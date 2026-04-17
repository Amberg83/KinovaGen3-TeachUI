import time
import os
import threading
import logging
from tkinter import filedialog

class RobotController:
    def __init__(self, root, view, model, hardware):
        self.root = root
        self.view = view
        self.model = model
        self.hardware = hardware
        
        # Eigener Logger für den Controller
        self.logger = logging.getLogger("Controller")
        
        self.stop_requested = False
        self.is_replaying = False
        self.is_dialog_open = False
        self.current_deg_cache = None 

        os.makedirs("expressions", exist_ok=True)
        
        self.view.bind_controller(self)
        self.handle_mode_change()
        self.handle_reconnect()

        self.logger.info("Application started. Ready for operation.")

        self._update_gui_joints_loop()

    def _format_angles(self, angles):
        """Hilfsfunktion: Formatiert eine Liste von Winkeln schön für das Log."""
        if not angles: return "[]"
        return f"[{', '.join(f'{a:.2f}' for a in angles)}]"

    # --- Live Update Loop ---
    def _update_gui_joints_loop(self):
        if self.is_dialog_open:
            self.root.after(100, self._update_gui_joints_loop)
            return

        try:
            state = self.hardware.get_robot_state()
            
            if state is not None:
                self.current_deg_cache = state["angles"]
                dof_str = f"{state['dof']}-DOF"
                
                if state["fault"]:
                    status_text = f"🔴 FAULT ERROR ({dof_str}) - Clear Faults! - {self.hardware.ip}"
                    color = "red"
                else:
                    status_text = f"🟢 Connected ({dof_str}) - {self.hardware.ip}"
                    color = "#00ff00"
                
                self.view.set_status(status_text, color)
                
                if self.view.mode_var.get() == "TEACH":
                    self.view.update_joint_entries(state["angles"])
            else:
                self.view.set_status(f"🔴 Disconnected ({self.hardware.ip})", "#ff3333")
                
        except Exception as e:
            self.logger.error(f"GUI Loop Error: {str(e)}")
            
        self.root.after(100, self._update_gui_joints_loop)

    # --- UI Logic Handlers ---
    def handle_mode_change(self, *args):
        mode = self.view.mode_var.get()
        if mode == "TEACH":
            self.view.toggle_entry_states("readonly")
            self.view.btn_apply_ui.config(state="disabled")
            self.logger.info("Switched to TEACH MODE: Move robot by hand. Values live update.")
        else:
            self.view.toggle_entry_states("normal")
            self.view.btn_apply_ui.config(state="normal")
            self.logger.info("Switched to EDIT MODE: Type values manually or select a waypoint to edit.")

    def handle_tree_select(self, event):
        indices = self.view.get_selected_indices()
        if indices:
            idx = indices[0]
            speed = self.model.sequence[idx]["speed"]
            self.view.update_speed_entry(speed)
            
            if self.view.mode_var.get() == "EDIT":
                pose = self.model.sequence[idx]["pos"]
                self.view.update_joint_entries(pose, force=True)
                self.logger.info(f"Loaded Waypoint {idx} (Speed {speed}°/s) into Edit Fields.")
    
    # --- Hardware Handlers ---
    def handle_reconnect(self):
        self.view.set_status("Status: Connecting...", "yellow")
        self.root.update()
        success, msg = self.hardware.connect()
        if success: 
            self.logger.info(msg)
        else: 
            self.logger.error(f"Connection failed: {msg}")

    def handle_clear_faults(self):
        if self.hardware.is_connected:
            self.hardware.clear_faults()
            self.logger.info("Clear Faults command sent to robot.")

    def handle_emergency_stop(self):
        self.stop_requested = True
        if self.hardware.is_connected:
            self.hardware.apply_emergency_stop() 
            self.logger.error("!!! EMERGENCY STOP EXECUTED !!!")

    def handle_apply_ui_poses(self):
        if not self.hardware.is_connected: return
        poses = self.view.get_entry_poses()
        if poses is None:
            self.logger.error("Invalid input. Must be numeric.")
            return
        
        self.logger.info(f"Applying manual UI pose to robot. Target angles: {self._format_angles(poses)}")
        threading.Thread(target=self.hardware.execute_pose, args=(poses, 15.0, "UI Manual Pose"), daemon=True).start()

    # --- Sequence List Handlers ---
    def handle_append_pose(self):
        poses = self.view.get_entry_poses()
        if poses is None: return
        self.model.append_pose(poses)
        new_idx = len(self.model.sequence) - 1
        self.view.update_treeview(self.model.sequence, select_index=new_idx)
        self._auto_save()
        self.logger.info(f"Appended new position at index {new_idx}: {self._format_angles(poses)}")

    def handle_overwrite_selected(self):
        indices = self.view.get_selected_indices()
        if not indices:
            self.logger.warning("Please select a waypoint to update.")
            return
        poses = self.view.get_entry_poses()
        if poses is None: return
        idx = indices[0]
        self.model.update_pose(idx, poses)
        self.view.update_treeview(self.model.sequence, select_index=idx)
        self._auto_save()
        self.logger.info(f"Overwrote waypoint at index {idx} with new pose: {self._format_angles(poses)}")

    def handle_move_up(self):
        indices = self.view.get_selected_indices()
        if not indices: return
        old_idx = indices[0]
        new_idx = self.model.move_up(old_idx)
        self.view.update_treeview(self.model.sequence, select_index=new_idx)
        self._auto_save()
        if old_idx != new_idx:
            self.logger.info(f"Moved waypoint UP from index {old_idx} to {new_idx}.")

    def handle_move_down(self):
        indices = self.view.get_selected_indices()
        if not indices: return
        old_idx = indices[0]
        new_idx = self.model.move_down(old_idx)
        self.view.update_treeview(self.model.sequence, select_index=new_idx)
        self._auto_save()
        if old_idx != new_idx:
            self.logger.info(f"Moved waypoint DOWN from index {old_idx} to {new_idx}.")

    def handle_delete_poses(self):
        indices = self.view.get_selected_indices()
        if not indices: return
        idx_list = list(indices) # Mache es zu einer sauberen Liste für das Log
        self.model.delete_poses(indices)
        self.view.update_treeview(self.model.sequence)
        self._auto_save()
        self.logger.info(f"Deleted waypoint(s) at indices: {idx_list}")

    def handle_change_speed(self):
        indices = self.view.get_selected_indices()
        if not indices: return
        speed = self.view.get_speed_input()
        if speed is None: return
        idx_list = list(indices)
        self.model.set_speed(indices, speed)
        self.view.update_treeview(self.model.sequence, select_index=indices[0])
        self._auto_save()
        self.logger.info(f"Set speed to {speed}°/s for waypoint(s) at indices: {idx_list}")

    def handle_clear_list(self):
        count = len(self.model.sequence)
        self.model.clear()
        if self.model.current_filepath:
            self.model.current_filepath = None
            self.view.set_active_file_label(None)
        self.view.update_treeview(self.model.sequence)
        self.logger.info(f"List cleared. Removed {count} waypoint(s). Auto-save context reset.")

    def handle_move_to_selected(self):
        indices = self.view.get_selected_indices()
        if not indices:
            self.logger.warning("Action aborted: Please select a waypoint first!")
            return
            
        if not self.hardware.is_connected:
            self.logger.error("Action aborted: Robot is not connected.")
            return
            
        idx = indices[0]
        step = self.model.sequence[idx]

        self.logger.info(f"Starting movement to WP {idx}. Target angles: {self._format_angles(step['pos'])}")

        def move_worker():
            self.hardware.execute_pose(step["pos"], step["speed"], f"Move to WP {idx}")
    
        threading.Thread(target=move_worker, daemon=True).start()

    def _auto_save(self):
        if self.model.current_filepath is None and len(self.model.sequence) > 0:
            timestamp = time.strftime("%Y_%m_%d-%H_%M_%S")
            new_file = os.path.join("expressions", f"{timestamp}.json")
            self.model.current_filepath = new_file
            self.view.set_active_file_label(new_file)
            self.logger.info(f"Started new auto-save session: {new_file}")

        if self.model.current_filepath is not None:
            self.model.save_to_json()

    # --- File Handlers ---
    def handle_save_json(self):
        if not self.model.sequence: 
            self.logger.warning("Nothing to save.")
            return
            
        self._auto_save()
        self.logger.info(f"Manually saved sequence ({len(self.model.sequence)} waypoints) to {self.model.current_filepath}")

    def handle_load_json(self):
        self.is_dialog_open = True 
        try:
            path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
            if path:
                self.model.load_from_json(path)
                self.view.update_treeview(self.model.sequence)
                self.view.set_active_file_label(path) 
                self.logger.info(f"JSON loaded successfully. {len(self.model.sequence)} waypoints imported. Auto-saving to this file now.")
        except Exception as e:
            self.logger.error(f"Error loading JSON: {str(e)}")
        finally:
            self.is_dialog_open = False 

    # --- Replay Thread ---
    def handle_start_replay(self):
        if not self.model.sequence or not self.hardware.is_connected: return
        
        if self.is_replaying:
            self.logger.warning("A replay is already running!")
            return
        
        self.view.mode_var.set("TEACH") 
        self.stop_requested = False
        self.is_replaying = True
        self.logger.info(f"Starting Sequence Replay for {len(self.model.sequence)} waypoints...")
        
        threading.Thread(target=self._replay_worker, daemon=True).start()

    def _replay_worker(self):
        try:
            for idx, step in enumerate(self.model.sequence):
                if self.stop_requested or not self.hardware.is_connected: break
                
                # Hier geben wir die Gelenkwinkel für den aktuellen Wegpunkt aus
                self.logger.info(f"Executing Replay WP {idx}. Target angles: {self._format_angles(step['pos'])}")
                
                # Sende Befehl synchron in diesem Thread ab
                self.hardware.execute_pose(step["pos"], step["speed"], f"Replay WP {idx}")
                
                # Warten, bis Ziel erreicht ist
                while not self.stop_requested and self.hardware.is_connected:
                    time.sleep(0.1)
                    current_deg = self.current_deg_cache 
                    if current_deg is None: break
                    
                    diffs = [abs(c - t) for c, t in zip(current_deg, step["pos"])]
                    if max(diffs) < 1.0: # Toleranz für Zielerreichung
                        time.sleep(0.2) # Kurze Pause zwischen den Wegpunkten
                        break

            if not self.stop_requested and self.hardware.is_connected:
                self.logger.info("Replay finished successfully.")
            elif self.stop_requested:
                self.logger.warning("Replay aborted by E-Stop.")
                
        finally:
            self.is_replaying = False