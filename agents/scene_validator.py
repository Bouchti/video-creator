"""
Scene validator for Blender films: accepts or rejects every ~3 second window of the render AS
SOON AS ITS FRAMES EXIST, while Blender keeps rendering the rest (the same idea as the local-ai
pipeline's per-shot review, applied to a 3D render).

Each window gets:
  1. technical QC (free, local): frames present, not black / blown out / flat, no Blender
     "missing texture" magenta, not frozen;
  2. a story review by Claude vision: three frames of the window (start / middle / end) against
     what the beat's action is supposed to show and what the narration says at that moment.
     Scores 1-10 for visual_match, readability, image_quality and continuity, plus fatal problems
     and a concrete fix. Accepted = no fatal problem and every score >= SCENE_MIN_SCORE (or a
     quality floor), like local_video/visual_review.py.

Results stream into <work>/scene_review.json (and the judged frames into <work>/review/), so a
failed scene is known minutes into a render instead of at the end. make_film uses it like this:

  SCENE_VALIDATE=1|0          on by default for evolution films, off for cutaway films
  SCENE_POLICY=stop           stop Blender at the first rejected window (default)
               fix            render the whole film, then let Claude fix EVERY rejected window in one
                              turn (agents/set_builder.fix_scenes) and resume
               report         render everything, then fail with the list of rejected windows
               warn           render everything, log rejections, assemble the video anyway
  SCENE_FIX_ABORT_EARLY=0     policy "fix": stop at the first rejection again (one window per AI turn,
                              which costs one repair turn and one full re-render per bad window)
  SCENE_WINDOW_SECONDS=3      window length
  SCENE_MIN_SCORE=6           acceptance threshold (1-10)
  SCENE_PREFLIGHT=1           rehearse exact final-timing samples before production rendering
  SCENE_PREFLIGHT_FIX_ATTEMPTS=3  cheap rehearsal repair rounds before full frames may start
  SCENE_FIX_ATTEMPTS=2        auto-fix rounds per render (policy "fix")
  SCENE_REVIEW_BACKEND        "subscription" (default) or "codex"
  SCENE_REVIEW_CLI_MODEL      optional Claude subscription model override

Re-check an existing render without rendering:  python -m agents.scene_validator <film name or JSON>
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image

log = logging.getLogger("pipeline")

FPS = 30
REVIEW_W = int(os.getenv("SCENE_REVIEW_WIDTH") or "360")  # enough for phone-scale QC; lowers image tokens
REVIEW_JPEG_QUALITY = int(os.getenv("SCENE_REVIEW_JPEG_QUALITY") or "78")


def _env_flag(name, default):
    value = (os.getenv(name) or "").strip().lower() or default     # unset or empty → default
    return value not in ("0", "false", "no", "off")


def policy() -> str:
    p = (os.getenv("SCENE_POLICY") or "stop").strip().lower()
    return p if p in ("stop", "fix", "report", "warn") else "stop"


def min_score() -> int:
    return int(os.getenv("SCENE_MIN_SCORE") or "6")


class SceneRejected(RuntimeError):
    """One or more rendered windows failed review; .rejected holds their reports."""

    def __init__(self, rejected, report_path):
        self.rejected, self.report_path = rejected, report_path
        lines = [f"  window {w['window']:02d} {w['t0']:.1f}-{w['t1']:.1f}s [{w['action']}]: "
                 + "; ".join((w.get('fatal_problems') or w.get('problems') or [w.get('reason', '')])[:2])
                 for w in rejected]
        super().__init__(f"{len(rejected)} scene window(s) rejected (see {report_path}):\n" + "\n".join(lines))


# ------------------- windows -------------------

def plan_windows(film: dict, spans: list, seconds: float = None, spec=None) -> list:
    """Split the timeline into ~`seconds` windows that never straddle two beats.
    spans: [{"start", "end"}] 0-based inclusive (timings.json). Windows use 1-based frame numbers."""
    seconds = seconds or float(os.getenv("SCENE_WINDOW_SECONDS") or "3")
    per = max(30, int(seconds * FPS))
    out = []
    for k, (beat, sp) in enumerate(zip(film["beats"], spans)):
        f0, f1 = sp["start"] + 1, sp["end"] + 1
        n = max(1, round((f1 - f0 + 1) / per))
        acts = list(beat.get("actions") or [beat.get("action")])
        shows = []
        if spec is not None:
            shows = [spec.ACTIONS.get(a, {}).get("shows", "") for a in acts]
        for j in range(n):
            a = f0 + (f1 - f0 + 1) * j // n
            b = f0 + (f1 - f0 + 1) * (j + 1) // n - 1
            out.append({"window": len(out) + 1, "beat": k + 1, "action": "+".join(acts), "part": f"{j + 1}/{n}",
                        "f0": a, "f1": b, "t0": (a - 1) / FPS, "t1": b / FPS, "shows": " ".join(shows),
                        "text": beat.get("text", "")})
    return out


def sample_picks(w: dict) -> list[tuple[str, int]]:
    """The exact three production frames used to judge a timeline window."""
    n = w["f1"] - w["f0"]
    return [("start", w["f0"] + max(1, n // 10)),
            ("middle", w["f0"] + n // 2),
            ("end", w["f1"] - max(1, n // 10))]


def _is_rendered_window(w: dict, spec=None) -> bool:
    """Rewind is assembled from existing frames in post; Blender never renders its timeline range."""
    actions = str(w.get("action") or "").split("+")
    if actions == ["rewind"]:
        return False
    return not (spec and actions and all(spec.ACTIONS.get(a, {}).get("kind") == "rewind" for a in actions))


def _frame_path(frames_dir, f):
    return os.path.join(frames_dir, f"f_{f:04d}.png")


def window_ready(w, frames_dir, settle=2.0) -> bool:
    """All frames of the window exist and the newest was written more than `settle` s ago."""
    newest = 0.0
    for f in range(w["f0"], w["f1"] + 1):
        p = _frame_path(frames_dir, f)
        try:
            st = os.stat(p)
        except OSError:
            return False
        if st.st_size == 0:
            return False
        newest = max(newest, st.st_mtime)
    return time.time() - newest >= settle


# ------------------- 1. technical QC -------------------

def _void_band(lum) -> float:
    """Fraction of the frame height, from the bottom edge up, that is uniform black: the world's edge."""
    rows = 0
    for row in lum[::-1]:
        if row.mean() >= 0.03 or row.std() >= 0.02:
            break
        rows += 1
    return rows / max(1, lum.shape[0])


