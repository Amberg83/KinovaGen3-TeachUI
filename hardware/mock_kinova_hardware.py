import time
import math
import logging
import threading
import copy
from .robot_state import RobotState
from utils.event_bus import EventBus
from utils.duration_calculator import calculate_min_trajectory_duration

class MockKinovaHardware:
    """
    Simulated/Mock hardware driver for the Kinova Gen3 robot.
    Emulates physical connections, state polling (20Hz), joint/gripper actions, 
    and fault modes to support 100% offline development, testing, and display.
    Fully implements 100% API parity with the physical KinovaHardware.
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
        self._is_action_paused = False
        
        # Parity with physical robot
        self.default_pose = [0.0, 50.0, 264.0, 0.0, 58.0, 90.0]
        self._last_action_success = True
        
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
        self._is_action_paused = False
        return True

    def move_to_default(self):
        """Moves simulated robot back to its home default pose."""
        speed = calculate_min_trajectory_duration(self.state.joint_angles_deg, self.default_pose)
        return self.execute_action_pose(self.default_pose, speed * 2.0, "Origin")

    def apply_emergency_stop(self):
        if self.state.is_connected:
            self.logger.critical("[Mock] EMERGENCY STOP APPLIED!")
            self._estop_active = True
            self.state.has_fault = True
            # Abort any current movement
            self.stop()
            EventBus.publish("estop_activated")
            self._trigger_fault_sequence()

    def clear_faults(self):
        if self.state.is_connected:
            self.logger.info("[Mock] Clear Faults command dispatched.")
            self._estop_active = False
            self.trigger_fault_cleared()

    def trigger_fault_detected(self):
        """Thread-safely handles detecting the fault state and starting the beep loop."""
        if not self.state.has_fault:
            self.state.has_fault = True
            self._trigger_fault_sequence()
            self.logger.critical("[Mock] Robot entered a Faulty State!")

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

    def notify_observers(self):
        """Notifies GUI about telemetry update."""
        self._publish_state()

    def stop(self):
        """Sends a gentle deceleration command to stop the current movement."""
        if self.state.is_connected:
            self.logger.info("[Mock] Gentle Stop command executed.")
            # Gentle stop sets the pager to None or clears the active pager
            # and lets the active interpolation thread decelerate or exit.
            self._active_movement_pager = None

    def toggle_pause_action(self):
        """Toggles a Pause to later resume the same action"""
        if self.state.is_connected:
            if self._is_action_paused:
                self._is_action_paused = False
                self.logger.info("[Mock] Action resumed.")
            else:
                self._is_action_paused = True
                self.logger.info("[Mock] Action paused.")

    def validate_waypoint_list(self, waypoint_list):
        """Validates a WaypointList against the robot's kinematic and safety limits."""
        if not self.state.is_connected:
            return False, "Robot disconnected."
        return True, "Validation successful."

    def execute_action_pose(self, target_pos_deg, duration_s, action_name="Move"):
        """Executes a single pose movement using high-fidelity Quintic Smoothstep representation."""
        pager = threading.Event()
        self._last_action_success = True
        if not self.state.is_connected or self.state.has_fault:
            self.logger.warning("[Mock] Aborted action execution: Robot offline or in fault.")
            self._last_action_success = False
            pager.set()
            return pager
            
        self._active_movement_pager = pager
        self._is_action_paused = False
        self.logger.info(f"[Mock] Action '{action_name}': Starting quintic smoothstep to {target_pos_deg} over {duration_s:.2f}s...")
        
        threading.Thread(
            target=self._run_action_trajectory,
            args=(list(self.state.joint_angles_deg), target_pos_deg, float(duration_s), pager),
            daemon=True
        ).start()
        
        return pager

    def execute_waypoint_list(self, waypoint_list):
        """Executes a waypoint list trajectory using continuous Cubic Hermite Splines with velocity blending."""
        pager = threading.Event()
        self._last_action_success = True
        if not self.state.is_connected or self.state.has_fault:
            self.logger.warning("[Mock] Aborted waypoint list execution: Robot offline or in fault.")
            self._last_action_success = False
            pager.set()
            return pager

        self._active_movement_pager = pager
        self._is_action_paused = False
        
        # Pre-calculate unwrapped targets P and segment durations D
        start_angles = list(self.state.joint_angles_deg)
        P = [start_angles]
        D = []
        for wp in waypoint_list.waypoints:
            target_angles = list(wp.angular_waypoint.angles)
            duration = max(float(wp.angular_waypoint.duration), 0.05) # Prevent division by zero
            D.append(duration)
            
            next_p = []
            for start, target in zip(P[-1], target_angles):
                diff = target - start
                diff = (diff + 180.0) % 360.0 - 180.0
                next_p.append(start + diff)
            P.append(next_p)
            
        # Calculate continuous blending velocities V using limit-clamped finite difference
        N = len(D)
        V = [[0.0] * self.state.dof for _ in range(N + 1)] # Boundary velocities: V[0] and V[N] are [0.0]*dof
        
        for k in range(1, N):
            T_prev = D[k-1]
            T_next = D[k]
            p_prev = P[k-1]
            p_curr = P[k]
            p_next = P[k+1]
            
            for j in range(self.state.dof):
                delta_prev = (p_curr[j] - p_prev[j]) / T_prev
                delta_next = (p_next[j] - p_curr[j]) / T_next
                
                # Check for direction reversal (monotonicity preservation)
                if delta_prev * delta_next <= 0.0:
                    V[k][j] = 0.0
                else:
                    # Weighted finite difference
                    V[k][j] = (delta_prev * T_next + delta_next * T_prev) / (T_prev + T_next)
                    
        self.logger.info(f"[Mock] Spline trajectory: Starting Hermite Spline interpolation for {N} waypoints...")
        
        threading.Thread(
            target=self._run_spline_trajectory,
            args=(P, D, V, pager),
            daemon=True
        ).start()
        
        return pager

    def _run_action_trajectory(self, start_angles, target_angles, duration, pager):
        """
        Executes a smooth action pose trajectory using a Quintic Smoothstep function.
        Yields continuous position, continuous velocity, and zero boundaries.
        """
        dt = 0.05  # 20Hz update interval (50ms)
        steps = int(duration / dt)
        if steps <= 0:
            steps = 1
            
        # Pre-compute the unwrapped target angles to guarantee shortest-path rotation
        unwrapped_targets = []
        for start, target in zip(start_angles, target_angles):
            diff = target - start
            diff = (diff + 180.0) % 360.0 - 180.0
            unwrapped_targets.append(start + diff)
            
        self.state.joint_velocities = [0.0] * self.state.dof
        step = 1
        
        while step <= steps:
            if not self.state.is_connected or self.state.has_fault:
                self._last_action_success = False
                break
                
            if self._is_action_paused:
                self.state.joint_velocities = [0.0] * self.state.dof
                self._publish_state()
                time.sleep(dt)
                continue
                
            if not self._active_movement_pager or self._active_movement_pager != pager:
                self._last_action_success = False
                break
                
            t = step * dt
            tau = step / steps
            if tau > 1.0:
                tau = 1.0
                
            # Quintic smoothstep polynomial: S(tau) = 10*tau^3 - 15*tau^4 + 6*tau^5
            # Derivative: dS/dtau = 30*tau^2 - 60*tau^3 + 30*tau^4
            s_tau = 10 * (tau ** 3) - 15 * (tau ** 4) + 6 * (tau ** 5)
            ds_dtau = 30 * (tau ** 2) - 60 * (tau ** 3) + 30 * (tau ** 4)
            
            new_angles = []
            new_velocities = []
            for start, unwrapped_target in zip(start_angles, unwrapped_targets):
                angle = start + (unwrapped_target - start) * s_tau
                new_angles.append(angle)
                
                # velocity: dtheta / dt = (unwrapped_target - start) * dS/dtau * (1 / duration)
                velocity = (unwrapped_target - start) * ds_dtau / duration
                new_velocities.append(velocity)
                
            self.state.joint_angles_deg = new_angles
            self.state.joint_velocities = new_velocities
            
            # Simulate corresponding small TCP drift based on joints
            self.state.tcp_position[0] = 0.35 + 0.1 * math.sin(s_tau * math.pi)
            self.state.tcp_position[1] = 0.0 + 0.1 * math.cos(s_tau * math.pi)
            self.state.tcp_position[2] = 0.45 + 0.05 * math.sin(s_tau * math.pi * 2)
            
            self._publish_state()
            step += 1
            time.sleep(dt)
            
        if self._last_action_success and self.state.is_connected and not self.state.has_fault:
            self.state.joint_angles_deg = unwrapped_targets
            self.state.joint_velocities = [0.0] * self.state.dof
            self._publish_state()
            self.logger.info("[Mock] Action pose completed successfully.")
        else:
            self.state.joint_velocities = [0.0] * self.state.dof
            self._publish_state()
            self.logger.warning("[Mock] Action pose interrupted or failed.")
            
        self._active_movement_pager = None
        pager.set()

    def _run_spline_trajectory(self, P, D, V, pager):
        """
        Unified high-fidelity spline trajectory generator.
        Supports continuous multi-segment Hermite Spline blending, pausing, stopping,
        and generates realistic joint velocities.
        """
        N = len(D)
        current_segment = 0
        segment_time = 0.0
        dt = 0.05  # 20Hz update interval (50ms)
        
        self.state.joint_velocities = [0.0] * self.state.dof
        
        while current_segment < N:
            if not self.state.is_connected or self.state.has_fault:
                self._last_action_success = False
                break
                
            if self._is_action_paused:
                self.state.joint_velocities = [0.0] * self.state.dof
                self._publish_state()
                time.sleep(dt)
                continue
                
            if not self._active_movement_pager or self._active_movement_pager != pager:
                self._last_action_success = False
                break
                
            segment_time += dt
            T_k = D[current_segment]
            
            if segment_time >= T_k:
                segment_time_clamped = T_k
            else:
                segment_time_clamped = segment_time
                
            tau = segment_time_clamped / T_k
            
            # Evaluate Cubic Hermite Spline basis functions
            h00 = 2 * (tau ** 3) - 3 * (tau ** 2) + 1
            h10 = (tau ** 3) - 2 * (tau ** 2) + tau
            h01 = -2 * (tau ** 3) + 3 * (tau ** 2)
            h11 = (tau ** 3) - (tau ** 2)
            
            # Evaluate derivatives with respect to tau
            dh00 = 6 * (tau ** 2) - 6 * tau
            dh10 = 3 * (tau ** 2) - 4 * tau + 1
            dh01 = -6 * (tau ** 2) + 6 * tau
            dh11 = 3 * (tau ** 2) - 2 * tau
            
            p_start = P[current_segment]
            p_end = P[current_segment + 1]
            v_start = V[current_segment]
            v_end = V[current_segment + 1]
            
            new_angles = []
            new_velocities = []
            
            for j in range(self.state.dof):
                theta_start = p_start[j]
                theta_end = p_end[j]
                vel_start = v_start[j]
                vel_end = v_end[j]
                
                # Joint position calculation
                theta = (h00 * theta_start + 
                         h10 * T_k * vel_start + 
                         h01 * theta_end + 
                         h11 * T_k * vel_end)
                new_angles.append(theta)
                
                # Joint velocity calculation (dh/dt = dh/dtau * 1/T_k)
                omega = (dh00 * theta_start + 
                         dh10 * T_k * vel_start + 
                         dh01 * theta_end + 
                         dh11 * T_k * vel_end) / T_k
                new_velocities.append(omega)
                
            self.state.joint_angles_deg = new_angles
            self.state.joint_velocities = new_velocities
            
            # Simulate corresponding small TCP drift based on joints
            total_progress = (current_segment + tau) / N
            self.state.tcp_position[0] = 0.35 + 0.1 * math.sin(total_progress * math.pi)
            self.state.tcp_position[1] = 0.0 + 0.15 * math.cos(total_progress * math.pi)
            self.state.tcp_position[2] = 0.45 + 0.08 * math.sin(total_progress * 2 * math.pi)
            
            self._publish_state()
            
            if segment_time >= T_k:
                current_segment += 1
                segment_time = 0.0
                
            time.sleep(dt)
            
        if self._last_action_success and self.state.is_connected and not self.state.has_fault:
            self.state.joint_angles_deg = P[-1]
            self.state.joint_velocities = [0.0] * self.state.dof
            self._publish_state()
            self.logger.info("[Mock] Spline trajectory movement completed successfully.")
        else:
            self.state.joint_velocities = [0.0] * self.state.dof
            self._publish_state()
            self.logger.warning("[Mock] Spline trajectory movement interrupted or failed.")
            
        self._active_movement_pager = None
        pager.set()

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
