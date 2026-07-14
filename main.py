import sys
import os
import json
import time
import logging
import queue
import threading
import tkinter as tk
import customtkinter as ctk
from hardware import KinovaHardware, MockKinovaHardware
from model import SequenceModel
from view import RobotView, ConnectionDialog
from view.replay_all_view import ReplayAllView
from controller import RobotController
from utils.sound_coordinator import SoundCoordinator
from utils.udp_transmitter import UDPTransmitter
from view import theme

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config", "connection_config.json")

class UITextHandler(logging.Handler):
    """Routes log messages to Tkinter safely using a Queue to prevent freezes."""
    def __init__(self, text_widget: ctk.CTkTextbox, update_interval=100, max_lines=2000):
        super().__init__()
        self.text_widget = text_widget
        self.log_queue = queue.Queue()
        self.update_interval = update_interval
        self.max_lines = max_lines
        
        formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s', datefmt='%H:%M:%S')
        self.setFormatter(formatter)
        self.text_widget.after(self.update_interval, self.flush_queue)

    def emit(self, record):
        """Intercepts log records and pushes them to the queue."""
        msg = self.format(record)
        level_tag = record.levelname 
        self.log_queue.put((msg, level_tag))

    def flush_queue(self):
        """Bulk-inserts waiting logs into Tkinter and prunes old lines with classic terminal scroll behavior."""
        if not self.log_queue.empty():
            # Check scroll position before modifying the text
            y_range = self.text_widget.yview()
            is_at_bottom = len(y_range) == 2 and y_range[1] >= 0.99
            
            self.text_widget.configure(state='normal')
            
            while not self.log_queue.empty():
                try:
                    msg, level_tag = self.log_queue.get_nowait()
                    self.text_widget.insert(tk.END, msg + '\n', level_tag)
                except queue.Empty:
                    break
            
            current_lines = int(self.text_widget.index('end-1c').split('.')[0])
            if current_lines > self.max_lines:
                self.text_widget.delete('1.0', f'{current_lines - self.max_lines + 1}.0')
            
            self.text_widget.configure(state='disabled')
            
            # Auto-scroll to bottom only if the user was already at the bottom
            if is_at_bottom:
                self.text_widget.see(tk.END)
            
        self.text_widget.after(self.update_interval, self.flush_queue)


def setup_global_logging(view: RobotView):
    """Configures system logging for UI, File, and Console outputs."""
    os.makedirs("log", exist_ok=True)
    log_timestamp = str(int(time.time()))
    log_filepath = os.path.join("log", f"{log_timestamp}.log")

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO) 

    ui_handler = UITextHandler(view.log_area)
    ui_handler.setLevel(logging.INFO)
    root_logger.addHandler(ui_handler)

    file_formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(file_formatter)
    console_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)

def load_config():
    """Loads previously saved IP and credentials from JSON."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load config: {e}")
    return {"ip": "", "username": "", "password": ""}

def save_config(ip, username, password):
    """Saves current IP and credentials to JSON."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"ip": ip, "username": username, "password": password}, f, indent=4)
    except Exception as e:
        print(f"Failed to save config: {e}")

def main():
    """Application entry point: Prompts for connection and builds MVC structure."""
    os.makedirs(os.path.join(BASE_DIR, "config"), exist_ok=True)
    config = load_config()
    
    # Run setup login screen as standalone root CTk window
    dialog = ConnectionDialog(
        default_ip=config.get("ip", ""), 
        default_user=config.get("username", ""), 
        default_pass=config.get("password", "")
    )
    dialog.mainloop()
    
    if dialog.result is None:
        print("Connection cancelled by user. Shutting down.")
        sys.exit(0)
        
    if len(dialog.result) == 7:
        ip, username, password, participant_id, is_review_mode, is_replay_all, exclude_pids = dialog.result
    else:
        ip, username, password, participant_id, is_review_mode = dialog.result[:5]
        is_replay_all = False
        exclude_pids = ""
        
    save_config(ip, username, password)

    # Clear theme's icon cache to prevent _tkinter.TclError: image "pyimageX" doesn't exist
    # which is caused by recreating Tkinter root windows (ConnectionDialog -> Main Root)
    theme._icon_cache.clear()

    # Initialize main dashboard application root
    root = ctk.CTk()
    root.title("Kinova Gen3 TeachUI Dashboard" + (" — REPLAY ALL (EXPERT REVIEW)" if is_replay_all else ""))
    root.configure(fg_color=theme.BG_MAIN)
    
    scaling = root._get_window_scaling()
    theme.update_treeview_font_scaling(scaling)

    if "mock" in ip.lower():
        logging.getLogger("Main").info("Launching in OFFLINE SIMULATION (MOCK) Mode.")
        hardware = MockKinovaHardware(ip=ip, username=username, password=password)
    else:
        hardware = KinovaHardware(ip=ip, username=username, password=password)
    model = SequenceModel()
    
    if is_replay_all:
        view = ReplayAllView(root)
    else:
        view = RobotView(root)
    setup_global_logging(view)
    
    controller = RobotController(
        root, view, model, hardware, 
        participant_id=participant_id, 
        is_review_mode=is_review_mode,
        is_replay_all=is_replay_all,
        exclude_pids=exclude_pids
    )
    
    # Initialize the sound coordinator to listen to events and trigger audio feedback
    sound_coordinator = SoundCoordinator()
    
    # Initialize UDP transmitter to stream joint angles to Unity on port 5005
    udp_transmitter = UDPTransmitter()
    
    def on_closing():
        logging.getLogger("Main").info("Closing application...")
        # Hide the UI window immediately so the user sees it close instantly
        root.withdraw()
        root.destroy()

        # Start a background non-daemon thread to perform cleanup and disconnect the robot.
        # A non-daemon thread ensures the Python process remains alive until it finishes.
        def cleanup():
            try:
                udp_transmitter.close()
            except Exception as e:
                logging.getLogger("Main").error(f"Error during UDP cleanup: {e}")
            try:
                hardware.disconnect(block_sound=True)
            except Exception as e:
                logging.getLogger("Main").error(f"Error during hardware disconnect: {e}")
            logging.getLogger("Main").info("Cleanup complete. Process exiting.")

        cleanup_thread = threading.Thread(target=cleanup, daemon=False)
        cleanup_thread.start()
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()