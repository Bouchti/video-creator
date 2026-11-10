"""
HyperFrames composition for Build-It videos (docs/style_guide.md, sections 5-6): rendered shots, word-pop
captions (1-2 words, white heavy rounded sans, dark outline), label pills beside the parts they name (following
the Blender anchors, with an optional leader line), the mix. Follows the HyperFrames contract: every timed
element has data-start / data-duration, one paused timeline per composition registered last, initial hidden
states in CSS, no clocks or randomness.

    project(out_dir, scenes, words, labels, mix_wav, duration, title)

scenes: [{"id", "video": abs path, "start", "end", "anchors": abs path to anchors.json}]
words:  [{"text", "start", "end"}]          (word timestamps, never guessed)
labels: [{"scene", "text", "variant": neutral|warn|air|done|chip, "anchor", "t0", "t1", "line": bool}]
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil

from .assets.fetch import font
from .config import CAPTION_Y, FPS, H, PALETTE, SAFE_RIGHT, SUBJECT_BAND, W

GSAP = "https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js"
ICONS = {   # tiny inline icons (24 px viewBox), stroke = currentColor
    "flame": '<path d="M12 3c1 3 4 4.5 4 8.5A4 4 0 0 1 8 11.5c0-1.5.7-2.6 1.5-3.4C9.8 9.6 11 10 11 8.5 11 6.6 12 4.6 12 3z"/>',
    "wind": '<path d="M3 9h11a3 3 0 1 0-3-3M3 15h15a3 3 0 1 1-3 3M3 12h8"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
    "bolt": '<path d="M13 3L5 13.5h6L10 21l8-10.5h-6L13 3z"/>',
    "drop": '<path d="M12 3.5c3 4 5.5 7 5.5 10a5.5 5.5 0 0 1-11 0c0-3 2.5-6 5.5-10z"/>',
    "turn": '<path d="M19 12a7 7 0 1 1-2.1-5M19 4v4h-4"/>',
}
VARIANT_ICON = {"warn": "flame", "air": "wind", "done": "check"}


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def _page(comp_id: str, duration: float, body: str, script: str, style: str = "") -> str:
    return f"""<template>
{style}
<div id="root" data-composition-id="{comp_id}" data-width="{W}" data-height="{H}" data-duration="{duration:.3f}">
{body}
</div>
<script>
{script}
</script>
</template>
"""


def _fonts_css() -> str:
    return ("@font-face { font-family: 'Poppins'; src: url('assets/fonts/Poppins-Black.ttf') format('truetype'); "
            "font-weight: 900; font-display: block; }\n"
            "@font-face { font-family: 'Poppins'; src: url('assets/fonts/Poppins-ExtraBold.ttf') format('truetype'); "
            "font-weight: 800; font-display: block; }")


# ------------------------------------------------------------ captions

SMALL = {"a", "an", "the", "to", "of", "in", "on", "and", "or", "it", "you", "your", "its", "is", "at", "by",
         "for", "so", "but", "with", "no", "too", "this", "that", "up", "into", "onto", "from", "than", "then",
         "as", "are", "was", "be", "has", "had", "each", "every", "more", "just", "now"}


CAPTION_CHARS = 20          # one line at the caption size


def caption_groups(words: list[dict]) -> list[list[dict]]:
    """Short whole phrases (up to 4 words / one line), so a sentence reads in a few calm steps instead of
    one-word flashes. Punctuation and pauses end a phrase; a phrase never ends on a small word (a, the, and,
    on...): it opens the next one instead ("a bike", "on top")."""
    def bare(w):
        return re.sub(r"[^\w']", "", w["text"]).lower()

    groups, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        if nxt is None:
            break
        text = " ".join(x["text"] for x in cur)
        punct = bool(re.search(r"[.,;:?!]$", w["text"]))
        pause = nxt["start"] - w["end"] > 0.25
        full = len(cur) >= 4 or len(text) + 1 + len(nxt["text"]) > CAPTION_CHARS
        if punct or pause or full:
            if not punct and len(cur) > 1 and bare(w) in SMALL:
                cur.pop()
                groups.append(cur)
                cur = [w]
            else:
                groups.append(cur)
                cur = []
    if cur:
        groups.append(cur)
    return groups


def captions_scene(words: list[dict], duration: float) -> str:
    groups = caption_groups(words)
    body, js = [], []
    for k, g in enumerate(groups):
        start = max(0.05, g[0]["start"] - 0.04)
        nxt = groups[k + 1][0]["start"] - 0.04 if k + 1 < len(groups) else duration
        end = min(max(g[-1]["end"] + 0.12, start + 0.32), nxt, duration)
        text = " ".join(w["text"] for w in g)
        gid = f"cg{k}"
        body.append(f'  <div id="{gid}" class="clip cg" data-start="{start:.3f}" data-duration="{end - start:.3f}" '
                    f'data-track-index="1"><span class="cg-in">{esc(text)}</span></div>')
        js.append(f'  tl.fromTo("#{gid} .cg-in", {{ scale: 0.86, opacity: 0 }}, {{ scale: 1, opacity: 1, '
                  f'duration: 0.09, ease: "back.out(2.2)", immediateRender: false }}, {start:.3f});')
    style = f"""<style>
  {_fonts_css()}
  #root {{ position: absolute; inset: 0; }}
  #root .cg {{ position: absolute; left: 0; width: {W}px; top: {CAPTION_Y[0]}px; height: {CAPTION_Y[1] - CAPTION_Y[0]}px;
    display: flex; align-items: center; justify-content: center; }}
  #root .cg-in {{ display: inline-block; opacity: 0; max-width: {W - 2 * SAFE_RIGHT}px; text-align: center;
    font-family: 'Poppins', sans-serif; font-weight: 900; font-size: 68px; line-height: 1.05; letter-spacing: -0.01em;
    color: #ffffff; padding: 8px 30px 14px; border-radius: 26px; background: rgba(16, 20, 28, 0.82);
    box-shadow: 0 8px 22px rgba(0, 0, 0, 0.25); transform-origin: 50% 60%; }}
