import json
import logging
import copy

class SequenceModel:
    """Manages the data logic for the robot's movement sequence in memory."""
    def __init__(self):
        self.logger = logging.getLogger("Model")
        self.sequence = []
        self.undo_stack = [] 
        self.redo_stack = []
        self.current_filepath = None

    def _save_state(self):
        self.undo_stack.append(copy.deepcopy(self.sequence))
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack: 
            return False
        self.redo_stack.append(copy.deepcopy(self.sequence))
        self.sequence = self.undo_stack.pop()
        return True

    def redo(self):
        if not self.redo_stack: 
            return False
        self.undo_stack.append(copy.deepcopy(self.sequence))
        self.sequence = self.redo_stack.pop()
        return True

    def append_pose(self, pose_data):
        """Appends a complete waypoint dictionary to the end of the sequence."""
        self._save_state()
        self.sequence.append(pose_data)
        self.logger.debug(f"Appended new waypoint. Total waypoints: {len(self.sequence)}.")

    def update_pose(self, index, pose_data):
        """Updates a complete waypoint dictionary at an existing index."""
        if 0 <= index < len(self.sequence):
            self._save_state()
            self.sequence[index] = pose_data
            self.logger.debug(f"Updated waypoint at index {index}.")

    def delete_poses(self, indices):
        """Deletes waypoints based on a list of indices."""
        self._save_state()
        for index in sorted(indices, reverse=True):
            if 0 <= index < len(self.sequence):
                del self.sequence[index]
        self.logger.debug(f"Deleted waypoints at indices: {indices}.")

    def move_up(self, index):
        if index > 0:
            self._save_state()
            self.sequence[index], self.sequence[index-1] = self.sequence[index-1], self.sequence[index]
            return index - 1
        return index

    def move_down(self, index):
        if index < len(self.sequence) - 1:
            self._save_state()
            self.sequence[index], self.sequence[index+1] = self.sequence[index+1], self.sequence[index]
            return index + 1
        return index

    def clear(self):
        self._save_state()
        count = len(self.sequence)
        self.sequence.clear()
        self.logger.debug(f"Cleared model sequence. Removed {count} item(s).")

    def save_to_json(self, filepath=None):
        path_to_save = filepath or self.current_filepath
        if path_to_save:
            try:
                with open(path_to_save, 'w') as f:
                    json.dump(self.sequence, f, indent=4)
                self.current_filepath = path_to_save 
                self.logger.info(f"Successfully saved {len(self.sequence)} waypoints to '{path_to_save}'.")
            except Exception as e:
                self.logger.error(f"Failed to save JSON to '{path_to_save}': {e}")

    def load_from_json(self, filepath):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    # Migration für alte JSON-Strukturen
                    for step in data:
                        if "type" not in step:
                            step["type"] = "action"
                            step["duration_s"] = 3.0
                            step["pause_s"] = 0.0
                            step["max_velocities"] = [0.0]*6
                        if "speed_deg_s" in step:
                            del step["speed_deg_s"]
                            
                    self.sequence = data
                    self.current_filepath = filepath
                    self.undo_stack.clear()
                    self.redo_stack.clear()
                    self.logger.info(f"Successfully loaded {len(self.sequence)} waypoints from '{filepath}'.")
                else:
                    raise ValueError("Data inside JSON is not a valid sequence list.")
        except Exception as e:
            self.logger.error(f"Failed to load JSON from '{filepath}': {e}")
            raise