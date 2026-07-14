#!/usr/bin/env python3
"""
Study Video Audio Extraction, Transcription & Task Segmentation Script
-----------------------------------------------------------------------
Designed to be placed inside any folder containing:
  1) Recorded video files (e.g. PID.mov, 1.mov, 12.mp4)
  2) The 'study_results/' directory containing session subfolders and CSV study logs:
     study_results/<PID>-<timestamp>/study_log-<PID>-<timestamp>.csv

Workflow per video file:
  1. Identifies the Participant ID (PID) from the filename.
  2. Locates the corresponding study log CSV in 'study_results/'.
  3. Extracts audio from the video and transcribes it automatically using Whisper
     (supports faster-whisper or openai-whisper) with segment timestamps.
     Saves the transcript to JSON so it never has to re-transcribe if run again.
  4. Uses fuzzy sequence matching between transcribed audio segments and the task
     descriptions ('instructions' and 'name' from CSV) read out loud during the session.
  5. Determines precise video start and end timestamps for each task.
  6. Automatically cuts the video into individual task files: PID-task.mov
"""

import os
import sys
import csv
import json
import time
import re
import difflib
import argparse
import subprocess
from pathlib import Path

if os.name == 'nt':
    os.system("")  # Enable VT100 ANSI terminal formatting in Windows console


_TIMERS = {"workflow_start": None, "current_stage": None, "stage_start": None}


def format_time(seconds):
    secs = int(seconds)
    mins = secs // 60
    s = secs % 60
    if mins >= 60:
        hrs = mins // 60
        m = mins % 60
        return f"{hrs:02d}:{m:02d}:{s:02d}"
    return f"{mins:02d}:{s:02d}"


def format_bar(pct, width=22):
    pct = max(0.0, min(100.0, float(pct)))
    filled = int(width * pct / 100.0)
    return "█" * filled + "░" * (width - filled)


def print_progress(stage_name, stage_pct, stage_detail, total_pct, total_detail):
    """Prints a 2-line live progress display with time counters behind each bar."""
    now = time.time()
    if _TIMERS["workflow_start"] is None:
        _TIMERS["workflow_start"] = now
    if _TIMERS["current_stage"] != stage_name or _TIMERS["stage_start"] is None:
        _TIMERS["current_stage"] = stage_name
        _TIMERS["stage_start"] = now

    stage_elapsed = format_time(now - _TIMERS["stage_start"])
    total_elapsed = format_time(now - _TIMERS["workflow_start"])

    stage_bar = format_bar(stage_pct, 20)
    total_bar = format_bar(total_pct, 20)
    
    line1 = f"  -> Current: |{stage_bar}| {stage_pct:5.1f}% [{stage_elapsed}] | {stage_name}: {stage_detail}"
    line2 = f"  => TOTAL:   |{total_bar}| {total_pct:5.1f}% [{total_elapsed}] | {total_detail}"
    
    line1 = line1.ljust(98)[:98]
    line2 = line2.ljust(98)[:98]
    
    print(f"\r{line1}\n{line2}\033[1A\r", end="", flush=True)


def finish_progress():
    """Moves cursor past the 2-line progress block."""
    print("\n\n", end="", flush=True)


def get_ffmpeg_exe():
    """Locates a valid ffmpeg executable on PATH or via imageio_ffmpeg."""
    try:
        res = subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode == 0:
            return "ffmpeg"
    except Exception:
        pass

    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except ImportError:
        pass

    return None


def check_whisper_available():
    """Checks for faster-whisper or openai-whisper."""
    try:
        import faster_whisper
        return "faster_whisper"
    except ImportError:
        pass

    try:
        import whisper
        return "whisper"
    except ImportError:
        pass

    return None


