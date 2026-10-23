"""
Diagram engine: renders a beat's `diagram` visual as an animated 1080x1920 clip.

Each template draws one frame for time t from the beat's parameters, so the
picture shows EXACTLY what the narration says (the number, the step, the date)
— no model involved, fully deterministic, zero cost.

Templates (selected by visual["template"]):
  key_phrase  text                                   — an idea that can't be filmed
  stat        value, label, title?                   — a number that counts up
  process     steps[], active_step? (1-based), title — vertical flow, current step lit
  timeline    events[{year,label}], active_event?, title
  comparison  items[{label,value,display?}], title   — growing bars
"""
import logging
import re

from PIL import Image, ImageDraw

from agents.render import (
    W, H, FPS, SAFE_TOP, SAFE_BOTTOM, PALETTE,
    load_font, fit_text, line_height, text_width, rgba,
    ease_out_cubic, ease_out_back, ease_in_out, progress,
    gradient_background, encode_frames,
)

log = logging.getLogger("pipeline")

MARGIN = 90
_bg_cache = None


def _background() -> Image.Image:
    global _bg_cache
    if _bg_cache is None:
        _bg_cache = gradient_background()
    return _bg_cache


def _active_index(value, count: int):
    """1-based index from the script → 0-based, or None when absent/invalid."""
    try:
        i = int(value) - 1
    except (TypeError, ValueError):
        return None
    return i if 0 <= i < count else None


def _draw_title(draw, title, t: float, y: int = SAFE_TOP + 20) -> int:
    """Draw an optional header; return the y where content can start."""
    if not title:
        return y
    font, lines = fit_text(draw, str(title), W - 2 * MARGIN, 2, 66, 40)
    a = ease_out_cubic(progress(t, 0, 0.35))
    for line in lines:
        draw.text((W / 2, y), line, font=font, anchor="mt", fill=rgba(PALETTE["muted"], a))
        y += line_height(font)
    return y + 40


# ------------------- key_phrase -------------------

def _key_phrase(draw, t, dur, v):
    text = str(v.get("text") or v.get("title") or v.get("description") or "").strip()
    font, lines = fit_text(draw, text, W - 2 * MARGIN, 5, 128, 60)
    lh = line_height(font)
    y = (SAFE_TOP + SAFE_BOTTOM) / 2 - lh * len(lines) / 2
    for i, line in enumerate(lines):
        p = ease_out_cubic(progress(t, 0.1 * i, 0.4))
        draw.text((W / 2, y + lh * i + 50 * (1 - p)), line, font=font, anchor="mt",
                  fill=rgba(PALETTE["text"], p))
    bar = 260 * ease_out_cubic(progress(t, 0.25 + 0.1 * len(lines), 0.5))
    by = y + lh * len(lines) + 30
    if bar > 1:
        draw.rounded_rectangle((W / 2 - bar / 2, by, W / 2 + bar / 2, by + 14), radius=7,
                               fill=rgba(PALETTE["accent"], 1))


# ------------------- stat -------------------

_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def parse_stat(value: str):
    """Split '$4.2B' → ('$', 4.2, 'B', decimals=1, commas=False). None if no number."""
    m = _NUM.search(value)
    if not m:
        return None
    raw = m.group(0)
    decimals = len(raw.split(".")[1]) if "." in raw else 0
    return value[:m.start()], float(raw.replace(",", "")), value[m.end():], decimals, "," in raw


def format_stat(prefix, number, suffix, decimals, commas) -> str:
    body = f"{number:,.{decimals}f}" if commas else f"{number:.{decimals}f}"
    return f"{prefix}{body}{suffix}"


def stat_text_at(value: str, p: float) -> str:
    """Counted-up text for animation progress p (0→1). Years don't count."""
    parsed = parse_stat(value)
    if not parsed:
        return value
    prefix, number, suffix, decimals, commas = parsed
    looks_like_year = decimals == 0 and not commas and 1000 <= number <= 2100 and not suffix.strip()
    if looks_like_year or p >= 1:
        return value
    return format_stat(prefix, number * ease_out_cubic(p), suffix, decimals, commas)


def _stat(draw, t, dur, v):
    value = str(v.get("value") or "").strip()
    top = _draw_title(draw, v.get("title"), t)
    cx, cy, r = W / 2, max(top + 360, 720), 330
    box = (cx - r, cy - r, cx + r, cy + r)
    draw.ellipse(box, outline=rgba(PALETTE["muted"], 0.25), width=18)
    sweep = 360 * ease_out_cubic(progress(t, 0.05, 1.0))
    if sweep > 0.5:
        draw.arc(box, start=-90, end=-90 + sweep, fill=rgba(PALETTE["accent"], 1), width=18)

    shown = stat_text_at(value, progress(t, 0.05, 0.9))
    font, _ = fit_text(draw, value, 2 * r - 110, 1, 210, 70)  # size from the FINAL text
    pop = ease_out_back(progress(t, 0, 0.45))
    draw.text((cx, cy), shown, font=font, anchor="mm", fill=rgba(PALETTE["text"], min(1, pop)))

    label = str(v.get("label") or "").strip()
    if label:
        lf, lines = fit_text(draw, label, W - 2 * MARGIN, 2, 66, 40)
        a = ease_out_cubic(progress(t, 0.45, 0.4))
        y = cy + r + 50
        for line in lines:
            draw.text((cx, y), line, font=lf, anchor="mt", fill=rgba(PALETTE["text"], a))
            y += line_height(lf)