def technical_check(paths: list) -> dict:
    """Cheap pixel checks on a few frames: black, blown out, flat, Blender's magenta, frozen."""
    fatal, problems, stats = [], [], []
    arrays = []
    for p in paths:
        try:
            im = Image.open(p).convert("RGB")
        except Exception as exc:                     # noqa: BLE001
            fatal.append(f"unreadable frame {os.path.basename(p)} ({exc.__class__.__name__})")
            continue
        im.thumbnail((270, 480))
        a = np.asarray(im).astype(np.float32) / 255.0
        arrays.append(a)
        lum = a @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        magenta = float(np.mean((a[..., 0] > 0.8) & (a[..., 2] > 0.8) & (a[..., 1] < 0.25)))
        stats.append({"mean": round(float(lum.mean()), 3), "std": round(float(lum.std()), 3),
                      "magenta": round(magenta, 4)})
        name = os.path.basename(p)
        if lum.mean() < 0.04:
            fatal.append(f"{name} is black (mean luminance {lum.mean():.2f})")
        elif lum.mean() > 0.96:
            fatal.append(f"{name} is blown out white (mean luminance {lum.mean():.2f})")
        if lum.std() < 0.02:
            fatal.append(f"{name} is a flat single colour (no scene visible)")
        void = _void_band(lum)
        if void >= 0.08:
            fatal.append(f"{name} shows an empty black void across the bottom {void:.0%} of the frame "
                         "(the ground/terrain ends inside the shot)")
        if magenta > 0.03:
            fatal.append(f"{name} shows Blender's magenta missing-texture colour on {magenta:.0%} of the frame")
    if len(arrays) >= 2 and all(np.abs(arrays[0] - b).mean() < 0.002 for b in arrays[1:]):
        problems.append("the window is frozen: start, middle and end frames are identical")
    return {"valid": not fatal, "fatal_problems": fatal, "problems": problems, "frames": stats}


# ------------------- 2. story review (Claude vision) -------------------

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "visual_match": {"type": "integer", "minimum": 1, "maximum": 10},
        "readability": {"type": "integer", "minimum": 1, "maximum": 10},
        "image_quality": {"type": "integer", "minimum": 1, "maximum": 10},
        "continuity": {"type": "integer", "minimum": 1, "maximum": 10},
        "fatal_problems": {"type": "array", "items": {"type": "string"}},
        "problems": {"type": "array", "items": {"type": "string"}},
        "fix": {"type": "string"},
    },
    "required": ["visual_match", "readability", "image_quality", "continuity", "fatal_problems", "problems", "fix"],
    "additionalProperties": False,
}
SCORES = ("visual_match", "readability", "image_quality", "continuity")


