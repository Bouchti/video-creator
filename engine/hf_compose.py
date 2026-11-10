"""
HyperFrames post-production for Blender films (engine/make_film.py, films with "compose": "hyperframes").

Blender renders the picture only (no stickers, no burned captions) plus anchors*.json: the screen position of
named 3D points per frame. This module builds a HyperFrames project in <work>/hf over that render and renders it:

    index.html                  root: the film, the overlay layers, the mix
    compositions/film.html      the rendered film, graded through `hyperframes media-treatment`
    compositions/labels.html    labels pinned to moving 3D parts (leader line + dot follow the anchor per frame)
    compositions/titles.html    the hook line, chapter titles, step titles, a stat with a ruler between two
                                anchors, the closing question
    compositions/route.html     the journey tracker: a pipe across the top that fills stop by stop, with a drop
                                riding to the current chapter
    compositions/fx.html        a short dip on every chapter change
    compositions/captions.html  word-by-word karaoke captions in one fixed band (Cutaway Studio's)

Film JSON keys it reads: chapters [{id, label}], beats[].chapter / hook / title / callouts [{anchor, text, at}] /
stat {display, ruler: [a, b]} / question. Every timed element follows the HyperFrames contract (data-start,
data-duration, one paused timeline per composition, no clocks).
"""
from __future__ import annotations

import glob
import json
import logging
import os
import re
import shutil

from cutaway import hf
from cutaway.assets.fetch import font
from cutaway.config import BRAND, CAPTION_BAND, HEADER_BAND, MECHANISM_BAND, SAFE_RIGHT, SAFE_TOP
from cutaway.stages.compose import GSAP, _font_face, _page, captions_scene, esc

log = logging.getLogger("pipeline")
FPS = 30
W, H = 1080, 1920
GRADE = {"intensity": 1, "details": {"vignette": 0.1, "grain": 0.025, "grainSize": 0.16, "grainRoughness": 0.5}}
LABEL_GUTTER = 64
ROUTE_Y = SAFE_TOP + 22                  # the journey tracker's pipe (px from the top)
ROUTE_X0, ROUTE_X1 = 96, W - SAFE_RIGHT - 40


def beat_times(spans):
    """[(t0, t1)] seconds per beat from make_film's frame spans (0-based, inclusive)."""
    return [(s["start"] / FPS, (s["end"] + 1) / FPS) for s in spans]


def load_anchors(work):
    frames = {}
    for p in sorted(glob.glob(os.path.join(work, "anchors*.json")), key=os.path.getmtime):
        try:
            frames.update(json.load(open(p, encoding="utf-8")).get("frames", {}))
        except (OSError, ValueError):
            log.warning("[compose] unreadable %s", p)
    return frames


def _track(anchors, name, t0, t1):
    """Per-frame [x, y, vis] of an anchor over [t0, t1] (gaps hold the last known point)."""
    out, last = [], None
    for f in range(int(round(t0 * FPS)) + 1, int(round(t1 * FPS)) + 2):
        p = anchors.get(str(f), {}).get(name) or last
        if p is not None:
            out.append(p)
            last = p
    return out


# ------------------------------------------------------------------ pinned labels

