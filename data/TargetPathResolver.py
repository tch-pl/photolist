import hashlib
import os
import datetime
from .ImageData import ImageData


class TargetPathResolver:
    """
    Resolves target paths for image files based on date patterns.
    
    Supports customizable path patterns using placeholders like {year}, {month}, {day}.
    Default pattern is /{year}/{month}/{day}.
    """
    
    def __init__(self, pattern="/{year}/{month}/{day}"):
        """
        Initialize TargetPathResolver with a custom pattern.
        
        Args:
            pattern: Path pattern using placeholders {year}, {month}, {day}
                     Default: "/{year}/{month}/{day}"
        """
        self.pattern = pattern
        
    def resolve(self, image_data: ImageData):
        """
        Resolve target path for an ImageData object using the configured pattern.
        
        Args:
            image_data: ImageData object to resolve path for
            
        Returns:
            Resolved path string, or None if date cannot be determined
        """
        # Prefer EXIF date if available, fallback to file modification date
        date = image_data.exif_date if image_data.exif_date else image_data.date
        return self.resolve_target_path(date, self.pattern)
    
    @staticmethod
    def resolve_target_path(date, pattern="/{year}/{month}/{day}"):
        """
        Resolve target path based on date and pattern.
        
        Args:
            date: Unix timestamp or datetime-compatible value
            pattern: Path pattern with {year}, {month}, {day} placeholders
            
        Returns:
            Resolved path string, or None if date is invalid
        """
        if not date:
            return None
            
        try:
            # Handle both timestamp and string dates (from EXIF)
            if isinstance(date, str):
                # EXIF date format: "2023:12:31 14:30:00"
                dt = datetime.datetime.strptime(date, "%Y:%m:%d %H:%M:%S")
            else:
                # Unix timestamp
                dt = datetime.datetime.fromtimestamp(date)
            
            # Replace placeholders with actual values
            resolved = pattern.replace("{year}", dt.strftime("%Y"))
            resolved = resolved.replace("{month}", dt.strftime("%m"))
            resolved = resolved.replace("{day}", dt.strftime("%d"))
            
            return resolved
        except Exception:
            return None
        
