
import tkinter as tk
import math

class AnimationPanel(tk.Canvas):
    def __init__(self, parent, width=200, height=100, bg="#101010"):
        super().__init__(parent, width=width, height=height, bg=bg)
        self.is_running = False
        self.animation_step = 0
        self.animation_id = None
        
    def start(self):
        if not self.is_running:
            self.is_running = True
            self.animate()
            
    def stop(self):
        self.is_running = False
        if self.animation_id:
            self.after_cancel(self.animation_id)
            self.animation_id = None
        self.delete("all")
        
    def animate(self):
        if not self.is_running:
            return
            
        self.delete("all")
        w = self.winfo_width()
        if w < 10: w = 200
        h = self.winfo_height()
        if h < 10: h = 100 # Fallback header size
        
        self.animation_step += 0.05
        
        # Hallucinating Effect
        cols = 8
        rows = 4
        cell_w = w / cols
        cell_h = h / rows
        
        palette = ["#FF00FF", "#00FFFF", "#FFFF00", "#FF0000", "#0000FF", "#00FF00"]
        
        for r in range(rows):
            for c in range(cols):
                cx = (c + 0.5) * cell_w
                cy = (r + 0.5) * cell_h
                
                dx = math.sin(self.animation_step + c*0.5 + r*0.3) * (cell_w * 0.8)
                dy = math.cos(self.animation_step * 1.2 + c*0.3 + r*0.5) * (cell_h * 0.8)
                
                size = (cell_w + cell_h) * 0.4 * (1.2 + 0.5 * math.sin(self.animation_step * 2 + r*c))
                
                col_idx = int(self.animation_step * 2 + c + r) % len(palette)
                color = palette[col_idx]
                
                x1 = cx + dx - size
                y1 = cy + dy - size
                x2 = cx + dx + size
                y2 = cy + dy + size
                
                self.create_oval(x1, y1, x2, y2, fill=color, outline="", stipple="gray50")

        self.animation_id = self.after(50, self.animate)
