"""Deadline-driven production: a whole local-ai video inside a fixed wall-clock budget.

Measured on this laptop (RTX 4070 Laptop, 8 GB) on 2026-10-30: a 3 s MiniMax H3 clip costs ~190 s of
GPU (~25 s text encoding plus ~165 s sampling and decoding, mostly weight streaming, so a smaller frame
barely helps), a FLUX schnell keyframe ~15 s, a Claude review ~40 s. A 64 s video cut into 22 shots
needed 70+ minutes of clips alone with every shot a MiniMax clip, and the stray-dog run took 3.5 h.

Fast mode (LOCAL_VIDEO_FAST=1, the default) instead:
- gives every shot its own reviewed FLUX keyframe (hard cuts, so no shot waits for another's clip and
  keyframes are drawn while earlier ones are still being reviewed);
- renders every shot as a MiniMax clip, first takes for all shots before any retake;
- retries a rejected clip only while the deadline still has room for it, and otherwise falls back to
  the best clean take or that shot's approved keyframe as a parallax still, never to a take the reviewer
  called broken.

Planned stills (LOCAL_VIDEO_PLANNED_STILLS=1, off by default) fit a 55 min budget by turning every shot
but the few that most need motion into a depth-parallax move over its keyframe. The 2026-10-31 runs did
that (17-20 of 22 shots as stills) and the user judged the result "pictures only and zoom in zoom out":
real motion on every shot matters more than the hour.
"""

from __future__ import annotations

import logging
import math
import os
import re
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from .config import env_float, env_int
from . import sound
from .models import MANIFEST_LOCK, ProjectManifest, Shot

log = logging.getLogger("pipeline")

STILL_MOVES = ("push_in", "pull_out", "pan_left", "pan_right", "rise")
# Assembly, captions, mix and the final creative review after the last clip (~3 min measured).
RESERVE_SECONDS = 240.0


def enabled() -> bool:
    return env_int("LOCAL_VIDEO_FAST", 1, 0, 1) == 1


def planned_stills() -> bool:
    """Plan parallax stills to fit the budget (LOCAL_VIDEO_PLANNED_STILLS=1); off: every shot is a clip."""
    return env_int("LOCAL_VIDEO_PLANNED_STILLS", 0, 0, 1) == 1


def budget_seconds() -> float:
    """Wall-clock budget for the whole pipeline, topic to final video (LOCAL_VIDEO_BUDGET_MINUTES).

    55 min with planned stills; 100 min when every shot is a clip (22 first takes of ~205 s are ~75 min),
    which leaves room for a few retakes at the end.
    """
    return env_float("LOCAL_VIDEO_BUDGET_MINUTES", 55.0 if planned_stills() else 100.0, 5.0) * 60.0


def pipeline_started(default: float | None = None) -> float:
    """When this pipeline run began: main.py exports PIPELINE_STARTED_AT; a bare resume starts now."""
    try:
        value = float(os.getenv("PIPELINE_STARTED_AT") or "")
    except ValueError:
        value = 0.0
    if value > 0 and time.time() - value < 6 * 3600:
        return value
    return default if default is not None else time.time()


def clip_cost(manifest: ProjectManifest) -> float:
    """Expected GPU seconds for one more MiniMax clip, from this project's own takes when it has any."""
    default = env_float("LOCAL_VIDEO_CLIP_SECONDS", 205.0, 30.0)
    measured = [float(a["generation_seconds"]) for shot in manifest.shots for a in shot.attempts
                if a.get("backend") == "minimax" and a.get("generation_seconds")]
    if not measured:
        return default
    recent = measured[-4:]
    # Weighted toward the default until a few takes are in: one fast first clip must not overbook.
    weight = len(recent) / (len(recent) + 2)
    return max(60.0, weight * sum(recent) / len(recent) + (1 - weight) * default)


def keyframe_stage_seconds(shots: int) -> float:
    """FLUX draws one take per ~15 s while reviews run beside it; about a third of shots need a retake."""
    return 60.0 + shots * 22.0


