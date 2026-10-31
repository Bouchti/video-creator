"""Sound for local-ai videos: a bed and one spot effect per shot from the realistic library (agents/sfx_library).

The clips are silent (MiniMax's own audio is removed: it can invent voices and music), and the ambience
track was silence, so the Ghost Army video (2026-10-31) had only a voice and music; the user asked for
sound effects. The shot designer (fast.py) picks, for each shot, a looping bed for its place and at most
one spot effect for its action; this module lays them on the shots' real times under the narration.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .models import ProjectManifest

log = logging.getLogger("pipeline")

# Loops that can sit under a whole shot, with what each one is for (the designer reads these).
BEDS = {
    "wind": "wind over open ground: fields, hills, beaches, ruins, any quiet outdoor place",
    "rain": "heavy rain",
    "lake": "calm water lapping: a lake, a harbour, a dock, a riverbank",
    "water_rush": "rushing or gushing water: a flood, a torrent, a leak",
    "rumble": "deep rumble: a crowd of heavy machines, a convoy far off, earth moving, a disaster building",
    "engine": "a diesel engine running: trucks, tractors, a jeep, machinery close by",
    "engine_rev": "a diesel engine revving and moving: vehicles driving off, a convoy passing",
    "plane_engine": "a propeller plane engine running",
    "boat_motor": "a small boat motor",
    "train_pass": "an old steam train clattering past",
    "traffic": "cars passing on a road (modern stories only)",
    "hum": "an electric hum: a workshop, a control room, a radio room",
    "turbine": "a big machine spinning: a turbine, a generator, a factory",
    "boil": "liquid boiling and bubbling: a kettle, a vat, a cauldron",
    "weld": "welding sparks crackling",
    "bubbles": "underwater bubbles",
    "roll": "wooden wheels rolling over dirt: carts, wagons",
    "birds": "quiet countryside birds (kept very low)",
}
# One-shot effects for a shot's action, placed a little after its start.
SPOTS = {
    "plane_flyby": "a plane flying past overhead",
    "thunder": "distant thunder, or a far-off explosion or artillery",
    "ship_horn": "a big ship's horn",
    "crack": "something cracking or breaking: a wall, ice, a tank seam",
    "creak": "metal or wood groaning under strain",
    "steam_hiss": "steam or air hissing out: a valve, a compressor, an inflating balloon",
    "hammer": "one hammer blow",
    "step": "a footstep",
    "steel_clank": "heavy metal clanking into place",
    "stone_thud": "something heavy dropped on stone or ground",
    "splash": "a big splash",
    "clink": "small metal parts clinking",
    "rivet_pop": "a rivet or bolt popping out",
    "switch": "a heavy lever or switch thrown",
}
FPS = 30
BED_GAIN = 0.3           # under the voice, and ducked further while it speaks (assembly)
SPOT_GAIN = 0.45         # 0.8 was "exaggerated" (user, Ghost Army 2026-10-31)


def events(manifest: ProjectManifest) -> list[dict]:
    """The designed sound of every shot as sfx.render_events events, on the shots' assembled times."""
    design = manifest.settings.get("fast_design") or {}
    result: list[dict] = []
    start = 0.0
    for shot in manifest.shots:
        duration = float(shot.duration_seconds)
        plan = design.get(shot.id) or {}
        bed, spot = plan.get("sound_bed") or "", plan.get("sound_spot") or ""
        if bed in BEDS:
            previous = result[-1] if result and result[-1].get("bed") else None
            if previous and previous["kind"] == bed and previous["end"] == round(start, 3):
                previous["duration"] += duration * FPS             # one continuous bed across the cut
                previous["end"] = round(start + duration, 3)
            else:
                result.append({"kind": bed, "frame": start * FPS + 1, "duration": duration * FPS,
                               "gain": BED_GAIN, "bed": True, "end": round(start + duration, 3)})
        if spot in SPOTS:
            result.append({"kind": spot, "frame": (start + min(0.6, duration * 0.25)) * FPS + 1,
                           "gain": SPOT_GAIN})
        start += duration
    return result


def render(manifest: ProjectManifest, target: Path) -> bool:
    """Write the designed sound track (beds and spots) to `target`; False when the video has none."""
    planned = events(manifest)
    if not planned:
        return False
    from agents import sfx
    sfx.render_events(planned, FPS, float(manifest.duration_seconds), str(target), ambience=False)
    log.info("Sound: %d bed(s) and %d effect(s) under the narration", sum(1 for e in planned if e.get("bed")),
             sum(1 for e in planned if not e.get("bed")))
    return True
