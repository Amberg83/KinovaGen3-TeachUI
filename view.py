import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog
import re

class ToolTip:
    """Small Hover-Widget to show tooltips for buttons."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        
        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True) # Entfernt den Fensterrahmen
        tw.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(tw, text=self.text, justify='left',
                         background="#ffffe0", relief='solid', borderwidth=1,
                         font=("Arial", 9, "normal"), padx=3, pady=1)
        label.pack(ipadx=1)

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

class RobotView:
    def __init__(self, root):
        self.root = root
        self.root.title("Robot Teach-In Controller (Dashboard)")
        self.root.geometry("1450x900") 
        
        self.commands = {}
        self.is_dialog_open = False
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TButton", font=("Arial", 10))
        style.configure("Treeview.Heading", font=("Arial", 10, "bold"))
        style.configure("TNotebook.Tab", font=("Arial", 10, "bold"), padding=[10, 5])

        self.setup_ui()

    def setup_ui(self):
        # --- HEADER ---
        status_frame = tk.Frame(self.root, bg="#2d2d2d", padx=10, pady=5)
        status_frame.pack(fill="x")
        self.lbl_status = tk.Label(status_frame, text="Status: Initializing...", font=("Arial", 11, "bold"), bg="#2d2d2d", fg="white")
        self.lbl_status.pack(side="left")
        
        btn_frame = tk.Frame(status_frame, bg="#2d2d2d")
        btn_frame.pack(side="right")
        self.btn_reconnect = tk.Button(btn_frame, text="🔄 Reconnect")
        self.btn_reconnect.pack(side="left", padx=5)
        self.btn_clear_faults = tk.Button(btn_frame, text="🧹 Clear Faults", bg="#ffcc99")
        self.btn_clear_faults.pack(side="left", padx=5)

        # --- 3-COLUMN LAYOUT ---
        content_frame = tk.Frame(self.root)
        content_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.paned = ttk.PanedWindow(content_frame, orient=tk.HORIZONTAL)
        self.paned.pack(fill="both", expand=True)

        col1_live = tk.LabelFrame(self.paned, text="1. Live State (Read Only)", font=("Arial", 11, "bold"), padx=10, pady=10)
        col2_seq = tk.LabelFrame(self.paned, text="2. Sequence Timeline", font=("Arial", 11, "bold"), padx=10, pady=10)
        col3_insp = tk.LabelFrame(self.paned, text="3. Waypoint Inspector (Edit)", font=("Arial", 11, "bold"), padx=10, pady=10)

        self.paned.add(col1_live, weight=1)
        self.paned.add(col2_seq, weight=3)
        self.paned.add(col3_insp, weight=1)

        # ==========================================
        # COLUMN 1: LIVE STATE
        # ==========================================
        self.notebook = ttk.Notebook(col1_live)
        self.notebook.pack(fill="both", expand=True, pady=(0, 10))

        # Tab 1: Joints
        tab_joints = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab_joints, text="Joints")
        self.live_joint_vars = []
        for i in range(6):
            f = tk.Frame(tab_joints, bg="white")
            f.pack(fill="x", pady=5, padx=10)
            tk.Label(f, text=f"J{i+1}:", font=("Arial", 11, "bold"), bg="white", width=5, anchor="w").pack(side="left")
            var = tk.StringVar(value="0.00 °")
            tk.Entry(f, textvariable=var, font=("Courier", 12), state="readonly", width=12).pack(side="right")
            self.live_joint_vars.append(var)

        # Tab 2: Cartesian
        tab_cart = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab_cart, text="Cartesian")
        self.live_cart_vars = {}
        for axis in ["X", "Y", "Z", "Rx", "Ry", "Rz"]:
            f = tk.Frame(tab_cart, bg="white")
            f.pack(fill="x", pady=5, padx=10)
            tk.Label(f, text=f"{axis}:", font=("Arial", 11, "bold"), bg="white", width=5, anchor="w").pack(side="left")
            var = tk.StringVar(value="0.00")
            tk.Entry(f, textvariable=var, font=("Courier", 12), state="readonly", width=12).pack(side="right")
            self.live_cart_vars[axis] = var

        # Tab 3: Diagnostics
        tab_diag = tk.Frame(self.notebook, bg="white")
        self.notebook.add(tab_diag, text="Diag")
        self.lbl_diag = tk.Label(tab_diag, text="Waiting for telemetry...", bg="white", justify="left", font=("Courier", 9))
        self.lbl_diag.pack(anchor="nw", padx=10, pady=10)

        # Capture Button
        self.btn_capture = tk.Button(col1_live, text="➕ Capture Current Pose", bg="#008CBA", fg="white", font=("Arial", 12, "bold"), height=2)
        self.btn_capture.pack(fill="x", side="bottom", pady=5)

        # ==========================================
        # COLUMN 2: SEQUENCE TIMELINE
        # ==========================================
        # Toolbar Top
        toolbar_top = tk.Frame(col2_seq)
        toolbar_top.pack(fill="x", pady=(0, 5))
        self.btn_load_json = tk.Button(toolbar_top, text="📂", font=("Arial", 12), width=4)
        self.btn_load_json.pack(side="left", padx=2)
        ToolTip(self.btn_load_json, "Load Sequence List")
        self.btn_save_json = tk.Button(toolbar_top, text="💾", font=("Arial", 12), width=4)
        self.btn_save_json.pack(side="left", padx=2)
        ToolTip(self.btn_save_json, "Save Sequence List")
        self.btn_clear_list = tk.Button(toolbar_top, text="🧹", font=("Arial", 12), width=4)
        self.btn_clear_list.pack(side="left", padx=2)
        ToolTip(self.btn_clear_list, "Clear Sequence List")
        self.lbl_active_file = tk.Label(toolbar_top, text="Active File: None", font=("Arial", 10, "italic"), fg="gray")
        self.lbl_active_file.pack(side="right", padx=10)

        # Treeview
        tree_frame = tk.Frame(col2_seq)
        tree_frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tree_frame, columns=("id", "type", "position", "params"), show="headings")
        self.tree.heading("id", text="ID")
        self.tree.heading("type", text="Type")
        self.tree.heading("position", text="Position (°)")
        self.tree.heading("params", text="Parameters")
        self.tree.column("id", width=30, anchor="center")
        self.tree.column("type", width=100, anchor="center")
        self.tree.column("position", width=250, anchor="center")
        self.tree.column("params", width=200, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)

        # Toolbar Middle (List Ops)
        list_ops = tk.Frame(col2_seq)
        list_ops.pack(fill="x", pady=5)
        self.btn_move_up = tk.Button(list_ops, text="⬆", font=("Arial", 12), width=4)
        self.btn_move_up.pack(side="left", padx=2)
        ToolTip(self.btn_move_up, "Move Entry Up")
        self.btn_move_down = tk.Button(list_ops, text="⬇", font=("Arial", 12), width=4)
        self.btn_move_down.pack(side="left", padx=2)
        ToolTip(self.btn_move_down, "Move Entry Down")
        self.btn_delete = tk.Button(list_ops, text="🗑", font=("Arial", 12), width=4, fg="red")
        self.btn_delete.pack(side="left", padx=(15, 2))
        ToolTip(self.btn_delete, "Remove Marked Entries")
        self.btn_undo = tk.Button(list_ops, text="⤺", font=("Arial", 12), width=4)
        self.btn_undo.pack(side="right", padx=2)
        ToolTip(self.btn_undo, "Undo")
        self.btn_redo = tk.Button(list_ops, text="⤻", font=("Arial", 12), width=4)
        self.btn_redo.pack(side="right", padx=2)
        ToolTip(self.btn_redo, "Redo")

        # Media Controls Bottom
        media_frame = tk.Frame(col2_seq, bg="#e6e6e6", pady=10, padx=10)
        media_frame.pack(fill="x", pady=(10, 0))
        self.btn_replay = tk.Button(media_frame, text="▶ START REPLAY", bg="#4CAF50", fg="white", font=("Arial", 11, "bold"), height=2, width=18)
        self.btn_replay.pack(side="left", padx=5)
        self.btn_pause_media = tk.Button(media_frame, text="⏸", font=("Arial", 14), width=3)
        self.btn_pause_media.pack(side="left", padx=5)
        ToolTip(self.btn_pause_media, "Pause/Resume current Action")
        self.btn_stop_media = tk.Button(media_frame, text="⏹", font=("Arial", 14), width=3)
        self.btn_stop_media.pack(side="left", padx=5)
        ToolTip(self.btn_stop_media, "Stop Sequence")
        self.btn_estop = tk.Button(media_frame, text="🛑 E-STOP", bg="#f44336", fg="white", font=("Arial", 11, "bold"), height=2)
        self.btn_estop.pack(side="right", fill="x", expand=True, padx=(20, 0))

        # ==========================================
        # COLUMN 3: INSPECTOR
        # ==========================================
        self.lbl_inspector_title = tk.Label(col3_insp, text="No Waypoint Selected", font=("Arial", 10, "italic"), fg="gray")
        self.lbl_inspector_title.pack(pady=(0, 10))

        tk.Label(col3_insp, text="Type:", font=("Arial", 10, "bold")).pack(anchor="w", pady=(0, 5))
        
        self.wp_type_var = tk.StringVar(value="action")
        
        type_frame = tk.Frame(col3_insp, bg="#cccccc", padx=1, pady=1) 
        type_frame.pack(fill="x", pady=(0, 10))

        # Toggle Style
        toggle_opts = {
            "variable": self.wp_type_var,
            "indicatoron": 0,               
            "relief": "flat",               
            "bg": "#f8f9fa",                
            "selectcolor": "#b3e5fc",       
            "activebackground": "#e9ecef",  
            "font": ("Arial", 9, "bold"),
            "pady": 6,
            "command": self.toggle_wp_settings
        }

        tk.Radiobutton(type_frame, text="ACTION", value="action", **toggle_opts).pack(side="left", fill="x", expand=True, padx=1)
        tk.Radiobutton(type_frame, text="WAYPOINT", value="angularwaypoint", **toggle_opts).pack(side="left", fill="x", expand=True, padx=1)
        tk.Radiobutton(type_frame, text="PAUSE", value="pause", **toggle_opts).pack(side="left", fill="x", expand=True, padx=1)

        tk.Label(col3_insp, text="Duration / Wait Time (s):").pack(anchor="w", pady=(10, 0))
        self.ent_duration = tk.Entry(col3_insp, width=15, font=("Courier", 11))
        self.ent_duration.pack(anchor="w")

        self.frame_wp_vels = tk.Frame(col3_insp)
        tk.Label(self.frame_wp_vels, text="Max Velocities (°/s):").pack(anchor="w", pady=(10, 0))
        self.ent_wp_vels = []
        vel_grid = tk.Frame(self.frame_wp_vels)
        vel_grid.pack(fill="x")
        for i in range(6):
            tk.Label(vel_grid, text=f"J{i+1}:").grid(row=i//2, column=(i%2)*2, sticky="w", padx=(0,2))
            ent = tk.Entry(vel_grid, width=6)
            ent.grid(row=i//2, column=(i%2)*2+1, sticky="w", padx=(0,10), pady=2)
            self.ent_wp_vels.append(ent)

        tk.Label(col3_insp, text="Joint Angles (°):", font=("Arial", 10, "bold")).pack(anchor="w", pady=(15, 5))
        self.insp_joint_vars = []
        insp_joint_grid = tk.Frame(col3_insp)
        insp_joint_grid.pack(fill="x")
        for i in range(6):
            tk.Label(insp_joint_grid, text=f"J{i+1}:").grid(row=i, column=0, sticky="w", pady=2)
            var = tk.StringVar(value="0.0")
            tk.Entry(insp_joint_grid, textvariable=var, width=15, font=("Courier", 11)).grid(row=i, column=1, sticky="w", padx=5, pady=2)
            self.insp_joint_vars.append(var)

        self.btn_preview = tk.Button(col3_insp, text="▶ Preview this Pose", bg="#fff9c4", font=("Arial", 10))
        self.btn_preview.pack(fill="x", side="bottom", pady=5)
        
        self.btn_save_settings = tk.Button(col3_insp, text="💾 Apply & Save to Selected", bg="#c8e6c9", font=("Arial", 10, "bold"))
        self.btn_save_settings.pack(fill="x", side="bottom", pady=5)

        self.btn_append_new = tk.Button(col3_insp, text="➕ Append as New Waypoint", bg="#b3e5fc", font=("Arial", 10, "bold"))
        self.btn_append_new.pack(fill="x", side="bottom", pady=5)

        self.toggle_wp_settings()
        self._set_inspector_state("disabled")

        # --- FOOTER (Logs) ---
        log_frame = tk.LabelFrame(self.root, text="System Logs", padx=5, pady=5)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.log_area = scrolledtext.ScrolledText(log_frame, height=5, state='disabled', font=("Courier", 10))
        self.log_area.pack(fill="both", expand=True)
        self.log_area.tag_config('INFO', foreground='black')
        self.log_area.tag_config('WARNING', foreground='#FF8C00')
        self.log_area.tag_config('ERROR', foreground='red', font=("Courier", 10, "bold"))

    def bind_commands(self, commands):
        """Binds abstract intent callbacks from the Controller."""
        self.commands = commands
        
        self.btn_reconnect.config(command=self.commands.get("reconnect"))
        self.btn_clear_faults.config(command=self.commands.get("clear_faults"))
        
        # Wrapping UI data extraction before calling controller
        self.btn_capture.config(command=self.on_capture_pose)
        self.btn_save_settings.config(command=self.on_save_waypoint)
        self.btn_preview.config(command=self.on_preview_pose)
        self.btn_append_new.config(command=self.on_append_inspector_pose)
        
        self.btn_move_up.config(command=self.on_move_up)
        self.btn_move_down.config(command=self.on_move_down)
        self.btn_delete.config(command=self.on_delete_poses)
        self.btn_undo.config(command=self.commands.get("undo"))
        self.btn_redo.config(command=self.commands.get("redo"))
        
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        
        self.btn_save_json.config(command=self.commands.get("save_json"))
        self.btn_load_json.config(command=self.prompt_load_json)
        self.btn_clear_list.config(command=self.commands.get("clear_list"))
        
        self.btn_replay.config(command=self.commands.get("replay"))
        self.btn_estop.config(command=self.commands.get("estop"))
        self.btn_stop_media.config(command=self.commands.get("stop_media"))
        self.btn_pause_media.config(command=self.on_pause_media)

        # Hotkeys
        self.root.bind("<Control-Up>", self.on_move_up)
        self.root.bind("<Control-Down>", self.on_move_down)
        self.root.bind("<Delete>", self.on_delete_poses)
        self.root.bind("<Control-z>", lambda e: self.commands.get("undo")())
        self.root.bind("<Control-y>", lambda e: self.commands.get("redo")())

    # ================= VIEW -> CONTROLLER INTENTS =================
    
    def on_capture_pose(self):
        poses = self.get_live_poses()
        if poses and "capture_pose" in self.commands:
            self.commands["capture_pose"](poses)

    def on_save_waypoint(self):
        indices = self.get_selected_indices()
        if not indices: return
        idx = indices[0]
        params = self.get_waypoint_params()
        poses = self.get_inspector_poses()
        if "save_waypoint" in self.commands:
            self.commands["save_waypoint"](idx, params, poses)

    def on_preview_pose(self):
        poses = self.get_inspector_poses()
        if poses and "preview_pose" in self.commands:
            self.commands["preview_pose"](poses)

    def on_append_inspector_pose(self) -> None:
        params = self.get_waypoint_params()
        poses = self.get_inspector_poses()
        
        if poses and "append_inspector_pose" in self.commands:
            self.commands["append_inspector_pose"](params, poses)

    def on_tree_select(self, event):
        indices = self.get_selected_indices()
        if indices and "tree_select" in self.commands:
            self.commands["tree_select"](indices[0])

    def on_move_up(self, event=None):
        indices = self.get_selected_indices()
        if indices and "move_up" in self.commands:
            self.commands["move_up"](indices[0])

    def on_move_down(self, event=None):
        indices = self.get_selected_indices()
        if indices and "move_down" in self.commands:
            self.commands["move_down"](indices[0])

    def on_delete_poses(self, event=None):
        indices = self.get_selected_indices()
        if indices and "delete_poses" in self.commands:
            self.commands["delete_poses"](indices)

    def on_pause_media(self):
        is_paused = self.commands.get("pause_media")() if "pause_media" in self.commands else False
        self.btn_pause_media.config(fg="orange" if is_paused else "black")

    def prompt_load_json(self):
        self.is_dialog_open = True 
        try:
            path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
            if path and "load_json" in self.commands:
                self.commands["load_json"](path)
        finally:
            self.is_dialog_open = False 

    # ================= OBSERVER CALLBACKS (MODEL -> VIEW) =================

    def on_sequence_changed(self, sequence, filepath, select_index=None):
        """Triggered automatically when the Model changes."""
        # Update File Label
        if filepath:
            name = filepath.split("/")[-1].split("\\")[-1]
            self.lbl_active_file.config(text=f"Active File: {name}", fg="#0066cc")
        else:
            self.lbl_active_file.config(text="Active File: None", fg="gray")

        # Update Treeview
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        for idx, step in enumerate(sequence):
            type_str = step.get("type", "action").upper()
            dur = step.get('duration_s', 3.0)
            
            if type_str == "PAUSE":
                pos_str = "--- (WAITING) ---"
                param_str = f"Wait: {dur}s"
            else:
                pos_str = [f"{v:.1f}" for v in step["pos"]]
                param_str = f"Duration: {dur}s"
                
            item = self.tree.insert("", "end", values=(idx, type_str, str(pos_str), param_str))
            if select_index is not None and idx == select_index:
                self.tree.selection_set(item)

        # Handle Inspector clearing if list is empty
        if not sequence:
            self._set_inspector_state("disabled")
            self.lbl_inspector_title.config(text="No Waypoint Selected")

    # ================= OBSERVER CALLBACKS (HARDWARE -> VIEW) =================
    
    def on_hardware_state_changed(self, state):
        """Triggered automatically by hardware telemetry. Handles Tkinter thread safety."""
        if self.is_dialog_open: return 
        self.root.after(0, self._update_live_ui, state)

    def _update_live_ui(self, state):
        # Connection Status
        if state.is_connected:
            if state.has_fault: 
                self.lbl_status.config(text=f"🔴 FAULT ERROR - IP: {getattr(state, 'ip', 'Unknown')}", fg="#ff3333")
            else: 
                self.lbl_status.config(text=f"🟢 Connected - IP: {getattr(state, 'ip', 'Unknown')} ({state.dof}-DOF)", fg="#00ff00")
        else: 
            self.lbl_status.config(text="⚪ Disconnected", fg="#a0a0a0")

        if not state.is_connected: return

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

        #States Mapping
        active_states = {
            0: "Unknown", 1: "Ready (Idle)", 2: "In Fault", 3: "Maintenance",
            4: "Paused", 5: "Executing Action", 6: "Initialization"
        }
        state_str = active_states.get(state.active_state, f"Code {state.active_state}")

        #Metrics Mapping
        temps_str = "|".join([f"{t:.1f}" for t in state.joint_temperatures]) if state.joint_temperatures else "N/A"
        currents_str = "|".join([f"{c:.2f}" for c in state.joint_currents]) if state.joint_currents else "N/A"
        torques_str = "|".join([f"{t:.1f}" for t in state.joint_torques]) if state.joint_torques else "N/A"
        
        #Fault State
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

    # ================= UI LOGIC =================
    def _set_inspector_state(self, state):
        widgets = [self.ent_duration] + self.ent_wp_vels + [self.btn_save_settings, self.btn_preview, self.btn_append_new]
        for w in widgets: w.config(state=state)
        for rb in self.wp_type_var.trace_info(): pass # Radiobuttons
        for i in range(6): 
            self.insp_joint_vars[i].set("0.0" if state == "disabled" else self.insp_joint_vars[i].get())

    def toggle_wp_settings(self):
        wp_type = self.wp_type_var.get()
        if wp_type == "angularwaypoint":
            self.frame_wp_vels.pack(anchor="w", after=self.ent_duration, pady=5)
        else:
            self.frame_wp_vels.pack_forget()

    def load_inspector_data(self, data, index):
        """Populates Column 3 when a tree item is clicked."""
        self.lbl_inspector_title.config(text=f"Selected Waypoint: #{index}", fg="#0066cc", font=("Arial", 10, "bold"))
        self._set_inspector_state("normal")
        
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

    def get_waypoint_params(self):
        wp_type = self.wp_type_var.get()
        max_vels = [0.0] * 6
        try: dur_s = float(self.ent_duration.get() or 3.0)
        except: dur_s = 3.0

        if wp_type == "angularwaypoint":
            for i, ent in enumerate(self.ent_wp_vels):
                try: max_vels[i] = float(ent.get() or 0.0)
                except: pass

        return {"type": wp_type, "duration_s": dur_s, "max_velocities": max_vels, "pause_s": 0.0}

    def get_inspector_poses(self):
        try: return [float(var.get()) for var in self.insp_joint_vars]
        except ValueError: return None
        
    def get_live_poses(self):
        try: return [float(var.get().replace(" °", "")) for var in self.live_joint_vars]
        except ValueError: return None

    def update_treeview(self, sequence_data, select_index=None):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        for idx, step in enumerate(sequence_data):
            type_str = step.get("type", "action").upper()
            dur = step.get('duration_s', 3.0)
            
            if type_str == "PAUSE":
                pos_str = "--- (WAITING) ---"
                param_str = f"Wait: {dur}s"
            else:
                pos_str = [f"{v:.1f}" for v in step["pos"]]
                param_str = f"Duration: {dur}s"
                
            item = self.tree.insert("", "end", values=(idx, type_str, str(pos_str), param_str))
            if select_index is not None and idx == select_index:
                self.tree.selection_set(item)

    def get_selected_indices(self):
        return [self.tree.index(item) for item in self.tree.selection()]

class ConnectionDialog(tk.Toplevel):
    """Blocking popup dialog that requests IP and Credentials on startup."""
    def __init__(self, parent, default_ip="", default_user="", default_pass=""):
        super().__init__(parent)
        self.title("Robot Connection")
        self.resizable(False, False)

        self.result = None

        self.ip_var = tk.StringVar(value=default_ip)
        self.user_var = tk.StringVar(value=default_user)
        self.pass_var = tk.StringVar(value=default_pass)

        self.ip_var.trace_add("write", self.validate_inputs)
        self.user_var.trace_add("write", self.validate_inputs)
        self.pass_var.trace_add("write", self.validate_inputs)

        tk.Label(self, text="Enter Kinova Robot Credentials", font=("Arial", 11, "bold")).pack(pady=(15, 10))

        tk.Label(self, text="IP Address:").pack(pady=(5, 0))
        self.ent_ip = tk.Entry(self, width=25, justify="center", textvariable=self.ip_var)
        self.ent_ip.pack()

        tk.Label(self, text="Username:").pack(pady=(5, 0))
        self.ent_user = tk.Entry(self, width=25, justify="center", textvariable=self.user_var)
        self.ent_user.pack()

        tk.Label(self, text="Password:").pack(pady=(5, 0))
        self.ent_pass = tk.Entry(self, width=25, justify="center", show="*", textvariable=self.pass_var)
        self.ent_pass.pack()

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=20)
        self.btn_connect = tk.Button(btn_frame, text="Connect", command=self.on_connect, bg="lightgreen", width=10)
        self.btn_connect.pack(side="left", padx=10)
        tk.Button(btn_frame, text="Cancel", command=self.on_cancel, bg="lightcoral", width=10).pack(side="left", padx=10)

        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

        self.validate_inputs()

        self.update_idletasks() 
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
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
            self.btn_connect.config(state=tk.NORMAL)
        else:
            self.btn_connect.config(state=tk.DISABLED)

    def on_connect(self):
        """Commits the user input and closes the dialog."""
        self.result = (self.ip_var.get().strip(), self.user_var.get().strip(), self.pass_var.get().strip())
        self.destroy()

    def on_cancel(self):
        """Destroys the dialog upon cancellation."""
        self.destroy()