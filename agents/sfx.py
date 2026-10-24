"""
Synthesised sound effects, placed on the exact frames the animation recorded
(engine/events.py): footsteps, hammer taps, engine rumble, scoops, dirt dumps,
rebar clinks, tile clacks, concrete spray, pouring water, pump hum, clock
ticks, the splash — plus a soft birdsong ambience under the whole film.
All sounds are generated here, so there is nothing to license.
"""
import wave

import numpy as np

SR = 44100
_rng = np.random.default_rng(7)


def _t(seconds):
    return np.arange(int(SR * seconds)) / SR


def _band(x, lo=None, hi=None):
    """Zero-phase FFT band-pass with soft edges (fast, no scipy needed)."""
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    mask = np.ones_like(f)
    if lo:
        mask *= 1 / (1 + (lo / np.maximum(f, 1e-3)) ** 4)
    if hi:
        mask *= 1 / (1 + (f / hi) ** 4)
    return np.fft.irfft(spec * mask, n=len(x))


def _env(n, attack=0.005, decay=0.1):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(attack, 1e-4)) * np.exp(-t / max(decay, 1e-4))


def _norm(x, peak=1.0):
    m = np.abs(x).max()
    return x / m * peak if m > 0 else x


def _noise(seconds):
    return _rng.standard_normal(int(SR * seconds))


# ------------------- ONE-SHOTS -------------------

def step():
    x = _band(_noise(0.09), 60, 900) * _env(int(SR * 0.09), 0.003, 0.025)
    return _norm(x, 0.35)


def hammer():
    t = _t(0.18)
    tone = np.sin(2 * np.pi * 1850 * t) * 0.5 + np.sin(2 * np.pi * 620 * t)
    x = (tone + _band(_noise(0.18), 1500, 8000) * 0.6) * _env(len(t), 0.001, 0.035)
    return _norm(x, 0.7)


def scoop():
    x = _band(_noise(0.4), 80, 1500) * _env(int(SR * 0.4), 0.03, 0.12)
    grit = _band(_noise(0.4), 2000, 6000) * _env(int(SR * 0.4), 0.02, 0.06) * 0.3
    return _norm(x + grit, 0.6)


def dump():
    n = int(SR * 0.7)
    x = _band(_noise(0.7), 50, 700) * _env(n, 0.04, 0.25)
    return _norm(x, 0.6)


def clink():
    t = _t(0.35)
    x = sum(np.sin(2 * np.pi * f * t) * a for f, a in ((2400, 1.0), (3710, 0.6), (5130, 0.4), (6900, 0.2)))
    return _norm(x * _env(len(t), 0.001, 0.07), 0.35)


def tile():
    t = _t(0.12)
    x = (np.sin(2 * np.pi * 2600 * t) + 0.7 * np.sin(2 * np.pi * 950 * t)) * _env(len(t), 0.001, 0.02)
    return _norm(x, 0.4)


def pop():
    t = _t(0.09)
    freq = np.linspace(1100, 450, len(t))
    return np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 38) * 0.35


def tick():
    t = _t(0.04)
    return _norm(np.sin(2 * np.pi * 3200 * t) * _env(len(t), 0.0005, 0.006), 0.3)


def splash():
    n = int(SR * 1.1)
    body = _band(_noise(1.1), 150, 4000) * _env(n, 0.005, 0.28)
    hiss = _band(_noise(1.1), 3000, 12000) * _env(n, 0.01, 0.4) * 0.4
    plop = np.sin(2 * np.pi * np.cumsum(np.linspace(300, 90, n)) / SR) * _env(n, 0.002, 0.12)
    return _norm(body + hiss + plop * 0.8, 0.9)


# ------------------- LOOPS (with duration) -------------------