def motion_budget(shots: int, seconds_left: float, cost: float) -> int:
    """How many shots can be MiniMax clips: one clip's worth is held back for a retake."""
    if seconds_left <= 0 or cost <= 0:
        return 0
    return max(0, min(shots, int(seconds_left // cost) - 1))


# ---------------------------------------------------------------------------------------------------
# Shot design: which beats move, and a first frame FLUX schnell can actually draw for each.

FRAME_RULES = """How FLUX.1-schnell fails, measured on hundreds of rejected first frames on this machine:
- It draws a PHOTOGRAPH, not an event. "Molasses races toward the camera, swallowing cobblestones" came
  back as a giant glossy disc in 9 of 9 takes; "the wave splinters the awning" drew an intact awning.
  Describe the frozen instant as a photographer would see it: what stands where, its size, material,
  colour and texture, the state things are in (flooded, buried, torn, standing whole).
- An unusual substance or disaster needs a familiar photographic analogy: a molasses flood is "a street
  flooded knee-deep with thick glossy dark-brown syrup, like a mudslide of brown sludge", a lava front is
  "a wall of black crumbling rock with glowing orange cracks". Name the look, not the physics.
- It does not read left/right or "toward frame right": write the layout as near/far, foreground/
  background, centre, "fills the lower half". A moving subject comes toward or goes away from the camera.
- More than two people side by side do not fit a tall frame; stage groups in depth (one near the camera,
  the rest behind). A marching column or crowd goes away from the camera up its road. Exact counts above
  three are not drawn: say "a few" or "a crowd" unless the count is the point.
- It has no negative channel: never write "no X", "without X", "empty of X" (that draws X). Write what
  is there instead.
- Text appears wherever a sign, label, poster, newspaper, plaque, screen, map or document is named: show
  physical things only, with plain unmarked surfaces.
- A flag only works planted on a pole in the ground or on a building, its pattern stated exactly.
- An expression is drawn from its visible mechanics ("eyes wide, mouth open in a gasp"), never an
  abstract word ("terrified", "vacant").
- One clear focal subject large in the frame, readable at phone size, with a simple uncluttered
  background. Vary the shot size from shot to shot (wide, medium, close-up, detail) so no two neighbouring
  shots look alike. When several beats show the same object or place, show it differently each time (another
  scale, angle, light or stage of the action): the same hand-on-a-wax-seal close-up three times reads as a
  loop.
- It does not know period names for clothes and gear ("tricorn", "grenadier mitre cap", "doublet",
  "kepi"): it draws a shako, a bicorne or a modern cap instead. Describe each garment by its plain shape,
  material and colour ("a black felt hat with its wide brim turned up into three points", "a tall pointed
  red cloth cap with a polished brass plate on its front").
- One person doing one simple, visible thing draws well; two people handling the same object (measuring a
  recruit against a post, handing over a purse) or a person interacting with a prop in a specific way comes
  out wrong. Stage such beats as one person with the object, or the object alone in its place.
- A named character's face cannot be held from shot to shot by words alone: show them in as few frames as
  the story allows, at medium distance or from behind, and put their face close up only where it matters.
- Prefer frames with people in their place (period-correct anonymous figures doing what the narration
  describes, faces not featured) and the story's real places over isolated inserts: at most two close-ups of
  hands, papers or small objects in the whole video (the Zanzibar cut used four and read as stock montage).
- An explosion, fire burst or impact looks fake frozen mid-burst: show the moment just after (a thick column
  of grey-brown smoke rising from the hit building, fresh rubble below).
- The story's recurring hero (an animal, a person, a machine) is seen at many scales and in its world: at
  most two face-on close-ups of it in the whole video (the pig run used seven nearly identical snout shots).
- Every frame is full of its place: a flag, a tool or an object is shown in its setting (on the palace roof,
  on the desk), never alone against a blank sky or plain background.
- A fake, a model or a decoy (an inflatable tank, a dummy plane, a painted backdrop) is drawn as the real
  thing unless the frame shows what gives it away: two soldiers carrying a whole tank on their shoulders, a
  slack half-inflated rubber hull with wrinkles, glued seams and a fill valve, plywood props seen from behind.
  The Ghost Army run lost a shot to six real-looking planes and jeeps.
- Daylight or interior light only; never night, dusk or glow-in-the-dark subjects.
- Crisp, clear light with the sun behind or beside the camera, and the subject in sharp focus. Never dust in
  the air, haze, mist, fog, smoke, steam, spray, sun glare, a backlit subject, a silhouette or a lens flare:
  the video model turns any of them into a veil over the whole clip (the windmill run's three softest shots,
  a dust storm and a dust-blown well, kept 22-29% of their first frame's detail against 40-100% for the rest).
- Real people the story names keep the identity text the plan gives them; never invent a face detail."""

# What the image-to-video model (MiniMax H3) renders on the first take, and what got takes rejected: 340
# reviewer problems across every local-ai project (2026-10-31): 25% a camera move that did not happen as
# planned, 19% planned motion too weak, 18% a detail unlike the plan, 16% objects appearing or vanishing,
# 9% an end state never reached.
MOTION_RULES = """How to write the motion so the first take passes:
- ONE simple motion that runs steadily through the whole clip, already underway in the first frame: sails
  or a wheel turning at an even speed, water flowing, grass and cloth swaying in a steady breeze, a cart or a
  person moving straight toward or away from the camera. Never a sequence of events.
- Say how things move, never where they end up: no "ends close on", "until", "settles", "comes to rest",
  "by the end", and no final composition. The model does not reach planned end states.
- The camera holds still, or makes one slow, steady push in with no target framing. Never rise, tilt,
  crane, orbit, pan or pull back to reveal: a quarter of all rejections were camera moves that did not
  happen as planned.
- Nothing changes in amount: no filling tank, rising level, growing pile, spreading crack or gathering
  crowd. Show the state the beat is about.
- Nothing enters, leaves, appears or disappears, and every moving part is fully visible in the first frame.
- A mechanism may turn or slide; it never changes shape (no folding, swinging arms, a pole sweeping round):
  changing shapes morph.
- Never dust, haze, smoke, mist, fog, steam or spray as the motion: they blur the whole clip.
- At most 30 words, plain and concrete."""

# Free check of a designed shot against MOTION_RULES and the haze rule, before any GPU time is spent.
_HAZE = re.compile(r"\b(?:dust(?:y|s)?|haze|hazy|mist|misty|fog|foggy|smoke|smoky|steam|spray|glare|backlit|"
                   r"silhouett\w*|lens flare|sunburst|into the sun)\b", re.I)
_END_STATE = re.compile(r"\b(?:ends? (?:close|on|with|at|in|up|framed|tight)|until|settles?|settling|"
                        r"comes? to rest|by the end|at the end|finally|in the last frame)\b", re.I)
_CAMERA = re.compile(r"\b(?:rise[sd]?|rising|tilt\w*|crane[sd]?|craning|orbit\w*|pans?|panning|"
                     r"pull(?:s|ing)? (?:back|out)|pull-back|pull-out|reveal\w*|zoom\w*)\b", re.I)
_AMOUNT = re.compile(r"\b(?:fill(?:s|ing)?|rising level|level rises|grow(?:s|ing)|spread(?:s|ing)|"
                     r"gather(?:s|ing)|appears?|appearing|disappear\w*|vanish\w*|emerg\w*)\b", re.I)
# Lighthouse shot-003 asked for "exactly one tiny orange pinpoint" of a far-off fire: three takes drew two fires
# or a large blaze. A tiny subject is redrawn large, and an exact count of small things is not kept.
_TINY = re.compile(r"\b(?:tiny|pinpoint|speck|dot of|faint glow|exactly (?:one|two|three|a single))\b", re.I)
# Lighthouse shot-015: "exactly twelve polished silver bowl mirrors in a ring, each with its own small flame" went
# soft on every take (29-30% of the keyframe's detail). Many small repeated parts are fine detail the model smears.
_MANY = re.compile(r"\b(?:exactly\s+(?:[5-9]|\d{2,}|five|six|seven|eight|nine|ten|eleven|twelve|twenty|dozen)\b|"
                   r"dozens? of|rings? of|many small|each with its own)", re.I)
# Lighthouse shot-009: "coal glowing only faintly red, faint embers pulse weakly" went soft twice (31-32% of the
# keyframe's detail kept), then flared into a blaze. A dim subject has no detail for the model to keep.
# Windmill shot-015 (both runs): "water pours from the pipe into the tank" failed four takes each time (the stream
# arced short, came out as a white splash, or hid behind the tank rim); liquid streams passed 60% of first takes.
_POUR = re.compile(r"\b(?:pour(?:s|ing)?|gush\w*|spurt\w*|stream(?:s|ing)? (?:of water|into|from)|"
                   r"water (?:runs|running|flows|flowing|falls|falling) (?:into|from|out))\b", re.I)
_DIM = re.compile(r"\b(?:faint(?:ly)?|dim(?:ly)?|embers?|smoulder\w*|glowing only|weak(?:ly)?)\b", re.I)


def design_problems(frame: str, motion: str) -> list[str]:
    """What in a designed shot breaks the measured first-take rules; empty when it is clean."""
    problems = []
    for word in sorted({m.group(0).lower() for m in _HAZE.finditer(f"{frame} {motion}")}):
        problems.append(f"'{word}': haze, dust, smoke and glare blur the whole clip; use crisp clear light")
    for word in sorted({m.group(0).lower() for m in _TINY.finditer(f"{frame} {motion}")}):
        problems.append(f"'{word}': a tiny subject or an exact count of small things is redrawn large or "
                        "doubled; make the subject large and clear in the frame")
    for word in sorted({m.group(0).lower() for m in _POUR.finditer(motion)}):
        problems.append(f"'{word}': a stream of liquid pouring into a container rarely renders; show the water "
                        "already standing in it, rippling, while the machine that fills it moves")
    for word in sorted({m.group(0).lower() for m in _MANY.finditer(f"{frame} {motion}")}):
        problems.append(f"'{word}': many small repeated parts are fine detail the model smears; frame one or two "
                        "of them large and close instead")
    for word in sorted({m.group(0).lower() for m in _DIM.finditer(f"{frame} {motion}")}):
        problems.append(f"'{word}': a dim or faintly glowing subject has no detail to keep and goes soft or "
                        "flares; show it brightly lit by daylight, its state carried by its look (soot, ash)")
    for regex, why in ((_END_STATE, "names an end state the model never reaches; say how it moves"),
                       (_CAMERA, "a camera move the model does not follow; hold still or push in slowly"),
                       (_AMOUNT, "an amount that changes or a thing that appears; show the state instead")):
        for word in sorted({m.group(0).lower() for m in regex.finditer(motion)}):
            problems.append(f"'{word}': {why}")
    if len(motion.split()) > 40:
        problems.append(f"the motion is {len(motion.split())} words; keep it to one steady motion in 30")
    return problems

DESIGN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["shots"],
    "properties": {
        "shots": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["shot", "render", "motion_need", "frame", "motion", "still_move", "subjects",
                             "sound_bed", "sound_spot"],
                "properties": {
                    "shot": {"type": "integer"},
                    "render": {"type": "string", "enum": ["motion", "still"]},
                    "motion_need": {
                        "type": "integer", "minimum": 0, "maximum": 10,
                        "description": "How much the beat loses as a still photograph with a slow camera move: "
                                       "10 = the movement IS the beat (a wave surging, a dog sprinting, a tank "
                                       "bursting); 0 = a place, an object, an aftermath or a portrait.",
                    },
                    "frame": {
                        "type": "string",
                        "description": "The photograph FLUX draws for this shot, 40-90 words, starting with the "
                                       "shot size. For a motion shot: the opening instant the movement starts "
                                       "from, with the moving thing already present. For a still shot: the "
                                       "single moment that tells the beat.",
                    },
                    "motion": {
                        "type": "string",
                        "description": "For a motion shot, 15-30 words: the ONE steady motion of the ~3 s clip, "
                                       "already underway in that frame, and what the camera does (holds still "
                                       "or pushes in slowly). How things move, never where they end up. Only "
                                       "what this beat shows: never a later event of the story. Empty for a "
                                       "still.",
                    },
                    "still_move": {"type": "string", "enum": list(STILL_MOVES)},
                    "sound_bed": {"type": "string", "enum": ["", *sound.BEDS],
                                  "description": "The looping sound of this shot's place, or empty for quiet."},
                    "sound_spot": {"type": "string", "enum": ["", *sound.SPOTS],
                                   "description": "One effect for the shot's action, or empty (most shots)."},
                    "subjects": {
                        "type": "array", "items": {"type": "integer"},
                        "description": "Numbers of the recurring subjects this frame shows looking as described "
                                       "(whole and unchanged); leave out one shown destroyed or changed.",
                    },
                },
            },
        },
    },
}

