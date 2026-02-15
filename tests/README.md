# ScannerService Unit Tests

## Overview
Comprehensive test suite for the `ScannerService` class with 22 unit tests covering all major functionality.

## Test Coverage

### 1. Basic Scanner Functionality (5 tests)
- **Initialization**: Verifies service initializes with correct default state
- **Cancel**: Tests cancellation mechanism
- **Pause/Resume**: Tests pause and resume functionality
- **Check on Cancel**: Verifies ProcessingCancelled exception is raised when cancelled
- **Check on Pause**: Verifies that check() blocks when paused and resumes correctly

### 2. Main Scan Method (7 tests)
- **Single folder, no duplicates**: Basic scan with unique images
- **Single folder, with duplicates**: Scan detecting duplicates within a folder
- **Multiple extensions**: Handling multiple file extensions (jpg, png, gif)
- **Checksum mode**: Verifies checksum-based detection works correctly
- **Progress callback**: Tests progress reporting mechanism
- **Log callback**: Tests logging functionality
- **Scan with callbacks**: Tests that all callbacks are invoked correctly

### 3. Cross-Folder Duplicate Detection (2 tests)
- **Cross-folder duplicates**: Detects when the same image appears in different folders
- **Merge existing duplicates**: Merges duplicate groups from multiple folders

### 4. Merge Scan Feature (3 tests)
- **Filter against base result**: Tests filtering new scan results against previously saved results
- **Filter with empty base**: Verifies behavior when base result is empty
- **Filter logs correctly**: Ensures proper logging during merge operations

### 5. Parallel Scanning (2 tests)
- **Parallel execution**: Verifies multiple folders are scanned in parallel (performance test)
- **Error handling**: Confirms errors in one folder don't stop other folders from processing

### 6. Cancellation During Scanning (1 test)
- **Cancel during scan**: Tests that long-running scans can be cancelled mid-execution

### 7. Edge Cases (3 tests)
- **Empty folder list**: Handles empty input gracefully
- **Single extension as string**: Handles both string and list input for extensions
- **No callbacks**: Scans work correctly without callbacks

## Running the Tests

### Run all tests:
```powershell
py -m unittest tests.test_scanner_service -v
```

### Run specific test class:
```powershell
py -m unittest tests.test_scanner_service.TestScanMethod -v
```

### Run a single test:
```powershell
py -m unittest tests.test_scanner_service.TestScanMethod.test_single_folder_scan_no_duplicates -v
```

## Test Results
All 22 tests passing ✅

## Key Testing Techniques Used

1. **Mocking**: Uses `unittest.mock.patch` to mock `ImageData.find_duplicates`
2. **Threading**: Tests pause/resume and cancellation with background threads
3. **Side Effects**: Uses `side_effect` to simulate different behaviors per folder
4. **Callbacks**: Captures callback invocations to verify logging and progress
5. **Fixtures**: Uses `setUp()` to create consistent test data

## Test Data
Tests use realistic `ImageData` objects with:
- Numeric timestamps (Unix epoch format)
- Different sizes and filenames
- Proper hash/equality semantics

## Future Improvements
- Add integration tests with actual file system
- Add performance benchmarks
- Test with very large folder lists
- Add tests for memory usage during parallel scanning
