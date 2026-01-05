import hashlib
import os
import datetime
from .ImageData import ImageData


class TargetPathResolver:
    """
    Extended ImageData class that uses file content checksum for duplicate detection.
    
    This provides more accurate duplicate detection than metadata-based comparison,
    as it identifies files with identical content regardless of filename, date, or EXIF data.
    """
    
    def __init__(self):
        """
        Initialize ChecksumImageData.
        
        Args:
            path: File path
            date: File modification date
            size: File size in bytes
            filename: Base filename
            exif_date: EXIF DateTimeOriginal if available
            checksum: MD5 checksum of file content (calculated if None)
        """
        
    def resolve(self, image_data: ImageData):
        return self.resolve_target_path(image_data.date)
    
    @staticmethod
    def resolve_target_path(date):
        """
        Resolve target path based on date with pattern /YYYY/MM/DD
        """
        if not date:
            return None
            
        try:
            dt = datetime.datetime.fromtimestamp(date)
            return dt.strftime("/%Y/%m/%d")
        except Exception:
            return None
        
