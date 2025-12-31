import json
import os
from typing import Dict, List, Set, Tuple
from . import ImageData as ImgData


class ScanResultStorage:
    """Manages persistent storage of duplicate scan results in JSON format."""
    
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
    def save_results(uniques: List, duplicates: Dict, filepath: str = None) -> bool:
        """
        Save scan results to JSON file.
        
        Args:
            uniques: List of unique ImageData objects
            duplicates: Dict mapping ImageData to set of file paths
            filepath: Path to save file (uses default if None)
            
        Returns:
            True if save successful, False otherwise
        """
        if filepath is None:
            filepath = ScanResultStorage.DEFAULT_STORAGE_PATH
        
        try:
            # Prepare data structure for JSON
            data = {
                'version': '1.0',
                'uniques': [],
                'duplicates': []
            }
            
            # Serialize uniques
            for img in uniques:
                data['uniques'].append({
                    'image_data': ScanResultStorage._serialize_image_data(img),
                    'paths': [img.path]  # Unique items have single path
                })
            
            # Serialize duplicates
            for img_data, paths in duplicates.items():
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
    def load_results(filepath: str = None) -> Tuple[List, Dict]:
        """
        Load scan results from JSON file.
        
        Args:
            filepath: Path to load file (uses default if None)
            
        Returns:
            Tuple of (uniques_list, duplicates_dict)
            Returns ([], {}) if file doesn't exist or is corrupted
        """
        if filepath is None:
            filepath = ScanResultStorage.DEFAULT_STORAGE_PATH
        
        # Check if file exists
        if not os.path.exists(filepath):
            print(f"Storage file not found: {filepath}")
            return [], {}
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Validate version (for future compatibility)
            version = data.get('version', '1.0')
            if version != '1.0':
                print(f"Warning: Storage version {version} may not be fully compatible")
            
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
            
            return uniques, duplicates
            
        except json.JSONDecodeError as e:
            print(f"Error: Corrupted storage file (invalid JSON): {e}")
            return [], {}
        except Exception as e:
            print(f"Error loading results from storage: {e}")
            return [], {}
    
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
