"""
The Build-It quality bar, shared by the review BEFORE the render (preview stage) and the final QA after it, so a
storyboard that passes the preview is judged by the same rules as the finished video.

    RUBRIC                                  what each item means (every item must reach PASS for a render)
    overlay(still, t, ...)                  draw the captions, label pills and loop map the composer will add, so
                                            the reviewer judges what the viewer will see, not a bare render
    audio_score(cues, duration, loudness)   the audio item, MEASURED (a vision model cannot hear)
    judge(run, sheet, captions, extra)      the vision review: scores, per-still problems, concrete fixes, and
                                            which stage the fixes belong to (storyboard or script)
"""
from __future__ import annotations

import json
import logging

from PIL import Image, ImageDraw, ImageFont

from agents import llm

from . import compose
from .assets.fetch import font
from .config import CAPTION_Y, SUBJECT_BAND, W, H

log = logging.getLogger("pipeline")
PASS = 4
PANEL = 3               # independent reviews per round (median per item)
RUBRIC = {
    "hook": "The first 2 s show something surprising that makes you want the answer",
    "story": "Each part arrives as the answer to a problem; a 12-year-old can follow the whole chain and SEE how the "
             "parts connect and what flows between them",
    "look": "Premium and bright: a clean studio, the real machine recognisable at a glance, parts clearly mounted "
            "on it, nothing empty, cut off, blurred over the subject or floating oddly",
    "animation": "Parts arrive and act with weight; mechanisms run; the invisible (flows, heat, cold) is shown",
    "captions_labels": "Captions, label pills and the loop map are readable on a phone, never cover the subject",
    "pacing": "Calm and clear: every step has time to land before the next, one change at a time, no dead air",
    "accuracy": "Every claim and number is right; analogies simplified but correct",
}
# what a 4 concretely needs, item by item: checks, not taste (the bar is the same; its meaning is spelled out)
FOUR = {
    "hook": "within 2 s the hook object is on screen doing something surprising, and the narration poses a question",
    "story": "every part arrives right after the problem it solves; each part is shown connected to the parts it "
             "works with; the whole loop is seen working at least once (e.g. a finale where it lights up in order)",
    "look": "the subject is whole, sharp and big enough in every shot; no empty half-frame; the machine reads as the "
            "real product; mounted parts sit on it, not in the air",
    "animation": "parts fly in and click; motors visibly run; every flow, heat and cold change the narration names "
                 "is shown as it is named",
    "captions_labels": "captions readable and off the subject; each pill near the thing it names; the loop strip "
                       "legible when shown (it appears on whole-machine shots only, by design)",
    "pacing": "no shot over ~6 s without a change; never two near-identical shots in a row; each step gets its own "
              "beat; nothing important crammed into under 2 s",
    "accuracy": "no false claim; colours follow the legend at every moment; pills match what they point at",
}
SCHEMA = {"type": "object", "properties": {
    "scores": {"type": "object", "properties": {k: {"type": "object", "properties": {
        "score": {"type": "integer", "minimum": 1, "maximum": 5}, "why": {"type": "string"}},
        "required": ["score", "why"]} for k in RUBRIC}, "required": list(RUBRIC)},
    "stills": {"type": "array", "items": {"type": "object", "properties": {
        "n": {"type": "integer"}, "ok": {"type": "boolean"}, "problem": {"type": "string"}},
        "required": ["n", "ok", "problem"]}},
    "fixes": {"type": "array", "items": {"type": "string"},
              "description": "concrete changes, each naming the shot / word / part / event to change"},
    "fix_stage": {"type": "string", "enum": ["storyboard", "script"],
                  "description": "script only when the narration itself (hook, story, facts) must change"},
    "engine_gaps": {"type": "array", "items": {"type": "string"},
                    "description": "what you would want that the kit cannot show (not storyboard fixes)"},
}, "required": ["scores", "stills", "fixes", "fix_stage", "engine_gaps"]}


