import tkinter as tk
from tkinter import ttk
from view import theme
from view.widgets import ToolTip

class LiveStatePanel(ttk.LabelFrame):
    """Encapsulates Column 1: Live State displays, telemetry updates, and admittance controls in responsive dark flat style."""
    def __init__(self, parent, **kwargs):
        kwargs.setdefault("text", "1. Live State (Read Only)")
        super().__init__(parent, style="TLabelframe", **kwargs)
        
        self.live_joint_vars = []
        self.live_cart_vars = {}
        self.joint_frames = []
        self.cart_frames = []
        self.temp_labels = []
        self.current_labels = []
        self.torque_labels = []
        self._apply_admittance_cb = None
        
        self.wide_mode = True 
        
        self.setup_ui()
        self.bind("<Configure>", self.on_resize)

    def setup_ui(self):
        # ---------------- PINNED BOTTOM FRAME (Always visible on baseline) ----------------
        self.bottom_frame = tk.Frame(self, bg=theme.BG_CARD)
        self.bottom_frame.pack(side="bottom", fill="x", pady=(6, 0))

        # Admittance Control Panel inside Bottom Frame
        self.adm_frame = tk.LabelFrame(self.bottom_frame, text="Admittance Control", font=theme.FONT_BOLD, 
                                  bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY, relief="solid", bd=1, padx=8, pady=4)
        self.adm_frame.pack(fill="x", pady=(0, 6))

        # Premium Segmented Control for Admittance Modes
        self.adm_type_var = tk.StringVar(value="Disabled")
        
        # High-contrast border wrapper for custom flat segmented bar
        self.adm_segmented_frame = tk.Frame(self.adm_frame, bg=theme.BORDER_COLOR, padx=1, pady=1)
        self.adm_segmented_frame.pack(fill="x", pady=4)
        
        # Grid weights to ensure equal column widths
        self.adm_segmented_frame.columnconfigure(0, weight=1)
        self.adm_segmented_frame.columnconfigure(1, weight=1)
        self.adm_segmented_frame.columnconfigure(2, weight=1)

        # Custom label-based segment buttons to bypass Windows beveled OS defaults
        self.lbl_disabled = self.make_segment_btn(self.adm_segmented_frame, "DISABLED", "Disabled")
        self.lbl_disabled.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)

        self.lbl_cartesian = self.make_segment_btn(self.adm_segmented_frame, "CARTESIAN", "Cartesian")
        self.lbl_cartesian.grid(row=0, column=1, sticky="nsew", padx=1, pady=1)

        self.lbl_joint = self.make_segment_btn(self.adm_segmented_frame, "JOINT", "Joint")
        self.lbl_joint.grid(row=0, column=2, sticky="nsew", padx=1, pady=1)

        # Draw active selection state
        self.update_segment_styles()

        # Capture Button inside Bottom Frame
        self.btn_capture = theme.make_flat_button(
            self.bottom_frame, text=" Capture Current Pose", image=theme.get_icon("add_waypoint", tint=theme.BG_MAIN), compound="left",
            bg_color=theme.ACCENT_GREEN, fg_color=theme.BG_MAIN, hover_bg="#059669", 
            font_style=theme.FONT_BOLD, pady=8
        )
        self.btn_capture.pack(fill="x", side="bottom")
        ToolTip(self.btn_capture, "Capture current joint & cartesian positions (Ctrl+Space)")

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

        # ---------------- SECTION 1: JOINT TELEMETRY (Inside Scrollable Content) ----------------
        self.joint_frame = tk.LabelFrame(self.scrollable_content, text="Joint Positions", font=theme.FONT_BOLD, 
                                    bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY, relief="solid", bd=1, padx=8, pady=6)
        self.joint_frame.pack(fill="x", pady=(0, 6))
        
        for i in range(6):
            f = tk.Frame(self.joint_frame, bg=theme.BG_CARD)
            tk.Label(f, text=f"J{i+1}:", font=theme.FONT_BOLD, bg=theme.BG_CARD, fg=theme.TEXT_MUTED, width=3, anchor="w").pack(side="left")
            
            var = tk.StringVar(value="0.00 °")
            ent = tk.Entry(f, textvariable=var, font=theme.FONT_MONO, state="readonly", width=10)
            ent.pack(side="right", fill="x", expand=True, padx=(4, 0))
            ent.config(readonlybackground=theme.BG_INPUT, fg=theme.TEXT_PRIMARY, relief="flat", bd=1,
                       highlightbackground=theme.BORDER_COLOR, highlightthickness=1)
            self.live_joint_vars.append(var)
            self.joint_frames.append(f)

        # ---------------- SECTION 2: CARTESIAN POSE (Inside Scrollable Content) ----------------
        self.cart_frame = tk.LabelFrame(self.scrollable_content, text="Cartesian Pose", font=theme.FONT_BOLD, 
                                   bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY, relief="solid", bd=1, padx=8, pady=6)
        self.cart_frame.pack(fill="x", pady=6)
        
        axes = ["X", "Y", "Z", "Rx", "Ry", "Rz"]
        for i, axis in enumerate(axes):
            f = tk.Frame(self.cart_frame, bg=theme.BG_CARD)
            tk.Label(f, text=f"{axis}:", font=theme.FONT_BOLD, bg=theme.BG_CARD, fg=theme.TEXT_MUTED, width=3, anchor="w").pack(side="left")
            
            var = tk.StringVar(value="0.000")
            ent = tk.Entry(f, textvariable=var, font=theme.FONT_MONO, state="readonly", width=10)
            ent.pack(side="right", fill="x", expand=True, padx=(4, 0))
            ent.config(readonlybackground=theme.BG_INPUT, fg=theme.TEXT_PRIMARY, relief="flat", bd=1,
                       highlightbackground=theme.BORDER_COLOR, highlightthickness=1)
            self.live_cart_vars[axis] = var
            self.cart_frames.append(f)

        # ---------------- SECTION 3: ARM DIAGNOSTICS (Inside Scrollable Content) ----------------
        self.diag_frame = tk.LabelFrame(self.scrollable_content, text="Arm Diagnostics", font=theme.FONT_BOLD, 
                                   bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY, relief="solid", bd=1, padx=8, pady=6)
        self.diag_frame.pack(fill="both", expand=True, pady=6)

        # Status Grid
        self.status_grid = tk.Frame(self.diag_frame, bg=theme.BG_CARD)
        self.status_grid.pack(fill="x", pady=(0, 4))
        self.status_grid.columnconfigure(0, weight=1)
        self.status_grid.columnconfigure(1, weight=1)

        self.f_mode = tk.Frame(self.status_grid, bg=theme.BG_CARD)
        tk.Label(self.f_mode, text="Mode:", font=theme.FONT_BOLD, bg=theme.BG_CARD, fg=theme.TEXT_MUTED).pack(anchor="w")
        self.lbl_ctrl_mode = tk.Label(self.f_mode, text="Normal/Disabled", font=("Arial", 9, "bold"), bg=theme.BG_CARD, fg=theme.ACCENT_CYBER)
        self.lbl_ctrl_mode.pack(anchor="w")

        self.f_state = tk.Frame(self.status_grid, bg=theme.BG_CARD)
        tk.Label(self.f_state, text="State:", font=theme.FONT_BOLD, bg=theme.BG_CARD, fg=theme.TEXT_MUTED).pack(anchor="w")
        self.lbl_active_state = tk.Label(self.f_state, text="Ready (Idle)", font=("Arial", 9, "bold"), bg=theme.BG_CARD, fg=theme.ACCENT_GREEN)
        self.lbl_active_state.pack(anchor="w")

        # Compact lists display using labels as micro-badges
        self.metrics_frame = tk.Frame(self.diag_frame, bg=theme.BG_CARD)
        self.metrics_frame.pack(fill="both", expand=True, pady=4)

        def make_metric_row_badges(parent, title):
            f = tk.Frame(parent, bg=theme.BG_CARD)
            f.pack(fill="x", pady=3)
            tk.Label(f, text=title, font=theme.FONT_BOLD, bg=theme.BG_CARD, fg=theme.TEXT_MUTED, width=11, anchor="w").pack(side="left")
            
            badges_frame = tk.Frame(f, bg=theme.BG_CARD)
            badges_frame.pack(side="left", fill="x", expand=True)
            
            labels = []
            for j in range(6):
                lbl = tk.Label(
                    badges_frame, text="-", font=("Consolas", 8), bg=theme.BG_INPUT, fg=theme.TEXT_PRIMARY,
                    relief="solid", bd=1, highlightthickness=0, width=4, pady=1
                )
                lbl.pack(side="left", padx=1)
                lbl.config(highlightbackground=theme.BORDER_COLOR)
                labels.append(lbl)
            return labels

        self.temp_labels = make_metric_row_badges(self.metrics_frame, "Temps (°C):")
        self.current_labels = make_metric_row_badges(self.metrics_frame, "Currents (A):")
        self.torque_labels = make_metric_row_badges(self.metrics_frame, "Torques (Nm):")

        # Apply initial layout positioning
        self.apply_layout(self.wide_mode)

    def apply_layout(self, is_wide):
        """Redraws and grids components depending on container panel width."""
        
        # 1. Update Joint position grids
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

        # 2. Update Cartesian pose grids
        self.cart_frame.columnconfigure(0, weight=1)
        if is_wide:
            self.cart_frame.columnconfigure(1, weight=1)
            for i, f in enumerate(self.cart_frames):
                row = i // 2
                col = i % 2
                f.grid_forget()
                f.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
        else:
            self.cart_frame.columnconfigure(1, weight=0)
            for i, f in enumerate(self.cart_frames):
                f.grid_forget()
                f.grid(row=i, column=0, sticky="nsew", padx=4, pady=3)

        # 3. Update Diagnostics Mode/State Placement
        if is_wide:
            self.f_mode.grid_forget()
            self.f_state.grid_forget()
            self.f_mode.grid(row=0, column=0, sticky="nw", padx=2, pady=2)
            self.f_state.grid(row=0, column=1, sticky="nw", padx=2, pady=2)
        else:
            self.f_mode.grid_forget()
            self.f_state.grid_forget()
            self.f_mode.grid(row=0, column=0, sticky="nw", padx=2, pady=2)
            self.f_state.grid(row=1, column=0, sticky="nw", padx=2, pady=(6, 2))

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
        """Builds a custom label-based segmented button with flat styling and hover bindings."""
        lbl = tk.Label(
            parent, text=text, font=("Arial", 8, "bold"),
            bg=theme.BG_INPUT, fg=theme.TEXT_MUTED,
            relief="flat", bd=0, pady=8, cursor="hand2"
        )
        
        def on_enter(e):
            if self.adm_type_var.get() != value:
                lbl.config(bg=theme.BORDER_COLOR, fg=theme.TEXT_PRIMARY)
                
        def on_leave(e):
            if self.adm_type_var.get() != value:
                lbl.config(bg=theme.BG_INPUT, fg=theme.TEXT_MUTED)
                
        def on_click(e):
            self.set_admittance_mode(value)
            
        lbl.bind("<Enter>", on_enter)
        lbl.bind("<Leave>", on_leave)
        lbl.bind("<Button-1>", on_click)
        return lbl

    def set_admittance_mode(self, value):
        """Sets the active selection, updates button highlights, and invokes command callbacks."""
        self.adm_type_var.set(value)
        self.update_segment_styles()
        self.on_admittance_toggle()

    def update_segment_styles(self):
        """Renders solid accent selection backgrounds on active toggles."""
        mapping = {
            "Disabled": self.lbl_disabled,
            "Cartesian": self.lbl_cartesian,
            "Joint": self.lbl_joint
        }
        for val, lbl in mapping.items():
            if self.adm_type_var.get() == val:
                lbl.config(bg=theme.ACCENT_CYBER, fg=theme.BG_MAIN)
            else:
                lbl.config(bg=theme.BG_INPUT, fg=theme.TEXT_MUTED)

    def bind_commands(self, capture_pose_cb, apply_admittance_cb):
        """Binds commands relating to Column 1 operations."""
        self.btn_capture.config(command=capture_pose_cb)
        self._apply_admittance_cb = apply_admittance_cb

    def on_admittance_toggle(self):
        """Called immediately when any admittance segmented button is clicked."""
        if self._apply_admittance_cb:
            self._apply_admittance_cb()

    def get_live_poses(self):
        """Retrieves raw numeric joint angles in degrees from variables."""
        try:
            return [float(var.get().replace(" °", "")) for var in self.live_joint_vars]
        except ValueError:
            return None

    def get_selected_admittance_mode(self):
        """Gets active admittance selection."""
        return self.adm_type_var.get()

    def update_telemetry(self, state):
        """Updates all readouts safely from state object."""
        # Update Joints
        for i, val in enumerate(state.joint_angles_deg):
            if i < len(self.live_joint_vars):
                self.live_joint_vars[i].set(f"{val:.2f} °")
                
        # Update Cartesian
        if len(state.tcp_position) >= 3 and len(state.tcp_orientation) >= 3:
            vals = state.tcp_position + state.tcp_orientation
            keys = ["X", "Y", "Z", "Rx", "Ry", "Rz"]
            for k, v in zip(keys, vals):
                self.live_cart_vars[k].set(f"{v:.3f}")
                
        # Update Control Mode
        ctrl_modes = {
            0: "Normal/Disabled",        # UNSPECIFIED_CONTROL_MODE
            1: "Ang. Joystick",          # ANGULAR_JOYSTICK
            2: "Cart. Joystick",         # CARTESIAN_JOYSTICK
            4: "Ang. Trajectory",        # ANGULAR_TRAJECTORY
            5: "Cart. Trajectory",       # CARTESIAN_TRAJECTORY
            6: "CARTESIAN ADMITTANCE",   # CARTESIAN_ADMITTANCE
            7: "JOINT ADMITTANCE",       # JOINT_ADMITTANCE
            8: "NULL-SPACE ADMITTANCE",  # NULL_SPACE_ADMITTANCE
            10: "Force Control",         # FORCE_CONTROL
            11: "Force Control (Restr.)",# FORCE_CONTROL_MOTION_RESTRICTED
            12: "Cart. Waypoint Traj.",  # CARTESIAN_WAYPOINT_TRAJECTORY
            13: "Idle"                   # IDLE
        }
        mode_str = ctrl_modes.get(state.control_mode, f"Unknown ({state.control_mode})")
        self.lbl_ctrl_mode.config(text=mode_str, fg=theme.ACCENT_CYBER if state.control_mode in [6, 7, 8] else theme.TEXT_MUTED)

        # Update Active State
        active_states = {
            0: "Unspecified",            # ARMSTATE_UNSPECIFIED
            1: "Base Init",              # ARMSTATE_BASE_INITIALIZATION
            2: "Ready (Idle)",           # ARMSTATE_IDLE
            3: "Initialization",         # ARMSTATE_INITIALIZATION
            4: "In Fault",               # ARMSTATE_IN_FAULT
            5: "Maintenance",            # ARMSTATE_MAINTENANCE
            6: "Low-Level Servoing",     # ARMSTATE_SERVOING_LOW_LEVEL
            7: "Servoing Ready",         # ARMSTATE_SERVOING_READY
            8: "Playing Sequence",       # ARMSTATE_SERVOING_PLAYING_SEQUENCE
            9: "Manual Controlled",      # ARMSTATE_SERVOING_MANUALLY_CONTROLLED (Admittance)
            255: "Reserved"              # ARMSTATE_RESERVED
        }
        state_str = active_states.get(state.active_state, f"Code {state.active_state}")
        self.lbl_active_state.config(text=state_str, fg=theme.ACCENT_RED if state.active_state == 4 else theme.ACCENT_GREEN)

        # Update Temps micro-badges
        if state.joint_temperatures:
            for j, t in enumerate(state.joint_temperatures):
                if j < len(self.temp_labels):
                    self.temp_labels[j].config(text=f"{t:.0f}°")
        else:
            for lbl in self.temp_labels: lbl.config(text="-")

        # Update Currents micro-badges
        if state.joint_currents:
            for j, c in enumerate(state.joint_currents):
                if j < len(self.current_labels):
                    self.current_labels[j].config(text=f"{c:.1f}")
        else:
            for lbl in self.current_labels: lbl.config(text="-")

        # Update Torques micro-badges
        if state.joint_torques:
            for j, t in enumerate(state.joint_torques):
                if j < len(self.torque_labels):
                    self.torque_labels[j].config(text=f"{t:.1f}")
        else:
            for lbl in self.torque_labels: lbl.config(text="-")
