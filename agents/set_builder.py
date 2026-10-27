"""
Auto set builder: Claude creates a whole new 3D evolution or Max-story set (spec + Blender builder
and reference script), renders it, LOOKS at the result, and fixes it until every beat is accepted.
A set is only registered once it passes.

    python -m agents.set_builder "from a raft to a container ship"
    python -m agents.set_builder "how castles evolved" --id castle_evolution --rounds 5
    python -m agents.set_builder --fix bridge_evolution --report output/bridge_evolution_work/scene_review.json

Steps:
  1. design + write   Claude (Claude Code headless, on your subscription) reads the kit
                      (engine/evo_kit.py) and the reference bridge set, then writes
                      engine/sets/<id>_spec.py, engine/sets/<id>.py and engine/films/<id>.json
  2. static checks    the spec imports, the reference script passes the spec's rules, the
                      builder compiles; errors go back to Claude
  3. preview render   Blender renders 3 stills per beat (no voice needed: timings come from the
                      word counts); a Blender traceback goes back to Claude
  4. scene review     every beat's stills go through agents/scene_validator (technical QC +
                      Claude vision: does it show the action, is it readable, is it clean)
  5. fix + repeat     rejected beats (with the reviewer's problems and fix, and the image files)
                      go back to Claude, up to --rounds times
  6. accept           all beats accepted → the set is added to EVOLUTION in engine/sets/__init__.py
                      and a contact sheet is saved in output/sets/<id>/

The coding agent works in an isolated source mirror; only the set's own files are copied back.
Needs the selected subscription CLI (`codex` by default) and Blender (BLENDER_EXE).
"""
import argparse
import glob
import hashlib
import json
import logging
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile

from config.paths import PROJECT_ROOT

log = logging.getLogger("pipeline")

BUILD_MODEL = os.getenv("SET_BUILDER_MODEL") or "opus"
CODEX_BUILD_MODEL = os.getenv("SET_BUILDER_CODEX_MODEL") or os.getenv("SHOWRUNNER_CODEX_MODEL") or "gpt-5.6-sol"


class RepairNotApplied(RuntimeError):
    """The coding agent returned, but none of the permitted source files changed."""


# ------------------- subscription coding agent, isolated from the real worktree -------------------


def _step(name, args, workspace):
    """One short line per agent tool call (what it reads, writes, runs)."""
    path = args.get("file_path") or args.get("path") or ""
    if path:
        path = os.path.relpath(path, workspace) if os.path.isabs(path) else path
    if name == "Bash":
        return f"run: {str(args.get('command', ''))[:110]}"
    if name in ("Glob", "Grep"):
        return f"{name.lower()}: {str(args.get('pattern', ''))[:80]} {path}".strip()
    return f"{name.lower()}: {path or json.dumps(args)[:80]}"


def _run_claude_streaming(cmd, stdin_text, workspace, env, timeout):
    """Run `claude -p --output-format stream-json`, logging each tool call as it happens (so a long
    build visibly progresses). Returns (final result event or None, tail of raw output)."""
    import threading
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace", cwd=workspace, env=env)
    timer = threading.Timer(timeout, p.kill)
    timer.start()
    result, tail = None, []
    try:
        p.stdin.write(stdin_text)
        p.stdin.close()
        for line in p.stdout:
            tail = (tail + [line])[-20:]
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "result":
                result = event
            elif event.get("type") == "assistant":
                for part in (event.get("message") or {}).get("content") or []:
                    if part.get("type") == "tool_use":
                        log.info(f"[claude] {_step(part.get('name', ''), part.get('input') or {}, workspace)}")
        p.wait()
    finally:
        timer.cancel()
    return result, "".join(tail)


