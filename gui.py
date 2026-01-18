import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, Label, ttk
from PIL import Image, ImageTk
import sys
import os
import shutil
import concurrent.futures
import threading
import math
import time

# Ensure we can import ImageData from the data directory
sys.path.append(os.path.join(os.path.dirname(__file__), 'data'))
import data.ImageData as ImageData
from data.storage import ScanResultStorage
from data.TargetPathResolver import TargetPathResolver

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
        self.use_checksum = False  # Checksum mode toggle

        # Top Frame for controls
        control_frame = tk.Frame(root)
        control_frame.pack(pady=10, padx=10, fill=tk.X)

        # Folder List (Treeview)
        tk.Label(control_frame, text="Selected Folders:").pack(anchor=tk.W)
        
        # Frame for Treeview and Scrollbar
        list_frame = tk.Frame(control_frame)
        list_frame.pack(fill=tk.X, pady=5)
        
        self.folder_tree = ttk.Treeview(list_frame, columns=("Folder", "Status"), show="headings", height=6)
        self.folder_tree.heading("Folder", text="Folder Path")
        self.folder_tree.heading("Status", text="Status")
        self.folder_tree.column("Folder", width=400)
        self.folder_tree.column("Status", width=150)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.folder_tree.yview)
        self.folder_tree.configure(yscrollcommand=scrollbar.set)
        
        self.folder_tree.pack(side=tk.LEFT, fill=tk.X, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

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
        
        # Checksum Mode Toggle
        self.checksum_var = tk.BooleanVar(value=False)
        checksum_cb = tk.Checkbutton(
            ext_frame, 
            text="Use Checksum (slower, more accurate)",
            variable=self.checksum_var,
            command=self.toggle_checksum_mode
        )
        checksum_cb.pack(side=tk.LEFT, padx=15)

        # Process Button
        self.process_btn = tk.Button(control_frame, text="Find Duplicates", command=self.start_processing_thread, bg="#dddddd")
        self.process_btn.pack(pady=5, side=tk.LEFT, padx=5)

        self.report_btn = tk.Button(control_frame, text="Generate Report", command=self.start_report_thread, bg="#dddddd")
        self.report_btn.pack(pady=5, side=tk.LEFT, padx=5)

        # Storage Buttons
        self.save_btn = tk.Button(control_frame, text="Save Results", command=self.save_results_to_storage, bg="#dddddd")
        self.save_btn.pack(pady=5, side=tk.LEFT, padx=5)
        
        self.load_btn = tk.Button(control_frame, text="Load Results", command=self.load_results_from_storage, bg="#dddddd")
        self.load_btn.pack(pady=5, side=tk.LEFT, padx=5)
        
        self.copy_btn = tk.Button(control_frame, text="Copy Distinct Items", command=self.copy_distinct_items_thread, bg="#dddddd")
        self.copy_btn.pack(pady=5, side=tk.LEFT, padx=5)

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
       # self.auto_load_on_startup()

        self.loaded_uniques = []

    def add_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            # Check if already added
            existing = [self.folder_tree.item(item)['values'][0] for item in self.folder_tree.get_children()]
            if folder not in existing:
                self.folder_tree.insert("", tk.END, values=(folder, "Pending"))

    def remove_folder(self):
        selection = self.folder_tree.selection()
        if selection:
            for item in selection:
                self.folder_tree.delete(item)
    
    def toggle_checksum_mode(self):
        """Toggle checksum-based detection mode."""
        self.use_checksum = self.checksum_var.get()
        mode_str = "checksum-based" if self.use_checksum else "metadata-based"
        print(f"Detection mode: {mode_str}")

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
        folders = [self.folder_tree.item(item)['values'][0] for item in self.folder_tree.get_children()]
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
        self.loaded_uniques = []
        self.loaded_from_storage = False
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
        thread = threading.Thread(target=self.process_folders, args=(list(folders), ext))
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

    def process_single_folder(self, folder, ext):
        """
        Process a single folder for duplicates.
        Returns (uniques, duplicates) tuple.
        """
        print(f"Processing folder: {folder}")
        return ImageData.find_duplicates(
            [folder], 
            ext, 
            progress_callback=self.update_progress, 
            controller=self.controller,
            use_checksum=self.use_checksum
        )
    
    def process_folders(self, folders, ext):
        """
        Process multiple folders for duplicates in parallel.
        This method processes folders concurrently and aggregates results.
        """
        print("Starting processing...")
        
        # Redirect stdout
        old_stdout = sys.stdout
        sys.stdout = self.redirector

        try:
            all_uniques = []
            all_duplicates = {}
            
            total_folders = len(folders)
            max_workers = total_folders if total_folders > 0 else 1
            print(f"Parallelizing with {max_workers} folder worker threads.")
            
            # Initialize status in Treeview
            folder_item_map = {} # Map folder path -> tree item ID
            for item in self.folder_tree.get_children():
                folder_path = self.folder_tree.item(item)['values'][0]
                if folder_path in folders:
                    folder_item_map[folder_path] = item
                    self.folder_tree.set(item, "Status", "Waiting...")
            
            # Simple thread-safe counter for progress
            completed_count = 0
            lock = threading.Lock()
            
            def folder_task_done_callback(future):
                nonlocal completed_count
                with lock:
                    completed_count += 1
                    count = completed_count 
                self.root.after(0, lambda: self.progress_label.config(text=f"Processed folders: {count}/{total_folders}"))

            # Callback factory for per-folder progress
            def make_progress_callback(folder_path):
                tree_item = folder_item_map.get(folder_path)
                if not tree_item:
                    return None
                    
                def callback(current, total):
                    # Update Treeview in main thread
                    # We use percentage to be concise
                    status_text = f"Scanning {current}/{total}"
                    self.root.after(0, lambda: self.folder_tree.set(tree_item, "Status", status_text))
                return callback

            # Process folders in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Update status
                self.root.after(0, lambda: self.progress_label.config(text=f"Processing {total_folders} folders in parallel..."))
                
                # Submit all tasks
                future_to_folder = {}
                for folder in folders:
                    # Set initial status
                    if folder in folder_item_map:
                        self.root.after(0, lambda f=folder: self.folder_tree.set(folder_item_map[f], "Status", "Starting..."))
                    
                    future = executor.submit(
                        ImageData.find_duplicates, 
                        [folder], 
                        ext, 
                        progress_callback=make_progress_callback(folder), 
                        controller=self.controller,
                        use_checksum=self.use_checksum
                    )
                    future_to_folder[future] = folder
                
                # Check for cancellation periodically while waiting
                # We can't easily wait with timeout in a loop without blocking checking cancel
                # So we just iterate get results.
                
                for future in concurrent.futures.as_completed(future_to_folder):
                    if self.controller and self.controller.cancelled.is_set():
                        break
                        
                    folder = future_to_folder[future]
                    try:
                        folder_uniques, folder_duplicates = future.result()
                        
                        # Aggregate results (main thread safe here as we are in the orchestrator loop)
                        all_uniques.extend(folder_uniques)
                        
                        for img_data, paths in folder_duplicates.items():
                            if img_data in all_duplicates:
                                all_duplicates[img_data].update(paths)
                            else:
                                all_duplicates[img_data] = paths.copy()
                                
                        folder_task_done_callback(future)
                        if folder in folder_item_map:
                             self.root.after(0, lambda f=folder: self.folder_tree.set(folder_item_map[f], "Status", "Done"))
                        
                    except Exception as exc:
                        print(f"Folder {folder} generated an exception: {exc}")

            if self.controller and self.controller.cancelled.is_set():
                raise ImageData.ProcessingCancelled("User cancelled processing")

            # CRITICAL FIX: Re-check uniques for cross-folder duplicates
            # When processing folders in parallel, each folder's files are marked as unique WITHIN that folder
            # But files in folder A might be duplicates of files in folder B!
            # We need to check all "uniques" against each other to find cross-folder duplicates
            print(f"\nMerging results from {total_folders} folders...")
            print(f"Pre-merge: {len(all_uniques)} unique files, {len(all_duplicates)} duplicate groups")
            
            # Build a map of all images (including current duplicates)
            image_map = {}
            
            # Add existing duplicates first
            for img_data, paths in all_duplicates.items():
                image_map[img_data] = paths
            
            # Now check each "unique" against the map
            final_uniques = []
            for img_data in all_uniques:
                if img_data in image_map:
                    # This "unique" matches an existing entry - it's actually a duplicate!
                    image_map[img_data].add(img_data.path)
                else:
                    # First time seeing this image
                    image_map[img_data] = {img_data.path}
            
            # Rebuild duplicates and uniques from the merged map
            all_duplicates = {}
            final_uniques = []
            for img_data, paths in image_map.items():
                if len(paths) > 1:
                    all_duplicates[img_data] = paths
                else:
                    final_uniques.append(img_data)
            
            all_uniques = final_uniques
            
            print("\nProcessing complete.")
            print(f"Found {len(all_uniques)} unique files.")
            print(f"Found {len(all_duplicates)} duplicate groups.")
            
            # Calculate distinct file size
            distinct_size, total_files, distinct_files = ImageData.calculate_distinct_size(all_uniques, all_duplicates)
            print(f"\nTotal files scanned: {total_files}")
            print(f"Distinct files (unique content): {distinct_files}")
            print(f"Distinct files total size: {self.format_size(distinct_size)}")
            
            # Populate GUI on main thread
            # Use default argument to capture current value and avoid late binding issues
            self.root.after(0, lambda d=all_duplicates, u=all_uniques: self.populate_results(d))
            
            # Store uniques - not currently stored in duplicates_data but useful for report
            self.loaded_uniques = all_uniques
            
        except ImageData.ProcessingCancelled:
            print("\n[!] Processing Cancelled by User.")
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Restore stdout
            sys.stdout = old_stdout
            
            # Reset UI state on main thread
            self.is_processing = False
            self.root.after(0, lambda: self.process_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.pause_btn.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.cancel_btn.config(state=tk.DISABLED))
            if self.controller and self.controller.cancelled.is_set():
                 self.root.after(0, lambda: self.progress_label.config(text="Cancelled."))
            else:
                 self.root.after(0, lambda: self.progress_label.config(text="Done."))

    def start_report_thread(self):
        # Case 1: Load from storage (No re-scan needed)
        if self.loaded_from_storage and self.duplicates_data:
            self.generate_report_from_memory()
            return

        # Case 2: Process folders
        folders = [self.folder_tree.item(item)['values'][0] for item in self.folder_tree.get_children()]
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

    def generate_report_from_memory(self):
        """Generate report from loaded uniques and duplicates without re-scanning."""
        try:
            # Reconstruct report structure
            uniques = self.loaded_uniques if hasattr(self, 'loaded_uniques') else []
            duplicates = {}
            # Restore duplicate structure (duplicates_data is id -> (img, paths))
            for idx, (img, paths) in self.duplicates_data.items():
                duplicates[img] = paths
                
            # Use calculate_distinct_size to get totals
            distinct_size, total_files, distinct_files = ImageData.calculate_distinct_size(uniques, duplicates)
            
            total_size = 0
            # Sum unqiues
            for u in uniques: total_size += u.size
            # Sum duplicates
            for img, paths in duplicates.items():
                total_size += img.size * len(paths)
                
            # If loaded from partial storage (uniques missing), distinct_files might be just duplicates count
            # Use distinct_size from calculation
            
            # Find clashes (re-implement clash logic from analyze_dataset)
            clashes = {}
            # Combine all for name check
            all_content = []
            all_content.extend(uniques)
            for img in duplicates:
                all_content.append(img)
            
            filename_map = {}
            for img in all_content:
                if img.filename not in filename_map:
                    filename_map[img.filename] = []
                filename_map[img.filename].append(img)
            
            for fname, versions in filename_map.items():
                if len(versions) > 1:
                    clashes[fname] = versions
            
            report = {
                'total_files': total_files,
                'distinct_items': distinct_files,
                'total_size': total_size,
                'unique_size': distinct_size,
                'clashes': clashes
            }
            
            self.show_report_window(report)
            
        except Exception as e:
            messagebox.showerror("Report Error", f"Failed to generate report from loaded data: {e}")
            print(f"Report Generation Error: {e}")

    def run_report(self, folders, ext):
        # Redirect stdout
        old_stdout = sys.stdout
        sys.stdout = self.redirector
        
        try:
             report = ImageData.analyze_dataset(folders, ext, progress_callback=self.update_progress, controller=self.controller, use_checksum=self.use_checksum)
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
        
        if not duplicates_dict:
            # Show informative message when no duplicates found
            self.groups_list.insert(tk.END, "[No duplicate groups found]")
            self.groups_list.itemconfig(0, {'fg': '#888888'})
            return
        
        idx = 0
        for img_data, paths in duplicates_dict.items():
            label = f"{img_data.filename} ({len(paths)} copies)"
            self.groups_list.insert(tk.END, label)
            self.duplicates_data[idx] = (img_data, paths)
            idx += 1
    
    def save_results_to_storage(self):
        """Save current scan results to storage with file path selection."""
        # Check if there are any results to save (either duplicates or uniques)
        if not self.duplicates_data and not self.loaded_uniques:
            messagebox.showinfo("Info", "No results to save. Please run a scan first.")
            return
        
        # Ask user for save location
        filepath = filedialog.asksaveasfilename(
            title="Save Scan Results",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="scan_results.json"
        )
        
        # User cancelled
        if not filepath:
            return
        
        try:
            # Convert duplicates_data back to the format expected by storage
            duplicates = {}
            for idx, (img_data, paths) in self.duplicates_data.items():
                duplicates[img_data] = paths
            
            # Save both uniques and duplicates
            success = ScanResultStorage.save_results(self.loaded_uniques, duplicates, filepath)
            
            if success:
                self.storage_status_label.config(text=f"✓ Results saved to {os.path.basename(filepath)}", fg="#00AA00")
                messagebox.showinfo("Success", f"Scan results saved to:\n{filepath}")
            else:
                self.storage_status_label.config(text="✗ Failed to save results", fg="#AA0000")
                messagebox.showerror("Error", "Failed to save results to storage.")
        except Exception as e:
            self.storage_status_label.config(text="✗ Save error", fg="#AA0000")
            messagebox.showerror("Error", f"Error saving results: {e}")
    
    def load_results_from_storage(self):
        """Load scan results from storage with file path selection."""
        # Ask user for file location
        filepath = filedialog.askopenfilename(
            title="Load Scan Results",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="scan_results.json"
        )
        
        # User cancelled
        if not filepath:
            return
        
        if not os.path.exists(filepath):
            messagebox.showinfo("Info", "Selected file does not exist.")
            return
        
        try:
            uniques, duplicates = ScanResultStorage.load_results(filepath)
            
            if not duplicates:
                messagebox.showinfo("Info", "No duplicate results found in file.")
                self.storage_status_label.config(text="File empty", fg="#666666")
                return
            
            # Clear current results
            self.groups_list.delete(0, tk.END)
            self.details_text.delete(1.0, tk.END)
            self.log_area.delete(1.0, tk.END)
            self.preview_label.config(image="", text="No Preview")
            
            # Populate with loaded data
            self.populate_results(duplicates)
            self.loaded_from_storage = True
            
            # Store uniques if available
            self.loaded_uniques = uniques if uniques else []
            
            self.storage_status_label.config(text=f"✓ Loaded {len(duplicates)} groups from {os.path.basename(filepath)}", fg="#0066CC")
            self.log_area.insert(tk.END, f"Loaded {len(duplicates)} duplicate groups from {filepath}.\n")
            messagebox.showinfo("Success", f"Loaded {len(duplicates)} duplicate groups from file.")
            
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
    
    def copy_distinct_items_thread(self):
        """Start thread to copy all distinct items to target location."""
        if not self.duplicates_data and not self.loaded_uniques:
            messagebox.showwarning("Warning", "No results to copy. Please run a scan or load results first.")
            return
        
        # Show configuration dialog
        config_dialog = tk.Toplevel(self.root)
        config_dialog.title("Copy Distinct Items - Configuration")
        config_dialog.geometry("500x250")
        config_dialog.transient(self.root)
        config_dialog.grab_set()
        
        # Target directory
        tk.Label(config_dialog, text="Target Base Directory:", font=("Arial", 10, "bold")).pack(pady=(10, 5), anchor=tk.W, padx=10)
        
        dir_frame = tk.Frame(config_dialog)
        dir_frame.pack(fill=tk.X, padx=10, pady=5)
        
        target_dir_var = tk.StringVar()
        dir_entry = tk.Entry(dir_frame, textvariable=target_dir_var, state="readonly", width=50)
        dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        def browse_directory():
            folder = filedialog.askdirectory(title="Select Target Base Directory")
            if folder:
                target_dir_var.set(folder)
        
        tk.Button(dir_frame, text="Browse...", command=browse_directory).pack(side=tk.LEFT)
        
        # Path pattern
        tk.Label(config_dialog, text="Path Pattern:", font=("Arial", 10, "bold")).pack(pady=(15, 5), anchor=tk.W, padx=10)
        tk.Label(config_dialog, text="Use {year}, {month}, {day} placeholders", font=("Arial", 8), fg="#666666").pack(anchor=tk.W, padx=10)
        
        pattern_var = tk.StringVar(value="/{year}/{month}/{day}")
        pattern_entry = tk.Entry(config_dialog, textvariable=pattern_var, width=50)
        pattern_entry.pack(fill=tk.X, padx=10, pady=5)
        
        # Buttons
        btn_frame = tk.Frame(config_dialog)
        btn_frame.pack(pady=20)
        
        result_container = {"target_root": None, "pattern": None}
        
        def on_start():
            target = target_dir_var.get()
            pattern = pattern_var.get().strip()
            
            if not target:
                messagebox.showwarning("Warning", "Please select a target directory.")
                return
            
            if not pattern:
                messagebox.showwarning("Warning", "Please enter a path pattern.")
                return
            
            # Validate pattern has at least one placeholder
            if "{year}" not in pattern and "{month}" not in pattern and "{day}" not in pattern:
                response = messagebox.askyesno(
                    "Warning", 
                    "Pattern doesn't contain any date placeholders ({year}, {month}, {day}).\n\n"
                    "All files will be copied to the same directory.\n\nContinue?"
                )
                if not response:
                    return
            
            result_container["target_root"] = target
            result_container["pattern"] = pattern
            config_dialog.destroy()
        
        def on_cancel():
            config_dialog.destroy()
        
        tk.Button(btn_frame, text="Start Copy", command=on_start, bg="#4CAF50", fg="white", width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=on_cancel, width=12).pack(side=tk.LEFT, padx=5)
        
        # Wait for dialog to close
        self.root.wait_window(config_dialog)
        
        target_root = result_container["target_root"]
        pattern = result_container["pattern"]
        
        if not target_root or not pattern:
            return  # User cancelled
        
        # Calculate total size of distinct items (duplicates + uniques)
        total_size = 0
        total_count = 0
        
        
        
        for img_data in self.loaded_uniques:
            total_size += img_data.size
            total_count += 1
        
        # Check available disk space
        try:
            disk_usage = shutil.disk_usage(target_root)
            available_space = disk_usage.free
            
            if total_size > available_space:
                messagebox.showerror(
                    "Insufficient Space",
                    f"Not enough disk space!\n\n"
                    f"Required: {self.format_size(total_size)}\n"
                    f"Available: {self.format_size(available_space)}\n\n"
                    f"Please select a different target directory."
                )
                return
            
            # Show confirmation with space info
            response = messagebox.askyesno(
                "Confirm Copy",
                f"Copy {total_count} distinct items to:\n{target_root}\n\n"
                f"Pattern: {pattern}\n"
                f"Total size: {self.format_size(total_size)}\n"
                f"Available space: {self.format_size(available_space)}\n\n"
                f"Continue?"
            )
            
            if not response:
                return
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to check disk space: {e}")
            return
        
        # Disable button during operation and show initial progress
        self.copy_btn.config(state=tk.DISABLED)
        self.progress_label.config(text="Starting copy operation...")
        
        # Start copy thread
        thread = threading.Thread(target=self.copy_distinct_items, args=(target_root, pattern))
        thread.daemon = True
        thread.start()
    
    def copy_distinct_items(self, target_root, pattern):
        """Copy all distinct items to target location with date-based paths."""
        old_stdout = sys.stdout
        sys.stdout = self.redirector
        
        try:
            resolver = TargetPathResolver(pattern)
            copied_count = 0
            error_count = 0
            
            total_items = len(self.duplicates_data) + len(self.loaded_uniques)
            
            print(f"\nStarting copy operation to: {target_root}")
            print(f"Using pattern: {pattern}")
            print(f"Total distinct items: {total_items}")
            print(f"  - Duplicates (1 per group): {len(self.duplicates_data)}")
            print(f"  - Unique items: {len(self.loaded_uniques)}\n")
            
            # Copy one representative from each duplicate group
            for idx, (img_data, paths) in self.duplicates_data.items():
                try:
                    # Resolve date-based path
                    date_path = resolver.resolve(img_data)
                    
                    if not date_path:
                        print(f"Warning: Could not resolve date path for {img_data.filename}, skipping...")
                        error_count += 1
                        continue
                    
                    # Combine root with resolved path (remove leading slash from date_path)
                    target_dir = os.path.join(target_root, date_path.lstrip('/\\'))
                    
                    # Create directory if it doesn't exist
                    os.makedirs(target_dir, exist_ok=True)
                    
                    # Get source file (first path from the set) - only ONE from the duplicate group
                    source_file = list(paths)[0]
                    target_file = os.path.join(target_dir, img_data.filename)
                    
                    # Handle filename conflicts
                    if os.path.exists(target_file):
                        base, ext = os.path.splitext(img_data.filename)
                        counter = 1
                        while os.path.exists(target_file):
                            target_file = os.path.join(target_dir, f"{base}_{counter}{ext}")
                            counter += 1
                    
                    # Copy file
                    shutil.copy2(source_file, target_file)
                    copied_count += 1
                    
                    # Update progress on GUI
                    percentage = (copied_count / total_items) * 100
                    self.root.after(0, lambda c=copied_count, t=total_items, f=img_data.filename, p=percentage: 
                        self.progress_label.config(text=f"Copying: {f} ({c}/{t} - {p:.1f}%)"))
                    
                    # Show which file was selected from the duplicate group
                    print(f"[{copied_count}/{total_items}] Copied (dup 1/{len(paths)}): {img_data.filename} -> {date_path}")
                    print(f"    Source: {source_file}")
                    
                except Exception as e:
                    print(f"Error copying {img_data.filename}: {e}")
                    error_count += 1
            
            # Copy all unique items
            for img_data in self.loaded_uniques:
                try:
                    # Resolve date-based path
                    date_path = resolver.resolve(img_data)
                    
                    if not date_path:
                        print(f"Warning: Could not resolve date path for {img_data.filename}, skipping...")
                        error_count += 1
                        continue
                    
                    # Combine root with resolved path (remove leading slash from date_path)
                    target_dir = os.path.join(target_root, date_path.lstrip('/\\'))
                    
                    # Create directory if it doesn't exist
                    os.makedirs(target_dir, exist_ok=True)
                    
                    # Get source file
                    source_file = img_data.path
                    target_file = os.path.join(target_dir, img_data.filename)
                    
                    # Handle filename conflicts
                    if os.path.exists(target_file):
                        base, ext = os.path.splitext(img_data.filename)
                        counter = 1
                        while os.path.exists(target_file):
                            target_file = os.path.join(target_dir, f"{base}_{counter}{ext}")
                            counter += 1
                    
                    # Copy file
                    shutil.copy2(source_file, target_file)
                    copied_count += 1
                    
                    # Update progress on GUI
                    percentage = (copied_count / total_items) * 100
                    self.root.after(0, lambda c=copied_count, t=total_items, f=img_data.filename, p=percentage: 
                        self.progress_label.config(text=f"Copying: {f} ({c}/{t} - {p:.1f}%)"))
                    
                    print(f"[{copied_count}/{total_items}] Copied (unique): {img_data.filename} -> {date_path}")
                    
                except Exception as e:
                    print(f"Error copying {img_data.filename}: {e}")
                    error_count += 1
            
            # Show completion message
            summary = f"\nCopy operation complete!\n\nCopied: {copied_count} files\nErrors: {error_count}"
            print(summary)
            
            # Update progress label to show completion
            self.root.after(0, lambda c=copied_count, e=error_count: 
                self.progress_label.config(text=f"Copy complete: {c} files copied, {e} errors"))
            
            self.root.after(0, lambda c=copied_count, e=error_count: messagebox.showinfo(
                "Copy Complete",
                f"Successfully copied {c} distinct items.\n\nErrors: {e}"
            ))
            
        except Exception as e:
            print(f"\nCopy operation failed: {e}")
            self.root.after(0, lambda: self.progress_label.config(text="Copy failed!"))
            import traceback
            traceback.print_exc()
            self.root.after(0, lambda: messagebox.showerror("Error", f"Copy operation failed: {e}"))
        finally:
            sys.stdout = old_stdout
            self.root.after(0, lambda: self.copy_btn.config(state=tk.NORMAL))

if __name__ == "__main__":
    root = tk.Tk()
    app = DuplicateFinderGUI(root)
    root.mainloop()
