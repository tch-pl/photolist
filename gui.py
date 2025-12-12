import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
import sys
import os

# Ensure we can import ImageData from the data directory
sys.path.append(os.path.join(os.path.dirname(__file__), 'data'))
import ImageData

class DuplicateFinderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Duplicate Image Finder")
        self.root.geometry("600x500")

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
        tk.Button(control_frame, text="Find Duplicates", command=self.process, bg="#dddddd").pack(pady=10)

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

    def process(self):
        folders = self.folder_list.get(0, tk.END)
        if not folders:
            messagebox.showwarning("Warning", "Please add at least one folder.")
            return
        
        ext = self.ext_entry.get().strip()
        if not ext:
            messagebox.showwarning("Warning", "Please specify a file extension.")
            return

        # Clear previous output
        self.output_area.delete(1.0, tk.END)
        print("Starting processing...")
        
        # Redirect stdout
        old_stdout = sys.stdout
        sys.stdout = self.redirector

        try:
            # Call the logic
            ImageData.main(list(folders), ext)
            print("\nProcessing complete.")
        except Exception as e:
            print(f"\nError: {e}")
        finally:
            # Restore stdout
            sys.stdout = old_stdout

if __name__ == "__main__":
    root = tk.Tk()
    app = DuplicateFinderGUI(root)
    root.mainloop()
