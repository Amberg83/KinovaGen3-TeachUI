import tkinter as tk
from tkinter import ttk
from view import theme

class WaypointInspectorPanel(ttk.LabelFrame):
    """Encapsulates Column 3: The Waypoint Inspector form to edit or preview sequence entries in responsive dark flat style."""
    def __init__(self, parent, **kwargs):
        kwargs.setdefault("text", "3. Waypoint Inspector / Editor")
        super().__init__(parent, style="TLabelframe", **kwargs)
        
        self.wp_type_var = tk.StringVar(value="action")
        self.insp_joint_vars = []
        self.ent_wp_vels = []
        self.joint_frames = []
        self.vel_frames = []
        self.insp_entries = []
        self.inspector_state = "disabled"
        self.wide_mode = True
        
        self.setup_ui()
        self._set_inspector_state("disabled")
        self.bind("<Configure>", self.on_resize)

    def setup_ui(self):
        # ---------------- PINNED BOTTOM FRAME (Always visible on baseline) ----------------
        self.bottom_frame = tk.Frame(self, bg=theme.BG_CARD)
        self.bottom_frame.pack(side="bottom", fill="x", pady=(6, 0))

        self.btn_preview = theme.make_flat_button(
            self.bottom_frame, text="▶ Preview this Pose", bg_color=theme.ACCENT_YELLOW, 
            fg_color=theme.BG_MAIN, hover_bg="#eab308", 
            font_style=theme.FONT_EMOJI_LARGE
        )
        self.btn_preview.pack(fill="x", side="bottom", pady=2)
        
        self.btn_save_settings = theme.make_flat_button(
            self.bottom_frame, text="💾 Apply & Save to Selected", bg_color=theme.ACCENT_GREEN, 
            fg_color=theme.BG_MAIN, hover_bg="#059669", 
            font_style=theme.FONT_EMOJI_LARGE
        )
        self.btn_save_settings.pack(fill="x", side="bottom", pady=2)

        self.btn_append_new = theme.make_flat_button(
            self.bottom_frame, text="➕ Append as New Waypoint", bg_color=theme.ACCENT_CYBER, 
            fg_color=theme.TEXT_PRIMARY, hover_bg=theme.ACCENT_CYBER_HOVER, 
            font_style=theme.FONT_EMOJI_LARGE
        )
        self.btn_append_new.pack(fill="x", side="bottom", pady=2)

        # ---------------- SCROLLABLE TOP CONTAINER ----------------
        self.top_frame = tk.Frame(self, bg=theme.BG_CARD)
        self.top_frame.pack(side="top", fill="both", expand=True)

        self.canvas = tk.Canvas(self.top_frame, bg=theme.BG_CARD, highlightthickness=0, bd=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        self.scrollbar = ttk.Scrollbar(self.top_frame, orient="vertical", command=self.canvas.yview, style="Vertical.TScrollbar")
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scrollable_content = tk.Frame(self.canvas, bg=theme.BG_CARD)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_content, anchor="nw")

        def configure_scroll(event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.scrollable_content.bind("<Configure>", configure_scroll)

        def configure_canvas(event):
            # Synchronize width of the content frame to fill the canvas width
            self.canvas.itemconfig(self.canvas_window, width=event.width)
        self.canvas.bind("<Configure>", configure_canvas)

        # Localized mousewheel binding helpers
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        def _bind_mousewheel(event):
            self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        def _unbind_mousewheel(event):
            self.canvas.unbind_all("<MouseWheel>")
            
        self.bind("<Enter>", _bind_mousewheel)
        self.bind("<Leave>", _unbind_mousewheel)

        # Title & Type selectors
        self.lbl_inspector_title = tk.Label(self.scrollable_content, text="No Waypoint Selected", font=theme.FONT_NORMAL, bg=theme.BG_CARD, fg=theme.TEXT_MUTED)
        self.lbl_inspector_title.pack(pady=(0, 10))

        tk.Label(self.scrollable_content, text="Type:", font=theme.FONT_BOLD, bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY).pack(anchor="w", pady=(0, 5))
        
        # Segmented Control Frame
        type_frame = tk.Frame(self.scrollable_content, bg=theme.BORDER_COLOR, padx=1, pady=1) 
        type_frame.pack(fill="x", pady=(0, 10))

        # Premium Custom Label-based Segmented Controls to bypass Windows native beveled 80s buttons
        self.lbl_action = self.make_segment_btn(type_frame, "ACTION", "action")
        self.lbl_action.pack(side="left", fill="x", expand=True, padx=1)
        
        self.lbl_waypoint = self.make_segment_btn(type_frame, "WAYPOINT", "angularwaypoint")
        self.lbl_waypoint.pack(side="left", fill="x", expand=True, padx=1)
        
        self.lbl_pause = self.make_segment_btn(type_frame, "PAUSE", "pause")
        self.lbl_pause.pack(side="left", fill="x", expand=True, padx=1)

        # ---------------- SECTION 1: JOINT TARGETS (Over other adjustments!) ----------------
        self.joint_frame = tk.LabelFrame(self.scrollable_content, text="Joint Angles (°)", font=theme.FONT_BOLD, 
                                    bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY, relief="solid", bd=1, padx=8, pady=6)
        
        for i in range(6):
            f = tk.Frame(self.joint_frame, bg=theme.BG_CARD)
            tk.Label(f, text=f"J{i+1}:", font=theme.FONT_BOLD, bg=theme.BG_CARD, fg=theme.TEXT_MUTED, width=3, anchor="w").pack(side="left")
            
            var = tk.StringVar(value="0.0")
            ent = tk.Entry(f, textvariable=var, width=10, font=theme.FONT_MONO)
            ent.pack(side="right", fill="x", expand=True, padx=(4, 0))
            theme.apply_entry_theme(ent)
            
            self.insp_joint_vars.append(var)
            self.insp_entries.append(ent)
            self.joint_frames.append(f)

        # ---------------- SECTION 2: MAX VELOCITIES (Middle adjustments) ----------------
        self.frame_wp_vels = tk.LabelFrame(self.scrollable_content, text="Max Velocities (°/s)", font=theme.FONT_BOLD, 
                                      bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY, relief="solid", bd=1, padx=8, pady=6)
        
        for i in range(6):
            f = tk.Frame(self.frame_wp_vels, bg=theme.BG_CARD)
            tk.Label(f, text=f"J{i+1}:", font=theme.FONT_BOLD, bg=theme.BG_CARD, fg=theme.TEXT_MUTED, width=3, anchor="w").pack(side="left")
            
            ent = tk.Entry(f, width=10, font=theme.FONT_MONO)
            ent.pack(side="right", fill="x", expand=True, padx=(4, 0))
            theme.apply_entry_theme(ent)
            
            self.ent_wp_vels.append(ent)
            self.vel_frames.append(f)

        # ---------------- SECTION 3: DURATION / WAIT TIME (Pause Editor always at the bottom!) ----------------
        self.duration_frame = tk.LabelFrame(self.scrollable_content, text="Duration / Wait Time (s)", font=theme.FONT_BOLD, 
                                        bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY, relief="solid", bd=1, padx=8, pady=6)
        
        self.ent_duration = tk.Entry(self.duration_frame, font=theme.FONT_MONO)
        self.ent_duration.pack(fill="x", pady=4)
        theme.apply_entry_theme(self.ent_duration)

        # Apply initial layout sizing
        self.apply_layout(self.wide_mode)
        
        # Toggle options views based on loaded default types
        self.toggle_wp_settings()

    def apply_layout(self, is_wide):
        """Redraws and grids editor components depending on container panel width."""
        
        # 1. Joint target position grids
        self.joint_frame.columnconfigure(0, weight=1)
        if is_wide:
            self.joint_frame.columnconfigure(1, weight=1)
            for i, f in enumerate(self.joint_frames):
                row = i // 2
                col = i % 2
                f.grid_forget()
                f.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
        else:
            self.joint_frame.columnconfigure(1, weight=0)
            for i, f in enumerate(self.joint_frames):
                f.grid_forget()
                f.grid(row=i, column=0, sticky="nsew", padx=4, pady=3)

        # 2. Max Velocities grids
        self.frame_wp_vels.columnconfigure(0, weight=1)
        if is_wide:
            self.frame_wp_vels.columnconfigure(1, weight=1)
            for i, f in enumerate(self.vel_frames):
                row = i // 2
                col = i % 2
                f.grid_forget()
                f.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
        else:
            self.frame_wp_vels.columnconfigure(1, weight=0)
            for i, f in enumerate(self.vel_frames):
                f.grid_forget()
                f.grid(row=i, column=0, sticky="nsew", padx=4, pady=3)

    def on_resize(self, event):
        """Binds to container Configure to adapt layout responsively."""
        if event.widget != self:
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
        lbl = tk.Label(
            parent, text=text, font=("Arial", 8, "bold"),
            bg=theme.BG_INPUT, fg=theme.TEXT_MUTED,
            relief="flat", bd=0, pady=8, cursor="hand2"
        )
        
        def on_enter(e):
            if self.inspector_state != "disabled" and self.wp_type_var.get() != value:
                lbl.config(bg=theme.BORDER_COLOR, fg=theme.TEXT_PRIMARY)
                
        def on_leave(e):
            if self.inspector_state != "disabled" and self.wp_type_var.get() != value:
                lbl.config(bg=theme.BG_INPUT, fg=theme.TEXT_MUTED)
                
        def on_click(e):
            if self.inspector_state != "disabled":
                self.set_wp_type(value)
                
        lbl.bind("<Enter>", on_enter)
        lbl.bind("<Leave>", on_leave)
        lbl.bind("<Button-1>", on_click)
        return lbl

    def set_wp_type(self, value):
        """Saves selection state, updates highlight colors and swaps velocity visibility dynamically."""
        self.wp_type_var.set(value)
        self.update_segment_styles()
        self.toggle_wp_settings()

    def update_segment_styles(self):
        """Renders solid accent cyan backgrounds on active toggle buttons and grey on disabled entries."""
        mapping = {
            "action": self.lbl_action,
            "angularwaypoint": self.lbl_waypoint,
            "pause": self.lbl_pause
        }
        for val, lbl in mapping.items():
            if self.inspector_state == "disabled":
                lbl.config(bg=theme.BG_INPUT, fg=theme.TEXT_MUTED, cursor="arrow")
            else:
                lbl.config(cursor="hand2")
                if self.wp_type_var.get() == val:
                    lbl.config(bg=theme.ACCENT_CYBER, fg=theme.BG_MAIN)
                else:
                    lbl.config(bg=theme.BG_INPUT, fg=theme.TEXT_MUTED)

    def bind_commands(self, commands):
        """Binds commands relating to Column 3 operations."""
        self.btn_preview.config(command=commands.get("preview_pose"))
        self.btn_save_settings.config(command=commands.get("save_settings"))
        self.btn_append_new.config(command=commands.get("append_pose"))

    def _set_inspector_state(self, state):
        """Enables or disables editor elements depending on selection state."""
        self.inspector_state = state
        tk_state = tk.NORMAL if state == "normal" else tk.DISABLED
        
        # Simple list of elements
        widgets = [self.ent_duration] + self.ent_wp_vels + self.insp_entries + [
            self.btn_save_settings, self.btn_preview, self.btn_append_new
        ]
        
        for w in widgets: 
            w.config(state=tk_state)
            
        # Update colors on disabled to keep the modern flat look
        if state == "disabled":
            self.btn_preview.config(bg=theme.BORDER_COLOR, fg=theme.TEXT_MUTED)
            self.btn_save_settings.config(bg=theme.BORDER_COLOR, fg=theme.TEXT_MUTED)
            self.btn_append_new.config(bg=theme.BORDER_COLOR, fg=theme.TEXT_MUTED)
        else:
            self.btn_preview.config(bg=theme.ACCENT_YELLOW, fg=theme.BG_MAIN)
            self.btn_save_settings.config(bg=theme.ACCENT_GREEN, fg=theme.BG_MAIN)
            self.btn_append_new.config(bg=theme.ACCENT_CYBER, fg=theme.TEXT_PRIMARY)

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
        self.lbl_inspector_title.config(text="No Waypoint Selected", fg=theme.TEXT_MUTED, font=theme.FONT_NORMAL)

    def load_inspector_data(self, data, index):
        """Populates fields from selected row dictionaries."""
        self._set_inspector_state("normal")
        self.lbl_inspector_title.config(text=f"Selected Waypoint: #{index}", fg=theme.ACCENT_CYBER, font=theme.FONT_TITLE)
        
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

    def enter_bulk_edit_mode(self, indices):
        """Enables a bulk-edit state for editing duration across multiple waypoints."""
        self._set_inspector_state("normal")
        self.lbl_inspector_title.config(
            text=f"Bulk-Editing {len(indices)} Waypoints", 
            fg=theme.ACCENT_ORANGE, font=theme.FONT_TITLE
        )
        
        # Disable elements that shouldn't be edited in bulk (type, velocities, coordinates, preview, append)
        self.inspector_state = "disabled"
        self.update_segment_styles()
        
        disable_widgets = [
            self.btn_preview, self.btn_append_new
        ] + self.ent_wp_vels + self.insp_entries
        
        for w in disable_widgets:
            w.config(state=tk.DISABLED)
            
        self.btn_preview.config(bg=theme.BORDER_COLOR, fg=theme.TEXT_MUTED)
        self.btn_append_new.config(bg=theme.BORDER_COLOR, fg=theme.TEXT_MUTED)
        
        # Clear duration and target inputs
        self.ent_duration.config(state=tk.NORMAL)
        self.ent_duration.delete(0, tk.END)
        self.ent_duration.insert(0, "3.0")
        self.ent_duration.focus_set()
        
        # Clear joint variables
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