def claude_agent(prompt: str, allowed: list, effort: str = "high", timeout: int = 5400) -> str:
    """Run the selected coding subscription in an isolated source mirror.

    Only allowed files are copied back. This avoids the old snapshot/fence race that could undo
    edits made in the real repository while a long set-building turn was still running.
    """
    from agents.showrunner import (UsageLimit, _API_ENV, _capped_effort, _record_claude_usage,
                                   activate_fallback, active_backend, check_budget, codex_unavailable)
    check_budget("set builder")          # the costliest call in the pipeline: never start one over budget
    backend = active_backend()
    story_id = next((os.path.basename(f)[:-8] for f in allowed if f.endswith("_spec.py")), None)
    measure_cmd = f"python -m agents.set_builder --measure {story_id}" if (story_id or "").endswith("_story") else None
    measures = ("(about 3 minutes; it prints collisions, floating characters, Max's on-screen size, static camera, "
                "flat surfaces, small labels and flicker sources per beat) and fix everything it prints; run it again "
                "until it prints no measured problems or only problems you cannot fix.")

    def rules_for(kind):
        text = ("\n\nYou may create or edit ONLY these files: " + ", ".join(allowed) +
                ". Every other file is read-only. The pipeline renders and tests after you finish. ")
        if kind == "codex":
            from engine.make_film import BLENDER
            text += ("When inspecting files, issue one simple read/search command at a time; never chain PowerShell "
                     "commands with semicolons, pipes, or command substitution because the execution policy blocks "
                     f"them. Python is {sys.executable} and Blender is {BLENDER} (they are not on PATH): before you "
                     "finish, byte-compile your files and build the set once in Blender background mode, and fix "
                     "every error you see.")
            if measure_cmd:
                text += f" Then measure it: `{sys.executable}{measure_cmd[6:]}` {measures}"
        elif measure_cmd:
            text += (f"The ONLY command you can run is `{measure_cmd}` (exactly that, nothing chained): when your "
                     f"files are written, run it {measures}")
        else:
            text += "You cannot run commands."
        return text

    rules = rules_for(backend)
    with tempfile.TemporaryDirectory(prefix="video_creator_set_agent_") as tmp:
        workspace = os.path.join(tmp, "repo")
        os.makedirs(workspace)
        ignored = shutil.ignore_patterns(".git", ".env", "venv", "output", "logs", "__pycache__",
                                         ".pytest_cache", "*.pyc", "*.mp4", "*.wav")
        for name in ("engine", "agents", "config", "local_video", "unreal_video", "tests"):
            src = os.path.join(PROJECT_ROOT, name)
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(workspace, name), ignore=ignored)
        for name in ("main.py", "README.md", "requirements.txt"):
            src = os.path.join(PROJECT_ROOT, name)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(workspace, name))

        if backend == "codex":
            from agents import codex_cli
            images = [p.strip() for p in re.findall(r"[A-Za-z]:[\\/][^,\n]+?\.(?:png|jpe?g)", prompt, re.I)
                      if os.path.isfile(p.strip())]
            try:
                out, _ = codex_cli.run(prompt + rules, effort=effort, images=images, cwd=workspace,
                                       sandbox="workspace-write", model=CODEX_BUILD_MODEL, timeout=timeout,
                                       effort_cap_env="SET_BUILDER_CODEX_EFFORT_CAP")
            except RuntimeError as exc:
                if codex_unavailable(exc):
                    limit = UsageLimit(str(exc)[:500])
                    if activate_fallback(str(limit)[:180], failed_backend=backend):
                        backend = active_backend()
                        rules = rules_for(backend)
                    else:
                        raise limit from exc
                else:
                    raise
        if backend != "codex":
            exe = shutil.which("claude")
            if not exe:
                raise RuntimeError("Claude Code CLI not found: install it and run `claude` once to log in")
            env = {k: v for k, v in os.environ.items() if k not in _API_ENV}
            tools = ["Read", "Glob", "Grep", "Write", "Edit"]
            permitted = list(tools)
            if measure_cmd:                       # one exact command: everything else needs approval = denied
                tools.append("Bash")
                permitted.append(f"Bash({measure_cmd}:*)")
                env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")   # venv python
                env.setdefault("BASH_DEFAULT_TIMEOUT_MS", "900000")       # a measurement takes ~3 minutes
                env.setdefault("BASH_MAX_TIMEOUT_MS", "900000")
            cmd = [exe, "-p", "--output-format", "stream-json", "--verbose", "--model", BUILD_MODEL, "--effort",
                   _capped_effort(effort, "SET_BUILDER_CLAUDE_EFFORT_CAP"),
                   "--no-session-persistence", "--strict-mcp-config", "--setting-sources", "",
                   "--permission-mode", "acceptEdits", "--tools", *tools, "--allowedTools", *permitted]
            log.info(f"[set_builder] Claude ({BUILD_MODEL}) is working on the set (usually 15-40 minutes); "
                     "its steps follow")
            data, tail = _run_claude_streaming(cmd, prompt + rules, workspace, env, timeout)
            if data is None:
                raise RuntimeError(f"claude -p failed: {tail[-400:]}")
            result_text = str(data.get("result") or "")
            if data.get("is_error") and "limit" in result_text.lower() and "reset" in result_text.lower():
                limit = UsageLimit(result_text[:300])
                if activate_fallback(str(limit)[:180], failed_backend=backend):
                    return claude_agent(prompt, allowed, effort=effort, timeout=timeout)
                raise limit
            if data.get("is_error"):
                raise RuntimeError(f"claude -p error: {result_text[:300]}")
            _record_claude_usage(data, "set builder")
            out = result_text.strip()

        for relative in allowed:
            relative = os.path.normpath(relative)
            if os.path.isabs(relative) or relative == ".." or relative.startswith(".." + os.sep):
                raise RuntimeError(f"unsafe allowed path: {relative}")
            src = os.path.join(workspace, relative)
            if not os.path.isfile(src):
                raise RuntimeError(f"coding agent did not produce required file: {relative} "
                                   f"(agent said: {str(out).strip()[-300:]})")
            dst = os.path.join(PROJECT_ROOT, relative)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
        return str(out).strip()


# ------------------- the brief Claude works from -------------------

def _files(set_id):
    return [f"engine/sets/{set_id}_spec.py", f"engine/sets/{set_id}.py", f"engine/films/{set_id}.json"]


def _film_file(set_id):
    exact = os.path.join(PROJECT_ROOT, "engine", "films", f"{set_id}.json")
    if os.path.exists(exact):
        return exact
    for path in glob.glob(os.path.join(PROJECT_ROOT, "engine", "films", "*.json")):
        try:
            if json.load(open(path, encoding="utf-8")).get("set") == set_id:
                return path
        except (OSError, json.JSONDecodeError):
            continue
    return exact


