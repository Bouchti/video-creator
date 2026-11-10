"""
Script + voiced beats -> one HyperFrames composition (index.html).

Every scene is a `.clip` section with absolute data-start / data-duration; every reveal is a tween on the
single paused root timeline at the exact second its beat starts; every beat is its own <audio> clip.
Fonts and GSAP are vendored next to the page, so a render needs no network and is repeatable.
"""
from __future__ import annotations

import html
import json
import math
import re

from pmp_video.config import BRAND, CHANNEL, GAP_SECONDS, SCENE_TAIL, SITE_LABEL, Shape

LETTERS = "ABCD"
ICON = ("<svg class='logo' viewBox='12 0 36 48' fill='none' xmlns='http://www.w3.org/2000/svg'>"
        "<g transform='translate(12, 4) scale(1.5)'>"
        "<path d='M10 2 L10 8 M14 2 L14 8' stroke='#7DD3FC' stroke-width='1.6' stroke-linecap='round'/>"
        "<path d='M10 8 L4 24 C3.5 25.5 4.5 27 6 27 L18 27 C19.5 27 20.5 25.5 20 24 L14 8' stroke='#7DD3FC' "
        "stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'/>"
        "<path d='M6.5 20 L17.5 20 C18.2 22 18.8 23.5 19 24 C19.3 24.8 18.8 26 18 26 L6 26 C5.2 26 4.7 24.8 5 24 "
        "C5.2 23.5 5.8 22 6.5 20 Z' fill='#BAE6FD' fill-opacity='0.55'/>"
        "<circle cx='9' cy='23' r='0.8' fill='#7DD3FC'/><circle cx='12' cy='24' r='1' fill='#7DD3FC'/>"
        "<circle cx='15' cy='22.5' r='0.7' fill='#7DD3FC'/></g></svg>")


def esc(text) -> str:
    return html.escape(str(text or ""), quote=True)


def fit(text: str, base: float, ref_chars: int, floor: float = 0.55) -> int:
    """Font size that keeps long text inside its box: shrinks with the square root of the overflow."""
    n = max(1, len(text or ""))
    return int(round(base * max(floor, min(1.0, math.sqrt(ref_chars / n)))))


# ---------------------------------------------------------------- timing

def schedule(script: dict, voiced: dict[str, dict]) -> float:
    """Give every scene and beat absolute times (in place). `voiced` maps beat text -> speak() result."""
    t = 0.0
    for scene in script["scenes"]:
        scene["start"] = round(t, 3)
        offset = 0.35 if scene["type"] not in ("pause",) else 0.0
        for b in scene["beats"]:
            v = voiced[b["say"]]
            b["start"], b["duration"], b["file"] = round(t + offset, 3), v["duration"], v["file"]
            b["words"] = [{**w, "start": round(t + offset + w["start"], 3), "end": round(t + offset + w["end"], 3)}
                          for w in v["words"]]
            offset += v["duration"] + GAP_SECONDS
        if scene["type"] == "pause":
            offset = float(scene.get("seconds", 5))
        else:
            offset += SCENE_TAIL - GAP_SECONDS
        minimum = {"hook": 1.6, "chapter": 2.2, "title": 3.0, "cta": 3.0}.get(scene["type"], 1.0)
        scene["duration"] = round(max(offset, minimum), 3)
        t += scene["duration"]
    script["duration"] = round(t, 3)
    return t


# ---------------------------------------------------------------- scene bodies

def _pill(text, cls="pill"):
    return f"<span class='{cls}'>{esc(text)}</span>" if text else ""


def _cards(sid, scene, shape: Shape, hidden: bool, why: bool) -> str:
    opts = scene["options"]
    longest = max(len(o) for o in opts)
    base = (46 if shape.portrait else 38) * (0.86 if why else 1.0)
    size = fit("x" * longest, base, 70)
    reasons = scene.get("reasons") or [""] * 4
    out = []
    for i, o in enumerate(opts):
        rv = " rv" if hidden else ""
        reason = (f"<div class='why rvw' id='{sid}-why-{i}'>{esc(reasons[i])}</div>"
                  if why and reasons[i] else "")
        out.append(
            f"<div class='card{rv}' id='{sid}-opt-{i}'><div class='glow good' id='{sid}-glow-{i}'></div>"
            f"<div class='glow warn' id='{sid}-focus-{i}'></div>"
            f"<div class='letter'>{LETTERS[i]}</div><div class='otext' style='font-size:{size}px'>{esc(o)}"
            f"{reason}</div><div class='strike' id='{sid}-strike-{i}'></div>"
            f"<div class='mark bad' id='{sid}-bad-{i}'>&#10005;</div><div class='mark ok' id='{sid}-ok-{i}'>&#10003;</div></div>")
    return f"<div class='cards'>{''.join(out)}</div>"


