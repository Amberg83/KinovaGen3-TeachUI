import tkinter as tk
from tkinter import ttk
import os
import customtkinter as ctk
from PIL import Image
import warnings

# Suppress CustomTkinter warning since we handle vector SVG scaling manually in get_icon
warnings.filterwarnings("ignore", category=UserWarning, message=".*Given image is not CTkImage.*")

# Initialize customtkinter default dark styles
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

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

def _get_best_font_family(fallbacks):
    """Returns the first font family from fallbacks that is available on the system."""
    import tkinter.font as tkfont
    try:
        available = [f.lower() for f in tkfont.families()]
        for f in fallbacks:
            if f.lower() in available:
                return f
    except Exception:
        pass
    return fallbacks[0] if fallbacks else "Arial"

# Create TTK-compatible single-family font definitions to avoid falling back to microscopic font sizes
best_font_family = _get_best_font_family(FONT_NORMAL[0])
TTK_FONT_NORMAL = (best_font_family, 10, "normal")
TTK_FONT_BOLD = (best_font_family, 10, "bold")

import tksvg

# --- IMAGE / ICON CACHE MANAGER ---
_icon_cache = {}
current_scaling = 1.0

def get_icon(name, tint=None, size=(24, 24)):
    """Retrieves a cached tksvg.SvgImage by its asset filename, optionally tinting it by modifying XML data."""
    # Ensure name is clean and lacks extensions
    name_base = name.replace(".png", "").replace(".svg", "")
    tint_color = tint or TEXT_PRIMARY
    
    cache_key = (name_base, tint_color, size)
    if cache_key not in _icon_cache:
        assets_dir = os.path.join(os.path.dirname(__file__), "assets")
        path = os.path.join(assets_dir, f"{name_base}.svg")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    svg_xml = f.read()
                
                # Apply dynamic tinting by injecting fill attribute in root <svg> tag
                svg_xml = svg_xml.replace("<svg ", f'<svg fill="{tint_color}" ')
                
                # Calculate physical pixel size for DPI scaling
                scaled_w = int(size[0] * current_scaling)
                scaled_h = int(size[1] * current_scaling)
                
                # Dynamically resize the SVG canvas to scaled width and height in the XML markup
                import re
                svg_xml = re.sub(r'width="\d+"', f'width="{scaled_w}"', svg_xml)
                svg_xml = re.sub(r'height="\d+"', f'height="{scaled_h}"', svg_xml)
                
                svg_img = tksvg.SvgImage(data=svg_xml)
                
                # Attach original icon metadata for FlatButton state updates
                svg_img._icon_name = name_base
                svg_img._icon_tint = tint
                
                _icon_cache[cache_key] = svg_img
            except Exception as e:
                print(f"Error loading/tinting SVG icon '{name_base}': {e}")
                _icon_cache[cache_key] = ""
        else:
            print(f"Icon asset path does not exist: {path}")
            _icon_cache[cache_key] = ""
            
    return _icon_cache[cache_key]


def clear_icon_cache():
    """Safely clears cached Tkinter SvgImage instances while preventing Tcl deallocator exceptions."""
    try:
        _icon_cache.clear()
    except Exception:
        pass

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
                    font=TTK_FONT_NORMAL)
    
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
                    font=TTK_FONT_NORMAL, 
                    borderwidth=0,
                    gridlines="none")
    
    style.configure("Treeview.Heading", 
                    background=BG_INPUT, 
                    foreground=TEXT_MUTED, 
                    font=TTK_FONT_BOLD, 
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
                    arrowsize=12,
                    width=14)
    
    style.map("Vertical.TScrollbar", 
              background=[("active", BORDER_COLOR)])


class FlatButton(ctk.CTkButton):
    """Modernized button class that wraps CustomTkinter's CTKButton for round-cornered animated style."""
    def __init__(self, master, text, bg_color, fg_color, font_style, hover_bg, **kwargs):
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.hover_bg = hover_bg
        self._custom_state = "normal"
        
        # Track original icon parameters for disabled states
        self._icon_name = None
        self._icon_tint = None
        self._original_image = kwargs.get("image")
        if self._original_image and hasattr(self._original_image, "_icon_name"):
            self._icon_name = self._original_image._icon_name
            self._icon_tint = getattr(self._original_image, "_icon_tint", None)
            
        # Clean up standard Tkinter properties that CTKButton does not accept or handles differently
        kwargs.pop("relief", None)
        kwargs.pop("bd", None)
        kwargs.pop("activebackground", None)
        kwargs.pop("activeforeground", None)
        kwargs.pop("cursor", None)
        kwargs.pop("padx", None)
        kwargs.pop("pady", None)
        
        # TK default widths for text-only buttons (like width=14) are character counts!
        # If an image is present, the dimensions are already in pixels!
        has_image = bool(self._original_image)
        if "width" in kwargs and not has_image:
            w = kwargs["width"]
            if w < 50:
                kwargs["width"] = w * 10
                
        if "height" in kwargs and not has_image:
            h = kwargs["height"]
            if h < 10:
                kwargs["height"] = h * 24

        # Custom-tailor corner radius: crisp rounded square (4) for tool icons, standard (6) for text buttons
        corner_radius = kwargs.pop("corner_radius", 4 if text == "" else 6)

        # Initialize CTKButton
        super().__init__(
            master, 
            text=text, 
            fg_color=bg_color, 
            text_color=fg_color, 
            font=font_style, 
            hover_color=hover_bg or bg_color,
            corner_radius=corner_radius,
            **kwargs
        )
        
    def configure(self, cnf=None, **kw):
        if cnf is None:
            cnf = {}
        cnf = {**cnf, **kw}
        
        # Normalize tk properties to customtkinter
        if "bg" in cnf:
            cnf["fg_color"] = cnf.pop("bg")
        if "fg" in cnf:
            cnf["text_color"] = cnf.pop("fg")
        if "bg_color" in cnf:
            cnf["fg_color"] = cnf.pop("bg_color")
            
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
                cnf["state"] = "disabled"
                if self._icon_name:
                    cnf["image"] = get_icon(self._icon_name, tint=TEXT_MUTED)
            elif state_val in ("normal", tk.NORMAL):
                self._custom_state = "normal"
                cnf["state"] = "normal"
                if self._icon_name:
                    cnf["image"] = get_icon(self._icon_name, tint=self._icon_tint)
                    
        # Remove any standard tk keys that CTK doesn't like inside configure()
        for key in ["activebackground", "activeforeground", "relief", "bd", "cursor", "padx", "pady", "compound"]:
            cnf.pop(key, None)
            
        # Standard width/height mapping from tk characters to CTK pixels
        has_image = bool(cnf.get("image") or self._original_image)
        if "width" in cnf and not has_image:
            w = cnf["width"]
            if w < 50:
                cnf["width"] = w * 10
        if "height" in cnf and not has_image:
            h = cnf["height"]
            if h < 10:
                cnf["height"] = h * 24
                
        return super().configure(**cnf)
        
    config = configure


