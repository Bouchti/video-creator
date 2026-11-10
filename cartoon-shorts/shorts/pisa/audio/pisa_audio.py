"""Sound for "The Tower That Was Saved by a War": an original score and synthesized effects, every event on its picture
frame (mirrored from src/videos/pisa/story.ts + cast.ts), mixed under the voice.

    python pisa_audio.py        (from this folder) -> mix.wav (48 kHz, exact film length), stems/, cues.md

Uses the skill's synthesis library (dsp.py, instruments.py, sfx_gen.py: no samples, no API). Mix rule of the skill:
voice unchanged, music +3 dB and effects -6 dB against the template balance; master -14 LUFS, true peak under -1 dBTP.
"""
import json, math, os, subprocess
import numpy as np
from dsp import SR, ns, tt, rng, lp, hp, bp, dbg, pan, place, fades, read_wav, write_wav, integrated, momentary_max, true_peak, make_ir, convolve_st, phase, modal
import instruments as I
import sfx_gen as G

HERE = os.path.dirname(os.path.abspath(__file__))
FPS, TOTAL = 30, 1962
DUR = TOTAL / FPS
N = ns(DUR)
fr = lambda f: f / FPS  # noqa: E731
F = I.m2f

# ---------------------------------------------------------------- picture timeline (story.ts)
SHOTS = {1: (0, 116), 2: (116, 261), 3: (261, 397), 4: (397, 488), 5: (488, 557), 6: (557, 616), 7: (616, 677), 8: (677, 816),
         9: (816, 888), 10: (888, 1026), 11: (1026, 1229), 12: (1229, 1401), 13: (1401, 1506), 14: (1506, 1586), 15: (1586, 1817),
         16: (1817, 1865), 17: (1865, TOTAL)}
XFADE = {6: 8, 7: 8, 8: 8, 12: 8, 13: 8, 14: 8, 15: 8, 17: 8}
CUTS = [60, 352, 370, 452, 741, 1008, 1165, 1192, 1314, 1380, 1666, 1762, 1905]  # hard cuts inside shots (camera keys)
FLASH = fr(112)
SINK, DROP, LEAVE, BANANA, FENCE, LAST_LEAD, SQUEEZE, FIRM = fr(352), fr(452), fr(466), fr(869), fr(1006), fr(1163), fr(1314), fr(1380)
TOPPLE0, LAND, DRILL_ON, SANK, OFF = fr(1540), fr(1578), fr(1664), fr(1762), fr(1836)


def smooth(x):
    u = min(1.0, max(0.0, x)); return u * u * (3 - 2 * u)


def kf(f, pts):
    if f <= pts[0][0]: return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if f <= x1: return y0 + (y1 - y0) * smooth((f - x0) / (x1 - x0))
    return pts[-1][1]


def crossings(fn, f0, f1, levels):
    """frames where fn(f) first reaches each level"""
    out, k = [], 0
    for f in range(f0, f1 + 1):
        while k < len(levels) and fn(f) >= levels[k]:
            out.append(f); k += 1
    return out


def hammer_strikes(t0, t1, per, off):
    """cast.ts hammer(): the strike frame is 11 f into each cycle of `per` s offset by `off`"""
    out, k = [], math.floor((t0 + off) / per)
    while True:
        tm = k * per - off + 11 / FPS
        if tm > t1: break
        if tm >= t0: out.append(tm)
        k += 1
    return out


# ---------------------------------------------------------------- cue list
class Cue:
    def __init__(self, t, name, desc, gen, db, p=0.0, send=0.1, lpf=None):
        self.t, self.name, self.desc, self.gen, self.db, self.p, self.send, self.lpf = t, name, desc, gen, db, p, send, lpf


def S(*xs):
    """sum signals of different lengths (mono or stereo), padded at the end"""
    xs = [np.asarray(x, float) for x in xs]
    st = any(x.ndim == 2 for x in xs)
    xs = [(np.stack([x, x]) if x.ndim == 1 else x) if st else x for x in xs]
    n = max(x.shape[-1] for x in xs)
    out = np.zeros((2, n)) if st else np.zeros(n)
    for x in xs: out[..., : x.shape[-1]] += x
    return out


def boing(r, f0=180, dur=0.55):
    t = tt(dur)
    f = f0 * (1 + 0.9 * np.exp(-t / 0.05)) * (1 + 0.06 * np.sin(2 * np.pi * 11 * t) * np.exp(-t / 0.3))
    return fades(np.sin(phase(f)) * np.exp(-t / 0.22), 0.002, 0.05)


