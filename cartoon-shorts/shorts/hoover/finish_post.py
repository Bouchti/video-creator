"""Hoover short v2 post pass (owner, 11 Nov: labels and tickets were cut off or hidden): composite the overlays (labels, comic
sound words, stamps, the question mark) exported per frame by scripts/export_hoover.ts (screen anchor sx, sy in 0..1 of the
frame) onto the rendered film, CLAMPED inside a safe area above the subtitle band so every one is fully readable, plus the
word-timed subtitles (same look as subtitles.py). Writes package/hoover_final_subtitled.mp4 + preview + captions.srt.

    python cartoon-shorts/shorts/hoover/finish_post.py <frames.json> [--stills f1,f2,...]   (from Video Creator/)
"""
import json, math, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PKG = HERE / "package"
W, H, FPS = 1440, 2560, 30
FB = "C:/Windows/Fonts/ariblk.ttf"
INK = (36, 23, 38, 255)
FR = {fr["f"]: fr for fr in json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["frames"]}
STILLS = [int(x) for x in sys.argv[sys.argv.index("--stills") + 1].split(",")] if "--stills" in sys.argv else None

# ---------------------------------------------------------------- captions (as subtitles.py)
sys.path.insert(0, str(ROOT))
CFONT = ImageFont.truetype(str(ROOT / "buildit" / "assets" / "fonts" / "Poppins-Black.ttf"), round(76 * 4 / 3))
CY, STROKE = 0.70 * H, round(9 * 4 / 3)
words = [{"text": w["word"], "start": w["start"], "end": w["end"]} for w in json.loads((HERE / "voice" / "words.json").read_text(encoding="utf-8"))["words"]]
SEQ = [(("nineteen", "ninety-two."), "1992."), (("a", "hundred", "and", "nineteen", "pounds."), "£119."), (("a", "hundred", "pounds,"), "£100,"),
       (("six", "hundred."), "£600."), (("fifty", "thousand"), "50,000"), (("three", "hundred", "thousand."), "300,000."),
       (("two", "hundred", "and", "twenty", "thousand"), "220,000"), (("thirteen",), "13"), (("seven-day",), "7-day"), (("fourteen-day",), "14-day")]
mw, i = [], 0
while i < len(words):
    for seq, rep in SEQ:
        if tuple(w["text"].lower() for w in words[i:i + len(seq)]) == seq:
            mw.append({"text": rep, "start": words[i]["start"], "end": words[i + len(seq) - 1]["end"]}); i += len(seq); break
    else:
        mw.append(words[i]); i += 1
groups, cur = [], []
for w in mw:
    if cur and (len(cur) >= 2 or len(" ".join(x["text"] for x in cur + [w])) > 11 or cur[-1]["text"][-1] in ",.!?:;"):
        groups.append(cur); cur = []
    cur.append(w)
if cur: groups.append(cur)
DUR = len(FR) / FPS
spans = []
for k, g in enumerate(groups):
    start = max(0.05, g[0]["start"] - 0.04)
    nxt = groups[k + 1][0]["start"] - 0.04 if k + 1 < len(groups) else DUR
    spans.append((start, min(max(g[-1]["end"] + 0.12, start + 0.32), nxt, DUR), " ".join(w["text"] for w in g)))


def caption_img(text):
    d0 = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    x0, y0, x1, y1 = d0.textbbox((0, 0), text, font=CFONT, stroke_width=STROKE); m = 40
    img = Image.new("RGBA", (x1 - x0 + 2 * m, y1 - y0 + 2 * m), (0, 0, 0, 0))
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((m - x0 + 5, m - y0 + 8), text, font=CFONT, fill=(0, 0, 0, 150), stroke_width=STROKE, stroke_fill=(0, 0, 0, 150))
    img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(8)))
    ImageDraw.Draw(img).text((m - x0, m - y0), text, font=CFONT, fill=(255, 255, 255, 255), stroke_width=STROKE, stroke_fill=(8, 8, 10, 255))
    return img

