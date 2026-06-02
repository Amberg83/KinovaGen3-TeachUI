import tkinter as tk
import customtkinter as ctk

class ReferentDisplayWindow(ctk.CTkToplevel):
    """
    A minimal, high-contrast secondary window designed for beamers and big screens.
    Displays the active study referent with large black text on a pure white background.
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Study Referent Display")
        self.geometry("900x650")
        
        # Force pure white background
        self.configure(fg_color="#FFFFFF")
        
        # Override standard delete protocol to hide the window instead of destroying it
        self.protocol("WM_DELETE_WINDOW", self.hide_window)
        
        # Primary container for margins and alignment
        self.container = ctk.CTkFrame(self, fg_color="#FFFFFF", corner_radius=0)
        self.container.pack(fill="both", expand=True, padx=50, pady=50)
        
        # Center-aligned inner block for vertical & horizontal centering
        self.inner_block = ctk.CTkFrame(self.container, fg_color="#FFFFFF", corner_radius=0)
        self.inner_block.pack(anchor="center", expand=True)
        
        # Header/Task Counter (e.g., "Task 1 of 4")
        self.lbl_task_counter = tk.Label(
            self.inner_block, text="", bg="#FFFFFF", fg="#555555",
            font=("Arial", 28, "bold"), justify="center", anchor="center"
        )
        self.lbl_task_counter.pack(fill="x", pady=(0, 25), anchor="center")
        
        # Task Instructions (Large, wrapping)
        self.lbl_task_desc = tk.Label(
            self.inner_block, text="", bg="#FFFFFF", fg="#000000",
            font=("Arial", 36, "normal"), justify="center", anchor="center"
        )
        self.lbl_task_desc.pack(fill="x", anchor="center")
        
        # Bind resize event to dynamically adjust wraplength
        self.bind("<Configure>", self._on_resize)
        
    def update_task(self, name, instructions, current_idx, total_count):
        """Updates the referent display with new details and brings it to front."""
        self.deiconify()  # Ensure window is visible
        self.lift()       # Bring to front
        
        self.lbl_task_counter.configure(text=f"Task {current_idx} of {total_count}")
        self.lbl_task_desc.configure(text=instructions)
        self._update_wraplength()

    def show_completed(self):
        """Displays completion screen."""
        self.deiconify()
        self.lift()
        self.lbl_task_counter.configure(text="")
        self.lbl_task_desc.configure(
            text="Study Tasks Completed!\n\nAll study tasks have been completed successfully.\n\nThank you for participating!"
        )
        self._update_wraplength()

    def show_window(self):
        """Shows and focuses the window."""
        self.deiconify()
        self.lift()
        self.focus()

    def hide_window(self):
        """Hides the window from view instead of destroying it."""
        self.withdraw()
        
    def _on_resize(self, event):
        """Debounces and adjusts wraplength dynamically so text never overflows the window."""
        self._update_wraplength()
        
    def _update_wraplength(self):
        # Subtract margins and padding from actual width
        scaling = self._get_window_scaling()
        logical_width = self.winfo_width() / scaling
        wrap_w = max(300, int(logical_width - 120))
        
        self.lbl_task_desc.configure(wraplength=wrap_w)
        self.lbl_task_counter.configure(wraplength=wrap_w)
