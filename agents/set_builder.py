"""
Auto set builder: Claude creates a whole new 3D "evolution" set (spec + Blender builder + reference
script) for a subject, renders it, LOOKS at the result, and fixes it until every beat is accepted.
A set is only registered (usable by `--source evolution --set <id>`) once it passes.

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

Claude may only write the set's own files: anything else it touches is restored afterwards.
Needs the `claude` CLI (logged in) and Blender (BLENDER_EXE), like the rest of the 3D pipeline.
"""
import argparse
import glob
import json
import logging
import os
import py_compile
import re
import shutil
import subprocess
import sys

from config.paths import PROJECT_ROOT

log = logging.getLogger("pipeline")

GUARD_DIRS = ("engine", "agents", "config", "local_video", "tests")
BUILD_MODEL = os.getenv("SET_BUILDER_MODEL") or "opus"


# ------------------- Claude Code as a coding agent, fenced to the set's files -------------------

def _snapshot():
    snap = {}
    for d in GUARD_DIRS:
        for p in glob.glob(os.path.join(PROJECT_ROOT, d, "**", "*"), recursive=True):
            if os.path.isfile(p) and p.endswith((".py", ".json", ".md")) and "__pycache__" not in p:
                with open(p, "rb") as fh:
                    snap[os.path.abspath(p)] = fh.read()
    for p in ("main.py", "README.md", "requirements.txt"):
        full = os.path.join(PROJECT_ROOT, p)
        if os.path.exists(full):
            with open(full, "rb") as fh:
                snap[os.path.abspath(full)] = fh.read()
    return snap


def _fence(before, allowed):
    """Undo any change outside `allowed` (restore modified files, delete new ones)."""
    allowed = {os.path.abspath(os.path.join(PROJECT_ROOT, a)) for a in allowed}
    after = _snapshot()
    for p, data in before.items():
        if p not in allowed and after.get(p) != data:
            with open(p, "wb") as fh:
                fh.write(data)
            log.warning(f"[set_builder] restored {os.path.relpath(p, PROJECT_ROOT)} (outside the set's files)")
    for p in after:
        if p not in before and p not in allowed:
            os.remove(p)
            log.warning(f"[set_builder] removed {os.path.relpath(p, PROJECT_ROOT)} (outside the set's files)")


def claude_agent(prompt: str, allowed: list, effort: str = "high", timeout: int = 5400) -> str:
    """One headless Claude Code session in the project folder with Read/Glob/Grep/Write/Edit,
    on the Claude subscription (API credentials stripped). Only `allowed` files may change."""
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("Claude Code CLI not found: install it and run `claude` once to log in")
    from agents.showrunner import _API_ENV
    env = {k: v for k, v in os.environ.items() if k not in _API_ENV}
    tools = ["Read", "Glob", "Grep", "Write", "Edit"]
    rules = ("\n\nYou may create or edit ONLY these files: " + ", ".join(allowed) +
             ". Every other file is read-only (changes elsewhere are reverted automatically). "
             "You cannot run commands: the pipeline renders and tests your files after you finish.")
    before = _snapshot()
    cmd = [exe, "-p", "--output-format", "json", "--model", BUILD_MODEL, "--effort", effort,
           "--no-session-persistence", "--strict-mcp-config", "--setting-sources", "",
           "--permission-mode", "acceptEdits", "--tools", *tools, "--allowedTools", *tools]
    try:
        r = subprocess.run(cmd, input=prompt + rules, capture_output=True, text=True, encoding="utf-8",
                           cwd=PROJECT_ROOT, env=env, timeout=timeout)
    finally:
        _fence(before, allowed)
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"claude -p failed (exit {r.returncode}): {(r.stderr or r.stdout)[-400:]}")
    if data.get("is_error"):
        raise RuntimeError(f"claude -p error: {str(data.get('result'))[:300]}")
    return str(data.get("result") or "").strip()


# ------------------- the brief Claude works from -------------------

