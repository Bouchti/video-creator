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
               fix            stop, let Claude fix the set's code (agents/set_builder.fix_scenes), resume
               report         render everything, then fail with the list of rejected windows
               warn           render everything, log rejections, assemble the video anyway
  SCENE_WINDOW_SECONDS=3      window length
  SCENE_MIN_SCORE=6           acceptance threshold (1-10)
  SCENE_FIX_ATTEMPTS=2        auto-fix rounds per render (policy "fix")
  SCENE_REVIEW_BACKEND        "subscription" (claude -p, default = SHOWRUNNER_BACKEND) or "api"

Re-check an existing render without rendering:  python -m agents.scene_validator <film name or JSON>
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
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
REVIEW_W = 432                                   # judged frames are saved at this width (9:16)


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
Do NOT call stylised low-poly trees, simple models, missing fine detail, motion blur, depth of field or
a camera angle you would have chosen differently fatal. Line drawings in white/orange are intentional.
fix: one concrete instruction for the 3D set's code (camera position/aim, object placement, timing),
empty if nothing to fix."""


def _jpeg(path, width=REVIEW_W):
    im = Image.open(path).convert("RGB")
    h = int(im.height * width / im.width)
    im = im.resize((width, h), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=84)
    return buf.getvalue()


def _backend():
    return os.getenv("SCENE_REVIEW_BACKEND") or os.getenv("SHOWRUNNER_BACKEND", "subscription")


def _review_api(prompt, images):
    import anthropic
    content = []
    for label, p in images:
        content += [{"type": "text", "text": label + ":"},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                 "data": base64.b64encode(open(p, "rb").read()).decode()}}]
    content.append({"type": "text", "text": prompt})
    tool = {"name": "submit_scene_review", "description": "Submit the review of this render window.",
            "input_schema": REVIEW_SCHEMA}
    model = os.getenv("SCENE_REVIEW_MODEL") or os.getenv("VISION_MODEL") or "claude-opus-5-5"
    resp = anthropic.Anthropic().messages.create(model=model, max_tokens=900, tools=[tool],
                                                 tool_choice={"type": "tool", "name": tool["name"]},
                                                 messages=[{"role": "user", "content": content}])
    for b in resp.content:
        if getattr(b, "type", None) == "tool_use":
            return dict(b.input)
    raise RuntimeError("no structured review returned")


def _review_cli(prompt, images):
    """claude -p on the Claude subscription: the images are copied into a temp dir and read with
    the Read tool (API credentials stripped, like the showrunner's subscription backend)."""
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("Claude Code CLI not found")
    from agents.showrunner import _API_ENV, CLI_MODEL
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
               "--effort", "medium", "--no-session-persistence", "--strict-mcp-config", "--setting-sources", "",
               "--tools", "Read", "--allowedTools", "Read", "--json-schema", json.dumps(REVIEW_SCHEMA)]
        r = subprocess.run(cmd, input=full, capture_output=True, text=True, encoding="utf-8", cwd=tmp, env=env,
                           timeout=600)
    data = json.loads(r.stdout)
    if data.get("is_error") or data.get("subtype") != "success":
        raise RuntimeError(f"claude -p: {str(data.get('result'))[:200]}")
    out = data.get("structured_output")
    return out if out is not None else json.loads(data["result"])


def judge(values: dict, threshold: int = None) -> dict:
    """Acceptance rule (mirrors local_video/visual_review.py): no fatal problem, and every score at the
    threshold, or a quality floor (visual_match and readability at most 1 below, average at it)."""
    threshold = threshold or min_score()
    scores = {k: int(values.get(k, 0)) for k in SCORES}
    fatal = [str(x) for x in values.get("fatal_problems", []) if x]
    avg = sum(scores.values()) / len(scores)
    strict = all(v >= threshold for v in scores.values())
    floor = (scores["visual_match"] >= threshold - 1 and scores["readability"] >= threshold - 1
             and scores["image_quality"] >= threshold and avg >= threshold)
    valid = not fatal and (strict or floor)
    return {"valid": valid, "acceptance": "strict" if strict and valid else "quality-floor" if valid else "rejected",
            "average_score": round(avg, 2), "threshold": threshold, **scores, "fatal_problems": fatal,
            "problems": [str(x) for x in values.get("problems", []) if x], "fix": str(values.get("fix") or "")}


