import json
import logging

class SequenceModel:
    """
    Manages the data logic for the robot's movement sequence.
    Handles appending, updating, deleting, and saving waypoints.
    """
    def __init__(self):
        self.logger = logging.getLogger("Model")
        self.sequence = []
        self.current_filepath = None

    def append_pose(self, poses_deg, speed=20):
        """Appends a new waypoint to the end of the sequence."""
        self.sequence.append({"pos": poses_deg, "speed": speed})
        self.logger.debug(f"Appended pose. Total waypoints: {len(self.sequence)}.")

    def insert_pose(self, index, poses_deg, speed=20):
        """Inserts a new waypoint at a specific index."""
        self.sequence.insert(index, {"pos": poses_deg, "speed": speed})
        self.logger.debug(f"Inserted pose at index {index}.")

    def update_pose(self, index, poses_deg):
        """Updates the joint angles of an existing waypoint."""
        if 0 <= index < len(self.sequence):
            self.sequence[index]["pos"] = poses_deg
            self.logger.debug(f"Updated pose at index {index}.")

    def delete_poses(self, indices):
        """Deletes multiple waypoints based on their indices."""
        for index in sorted(indices, reverse=True):
            if 0 <= index < len(self.sequence):
                del self.sequence[index]
        self.logger.debug(f"Deleted waypoints at indices: {indices}. Remaining: {len(self.sequence)}.")

    def move_up(self, index):
        """Moves a waypoint one position up in the sequence list."""
        if index > 0:
            self.sequence[index], self.sequence[index-1] = self.sequence[index-1], self.sequence[index]
            return index - 1
        return index

    def move_down(self, index):
        """Moves a waypoint one position down in the sequence list."""
        if index < len(self.sequence) - 1:
            self.sequence[index], self.sequence[index+1] = self.sequence[index+1], self.sequence[index]
            return index + 1
        return index

    def set_speed(self, indices, speed):
        """Applies a new speed value to the specified waypoints."""
        for index in indices:
            if 0 <= index < len(self.sequence):
                self.sequence[index]["speed"] = speed
        self.logger.debug(f"Applied speed {speed}°/s to indices: {indices}.")

    def clear(self):
        """Clears the entire sequence."""
        count = len(self.sequence)
        self.sequence.clear()
        self.logger.debug(f"Cleared model sequence. Removed {count} items.")

    def save_to_json(self, filepath=None):
        """Saves the current sequence to a JSON file."""
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
        """Loads a sequence of waypoints from a JSON file."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                
                if isinstance(data, list):
                    self.sequence = data
                    self.current_filepath = filepath
                    self.logger.info(f"Successfully loaded {len(self.sequence)} waypoints from '{filepath}'.")
                else:
                    raise ValueError("Data inside JSON is not a valid sequence list.")
                    
        except Exception as e:
            self.logger.error(f"Failed to load JSON from '{filepath}': {e}")
            raise