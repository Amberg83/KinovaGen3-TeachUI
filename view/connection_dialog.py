import tkinter as tk
import customtkinter as ctk
import re
from view import theme

class ConnectionDialog(ctk.CTk):
    """Blocking standalone popup dialog that requests IP and Credentials on startup, styled with the dark flat theme."""
    def __init__(self, default_ip="", default_user="", default_pass=""):
        super().__init__()
        self.title("Kinova Gen3 Dashboard Setup")
        self.resizable(False, False)
        self.configure(fg_color=theme.BG_MAIN)

        self.result = None

        self.ip_var = ctk.StringVar(value=default_ip)
        self.user_var = ctk.StringVar(value=default_user)
        self.pass_var = ctk.StringVar(value=default_pass)
        self.pid_var = ctk.StringVar(value="")
        self.review_var = ctk.BooleanVar(value=False)
        self.replay_all_var = ctk.BooleanVar(value=False)
        self.exclude_pids_var = ctk.StringVar(value="")

        self.ip_var.trace_add("write", self.validate_inputs)
        self.user_var.trace_add("write", self.validate_inputs)
        self.pass_var.trace_add("write", self.validate_inputs)
        self.pid_var.trace_add("write", self.validate_pid_change)
        self.replay_all_var.trace_add("write", self.on_replay_all_change)

        # ----------------- HEADER AREA -----------------
        header_frame = ctk.CTkFrame(self, fg_color=theme.BG_HEADER, corner_radius=0)
        header_frame.pack(fill="x")
        
        # Tech Title with Cyber Teal accent
        theme.make_label(
            header_frame, text="KINOVA DASHBOARD", 
            font=(theme.FONT_TITLE[0], 15, "bold"), fg_color=theme.BG_HEADER, text_color=theme.ACCENT_CYBER
        ).pack(pady=(18, 0))
        
        # Subtitle
        theme.make_label(
            header_frame, text="Configure connection & study credentials", 
            font=(theme.FONT_NORMAL[0], 11, "normal"), fg_color=theme.BG_HEADER, text_color=theme.TEXT_MUTED
        ).pack(pady=(2, 18))

        # Horizontal accent division line
        divider = ctk.CTkFrame(self, height=2, fg_color=theme.ACCENT_CYBER, corner_radius=0)
        divider.pack(fill="x")

        # ----------------- BODY/INPUT AREA -----------------
        body_frame = ctk.CTkFrame(self, fg_color=theme.BG_MAIN, corner_radius=0)
        body_frame.pack(fill="both", expand=True, padx=30, pady=20)

        # Styled container card for inputs
        card = ctk.CTkFrame(
            body_frame, fg_color=theme.BG_CARD,
            border_color=theme.BORDER_COLOR, border_width=1, corner_radius=6
        )
        card.pack(fill="both", expand=True, padx=5, pady=5)

        # Helper to create inputs
        def build_field(parent, label_text, text_var, is_password=False, is_mono=False):
            # Muted, small uppercase labels for high-end cyber look
            theme.make_label(
                parent, text=label_text.upper(), 
                font=(theme.FONT_NORMAL[0], 8, "bold"), fg_color=theme.BG_CARD, text_color=theme.TEXT_MUTED
            ).pack(anchor="w", pady=(10, 3), padx=20)
            
            ent_font = theme.FONT_MONO if is_mono else theme.FONT_NORMAL
            entry = ctk.CTkEntry(
                parent, width=280, justify="center", textvariable=text_var, 
                show="*" if is_password else "", font=ent_font,
                fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY,
                border_color=theme.BORDER_COLOR, corner_radius=4,
                border_width=1, height=30
            )
            entry.pack(fill="x", padx=20, pady=(0, 10))
            return entry

        self.ent_ip = build_field(card, "IP Address (IPv4)", self.ip_var, is_mono=True)
        self.ent_user = build_field(card, "Operator Username", self.user_var)
        self.ent_pass = build_field(card, "Session Password", self.pass_var, is_password=True)
        self.ent_pid = build_field(card, "User Study ID (Optional)", self.pid_var)
        
        # Checkbox for review mode
        self.chk_review = ctk.CTkCheckBox(
            card, text="Review Mode (Single Participant)", variable=self.review_var,
            font=(theme.FONT_NORMAL[0], 9, "bold"), fg_color=theme.ACCENT_CYBER,
            text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER_COLOR,
            corner_radius=4, hover_color=theme.ACCENT_CYBER
        )
        self.chk_review.pack(anchor="w", padx=20, pady=(0, 8))
        self.chk_review.configure(state="disabled")

        # Checkbox for Replay All
        self.chk_replay_all = ctk.CTkCheckBox(
            card, text="Replay All (Automatic Study Replay)", variable=self.replay_all_var,
            font=(theme.FONT_NORMAL[0], 9, "bold"), fg_color=theme.ACCENT_GREEN,
            text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER_COLOR,
            corner_radius=4, hover_color=theme.ACCENT_GREEN
        )
        self.chk_replay_all.pack(anchor="w", padx=20, pady=(0, 10))

        # Exclude PIDs field (optional)
        self.ent_exclude_pids = build_field(card, "Exclude PIDs (Comma-separated, optional)", self.exclude_pids_var)

        # Helpful notice badge
        notice_frame = ctk.CTkFrame(
            card, fg_color=theme.BG_INPUT,
            border_color=theme.BORDER_COLOR, border_width=1, corner_radius=4
        )
        notice_frame.pack(fill="x", pady=15, padx=20)
        
        theme.make_label(
            notice_frame, text=" Leave Participant ID empty to launch in Expert Mode, or check Replay All for automated review.",
            image=theme.get_icon("lightbulb"), compound="left",
            font=(theme.FONT_NORMAL[0], 10, "normal"), fg_color=theme.BG_INPUT, text_color=theme.TEXT_MUTED,
            wraplength=280, justify="left"
        ).pack(side="left", padx=10, pady=8)

        # ----------------- ACTION BUTTONS -----------------
        btn_frame = ctk.CTkFrame(self, fg_color=theme.BG_MAIN, corner_radius=0)
        btn_frame.pack(fill="x", pady=(0, 15))
        
        self.btn_connect = theme.make_flat_button(
            btn_frame, text="Connect", bg_color=theme.ACCENT_GREEN, 
            fg_color=theme.BG_MAIN, hover_bg="#059669", command=self.on_connect
        )
        self.btn_connect.pack(side="left", padx=(30, 10), fill="x", expand=True)
        
        btn_cancel = theme.make_flat_button(
            btn_frame, text="Cancel", bg_color=theme.BG_INPUT, 
            fg_color=theme.TEXT_PRIMARY, hover_bg=theme.BORDER_COLOR, 
            command=self.on_cancel
        )
        btn_cancel.pack(side="left", padx=(10, 30), fill="x", expand=True)

        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

        self.validate_inputs()

        # Update window geometry dynamically based on requested sizes
        self.update_idletasks() 
        
        scale = self._get_window_scaling()
        
        # winfo_reqwidth() and winfo_reqheight() return physical (scaled) pixels.
        # We must divide them by the scaling factor to obtain the logical (unscaled) sizes.
        width_logical = int(self.winfo_reqwidth() / scale)
        height_logical = int(self.winfo_reqheight() / scale)
        
        # winfo_screenwidth() and winfo_screenheight() return logical screen sizes.
        screen_width_logical = self.winfo_screenwidth()
        screen_height_logical = self.winfo_screenheight()
        
        # Center the window in logical coordinates
        x = (screen_width_logical // 2) - (width_logical // 2)
        y = (screen_height_logical // 2) - (height_logical // 2)
        
        self.geometry(f"{width_logical}x{height_logical}+{x}+{y}")
        
        # Bring to front & capture focus
        self.focus_force()

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
        elif "mock" in ip.lower():
            is_valid_ip = True

        if all_filled and is_valid_ip:
            self.btn_connect.configure(state="normal", fg_color=theme.ACCENT_GREEN, text_color=theme.BG_MAIN)
        else:
            self.btn_connect.configure(state="disabled", fg_color=theme.BORDER_COLOR, text_color=theme.TEXT_MUTED)

    def on_replay_all_change(self, *args):
        """Disables Review Mode checkbox when Replay All is selected."""
        if self.replay_all_var.get():
            self.review_var.set(True)
            self.chk_review.configure(state="disabled")
            self.ent_pid.configure(state="disabled", fg_color=theme.BORDER_COLOR)
        else:
            self.ent_pid.configure(state="normal", fg_color=theme.BG_INPUT)
            self.validate_pid_change()
        self.validate_inputs()

    def validate_pid_change(self, *args):
        """Enables/Disables the Review Mode checkbox dynamically based on PID textbox content."""
        if self.replay_all_var.get():
            return
        pid = self.pid_var.get().strip()
        if pid:
            self.chk_review.configure(state="normal")
        else:
            self.review_var.set(False)
            self.chk_review.configure(state="disabled")

    def on_connect(self):
        """Commits the user input, performs review mode checks, and closes the dialog."""
        import os
        from tkinter import messagebox
        
        pid = self.pid_var.get().strip()
        is_review = self.review_var.get()
        is_replay_all = self.replay_all_var.get()
        exclude_pids = self.exclude_pids_var.get().strip()
        
        if is_review and not is_replay_all and pid:
            possible_path = os.path.join("study_results", pid)
            if not os.path.isdir(possible_path):
                messagebox.showerror(
                    "Session Folder Not Found", 
                    f"The specified session folder '{pid}' does not exist under 'study_results/'.\n\n"
                    "Please verify the folder name matches an existing participant directory."
                )
                return

        if is_replay_all:
            if not os.path.isdir("study_results"):
                messagebox.showerror(
                    "Study Results Not Found",
                    "The 'study_results/' directory does not exist in the project root."
                )
                return
                
        self.result = (
            self.ip_var.get().strip(), 
            self.user_var.get().strip(), 
            self.pass_var.get().strip(),
            pid,
            is_review,
            is_replay_all,
            exclude_pids
        )
        self.destroy()

    def on_cancel(self):
        """Destroys the dialog upon cancellation."""
        self.destroy()
