import time
import os
import threading
import logging
from robot_state import RobotState
from model import SequenceModel
from kinova_hardware import KinovaHardware
from view import RobotView

class RobotController:
    """Orchestrates application logic, linking View intents to Model/Hardware mutations."""
    def __init__(self, root, view: RobotView, model: SequenceModel, hardware: KinovaHardware):
        self.root = root
        self.view = view
        self.model = model
        self.hardware = hardware
        
        self.logger = logging.getLogger("Controller")
        
        self.stop_requested = False
        self.is_replaying = False

        os.makedirs("expressions", exist_ok=True)
        
        # STRICT MVC WIRING: View observes Model & Hardware directly.
        self.model.register_observer(self.view.on_sequence_changed)
        self.hardware.register_observer(self.view.on_hardware_state_changed)
        
        # Bind abstract intents from the View to Controller actions
        self.view.bind_commands({
            "reconnect": self.handle_reconnect,
            "clear_faults": self.handle_clear_faults,
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
            "estop": self.handle_emergency_stop,
            "stop_media": self.handle_media_stop,
            "pause_media": self.handle_media_pause
        })

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

    def handle_emergency_stop(self):
        self.stop_requested = True
        if self.hardware.state.is_connected:
            threading.Thread(target=self.hardware.apply_emergency_stop, daemon=True).start()

    def handle_tree_select(self, idx):
        """Passes model data to the view for the inspector."""
        step_data = self.model.sequence[idx]
        self.view.load_inspector_data(step_data, idx)

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

    def handle_move_down(self, idx):
        self.model.move_down(idx)
        self._auto_save()

    def handle_delete_poses(self, indices):
        self.model.delete_poses(indices)
        self._auto_save()

    def handle_undo(self):
        if self.model.undo():
            self._auto_save()

    def handle_redo(self):
        if self.model.redo():
            self._auto_save()

    def handle_append_pose(self, poses):
        params = {"type": "action", "duration_s": 5.0, "max_velocities": [0.0]*6, "pause_s": 0.0}
        pose_data = {"pos": poses, **params}
        self.model.append_pose(pose_data)
        self._auto_save()
        self.logger.info(f"Captured current live pose to new entry.")

    def handle_save_waypoint_changes(self, idx, params, poses):
        if poses is not None:
            params["pos"] = poses
        else:
            params["pos"] = self.model.sequence[idx]["pos"] 
            
        self.model.update_pose(idx, params)
        self._auto_save()
        self.logger.info(f"Overwrote WP #{idx} with data from Inspector.")

    def _auto_save(self):
        """Explicitly called by the Controller only after actual data mutations."""
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