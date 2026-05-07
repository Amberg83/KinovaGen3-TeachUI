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

# Emoji specific fonts for cross-system display compatibility
FONT_EMOJI = ("Segoe UI Emoji", 10) if os.name == "nt" else ("Arial", 10, "bold")
FONT_EMOJI_LARGE = ("Segoe UI Emoji", 12) if os.name == "nt" else ("Arial", 12, "bold")



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

def make_flat_button(parent, text, bg_color, fg_color=TEXT_PRIMARY, font_style=FONT_BOLD, hover_bg=None, **kwargs):
    """Factory helper to build consistent flat, hover-active Tkinter buttons."""
    btn = tk.Button(parent, text=text, bg=bg_color, fg=fg_color, font=font_style, 
                    relief="flat", bd=0, activebackground=hover_bg or bg_color, 
                    activeforeground=fg_color, cursor="hand2", **kwargs)
    
    if hover_bg:
        btn.bind("<Enter>", lambda e: btn.config(bg=hover_bg))
        btn.bind("<Leave>", lambda e: btn.config(bg=bg_color))
        
    return btn

def apply_entry_theme(entry):
    """Applies clean, modern borders and text padding to an entry widget."""
    entry.config(bg=BG_INPUT, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                 relief="flat", bd=1, highlightbackground=BORDER_COLOR,
                 highlightcolor=ACCENT_CYBER, highlightthickness=1)
