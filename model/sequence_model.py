import json
import logging
import copy
from utils.event_bus import EventBus

class SequenceModel:
    """Manages the data logic for the robot's movement sequence in memory."""
    def __init__(self):
        self.logger = logging.getLogger("Model")
        self.sequence = []
        self.undo_stack = [] 
        self.redo_stack = []
        self.current_filepath = None

    def _notify_observers(self, select_index=None):
        """Broadcasts the current state to all observers via EventBus."""
        EventBus.publish("sequence_updated", self.sequence, self.current_filepath, select_index)

    def _save_state(self):
        self.undo_stack.append(copy.deepcopy(self.sequence))
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack: 
            return False
        self.redo_stack.append(copy.deepcopy(self.sequence))
        self.sequence = self.undo_stack.pop()
        self._notify_observers()
        return True

    def redo(self):
        if not self.redo_stack: 
            return False
        self.undo_stack.append(copy.deepcopy(self.sequence))
        self.sequence = self.redo_stack.pop()
        self._notify_observers()
        return True

    def append_pose(self, pose_data):
        self._save_state()
        self.sequence.append(pose_data)
        self.logger.info(f"Appended new waypoint. Total waypoints: {len(self.sequence)}.")
        self._notify_observers(select_index=len(self.sequence) - 1)

    def insert_pose(self, pose_data, index):
        self._save_state()
        self.sequence.insert(index + 1, pose_data)
        self.logger.info(f"Inserted new waypoint at index {index + 1}. Total waypoints: {len(self.sequence)}.")
        self._notify_observers(select_index=index + 1)

    def update_pose(self, index, pose_data):
        if 0 <= index < len(self.sequence):
            self._save_state()
            existing = self.sequence[index]
            
            # Prune joint position and velocity constraints for Pause and Gripper step types
            if pose_data.get("type") in ("pause", "gripper"):
                if "pos" in pose_data:
                    del pose_data["pos"]
                if "max_velocities" in pose_data:
                    del pose_data["max_velocities"]
            else:
                # Merge target_angles if present and containing None values (selective copy)
                if "pos" in pose_data and "pos" in existing:
                    merged_angles = []
                    for target, orig in zip(pose_data["pos"], existing["pos"]):
                        merged_angles.append(orig if target is None else target)
                    pose_data["pos"] = merged_angles
            
            self.sequence[index] = pose_data
            self.logger.info(f"Updated waypoint at index {index}.")
            self._notify_observers(select_index=index)

    def bulk_update_waypoint_changes(self, indices, duration_s, target_type=None):
        if not indices:
            return
        self._save_state()
        for index in indices:
            if 0 <= index < len(self.sequence):
                self.sequence[index]["duration_s"] = float(duration_s)
                if target_type is not None:
                    old_type = self.sequence[index].get("type")
                    if old_type != target_type:
                        self.sequence[index]["type"] = target_type
                        # Ensure structure is valid for the new type
                        if target_type in ("action", "angularwaypoint"):
                            if "pos" not in self.sequence[index]:
                                self.sequence[index]["pos"] = [0.0] * 6
                            if "max_velocities" not in self.sequence[index]:
                                self.sequence[index]["max_velocities"] = [0.0] * 6
        self.logger.info(f"Bulk updated waypoints {indices}: duration to {duration_s}s, type to {target_type}.")
        self._notify_observers(select_index=indices)

    def bulk_update_durations_custom(self, index_to_duration_dict):
        """Bulk updates multiple waypoints with individual customized durations in a single undo state."""
        if not index_to_duration_dict:
            return
        self._save_state()
        for index, duration_s in index_to_duration_dict.items():
            if 0 <= index < len(self.sequence):
                self.sequence[index]["duration_s"] = float(duration_s)
        self.logger.info(f"Bulk updated customized durations of waypoints.")
        self._notify_observers(select_index=list(index_to_duration_dict.keys()))

    def delete_poses(self, indices):
        self._save_state()
        for index in sorted(indices, reverse=True):
            if 0 <= index < len(self.sequence):
                del self.sequence[index]
        self.logger.info(f"Deleted waypoints at indices: {indices}.")
        self._notify_observers()

    def move_up(self, index):
        if index > 0:
            self._save_state()
            self.sequence[index], self.sequence[index-1] = self.sequence[index-1], self.sequence[index]
            self._notify_observers(select_index=index - 1)

    def move_down(self, index):
        if index < len(self.sequence) - 1:
            self._save_state()
            self.sequence[index], self.sequence[index+1] = self.sequence[index+1], self.sequence[index]
            self._notify_observers(select_index=index + 1)

    def move_pose(self, from_index, to_index):
        if 0 <= from_index < len(self.sequence) and 0 <= to_index < len(self.sequence):
            if from_index == to_index:
                return
            self._save_state()
            pose = self.sequence.pop(from_index)
            self.sequence.insert(to_index, pose)
            self.logger.info(f"Moved waypoint from index {from_index} to index {to_index}.")
            self._notify_observers(select_index=to_index)

    def copy_poses(self, indices):
        """Returns deep-copied sequence elements of specified indices."""
        copied = []
        for idx in sorted(indices):
            if 0 <= idx < len(self.sequence):
                copied.append(copy.deepcopy(self.sequence[idx]))
        return copied

    def paste_poses(self, poses, after_index):
        """Pastes a list of poses behind the specified index. If index is None, appends to the end."""
        if not poses:
            return
        self._save_state()
        if after_index is None or after_index < 0 or after_index >= len(self.sequence):
            # Append to the end
            start_idx = len(self.sequence)
            self.sequence.extend(copy.deepcopy(poses))
            new_selection = list(range(start_idx, len(self.sequence)))
        else:
            # Insert behind after_index
            new_selection = []
            for i, p in enumerate(poses):
                insert_idx = after_index + 1 + i
                self.sequence.insert(insert_idx, copy.deepcopy(p))
                new_selection.append(insert_idx)
        
        self.logger.info(f"Pasted {len(poses)} waypoint(s). Total waypoints: {len(self.sequence)}.")
        self._notify_observers(select_index=new_selection)

    def clear(self):
        self._save_state()
        count = len(self.sequence)
        self.sequence.clear()
        self.current_filepath = None
        self.logger.info(f"Cleared model sequence. Removed {count} item(s).")
        self._notify_observers()

    def save_to_json(self, filepath=None):
        path_to_save = filepath or self.current_filepath
        if path_to_save:
            try:
                with open(path_to_save, 'w', encoding='utf-8') as f:
                    json.dump(self.sequence, f, indent=4)
                self.current_filepath = path_to_save 
                self.logger.info(f"Successfully saved {len(self.sequence)} waypoints to '{path_to_save}'.")
                self._notify_observers()
            except Exception as e:
                self.logger.error(f"Failed to save JSON to '{path_to_save}': {e}")

    def load_from_json(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for step in data:
                        if "type" not in step:
                            step["type"] = "action"
                            step["duration_s"] = 3.0
                            step["pause_s"] = 0.0
                            step["max_velocities"] = [0.0]*6
                        if "speed_deg_s" in step:
                            del step["speed_deg_s"]
                            
                        # Backward compatibility migration for Robotiq gripper format:
                        # Rename gripper_speed to gripper_duration and prune gripper_force entirely
                        if step.get("type") == "gripper":
                            if "gripper_force" in step:
                                del step["gripper_force"]
                            if "gripper_speed" in step:
                                step["gripper_duration"] = step.pop("gripper_speed")
                            step["gripper_state"] = step.get("gripper_state", "open")
                            step["gripper_duration"] = step.get("gripper_duration", "medium")
                            
                            # Migrate custom target position percentage
                            if "gripper_target_pos" not in step:
                                state_lower = step["gripper_state"].lower()
                                if state_lower == "open":
                                    step["gripper_target_pos"] = 0.0
                                elif state_lower == "closed":
                                    step["gripper_target_pos"] = 100.0
                                elif state_lower == "pickup":
                                    step["gripper_target_pos"] = 50.0
                                else:
                                    step["gripper_target_pos"] = 0.0
                                    
                            # Migrate custom speed ratio override
                            if "gripper_speed_ratio" not in step:
                                dur_lower = step["gripper_duration"].lower()
                                if dur_lower == "slow":
                                    step["gripper_speed_ratio"] = 0.2
                                elif dur_lower == "medium":
                                    step["gripper_speed_ratio"] = 0.5
                                elif dur_lower == "fast":
                                    step["gripper_speed_ratio"] = 0.0
                                else:
                                    step["gripper_speed_ratio"] = 0.5
                            
                    self.sequence = data
                    self.current_filepath = filepath
                    self.undo_stack.clear()
                    self.redo_stack.clear()
                    self.logger.info(f"Successfully loaded {len(self.sequence)} waypoints from '{filepath}'.")
                    self._notify_observers()
                else:
                    raise ValueError("Data inside JSON is not a valid sequence list.")
        except Exception as e:
            self.logger.error(f"Failed to load JSON from '{filepath}': {e}")
            raise
