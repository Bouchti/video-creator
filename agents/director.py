"""
Director route: a plan (engine/director/plans/*.json) -> a finished 60-65 s vertical short.

    python -m agents.director engine/director/plans/septic.json            # full film
    python -m agents.director engine/director/plans/septic.json --stills   # 2 preview stills per beat
    python -m agents.director PLAN --compose-only                          # redo audio + 2D layer only

Stages (each one resumes from its files in output/director/<plan id>/):
  1. voice    narration -> TTS, then FIT into the 60-65 s window (tail, then at most +-5 % tempo)
  2. timing   Whisper word times -> beat frame ranges + word cues for the world's animation
  3. animatic every frame at half resolution, then the gates: flicker, action visibility (measured in Blender),
              colourfulness, and a sound-off viewer review (clear? funny? incoherent?) -> qa_report.json
  3b. render  Blender (engine/director/blender_job.py): anchors.json + frames -> beauty.mp4
  4. sound    synced effects + generated music bed, ducked under the voice
  5. compose  Remotion (compositor/): captions, pinned labels, titles, checklist, end card
  6. check    duration strictly inside the window, 1080x1920, audio present
"""
import argparse
import glob
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time

from config.paths import COMPOSITOR, NPX, PROJECT_ROOT, get_blender
from agents.beats import _norm_words, script_word_timings
from agents.media import FFMPEG, get_duration, read_pcm, run, vertical_short_problems, write_wav

log = logging.getLogger("pipeline")
FPS = 30
WINDOW = (60.0, 65.0)          # the final video must be strictly inside this (seconds)
IDEAL = 62.5
TAIL = (1.0, 3.0)              # silence after the last word, for the end card to land
MAX_TEMPO = 0.05               # never change the speech rate by more than 5 %
BLENDER = get_blender()


# ------------------------------------------------------------------ helpers

def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def narration(plan):
    return " ".join(b["text"].strip() for b in plan["beats"])


def _key(word):
    return word.lower().strip(".,:;?!\"'()")


# ------------------------------------------------------------------ 1. voice

def fit_window(voice_seconds):
    """(tempo, tail) that put voice/tempo + tail strictly inside WINDOW, as close to IDEAL as allowed.
    tempo > 1 speeds the voice up. Returns tail None when even +-5 % cannot fit (script must change)."""
    lo, hi = WINDOW[0] + 0.3, WINDOW[1] - 0.3
    for tempo in (1.0,) + tuple(1 + s * k / 100 for k in range(1, 6) for s in (1, -1)):
        if abs(tempo - 1) > MAX_TEMPO + 1e-9:
            continue
        d = voice_seconds / tempo
        tail = min(TAIL[1], max(TAIL[0], IDEAL - d))
        if lo < d + tail < hi:
            return tempo, tail
    return None, None


VOICE_SR = 44100                    # narration is analysed and tightened at this rate
MIN_PAUSE, MAX_PAUSE = 0.22, 0.7    # a tightened pause never gets shorter than this