def _instructions(w, subject, previous):
    extra = " (plus the previous window's end frame, for continuity)" if previous else ""
    first, _, count = str(w.get("part") or "").partition("/")
    if first == "1" and count.isdigit() and int(count) > 1:
        # the film's first window of a beat is its setup shot (Max making his change), like the preview's
        # 1/8 still: "no clay core shown yet" rejected a correct setup
        extra += (". This is the FIRST part of its beat: the setup (Max making his change, close up). Never fault "
                  "the absence of the result, its labels or arrows, or the payoff here; judge only that the "
                  "setup is clear and on track")
    if w.get("part") == "whole beat":
        # Set previews: the stills sit at 1/8, 1/2 and 7/8 of the beat, and every beat opens on Max making his
        # change before the mechanism and its result are shown. Faulting the opening still for the payoff
        # rejected almost every beat of the first auto-built levee set.
        extra += (". These stills are at 1/8, 1/2 and 7/8 of the WHOLE beat: the START still is the setup "
                  "(Max making his change, close up), so never fault the absence of labels, arrows, the result "
                  "or the payoff there; judge the required content on the MIDDLE and END stills")
    return f"""You are the director checking a 3D render (Blender, stylised but realistic, vertical 9:16)
of a short explainer film, one ~3 second window at a time, BEFORE the rest of the film is finished.

Film subject: {subject}
This window: beat {w['beat']}, action "{w['action']}" (part {w['part']}), {w['t0']:.1f}-{w['t1']:.1f} s.
What this action must show over its whole beat: {w['shows'] or '(see narration)'}
Narration spoken during this beat: "{w['text']}"
The frames you get are the START, MIDDLE and END of this window{extra}.
A window is only PART of its beat: judge whether it is on track for its part of the action (the
first window of a beat may only show the setup; a later one the payoff).

Score 1-10:
- visual_match: the frames show this action / what the narration says (for this part of the beat)
- readability: the subject is visible, in frame, not hidden behind a foreground object, not too small
  or too far, a viewer on a phone understands what they are looking at
- image_quality: clean render: no black/blank frames, no missing-texture magenta, no exploded or
  floating geometry, no objects intersecting in obviously wrong ways, no z-fighting flicker
- continuity: same world and objects as the previous window; changes are the story's, not glitches

fatal_problems (only concrete, visually unambiguous failures, each with the visible evidence): the
subject is not in frame or fully blocked; the frames show a different action than this beat; broken
or exploded geometry; black / blank / magenta frames; a camera inside an object.
Also fatal: a required action or explicit narration detail is visibly missing or wrong in the final
part of its beat; a character or prop visibly floats, hovers, clips through, or is detached from the
surface supporting it; the hero (Max) acts in this window but is so small that his face, hands and
what he is doing cannot be read on a phone (roughly under a fifth of the frame height); an explanatory
label is too small to read on a phone or cut off by the frame edge; an empty black void where the world
ends. Put those failures in fatal_problems, not merely problems.
Do NOT call stylised low-poly trees, simple models, missing fine detail, motion blur, depth of field or
a camera angle you would have chosen differently fatal. Line drawings in white/orange are intentional.
Captions of the narration, the closing question and stat stickers are added in post-production, over
the render: never ask for spoken words or the question as on-screen text, and never fault their absence.
Do not transfer a narrated comparison or external record onto an in-world display. For example, if
the hero's object is on a scale while narration separately cites a world record, the scale should show
the hero's result unless the action explicitly requires the record number.
fix: one concrete instruction for the 3D set's code (camera position/aim, object placement, timing),
empty if nothing to fix."""


def _jpeg(path, width=REVIEW_W):
    im = Image.open(path).convert("RGB")
    h = int(im.height * width / im.width)
    im = im.resize((width, h), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=REVIEW_JPEG_QUALITY, optimize=True)
    return buf.getvalue()


def _backend():
    from agents.showrunner import active_backend
    explicit = (os.getenv("SCENE_REVIEW_BACKEND") or "").strip().lower()
    active = active_backend()
    # A process-wide usage-limit fallback moves review work too.
    return active if not explicit or active != explicit else explicit


