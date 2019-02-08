import glob
import os
import sys

class ImageData:
    def __init__(self, path=None, date=None, size=None):
        self.path = path
        self.date = date
        self.size = size

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ImageData):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self.path == other.path and self.date == other.date and self.size == other.size

    def __str__(self):
        return 'path:[' + self.path + '], date=[' + str(self.date) + '], size=[' + str(self.size) + ']'

    def __hash__(self) -> int:
        return super().__hash__()

files = set()
root_dir = sys.argv[1]
ext = sys.argv[2]
path_mask =  root_dir+ '/**/*.' + ext

for filename in glob.iglob(path_mask, recursive=True):
    statinfo = os.stat(filename)
    files.add(ImageData(filename, statinfo.st_ctime, statinfo.st_size))
print(len(files))
for item in files:
    print(item)