def extract_pid_from_filename(filename):
    """
    Extracts Participant ID from video filename.
    Examples: '1.mov' -> '1', 'PID12_recording.mov' -> '12', 'participant_05.mp4' -> '05'
    """
    stem = Path(filename).stem
    # Try exact number first (e.g. '1', '12')
    if stem.isdigit():
        return stem
    
    # Try matching 'PID-' or 'P' followed by numbers
    match = re.search(r'(?:pid|participant|p)?[-_ ]*(\d+)', stem, re.IGNORECASE)
    if match:
        return match.group(1)
    
    return stem


def find_study_csv_for_pid(pid, base_dir="."):
    """
    Locates the newest study_log CSV file for the given PID inside study_results/.
    """
    results_dir = Path(base_dir) / "study_results"
    if not results_dir.exists():
        return None

    candidate_csvs = []
    # Strict matching: session folder must start with PID- and CSV must be named study_log-PID-timestamp.csv
    for subfolder in results_dir.iterdir():
        if subfolder.is_dir():
            folder_name = subfolder.name
            parts = folder_name.split("-")
            # Strict PID equality check
            if parts[0] == str(pid):
                for f in subfolder.glob(f"study_log-{pid}-*.csv"):
                    candidate_csvs.append(f)

    if not candidate_csvs:
        # Recursive exact search across study_results/ for study_log-{pid}-*.csv
        for f in results_dir.rglob(f"study_log-{pid}-*.csv"):
            candidate_csvs.append(f)

    if candidate_csvs:
        def get_row_count(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return sum(1 for line in f if line.strip())
            except Exception:
                return 0

        # Return the CSV with the most tasks (highest non-empty row count), breaking ties by newest timestamp
        candidate_csvs.sort(key=lambda x: (get_row_count(x), x.stat().st_mtime), reverse=True)
        return candidate_csvs[0]

    return None


def parse_tasks_from_csv(csv_path):
    """
    Parses the study tasks from the CSV file sorted by presentation_order.
    Returns list of dicts: [{'id': ..., 'name': ..., 'instructions': ..., 'order': ...}, ...]
    """
    tasks = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [n.strip() for n in reader.fieldnames] if reader.fieldnames else []
        for row in reader:
            tid = (row.get("id") or row.get("RID") or row.get("rid") or "").strip()
            name = (row.get("name") or row.get("RName") or row.get("rname") or "").strip()
            instructions = (row.get("instructions") or row.get("RInstructions") or row.get("rinstructions") or "").strip()
            order_str = (row.get("presentation_order") or row.get("PresentationOrder") or row.get("presentationorder") or "0").strip()
            order = int(order_str) if order_str.isdigit() else len(tasks) + 1
            
            if not name and not instructions:
                continue

            tasks.append({
                "id": tid,
                "name": name,
                "instructions": instructions,
                "presentation_order": order
            })

    tasks.sort(key=lambda x: x["presentation_order"])
    return tasks


def extract_audio_from_video(ffmpeg_exe, video_path, audio_out_path):
    """Extracts 16kHz mono WAV audio from video file for speech recognition."""
    cmd = [
        ffmpeg_exe, "-y",
        "-i", str(video_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(audio_out_path)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def transcribe_audio(audio_path, whisper_backend, model_size="medium", progress_cb=None):
    """
    Transcribes audio using Whisper and returns segment timestamps.
    Returns list of {'start': float, 'end': float, 'text': str}
    """
    segments_data = []

    if whisper_backend == "faster_whisper":
        from faster_whisper import WhisperModel
        print(f"  [Whisper] Loading faster-whisper '{model_size}' model...")
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments, info = model.transcribe(str(audio_path), beam_size=5, language="en")
        total_dur = getattr(info, "duration", 0.0)
        start_t = time.time()
        
        for seg in segments:
            segments_data.append({
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": seg.text.strip()
            })
            if total_dur > 0:
                pct = min(100.0, (seg.end / total_dur) * 100.0)
                if progress_cb:
                    progress_cb("Transcription", pct, f"{seg.end:6.1f}s / {total_dur:6.1f}s")
                else:
                    bar = format_bar(pct, 25)
                    print(f"\r  [Whisper] Transcribing: |{bar}| {pct:5.1f}% [{format_time(time.time() - start_t)}] ({seg.end:6.1f}s / {total_dur:6.1f}s)", end="", flush=True)
        if not progress_cb:
            print("\r" + " " * 85 + "\r", end="")
        print(f"  [Whisper] Transcription completed in {time.time() - start_t:.1f}s ({len(segments_data)} segments).")
    elif whisper_backend == "whisper":
        import whisper
        print(f"  [Whisper] Loading openai-whisper '{model_size}' model...")
        model = whisper.load_model(model_size)
        print("  [Whisper] Transcribing audio (openai-whisper running)...")
        start_t = time.time()
        res = model.transcribe(str(audio_path), language="en", verbose=False)
        for seg in res.get("segments", []):
            segments_data.append({
                "start": round(seg["start"], 2),
                "end": round(seg["end"], 2),
                "text": seg["text"].strip()
            })
        print(f"  [Whisper] Transcription completed in {time.time() - start_t:.1f}s ({len(segments_data)} segments).")

    return segments_data


def get_video_duration(ffmpeg_exe, video_path):
    """Gets total video duration in seconds using ffprobe or ffmpeg."""
    ffprobe_exe = ffmpeg_exe.replace("ffmpeg", "ffprobe") if "ffmpeg" in ffmpeg_exe else "ffprobe"
    try:
        cmd = [
            ffprobe_exe, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0 and res.stdout.strip():
            return float(res.stdout.strip())
    except Exception:
        pass

    return 99999.0


BOILERPLATE_WORDS = {
    "imagine", "you", "are", "at", "home", "in", "the", "kitchen", "room",
    "collaboratively", "assembling", "something", "together", "with", "another",
    "person", "while", "working", "doing", "else", "other", "persons", "how",
    "would", "show", "signal", "notify", "them", "that", "not", "and", "for",
    "from", "your", "shared", "when", "they", "on", "to", "of", "a", "is",
    "it", "if", "were", "look", "looking", "direction", "position", "same",
    "there", "have", "can", "could", "been", "was", "has", "this", "these"
}


def normalize_text(text):
    """Normalizes text for fuzzy matching."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    return ' '.join(text.split())


def align_tasks_to_transcript(tasks, segments, video_duration, progress_cb=None):
    """
    Aligns each task from the CSV to timestamped speech segments using strict forward sequential search
    matched exclusively against distinctive non-boilerplate content of task descriptions ('instructions').
    """
    aligned_tasks = []
    curr_search_time = 0.0

    # Build sliding windows of transcribed speech (~ 15-20 seconds window)
    windows = []
    for i in range(len(segments)):
        chunk_segs = []
        for s in segments[i:]:
            chunk_segs.append(s)
            if s["end"] - segments[i]["start"] > 25.0:
                break
        if not chunk_segs:
            continue
        text_chunk = " ".join([s["text"] for s in chunk_segs])
        windows.append({
            "start": chunk_segs[0]["start"],
            "end": chunk_segs[-1]["end"],
            "norm_text": normalize_text(text_chunk),
            "raw_text": text_chunk
        })

    for idx, task in enumerate(tasks):
        norm_inst = normalize_text(task["instructions"])
        if not norm_inst:
            norm_inst = normalize_text(task["name"])
        
        # Extract distinctive keywords excluding standard boilerplate scenario introductions
        task_keywords = set(w for w in norm_inst.split() if len(w) >= 4 and w not in BOILERPLATE_WORDS)
        if not task_keywords:
            task_keywords = set(w for w in norm_inst.split() if len(w) >= 4)
        name_keywords = set(w for w in normalize_text(task["name"]).split() if len(w) >= 3 and w not in BOILERPLATE_WORDS)
        all_keywords = task_keywords.union(name_keywords)

        clean_inst = " ".join([w for w in norm_inst.split() if w not in BOILERPLATE_WORDS])

        best_score = 0.0
        best_time = curr_search_time
        best_match_text = ""

        # Search forward sequentially within a 15-minute horizon for the peak match of distinctive keywords
        for w in windows:
            if w["start"] < curr_search_time - 1.0:
                continue
            if w["start"] > curr_search_time + 900.0:  # 15 min max forward horizon per task start
                break

            window_words = set(w["norm_text"].split())
            keyword_hits = len(all_keywords.intersection(window_words))
            keyword_score = keyword_hits / max(1, len(all_keywords)) if all_keywords else 0.0

            clean_win = " ".join([w_word for w_word in w["norm_text"].split() if w_word not in BOILERPLATE_WORDS])
            clean_ratio = difflib.SequenceMatcher(None, clean_inst, clean_win).ratio() if clean_inst else 0.0

            score = max(keyword_score, clean_ratio)
            
            if score > best_score:
                best_score = score
                best_time = w["start"]
                best_match_text = w["raw_text"][:80] + "..."

        if best_score > 0.25:
            start_cut = max(0.0, best_time - 1.5)  # Cut just before description is said out loud
            curr_search_time = best_time + 120.0  # Jump 2 mins forward to cleanly skip reading and task setup
        else:
            start_cut = curr_search_time
            curr_search_time = curr_search_time + 120.0  # Fallback advancement if unreadable

        aligned_tasks.append({
            "pid": task.get("pid", ""),
            "id": task["id"],
            "name": task["name"],
            "order": task["presentation_order"],
            "start_time": round(start_cut, 2),
            "end_time": 0.0,
            "match_score": round(best_score, 2),
            "matched_text": best_match_text
        })

        if progress_cb:
            pct = ((idx + 1) / len(tasks)) * 100.0
            progress_cb("Task Alignment", pct, f"Matched task {idx+1}/{len(tasks)}: {task['name'][:20]}")

    # Set end times based on the start of the next task
    for i in range(len(aligned_tasks) - 1):
        aligned_tasks[i]["end_time"] = max(aligned_tasks[i]["start_time"] + 2.0, aligned_tasks[i+1]["start_time"] - 0.5)

    if aligned_tasks:
        aligned_tasks[-1]["end_time"] = round(video_duration, 2)

    return aligned_tasks


def cut_video_segment(ffmpeg_exe, input_video, output_video, start_time, end_time, reencode=False):
    """Cuts video from start_time to end_time."""
    duration = end_time - start_time
    if duration <= 0:
        return False

    if not reencode:
        # Fast stream copy
        cmd = [
            ffmpeg_exe, "-y",
            "-ss", str(start_time),
            "-i", str(input_video),
            "-t", str(duration),
            "-c", "copy",
            str(output_video)
        ]
    else:
        # Sample-accurate re-encoding
        cmd = [
            ffmpeg_exe, "-y",
            "-ss", str(start_time),
            "-i", str(input_video),
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac",
            str(output_video)
        ]

    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return res.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Extract audio, transcribe, and cut study videos into tasks.")
    parser.add_argument("--dir", default=".", help="Directory containing video files and study_results/")
    parser.add_argument("--video", default=None, help="Process only a specific video file (e.g. 1.mov or path/to/video.mp4)")
    parser.add_argument("--model", default="medium", help="Whisper model size (tiny, base, small, medium)")
    parser.add_argument("--reencode", action="store_true", help="Re-encode video cuts for exact frame accuracy instead of fast copy")
    args = parser.parse_args()

    work_dir = Path(args.dir).resolve()
    print("=" * 90)
    print("STUDY VIDEO AUDIO EXTRACTION, TRANSCRIPTION & TASK SEGMENTATION")
    print("=" * 90)
    print(f"Working Directory: {work_dir}")

    ffmpeg_exe = get_ffmpeg_exe()
    if not ffmpeg_exe:
        print("\n[ERROR] ffmpeg executable not found!")
        print("Please install ffmpeg or run: pip install imageio-ffmpeg")
        sys.exit(1)

    whisper_backend = check_whisper_available()
    if not whisper_backend:
        print("\n[ERROR] No Whisper speech recognition package found!")
        print("Please install faster-whisper (recommended) or openai-whisper:")
        print("  pip install faster-whisper")
        sys.exit(1)

    print(f"Using FFmpeg: {ffmpeg_exe}")
    print(f"Using Whisper Backend: {whisper_backend} (model: {args.model})")

    # Find video files
    if args.video:
        target_vid = Path(args.video)
        if not target_vid.is_absolute():
            target_vid = work_dir / target_vid
        if not target_vid.exists():
            print(f"\n[ERROR] Specified video file '{target_vid}' does not exist!")
            sys.exit(1)
        videos = [target_vid]
    else:
        video_exts = {".mov", ".mp4", ".mkv", ".avi"}
        videos = [f for f in work_dir.iterdir() if f.suffix.lower() in video_exts and not f.name.startswith(".")]

    if not videos:
        print(f"\n[WARN] No video files found in {work_dir}.")
        sys.exit(0)

    print(f"\nFound {len(videos)} video file(s) to process.")

    for vid_idx, vid_path in enumerate(videos, 1):
        print("\n" + "-" * 80)
        print(f"[{vid_idx}/{len(videos)}] Processing Video: {vid_path.name}")
        print("-" * 80)

        pid = extract_pid_from_filename(vid_path.name)
        print(f"  -> Extracted Participant ID (PID): '{pid}'")

        csv_path = find_study_csv_for_pid(pid, work_dir)
        if not csv_path:
            print(f"  [WARN] Could not find study log CSV for PID '{pid}' inside study_results/. Skipping video.")
            continue

        print(f"  -> Matched Study Log CSV: {csv_path.name}")
        tasks = parse_tasks_from_csv(csv_path)
        print(f"  -> Parsed {len(tasks)} tasks ordered by presentation sequence.")

        # Create master folder for this participant's PID
        pid_dir = work_dir / str(pid)
        pid_dir.mkdir(exist_ok=True)
        print(f"  -> Output directory for PID '{pid}': {pid_dir.name}/")

        # Audio Extraction & Transcription
        transcript_json = pid_dir / f"{pid}_full_transcript.json"
        legacy_transcript = work_dir / f"{vid_path.stem}_transcript.json"
        audio_wav = pid_dir / f"{pid}_temp_audio.wav"

        total_vids = len(videos)
        base_pct = ((vid_idx - 1) / total_vids) * 100.0
        vid_share = 100.0 / total_vids

        if transcript_json.exists():
            print(f"  -> Found existing transcript: {transcript_json.name}. Loading segments...")
            with open(transcript_json, "r", encoding="utf-8") as f:
                segments = json.load(f)
        elif legacy_transcript.exists():
            print(f"  -> Found existing transcript: {legacy_transcript.name}. Loading segments...")
            with open(legacy_transcript, "r", encoding="utf-8") as f:
                segments = json.load(f)
        else:
            print("  -> Extracting audio track...")
            print_progress("Audio Extraction", 50.0, "Running ffmpeg audio extraction...", base_pct + vid_share * 0.05, f"Video {vid_idx}/{total_vids} (PID {pid})")
            extract_audio_from_video(ffmpeg_exe, vid_path, audio_wav)
            finish_progress()

            print("  -> Running automatic speech transcription...")
            def tx_cb(stage, pct, detail):
                total_p = base_pct + vid_share * (0.05 + 0.65 * (pct / 100.0))
                print_progress(stage, pct, detail, total_p, f"Video {vid_idx}/{total_vids} (PID {pid})")

            segments = transcribe_audio(audio_wav, whisper_backend, args.model, progress_cb=tx_cb)
            finish_progress()
            
            # Save transcript JSON & readable text inside pid_dir
            with open(transcript_json, "w", encoding="utf-8") as f:
                json.dump(segments, f, indent=2, ensure_ascii=False)
            
            txt_path = pid_dir / f"{pid}_full_transcript.txt"
            with open(txt_path, "w", encoding="utf-8") as f:
                for seg in segments:
                    f.write(f"[{seg['start']:6.2f}s -> {seg['end']:6.2f}s] {seg['text']}\n")
            
            print(f"  -> Saved full transcript to {pid_dir.name}/{transcript_json.name}")
            if audio_wav.exists():
                audio_wav.unlink()

        video_duration = get_video_duration(ffmpeg_exe, vid_path)
        print(f"  -> Video Duration: {video_duration:.2f} seconds")

        # Align Tasks to Audio Timestamps
        print("  -> Aligning task descriptions from CSV to spoken audio segments...")
        def align_cb(stage, pct, detail):
            total_p = base_pct + vid_share * (0.70 + 0.10 * (pct / 100.0))
            print_progress(stage, pct, detail, total_p, f"Video {vid_idx}/{total_vids} (PID {pid})")

        aligned_tasks = align_tasks_to_transcript(tasks, segments, video_duration, progress_cb=align_cb)
        finish_progress()

        # Output alignment table
        print("\n  TASK SEGMENTATION SUMMARY:")
        print(f"  {'Order':<6} | {'Task Name':<25} | {'Start (s)':<10} | {'End (s)':<10} | {'Match Score':<12}")
        print("  " + "-" * 72)
        for t in aligned_tasks:
            print(f"  {t['order']:<6} | {t['name']:<25} | {t['start_time']:<10.2f} | {t['end_time']:<10.2f} | {t['match_score']:<12.2f}")
        print("  " + "-" * 72)

        # Cut Video into Individual Tasks inside pid_dir
        print(f"\n  -> Cutting video segments into folder: {pid_dir.name}/")

        for idx, t in enumerate(aligned_tasks, 1):
            clean_name = re.sub(r'[\\/*?:"<>|]', "", t["name"]).strip()
            out_filename = f"{pid}-{clean_name}.mov"
            out_path = pid_dir / out_filename

            pct = (idx / len(aligned_tasks)) * 100.0
            total_p = base_pct + vid_share * (0.80 + 0.20 * (pct / 100.0))
            print_progress("Video Cutting", pct, f"Clip {idx}/{len(aligned_tasks)}: {out_filename[:20]}", total_p, f"Video {vid_idx}/{total_vids} (PID {pid})")

            success = cut_video_segment(ffmpeg_exe, vid_path, out_path, t["start_time"], t["end_time"], args.reencode)
            if success:
                snippet_txt_path = pid_dir / f"{pid}-{clean_name}_transcript.txt"
                snippet_json_path = pid_dir / f"{pid}-{clean_name}_transcript.json"
                
                snippet_segs = []
                with open(snippet_txt_path, "w", encoding="utf-8") as f_txt:
                    for seg in segments:
                        if seg["end"] > t["start_time"] and seg["start"] < t["end_time"]:
                            rel_start = max(0.0, round(seg["start"] - t["start_time"], 2))
                            rel_end = max(0.0, round(seg["end"] - t["start_time"], 2))
                            snippet_segs.append({"start": rel_start, "end": rel_end, "text": seg["text"]})
                            f_txt.write(f"[{rel_start:6.2f}s -> {rel_end:6.2f}s] {seg['text']}\n")
                with open(snippet_json_path, "w", encoding="utf-8") as f_json:
                    json.dump(snippet_segs, f_json, indent=2, ensure_ascii=False)
        finish_progress()

    print("\n" + "=" * 90)
    print("ALL VIDEOS PROCESSED SUCCESSFULLY!")
    print("=" * 90)


if __name__ == "__main__":
    main()
