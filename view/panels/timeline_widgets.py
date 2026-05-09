import tkinter as tk
import customtkinter as ctk
from view import theme
from view.widgets import ToolTip

class TimelineRowCard(ctk.CTkFrame):
    """Encapsulates the rendering, themes, and mouse event bindings for a single timeline row."""
    def __init__(self, parent, idx, step, col_widths, click_cb, drag_motion_cb, drag_drop_cb, is_selected):
        bg_color = theme.BG_HEADER if is_selected else theme.BG_INPUT
        border_color = theme.ACCENT_CYBER if is_selected else theme.BORDER_COLOR
        
        super().__init__(
            parent, fg_color=bg_color, height=36, corner_radius=4,
            border_width=1, border_color=border_color
        )
        self.idx = idx
        self.step = step
        self.col_widths = col_widths
        
        self.setup_ui()
        self.bind_events(click_cb, drag_motion_cb, drag_drop_cb)

    def setup_ui(self):
        type_str = self.step.get("type", "action").upper()
        dur = self.step.get('duration_s', 3.0)
        
        if type_str == "PAUSE":
            pos_str = "--- (WAITING) ---"
            param_str = f"Wait: {dur}s"
        else:
            pos_str = [f"{v:.1f}" for v in self.step["pos"]]
            param_str = f"Duration: {dur}s"
        
        # Labels (sized to current adjustable column widths)
        self.lbl_id = ctk.CTkLabel(self, text=str(self.idx), width=self.col_widths[0], font=theme.FONT_MONO)
        self.lbl_id.pack(side="left")
        
        self.lbl_type = ctk.CTkLabel(self, text=type_str, width=self.col_widths[1], font=theme.FONT_BOLD, text_color=theme.ACCENT_CYBER)
        self.lbl_type.pack(side="left")
        
        self.lbl_pos = ctk.CTkLabel(self, text=str(pos_str), width=self.col_widths[2], font=theme.FONT_MONO)
        self.lbl_pos.pack(side="left")
        
        self.lbl_param = ctk.CTkLabel(self, text=param_str, font=theme.FONT_NORMAL, anchor="w")
        self.lbl_param.pack(side="left", fill="x", expand=True, padx=(10, 0))

    def bind_events(self, click_cb, drag_motion_cb, drag_drop_cb):
        widgets_to_bind = [self, self.lbl_id, self.lbl_type, self.lbl_pos, self.lbl_param]
        for w in widgets_to_bind:
            w.bind("<ButtonPress-1>", lambda e, i=self.idx: click_cb(i, e))
            w.bind("<B1-Motion>", lambda e, i=self.idx: drag_motion_cb(i, e))
            w.bind("<ButtonRelease-1>", drag_drop_cb)


class SystemLogsConsole(ctk.CTkFrame):
    """Encapsulates the system text logger console, tag configuration, and auto-scroll behaviors."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        
        self.textbox = ctk.CTkTextbox(
            self, state='disabled', font=theme.FONT_MONO,
            fg_color="#09090b", text_color=theme.TEXT_PRIMARY,
            border_width=0, corner_radius=0
        )
        self.textbox.pack(fill="both", expand=True)
        
        self.textbox.tag_config('DEBUG', foreground='#818cf8')
        self.textbox.tag_config('INFO', foreground='#94a3b8')
        self.textbox.tag_config('WARNING', foreground=theme.ACCENT_YELLOW)
        self.textbox.tag_config('ERROR', foreground=theme.ACCENT_RED)
        self.textbox.tag_config('CRITICAL', foreground='#ffffff', background='#991b1b')


class MediaPlaybackToolbar(ctk.CTkFrame):
    """Encapsulates the horizontal control panel at the bottom (Play, Play Selection, Pause, Stop, E-Stop buttons)."""
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent, fg_color=theme.BG_HEADER, corner_radius=4,
            border_width=1, border_color=theme.BORDER_COLOR, **kwargs
        )
        self.setup_ui()

    def setup_ui(self):
        self.btn_replay = theme.make_flat_button(
            self, text=" Full Replay", image=theme.get_icon("play", tint=theme.BG_MAIN), compound="left",
            bg_color=theme.ACCENT_GREEN, fg_color=theme.BG_MAIN, hover_bg="#059669", 
            font_style=theme.FONT_BOLD, padx=15, height=44
        )
        self.btn_replay.pack(side="left", padx=3, pady=6)
        ToolTip(self.btn_replay, "Replay Entire Sequence (F5)")
        
        self.btn_replay_sel = theme.make_flat_button(
            self, text=" Selection", image=theme.get_icon("play_selection"), compound="left",
            bg_color=theme.BG_INPUT, fg_color=theme.TEXT_PRIMARY, hover_bg=theme.BORDER_COLOR, 
            font_style=theme.FONT_BOLD, padx=15, height=44
        )
        self.btn_replay_sel.pack(side="left", padx=3, pady=6)
        ToolTip(self.btn_replay_sel, "Replay Selected Timeline Items (F6)")
        
        # Helper to build playback media control flat toggles (image-based 1:1 squares)
        def make_media_btn(parent, icon_name, hover_text):
            img = theme.get_icon(icon_name)
            btn = theme.make_flat_button(
                parent, text="", image=img, bg_color=theme.BG_INPUT, 
                fg_color=theme.TEXT_PRIMARY, hover_bg=theme.BORDER_COLOR, 
                width=44, height=44, padx=0, pady=0
            )
            ToolTip(btn, hover_text)
            return btn

        self.btn_pause_media = make_media_btn(self, "pause", "Pause Active Replay (F7)")
        self.btn_pause_media.pack(side="left", padx=3, pady=6)
        
        self.btn_stop_media = make_media_btn(self, "stop", "Stop Playback and Release Robot Locks (F8)")
        self.btn_stop_media.pack(side="left", padx=3, pady=6)
        
        self.btn_estop = theme.make_flat_button(
            self, text=" E-STOP", image=theme.get_icon("estop"), compound="left",
            bg_color=theme.ACCENT_RED, fg_color=theme.TEXT_PRIMARY, hover_bg="#b91c1c", 
            font_style=theme.FONT_BOLD, padx=15, height=44
        )
        self.btn_estop.pack(side="right", fill="x", expand=True, padx=(15, 3), pady=6)
        ToolTip(self.btn_estop, "EMERGENCY STOP (Escape)")
