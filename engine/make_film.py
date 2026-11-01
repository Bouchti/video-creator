"""
Film production driver (runs in the project venv):

  python -m engine.make_film pool_cut [--reuse-voice] [--preview | --frames=450,470]

voiceover → word timings + lip-sync envelope → Blender render timed to the words
→ overlay stickers → restrained sound design (authored SFX, ambience, music)
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
import tempfile
import time
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from config.paths import PROJECT_ROOT, get_blender, get_output_dir  # noqa: E402
from agents.beats import align_beats, script_word_timings, FPS  # noqa: E402
from agents.media import FFMPEG, FFPROBE, get_duration, merge_audio_video, burn_subtitles, read_pcm, write_wav  # noqa: E402
from agents.transcription import transcribe_with_whisper  # noqa: E402
from agents.voice import generate_voiceover  # noqa: E402
from agents.audio_fx import build_fx_track, mix_audio, SR  # noqa: E402
from agents.captions import words_to_ass  # noqa: E402
from agents.render import draw_overlay  # noqa: E402
from agents import sfx  # noqa: E402

log = logging.getLogger("pipeline")
BLENDER = get_blender()


def voice_envelope(path: str, frames: int) -> list:
    """Per-frame loudness (0..1) of the voiceover — drives lip-sync."""
    x = read_pcm(path, 16000)
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


def _sticker_job(job):
    """Draw a sticker on a COPY of a raw frame (raw renders stay clean, so they can be re-used by
    --redo / --resume without stickers piling up)."""
    src, overlay, t, dst = job
    draw_overlay(Image.open(src).convert("RGB"), overlay, t).save(dst)


def _parse_redo(spec, film, beats, spans):
    """'keel,bulkheads' (beat ids/actions) | '7' (beat number) | '42-46s' / '42.5-46' (seconds)
    → sorted list of 1-based render frames."""
    frames = set()
    for part in [p.strip() for p in spec.split(",") if p.strip()]:
        if any(c.isdigit() for c in part) and ("-" in part or part.endswith("s")) and not part.isdigit():
            a, b = part.rstrip("s").split("-")
            frames.update(range(int(float(a) * FPS) + 1, int(float(b) * FPS) + 2))
            continue
        hit = [k for k, b in enumerate(beats)
               if part.isdigit() and k + 1 == int(part) or part in (b.get("id"), b.get("action"))
               or part in (b.get("actions") or [])]
        if not hit:
            raise SystemExit(f"--redo: no beat or time range matches '{part}' (see --list)")
        for k in hit:
            frames.update(range(spans[k]["start"] + 1, spans[k]["end"] + 2))
    total = spans[-1]["end"] + 1
    return sorted(f for f in frames if 1 <= f <= total)


def _ranges(frames):
    out, start, prev = [], None, None
    for f in frames:
        if start is None:
            start = prev = f
        elif f == prev + 1:
            prev = f
        else:
            out.append((start, prev))
            start = prev = f
    if start is not None:
        out.append((start, prev))
    return out


def _restore_redo_frames(video, frames_dir, total_frames, targets):
    """Recover cleaned frame caches from the retained intermediate video.

    Successful autopilot runs normally delete their large PNG caches. A later
    ``--redo`` still should not require a full Blender render: ``work/video.mp4``
    contains every previously accepted frame (with its existing stickers). Extract
    that video to a temporary directory and restore only non-target frames; Blender
    will replace the target ranges with fresh, clean renders below.
    """
    targets = set(targets)
    missing = [f for f in range(1, total_frames + 1)
               if f not in targets and not os.path.exists(os.path.join(frames_dir, f"f_{f:04d}.png"))]
    if not missing or not os.path.exists(video):
        return 0

    os.makedirs(frames_dir, exist_ok=True)
    work = os.path.dirname(frames_dir)
    with tempfile.TemporaryDirectory(prefix="redo_restore_", dir=work) as restored_dir:
        pattern = os.path.join(restored_dir, "f_%04d.png")
        subprocess.run([FFMPEG, "-v", "error", "-i", video, "-map", "0:v:0", "-an", "-sn", "-dn",
                        "-fps_mode", "passthrough", "-start_number", "1", pattern], check=True)
        restored = 0
        for f in missing:
            src = os.path.join(restored_dir, f"f_{f:04d}.png")
            if os.path.exists(src):
                shutil.move(src, os.path.join(frames_dir, f"f_{f:04d}.png"))
                restored += 1
    if restored:
        log.info(f"Redo: restored {restored} unaffected frames from the retained video cache")
    return restored


class BlenderFailed(RuntimeError):
    """Blender exited without finishing; .log holds its output (a Python traceback when the set's
    code is at fault, nothing useful when the process itself died: GPU, memory, killed)."""

    def __init__(self, log_text):
        self.log = log_text
        super().__init__(f"Blender failed:\n{log_text[-4000:]}")

    @property
    def is_code_error(self):
        return "Traceback (most recent call last)" in self.log


def _code_hash(film):
    """Fingerprint of everything that decides how a film's frames look (engine + its set)."""
    import hashlib
    h = hashlib.sha1()
    eng = os.path.join(PROJECT_ROOT, "engine")
    for root, _dirs, files in os.walk(eng):
        for fn in sorted(files):
            if fn.endswith(".py"):
                with open(os.path.join(root, fn), "rb") as fh:
                    h.update(fn.encode() + fh.read())
    return h.hexdigest()[:16]


