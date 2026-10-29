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
COLORFUL_MIN = 40.0      # below this a frame reads as washed out on a phone


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


def flicker_map(frames, threshold=8.0):
    """Which third of the frame strobes most (top / middle / bottom), for the warning text."""
    g = [_gray(f) for f in frames]
    acc = np.zeros_like(g[0])
    for i in range(1, len(g) - 1):
        acc += _spikes(g, i, threshold)
    h = acc.shape[0]
    parts = {"top": acc[: h // 3].mean(), "middle": acc[h // 3: 2 * h // 3].mean(), "bottom": acc[2 * h // 3:].mean()}
    return max(parts, key=parts.get)


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