def labels_scene(film, times, anchors, duration):
    body_html, lines_html, js, warnings = [], [], [], []
    k = 0
    for b, (bt0, bt1) in zip(film["beats"], times):
        for c in b.get("callouts", []):
            t0 = bt0 + c.get("at", 0.2) * (bt1 - bt0)
            t1 = min(bt1 - 0.08, t0 + 3.2)
            if t1 - t0 < 0.9:
                warnings.append(f"{b['id']}: label '{c['text']}' has under 0.9 s, dropped")
                continue
            track = _track(anchors, c["anchor"], t0, t1)
            if not track or sum(p[2] for p in track) < 0.6 * len(track):
                warnings.append(f"{b['id']}: anchor '{c['anchor']}' hidden or off screen, label dropped")
                continue
            a0 = track[0]
            left = a0[0] > W * 0.5             # the label sits in the gutter opposite the anchor
            ly = min(max(a0[1] - 110, MECHANISM_BAND[0] - 20), MECHANISM_BAND[1] - 60)
            lx = LABEL_GUTTER if left else W - SAFE_RIGHT - LABEL_GUTTER
            cid = f"lb{k}"
            k += 1
            body_html.append(
                f'  <div id="{cid}" class="clip co {"co-l" if left else "co-r"}" data-start="{t0:.3f}" '
                f'data-duration="{t1 - t0:.3f}" data-track-index="{2 + k % 4}" style="top:{ly:.0f}px;'
                f'{"left" if left else "right"}:{(lx if left else W - lx):.0f}px">'
                f'<div class="co-in"><span class="co-tick"></span><span class="co-text">{esc(c["text"].upper())}</span>'
                f'</div></div>')
            lines_html.append(
                f'<line id="{cid}-ln" x1="{lx:.0f}" y1="{ly + 28:.0f}" x2="{a0[0]:.1f}" y2="{a0[1]:.1f}" '
                f'pathLength="1" class="ln"/><circle id="{cid}-dt" cx="{a0[0]:.1f}" cy="{a0[1]:.1f}" r="9" '
                f'class="dt"/><circle id="{cid}-rg" cx="{a0[0]:.1f}" cy="{a0[1]:.1f}" r="18" class="rg"/>')
            pts = [[round(p[0], 1), round(p[1], 1), p[2]] for p in track]
            js.append(f"""  (function () {{
    const P = {json.dumps(pts, separators=(",", ":"))};
    const t0 = {t0:.3f}, dur = {t1 - t0:.3f}, step = 1 / {FPS};
    const box = document.querySelector("#{cid} .co-in");
    const w = box.getBoundingClientRect().width;
    document.getElementById("{cid}-ln").setAttribute("x1", {lx:.0f} + ({'w' if left else '-w'}));
    tl.fromTo("#{cid}-ln", {{ strokeDashoffset: 1, opacity: 1 }}, {{ strokeDashoffset: 0, duration: 0.32, ease: "power3.out" }}, t0);
    tl.fromTo(["#{cid}-dt", "#{cid}-rg"], {{ scale: 0, transformOrigin: "50% 50%" }}, {{ scale: 1, duration: 0.28, ease: "back.out(2)" }}, t0);
    tl.fromTo(box, {{ opacity: 0, x: {'-24' if left else '24'} }}, {{ opacity: 1, x: 0, duration: 0.3, ease: "expo.out" }}, t0 + 0.14);
    tl.to("#{cid}-ln", {{ keyframes: P.map((p) => ({{ attr: {{ x2: p[0], y2: p[1] }}, duration: step }})), ease: "none" }}, t0);
    tl.to(["#{cid}-dt", "#{cid}-rg"], {{ keyframes: P.map((p) => ({{ attr: {{ cx: p[0], cy: p[1] }}, duration: step }})), ease: "none" }}, t0);
    tl.fromTo("#{cid}-rg", {{ attr: {{ r: 12 }}, opacity: 0.8 }}, {{ attr: {{ r: 30 }}, opacity: 0, duration: 0.9, ease: "power2.out", repeat: Math.max(0, Math.floor(dur / 0.9) - 1) }}, t0 + 0.3);
    tl.to(box, {{ opacity: 0, duration: 0.16, ease: "power2.in" }}, t0 + dur - 0.2);
    tl.to(["#{cid}-ln", "#{cid}-dt"], {{ opacity: 0, duration: 0.16, ease: "power2.in" }}, t0 + dur - 0.2);
  }})();""")
    style = f"""<style>
  #root {{ position: absolute; inset: 0; }}
  #lb-svg {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; overflow: visible; }}
  #root .ln {{ stroke: {BRAND['cold']}; stroke-width: 3.5; stroke-dasharray: 1; fill: none;
    filter: drop-shadow(0 2px 4px rgba(0,0,0,0.55)); }}
  #root .dt {{ fill: {BRAND['cold']}; stroke: #ffffff; stroke-width: 2.5; }}
  #root .rg {{ fill: none; stroke: {BRAND['cold']}; stroke-width: 3; }}
  #root .co {{ position: absolute; height: 56px; }}
  #root .co-in {{ display: inline-flex; align-items: center; gap: 12px; padding: 11px 20px 11px 16px;
    background: rgba(8, 18, 34, 0.82); border: 2px solid {BRAND['cold']}; border-radius: 12px;
    font-family: 'Inter', sans-serif; font-weight: 800; font-size: 34px; letter-spacing: 0.03em;
    color: {BRAND['ink']}; white-space: nowrap; box-shadow: 0 6px 22px rgba(0, 0, 0, 0.35); }}
  #root .co-tick {{ width: 12px; height: 12px; border-radius: 50%; background: {BRAND['cold']}; }}
  #root .co-r .co-in {{ flex-direction: row-reverse; }}
</style>"""
    body = (f'  <svg id="lb-svg" viewBox="0 0 {W} {H}" data-layout-ignore>{"".join(lines_html)}</svg>\n'
            + "\n".join(body_html))
    script = "  const tl = gsap.timeline({ paused: true });\n" + "\n".join(js) + '\n  window.__timelines["labels"] = tl;'
    return _page(body, script, "labels", duration, style), warnings


