import glob
import os
import sys


class ImageData:
    def __init__(self, path=None, date=None, size=None, filename=None):
        self.path = path
        self.date = date
        self.size = size
        self.filename = filename

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ImageData):
            return NotImplemented
        elif self is other:
            return True
        else:
            return self.filename == other.filename and self.date == other.date and self.size == other.size

    def __str__(self):
        return 'file:[' + self.filename + '], path:[' + self.path + '], date=[' + str(self.date) + '], size=[' + str(self.size) + ']'

    def __hash__(self) -> int:
        print(self)
        print (hash((self.date, self.size, self.filename)))
        return hash((self.date, self.size, self.filename))


roots = sys.argv[2:]
ext = sys.argv[1]

albums = []
for num, root_dir in enumerate(roots):
    files = set()
    path_mask = root_dir + '/**/*.' + ext
    print(root_dir)
    for path in glob.iglob(path_mask, recursive=True):
        statinfo = os.stat(path)
        files.add(ImageData(path, statinfo.st_mtime, statinfo.st_size, os.path.basename(path)))
    albums.append(files)

no_duplicates = set()
for album in albums:
    no_duplicates.update(album)

print(len(no_duplicates))

# for item in no_duplicates:
#     print(item)
