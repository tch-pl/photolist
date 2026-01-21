
import concurrent.futures
import threading
import time
import sys
from typing import List, Optional, Callable, Dict, Set
from data import ImageData
from data.ScanResult import ScanResult

class ScannerService:
    """
    Service for scanning directories for duplicates.
    Orchestrates the scanning process, handles threading, and merges results.
    """
    
    def __init__(self):
        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.clear() # Not paused
        
    def cancel(self):
        self._cancel_event.set()
        
    def pause(self):
        self._pause_event.set()
        
    def resume(self):
        self._pause_event.clear()
        
    def is_paused(self):
        return self._pause_event.is_set()
        
    def is_cancelled(self):
        return self._cancel_event.is_set()
    
    # Interface expected by ImageData helpers
    def check(self):
        if self._cancel_event.is_set():
            raise ImageData.ProcessingCancelled("User cancelled processing")
        
        while self._pause_event.is_set():
            if self._cancel_event.is_set():
                raise ImageData.ProcessingCancelled("User cancelled processing")
            time.sleep(0.1)

    def scan(self, 
             folders: List[str], 
             ext: str, 
             use_checksum: bool = False,
             progress_callback: Callable[[str, int, int], None] = None,
             log_callback: Callable[[str], None] = None,
             base_result: Optional[ScanResult] = None) -> ScanResult:
        """
        Run the scan process.
        
        Args:
            folders: List of folder paths to scan.
            ext: File extension to filter (without dot).
            use_checksum: Whether to use content-based checksum.
            progress_callback: Function(status_msg, current, total) called periodically.
            log_callback: Function(msg) called for logging.
            
        Returns:
            ScanResult object.
        """
        self._cancel_event.clear()
        self._pause_event.clear()
        
        if log_callback: log_callback("Starting processing...")
        if log_callback: log_callback(f"Mode: {'Checksum' if use_checksum else 'Metadata'}")

        total_folders = len(folders)
        max_workers = total_folders if total_folders > 0 else 1
        
        all_uniques = []
        all_duplicates = {}
        
        # Helper logging
        def log(msg):
            if log_callback: log_callback(msg)
            
        # Progress tracking
        completed_folders = 0
        lock = threading.Lock()
        
        def folder_done():
            nonlocal completed_folders
            with lock:
                completed_folders += 1
                if progress_callback:
                    progress_callback(f"Processed folders: {completed_folders}/{total_folders}", completed_folders, total_folders)

        # Per-folder progress callback factory
        def make_folder_callback(folder_path):
            def cb(current, total):
                # We could aggregate this into a global progress if needed
                # For now just let the UI know something is happening?
                # Actually, the original UI updated per-folder status in the tree.
                # We might want to expose a standardized event for "folder status update"
                # But for simplicity, let's just log or ignore detailed per-file progress aggregation for now,
                # or rely on the main progress being "folders done".
                # To support the TreeView status update, we might need a richer callback.
                pass
            return cb

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                log(f"Parallelizing with {max_workers} folder worker threads.")
                
                future_to_folder = {}
                for folder in folders:
                    # Pass 'self' as the controller
                    future = executor.submit(
                        ImageData.find_duplicates, 
                        [folder], 
                        ext, 
                        progress_callback=make_folder_callback(folder), 
                        controller=self,
                        use_checksum=use_checksum
                    )
                    future_to_folder[future] = folder
                
                for future in concurrent.futures.as_completed(future_to_folder):
                    if self._cancel_event.is_set():
                        break
                        
                    folder = future_to_folder[future]
                    try:
                        folder_uniques, folder_duplicates = future.result()
                        
                        # Aggregate results
                        all_uniques.extend(folder_uniques)
                        
                        for img_data, paths in folder_duplicates.items():
                            if img_data in all_duplicates:
                                all_duplicates[img_data].update(paths)
                            else:
                                all_duplicates[img_data] = paths.copy()
                                
                        folder_done()
                        
                    except Exception as exc:
                        log(f"Folder {folder} generated an exception: {exc}")

            if self._cancel_event.is_set():
                raise ImageData.ProcessingCancelled("User cancelled processing")

            # CRITICAL: Merge logic (cross-folder duplicates)
            log(f"Merging results from {total_folders} folders...")
            
            # Map of all images
            image_map = {}
            
            # Add existing duplicates
            for img_data, paths in all_duplicates.items():
                image_map[img_data] = paths
            
            # Check uniques against map
            final_uniques = []
            for img_data in all_uniques:
                if img_data in image_map:
                    image_map[img_data].add(img_data.path)
                else:
                    image_map[img_data] = {img_data.path}
            
            # Rebuild final structures
            final_duplicates = {}
            final_uniques = []
            for img_data, paths in image_map.items():
                if len(paths) > 1:
                    final_duplicates[img_data] = paths
                else:
                    final_uniques.append(img_data)
            
            # Filter against base_result if provided
            if base_result:
                log(f"Filtering results against base result ({len(base_result.uniques)} unique, {len(base_result.duplicates)} duplicate groups)...")
                
                # Build set of known items
                known_items = set()
                known_items.update(base_result.uniques)
                known_items.update(base_result.duplicates.keys())
                
                filtered_uniques = []
                filtered_duplicates = {}
                
                # Filter uniques
                for u in final_uniques:
                    if u not in known_items:
                        filtered_uniques.append(u)
                        
                # Filter duplicates
                for d, paths in final_duplicates.items():
                    if d not in known_items:
                        filtered_duplicates[d] = paths
                        
                final_uniques = filtered_uniques
                final_duplicates = filtered_duplicates
                
                log(f"After filtering: {len(final_uniques)} unique files and {len(final_duplicates)} distinct duplicate groups.")
            
            log(f"Processing complete. Found {len(final_uniques)} unique files and {len(final_duplicates)} distinct duplicate groups.")
            
            return ScanResult(
                uniques=final_uniques,
                duplicates=final_duplicates,
                scanned_paths=folders,
                extension=ext,
                detection_mode='checksum' if use_checksum else 'metadata'
            )
            
        except ImageData.ProcessingCancelled:
            log("Processing cancelled.")
            raise
        except Exception as e:
            log(f"Error during scan: {e}")
            raise
