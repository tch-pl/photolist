
import json
import os
from typing import Dict, List, Set, Tuple, Optional
from . import ImageData as ImgData
from .ScanResult import ScanResult

class ScanResultStorage:
    """Manages persistent storage of ScanResult objects in JSON format."""
    
    DEFAULT_STORAGE_PATH = os.path.join(os.path.dirname(__file__), 'scan_results.json')
    
    @staticmethod
    def _serialize_image_data(img_data):
        """Convert ImageData object to dictionary for JSON serialization."""
        data = {
            'path': img_data.path,
            'date': img_data.date,
            'size': img_data.size,
            'filename': img_data.filename,
            'exif_date': img_data.exif_date
        }
        
        # Include checksum if available (for ChecksumImageData)
        if hasattr(img_data, '_checksum') and img_data._checksum is not None:
            data['checksum'] = img_data._checksum
        
        return data
    
    @staticmethod
    def _deserialize_image_data(data_dict):
        """Create ImageData or ChecksumImageData object from dictionary."""
        # Check if this is checksum-based data
        if 'checksum' in data_dict and data_dict['checksum'] is not None:
            from .ChecksumImageData import ChecksumImageData
            return ChecksumImageData(
                path=data_dict.get('path'),
                date=data_dict.get('date'),
                size=data_dict.get('size'),
                filename=data_dict.get('filename'),
                exif_date=data_dict.get('exif_date'),
                checksum=data_dict.get('checksum')
            )
        else:
            # Legacy format or metadata-based
            return ImgData.ImageData(
                path=data_dict.get('path'),
                date=data_dict.get('date'),
                size=data_dict.get('size'),
                filename=data_dict.get('filename'),
                exif_date=data_dict.get('exif_date')
            )
    
    @staticmethod
    def save_results(scan_result: ScanResult, filepath: str = None) -> bool:
        """
        Save ScanResult to JSON file.
        
        Args:
            scan_result: ScanResult object to save
            filepath: Path to save file (uses default if None)
            
        Returns:
            True if save successful, False otherwise
        """
        if filepath is None:
            filepath = ScanResultStorage.DEFAULT_STORAGE_PATH
        
        try:
            # Prepare data structure for JSON
            data = {
                'version': '2.0', # Version bumped for ScanResult support
                'metadata': {
                    'timestamp': scan_result.timestamp,
                    'scanned_paths': scan_result.scanned_paths,
                    'extension': scan_result.extension,
                    'detection_mode': scan_result.detection_mode
                },
                'uniques': [],
                'duplicates': []
            }
            
            # Serialize uniques
            for img in scan_result.uniques:
                data['uniques'].append({
                    'image_data': ScanResultStorage._serialize_image_data(img),
                    'paths': [img.path]  # Unique items have single path
                })
            
            # Serialize duplicates
            for img_data, paths in scan_result.duplicates.items():
                data['duplicates'].append({
                    'image_data': ScanResultStorage._serialize_image_data(img_data),
                    'paths': list(paths)  # Convert set to list for JSON
                })
            
            # Write to file with pretty formatting for readability
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"Error saving results to storage: {e}")
            return False
    
    @staticmethod
    def load_results(filepath: str = None) -> Optional[ScanResult]:
        """
        Load ScanResult from JSON file.
        
        Args:
            filepath: Path to load file (uses default if None)
            
        Returns:
            ScanResult object, or None if file doesn't exist or is corrupted
        """
        if filepath is None:
            filepath = ScanResultStorage.DEFAULT_STORAGE_PATH
        
        # Check if file exists
        if not os.path.exists(filepath):
            print(f"Storage file not found: {filepath}")
            return None
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            version = data.get('version', '1.0')
            
            # Deserialize uniques
            uniques = []
            for item in data.get('uniques', []):
                img_data = ScanResultStorage._deserialize_image_data(item['image_data'])
                uniques.append(img_data)
            
            # Deserialize duplicates
            duplicates = {}
            for item in data.get('duplicates', []):
                img_data = ScanResultStorage._deserialize_image_data(item['image_data'])
                paths = set(item['paths'])  # Convert list back to set
                duplicates[img_data] = paths
                
            # Handle metadata (Version 1.0 compatibility: Default values)
            metadata = data.get('metadata', {})
            
            scan_result = ScanResult(
                uniques=uniques,
                duplicates=duplicates,
                scanned_paths=metadata.get('scanned_paths', []),
                extension=metadata.get('extension', ''),
                detection_mode=metadata.get('detection_mode', 'unknown'),
                timestamp=metadata.get('timestamp', None)
            )
            
            return scan_result
            
        except json.JSONDecodeError as e:
            print(f"Error: Corrupted storage file (invalid JSON): {e}")
            return None
        except Exception as e:
            print(f"Error loading results from storage: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def clear_storage(filepath: str = None) -> bool:
        """
        Delete the storage file.
        
        Args:
            filepath: Path to storage file (uses default if None)
            
        Returns:
            True if deletion successful or file doesn't exist, False otherwise
        """
        if filepath is None:
            filepath = ScanResultStorage.DEFAULT_STORAGE_PATH
        
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
            return True
        except Exception as e:
            print(f"Error clearing storage: {e}")
            return False
    
    @staticmethod
    def storage_exists(filepath: str = None) -> bool:
        """
        Check if storage file exists.
        
        Args:
            filepath: Path to storage file (uses default if None)
            
        Returns:
            True if file exists, False otherwise
        """
        if filepath is None:
            filepath = ScanResultStorage.DEFAULT_STORAGE_PATH
        
        return os.path.exists(filepath)
