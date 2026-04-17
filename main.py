import sys
import os
import json
import time
import logging
import tkinter as tk
from kinova_hardware import KinovaHardware
from model import SequenceModel
from view import RobotView, ConnectionDialog
from controller import RobotController

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "connection_config.json")

# ==========================================
# LOGGING HANDLER FÜR DIE GUI
# ==========================================
class UITextHandler(logging.Handler):
    """Leitet Log-Nachrichten thread-sicher in das Text-Widget der View um."""
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s', datefmt='%H:%M:%S')
        self.setFormatter(formatter)

    def emit(self, record):
        msg = self.format(record)
        level_tag = record.levelname # Stimmt exakt mit den Tags in deiner view.py überein ('INFO', 'ERROR'...)
        
        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, msg + '\n', level_tag)
            self.text_widget.configure(state='disabled')
            self.text_widget.see(tk.END)
            
        # after(0) garantiert die thread-sichere Ausführung in der Tkinter-Mainloop
        self.text_widget.after(0, append)

def setup_global_logging(view):
    """Konfiguriert das globale Logging in UI, Datei und Konsole."""
    os.makedirs("log", exist_ok=True)
    log_timestamp = time.strftime("%Y_%m_%d-%H_%M_%S")
    log_filepath = os.path.join("log", f"{log_timestamp}.log")

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # 1. UI Handler (Schreibt in deine Applikation)
    ui_handler = UITextHandler(view.log_area)
    root_logger.addHandler(ui_handler)

    # 2. File Handler (Schreibt in die .log Datei)
    file_formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # 3. Console Handler (Schreibt in dein Terminal/IDE)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(file_formatter)
    root_logger.addHandler(console_handler)

# --- Config Helpers ---
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load config: {e}")
    return {"ip": "", "username": "", "password": ""}

def save_config(ip, username, password):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump({"ip": ip, "username": username, "password": password}, f, indent=4)
    except Exception as e:
        print(f"Failed to save config: {e}")


def main():
    root = tk.Tk()
    root.withdraw() 
    
    config = load_config()
    
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
    root.deiconify() 
    
    # MVC Setup
    view = RobotView(root)
    
    # WICHTIG: Logging aufsetzen, sobald die View da ist!
    setup_global_logging(view)
    
    hardware = KinovaHardware(ip=ip, username=username, password=password)
    model = SequenceModel()
    controller = RobotController(root, view, model, hardware)
    
    def on_closing():
        logging.getLogger("Main").info("Closing application...")
        hardware.disconnect()
        root.destroy()
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()