def engine_notes(sb: dict, measured: list[str] | None = None) -> str:
    """What the reviewer must know to judge fairly and to write fixes the storyboard can carry out: how the
    engine draws things on purpose, the storyboard's vocabulary, and (when measured) the layout as measured from
    the geometry."""
    from .kit import hosts, vocab
    host = (sb.get("machine") or {}).get("host", "machine")
    about = hosts.HOSTS.get(host, hosts.HOSTS["machine"])[3]
    lay = "" if measured is None else "\nLayout, measured from the 3D geometry:\n" + (
        "\n".join(f"- {m}" for m in measured) if measured else
        "nothing is cut by the frame edge, under a caption or the loop strip, and no label pill covers a part "
        "(trust this over the low-quality preview)")
    return f"""How this engine draws the film (deliberate and correct; do not ask to change it):
- The {host} is {about}. Parts in inside_* slots are inside it, seen through the cut-open side; parts in back_*
  slots are fixed on the OUTSIDE of its dark back panel, where the real machine has them (a fridge's compressor and
  condenser coil sit on the outside of its back).
- COLOUR LEGEND of the moving dashes in pipes: deep blue = cold liquid, pale cyan = cold gas, red = hot gas,
  orange = warm liquid. Where a state CHANGES the dashes shade along the coil: a cold coil going from deep blue
  (inlet) to pale cyan (outlet) IS the liquid boiling into gas; a hot coil going from red to orange IS the gas
  condensing into liquid. Warm orange particle waves (heat_flow) show heat moving; parts glow warm (heat), frost
  white (frost), or glow at their edges (highlight). The loop strip at the top shows only on whole-machine shots.
- The camera keeps one home view of the whole machine; part / area / prop shots frame what they name.
Write every fix in the storyboard's terms: shots (start word; frame {' | '.join(vocab.FRAMES)}; move
{' | '.join(vocab.MOVES)}; which parts are 'on'), parts and slots, events ({', '.join(vocab.EVENTS)}), labels and
their words. Put anything the kit cannot show in engine_gaps, not in fixes.{lay}"""


# ------------------------------------------------------------ what the viewer sees: overlays on a still

def _font(name: str, px: int):
    return ImageFont.truetype(font(name), px)


