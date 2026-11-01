"""
Stage 10 - QA gates, then the release-candidate render.

Gates (any failure blocks the release):
  hyperframes lint and check --json with zero errors
  snapshot contact sheet at every beat midpoint, scored against the rubric (vision review; < 4 blocks --final)
  the HyperFrames render, then ffprobe (duration matches, 1080x1920, audio present)
  ffmpeg blackdetect / freezedetect: no black or frozen stretch over 0.3 s
  loudness (ebur128) of the rendered file
  facts: every stat and every number in a callout has a fact_id that exists in facts.json
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess

from agents import llm
from config.paths import get_ffmpeg, get_ffprobe

from .. import hf
from ..runner import StageError
from .sound import TARGET_I, TARGET_TP, measure

log = logging.getLogger("pipeline")

RUBRIC = {
    "hook": "Stops the scroll in 1.5 s with motion plus a question or number",
    "realism": "Materials, lighting and parts read as real engineering, not CG primitives",
    "clarity": "A 12-year-old can follow cause and effect for each step, and the whole machine is explained "
               "from start to finish with what happens inside actually shown (gas, flame, flow), not just named",
    "camera": "Purposeful moves; one dive into the mechanism beats ten orbits; shots look different from each "
              "other (never the same view over and over)",
    "motion_design": "Titles, callouts and captions are timed to words and never cover the action",
    "audio": "Voice is clear and natural (not robotic), music sits well under it, SFX land on events, -14 LUFS",
    "pacing": "A visual change at least every 1.5 s, with no dead air",
    "accuracy": "Every number is sourced",
    "loop": "The last frame flows back into the first",
}
SCHEMA = {"type": "object", "properties": {
    "scores": {"type": "object", "properties": {k: {"type": "object", "properties": {
        "score": {"type": "integer", "minimum": 1, "maximum": 5}, "why": {"type": "string"}},
        "required": ["score", "why"]} for k in RUBRIC}, "required": list(RUBRIC)},
    "weakest": {"type": "string"}, "fixes": {"type": "array", "items": {"type": "string"}}},
    "required": ["scores", "weakest", "fixes"]}


def inputs(run):
    q = run.quality
    return [run.path("hf"), run.path("audio", "mix.wav"), q]


def _ffprobe(path: str) -> dict:
    out = subprocess.run([get_ffprobe(), "-v", "error", "-show_entries",
                          "format=duration:stream=codec_type,width,height,r_frame_rate", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def _detect(path: str) -> dict:
    out = subprocess.run([get_ffmpeg(), "-hide_banner", "-nostats", "-i", path, "-vf",
                          "blackdetect=d=0.3:pix_th=0.06,freezedetect=n=0.002:d=0.3", "-an", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    black = [tuple(map(float, m)) for m in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", out)]
    starts = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", out)]
    ends = [float(x) for x in re.findall(r"freeze_end: ([\d.]+)", out)]
    return {"black": black, "freeze": list(zip(starts, ends + [None] * (len(starts) - len(ends))))}


def facts_check(run) -> list[str]:
    facts = {f["id"] for f in run.need("facts.json")["facts"]}
    errs = []
    for b in run.need("script.json")["beats"]:
        if b.get("stat") and b["stat"]["fact_id"] not in facts:
            errs.append(f"{b['id']}: stat without a valid fact")
    for s in run.need("shotlist.json")["shots"]:
        for c in s.get("callouts_t", []):
            if re.search(r"\d", c["text"]) and c.get("fact_id") not in facts:
                errs.append(f"{s['id']}: callout '{c['text']}' has a number but no valid fact")
    return errs


def snapshots(run) -> tuple[str, list[str]]:
    words = run.need("words.json")
    times = [round((b["start"] + b["end"]) / 2, 2) for b in words["beats"]]
    script = run.need("script.json")                  # never sample a counter mid-roll: land after it settles
    for i, (b, sb) in enumerate(zip(words["beats"], script["beats"])):
        if sb.get("stat"):
            settle = b["start"] + (0.08 if sb["mechanism"] == "hook" or not sb.get("title") else 1.75) + 0.8
            if times[i] < settle < b["end"]:
                times[i] = round(min(settle + 0.1, b["end"] - 0.05), 2)
    times = [0.6] + times + [round(words["duration"] - 0.2, 2)]          # hook frame and loop frame too
    d = run.path("hf")
    hf.run(["snapshot", "--at", ",".join(str(t) for t in times)], cwd=d, timeout=1800)
    root = os.path.join(d, ".hyperframes", "artifacts", "snapshots")      # newest snapshot run (paths have spaces)
    latest = max((os.path.join(root, x) for x in os.listdir(root)), key=os.path.getmtime)
    paths = sorted(os.path.join(latest, f) for f in os.listdir(latest) if f.startswith("frame-") and f.endswith(".png"))
    out_dir = run.path("qa", "snapshots")
    os.makedirs(out_dir, exist_ok=True)
    kept = []
    for p in paths:
        dst = os.path.join(out_dir, os.path.basename(p))
        shutil.copyfile(p, dst)
        kept.append(dst)
    sheet_dst = run.path("qa", "contact_sheet.jpg")
    contact_sheet(kept, sheet_dst)
    return sheet_dst, kept


def contact_sheet(frames: list[str], out: str, cols: int = 6, w: int = 270):
    """One labelled grid of every snapshot (HyperFrames splits long runs into several sheets)."""
    from PIL import Image, ImageDraw
    h = int(w * 16 / 9)
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * (h + 22)), (16, 18, 22))
    d = ImageDraw.Draw(sheet)
    for i, f in enumerate(frames):
        im = Image.open(f).convert("RGB").resize((w, h))
        x, y = (i % cols) * w, (i // cols) * (h + 22)
        sheet.paste(im, (x, y + 22))
        label = re.search(r"at-([\d.]+)s", os.path.basename(f))
        d.text((x + 4, y + 4), f"{label.group(1) if label else i} s", fill=(230, 230, 230))
    sheet.save(out, quality=88)


def rubric(run, sheet: str, frames: list[str]) -> dict:
    script = run.need("script.json")
    audio = run.load("audio/audio.json", {}) or {}
    narration = "\n".join(f"{b['id']}: {b['narration']}" for b in script["beats"])
    images = [("contact sheet: one frame per beat midpoint, plus the first and last frame", sheet)]
    images += [(f"frame {os.path.basename(f)}", f) for f in frames[:3]] + [("last frame", frames[-1])]
    prompt = f"""Score this vertical engineering explainer against the rubric, 1-5 each (5 = the description fully
met; be strict: 4 means good enough to publish on a premium channel). Judge only what you can see and what is
stated here; one short reason each.