def rumble(dur, r, f_lo=30, f_hi=160, att=0.05):
    n = ns(dur); t = np.arange(n) / SR
    x = lp(hp(r.standard_normal(n), f_lo, 2), f_hi, 2)
    env = np.clip(t / att, 0, 1) * np.exp(-t / (dur * 0.35))
    return fades(x * env, 0.002, 0.1)


def stone_thud(r, big=1.0):
    d = 0.8; t = tt(d)
    body = modal(d, [(55, 1.0, 0.18), (92, 0.7, 0.12), (160, 0.4, 0.06)], r)
    nz = bp(r.standard_normal(len(t)), 200, 3000, 1) * np.exp(-t / 0.03)
    grit = bp(r.standard_normal(len(t)), 1500, 7000, 1) * np.exp(-t / 0.12) * 0.25
    return fades((body * 1.2 + nz * 0.8 + grit) * big, 0.0, 0.1)


def motor(dur, r, f=48):
    n = ns(dur); t = np.arange(n) / SR
    saw = sum(np.sin(2 * np.pi * f * k * t + r.uniform(0, 6)) / k for k in range(1, 9))
    grind = bp(r.standard_normal(n), 900, 3200, 1) * (0.5 + 0.5 * np.sin(2 * np.pi * 7.5 * t)) * 0.4
    env = np.clip(t / 0.35, 0, 1)
    return fades((saw * 0.5 + grind) * env, 0.01, 0.2)


def shutter(r):
    d = 0.12; t = tt(d)
    a = hp(r.standard_normal(len(t)), 2500) * np.exp(-t / 0.004)
    b = np.zeros_like(a); k = ns(0.045); b[k:] = hp(r.standard_normal(len(t) - k), 2000) * np.exp(-t[: len(t) - k] / 0.004) * 0.7
    return a + b


def squelch(dur, r):
    return S(G.bubbles(dur, r, 9.0, 250, 1400, (0.01, 0.04)) * 0.7, lp(r.standard_normal(ns(dur)), 600) * np.exp(-tt(dur) / 0.25) * 0.4)


