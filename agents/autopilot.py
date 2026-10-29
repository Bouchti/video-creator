r"""
Autopilot: runs the whole 3D video pipeline unattended and repairs what goes wrong on its own.

    python main.py --source evolution                 # (uses the autopilot)
    python main.py --source cutaway                   # (uses the autopilot)
    python main.py --source explainer                 # (uses the autopilot; no-hero cutaway explainers)
    .\venv\Scripts\python.exe -m agents.autopilot --source evolution --angle "..." --set bridge_evolution
    .\venv\Scripts\python.exe -m agents.autopilot --resume output/autopilot/<run>.json

Stages and what happens when one fails:

  1. script     writer raises (no script passes the rules, Claude error)  → retry; from the 3rd try a
                fresh angle. Claude usage limit → wait for the reset and continue.
  2. render     a) a scene window is REJECTED by the validator → Claude fixes the set's code, the
                   render resumes from that beat (inside make_film, SCENE_POLICY=fix)
                b) Blender crashes with a Python traceback → Claude fixes the set's code, resume
                c) Blender dies without a traceback (GPU / memory / killed) → resume as is
                d) voice (ElevenLabs) or network error → wait and retry; out of credits → stop with a
                   clear message (cannot be fixed by retrying)
                e) still rejected after every fix round → stop safely (shipping requires the explicit
                   AUTOPILOT_ON_GIVE_UP=ship override and is never the default)
  3. check      the final MP4 is probed: 1080x1920, audio present, duration matches the voice.
                A bad file → rebuild sound + captions (--remix), then a full post-production retry.
  4. notes      <video>.txt with title, caption and hashtags for the upload.

Every automated code fix first backs up the set's file (output/autopilot/backups/); if the run
gives up, the last working version is restored. Every step is recorded in
output/autopilot/<run>.json, so an interrupted run continues where it stopped (--resume).

  AUTOPILOT_MAX_ATTEMPTS=6      render attempts (each one resumes, it never starts over)
  AUTOPILOT_MAX_HOURS=10        overall time budget
  AUTOPILOT_ON_GIVE_UP=ship     ship a flagged draft | fail (strict accepted-only mode)
"""
import argparse
import datetime
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import traceback

from config.paths import PROJECT_ROOT, get_output_dir

log = logging.getLogger("pipeline")
RUNS_DIR = os.path.join(get_output_dir(), "autopilot")
BACKUPS = os.path.join(RUNS_DIR, "backups")


def _int(name, default):
    return int(os.getenv(name) or default)


def _enabled(name, default=True):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


class GiveUp(RuntimeError):
    """A failure the autopilot cannot repair (e.g. no voice credits left)."""


def _project_python():
    """The installed project interpreter, falling back to the one running us."""
    scripts = "Scripts" if os.name == "nt" else "bin"
    executable = "python.exe" if os.name == "nt" else "python"
    relative = os.path.join("venv", scripts, executable)
    candidate = os.path.join(PROJECT_ROOT, relative)
    return candidate if os.path.isfile(candidate) else sys.executable


def _resume_command(path):
    python = _project_python()
    try:
        python = os.path.relpath(python, PROJECT_ROOT)
        if not python.startswith("."):
            python = "." + os.sep + python
    except ValueError:                                      # another Windows drive
        python = f'& "{python}"'
    return f'{python} -m agents.autopilot --resume "{path}"'


def _require_runtime():
    """Fail before paid work when the command used an interpreter without project dependencies."""
    try:
        import requests  # noqa: F401
    except ModuleNotFoundError as exc:
        raise GiveUp(f"project dependency '{exc.name or 'requests'}' is missing from {sys.executable}; "
                     f"run this project with {_project_python()}") from exc


# ------------------- run record -------------------

