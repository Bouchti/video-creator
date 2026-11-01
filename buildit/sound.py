"""
The Build-It mix: the narration on top, light upbeat music levelled against it and ducked under it, and REAL
recorded sound effects tied to what the picture does (a metal clank as a part clicks into the machine, a click
as a pipe connects, a motor hum for as long as the compressor runs, a fan whirr, a gas hiss, a spray), mastered
to -14 LUFS / -1 dBTP. Sounds come from the project's own library (assets/sfx, agents/sfx_library) by exact
name, never by a loose keyword search (that put a door knock on every landing part). Reuses the cutaway
pipeline's audio helpers (by import).

    mix(voice_wav, duration, music_mp3, [(t, "clank", None), (t, "hum", 6.5), ...], out_wav) -> loudness report
"""
from __future__ import annotations

import logging
import os

import numpy as np

from agents import sfx_library
from cutaway.stages.sound import (SR, db, envelope, load, loudnorm, music_bed, place, rms, save,  # noqa: F401
                                  speech_rms, varied)

log = logging.getLogger("pipeline")
MUSIC_DB, MUSIC_DUCK_DB = -24.0, -8.0         # light under the voice; a little lift in the pauses
# cue -> (library names, first found wins; gain dB vs the voice; max seconds of a one-shot; loop)
CUES = {
    "clank": (["steel_clank", "metal clang"], -11, 0.9, False),       # a big part clicks into the machine
    "clank_small": (["rivet_pop", "clink"], -12, 0.6, False),         # a small part clicks in
    "click": (["switch", "rivet_pop"], -13, 0.4, False),              # a pipe / wire connects
    "whoosh": (["whoosh"], -15, 0.9, False),                          # something flies in / out
    "pop": (["pop"], -13, 0.5, False),                                # a prop pops up
    "thud": (["tile", "steel_clank"], -15, 0.5, False),               # a prop lands on the floor
    "hiss": (["steam_hiss"], -22, 1.4, False),                        # gas starts to flow
    "spray": (["spray"], -19, 2.2, True),                             # a spray jet, while it sprays
    "hum": (["hum", "pump"], -28, 60.0, True),                        # a compressor / pump running
    "whirr": (["whirring"], -29, 60.0, True),                         # a fan / motor spinning
    "turbine": (["turbine"], -28, 60.0, True),
    "boil": (["boil", "bubbles"], -21, 20.0, True),
    "bubbles": (["bubbles"], -20, 2.0, False),
    "spark": (["weld"], -16, 0.6, False),
    "bang": (["metal crash bang", "metal crash"], -10, 1.4, False),
    "rattle": (["rattle"], -20, 0.5, False),
    "power_up": (["power_up"], -12, 2.5, False),                      # the finished machine starts
    "ding": (["fanfare", "pop"], -16, 1.2, False),
}
_CLIPS: dict = {}


def clip(cue: str) -> np.ndarray | None:
    """The cue's sound at SR, loudness-matched (the first library name that exists)."""
    if cue not in _CLIPS:
        x = None
        for name in CUES.get(cue, ([cue], 0, 1, False))[0]:
            try:
                path = sfx_library._source(name)
            except Exception as exc:              # noqa: BLE001 - a missing sound never stops a video
                log.warning("[buildit] sfx %s: %s", name, exc)
                path = None
            if path and os.path.exists(path):
                x = load(path)
                if len(x):
                    break
        if x is not None and len(x):
            x = x / max(1e-6, rms(x[np.abs(x) > 1e-4]) if np.any(np.abs(x) > 1e-4) else 1.0) * 0.12
        _CLIPS[cue] = x if x is not None and len(x) else None
        if _CLIPS[cue] is None:
            log.warning("[buildit] no sound for cue '%s'", cue)
    return _CLIPS[cue]


def _tile(x: np.ndarray, seconds: float, fade: float = 0.3) -> np.ndarray:
    n = max(1, int(SR * seconds))
    xf = min(int(SR * 0.35), len(x) // 3)
    out = np.zeros(n + len(x), dtype=np.float32)
    pos = 0
    ramp = np.linspace(0, 1, xf, dtype=np.float32) if xf else None
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


def mix(voice_wav: str, duration: float, music_mp3: str | None, cues: list[tuple], out_wav: str) -> dict:
    """cues: (t, cue) one-shots or (t, cue, seconds) loops / long sounds."""
    n = int(duration * SR)
    voice = load(voice_wav)
    voice = np.pad(voice, (0, max(0, n - len(voice))))[:n]
    env = envelope(voice)
    ref = speech_rms(voice, env)
    music = 0.0
    if music_mp3:
        import cutaway.stages.sound as cs
        saved = cs.MUSIC_DB, cs.MUSIC_DUCK_DB
        cs.MUSIC_DB, cs.MUSIC_DUCK_DB = MUSIC_DB, MUSIC_DUCK_DB
        try:
            music = music_bed(music_mp3, n, env, ref)
        finally:
            cs.MUSIC_DB, cs.MUSIC_DUCK_DB = saved
    fx = np.zeros(n, dtype=np.float32)
    beds = np.zeros(n, dtype=np.float32)
    for k, c in enumerate(sorted(cues, key=lambda c: c[0])):
        t, cue = c[0], c[1]
        secs = c[2] if len(c) > 2 else None
        x = clip(cue)
        if x is None:
            continue
        names, gain, keep, loop = CUES.get(cue, ([cue], -14, 1.0, False))
        g = db(gain) * ref / 0.12
        if loop:
            span = min(keep, secs or keep)
            y = _tile(x, span) * g
            a = int(max(0.0, t) * SR)
            b = min(n, a + len(y))
            beds[a:b] += y[:b - a]
        else:
            y = x[:int(min(keep, secs or keep) * SR)].copy()
            fade = min(int(0.06 * SR), max(1, len(y) // 3))
            y[-fade:] *= np.linspace(1, 0, fade)
            place(fx, varied(y, k), t, g)
    beds *= (1.0 - 0.45 * np.clip(env, 0, 1))                 # running machines sit under the voice
    total = voice + music + fx + beds
    stereo = np.stack([total, total], axis=1)
    raw = out_wav[:-4] + "_raw.wav"
    save(raw, stereo)
    report = loudnorm(raw, out_wav)
    os.remove(raw)
    return report
