
import tkinter as tk
from tkinter import ttk

class ControlPanel(tk.Frame):
    def __init__(self, parent, on_scan_click, on_report_click, on_save_click, on_load_click, on_merge_click, on_copy_click, on_pause_click, on_cancel_click):
        super().__init__(parent)
        
        # Extension Input
        ext_frame = tk.Frame(self)
        ext_frame.pack(fill=tk.X, pady=10)
        tk.Label(ext_frame, text="File Extension:").pack(side=tk.LEFT)
        self.ext_entry = tk.Entry(ext_frame, width=10)
        self.ext_entry.insert(0, "jpg")
        self.ext_entry.pack(side=tk.LEFT, padx=5)
        
        # Checksum Toggle
        self.checksum_var = tk.BooleanVar(value=False)
        self.checksum_cb = tk.Checkbutton(
            ext_frame, 
            text="Use Checksum (slower, more accurate)",
            variable=self.checksum_var
        )
        self.checksum_cb.pack(side=tk.LEFT, padx=15)
        
        # Action Buttons
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=5)
        
        self.scan_btn = tk.Button(btn_frame, text="Scan files", command=on_scan_click, bg="#dddddd")
        self.scan_btn.pack(side=tk.LEFT, padx=5)
        
        self.report_btn = tk.Button(btn_frame, text="Generate Report", command=on_report_click, bg="#dddddd")
        self.report_btn.pack(side=tk.LEFT, padx=5)
        
        self.save_btn = tk.Button(btn_frame, text="Export scan result", command=on_save_click, bg="#dddddd")
        self.save_btn.pack(side=tk.LEFT, padx=5)
        
        self.load_btn = tk.Button(btn_frame, text="Import scan result", command=on_load_click, bg="#dddddd")
        self.load_btn.pack(side=tk.LEFT, padx=5)
        
        self.merge_btn = tk.Button(btn_frame, text="Merge with Result", command=on_merge_click, bg="#dddddd")
        self.merge_btn.pack(side=tk.LEFT, padx=5)
        
        self.copy_btn = tk.Button(btn_frame, text="Archive distinct images", command=on_copy_click, bg="#dddddd")
        self.copy_btn.pack(side=tk.LEFT, padx=5)
        
        # Scan Control Buttons (Pause/Cancel)
        ctrl_frame = tk.Frame(self)
        ctrl_frame.pack(fill=tk.X, pady=5)
        
        self.pause_btn = tk.Button(ctrl_frame, text="Pause", command=on_pause_click, state=tk.DISABLED)
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        
        self.cancel_btn = tk.Button(ctrl_frame, text="Cancel", command=on_cancel_click, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.LEFT, padx=5)
        
    def get_extension(self):
        return self.ext_entry.get().strip()
        
    def get_use_checksum(self):
        return self.checksum_var.get()
        
    def set_processing_state(self, is_processing):
        state = tk.DISABLED if is_processing else tk.NORMAL
        ctrl_state = tk.NORMAL if is_processing else tk.DISABLED
        
        self.scan_btn.config(state=state)
        self.report_btn.config(state=state)
        # Save/Load/Copy might be allowed depending on context, but generally disabled during scan
        self.save_btn.config(state=state)
        self.load_btn.config(state=state) 
        self.merge_btn.config(state=state)
        # self.copy_btn.config(state=state) # Actually copy is a separate process
        
        self.pause_btn.config(state=ctrl_state)
        self.cancel_btn.config(state=ctrl_state)
        
        if not is_processing:
            self.pause_btn.config(text="Pause") # Reset text
            
    def set_paused(self, is_paused):
        self.pause_btn.config(text="Resume" if is_paused else "Pause")
