
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

class FolderListPanel(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        
        # Header
        tk.Label(self, text="Selected Folders:").pack(anchor=tk.W)
        
        # Treeview + Scrollbar
        list_frame = tk.Frame(self)
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
        
        # Buttons
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=5)
        
        tk.Button(btn_frame, text="Add Folder", command=self._add_folder).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Remove Selected", command=self._remove_folder).pack(side=tk.LEFT, padx=5)

    def _add_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            existing = self.get_folders()
            if folder not in existing:
                self.folder_tree.insert("", tk.END, values=(folder, "Pending"))
                
    def _remove_folder(self):
        selection = self.folder_tree.selection()
        if selection:
            for item in selection:
                self.folder_tree.delete(item)
                
    def get_folders(self):
        return [self.folder_tree.item(item)['values'][0] for item in self.folder_tree.get_children()]

    def update_status(self, folder_path, status):
        # We need to find the item. This is O(N) but N is small.
        # Ideally we maintain a map, but for simplicity:
        for item in self.folder_tree.get_children():
            vals = self.folder_tree.item(item)['values']
            if vals[0] == folder_path:
                self.folder_tree.set(item, "Status", status)
                break
                
    def clear_status(self):
        for item in self.folder_tree.get_children():
            self.folder_tree.set(item, "Status", "Pending")