# ---------------------------------------------------------------- overlays
def hexa(h, a=255):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def fit_font(text, w, size):
    f = ImageFont.truetype(FB, size); d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    while d.textlength(text, font=f) > w and size > 10: size = int(size * 0.94); f = ImageFont.truetype(FB, size)
    return f


def label_img(text, w, bg):
    bgc = hexa(bg); fg = (255, 255, 255, 255) if bg.lower() in ("#d8262e",) else INK
    f = fit_font(text, w * 0.86, 120); d0 = ImageDraw.Draw(Image.new("RGBA", (1, 1))); bb = d0.textbbox((0, 0), text, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]; pw, ph = int(tw + 0.12 * w + 40), int(th * 1.9 + 20)
    im = Image.new("RGBA", (pw + 24, ph + 30), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((10, 18, pw + 10, ph + 18), radius=ph // 3, fill=(0, 0, 0, 110))
    d.rounded_rectangle((4, 4, pw + 4, ph + 4), radius=ph // 3, fill=bgc, outline=INK, width=9)
    d.text((4 + pw / 2 - tw / 2 - bb[0], 4 + ph / 2 - th / 2 - bb[1]), text, font=f, fill=fg)
    return im


def shout_img(text, w, wob):
    R = w / 2; n = 14; pts = []
    for i in range(2 * n):
        a = i / (2 * n) * 2 * math.pi + (0.06 if wob else 0); r = R if i % 2 == 0 else R * 0.74
        pts.append((R + 12 + r * math.cos(a), R * 0.72 + 12 + r * 0.72 * math.sin(a)))
    im = Image.new("RGBA", (int(2 * R + 24), int(1.44 * R + 24)), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.polygon(pts, fill=hexa("#fff2c0"), outline=INK, width=10)
    f = fit_font(text, R * 1.2, 160); bb = d.textbbox((0, 0), text, font=f, stroke_width=4)
    d.text((im.width / 2 - (bb[2] - bb[0]) / 2 - bb[0], im.height / 2 - (bb[3] - bb[1]) / 2 - bb[1]), text, font=f, fill=hexa("#d8262e"), stroke_width=4, stroke_fill=INK)
    return im.rotate(-4 if wob else 4, expand=True, resample=Image.BICUBIC)


def stamp_img(text, w, rot):
    f = fit_font(text, w * 0.8, 160); d0 = ImageDraw.Draw(Image.new("RGBA", (1, 1))); bb = d0.textbbox((0, 0), text, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]; pw, ph = int(tw + 70), int(th + 60)
    im = Image.new("RGBA", (pw + 20, ph + 20), (0, 0, 0, 0)); d = ImageDraw.Draw(im); red = hexa("#d8262e", 235)
    d.rectangle((10, 10, pw + 10, ph + 10), outline=red, width=14); d.rectangle((26, 26, pw - 6, ph - 6), outline=red, width=5)
    d.text((10 + pw / 2 - tw / 2 - bb[0], 10 + ph / 2 - th / 2 - bb[1]), text, font=f, fill=red)
    return im.rotate(rot, expand=True, resample=Image.BICUBIC)


def q_img(w):
    f = ImageFont.truetype(FB, int(w * 1.5)); im = Image.new("RGBA", (int(w * 1.4), int(w * 2.0)), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    bb = d.textbbox((0, 0), "?", font=f, stroke_width=10)
    d.text((im.width / 2 - (bb[2] - bb[0]) / 2 - bb[0], im.height / 2 - (bb[3] - bb[1]) / 2 - bb[1]), "?", font=f, fill=hexa("#f2c230"), stroke_width=10, stroke_fill=INK)
    return im


cache = {}


def ov_img(o):
    w = o["w"] * W
    key = (o["t"], o["text"], o.get("bg"), round(o.get("rot", 0)), o.get("wob", 0), round(w))
    if key not in cache:
        cache[key] = (label_img(o["text"], w, o["bg"] or "#f2c230") if o["t"] == "label" else shout_img(o["text"], w, o.get("wob", 0)) if o["t"] == "shout"
                      else stamp_img(o["text"], w, o.get("rot", 0)) if o["t"] == "stamp" else q_img(w))
    im = cache[key]; k = max(0.0, o["k"])
    if abs(k - 1) > 0.01 and k > 0.02:
        im = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)
    return im


SAFE_X, SAFE_TOP, SAFE_BOT = 0.04 * W, 0.07 * H, 0.60 * H


def compose(f, t):
    frame = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for o in FR[f]["ov"]:
        if o["k"] <= 0.02: continue
        im = ov_img(o)
        cx, cy = o["sx"] * W, o["sy"] * H - im.height * 0.55     # sit just above its anchor
        cx = min(max(cx, SAFE_X + im.width / 2), W - SAFE_X - im.width / 2)
        cy = min(max(cy, SAFE_TOP + im.height / 2), SAFE_BOT - im.height / 2)
        frame.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))
    sp = next((s for s in spans if s[0] <= t < s[1]), None)
    if sp:
        key = ("cap", sp[2])
        if key not in cache: cache[key] = caption_img(sp[2])
        base = cache[key]; u = min(1.0, (t - sp[0]) / 0.09); sc = 0.86 + 0.14 * (1 + (u - 1) ** 2 * (3.2 * (u - 1) + 2.2))
        im = base.resize((max(1, round(base.width * sc)), max(1, round(base.height * sc))), Image.LANCZOS) if abs(sc - 1) > 0.005 else base
        if u < 1: a = np.asarray(im).copy(); a[..., 3] = (a[..., 3] * u).astype(np.uint8); im = Image.fromarray(a)
        frame.alpha_composite(im, (round(W / 2 - im.width / 2), round(CY - im.height * 0.6)))
    return frame


if STILLS:
    out = HERE.parent.parent / "out" / "hoover" / "post_stills"; out.mkdir(parents=True, exist_ok=True)
    src = HERE.parent.parent / "out" / "hoover" / sys.argv[sys.argv.index("--src") + 1] if "--src" in sys.argv else None
    for f in STILLS:
        bg = Image.open(src / f"s_{f:04d}.png").convert("RGBA").resize((W, H)) if src else Image.new("RGBA", (W, H), (90, 90, 90, 255))
        bg.alpha_composite(compose(f, (f + 0.5) / FPS)); bg.convert("RGB").save(out / f"s_{f:04d}.png")
    print("stills ->", out); sys.exit(0)

SRC = PKG / "hoover_final_1440x2560.mp4"
OUT = PKG / "hoover_final_subtitled.mp4"
p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-i", str(SRC), "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                      "-filter_complex", "[0:v][1:v]overlay=0:0:eof_action=pass[v]", "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-crf", "16",
                      "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(OUT)], stdin=subprocess.PIPE)
EMPTY = None
for f in range(len(FR)):
    fr = compose(f, (f + 0.5) / FPS)
    p.stdin.write(fr.tobytes())
p.stdin.close(); p.wait()
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(OUT), "-vf", "scale=720:1280", "-c:v", "libx264", "-crf", "27", "-preset", "slow", "-c:a", "aac",
                "-b:a", "128k", "-movflags", "+faststart", str(PKG / "hoover_preview_720p.mp4")], check=True)


def ts(x):
    ms = round(x * 1000); return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


(PKG / "captions.srt").write_text("".join(f"{i + 1}\n{ts(a)} --> {ts(b)}\n{t}\n\n" for i, (a, b, t) in enumerate(spans)), encoding="utf-8")
print(f"{OUT.name}: {len(spans)} captions, overlays composited over {len(FR)} frames")
