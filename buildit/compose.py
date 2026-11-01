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
from .config import CAPTION_Y, FPS, H, PALETTE, SAFE_RIGHT, SAFE_TOP, SUBJECT_BAND, W

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


def caption_groups(words: list[dict]) -> list[list[dict]]:
    """1-2 words on screen at a time (the reference). A small word (a, the, and, on...) opens the next group
    instead of trailing the last one ("a bike", "on top"), punctuation and pauses end a group, two content words
    pair only when they are short together."""
    def bare(w):
        return re.sub(r"[^\w']", "", w["text"]).lower()

    groups, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        if nxt is None:
            break
        content = [x for x in cur if bare(x) not in SMALL]
        punct = bool(re.search(r"[.,;:?!]$", w["text"]))
        pause = nxt["start"] - w["end"] > 0.25
        nxt_small = bare(nxt) in SMALL
        pair_ok = len(cur) == 1 and len(bare(w)) + len(bare(nxt)) <= 11
        full = len(cur) >= 3 or (len(cur) >= 2 and content)            # "and the air" may take three
        if full or punct or pause or (content and nxt_small) or (content and not pair_ok):
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
    font-family: 'Poppins', sans-serif; font-weight: 900; font-size: 80px; line-height: 1.05; letter-spacing: -0.01em;
    color: #ffffff; padding: 8px 30px 14px; border-radius: 26px; background: rgba(16, 20, 28, 0.82);
    box-shadow: 0 8px 22px rgba(0, 0, 0, 0.25); transform-origin: 50% 60%; }}