_MOTION_WORDS = re.compile(
    r"\b(?:run|runs|running|sprint\w*|race[sd]?|racing|surg\w*|rush\w*|pour\w*|flow\w*|burst\w*|explod\w*|"
    r"collaps\w*|crash\w*|fall\w*|falls|march\w*|walk\w*|charg\w*|gallop\w*|fly|flies|flying|swim\w*|"
    r"splash\w*|spray\w*|wave[sd]?|roll\w*|spin\w*|swing\w*|throw\w*|launch\w*|erupt\w*|blow\w*|"
    r"chas\w*|flee\w*|jump\w*|leap\w*|climb\w*|drag\w*|push\w*|pull\w*|lift\w*|dig\w*|scrap\w*|"
    r"shovel\w*|hammer\w*|smash\w*|tear\w*|tore|rip\w*)\b", re.I)


def heuristic_design(manifest: ProjectManifest, motion_count: int) -> dict[str, dict[str, Any]]:
    """The design without a model: motion where the beat's words move, the hook first."""
    scored = []
    for shot in manifest.shots:
        need = min(10, 2 * len(_MOTION_WORDS.findall(shot.subject_action)))
        if shot.index == 0:
            need = max(need, 9)
        scored.append((need, shot))
    ranked = sorted(scored, key=lambda item: (-item[0], item[1].index))
    motion = {shot.id for _, shot in ranked[:motion_count]}
    return {shot.id: {"render": "motion" if shot.id in motion else "still", "motion_need": need,
                      "frame": "", "still_move": STILL_MOVES[shot.index % 2], "source": "heuristic"}
            for need, shot in scored}


