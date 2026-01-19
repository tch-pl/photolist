
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
        
    def _init_ui(self):
        # 1. Top Control Container
        top_frame = tk.Frame(self)
        top_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Folder List
        self.folder_panel = FolderListPanel(top_frame)
        self.folder_panel.pack(fill=tk.X, pady=5)
        
        # Controls
        self.control_panel = ControlPanel(
            top_frame,
            on_scan_click=self._start_scan,
            on_report_click=self._generate_report,
            on_save_click=self._save_results,
            on_load_click=self._load_results,
            on_copy_click=self._copy_distinct,
            on_pause_click=self._toggle_pause,
            on_cancel_click=self._cancel_processing
        )
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
            
        ext = self.control_panel.get_extension()
        if not ext:
            messagebox.showwarning("Warning", "Please specify a file extension.")
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
        thread = threading.Thread(target=self._run_scan_thread, args=(folders, ext, use_checksum))
        thread.daemon = True
        thread.start()
        
    def _run_scan_thread(self, folders, ext, use_checksum):
        try:
            def progress_cb(msg, current, total):
                self.after(0, lambda: self.status_label.config(text=msg))
                
            def log_cb(msg):
                self.after(0, lambda: self._log(msg))
                
            result = self.scanner_service.scan(
                folders, 
                ext, 
                use_checksum=use_checksum,
                progress_callback=progress_cb,
                log_callback=log_cb
            )
            
            self.after(0, lambda: self._on_scan_complete(result))
            
        except ImageData.ProcessingCancelled:
            self.after(0, lambda: self.status_label.config(text="Scan Cancelled"))
            self.after(0, lambda: self._log("Scan cancelled by user."))
        except Exception as e:
            self.after(0, lambda: self.status_label.config(text="Error"))
            self.after(0, lambda: self._log(f"Error: {e}"))
            import traceback
            traceback.print_exc()
        finally:
            self.after(0, lambda: self._set_processing(False))
            self.after(0, self.animation_panel.stop)

    def _on_scan_complete(self, result: ScanResult):
        self.current_scan_result = result
        self.status_label.config(text=f"Scan Complete. Found {result.duplicate_groups_count} duplicate groups.")
        self.results_panel.populate(result)

    def _set_processing(self, is_processing):
        self.control_panel.set_processing_state(is_processing)
        
    def _toggle_pause(self):
        if self.scanner_service.is_paused():
            self.scanner_service.resume()
            self.control_panel.set_paused(False)
            self.status_label.config(text="Resumed...")
        else:
            self.scanner_service.pause()
            self.control_panel.set_paused(True)
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
