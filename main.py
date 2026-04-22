import sys
import os
import json
import time
import logging
import queue
import tkinter as tk
from kinova_hardware import KinovaHardware
from model import SequenceModel
from view import RobotView, ConnectionDialog
from controller import RobotController

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "connection_config.json")

# ==========================================
# BUFFERED LOGGING HANDLER FOR TKINTER GUI
# ==========================================
class UITextHandler(logging.Handler):
    """
    Routes log messages to the Tkinter Text Widget safely.
    Uses a Queue and periodic flush to prevent UI freezes under heavy log loads.
    """
    def __init__(self, text_widget, update_interval=100, max_lines=2000):
        super().__init__()
        self.text_widget = text_widget
        self.log_queue = queue.Queue()
        self.update_interval = update_interval
        self.max_lines = max_lines
        
        formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s', datefmt='%H:%M:%S')
        self.setFormatter(formatter)
        
        # Start the periodic background loop
        self.text_widget.after(self.update_interval, self.flush_queue)

    def emit(self, record):
        msg = self.format(record)
        level_tag = record.levelname 
        self.log_queue.put((msg, level_tag))

    def flush_queue(self):
        if not self.log_queue.empty():
            self.text_widget.configure(state='normal')
            
            while not self.log_queue.empty():
                try:
                    msg, level_tag = self.log_queue.get_nowait()
                    self.text_widget.insert(tk.END, msg + '\n', level_tag)
                except queue.Empty:
                    break
            
            # Prune log to prevent memory overflow
            current_lines = int(self.text_widget.index('end-1c').split('.')[0])
            if current_lines > self.max_lines:
                self.text_widget.delete('1.0', f'{current_lines - self.max_lines + 1}.0')
            
            self.text_widget.configure(state='disabled')
            self.text_widget.see(tk.END)
            
        self.text_widget.after(self.update_interval, self.flush_queue)


def setup_global_logging(view):
    """Sets up unified logging for UI, file output, and the developer console."""
    os.makedirs("log", exist_ok=True)
    log_timestamp = time.strftime("%Y_%m_%d-%H_%M_%S")
    log_filepath = os.path.join("log", f"{log_timestamp}.log")

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO) 

    # UI Handler with Queue
    ui_handler = UITextHandler(view.log_area)
    ui_handler.setLevel(logging.INFO)
    root_logger.addHandler(ui_handler)

    # File Handler
    file_formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(file_formatter)
    console_handler.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)

# --- Config Helpers ---
def load_config():
    """Loads previous IP and login credentials from JSON."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load config: {e}")
    return {"ip": "", "username": "", "password": ""}

def save_config(ip, username, password):
    """Saves IP and login credentials to JSON."""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump({"ip": ip, "username": username, "password": password}, f, indent=4)
    except Exception as e:
        print(f"Failed to save config: {e}")


def main():
    """Application Entry Point."""
    root = tk.Tk()
    root.withdraw() # Hide main window until connected
    
    config = load_config()
    
    # Launch connection prompt
    dialog = ConnectionDialog(
        root, 
        default_ip=config.get("ip", ""), 
        default_user=config.get("username", ""), 
        default_pass=config.get("password", "")
    )
    root.wait_window(dialog)
    
    if dialog.result is None:
        print("Connection cancelled by user. Shutting down.")
        root.destroy()
        sys.exit(0)
        
    ip, username, password = dialog.result
    save_config(ip, username, password)
    root.deiconify() # Reveal main window
    
    # Assemble MVC Architecture
    view = RobotView(root)
    setup_global_logging(view)
    
    hardware = KinovaHardware(ip=ip, username=username, password=password)
    model = SequenceModel()
    
    # The controller connects them all
    controller = RobotController(root, view, model, hardware)
    
    def on_closing():
        logging.getLogger("Main").info("Closing application...")
        hardware.disconnect()
        root.destroy()
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()