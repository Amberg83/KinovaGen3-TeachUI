import tkinter as tk
import customtkinter as ctk
from view.widgets import ToolTip
from view import theme
from .timeline_widgets import TimelineRowCard, SystemLogsConsole, MediaPlaybackToolbar

class SequenceTimelinePanel(ctk.CTkFrame):
    """Encapsulates Column 2: The sequence timeline list, file utilities, and media playback control buttons with fully adjustable columns."""
    def __init__(self, parent, **kwargs):
        kwargs.pop("text", None)
        super().__init__(parent, fg_color=theme.BG_MAIN, corner_radius=0, **kwargs)
        self._move_entry_cb = None
        self._drag_start_idx = None
        self.drag_proxy = None
        
        # Adjustable column settings
        self.col_widths = [60, 130, 280]  # Initial widths for Col 0 (ID), Col 1 (Type), Col 2 (Position)
        self.row_widgets = []              # References to labels of each row to synchronize resizes
        
        self.selected_indices = set()
        self.last_clicked_idx = None
        self.widget_to_idx = {}
        self._select_cb = None
        self.logs_ratio = 0.75 # Default vertical split ratio for timeline vs logs
        
        self.setup_ui()

    def setup_ui(self):
        # Panel Title Header
        self.lbl_panel_header = theme.make_label(
            self, text="2. SEQUENCE TIMELINE LIST", font=theme.FONT_TITLE,
            fg_color=theme.BG_HEADER, text_color=theme.ACCENT_CYBER,
            height=32, corner_radius=0
        )
        self.lbl_panel_header.pack(fill="x", pady=(0, 6))

        # Modern vertical split container using SectionFrame wrappers
        self.timeline_sub_frame = timeline_sub_frame = theme.SectionFrame(self, text="Sequence Timeline")
        self.timeline_sub_frame.pack_propagate(False)
        
        # Horizontal separator bar running from left to right (6px high, sb_v_double_arrow drag cursor)
        # We use theme.BG_MAIN instead of transparent to prevent Tkinter mouse event click-throughs
        self.logs_sep = ctk.CTkFrame(self, fg_color=theme.BG_MAIN, cursor="sb_v_double_arrow", height=6)
        
        # Logs bottom panel
        self.logs_sub_frame = logs_sub_frame = theme.SectionFrame(self, text="System Logs")
        self.logs_sub_frame.pack_propagate(False)
        
        # Bind hover highlight to the separator frame
        def on_sep_enter(event):
            self.logs_sep.configure(fg_color=theme.ACCENT_CYBER)
        def on_sep_leave(event):
            self.logs_sep.configure(fg_color=theme.BG_MAIN)
            
        self.logs_sep.bind("<Enter>", on_sep_enter)
        self.logs_sep.bind("<Leave>", on_sep_leave)
        
        # Bind vertical dragging events to the separator
        self.logs_sep.bind("<ButtonPress-1>", self.on_sep_press)
        self.logs_sep.bind("<B1-Motion>", self.on_sep_motion)
        self.logs_sep.bind("<ButtonRelease-1>", self.on_sep_release)
        
        # Sizing layout is now driven directly and synchronously by the parent MainView

        # Toolbar Top
        toolbar_top = ctk.CTkFrame(timeline_sub_frame.content, fg_color="transparent", corner_radius=0)
        toolbar_top.pack(fill="x", pady=(0, 6))
        
        # Tool button styling helper (using cached PNG PhotoImage)
        def make_tool_btn(parent, icon_name, hover_text):
            img = theme.get_icon(icon_name)
            btn = theme.make_flat_button(
                parent, text="", image=img, bg_color=theme.BG_INPUT, 
                fg_color=theme.TEXT_PRIMARY, hover_bg=theme.BORDER_COLOR, 
                width=36, height=36
            )
            ToolTip(btn, hover_text)
            return btn
            
        self.btn_load_json = make_tool_btn(toolbar_top, "load", "Load Sequence List (Ctrl+O)")
        self.btn_load_json.pack(side="left", padx=2)
        
        self.btn_save_json = make_tool_btn(toolbar_top, "save", "Save Sequence List (Ctrl+S)")
        self.btn_save_json.pack(side="left", padx=2)
        
        self.btn_clear_list = make_tool_btn(toolbar_top, "clear", "Clear Sequence List (Ctrl+N)")
        self.btn_clear_list.pack(side="left", padx=2)
        
        self.lbl_active_file = theme.make_label(
            toolbar_top, text="Active File: None", font=theme.FONT_NORMAL, 
            fg_color="transparent", text_color=theme.TEXT_MUTED
        )
        self.lbl_active_file.pack(side="right", padx=10)

        # Custom List Container
        tree_frame = ctk.CTkFrame(timeline_sub_frame.content, fg_color="transparent", corner_radius=0)
        tree_frame.pack(fill="both", expand=True)
        
        # Static Header Row
        self.header_row = ctk.CTkFrame(tree_frame, fg_color=theme.BG_HEADER, height=32, corner_radius=4)
        self.header_row.pack(fill="x", pady=(0, 4))
        
        self.lbl_h_id = ctk.CTkLabel(self.header_row, text="ID", width=self.col_widths[0], font=theme.FONT_BOLD, text_color=theme.TEXT_MUTED)
        self.lbl_h_id.pack(side="left")
        
        self.lbl_h_type = ctk.CTkLabel(self.header_row, text="TYPE", width=self.col_widths[1], font=theme.FONT_BOLD, text_color=theme.TEXT_MUTED)
        self.lbl_h_type.pack(side="left")
        
        self.lbl_h_pos = ctk.CTkLabel(self.header_row, text="POSITION (°)", width=self.col_widths[2], font=theme.FONT_BOLD, text_color=theme.TEXT_MUTED)
        self.lbl_h_pos.pack(side="left")
        
        self.lbl_h_param = ctk.CTkLabel(self.header_row, text="PARAMETERS", font=theme.FONT_BOLD, text_color=theme.TEXT_MUTED, anchor="w")
        self.lbl_h_param.pack(side="left", fill="x", expand=True, padx=(10, 0))

        # Create column resize separators inside the header row
        self.sep_0 = ctk.CTkFrame(self.header_row, fg_color="transparent", cursor="sb_h_double_arrow", width=5)
        self.sep_1 = ctk.CTkFrame(self.header_row, fg_color="transparent", cursor="sb_h_double_arrow", width=5)
        self.sep_2 = ctk.CTkFrame(self.header_row, fg_color="transparent", cursor="sb_h_double_arrow", width=5)
        
        # Attach subtle hover effects to separators
        def on_sep_enter(sep, event):
            sep.configure(fg_color=theme.ACCENT_CYBER)
            
        def on_sep_leave(sep, event):
            sep.configure(fg_color="transparent")
            
        self.sep_0.bind("<Enter>", lambda e, s=self.sep_0: on_sep_enter(s, e))
        self.sep_0.bind("<Leave>", lambda e, s=self.sep_0: on_sep_leave(s, e))
        self.sep_1.bind("<Enter>", lambda e, s=self.sep_1: on_sep_enter(s, e))
        self.sep_1.bind("<Leave>", lambda e, s=self.sep_1: on_sep_leave(s, e))
        self.sep_2.bind("<Enter>", lambda e, s=self.sep_2: on_sep_enter(s, e))
        self.sep_2.bind("<Leave>", lambda e, s=self.sep_2: on_sep_leave(s, e))

        # Bind resizing logic to drag movements of the separator
        self.sep_0.bind("<ButtonPress-1>", lambda e: self.on_sep_press(0, e))
        self.sep_0.bind("<B1-Motion>", self.on_sep_motion)
        self.sep_0.bind("<ButtonRelease-1>", self.on_sep_release)
        
        self.sep_1.bind("<ButtonPress-1>", lambda e: self.on_sep_press(1, e))
        self.sep_1.bind("<B1-Motion>", self.on_sep_motion)
        self.sep_1.bind("<ButtonRelease-1>", self.on_sep_release)
        
        self.sep_2.bind("<ButtonPress-1>", lambda e: self.on_sep_press(2, e))
        self.sep_2.bind("<B1-Motion>", self.on_sep_motion)
        self.sep_2.bind("<ButtonRelease-1>", self.on_sep_release)
        
        self.update_header_separators()

        # Custom Scrollable List Frame
        self.scroll_frame = ctk.CTkScrollableFrame(
            tree_frame, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=theme.BG_INPUT,
            scrollbar_button_hover_color=theme.BORDER_COLOR
        )
        self.scroll_frame.pack(fill="both", expand=True)

        # Toolbar Middle (List Ops)
        list_ops = ctk.CTkFrame(timeline_sub_frame.content, fg_color="transparent", corner_radius=0)
        list_ops.pack(fill="x", pady=6)
        
        self.btn_move_up = make_tool_btn(list_ops, "arrow_up", "Move Entry Up (Ctrl+Up)")
        self.btn_move_up.pack(side="left", padx=2)
        
        self.btn_move_down = make_tool_btn(list_ops, "arrow_down", "Move Entry Down (Ctrl+Down)")
        self.btn_move_down.pack(side="left", padx=2)
        
        self.btn_delete = theme.make_flat_button(
            list_ops, text="", image=theme.get_icon("delete"), bg_color=theme.ACCENT_RED, 
            fg_color=theme.TEXT_PRIMARY, hover_bg="#b91c1c", 
            width=36, height=36
        )
        ToolTip(self.btn_delete, "Remove Marked Entries (Delete)")
        self.btn_delete.pack(side="left", padx=(15, 2))
        
        self.btn_copy = make_tool_btn(list_ops, "copy", "Copy Selected Entries (Ctrl+C)")
        self.btn_copy.pack(side="left", padx=2)
        
        self.btn_paste = make_tool_btn(list_ops, "paste", "Paste Clipboard Entries (Ctrl+V)")
        self.btn_paste.pack(side="left", padx=2)
        
        self.btn_duplicate = make_tool_btn(list_ops, "duplicate", "Duplicate Selection (Ctrl+D)")
        self.btn_duplicate.pack(side="left", padx=2)
        
        self.btn_undo = make_tool_btn(list_ops, "undo", "Undo Step (Ctrl+Z)")
        self.btn_undo.pack(side="right", padx=2)
        
        self.btn_redo = make_tool_btn(list_ops, "redo", "Redo Step (Ctrl+Y)")
        self.btn_redo.pack(side="right", padx=2)

        # Toolbar Bottom (Playback / Media Control Center)
        self.playback_toolbar = MediaPlaybackToolbar(timeline_sub_frame.content)
        self.playback_toolbar.pack(fill="x", pady=(6, 0))
        
        # Expose references for controller bindings and main view toggles
        self.btn_replay = self.playback_toolbar.btn_replay
        self.btn_replay_sel = self.playback_toolbar.btn_replay_sel
        self.btn_pause_media = self.playback_toolbar.btn_pause_media
        self.btn_stop_media = self.playback_toolbar.btn_stop_media
        self.btn_estop = self.playback_toolbar.btn_estop

        # Build System Logs Console Component
        self.logs_console = SystemLogsConsole(logs_sub_frame.content)
        self.logs_console.pack(fill="both", expand=True)
        self.log_area = self.logs_console.textbox

    def update_header_separators(self):
        """Calculates and places column resizing markers inside the header frame."""
        # Separator 0 (moves boundary of ID / Type)
        x0 = self.col_widths[0]
        self.sep_0.place(x=x0 - 2, y=0, relheight=1.0)
        
        # Separator 1 (moves boundary of Type / Position)
        x1 = self.col_widths[0] + self.col_widths[1]
        self.sep_1.place(x=x1 - 2, y=0, relheight=1.0)
        
        # Separator 2 (moves boundary of Position / Parameters)
        x2 = self.col_widths[0] + self.col_widths[1] + self.col_widths[2]
        self.sep_2.place(x=x2 - 2, y=0, relheight=1.0)

    def on_sep_press(self, sep_idx, event):
        """Records initial drag position and state on click."""
        self._drag_sep_idx = sep_idx
        self._drag_start_x = event.x_root
        self._drag_start_width = self.col_widths[sep_idx]

    def on_sep_motion(self, event):
        """Dynamically computes delta mouse position and scales columns in real-time."""
        if getattr(self, "_drag_sep_idx", None) is not None:
            dx = event.x_root - self._drag_start_x
            new_width = max(30, self._drag_start_width + dx)  # Enforce minimum column width of 30px
            
            # Update width in state
            self.col_widths[self._drag_sep_idx] = new_width
            
            # Propagate geometry shifts to all row cells and move headers
            self.apply_column_widths()
            self.update_header_separators()

    def on_sep_release(self, event):
        """Clears drag separator token."""
        self._drag_sep_idx = None

    def apply_column_widths(self):
        """Updates width parameter of header cells and row cells instantly."""
        self.lbl_h_id.configure(width=self.col_widths[0])
        self.lbl_h_type.configure(width=self.col_widths[1])
        self.lbl_h_pos.configure(width=self.col_widths[2])
        
        for cells in self.row_widgets:
            if cells["id"].winfo_exists():
                cells["id"].configure(width=self.col_widths[0])
            if cells["type"].winfo_exists():
                cells["type"].configure(width=self.col_widths[1])
            if cells["pos"].winfo_exists():
                cells["pos"].configure(width=self.col_widths[2])

    def bind_commands(self, commands):
        """Binds commands relating to Column 2 interactions and buttons."""
        self.btn_load_json.configure(command=commands.get("load_json_prompt"))
        self.btn_save_json.configure(command=commands.get("save_json"))
        self.btn_clear_list.configure(command=commands.get("clear_list"))
        
        self.btn_move_up.configure(command=commands.get("move_up"))
        self.btn_move_down.configure(command=commands.get("move_down"))
        self.btn_delete.configure(command=commands.get("delete_poses"))
        
        self.btn_copy.configure(command=commands.get("copy"))
        self.btn_paste.configure(command=commands.get("paste"))
        self.btn_duplicate.configure(command=commands.get("duplicate"))
        self._move_entry_cb = commands.get("move_entry")
        
        self.btn_undo.configure(command=commands.get("undo"))
        self.btn_redo.configure(command=commands.get("redo"))
        
        self.btn_replay.configure(command=commands.get("replay"))
        self.btn_replay_sel.configure(command=commands.get("replay_selection"))
        self.btn_pause_media.configure(command=commands.get("pause_media"))
        self.btn_stop_media.configure(command=commands.get("stop_media"))
        self.btn_estop.configure(command=commands.get("estop"))
        
        self._select_cb = commands.get("tree_select")

    def get_selected_indices(self):
        """Retrieves indexes of selected rows."""
        return sorted(list(self.selected_indices))

    def update_sequence(self, sequence, filepath, select_index=None):
        """Re-draws the list cards from the sequence list and updates the current active filename."""
        # Update File Label
        if filepath:
            name = filepath.split("/")[-1].split("\\")[-1]
            self.lbl_active_file.configure(text=f"Active File: {name}", text_color=theme.ACCENT_CYBER)
        else:
            self.lbl_active_file.configure(text="Active File: None", text_color=theme.TEXT_MUTED)

        # Clear previous rows
        for cells in self.row_widgets:
            cells["frame"].destroy()
        self.row_widgets.clear()
        self.widget_to_idx.clear()

        # Update select_index if passed, otherwise preserve valid current selections
        if select_index is not None:
            if isinstance(select_index, list):
                self.selected_indices = set(select_index)
            else:
                self.selected_indices = {select_index}
            if select_index:
                if isinstance(select_index, list):
                    self.last_clicked_idx = select_index[0]
                else:
                    self.last_clicked_idx = select_index
        else:
            # Preserve current selection, filtering out any indices that are now out of bounds (e.g. after list clear)
            self.selected_indices = {idx for idx in self.selected_indices if 0 <= idx < len(sequence)}
            if self.last_clicked_idx is not None and (self.last_clicked_idx < 0 or self.last_clicked_idx >= len(sequence)):
                self.last_clicked_idx = None if not self.selected_indices else list(self.selected_indices)[0]

        # Re-build each row
        for idx, step in enumerate(sequence):
            is_selected = idx in self.selected_indices
            
            # Instantiate clean modular subclass widget
            row_card = TimelineRowCard(
                self.scroll_frame, idx, step, self.col_widths,
                self.on_row_click, self.on_row_drag_motion, self.on_row_drag_drop,
                is_selected
            )
            row_card.pack(fill="x", pady=2, ipady=4)
            
            self.row_widgets.append({
                "frame": row_card,
                "id": row_card.lbl_id,
                "type": row_card.lbl_type,
                "pos": row_card.lbl_pos,
                "param": row_card.lbl_param
            })
            
            # Map widgets to index for drag-and-drop containing lookup
            self.widget_to_idx[row_card] = idx
            self.widget_to_idx[row_card.lbl_id] = idx
            self.widget_to_idx[row_card.lbl_type] = idx
            self.widget_to_idx[row_card.lbl_pos] = idx
            self.widget_to_idx[row_card.lbl_param] = idx

    def on_row_click(self, idx, event):
        self._drag_start_idx = idx
        
        # Support multi-selection modes
        if event.state & 0x0004:  # Ctrl key pressed
            if idx in self.selected_indices:
                self.selected_indices.remove(idx)
            else:
                self.selected_indices.add(idx)
            self.last_clicked_idx = idx
        elif event.state & 0x0001:  # Shift key pressed
            if self.last_clicked_idx is not None:
                start = min(self.last_clicked_idx, idx)
                end = max(self.last_clicked_idx, idx)
                self.selected_indices.clear()
                for i in range(start, end + 1):
                    self.selected_indices.add(i)
            else:
                self.selected_indices.add(idx)
                self.last_clicked_idx = idx
        else:  # Regular single click
            self.selected_indices = {idx}
            self.last_clicked_idx = idx
            
        self.redraw_selection_states()
        
        # Trigger the select event callback
        if self._select_cb:
            self._select_cb(event)

    def on_row_drag_motion(self, idx, event):
        self.scroll_frame.configure(cursor="hand2")
        
        if self._drag_start_idx is not None:
            # 1. Create the floating proxy card if it does not exist yet
            if not self.drag_proxy:
                # Dim/ghost the original row in the list to indicate it is "detached"
                orig_cells = self.row_widgets[idx]
                orig_cells["frame"].configure(
                    fg_color=theme.BG_MAIN,
                    border_color=theme.BORDER_COLOR
                )
                
                # Build the floating proxy container overlay parented to self (SequenceTimelinePanel)
                # Pass width and height strictly to constructor to avoid CustomTkinter place ValueError
                self.drag_proxy = ctk.CTkFrame(
                    self,
                    fg_color=theme.ACCENT_CYBER,
                    width=self.winfo_width() - 40,
                    height=36,
                    corner_radius=4,
                    border_width=1,
                    border_color=theme.TEXT_PRIMARY
                )
                self.drag_proxy.place(x=20, y=0)
                
                # Clone labels inside the proxy card (using dark theme contrast text color)
                lbl_type = ctk.CTkLabel(
                    self.drag_proxy,
                    text=orig_cells["type"].cget("text"),
                    font=theme.FONT_BOLD,
                    text_color=theme.BG_MAIN
                )
                lbl_type.pack(side="left", padx=15)
                
                lbl_pos = ctk.CTkLabel(
                    self.drag_proxy,
                    text=orig_cells["pos"].cget("text"),
                    font=theme.FONT_MONO,
                    text_color=theme.BG_MAIN
                )
                lbl_pos.pack(side="left", fill="x", expand=True, padx=10)
                
            # 2. Update position of the proxy card based on screen DPI scaling relative to panel
            scaling = ctk.ScalingTracker.get_window_scaling(self)
            relative_y_physical = event.y_root - self.winfo_rooty()
            relative_y_logical = relative_y_physical / scaling
            
            # Position centered vertically on the mouse pointer inside Column 2
            self.drag_proxy.place(x=20, y=relative_y_logical - 18)
            # Lift the proxy to the top of the timeline's widget Z-stack overlay
            self.drag_proxy.lift()

            # 3. Dynamic insertion highlight feedback: locate current hover target index
            hover_idx = None
            for i, cells in enumerate(self.row_widgets):
                row_frame = cells["frame"]
                if not row_frame.winfo_exists():
                    continue
                ry = row_frame.winfo_rooty()
                rh = row_frame.winfo_height()
                if ry <= event.y_root <= ry + rh:
                    hover_idx = i
                    break
            
            # If hover index changed, update styling of the rows in real-time
            if not hasattr(self, "_current_hover_idx") or self._current_hover_idx != hover_idx:
                self._current_hover_idx = hover_idx
                self.redraw_selection_states()
                if hover_idx is not None and hover_idx != self._drag_start_idx:
                    # Highlight target row with cyber-cyan border and filled header background
                    self.row_widgets[hover_idx]["frame"].configure(
                        border_color=theme.ACCENT_CYBER,
                        fg_color=theme.BG_HEADER
                    )

    def on_row_drag_drop(self, event):
        self.scroll_frame.configure(cursor="")
        
        # Reset hover index tracking
        self._current_hover_idx = None
        
        # Check if a drag was actually initiated (proxy overlay existed)
        was_dragging = (self.drag_proxy is not None)
        
        # Clean up and destroy the floating drag-and-drop proxy card overlay
        if self.drag_proxy:
            self.drag_proxy.destroy()
            self.drag_proxy = None
            
        if self._drag_start_idx is not None:
            # Check which row card frame contains the absolute screen pointer y-coordinate
            target_idx = None
            for idx, cells in enumerate(self.row_widgets):
                row_frame = cells["frame"]
                if not row_frame.winfo_exists():
                    continue
                # Retrieve absolute screen-y coordinate bounds for this specific card
                ry = row_frame.winfo_rooty()
                rh = row_frame.winfo_height()
                if ry <= event.y_root <= ry + rh:
                    target_idx = idx
                    break
            
            # If a real drag occurred and a drop target was identified, select it and move it in the model
            if was_dragging and target_idx is not None:
                self.selected_indices = {target_idx}
                self.last_clicked_idx = target_idx
                
                if target_idx != self._drag_start_idx:
                    if self._move_entry_cb:
                        self._move_entry_cb(self._drag_start_idx, target_idx)
                
                # Trigger selection callback to update controller/inspector
                if self._select_cb:
                    self._select_cb(None)
            
            # Refresh all row background and border colors
            self.redraw_selection_states()
            
        self._drag_start_idx = None

    def redraw_selection_states(self):
        """Re-draws background and border colors of each row card based on selection status."""
        for idx, cells in enumerate(self.row_widgets):
            row_frame = cells["frame"]
            is_selected = idx in self.selected_indices
            bg_color = theme.BG_HEADER if is_selected else theme.BG_INPUT
            border_color = theme.ACCENT_CYBER if is_selected else theme.BORDER_COLOR
            row_frame.configure(fg_color=bg_color, border_color=border_color)

    def on_panel_resize(self, event):
        """Called automatically when this sequence timeline panel resizes (e.g. window scaling)."""
        # CRITICAL: Only respond to resize events on the sequence panel itself (or its rendering canvas),
        widget_path = str(event.widget)
        canvas_path = str(getattr(self, "_canvas", ""))
        
        if widget_path != self._w and widget_path != canvas_path:
            return
            
        scaling = self._get_window_scaling()
        logical_W = event.width / scaling
        logical_H = event.height / scaling
        
        # Initialize default logs ratio if not set (default 0.75 ratio for timeline vs logs)
        if not hasattr(self, "logs_ratio"):
            self.logs_ratio = 0.75
            
        self.layout_vertical_panels(logical_W, logical_H)

    def layout_vertical_panels(self, W, H):
        """Precisely calculates and places vertical frames and separator using absolute pixels."""
        if not hasattr(self, "logs_ratio"):
            self.logs_ratio = 0.75
            
        # lbl_panel_header is packed with height=32, pady=(0, 6), taking exactly 38px of height
        header_h = 38
        content_h = H - header_h
        if content_h <= 100:
            return
            
        total_split_h = content_h - 6 # Subtract 6px separator height
        h0 = int(total_split_h * self.logs_ratio)
        h1 = total_split_h - h0
        
        # Position Timeline Sub Frame forcing exact logical width and height
        self.timeline_sub_frame.configure(width=W, height=h0)
        self.timeline_sub_frame.place(x=0, y=header_h)
        
        # Position separator forcing exact logical width and height
        self.logs_sep.configure(width=W, height=6)
        self.logs_sep.place(x=0, y=header_h + h0)
        self.logs_sep.lift() # Raise separator to the top of the Z-order stack
        
        # Position System Logs Frame forcing exact logical width and height
        self.logs_sub_frame.configure(width=W, height=h1)
        self.logs_sub_frame.place(x=0, y=header_h + h0 + 6)

    def on_sep_press(self, event):
        """Initializes drag-state tracking on separator click."""
        self._drag_start_y = event.y_root
        self._drag_start_ratio = self.logs_ratio
        self._drag_frame_h = self.winfo_height()

    def on_sep_motion(self, event):
        """Recalculates logs pane ratio in real-time based on pointer movement."""
        if getattr(self, "_drag_start_y", None) is None:
            return
            
        dy = event.y_root - self._drag_start_y
        H_physical = self.winfo_height()
        if H_physical <= 100:
            return
            
        scaling = self.winfo_toplevel()._get_window_scaling()
        H_logical = H_physical / scaling
        header_h = 38
        content_h = H_logical - header_h
        
        if content_h <= 100:
            return
            
        # Delta movement in terms of ratio (physical dy / physical content height)
        dr = dy / (H_physical - (header_h * scaling) - 6)
        
        # Enforce robust minimum heights: 150px for timeline (top) and 100px for logs (bottom)
        min_ratio = 150 / content_h
        max_ratio = (content_h - 100) / content_h
        
        new_ratio = self._drag_start_ratio + dr
        new_ratio = max(min_ratio, min(max_ratio, new_ratio))
        
        self.logs_ratio = new_ratio
        
        W_logical = self.winfo_width() / scaling
        self.layout_vertical_panels(W_logical, H_logical)

    def on_sep_release(self, event):
        """Ends active separator dragging operations."""
        self._drag_start_y = None
