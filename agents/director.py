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

from config.paths import PROJECT_ROOT
from agents.beats import _norm_words, script_word_timings
from agents.media import FFMPEG, get_duration

log = logging.getLogger("pipeline")
FPS = 30
WINDOW = (60.0, 65.0)          # the final video must be strictly inside this (seconds)
IDEAL = 62.5
TAIL = (1.0, 3.0)              # silence after the last word, for the end card to land
MAX_TEMPO = 0.05               # never change the speech rate by more than 5 %
BLENDER = os.getenv("BLENDER_EXE", r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe")
COMPOSITOR = os.path.join(PROJECT_ROOT, "compositor")
NPX = "npx.cmd" if os.name == "nt" else "npx"


# ------------------------------------------------------------------ helpers

def _run(cmd, **kw):
    kw.setdefault("text", True)
    r = subprocess.run(cmd, capture_output=True, **kw)
    if r.returncode != 0:
        err = r.stderr or r.stdout
        err = err.decode("utf-8", "replace") if isinstance(err, bytes) else err
        raise RuntimeError(f"{os.path.basename(str(cmd[0]))} failed: {err[-1500:]}")
    return r


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


MIN_PAUSE, MAX_PAUSE = 0.22, 0.7    # a tightened pause never gets shorter than this


def _pcm(path, sr=44100):
    import numpy as np
    raw = _run([FFMPEG, "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
               text=False).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768, sr


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
    import wave
    x, sr = _pcm(src)
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
    with wave.open(dst, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())
    return dst


def stage_voice(plan, work):
    text = narration(plan)
    digest = hashlib.sha1(f"{text}|{plan.get('voice')}".encode()).hexdigest()[:10]
    raw = os.path.join(work, f"voice_{digest}.mp3")
    if not os.path.isfile(raw):
        from agents.voice import generate_voiceover
        path, _ = generate_voiceover(text, plan.get("voice", "energetic"))
        shutil.copy(path, raw)
    # 1) tighten dead air just enough to aim at the window (natural: words keep their speed)
    x, sr = _pcm(raw)
    runs = pauses(x, sr)
    cap = pause_cap(runs, len(x) / sr, IDEAL - 1.6)
    tight = tighten(raw, os.path.join(work, "voice_tight.wav"), cap)
    # 2) then tempo (<= 5 %) and the tail
    d = get_duration(tight)
    raw = tight
    tempo, tail = fit_window(d)
    if tempo is None:
        # never stop the run: clamp the tempo to the limit and let the tail absorb what it can;
        # the check stage reports it, and the planner must shorten/lengthen the script next time
        tempo = 1 + MAX_TEMPO if d > IDEAL else 1 - MAX_TEMPO
        tail = min(TAIL[1], max(TAIL[0], IDEAL - d / tempo))
        log.warning("voice is %.1fs: outside what +-5%% tempo can fit; the script needs %s words", d,
                    "fewer" if d > IDEAL else "more")
    voice = os.path.join(work, "voice.wav")
    _run([FFMPEG, "-y", "-v", "error", "-i", raw, "-filter:a", f"atempo={tempo:.4f}", "-ar", "44100", "-ac", "1",
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


# ------------------------------------------------------------------ 3. render

def _gpu_lock():
    """The shared GPU lock (local_video): wait while another run owns it, never fail."""
    from pathlib import Path
    from local_video.queue import FileLock, QueueBusyError
    root = Path(os.getenv("LOCAL_VIDEO_OUTPUT_DIR") or Path(PROJECT_ROOT) / "output" / "projects")
    lock = FileLock(root / ".gpu-generation.lock")
    while True:
        try:
            return lock.__enter__() and lock
        except QueueBusyError as exc:
            log.info("GPU busy (%s); waiting", exc)
            time.sleep(60)


def blender(job, work, name):
    path = os.path.join(work, f"{name}.json")
    _save(path, job)
    log_path = os.path.join(work, f"{name}.log")
    lock = _gpu_lock()
    try:
        with open(log_path, "w", encoding="utf-8") as fh:
            r = subprocess.run([BLENDER, "-b", "--factory-startup", "--python",
                                os.path.join(PROJECT_ROOT, "engine", "director", "blender_job.py"), "--", path],
                               stdout=fh, stderr=subprocess.STDOUT)
    finally:
        lock.__exit__(None, None, None)
    text = open(log_path, encoding="utf-8", errors="replace").read()
    if r.returncode != 0 or "Traceback" in text:
        raise RuntimeError(f"Blender failed (see {log_path}): {text[-1200:]}")


def stage_render(plan, timing, work, stills=False):
    out = os.path.join(work, "render")
    job = {"world": plan["world"], "timing": timing, "out": out, "preview": stills}
    if stills:
        frames = []
        for b in timing["beats"]:
            n = b["f1"] - b["f0"]
            frames += [b["f0"] + int(n * 0.3), b["f0"] + int(n * 0.8)]
        job["stills"] = frames
        blender(job, work, "stills")
        return None
    return _render_movie(job, out, os.path.join(work, "beauty.mp4"), work, "render", timing["total"], crf=14)


def _render_movie(job, out, movie, work, name, total, crf):
    frames = sorted(glob.glob(os.path.join(out, "frames", "*.png")))
    if len(frames) < total or not all(os.path.getsize(f) > 0 for f in frames):
        blender(job, work, name)
        frames = sorted(glob.glob(os.path.join(out, "frames", "*.png")))
    if not os.path.isfile(movie) or os.path.getmtime(movie) < max(os.path.getmtime(f) for f in frames):
        _run([FFMPEG, "-y", "-v", "error", "-framerate", str(FPS), "-i", os.path.join(out, "frames", "%04d.png"),
              "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p", movie])
    return movie


# ------------------------------------------------------------------ 3b. animatic + gates (before the final)

def stage_animatic(plan, timing, work):
    """Every frame at half resolution (~20 min), then the measured gates and the viewer review run on it, so
    flicker, invisible actions, washed-out colour, confusion and incoherence are found BEFORE the 2 h final."""
    out = os.path.join(work, "animatic")
    job = {"world": plan["world"], "timing": timing, "out": out, "preview": True}
    movie = _render_movie(job, out, os.path.join(work, "animatic.mp4"), work, "animatic", timing["total"], crf=20)
    report = gates(plan, timing, out)
    try:
        report["viewer"] = viewer_review(plan, timing, work, movie)
    except Exception as exc:          # the review is advice; it never blocks the video
        report["viewer"] = {"error": str(exc)[:300]}
    _save(os.path.join(work, "qa_report.json"), report)
    for w in report["warnings"] + [f"viewer: {b['id']}: {b['problem']}" for b in report["viewer"].get("beats", [])
                                   if b.get("problem")]:
        log.warning("QA: %s", w)
    return report


def gates(plan, timing, render_dir):
    """Deterministic checks on rendered frames + Blender's action measurements. Returns warnings per beat."""
    from agents import frame_qa
    frames = sorted(glob.glob(os.path.join(render_dir, "frames", "*.png")))
    warnings, beats = [], {}
    for b in timing["beats"]:
        n = b["f1"] - b["f0"]
        row = {"flicker": 0.0, "colorfulness": [], "pan": 0.0}
        for share in (0.2, 0.5, 0.8):
            i = b["f0"] + int(n * share) - 1
            window = frames[max(0, i - 2): i + 3]
            if len(window) >= 3:
                fl = frame_qa.flicker(window)
                if fl > row["flicker"]:
                    row["flicker"], row["flicker_where"] = fl, frame_qa.flicker_map(window)
                row["pan"] = max(row["pan"], frame_qa.pan_speed(window))
            if 0 <= i < len(frames):
                row["colorfulness"].append(frame_qa.colorfulness(frames[i]))
        row["colorfulness"] = round(min(row["colorfulness"]), 1) if row["colorfulness"] else 0.0
        row["flicker"] = round(row["flicker"], 2)
        if row["flicker"] > frame_qa.FLICKER_MAX:
            warnings.append(f"{b['id']}: {row['flicker']}% of pixels strobe ({row['flicker_where']} of the frame)")
        row["pan"] = round(row["pan"], 4)
        if row["pan"] > frame_qa.PAN_MAX:
            warnings.append(f"{b['id']}: the camera moves {row['pan'] * 100:.1f}% of the frame width per frame "
                            f"(max {frame_qa.PAN_MAX * 100:.1f}%): it stutters; slow it, widen it, or cut")
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
    return {"beats": beats, "actions": actions, "warnings": warnings}


VIEWER_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["beats", "overall"], "properties": {
    "overall": {"type": "string"},
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
    from agents import ai_router
    from engine.director.worlds import WORLDS
    spec = WORLDS[plan["world"]]
    sheets = []
    for b in timing["beats"]:
        tiles = []
        for share in (0.1, 0.37, 0.63, 0.9):
            t = (b["f0"] + (b["f1"] - b["f0"]) * share - 1) / FPS
            png = os.path.join(work, "review", f"{b['id']}_{share}.png")
            os.makedirs(os.path.dirname(png), exist_ok=True)
            _run([FFMPEG, "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", movie, "-frames:v", "1", "-vf",
                  "scale=300:533", png])
            tiles.append(Image.open(png).convert("RGB"))
        sheet = Image.new("RGB", (300 * 4 + 30, 533), "white")
        for i, im in enumerate(tiles):
            sheet.paste(im, (i * 310, 0))
        path = os.path.join(work, "review", f"{b['id']}.jpg")
        sheet.save(path, quality=88)
        sheets.append((b["id"], path))
    intents = "\n".join(f"- {bid}: {spec['shots'][bid]['shows']} (gag: {spec['shots'][bid]['gag']})"
                        for bid, _ in sheets)
    system = ("You are a 16-year-old scrolling TikTok with the SOUND OFF. Each image is one beat of a short animated "
              "film: 4 moments left to right. For each beat FIRST write what_happens: what you actually see, in one "
              "sentence, without guessing. THEN read the intent. clear: would you get that idea from the picture "
              "alone? funny: 1 (not at all) to 5 (I'd send it to a friend). incoherent: anything physically wrong "
              "or contradictory (things popping in or out, objects passing through each other, a hole that "
              "disappears), or ''. problem: the single change that would help most, or ''. Be blunt. Anything marked "
              "(edit) in the intent is added later in the edit (text, rewind effect): do not judge its absence.")
    return ai_router.ask(system, f"INTENT (read after describing):\n{intents}", VIEWER_SCHEMA, images=sheets)


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


def sound_events(plan, timing):
    events = []
    beats = {b["id"]: b for b in timing["beats"]}
    for pb in plan["beats"]:
        b = beats[pb["id"]]
        n = b["f1"] - b["f0"]
        for kind, at, gain, dur in SOUNDS.get(pb["id"], []):
            f = b["cues"].get(_key(at), b["f0"] + int(n * 0.3)) if isinstance(at, str) else b["f0"] + int(n * at)
            events.append({"kind": kind, "frame": f, "gain": gain, "duration": int(n * dur)})
    return events


def stage_sound(plan, timing, voice, total_seconds, work):
    from agents import sfx
    from agents.audio_fx import mix_audio
    import numpy as np
    import wave
    fx = sfx.render_events(sound_events(plan, timing), FPS, total_seconds, os.path.join(work, "fx.wav"))
    music = os.path.join(work, "music.wav")
    bed = sfx.music(total_seconds + 0.5, bpm=112)
    with wave.open(music, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sfx.SR)
        w.writeframes((np.clip(bed, -1, 1) * 32767).astype(np.int16).tobytes())
    return mix_audio(voice, fx, os.path.join(work, "mix.m4a"), total_seconds, music=music)


# ------------------------------------------------------------------ 5. compose

GRADE = {"saturate": 1.15, "contrast": 1.06, "brightness": 1.02}


def props(plan, timing, words, anchors, total_frames):
    beats = {b["id"]: b for b in timing["beats"]}
    emphasis = {_key(w) for b in plan["beats"] for w in b.get("emphasis", [])}
    out = {"fps": FPS, "width": 1080, "height": 1920, "durationInFrames": total_frames,
           "video": "beauty.mp4", "audio": "mix.m4a", "grain": 0.03, "grade": GRADE, "anchors": anchors,
           "words": [{"text": w["text"], "startMs": int(w["start"] * 1000), "endMs": int(w["end"] * 1000),
                      "emphasis": _key(w["text"]) in emphasis} for w in words],
           "chapters": [], "labels": [], "callouts": [], "punchIns": []}
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
    _run([NPX, "remotion", "render", "src/index.ts", "Short", final, f"--props={path}", f"--public-dir={public}",
          "--codec=h264", "--crf=20", "--audio-codec=aac", "--log=error"], cwd=COMPOSITOR, timeout=7200)
    return final


# ------------------------------------------------------------------ 6. check

def check(final):
    probe = json.loads(_run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height",
                             "-of", "json", final]).stdout)
    d = float(probe["format"]["duration"])
    v = next(s for s in probe["streams"] if s["codec_type"] == "video")
    problems = []
    if not WINDOW[0] < d < WINDOW[1]:
        problems.append(f"duration {d:.2f}s is outside {WINDOW}")
    if (v["width"], v["height"]) != (1080, 1920):
        problems.append(f"video is {v['width']}x{v['height']}")
    if not any(s["codec_type"] == "audio" for s in probe["streams"]):
        problems.append("no audio")
    return d, problems


# ------------------------------------------------------------------ main

def produce(plan_path, stills=False, compose_only=False, animatic_only=False, skip_animatic=False):
    plan = _load(plan_path)
    work = os.path.join(PROJECT_ROOT, "output", "director", plan["id"])
    os.makedirs(work, exist_ok=True)
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
    a = ap.parse_args()
    from agents.libraries import ensure
    ensure()                      # the asset libraries and the compositor, before anything else
    print(produce(a.plan, stills=a.stills, compose_only=a.compose_only, animatic_only=a.animatic,
                  skip_animatic=a.skip_animatic))


if __name__ == "__main__":
    sys.exit(main())
