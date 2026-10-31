"""
One-off quality probe: can local MiniMax H3 (FreeVideo) make the "3D cutaway explainer" look of the
reference video (glossy cross-section renders, blue water, warm light)? Text-to-video, no code paths of
the local-ai route are touched (its prompts force live-action realism and ban "3D render").

    python -m local_video.cutaway_probe                 # all shots, 2 seeds each
    python -m local_video.cutaway_probe --shots toilet --seeds 1

Clips land in output/_review/cutaway_probe/<shot>_s<seed>.mp4 with a timing log.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from config.paths import PROJECT_ROOT

from .backends import MiniMaxAdapter
from .config import PipelineConfig
from .freevideo import ensure_minimax
from .models import Shot
from .planner import h3_prompt

STYLE = ("Photoreal 3D cutaway cross-section render in the style of a premium engineering explainer: "
         "clean glossy materials, objects sliced exactly in half to show their inside, warm golden "
         "afternoon sunlight with soft shadows, gentle depth of field, crisp detail, 9:16 vertical frame")

SHOTS = {
    "toilet": (
        "A white ceramic toilet with a cistern stands in a bright bathroom with pale blue walls and white "
        "floor tiles. The toilet is sliced exactly in half from front to back, so the inside of the "
        "ceramic is visible: clear bright blue water fills the bowl and the S-shaped trap channel inside "
        "the white ceramic. Below the tiled floor slab, a smooth brown soil cross-section, and a white "
        "PVC drain pipe cut open lengthwise drops straight down from the toilet. The toilet flushes: the "
        "blue water swirls in the bowl, rushes through the S-shaped trap and pours down inside the open "
        "pipe into the ground. Camera: slow gentle push-in from the side at seat height, steady.",
        "Toilet flush, water rushing and gurgling down a pipe."),
    "pipe": (
        "Underground cross-section beside a house: the cream plaster wall of the house on the right, a "
        "green lawn with real grass blades on top, and below it a clean cut face of brown soil. A white "
        "PVC drain pipe, cut open lengthwise so its inside is visible, runs from under the house foundation "
        "with a smooth white elbow and slopes gently away under the lawn. Blue water flows quickly along "
        "the bottom of the open pipe, with small ripples and bubbles, carrying a few scraps of white "
        "toilet paper. Camera: slow lateral move following the flow along the pipe, steady.",
        "Water flowing and trickling inside a pipe, birds outside faintly."),
    "street": (
        "An open trench along a quiet residential street beside a concrete curb and sidewalk, with neat "
        "lawns and white houses with blue shutters. In the trench lies a large grey sewer pipe, cut open "
        "along its top so the inside is visible. A smaller white PVC pipe from a house joins it at an angle "
        "through a Y-shaped fitting, pouring blue-grey water into the big pipe, where the water flows "
        "away along the street. Camera: slow push-in along the trench from above, steady.",
        "Water flowing in a large pipe, light street ambience."),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default=",".join(SHOTS))
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--seconds", type=float, default=5.0)
    a = ap.parse_args()
    out = Path(PROJECT_ROOT) / "output" / "_review" / "cutaway_probe"
    out.mkdir(parents=True, exist_ok=True)
    config = PipelineConfig()
    config.minimax_seconds = a.seconds
    ok, where = ensure_minimax(config)
    if not ok:
        print(f"MiniMax is not available: {where}")
        return 1
    backend = MiniMaxAdapter(config)
    log = []
    for name in [s.strip() for s in a.shots.split(",") if s.strip()]:
        action, sound = SHOTS[name]
        prompt = h3_prompt(f"{STYLE}. {action} No subtitles, no on-screen text.", sound)
        for k in range(a.seeds):
            seed = 1000 + 37 * k
            target = out / f"{name}_s{seed}.mp4"
            if target.exists():
                print(f"skip {target.name} (exists)")
                continue
            shot = Shot(id=f"{name}-{seed}", index=k, duration_frames=int(a.seconds * 30), prompt=prompt,
                        negative_prompt="", seed=seed)
            t0 = time.monotonic()
            print(f"generating {target.name} ...", flush=True)
            result = backend.generate(shot, target)
            dt = time.monotonic() - t0
            print(f"  done in {dt / 60:.1f} min -> {result.path}", flush=True)
            log.append({"shot": name, "seed": seed, "minutes": round(dt / 60, 2), "path": str(result.path),
                        "prompt": prompt})
            (out / "probe_log.json").write_text(json.dumps(log, indent=1), encoding="utf-8")
    print(f"clips in {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
