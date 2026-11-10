"""
Stage 11 - qa/: the gates that block a release.
  hyperframes lint + check (zero errors), the HyperFrames render of the candidate, ffprobe (1080x1920, duration,
  audio), blackdetect / freezedetect, loudness, every label number backed by a fact, and the rubric: frames of
  the finished video scored with the same rubric as the pre-render review (buildit/review.py; audio is measured).
  Every item must reach 4, or the video is not packaged.
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess

from config.paths import get_ffmpeg
from cutaway import hf
from cutaway.stages.qa import _detect, _ffprobe
from cutaway.stages.sound import measure

from .. import review as review_mod
from ..runner import StageError
from .preview import sheet

log = logging.getLogger("pipeline")
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


def review(run, loudness: dict | None = None) -> dict:
    """Frames of the finished video (shot middles and beat middles), scored like the pre-render review."""
    from . import sound as sound_stage
    video = candidate(run)
    paths, caps = beat_frames(run, video)
    sh = run.path("qa", "contact_sheet.jpg")
    sheet(paths, caps, sh, [])
    big = review_mod.sheets(paths, caps, run.path("qa", "review"))
    v = review_mod.panel(run, big, caps, extra="These are frames of the FINISHED video: the overlays are real.\n" +
                         review_mod.engine_notes(run.need("storyboard.json")))
    v["scores"]["audio"] = review_mod.audio_score(sound_stage.cues(run), run.need("words.json")["duration"], loudness)
    return {"sheet": sh, **v}


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
    out["rubric"] = review(run, out["loudness"])
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
    low = review_mod.low_items(q["rubric"]["scores"])
    if low and run.quality == "final":
        problems.append(f"rubric below {review_mod.PASS}: {low} (fixes: {q['rubric']['fixes'][:4]})")
    if problems:
        raise StageError("QA gates failed:\n- " + "\n- ".join(problems))
