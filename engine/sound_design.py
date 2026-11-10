"""
Hand-placed sound design for a film whose json has a "sound" list: real CC0 recordings (BigSoundBank, in
assets/cc0/sfx/bigsoundbank/) laid per beat, so what you hear is what the shot shows.

Each entry is one layer:
    {"file": "rowing-slowly-s1514", "from": "floc", "to": "floc", "db": -12, "lp": 6000, "at": 0.0, "hit": false}

  from/to  the first and last beat it plays under (one continuous take across them, never restarted on a cut)
  db       level against the narration's speaking level (0 = as loud as the voice)
  lp       optional low-pass in Hz: takes the hiss off, and muffles water heard through a pipe or a wall
  at       start offset into the first beat, as a fraction of that beat
  hit      a one-shot: the recording's first loud transient is placed at `at` (no looping)

Beds fade in and out over FADE seconds, centred on the cut, so neighbouring beats crossfade instead of
starting hard: a burst of noise on every cut is what read as a whoosh in the first tap-water mix.
"""
from __future__ import annotations

import os
import subprocess

import numpy as np

from config.paths import PROJECT_ROOT, get_ffmpeg

LIB = os.path.join(PROJECT_ROOT, "assets", "cc0", "sfx", "bigsoundbank")
FADE = 0.5                      # crossfade across a cut (s)
SKIP = 1.0                      # skip a recording's first second (handling noise, fade-ins)


def _load(name: str, sr: int, lp: float | None) -> np.ndarray:
    path = name if os.path.isabs(name) else os.path.join(LIB, f"{name}.mp3")
    af = ["-af", f"lowpass=f={lp},lowpass=f={lp}"] if lp else []
    raw = subprocess.run([get_ffmpeg(), "-v", "error", "-i", path, *af, "-f", "f32le", "-ac", "1", "-ar", str(sr),
                          "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def _level(x: np.ndarray, sr: int) -> float:
    """The recording's level while it sounds: the 80th percentile of half-second RMS windows, so sparse
    sounds (drops, a meter's ticks) are matched on their sound and not on the silence between."""
    w = sr // 2
    bars = [float(np.sqrt(np.mean(x[i:i + w] ** 2))) for i in range(0, max(1, len(x) - w), w)]
    return float(np.percentile(bars, 80)) if bars else 0.0


def _bed(x: np.ndarray, n: int, sr: int) -> np.ndarray:
    """n samples of a recording from SKIP in, looped with a 1 s crossfade when it is too short."""
    start = min(int(SKIP * sr), max(0, len(x) - n))
    x = x[start:]
    if len(x) >= n:
        return x[:n].copy()
    xf = min(sr, len(x) // 4)
    out = x.copy()
    while len(out) < n:
        ramp = np.linspace(0, 1, xf)
        out[-xf:] = out[-xf:] * (1 - ramp) + x[:xf] * ramp
        out = np.concatenate([out, x[xf:]])
    return out[:n]


def _hit(x: np.ndarray, sr: int, seconds: float = 2.5) -> np.ndarray:
    """A one-shot cut from its first loud transient (50 ms before it), with a short fade-out."""
    env = np.abs(x)
    i = int(np.argmax(env > 0.5 * env.max()))
    y = x[max(0, i - int(0.05 * sr)):][: int(seconds * sr)].copy()
    k = min(len(y), int(0.3 * sr))
    y[-k:] *= np.linspace(1, 0, k)
    return y


def render(film: dict, times: list, total: float, ref: float, sr: int) -> np.ndarray:
    """The film's sound layers as one mono track of `total` seconds. times: [(t0, t1)] per beat."""
    ids = [b["id"] for b in film["beats"]]
    n = int(round(total * sr))
    out = np.zeros(n, dtype=np.float32)
    for layer in film.get("sound", []):
        a, b = ids.index(layer["from"]), ids.index(layer.get("to", layer["from"]))
        t0, t1 = times[a][0] + layer.get("at", 0.0) * (times[a][1] - times[a][0]), times[b][1]
        x = _load(layer["file"], sr, layer.get("lp"))
        x = x * (ref / max(1e-6, _level(x, sr))) * 10 ** (layer.get("db", -14) / 20)
        if layer.get("hit"):
            y = _hit(x, sr, layer.get("len", 2.5))
            i = int(t0 * sr)
        else:
            # centred on the cuts: fade in from FADE/2 before the beat, out until FADE/2 after it
            first, last = a == 0 and layer.get("at", 0) == 0, b == len(ids) - 1
            s0 = max(0.0, t0 - (0 if first else FADE / 2))
            s1 = min(total, t1 + (0 if last else FADE / 2))
            i = int(s0 * sr)
            y = _bed(x, int((s1 - s0) * sr), sr)
            k_in = min(len(y) // 2, int((0.05 if first else FADE) * sr))
            k_out = min(len(y) // 2, int((1.5 if last else FADE) * sr))
            y[:k_in] *= np.linspace(0, 1, k_in)
            y[len(y) - k_out:] *= np.linspace(1, 0, k_out)
        j = min(n, i + len(y))
        out[i:j] += y[: j - i]
    return out