</style>"""
    script = "  const tl = gsap.timeline({ paused: true });\n" + "\n".join(js) + \
             '\n  window.__timelines["captions"] = tl;'
    return _page("captions", duration, "\n".join(body), script, style)


# ------------------------------------------------------------ label pills

PILL_H = 72                 # a pill's height in master pixels (44 px text, padding, border)
PILL_PX = 50                # label text size: readable on a phone
SETTLE = 1.1                # seconds into a shot before a label shows: the camera has finished its glide


def label_times(sb: dict, words: list[dict]) -> list[tuple[dict, float, float]]:
    """(label, t0, t1) of every label: from its word (but never while the camera is still gliding into a new
    shot) until its until_word, at least 1.6 s."""
    W = words
    starts = [max(0.0, W[min(s["start_word"], len(W) - 1)]["start"] - 0.12) for s in sb.get("shots", [])]
    out = []
    for lb in sb.get("labels", []):
        t0 = W[min(lb["word"], len(W) - 1)]["start"]
        cut = max((s for s in starts if s <= t0 + 0.8), default=None)     # incl. a cut just after its word
        if cut is not None and cut > 0 and t0 < cut + SETTLE:
            t0 = cut + SETTLE
        t1 = max(W[min(lb["until_word"], len(W) - 1)]["start"], t0 + 1.6)
        out.append((lb, t0, t1))
    return out
_FONTS: dict = {}


def _measure(name: str, px: int, text: str) -> float:
    from PIL import ImageFont
    if (name, px) not in _FONTS:
        _FONTS[(name, px)] = ImageFont.truetype(font(name), px)
    return _FONTS[(name, px)].getlength(text)


def pill_width(lb: dict) -> float:
    """The real width of a label pill (measured with its font, letter spacing, padding, border and icon)."""
    icon = (lb.get("icon") or VARIANT_ICON.get(lb.get("variant", "neutral"))) in ICONS
    txt = lb["text"].upper()
    return _measure("Poppins-ExtraBold.ttf", PILL_PX, txt) + 1.0 * len(txt) + 50 + (52 if icon else 0)


def caption_rect(words: list[dict], t: float):
    """(x0, y0, x1, y1) of the caption group on screen at time t, or None."""
    g = next((g for g in caption_groups(words) if g[0]["start"] - 0.05 <= t <= g[-1]["end"] + 0.15), None)
    if not g:
        return None
    bw = _measure("Poppins-Black.ttf", 68, " ".join(w["text"] for w in g))
    cy = (CAPTION_Y[0] + CAPTION_Y[1]) / 2
    return (W / 2 - bw / 2 - 30, cy - 52, W / 2 + bw / 2 + 30, cy + 52)


def _overlap(a, b) -> float:
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def place_pill(ax: float, ay: float, pw: float, boxes: dict, map_on: bool = False, taken=()) -> tuple[float, float]:
    """Top-left of a pill pw wide for a part anchored at (ax, ay): the spot nearest the anchor that covers no
    part on screen (boxes: {id: rect} from anchors.json; the machine body counts less than a part, so inside a
    close shot the pill sits on the cabinet, never on a part), inside the safe area, under the loop strip and
    above the captions. The leader line bridges the distance."""
    top = (MAP_Y + MAP_H + 16) if map_on else 190
    bottom = CAPTION_Y[0] - 24 - PILL_H
    x_lo, x_hi = 40, W - SAFE_RIGHT - pw
    xs = {x_lo, x_hi, ax + 70, ax - 70 - pw, ax - pw / 2}
    best, cost_best = (x_lo, top), None
    for x in xs:
        x = min(max(x, x_lo), max(x_lo, x_hi))
        for dy in range(-480, 481, 40):
            y = min(max(ay - PILL_H / 2 + dy, top), bottom)
            r = (x, y, x + pw, y + PILL_H)
            cover = sum(_overlap(r, b) * (1.0 if gid == "machine" else 4.0) for gid, b in boxes.items())
            cover += sum(_overlap(r, b) * 8.0 for b in taken)
            dist = ((x + pw / 2 - ax) ** 2 + (y + PILL_H / 2 - ay) ** 2) ** 0.5
            cost = 1000 * cover / (pw * PILL_H) + 0.5 * dist
            if cost_best is None or cost < cost_best:
                best, cost_best = (x, y), cost
    return best


STATE_WORDS = ("GAS", "LIQUID", "°", "PRESSURE")
PART_WORDS = {"EVAPORATOR", "COMPRESSOR", "CONDENSER", "CAPILLARY", "THERMOSTAT", "COIL", "VALVE", "PUMP", "MOTOR",
              "FAN", "NOZZLE", "TUBE", "PISTON", "RADIATOR", "BURNER", "HEATER", "GAUGE", "TURBINE", "SPRING", "LEVER",
              "GEAR", "SHAFT", "WHEEL", "BELT", "FLYWHEEL", "CRANK", "BATTERY", "BULB", "MAGNET", "FILTER", "DRUM"}


def is_title(lb: dict) -> bool:
    """A label for the whole machine or for an IDEA (LOOP CLOSED, MOVES HEAT, COLDER THAN KITCHEN), not for a part,
    a number or a flow state: a title pill at the top, no leader line (a line from an idea to a part points at
    nothing)."""
    if str(lb.get("anchor", "")).startswith("machine"):
        return True
    t = str(lb.get("text", "")).upper()
    if any(ch.isdigit() for ch in t) or any(w in t for w in STATE_WORDS):
        return False
    words = set(t.replace("-", " ").split())
    return not (words & PART_WORDS) and not any(p.upper().replace("_", " ") in t for p in _part_types())


def _part_types():
    from .kit import vocab
    return list(vocab.PARTS)


def first_visible(pts: list, start: int = 0) -> int | None:
    """Index of the first tracked anchor sample that is on screen and not hidden behind geometry."""
    return next((i for i in range(start, len(pts)) if len(pts[i]) < 3 or pts[i][2]), None)


def title_spot(pw: float, map_on: bool) -> tuple[float, float]:
    return W / 2 - pw / 2, (MAP_Y + MAP_H + 24) if map_on else 200


def leader_start(px: float, py: float, pw: float, ax: float) -> tuple[float, float]:
    """Where a pill's leader line leaves it: the pill edge facing the anchor."""
    x = px if ax < px else (px + pw if ax > px + pw else ax)
    return x, py + PILL_H / 2


