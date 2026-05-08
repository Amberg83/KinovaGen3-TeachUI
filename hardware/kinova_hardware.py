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

def calculate_min_safe_duration(target_pos, predecessor_pos):
    """
    Computes the physical minimum safe duration (seconds) for moving between two joint positions
    using the industry-standard Trapezoidal Profile Estimation model.
    
    This is the SINGLE SOURCE OF TRUTH for robot joint transition limits across the system.
    """
    if not target_pos or not predecessor_pos or len(target_pos) != len(predecessor_pos):
        return 0.6
        
    # Cruising Speed: 55.0 deg/s, Ramp Overhead: 0.6s
    V_MAX = 49.5
    T_OVERHEAD = 0.5
    
    max_diff = 0.0
    for t, p in zip(target_pos, predecessor_pos):
        diff = t - p
        while diff > 180.0: diff -= 360.0
        while diff < -180.0: diff += 360.0
        max_diff = max(max_diff, abs(diff))
        
    return T_OVERHEAD + (max_diff / V_MAX)

class KinovaHardware:
    """Handles direct communication with the Kinova Gen3 Robot via the Kortex API."""
    def __init__(self, ip="10.163.65.187", username="admin", password="admin"):
        self.logger = logging.getLogger("Hardware")
        self.ip = ip
        self.username = username
        self.password = password
        
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
            self.move_to_default()
            return True, f"Successfully connected to {self.ip}"
            
        except Exception as e:
            self.state.is_connected = False
            self.notify_observers()
            self.logger.error(f"Connection attempt failed: {str(e)}")
            return False, str(e)
 
    def move_to_default(self):
        return self.execute_action_pose([0.0,0.0,0.0,0.0,0.0,0.0], 10.0, "Origin")
 
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
                threading.Thread(target=self._fault_beep_loop, daemon=True).start()
            self.logger.critical("Robot entered a Faulty State!")

    def trigger_fault_cleared(self):
        """Thread-safely handles clearing the fault state and playing the success chime."""
        if self.state.has_fault:
            self.state.has_fault = False
            EventBus.publish("fault_cleared")
            self.logger.info("Robot Fault successfully cleared.")

    def _fault_beep_loop(self):
        """Asynchronously repeats the fault warning sound every 3 seconds while in fault."""
        # If an E-Stop was pressed, wait 3 seconds for the siren sound to finish once before beeping
        if self._estop_active:
            for _ in range(6):
                if not self.state.has_fault or not self.state.is_connected:
                    break
                time.sleep(0.5)
            self._estop_active = False # Clear E-Stop flag so normal fault beep takes over

        while self.state.is_connected and self.state.has_fault:
            EventBus.publish("fault")
            # Sleep in 0.5s increments to respond instantly when faults are cleared
            for _ in range(6):
                if not self.state.has_fault or not self.state.is_connected:
                    break
                time.sleep(0.5)
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
        """Autonomous thread continuously fetching telemetry data (20Hz Polling, faster polling yields smoother rendering)."""
        while self._is_polling:
            try:
                if self.state.is_connected:
                    self.refresh_state_from_robot()
            except Exception as e:
                self.logger.debug(f"Hardware polling missed a cycle: {e}")
            time.sleep(0.05) 

    def refresh_state_from_robot(self):
        """Fetches telemetry data and profiles network latency."""
        if not self.state.is_connected or not self.base_cyclic: 
            return False

        try:
            # Set a strict 35ms RPC timeout options block.
            # Running at 20Hz leaves a tight 50ms total cycle time.
            # Limiting to 35ms ensures we never overflow the 50ms loop budget if a packet drops!
            options = RouterClientSendOptions()
            options.timeout_ms = 35
            feedback = self.base_cyclic.RefreshFeedback(options=options)
            self.missed_feedback_count = 0 
        except Exception as e:
            self.missed_feedback_count += 1
            if self.missed_feedback_count > 60: # Support up to 3 seconds of transient UDP jitter (60 cycles @ 20Hz)
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
            
            self.notify_observers()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Data Parsing Error: {e}")
            return False

    def execute_action_pose(self, target_pos_deg, duration_s, action_name="Move"):
        """Executes deployed action."""
        pager = threading.Event()

        if not self.state.is_connected or self.state.has_fault:
            self.logger.warning(f"Aborted action execution: Robot offline or in fault state.")
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
            min_safe_duration = calculate_min_safe_duration(target_pos_deg, current_deg)
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
            pager.set()
            self._active_movement_pager = None
            
        return pager


    def execute_waypoint_list(self, waypoint_list):
        """Executes deployed WaypointList."""
        pager = threading.Event()

        if not self.state.is_connected or self.state.has_fault:
            pager.set()
            return pager

        self._active_movement_pager = pager

        try:
            self.logger.info(f"WaypointList ({len(waypoint_list.waypoints)} Points) sent to robot.")
            self.base.ExecuteWaypointTrajectory(waypoint_list)
        except Exception as e:
            self.logger.error(f"Exception during API WaypointList call: {e}")
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
                EventBus.publish("estop_activated")
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