# ------------------------------------------------------------------ titles, stat ruler, question

def _chapter_starts(film, times):
    """[(chapter index, t0)] where each chapter begins."""
    ids = [c["id"] for c in film.get("chapters", [])]
    out, cur = [], None
    for b, (t0, _t1) in zip(film["beats"], times):
        ch = b.get("chapter")
        if ch and ch != cur and ch in ids:
            out.append((ids.index(ch), t0))
        cur = ch or cur
    return out


def titles_scene(film, times, anchors, words, duration):
    body, js, warnings = [], [], []
    chapters = film.get("chapters", [])
    starts = dict((t0, i) for i, t0 in _chapter_starts(film, times))
    step = 0
    for k, (b, (t0, t1)) in enumerate(zip(film["beats"], times)):
        bid = b["id"]
        if b.get("hook"):
            body.append(f'  <div id="hk-{bid}" class="clip hk" data-start="0" data-duration="{t1:.3f}" '
                        f'data-track-index="1"><div class="hk-in">{esc(b["hook"])}</div></div>')
            js.append(f"""  tl.fromTo("#hk-{bid} .hk-in", {{ opacity: 0, y: 30, scale: 0.92 }}, {{ opacity: 1, y: 0, scale: 1, duration: 0.35, ease: "back.out(1.6)" }}, 0.05);
  tl.to("#hk-{bid} .hk-in", {{ opacity: 0, y: -16, duration: 0.2, ease: "power2.in" }}, {t1 - 0.25:.3f});""")
        if t0 in starts and not b.get("title"):
            ci = starts[t0]
            label = chapters[ci]["label"]
            hid = f"ch-{bid}"
            hold = min(1.6, t1 - t0 - 0.2)
            body.append(f'  <div id="{hid}" class="clip ch" data-start="{t0:.3f}" data-duration="{hold:.3f}" '
                        f'data-track-index="2"><div class="ch-in"><div class="ch-num">STOP {ci + 1} OF {len(chapters)}'
                        f'</div><div class="ch-word">{esc(label)}</div></div></div>')
            js.append(f"""  tl.fromTo("#{hid} .ch-in", {{ opacity: 0, scale: 1.15 }}, {{ opacity: 1, scale: 1, duration: 0.28, ease: "expo.out" }}, {t0 + 0.05:.3f});
  tl.to("#{hid} .ch-in", {{ opacity: 0, y: -20, duration: 0.2, ease: "power2.in" }}, {t0 + hold - 0.22:.3f});""")
        if b.get("title"):
            step += 1
            tid = f"tt-{bid}"
            body.append(f'  <div id="{tid}" class="clip ttl" data-start="{t0:.3f}" data-duration="{t1 - t0:.3f}" '
                        f'data-track-index="3"><div class="ttl-in"><div class="ttl-step">STEP {step}</div>'
                        f'<div class="ttl-word">{esc(b["title"])}</div></div></div>')
            js.append(f"""  tl.fromTo("#{tid} .ttl-in", {{ opacity: 0, scale: 1.12, filter: "blur(10px)" }}, {{ opacity: 1, scale: 1, filter: "blur(0px)", duration: 0.24, ease: "expo.out" }}, {t0 + 0.04:.3f});
  tl.fromTo("#{tid} .ttl-in", {{ y: 0, scale: 1 }}, {{ y: 0, scale: 0.6, duration: 0.45, ease: "power3.inOut", immediateRender: false }}, {t0 + 1.3:.3f});
  tl.to("#{tid} .ttl-in", {{ opacity: 0, duration: 0.16, ease: "power2.in" }}, {t1 - 0.2:.3f});""")
        stat = b.get("stat")
        if stat:
            sid = f"st-{bid}"
            s_in = t0 + 0.35
            ruler = stat.get("ruler") or []
            track_a = _track(anchors, ruler[0], s_in, t1) if len(ruler) == 2 else []
            track_b = _track(anchors, ruler[1], s_in, t1) if len(ruler) == 2 else []
            has_ruler = bool(track_a and track_b and min(len(track_a), len(track_b)) > 5)
            if len(ruler) == 2 and not has_ruler:
                warnings.append(f"{bid}: ruler anchors missing, the stat shows without its ruler")
            body.append(f'  <div id="{sid}" class="clip st" data-start="{s_in:.3f}" data-duration="{t1 - s_in:.3f}" '
                        f'data-track-index="4"><div class="st-in">{esc(stat["display"])}</div></div>')
            js.append(f"""  tl.fromTo("#{sid} .st-in", {{ opacity: 0, y: 24, scale: 0.9 }}, {{ opacity: 1, y: 0, scale: 1, duration: 0.35, ease: "back.out(1.7)" }}, {s_in + 0.02:.3f});
  tl.to("#{sid} .st-in", {{ opacity: 0, duration: 0.16, ease: "power2.in" }}, {t1 - 0.2:.3f});""")
            if has_ruler:
                n = min(len(track_a), len(track_b))
                A = [[round(p[0], 1), round(p[1], 1)] for p in track_a[:n]]
                B = [[round(p[0], 1), round(p[1], 1)] for p in track_b[:n]]
                side = -1 if A[0][0] > W * 0.5 else 1      # the ruler stands beside the tower, on the open side
                off = 150 * side
                # one tick per 10 m when the film gives the ruler's real height (the stat is "10 m = 1 bar")
                nt = max(1, round(stat["ruler_m"] / 10)) if stat.get("ruler_m") else 10
                ticks = "".join(f'<line id="{sid}-tk{j}" class="rt" x1="0" y1="0" x2="0" y2="0"/>' for j in range(nt + 1))
                body.append(f'  <svg id="{sid}-svg" class="clip rsvg" data-start="{s_in:.3f}" data-duration="{t1 - s_in:.3f}" '
                            f'data-track-index="5" viewBox="0 0 {W} {H}" data-layout-ignore><line id="{sid}-ax" '
                            f'class="ra" x1="0" y1="0" x2="0" y2="0"/>{ticks}</svg>')
                js.append(f"""  (function () {{
    const A = {json.dumps(A, separators=(",", ":"))}, B = {json.dumps(B, separators=(",", ":"))};
    const t0 = {s_in:.3f}, step = 1 / {FPS}, off = {off}, NT = {nt};
    const g = {{ k: 0 }};
    const ax = document.getElementById("{sid}-ax");
    const tk = [...Array(NT + 1).keys()].map((j) => document.getElementById("{sid}-tk" + j));
    const draw = (i, grow) => {{
      const a = A[i], b = B[i], x = Math.min(a[0], b[0]) + off;
      const y0 = a[1], y1 = a[1] + (b[1] - a[1]) * grow;
      ax.setAttribute("x1", x); ax.setAttribute("x2", x); ax.setAttribute("y1", y0); ax.setAttribute("y2", y1);
      tk.forEach((t, j) => {{
        const y = a[1] + (b[1] - a[1]) * j / NT, on = j / NT <= grow + 1e-6, big = NT <= 5 || j % 5 === 0;
        t.setAttribute("x1", x - (big ? 22 : 12)); t.setAttribute("x2", x + (big ? 22 : 12));
        t.setAttribute("y1", y); t.setAttribute("y2", y); t.style.opacity = on ? 1 : 0;
      }});
    }};
    draw(0, 0);
    const box = {{ v: 0 }};
    tl.to(box, {{ v: A.length - 1, duration: (A.length - 1) * step, ease: "none",
      onUpdate: () => draw(Math.round(box.v), Math.min(1, (box.v * step) / 0.9)) }}, t0);
    tl.to("#{sid}-svg", {{ opacity: 0, duration: 0.16 }}, {t1 - 0.2:.3f});
  }})();""")
        if b.get("question"):
            q = b["question"]
            ws = [w for w in words if w.get("beat") == k]
            q0 = max(t0 + 0.2, ws[0]["start"] if ws else t0)
            body.append(f'  <div id="q-{bid}" class="clip qn" data-start="{q0:.3f}" data-duration="{duration - q0:.3f}" '
                        f'data-track-index="6"><div class="qn-in"><div class="qn-word">{esc(q)}</div>'
                        f'<div class="qn-sub">TELL US IN THE COMMENTS</div></div></div>')
            js.append(f"""  tl.fromTo("#q-{bid} .qn-word", {{ opacity: 0, scale: 1.2 }}, {{ opacity: 1, scale: 1, duration: 0.3, ease: "back.out(1.8)" }}, {q0 + 0.02:.3f});
  tl.fromTo("#q-{bid} .qn-sub", {{ opacity: 0, y: 14 }}, {{ opacity: 1, y: 0, duration: 0.3, ease: "expo.out" }}, {q0 + 0.5:.3f});""")
    style = f"""<style>
  {_font_face()}
  #root {{ position: absolute; inset: 0; }}
  #root .hk {{ position: absolute; left: 60px; width: {W - 60 - SAFE_RIGHT}px; top: {HEADER_BAND[0] + 150}px; }}
  #root .hk-in {{ font-family: 'Anton', sans-serif; font-size: 112px; line-height: 1.0; color: {BRAND['ink']};
    text-align: center; text-shadow: 0 6px 30px rgba(0, 0, 0, 0.6); }}
  #root .ch {{ position: absolute; left: 0; width: {W}px; top: {HEADER_BAND[0] + 120}px; }}
  #root .ch-in {{ text-align: center; }}
  #root .ch-num {{ font-family: 'Inter', sans-serif; font-weight: 800; font-size: 30px; letter-spacing: 0.3em;
    color: {BRAND['cold']}; text-shadow: 0 3px 12px rgba(0, 0, 0, 0.7); }}
  #root .ch-word {{ font-family: 'Anton', sans-serif; font-size: 150px; line-height: 1.0; color: {BRAND['ink']};
    text-shadow: 0 6px 30px rgba(0, 0, 0, 0.6); }}
  #root .ttl {{ position: absolute; left: 0; width: {W}px; top: {HEADER_BAND[0] + 110}px; height: 230px; }}
  #root .ttl-in {{ width: 100%; text-align: center; transform-origin: 50% 0%; }}
  #root .ttl-step {{ font-family: 'Inter', sans-serif; font-weight: 800; font-size: 30px; letter-spacing: 0.32em;
    color: {BRAND['cold']}; height: 40px; text-shadow: 0 3px 12px rgba(0, 0, 0, 0.7); }}
  #root .ttl-word {{ font-family: 'Anton', sans-serif; font-size: 140px; line-height: 1.0; color: {BRAND['ink']};
    text-shadow: 0 6px 30px rgba(0, 0, 0, 0.55); }}
  #root .st {{ position: absolute; left: 0; width: {W}px; top: {HEADER_BAND[0] + 170}px; }}
  #root .st-in {{ text-align: center; font-family: 'Anton', sans-serif; font-size: 120px; line-height: 1.0;
    color: {BRAND['hot']}; text-shadow: 0 6px 30px rgba(0, 0, 0, 0.6); }}
  #root .rsvg {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; overflow: visible; }}
  #root .ra {{ stroke: {BRAND['hot']}; stroke-width: 6; stroke-linecap: round; }}
  #root .rt {{ stroke: {BRAND['hot']}; stroke-width: 4; stroke-linecap: round; }}
  #root .qn {{ position: absolute; left: 60px; width: {W - 60 - SAFE_RIGHT}px; top: {HEADER_BAND[0] + 140}px; }}
  #root .qn-in {{ text-align: center; }}
  #root .qn-word {{ font-family: 'Anton', sans-serif; font-size: 130px; line-height: 1.0; color: {BRAND['hot']};
    text-shadow: 0 6px 30px rgba(0, 0, 0, 0.6); }}
  #root .qn-sub {{ font-family: 'Inter', sans-serif; font-weight: 800; font-size: 32px; letter-spacing: 0.22em;
    color: {BRAND['ink']}; margin-top: 18px; text-shadow: 0 3px 12px rgba(0, 0, 0, 0.7); }}
</style>"""
    script = "  const tl = gsap.timeline({ paused: true });\n" + "\n".join(js) + '\n  window.__timelines["titles"] = tl;'
    return _page("\n".join(body), script, "titles", duration, style), warnings


