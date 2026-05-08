import sys
import os
import subprocess
import logging
import threading

logger = logging.getLogger("SoundManager")

# Apple iOS exclusive sound theme mapping
SOUND_THEME_MAP = {
    "captured": "photoShutter.mp3",
    "connected": "connect_power.mp3",
    "disconnected": "low_power.mp3",
    "fault": "3rdParty_Failure_Haptic.mp3",    # 3rd party failure haptic for non-intrusive fault sound
    "fault_cleared": "3rdParty_Success_Haptic.mp3", # Paired success haptic when faults are cleared
    "replay_start": "begin_record.mp3",
    "replay_finished": "end_record.mp3",
    "admittance_enable": "SentMessage.mp3",   # Classic iOS "swoosh" wind sweep when manual guiding is enabled
    "admittance_disable": "ReceivedMessage.mp3", # Classic iOS note/chime when manual guiding is disabled
    "task_completed": "payment_success.mp3",  # Apple Pay double success ding on study task completion
    "waypoint_saved": "lock.mp3",              # Mechanical slide-lock click when waypoint edits are saved
    "estop": "3rd_party_critical.mp3",         # High priority critical alarm siren on emergency stop
    "delete": "Tock.mp3",                      # Wood pop click on deleting waypoint(s)
    "undo": "key_press_click.mp3",             # Soft keyboard tap on Undo
    "redo": "key_press_click.mp3",             # Soft keyboard tap on Redo
    "move_up": "Tock.mp3",                     # Wood pop click for row reordering
    "move_down": "Tock.mp3",                   # Wood pop click for row reordering
    "move_entry": "Tock.mp3"                   # Wood pop click when waypoints are drag-n-drop reordered
}

def play_chime(event_type, block=False):
    """
    Plays a pre-defined Apple iOS MP3 chime file cross-platform.
    Supports Windows (native MCI ctypes), macOS (native afplay), and Linux (paplay/mpg123).
    If block=True, waits until the sound completes before returning (useful during shutdown).
    """
    filename = SOUND_THEME_MAP.get(event_type)
    if not filename:
        return

    # Build absolute path to the sounds directory (relative to workspace root)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sound_path = os.path.join(base_dir, "sounds", "apple", filename)

    if not os.path.exists(sound_path):
        logger.warning(f"Sound file not found: {sound_path}. Falling back to system bell.")
        sys.stdout.write("\a")
        sys.stdout.flush()
        return

    def play_worker():
        try:
            # First Priority: High-performance, low-latency miniaudio engine
            try:
                import miniaudio
                import time
                stream = miniaudio.stream_file(sound_path)
                with miniaudio.PlaybackDevice() as device:
                    device.start(stream)
                    # Adjust sleep duration so short disconnection cues complete faster (2s) than other cues (4s)
                    duration = 2.0 if event_type == "disconnected" else 4.0
                    time.sleep(duration)
                return
            except ImportError:
                pass

            # Second Priority: Platform-specific native fallbacks
            if sys.platform.startswith("win"):
                import ctypes
                winmm = ctypes.windll.winmm
                # Close previous instance to avoid file locks
                winmm.mciSendStringW('close teachui_mp3', None, 0, 0)
                # Open and play via Windows Media Control Interface (MCI)
                open_cmd = f'open "{sound_path}" type mpegvideo alias teachui_mp3'
                err_open = winmm.mciSendStringW(open_cmd, None, 0, 0)
                err_play = 0
                if err_open == 0:
                    play_cmd = 'play teachui_mp3 wait' if block else 'play teachui_mp3'
                    err_play = winmm.mciSendStringW(play_cmd, None, 0, 0)
                
                # If MCI failed to open or play (e.g. system is missing MPEGvideo codecs),
                # fall back to a headless PowerShell WPF MediaPlayer instance.
                if err_open != 0 or err_play != 0:
                    sleep_s = 2 if event_type == "disconnected" else 5
                    ps_cmd = (
                        f"[Void][Reflection.Assembly]::LoadWithPartialName('PresentationCore'); "
                        f"$player = New-Object System.Windows.Media.MediaPlayer; "
                        f"$player.Open('{sound_path}'); "
                        f"$player.Play(); "
                        f"Start-Sleep -s {sleep_s}"
                    )
                    if block:
                        subprocess.run(
                            ["powershell", "-NoProfile", "-Command", ps_cmd],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                    else:
                        subprocess.Popen(
                            ["powershell", "-NoProfile", "-Command", ps_cmd],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
            elif sys.platform == "darwin":
                # macOS natively plays MP3 using afplay
                cmd = ["afplay", sound_path]
                if block:
                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                # Linux MP3 playback using PulseAudio or common command-line players
                try:
                    cmd = ["paplay", sound_path]
                    if block:
                        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    else:
                        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    try:
                        cmd = ["mpg123", "-q", sound_path]
                        if block:
                            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        else:
                            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except FileNotFoundError:
                        sys.stdout.write("\a")
                        sys.stdout.flush()
        except Exception as e:
            logger.debug(f"Audio playback error: {e}")

    if block:
        play_worker()
    else:
        # Run asynchronously in a background thread
        threading.Thread(target=play_worker, daemon=True).start()
