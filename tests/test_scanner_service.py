"""
Unit tests for ScannerService.

Tests cover:
- Basic scan functionality
- Parallel folder scanning
- Cross-folder duplicate detection
- Merge scan feature (filtering against base results)
- Cancellation and pause functionality
- Progress and logging callbacks
- Edge cases and error handling
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, call
import threading
from typing import List, Dict, Set

import sys
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.ScannerService import ScannerService
from data.ImageData import ImageData, ProcessingCancelled
from data.ScanResult import ScanResult


class TestScannerService(unittest.TestCase):
    """Test cases for ScannerService class."""
    
    def setUp(self):
        """Set up test fixtures before each test."""
        self.service = ScannerService()
        
        # Create mock ImageData objects with numeric timestamps
        self.img1 = ImageData(path="/path/img1.jpg", date=1704067200, size=1000, filename="img1.jpg")
        self.img2 = ImageData(path="/path/img2.jpg", date=1704153600, size=2000, filename="img2.jpg")
        self.img3 = ImageData(path="/path/img3.jpg", date=1704240000, size=3000, filename="img3.jpg")
        self.img4 = ImageData(path="/path/img4.jpg", date=1704326400, size=4000, filename="img4.jpg")
        
    def tearDown(self):
        """Clean up after each test."""
        self.service = None


class TestBasicScannerFunctionality(TestScannerService):
    """Test basic scanner service functionality."""
    
    def test_initialization(self):
        """Test that ScannerService initializes correctly."""
        self.assertFalse(self.service.is_cancelled())
        self.assertFalse(self.service.is_paused())
    
    def test_cancel(self):
        """Test cancel functionality."""
        self.service.cancel()
        self.assertTrue(self.service.is_cancelled())
    
    def test_pause_resume(self):
        """Test pause and resume functionality."""
        self.assertFalse(self.service.is_paused())
        
        self.service.pause()
        self.assertTrue(self.service.is_paused())
        
        self.service.resume()
        self.assertFalse(self.service.is_paused())
    
    def test_check_raises_on_cancel(self):
        """Test that check() raises ProcessingCancelled when cancelled."""
        self.service.cancel()
        with self.assertRaises(ProcessingCancelled):
            self.service.check()
    
    def test_check_waits_on_pause(self):
        """Test that check() waits when paused."""
        self.service.pause()
        
        # Test check in a separate thread
        check_completed = threading.Event()
        exception_raised = [None]
        
        def run_check():
            try:
                # This should block
                self.service.check()
                check_completed.set()
            except Exception as e:
                exception_raised[0] = e
        
        thread = threading.Thread(target=run_check)
        thread.start()
        
        # Give it a moment to enter the pause loop
        import time
        time.sleep(0.2)
        
        # Should still be waiting
        self.assertFalse(check_completed.is_set())
        
        # Resume and it should complete
        self.service.resume()
        thread.join(timeout=1)
        
        self.assertTrue(check_completed.is_set())
        self.assertIsNone(exception_raised[0])


class TestScanMethod(TestScannerService):
    """Test the main scan method."""
    
    @patch('services.ScannerService.ImageData.find_duplicates')
    def test_single_folder_scan_no_duplicates(self, mock_find_duplicates):
        """Test scanning a single folder with no duplicates."""
        # Mock find_duplicates to return some unique files
        mock_find_duplicates.return_value = ([self.img1, self.img2], {})
        
        result = self.service.scan(
            folders=['/test/folder1'],
            ext='jpg',
            use_checksum=False
        )
        
        self.assertIsInstance(result, ScanResult)
        self.assertEqual(len(result.uniques), 2)
        self.assertEqual(len(result.duplicates), 0)
        self.assertEqual(result.scanned_paths, ['/test/folder1'])
        self.assertEqual(result.extension, 'jpg')
        self.assertEqual(result.detection_mode, 'metadata')
    
    @patch('services.ScannerService.ImageData.find_duplicates')
    def test_single_folder_scan_with_duplicates(self, mock_find_duplicates):
        """Test scanning a single folder with duplicates."""
        # Mock find_duplicates to return duplicates
        duplicates = {
            self.img1: {'/path/img1.jpg', '/path/img1_copy.jpg'}
        }
        mock_find_duplicates.return_value = ([self.img2], duplicates)
        
        result = self.service.scan(
            folders=['/test/folder1'],
            ext='jpg'
        )
        
        self.assertEqual(len(result.uniques), 1)
        self.assertEqual(len(result.duplicates), 1)
        self.assertIn(self.img1, result.duplicates)
    
    @patch('services.ScannerService.ImageData.find_duplicates')
    def test_multiple_extensions(self, mock_find_duplicates):
        """Test scanning with multiple file extensions."""
        mock_find_duplicates.return_value = ([self.img1], {})
        
        result = self.service.scan(
            folders=['/test/folder1'],
            ext=['jpg', 'png', 'gif']
        )
        
        # Check that find_duplicates was called with the list of extensions
        call_args = mock_find_duplicates.call_args
        self.assertEqual(call_args[0][1], ['jpg', 'png', 'gif'])
        self.assertEqual(result.extension, 'jpg, png, gif')
    
    @patch('services.ScannerService.ImageData.find_duplicates')
    def test_checksum_mode(self, mock_find_duplicates):
        """Test scanning with checksum mode enabled."""
        mock_find_duplicates.return_value = ([self.img1], {})
        
        result = self.service.scan(
            folders=['/test/folder1'],
            ext='jpg',
            use_checksum=True
        )
        
        # Verify checksum flag was passed
        call_args = mock_find_duplicates.call_args
        self.assertTrue(call_args[1]['use_checksum'])
        self.assertEqual(result.detection_mode, 'checksum')
    
    @patch('services.ScannerService.ImageData.find_duplicates')
    def test_progress_callback(self, mock_find_duplicates):
        """Test that progress callback is called correctly."""
        mock_find_duplicates.return_value = ([self.img1], {})
        
        progress_calls = []
        def progress_cb(msg, current, total):
            progress_calls.append((msg, current, total))
        
        self.service.scan(
            folders=['/test/folder1', '/test/folder2'],
            ext='jpg',
            progress_callback=progress_cb
        )
        
        # Should have progress updates for folder completion
        self.assertTrue(len(progress_calls) > 0)
        # Check last progress shows completion
        last_call = progress_calls[-1]
        self.assertEqual(last_call[1], last_call[2])  # current == total
    
    @patch('services.ScannerService.ImageData.find_duplicates')
    def test_log_callback(self, mock_find_duplicates):
        """Test that log callback is called correctly."""
        mock_find_duplicates.return_value = ([self.img1], {})
        
        log_messages = []
        def log_cb(msg):
            log_messages.append(msg)
        
        self.service.scan(
            folders=['/test/folder1'],
            ext='jpg',
            log_callback=log_cb
        )
        
        # Should have several log messages
        self.assertTrue(len(log_messages) > 0)
        self.assertTrue(any('Starting processing' in msg for msg in log_messages))
        self.assertTrue(any('Processing complete' in msg for msg in log_messages))


class TestCrossFolderDuplicateDetection(TestScannerService):
    """Test cross-folder duplicate detection (_merge_folder_results)."""
    
    @patch('services.ScannerService.ImageData.find_duplicates')
    def test_cross_folder_duplicate_detection(self, mock_find_duplicates):
        """Test that duplicates across folders are properly detected."""
        # Simulate two folders each having the same image content but different paths
        # After merging, it should be detected as a duplicate
        
        def find_duplicates_side_effect(folders, *args, **kwargs):
            if folders[0] == '/folder1':
                # folder1 has img1 and img2 as unique
                # Create copies with different paths
                img1_folder1 = ImageData(path="/folder1/img1.jpg", date=self.img1.date, size=self.img1.size, filename=self.img1.filename)
                return ([img1_folder1, self.img2], {})
            else:  # folder2
                # folder2 also has img1 (different path) and img3 as unique
                img1_folder2 = ImageData(path="/folder2/img1.jpg", date=self.img1.date, size=self.img1.size, filename=self.img1.filename)
                return ([img1_folder2, self.img3], {})
        
        mock_find_duplicates.side_effect = find_duplicates_side_effect
        
        result = self.service.scan(
            folders=['/folder1', '/folder2'],
            ext='jpg'
        )
        
        # img1 should now be in duplicates (found in both folders with different paths)
        # img2 and img3 should remain unique
        self.assertEqual(len(result.uniques), 2)
        self.assertEqual(len(result.duplicates), 1)
        # Check that there's one duplicate group with 2 paths
        self.assertEqual(len(result.duplicates), 1)
        duplicate_group = list(result.duplicates.values())[0]
        self.assertEqual(len(duplicate_group), 2)
    
    @patch('services.ScannerService.ImageData.find_duplicates')
    def test_merge_existing_duplicates(self, mock_find_duplicates):
        """Test that existing duplicates from different folders are merged."""
        # Both folders have img1 as duplicate
        duplicates1 = {self.img1: {'/folder1/img1_a.jpg', '/folder1/img1_b.jpg'}}
        duplicates2 = {self.img1: {'/folder2/img1_c.jpg'}}
        
        def find_duplicates_side_effect(folders, *args, **kwargs):
            if folders[0] == '/folder1':
                return ([], duplicates1)
            else:
                return ([], duplicates2)
        
        mock_find_duplicates.side_effect = find_duplicates_side_effect
        
        result = self.service.scan(
            folders=['/folder1', '/folder2'],
            ext='jpg'
        )
        
        # Should have one duplicate group with 3 paths
        self.assertEqual(len(result.duplicates), 1)
        self.assertIn(self.img1, result.duplicates)
        self.assertEqual(len(result.duplicates[self.img1]), 3)


class TestMergeScanFeature(TestScannerService):
    """Test merge scan feature (_filter_against_base)."""
    
    @patch('services.ScannerService.ImageData.find_duplicates')
    def test_filter_against_base_result(self, mock_find_duplicates):
        """Test that new scan results are filtered against base result."""
        # Create a base result with img1 and img2
        base_result = ScanResult(
            uniques=[self.img1],
            duplicates={self.img2: {'/base/img2_a.jpg', '/base/img2_b.jpg'}},
            scanned_paths=['/base/folder'],
            extension='jpg',
            detection_mode='metadata'
        )
        
        # New scan finds img1 (duplicate), img2 (duplicate), img3 (new unique), img4 (new duplicate)
        mock_find_duplicates.return_value = (
            [self.img1, self.img3],
            {self.img2: {'/new/img2_c.jpg'}, self.img4: {'/new/img4_a.jpg', '/new/img4_b.jpg'}}
        )
        
        result = self.service.scan(
            folders=['/new/folder'],
            ext='jpg',
            base_result=base_result
        )
        
        # Only img3 and img4 should be in the result (img1 and img2 filtered out)
        self.assertEqual(len(result.uniques), 1)
        self.assertIn(self.img3, result.uniques)
        
        self.assertEqual(len(result.duplicates), 1)
        self.assertIn(self.img4, result.duplicates)
        self.assertNotIn(self.img1, result.duplicates)
        self.assertNotIn(self.img2, result.duplicates)
    
    @patch('services.ScannerService.ImageData.find_duplicates')
    def test_filter_with_empty_base_result(self, mock_find_duplicates):
        """Test filtering with an empty base result."""
        base_result = ScanResult(
            uniques=[],
            duplicates={},
            scanned_paths=[],
            extension='jpg',
            detection_mode='metadata'
        )
        
        mock_find_duplicates.return_value = ([self.img1, self.img2], {})
        
        result = self.service.scan(
            folders=['/folder'],
            ext='jpg',
            base_result=base_result
        )
        
        # Nothing should be filtered
        self.assertEqual(len(result.uniques), 2)
    
    @patch('services.ScannerService.ImageData.find_duplicates')
    def test_filter_logs_correctly(self, mock_find_duplicates):
        """Test that filtering logs appropriate messages."""
        base_result = ScanResult(
            uniques=[self.img1],
            duplicates={},
            scanned_paths=['/base'],
            extension='jpg',
            detection_mode='metadata'
        )
        
        mock_find_duplicates.return_value = ([self.img1, self.img2], {})
        
        log_messages = []
        self.service.scan(
            folders=['/folder'],
            ext='jpg',
            base_result=base_result,
            log_callback=lambda msg: log_messages.append(msg)
        )
        
        # Should have logs about filtering
        self.assertTrue(any('Filtering results against base result' in msg for msg in log_messages))
        self.assertTrue(any('After filtering' in msg for msg in log_messages))


class TestParallelScanning(TestScannerService):
    """Test parallel folder scanning (_scan_folders_parallel)."""
    
    @patch('services.ScannerService.ImageData.find_duplicates')
    def test_parallel_execution(self, mock_find_duplicates):
        """Test that multiple folders are scanned in parallel."""
        # Track which folders were scanned
        scanned_folders = []
        
        def find_duplicates_tracker(folders, *args, **kwargs):
            scanned_folders.append(folders[0])
            # Simulate some work
            import time
            time.sleep(0.1)
            return ([self.img1], {})
        
        mock_find_duplicates.side_effect = find_duplicates_tracker
        
        import time
        start = time.time()
        
        self.service.scan(
            folders=['/folder1', '/folder2', '/folder3'],
            ext='jpg'
        )
        
        elapsed = time.time() - start
        
        # With 3 folders and 0.1s each, parallel should take ~0.1s not 0.3s
        # Allow some tolerance for threading overhead
        self.assertLess(elapsed, 0.25)
        self.assertEqual(len(scanned_folders), 3)
    
    @patch('services.ScannerService.ImageData.find_duplicates')
    def test_folder_error_handling(self, mock_find_duplicates):
        """Test that errors in one folder don't stop other folders."""
        def find_duplicates_with_error(folders, *args, **kwargs):
            if folders[0] == '/bad_folder':
                raise Exception("Simulated error")
            # Return img1 with different path for each good folder
            if folders[0] == '/good_folder':
                img = ImageData(path="/good_folder/img1.jpg", date=self.img1.date, size=self.img1.size, filename=self.img1.filename)
            else:
                img = ImageData(path="/another_good_folder/img1.jpg", date=self.img1.date, size=self.img1.size, filename=self.img1.filename)
            return ([img], {})
        
        mock_find_duplicates.side_effect = find_duplicates_with_error
        
        log_messages = []
        result = self.service.scan(
            folders=['/good_folder', '/bad_folder', '/another_good_folder'],
            ext='jpg',
            log_callback=lambda msg: log_messages.append(msg)
        )
        
        # Should have logged the error
        self.assertTrue(any('generated an exception' in msg for msg in log_messages))
        
        # Both good folders returned img1 with different paths, so they merge into 1 duplicate group
        self.assertEqual(len(result.duplicates), 1)
        self.assertEqual(len(list(result.duplicates.values())[0]), 2)  # 2 paths for the same image