def scene_html(sid: str, scene: dict, shape: Shape) -> str:
    kind = scene["type"]
    p = shape.portrait
    if kind == "hook":
        size = fit(scene["text"], 104 if p else 96, 48)
        body = (f"{_pill(scene.get('badge'), 'pill accent')}"
                f"<h1 class='hook' style='font-size:{size}px'>{esc(scene['text'])}</h1>")
    elif kind == "scenario":
        size = fit(scene["text"], 56 if p else 50, 160)
        body = (f"<div class='pills'>{_pill(scene.get('domain'))}{_pill((scene.get('approach') or '').title())}</div>"
                f"<div class='panel'><p class='scenario' style='font-size:{size}px'>{esc(scene['text'])}</p></div>")
    elif kind in ("options", "pause", "reveal", "trap"):
        head = {"options": "What would you do?", "pause": "Pause and pick", "reveal": "Answer",
                "trap": "The trap"}[kind]
        countdown = ""
        if kind == "pause":
            secs = int(round(scene.get("seconds", 5)))
            digits = "".join(f"<span class='digit' id='{sid}-d{k}'>{k}</span>" for k in range(secs, 0, -1))
            countdown = f"<div class='countdown'>{digits}<div class='bar'><div class='fill' id='{sid}-fill'></div></div></div>"
        body = (f"<div class='qhead'>{esc(head)}</div>"
                + _cards(sid, scene, shape, hidden=kind == "options", why=kind == "reveal") + countdown)
    elif kind == "rule":
        size = fit(scene["text"], 84 if p else 76, 50)
        body = (f"{_pill(scene.get('label'), 'pill accent')}"
                f"<div class='rule' style='font-size:{size}px'>{esc(scene['text'])}</div>")
    elif kind == "cta":
        body = (f"{ICON}<div class='cta'>{esc(scene['text'])}</div>"
                f"<div class='url'>{esc(scene.get('url') or SITE_LABEL)}</div>"
                f"<div class='sub'>Free PMP exam simulator with an AI coach</div>")
    elif kind == "compare":
        sides = []
        for key in ("left", "right"):
            s = scene[key]
            sides.append(f"<div class='side rv' id='{sid}-{key}'><div class='term'>{esc(s['term'])}</div>"
                         f"<div class='def'>{esc(s['definition'])}</div>"
                         f"<div class='ex'><b>Example</b> {esc(s['example'])}</div></div>")
        body = f"<div class='vs-wrap'>{sides[0]}<div class='vs'>vs</div>{sides[1]}</div>"
    elif kind == "quiz":
        body = (f"{_pill('Quick check', 'pill accent')}"
                f"<div class='panel rv' id='{sid}-question'><p class='scenario'>{esc(scene['question'])}</p></div>"
                f"<div class='answer rv' id='{sid}-answer'>&#10003; {esc(scene['answer'])}</div>")
    elif kind == "dodont":
        body = (f"<div class='panel rv' id='{sid}-scenario'><p class='scenario'>{esc(scene['scenario'])}</p></div>"
                f"<div class='dd dont rv' id='{sid}-dont'><b>&#10005; Don't</b> {esc(scene['dont'])}</div>"
                f"<div class='dd do rv' id='{sid}-do'><b>&#10003; Do</b> {esc(scene['do'])}</div>")
    elif kind == "title":
        size = fit(scene["title"], 100 if p else 92, 40)
        body = (f"{ICON}{_pill(scene.get('kicker'), 'pill accent')}"
                f"<h1 class='title' style='font-size:{size}px'>{esc(scene['title'])}</h1>"
                f"<div class='sub'>{esc(scene.get('subtitle'))}</div>")
    elif kind == "chapter":
        numbered = not scene.get("title", "").startswith(("Question", "Check"))    # course chapters only
        label = f"{scene['number']:02d}" if numbered else ""
        body = (f"<div class='chnum'>{esc(label)}</div>"
                f"<h1 class='chtitle'>{esc(scene['title'])}</h1>"
                + (f"<div class='sub'>{esc(scene['chapter'])}</div>" if scene.get("chapter")
                   and scene["chapter"] != scene["title"] else ""))
    elif kind in ("bullets", "recap"):
        items = "".join(f"<li class='rv' id='{sid}-b-{i}'>{esc(b)}</li>" for i, b in enumerate(scene["bullets"]))
        body = f"<h2 class='heading'>{esc(scene['heading'])}</h2><ul class='bullets'>{items}</ul>"
    elif kind == "example":
        size = fit(scene["text"], 52 if p else 46, 220)
        body = (f"{_pill('Exam scenario', 'pill accent')}<h2 class='heading'>{esc(scene['heading'])}</h2>"
                f"<div class='panel'><p class='scenario' style='font-size:{size}px'>{esc(scene['text'])}</p></div>")
    else:
        raise ValueError(f"Unknown scene type {kind}")
    return (f"<section id='{sid}' class='clip scene {kind}' data-start='{scene['start']}' "
            f"data-duration='{scene['duration']}' data-track-index='1'><div class='inner'>{body}</div></section>")


