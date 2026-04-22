import math
import time
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
    """
    Handles all direct communication with the Kinova Gen3 Robot via the Kortex API.
    Acts as the 'Subject' in the Observer pattern, notifying listeners of state changes.
    """
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

    def register_observer(self, callback):
        """Registers a callback function to be notified upon state changes."""
        self._observers.append(callback)

    def notify_observers(self):
        """Notifies all registered observers by passing the current RobotState."""
        for callback in self._observers:
            callback(self.state)

    def connect(self):
        """Establishes TCP and UDP connections and creates API sessions."""
        self.logger.info(f"Attempting connection to {self.ip} as '{self.username}'...")
        self.disconnect()
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
            
            # Fetch initial state to log DOF
            self.refresh_state_from_robot()
            self.logger.info(f"Successfully connected! Hardware detected as {self.state.dof}-DOF arm.")
            return True, f"Successfully connected to {self.ip}"
            
        except Exception as e:
            self.state.is_connected = False
            self.notify_observers()
            self.logger.error(f"Connection failed: {str(e)}")
            return False, str(e)

    def disconnect(self):
        """Closes all API sessions and transports securely."""
        if self.state.is_connected:
            self.logger.info("Disconnecting from robot...")
            
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

    def refresh_state_from_robot(self):
        """Fetches high-frequency telemetry data via UDP and updates the RobotState."""
        if not self.state.is_connected or not self.base_cyclic: 
            return False

        try:
            feedback = self.base_cyclic.RefreshFeedback()
            self.missed_feedback_count = 0 
        except Exception as e:
            self.missed_feedback_count += 1
            if self.missed_feedback_count > 10:
                self.logger.error(f"Connection lost: Exceeded UDP timeout limit. Last error: {e}")
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
                getattr(feedback.base, 'tool_pose_x', 0.0),
                getattr(feedback.base, 'tool_pose_y', 0.0),
                getattr(feedback.base, 'tool_pose_z', 0.0)
            ]
            self.state.tcp_orientation = [
                getattr(feedback.base, 'tool_pose_theta_x', 0.0),
                getattr(feedback.base, 'tool_pose_theta_y', 0.0),
                getattr(feedback.base, 'tool_pose_theta_z', 0.0)
            ]
            
            self.state.joint_angles_deg = [round(getattr(a, 'position', 0.0), 2) for a in feedback.actuators]
            self.state.joint_velocities = [round(getattr(a, 'velocity', 0.0), 2) for a in feedback.actuators]
            self.state.joint_torques =    [round(getattr(a, 'torque', 0.0), 2) for a in feedback.actuators]
            self.state.joint_currents =   [round(getattr(a, 'current_motor', 0.0), 2) for a in feedback.actuators]
            self.state.joint_temperatures = [round(getattr(a, 'temperature_motor', 0.0), 1) for a in feedback.actuators]
            
            self.notify_observers()
            return True
            
        except Exception as e:
            self.logger.error(f"Data Parsing Error in telemetry: {e}")
            return False

    def execute_pose(self, target_pos_deg, speed_deg_per_sec, action_name="Move"):
        """Sends a high-level command to the robot to reach specific joint angles."""
        if not self.state.is_connected or not self.base:
            self.logger.warning(f"Cannot execute '{action_name}': Robot is not connected.")
            return

        try:
            self.base.ClearFaults()
            time.sleep(0.5)
        except Exception as e: 
            self.logger.error(f"Failed to clear faults before execution: {e}")

        max_delta = 0.0
        if self.state.joint_angles_deg:
            for i, target in enumerate(target_pos_deg):
                if i < len(self.state.joint_angles_deg):
                    delta = abs(target - self.state.joint_angles_deg[i])
                    if delta > 180: delta = 360 - delta
                    max_delta = max(max_delta, delta)
        else:
            self.logger.warning("No current state available. Delta time calculation may be inaccurate.")
                    
        safe_speed = max(1.0, float(speed_deg_per_sec))
        base_time = max_delta / safe_speed
        calculated_duration = max(2.0, base_time + (safe_speed * 0.05) + 0.5) 

        action = Base_pb2.Action()
        action.name = action_name

        for i, angle in enumerate(target_pos_deg):
            joint_angle = action.reach_joint_angles.joint_angles.joint_angles.add()
            joint_angle.joint_identifier = i
            joint_angle.value = float(angle)

        try:
            action.reach_joint_angles.constraint.type = Base_pb2.JOINT_CONSTRAINT_DURATION
        except AttributeError:
            action.reach_joint_angles.constraint.type = 1 
            
        action.reach_joint_angles.constraint.value = float(calculated_duration)

        handle_container = []

        def unsubscribe_safe():
            if handle_container:
                try: self.base.Unsubscribe(handle_container[0])
                except Exception: pass

        def notification_callback(notification):
            if notification.action_event == Base_pb2.ACTION_ABORT:
                self.logger.error(f"ACTION ABORTED for '{action_name}'. Target was: {target_pos_deg}. Reason Code: {notification.abort_details}.")
                unsubscribe_safe()
            elif notification.action_event == Base_pb2.ACTION_END:
                self.logger.info(f"Target successfully reached for action: '{action_name}'.")
                unsubscribe_safe()

        handle = self.base.OnNotificationActionTopic(notification_callback, Base_pb2.NotificationOptions())
        handle_container.append(handle)

        try:
            self.logger.info(f"Executing '{action_name}' | Speed: {safe_speed}°/s | Max Delta: {max_delta:.1f}° | Duration Limit: {calculated_duration:.2f}s")
            self.base.ExecuteAction(action)
        except Exception as e:
            self.logger.exception(f"API Error while dispatching action '{action_name}': {e}")
            unsubscribe_safe()

    def stop(self):
        """Sends a gentle stop command to the robot."""
        if self.state.is_connected and self.base:
            try:
                self.base.Stop()
                self.logger.info("Gentle Stop command successfully executed.")
            except Exception as e:
                self.logger.error(f"API Error during gentle Stop: {e}")

    def apply_emergency_stop(self):
        """Sends an immediate emergency stop (E-Stop) to the robot."""
        if self.state.is_connected and self.base:
            try: 
                self.base.ApplyEmergencyStop()
                self.logger.critical("EMERGENCY STOP APPLIED! Physical reset might be required.")
            except Exception as e: 
                self.logger.error(f"API Error during E-Stop: {e}")

    def clear_faults(self):
        """Attempts to clear minor software faults and warnings."""
        if self.state.is_connected and self.base:
            try:
                self.base.ClearFaults()
                self.logger.info("Clear Faults command dispatched.")
            except Exception as e:
                self.logger.error(f"Failed to clear faults: {e}")