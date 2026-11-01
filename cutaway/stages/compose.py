"""
Stage 8 - the HyperFrames project (runs/<slug>/hf/), generated from shotlist.json, words.json and the
Blender anchors. Follows the HyperFrames contract: every timed element has data-start/data-duration, one paused
timeline per composition registered last, fromTo tweens at absolute times, no clocks or randomness, the grade
through `hyperframes media-treatment`, assets under assets/.

    index.html                 root: shot scenes, overlay layers, the mix
    compositions/sNN.html      one scene per shot: the graded footage + its anchored callouts
    compositions/titles.html   step titles (land big, shrink to a header after 1.5 s) and stat counters
    compositions/hud.html      the step tracker
    compositions/fx.html       flash / dip overlays on transitions
    compositions/captions.html word-by-word karaoke captions in one fixed band
"""
from __future__ import annotations

import html
import json
import logging
import os
import re
import shutil
from urllib.parse import urlparse

from .. import hf
from ..assets.fetch import font
from ..config import BRAND, CAPTION_BAND, FPS, HEADER_BAND, MECHANISM_BAND, SAFE_RIGHT, SAFE_TOP
from ..runner import StageError

log = logging.getLogger("pipeline")
GSAP = "https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js"
GRADE = {"intensity": 1, "details": {"vignette": 0.08, "grain": 0.03, "grainSize": 0.16, "grainRoughness": 0.5}}
W, H = 1080, 1920
LABEL_GUTTER = 64


def inputs(run):
    q = run.quality
    return [run.path("shotlist.json"), run.path("words.json"), run.path("script.json"), run.path("facts.json"),
            run.path("render", q, "render.json"), q, os.path.abspath(__file__)]


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def _page(body: str, script: str, comp_id: str, duration: float, extra_head: str = "") -> str:
    """A sub-composition file: everything inside <template>, root styled as #root."""
    return f"""<template>
{extra_head}
<div id="root" data-composition-id="{comp_id}" data-width="{W}" data-height="{H}" data-duration="{duration:.3f}">
{body}
</div>
<script>
{script}
</script>
</template>
"""


def _font_face() -> str:
    return ("@font-face { font-family: 'Anton'; src: url('assets/fonts/Anton-Regular.ttf') format('truetype'); "
            "font-weight: 400; font-display: block; }")


# ------------------------------------------------------------ shots + callouts

