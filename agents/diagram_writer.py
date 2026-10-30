"""
Explanation diagrams written by the AI (Claude or Codex, through agents/ai_router): one small React/SVG
component per why-step, built ONLY from the house design library (compositor/src/diagram/kit.tsx), then
CHECKED the way a viewer would: typecheck -> 3 rendered stills -> a vision review against what the step must
show -> at most DIAGRAM_ROUNDS-1 fixes -> else the ready-made chain diagram (never blocks a film).

    status = write({"id": "bike_trail", "title": "WHY IT STEERS", "dur": 150,
                    "must_see": "...", "narration": "...", "cues": [[12, "leans"], [60, "wheel"]],
                    "steps": ["BIKE LEANS", "WHEEL TURNS IN", "BIKE STANDS UP"]})

Why 2D: the AI writes vector animation reliably (a wrong one costs seconds to re-render), while AI-written
Blender worlds cost ~1M tokens per repair turn and still looked poor. Any subject can be drawn.
"""
import json
import logging
import os
import re
import subprocess

from config.paths import PROJECT_ROOT

log = logging.getLogger("pipeline")
COMPOSITOR = os.path.join(PROJECT_ROOT, "compositor")
GENERATED = os.path.join(COMPOSITOR, "src", "diagrams", "generated")
INDEX = os.path.join(COMPOSITOR, "src", "diagrams", "index.ts")
NPX = "npx.cmd" if os.name == "nt" else "npx"
ROUNDS = int(os.getenv("DIAGRAM_ROUNDS", "3"))

KIT_API = """\
import React from 'react';
import {Arrow, Box, C, Canvas, Circle, Counter, Curve, DiagramProps, Flow, Group, Label, Line, Mark, Path, Pulse,
        STROKE, ease, lerp, loop, pop, useT} from '../../diagram/kit';

export default function Diagram({t, dur, w, h}: DiagramProps) { return <Canvas t={t} w={w} h={h}>...</Canvas>; }

t = local frame (30 fps, 0 at the start of the step), dur = frames in the step, w = h = 1080 (pixels, y down).
Every shape draws itself on (outline like a pen, then the fill) from its `at` frame over `len` frames.
  C.ink C.paper C.accent C.good C.bad C.water C.air C.heat C.cold C.metal C.wood C.skin C.plant C.ground
  C.purple C.pink                      palette (use these only)
  <Box x y w h r? fill? stroke? width? at? len? opacity?/>         rounded rectangle, x/y top-left
  <Circle cx cy r fill? stroke? at? .../>   <Line x1 y1 x2 y2 dashed? .../>
  <Curve points={[[x,y],...]} closed? fill? .../>   <Path d="svg path" fill? .../>   (any shape)
  <Arrow x1 y1 x2 y2 color? at? len? bend? width?/>   thick arrow that shoots out (bend = curve in px)
  <Label x y text tone?="white"|"accent"|"good"|"bad" at? size?/>   1-3 word pill centred at x,y
  <Counter x y from to unit? at? len? size? color?/>   a number counting up/down
  <Flow points={[[x,y],...]} color? at? speed? count? r?/>   dots streaming along a line (water, air, heat...)
  <Pulse cx cy r? at? color?/>   "look here" ring      <Mark x y ok at? size?/>   tick or cross stamp
  <Group x? y? rotate? scale? opacity?>...</Group>    move/rotate/scale a part (rotate in degrees, around the
                                                      group's origin: draw the part around 0,0 inside it)
  ease(t, at, len) 0->1   pop(t, at, len) 0->1 with overshoot   lerp(t, at, len, a, b)   loop(t, at, period) 0..1
"""

def _example():
    try:
        with open(os.path.join(COMPOSITOR, "src", "diagram", "example.tsx"), encoding="utf-8") as fh:
            return fh.read().replace("from './kit'", "from '../../diagram/kit'")
    except OSError:
        return "(missing)"


RULES = """You write ONE animated explanation diagram for a funny science short (vertical phone video). It is shown
full screen over a dimmed blueprint background while the narrator says the step. Style: a clean, bold, simple
cartoon diagram (think the best YouTube explainers): thick outlines, flat fills, few big parts, generous space.

HARD RULES
- TypeScript React. Imports ONLY 'react' and '../../diagram/kit' (exactly the API below). No other imports, no
  Math.random, no Date, no window/document, no hooks except useT. Deterministic: everything is a function of t.
- `export default function Diagram({t, dur, w, h}: DiagramProps)` returning one <Canvas t={t} w={w} h={h}>.
- Draw the real thing SIMPLIFIED to the parts that matter (side view or cutaway), big: the main object spans
  60-80 % of the canvas. Everything stays inside x 60..1020, y 60..1020.
- The step is a short ANIMATION that shows cause -> effect: things MOVE (Group rotate/x/y with lerp, Flow,
  Arrow shooting out) exactly when the narrator says them (the cue frames given). Not a static poster.
- At most 4 labels, 1-3 words each, never overlapping each other or the key part; size >= 40.
- Use the palette only; the thing to look at is C.accent; wrong = C.bad, right = C.good.
- Everything drawn by 70 % of dur, then it holds (the viewer needs time to read it).
- NO title or caption text: the film shows the step title and the narration above and below the diagram.
- The object must be RECOGNISABLE at a glance: draw its real silhouette with its real parts (a bike = two
  round wheels, a frame triangle, fork, handlebars, saddle), not abstract sticks. Arrows touch the part they
  act on; labels sit next to their part.
- Copy the QUALITY of the style reference below (it is another subject: never reuse its content).

THE KIT API
""" + KIT_API + "\n\nSTYLE REFERENCE (src/diagram/example.tsx, 'why ice floats'):\n" + _example()