def _loop_env(n, fade=0.25):
    e = np.ones(n)
    k = min(int(SR * fade), n // 2)
    if k:
        e[:k] = np.linspace(0, 1, k)
        e[-k:] = np.linspace(1, 0, k)
    return e


def engine(seconds, rev=False):
    t = _t(seconds)
    f0 = 48 + (np.linspace(0, 22, len(t)) if rev else 0)
    phase = 2 * np.pi * np.cumsum(f0 * np.ones(len(t))) / SR
    tone = sum(np.sin(phase * h) / h for h in range(1, 7))
    putter = 0.6 + 0.4 * np.sin(2 * np.pi * 9 * t)
    rumble = _band(_noise(seconds), 30, 400)
    x = (tone * putter + rumble * 0.8) * _loop_env(len(t), 0.4)
    return _norm(x, 0.45)


def spray(seconds):
    t = _t(seconds)
    flutter = 0.75 + 0.25 * np.sin(2 * np.pi * 13 * t + np.sin(2 * np.pi * 2 * t))
    x = _band(_noise(seconds), 1500, 9000) * flutter * _loop_env(len(t), 0.1)
    return _norm(x, 0.35)


def pour(seconds):
    n = int(SR * seconds)
    x = _band(_noise(seconds), 300, 3500) * 0.6
    bubbles = np.zeros(n)
    for _ in range(int(seconds * 18)):
        i = _rng.integers(0, max(1, n - 3000))
        k = np.arange(2500)
        f = _rng.uniform(500, 1400)
        bubbles[i:i + 2500] += np.sin(2 * np.pi * np.cumsum(np.linspace(f, f * 1.6, 2500)) / SR) * np.exp(-k / 400)
    return _norm((x + bubbles * 0.5) * _loop_env(n, 0.2), 0.4)


def pump(seconds):
    t = _t(seconds)
    x = sum(np.sin(2 * np.pi * 120 * h * t) / h ** 1.5 for h in range(1, 5)) + _band(_noise(seconds), 200, 2000) * 0.2
    return _norm(x * _loop_env(len(t), 0.5), 0.15)


def ticks(seconds, interval=0.12):
    n = int(SR * seconds)
    out = np.zeros(n)
    one = tick()
    for i in range(0, n - len(one), int(SR * interval)):
        out[i:i + len(one)] += one
    return out


def birds(seconds):
    n = int(SR * seconds)
    out = np.zeros(n)
    t0 = 0.6
    while t0 < seconds - 0.5:
        for k in range(_rng.integers(2, 5)):        # a little phrase of chirps
            dur = _rng.uniform(0.05, 0.12)
            t = _t(dur)
            f = _rng.uniform(2600, 4800)
            sweep = f + 900 * np.sin(np.pi * t / dur) * _rng.choice([-1, 1])
            chirp = np.sin(2 * np.pi * np.cumsum(sweep) / SR) * np.sin(np.pi * t / dur) ** 2
            i = int(SR * (t0 + k * _rng.uniform(0.1, 0.16)))
            out[i:i + len(chirp)] += chirp[: max(0, min(len(chirp), n - i))]
        t0 += _rng.uniform(1.2, 3.0)
    return _norm(out, 0.12)


def scratch():
    """Record scratch: a quick back-and-forth pitch rip (the freeze-frame gag)."""
    n = int(SR * 0.42)
    t = np.arange(n) / SR
    rate = 1 + 0.9 * np.sin(2 * np.pi * 5.5 * t)                  # platter jerked back and forth
    grit = _band(_noise(0.42), 300, 5000)
    tone = np.sin(2 * np.pi * np.cumsum(220 + 900 * np.abs(np.sin(2 * np.pi * 5.5 * t))) / SR)
    x = (grit * 0.7 + tone * 0.6) * rate * _env(n, 0.004, 0.25)
    return _norm(x, 0.8)


def boing():
    """Cartoon spring for little hops."""
    n = int(SR * 0.35)
    t = np.arange(n) / SR
    f = 180 + 220 * (1 - np.exp(-t / 0.05)) + 60 * np.sin(2 * np.pi * 14 * t)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.003, 0.14)
    return _norm(x, 0.5)