def _design_prompt(manifest: ProjectManifest, motion_count: int) -> str:
    script = manifest.script or {}
    lines = []
    for shot in manifest.shots:
        cast = f" | named on screen: {', '.join(shot.cast)}" if shot.cast else ""
        # The place's own sentence of the script's world: without it the shared landscape (the same river and
        # far-bank oak under every bridge of an evolution film) never reached the frames FLUX draws.
        world = str((shot.continuity or {}).get("location") or "").strip()
        lines.append(
            f"Shot {shot.index + 1} ({shot.duration_seconds:.1f} s) | narration: \"{shot.narration.strip()}\" | "
            f"planned visual: {shot.subject_action.strip()} | place: {shot.scene or '-'}"
            f"{f' ({world})' if world else ''} | light: {shot.light or '-'}{cast}")
    first = manifest.shots[0].continuity if manifest.shots else {}
    period = str((first or {}).get("period") or "")
    objects = " ".join(f"[{n}] {item}" for n, item in enumerate(script.get("recurring_objects") or [], 1))
    mixed = motion_count < len(manifest.shots)
    if mixed:
        render = ("\nEach shot below becomes either a MOTION shot (an image-to-video model animates it for ~3 s "
                  "from a first frame) or a STILL shot (one photograph with a slow camera move over it, like a "
                  f"documentary photo). The time budget allows exactly {motion_count} motion shot(s) out of "
                  f"{len(manifest.shots)}. Give motion to the shots whose beat is lost without real movement (the "
                  "hook, the surge, the collapse, the chase), the opening shot above all; give stills to places, "
                  "objects, portraits, aftermath and anything quiet. Spread the motion shots through the video "
                  "rather than bunching them.\n\n")
    else:
        render = ("\nEvery shot below is a MOTION shot: an image-to-video model animates it for ~3 s from the "
                  "first frame you write. Set render to motion for all of them; still_move is only the fallback "
                  "camera move if a clip fails.\n\n")
    return (
        f"Video: {manifest.concept}\n"
        + (f"Story period: {period}\n" if period else "")
        + f"Visual style: {manifest.visual_style}\n"
        + (f"Recurring subjects, numbered (repeat each one's look word for word in every frame that shows it, "
           f"and list its number in that shot's subjects): {objects}\n" if objects else "")
        + render
        + "For EVERY shot, write the photograph a text-to-image model (FLUX.1-schnell) draws: the opening "
          "instant the movement starts (for a still, the telling moment). Keep the beat's facts, place, era, "
          "light and named people; change only how it is staged so the model can draw it. For a motion shot "
          "also write its motion: the clip is generated from your frame and your motion and judged against "
          "them, so together they must tell the beat in something both models can really film. The planned "
          "visual is a wish, not a contract: a spectacle no camera could catch (a wave taller than a house "
          "racing at the lens, a building splitting in half) is restaged at the scale real footage shows it "
          "(a knee-deep surge of dark syrup sweeping along the street past the camera, dark syrup spurting "
          "through a split seam), never dropped. A calm shot's motion stays calm: an intact object stays "
          "intact, and nothing from a later beat happens in it.\n"
        + FRAME_RULES
        + "\n\n" + MOTION_RULES
        + "\n\nMotion shots use motion this video model renders well: water, flags and cloth in "
          "wind, people walking, talking or working, vessels moving, a slow camera move. It renders badly a "
          "hand doing a precise thing to a prop (tugging a net, tying, handing over, writing: the Ghost Army "
          "soldier walked past the net in four takes): let people walk, turn, look, talk, gesture or carry "
          "something they already hold, and let objects move by wind, water or the camera. It also renders "
          "badly an explosion starting, something breaking or falling, a crowd running, or an object "
          "appearing: " + ("give those beats to stills, or " if mixed else "")
          + "start the motion just after the event (smoke already rising, debris settling, people turning to "
          "look). Every frame must hold something that can move naturally for 3 s: water, cloth, grass, "
          "people at work, light, a vessel, or at least depth for a slow camera move."
        + "\n\nSOUND: the clips are silent, so give each shot the sound a viewer expects to hear there, under "
          "the narration. sound_bed is the looping sound of the place (keep the same bed across shots in the "
          "same place, so it flows across the cuts); sound_spot is one effect for a visible action (a plane "
          "passing, a hammer blow, steam hissing), on about one shot in three, never on a quiet portrait. "
          "Only sounds of the story's era: no traffic before cars. Beds: "
          + "; ".join(f"{name} = {use}" for name, use in sound.BEDS.items())
          + ". Spots: " + "; ".join(f"{name} = {use}" for name, use in sound.SPOTS.items()) + "."
        + "\n\nFor a still, pick the camera move that best reveals it: push_in toward the focal subject, "
          "pull_out to reveal scale, pan_left/pan_right across a wide scene, rise up a tall subject.\n\n"
        + "SHOTS:\n" + "\n".join(lines)
        + "\n\nReturn one entry per shot, in order. Submit the structured output."
    )