SCHEMA = {"type": "object", "additionalProperties": False, "required": ["code"],
          "properties": {"code": {"type": "string"}}}
PASS = 4         # review score (1-5) a diagram needs; below KEEP the ready-made chain is shown instead
KEEP = 3
REVIEW_SCHEMA = {"type": "object", "additionalProperties": False,
                 "required": ["seen", "score", "shows", "readable", "clean", "problems", "fix"],
                 "properties": {"seen": {"type": "string"}, "score": {"type": "integer"},
                                "shows": {"type": "boolean"},
                                "readable": {"type": "boolean"}, "clean": {"type": "boolean"},
                                "problems": {"type": "array", "items": {"type": "string"}},
                                "fix": {"type": "string"}}}

BANNED = re.compile(r"\b(Math\.random|Date|window|document|fetch|require|eval|setTimeout|useEffect|useState)\b")


def _safe_id(s):
    return re.sub(r"[^a-z0-9_]", "_", s.lower())[:48] or "diagram"


def _strip_fences(code):
    m = re.search(r"```(?:tsx|typescript|ts)?\s*\n(.*?)```", code, re.S)
    return (m.group(1) if m else code).strip() + "\n"


def static_problems(code):
    """What a typecheck would not catch but the house rules forbid."""
    problems = []
    for imp in re.findall(r"from\s+['\"]([^'\"]+)['\"]", code):
        if imp not in ("react", "../../diagram/kit"):
            problems.append(f"import from '{imp}' is not allowed (only 'react' and '../../diagram/kit')")
    m = BANNED.search(code)
    if m:
        problems.append(f"'{m.group(0)}' is not allowed: everything must be a pure function of t")
    if "export default function" not in code:
        problems.append("missing `export default function Diagram({t, dur, w, h}: DiagramProps)`")
    return problems