def _track(anchors: dict, name: str, f0: int, f1: int):
    pts, last = [], None
    for f in range(f0, f1 + 1):
        p = anchors["frames"].get(str(f), {}).get(name) or last
        if p is not None:
            pts.append(p)
            last = p
    return pts


def _pill_html(lid: str, lb: dict) -> str:
    v = lb.get("variant", "neutral")
    icon = lb.get("icon") or VARIANT_ICON.get(v)
    ic = (f'<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" '
          f'stroke-linecap="round" stroke-linejoin="round">{ICONS[icon]}</svg>') if icon in ICONS else ""
    return f'<div class="pill pill-{v}">{ic}<span>{esc(lb["text"].upper())}</span></div>'


def scene_page(scene: dict, labels: list[dict]) -> str:
    """One shot: its footage, plus the label pills of that shot following their anchors."""
    sid, d = scene["id"], scene["end"] - scene["start"]
    anchors = json.load(open(scene["anchors"], encoding="utf-8")) if scene.get("anchors") else {"frames": {}}
    body = [f'  <video id="{sid}-v" class="clip" data-start="0" data-duration="{d:.3f}" data-track-index="0" '
            f'src="assets/shots/{sid}.mp4" muted playsinline></video>']
    lines, js, taken = [], [], []
    for k, lb in enumerate(labels):
        t0 = max(0.0, lb["t0"] - scene["start"])
        t1 = min(d - 0.05, lb["t1"] - scene["start"])
        if t1 - t0 < 0.5:
            continue
        f_base = int(round(scene["start"] * FPS))
        pts = _track(anchors, lb["anchor"], f_base + int(round(t0 * FPS)) + 1, f_base + int(round(t1 * FPS)) + 1)
        if not pts:
            continue
        if not is_title(lb):                        # a pill waits until what it names is in sight (or never shows)
            i0 = first_visible(pts)
            if i0 is None or t1 - (t0 + i0 / FPS) < 0.8:
                continue
            t0, pts = t0 + i0 / FPS, pts[i0:]
        lid = f"{sid}-l{k}"
        # on the free spot nearest the part (measured against every part on screen), a leader line to it
        ax, ay = pts[0][0], pts[0][1]
        pw = pill_width(lb)
        f0 = f_base + int(round(t0 * FPS)) + 1
        bx = anchors.get("boxes", {}).get(str(f0), {})
        if is_title(lb):                            # a title pill: still, at the top, no line
            px, py = title_spot(pw, bool(scene.get("map_on")))
            pts = [pts[0]] * len(pts)
            lb = dict(lb, line=False)
        else:
            px, py = place_pill(ax, ay, pw, bx, map_on=bool(scene.get("map_on")), taken=taken)
        taken.append((px, py, px + pw, py + PILL_H))
        lx, ly = leader_start(px, py, pw, ax)
        body.append(f'  <div id="{lid}" class="clip lab lab-r" data-start="{t0:.3f}" '
                    f'data-duration="{t1 - t0:.3f}" data-track-index="{2 + k}" '
                    f'style="left:{px:.0f}px;top:{py:.0f}px">{_pill_html(lid, lb)}</div>')
        if lb.get("line", True):
            lines.append(f'<line id="{lid}-ln" x1="{lx:.0f}" y1="{ly:.0f}" x2="{ax:.1f}" y2="{ay:.1f}" class="ln"/>'
                         f'<circle id="{lid}-dt" cx="{ax:.1f}" cy="{ay:.1f}" r="7" class="dt"/>')
        follow = [[round(p[0], 1), round(p[1], 1)] for p in pts]
        js.append(f"""  (function () {{
    const P = {json.dumps(follow, separators=(",", ":"))}, step = 1 / {FPS}, t0 = {t0:.3f}, dur = {t1 - t0:.3f};
    const ox = {px:.1f} - P[0][0], oy = {py:.1f} - P[0][1], lx = {lx:.1f} - P[0][0], ly = {ly:.1f} - P[0][1];
    const pill = document.querySelector("#{lid} .pill");
    tl.fromTo(pill, {{ scale: 0.6, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.22, ease: "back.out(2.4)", immediateRender: false }}, t0);
    tl.to("#{lid}", {{ keyframes: P.map((p) => ({{ left: p[0] + ox, top: p[1] + oy, duration: step }})), ease: "none" }}, t0);
    if (document.getElementById("{lid}-ln")) {{
      tl.fromTo(["#{lid}-ln", "#{lid}-dt"], {{ opacity: 0 }}, {{ opacity: 1, duration: 0.2, immediateRender: false }}, t0 + 0.08);
      tl.to("#{lid}-ln", {{ keyframes: P.map((p) => ({{ attr: {{ x1: p[0] + lx, y1: p[1] + ly, x2: p[0], y2: p[1] }}, duration: step }})), ease: "none" }}, t0);
      tl.to("#{lid}-dt", {{ keyframes: P.map((p) => ({{ attr: {{ cx: p[0], cy: p[1] }}, duration: step }})), ease: "none" }}, t0);
      tl.to(["#{lid}-ln", "#{lid}-dt"], {{ opacity: 0, duration: 0.15 }}, t0 + dur - 0.18);
    }}
    tl.to(pill, {{ scale: 0.8, opacity: 0, duration: 0.15, ease: "power2.in" }}, t0 + dur - 0.18);
  }})();""")
    body.insert(1, f'  <svg id="{sid}-svg" class="lines" viewBox="0 0 {W} {H}" data-layout-ignore>{"".join(lines)}</svg>')
    style = f"""<style>
  {_fonts_css()}
  #root {{ position: absolute; inset: 0; }}
  #{sid}-v {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; object-fit: cover; }}
  #root .lines {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; overflow: visible; }}
  #root .ln {{ stroke: {PALETTE['outline']}; stroke-width: 3.5; opacity: 0; filter: drop-shadow(0 1px 2px rgba(255,255,255,0.6)); }}
  #root .dt {{ fill: #ffd23a; stroke: {PALETTE['outline']}; stroke-width: 3; opacity: 0; }}
  #root .lab {{ position: absolute; width: 0; height: 0; overflow: visible; }}
  #root .pill {{ position: absolute; top: 0; display: inline-flex; align-items: center; gap: 10px; white-space: nowrap;
    padding: 10px 20px; border-radius: 999px; border: 3px solid {PALETTE['outline']}; opacity: 0;
    font-family: 'Poppins', sans-serif; font-weight: 800; font-size: {PILL_PX}px; letter-spacing: 0.02em; line-height: 1;
    background: {PALETTE['pill']}; color: {PALETTE['pill_ink']}; box-shadow: 0 6px 16px rgba(0, 0, 0, 0.28); }}
  #root .lab-r .pill {{ left: 0; transform-origin: 0% 50%; }}
  #root .lab-l .pill {{ right: 0; transform-origin: 100% 50%; }}
  #root .pill .ic {{ width: 38px; height: 38px; }}
  #root .pill-warn {{ background: {PALETTE['warn_bg']}; border-color: {PALETTE['warn']}; color: #6a2a07; }}
  #root .pill-warn .ic {{ color: {PALETTE['warn']}; }}
  #root .pill-air {{ background: {PALETTE['air_bg']}; border-color: {PALETTE['air']}; color: #123b6b; }}
  #root .pill-air .ic {{ color: {PALETTE['air']}; }}
  #root .pill-done {{ background: {PALETTE['done_bg']}; border-color: {PALETTE['done']}; color: #0f4d29; }}
  #root .pill-done .ic {{ color: {PALETTE['done']}; }}
  #root .pill-chip {{ background: {PALETTE['chip']}; border-color: {PALETTE['chip']}; color: #ffffff; border-radius: 12px; }}
</style>"""
    script = "  const tl = gsap.timeline({ paused: true });\n" + "\n".join(js) + f'\n  window.__timelines["{sid}"] = tl;'
    return _page(sid, d, "\n".join(body), script, style)