class Run:
    def __init__(self, path=None, **meta):
        os.makedirs(RUNS_DIR, exist_ok=True)
        if path and os.path.exists(path):
            self.path = path
            self.data = json.load(open(path, encoding="utf-8"))
            from agents.showrunner import carry_tokens
            carry_tokens(self.data.get("claude_tokens"))   # the budget covers the whole run, across resumes
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
        from agents.showrunner import tokens_used
        self.data["claude_tokens"] = tokens_used()
        tmp = self.path + ".tmp"
        json.dump(self.data, open(tmp, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        os.replace(tmp, self.path)


# ------------------- helpers -------------------

def _wait_for_claude(exc, run, stage):
    """Wait only for a known, near-term subscription reset; never sleep on a guess."""
    reset = getattr(exc, "reset", None)
    if reset is None:
        run.event(stage, "all configured AI backends are unavailable; stopped safely",
                  detail="no reset time was supplied; resume later")
        raise GiveUp("Codex models and the Claude fallback are currently unavailable; no reset time "
                     "was supplied, so the run was stopped instead of sleeping blindly. Resume it later.") from exc
    wait = (reset - datetime.datetime.now()).total_seconds() + 90
    max_wait = float(os.getenv("SHOWRUNNER_MAX_WAIT", "65")) * 60
    if wait > max_wait:
        run.event(stage, "AI reset is beyond the automatic wait limit; stopped safely",
                  detail=f"reset in {wait / 60:.0f} min; limit {max_wait / 60:.0f} min")
        raise GiveUp(f"AI subscriptions reset in {wait / 60:.0f} minutes, beyond the configured "
                     f"{max_wait / 60:.0f}-minute wait limit. Resume the run after the reset.") from exc
    run.event(stage, "AI subscription usage limit reached; waiting for the reset", detail=f"{wait / 60:.0f} min")
    time.sleep(max(60, wait))


def _is_usage_limit(exc):
    from agents.showrunner import UsageLimit
    return isinstance(exc, UsageLimit) or ("limit" in str(exc).lower() and "reset" in str(exc).lower())


def _is_budget(exc):
    """A spent token budget is not a transient failure: retrying only spends more."""
    from agents.showrunner import BudgetExceeded
    return isinstance(exc, BudgetExceeded)


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
    from agents.media import FFMPEG
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
    set_id = run["generated_set"] or set_id
    max_attempts = _int("AUTOPILOT_SCRIPT_ATTEMPTS", 3)
    for attempt in range(1, max_attempts + 1):
        try:
            use_angle = angle if attempt <= 2 else None          # from the 3rd try: let it pick a fresh angle
            if source == "evolution":
                from agents.evolution_writer import run as write
                path = write(angle=use_angle, set_id=set_id, render=False)
            elif source == "explainer":
                path = _explainer_script(run, use_angle, set_id)
            else:
                from agents.showrunner import NoUnusedStorySets, plan_new_story_set, run as write
                topic_hint = run["script_topic"]
                selected_set = set_id or ((topic_hint or {}).get("set"))

                def remember_topic(topic):
                    run.set(script_topic=topic)

                try:
                    path = write(angle=use_angle, render=False, set_id=selected_set,
                                 topic_hint=topic_hint, on_topic=remember_topic)
                except NoUnusedStorySets as exc:
                    if selected_set or not _enabled("SHOWRUNNER_AUTO_BUILD_SETS", True):
                        raise GiveUp(str(exc)) from exc
                    plan = run["new_set_plan"]
                    kit = (os.getenv("SHOWRUNNER_SET_MODE") or "kit").strip().lower() == "kit"
                    if not plan:
                        run.event("script", "all existing Max subjects are consumed; researching a new one")
                        if kit:
                            from agents import kit_world
                            from agents.kit_planner import plan_kit_story
                            from agents.showrunner import _history
                            published = "\n".join(f"- {h.get('title')}" for h in _history()[-40:]) or "- none"
                            try:              # the world (and every object in it) exists before the story
                                world = (kit_world.ensure_world(use_angle, run.event) if use_angle
                                         else kit_world.pick_world())
                            except kit_world.WorldNotBuilt as exc:
                                raise GiveUp(str(exc)) from exc
                            plan = plan_kit_story(published, world=world)
                        else:
                            plan = plan_new_story_set()
                        run.set(new_set_plan=plan)
                    if plan.get("storyboard"):
                        # the kit films a storyboard: no code is written, nothing is repaired by an agent
                        from agents.set_builder import KitDefect, build_kit_set
                        run.event("set", "filming the planned storyboard with the kit",
                                  detail=f"{plan['title']} ({plan['set_id']})")
                        try:
                            status = build_kit_set(plan)
                        except KitDefect as defect:
                            raise GiveUp(str(defect)) from defect
                        plan["set_id"] = status["set"]
                        run.set(new_set_plan=plan)
                    else:
                        from agents.set_builder import build_story_set
                        run.event("set", "building and visually validating a new Max set",
                                  detail=f"{plan['subject']} ({plan['set_id']})")
                        status = build_story_set(plan["build_brief"], plan["set_id"],
                                                 rounds=_int("SET_BUILD_ROUNDS", 4))
                    if not status.get("accepted"):
                        raise GiveUp(f"new set '{plan['set_id']}' did not pass visual validation; "
                                     f"continue it in {status.get('work')}")
                    set_id = plan["set_id"]
                    run.set(generated_set=set_id, set=set_id, set_build=status)
                    run.event("set", "new Max set accepted and registered", detail=set_id)
                    path = write(angle=use_angle, render=False, set_id=set_id, topic_hint=plan,
                                 on_topic=remember_topic)
            run.set(film=path)
            run.event("script", "script written", detail=os.path.basename(path))
            return path
        except GiveUp:
            raise
        except Exception as exc:                          # noqa: BLE001
            if _is_budget(exc):
                raise GiveUp(str(exc)) from exc
            if isinstance(exc, ModuleNotFoundError):
                raise GiveUp(f"pipeline dependency/module '{exc.name or str(exc)}' is missing; retries cannot "
                             f"install it. Run the pipeline with {_project_python()}") from exc
            from agents.set_builder import RepairNotApplied
            if isinstance(exc, RepairNotApplied):
                # A set repair that changed nothing would get the same inputs again on a retry: stop instead.
                raise GiveUp(f"the set repair made no changes; retrying would repeat the same paid turn: "
                             f"{exc}") from exc
            if _is_usage_limit(exc):
                _wait_for_claude(exc, run, "script")
                continue
            if isinstance(exc, (TypeError, AttributeError, KeyError, IndexError)):
                raise GiveUp(f"pipeline code error; retries would repeat the same work: {exc}") from exc
            run.event("script", f"attempt {attempt} failed; retrying", detail=str(exc)[:300])
            time.sleep(min(300, 20 * attempt))
    raise GiveUp(f"no script could be written after {max_attempts} attempts")


def _explainer_script(run, angle, set_id):
    """Explainer route: reuse a registered no-hero set, or research, build and register a new one."""
    from agents import explainer

    def remember_topic(topic):
        run.set(script_topic=topic)

    hint = run["script_topic"]
    if run["generated_set"]:                                   # resumed after the new set was accepted
        return explainer.write(angle, run["generated_set"], topic_hint=hint or run["new_set_plan"],
                               on_topic=remember_topic)
    chosen = set_id or (hint or {}).get("set")
    if not chosen and not run["new_set_plan"]:
        chosen = explainer.choose_set(angle)                   # "" = any unused set, None = needs a new set
        if chosen is not None:
            run.event("script", "explainer set chosen", detail=chosen or "showrunner picks among unused sets")
    if chosen is not None and not run["new_set_plan"]:
        try:
            return explainer.write(angle, chosen or None, topic_hint=hint, on_topic=remember_topic)
        except explainer.NoUnusedExplainerSets as exc:
            if set_id or not _enabled("SHOWRUNNER_AUTO_BUILD_SETS", True):
                raise GiveUp(str(exc)) from exc
            run.event("script", "no registered explainer set can carry today's video", detail=str(exc)[:200])
    elif not _enabled("SHOWRUNNER_AUTO_BUILD_SETS", True) and not run["new_set_plan"]:
        raise GiveUp("no registered explainer set fits this topic and SHOWRUNNER_AUTO_BUILD_SETS=0")
    plan = run["new_set_plan"]
    kit = (os.getenv("SHOWRUNNER_SET_MODE") or "kit").strip().lower() == "kit"
    if not plan:
        run.event("script", "researching a new explainer subject")
        try:
            if kit:                   # the Max architecture: a storyboard the tested kit films, no code written
                from agents import kit_world
                from agents.kit_planner import plan_kit_explainer
                from agents.showrunner import _history
                published = "\n".join(f"- {h.get('title')}" for h in _history()[-40:]) or "- none"
                try:                  # the world (and every object in it) exists before the storyboard
                    world = kit_world.ensure_world(angle, run.event) if angle else kit_world.pick_world()
                except kit_world.WorldNotBuilt as exc:
                    raise GiveUp(str(exc)) from exc
                plan = plan_kit_explainer(published, angle, world=world)
            else:
                plan = explainer.plan_new_set(angle)
        except explainer.NoUnusedExplainerSets as exc:
            raise GiveUp(str(exc)) from exc
        run.set(new_set_plan=plan)
    if plan.get("storyboard"):
        from agents.set_builder import KitDefect, build_kit_set
        run.event("set", "filming the planned explainer storyboard with the kit",
                  detail=f"{plan['title']} ({plan['set_id']})")
        try:
            status = build_kit_set(plan)
        except KitDefect as defect:
            raise GiveUp(str(defect)) from defect
        plan["set_id"] = status["set"]
        run.set(new_set_plan=plan)
    else:
        from agents.set_builder import build_explainer_set
        run.event("set", "building and visually validating a new explainer set",
                  detail=f"{plan['subject']} ({plan['set_id']})")
        status = build_explainer_set(plan["build_brief"], plan["set_id"], rounds=_int("SET_BUILD_ROUNDS", 4),
                                     hook_action=plan.get("hook_action"))
    if not status.get("accepted"):
        raise GiveUp(f"new explainer set '{plan['set_id']}' did not pass visual validation; "
                     f"continue it in {status.get('work')}")
    run.set(generated_set=plan["set_id"], set=plan["set_id"], set_build=status)
    run.event("set", "new explainer set accepted and registered", detail=plan["set_id"])
    return explainer.write(angle, plan["set_id"], topic_hint=plan, on_topic=remember_topic)


def _voice_error(exc):
    text = str(exc).lower()
    if "out of credits" in text or "no elevenlabs key" in text or "not configured" in text:
        raise GiveUp(f"voiceover cannot be made: {exc}")
    return "elevenlabs" in text or "requests" in text or "connection" in text or "timed out" in text


def stage_render(run, film_json):
    """make_film with scene validation + auto-fix; every failure is classified, repaired, resumed."""
    from agents import scene_validator as sv
    from agents.set_builder import KitDefect, RepairNotApplied, fix_code
    from engine.make_film import BlenderFailed, produce

    film = json.load(open(film_json, encoding="utf-8"))
    set_id = film.get("set")
    from engine import sets as _sets
    kit = bool(set_id) and bool(getattr(_sets.spec(set_id), "KIT", None))
    if kit:
        # a kit set was measured when its storyboard was filmed and has no agent repair path: no paid
        # rehearsal or film review (a defect there is a kit bug, fixed once in engine/kit)
        os.environ["SCENE_VALIDATE"] = "0"
        os.environ["SCENE_PREFLIGHT"] = "0"
    os.environ["SCENE_POLICY"] = "fix"                      # autopilot: a rejected scene is always repaired
    os.environ["SCENE_VALIDATE"] = os.getenv("SCENE_VALIDATE") or "1"   # validate cutaway films too
    # Both Blender cutaway routes use this stage: Max stories and no-hero explainers must pass the
    # exact final-timing rehearsal before their first production frame is allowed to render.
    os.environ["SCENE_PREFLIGHT"] = os.getenv("SCENE_PREFLIGHT") or "1"
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
        # Any frames in the work directory are completed work, including on the first attempt of a
        # manually resumed process (run() renews the attempt counter). Basing this on attempt > 1
        # made `--resume` erase an interrupted render before starting it again.
        args = argparse.Namespace(film=film_json, reuse_voice=has_voice, preview=False, frames="", remix=False,
                                  resume=bool(has_frames), redo="", list=False)
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
            if kit and exc.is_code_error:
                raise GiveUp(f"the kit crashed rendering '{set_id}' (a kit bug: fix engine/kit, never this video): "
                             f"{exc.log[exc.log.rfind('Traceback'):][:600]}") from exc
            if exc.is_code_error and set_id:
                run.event("render", "Blender crashed in the set's code; Claude is fixing it",
                          detail=exc.log[exc.log.rfind("Traceback"):][:300])
                try:
                    fix_code(set_id, exc.log)
                except RepairNotApplied:
                    raise
                except Exception as fx:                   # noqa: BLE001
                    if _is_budget(fx):
                        raise GiveUp(str(fx)) from fx
                    if _is_usage_limit(fx):
                        _wait_for_claude(fx, run, "render")
                    else:
                        run.event("render", "code fix failed", detail=str(fx)[:200])
            else:
                run.event("render", "Blender stopped without a code error (GPU / memory); resuming",
                          detail=exc.log[-200:])
                time.sleep(30)
        except GiveUp as exc:
            # Do not strand a nearly complete film when an AI backend or token budget is
            # exhausted. Existing frames can be finished without further model calls.
            if has_frames:
                return _give_up(run, film_json, set_id, exc)
            raise
        except RepairNotApplied as exc:
            raise GiveUp(f"automatic scene repair could not edit the set; stopped before wasting another render: "
                         f"{exc}") from exc
        except KitDefect as exc:
            # the prepare stage found a missing or broken object before any frame: a kit bug, same on a retry
            run.event("render", "the kit scene failed its prepare check; nothing was rendered", detail=str(exc)[:400])
            raise GiveUp(str(exc)) from exc
        except Exception as exc:                          # noqa: BLE001
            if _is_budget(exc):
                return _give_up(run, film_json, set_id, exc)
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
    """Finish a flagged draft after exhausted repairs; strict failure is an explicit opt-in."""
    from engine.make_film import produce
    if (os.getenv("AUTOPILOT_ON_GIVE_UP") or "ship").lower() == "fail":
        if set_id:
            _restore_first_backup(set_id, run)
        raise GiveUp(f"render could not be repaired: {exc}")
    run.event("render", "finishing the video anyway (scenes flagged); it will be marked NEEDS_REVIEW")
    # These frames were already reviewed. Re-running the watcher while assembling a fallback
    # burns another model batch and can fail again when the subscription quota is exhausted.
    os.environ["SCENE_VALIDATE"] = "0"
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
        if len(problems) == 1 and problems[0].startswith("video is ") and _normalize_final_resolution(video):
            run.event("check", "normalized the completed 9:16 video to 1080x1920",
                      detail=problems[0])
            continue
        run.event("check", f"final video has problems; rebuilding post-production (try {attempt})",
                  detail="; ".join(problems))
        args = argparse.Namespace(film=film_json, reuse_voice=True, preview=False, frames="", remix=True,
                                  resume=False, redo="", list=False)
        video = produce(args)
    problems = probe(video)
    if problems:
        raise GiveUp(f"final video still invalid: {problems}")
    return video


def _normalize_final_resolution(video):
    """Upscale a completed 9:16 encode without rerendering thousands of Blender frames."""
    from agents.media import FFMPEG, get_dimensions
    try:
        width, height = get_dimensions(video)
    except Exception:                                     # noqa: BLE001  normal repair can still run
        return False
    if not width or not height or width * 16 != height * 9:
        return False
    tmp = os.path.splitext(video)[0] + ".normalized.tmp.mp4"
    try:
        result = subprocess.run([
            FFMPEG, "-y", "-i", video, "-vf", "scale=1080:1920:flags=lanczos,setsar=1",
            "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
            "-c:a", "copy", "-movflags", "+faststart", tmp,
        ], capture_output=True, text=True, timeout=1800)
        if result.returncode:
            log.warning(f"[autopilot] final resolution normalization failed: {result.stderr[-300:]}")
            return False
        os.replace(tmp, video)
        return True
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _cleanup_successful_work(film_json):
    """Drop reproducible frame caches after a validated run; retain voice, reports and encoded video."""
    if _enabled("AUTOPILOT_KEEP_WORKFILES", False):
        return 0
    output_root = os.path.realpath(get_output_dir())
    name = os.path.splitext(os.path.basename(film_json))[0]
    work = os.path.realpath(os.path.join(output_root, name + "_work"))
    if os.path.commonpath((output_root, work)) != output_root or not work.endswith("_work"):
        raise RuntimeError(f"refusing to clean unexpected work path: {work}")
    freed, seen_files = 0, set()
    for leaf in ("frames", "comp"):
        target = os.path.join(work, leaf)
        if os.path.isdir(target):
            for root, _, files in os.walk(target):
                for filename in files:
                    try:
                        stat = os.stat(os.path.join(root, filename))
                        identity = (stat.st_dev, stat.st_ino)
                        if identity not in seen_files:
                            freed += stat.st_size
                            seen_files.add(identity)
                    except OSError:
                        pass
            shutil.rmtree(target)
    if freed:
        log.info(f"[autopilot] removed reproducible render frames ({freed / 1024 ** 3:.1f} GB); "
                 "set AUTOPILOT_KEEP_WORKFILES=1 to retain them for manual --redo")
    return freed


# ------------------- the run -------------------

def run(source="evolution", angle=None, set_id=None, resume_path=None):
    r = Run(resume_path, source=source, angle=angle, set=set_id)
    if resume_path:
        # A manual resume is a fresh repair session. Source may have been corrected between runs;
        # make that current version the new rollback baseline and renew the bounded attempt budget.
        previous_error = r["error"]
        r.set(status="running", error=None, render_attempts=0, first_backup=None)
        # Attempt three deliberately tries a fresh subject.  If all script attempts failed, that rejected
        # subject must not replace an explicit angle on the next manual resume.
        if previous_error and "no script could be written" in previous_error and r["angle"] and not r["film"]:
            r.set(script_topic=None)
        if previous_error and "final video still invalid" in previous_error and not r["video"] and r["film"]:
            # Older runs did not persist the completed encode until after validation.  Recover it so a
            # resolution-only failure can be repaired without rebuilding audio, captions, or Blender frames.
            name = os.path.splitext(os.path.basename(r["film"]))[0]
            candidate = os.path.join(get_output_dir(), f"{name}.mp4")
            if os.path.isfile(candidate):
                r.set(video=candidate, render_flagged=False)
    source, angle, set_id = r["source"] or source, r["angle"], r["set"]
    t0 = time.time()
    try:
        _require_runtime()
        film_json = stage_script(r, source, angle, set_id)
        if r["video"] and os.path.isfile(r["video"]):
            video, flagged = r["video"], bool(r["render_flagged"])
            r.event("render", "reusing the completed video for final validation", detail=os.path.basename(video))
        else:
            video, flagged = stage_render(r, film_json)
            r.set(video=video, render_flagged=flagged)
        video = stage_check(r, video, film_json)
        if flagged:
            flagged_path = re.sub(r"\.mp4$", "_NEEDS_REVIEW.mp4", video)
            shutil.move(video, flagged_path)
            video = flagged_path
        notes = write_notes(video, film_json)
        if not flagged:
            _cleanup_successful_work(film_json)
        r.set(status="needs_review" if flagged else "done", video=video, notes=notes,
              minutes=round((time.time() - t0) / 60, 1))
        log.info(f"[autopilot] {'DONE' if not flagged else 'DONE (NEEDS REVIEW)'}: {video}\n"
                 f"  upload notes: {notes}\n  run log: {r.path}")
        return video
    except GiveUp as exc:
        r.set(status="failed", error=str(exc))
        log.error(f"[autopilot] STOPPED: {exc}\n  run log: {r.path}\n  continue later with: "
                  f"{_resume_command(r.path)}")
        raise
    except KeyboardInterrupt:
        r.set(status="interrupted", error="stopped by user")
        log.error(f"[autopilot] INTERRUPTED\n  run log: {r.path}")
        raise
    except BaseException as exc:
        r.set(status="failed", error=str(exc) or type(exc).__name__)
        log.exception(f"[autopilot] FAILED: {exc}\n  run log: {r.path}")
        raise


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    ap = argparse.ArgumentParser(description="Make a 3D video end to end, repairing failures automatically.")
    ap.add_argument("--source", choices=["evolution", "cutaway", "explainer"], default="evolution")
    ap.add_argument("--angle", default=None)
    ap.add_argument("--set", default=None, help="evolution set (default: the first registered)")
    ap.add_argument("--resume", default=None, help="continue a run from its output/autopilot/<run>.json")
    a = ap.parse_args()
    try:
        print(run(a.source, a.angle, a.set, a.resume))
    except GiveUp:                       # already logged with the resume command; no traceback
        sys.exit(1)


if __name__ == "__main__":
    main()