def _review_cli(prompt, images, schema=REVIEW_SCHEMA):
    """claude -p on the Claude subscription: the images are copied into a temp dir and read with
    the Read tool (API credentials stripped, like the showrunner's subscription backend)."""
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("Claude Code CLI not found")
    from agents.showrunner import (UsageLimit, _API_ENV, CLI_MODEL, _capped_effort,
                                   _record_claude_usage, check_budget)
    check_budget("scene review")
    env = {k: v for k, v in os.environ.items() if k not in _API_ENV}
    with tempfile.TemporaryDirectory() as tmp:
        names = []
        for k, (label, p) in enumerate(images):
            dst = os.path.join(tmp, f"{k + 1}_{os.path.basename(p)}")
            shutil.copyfile(p, dst)
            names.append(f"- {os.path.basename(dst)}: {label}")
        full = (prompt + "\n\nRead these image files (in the current directory) with the Read tool, then return "
                "the review:\n" + "\n".join(names))
        cmd = [exe, "-p", "--output-format", "json", "--model", os.getenv("SCENE_REVIEW_CLI_MODEL", CLI_MODEL),
               "--effort", _capped_effort(os.getenv("SCENE_REVIEW_EFFORT") or "low"),
               "--no-session-persistence", "--strict-mcp-config", "--setting-sources", "",
               "--tools", "Read", "--allowedTools", "Read", "--json-schema", json.dumps(schema)]
        r = subprocess.run(cmd, input=full, capture_output=True, text=True, encoding="utf-8", cwd=tmp, env=env,
                           timeout=600)
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"claude -p failed (exit {r.returncode}): {(r.stderr or r.stdout)[-400:]}") from exc
    result_text = str(data.get("result") or "")
    if data.get("is_error") and "limit" in result_text.lower() and "reset" in result_text.lower():
        raise UsageLimit(result_text[:500])
    if data.get("is_error") or data.get("subtype") != "success":
        raise RuntimeError(f"claude -p: {result_text[:200]}")
    _record_claude_usage(data, "scene review")
    out = data.get("structured_output")
    return out if out is not None else json.loads(data["result"])


def _review_codex(prompt, images, schema=REVIEW_SCHEMA):
    """Review images through the logged-in Codex subscription."""
    from agents import codex_cli
    from agents.showrunner import UsageLimit, codex_unavailable

    labels = "\n".join(f"Image {i + 1}: {label}" for i, (label, _) in enumerate(images))
    full = prompt + "\n\nAttached images, in order:\n" + labels
    model = os.getenv("SCENE_REVIEW_CODEX_MODEL") or os.getenv("SHOWRUNNER_CODEX_MODEL") or "gpt-5.6-sol"
    try:
        out, _ = codex_cli.run(full, schema=schema, effort=os.getenv("SCENE_REVIEW_EFFORT") or "low",
                               images=[p for _, p in images], model=model,
                               timeout=900, effort_cap_env="SCENE_REVIEW_CODEX_EFFORT_CAP")
        return out
    except RuntimeError as exc:
        if codex_unavailable(exc):
            raise UsageLimit(str(exc)[:500]) from exc
        raise


def _review_dispatch(prompt, images, schema=REVIEW_SCHEMA):
    """Use the active reviewer and switch the process after a subscription usage limit."""
    from agents.showrunner import UsageLimit, activate_fallback, active_backend
    backend = _backend()
    try:
        return (_review_codex(prompt, images, schema) if backend == "codex" else
                _review_cli(prompt, images, schema))
    except UsageLimit as exc:
        if activate_fallback(str(exc), failed_backend=backend):
            fallback = active_backend()
            return (_review_codex(prompt, images, schema) if fallback == "codex" else
                    _review_cli(prompt, images, schema))
        raise


BATCH_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {"reviews": {"type": "array", "items": {
        "type": "object",
        "properties": {"window": {"type": "integer"}, **REVIEW_SCHEMA["properties"]},
        "required": ["window", *REVIEW_SCHEMA["required"]],
        "additionalProperties": False,
    }}},
    "required": ["reviews"],
    "additionalProperties": False,
}


def review_batch(items: list, subject: str) -> dict:
    """Judge several windows in one turn on every backend to amortize fixed prompt overhead."""
    blocks, images = [], []
    for w, beat_images in items:
        first = len(images) + 1
        images.extend(beat_images)
        last = len(images)
        blocks.append(_instructions(w, subject, None) +
                      f"\nThis beat uses attached images {first}-{last}. Return window={w['window']}.")
    prompt = ("Review every beat below independently. Return exactly one review per requested window, in the "
              "same order. Do not omit a window. Use adjacent beats' end/start frames to judge continuity.\n\n"
              + "\n\n--- NEXT BEAT ---\n\n".join(blocks))
    values = _review_dispatch(prompt, images, BATCH_REVIEW_SCHEMA)
    by_window = {int(v["window"]): {**judge(v), "skipped": False} for v in values.get("reviews", [])}
    expected = {int(w["window"]) for w, _ in items}
    if set(by_window) != expected:
        raise RuntimeError(f"batch review returned windows {sorted(by_window)}, expected {sorted(expected)}")
    return by_window


