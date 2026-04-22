import tkinter as tk
from tkinter import ttk, scrolledtext
import re

class RobotView:
    """
    Handles all visual components (Tkinter).
    No application logic resides here, only UI setup and update mechanisms.
    """
    def __init__(self, root):
        self.root = root
        self.root.title("Robot Teach-In Controller")
        self.root.geometry("1280x900")
        
        self.mode_var = tk.StringVar(value="TEACH")
        self.setup_ui()

    def setup_ui(self):
        # --- 1. Status Bar ---
        status_frame = tk.Frame(self.root, bg="#333333", padx=10, pady=5)
        status_frame.pack(fill="x")
        self.lbl_status = tk.Label(status_frame, text="Status: Initializing...", font=("Arial", 11, "bold"), bg="#333333", fg="white")
        self.lbl_status.pack(side="left")
        self.btn_reconnect = tk.Button(status_frame, text="🔄 Reconnect")
        self.btn_reconnect.pack(side="right")

        # --- 2. Main Content (Two Columns) ---
        content_frame = tk.Frame(self.root)
        content_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # LEFT COLUMN: Joint Control
        left_col = tk.LabelFrame(content_frame, text="1. Joint Control (The 'Now')", padx=15, pady=15)
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 5))

        # Mode Selection
        mode_frame = tk.Frame(left_col)
        mode_frame.pack(fill="x", pady=(0, 15))
        self.rb_teach = tk.Radiobutton(mode_frame, text="TEACH MODE (Live Sensor Data)", variable=self.mode_var, value="TEACH", font=("Arial", 11, "bold"), fg="#0066cc")
        self.rb_teach.pack(anchor="w")
        self.rb_edit = tk.Radiobutton(mode_frame, text="EDIT MODE (Manual Input / Fine Tuning)", variable=self.mode_var, value="EDIT", font=("Arial", 11, "bold"), fg="#800080")
        self.rb_edit.pack(anchor="w")

        # Joints Display
        self.joint_entries = []
        self.joint_frames = []
        self.joint_toggles = [] 
        
        joints_frame = tk.Frame(left_col)
        joints_frame.pack(fill="x", pady=10)
        
        for i in range(7):
            frame = tk.Frame(joints_frame)
            frame.pack(fill="x", pady=4)
            
            tk.Label(frame, text=f"Joint {i+1}:", width=8, font=("Arial", 11, "bold"), anchor="w").pack(side="left")
            entry_val = tk.Entry(frame, width=12, font=("Courier", 12))
            entry_val.insert(0, "0.00")
            entry_val.pack(side="left", padx=5)
            tk.Label(frame, text="°", font=("Courier", 12, "bold")).pack(side="left")
            
            toggle_var = tk.BooleanVar(value=False)
            chk = tk.Checkbutton(frame, text="Unlock", variable=toggle_var, fg="#FF8C00", font=("Arial", 9, "bold"))
            chk.pack(side="left", padx=10)
            
            self.joint_entries.append(entry_val)
            self.joint_frames.append(frame)
            self.joint_toggles.append(toggle_var)

        # Action Buttons for Poses
        tk.Label(left_col, text="Actions:", font=("Arial", 10, "bold")).pack(anchor="w", pady=(15, 5))
        
        self.btn_teach_custom = tk.Button(left_col, text="✋ START TEACH (Unlocked Joints)", bg="#FFA500", font=("Arial", 11, "bold"), height=2)
        self.btn_teach_custom.pack(fill="x", pady=2)

        # --- Teach Parameters (Gain & Deadzone) ---
        param_frame = tk.LabelFrame(left_col, text="Teach Parameters", padx=5, pady=5)
        param_frame.pack(fill="x", pady=10)

        tk.Label(param_frame, text="Gain (Strength):", font=("Arial", 9)).grid(row=0, column=0, sticky="w")
        self.ent_gain = tk.Entry(param_frame, width=8)
        self.ent_gain.insert(0, "1.0") 
        self.ent_gain.grid(row=0, column=1, padx=5, pady=2)

        tk.Label(param_frame, text="Deadzone (Tolerance):", font=("Arial", 9)).grid(row=1, column=0, sticky="w")
        self.ent_deadzone = tk.Entry(param_frame, width=8)
        self.ent_deadzone.insert(0, "1.5") 
        self.ent_deadzone.grid(row=1, column=1, padx=5, pady=2)
        
        # More Actions
        self.btn_save_ui = tk.Button(left_col, text="➕ Add Current Pose to Sequence", bg="lightblue", font=("Arial", 11, "bold"), height=2)
        self.btn_save_ui.pack(fill="x", pady=2)
        self.btn_overwrite = tk.Button(left_col, text="💾 Overwrite Selected Waypoint", bg="#e6e6fa", height=2)
        self.btn_overwrite.pack(fill="x", pady=2)
        self.btn_apply_ui = tk.Button(left_col, text="📤 Apply Editable Poses to Robot", bg="#f0e68c", height=2)
        self.btn_apply_ui.pack(fill="x", pady=2)

        # RIGHT COLUMN: Sequence Management
        right_col = tk.LabelFrame(content_frame, text="2. Sequence Management (The 'Future')", padx=15, pady=15)
        right_col.pack(side="right", fill="both", expand=True, padx=(5, 0))

        # Treeview
        tree_frame = tk.Frame(right_col)
        tree_frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tree_frame, columns=("id", "position", "speed"), show="headings")
        self.tree.heading("id", text="ID")
        self.tree.heading("position", text="Position (°)")
        self.tree.heading("speed", text="Speed (°/s)")
        self.tree.column("id", width=40, anchor="center")
        self.tree.column("position", width=350, anchor="center")
        self.tree.column("speed", width=80, anchor="center")
        self.tree.pack(fill="both", expand=True, side="left")
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        # List Actions
        list_action_frame = tk.Frame(right_col, pady=10)
        list_action_frame.pack(fill="x")
        self.btn_move_up = tk.Button(list_action_frame, text="⬆ Move Up")
        self.btn_move_up.grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        self.btn_move_down = tk.Button(list_action_frame, text="⬇ Move Down")
        self.btn_move_down.grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        self.btn_delete = tk.Button(list_action_frame, text="🗑 Delete Selected", bg="#ffb6c1")
        self.btn_delete.grid(row=0, column=2, padx=2, pady=2, sticky="ew")
        self.btn_move_to = tk.Button(list_action_frame, text="▶ Move Robot to Selected", bg="lightyellow")
        self.btn_move_to.grid(row=0, column=3, padx=2, pady=2, sticky="ew")

        # Speed Actions
        speed_frame = tk.Frame(right_col)
        speed_frame.pack(fill="x", pady=5)
        tk.Label(speed_frame, text="Speed for selected (°/s):").pack(side="left")
        self.ent_speed = tk.Entry(speed_frame, width=8)
        self.ent_speed.insert(0, "20") 
        self.ent_speed.pack(side="left", padx=5)
        self.btn_apply_speed = tk.Button(speed_frame, text="Apply Speed")
        self.btn_apply_speed.pack(side="left")

        # --- 3. Execution & Global Controls ---
        global_frame = tk.Frame(self.root, padx=10, pady=5)
        global_frame.pack(fill="x")
        
        file_frame = tk.Frame(global_frame)
        file_frame.pack(side="left")
        self.btn_save_json = tk.Button(file_frame, text="💾 Save JSON", width=15)
        self.btn_save_json.grid(row=0, column=0, padx=2)
        self.btn_load_json = tk.Button(file_frame, text="📂 Load JSON", width=15)
        self.btn_load_json.grid(row=0, column=1, padx=2)
        self.btn_clear_list = tk.Button(file_frame, text="🧹 Clear List", width=15)
        self.btn_clear_list.grid(row=0, column=2, padx=2)
        self.btn_clear_faults = tk.Button(file_frame, text="🔄 Clear Faults", bg="#ffcc99", width=15)
        self.btn_clear_faults.grid(row=0, column=3, padx=2)

        self.lbl_active_file = tk.Label(file_frame, text="Active File: None", font=("Arial", 10, "italic"), fg="gray")
        self.lbl_active_file.grid(row=1, column=0, columnspan=4, sticky="w", pady=(2,0), padx=2)

        exec_frame = tk.Frame(global_frame)
        exec_frame.pack(side="right")
        self.btn_replay = tk.Button(exec_frame, text="▶ REPLAY SEQUENCE", bg="lightgreen", font=("Arial", 11, "bold"), width=20, height=2)
        self.btn_replay.grid(row=0, column=0, padx=10)
        self.btn_estop = tk.Button(exec_frame, text="🛑 EMERGENCY STOP", bg="red", fg="white", font=("Arial", 11, "bold"), width=20, height=2)
        self.btn_estop.grid(row=0, column=1, padx=10)

        # --- 4. Logs ---
        log_frame = tk.LabelFrame(self.root, text="System Logs", padx=5, pady=5)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.log_area = scrolledtext.ScrolledText(log_frame, height=6, state='disabled', font=("Courier", 10))
        self.log_area.pack(fill="both", expand=True)
        self.log_area.tag_config('INFO', foreground='black')
        self.log_area.tag_config('ERROR', foreground='red', font=("Courier", 10, "bold"))
        self.log_area.tag_config('WARNING', foreground='#FF8C00')
        self.log_area.tag_config('CRITICAL', foreground='white', background='red', font=("Courier", 10, "bold"))

    def bind_controller(self, controller):
        """Binds UI button clicks and events to Controller methods."""
        # --- Hardware & Poses ---
        self.btn_reconnect.config(command=controller.handle_reconnect)
        self.btn_apply_ui.config(command=controller.handle_apply_ui_poses)
        self.btn_save_ui.config(command=controller.handle_append_pose)
        self.btn_overwrite.config(command=controller.handle_overwrite_selected)
        
        # --- List Actions ---
        self.btn_move_up.config(command=controller.handle_move_up)
        self.btn_move_down.config(command=controller.handle_move_down)
        self.btn_delete.config(command=controller.handle_delete_poses)
        self.btn_move_to.config(command=controller.handle_move_to_selected)
        self.btn_apply_speed.config(command=controller.handle_change_speed)
        
        # --- File & Global ---
        self.btn_save_json.config(command=controller.handle_save_json)
        self.btn_load_json.config(command=controller.handle_load_json)
        self.btn_clear_list.config(command=controller.handle_clear_list)
        self.btn_clear_faults.config(command=controller.handle_clear_faults)
        self.btn_replay.config(command=controller.handle_start_replay)
        self.btn_estop.config(command=controller.handle_emergency_stop)
        
        # --- Traces & Events ---
        self.mode_var.trace_add("write", controller.handle_mode_change)
        self.tree.bind("<<TreeviewSelect>>", controller.handle_tree_select)
        
        # --- Custom Teach ---
        self.btn_teach_custom.config(command=controller.handle_teach_toggle)

    # ---> MVC UPDATE: View evaluates state to UI text/colors! <---
    def update_connection_status(self, is_connected, has_fault, dof, ip):
        """Updates the status bar text and color based on robot state variables."""
        dof_str = f"{dof}-DOF" if dof > 0 else "Unknown DOF"
        
        if is_connected:
            if has_fault:
                self.lbl_status.config(text=f"🔴 FAULT ERROR ({dof_str}) - Clear Faults! - IP: {ip}", fg="red")
            else:
                self.lbl_status.config(text=f"🟢 Connected ({dof_str}) - IP: {ip}", fg="#00ff00")
        else:
            self.lbl_status.config(text=f"🔴 Disconnected - (Target: {ip})", fg="#ff3333")

    def set_active_file_label(self, filename):
        """Displays the currently open JSON file path."""
        if filename:
            self.lbl_active_file.config(text=f"Active File: {filename}", fg="blue")
        else:
            self.lbl_active_file.config(text="Active File: None", fg="gray")

    def update_treeview(self, sequence_data, select_index=None):
        """Refreshes the data table containing all waypoints."""
        for item in self.tree.get_children():
            self.tree.delete(item)
        for idx, step in enumerate(sequence_data):
            pos_str = [f"{v:.3f}" for v in step["pos"]]
            item = self.tree.insert("", "end", values=(idx, str(pos_str), step["speed"]))
            if select_index is not None and idx == select_index:
                self.tree.selection_set(item)

    def update_joint_entries(self, current_rad, force=False):
        """Updates the UI input fields with telemetry data."""
        # Hide unneeded frames (e.g. joint 7 on a 6-DOF bot)
        for i, frame in enumerate(self.joint_frames):
            if i < len(current_rad):
                if not frame.winfo_ismapped():
                    frame.pack(fill="x", pady=4)
            else:
                if frame.winfo_ismapped():
                    frame.pack_forget() 

        for i, val in enumerate(current_rad):
            if force or self.root.focus_get() != self.joint_entries[i]:
                self.joint_entries[i].config(state="normal")
                self.joint_entries[i].delete(0, tk.END)
                self.joint_entries[i].insert(0, f"{val:.2f}")
                if self.mode_var.get() == "TEACH":
                    self.joint_entries[i].config(state="readonly")

    def toggle_entry_states(self, state):
        """Locks or unlocks the joint text fields based on current mode."""
        visible_entries = [e for e, f in zip(self.joint_entries, self.joint_frames) if f.winfo_ismapped()]
        for entry in visible_entries:
            entry.config(state=state)

    def get_entry_poses(self):
        """Extracts float values from the joint text fields."""
        try:
            visible_entries = [e for e, f in zip(self.joint_entries, self.joint_frames) if f.winfo_ismapped()]
            return [float(entry.get()) for entry in visible_entries]
        except ValueError:
            return None

    def get_selected_indices(self):
        """Returns indices of selected waypoints in the table."""
        selected = self.tree.selection()
        return [self.tree.index(item) for item in selected]

    def get_speed_input(self):
        """Validates and returns the user's speed input."""
        try:
            speed = int(self.ent_speed.get())
            return speed if 1 <= speed <= 100 else None
        except ValueError:
            return None
        
    def update_speed_entry(self, speed):
        """Populates the speed text field with a specific value."""
        self.ent_speed.delete(0, tk.END)
        self.ent_speed.insert(0, str(speed))

    def get_unlocked_joints(self):
        """Returns a list of indices representing the ticked 'Unlock' checkboxes."""
        visible_toggles = [t for t, f in zip(self.joint_toggles, self.joint_frames) if f.winfo_ismapped()]
        return [i for i, var in enumerate(visible_toggles) if var.get()]
        
    def get_admittance_params(self):
        """Reads Admittance Teach parameters from UI."""
        try:
            gain = float(self.ent_gain.get())
            deadzone = float(self.ent_deadzone.get())
            return gain, deadzone
        except ValueError:
            return None, None

class ConnectionDialog(tk.Toplevel):
    """A blocking dialog that asks for IP, Username, and Password."""
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
        self.result = (self.ip_var.get().strip(), self.user_var.get().strip(), self.pass_var.get().strip())
        self.destroy()

    def on_cancel(self):
        self.destroy()