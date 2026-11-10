"""
Stage 9 - hf/: the HyperFrames project (buildit/compose.py): every rendered shot as its own scene with the label
pills that belong to it (following the Blender anchors), word-pop captions over the whole video, the mix.
"""
from __future__ import annotations

import logging
import os

from .. import compose
from ..runner import StageError

log = logging.getLogger("pipeline")


def inputs(run):
    q = run.quality
    return [run.path("render", q, "render.json"), run.path("words.json"), run.path("storyboard.json"),
            os.path.abspath(compose.__file__)]


def labels(run, scenes) -> list[dict]:
    sb, W = run.need("storyboard.json"), run.need("words.json")["words"]
    out = []
    for lb, t0, t1 in compose.label_times(sb, W):
        scene = next((s for s in scenes if s["start"] <= t0 < s["end"]), None)
        if scene is None:
            continue
        out.append({"scene": scene["id"], "text": lb["text"], "variant": lb.get("variant", "neutral"),
                    "anchor": lb["anchor"] if "." in lb["anchor"] else lb["anchor"] + ".center",
                    "t0": t0, "t1": min(t1, scene["end"] - 0.05), "line": True})
    return out


def run(run):
    q = run.quality
    r = run.need(f"render/{q}/render.json")
    words = run.need("words.json")
    scenes = [{"id": s["shot"], "video": run.path("render", q, f"{s['shot']}.mp4"), "start": s["start"],
               "end": s["end"], "anchors": run.path("render", q, s["shot"], "anchors.json")} for s in r["shots"]]
    mix = run.path("audio", "mix.wav")
    if not os.path.exists(mix):
        mix = run.path("voice", "narration.wav")
    loop = compose.loop_info(run.need("storyboard.json"), words["words"], words["duration"])
    compose.project(run.path("hf"), scenes, words["words"], labels(run, scenes), mix, words["duration"],
                    run.need("brief.json")["title"], loop)


def validate(run):
    from cutaway import hf
    d = run.path("hf")
    if not os.path.exists(os.path.join(d, "index.html")):
        raise StageError("hf/index.html missing")
    r = hf.run(["lint"], cwd=d, check=False, timeout=600)
    import re
    errors = re.findall(r"(\d+) error", r.stdout or "")
    if r.returncode != 0 or (errors and int(errors[-1]) > 0):
        raise StageError("hyperframes lint failed:\n" + (r.stdout or "")[-3000:])
