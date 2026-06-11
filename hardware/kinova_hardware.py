import time
import threading
import logging
from kortex_api.autogen.client_stubs.BaseClientRpc import BaseClient
from kortex_api.autogen.client_stubs.BaseCyclicClientRpc import BaseCyclicClient
from kortex_api.autogen.client_stubs.ControlConfigClientRpc import ControlConfigClient
from kortex_api.autogen.messages import Base_pb2, Session_pb2
from kortex_api.RouterClient import RouterClient, RouterClientSendOptions
from kortex_api.SessionManager import SessionManager
from kortex_api.TCPTransport import TCPTransport
from kortex_api.UDPTransport import UDPTransport

from .robot_state import RobotState 
from utils.event_bus import EventBus
from utils.duration_calculator import calculate_min_trajectory_duration

class KinovaHardware:
    """Handles direct communication with the Kinova Gen3 Robot via the Kortex API."""
    def __init__(self, ip="10.163.65.187", username="admin", password="admin"):
        self.logger = logging.getLogger("Hardware")
        self.ip = ip
        self.username = username
        self.password = password
        
        # Load configurable defaults from config/ files
        self.default_pose = [0.0, 50.0, 264.0, 0.0, 58.0, 90.0]
        self.default_gripper_pos = 0.0
        self.polling_frequency_hz = 20
        self.gripper_presets = {"open": 0.0, "closed": 100.0, "pickup": 50.0}
        self.gripper_speed_presets = {"slow": 0.2, "medium": 0.5, "fast": 0.0}
        self.connection_timeout_ms = 10000
        
        import os
        import json
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 1. Load Network configuration
        net_path = os.path.join(base_dir, "config", "network_config.json")
        if os.path.exists(net_path):
            try:
                with open(net_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    self.polling_frequency_hz = int(cfg.get("polling_frequency_hz", 20))
                self.logger.info(f"Loaded polling frequency: {self.polling_frequency_hz}Hz")
            except Exception as e:
                self.logger.error(f"Failed to load network config in Hardware: {e}")
                
        # 2. Load Robot configuration
        rob_path = os.path.join(base_dir, "config", "robot_config.json")
        if os.path.exists(rob_path):
            try:
                with open(rob_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    self.default_pose = list(cfg.get("default_pose", self.default_pose))
                    self.gripper_presets = cfg.get("gripper_presets", self.gripper_presets)
                    self.gripper_speed_presets = cfg.get("gripper_speed_presets", self.gripper_speed_presets)
                    
                    default_g = cfg.get("default_gripper_pos", 0.0)
                    if isinstance(default_g, str):
                        self.default_gripper_pos = float(self.gripper_presets.get(default_g.lower(), 0.0))
                    else:
                        self.default_gripper_pos = float(default_g)
                    
                    conn = cfg.get("hardware_connection", {})
                    self.connection_timeout_ms = int(conn.get("connection_timeout_ms", 10000))
                self.logger.info(f"Loaded robot settings from {rob_path}")
            except Exception as e:
                self.logger.error(f"Failed to load robot config in Hardware: {e}")
        
        self.base = None
        self.base_cyclic = None
        self.control_config = None
        self._transports = []
        self._sessions = []

        self.state = RobotState()
        self.missed_feedback_count = 0

        self._global_notification_handle = None
        self._global_armstate_handle = None
        self._global_control_mode_handle = None
        self._active_movement_pager = None
        
        self._is_polling = False
        self._polling_thread = None
        self._is_action_paused = False
        self._fault_loop_active = False
        self._estop_active = False

    def notify_observers(self):
        """Thread-safely publishes an isolated snapshot of the current state on the EventBus."""
        import copy
        state_copy = copy.copy(self.state)
        # Deepcopy list fields to prevent read/write thread mutation races
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

    def connect(self):
        """Establishes network connections and starts background telemetry polling."""
        self.logger.info(f"Attempting connection to robot at {self.ip} as user '{self.username}'...")
        
        try:
            tcp = TCPTransport()
            tcp.connect(self.ip, 10000)
            router_tcp = RouterClient(tcp, RouterClient.basicErrorCallback)
            
            udp = UDPTransport()
            udp.connect(self.ip, 10001)
            router_udp = RouterClient(udp, RouterClient.basicErrorCallback)

            self._transports.extend([tcp, udp])

            session_info = Session_pb2.CreateSessionInfo()
            session_info.username = self.username
            session_info.password = self.password
            session_info.session_inactivity_timeout = 60000 
            session_info.connection_inactivity_timeout = 5000 

            session_tcp = SessionManager(router_tcp)
            session_tcp.CreateSession(session_info)
            session_udp = SessionManager(router_udp)
            session_udp.CreateSession(session_info)
            
            self._sessions.extend([session_tcp, session_udp])

            self.base = BaseClient(router_tcp)
            self.base_cyclic = BaseCyclicClient(router_udp)
            self.control_config = ControlConfigClient(router_tcp)
            
            try:
                mode_info = self.control_config.GetControlMode()
                self.state.control_mode = mode_info.control_mode
            except Exception as e:
                self.logger.warning(f"Could not fetch initial control mode: {e}")
            
            self.state.is_connected = True
            self.state.ip = self.ip
            self.notify_observers()
            
            self._start_internal_polling()

            time.sleep(0.5)
            self._start_global_listeners()
            
            self.logger.info(f"Connection successful! Hardware detected as a {self.state.dof}-DOF robotic arm.")
            EventBus.publish("robot_connected")
            return True, f"Successfully connected to {self.ip}"
            
        except Exception as e:
            self.state.is_connected = False
            self.notify_observers()
            self.logger.error(f"Connection attempt failed: {str(e)}")
            return False, str(e)
 
    def move_to_default(self):
        pager = threading.Event()
        
        def worker():
            # Calculate speed and start the arm trajectory first
            speed = calculate_min_trajectory_duration(self.state.joint_angles_deg, self.default_pose, speed="medium")
            movement_pager = self.execute_action_pose(self.default_pose, speed, "Origin")
            
            # Wait for joint movement to fully complete (timeout safe-guard of 15 seconds)
            movement_pager.wait(timeout=15.0)
            
            # As soon as the listener sets movement_pager (meaning the arm has finished moving),
            # adjust the gripper to the custom default gripper position.
            gripper_pager = self.execute_gripper_action("", "medium", target_pos=self.default_gripper_pos)
            # Wait for gripper movement to settle/complete (timeout 3 seconds)
            gripper_pager.wait(timeout=3.0)
            
            # Movement completed fully: play the replay completion chime!
            EventBus.publish("replay_finished")
            
            pager.set()
            
        threading.Thread(target=worker, daemon=True).start()
        return pager
 
    def disconnect(self, block_sound=False):
        """Stops polling threads and closes all API sessions."""
        if self.state.is_connected:
            self.logger.info("Disconnecting from robot and closing network sessions...")
            EventBus.publish("robot_disconnected", block=block_sound)
            
        self._stop_internal_polling()
        self._stop_global_listeners()
        
        self.state.is_connected = False
        self.notify_observers()
        
        self.control_config = None
        for session in self._sessions:
            try: session.CloseSession()
            except: pass
        for transport in self._transports:
            try: transport.disconnect()
            except: pass
        self._sessions.clear()
        self._transports.clear()

    def trigger_fault_detected(self):
        """Thread-safely handles detecting the fault state and starting the beep loop."""
        if not self.state.has_fault:
            self.state.has_fault = True
            if not self._fault_loop_active:
                self._fault_loop_active = True
                EventBus.publish("estop")
                threading.Thread(target=self._fault_beep_loop, daemon=True).start()
            self.logger.critical("Robot entered a Faulty State!")

    def trigger_fault_cleared(self):
        """Thread-safely handles clearing the fault state and playing the success chime."""
        if self.state.has_fault:
            self.state.has_fault = False
            EventBus.publish("fault_cleared")
            self.logger.info("Robot Fault successfully cleared.")

    def _fault_beep_loop(self):
        """Asynchronously repeats the fault warning sound every 5 seconds while in fault."""
        while self.state.is_connected and self.state.has_fault:
            # Sleep in 0.5s increments to respond instantly when faults are cleared
            time.sleep(5.0)
            if not self.state.has_fault or not self.state.is_connected:
                break
            EventBus.publish("fault")
        self._fault_loop_active = False

    def _start_global_listeners(self):
        """Starts implemented event subscribers."""
        if not self.base: return

        # --- Action_Event Subscriber ---
        def action_callback(notification):
            event_type = notification.action_event
            action_id = notification.handle.identifier
            action_type_enum = notification.handle.action_type
            
            try:
                action_type_name = Base_pb2.ActionType.Name(action_type_enum)
            except Exception:
                action_type_name = str(action_type_enum)

            if event_type == Base_pb2.ACTION_END:
                self.logger.info(f"Action ({action_id}, {action_type_name}) completed.")
                if self._active_movement_pager:
                    self._active_movement_pager.set()
                    self._active_movement_pager = None
            elif event_type == Base_pb2.ACTION_ABORT:
                self.logger.error(f"Action ({action_id}, {action_type_name}) aborted with Code: {notification.abort_details}")
                self._last_action_success = False
                if self._active_movement_pager:
                    self._active_movement_pager.set()
                    self._active_movement_pager = None
            elif event_type == Base_pb2.ACTION_START:
                self.logger.info(f"Action ({action_id}, {action_type_name}) started.")
            elif event_type == Base_pb2.ACTION_PAUSE:
                self.logger.info(f"Action ({action_id}, {action_type_name}) paused.")

        # --- Arm_State Subscriber ---
        def arm_state_callback(notification):
            active_state = notification.active_state
            if active_state == Base_pb2.ARMSTATE_IN_FAULT:
                self.trigger_fault_detected()
                self._last_action_success = False
                if self._active_movement_pager:
                    self._active_movement_pager.set()
                    self._active_movement_pager = None
            elif active_state == Base_pb2.ARMSTATE_IDLE:
                self.trigger_fault_cleared()

        # --- Control_Mode Subscriber ---
        def control_mode_callback(notification):
            self.state.control_mode = notification.control_mode
            self.logger.debug(f"Control Mode updated via notification: {notification.control_mode}")
            self.notify_observers()

        # --- Register Subscribers ---
        try:
            self.logger.info("Starting event subscribers (ActionEvent, ArmState, ControlMode)...")
            self._global_notification_handle = self.base.OnNotificationActionTopic(action_callback, Base_pb2.NotificationOptions())
            self._global_armstate_handle = self.base.OnNotificationArmStateTopic(arm_state_callback, Base_pb2.NotificationOptions())
            if self.control_config:
                self._global_control_mode_handle = self.control_config.OnNotificationControlModeTopic(control_mode_callback, Base_pb2.NotificationOptions())
        except Exception as e:
            self.logger.error(f"Could not start all event subscribers: {e}")

    def _stop_global_listeners(self):
        """Stops all subscribers."""
        if not self.base: return
        
        handles = [
            (self.base, self._global_notification_handle),
            (self.base, self._global_armstate_handle),
            (self.control_config, self._global_control_mode_handle)
        ]
        
        for client, handle in handles:
            if client and handle:
                try: client.Unsubscribe(handle)
                except Exception: pass
                
        self._global_notification_handle = None
        self._global_armstate_handle = None
        self._global_control_mode_handle = None
        self._global_robotevent_handle = None
        self.logger.info("Closed all event subscribers.")

    def _start_internal_polling(self):
        """Starts the autonomous hardware polling thread."""
        if not self._is_polling:
            self._is_polling = True
            self._polling_thread = threading.Thread(target=self._hardware_polling_worker, daemon=True)
            self._polling_thread.start()
            self.logger.debug("Internal hardware telemetry polling started.")

    def _stop_internal_polling(self):
        """Stops the hardware polling thread."""
        self._is_polling = False
        if self._polling_thread:
            self._polling_thread.join(timeout=1.0)
            self._polling_thread = None

    def _hardware_polling_worker(self):
        """Autonomous thread continuously fetching telemetry data (polling frequency configurable, faster yields smoother rendering)."""
        dt = 1.0 / self.polling_frequency_hz
        while self._is_polling:
            try:
                if self.state.is_connected:
                    self.refresh_state_from_robot()
            except Exception as e:
                self.logger.debug(f"Hardware polling missed a cycle: {e}")
            time.sleep(dt) 

    def refresh_state_from_robot(self):
        """Fetches telemetry data and profiles network latency."""
        if not self.state.is_connected or not self.base_cyclic: 
            return False

        try:
            # Dynamically calculate RPC timeout (ms) based on the configured polling loop budget
            # Timeout = clamp(10ms, 70% of loop budget, 35ms)
            loop_budget_ms = (1.0 / self.polling_frequency_hz) * 1000.0
            timeout_ms = max(10, min(35, int(loop_budget_ms * 0.7)))
            
            options = RouterClientSendOptions()
            options.timeout_ms = timeout_ms
            feedback = self.base_cyclic.RefreshFeedback(options=options)
            self.missed_feedback_count = 0 
        except Exception as e:
            self.missed_feedback_count += 1
            # Support up to 3.0 seconds of transient UDP jitter (scaled based on polling rate)
            max_missed = int(3.0 * self.polling_frequency_hz)
            if self.missed_feedback_count > max_missed:
                self.logger.error(f"Connection lost: Exceeded UDP timeout limit. Error: {e}")
                self.state.is_connected = False
                self.notify_observers()
            return False

        try:
            self.state.dof = len(feedback.actuators)
            self.state.fault_bank_a = getattr(feedback.base, 'fault_bank_a', 0)
            self.state.fault_bank_b = getattr(feedback.base, 'fault_bank_b', 0)
            active_state_val = getattr(feedback.base, 'active_state', 0)
            self.state.active_state = active_state_val
            
            # Encapsulated state updates via atomic triggers to eliminate race conditions
            is_currently_faulted = (active_state_val == Base_pb2.ARMSTATE_IN_FAULT) or \
                                   (self.state.fault_bank_a != 0) or \
                                   (self.state.fault_bank_b != 0)
            
            if is_currently_faulted:
                self.trigger_fault_detected()
            else:
                self.trigger_fault_cleared()
            
            self.state.tcp_position = [
                getattr(feedback.base, 'tool_pose_x', 0.0), getattr(feedback.base, 'tool_pose_y', 0.0), getattr(feedback.base, 'tool_pose_z', 0.0)
            ]
            self.state.tcp_orientation = [
                getattr(feedback.base, 'tool_pose_theta_x', 0.0), getattr(feedback.base, 'tool_pose_theta_y', 0.0), getattr(feedback.base, 'tool_pose_theta_z', 0.0)
            ]
            
            self.state.joint_angles_deg = [round(getattr(a, 'position', 0.0), 2) for a in feedback.actuators]
            self.state.joint_velocities = [round(getattr(a, 'velocity', 0.0), 2) for a in feedback.actuators]
            self.state.joint_torques =    [round(getattr(a, 'torque', 0.0), 2) for a in feedback.actuators]
            self.state.joint_currents =   [round(getattr(a, 'current_motor', 0.0), 2) for a in feedback.actuators]
            self.state.joint_temperatures = [round(getattr(a, 'temperature_motor', 0.0), 1) for a in feedback.actuators]
            
            # Read tool gripper feedback if available
            try:
                if hasattr(feedback, 'interconnect') and hasattr(feedback.interconnect, 'gripper_feedback'):
                    g_feedback = feedback.interconnect.gripper_feedback
                    if g_feedback.motor:
                        self.state.gripper_position = round(g_feedback.motor[0].position, 1)
                        self.state.gripper_current = round(g_feedback.motor[0].current_motor, 2)
                    else:
                        self.state.gripper_position = 0.0
                        self.state.gripper_current = 0.0
                else:
                    self.state.gripper_position = 0.0
                    self.state.gripper_current = 0.0
            except Exception:
                self.state.gripper_position = 0.0
                self.state.gripper_current = 0.0

            self.notify_observers()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Data Parsing Error: {e}")
            return False

    def execute_action_pose(self, target_pos_deg, duration_s, action_name="Move"):
        """Executes deployed action."""
        pager = threading.Event()
        self._last_action_success = True

        if not self.state.is_connected or self.state.has_fault:
            self.logger.warning(f"Aborted action execution: Robot offline or in fault state.")
            self._last_action_success = False
            pager.set()
            return pager

        # measure distance for fail save
        current_deg = self.state.joint_angles_deg
        max_diff = 0.0
        if current_deg and len(current_deg) == len(target_pos_deg):
            for p, c in zip(current_deg, target_pos_deg):
                diff = c - p
                if diff > 180.0: diff -= 360.0
                elif diff < -180.0: diff += 360.0
                max_diff = max(max_diff, abs(diff))
                
            if max_diff < 0.1:
                self.logger.info(f"Skipping '{action_name}': Destination already reached.")
                pager.set()
                return pager

        # action creation
        action = Base_pb2.Action()
        action.name = action_name
        for i, angle in enumerate(target_pos_deg):
            safe_angle = float(angle) % 360.0
            if safe_angle < 0: safe_angle += 360.0
            ja = action.reach_joint_angles.joint_angles.joint_angles.add()
            ja.joint_identifier = i
            ja.value = safe_angle

        # construct safe time-frame for movement action
        if duration_s > 0.0:
            min_safe_duration = calculate_min_trajectory_duration(current_deg, target_pos_deg)
            actual_duration = max(float(duration_s), min_safe_duration)
            try: 
                action.reach_joint_angles.constraint.type = Base_pb2.JOINT_CONSTRAINT_DURATION
            except AttributeError: 
                action.reach_joint_angles.constraint.type = 1 
            action.reach_joint_angles.constraint.value = float(actual_duration)
            log_msg = f"Action '{action_name}' sent to robot (Time constraint: {actual_duration:.2f}s)."
        else:
            log_msg = f"Action '{action_name}' sent to robot with NO duration constraint (Executing at maximum physical speed!)."

        # Notify application about new constructed action
        self._active_movement_pager = pager
        
        try:
            self.logger.info(log_msg)
            self.base.ExecuteAction(action)
        except Exception as e:
            self.logger.error(f"Exception during API action call (Action '{action_name}'): {e}")
            self._last_action_success = False
            pager.set()
            self._active_movement_pager = None
            
        return pager


    def execute_waypoint_list(self, waypoint_list):
        """Executes deployed WaypointList."""
        pager = threading.Event()
        self._last_action_success = True

        if not self.state.is_connected or self.state.has_fault:
            self._last_action_success = False
            pager.set()
            return pager

        self._active_movement_pager = pager

        try:
            self.logger.info(f"WaypointList ({len(waypoint_list.waypoints)} Points) sent to robot.")
            self.base.ExecuteWaypointTrajectory(waypoint_list)
        except Exception as e:
            self.logger.error(f"Exception during API WaypointList call: {e}")
            self._last_action_success = False
            
            # Retrieve exact trajectory error report from base
            try:
                validation_res = self.base.ValidateWaypointList(waypoint_list)
                errors = validation_res.trajectory_error_report.trajectory_error_elements
                if errors:
                    error_msgs = []
                    for i, err in enumerate(errors):
                        # Clean up formatting to keep it on one line in log
                        err_str = str(err).replace('\n', ' ').strip()
                        error_msgs.append(f"Err #{i+1}: {err_str}")
                    self.logger.error("Trajectory Error Report: " + " | ".join(error_msgs))
                else:
                    self.logger.error("Trajectory Error Report: No specific validation errors returned.")
            except Exception as val_e:
                self.logger.error(f"Failed to retrieve validation report: {val_e}")
                
            pager.set()
            self._active_movement_pager = None
            
        return pager

    def stop(self):
        """Sends a gentle deceleration command to stop the current movement."""
        if self.state.is_connected and self.base:
            try:
                self.base.Stop()
                self.logger.info("Gentle Stop command successfully executed.")
            except Exception as e:
                self.logger.error(f"API Error during gentle Stop: {e}")

    def toggle_pause_action(self):
        """Toggles a Pause to later resume the same action"""
        if self.state.is_connected and self.base:
            try:
                if self._is_action_paused:
                    self.base.ResumeAction()
                    self._is_action_paused = False
                    self.logger.info("Action resumed.")
                else:
                    self.base.PauseAction()
                    self._is_action_paused = True
                    self.logger.info("Action paused.")
            except Exception as e:
                self.logger.error(f"API Error during Pause/Unpause: {e}")

    def apply_emergency_stop(self):
        """Sends an immediate Emergency Stop."""
        if self.state.is_connected and self.base:
            try: 
                self._estop_active = True
                self.base.ApplyEmergencyStop()
                self.logger.critical("EMERGENCY STOP APPLIED! Physical robot reset might be required.")
            except Exception as e: 
                self.logger.error(f"API Error during E-Stop: {e}")

    def clear_faults(self):
        """Attempts to clear minor software faults and warnings."""
        if self.state.is_connected and self.base:
            try:
                self._estop_active = False
                self.base.ClearFaults()
                self.logger.info("Clear Faults command dispatched to robot controller.")
            except Exception as e:
                self.logger.error(f"Failed to clear faults: {e}")

    def set_admittance(self, mode_str):
        """Sets the admittance control mode on the robot arm."""
        if not self.state.is_connected or not self.base:
            self.logger.warning("Cannot set admittance: Robot disconnected.")
            return False

        try:
            mode_map = {
                "Cartesian": getattr(Base_pb2, 'CARTESIAN', 1),
                "Joint": getattr(Base_pb2, 'JOINT', 2),
                "Null-Space": getattr(Base_pb2, 'NULL_SPACE', 3),
                "Disabled": getattr(Base_pb2, 'DISABLED', 4)
            }
            
            target_enum = mode_map.get(mode_str, 0)
            
            admittance = Base_pb2.Admittance()
            admittance.admittance_mode = target_enum
            
            self.base.SetAdmittance(admittance)
            self.logger.info(f"Successfully set Admittance Mode to: {mode_str}")
            if mode_str == "Disabled":
                EventBus.publish("admittance_disabled")
            else:
                EventBus.publish("admittance_enabled")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to set admittance mode '{mode_str}': {e}")
            return False

    def execute_gripper_action(self, state_str, duration_str="medium", target_pos=None, speed_ratio=None):
        """Sends gripper command to Kortex API. Returns a waitable event."""
        pager = threading.Event()
        self._last_action_success = True
        
        if not self.state.is_connected or not self.base:
            self._last_action_success = False
            pager.set()
            return pager

        # 1. Resolve target position (percentage between 0.0 and 100.0)
        if target_pos is not None:
            resolved_target = float(target_pos)
        else:
            resolved_target = self.gripper_presets.get(state_str.lower(), 0.0)

        # 2. Resolve speed ratio (between 0.0 and 1.0)
        if speed_ratio is not None:
            resolved_speed = float(speed_ratio)
        else:
            resolved_speed = self.gripper_speed_presets.get(duration_str.lower(), 0.5)

        def gripper_worker():
            try:
                self.logger.info(f"Sending gripper command: State={state_str}, Duration={duration_str}, target_pos={resolved_target}, speed_ratio={resolved_speed}")
                
                # A. Fast Movement: use standard GRIPPER_POSITION mode (resolved_speed == 0.0)
                if resolved_speed == 0.0:
                    gripper_command = Base_pb2.GripperCommand()
                    gripper_command.mode = Base_pb2.GRIPPER_POSITION
                    
                    # Convert percentage (0-100) to normalized fraction where 0.0 is fully open and 1.0 is fully closed
                    normalized_pos = max(0.0, min(1.0, resolved_target / 100.0))
                    
                    finger = gripper_command.gripper.finger.add()
                    finger.finger_identifier = 1
                    finger.value = normalized_pos
                    
                    self.base.SendGripperCommand(gripper_command)
                    time.sleep(1.2) # Fast movement mechanical transit time
                    pager.set()
                    return
                
                # B. Velocity Control Mode: use GRIPPER_SPEED (resolved_speed > 0.0)
                speed_mag = max(0.01, min(1.0, resolved_speed))
                current_pos = self.state.gripper_position
                
                # Determine command velocity sign (positive speed opens towards 0%, negative speed closes towards 100%)
                if resolved_target < current_pos:
                    cmd_speed = speed_mag
                elif resolved_target > current_pos:
                    cmd_speed = -speed_mag
                else:
                    self.logger.info(f"Gripper already at target position ({resolved_target}%). No movement needed.")
                    pager.set()
                    return
                        
                # Start speed command
                self.logger.info(f"Starting GRIPPER_SPEED mode movement at speed {cmd_speed} towards target {resolved_target}%")
                gripper_command = Base_pb2.GripperCommand()
                gripper_command.mode = Base_pb2.GRIPPER_SPEED
                finger = gripper_command.gripper.finger.add()
                finger.finger_identifier = 1
                finger.value = cmd_speed
                
                self.base.SendGripperCommand(gripper_command)
                
                # Monitor position telemetry feedback at 20Hz (50ms cycles)
                last_positions = []
                max_loop_cycles = 160 # Fail-safe timeout after 8.0s (160 * 50ms)
                
                for cycle in range(max_loop_cycles):
                    time.sleep(0.05)
                    current_pos = self.state.gripper_position
                    
                    # Check if destination reached (with 3.5% headroom to handle 20Hz latency)
                    is_reached = False
                    if cmd_speed > 0: # Opening (moving towards smaller percentage)
                        if current_pos <= (resolved_target + 3.5):
                            is_reached = True
                    else: # Closing (moving towards larger percentage)
                        if current_pos >= (resolved_target - 3.5):
                            is_reached = True
                            
                    if is_reached:
                        self.logger.info(f"Target position reached (current={current_pos}%, target={resolved_target}%). Stopping.")
                        break
                            
                    # Stalled / End limit check
                    last_positions.append(current_pos)
                    if len(last_positions) > 5:
                        last_positions.pop(0)
                        
                        # Detect if the position has stopped changing (absolute variation < 0.15%)
                        if len(last_positions) == 5:
                            max_diff = max(last_positions) - min(last_positions)
                            if max_diff < 0.15:
                                self.logger.info(f"Gripper movement stalled/completed at {current_pos}%. Stopping.")
                                break
                                
                # Send the stop command (velocity = 0.0) to hold position
                stop_command = Base_pb2.GripperCommand()
                stop_command.mode = Base_pb2.GRIPPER_SPEED
                stop_finger = stop_command.gripper.finger.add()
                stop_finger.finger_identifier = 1
                stop_finger.value = 0.0
                
                self.base.SendGripperCommand(stop_command)
                self.logger.info("GRIPPER_SPEED movement stopped.")
                pager.set()
            except Exception as e:
                self.logger.error(f"Error during physical GRIPPER_SPEED loop execution: {e}")
                self._last_action_success = False
                pager.set()

        threading.Thread(target=gripper_worker, daemon=True).start()
        return pager
    
    def validate_waypoint_list(self, waypoint_list):
        """Validates a WaypointList against the robot's kinematic and safety limits. Currently not in use."""
        if not self.state.is_connected or not self.base:
            return False, "Robot disconnected."
        try:
            res = self.base.ValidateWaypointList(waypoint_list)
            if len(res.trajectory_error_report.trajectory_error_elements) > 0:
                # Sammle alle Fehler in einem String
                error_msgs = [err.message for err in res.trajectory_error_report.trajectory_error_elements]
                return False, " | ".join(error_msgs)
            return True, "Validation successful."
        except Exception as e:
            return False, f"API Exception during validation: {e}"

