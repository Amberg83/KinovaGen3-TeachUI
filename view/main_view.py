import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog
from view.panels import LiveStatePanel, SequenceTimelinePanel, WaypointInspectorPanel
from view import theme

class RobotView:
    def __init__(self, root):
        self.root = root
        self.root.title("Robot Teach-In Controller (Dashboard)")
        self.root.geometry("1450x900") 
        self.root.configure(bg=theme.BG_MAIN)
        
        self.commands = {}
        self.is_dialog_open = False
        self._last_hardware_state = None
        self._last_status_text = ""
        self._last_status_fg = ""
        
        # Configure our visual design system (TTK styling)
        theme.configure_flat_styles()

        self.setup_ui()
        self.root.after(50, self._tick_live_ui)

    def setup_ui(self):
        # --- HEADER (Connection Status & Header Operations) ---
        status_frame = tk.Frame(self.root, bg=theme.BG_HEADER, padx=15, pady=8,
                                highlightbackground=theme.BORDER_COLOR, highlightthickness=1)
        status_frame.pack(fill="x")
        
        self.lbl_status = tk.Label(status_frame, text="Status: Initializing...", font=theme.FONT_TITLE, bg=theme.BG_HEADER, fg=theme.TEXT_MUTED)
        self.lbl_status.pack(side="left")
        
        btn_frame = tk.Frame(status_frame, bg=theme.BG_HEADER)
        btn_frame.pack(side="right")
        
        self.btn_reconnect = theme.make_flat_button(
            btn_frame, text="🔄 Reconnect", bg_color=theme.BG_INPUT, 
            fg_color=theme.TEXT_PRIMARY, hover_bg=theme.BORDER_COLOR, 
            font_style=theme.FONT_EMOJI, padx=12, pady=4
        )
        self.btn_reconnect.pack(side="left", padx=5)
        
        self.btn_clear_faults = theme.make_flat_button(
            btn_frame, text="🧹 Clear Faults", bg_color=theme.ACCENT_ORANGE, 
            fg_color=theme.BG_MAIN, hover_bg="#d97706", 
            font_style=theme.FONT_EMOJI, padx=12, pady=4
        )
        self.btn_clear_faults.pack(side="left", padx=5)

        # --- 3-COLUMN MAIN LAYOUT ---
        content_frame = tk.Frame(self.root, bg=theme.BG_MAIN)
        content_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # ttk.Panedwindow style is mapped inside theme configuration
        self.paned = ttk.PanedWindow(content_frame, orient=tk.HORIZONTAL, style="TPanedwindow")
        self.paned.pack(fill="both", expand=True)

        # Columns Packages instantiation
        self.panel_live = LiveStatePanel(self.paned)
        self.panel_seq = SequenceTimelinePanel(self.paned)
        self.panel_insp = WaypointInspectorPanel(self.paned)

        self.paned.add(self.panel_live, weight=1)
        self.paned.add(self.panel_seq, weight=3)
        self.paned.add(self.panel_insp, weight=1)

        # --- FOOTER (System Logs Console) ---
        log_frame = ttk.LabelFrame(self.root, text="System Logs", style="TLabelframe", padding=8)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Styled as a dark modern log terminal
        self.log_area = scrolledtext.ScrolledText(
            log_frame, height=5, state='disabled', font=theme.FONT_MONO,
            bg="#09090b", fg=theme.TEXT_PRIMARY, insertbackground=theme.TEXT_PRIMARY,
            relief="flat", bd=0, highlightthickness=0
        )
        self.log_area.pack(fill="both", expand=True)
        
        # Beautiful contrasting tag colors for logs output
        self.log_area.tag_config('INFO', foreground='#94a3b8')      # Clean slate gray
        self.log_area.tag_config('WARNING', foreground=theme.ACCENT_YELLOW) # Bright gold
        self.log_area.tag_config('ERROR', foreground=theme.ACCENT_RED, font=(theme.FONT_MONO[0], theme.FONT_MONO[1], "bold")) # Strong red

    def bind_commands(self, commands):
        """Binds abstract intent callbacks from the Controller to View/Panel nodes."""
        self.commands = commands
        
        # Connect Header items
        self.btn_reconnect.config(command=self.commands.get("reconnect"))
        self.btn_clear_faults.config(command=self.commands.get("clear_faults"))
        
        # Bind Column 1
        self.panel_live.bind_commands(
            capture_pose_cb=self.on_capture_pose,
            apply_admittance_cb=self.on_apply_admittance
        )
        
        # Bind Column 2
        self.panel_seq.bind_commands({
            "load_json_prompt": self.prompt_load_json,
            "save_json": self.commands.get("save_json"),
            "clear_list": self.commands.get("clear_list"),
            "move_up": self.on_move_up,
            "move_down": self.on_move_down,
            "delete_poses": self.on_delete_poses,
            "undo": self.commands.get("undo"),
            "redo": self.commands.get("redo"),
            "replay": self.commands.get("replay"),
            "replay_selection": self.commands.get("replay_selection"),
            "pause_media": self.on_pause_media,
            "stop_media": self.commands.get("stop_media"),
            "estop": self.commands.get("estop"),
            "tree_select": self.on_tree_select
        })
        
        # Bind Column 3
        self.panel_insp.bind_commands({
            "preview_pose": self.on_preview_pose,
            "save_settings": self.on_save_waypoint,
            "append_pose": self.on_append_inspector_pose
        })

        # Global Hotkey listeners
        self.root.bind("<Control-Up>", self.on_move_up)
        self.root.bind("<Control-Down>", self.on_move_down)
        self.root.bind("<Delete>", self.on_delete_poses)
        self.root.bind("<Control-z>", lambda e: self.commands.get("undo")())
        self.root.bind("<Control-y>", lambda e: self.commands.get("redo")())

    # ================= VIEW -> CONTROLLER INTERFACES =================
    
    def on_capture_pose(self):
        poses = self.panel_live.get_live_poses()
        if poses and "capture_pose" in self.commands:
            self.commands["capture_pose"](poses)

    def on_save_waypoint(self):
        indices = self.panel_seq.get_selected_indices()
        if not indices: return
        params = self.panel_insp.get_waypoint_params()
        poses = self.panel_insp.get_inspector_poses()
        if "save_waypoint" in self.commands:
            if len(indices) > 1:
                # Bulk duration updates (poses are ignored for multiple selections)
                self.commands["save_waypoint"](indices, params, None)
            else:
                self.commands["save_waypoint"](indices[0], params, poses)

    def on_preview_pose(self):
        poses = self.panel_insp.get_inspector_poses()
        if poses and "preview_pose" in self.commands:
            self.commands["preview_pose"](poses)

    def on_append_inspector_pose(self) -> None:
        params = self.panel_insp.get_waypoint_params()
        poses = self.panel_insp.get_inspector_poses()
        if poses and "append_inspector_pose" in self.commands:
            self.commands["append_inspector_pose"](params, poses)
    
    def on_apply_admittance(self):
        mode = self.panel_live.get_selected_admittance_mode()
        if mode and "set_admittance" in self.commands:
            self.commands["set_admittance"](mode)

    def on_tree_select(self, event):
        indices = self.panel_seq.get_selected_indices()
        if not indices: return
        if len(indices) > 1:
            # Enter bulk editing mode in Inspector
            self.panel_insp.enter_bulk_edit_mode(indices)
        else:
            if "tree_select" in self.commands:
                self.commands["tree_select"](indices[0])

    def on_move_up(self, event=None):
        indices = self.panel_seq.get_selected_indices()
        if indices and "move_up" in self.commands:
            self.commands["move_up"](indices[0])

    def on_move_down(self, event=None):
        indices = self.panel_seq.get_selected_indices()
        if indices and "move_down" in self.commands:
            self.commands["move_down"](indices[0])

    def on_delete_poses(self, event=None):
        indices = self.panel_seq.get_selected_indices()
        if indices and "delete_poses" in self.commands:
            self.commands["delete_poses"](indices)

    def on_pause_media(self):
        is_paused = self.commands.get("pause_media")() if "pause_media" in self.commands else False
        self.panel_seq.btn_pause_media.config(fg="orange" if is_paused else "white")

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
        """Dispatched from sequence model changes. Updates Column 2 & resets Column 3."""
        self.panel_seq.update_sequence(sequence, filepath, select_index)

        # Clear inspector if the timeline list was wiped out
        if not sequence:
            self.panel_insp.clear_inspector()

    # ================= OBSERVER CALLBACKS (HARDWARE -> VIEW) =================
    
    def on_hardware_state_changed(self, state):
        """Caches the latest hardware telemetry state (thread-safe reference copy)."""
        self._last_hardware_state = state

    def _tick_live_ui(self):
        """Periodic tick pulling the latest state updates to avoid event queue flooding."""
        if not self.is_dialog_open and self._last_hardware_state is not None:
            self._update_live_ui(self._last_hardware_state)
        # Schedule next tick (50ms corresponds to a stable 20Hz redraw)
        self.root.after(50, self._tick_live_ui)

    def _update_live_ui(self, state):
        # Determine status text and color
        if state.is_connected:
            if state.has_fault: 
                text = f"🔴 FAULT ERROR - IP: {getattr(state, 'ip', 'Unknown')}"
                fg = theme.ACCENT_RED
            else: 
                text = f"🟢 Connected - IP: {getattr(state, 'ip', 'Unknown')} ({state.dof}-DOF)"
                fg = theme.ACCENT_GREEN
        else: 
            text = "⚪ Disconnected"
            fg = theme.TEXT_MUTED

        # Only update the widget configuration if the state changed
        if text != self._last_status_text or fg != self._last_status_fg:
            self.lbl_status.config(text=text, fg=fg)
            self._last_status_text = text
            self._last_status_fg = fg

        if not state.is_connected: return

        # Delegate telemetry displays
        self.panel_live.update_telemetry(state)

    # ================= PUBLIC API INTERFACES FOR CONTROLLER =================
    def load_inspector_data(self, data, index):
        """Called by controller to load a selected waypoint into the editor form."""
        self.panel_insp.load_inspector_data(data, index)

    # ================= STUDY MODE WIDGET DECORATIONS =================

    def enable_study_mode(self, pid, first_task, current_idx, total_count, on_completed_callback):
        """Builds a beautiful premium banner panel representing participant task progress."""
        self.study_banner = tk.Frame(
            self.root, bg=theme.BG_CARD, padx=15, pady=10, bd=0,
            highlightbackground=theme.ACCENT_CYBER, highlightthickness=1
        )
        # Pack right beneath the main status_frame
        self.study_banner.pack(fill="x", before=self.root.pack_slaves()[1])
        
        # Grid layout for high-density information
        self.study_banner.columnconfigure(0, weight=1)
        self.study_banner.columnconfigure(1, weight=3)
        self.study_banner.columnconfigure(2, weight=0)
        
        info_frame = tk.Frame(self.study_banner, bg=theme.BG_CARD)
        info_frame.grid(row=0, column=0, sticky="w")
        
        self.lbl_study_p = tk.Label(
            info_frame, text=f"👤 Participant: #{pid}", 
            font=theme.FONT_TITLE, bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY
        )
        self.lbl_study_p.pack(anchor="w")
        
        self.lbl_study_counter = tk.Label(
            info_frame, text=f"📋 Task {current_idx}/{total_count}", 
            font=theme.FONT_NORMAL, bg=theme.BG_CARD, fg=theme.ACCENT_CYBER
        )
        self.lbl_study_counter.pack(anchor="w", pady=(2, 0))
        
        inst_frame = tk.Frame(self.study_banner, bg=theme.BG_CARD)
        inst_frame.grid(row=0, column=1, sticky="w", padx=20)
        
        self.lbl_task_name = tk.Label(
            inst_frame, text=f"Active Referent: {first_task['name']}", 
            font=(theme.FONT_NORMAL[0], theme.FONT_NORMAL[1] + 1, "bold"), 
            bg=theme.BG_CARD, fg=theme.TEXT_PRIMARY
        )
        self.lbl_task_name.pack(anchor="w")
        
        self.lbl_task_desc = tk.Label(
            inst_frame, text=first_task["instructions"], 
            font=theme.FONT_NORMAL, bg=theme.BG_CARD, fg=theme.TEXT_MUTED,
            justify="left", anchor="w"
        )
        self.lbl_task_desc.pack(anchor="w", pady=(2, 0))
        
        self.btn_study_next = theme.make_flat_button(
            self.study_banner, text="✅ Task Completed / Next Referent", 
            bg_color=theme.ACCENT_GREEN, fg_color=theme.BG_MAIN, 
            hover_bg="#059669", font_style=theme.FONT_EMOJI_LARGE, 
            padx=20, pady=8, command=on_completed_callback
        )
        self.btn_study_next.grid(row=0, column=2, sticky="e", padx=(10, 0))

    def update_study_task(self, task, current_idx, total_count):
        """Transitions study banner details smoothly to the next task sequence."""
        if not hasattr(self, "study_banner") or self.study_banner is None:
            return
        self.lbl_study_counter.config(text=f"📋 Task {current_idx}/{total_count}")
        self.lbl_task_name.config(text=f"Active Referent: {task['name']}")
        self.lbl_task_desc.config(text=task["instructions"])

    def show_study_completed(self):
        """Displays a beautiful celebration state and informs user of task completions."""
        if not hasattr(self, "study_banner") or self.study_banner is None:
            return
        self.lbl_study_counter.config(text="📋 Tasks Completed!", fg=theme.ACCENT_GREEN)
        self.lbl_task_name.config(text="🎉 All study referents have been completed successfully!", fg=theme.ACCENT_GREEN)
        self.lbl_task_desc.config(text="The study data and JSON state sequences have been successfully saved to /log/ and /expressions/.\nPlease close the application to reset.")
        self.btn_study_next.config(state=tk.DISABLED, text="🎉 Done!", bg_color=theme.BORDER_COLOR, fg_color=theme.TEXT_MUTED)
        
        # Visual alert popup
        tk.messagebox.showinfo(
            "Study Completed", 
            "Congratulations! All referent tasks are complete.\nThe participant logs are stored in /log/ and waypoint sequences in /expressions/.\n\nYou can now close the application."
        )