def pauses(x, sr, threshold_db=-38.0, min_len=0.2):
    """[(start, end)] seconds of silence runs longer than min_len (not counting the very start/end)."""
    import numpy as np
    hop = int(sr * 0.01)
    n = len(x) // hop
    rms = np.sqrt(np.mean(x[: n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    quiet = 20 * np.log10(rms) < threshold_db
    runs, i = [], 0
    while i < n:
        if quiet[i]:
            j = i
            while j < n and quiet[j]:
                j += 1
            if i > 0 and j < n and (j - i) * 0.01 >= min_len:
                runs.append((i * 0.01, j * 0.01))
            i = j
        else:
            i += 1
    return runs


def pause_cap(runs, seconds, target):
    """The longest pause that brings `seconds` down to `target` (clamped to MIN_PAUSE..MAX_PAUSE)."""
    lo, hi = MIN_PAUSE, MAX_PAUSE
    shrink = lambda cap: sum(max(0.0, (b - a) - cap) for a, b in runs)  # noqa: E731
    if seconds - shrink(hi) <= target:
        return hi                      # already short enough with only the longest pauses trimmed
    for _ in range(30):
        mid = (lo + hi) / 2
        if seconds - shrink(mid) > target:
            hi = mid
        else:
            lo = mid
    return max(MIN_PAUSE, hi)


def tighten(src, dst, cap):
    """Shorten every pause longer than `cap` to `cap` (keeping its two edges, 10 ms crossfades)."""
    import numpy as np
    sr = VOICE_SR
    x = read_pcm(src, sr)
    out, last, fade = [], 0, int(sr * 0.01)
    ramp = np.linspace(0, 1, fade)
    for a, b in pauses(x, sr):
        if b - a <= cap:
            continue
        keep = int(cap * sr / 2)
        i0, i1 = int(a * sr) + keep, int(b * sr) - keep
        head, tail = x[last:i0].copy(), x[i1:i1 + fade].copy()
        head[-fade:] = head[-fade:] * ramp[::-1] + tail * ramp
        out.append(head)
        last = i1 + fade
    out.append(x[last:])
    y = np.concatenate(out)
    return write_wav(dst, y, sr)


VOICE_FIT_ROUNDS = int(os.getenv("DIRECTOR_VOICE_FIT_ROUNDS", "2"))


def stage_voice(plan, work, attempt=0):
    text = narration(plan)
    # the ENGINE is part of the key: switching to another voice must record again, not reuse the old file
    engine = (os.getenv("VOICE_ENGINE") or "elevenlabs").strip().lower()
    digest = hashlib.sha1(f"{text}|{plan.get('voice')}|{engine}".encode()).hexdigest()[:10]
    found = glob.glob(os.path.join(work, f"voice_{digest}.*"))
    raw = found[0] if found else None
    if raw is None:
        from agents.voice import generate_voiceover
        path, _ = generate_voiceover(text, plan.get("voice", "energetic"))
        raw = os.path.join(work, f"voice_{digest}{os.path.splitext(path)[1] or '.mp3'}")
        shutil.copy(path, raw)
    # 1) tighten dead air just enough to aim at the window (natural: words keep their speed)
    sr = VOICE_SR
    x = read_pcm(raw, sr)
    runs = pauses(x, sr)
    cap = pause_cap(runs, len(x) / sr, IDEAL - 1.6)
    tight = tighten(raw, os.path.join(work, "voice_tight.wav"), cap)
    # 2) then tempo (<= 5 %) and the tail
    d = get_duration(tight)
    raw = tight
    from agents import stage_writer
    n_words = len(_norm_words(text))
    stage_writer.record_rate(n_words, d)          # the next script gets the right length for this voice
    tempo, tail = fit_window(d)
    if tempo is None and plan.get("world") == "stage" and attempt < VOICE_FIT_ROUNDS:
        # the film would leave the 60-65 s window: re-size the narration to what THIS voice needs and record
        # again (Chatterbox speaks ~25 % faster than the voice the first scripts were sized for)
        target = int(round(n_words * (IDEAL - 2.0) / d))
        log.warning("voice is %.1fs for %d words: re-sizing the narration to ~%d words and recording again",
                    d, n_words, target)
        new = stage_writer.resize(plan, target)
        if new is not plan:
            plan["beats"] = new["beats"]
            _save(os.path.join(work, "plan.json"), {k: v for k, v in plan.items() if k not in ("assets", "assets_for")})
            if os.path.isfile(os.path.join(work, "plan_resolved.json")):
                _save(os.path.join(work, "plan_resolved.json"), plan)
            return stage_voice(plan, work, attempt + 1)
    if tempo is None:
        # never stop the run: clamp the tempo to the limit and let the tail absorb what it can;
        # the check stage reports it, and the planner must shorten/lengthen the script next time
        tempo = 1 + MAX_TEMPO if d > IDEAL else 1 - MAX_TEMPO
        tail = min(TAIL[1], max(TAIL[0], IDEAL - d / tempo))
        log.warning("voice is %.1fs: outside what +-5%% tempo can fit; the script needs %s words", d,
                    "fewer" if d > IDEAL else "more")
    voice = os.path.join(work, "voice.wav")
    run([FFMPEG, "-y", "-v", "error", "-i", raw, "-filter:a", f"atempo={tempo:.4f}", "-ar", "44100", "-ac", "1",
          voice])
    d = get_duration(voice)
    info = {"tightened_seconds": round(get_duration(raw), 3), "pause_cap": round(cap, 3), "pauses": len(runs),
            "tempo": round(tempo, 4), "voice_seconds": round(d, 3),
            "tail": round(tail, 3), "total": round(d + tail, 3)}
    log.info("voice: %s", info)
    return voice, info


# ------------------------------------------------------------------ 2. timing

def stage_timing(plan, voice, total_seconds, work):
    path = os.path.join(work, "timing.json")
    words_path = os.path.join(work, "words.json")
    if os.path.isfile(words_path) and os.path.getmtime(words_path) > os.path.getmtime(voice):
        words = _load(words_path)
    else:
        from agents.transcription import transcribe_with_whisper
        heard = transcribe_with_whisper(voice)
        words = script_word_timings(plan["beats"], heard, total_seconds)
        _save(words_path, words)
    words = strictly_increasing(words)
    total = int(round(total_seconds * FPS))
    beats, i = [], 0
    for b in plan["beats"]:
        n = len([w for w in b["text"].split() if _norm_words(w)])
        mine = words[i:i + n]
        i += n
        cues = {}
        for w in mine:
            cues.setdefault(_key(w["text"]), int(round(w["start"] * FPS)) + 1)
        beats.append({"id": b["id"], "start": mine[0]["start"] if mine else 0.0, "cues": cues, "words": mine})
    for k, b in enumerate(beats):
        # each beat's picture starts a few frames before its first word (anticipation)
        b["f0"] = 1 if k == 0 else max(beats[k - 1]["f0"] + 12, int(round(b["start"] * FPS)) + 1 - 4)
    for k, b in enumerate(beats):
        b["f1"] = beats[k + 1]["f0"] - 1 if k + 1 < len(beats) else total
    timing = {"fps": FPS, "total": total, "beats": [{kk: b[kk] for kk in ("id", "f0", "f1", "cues")} for b in beats]}
    _save(path, timing)
    return timing, words


def strictly_increasing(words, gap=0.02):
    """Every word starts after the previous one (Whisper can give two words the same start time)."""
    out, last = [], -1.0
    for w in words:
        start = max(float(w["start"]), last + gap)
        out.append(dict(w, start=round(start, 3), end=round(max(float(w["end"]), start + gap), 3)))
        last = start
    return out


# ------------------------------------------------------------------ 3. render

def blender(job, work, name):
    path = os.path.join(work, f"{name}.json")
    _save(path, job)
    log_path = os.path.join(work, f"{name}.log")
    from local_video.queue import gpu_lock
    with gpu_lock(), open(log_path, "w", encoding="utf-8") as fh:
        r = subprocess.run([BLENDER, "-b", "--factory-startup", "--python",
                            os.path.join(PROJECT_ROOT, "engine", "director", "blender_job.py"), "--", path],
                           stdout=fh, stderr=subprocess.STDOUT)
    text = open(log_path, encoding="utf-8", errors="replace").read()
    if r.returncode != 0 or "Traceback" in text:
        raise RuntimeError(f"Blender failed (see {log_path}): {text[-1200:]}")


GROUND_LOOKS = {   # ground kind -> BlenderKit assetBaseId, chosen side by side from the free stylized materials
    # grass: none: the painted grass texture still read as ugly; grass is the stage's soft lawn + 3D blades
    "sand": "f9bc120c-5b02-4d17-9edb-86544b0eb513",           # Stylized Sand
    "gravel": "eb7e115a-cb91-4ee7-96c9-89b106c5c45d",         # Stylized Rock Pebble
    "dirt": "c2fdb05d-d991-450f-8b6b-7f4338be4c68",           # Stylized Dirt
    "snow": "10c9cbb4-7431-465c-915e-c708d740c4da",           # Stylized Snow 02
    "paving stones": "c9c6a0f3-4666-47ee-86ce-4b1610ab5ce6",  # Stylized paving
}                                                              # asphalt: the procedural one (no clean candidate)


def stage_assets(plan, work):
    """Data-driven worlds: every prop, the ground and the backdrop resolved to a downloaded BlenderKit asset
    (agents/blenderkit.py) BEFORE any render. A miss is fine: the world builds a clean fallback."""
    if plan.get("world") != "stage":
        return plan
    path = os.path.join(work, "plan_resolved.json")
    digest = hashlib.sha1(json.dumps(dict({k: plan.get(k) for k in ("place", "props")}, looks=GROUND_LOOKS),
                                     sort_keys=True).encode()).hexdigest()[:12]
    if os.path.isfile(path):
        cached = _load(path)
        if cached.get("assets_for") == digest:          # same props: keep the picks; new beats still apply
            return dict(plan, assets=cached["assets"], assets_for=digest)
    from agents import blenderkit
    assets = {}
    story = " ".join(b["text"] for b in plan["beats"])[:400]
    for p in plan.get("props", []):
        a = blenderkit.resolve(p["query"], "model", p.get("size_m"), story)
        if a:
            assets[p["id"]] = a
    if any(float(p.get("size_m") or 1) < 0.6 for p in plan.get("props", [])):     # see stage.SMALL
        a = blenderkit.resolve("wooden table", "model", 1.8, story)
        if a:
            assets["_worktable"] = a
    place = plan.get("place", {})
    # the ground: a hand-picked clean STYLIZED BlenderKit material per kind (photo scans looked like noisy carpet);
    # without it the stage's own procedural ground is used (engine/director/stage.GROUNDS)
    ground_id = GROUND_LOOKS.get(place.get("ground", "grass"))
    if ground_id:
        a = blenderkit.resolve_id(ground_id, "material", f"ground {place.get('ground', 'grass')}")
        if a:
            assets["_ground"] = a
    for q in place.get("backdrop", [])[:3]:
        a = blenderkit.resolve(q, "model", None, story)
        if a:
            dims = [d for d in (a.get("dimensions") or []) if d]
            assets[f"_backdrop_{q}"] = dict(a, size_m=max(dims) if dims else 6.0)
    missing = [p["id"] for p in plan.get("props", []) if p["id"] not in assets]
    if missing:
        log.warning("QUALITY WARNING: no BlenderKit asset for %s (clean fallback shapes)", ", ".join(missing))
    resolved = dict(plan, assets=assets, assets_for=digest)
    _save(path, resolved)
    return resolved


def _job(plan, timing, out, preview):
    job = {"world": plan["world"], "timing": timing, "out": out, "preview": preview}
    if plan.get("world") == "stage":
        job["plan"] = plan
    return job


def stage_render(plan, timing, work, stills=False):
    out = os.path.join(work, "render")
    job = _job(plan, timing, out, stills)
    if stills:
        frames = []
        for b in timing["beats"]:
            n = b["f1"] - b["f0"]
            frames += [b["f0"] + int(n * 0.3), b["f0"] + int(n * 0.8)]
        job["stills"] = frames
        blender(job, work, "stills")
        return None
    return _render_movie(job, out, os.path.join(work, "beauty.mp4"), work, "render", timing["total"], crf=14)


STAGE_CODE = ("engine/director/stage.py", "engine/director/lib.py", "engine/character.py", "engine/mocap.py",
              "engine/director/blender_job.py")
REVEAL = {"appear", "drop"}      # these events hide their prop from frame 1: they change every earlier beat
LASTING = {"appear", "vanish", "grow", "shrink", "rise", "drop", "slide", "tip_over"}   # change later beats too


def beat_keys(plan, timing, preview):
    """beat id -> fingerprint of everything that decides that beat's PICTURE. A beat whose key did not change
    since the last render is not rendered again. Characters carry their position from beat to beat, so a
    beat depends on the staging (cast, events) of every beat up to it, but only on its OWN shot; a prop that
    appears later is hidden from frame 1, so reveal events count everywhere. The stage code, the set
    (place, props, assets), the beat's frame range and the render quality count too."""
    code = hashlib.sha1()
    for rel in STAGE_CODE:
        try:
            with open(os.path.join(PROJECT_ROOT, rel), "rb") as fh:
                code.update(fh.read())
        except OSError:
            pass
    world = {k: plan.get(k) for k in ("world", "place", "props", "assets")}
    beats = {b["id"]: b for b in plan["beats"]}
    reveals = [[e for e in b.get("events", []) if e.get("does") in REVEAL] for b in plan["beats"]]
    keys, carried, last_act, prev = {}, [], {}, {}
    for b in timing["beats"]:
        pb = beats.get(b["id"], {})
        blob = json.dumps({"code": code.hexdigest(), "world": world, "reveals": reveals, "carried": carried,
                           "last_act": last_act, "prev_events": prev.get("events"),
                           "own": {"cast": pb.get("cast"), "events": pb.get("events"), "shot": pb.get("shot"),
                                   "cues": b.get("cues")},
                           "range": [b["f0"], b["f1"]], "preview": preview, "total": timing["total"]},
                          sort_keys=True, default=str)
        keys[b["id"]] = hashlib.sha1(blob.encode()).hexdigest()[:10]
        # what this beat leaves for the next ones: where people walked, lasting prop changes, the last action
        # each character is still playing (a clip runs on until that character's next cue)
        carried = carried + [{"moves": [(c.get("who"), c.get("to"), c.get("at")) for c in pb.get("cast", [])
                                        if c.get("to")],
                              "lasting": [e for e in pb.get("events", []) if e.get("does") in LASTING],
                              "cues": b.get("cues")}]
        for c in pb.get("cast", []):
            last_act = dict(last_act, **{c.get("who"): c})
        prev = pb
    return keys


def _render_beats(job, out, work, name, plan, timing):
    """Render only the beats whose picture changed (beat_keys) into out/beats/<beat>-<key>/, in ONE Blender run,
    then link every beat's frames into out/frames/ in order. Fixing one beat re-renders one beat."""
    keys = beat_keys(plan, timing, job.get("preview", False))
    segments = []
    for b in timing["beats"]:
        folder = os.path.join(out, "beats", f"{b['id']}-{keys[b['id']]}")
        n = b["f1"] - b["f0"] + 1
        done = [f for f in glob.glob(os.path.join(folder, "*.png")) if os.path.getsize(f) > 0]
        if len(done) < n:
            segments.append({"f0": b["f0"], "f1": b["f1"], "dir": folder})
    if segments:
        log.info("render: %d of %d beats changed (%s); the rest are reused", len(segments), len(timing["beats"]),
                 ", ".join(os.path.basename(s["dir"]) for s in segments))
        blender(dict(job, segments=segments), work, name)
    else:
        log.info("render: every beat is unchanged; nothing to render")
    frames_dir = os.path.join(out, "frames")
    os.makedirs(frames_dir, exist_ok=True)
    for old in glob.glob(os.path.join(frames_dir, "*.png")):
        os.remove(old)
    for b in timing["beats"]:
        folder = os.path.join(out, "beats", f"{b['id']}-{keys[b['id']]}")
        for f in range(b["f0"], b["f1"] + 1):
            src, dst = os.path.join(folder, f"{f:04d}.png"), os.path.join(frames_dir, f"{f:04d}.png")
            try:
                os.link(src, dst)                   # no copy: the beat folder keeps the only data
            except OSError:
                shutil.copy(src, dst)
    for folder in glob.glob(os.path.join(out, "beats", "*")):     # superseded versions of a beat
        bid, _, key = os.path.basename(folder).rpartition("-")
        if keys.get(bid) and keys[bid] != key:
            shutil.rmtree(folder, ignore_errors=True)


def _render_movie(job, out, movie, work, name, total, crf):
    if job.get("plan") and job["plan"].get("world") == "stage":
        _render_beats(job, out, work, name, job["plan"], job["timing"])
    frames = sorted(glob.glob(os.path.join(out, "frames", "*.png")))
    if len(frames) < total or not all(os.path.getsize(f) > 0 for f in frames):
        blender(job, work, name)
        frames = sorted(glob.glob(os.path.join(out, "frames", "*.png")))
    if not os.path.isfile(movie) or os.path.getmtime(movie) < max(os.path.getmtime(f) for f in frames):
        run([FFMPEG, "-y", "-v", "error", "-framerate", str(FPS), "-i", os.path.join(out, "frames", "%04d.png"),
              "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p", movie])
    return movie


# ------------------------------------------------------------------ 3b. animatic + gates (before the final)

HOOK_ROUNDS = int(os.getenv("DIRECTOR_HOOK_ROUNDS", "2"))     # automatic re-stagings of a hook that fails


def stage_animatic(plan, timing, work):
    """Every frame at half resolution (~20 min), then the measured gates and the viewer review run on it, so
    flicker, invisible actions, washed-out colour, confusion and incoherence are found BEFORE the 2 h final."""
    out = os.path.join(work, "animatic")
    for attempt in range(HOOK_ROUNDS + 1):
        job = _job(plan, timing, out, True)
        movie = _render_movie(job, out, os.path.join(work, "animatic.mp4"), work, "animatic", timing["total"],
                              crf=20)
        report = gates(plan, timing, out)
        try:
            report["viewer"] = viewer_review(plan, timing, work, movie)
        except Exception as exc:          # the review is advice; it never blocks the video
            report["viewer"] = {"error": str(exc)[:300]}
        hook = report["viewer"].get("hook") or {}
        if plan.get("world") != "stage" or hook.get("stops_scroll", True) or attempt == HOOK_ROUNDS:
            break
        # the hook does not stop the scroll: re-stage the FIRST beat only (same words, so voice and timing
        # stay); thanks to the per-beat render only the hook (and its spill into beat 2) renders again
        log.warning("QA: the hook would not stop a scroll (%s); re-staging it", hook.get("why", ""))
        from agents import stage_writer
        plan["beats"][0] = stage_writer.restage_hook(plan, hook.get("why", ""))
        _save(os.path.join(work, "plan_resolved.json"), plan)
        _save(os.path.join(work, "plan.json"), {k: v for k, v in plan.items() if k not in ("assets", "assets_for")})
    for c in report["viewer"].get("confusing") or []:          # the film must never confuse the viewer
        report["warnings"].append(f"clarity: {c}")
    if report["viewer"].get("beats") and not (report["viewer"].get("learned") or "").strip():
        report["warnings"].append("teach: the reviewer learned nothing new from the film")
    if plan.get("world") == "stage" and not (report["viewer"].get("hook") or {}).get("stops_scroll", True):
        report["warnings"].append(f"hook: still would not stop a scroll after {HOOK_ROUNDS} re-staging(s): "
                                  f"{report['viewer']['hook'].get('why', '')}")
    _save(os.path.join(work, "qa_report.json"), report)
    for w in report["warnings"] + [f"viewer: {b['id']}: {b['problem']}" for b in report["viewer"].get("beats", [])
                                   if b.get("problem")]:
        log.warning("QA: %s", w)
    return report


def gates(plan, timing, render_dir):
    """Deterministic checks on EVERY rendered frame + Blender's action and camera measurements."""
    from agents import frame_qa
    frames = sorted(glob.glob(os.path.join(render_dir, "frames", "*.png")))
    series = frame_qa.scan(frames)
    warnings, beats = [], {}
    for b in timing["beats"]:
        rows = [r for r in series if b["f0"] <= r[0] <= b["f1"]]
        strobing = [r for r in rows if r[1] > frame_qa.FLICKER_MAX]
        fast = [r for r in rows if r[2] > frame_qa.PAN_MAX]
        colour = [frame_qa.colorfulness(frames[i - 1]) for i in
                  (b["f0"] + int((b["f1"] - b["f0"]) * s) for s in (0.2, 0.5, 0.8)) if 0 < i <= len(frames)]
        light = [frame_qa.highlights(frames[i - 1]) for i in
                 (b["f0"] + int((b["f1"] - b["f0"]) * s) for s in (0.2, 0.5, 0.8)) if 0 < i <= len(frames)]
        row = {"strobe_frames": len(strobing), "worst_strobe": round(max([r[1] for r in rows] or [0]), 2),
               "highlights": round(min(light), 2) if light else 0.0,
               "fast_frames": len(fast), "worst_pan": round(max([r[2] for r in rows] or [0]), 4),
               "colorfulness": round(min(colour), 1) if colour else 0.0}
        if len(strobing) > 3:
            warnings.append(f"{b['id']}: {len(strobing)} frames strobe (worst {row['worst_strobe']}% at frame "
                            f"{max(strobing, key=lambda r: r[1])[0]})")
        if len(fast) > 3:
            warnings.append(f"{b['id']}: the picture moves too fast on {len(fast)} frames (worst "
                            f"{row['worst_pan'] * 100:.1f}% of the width per frame at frame "
                            f"{max(fast, key=lambda r: r[2])[0]})")
        if row["highlights"] < frame_qa.HIGHLIGHT_MIN:
            warnings.append(f"{b['id']}: flat, greyed picture: its brightest 2 % only reach {row['highlights']} "
                            f"(needs {frame_qa.HIGHLIGHT_MIN}); check the view transform and exposure")
        if row["colorfulness"] < frame_qa.COLORFUL_MIN:
            warnings.append(f"{b['id']}: washed-out colour (colourfulness {row['colorfulness']} < "
                            f"{frame_qa.COLORFUL_MIN})")
        beats[b["id"]] = row
    actions_path = os.path.join(render_dir, "actions.json")
    actions = _load(actions_path) if os.path.isfile(actions_path) else []
    for a in actions:
        if a["share"] < a["min_share"]:
            warnings.append(f"action '{a['name']}' is too small on screen ({a['share']:.3f} of the frame height, "
                            f"needs {a['min_share']})")
        if a["visible"] < 0.8:
            warnings.append(f"action '{a['name']}' is out of frame {100 - a['visible'] * 100:.0f}% of its time")
        if (a["f1"] - a["f0"]) < 18:
            warnings.append(f"action '{a['name']}' lasts {a['f1'] - a['f0']} frames; hold it >= 18 (0.6 s)")
    notes_path = os.path.join(render_dir, "camera_notes.json")
    for note in (_load(notes_path) if os.path.isfile(notes_path) else []):
        warnings.append(f"camera: {note}")
    return {"beats": beats, "actions": actions, "warnings": warnings}


VIEWER_SCHEMA = {"type": "object", "additionalProperties": False,
                 "required": ["beats", "overall", "hook", "learned", "confusing"],
                 "properties": {
    "overall": {"type": "string"},
    "learned": {"type": "string"},
    "confusing": {"type": "array", "items": {"type": "string"}},
    "hook": {"type": "object", "additionalProperties": False, "required": ["stops_scroll", "why"],
             "properties": {"stops_scroll": {"type": "boolean"}, "why": {"type": "string"}}},
    "beats": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["id", "what_happens", "clear", "funny", "incoherent", "problem"],
        "properties": {"id": {"type": "string"}, "what_happens": {"type": "string"}, "clear": {"type": "boolean"},
                       "funny": {"type": "integer"}, "incoherent": {"type": "string"},
                       "problem": {"type": "string"}}}}}}


def viewer_review(plan, timing, work, movie):
    """A sound-off, text-off first-time viewer: per beat, a strip of 4 frames. It says what it sees BEFORE it
    reads the intent, then: clear?, funny 1-5, anything physically incoherent, the single biggest problem."""
    from PIL import Image
    from agents import llm
    from engine.director.worlds import WORLDS
    spec = WORLDS.get(plan["world"]) or {"shots": {b["id"]: {"shows": b.get("shows", b["text"]), "gag": b["text"]}
                                                   for b in plan["beats"]}}
    # sample what MATTERS: the start, the peak of each registered action, the end (even shares missed
    # every chomp, bounce and landing)
    actions_path = os.path.join(work, "animatic", "actions.json")
    actions = _load(actions_path) if os.path.isfile(actions_path) else []
    sheets = []
    for b in timing["beats"]:
        tiles = []
        peaks = sorted({(a["f0"] + a["f1"]) // 2 for a in actions if b["f0"] < (a["f0"] + a["f1"]) // 2 < b["f1"]})
        if len(peaks) > 3:
            peaks = [peaks[0], peaks[len(peaks) // 2], peaks[-1]]
        frames = [b["f0"] + (b["f1"] - b["f0"]) * 0.08] + peaks + [b["f0"] + (b["f1"] - b["f0"]) * 0.92]
        while len(frames) < 4:
            frames.insert(1, b["f0"] + (b["f1"] - b["f0"]) * (0.3 + 0.3 * (len(frames) - 2)))
        if b is timing["beats"][0]:            # the hook is judged on what the FIRST SECOND shows
            frames = [b["f0"] + 15, b["f0"] + 30] + [x for x in frames if x > b["f0"] + 30][:2]
        frames = [int(round(x)) for x in frames]
        for share in sorted(frames):
            t = (share - 1) / FPS
            png = os.path.join(work, "review", f"{b['id']}_{share}.png")
            os.makedirs(os.path.dirname(png), exist_ok=True)
            run([FFMPEG, "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", movie, "-frames:v", "1", "-vf",
                  "scale=300:533", png])
            tiles.append(Image.open(png).convert("RGB"))
        sheet = Image.new("RGB", (310 * len(tiles), 533), "white")
        for i, im in enumerate(tiles):
            sheet.paste(im, (i * 310, 0))
        path = os.path.join(work, "review", f"{b['id']}.jpg")
        sheet.save(path, quality=88)
        sheets.append((b["id"], path))
    by_id = {b["id"]: b for b in plan["beats"]}

    def overlays(bid):
        """The explanation arrows and tags the 2D edit draws over the beat (not in these 3D frames yet)."""
        b = by_id.get(bid, {})
        bits = [f"arrow {a.get('dir')} over {a.get('prop')} '{a.get('text', '')}'" for a in b.get("arrows", [])]
        bits += [f"tag '{lb.get('text')}' on {lb.get('anchor')}" for lb in b.get("labels", [])]
        return f" (edit: {'; '.join(bits)})" if bits else ""
    intents = "\n".join(f"- {bid}: {spec['shots'][bid]['shows']} (gag: {spec['shots'][bid]['gag']}){overlays(bid)}"
                        for bid, _ in sheets)
    system = ("You are a 16-year-old scrolling TikTok with the SOUND OFF. Each image is one beat of a short animated "
              "film: its key moments left to right. For each beat FIRST write what_happens: what you actually see, in one "
              "sentence, without guessing. THEN read the intent. clear: would you get that idea from the picture "
              "alone? funny: 1 (not at all) to 5 (I'd send it to a friend). incoherent: anything physically wrong "
              "or contradictory (things popping in or out, objects passing through each other, a hole that "
              "disappears), or ''. problem: the single change that would help most, or ''. Be blunt. Anything marked "
              "(edit) in the intent is added later in the edit (text, rewind effect): do not judge its absence. "
              "hook: look ONLY at the first two pictures of the FIRST beat (its first second). stops_scroll: would "
              "that make you stop scrolling, because something surprising, spectacular or funny is visibly "
              "happening? A person standing or walking next to an object is NOT enough. why: one line. "
              "LAST, with the narration (given after the intent) as if the sound were on: learned = the new thing a "
              "12-year-old would now know, in one sentence ('' if nothing); confusing = every moment where the words "
              "and the pictures do not explain it simply, or do not match.")
    said = "\n".join(f"- {b['id']}: {b['text']}" for b in plan["beats"])
    return llm.ask(system, f"INTENT (read after describing):\n{intents}\n\nNARRATION (for learned / confusing):\n"
                         f"{said}", VIEWER_SCHEMA, images=sheets)


# ------------------------------------------------------------------ 4. sound

SOUNDS = {   # beat id -> [(sound, cue word or share of the beat, gain, duration share)]
    "hook": [("water_rush", 0.0, 0.6, 0.3), ("crack", 0.28, 1.0, 0), ("dump", 0.3, 0.8, 0), ("whoosh", 0.33, 0.9, 0)],
    "follow": [("rewind", 0.0, 0.9, 0), ("flop", 0.3, 0.8, 0), ("pour", 0.35, 0.5, 0.6)],
    "sort": [("splash", 0.03, 0.9, 0), ("bubbles", 0.1, 0.4, 0.7), ("underwater_thud", "heavy", 0.7, 0),
             ("boing", "greasy", 0.6, 0)],
    "baffle": [("boing", "tonight", 1.0, 0)],
    "field": [("pour", "seeps", 0.4, 0.4), ("pop", "microbes", 0.6, 0), ("pop", 0.7, 0.6, 0)],
    "die": [("splash", "wipes", 0.6, 0), ("water_rush", "escapes", 0.5, 0), ("boil", "swamp", 0.5, 0.3)],
    "float": [("engine", 0.0, 0.5, 0.25), ("pump", "pumps", 0.6, 0.25), ("thunder", "flood", 0.7, 0),
              ("rain", "flood", 0.5, 0.5), ("crack", "shoves", 1.0, 0), ("whoosh", 0.85, 0.9, 0)],
    "land": [("flop", "lands", 1.0, 0), ("boing", "ta-da", 0.8, 0), ("kids_cheer", "ta-da", 0.35, 0)],
}


def sound_events(plan, timing, work=None):
    """The septic world's hand-timed table; data-driven worlds: the plan's named sounds on their cue words +
    what the world itself emitted while animating (footsteps, pops, thuds: render/sound_events.json)."""
    events = []
    beats = {b["id"]: b for b in timing["beats"]}
    table = SOUNDS if plan.get("world") == "septic" else {}
    for pb in plan["beats"]:
        b = beats[pb["id"]]
        n = b["f1"] - b["f0"]
        for kind, at, gain, dur in table.get(pb["id"], []):
            f = b["cues"].get(_key(at), b["f0"] + int(n * 0.3)) if isinstance(at, str) else b["f0"] + int(n * at)
            events.append({"kind": kind, "frame": f, "gain": gain, "duration": int(n * dur)})
        for s in pb.get("sounds", []):
            f = b["cues"].get(_key(s.get("at", "")), b["f0"] + int(n * 0.2))
            events.append({"kind": s["name"], "frame": f, "gain": 1.0, "duration": 0})
    for sub in ("render", "animatic"):
        path = os.path.join(work or "", sub, "sound_events.json")
        if work and os.path.isfile(path):
            events += _load(path)
            break
    return events


def stage_sound(plan, timing, voice, total_seconds, work):
    from agents import sfx
    from agents.audio_fx import mix_audio
    fx = sfx.render_events(sound_events(plan, timing, work), FPS, total_seconds, os.path.join(work, "fx.wav"))
    track = music_track(plan)
    if track:
        music = track["path"]                 # mix_audio loops it to length and ducks it under the voice
        plan.setdefault("credits", [])
        if track["credit"] not in plan["credits"]:
            plan["credits"].append(track["credit"])
    else:                                     # no library on this machine: the generated bed
        music = os.path.join(work, "music.wav")
        bed = sfx.music(total_seconds + 0.5, bpm=112)
        write_wav(music, bed, sfx.SR)
    return mix_audio(voice, fx, os.path.join(work, "mix.m4a"), total_seconds, music=music)


MUSIC_DIR = os.path.join(PROJECT_ROOT, "assets", "cc0", "music", "incompetech")


def music_track(plan):
    """A real comedy track for the film (assets/fetch_music.py), the same one on every rerun of a plan;
    None when the music library is not downloaded."""
    try:
        rows = [r for r in _load(os.path.join(MUSIC_DIR, "catalog.json"))
                if os.path.isfile(os.path.join(MUSIC_DIR, r["file"]))]
    except (OSError, ValueError):
        return None
    if not rows:
        return None
    k = int(hashlib.sha1(plan["id"].encode()).hexdigest(), 16) % len(rows)
    return dict(rows[k], path=os.path.join(MUSIC_DIR, rows[k]["file"]))


# ------------------------------------------------------------------ 5. compose

GRADE = {"saturate": 1.05, "contrast": 1.04, "brightness": 1.0}   # the render is vivid now; just a touch


def props(plan, timing, words, anchors, total_frames):
    beats = {b["id"]: b for b in timing["beats"]}
    emphasis = {_key(w) for b in plan["beats"] for w in b.get("emphasis", [])}
    out = {"fps": FPS, "width": 1080, "height": 1920, "durationInFrames": total_frames,
           "video": "beauty.mp4", "audio": "mix.m4a", "grain": 0.03, "grade": GRADE, "anchors": anchors,
           "words": [{"text": w["text"], "startMs": int(w["start"] * 1000), "endMs": int(w["end"] * 1000),
                      "emphasis": _key(w["text"]) in emphasis} for w in words],
           "chapters": [], "labels": [], "arrows": [], "callouts": [], "punchIns": []}
    order = [b["id"] for b in timing["beats"]]
    for pb in plan["beats"]:
        b = beats[pb["id"]]
        f0, f1 = b["f0"], b["f1"]
        cue = lambda w, d=f0: b["cues"].get(_key(w), d)  # noqa: E731
        if pb.get("hook_text"):
            out["hook"] = {"text": pb["hook_text"], "from": 0, "to": f1}
        if pb.get("rewind"):
            prev = beats[order[order.index(pb["id"]) - 1]]
            out["rewind"] = {"from": f0, "to": f0 + 18, "sourceFrom": prev["f1"], "sourceTo": prev["f0"]}
        if pb.get("chapter"):
            out["chapters"].append({"text": pb["chapter"], "from": f0, "to": min(f1, f0 + 50)})
        labels = pb.get("labels", [])
        starts = [cue(lb["at"]) for lb in labels]
        for k, lb in enumerate(labels):   # at most two labels on screen: each yields to the one after next
            end = min(f1, starts[k + 2] - 1) if k + 2 < len(starts) else f1
            out["labels"].append({"text": lb["text"], "anchor": lb["anchor"], "from": starts[k], "to": end})
        arrows = pb.get("arrows", [])
        starts = [cue(a["at"]) for a in arrows]
        for k, a in enumerate(arrows):    # one explanation step at a time: each holds until the next one
            end = min(f1, starts[k + 1] - 1) if k + 1 < len(starts) else f1
            anchor = f"{a['prop']}.mid" if f"{a['prop']}.mid" in (anchors or {}) else a["prop"]
            out["arrows"].append({"anchor": anchor, "dir": a["dir"], "text": a.get("text", ""), "from": starts[k],
                                  "to": max(starts[k] + 30, end)})
        for c in pb.get("callouts", []):
            at = cue(c["at"])
            out["callouts"].append({"kind": c["kind"], "text": c["text"], "tone": c.get("tone"), "from": at,
                                    "to": min(f1, at + 55)})
            out["punchIns"].append({"from": max(f0, at - 2), "to": min(f1, at + 40), "scale": 1.12})
        if pb.get("checklist"):
            out["checklist"] = {"from": f0, "to": f1,
                                "items": [{"text": it["text"], "from": cue(it["at"])} for it in pb["checklist"]]}
        if pb.get("end_card"):
            out["endCard"] = {"text": pb["end_card"], "from": max(f0 + 18, f1 - 75), "to": total_frames}
    return out


def stage_compose(plan, timing, words, work, final):
    public = os.path.join(work, "public")
    os.makedirs(public, exist_ok=True)
    for f in ("beauty.mp4", "mix.m4a"):
        shutil.copy(os.path.join(work, f), os.path.join(public, f))
    anchors = _load(os.path.join(work, "render", "anchors.json"))
    p = props(plan, timing, words, anchors, timing["total"])
    path = os.path.join(work, "props.json")
    _save(path, p)
    run([NPX, "remotion", "render", "src/index.ts", "Short", final, f"--props={path}", f"--public-dir={public}",
          "--codec=h264", "--crf=20", "--audio-codec=aac", "--log=error"], cwd=COMPOSITOR, timeout=7200)
    return final


# ------------------------------------------------------------------ 6. check

def check(final):
    d, problems = vertical_short_problems(final, *WINDOW)
    if "no audio stream" not in problems:
        from agents.audio_fx import loudness, LOUDNESS_TARGET
        lufs = loudness(final)
        if abs(lufs - LOUDNESS_TARGET) > 2:
            problems.append(f"loudness {lufs:.1f} LUFS, platforms expect {LOUDNESS_TARGET:.0f} (sounds near-silent)")
    return d, problems


# ------------------------------------------------------------------ main

def fact_sheet(research, grounding=None):
    """The writer's only source of facts: the grounded claims, then the evidence snippets with their URLs."""
    lines = [f"- {c}" for c in (grounding or {}).get("kept") or []]
    for r in research or []:
        lines.append(f"- {r.get('title', '')}: {str(r.get('snippet') or r.get('content') or '')[:400]} "
                     f"({r.get('url', '')})")
    return "\n".join(lines)[:9000]


ASSET_ROUNDS = int(os.getenv("DIRECTOR_ASSET_ROUNDS", "2"))    # new searches for props with no 3D model


def make(topic, research, angle=None, grounding=None):
    """Autonomous route: topic + evidence -> stage plan (agents/stage_writer.py) -> finished film.
    Returns (final video path, plan). The plan is saved next to the work files for reruns."""
    from agents import stage_writer
    plan = stage_writer.write(topic, fact_sheet(research, grounding), angle)
    work = os.path.join(PROJECT_ROOT, "output", "director", plan["id"])
    os.makedirs(work, exist_ok=True)
    # props without a 3D model get new searches BEFORE anything is recorded or rendered (a plain cone called
    # "a spinning top" by the narration confused every viewer)
    for _ in range(ASSET_ROUNDS):
        missing = [p["id"] for p in plan.get("props", []) if p["id"] not in stage_assets(plan, work).get("assets", {})]
        if not missing:
            break
        again = stage_writer.replace_props(plan, missing)
        if again is plan:
            break
        plan = again
    _save(os.path.join(work, "plan.json"), plan)
    final = produce(plan)
    track = music_track(plan)
    plan["credits"] = [track["credit"]] if track else []     # agents/post_text.py prints them for the description
    return final, plan


def produce(plan_path, stills=False, compose_only=False, animatic_only=False, skip_animatic=False):
    plan = _load(plan_path) if isinstance(plan_path, str) else plan_path
    work = os.path.join(PROJECT_ROOT, "output", "director", plan["id"])
    os.makedirs(work, exist_ok=True)
    plan = stage_assets(plan, work)
    voice, info = stage_voice(plan, work)
    timing, words = stage_timing(plan, voice, info["total"], work)
    if stills:
        stage_render(plan, timing, work, stills=True)
        return os.path.join(work, "render")
    if not compose_only:
        if not skip_animatic:
            stage_animatic(plan, timing, work)
            if animatic_only:
                return os.path.join(work, "qa_report.json")
        stage_render(plan, timing, work)
    stage_sound(plan, timing, voice, info["total"], work)
    final = os.path.join(PROJECT_ROOT, "output", f"{time.strftime('%Y%m%d')}_{plan['id']}.mp4")
    stage_compose(plan, timing, words, work, final)
    d, problems = check(final)
    with open(final[:-4] + ".txt", "w", encoding="utf-8") as f:
        f.write(f"{plan['title']}\n\n{plan.get('caption', '')}\n\n{' '.join(plan.get('hashtags', []))}\n")
        for credit in plan.get("credits", []):            # CC BY music must be credited in the description
            f.write(f"\n{credit}\n")
    for p in problems:
        log.warning("QUALITY WARNING: %s", p)
    log.info("final: %s (%.2fs)", final, d)
    return final


def main():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--stills", action="store_true", help="voice + timing + 2 preview stills per beat")
    ap.add_argument("--animatic", action="store_true", help="stop after the animatic and its QA report")
    ap.add_argument("--skip-animatic", action="store_true")
    ap.add_argument("--compose-only", action="store_true", help="redo sound + 2D layer on the existing render")
    ap.add_argument("--rerender", default="", help="comma list of beat ids to render again even if unchanged")
    a = ap.parse_args()
    if a.rerender:                # drop those beats' frames: the next render makes them again, nothing else
        plan_id = _load(a.plan)["id"]
        for bid in [x.strip() for x in a.rerender.split(",") if x.strip()]:
            for sub in ("render", "animatic"):
                for folder in glob.glob(os.path.join(PROJECT_ROOT, "output", "director", plan_id, sub, "beats",
                                                     f"{bid}-*")):
                    shutil.rmtree(folder, ignore_errors=True)
    from agents.libraries import ensure
    ensure()                      # the asset libraries and the compositor, before anything else
    print(produce(a.plan, stills=a.stills, compose_only=a.compose_only, animatic_only=a.animatic,
                  skip_animatic=a.skip_animatic))


if __name__ == "__main__":
    sys.exit(main())
