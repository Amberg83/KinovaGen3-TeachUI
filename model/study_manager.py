import os
import json
import time
import logging
import shutil

class StudyManager:
    """
    Manages the state, task transition, logging, and backups for a user study session.
    Keeps high-level experimental workflow logic cleanly separated from the controller.
    """
    def __init__(self, participant_id=""):
        self.participant_id = participant_id
        self.study_mode = bool(participant_id)
        self.logger = logging.getLogger("StudyManager")
        
        self.tasks = []
        self.task_order_indices = []
        self.current_task_index = 0
        self.task_start_time = 0.0
        
        if self.study_mode:
            self.tasks = self._load_or_create_referents()
            n_tasks = len(self.tasks)
            pid_int = int(self.participant_id) if self.participant_id.isdigit() else 1
            # Balanced Latin Square task mapping based on participant ID
            self.task_order_indices = [(pid_int - 1 + i) % n_tasks for i in range(n_tasks)]
            self.current_task_index = 0
            self.task_start_time = time.time()
            self.logger.info(f"Study Mode activated for PID: '{self.participant_id}' with task order indices: {self.task_order_indices}")

    def get_active_task(self):
        """Returns the currently active task dictionary, or None if not in study mode."""
        if not self.study_mode or self.current_task_index >= len(self.tasks):
            return None
        return self.tasks[self.task_order_indices[self.current_task_index]]

    def get_total_tasks(self):
        """Returns the total number of tasks in the study."""
        return len(self.tasks)

    def complete_task(self, current_sequence_model):
        """
        Processes current task completion:
        1. Backs up the current sequence to a participant-specific folder.
        2. Appends transaction record to CSV metrics.
        3. Moves state to the next task.
        4. Handles archiving log files when the entire study finishes.
        
        Returns:
            Tuple (bool study_completed, dict next_task)
        """
        if not self.study_mode:
            return False, None

        active_task = self.get_active_task()
        if not active_task:
            return True, None

        task_id = active_task["id"]
        task_name = active_task["name"]
        
        # 1. Back up current timeline JSON inside separate folder for the PID
        study_results_dir = "study_results"
        pid_dir = os.path.join(study_results_dir, self.participant_id)
        os.makedirs(pid_dir, exist_ok=True)
        
        timestamp_str = time.strftime("%Y_%m_%d-%H_%M_%S")
        backup_filename = f"task_{task_id}_{timestamp_str}.json"
        backup_path = os.path.join(pid_dir, backup_filename)
        
        # Save sequence list even if empty
        current_sequence_model.save_to_json(backup_path)
        
        # 2. Append to log file
        log_path = os.path.join(study_results_dir, "study_logs.csv")
        start_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.task_start_time))
        end_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
        
        write_header = not os.path.exists(log_path)
        presentation_order = self.current_task_index + 1
        
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                if write_header:
                    f.write("PID,PresentationOrder,ReferentID,ReferentName,StartTime,EndTime,BackupFile\n")
                f.write(f'"{self.participant_id}",{presentation_order},{task_id},"{task_name}","{start_time_str}","{end_time_str}","{backup_filename}"\n')
            self.logger.info(f"Logged task {presentation_order} metrics to {log_path}")
        except Exception as e:
            self.logger.error(f"Failed to write study_logs.csv: {e}")

        # 3. Transition to next task
        self.current_task_index += 1
        if self.current_task_index < len(self.tasks):
            self.task_start_time = time.time()
            next_task = self.get_active_task()
            return False, next_task
        else:
            # Study completed! Archive log file
            self._archive_session_logs(pid_dir)
            return True, None

    def _archive_session_logs(self, pid_dir):
        """Locates active python file logger handlers and copies them to results."""
        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.FileHandler):
                handler.flush()
        
        copied_log = False
        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.FileHandler):
                active_log_filepath = handler.baseFilename
                if active_log_filepath and os.path.exists(active_log_filepath):
                    try:
                        target_log_path = os.path.join(pid_dir, "teach_ui.log")
                        shutil.copy(active_log_filepath, target_log_path)
                        self.logger.info(f"Successfully archived session log file to '{target_log_path}'.")
                        copied_log = True
                        break
                    except Exception as copy_err:
                        self.logger.error(f"Failed to copy active log file: {copy_err}")
                        
        if not copied_log:
            self.logger.warning("Could not locate active log file handler to archive.")

    def _load_or_create_referents(self):
        """Loads study tasks from referents.json, creating a default file if missing."""
        path = "referents.json"
        default_tasks = [
            {
                "id": 1,
                "name": "Winken (Wave)",
                "instructions": "Bringe den Roboter dazu, mit seiner Hand eine winkende Geste auszuführen.\nBewege dazu den Roboter von links nach rechts."
            },
            {
                "id": 2,
                "name": "Zeigen (Point)",
                "instructions": "Bringe den Roboter dazu, auf die Tür zu zeigen.\nHalte den Arm für mindestens 2 Sekunden still."
            },
            {
                "id": 3,
                "name": "Objekt greifen (Pick Object)",
                "instructions": "Bewege den Arm so, dass er das Objekt greifen kann.\nPositioniere den Greifer über dem Becher."
            },
            {
                "id": 4,
                "name": "Objekt ablegen (Place Object)",
                "instructions": "Bewege den Arm so, dass er das gegriffene Objekt auf dem Tisch ablegt.\nFahre danach in eine sichere Warteposition."
            }
        ]
        
        if not os.path.exists(path):
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(default_tasks, f, indent=2, ensure_ascii=False)
                self.logger.info("Created default referents.json configuration file.")
                return default_tasks
            except Exception as e:
                self.logger.error(f"Failed to write default referents.json: {e}")
                return default_tasks
        else:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    tasks = json.load(f)
                self.logger.info(f"Successfully loaded {len(tasks)} tasks from referents.json.")
                return tasks
            except Exception as e:
                self.logger.error(f"Failed to read referents.json: {e}. Using defaults.")
                return default_tasks