# ------------------------------------------------------------ root + project

def index_html(scenes: list[dict], duration: float, title: str, loopmap: bool = False) -> str:
    hosts = [f'    <div id="{s["id"]}" data-composition-id="{s["id"]}" data-composition-src="compositions/{s["id"]}.html" '
             f'data-start="{s["start"]:.3f}" data-duration="{s["end"] - s["start"]:.3f}" data-track-index="1" '
             f'data-width="{W}" data-height="{H}" class="layer shot"></div>' for s in scenes]
    hosts.append(f'    <div id="captions" data-composition-id="captions" data-composition-src="compositions/captions.html" '
                 f'data-start="0" data-duration="{duration:.3f}" data-track-index="5" data-track-kind="captions" '
                 f'data-width="{W}" data-height="{H}" class="layer captions"></div>')
    if loopmap:
        hosts.append(f'    <div id="loopmap" data-composition-id="loopmap" data-composition-src="compositions/loopmap.html" '
                     f'data-start="0" data-duration="{duration:.3f}" data-track-index="4" '
                     f'data-width="{W}" data-height="{H}" class="layer loopmap"></div>')
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <title>{esc(title)}</title>
    <script src="{GSAP}"></script>
    <style>
      html, body {{ margin: 0; width: {W}px; height: {H}px; overflow: hidden; background: #8a847e; }}
      .layer {{ position: absolute; inset: 0; }}
      .layer.shot {{ z-index: 1; }}
      .layer.captions {{ z-index: 10; }}
      .layer.loopmap {{ z-index: 8; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{duration:.3f}" data-width="{W}" data-height="{H}">
{chr(10).join(hosts)}
    <audio id="mix" class="clip" data-start="0" data-duration="{duration:.3f}" data-track-index="7" src="assets/audio/mix.wav" data-volume="1"></audio>
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      window.__timelines["main"] = gsap.timeline({{ paused: true }});
    </script>
  </body>
</html>
"""


def _link(src: str, dst: str):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        os.remove(dst)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


def project(out_dir: str, scenes: list[dict], words: list[dict], labels: list[dict], mix_wav: str,
            duration: float, title: str, loop: dict | None = None) -> str:
    """Write (or refresh) the HyperFrames project; returns its directory."""
    from cutaway import hf
    if not os.path.exists(os.path.join(out_dir, "hyperframes.json")):
        os.makedirs(os.path.dirname(out_dir), exist_ok=True)
        hf.run(["init", out_dir], cwd=os.path.dirname(out_dir))
    comp = os.path.join(out_dir, "compositions")
    os.makedirs(comp, exist_ok=True)
    for f in os.listdir(comp):
        if f.endswith(".html"):
            os.remove(os.path.join(comp, f))
    for name in ("Poppins-Black.ttf", "Poppins-ExtraBold.ttf"):
        _link(font(name), os.path.join(out_dir, "assets", "fonts", name))
    for s in scenes:
        _link(s["video"], os.path.join(out_dir, "assets", "shots", f"{s['id']}.mp4"))
        s = dict(s, map_on=map_visible(loop, (s["start"] + s["end"]) / 2))
        with open(os.path.join(comp, f"{s['id']}.html"), "w", encoding="utf-8") as fh:
            fh.write(scene_page(s, [lb for lb in labels if lb["scene"] == s["id"]]))
    with open(os.path.join(comp, "captions.html"), "w", encoding="utf-8") as fh:
        fh.write(captions_scene(words, duration))
    if loop:
        with open(os.path.join(comp, "loopmap.html"), "w", encoding="utf-8") as fh:
            fh.write(loop_map(loop, duration))
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(index_html(scenes, duration, title, loopmap=bool(loop)))
    _link(mix_wav, os.path.join(out_dir, "assets", "audio", "mix.wav"))
    return out_dir


# ------------------------------------------------------------ the loop map

MAP_X, MAP_Y, MAP_W, MAP_H = 24, 175, 1032, 140    # the loop strip across the top, under the app's top UI
FLOW_HEX = {"air": "#f4f8ff", "fuel": "#ffd23a", "hot_gas": "#ff3b1f", "cold_gas": "#9fe6ff",
            "hot_liquid": "#ff8a1a", "cold_liquid": "#1e40ff", "water": "#28c8ff", "steam": "#ffffff",
            "exhaust": "#9a948c", "electricity": "#fff36b", "heat": "#ff6a1a", "oil": "#e0a030"}


def loop_info(sb: dict, words: list[dict], duration: float) -> dict | None:
    """What the corner map shows: the connected machine parts in loop order, the pipes between them and when
    each lights up in which colour, when each part arrives and when it is the one being talked about."""
    from .kit import layout
    conns = [c for c in sb.get("connections", []) if c.get("kind") in ("pipe", "hose")]   # what flows round
    if len(conns) < 2:
        return None
    span = layout.spans(sb, words, duration)

    def t(i):
        return words[max(0, min(int(i), len(words) - 1))]["start"]
    nxt = {}
    for c in conns:
        nxt.setdefault(c["from"].split(".")[0], c["to"].split(".")[0])
    first = min(nxt, key=lambda p: span.get(p, (0, 0))[0])
    order, p = [], first
    while p is not None and p not in order:
        order.append(p)
        p = nxt.get(p)
    for c in conns:                                   # parts off the main cycle still get a node
        for q in (c["from"].split(".")[0], c["to"].split(".")[0]):
            if q not in order:
                order.append(q)
    types = {x["id"]: x["type"] for x in sb["parts"]}
    names = {}
    for lb in sb.get("labels", []):
        pid = lb["anchor"].split(".")[0]
        if pid in types and pid not in names and not re.search(r"\d", lb["text"]):
            names[pid] = lb["text"].upper()
    nodes = []
    for pid in order:
        if pid not in types:
            continue
        name = names.get(pid, types[pid].replace("_", " ").upper())
        hl = [(span[pid][0] + 0.55, span[pid][0] + 2.4)]
        for e in sb.get("events", []):
            if e["do"] == "highlight" and str(e.get("target", "")).split(".")[0] == pid and e.get("on") is not False:
                hl.append((t(e["word"]), t(e["word"]) + 2.6))
        if len(name) > 11:                            # EXPANSION NOZZLE -> NOZZLE
            name = max(name.split(), key=len) if len(name.split()) > 1 else name[:11]
        nodes.append({"id": pid, "name": name[:11], "t_in": span[pid][0] + 0.55, "hl": hl})
    edges = []
    for c in conns:
        a, b = c["from"].split(".")[0], c["to"].split(".")[0]
        flows = [(t(e["word"]), e.get("kind"), e.get("on", True) is not False) for e in sb.get("events", [])
                 if e["do"] == "flow" and e.get("target") == c["id"]]
        edges.append({"id": c["id"], "a": a, "b": b, "t_in": max(span[a][0], span[b][0]) + 1.25,
                      "flows": sorted(flows, key=lambda f: f[0])})
    t_show = min(e["t_in"] for e in edges)
    # the strip is shown on the whole-machine and area shots (where the loop is on screen to be read), not over
    # the close-ups, where it would sit on the subject
    shots = sorted(sb.get("shots", []), key=lambda s: s["start_word"])
    show = []
    for i, s in enumerate(shots):
        if s.get("frame") != "machine":
            continue
        a = max(t(s["start_word"]), t_show)
        b = t(shots[i + 1]["start_word"]) if i + 1 < len(shots) else duration
        if b - a < 1.0:
            continue
        if show and a - show[-1][1] < 0.05:
            show[-1] = (show[-1][0], b)
        else:
            show.append((a, b))
    return {"nodes": nodes, "edges": edges, "t_show": t_show, "show": show}


def map_visible(info: dict | None, t: float) -> bool:
    return bool(info) and any(a <= t <= b for a, b in info.get("show", []))


def map_font_px(info: dict) -> int:
    """The largest strip text (up to 36 px) at which every node, MEASURED in its font, fits its slot of the strip
    with room for the arrows between them."""
    n = max(1, len(info["nodes"]))
    for fp in range(36, 17, -1):
        if all(_measure("Poppins-ExtraBold.ttf", fp, nd["name"]) + 26 + 34 <= MAP_W / n for nd in info["nodes"]):
            return fp
    return 18


def loop_geometry(info: dict) -> dict:
    """The strip's layout (pixels inside it): nodes left to right in loop order, a straight arrow between
    neighbours, and the pipe that closes the loop drawn as a return path under them.
    {"nodes": {id: (x, y, w)}, "edges": {edge id: {"pts": [...], "arrow": (x, y, degrees)}}}"""
    n = len(info["nodes"])
    fp = map_font_px(info)
    y = 50
    nodes = {}
    for i, nd in enumerate(info["nodes"]):
        nodes[nd["id"]] = (MAP_W * (i + 0.5) / n, y, _measure("Poppins-ExtraBold.ttf", fp, nd["name"]) + 26)
    order = [nd["id"] for nd in info["nodes"]]
    edges = {}
    for e in info["edges"]:
        if e["a"] not in nodes or e["b"] not in nodes:
            continue
        (xa, _, wa), (xb, _, wb) = nodes[e["a"]], nodes[e["b"]]
        if order.index(e["b"]) == order.index(e["a"]) + 1:
            x0, x1 = xa + wa / 2 + 8, xb - wb / 2 - 10
            edges[e["id"]] = {"pts": [(x0, y), (x1, y)], "arrow": (x1 - 2, y, 0.0)}
        else:                                    # back along the bottom of the strip
            low = y + 58
            pts = [(xa, y + 20), (xa, low), (xb, low), (xb, y + 22)]
            edges[e["id"]] = {"pts": pts, "arrow": ((xa + xb) / 2, low, 180.0 if xb < xa else 0.0)}
    return {"nodes": nodes, "edges": edges}


def loop_map(info: dict, duration: float) -> str:
    geo_ = loop_geometry(info)
    svg, js = [], []
    for k, e in enumerate(info["edges"]):
        g = geo_["edges"].get(e["id"])
        if not g:
            continue
        d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in g["pts"])
        ax, ay, ang = g["arrow"]
        svg.append(f'<path id="lm-e{k}" class="lm-e" d="{d}"/>'
                   f'<polygon id="lm-a{k}" class="lm-a" points="-11,-9 11,0 -11,9" '
                   f'transform="translate({ax:.1f},{ay:.1f}) rotate({ang:.1f})"/>')
        js.append(f'  tl.fromTo(["#lm-e{k}", "#lm-a{k}"], {{ opacity: 0 }}, {{ opacity: 1, duration: 0.3, '
                  f'immediateRender: false }}, {e["t_in"]:.3f});')
        for tf, kind, on in e["flows"]:
            col = FLOW_HEX.get(kind or "", "#ffffff") if on else "#8e98a3"
            js.append(f'  tl.to("#lm-e{k}", {{ stroke: "{col}", duration: 0.3 }}, {tf:.3f});')
            js.append(f'  tl.to("#lm-a{k}", {{ fill: "{col}", duration: 0.3 }}, {tf:.3f});')
    pos = {pid: (x, y) for pid, (x, y, _w) in geo_["nodes"].items()}
    body_nodes = []
    for k, nd in enumerate(info["nodes"]):
        x, y = pos[nd["id"]]
        body_nodes.append(f'<div id="lm-n{k}" class="lm-n" style="left:{x:.0f}px;top:{y:.0f}px">'
                          f'<span>{esc(nd["name"])}</span></div>')
        js.append(f'  tl.fromTo("#lm-n{k}", {{ scale: 0.4, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.3, '
                  f'ease: "back.out(2)", immediateRender: false }}, {max(nd["t_in"], info["t_show"]):.3f});')
        for a, b in nd["hl"]:
            a = max(a, info["t_show"])
            if b - a < 0.4:
                continue
            js.append(f'  tl.to("#lm-n{k} span", {{ backgroundColor: "#ffd23a", color: "#10141c", scale: 1.12, '
                      f'duration: 0.2 }}, {a:.3f});')
            js.append(f'  tl.to("#lm-n{k} span", {{ backgroundColor: "#ffffff", color: "#10141c", scale: 1, '
                      f'duration: 0.25 }}, {b:.3f});')
    t_show = info["show"][0][0] if info.get("show") else info["t_show"]
    body = (f'  <div id="lm" class="clip" data-start="{t_show:.3f}" data-duration="{duration - t_show:.3f}" '
            f'data-track-index="1">\n'
            f'    <svg class="lm-svg" viewBox="0 0 {MAP_W} {MAP_H}">{"".join(svg)}</svg>\n'
            f'    {"".join(body_nodes)}\n  </div>')
    for a, b in reversed(info.get("show") or [(t_show, duration)]):
        js.insert(0, f'  tl.to("#lm", {{ opacity: 0, duration: 0.3 }}, {max(a, b - 0.3):.3f});')
        js.insert(0, f'  tl.fromTo("#lm", {{ opacity: 0, y: -12 }}, {{ opacity: 1, y: 0, duration: 0.35, '
                     f'immediateRender: false }}, {a:.3f});')
    style = f"""<style>
  {_fonts_css()}
  #root {{ position: absolute; inset: 0; }}
  #root #lm {{ position: absolute; left: {MAP_X}px; top: {MAP_Y}px; width: {MAP_W}px; height: {MAP_H}px; opacity: 0;
    border-radius: 30px; background: rgba(16, 20, 28, 0.72); box-shadow: 0 10px 26px rgba(0, 0, 0, 0.22); }}
  #root .lm-svg {{ position: absolute; inset: 0; width: {MAP_W}px; height: {MAP_H}px; }}
  #root .lm-e {{ fill: none; stroke: #8e98a3; stroke-width: 7; stroke-linecap: round; stroke-linejoin: round;
    opacity: 0; }}
  #root .lm-a {{ fill: #8e98a3; opacity: 0; }}
  #root .lm-n {{ position: absolute; width: 0; height: 0; opacity: 0; }}
  #root .lm-n span {{ position: absolute; white-space: nowrap; display: inline-block;
    padding: 6px 13px; border-radius: 14px; background: #ffffff; color: #10141c;
    font-family: 'Poppins', sans-serif; font-weight: 800; font-size: {map_font_px(info)}px; letter-spacing: 0.01em; }}
</style>"""
    script = ("  gsap.set('#lm .lm-n span', { xPercent: -50, yPercent: -50 });\n"
              "  const tl = gsap.timeline({ paused: true });\n" + "\n".join(js) +
              '\n  window.__timelines["loopmap"] = tl;')
    return _page("loopmap", duration, body, script, style)