# ------------------------------------------------------------------ journey tracker

DROP = ("M0,-26 C10,-12 18,-2 18,8 C18,19 10,26 0,26 C-10,26 -18,19 -18,8 C-18,-2 -10,-12 0,-26 Z")


def route_scene(film, times, duration):
    chapters = film.get("chapters", [])
    starts = _chapter_starts(film, times)
    scrim = (f'  <div id="scrim" class="clip" data-start="0" data-duration="{duration:.3f}" data-track-index="0" '
             f'data-layout-ignore></div>')
    if not chapters or not starts:
        body, js = scrim, []
    else:
        n = len(chapters)
        xs = [ROUTE_X0 + (ROUTE_X1 - ROUTE_X0) * i / (n - 1) for i in range(n)]
        t_show = starts[0][1] - 0.1
        stops = "".join(f'<circle id="rs{i}" class="rs" cx="{x:.1f}" cy="{ROUTE_Y}" r="13"/>' for i, x in enumerate(xs))
        labels = "".join(f'<div id="rl{i}" class="rl" style="left:{x - 90:.1f}px">{esc(c["label"])}</div>'
                         for i, (x, c) in enumerate(zip(xs, chapters)))
        body = scrim + "\n" + (
            f'  <div id="route" class="clip" data-start="{t_show:.3f}" data-duration="{duration - t_show:.3f}" '
            f'data-track-index="1"><div class="rt-in"><svg class="rt-svg" viewBox="0 0 {W} 120" data-layout-ignore>'
            f'<line class="rp" x1="{xs[0]:.1f}" y1="{ROUTE_Y}" x2="{xs[-1]:.1f}" y2="{ROUTE_Y}"/>'
            f'<line id="rfill" class="rf" x1="{xs[0]:.1f}" y1="{ROUTE_Y}" x2="{xs[0]:.1f}" y2="{ROUTE_Y}"/>'
            f'{stops}<g id="rdrop" transform="translate({xs[0]:.1f},{ROUTE_Y - 44})"><path class="rd" d="{DROP}"/>'
            f'</g></svg>{labels}</div></div>')
        js = [f'  tl.fromTo("#route .rt-in", {{ opacity: 0, y: -16 }}, {{ opacity: 1, y: 0, duration: 0.35, '
              f'ease: "expo.out" }}, {t_show + 0.02:.3f});']
        prev = None
        for i, t in starts:
            x = xs[i]
            if prev is None:
                js.append(f'  tl.set("#rdrop", {{ attr: {{ transform: "translate({x:.1f},{ROUTE_Y - 44})" }} }}, {t_show:.3f});')
            else:
                js.append(f'  tl.to("#rdrop", {{ attr: {{ transform: "translate({x:.1f},{ROUTE_Y - 44})" }}, duration: 0.7, '
                          f'ease: "power2.inOut" }}, {t - 0.35:.3f});')
                js.append(f'  tl.to("#rfill", {{ attr: {{ x2: {x:.1f} }}, duration: 0.7, ease: "power2.inOut" }}, {t - 0.35:.3f});')
            js.append(f'  tl.to("#rs{i}", {{ attr: {{ r: 17 }}, fill: "{BRAND["cold"]}", stroke: "#ffffff", duration: 0.25, '
                      f'ease: "back.out(2)" }}, {t + 0.3:.3f});')
            js.append(f'  tl.to("#rl{i}", {{ color: "{BRAND["ink"]}", opacity: 1, duration: 0.25 }}, {t + 0.3:.3f});')
            if prev is not None:
                js.append(f'  tl.to("#rs{prev}", {{ attr: {{ r: 12 }}, duration: 0.25 }}, {t + 0.3:.3f});')
                js.append(f'  tl.to("#rl{prev}", {{ color: "{BRAND["muted"]}", opacity: 0.8, duration: 0.25 }}, {t + 0.3:.3f});')
            prev = i
        q = next((t0 for b, (t0, _t1) in zip(film["beats"], times) if b.get("question")), None)
        if q is not None:                              # the closing question takes the header: the tracker leaves
            js.append(f'  tl.to("#route .rt-in", {{ opacity: 0, y: -16, duration: 0.3, ease: "power2.in" }}, {q:.3f});')
    style = f"""<style>
  #root {{ position: absolute; inset: 0; }}
  #scrim {{ position: absolute; left: 0; top: 0; width: {W}px; height: 560px;
    background: linear-gradient(180deg, rgba(8, 16, 30, 0.78) 0%, rgba(8, 16, 30, 0.42) 50%, rgba(8, 16, 30, 0) 100%); }}
  #route {{ position: absolute; left: 0; top: 0; width: {W}px; height: 260px; }}
  #root .rt-in {{ position: absolute; inset: 0; }}
  #root .rt-svg {{ position: absolute; left: 0; top: 0; width: {W}px; height: 260px; overflow: visible; }}
  #root .rp {{ stroke: rgba(255, 255, 255, 0.35); stroke-width: 8; stroke-linecap: round; }}
  #root .rf {{ stroke: {BRAND['cold']}; stroke-width: 8; stroke-linecap: round; }}
  #root .rs {{ fill: rgba(8, 16, 30, 0.9); stroke: rgba(255, 255, 255, 0.6); stroke-width: 4; }}
  #root .rd {{ fill: {BRAND['cold']}; stroke: #ffffff; stroke-width: 3; }}
  #root .rl {{ position: absolute; top: {ROUTE_Y + 22}px; width: 180px; text-align: center;
    font-family: 'Inter', sans-serif; font-weight: 800; font-size: 26px; letter-spacing: 0.06em;
    color: {BRAND['muted']}; opacity: 0.8; text-shadow: 0 2px 8px rgba(0, 0, 0, 0.8); }}
</style>"""
    return _page(body, "  const tl = gsap.timeline({ paused: true });\n" + "\n".join(js) +
                 '\n  window.__timelines["route"] = tl;', "route", duration, style)