Narration by beat:
{narration}

Measured audio: {json.dumps(audio.get('loudness'))}, {len(audio.get('sfx', []))} sound effects placed on events.
Stills are taken after stat counters settle; captions are karaoke groups of 2-4 words by design (the brief).
Facts: every number on screen traces to a verified source (checked in code).

Rubric:
""" + "\n".join(f"- {k}: {v}" for k, v in RUBRIC.items())
    return llm.ask("You are a demanding creative director for a premium 3D engineering channel.", prompt, SCHEMA,
                   effort="medium", images=images, label="cutaway_rubric")


def review(run) -> dict:
    """Contact sheet + rubric report for an existing run (python -m cutaway review <slug>)."""
    sheet, frames = snapshots(run)
    scores = rubric(run, sheet, frames)
    lines = [f"{k:14s} {v['score']}/5  {v['why']}" for k, v in scores["scores"].items()]
    summary = "\n".join(lines) + f"\n\nWeakest: {scores['weakest']}\nFixes:\n- " + "\n- ".join(scores["fixes"])
    run.save("qa/review.json", scores)
    run.save("qa/review.md", summary + "\n")
    return {"summary": summary, "contact_sheet": sheet, "scores": scores}


def run(run):
    d = run.path("hf")
    report = {"quality": run.quality, "gates": {}, "errors": []}
    lint = hf.run(["lint"], cwd=d, check=False, timeout=600)
    n_err = int((re.findall(r"(\d+) error", lint.stdout or "") or ["0"])[-1])
    report["gates"]["lint"] = {"errors": n_err}
    if n_err:
        report["errors"].append(f"lint: {n_err} errors")
    try:
        chk = hf.run_json(["check"], cwd=d, timeout=1800)
    except RuntimeError as exc:
        chk = {"ok": False, "error": str(exc)[:500]}
    sections = ("lint", "runtime", "layout", "motion", "contrast", "craft", "audio")
    errs = [{"section": sec, **f} for sec in sections for f in (chk.get(sec) or {}).get("findings", [])
            if f.get("severity") == "error"]
    report["gates"]["check"] = {"ok": chk.get("ok"), "errors": len(errs),
                                "warnings": sum((chk.get(sec) or {}).get("warningCount", 0) for sec in sections),
                                "first": [f"{f['section']}/{f.get('code')} @ {f.get('time')}: {f.get('selector', '')}"
                                          for f in errs[:8]]}
    if errs or chk.get("ok") is False:
        report["errors"].append(f"check: {len(errs)} errors")
    sheet, frames = snapshots(run)
    report["contact_sheet"] = sheet
    # the release candidate
    q = "delivery" if run.quality == "final" else "draft"
    out = run.path("release", f"candidate_{run.quality}.mp4")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    hf.run(["render", "--quality", q, "-o", out], cwd=d, timeout=7200)
    probe = _ffprobe(out)
    dur = float(probe["format"]["duration"])
    want = run.need("shotlist.json")["duration"]
    v = [s for s in probe["streams"] if s["codec_type"] == "video"]
    a = [s for s in probe["streams"] if s["codec_type"] == "audio"]
    report["gates"]["ffprobe"] = {"duration": dur, "want": want, "size": [v[0]["width"], v[0]["height"]] if v else None,
                                  "audio": bool(a)}
    if abs(dur - want) > 0.15:
        report["errors"].append(f"duration {dur:.2f} s, want {want:.2f}")
    if not v or (v[0]["width"], v[0]["height"]) != (1080, 1920):
        report["errors"].append("not 1080x1920")
    if not a:
        report["errors"].append("no audio stream")
    det = _detect(out)
    report["gates"]["black_freeze"] = det
    if det["black"]:
        report["errors"].append(f"black stretches: {det['black']}")
    long_freeze = [f for f in det["freeze"] if f[1] is None or f[1] - f[0] > 0.3]
    if long_freeze:
        report["errors"].append(f"frozen stretches: {long_freeze}")
    loud = measure(out)
    report["gates"]["loudness"] = loud
    if loud["I"] is None or abs(loud["I"] - TARGET_I) > 1.0 or (loud["TP"] or 0) > TARGET_TP + 0.3:
        report["errors"].append(f"loudness {loud}")
    fc = facts_check(run)
    report["gates"]["facts"] = {"errors": fc}
    report["errors"] += fc
    scores = rubric(run, sheet, frames)
    report["rubric"] = scores
    low = [k for k, v in scores["scores"].items() if v["score"] < 4]
    if low:
        msg = f"rubric below 4: {low}"
        (report["errors"].append if run.quality == "final" else report.setdefault("warnings", []).append)(msg)
    report["candidate"] = out
    run.save("qa/qa.json", report)
    for e in report["errors"]:
        log.error("[qa] %s", e)
    for w in report.get("warnings", []):
        log.warning("[qa] %s", w)


def validate(run):
    r = run.need("qa/qa.json")
    if r["errors"]:
        raise StageError("QA gates failed:\n- " + "\n- ".join(r["errors"]))
    if not os.path.exists(r["candidate"]):
        raise StageError("release candidate missing")