def judge(values: dict, threshold: int = None) -> dict:
    """Acceptance rule (mirrors local_video/visual_review.py): no fatal problem, and every score at the
    threshold, or a quality floor (visual_match and readability at most 1 below, average at it)."""
    threshold = threshold or min_score()
    scores = {k: int(values.get(k, 0)) for k in SCORES}
    problems = [str(x) for x in values.get("problems", []) if x]
    fatal = [str(x) for x in values.get("fatal_problems", []) if x]
    # Fail closed on physically impossible contact even when a vision model files it as an
    # ordinary note or assigns generous numeric scores.
    impossible = [p for p in problems if re.search(
        r"\b(float(?:s|ing|ed)?|hover(?:s|ing|ed)?|suspend(?:s|ing|ed)?|clips? through|detached)\b", p, re.I)]
    fatal += [p for p in impossible if p not in fatal]
    avg = sum(scores.values()) / len(scores)
    strict = all(v >= threshold for v in scores.values())
    floor = (scores["visual_match"] >= threshold and scores["readability"] >= threshold - 1
             and scores["image_quality"] >= threshold and avg >= threshold)
    valid = not fatal and (strict or floor)
    return {"valid": valid, "acceptance": "strict" if strict and valid else "quality-floor" if valid else "rejected",
            "average_score": round(avg, 2), "threshold": threshold, **scores, "fatal_problems": fatal,
            "problems": problems, "fix": str(values.get("fix") or "")}


def review_images(w: dict, images: list, subject: str, previous: str = None) -> dict:
    """Story review of one window. Service failures reject unless explicitly overridden."""
    if not _env_flag("SCENE_VISION", "1"):
        return {"valid": _env_flag("SCENE_ALLOW_QC_SKIP", "0"), "skipped": True,
                "reason": "vision review disabled (SCENE_VISION=0)"}
    prompt = _instructions(w, subject, previous)
    imgs = ([("previous window end frame", previous)] if previous else []) + images
    try:
        values = _review_dispatch(prompt, imgs)
    except Exception as exc:                         # noqa: BLE001
        from agents.showrunner import UsageLimit
        text = str(exc).lower()
        if isinstance(exc, UsageLimit) or ("limit" in text and any(x in text for x in ("reset", "rate", "usage"))):
            raise UsageLimit(str(exc)[:500]) from exc
        log.warning(f"[scenes] vision review unavailable for window {w['window']} ({str(exc)[:120]}); "
                    "technical QC only")
        return {"valid": _env_flag("SCENE_ALLOW_QC_SKIP", "0"), "skipped": True,
                "reason": f"vision review unavailable: {exc.__class__.__name__}"}
    return {**judge(values), "skipped": False}


def _prepare_window(w: dict, frames_dir: str, review_dir: str):
    """Run local QC and encode review frames once; shared by single and batched review paths."""
    os.makedirs(review_dir, exist_ok=True)
    picks = sample_picks(w)
    paths = [_frame_path(frames_dir, f) for _, f in picks]
    tech = technical_check(paths)
    images = []
    for (label, f), p in zip(picks, paths):
        if os.path.exists(p):
            dst = os.path.join(review_dir, f"w{w['window']:02d}_{label}_f{f:04d}.jpg")
            with open(dst, "wb") as fh:
                fh.write(_jpeg(p))
            images.append((f"{label} frame ({(f - 1) / FPS:.1f} s)", dst))
    rep = {**{k: w[k] for k in ("window", "beat", "action", "part", "f0", "f1", "t0", "t1")},
           "technical": tech, "images": [p for _, p in images]}
    return rep, images, tech


