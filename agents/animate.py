"""
2.5D scene animation: turns one generated still into a moving camera shot.

A depth map splits the picture into near and far: on a push-in, close objects
grow faster than the background; on a pan, the foreground slides past the
backdrop. Every shot also opens with a quick zoom "punch" so cuts land with
energy. Optional overlays (a counting-up number or a name label) pop in on top.

Camera moves: push_in, pull_out, pan_left, pan_right, rise, orbit.
"""
import logging

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps

from agents.render import (
    W, H, FPS, SAFE_TOP, PALETTE,
    load_font, fit_text, line_height, rgba, draw_badge,
    ease_in_out, ease_out_cubic, ease_out_back, progress, encode_frames,
)
from agents.depth import estimate_depth

log = logging.getLogger("pipeline")

CAMERA_MOVES = ("push_in", "pull_out", "pan_left", "pan_right", "rise", "orbit")
OVERSCAN = 1.24          # source is rendered this much larger than the frame
PUNCH_SECONDS = 0.28     # opening zoom punch on every cut
PUNCH_ZOOM = 0.07


def _camera(move: str, p: float, d: np.ndarray):
    """Per-pixel zoom and shift (pixels) for progress p (0→1) of the shot."""
    near = d - 0.5                      # -0.5 (far) … +0.5 (near)
    span = W * (OVERSCAN - 1) / 2       # how far we can slide without showing edges
    if move == "pull_out":
        zoom = 1.16 - 0.16 * p + 0.10 * (1 - p) * near
        return zoom, 0.0, 0.0
    if move in ("pan_left", "pan_right"):
        sign = 1 if move == "pan_left" else -1
        shift = sign * span * 0.8 * (p - 0.5) * 2 * (0.55 + 0.9 * (d - 0.3))
        return 1.04, shift, 0.0
    if move == "rise":
        shift = -span * 0.7 * (p - 0.5) * 2 * (0.55 + 0.9 * (d - 0.3))
        return 1.03 + 0.03 * p, 0.0, shift
    if move == "orbit":
        shift = span * 0.8 * (p - 0.5) * 2 * (0.3 + 1.2 * (d - 0.3))
        return 1.05 + 0.07 * p + 0.04 * p * near, shift, 0.0
    # push_in (default): dolly in, near objects grow faster than the backdrop
    zoom = 1.0 + 0.16 * p + 0.12 * p * near
    return zoom, 0.0, 0.0


def _fit_source(image_path: str) -> np.ndarray:
    """Load the still and cover-crop it to the overscanned 9:16 canvas."""
    img = ImageOps.exif_transpose(Image.open(image_path)).convert("RGB")
    sw, sh = int(W * OVERSCAN), int(H * OVERSCAN)
    img = ImageOps.fit(img, (sw, sh), Image.LANCZOS)
    return np.ascontiguousarray(np.asarray(img))


# ------------------- OVERLAYS -------------------

def _draw_overlay(frame: Image.Image, overlay: dict, t: float) -> Image.Image:
    from agents.diagram import stat_text_at
    kind = overlay.get("type")
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    appear = 0.18

    if kind == "label":
        p = ease_out_back(progress(t, appear, 0.35))
        if p > 0:
            draw_badge(draw, str(overlay.get("text") or ""), W // 2, int(SAFE_TOP - 40 * (1 - p)),
                       alpha=min(1.0, p), size=76)
    elif kind == "stat":
        value = str(overlay.get("value") or "").strip()
        a = ease_out_cubic(progress(t, appear, 0.25))
        pop = ease_out_back(progress(t, appear, 0.4))
        shown = stat_text_at(value, progress(t, appear, 0.9))
        font, _ = fit_text(draw, value, W - 160, 1, 220, 90)
        y = SAFE_TOP + 40 + int(30 * (1 - pop))
        draw.text((W / 2, y), shown, font=font, anchor="mt", fill=rgba(PALETTE["accent"], a),
                  stroke_width=10, stroke_fill=rgba(PALETTE["dark"], a))
        label = str(overlay.get("text") or overlay.get("label") or "").strip()
        if label:
            lf, lines = fit_text(draw, label.upper(), W - 160, 2, 64, 40)
            ly = y + line_height(font) + 6
            la = ease_out_cubic(progress(t, appear + 0.25, 0.3))
            for line in lines:
                draw.text((W / 2, ly), line, font=lf, anchor="mt", fill=rgba(PALETTE["text"], la),
                          stroke_width=7, stroke_fill=rgba(PALETTE["dark"], la))
                ly += line_height(lf)
    else:
        return frame
    frame.paste(layer, (0, 0), layer)
    return frame


# ------------------- RENDER -------------------

def render_scene(image_path: str, frames: int, out_path: str, camera: str = "push_in",
                 overlay: dict = None, punch: bool = True) -> str:
    """Animate one still into a `frames`-long 1080x1920 clip."""
    src = _fit_source(image_path)
    depth = estimate_depth(src)
    sh, sw = src.shape[:2]
    cx, cy = sw / 2, sh / 2

    # Depth as seen from the resting camera (output grid) — drives per-pixel motion.
    ox, oy = (sw - W) // 2, (sh - H) // 2
    d_out = np.ascontiguousarray(depth[oy:oy + H, ox:ox + W])
    gx, gy = np.meshgrid(np.arange(W, dtype=np.float32) - W / 2,
                         np.arange(H, dtype=np.float32) - H / 2)
    move = camera if camera in CAMERA_MOVES else "push_in"
    duration = frames / FPS

    def frame_at(i):
        t = i / FPS
        p = ease_in_out(i / max(frames - 1, 1))
        zoom, sx, sy = _camera(move, p, d_out)
        if punch:
            zoom = zoom * (1 + PUNCH_ZOOM * (1 - ease_out_cubic(progress(t, 0, PUNCH_SECONDS))))
        map_x = (cx + gx / zoom - sx).astype(np.float32)
        map_y = (cy + gy / zoom - sy).astype(np.float32)
        out = cv2.remap(src, map_x, map_y, interpolation=cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_REFLECT101)
        if overlay and overlay.get("type"):
            return _draw_overlay(Image.fromarray(out), overlay, t)
        return out

    log.info(f"    Animating scene ({move}, {duration:.1f}s)")
    return encode_frames((frame_at(i) for i in range(frames)), out_path)
