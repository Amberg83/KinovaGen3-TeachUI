import os
import csv
import json
import time
import re
import threading
import logging
from datetime import datetime
from utils.event_bus import EventBus
from utils.sound_manager import play_chime

logger = logging.getLogger("ReplayAllManager")

class ReplayAllManager:
    """
    Orchestrates automated batch replay ('Replay All') across all participant session folders in study_results/.
    
    Key Features:
    - Automatically discovers session folders, excluding any PIDs specified in exclude_pids.
    - Filters out tutorial tasks (RID > 100), keeping only experimental referents (RID <= 100).
    - Groups gestures chronologically per (PID, RID) and assigns version letters (P1_R1_A, P1_R1_B, ...).
    - Groups execution sequentially by Referent ID (RID 1, RID 2, ...).
    - Requires manual startup for each RID, displaying full setup instructions and description in ReplayAllView.
    - Triggers an initial 'Clapperboard' emergency sound right when the very first gesture starts.
    - Executes a 3-step pre-gesture reset sequence (5s wait -> move_to_default -> 5s wait) before every gesture.
    - Logs high-precision, FFmpeg-ready timestamps (Start/End) to study_results/replay_all_log_<timestamp>.csv.
    - Plays the fault mode sound when all referents have finished playing across the entire study.
    """
    def __init__(self, controller, exclude_pids=""):
        self.controller = controller
        self.exclude_pids_raw = exclude_pids
        self.exclude_pids = self._parse_exclude_pids(exclude_pids)
        
        self.rids = []               # Sorted list of discovered RIDs (<= 100)
        self.gestures_by_rid = {}    # rid -> list of gesture dicts
        self.total_gestures = 0
        
        self.current_r_idx = 0
        self.current_g_idx = 0
        
        self.is_running = False
        self.is_paused = True
        self.is_waiting_for_referent_start = True
        self._worker_thread = None
        
        self.csv_file_path = None
        self.start_time_epoch = time.time()
        
        # Load referents metadata (name, instructions, default_pose, default_gripper_pos)
        self.referents_map = self._load_referents_map()
        self.view = None             # Set when ReplayAllView initializes

    def _parse_exclude_pids(self, raw_str):
        if not raw_str:
            return set()
        tokens = [t.strip().lower() for t in re.split(r'[,;\s]+', raw_str) if t.strip()]
        result = set(tokens)
        # Also add integer equivalents or 'pX' equivalents for robust matching
        for t in list(result):
            if t.isdigit():
                result.add(f"p{t}")
            elif t.startswith("p") and t[1:].isdigit():
                result.add(t[1:])
        return result

    def _load_referents_map(self):
        ref_map = {}
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            path = os.path.join(base_dir, "config", "study_referents.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    tasks = json.load(f)
                    for t in tasks:
                        rid = int(t.get("id", 0))
                        if rid > 0:
                            ref_map[rid] = t
        except Exception as e:
            logger.error(f"Error loading study_referents.json in ReplayAllManager: {e}")
        return ref_map

    def set_view(self, view):
        self.view = view

    def scan_and_prepare(self):
        """Scans study_results/, filters out tutorials and excluded PIDs, and builds the playback queue."""
        study_results_dir = "study_results"
        if not os.path.isdir(study_results_dir):
            logger.error(f"Directory '{study_results_dir}' not found.")
            return

        discovered_by_pid_rid = {}  # (pid_str, rid) -> list of (filepath, mtime)

        # Walk through study_results/ to find session folders (e.g., "1-1781695201" or "Participants/1-...")
        for root, dirs, files in os.walk(study_results_dir):
            # Check if this folder looks like a session directory containing gesture JSONs or study_log CSVs
            has_gestures = any(f.endswith(".json") and f.startswith("task_") for f in files)
            has_csv = any(f.startswith("study_log-") and f.endswith(".csv") for f in files)
            if not (has_gestures or has_csv):
                continue

            folder_name = os.path.basename(root)
            # Extract PID from folder name (e.g. "1-1781695201" -> "1", "P12-..." -> "12")
            pid_match = re.match(r'^([a-zA-Z]*[0-9]+)', folder_name)
            pid_str = pid_match.group(1).lower() if pid_match else folder_name.lower()
            if pid_str.startswith("p") and pid_str[1:].isdigit():
                pid_clean = pid_str[1:]
            else:
                pid_clean = pid_str

            # Check exclusions
            if pid_str in self.exclude_pids or pid_clean in self.exclude_pids or f"p{pid_clean}" in self.exclude_pids:
                logger.info(f"Skipping excluded session folder: {root} (PID: {pid_clean})")
                continue

            # First check study_log CSV if available to map gestures
            csv_files = [os.path.join(root, f) for f in files if f.startswith("study_log-") and f.endswith(".csv")]
            seen_files = set()
            if csv_files:
                for csv_p in csv_files:
                    try:
                        with open(csv_p, "r", encoding="utf-8") as f:
                            reader = csv.DictReader(f)
                            for row in reader:
                                rid_str = str(row.get("ID") or row.get("RID") or row.get("rid") or "0").strip()
                                if not rid_str.isdigit():
                                    continue
                                rid = int(rid_str)
                                # STRICT FILTER: Skip tutorials (RID > 100)
                                if rid <= 0 or rid > 100:
                                    continue
                                g_file = (row.get("gesture_file") or row.get("GestureFile") or "").strip()
                                if g_file:
                                    full_g_path = os.path.join(root, g_file)
                                    if os.path.exists(full_g_path):
                                        key = (pid_clean, rid)
                                        if key not in discovered_by_pid_rid:
                                            discovered_by_pid_rid[key] = []
                                        discovered_by_pid_rid[key].append((full_g_path, os.path.getmtime(full_g_path)))
                                        seen_files.add(os.path.abspath(full_g_path))
                    except Exception as e:
                        logger.warning(f"Could not read study_log CSV '{csv_p}': {e}")

            # Also scan for any task_<RID>_<timestamp>.json files inside root not covered by CSV
            for f in files:
                if f.startswith("task_") and f.endswith(".json"):
                    full_p = os.path.abspath(os.path.join(root, f))
                    if full_p in seen_files:
                        continue
                    # Parse RID from filename (e.g. task_3_1781695201.json -> RID=3)
                    m = re.match(r'^task_(\d+)_\d+\.json$', f)
                    if m:
                        rid = int(m.group(1))
                        # STRICT FILTER: Skip tutorials (RID > 100)
                        if rid <= 0 or rid > 100:
                            continue
                        key = (pid_clean, rid)
                        if key not in discovered_by_pid_rid:
                            discovered_by_pid_rid[key] = []
                        discovered_by_pid_rid[key].append((full_p, os.path.getmtime(full_p)))
                        seen_files.add(full_p)

        # Build Versioned Gestures map grouped by RID
        self.gestures_by_rid.clear()
        for (pid_clean, rid), file_list in discovered_by_pid_rid.items():
            # Sort chronologically
            file_list.sort(key=lambda x: x[1])
            for idx, (fpath, _) in enumerate(file_list):
                version_letter = chr(ord('A') + idx) if idx < 26 else f"Z{idx}"
                item_id = f"P{pid_clean}_R{rid}_{version_letter}"
                
                # Look up default pose / gripper from referents_map
                ref_info = self.referents_map.get(rid, {})
                def_pose = ref_info.get("default_pose", [0.0, 70.0, 264.0, 0.0, 58.0, 90.0])
                def_gripper = ref_info.get("default_gripper_pos", "pickup")
                
                if rid not in self.gestures_by_rid:
                    self.gestures_by_rid[rid] = []
                self.gestures_by_rid[rid].append({
                    "id": item_id,
                    "pid": pid_clean,
                    "rid": rid,
                    "version": version_letter,
                    "filepath": fpath,
                    "default_pose": def_pose,
                    "default_gripper_pos": def_gripper
                })

        # Sort RIDs ascending
        self.rids = sorted(self.gestures_by_rid.keys())
        # Sort gestures within each RID cleanly by (numeric PID, version)
        for rid in self.rids:
            self.gestures_by_rid[rid].sort(key=lambda g: (int(g["pid"]) if g["pid"].isdigit() else g["pid"], g["version"]))

        self.total_gestures = sum(len(v) for v in self.gestures_by_rid.values())
        logger.info(f"ReplayAll scan complete. Found {len(self.rids)} referents ({self.rids}) and {self.total_gestures} total experimental gestures.")

    def start(self):
        """Initializes the Replay All sequence, creates the CSV log, and sets up initial prompt for RID 1."""
        self.scan_and_prepare()
        if not self.rids:
            logger.error("No valid experimental gestures found in study_results/.")
            if self.view:
                self.view.update_status(phase="No experimental gestures found (RID <= 100)", progress=0.0, counter_str="0 / 0")
            return

        # Create high-precision FFmpeg-ready CSV log file
        os.makedirs("study_results", exist_ok=True)
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.csv_file_path = os.path.join("study_results", f"replay_all_log_{timestamp_str}.csv")
        try:
            with open(self.csv_file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "Event", "Timestamp", "FormattedTime", "ElapsedSeconds"])
            logger.info(f"Created Replay All CSV log: {self.csv_file_path}")
        except Exception as e:
            logger.error(f"Error creating Replay All CSV log: {e}")

        self.start_time_epoch = time.time()
        self.current_r_idx = 0
        self.current_g_idx = 0
        self.is_running = False
        self.is_paused = True
        self.is_waiting_for_referent_start = True

        self._update_view_for_referent_prompt()

    def _update_view_for_referent_prompt(self):
        """Updates ReplayAllView to display instructions for the current RID and wait for operator confirmation."""
        if not self.view or self.current_r_idx >= len(self.rids):
            return
        current_rid = self.rids[self.current_r_idx]
        ref_info = self.referents_map.get(current_rid, {})
        ref_name = ref_info.get("name", f"Referent {current_rid}")
        ref_instructions = ref_info.get("instructions", "Please arrange the physical environment for this referent.")
        
        # Calculate overall gesture index
        completed_before = sum(len(self.gestures_by_rid[self.rids[i]]) for i in range(self.current_r_idx))
        progress_pct = (completed_before / max(1, self.total_gestures)) * 100.0
        
        self.view.show_referent_prompt(
            rid=current_rid,
            name=ref_name,
            instructions=ref_instructions,
            phase=f"Ready for Referent R{current_rid}. Press [ Start Referent R{current_rid} ] after physical setup.",
            progress=progress_pct,
            counter_str=f"{completed_before} / {self.total_gestures} completed ({progress_pct:.1f}%)"
        )

    def start_referent(self):
        """Called when the operator presses the [ Start Referent R<rid> ] button after physical setup."""
        if not self.is_waiting_for_referent_start or self.current_r_idx >= len(self.rids):
            return
        
        self.is_waiting_for_referent_start = False
        self.is_paused = False
        self.is_running = True

        # Check if this is the VERY FIRST gesture across the entire Replay All run
        is_very_first = (self.current_r_idx == 0 and self.current_g_idx == 0)
        if is_very_first:
            logger.info("Triggering initial clapperboard emergency sound at start of very first referent!")
            try:
                play_chime("fault")
                EventBus.publish("fault")
            except Exception as e:
                logger.error(f"Error playing initial clapperboard sound: {e}")

        # Start pre-gesture sequence worker thread
        self._worker_thread = threading.Thread(target=self._pre_gesture_worker, daemon=True)
        self._worker_thread.start()

    def _pre_gesture_worker(self):
        """Worker thread that executes the 5s pre-reset -> move_to_default -> 5s post-reset timing."""
        if not self.is_running or self.is_paused:
            return
        
        current_rid = self.rids[self.current_r_idx]
        entry = self.gestures_by_rid[current_rid][self.current_g_idx]
        
        completed_before = sum(len(self.gestures_by_rid[self.rids[i]]) for i in range(self.current_r_idx)) + self.current_g_idx
        progress_pct = (completed_before / max(1, self.total_gestures)) * 100.0
        counter_str = f"Clip {completed_before + 1} of {self.total_gestures} ({progress_pct:.1f}%) — {entry['id']}"

        # 1. Wait 5.0 seconds (NOT logged to CSV)
        logger.info(f"[{entry['id']}] Stage 1: Waiting 5.0s pre-reset pause...")
        if self.view:
            self.controller.root.after(0, lambda: self.view.update_status(
                phase=f"Stage 1/3: Waiting 5.0s Pre-Reset Pause ({entry['id']})...",
                progress=progress_pct, counter_str=counter_str, active_gesture=entry
            ))
        if not self._sleep_interruptible(5.0):
            return

        # 2. Move to Default Pose (NOT logged to CSV)
        logger.info(f"[{entry['id']}] Stage 2: Moving robot to default pose...")
        if self.view:
            self.controller.root.after(0, lambda: self.view.update_status(
                phase=f"Stage 2/3: Homing to Default Pose ({entry['id']})...",
                progress=progress_pct, counter_str=counter_str, active_gesture=entry
            ))
        try:
            completion_event = self.controller.hardware.move_to_default(
                custom_pose=entry["default_pose"],
                custom_gripper_pos=entry["default_gripper_pos"]
            )
            if completion_event:
                completion_event.wait(timeout=18.0)
        except Exception as e:
            logger.error(f"Error during move_to_default in ReplayAll: {e}")
            if not self.is_running or self.is_paused:
                return

        # 3. Wait another 5.0 seconds (NOT logged to CSV)
        logger.info(f"[{entry['id']}] Stage 3: Waiting 5.0s post-reset pause...")
        if self.view:
            self.controller.root.after(0, lambda: self.view.update_status(
                phase=f"Stage 3/3: Waiting 5.0s Post-Reset Pause ({entry['id']})...",
                progress=progress_pct, counter_str=counter_str, active_gesture=entry
            ))
        if not self._sleep_interruptible(5.0):
            return

        # 4. Schedule CSV Start Log & Replay Engine launch on main thread
        if self.is_running and not self.is_paused:
            self.controller.root.after(0, lambda: self._launch_physical_gesture(entry, progress_pct, counter_str))

    def _sleep_interruptible(self, duration):
        """Sleeps in 0.1s increments, returning False if paused or stopped."""
        steps = int(duration * 10)
        for _ in range(steps):
            if not self.is_running or self.is_paused:
                return False
            time.sleep(0.1)
        return True

    def _launch_physical_gesture(self, entry, progress_pct, counter_str):
        """Logs Start to CSV and launches the ReplayEngine with skip_pre_default=True."""
        if not self.is_running or self.is_paused:
            return
        
        now = time.time()
        formatted = datetime.fromtimestamp(now).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        elapsed = round(now - self.start_time_epoch, 3)
        
        # Write Start row to CSV
        if self.csv_file_path:
            try:
                with open(self.csv_file_path, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([entry["id"], "Start", f"{now:.3f}", formatted, elapsed])
            except Exception as e:
                logger.error(f"Error logging Start event to CSV: {e}")

        logger.info(f"[{entry['id']}] Replay Started at {formatted} (Epoch: {now:.3f})")
        if self.view:
            self.view.update_status(
                phase=f"Replaying Spoken Gesture: {entry['id']} ({entry['version']})...",
                progress=progress_pct, counter_str=counter_str, active_gesture=entry
            )

        # Load waypoints into controller model
        try:
            self.controller.model.load_from_json(entry["filepath"])
        except Exception as e:
            logger.error(f"Error loading gesture file '{entry['filepath']}': {e}")
            self.controller.root.after(100, self._on_gesture_finished)
            return

        # Launch replay engine on controller, skipping built-in default movement
        self.controller.replay_engine.start(
            self.controller.model.waypoints,
            on_finished_callback=lambda: self.controller.root.after(0, self._on_gesture_finished),
            skip_pre_default=True
        )

    def _on_gesture_finished(self):
        """Handles physical gesture completion, logs End timestamp, and schedules next gesture or referent pause."""
        if not self.is_running:
            return
        
        current_rid = self.rids[self.current_r_idx]
        entry = self.gestures_by_rid[current_rid][self.current_g_idx]
        
        now = time.time()
        formatted = datetime.fromtimestamp(now).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        elapsed = round(now - self.start_time_epoch, 3)
        
        # Write End row to CSV
        if self.csv_file_path:
            try:
                with open(self.csv_file_path, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([entry["id"], "End", f"{now:.3f}", formatted, elapsed])
            except Exception as e:
                logger.error(f"Error logging End event to CSV: {e}")

        logger.info(f"[{entry['id']}] Replay Finished at {formatted} (Epoch: {now:.3f})")

        # Advance gesture index
        self.current_g_idx += 1
        if self.current_g_idx < len(self.gestures_by_rid[current_rid]):
            # More gestures left for this same RID -> start pre-gesture sequence (5s -> reset -> 5s)
            self._worker_thread = threading.Thread(target=self._pre_gesture_worker, daemon=True)
            self._worker_thread.start()
        else:
            # All gestures for current RID completed! Advance to next RID
            self.current_r_idx += 1
            self.current_g_idx = 0
            
            if self.current_r_idx < len(self.rids):
                # Programmatic Stop for Setup Readjustment!
                logger.info(f"Completed all gestures for RID {current_rid}. Pausing for setup readjustment.")
                self.is_paused = True
                self.is_waiting_for_referent_start = True
                self._update_view_for_referent_prompt()
            else:
                # ALL RIDs FINISHED! Replay All Completed Across Entire Study!
                logger.info("Replay All completed successfully across all referents.")
                self.is_running = False
                self.is_paused = True
                self.is_waiting_for_referent_start = False
                
                if self.view:
                    self.view.show_completion_screen(total_gestures=self.total_gestures)
                
                # Play unmistakable fault mode sound upon full study completion
                try:
                    play_chime("fault")
                    EventBus.publish("fault")
                except Exception as e:
                    logger.error(f"Error playing completion fault sound: {e}")

    def pause(self):
        """Pauses active playback between gestures or interrupts current sequence."""
        self.is_paused = True
        self.controller.replay_engine.stop()
        logger.info("Replay All paused by operator.")
        if self.view:
            self.view.update_status(phase="Replay Paused by Operator.")

    def resume(self):
        """Resumes active playback or triggers referent start if waiting."""
        if self.is_waiting_for_referent_start:
            self.start_referent()
        elif self.is_paused and self.is_running:
            self.is_paused = False
            self._worker_thread = threading.Thread(target=self._pre_gesture_worker, daemon=True)
            self._worker_thread.start()

    def stop(self):
        """Aborts Replay All entirely."""
        self.is_running = False
        self.is_paused = True
        self.is_waiting_for_referent_start = False
        self.controller.replay_engine.stop()
        logger.info("Replay All aborted by operator.")
        if self.view:
            self.view.update_status(phase="Replay All Aborted.")

    def skip_gesture(self):
        """Skips the currently active gesture and immediately advances."""
        if not self.is_running:
            return
        logger.info("Skipping current gesture by operator request.")
        self.controller.replay_engine.stop()
        self.controller.root.after(100, self._on_gesture_finished)