def recurring_labels(manifest: ProjectManifest) -> list[str]:
    """The script's recurring subjects by label, in order (the designer refers to them by number)."""
    return [re.sub(r"\(.*?\)", "", str(item).partition(":")[0]).strip()
            for item in (manifest.script or {}).get("recurring_objects") or []]


def design_shots(manifest: ProjectManifest, motion_count: int) -> dict[str, dict[str, Any]]:
    """Decide which shots move and write a drawable first frame for each; cached in the manifest.

    One text call (~30-60 s). Falls back to a motion-word heuristic and the plan's own visuals.
    """
    cached = manifest.settings.get("fast_design") or {}
    if cached and all(shot.id in cached for shot in manifest.shots):
        return cached
    design = heuristic_design(manifest, motion_count)
    if env_int("LOCAL_VIDEO_DESIGN", 1, 0, 1) == 1:
        try:
            from agents import llm
            started = time.monotonic()
            values = llm.ask(
                "You are the director of photography for a short vertical documentary made with local "
                "image and video generators.", _design_prompt(manifest, motion_count), DESIGN_SCHEMA,
                effort="low")
            labels = recurring_labels(manifest)
            rows = values.get("shots") if isinstance(values, dict) else None
            by_number = {int(row.get("shot", 0)): row for row in rows or [] if isinstance(row, dict)}
            for shot in manifest.shots:
                row = by_number.get(shot.index + 1)
                if not row:
                    continue
                frame = str(row.get("frame") or "").strip()
                motion = str(row.get("motion") or "").strip()
                design[shot.id] = {
                    "render": "motion" if row.get("render") == "motion" else "still",
                    "motion_need": max(0, min(10, int(row.get("motion_need") or 0))),
                    "frame": frame if len(frame) >= 30 else "",
                    "motion": motion if len(frame) >= 30 and len(motion) >= 15 else "",
                    "still_move": row.get("still_move") if row.get("still_move") in STILL_MOVES else "push_in",
                    "subjects": [labels[n - 1] for n in row.get("subjects") or []
                                 if isinstance(n, int) and 0 < n <= len(labels)],
                    "sound_bed": row.get("sound_bed") if row.get("sound_bed") in sound.BEDS else "",
                    "sound_spot": row.get("sound_spot") if row.get("sound_spot") in sound.SPOTS else "",
                    "source": "designer",
                }
            log.info("Shot design ready in %.0fs", time.monotonic() - started)
            _repair_design(manifest, design)
        except Exception as exc:     # the plan's own visuals still work; only the first takes suffer
            log.warning("Shot design unavailable (%s); using the plan's visuals", exc.__class__.__name__)
    _cap_motion(design, manifest, motion_count)
    with MANIFEST_LOCK:
        manifest.settings["fast_design"] = design
        manifest.record("shots_designed", motion=[s for s, d in design.items() if d["render"] == "motion"],
                        budget=motion_count)
    manifest.save()
    return design


