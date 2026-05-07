import tkinter as tk
from tkinter import ttk
import os

# --- DESIGN SYSTEM COLOR PALETTE (Premium Dark/Cyber Mode) ---
BG_MAIN = "#121214"         # Deep Slate Charcoal (MainWindow background)
BG_CARD = "#1c1c1e"         # Slightly lighter slate (Panels/Cards background)
BG_INPUT = "#252529"        # Dark entry box background
BG_HEADER = "#18181b"       # Top connection header background

TEXT_PRIMARY = "#f4f4f5"     # Crisp Off-White
TEXT_MUTED = "#a1a1aa"       # Muted Zinc Gray
BORDER_COLOR = "#2d2d30"     # Thin flat boundaries

ACCENT_CYBER = "#0ea5e9"     # Cyber Teal/Sky Blue (Primary brand accent)
ACCENT_CYBER_HOVER = "#0284c7"
ACCENT_GREEN = "#10b981"     # Connected Mint Green
ACCENT_RED = "#ef4444"       # Stop Coral/Cherry Red
ACCENT_ORANGE = "#f59e0b"    # Active Warning Gold
ACCENT_YELLOW = "#facc15"    # Active Warning Gold

# --- FONTS ---
FONT_TITLE = (("Segoe UI", "DejaVu Sans", "Helvetica", "Arial"), 11, "bold")
FONT_NORMAL = (("Segoe UI", "DejaVu Sans", "Helvetica", "Arial"), 10, "normal")
FONT_BOLD = (("Segoe UI", "DejaVu Sans", "Helvetica", "Arial"), 10, "bold")
FONT_MONO = (("Consolas", "DejaVu Sans Mono", "Courier New", "monospace"), 11, "normal")
FONT_MONO_SMALL = (("Consolas", "DejaVu Sans Mono", "Courier New", "monospace"), 9, "normal")

# Emoji specific fonts with fallback chain for beautiful cross-system display (Windows, Linux, macOS)
FONT_EMOJI = (("Segoe UI Emoji", "Noto Color Emoji", "Apple Color Emoji", "DejaVu Sans", "Arial"), 10)
FONT_EMOJI_LARGE = (("Segoe UI Emoji", "Noto Color Emoji", "Apple Color Emoji", "DejaVu Sans", "Arial"), 12)

# --- IMAGE / ICON CACHE MANAGER ---
_icon_cache = {}

def get_icon(name, tint=None):
    """Retrieves a cached PhotoImage by its asset filename, optionally tinting it on the fly."""
    cache_key = (name, tint)
    if cache_key not in _icon_cache:
        base_key = (name, None)
        if base_key not in _icon_cache:
            assets_dir = os.path.join(os.path.dirname(__file__), "assets")
            path = os.path.join(assets_dir, f"{name}.png")
            if os.path.exists(path):
                try:
                    _icon_cache[base_key] = tk.PhotoImage(file=path)
                except Exception as e:
                    print(f"Error loading icon '{name}': {e}")
                    _icon_cache[base_key] = ""
            else:
                print(f"Icon asset path does not exist: {path}")
                _icon_cache[base_key] = ""
                
        base_img = _icon_cache[base_key]
        if base_img == "":
            _icon_cache[cache_key] = ""
        elif tint is None:
            # Attach custom properties to the base image
            if hasattr(base_img, "width"):
                base_img._icon_name = name
                base_img._icon_tint = None
            _icon_cache[cache_key] = base_img
        else:
            try:
                # Create a tinted copy of the base image!
                tinted_img = base_img.copy()
                w = tinted_img.width()
                h = tinted_img.height()
                for y in range(h):
                    for x in range(w):
                        if not tinted_img.transparency_get(x, y):
                            tinted_img.put(tint, to=(x, y))
                # Attach custom properties to the tinted image
                tinted_img._icon_name = name
                tinted_img._icon_tint = tint
                _icon_cache[cache_key] = tinted_img
            except Exception as e:
                print(f"Error tinting icon '{name}' to '{tint}': {e}")
                _icon_cache[cache_key] = base_img # Fallback to original white icon
                
    return _icon_cache[cache_key]



