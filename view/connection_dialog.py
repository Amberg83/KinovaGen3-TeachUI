import tkinter as tk
import re
from view import theme

class ConnectionDialog(tk.Toplevel):
    """Blocking popup dialog that requests IP and Credentials on startup, styled with the dark flat theme."""
    def __init__(self, parent, default_ip="", default_user="", default_pass=""):
        super().__init__(parent)
        self.title("Kinova Gen3 Dashboard Setup")
        self.resizable(False, False)
        self.configure(bg=theme.BG_MAIN)

        self.result = None

        self.ip_var = tk.StringVar(value=default_ip)
        self.user_var = tk.StringVar(value=default_user)
        self.pass_var = tk.StringVar(value=default_pass)
        self.pid_var = tk.StringVar(value="")

        self.ip_var.trace_add("write", self.validate_inputs)
        self.user_var.trace_add("write", self.validate_inputs)
        self.pass_var.trace_add("write", self.validate_inputs)

        # ----------------- HEADER AREA -----------------
        header_frame = tk.Frame(self, bg=theme.BG_HEADER, pady=18)
        header_frame.pack(fill="x")
        
        # Tech Title with Cyber Teal accent
        tk.Label(
            header_frame, text="KINOVA DASHBOARD", 
            font=theme.FONT_TITLE, bg=theme.BG_HEADER, fg=theme.ACCENT_CYBER
        ).pack()
        
        # Subtitle
        tk.Label(
            header_frame, text="Configure connection & study credentials", 
            font=(theme.FONT_NORMAL[0], 9, "normal"), bg=theme.BG_HEADER, fg=theme.TEXT_MUTED
        ).pack(pady=(2, 0))

        # Horizontal accent division line
        divider = tk.Frame(self, height=2, bg=theme.ACCENT_CYBER)
        divider.pack(fill="x")

        # ----------------- BODY/INPUT AREA -----------------
        body_frame = tk.Frame(self, bg=theme.BG_MAIN, padx=30, pady=20)
        body_frame.pack(fill="both", expand=True)

        # Styled container card for inputs
        card = tk.Frame(
            body_frame, bg=theme.BG_CARD, padx=20, pady=20, 
            highlightbackground=theme.BORDER_COLOR, highlightthickness=1
        )
        card.pack(fill="both", expand=True)

        # Helper to create inputs
        def build_field(parent, label_text, text_var, is_password=False, is_mono=False):
            # Muted, small uppercase labels for high-end cyber look
            tk.Label(
                parent, text=label_text.upper(), 
                font=(theme.FONT_NORMAL[0], 8, "bold"), bg=theme.BG_CARD, fg=theme.TEXT_MUTED
            ).pack(anchor="w", pady=(10, 3))
            
            ent_font = theme.FONT_MONO if is_mono else theme.FONT_NORMAL
            entry = tk.Entry(
                parent, width=32, justify="center", textvariable=text_var, 
                show="*" if is_password else "", font=ent_font
            )
            entry.pack(fill="x", ipady=3)
            theme.apply_entry_theme(entry)
            return entry

        self.ent_ip = build_field(card, "IP Address (IPv4)", self.ip_var, is_mono=True)
        self.ent_user = build_field(card, "Operator Username", self.user_var)
        self.ent_pass = build_field(card, "Session Password", self.pass_var, is_password=True)
        self.ent_pid = build_field(card, "User Study ID (Optional)", self.pid_var)

        # Helpful notice badge
        notice_frame = tk.Frame(
            card, bg=theme.BG_INPUT, padx=10, pady=8,
            highlightbackground=theme.BORDER_COLOR, highlightthickness=1
        )
        notice_frame.pack(fill="x", pady=(15, 0))
        
        tk.Label(
            notice_frame, text="💡 Leave Participant ID empty to launch in Expert Mode.",
            font=(theme.FONT_NORMAL[0], 8, "normal"), bg=theme.BG_INPUT, fg=theme.TEXT_MUTED,
            wraplength=220, justify="left"
        ).pack(fill="x")

        # ----------------- ACTION BUTTONS -----------------
        btn_frame = tk.Frame(self, bg=theme.BG_MAIN, pady=15)
        btn_frame.pack(fill="x")
        
        self.btn_connect = theme.make_flat_button(
            btn_frame, text="Connect", bg_color=theme.ACCENT_GREEN, 
            fg_color=theme.BG_MAIN, hover_bg="#059669", width=14, pady=8
        )
        self.btn_connect.pack(side="left", padx=(30, 10), fill="x", expand=True)
        
        btn_cancel = theme.make_flat_button(
            btn_frame, text="Cancel", bg_color=theme.BG_INPUT, 
            fg_color=theme.TEXT_PRIMARY, hover_bg=theme.BORDER_COLOR, 
            width=14, pady=8, command=self.on_cancel
        )
        btn_cancel.pack(side="left", padx=(10, 30), fill="x", expand=True)

        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

        self.validate_inputs()

        # Update window geometry dynamically based on requested sizes
        self.update_idletasks() 
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        self.geometry(f"{width}x{height}")
        
        # Position exactly at screen center
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
