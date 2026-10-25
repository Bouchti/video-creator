"""
Autopilot: runs the whole 3D video pipeline unattended and repairs what goes wrong on its own.

    python main.py --source evolution                 # (uses the autopilot)
    python main.py --source cutaway                   # (uses the autopilot)
    python -m agents.autopilot --source evolution --angle "..." --set bridge_evolution
    python -m agents.autopilot --resume output/autopilot/<run>.json   # continue an interrupted run

Stages and what happens when one fails:

  1. script     writer raises (no script passes the rules, Claude error)  → retry; from the 3rd try a
                fresh angle. Claude usage limit → wait for the reset and continue.
  2. render     a) a scene window is REJECTED by the validator → Claude fixes the set's code, the
                   render resumes from that beat (inside make_film, SCENE_POLICY=fix)
                b) Blender crashes with a Python traceback → Claude fixes the set's code, resume
                c) Blender dies without a traceback (GPU / memory / killed) → resume as is
                d) voice (ElevenLabs) or network error → wait and retry; out of credits → stop with a
                   clear message (cannot be fixed by retrying)
                e) still rejected after every fix round → finish the video anyway with
                   SCENE_POLICY=warn, marked NEEDS_REVIEW (or stop: AUTOPILOT_ON_GIVE_UP=fail)
  3. check      the final MP4 is probed: 1080x1920, audio present, duration matches the voice.
                A bad file → rebuild sound + captions (--remix), then a full post-production retry.
  4. notes      <video>.txt with title, caption and hashtags for the upload.

Every automated code fix first backs up the set's file (output/autopilot/backups/); if the run
gives up, the last working version is restored. Every step is recorded in
output/autopilot/<run>.json, so an interrupted run continues where it stopped (--resume).

  AUTOPILOT_MAX_ATTEMPTS=6      render attempts (each one resumes, it never starts over)
  AUTOPILOT_MAX_HOURS=10        overall time budget
  AUTOPILOT_ON_GIVE_UP=ship     ship (marked NEEDS_REVIEW) | fail
"""
import argparse
import datetime
import json
import logging
import os
import re
import shutil
import subprocess
import time
import traceback

from config.paths import PROJECT_ROOT, get_output_dir

log = logging.getLogger("pipeline")
RUNS_DIR = os.path.join(get_output_dir(), "autopilot")
BACKUPS = os.path.join(RUNS_DIR, "backups")


def _int(name, default):
    return int(os.getenv(name) or default)


class GiveUp(RuntimeError):
    """A failure the autopilot cannot repair (e.g. no voice credits left)."""


# ------------------- run record -------------------