# ------------------------------------------------------------------ chapter dips

def fx_scene(film, times, duration):
    body, js = [], []
    for k, (_i, t) in enumerate(_chapter_starts(film, times)):
        if t < 0.5:
            continue
        body.append(f'  <div id="dp{k}" class="clip ov" data-start="{t - 0.12:.3f}" data-duration="0.36" '
                    f'data-track-index="1"><div class="ov-in"></div></div>')
        js.append(f'  tl.fromTo("#dp{k} .ov-in", {{ opacity: 0 }}, {{ keyframes: [{{ opacity: 0.6, duration: 0.12 }}, '
                  f'{{ opacity: 0, duration: 0.22, ease: "power2.out" }}] }}, {t - 0.12:.3f});')
    style = """<style>
  #root { position: absolute; inset: 0; }
  #root .ov { position: absolute; inset: 0; }
  #root .ov-in { position: absolute; inset: 0; opacity: 0; background: #04101f; }
</style>"""
    return _page("\n".join(body), "  const tl = gsap.timeline({ paused: true });\n" + "\n".join(js) +
                 '\n  window.__timelines["fx"] = tl;', "fx", duration, style)


# ------------------------------------------------------------------ film + root

def film_scene(duration):
    style = f"""<style>
  #root {{ position: absolute; inset: 0; }}
  #film-v {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; object-fit: cover; }}
</style>"""
    body = (f'  <video id="film-v" class="clip" data-start="0" data-duration="{duration:.3f}" data-track-index="0" '
            f'src="assets/video/film.mp4" muted playsinline></video>')
    return _page(body, '  const tl = gsap.timeline({ paused: true });\n  window.__timelines["film"] = tl;',
                 "film", duration, style)