def whoosh():
    """Body flying through the air."""
    n = int(SR * 0.5)
    t = np.arange(n) / SR
    shape = np.sin(np.pi * t / 0.5) ** 2
    x = _band(_noise(0.5), 400, 3000) * shape
    return _norm(x, 0.45)


def rewind(seconds):
    """VHS-style rewind: a fast warbling, rising whirr with tape hiss."""
    t = _t(seconds)
    f = 300 + 1400 * (t / max(seconds, 1e-3)) ** 0.7 + 120 * np.sin(2 * np.pi * 23 * t)
    whirr = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.5 * np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR)
    hiss = _band(_noise(seconds), 2000, 9000) * 0.5
    chops = 0.7 + 0.3 * np.sign(np.sin(2 * np.pi * 17 * t))
    return _norm((whirr * 0.6 + hiss) * chops * _loop_env(len(t), 0.05), 0.5)


def snore(seconds):
    """Slow cartoon snores (in-breath rattle, out-breath whistle)."""
    n = int(SR * seconds)
    out = np.zeros(n)
    period = 1.6
    for k in range(int(seconds / period)):
        i = int(SR * k * period)
        m = int(SR * 0.7)
        tt = np.arange(m) / SR
        rattle = _band(_noise(0.7), 60, 500) * (0.6 + 0.4 * np.sin(2 * np.pi * 30 * tt)) * np.sin(np.pi * tt / 0.7)
        w = int(SR * 0.5)
        tw = np.arange(w) / SR
        whistle = np.sin(2 * np.pi * np.cumsum(np.linspace(900, 600, w)) / SR) * np.sin(np.pi * tw / 0.5) * 0.3
        out[i:i + m] += rattle[: max(0, min(m, n - i))]
        j = i + m
        out[j:j + w] += whistle[: max(0, min(w, n - j))]
    return _norm(out, 0.35)


ONE_SHOTS = {"step": step, "hammer": hammer, "scoop": scoop, "dump": dump, "clink": clink,
             "tile": tile, "pop": pop, "splash": splash, "scratch": scratch, "boing": boing,
             "whoosh": whoosh}
LOOPS = {"engine": engine, "engine_rev": lambda s: engine(s, rev=True), "spray": spray, "pour": pour,
         "pump": pump, "tick": ticks, "rewind": rewind, "snore": snore}


# Relative loudness of each event kind in the effects mix (library samples are loudness-matched).
MIX = {"step": 0.35, "hammer": 0.75, "boing": 0.55, "whoosh": 0.55, "kids_cheer": 1.0, "snore": 0.8,
       "scratch": 1.0, "rewind": 0.9, "pop": 0.4, "splash": 1.0, "engine": 0.55, "engine_rev": 0.6,
       "scoop": 0.8, "dump": 0.8, "clink": 0.5, "tile": 0.5, "spray": 0.5, "pour": 0.55, "pump": 0.3,
       "crack": 1.0, "rain": 0.6, "thunder": 0.8, "plane_start": 0.9, "plane_engine": 0.7,
       "plane_flyby": 1.0, "crash_tree": 1.1, "hay_thud": 0.9, "flop": 1.0, "roll": 0.4, "pant": 0.8,
       "tick": 0.6}
VARY = {"step", "hammer", "clink", "tile", "pop", "scoop", "dump", "boing", "whoosh", "splash"}


