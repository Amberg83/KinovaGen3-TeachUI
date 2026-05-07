import tkinter as tk
from tkinter import ttk
from view.widgets import ToolTip
from view import theme

class SequenceTimelinePanel(ttk.LabelFrame):
    """Encapsulates Column 2: The sequence timeline list (Treeview), file utilities, and media playback control buttons."""
    def __init__(self, parent, **kwargs):
        kwargs.setdefault("text", "2. Sequence Timeline List")
        super().__init__(parent, style="TLabelframe", **kwargs)
        self._move_entry_cb = None
        self._drag_start_row = None
        self._drag_start_idx = None
        self.setup_ui()
        
        self.tree.bind("<ButtonPress-1>", self.on_drag_start, add="+")
        self.tree.bind("<B1-Motion>", self.on_drag_motion, add="+")
        self.tree.bind("<ButtonRelease-1>", self.on_drag_drop, add="+")

    def setup_ui(self):
        # Vertical split container inside Column 2 to hold Timeline and System Logs
        self.v_paned = ttk.PanedWindow(self, orient=tk.VERTICAL, style="TPanedwindow")
        self.v_paned.pack(fill="both", expand=True)
        
        timeline_sub_frame = tk.Frame(self.v_paned, bg=theme.BG_CARD)
        logs_sub_frame = ttk.LabelFrame(self.v_paned, text="System Logs", style="TLabelframe", padding=5)
        
        # Add panes with reasonable default heights
        self.v_paned.add(timeline_sub_frame, weight=4)
        self.v_paned.add(logs_sub_frame, weight=1)

        # Toolbar Top
        toolbar_top = tk.Frame(timeline_sub_frame, bg=theme.BG_CARD)
        toolbar_top.pack(fill="x", pady=(0, 6))
        
        # Tool button styling helper (using cached PNG PhotoImage)
        def make_tool_btn(parent, icon_name, hover_text):
            img = theme.get_icon(icon_name)
            btn = theme.make_flat_button(
                parent, text="", image=img, bg_color=theme.BG_INPUT, 
                fg_color=theme.TEXT_PRIMARY, hover_bg=theme.BORDER_COLOR, 
                width=36, height=36, padx=0, pady=0
            )
            ToolTip(btn, hover_text)
            return btn
            
        self.btn_load_json = make_tool_btn(toolbar_top, "load", "Load Sequence List (Ctrl+O)")
        self.btn_load_json.pack(side="left", padx=2)
        
        self.btn_save_json = make_tool_btn(toolbar_top, "save", "Save Sequence List (Ctrl+S)")
        self.btn_save_json.pack(side="left", padx=2)
        
        self.btn_clear_list = make_tool_btn(toolbar_top, "clear", "Clear Sequence List (Ctrl+N)")
        self.btn_clear_list.pack(side="left", padx=2)
        
        self.lbl_active_file = tk.Label(toolbar_top, text="Active File: None", font=theme.FONT_NORMAL, bg=theme.BG_CARD, fg=theme.TEXT_MUTED)
        self.lbl_active_file.pack(side="right", padx=10)

        # Treeview Container
        tree_frame = tk.Frame(timeline_sub_frame, bg=theme.BG_CARD)
        tree_frame.pack(fill="both", expand=True)
        
        # Using standard TTK Treeview (custom styled via style maps) with extended multi-selection
        self.tree = ttk.Treeview(tree_frame, columns=("id", "type", "position", "params"), show="headings", style="Treeview", selectmode="extended")
        self.tree.heading("id", text="ID")
        self.tree.heading("type", text="Type")
        self.tree.heading("position", text="Position (°)")
        self.tree.heading("params", text="Parameters")
        
        self.tree.column("id", width=30, anchor="center")
        self.tree.column("type", width=100, anchor="center")
        self.tree.column("position", width=250, anchor="center")
        self.tree.column("params", width=200, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)
        
        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview, style="Vertical.TScrollbar")
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)

        # Toolbar Middle (List Ops)
        list_ops = tk.Frame(timeline_sub_frame, bg=theme.BG_CARD)
        list_ops.pack(fill="x", pady=6)
        
        self.btn_move_up = make_tool_btn(list_ops, "arrow_up", "Move Entry Up (Ctrl+Up)")
        self.btn_move_up.pack(side="left", padx=2)
        
        self.btn_move_down = make_tool_btn(list_ops, "arrow_down", "Move Entry Down (Ctrl+Down)")
        self.btn_move_down.pack(side="left", padx=2)
        
        self.btn_delete = theme.make_flat_button(
            list_ops, text="", image=theme.get_icon("delete"), bg_color=theme.ACCENT_RED, 
            fg_color=theme.TEXT_PRIMARY, hover_bg="#b91c1c", 
            width=36, height=36, padx=0, pady=0
        )
        ToolTip(self.btn_delete, "Remove Marked Entries (Delete)")
        self.btn_delete.pack(side="left", padx=(15, 2))
        
        self.btn_copy = make_tool_btn(list_ops, "copy", "Copy Selected Entries (Ctrl+C)")
        self.btn_copy.pack(side="left", padx=2)
        
        self.btn_paste = make_tool_btn(list_ops, "paste", "Paste Entries Behind Selection (Ctrl+V)")
        self.btn_paste.pack(side="left", padx=2)
        
        self.btn_duplicate = make_tool_btn(list_ops, "duplicate", "Duplicate Selected Entries (Ctrl+D)")
        self.btn_duplicate.pack(side="left", padx=2)
        
        self.btn_redo = make_tool_btn(list_ops, "redo", "Redo (Ctrl+Y)")
        self.btn_redo.pack(side="right", padx=2)
        
        self.btn_undo = make_tool_btn(list_ops, "undo", "Undo (Ctrl+Z)")
        self.btn_undo.pack(side="right", padx=2)

        # Media Controls Bottom Frame
        media_frame = tk.Frame(timeline_sub_frame, bg=theme.BG_HEADER, pady=6, padx=10,
                               highlightbackground=theme.BORDER_COLOR, highlightthickness=1)
        media_frame.pack(fill="x", pady=(6, 0))
        
        self.btn_replay = theme.make_flat_button(
            media_frame, text=" Full Replay", image=theme.get_icon("play", tint=theme.BG_MAIN), compound="left",
            bg_color=theme.ACCENT_GREEN, fg_color=theme.BG_MAIN, hover_bg="#059669", 
            font_style=theme.FONT_BOLD, padx=15, pady=8
        )
        self.btn_replay.pack(side="left", padx=3)
        ToolTip(self.btn_replay, "Replay Entire Sequence (F5)")
        
        self.btn_replay_sel = theme.make_flat_button(
            media_frame, text=" Selection", image=theme.get_icon("play_selection"), compound="left",
            bg_color=theme.BG_INPUT, fg_color=theme.TEXT_PRIMARY, hover_bg=theme.BORDER_COLOR, 
            font_style=theme.FONT_BOLD, padx=15, pady=8
        )
        self.btn_replay_sel.pack(side="left", padx=3)
        ToolTip(self.btn_replay_sel, "Replay Selected Timeline Items (F6)")
        
        # Helper to build playback media control flat toggles (image-based)
        def make_media_btn(parent, icon_name, hover_text):
            img = theme.get_icon(icon_name)
            btn = theme.make_flat_button(
                parent, text="", image=img, bg_color=theme.BG_INPUT, 
                fg_color=theme.TEXT_PRIMARY, hover_bg=theme.BORDER_COLOR, 
                width=44, height=44, padx=0, pady=0
            )
            ToolTip(btn, hover_text)
            return btn

        self.btn_pause_media = make_media_btn(media_frame, "pause", "Pause/Resume Current Playback (F7)")
        self.btn_pause_media.pack(side="left", padx=3)
        
        self.btn_stop_media = make_media_btn(media_frame, "stop", "Stop Sequence Replay (F8)")
        self.btn_stop_media.pack(side="left", padx=3)
        
        self.btn_estop = theme.make_flat_button(
            media_frame, text=" E-STOP", image=theme.get_icon("estop"), compound="left",
            bg_color=theme.ACCENT_RED, fg_color=theme.TEXT_PRIMARY, hover_bg="#b91c1c", 
            font_style=theme.FONT_BOLD, padx=15, pady=8
        )
        self.btn_estop.pack(side="right", fill="x", expand=True, padx=(15, 0))
        ToolTip(self.btn_estop, "EMERGENCY STOP (Escape)")

        # Dynamic layout synchronization: Ensure Pause and Stop buttons are perfect 1:1 squares 
        # that exactly match the physical height of the Full Replay button next to them in the row.
        def sync_media_btn_height(event):
            h = event.height
            if h > 10:
                self.btn_pause_media.config(width=h, height=h)
                self.btn_stop_media.config(width=h, height=h)

        self.btn_replay.bind("<Configure>", sync_media_btn_height)

        # Build System Logs ScrolledText Terminal console inside logs_sub_frame
        from tkinter import scrolledtext
        self.log_area = scrolledtext.ScrolledText(
            logs_sub_frame, height=4, state='disabled', font=theme.FONT_MONO,
            bg="#09090b", fg=theme.TEXT_PRIMARY, insertbackground=theme.TEXT_PRIMARY,
            relief="flat", bd=0, highlightthickness=0
        )
        self.log_area.pack(fill="both", expand=True)
        
        self.log_area.tag_config('DEBUG', foreground='#818cf8')
        self.log_area.tag_config('INFO', foreground='#94a3b8')
        self.log_area.tag_config('WARNING', foreground=theme.ACCENT_YELLOW)
        self.log_area.tag_config('ERROR', foreground=theme.ACCENT_RED, font=(theme.FONT_MONO[0], theme.FONT_MONO[1], "bold"))
        self.log_area.tag_config('CRITICAL', foreground='#ffffff', background='#991b1b', font=(theme.FONT_MONO[0], theme.FONT_MONO[1], "bold"))

    def bind_commands(self, commands):
        """Binds commands relating to Column 2 interactions and buttons."""
        self.btn_load_json.config(command=commands.get("load_json_prompt"))
        self.btn_save_json.config(command=commands.get("save_json"))
        self.btn_clear_list.config(command=commands.get("clear_list"))
        
        self.btn_move_up.config(command=commands.get("move_up"))
        self.btn_move_down.config(command=commands.get("move_down"))
        self.btn_delete.config(command=commands.get("delete_poses"))
        
        self.btn_copy.config(command=commands.get("copy"))
        self.btn_paste.config(command=commands.get("paste"))
        self.btn_duplicate.config(command=commands.get("duplicate"))
        self._move_entry_cb = commands.get("move_entry")
        
        self.btn_undo.config(command=commands.get("undo"))
        self.btn_redo.config(command=commands.get("redo"))
        
        self.btn_replay.config(command=commands.get("replay"))
        self.btn_replay_sel.config(command=commands.get("replay_selection"))
        self.btn_pause_media.config(command=commands.get("pause_media"))
        self.btn_stop_media.config(command=commands.get("stop_media"))
        self.btn_estop.config(command=commands.get("estop"))
        
        self.tree.bind("<<TreeviewSelect>>", commands.get("tree_select"))

    def get_selected_indices(self):
        """Retrieves indexes of selected Treeview rows."""
        return [self.tree.index(item) for item in self.tree.selection()]

    def update_sequence(self, sequence, filepath, select_index=None):
        """Re-draws the tree rows from the sequence list and updates the current active filename."""
        # Update File Label
        if filepath:
            name = filepath.split("/")[-1].split("\\")[-1]
            self.lbl_active_file.config(text=f"Active File: {name}", fg=theme.ACCENT_CYBER)
        else:
            self.lbl_active_file.config(text="Active File: None", fg=theme.TEXT_MUTED)

        # Update Treeview rows
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
            if select_index is not None:
                if isinstance(select_index, list):
                    if idx in select_index:
                        self.tree.selection_add(item)
                        if idx == select_index[0]:
                            self.tree.see(item)
                elif idx == select_index:
                    self.tree.selection_set(item)
                    self.tree.see(item)

    def on_drag_start(self, event):
        row_id = self.tree.identify_row(event.y)
        if row_id:
            self._drag_start_row = row_id
            self._drag_start_idx = self.tree.index(row_id)
        else:
            self._drag_start_row = None
            self._drag_start_idx = None

    def on_drag_motion(self, event):
        if getattr(self, "_drag_start_row", None):
            self.tree.config(cursor="hand2")

    def on_drag_drop(self, event):
        self.tree.config(cursor="")
        start_row = getattr(self, "_drag_start_row", None)
        if start_row:
            target_row = self.tree.identify_row(event.y)
            if target_row and target_row != start_row:
                target_idx = self.tree.index(target_row)
                if self._move_entry_cb:
                    self._move_entry_cb(self._drag_start_idx, target_idx)
        self._drag_start_row = None
        self._drag_start_idx = None