_SHOT_SIZE = re.compile(r"^\s*(extreme close-up|close-up|medium shot|wide shot|medium close-up|medium wide)", re.I)


def same_picture(before: dict[str, Any], after: dict[str, Any], shot_before: Shot, shot_after: Shot) -> bool:
    """Two neighbouring shots in one place at one shot size read as one picture twice (lighthouse beats 7-8:
    the same brazier tower on the same shingle; windmill shots 19-20: the same steel windmill)."""
    scene = getattr(shot_before, "scene", "")
    if not scene or scene != getattr(shot_after, "scene", ""):
        return False
    size_before = _SHOT_SIZE.match(str(before.get("frame") or ""))
    size_after = _SHOT_SIZE.match(str(after.get("frame") or ""))
    return bool(size_before and size_after and size_before.group(1).lower() == size_after.group(1).lower())


def _repair_design(manifest: ProjectManifest, design: dict[str, dict[str, Any]]) -> None:
    """Rewrite, once, every designed shot that breaks the first-take rules; cheaper than any rejected take."""
    flagged = {shot.id: design_problems(design[shot.id].get("frame", ""), design[shot.id].get("motion", ""))
               for shot in manifest.shots if design.get(shot.id, {}).get("source") == "designer"}
    for before, shot in zip(manifest.shots, manifest.shots[1:]):
        if shot.id in flagged and same_picture(design.get(before.id, {}), design[shot.id], before, shot):
            flagged[shot.id].append(f"looks like shot {before.index + 1} just before it (same place, same shot "
                                    "size): change the shot size or the angle, or show another part of the place")
    flagged = {shot_id: problems for shot_id, problems in flagged.items() if problems}
    if not flagged:
        return
    log.info("Shot design: rewriting %d shot(s) that break the first-take rules: %s", len(flagged),
             ", ".join(flagged))
    from agents import llm
    for shot in manifest.shots:
        problems = flagged.get(shot.id)
        if not problems:
            continue
        row = design[shot.id]
        prompt = (f"Video: {manifest.concept}\nVisual style: {manifest.visual_style}\n"
                  f"Shot {shot.index + 1} narration: \"{shot.narration.strip()}\"\n"
                  f"Frame: {row.get('frame')}\nMotion: {row.get('motion')}\n"
                  "This staging breaks rules that get first takes rejected:\n- " + "\n- ".join(problems)
                  + "\n\nRewrite the frame and the motion so they tell the same beat in the same place, era and "
                    "light, with every problem gone. Keep whatever already works.\n" + FRAME_RULES
                  + "\n\n" + MOTION_RULES + "\n\nSubmit the structured output.")
        try:
            values = llm.ask("You are the director of photography. You fix shot designs before they are filmed.",
                             prompt, RESTAGE_SCHEMA, effort="low")
        except Exception as exc:      # the original design still films; it is only likelier to need a retake
            log.warning("Shot design repair failed for %s (%s)", shot.id, exc.__class__.__name__)
            continue
        frame = str((values or {}).get("frame") or "").strip()
        motion = str((values or {}).get("motion") or "").strip()
        if len(frame) >= 30 and (len(motion) >= 15 or not row.get("motion")):
            left = design_problems(frame, motion)
            row.update(frame=frame, motion=motion if row.get("motion") else "", repaired=problems)
            if left:
                log.info("Shot design %s still has: %s", shot.id, "; ".join(left))


