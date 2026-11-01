"""
Stage 7 - preview/: cheap EEVEE stills (about 0.7 s each) at the hook, every shot's midpoint and every label,
laid out on a contact sheet next to reference frames and judged by a vision check (is each beat's subject in frame,
readable, recognisable, nothing intersecting or empty?). Problems go back to the storyboard (up to 2 revisions)
before a single frame of the final render is spent: no full draft render is needed.
"""
from __future__ import annotations

import json
import logging
import os

from PIL import Image, ImageDraw, ImageFont

from agents import llm

from .. import blender_run
from ..runner import StageError
from . import storyboard

log = logging.getLogger("pipeline")
MAX_REVISIONS = 2
SCHEMA = {"type": "object", "properties": {
    "stills": {"type": "array", "items": {"type": "object", "properties": {
        "n": {"type": "integer"}, "ok": {"type": "boolean"}, "problem": {"type": "string"}},
        "required": ["n", "ok", "problem"]}},
    "pass": {"type": "boolean"}, "notes": {"type": "string", "description": "fixes for the storyboard, concrete"}},
    "required": ["stills", "pass", "notes"]}


def inputs(run):
    return [run.path("storyboard.json"), blender_run.code_hash()]


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
        out.append(((t0 + t1) / 2, f"shot {k + 1}: {s['frame']} on {', '.join(s['on'])}"))
    for lb in sb.get("labels", []):
        out.append((t(lb["word"]) + 0.4, f"label {lb['text']} on {lb['anchor']}"))
    out.sort()
    merged = []
    for tm, what in out:
        if merged and tm - merged[-1][0] < 0.5:
            merged[-1] = (merged[-1][0], merged[-1][1] + "; " + what)
        else:
            merged.append((tm, what))
    return merged


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


def _render_and_judge(run, attempt: int) -> dict:
    ms = moments(run)
    frames = [int(round(tm * 30)) + 1 for tm, _ in ms]
    out = run.path("preview", f"r{attempt}")
    done = blender_run.render(blender_run.job_for(run, out, "preview", stills=frames))
    paths = [os.path.join(out, f"f_{f:04d}.png") for f in frames]
    caps = [f"{n + 1}. {tm:.1f}s {what}" for n, (tm, what) in enumerate(ms)]
    sheet_path = run.path("preview", f"sheet_{attempt}.jpg")
    sheet(paths, caps, sheet_path, [])
    script = run.need("script.json")
    story = "\n".join(f"{b['id']} {b['role']}: {b['narration']}" for b in script["beats"])
    verdict = llm.ask(
        "You are a demanding 3D motion-design director checking storyboard previews.",
        f"""Contact sheet: numbered preview stills of a vertical machine explainer (low quality preview: judge
composition and content, not noise). The look: a bright studio, the real machine (cut away / see-through) with
the story's parts mounted on it, pipes along it glowing with coloured moving dashes where something flows.
Stills: {json.dumps(caps)}
Narration: {story}

Captions and label pills are NOT in these stills (they are added later as overlays): never judge labels or text.
For each numbered still: is what the caption says on screen clearly visible, big enough, framed (not cut off),
recognisable for what it is meant to be, and not intersecting or floating oddly? Is anything important empty or
off-frame? Then: pass = true only if the video would read clearly. notes = concrete storyboard fixes (which
part, placement, size, shot framing or event to change).""", SCHEMA, effort="medium", images=[("contact sheet: numbered preview stills", sheet_path)],
        label="buildit_preview")
    verdict.update({"sheet": sheet_path, "s_per_still": done.get("s_per_frame"), "stills_n": len(frames)})
    return verdict


def run(run):
    reports = []
    for attempt in range(MAX_REVISIONS + 1):
        v = _render_and_judge(run, attempt)
        reports.append(v)
        bad = [s for s in v["stills"] if not s["ok"]]
        log.info("[preview] round %d: %s, %d/%d stills with problems", attempt, "pass" if v["pass"] else "fail",
                 len(bad), len(v["stills"]))
        if v["pass"] or attempt == MAX_REVISIONS:
            break
        notes = v["notes"] + "\n" + "\n".join(f"- still {s['n']}: {s['problem']}" for s in bad)
        sb = storyboard.revise(run, notes)
        if sb["errors"]:
            log.warning("[preview] revision did not pass the checks; keeping the last valid storyboard")
            break
    run.save("preview/report.json", {"rounds": reports})


def validate(run):
    r = run.need("preview/report.json")
    last = r["rounds"][-1]
    if not os.path.exists(last["sheet"]):
        raise StageError("preview sheet missing")
    if not last["pass"]:
        log.warning("[preview] still has problems after %d revisions: %s", MAX_REVISIONS, last["notes"][:300])