GUIDE = """HOW EVOLUTION SETS WORK (read these files first, in this order):
- engine/evo_kit.py: the toolkit and the EvolutionSet base class (river valley with sliding banks,
  forest, village, clouds, ship, cars + traffic, pop_in / fly_in / fall / show_between, attach, beam,
  base_box, extrude_xz, stroke + draw_on for the white pen drawings, shot(), sun_key(), splash(), dust(),
  wind streaks). Reuse it; do not copy it.
- engine/sets/bridge_evolution_spec.py and engine/sets/bridge_evolution.py: the reference set. Copy
  its structure exactly: the spec is pure data (SET_ID, FORMAT = "evolution", SUBJECT, MODEL_FACTS,
  STAGE_ORDER, ACTIONS with kind/shows/seconds, ANSWERS, beat_actions, min_seconds, validate); the
  builder subclasses EvolutionSet, builds every model HIDDEN in build(), and has one method
  a_<action>(self, i, b, e) per action that animates frames b..e and places the camera with self.shot().
- engine/films/bridge_evolution.json: the reference script (second person, problem → "So you..." fix).
- engine/films/evolution_film.py (how the set is run), engine/toy.py, engine/camera.py (CameraRig).

RULES THAT KEEP RENDERS CORRECT (learned the hard way):
- Blender 5.2 Python API. Deterministic: seed every random.Random.
- Parent with attach(child, parent), never toy.parent_keep (matrix_world is stale while building).
- Hidden objects are excluded from evaluation: anything that must appear later is hidden at frame 0 and
  revealed with pop_in / fly_in / show_between (they handle the whole hierarchy). Never reveal a parent
  with show_between if its children pop in one by one later (they would all appear at once).
- Every action must keep its subject IN FRAME and READABLE in a vertical 9:16 frame: lens 22-26 gives
  about 46 degrees horizontal field of view, so a 40 m object needs the camera ~50 m away or an
  oblique view along it. Put cameras over open ground or water, ABOVE tree height (trees are ~10 m)
  and never inside or right behind an object (towers, walls). The first shot of the film uses cut=True.
- Keep the world at real scale (metres). Bank tops are z = 0, the river surface WATER_Z = -4 if you
  use the river. If the subject is not about a river, set RIVER/VILLAGE as needed and build on the banks.
- Sound: events.add(frame, kind, duration, gain) with kinds from agents/sfx.py MIX (e.g. hammer,
  splash, creak, crack, whoosh, pop, wind, rumble, stone_thud, steel_clank, bridge_groan, traffic,
  engine, ship_horn, boing, roll).
- The film JSON: "set": "<id>", "format": "evolution", "captions": "phrase", "music": "synth",
  "beat_pause": 0.35, "tail": 1.5, one beat per action in STAGE_ORDER, 140-190 words in total, an
  opening of at most 18 words, at most 5 overlays, and a closing question as the last sentence plus
  "cta" with that question. Facts must be true; numbers only from MODEL_FACTS."""


def design_prompt(subject, set_id):
    return f"""Create a new 3D "evolution" set for this subject: {subject}

Set id: {set_id}

{GUIDE}

Design first: a ladder of 4-6 stages (the simplest version first, the most advanced last), each
replaced because a real NEW LOAD OR NEED appears that the current stage cannot handle and the next one
answers (problem actions between stages, like the bridge set's
heavy_load / railway / heat / wind), 9-13 actions in total, every problem answered by the next stage, an outro.
Never fake a cause (a river that widens by itself, a bridge that collapses for no reason): a viewer must
see WHY the old design fails and how the new one fixes exactly that.
Every stage must be buildable from simple shapes and look great from drone height; every problem
must be VISIBLE (something sags, sinks, cracks, floods, burns, collapses...). Give each action a
precise "shows" description, because the scene reviewer checks the render against it.

Then write the three files:
- engine/sets/{set_id}_spec.py
- engine/sets/{set_id}.py (class name must end with "Set")
- engine/films/{set_id}.json (the reference script)

Finish with a short summary of the ladder."""


STORY_GUIDE = """HOW MAX STORY SETS WORK (read these files first, in this order):
- engine/sets/pool_story_spec.py and engine/sets/pool_story.py: the smallest complete Max story.
- engine/sets/plane_story_spec.py and engine/sets/plane_story.py: a self-contained outdoor story.
- engine/sets/boat_story_spec.py and engine/sets/boat_story.py: a detailed cutaway reference.
- engine/films/cutaway_film.py, engine/toy.py, engine/camera.py and engine/character.py.
- engine/studio.py: THE PRODUCTION KIT. Build the world and the hero objects with it (natural terrain
  with carved tunnels/caverns, endless ground, concrete, water reservoirs, flanged pipes with flowing
  water, a real pump-turbine, solar panels, a house with lights, lanterns, cutaways, close-up camera
  moves). It already follows every quality rule below; extend it in your set, never re-invent it.

The spec is pure data and must define SET_ID, SUBJECT, HERO = "Max", MODEL_FACTS, STORY_ORDER,
ACTIONS, beat_actions(), min_seconds() and validate(). It needs two hook actions, then rewind,
then a 7-10 action trial-and-error ladder that alternates visible failures with real engineering
fixes and ends in a happy finale with Max's two children. Each action needs kind, shows and seconds.
The validator must require one hook first, rewind second, and every STORY_ORDER action exactly once.

The Blender module defines one class whose name ends in Set. Its constructor is
(scene, sun, fill, bg, total), builds all models hidden as needed, creates Max and two children with
engine.character.Character, and owns a CameraRig. Its run(beats, spans, epilogue_offset) method
plays every non-hook action through a_<action>(i, start, end), stages the opening hook at the
epilogue offset, then calls rig.build(). Every action named by the spec needs a method.
The class sets QA_ALLOW: a regex of "objA x objB" pairs that touch BY DESIGN (a pipe entering a
casing, a lantern in a hand); every other intersection is reported as a collision.

ASSET PLAN FIRST: at the top of the Blender module write a comment block listing every real-world
object the story needs, its real shape and proportions, the detail that makes it recognizable at a
glance (a dam's sloped concrete profile and crest road, a turbine's snail casing and runner blades...)
and the studio/textures pieces that build it. Then build exactly that.

VISUAL AND SAFETY RULES:
- Use only reusable primitives and the repository's Blender helpers; never require downloaded assets.
- Make one coherent 9:16 diorama with a readable cutaway. Keep the active subject large and centred.
- Every failure must visibly happen; every fix must visibly answer it. Max is endearing, never harmed.
- Do not render narration, captions, lettering, watermarks or title cards in Blender. Short physical
  labels and fact arrows are allowed only when they explain the mechanism.
- Add only motivated diegetic sound events. Never add recurring transition whooshes.
- Deterministic output: seed random generators. Blender 5.2 Python. Build everything before animation.
- Hidden objects are excluded from evaluation; use toy.hide_tree/show helpers and keyframe visibility.
- Camera shots use cuts between beats and keep objects away from the vertical-frame edges.
- QUALITY BAR (the channel's standard). The pipeline MEASURES these on the staged scene (engine/qa.py
  quality()) and rejects the set until they pass, before any reviewer looks at it:
  * Max is big and readable: in every beat he fills >= 18% of the frame height for at least 35% of the
    beat (aim for ~40% with studio.close_on whenever he acts). Wide shots only briefly, to establish.
  * The camera always moves: never still for more than 2.5 s (close_on swings, studio.orbit, push-ins).
  * Characters stand ON things: feet on a surface (no hovering), never inside props or each other.
  * No flat colours: every surface bigger than ~3% of the frame has a real material (engine.studio /
    engine.textures: concrete, rock_grass, metal, paint, planks...). Realistic shapes, no grey primitives.
  * Callout labels (studio.label) are >= 1.8% of the frame height per line and fully inside the frame.
  * No flicker: no coplanar faces (offset touching surfaces >= 5 mm), no bump on squashed objects, no
    live booleans on moving parts (studio.carve once, or studio.section_clip).
  * No void: studio.world_floor + terrain blocks reaching well past every frame edge; no black band.
- The reference film JSON names this set, uses captions "word", one beat per required action, 140-192
  spoken words, a <=13-word hook and a final question. It exists for preview validation; the
  showrunner writes the production script after the set passes.
"""