# ---------------------------------------------------------------- animation

def _tweens(sid: str, scene: dict) -> list[str]:
    t0 = scene["start"]
    js = [] if t0 == 0 else [   # the first frame is the Shorts cover: the opening scene is there from frame 0
        f"tl.fromTo('#{sid} .inner', {{opacity: 0, y: 28}}, {{opacity: 1, y: 0, duration: 0.45, "
        f"ease: 'power3.out'}}, {t0:.3f});"]
    kind = scene["type"]
    if kind == "pause":
        secs = int(round(scene.get("seconds", 5)))
        for i, k in enumerate(range(secs, 0, -1)):
            js.append(f"tl.set('#{sid}-d{k}', {{opacity: 1}}, {t0 + i:.3f});")
            if i + 1 < secs:
                js.append(f"tl.set('#{sid}-d{k}', {{opacity: 0}}, {t0 + i + 1:.3f});")
        js.append(f"tl.fromTo('#{sid}-fill', {{scaleX: 1}}, {{scaleX: 0, duration: {secs}, ease: 'none'}}, {t0:.3f});")
    if kind in ("bullets", "recap", "options") and not scene["beats"]:
        js.append(f"tl.to('#{sid} .rv', {{opacity: 1, y: 0, duration: 0.35, stagger: 0.25}}, {t0 + 0.3:.3f});")
    for b in scene["beats"]:
        for show in [b.get("show")] + list(b.get("also", [])):
            if show:
                js += _reveal(sid, show, b["start"], why=kind == "reveal" and any(scene.get("reasons") or []))
    return js


def _reveal(sid: str, show: str, t: float, why: bool = False) -> list[str]:
    at = f"{t:.3f}"
    if show == "opt-all":
        return [f"tl.to('#{sid} .card', {{opacity: 1, y: 0, duration: 0.35, stagger: 0.12}}, {at});"]
    m = re.fullmatch(r"(opt|strike|good|focus|b)-(\d+)", show)
    if m:
        kind, i = m.group(1), m.group(2)
        if kind in ("opt", "b"):
            return [f"tl.to('#{sid}-{kind}-{i}', {{opacity: 1, y: 0, duration: 0.35, ease: 'power2.out'}}, {at});"]
        if kind == "strike":
            return [f"tl.to('#{sid}-opt-{i}', {{opacity: 0.42, duration: 0.3}}, {at});",
                    f"tl.fromTo('#{sid}-strike-{i}', {{scaleY: 0}}, {{scaleY: 1, duration: 0.35}}, {at});",
                    f"tl.to('#{sid}-bad-{i}', {{opacity: 1, duration: 0.2}}, {at});",
                    f"tl.to('#{sid}-focus-{i}', {{opacity: 0, duration: 0.2}}, {at});"] + (
                [f"tl.to('#{sid}-why-{i}', {{opacity: 1, duration: 0.3}}, {at});"] if why else [])
        if kind == "good":
            return [f"tl.to('#{sid}-glow-{i}', {{opacity: 1, duration: 0.35}}, {at});",
                    f"tl.fromTo('#{sid}-opt-{i}', {{scale: 1}}, {{scale: 1.03, duration: 0.25, yoyo: true, "
                    f"repeat: 1}}, {at});",
                    f"tl.to('#{sid}-ok-{i}', {{opacity: 1, duration: 0.2}}, {at});"] + (
                [f"tl.to('#{sid}-why-{i}', {{opacity: 1, duration: 0.3}}, {at});"] if why else [])
        if kind == "focus":
            return [f"tl.to('#{sid}-focus-{i}', {{opacity: 1, duration: 0.3}}, {at});"]
    return [f"tl.to('#{sid}-{show}', {{opacity: 1, y: 0, duration: 0.4, ease: 'power2.out'}}, {at});"]


