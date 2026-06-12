import tkinter as tk
import customtkinter as ctk
import os
from PIL import Image, ImageTk, ImageOps, ImageDraw

class ReferentDisplayWindow(ctk.CTkToplevel):
    """
    A minimal, secondary window designed for beamers and big screens.
    Displays the active study referent on top of a scaled and cropped background image.
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Study Referent Display")
        self.geometry("900x650")
        
        # Override standard delete protocol to hide the window instead of destroying it
        self.protocol("WM_DELETE_WINDOW", self.hide_window)
        
        # Initialize state variables
        self.counter_text = ""
        self.instructions_text = ""
        self._resize_after_id = None
        
        # Load background image
        assets_dir = os.path.join(os.path.dirname(__file__), "assets")
        self.bg_image_path = os.path.join(assets_dir, "HomeBackground.png")
        try:
            if os.path.exists(self.bg_image_path):
                self.bg_image_original = Image.open(self.bg_image_path)
            else:
                print(f"Warning: Background image not found at {self.bg_image_path}")
                self.bg_image_original = None
        except Exception as e:
            print(f"Error loading background image: {e}")
            self.bg_image_original = None
            
        # Canvas holds the background image and centered text elements
        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # Bind resize event to debounced handler
        self.bind("<Configure>", self._on_resize)
        
    def update_task(self, name, instructions, counter_text):
        """Updates the referent display with new details and brings it to front."""
        self.deiconify()  # Ensure window is visible
        self.lift()       # Bring to front
        
        self.counter_text = counter_text
        self.instructions_text = instructions
        
        # Cancel any pending resize timer and update immediately
        if self._resize_after_id:
            self.after_cancel(self._resize_after_id)
            self._resize_after_id = None
            
        self._update_display()

    def show_completed(self):
        """Displays completion screen."""
        self.deiconify()
        self.lift()
        self.counter_text = ""
        self.instructions_text = (
            "Study Tasks Completed!\n\n"
            "All study tasks have been completed successfully.\n\n"
            "Thank you for participating!"
        )
        
        if self._resize_after_id:
            self.after_cancel(self._resize_after_id)
            self._resize_after_id = None
            
        self._update_display()

    def show_window(self):
        """Shows and focuses the window."""
        self.deiconify()
        self.lift()
        self.focus()

    def hide_window(self):
        """Hides the window from view instead of destroying it."""
        # Cancel pending timers when hiding
        if self._resize_after_id:
            self.after_cancel(self._resize_after_id)
            self._resize_after_id = None
        self.withdraw()
        
    def _on_resize(self, event):
        """Debounces configure event to prevent lag during drag resizing."""
        # Only respond to configure event of the window itself
        if event.widget != self:
            return
            
        if self._resize_after_id:
            self.after_cancel(self._resize_after_id)
            
        self._resize_after_id = self.after(20, self._update_display)
        
    def _update_display(self):
        self._resize_after_id = None
        
        # Wait for window updates to get real geometry
        self.update_idletasks()
        win_w = self.winfo_width()
        win_h = self.winfo_height()
        
        if win_w <= 1 or win_h <= 1:
            return
            
        self.canvas.delete("all")
        
        scaling = self._get_window_scaling()
        
        # Calculate fonts scaled to DPI
        font_counter = ("Arial", int(28 * scaling), "bold")
        font_desc = ("Arial", int(36 * scaling), "normal")
        
        # Wrapped width in physical pixels for Canvas text drawing
        physical_wrap_w = max(300 * scaling, win_w - 200 * scaling)
        
        # Draw temporary text to measure dimensions
        counter_id = self.canvas.create_text(
            win_w / 2, 0, text=self.counter_text,
            font=font_counter, fill="#555555",
            justify="center", anchor="center", width=physical_wrap_w
        )
        
        desc_id = self.canvas.create_text(
            win_w / 2, 0, text=self.instructions_text,
            font=font_desc, fill="#000000",
            justify="center", anchor="center", width=physical_wrap_w
        )
        
        # Get bounding boxes
        bbox_counter = self.canvas.bbox(counter_id) if self.counter_text else None
        bbox_desc = self.canvas.bbox(desc_id) if self.instructions_text else None
        
        h_counter = bbox_counter[3] - bbox_counter[1] if bbox_counter else 0
        h_desc = bbox_desc[3] - bbox_desc[1] if bbox_desc else 0
        
        gap = 25 * scaling if (self.counter_text and self.instructions_text) else 0
        total_h = h_counter + gap + h_desc
        
        # Centered Y coordinates
        top_y = (win_h - total_h) / 2
        
        # Draw/reposition elements and delete placeholders if empty
        if self.counter_text:
            y_counter = top_y + h_counter / 2
            self.canvas.coords(counter_id, win_w / 2, y_counter)
        else:
            self.canvas.delete(counter_id)
            counter_id = None
            
        if self.instructions_text:
            y_desc = top_y + h_counter + gap + h_desc / 2
            self.canvas.coords(desc_id, win_w / 2, y_desc)
        else:
            self.canvas.delete(desc_id)
            desc_id = None
            
        # Re-measure final bounding boxes for drawing the readability card
        bbox_counter = self.canvas.bbox(counter_id) if (counter_id and self.counter_text) else None
        bbox_desc = self.canvas.bbox(desc_id) if (desc_id and self.instructions_text) else None
        
        lefts = []
        rights = []
        tops = []
        bottoms = []
        
        if bbox_counter:
            lefts.append(bbox_counter[0])
            rights.append(bbox_counter[2])
            tops.append(bbox_counter[1])
            bottoms.append(bbox_counter[3])
        if bbox_desc:
            lefts.append(bbox_desc[0])
            rights.append(bbox_desc[2])
            tops.append(bbox_desc[1])
            bottoms.append(bbox_desc[3])
            
        if lefts:
            pad_x = 60 * scaling
            pad_y = 45 * scaling
            
            box_left = max(20 * scaling, min(lefts) - pad_x)
            box_right = min(win_w - 20 * scaling, max(rights) + pad_x)
            box_top = max(20 * scaling, min(tops) - pad_y)
            box_bottom = min(win_h - 20 * scaling, max(bottoms) + pad_y)
        else:
            box_left, box_top, box_right, box_bottom = 0, 0, 0, 0
            
        # Draw background and composite elements
        if self.bg_image_original:
            try:
                resample_filter = Image.Resampling.BILINEAR
            except AttributeError:
                resample_filter = Image.BILINEAR
                
            # Resize and crop image using PIL's ImageOps.fit to fill (win_w, win_h)
            resized_img = ImageOps.fit(self.bg_image_original, (win_w, win_h), method=resample_filter)
            
            if lefts:
                # Create an overlay layer with alpha channel
                overlay = Image.new('RGBA', (win_w, win_h), (0, 0, 0, 0))
                draw = ImageDraw.Draw(overlay)
                
                # Draw rounded rectangle readability card with alpha 220
                draw.rounded_rectangle(
                    [box_left, box_top, box_right, box_bottom],
                    radius=16 * scaling,
                    fill=(255, 255, 255, 220)
                )
                
                # Composite the card overlay onto the background image
                final_img = Image.alpha_composite(resized_img.convert('RGBA'), overlay)
            else:
                final_img = resized_img
                
            # Keep photo image reference to prevent garbage collection
            self.bg_image_tk = ImageTk.PhotoImage(final_img)
            bg_id = self.canvas.create_image(0, 0, anchor="nw", image=self.bg_image_tk)
            self.canvas.tag_lower(bg_id)
        elif lefts:
            # Fallback solid white card if background image is missing
            rect_id = self.canvas.create_rectangle(
                box_left, box_top, box_right, box_bottom,
                fill="#F9F9F9", outline="#E2E8F0", width=2 * scaling
            )
            self.canvas.tag_lower(rect_id)