def story_design_prompt(subject, set_id):
    return f"""Create a completely new 3D Max trial-and-error story set.

Set id: {set_id}
Subject and build brief: {subject}

{STORY_GUIDE}

Design the story first. The thing Max builds must be unambiguous; every failure must teach one true
physical principle, and the following fix must solve exactly that failure. Keep it achievable with
simple, robust Blender geometry. Then write exactly these three files:
- engine/sets/{set_id}_spec.py
- engine/sets/{set_id}.py
- engine/films/{set_id}.json

Finish with a short summary of the visual ladder."""


def _guide(set_id):
    """Return the format-specific repair guide for this set."""
    try:
        import importlib
        fmt = getattr(importlib.import_module(f"engine.sets.{set_id}_spec"), "FORMAT", "")
    except Exception:                                # noqa: BLE001
        fmt = ""
    if fmt == "evolution":
        return GUIDE
    try:
        if getattr(importlib.import_module(f"engine.sets.{set_id}_spec"), "HERO", None):
            return STORY_GUIDE
    except Exception:                                # noqa: BLE001
        pass
    return ("This is a hand-built cutaway set (rendered by engine/films/cutaway_film.py with toy.py, camera.py "
            "and character.py). Keep its structure and style; change as little as possible.")


def fix_prompt(set_id, problems, header):
    return f"""{header}

Set: engine/sets/{set_id}.py (spec: engine/sets/{set_id}_spec.py, script: engine/films/{set_id}.json)

{_guide(set_id)}

Problems to fix:
{problems}

Read the files involved (and the listed images, with the Read tool) and fix the cause in the set's
code. Keep every action name and the spec's STAGE_ORDER unchanged unless a problem says the spec
itself is wrong. Finish with one line per problem saying what you changed."""


def fix_code(set_id: str, error: str, allowed=None):
    """Blender crashed with a Python traceback inside the set: Claude fixes the code."""
    allowed = allowed or [f"engine/sets/{set_id}.py"]
    before = _content_hashes(allowed)
    out = claude_agent(fix_prompt(set_id, f"Blender crashed while building or rendering the set:\n{error[-6000:]}",
                                  "The render failed with a Python error. Find the cause and fix it."),
                       allowed)
    _require_changed(allowed, before, out)
    log.info(f"[set_builder] code fix applied:\n{out[-1200:]}")
    return out


def fix_scenes(set_id: str, rejected: list, allowed=None, keep=None):
    """Called by make_film (SCENE_POLICY=fix) and by the builder: the reviewer's rejected windows →
    Claude edits the set's builder.

    A whole-film review can reject a dozen windows at once. The agent reads three frames per window
    with the Read tool, and each read grows the turn it is resent with, so the worst windows are sent
    first and the list is capped (SCENE_FIX_MAX_WINDOWS). The rest come back on the next round.
    """
    worst = sorted(rejected, key=lambda r: (not r.get("fatal_problems"), r.get("average_score") or 0))
    try:                                  # a typo in .env must not break the repair path
        cap = max(1, int(os.getenv("SCENE_FIX_MAX_WINDOWS") or 6))
    except ValueError:
        cap = 6
    sent, held = worst[:cap], worst[cap:]
    lines = []
    for r in sent:
        imgs = ", ".join(os.path.abspath(p) for p in r.get("images", []))
        lines.append(f"- window {r.get('window')} ({r.get('t0', 0):.1f}-{r.get('t1', 0):.1f}s), action "
                     f"'{r.get('action')}' (method a_{str(r.get('action')).split('+')[0]}): "
                     f"fatal: {r.get('fatal_problems')}; problems: {r.get('problems')}; reviewer's fix: "
                     f"{r.get('fix')}; frames: {imgs}")
    if held:
        log.info(f"[set_builder] {len(rejected)} window(s) rejected; repairing the worst {len(sent)} this "
                 f"round (SCENE_FIX_MAX_WINDOWS={cap}), {len(held)} deferred to the next round")
        lines.append("\nThese windows were ALSO rejected but are not detailed here; prefer a root-cause fix "
                     "that covers them too over a patch for the windows above only: "
                     + ", ".join(f"{r.get('window')} ({r.get('action')})" for r in held))
    allowed = allowed or [f"engine/sets/{set_id}.py"]
    before = _content_hashes(allowed)
    if keep:
        lines.append("\nThe reviewer ACCEPTED these actions; their shots must still look the same afterwards. "
                     "Do not change their a_<action> methods, and keep any shared change (ground, camera "
                     "helpers, characters, materials) from altering them: " + ", ".join(keep))
    out = claude_agent(fix_prompt(set_id, "\n".join(lines),
                                  "The scene reviewer REJECTED these rendered windows of a 3D film."),
                       allowed)
    _require_changed(allowed, before, out)
    log.info(f"[set_builder] fix applied:\n{out[-1500:]}")
    return out


def _content_hashes(relative_paths):
    values = {}
    for relative in relative_paths:
        path = os.path.join(PROJECT_ROOT, relative)
        try:
            with open(path, "rb") as fh:
                values[relative] = hashlib.sha256(fh.read()).hexdigest()
        except OSError:
            values[relative] = None
    return values