# ---------------------------------------------------------------- captions

def _caption_groups(script: dict, size: int) -> list[list[dict]]:
    groups: list[list[dict]] = []
    for scene in script["scenes"]:
        for b in scene["beats"]:
            cur: list[dict] = []
            for w in b["words"]:
                cur.append(w)
                if len(cur) >= size or re.search(r"[.!?,:;]$", w["text"]):
                    groups.append(cur)
                    cur = []
            if cur:
                groups.append(cur)
    return groups


def captions(script: dict, shape: Shape) -> tuple[str, list[str]]:
    groups = _caption_groups(script, shape.caption_words)
    spans, js = [], []
    for gi, g in enumerate(groups):
        start = g[0]["start"]
        end = groups[gi + 1][0]["start"] if gi + 1 < len(groups) and groups[gi + 1][0]["start"] - g[-1]["end"] < 0.6 \
            else g[-1]["end"] + 0.25
        words = "".join(f"<span id='w{gi}-{wi}'>{esc(w['text'])}</span> " for wi, w in enumerate(g))
        spans.append(f"<div class='cg' id='cg{gi}'>{words.strip()}</div>")
        js.append(f"tl.set('#cg{gi}', {{opacity: 1}}, {start:.3f}); tl.set('#cg{gi}', {{opacity: 0}}, {end:.3f});")
        if shape.portrait:                                   # word-by-word highlight on shorts
            for wi, w in enumerate(g):
                js.append(f"tl.set('#w{gi}-{wi}', {{color: '{BRAND['sky']}'}}, {w['start']:.3f});")
                if wi + 1 < len(g):
                    js.append(f"tl.set('#w{gi}-{wi}', {{color: '#FFFFFF'}}, {g[wi + 1]['start']:.3f});")
    total = script["duration"]
    layer = (f"<div id='captions' class='clip' data-start='0' data-duration='{total}' data-track-index='3'>"
             + "".join(spans) + "</div>")
    return layer, js


# ---------------------------------------------------------------- page

