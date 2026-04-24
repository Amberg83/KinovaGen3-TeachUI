import time
import threading
import logging
from kortex_api.autogen.client_stubs.BaseClientRpc import BaseClient
from kortex_api.autogen.client_stubs.BaseCyclicClientRpc import BaseCyclicClient
from kortex_api.autogen.messages import Base_pb2, Session_pb2
from kortex_api.RouterClient import RouterClient
from kortex_api.SessionManager import SessionManager
from kortex_api.TCPTransport import TCPTransport
from kortex_api.UDPTransport import UDPTransport

from robot_state import RobotState 

class KinovaHardware:
    """Handles direct communication with the Kinova Gen3 Robot via the Kortex API."""
    def __init__(self, ip="10.163.65.187", username="admin", password="admin"):
        self.logger = logging.getLogger("Hardware")
        self.ip = ip
        self.username = username
        self.password = password
        
        self.base = None
        self.base_cyclic = None
        self._transports = []
        self._sessions = []

        self.state = RobotState()
        self.missed_feedback_count = 0
        self._observers = []

        self._global_notification_handle = None
        self._global_armstate_handle = None
        self._active_movement_pager = None
        
        self._is_polling = False
        self._polling_thread = None
        self._is_action_paused = False

    def register_observer(self, callback):
        """Registers a callback to be notified upon state changes."""
        self._observers.append(callback)

    def notify_observers(self):
        """Notifies all registered observers by passing the current RobotState."""
        for callback in self._observers:
            callback(self.state)

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
            
            self.state.is_connected = True
            self.notify_observers()
            
            self._start_internal_polling()

            time.sleep(0.5)
            self._start_global_listeners()
            
            self.logger.info(f"Connection successful! Hardware detected as a {self.state.dof}-DOF robotic arm.")
            self.move_to_default()
            return True, f"Successfully connected to {self.ip}"
            
        except Exception as e:
            self.state.is_connected = False
            self.notify_observers()
            self.logger.error(f"Connection attempt failed: {str(e)}")
            return False, str(e)

    def move_to_default(self):
        self.execute_action_pose([0.0,0.0,0.0,0.0,0.0,0.0], 10.0, "Origin")

    def disconnect(self):
        """Stops polling threads and closes all API sessions."""
        if self.state.is_connected:
            self.logger.info("Disconnecting from robot and closing network sessions...")
            
        self._stop_internal_polling()
        self._stop_global_listeners()
        
        self.state.is_connected = False
        self.notify_observers()
        
        for session in self._sessions:
            try: session.CloseSession()
            except: pass
        for transport in self._transports:
            try: transport.disconnect()
            except: pass
        self._sessions.clear()
        self._transports.clear()

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
                self.logger.critical("Robot in Faulty State!")
                self.state.has_fault = True
                
                if self._active_movement_pager:
                    self._active_movement_pager.set()
                    self._active_movement_pager = None
                    
            elif active_state == Base_pb2.ARMSTATE_IDLE:
                self.state.has_fault = False

        # --- Register Subscribers ---
        try:
            self.logger.info("Starting event subscribers (ActionEvent, ArmState)...")
            self._global_notification_handle = self.base.OnNotificationActionTopic(action_callback, Base_pb2.NotificationOptions())
            self._global_armstate_handle = self.base.OnNotificationArmStateTopic(arm_state_callback, Base_pb2.NotificationOptions())
        except Exception as e:
            self.logger.error(f"Could not start all event subscribers: {e}")

    def _stop_global_listeners(self):
        """Stops all subscribers."""
        if not self.base: return
        
        handles = [
            self._global_notification_handle,
            self._global_armstate_handle
        ]
        
        for handle in handles:
            if handle:
                try: self.base.Unsubscribe(handle)
                except Exception: pass
                
        self._global_notification_handle = None
        self._global_armstate_handle = None
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
        """Autonomous thread continuously fetching telemetry data (10Hz Polling, faster polling lags out the robot)."""
        while self._is_polling:
            try:
                if self.state.is_connected:
                    self.refresh_state_from_robot()
            except Exception as e:
                self.logger.debug(f"Hardware polling missed a cycle: {e}")
            time.sleep(0.1) 

    def refresh_state_from_robot(self):
        """Fetches telemetry data and profiles network latency."""
        if not self.state.is_connected or not self.base_cyclic: 
            return False

        try:
            feedback = self.base_cyclic.RefreshFeedback()
            self.missed_feedback_count = 0 
        except Exception as e:
            self.missed_feedback_count += 1
            if self.missed_feedback_count > 5:
                self.logger.error(f"Connection lost: Exceeded UDP timeout limit. Error: {e}")
                self.state.is_connected = False
                self.notify_observers()
            return False

        try:
            self.state.dof = len(feedback.actuators)
            self.state.fault_bank_a = getattr(feedback.base, 'fault_bank_a', 0)
            self.state.fault_bank_b = getattr(feedback.base, 'fault_bank_b', 0)
            self.state.has_fault = (self.state.fault_bank_a != 0) or (self.state.fault_bank_b != 0)
            
            self.state.control_mode = getattr(feedback.base, 'control_mode', 0)
            self.state.command_mode = getattr(feedback.base, 'command_mode', 0)
            self.state.active_state = getattr(feedback.base, 'active_state', 0)
            
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
            min_safe_duration = max(0.5, max_diff / 30.0) 
            actual_duration = max(float(duration_s), min_safe_duration)
            try: 
                action.reach_joint_angles.constraint.type = Base_pb2.JOINT_CONSTRAINT_DURATION
            except AttributeError: 
                action.reach_joint_angles.constraint.type = 1 
            action.reach_joint_angles.constraint.value = float(actual_duration)

        # Notify application about new constructed action
        self._active_movement_pager = pager
        
        try:
            self.logger.info(f"Action '{action_name}' sent to robot (Time to complete: {duration_s}s).")
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
                self.base.ApplyEmergencyStop()
                self.logger.critical("EMERGENCY STOP APPLIED! Physical robot reset might be required.")
            except Exception as e: 
                self.logger.error(f"API Error during E-Stop: {e}")

    def clear_faults(self):
        """Attempts to clear minor software faults and warnings."""
        if self.state.is_connected and self.base:
            try:
                self.base.ClearFaults()
                self.logger.info("Clear Faults command dispatched to robot controller.")
            except Exception as e:
                self.logger.error(f"Failed to clear faults: {e}")
    
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