"""
Shared frame renderer: draws 1080x1920 frames with Pillow and pipes them into
FFmpeg. Used by the diagram engine and the photo (Ken Burns) renderer so every
generated shot has identical size, frame rate, and encoding to the stock clips.
"""
import os
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

from agents.editor_hailuo import FFMPEG

W, H, FPS = 1080, 1920, 30

# Content stays inside this band: TikTok/Shorts UI covers the top edge and the
# burned subtitles sit around y≈1400-1550.
SAFE_TOP, SAFE_BOTTOM = 220, 1320

PALETTE = {
    "bg_top": (11, 16, 32),
    "bg_bottom": (30, 38, 70),
    "accent": (255, 210, 63),     # matches the yellow subtitles
    "accent2": (61, 217, 235),
    "text": (255, 255, 255),
    "muted": (138, 147, 178),
    "dark": (14, 18, 34),
}

_FONT_CANDIDATES = {
    True: [
        "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ],
    False: [
        "C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ],
}
_font_cache = {}


def load_font(size: int, bold: bool = True):
    key = (size, bold)
    if key not in _font_cache:
        path = next((p for p in _FONT_CANDIDATES[bold] if os.path.exists(p)), None)
        _font_cache[key] = (ImageFont.truetype(path, size) if path
                            else ImageFont.load_default(size))
    return _font_cache[key]


# ------------------- EASING -------------------

def clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def ease_out_cubic(x: float) -> float:
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ease_in_out(x: float) -> float:
    x = clamp01(x)
    return 3 * x * x - 2 * x * x * x


def ease_out_back(x: float) -> float:
    x = clamp01(x)
    c1 = 1.70158
    return 1 + (c1 + 1) * (x - 1) ** 3 + c1 * (x - 1) ** 2


def progress(t: float, start: float, length: float) -> float:
    """0→1 as t goes from start to start+length."""
    return clamp01((t - start) / length) if length > 0 else float(t >= start)


def rgba(color, alpha: float) -> tuple:
    return (*color[:3], int(255 * clamp01(alpha)))


# ------------------- TEXT LAYOUT -------------------

def text_width(draw, text: str, font) -> float:
    return draw.textlength(text, font=font)


def wrap_text(draw, text: str, font, max_width: float) -> list:
    words, lines, line = str(text).split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if not line or text_width(draw, trial, font) <= max_width:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def fit_text(draw, text: str, max_width: float, max_lines: int,
             start_size: int, min_size: int, bold: bool = True) -> tuple:
    """Largest font (stepping down) whose wrapped text fits max_lines × max_width."""
    size = start_size
    while True:
        font = load_font(size, bold)
        lines = wrap_text(draw, text, font, max_width)
        fits = len(lines) <= max_lines and all(text_width(draw, l, font) <= max_width for l in lines)
        if fits or size <= min_size:
            return font, lines[:max_lines] if not fits else lines
        size = max(min_size, int(size * 0.9))


def line_height(font) -> int:
    ascent, descent = font.getmetrics()
    return int((ascent + descent) * 1.1)


def draw_badge(draw, text: str, center_x: int, top: int, alpha: float = 1.0,
               size: int = 58) -> None:
    """Accent pill with dark text — used for on-screen labels (names, years)."""
    font, lines = fit_text(draw, str(text), W - 200, 1, size, 34)
    label = lines[0] if lines else ""
    tw = text_width(draw, label, font)
    pad_x, pad_y = 36, 18
    h = line_height(font) + pad_y
    box = (center_x - tw / 2 - pad_x, top, center_x + tw / 2 + pad_x, top + h)
    draw.rounded_rectangle(box, radius=h // 2, fill=rgba(PALETTE["accent"], alpha))
    draw.text((center_x, top + h / 2), label, font=font, anchor="mm",
              fill=rgba(PALETTE["dark"], alpha))


def text_overlay_png(text: str, out_path: str) -> str:
    """Transparent full-frame PNG with a badge near the top, for overlaying footage."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_badge(ImageDraw.Draw(layer), text, W // 2, SAFE_TOP)
    layer.save(out_path)
    return out_path


def gradient_background() -> Image.Image:
    grad = Image.linear_gradient("L").resize((W, H))
    top, bottom = PALETTE["bg_top"], PALETTE["bg_bottom"]
    bands = [grad.point(lambda v, a=a, b=b: int(a + (b - a) * v / 255))
             for a, b in zip(top, bottom)]
    return Image.merge("RGB", bands)


# ------------------- ENCODING -------------------

def encode_frames(frames, out_path: str) -> str:
    """Pipe an iterable of RGB PIL images (W×H) into an H.264 MP4 at FPS."""
    cmd = [
        FFMPEG, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
        "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-an", out_path,
    ]
    # stderr goes to a temp file: a PIPE could fill up and deadlock while we
    # are still writing frames to stdin.
    with tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=err)
        try:
            for frame in frames:
                proc.stdin.write(frame.tobytes())
            proc.stdin.close()
            proc.wait(timeout=300)
        except BaseException:
            proc.kill()
            proc.wait()
            if os.path.exists(out_path):
                os.remove(out_path)
            raise
        if proc.returncode != 0:
            err.seek(0)
            tail = err.read().decode("utf-8", "replace")[-400:]
            if os.path.exists(out_path):
                os.remove(out_path)
            raise RuntimeError(f"Frame encode failed: {tail}")
    return out_path
