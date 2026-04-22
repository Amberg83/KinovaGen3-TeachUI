import time
import os
import threading
import logging
from tkinter import filedialog
from robot_state import RobotState

class RobotController:
    """
    The orchestrator of the application. 
    Handles user inputs from the View, updates the Model, and sends commands to the Hardware.
    """
    def __init__(self, root, view, model, hardware):
        self.root = root
        self.view = view
        self.model = model
        self.hardware = hardware
        
        self.logger = logging.getLogger("Controller")
        
        self.stop_requested = False
        self.is_replaying = False
        self.is_dialog_open = False
        self.current_deg_cache = None 

        os.makedirs("expressions", exist_ok=True)
        
        self.view.bind_controller(self)
        self.handle_mode_change()

        # 1. Register Observer FIRST
        self.hardware.register_observer(self.on_robot_state_received)
        
        # 2. Start polling worker
        self._is_polling = True
        threading.Thread(target=self._hardware_polling_worker, daemon=True).start()

        self.logger.info("Application initialized. Ready for operation.")

        # 3. Schedule connection attempt after UI has loaded
        self.root.after(500, self.handle_reconnect)

    def _format_angles(self, angles):
        """Helper to format angle lists cleanly for logging."""
        if not angles: return "[]"
        return f"[{', '.join(f'{a:.2f}' for a in angles)}]"

    # --- Hardware Polling (Background) ---
    def _hardware_polling_worker(self):
        """Continuously requests telemetry data without blocking the Tkinter UI."""
        while self._is_polling:
            try:
                if self.hardware.state.is_connected:
                    self.hardware.refresh_state_from_robot()
            except Exception as e:
                self.logger.debug(f"Polling-Worker missed a cycle: {e}")
            
            time.sleep(0.05)

    # --- Observer Callback ---
    def on_robot_state_received(self, state: RobotState):
        """Triggered by Hardware. Pushes UI updates safely to the Main Thread."""
        self.root.after(0, lambda: self._update_ui_from_state(state))

    def _update_ui_from_state(self, state: RobotState):
        """Updates the visual components based on the incoming RobotState."""
        if self.is_dialog_open:
            return # Pause updates while file dialogs are open

        try:
            # ---> MVC FIX: We pass the pure state variables to the View! <---
            self.view.update_connection_status(state.is_connected, state.has_fault, state.dof, self.hardware.ip)
            
            if state.is_connected:
                self.current_deg_cache = state.joint_angles_deg
                
                if self.view.mode_var.get() == "TEACH" and state.joint_angles_deg:
                    self.view.update_joint_entries(state.joint_angles_deg)
                
        except Exception as e:
            self.logger.error(f"GUI Update Error: {str(e)}")

    # --- UI Logic Handlers ---
    def handle_mode_change(self, *args):
        """Handles switching between LIVE TEACH and MANUAL EDIT modes."""
        mode = self.view.mode_var.get()
        if mode == "TEACH":
            self.view.toggle_entry_states("readonly")
            self.view.btn_apply_ui.config(state="disabled")
            self.logger.info("Mode changed: TEACH (Live tracking of robot poses).")
        else:
            self.view.toggle_entry_states("normal")
            self.view.btn_apply_ui.config(state="normal")
            self.logger.info("Mode changed: EDIT (Manual input enabled).")

    def handle_tree_select(self, event):
        """Loads a selected waypoint from the sequence list into the input fields."""
        indices = self.view.get_selected_indices()
        if indices:
            idx = indices[0]
            speed = self.model.sequence[idx]["speed"]
            self.view.update_speed_entry(speed)
            
            if self.view.mode_var.get() == "EDIT":
                pose = self.model.sequence[idx]["pos"]
                self.view.update_joint_entries(pose, force=True)
                self.logger.debug(f"Waypoint {idx} loaded into UI edit fields.")

    # --- Hardware Handlers ---
    def handle_reconnect(self):
        """Initiates a connection attempt to the hardware."""
        self.view.update_connection_status(False, False, 0, "Connecting...")
        self.root.update()
        success, msg = self.hardware.connect()
        # Connection result will automatically be logged by hardware class

    def handle_clear_faults(self):
        """Sends a clear fault command."""
        if self.hardware.state.is_connected:
            self.hardware.clear_faults()

    def handle_emergency_stop(self):
        """Triggers E-Stop and aborts any running replays."""
        self.stop_requested = True
        if self.hardware.state.is_connected:
            self.hardware.apply_emergency_stop() 

    def handle_apply_ui_poses(self):
        """Applies manually typed angles to the robot."""
        if not self.hardware.state.is_connected: return
        poses = self.view.get_entry_poses()
        if poses is None:
            self.logger.error("Invalid input. Pose fields must contain numeric values.")
            return
        
        threading.Thread(target=self.hardware.execute_pose, args=(poses, 15.0, "UI Manual Pose"), daemon=True).start()

    # --- Sequence List Handlers ---
    def handle_append_pose(self):
        """Saves the currently visible pose into the sequence."""
        poses = self.view.get_entry_poses()
        if poses is None: return
        self.model.append_pose(poses)
        new_idx = len(self.model.sequence) - 1
        self.view.update_treeview(self.model.sequence, select_index=new_idx)
        self._auto_save()
        self.logger.info(f"Recorded new pose at WP {new_idx}: {self._format_angles(poses)}")

    def handle_overwrite_selected(self):
        """Overwrites the selected waypoint with the currently visible pose."""
        indices = self.view.get_selected_indices()
        if not indices:
            self.logger.warning("Cannot overwrite: No waypoint selected in list.")
            return
        poses = self.view.get_entry_poses()
        if poses is None: return
        idx = indices[0]
        self.model.update_pose(idx, poses)
        self.view.update_treeview(self.model.sequence, select_index=idx)
        self._auto_save()
        self.logger.info(f"Overwrote WP {idx} with new pose: {self._format_angles(poses)}")

    def handle_move_up(self):
        """Shifts a waypoint up in the execution order."""
        indices = self.view.get_selected_indices()
        if not indices: return
        idx = indices[0]
        new_idx = self.model.move_up(idx)
        self.view.update_treeview(self.model.sequence, select_index=new_idx)
        self._auto_save()

    def handle_move_down(self):
        """Shifts a waypoint down in the execution order."""
        indices = self.view.get_selected_indices()
        if not indices: return
        idx = indices[0]
        new_idx = self.model.move_down(idx)
        self.view.update_treeview(self.model.sequence, select_index=new_idx)
        self._auto_save()

    def handle_delete_poses(self):
        """Deletes selected waypoints from the sequence."""
        indices = self.view.get_selected_indices()
        if not indices: return
        self.model.delete_poses(indices)
        self.view.update_treeview(self.model.sequence)
        self._auto_save()
        self.logger.info(f"Deleted {len(indices)} waypoint(s) from sequence.")

    def handle_change_speed(self):
        """Updates the movement speed parameter of selected waypoints."""
        indices = self.view.get_selected_indices()
        if not indices: return
        speed = self.view.get_speed_input()
        if speed is None: return
        self.model.set_speed(indices, speed)
        self.view.update_treeview(self.model.sequence, select_index=indices[0])
        self._auto_save()
        self.logger.info(f"Updated speed of {len(indices)} waypoint(s) to {speed}°/s.")

    def handle_clear_list(self):
        """Wipes the entire sequence memory."""
        self.model.clear()
        if self.model.current_filepath:
            self.model.current_filepath = None
            self.view.set_active_file_label(None)
        self.view.update_treeview(self.model.sequence)
        self.logger.warning("Sequence list wiped clean. Starting fresh.")

    def handle_teach_toggle(self):
        """Initiates the custom admittance / teach-in mode."""
        unlocked_joints = self.view.get_unlocked_joints()
        gain, deadzone = self.view.get_admittance_params()
        
        if not self.hardware.state.is_connected:
            self.logger.warning("Cannot start Custom Teach Mode: Robot disconnected.")
            return

        if not unlocked_joints:
            self.logger.warning("Teach Mode abort: No joints were unlocked. Please select at least one joint checkbox.")
            return
            
        if gain is None or deadzone is None:
            self.logger.error("Teach Mode abort: Invalid Admittance parameters (Gain/Deadzone).")
            return

        self.logger.info(f"Custom Admittance Mode engaged. Unlocked indices: {unlocked_joints} | Gain: {gain} | Deadzone: {deadzone}")
        self.logger.debug(f"Initial positions at engage: {self._format_angles(self.hardware.state.joint_angles_deg)}")
        # Implement custom velocity loop here later...

    def handle_move_to_selected(self):
        """Moves the robot to the currently highlighted waypoint in the list."""
        indices = self.view.get_selected_indices()
        if not indices or not self.hardware.state.is_connected: 
            self.logger.warning("Action aborted: Please select a waypoint and ensure robot is connected.")
            return
            
        idx = indices[0]
        step = self.model.sequence[idx]
        self.logger.info(f"Previewing WP {idx} - Target angles: {self._format_angles(step['pos'])}")

        def move_worker():
            self.hardware.execute_pose(step["pos"], step["speed"], f"Preview WP {idx}")
        threading.Thread(target=move_worker, daemon=True).start()

    def _auto_save(self):
        """Automatically saves progress to a JSON file to prevent data loss."""
        if self.model.current_filepath is None and len(self.model.sequence) > 0:
            timestamp = time.strftime("%Y_%m_%d-%H_%M_%S")
            new_file = os.path.join("expressions", f"{timestamp}.json")
            self.model.current_filepath = new_file
            self.view.set_active_file_label(new_file)
            self.logger.info(f"Initiated new auto-save context: {new_file}")

        if self.model.current_filepath is not None:
            self.model.save_to_json()

    # --- File Handlers ---
    def handle_save_json(self):
        """Forces a manual save to the current JSON file."""
        if not self.model.sequence: 
            self.logger.warning("Sequence is empty. Nothing to save.")
            return
        self._auto_save()
        self.logger.info("Manual save executed successfully.")

    def handle_load_json(self):
        """Opens a file dialog to load an existing JSON sequence."""
        self.is_dialog_open = True 
        try:
            path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
            if path:
                self.model.load_from_json(path)
                self.view.update_treeview(self.model.sequence)
                self.view.set_active_file_label(path) 
        except Exception as e:
            self.logger.error(f"Error during JSON load procedure: {str(e)}")
        finally:
            self.is_dialog_open = False 

    # --- Replay Thread ---
    def handle_start_replay(self):
        """Starts iterating through the entire sequence of waypoints."""
        if not self.model.sequence or not self.hardware.state.is_connected: return
        if self.is_replaying: 
            self.logger.warning("Replay is already in progress.")
            return
        
        self.view.mode_var.set("TEACH") 
        self.stop_requested = False
        self.is_replaying = True
        self.logger.info(f"--- STARTING REPLAY ENGINE ({len(self.model.sequence)} WPs) ---")
        
        threading.Thread(target=self._replay_worker, daemon=True).start()

    def _replay_worker(self):
        """Background worker that manages the execution timing of the sequence."""
        try:
            for idx, step in enumerate(self.model.sequence):
                if self.stop_requested or not self.hardware.state.is_connected: break
                
                self.logger.info(f"Replay Engine: Executing WP {idx} -> {self._format_angles(step['pos'])}")
                self.hardware.execute_pose(step["pos"], step["speed"], f"Replay WP {idx}")
                
                # Check for completion via telemetry
                while not self.stop_requested and self.hardware.state.is_connected:
                    time.sleep(0.1)
                    current_deg = self.current_deg_cache 
                    if current_deg is None: break
                    
                    diffs = [abs(c - t) for c, t in zip(current_deg, step["pos"])]
                    if max(diffs) < 1.0: 
                        time.sleep(0.2) 
                        break

            if not self.stop_requested and self.hardware.state.is_connected:
                self.logger.info("--- REPLAY ENGINE FINISHED SUCCESSFULLY ---")
            elif self.stop_requested:
                self.logger.warning("--- REPLAY ENGINE ABORTED VIA E-STOP ---")
                
        finally:
            self.is_replaying = False