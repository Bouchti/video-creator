"""Sign, poster and decal textures for the Hoover-van sets (PIL, Arial Black).
    python blender/gen_signs_hoover.py <outDir>"""
import os, sys, random
from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
FB = "C:/Windows/Fonts/ariblk.ttf"
FA = "C:/Windows/Fonts/arialbd.ttf"
RED, BLUE, INK = "#d8262e", "#1f4fa0", "#241726"


def text_fit(d, s, w, size, font=FB):
    f = ImageFont.truetype(font, size)
    while d.textlength(s, font=f) > w and size > 8:
        size = int(size * 0.93); f = ImageFont.truetype(font, size)
    return f, size


def sign(name, w, h, bg, fg, lines, border=True, font=FB):
    im = Image.new("RGB", (w, h), bg); d = ImageDraw.Draw(im)
    if border:
        b = max(8, int(h * 0.04)); d.rectangle((b, b, w - b - 1, h - b - 1), outline=fg, width=b)
    total = sum(s for _, s in lines) * 1.12; y = (h - total) / 2
    for text, size in lines:
        f, size = text_fit(d, text, w * 0.9, size, font)
        d.text(((w - d.textlength(text, font=f)) / 2, y), text, font=f, fill=fg); y += size * 1.12
    im.save(os.path.join(OUT, name + ".png"))


# shop: the window banner, the fascia, posters, price cards
sign("banner", 2400, 600, "#f2c230", RED, [("TWO FREE FLIGHTS!", 250), ("UNBELIEVABLE!", 200)])
sign("fascia", 2400, 360, "#1f2a44", "#f4f1ea", [("NORTHERN ELECTRICS", 200)], border=False)
sign("poster_usa", 600, 800, "#ffffff", BLUE, [("FLY TO", 110), ("AMERICA", 130), ("FREE!", 190), ("with any £100", 60), ("HOOVER purchase", 60)])
sign("poster_price", 600, 400, "#fff4a8", RED, [("TURBO", 90), ("£119.99", 150)])
sign("poster_wash", 600, 400, "#ffffff", BLUE, [("WASHER", 90), ("£299", 160)])
sign("sale", 1200, 300, RED, "#ffffff", [("FLIGHTS WITH EVERY HOOVER", 140)])
# the van's side decal and back doors
im = Image.new("RGB", (2000, 700), "#f7f7f4"); d = ImageDraw.Draw(im)
d.rectangle((0, 470, 2000, 560), fill=RED); d.rectangle((0, 580, 2000, 610), fill=BLUE)
f, s = text_fit(d, "HOOVER", 1300, 330); d.text((90, 90), "HOOVER", font=f, fill=RED)
f2, _ = text_fit(d, "SERVICE", 600, 120, FA); d.text((1420, 300), "SERVICE", font=f2, fill=BLUE)
im.save(os.path.join(OUT, "van_side.png"))
im = Image.new("RGB", (1000, 900), "#f7f7f4"); d = ImageDraw.Draw(im)
d.rectangle((0, 560, 1000, 640), fill=RED); d.line((500, 0, 500, 900), fill="#9aa0a8", width=10)
f, _ = text_fit(d, "HOOVER", 860, 220); d.text((70, 250), "HOOVER", font=f, fill=RED)
d.rectangle((60, 700, 300, 790), fill="#f2c230", outline=INK, width=6); f3, _ = text_fit(d, "K 412 RVM", 220, 60, FA); d.text((72, 715), "K 412 RVM", font=f3, fill=INK)
im.save(os.path.join(OUT, "van_back.png"))
# horse truck side: cream with maroon band and HORSES lettering
im = Image.new("RGB", (2400, 900), "#efe6d2"); d = ImageDraw.Draw(im)
d.rectangle((0, 600, 2400, 720), fill="#7a2a32"); d.rectangle((0, 735, 2400, 760), fill="#c9a35a")
f, _ = text_fit(d, "CAUTION HORSES", 1300, 150); d.text((560, 380), "CAUTION HORSES", font=f, fill="#7a2a32")
for x in range(0, 2400, 200): d.line((x, 0, x, 590), fill="#d9cdb2", width=4)
im.save(os.path.join(OUT, "truck_side.png"))
# factory and office signs
sign("factory_sign", 2400, 600, "#ffffff", RED, [("HOOVER", 400)], border=False)
sign("factory_shift", 1200, 400, "#f2c230", INK, [("OVERTIME:", 120), ("7 DAYS A WEEK", 120)])
sign("office_sign", 1600, 400, "#1f2a44", "#f4f1ea", [("HOOVER EUROPE", 170), ("Promotions Dept.", 70)], border=False)
sign("office_chart", 800, 600, "#ffffff", BLUE, [("FLIGHT CLAIMS", 80), ("EXPECTED  50,000", 70), ("ACTUAL  300,000+", 70)])
# vacuum carton print (each face of a box)
im = Image.new("RGB", (512, 640), "#c99a5e"); d = ImageDraw.Draw(im)
d.rectangle((0, 70, 512, 200), fill=RED); f, _ = text_fit(d, "HOOVER", 440, 110); d.text((40, 82), "HOOVER", font=f, fill="#ffffff")
d.rectangle((220, 250, 290, 520), fill=RED, outline=INK, width=5); d.rectangle((170, 520, 340, 580), fill="#3a3d47", outline=INK, width=5)
d.line((255, 230, 255, 250), fill="#5a5f6a", width=14); f4, _ = text_fit(d, "TURBO", 160, 60); d.text((30, 300), "TURBO", font=f4, fill=INK)
im.save(os.path.join(OUT, "carton.png"))
im = Image.new("RGB", (512, 640), "#f4f6fa"); d = ImageDraw.Draw(im)
d.rectangle((0, 60, 512, 170), fill=BLUE); f, _ = text_fit(d, "HOOVER", 420, 90); d.text((50, 72), "HOOVER", font=f, fill="#ffffff")
d.rectangle((120, 230, 390, 560), fill="#ffffff", outline=INK, width=6); d.ellipse((170, 300, 340, 470), fill="#9fc4e8", outline=INK, width=8)
im.save(os.path.join(OUT, "carton_wash.png"))
# window views: a northern town skyline (office), back gardens (kitchen)
rnd = random.Random(3)
im = Image.new("RGB", (1600, 800), "#9ed0f2"); d = ImageDraw.Draw(im)
for i in range(18):
    x = i * 95 + rnd.randint(-20, 20); h = rnd.randint(250, 560); c = rnd.choice(["#b5573f", "#8a7a6a", "#c9744f", "#a8a4a0", "#6a6f7a"])
    d.rectangle((x, 800 - h, x + 90, 800), fill=c, outline=INK, width=4)
    for wy in range(800 - h + 30, 780, 60):
        for wx in range(x + 12, x + 80, 28): d.rectangle((wx, wy, wx + 14, wy + 26), fill="#ffe9a0" if rnd.random() < 0.3 else "#3a4a6a")