LAYERS = [("film", 1, "graphics"), ("labels", 9, "graphics"), ("titles", 10, "graphics"), ("route", 11, "graphics"),
          ("fx", 12, "graphics"), ("captions", 13, "captions")]


def index_html(title, duration):
    hosts = [f'    <div id="{cid}" data-composition-id="{cid}" data-composition-src="compositions/{cid}.html" '
             f'data-start="0" data-duration="{duration:.3f}" data-track-index="{z}" data-track-kind="{kind}" '
             f'data-width="{W}" data-height="{H}" class="layer {cid}"></div>' for cid, z, kind in LAYERS]
    zs = "\n".join(f"      .layer.{cid} {{ z-index: {z}; }}" for cid, z, _k in LAYERS)
    variables = [{"id": "color-ground", "type": "color", "label": "Background", "default": BRAND["bg"]},
                 {"id": "color-cold", "type": "color", "label": "Accent", "default": BRAND["cold"]}]
    return f"""<!doctype html>
<html lang="en" data-composition-variables='{json.dumps(variables)}'>
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <title>{esc(title)}</title>
    <script src="{GSAP}"></script>
    <style>
      html, body {{ margin: 0; width: {W}px; height: {H}px; overflow: hidden; background: {BRAND['bg']}; }}
      #ground {{ position: absolute; inset: 0; background: var(--color-ground, {BRAND['bg']}); z-index: 0; }}
      .layer {{ position: absolute; inset: 0; }}
{zs}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{duration:.3f}" data-width="{W}" data-height="{H}">
    <div id="ground"></div>
{chr(10).join(hosts)}
    <audio id="mix" class="clip" data-start="0" data-duration="{duration:.3f}" data-track-index="20" src="assets/audio/mix.wav" data-volume="1"></audio>
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      window.__timelines["main"] = gsap.timeline({{ paused: true }});
    </script>
  </body>
</html>
"""


