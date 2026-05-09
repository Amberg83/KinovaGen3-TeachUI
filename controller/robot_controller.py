import time
import os
import threading
import logging
import json
from .replay_engine import ReplayEngine
from utils.event_bus import EventBus
from model import StudyManager

class RobotController:
    """Orchestrates application logic, linking View panels to Model and Hardware layers."""
    def __init__(self, root, view, model, hardware, participant_id=""):
        self.root = root
        self.view = view
        self.model = model
        self.hardware = hardware
        
        # Instantiate encapsulated study manager
        self.study_manager = StudyManager(participant_id)
        
        self.logger = logging.getLogger("Controller")
        self.replay_engine = ReplayEngine(self.hardware)
        self.clipboard = []

        os.makedirs("expressions", exist_ok=True)
        os.makedirs("log", exist_ok=True)
        
        # Loose Decoupled wiring: View listens to events on the EventBus.
        EventBus.subscribe("sequence_updated", self.view.on_sequence_changed)
        EventBus.subscribe("hardware_telemetry_updated", self.view.on_hardware_state_changed)
        
        # Bind abstract intents from the View to Controller actions
        self.view.bind_commands({
            "reconnect": self.handle_reconnect,
            "clear_faults": self.handle_clear_faults,
            "set_admittance": self.handle_set_admittance,
            "capture_pose": self.handle_append_pose,
            "save_waypoint": self.handle_save_waypoint_changes,
            "preview_pose": self.handle_preview_inspector_pose,
            "append_inspector_pose": self.handle_append_inspector_pose,
            "move_up": self.handle_move_up,
            "move_down": self.handle_move_down,
            "delete_poses": self.handle_delete_poses,
            "undo": self.handle_undo,
            "redo": self.handle_redo,
            "tree_select": self.handle_tree_select,
            "save_json": self.handle_save_json,
            "load_json": self.model.load_from_json,
            "clear_list": self.model.clear,
            "replay": self.handle_start_replay,
            "replay_selection": self.handle_start_replay_selection,
            "estop": self.handle_emergency_stop,
            "stop_media": self.handle_media_stop,
            "pause_media": self.handle_media_pause,
            "copy": self.handle_copy_poses,
            "paste": self.handle_paste_poses,
            "duplicate": self.handle_duplicate_poses,
            "move_entry": self.handle_move_entry,
            "apply_min_durations": self.handle_apply_min_durations
        })

        # Study Mode Setup
        if self.study_manager.study_mode:
            active_task = self.study_manager.get_active_task()
            self.view.enable_study_mode(
                self.study_manager.participant_id, active_task, 
                self.study_manager.current_task_index + 1, self.study_manager.get_total_tasks(), 
                self.handle_task_completed
            )

        self.logger.info("Application initialized. Dashboard active.")
        self.root.after(100, self.handle_initial_connect)

    def handle_initial_connect(self):
        threading.Thread(target=self.hardware.connect, daemon=True).start()

    def handle_reconnect(self):
        threading.Thread(target=self._reconnect_worker, daemon=True).start()

    def _reconnect_worker(self):
        self.hardware.disconnect()
        time.sleep(0.5) 
        self.hardware.connect()

    def handle_clear_faults(self):
        if self.hardware.state.is_connected:
            threading.Thread(target=self.hardware.clear_faults, daemon=True).start()

    def handle_set_admittance(self, mode):
        """Dispatches the admittance mode change to the hardware thread."""
        if self.hardware.state.is_connected:
            self.logger.info(f"Applying Admittance Mode: {mode}...")
            threading.Thread(target=self.hardware.set_admittance, args=(mode,), daemon=True).start()

    def handle_emergency_stop(self):
        self.replay_engine.stop()
        if self.hardware.state.is_connected:
            threading.Thread(target=self.hardware.apply_emergency_stop, daemon=True).start()

    def handle_tree_select(self, idx):
        """Passes model data to the view for the inspector, including the predecessor's joint positions for dynamic min safe duration calculations."""
        step_data = self.model.sequence[idx]
        
        # Calculate predecessor position
        predecessor_pos = None
        if idx > 0:
            prev_step = self.model.sequence[idx - 1]
            if prev_step.get("type", "action") != "pause" and "pos" in prev_step:
                predecessor_pos = prev_step["pos"]
        else:
            # For first step, compare with current live position if available, or default to Origin
            if self.hardware.state.is_connected and getattr(self.hardware.state, "joint_angles_deg", None):
                predecessor_pos = self.hardware.state.joint_angles_deg
            else:
                predecessor_pos = [0.0] * 6 # fallback to default/origin
                
        self.view.load_inspector_data(step_data, idx, predecessor_pos)

    def handle_preview_inspector_pose(self, poses):
        if not self.hardware.state.is_connected: return
        self.logger.info("Previewing pose from Inspector...")
        threading.Thread(target=self.hardware.execute_action_pose, args=(poses, 10.0, "Preview Pose"), daemon=True).start()

    def handle_append_inspector_pose(self, params, poses):
        """Creates a new entry at the end of the sequence using Inspector data."""
        params["pos"] = poses
        self.model.append_pose(params)
        self.logger.info("Appended manually entered pose as a new waypoint.")
        self._auto_save()

    def handle_move_up(self, idx):
        self.model.move_up(idx)
        self._auto_save()
        EventBus.publish("waypoint_moved_up")

    def handle_move_down(self, idx):
        self.model.move_down(idx)
        self._auto_save()
        EventBus.publish("waypoint_moved_down")

    def handle_copy_poses(self, indices):
        self.clipboard = self.model.copy_poses(indices)
        self.logger.info(f"Copied {len(self.clipboard)} waypoint(s) to clipboard.")

    def handle_paste_poses(self, after_index):
        if self.clipboard:
            self.model.paste_poses(self.clipboard, after_index)
            self._auto_save()

    def handle_duplicate_poses(self, indices):
        copied = self.model.copy_poses(indices)
        if copied:
            self.model.paste_poses(copied, indices[-1])
            self._auto_save()

    def handle_move_entry(self, from_idx, to_idx):
        self.model.move_pose(from_idx, to_idx)
        self._auto_save()
        EventBus.publish("waypoint_moved_entry")

    def handle_delete_poses(self, indices):
        self.model.delete_poses(indices)
        self._auto_save()
        EventBus.publish("waypoint_deleted")

    def handle_undo(self):
        if self.model.undo():
            self._auto_save()
            EventBus.publish("edit_undone")

    def handle_redo(self):
        if self.model.redo():
            self._auto_save()
            EventBus.publish("edit_redone")

    def handle_append_pose(self, poses):
        params = {"type": "action", "duration_s": 5.0, "max_velocities": [0.0]*6, "pause_s": 0.0}
        pose_data = {"pos": poses, **params}
        
        selected_indices = self.view.panel_seq.get_selected_indices()
        if selected_indices:
            # Insert right after the last highlighted row (Insert Behind)
            target_index = selected_indices[-1]
            self.model.insert_pose(pose_data, target_index)
            self.logger.info(f"Inserted captured pose right after index {target_index}.")
        else:
            self.model.append_pose(pose_data)
            self.logger.info(f"Captured current live pose to new end entry.")
            
        EventBus.publish("waypoint_captured")
        self._auto_save()

    def handle_save_waypoint_changes(self, idx_or_indices, params, poses):
        if isinstance(idx_or_indices, list):
            # Bulk duration edit on selected rows
            self.model.bulk_update_durations(idx_or_indices, params["duration_s"])
            self._auto_save()
            self.logger.info(f"Bulk-updated durations of {len(idx_or_indices)} selected waypoints.")
        else:
            idx = idx_or_indices
            if poses is not None:
                params["pos"] = poses
            else:
                params["pos"] = self.model.sequence[idx]["pos"] 
                
            self.model.update_pose(idx, params)
            self._auto_save()
            self.logger.info(f"Overwrote WP #{idx} with data from Inspector.")
            
        EventBus.publish("waypoint_saved")

    def handle_apply_min_durations(self, indices):
        """Calculates and transactionally applies the physical minimum safe duration to each highlighted waypoint index."""
        if not indices:
            return
            
        index_to_dur = {}
        for idx in indices:
            if idx < 0 or idx >= len(self.model.sequence):
                continue
                
            step_data = self.model.sequence[idx]
            if step_data.get("type", "action") == "pause":
                continue # Skip pause steps as their duration is a fixed delay
                
            # Compute predecessor pos
            predecessor_pos = None
            if idx > 0:
                prev_step = self.model.sequence[idx - 1]
                if prev_step.get("type", "action") != "pause" and "pos" in prev_step:
                    predecessor_pos = prev_step["pos"]
            else:
                if self.hardware.state.is_connected and getattr(self.hardware.state, "joint_angles_deg", None):
                    predecessor_pos = self.hardware.state.joint_angles_deg
                else:
                    predecessor_pos = [0.0] * 6
                    
            target_pos = step_data.get("pos", [0.0] * 6)
            
            # Retrieve centralized duration
            from hardware.kinova_hardware import calculate_min_safe_duration
            min_dur = calculate_min_safe_duration(target_pos, predecessor_pos)
            
            # Save mapped duration (rounded to 2 decimals)
            index_to_dur[idx] = round(min_dur, 2)
            
        if index_to_dur:
            self.model.bulk_update_durations_custom(index_to_dur)
            self._auto_save()
            self.logger.info(f"Applied physical max speed limits to {len(index_to_dur)} waypoint(s).")
            # Select first index to refresh form entries
            self.view.panel_seq.select_index(indices[0])

    def _auto_save(self):
        """Explicitly called by the Controller only after actual data mutations."""
        # If in study mode, save directly to the participant's persistent task file
        if self.study_manager.study_mode:
            filepath = self.study_manager.current_task_filepath
            if filepath:
                self.model.save_to_json(filepath)
            return

        if self.model.current_filepath is None and len(self.model.sequence) > 0:
            timestamp = time.strftime("%Y_%m_%d-%H_%M_%S")
            new_file = os.path.join("expressions", f"{timestamp}.json")
            self.model.current_filepath = new_file
            self.logger.info(f"Initiated new auto-save context: {new_file}")

        if self.model.current_filepath is not None:
            self.model.save_to_json()

    def handle_save_json(self):
        if not self.model.sequence and self.model.current_filepath is not None: return
        self.model.save_to_json()
        self.logger.info("Manual save executed successfully.")

    def handle_media_pause(self):
        if not self.hardware.state.is_connected: return False
        self.hardware.toggle_pause_action()
        return getattr(self.hardware, '_is_action_paused', False)

    def handle_media_stop(self):
        if not self.hardware.state.is_connected: return
        self.logger.info("Soft-STOP requested.")
        self.replay_engine.stop()
        self.hardware.stop()
        if getattr(self.hardware, '_is_action_paused', False):
            self.hardware._is_action_paused = False
            self.view.panel_seq.btn_pause_media.config(fg="white")

    def handle_start_replay(self):
        if not self.model.sequence or not self.hardware.state.is_connected: return
        self.logger.info("Starting full sequence replay...")
        self.replay_engine.start(self.model.sequence)

    def handle_start_replay_selection(self):
        if not self.model.sequence or not self.hardware.state.is_connected: return
        selected_indices = self.view.panel_seq.get_selected_indices()
        if not selected_indices:
            self.logger.warning("Replay selection requested, but no row is highlighted.")
            return
        
        subset = [self.model.sequence[i] for i in selected_indices if 0 <= i < len(self.model.sequence)]
        if subset:
            self.logger.info(f"Starting partial selection replay of {len(subset)} waypoint(s)...")
            self.replay_engine.start(subset)

    def handle_task_completed(self):
        """Processes task completion, delegating state transitions and backups to StudyManager."""
        if not self.study_manager.study_mode:
            return

        study_completed, next_task = self.study_manager.complete_task(self.model)
        
        # Play completion success sound
        EventBus.publish("task_completed")

        if not study_completed:
            # Clear current sequence timeline for the next task
            self.model.clear()
            self.view.update_study_task(
                next_task, 
                self.study_manager.current_task_index + 1, 
                self.study_manager.get_total_tasks()
            )
            self.logger.info(f"Transitioned to study task {self.study_manager.current_task_index + 1}/{self.study_manager.get_total_tasks()}.")
        else:
            # Entire study sequence is completed
            self.view.show_study_completed()
            self.model.clear()
            self.logger.info("Participant study cycle fully completed! Results archived.")