def css(shape: Shape) -> str:
    b = BRAND
    p = shape.portrait
    pad = "220px 84px 500px" if p else "110px 150px 190px"
    return f"""
@font-face {{ font-family: 'Plex'; src: url('assets/fonts/ibm-plex-sans-latin-400-normal.woff2') format('woff2'); font-weight: 400; }}
@font-face {{ font-family: 'Plex'; src: url('assets/fonts/ibm-plex-sans-latin-500-normal.woff2') format('woff2'); font-weight: 500; }}
@font-face {{ font-family: 'Plex'; src: url('assets/fonts/ibm-plex-sans-latin-600-normal.woff2') format('woff2'); font-weight: 600; }}
@font-face {{ font-family: 'Plex'; src: url('assets/fonts/ibm-plex-sans-latin-700-normal.woff2') format('woff2'); font-weight: 700; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: {shape.width}px; height: {shape.height}px; overflow: hidden; background: {b['ground']}; }}
#root {{ position: relative; width: 100%; height: 100%; font-family: 'Plex', 'Segoe UI', Arial, sans-serif; color: {b['ink']}; }}
.bg {{ position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 38%, {b['ground_2']} 0%, {b['ground']} 70%); }}
.dots {{ position: absolute; inset: 0; background-image: radial-gradient({b['line']} 1.5px, transparent 1.5px); background-size: 48px 48px; opacity: .35; }}
.brandbar {{ position: absolute; top: {90 if p else 44}px; left: {84 if p else 70}px; display: flex; align-items: center; gap: 16px; font-weight: 600; font-size: {34 if p else 28}px; color: {b['sky_soft']}; }}
.brandbar .logo {{ width: {44 if p else 36}px; height: auto; }}
.scene {{ position: absolute; inset: 0; }}
.inner {{ position: absolute; inset: 0; padding: {pad}; display: flex; flex-direction: column; justify-content: center; align-items: {'stretch' if p else 'center'}; gap: {34 if p else 28}px; text-align: {'left' if p else 'center'}; }}
.pill {{ align-self: {'flex-start' if p else 'center'}; display: inline-block; border: 2px solid {b['line']}; color: {b['sky_soft']}; border-radius: 999px; padding: 10px 26px; font-size: {32 if p else 26}px; font-weight: 600; letter-spacing: .02em; }}
.pill.accent {{ background: {b['brand']}; border-color: {b['brand']}; color: #fff; }}
.pills {{ display: flex; gap: 14px; justify-content: {'flex-start' if p else 'center'}; }}
.hook, .title {{ font-weight: 700; line-height: 1.08; letter-spacing: -0.02em; }}
.panel {{ background: {b['panel']}; border: 2px solid {b['line']}; border-radius: 28px; padding: {'44px 46px' if p else '40px 56px'}; max-width: 1500px; }}
.scenario {{ font-size: {52 if p else 44}px; line-height: 1.32; font-weight: 500; }}
.qhead {{ font-size: {40 if p else 34}px; font-weight: 600; color: {b['sky_soft']}; text-transform: uppercase; letter-spacing: .08em; }}
.cards {{ display: grid; grid-template-columns: {'1fr' if p else '1fr 1fr'}; gap: {22 if p else 26}px; width: 100%; max-width: 1640px; }}
.card {{ position: relative; display: flex; gap: 26px; align-items: flex-start; background: {b['panel']}; border: 2px solid {b['line']}; border-radius: 24px; padding: {'26px 30px' if p else '26px 30px'}; text-align: left; overflow: hidden; }}
.card.rv {{ opacity: 0; transform: translateY(24px); }}
.letter {{ flex: none; width: {74 if p else 64}px; height: {74 if p else 64}px; border-radius: 18px; background: {b['brand']}; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: {40 if p else 34}px; position: relative; z-index: 2; }}
.otext {{ position: relative; z-index: 2; line-height: 1.25; font-weight: 500; padding-top: 6px; padding-right: 54px; }}
.why {{ margin-top: 10px; font-size: {32 if p else 26}px; font-weight: 400; color: {b['muted']}; line-height: 1.3; opacity: 0; }}
.glow {{ position: absolute; inset: 0; opacity: 0; border-radius: 22px; z-index: 1; }}
.glow.good {{ background: rgba(34,197,94,.20); box-shadow: inset 0 0 0 4px {b['good']}; }}
.glow.warn {{ background: rgba(245,158,11,.16); box-shadow: inset 0 0 0 4px {b['warn']}; }}
.strike {{ position: absolute; left: 0; top: 0; bottom: 0; width: 8px; background: {b['bad']}; transform: scaleY(0); transform-origin: center top; z-index: 3; }}
.mark {{ position: absolute; top: 18px; right: 24px; font-size: {48 if p else 40}px; font-weight: 700; opacity: 0; z-index: 3; }}
.mark.bad {{ color: {b['bad']}; }} .mark.ok {{ color: {b['good']}; }}
.countdown {{ display: flex; align-items: center; gap: 30px; justify-content: center; margin-top: 10px; }}
.digit {{ position: absolute; opacity: 0; font-size: 96px; font-weight: 700; color: {b['sky']}; }}
.countdown {{ position: relative; height: 120px; }}
.countdown .digit {{ left: 0; }}
.bar {{ margin-left: 120px; flex: 1; height: 16px; background: {b['line']}; border-radius: 8px; overflow: hidden; }}
.fill {{ width: 100%; height: 100%; background: {b['sky']}; transform-origin: left center; }}
.rule {{ font-weight: 700; line-height: 1.15; letter-spacing: -0.01em; }}
.cta {{ font-size: {78 if p else 70}px; font-weight: 700; line-height: 1.1; }}
.url {{ font-size: {72 if p else 64}px; font-weight: 700; color: {b['sky']}; }}
.sub {{ font-size: {38 if p else 34}px; color: {b['muted']}; font-weight: 500; }}
.inner > .logo {{ width: {150 if p else 120}px; height: auto; align-self: {'flex-start' if p else 'center'}; }}
.vs-wrap {{ display: flex; flex-direction: {'column' if p else 'row'}; gap: 28px; align-items: stretch; width: 100%; }}
.side {{ flex: 1; background: {b['panel']}; border: 2px solid {b['line']}; border-radius: 28px; padding: 40px; opacity: 0; transform: translateY(24px); text-align: left; }}
.term {{ font-size: {64 if p else 58}px; font-weight: 700; color: {b['sky']}; margin-bottom: 14px; }}
.def {{ font-size: {44 if p else 38}px; font-weight: 500; line-height: 1.3; margin-bottom: 18px; }}
.ex {{ font-size: {36 if p else 30}px; color: {b['muted']}; line-height: 1.35; }}
.ex b {{ color: {b['sky_soft']}; margin-right: 8px; }}
.vs {{ align-self: center; font-size: 44px; font-weight: 700; color: {b['muted']}; }}
.rv {{ opacity: 0; transform: translateY(24px); }}
.answer {{ font-size: {54 if p else 48}px; font-weight: 700; color: {b['good']}; }}
.dd {{ border-radius: 24px; padding: 32px 36px; font-size: {44 if p else 38}px; font-weight: 500; line-height: 1.3; text-align: left; }}
.dd b {{ display: block; font-size: {34 if p else 30}px; margin-bottom: 8px; }}
.dd.dont {{ background: rgba(244,63,94,.12); border: 2px solid {b['bad']}; }} .dd.dont b {{ color: {b['bad']}; }}
.dd.do {{ background: rgba(34,197,94,.12); border: 2px solid {b['good']}; }} .dd.do b {{ color: {b['good']}; }}
.chnum {{ font-size: 150px; font-weight: 700; color: {b['sky']}; line-height: 1; }}
.chtitle {{ font-size: {88 if p else 84}px; font-weight: 700; line-height: 1.1; }}
.heading {{ font-size: {66 if p else 60}px; font-weight: 700; line-height: 1.15; }}
.bullets {{ list-style: none; display: flex; flex-direction: column; gap: 22px; text-align: left; max-width: 1500px; }}
.bullets li {{ font-size: {46 if p else 42}px; font-weight: 500; line-height: 1.3; padding-left: 48px; position: relative; }}
.bullets li::before {{ content: ''; position: absolute; left: 0; top: .5em; width: 18px; height: 18px; border-radius: 5px; background: {b['sky']}; }}
.reveal .cards {{ gap: {14 if p else 18}px; }}
.reveal .card {{ padding: {'18px 24px' if p else '20px 26px'}; }}
.reveal .letter {{ width: {62 if p else 56}px; height: {62 if p else 56}px; font-size: {34 if p else 30}px; }}
.reveal .why {{ font-size: {29 if p else 24}px; margin-top: 6px; }}
.reveal .inner {{ gap: 20px; }}
#captions {{ position: absolute; left: 0; right: 0; top: {1460 if p else 930}px; height: {200 if p else 110}px; z-index: 20; }}
.cg {{ position: absolute; left: {70 if p else 160}px; right: {70 if p else 160}px; top: 0; text-align: center; opacity: 0; font-weight: 700; font-size: {66 if p else 44}px; line-height: 1.15; color: #fff; -webkit-text-stroke: {'3px' if p else '0'} {b['ground']}; paint-order: stroke fill; text-shadow: 0 4px 18px rgba(0,0,0,.55); }}
"""


