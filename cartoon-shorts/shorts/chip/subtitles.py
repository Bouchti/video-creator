"""Burn the Video Creator captions into the chip short: the Build-It pipeline's own phrase grouping
(buildit.compose.caption_groups) and its caption look (Poppins Black, white on a dark rounded pill with a soft shadow,
a 0.09 s back-out pop, the band under the subject), scaled from 1080x1920 to the 1440x2560 final.

    python cartoon-shorts/shorts/chip/subtitles.py        (from Video Creator/)
writes package/chip_final_subtitled.mp4, package/chip_preview_720p.mp4 and package/captions.srt
"""
import json, subprocess, sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from buildit.compose import caption_groups  # noqa: E402
from buildit.config import CAPTION_Y, SAFE_RIGHT, W as BW  # noqa: E402

HERE = Path(__file__).resolve().parent
PKG = HERE / "package"
SRC = PKG / "chip_final_1440x2560.mp4"
W, H, FPS = 1440, 2560, 30
K = W / BW                                        # 4/3: Build-It's 1080-wide sizes -> the 2K frame
FONT = ImageFont.truetype(str(ROOT / "buildit" / "assets" / "fonts" / "Poppins-Black.ttf"), round(68 * K))
CY = (CAPTION_Y[0] + CAPTION_Y[1]) / 2 * K        # band centre (Build-It: 1530 of 1920)
STRIP_Y, STRIP_H = int(CY - 170), 340             # only this strip is composited (keeps the pipe small)
PAD = (round(30 * K), round(8 * K), round(30 * K), round(14 * K))  # left, top, right, bottom (CSS padding 8 30 14)
RADIUS, MAXW = round(26 * K), round(W - 2 * SAFE_RIGHT * K)

words = [{"text": w["word"], "start": w["start"], "end": w["end"]} for w in json.loads((HERE / "voice" / "words.json").read_text(encoding="utf-8"))["words"]]
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(SRC)], capture_output=True, text=True).stdout)
NUMS = []
# spoken numbers become digits, merged into one caption token so a group never splits them
MERGE = {("nineteen", "forty-seven,"): "1947,", ("fifty", "thousand"): "50,000", ("twenty", "billion"): "20 billion", ("two", "hundred"): "200"}
SINGLE = {"forty-six.": "46."}
mw, i = [], 0
while i < len(words):
    w = words[i]
    if i + 1 < len(words) and (w["text"].lower(), words[i + 1]["text"]) in MERGE:
        mw.append({"text": MERGE[(w["text"].lower(), words[i + 1]["text"])], "start": w["start"], "end": words[i + 1]["end"]}); i += 2; continue
    mw.append({**w, "text": SINGLE.get(w["text"], w["text"])}); i += 1
words = mw
groups = caption_groups(words)
spans = []
for k, g in enumerate(groups):                     # timing exactly as buildit.compose.captions_scene
    start = max(0.05, g[0]["start"] - 0.04)
    nxt = groups[k + 1][0]["start"] - 0.04 if k + 1 < len(groups) else dur
    end = min(max(g[-1]["end"] + 0.12, start + 0.32), nxt, dur)
    txt = " ".join(w["text"] for w in g)
    for k, v in NUMS: txt = txt.replace(k, v)
    spans.append((start, end, txt))


def pill(text: str) -> Image.Image:
    """the caption at full size: shadowed dark pill + white heavy text (RGBA, tight box incl. shadow margin)"""
    d0 = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    x0, y0, x1, y1 = d0.textbbox((0, 0), text, font=FONT)
    tw, th = x1 - x0, round(68 * K * 1.05)
    bw, bh = min(tw + PAD[0] + PAD[2], MAXW), th + PAD[1] + PAD[3]
    m = 50
    img = Image.new("RGBA", (bw + 2 * m, bh + 2 * m), (0, 0, 0, 0))
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((m, m + round(8 * K), m + bw, m + bh + round(8 * K)), RADIUS, fill=(0, 0, 0, 64))
    img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(round(11 * K))))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((m, m, m + bw, m + bh), RADIUS, fill=(16, 20, 28, 209))
    tx = m + (bw - tw) / 2 - x0
    ty = m + PAD[1] + (th - (y1 - y0)) / 2 - y0
    d.text((tx, ty), text, font=FONT, fill=(255, 255, 255, 255))
    return img


def back_out(u, s=2.2):
    u -= 1
    return u * u * ((s + 1) * u + s) + 1


cache = {}


def strip_at(t: float) -> bytes:
    sp = next((s for s in spans if s[0] <= t < s[1]), None)
    if sp is None:
        return EMPTY
    u = min(1.0, (t - sp[0]) / 0.09)
    key = (sp[2], round(u, 2))
    if key not in cache:
        base = pill(sp[2])
        sc = 0.86 + 0.14 * back_out(u)
        im = base.resize((max(1, round(base.width * sc)), max(1, round(base.height * sc))), Image.LANCZOS) if sc != 1 else base
        if u < 1:
            a = np.asarray(im).copy(); a[..., 3] = (a[..., 3] * u).astype(np.uint8); im = Image.fromarray(a)
        strip = Image.new("RGBA", (W, STRIP_H), (0, 0, 0, 0))
        # transform-origin 50% 60%: scale about a point 60 % down the pill
        strip.alpha_composite(im, (round(W / 2 - im.width / 2), round(CY - STRIP_Y - im.height * 0.6 + (base.height * 0.6 - base.height / 2) * 1)))
        cache[key] = strip.tobytes()
    return cache[key]


EMPTY = Image.new("RGBA", (W, STRIP_H), (0, 0, 0, 0)).tobytes()
out = PKG / "chip_final_subtitled.mp4"
nframes = round(dur * FPS)
p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-i", str(SRC), "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{STRIP_H}", "-r", str(FPS), "-i", "-",
                      "-filter_complex", f"[0:v][1:v]overlay=0:{STRIP_Y}:eof_action=pass[v]", "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-crf", "16",
                      "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
for f in range(nframes):
    p.stdin.write(strip_at((f + 0.5) / FPS))
p.stdin.close()
p.wait()
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-vf", "scale=720:1280", "-c:v", "libx264", "-crf", "27", "-preset", "slow", "-c:a", "aac",
                "-b:a", "128k", "-movflags", "+faststart", str(PKG / "chip_preview_720p.mp4")], check=True)


def ts(x):
    ms = round(x * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


(PKG / "captions.srt").write_text("".join(f"{i + 1}\n{ts(a)} --> {ts(b)}\n{t}\n\n" for i, (a, b, t) in enumerate(spans)), encoding="utf-8")
print(f"{out.name}: {len(spans)} captions over {dur:.1f} s")
