import tkinter as tk
import re
from view import theme

class ConnectionDialog(tk.Toplevel):
    """Blocking popup dialog that requests IP and Credentials on startup, styled with the dark flat theme."""
    def __init__(self, parent, default_ip="", default_user="", default_pass=""):
        super().__init__(parent)
        self.title("Robot Connection")
        self.resizable(False, False)
        self.configure(bg=theme.BG_CARD)

        self.result = None

        self.ip_var = tk.StringVar(value=default_ip)
        self.user_var = tk.StringVar(value=default_user)
        self.pass_var = tk.StringVar(value=default_pass)
        self.pid_var = tk.StringVar(value="")

        self.ip_var.trace_add("write", self.validate_inputs)
        self.user_var.trace_add("write", self.validate_inputs)
        self.pass_var.trace_add("write", self.validate_inputs)

        # Main header Label
        tk.Label(self, text="Enter Kinova Robot Credentials", font=theme.FONT_TITLE, bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY).pack(pady=(20, 15))

        # Inputs Fields
        tk.Label(self, text="IP Address:", font=theme.FONT_NORMAL, bg=theme.BG_CARD, fg=theme.TEXT_MUTED).pack(pady=(5, 2))
        self.ent_ip = tk.Entry(self, width=28, justify="center", textvariable=self.ip_var, font=theme.FONT_MONO)
        self.ent_ip.pack()
        theme.apply_entry_theme(self.ent_ip)

        tk.Label(self, text="Username:", font=theme.FONT_NORMAL, bg=theme.BG_CARD, fg=theme.TEXT_MUTED).pack(pady=(8, 2))
        self.ent_user = tk.Entry(self, width=28, justify="center", textvariable=self.user_var, font=theme.FONT_NORMAL)
        self.ent_user.pack()
        theme.apply_entry_theme(self.ent_user)

        tk.Label(self, text="Password:", font=theme.FONT_NORMAL, bg=theme.BG_CARD, fg=theme.TEXT_MUTED).pack(pady=(8, 2))
        self.ent_pass = tk.Entry(self, width=28, justify="center", show="*", textvariable=self.pass_var, font=theme.FONT_NORMAL)
        self.ent_pass.pack()
        theme.apply_entry_theme(self.ent_pass)

        tk.Label(self, text="Participant ID (Optional):", font=theme.FONT_NORMAL, bg=theme.BG_CARD, fg=theme.TEXT_MUTED).pack(pady=(8, 2))
        self.ent_pid = tk.Entry(self, width=28, justify="center", textvariable=self.pid_var, font=theme.FONT_NORMAL)
        self.ent_pid.pack()
        theme.apply_entry_theme(self.ent_pid)

        # Action Buttons
        btn_frame = tk.Frame(self, bg=theme.BG_CARD)
        btn_frame.pack(pady=25)
        
        self.btn_connect = theme.make_flat_button(
            btn_frame, text="Connect", bg_color=theme.ACCENT_GREEN, 
            fg_color=theme.BG_MAIN, hover_bg="#059669", width=12, pady=6
        )
        self.btn_connect.pack(side="left", padx=10)
        
        btn_cancel = theme.make_flat_button(
            btn_frame, text="Cancel", bg_color=theme.BG_INPUT, 
            fg_color=theme.TEXT_PRIMARY, hover_bg=theme.BORDER_COLOR, 
            width=12, pady=6, command=self.on_cancel
        )
        btn_cancel.pack(side="left", padx=10)

        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

        self.validate_inputs()

        self.update_idletasks() 
        width = self.winfo_reqwidth() + 40
        height = self.winfo_reqheight() + 20
        self.geometry(f"{width}x{height}")
        
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'+{x}+{y}') 
        self.grab_set()

    def validate_inputs(self, *args):
        """Enables the Connect button only if inputs match valid IP format."""
        ip = self.ip_var.get().strip()
        user = self.user_var.get().strip()
        pwd = self.pass_var.get().strip()

        all_filled = bool(ip and user and pwd)

        is_valid_ip = False
        ip_pattern = r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$"
        if re.match(ip_pattern, ip):
            is_valid_ip = all(0 <= int(part) <= 255 for part in ip.split('.'))

        if all_filled and is_valid_ip:
            self.btn_connect.config(state=tk.NORMAL, bg=theme.ACCENT_GREEN, fg=theme.BG_MAIN, cursor="hand2")
            self.btn_connect.bind("<Button-1>", lambda e: self.on_connect())
            self.btn_connect.bind("<Enter>", lambda e: self.btn_connect.config(bg="#059669"))
            self.btn_connect.bind("<Leave>", lambda e: self.btn_connect.config(bg=theme.ACCENT_GREEN))
        else:
            self.btn_connect.config(state=tk.DISABLED, bg=theme.BORDER_COLOR, fg=theme.TEXT_MUTED, cursor="arrow")
            self.btn_connect.unbind("<Button-1>")
            self.btn_connect.unbind("<Enter>")
            self.btn_connect.unbind("<Leave>")

    def on_connect(self):
        """Commits the user input and closes the dialog."""
        self.result = (
            self.ip_var.get().strip(), 
            self.user_var.get().strip(), 
            self.pass_var.get().strip(),
            self.pid_var.get().strip()
        )
        self.destroy()

    def on_cancel(self):
        """Destroys the dialog upon cancellation."""
        self.destroy()