# ------------------- process -------------------

def _process(draw, t, dur, v):
    steps = [str(s) for s in (v.get("steps") or [])][:6]
    active = _active_index(v.get("active_step"), len(steps))
    top = _draw_title(draw, v.get("title"), t)
    n = len(steps)
    gap = 70
    box_h = min(170, (SAFE_BOTTOM - top - gap * (n - 1)) / n)
    top += max(0, (SAFE_BOTTOM - top - (n * box_h + (n - 1) * gap)) / 2)  # center the flow
    x0, x1 = MARGIN, W - MARGIN
    font = load_font(int(min(60, box_h * 0.4)))
    num_font = load_font(int(min(52, box_h * 0.36)))

    for i, step in enumerate(steps):
        y = top + i * (box_h + gap)
        if active is None:  # build the whole flow, step by step
            p = ease_out_cubic(progress(t, 0.18 * i, 0.4))
            state = "active"
        else:
            p = 1.0
            state = "done" if i < active else "active" if i == active else "future"

        scale, dx = 1.0, -60 * (1 - p)
        if state == "active" and active is not None:
            scale = 0.85 + 0.15 * ease_out_back(progress(t, 0.1, 0.4))
        w, h = (x1 - x0) * scale, box_h * scale
        cx, cy = (x0 + x1) / 2 + dx, y + box_h / 2
        rect = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)

        if state == "active":
            draw.rounded_rectangle(rect, radius=int(h * 0.3), fill=rgba(PALETTE["accent"], p))
            text_col, num_bg, num_col = PALETTE["dark"], PALETTE["dark"], PALETTE["accent"]
        elif state == "done":
            draw.rounded_rectangle(rect, radius=int(h * 0.3), fill=rgba(PALETTE["accent2"], 0.22))
            text_col, num_bg, num_col = PALETTE["text"], PALETTE["accent2"], PALETTE["dark"]
        else:
            draw.rounded_rectangle(rect, radius=int(h * 0.3), outline=rgba(PALETTE["muted"], 0.6), width=4)
            text_col, num_bg, num_col = PALETTE["muted"], PALETTE["muted"], PALETTE["dark"]

        nr = h * 0.3
        ncx = rect[0] + nr + 26
        draw.ellipse((ncx - nr, cy - nr, ncx + nr, cy + nr), fill=rgba(num_bg, p))
        draw.text((ncx, cy), str(i + 1), font=num_font, anchor="mm", fill=rgba(num_col, p))
        label_font, lines = fit_text(draw, step, rect[2] - (ncx + nr + 30) - 30, 1,
                                     font.size, 30)
        draw.text((ncx + nr + 30, cy), lines[0] if lines else step, font=label_font,
                  anchor="lm", fill=rgba(text_col, p))

        if i < n - 1:  # arrow to the next step
            ay0, ay1 = y + box_h + 10, y + box_h + gap - 10
            if active is None:
                grow = ease_out_cubic(progress(t, 0.18 * i + 0.25, 0.25))
            elif i + 1 == active:  # the arrow INTO the current step draws itself
                grow = ease_out_cubic(progress(t, 0, 0.35))
            else:
                grow = 1.0
            ay = ay0 + (ay1 - ay0) * grow
            col = rgba(PALETTE["muted"], 0.8)
            if grow > 0.05:
                draw.line((W / 2, ay0, W / 2, ay), fill=col, width=6)
                draw.polygon([(W / 2 - 16, ay - 14), (W / 2 + 16, ay - 14), (W / 2, ay + 4)], fill=col)


# ------------------- timeline -------------------