def _require_changed(relative_paths, before, agent_output):
    if _content_hashes(relative_paths) == before:
        detail = str(agent_output).strip().replace("\n", " ")[-500:]
        raise RepairNotApplied("AI repair made no source changes; refusing to rerender identical scenes"
                               + (f": {detail}" if detail else ""))


# ------------------- checks, preview render, review -------------------

def static_checks(set_id, story=False) -> list:
    """Import the spec and validate the reference script in a fresh interpreter; compile the builder."""
    errs = []
    identity_check = ("assert getattr(sp, 'HERO', '') == 'Max', 'story spec HERO must be Max'; "
                      if story else
                      "assert getattr(sp, 'FORMAT', '') == 'evolution', 'spec FORMAT must be \"evolution\"'; ")
    story_check = (f"from agents.showrunner import hard_checks; e += hard_checks(f, {set_id!r}); "
                   if story else "")
    film_path = _film_file(set_id)
    code = (f"import json; from engine.sets import {set_id}_spec as sp; "
            f"f = json.load(open({film_path!r}, encoding='utf-8')); "
            + identity_check +
            "assert f.get('set') == sp.SET_ID, 'film set must match spec SET_ID'; "
            "e = sp.validate(f['beats']); " + story_check + "print(json.dumps(e))")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=PROJECT_ROOT)
    if r.returncode:
        errs.append(f"spec/script check failed:\n{r.stderr[-2000:]}")
    else:
        errs += [f"reference script breaks the spec: {e}" for e in json.loads(r.stdout.strip().splitlines()[-1])]
    try:
        py_compile.compile(os.path.join(PROJECT_ROOT, "engine", "sets", f"{set_id}.py"), doraise=True)
    except py_compile.PyCompileError as exc:
        errs.append(f"builder does not compile: {exc.msg}")
    if not errs:
        film = json.load(open(film_path, encoding="utf-8"))
        words = sum(len(b["text"].split()) for b in film["beats"])
        if not 120 <= words <= 200:
            errs.append(f"reference script has {words} words; aim for 140-190")
    return errs


def fake_timings(film: dict, path: str):
    """Beat lengths from word counts (2.4 words/s), so a set can be previewed without a voiceover."""
    fr, spans = 0, []
    for b in film["beats"]:
        n = max(75, int(len(b["text"].split()) / 2.4 * 30) + 10)
        spans.append({"start": fr, "end": fr + n - 1})
        fr += n
    json.dump({"fps": 30, "total_frames": fr, "beats": spans, "envelope": []}, open(path, "w"))
    return spans


def _preview_fingerprint(set_id: str, runner: str, story: bool) -> str:
    """Hash every input that can change preview pixels, so unchanged previews are reusable."""
    paths = set(glob.glob(os.path.join(PROJECT_ROOT, "engine", "*.py")))
    paths.update(glob.glob(os.path.join(PROJECT_ROOT, "engine", "films", "*.py")))
    paths.update(os.path.join(PROJECT_ROOT, p) for p in _files(set_id))
    paths.add(runner)
    h = hashlib.sha256()
    for path in sorted(paths):
        if os.path.isfile(path):
            h.update(os.path.relpath(path, PROJECT_ROOT).encode("utf-8"))
            with open(path, "rb") as fh:
                h.update(fh.read())
    settings = {
        "story": story,
        "pct": os.getenv("CUT_PCT" if story else "EVO_PCT", "50"),
        "samples": os.getenv("CUT_SAMPLES" if story else "EVO_SAMPLES", "16"),
        "blender": os.getenv("BLENDER_EXE", ""),
    }
    h.update(json.dumps(settings, sort_keys=True).encode("utf-8"))
    return h.hexdigest()


def _complete_preview(work: str, film: dict, spec) -> bool:
    """Every renderable beat has three stills; rewind beats are synthesized and intentionally absent."""
    for k, beat in enumerate(film["beats"], 1):
        actions = list(beat.get("actions") or [beat.get("action")])
        if actions and all(spec.ACTIONS.get(action, {}).get("kind") == "rewind" for action in actions):
            continue
        if len(glob.glob(os.path.join(work, f"preview_{k:02d}_*_[abc].png"))) < 3:
            return False
    return True


def preview_render(set_id, work) -> str:
    """Render 3 stills per beat, or reuse an exact source/settings match."""
    from engine.make_film import BLENDER, _run_blender
    film_json = _film_file(set_id)
    film = json.load(open(film_json, encoding="utf-8"))
    timings = os.path.join(work, "timings.json")
    fake_timings(film, timings)
    import importlib
    spec = importlib.import_module(f"engine.sets.{set_id}_spec")
    story = bool(getattr(spec, "HERO", None))
    runner = os.path.join(PROJECT_ROOT, "engine", "films",
                          "cutaway_film.py" if story else "evolution_film.py")
    os.environ.setdefault("CUT_PCT" if story else "EVO_PCT", "50")
    os.environ.setdefault("CUT_SAMPLES" if story else "EVO_SAMPLES", "16")
    fingerprint = _preview_fingerprint(set_id, runner, story)
    manifest_path = os.path.join(work, "preview_manifest.json")
    try:
        manifest = json.load(open(manifest_path, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        manifest = {}
    if manifest.get("fingerprint") == fingerprint and _complete_preview(work, film, spec):
        log.info("[set_builder] preview unchanged; reusing existing stills")
        return ""
    for p in glob.glob(os.path.join(work, "preview_*.png")):
        os.remove(p)
    try:
        _run_blender([BLENDER, "--background", "--factory-startup", "--python", runner, "--", film_json, timings,
                      work, "--preview"])
    except RuntimeError as exc:
        return str(exc)[-4000:]
    if not _complete_preview(work, film, spec):
        return "preview renderer completed without producing all three stills for every renderable beat"
    tmp = manifest_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"fingerprint": fingerprint, "beats": len(film["beats"])}, fh, indent=2)
    os.replace(tmp, manifest_path)
    return ""


