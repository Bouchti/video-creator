"""Sound for "The Day Boston Drowned in Syrup": real CC0 recordings (BigSoundBank) laid per shot, an original score
(the skill's synth instruments, a jaunty 1910s ragtime in C) ducked under the voice. Every event sits on its picture
frame (src/videos/molasses/story.ts + cast.ts).

    python molasses_audio.py   (from this folder) -> mix.wav (48 kHz, exact film length), stems/, cues.md

Rules from the user's feedback: real recordings matched to what is on screen, beds crossfade across cuts, calm music
~-22 dB under the voice; the hook opens on a hit (roar + screams + the boom on frame 0).
"""
import json, os, subprocess
import numpy as np
from dsp import SR, ns, rng, hp, dbg, pan, place, read_wav, write_wav, integrated, true_peak
import instruments as I

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", "assets", "cc0", "sfx", "bigsoundbank"))
FFMPEG = "ffmpeg"
FPS, TOTAL = 30, 1940
DUR = TOTAL / FPS
N = ns(DUR)
fr = lambda f: f / FPS  # noqa: E731
F = I.m2f

_cache = {}


def rec(name, lpf=None, hpf=None):
    key = (name, lpf, hpf)
    if key not in _cache:
        af = []
        if "@" in name:
            name, rate = name.split("@"); af.append(f"asetrate=44100*{float(rate)},aresample=48000")
        if hpf: af.append(f"highpass=f={hpf}")
        if lpf: af.append(f"lowpass=f={lpf},lowpass=f={lpf}")
        cmd = [FFMPEG, "-v", "error", "-i", os.path.join(LIB, name + ".mp3")] + (["-af", ",".join(af)] if af else []) + ["-f", "f32le", "-ac", "1", "-ar", str(SR), "-"]
        _cache[key] = np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, dtype=np.float32).astype(float)
    return _cache[key]


def level(x):
    w = SR // 2
    bars = [np.sqrt(np.mean(x[i:i + w] ** 2)) + 1e-9 for i in range(0, max(1, len(x) - w), w)]
    return 20 * np.log10(np.percentile(bars, 80))


def bed(name, n, skip=1.0, lpf=None, hpf=None, offset=0.0):
    x = rec(name, lpf, hpf)
    s = int((skip + offset) * SR) % max(1, len(x) - SR)
    x = np.concatenate([x[s:], x[: s]])
    out = x.copy()
    xf = SR
    while len(out) < n:
        r = np.linspace(0, 1, xf)
        out[-xf:] = out[-xf:] * (1 - r) + x[:xf] * r
        out = np.concatenate([out, x[xf:]])
    return out[:n]


def hit(name, seconds=2.0, lpf=None, start=None):
    x = rec(name, lpf)
    if start is None:
        env = np.abs(x); i = int(np.argmax(env > 0.5 * env.max())); i = max(0, i - int(0.04 * SR))
    else:
        i = int(start * SR)
    y = x[i: i + int(seconds * SR)].copy()
    k = min(len(y), int(0.25 * SR)); y[-k:] *= np.linspace(1, 0, k)
    return y


VREF = None
rows = []