def shot_scene(run, shot, q: str, d_shot: float, facts: dict) -> tuple[str, list[str]]:
    sid = shot["id"]
    warnings = []
    anchors = json.load(open(run.path("render", q, sid, "anchors.json"), encoding="utf-8"))
    callouts_html, lines_html, js = [], [], []
    for k, c in enumerate(shot.get("callouts_t", [])):
        t0 = max(shot["start"], c["t"])
        t1 = min(shot["end"] - 0.05, t0 + 3.4)
        if t1 - t0 < 0.9:
            warnings.append(f"{sid}: callout '{c['text']}' too short, dropped")
            continue
        track, last = [], None
        for f in range(int(round(t0 * FPS)) + 1, int(round(t1 * FPS)) + 2):
            p = anchors["frames"].get(str(f), {}).get(c["anchor"]) or last
            if p is not None:
                track.append({"x": p[0], "y": p[1], "v": p[2]})
                last = p
        if not track or sum(p["v"] for p in track) < 0.6 * len(track):
            warnings.append(f"{sid}: '{c['anchor']}' hidden most of the callout, dropped")
            continue
        a0 = track[0]
        left = a0["x"] > W * 0.5             # label goes to the gutter on the opposite side of the anchor
        ly = min(max(a0["y"] - 40, MECHANISM_BAND[0] + 20), MECHANISM_BAND[1] - 80)
        lx = LABEL_GUTTER if left else W - SAFE_RIGHT - LABEL_GUTTER
        lt, ld = t0 - shot["start"], t1 - t0
        cid = f"{sid}-c{k}"
        callouts_html.append(
            f'<div id="{cid}" class="clip co {"co-l" if left else "co-r"}" data-start="{lt:.3f}" '
            f'data-duration="{ld:.3f}" data-track-index="{2 + k}" style="top:{ly:.0f}px;'
            f'{"left" if left else "right"}:{(lx if left else W - lx):.0f}px">'
            f'<div class="co-in"><span class="co-tick"></span><span class="co-text">{esc(c["text"].upper())}</span>'
            f'</div></div>')
        lines_html.append(
            f'<line id="{cid}-ln" x1="{lx:.0f}" y1="{ly + 26:.0f}" x2="{a0["x"]:.1f}" y2="{a0["y"]:.1f}" '
            f'pathLength="1" class="ln"/><circle id="{cid}-dt" cx="{a0["x"]:.1f}" cy="{a0["y"]:.1f}" r="9" '
            f'class="dt"/><circle id="{cid}-rg" cx="{a0["x"]:.1f}" cy="{a0["y"]:.1f}" r="18" class="rg"/>')
        pts = [[round(p["x"], 1), round(p["y"], 1), p["v"]] for p in track]
        js.append(f"""  (function () {{
    const P = {json.dumps(pts, separators=(",", ":"))};
    const t0 = {lt:.3f}, dur = {ld:.3f}, step = 1 / {FPS};
    const box = document.querySelector("#{cid} .co-in");
    const w = box.getBoundingClientRect().width;
    const x1 = {"%.0f" % lx} + ({'w' if left else '-w'});
    document.getElementById("{cid}-ln").setAttribute("x1", x1);
    tl.fromTo(box, {{ opacity: 0, filter: "blur(8px)" }}, {{ opacity: 1, filter: "blur(0px)", duration: 0.18, ease: "expo.out" }}, t0 + 0.12);
    tl.fromTo("#{cid}-ln", {{ strokeDashoffset: 1, opacity: 1 }}, {{ strokeDashoffset: 0, duration: 0.32, ease: "power3.out" }}, t0);
    tl.fromTo(["#{cid}-dt", "#{cid}-rg"], {{ scale: 0, transformOrigin: "50% 50%" }}, {{ scale: 1, duration: 0.28, ease: "expo.out" }}, t0);
    const kfl = P.map((p) => ({{ attr: {{ x2: p[0], y2: p[1] }}, duration: step }}));
    const kfd = P.map((p) => ({{ attr: {{ cx: p[0], cy: p[1] }}, duration: step }}));
    tl.to("#{cid}-ln", {{ keyframes: kfl, ease: "none" }}, t0);
    tl.to(["#{cid}-dt", "#{cid}-rg"], {{ keyframes: kfd, ease: "none" }}, t0);
    const vis = P.map((p) => ({{ opacity: p[2] ? 1 : 0.15, duration: step }}));
    tl.to(["#{cid}-ln", "#{cid}-dt", "#{cid}-rg"], {{ keyframes: vis, ease: "none" }}, t0);
    tl.to(box, {{ opacity: 0, filter: "blur(6px)", duration: 0.16, ease: "power2.in" }}, t0 + dur - 0.2);
    tl.to(["#{cid}-ln", "#{cid}-dt", "#{cid}-rg"], {{ opacity: 0, duration: 0.16, ease: "power2.in" }}, t0 + dur - 0.2);
  }})();""")
    style = f"""<style>
  #root {{ position: absolute; inset: 0; }}
  #{sid}-v {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; object-fit: cover; }}
  #{sid}-svg {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; overflow: visible; }}
  #root .ln {{ stroke: {BRAND['cold']}; stroke-width: 3; stroke-dasharray: 1; fill: none; }}
  #root .dt {{ fill: {BRAND['cold']}; }}
  #root .rg {{ fill: none; stroke: {BRAND['cold']}; stroke-width: 3; opacity: 0.55; }}
  #root .co {{ position: absolute; height: 52px; }}
  #root .co-in {{ display: inline-flex; align-items: center; gap: 12px; padding: 10px 18px 10px 14px;
    background: rgba(10, 18, 32, 0.78); border: 2px solid {BRAND['cold']}; border-radius: 10px;
    font-family: 'Inter', sans-serif; font-weight: 700; font-size: 34px; letter-spacing: 0.03em;
    color: {BRAND['ink']}; white-space: nowrap; }}
  #root .co-tick {{ width: 10px; height: 10px; border-radius: 50%; background: {BRAND['cold']}; }}
  #root .co-r .co-in {{ flex-direction: row-reverse; }}
</style>"""
    body = (f'  <video id="{sid}-v" class="clip" data-start="0" data-duration="{d_shot:.3f}" data-track-index="0" '
            f'src="assets/shots/{sid}.mp4" muted playsinline></video>\n'
            f'  <svg id="{sid}-svg" viewBox="0 0 {W} {H}" data-layout-ignore>{"".join(lines_html)}</svg>\n'
            + "\n".join(f"  {c}" for c in callouts_html))
    script = "  const tl = gsap.timeline({ paused: true });\n" + "\n".join(js) + \
             f'\n  window.__timelines["{sid}"] = tl;'
    return _page(body, script, sid, d_shot, style), warnings


