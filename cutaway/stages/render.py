"""
Stage 7 - Blender renders: one job per shot over its exact global frames (frame = round(t * 30) + 1), run by
parallel headless Blender workers. Frames already on disk are skipped (resume). Each shot is then encoded to
render/<shot>.mp4 with a keyframe every second so HyperFrames seeks it exactly.

--draft: EEVEE at half resolution. --final: Cycles on OptiX with the denoiser and motion blur, full 1080x1920.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from config.paths import get_ffmpeg

from .. import kits
from ..assets.fetch import polyhaven_hdri
from ..config import BLENDER, BLENDER_DIR, FPS
from ..runner import StageError

log = logging.getLogger("pipeline")
HDRI = "studio_small_09"


def frames_of(shot) -> tuple[int, int]:
    return int(round(shot["start"] * FPS)) + 1, int(round(shot["end"] * FPS))


def inputs(run):
    return [run.path("shotlist.json"), run.quality, BLENDER_DIR]


def _job(run, shot, sl, quality) -> str:
    f0, f1 = frames_of(shot)
    out_dir = run.path("render", quality, shot["id"])
    os.makedirs(out_dir, exist_ok=True)
    job = {
        "assembly": kits.KITS[sl["kit"]]["assembly"],
        "quality": quality, "out_dir": out_dir, "frames": [f0, f1],
        "crank": sl["crank"], "events": sl.get("events", []), "hdri": polyhaven_hdri(HDRI),
        "shot": {"id": shot["id"], "cut": shot["cut"], "camera": shot["camera_spec"],
                 "anchors": sorted({c["anchor"] for c in shot["callouts_t"]} | {shot["camera"]["focus"]})},
    }
    job["code"] = _code_hash()
    path = os.path.join(out_dir, "job.json")
    old = None
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            old = json.load(f)
    if old != job:
        # frames on disk belong to another plan or other Blender code: never mix them into this shot
        stale = [n for n in os.listdir(out_dir) if n.startswith("f_") or n == "anchors.json"]
        for n in stale:
            os.remove(os.path.join(out_dir, n))
        if stale and old is not None:
            log.info("[render] %s: plan or 3D code changed, %d old files cleared", shot["id"], len(stale))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(job, f, indent=1)
    return path


def _code_hash() -> str:
    """Fingerprint of the Blender-side code and the kits (what a frame depends on besides the job)."""
    h = hashlib.sha1()
    for root in (BLENDER_DIR, os.path.join(os.path.dirname(BLENDER_DIR), "kits")):
        for dirpath, dirs, files in sorted(os.walk(root)):
            dirs.sort()
            for n in sorted(files):
                if n.endswith(".py"):
                    with open(os.path.join(dirpath, n), "rb") as f:
                        h.update(n.encode() + f.read())
    return h.hexdigest()[:16]


def _render_shot(run, shot, sl, quality, lock) -> dict:
    job = _job(run, shot, sl, quality)
    t = time.time()
    cmd = [BLENDER, "-b", "--factory-startup", "-P", os.path.join(BLENDER_DIR, "render_shot.py"), "--", job]
    frames, secs = 0, []
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                          errors="replace") as p:
        tail = []
        for line in p.stdout:
            tail = (tail + [line.rstrip()])[-40:]
            if line.startswith("CUTAWAY "):
                ev = json.loads(line[8:])
                if ev["event"] == "frame":
                    frames += 1
                    secs.append(ev["seconds"])
                elif ev["event"] in ("cut", "baked", "done"):
                    with lock:
                        log.info("[render] %s %s", shot["id"], ev)
        p.wait()
    if p.returncode != 0:
        raise StageError(f"Blender failed on {shot['id']}:\n" + "\n".join(tail[-15:]))
    return {"shot": shot["id"], "rendered": frames, "seconds": round(time.time() - t, 1),
            "s_per_frame": round(sum(secs) / len(secs), 2) if secs else None}


def encode(run, shot, quality) -> str:
    f0, _ = frames_of(shot)
    src = run.path("render", quality, shot["id"], "f_%04d.png")
    dst = run.path("render", quality, f"{shot['id']}.mp4")
    subprocess.run([get_ffmpeg(), "-v", "error", "-y", "-framerate", str(FPS), "-start_number", str(f0), "-i", src,
                    "-vf", "scale=1080:1920:flags=lanczos", "-c:v", "libx264", "-preset", "medium", "-crf", "14",
                    "-g", str(FPS), "-pix_fmt", "yuv420p", "-movflags", "+faststart", dst], check=True)
    return dst


def run(run):
    sl = run.need("shotlist.json")
    quality = run.quality
    workers = int(run.meta.get("workers") or 2)
    lock = threading.Lock()
    t = time.time()
    shots = sorted(sl["shots"], key=lambda s: -(s["end"] - s["start"]))       # longest first: better packing
    def shot_with_retry(s):
        res = _render_shot(run, s, sl, quality, lock)
        if _missing(run, s, quality):                 # Blender can quit "cleanly" without frames (GPU memory)
            log.warning("[render] %s came back with missing frames: retrying once", s["id"])
            res = _render_shot(run, s, sl, quality, lock)
            gone = _missing(run, s, quality)
            if gone:
                raise StageError(f"{s['id']}: {len(gone)} frames still missing after a retry")
        return res
    with ThreadPoolExecutor(workers) as pool:
        results = list(pool.map(shot_with_retry, shots))
    for s in sl["shots"]:
        encode(run, s, quality)
    report = {"quality": quality, "workers": workers, "seconds": round(time.time() - t, 1),
              "shots": sorted(results, key=lambda r: r["shot"])}
    run.save(f"render/{quality}/render.json", report)
    run.meta["rendered_quality"] = quality
    run.save("run.json", run.meta)
    log.info("[render] %s: %.1f min for %d shots", quality, report["seconds"] / 60, len(results))


def _missing(run, shot, quality) -> list[int]:
    f0, f1 = frames_of(shot)
    d = run.path("render", quality, shot["id"])
    return [f for f in range(f0, f1 + 1) if not os.path.exists(os.path.join(d, f"f_{f:04d}.png"))]


def validate(run):
    sl = run.need("shotlist.json")
    q = run.quality
    for s in sl["shots"]:
        f0, f1 = frames_of(s)
        d = run.path("render", q, s["id"])
        missing = [f for f in range(f0, f1 + 1) if not os.path.exists(os.path.join(d, f"f_{f:04d}.png"))]
        if missing:
            raise StageError(f"{s['id']}: {len(missing)} frames missing (first {missing[0]})")
        if not os.path.exists(os.path.join(d, "anchors.json")):
            raise StageError(f"{s['id']}: anchors.json missing")
        if not os.path.exists(run.path("render", q, f"{s['id']}.mp4")):
            raise StageError(f"{s['id']}: encoded shot missing")