def _timeline(draw, t, dur, v):
    events = [e for e in (v.get("events") or []) if isinstance(e, dict)][:6]
    active = _active_index(v.get("active_event"), len(events))
    top = _draw_title(draw, v.get("title"), t) + 20
    n = len(events)
    lx = 200
    spacing = (SAFE_BOTTOM - top - 80) / max(n - 1, 1)
    y_last = top + spacing * (n - 1)

    grow = 1.0 if active is not None else ease_in_out(progress(t, 0, 0.3 + 0.2 * n))
    draw.line((lx, top, lx, top + (y_last - top) * grow), fill=rgba(PALETTE["muted"], 0.6), width=8)

    year_font, label_font = load_font(70), load_font(50, bold=False)
    for i, e in enumerate(events):
        y = top + spacing * i
        if active is None:
            a = ease_out_cubic(progress(t, (0.3 + 0.2 * n) * i / max(n, 1), 0.3))
            is_active = False
        else:
            a, is_active = 1.0, i == active
        col = PALETTE["accent"] if is_active else PALETTE["accent2"] if active is None or i < active else PALETTE["muted"]
        dot = 26 if is_active else 18
        if is_active:
            pulse = (t % 1.0)
            ring = dot + 40 * pulse
            draw.ellipse((lx - ring, y - ring, lx + ring, y + ring),
                         outline=rgba(PALETTE["accent"], 1 - pulse), width=5)
        draw.ellipse((lx - dot, y - dot, lx + dot, y + dot), fill=rgba(col, a))

        tx = lx + 70
        dx = 40 * (1 - ease_out_cubic(progress(t, 0, 0.4))) if is_active else 0
        draw.text((tx + dx, y), str(e.get("year", "")), font=year_font, anchor="ls",
                  fill=rgba(PALETTE["accent"] if is_active else PALETTE["text"], a))
        lf, lines = fit_text(draw, str(e.get("label", "")), W - tx - MARGIN, 2,
                             label_font.size, 30, bold=False)
        ly = y + 14
        for line in lines:
            draw.text((tx + dx, ly), line, font=lf, anchor="lt",
                      fill=rgba(PALETTE["text"] if is_active or active is None else PALETTE["muted"], a))
            ly += line_height(lf)


# ------------------- comparison -------------------

def _comparison(draw, t, dur, v):
    items = [i for i in (v.get("items") or []) if isinstance(i, dict)][:4]
    values = [max(float(i.get("value") or 0), 0.0) for i in items]
    biggest = max(values) or 1.0
    top = _draw_title(draw, v.get("title"), t) + 30
    n = len(items)
    row = min(300, (SAFE_BOTTOM - top) / n)
    top += max(0, (SAFE_BOTTOM - top - n * row) / 2)  # center the bars
    bar_h = row * 0.38
    label_font, value_font = load_font(54), load_font(50)
    max_w = W - 2 * MARGIN

    for i, (item, value) in enumerate(zip(items, values)):
        y = top + row * i
        a = ease_out_cubic(progress(t, 0.12 * i, 0.35))
        lf, lines = fit_text(draw, str(item.get("label", "")), max_w, 1, label_font.size, 30)
        draw.text((MARGIN, y), lines[0] if lines else "", font=lf, anchor="lt",
                  fill=rgba(PALETTE["text"], a))
        by = y + line_height(lf) + 12
        draw.rounded_rectangle((MARGIN, by, MARGIN + max_w, by + bar_h), radius=int(bar_h / 2),
                               fill=rgba(PALETTE["muted"], 0.18 * a))
        grow = ease_out_cubic(progress(t, 0.2 + 0.12 * i, 0.8))
        bw = max(bar_h, max_w * value / biggest * grow)
        col = PALETTE["accent"] if value == biggest else PALETTE["accent2"]
        draw.rounded_rectangle((MARGIN, by, MARGIN + bw, by + bar_h), radius=int(bar_h / 2),
                               fill=rgba(col, a))
        shown = str(item.get("display") or f"{value:g}")
        vw = text_width(draw, shown, value_font)
        inside = bw - vw - 30 > 0
        vx = MARGIN + bw - 24 if inside else MARGIN + bw + 20
        draw.text((vx, by + bar_h / 2), shown, font=value_font, anchor="rm" if inside else "lm",
                  fill=rgba(PALETTE["dark"] if inside else PALETTE["text"], a * grow))


TEMPLATES = {
    "key_phrase": _key_phrase,
    "stat": _stat,
    "process": _process,
    "timeline": _timeline,
    "comparison": _comparison,
}


def render_frame(visual: dict, t: float, duration: float) -> Image.Image:
    """One RGB frame of the diagram at time t (seconds)."""
    drawer = TEMPLATES.get(visual.get("template"), _key_phrase)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    drawer(ImageDraw.Draw(layer), t, duration, visual)
    frame = _background().copy()
    frame.paste(layer, (0, 0), layer)
    return frame


def render_diagram(visual: dict, frames: int, out_path: str) -> str:
    """Render `frames` frames of the diagram to out_path (MP4, 1080x1920, 30fps).

    If the parameters can't be drawn (bad data from the script), falls back to a
    key_phrase card of the description so the slot is still on-topic.
    """
    duration = frames / FPS
    try:
        render_frame(visual, 0.0, duration)
        render_frame(visual, duration, duration)
    except Exception as e:
        log.warning(f"    Diagram '{visual.get('template')}' unusable ({e}); using a text card")
        visual = {"template": "key_phrase",
                  "text": visual.get("text") or visual.get("title") or visual.get("description", "")}
    return encode_frames((render_frame(visual, i / FPS, duration) for i in range(frames)), out_path)
