"""
Realistic sound-effect library, generated ONCE with ElevenLabs' text-to-sound-effects API and
cached in assets/sfx/ (then reused by every video, so it costs credits only the first time).

Each entry: name → (prompt, seconds or None for auto, loop?). One-shots are placed on the frame
an animation event happens; loops are tiled with crossfades to any length. sfx.render_events()
uses a library sound when one exists for an event kind and falls back to the synthesized one.

    python -m agents.sfx_library          # generate whatever is missing
"""
import logging
import os
import subprocess

import numpy as np
import requests

from config.paths import PROJECT_ROOT

log = logging.getLogger("pipeline")
SR = 44100
LIB_DIR = os.path.join(PROJECT_ROOT, "assets", "sfx")

# name: (prompt, duration seconds (None = let the model decide), loop)
LIBRARY = {
    # ---- characters / comedy ----
    "step": ("a single soft footstep on grass", 0.5, False),
    "hammer": ("a hammer hitting a nail into a wooden plank, one sharp hit", 0.8, False),
    "boing": ("cartoon spring boing sound effect", 0.9, False),
    "whoosh": ("short quick cartoon swoosh of something jumping", 0.6, False),
    "kids_cheer": ("two young children cheering and laughing outdoors, yay", 3.0, False),
    "snore": ("cartoon man snoring loudly, two snores", 3.5, False),
    "scratch": ("vinyl record scratch sound effect", 1.0, False),
    "rewind": ("VHS tape rewinding fast, whirring", 3.0, True),
    "pop": ("soft bubbly UI pop", 0.4, False),
    "splash": ("person doing a cannonball jump into a swimming pool, big splash", 2.0, False),
    # ---- construction (pool) ----
    "engine": ("small excavator diesel engine running steadily, outdoors", 6.0, True),
    "engine_rev": ("small excavator diesel engine revving and tracks moving", 4.0, True),
    "scoop": ("excavator bucket digging into dirt and soil", 1.5, False),
    "dump": ("excavator dumping a bucket of dirt onto a pile", 1.5, False),
    "clink": ("steel rebar bars clanking together", 0.8, False),
    "tile": ("ceramic tile placed on a wall, light clack", 0.5, False),
    "spray": ("concrete being sprayed from a high pressure hose, hissing", 5.0, True),
    "pour": ("water pouring from a garden hose into a pool", 6.0, True),
    "pump": ("swimming pool pump motor humming", 5.0, True),
    "crack": ("concrete wall cracking loudly", 1.5, False),
    "rain": ("heavy rain falling on grass and a garden", 8.0, True),
    "thunder": ("distant thunder rumble", 3.0, False),
    # ---- plane ----
    "plane_start": ("small propeller airplane engine starting, sputtering then running", 4.0, False),
    "plane_engine": ("small propeller airplane engine running steadily, close", 6.0, True),
    "plane_flyby": ("small propeller airplane flying past close, doppler", 5.0, False),
    "crash_tree": ("small wooden airplane crashing into a big tree, branches snapping, leaves rustling", 2.5, False),
    "hay_thud": ("wooden cart rolling into hay bales, soft thud", 1.2, False),
    "flop": ("light wooden airplane flopping onto grass, clattering thud", 1.5, False),
    "roll": ("wooden wheels rolling over a grassy dirt field", 4.0, True),
    "pant": ("man panting out of breath, comedic", 2.0, False),
    # ---- ambience ----
    "birds": ("countryside birds chirping, peaceful daytime ambience", 10.0, True),
    "wind": ("gentle wind over a grassy field", 8.0, True),
}


def path(name):
    return os.path.join(LIB_DIR, f"{name}.mp3")


def _keys():
    from agents.editor_hailuo import _elevenlabs_keys
    return _elevenlabs_keys()


def generate(name, force=False):
    """Generate one library sound with ElevenLabs (rotating through the configured keys)."""
    prompt, secs, loop = LIBRARY[name]
    out = path(name)
    if os.path.exists(out) and not force:
        return out
    os.makedirs(LIB_DIR, exist_ok=True)
    body = {"text": prompt, "prompt_influence": 0.5}
    if secs:
        body["duration_seconds"] = max(0.5, min(22.0, secs))
    errors = []
    for slot, key in _keys():
        r = requests.post("https://api.elevenlabs.io/v1/sound-generation", headers={"xi-api-key": key},
                          json=body, timeout=120)
        if r.status_code == 200 and r.content:
            with open(out, "wb") as f:
                f.write(r.content)
            log.info(f"  sfx library: generated '{name}' ({slot})")
            return out
        errors.append(f"{slot}: {r.status_code}")
    raise RuntimeError(f"could not generate sound '{name}': {errors}")


def ensure(names=None):
    """Generate every missing library sound (or just `names`). Failures fall back to synthesis."""
    for name in names or LIBRARY:
        if not os.path.exists(path(name)):
            try:
                generate(name)
            except Exception as e:                          # never block a render on a sound
                log.warning(f"  sfx library: {e}")


_cache = {}


def load(name):
    """Mono float32 samples at SR, loudness-normalised, or None if not in the library."""
    if name in _cache:
        return _cache[name]
    p = path(name)
    if name not in LIBRARY or not os.path.exists(p):
        return None
    from agents.editor_hailuo import FFMPEG
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", p, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    if len(x) == 0:
        return None
    x = x / max(1e-4, float(np.sqrt(np.mean(x ** 2)))) * 0.12        # same loudness for every sample
    peak = float(np.abs(x).max())
    if peak > 0.98:
        x *= 0.98 / peak
    _cache[name] = x
    return x


def is_loop(name):
    return name in LIBRARY and LIBRARY[name][2]


def tiled(name, seconds, fade=0.35):
    """A loop sound stretched to `seconds` with seamless crossfades and soft in/out fades."""
    x = load(name)
    if x is None:
        return None
    n = int(SR * seconds)
    xf = min(int(SR * 0.4), len(x) // 3)
    out = np.zeros(n + len(x))
    pos, ramp = 0, np.linspace(0, 1, xf) if xf else None
    while pos < n:
        seg = x.copy()
        if xf and pos:
            seg[:xf] *= ramp
            out[pos:pos + xf] *= ramp[::-1]
        out[pos:pos + len(seg)] += seg
        pos += len(seg) - xf
    out = out[:n]
    k = min(int(SR * fade), n // 2)
    if k:
        out[:k] *= np.linspace(0, 1, k)
        out[-k:] *= np.linspace(1, 0, k)
    return out


def varied(name, seed=0):
    """A one-shot with a slight random pitch/speed change, so repeats (steps, hammer) don't sound cloned."""
    x = load(name)
    if x is None:
        return None
    rate = 1.0 + (((seed * 2654435761) % 1000) / 1000 - 0.5) * 0.12
    idx = np.arange(0, len(x) - 1, rate)
    return np.interp(idx, np.arange(len(x)), x).astype(np.float32)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ensure()
    print(f"{sum(os.path.exists(path(n)) for n in LIBRARY)}/{len(LIBRARY)} sounds in {LIB_DIR}")