def overlay(src: str, dst: str, t: float, words: list[dict], labels: list[dict], anchors: dict | None,
            loop: dict | None, boxes: dict | None = None):
    """Draw on a rendered still (any size, 9:16) the caption group, label pills and loop map shown at time t,
    placed exactly as buildit/compose places them. Returns the pill rects drawn (master pixels)."""
    im = Image.open(src).convert("RGB")
    k = im.width / W
    d = ImageDraw.Draw(im, "RGBA")
    # caption group
    cr = compose.caption_rect(words, t)
    if cr:
        g = next(g for g in compose.caption_groups(words) if g[0]["start"] - 0.05 <= t <= g[-1]["end"] + 0.15)
        f = _font("Poppins-Black.ttf", int(68 * k))
        d.rounded_rectangle(tuple(v * k for v in cr), radius=26 * k, fill=(16, 20, 28, 210))
        d.text(((cr[0] + cr[2]) / 2 * k, (cr[1] + cr[3]) / 2 * k), " ".join(w["text"] for w in g), font=f,
               fill=(255, 255, 255), anchor="mm")
    # label pills on the free spot nearest their part
    map_on = compose.map_visible(loop, t)
    taken = []
    for lb in labels:
        if not lb["t0"] <= t <= lb["t1"] or not anchors:
            continue
        p = anchors.get(lb["anchor"])
        if not p:
            continue
        if not compose.is_title(lb) and len(p) > 2 and not p[2]:
            continue                                # what it names is out of sight: the pill waits (as in compose)
        ax, ay = p[0], p[1]
        pw = compose.pill_width(lb)
        concept = compose.is_title(lb)
        if concept:
            px, py = compose.title_spot(pw, map_on)
        else:
            px, py = compose.place_pill(ax, ay, pw, boxes or {}, map_on=map_on, taken=taken)
        taken.append((px, py, px + pw, py + compose.PILL_H))
        lx, ly = compose.leader_start(px, py, pw, ax)
        f = _font("Poppins-ExtraBold.ttf", int(compose.PILL_PX * k))
        if not concept:
            d.line((lx * k, ly * k, ax * k, ay * k), fill=(29, 23, 18, 255), width=int(4 * k))
            d.ellipse(((ax - 7) * k, (ay - 7) * k, (ax + 7) * k, (ay + 7) * k), fill=(255, 210, 58, 255),
                      outline=(29, 23, 18, 255), width=max(1, int(3 * k)))
        d.rounded_rectangle((px * k, py * k, (px + pw) * k, (py + compose.PILL_H) * k), radius=36 * k,
                            fill=(255, 255, 255, 255), outline=(29, 23, 18, 255), width=int(3 * k))
        d.text(((px + pw / 2) * k, (py + compose.PILL_H / 2) * k), lb["text"].upper(), font=f, fill=(29, 23, 18),
               anchor="mm")
    # the loop strip across the top
    if map_on:
        x0, y0 = compose.MAP_X * k, compose.MAP_Y * k
        d.rounded_rectangle((x0, y0, x0 + compose.MAP_W * k, y0 + compose.MAP_H * k), radius=30 * k,
                            fill=(16, 20, 28, 184))
        g = compose.loop_geometry(loop)
        f = _font("Poppins-ExtraBold.ttf", int(compose.map_font_px(loop) * k))
        for e in loop["edges"]:
            if t >= e["t_in"] and e["id"] in g["edges"]:
                kinds = [fl for fl in e["flows"] if fl[0] <= t]
                col = compose.FLOW_HEX.get(kinds[-1][1] or "", "#ffffff") if kinds and kinds[-1][2] else "#8e98a3"
                pts = [(x0 + x * k, y0 + y * k) for x, y in g["edges"][e["id"]]["pts"]]
                d.line(pts, fill=col, width=int(7 * k), joint="curve")
        for nd in loop["nodes"]:
            if t < nd["t_in"]:
                continue
            x, y, _w = g["nodes"][nd["id"]]
            hot = any(a <= t <= b for a, b in nd["hl"])
            tw = d.textlength(nd["name"], font=f)
            bx0, by0 = x0 + x * k - tw / 2 - 13 * k, y0 + y * k - 20 * k
            d.rounded_rectangle((bx0, by0, bx0 + tw + 26 * k, by0 + 40 * k), radius=14 * k,
                                fill="#ffd23a" if hot else "#ffffff")
            d.text((x0 + x * k, y0 + y * k), nd["name"], font=f, fill="#10141c", anchor="mm")
    im.save(dst, quality=90)
    return taken


# ------------------------------------------------------------ the layout, measured

SMALL_BELOW = {"machine": 0.72, "area": 0.5, "part": 0.3, "prop": 0.42}   # subject height / band height


