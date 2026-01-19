from datetime import datetime
from typing import List, Dict, Set
from .ImageData import ImageData

class ScanResult:
    """
    Encapsulates the results and metadata of a duplicate scan.
    """
    def __init__(self, 
                 uniques: List[ImageData], 
                 duplicates: Dict[ImageData, Set[str]], 
                 scanned_paths: List[str],
                 extension: str,
                 detection_mode: str,
                 timestamp: float = None):
        """
        Initialize a ScanResult.

        Args:
            uniques: List of unique ImageData objects.
            duplicates: Dictionary mapping ImageData to a set of duplicate file paths.
            scanned_paths: List of root folder paths that were scanned.
            extension: The file extension that was filtered for.
            detection_mode: 'checksum' or 'metadata'.
            timestamp: Unix timestamp of the scan. Defaults to current time.
        """
        self.uniques = uniques
        self.duplicates = duplicates
        self.scanned_paths = scanned_paths
        self.extension = extension
        self.detection_mode = detection_mode
        self.timestamp = timestamp if timestamp is not None else datetime.now().timestamp()

    @property
    def total_files_scanned(self) -> int:
        count = len(self.uniques)
        for paths in self.duplicates.values():
            count += len(paths)
        return count

    @property
    def duplicate_groups_count(self) -> int:
        return len(self.duplicates)
