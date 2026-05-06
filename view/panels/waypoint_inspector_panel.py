import tkinter as tk
from tkinter import ttk
from view import theme

class WaypointInspectorPanel(ttk.LabelFrame):
    """Encapsulates Column 3: The Waypoint Inspector form to edit or preview sequence entries, styled in dark flat mode."""
    def __init__(self, parent, **kwargs):
        kwargs.setdefault("text", "3. Waypoint Inspector / Editor")
        super().__init__(parent, style="TLabelframe", **kwargs)
        
        self.wp_type_var = tk.StringVar(value="action")
        self.insp_joint_vars = []
        self.ent_wp_vels = []
        
        self.setup_ui()
        self._set_inspector_state("disabled")

    def setup_ui(self):
        self.lbl_inspector_title = tk.Label(self, text="No Waypoint Selected", font=theme.FONT_NORMAL, bg=theme.BG_CARD, fg=theme.TEXT_MUTED)
        self.lbl_inspector_title.pack(pady=(0, 15))

        tk.Label(self, text="Type:", font=theme.FONT_BOLD, bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY).pack(anchor="w", pady=(0, 5))
        
        # Segmented Control Frame
        type_frame = tk.Frame(self, bg=theme.BORDER_COLOR, padx=1, pady=1) 
        type_frame.pack(fill="x", pady=(0, 10))

        # Modern Segmented toggle styles using standard flat Radiobuttons
        toggle_opts = {
            "variable": self.wp_type_var,
            "indicatoron": 0,               
            "relief": "flat",               
            "bg": theme.BG_INPUT,
            "fg": theme.TEXT_MUTED,
            "selectcolor": theme.ACCENT_CYBER,       
            "activebackground": theme.BORDER_COLOR,  
            "activeforeground": theme.TEXT_PRIMARY,
            "font": ("Arial", 9, "bold"),
            "pady": 8,
            "cursor": "hand2",
            "command": self.toggle_wp_settings
        }

        # Pack segments
        self.rb_action = tk.Radiobutton(type_frame, text="ACTION", value="action", **toggle_opts)
        self.rb_action.pack(side="left", fill="x", expand=True, padx=1)
        
        self.rb_waypoint = tk.Radiobutton(type_frame, text="WAYPOINT", value="angularwaypoint", **toggle_opts)
        self.rb_waypoint.pack(side="left", fill="x", expand=True, padx=1)
        
        self.rb_pause = tk.Radiobutton(type_frame, text="PAUSE", value="pause", **toggle_opts)
        self.rb_pause.pack(side="left", fill="x", expand=True, padx=1)

        tk.Label(self, text="Duration / Wait Time (s):", font=theme.FONT_NORMAL, bg=theme.BG_CARD, fg=theme.TEXT_MUTED).pack(anchor="w", pady=(10, 3))
        self.ent_duration = tk.Entry(self, width=15, font=theme.FONT_MONO)
        self.ent_duration.pack(anchor="w")
        theme.apply_entry_theme(self.ent_duration)

        # Velocities Frame (packed only for angularwaypoint type)
        self.frame_wp_vels = tk.Frame(self, bg=theme.BG_CARD)
        tk.Label(self.frame_wp_vels, text="Max Velocities (°/s):", font=theme.FONT_NORMAL, bg=theme.BG_CARD, fg=theme.TEXT_MUTED).pack(anchor="w", pady=(10, 3))
        
        vel_grid = tk.Frame(self.frame_wp_vels, bg=theme.BG_CARD)
        vel_grid.pack(fill="x")
        for i in range(6):
            tk.Label(vel_grid, text=f"J{i+1}:", font=theme.FONT_BOLD, bg=theme.BG_CARD, fg=theme.TEXT_MUTED).grid(row=i//2, column=(i%2)*4, sticky="w", padx=(0,4))
            ent = tk.Entry(vel_grid, width=6, font=theme.FONT_MONO)
            ent.grid(row=i//2, column=(i%2)*4+1, sticky="w", padx=(0,15), pady=3)
            theme.apply_entry_theme(ent)
            self.ent_wp_vels.append(ent)

        # Joint target positions entry form
        tk.Label(self, text="Joint Angles (°):", font=theme.FONT_BOLD, bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY).pack(anchor="w", pady=(18, 5))
        
        insp_joint_grid = tk.Frame(self, bg=theme.BG_CARD)
        insp_joint_grid.pack(fill="x")
        self.insp_entries = [] # Cache to apply entries settings easily
        for i in range(6):
            tk.Label(insp_joint_grid, text=f"J{i+1}:", font=theme.FONT_BOLD, bg=theme.BG_CARD, fg=theme.TEXT_MUTED).grid(row=i, column=0, sticky="w", pady=4)
            var = tk.StringVar(value="0.0")
            ent = tk.Entry(insp_joint_grid, textvariable=var, width=15, font=theme.FONT_MONO)
            ent.grid(row=i, column=1, sticky="w", padx=8, pady=4)
            theme.apply_entry_theme(ent)
            self.insp_joint_vars.append(var)
            self.insp_entries.append(ent)

        # Bottom Buttons
        self.btn_preview = theme.make_flat_button(
            self, text="▶ Preview this Pose", bg_color=theme.ACCENT_YELLOW, 
            fg_color=theme.BG_MAIN, hover_bg="#eab308", 
            font_style=theme.FONT_EMOJI_LARGE
        )
        self.btn_preview.pack(fill="x", side="bottom", pady=4)
        
        self.btn_save_settings = theme.make_flat_button(
            self, text="💾 Apply & Save to Selected", bg_color=theme.ACCENT_GREEN, 
            fg_color=theme.BG_MAIN, hover_bg="#059669", 
            font_style=theme.FONT_EMOJI_LARGE
        )
        self.btn_save_settings.pack(fill="x", side="bottom", pady=4)

        self.btn_append_new = theme.make_flat_button(
            self, text="➕ Append as New Waypoint", bg_color=theme.ACCENT_CYBER, 
            fg_color=theme.TEXT_PRIMARY, hover_bg=theme.ACCENT_CYBER_HOVER, 
            font_style=theme.FONT_EMOJI_LARGE
        )
        self.btn_append_new.pack(fill="x", side="bottom", pady=4)

    def bind_commands(self, commands):
        """Binds commands relating to Column 3 operations."""
        self.btn_preview.config(command=commands.get("preview_pose"))
        self.btn_save_settings.config(command=commands.get("save_settings"))
        self.btn_append_new.config(command=commands.get("append_pose"))

    def _set_inspector_state(self, state):
        """Enables or disables editor elements depending on selection state."""
        tk_state = tk.NORMAL if state == "normal" else tk.DISABLED
        
        # Simple list of elements
        widgets = [self.ent_duration] + self.ent_wp_vels + self.insp_entries + [
            self.rb_action, self.rb_waypoint, self.rb_pause,
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

        for i in range(6): 
            self.insp_joint_vars[i].set("0.0" if state == "disabled" else self.insp_joint_vars[i].get())

    def toggle_wp_settings(self):
        """Swaps visibility of the angularwaypoint velocity grid dynamically."""
        wp_type = self.wp_type_var.get()
        if wp_type == "angularwaypoint":
            self.frame_wp_vels.pack(anchor="w", after=self.ent_duration, pady=5)
        else:
            self.frame_wp_vels.pack_forget()

    def clear_inspector(self):
        """Resets panel state when no element is selected anymore."""
        self._set_inspector_state("disabled")
        self.lbl_inspector_title.config(text="No Waypoint Selected", fg=theme.TEXT_MUTED, font=theme.FONT_NORMAL)

    def load_inspector_data(self, data, index):
        """Populates fields from selected row dictionaries."""
        self._set_inspector_state("normal")
        self.lbl_inspector_title.config(text=f"Selected Waypoint: #{index}", fg=theme.ACCENT_CYBER, font=theme.FONT_TITLE)
        
        self.wp_type_var.set(data.get("type", "action"))
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
        disable_widgets = [
            self.rb_action, self.rb_waypoint, self.rb_pause,
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
