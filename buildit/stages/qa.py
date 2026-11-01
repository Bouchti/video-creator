"""
Stage 11 - qa/: the gates that block a release.
  hyperframes lint + check (zero errors), the HyperFrames render of the candidate, ffprobe (1080x1920, duration,
  audio), blackdetect / freezedetect, loudness, every label number backed by a fact, and the rubric: a contact
  sheet at each beat's midpoint next to reference frames, scored by a vision model (every item >= 4 for final).
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess

from agents import llm
from config.paths import get_ffmpeg
from cutaway import hf
from cutaway.stages.qa import _detect, _ffprobe
from cutaway.stages.sound import measure

from ..runner import StageError
from .preview import sheet

log = logging.getLogger("pipeline")
RUBRIC = {
    "hook": "An everyday object does something surprising in the first 2 s",
    "story": "Each part arrives as the answer to a problem; a 12-year-old can follow the whole chain and SEE how the parts connect and what flows between them",
    "look": "Premium and bright: a clean studio, the real machine recognisable at a glance, parts clearly mounted on it",
    "animation": "Parts assemble with weight and overshoot; mechanisms run; the invisible (flows, heat) is shown",
    "captions_labels": "Word-synced captions and pills are readable and never cover the action",
    "audio": "Clear voice, ducked music, SFX on events, -14 LUFS (judge from the plan if you cannot hear it)",
    "pacing": "Calm and clear: every step has time to land before the next, the camera glides instead of flashing between views, no dead air",
    "accuracy": "Every claim sourced; analogies simplified but correct",
}
SCHEMA = {"type": "object", "properties": {
    "scores": {"type": "object", "properties": {k: {"type": "object", "properties": {
        "score": {"type": "integer", "minimum": 1, "maximum": 5}, "why": {"type": "string"}},
        "required": ["score", "why"]} for k in RUBRIC}, "required": list(RUBRIC)},
    "weakest": {"type": "string"}, "fixes": {"type": "array", "items": {"type": "string"}}},
    "required": ["scores", "weakest", "fixes"]}


def inputs(run):
    return [run.path("hf"), run.path("audio", "mix.wav"), run.quality]


def candidate(run) -> str:
    return run.path("release", f"candidate_{run.quality}.mp4")


def facts_check(run) -> list[str]:
    facts = {f["id"] for f in run.need("facts.json")["facts"]}
    return [f"label '{lb['text']}' shows a number without a valid fact" for lb in run.need("storyboard.json").get("labels", [])
            if re.search(r"\d", lb["text"]) and lb.get("fact_id") not in facts]


def beat_frames(run, video: str) -> tuple[list[str], list[str]]:
    words, script = run.need("words.json"), run.need("script.json")
    d = run.path("qa", "frames")
    os.makedirs(d, exist_ok=True)
    paths, caps = [], []
    for b, sb in zip(words["beats"], script["beats"]):
        tm = (b["start"] + b["end"]) / 2
        p = os.path.join(d, f"{b['id']}.png")
        subprocess.run([get_ffmpeg(), "-v", "error", "-y", "-ss", f"{tm:.2f}", "-i", video, "-frames:v", "1", p],
                       check=True)
        paths.append(p)
        caps.append(f"{b['id']} {tm:.1f}s {sb['role']}")
    return paths, caps


def rubric(run, sheet_path: str) -> dict:
    script = run.need("script.json")
    story = "\n".join(f"{b['id']} {b['role']}: {b['narration']}" for b in script["beats"])
    return llm.ask("You are a demanding creative director for a premium 3D explainer channel.",
                   f"""Contact sheet: one frame per beat of a vertical explainer. Narration:
{story}

Score 1-5 with a one-line reason each (5 = as good as the best of the genre):
""" + "\n".join(f"- {k}: {v}" for k, v in RUBRIC.items()), SCHEMA, effort="medium", images=[("contact sheet: one frame per beat", sheet_path)],
                   label="buildit_rubric")


def review(run) -> dict:
    video = candidate(run)
    paths, caps = beat_frames(run, video)
    sh = run.path("qa", "contact_sheet.jpg")
    sheet(paths, caps, sh, [])
    return {"sheet": sh, **rubric(run, sh)}


def run(run):
    d = run.path("hf")
    out = {}
    chk = hf.run_json(["check"], cwd=d, timeout=1200)
    errs = sum(int(sec.get("errorCount", 0)) for sec in chk.values() if isinstance(sec, dict))
    out["check_errors"] = errs
    video = candidate(run)
    os.makedirs(os.path.dirname(video), exist_ok=True)
    hf.run(["render", "-o", video, "--quality", "looks", "--keyframe-interval", "1"], cwd=d, timeout=3600)
    probe = _ffprobe(video)
    vs = next(s for s in probe["streams"] if s["codec_type"] == "video")
    out["probe"] = {"duration": float(probe["format"]["duration"]), "width": vs["width"], "height": vs["height"],
                    "audio": any(s["codec_type"] == "audio" for s in probe["streams"])}
    out["detect"] = _detect(video)
    out["loudness"] = measure(video)
    out["facts"] = facts_check(run)
    out["rubric"] = review(run)
    run.save("qa/qa.json", out)
    log.info("[qa] %s", {k: v for k, v in out.items() if k != "rubric"})
    log.info("[qa] rubric: %s", {k: v["score"] for k, v in out["rubric"]["scores"].items()})


def validate(run):
    q = run.need("qa/qa.json")
    dur = run.need("words.json")["duration"]
    problems = []
    if q["check_errors"]:
        problems.append(f"hyperframes check: {q['check_errors']} errors")
    p = q["probe"]
    if (p["width"], p["height"]) != (1080, 1920) or not p["audio"] or abs(p["duration"] - dur) > 0.5:
        problems.append(f"bad output: {p}")
    if q["detect"]["black"]:
        problems.append(f"black frames at {q['detect']['black']}")
    long_freeze = [f for f in q["detect"]["freeze"] if f[1] is None or f[1] - f[0] > 0.8]
    if long_freeze:
        problems.append(f"frozen picture at {long_freeze}")
    if abs(q["loudness"]["I"] + 14) > 1.0 or q["loudness"]["TP"] > -0.5:
        problems.append(f"loudness {q['loudness']}")
    problems += q["facts"]
    low = {k: v["score"] for k, v in q["rubric"]["scores"].items() if v["score"] < 4}
    if low and run.quality == "final":
        log.warning("[qa] rubric below 4: %s (fixes: %s)", low, q["rubric"]["fixes"][:3])
    if problems:
        raise StageError("QA gates failed:\n- " + "\n- ".join(problems))
