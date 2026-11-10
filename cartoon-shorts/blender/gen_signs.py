"""Sign and crowd textures for the Blender marathon sets (PIL; Arial Black like the three.js signs).
    python blender/gen_signs.py <outDir>"""
import os, sys, random
from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
FB = "C:/Windows/Fonts/ariblk.ttf"


def sign(name, w, h, bg, fg, lines, border=True):
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    if border:
        b = max(8, int(h * 0.04))
        d.rectangle((b, b, w - b - 1, h - b - 1), outline=fg, width=b)
    total = sum(s for _, s in lines) * 1.12
    y = (h - total) / 2
    for text, size in lines:
        f = ImageFont.truetype(FB, size)
        tw = d.textlength(text, font=f)
        while tw > w * 0.9:
            size = int(size * 0.92); f = ImageFont.truetype(FB, size); tw = d.textlength(text, font=f)
        d.text(((w - tw) / 2, y), text, font=f, fill=fg)
        y += size * 1.12
    im.save(os.path.join(OUT, name + ".png"))


sign("water", 800, 520, "#f4f1ea", "#1f2a44", [("WATER STOP", 96), ("1 OF 1", 170)])
sign("mile9", 640, 360, "#f4f1ea", "#1f2a44", [("MILE 9", 150)])
sign("mile19", 640, 360, "#f4f1ea", "#1f2a44", [("MILE 19", 150)])
sign("boston", 1500, 400, "#f4f1ea", "#1f2a44", [("BOSTON MARATHON", 118), ("1905", 120)])
sign("finish", 1200, 260, "#f4f1ea", "#c0353a", [("FINISH", 170)])
sign("games", 2400, 260, "#1f2a44", "#f2c230", [("OLYMPIC GAMES  ST. LOUIS 1904", 150)])

# painted grandstand crowd: rows of little hats and faces (tiles horizontally)
rnd = random.Random(7)
W, H = 2048, 512
im = Image.new("RGB", (W, H), "#7a5a3c")
d = ImageDraw.Draw(im)
skins = ["#f5c9a0", "#e0b48a", "#c98e64", "#7a4e34", "#ffe2c2"]
cloth = ["#3f6fb5", "#c0353a", "#f2c230", "#4fa36a", "#f4f1ea", "#8a5ab8", "#2f3a5a", "#e07a32"]
hats = ["#2e2a36", "#f4f1ea", "#c9a35a", "#5a3b2a", "#8c3b4a"]
for row in range(8):
    y = 30 + row * 60
    d.rectangle((0, y + 34, W, y + 44), fill="#5e4027")
    for x in range(10 + (row % 2) * 30, W, 58 + rnd.randint(0, 10)):
        c = rnd.choice(cloth)
        d.ellipse((x - 20, y + 10, x + 20, y + 62), fill=c, outline="#241726", width=3)
        d.ellipse((x - 15, y - 14, x + 15, y + 16), fill=rnd.choice(skins), outline="#241726", width=3)
        d.ellipse((x - 7, y - 3, x - 3, y + 1), fill="#241726"); d.ellipse((x + 3, y - 3, x + 7, y + 1), fill="#241726")
        d.arc((x - 6, y + 2, x + 6, y + 10), 0, 180, fill="#241726", width=2)
        if rnd.random() < 0.7:
            hc = rnd.choice(hats)
            d.ellipse((x - 20, y - 14, x + 20, y - 6), fill=hc, outline="#241726", width=2)
            d.rectangle((x - 12, y - 28, x + 12, y - 10), fill=hc, outline="#241726", width=2)
        if rnd.random() < 0.35:  # waving arm
            d.line((x + 18, y + 24, x + 30, y - 6), fill="#241726", width=4)
im.save(os.path.join(OUT, "crowd.png"))

# brick facade (Boston 1905 blocks) with windows
for k, col in enumerate(["#b5573f", "#a24a36", "#c9744f"]):
    im = Image.new("RGB", (512, 512), col)
    d = ImageDraw.Draw(im)
    for y in range(0, 512, 16):
        for x in range(-16 if (y // 16) % 2 else 0, 512, 32):
            d.rectangle((x + 1, y + 1, x + 30, y + 14), outline="#7a3424")
    for fl in range(3):
        for i in range(4):
            d.rectangle((40 + i * 120, 60 + fl * 150, 100 + i * 120, 150 + fl * 150), fill="#2c3a52", outline="#efe3c8", width=6)
            d.rectangle((34 + i * 120, 150 + fl * 150, 106 + i * 120, 160 + fl * 150), fill="#efe3c8")
    im.save(os.path.join(OUT, f"brick{k}.png"))

# US flag
im = Image.new("RGB", (320, 200), "#f4f1ea"); d = ImageDraw.Draw(im)
for i in range(13):
    if i % 2 == 0: d.rectangle((0, i * 200 / 13, 320, (i + 1) * 200 / 13), fill="#c8352f")
d.rectangle((0, 0, 140, 108), fill="#2a3f7a")
for r in range(5):
    for c in range(6):
        x, y = 14 + c * 22 + (r % 2) * 6, 12 + r * 21; d.ellipse((x - 4, y - 4, x + 4, y + 4), fill="#f4f1ea")
im.save(os.path.join(OUT, "usflag.png"))
print("signs ->", OUT)
