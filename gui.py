
import tkinter as tk
import sys
import os

# Ensure data directory is in path (legacy support if needed, but we structure imports differently now)
sys.path.append(os.path.join(os.path.dirname(__file__), 'data'))

# Import the new MainWindow
from ui.MainWindow import MainWindow

if __name__ == "__main__":
    app = MainWindow()
    app.mainloop()