def cues():
    C = []
    add = C.append
    R = lambda s: rng(s)  # noqa: E731
    # ---- ambiences per place ----
    def amb(a, b, kind, db, seed):
        dur = fr(b) - fr(a)
        if kind == "day":
            gen = lambda: S(G.breeze(dur, R(seed), 0.8) * 0.8, G.bird_chirps(dur, R(seed + 1), 0.4))  # noqa: E731
        elif kind == "golden":
            gen = lambda: S(G.breeze(dur, R(seed), 0.6) * 0.7, G.crickets(dur, R(seed + 1), 3) * 0.6)  # noqa: E731
        elif kind == "river":
            gen = lambda: G.water_bed(dur, R(seed), 0.8, 0.6)  # noqa: E731
        else:
            gen = lambda: G.breeze(dur, R(seed), 1.6, 0.4, 1400)  # noqa: E731 (time-lapse wind)
        add(Cue(fr(a), f"amb_{kind}", f"{kind} ambience", lambda g=gen: (fades(g(), 0.3, 0.4), 0.0), db, send=0.0))
    for (a, b, k, s) in [(0, 112, "day", 1), (116, 557, "day", 2), (553, 620, "golden", 3), (612, 681, "wind", 4), (673, 1233, "day", 5),
                         (1225, 1405, "river", 6), (1397, 1510, "wind", 7), (1502, 1590, "golden", 8), (1582, 1869, "day", 9), (1861, TOTAL, "golden", 10)]:
        amb(a, b, k, -24 if k != "river" else -20, s)
    # ---- camera: whooshes on cuts, a swell into the white flash ----
    for i, f in enumerate([SHOTS[k][0] for k in SHOTS if k > 1] + CUTS):
        if f == SHOTS[2][0]: continue
        x = XFADE.get(next((k for k in SHOTS if SHOTS[k][0] == f), 0), 0)
        add(Cue(fr(f), "whoosh", f"cut / crossfade whoosh at frame {f}", lambda r=R(100 + i), x=x: (G.whoosh(0.7 if x else 0.5, r, 0.25 if x else 0.12, 320, 1900, 0.9, 0.2, 0.12), 0.25 if x else 0.12), -16, p=0.0, send=0.1))
    add(Cue(FLASH, "flash", "reverse swell into the white flash + soft whoomp", lambda: (S(G.whoosh(1.0, R(5), 0.85, 200, 2600, 1.0, 0.25, 0.2), np.pad(rumble(0.6, R(6)), (ns(0.85), 0))), 0.85), -8))
    # ---- 1173: hammers at the foot and on the rising top (shot 2), on the rim (shot 3, until the sinking), at the foot (shot 4) ----
    for i, off in enumerate([0, 0.31, 0.62, 0.93, 1.24, 1.55]):
        for tm in hammer_strikes(fr(116), fr(261), 0.9, off):
            add(Cue(tm, "chisel", "mason's mallet on marble", lambda r=R(int(tm * 977) + i): (G.hammer_hit(r, 0.6) , 0.0), -22 - 2 * (i % 3), p=-0.6 + 0.24 * i, send=0.15, lpf=6000))
    for i in range(5):
        for tm in hammer_strikes(fr(261), SINK - 0.05, 0.8, i * 0.23):
            add(Cue(tm, "chisel", "mallet on the rim", lambda r=R(int(tm * 991) + i): (G.hammer_hit(r, 0.7), 0.0), -18 - 1.5 * (i % 2), p=-0.5 + 0.25 * i, send=0.12))
    for i in range(3):
        for tm in hammer_strikes(fr(397), DROP - 0.1, 0.85, i * 0.3):
            add(Cue(tm, "chisel", "mallets at the foot", lambda r=R(int(tm * 953) + i): (G.hammer_hit(r, 0.5), 0.0), -22, p=-0.3 + 0.3 * i, send=0.12, lpf=7000))
    # ---- the sinking ----
    add(Cue(SINK, "sink", "the foot sinks: deep stone groan + crunch of soil + low rumble", lambda: (S(G.creak(1.2, R(11), 40, 70, scale=0.6) * 0.8, rumble(1.6, R(12)) * 1.4), 0.0), -6, send=0.2))
    add(Cue(SINK + 0.04, "thud", "settling thud", lambda: (stone_thud(R(13), 1.0), 0.0), -6, send=0.2))
    add(Cue(SINK + 0.1, "gasps", "masons gasp", lambda: (S(*[pan(G.whoa(R(14 + k)), -0.4 + 0.4 * k) for k in range(3)]), 0.0), -14, send=0.1))
    # ---- war: the column (boots every 0.5 s on cobbles), a war horn, cheers; the tools hit the ground ----
    add(Cue(fr(399), "horn", "war horn blast (two notes)", lambda: (S(I.brass(F(50), 0.5, 0.9, R(20), "horn"), np.pad(I.brass(F(57), 0.9, 1.0, R(21), "horn"), (ns(0.55), 0))), 0.0), -12, send=0.35))
    t = 13.5
    while t < fr(557):
        if fr(397) <= t:
            add(Cue(t, "boots", "column footfall on cobbles", lambda r=R(int(t * 100)), t=t: G.column_stomp(r, 0.9, int(t * 2) % 2, 24), -15 if t < fr(488) else -10, p=0.2, send=0.12, lpf=9000))
        t += 0.5
    for i in range(3):
        add(Cue(DROP + 0.3 + 0.05 * i, "tool", "a mallet / chisel clanks onto the paving", lambda r=R(30 + i): (S(G.clink(r, 2400 + 400 * i, 0.15), G.boot(r, 0.4) * 0.5), 0.0), -12, p=-0.3 + 0.3 * i))
    add(Cue(fr(492), "cheer", "the column cheers off to war", lambda: (S(*[pan(G.hurrah(R(40 + k), 110 + 25 * k, 1.0 + 0.05 * k), -0.7 + 0.35 * k) for k in range(5)]), 0.0), -12, send=0.3))
    # ---- "Unluckily": the camp: groans, an 'ow' ----
    for k, (tm, kind) in enumerate([(19.3, "ugh"), (19.75, "ow"), (20.1, "oh")]):
        add(Cue(tm, "oof", f"defeated soldier: {kind}", lambda r=R(50 + k), kind=kind: (G.oof(r, kind), 0.0), -14, p=-0.4 + 0.4 * k, send=0.15))
    # ---- the return: each new storey lands with a stone thunk ----
    for i, f in enumerate(crossings(lambda f: kf(f, [(743, 3), (799, 7)]), 743, 800, [3.5, 4.5, 5.5, 6.5])):
        add(Cue(fr(f), "storey", "a storey goes up: stone thunk + pop", lambda r=R(60 + i): (stone_thud(r, 0.7), 0.0), -12, send=0.2))
    add(Cue(BANANA, "boing", "the banana pops in: cartoon boing", lambda: (boing(R(70)), 0.0), -10))
    # ---- tipping year on year: creaks; the barrier clatters up ----
    for k, tm in enumerate([30.2, 31.3, 32.4]):
        add(Cue(tm, "creak", "the tower creaks as it leans further", lambda r=R(80 + k): (G.creak(0.9, r, 35, 60, scale=0.7), 0.0), -14, send=0.25))
    add(Cue(FENCE, "barrier", "barrier posts set down + tape stretched", lambda: (S(G.rattle(0.5, R(85), 25), G.clink(R(86), 1800, 0.2)), 0.0), -14))
    # ---- lead: each layer thunks down; the last ingot is the paperweight ----
    for i, f in enumerate(crossings(lambda f: kf(f, [(1050, 0), (1165, 1)]) * 60, 1050, 1166, [12 * k + 6 for k in range(5)])):
        add(Cue(fr(f), "lead", "a layer of lead ingots thunks down", lambda r=R(90 + i): (S(stone_thud(r, 0.8), G.clink(r, 900, 0.2) * 0.4), 0.0), -12, send=0.15))
    add(Cue(LAST_LEAD, "paperweight", "the last ingot: heavy thump + puff", lambda: (S(stone_thud(R(96), 1.4), rumble(0.6, R(97)) * 0.8), 0.0), -8))
    add(Cue(fr(1194), "creak_back", "a tiny creak back", lambda: (G.creak(0.6, R(98), 50, 80, scale=0.5), 0.0), -18))
    # ---- wet sand: squelch as the water squeezes out, then still ----
    add(Cue(SQUEEZE - 0.1, "squelch", "wet sand squelch under the feet, water oozing out", lambda: (squelch(2.0, R(110)), 0.0), -12))
    add(Cue(FIRM, "pat", "a firm little pat on the sand", lambda: (G.stroll_step(R(111), 0.2), 0.0), -16))
    # ---- the clay: droplets over a century ----
    for k in range(9):
        add(Cue(fr(1405) + k * 0.38, "drip", "water bead pops out of the clay", lambda r=R(120 + k): (G.bubbles(0.2, r, 12, 900, 2600, (0.006, 0.02)), 0.0), -22, p=-0.6 + 0.15 * k))
    # ---- what if: the topple (groan, air rush, the crash, debris) ----
    add(Cue(TOPPLE0, "groan", "the tower groans and starts to go", lambda: (S(G.creak(1.2, R(130), 30, 55, scale=0.5) * 1.2, rumble(1.3, R(131))), 0.0), -6, send=0.25))
    add(Cue(LAND, "air", "air rush of the falling tower", lambda: (G.whoosh(1.2, R(132), 1.05, 150, 1200, 1.0, 0.1, 0.25), 1.05), -6))
    add(Cue(LAND, "crash", "the crash: marble boom + crack + debris", lambda: (S(stone_thud(R(133), 2.0), G.wood_crack(R(134)) * 0.6, rumble(2.4, R(135), 25, 200, 0.02) * 2.0, G.rattle(1.6, R(136), 40, heavy=True) * 0.8), 0.0), 0, send=0.35))
    # ---- extraction: the drill motor, soil, the sinking back; the switch-off ----
    add(Cue(DRILL_ON, "drill", "drill rig motor + auger grind (until switched off)", lambda: (fades(motor(OFF - DRILL_ON + 0.25, R(140)), 0.3, 0.25), 0.0), -15, send=0.1))
    add(Cue(SANK, "sank", "the tower settles back: low groan + rumble", lambda: (S(G.creak(1.4, R(141), 40, 30, scale=0.6), rumble(1.6, R(142))), 0.0), -9, send=0.25))
    add(Cue(OFF, "switch", "the big switch: clunk, the motor winds down", lambda: (S(G.clink(R(143), 700, 0.25), G.boot(R(144), 1.0) * 0.6), 0.0), -10))
    # ---- today: tourists' chatter and camera shutters ----
    for (a, b) in [(0, 112), (1865, TOTAL)]:
        dur = fr(b) - fr(a)
        add(Cue(fr(a), "chatter", "visitors on the lawn: chatter", lambda r=R(150 + a), dur=dur: (fades(S(*[pan(lp(G.babble(dur, r, r.uniform(110, 230), r.uniform(1.0, 1.2), 4.2, 0.6), 3000, 1), r.uniform(-0.8, 0.8)) for _ in range(6)]), 0.3, 0.4), 0.0), -24, send=0.05))
        for k in range(4):
            tm = fr(a) + 0.5 + k * dur / 4.4
            add(Cue(tm, "shutter", "camera shutter", lambda r=R(160 + a + k): (shutter(r), 0.0), -20, p=-0.6 + 0.4 * k))
    return C