def review_images(w: dict, images: list, subject: str, previous: str = None) -> dict:
    """Story review of one window. Service failures reject unless explicitly overridden."""
    if not _env_flag("SCENE_VISION", "1"):
        return {"valid": _env_flag("SCENE_ALLOW_QC_SKIP", "0"), "skipped": True,
                "reason": "vision review disabled (SCENE_VISION=0)"}
    prompt = _instructions(w, subject, previous)
    imgs = ([("previous window end frame", previous)] if previous else []) + images
    try:
        values = _review_api(prompt, imgs) if _backend() == "api" else _review_cli(prompt, imgs)
    except Exception as exc:                         # noqa: BLE001
        log.warning(f"[scenes] vision review unavailable for window {w['window']} ({str(exc)[:120]}); "
                    "technical QC only")
        return {"valid": _env_flag("SCENE_ALLOW_QC_SKIP", "0"), "skipped": True,
                "reason": f"vision review unavailable: {exc.__class__.__name__}"}
    return {**judge(values), "skipped": False}


def validate_window(w: dict, frames_dir: str, review_dir: str, subject: str, previous: str = None) -> dict:
    os.makedirs(review_dir, exist_ok=True)
    n = w["f1"] - w["f0"]
    picks = [("start", w["f0"] + max(1, n // 10)), ("middle", w["f0"] + n // 2), ("end", w["f1"] - max(1, n // 10))]
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

    def __init__(self, film: dict, spans: list, work: str, spec=None, only_frames=None, keep_previous=True):
        self.film, self.work = film, work
        self.frames_dir = os.path.join(work, "frames")
        self.review_dir = os.path.join(work, "review")
        self.report_path = os.path.join(work, "scene_review.json")
        self.subject = (getattr(spec, "SUBJECT", "") + " | " + film.get("title", "")).strip(" |")
        self.windows = plan_windows(film, spans, spec=spec)
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
        self._pool = ThreadPoolExecutor(max_workers=int(os.getenv("SCENE_REVIEW_WORKERS", "2")))
        self._submitted = set(self.results)          # kept verdicts are not checked again
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
        while time.time() - t0 < timeout and not self._abort.is_set():
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
        return self.report()

    # -- internals --
    def _loop(self):
        while not self._stop.is_set():
            for w in self.windows:
                key = (w["f0"], w["f1"])
                if key in self._submitted:
                    continue
                if window_ready(w, self.frames_dir, settle=0.5 if self._render_done.is_set() else 2.0):
                    self._submitted.add(key)
                    self._pool.submit(self._check, w)
            if self._abort.is_set():
                return
            time.sleep(2.0)

    def _previous_frame(self, w):
        prev = [r for r in self.results.values() if r["f1"] == w["f0"] - 1 and r.get("images")]
        return prev[0]["images"][-1] if prev else None

    def _check(self, w):
        try:
            r = validate_window(w, self.frames_dir, self.review_dir, self.subject, self._previous_frame(w))
        except Exception as exc:                     # noqa: BLE001
            r = {**{k: w[k] for k in ("window", "beat", "action", "part", "f0", "f1", "t0", "t1")},
                 "valid": _env_flag("SCENE_ALLOW_QC_SKIP", "0"), "skipped": True,
                 "reason": f"validator error: {exc}"}
        with self._lock:
            self.results[(w["f0"], w["f1"])] = r
            self._save()
        verdict = "ACCEPTED" if r.get("valid") else "REJECTED"
        detail = "" if r.get("valid") else ": " + "; ".join((r.get("fatal_problems") or r.get("problems") or [])[:2])
        scores = "" if r.get("skipped") else f" (avg {r.get('average_score')})"
        log.info(f"[scenes] window {w['window']:02d} {w['t0']:5.1f}-{w['t1']:5.1f}s [{w['action']} {w['part']}] "
                 f"{verdict}{scores}{detail}")
        if not r.get("valid") and self.policy in ("stop", "fix"):
            self._abort.set()

    def report(self) -> dict:
        with self._lock:
            rows = sorted(self.results.values(), key=lambda r: r["f0"])
        rejected = [r for r in rows if not r.get("valid")]
        return {"windows": rows, "rejected": rejected, "checked": len(rows), "planned": len(self.windows),
                "accepted": sum(1 for r in rows if r.get("valid")), "policy": self.policy,
                "complete": all((w["f0"], w["f1"]) in self.results for w in self.windows)}

    def _save(self):
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
