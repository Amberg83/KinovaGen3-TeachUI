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
        self._observers = []

    def register_observer(self, callback):
        """Registers a callback to be notified when the model changes."""
        if callback not in self._observers:
            self._observers.append(callback)

    def _notify_observers(self, select_index=None):
        """Broadcasts the current state to all observers."""
        for observer in self._observers:
            observer(self.sequence, self.current_filepath, select_index)

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

    def update_pose(self, index, pose_data):
        if 0 <= index < len(self.sequence):
            self._save_state()
            self.sequence[index] = pose_data
            self.logger.info(f"Updated waypoint at index {index}.")
            self._notify_observers(select_index=index)

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
                with open(path_to_save, 'w') as f:
                    json.dump(self.sequence, f, indent=4)
                self.current_filepath = path_to_save 
                self.logger.info(f"Successfully saved {len(self.sequence)} waypoints to '{path_to_save}'.")
                self._notify_observers()
            except Exception as e:
                self.logger.error(f"Failed to save JSON to '{path_to_save}': {e}")

    def load_from_json(self, filepath):
        try:
            with open(filepath, 'r') as f:
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