# ---------------------------------------------------------------- score (original): a tarantella-ish pluck theme in D
BEAT = 60 / 126  # 126 bpm
THEME = [  # (beat, length in beats, midi) 4 bars, D major / A7
    (0, .5, 74), (.5, .5, 76), (1, .5, 78), (1.5, .5, 79), (2, 1, 81), (3, .5, 78), (3.5, .5, 81),
    (4, .5, 83), (4.5, .5, 81), (5, .5, 79), (5.5, .5, 76), (6, 1, 78), (7, 1, 74),
    (8, .5, 76), (8.5, .5, 78), (9, .5, 79), (9.5, .5, 81), (10, 1, 83), (11, .5, 79), (11.5, .5, 76),
    (12, .5, 78), (12.5, .5, 76), (13, .5, 73), (13.5, .5, 76), (14, 2, 74),
]
CHORDS = [50, 50, 45, 50]  # bass roots per bar: D D A D


class Band:
    def __init__(self):
        self.tracks = {}
        self.cues = []

    def add(self, name, x, t, p=0.0, g=1.0):
        buf = self.tracks.setdefault(name, np.zeros((2, N)))
        place(buf, pan(np.asarray(x, float), p) if np.ndim(x) == 1 else x, t, g)


def theme(b, t0, bars=4, inst="pluck", tr=0, vel=0.7, end=None):
    r = rng(int(t0 * 100))
    for (bt, ln, m) in THEME:
        if bt >= bars * 4: continue
        tm = t0 + bt * BEAT
        if end is not None and tm >= end: break
        f = F(m + tr)
        if inst == "pluck": b.add("pluck", I.pluck(f, vel * r.uniform(0.85, 1.0), r, 0.5 + ln * BEAT), tm, 0.15)
        elif inst == "glock": b.add("glock", I.glock(f, vel * 0.8, r, 1.2), tm, -0.2)
        elif inst == "fife": b.add("fife", I.fife(f, ln * BEAT * 0.92, vel, r), tm, 0.1)
        elif inst == "box": b.add("box", I.musicbox(f, vel, r, 1.6), tm, 0.0)
        elif inst == "vibes": b.add("vibes", I.vibes(f, vel, r, 1.6), tm, 0.0)


