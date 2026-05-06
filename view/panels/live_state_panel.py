import tkinter as tk
from tkinter import ttk
from view import theme

class LiveStatePanel(ttk.LabelFrame):
    """Encapsulates Column 1: Live State displays, telemetry updates, and admittance controls in dark flat style."""
    def __init__(self, parent, **kwargs):
        kwargs.setdefault("text", "1. Live State (Read Only)")
        # We use style="TLabelframe" to get the dark card backgrounds
        super().__init__(parent, style="TLabelframe", **kwargs)
        
        self.live_joint_vars = []
        self.live_cart_vars = {}
        
        self.setup_ui()

    def setup_ui(self):
        # Notebook for Live Telemetry Tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, pady=(0, 10))

        # Tab 1: Joints
        tab_joints = tk.Frame(self.notebook, bg=theme.BG_CARD)
        self.notebook.add(tab_joints, text="Joints")
        for i in range(6):
            f = tk.Frame(tab_joints, bg=theme.BG_CARD)
            f.pack(fill="x", pady=6, padx=10)
            tk.Label(f, text=f"J{i+1}:", font=theme.FONT_BOLD, bg=theme.BG_CARD, fg=theme.TEXT_MUTED, width=5, anchor="w").pack(side="left")
            
            var = tk.StringVar(value="0.00 °")
            ent = tk.Entry(f, textvariable=var, font=theme.FONT_MONO, state="readonly", width=12)
            ent.pack(side="right")
            ent.config(readonlybackground=theme.BG_INPUT, fg=theme.TEXT_PRIMARY, relief="flat", bd=1,
                       highlightbackground=theme.BORDER_COLOR, highlightthickness=1)
            self.live_joint_vars.append(var)

        # Tab 2: Cartesian
        tab_cart = tk.Frame(self.notebook, bg=theme.BG_CARD)
        self.notebook.add(tab_cart, text="Cartesian")
        for axis in ["X", "Y", "Z", "Rx", "Ry", "Rz"]:
            f = tk.Frame(tab_cart, bg=theme.BG_CARD)
            f.pack(fill="x", pady=6, padx=10)
            tk.Label(f, text=f"{axis}:", font=theme.FONT_BOLD, bg=theme.BG_CARD, fg=theme.TEXT_MUTED, width=5, anchor="w").pack(side="left")
            
            var = tk.StringVar(value="0.00")
            ent = tk.Entry(f, textvariable=var, font=theme.FONT_MONO, state="readonly", width=12)
            ent.pack(side="right")
            ent.config(readonlybackground=theme.BG_INPUT, fg=theme.TEXT_PRIMARY, relief="flat", bd=1,
                       highlightbackground=theme.BORDER_COLOR, highlightthickness=1)
            self.live_cart_vars[axis] = var

        # Tab 3: Diagnostics
        tab_diag = tk.Frame(self.notebook, bg=theme.BG_CARD)
        self.notebook.add(tab_diag, text="Diag")
        self.lbl_diag = tk.Label(tab_diag, text="Waiting for telemetry...", bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY,
                                 justify="left", font=theme.FONT_MONO_SMALL)
        self.lbl_diag.pack(anchor="nw", padx=10, pady=10)

        # Admittance Control Panel Frame
        # In order to keep borders clean and flat, we build a flat label frame using tk.LabelFrame with our borders
        adm_frame = tk.LabelFrame(self, text="Admittance Control", font=theme.FONT_BOLD, 
                                  bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY, relief="solid", bd=1, padx=10, pady=8)
        adm_frame.pack(fill="x", pady=(5, 10))

        self.cb_admittance = ttk.Combobox(adm_frame, values=["Disabled", "Cartesian", "Joint", "Null-Space"], 
                                         state="readonly", font=theme.FONT_NORMAL, style="TCombobox")
        self.cb_admittance.set("Disabled")
        self.cb_admittance.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.btn_apply_admittance = theme.make_flat_button(
            adm_frame, text="Apply Mode", bg_color=theme.ACCENT_CYBER, 
            fg_color=theme.TEXT_PRIMARY, hover_bg=theme.ACCENT_CYBER_HOVER, 
            padx=12, pady=3
        )
        self.btn_apply_admittance.pack(side="right")

        # Capture Button (Styled with green/mint colors)
        self.btn_capture = theme.make_flat_button(
            self, text="➕ Capture Current Pose", bg_color=theme.ACCENT_GREEN, 
            fg_color=theme.BG_MAIN, hover_bg="#059669", 
            font_style=theme.FONT_EMOJI_LARGE, height=2
        )
        self.btn_capture.pack(fill="x", side="bottom", pady=5)

    def bind_commands(self, capture_pose_cb, apply_admittance_cb):
        """Binds commands relating to Column 1 operations."""
        self.btn_capture.config(command=capture_pose_cb)
        self.btn_apply_admittance.config(command=apply_admittance_cb)

    def get_live_poses(self):
        """Retrieves raw numeric joint angles in degrees from variables."""
        try:
            return [float(var.get().replace(" °", "")) for var in self.live_joint_vars]
        except ValueError:
            return None

    def get_selected_admittance_mode(self):
        """Gets active combobox selection."""
        return self.cb_admittance.get()

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
                
        # Update Diag
        ctrl_modes = {
            0: "Normal/Disabled", 1: "Ang. Joystick", 2: "Cart. Joystick",
            4: "Ang. Trajectory", 5: "Cart. Trajectory",
            6: "CARTESIAN ADMITTANCE", 7: "JOINT ADMITTANCE",
            8: "NULL-SPACE ADMITTANCE", 9: "Force Control"
        }
        mode_str = ctrl_modes.get(state.control_mode, f"Unknown ({state.control_mode})")

        # States Mapping
        active_states = {
            0: "Unknown", 1: "Ready (Idle)", 2: "In Fault", 3: "Maintenance",
            4: "Paused", 5: "Executing Action", 6: "Initialization"
        }
        state_str = active_states.get(state.active_state, f"Code {state.active_state}")

        # Metrics Mapping
        temps_str = "|".join([f"{t:.1f}" for t in state.joint_temperatures]) if state.joint_temperatures else "N/A"
        currents_str = "|".join([f"{c:.2f}" for c in state.joint_currents]) if state.joint_currents else "N/A"
        torques_str = "|".join([f"{t:.1f}" for t in state.joint_torques]) if state.joint_torques else "N/A"
        
        # Fault State
        if state.has_fault:
            fault_str = f"{state.has_fault} (Bank A:{state.fault_bank_a} | Bank B:{state.fault_bank_b})"
        else:
            fault_str = f"{state.has_fault}"

        diag_text = (
            f"Control Mode: {mode_str}\n"
            f"Active State: {state_str}\n"
            f"Joint Temperatures (°C):\n{temps_str}\n"
            f"Joint Currents (A):\n{currents_str}\n"
            f"Joint Torques (Nm):\n{torques_str}\n"
            f"Faults:\n{fault_str}"
        )
        self.lbl_diag.config(text=diag_text)
