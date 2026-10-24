"""
Film production driver (runs in the project venv):

  python -m engine.make_film pool [--reuse-voice] [--preview | --frames=450,470]

voiceover → word timings + lip-sync envelope → Blender render timed to the words
→ overlay stickers → sound design (cut whooshes, synced SFX, ambience, music)
→ TikTok captions → output/<film>.mp4 (AAC, for TikTok) + <film>_preview.mp4
(Opus audio, which also plays inside VS Code's built-in player).
"""
import argparse
import glob
import json
import logging
import os
import shutil
import subprocess
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from config.paths import PROJECT_ROOT, get_output_dir  # noqa: E402
from agents.beats import align_beats, script_word_timings, FPS  # noqa: E402
from agents.editor_hailuo import (FFMPEG, generate_voiceover, get_duration,  # noqa: E402
                                  transcribe_with_whisper, merge_audio_video, burn_subtitles)
from agents.audio_fx import build_fx_track, mix_audio, SR  # noqa: E402
from agents.captions import words_to_ass  # noqa: E402
from agents.animate import _draw_overlay  # noqa: E402
from agents import sfx  # noqa: E402

log = logging.getLogger("pipeline")
BLENDER = os.getenv("BLENDER_EXE", r"C:\blender-5.2.3-windows-x64\blender.exe")


def voice_envelope(path: str, frames: int) -> list:
    """Per-frame loudness (0..1) of the voiceover — drives lip-sync."""
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", path, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    hop = 16000 / FPS
    rms = np.zeros(frames)
    for i in range(frames):
        chunk = x[int(i * hop):int((i + 1) * hop)]
        rms[i] = np.sqrt(np.mean(chunk ** 2)) if len(chunk) else 0.0   # silence after the voice ends
    ref = np.percentile(rms, 95) or 1.0
    env = np.clip(rms / ref, 0, 1)
    env = np.convolve(env, [0.25, 0.5, 0.25], mode="same")
    return [round(float(v), 3) for v in env]


def _read_wav(path):
    with wave.open(path) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def _write_wav(path, x):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    return path


def _sticker_job(job):
    path, overlay, t = job
    _draw_overlay(Image.open(path).convert("RGB"), overlay, t).save(path)


def _render_parallel(cmd, spans, total, n, work, start=None, hook=True):
    """Render the film with n Blender processes at once, each on a contiguous chunk of frames
    (worker 0 also renders the hook). A single process leaves the GPU idle while it updates the
    scene and writes each PNG; parallel workers fill those gaps. Frames are deterministic, so the
    result is identical to a single-process render."""
    with_hook = hook
    hook = (spans[0]["end"] - spans[0]["start"] + 1) if with_hook else 0
    build0 = start or spans[2]["start"] + 1            # first frame after hook + rewind (1-based)
    share = (total - build0 + 1 + hook) / n
    chunks, a = [], build0
    for k in range(n):
        size = round(share - (hook if k == 0 else 0))
        b = total if k == n - 1 else min(total, a + max(0, size) - 1)
        chunks.append((a, b))
        a = b + 1
    procs = []
    for k, (a, b) in enumerate(chunks):
        logf = open(os.path.join(work, f"render_worker{k}.log"), "w", encoding="utf-8")
        extra = [f"--range={a}:{b}"] + (["--hook"] if k == 0 and with_hook else [])
        procs.append((subprocess.Popen(cmd + extra, stdout=logf, stderr=subprocess.STDOUT, text=True), logf, k))
        log.info(f"  worker {k}: frames {a}-{b}" + (" + hook" if k == 0 and with_hook else ""))
    failed = []
    for p, logf, k in procs:
        p.wait()
        logf.close()
        out = open(logf.name, encoding="utf-8", errors="replace").read()
        if "DONE" not in out:
            failed.append(f"worker {k}:\n{out[-2000:]}")
    if failed:
        raise RuntimeError("Blender failed:\n" + "\n".join(failed))