def render_events(events: list, fps: int, total_seconds: float, path: str, ambience: bool = True) -> str:
    """Mix every event into a mono 16-bit WAV of the film's length. Each event uses the realistic
    library sound when one exists (agents/sfx_library.py), else the synthesized fallback."""
    from agents import sfx_library as lib
    n = int(SR * (total_seconds + 1.5))
    track = np.zeros(n)

    def add(sound, at_sec, gain):
        i = max(0, int(at_sec * SR))
        j = min(n, i + len(sound))
        if j > i:
            track[i:j] += sound[: j - i] * gain

    for k, ev in enumerate(events):
        kind = ev["kind"]
        at = (ev["frame"] - 1) / fps
        dur = ev.get("duration", 0) / fps
        gain = ev.get("gain", 1.0) * MIX.get(kind, 1.0)
        sound = None
        if lib.load(kind) is not None:
            if lib.is_loop(kind):
                sound = lib.tiled(kind, max(dur, 1.0))
            else:
                sound = lib.varied(kind, seed=k) if kind in VARY else lib.load(kind)
        elif kind in ONE_SHOTS:
            sound, gain = ONE_SHOTS[kind](), ev.get("gain", 1.0)
        elif kind in LOOPS and dur > 0:
            sound, gain = LOOPS[kind](dur), ev.get("gain", 1.0)
        if sound is not None:
            add(sound, at, gain)
    if ambience:
        bed = lib.tiled("birds", total_seconds) if lib.load("birds") is not None else None
        if bed is not None:
            add(bed, 0, 0.35)
            wind = lib.tiled("wind", total_seconds)
            if wind is not None:
                add(wind, 0, 0.25)
        else:
            add(birds(total_seconds), 0, 1.0)
    peak = np.abs(track).max()
    if peak > 0.95:
        track *= 0.95 / peak
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(track, -1, 1) * 32767).astype(np.int16).tobytes())
    return path


# ------------------- MUSIC BED -------------------

def music(seconds: float, bpm: float = 100.0, seed: int = 4) -> np.ndarray:
    """Light, upbeat explainer bed (generated, so nothing to license): warm chord pads on a
    I–V–vi–IV loop, a plucked arpeggio, a soft kick and shaker. Meant to sit ducked under a voice."""
    rng = np.random.default_rng(seed)
    n = int(SR * seconds)
    out = np.zeros(n)
    beat = 60.0 / bpm
    bar = beat * 4
    root = 261.63                                    # C4
    prog = [(0, 4, 7), (7, 11, 14), (9, 12, 16), (5, 9, 12)]   # C  G  Am  F  (semitones)

    def tone(freq, dur, kind="pad"):
        m = int(SR * dur)
        t = np.arange(m) / SR
        if kind == "pad":
            x = sum(np.sin(2 * np.pi * freq * d * t + rng.uniform(0, 6)) for d in (0.997, 1.0, 1.004))
            x += 0.3 * np.sin(2 * np.pi * freq * 2 * t)
            env = np.minimum(1, t / 0.35) * np.minimum(1, (dur - t) / 0.45)
            return x * env / 3.3
        x = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * freq * 2 * t)
        return x * np.exp(-t / 0.18) * np.minimum(1, t / 0.004)

    def put(sig, at):
        i = int(SR * at)
        j = min(n, i + len(sig))
        if j > i:
            out[i:j] += sig[: j - i]

    t0, k = 0.0, 0
    while t0 < seconds:
        chord = prog[k % len(prog)]
        for st in chord:
            put(tone(root / 2 * 2 ** (st / 12), bar + 0.4, "pad") * 0.22, t0)
        for s8 in range(8):                          # eighth-note arpeggio
            st = chord[[0, 1, 2, 1, 2, 0, 1, 2][s8]] + (12 if s8 in (2, 4) else 0)
            put(tone(root * 2 ** (st / 12), 0.5, "pluck") * 0.16, t0 + s8 * beat / 2)
        for b in range(4):                           # kick on 1 and 3, shaker on the offbeats
            if b % 2 == 0:
                m = int(SR * 0.25)
                tt = np.arange(m) / SR
                put(np.sin(2 * np.pi * np.cumsum(np.linspace(110, 45, m)) / SR) * np.exp(-tt / 0.09) * 0.5,
                    t0 + b * beat)
            put(_band(_noise(0.06), 5000, 12000) * _env(int(SR * 0.06), 0.002, 0.02) * 0.12, t0 + b * beat + beat / 2)
        t0 += bar
        k += 1
    return _norm(out * _loop_env(n, 1.0), 0.7)