def lay(buf, x, t0, t1, db, name, desc, fade=0.5, p=0.0, peak=False):
    n = len(x)
    g = dbg(VREF + db - 20 * np.log10(np.max(np.abs(x)) + 1e-9) + 14) if peak else dbg(VREF + db - level(x))
    y = x * g
    k = min(n // 2, int(fade * SR))
    if k > 0 and not peak:
        y[:k] *= np.linspace(0, 1, k); y[-k:] *= np.linspace(1, 0, k)
    place(buf, pan(y, p), t0 - (fade / 2 if not peak else 0))
    if desc: rows.append(f"| {t0:6.2f}-{t1:6.2f} | {name} | {desc} | {db:+.0f} |")


RIVETS = [858, 864, 869, 874, 878, 882, 887, 891]


def sfx_track():
    sfx = np.zeros((2, N))
    span = lambda a, b: (fr(a), fr(b))  # noqa: E731
    roar = lambda a, b, db, desc="": lay(sfx, bed("small-dam-s0871@0.62", ns(fr(b) - fr(a) + 0.6), lpf=1800), fr(a), fr(b), db, "roar", desc)  # noqa: E731
    rush = lambda a, b, db, desc="": lay(sfx, bed("water-flow-3-s1219@0.75", ns(fr(b) - fr(a) + 0.6), lpf=2500, offset=a / 9), fr(a), fr(b), db, "rush", desc)  # noqa: E731
    panic = lambda a, b, db, desc="": lay(sfx, bed("kids-screaming-1-s1148@0.8", ns(fr(b) - fr(a) + 0.6), lpf=4000, offset=a / 13), fr(a), fr(b), db, "screams", desc, p=-0.15)  # noqa: E731
    # 1-2: the hook: a boom on frame 0, the wave's roar, people screaming; the streetcar crashes over the crest
    lay(sfx, hit("explosion-1-s1807@0.6", 2.4, lpf=1500), 0, 0, -4, "boom", "frame 0: a deep boom", peak=True)
    roar(0, 133, -3, "the syrup wave roaring down the street")
    rush(0, 133, -9, "liquid rushing")
    panic(0, 133, -10, "crowd screaming")
    lay(sfx, bed("manifestation-s0108", ns(4.6), lpf=3500, offset=8), fr(0), fr(133), -16, "shouts", "people shouting, running")
    lay(sfx, hit("anvil-1-s3589", 1.0, lpf=3000), fr(20), fr(20), -10, "clang", "the streetcar's steel crashing", peak=True, p=0.3)
    lay(sfx, hit("glass-burst-s0148", 1.0), fr(22), fr(22), -14, "glass", "streetcar windows bursting", peak=True, p=0.3)
    lay(sfx, hit("splash-big-1-s1519@0.6", 1.6, lpf=2500), fr(30), fr(30), -9, "splash", "a big syrupy splash", peak=True)
    lay(sfx, hit("whoosh-7-s1800@0.7", 0.9), fr(56), fr(56), -14, "whoosh", "into the side view", peak=True)
    # 3: the calm street before: harbor gulls, a tram passing, the tank's ding and the glug of it filling
    t0, t1 = span(133, 257)
    lay(sfx, bed("sea-waves-and-seagulls-s0267", ns(t1 - t0 + 0.5), lpf=6000), t0, t1, -30, "harbor", "harbor gulls")
    lay(sfx, bed("outside-talks-2-s2969", ns(t1 - t0 + 0.5), lpf=4500), t0, t1, -32, "street", "street voices")
    lay(sfx, hit("passing-tram-1-s0278", 3.5, lpf=4000), fr(140), fr(140), -22, "tram", "a streetcar passing", peak=True, p=-0.3)
    lay(sfx, hit("small-bell-s0010", 0.8), fr(176), fr(176), -19, "ding", "the 50 FT tag pops", peak=True, p=0.2)
    lay(sfx, hit("glass-of-water-filling-1-s1242@0.5", 1.6), fr(228), fr(228), -16, "glug", "the tank filling with molasses", peak=True)
    # 4-5: the office: pencil, the X buzzer, the adding machine, the blueprint
    t0, t1 = span(257, 438)
    lay(sfx, bed("atmosphere-bar-2-s0480", ns(t1 - t0 + 0.5), lpf=1200), t0, t1, -38, "room", "office room tone")
    lay(sfx, hit("pencil-signature-1-s3236", 1.4), fr(262), fr(262), -20, "pencil", "the accountant scribbling", peak=True)
    lay(sfx, hit("door-knock-s0095", 0.2, lpf=1500), fr(301), fr(301), -20, "pop", "the hard-hat badge pops up", peak=True)
    lay(sfx, hit("rattle-s0923", 0.4), fr(309), fr(309), -17, "x", "the red X", peak=True)
    lay(sfx, hit("typewriter-8-s2841", 1.6), fr(361), fr(361), -15, "adder", "the adding machine cranking", peak=True)
    lay(sfx, hit("great-page-that-turns-1-s0362", 0.9), fr(408), fr(408), -15, "paper", "the blueprint turned sideways", peak=True)
    # 6-9: at the tank: drips and trickles; the brush; the ta-da; buckets filling
    t0, t1 = span(438, 731)
    lay(sfx, bed("sea-waves-and-seagulls-s0267", ns(t1 - t0 + 0.5), lpf=5000, offset=20), t0, t1, -34, "harbor", "")
    lay(sfx, bed("liquid-flowing-over-the-soil-s0563", ns(fr(519) - fr(438) + 0.5), lpf=3000), fr(438), fr(519), -24, "leak", "molasses trickling down the tank")
    for k in range(5): lay(sfx, hit("drops-of-water-2-s1385@0.7", 0.4, start=0.2 + k * 0.6), fr(448 + k * 13), fr(448 + k * 13), -21, "drip", "thick drips" if k == 0 else "", peak=True, p=0.2)
    lay(sfx, hit("steps-on-gravels-s0510", 0.8, lpf=2000), fr(520), fr(520), -22, "ladder", "climbing the ladder", peak=True)
    for k, f in enumerate([553, 561, 569, 577]): lay(sfx, hit("news-paper-manipulations-s1251", 0.35, lpf=3500, start=1.0 + k * 0.4), fr(f), fr(f), -18, "brush", "brush strokes" if k == 0 else "", peak=True)
    lay(sfx, hit("small-bell-s0010", 1.2), fr(618), fr(618), -15, "tada", "ta-da: the leaks match", peak=True)
    for f in (650, 664, 678): lay(sfx, hit("metal-bucket-s0543", 0.6), fr(f), fr(f), -17, "bucket", "tin buckets set down" if f == 650 else "", peak=True, p=-0.2)
    lay(sfx, bed("liquid-flowing-over-the-soil-s0563", ns(fr(731) - fr(660) + 0.5), lpf=2500, offset=5), fr(660), fr(731), -26, "pour", "molasses glugging into buckets")
    lay(sfx, hit("spoon-into-a-mug-of-coffee-s0410", 0.6), fr(705), fr(705), -20, "lick", "the kid licking his finger", peak=True)
    # 10: the warm January day
    t0, t1 = span(731, 799)
    lay(sfx, bed("outside-talks-2-s2969", ns(t1 - t0 + 0.5), lpf=4500, offset=12), t0, t1, -30, "street", "a mild street")
    lay(sfx, hit("small-ratchet-s0794", 1.4), fr(748), fr(748), -18, "thermo", "the thermometer climbing", peak=True)
    # 11-12: the groan; rivets like machine-gun fire
    lay(sfx, hit("creaking-metallic-door-s0616@0.45", 2.6, lpf=1600), fr(806), fr(806), -7, "groan", "the tank's steel groaning", peak=True)
    lay(sfx, hit("creaking-metallic-door-s0616@0.4", 2.0, lpf=1400, start=6.0), fr(823), fr(823), -8, "groan", "", peak=True)
    for f in RIVETS:
        lay(sfx, hit("bang-snaps-s0550", 0.3), fr(f), fr(f), -8, "rivet", "rivets popping" if f == RIVETS[0] else "", peak=True, p=0.3 if f % 2 else -0.3)
        lay(sfx, hit("bullet-case-7-62mm-on-concrete-1-s1367", 0.5), fr(f + 2), fr(f + 2), -16, "tink", "", peak=True)
    # 13: the burst: boom, steel tearing, the geyser's roar
    lay(sfx, hit("explosion-1-s1807@0.55", 3.0, lpf=1400), fr(904), fr(904), -2, "burst", "the tank bursts", peak=True)
    lay(sfx, hit("creaking-metallic-door-s0616@0.35", 1.8, lpf=1200, start=3.0), fr(906), fr(906), -8, "tear", "steel plates tearing open", peak=True)
    roar(905, 1120, -4, "the flood roaring")
    rush(905, 1120, -9)
    panic(915, 1118, -12)
    # 14: the streetcar knocked over, the truck into the harbor; 15: the surfer
    lay(sfx, hit("anvil-1-s3589", 1.2, lpf=2500), fr(985), fr(985), -8, "crash", "the streetcar knocked over", peak=True, p=-0.3)
    lay(sfx, hit("glass-burst-s0148", 1.0), fr(988), fr(988), -12, "glass", "", peak=True, p=-0.3)
    lay(sfx, hit("whoosh-7-s1800@0.8", 0.9), fr(1018), fr(1018), -12, "fly", "the truck thrown", peak=True, p=0.3)
    lay(sfx, hit("splash-big-3-s1521", 2.0), fr(1040), fr(1040), -6, "splash", "the truck splashes into the harbor", peak=True, p=0.4)
    lay(sfx, hit("water-swirls-and-flow-s0245", 2.0, lpf=3000), fr(1060), fr(1060), -16, "surf", "riding the crest", peak=True)
    # 16: quiet: the flooded street; sailors wading, stuck
    t0, t1 = span(1118, 1248)
    lay(sfx, bed("sea-waves-and-seagulls-s0267", ns(t1 - t0 + 0.5), lpf=3000, offset=40), t0, t1, -34, "quiet", "a hush; distant gulls")
    for k, f in enumerate(range(1150, 1240, 15)): lay(sfx, hit("steps-in-the-mud-s0495", 0.5, start=0.5 + k * 0.7), fr(f), fr(f), -19, "wade", "boots squelching through syrup" if k == 0 else "", peak=True, p=-0.2 + k * 0.08)
    # 17-20: everything sticky: squelches, a bench, a payphone
    for f in (1262, 1280, 1296, 1310, 1322, 1340, 1350, 1362, 1372):
        lay(sfx, hit("steps-in-the-mud-s0495", 0.45, start=1.0 + (f % 7) * 0.5), fr(f), fr(f), -15, "squelch", "sticky squelch" if f == 1262 else "", peak=True)
    lay(sfx, bed("ventilation-5-s3598", ns(fr(1355) - fr(1300) + 0.4), lpf=900), fr(1300), fr(1355), -34, "station", "station hum")
    lay(sfx, hit("lock-s0191", 0.3), fr(1336), fr(1336), -18, "phone", "the receiver clacks", peak=True)
    # 21: the press: flashbulbs, murmurs, the fuse hiss
    t0, t1 = span(1381, 1486)
    lay(sfx, bed("walla-group-averages-discussions-s0684", ns(t1 - t0 + 0.5), lpf=4000), t0, t1, -28, "press", "reporters murmuring")
    for f in (1392, 1470): lay(sfx, hit("trigger-of-camera-1-s2394", 0.5), fr(f), fr(f), -13, "flash", "a flashbulb", peak=True, p=0.3)
    lay(sfx, hit("cigarette-ignition-s2131", 1.6), fr(1432), fr(1432), -15, "fuse", "the bomb's fuse fizzing", peak=True, p=-0.2)
    # 22: the court: pages, the gavel on "no"
    t0, t1 = span(1486, 1600)
    lay(sfx, bed("walla-group-averages-discussions-s0684", ns(t1 - t0 + 0.5), lpf=1800, offset=20), t0, t1, -36, "court", "a hushed courtroom")
    lay(sfx, hit("great-page-that-turns-1-s0362", 0.9), fr(1491), fr(1491), -16, "calendar", "calendar pages flipping", peak=True)
    lay(sfx, hit("gavel-1-blow-s1588", 0.6), fr(1538), fr(1538), -6, "gavel", "the gavel on 'no'", peak=True)
    lay(sfx, hit("gavel-1-blow-s1588", 0.6), fr(1544), fr(1544), -10, "gavel", "", peak=True)
    # 23-24: summer: gulls on the brown harbor; the sweet street
    t0, t1 = span(1600, 1708)
    lay(sfx, bed("sea-waves-and-seagulls-s0267", ns(t1 - t0 + 0.5), lpf=7000, offset=60), t0, t1, -26, "summer", "summer gulls, slow water")
    lay(sfx, bed("cicadas-s3002", ns(t1 - t0 + 0.5), lpf=6000), t0, t1, -34, "summer", "summer heat")
    lay(sfx, hit("small-bell-s0010", 1.2), fr(1672), fr(1672), -19, "sweet", "a sweet ding", peak=True)
    # 25-26: the office: the still bubbling, a glass clinked; the paper; the glass smashes
    t0, t1 = span(1708, TOTAL)
    lay(sfx, bed("atmosphere-bar-2-s0480", ns(t1 - t0 + 0.5), lpf=1200, offset=6), t0, t1, -38, "room", "office room tone")
    lay(sfx, hit("water-bubbles-s0150", 1.8), fr(1745), fr(1745), -18, "still", "the still bubbling", peak=True)
    lay(sfx, hit("cheers-small-wineglass-1-s1325", 0.8), fr(1766), fr(1766), -14, "clink", "a glass raised", peak=True)
    lay(sfx, hit("news-paper-manipulations-s1251", 1.2, start=2.0), fr(1798), fr(1798), -17, "paper", "the morning paper", peak=True)
    lay(sfx, hit("broken-glass-of-champagne-s1591", 1.4), fr(1866), fr(1866), -7, "smash", "his glass smashes on 'banned'", peak=True, p=0.2)
    return sfx


# ---------------------------------------------------------------- score (original): a jaunty 1910s ragtime in C
BPM = 112
BEAT = 60 / BPM
BAR = 4 * BEAT
# a syncopated melody over 4 bars (beat, length, midi)
MEL = [(0, .5, 76), (.5, .5, 79), (1, .25, 81), (1.25, .75, 79), (2, .5, 76), (2.5, .5, 72), (3, 1, 74),
       (4, .5, 77), (4.5, .5, 81), (5, .25, 83), (5.25, .75, 81), (6, .5, 77), (6.5, .5, 74), (7, 1, 76),
       (8, .5, 79), (8.5, .5, 76), (9, .5, 72), (9.5, .5, 76), (10, .5, 79), (10.5, .5, 84), (11, 1, 83),
       (12, .5, 81), (12.5, .5, 77), (13, .5, 74), (13.5, .5, 71), (14, 2, 72)]
CHORDS = [(48, [64, 67, 72]), (53, [65, 69, 72]), (43, [62, 65, 71]), (48, [64, 67, 72])]


class Band:
    def __init__(self): self.tr = {}; self.cues = []
    def add(self, k, x, t, p=0.0):
        buf = self.tr.setdefault(k, np.zeros((2, N)))
        place(buf, pan(np.asarray(x, float), p) if np.ndim(x) == 1 else x, t)


def rag(b, t0, t1, mel=True, vel=0.5):
    """stride left hand (bass note on 1 and 3, chord on 2 and 4), a bright plucked-piano melody, brushes"""
    r = rng(int(t0 * 100))
    k = 0
    while True:
        tb = t0 + k * BAR
        if tb >= t1 - 0.05: break
        root, ch = CHORDS[k % 4]
        for j in range(4):
            tj = tb + j * BEAT
            if tj >= t1: break
            if j % 2 == 0: b.add("bass", I.pluck(F(root - 12 + (0 if j == 0 else 7)), vel * 0.9, r, 0.45, 0.35), tj, 0.0)
            else:
                for n, m in enumerate(ch): b.add("chord", I.pluck(F(m - 12), vel * 0.3, r, 0.25, 0.7), tj + n * 0.008, 0.15)
            b.add("brush", I.brush(vel * (0.5 if j % 2 else 0.28), r), tj, -0.2)
        k += 1
    if mel:
        tm0 = t0
        while tm0 < t1:
            for (bt, ln, m) in MEL:
                tm = tm0 + bt * BEAT
                if tm + ln * BEAT > t1 + 0.05: break
                b.add("mel", I.pluck(F(m), vel * 0.6, r, ln * BEAT + 0.3, 0.8), tm, 0.05)
            tm0 += 16 * BEAT


def build_score():
    b = Band()
    # the hook has no tune: the roar is the music; a timpani hit and cymbal on the white flash into the story
    b.add("timp", I.timpani(F(36), 0.7, rng(1), 2.0), fr(131)); b.add("cym", I.cymbal(0.35, rng(2), 2.2), fr(131)); b.cues.append((fr(131), "timpani + cymbal on the flash into the story"))
    rag(b, fr(136), fr(799) - 0.05, vel=0.5); b.cues.append((fr(136), "the ragtime starts"))
    # Jell whistles beside the leaks (488-518)
    w0, wx = I.whistle([(0.0, 0.2, 79, 0.7), (0.24, 0.2, 84, 0.7), (0.5, 0.35, 81, 0.7), (0.9, 0.5, 76, 0.6)], rng(5)); b.add("whistle", wx, fr(488) + w0, 0.1); b.cues.append((fr(488), "the accountant whistles"))
    # ta-da on "match"
    for m in (72, 76, 79, 84): b.add("tada", I.glock(F(m), 0.7, rng(m), dur=1.4), fr(618) + (m - 72) * 0.012, 0.0)
    # the groan: the tune stops, a low tremolo pad of dread up to the burst
    b.cues.append((fr(799), "music stops for the groan"))
    for m in (36, 43): b.add("dread", I.pad([F(m)], 3.4, 0.4, rng(m), att=0.8, rel=0.6, warm=600, trem=lambda tt_: 0.75 + 0.25 * np.sin(2 * np.pi * 7.0 * tt_)), fr(800), 0.0)
    for tr_, vr_ in I.snare_roll(0.0, 1.6, 0.15, 0.7, rng(7)): b.add("roll", I.snare(vr_, rng(int(tr_ * 1000)), 0.2, buzz=True), fr(850) + tr_)
    b.add("timp", I.timpani(F(36), 0.9, rng(8), 2.4), fr(904)); b.cues.append((fr(904), "timpani on the burst"))
    # the quiet: soft sad chords under the deaths and the rescue
    for m in (57, 60, 64): b.add("pad", I.pad([F(m)], 3.2, 0.3, rng(m), att=0.8, rel=1.2, warm=1200), fr(1124), 0.0)
    for m in (53, 57, 60): b.add("pad", I.pad([F(m)], 2.6, 0.3, rng(m + 1), att=0.8, rel=1.2, warm=1200), fr(1190), 0.0)
    b.cues.append((fr(1124), "soft sad chords for the deaths and the rescue"))
    rag(b, fr(1252), fr(1861) - 0.05, vel=0.48); b.cues.append((fr(1252), "the ragtime returns: everything sticky"))
    # "banned": the tune stops dead, a sad two-note fall, a low final chord
    b.cues.append((fr(1861), "the tune stops dead on 'banned'"))
    b.add("sting", I.brass(F(55), 0.5, 0.6, rng(11), kind="tuba"), fr(1876)); b.add("sting", I.brass(F(54), 0.9, 0.6, rng(12), kind="tuba", fall=-3.0), fr(1893))
    for m in (36, 48, 55, 60): b.add("end", I.pluck(F(m), 0.6, rng(m), 2.2, 0.4), fr(1912))
    b.cues.append((fr(1876), "a sad tuba 'wah-wah' and a last chord"))
    BAL = {"mel": -2, "chord": -6, "bass": -3, "brush": -11, "timp": -6, "cym": -10, "whistle": -2, "tada": -4, "dread": -4, "roll": -10, "pad": -6, "sting": -2, "end": -3}
    mix = np.zeros((2, N))
    for k, x in b.tr.items():
        L = integrated(x)
        if np.isfinite(L): mix += x * dbg(-20 + BAL.get(k, -6) - L)
    return mix, b.cues


def duck_curve(words, depth_db):
    g = np.zeros(N)
    for w in words:
        a, c = ns(w["start"] - 0.08), ns(w["end"] + 0.15)
        g[max(0, a): min(N, c)] = 1
    k = ns(0.25); win = np.hanning(2 * k + 1); win /= win.sum()
    from scipy.signal import fftconvolve
    return dbg(depth_db * fftconvolve(g, win, "same"))


def main():
    global VREF
    src = os.path.join(HERE, "..", "voice", "voice.wav"), os.path.join(HERE, "_voice48.wav")
    subprocess.run([FFMPEG, "-v", "error", "-y", "-i", src[0], "-ar", str(SR), "-ac", "2", src[1]], check=True)
    v, _ = read_wav(src[1])
    voice = np.zeros((2, N)); voice[:, : min(N, v.shape[1])] = v[:, :N]
    words = json.load(open(os.path.join(HERE, "..", "voice", "words.json"), encoding="utf-8"))["words"]
    VREF = integrated(voice)
    sfx = hp(sfx_track(), 30, 2)
    sfx = sfx * duck_curve(words, -4.0)[None, :]
    music, mcues = build_score()
    music = music * dbg(VREF - 22.0 - integrated(music))
    music = music * duck_curve(words, -4.0)[None, :]
    mix = voice + music + sfx
    mix = mix * dbg(-14.0 - integrated(mix))
    for _ in range(6):
        if true_peak(mix) <= -1.2: break
        mix = np.tanh(mix / dbg(-1.4)) * dbg(-1.4)
        mix = mix * dbg(-14.0 - integrated(mix))
    end = ns(DUR - 0.4); mix[:, end:] *= np.linspace(1, 0, N - end)[None, :] ** 2
    os.makedirs(os.path.join(HERE, "stems"), exist_ok=True)
    write_wav(os.path.join(HERE, "mix.wav"), mix)
    for n, x in [("voice", voice), ("music", music), ("sfx", sfx)]: write_wav(os.path.join(HERE, "stems", n + ".wav"), x)
    with open(os.path.join(HERE, "cues.md"), "w", encoding="utf-8") as f:
        f.write("# Molasses short: sound cues (real CC0 recordings, BigSoundBank)\n\n| t (s) | layer | what | dB vs voice |\n|---|---|---|---|\n" + "\n".join(rows) + "\n\n## Music (original, synthesized)\n\n")
        f.write("\n".join(f"- {t:.2f} s: {d}" for t, d in mcues) + "\n")
    print(f"mix {DUR:.2f} s, {integrated(mix):.1f} LUFS, TP {true_peak(mix):.1f} dBTP; voice {VREF:.1f}, music {integrated(music):.1f}, sfx {integrated(sfx):.1f} LUFS")


if __name__ == "__main__":
    main()