def oompah(b, t0, bars, vel=0.55, end=None):
    r = rng(int(t0 * 77))
    for bar in range(bars):
        root = CHORDS[bar % 4]
        for beat in range(4):
            tm = t0 + (bar * 4 + beat) * BEAT
            if end is not None and tm >= end: return
            if beat % 2 == 0: b.add("tuba", I.brass(F(root - 12 + (7 if beat == 2 else 0)), BEAT * 0.5, vel, r, "tuba"), tm, -0.1)
            else: b.add("pluck", I.pluck(F(root + 12), vel * 0.5, r, 0.25, 0.3), tm, 0.3)


def drums(b, t0, t1, vel=0.5, roll=False):
    r = rng(int(t0 * 13))
    tm = t0
    k = 0
    while tm < t1:
        if roll or k % 2 == 0: b.add("snare", I.snare(vel * (1 if k % 4 == 0 else 0.7), r, 0.25), tm, 0.05)
        tm += BEAT / (4 if roll else 2); k += 1


def build_score():
    b = Band()
    # hook: the theme on pluck + glock, a button on the flash
    theme(b, 0.25, 2, "pluck", vel=0.6, end=FLASH - 0.1)
    b.add("timp", I.timpani(F(38), 0.8, rng(1)), FLASH, 0.0); b.add("cym", I.cymbal(0.4, rng(2), 1.4), FLASH, 0.0)
    b.add("glock", I.glock(F(86), 0.7, rng(3)), FLASH, -0.2)
    b.cues.append((FLASH, "D button + timpani + cymbal on the white flash"))
    # 1173: building, playful theme with oom-pah, to the sinking
    t0 = 4.0
    theme(b, t0, 4, "pluck", vel=0.7, end=SINK - 0.05); theme(b, t0 + 16 * BEAT, 4, "glock", vel=0.5, end=SINK - 0.05)
    oompah(b, t0, 6, 0.5, end=SINK - 0.05)
    b.add("timp", I.timpani(F(33), 1.0, rng(4), 2.4), SINK, 0.0)
    for k, m in enumerate([81, 78, 74, 69]):
        b.add("pluck", I.pluck(F(m), 0.6, rng(5 + k), 0.4), SINK + 0.12 * k, 0.0)
    b.cues.append((SINK, "music trips on the sinking: timpani + falling pluck run"))
    # war: snare roll -> fife march (the theme in A) to "Unluckily"
    drums(b, fr(397), fr(488), 0.45, roll=True)
    theme(b, fr(488), 4, "fife", tr=7, vel=0.7, end=fr(557) - 0.05); oompah(b, fr(488), 3, 0.6, end=fr(557) - 0.05); drums(b, fr(488), fr(557) - 0.05, 0.5)
    # "Unluckily": sad trombone, four falling notes
    for k, (m, d) in enumerate([(55, 0.32), (54, 0.32), (53, 0.32), (52, 1.1)]):
        b.add("brass", I.brass(F(m), d, 0.75, rng(20 + k), "horn", fall=(-3.0 if k == 3 else 0.0)), fr(557) + 0.12 + k * 0.38, 0.0)
    b.cues.append((fr(557), "sad trombone 'wah wah wah waaah' on Unluckily"))
    # the century: slow music box
    theme(b, fr(616), 2, "box", vel=0.5, end=fr(677))
    # the return + banana: theme back, glock steps as the storeys go up
    theme(b, fr(681), 4, "pluck", vel=0.65, end=fr(885)); oompah(b, fr(681), 4, 0.45, end=fr(885))
    for k, m in enumerate([74, 78, 81, 86]):
        b.add("glock", I.glock(F(m), 0.6, rng(30 + k)), fr(750) + k * 0.43, 0.2)
    b.add("glock", I.glock(F(93), 0.7, rng(35)), BANANA, 0.0)
    # tipping to 1990: tension pad + timpani pulse
    b.add("pad", I.pad([F(50), F(57), F(62)], fr(1026) - fr(888), 0.45, rng(40), 1.2, 0.6, 700), fr(888), 0.0)
    for k in range(9): b.add("timp", I.timpani(F(38), 0.35 + 0.05 * k, rng(41 + k), 1.2), fr(888) + k * BEAT * 2, 0.0)
    # lead: tuba stomps, a lighter theme
    oompah(b, fr(1030), 6, 0.55, end=fr(1225)); theme(b, fr(1030) + 8 * BEAT, 2, "pluck", vel=0.5, end=fr(1225))
    # wet sand + clay: soft vibes and the music box
    theme(b, fr(1233), 3, "vibes", vel=0.45, end=fr(1401)); theme(b, fr(1405), 2, "box", vel=0.45, end=fr(1540))
    # the topple: music cuts out under the groan, nothing until the crash
    # extraction: playful again, a timpani as it sinks back
    oompah(b, fr(1590), 8, 0.5, end=fr(1817)); theme(b, fr(1590) + 8 * BEAT, 4, "pluck", vel=0.6, end=fr(1817))
    b.add("timp", I.timpani(F(38), 0.8, rng(60), 2.0), SANK, 0.0)
    # finale: the full theme with glock + oom-pah, the button on the last word
    tF = fr(1817) + 0.1
    theme(b, tF, 4, "pluck", vel=0.75, end=DUR - 0.9); theme(b, tF, 4, "glock", vel=0.5, end=DUR - 0.9); oompah(b, tF, 4, 0.6, end=DUR - 0.9)
    end = 64.15
    b.add("brass", I.brass(F(50), 0.6, 0.9, rng(70), "stab"), end, 0.0); b.add("brass", I.brass(F(62), 0.6, 0.8, rng(71), "stab"), end, 0.2)
    b.add("cym", I.cymbal(0.5, rng(72), 2.0), end, 0.0); b.add("glock", I.glock(F(86), 0.8, rng(73)), end, 0.0)
    b.cues.append((end, "D stab + cymbal button after the last word"))
    BAL = {"pluck": 0, "glock": -5, "tuba": -3, "fife": -1, "snare": -7, "timp": -3, "cym": -9, "brass": -2, "box": -2, "vibes": -2, "pad": -6}
    mix = np.zeros((2, N))
    for k, x in b.tracks.items():
        L = integrated(x)
        if np.isfinite(L): mix += x * dbg(-20 + BAL.get(k, -6) - L)
    return mix, b.cues


