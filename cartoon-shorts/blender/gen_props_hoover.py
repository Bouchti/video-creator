"""Textures for the 3D props of the Hoover-van film (PIL): tickets, claim forms, calendars, the week board, small-ads pages,
the court order, the SOLD board, a clock face, deckchair stripes, the vacuum's badge.
    python blender/gen_props_hoover.py <outDir>"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
FB, FA = "C:/Windows/Fonts/ariblk.ttf", "C:/Windows/Fonts/arialbd.ttf"
RED, BLUE, INK = "#d8262e", "#1f4fa0", "#241726"


def fit(d, s, w, size, font=FB):
    f = ImageFont.truetype(font, size)
    while d.textlength(s, font=f) > w and size > 8:
        size = int(size * 0.93); f = ImageFont.truetype(font, size)
    return f


def ctext(d, s, cx, cy, w, size, fill, font=FB):
    f = fit(d, s, w, size, font)
    bb = d.textbbox((0, 0), s, font=f)
    d.text((cx - (bb[2] - bb[0]) / 2 - bb[0], cy - (bb[3] - bb[1]) / 2 - bb[1]), s, font=f, fill=fill)


def ticket(name, l1, l2):
    im = Image.new("RGB", (1040, 480), "#fdfbf4"); d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 1040, 130), fill=BLUE); ctext(d, l1, 520, 66, 900, 96, "#ffffff")
    ctext(d, l2, 470, 250, 760, 70, INK)
    for k in range(9): d.rectangle((70 + k * 70, 370, 110 + k * 70, 384), fill="#8a8f9a")
    d.line((860, 150, 860, 470), fill="#b9bcc4", width=6)
    ctext(d, "✈", 950, 300, 140, 140, BLUE, "C:/Windows/Fonts/seguisym.ttf")
    d.rectangle((0, 0, 1039, 479), outline=INK, width=8)
    im.save(os.path.join(OUT, name + ".png"))


ticket("ticket_ny", "FREE FLIGHT", "LONDON → NEW YORK")
ticket("ticket_orl", "FREE FLIGHT", "LONDON → ORLANDO")
ticket("ticket_wus", "FREE FLIGHT", "WORKINGTON → USA")
ticket("ticket_ours", "YOUR FLIGHT", "DATE: OUR CHOICE")


def form(name, stamp):
    im = Image.new("RGB", (600, 800), "#fdfbf4"); d = ImageDraw.Draw(im)
    ctext(d, "FREE FLIGHTS", 300, 80, 520, 64, BLUE); ctext(d, "CLAIM FORM", 300, 150, 520, 44, INK)
    for k in range(9):
        y = 230 + k * 52; d.rectangle((60, y, 84, y + 24), outline=INK, width=4); d.line((100, y + 22, 540, y + 22), fill="#a8acb6", width=4)
    ctext(d, "RETURN WITHIN 14 DAYS!", 300, 730, 520, 40, RED)
    if stamp:
        st = Image.new("RGBA", (560, 200), (0, 0, 0, 0)); sd = ImageDraw.Draw(st)
        sd.rectangle((8, 8, 552, 192), outline=RED, width=18); ctext(sd, "REJECTED", 280, 102, 480, 120, RED)
        st = st.rotate(16, expand=True, resample=Image.BICUBIC); im.paste(st, (300 - st.width // 2, 440 - st.height // 2), st)
    im.save(os.path.join(OUT, name + ".png"))


form("form", False); form("form_rej", True)


def cal(name, big, word):
    im = Image.new("RGB", (520, 600), "#ffffff"); d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 520, 150), fill=RED)
    for x in (130, 390): d.rounded_rectangle((x - 16, 20, x + 16, 120), 10, fill="#3a3d47")
    ctext(d, big, 260, 345, 440, 260, INK); ctext(d, word, 260, 530, 460, 70, INK)
    d.rectangle((0, 0, 519, 599), outline=INK, width=10)
    im.save(os.path.join(OUT, name + ".png"))


for n in range(1, 15): cal(f"cal_{n}", str(n), "DAYS")
for m in ["JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC", "JAN", "FEB", "MAR"]: cal(f"cal_{m}", m, "STILL NOTHING")

D7 = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
for k in range(8):
    for stamp in (False, True):
        if stamp and k < 7: continue
        im = Image.new("RGB", (1240, 600), "#ffffff"); d = ImageDraw.Draw(im)
        d.rectangle((0, 0, 1240, 120), fill=RED); ctext(d, "THIS WEEK'S SHIFTS", 620, 60, 1100, 70, "#ffffff")
        for i, dd in enumerate(D7):
            x = 30 + i * 170; d.rectangle((x, 150, x + 150, 560), fill="#ffe0d0" if i >= 5 else "#f4f6fa", outline=INK, width=6); ctext(d, dd, x + 75, 200, 120, 48, INK)
            if i < k: d.line((x + 25, 270, x + 125, 520), fill=RED, width=22); d.line((x + 125, 270, x + 25, 520), fill=RED, width=22)
        if stamp:
            st = Image.new("RGBA", (900, 220), (0, 0, 0, 0)); sd = ImageDraw.Draw(st)
            sd.rectangle((10, 10, 890, 210), outline=RED, width=22); ctext(sd, "OVERTIME!", 450, 112, 800, 150, RED)
            st = st.rotate(10, expand=True, resample=Image.BICUBIC); im.paste(st, (620 - st.width // 2, 380 - st.height // 2), st)
        d.rectangle((0, 0, 1239, 599), outline=INK, width=10)
        im.save(os.path.join(OUT, f"week_{k}{'s' if stamp else ''}.png"))

ADS = ["HOOVER. UNUSED. STILL IN BOX", "HOOVER, NEVER OPENED £60", "BRAND NEW HOOVER - BOXED", "HOOVER TURBO. UNWANTED", "HOOVER, IN BOX, OFFERS", "HOOVER. NEW. NO FLIGHTS"]
for n in (0, 3, 6, 9, 12, 15, 18):
    im = Image.new("RGB", (900, 1140), "#f1ece0"); d = ImageDraw.Draw(im)
    ctext(d, "SMALL ADS", 450, 80, 800, 96, INK); d.line((40, 150, 860, 150), fill=INK, width=8)
    for i in range(18):
        c, r = i % 2, i // 2; x, y = 50 + c * 410, 175 + r * 105
        if i < n:
            d.rectangle((x, y, x + 390, y + 90), fill="#fff4a8" if i % 5 == 2 else "#ffffff", outline=INK, width=4)
            ctext(d, ADS[(i * 7 + 3) % len(ADS)], x + 195, y + 45, 360, 34, INK, FA)
        else:
            for k in range(3): d.line((x + 10, y + 22 + k * 26, x + 380, y + 22 + k * 26), fill="#c9c3b5", width=6)
    im.save(os.path.join(OUT, f"ads_{n}.png"))

im = Image.new("RGB", (600, 840), "#fbf6e6"); d = ImageDraw.Draw(im)
ctext(d, "IN THE HIGH COURT", 300, 90, 520, 48, INK); ctext(d, "ORDER", 300, 170, 400, 80, INK)
for k in range(8): d.line((70, 260 + k * 46, 530, 260 + k * 46), fill="#a8a090", width=5)
ctext(d, "RELEASE THE VAN", 300, 690, 500, 54, RED); d.ellipse((420, 720, 520, 820), fill=RED)
im.save(os.path.join(OUT, "order.png"))

im = Image.new("RGB", (1040, 600), RED); d = ImageDraw.Draw(im)
d.rectangle((20, 20, 1020, 580), outline="#ffffff", width=14); ctext(d, "SOLD", 520, 250, 900, 280, "#ffffff"); ctext(d, "HOOVER EUROPE", 520, 480, 880, 90, "#ffffff")
im.save(os.path.join(OUT, "sold.png"))

im = Image.new("RGB", (600, 600), "#ffffff"); d = ImageDraw.Draw(im)
d.ellipse((10, 10, 590, 590), outline=INK, width=24)
import math
for k in range(12):
    a = k / 12 * 2 * math.pi; d.line((300 + 230 * math.sin(a), 300 - 230 * math.cos(a), 300 + 265 * math.sin(a), 300 - 265 * math.cos(a)), fill=INK, width=14)
ctext(d, "HOOVER", 300, 410, 200, 40, RED)
im.save(os.path.join(OUT, "clock.png"))

im = Image.new("RGB", (512, 512), "#2f6fd0"); d = ImageDraw.Draw(im)
for k in range(0, 512, 128): d.rectangle((k, 0, k + 64, 512), fill="#ffffff")
im.save(os.path.join(OUT, "stripes.png"))

im = Image.new("RGB", (600, 260), "#f4f1ea"); d = ImageDraw.Draw(im)
d.rectangle((0, 0, 599, 259), outline="#c9ccd4", width=16); ctext(d, "HOOVER", 300, 110, 520, 120, RED); ctext(d, "TURBO", 300, 210, 300, 46, INK, FA)
im.save(os.path.join(OUT, "vac_badge.png"))
for nm, txt, col in (("tag_119", "£119", "#fff4a8"), ("tag_600", "£600", "#9be07a")):
    im = Image.new("RGB", (400, 180), col); d = ImageDraw.Draw(im); ctext(d, txt, 200, 90, 340, 120, INK); d.rectangle((0, 0, 399, 179), outline=INK, width=10)
    im.save(os.path.join(OUT, nm + ".png"))
print("props ->", OUT)
