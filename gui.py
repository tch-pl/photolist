import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
import sys
import os
import threading
import math
import time

# Ensure we can import ImageData from the data directory
sys.path.append(os.path.join(os.path.dirname(__file__), 'data'))
import ImageData

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
        self.root.geometry("600x650")
        
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
        self.canvas.pack(pady=10)

        # Output Text Area
        tk.Label(root, text="Output:").pack(anchor=tk.W, padx=10)
        self.output_area = scrolledtext.ScrolledText(root, height=15)
        self.output_area.pack(padx=10, pady=(0, 10), fill=tk.BOTH, expand=True)

        # Redirect stdout to text widget
        class Redirector:
            def __init__(self, text_widget):
                self.text_widget = text_widget

            def write(self, string):
                self.text_widget.insert(tk.END, string)
                self.text_widget.see(tk.END)
                self.text_widget.update_idletasks() # Force update UI

            def flush(self):
                pass

        self.redirector = Redirector(self.output_area)

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

    def update_progress(self, current, total):
        if total > 0:
            percentage = (current / total) * 100
            self.root.after(0, lambda: self.progress_label.config(text=f"Processed: {current}/{total} ({percentage:.1f}%)"))

    def animate(self):
        if not self.is_processing:
            return
            
        # If paused, just skip drawing but keep loop alive (or could stop/start)
        if self.controller and self.controller.is_paused():
             self.animation_id = self.root.after(100, self.animate)
             return
            
        self.canvas.delete("all")
        w, h = 200, 100
        cx, cy = w/2, h/2
        self.animation_step += 0.1
        
        # Draw "Wild" Fractal-ish geometric pattern
        # Concentric rotating triangles and circles
        for i in range(5):
            angle_offset = self.animation_step + (i * math.pi / 2.5)
            scale = 30 + (i * 10)
            
            # Rotating Triangle
            p1 = (cx + scale * math.cos(angle_offset), cy + scale * math.sin(angle_offset))
            p2 = (cx + scale * math.cos(angle_offset + 2*math.pi/3), cy + scale * math.sin(angle_offset + 2*math.pi/3))
            p3 = (cx + scale * math.cos(angle_offset + 4*math.pi/3), cy + scale * math.sin(angle_offset + 4*math.pi/3))
            
            colors = ["#ff0055", "#00ff55", "#5500ff", "#ffff00", "#00ffff"]
            color = colors[i % len(colors)]
            
            self.canvas.create_polygon(p1, p2, p3, outline=color, width=2, fill="")
            
            # Ornament circles
            rad = 3 + i
            ox = cx + (scale * 0.5) * math.cos(-angle_offset * 1.5)
            oy = cy + (scale * 0.5) * math.sin(-angle_offset * 1.5)
            self.canvas.create_oval(ox-rad, oy-rad, ox+rad, oy+rad, fill=color)

        self.animation_id = self.root.after(30, self.animate)

    def process(self, folders, ext):
        # Clear previous output
        self.output_area.delete(1.0, tk.END)
        print("Starting processing...")
        
        # Redirect stdout
        old_stdout = sys.stdout
        sys.stdout = self.redirector

        try:
            # Call the logic with callback and controller
            ImageData.main(folders, ext, progress_callback=self.update_progress, controller=self.controller)
            print("\nProcessing complete.")
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

if __name__ == "__main__":
    root = tk.Tk()
    app = DuplicateFinderGUI(root)
    root.mainloop()
