import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, Label
from PIL import Image, ImageTk
import sys
import os
import threading
import math
import time

# Ensure we can import ImageData from the data directory
sys.path.append(os.path.join(os.path.dirname(__file__), 'data'))
import ImageData

class Redirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, string):
        try:
            self.text_widget.insert(tk.END, string)
            self.text_widget.see(tk.END)
            self.text_widget.update_idletasks()
        except Exception:
            pass

    def flush(self):
        pass

class GuiRunController:
    def __init__(self):
        self.paused = threading.Event()
        self.cancelled = threading.Event()
        self.paused.clear() # Not paused initially
        self.cancelled.clear()

    def pause(self):
        self.paused.set()

    def resume(self):
        self.paused.clear()

    def cancel(self):
        self.cancelled.set()

    def is_paused(self):
        return self.paused.is_set()

    def check(self):
        if self.cancelled.is_set():
            raise ImageData.ProcessingCancelled("User cancelled processing")
        
        while self.paused.is_set():
            if self.cancelled.is_set():
               raise ImageData.ProcessingCancelled("User cancelled processing")
            time.sleep(0.1)

class DuplicateFinderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Duplicate Image Finder")
        self.root.geometry("800x650") # Increased width for 3 columns
        
        self.is_processing = False
        self.animation_step = 0
        self.animation_id = None
        self.controller = None

        # Top Frame for controls
        control_frame = tk.Frame(root)
        control_frame.pack(pady=10, padx=10, fill=tk.X)

        # Folder List
        tk.Label(control_frame, text="Selected Folders:").pack(anchor=tk.W)
        self.folder_list = tk.Listbox(control_frame, height=6)
        self.folder_list.pack(fill=tk.X, pady=5)

        # Buttons for folders
        btn_frame = tk.Frame(control_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        tk.Button(btn_frame, text="Add Folder", command=self.add_folder).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Remove Selected", command=self.remove_folder).pack(side=tk.LEFT, padx=5)

        # Extension Input
        ext_frame = tk.Frame(control_frame)
        ext_frame.pack(fill=tk.X, pady=10)
        tk.Label(ext_frame, text="File Extension:").pack(side=tk.LEFT)
        self.ext_entry = tk.Entry(ext_frame, width=10)
        self.ext_entry.insert(0, "jpg")
        self.ext_entry.pack(side=tk.LEFT, padx=5)

        # Process Button
        self.process_btn = tk.Button(control_frame, text="Find Duplicates", command=self.start_processing_thread, bg="#dddddd")
        self.process_btn.pack(pady=5)

        # Control Buttons
        ctrl_frame = tk.Frame(control_frame)
        ctrl_frame.pack(pady=2)
        
        self.pause_btn = tk.Button(ctrl_frame, text="Pause", command=self.toggle_pause, state=tk.DISABLED)
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        
        self.cancel_btn = tk.Button(ctrl_frame, text="Cancel", command=self.cancel_processing, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.LEFT, padx=5)

        # Progress Info
        self.progress_label = tk.Label(control_frame, text="Ready", font=("Arial", 10))
        self.progress_label.pack(pady=2)

        # Animation Canvas
        self.canvas = tk.Canvas(control_frame, width=200, height=100, bg="#101010")
        self.canvas.pack(pady=10, fill=tk.X)

        # Results Pane (Split View)
        self.paned_window = tk.PanedWindow(root, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Left Panel: Groups List
        left_frame = tk.Frame(self.paned_window)
        tk.Label(left_frame, text="Duplicate Groups:").pack(anchor=tk.W)
        
        self.groups_list = tk.Listbox(left_frame, width=40)
        self.groups_list.pack(fill=tk.BOTH, expand=True)
        self.groups_list.bind('<<ListboxSelect>>', self.on_group_select)
        self.paned_window.add(left_frame)

        # Middle Panel: Details
        right_frame = tk.Frame(self.paned_window)
        tk.Label(right_frame, text="Details:").pack(anchor=tk.W)
        
        self.details_text = scrolledtext.ScrolledText(right_frame, width=40, height=10)
        self.details_text.pack(fill=tk.BOTH, expand=True)
        self.paned_window.add(right_frame)

        # Right Panel: Preview
        preview_frame = tk.Frame(self.paned_window)
        tk.Label(preview_frame, text="Preview:").pack(anchor=tk.W)
        self.preview_label = tk.Label(preview_frame, text="No Preview", bg="#202020")
        self.preview_label.pack(fill=tk.BOTH, expand=True)
        self.paned_window.add(preview_frame)

        # Output Log (Hidden or minimized, or just used for log messages)
        # For now, let's keep a small log area at the bottom for status messages
        self.log_area = scrolledtext.ScrolledText(root, height=5)
        self.log_area.pack(padx=10, pady=(0, 10), fill=tk.X)

        self.redirector = Redirector(self.log_area)
        
        # Store results
        self.duplicates_data = {} # Map Index -> (ImageData, [paths])

    def add_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            # Check if already added
            if folder not in self.folder_list.get(0, tk.END):
                self.folder_list.insert(tk.END, folder)

    def remove_folder(self):
        selection = self.folder_list.curselection()
        if selection:
            self.folder_list.delete(selection[0])

    def toggle_pause(self):
        if not self.controller: return
        
        if self.controller.is_paused():
            self.controller.resume()
            self.pause_btn.config(text="Pause")
            self.progress_label.config(text="Resuming...")
        else:
            self.controller.pause()
            self.pause_btn.config(text="Resume")
            self.progress_label.config(text="Paused")

    def cancel_processing(self):
        if self.controller:
            self.controller.cancel()
            self.progress_label.config(text="Cancelling...")
            self.cancel_btn.config(state=tk.DISABLED)
            self.pause_btn.config(state=tk.DISABLED)

    def start_processing_thread(self):
        folders = self.folder_list.get(0, tk.END)
        if not folders:
            messagebox.showwarning("Warning", "Please add at least one folder.")
            return
        
        ext = self.ext_entry.get().strip()
        if not ext:
            messagebox.showwarning("Warning", "Please specify a file extension.")
            return
        
        # Clear UI
        self.groups_list.delete(0, tk.END)
        self.details_text.delete(1.0, tk.END)
        self.log_area.delete(1.0, tk.END)
        self.duplicates_data = {}
        self.preview_label.config(image="", text="No Preview")

        # Reset Controller
        self.controller = GuiRunController()
        
        self.process_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.NORMAL, text="Pause")
        self.cancel_btn.config(state=tk.NORMAL)
        
        self.is_processing = True
        self.progress_label.config(text="Starting...")
        
        # Start Animation
        self.animate()

        # Start Thread
        thread = threading.Thread(target=self.process, args=(list(folders), ext))
        thread.daemon = True
        thread.start()

    def on_group_select(self, event):
        selection = self.groups_list.curselection()
        if not selection:
            return
        
        index = selection[0]
        if index in self.duplicates_data:
            img_data, paths = self.duplicates_data[index]
            
            # Show details
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(tk.END, f"Filename: {img_data.filename}\n")
            self.details_text.insert(tk.END, f"Size: {img_data.size} bytes\n")
            self.details_text.insert(tk.END, f"Date: {img_data.date}\n")
            exif_str = str(img_data.exif_date) if img_data.exif_date else "No EXIF"
            self.details_text.insert(tk.END, f"EXIF Date: {exif_str}\n")
            self.details_text.insert(tk.END, "-"*40 + "\n")
            self.details_text.insert(tk.END, f"Count: {len(paths)}\n")
            self.details_text.insert(tk.END, "Paths:\n")
            for p in paths:
                self.details_text.insert(tk.END, f"  {p}\n")
            
            # Show Preview (First image)
            if paths:
                first_path = list(paths)[0]
                self.show_preview(first_path)

    def show_preview(self, path):
        try:
            pil_image = Image.open(path)
            
            # Resize
            max_size = (300, 300)
            pil_image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Convert to ImageTk
            self.tk_image = ImageTk.PhotoImage(pil_image)
            self.preview_label.config(image=self.tk_image, text="")
        except Exception as e:
            self.preview_label.config(image="", text="Preview Failed")
            print(f"Preview error: {e}")

    def update_progress(self, current, total):
        if total > 0:
            percentage = (current / total) * 100
            self.root.after(0, lambda: self.progress_label.config(text=f"Processed: {current}/{total} ({percentage:.1f}%)"))

    def animate(self):
        if not self.is_processing:
            return
            
        if self.controller and self.controller.is_paused():
             self.animation_id = self.root.after(100, self.animate)
             return
            
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        if w < 10: w = 200
        h = 100
        
        self.animation_step += 0.05
        
        # Hallucinating Effect: Morphing blobs that fill the screen
        # We create a mesh of colored polygons that shift over time
        
        cols = 8
        rows = 4
        cell_w = w / cols
        cell_h = h / rows
        
        # Color palette: Psychedelic
        palette = ["#FF00FF", "#00FFFF", "#FFFF00", "#FF0000", "#0000FF", "#00FF00"]
        
        for r in range(rows):
            for c in range(cols):
                # Calculate diverse phase shifts for each cell
                cx = (c + 0.5) * cell_w
                cy = (r + 0.5) * cell_h
                
                # Warping logic
                dx = math.sin(self.animation_step + c*0.5 + r*0.3) * (cell_w * 0.8)
                dy = math.cos(self.animation_step * 1.2 + c*0.3 + r*0.5) * (cell_h * 0.8)
                
                # Size oscillation
                size = (cell_w + cell_h) * 0.4 * (1.2 + 0.5 * math.sin(self.animation_step * 2 + r*c))
                
                # Dynamic Color Selection
                col_idx = int(self.animation_step * 2 + c + r) % len(palette)
                color = palette[col_idx]
                
                # Draw shifting ovals/blobs that overlap significantly to cover background
                x1 = cx + dx - size
                y1 = cy + dy - size
                x2 = cx + dx + size
                y2 = cy + dy + size
                
                self.canvas.create_oval(x1, y1, x2, y2, fill=color, outline="", stipple="gray50") # Stipple adds a bit of texture/blending

        self.animation_id = self.root.after(50, self.animate)

    def process(self, folders, ext):
        print("Starting processing...")
        
        # Redirect stdout
        old_stdout = sys.stdout
        sys.stdout = self.redirector

        try:
            # Call the logic with callback and controller
            # Now using find_duplicates to get data back
            uniques, duplicates = ImageData.find_duplicates(folders, ext, progress_callback=self.update_progress, controller=self.controller)
            print("\nProcessing complete.")
            print(f"Found {len(uniques)} unique files.")
            print(f"Found {len(duplicates)} duplicate groups.")
            
            # Populate GUI on main thread
            self.root.after(0, lambda: self.populate_results(duplicates))
            
        except ImageData.ProcessingCancelled:
            print("\n[!] Processing Cancelled by User.")
        except Exception as e:
            print(f"\nError: {e}")
        finally:
            # Restore stdout
            sys.stdout = old_stdout
            
            # Reset UI state (must be done on main thread ideally, but typically ok in simple tk)
            self.is_processing = False
            self.root.after(0, lambda: self.process_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.pause_btn.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.cancel_btn.config(state=tk.DISABLED))
            if self.controller and self.controller.cancelled.is_set():
                 self.root.after(0, lambda: self.progress_label.config(text="Cancelled."))
            else:
                 self.root.after(0, lambda: self.progress_label.config(text="Done."))

    def populate_results(self, duplicates_dict):
        self.groups_list.delete(0, tk.END)
        self.duplicates_data = {}
        
        idx = 0
        for img_data, paths in duplicates_dict.items():
            label = f"{img_data.filename} ({len(paths)} copies)"
            self.groups_list.insert(tk.END, label)
            self.duplicates_data[idx] = (img_data, paths)
            idx += 1

if __name__ == "__main__":
    root = tk.Tk()
    app = DuplicateFinderGUI(root)
    root.mainloop()
