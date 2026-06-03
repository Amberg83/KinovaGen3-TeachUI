import time
import os
import threading
import logging
import json
from .replay_engine import ReplayEngine
from utils.event_bus import EventBus
from model import StudyManager
from view import theme

class RobotController:
    """Orchestrates application logic, linking View panels to Model and Hardware layers."""
    def __init__(self, root, view, model, hardware, participant_id="", is_review_mode=False):
        self.root = root
        self.view = view
        self.model = model
        self.hardware = hardware
        
        # Instantiate encapsulated study manager
        self.study_manager = StudyManager(participant_id, is_review_mode=is_review_mode)
        
        self.logger = logging.getLogger("Controller")
        self.replay_engine = ReplayEngine(self.hardware)
        self.clipboard = []

        os.makedirs("expressions", exist_ok=True)
        os.makedirs("log", exist_ok=True)
        
        # Loose Decoupled wiring: View listens to events on the EventBus.
        EventBus.subscribe("sequence_updated", self.view.on_sequence_changed)
        EventBus.subscribe("hardware_telemetry_updated", self.view.on_hardware_state_changed)
        EventBus.subscribe("play_predefined_gesture", self.handle_play_predefined_gesture)
        
        # Bind abstract intents from the View to Controller actions
        self.view.bind_commands({
            "reconnect": self.handle_reconnect,
            "clear_faults": self.handle_clear_faults,
            "set_admittance": self.handle_set_admittance,
            "capture_pose": self.handle_append_pose,
            "save_waypoint": self.handle_save_waypoint_changes,
            "preview_pose": self.handle_preview_inspector_pose,
            "preview_gripper": self.handle_preview_gripper,
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
            "apply_min_durations": self.handle_apply_min_durations,
            "move_default": self.handle_move_default,
            "add_pause": self.handle_add_pause,
            "add_gripper": self.handle_add_gripper
        })

        # Study Mode Setup
        if self.study_manager.study_mode:
            active_task = self.study_manager.get_active_task()
            
            # Display custom participant ID indicator including Review Mode flag in the view
            pid_display = f"{self.study_manager.participant_id} (REVIEW MODE)" if getattr(self.study_manager, "review_mode", False) else self.study_manager.participant_id
            
            self.view.enable_study_mode(
                pid_display, active_task, 
                self.study_manager.current_task_index + 1, self.study_manager.get_total_tasks(), 
                self.handle_task_completed
            )
            
            # If in Review Mode, load recorded gesture if a file exists, but NEVER move to default or save initial pose
            if getattr(self.study_manager, "review_mode", False):
                filepath = self.study_manager.current_task_filepath
                if filepath and os.path.exists(filepath):
                    self.logger.info(f"Review Mode: Loading recorded gesture from '{filepath}'")
                    self.model.load_from_json(filepath)
            else:
                # Automatically move to default and save initial pose on startup for normal study
                self._move_to_default_and_save_pose()
        else:
            # Expert Mode / Standard Start: load first tutorial referent with the preinserted Default position
            filepath = os.path.join("predefined_gestures", "1.json")
            if os.path.exists(filepath):
                self.logger.info(f"Expert Mode Startup: Loading first tutorial referent from '{filepath}'")
                try:
                    self.model.load_from_json(filepath)
                    default_pose = getattr(self.hardware, 'default_pose', [0.0, 50.0, 264.0, 0.0, 58.0, 90.0])
                    if len(self.model.sequence) > 0:
                        first_step = self.model.sequence[0]
                        if "pos" in first_step:
                            first_step["pos"] = list(default_pose)
                            self.model._notify_observers()
                except Exception as e:
                    self.logger.error(f"Failed to load first tutorial referent on startup: {e}")

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
        
        # Calculate predecessor position by searching backwards for the last step that actually has a position mapped to it
        predecessor_pos = None
        if idx > 0:
            for k in range(idx - 1, -1, -1):
                prev_step = self.model.sequence[k]
                if prev_step.get("type", "action") not in ["pause", "gripper"] and "pos" in prev_step:
                    predecessor_pos = prev_step["pos"]
                    break
        if predecessor_pos is None:
            # For first step (Pos 0) or if no predecessor has a pos, use Default Position!
            predecessor_pos = getattr(self.hardware, 'default_pose', [0.0, 50.0, 264.0, 0.0, 58.0, 90.0])
                
        # Find consecutive run context for angularwaypoint
        run_poses = None
        run_selected_idx = None
        if step_data.get("type", "action") == "angularwaypoint":
            # Find start and end of the consecutive run of angularwaypoint
            start_run_idx = idx
            while start_run_idx > 0 and self.model.sequence[start_run_idx - 1].get("type", "action") == "angularwaypoint":
                start_run_idx -= 1
                
            end_run_idx = idx
            while end_run_idx < len(self.model.sequence) - 1 and self.model.sequence[end_run_idx + 1].get("type", "action") == "angularwaypoint":
                end_run_idx += 1
                
            # Determine predecessor for the run by searching backwards for the last step that actually has a position mapped to it
            run_predecessor_pos = None
            if start_run_idx > 0:
                for k in range(start_run_idx - 1, -1, -1):
                    step = self.model.sequence[k]
                    if step.get("type", "action") not in ["pause", "gripper"] and "pos" in step:
                        run_predecessor_pos = step["pos"]
                        break
            if run_predecessor_pos is None:
                run_predecessor_pos = getattr(self.hardware, 'default_pose', [0.0, 50.0, 264.0, 0.0, 58.0, 90.0])
                    
            run_poses = [run_predecessor_pos] + [self.model.sequence[k]["pos"] for k in range(start_run_idx, end_run_idx + 1)]
            run_selected_idx = idx - start_run_idx
            
        self.view.load_inspector_data(step_data, idx, predecessor_pos, run_poses, run_selected_idx)

        # Publish preview override angles to Unity simulation
        # If the selected step does not have a position mapped (e.g. pause or gripper),
        # use the last step in the sequence that actually has a position mapped to it.
        preview_pos = None
        preview_gripper = None
        if "pos" in step_data and step_data.get("type", "action") not in ["pause", "gripper"]:
            preview_pos = step_data["pos"]
        else:
            # Search backwards from the selected index to find the last step with a position
            for k in range(idx - 1, -1, -1):
                prev_step = self.model.sequence[k]
                if prev_step.get("type", "action") not in ["pause", "gripper"] and "pos" in prev_step:
                    preview_pos = prev_step["pos"]
                    break
            if preview_pos is None:
                # If no previous step has a position, fall back to Default Position
                preview_pos = getattr(self.hardware, 'default_pose', [0.0, 50.0, 264.0, 0.0, 58.0, 90.0])
                
        # If the selected step is a gripper step, preview its target gripper position
        if step_data.get("type", "action") == "gripper":
            preview_gripper = step_data.get("gripper_target_pos", 0.0)
            
        EventBus.publish("set_preview_angles", preview_pos, preview_gripper)

    def handle_preview_inspector_pose(self, poses):
        if not self.hardware.state.is_connected: return
        self.logger.info("Previewing pose from Inspector...")
        
        # Clear preview angles so it follows live movement
        EventBus.publish("clear_preview_angles")
        
        # Calculate duration dynamically in medium speed based on the difference from current position:
        try:
            from utils.duration_calculator import calculate_min_trajectory_duration
            current_angles = self.hardware.state.joint_angles_deg
            duration = calculate_min_trajectory_duration(current_angles, poses, speed="medium")
            duration = round(duration, 2)
        except Exception:
            duration = 10.0
            
        def worker():
            pager = self.hardware.execute_action_pose(poses, duration, "Preview Pose")
            # Wait for movement to fully complete
            pager.wait(timeout=15.0)
            # play completion sound
            EventBus.publish("replay_finished")
            
        threading.Thread(target=worker, daemon=True).start()

    def handle_preview_gripper(self, state, duration, target_pos=None, speed_ratio=None):
        if not self.hardware.state.is_connected: return
        self.logger.info(f"Previewing gripper action: state={state}, duration={duration}, target_pos={target_pos}, speed_ratio={speed_ratio}...")
        threading.Thread(target=self.hardware.execute_gripper_action, args=(state, duration, target_pos, speed_ratio), daemon=True).start()

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
        # 1. Determine predecessor pose in the sequence to compute default duration in medium speed
        predecessor_pos = None
        selected_indices = self.view.panel_seq.get_selected_indices()
        if selected_indices:
            target_index = selected_indices[-1]
            for k in range(target_index, -1, -1):
                step = self.model.sequence[k]
                if step.get("type", "action") != "pause" and "pos" in step:
                    predecessor_pos = step["pos"]
                    break
        else:
            for k in range(len(self.model.sequence) - 1, -1, -1):
                step = self.model.sequence[k]
                if step.get("type", "action") != "pause" and "pos" in step:
                    predecessor_pos = step["pos"]
                    break
                    
        if predecessor_pos is None:
            predecessor_pos = getattr(self.hardware, 'default_pose', [0.0, 50.0, 264.0, 0.0, 58.0, 90.0])
                
        # 2. Calculate duration in medium speed
        try:
            from utils.duration_calculator import calculate_min_trajectory_duration
            min_dur = calculate_min_trajectory_duration(predecessor_pos, poses, speed="medium")
            duration_s = round(min_dur, 2)
        except Exception:
            duration_s = 5.0
            
        params = {"type": "action", "duration_s": duration_s, "max_velocities": [0.0]*6, "pause_s": 0.0}
        pose_data = {"pos": poses, **params}
        
        if selected_indices:
            # Insert right after the last highlighted row (Insert Behind)
            target_index = selected_indices[-1]
            self.model.insert_pose(pose_data, target_index)
            self.logger.info(f"Inserted captured pose right after index {target_index} with Medium speed duration {duration_s}s.")
        else:
            self.model.append_pose(pose_data)
            self.logger.info(f"Captured current live pose to new end entry with Medium speed duration {duration_s}s.")
            
        EventBus.publish("waypoint_captured")
        self._auto_save()

    def handle_save_waypoint_changes(self, idx_or_indices, params, poses):
        if isinstance(idx_or_indices, list):
            # Bulk update type and duration on selected rows
            target_type = params.get("type")
            self.model.bulk_update_waypoint_changes(idx_or_indices, params["duration_s"], target_type)
            self._auto_save()
            self.logger.info(f"Bulk-updated details of {len(idx_or_indices)} selected waypoints.")
        else:
            idx = idx_or_indices
            if poses is not None:
                params["pos"] = poses
            elif "pos" in self.model.sequence[idx]:
                params["pos"] = self.model.sequence[idx]["pos"] 
                
            self.model.update_pose(idx, params)
            self._auto_save()
            self.logger.info(f"Overwrote WP #{idx} with data from Inspector.")
            
        EventBus.publish("waypoint_saved")

    def handle_apply_min_durations(self, indices, speed="fast"):
        """Calculates and transactionally applies the physical minimum safe duration (scaled by speed multiplier) to each highlighted waypoint index."""
        if not indices:
            return
            
        from utils.duration_calculator import calculate_min_trajectory_duration, calculate_waypoint_durations
        
        # 1. Identify all consecutive runs of 'angularwaypoint' in the entire sequence
        runs = []
        in_run = False
        start_idx = None
        for i, step in enumerate(self.model.sequence):
            if step.get("type", "action") == "angularwaypoint":
                if not in_run:
                    in_run = True
                    start_idx = i
            else:
                if in_run:
                    runs.append((start_idx, i - 1))
                    in_run = False
        if in_run:
            runs.append((start_idx, len(self.model.sequence) - 1))
            
        # 2. For each run, compute predecessor pose and all safe segment durations
        waypoint_durations_map = {}
        for r_start, r_end in runs:
            # Determine the predecessor pose for this run
            predecessor_pos = None
            for k in range(r_start - 1, -1, -1):
                step = self.model.sequence[k]
                if step.get("type", "action") not in ["pause", "gripper"] and "pos" in step:
                    predecessor_pos = step["pos"]
                    break
            if predecessor_pos is None:
                predecessor_pos = getattr(self.hardware, 'default_pose', [0.0, 50.0, 264.0, 0.0, 58.0, 90.0])
                    
            run_waypoints = [predecessor_pos] + [self.model.sequence[k]["pos"] for k in range(r_start, r_end + 1)]
            segment_durations = calculate_waypoint_durations(run_waypoints, speed=speed)
            
            for k in range(r_start, r_end + 1):
                seg_idx = k - r_start
                if seg_idx < len(segment_durations):
                    waypoint_durations_map[k] = segment_durations[seg_idx]

        # 3. Apply the limits to the requested indices
        index_to_dur = {}
        for idx in indices:
            if idx < 0 or idx >= len(self.model.sequence):
                continue
                
            step_data = self.model.sequence[idx]
            step_type = step_data.get("type", "action")
            
            if step_type in ["pause", "gripper"]:
                continue # Skip pause and gripper steps
                
            if step_type == "action":
                # Compute predecessor pos for this single action step
                predecessor_pos = None
                for k in range(idx - 1, -1, -1):
                    step = self.model.sequence[k]
                    if step.get("type", "action") not in ["pause", "gripper"] and "pos" in step:
                        predecessor_pos = step["pos"]
                        break
                if predecessor_pos is None:
                    predecessor_pos = getattr(self.hardware, 'default_pose', [0.0, 50.0, 264.0, 0.0, 58.0, 90.0])
                
                target_pos = step_data.get("pos", [0.0] * 6)
                min_dur = calculate_min_trajectory_duration(predecessor_pos, target_pos, speed=speed)
                index_to_dur[idx] = round(min_dur, 2)
                
            elif step_type == "angularwaypoint":
                if idx in waypoint_durations_map:
                    index_to_dur[idx] = round(waypoint_durations_map[idx], 2)
                    
        if index_to_dur:
            self.model.bulk_update_durations_custom(index_to_dur)
            self._auto_save()
            self.logger.info(f"Applied physical max speed limits at speed '{speed}' to {len(index_to_dur)} waypoint(s).")
            # Select first index to refresh form entries
            self.handle_tree_select(indices[0])

    def _auto_save(self):
        """Explicitly called by the Controller only after actual data mutations."""
        # Block autosaving in study review mode
        if getattr(self.study_manager, "review_mode", False):
            return
            
        # If in study mode, save directly to the participant's persistent task file
        if self.study_manager.study_mode:
            filepath = self.study_manager.current_task_filepath
            if filepath:
                self.model.save_to_json(filepath)
            return

        if self.model.current_filepath is None and len(self.model.sequence) > 0:
            timestamp = str(int(time.time()))
            new_file = os.path.join("expressions", f"{timestamp}.json")
            self.model.current_filepath = new_file
            self.logger.info(f"Initiated new auto-save context: {new_file}")

        if self.model.current_filepath is not None:
            self.model.save_to_json()

    def handle_save_json(self):
        if getattr(self.study_manager, "review_mode", False):
            self.logger.warning("Saving is disabled in Study Review Mode.")
            return
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
        EventBus.publish("clear_preview_angles")
        self.replay_engine.stop()
        self.hardware.stop()
        if getattr(self.hardware, '_is_action_paused', False):
            self.hardware._is_action_paused = False
            self.view.panel_seq.btn_pause_media.config(fg="white")

    def handle_start_replay(self):
        if not self.model.sequence or not self.hardware.state.is_connected: return
        self.logger.info("Starting full sequence replay...")
        EventBus.publish("clear_preview_angles")
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
            EventBus.publish("clear_preview_angles")
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
            
            # If in Review Mode, load recorded gesture if a file exists, but NEVER move to default or save initial pose
            if getattr(self.study_manager, "review_mode", False):
                filepath = self.study_manager.current_task_filepath
                if filepath and os.path.exists(filepath):
                    self.logger.info(f"Review Mode: Loading recorded gesture from '{filepath}'")
                    self.model.load_from_json(filepath)
            else:
                # Automatically move to default and save initial pose for the new task
                self._move_to_default_and_save_pose()
        else:
            # Entire study sequence is completed
            if getattr(self.study_manager, "review_mode", False):
                self.view.show_study_completed()
                # Customize the text for review mode
                self.view.lbl_task_name.configure(text="Review of study referents completed successfully!", text_color=theme.ACCENT_GREEN)
                self.view.lbl_task_desc.configure(text="No changes were saved, as the system is in Review Mode.\nYou can close the application now.")
            else:
                self.view.show_study_completed()
            self.model.clear()
            self.logger.info("Participant study cycle fully completed! Results archived.")

    def handle_move_default(self):
        if not self.hardware.state.is_connected:
            self.logger.warning("Cannot move to default position: Robot disconnected.")
            return
        self.logger.info("Moving robot to default position...")
        threading.Thread(target=self.hardware.move_to_default, daemon=True).start()

    def _move_to_default_and_save_pose(self):
        """Asynchronously moves the robot to the default position, waits for it, and appends/saves the pose."""
        def worker():
            if not self.hardware.state.is_connected:
                # Wait up to 5 seconds for connection if we are at startup
                for _ in range(50):
                    if self.hardware.state.is_connected:
                        break
                    time.sleep(0.1)
            
            if not self.hardware.state.is_connected:
                self.logger.error("Cannot move to default position: Robot not connected.")
                return
                
            self.logger.info("Moving to default position...")
            completion_event = self.hardware.move_to_default()
            
            # Wait for default positioning completion (up to 15s)
            if not completion_event.wait(timeout=15.0):
                self.logger.warning("Default positioning movement timed out before appending pose.")
            
            # Wait another short moment to ensure telemetry is updated/settled
            time.sleep(0.5)
            
            # Save the exact starting default pose specified in the hardware layer instead of capturing live angles
            default_poses = list(self.hardware.default_pose)
                
            # Run the pose capture inside the main Tkinter thread to avoid race conditions on the model/UI
            self.root.after(0, lambda: self._capture_and_save_initial_pose(default_poses))
            
        threading.Thread(target=worker, daemon=True).start()

    def _capture_and_save_initial_pose(self, poses):
        """Appends the initial default pose to the model sequence and saves it."""
        self.logger.info(f"Automatically capturing and saving initial default pose: {poses}")
        params = {"type": "action", "duration_s": 5.0, "max_velocities": [0.0]*6, "pause_s": 0.0}
        pose_data = {"pos": poses, **params}
        self.model.append_pose(pose_data)
        self._auto_save()

    def handle_play_predefined_gesture(self, filepath):
        """Loads a predefined gesture file."""
        if not os.path.exists(filepath):
            self.logger.error(f"Gesture file '{filepath}' does not exist.")
            return
            
        try:
            self.logger.info(f"Loading predefined gesture: '{filepath}'")
            self.model.load_from_json(filepath)
        except Exception as e:
            self.logger.error(f"Error loading predefined gesture: {e}")

    def handle_add_pause(self, after_idx):
        """Inserts a clean Pause step immediately after the specified index (or at the end)."""
        pause_data = {
            "type": "pause",
            "duration_s": 2.0
        }
        if after_idx is None:
            self.model.append_pose(pause_data)
        else:
            self.model.insert_pose(pause_data, after_idx)
        self.logger.info(f"Inserted Pause step after index {after_idx}.")
        self._auto_save()

    def handle_add_gripper(self, after_idx):
        """Inserts a clean Gripper step immediately after the specified index (or at the end)."""
        gripper_data = {
            "type": "gripper",
            "gripper_state": "open",       # "open", "closed", "pickup"
            "gripper_duration": "medium",  # "slow", "medium", "fast"
            "gripper_target_pos": 0.0,     # default 0% (fully open)
            "gripper_speed_ratio": 0.5,    # default medium speed
            "duration_s": 1.5              # internal mechanical wait duration
        }
        if after_idx is None:
            self.model.append_pose(gripper_data)
        else:
            self.model.insert_pose(gripper_data, after_idx)
        self.logger.info(f"Inserted Gripper step after index {after_idx}.")
        self._auto_save()