def layout_faults(t: float, shot: dict, boxes: dict, words: list[dict], loop: dict | None,
                  pills=(), props=()) -> list[str]:
    """What is measurably wrong with the composition of the frame at time t (boxes: {id: screen rect} of the
    real geometry): the subject cut by the frame edge, too small, under the caption or the loop strip; another
    part sliced by the frame edge; a pill on a part. Empty when the frame is clean."""
    out = []
    frame = shot.get("frame", "area")
    ids = [q for q in shot.get("on", []) if q in boxes]
    if frame == "machine":
        ids = ["machine"] + ids
    rs = [boxes[q] for q in ids if q in boxes]
    if not rs:
        return [f"none of {ids or ['the machine']} is on screen"]
    sub = (min(r[0] for r in rs), min(r[1] for r in rs), max(r[2] for r in rs), max(r[3] for r in rs))
    sw, sh = sub[2] - sub[0], sub[3] - sub[1]
    name = ", ".join(ids)
    for side, over in (("left", -sub[0]), ("right", sub[2] - W), ("top", -sub[1]), ("bottom", sub[3] - H)):
        if over > 0.04 * (sw if side in ("left", "right") else sh):
            out.append(f"{name} is cut by the {side} edge of the frame")
    band = SUBJECT_BAND[1] - SUBJECT_BAND[0]
    if frame != "area" and sh < SMALL_BELOW[frame] * band and sw < 0.6 * W:     # an area shot is about context
        out.append(f"{name} is small ({sh / band:.0%} of the picture height)")
    cr = compose.caption_rect(words, t)
    if cr and frame != "machine" and compose._overlap(cr, sub) > 0.08 * (cr[2] - cr[0]) * (cr[3] - cr[1]):
        out.append(f"the caption covers {name}")
    if cr:
        for q, r in boxes.items():
            if q not in ids and q != "machine" and compose._overlap(cr, r) > 0.3 * (cr[2] - cr[0]) * (cr[3] - cr[1]):
                out.append(f"the caption sits on {q}")
    if compose.map_visible(loop, t):
        mr = (compose.MAP_X, compose.MAP_Y, compose.MAP_X + compose.MAP_W, compose.MAP_Y + compose.MAP_H)
        if compose._overlap(mr, sub) > 0.06 * sw * sh:
            out.append(f"the loop strip covers the top of {name}")
    for q, r in boxes.items():
        # in a close shot of a mounted part its neighbours are context and may run off the edge; a prop shot
        # and a machine shot must show everything whole
        if q in ids or q == "machine" or (frame in ("part", "area", "prop") and q not in props):
            continue
        inside = compose._overlap(r, (0, 0, W, H))
        whole = max(1.0, (r[2] - r[0]) * (r[3] - r[1]))
        if 0.01 * W * H < inside < 0.85 * whole:
            out.append(f"{q} is sliced by the frame edge")
    for pr in pills:
        for q, r in boxes.items():
            if q != "machine" and compose._overlap(pr, r) > 0.2 * (pr[2] - pr[0]) * (pr[3] - pr[1]):
                out.append(f"a label pill covers {q}")
    return out


# ------------------------------------------------------------ audio, measured

def audio_score(cues: list, duration: float, loudness: dict | None = None) -> dict:
    """The audio item from facts, not a guess: target loudness, sparse one-shots, no long jets, one bed at a time."""
    problems = []
    one = [c for c in cues if len(c) < 3]
    if duration and len(one) / duration > 0.45:
        problems.append(f"{len(one)} one-shot sounds in {duration:.0f} s is busy (max ~1 per 2.2 s)")
    sprays = [c for c in cues if c[1] == "spray" and len(c) > 2 and c[2] > 2.5]
    if sprays:
        problems.append(f"{len(sprays)} spray sound(s) longer than 2.5 s")
    beds = sorted((c[0], c[0] + c[2]) for c in cues if len(c) > 2 and c[1] in ("hum", "whirr", "turbine", "boil"))
    for (a0, a1), (b0, b1) in zip(beds, beds[1:]):
        if b0 < a1 - 0.5 and min(a1, b1) - b0 > 4.0:
            problems.append("two machine loops play together for more than 4 s")
            break
    if loudness and (abs(loudness.get("I", -14) + 14) > 1.0 or loudness.get("TP", -2) > -0.5):
        problems.append(f"loudness off target: {loudness}")
    return {"score": 4 if not problems else 2, "why": "; ".join(problems) or
            "voice on top, sparse effects tied to the picture, one machine loop at a time, -14 LUFS"}


# ------------------------------------------------------------ the vision review