def _files(set_id):
    return [f"engine/sets/{set_id}_spec.py", f"engine/sets/{set_id}.py", f"engine/films/{set_id}.json"]


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
replaced because a real problem appears (problem actions between stages, like the bridge set's
widen_* / heat / wind), 9-13 actions in total, every problem answered by the next stage, an outro.
Every stage must be buildable from simple shapes and look great from drone height; every problem
must be VISIBLE (something sags, sinks, cracks, floods, burns, collapses...). Give each action a
precise "shows" description, because the scene reviewer checks the render against it.

Then write the three files:
- engine/sets/{set_id}_spec.py
- engine/sets/{set_id}.py (class name must end with "Set")
- engine/films/{set_id}.json (the reference script)

Finish with a short summary of the ladder."""


def _guide(set_id):
    """The evolution guide for evolution sets; a short note for the hand-built Max cutaway sets."""
    try:
        import importlib
        fmt = getattr(importlib.import_module(f"engine.sets.{set_id}_spec"), "FORMAT", "")
    except Exception:                                # noqa: BLE001
        fmt = ""
    if fmt == "evolution":
        return GUIDE
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
    out = claude_agent(fix_prompt(set_id, f"Blender crashed while building or rendering the set:\n{error[-6000:]}",
                                  "The render failed with a Python error. Find the cause and fix it."),
                       allowed or [f"engine/sets/{set_id}.py"])
    log.info(f"[set_builder] code fix applied:\n{out[-1200:]}")
    return out


def fix_scenes(set_id: str, rejected: list, allowed=None):
    """Called by make_film (SCENE_POLICY=fix) and by the builder: the reviewer's rejected windows →
    Claude edits the set's builder."""
    lines = []
    for r in rejected:
        imgs = ", ".join(os.path.abspath(p) for p in r.get("images", []))
        lines.append(f"- window {r.get('window')} ({r.get('t0', 0):.1f}-{r.get('t1', 0):.1f}s), action "
                     f"'{r.get('action')}' (method a_{str(r.get('action')).split('+')[0]}): "
                     f"fatal: {r.get('fatal_problems')}; problems: {r.get('problems')}; reviewer's fix: "
                     f"{r.get('fix')}; frames: {imgs}")
    out = claude_agent(fix_prompt(set_id, "\n".join(lines),
                                  "The scene reviewer REJECTED these rendered windows of an evolution film."),
                       allowed or [f"engine/sets/{set_id}.py"])
    log.info(f"[set_builder] fix applied:\n{out[-1500:]}")
    return out


# ------------------- checks, preview render, review -------------------

def static_checks(set_id) -> list:
    """Import the spec and validate the reference script in a fresh interpreter; compile the builder."""
    errs = []
    code = (f"import json; from engine.sets import {set_id}_spec as sp; "
            f"f = json.load(open('engine/films/{set_id}.json', encoding='utf-8')); "
            "assert getattr(sp, 'FORMAT', '') == 'evolution', 'spec FORMAT must be \"evolution\"'; "
            "e = sp.validate(f['beats']); print(json.dumps(e))")
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
        film = json.load(open(os.path.join(PROJECT_ROOT, "engine", "films", f"{set_id}.json"), encoding="utf-8"))
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


def preview_render(set_id, work) -> str:
    """Render 3 stills per beat; returns '' or the Blender error text."""
    from engine.make_film import BLENDER, _run_blender
    film_json = os.path.join(PROJECT_ROOT, "engine", "films", f"{set_id}.json")
    film = json.load(open(film_json, encoding="utf-8"))
    for p in glob.glob(os.path.join(work, "preview_*.png")):
        os.remove(p)
    timings = os.path.join(work, "timings.json")
    fake_timings(film, timings)
    runner = os.path.join(PROJECT_ROOT, "engine", "films", "evolution_film.py")
    os.environ.setdefault("EVO_PCT", "50")
    os.environ.setdefault("EVO_SAMPLES", "16")
    try:
        _run_blender([BLENDER, "--background", "--factory-startup", "--python", runner, "--", film_json, timings,
                      work, "--preview"])
    except RuntimeError as exc:
        return str(exc)[-4000:]
    return ""


