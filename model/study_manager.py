import os
import json
import time
import logging
import shutil
import csv

class StudyManager:
    """
    Manages the state, task transition, logging, and backups for a user study session.
    Keeps high-level experimental workflow logic cleanly separated from the controller.
    """
    def __init__(self, participant_id="", is_review_mode=False):
        self.participant_id = participant_id
        self.study_mode = bool(participant_id)
        self.logger = logging.getLogger("StudyManager")
        
        self.tasks = []
        self.tutorials = []
        self.experimental_tasks = []
        self.current_task_index = 0
        self.task_start_time = 0.0
        self.current_task_filepath = None
        self.session_creation_timestamp = int(time.time())
        self.review_mode = False
        
        if self.study_mode:
            # Check if this participant_id matches an existing directory under study_results and Review Mode was checked
            possible_path = os.path.join("study_results", self.participant_id)
            if is_review_mode and os.path.isdir(possible_path):
                self.review_mode = True
                self.logger.info(f"Review Mode activated: loading session folder '{self.participant_id}'")
                
                # Parse participant ID and original session timestamp if it follows the PID-timestamp pattern
                if "-" in self.participant_id:
                    parts = self.participant_id.rsplit("-", 1)
                    if len(parts) == 2 and parts[1].isdigit():
                        self.participant_id = parts[0]
                        self.session_creation_timestamp = int(parts[1])
                        self.logger.info(f"Parsed original PID: '{self.participant_id}' and Session Timestamp: {self.session_creation_timestamp}")
            
            # If in review mode, attempt to load the task sequence from the CSV inside the folder
            csv_loaded = False
            if self.review_mode:
                csv_filename = f"study_log-{self.participant_id}-{self.session_creation_timestamp}.csv"
                session_folder = f"{self.participant_id}-{self.session_creation_timestamp}"
                csv_path = os.path.join("study_results", session_folder, csv_filename)
                
                if os.path.exists(csv_path):
                    try:
                        loaded_tasks = []
                        with open(csv_path, "r", encoding="utf-8") as f:
                            reader = csv.DictReader(f)
                            # Strip whitespace from headers
                            reader.fieldnames = [name.strip() for name in reader.fieldnames] if reader.fieldnames else []
                            
                            # Fallbacks for instructions if not present in CSV
                            normal_ref = {t["id"]: t for t in self._load_or_create_referents()}
                            normal_tut = {t["id"]: t for t in self._load_or_create_tutorials()}
                            
                            for row in reader:
                                rid_str = row.get("RID", "").strip()
                                rid = int(rid_str) if rid_str.isdigit() else 0
                                rname = row.get("RName", "").strip()
                                
                                # Use instructions from CSV if available, otherwise fall back to matching configuration
                                rinstructions = row.get("RInstructions", None)
                                if rinstructions is not None:
                                    rinstructions = rinstructions.strip()
                                else:
                                    config_task = normal_ref.get(rid) or normal_tut.get(rid)
                                    rinstructions = config_task["instructions"] if config_task else ""
                                    
                                loaded_tasks.append({
                                    "id": rid,
                                    "name": rname,
                                    "instructions": rinstructions,
                                    "gesture_file": row.get("GestureFile", "").strip()
                                })
                        if loaded_tasks:
                            self.tasks = loaded_tasks
                            csv_loaded = True
                            self.logger.info(f"Successfully loaded {len(self.tasks)} tasks from session log CSV at {csv_path}")
                    except Exception as e:
                        self.logger.error(f"Error reading session log CSV at {csv_path}: {e}. Falling back to default order.")
            
            if not csv_loaded:
                self.tutorials = self._load_or_create_tutorials()
                self.experimental_tasks = self._load_or_create_referents()
                
                n_experimental = len(self.experimental_tasks)
                pid_int = int(self.participant_id) if self.participant_id.isdigit() else 1
                
                # Reorder experimental tasks first using the balanced Latin Square
                latin_order = self._generate_balanced_latin_square_order(pid_int, n_experimental)
                ordered_experimental = [self.experimental_tasks[idx] for idx in latin_order]
                
                # Combine tutorials and ordered experimental tasks directly
                self.tasks = self.tutorials + ordered_experimental
            
            self.current_task_index = 0
            self.task_start_time = time.time()
            self._update_current_task_filepath()
            
            mode_str = "Review Mode" if self.review_mode else "Study Mode"
            self.logger.info(f"{mode_str} activated for PID: '{self.participant_id}' (Session: {self.session_creation_timestamp}) with tasks in presentation order: {[t['name'] for t in self.tasks]}")

    def _update_current_task_filepath(self):
        """Updates the persistent filepath for the currently active study task."""
        if not self.study_mode:
            self.current_task_filepath = None
            return
        active_task = self.get_active_task()
        if not active_task:
            self.current_task_filepath = None
            return
        
        task_id = active_task["id"]
        study_results_dir = "study_results"
        pid_dir = os.path.join(study_results_dir, f"{self.participant_id}-{self.session_creation_timestamp}")
        
        # If in Review Mode, find the existing gesture file
        if getattr(self, "review_mode", False) and os.path.exists(pid_dir):
            gesture_file = active_task.get("gesture_file")
            if gesture_file:
                path = os.path.join(pid_dir, gesture_file)
                if os.path.exists(path):
                    self.current_task_filepath = path
                    return
            # Fallback to scanning if gesture_file is missing or not found
            for filename in os.listdir(pid_dir):
                if filename.startswith(f"task_{task_id}_") and filename.endswith(".json"):
                    self.current_task_filepath = os.path.join(pid_dir, filename)
                    return
        
        os.makedirs(pid_dir, exist_ok=True)
        timestamp_str = str(int(self.task_start_time))
        self.current_task_filepath = os.path.join(pid_dir, f"task_{task_id}_{timestamp_str}.json")

    def get_active_task(self):
        """Returns the currently active task dictionary, or None if not in study mode."""
        if not self.study_mode or self.current_task_index >= len(self.tasks):
            return None
        return self.tasks[self.current_task_index]

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
        
        # If in Review Mode, completely bypass saving, CSV writing, and log archiving
        if getattr(self, "review_mode", False):
            self.current_task_index += 1
            if self.current_task_index < len(self.tasks):
                self.task_start_time = time.time()
                self._update_current_task_filepath()
                next_task = self.get_active_task()
                return False, next_task
            else:
                return True, None
        
        # 1. Back up current timeline JSON inside separate folder for the PID
        if self.current_task_filepath:
            pid_dir = os.path.dirname(self.current_task_filepath)
            os.makedirs(pid_dir, exist_ok=True)
            current_sequence_model.save_to_json(self.current_task_filepath)
            backup_filename = os.path.basename(self.current_task_filepath)
        else:
            # Fallback
            pid_dir = os.path.join("study_results", f"{self.participant_id}-{self.session_creation_timestamp}")
            os.makedirs(pid_dir, exist_ok=True)
            timestamp_str = str(int(time.time()))
            backup_filename = f"task_{task_id}_{timestamp_str}.json"
            backup_path = os.path.join(pid_dir, backup_filename)
            current_sequence_model.save_to_json(backup_path)
        
        # 2. Append to participant-specific CSV log file
        log_filename = f"study_log-{self.participant_id}-{self.session_creation_timestamp}.csv"
        log_path = os.path.join(pid_dir, log_filename)
        
        write_header = not os.path.exists(log_path)
        presentation_order = self.current_task_index + 1
        
        start_time_unix = int(self.task_start_time)
        end_time_unix = int(time.time())
        
        try:
            # Note: newline="" is recommended when writing files using python's csv module
            with open(log_path, "a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                if write_header:
                    writer.writerow(["PID", "Starttime", "Endtime", "RID", "RName", "RInstructions", "PresentationOrder", "GestureFile"])
                
                instructions = active_task.get("instructions", "")
                writer.writerow([
                    self.participant_id,
                    start_time_unix,
                    end_time_unix,
                    task_id,
                    task_name,
                    instructions,
                    presentation_order,
                    backup_filename
                ])
            self.logger.info(f"Logged task {presentation_order} metrics to {log_path}")
        except Exception as e:
            self.logger.error(f"Failed to write participant study log: {e}")

        # 3. Transition to next task
        self.current_task_index += 1
        if self.current_task_index < len(self.tasks):
            self.task_start_time = time.time()
            self._update_current_task_filepath()
            next_task = self.get_active_task()
            return False, next_task
        else:
            # Study completed! Archive log file
            pid_dir = os.path.join("study_results", f"{self.participant_id}-{self.session_creation_timestamp}")
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
        """Loads study tasks from study_referents.json, creating a default file if missing."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base_dir, "config", "study_referents.json")
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
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(default_tasks, f, indent=2, ensure_ascii=False)
                self.logger.info("Created default study_referents.json configuration file.")
                return default_tasks
            except Exception as e:
                self.logger.error(f"Failed to write default study_referents.json: {e}")
                return default_tasks
        else:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    tasks = json.load(f)
                self.logger.info(f"Successfully loaded {len(tasks)} tasks from study_referents.json.")
                return tasks
            except Exception as e:
                self.logger.error(f"Failed to read study_referents.json: {e}. Using defaults.")
                return default_tasks

    def _load_or_create_tutorials(self):
        """Loads tutorial tasks from study_tutorials.json, creating a default file if missing."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base_dir, "config", "study_tutorials.json")
        default_tutorials = [
            {
                "id": 101,
                "name": "Tutorial 1: Greifer testen (Test Gripper)",
                "instructions": "Öffne und schließe den Greifer des Roboters mehrmals.\nGewöhne dich an die Steuerung."
            },
            {
                "id": 102,
                "name": "Tutorial 2: Einfache Bewegung (Simple Movement)",
                "instructions": "Bewege den Roboterarm ein kleines Stück nach oben und wieder zurück."
            }
        ]
        
        if not os.path.exists(path):
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(default_tutorials, f, indent=2, ensure_ascii=False)
                self.logger.info("Created default study_tutorials.json configuration file.")
                return default_tutorials
            except Exception as e:
                self.logger.error(f"Failed to write default study_tutorials.json: {e}")
                return default_tutorials
        else:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    tutorials = json.load(f)
                self.logger.info(f"Successfully loaded {len(tutorials)} tutorials from study_tutorials.json.")
                return tutorials
            except Exception as e:
                self.logger.error(f"Failed to read study_tutorials.json: {e}. Using defaults.")
                return default_tutorials

    def _generate_balanced_latin_square_order(self, pid_int, n_tasks):
        """
        Generates a balanced Latin Square sequence.
        Requires N to be even.
        """  
        # Sequence generator:
        col = []
        left = 0
        right = n_tasks - 1
        for j in range(n_tasks):
            if j % 2 == 0:
                col.append(left)
                left += 1
            else:
                col.append(right)
                right -= 1
                
        # Offset based on 0-indexed PID
        participant_index = (pid_int - 1) % n_tasks
        
        order = []
        for j in range(n_tasks):
            val = (participant_index + col[j]) % n_tasks
            order.append(val)
            
        return order