def build(script: dict, shape: Shape, *, captions_on: bool = True, music: str | None = None) -> str:
    total = script["duration"]
    scenes, js, audio = [], [], []
    for i, scene in enumerate(script["scenes"]):
        sid = f"s{i}"
        scenes.append(scene_html(sid, scene, shape))
        js += _tweens(sid, scene)
        for b in scene["beats"]:
            audio.append(f"<audio id='vo{len(audio)}' data-start='{b['start']}' data-duration='{b['duration']}' data-track-index='5' "
                         f"data-volume='1' src='audio/{b['file']}'></audio>")
    cap_html, cap_js = captions(script, shape) if captions_on else ("", [])
    if music:
        audio.append(f"<audio id='music' data-start='0' data-duration='{total}' data-track-index='6' data-volume='0.09' "
                     f"data-fade-in='1' data-fade-out='2' src='audio/{music}'></audio>")
    meta = json.dumps({"format": script["format"], "title": script["title"]}, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="en" data-resolution="{'portrait' if shape.portrait else 'landscape'}">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width={shape.width}, height={shape.height}" />
<meta name="pmp-video" content='{esc(meta)}' />
<script src="assets/gsap.min.js"></script>
<style>{css(shape)}</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{total}" data-width="{shape.width}" data-height="{shape.height}">
<div id="bg" class="clip bg" data-start="0" data-duration="{total}" data-track-index="0"><div class="dots"></div></div>
<div id="brand" class="clip brandbar" data-start="0" data-duration="{total}" data-track-index="2">{ICON}<span>{esc(CHANNEL)}</span></div>
{''.join(scenes)}
{cap_html}
{''.join(audio)}
</div>
<script>
const tl = gsap.timeline({{ paused: true }});
{chr(10).join(js + cap_js)}
window.__timelines = window.__timelines || {{}};
window.__timelines["main"] = tl;
tl.seek(0);
</script>
</body>
</html>
"""
