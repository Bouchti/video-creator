"""
Stage 8 - render/<quality>/: the final frames, one Blender process per shot (shots are the resume unit: a stopped
render restarts at the first missing frame), encoded per shot with a keyframe every second (HyperFrames seeks).
Shots render one after the other: the GPU is the limit, a second Blender process only halves each one's speed.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import time

from config.paths import get_ffmpeg

from .. import blender_run
from ..config import FPS
from ..runner import StageError

log = logging.getLogger("pipeline")


CHUNK = 8.0          # seconds: shots are grouped into render chunks (one Blender start per chunk, not per shot)


def shot_frames(run) -> list[tuple[str, int, int, float, float]]:
    """Render chunks (id, f0, f1, t0, t1): consecutive shots grouped to at least CHUNK seconds, cut on shot
    boundaries; the camera still changes on every shot inside a chunk."""
    sb, words = run.need("storyboard.json"), run.need("words.json")
    W = words["words"]
    cuts = [0.0] + [W[s["start_word"]]["start"] - 0.15 for s in sb["shots"][1:]] + [words["duration"]]
    bounds = [0.0]
    for c in cuts[1:-1]:
        if c - bounds[-1] >= CHUNK and words["duration"] - c >= CHUNK / 2:
            bounds.append(c)
    bounds.append(words["duration"])
    out = []
    for k, (a, b) in enumerate(zip(bounds, bounds[1:])):
        f0, f1 = int(round(a * FPS)) + 1, int(round(b * FPS))
        if out:
            f0 = out[-1][2] + 1
        out.append((f"s{k + 1:02d}", f0, f1, (f0 - 1) / FPS, f1 / FPS))
    return out


def inputs(run):
    return [run.path("storyboard.json"), run.path("words.json"), run.quality, blender_run.code_hash()]


def encode(src_dir: str, f0: int, dst: str):
    subprocess.run([get_ffmpeg(), "-v", "error", "-y", "-framerate", str(FPS), "-start_number", str(f0), "-i",
                    os.path.join(src_dir, "f_%04d.png"), "-vf", "scale=1080:1920:flags=lanczos", "-c:v", "libx264",
                    "-preset", "medium", "-crf", "15", "-g", str(FPS), "-pix_fmt", "yuv420p", dst], check=True)


def run(run):
    q = run.quality
    report, t_all = [], time.time()
    for sid, f0, f1, t0, t1 in shot_frames(run):
        out = run.path("render", q, sid)
        t = time.time()
        done = blender_run.render(blender_run.job_for(run, out, q, frames=[f0, f1]))
        encode(out, f0, run.path("render", q, f"{sid}.mp4"))
        report.append({"shot": sid, "frames": [f0, f1], "start": round(t0, 3), "end": round(t1, 3),
                       "rendered": done["rendered"], "s_per_frame": done["s_per_frame"],
                       "seconds": round(time.time() - t, 1)})
        log.info("[render] %s %d-%d: %d frames, %.2f s/frame", sid, f0, f1, done["rendered"], done["s_per_frame"])
    run.save(f"render/{q}/render.json", {"shots": report, "seconds": round(time.time() - t_all, 1)})


def validate(run):
    q = run.quality
    r = run.need(f"render/{q}/render.json")
    for s in r["shots"]:
        if not os.path.exists(run.path("render", q, f"{s['shot']}.mp4")):
            raise StageError(f"{s['shot']}.mp4 missing")
        f0, f1 = s["frames"]
        missing = [f for f in range(f0, f1 + 1) if not os.path.exists(run.path("render", q, s["shot"], f"f_{f:04d}.png"))]
        if missing:
            raise StageError(f"{s['shot']}: {len(missing)} frames missing")