def _cap_motion(design: dict[str, dict[str, Any]], manifest: ProjectManifest, motion_count: int) -> None:
    """Exactly the affordable number of motion shots, the most motion-dependent ones."""
    order = sorted(manifest.shots, key=lambda s: (design[s.id]["render"] != "motion",
                                                   -design[s.id]["motion_need"], s.index))
    keep = {shot.id for shot in order[:motion_count]}
    for shot in manifest.shots:
        design[shot.id]["render"] = "motion" if shot.id in keep else "still"


RESTAGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["frame", "motion"],
    "properties": {
        "frame": {"type": "string", "description": "The new first frame FLUX draws, 40-90 words, shot size first."},
        "motion": {"type": "string", "description": "The ONE steady motion of the ~3 s clip from that frame and "
                                                    "what the camera does, 15-30 words; never where things end up."},
    },
}


def restage(manifest: ProjectManifest, shot: Shot, failures: list[str]) -> dict[str, str] | None:
    """A new, simpler staging for a shot whose every take was rejected: one text call.

    Ghost Army shot-018 ("If discovered, they faced grave danger") failed four takes on an inflatable tank
    that read as a blob and a glove that appeared mid-clip, then played as a still picture. Telling the same
    beat with what the models film well (a soldier in the rain scanning the sky) is better than any fallback.
    """
    design = designed(manifest, shot)
    planned = design.get("planned_action") or shot.subject_action
    prompt = (
        f"Video: {manifest.concept}\nVisual style: {manifest.visual_style}\n"
        f"Shot {shot.index + 1} narration: \"{shot.narration.strip()}\"\n"
        f"Planned visual: {planned}\n"
        f"Staging tried: {design.get('frame') or shot.subject_action} {design.get('motion') or ''}\n"
        "Every clip of that staging was rejected by the reviewer for:\n- "
        + "\n- ".join(failure[:400] for failure in failures[:6])
        + "\n\nWrite a NEW staging that tells the same beat with something a text-to-image model (FLUX.1-"
          "schnell) and an image-to-video model really film well: one clear subject, simple shapes, natural "
          "motion (people walking, turning, looking; water, cloth, grass, a vehicle driving forward; a slow "
          "push in). Drop the element that kept failing rather than describing it harder. Keep the story's "
          "era, place and light.\n" + FRAME_RULES + "\n\n" + MOTION_RULES
        + "\n\nSubmit the structured output."
    )
    from agents import llm
    values = llm.ask("You are the director of photography rescuing a shot the video model keeps failing.",
                           prompt, RESTAGE_SCHEMA, effort="low")
    frame = str((values or {}).get("frame") or "").strip()
    motion = str((values or {}).get("motion") or "").strip()
    if len(frame) < 30 or len(motion) < 15:
        return None
    return {"frame": frame, "motion": motion}


