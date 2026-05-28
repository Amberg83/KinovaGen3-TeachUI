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
        
        # Segmented Control Frame
        type_frame = ctk.CTkFrame(self.scrollable_content, fg_color=theme.BORDER_COLOR, corner_radius=4) 
        type_frame.pack(fill="x", pady=(0, 10))

        # Premium Custom Label-based Segmented Controls to bypass Windows native beveled 80s buttons
        self.lbl_action = self.make_segment_btn(type_frame, "ACTION", "action")
        self.lbl_action.pack(side="left", fill="x", expand=True, padx=1, pady=1)
        
        self.lbl_waypoint = self.make_segment_btn(type_frame, "WAYPOINT", "angularwaypoint")
        self.lbl_waypoint.pack(side="left", fill="x", expand=True, padx=1, pady=1)
        
        self.lbl_pause = self.make_segment_btn(type_frame, "PAUSE", "pause")
        self.lbl_pause.pack(side="left", fill="x", expand=True, padx=1, pady=1)

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

        # ---------------- SECTION 3: DURATION / WAIT TIME (Pause Editor always at the bottom!) ----------------
        self.duration_frame = theme.SectionFrame(self.scrollable_content, text="Duration / Wait Time (s)")
        
        self.ent_duration = ctk.CTkEntry(
            self.duration_frame.content, font=theme.FONT_MONO, height=30,
            fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER_COLOR, corner_radius=4
        )
        self.ent_duration.pack(fill="x", pady=4, padx=5)

        # Create a frame for the label and quick apply button
        dur_action_frame = ctk.CTkFrame(self.duration_frame.content, fg_color="transparent")
        dur_action_frame.pack(fill="x", pady=(2, 0), padx=5)

        self.lbl_min_duration = theme.make_label(
            dur_action_frame, text="Fast Limit: --s", 
            font=theme.FONT_BOLD, fg_color="transparent", text_color=theme.ACCENT_CYBER
        )
        self.lbl_min_duration.pack(side="left", anchor="w")

        self.btn_apply_min_dur = theme.make_flat_button(
            dur_action_frame, text=" Apply Limit", image=theme.get_icon("bolt", tint=theme.ACCENT_CYBER), compound="left",
            bg_color=theme.BG_INPUT, fg_color=theme.ACCENT_CYBER, hover_bg=theme.BORDER_COLOR
        )
        self.btn_apply_min_dur.pack(side="right")

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
            if (self.inspector_state != "disabled" or getattr(self, 'is_bulk_editing', False)) and self.wp_type_var.get() != value:
                lbl.configure(fg_color=theme.BORDER_COLOR, text_color=theme.TEXT_PRIMARY)
                
        def on_leave(e):
            if (self.inspector_state != "disabled" or getattr(self, 'is_bulk_editing', False)) and self.wp_type_var.get() != value:
                lbl.configure(fg_color=theme.BG_INPUT, text_color=theme.TEXT_MUTED)
                
        def on_click(e):
            if self.inspector_state != "disabled" or getattr(self, 'is_bulk_editing', False):
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
            "angularwaypoint": self.lbl_waypoint,
            "pause": self.lbl_pause
        }
        for val, lbl in mapping.items():
            if self.inspector_state == "disabled" and not getattr(self, 'is_bulk_editing', False):
                lbl.configure(fg_color=theme.BG_INPUT, text_color=theme.TEXT_MUTED, cursor="arrow")
            else:
                lbl.configure(cursor="hand2")
                if self.wp_type_var.get() == val:
                    lbl.configure(fg_color=theme.ACCENT_CYBER, text_color=theme.BG_MAIN)
                else:
                    lbl.configure(fg_color=theme.BG_INPUT, text_color=theme.TEXT_MUTED)

    def bind_commands(self, commands):
        """Binds commands relating to Column 3 operations."""
        self.btn_preview.configure(command=commands.get("preview_pose"))
        self.btn_save_settings.configure(command=commands.get("save_settings"))
        self.btn_append_new.configure(command=commands.get("append_pose"))
        self.btn_apply_min_dur.configure(command=commands.get("apply_min_durations"))
        
        # Bind <Return> (Enter key) on all entry fields to trigger save settings
        self._save_settings_cb = commands.get("save_settings")
        for ent in self.insp_entries + self.ent_wp_vels + [self.ent_duration]:
            ent.bind("<Return>", lambda event: self._on_enter_pressed())

    def _on_enter_pressed(self):
        """Triggers waypoint modifications save when Enter key is pressed."""
        if self.inspector_state != "disabled" and getattr(self, "_save_settings_cb", None):
            self._save_settings_cb()

    def _set_inspector_state(self, state):
        """Enables or disables editor elements depending on selection state."""
        self.inspector_state = state
        tk_state = "normal" if state == "normal" else "disabled"
        
        # Simple list of elements
        widgets = [self.ent_duration] + self.ent_wp_vels + self.insp_entries + [
            self.btn_save_settings, self.btn_preview, self.btn_append_new, self.btn_apply_min_dur
        ]
        
        for w in widgets: 
            w.configure(state=tk_state)
            
        # Update colors on disabled to keep the modern flat look
        if state == "disabled":
            self.btn_preview.configure(fg_color=theme.BORDER_COLOR, text_color=theme.TEXT_MUTED)
            self.btn_save_settings.configure(fg_color=theme.BORDER_COLOR, text_color=theme.TEXT_MUTED)
            self.btn_append_new.configure(fg_color=theme.BORDER_COLOR, text_color=theme.TEXT_MUTED)
            self.btn_apply_min_dur.configure(fg_color=theme.BORDER_COLOR, text_color=theme.TEXT_MUTED)
        else:
            self.btn_preview.configure(fg_color=theme.ACCENT_YELLOW, text_color=theme.BG_MAIN)
            self.btn_save_settings.configure(fg_color=theme.ACCENT_GREEN, text_color=theme.BG_MAIN)
            self.btn_append_new.configure(fg_color=theme.ACCENT_CYBER, text_color=theme.TEXT_PRIMARY)
            self.btn_apply_min_dur.configure(fg_color=theme.BG_INPUT, text_color=theme.ACCENT_CYBER)

        # Update segment button styles
        self.update_segment_styles()

        for i in range(6): 
            self.insp_joint_vars[i].set("0.0" if state == "disabled" else self.insp_joint_vars[i].get())

    def toggle_wp_settings(self):
        """Swaps visibility and order of panels based on selected waypoint type."""
        wp_type = self.wp_type_var.get()
        if wp_type == "action":
            self.joint_frame.pack(fill="x", pady=5)
            self.frame_wp_vels.pack_forget()
            self.duration_frame.pack(fill="x", pady=5)
        elif wp_type == "angularwaypoint":
            self.joint_frame.pack(fill="x", pady=5)
            self.frame_wp_vels.pack(fill="x", pady=5)
            self.duration_frame.pack(fill="x", pady=5)
        elif wp_type == "pause":
            self.joint_frame.pack_forget()
            self.frame_wp_vels.pack_forget()
            self.duration_frame.pack(fill="x", pady=5)

    def clear_inspector(self):
        """Resets panel state when no element is selected anymore."""
        self._set_inspector_state("disabled")
        self.lbl_inspector_title.configure(text="No Waypoint Selected", text_color=theme.TEXT_MUTED, font=theme.FONT_NORMAL)
        self.lbl_min_duration.configure(text="Fast Limit: --s", text_color=theme.TEXT_MUTED)

    def load_inspector_data(self, data, index, predecessor_pos=None):
        """Populates fields from selected row dictionaries."""
        self.is_bulk_editing = False
        self._set_inspector_state("normal")
        self.lbl_inspector_title.configure(text=f"Selected Waypoint: #{index}", text_color=theme.ACCENT_CYBER, font=theme.FONT_TITLE)
        
        # Disable joint change listener during loading to prevent noise
        self._disable_joint_traces = True
        
        self.wp_type_var.set(data.get("type", "action"))
        self.update_segment_styles()
        self.toggle_wp_settings()
        
        self.ent_duration.delete(0, tk.END)
        self.ent_duration.insert(0, str(data.get("duration_s", 3.0)))
        
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
            
        # Re-enable trace changes and refresh speed limit text
        self._disable_joint_traces = False
        self.recalculate_min_safe_duration()

    def recalculate_min_safe_duration(self):
        """Dynamically computes the physical speed/duration boundary for joint movements."""
        if getattr(self, "_disable_joint_traces", False) or self.inspector_state == "disabled":
            return
            
        wp_type = self.wp_type_var.get()
        if wp_type == "pause":
            self.lbl_min_duration.configure(text="Fast Limit: -- (Pause Step)", text_color=theme.TEXT_MUTED)
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
            if wp_type == "action":
                min_safe_dur = calculate_min_trajectory_duration(self._predecessor_pos, current_poses)
            else:
                min_durs = calculate_waypoint_durations([self._predecessor_pos, current_poses])
                min_safe_dur = min_durs[0] if min_durs else 0.6
                
            self.lbl_min_duration.configure(text=f"Fast Limit: {min_safe_dur:.2f}s", text_color=theme.ACCENT_CYBER)
        else:
            self.lbl_min_duration.configure(text="Fast Limit: 0.50s", text_color=theme.ACCENT_CYBER)

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
        
        disable_widgets = [
            self.btn_preview, self.btn_append_new
        ] + self.ent_wp_vels + self.insp_entries
        
        for w in disable_widgets:
            w.configure(state="disabled")
            
        self.btn_preview.configure(fg_color=theme.BORDER_COLOR, text_color=theme.TEXT_MUTED)
        self.btn_append_new.configure(fg_color=theme.BORDER_COLOR, text_color=theme.TEXT_MUTED)
        
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
        try: 
            dur_s = float(self.ent_duration.get() or 3.0)
        except ValueError: 
            dur_s = 3.0

        if wp_type == "angularwaypoint":
            for i, ent in enumerate(self.ent_wp_vels):
                try: 
                    max_vels[i] = float(ent.get() or 0.0)
                except ValueError: 
                    pass

        return {"type": wp_type, "duration_s": dur_s, "max_velocities": max_vels, "pause_s": 0.0}

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