class TestCancellationDuringScanning(TestScannerService):
    """Test cancellation functionality during scanning."""
    
    @patch('services.ScannerService.ImageData.find_duplicates')
    def test_cancel_during_scan(self, mock_find_duplicates):
        """Test that scan can be cancelled mid-execution."""
        
        def slow_find_duplicates(folders, *args, **kwargs):
            # Simulate slow operation
            import time
            time.sleep(0.5)
            return ([self.img1], {})
        
        mock_find_duplicates.side_effect = slow_find_duplicates
        
        # Start scan in a thread
        exception_raised = [None]
        
        def run_scan():
            try:
                self.service.scan(
                    folders=['/folder1', '/folder2'],
                    ext='jpg'
                )
            except ProcessingCancelled as e:
                exception_raised[0] = e
        
        thread = threading.Thread(target=run_scan)
        thread.start()
        
        # Cancel after a short delay
        import time
        time.sleep(0.1)
        self.service.cancel()
        
        thread.join(timeout=2)
        
        # Should have raised ProcessingCancelled
        self.assertIsInstance(exception_raised[0], ProcessingCancelled)


class TestEdgeCases(TestScannerService):
    """Test edge cases and boundary conditions."""
    
    @patch('services.ScannerService.ImageData.find_duplicates')
    def test_empty_folder_list(self, mock_find_duplicates):
        """Test scanning with an empty folder list."""
        mock_find_duplicates.return_value = ([], {})
        
        result = self.service.scan(
            folders=[],
            ext='jpg'
        )
        
        self.assertEqual(len(result.uniques), 0)
        self.assertEqual(len(result.duplicates), 0)
    
    @patch('services.ScannerService.ImageData.find_duplicates')
    def test_single_extension_as_string(self, mock_find_duplicates):
        """Test that single extension as string is handled correctly."""
        mock_find_duplicates.return_value = ([self.img1], {})
        
        result = self.service.scan(
            folders=['/folder'],
            ext='jpg'  # String, not list
        )
        
        # Should be converted to list internally
        call_args = mock_find_duplicates.call_args
        self.assertEqual(call_args[0][1], ['jpg'])
        self.assertEqual(result.extension, 'jpg')
    
    @patch('services.ScannerService.ImageData.find_duplicates')
    def test_no_callbacks(self, mock_find_duplicates):
        """Test scanning without progress or log callbacks."""
        mock_find_duplicates.return_value = ([self.img1], {})
        
        # Should not raise any errors
        result = self.service.scan(
            folders=['/folder'],
            ext='jpg',
            progress_callback=None,
            log_callback=None
        )
        
        self.assertIsNotNone(result)


if __name__ == '__main__':
    unittest.main()
