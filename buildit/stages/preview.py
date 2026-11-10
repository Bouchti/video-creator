"""
Stage 7 - preview/: the quality gate BEFORE the render. Cheap EEVEE stills (about 0.5 s each) at the hook, every
shot (as it starts and at its middle) and every label, with the captions, label pills and loop map drawn on as the
viewer will see them. First the layout is MEASURED from the posed geometry (review.layout_faults: the subject cut
by the frame, too small, under the caption or the loop strip, a prop sliced by the edge, a pill on a part); then
the stills are scored with the same rubric as the final QA (buildit/review.py; audio is measured from the planned
sound cues), the reviewer briefed on how the engine draws things and what the storyboard can change
(review.engine_notes), so its fixes are ones the storyboard can carry out. Any item below 4 sends the fixes back:
the reviewed storyboard is EDITED with them (storyboard.revise), or, when the narration itself must change, the
script, voice and storyboard are redone (at most twice). Wishes the kit cannot show are logged as engine gaps.
Up to MAX_ROUNDS reviews; a storyboard that never reaches 4 everywhere stops the run here, before a single frame
of the final render is spent.
"""
from __future__ import annotations

import logging
import os

from PIL import Image, ImageDraw, ImageFont

from .. import blender_run, compose, review
from ..runner import StageError
from . import storyboard

log = logging.getLogger("pipeline")
MAX_ROUNDS = 3


def inputs(run):
    return [run.path("storyboard.json"), blender_run.code_hash(), review.RUBRIC, review.PASS]


def moments(run) -> list[tuple[float, str]]:
    sb, words = run.need("storyboard.json"), run.need("words.json")
    W = words["words"]

    def t(i):
        return W[max(0, min(int(i), len(W) - 1))]["start"]
    shots = sb["shots"]
    out = [(0.6, "hook"), (min(2.0, words["duration"] / 2), "hook payoff")]
    for k, s in enumerate(shots):
        t0 = t(s["start_word"])
        t1 = t(shots[k + 1]["start_word"]) if k + 1 < len(shots) else words["duration"]
        what = f"shot {k + 1}: {s['frame']} on {', '.join(s['on']) or 'machine'}"
        out.append((min(t0 + 1.4, (t0 + t1) / 2), what + " (start)"))     # after the camera's glide
        out.append(((t0 + t1) / 2 + 0.6, what))
    for lb, t0, _t1 in compose.label_times(sb, W):
        out.append((t0 + 0.5, f"label {lb['text']}"))
    # never a still of a part in mid-flight (it reads as floating): the moment just after it clicks in instead
    flights = []
    for e in sb.get("events", []):
        if e.get("do") == "appear" and e.get("target") != "machine":
            land = t(e["word"]) + 0.2
            flights.append((land - (1.0 if e.get("from") else 0.85) - 0.05, land + 0.15, land + 0.35))
    out = [(next((after for a, b, after in flights if a <= tm <= b), tm), what) for tm, what in out]
    out.sort()
    merged = []
    for tm, what in out:
        if merged and tm - merged[-1][0] < 0.6:
            merged[-1] = (merged[-1][0], merged[-1][1] + "; " + what)
        else:
            merged.append((tm, what))
    return merged


def motion(sb: dict, W: list[dict], t: float) -> list[str]:
    """What is MOVING at time t, from the event timeline (a still cannot show motion; the reviewer must know)."""
    def tw(i):
        return W[max(0, min(int(i), len(W) - 1))]["start"]
    from ..kit import layout
    span = layout.spans(sb, W, W[-1]["end"] + 1.0)
    shown = {q for q, (a, b) in span.items() if a <= t <= b} | {c["id"] for c in sb.get("connections", [])}
    evs = sorted((e for e in sb.get("events", []) if str(e.get("target", "")).split(".")[0] in shown | {"machine"}),
                 key=lambda e: e["word"])
    out, last = [], {}
    for e in evs:
        if tw(e["word"]) <= t:
            last[(e["do"], str(e.get("target")), str(e.get("to")))] = e
    for (do, target, to), e in last.items():
        dt = t - tw(e["word"])
        on = e.get("on") is not False and e.get("speed") != "stop"
        if do == "run" and on:
            out.append(f"{target} runs ({e.get('driver') or 'moving'})")
        elif do == "flow" and on:
            out.append(f"{e.get('kind')} dashes stream through {target}")
        elif do == "heat_flow" and on and dt < 6.0:
            out.append(f"warm heat waves drift {target} -> {to}")
        elif do in ("frost", "heat") and dt < 1.5:
            out.append(f"{target} {'frosting over' if do == 'frost' else 'warming up'}")
        elif do == "appear" and dt < 1.0:
            out.append(f"{target} arriving")
        elif do == "highlight" and on and dt < 2.6:
            out.append(f"{target} glowing (highlighted)")
    shot = _shot_at(sb, W, t)
    if shot.get("move") and shot["move"] != "hold":
        out.append(f"camera {shot['move'].replace('_', ' ')}")
    shots = sorted(sb["shots"], key=lambda x: x["start_word"])
    last = next((x for x in reversed(shots) if x.get("frame") == "machine"), None)
    if last is shot and len(shots) > 2:              # the finale (build_scene._finale_comet)
        from ..kit.check import loop_order
        order = loop_order(sb, {p["id"]: p for p in sb["parts"]})
        if order:
            out.append("FINALE: a bright comet runs the whole loop in flow order (" + " -> ".join(order) +
                       " -> back), one lap every ~4 s; each part glows and the loop strip lights each stage in turn")
    return out