# ------------------------------------------------------------ titles + stats

def _parse_stat(display: str):
    m = re.search(r"(\d[\d,]*(?:\.\d+)?)", display)
    if not m:
        return None, display, ""
    num = m.group(1)
    return num, display[:m.start()], display[m.end():]


def titles_scene(script, words, facts, duration) -> str:
    by_id = {f["id"]: f for f in facts["facts"]}
    beats = words["beats"]
    starts = {b["id"]: b["start"] for b in beats}
    ends = {b["id"]: (beats[i + 1]["start"] if i + 1 < len(beats) else duration) for i, b in enumerate(beats)}
    body, js = [], []
    step = 0
    seen_mech = []
    for sb in script["beats"]:
        bid = sb["id"]
        t0, t1 = starts[bid], ends[bid]
        if sb["mechanism"] not in ("hook", "outro") and sb["mechanism"] not in seen_mech:
            seen_mech.append(sb["mechanism"])
        step = seen_mech.index(sb["mechanism"]) + 1 if sb["mechanism"] in seen_mech else 0
        title = sb.get("title", "").strip()
        hook = sb["mechanism"] == "hook"
        if sb["mechanism"] == "outro" and sb is script["beats"][-1]:
            q = re.split(r"(?<=[.!?])\s+", sb["narration"].strip())[-1]
            ws = [w for w in words["words"] if w["beat"] == bid]
            q_start = next((w["start"] for w in ws if q.split()[0].strip(".,") in w["text"]), t0) if q else t0
            body.append(f'  <div id="q-{bid}" class="clip qn" data-start="{q_start:.3f}" '
                        f'data-duration="{max(0.8, t1 - q_start):.3f}" data-track-index="3"><div class="qn-in">'
                        f'{esc(q)}</div></div>')
            js.append(f"""  tl.fromTo("#q-{bid} .qn-in", {{ opacity: 0, filter: "blur(8px)" }}, {{ opacity: 1, filter: "blur(0px)", duration: 0.2, ease: "expo.out" }}, {q_start + 0.02:.3f});""")
        if title:
            tid = f"t-{bid}"
            body.append(f'  <div id="{tid}" class="clip ttl" data-start="{t0:.3f}" data-duration="{t1 - t0:.3f}" '
                        f'data-track-index="1"><div class="ttl-in"><div class="ttl-step">'
                        f'{"STEP " + str(step) if step else ""}</div><div class="ttl-word">{esc(title)}</div></div></div>')
            js.append(f"""  tl.fromTo("#{tid} .ttl-in", {{ opacity: 0, scale: 1.12, filter: "blur(10px)" }}, {{ opacity: 1, scale: 1, filter: "blur(0px)", duration: 0.22, ease: "expo.out" }}, {t0 + 0.04:.3f});
  tl.fromTo("#{tid} .ttl-in", {{ y: 0, scale: 1 }}, {{ y: 6, scale: 0.5, duration: 0.45, ease: "power3.inOut", immediateRender: false }}, {t0 + 1.5:.3f});
  tl.to("#{tid} .ttl-in", {{ opacity: 0, filter: "blur(6px)", duration: 0.16, ease: "power2.in" }}, {max(t0 + 1.9, t1 - 0.18):.3f});""")
        stat = sb.get("stat")
        if not stat and hook:                         # the hook needs its number on screen in the first 1.5 s
            for fid in sb.get("fact_ids", []):
                f = by_id.get(fid)
                if f and re.search(r"\d", f["value"]) and re.sub(r"\D", "", f["value"])[:3] in                         re.sub(r"\D", "", sb["narration"]):
                    stat = {"fact_id": fid, "display": f"{f['value']} {f['unit']}".strip()}
                    break
        if sb["mechanism"] == "outro" and sb is script["beats"][-1]:
            stat = None
        if stat and title and re.sub(r"\W", "", stat["display"]).lower() == re.sub(r"\W", "", title).lower():
            stat = None                               # the title already says it
        if stat and stat.get("fact_id") in by_id:
            f = by_id[stat["fact_id"]]
            num, pre, post = _parse_stat(stat["display"])
            sid = f"st-{bid}"
            s_in = t0 + (0.08 if hook or not title else 1.75)
            dom = urlparse(f["source_url"]).netloc.replace("www.", "")
            big = " st-hook" if hook or not title else ""
            if num:
                plain = num.replace(",", "")
                dec = len(plain.split(".")[1]) if "." in plain else 0
                numhtml = f'<span class="st-pre">{esc(pre)}</span><span class="st-num" data-to="{plain}">0</span>' \
                          f'<span class="st-post">{esc(post)}</span>'
            else:
                numhtml = f'<span class="st-num">{esc(stat["display"])}</span>'
            body.append(f'  <div id="{sid}" class="clip st{big}" data-start="{s_in:.3f}" '
                        f'data-duration="{max(0.8, t1 - s_in):.3f}" data-track-index="2"><div class="st-in">'
                        f'<div class="st-val">{numhtml}</div><div class="st-src">source: {esc(dom)}</div></div></div>')
            js.append(f"""  tl.fromTo("#{sid} .st-in", {{ opacity: 0, y: 24 }}, {{ opacity: 1, y: 0, duration: 0.3, ease: "expo.out" }}, {s_in + 0.02:.3f});
  tl.to("#{sid} .st-in", {{ opacity: 0, duration: 0.15, ease: "power2.in" }}, {max(s_in + 0.9, t1 - 0.17):.3f});""")
            if num:
                js.append(f"""  (function () {{
    const el = document.querySelector("#{sid} .st-num"), box = {{ v: 0 }};
    const fmt = (v) => v.toLocaleString("en-US", {{ minimumFractionDigits: {dec}, maximumFractionDigits: {dec} }});
    el.textContent = fmt(0);
    tl.fromTo(box, {{ v: 0 }}, {{ v: {plain}, duration: 0.6, ease: "power3.out",
      onUpdate: () => {{ el.textContent = fmt(box.v); }} }}, {s_in + 0.02:.3f});
  }})();""")
    style = f"""<style>
  {_font_face()}
  #root {{ position: absolute; inset: 0; }}
  #root .ttl {{ position: absolute; left: 0; width: {W}px; top: {HEADER_BAND[0] + 70}px; height: 230px; }}
  #root .ttl-in {{ width: 100%; text-align: center; transform-origin: 50% 0%; }}
  #root .ttl-step {{ font-family: 'Inter', sans-serif; font-weight: 700; font-size: 26px; letter-spacing: 0.32em;
    color: {BRAND['cold']}; height: 34px; }}
  #root .ttl-word {{ font-family: 'Anton', sans-serif; font-size: 132px; line-height: 1.0; color: {BRAND['ink']};
    letter-spacing: 0.01em; text-shadow: 0 6px 30px rgba(0, 0, 0, 0.55); }}
  #root .st {{ position: absolute; left: 0; width: {W}px; top: {HEADER_BAND[0] + 172}px; height: 140px; }}
  #root .st.st-hook {{ top: {HEADER_BAND[0] + 40}px; }}
  #root .st-in {{ text-align: center; }}
  #root .st-val {{ font-family: 'Anton', sans-serif; font-size: 112px; line-height: 1.0; color: {BRAND['hot']};
    text-shadow: 0 6px 30px rgba(0, 0, 0, 0.6); }}
  #root .st-hook .st-val {{ font-size: 112px; }}
  #root .st-pre, #root .st-post {{ font-size: 0.6em; }}
  #root .qn {{ position: absolute; left: 70px; width: {W - 70 - SAFE_RIGHT}px; top: {HEADER_BAND[0] + 20}px; }}
  #root .qn-in {{ font-family: 'Anton', sans-serif; font-size: 76px; line-height: 1.05; color: {BRAND['ink']};
    text-align: center; text-shadow: 0 6px 30px rgba(0, 0, 0, 0.6); }}
  #root .st-src {{ font-family: 'Inter', sans-serif; font-weight: 400; font-size: 22px; color: {BRAND['muted']};
    margin-top: 6px; letter-spacing: 0.02em; }}
</style>"""
    script_js = "  const tl = gsap.timeline({ paused: true });\n" + "\n".join(js) + '\n  window.__timelines["titles"] = tl;'
    return _page("\n".join(body), script_js, "titles", duration, style)


