import glob
import os
import sys
from functools import reduce
from multiprocessing.dummy import Pool as ThreadPool
def getFiles(root_dir, ext):
    files = set()
    path_mask = root_dir + '/**/*.' + ext
    print(root_dir)
    for path in glob.iglob(path_mask, recursive=True):
        statinfo = os.stat(path)
        files.add(ImageData(path, statinfo.st_mtime, statinfo.st_size, os.path.basename(path)))
    return files

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
        return 'file:[' + self.filename + '], path:[' + self.path + '], date=[' + str(self.date) + '], size=[' + str(
            self.size) + ']'

    def __hash__(self) -> int:
        return hash((self.date, self.size, self.filename))


roots = sys.argv[2:]
ext = sys.argv[1]

albums = []
# pool = ThreadPool(4)
# results = pool.apply_async(getFiles, (roots, ext))
for num, root_dir in enumerate(roots):
    # files = set()
    # path_mask = root_dir + '/**/*.' + ext
    # print(root_dir)
    # for path in glob.iglob(path_mask, recursive=True):
    #     statinfo = os.stat(path)
    #     files.add(ImageData(path, statinfo.st_mtime, statinfo.st_size, os.path.basename(path)))
    albums.append(getFiles(root_dir, ext))
no_duplicates = set()
for album in albums:
    no_duplicates.update(album)

# print(len(no_duplicates))

total_size = reduce((lambda x, i: i + x), list(map(lambda s: s.size, no_duplicates)))
MBFACTOR = float(1<<20)
print(total_size/MBFACTOR)

# for item in no_duplicates:
#      print(item.path)
