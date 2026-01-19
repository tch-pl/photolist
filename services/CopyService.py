
import os
import shutil
import sys
import threading
from typing import Callable, Optional
from data import ImageData
from data.TargetPathResolver import TargetPathResolver
from data.ScanResult import ScanResult

class CopyService:
    """
    Service for copying distinct items to a target location.
    """
    
    def __init__(self):
        self._cancel_event = threading.Event()
        
    def cancel(self):
        self._cancel_event.set()
        
    def is_cancelled(self):
        return self._cancel_event.is_set()

    def copy_distinct_items(self, 
                          scan_result: ScanResult, 
                          target_root: str, 
                          pattern: str, 
                          progress_callback: Callable[[str, int, int], None] = None,
                          log_callback: Callable[[str], None] = None):
        """
        Copy all distinct items (uniques + 1 from each duplicate group) to target location.
        """
        self._cancel_event.clear()
        
        resolver = TargetPathResolver(pattern)
        copied_count = 0
        error_count = 0
        
        # Combine items
        duplicates_count = len(scan_result.duplicates)
        uniques_count = len(scan_result.uniques)
        total_items = duplicates_count + uniques_count
        
        if log_callback:
            log_callback(f"\nStarting copy operation to: {target_root}")
            log_callback(f"Using pattern: {pattern}")
            log_callback(f"Total distinct items: {total_items}")
        
        def update_progress(filename):
            if progress_callback:
                progress_callback(f"Copying: {filename}", copied_count, total_items)

        # 1. Process Duplicates
        for img_data, paths in scan_result.duplicates.items():
            if self._cancel_event.is_set(): break
            
            try:
                self._copy_item(img_data, paths, resolver, target_root, log_callback)
                copied_count += 1
                update_progress(img_data.filename)
            except Exception as e:
                if log_callback: log_callback(f"Error copying {img_data.filename}: {e}")
                error_count += 1

        # 2. Process Uniques
        for img_data in scan_result.uniques:
            if self._cancel_event.is_set(): break
            
            try:
                # Uniques behave as having 1 path usually, but img_data has .path
                self._copy_item(img_data, {img_data.path}, resolver, target_root, log_callback)
                copied_count += 1
                update_progress(img_data.filename)
            except Exception as e:
                if log_callback: log_callback(f"Error copying {img_data.filename}: {e}")
                error_count += 1

        if self._cancel_event.is_set():
            if log_callback: log_callback("Copy operation cancelled.")
            return

        summary = f"Copy complete! Copied: {copied_count}, Errors: {error_count}"
        if log_callback: log_callback(summary)
        
    def _copy_item(self, img_data: ImageData, paths: set, resolver, target_root, log_callback):
        # Resolve path
        date_path = resolver.resolve(img_data)
        if not date_path:
            raise ValueError(f"Could not resolve date path for {img_data.filename}")
            
        target_dir = os.path.join(target_root, date_path.lstrip('/\\'))
        os.makedirs(target_dir, exist_ok=True)
        
        # Source file (pick first)
        source_file = list(paths)[0]
        target_file = os.path.join(target_dir, img_data.filename)
        
        # Handle conflicts
        if os.path.exists(target_file):
            base, ext = os.path.splitext(img_data.filename)
            counter = 1
            while os.path.exists(target_file):
                target_file = os.path.join(target_dir, f"{base}_{counter}{ext}")
                counter += 1
                
        shutil.copy2(source_file, target_file)
        if log_callback:
            log_callback(f"Copied: {img_data.filename} -> {date_path}")