def review_sampled_windows(film: dict, spans: list, work: str, spec=None) -> dict:
    """Review a cheap dress rehearsal made from the exact production-window sample frames.

    ``work/frames`` contains only the three frames returned by :func:`sample_picks`, not a full
    animation. Pixel+rubric keyed results persist across repair rounds, so accepted unchanged
    windows consume neither another model call nor another judgment.
    """
    frames_dir, review_dir = os.path.join(work, "frames"), os.path.join(work, "review")
    os.makedirs(review_dir, exist_ok=True)
    windows = [w for w in plan_windows(film, spans, spec=spec) if _is_rendered_window(w, spec)]
    subject = ((getattr(spec, "SUBJECT", "") if spec else "") + " | " + film.get("title", "")).strip(" |")
    cache_path = os.path.join(work, "review_cache.json")
    try:
        cache = json.load(open(cache_path, encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}

    def key_for(w, images):
        meta = {"version": 1, "window": w, "subject": subject, "min_score": min_score(),
                "review_width": REVIEW_W, "jpeg_quality": REVIEW_JPEG_QUALITY,
                "rubric": hashlib.sha256(_instructions(w, subject, None).encode("utf-8")).hexdigest()}
        h = hashlib.sha256(json.dumps(meta, sort_keys=True).encode("utf-8"))
        for _, path in images:
            with open(path, "rb") as fh:
                h.update(fh.read())
        return h.hexdigest()

    rows, pending = [], []
    for w in windows:
        rep, images, tech = _prepare_window(w, frames_dir, review_dir)
        if not tech["valid"]:
            rows.append({**rep, "valid": False, "acceptance": "rejected",
                         "fatal_problems": tech["fatal_problems"], "problems": tech["problems"],
                         "fix": "", "skipped": False})
            continue
        key = key_for(w, images)
        if key in cache:
            rows.append({**rep, **cache[key], "cached": True})
        else:
            pending.append((w, rep, images, key))

    if _env_flag("SCENE_VISION", "1"):
        size = max(1, int(os.getenv("SCENE_REVIEW_BATCH_SIZE") or "4"))
        for start in range(0, len(pending), size):
            batch = pending[start:start + size]
            reviewed = review_batch([(w, images) for w, _, images, _ in batch], subject)
            for w, rep, _images, key in batch:
                result = reviewed[w["window"]]
                cache[key] = result
                rows.append({**rep, **result})
            tmp = cache_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(cache, fh, indent=1)
            os.replace(tmp, cache_path)
    else:
        for w, rep, images, key in pending:
            result = review_images(w, images, subject)
            if not result.get("skipped"):
                cache[key] = result
            rows.append({**rep, **result})

    rows.sort(key=lambda r: r["f0"])
    rejected = [r for r in rows if not r.get("valid")]
    report = {"windows": rows, "rejected": rejected, "checked": len(rows), "planned": len(windows),
              "accepted": sum(1 for r in rows if r.get("valid")), "policy": "preflight",
              "complete": len(rows) == len(windows)}
    report_path = os.path.join(work, "scene_review.json")
    tmp = report_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    os.replace(tmp, report_path)
    for r in rows:
        detail = "" if r.get("valid") else ": " + "; ".join(
            (r.get("fatal_problems") or r.get("problems") or [r.get("reason", "")])[:2])
        log.info(f"[preflight] window {r['window']:02d} [{r['action']} {r['part']}] "
                 f"{'ACCEPTED' if r.get('valid') else 'REJECTED'}"
                 + (" [cached]" if r.get("cached") else "") + detail)
    return report


def validate_window(w: dict, frames_dir: str, review_dir: str, subject: str, previous: str = None) -> dict:
    rep, images, tech = _prepare_window(w, frames_dir, review_dir)
    if not tech["valid"]:
        return {**rep, "valid": False, "acceptance": "rejected", "fatal_problems": tech["fatal_problems"],
                "problems": tech["problems"], "fix": "", "skipped": False}
    story = review_images(w, images, subject, previous)
    story["problems"] = tech["problems"] + story.get("problems", [])
    return {**rep, **story}


# ------------------- the watcher (runs beside Blender) -------------------

class SceneWatcher:
    """Validates each window as soon as its frames are on disk. Thread-safe; call start() before the
    render, should_abort() while waiting on Blender, finish() after it ends."""

    def __init__(self, film: dict, spans: list, work: str, spec=None, only_frames=None, keep_previous=True,
                 preapproved=None):
        self.film, self.work = film, work
        self.frames_dir = os.path.join(work, "frames")
        self.review_dir = os.path.join(work, "review")
        self.report_path = os.path.join(work, "scene_review.json")
        self.subject = (getattr(spec, "SUBJECT", "") + " | " + film.get("title", "")).strip(" |")
        self.windows = [w for w in plan_windows(film, spans, spec=spec) if _is_rendered_window(w, spec)]
        if only_frames is not None:
            only = set(only_frames)
            self.windows = [w for w in self.windows if any(f in only for f in range(w["f0"], w["f1"] + 1))]
        self.results = {}
        if keep_previous and os.path.exists(self.report_path):        # resume / redo: keep earlier verdicts
            try:
                old = json.load(open(self.report_path, encoding="utf-8"))
                todo = {(w["f0"], w["f1"]) for w in self.windows}
                for r in old.get("windows", []):
                    if (r["f0"], r["f1"]) not in todo or (only_frames is None and r.get("valid")
                                                          and all(os.path.exists(_frame_path(self.frames_dir, f))
                                                                  for f in (r["f0"], r["f1"]))):
                        self.results[(r["f0"], r["f1"])] = r
            except (OSError, json.JSONDecodeError, KeyError):
                pass
        self.policy = policy()
        self._lock = threading.Lock()
        self._abort = threading.Event()
        self._stop = threading.Event()
        self._render_done = threading.Event()
        self._fatal_error = None
        self.batch_size = (max(1, int(os.getenv("SCENE_REVIEW_BATCH_SIZE") or "4"))
                           if _env_flag("SCENE_VISION", "1") else 1)
        self._pool = ThreadPoolExecutor(max_workers=int(os.getenv("SCENE_REVIEW_WORKERS", "1")))
        self._submitted = set(self.results)          # kept verdicts are not checked again
        self.preapproved = preapproved or {}          # exact-timing rehearsal verdicts; still run local pixel QC
        self._thread = None

    # -- lifecycle --
    def start(self):
        log.info(f"[scenes] validating {len(self.windows)} windows of ~{os.getenv('SCENE_WINDOW_SECONDS', '3')} s "
                 f"while rendering (policy: {self.policy})")
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def render_finished(self):
        self._render_done.set()

    def should_abort(self) -> bool:
        return self._abort.is_set()

    def finish(self, timeout=3600) -> dict:
        """Wait for every remaining window (the render is over), then return the report."""
        self._render_done.set()
        t0 = time.time()
        while (time.time() - t0 < timeout and not self._abort.is_set()
               and self._fatal_error is None):
            with self._lock:
                pending = [w for w in self.windows if (w["f0"], w["f1"]) not in self.results]
            ready = [w for w in pending if all(os.path.exists(_frame_path(self.frames_dir, f))
                                               for f in range(w["f0"], w["f1"] + 1))]
            if not ready:
                break
            time.sleep(1.0)
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)
        self._pool.shutdown(wait=True, cancel_futures=self._abort.is_set())
        if self._fatal_error is not None:
            raise self._fatal_error
        return self.report()

    # -- internals --
    def _loop(self):
        while not self._stop.is_set():
            ready = []
            for w in self.windows:
                key = (w["f0"], w["f1"])
                if key in self._submitted:
                    continue
                if window_ready(w, self.frames_dir, settle=0.5 if self._render_done.is_set() else 2.0):
                    ready.append(w)
            while len(ready) >= self.batch_size or (ready and self._render_done.is_set()):
                batch = ready[:self.batch_size]
                del ready[:self.batch_size]
                for w in batch:
                    self._submitted.add((w["f0"], w["f1"]))
                if self.batch_size == 1:
                    self._pool.submit(self._check, batch[0])
                else:
                    self._pool.submit(self._check_batch, batch)
            if self._abort.is_set():
                return
            time.sleep(2.0)

    def _previous_frame(self, w):
        prev = [r for r in self.results.values() if r["f1"] == w["f0"] - 1 and r.get("images")]
        return prev[0]["images"][-1] if prev else None

    def _check(self, w):
        try:
            rep, images, tech = _prepare_window(w, self.frames_dir, self.review_dir)
            approved = self.preapproved.get((w["f0"], w["f1"]))
            if not tech["valid"]:
                r = {**rep, "valid": False, "acceptance": "rejected",
                     "fatal_problems": tech["fatal_problems"], "problems": tech["problems"],
                     "fix": "", "skipped": False}
            elif approved:
                story = {k: v for k, v in approved.items() if k not in
                         ("window", "beat", "action", "part", "f0", "f1", "t0", "t1", "images", "technical")}
                r = {**rep, **story, "valid": True, "preflight_approved": True,
                     "problems": tech["problems"] + story.get("problems", [])}
            else:
                story = review_images(w, images, self.subject, self._previous_frame(w))
                story["problems"] = tech["problems"] + story.get("problems", [])
                r = {**rep, **story}
        except Exception as exc:                     # noqa: BLE001
            if self._remember_usage_limit(exc):
                return
            r = {**{k: w[k] for k in ("window", "beat", "action", "part", "f0", "f1", "t0", "t1")},
                 "valid": _env_flag("SCENE_ALLOW_QC_SKIP", "0"), "skipped": True,
                 "reason": f"validator error: {exc}"}
        self._store_result(w, r)

    def _check_batch(self, windows):
        """Technical-check locally, then send up to SCENE_REVIEW_BATCH_SIZE windows per AI turn."""
        prepared, ai_items = {}, []
        try:
            for w in windows:
                rep, images, tech = _prepare_window(w, self.frames_dir, self.review_dir)
                prepared[w["window"]] = (w, rep, tech)
                approved = self.preapproved.get((w["f0"], w["f1"]))
                if not tech["valid"]:
                    self._store_result(w, {**rep, "valid": False, "acceptance": "rejected",
                                           "fatal_problems": tech["fatal_problems"],
                                           "problems": tech["problems"], "fix": "", "skipped": False})
                elif approved:
                    story = {k: v for k, v in approved.items() if k not in
                             ("window", "beat", "action", "part", "f0", "f1", "t0", "t1", "images", "technical")}
                    self._store_result(w, {**rep, **story, "valid": True, "preflight_approved": True,
                                           "problems": tech["problems"] + story.get("problems", [])})
                else:
                    ai_items.append((w, images))
            if self._abort.is_set() or not ai_items:
                return
            reviewed = review_batch(ai_items, self.subject)
            for w, _ in ai_items:
                _, rep, tech = prepared[w["window"]]
                story = reviewed[w["window"]]
                story["problems"] = tech["problems"] + story.get("problems", [])
                self._store_result(w, {**rep, **story})
                if self._abort.is_set():
                    return
        except Exception as exc:                     # noqa: BLE001
            if self._remember_usage_limit(exc):
                return
            for w in windows:
                key = (w["f0"], w["f1"])
                with self._lock:
                    done = key in self.results
                if not done:
                    self._store_result(w, {**{k: w[k] for k in
                                               ("window", "beat", "action", "part", "f0", "f1", "t0", "t1")},
                                           "valid": _env_flag("SCENE_ALLOW_QC_SKIP", "0"), "skipped": True,
                                           "reason": f"validator error: {exc}"})

    def _remember_usage_limit(self, exc):
        from agents.showrunner import UsageLimit
        text = str(exc).lower()
        if not (isinstance(exc, UsageLimit) or ("limit" in text and "reset" in text)):
            return False
        with self._lock:
            if self._fatal_error is None:
                self._fatal_error = exc if isinstance(exc, UsageLimit) else UsageLimit(str(exc))
        # A temporary reviewer quota is not a reason to throw away render time. Stop submitting
        # more reviews, let Blender finish writing frames, then surface the limit from finish().
        # Autopilot will wait for the reset and resume with those frames intact.
        self._stop.set()
        return True

    def _store_result(self, w, r):
        with self._lock:
            self.results[(w["f0"], w["f1"])] = r
            self._save_unlocked()
        verdict = "ACCEPTED" if r.get("valid") else "REJECTED"
        detail = "" if r.get("valid") else ": " + "; ".join((r.get("fatal_problems") or r.get("problems") or [])[:2])
        scores = "" if r.get("skipped") else f" (avg {r.get('average_score')})"
        log.info(f"[scenes] window {w['window']:02d} {w['t0']:5.1f}-{w['t1']:5.1f}s [{w['action']} {w['part']}] "
                 f"{verdict}{scores}{detail}")
        # policy "fix": keep rendering and reviewing so ONE repair turn receives every rejected
        # window. Aborting at the first rejection made each AI fix address a single window and then
        # re-render and re-review the whole film, multiplying AI cost by the number of bad windows.
        if not r.get("valid") and (self.policy == "stop"
                                   or (self.policy == "fix" and _env_flag("SCENE_FIX_ABORT_EARLY", "0"))):
            self._abort.set()

    def report(self) -> dict:
        with self._lock:
            rows = sorted(self.results.values(), key=lambda r: r["f0"])
        rejected = [r for r in rows if not r.get("valid")]
        return {"windows": rows, "rejected": rejected, "checked": len(rows), "planned": len(self.windows),
                "accepted": sum(1 for r in rows if r.get("valid")), "policy": self.policy,
                "complete": all((w["f0"], w["f1"]) in self.results for w in self.windows)}

    def _save(self):
        with self._lock:
            self._save_unlocked()

    def _save_unlocked(self):
        rows = sorted(self.results.values(), key=lambda r: r["f0"])
        tmp = self.report_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"film": self.film.get("title"), "policy": self.policy, "windows": rows}, fh, indent=1)
        os.replace(tmp, self.report_path)