def review_preview(set_id, work) -> list:
    """Every beat's three preview stills through the scene validator. Returns the per-beat reports."""
    import importlib

    from agents import scene_validator as sv
    spec = importlib.reload(importlib.import_module(f"engine.sets.{set_id}_spec"))
    film = json.load(open(os.path.join(PROJECT_ROOT, "engine", "films", f"{set_id}.json"), encoding="utf-8"))
    spans = json.load(open(os.path.join(work, "timings.json")))["beats"]
    review_dir = os.path.join(work, "review")
    os.makedirs(review_dir, exist_ok=True)
    reports, previous = [], None
    for k, (beat, sp) in enumerate(zip(film["beats"], spans)):
        acts = list(beat.get("actions") or [beat.get("action")])
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
            r = {**w, **sv.review_images(w, images, getattr(spec, "SUBJECT", set_id), previous)}
        r["images"] = [p for _, p in images]
        previous = images[-1][1]
        reports.append(r)
        log.info(f"[set_builder] beat {k + 1:02d} [{w['action']}] "
                 f"{'ACCEPTED' if r.get('valid') else 'REJECTED'}"
                 + ("" if r.get("valid") else ": " + "; ".join((r.get("fatal_problems") or r.get("problems"))[:2])))
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


def register(set_id):
    p = os.path.join(PROJECT_ROOT, "engine", "sets", "__init__.py")
    s = open(p, encoding="utf-8").read()
    m = re.search(r"EVOLUTION = \[([^\]]*)\]", s)
    names = re.findall(r'"([^"]+)"', m.group(1)) if m else []
    if set_id not in names:
        names.append(set_id)
        new = "EVOLUTION = [" + ", ".join(f'"{n}"' for n in names) + "]"
        s = s.replace(m.group(0), new) if m else s + f"\n{new}\n"
        open(p, "w", encoding="utf-8").write(s)


# ------------------- the build loop -------------------

def build_set(subject: str, set_id: str = None, rounds: int = 4) -> dict:
    set_id = set_id or re.sub(r"[^a-z0-9]+", "_", subject.lower()).strip("_")[:28] + "_evolution"
    files = _files(set_id)
    work = os.path.join(PROJECT_ROOT, "output", "sets", set_id)
    os.makedirs(work, exist_ok=True)
    exists = all(os.path.exists(os.path.join(PROJECT_ROOT, f)) for f in files)
    if not exists:
        log.info(f"[set_builder] designing and writing '{set_id}' for: {subject}")
        log.info(claude_agent(design_prompt(subject, set_id), files)[-1500:])
    else:
        log.info(f"[set_builder] '{set_id}' already exists: checking and improving it")
    status = {"set": set_id, "accepted": False, "rounds": 0, "work": work}
    for rnd in range(1, rounds + 1):
        status["rounds"] = rnd
        errs = static_checks(set_id)
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
            register(set_id)
            status.update(accepted=True, contact_sheet=sheet)
            log.info(f"[set_builder] ACCEPTED: '{set_id}' is registered. Make a video with:\n"
                     f"  python main.py --source evolution --set {set_id}")
            return status
        if rnd < rounds:
            fix_scenes(set_id, rejected, allowed=files)
    status["contact_sheet"] = os.path.join(work, f"contact_round{status['rounds']}.png")
    log.warning(f"[set_builder] NOT accepted after {rounds} rounds: '{set_id}' stays a draft (not registered). "
                f"See {os.path.join(work, 'build_review.json')}; run again to continue improving it.")
    return status


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Let Claude build (and validate) a new 3D evolution set.")
    ap.add_argument("subject", nargs="?", help='e.g. "from a raft to a container ship"')
    ap.add_argument("--id", default=None, help="set id (default: from the subject, ending in _evolution)")
    ap.add_argument("--rounds", type=int, default=int(os.getenv("SET_BUILD_ROUNDS") or "4"))
    ap.add_argument("--fix", default=None, help="fix an existing set from a scene_review.json (with --report)")
    ap.add_argument("--report", default=None, help="scene_review.json whose rejected windows to fix")
    a = ap.parse_args()
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
    print(json.dumps(build_set(a.subject, a.id, a.rounds), indent=1))


if __name__ == "__main__":
    main()