# ---------------------------------------------------------------- mix
def load_voice():
    src = os.path.join(HERE, "..", "voice", "voice.wav")
    tmp = os.path.join(HERE, "_voice48.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-ar", str(SR), "-ac", "2", tmp], check=True)
    v, _sr = read_wav(tmp)
    out = np.zeros((2, N)); out[:, : min(N, v.shape[1])] = v[:, :N]
    return out


def duck_curve(words, depth_db):
    g = np.zeros(N)
    for w in words:
        a, b = ns(w["start"] - 0.08), ns(w["end"] + 0.15)
        g[max(0, a): min(N, b)] = 1
    k = ns(0.25); win = np.hanning(2 * k + 1); win /= win.sum()
    g = np.convolve(g, win, "same")
    return dbg(depth_db * g)


def main():
    voice = load_voice()
    words = json.load(open(os.path.join(HERE, "..", "voice", "words.json"), encoding="utf-8"))["words"]
    vref = integrated(voice)
    # effects
    sfx = np.zeros((2, N)); send = np.zeros(N); rows = []
    for c in cues():
        x, anchor = c.gen()
        x = pan(np.asarray(x, float), c.p) if np.ndim(x) == 1 else np.asarray(x, float)
        cur = momentary_max(x)
        if np.isfinite(cur): x = x * dbg(vref + c.db - 6.0 - cur)  # skill rule: effects -6 dB
        if c.lpf: x = lp(x, c.lpf, 1)
        place(sfx, x, c.t - anchor)
        if c.send > 0: send[max(0, ns(c.t - anchor)): max(0, ns(c.t - anchor)) + x.shape[1]] += (c.send * x.mean(0))[: max(0, N - max(0, ns(c.t - anchor)))]
        rows.append(f"| {c.t:6.2f} | {c.name} | {c.desc} | {c.db - 6:+.0f} |")
    sfx += 0.5 * convolve_st(send, make_ir(1.2, 9, pre=0.012, hf=1.4))
    sfx = hp(sfx, 25, 2)
    # music: ducked under the voice, +3 dB (skill rule) on the template's -11 LU bed
    music, mcues = build_score()
    music = music * dbg(vref - 13.0 + 3.0 - integrated(music))
    music = music * duck_curve(words, -9.0)[None, :]
    mix = voice + music + sfx
    # master: -14 LUFS, true peak under -1 dBTP (simple look-ahead-free soft limiter + trim)
    mix = mix * dbg(-14.0 - integrated(mix))
    for _ in range(6):
        tp = true_peak(mix)
        if tp <= -1.2: break
        mix = np.tanh(mix / dbg(-1.4)) * dbg(-1.4)
        mix = mix * dbg(-14.0 - integrated(mix))
    end = ns(DUR - 0.25); mix[:, end:] *= np.linspace(1, 0, N - end)[None, :] ** 2
    os.makedirs(os.path.join(HERE, "stems"), exist_ok=True)
    write_wav(os.path.join(HERE, "mix.wav"), mix)
    for n, x in [("voice", voice), ("music", music), ("sfx", sfx)]: write_wav(os.path.join(HERE, "stems", n + ".wav"), x)
    with open(os.path.join(HERE, "cues.md"), "w", encoding="utf-8") as f:
        f.write("# Pisa short: sound cues\n\n| t (s) | cue | what | dB vs voice |\n|---|---|---|---|\n" + "\n".join(rows) + "\n\n## Music\n\n")
        f.write("\n".join(f"- {t:.2f} s: {d}" for t, d in mcues) + "\n")
    print(f"mix {DUR:.2f} s, {integrated(mix):.1f} LUFS, TP {true_peak(mix):.1f} dBTP, {len(rows)} sfx cues")


if __name__ == "__main__":
    main()