im.save(os.path.join(OUT, "view_town.png"))
im = Image.new("RGB", (1600, 800), "#a8d8f8"); d = ImageDraw.Draw(im)
d.rectangle((0, 480, 1600, 800), fill="#7ab84a")
for i in range(9):
    x = i * 190; d.rectangle((x, 380, x + 150, 520), fill="#c9744f", outline=INK, width=4); d.polygon([(x - 10, 380), (x + 75, 300), (x + 160, 380)], fill="#5a5058", outline=INK)
for i in range(30): x = rnd.randint(0, 1600); d.ellipse((x - 40, 420, x + 40, 520), fill=rnd.choice(["#4f8a3a", "#5d9a3a"]), outline=INK, width=3)
d.line((0, 600, 1600, 560), fill="#efe6d2", width=6)
for x in range(80, 1600, 160): d.rectangle((x, 560, x + 50, 640), fill=rnd.choice(["#f4f1ea", RED, BLUE, "#f2c230"]))
im.save(os.path.join(OUT, "view_garden.png"))
# brick for the houses (warm northern red)
for k, col in enumerate(["#a8503c", "#b8664a"]):
    im = Image.new("RGB", (512, 512), col); d = ImageDraw.Draw(im)
    for y in range(0, 512, 16):
        for x in range(-16 if (y // 16) % 2 else 0, 512, 32):
            d.rectangle((x + 1, y + 1, x + 30, y + 14), outline="#6e2e22", fill=col if rnd.random() < 0.8 else ("#9a4634" if k == 0 else "#a65a40"))
    im.save(os.path.join(OUT, f"brick{k}.png"))
print("signs ->", OUT)