def _link(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        os.remove(dst)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


def caption_words(beats, words):
    """Script words with timings (agents.beats.script_word_timings) tagged with their beat index."""
    out, i = [], 0
    for k, b in enumerate(beats):
        for _w in str(b.get("text") or "").split():
            if i < len(words) and re.search(r"\w", _w):
                out.append(dict(words[i], beat=k))
                i += 1
    return out


def build(film, work, spans, words, duration, video, mix):
    """Write the HyperFrames project in <work>/hf; returns (project dir, warnings)."""
    d = os.path.join(work, "hf")
    if not os.path.exists(os.path.join(d, "hyperframes.json")):
        hf.run(["init", d], cwd=work)
        for junk in ("compositions",):
            p = os.path.join(d, junk)
            if os.path.isdir(p):
                shutil.rmtree(p)
    comp = os.path.join(d, "compositions")
    os.makedirs(comp, exist_ok=True)
    for f in os.listdir(comp):
        if f.endswith(".html"):
            os.remove(os.path.join(comp, f))
    _link(font(), os.path.join(d, "assets", "fonts", "Anton-Regular.ttf"))
    _link(video, os.path.join(d, "assets", "video", "film.mp4"))
    _link(mix, os.path.join(d, "assets", "audio", "mix.wav"))
    times = beat_times(spans)
    anchors = load_anchors(work)
    lab, w1 = labels_scene(film, times, anchors, duration)
    tit, w2 = titles_scene(film, times, anchors, words, duration)
    pages = {"film": film_scene(duration), "labels": lab, "titles": tit, "route": route_scene(film, times, duration),
             "fx": fx_scene(film, times, duration), "captions": captions_scene({"words": words}, duration)}
    for name, page in pages.items():
        with open(os.path.join(comp, f"{name}.html"), "w", encoding="utf-8") as fh:
            fh.write(page)
    with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(index_html(film.get("title", "film"), duration))
    gpath = os.path.join(d, ".grade.json")
    json.dump(GRADE, open(gpath, "w", encoding="utf-8"))
    hf.run(["media-treatment", "--project", ".", "--file", "compositions/film.html", "--selector", "#film-v",
            "--grading", ".grade.json", "--apply", "--json"], cwd=d, timeout=300)
    warnings = w1 + w2
    for w in warnings:
        log.warning("[compose] %s", w)
    return d, warnings


def lint(d):
    r = hf.run(["lint"], cwd=d, check=False, timeout=600)
    errors = re.findall(r"(\d+) error", r.stdout or "")
    if r.returncode != 0 or (errors and int(errors[-1]) > 0):
        raise RuntimeError("hyperframes lint failed:\n" + (r.stdout or "")[-3000:])
    return r.stdout


def render(d, out, quality="delivery"):
    hf.run(["render", "--quality", quality, "-o", out], cwd=d, timeout=7200)
    return out
