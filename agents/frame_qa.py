"""
Measured frame checks for rendered video (no AI, deterministic, cheap).

  flicker(frames)        share of pixels that spike for ONE frame against both neighbours (strobing)
  colorfulness(image)    Hasler & Suesstrunk 2003 colourfulness (M): <33 dull, 33-45 moderate, >59 vivid
  pan_speed(frames)      fastest image motion between consecutive frames, in frame widths per frame
"""
import numpy as np
from PIL import Image

FLICKER_MAX = 1.5        # % of pixels allowed to strobe between consecutive frames
PAN_MAX = 0.015          # frame widths per frame: faster than this, a pan without motion blur stutters
COLORFUL_MIN = 65.0      # below this a cartoon frame reads as washed out on a phone (AgX frames scored ~50)
HIGHLIGHT_MIN = 0.8      # the brightest 2 % of a frame must reach this (AgX capped them at 0.71: grey, faded)


def _gray(img, size=(270, 480)):
    if isinstance(img, str):
        img = Image.open(img)
    return np.asarray(img.convert("L").resize(size), dtype=np.float32)


def _shift(a, b):
    """Integer (dy, dx) that best aligns b onto a (phase correlation): a camera pan is motion, not flicker."""
    fa, fb = np.fft.fft2(a - a.mean()), np.fft.fft2(b - b.mean())
    r = fa * np.conj(fb)
    corr = np.fft.ifft2(r / (np.abs(r) + 1e-9)).real
    dy, dx = np.unravel_index(np.argmax(corr), corr.shape)
    h, w = a.shape
    return (dy - h if dy > h // 2 else dy), (dx - w if dx > w // 2 else dx)


def _aligned(ref, img):
    dy, dx = _shift(ref, img)
    return np.roll(img, (dy, dx), axis=(0, 1)), max(abs(dy), abs(dx))


def _spikes(g, i, threshold):
    """Pixels of frame i brighter (or darker) than BOTH neighbours after aligning them on frame i. The
    border a shift wraps around is ignored."""
    prev, m1 = _aligned(g[i], g[i - 1])
    nxt, m2 = _aligned(g[i], g[i + 1])
    a, b = g[i] - prev, g[i] - nxt
    spike = (np.sign(a) == np.sign(b)) & (np.abs(a) > threshold) & (np.abs(b) > threshold)
    m = max(m1, m2) + 1
    spike[:m], spike[-m:], spike[:, :m], spike[:, -m:] = False, False, False, False
    return spike


def flicker(frames, threshold=8.0):
    """frames: >= 3 consecutive images (paths or PIL). Returns the worst per-triplet strobing share in %."""
    g = [_gray(f) for f in frames]
    return max((float(_spikes(g, i, threshold).mean() * 100) for i in range(1, len(g) - 1)), default=0.0)


def colorfulness(img):
    if isinstance(img, str):
        img = Image.open(img)
    x = np.asarray(img.convert("RGB").resize((270, 480)), dtype=np.float32)
    rg = x[..., 0] - x[..., 1]
    yb = 0.5 * (x[..., 0] + x[..., 1]) - x[..., 2]
    return float(np.sqrt(rg.std() ** 2 + yb.std() ** 2) + 0.3 * np.sqrt(rg.mean() ** 2 + yb.mean() ** 2))


def pan_speed(frames, size=(540, 960)):
    g = [_gray(f, size) for f in frames]
    return max((max(abs(v) for v in _shift(g[i + 1], g[i])) / size[0] for i in range(len(g) - 1)), default=0.0)


def scan(frames, size=(90, 160), threshold=12.0, cut_level=40.0):
    # coarse on purpose: real flicker (a pop, a one-frame glitch, a jittering actor) survives downscaling,
    # while sub-pixel texture motion under a slow zoom averages away (it read as 2-9 % "strobe" at 180 px)
    """Every frame, not samples: [(frame_no, strobe %, pan in frame widths)] (frame_no is 1-based).
    A cut (the whole picture changes) is neither flicker nor a pan, so it reads as (0, 0)."""
    out = []
    prev = cur = None
    for k, path in enumerate(frames):
        nxt = _gray(path, size)
        if cur is not None and prev is not None:
            a, b = np.abs(cur - prev).mean(), np.abs(cur - nxt).mean()
            if a > cut_level or b > cut_level:
                out.append((k, 0.0, 0.0))
            else:
                strobe = float(_spikes([prev, cur, nxt], 1, threshold).mean() * 100)
                pan = max(abs(v) for v in _shift(nxt, cur)) / size[0]
                out.append((k, strobe, pan))
        prev, cur = cur, nxt
    return out


def highlights(img):
    """Brightness (0..1) of the brightest 2 % of the frame: low means the picture never reaches white."""
    if isinstance(img, str):
        img = Image.open(img)
    x = np.asarray(img.convert("RGB").resize((270, 480)), dtype=np.float32) / 255
    return float(np.percentile(x.mean(axis=2), 98))