def write_index(extra=()):
    """compositor/src/diagrams/index.ts: every generated diagram on disk (+ the one being tried)."""
    os.makedirs(GENERATED, exist_ok=True)
    ids = sorted({f[:-4] for f in os.listdir(GENERATED) if f.endswith(".tsx")} | set(extra))
    lines = ["// GENERATED by agents/diagram_writer.py: every accepted diagram, by id. Do not edit by hand.",
             "import React from 'react';", "import {DiagramProps} from '../diagram/kit';",
             "import d__style_example from '../diagram/example';"]
    lines += [f"import d_{i} from './generated/{i}';" for i in ids]
    lines += ["", "export const DIAGRAMS: Record<string, React.FC<DiagramProps>> = {",
              "  _style_example: d__style_example,"]
    lines += [f"  {i}: d_{i}," for i in ids] + ["};", ""]
    with open(INDEX, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def typecheck(path):
    """tsc errors that concern this diagram ('' when it compiles)."""
    r = subprocess.run([NPX, "tsc", "--noEmit", "-p", "."], cwd=COMPOSITOR, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300)
    name = os.path.basename(path)
    return "\n".join(line for line in (r.stdout + r.stderr).splitlines() if name in line)[:3000]


def stills(spec, out_dir):
    """3 frames of the diagram as the viewer sees it: early, middle, held end."""
    os.makedirs(out_dir, exist_ok=True)
    dur = int(spec["dur"])
    props = os.path.join(out_dir, "props.json")
    with open(props, "w", encoding="utf-8") as fh:
        json.dump({"cue": {"id": spec["id"], "from": 0, "to": dur, "steps": spec.get("steps", [])}}, fh)
    paths = []
    for share in (0.35, 0.65, 0.95):
        f = max(0, min(dur - 1, int(dur * share)))
        png = os.path.join(out_dir, f"{spec['id']}_{f:04d}.png")
        subprocess.run([NPX, "remotion", "still", "src/index.ts", "DiagramPreview", png, f"--props={props}",
                        f"--frame={f}", "--log=error"], cwd=COMPOSITOR, check=True, timeout=600,
                       capture_output=True)
        paths.append(png)
    return paths


def review(spec, pngs, call=None):
    from agents import ai_router
    call = call or ai_router.ask
    system = ("You review one animated explanation diagram from a phone science short, as a curious 12-year-old "
              "AND a strict art director. The images are 3 moments of the animation, in order.")
    prompt = (f"WHAT IT MUST SHOW: {spec['must_see']}\nNARRATION AT THAT MOMENT: {spec.get('narration', '')}\n\n"
              "seen: what you actually see, one sentence. score: 1 (confusing or broken) to 5 (a 12-year-old gets "
              "the idea at once and it looks great); 4 = clear with small flaws. shows: true if a 12-year-old gets "
              "that idea "
              "from the pictures. readable: every label legible, none overlapping or cut off. clean: simple, bold, "
              "uncluttered, nothing broken or floating wrongly. problems: each concrete problem. fix: the single "
              "most useful change to the drawing.")
    return call(system, prompt, REVIEW_SCHEMA, images=[(f"moment {k + 1}", p) for k, p in enumerate(pngs)])


def _brief(spec):
    cues = "; ".join(f"frame {int(f)}: '{w}'" for f, w in spec.get("cues", []))
    return (f"STEP TITLE: {spec.get('title', '')}\nWHAT IT MUST SHOW: {spec['must_see']}\n"
            f"NARRATION: {spec.get('narration', '')}\nDURATION: {spec['dur']} frames\n"
            f"WORD CUES (make each part happen on its word): {cues or 'none'}")


def write(spec, call=None, judge=None, out_dir=None, look=None):
    """Write, check and review one diagram. Returns {"id", "status": accepted|fallback, "rounds", "score",
    "problems"}. The best-scoring version is kept when none passes; below KEEP the candidate is deleted and the
    film shows the ready-made chain of spec["steps"]. Fix rounds SEE their own stills (`look`: an image call)."""
    from agents import ai_router
    call = call or (lambda s, p, sc: ai_router.ask(s, p, sc, effort="high"))
    look = look or (lambda s, p, sc, images: ai_router.ask(s, p, sc, images=images))
    spec = dict(spec, id=_safe_id(spec["id"]))
    path = os.path.join(GENERATED, f"{spec['id']}.tsx")
    out_dir = out_dir or os.path.join(PROJECT_ROOT, "output", "diagrams", spec["id"])
    code, problems, last, pngs = None, [], [], []
    best = (0, None, [], [])             # (score, code, problems, stills)
    for k in range(ROUNDS):
        ask = _brief(spec)
        if code is not None:
            ask += ("\n\nYOUR PREVIOUS VERSION:\n" + code + "\n\nFIX THESE PROBLEMS (keep what works):\n- "
                    + "\n- ".join(problems))
        try:
            if pngs and code is not None:       # it SEES what it drew (fixing from words alone went in circles)
                ask += "\n\nThe images are 3 moments of your previous version, as rendered."
                code = _strip_fences(look(RULES, ask, SCHEMA,
                                          [(f"moment {i + 1}", p) for i, p in enumerate(pngs)])["code"])
            else:
                code = _strip_fences(call(RULES, ask, SCHEMA)["code"])
        except Exception as e:  # noqa: BLE001
            log.warning("diagram %s: writer unavailable (%s)", spec["id"], str(e)[:120])
            break
        problems = static_problems(code)
        if problems:
            continue
        os.makedirs(GENERATED, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(code)
        write_index()
        errors = typecheck(path)
        if errors:
            problems = [f"TypeScript errors:\n{errors}"]
            continue
        try:
            pngs = stills(spec, out_dir)
        except subprocess.CalledProcessError as e:
            problems = [f"render failed: {(e.stderr or b'')[-1500:].decode('utf-8', 'replace')}"]
            continue
        try:
            verdict = (judge or review)(spec, pngs)
        except Exception as e:  # noqa: BLE001  (no reviewer: keep a diagram that compiles and renders)
            log.warning("diagram %s: review unavailable (%s); kept unreviewed", spec["id"], str(e)[:120])
            return {"id": spec["id"], "status": "accepted", "rounds": k + 1, "problems": ["unreviewed"]}
        score = int(verdict.get("score") or 0)
        log.info("diagram %s round %d: score %d: %s", spec["id"], k + 1, score, verdict.get("seen", ""))
        problems = list(verdict.get("problems") or []) + ([f"most useful fix: {verdict['fix']}"]
                                                          if verdict.get("fix") else [])
        last = problems
        if score >= PASS and verdict.get("shows") and verdict.get("readable"):
            return {"id": spec["id"], "status": "accepted", "rounds": k + 1, "score": score, "problems": problems,
                    "stills": pngs}
        if score > best[0]:
            best = (score, code, problems, pngs)
    if best[0] >= KEEP:               # the best version a viewer can follow beats a list of words
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(best[1])
        write_index()
        log.warning("QUALITY WARNING: diagram %s kept at score %d (%s)", spec["id"], best[0],
                    "; ".join(best[2])[:300])
        return {"id": spec["id"], "status": "accepted", "rounds": ROUNDS, "score": best[0], "problems": best[2],
                "stills": best[3]}
    if os.path.isfile(path):          # never ship a diagram nobody can follow: the template takes over
        os.remove(path)
        write_index()
    log.warning("QUALITY WARNING: diagram %s fell back to the step chain (%s)", spec["id"],
                "; ".join(last or problems)[:300])
    return {"id": spec["id"], "status": "fallback", "rounds": ROUNDS, "problems": last or problems}
