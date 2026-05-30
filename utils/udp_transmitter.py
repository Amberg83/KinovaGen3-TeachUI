import socket
import json
import logging
from utils.event_bus import EventBus
from hardware.robot_state import RobotState

class UDPTransmitter:
    """
    Subscribes to 'hardware_telemetry_updated' events and streams
    the robot's joint angles over a UDP socket to a local Unity listener.
    """
    def __init__(self, host="127.0.0.1", port=5005):
        self.logger = logging.getLogger("UDPTransmitter")
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.last_sent_angles = None
        
        # Subscribe to telemetry updates
        EventBus.subscribe("hardware_telemetry_updated", self.send_telemetry)
        self.logger.info(f"UDP Transmitter initialized. Streaming to {self.host}:{self.port}")

    def send_telemetry(self, state: RobotState):
        """Callback triggered when the robot state is updated."""
        if not state or not state.is_connected or not state.joint_angles_deg:
            return
        
        # Only transmit if the joint angles have actually changed (threshold: 0.005 degrees)
        # Or if we haven't sent a packet in 20 cycles (acts as a keep-alive heartbeat for late-starting Unity twins)
        if self.last_sent_angles is not None:
            has_changed = False
            for prev, curr in zip(self.last_sent_angles, state.joint_angles_deg):
                if abs(curr - prev) > 0.005:
                    has_changed = True
                    break
            
            if not has_changed:
                self.skipped_count = getattr(self, "skipped_count", 0) + 1
                if self.skipped_count < 20: # 20 cycles @ 20Hz = 1.0 second heartbeat interval
                    return
        
        self.skipped_count = 0
        
        try:
            # Send simple comma-separated floats for maximum Unity parsing reliability
            message = ",".join(map(str, state.joint_angles_deg)).encode('utf-8')
            self.socket.sendto(message, (self.host, self.port))
            self.last_sent_angles = list(state.joint_angles_deg)
        except Exception as e:
            self.logger.error(f"Failed to transmit UDP telemetry: {e}")

    def close(self):
        """Clean up resources by unsubscribing and closing the socket."""
        EventBus.unsubscribe("hardware_telemetry_updated", self.send_telemetry)
        try:
            self.socket.close()
            self.logger.info("UDP socket closed successfully.")
        except Exception as e:
            self.logger.error(f"Error closing UDP socket: {e}")
