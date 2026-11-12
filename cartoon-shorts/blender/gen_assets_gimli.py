"""Printed textures for the Gimli Glider sets (livery, signs, banners, cockpit screens), written to out/gimli/assets/.
    python blender/gen_assets_gimli.py
All lettering is our own; no logos are copied (the airline title is plain bold type, the tail a simple maple leaf)."""
import math, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out", "gimli", "assets")
os.makedirs(OUT, exist_ok=True)
F = lambda name, size: ImageFont.truetype(os.path.join("C:/Windows/Fonts", name), size)  # noqa: E731


def save(im, name):
    im.save(os.path.join(OUT, name)); print("->", name, im.size)


def text_c(d, box, txt, font, fill, stroke=0, sfill=None):
    x0, y0, x1, y1 = box
    l, t, r, b = d.textbbox((0, 0), txt, font=font, stroke_width=stroke)
    d.text(((x0 + x1 - (r - l)) / 2 - l, (y0 + y1 - (b - t)) / 2 - t), txt, font=font, fill=fill, stroke_width=stroke, stroke_fill=sfill)


def leaf(d, cx, cy, s, fill):
    """a simple 11-point maple leaf, our own drawing"""
    pts = [(0, -1.0), (0.16, -0.62), (0.42, -0.74), (0.34, -0.3), (0.82, -0.42), (0.7, -0.16), (0.96, 0.02), (0.5, 0.2), (0.6, 0.42),
           (0.12, 0.34), (0.08, 0.78), (-0.08, 0.78), (-0.12, 0.34), (-0.6, 0.42), (-0.5, 0.2), (-0.96, 0.02), (-0.7, -0.16), (-0.82, -0.42),
           (-0.34, -0.3), (-0.42, -0.74), (-0.16, -0.62)]
    d.polygon([(cx + x * s, cy + y * s) for x, y in pts], fill=fill)


# airline title on the fuselage (transparent): bold red caps
im = Image.new("RGBA", (2048, 256), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
text_c(d, (0, 0, 2048, 256), "AIR CANADA", F("ariblk.ttf", 190), (200, 24, 36, 255)); save(im, "title.png")
# tail: white leaf on transparent
im = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0)); d = ImageDraw.Draw(im); leaf(d, 512, 470, 430, (255, 255, 255, 255)); save(im, "tail_leaf.png")
# registration
im = Image.new("RGBA", (1024, 160), (0, 0, 0, 0)); d = ImageDraw.Draw(im); text_c(d, (0, 0, 1024, 160), "C-GAUN", F("arialbd.ttf", 120), (40, 40, 48, 255)); save(im, "reg.png")

# terminal signs
for name, txt, sub in (("sign_mtl.png", "MONTRÉAL", "DORVAL  ·  GATE 12"), ("sign_ott.png", "OTTAWA", "GATE 7")):
    im = Image.new("RGB", (2048, 512), (24, 44, 92)); d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 2048, 30), fill=(216, 38, 46)); d.rectangle((0, 482, 2048, 512), fill=(216, 38, 46))
    text_c(d, (0, 40, 2048, 380), txt, F("ariblk.ttf", 260), (255, 255, 255)); text_c(d, (0, 370, 2048, 480), sub, F("arialbd.ttf", 84), (255, 214, 90)); save(im, name)

