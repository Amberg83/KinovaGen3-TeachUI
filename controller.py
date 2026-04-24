import time
import os
import threading
import logging
from tkinter import filedialog
from robot_state import RobotState
from model import SequenceModel
from kinova_hardware import KinovaHardware
from view import RobotView

class RobotController:
    """Orchestrates the application by linking the View, Model, and Hardware logic."""
    def __init__(self, root, view: RobotView, model: SequenceModel, hardware: KinovaHardware):
        self.root = root
        self.view = view
        self.model = model
        self.hardware = hardware
        
        self.logger = logging.getLogger("Controller")
        
        self.stop_requested = False
        self.is_replaying = False
        self.is_dialog_open = False

        os.makedirs("expressions", exist_ok=True)
        
        self.view.bind_controller(self)

        self.hardware.register_observer(self.on_robot_state_received)
        
        self.logger.info("Application initialized. Dashboard active.")
        self.root.after(100, self.handle_initial_connect)

    def on_robot_state_received(self, state: RobotState):
        self.root.after(0, self._update_ui_from_state, state)

    def _update_ui_from_state(self, state: RobotState):
        if self.is_dialog_open: return 
        try:
            self.view.update_connection_status(state.is_connected, state.has_fault, state.dof, self.hardware.ip)
            
            self.view.update_live_state(state)
        except Exception as e:
            pass

    def handle_tree_select(self, event):
        indices = self.view.get_selected_indices()
        if indices:
            idx = indices[0]
            step_data = self.model.sequence[idx]
            
            self.view.load_inspector_data(step_data, idx)

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

    def handle_emergency_stop(self):
        self.stop_requested = True
        if self.hardware.state.is_connected:
            threading.Thread(target=self.hardware.apply_emergency_stop, daemon=True).start()

    def handle_preview_inspector_pose(self):
        """Allows preview of pose preentered in inspector."""
        if not self.hardware.state.is_connected: return
        poses = self.view.get_inspector_poses()
        if poses is None: return
        self.logger.info("Previewing pose from Inspector...")
        threading.Thread(target=self.hardware.execute_action_pose, args=(poses, 10.0, "Preview Pose"), daemon=True).start()

    def handle_append_pose(self):
        """Adds current robot position as new entry in list."""
        poses = self.view.get_live_poses()
        if poses is None: return
        
        params = {"type": "action", "duration_s": 5.0, "max_velocities": [0.0]*6, "pause_s": 0.0}
        pose_data = {"pos": poses, **params}
        
        self.model.append_pose(pose_data)
        new_idx = len(self.model.sequence) - 1
        self.view.update_treeview(self.model.sequence, select_index=new_idx)
        self._auto_save()
        self.logger.info(f"Captured current live pose to new entry #{new_idx}")

    def handle_save_waypoint_changes(self):
        """Overrites waypoint with the changes from the inspector panel."""
        indices = self.view.get_selected_indices()
        if not indices: return
        idx = indices[0]
        
        params = self.view.get_waypoint_params()
        poses = self.view.get_inspector_poses()
        
        if poses is not None:
            params["pos"] = poses
        else:
            params["pos"] = self.model.sequence[idx]["pos"] # Behalte alte daten, falls Eingabe fehlerhaft

        self.model.update_pose(idx, params)
        self.view.update_treeview(self.model.sequence, select_index=idx)
        self._auto_save()
        self.logger.info(f"Overwrote WP #{idx} with data from Inspector.")

    def handle_move_up(self, event=None):
        indices = self.view.get_selected_indices()
        if not indices: return
        new_idx = self.model.move_up(indices[0])
        self.view.update_treeview(self.model.sequence, select_index=new_idx)
        self._auto_save()

    def handle_move_down(self, event=None):
        indices = self.view.get_selected_indices()
        if not indices: return
        new_idx = self.model.move_down(indices[0])
        self.view.update_treeview(self.model.sequence, select_index=new_idx)
        self._auto_save()

    def handle_delete_poses(self, event=None):
        indices = self.view.get_selected_indices()
        if not indices: return
        self.model.delete_poses(indices)
        self.view.update_treeview(self.model.sequence)
        self.view._set_inspector_state("disabled")
        self.view.lbl_inspector_title.config(text="No Waypoint Selected")
        self._auto_save()

    def handle_clear_list(self):
        self.model.clear()
        if self.model.current_filepath:
            self.model.current_filepath = None
            self.view.set_active_file_label(None)
        self.view.update_treeview(self.model.sequence)
        self.view._set_inspector_state("disabled")
        self.view.lbl_inspector_title.config(text="No Waypoint Selected")
        self.logger.warning("Sequence list wiped clean.")

    def _auto_save(self):
        if self.model.current_filepath is None and len(self.model.sequence) > 0:
            timestamp = time.strftime("%Y_%m_%d-%H_%M_%S")
            new_file = os.path.join("expressions", f"{timestamp}.json")
            self.model.current_filepath = new_file
            self.view.set_active_file_label(new_file)
            self.logger.info(f"Initiated new auto-save context: {new_file}")

        if self.model.current_filepath is not None:
            self.model.save_to_json()

    def handle_save_json(self):
        if not self.model.sequence and self.model.current_filepath is not None: return
        self.model.save_to_json()
        self.logger.info("Manual save executed successfully.")

    def handle_load_json(self):
        self.is_dialog_open = True 
        try:
            path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
            if path:
                self.model.load_from_json(path)
                self.view.update_treeview(self.model.sequence)
                self.view.set_active_file_label(path) 
        except Exception as e:
            self.logger.error(f"Error loading JSON: {str(e)}")
        finally:
            self.is_dialog_open = False 
    
    def handle_undo(self, event=None):
        if self.model.undo():
            self.view.update_treeview(self.model.sequence)
            self._auto_save()

    def handle_redo(self, event=None):
        if self.model.redo():
            self.view.update_treeview(self.model.sequence)
            self._auto_save()

    def handle_media_pause(self):
        if not self.hardware.state.is_connected:
            return
        self.hardware.toggle_pause_action()
        if getattr(self.hardware, '_is_action_paused', False):
            self.view.btn_pause_media.config(fg="orange")
        else:
            self.view.btn_pause_media.config(fg="black")

    def handle_media_stop(self):
        if not self.hardware.state.is_connected:
            return
        self.logger.info("Soft-STOP requested.")
        self.stop_requested = True 
        self.hardware.stop()
        if getattr(self.hardware, '_is_action_paused', False):
            self.hardware._is_action_paused = False
            self.view.btn_pause_media.config(fg="black")

    def handle_start_replay(self):
        if not self.model.sequence or not self.hardware.state.is_connected: return
        if self.is_replaying: return
        
        self.stop_requested = False
        self.is_replaying = True
        
        threading.Thread(target=self._replay_worker, daemon=True).start()

    def _replay_worker(self):
        from kortex_api.autogen.messages import Base_pb2
        import time

        try:
            self.logger.info("=== START SEQUENCE-REPLAY ===")
            batch_waypoints = []
            batch_duration = 0.0

            def flush_waypoints():
                nonlocal batch_waypoints, batch_duration
                if not batch_waypoints: return
                
                wp_list = Base_pb2.WaypointList()
                wp_list.use_optimal_blending = True
                for wp_data in batch_waypoints:
                    wp = wp_list.waypoints.add()
                    wp.angular_waypoint.angles.extend(wp_data['pos'])
                    wp.angular_waypoint.duration = wp_data['duration_s']
                    if sum(wp_data['max_velocities']) > 0:
                        wp.angular_waypoint.maximum_velocities.extend(wp_data['max_velocities'])

                self.logger.info(f"[BATCH] Send {len(batch_waypoints)} Waypoints to hardware...")
                completion_event = self.hardware.execute_waypoint_list(wp_list)
                
                if completion_event:
                    completion_event.wait(timeout=batch_duration + 5.0) 
                    
                batch_waypoints.clear()
                batch_duration = 0.0

            for idx, step in enumerate(self.model.sequence):
                if self.stop_requested: break
                stype = step["type"]

                if stype == "angularwaypoint":
                    batch_waypoints.append(step)
                    batch_duration += step["duration_s"]

                elif stype == "action":
                    flush_waypoints()
                    
                    self.logger.info(f"[STEP {idx}] Send action to hardware...")
                    completion_event = self.hardware.execute_action_pose(
                        step["pos"], 
                        step["duration_s"], 
                        f"Step_{idx}"
                    )
                    
                    if completion_event:
                        completion_event.wait(timeout=step["duration_s"] + 5.0)

                elif stype == "pause":
                    flush_waypoints()
                    p_time = step["duration_s"]
                    self.logger.info(f"[STEP {idx}] ⏱️ PAUSE: {p_time}s")
                    time.sleep(p_time)

            flush_waypoints()
            self.logger.info("=== REPLAY COMPLETED SUCCESSFULLY ===")

        except Exception as e:
            self.logger.error(f"Exception occured during Replay: {e}")
        finally:
            self.is_replaying = False