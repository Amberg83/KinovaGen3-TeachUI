import tkinter as tk
import customtkinter as ctk
from view import theme

class ToolTip:
    """Sleek Cyber-Dark Hover Tooltip with modern font, border accents, and mathematically perfect centering."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.delay_job = None
        
        # Bind hover events
        self.widget.bind("<Enter>", self.on_enter, add="+")
        self.widget.bind("<Leave>", self.on_leave, add="+")

    def on_enter(self, event=None):
        """Initializes hover timer to prevent annoying flashing on fast mouse sweeps."""
        if self.delay_job:
            self.widget.after_cancel(self.delay_job)
        self.delay_job = self.widget.after(350, self.show_tooltip)

    def on_leave(self, event=None):
        """Cancels hover timer and closes tooltip instantly."""
        if self.delay_job:
            self.widget.after_cancel(self.delay_job)
            self.delay_job = None
        self.hide_tooltip()

    def show_tooltip(self):
        """Draws, aligns, and fades in a premium styled tooltip beneath the active host widget."""
        if self.tooltip_window:
            return
            
        wx = self.widget.winfo_rootx()
        wy = self.widget.winfo_rooty()
        ww = self.widget.winfo_width()
        wh = self.widget.winfo_height()
        
        # Create lightweight borderless container initially hidden
        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_withdraw()
        tw.wm_overrideredirect(True)
        tw.configure(bg=theme.BG_MAIN)
        
        # Premium cyber card container with subtle accent border
        container = ctk.CTkFrame(
            tw, fg_color=theme.BG_CARD, 
            border_width=1, border_color=theme.ACCENT_CYBER, 
            corner_radius=4
        )
        container.pack(fill="both", expand=True)
        
        lbl = ctk.CTkLabel(
            container, text=self.text, 
            font=theme.FONT_NORMAL,
            text_color=theme.TEXT_PRIMARY,
            padx=10, pady=5
        )
        lbl.pack()
        
        # Force layout to compute actual dimensions
        tw.update_idletasks()
        tw_w = tw.winfo_reqwidth()
        tw_h = tw.winfo_reqheight()
        
        # Calculate coordinate space to center tooltip horizontally below the button
        x = wx + (ww // 2) - (tw_w // 2)
        y = wy + wh + 6 # 6px gap below button
        
        # Prevent clipping off the left/right screen borders
        screen_w = tw.winfo_screenwidth()
        if x < 10:
            x = 10
        elif x + tw_w > screen_w - 10:
            x = screen_w - tw_w - 10
            
        tw.wm_geometry(f"+{int(x)}+{int(y)}")
        tw.wm_deiconify()

    def hide_tooltip(self):
        """Destroys active tooltip window."""
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None
