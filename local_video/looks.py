"""
The look a local-ai film is filmed in.

  photo    real documentary footage (every route's default; nothing about it changes here)
  cutaway  photoreal 3D cutaway cross-section renders: the ground, walls and pipes sliced open to show
           the water and machinery inside, a tidy diorama scale and warm late-afternoon light. The look of
           the 1hidden_by_design wastewater Shorts (FLUX still -> MiniMax clip, hard cuts every 2-4 s),
           which the fast mode already matches in structure.

The look travels with the film: the script records it (`script["look"]`), every shot's continuity
carries it, and each layer that used to assume camera footage asks this module: the clip prompt, the
FLUX keyframe prompt, the negative prompt, and the keyframe, clip and final reviews (which otherwise
reject a cut-open ground as a "surreal set" and a render as "CGI").

`--source evolution` films in the cutaway look by default; EVOLUTION_LOOK=photo (or --look photo)
brings back the photoreal ladder.
"""
from __future__ import annotations

import os
from typing import Any

PHOTO = "photo"
CUTAWAY = "cutaway"
LOOKS = (PHOTO, CUTAWAY)

# One fixed style, word for word in every clip prompt and every FLUX still. FLUX takes no reference image:
# the reference Short keeps the same houses, soil and light across ~30 shots because every image was drawn
# from the same style text, so this text never varies from shot to shot.
CUTAWAY_STYLE = (
    "photoreal 3D cutaway cross-section render of a premium engineering explainer: the ground, walls and "
    "structures sliced open in one clean vertical cut that shows their inside, layered brown soil on the cut "
    "face, grey concrete chambers and white or grey pipes cut in half lengthwise so the water inside shows, "
    "bright clear blue water, green lawns and pale buildings above ground at a tidy miniature-diorama scale, "
    "soft warm late-afternoon sunlight with gentle shadows, crisp detailed materials, slight depth of field"
)
# Where the photo look says "real documentary footage ... 35mm lens" (planner.PHOTO_LOOK).
CUTAWAY_RENDER = (
    "crisp high-detail photoreal 3D render, clean believable materials (concrete, soil, metal, pipe, water), "
    "every cut face, pipe and chamber keeping its exact shape and position, stable geometry, smooth "
    "physically plausible water flow"
)
# The negative prompt's look terms: the photo look bans "CGI, 3D render", which is this look itself.
CUTAWAY_BAN = (
    "cartoon, anime, flat colours, sketch, drawing, painting, low-poly, plastic toy look, dreamy haze, glow, "
    "bloom, soft focus, blurry, oversaturated colours, fantasy lighting, morphing, melting shapes, pipes or "
    "walls bending or merging, people, faces, hands"
)
CUTAWAY_LIGHT = "soft warm late-afternoon sunlight with gentle shadows"
# Where the camera stands. The photo look's "eye level about two metres above the ground" films the street
# surface and misses the cut; the reference always looks down at the cut face from an elevated three-quarter
# angle, and goes close only into the cut.
CUTAWAY_WIDE = ("elevated three-quarter view looking slightly down at the cut face, the sliced-open ground "
                "filling the lower two-thirds of the frame and the surface above it")
CUTAWAY_CLOSE = "close three-quarter view into the cut, the sliced-open part filling most of the frame"

# Prepended to every cutaway review: without it the reviewers read the sliced-open ground as a broken set.
CUTAWAY_REVIEW_NOTE = (
    "THIS FILM IS A PHOTOREAL 3D CUTAWAY EXPLAINER, NOT CAMERA FOOTAGE. Every picture is meant to be a clean "
    "3D render with the ground, walls, pipes and chambers sliced open in a cross-section: brown soil layers on "
    "the cut face, water and machinery visible inside, a tidy diorama scale. That cut-open view is REQUIRED; "
    "never call it a surreal set, a missing wall, a render artifact or the wrong setting. "
)
CUTAWAY_CLIP_LOOK = (
    "The film must look like a clean, crisp photoreal 3D cutaway render. A cartoon, flat, sketched or toy-like "
    "look, dreamy haze or glow over the whole frame, or pipes, walls, cut faces and chambers that melt, bend, "
    "merge or change shape between frames is fatal; milder softness, oversaturation or a waxy sheen must lower "
    "the image-quality score. "
)
CUTAWAY_FINAL_RULES = (
    "This is a photoreal 3D cutaway engineering explainer: the ground, walls and pipes are sliced open on "
    "purpose so the viewer sees inside, and no people appear. The story must have a clear hook, a causal "
    "problem -> fix progression and a visible payoff; the same cutaway style, light and world (buildings, "
    "soil, pipes) must persist between shots of the same stage; captions must be readable and stay away from "
    "interface edges. Reject repeated shots, random objects, illegible captions, montage-like non sequiturs, "
    "an ending that does not pay off the opening, a cartoon, flat or toy-like look, and pipes, walls or "
    "chambers that melt or morph."
)


def cutaway_framing(framing: str) -> str:
    """The cutaway camera for a shot the photo planner framed as `framing` (only its shot size is kept)."""
    text = str(framing or "").lower()
    return CUTAWAY_CLOSE if "close-up" in text or "macro" in text else CUTAWAY_WIDE


def look_of(data: Any) -> str:
    """The look recorded on a script or continuity dict, a Shot (its continuity) or a manifest (its script).

    Anything without a recorded look is a photo film, so every project made before looks existed is
    unchanged.
    """
    if data is not None and not isinstance(data, dict):
        data = getattr(data, "continuity", None) or getattr(data, "script", None)
    value = str((data or {}).get("look") or "").strip().lower() if isinstance(data, dict) else ""
    return value if value in LOOKS else PHOTO


def is_cutaway(data: Any) -> bool:
    return look_of(data) == CUTAWAY


def evolution_look() -> str:
    """The look --source evolution films in: EVOLUTION_LOOK, cutaway unless it says photo."""
    value = (os.getenv("EVOLUTION_LOOK") or CUTAWAY).strip().lower()
    return value if value in LOOKS else CUTAWAY