def sheet(paths: list[str], captions: list[str], out: str, refs: list[str]):
    w, h = 270, 480
    cols = 6
    items = [(p, c) for p, c in zip(paths, captions)] + [(r, "REFERENCE " + os.path.basename(r)) for r in refs]
    rows = (len(items) + cols - 1) // cols
    img = Image.new("RGB", (cols * w, rows * (h + 34)), (20, 20, 22))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 15)
    except OSError:
        font = ImageFont.load_default()
    for k, (p, c) in enumerate(items):
        im = Image.open(p).convert("RGB").resize((w, h))
        x, y = (k % cols) * w, (k // cols) * (h + 34)
        img.paste(im, (x, y))
        d.text((x + 4, y + h + 4), c[:42], fill=(240, 240, 240), font=font)
    img.save(out, quality=88)


def _labels(run) -> list[dict]:
    sb, W = run.need("storyboard.json"), run.need("words.json")["words"]
    out = []
    for lb, t0, t1 in compose.label_times(sb, W):
        out.append({"text": lb["text"], "anchor": lb["anchor"] if "." in lb["anchor"] else lb["anchor"] + ".center",
                    "t0": t0, "t1": t1})
    return out


def _shot_at(sb: dict, W: list[dict], t: float) -> dict:
    shots = sorted(sb["shots"], key=lambda s: s["start_word"])
    cur = shots[0]
    for s in shots:
        if W[min(s["start_word"], len(W) - 1)]["start"] - 0.12 <= t:
            cur = s
    return cur


def measure(run, attempt) -> dict:
    """Render the stills, draw what the viewer will see on them and MEASURE the layout of each (the subject cut
    by the frame, too small, under the caption or the strip; a part sliced by the edge; a pill on a part)."""
    import json
    words = run.need("words.json")
    sb = run.need("storyboard.json")
    ms = moments(run)
    frames = [int(round(tm * 30)) + 1 for tm, _ in ms]
    out = run.path("preview", f"r{attempt}")
    done = blender_run.render(blender_run.job_for(run, out, "preview", stills=frames))
    data = json.load(open(os.path.join(out, "anchors.json"), encoding="utf-8"))
    anchors, boxes = data["frames"], data.get("boxes", {})
    loop = compose.loop_info(sb, words["words"], words["duration"])
    labels = _labels(run)
    paths, faults = [], []
    for n, ((tm, _), f) in enumerate(zip(ms, frames)):
        src = os.path.join(out, f"f_{f:04d}.png")
        dst = os.path.join(out, f"o_{f:04d}.jpg")
        bx = boxes.get(str(f), {})
        pills = review.overlay(src, dst, tm, words["words"], labels, anchors.get(str(f)), loop, bx)
        paths.append(dst)
        props = {p["id"] for p in sb["parts"] if not p.get("mount")}
        for x in review.layout_faults(tm, _shot_at(sb, words["words"], tm), bx, words["words"], loop, pills, props):
            faults.append(f"still {n + 1} ({tm:.1f} s): {x}")
    caps = [f"{n + 1}. {tm:.1f}s {what}" for n, (tm, what) in enumerate(ms)]
    return {"paths": paths, "caps": caps, "faults": faults, "s_per_still": done.get("s_per_frame"),
            "times": [tm for tm, _ in ms]}


def _review_round(run, attempt: int) -> dict:
    from . import sound as sound_stage
    words = run.need("words.json")
    m = measure(run, attempt)
    if m["faults"]:
        log.warning("[preview] measured layout faults (%d):\n  %s", len(m["faults"]), "\n  ".join(m["faults"]))
    sheet_path = run.path("preview", f"sheet_{attempt}.jpg")
    sheet(m["paths"], m["caps"], sheet_path, [])              # the overview, for people
    big = review.sheets(m["paths"], m["caps"], run.path("preview", f"review_{attempt}"))
    audio = review.audio_score(sound_stage.cues(run), words["duration"])
    sb = run.need("storyboard.json")
    moving = "\n".join(f"{n + 1}: " + ("; ".join(motion(sb, words["words"], tm)) or "nothing moves")
                       for n, tm in enumerate(m["times"]))
    v = review.panel(run, big, m["caps"], review.engine_notes(sb, m["faults"]) +
                     "\n\nThe narration's claims were already scored for accuracy (the same bar) by the story "
                     "editor's panel: judge accuracy here on what the PICTURES show and label -- flow colours, pills, "
                     "numbers on screen, parts and their places -- and whether they match the narration."
                     "\n\nWhat is MOVING in each still (from the animation timeline; a still cannot show motion, "
                     "so judge animation and pacing with this):\n" + moving)
    v["scores"]["audio"] = audio
    v.update({"sheet": sheet_path, "s_per_still": m["s_per_still"], "stills_n": len(m["paths"]),
              "measured": m["faults"]})
    return v


def _notes(v: dict) -> str:
    low = review.low_items(v["scores"])
    lines = [f"- {k} scored {s}/5: {v['scores'][k]['why']}" for k, s in low.items()]
    lines += [f"- fix: {f}" for f in v["fixes"]]
    lines += [f"- still {s['n']}: {s['problem']}" for s in v["stills"] if not s["ok"]]
    lines += [f"- measured: {f}" for f in v.get("measured", [])]
    return "Every rubric item must reach 4. The reviewer found:\n" + "\n".join(lines)


def _redo_story(run, notes: str):
    """The narration itself must change: script again with the notes, then voice, word timing, storyboard."""
    from . import align, script, voice
    log.info("[preview] the story needs work: rewriting the script, voice and storyboard")
    script.run(run, notes)
    script.validate(run)
    voice.run(run)
    voice.validate(run)
    align.run(run)
    run.save("storyboard.json", storyboard.plan(run, notes))   # a fresh storyboard for the new words, with the notes
    storyboard.validate(run)


def _rank(v: dict) -> tuple:
    """How good a reviewed version is: its weakest item first, then the total."""
    sc = [s["score"] for s in v["scores"].values()]
    return (min(sc), sum(sc))


def run(run):
    """Review, fix, review again. The best version so far is kept: an edit that makes things worse is thrown
    away and the best one is revised again (a model's edit is not always an improvement)."""
    import copy
    rounds, story_redone = [], 0
    best = None                                   # (rank, round index, storyboard) for the current script
    for attempt in range(MAX_ROUNDS):
        v = _review_round(run, attempt)
        rounds.append(v)
        low = review.low_items(v["scores"])
        log.info("[preview] review %d: %s", attempt + 1,
                 {k: s["score"] for k, s in v["scores"].items()} | ({"PASS": True} if not low else {}))
        review.record_lessons(run, v, "preview")
        if best is None or _rank(v) > best[0]:
            best = (_rank(v), attempt, copy.deepcopy(run.need("storyboard.json")))
        v["best"] = best[1]
        run.save("preview/report.json", {"rounds": rounds, "best": best[1]})
        if not low or attempt == MAX_ROUNDS - 1:
            break
        if v.get("engine_gaps"):
            log.warning("[preview] the reviewer wants what the kit cannot show yet: %s", "; ".join(v["engine_gaps"]))
        if best[1] != attempt:                    # this edit made it worse: back to the best version and its notes
            log.info("[preview] review %d is worse than review %d: revising the better storyboard again",
                     attempt + 1, best[1] + 1)
            run.save("storyboard.json", copy.deepcopy(best[2]))
            v = rounds[best[1]]
            low = review.low_items(v["scores"])
        notes = _notes(v)
        # the narration itself is the problem (a wrong or loose claim, a weak hook): rewrite it, at most twice
        # the narration was already passed by the story editor's panel: it is rewritten only when the reviewers say
        # the words themselves must change; a wrong picture (a dash colour, a pill) is the storyboard's to fix
        if story_redone < 2 and v.get("fix_stage") == "script" and set(low) & {"hook", "story", "accuracy"}:
            story_redone += 1
            _redo_story(run, notes)
            best = None                           # new words: storyboards of the old script no longer apply
        else:
            sb = storyboard.revise(run, notes)
            if sb["errors"]:
                log.warning("[preview] the revision broke the storyboard rules; reviewing the last valid one again")
    if best is not None and best[1] != len(rounds) - 1:
        run.save("storyboard.json", copy.deepcopy(best[2]))      # leave the best version, not the last edit
    run.save("preview/report.json", {"rounds": rounds, "best": best[1] if best else len(rounds) - 1})


def validate(run):
    r = run.need("preview/report.json")
    last = r["rounds"][r.get("best", len(r["rounds"]) - 1)]
    if not os.path.exists(last["sheet"]):
        raise StageError("preview sheet missing")
    low = review.low_items(last["scores"])
    if low:
        raise StageError(f"not good enough to render after {len(r['rounds'])} reviews (best: review "
                         f"{r.get('best', len(r['rounds']) - 1) + 1}): {low}\n" +
                         "\n".join(f"- {f}" for f in last["fixes"][:8]) + f"\n(sheet: {last['sheet']})")
