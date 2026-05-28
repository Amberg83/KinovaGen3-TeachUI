import time
import math
import logging
import threading
import copy
from .robot_state import RobotState
from utils.event_bus import EventBus

class MockKinovaHardware:
    """
    Simulated/Mock hardware driver for the Kinova Gen3 robot.
    Emulates physical connections, state polling (20Hz), joint/gripper actions, 
    and fault modes to support 100% offline development, testing, and display.
    """
    def __init__(self, ip="127.0.0.1", username="admin", password=""):
        self.ip = ip
        self.username = username
        self.password = password
        self.logger = logging.getLogger("MockHardware")
        
        self.state = RobotState()
        self._is_polling = False
        self._polling_thread = None
        self._active_movement_pager = None
        self._estop_active = False
        self._fault_loop_active = False
        
        # Initialize default joint states
        self.state.is_connected = False
        self.state.ip = ip
        self.state.dof = 6
        self.state.joint_angles_deg = [0.0, 15.0, -130.0, 0.0, 55.0, 90.0]
        self.state.joint_velocities = [0.0] * 6
        self.state.joint_torques = [0.0] * 6
        self.state.joint_currents = [0.0] * 6
        self.state.joint_temperatures = [35.0] * 6
        self.state.joint_voltage = [24.0] * 6
        self.state.tcp_position = [0.35, 0.0, 0.45]
        self.state.tcp_orientation = [180.0, 0.0, 90.0]

    def connect(self):
        self.logger.info(f"[Mock] Simulating connection to robot at {self.ip}...")
        time.sleep(0.5) # Simulate minor network handshake delay
        
        self.state.is_connected = True
        self.state.ip = self.ip
        self.state.dof = 6
        
        self._is_polling = True
        self._polling_thread = threading.Thread(target=self._mock_polling_worker, daemon=True)
        self._polling_thread.start()
        
        self.logger.info("[Mock] Connection successful! Simulated 6-DOF robotic arm ready.")
        EventBus.publish("robot_connected")
        self.move_to_default()
        return True, "Successfully connected to mock robot"

    def disconnect(self, block_sound=False):
        if self.state.is_connected:
            self.logger.info("[Mock] Disconnecting from mock robot...")
            EventBus.publish("robot_disconnected", block=block_sound)
            
        self._is_polling = False
        if self._polling_thread:
            self._polling_thread.join(timeout=1.0)
            self._polling_thread = None
            
        self.state.is_connected = False
        self._active_movement_pager = None
        return True

    def apply_emergency_stop(self):
        if self.state.is_connected:
            self.logger.critical("[Mock] EMERGENCY STOP APPLIED!")
            self._estop_active = True
            self.state.has_fault = True
            EventBus.publish("estop_activated")
            self._trigger_fault_sequence()

    def clear_faults(self):
        if self.state.is_connected:
            self.logger.info("[Mock] Clear Faults command dispatched.")
            self._estop_active = False
            self.state.has_fault = False
            self.trigger_fault_cleared()

    def trigger_fault_cleared(self):
        if self.state.has_fault:
            self.state.has_fault = False
            EventBus.publish("fault_cleared")
            self.logger.info("[Mock] Robot Fault successfully cleared.")

    def _trigger_fault_sequence(self):
        if not self._fault_loop_active:
            self._fault_loop_active = True
            threading.Thread(target=self._fault_beep_loop, daemon=True).start()

    def _fault_beep_loop(self):
        if self._estop_active:
            # E-stop siren wait duration simulation
            for _ in range(6):
                if not self.state.has_fault or not self.state.is_connected:
                    break
                time.sleep(0.5)
            self._estop_active = False
            
        while self.state.is_connected and self.state.has_fault:
            EventBus.publish("fault")
            for _ in range(6):
                if not self.state.has_fault or not self.state.is_connected:
                    break
                time.sleep(0.5)
        self._fault_loop_active = False

    def set_admittance(self, mode_str):
        if not self.state.is_connected:
            return False
        
        self.logger.info(f"[Mock] Applying Admittance Mode: {mode_str}")
        self.state.control_mode = 1 if mode_str != "Disabled" else 0
        if mode_str == "Disabled":
            EventBus.publish("admittance_disabled")
        else:
            EventBus.publish("admittance_enabled")
        return True

    def execute_action_pose(self, target_pos_deg, duration_s, action_name="Move"):
        pager = threading.Event()
        self._last_action_success = True
        if not self.state.is_connected or self.state.has_fault:
            self.logger.warning("[Mock] Aborted action execution: Robot offline or in fault.")
            self._last_action_success = False
            pager.set()
            return pager
            
        self._active_movement_pager = pager
        self.logger.info(f"[Mock] Starting joint interpolation to {target_pos_deg} over {duration_s:.2f}s...")
        
        threading.Thread(
            target=self._interpolate_joints,
            args=(list(self.state.joint_angles_deg), target_pos_deg, float(duration_s), pager),
            daemon=True
        ).start()
        
    def execute_waypoint_list(self, waypoint_list):
        """Mock implementation of waypoint list execution."""
        pager = threading.Event()
        self._last_action_success = True
        if not self.state.is_connected or self.state.has_fault:
            self.logger.warning("[Mock] Aborted waypoint list execution: Robot offline or in fault.")
            self._last_action_success = False
            pager.set()
            return pager

        self._active_movement_pager = pager
        
        def worker():
            for i, wp in enumerate(waypoint_list.waypoints):
                if not self.state.is_connected or self.state.has_fault:
                    self._last_action_success = False
                    break
                target_angles = list(wp.angular_waypoint.angles)
                duration = wp.angular_waypoint.duration
                self.logger.info(f"[Mock] Waypoint {i+1}/{len(waypoint_list.waypoints)}: Interpolating to {target_angles} over {duration:.2f}s...")
                
                sub_pager = threading.Event()
                threading.Thread(
                    target=self._interpolate_joints,
                    args=(list(self.state.joint_angles_deg), target_angles, float(duration), sub_pager),
                    daemon=True
                ).start()
                sub_pager.wait()
                
                if not self._last_action_success:
                    break
            
            self._active_movement_pager = None
            pager.set()
            if self._last_action_success:
                self.logger.info("[Mock] Waypoint list execution completed.")
            else:
                self.logger.error("[Mock] Waypoint list execution failed.")

        threading.Thread(target=worker, daemon=True).start()
        return pager

    def move_to_default(self):
        return self.execute_action_pose([0.0]*6, 5.0, "Origin")

    def _interpolate_joints(self, start_angles, target_angles, duration, pager):
        steps = int(duration * 20.0) # 20Hz update steps
        if steps <= 0:
            steps = 1
            
        for step in range(1, steps + 1):
            if not self.state.is_connected or self.state.has_fault:
                self._last_action_success = False
                self._active_movement_pager = None
                pager.set()
                return
                
            t = step / steps
            # Smooth ease-in-ease-out sine interpolation
            t_smooth = 0.5 - 0.5 * math.cos(t * math.pi)
            
            new_angles = []
            for start, target in zip(start_angles, target_angles):
                angle = start + (target - start) * t_smooth
                new_angles.append(angle)
                
            self.state.joint_angles_deg = new_angles
            
            # Simulate corresponding small TCP drift based on joints
            self.state.tcp_position[0] = 0.35 + 0.1 * math.sin(t_smooth * math.pi)
            self.state.tcp_position[1] = 0.0 + 0.1 * math.cos(t_smooth * math.pi)
            self.state.tcp_position[2] = 0.45 + 0.05 * math.sin(t_smooth * math.pi * 2)
            
            time.sleep(0.05)
            
        self.state.joint_angles_deg = target_angles
        self.state.joint_velocities = [0.0] * 6
        self._active_movement_pager = None
        pager.set()
        self.logger.info("[Mock] Movement completed.")

    def _mock_polling_worker(self):
        """Generates realistic telemetry waveforms (20Hz) to keep the GUI feeling alive."""
        count = 0
        while self._is_polling:
            if self.state.is_connected and not self._active_movement_pager:
                # Add tiny natural noise oscillation to joint parameters, voltages, and currents
                count += 1
                osc = math.sin(count * 0.1)
                
                # Update temperatures/voltages with realistic noise
                self.state.joint_temperatures = [35.0 + 0.5 * osc] * 6
                self.state.joint_voltage = [24.0 + 0.1 * osc] * 6
                self.state.joint_currents = [0.1 + 0.05 * math.cos(count * 0.1)] * 6
                
                # Small TCP vibration
                self.state.torque = [0.1 * osc, -0.05 * osc, 0.15 * osc]
                
            self._publish_state()
            time.sleep(0.05)

    def _publish_state(self):
        """Thread-safe event broadcast of an isolated snapshot copy."""
        state_copy = copy.copy(self.state)
        # Deepcopy list fields to prevent read/write thread mutation races!
        state_copy.tcp_position = list(self.state.tcp_position)
        state_copy.tcp_orientation = list(self.state.tcp_orientation)
        state_copy.tcp_linear_velocity = list(self.state.tcp_linear_velocity)
        state_copy.tcp_angular_velocity = list(self.state.tcp_angular_velocity)
        state_copy.force = list(self.state.force)
        state_copy.torque = list(self.state.torque)
        state_copy.joint_angles_deg = list(self.state.joint_angles_deg)
        state_copy.joint_velocities = list(self.state.joint_velocities)
        state_copy.joint_torques = list(self.state.joint_torques)
        state_copy.joint_currents = list(self.state.joint_currents)
        state_copy.joint_temperatures = list(self.state.joint_temperatures)
        state_copy.joint_voltage = list(self.state.joint_voltage)
        
        EventBus.publish("hardware_telemetry_updated", state_copy)