def _overlay(beat):
    """2D sticker for a beat: `overlay`, or the first 2D-type entry of a structured `callouts`
    list (stat / label). 3D callouts (label3d, dimension) are drawn in the scene instead."""
    if beat.get("overlay"):
        return beat["overlay"]
    for c in beat.get("callouts", []):
        if c.get("type") in ("stat", "label"):
            return c
    return None


def _frame(frames_dir, i):
    """Path of 0-based video frame i."""
    return os.path.join(frames_dir, f"f_{i + 1:04d}.png")


def _zoom(img, z):
    w, h = img.size
    cw, ch = int(w / z), int(h / z)
    x0, y0 = (w - cw) // 2, (h - ch) // 2
    return img.crop((x0, y0, x0 + cw, y0 + ch)).resize((w, h), Image.LANCZOS)


def _vhs(img, k, rng):
    """Rewind look: RGB split, a few tracking-noise bands, cool tint, and a ◀◀ glyph."""
    a = np.asarray(img).astype(np.int16)
    out = a.copy()
    out[..., 0] = np.roll(a[..., 0], 9, axis=1)
    out[..., 2] = np.roll(a[..., 2], -9, axis=1)
    h = a.shape[0]
    for _ in range(3):
        y = int(rng.integers(0, h - 40))
        band = int(rng.integers(8, 34))
        out[y:y + band] = np.roll(out[y:y + band], int(rng.integers(-60, 60)), axis=1) + 40
    out = np.clip(out * [0.92, 0.97, 1.08] + 8, 0, 255).astype(np.uint8)
    im = Image.fromarray(out)
    d = ImageDraw.Draw(im)
    if (k // 6) % 2 == 0:                                  # blinking ◀◀, like a VCR
        x, y, s_ = 70, 170, 64
        for dx in (0, s_):
            tri = [(x + dx + s_, y), (x + dx, y + s_), (x + dx + s_, y + 2 * s_)]
            d.polygon(tri, fill=(255, 255, 255), outline=(20, 20, 30))
    return im


def _beat_ids(beats):
    """Beat ids, with the hook / rewind beats identified by their `video` role (data-driven films
    name beats after their action, e.g. "float_hook")."""
    roles = {"epilogue": "hook", "rewind": "rewind"}
    return [roles.get(b.get("video"), b.get("id", b.get("action"))) for b in beats]


def _rewind_hold(n):
    return min(18, max(6, n // 3))


def _rewind_montage(film, beats, spans, frames_dir):
    """Hook → rewind: freeze the hook's last frame (record scratch), then play the whole build
    backwards at high speed with a VHS look, ending on the bare lawn where the build starts."""
    ids = _beat_ids(beats)
    if "rewind" not in ids or "hook" not in ids:
        return
    r = spans[ids.index("rewind")]
    hook_last = spans[ids.index("hook")]["end"]
    ri = ids.index("rewind")
    src0 = spans[ids.index(film["rewind_from"]) if "rewind_from" in film else ri + 1]["start"]
    src1 = spans[ids.index(film["rewind_to"]) if "rewind_to" in film else len(ids) - 2]["end"]
    n = r["end"] - r["start"] + 1
    hold = _rewind_hold(n)
    frozen = Image.open(_frame(frames_dir, hook_last)).convert("RGB")
    for k in range(hold):                                  # freeze with a slow push-in
        _zoom(frozen, 1.0 + 0.07 * k / hold).save(_frame(frames_dir, r["start"] + k))
    rng = np.random.default_rng(3)
    m = n - hold
    for k in range(m):
        t = (k / max(1, m - 1)) ** 0.8                     # end → start of the build
        src = int(round(src1 - (src1 - src0) * t))
        img = Image.open(_frame(frames_dir, src)).convert("RGB")
        _vhs(img, k, rng).save(_frame(frames_dir, r["start"] + hold + k))
    log.info(f"Rewind montage: {hold} freeze + {m} reversed frames")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("film", help="name of engine/films/<film>.json + <film>_film.py")
    ap.add_argument("--reuse-voice", action="store_true")
    ap.add_argument("--preview", action="store_true", help="render 3 stills per beat only")
    ap.add_argument("--frames", default="", help="render only these frames as stills, e.g. 450,470")
    ap.add_argument("--resume", action="store_true",
                    help="keep already-rendered frames and render only the missing ones")
    ap.add_argument("--remix", action="store_true",
                    help="reuse the rendered video; rebuild only sound + captions (implies --reuse-voice)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    return produce(args)


def produce(args):
    """Voice → timings → Blender render → post. `args.film` is a film name in engine/films/ or a
    path to a film JSON (e.g. a script written by agents/showrunner.py). Returns the final mp4."""
    films = os.path.join(PROJECT_ROOT, "engine", "films")
    if args.film.endswith(".json") and os.path.exists(args.film):
        film_json = os.path.abspath(args.film)
        args.film = os.path.splitext(os.path.basename(film_json))[0]
    else:
        film_json = os.path.join(films, f"{args.film}.json")
    film = json.load(open(film_json, encoding="utf-8"))
    # Data-driven films (a 3D set + one action per beat) all render through the generic runner.
    film_py = os.path.join(films, "cutaway_film.py" if film.get("set") else f"{args.film}_film.py")
    beats = film["beats"]
    work = os.path.join(PROJECT_ROOT, "output", f"{args.film}_work")
    os.makedirs(work, exist_ok=True)

    # ---- voice + timing ----
    voice_path = os.path.join(work, "voice.mp3")
    if not ((args.reuse_voice or args.remix) and os.path.exists(voice_path)):
        tmp, _ = generate_voiceover(" ".join(b["text"] for b in beats), voice=film.get("voice", "energetic"))
        shutil.move(tmp, voice_path)
    duration = get_duration(voice_path)
    words = transcribe_with_whisper(voice_path)
    total = duration + film.get("tail", 0.8)      # time after the last word (let the ending land)
    slots = align_beats(beats, words, total)
    total_frames = sum(s["frames"] for s in slots)
    f, spans = 0, []
    for s in slots:
        spans.append({"start": f, "end": f + s["frames"] - 1})
        f += s["frames"]
    timings = {"fps": FPS, "total_frames": total_frames, "beats": spans,
               "envelope": voice_envelope(voice_path, total_frames)}
    timings_path = os.path.join(work, "timings.json")
    json.dump(timings, open(timings_path, "w", encoding="utf-8"))
    log.info(f"Voice {duration:.1f}s → {total_frames} frames, {len(beats)} beats")

    video = os.path.join(work, "video.mp4")
    if args.remix:
        if not os.path.exists(video):
            raise RuntimeError("--remix needs a previous full render (work/video.mp4)")
        return _finish(args, film, beats, spans, words, total, work, voice_path, video)

    # ---- render ----
    resume = getattr(args, "resume", False)
    if not (args.preview or args.frames or resume):
        shutil.rmtree(os.path.join(work, "frames"), ignore_errors=True)
    log.info("Rendering in Blender...")
    cmd = [BLENDER, "--background", "--factory-startup", "--python", film_py, "--", film_json, timings_path, work]
    extra = (["--preview"] if args.preview else []) + ([f"--frames={args.frames}"] if args.frames else [])
    workers = int(os.getenv("RENDER_WORKERS", "1"))   # measured: 2 = no gain on the laptop GPU
    if film.get("set") and not (args.preview or args.frames) and (workers > 1 or resume):
        start, hook = None, True
        if resume:                                     # keep finished frames, render only the rest
            have = {int(os.path.basename(p)[2:6]) for p in glob.glob(os.path.join(work, "frames", "f_*.png"))}
            hook = not all(f in have for f in range(spans[0]["start"] + 1, spans[0]["end"] + 2))
            build0 = spans[2]["start"] + 1
            missing = [f for f in range(build0, total_frames + 1) if f not in have]
            start = max(build0, missing[0] - 1) if missing else total_frames + 1   # redo the last (maybe partial) one
            log.info(f"  resume: {len(have)} frames kept, rendering from frame {start}" + (" + hook" if hook else ""))
        if start is None or start <= total_frames or hook:
            _render_parallel(cmd, spans, total_frames, max(1, workers), work, start=start, hook=hook)
    else:
        r = subprocess.run(cmd + extra, capture_output=True, text=True)
        if "DONE" not in r.stdout:
            raise RuntimeError(f"Blender failed:\n{r.stdout[-3000:]}\n{r.stderr[-2000:]}")
    if args.preview or args.frames:
        log.info(f"Stills in {work}")
        return
    _rewind_montage(film, beats, spans, os.path.join(work, "frames"))
    frames = sorted(glob.glob(os.path.join(work, "frames", "f_*.png")))
    log.info(f"Rendered {len(frames)} frames")

    # ---- stickers (spread over all CPU cores: one PNG load/draw/save per frame adds up) ----
    jobs = [(frames[i], _overlay(beat), (i - span["start"]) / FPS)
            for beat, span in zip(beats, spans) if _overlay(beat)
            for i in range(span["start"], min(span["end"] + 1, len(frames)))]
    if jobs:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) - 1)) as pool:
            list(pool.map(_sticker_job, jobs, chunksize=16))

    subprocess.run([FFMPEG, "-y", "-framerate", str(FPS), "-i", os.path.join(work, "frames", "f_%04d.png"),
                    "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", video],
                   check=True, capture_output=True)
    return _finish(args, film, beats, spans, words, total, work, voice_path, video)


# Effects sit well under the narration: the voice must always win.
SFX_GAIN, WHOOSH_GAIN = 0.32, 0.45


def _finish(args, film, beats, spans, words, total, work, voice_path, video):
    # ---- sound design ----
    cuts = []                                          # no whoosh on scene changes (too noisy)
    pops = [s["start"] / FPS + 0.18 for b, s in zip(beats, spans) if _overlay(b)]
    whoosh = _read_wav(build_fx_track(total, cuts, pops, os.path.join(work, "whoosh.wav")))
    events = json.load(open(os.path.join(work, "events.json"), encoding="utf-8"))
    ids = _beat_ids(beats)
    if "rewind" in ids:                                    # record scratch on the freeze, then the VCR whirr
        r = spans[ids.index("rewind")]
        hold = _rewind_hold(r["end"] - r["start"] + 1)
        events.append({"frame": r["start"] + 1, "kind": "scratch", "duration": 0, "gain": 1.0})
        events.append({"frame": r["start"] + hold + 1, "kind": "rewind",
                       "duration": r["end"] - r["start"] - hold, "gain": 1.0})
    synced = _read_wav(sfx.render_events(events, FPS, total, os.path.join(work, "sfx.wav")))
    n = max(len(whoosh), len(synced))
    fx = np.zeros(n)
    fx[:len(whoosh)] += whoosh * WHOOSH_GAIN
    fx[:len(synced)] += synced * SFX_GAIN
    fx_path = _write_wav(os.path.join(work, "fx_all.wav"), fx)
    music = None
    if film.get("music") == "synth":                       # generated bed (no licensed tracks needed)
        music = _write_wav(os.path.join(work, "music.wav"), sfx.music(min(total, 60.0)))
    mixed = mix_audio(voice_path, fx_path, os.path.join(work, "mix.m4a"), total, music=music)
    merged = merge_audio_video(video, mixed)

    ass = os.path.join(work, "captions.ass")
    words_to_ass(script_word_timings(beats, words, total), ass, mode=film.get("captions", "phrase"))
    final = burn_subtitles(merged, ass)
    out = os.path.join(get_output_dir(), f"{args.film}.mp4")
    shutil.move(final, out)
    os.remove(merged)
    preview = os.path.join(get_output_dir(), f"{args.film}_preview.mp4")
    subprocess.run([FFMPEG, "-v", "error", "-y", "-i", out, "-c:v", "copy", "-c:a", "libopus", "-b:a", "128k",
                    preview], check=True)
    log.info(f"\nFILM: {out} ({get_duration(out):.1f}s)\nVS Code preview: {preview}")
    return out


if __name__ == "__main__":
    main()
