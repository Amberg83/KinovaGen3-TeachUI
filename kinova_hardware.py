import math
import threading
import time
import logging
from kortex_api.autogen.client_stubs.BaseClientRpc import BaseClient
from kortex_api.autogen.client_stubs.BaseCyclicClientRpc import BaseCyclicClient
from kortex_api.autogen.messages import Base_pb2, Session_pb2
from kortex_api.RouterClient import RouterClient
from kortex_api.SessionManager import SessionManager
from kortex_api.TCPTransport import TCPTransport
from kortex_api.UDPTransport import UDPTransport

class KinovaHardware:
    def __init__(self, ip="10.163.65.187", username="admin", password="admin"):
        self.logger = logging.getLogger("Hardware")
        self.ip = ip
        self.username = username
        self.password = password
        self.is_connected = False
        self.base = None
        self.base_cyclic = None
        self._transports = []
        self._sessions = []

    def connect(self):
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
            session_info.connection_inactivity_timeout = 2000

            session_tcp = SessionManager(router_tcp)
            session_tcp.CreateSession(session_info)
            session_udp = SessionManager(router_udp)
            session_udp.CreateSession(session_info)
            
            self._sessions.extend([session_tcp, session_udp])

            self.base = BaseClient(router_tcp)
            self.base_cyclic = BaseCyclicClient(router_udp)
            
            self.is_connected = True
            return True, f"Successfully connected to {self.ip}"
        except Exception as e:
            self.is_connected = False
            return False, str(e)

    def disconnect(self):
        self.is_connected = False
        for session in self._sessions:
            try: session.CloseSession()
            except: pass
        for transport in self._transports:
            try: transport.disconnect()
            except: pass
        self._sessions.clear()
        self._transports.clear()

    def get_robot_state(self):
        if not self.is_connected or not self.base_cyclic: return None
        try:
            feedback = self.base_cyclic.RefreshFeedback()
            dof = len(feedback.actuators)
            angles = [round(a.position, 2) for a in feedback.actuators]
            has_fault = (feedback.base.fault_bank_a != 0) or (feedback.base.fault_bank_b != 0)
            return {"angles": angles, "dof": dof, "fault": has_fault}
        except Exception:
            self.is_connected = False
            return None

    def execute_pose(self, target_pos_deg, speed_deg_per_sec, action_name="Move"):
        """Executes a joint trajectory with dynamic duration to protect hardware limits."""
        if not self.is_connected or not self.base:
            self.logger.warning(f"Cannot execute '{action_name}': Robot is not connected.")
            return

        # 1. Reset
        try:
            self.base.ClearFaults()
            time.sleep(0.5) # Crucial: Allow mechanical brakes to release
        except Exception as e: 
            self.logger.error(f"Failed to clear faults before execution: {e}")

        # 2. Calculate Distance
        feedback = self.get_robot_state()
        max_delta = 0.0
        if feedback:
            for i, target in enumerate(target_pos_deg):
                if i < len(feedback["angles"]):
                    delta = abs(target - feedback["angles"][i])
                    if delta > 180: delta = 360 - delta # Shortest path
                    max_delta = max(max_delta, delta)
        else:
            self.logger.warning("Could not retrieve current robot state. Delta calculation may be inaccurate.")
                    
        # 3. Dynamic Time Calculation (Prevents Code 1 Overcurrent)
        safe_speed = max(1.0, float(speed_deg_per_sec))
        base_time = max_delta / safe_speed
        dynamic_buffer = (safe_speed * 0.05) 
        fixed_buffer = 0.5
        calculated_duration = max(2.0, base_time + dynamic_buffer + fixed_buffer) 

        # 4. Build Action
        action = Base_pb2.Action()
        action.name = action_name

        for i, angle in enumerate(target_pos_deg):
            joint_angle = action.reach_joint_angles.joint_angles.joint_angles.add()
            joint_angle.joint_identifier = i
            joint_angle.value = float(angle)

        # 5. Set Constraint (Type 1 = DURATION)
        try:
            action.reach_joint_angles.constraint.type = Base_pb2.JOINT_CONSTRAINT_DURATION
        except AttributeError:
            action.reach_joint_angles.constraint.type = 1 
            
        action.reach_joint_angles.constraint.value = float(calculated_duration)

        # 6. Setup Notification Callback (Mit Auto-Unsubscribe)
        handle_container = [] # Erlaubt dem Callback den Zugriff auf das Handle

        def unsubscribe_safe():
            if handle_container:
                try:
                    self.base.Unsubscribe(handle_container[0])
                except Exception:
                    pass

        def notification_callback(notification):
            if notification.action_event == Base_pb2.ACTION_ABORT:
                reason = notification.abort_details
                self.logger.error(f"ACTION ABORTED for '{action_name}'. Reason Code: {reason} (1=Overcurrent, 3=Joint Limits).")
                unsubscribe_safe() # Abo beenden
            elif notification.action_event == Base_pb2.ACTION_END:
                self.logger.info(f"Target successfully reached for action: '{action_name}'.")
                unsubscribe_safe() # Abo beenden

        handle = self.base.OnNotificationActionTopic(notification_callback, Base_pb2.NotificationOptions())
        handle_container.append(handle)

        # 7. Execute
        try:
            self.logger.info(f"Dispatching '{action_name}' | Speed: {safe_speed}°/s | Max Delta: {max_delta:.1f}° | Safe Duration: {calculated_duration:.2f}s")
            self.base.ExecuteAction(action)
        except Exception as e:
            self.logger.exception(f"API Error while dispatching action '{action_name}': {e}")
            unsubscribe_safe()

    def stop(self):
        if self.is_connected and self.base:
            try:
                self.base.Stop()
                self.logger.info("Normal Stop command executed.")
            except Exception as e:
                self.logger.error(f"API Error during normal Stop: {e}")

    def apply_emergency_stop(self):
        if self.is_connected and self.base:
            try:
                self.base.ApplyEmergencyStop()
            except Exception as e:
                self.logger.error(f"API Error during E-Stop: {e}")

    def clear_faults(self):
        if self.is_connected and self.base:
            self.base.ClearFaults()