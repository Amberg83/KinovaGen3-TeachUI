import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from view.panels import LiveStatePanel, SequenceTimelinePanel, WaypointInspectorPanel
from view import theme

class RobotView:
    def __init__(self, root):
        self.root = root
        self.root.title("Robot Teach-In Controller (Dashboard)")
        self.root.geometry("1450x820") 
        self.root.configure(fg_color=theme.BG_MAIN)
        
        # Maximize the dashboard window dynamically (Windows + Linux cross-platform compliant)
        try:
            self.root.state('zoomed')
        except Exception:
            try:
                self.root.attributes('-zoomed', True)
            except Exception:
                pass
        
        self.commands = {}
        self.is_dialog_open = False
        self._last_hardware_state = None
        self._last_status_text = ""
        self._last_status_fg = ""
        self._last_fault_state = None
        
        # Configure our visual design system (TTK styling)
        theme.configure_flat_styles()
 
        self.setup_ui()
        self.root.after(50, self._tick_live_ui)
 
    def setup_ui(self):
        # --- HEADER (Connection Status & Header Operations) ---
        status_frame = ctk.CTkFrame(
            self.root, fg_color=theme.BG_HEADER, corner_radius=0,
            border_color=theme.BORDER_COLOR, border_width=1
        )
        status_frame.pack(fill="x")
        
        # Premium custom flat fault indicator pill badge (Left-aligned)
        self.lbl_fault_badge = theme.make_label(
            status_frame, text="OFFLINE", font=theme.FONT_BOLD,
            fg_color=theme.BG_INPUT, text_color=theme.TEXT_MUTED,
            padx=12, pady=4, corner_radius=4
        )
        self.lbl_fault_badge.pack(side="left", padx=15, pady=8)

        # Connection status badge (Center-aligned using geometric placement)
        self.lbl_status = theme.make_label(
            status_frame, text=" DISCONNECTED", image=theme.get_icon("disconnected"),
            compound="left", font=theme.FONT_BOLD, fg_color=theme.BG_INPUT,
            text_color=theme.TEXT_MUTED, padx=15, pady=4, corner_radius=4
        )
        self.lbl_status.place(relx=0.5, rely=0.5, anchor="center")
        
        btn_frame = ctk.CTkFrame(status_frame, fg_color=theme.BG_HEADER, corner_radius=0)
        btn_frame.pack(side="right", padx=15, pady=8)
        
        self.btn_reconnect = theme.make_flat_button(
            btn_frame, text=" Reconnect", image=theme.get_icon("reconnect"), compound="left", bg_color=theme.BG_INPUT, 
            fg_color=theme.TEXT_PRIMARY, hover_bg=theme.BORDER_COLOR, 
            font_style=theme.FONT_BOLD
        )
        self.btn_reconnect.pack(side="left", padx=5)
        
        self.btn_clear_faults = theme.make_flat_button(
            btn_frame, text=" Clear Faults", image=theme.get_icon("wrench", tint=theme.BG_MAIN), compound="left", bg_color=theme.ACCENT_ORANGE, 
            fg_color=theme.BG_MAIN, hover_bg="#d97706", 
            font_style=theme.FONT_BOLD
        )
        self.btn_clear_faults.pack(side="left", padx=5)

        # --- 3-COLUMN MAIN LAYOUT ---
        self.content_frame = content_frame = ctk.CTkFrame(self.root, fg_color=theme.BG_MAIN, corner_radius=0)
        content_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Proportional ratio tracking for 3 columns (sums to 1.0)
        self.panel_ratios = [0.22, 0.56, 0.22]
        
        # Columns Packages instantiation (parented to content_frame)
        self.panel_live = LiveStatePanel(content_frame)
        self.panel_seq = SequenceTimelinePanel(content_frame)
        self.panel_insp = WaypointInspectorPanel(content_frame)

        # Disable geometry propagation so they respect the exact configured layout sizes
        self.panel_live.pack_propagate(False)
        self.panel_live.grid_propagate(False)
        self.panel_seq.pack_propagate(False)
        self.panel_seq.grid_propagate(False)
        self.panel_insp.pack_propagate(False)
        self.panel_insp.grid_propagate(False)

        # Create custom vertical dragging dividers (glowing separators)
        self.panel_sep_0 = ctk.CTkFrame(content_frame, fg_color="transparent", cursor="sb_h_double_arrow", width=6)
        self.panel_sep_1 = ctk.CTkFrame(content_frame, fg_color="transparent", cursor="sb_h_double_arrow", width=6)

        # Hover animations for panel separators
        def on_p_sep_enter(sep, event):
            sep.configure(fg_color=theme.ACCENT_CYBER)
            
        def on_p_sep_leave(sep, event):
            sep.configure(fg_color="transparent")
            
        self.panel_sep_0.bind("<Enter>", lambda e, s=self.panel_sep_0: on_p_sep_enter(s, e))
        self.panel_sep_0.bind("<Leave>", lambda e, s=self.panel_sep_0: on_p_sep_leave(s, e))
        self.panel_sep_1.bind("<Enter>", lambda e, s=self.panel_sep_1: on_p_sep_enter(s, e))
        self.panel_sep_1.bind("<Leave>", lambda e, s=self.panel_sep_1: on_p_sep_leave(s, e))

        # Bind resizing drag-motion events to dividers
        self.panel_sep_0.bind("<ButtonPress-1>", lambda e: self.on_p_sep_press(0, e))
        self.panel_sep_0.bind("<B1-Motion>", self.on_p_sep_motion)
        self.panel_sep_0.bind("<ButtonRelease-1>", self.on_p_sep_release)
        
        self.panel_sep_1.bind("<ButtonPress-1>", lambda e: self.on_p_sep_press(1, e))
        self.panel_sep_1.bind("<B1-Motion>", self.on_p_sep_motion)
        self.panel_sep_1.bind("<ButtonRelease-1>", self.on_p_sep_release)

        # Handle responsive resize on content_frame configure event
        content_frame.bind("<Configure>", self.on_content_resize)

        # Expose the System Logs Console from Column 2 to the global logger
        self.log_area = self.panel_seq.log_area

    def bind_commands(self, commands):
        """Binds abstract intent callbacks from the Controller to View/Panel nodes."""
        self.commands = commands
        
        # Connect Header items
        self.btn_reconnect.configure(command=self.commands.get("reconnect"))
        self.btn_clear_faults.configure(command=self.commands.get("clear_faults"))
        
        # Bind Column 1
        self.panel_live.bind_commands(
            capture_pose_cb=self.on_capture_pose,
            apply_admittance_cb=self.on_apply_admittance,
            move_default_cb=self.on_move_default
        )
        
        # Bind Column 2
        self.panel_seq.bind_commands({
            "load_json_prompt": self.prompt_load_json,
            "save_json": self.commands.get("save_json"),
            "clear_list": self.commands.get("clear_list"),
            "move_up": self.on_move_up,
            "move_down": self.on_move_down,
            "delete_poses": self.on_delete_poses,
            "copy": self.on_copy,
            "paste": self.on_paste,
            "duplicate": self.on_duplicate,
            "move_entry": self.commands.get("move_entry"),
            "undo": self.commands.get("undo"),
            "redo": self.commands.get("redo"),
            "replay": self.commands.get("replay"),
            "replay_selection": self.commands.get("replay_selection"),
            "pause_media": self.on_pause_media,
            "stop_media": self.commands.get("stop_media"),
            "estop": self.commands.get("estop"),
            "tree_select": self.on_tree_select,
            "add_pause": self.on_add_pause,
            "add_gripper": self.on_add_gripper
        })
        
        # Bind Column 3
        self.panel_insp.bind_commands({
            "preview_pose": self.on_preview_pose,
            "save_settings": self.on_save_waypoint,
            "append_pose": self.on_append_inspector_pose,
            "apply_min_durations": self.on_apply_min_durations
        })

        # Global Hotkey listeners
        self.root.bind("<Control-Up>", self.on_move_up)
        self.root.bind("<Control-Down>", self.on_move_down)
        self.root.bind("<Delete>", self.on_delete_poses)
        
        self.root.bind("<Control-z>", lambda e: self.commands.get("undo")() if self.commands.get("undo") else None)
        self.root.bind("<Control-y>", lambda e: self.commands.get("redo")() if self.commands.get("redo") else None)
        self.root.bind("<Control-Z>", lambda e: self.commands.get("undo")() if self.commands.get("undo") else None)
        self.root.bind("<Control-Y>", lambda e: self.commands.get("redo")() if self.commands.get("redo") else None)
        
        self.root.bind("<Control-c>", self.on_copy)
        self.root.bind("<Control-v>", self.on_paste)
        self.root.bind("<Control-d>", self.on_duplicate)
        self.root.bind("<Control-C>", self.on_copy)
        self.root.bind("<Control-V>", self.on_paste)
        self.root.bind("<Control-D>", self.on_duplicate)

        # File Operations
        self.root.bind("<Control-s>", lambda e: self.commands.get("save_json")() if self.commands.get("save_json") else None)
        self.root.bind("<Control-S>", lambda e: self.commands.get("save_json")() if self.commands.get("save_json") else None)
        self.root.bind("<Control-o>", lambda e: self.prompt_load_json())
        self.root.bind("<Control-O>", lambda e: self.prompt_load_json())
        self.root.bind("<Control-n>", lambda e: self.commands.get("clear_list")() if self.commands.get("clear_list") else None)
        self.root.bind("<Control-N>", lambda e: self.commands.get("clear_list")() if self.commands.get("clear_list") else None)

        # Capture Pose
        self.root.bind("<Control-space>", lambda e: self.on_capture_pose())

        # Playback Controls
        self.root.bind("<F5>", lambda e: self.commands.get("replay")() if self.commands.get("replay") else None)
        self.root.bind("<F6>", lambda e: self.commands.get("replay_selection")() if self.commands.get("replay_selection") else None)
        self.root.bind("<F7>", lambda e: self.on_pause_media())
        self.root.bind("<F8>", lambda e: self.commands.get("stop_media")() if self.commands.get("stop_media") else None)
        self.root.bind("<Escape>", lambda e: self.commands.get("estop")() if self.commands.get("estop") else None)

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
        wp_type = self.panel_insp.wp_type_var.get()
        if wp_type == "pause":
            return
            
        if wp_type == "gripper":
            params = self.panel_insp.get_waypoint_params()
            state = params.get("gripper_state", "open")
            duration = params.get("gripper_duration", "medium")
            target_pos = params.get("gripper_target_pos", 0.0)
            speed_ratio = params.get("gripper_speed_ratio", 0.0)
            
            if "preview_gripper" in self.commands:
                self.commands["preview_gripper"](state, duration, target_pos, speed_ratio)
            return

        poses = self.panel_insp.get_inspector_poses()
        if poses and "preview_pose" in self.commands:
            self.commands["preview_pose"](poses)

    def on_append_inspector_pose(self) -> None:
        params = self.panel_insp.get_waypoint_params()
        poses = self.panel_insp.get_inspector_poses()
        if poses and "append_inspector_pose" in self.commands:
            self.commands["append_inspector_pose"](params, poses)
            
    def on_apply_min_durations(self, speed="fast"):
        indices = self.panel_seq.get_selected_indices()
        if indices and "apply_min_durations" in self.commands:
            self.commands["apply_min_durations"](indices, speed)
    
    def on_apply_admittance(self):
        mode = self.panel_live.get_selected_admittance_mode()
        if mode and "set_admittance" in self.commands:
            self.commands["set_admittance"](mode)

    def on_move_default(self):
        if "move_default" in self.commands:
            self.commands["move_default"]()

    def on_tree_select(self, event):
        indices = self.panel_seq.get_selected_indices()
        if not indices: return
        if len(indices) > 1:
            # Enter bulk editing mode in Inspector
            from utils.event_bus import EventBus
            EventBus.publish("clear_preview_angles")
            self.panel_insp.enter_bulk_edit_mode(indices)
        else:
            if "tree_select" in self.commands:
                self.commands["tree_select"](indices[0])

    def on_add_pause(self):
        indices = self.panel_seq.get_selected_indices()
        target_idx = indices[-1] if indices else None
        if "add_pause" in self.commands:
            self.commands["add_pause"](target_idx)

    def on_add_gripper(self):
        indices = self.panel_seq.get_selected_indices()
        target_idx = indices[-1] if indices else None
        if "add_gripper" in self.commands:
            self.commands["add_gripper"](target_idx)

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

    def on_copy(self, event=None):
        indices = self.panel_seq.get_selected_indices()
        if indices and "copy" in self.commands:
            self.commands["copy"](indices)

    def on_paste(self, event=None):
        indices = self.panel_seq.get_selected_indices()
        after_index = indices[-1] if indices else None
        if "paste" in self.commands:
            self.commands["paste"](after_index)

    def on_duplicate(self, event=None):
        indices = self.panel_seq.get_selected_indices()
        if indices and "duplicate" in self.commands:
            self.commands["duplicate"](indices)

    def on_pause_media(self):
        is_paused = self.commands.get("pause_media")() if "pause_media" in self.commands else False
        self.panel_seq.btn_pause_media.configure(text_color="orange" if is_paused else "white")

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
        """Dispatched from sequence model changes. Updates Column 2 and synchronizes Column 3 selection."""
        self.panel_seq.update_sequence(sequence, filepath, select_index)

        # Clear or synchronize inspector based on current selections after sequence updates
        indices = self.panel_seq.get_selected_indices()
        if not sequence or not indices:
            self.panel_insp.clear_inspector()
        elif len(indices) == 1:
            if "tree_select" in self.commands:
                self.commands["tree_select"](indices[0])
        else:
            from utils.event_bus import EventBus
            EventBus.publish("clear_preview_angles")
            self.panel_insp.enter_bulk_edit_mode(indices)

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
        # 1. Update Connection Status Label (Symmetric pill style centered)
        current_conn_state = (state.is_connected, getattr(state, "ip", "Unknown"), getattr(state, "dof", 0))
        if current_conn_state != self._last_status_text:
            self._last_status_text = current_conn_state
            if state.is_connected:
                self.lbl_status.configure(
                    text=f" CONNECTED: {current_conn_state[1]} ({current_conn_state[2]}-DOF)",
                    image=theme.get_icon("connected"),
                    compound="left",
                    fg_color="#172554",   # Deep dark navy-blue background
                    text_color="#93c5fd"    # Bright sky-blue text
                )
            else:
                self.lbl_status.configure(
                    text=" DISCONNECTED",
                    image=theme.get_icon("disconnected"),
                    compound="left",
                    fg_color=theme.BG_INPUT,
                    text_color=theme.TEXT_MUTED
                )

        # 2. Update Fault Status Badge (Separate & highly prominent)
        current_fault_state = (state.is_connected, getattr(state, "has_fault", False))
        if current_fault_state != self._last_fault_state:
            self._last_fault_state = current_fault_state
            if not state.is_connected:
                self.lbl_fault_badge.configure(text="OFFLINE", image="", compound="none", fg_color=theme.BG_INPUT, text_color=theme.TEXT_MUTED)
            else:
                if state.has_fault:
                    self.lbl_fault_badge.configure(
                        text="ARM FAULT ACTIVE", 
                        image=theme.get_icon("fault"),
                        compound="left",
                        fg_color=theme.ACCENT_RED, 
                        text_color=theme.TEXT_PRIMARY
                    )
                else:
                    self.lbl_fault_badge.configure(
                        text="SYSTEM HEALTHY", 
                        image=theme.get_icon("healthy"),
                        compound="left",
                        fg_color="#064e3b",   # Rich dark emerald background
                        text_color="#a7f3d0"    # Soft mint green foreground
                    )

        if not state.is_connected: return

        # Delegate telemetry displays
        self.panel_live.update_telemetry(state)

    # ================= PUBLIC API INTERFACES FOR CONTROLLER =================
    def load_inspector_data(self, data, index, predecessor_pos=None, run_poses=None, run_selected_idx=None):
        """Called by controller to load a selected waypoint into the editor form."""
        self.panel_insp.load_inspector_data(data, index, predecessor_pos, run_poses, run_selected_idx)

    # ================= STUDY MODE WIDGET DECORATIONS =================

    def enable_study_mode(self, pid, first_task, current_idx, total_count, on_completed_callback):
        """Builds a beautiful premium banner panel representing participant task progress."""
        self.study_banner = ctk.CTkFrame(
            self.root, fg_color=theme.BG_CARD, corner_radius=6,
            border_color=theme.ACCENT_CYBER, border_width=1
        )
        # Pack right beneath the main status_frame
        self.study_banner.pack(fill="x", before=self.root.pack_slaves()[1], padx=10, pady=(5, 0))
        
        # Grid layout for high-density information
        self.study_banner.columnconfigure(0, weight=1)
        self.study_banner.columnconfigure(1, weight=3)
        self.study_banner.columnconfigure(2, weight=0)
        
        info_frame = ctk.CTkFrame(self.study_banner, fg_color=theme.BG_CARD, corner_radius=0)
        info_frame.grid(row=0, column=0, sticky="w", padx=15, pady=10)
        
        self.lbl_study_p = theme.make_label(
            info_frame, text=f" Participant: #{pid}", image=theme.get_icon("participant"), compound="left",
            font=theme.FONT_BOLD, fg_color=theme.BG_CARD, text_color=theme.TEXT_PRIMARY
        )
        self.lbl_study_p.pack(anchor="w")
        
        self.lbl_study_counter = theme.make_label(
            info_frame, text=f" Task {current_idx}/{total_count}", image=theme.get_icon("task"), compound="left",
            font=theme.FONT_BOLD, fg_color=theme.BG_CARD, text_color=theme.ACCENT_CYBER
        )
        self.lbl_study_counter.pack(anchor="w", pady=(2, 0))
        
        inst_frame = ctk.CTkFrame(self.study_banner, fg_color=theme.BG_CARD, corner_radius=0)
        inst_frame.grid(row=0, column=1, sticky="w", padx=20, pady=10)
        
        self.lbl_task_name = theme.make_label(
            inst_frame, text=f"Active Referent: {first_task['name']}", 
            font=(theme.FONT_NORMAL[0], theme.FONT_NORMAL[1] + 1, "bold"), 
            fg_color=theme.BG_CARD, text_color=theme.TEXT_PRIMARY
        )
        self.lbl_task_name.pack(anchor="w")
        
        self.lbl_task_desc = theme.make_label(
            inst_frame, text=first_task["instructions"], 
            font=theme.FONT_NORMAL, fg_color=theme.BG_CARD, text_color=theme.TEXT_MUTED,
            justify="left", wraplength=800
        )
        self.lbl_task_desc.pack(anchor="w", pady=(2, 0))
        
        self.btn_study_next = theme.make_flat_button(
            self.study_banner, text=" Task Completed / Next Referent", image=theme.get_icon("play"), compound="left",
            bg_color=theme.ACCENT_GREEN, fg_color=theme.BG_MAIN, 
            hover_bg="#059669", font_style=theme.FONT_BOLD, 
            command=on_completed_callback
        )
        self.btn_study_next.grid(row=0, column=2, sticky="e", padx=15, pady=10)

        # Predefined Gestures buttons frame initialization
        self.gestures_btn_frame = None
        self._check_and_create_tutorial_buttons(first_task, inst_frame)

    def _check_and_create_tutorial_buttons(self, task, parent_frame):
        # Scan predefined_gestures/ directory if task ID is 101
        if task and task.get("id") == 101:
            import os
            gestures_dir = "predefined_gestures"
            if not os.path.exists(gestures_dir):
                return
                
            json_files = [f for f in os.listdir(gestures_dir) if f.endswith(".json")]
            if not json_files:
                return
                
            self.gestures_btn_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
            self.gestures_btn_frame.pack(anchor="w", pady=(8, 0))
            
            theme.make_label(
                self.gestures_btn_frame, text="Predefined Gestures: ", 
                font=theme.FONT_BOLD, fg_color="transparent", text_color=theme.ACCENT_CYBER
            ).pack(side="left")
            
            from utils.event_bus import EventBus
            for f in sorted(json_files):
                gesture_name = f.replace(".json", "").capitalize()
                filepath = os.path.join(gestures_dir, f)
                
                btn = theme.make_flat_button(
                    self.gestures_btn_frame, text=gesture_name,
                    bg_color=theme.BG_INPUT, fg_color=theme.TEXT_PRIMARY, hover_bg=theme.BORDER_COLOR,
                    font_style=theme.FONT_NORMAL,
                    command=lambda fp=filepath: EventBus.publish("play_predefined_gesture", fp)
                )
                btn.pack(side="left", padx=4)

    def _destroy_tutorial_buttons(self):
        if hasattr(self, "gestures_btn_frame") and self.gestures_btn_frame is not None:
            try:
                self.gestures_btn_frame.destroy()
            except Exception:
                pass
            self.gestures_btn_frame = None

    def update_study_task(self, task, current_idx, total_count):
        """Transitions study banner details smoothly to the next task sequence."""
        if not hasattr(self, "study_banner") or self.study_banner is None:
            return
        
        # Destroy previous buttons first
        self._destroy_tutorial_buttons()
        
        self.lbl_study_counter.configure(text=f" Task {current_idx}/{total_count}")
        self.lbl_task_name.configure(text=f"Active Referent: {task['name']}")
        self.lbl_task_desc.configure(text=task["instructions"])
        
        # Check and create new ones
        self._check_and_create_tutorial_buttons(task, self.lbl_task_name.master)

    def show_study_completed(self):
        """Displays a beautiful celebration state and informs user of task completions."""
        if not hasattr(self, "study_banner") or self.study_banner is None:
            return
        self.lbl_study_counter.configure(text=" Tasks Completed!", text_color=theme.ACCENT_GREEN)
        self.lbl_task_name.configure(text="All study referents have been completed successfully!", text_color=theme.ACCENT_GREEN)
        self.lbl_task_desc.configure(text="The study data and JSON state sequences have been successfully saved to /log/ and /expressions/.\nPlease close the application to reset.")
        self.btn_study_next.configure(state="disabled", text="Done!", fg_color=theme.BORDER_COLOR, text_color=theme.TEXT_MUTED)
        
        # Visual alert popup
        messagebox.showinfo(
            "Study Completed", 
            "Congratulations! All referent tasks are complete.\nThe participant logs are stored in /log/ and waypoint sequences in /expressions/.\n\nYou can now close the application."
        )

    def on_content_resize(self, event):
        """Called automatically when the main content container resizes (e.g. window scaling)."""
        # CRITICAL: Only respond to resize events on the content_frame itself (or its rendering canvas),
        # ignore any bubbled-up configure events from child widgets!
        if event.widget != self.content_frame and event.widget != getattr(self.content_frame, "_canvas", None):
            return
            
        scaling = self.root._get_window_scaling()
        logical_W = event.width / scaling
        logical_H = event.height / scaling
        self.layout_panels(logical_W, logical_H)
        
        # Dynamically adjust the wrap length of study banner instructions
        if hasattr(self, "lbl_task_desc") and self.lbl_task_desc is not None:
            # Prevent overflowing Column 2 (Next button) by allocating the responsive width
            wrap_w = max(400, int(logical_W - 500))
            self.lbl_task_desc.configure(wraplength=wrap_w)

    def layout_panels(self, W, H):
        """Precisely calculates and places columns and vertical separators using absolute pixels."""
        # Total spacing taken by both vertical dividers (2 * 6px)
        total_panel_w = W - 12
        if total_panel_w <= 100:
            return
            
        # Compute exact widths according to proportions
        w0 = int(total_panel_w * self.panel_ratios[0])
        w1 = int(total_panel_w * self.panel_ratios[1])
        w2 = total_panel_w - w0 - w1
        
        # Geometry layout propagation using native CTk .configure for scaling
        self.panel_live.configure(width=w0, height=H)
        self.panel_live.place(x=0, y=0)
        self.panel_live.apply_layout(w0 >= 290)
        
        x_sep0 = w0
        self.panel_sep_0.configure(width=6, height=H)
        self.panel_sep_0.place(x=x_sep0, y=0)
        
        self.panel_seq.configure(width=w1, height=H)
        self.panel_seq.place(x=x_sep0 + 6, y=0)
        self.panel_seq.layout_vertical_panels(w1, H)
        
        x_sep1 = x_sep0 + 6 + w1
        self.panel_sep_1.configure(width=6, height=H)
        self.panel_sep_1.place(x=x_sep1, y=0)
        
        self.panel_insp.configure(width=w2, height=H)
        self.panel_insp.place(x=x_sep1 + 6, y=0)
        self.panel_insp.apply_layout(w2 >= 290)

    def on_p_sep_press(self, sep_idx, event):
        """Initializes drag-state tracing on separator click."""
        self._drag_p_sep_idx = sep_idx
        self._drag_p_start_x = event.x_root
        self._drag_p_start_ratios = list(self.panel_ratios)
        self._drag_p_frame_w = self.panel_live.master.winfo_width()
        
    def on_p_sep_motion(self, event):
        """Recalculates ratios in real-time based on absolute pointer movement."""
        if getattr(self, "_drag_p_sep_idx", None) is None:
            return
            
        scaling = self.root._get_window_scaling()
        # Fetch physical width and unscale it for ratio checks
        W_physical = self.content_frame.winfo_width()
        W_logical = W_physical / scaling
        
        dx = event.x_root - self._drag_p_start_x
        
        # Determine movement in terms of proportional width ratio (physical dx / physical total width)
        # Note: both are in physical pixels, so the ratio is correct
        dr = dx / (W_physical - 12)
        
        # Enforce robust minimum column width limits of 200px (logical pixels)
        min_ratio = 200 / W_logical
        
        new_ratios = list(self._drag_p_start_ratios)
        if self._drag_p_sep_idx == 0:
            r0 = self._drag_p_start_ratios[0] + dr
            r1 = self._drag_p_start_ratios[1] - dr
            if r0 >= min_ratio and r1 >= min_ratio:
                new_ratios[0] = r0
                new_ratios[1] = r1
                self.panel_ratios = new_ratios
                logical_H = self.content_frame.winfo_height() / scaling
                self.layout_panels(W_logical, logical_H)
                
        elif self._drag_p_sep_idx == 1:
            r1 = self._drag_p_start_ratios[1] + dr
            r2 = self._drag_p_start_ratios[2] - dr
            if r1 >= min_ratio and r2 >= min_ratio:
                new_ratios[1] = r1
                new_ratios[2] = r2
                self.panel_ratios = new_ratios
                logical_H = self.content_frame.winfo_height() / scaling
                self.layout_panels(W_logical, logical_H)

    def on_p_sep_release(self, event):
        """Ends active resizing drag operations."""
        self._drag_p_sep_idx = None
