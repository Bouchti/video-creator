"""Sound for "Oregon Blew Up a Whale. On Purpose.": real CC0 recordings (BigSoundBank) laid per shot, an original quiet score
(the skill's synth instruments) ducked under the voice. Every event sits on its picture frame (src/videos/whale/
story.ts + cast.ts).

    python whale_audio.py        (from this folder) -> mix.wav (48 kHz, exact film length), stems/, cues.md

Rules from the user's feedback: real recordings matched to what is on screen, no whoosh loops restarting on cuts
(beds crossfade 0.5 s across shot changes), calm music barely audible (~-22 dB under the voice), no synth dings.
"""
import json, os, subprocess
import numpy as np
from dsp import SR, ns, rng, lp, hp, dbg, pan, place, read_wav, write_wav, integrated, true_peak
import instruments as I

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", "assets", "cc0", "sfx", "bigsoundbank"))
FFMPEG = "ffmpeg"
FPS, TOTAL = 30, 2150
DUR = TOTAL / FPS
N = ns(DUR)
fr = lambda f: f / FPS  # noqa: E731
F = I.m2f

# ---------------------------------------------------------------- recordings
_cache = {}


def rec(name, lpf=None, hpf=None):
    key = (name, lpf, hpf)
    if key not in _cache:
        af = []
        if "@" in name:  # name@0.5: played slower and lower (a deeper boom)
            name, rate = name.split("@"); af.append(f"asetrate=44100*{float(rate)},aresample=48000")
        if hpf: af.append(f"highpass=f={hpf}")
        if lpf: af.append(f"lowpass=f={lpf},lowpass=f={lpf}")
        cmd = [FFMPEG, "-v", "error", "-i", os.path.join(LIB, name + ".mp3")] + (["-af", ",".join(af)] if af else []) + ["-f", "f32le", "-ac", "1", "-ar", str(SR), "-"]
        x = np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, dtype=np.float32).astype(float)
        _cache[key] = x
    return _cache[key]


def level(x):
    """the recording's level while it sounds: 80th percentile of half-second RMS windows (dBFS)"""
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
        env = np.abs(x); i = int(np.argmax(env > 0.5 * env.max()))
        i = max(0, i - int(0.04 * SR))
    else:
        i = int(start * SR)
    y = x[i: i + int(seconds * SR)].copy()
    k = min(len(y), int(0.25 * SR)); y[-k:] *= np.linspace(1, 0, k)
    return y


VREF = None
rows = []