class Run:
    def __init__(self, path=None, **meta):
        os.makedirs(RUNS_DIR, exist_ok=True)
        if path and os.path.exists(path):
            self.path = path
            self.data = json.load(open(path, encoding="utf-8"))
        else:
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.path = os.path.join(RUNS_DIR, f"{stamp}_{meta.get('source', 'run')}.json")
            self.data = {"started": stamp, "status": "running", "events": [], **meta}
            self.save()

    def __getitem__(self, k):
        return self.data.get(k)

    def set(self, **kv):
        self.data.update(kv)
        self.save()

    def event(self, stage, what, **kv):
        e = {"time": datetime.datetime.now().isoformat(timespec="seconds"), "stage": stage, "what": what, **kv}
        self.data["events"].append(e)
        log.info(f"[autopilot] {stage}: {what}" + (f" ({kv.get('detail')})" if kv.get("detail") else ""))
        self.save()

    def save(self):
        tmp = self.path + ".tmp"
        json.dump(self.data, open(tmp, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        os.replace(tmp, self.path)


# ------------------- helpers -------------------

def _wait_for_claude(exc, run, stage):
    """Claude subscription limit: sleep until the reset Claude announced (or an hour)."""
    reset = getattr(exc, "reset", None)
    wait = (reset - datetime.datetime.now()).total_seconds() + 90 if reset else 3600
    run.event(stage, "Claude usage limit reached; waiting for the reset", detail=f"{wait / 60:.0f} min")
    time.sleep(max(60, wait))


def _is_usage_limit(exc):
    from agents.showrunner import UsageLimit
    return isinstance(exc, UsageLimit) or ("limit" in str(exc).lower() and "reset" in str(exc).lower())


def _set_file(set_id):
    return os.path.join(PROJECT_ROOT, "engine", "sets", f"{set_id}.py")


def _backup(set_id, run):
    os.makedirs(BACKUPS, exist_ok=True)
    src = _set_file(set_id)
    dst = os.path.join(BACKUPS, f"{set_id}_{datetime.datetime.now():%Y%m%d_%H%M%S}.py")
    shutil.copyfile(src, dst)
    first = run["first_backup"] or dst
    run.set(first_backup=first)
    return dst


def _restore_first_backup(set_id, run):
    b = run["first_backup"]
    if b and os.path.exists(b):
        shutil.copyfile(b, _set_file(set_id))
        run.event("render", "restored the set's last working code", detail=os.path.basename(b))


def probe(path):
    """1080x1920 video, an audio stream, a sane duration."""
    from agents.editor_hailuo import FFMPEG
    ffprobe = shutil.which("ffprobe") or FFMPEG.replace("ffmpeg", "ffprobe")
    r = subprocess.run([ffprobe, "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration",
                        "-of", "json", path], capture_output=True, text=True)
    problems = []
    try:
        info = json.loads(r.stdout)
    except json.JSONDecodeError:
        return [f"ffprobe could not read {path}"]
    streams = info.get("streams", [])
    video = [s for s in streams if s.get("codec_type") == "video"]
    if not video:
        problems.append("no video stream")
    elif (video[0].get("width"), video[0].get("height")) != (1080, 1920):
        problems.append(f"video is {video[0].get('width')}x{video[0].get('height')}, not 1080x1920")
    if not any(s.get("codec_type") == "audio" for s in streams):
        problems.append("no audio stream")
    dur = float(info.get("format", {}).get("duration") or 0)
    if not 15 <= dur <= 180:
        problems.append(f"duration {dur:.1f}s is outside 15-180 s")
    return problems


def write_notes(video, film_json):
    film = json.load(open(film_json, encoding="utf-8"))
    meta = film.get("meta", {})
    lines = [film.get("title", ""), "", meta.get("caption", ""), "", " ".join(meta.get("hashtags", []))]
    path = os.path.splitext(video)[0] + ".txt"
    open(path, "w", encoding="utf-8").write("\n".join(lines).strip() + "\n")
    return path


# ------------------- stages -------------------

def stage_script(run, source, angle, set_id):
    if run["film"] and os.path.exists(run["film"]):
        return run["film"]
    for attempt in range(1, 7):
        try:
            use_angle = angle if attempt <= 2 else None          # from the 3rd try: let it pick a fresh angle
            if source == "evolution":
                from agents.evolution_writer import run as write
                path = write(angle=use_angle, set_id=set_id, render=False)
            else:
                from agents.showrunner import run as write
                path = write(angle=use_angle, render=False)
            run.set(film=path)
            run.event("script", "script written", detail=os.path.basename(path))
            return path
        except Exception as exc:                          # noqa: BLE001
            if _is_usage_limit(exc):
                _wait_for_claude(exc, run, "script")
                continue
            run.event("script", f"attempt {attempt} failed; retrying", detail=str(exc)[:300])
            time.sleep(min(300, 20 * attempt))
    raise GiveUp("no script could be written after 6 attempts")


def _voice_error(exc):
    text = str(exc).lower()
    if "out of credits" in text or "no elevenlabs key" in text or "not configured" in text:
        raise GiveUp(f"voiceover cannot be made: {exc}")
    return "elevenlabs" in text or "requests" in text or "connection" in text or "timed out" in text


def stage_render(run, film_json):
    """make_film with scene validation + auto-fix; every failure is classified, repaired, resumed."""
    from agents import scene_validator as sv
    from agents.set_builder import fix_code
    from engine.make_film import BlenderFailed, produce

    film = json.load(open(film_json, encoding="utf-8"))
    set_id = film.get("set")
    os.environ["SCENE_POLICY"] = "fix"                      # autopilot: a rejected scene is always repaired
    os.environ["SCENE_VALIDATE"] = os.getenv("SCENE_VALIDATE") or "1"   # validate cutaway films too
    os.environ["SCENE_FIX_ATTEMPTS"] = os.getenv("SCENE_FIX_ATTEMPTS") or "3"
    max_attempts = _int("AUTOPILOT_MAX_ATTEMPTS", 6)
    deadline = time.time() + float(os.getenv("AUTOPILOT_MAX_HOURS") or 10) * 3600
    attempt = run["render_attempts"] or 0
    while True:
        attempt += 1
        run.set(render_attempts=attempt)
        work = os.path.join(get_output_dir(), f"{os.path.splitext(os.path.basename(film_json))[0]}_work")
        has_voice = os.path.exists(os.path.join(work, "voice.mp3"))
        has_frames = os.path.isdir(os.path.join(work, "frames")) and os.listdir(os.path.join(work, "frames"))
        args = argparse.Namespace(film=film_json, reuse_voice=has_voice, preview=False, frames="", remix=False,
                                  resume=bool(has_frames and attempt > 1), redo="", list=False)
        try:
            if set_id:
                _backup(set_id, run)
            out = produce(args)
            run.event("render", "film rendered", detail=os.path.basename(out))
            return out, False
        except sv.SceneRejected as exc:
            # make_film already ran its fix rounds; out of rounds for this attempt
            run.event("render", "scenes still rejected after the fix rounds", detail=str(exc)[:400])
            if attempt < max_attempts and time.time() < deadline:
                os.environ["SCENE_FIX_ATTEMPTS"] = "2"
                continue
            return _give_up(run, film_json, set_id, exc)
        except BlenderFailed as exc:
            if exc.is_code_error and set_id:
                run.event("render", "Blender crashed in the set's code; Claude is fixing it",
                          detail=exc.log[exc.log.rfind("Traceback"):][:300])
                try:
                    fix_code(set_id, exc.log)
                except Exception as fx:                   # noqa: BLE001
                    if _is_usage_limit(fx):
                        _wait_for_claude(fx, run, "render")
                    else:
                        run.event("render", "code fix failed", detail=str(fx)[:200])
            else:
                run.event("render", "Blender stopped without a code error (GPU / memory); resuming",
                          detail=exc.log[-200:])
                time.sleep(30)
        except GiveUp:
            raise
        except Exception as exc:                          # noqa: BLE001
            if _is_usage_limit(exc):
                _wait_for_claude(exc, run, "render")
            elif _voice_error(exc):
                run.event("render", "voice / network error; retrying in 2 min", detail=str(exc)[:200])
                time.sleep(120)
            else:
                run.event("render", "unexpected error; retrying", detail=traceback.format_exc()[-600:])
                time.sleep(30)
        if attempt >= max_attempts or time.time() > deadline:
            return _give_up(run, film_json, set_id, RuntimeError("out of render attempts"))


def _give_up(run, film_json, set_id, exc):
    """Every repair round is spent: ship the video marked NEEDS_REVIEW (default), or fail."""
    from engine.make_film import produce
    if (os.getenv("AUTOPILOT_ON_GIVE_UP") or "ship").lower() == "fail":
        if set_id:
            _restore_first_backup(set_id, run)
        raise GiveUp(f"render could not be repaired: {exc}")
    run.event("render", "finishing the video anyway (scenes flagged); it will be marked NEEDS_REVIEW")
    os.environ["SCENE_POLICY"] = "warn"
    args = argparse.Namespace(film=film_json, reuse_voice=True, preview=False, frames="", remix=False,
                              resume=True, redo="", list=False)
    try:
        return produce(args), True
    except Exception as first:                       # noqa: BLE001  the automated fixes made it worse:
        if not set_id:
            raise GiveUp(f"render failed: {first}")
        _restore_first_backup(set_id, run)           # back to the code that worked, render the rest with it
        try:
            return produce(args), True
        except Exception as exc2:                    # noqa: BLE001
            raise GiveUp(f"render failed even with the original code: {exc2}")


def stage_check(run, video, film_json):
    from engine.make_film import produce
    for attempt in range(1, 3):
        problems = probe(video)
        if not problems:
            run.event("check", "final video checked: 1080x1920, audio, duration OK")
            return video
        run.event("check", f"final video has problems; rebuilding post-production (try {attempt})",
                  detail="; ".join(problems))
        args = argparse.Namespace(film=film_json, reuse_voice=True, preview=False, frames="", remix=True,
                                  resume=False, redo="", list=False)
        video = produce(args)
    problems = probe(video)
    if problems:
        raise GiveUp(f"final video still invalid: {problems}")
    return video


# ------------------- the run -------------------

def run(source="evolution", angle=None, set_id=None, resume_path=None):
    r = Run(resume_path, source=source, angle=angle, set=set_id)
    source, angle, set_id = r["source"] or source, r["angle"], r["set"]
    t0 = time.time()
    try:
        film_json = stage_script(r, source, angle, set_id)
        video, flagged = stage_render(r, film_json)
        video = stage_check(r, video, film_json)
        if flagged:
            flagged_path = re.sub(r"\.mp4$", "_NEEDS_REVIEW.mp4", video)
            shutil.move(video, flagged_path)
            video = flagged_path
        notes = write_notes(video, film_json)
        r.set(status="needs_review" if flagged else "done", video=video, notes=notes,
              minutes=round((time.time() - t0) / 60, 1))
        log.info(f"[autopilot] {'DONE' if not flagged else 'DONE (NEEDS REVIEW)'}: {video}\n"
                 f"  upload notes: {notes}\n  run log: {r.path}")
        return video
    except GiveUp as exc:
        r.set(status="failed", error=str(exc))
        log.error(f"[autopilot] STOPPED: {exc}\n  run log: {r.path}\n  continue later with: "
                  f"python -m agents.autopilot --resume \"{r.path}\"")
        raise


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    ap = argparse.ArgumentParser(description="Make a 3D video end to end, repairing failures automatically.")
    ap.add_argument("--source", choices=["evolution", "cutaway"], default="evolution")
    ap.add_argument("--angle", default=None)
    ap.add_argument("--set", default=None, help="evolution set (default: the first registered)")
    ap.add_argument("--resume", default=None, help="continue a run from its output/autopilot/<run>.json")
    a = ap.parse_args()
    print(run(a.source, a.angle, a.set, a.resume))


if __name__ == "__main__":
    main()