def _frame_codes(work):
    try:
        return json.load(open(os.path.join(work, "frame_code.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_frame_codes(work, codes):
    with open(os.path.join(work, "frame_code.json"), "w", encoding="utf-8") as fh:
        json.dump(codes, fh)


def _stale_beats(cmd, film, beats, spans, work, keep, code):
    """Kept frames rendered with OTHER code: does the current code still produce them? Render a quick
    low-res sample per affected beat and compare it with the kept frame; beats that changed are
    returned (so a fix in shared code, e.g. where the kids sit, reaches every scene it touches)."""
    codes = _frame_codes(work)
    suspect = {}
    for k, sp in enumerate(spans):
        frames = [f for f in range(sp["start"] + 1, sp["end"] + 2) if f in keep and codes.get(str(f)) != code]
        if frames and _beat_ids(beats)[k] != "rewind":
            suspect[k] = frames
    if not suspect:
        return []
    probe = {k: fr[len(fr) // 2] for k, fr in suspect.items()}
    tmp = tempfile.mkdtemp(prefix="stale_", dir=work)
    env = dict(os.environ, CUT_PCT="25", CUT_SAMPLES="8")
    subprocess.run(cmd + [f"--frames={','.join(str(f) for f in probe.values())}"], env=env, capture_output=True,
                   text=True)
    changed = []
    for k, f in probe.items():
        new_p = os.path.join(tmp, f"still_{f:04d}.png")
        old_p = os.path.join(work, "frames", f"f_{f:04d}.png")
        if not (os.path.exists(new_p) and os.path.exists(old_p)):
            changed.append(k)
            continue
        a = np.asarray(Image.open(new_p).convert("L"), dtype=np.float32)
        b = np.asarray(Image.open(old_p).convert("L").resize((a.shape[1], a.shape[0])), dtype=np.float32)
        y0 = int(a.shape[0] * 0.24)                              # below the sticker band
        diff = np.abs(a[y0:] - b[y0:])
        if (diff > 40).mean() > 0.015:                           # >1.5% of the picture really moved
            changed.append(k)
    shutil.rmtree(tmp, ignore_errors=True)
    return changed


def _run_blender(cmd, watcher=None, env=None):
    """Run one Blender process. With a scene watcher, poll it while Blender renders and stop
    Blender as soon as a window is rejected (returns "aborted")."""
    logf = tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace")
    kwargs = {"stdout": logf, "stderr": subprocess.STDOUT, "text": True}
    if env is not None:
        kwargs["env"] = env
    p = subprocess.Popen(cmd, **kwargs)
    while p.poll() is None:
        if watcher is not None and watcher.should_abort():
            p.terminate()
            p.wait()
            log.warning("Blender stopped: a rendered scene was rejected")
            return "aborted"
        time.sleep(1.0)
    logf.seek(0)
    out = logf.read()
    logf.close()
    if "DONE" not in out:
        raise BlenderFailed(out)
    return out


def _render_parallel(cmd, spans, total, n, work, start=None, hook=True, watcher=None):
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
    while watcher is not None and any(p.poll() is None for p, _, _ in procs):
        if watcher.should_abort():
            for p, _, _ in procs:
                if p.poll() is None:
                    p.terminate()
            for p, logf, _ in procs:
                p.wait()
                logf.close()
            log.warning("Blender stopped: a rendered scene was rejected")
            return "aborted"
        time.sleep(1.0)
    failed = []
    for p, logf, k in procs:
        p.wait()
        logf.close()
        out = open(logf.name, encoding="utf-8", errors="replace").read()
        if "DONE" not in out:
            failed.append(f"worker {k}:\n{out[-2000:]}")
    if failed:
        raise BlenderFailed("\n".join(failed))


def _scene_verdict(args, film, watcher, spans, work):
    """After the render: every window accepted → None (carry on to post-production). Otherwise act on
    SCENE_POLICY: warn → carry on; fix → let Claude fix the set's code, delete the rejected beats'
    frames and resume the render (up to SCENE_FIX_ATTEMPTS rounds); stop/report → raise."""
    from agents import scene_validator as sv
    rep = watcher.finish()
    log.info(f"Scene review: {rep['accepted']}/{rep['planned']} windows accepted ({watcher.report_path})")
    if not rep["rejected"]:
        return None
    if watcher.policy == "warn":
        log.warning(f"{len(rep['rejected'])} scene window(s) rejected; assembling anyway (SCENE_POLICY=warn)")
        return None
    attempt = getattr(args, "_scene_attempt", 0)
    before = getattr(args, "_scene_rejected", None)
    args._scene_rejected = len(rep["rejected"])
    if before is not None and len(rep["rejected"]) >= before:
        # the last repair round fixed nothing (the floating-cabin film: 11 rejected windows before and after, each
        # round re-rendering most of the film): another round with the same inputs only burns another hour
        log.warning(f"QUALITY WARNING: the repair round did not reduce the rejected windows ({before} -> "
                    f"{len(rep['rejected'])}); no more repair rounds")
        raise sv.SceneRejected(rep["rejected"], watcher.report_path)
    if watcher.policy == "fix" and attempt < int(os.getenv("SCENE_FIX_ATTEMPTS") or "2"):
        from agents.set_builder import fix_scenes, freeze_methods, restore_methods
        log.info(f"Auto-fix round {attempt + 1}: asking Claude to fix {len(rep['rejected'])} rejected window(s)")
        # beats whose every window passed keep their code exactly (a repair must not break them), and the
        # repair turn gets a few windows at a time so it finishes within its token cap
        bad_beats = {r["beat"] for r in rep["rejected"]}
        keep = sorted({r["action"] for r in rep["windows"] if r.get("valid") and r["beat"] not in bad_beats})
        frozen = freeze_methods(film["set"], [a for k in keep for a in k.split("+")])
        # Film-window repairs have their own cap.  SET_FIX_MAX_WINDOWS belongs to the
        # initial set-builder preview loop; using it here silently ignored the
        # documented SCENE_FIX_MAX_WINDOWS setting and stretched production repair
        # across unnecessary full rerenders.
        fix_scenes(film["set"], rep["rejected"], keep=keep,
                   max_windows=int(os.getenv("SCENE_FIX_MAX_WINDOWS") or
                                   os.getenv("SET_FIX_MAX_WINDOWS") or 3), measure=False)
        restored = restore_methods(film["set"], frozen)
        if restored:
            log.info(f"Kept the accepted scenes as they were: put back {', '.join(restored)}")
        # Use the existing targeted-redo renderer. The old implementation deleted every
        # frame from the earliest rejected beat onward; one bad hook therefore discarded an
        # otherwise complete film and forced thousands of accepted frames through Blender and
        # vision review again. Beat numbers are unambiguous even when actions are reused.
        rejected_beats = sorted({int(r["beat"]) for r in rep["rejected"]})
        args._scene_attempt = attempt + 1
        args.resume, args.reuse_voice = True, True
        args.redo = ",".join(str(beat) for beat in rejected_beats)
        log.info(f"Auto-fix round {attempt + 1}: targeted redo of beat(s) {args.redo}; "
                 "all other production frames are preserved")
        return produce(args)
    raise sv.SceneRejected(rep["rejected"], watcher.report_path)


def _scene_preflight(film, film_json, film_py, timings_path, spans, work, spec):
    """Approve the exact final timeline cheaply before rendering production frames.

    The set builder's three stills per *beat* cannot catch a late camera cut or a prop that vanishes
    in one three-second production window. This rehearsal stages the real film and renders only the
    same start/middle/end frames the production reviewer will inspect, at phone-review resolution.
    Rejected windows are repaired here; unchanged pixel-identical verdicts are cached by the scene
    validator. The expensive full animation starts only after every rehearsal window passes.
    """
    from agents import scene_validator as sv
    if not sv._env_flag("SCENE_PREFLIGHT", "1"):
        return {}

    import hashlib
    from agents.set_builder import fix_scenes, freeze_methods, restore_methods

    root = os.path.join(work, "preflight")
    os.makedirs(root, exist_ok=True)
    rounds = max(1, int(os.getenv("SCENE_PREFLIGHT_FIX_ATTEMPTS") or "3"))
    cap = max(1, int(os.getenv("SCENE_PREFLIGHT_FIX_WINDOWS") or "6"))
    report_path = os.path.join(root, "scene_review.json")
    manifest_path = os.path.join(root, "manifest.json")

    for attempt in range(rounds + 1):
        h = hashlib.sha256()
        h.update(_code_hash(film).encode("ascii"))
        with open(film_json, "rb") as fh:
            h.update(fh.read())
        with open(timings_path, "rb") as fh:
            h.update(fh.read())
        h.update(b"exact-window-preflight-v1")
        fingerprint = h.hexdigest()
        try:
            manifest = json.load(open(manifest_path, encoding="utf-8"))
        except (OSError, ValueError):
            manifest = {}
        if manifest.get("fingerprint") == fingerprint and manifest.get("accepted"):
            try:
                saved = json.load(open(report_path, encoding="utf-8"))
            except (OSError, ValueError):
                saved = {}
            if saved.get("complete") and not saved.get("rejected"):
                log.info("[preflight] exact-timing rehearsal already accepted; reusing it")
                return {(r["f0"], r["f1"]): r for r in saved["windows"] if r.get("valid")}

        frames_dir, review_dir = os.path.join(root, "frames"), os.path.join(root, "review")
        shutil.rmtree(frames_dir, ignore_errors=True)
        shutil.rmtree(review_dir, ignore_errors=True)
        os.makedirs(frames_dir)
        windows = [w for w in sv.plan_windows(film, spans, spec=spec) if sv._is_rendered_window(w, spec)]
        samples = sorted({f for w in windows for _, f in sv.sample_picks(w)})
        env = dict(os.environ)
        env.update(CUT_PCT=os.getenv("SCENE_PREFLIGHT_RENDER_PCT") or "35",
                   CUT_SAMPLES=os.getenv("SCENE_PREFLIGHT_SAMPLES") or "8", CUT_RT="0")
        env.pop("CUT_PROBE", None)
        cmd = [BLENDER, "--background", "--factory-startup", "--python", film_py, "--",
               film_json, timings_path, frames_dir, f"--frames={','.join(str(f) for f in samples)}"]
        log.info(f"[preflight] round {attempt + 1}: rendering {len(samples)} exact timeline samples "
                 f"before the {spans[-1]['end'] + 1}-frame production render")
        _run_blender(cmd, env=env)
        for f in samples:
            src, dst = os.path.join(frames_dir, f"still_{f:04d}.png"), os.path.join(frames_dir, f"f_{f:04d}.png")
            if os.path.exists(src):
                os.replace(src, dst)
        rep = sv.review_sampled_windows(film, spans, root, spec=spec)
        log.info(f"[preflight] {rep['accepted']}/{rep['planned']} exact windows accepted")
        if not rep["rejected"]:
            with open(manifest_path, "w", encoding="utf-8") as fh:
                json.dump({"fingerprint": fingerprint, "accepted": True,
                           "windows": rep["planned"]}, fh, indent=1)
            return {(r["f0"], r["f1"]): r for r in rep["windows"] if r.get("valid")}
        if attempt >= rounds:
            raise sv.SceneRejected(rep["rejected"], report_path)

        bad_beats = {r["beat"] for r in rep["rejected"]}
        keep = sorted({r["action"] for r in rep["windows"] if r.get("valid") and r["beat"] not in bad_beats})
        frozen = freeze_methods(film["set"], [a for actions in keep for a in actions.split("+")])
        log.info(f"[preflight] repairing {len(rep['rejected'])} rejected windows before production render")
        fix_scenes(film["set"], rep["rejected"], keep=keep, max_windows=cap, measure=False)
        restored = restore_methods(film["set"], frozen)
        if restored:
            log.info(f"[preflight] kept accepted scenes unchanged: {', '.join(restored)}")


def _overlay(beat):
    """2D sticker for a beat: `overlay`, or the first 2D-type entry of a structured `callouts`
    list (stat / label). 3D callouts (label3d, dimension) are drawn in the scene instead."""
    if beat.get("overlay") and beat["overlay"].get("type") != "none":
        return beat["overlay"]
    for c in beat.get("callouts", []):
        if c.get("type") in ("stat", "label"):
            return c
    return None


def _kit_film(film):
    """Kit scenes explain with physical 3D labels; they never receive 2D stickers or a CTA card."""
    if not film.get("set"):
        return False
    from engine import sets as _sets
    return bool(getattr(_sets.spec(film["set"]), "KIT", None))


# Where each 2D sticker kind is drawn (agents/render.draw_overlay), in image units (x0, y0, x1, y1, y down).
STICKER_BOX = {"label": (0.15, 0.10, 0.85, 0.18), "stat": (0.08, 0.13, 0.92, 0.34)}
STICKER_CLASH = 0.15         # share of the beat's measured frames a 3D label may overlap the sticker


def _overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def drop_clashing_stickers(beats, spans, boxes_path):
    """One text per moment: a sticker whose place is taken by one of the scene's 3D labels or insets (measured
    frame by frame in Blender: engine/overlays.py) for more than STICKER_CLASH of its beat is dropped, the
    scene's own label wins. The sandcastle film stacked a "2 m" sticker on DRY SAND and a yellow pill on
    1% WATER. Returns the ids of the beats that lost their sticker."""
    try:
        boxes = {int(k): v for k, v in json.load(open(boxes_path, encoding="utf-8")).items()}
    except (OSError, ValueError):
        return []
    dropped = []
    for b, span in zip(beats, spans):
        sticker = _overlay(b)
        region = STICKER_BOX.get((sticker or {}).get("type"))
        if not region:
            continue
        measured = [f for f in boxes if span["start"] + 1 <= f <= span["end"] + 1]
        # (frames without any label are measured too, but text_boxes keeps only frames that HAVE labels)
        n = max(1, (span["end"] - span["start"] + 1) // 2)          # settle() measures every 2nd frame
        clash = sum(1 for f in measured if any(_overlap(region, box) for box in boxes[f]))
        if clash > STICKER_CLASH * n:
            log.info(f"Sticker dropped on '{b.get('id') or b.get('action')}': a 3D label/inset sits where it would "
                     f"be drawn ({clash}/{n} measured frames) - {sticker}")
            b.pop("overlay", None)
            b["callouts"] = [c for c in b.get("callouts", []) if c is not sticker]
            dropped.append(b.get("id") or b.get("action"))
    return dropped


def _cta_start(film, words, n_frames):
    """Frame where the closing question starts being spoken (it stays on screen until the end)."""
    q = [w.strip(".,!?;:\"'").lower() for w in film["cta"].split()]
    spoken = [str(w.get("word", w.get("text", ""))).strip(".,!?;:\"' ").lower() for w in words]
    for k in range(len(spoken) - len(q), -1, -1):
        if spoken[k:k + 2] == q[:2]:
            start = words[k].get("start", 0.0)
            return max(0, min(n_frames - 1, int(start * FPS)))
    return max(0, n_frames - int(3.5 * FPS))


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
    ids = []
    for beat in beats:
        role = roles.get(beat.get("video"))
        name = beat.get("id") or beat.get("action")
        # Generated kit films made before roles were explicit still name the opening action *_hook.
        # Treat that as an epilogue hook so their rewind frames cannot silently disappear.
        ids.append(role or ("hook" if name and name.endswith("_hook") else name))
    return ids


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
    try:                                               # run on its own (manual render, --redo): read .env like main.py
        from dotenv import load_dotenv
        load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
    except ImportError:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("film", help="name of engine/films/<film>.json + <film>_film.py")
    ap.add_argument("--reuse-voice", action="store_true")
    ap.add_argument("--preview", action="store_true", help="render 3 stills per beat only")
    ap.add_argument("--frames", default="", help="render only these frames as stills, e.g. 450,470")
    ap.add_argument("--resume", action="store_true",
                    help="keep already-rendered frames and render only the missing ones")
    ap.add_argument("--remix", action="store_true",
                    help="reuse the rendered video; rebuild only sound + captions (implies --reuse-voice)")
    ap.add_argument("--redo", default="",
                    help="re-render ONLY these scenes, keep every other frame and the voice: beat ids/actions "
                         "('keel,bulkheads'), beat numbers ('7') or time ranges ('42-46s')")
    ap.add_argument("--list", action="store_true", help="print the scenes with their start/end times")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    return produce(args)


MAX_SPEED = 1.15                       # the fastest narration still reads as natural


class FilmTooLong(RuntimeError):
    """The narration cannot fit the film's length cap even read faster: the script is too long."""


def _replace_file(source, destination):
    """Atomically replace a cached artifact when possible, with a cross-volume fallback for temp files."""
    try:
        os.replace(source, destination)
    except OSError:
        shutil.copyfile(source, destination)
        os.remove(source)


def _fit_cap(voice_path, text, film):
    """Keep a film inside FILM_MAX_SECONDS when it is set (off by default: scripts are sized by the voice's
    measured pace): if the voiced narration plus the tail is longer, voice it again once, proportionally
    faster (up to MAX_SPEED); if even that cannot fit, stop before any frame is rendered."""
    cap = float(os.getenv("FILM_MAX_SECONDS") or 0)
    tail = film.get("tail", 0.8)
    duration = get_duration(voice_path)
    if not cap or duration + tail <= cap:
        return duration
    base = float(os.getenv("VOICE_SPEED", "0.92"))
    speed = min(MAX_SPEED, base * duration / max(1.0, cap - tail - 0.4))
    if speed <= base + 1e-6:
        raise FilmTooLong(f"narration is {duration:.1f}s; with the tail it passes the {cap:.0f}s cap")
    log.warning(f"Narration {duration:.1f}s + tail passes the {cap:.0f}s cap; voicing it again at speed {speed:.2f}")
    old = os.environ.get("VOICE_SPEED")
    os.environ["VOICE_SPEED"] = f"{speed:.3f}"
    try:
        tmp, _ = generate_voiceover(text, voice=film.get("voice", "energetic"))
    finally:
        if old is None:
            os.environ.pop("VOICE_SPEED", None)
        else:
            os.environ["VOICE_SPEED"] = old
    _replace_file(tmp, voice_path)
    duration = get_duration(voice_path)
    if duration + tail > cap:
        raise FilmTooLong(f"narration is still {duration:.1f}s at speed {speed:.2f}: the script is too long for "
                          f"the {cap:.0f}s cap")
    return duration


def _stream_durations(path):
    result = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "json", path],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe stream check failed for {path}: {result.stderr[-300:]}")
    found = {}
    for stream in json.loads(result.stdout or "{}").get("streams", []):
        try:
            found.setdefault(stream["codec_type"], []).append(float(stream["duration"]))
        except (KeyError, TypeError, ValueError):
            pass
    return {kind: max(values) for kind, values in found.items() if values}


def _assert_file_cap(path):
    """The encoded deliverable is the last authority: it must be complete and, with FILM_MAX_SECONDS set,
    not one frame over the cap."""
    cap = float(os.getenv("FILM_MAX_SECONDS") or 0)
    duration = get_duration(path)
    if cap and duration > cap:
        raise FilmTooLong(f"final file is {duration:.2f}s; it passes the {cap:.0f}s cap")
    streams = _stream_durations(path)
    if "video" not in streams or "audio" not in streams:
        raise RuntimeError("final file must contain both a video stream and an audio stream")
    for kind in ("video", "audio"):
        if duration - streams[kind] > 0.25:
            raise RuntimeError(f"final {kind} stream is only {streams[kind]:.2f}s of the {duration:.2f}s film")
    return duration


def _hold_actions(film, beats, words, duration, voice_path):
    """Silence in the voice wherever a beat's line is shorter than its action's minimum seconds (the set spec),
    so every action plays out on screen. Returns the shifted word timings and the new voice length."""
    from agents.beats import action_holds, shift_words
    if not film.get("set") or not film.get("action_hold", True):
        return words, duration
    from engine import sets as _sets
    min_seconds = getattr(_sets.spec(film["set"]), "min_seconds", None)
    if min_seconds is None:
        return words, duration
    holds = action_holds(beats, words, duration, film.get("tail", 0.8), min_seconds)
    if not holds:
        return words, duration
    sr = 44100
    x = read_pcm(voice_path, sr)
    parts, last = [], 0
    for at, pad in holds:
        i = min(len(x), int(at * sr))
        parts += [x[last:i], np.zeros(int(pad * sr), dtype=np.float32)]
        last = i
    parts.append(x[last:])
    tmp = voice_path + ".hold.wav"
    write_wav(tmp, np.concatenate(parts), sr)
    os.replace(tmp, voice_path)                    # (WAV data under voice.mp3, as the Chatterbox voice already is)
    log.info(f"Action holds: +{sum(p for _, p in holds):.1f}s over {len(holds)} beats, so each action reads "
             f"({', '.join(f'{a:.1f}s+{p:.1f}' for a, p in holds)})")
    return shift_words(words, holds), get_duration(voice_path)


WORK_LOCK = ".make_film.lock"


def _pid_alive(pid):
    if pid <= 0:
        return False
    if os.name == "nt":                                # (os.kill(pid, 0) can change a Windows process's exit code)
        import ctypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = ctypes.c_void_p
        handle = k32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(k32.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code))) and code.value == 259
        finally:
            k32.CloseHandle(ctypes.c_void_p(handle))
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def work_in_use(work):
    """The pid of ANOTHER live make_film that holds this work dir (its frames are in use), else None."""
    try:
        pid = int(open(os.path.join(work, WORK_LOCK), encoding="utf-8").read().split()[0])
    except (OSError, ValueError, IndexError):
        return None
    return pid if pid != os.getpid() and _pid_alive(pid) else None


def produce(args):
    """produce_film() holding the film's work dir: a second make_film on the same film (a manual --redo while the
    autopilot runs) and the autopilot's frame cleanup both wait for it instead of deleting frames it is using."""
    film_source = getattr(args, "_film_json", args.film)
    name = os.path.splitext(os.path.basename(film_source))[0] if film_source.endswith(".json") else film_source
    work = os.path.join(PROJECT_ROOT, "output", f"{name}_work")
    os.makedirs(work, exist_ok=True)
    lock = os.path.join(work, WORK_LOCK)
    other = work_in_use(work)
    if other:
        raise RuntimeError(f"another make_film (pid {other}) is rendering {name}; wait for it to finish")
    try:
        holder = int(open(lock, encoding="utf-8").read().split()[0])
    except (OSError, ValueError, IndexError):
        holder = None
    mine = holder is None or (holder != os.getpid() and not _pid_alive(holder))   # (a repair re-render nests)
    if mine:
        open(lock, "w", encoding="utf-8").write(str(os.getpid()))
    try:
        return produce_film(args)
    finally:
        if mine:
            try:
                if open(lock, encoding="utf-8").read().split()[0] == str(os.getpid()):
                    os.remove(lock)
            except (OSError, IndexError):
                pass


def produce_film(args):
    """Voice → timings → Blender render → post. `args.film` is a film name in engine/films/ or a
    path to a film JSON (e.g. a script written by agents/showrunner.py). Returns the final mp4."""
    films = os.path.join(PROJECT_ROOT, "engine", "films")
    # Automatic scene repair recursively calls produce(). Preserve the original absolute JSON
    # path because generated films live in output/films, while args.film is shortened below only
    # to derive stable work and output names.
    film_source = getattr(args, "_film_json", args.film)
    if film_source.endswith(".json") and os.path.exists(film_source):
        film_json = os.path.abspath(film_source)
        args._film_json = film_json
        args.film = os.path.splitext(os.path.basename(film_json))[0]
    else:
        film_json = os.path.join(films, f"{film_source}.json")
        args._film_json = film_json
    name = args.film
    film = json.load(open(film_json, encoding="utf-8"))
    # Data-driven films (a 3D set + one action per beat) all render through a generic runner:
    # "evolution" films (no hook/rewind, e.g. bridge_evolution) through evolution_film.py.
    evolution = film.get("format") == "evolution"
    # build-up explainers ("If you ...", agents/buildup.py) render with the cutaway runner but, like
    # evolution films, start on the first build step: no epilogue hook to render, no rewind.
    hookless = evolution or film.get("format") == "buildup"
    film_py = os.path.join(films, "evolution_film.py" if evolution else "cutaway_film.py")
    beats = film["beats"]
    if film.get("set"):                               # one text per idea: the scene's own label wins over a sticker
        from engine import sets as _sets
        for b in beats:
            acts = b.get("actions") or [b.get("action")]
            if b.get("overlay") and _sets.repeats_label(b["overlay"], _sets.scene_labels(film["set"], acts)):
                log.info(f"Sticker dropped on '{b.get('id')}': the scene already labels it ({b['overlay']})")
                b.pop("overlay")
    work = os.path.join(PROJECT_ROOT, "output", f"{name}_work")
    os.makedirs(work, exist_ok=True)

    # ---- voice + timing ----
    voice_path = os.path.join(work, "voice.mp3")
    redo = getattr(args, "redo", "") or ""
    if redo or getattr(args, "list", False):
        args.reuse_voice = True                        # same voice → same timings → frames line up
        if not os.path.exists(voice_path):
            raise SystemExit("--redo/--list need a previous full render (work/voice.mp3)")
    # A short pause between beats lets each gag / explanation land (ElevenLabs <break> tags). Build the
    # exact text even when reusing audio: an old overlong voice must be re-voiced or rejected, never reused.
    gap = film.get("beat_pause", 0.55)
    text = f' <break time="{gap:.2f}s" /> '.join(b["text"] for b in beats) if gap else " ".join(b["text"] for b in beats)
    fresh_voice = not ((args.reuse_voice or args.remix) and os.path.exists(voice_path))
    if fresh_voice:
        tmp, _ = generate_voiceover(text, voice=film.get("voice", "energetic"))
        _replace_file(tmp, voice_path)
    duration = _fit_cap(voice_path, text, film)
    words = transcribe_with_whisper(voice_path)
    if fresh_voice:                                    # (a reused voice already carries its holds: same timings)
        from agents import stage_writer
        stage_writer.record_rate(sum(len(b["text"].split()) for b in beats), duration, route="cutaway")
        words, duration = _hold_actions(film, beats, words, duration, voice_path)
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
    if getattr(args, "list", False):
        for k, (b, s) in enumerate(zip(beats, spans)):
            print(f"{k + 1:2d}  {s['start'] / FPS:5.1f}s - {(s['end'] + 1) / FPS:5.1f}s  "
                  f"{b.get('id') or b.get('action'):<16} {b['text'][:70]}")
        return None

    video = os.path.join(work, "video.mp4")
    if args.remix:
        if not os.path.exists(video):
            raise RuntimeError("--remix needs a previous full render (work/video.mp4)")
        return _finish(args, film, beats, spans, words, total, work, voice_path, video)

    # ---- prepare: a kit film's whole scene is built and every object measured before any frame renders ----
    resume = getattr(args, "resume", False)
    if film.get("set") and not (args.preview or args.frames or redo):
        from engine import sets as _sets
        if getattr(_sets.spec(film["set"]), "KIT", None):
            from agents.set_builder import prepare_kit_film
            prepare_kit_film(film_json, timings_path, work)

    # ---- render ----
    baked_frames = None                                # (older renders: stickers baked into the kept frames)
    from agents import scene_validator as sv
    validate = sv.enabled(film) and not (args.preview or args.frames)
    watcher = None
    preapproved = {}
    if validate:
        from engine import sets as _sets
        spec = _sets.spec(film["set"])
        # A fresh production render must first pass the exact final-timing rehearsal. Resumes and
        # targeted redos already have production frames and use the live watcher below.
        if not (redo or args.preview or args.frames or resume):
            preapproved = _scene_preflight(film, film_json, film_py, timings_path, spans, work, spec)
    if redo:                                           # only the requested scenes are re-rendered
        targets = _parse_redo(redo, film, beats, spans)
        frames_dir = os.path.join(work, "frames")
        restored = _restore_redo_frames(video, frames_dir, total_frames, targets)
        code = _code_hash(film)
        if os.getenv("REDO_KEEP_STALE") != "1":
            probe_cmd = [BLENDER, "--background", "--factory-startup", "--python", film_py, "--", film_json,
                         timings_path, work]
            keep = set(range(1, total_frames + 1)) - set(targets)
            stale = _stale_beats(probe_cmd, film, beats, spans, work, keep, code)
            if stale:
                names = [beats[k].get("id") or beats[k].get("action") for k in stale]
                log.warning(f"Redo: the code changed since these scenes were rendered and they now look different: "
                            f"{', '.join(names)} -> re-rendering them too")
                for k in stale:
                    targets = sorted(set(targets) | set(range(spans[k]["start"] + 1, spans[k]["end"] + 2)))
        ids = _beat_ids(beats)
        hook = spans[ids.index("hook")] if "hook" in ids else None
        rew = spans[ids.index("rewind")] if "rewind" in ids else None
        in_hook = hook and any(hook["start"] + 1 <= f <= hook["end"] + 1 for f in targets)
        build = [f for f in targets if not (hook and hook["start"] + 1 <= f <= hook["end"] + 1)
                 and not (rew and rew["start"] + 1 <= f <= rew["end"] + 1)]   # the rewind is rebuilt from the build
        for f in targets:
            p = os.path.join(frames_dir, f"f_{f:04d}.png")
            if os.path.exists(p):
                os.remove(p)
        rr = _ranges(build)
        log.info(f"Redo: {len(targets)} frames ({len(targets) / FPS:.1f}s) in {len(rr)} range(s)"
                 + (" + hook" if in_hook else "") + f"; keeping the other {total_frames - len(targets)} frames")
        baked_frames = None if (os.path.exists(os.path.join(work, "frames", ".clean")) and not restored) \
            else set(targets)                         # restored frames already carry their stickers
        if rr or in_hook:                              # (a rewind-only redo needs no Blender run)
            cmd = [BLENDER, "--background", "--factory-startup", "--python", film_py, "--", film_json, timings_path,
                   work]
            extra = ([f"--ranges={','.join(f'{a}:{b}' for a, b in rr)}"] if rr else ["--range=1:0"]) + \
                (["--hook"] if in_hook else [])
            if validate:                               # re-check only the redone windows
                watcher = sv.SceneWatcher(film, spans, work, spec=spec, only_frames=targets).start()
            _run_blender(cmd + extra, watcher)
        missing = [f for f in range(1, total_frames + 1) if not os.path.exists(os.path.join(work, "frames", f"f_{f:04d}.png"))
                   and not (rew and rew["start"] + 1 <= f <= rew["end"] + 1)]
        if missing and not (watcher and watcher.should_abort()):
            raise RuntimeError(f"--redo: {len(missing)} frames are missing (first {missing[0]}); run a full render")
        args.preview = args.frames = None
    elif not (args.preview or args.frames or resume):
        shutil.rmtree(os.path.join(work, "frames"), ignore_errors=True)
    if film.get("set"):     # the set's BlenderKit props (cutaway-bk sets only; a no-op for sets that build all)
        from agents import blenderkit
        blenderkit.resolve_set_props(os.path.join(PROJECT_ROOT, "engine", "sets", f"{film['set']}.py"),
                                     story=str(film.get("title", "")))
    if not redo:
        log.info("Rendering in Blender...")
    cmd = [BLENDER, "--background", "--factory-startup", "--python", film_py, "--", film_json, timings_path, work]
    extra = (["--preview"] if args.preview else []) + ([f"--frames={args.frames}"] if args.frames else [])
    workers = int(os.getenv("RENDER_WORKERS", "1"))   # measured: 2 = no gain on the laptop GPU
    if validate and not redo:                          # every ~3 s window is judged as soon as it is rendered
        watcher = sv.SceneWatcher(film, spans, work, spec=spec, keep_previous=resume,
                                  preapproved=preapproved).start()
    if redo:
        pass
    elif film.get("set") and not (args.preview or args.frames) and (workers > 1 or resume):
        start, hook = None, True
        if hookless:                                   # no hook staged in an epilogue: frames 1..N
            hook, start = False, 1
            if resume:
                have = {int(os.path.basename(p)[2:6]) for p in glob.glob(os.path.join(work, "frames", "f_*.png"))}
                missing = [f for f in range(1, total_frames + 1) if f not in have]
                start = max(1, missing[0] - 1) if missing else total_frames + 1
                log.info(f"  resume: {len(have)} frames kept, rendering from frame {start}")
        elif resume:                                   # keep finished frames, render only the rest
            have = {int(os.path.basename(p)[2:6]) for p in glob.glob(os.path.join(work, "frames", "f_*.png"))}
            hook = not all(f in have for f in range(spans[0]["start"] + 1, spans[0]["end"] + 2))
            build0 = spans[2]["start"] + 1
            missing = [f for f in range(build0, total_frames + 1) if f not in have]
            start = max(build0, missing[0] - 1) if missing else total_frames + 1   # redo the last (maybe partial) one
            log.info(f"  resume: {len(have)} frames kept, rendering from frame {start}" + (" + hook" if hook else ""))
        if start is None or start <= total_frames or hook:
            _render_parallel(cmd, spans, total_frames, max(1, workers), work, start=start, hook=hook, watcher=watcher)
    else:
        _run_blender(cmd + extra, watcher)
    if watcher is not None:
        verdict = _scene_verdict(args, film, watcher, spans, work)
        if verdict is not None:                        # auto-fixed and re-rendered: that run produced the film
            return verdict
    if args.preview or args.frames:
        log.info(f"Stills in {work}")
        return
    codes = {} if not (redo or resume) else _frame_codes(work)
    fresh = targets if redo else range(1, total_frames + 1)
    if resume and not redo:
        fresh = [f for f in range(1, total_frames + 1) if str(f) not in codes]
    code_now = _code_hash(film)
    for f in fresh:
        codes[str(f)] = code_now
    _save_frame_codes(work, codes)
    _rewind_montage(film, beats, spans, os.path.join(work, "frames"))
    frames = sorted(glob.glob(os.path.join(work, "frames", "f_*.png")))
    log.info(f"Rendered {len(frames)} frames")
    if not redo:                                       # raw frames carry no stickers from now on
        open(os.path.join(work, "frames", ".clean"), "w").close()

    # ---- stickers (spread over all CPU cores: one PNG load/draw/save per frame adds up) ----
    stickers = not _kit_film(film)
    if stickers:
        drop_clashing_stickers(beats, spans, os.path.join(work, "text_boxes.json"))
    cta = film.get("cta") if stickers else None
    cta_from = _cta_start(film, words, len(frames)) if cta else len(frames)
    comp = os.path.join(work, "comp")                  # final frames = raw render + stickers
    shutil.rmtree(comp, ignore_errors=True)
    os.makedirs(comp)
    dst = lambda i: os.path.join(comp, os.path.basename(frames[i]))      # noqa: E731
    jobs = [(frames[i], _overlay(beat), (i - span["start"]) / FPS, dst(i))
            for beat, span in zip(beats, spans) if _overlay(beat)
            for i in range(span["start"], min(span["end"] + 1, len(frames), cta_from))]
    if not stickers:
        jobs = []
    if cta:                                            # end card: the closing question, until the last frame
        jobs += [(frames[i], {"type": "question", "text": cta}, (i - cta_from) / FPS, dst(i))
                 for i in range(cta_from, len(frames))]
    if baked_frames is not None:                       # old render: kept frames already carry their stickers
        jobs = [j for j in jobs if int(os.path.basename(j[0])[2:6]) in baked_frames]
    stickered = {j[3] for j in jobs}
    for i in range(len(frames)):                       # frames without a sticker: a hard link, no copy
        if dst(i) not in stickered:
            try:
                os.link(frames[i], dst(i))
            except OSError:
                shutil.copyfile(frames[i], dst(i))
    if jobs:
        # Threads, never processes: on Windows each pool process re-imports the calling script, and a script that
        # calls produce() without a __main__ guard started a whole render per worker (the oil film: 23 duplicate
        # renders deleting each other's frames). PNG decode/encode releases the GIL, so threads still scale.
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) - 1)) as pool:
            list(pool.map(_sticker_job, jobs))

    subprocess.run([FFMPEG, "-y", "-framerate", str(FPS), "-i", os.path.join(comp, "f_%04d.png"),
                    "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", video],
                   check=True, capture_output=True)
    return _finish(args, film, beats, spans, words, total, work, voice_path, video)


