from PIL import Image
from PIL.ExifTags import TAGS
import io

def create_image(path, date_str=None):
    img = Image.new('RGB', (60, 30), color = 'red')
    
    if date_str:
        # Minimal EXIF header injection (this is tricky manually, simpler to just rely on unique content for now or skip complex EXIF gen if not needed deeply)
        # Actually, let's just create valid images first to test the validation logic.
        pass
        
    img.save(path)

import shutil
import os

if __name__ == "__main__":
    if not os.path.exists("tmp_test/A"): os.makedirs("tmp_test/A")
    if not os.path.exists("tmp_test/B"): os.makedirs("tmp_test/B")

    create_image("tmp_test/A/valid_image.jpg")
    
    # Use copy2 to preserve mtime so it counts as a duplicate in our fallback logic
    shutil.copy2("tmp_test/A/valid_image.jpg", "tmp_test/B/valid_image.jpg")
    
    with open("tmp_test/A/not_an_image.jpg", "w") as f:
        f.write("I am just text")
