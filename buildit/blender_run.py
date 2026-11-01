"""Run buildit/blender/build_scene.py on a job (one Blender process), with stale-frame protection."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess

from .assets.fetch import hdri
from .config import BLENDER, BLENDER_DIR, PKG

log = logging.getLogger("pipeline")


def code_hash() -> str:
    """Fingerprint of everything a frame depends on besides the job: the Blender code and the kit."""
    h = hashlib.sha1()
    for root in (BLENDER_DIR, os.path.join(PKG, "kit")):
        for dirpath, dirs, files in sorted(os.walk(root)):
            dirs.sort()
            for n in sorted(files):
                if n.endswith(".py"):
                    with open(os.path.join(dirpath, n), "rb") as f:
                        h.update(n.encode() + f.read())
    return h.hexdigest()[:16]


def job_for(run, out_dir: str, quality: str, frames=None, stills=None) -> dict:
    words = run.need("words.json")
    return {"storyboard": run.need("storyboard.json"), "words": words["words"], "duration": words["duration"],
            "quality": quality, "frames": frames, "stills": stills, "out_dir": os.path.abspath(out_dir),
            "hdri": hdri(), "code": code_hash()}


def render(job: dict, timeout: int = 7200) -> dict:
    out = job["out_dir"]
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "job.json")
    old = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None
    if old != job:                          # frames on disk belong to another plan or other code
        for n in os.listdir(out):
            if n.startswith("f_") or n == "anchors.json":
                os.remove(os.path.join(out, n))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(job, f)
    p = subprocess.run([BLENDER, "-b", "--factory-startup", "-P", os.path.join(BLENDER_DIR, "build_scene.py"),
                        "--", path], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout)
    events = [json.loads(line[8:]) for line in p.stdout.splitlines() if line.startswith("BUILDIT ")]
    done = next((e for e in events if e["event"] == "done"), None)
    if p.returncode != 0 or done is None:
        tail = "\n".join(p.stdout.splitlines()[-25:]) + "\n" + (p.stderr or "")[-1500:]
        raise RuntimeError(f"Blender failed for {out}:\n{tail}")
    return done