# ------------------------------------------------------------ step tracker

def _chips_timeline(script, words, brief, sl) -> tuple[list[str], list[tuple[int, float, float]], float, float]:
    """Chip labels and when each is lit: [(chip, on, off)], plus the tracker's show/hide times.

    A kit with a tracker lights its stage chips from the real crank angle (INTAKE while cylinder 1's piston is
    on its intake stroke, ...) during the beats that explain them, so the chip changes exactly when the piston
    does. Otherwise one chip per explained mechanism, lit during its beats (short stories only)."""
    from .. import kits
    from .shotlist import theta_at
    kit = kits.KITS[brief["kit"]]
    starts = {b["id"]: b["start"] for b in words["beats"]}
    ends = {b["id"]: b["end"] for b in words["beats"]}
    tr = kit.get("tracker")
    if tr:
        beats = [sb["id"] for sb in script["beats"] if sb["mechanism"] in tr["mechanisms"]]
        if not beats:
            return [], [], 0.0, 0.0
        t0, t1 = starts[beats[0]] - 0.3, ends[beats[-1]] + 0.4
        keys = sl["crank"]["keys"]
        off = kit["cycle_offsets"][tr["unit"]]
        lit, out, t = None, [], t0
        n = len(tr["labels"])
        while t <= t1 + 1e-6:
            k = int(((theta_at(keys, t) - off) % 720.0) // tr["span"]) % n
            if k != lit:
                if out:
                    out[-1] = (out[-1][0], out[-1][1], t)
                out.append((k, t, t1))
                lit = k
            t += 1.0 / FPS
        return list(tr["labels"]), out, t0, t1
    order, labels, first = [], {}, {}
    for sb in script["beats"]:
        m = sb["mechanism"]
        if m in ("hook", "outro"):
            continue
        if m not in order:
            order.append(m)
            labels[m] = (sb.get("title") or m).split(",")[0].strip().upper()
            first[m] = starts[sb["id"]]
    if not order or len(order) > 5:
        return [], [], 0.0, 0.0
    outro = [starts[sb["id"]] for sb in script["beats"] if sb["mechanism"] == "outro"]
    stops = [first[m] for m in order[1:]] + [max(outro) if outro else sl["duration"]]
    lit = [(i, first[m], stops[i]) for i, m in enumerate(order)]
    return [labels[m] for m in order], lit, first[order[0]] - 0.3, stops[-1]


def hud_scene(script, words, brief, duration, sl) -> str:
    labels, lit, t_show, t_hide = _chips_timeline(script, words, brief, sl)
    scrim = (f'  <div id="scrim" class="clip" data-start="0" data-duration="{duration:.3f}" data-track-index="0" '
             f'data-layout-ignore></div>')
    if not labels:
        body, js = scrim, []
    else:
        chips = "".join(f'<span id="chip-{i}" class="chip">{esc(x)}</span>' for i, x in enumerate(labels))
        body = scrim + "\n" + (f'  <div id="tracker" class="clip" data-start="{t_show:.3f}" '
                               f'data-duration="{t_hide - t_show:.3f}" data-track-index="1"><div class="tr-in">'
                               f'{chips}</div></div>')
        js = [f'  tl.fromTo("#tracker .tr-in", {{ opacity: 0, y: -12 }}, {{ opacity: 1, y: 0, duration: 0.3, '
              f'ease: "expo.out" }}, {t_show + 0.02:.3f});']
        for i, a, b in lit:
            js.append(f'  tl.fromTo("#chip-{i}", {{ backgroundColor: "rgba(111,211,255,0)", color: "{BRAND["muted"]}", '
                      f'scale: 1 }}, {{ backgroundColor: "{BRAND["cold"]}", color: "{BRAND["bg"]}", scale: 1.08, '
                      f'duration: 0.15, ease: "power2.out", immediateRender: false }}, {a:.3f});')
            js.append(f'  tl.to("#chip-{i}", {{ backgroundColor: "rgba(111,211,255,0)", color: "{BRAND["ink"]}", '
                      f'scale: 1, duration: 0.15, ease: "power2.in" }}, {max(a + 0.16, b - 0.15):.3f});')
        js.append(f'  tl.to("#tracker .tr-in", {{ opacity: 0, duration: 0.2, ease: "power2.in" }}, {t_hide - 0.22:.3f});')
    style = f"""<style>
  #root {{ position: absolute; inset: 0; }}
  #scrim {{ position: absolute; left: 0; top: 0; width: {W}px; height: 520px;
    background: linear-gradient(180deg, rgba(10, 18, 32, 0.86) 0%, rgba(10, 18, 32, 0.55) 55%, rgba(10, 18, 32, 0) 100%); }}
  #tracker {{ position: absolute; left: 0; top: {SAFE_TOP + 14}px; width: {W - SAFE_RIGHT}px; height: 48px; }}
  #root .tr-in {{ display: flex; justify-content: center; gap: 10px; padding-left: {SAFE_RIGHT}px; }}
  #root .chip {{ font-family: 'Inter', sans-serif; font-weight: 700; font-size: 20px; letter-spacing: 0.08em;
    padding: 8px 14px; border-radius: 999px; border: 2px solid rgba(111, 211, 255, 0.55); color: {BRAND['muted']};
    background: rgba(10, 18, 32, 0.55); white-space: nowrap; }}
</style>"""
    return _page(body, "  const tl = gsap.timeline({ paused: true });\n" + "\n".join(js) +
                 '\n  window.__timelines["hud"] = tl;', "hud", duration, style)


# ------------------------------------------------------------ transitions overlay

def fx_scene(shotlist, duration) -> str:
    body, js = [], []
    for i, s in enumerate(shotlist["shots"][1:], start=1):
        t = s["start"]
        kind = s.get("transition", "cut")
        if kind == "flash":
            body.append(f'  <div id="fl-{i}" class="clip ov" data-start="{max(0, t - 0.06):.3f}" data-duration="0.5" '
                        f'data-track-index="1"><div class="ov-in fl"></div></div>')
            js.append(f'  tl.fromTo("#fl-{i} .ov-in", {{ opacity: 0 }}, {{ keyframes: [{{ opacity: 0.85, duration: 0.06 }}, '
                      f'{{ opacity: 0, duration: 0.4, ease: "power2.out" }}] }}, {max(0, t - 0.06):.3f});')
        elif kind == "dip":
            body.append(f'  <div id="dp-{i}" class="clip ov" data-start="{max(0, t - 0.1):.3f}" data-duration="0.3" '
                        f'data-track-index="2"><div class="ov-in dp"></div></div>')
            js.append(f'  tl.fromTo("#dp-{i} .ov-in", {{ opacity: 0 }}, {{ keyframes: [{{ opacity: 0.45, duration: 0.1 }}, '
                      f'{{ opacity: 0, duration: 0.18, ease: "power2.out" }}] }}, {max(0, t - 0.1):.3f});')
    style = """<style>
  #root { position: absolute; inset: 0; }
  #root .ov { position: absolute; inset: 0; }
  #root .ov-in { position: absolute; inset: 0; opacity: 0; }
  #root .fl { background: #fff4e0; }
  #root .dp { background: #000; }
</style>"""
    return _page("\n".join(body), "  const tl = gsap.timeline({ paused: true });\n" + "\n".join(js) +
                 '\n  window.__timelines["fx"] = tl;', "fx", duration, style)


# ------------------------------------------------------------ captions

def caption_groups(words: list[dict]) -> list[list[dict]]:
    groups, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        punct = bool(re.search(r"[.,;:?!—-]$", w["text"]))
        pause = nxt is not None and nxt["start"] - w["end"] >= 0.15
        beat_end = nxt is None or nxt["beat"] != w["beat"]
        if len(cur) >= 4 or beat_end or (len(cur) >= 2 and (punct or pause)) or \
                (re.search(r"[.?!]$", w["text"]) and len(cur) >= 1):
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    return groups


def captions_scene(words: dict, duration: float) -> str:
    groups = caption_groups(words["words"])
    body, js = [], []
    for g_i, g in enumerate(groups):
        start = max(0.1, g[0]["start"] - 0.05)
        nxt = groups[g_i + 1][0]["start"] - 0.05 if g_i + 1 < len(groups) else duration
        end = min(max(g[-1]["end"] + 0.25, start + 0.4), nxt, duration)
        gid = f"cg{g_i}"
        ends = [min(w["end"], g[k + 1]["start"]) if k + 1 < len(g) else w["end"] for k, w in enumerate(g)]
        spans = " ".join(f'<span id="{gid}-w{k}" class="w" data-ws="{w["start"] - start:.3f}" '
                         f'data-we="{e - start:.3f}">{esc(w["text"])}</span>' for k, (w, e) in enumerate(zip(g, ends)))
        body.append(f'  <div id="{gid}" class="clip cg" data-start="{start:.3f}" data-duration="{end - start:.3f}" '
                    f'data-track-index="1"><div class="cg-in">{spans}</div></div>')
        js.append(f"  group({json.dumps(gid)}, {start:.3f}, {end:.3f});")
    style = f"""<style>
  #root {{ position: absolute; inset: 0; }}
  #root .cg {{ position: absolute; left: 0; width: {W}px; top: {CAPTION_BAND[0]}px;
    height: {CAPTION_BAND[1] - CAPTION_BAND[0]}px; overflow: visible; }}
  #root .cg-in {{ position: absolute; left: 60px; right: {SAFE_RIGHT}px; top: 0; bottom: 0; display: flex;
    align-items: center; justify-content: center; flex-wrap: wrap; gap: 0 26px; text-align: center;
    font-family: 'Inter', sans-serif; font-weight: 900; font-size: 64px; line-height: 1.08;
    text-transform: uppercase; letter-spacing: -0.01em; color: {BRAND['ink']};
    text-shadow: 0 4px 18px rgba(0, 0, 0, 0.75), 0 0 2px rgba(0, 0, 0, 0.9); }}
  #root .w {{ display: inline-block; transform-origin: 50% 70%; }}
</style>"""
    script = f"""  const tl = gsap.timeline({{ paused: true }});
  const fit = (window.__hyperframes && window.__hyperframes.fitTextFontSize) || null;
  let first = true;                // only the earliest group renders its from-state at build time
  function group(id, start, end) {{
    const el = document.getElementById(id);
    const inner = el.querySelector(".cg-in");
    if (fit) {{
      const r = fit(inner.textContent.trim().toUpperCase(), {{ fontFamily: "Inter", fontWeight: 900, maxWidth: 860 }});
      if (r && r.fontSize) inner.style.fontSize = Math.min(64, Math.max(42, r.fontSize)) + "px";
    }}
    tl.fromTo(inner, {{ opacity: 0, scale: 0.96 }}, {{ opacity: 1, scale: 1, duration: 0.09, ease: "power2.out",
      immediateRender: first }}, start);
    first = false;
    el.querySelectorAll(".w").forEach((w) => {{
      const ws = start + parseFloat(w.dataset.ws), we = start + parseFloat(w.dataset.we);
      tl.fromTo(w, {{ color: "{BRAND['ink']}", scale: 1 }}, {{ color: "{BRAND['hot']}", scale: 1.04, duration: 0.06, ease: "power2.out" }}, ws);
      tl.to(w, {{ color: "{BRAND['ink']}", scale: 1, duration: 0.08, ease: "power2.in" }}, Math.max(ws + 0.08, we));
    }});
    tl.to(inner, {{ opacity: 0, duration: 0.08, ease: "power2.in" }}, end - 0.08);
    tl.set(inner, {{ opacity: 0, visibility: "hidden" }}, end);
  }}
{chr(10).join(js)}
  window.__timelines["captions"] = tl;"""
    return _page("\n".join(body), script, "captions", duration, style)


# ------------------------------------------------------------ root

def index_html(shotlist, duration, brief) -> str:
    hosts = []
    for s in shotlist["shots"]:
        d = s["end"] - s["start"]
        hosts.append(f'    <div id="{s["id"]}" data-composition-id="{s["id"]}" data-composition-src="compositions/{s["id"]}.html" '
                     f'data-start="{s["start"]:.3f}" data-duration="{d:.3f}" data-track-index="1" '
                     f'data-track-kind="graphics" data-width="{W}" data-height="{H}" class="layer shot"></div>')
    over = [("titles", 3, "graphics"), ("hud", 4, "graphics"), ("fx", 5, "graphics"), ("captions", 6, "captions")]
    for cid, track, kind in over:
        hosts.append(f'    <div id="{cid}" data-composition-id="{cid}" data-composition-src="compositions/{cid}.html" '
                     f'data-start="0" data-duration="{duration:.3f}" data-track-index="{track}" '
                     f'data-track-kind="{kind}" data-width="{W}" data-height="{H}" class="layer {cid}"></div>')
    variables = [
        {"id": "color-ground", "type": "color", "label": "Background", "default": BRAND["bg"]},
        {"id": "color-ink", "type": "color", "label": "Text", "default": BRAND["ink"]},
        {"id": "color-cold", "type": "color", "label": "Cold accent", "default": BRAND["cold"]},
        {"id": "color-hot", "type": "color", "label": "Hot accent", "default": BRAND["hot"]},
    ]
    return f"""<!doctype html>
<html lang="en" data-composition-variables='{json.dumps(variables)}'>
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <title>{esc(brief['title'])}</title>
    <script src="{GSAP}"></script>
    <style>
      html, body {{ margin: 0; width: {W}px; height: {H}px; overflow: hidden; background: {BRAND['bg']}; }}
      #ground {{ position: absolute; inset: 0; background: var(--color-ground, {BRAND['bg']}); z-index: 0; }}
      .layer {{ position: absolute; inset: 0; }}
      .layer.shot {{ z-index: 1; }}
      .layer.titles {{ z-index: 10; }}
      .layer.hud {{ z-index: 11; }}
      .layer.fx {{ z-index: 12; }}
      .layer.captions {{ z-index: 13; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{duration:.3f}" data-width="{W}" data-height="{H}">
    <div id="ground"></div>
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


def _link(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        os.remove(dst)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


def run(run):
    q = run.quality
    sl = run.need("shotlist.json")
    words = run.need("words.json")
    script = run.need("script.json")
    facts = run.need("facts.json")
    brief = run.need("brief.json")
    duration = sl["duration"]
    d = run.path("hf")
    if not os.path.exists(os.path.join(d, "hyperframes.json")):
        os.makedirs(os.path.dirname(d), exist_ok=True)
        hf.run(["init", d], cwd=run.dir)
    comp = os.path.join(d, "compositions")
    os.makedirs(comp, exist_ok=True)
    for f in os.listdir(comp):
        if f.endswith(".html"):
            os.remove(os.path.join(comp, f))
    _link(font(), os.path.join(d, "assets", "fonts", "Anton-Regular.ttf"))
    warnings = []
    for s in sl["shots"]:
        _link(run.path("render", q, f"{s['id']}.mp4"), os.path.join(d, "assets", "shots", f"{s['id']}.mp4"))
        page, warn = shot_scene(run, s, q, s["end"] - s["start"], facts)
        warnings += warn
        with open(os.path.join(comp, f"{s['id']}.html"), "w", encoding="utf-8") as fh:
            fh.write(page)
    pages = {"titles": titles_scene(script, words, facts, duration),
             "hud": hud_scene(script, words, brief, duration, sl),
             "fx": fx_scene(sl, duration),
             "captions": captions_scene(words, duration)}
    for name, page in pages.items():
        with open(os.path.join(comp, f"{name}.html"), "w", encoding="utf-8") as fh:
            fh.write(page)
    with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(index_html(sl, duration, brief))
    # placeholder mix so the project lints before the sound stage writes the real one
    mix = os.path.join(d, "assets", "audio", "mix.wav")
    if not os.path.exists(mix):
        _link(run.path("voice", "narration.wav"), mix)
    # the grade, through the CLI (realtime, seek-safe): vignette + fine grain on every shot
    gpath = os.path.join(d, ".grade.json")
    with open(gpath, "w", encoding="utf-8") as fh:
        json.dump(GRADE, fh)
    for s in sl["shots"]:
        hf.run(["media-treatment", "--project", ".", "--file", f"compositions/{s['id']}.html", "--selector",
                f"#{s['id']}-v", "--grading", ".grade.json", "--apply", "--json"], cwd=d, timeout=300)
    run.save("hf_compose.json", {"warnings": warnings, "quality": q})
    for w in warnings:
        log.warning("[compose] %s", w)


def validate(run):
    d = run.path("hf")
    if not os.path.exists(os.path.join(d, "index.html")):
        raise StageError("hf/index.html missing")
    r = hf.run(["lint"], cwd=d, check=False, timeout=600)
    errors = re.findall(r"(\d+) error", r.stdout or "")
    if r.returncode != 0 or (errors and int(errors[-1]) > 0):
        raise StageError("hyperframes lint failed:\n" + (r.stdout or "")[-3000:])
