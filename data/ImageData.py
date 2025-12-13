import glob
import os
import sys
import concurrent.futures
from functools import reduce
from PIL import Image, UnidentifiedImageError
from PIL.ExifTags import TAGS

class ProcessingCancelled(Exception):
    pass

def collect_paths(root_dir, ext, visited_paths, controller=None):
    paths = []
    path_mask = root_dir + '/**/*.' + ext
    print(f"Scanning root: {root_dir}")
    for path in glob.iglob(path_mask, recursive=True):
        if controller:
            controller.check()
            
        abs_path = os.path.abspath(path)
        if not os.path.isfile(abs_path):
            continue
        if abs_path in visited_paths:
            continue
        visited_paths.add(abs_path)
        paths.append(abs_path)
    return paths

def process_image(abs_path, controller=None):
    if controller:
        controller.check()
        
    try:
        with Image.open(abs_path) as img:
            exif_date = None
            try:
                exif_data = img._getexif()
                if exif_data:
                    for tag, value in exif_data.items():
                        if TAGS.get(tag) == 'DateTimeOriginal':
                            exif_date = value
                            break
            except Exception:
                pass # EXIF extraction failed, treat as None

            statinfo = os.stat(abs_path)
            return ImageData(abs_path, statinfo.st_mtime, statinfo.st_size, os.path.basename(abs_path), exif_date)
    except UnidentifiedImageError:
        return None # Not a valid image
    except Exception as e:
        print(f"Error processing {abs_path}: {e}")
        return None

class ImageData:
    def __init__(self, path=None, date=None, size=None, filename=None, exif_date=None):
        self.path = path
        self.date = date
        self.size = size
        self.filename = filename
        self.exif_date = exif_date

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ImageData):
            return NotImplemented
        elif self is other:
            return True
        else:
            # If both have EXIF date, prioritize that for equality check alongside size
            if self.exif_date and other.exif_date:
                 return self.exif_date == other.exif_date and self.size == other.size
            
            # Fallback to loose filename/date match if EXIF missing
            return self.filename == other.filename and self.date == other.date and self.size == other.size

    def __str__(self):
        return 'file:[' + self.filename + '], path:[' + self.path + '], date=[' + str(self.date) + '], size=[' + str(
            self.size) + '], exif_date=[' + str(self.exif_date) + ']'

    def __hash__(self) -> int:
        # Use EXIF date in hash if available, otherwise FS date
        date_key = self.exif_date if self.exif_date else self.date
        # Include filename in hash ONLY if we don't have EXIF. 
        # Rationale: Duplicate images might be renamed. If they have same EXIF date + Size, they are likely dupes.
        # But to be safe and stick to previous logic:
        return hash((date_key, self.size, self.filename))


def find_duplicates(roots, ext, progress_callback=None, controller=None):
    visited_paths = set()
    all_paths = []
    
    # Step 1: Collect all paths (fast)
    for root_dir in roots:
        if controller: controller.check()
        all_paths.extend(collect_paths(root_dir, ext, visited_paths, controller))

    total_files = len(all_paths)
    all_files = []
    
    # Step 2: Process images (parallel)
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Submit all tasks
        futures = {executor.submit(process_image, path, controller): path for path in all_paths}
        
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            if controller: controller.check()
            
            if progress_callback:
                progress_callback(i + 1, total_files) # i is 0-indexed
            
            try:
                img_data = future.result()
                if img_data:
                    all_files.append(img_data)
            except Exception as exc:
                print(f'Generated an exception: {exc}')
            
    if progress_callback:
        progress_callback(total_files, total_files)

    found_files = {}

    for img in all_files:
        if img in found_files:
            found_files[img].add(img.path)
        else:
            found_files[img] = {img.path}

    duplicates = {}
    uniques = []

    for img_key, paths in found_files.items():
        if len(paths) > 1:
            duplicates[img_key] = paths
        else:
            uniques.append(img_key)
            
    return uniques, duplicates

def main(roots, ext):
    uniques, duplicates = find_duplicates(roots, ext)

    print(f"--- Uniques: {len(uniques)} ---")
    # for item in uniques:
    #     exif_info = f" [EXIF: {item.exif_date}]" if item.exif_date else " [No EXIF]"
    #     print(f"{item.path}{exif_info}")

    print("\n--- Duplicates ---")
    for img_key, paths in duplicates.items():
        exif_info = f" [EXIF: {img_key.exif_date}]" if img_key.exif_date else " [No EXIF]"
        print(f"Duplicate Group ({len(paths)} files): {img_key.filename} (Size: {img_key.size}){exif_info}")
        for p in paths:
             print(f"  {p}")

if __name__ == "__main__":
    roots = sys.argv[2:]
    ext = sys.argv[1]
    main(roots, ext)
