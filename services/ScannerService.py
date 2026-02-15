
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
             ext, 
             use_checksum: bool = False,
             progress_callback: Callable[[str, int, int], None] = None,
             log_callback: Callable[[str], None] = None,
             base_result: Optional[ScanResult] = None) -> ScanResult:
        """
        Run the scan process.
        
        Args:
            folders: List of folder paths to scan.
            ext: File extension (string) or list of extensions to filter (without dot).
            use_checksum: Whether to use content-based checksum.
            progress_callback: Function(status_msg, current, total) called periodically.
            log_callback: Function(msg) called for logging.
            base_result: Optional base scan result for merge operations.
            
        Returns:
            ScanResult object.
        """
        self._cancel_event.clear()
        self._pause_event.clear()
        
        # Handle both single extension and list of extensions
        extensions = [ext] if isinstance(ext, str) else ext
        
        def log(msg):
            if log_callback: log_callback(msg)
        
        log("Starting processing...")
        log(f"Mode: {'Checksum' if use_checksum else 'Metadata'}")
        log(f"Extensions: {', '.join(extensions)}")

        try:
            # Step 1: Scan all folders in parallel
            all_uniques, all_duplicates = self._scan_folders_parallel(
                folders, extensions, use_checksum, progress_callback, log
            )
            
            # Step 2: Merge results from multiple folders (detect cross-folder duplicates)
            final_uniques, final_duplicates = self._merge_folder_results(
                all_uniques, all_duplicates, len(folders), log
            )
            
            # Step 3: Filter against base result if provided (merge scan feature)
            if base_result:
                final_uniques, final_duplicates = self._filter_against_base(
                    final_uniques, final_duplicates, base_result, log
                )
            
            log(f"Processing complete. Found {len(final_uniques)} unique files and {len(final_duplicates)} distinct duplicate groups.")
            
            return ScanResult(
                uniques=final_uniques,
                duplicates=final_duplicates,
                scanned_paths=folders,
                extension=', '.join(extensions),
                detection_mode='checksum' if use_checksum else 'metadata'
            )
            
        except ImageData.ProcessingCancelled:
            log("Processing cancelled.")
            raise
        except Exception as e:
            log(f"Error during scan: {e}")
            raise
    
    def _scan_folders_parallel(self, 
                               folders: List[str], 
                               extensions: List[str],
                               use_checksum: bool,
                               progress_callback: Optional[Callable[[str, int, int], None]],
                               log: Callable[[str], None]) -> tuple[List, Dict]:
        """
        Scan multiple folders in parallel.
        
        Returns:
            Tuple of (all_uniques, all_duplicates) aggregated from all folders.
        """
        total_folders = len(folders)
        max_workers = total_folders if total_folders > 0 else 1
        
        all_uniques = []
        all_duplicates = {}
        
        # Progress tracking
        completed_folders = 0
        lock = threading.Lock()
        
        def folder_done():
            nonlocal completed_folders
            with lock:
                completed_folders += 1
                if progress_callback:
                    progress_callback(
                        f"Processed folders: {completed_folders}/{total_folders}", 
                        completed_folders, 
                        total_folders
                    )

        def make_folder_callback(folder_path):
            """Create per-folder progress callback if needed."""
            def cb(current, total):
                # Could be enhanced to provide per-folder progress updates
                pass
            return cb

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            log(f"Parallelizing with {max_workers} folder worker threads.")
            
            future_to_folder = {}
            for folder in folders:
                future = executor.submit(
                    ImageData.find_duplicates, 
                    [folder], 
                    extensions, 
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
            
        return all_uniques, all_duplicates
    
    def _merge_folder_results(self, 
                              all_uniques: List, 
                              all_duplicates: Dict,
                              total_folders: int,
                              log: Callable[[str], None]) -> tuple[List, Dict]:
        """
        Merge results from multiple folders to detect cross-folder duplicates.
        
        Returns:
            Tuple of (final_uniques, final_duplicates) after merging.
        """
        log(f"Merging results from {total_folders} folders...")
        
        # Build a map of all images
        image_map = {}
        
        # Add existing duplicates
        for img_data, paths in all_duplicates.items():
            image_map[img_data] = paths
        
        # Check uniques against the map
        for img_data in all_uniques:
            if img_data in image_map:
                image_map[img_data].add(img_data.path)
            else:
                image_map[img_data] = {img_data.path}
        
        # Rebuild final structures based on path count
        final_duplicates = {}
        final_uniques = []
        for img_data, paths in image_map.items():
            if len(paths) > 1:
                final_duplicates[img_data] = paths
            else:
                final_uniques.append(img_data)
        
        return final_uniques, final_duplicates
    
    def _filter_against_base(self, 
                             uniques: List, 
                             duplicates: Dict,
                             base_result: ScanResult,
                             log: Callable[[str], None]) -> tuple[List, Dict]:
        """
        Filter scan results against a base result (merge scan feature).
        Only returns items not present in the base result.
        
        Returns:
            Tuple of (filtered_uniques, filtered_duplicates).
        """
        log(f"Filtering results against base result ({len(base_result.uniques)} unique, {len(base_result.duplicates)} duplicate groups)...")
        
        # Build set of known items from base result
        known_items = set()
        known_items.update(base_result.uniques)
        known_items.update(base_result.duplicates.keys())
        
        # Filter uniques
        filtered_uniques = [u for u in uniques if u not in known_items]
        
        # Filter duplicates
        filtered_duplicates = {d: paths for d, paths in duplicates.items() if d not in known_items}
        
        log(f"After filtering: {len(filtered_uniques)} unique files and {len(filtered_duplicates)} distinct duplicate groups.")
        
        return filtered_uniques, filtered_duplicates
