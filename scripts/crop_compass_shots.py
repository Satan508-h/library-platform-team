"""把 Compass 截图裁到窗口内容区，去掉桌面壁纸边缘。"""
import glob
import os
from PIL import Image

D = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "截图")
BOX = (5, 9, 1047, 667)

for p in sorted(glob.glob(os.path.join(D, "compass_*.png"))):
    im = Image.open(p).convert("RGB")
    im = im.crop(BOX)
    im.convert("P", palette=Image.ADAPTIVE, colors=256).save(p, optimize=True)
    print(os.path.basename(p), im.size, os.path.getsize(p) // 1024, "KB")
