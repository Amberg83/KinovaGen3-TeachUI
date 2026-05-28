import tkinter as tk
import customtkinter as ctk
from view import theme
from view.widgets import ToolTip

class LiveStatePanel(ctk.CTkFrame):
    """Encapsulates Column 1: Live State displays, telemetry updates, and admittance controls in responsive dark flat style."""
    def __init__(self, parent, **kwargs):
        kwargs.pop("text", None)
        super().__init__(parent, fg_color=theme.BG_MAIN, corner_radius=0, **kwargs)
        
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
        # self.bind("<Configure>", self.on_resize)  # Driven directly by parent MainView

    def setup_ui(self):
        # Panel Title Header
        self.lbl_panel_header = theme.make_label(
            self, text="1. LIVE STATE (READ ONLY)", font=theme.FONT_TITLE,
            fg_color=theme.BG_HEADER, text_color=theme.ACCENT_CYBER,
            height=32, corner_radius=0
        )
        self.lbl_panel_header.pack(fill="x", pady=(0, 6))

        # ---------------- PINNED BOTTOM FRAME (Always visible on baseline) ----------------
        self.bottom_frame = ctk.CTkFrame(self, fg_color=theme.BG_CARD, corner_radius=4)
        self.bottom_frame.pack(side="bottom", fill="x", pady=(6, 0))

        # Button to move robot to default position
        self.btn_default_pose = theme.make_flat_button(
            self.bottom_frame, text=" Move to Default Position", image=theme.get_icon("play", tint=theme.BG_MAIN), compound="left",
            bg_color=theme.ACCENT_CYBER, fg_color=theme.BG_MAIN, hover_bg=theme.ACCENT_CYBER_HOVER
        )
        self.btn_default_pose.pack(fill="x", padx=10, pady=(10, 6))
        ToolTip(self.btn_default_pose, "Move robot back to its starting default pose")

        # Admittance Control Panel inside Bottom Frame
        self.adm_frame = theme.SectionFrame(self.bottom_frame, text="Admittance Control")
        self.adm_frame.pack(fill="x", pady=(0, 6))

        # Premium Segmented Control for Admittance Modes
        self.adm_type_var = ctk.StringVar(value="Disabled")
        
        # High-contrast border wrapper for custom flat segmented bar
        self.adm_segmented_frame = ctk.CTkFrame(self.adm_frame.content, fg_color=theme.BORDER_COLOR, corner_radius=4)
        self.adm_segmented_frame.pack(fill="x", pady=4, padx=5)
        
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
            bg_color=theme.ACCENT_GREEN, fg_color=theme.BG_MAIN, hover_bg="#059669"
        )
        self.btn_capture.pack(fill="x", side="bottom", padx=10, pady=10)
        ToolTip(self.btn_capture, "Capture current joint & cartesian positions (Ctrl+Space)")

        # ---------------- SCROLLABLE TOP CONTAINER ----------------
        self.scrollable_content = ctk.CTkScrollableFrame(
            self, fg_color=theme.BG_CARD, corner_radius=4,
            scrollbar_button_color=theme.BORDER_COLOR,
            scrollbar_button_hover_color=theme.ACCENT_CYBER
        )
        self.scrollable_content.pack(side="top", fill="both", expand=True)

        # ---------------- SECTION 1: JOINT TELEMETRY (Inside Scrollable Content) ----------------
        self.joint_frame = theme.SectionFrame(self.scrollable_content, text="Joint Positions")
        self.joint_frame.pack(fill="x", pady=(0, 6))
        
        for i in range(6):
            f = ctk.CTkFrame(self.joint_frame.content, fg_color="transparent")
            theme.make_label(f, text=f"J{i+1}:", font=theme.FONT_BOLD, fg_color="transparent", text_color=theme.TEXT_MUTED, width=30, anchor="w").pack(side="left")
            
            var = ctk.StringVar(value="0.00 °")
            ent = ctk.CTkEntry(
                f, textvariable=var, font=theme.FONT_MONO, state="readonly", width=100, height=28,
                fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER_COLOR, corner_radius=4
            )
            ent.pack(side="right", fill="x", expand=True, padx=(4, 0))
            self.live_joint_vars.append(var)
            self.joint_frames.append(f)

        # ---------------- SECTION 2: CARTESIAN POSE (Inside Scrollable Content) ----------------
        self.cart_frame = theme.SectionFrame(self.scrollable_content, text="Cartesian Pose")
        self.cart_frame.pack(fill="x", pady=6)
        
        axes = ["X", "Y", "Z", "Rx", "Ry", "Rz"]
        for i, axis in enumerate(axes):
            f = ctk.CTkFrame(self.cart_frame.content, fg_color="transparent")
            theme.make_label(f, text=f"{axis}:", font=theme.FONT_BOLD, fg_color="transparent", text_color=theme.TEXT_MUTED, width=30, anchor="w").pack(side="left")
            
            var = ctk.StringVar(value="0.000")
            ent = ctk.CTkEntry(
                f, textvariable=var, font=theme.FONT_MONO, state="readonly", width=100, height=28,
                fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY, border_color=theme.BORDER_COLOR, corner_radius=4
            )
            ent.pack(side="right", fill="x", expand=True, padx=(4, 0))
            self.live_cart_vars[axis] = var
            self.cart_frames.append(f)

        # ---------------- SECTION 3: ARM DIAGNOSTICS (Inside Scrollable Content) ----------------
        self.diag_frame = theme.SectionFrame(self.scrollable_content, text="Arm Diagnostics")
        self.diag_frame.pack(fill="both", expand=True, pady=6)

        # Status Grid
        self.status_grid = ctk.CTkFrame(self.diag_frame.content, fg_color="transparent")
        self.status_grid.pack(fill="x", pady=(0, 4))
        self.status_grid.columnconfigure(0, weight=1)
        self.status_grid.columnconfigure(1, weight=1)

        self.f_mode = ctk.CTkFrame(self.status_grid, fg_color="transparent")
        theme.make_label(self.f_mode, text="Mode: ", font=theme.FONT_BOLD, fg_color="transparent", text_color=theme.TEXT_MUTED).pack(side="left")
        self.lbl_ctrl_mode = theme.make_label(self.f_mode, text="Normal/Disabled", font=("Arial", 9, "bold"), fg_color="transparent", text_color=theme.ACCENT_CYBER)
        self.lbl_ctrl_mode.pack(side="left")

        self.f_state = ctk.CTkFrame(self.status_grid, fg_color="transparent")
        theme.make_label(self.f_state, text="State: ", font=theme.FONT_BOLD, fg_color="transparent", text_color=theme.TEXT_MUTED).pack(side="left")
        self.lbl_active_state = theme.make_label(self.f_state, text="Ready (Idle)", font=("Arial", 9, "bold"), fg_color="transparent", text_color=theme.ACCENT_GREEN)
        self.lbl_active_state.pack(side="left")

        # Compact lists display using labels as micro-badges
        self.metrics_frame = ctk.CTkFrame(self.diag_frame.content, fg_color="transparent")
        self.metrics_frame.pack(fill="both", expand=True, pady=4)

        def make_metric_row_badges(parent, title):
            f = ctk.CTkFrame(parent, fg_color="transparent")
            f.pack(fill="x", pady=4)
            
            # Pack label above the badges
            theme.make_label(f, text=title, font=theme.FONT_BOLD, fg_color="transparent", text_color=theme.TEXT_MUTED).pack(anchor="w")
            
            # Badges container frame underneath
            badges_frame = ctk.CTkFrame(f, fg_color="transparent")
            badges_frame.pack(fill="x", pady=(2, 0))
            
            labels = []
            for j in range(6):
                lbl = theme.make_label(
                    badges_frame, text="-", font=("Consolas", 8), fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY,
                    height=20, corner_radius=4
                )
                lbl.pack(side="left", fill="x", expand=True, padx=1)
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

        # 2. Update Cartesian pose grids
        self.cart_frame.content.columnconfigure(0, weight=1)
        if is_wide:
            self.cart_frame.content.columnconfigure(1, weight=1)
            for i, f in enumerate(self.cart_frames):
                row = i // 2
                col = i % 2
                f.grid_forget()
                f.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
        else:
            self.cart_frame.content.columnconfigure(1, weight=0)
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
        """Builds a custom label-based segmented button with flat styling and hover bindings."""
        lbl = theme.make_label(
            parent, text=text, font=("Arial", 8, "bold"),
            fg_color=theme.BG_INPUT, text_color=theme.TEXT_MUTED,
            pady=8, corner_radius=0
        )
        lbl.configure(cursor="hand2")
        
        def on_enter(e):
            if self.adm_type_var.get() != value:
                lbl.configure(fg_color=theme.BORDER_COLOR, text_color=theme.TEXT_PRIMARY)
                
        def on_leave(e):
            if self.adm_type_var.get() != value:
                lbl.configure(fg_color=theme.BG_INPUT, text_color=theme.TEXT_MUTED)
                
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
                lbl.configure(fg_color=theme.ACCENT_CYBER, text_color=theme.BG_MAIN)
            else:
                lbl.configure(fg_color=theme.BG_INPUT, text_color=theme.TEXT_MUTED)

    def bind_commands(self, capture_pose_cb, apply_admittance_cb, move_default_cb):
        """Binds commands relating to Column 1 operations."""
        self.btn_capture.configure(command=capture_pose_cb)
        self.btn_default_pose.configure(command=move_default_cb)
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
        self.lbl_ctrl_mode.configure(text=mode_str, text_color=theme.ACCENT_CYBER if state.control_mode in [6, 7, 8] else theme.TEXT_MUTED)

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
        self.lbl_active_state.configure(text=state_str, text_color=theme.ACCENT_RED if state.active_state == 4 else theme.ACCENT_GREEN)

        # Update Temps micro-badges
        if state.joint_temperatures:
            for j, t in enumerate(state.joint_temperatures):
                if j < len(self.temp_labels):
                    self.temp_labels[j].configure(text=f"{t:.0f}°")
        else:
            for lbl in self.temp_labels: lbl.configure(text="-")

        # Update Currents micro-badges
        if state.joint_currents:
            for j, c in enumerate(state.joint_currents):
                if j < len(self.current_labels):
                    self.current_labels[j].configure(text=f"{c:.1f}")
        else:
            for lbl in self.current_labels: lbl.configure(text="-")

        # Update Torques micro-badges
        if state.joint_torques:
            for j, t in enumerate(state.joint_torques):
                if j < len(self.torque_labels):
                    self.torque_labels[j].configure(text=f"{t:.1f}")
        else:
            for lbl in self.torque_labels: lbl.configure(text="-")