# Effects sit well under the narration: the voice must always win.
SFX_GAIN, WHOOSH_GAIN = 0.32, 0.45


def _ambience_scenes(film, beats, spans):
    """[(start_s, end_s, where)] per beat from its set action (sfx.scene_ambience), or None (one outdoor bed)."""
    if not film.get("set"):
        return None
    from engine import sets as _sets
    sp = _sets.spec(film["set"])
    actions, default = getattr(sp, "ACTIONS", {}), sfx.set_ambience(getattr(sp, "SUBJECT", ""))
    return [(s["start"] / FPS, (s["end"] + 1) / FPS,
             sfx.scene_ambience(actions.get(b.get("action") or (b.get("actions") or [""])[0], {}), default))
            for b, s in zip(beats, spans)]


def _finish(args, film, beats, spans, words, total, work, voice_path, video):
    name = os.path.basename(os.path.normpath(work))[:-len("_work")]   # the film's name (work = <name>_work)
    # ---- sound design ----
    cuts = []                                          # no whoosh on scene changes (too noisy)
    pops = [s["start"] / FPS + 0.18 for b, s in zip(beats, spans) if _overlay(b)]
    if film.get("cta"):
        pops.append(_cta_start(film, words, int(total * FPS)) / FPS + 0.1)
    whoosh = _read_wav(build_fx_track(total, cuts, pops, os.path.join(work, "whoosh.wav")))
    events = json.load(open(os.path.join(work, "events.json"), encoding="utf-8"))
    ids = _beat_ids(beats)
    if "rewind" in ids:                                    # record scratch on the freeze, then the VCR whirr
        r = spans[ids.index("rewind")]
        hold = _rewind_hold(r["end"] - r["start"] + 1)
        events.append({"frame": r["start"] + 1, "kind": "scratch", "duration": 0, "gain": 1.0})
        events.append({"frame": r["start"] + hold + 1, "kind": "rewind",
                       "duration": r["end"] - r["start"] - hold, "gain": 1.0})
    # a film can drop the outdoor bird/wind bed ("ambience": false) and set its own effects level ("sfx_gain")
    synced = _read_wav(sfx.render_events(events, FPS, total, os.path.join(work, "sfx.wav"),
                                         ambience=film.get("ambience", True),
                                         scenes=_ambience_scenes(film, beats, spans)))
    n = max(len(whoosh), len(synced))
    fx = np.zeros(n)
    fx[:len(whoosh)] += whoosh * WHOOSH_GAIN
    fx[:len(synced)] += synced * film.get("sfx_gain", SFX_GAIN)
    fx_path = write_wav(os.path.join(work, "fx_all.wav"), fx, SR)
    music = None
    if film.get("music") == "synth":                       # generated bed (no licensed tracks needed)
        # the whole film's length: a shorter bed is looped by the mixer, and its fade-out/in plus the
        # chord jump at the seam were audible ~60 s into every 90 s film
        music = write_wav(os.path.join(work, "music.wav"), sfx.music(total + 0.5), SR)
    mixed = mix_audio(voice_path, fx_path, os.path.join(work, "mix.m4a"), total, music=music)
    merged = merge_audio_video(video, mixed)

    ass = os.path.join(work, "captions.ass")
    words_to_ass(script_word_timings(beats, words, total), ass, mode=film.get("captions", "phrase"),
                 upper=film.get("captions_upper", False), y=film.get("captions_y"))
    final = burn_subtitles(merged, ass)
    out = os.path.join(get_output_dir(), f"{name}.mp4")
    shutil.move(final, out)
    os.remove(merged)
    final_duration = _assert_file_cap(out)
    preview = os.path.join(get_output_dir(), f"{name}_preview.mp4")
    subprocess.run([FFMPEG, "-v", "error", "-y", "-i", out, "-c:v", "copy", "-c:a", "libopus", "-b:a", "128k",
                    preview], check=True)
    log.info(f"\nFILM: {out} ({final_duration:.1f}s)\nVS Code preview: {preview}")
    if os.getenv("POST_TEXT", "1") != "0":             # ready-to-post TikTok + YouTube text next to the video
        from agents import post_text
        post_text.write(film, out)
    return out


if __name__ == "__main__":
    main()
