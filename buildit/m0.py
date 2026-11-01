"""Milestone 0 style test, after the Blender render: encode, mix, compose, render the MP4 (python -m buildit.m0)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

from config.paths import get_ffmpeg

from . import compose, sound
from .assets.fetch import music
from .config import RUNS

M0 = os.path.join(RUNS, "m0")
DURATION = 10.1


def word_t(words, text):
    return next(w["start"] for w in words if w["text"].strip(".,!?").lower() == text)


def main(quality="final"):
    t = time.time()
    frames = os.path.join(M0, quality)
    anchors = os.path.join(frames, "anchors.json")
    shot = os.path.join(M0, "s01.mp4")
    subprocess.run([get_ffmpeg(), "-v", "error", "-y", "-framerate", "30", "-i", os.path.join(frames, "f_%04d.png"),
                    "-vf", "scale=1080:1920:flags=lanczos", "-c:v", "libx264", "-preset", "medium", "-crf", "15",
                    "-g", "30", "-pix_fmt", "yuv420p", shot], check=True)
    words = json.load(open(os.path.join(M0, "words_raw.json"), encoding="utf-8"))
    t_pump, t_push, t_valve, t_cant = (word_t(words, w) for w in ("pump", "push", "valve", "can't"))
    strokes = [t_push + 0.02 + k for k in (0, 0.93, 1.83, 2.73, 3.58)]
    cues = [(t_pump - 0.02, "land"), (t_valve - 0.03, "pop"), (t_cant, "ratchet")] + [(s, "puff") for s in strokes]
    mix = os.path.join(M0, "mix.wav")
    report = sound.mix(os.path.join(M0, "voice.wav"), DURATION, music()["file"], cues, mix)
    labels = [{"scene": "s01", "text": "Air in", "variant": "air", "anchor": "tank_air",
               "t0": word_t(words, "air"), "t1": word_t(words, "add") - 0.1, "line": True}]
    hf_dir = os.path.join(M0, "hf")
    compose.project(hf_dir, [{"id": "s01", "video": shot, "start": 0.0, "end": DURATION, "anchors": anchors}],
                    words, labels, mix, DURATION, "Build-It M0 style test")
    from cutaway import hf
    lint = hf.run(["lint"], cwd=hf_dir, check=False, timeout=600)
    print((lint.stdout or "")[-1500:])
    out = os.path.join(M0, f"m0_{quality}.mp4")
    r = hf.run(["render", "-o", out, "--quality", "looks", "--keyframe-interval", "1"], cwd=hf_dir, check=False, timeout=1800)
    print((r.stdout or "")[-800:], (r.stderr or "")[-800:])
    print(json.dumps({"loudness": report, "seconds": round(time.time() - t, 1), "out": out}))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "final")
