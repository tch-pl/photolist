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
import data.ImageData as ImageData
from data.storage import ScanResultStorage

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
        self.loaded_from_storage = False

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
        self.process_btn.pack(pady=5, side=tk.LEFT, padx=5)

        self.report_btn = tk.Button(control_frame, text="Generate Report", command=self.start_report_thread, bg="#dddddd")
        self.report_btn.pack(pady=5, side=tk.LEFT, padx=5)

        # Storage Buttons
        #antigravity add file path choice for this button
        self.save_btn = tk.Button(control_frame, text="Save Results", command=self.save_results_to_storage, bg="#dddddd")
        self.save_btn.pack(pady=5, side=tk.LEFT, padx=5)
        
        self.load_btn = tk.Button(control_frame, text="Load Results", command=self.load_results_from_storage, bg="#dddddd")
        self.load_btn.pack(pady=5, side=tk.LEFT, padx=5)

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
        
        # Storage Status
        self.storage_status_label = tk.Label(control_frame, text="", font=("Arial", 9), fg="#666666")
        self.storage_status_label.pack(pady=2)

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
        
        # Auto-load previous results on startup
        self.auto_load_on_startup()

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
        # anyigravity process more than one folder in a multiple threads
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
    
    def format_size(self, size_bytes):
        """Format byte size to human-readable format."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if abs(size_bytes) < 1024.0:
                return f"{size_bytes:3.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"

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

    #antigravity method should be processing just one folder, to process more than one folder call this method for each folder separately
    # move GUI handling outside
    # populate asynchronous GUI on main thread
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
            
            # Calculate distinct file size
            distinct_size, total_files, distinct_files = ImageData.calculate_distinct_size(uniques, duplicates)
            print(f"\nTotal files scanned: {total_files}")
            print(f"Distinct files (unique content): {distinct_files}")
            print(f"Distinct files total size: {self.format_size(distinct_size)}")
            
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

    def start_report_thread(self):
        folders = self.folder_list.get(0, tk.END)
        if not folders:
            messagebox.showwarning("Warning", "Please add at least one folder.")
            return
        
        ext = self.ext_entry.get().strip()
        
        # UI Prep
        self.report_btn.config(state=tk.DISABLED)
        self.process_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.NORMAL, text="Pause")
        self.cancel_btn.config(state=tk.NORMAL)
        self.is_processing = True
        self.progress_label.config(text="Generating Report...")
        
        self.controller = GuiRunController()
        self.animate()
        
        thread = threading.Thread(target=self.run_report, args=(list(folders), ext))
        thread.daemon = True
        thread.start()

    def run_report(self, folders, ext):
        # Redirect stdout
        old_stdout = sys.stdout
        sys.stdout = self.redirector
        
        try:
             report = ImageData.analyze_dataset(folders, ext, progress_callback=self.update_progress, controller=self.controller)
             self.root.after(0, lambda: self.show_report_window(report))
        except ImageData.ProcessingCancelled:
             print("\nReport Cancelled.")
        except Exception as e:
             print(f"\nReport Error: {e}")
        finally:
            sys.stdout = old_stdout
            self.is_processing = False
            self.root.after(0, lambda: self.report_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.process_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.pause_btn.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.cancel_btn.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.progress_label.config(text="Report Ready." if not self.controller.cancelled.is_set() else "Cancelled."))

    def show_report_window(self, report):
        top = tk.Toplevel(self.root)
        top.title("Dataset Analysis Report")
        top.geometry("600x500")
        
        txt = scrolledtext.ScrolledText(top, width=70, height=25)
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Format Report
        lines = []
        lines.append("=== DATASET ANALYSIS REPORT ===")
        lines.append(f"Total Files Found: {report['total_files']}")
        lines.append(f"Distinct Content Items: {report['distinct_items']}")
        
        def sizeof_fmt(num):
            for unit in ["B", "KB", "MB", "GB", "TB"]:
                if abs(num) < 1024.0:
                    return f"{num:3.1f} {unit}"
                num /= 1024.0
            return f"{num:.1f} PB"

        lines.append(f"Total Size on Disk: {sizeof_fmt(report['total_size'])}")
        lines.append(f"Unique Content Size: {sizeof_fmt(report['unique_size'])}")
        
        savings = report['total_size'] - report['unique_size']
        lines.append(f"Potential Savings: {sizeof_fmt(savings)}")
        lines.append("-" * 40)
        
        lines.append(f"\n=== FILENAME CLASHES ({len(report['clashes'])}) ===")
        if not report['clashes']:
            lines.append("No clashes found. All filenames represent unique content.")
        else:
            for fname, versions in report['clashes'].items():
                lines.append(f"\nFilename: '{fname}' used for {len(versions)} different contents:")
                for img in versions:
                    exif = str(img.exif_date) if img.exif_date else "No EXIF"
                    lines.append(f"  - Size: {img.size} bytes | Date: {img.date} | {exif}")

        txt.insert(tk.END, "\n".join(lines))
        txt.config(state=tk.DISABLED) # Read only

    def populate_results(self, duplicates_dict):
        self.groups_list.delete(0, tk.END)
        self.duplicates_data = {}
        
        idx = 0
        for img_data, paths in duplicates_dict.items():
            label = f"{img_data.filename} ({len(paths)} copies)"
            self.groups_list.insert(tk.END, label)
            self.duplicates_data[idx] = (img_data, paths)
            idx += 1
    
    def save_results_to_storage(self):
        """Save current scan results to storage."""
        if not self.duplicates_data:
            messagebox.showinfo("Info", "No results to save. Please run a scan first.")
            return
        
        try:
            # Convert duplicates_data back to the format expected by storage
            duplicates = {}
            for idx, (img_data, paths) in self.duplicates_data.items():
                duplicates[img_data] = paths
            
            # For now, we don't track uniques in the GUI, so pass empty list
            # In a full implementation, you might want to store uniques too
            success = ScanResultStorage.save_results([], duplicates)
            
            if success:
                self.storage_status_label.config(text="✓ Results saved to storage", fg="#00AA00")
                messagebox.showinfo("Success", "Scan results saved successfully!")
            else:
                self.storage_status_label.config(text="✗ Failed to save results", fg="#AA0000")
                messagebox.showerror("Error", "Failed to save results to storage.")
        except Exception as e:
            self.storage_status_label.config(text="✗ Save error", fg="#AA0000")
            messagebox.showerror("Error", f"Error saving results: {e}")
    
    def load_results_from_storage(self):
        """Load scan results from storage."""
        if not ScanResultStorage.storage_exists():
            messagebox.showinfo("Info", "No saved results found.")
            return
        
        try:
            uniques, duplicates = ScanResultStorage.load_results()
            
            if not duplicates:
                messagebox.showinfo("Info", "No duplicate results found in storage.")
                self.storage_status_label.config(text="Storage empty", fg="#666666")
                return
            
            # Clear current results
            self.groups_list.delete(0, tk.END)
            self.details_text.delete(1.0, tk.END)
            self.log_area.delete(1.0, tk.END)
            self.preview_label.config(image="", text="No Preview")
            
            # Populate with loaded data
            self.populate_results(duplicates)
            self.loaded_from_storage = True
            
            self.storage_status_label.config(text=f"✓ Loaded {len(duplicates)} duplicate groups from storage", fg="#0066CC")
            self.log_area.insert(tk.END, f"Loaded {len(duplicates)} duplicate groups from storage.\n")
            messagebox.showinfo("Success", f"Loaded {len(duplicates)} duplicate groups from storage.")
            
        except Exception as e:
            self.storage_status_label.config(text="✗ Load error", fg="#AA0000")
            messagebox.showerror("Error", f"Error loading results: {e}")
    
    def auto_load_on_startup(self):
        """Automatically load previous results on application startup."""
        if ScanResultStorage.storage_exists():
            try:
                uniques, duplicates = ScanResultStorage.load_results()
                
                if duplicates:
                    self.populate_results(duplicates)
                    self.loaded_from_storage = True
                    self.storage_status_label.config(text=f"✓ Auto-loaded {len(duplicates)} groups from previous scan", fg="#0066CC")
                    self.log_area.insert(tk.END, f"Auto-loaded {len(duplicates)} duplicate groups from previous scan.\n")
            except Exception as e:
                print(f"Failed to auto-load results: {e}")
                self.storage_status_label.config(text="Previous results could not be loaded", fg="#AA6600")

if __name__ == "__main__":
    root = tk.Tk()
    app = DuplicateFinderGUI(root)
    root.mainloop()
