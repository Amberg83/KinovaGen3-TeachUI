import os
import tkinter as tk
import customtkinter as ctk
from view import theme
from view.widgets import ToolTip

class ReplayAllView(ctk.CTkFrame):
    """
    Dedicated Study Replay Center GUI displayed when Replay All (is_replay_all=True) is activated.
    
    Provides:
    - Essential Robot Safety & Status Controls: E-STOP, Clear Faults, Reconnect, and Status Badges.
    - Prominent Setup Readjustment Area: Displays the exact referent instructions and requires manual start.
    - Live Replay Telemetry & Progress: Shows current gesture (P1_R1_A), active phase, and overall study progress.
    """
    def __init__(self, parent, controller=None, **kwargs):
        super().__init__(parent, fg_color=theme.BG_MAIN, corner_radius=0, **kwargs)
        self.parent = parent
        self.controller = controller
        self.commands = {}
        
        # Maximize the dashboard window dynamically (Windows + Linux cross-platform compliant)
        try:
            self.parent.state('zoomed')
        except Exception:
            try:
                self.parent.attributes('-zoomed', True)
            except Exception:
                pass
                
        self.setup_ui()
        self.pack(fill="both", expand=True)

    def bind_commands(self, commands: dict):
        """Binds view actions to controller/ReplayAllManager callbacks."""
        self.commands = commands
        if "reconnect" in commands:
            self.btn_reconnect.configure(command=commands["reconnect"])
        if "clear_faults" in commands:
            self.btn_clear_faults.configure(command=commands["clear_faults"])
        if "estop" in commands:
            self.btn_estop.configure(command=commands["estop"])
        if "start_referent" in commands:
            self.btn_start_referent.configure(command=commands["start_referent"])
        if "pause" in commands:
            self.btn_pause.configure(command=commands["pause"])
        if "resume" in commands:
            self.btn_resume.configure(command=commands["resume"])
        if "previous_gesture" in commands:
            self.btn_prev.configure(command=commands["previous_gesture"])
        if "restart_current_gesture" in commands:
            self.btn_restart.configure(command=commands["restart_current_gesture"])
        if "skip_gesture" in commands:
            self.btn_skip.configure(command=commands["skip_gesture"])
        if "stop" in commands:
            self.btn_abort.configure(command=commands["stop"])

    def setup_ui(self):
        # ================= 1. TOP SAFETY & STATUS HEADER =================
        header_frame = ctk.CTkFrame(self, fg_color=theme.BG_HEADER, height=64, corner_radius=0)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)

        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.pack(side="left", padx=20, pady=10)

        theme.make_label(
            title_box, text="AUTOMATED STUDY REPLAY CENTER (EXPERT REVIEW)",
            font=(theme.FONT_TITLE[0], 15, "bold"), fg_color="transparent", text_color=theme.ACCENT_CYBER
        ).pack(anchor="w")

        theme.make_label(
            title_box, text="Batch evaluating participant gestures with automated spacing and FFmpeg logging",
            font=(theme.FONT_NORMAL[0], 10, "normal"), fg_color="transparent", text_color=theme.TEXT_MUTED
        ).pack(anchor="w")

        # Right-side Safety Controls
        safety_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        safety_box.pack(side="right", padx=20, pady=10)

        self.lbl_robot_status = theme.make_label(
            safety_box, text="ROBOT ONLINE / READY", font=theme.FONT_BOLD,
            fg_color=theme.BG_CARD, text_color=theme.ACCENT_GREEN, padx=12, pady=4, corner_radius=4
        )
        self.lbl_robot_status.pack(side="left", padx=8)

        self.btn_reconnect = theme.make_flat_button(
            safety_box, text="Reconnect", bg_color=theme.BG_INPUT,
            fg_color=theme.TEXT_PRIMARY, hover_bg=theme.BORDER_COLOR, height=36
        )
        self.btn_reconnect.pack(side="left", padx=4)
        ToolTip(self.btn_reconnect, "Reconnect to Robot Hardware API")

        self.btn_clear_faults = theme.make_flat_button(
            safety_box, text="Clear Faults", bg_color=theme.ACCENT_GREEN,
            fg_color=theme.BG_MAIN, hover_bg="#059669", font_style=theme.FONT_BOLD, height=36
        )
        self.btn_clear_faults.pack(side="left", padx=4)
        ToolTip(self.btn_clear_faults, "Acknowledge and Clear Safety Faults")

        self.btn_estop = theme.make_flat_button(
            safety_box, text=" EMERGENCY STOP", image=theme.get_icon("estop"), compound="left",
            bg_color=theme.ACCENT_RED, fg_color=theme.TEXT_PRIMARY, hover_bg="#b91c1c",
            font_style=theme.FONT_BOLD, height=36, padx=15
        )
        self.btn_estop.pack(side="left", padx=4)
        ToolTip(self.btn_estop, "EMERGENCY STOP (Escape / F8)")

        # Divider line
        ctk.CTkFrame(self, height=2, fg_color=theme.ACCENT_CYBER, corner_radius=0).pack(fill="x")

        # ================= 2. CENTER REFERENT SETUP & INSTRUCTION CARD =================
        center_container = ctk.CTkFrame(self, fg_color=theme.BG_MAIN, corner_radius=0)
        center_container.pack(fill="both", expand=True, padx=30, pady=(20, 10))

        ref_card = ctk.CTkFrame(
            center_container, fg_color=theme.BG_CARD,
            border_color=theme.BORDER_COLOR, border_width=1, corner_radius=8
        )
        ref_card.pack(fill="both", expand=True, padx=5, pady=5)

        # Referent Card Header Banner
        self.lbl_setup_banner = theme.make_label(
            ref_card, text="SETUP READJUSTMENT REQUIRED: Verify physical study setup before starting.",
            font=(theme.FONT_TITLE[0], 12, "bold"), fg_color="#38bdf8", text_color="#0f172a",
            height=36, corner_radius=6
        )
        self.lbl_setup_banner.pack(fill="x", padx=15, pady=(15, 10))

        self.lbl_referent_title = theme.make_label(
            ref_card, text="Referent R1 — SS Direct", font=(theme.FONT_TITLE[0], 18, "bold"),
            fg_color="transparent", text_color=theme.TEXT_PRIMARY
        )
        self.lbl_referent_title.pack(anchor="w", padx=25, pady=(5, 5))

        theme.make_label(
            ref_card, text="STUDY TASK INSTRUCTIONS / OPERATOR SETUP PROMPT:",
            font=(theme.FONT_NORMAL[0], 9, "bold"), fg_color="transparent", text_color=theme.TEXT_MUTED
        ).pack(anchor="w", padx=25, pady=(5, 5))

        # Instructions text container with scrollbar just in case
        inst_box = ctk.CTkFrame(ref_card, fg_color=theme.BG_INPUT, border_color=theme.BORDER_COLOR, border_width=1, corner_radius=6)
        inst_box.pack(fill="both", expand=True, padx=25, pady=(0, 15))

        self.lbl_instructions = ctk.CTkLabel(
            inst_box, text="Imagine you are collaboratively assembling something together with another person...",
            font=(theme.FONT_NORMAL[0], 13, "normal"), text_color=theme.TEXT_PRIMARY,
            wraplength=850, justify="left", anchor="nw"
        )
        self.lbl_instructions.pack(fill="both", expand=True, padx=20, pady=20)

        # Prominent Start / Resume Referent Button
        btn_start_box = ctk.CTkFrame(ref_card, fg_color="transparent")
        btn_start_box.pack(fill="x", padx=25, pady=(0, 20))

        self.btn_start_referent = theme.make_flat_button(
            btn_start_box, text="Start Referent R1 (F5)",
            image=theme.get_icon("play", tint=theme.BG_MAIN), compound="left",
            bg_color=theme.ACCENT_GREEN, fg_color=theme.BG_MAIN, hover_bg="#059669",
            font_style=(theme.FONT_TITLE[0], 13, "bold"), height=48
        )
        self.btn_start_referent.pack(fill="x")
        ToolTip(self.btn_start_referent, "Verify physical setup and click to begin automated replay for this referent")

        # ================= 3. BOTTOM ACTIVE REPLAY & TELEMETRY PANEL =================
        bottom_container = ctk.CTkFrame(self, fg_color=theme.BG_MAIN, corner_radius=0, height=220)
        bottom_container.pack(fill="x", padx=30, pady=(0, 25))
        bottom_container.pack_propagate(False)

        status_card = ctk.CTkFrame(
            bottom_container, fg_color=theme.BG_CARD,
            border_color=theme.BORDER_COLOR, border_width=1, corner_radius=8
        )
        status_card.pack(fill="both", expand=True, padx=5, pady=5)

        # Split into left (current clip info) and right (progress & actions)
        left_box = ctk.CTkFrame(status_card, fg_color="transparent")
        left_box.pack(side="left", fill="both", expand=True, padx=20, pady=15)

        theme.make_label(
            left_box, text="CURRENT ACTIVE GESTURE TELEMETRY",
            font=(theme.FONT_NORMAL[0], 9, "bold"), fg_color="transparent", text_color=theme.TEXT_MUTED
        ).pack(anchor="w")

        self.lbl_clip_id = theme.make_label(
            left_box, text="Clip ID: -",
            font=(theme.FONT_TITLE[0], 14, "bold"), fg_color="transparent", text_color=theme.TEXT_PRIMARY
        )
        self.lbl_clip_id.pack(anchor="w", pady=(4, 2))

        self.lbl_clip_path = theme.make_label(
            left_box, text="File: -",
            font=theme.FONT_MONO_SMALL, fg_color="transparent", text_color=theme.TEXT_MUTED
        )
        self.lbl_clip_path.pack(anchor="w", pady=(0, 10))

        self.lbl_phase = theme.make_label(
            left_box, text="Phase: Waiting for operator to confirm setup and press Start...",
            font=(theme.FONT_NORMAL[0], 12, "bold"), fg_color=theme.BG_INPUT, text_color=theme.ACCENT_CYBER,
            padx=15, pady=6, corner_radius=4
        )
        self.lbl_phase.pack(anchor="w", fill="x")

        # Right side: Progress bar and action toolbar
        right_box = ctk.CTkFrame(status_card, fg_color="transparent", width=420)
        right_box.pack(side="right", fill="both", padx=20, pady=15)
        right_box.pack_propagate(False)

        theme.make_label(
            right_box, text="OVERALL STUDY REPLAY PROGRESS",
            font=(theme.FONT_NORMAL[0], 9, "bold"), fg_color="transparent", text_color=theme.TEXT_MUTED
        ).pack(anchor="w")

        self.lbl_progress_counter = theme.make_label(
            right_box, text="0 / 0 completed (0.0%)",
            font=(theme.FONT_TITLE[0], 12, "bold"), fg_color="transparent", text_color=theme.TEXT_PRIMARY
        )
        self.lbl_progress_counter.pack(anchor="w", pady=(4, 6))

        self.progress_bar = ctk.CTkProgressBar(
            right_box, height=14, corner_radius=7, fg_color=theme.BG_INPUT, progress_color=theme.ACCENT_CYBER
        )
        self.progress_bar.pack(fill="x", pady=(0, 15))
        self.progress_bar.set(0.0)

        # Controls row 1: Playback & Navigation
        ctrl_row_1 = ctk.CTkFrame(right_box, fg_color="transparent")
        ctrl_row_1.pack(fill="x", pady=(0, 6))

        self.btn_prev = theme.make_flat_button(
            ctrl_row_1, text="◄ Previous Clip", bg_color=theme.BG_INPUT,
            fg_color=theme.TEXT_PRIMARY, hover_bg=theme.BORDER_COLOR, height=34
        )
        self.btn_prev.pack(side="left", fill="x", expand=True, padx=(0, 2))
        ToolTip(self.btn_prev, "Halt and go back to previous clip (clears Start/End CSV entries of current & previous)")

        self.btn_pause = theme.make_flat_button(
            ctrl_row_1, text="Pause (F7)", bg_color=theme.BG_INPUT,
            fg_color=theme.TEXT_PRIMARY, hover_bg=theme.BORDER_COLOR, height=34
        )
        self.btn_pause.pack(side="left", fill="x", expand=True, padx=2)
        ToolTip(self.btn_pause, "Pause active playback between gestures")

        self.btn_resume = theme.make_flat_button(
            ctrl_row_1, text="Resume (F5)", bg_color=theme.BG_INPUT,
            fg_color=theme.TEXT_PRIMARY, hover_bg=theme.BORDER_COLOR, height=34
        )
        self.btn_resume.pack(side="left", fill="x", expand=True, padx=2)
        ToolTip(self.btn_resume, "Resume playback / Start current referent")

        self.btn_skip = theme.make_flat_button(
            ctrl_row_1, text="Skip Clip ►", bg_color=theme.BG_INPUT,
            fg_color=theme.TEXT_PRIMARY, hover_bg=theme.BORDER_COLOR, height=34
        )
        self.btn_skip.pack(side="left", fill="x", expand=True, padx=(2, 0))
        ToolTip(self.btn_skip, "Skip active clip without replaying")

        # Controls row 2: Halt & Restart / Abort
        ctrl_row_2 = ctk.CTkFrame(right_box, fg_color="transparent")
        ctrl_row_2.pack(fill="x")

        self.btn_restart = theme.make_flat_button(
            ctrl_row_2, text="↺ Halt & Restart Current (F6)", bg_color="#d97706",
            fg_color=theme.TEXT_PRIMARY, hover_bg="#b45309", font_style=theme.FONT_BOLD, height=34
        )
        self.btn_restart.pack(side="left", fill="x", expand=True, padx=(0, 4))
        ToolTip(self.btn_restart, "Manually halt and restart current clip from beginning (clears Start/End CSV entries)")

        self.btn_abort = theme.make_flat_button(
            ctrl_row_2, text="Abort Replay", bg_color=theme.ACCENT_RED,
            fg_color=theme.TEXT_PRIMARY, hover_bg="#b91c1c", height=34
        )
        self.btn_abort.pack(side="left", fill="x", expand=True, padx=(4, 0))
        ToolTip(self.btn_abort, "Abort Replay All entirely")

        # Hidden log area for setup_global_logging compatibility
        self.log_area = ctk.CTkTextbox(self, height=0, width=0)

        # Hotkeys (bound to toplevel root window since CTkFrame forbids bind_all)
        root_win = self.winfo_toplevel()
        root_win.bind("<F5>", lambda e: (self.commands.get("resume")() if self.commands.get("resume") else (self.commands.get("start_referent")() if self.commands.get("start_referent") else None)))
        root_win.bind("<F6>", lambda e: self.commands.get("restart_current_gesture")() if self.commands.get("restart_current_gesture") else None)
        root_win.bind("<Shift-F6>", lambda e: self.commands.get("previous_gesture")() if self.commands.get("previous_gesture") else None)
        root_win.bind("<F7>", lambda e: self.commands.get("pause")() if self.commands.get("pause") else None)
        root_win.bind("<F8>", lambda e: self.commands.get("estop")() if self.commands.get("estop") else None)
        root_win.bind("<Escape>", lambda e: self.commands.get("estop")() if self.commands.get("estop") else None)

    def on_sequence_changed(self, *args, **kwargs):
        """No-op handler to satisfy EventBus sequence_updated subscriptions."""
        pass

    def on_hardware_state_changed(self, state):
        """Updates safety badge based on live hardware telemetry."""
        if hasattr(state, 'is_fault_state') and state.is_fault_state:
            self.lbl_robot_status.configure(text="SAFETY FAULT / E-STOP", text_color=theme.ACCENT_RED)
        elif hasattr(state, 'is_connected') and state.is_connected:
            self.lbl_robot_status.configure(text="ROBOT ONLINE / READY", text_color=theme.ACCENT_GREEN)
        elif hasattr(state, 'is_connected') and not state.is_connected:
            self.lbl_robot_status.configure(text="ROBOT DISCONNECTED", text_color=theme.ACCENT_ORANGE)

    def show_referent_prompt(self, rid, name, instructions, phase, progress, counter_str, active_gesture=None):
        """Displays the setup readjustment prompt for the specified referent (`RID`)."""
        self.lbl_setup_banner.configure(
            text=f"SETUP READJUSTMENT REQUIRED: Verify physical study setup for R{rid} below.",
            fg_color="#38bdf8", text_color="#0f172a"
        )
        self.lbl_referent_title.configure(text=f"Referent R{rid} — {name}")
        self.lbl_instructions.configure(text=instructions)
        self.btn_start_referent.configure(
            text=f"Start Referent R{rid} (F5)",
            state="normal", bg_color=theme.ACCENT_GREEN
        )
        self.lbl_phase.configure(text=f"Phase: {phase}", text_color=theme.ACCENT_CYBER)
        self.lbl_progress_counter.configure(text=counter_str)
        self.progress_bar.set(progress / 100.0)

        if active_gesture:
            gid = active_gesture.get("id", "-")
            gpid = active_gesture.get("pid", "-")
            gver = active_gesture.get("version", "-")
            gpath = active_gesture.get("filepath", "-")
            self.lbl_clip_id.configure(text=f"Next Clip: {gid} (Participant {gpid}, Version {gver})")
            self.lbl_clip_path.configure(text=f"File: {os.path.basename(gpath)}")

    def update_status(self, phase=None, progress=None, counter_str=None, active_gesture=None):
        """Updates live phase status and progress during automated playback."""
        if phase:
            self.lbl_phase.configure(text=f"Phase: {phase}")
            if "Replaying" in phase or "Stage" in phase:
                self.lbl_setup_banner.configure(
                    text="REPLAY IN PROGRESS: Robot arm is actively moving in automated sequence.",
                    fg_color=theme.ACCENT_GREEN, text_color=theme.BG_MAIN
                )
                self.btn_start_referent.configure(state="disabled", bg_color=theme.BORDER_COLOR)
        if progress is not None:
            self.progress_bar.set(progress / 100.0)
        if counter_str:
            self.lbl_progress_counter.configure(text=counter_str)
        if active_gesture:
            gid = active_gesture.get("id", "-")
            gpid = active_gesture.get("pid", "-")
            gver = active_gesture.get("version", "-")
            gpath = active_gesture.get("filepath", "-")
            self.lbl_clip_id.configure(text=f"Clip ID: {gid} (Participant {gpid}, Version {gver})")
            self.lbl_clip_path.configure(text=f"File: {os.path.basename(gpath)}")

    def show_completion_screen(self, total_gestures):
        """Updates view to indicate full Replay All study completion."""
        self.lbl_setup_banner.configure(
            text="=== STUDY REPLAY ALL COMPLETED SUCCESSFULLY ===",
            fg_color=theme.ACCENT_GREEN, text_color=theme.BG_MAIN
        )
        self.lbl_referent_title.configure(text="All Referents Evaluated")
        self.lbl_instructions.configure(text=f"Batch evaluation across all {total_gestures} experimental gestures has finished. You can now close the dashboard or review the generated FFmpeg log inside study_results/.")
        self.btn_start_referent.configure(state="disabled", text="Study Completed", bg_color=theme.BORDER_COLOR)
        self.lbl_phase.configure(text="Phase: Completed All Replays Across Study.", text_color=theme.ACCENT_GREEN)
        self.progress_bar.set(1.0)
        self.lbl_progress_counter.configure(text=f"{total_gestures} / {total_gestures} completed (100.0%)")
