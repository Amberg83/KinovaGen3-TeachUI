import json
import logging

class SequenceModel:
    def __init__(self):
        self.logger = logging.getLogger("Model")
        self.sequence = []
        self.current_filepath = None

    def append_pose(self, poses_deg, speed=20):
        self.sequence.append({"pos": poses_deg, "speed": speed})

    def insert_pose(self, index, poses_deg, speed=20):
        self.sequence.insert(index, {"pos": poses_deg, "speed": speed})

    def update_pose(self, index, poses_deg):
        if 0 <= index < len(self.sequence):
            self.sequence[index]["pos"] = poses_deg

    def delete_poses(self, indices):
        for index in sorted(indices, reverse=True):
            if 0 <= index < len(self.sequence):
                del self.sequence[index]

    def move_up(self, index):
        if index > 0:
            self.sequence[index], self.sequence[index-1] = self.sequence[index-1], self.sequence[index]
            return index - 1
        return index

    def move_down(self, index):
        if index < len(self.sequence) - 1:
            self.sequence[index], self.sequence[index+1] = self.sequence[index+1], self.sequence[index]
            return index + 1
        return index

    def set_speed(self, indices, speed):
        for index in indices:
            if 0 <= index < len(self.sequence):
                self.sequence[index]["speed"] = speed

    def clear(self):
        self.sequence.clear()

    def save_to_json(self, filepath=None):
        path_to_save = filepath or self.current_filepath
        if path_to_save:
            try:
                with open(path_to_save, 'w') as f:
                    json.dump(self.sequence, f, indent=4)
                self.current_filepath = path_to_save 
            except Exception as e:
                self.logger.error(f"Failed to save JSON: {e}")

    def load_from_json(self, filepath):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                
                if isinstance(data, list):
                    self.sequence = data
                    self.current_filepath = filepath
                else:
                    raise ValueError("Data inside JSON is not a sequence list.")
                    
        except Exception as e:
            self.logger.error(f"Failed to load JSON: {e}")
            raise