_HELD = re.compile(r"\(\w*_(hand|handmesh|thumb|finger|palm)\w*\s*/", re.I)     # holding a prop = by design
# A character's head or body INSIDE something is a defect; limbs touching things (feet in sand, a kid
# seated on a pumpkin, arms brushing) is normal contact: reported to the fixer, not a rejection.
_CORE = re.compile(r"\(\w*_(skull|cheek|nose|ear|eye|iris|pupil|brow|hair|ponytail|hat|brim|mouth|mustache|torso|bib)"
                   r"\w*\s*/", re.I)


def _advisory(text):
    if text.startswith(("cropped:", "occluded:")):
        return True
    return text.startswith("collision:") and not _CORE.search(text)


def qa_check(set_id, work) -> dict:
    """The MEASURED quality gates (engine/qa.py run on the staged preview scene, no rendering):
    collisions, floating characters, Max's on-screen size, camera motion, flat untextured surfaces,
    label size/crops, coplanar (flickering) faces, squashed bump, live booleans.
    Returns {beat_number: [issue, ...]} (0 = whole set). Reused while the preview is unchanged."""
    import importlib

    from engine.make_film import BLENDER, _run_blender
    spec = importlib.import_module(f"engine.sets.{set_id}_spec")
    if not getattr(spec, "HERO", None) or os.getenv("SET_BUILD_QA", "1") != "1":
        return {}
    try:
        fingerprint = json.load(open(os.path.join(work, "preview_manifest.json"), encoding="utf-8"))["fingerprint"]
    except (OSError, ValueError, KeyError):
        fingerprint = None
    qa_path = os.path.join(work, "qa.json")
    try:
        rep = json.load(open(qa_path, encoding="utf-8"))
    except (OSError, ValueError):
        rep = {}
    if not fingerprint or rep.get("fingerprint") != fingerprint:
        log.info("[set_builder] measuring the staged scene (collisions, Max's size, camera motion, textures, "
                 "labels, flicker sources)")
        if os.path.exists(qa_path):
            os.remove(qa_path)
        os.environ.setdefault("QA_STEP", "9")
        runner = os.path.join(PROJECT_ROOT, "engine", "films", "cutaway_film.py")
        try:
            _run_blender([BLENDER, "--background", "--factory-startup", "--python", runner, "--",
                          _film_file(set_id), os.path.join(work, "timings.json"), work, "--qa"])
            rep = json.load(open(qa_path, encoding="utf-8"))
        except (RuntimeError, OSError, ValueError) as exc:
            log.warning(f"[set_builder] scene measurement failed ({str(exc)[-300:]}); vision review only")
            return {}
        rep["fingerprint"] = fingerprint
        json.dump(rep, open(qa_path, "w", encoding="utf-8"), indent=1)
    spans = json.load(open(os.path.join(work, "timings.json"), encoding="utf-8"))["beats"]
    out = {}

    def add(beat, text):
        items = out.setdefault(beat, [])
        if text not in items:
            items.append(text)

    for group in (rep.get("beats") or {}, rep.get("quality") or {}):
        for label, items in group.items():
            beat = 0 if label == "all" else int(label[:2])
            for it in items:
                text = it["issue"]
                if text.startswith("collision:") and _HELD.search(text):
                    continue
                if text.startswith("collision:"):              # one line per pair of things, not per part
                    head = text.split(" (")[0]
                    if any(x.split(" (")[0] == head for x in out.get(beat, [])):
                        continue
                add(beat, text)
    for pair, frame in (rep.get("objects") or {}).items():
        beat = next((k + 1 for k, sp in enumerate(spans) if sp["start"] + 1 <= frame <= sp["end"] + 1), 0)
        add(beat, f"object collision: {pair} intersect (move one, or add the pair to QA_ALLOW if they touch by design)")
    return out


def measure(set_id) -> dict:
    """Stage a story set (no rendering) and return its measured problems {beat: [issue]} (CLI --measure:
    the building agent runs this itself before it finishes)."""
    work = os.path.join(PROJECT_ROOT, "output", "sets", set_id, "measure")
    os.makedirs(work, exist_ok=True)
    fake_timings(json.load(open(_film_file(set_id), encoding="utf-8")), os.path.join(work, "timings.json"))
    for name in ("preview_manifest.json", "qa.json"):
        if os.path.exists(os.path.join(work, name)):
            os.remove(os.path.join(work, name))
    return qa_check(set_id, work)


def _merge_qa(reports, qa):
    """Measured problems reject a beat even when the vision review liked it (they are facts, not taste)."""
    if not qa:
        return reports
    merged = []
    for k, r in enumerate(reports):
        issues = qa.get(r["beat"], []) + (qa.get(0, []) if k == 0 else [])
        fatal = [f"measured: {x}" for x in issues if not _advisory(x)][:10]
        advisory = [f"measured: {x}" for x in issues if _advisory(x)][:6]
        if fatal or advisory:
            r = {**r, "fatal_problems": fatal + list(r.get("fatal_problems") or []),
                 "problems": advisory + list(r.get("problems") or []), "measured": len(fatal)}
            if fatal:
                r["valid"] = False
        merged.append(r)
    return merged