def sheets(paths: list[str], captions: list[str], out_prefix: str, per: int = 8) -> list[str]:
    """Contact sheets big enough to READ captions and pills (405 x 720 tiles, 8 per sheet): a reviewer shown
    thumbnails judges every text as tiny."""
    from PIL import Image as _I
    out = []
    w, h, cols = 405, 720, 4
    try:
        f = ImageFont.truetype("arial.ttf", 22)
    except OSError:
        f = ImageFont.load_default()
    for s in range(0, len(paths), per):
        chunk = list(zip(paths, captions))[s:s + per]
        rows = (len(chunk) + cols - 1) // cols
        img = _I.new("RGB", (cols * w, rows * (h + 40)), (20, 20, 22))
        d = ImageDraw.Draw(img)
        for k, (p, c) in enumerate(chunk):
            x, y = (k % cols) * w, (k // cols) * (h + 40)
            img.paste(_I.open(p).convert("RGB").resize((w, h)), (x, y))
            d.text((x + 6, y + h + 8), c[:44], fill=(240, 240, 240), font=f)
        path = f"{out_prefix}_{s // per + 1}.jpg"
        img.save(path, quality=88)
        out.append(path)
    return out


def judge(run, sheet_path, captions: list[str], extra: str = "") -> dict:
    """sheet_path: one contact sheet or a list of them (in still order)."""
    script, sb = run.need("script.json"), run.need("storyboard.json")
    story = "\n".join(f"{b['id']} {b['role']}: {b['narration']}" for b in script["beats"])
    W_ = run.need("words.json")["words"]
    shots = "\n".join(f"- shot {i + 1} @ word {s['start_word']} ({W_[min(s['start_word'], len(W_) - 1)]['start']:.1f} s): "
                      f"{s['frame']} on {', '.join(s.get('on') or []) or 'the whole machine'}, {s.get('move')}"
                      for i, s in enumerate(sb.get("shots", [])))
    parts = ", ".join(f"{p['id']} ({p['type']}, {'mounted ' + p['mount'] if p.get('mount') else 'prop ' + str(p.get('stage'))})"
                      for p in sb.get("parts", []))
    out = llm.ask(
        "You are the demanding creative director of a premium 3D explainer channel. You score honestly against "
        "the bar: 4 = good enough to publish on a quality channel, 5 = as good as the best of the genre.",
        f"""Numbered stills of a vertical machine explainer, with the captions, label pills and the corner loop
map drawn on as the viewer will see them. (Previews are low quality: judge content and composition, not noise.)
Stills: {json.dumps(captions)}
Narration:
{story}
Machine: {sb.get('machine', {}).get('host')}. Parts: {parts}
Shots:
{shots}
{extra}

Score each item 1-5 with a one-line reason. Check each item against what a 4 needs; give 4 when every check
holds, 5 when it is as good as the best of the genre, 3 or less only for a check that fails (say which):
""" + "\n".join(f"- {k}: {v}. A 4 needs: {FOUR[k]}." for k, v in RUBRIC.items()) + """

For every still say ok or the problem. Then list the fixes that would bring every item to 4 or more: concrete
storyboard changes naming the shot, word index, part, slot or event (e.g. "shot 7: frame part on compressor
instead of area", "move the thermostat to inside_middle", "hold shot 3 until word 52"). fix_stage = script only
when the narration itself must change (hook, story order, a wrong claim).""",
        SCHEMA, effort="high", label="buildit_review",
        images=[(f"numbered stills with overlays, sheet {i + 1}", p)
                for i, p in enumerate(sheet_path if isinstance(sheet_path, list) else [sheet_path])])
    return out


def _safe(fn, *args):
    """One reviewer's answer, or None when it failed (a malformed structured answer must not stop the panel)."""
    try:
        return fn(*args)
    except llm.UsageLimit:
        raise
    except Exception as exc:                              # noqa: BLE001
        log.warning("[review] a reviewer failed: %s", str(exc)[:200])
        return None


def panel(run, sheet_path, captions: list[str], extra: str = "", n: int = PANEL) -> dict:
    """n independent reviews of the same stills, merged: the MEDIAN score per item (with the reason of a reviewer
    who gave it), every fix and still problem any of them raised, the majority fix_stage. One review of the same
    video swings by a point per item; a gate that needs all items at 4 at once must not hang on one draw."""
    from concurrent.futures import ThreadPoolExecutor
    llm.active_backend()            # settle the backend (and any remembered usage limit) before the threads start
    with ThreadPoolExecutor(n) as ex:
        vs = list(ex.map(lambda _i: _safe(judge, run, sheet_path, captions, extra), range(n)))
    # a review that came back without a usable answer is asked again once; the panel goes on with what it has
    vs = [v if isinstance(v, dict) and v.get("scores") else _safe(judge, run, sheet_path, captions, extra) for v in vs]
    vs = [v for v in vs if isinstance(v, dict) and v.get("scores")]
    for v in vs:                                   # an item a reviewer left null is simply not counted
        v["scores"] = {k: x for k, x in v["scores"].items() if isinstance(x, dict) and isinstance(x.get("score"), int)}
    vs = [v for v in vs if v["scores"]]
    if not vs:
        raise RuntimeError("no reviewer returned a usable review")
    out = {"scores": {}, "fixes": [], "stills": [], "engine_gaps": [], "panel": [
        {k: s["score"] for k, s in v["scores"].items()} for v in vs]}
    for k in RUBRIC:
        got = sorted((v["scores"][k]["score"], i) for i, v in enumerate(vs) if k in v["scores"])
        if not got:                                # nobody scored it: it has not passed
            out["scores"][k] = {"score": 1, "why": "no reviewer scored this item"}
            continue
        sc, i = got[len(got) // 2]
        out["scores"][k] = {"score": sc, "why": vs[i]["scores"][k]["why"]}
    for v in vs:
        out["fixes"] += [f for f in v.get("fixes", []) if f not in out["fixes"]]
        out["engine_gaps"] += [g for g in v.get("engine_gaps", []) if g not in out["engine_gaps"]]
        out["stills"] += [st for st in v.get("stills", []) if not st.get("ok")]
    stages = [v.get("fix_stage") for v in vs]
    out["fix_stage"] = max(set(stages), key=stages.count)
    return out


def low_items(scores: dict) -> dict:
    return {k: v["score"] for k, v in scores.items() if v["score"] < PASS}


# ------------------------------------------------------------ lessons: what reviewers rejected, carried forward

def _lessons_path(run) -> str:
    import os
    return os.path.join(os.path.dirname(os.path.dirname(run.path("brief.json"))), "lessons.json")


def record_lessons(run, v: dict, where: str):
    """Every item a review scored below PASS, with its reason, into the shared lessons file (newest last), so the
    planners of the next script / storyboard avoid what was already rejected."""
    import os
    from datetime import datetime
    path = _lessons_path(run)
    data = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else []
    topic = run.need("brief.json").get("topic", "")
    for k, s in v.get("scores", {}).items():
        if k in RUBRIC and s.get("score", 5) < PASS and s.get("why"):
            data.append({"item": k, "why": s["why"], "where": where, "topic": topic,
                         "date": datetime.now().isoformat(timespec="seconds")})
    json.dump(data[-120:], open(path, "w", encoding="utf-8"), indent=1)


def lessons_text(run, items=None, n: int = 16) -> str:
    """The most recent distinct reviewer complaints (optionally for some rubric items), as planner guidance."""
    import os
    path = _lessons_path(run)
    if not os.path.exists(path):
        return ""
    seen, out = set(), []
    for L in reversed(json.load(open(path, encoding="utf-8"))):
        if items and L["item"] not in items:
            continue
        key = L["why"][:80]
        if key in seen:
            continue
        seen.add(key)
        out.append(f"- [{L['item']}] {L['why']}")
        if len(out) >= n:
            break
    return ("Reviewers rejected earlier films for these reasons -- do not repeat them:\n" + "\n".join(out)) if out else ""


# ------------------------------------------------------------ the script, reviewed before a word is voiced

SCRIPT_ITEMS = ["hook", "story", "pacing", "accuracy"]
SCRIPT_SCHEMA = {"type": "object", "properties": {
    "scores": {"type": "object", "properties": {k: {"type": "object", "properties": {
        "score": {"type": "integer", "minimum": 1, "maximum": 5}, "why": {"type": "string"}},
        "required": ["score", "why"]} for k in SCRIPT_ITEMS}, "required": SCRIPT_ITEMS},
    "fixes": {"type": "array", "items": {"type": "string"}, "description": "concrete changes naming the beat"},
}, "required": ["scores", "fixes"]}


def judge_script(run, script: dict, n: int = PANEL) -> dict:
    """The narration (with each beat's planned visual) scored on the rubric items a text can be judged on, by a
    panel of n independent reviews, median per item -- so a weak hook, a loose claim, a detour or a rushed end
    is fixed before voice, storyboard and render are spent on it."""
    from concurrent.futures import ThreadPoolExecutor
    from .kit import vocab
    b, facts = run.need("brief.json"), run.need("facts.json")
    words = sum(len(x["narration"].split()) for x in script["beats"])
    beats = "\n".join(f"{x['id']} {x['role']}: {x['narration']}" for x in script["beats"])
    fl = "\n".join(f"- {f['id']}: {f['claim']} ({f['value']} {f['unit']})" for f in facts["facts"])
    prompt = f"""A vertical (9:16) machine explainer for a premium 3D channel, {b['target_seconds']} s target, about
{words / 2.4:.0f} s of narration ({words} words). It is filmed in a 3D kit: the machine ({b.get('host')}) as a cutaway,
parts that fly in and click into place, coloured flow dashes in pipes, heat waves, frost, glow, labels, and
everyday props ({', '.join(vocab.PROPS)}) for analogies. Nothing else can be shown.

Narration (beat id, role, words; the pictures are planned and reviewed later, so judge the words):
{beats}

Verified facts:
{fl}

Score each item 1-5 with a one-line reason (4 = good enough to publish on a quality channel, 5 = best of genre):
""" + "\n".join(f"- {k}: {RUBRIC[k]}" for k in SCRIPT_ITEMS) + """
Judge pacing from the words: analogy beats that drag, two ideas crammed into one beat, an ending that rushes.
DEPTH IS WANTED: explaining WHY each step works is the film's value, never "density" to cut; the film runs 65-75 s. Judge accuracy strictly: every claim physically right, analogies
simplified but not wrong, nothing that needs a missing condition to be true (e.g. boiling point without pressure).
Then list concrete fixes naming the beat."""
    llm.active_backend()
    with ThreadPoolExecutor(n) as ex:
        vs = list(ex.map(lambda _i: llm.ask(
            "You are the demanding story editor of a premium 3D explainer channel; you score honestly.",
            prompt, SCRIPT_SCHEMA, effort="high", label="buildit_script_review"), range(n)))
    vs = [v for v in vs if isinstance(v, dict) and v.get("scores")]
    for v in vs:
        v["scores"] = {k: x for k, x in v["scores"].items() if isinstance(x, dict) and isinstance(x.get("score"), int)}
    vs = [v for v in vs if v["scores"]]
    if not vs:
        raise RuntimeError("no script review came back")
    out = {"scores": {}, "fixes": []}
    for k in SCRIPT_ITEMS:
        got = sorted((v["scores"][k]["score"], i) for i, v in enumerate(vs) if k in v["scores"])
        if not got:
            out["scores"][k] = {"score": 1, "why": "no reviewer scored this item"}
            continue
        sc, i = got[len(got) // 2]
        out["scores"][k] = {"score": sc, "why": vs[i]["scores"][k]["why"]}
    for v in vs:
        out["fixes"] += [f for f in v.get("fixes", []) if f not in out["fixes"]]
    return out