# race-day banner + start-line banner + strip sign
im = Image.new("RGB", (2048, 512), (255, 206, 40)); d = ImageDraw.Draw(im)
for k in range(0, 2048, 128): d.polygon([(k, 0), (k + 64, 0), (k, 64)], fill=(216, 38, 46)); d.polygon([(k, 512), (k + 64, 512), (k, 448)], fill=(216, 38, 46))
text_c(d, (0, 30, 2048, 330), "FAMILY DAY", F("ariblk.ttf", 250), (216, 38, 46), stroke=10, sfill=(255, 255, 255))
text_c(d, (0, 320, 2048, 470), "DRAG RACES  ·  BBQ  ·  KIDS FREE", F("arialbd.ttf", 96), (30, 30, 40)); save(im, "banner_family.png")
im = Image.new("RGB", (2048, 384), (240, 240, 236)); d = ImageDraw.Draw(im)
for k in range(0, 2048, 96):
    for r in range(0, 384, 96): d.rectangle((k, r, k + 48, r + 48), fill=(20, 20, 24)) if (k // 96 + r // 96) % 2 == 0 else None
d.rectangle((300, 70, 1748, 314), fill=(216, 38, 46)); text_c(d, (300, 70, 1748, 314), "START", F("ariblk.ttf", 200), (255, 255, 255)); save(im, "banner_start.png")
im = Image.new("RGB", (1536, 768), (34, 110, 60)); d = ImageDraw.Draw(im); d.rectangle((24, 24, 1512, 744), outline=(255, 255, 255), width=18)
text_c(d, (0, 60, 1536, 420), "GIMLI", F("ariblk.ttf", 300), (255, 255, 255)); text_c(d, (0, 420, 1536, 700), "MOTORSPORT PARK", F("arialbd.ttf", 130), (255, 255, 255)); save(im, "sign_gimli.png")

# fuel truck + van decals
im = Image.new("RGBA", (2048, 512), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
d.rounded_rectangle((40, 60, 2008, 452), 40, fill=(216, 38, 46)); text_c(d, (40, 60, 2008, 452), "JET FUEL", F("ariblk.ttf", 250), (255, 255, 255)); save(im, "truck_side.png")
im = Image.new("RGBA", (2048, 512), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
d.rectangle((0, 200, 2048, 260), fill=(216, 38, 46)); text_c(d, (0, 280, 2048, 470), "AIRCRAFT MAINTENANCE", F("ariblk.ttf", 130), (40, 50, 80)); save(im, "van_side.png")

# cockpit: the six glass screens lit (attitude, map, engine), the same panel dark, the blank fuel gauge, the warning light
def screens(lit):
    im = Image.new("RGB", (3072, 768), (16, 17, 20)); d = ImageDraw.Draw(im)
    for i in range(6):
        x0 = 40 + i * 505; box = (x0, 120, x0 + 440, 680)
        d.rounded_rectangle((box[0] - 18, box[1] - 18, box[2] + 18, box[3] + 18), 26, fill=(44, 46, 52))
        if not lit:
            d.rectangle(box, fill=(6, 7, 9)); d.line((box[0] + 30, box[1] + 30, box[0] + 160, box[1] + 30), fill=(30, 32, 38), width=8); continue
        kind = ["adi", "map", "eng", "eng", "map", "adi"][i]
        if kind == "adi":
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            d.rectangle((box[0], box[1], box[2], cy + 20), fill=(40, 120, 220)); d.rectangle((box[0], cy + 20, box[2], box[3]), fill=(150, 96, 44))
            d.line((box[0], cy + 20, box[2], cy + 20), fill=(255, 255, 255), width=6)
            for k in (-2, -1, 1, 2): d.line((cx - 60, cy + 20 - k * 60, cx + 60, cy + 20 - k * 60), fill=(255, 255, 255), width=4)
            d.polygon([(cx - 120, cy + 20), (cx - 40, cy + 20), (cx - 40, cy + 40)], fill=(255, 220, 40)); d.polygon([(cx + 120, cy + 20), (cx + 40, cy + 20), (cx + 40, cy + 40)], fill=(255, 220, 40))
        elif kind == "map":
            d.rectangle(box, fill=(4, 6, 10)); cx = (box[0] + box[2]) / 2
            for r in (120, 220, 320): d.arc((cx - r, box[3] - r - 40, cx + r, box[3] + r - 40), 200, 340, fill=(220, 220, 230), width=4)
            d.line((cx, box[3] - 60, cx + 70, box[1] + 80), fill=(255, 60, 220), width=8); d.polygon([(cx - 22, box[3] - 40), (cx + 22, box[3] - 40), (cx, box[3] - 90)], fill=(255, 255, 255))
        else:
            d.rectangle(box, fill=(4, 6, 10))
            for j, (cx, cy) in enumerate(((box[0] + 120, box[1] + 140), (box[0] + 320, box[1] + 140), (box[0] + 120, box[1] + 380), (box[0] + 320, box[1] + 380))):
                d.arc((cx - 90, cy - 90, cx + 90, cy + 90), 160, 380, fill=(240, 240, 240), width=8)
                a = math.radians(160 + 160 * (0.55 + 0.1 * j)); d.line((cx, cy, cx + 80 * math.cos(a), cy + 80 * math.sin(a)), fill=(80, 255, 120), width=8)
    return im
save(screens(True), "screens_on.png"); save(screens(False), "screens_off.png")
im = Image.new("RGB", (1024, 512), (30, 31, 36)); d = ImageDraw.Draw(im)
d.rounded_rectangle((60, 60, 964, 452), 30, fill=(8, 8, 10)); text_c(d, (60, 70, 964, 160), "FUEL QTY   KG x 1000", F("arialbd.ttf", 54), (200, 200, 200))
text_c(d, (60, 170, 964, 440), "- - - -", F("consolab.ttf", 230), (255, 170, 40)); save(im, "fuel_blank.png")
im = Image.new("RGB", (512, 256), (190, 20, 24)); d = ImageDraw.Draw(im); d.rectangle((12, 12, 500, 244), outline=(255, 120, 110), width=10)
text_c(d, (0, 0, 512, 256), "WARNING", F("ariblk.ttf", 92), (255, 236, 230)); save(im, "warn.png")
# chart on the cockpit glareshield? no: the map is the co-pilot's 2D prop. Overhead panel switches:
im = Image.new("RGB", (1024, 512), (52, 54, 60)); d = ImageDraw.Draw(im)
for r in range(6):
    for c in range(14):
        x, y = 40 + c * 70, 40 + r * 75; d.rounded_rectangle((x, y, x + 40, y + 50), 8, fill=(30, 31, 36)); d.rectangle((x + 12, y + 10, x + 28, y + 30), fill=(230, 230, 230) if (r * 3 + c) % 5 else (255, 190, 40))
save(im, "overhead.png")
# crowd banner / sponsor boards along the strip (generic words, no brands)
for i, (bg, fg, txt) in enumerate((((255, 255, 255), (216, 38, 46), "QUARTER MILE"), ((30, 60, 140), (255, 210, 40), "PIT LANE"), ((255, 206, 40), (30, 30, 40), "RACE CONTROL"))):
    im = Image.new("RGB", (1536, 384), bg); d = ImageDraw.Draw(im); text_c(d, (0, 0, 1536, 384), txt, F("ariblk.ttf", 170), fg); save(im, f"board{i}.png")
