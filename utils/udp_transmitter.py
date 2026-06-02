import socket
import json
import logging
from utils.event_bus import EventBus
from hardware.robot_state import RobotState

class UDPTransmitter:
    """
    Subscribes to 'hardware_telemetry_updated' events and streams
    the robot's joint angles and gripper position over a UDP socket to a local Unity listener.
    """
    def __init__(self, host="127.0.0.1", port=5005):
        self.logger = logging.getLogger("UDPTransmitter")
        
        # Load configuration from config/network_config.json if available
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, "config", "network_config.json")
        
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    host = cfg.get("udp_host", host)
                    port = cfg.get("udp_port", port)
                self.logger.info(f"Loaded network settings from {config_path}: {host}:{port}")
            except Exception as e:
                self.logger.error(f"Failed to load network config: {e}. Using defaults.")
                
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.last_sent_data = None
        self.preview_angles = None
        self.preview_gripper = None
        self.last_gripper_position = 0.0
        
        # Subscribe to telemetry updates and preview requests
        EventBus.subscribe("hardware_telemetry_updated", self.send_telemetry)
        EventBus.subscribe("set_preview_angles", self.set_preview_angles)
        EventBus.subscribe("clear_preview_angles", self.clear_preview_angles)
        self.logger.info(f"UDP Transmitter initialized. Streaming to {self.host}:{self.port}")
 
    def set_preview_angles(self, angles, gripper_pos=None):
        self.preview_angles = list(angles) if angles else None
        self.preview_gripper = gripper_pos
        if self.preview_angles:
            # Immediately transmit to Unity for instant teleportation preview
            g_pos = self.preview_gripper if self.preview_gripper is not None else self.last_gripper_position
            data = self.preview_angles + [g_pos]
            self._transmit(data)
 
    def clear_preview_angles(self):
        self.preview_angles = None
        self.preview_gripper = None
 
    def send_telemetry(self, state: RobotState):
        """Callback triggered when the robot state is updated."""
        if not state or not state.is_connected or not state.joint_angles_deg:
            return
        
        # Auto-reset preview if robot starts moving (magnitude of any joint velocity > 0.1 deg/s)
        if self.preview_angles is not None and state.joint_velocities:
            if any(abs(v) > 0.1 for v in state.joint_velocities):
                self.preview_angles = None
                self.preview_gripper = None
                self.logger.info("Cleared preview override automatically due to physical movement.")
        
        # Store last known gripper position
        self.last_gripper_position = getattr(state, "gripper_position", 0.0)
        
        angles_to_send = self.preview_angles if self.preview_angles is not None else state.joint_angles_deg
        g_pos = self.preview_gripper if (self.preview_angles is not None and self.preview_gripper is not None) else self.last_gripper_position
        data_to_send = list(angles_to_send) + [g_pos]
        
        # Only transmit if the joint angles or gripper have actually changed (threshold: 0.005)
        # Or if we haven't sent a packet in 20 cycles (acts as a keep-alive heartbeat for late-starting Unity twins)
        if self.last_sent_data is not None and len(self.last_sent_data) == 7:
            has_changed = False
            for prev, curr in zip(self.last_sent_data, data_to_send):
                if abs(curr - prev) > 0.005:
                    has_changed = True
                    break
            
            if not has_changed:
                self.skipped_count = getattr(self, "skipped_count", 0) + 1
                if self.skipped_count < 20: # 20 cycles @ 20Hz = 1.0 second heartbeat interval
                    return
        
        self.skipped_count = 0
        self._transmit(data_to_send)

    def _transmit(self, data):
        try:
            # Send simple comma-separated floats (6 joints + 1 gripper) for maximum Unity parsing reliability
            message = ",".join(map(str, data)).encode('utf-8')
            self.socket.sendto(message, (self.host, self.port))
            self.last_sent_data = list(data)
        except Exception as e:
            self.logger.error(f"Failed to transmit UDP telemetry: {e}")

    def close(self):
        """Clean up resources by unsubscribing and closing the socket."""
        EventBus.unsubscribe("hardware_telemetry_updated", self.send_telemetry)
        EventBus.unsubscribe("set_preview_angles", self.set_preview_angles)
        EventBus.unsubscribe("clear_preview_angles", self.clear_preview_angles)
        try:
            self.socket.close()
            self.logger.info("UDP socket closed successfully.")
        except Exception as e:
            self.logger.error(f"Error closing UDP socket: {e}")