def lay(buf, x, t0, t1, db, name, desc, fade=0.5, p=0.0, peak=False):
    """place a mono layer from t0 to t1 at `db` against the voice level (peak=True: one-shot set by its peak)"""
    n = len(x)
    if peak:
        g = dbg(VREF + db - 20 * np.log10(np.max(np.abs(x)) + 1e-9) + 14)  # peak ~14 dB over the voice's integrated level
    else:
        g = dbg(VREF + db - level(x))
    y = x * g
    k = min(n // 2, int(fade * SR))
    if k > 0 and not peak:
        y[:k] *= np.linspace(0, 1, k); y[-k:] *= np.linspace(1, 0, k)
    place(buf, pan(y, p), t0 - (fade / 2 if not peak else 0))
    rows.append(f"| {t0:6.2f}-{t1:6.2f} | {name} | {desc} | {db:+.0f} |")


# ---------------------------------------------------------------- picture timeline (src/videos/whale/story.ts)
BLAST = 1018
BEACH = [(72, 236), (236, 963), (963, 1392), (1531, 1764), (1894, 2013)]


def hh(i, s=0):
    v = np.sin(i * 127.1 + s * 311.7) * 43758.5453
    return v - np.floor(v)


def blast(sfx, f, db=-4.0, desc="the blast"):
    """the dynamite: a deep body (a far explosion slowed to half speed), a sharp crack on top, the air thump, and the wet
    part: big splashes as the whale comes apart"""
    lay(sfx, hit("explosion-far-away-s1023@0.55", 6.0), fr(f), fr(f), db, "blast", desc + ": deep body (explosion slowed down)", peak=True)
    lay(sfx, hit("explosion-2-s1808@0.6", 0.7), fr(f), fr(f), db - 1, "crack", "the crack on top", peak=True, p=0.1)
    lay(sfx, hit("explosion-1-s1807@0.45", 0.6), fr(f + 1), fr(f + 1), db - 3, "thump", "the air thump", peak=True, p=-0.1)
    lay(sfx, hit("splash-big-3-s1521@0.7", 2.5), fr(f + 2), fr(f + 2), db - 8, "wet", "the wet burst of blubber", peak=True)


def splat(sfx, f, db=-14.0, p=0.0, big=True, desc=""):
    lay(sfx, hit("splash-big-1-s1519@0.8" if big else "splash-small-1-s1529@0.85", 1.0), fr(f), fr(f), db, "splat", desc, peak=True, p=p)
    lay(sfx, hit("steps-in-the-mud-s0495", 0.35, start=1.0 + (f % 5) * 1.3), fr(f), fr(f), db - 4, "squelch", "", peak=True, p=p)


def sfx_track():
    sfx = np.zeros((2, N))
    span = lambda a, b: (fr(a), fr(b))  # noqa: E731
    # the beach: surf + gulls and an onshore wind under every beach shot
    for a, b in BEACH:
        t0, t1 = span(a, b)
        lay(sfx, bed("sea-waves-and-seagulls-s0267", ns(t1 - t0 + 0.5), offset=a / 4), t0, t1, -27, "surf", "Pacific surf and gulls")
        lay(sfx, bed("strong-wind-1-s0146", ns(t1 - t0 + 0.5), lpf=900, offset=a / 6), t0, t1, -36, "wind", "onshore wind")
    # 1-2: the hook: mid-blast on frame 0, the crowd screaming, blubber coming down
    blast(sfx, 0, -3.0, "frame 0: the blast")
    lay(sfx, hit("shouts-and-applauses-of-teens-1-s0236", 2.4, lpf=5000), fr(6), fr(6), -15, "screams", "the crowd screaming and running", peak=True)
    lay(sfx, bed("sea-waves-and-seagulls-s0267", ns(2.6), offset=20), fr(0), fr(72), -30, "surf", "")
    splat(sfx, 42, -10, 0.25, desc="a chunk lands beside Thornton")
    for k, f in enumerate([52, 58, 63, 68]): splat(sfx, f, -19 - k, (k % 3 - 1) * 0.4, big=k % 2 == 0, desc="more chunks raining down" if k == 0 else "")
    # 6: a car cruising the beach highway; 7: the highway truck rolls in, doors
    lay(sfx, hit("motor-car-1-s0290", 2.4, lpf=4000), fr(312), fr(376), -22, "car", "a car driving along the beach")
    lay(sfx, hit("ford-courier-engine-s0896", 2.0, start=1.0, lpf=4000), fr(378), fr(414), -20, "truck", "the highway truck rolling in")
    for k, f in enumerate([414, 419, 424]): lay(sfx, hit("car-door-3-s1524", 0.6), fr(f), fr(f), -17, "doors", "truck doors" if k == 0 else "", peak=True, p=-0.3 + k * 0.3)
    # 8-9: the thought bubble pops in
    lay(sfx, hit("bubble-wrap-breakouts-s0462", 0.15, start=0.5) if os.path.exists(os.path.join(LIB, "bubble-wrap-breakouts-s0462.mp3")) else hit("door-knock-s0095", 0.2, lpf=900), fr(518), fr(518), -20, "pop", "the thought bubble pops up", peak=True, p=0.3)
    lay(sfx, hit("pencil-signature-1-s3236", 1.0), fr(470), fr(500), -24, "pencil", "Thornton's pencil on the clipboard")
    # 11: twenty cases of dynamite stacking up
    for k in range(20):
        f = 622 + int(k * 2.1) + 4
        if k % 2 == 0 or k == 19: lay(sfx, hit("door-knock-s0095", 0.25, lpf=700), fr(f), fr(f), -18 if k < 19 else -11, "cases", "dynamite cases thudding onto the stack" if k == 0 else "", peak=True, p=(k % 5 - 2) * 0.15)
    # 13: "twenty cases": the facepalm
    lay(sfx, hit("door-knock-s0095", 0.15, lpf=2500), fr(845), fr(845), -19, "slap", "Walter's facepalm", peak=True)
    # 14: Walter's new car rolls in, the door, a sparkle
    lay(sfx, hit("motor-car-1-s0290", 1.4, start=2.0, lpf=3500), fr(873), fr(906), -21, "car", "the new car pulling in")
    lay(sfx, hit("car-door-3-s1524", 0.6), fr(902), fr(902), -16, "door", "car door", peak=True, p=0.2)
    lay(sfx, hit("small-bell-s0010", 1.2), fr(905), fr(905), -21, "ding", "a showroom-shine ding", peak=True, p=0.3)
    # 15: the crowd shuffling back
    lay(sfx, hit("outside-talks-2-s2969", 1.8, lpf=4000), fr(918), fr(962), -27, "crowd", "the crowd murmuring as it backs off")
    lay(sfx, hit("steps-on-gravels-s0510", 1.5, lpf=2500), fr(920), fr(960), -27, "steps", "feet shuffling back on sand")
    # 16-18: the countdown: a tick on each number, the plunger clack
    for f in (965, 985, 1005):
        lay(sfx, hit("stopwatch-1-s2137", 0.2), fr(f), fr(f), -15, "tick", "a tick on each count", peak=True)
    lay(sfx, hit("gun-loading-1-s1988", 0.5), fr(1010), fr(1010), -13, "plunger", "the plunger rammed down", peak=True)
    # 19-20: the blast for real; screams; blubber raining on the lot
    blast(sfx, BLAST, -2.0, "the blast (story time)")
    lay(sfx, hit("shouts-and-applauses-of-teens-1-s0236", 3.5, lpf=5000), fr(1046), fr(1046), -14, "screams", "the crowd screaming", peak=True)
    lay(sfx, bed("crowd-of-50-60-people-2-s3516", ns(4.0), lpf=4000, offset=30), fr(1050), fr(1170), -25, "crowd", "crowd panic")
    for i in range(26):
        f = BLAST + int(round((3.3 + 1.3 * hh(i, 13)) * FPS))
        if 1070 <= f < 1172: splat(sfx, f, -14 - 4 * hh(i, 14), (hh(i, 11) - 0.5) * 1.2, big=hh(i, 14) > 0.4, desc="blubber landing on the lot" if i == 0 else "")
    splat(sfx, 1126, -8, 0.0, desc="a big chunk lands right beside a running man")
    lay(sfx, hit("door-knock-s0095", 0.25, lpf=600), fr(1127), fr(1127), -12, "thud", "he goes down", peak=True)
    # 21: "Wait": the wind alone and a lone gull
    # 22: the slow-motion replay: a low drawn-out rumble, speeding up on "move"
    lay(sfx, hit("explosion-far-away-s1023@0.3", 4.0), fr(1272), fr(1272), -14, "slowmo", "the blast slowed right down", peak=True)
    lay(sfx, hit("whoosh-7-s1800", 1.0), fr(1356), fr(1356), -17, "whoosh", "everything flies out on 'move'", peak=True)
    # 23: the kitchen: fridge hum, the hammer on the jelly, kids
    lay(sfx, bed("refrigeration-unit-s3597", ns(fr(1531) - fr(1392) + 0.5), lpf=1500), fr(1392), fr(1531), -36, "fridge", "kitchen fridge hum")
    lay(sfx, hit("door-knock-s0095", 0.25, lpf=900), fr(HAMMER := 1431), fr(1431), -10, "hammer", "the hammer comes down", peak=True)
    lay(sfx, hit("splash-small-3-s1531", 0.8), fr(1432), fr(1432), -12, "jelly", "jelly splattering", peak=True)
    lay(sfx, hit("steps-in-the-mud-s0495", 0.5, start=4.0), fr(1433), fr(1433), -15, "squelch", "", peak=True, p=0.3)
    lay(sfx, hit("delirious-laughter-12-s2102", 1.2, lpf=6000), fr(1500), fr(1500), -21, "laugh", "the kid laughing", peak=True, p=0.3)
    # 24: the gulls take off
    for k, f in enumerate([1568, 1572, 1577]): lay(sfx, hit("flight-bird-1-s2891" if k % 2 else "flight-bird-3-s2893", 0.9), fr(f), fr(f), -16, "wings", "gulls flapping off" if k == 0 else "", peak=True, p=(k - 1) * 0.4)
    # 26: a chunk thumps down behind Thornton on "exactly"
    splat(sfx, 1733, -11, -0.3, desc="a late chunk lands behind Thornton")
    # 27: the park: birds and a friendly afternoon
    t0, t1 = span(1764, 1894)
    lay(sfx, bed("countryside-s0097", ns(t1 - t0 + 0.5)), t0, t1, -29, "park", "park birdsong")
    lay(sfx, bed("cheerful-street-s2372", ns(t1 - t0 + 0.5), lpf=3500), t0, t1, -34, "people", "families in the park")
    # 29-30: the falling lump whistles down, the crush
    lay(sfx, hit("whoosh-7-s1800@0.7", 1.3), fr(1950), fr(1950), -20, "fall", "the lump falling", peak=True)
    lay(sfx, hit("whoosh-7-s1800", 1.0), fr(1968), fr(1968), -16, "fall", "", peak=True)
    lay(sfx, hit("metal-bucket-s0543@0.6", 1.0), fr(1985), fr(1985), -7, "crunch", "the roof crunches", peak=True)
    lay(sfx, hit("car-door-3-s1524@0.8", 0.6), fr(1985), fr(1985), -10, "crunch", "", peak=True, p=0.2)
    splat(sfx, 1985, -8, 0.0, desc="the blubber on the roof")
    lay(sfx, hit("3-glasses-on-table-s1205", 0.8), fr(1987), fr(1987), -16, "glass", "the windows cracking", peak=True, p=-0.2)
    # 31: the dealer's lot, 1970: a bright street, the sparkles
    t0, t1 = span(2013, TOTAL)
    lay(sfx, bed("cheerful-street-s2372", ns(t1 - t0 + 0.5), lpf=4000, offset=10), t0, t1, -30, "street", "a busy street by the car lot")
    for f in (2030, 2070): lay(sfx, hit("small-bell-s0010", 1.0), fr(f), fr(f), -23, "ding", "sparkle dings" if f == 2030 else "", peak=True, p=0.3)
    return sfx


# ---------------------------------------------------------------- score (original): a cheeky seaside shuffle in C
BPM = 112
BEAT = 60 / BPM
BAR = 4 * BEAT
MEL = [(0, .5, 72), (.5, .5, 76), (1, .5, 79), (1.5, .5, 76), (2, 1, 77), (3, 1, 74),
       (4, .5, 71), (4.5, .5, 74), (5, .5, 77), (5.5, .5, 74), (6, 1, 76), (7, 1, 72),
       (8, .5, 69), (8.5, .5, 72), (9, .5, 76), (9.5, .5, 72), (10, 1, 74), (11, .5, 72), (11.5, .5, 71),
       (12, .5, 72), (12.5, .5, 74), (13, .5, 76), (13.5, .5, 74), (14, 2, 72)]
CHORDS = [(36, [64, 67, 72]), (43, [62, 67, 71]), (45, [64, 69, 72]), (41, [65, 69, 72])]


class Band:
    def __init__(self): self.tr = {}; self.cues = []
    def add(self, k, x, t, p=0.0):
        buf = self.tr.setdefault(k, np.zeros((2, N)))
        place(buf, pan(np.asarray(x, float), p) if np.ndim(x) == 1 else x, t)


def shuffle(b, t0, t1, mel=True, vel=0.5, drums=True):
    """plucked bass on 1 and 3, a ukulele-style strum on 2 and 4, brushes; marimba-like melody on top"""
    r = rng(int(t0 * 100))
    k = 0
    while True:
        tb = t0 + k * BAR
        if tb >= t1 - 0.05: break
        root, ch = CHORDS[k % 4]
        for j in range(4):
            tj = tb + j * BEAT
            if tj >= t1: break
            if j % 2 == 0: b.add("bass", I.pluck(F(root + (0 if j == 0 else 7)), vel * 0.9, r, 0.6, 0.35), tj, 0.0)
            else:
                for n, m in enumerate(ch): b.add("uke", I.pluck(F(m), vel * 0.32, r, 0.35, 0.7), tj + n * 0.012, 0.15)
            if drums: b.add("brush", I.brush(vel * (0.5 if j % 2 else 0.3), r), tj, -0.2)
        k += 1
    if mel:
        tm0 = t0
        while tm0 < t1:
            for (bt, ln, m) in MEL:
                tm = tm0 + bt * BEAT
                if tm + ln * BEAT > t1 + 0.05: break
                b.add("mel", I.vibes(F(m), vel * 0.7, r, dur=ln * BEAT + 0.4), tm, 0.05)
            tm0 += 16 * BEAT


def build_score():
    b = Band()
    # the hook plays on the blast alone; the tune starts with the rewind to November 1970
    b.add("timp", I.timpani(F(36), 0.6, rng(1), 1.6), fr(70)); b.cues.append((fr(70), "a timpani hit on the white flash into the rewind"))
    shuffle(b, fr(72), fr(963) - 0.05)
    b.cues.append((fr(72), "the seaside shuffle starts"))
    b.cues.append((fr(963), "music out for the countdown and the blast"))
    shuffle(b, fr(1272), fr(1764) - 0.05, mel=True, vel=0.45)
    b.cues.append((fr(1172), "silence under 'Wait. How does half a ton...'"))
    b.cues.append((fr(1272), "the tune returns on 'You see'"))
    shuffle(b, fr(1764), fr(1946), mel=True, vel=0.5)
    b.cues.append((fr(1946), "music out as the lump falls"))
    shuffle(b, fr(2013), fr(2096), mel=True, vel=0.55)
    for m in [48, 60, 64, 67, 72]: b.add("end", I.vibes(F(m), 0.6, rng(m), dur=2.4), fr(2096), 0.0)
    b.add("bass", I.pluck(F(36), 0.9, rng(9), 1.6, 0.35), fr(2096))
    b.add("timp", I.cymbal(0.35, rng(3), 2.4), fr(2096)); b.cues.append((fr(2096), "final C major chord on 'deal'"))
    BAL = {"mel": -2, "uke": -5, "bass": -3, "brush": -10, "timp": -8, "end": -2}
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
    sfx = sfx * duck_curve(words, -3.0)[None, :]
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
        f.write("# Whale short: sound cues (real CC0 recordings, BigSoundBank)\n\n| t (s) | layer | what | dB vs voice |\n|---|---|---|---|\n" + "\n".join(rows) + "\n\n## Music (original, synthesized)\n\n")
        f.write("\n".join(f"- {t:.2f} s: {d}" for t, d in mcues) + "\n")
    print(f"mix {DUR:.2f} s, {integrated(mix):.1f} LUFS, TP {true_peak(mix):.1f} dBTP; voice {VREF:.1f}, music {integrated(music):.1f}, sfx {integrated(sfx):.1f} LUFS")


if __name__ == "__main__":
    main()
