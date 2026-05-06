import tkinter as tk
from tkinter import ttk
from view.widgets import ToolTip
from view import theme

class SequenceTimelinePanel(ttk.LabelFrame):
    """Encapsulates Column 2: The sequence timeline list (Treeview), file utilities, and media playback control buttons."""
    def __init__(self, parent, **kwargs):
        kwargs.setdefault("text", "2. Sequence Timeline List")
        super().__init__(parent, style="TLabelframe", **kwargs)
        self.setup_ui()

    def setup_ui(self):
        # Toolbar Top
        toolbar_top = tk.Frame(self, bg=theme.BG_CARD)
        toolbar_top.pack(fill="x", pady=(0, 8))
        
        # Tool button styling helper
        def make_tool_btn(parent, text, hover_text, width=4):
            btn = theme.make_flat_button(
                parent, text=text, bg_color=theme.BG_INPUT, 
                fg_color=theme.TEXT_PRIMARY, hover_bg=theme.BORDER_COLOR, 
                font_style=theme.FONT_EMOJI_LARGE, width=width, pady=5
            )
            ToolTip(btn, hover_text)
            return btn
            
        self.btn_load_json = make_tool_btn(toolbar_top, "📂", "Load Sequence List", width=4)
        self.btn_load_json.pack(side="left", padx=2)
        
        self.btn_save_json = make_tool_btn(toolbar_top, "💾", "Save Sequence List", width=4)
        self.btn_save_json.pack(side="left", padx=2)
        
        self.btn_clear_list = make_tool_btn(toolbar_top, "🧹", "Clear Sequence List", width=4)
        self.btn_clear_list.pack(side="left", padx=2)
        
        self.lbl_active_file = tk.Label(toolbar_top, text="Active File: None", font=theme.FONT_NORMAL, bg=theme.BG_CARD, fg=theme.TEXT_MUTED)
        self.lbl_active_file.pack(side="right", padx=10)

        # Treeview Container
        tree_frame = tk.Frame(self, bg=theme.BG_CARD)
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
        list_ops = tk.Frame(self, bg=theme.BG_CARD)
        list_ops.pack(fill="x", pady=8)
        
        self.btn_move_up = make_tool_btn(list_ops, "⬆", "Move Entry Up", width=4)
        self.btn_move_up.pack(side="left", padx=2)
        
        self.btn_move_down = make_tool_btn(list_ops, "⬇", "Move Entry Down", width=4)
        self.btn_move_down.pack(side="left", padx=2)
        
        self.btn_delete = theme.make_flat_button(
            list_ops, text="🗑", bg_color=theme.ACCENT_RED, 
            fg_color=theme.TEXT_PRIMARY, hover_bg="#b91c1c", 
            font_style=theme.FONT_EMOJI_LARGE, width=4, pady=5
        )
        ToolTip(self.btn_delete, "Remove Marked Entries")
        self.btn_delete.pack(side="left", padx=(15, 2))
        
        self.btn_redo = make_tool_btn(list_ops, "⤻", "Redo", width=4)
        self.btn_redo.pack(side="right", padx=2)
        
        self.btn_undo = make_tool_btn(list_ops, "⤺", "Undo", width=4)
        self.btn_undo.pack(side="right", padx=2)

        # Media Controls Bottom Frame
        media_frame = tk.Frame(self, bg=theme.BG_HEADER, pady=12, padx=12,
                               highlightbackground=theme.BORDER_COLOR, highlightthickness=1)
        media_frame.pack(fill="x", pady=(10, 0))
        
        self.btn_replay = theme.make_flat_button(
            media_frame, text="▶ Full Replay", bg_color=theme.ACCENT_GREEN, 
            fg_color=theme.BG_MAIN, hover_bg="#059669", 
            font_style=theme.FONT_EMOJI_LARGE, height=2, width=14
        )
        self.btn_replay.pack(side="left", padx=5)
        
        self.btn_replay_sel = theme.make_flat_button(
            media_frame, text="▶ Selection", bg_color=theme.BG_INPUT, 
            fg_color=theme.TEXT_PRIMARY, hover_bg=theme.BORDER_COLOR, 
            font_style=theme.FONT_EMOJI_LARGE, height=2, width=14
        )
        self.btn_replay_sel.pack(side="left", padx=5)
        
        # Helper to build playback media control flat toggles
        def make_media_btn(parent, text, hover_text, width=4):
            btn = theme.make_flat_button(
                parent, text=text, bg_color=theme.BG_INPUT, 
                fg_color=theme.TEXT_PRIMARY, hover_bg=theme.BORDER_COLOR, 
                font_style=theme.FONT_EMOJI_LARGE, width=width, pady=8
            )
            ToolTip(btn, hover_text)
            return btn

        self.btn_pause_media = make_media_btn(media_frame, "⏸", "Pause/Resume current Action", width=4)
        self.btn_pause_media.pack(side="left", padx=5)
        
        self.btn_stop_media = make_media_btn(media_frame, "⏹", "Stop Sequence", width=4)
        self.btn_stop_media.pack(side="left", padx=5)
        
        self.btn_estop = theme.make_flat_button(
            media_frame, text="🛑 E-STOP", bg_color=theme.ACCENT_RED, 
            fg_color=theme.TEXT_PRIMARY, hover_bg="#b91c1c", 
            font_style=theme.FONT_EMOJI_LARGE, height=2
        )
        self.btn_estop.pack(side="right", fill="x", expand=True, padx=(20, 0))

    def bind_commands(self, commands):
        """Binds commands relating to Column 2 interactions and buttons."""
        self.btn_load_json.config(command=commands.get("load_json_prompt"))
        self.btn_save_json.config(command=commands.get("save_json"))
        self.btn_clear_list.config(command=commands.get("clear_list"))
        
        self.btn_move_up.config(command=commands.get("move_up"))
        self.btn_move_down.config(command=commands.get("move_down"))
        self.btn_delete.config(command=commands.get("delete_poses"))
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