def make_flat_button(parent, text, bg_color, fg_color=TEXT_PRIMARY, font_style=FONT_BOLD, hover_bg=None, **kwargs):
    """Factory helper to build consistent flat, hover-active CustomTkinter buttons."""
    # Ensure default padding parameters are stripped for CTKButton compatibility
    kwargs.pop("padx", None)
    kwargs.pop("pady", None)
    
    # Prevent the 1-pixel height trap when using image-compounded buttons
    if "image" in kwargs and kwargs.get("height") == 1:
        del kwargs["height"]

    return FlatButton(parent, text=text, bg_color=bg_color, fg_color=fg_color, 
                      font_style=font_style, hover_bg=hover_bg, **kwargs)


def apply_entry_theme(entry):
    """Applies clean, modern borders and text padding to an entry widget (handles both tk and CTK)."""
    if hasattr(entry, "configure") and not isinstance(entry, ctk.CTkEntry):
        try:
            entry.configure(bg=BG_INPUT, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                            relief="flat", bd=1, highlightbackground=BORDER_COLOR,
                            highlightcolor=ACCENT_CYBER, highlightthickness=1)
        except Exception:
            pass


class SectionFrame(ctk.CTkFrame):
    """
    A titled CTkFrame that replaces tk.LabelFrame throughout the UI.
    The title appears as a small CTkLabel at the top of the frame.
    Children should be added to `self.content` (a nested frame)
    to prevent mixing pack/grid geometry managers inside the main SectionFrame container.
    """
    def __init__(self, parent, text: str = "", font=None,
                 fg_color: str = BG_CARD, text_color: str = TEXT_MUTED, **kwargs):
        # Strip tk-only constructor kwargs that CTkFrame does not accept
        for k in ("bg", "fg", "relief", "bd", "padx", "pady",
                  "highlightbackground", "highlightthickness"):
            kwargs.pop(k, None)
        super().__init__(parent, fg_color=fg_color,
                         border_color=BORDER_COLOR, border_width=1,
                         corner_radius=4, **kwargs)
        if text:
            _font = font if font is not None else FONT_BOLD
            ctk.CTkLabel(
                self, text=f" {text} ",
                font=_font, fg_color=fg_color,
                text_color=text_color, anchor="w"
            ).pack(anchor="w", padx=6, pady=(4, 0))
            
        self.content = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.content.pack(fill="both", expand=True, padx=4, pady=4)


def make_label(parent, text: str = "", font=None,
               fg_color: str = "transparent",
               text_color: str = TEXT_PRIMARY, **kwargs) -> ctk.CTkLabel:
    """
    Convenience factory: creates a ctk.CTkLabel with common theme defaults.
    Accepts legacy tk.Label kwargs (bg/fg) and silently translates them.
    """
    if "bg" in kwargs:
        fg_color = kwargs.pop("bg")
    if "fg" in kwargs:
        text_color = kwargs.pop("fg")
    for k in ("relief", "bd", "highlightbackground", "highlightthickness", "anchor"):
        kwargs.pop(k, None)
    _font = font if font is not None else FONT_NORMAL
    return ctk.CTkLabel(parent, text=text, font=_font,
                        fg_color=fg_color, text_color=text_color, **kwargs)


def update_treeview_font_scaling(scaling):
    """Updates the TTK Treeview style font size dynamically based on the DPI scaling ratio."""
    global current_scaling
    current_scaling = scaling
    style = ttk.Style()
    
    # Intuitively scale the standard font sizes according to system DPI multiplier
    # Start with a comfortable base size of 11 (instead of 10) for pristine clarity on High-DPI screens
    normal_size = int(11 * scaling)
    bold_size = int(11 * scaling)
    row_height = int(36 * scaling)
    
    scaled_normal = (best_font_family, normal_size, "normal")
    scaled_bold = (best_font_family, bold_size, "bold")
    
    style.configure("Treeview", font=scaled_normal, rowheight=row_height)
    style.configure("Treeview.Heading", font=scaled_bold)

