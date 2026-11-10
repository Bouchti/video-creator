"""The 9:16 cut of a finished episode, on the tool-reel-edit format (Instagram safe zone, word-synced captions).

    python scripts/vertical.py <slug>          (from what-if-studio/, after master.py)

The 16:9 master sits whole in the middle of a 1080x1920 frame over a blurred, darkened copy of itself; the title is
pinned at the top of the safe zone; captions run 1-2 words at a time (~0.42 s a chunk, each held until the next
begins) on the low caption line. Every piece of text stays inside the safe zone: x 35-980, y 220-1470, and a row
centred on x 540 is at most 880 px wide. Writes out/<slug>/<slug>-9x16.mp4 and out/<slug>/captions.srt.
"""
import json, subprocess, sys, tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

STUDIO = Path(__file__).resolve().parent.parent
FONT = STUDIO.parent / 'buildit' / 'assets' / 'fonts' / 'Poppins-Black.ttf'
W, H = 1080, 1920
SAFE = (35, 220, 980, 1470)
SAFE_CENTRED_W = 880
VIDEO_Y = 520                    # the 1080x608 picture: y 520-1128
CAPTION_Y = 1290                 # caption centre, between the picture and the lowest safe centre (1366)
ORANGE, YELLOW, INK = '#FF8A3D', '#FFE27A', '#1A1230'

slug = sys.argv[1]
ep = json.loads((STUDIO / 'src' / 'episodes' / slug / 'episode.json').read_text(encoding='utf-8'))
words = json.loads((STUDIO / 'src' / 'episodes' / slug / 'words.json').read_text(encoding='utf-8'))
out = STUDIO / 'out' / slug
master = out / f'{slug}-final.mp4'
dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(master)],
                           capture_output=True, text=True, check=True).stdout)
accent = ep.get('accent', '').upper()


def fit(text: str, size: int, box_w: int) -> ImageFont.FreeTypeFont:
    """The largest font up to `size` whose measured width fits box_w."""
    while size > 20:
        f = ImageFont.truetype(str(FONT), size)
        if ImageDraw.Draw(Image.new('RGB', (1, 1))).textlength(text, font=f) <= box_w:
            return f
        size -= 2
    return ImageFont.truetype(str(FONT), size)


def text_png(lines, sizes, path, gap=10, stroke=10):
    """Centred lines on a transparent 1080-wide strip; the accent word in yellow. Returns the strip's height."""
    fonts = [fit(t, s, SAFE_CENTRED_W - 2 * stroke) for t, s in zip(lines, sizes)]
    hs = [f.getbbox('Ag')[3] + stroke for f in fonts]
    h = sum(hs) + gap * (len(lines) - 1) + 2 * stroke
    img = Image.new('RGBA', (W, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = stroke
    for t, f, lh in zip(lines, fonts, hs):
        x = 540 - d.textlength(t, font=f) / 2
        for k, w in enumerate(t.split(' ')):
            piece = w + (' ' if k < len(t.split(' ')) - 1 else '')
            fill = YELLOW if accent and accent in w.upper().strip('?.!,') else 'white'
            d.text((x, y), piece, font=f, fill=fill, stroke_width=stroke, stroke_fill=INK)
            x += d.textlength(piece, font=f)
        y += lh + gap
    img.save(path)
    return h


# ---- caption chunks: 1-2 words, ~0.42 s, a second word only if the first doesn't end a phrase
chunks, i = [], 0
while i < len(words):
    w = words[i]
    group = [w]
    if i + 1 < len(words):
        n = words[i + 1]
        first_ends = (w.get('p') or '').strip() != ''
        if not first_ends and n['e'] - w['s'] <= 0.5 and len(w['w']) + len(n['w']) <= 13:
            group.append(n)
    chunks.append(group)
    i += len(group)
spans = []
for k, g in enumerate(chunks):
    a = g[0]['s']
    b = chunks[k + 1][0]['s'] if k + 1 < len(chunks) else min(dur, g[-1]['e'] + 0.8)
    spans.append((a, b, ' '.join(x['w'] + (x.get('p') or '').strip() for x in g)))

tmp = Path(tempfile.mkdtemp(prefix='wi_vert_'))
title = ep['title'] if isinstance(ep['title'], list) else [ep['title'], '']
title_png = tmp / 'title.png'
th = text_png([title[0], title[1]], [58, 84], title_png)
assert 240 + th <= VIDEO_Y, 'the title runs into the picture'

pngs = []
for k, (a, b, text) in enumerate(spans):
    p = tmp / f'c{k:03d}.png'
    ch = text_png([text.upper()], [92], p, stroke=12)
    assert CAPTION_Y - ch / 2 >= SAFE[1] and CAPTION_Y + ch / 2 <= SAFE[3], text
    pngs.append((p, a, b, ch))

# ---- the filter: blurred fill, the picture, the title, the captions
inputs = ['-i', str(master), '-i', str(title_png)]
for p, *_ in pngs:
    inputs += ['-i', str(p)]
fc = [f'[0:v]split[a][b]',
      f'[a]scale=-2:{H},crop={W}:{H},boxblur=30:3,eq=brightness=-0.22:saturation=0.8[bg]',
      f'[b]scale={W}:-2[fg]',
      f'[bg][fg]overlay=0:{VIDEO_Y}[v0]',
      f'[v0][1:v]overlay=0:240[v1]']
last = 'v1'
for k, (p, a, b, ch) in enumerate(pngs):
    fc.append(f"[{last}][{k + 2}:v]overlay=0:{int(CAPTION_Y - ch / 2)}:enable='between(t,{a:.3f},{b:.3f})'[c{k}]")
    last = f'c{k}'
vert = out / f'{slug}-9x16.mp4'
subprocess.run(['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', ';'.join(fc), '-map', f'[{last}]', '-map', '0:a',
                '-c:v', 'libx264', '-crf', '18', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-c:a', 'copy',
                '-movflags', '+faststart', str(vert)], check=True)


def ts(x):
    ms = int(round(x * 1000))
    return f'{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}'


(out / 'captions.srt').write_text(''.join(f'{k + 1}\n{ts(a)} --> {ts(b)}\n{t}\n\n' for k, (a, b, t) in enumerate(spans)), encoding='utf-8')
print(f'{vert} ({dur:.1f} s, {len(spans)} caption chunks)')