def enabled(film: dict) -> bool:
    default = "1" if film.get("format") == "evolution" else "0"
    return bool(film.get("set")) and _env_flag("SCENE_VALIDATE", default)


# ------------------- CLI: re-check an existing render -------------------

def main():
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    from config.paths import PROJECT_ROOT
    from engine import sets
    ap = argparse.ArgumentParser(description="Validate the rendered frames of a film, window by window.")
    ap.add_argument("film", help="film name (engine/films/<name>.json) or path to a film JSON")
    a = ap.parse_args()
    path = a.film if a.film.endswith(".json") else os.path.join(PROJECT_ROOT, "engine", "films", f"{a.film}.json")
    name = os.path.splitext(os.path.basename(path))[0]
    film = json.load(open(path, encoding="utf-8"))
    work = os.path.join(PROJECT_ROOT, "output", f"{name}_work")
    timings = json.load(open(os.path.join(work, "timings.json"), encoding="utf-8"))
    w = SceneWatcher(film, timings["beats"], work, spec=sets.spec(film["set"]) if film.get("set") else None,
                     keep_previous=False)
    os.environ.setdefault("SCENE_POLICY", "report")
    w.policy = "report"
    w.start()
    rep = w.finish()
    print(f"{rep['accepted']}/{rep['planned']} windows accepted; report: {w.report_path}")
    for r in rep["rejected"]:
        print(f"  REJECTED window {r['window']:02d} {r['t0']:.1f}-{r['t1']:.1f}s [{r['action']}]: "
              f"{'; '.join(r.get('fatal_problems') or r.get('problems') or [])} | fix: {r.get('fix', '')}")


if __name__ == "__main__":
    main()
