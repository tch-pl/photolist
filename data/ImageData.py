import glob
import os
import sys
from functools import reduce
from multiprocessing.dummy import Pool as ThreadPool
from PIL import Image, UnidentifiedImageError
from PIL.ExifTags import TAGS

def getFiles(root_dir, ext, visited_paths):
    files = []
    path_mask = root_dir + '/**/*.' + ext
    print(f"Processing root: {root_dir}")
    for path in glob.iglob(path_mask, recursive=True):
        abs_path = os.path.abspath(path)
        if not os.path.isfile(abs_path):
            continue
        if abs_path in visited_paths:
            continue
        visited_paths.add(abs_path)
        
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
                files.append(ImageData(abs_path, statinfo.st_mtime, statinfo.st_size, os.path.basename(abs_path), exif_date))
        except UnidentifiedImageError:
            # Not a valid image, skip it
            continue
        except Exception as e:
            print(f"Error processing {abs_path}: {e}")
            continue

    return files

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


roots = sys.argv[2:]
ext = sys.argv[1]

visited_paths = set()
all_files = []

for root_dir in roots:
    all_files.extend(getFiles(root_dir, ext, visited_paths))

found_files = {}

for img in all_files:
    if img in found_files:
        found_files[img].append(img)
    else:
        found_files[img] = [img]

duplicates = []
uniques = []

for img_list in found_files.values():
    if len(img_list) > 1:
        duplicates.extend(img_list)
    else:
        uniques.extend(img_list)

print("--- Uniques ---")
for item in uniques:
    exif_info = f" [EXIF: {item.exif_date}]" if item.exif_date else " [No EXIF]"
    print(f"{item.path}{exif_info}")

print("\n--- Duplicates ---")
for item in duplicates:
    exif_info = f" [EXIF: {item.exif_date}]" if item.exif_date else " [No EXIF]"
    print(f"{item.path}{exif_info}")

# for item in no_duplicates:
#      print(item.path)