def configure_flat_styles():
    """Sets up flat, modern styling across all TTK widgets."""
    style = ttk.Style()
    style.theme_use('clam')

    # --- Parent PanedWindow styling ---
    style.configure("TPanedwindow", background=BG_MAIN)
    style.configure("Panedwindow", background=BG_MAIN, sashwidth=4, sashpad=2)

    # --- Labelframe Styling ---
    style.configure("TLabelframe", background=BG_CARD, bordercolor=BORDER_COLOR, borderwidth=1, relief="solid")
    style.configure("TLabelframe.Label", font=FONT_TITLE, foreground=TEXT_PRIMARY, background=BG_CARD)

    # --- Notebook (Tab control) Styling ---
    style.configure("TNotebook", background=BG_CARD, borderwidth=0, padding=0)
    style.configure("TNotebook.Tab", 
                    font=FONT_BOLD, 
                    padding=[12, 6], 
                    background=BG_INPUT, 
                    foreground=TEXT_MUTED, 
                    lightcolor="transparent", 
                    darkcolor="transparent", 
                    bordercolor=BORDER_COLOR,
                    borderwidth=1)
    
    style.map("TNotebook.Tab", 
              background=[("selected", BG_CARD), ("active", BG_CARD)],
              foreground=[("selected", ACCENT_CYBER), ("active", TEXT_PRIMARY)],
              focuscolor=[("selected", "transparent")])

    # --- Combobox Styling ---
    style.configure("TCombobox", 
                    arrowcolor=TEXT_PRIMARY, 
                    background=BG_INPUT, 
                    fieldbackground=BG_INPUT, 
                    foreground=TEXT_PRIMARY, 
                    bordercolor=BORDER_COLOR, 
                    lightcolor=BORDER_COLOR, 
                    darkcolor=BORDER_COLOR,
                    borderwidth=1,
                    font=FONT_NORMAL)
    
    style.map("TCombobox", 
              fieldbackground=[("readonly", BG_INPUT)],
              background=[("readonly", BG_INPUT)],
              foreground=[("readonly", TEXT_PRIMARY)])

    # --- Treeview (Waypoint list table) Styling ---
    style.configure("Treeview", 
                    background=BG_CARD, 
                    fieldbackground=BG_CARD, 
                    foreground=TEXT_PRIMARY, 
                    rowheight=32, 
                    font=FONT_NORMAL, 
                    borderwidth=0,
                    gridlines="none")
    
    style.configure("Treeview.Heading", 
                    background=BG_INPUT, 
                    foreground=TEXT_MUTED, 
                    font=FONT_BOLD, 
                    relief="flat", 
                    borderwidth=1, 
                    bordercolor=BORDER_COLOR)
    
    style.map("Treeview", 
              background=[("selected", BG_INPUT)],
              foreground=[("selected", ACCENT_CYBER)])

    # --- Scrollbar styling ---
    style.configure("Vertical.TScrollbar", 
                    gripcount=0, 
                    background=BG_INPUT, 
                    troughcolor=BG_CARD, 
                    bordercolor=BG_CARD, 
                    lightcolor=BG_CARD, 
                    darkcolor=BG_CARD, 
                    arrowcolor=TEXT_MUTED,
                    arrowsize=10,
                    width=10)
    
    style.map("Vertical.TScrollbar", 
              background=[("active", BORDER_COLOR)])