def designed(manifest: ProjectManifest, shot: Shot) -> dict[str, Any]:
    return (manifest.settings.get("fast_design") or {}).get(shot.id) or {}


def is_motion(manifest: ProjectManifest, shot: Shot) -> bool:
    design = designed(manifest, shot)
    return not design or design.get("render") == "motion"


def frame_view(manifest: ProjectManifest, shot: Shot) -> Shot:
    """The shot as its keyframe should draw and be judged: the designed frame as its visual action."""
    design = designed(manifest, shot)
    frame = design.get("frame") or ""
    if not frame:
        return shot
    continuity = dict(shot.continuity or {})
    if design.get("source") == "designer":       # it names the recurring subjects it shows (see keyframes)
        continuity["subjects_shown"] = list(design.get("subjects") or [])
    return replace(shot, subject_action=frame, continuity=continuity)


def demote(manifest: ProjectManifest, shot: Shot, reason: str) -> None:
    with MANIFEST_LOCK:
        design = manifest.settings.setdefault("fast_design", {}).setdefault(
            shot.id, {"motion_need": 0, "frame": "", "still_move": "push_in", "source": "demoted"})
        design["render"] = "still"
        manifest.record("shot_demoted_to_still", shot=shot.id, reason=reason)
    log.info("Fast mode: %s becomes a still (%s)", shot.id, reason)


# ---------------------------------------------------------------------------------------------------
# Parallax stills

def hires_keyframe(manifest: ProjectManifest, shot: Shot) -> Path | None:
    """The full-resolution FLUX frame of a shot's approved keyframe, else the keyframe itself."""
    root = Path(manifest.project_dir) / "keyframes"
    for path in (root / f"{shot.id}.hires.png", root / f"{shot.id}.png"):
        if path.is_file():
            return path
    return None


def render_still(manifest: ProjectManifest, shot: Shot, config, source: Path | None = None,
                 move: str | None = None) -> Path | None:
    """A depth-parallax camera move over one image, 1080x1920, a little longer than the shot.

    The extra half second lets assembly re-fit the cut to the spoken words without freezing a frame.
    """
    image = source or hires_keyframe(manifest, shot)
    if image is None:
        return None
    from agents.animate import render_scene
    camera = move or designed(manifest, shot).get("still_move") or "push_in"
    target = Path(manifest.project_dir) / "shots" / f"{shot.id}-still.mp4"
    target.parent.mkdir(parents=True, exist_ok=True)
    frames = int(math.ceil((shot.duration_seconds + 0.5) * 30))
    started = time.monotonic()
    render_scene(str(image), frames, str(target), camera=camera, punch=False)
    log.info("Still %s rendered (%s, %.1fs) in %.0fs", shot.id, camera, frames / 30, time.monotonic() - started)
    return target


def accept_still(manifest: ProjectManifest, shot: Shot, path: Path, config, *, planned: bool,
                 reason: str = "") -> None:
    """Mark a parallax still as the shot's output. A planned still is not a salvage."""
    from .validation import ffprobe, media_metadata
    metadata = media_metadata(ffprobe(path, config))
    with MANIFEST_LOCK:
        shot.backend = "still"
        shot.output = str(path.relative_to(manifest.project_dir))
        shot.validation = {**metadata, "valid": True, "problems": [], "still": True}
        shot.status = "accepted"
        shot.error = None
        shot.degraded = "" if planned else "still"
        manifest.record("shot_rendered_as_still", shot=shot.id, planned=planned, reason=reason)
