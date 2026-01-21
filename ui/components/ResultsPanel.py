
import tkinter as tk
from tkinter import ttk, scrolledtext
from PIL import Image, ImageTk

class ResultsPanel(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        

        # Stats Header
        self.stats_frame = tk.Frame(self)
        self.stats_frame.pack(fill=tk.X, padx=5, pady=2)
        self.stats_label = tk.Label(self.stats_frame, text="No scan results.", font=("Arial", 9, "italic"), fg="#888")
        self.stats_label.pack(anchor=tk.W)

        # Split View
        self.paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)

        # Left Panel: Results List
        left_frame = tk.Frame(self.paned_window)
        tk.Label(left_frame, text="Scan Results:").pack(anchor=tk.W)
        
        self.groups_list = tk.Listbox(left_frame, width=40)
        self.groups_list.pack(fill=tk.BOTH, expand=True)
        self.groups_list.bind('<<ListboxSelect>>', self._on_group_select)
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
        
        self.duplicates_data = {} # Map Index -> (ImageData, [paths])
        self.tk_image = None # Keep reference

    def custom_clear(self):
        self.groups_list.delete(0, tk.END)
        self.details_text.delete(1.0, tk.END)
        self.preview_label.config(image="", text="No Preview")
        self.duplicates_data = {}

    def populate(self, scan_result):
        self.custom_clear()
        
        if not scan_result:
            self.stats_label.config(text="No scan results.", font=("Arial", 9, "italic"), fg="#888")
            self._show_empty_message()
            return
            
        # Update Stats
        from datetime import datetime
        ts_str = datetime.fromtimestamp(scan_result.timestamp).strftime('%Y-%m-%d %H:%M:%S')
        mode = scan_result.detection_mode.capitalize()
        stats_text = (f"Scan: {ts_str} | Mode: {mode} | "
                      f"Total Files: {scan_result.total_files_scanned} | "
                      f"Duplicate Groups: {scan_result.duplicate_groups_count}")
        self.stats_label.config(text=stats_text, font=("Arial", 9, "bold"), fg="black")

        # Collect all items to display
        # List of tuples: (displayed_text, ImageData, paths_list_or_None)
        items = []

        # Add duplicates
        for img_data, paths in scan_result.duplicates.items():
            items.append((f"{img_data.filename} ({len(paths)} copies)", img_data, paths))

        # Add uniques (if any are explicitly interesting, e.g. from merge)
        # Note: In standard scan, uniques are usually not shown in this list. 
        # But user requested "list of scan result items". 
        # For Merge scan, 'uniques' are the result.
        for img_data in scan_result.uniques:
            items.append((f"{img_data.filename}", img_data, None))

        if not items:
            self._show_empty_message()
            return
            
        # Sort items by filename
        items.sort(key=lambda x: x[0])

        idx = 0
        for label, img_data, paths in items:
            self.groups_list.insert(tk.END, label)
            # Store data: (ImageData, paths) -> paths is None for unique items
            self.duplicates_data[idx] = (img_data, paths)
            idx += 1
            
    def _show_empty_message(self):
        self.groups_list.insert(tk.END, "[No items found]")
        self.groups_list.itemconfig(0, {'fg': '#888888'})

    def _on_group_select(self, event):
        selection = self.groups_list.curselection()
        if not selection:
            return
        
        index = selection[0]
        if index in self.duplicates_data:
            img_data, paths = self.duplicates_data[index]
            self._show_details(img_data, paths)
            
            # Show Preview (First image)
            if paths:
                first_path = list(paths)[0]
                self._show_preview(first_path)
            else:
                # Unique item, use its own path
                self._show_preview(img_data.path)

    def _show_details(self, img_data, paths):
        self.details_text.delete(1.0, tk.END)
        self.details_text.insert(tk.END, f"Filename: {img_data.filename}\n")
        self.details_text.insert(tk.END, f"Size: {img_data.size} bytes\n")
        self.details_text.insert(tk.END, f"Date: {img_data.date}\n")
        exif_str = str(img_data.exif_date) if img_data.exif_date else "No EXIF"
        self.details_text.insert(tk.END, f"EXIF Date: {exif_str}\n")
        self.details_text.insert(tk.END, "-"*40 + "\n")
        
        if paths:
            self.details_text.insert(tk.END, f"Count: {len(paths)}\n")
            self.details_text.insert(tk.END, "Paths (Duplicates):\n")
            for p in paths:
                self.details_text.insert(tk.END, f"  {p}\n")
        else:
            self.details_text.insert(tk.END, "Unique Item\n")
            self.details_text.insert(tk.END, f"Path: {img_data.path}\n")

    def _show_preview(self, path):
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