class FlatButton(tk.Button):
    """Custom button class to bypass Tkinter's legacy, buggy disabled image rendering."""
    def __init__(self, master, text, bg_color, fg_color, font_style, hover_bg, **kwargs):
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.hover_bg = hover_bg
        self._custom_state = "normal"
        
        # Track original icon parameters for stateful grey tint adjustments
        self._icon_name = None
        self._icon_tint = None
        self._original_image = kwargs.get("image")
        if self._original_image and hasattr(self._original_image, "_icon_name"):
            self._icon_name = self._original_image._icon_name
            self._icon_tint = getattr(self._original_image, "_icon_tint", None)
            
        # Pull command from kwargs if present
        self._command = kwargs.get("command")
        if "command" in kwargs:
            kwargs["command"] = self._on_click
            
        super().__init__(master, text=text, bg=bg_color, fg=fg_color, font=font_style, 
                         relief="flat", bd=0, activebackground=hover_bg or bg_color, 
                         activeforeground=fg_color, cursor="hand2", **kwargs)
        
        if self.hover_bg:
            self.bind("<Enter>", self._on_enter)
            self.bind("<Leave>", self._on_leave)
            
    def _on_enter(self, e):
        if self._custom_state == "normal" and self.hover_bg:
            super().configure(bg=self.hover_bg)
            
    def _on_leave(self, e):
        if self._custom_state == "normal":
            super().configure(bg=self.bg_color)
            
    def _on_click(self):
        if self._custom_state == "normal" and self._command:
            self._command()
            
    def configure(self, cnf=None, **kw):
        if cnf is None:
            cnf = {}
        cnf = {**cnf, **kw}
        
        if "command" in cnf:
            self._command = cnf["command"]
            cnf["command"] = self._on_click
            
        if "image" in cnf:
            new_img = cnf["image"]
            self._original_image = new_img
            if new_img and hasattr(new_img, "_icon_name"):
                self._icon_name = new_img._icon_name
                self._icon_tint = getattr(new_img, "_icon_tint", None)
            else:
                self._icon_name = None
                self._icon_tint = None
                
        if "state" in cnf:
            state_val = cnf["state"]
            if state_val in ("disabled", tk.DISABLED):
                self._custom_state = "disabled"
                # Use standard dark input background and zinc text gray for disabled states
                super().configure(bg=BG_INPUT, fg=TEXT_MUTED, cursor="arrow")
                if self._icon_name:
                    # Switch icon to grey-tinted version to match disabled text color perfectly!
                    super().configure(image=get_icon(self._icon_name, tint=TEXT_MUTED))
                cnf["state"] = "normal"  # Force native Tk state to remain "normal" to prevent ugly image halo!
            elif state_val in ("normal", tk.NORMAL):
                self._custom_state = "normal"
                super().configure(bg=self.bg_color, fg=self.fg_color, cursor="hand2")
                if self._icon_name:
                    # Restore original active/tinted icon
                    super().configure(image=self._original_image)
                cnf["state"] = "normal"
                
        return super().configure(**cnf)
        
    config = configure

def make_flat_button(parent, text, bg_color, fg_color=TEXT_PRIMARY, font_style=FONT_BOLD, hover_bg=None, **kwargs):
    """Factory helper to build consistent flat, hover-active Tkinter buttons."""
    # Ensure default generous padding if not provided to secure high y-axis readability
    if "pady" not in kwargs:
        kwargs["pady"] = 6
    if "padx" not in kwargs:
        kwargs["padx"] = 12
        
    # Prevent the 1-pixel height trap when using image-compounded buttons
    if "image" in kwargs and kwargs.get("height") == 1:
        del kwargs["height"]

    return FlatButton(parent, text=text, bg_color=bg_color, fg_color=fg_color, 
                      font_style=font_style, hover_bg=hover_bg, **kwargs)

def apply_entry_theme(entry):
    """Applies clean, modern borders and text padding to an entry widget."""
    entry.config(bg=BG_INPUT, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                 relief="flat", bd=1, highlightbackground=BORDER_COLOR,
                 highlightcolor=ACCENT_CYBER, highlightthickness=1)