def review_preview(set_id, work) -> list:
    """Review previews with a persistent image cache and batched turns on every backend."""
    import importlib

    from agents import scene_validator as sv
    spec = importlib.reload(importlib.import_module(f"engine.sets.{set_id}_spec"))
    review_backend = sv._backend()
    film = json.load(open(_film_file(set_id), encoding="utf-8"))
    spans = json.load(open(os.path.join(work, "timings.json")))["beats"]
    review_dir = os.path.join(work, "review")
    os.makedirs(review_dir, exist_ok=True)
    cache_path = os.path.join(work, "review_cache.json")
    try:
        cache = json.load(open(cache_path, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cache = {}

    def save_cache():
        tmp = cache_path + ".tmp"
        json.dump(cache, open(tmp, "w", encoding="utf-8"), indent=1)
        os.replace(tmp, cache_path)

    def cache_key(w, images, previous):
        model = ((os.getenv("SCENE_REVIEW_CODEX_MODEL") or os.getenv("SHOWRUNNER_CODEX_MODEL") or "")
                 if review_backend == "codex" else
                 (os.getenv("SCENE_REVIEW_CLI_MODEL") or os.getenv("SHOWRUNNER_CLI_MODEL") or "opus"))
        meta = {"cache_version": 2, "window": w, "subject": getattr(spec, "SUBJECT", set_id),
                "backend": review_backend, "model": model, "review_width": sv.REVIEW_W,
                "jpeg_quality": sv.REVIEW_JPEG_QUALITY, "min_score": sv.min_score(),
                # a stricter (or otherwise changed) review rubric must not reuse old verdicts
                "rubric": hashlib.sha256(sv._instructions(w, getattr(spec, "SUBJECT", set_id), previous)
                                         .encode("utf-8")).hexdigest()}
        h = hashlib.sha256(json.dumps(meta, sort_keys=True).encode("utf-8"))
        for path in ([previous] if previous else []) + [p for _, p in images]:
            with open(path, "rb") as fh:
                h.update(fh.read())
        return h.hexdigest()

    reports, pending, previous = [], [], None
    for k, (beat, sp) in enumerate(zip(film["beats"], spans)):
        acts = list(beat.get("actions") or [beat.get("action")])
        if all(spec.ACTIONS.get(action, {}).get("kind") == "rewind" for action in acts):
            continue
        w = {"window": k + 1, "beat": k + 1, "action": "+".join(acts), "part": "whole beat",
             "f0": sp["start"] + 1, "f1": sp["end"] + 1, "t0": sp["start"] / 30, "t1": (sp["end"] + 1) / 30,
             "shows": " ".join(spec.ACTIONS.get(a, {}).get("shows", "") for a in acts), "text": beat["text"]}
        stills = sorted(glob.glob(os.path.join(work, f"preview_{k + 1:02d}_*_[abc].png")))
        if len(stills) < 3:
            reports.append({**w, "valid": False, "fatal_problems": ["preview stills missing for this beat"],
                            "problems": [], "fix": "", "images": stills})
            continue
        tech = sv.technical_check(stills)
        images = []
        for label, p in zip(("start", "middle", "end"), stills):
            dst = os.path.join(review_dir, f"b{k + 1:02d}_{label}.jpg")
            with open(dst, "wb") as fh:
                fh.write(sv._jpeg(p))
            images.append((f"{label} of the beat", dst))
        if not tech["valid"]:
            r = {**w, "valid": False, "fatal_problems": tech["fatal_problems"], "problems": tech["problems"],
                 "fix": ""}
        else:
            key = cache_key(w, images, previous)
            if key in cache:
                r = {**w, **cache[key], "cached": True}
            else:
                pending.append((w, images, previous, key))
                previous = images[-1][1]
                continue
        r["images"] = [p for _, p in images]
        previous = images[-1][1]
        reports.append(r)

    subject = getattr(spec, "SUBJECT", set_id)
    if sv._env_flag("SCENE_VISION", "1"):
        size = max(1, int(os.getenv("SCENE_REVIEW_BATCH_SIZE") or "4"))
        for start in range(0, len(pending), size):
            batch = pending[start:start + size]
            reviewed = sv.review_batch([(w, images) for w, images, _, _ in batch], subject)
            for w, images, _, key in batch:
                result = reviewed[w["window"]]
                cache[key] = result
                reports.append({**w, **result, "images": [p for _, p in images]})
            save_cache()
    else:
        for w, images, previous, key in pending:
            result = sv.review_images(w, images, subject, previous)
            if not result.get("skipped"):
                cache[key] = result
                save_cache()
            reports.append({**w, **result, "images": [p for _, p in images]})

    reports.sort(key=lambda r: r["window"])
    reports = _merge_qa(reports, qa_check(set_id, work))
    for r in reports:
        problems = r.get("fatal_problems") or r.get("problems") or [r.get("reason", "review unavailable")]
        log.info(f"[set_builder] beat {r['beat']:02d} [{r['action']}] "
                 f"{'ACCEPTED' if r.get('valid') else 'REJECTED'}"
                 + (" [cached]" if r.get("cached") else "")
                 + ("" if r.get("valid") else ": " + "; ".join(str(x) for x in problems[:2])))
    json.dump(reports, open(os.path.join(work, "build_review.json"), "w", encoding="utf-8"), indent=1)
    return reports


def contact_sheet(work, out_path):
    from PIL import Image, ImageDraw
    fs = sorted(glob.glob(os.path.join(work, "preview_*.png")))
    if not fs:
        return None
    w, h = 216, 384
    cols = 9
    rows = (len(fs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (w + 4), rows * (h + 18)), "white")
    for k, f in enumerate(fs):
        im = Image.open(f).convert("RGB").resize((w, h))
        x, y = (k % cols) * (w + 4), (k // cols) * (h + 18)
        sheet.paste(im, (x, y + 16))
        ImageDraw.Draw(sheet).text((x + 2, y + 2), os.path.basename(f)[8:-4], fill="black")
    sheet.save(out_path)
    return out_path


def register(set_id, collection="EVOLUTION"):
    p = os.path.join(PROJECT_ROOT, "engine", "sets", "__init__.py")
    s = open(p, encoding="utf-8").read()
    m = re.search(rf"{re.escape(collection)} = \[([^\]]*)\]", s)
    names = re.findall(r'"([^"]+)"', m.group(1)) if m else []
    if set_id not in names:
        names.append(set_id)
        new = collection + " = [" + ", ".join(f'"{n}"' for n in names) + "]"
        s = s.replace(m.group(0), new) if m else s + f"\n{new}\n"
        open(p, "w", encoding="utf-8").write(s)


# ------------------- the build loop -------------------

def build_set(subject: str, set_id: str = None, rounds: int = 4, story: bool = False) -> dict:
    suffix = "_story" if story else "_evolution"
    set_id = set_id or re.sub(r"[^a-z0-9]+", "_", subject.lower()).strip("_")[:28] + suffix
    files = _files(set_id)
    work = os.path.join(PROJECT_ROOT, "output", "sets", set_id)
    os.makedirs(work, exist_ok=True)
    exists = all(os.path.exists(os.path.join(PROJECT_ROOT, f)) for f in files)
    if not exists:
        log.info(f"[set_builder] designing and writing '{set_id}' for: {subject}")
        prompt = story_design_prompt(subject, set_id) if story else design_prompt(subject, set_id)
        log.info(claude_agent(prompt, files)[-1500:])
    else:
        log.info(f"[set_builder] '{set_id}' already exists: checking and improving it")
    status = {"set": set_id, "accepted": False, "rounds": 0, "work": work}
    # Keep fixing past `rounds` while it still improves (patience: rounds without a new best), up to a cap.
    # A round that accepts fewer beats than the best draft is rolled back to that draft before fixing.
    max_rounds = max(rounds, int(os.getenv("SET_BUILD_MAX_ROUNDS") or "8"))
    patience = int(os.getenv("SET_BUILD_PATIENCE") or "2")
    best, best_reports, stale = -1, None, 0
    best_dir = os.path.join(work, "best_draft")
    rnd = 0
    while rnd < max_rounds:
        rnd += 1
        status["rounds"] = rnd
        errs = static_checks(set_id, story=story)
        if errs:
            log.info(f"[set_builder] round {rnd}: {len(errs)} static problem(s); sending back to Claude")
            claude_agent(fix_prompt(set_id, "\n".join(f"- {e}" for e in errs),
                                    "The set's files fail the pipeline's static checks."), files)
            continue
        log.info(f"[set_builder] round {rnd}: preview render (3 stills per beat)")
        err = preview_render(set_id, work)
        if err:
            log.info(f"[set_builder] round {rnd}: Blender error; sending the traceback to Claude")
            claude_agent(fix_prompt(set_id, f"Blender crashed while building or rendering the set:\n{err}",
                                    "The preview render failed."), files)
            continue
        reports = review_preview(set_id, work)
        sheet = contact_sheet(work, os.path.join(work, f"contact_round{rnd}.png"))
        rejected = [r for r in reports if not r.get("valid")]
        log.info(f"[set_builder] round {rnd}: {len(reports) - len(rejected)}/{len(reports)} beats accepted"
                 + (f" (contact sheet: {sheet})" if sheet else ""))
        if not rejected:
            register(set_id, "AVAILABLE" if story else "EVOLUTION")
            status.update(accepted=True, contact_sheet=sheet)
            source = "cutaway" if story else "evolution"
            log.info(f"[set_builder] ACCEPTED: '{set_id}' is registered. Make a video with:\n"
                     f"  python main.py --source {source} --set {set_id}")
            return status
        accepted = len(reports) - len(rejected)
        if accepted > best:
            best, best_reports, stale = accepted, reports, 0
            _snapshot(files, best_dir)
        else:
            stale += 1
            if accepted < best:
                log.info(f"[set_builder] round {rnd}: worse than the best draft ({best} accepted); rolling back")
                _restore(files, best_dir)
                reports = best_reports
                rejected = [r for r in reports if not r.get("valid")]
        if rnd >= rounds and stale >= patience:
            break
        if rnd < max_rounds:
            fix_scenes(set_id, rejected, allowed=files,
                       keep=[r["action"] for r in reports if r.get("valid")])
    status["contact_sheet"] = os.path.join(work, f"contact_round{status['rounds']}.png")
    log.warning(f"[set_builder] NOT accepted after {status['rounds']} rounds: '{set_id}' stays a draft (not registered). "
                f"See {os.path.join(work, 'build_review.json')}; run again to continue improving it.")
    return status


def _snapshot(files, folder):
    for relative in files:
        dst = os.path.join(folder, relative)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(PROJECT_ROOT, relative), dst)


def _restore(files, folder):
    for relative in files:
        src = os.path.join(folder, relative)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(PROJECT_ROOT, relative))


def build_story_set(subject: str, set_id: str = None, rounds: int = 4) -> dict:
    """Build, visually validate and register a new Max cutaway story set."""
    return build_set(subject, set_id=set_id, rounds=rounds, story=True)


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Let Claude build (and validate) a new 3D evolution set.")
    ap.add_argument("subject", nargs="?", help='e.g. "from a raft to a container ship"')
    ap.add_argument("--id", default=None, help="set id (default: from the subject, ending in _evolution)")
    ap.add_argument("--rounds", type=int, default=int(os.getenv("SET_BUILD_ROUNDS") or "4"))
    ap.add_argument("--story", action="store_true", help="build a Max cutaway story instead of evolution")
    ap.add_argument("--fix", default=None, help="fix an existing set from a scene_review.json (with --report)")
    ap.add_argument("--report", default=None, help="scene_review.json whose rejected windows to fix")
    ap.add_argument("--measure", default=None, help="print the measured quality problems of a story set")
    a = ap.parse_args()
    if a.measure:
        found = measure(a.measure)
        lines = [f"beat {b:02d}: {x}" if b else f"whole set: {x}" for b, xs in sorted(found.items()) for x in xs]
        print("\n".join(lines) or "no measured problems")
        return
    if a.fix:
        rep = json.load(open(a.report, encoding="utf-8"))
        rejected = [w for w in rep.get("windows", rep) if not w.get("valid")]
        if not rejected:
            print("nothing rejected in that report")
            return
        fix_scenes(a.fix, rejected)
        return
    if not a.subject:
        ap.error("give a subject, or --fix SET --report FILE")
    print(json.dumps(build_set(a.subject, a.id, a.rounds, story=a.story), indent=1))


if __name__ == "__main__":
    main()
