import hashlib
import os
from .ImageData import ImageData


class ChecksumImageData(ImageData):
    """
    Extended ImageData class that uses file content checksum for duplicate detection.
    
    This provides more accurate duplicate detection than metadata-based comparison,
    as it identifies files with identical content regardless of filename, date, or EXIF data.
    """
    
    def __init__(self, path=None, date=None, size=None, filename=None, exif_date=None, checksum=None):
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
        super().__init__(path, date, size, filename, exif_date)
        self._checksum = checksum
        
    @property
    def checksum(self):
        """Get the checksum, calculating it if not already set."""
        if self._checksum is None and self.path:
            self._checksum = self.calculate_checksum(self.path)
        return self._checksum
    
    @staticmethod
    def calculate_checksum(filepath, chunk_size=8192):
        """
        Calculate MD5 checksum of a file.
        
        Args:
            filepath: Path to the file
            chunk_size: Size of chunks to read (default 8KB for memory efficiency)
            
        Returns:
            MD5 checksum as hexadecimal string, or None if error
        """
        try:
            md5_hash = hashlib.md5()
            with open(filepath, 'rb') as f:
                # Read file in chunks to handle large files efficiently
                while chunk := f.read(chunk_size):
                    md5_hash.update(chunk)
            return md5_hash.hexdigest()
        except Exception as e:
            print(f"Error calculating checksum for {filepath}: {e}")
            return None
    
    def __eq__(self, other):
        """
        Compare based on checksum and size.
        
        Two images are considered equal if they have the same checksum and size.
        This is more reliable than metadata-based comparison.
        """
        if not isinstance(other, ChecksumImageData):
            return NotImplemented
        elif self is other:
            return True
        else:
            # Compare by checksum (content) and size
            return (self.checksum == other.checksum and 
                    self.size == other.size and 
                    self.checksum is not None)
    
    def __hash__(self):
        """
        Hash based on checksum and size.
        
        This allows ChecksumImageData objects to be used as dictionary keys
        and in sets, with duplicates being properly identified.
        """
        # Use checksum as primary hash component
        if self.checksum:
            return hash((self.checksum, self.size))
        else:
            # Fallback to parent class hash if checksum unavailable
            return super().__hash__()
    
    def __str__(self):
        """String representation including checksum."""
        base_str = super().__str__()
        checksum_str = self.checksum[:8] + "..." if self.checksum else "None"
        return f"{base_str}, checksum=[{checksum_str}]"