</style>"""
    script = "  const tl = gsap.timeline({ paused: true });\n" + "\n".join(js) + \
             '\n  window.__timelines["captions"] = tl;'
    return _page("captions", duration, "\n".join(body), script, style)


# ------------------------------------------------------------ label pills

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
    lines, js = [], []
    for k, lb in enumerate(labels):
        t0 = max(0.0, lb["t0"] - scene["start"])
        t1 = min(d - 0.05, lb["t1"] - scene["start"])
        if t1 - t0 < 0.5:
            continue
        f_base = int(round(scene["start"] * FPS))
        pts = _track(anchors, lb["anchor"], f_base + int(round(t0 * FPS)) + 1, f_base + int(round(t1 * FPS)) + 1)
        if not pts:
            continue
        lid = f"{sid}-l{k}"
        # beside the part: to the side with more room, a little above the anchor, kept in the safe area
        ax, ay = pts[0][0], pts[0][1]
        right = ax < W * 0.56
        dx = 120 if right else -120
        px = min(max(ax + dx, 60), W - SAFE_RIGHT - 60)
        px = min(px, W - SAFE_RIGHT - 30 - 26 * len(lb["text"])) if right else max(px, 60 + 26 * len(lb["text"]))
        py = min(max(ay - 70, SAFE_TOP + 110), SUBJECT_BAND[1] - 40)     # never under the top UI / the map
        body.append(f'  <div id="{lid}" class="clip lab {"lab-r" if right else "lab-l"}" data-start="{t0:.3f}" '
                    f'data-duration="{t1 - t0:.3f}" data-track-index="{2 + k}" '
                    f'style="left:{px:.0f}px;top:{py:.0f}px">{_pill_html(lid, lb)}</div>')
        if lb.get("line", True):
            lines.append(f'<line id="{lid}-ln" x1="{px:.0f}" y1="{py:.0f}" x2="{ax:.1f}" y2="{ay:.1f}" class="ln"/>'
                         f'<circle id="{lid}-dt" cx="{ax:.1f}" cy="{ay:.1f}" r="7" class="dt"/>')
        follow = [[round(p[0], 1), round(p[1], 1)] for p in pts]
        js.append(f"""  (function () {{
    const P = {json.dumps(follow, separators=(",", ":"))}, step = 1 / {FPS}, t0 = {t0:.3f}, dur = {t1 - t0:.3f};
    const ox = {px:.1f} - P[0][0], oy = {py:.1f} - P[0][1];
    const pill = document.querySelector("#{lid} .pill");
    tl.fromTo(pill, {{ scale: 0.6, opacity: 0 }}, {{ scale: 1, opacity: 1, duration: 0.22, ease: "back.out(2.4)", immediateRender: false }}, t0);
    tl.to("#{lid}", {{ keyframes: P.map((p) => ({{ left: p[0] + ox, top: p[1] + oy, duration: step }})), ease: "none" }}, t0);
    if (document.getElementById("{lid}-ln")) {{
      tl.fromTo(["#{lid}-ln", "#{lid}-dt"], {{ opacity: 0 }}, {{ opacity: 1, duration: 0.2, immediateRender: false }}, t0 + 0.08);
      tl.to("#{lid}-ln", {{ keyframes: P.map((p) => ({{ attr: {{ x1: p[0] + ox, y1: p[1] + oy + 26, x2: p[0], y2: p[1] }}, duration: step }})), ease: "none" }}, t0);
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
    font-family: 'Poppins', sans-serif; font-weight: 800; font-size: 44px; letter-spacing: 0.02em; line-height: 1;
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

MAP_X, MAP_Y, MAP_S = 36, 190, 300          # a small corner diagram, under the app's top UI
FLOW_HEX = {"air": "#f4f8ff", "fuel": "#ffd23a", "hot_gas": "#ff3b1f", "cold_gas": "#5cc8ff",
            "hot_liquid": "#ff8a1a", "cold_liquid": "#2f6bff", "water": "#28c8ff", "steam": "#ffffff",
            "exhaust": "#9a948c", "electricity": "#fff36b", "heat": "#ff6a1a", "oil": "#e0a030"}


def loop_info(sb: dict, words: list[dict], duration: float) -> dict | None:
    """What the corner map shows: the connected machine parts in loop order, the pipes between them and when
    each lights up in which colour, when each part arrives and when it is the one being talked about."""
    from .kit import layout
    conns = [c for c in sb.get("connections", []) if c.get("kind") in ("pipe", "hose", "wire")]
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
    return {"nodes": nodes, "edges": edges, "t_show": t_show}


def loop_map(info: dict, duration: float) -> str:
    import math
    n = len(info["nodes"])
    cx = cy = MAP_S / 2
    r = MAP_S / 2 - 62
    pos = {}
    for k, nd in enumerate(info["nodes"]):
        a = -math.pi / 2 + 2 * math.pi * k / n
        pos[nd["id"]] = (cx + r * math.cos(a), cy + r * math.sin(a))
    svg, js = [], []
    for k, e in enumerate(info["edges"]):
        if e["a"] not in pos or e["b"] not in pos:
            continue
        (x1, y1), (x2, y2) = pos[e["a"]], pos[e["b"]]
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        # bow the pipe outward from the centre, arrow at its middle pointing along the flow
        ox, oy = mx - cx, my - cy
        ln = max(1.0, math.hypot(ox, oy))
        qx, qy = mx + ox / ln * 26, my + oy / ln * 26
        ang = math.degrees(math.atan2(y2 - y1, x2 - x1))
        ax, ay = 0.25 * x1 + 0.5 * qx + 0.25 * x2, 0.25 * y1 + 0.5 * qy + 0.25 * y2
        svg.append(f'<path id="lm-e{k}" class="lm-e" d="M{x1:.1f},{y1:.1f} Q{qx:.1f},{qy:.1f} {x2:.1f},{y2:.1f}"/>'
                   f'<polygon id="lm-a{k}" class="lm-a" points="-9,-7 9,0 -9,7" '
                   f'transform="translate({ax:.1f},{ay:.1f}) rotate({ang:.1f})"/>')
        js.append(f'  tl.fromTo(["#lm-e{k}", "#lm-a{k}"], {{ opacity: 0 }}, {{ opacity: 1, duration: 0.3, '
                  f'immediateRender: false }}, {e["t_in"]:.3f});')
        for tf, kind, on in e["flows"]:
            col = FLOW_HEX.get(kind or "", "#ffffff") if on else "#8e98a3"
            js.append(f'  tl.to("#lm-e{k}", {{ stroke: "{col}", duration: 0.3 }}, {tf:.3f});')
            js.append(f'  tl.to("#lm-a{k}", {{ fill: "{col}", duration: 0.3 }}, {tf:.3f});')
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
    t_show = info["t_show"]
    body = (f'  <div id="lm" class="clip" data-start="{t_show:.3f}" data-duration="{duration - t_show:.3f}" '
            f'data-track-index="1">\n'
            f'    <svg class="lm-svg" viewBox="0 0 {MAP_S} {MAP_S}">{"".join(svg)}</svg>\n'
            f'    {"".join(body_nodes)}\n  </div>')
    js.insert(0, f'  tl.fromTo("#lm", {{ opacity: 0, y: -12 }}, {{ opacity: 1, y: 0, duration: 0.4, '
                 f'immediateRender: false }}, {t_show:.3f});')
    style = f"""<style>
  {_fonts_css()}
  #root {{ position: absolute; inset: 0; }}
  #root #lm {{ position: absolute; left: {MAP_X}px; top: {MAP_Y}px; width: {MAP_S}px; height: {MAP_S}px; opacity: 0;
    border-radius: 32px; background: rgba(16, 20, 28, 0.72); box-shadow: 0 10px 26px rgba(0, 0, 0, 0.22); }}
  #root .lm-svg {{ position: absolute; inset: 0; width: {MAP_S}px; height: {MAP_S}px; }}
  #root .lm-e {{ fill: none; stroke: #8e98a3; stroke-width: 7; stroke-linecap: round; opacity: 0; }}
  #root .lm-a {{ fill: #8e98a3; opacity: 0; }}
  #root .lm-n {{ position: absolute; width: 0; height: 0; opacity: 0; }}
  #root .lm-n span {{ position: absolute; white-space: nowrap; display: inline-block;
    padding: 5px 11px; border-radius: 12px; background: #ffffff; color: #10141c;
    font-family: 'Poppins', sans-serif; font-weight: 800; font-size: 19px; letter-spacing: 0.02em; }}
</style>"""
    script = ("  gsap.set('#lm .lm-n span', { xPercent: -50, yPercent: -50 });\n"
              "  const tl = gsap.timeline({ paused: true });\n" + "\n".join(js) +
              '\n  window.__timelines["loopmap"] = tl;')
    return _page("loopmap", duration, body, script, style)
