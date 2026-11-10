"""contact sheet of stills: python scripts/eiffel_sheet.py out.jpg dir prefix [cols] [width]"""
import sys, glob, os, re
from PIL import Image, ImageDraw
out, d, pre = sys.argv[1:4]; cols = int(sys.argv[4]) if len(sys.argv) > 4 else 7; W = int(sys.argv[5]) if len(sys.argv) > 5 else 270
fs = sorted(glob.glob(os.path.join(d, pre + '*.jpg')), key=lambda p: int(re.findall(r'(\d+)\.jpg$', p)[0]))
ims = [Image.open(f).convert('RGB') for f in fs]
H = int(W * 16 / 9); rows = (len(ims) + cols - 1) // cols
sheet = Image.new('RGB', (cols * W, rows * H), 'black'); dr = ImageDraw.Draw(sheet)
for i, (f, im) in enumerate(zip(fs, ims)):
    x, y = (i % cols) * W, (i // cols) * H
    sheet.paste(im.resize((W, H)), (x, y))
    dr.rectangle([x, y, x + 60, y + 18], fill='black'); dr.text((x + 3, y + 3), re.findall(r'(\d+)\.jpg$', f)[0], fill='yellow')
sheet.save(out, quality=88)
print(out, len(ims))
