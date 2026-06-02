import tkinter as tk
import customtkinter as ctk
from view import theme
from utils.duration_calculator import calculate_min_trajectory_duration, calculate_waypoint_durations

class WaypointInspectorPanel(ctk.CTkFrame):
    """Encapsulates Column 3: The Waypoint Inspector form to edit or preview sequence entries in responsive dark flat style."""
    def __init__(self, parent, **kwargs):
        kwargs.pop("text", None)
        super().__init__(parent, fg_color=theme.BG_MAIN, corner_radius=0, **kwargs)
        
        self.wp_type_var = ctk.StringVar(value="action")
        self.insp_joint_vars = []
        self.ent_wp_vels = []
        self.joint_frames = []
        self.vel_frames = []
        self.insp_entries = []
        self.inspector_state = "disabled"
        self.wide_mode = True
        self.is_bulk_editing = False
        
        # Load custom gripper presets and speed presets dynamically from robot_config.json
        self.gripper_presets = {"open": "0.0", "closed": "100.0", "pickup": "50.0"}
        self.gripper_speed_presets = {"slow": "0.20", "medium": "0.50", "fast": "0.00"}
        
        import os
        import json
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        rob_path = os.path.join(base_dir, "config", "robot_config.json")
        if os.path.exists(rob_path):
            try:
                with open(rob_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    presets = cfg.get("gripper_presets", {})
                    self.gripper_presets = {k: f"{float(v):.1f}" for k, v in presets.items()}
                    
                    speeds = cfg.get("gripper_speed_presets", {})
                    self.gripper_speed_presets = {k: f"{float(v):.2f}" for k, v in speeds.items()}
            except Exception:
                pass
                
        # Declare variables for Robotiq 2F-140 Gripper settings
        self.gripper_state_var = ctk.StringVar(value="open")
        self.gripper_duration_var = ctk.StringVar(value="medium")
        
        self.setup_ui()
        self._set_inspector_state("disabled")
        # self.bind("<Configure>", self.on_resize)  # Driven directly by parent MainView

    def setup_ui(self):
        # Panel Title Header
        self.lbl_panel_header = theme.make_label(
            self, text="3. WAYPOINT INSPECTOR / EDITOR", font=theme.FONT_TITLE,
            fg_color=theme.BG_HEADER, text_color=theme.ACCENT_CYBER,
            height=32, corner_radius=0
        )
        self.lbl_panel_header.pack(fill="x", pady=(0, 6))

        # ---------------- PINNED BOTTOM FRAME (Always visible on baseline) ----------------
        self.bottom_frame = ctk.CTkFrame(self, fg_color=theme.BG_CARD, corner_radius=4)
        self.bottom_frame.pack(side="bottom", fill="x", pady=(6, 0))

        self.btn_preview = theme.make_flat_button(
            self.bottom_frame, text=" Preview this Pose", image=theme.get_icon("play", tint=theme.BG_MAIN), compound="left",
            bg_color=theme.ACCENT_YELLOW, fg_color=theme.BG_MAIN, hover_bg="#eab308"
        )
        self.btn_preview.pack(fill="x", side="bottom", pady=4, padx=10)
        
        self.btn_save_settings = theme.make_flat_button(
            self.bottom_frame, text=" Apply & Save to Selected", image=theme.get_icon("save", tint=theme.BG_MAIN), compound="left",
            bg_color=theme.ACCENT_GREEN, fg_color=theme.BG_MAIN, hover_bg="#059669"
        )
        self.btn_save_settings.pack(fill="x", side="bottom", pady=4, padx=10)

        self.btn_append_new = theme.make_flat_button(
            self.bottom_frame, text=" Append as New Waypoint", image=theme.get_icon("add_waypoint"), compound="left",
            bg_color=theme.ACCENT_CYBER, fg_color=theme.TEXT_PRIMARY, hover_bg=theme.ACCENT_CYBER_HOVER
        )
        self.btn_append_new.pack(fill="x", side="bottom", pady=(10, 4), padx=10)

        # ---------------- SCROLLABLE TOP CONTAINER ----------------
        self.scrollable_content = ctk.CTkScrollableFrame(
            self, fg_color=theme.BG_CARD, corner_radius=4,
            scrollbar_button_color=theme.BORDER_COLOR,
            scrollbar_button_hover_color=theme.ACCENT_CYBER
        )
        self.scrollable_content.pack(side="top", fill="both", expand=True)

        # Title & Type selectors
        self.lbl_inspector_title = theme.make_label(self.scrollable_content, text="No Waypoint Selected", font=theme.FONT_NORMAL, fg_color=theme.BG_CARD, text_color=theme.TEXT_MUTED)
        self.lbl_inspector_title.pack(pady=(0, 10))

        theme.make_label(self.scrollable_content, text="Type:", font=theme.FONT_BOLD, fg_color=theme.BG_CARD, text_color=theme.TEXT_PRIMARY).pack(anchor="w", pady=(0, 5))
        
        # Segmented Control Frame (only Action and Waypoint types; Pause and Gripper cannot be cross-swapped)
        type_frame = ctk.CTkFrame(self.scrollable_content, fg_color=theme.BORDER_COLOR, corner_radius=4) 
        type_frame.pack(fill="x", pady=(0, 10))

        # Premium Custom Label-based Segmented Controls to bypass Windows native beveled 80s buttons
        self.lbl_action = self.make_segment_btn(type_frame, "ACTION", "action")
        self.lbl_action.pack(side="left", fill="x", expand=True, padx=1, pady=1)
        
        self.lbl_waypoint = self.make_segment_btn(type_frame, "WAYPOINT", "angularwaypoint")
        self.lbl_waypoint.pack(side="left", fill="x", expand=True, padx=1, pady=1)

        # ---------------- SECTION 1: JOINT TARGETS (Over other adjustments!) ----------------
        self.joint_frame = theme.SectionFrame(self.scrollable_content, text="Joint Angles (°)")
        
        for i in range(6):
            f = ctk.CTkFrame(self.joint_frame.content, fg_color="transparent")
            theme.make_label(f, text=f"J{i+1}:", font=theme.FONT_BOLD, fg_color="transparent", text_color=theme.TEXT_MUTED, width=30, anchor="w").pack(side="left")
            
            var = ctk.StringVar(value="0.0")
            ent = ctk.CTkEntry(
                f, textvariable=var, width=100, height=28, font=theme.FONT_MONO,
                fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER_COLOR, corner_radius=4
            )
            ent.pack(side="right", fill="x", expand=True, padx=(4, 0))
            
            self.insp_joint_vars.append(var)
            self.insp_entries.append(ent)
            self.joint_frames.append(f)

        # ---------------- SECTION 2: MAX VELOCITIES (Middle adjustments) ----------------
        self.frame_wp_vels = theme.SectionFrame(self.scrollable_content, text="Max Velocities (°/s)")
        
        for i in range(6):
            f = ctk.CTkFrame(self.frame_wp_vels.content, fg_color="transparent")
            theme.make_label(f, text=f"J{i+1}:", font=theme.FONT_BOLD, fg_color="transparent", text_color=theme.TEXT_MUTED, width=30, anchor="w").pack(side="left")
            
            ent = ctk.CTkEntry(
                f, width=100, height=28, font=theme.FONT_MONO,
                fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER_COLOR, corner_radius=4
            )
            ent.pack(side="right", fill="x", expand=True, padx=(4, 0))
            
            self.ent_wp_vels.append(ent)
            self.vel_frames.append(f)

        # ---------------- SECTION 3: DURATION (s) ----------------
        self.duration_frame = theme.SectionFrame(self.scrollable_content, text="Duration (s)")
        
        self.ent_duration = ctk.CTkEntry(
            self.duration_frame.content, font=theme.FONT_MONO, height=30,
            fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER_COLOR, corner_radius=4
        )
        self.ent_duration.pack(fill="x", pady=4, padx=5)

        self.lbl_min_duration = theme.make_label(
            self.duration_frame.content, text="Fast: --s | Med: --s | Slow: --s", 
            font=theme.FONT_BOLD, fg_color="transparent", text_color=theme.ACCENT_CYBER,
            anchor="w"
        )
        self.lbl_min_duration.pack(fill="x", pady=(2, 4), padx=5)

        self.btn_apply_fast = theme.make_flat_button(
            self.duration_frame.content, text=" Apply Fast Limit", image=theme.get_icon("speed", tint=theme.ACCENT_RED), compound="left",
            bg_color=theme.BG_INPUT, fg_color=theme.ACCENT_RED, hover_bg=theme.BORDER_COLOR
        )
        self.btn_apply_fast.pack(fill="x", pady=2, padx=5)

        self.btn_apply_medium = theme.make_flat_button(
            self.duration_frame.content, text=" Apply Medium Limit", image=theme.get_icon("speed", tint=theme.ACCENT_YELLOW), compound="left",
            bg_color=theme.BG_INPUT, fg_color=theme.ACCENT_YELLOW, hover_bg=theme.BORDER_COLOR
        )
        self.btn_apply_medium.pack(fill="x", pady=2, padx=5)

        self.btn_apply_slow = theme.make_flat_button(
            self.duration_frame.content, text=" Apply Slow Limit", image=theme.get_icon("speed", tint=theme.ACCENT_GREEN), compound="left",
            bg_color=theme.BG_INPUT, fg_color=theme.ACCENT_GREEN, hover_bg=theme.BORDER_COLOR
        )
        self.btn_apply_slow.pack(fill="x", pady=2, padx=5)

        # ---------------- SECTION 3b: WAIT TIME (s) (Pause Editor) ----------------
        self.wait_time_frame = theme.SectionFrame(self.scrollable_content, text="Wait Time (s)")
        self.ent_wait_time = ctk.CTkEntry(
            self.wait_time_frame.content, font=theme.FONT_MONO, height=30,
            fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER_COLOR, corner_radius=4
        )
        self.ent_wait_time.pack(fill="x", pady=4, padx=5)

        # ---------------- SECTION 4: GRIPPER SETTINGS (New) ----------------
        self.gripper_frame = theme.SectionFrame(self.scrollable_content, text="Gripper Settings")
        
        # State segment
        theme.make_label(self.gripper_frame.content, text="State:", font=theme.FONT_BOLD, fg_color="transparent", text_color=theme.TEXT_PRIMARY).pack(anchor="w", pady=(4, 2))
        state_seg = ctk.CTkFrame(self.gripper_frame.content, fg_color=theme.BORDER_COLOR, corner_radius=4)
        state_seg.pack(fill="x", pady=(0, 6))
        state_seg.columnconfigure(0, weight=1)
        state_seg.columnconfigure(1, weight=1)
        state_seg.columnconfigure(2, weight=1)
        
        self.lbl_g_open = self.make_gripper_segment_btn(state_seg, "OPEN", "open", "state")
        self.lbl_g_open.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        self.lbl_g_closed = self.make_gripper_segment_btn(state_seg, "CLOSED", "closed", "state")
        self.lbl_g_closed.grid(row=0, column=1, sticky="nsew", padx=1, pady=1)
        self.lbl_g_pickup = self.make_gripper_segment_btn(state_seg, "PICKUP", "pickup", "state")
        self.lbl_g_pickup.grid(row=0, column=2, sticky="nsew", padx=1, pady=1)

        # Duration segment
        theme.make_label(self.gripper_frame.content, text="Duration:", font=theme.FONT_BOLD, fg_color="transparent", text_color=theme.TEXT_PRIMARY).pack(anchor="w", pady=(4, 2))
        duration_seg = ctk.CTkFrame(self.gripper_frame.content, fg_color=theme.BORDER_COLOR, corner_radius=4)
        duration_seg.pack(fill="x", pady=(0, 2))
        duration_seg.columnconfigure(0, weight=1)
        duration_seg.columnconfigure(1, weight=1)
        duration_seg.columnconfigure(2, weight=1)
        
        self.lbl_g_slow = self.make_gripper_segment_btn(duration_seg, "SLOW", "slow", "duration")
        self.lbl_g_slow.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        self.lbl_g_med = self.make_gripper_segment_btn(duration_seg, "MEDIUM", "medium", "duration")
        self.lbl_g_med.grid(row=0, column=1, sticky="nsew", padx=1, pady=1)
        self.lbl_g_fast = self.make_gripper_segment_btn(duration_seg, "FAST", "fast", "duration")
        self.lbl_g_fast.grid(row=0, column=2, sticky="nsew", padx=1, pady=1)

        # Custom inputs separator/label
        theme.make_label(self.gripper_frame.content, text="Custom Settings (Overrides):", font=theme.FONT_BOLD, fg_color="transparent", text_color=theme.ACCENT_CYBER).pack(anchor="w", pady=(8, 4))
        
        # Position Custom Entry
        theme.make_label(self.gripper_frame.content, text="Target Position (%):", font=theme.FONT_BOLD, fg_color="transparent", text_color=theme.TEXT_PRIMARY).pack(anchor="w", pady=(2, 1))
        
        pos_entry_frame = ctk.CTkFrame(self.gripper_frame.content, fg_color="transparent")
        pos_entry_frame.pack(fill="x", pady=(0, 4))
        
        self.ent_g_target_pos = ctk.CTkEntry(pos_entry_frame, fg_color=theme.BG_INPUT, border_color=theme.BORDER_COLOR, font=theme.FONT_MONO, height=28)
        self.ent_g_target_pos.pack(fill="x")
        self.ent_g_target_pos.bind("<KeyRelease>", lambda e: self._on_gripper_entry_changed())
        
        self.lbl_g_pos_desc = theme.make_label(self.gripper_frame.content, text="* Accepts 0 to 100 (0% is fully opened, 100% is fully closed)", font=("Arial", 8, "italic"), text_color=theme.TEXT_MUTED)
        self.lbl_g_pos_desc.pack(anchor="w", pady=(0, 6))

        # Speed Ratio Custom Entry
        theme.make_label(self.gripper_frame.content, text="Speed Ratio (0.0 to 1.0):", font=theme.FONT_BOLD, fg_color="transparent", text_color=theme.TEXT_PRIMARY).pack(anchor="w", pady=(2, 1))
        
        speed_entry_frame = ctk.CTkFrame(self.gripper_frame.content, fg_color="transparent")
        speed_entry_frame.pack(fill="x", pady=(0, 4))
        
        self.ent_g_speed_ratio = ctk.CTkEntry(speed_entry_frame, fg_color=theme.BG_INPUT, border_color=theme.BORDER_COLOR, font=theme.FONT_MONO, height=28)
        self.ent_g_speed_ratio.pack(fill="x")
        self.ent_g_speed_ratio.bind("<KeyRelease>", lambda e: self._on_gripper_entry_changed())
        
        self.lbl_g_speed_desc = theme.make_label(self.gripper_frame.content, text="* Accepts 0.01 to 1.0 (velocity limit ratio; 0.0 implies fast position mode)", font=("Arial", 8, "italic"), text_color=theme.TEXT_MUTED)
        self.lbl_g_speed_desc.pack(anchor="w", pady=(0, 6))

        # Traces for live recalculation of min duration
        self._disable_joint_traces = False
        self._predecessor_pos = [0.0] * 6
        for var in self.insp_joint_vars:
            var.trace_add("write", lambda *args: self.recalculate_min_safe_duration())
        self.wp_type_var.trace_add("write", lambda *args: self.recalculate_min_safe_duration())

        # Apply initial layout sizing
        self.apply_layout(self.wide_mode)
        
        # Toggle options views based on loaded default types
        self.toggle_wp_settings()

    def apply_layout(self, is_wide):
        """Redraws and grids editor components depending on container panel width."""
        
        # 1. Joint target position grids
        self.joint_frame.content.columnconfigure(0, weight=1)
        if is_wide:
            self.joint_frame.content.columnconfigure(1, weight=1)
            for i, f in enumerate(self.joint_frames):
                row = i // 2
                col = i % 2
                f.grid_forget()
                f.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
        else:
            self.joint_frame.content.columnconfigure(1, weight=0)
            for i, f in enumerate(self.joint_frames):
                f.grid_forget()
                f.grid(row=i, column=0, sticky="nsew", padx=4, pady=3)

        # 2. Max Velocities grids
        self.frame_wp_vels.content.columnconfigure(0, weight=1)
        if is_wide:
            self.frame_wp_vels.content.columnconfigure(1, weight=1)
            for i, f in enumerate(self.vel_frames):
                row = i // 2
                col = i % 2
                f.grid_forget()
                f.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
        else:
            self.frame_wp_vels.content.columnconfigure(1, weight=0)
            for i, f in enumerate(self.vel_frames):
                f.grid_forget()
                f.grid(row=i, column=0, sticky="nsew", padx=4, pady=3)

    def on_resize(self, event):
        """Binds to container Configure to adapt layout responsively."""
        if str(event.widget) != self._w:
            return
        w = event.width
        # Threshold: 290 pixels
        threshold = 290
        
        is_wide = (w >= threshold)
        if is_wide != self.wide_mode:
            self.wide_mode = is_wide
            self.apply_layout(is_wide)

    def make_segment_btn(self, parent, text, value):
        """Builds custom label-based segmented toggle buttons to bypass platform borders."""
        lbl = theme.make_label(
            parent, text=text, font=("Arial", 8, "bold"),
            fg_color=theme.BG_INPUT, text_color=theme.TEXT_MUTED,
            pady=8, corner_radius=0
        )
        lbl.configure(cursor="hand2")
        
        def on_enter(e):
            current_type = self.wp_type_var.get()
            is_type_locked = current_type in ["pause", "gripper"]
            if not is_type_locked and (self.inspector_state != "disabled" or getattr(self, 'is_bulk_editing', False)) and current_type != value:
                lbl.configure(fg_color=theme.BORDER_COLOR, text_color=theme.TEXT_PRIMARY)
                
        def on_leave(e):
            current_type = self.wp_type_var.get()
            is_type_locked = current_type in ["pause", "gripper"]
            if not is_type_locked and (self.inspector_state != "disabled" or getattr(self, 'is_bulk_editing', False)) and current_type != value:
                lbl.configure(fg_color=theme.BG_INPUT, text_color=theme.TEXT_MUTED)
                
        def on_click(e):
            current_type = self.wp_type_var.get()
            is_type_locked = current_type in ["pause", "gripper"]
            if not is_type_locked and (self.inspector_state != "disabled" or getattr(self, 'is_bulk_editing', False)):
                self.set_wp_type(value)
                
        lbl.bind("<Enter>", on_enter)
        lbl.bind("<Leave>", on_leave)
        lbl.bind("<Button-1>", on_click)
        return lbl

    def set_wp_type(self, value):
        """Saves selection state, updates highlight colors and swaps velocity visibility dynamically."""
        self.wp_type_var.set(value)
        self.update_segment_styles()
        if not getattr(self, 'is_bulk_editing', False):
            self.toggle_wp_settings()

    def update_segment_styles(self):
        """Renders solid accent cyan backgrounds on active toggle buttons and grey on disabled entries."""
        mapping = {
            "action": self.lbl_action,
            "angularwaypoint": self.lbl_waypoint
        }
        
        current_type = self.wp_type_var.get()
        is_type_locked = current_type in ["pause", "gripper"]
        
        for val, lbl in mapping.items():
            if (self.inspector_state == "disabled" and not getattr(self, 'is_bulk_editing', False)) or is_type_locked:
                lbl.configure(fg_color=theme.BG_INPUT, text_color=theme.TEXT_MUTED, cursor="arrow")
            else:
                lbl.configure(cursor="hand2")
                if current_type == val:
                    lbl.configure(fg_color=theme.ACCENT_CYBER, text_color=theme.BG_MAIN)
                else:
                    lbl.configure(fg_color=theme.BG_INPUT, text_color=theme.TEXT_MUTED)

    def make_gripper_segment_btn(self, parent, text, value, field_name):
        """Builds custom label-based segmented toggle buttons for gripper fields."""
        lbl = theme.make_label(
            parent, text=text, font=("Arial", 8, "bold"),
            fg_color=theme.BG_INPUT, text_color=theme.TEXT_MUTED,
            pady=8, corner_radius=0
        )
        lbl.configure(cursor="hand2")
        
        var_map = {
            "state": self.gripper_state_var,
            "duration": self.gripper_duration_var
        }
        var = var_map[field_name]
        
        def on_enter(e):
            if self.inspector_state != "disabled" and var.get() != value:
                lbl.configure(fg_color=theme.BORDER_COLOR, text_color=theme.TEXT_PRIMARY)
                
        def on_leave(e):
            if self.inspector_state != "disabled" and var.get() != value:
                lbl.configure(fg_color=theme.BG_INPUT, text_color=theme.TEXT_MUTED)
                
        def on_click(e):
            if self.inspector_state != "disabled":
                var.set(value)
                
                # Sync custom manual entry boxes dynamically on segment selection
                self._disable_joint_traces = True
                if field_name == "state":
                    state_val = value.lower()
                    self.ent_g_target_pos.delete(0, tk.END)
                    self.ent_g_target_pos.insert(0, self.gripper_presets.get(state_val, "0.0"))
                    self.ent_g_target_pos.configure(border_color=theme.BORDER_COLOR)
                elif field_name == "duration":
                    dur_val = value.lower()
                    self.ent_g_speed_ratio.delete(0, tk.END)
                    self.ent_g_speed_ratio.insert(0, self.gripper_speed_presets.get(dur_val, "0.00"))
                    self.ent_g_speed_ratio.configure(border_color=theme.BORDER_COLOR)
                self._disable_joint_traces = False
                
                self.update_gripper_segment_styles()
                # instant auto-save
                if hasattr(self, "commands") and self.commands.get("save_settings"):
                    self.commands["save_settings"]()
                
        lbl.bind("<Enter>", on_enter)
        lbl.bind("<Leave>", on_leave)
        lbl.bind("<Button-1>", on_click)
        return lbl

    def update_gripper_segment_styles(self):
        """Renders active gripper buttons with accent cyan and others with normal state."""
        state_mapping = {
            "open": self.lbl_g_open,
            "closed": self.lbl_g_closed,
            "pickup": self.lbl_g_pickup
        }
        duration_mapping = {
            "slow": self.lbl_g_slow,
            "medium": self.lbl_g_med,
            "fast": self.lbl_g_fast
        }
        
        def set_styles(mapping, current_val):
            for val, lbl in mapping.items():
                if self.inspector_state == "disabled":
                    lbl.configure(fg_color=theme.BG_INPUT, text_color=theme.TEXT_MUTED, cursor="arrow")
                else:
                    lbl.configure(cursor="hand2")
                    if current_val == val:
                        lbl.configure(fg_color=theme.ACCENT_CYBER, text_color=theme.BG_MAIN)
                    else:
                        lbl.configure(fg_color=theme.BG_INPUT, text_color=theme.TEXT_MUTED)

        set_styles(state_mapping, self.gripper_state_var.get())
        set_styles(duration_mapping, self.gripper_duration_var.get())

    def _on_gripper_entry_changed(self):
        """Called when manual target position or speed ratio entries are typed."""
        if getattr(self, "_disable_joint_traces", False) or self.inspector_state == "disabled":
            return
        
        # Validate Position
        pos_valid = False
        try:
            val = float(self.ent_g_target_pos.get().strip())
            if 0.0 <= val <= 100.0:
                pos_valid = True
        except ValueError:
            pass
            
        if pos_valid:
            self.ent_g_target_pos.configure(border_color=theme.BORDER_COLOR)
        else:
            self.ent_g_target_pos.configure(border_color=theme.ACCENT_RED)
            
        # Validate Speed Ratio
        speed_valid = False
        try:
            val = float(self.ent_g_speed_ratio.get().strip())
            if 0.0 <= val <= 1.0:
                speed_valid = True
        except ValueError:
            pass
            
        if speed_valid:
            self.ent_g_speed_ratio.configure(border_color=theme.BORDER_COLOR)
        else:
            self.ent_g_speed_ratio.configure(border_color=theme.ACCENT_RED)
            
        # Try to sync Segmented buttons
        if pos_valid:
            pos_val = float(self.ent_g_target_pos.get().strip())
            matched_state = ""
            for k, v in self.gripper_presets.items():
                try:
                    if abs(pos_val - float(v)) < 0.01:
                        matched_state = k
                        break
                except ValueError:
                    pass
            self.gripper_state_var.set(matched_state)
        else:
            self.gripper_state_var.set("")
            
        if speed_valid:
            speed_val = float(self.ent_g_speed_ratio.get().strip())
            matched_dur = ""
            for k, v in self.gripper_speed_presets.items():
                try:
                    if abs(speed_val - float(v)) < 0.01:
                        matched_dur = k
                        break
                except ValueError:
                    pass
            self.gripper_duration_var.set(matched_dur)
        else:
            self.gripper_duration_var.set("")
            
        self.update_gripper_segment_styles()
        
        # If valid, instant auto-save to model
        if pos_valid and speed_valid:
            if hasattr(self, "commands") and self.commands.get("save_settings"):
                self.commands["save_settings"]()

    def bind_commands(self, commands):
        """Binds commands relating to Column 3 operations."""
        self.commands = commands
        self.btn_preview.configure(command=commands.get("preview_pose"))
        self.btn_save_settings.configure(command=commands.get("save_settings"))
        self.btn_append_new.configure(command=commands.get("append_pose"))
        
        # Bind the three new apply buttons
        self.btn_apply_fast.configure(command=lambda: self._on_apply_speed(commands.get("apply_min_durations"), "fast"))
        self.btn_apply_medium.configure(command=lambda: self._on_apply_speed(commands.get("apply_min_durations"), "medium"))
        self.btn_apply_slow.configure(command=lambda: self._on_apply_speed(commands.get("apply_min_durations"), "slow"))
        
        # Bind <Return> (Enter key) on all entry fields to trigger save settings
        self._save_settings_cb = commands.get("save_settings")
        for ent in self.insp_entries + self.ent_wp_vels + [self.ent_duration, self.ent_wait_time]:
            ent.bind("<Return>", lambda event: self._on_enter_pressed())

    def _on_apply_speed(self, cmd_cb, speed):
        """Populates the calculated duration locally and dispatches the save/apply command."""
        if hasattr(self, "_calculated_durations") and speed in self._calculated_durations:
            val = self._calculated_durations[speed]
            self.ent_duration.delete(0, tk.END)
            self.ent_duration.insert(0, f"{val:.2f}")
            
        if cmd_cb:
            cmd_cb(speed=speed)

    def _on_enter_pressed(self):
        """Triggers waypoint modifications save when Enter key is pressed."""
        if self.inspector_state != "disabled" and getattr(self, "_save_settings_cb", None):
            self._save_settings_cb()

    def _set_inspector_state(self, state):
        """Enables or disables editor elements depending on selection state."""
        self.inspector_state = state
        tk_state = "normal" if state == "normal" else "disabled"
        
        # Simple list of elements
        widgets = [self.ent_duration, self.ent_wait_time] + self.ent_wp_vels + self.insp_entries + [
            self.btn_save_settings, self.btn_preview, self.btn_append_new,
            self.btn_apply_fast, self.btn_apply_medium, self.btn_apply_slow
        ]
        
        for w in widgets: 
            w.configure(state=tk_state)
            
        # Update colors on disabled to keep the modern flat look
        if state == "disabled":
            self.btn_preview.configure(fg_color=theme.BORDER_COLOR, text_color=theme.TEXT_MUTED)
            self.btn_save_settings.configure(fg_color=theme.BORDER_COLOR, text_color=theme.TEXT_MUTED)
            self.btn_append_new.configure(fg_color=theme.BORDER_COLOR, text_color=theme.TEXT_MUTED)
            self.btn_apply_fast.configure(fg_color=theme.BORDER_COLOR, text_color=theme.TEXT_MUTED, image=theme.get_icon("speed", tint=theme.TEXT_MUTED))
            self.btn_apply_medium.configure(fg_color=theme.BORDER_COLOR, text_color=theme.TEXT_MUTED, image=theme.get_icon("speed", tint=theme.TEXT_MUTED))
            self.btn_apply_slow.configure(fg_color=theme.BORDER_COLOR, text_color=theme.TEXT_MUTED, image=theme.get_icon("speed", tint=theme.TEXT_MUTED))
        else:
            self.btn_preview.configure(fg_color=theme.ACCENT_YELLOW, text_color=theme.BG_MAIN)
            self.btn_save_settings.configure(fg_color=theme.ACCENT_GREEN, text_color=theme.BG_MAIN)
            self.btn_append_new.configure(fg_color=theme.ACCENT_CYBER, text_color=theme.TEXT_PRIMARY)
            self.btn_apply_fast.configure(fg_color=theme.BG_INPUT, text_color=theme.ACCENT_RED, image=theme.get_icon("speed", tint=theme.ACCENT_RED))
            self.btn_apply_medium.configure(fg_color=theme.BG_INPUT, text_color=theme.ACCENT_YELLOW, image=theme.get_icon("speed", tint=theme.ACCENT_YELLOW))
            self.btn_apply_slow.configure(fg_color=theme.BG_INPUT, text_color=theme.ACCENT_GREEN, image=theme.get_icon("speed", tint=theme.ACCENT_GREEN))

        # Update segment button styles
        self.update_segment_styles()
        self.update_gripper_segment_styles()

        for i in range(6): 
            self.insp_joint_vars[i].set("0.0" if state == "disabled" else self.insp_joint_vars[i].get())

    def toggle_wp_settings(self):
        """Swaps visibility and order of panels based on selected waypoint type."""
        wp_type = self.wp_type_var.get()
        if wp_type == "action":
            self.joint_frame.pack(fill="x", pady=5)
            self.frame_wp_vels.pack_forget()
            self.duration_frame.pack(fill="x", pady=5)
            self.wait_time_frame.pack_forget()
            self.gripper_frame.pack_forget()
            
            # Enable preview button
            self.btn_preview.configure(state="normal", fg_color=theme.ACCENT_YELLOW, text_color=theme.BG_MAIN)
        elif wp_type == "angularwaypoint":
            self.joint_frame.pack(fill="x", pady=5)
            self.frame_wp_vels.pack_forget()
            self.duration_frame.pack(fill="x", pady=5)
            self.wait_time_frame.pack_forget()
            self.gripper_frame.pack_forget()
            
            # Enable preview button
            self.btn_preview.configure(state="normal", fg_color=theme.ACCENT_YELLOW, text_color=theme.BG_MAIN)
        elif wp_type == "pause":
            self.joint_frame.pack_forget()
            self.frame_wp_vels.pack_forget()
            self.duration_frame.pack_forget()
            self.wait_time_frame.pack(fill="x", pady=5)
            self.gripper_frame.pack_forget()
            
            # Disable preview button for pause!
            self.btn_preview.configure(state="disabled", fg_color=theme.BORDER_COLOR, text_color=theme.TEXT_MUTED)
        elif wp_type == "gripper":
            self.joint_frame.pack_forget()
            self.frame_wp_vels.pack_forget()
            self.duration_frame.pack_forget()
            self.wait_time_frame.pack_forget()
            self.gripper_frame.pack(fill="x", pady=5)
            
            # Enable preview button for gripper
            self.btn_preview.configure(state="normal", fg_color=theme.ACCENT_YELLOW, text_color=theme.BG_MAIN)

    def clear_inspector(self):
        """Resets panel state when no element is selected anymore."""
        self._set_inspector_state("disabled")
        self.lbl_inspector_title.configure(text="No Waypoint Selected", text_color=theme.TEXT_MUTED, font=theme.FONT_NORMAL)
        self.lbl_min_duration.configure(text="Fast: --s | Med: --s | Slow: --s", text_color=theme.TEXT_MUTED)

    def load_inspector_data(self, data, index, predecessor_pos=None, run_poses=None, run_selected_idx=None):
        """Populates fields from selected row dictionaries."""
        self.is_bulk_editing = False
        self._set_inspector_state("normal")
        self.lbl_inspector_title.configure(text=f"Selected Waypoint: #{index}", text_color=theme.ACCENT_CYBER, font=theme.FONT_TITLE)
        
        # Disable joint change listener during loading to prevent noise
        self._disable_joint_traces = True
        
        self.wp_type_var.set(data.get("type", "action"))
        self.gripper_state_var.set(data.get("gripper_state", "open"))
        # Failsafe migration: load gripper_duration, falling back to gripper_speed if present in older files
        self.gripper_duration_var.set(data.get("gripper_duration", data.get("gripper_speed", "medium")))
        
        # Populate custom gripper inputs
        self.ent_g_target_pos.delete(0, tk.END)
        self.ent_g_target_pos.insert(0, str(data.get("gripper_target_pos", 0.0)))
        self.ent_g_speed_ratio.delete(0, tk.END)
        self.ent_g_speed_ratio.insert(0, str(data.get("gripper_speed_ratio", 0.0)))
        self.ent_g_target_pos.configure(border_color=theme.BORDER_COLOR)
        self.ent_g_speed_ratio.configure(border_color=theme.BORDER_COLOR)
        
        self.update_segment_styles()
        self.update_gripper_segment_styles()
        self.toggle_wp_settings()
        
        self.ent_duration.delete(0, tk.END)
        self.ent_duration.insert(0, str(data.get("duration_s", 3.0)))
        
        self.ent_wait_time.delete(0, tk.END)
        self.ent_wait_time.insert(0, str(data.get("duration_s", 2.0)))
        
        vels = data.get("max_velocities", [0.0]*6)
        for i, ent in enumerate(self.ent_wp_vels):
            ent.delete(0, tk.END)
            val = vels[i] if i < len(vels) else 0.0
            ent.insert(0, "" if val == 0.0 else str(val))
            
        pos = data.get("pos", [0.0]*6)
        for i, val in enumerate(pos):
            if i < len(self.insp_joint_vars):
                self.insp_joint_vars[i].set(str(val))

        # Store predecessor reference angles to calculate limits on modifications
        if predecessor_pos is not None:
            self._predecessor_pos = predecessor_pos
        else:
            self._predecessor_pos = [0.0] * 6

        # Store run context to calculate precise continuous-run limits
        self._run_poses = run_poses
        self._run_selected_idx = run_selected_idx
            
        # Re-enable trace changes and refresh speed limit text
        self._disable_joint_traces = False
        self.recalculate_min_safe_duration()

    def recalculate_min_safe_duration(self):
        """Dynamically computes the physical speed/duration boundary for joint movements."""
        if getattr(self, "_disable_joint_traces", False) or self.inspector_state == "disabled":
            return
            
        wp_type = self.wp_type_var.get()
        if wp_type in ["pause", "gripper"]:
            self.lbl_min_duration.configure(text="Fast: --s | Med: --s | Slow: --s", text_color=theme.TEXT_MUTED)
            self.btn_apply_fast.configure(state="disabled", fg_color=theme.BORDER_COLOR, text_color=theme.TEXT_MUTED, image=theme.get_icon("speed", tint=theme.TEXT_MUTED))
            self.btn_apply_medium.configure(state="disabled", fg_color=theme.BORDER_COLOR, text_color=theme.TEXT_MUTED, image=theme.get_icon("speed", tint=theme.TEXT_MUTED))
            self.btn_apply_slow.configure(state="disabled", fg_color=theme.BORDER_COLOR, text_color=theme.TEXT_MUTED, image=theme.get_icon("speed", tint=theme.TEXT_MUTED))
            return

        current_poses = []
        for var in self.insp_joint_vars:
            val_str = var.get().strip()
            if not val_str:
                current_poses.append(0.0)
            else:
                try:
                    current_poses.append(float(val_str))
                except ValueError:
                    current_poses.append(0.0)
                    
        if hasattr(self, "_predecessor_pos") and len(self._predecessor_pos) == len(current_poses):
            durs = {}
            for speed in ["fast", "medium", "slow"]:
                if wp_type == "action":
                    durs[speed] = calculate_min_trajectory_duration(self._predecessor_pos, current_poses, speed=speed)
                else:
                    # Use the full consecutive run context if available to get accurate continuous-run limits
                    if getattr(self, "_run_poses", None) is not None and getattr(self, "_run_selected_idx", None) is not None:
                        modified_run_poses = list(self._run_poses)
                        target_idx = self._run_selected_idx + 1
                        if 0 <= target_idx < len(modified_run_poses):
                            modified_run_poses[target_idx] = current_poses
                        
                        min_durs = calculate_waypoint_durations(modified_run_poses, speed=speed)
                        if min_durs and 0 <= self._run_selected_idx < len(min_durs):
                            durs[speed] = min_durs[self._run_selected_idx]
                        else:
                            durs[speed] = 0.6
                    else:
                        min_durs = calculate_waypoint_durations([self._predecessor_pos, current_poses], speed=speed)
                        durs[speed] = min_durs[0] if min_durs else 0.6
                        
            self._calculated_durations = durs
            self.lbl_min_duration.configure(
                text=f"Fast: {durs['fast']:.2f}s | Med: {durs['medium']:.2f}s | Slow: {durs['slow']:.2f}s",
                text_color=theme.ACCENT_CYBER
            )
            
            # Make sure buttons are enabled since we are not in pause type
            self.btn_apply_fast.configure(state="normal", fg_color=theme.BG_INPUT, text_color=theme.ACCENT_RED, image=theme.get_icon("speed", tint=theme.ACCENT_RED))
            self.btn_apply_medium.configure(state="normal", fg_color=theme.BG_INPUT, text_color=theme.ACCENT_YELLOW, image=theme.get_icon("speed", tint=theme.ACCENT_YELLOW))
            self.btn_apply_slow.configure(state="normal", fg_color=theme.BG_INPUT, text_color=theme.ACCENT_GREEN, image=theme.get_icon("speed", tint=theme.ACCENT_GREEN))
        else:
            self.lbl_min_duration.configure(text="Fast: --s | Med: --s | Slow: --s", text_color=theme.ACCENT_CYBER)

    def enter_bulk_edit_mode(self, indices):
        """Enables a bulk-edit state for editing duration and type across multiple waypoints."""
        self._set_inspector_state("normal")
        self.lbl_inspector_title.configure(
            text=f"Bulk-Editing {len(indices)} Waypoints", 
            text_color=theme.ACCENT_ORANGE, font=theme.FONT_TITLE
        )
        
        # Clear/Disable speed limit label during bulk duration edits
        self.lbl_min_duration.configure(text="Fast Limit: -- (Bulk Edit)", text_color=theme.TEXT_MUTED)
        
        self.is_bulk_editing = True
        self.inspector_state = "disabled"
        self.wp_type_var.set("action")
        self.update_segment_styles()
        self.gripper_frame.pack_forget()
        
        disable_widgets = [
            self.btn_preview, self.btn_append_new
        ] + self.ent_wp_vels + self.insp_entries
        
        for w in disable_widgets:
            w.configure(state="disabled")
            
        self.btn_preview.configure(fg_color=theme.BORDER_COLOR, text_color=theme.TEXT_MUTED)
        self.btn_append_new.configure(fg_color=theme.BORDER_COLOR, text_color=theme.TEXT_MUTED)
        
        # Keep apply buttons active and colored in bulk edit mode
        self.btn_apply_fast.configure(state="normal", fg_color=theme.BG_INPUT, text_color=theme.ACCENT_RED, image=theme.get_icon("speed", tint=theme.ACCENT_RED))
        self.btn_apply_medium.configure(state="normal", fg_color=theme.BG_INPUT, text_color=theme.ACCENT_YELLOW, image=theme.get_icon("speed", tint=theme.ACCENT_YELLOW))
        self.btn_apply_slow.configure(state="normal", fg_color=theme.BG_INPUT, text_color=theme.ACCENT_GREEN, image=theme.get_icon("speed", tint=theme.ACCENT_GREEN))
        
        # Clear duration and target inputs
        self.ent_duration.configure(state="normal")
        self.ent_duration.delete(0, tk.END)
        self.ent_duration.insert(0, "3.0")
        self.ent_duration.focus_set()
        
        # Clear joint variables
        self._disable_joint_traces = True
        for var in self.insp_joint_vars:
            var.set("")

    def get_waypoint_params(self):
        """Retrieves edits as a step parameter dictionary."""
        wp_type = self.wp_type_var.get()
        max_vels = [0.0] * 6
        
        if wp_type == "pause":
            try:
                dur_s = float(self.ent_wait_time.get() or 2.0)
            except ValueError:
                dur_s = 2.0
            params = {"type": wp_type, "duration_s": dur_s}
        else:
            try: 
                dur_s = float(self.ent_duration.get() or 3.0)
            except ValueError: 
                dur_s = 3.0
            params = {"type": wp_type, "duration_s": dur_s, "max_velocities": max_vels}
            if wp_type == "gripper":
                params["gripper_state"] = self.gripper_state_var.get()
                params["gripper_duration"] = self.gripper_duration_var.get()
                try:
                    params["gripper_target_pos"] = float(self.ent_g_target_pos.get().strip() or 0.0)
                except ValueError:
                    params["gripper_target_pos"] = 0.0
                try:
                    params["gripper_speed_ratio"] = float(self.ent_g_speed_ratio.get().strip() or 0.0)
                except ValueError:
                    params["gripper_speed_ratio"] = 0.0
        return params

    def get_inspector_poses(self):
        """Retrieves editor coordinates as float or None array for selective copying."""
        poses = []
        for var in self.insp_joint_vars:
            val_str = var.get().strip()
            if val_str == "":
                poses.append(None)
            else:
                try:
                    poses.append(float(val_str))
                except ValueError:
                    poses.append(None)
        # If all items are None, return None altogether
        if all(x is None for x in poses):
            return None
        return poses
