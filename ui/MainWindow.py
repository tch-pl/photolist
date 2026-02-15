
import tkinter as tk
from tkinter import messagebox, filedialog, scrolledtext
import threading
import os
import sys

from .components.FolderListPanel import FolderListPanel
from .components.ControlPanel import ControlPanel
from .components.ResultsPanel import ResultsPanel
from .components.AnimationPanel import AnimationPanel
from services.ScannerService import ScannerService
from services.CopyService import CopyService
from data import ImageData
from data.ScanResult import ScanResult
from data.storage import ScanResultStorage

class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Duplicate Image Finder (Refactored)")
        self.geometry("800x700")
        
        # Services
        self.scanner_service = ScannerService()
        self.copy_service = CopyService()
        
        self.current_scan_result = None
        
        self._init_ui()
        self.after(100, self._auto_load_results) # Run after UI init
        
    def _init_menu_bar(self):
        """Initialize the menu bar with File and Actions menus."""
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        
        # File Menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        
        file_menu.add_command(label="Import scan result", command=self._load_results)
        file_menu.add_command(label="Export scan result", command=self._save_results)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        
        # Actions Menu
        actions_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Actions", menu=actions_menu)
        
        self.scan_menu_item = actions_menu.add_command(label="Scan files", command=self._start_scan)
        self.merge_menu_item = actions_menu.add_command(label="Merge with Result", command=self._merge_scan)
        self.report_menu_item = actions_menu.add_command(label="Generate Report", command=self._generate_report)
        self.copy_menu_item = actions_menu.add_command(label="Archive distinct images", command=self._copy_distinct)
        actions_menu.add_separator()
        self.pause_menu_item = actions_menu.add_command(label="Pause", command=self._toggle_pause, state=tk.DISABLED)
        self.cancel_menu_item = actions_menu.add_command(label="Cancel", command=self._cancel_processing, state=tk.DISABLED)
        
        # Store menu references for state management
        self.actions_menu = actions_menu
        
    def _init_ui(self):
        # Menu Bar
        self._init_menu_bar()
        
        # 1. Top Control Container
        top_frame = tk.Frame(self)
        top_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Folder List
        self.folder_panel = FolderListPanel(top_frame)
        self.folder_panel.pack(fill=tk.X, pady=5)
        
        # Controls (now only for extension and checksum configuration)
        self.control_panel = ControlPanel(top_frame)
        self.control_panel.pack(fill=tk.X, pady=5)
        
        # Status Label
        self.status_label = tk.Label(top_frame, text="Ready", font=("Arial", 10))
        self.status_label.pack(pady=2)
        
        # Animation
        self.animation_panel = AnimationPanel(top_frame)
        self.animation_panel.pack(pady=5, fill=tk.X)
        
        # 2. Results Area
        self.results_panel = ResultsPanel(self)
        self.results_panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 3. Log Area (Small)
        self.log_area = scrolledtext.ScrolledText(self, height=4)
        self.log_area.pack(fill=tk.X, padx=10, pady=5)

    def _log(self, msg):
        try:
            self.log_area.insert(tk.END, str(msg) + "\n")
            self.log_area.see(tk.END)
        except Exception:
            pass

    def _start_scan(self):
        folders = self.folder_panel.get_folders()
        if not folders:
            messagebox.showwarning("Warning", "Please add at least one folder.")
            return
            
        extensions = self.control_panel.get_extension()
        if not extensions:
            messagebox.showwarning("Warning", "Please specify valid file extension(s). Check the validation message.")
            return
            
        use_checksum = self.control_panel.get_use_checksum()
        
        # Reset UI
        self.results_panel.custom_clear()
        self.log_area.delete(1.0, tk.END)
        self.current_scan_result = None
        self.folder_panel.clear_status()
        
        self._set_processing(True)
        self.status_label.config(text="Starting scan...")
        self.animation_panel.start()
        
        # Run in thread
        thread = threading.Thread(target=self._run_scan_thread, args=(folders, extensions, use_checksum))
        thread.daemon = True
        thread.start()
        
    def _merge_scan(self):
        """Start a new scan but merge/filter against an existing result."""
        # 1. Validation (folders, ext)
        folders = self.folder_panel.get_folders()
        if not folders:
            messagebox.showwarning("Warning", "Please add at least one folder to scan.")
            return
            
        extensions = self.control_panel.get_extension()
        if not extensions:
            messagebox.showwarning("Warning", "Please specify valid file extension(s). Check the validation message.")
            return
            
        use_checksum = self.control_panel.get_use_checksum()
        
        # 2. Select Base Result
        filepath = filedialog.askopenfilename(
            title="Select Base Scan Result",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")]
        )
        if not filepath: return
        
        # 3. Load Base Result
        try:
            base_result = ScanResultStorage.load_results(filepath)
            if not base_result:
                messagebox.showerror("Error", "Failed to load base result file.")
                return
            self._log(f"Loaded base result from {os.path.basename(filepath)} ({base_result.total_files_scanned} files)")
        except Exception as e:
            messagebox.showerror("Error", f"Error loading base result: {e}")
            return
            
        # 4. Start Scan (filtered)
        # Reset UI
        self.results_panel.custom_clear()
        self.log_area.delete(1.0, tk.END)
        self.current_scan_result = None
        self.folder_panel.clear_status()
        
        self._set_processing(True)
        self.status_label.config(text=f"Starting merged scan (against {os.path.basename(filepath)})...")
        self.animation_panel.start()
        
        # Run in thread with base_result
        thread = threading.Thread(target=self._run_scan_thread, args=(folders, extensions, use_checksum, base_result))
        thread.daemon = True
        thread.start()

    def _run_scan_thread(self, folders, ext, use_checksum, base_result=None):
        try:
            def progress_cb(msg, current, total):
                self.after(0, lambda m=msg: self.status_label.config(text=m))
                
            def log_cb(msg):
                self.after(0, lambda m=msg: self._log(m))

            self._log(f"Base result {base_result}")
            result = self.scanner_service.scan(
                folders, 
                ext, 
                use_checksum=use_checksum,
                progress_callback=progress_cb,
                log_callback=log_cb,
                base_result=base_result
            )
            self._log(f"Scan result {result}")

            
            
        except ImageData.ProcessingCancelled:
            self.after(0, lambda: self.status_label.config(text="Scan Cancelled"))
            self.after(0, lambda: self._log("Scan cancelled by user."))
        except Exception as e:
            self.after(0, lambda: self.status_label.config(text="Error"))
            self.after(0, lambda err=str(e): self._log(f"Error: {err}"))
            import traceback
            traceback.print_exc()
        finally:
            self.after(0, lambda: self._set_processing(False))
            self.after(0, self.animation_panel.stop)
            # Fix: Capture result properly in the lambda
            self.after(0, lambda r=result: self._on_scan_complete(r))

    def _on_scan_complete(self, result: ScanResult):
        self.current_scan_result = result
        self._log(f"Scan complete: {len(result.uniques)} unique items, {len(result.duplicates)} duplicate groups")
        self.status_label.config(text=f"Scan Complete. Found {result.duplicate_groups_count} duplicate groups, {len(result.uniques)} unique items.")
        self.results_panel.populate(result)

    def _set_processing(self, is_processing):
        """Enable/disable menu items based on processing state."""
        state = tk.DISABLED if is_processing else tk.NORMAL
        ctrl_state = tk.NORMAL if is_processing else tk.DISABLED
        
        # Disable/enable action menu items during processing
        self.actions_menu.entryconfig(0, state=state)  # Scan files
        self.actions_menu.entryconfig(1, state=state)  # Merge with Result
        self.actions_menu.entryconfig(2, state=state)  # Generate Report
        self.actions_menu.entryconfig(3, state=state)  # Archive distinct images
        
        # Enable/disable pause and cancel during processing
        self.actions_menu.entryconfig(5, state=ctrl_state)  # Pause
        self.actions_menu.entryconfig(6, state=ctrl_state)  # Cancel
        
        if not is_processing:
            self.actions_menu.entryconfig(5, label="Pause")  # Reset pause label
        
    def _toggle_pause(self):
        if self.scanner_service.is_paused():
            self.scanner_service.resume()
            self.actions_menu.entryconfig(5, label="Pause")
            self.status_label.config(text="Resumed...")
        else:
            self.scanner_service.pause()
            self.actions_menu.entryconfig(5, label="Resume")
            self.status_label.config(text="Paused")

    def _cancel_processing(self):
        self.scanner_service.cancel()
        self.copy_service.cancel() # Try cancel copy if running
        self.status_label.config(text="Cancelling...")

    def _save_results(self):
        if not self.current_scan_result:
            messagebox.showinfo("Info", "No results to save.")
            return
            
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")]
        )
        if not filepath: return
        
        if ScanResultStorage.save_results(self.current_scan_result, filepath):
            messagebox.showinfo("Success", f"Saved to {filepath}")
            self._log(f"Saved results to {filepath}")
        else:
            messagebox.showerror("Error", "Failed to save results.")

    def _load_results(self):
        filepath = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")]
        )
        if not filepath: return
        
        result = ScanResultStorage.load_results(filepath)
        if result:
            self.current_scan_result = result
            self.results_panel.populate(result)
            self.status_label.config(text=f"Loaded {result.duplicate_groups_count} groups from file.")
            self._log(f"Loaded results from {filepath}")
        else:
            messagebox.showerror("Error", "Failed to load results.")

    def _auto_load_results(self):
        """Automatically load results from default storage if available."""
        if ScanResultStorage.storage_exists():
            try:
                result = ScanResultStorage.load_results()
                if result:
                    self.current_scan_result = result
                    self.results_panel.populate(result)
                    self.status_label.config(text=f"Auto-loaded {result.duplicate_groups_count} groups from previous scan.")
                    self._log("Auto-loaded previous scan results.")
            except Exception as e:
                self._log(f"Failed to auto-load: {e}")

    def _copy_distinct(self):
        if not self.current_scan_result:
            messagebox.showwarning("Warning", "No results to copy.")
            return
            
        # Simplified configuration dialog flow
        # In a real app, I'd move this dialog to a component too
        
        target_dir = filedialog.askdirectory(title="Select Target Base Directory")
        if not target_dir: return
        
        self._set_processing(True)
        self.status_label.config(text="Copying...")
        
        thread = threading.Thread(
            target=self._run_copy_thread, 
            args=(self.current_scan_result, target_dir, "/{year}/{month}/{day}")
        )
        thread.daemon = True
        thread.start()

    def _run_copy_thread(self, result, target, pattern):
        try:
            def progress_cb(msg, current, total):
                self.after(0, lambda: self.status_label.config(text=msg))
                
            def log_cb(msg):
                self.after(0, lambda: self._log(msg))
                
            self.copy_service.copy_distinct_items(
                result, target, pattern, 
                progress_callback=progress_cb, 
                log_callback=log_cb
            )
            self.after(0, lambda: messagebox.showinfo("Success", "Copy complete!"))
            
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", f"Copy failed: {e}"))
        finally:
            self.after(0, lambda: self._set_processing(False))
            self.after(0, lambda: self.status_label.config(text="Ready"))

    def _generate_report(self):
        if not self.current_scan_result:
            messagebox.showinfo("Info", "No results for report.")
            return
            
        # Simplistic report window
        top = tk.Toplevel(self)
        top.title("Report")
        top.geometry("600x400")
        
        txt = scrolledtext.ScrolledText(top)
        txt.pack(fill=tk.BOTH, expand=True)
        
        res = self.current_scan_result
        lines = [
            "=== Dataset Report ===",
            f"Total Files Scanned: {res.total_files_scanned}",
            f"Duplicate Groups: {res.duplicate_groups_count}",
            f"Detection Mode: {res.detection_mode}",
            f"Scan Time: {res.timestamp}"
        ]
        
        txt.insert(tk.END, "\n".join(lines))
