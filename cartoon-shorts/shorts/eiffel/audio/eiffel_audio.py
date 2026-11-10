"""Sound for "The Bribe That Sold the Eiffel Tower": real CC0 recordings (BigSoundBank) laid per shot, an original quiet score
(the skill's synth instruments) ducked under the voice. Every event sits on its picture frame (src/videos/eiffel/
story.ts + cast.ts).

    python eiffel_audio.py        (from this folder) -> mix.wav (48 kHz, exact film length), stems/, cues.md

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
FPS, TOTAL = 30, 2125
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


# ---------------------------------------------------------------- picture timeline (src/videos/eiffel/story.ts)
PARIS_OUT = [(0, 105), (202, 316), (734, 1049), (2006, TOTAL)]
SALON = [(389, 734), (1205, 1398), (1548, 1744)]
HOME = [(1049, 1205), (1926, 1966)]
FLASH = 101


def sfx_track():
    sfx = np.zeros((2, N))
    span = lambda a, b: (fr(a), fr(b))  # noqa: E731
    for a, b in PARIS_OUT:
        t0, t1 = span(a, b)
        lay(sfx, bed("city-center-1-s2762", ns(t1 - t0 + 0.5), lpf=5000, offset=a / 7), t0, t1, -29, "Paris", "a city square: distant voices and birds")
    # the hook: the cash changes hands, the second envelope on "bribe"
    lay(sfx, hit("news-paper-manipulations-s1251", 0.6, start=2.0), fr(62), fr(62), -18, "envelope", "the buyer pulls out the envelope", peak=True, p=0.2)
    lay(sfx, hit("coins-1-s0193", 0.8), fr(78), fr(78), -16, "coins", "a jingle on 'bribe'", peak=True, p=0.2)
    # the café: cups, a spoon, the paper
    t0, t1 = span(105, 202)
    lay(sfx, bed("cheerful-street-s2372", ns(t1 - t0 + 0.5), lpf=5000), t0, t1, -28, "café street", "a café terrace street")
    lay(sfx, bed("spoon-into-a-mug-of-coffee-s0410", ns(t1 - t0 + 0.5)), t0, t1, -31, "spoon", "a spoon in a coffee cup")
    lay(sfx, hit("news-paper-manipulations-s1251", 1.0, start=1.0), fr(110), fr(110), -17, "paper", "the newspaper shakes open", peak=True, p=-0.1)
    # the painter high on the leg: wind, the bucket
    lay(sfx, bed("strong-wind-1-s0146", ns(fr(240) - fr(202) + 0.5), lpf=1600, offset=3), fr(202), fr(240), -24, "wind", "wind high on the tower")
    lay(sfx, hit("metal-bucket-s0543", 0.6), fr(214), fr(214), -20, "bucket", "the paint bucket knocks the girder", peak=True, p=0.15)
    # the forger's press and the stamp
    lay(sfx, bed("heidelberg-printing-press-2-s3405", ns(fr(343) - fr(316) + 0.5), lpf=4000), fr(316), fr(343), -22, "press", "a printing press runs the letterhead")
    lay(sfx, hit("door-knock-s0095", 0.3, lpf=900), fr(343), fr(343), -12, "stamp", "the stamp thumps down (muffled knock)", peak=True)
    # the salon: murmurs, glasses
    for a, b in SALON:
        t0, t1 = span(a, b)
        lay(sfx, bed("computer-2-ventilation-s0126", ns(t1 - t0 + 0.5), lpf=700, offset=a / 9), t0, t1, -38, "room", "the salon's room tone")
    lay(sfx, bed("walla-group-averages-discussions-s0684", ns(fr(556) - fr(389) + 0.5), lpf=3500), fr(389), fr(556), -29, "murmur", "the dealers chatting")
    lay(sfx, hit("3-glasses-on-table-s1205", 1.0), fr(400), fr(400), -22, "glasses", "glasses set on the table", peak=True, p=-0.2)
    lay(sfx, hit("crowd-of-50-60-people-1-s3515", 1.6, lpf=1500), fr(684), fr(684), -22, "riot", "an angry crowd, muffled (the thought cloud)", peak=True)
    # the limousine: engine and its horn
    lay(sfx, hit("motor-car-1-s0290", 2.0), fr(734), fr(786), -19, "limo", "a vintage motor car")
    lay(sfx, hit("oogah-horn-3-s2542", 0.8), fr(748), fr(748), -18, "horn", "the limousine's horn", peak=True, p=0.1)
    # the knocks on the girder
    for k in [790, 806, 826]:
        lay(sfx, hit("metal-bucket-s0543", 0.5, lpf=2400), fr(k), fr(k), -13, "knock", "a knuckle on the iron girder", peak=True, p=-0.15)
    lay(sfx, hit("cheers-small-wineglass-1-s1325", 0.8), fr(975), fr(975), -21, "sparkle", "the dream sparkle (a glass ting)", peak=True, p=0.1)
    # the parlour: a clock
    for a, b in HOME:
        t0, t1 = span(a, b)
        lay(sfx, bed("stopwatch-1-s2137", ns(t1 - t0 + 0.5), lpf=2500), t0, t1, -33, "clock", "the parlour clock ticking")
    # the walk away
    lay(sfx, bed("footsteps-shoe-on-parquet-s0376", ns(fr(1258) - fr(1210) + 0.5), lpf=2500), fr(1210), fr(1258), -25, "steps", "the dealer walking off")
    # the ministry: typing, a busy hall, coins
    t0, t1 = span(1398, 1548)
    lay(sfx, bed("typewriter-8-s2841", ns(t1 - t0 + 0.5), lpf=3000), t0, t1, -31, "typewriter", "ministry typewriters")
    lay(sfx, bed("walla-group-averages-discussions-s0684", ns(t1 - t0 + 0.5), lpf=2500, offset=7), t0, t1, -33, "hall", "a busy hall")
    for k, f in enumerate([1420, 1452, 1490]):
        lay(sfx, hit("coins-2-s0194", 0.6, start=0.5 + k * 1.3), fr(f), fr(f), -18, "coins", "a bribe slides into a drawer", peak=True, p=(k - 1) * 0.3)
    # the deal: the envelope, the cash
    lay(sfx, hit("news-paper-manipulations-s1251", 0.8, start=3.0), fr(1686), fr(1686), -17, "envelope", "the envelope handed over", peak=True, p=0.2)
    lay(sfx, hit("coins-1-s0193", 1.2, start=0.3), fr(1714), fr(1714), -17, "cash", "the price counted out", peak=True, p=0.2)
    # the train to Austria
    t0, t1 = span(1744, 1841)
    lay(sfx, bed("steam-locomotive-passage-s3009", ns(t1 - t0 + 0.5), lpf=6000), t0, t1, -17, "train", "a steam train running")
    lay(sfx, hit("train-whistle-foley-7-s3321", 1.6), fr(1752), fr(1752), -16, "whistle", "the train whistle", peak=True, p=0.2)
    # the Austrian morning
    t0, t1 = span(1841, 1926)
    lay(sfx, bed("cheerful-street-s2372", ns(t1 - t0 + 0.5), lpf=4500, offset=20), t0, t1, -29, "morning street", "a quiet morning street")
    lay(sfx, hit("news-paper-manipulations-s1251", 1.0, start=6.0), fr(1844), fr(1844), -18, "paper", "the paper opened", peak=True, p=-0.1)
    lay(sfx, hit("news-paper-manipulations-s1251", 0.8, start=8.0), fr(1910), fr(1910), -17, "paper", "the paper folded down on 'Nothing'", peak=True, p=-0.1)
    # the policeman's street
    t0, t1 = span(1966, 2006)
    lay(sfx, bed("cheerful-street-s2372", ns(t1 - t0 + 0.5), lpf=5000, offset=40), t0, t1, -29, "street", "the street with the policeman")
    lay(sfx, bed("footsteps-shoe-on-concrete-s0514", ns(t1 - t0 + 0.5), lpf=3000, offset=5), t0, t1, -26, "steps", "the dealer hurrying past")
    # the return: footsteps
    lay(sfx, bed("footsteps-shoe-on-concrete-s0514", ns(fr(2072) - fr(2006) + 0.5), lpf=3000), fr(2006), fr(2072), -26, "steps", "walking back to the tower")
    return sfx


# ---------------------------------------------------------------- score (original): a sneaky musette waltz in A minor
BEAT = 60 / 138
BAR = 3 * BEAT
MEL = [(0, 1, 76), (1, .5, 72), (1.5, .5, 71), (2, 1, 69), (3, 1.5, 68), (4.5, .5, 71), (5, 1, 76),
       (6, 1, 81), (7, .5, 79), (7.5, .5, 77), (8, 1, 76), (9, 2, 74), (11, 1, 77),
       (12, 1, 76), (13, .5, 72), (13.5, .5, 71), (14, 1, 69), (15, 1, 71), (16, 1, 74), (17, 1, 68), (18, 3, 69)]
CHORDS = [(45, [57, 60, 64]), (40, [56, 59, 62]), (45, [57, 60, 64]), (38, [57, 62, 65]), (45, [57, 60, 64]), (40, [56, 59, 62]), (45, [57, 60, 64]), (40, [56, 59, 64])]


class Band:
    def __init__(self): self.tr = {}; self.cues = []
    def add(self, k, x, t, p=0.0):
        buf = self.tr.setdefault(k, np.zeros((2, N)))
        place(buf, pan(np.asarray(x, float), p) if np.ndim(x) == 1 else x, t)


def waltz(b, t0, t1, mel=True, vel=0.5):
    """oom-pah-pah (pizzicato bass + chord plucks) and the musette melody (detuned tremolo pad) from t0 to t1"""
    r = rng(int(t0 * 100))
    trem = lambda t: 1 + 0.18 * np.sin(2 * np.pi * 6.2 * t)  # noqa: E731
    k = 0
    while True:
        tb = t0 + k * BAR
        if tb >= t1: break
        root, ch = CHORDS[k % 8]
        b.add("bass", I.pluck(F(root), vel * 0.9, r, 0.6, 0.3), tb, 0.0)
        for j in (1, 2):
            for m in ch: b.add("chord", I.pluck(F(m), vel * 0.35, r, 0.3, 0.6), tb + j * BEAT, 0.1)
        k += 1
    if mel:
        tm0 = t0
        while tm0 < t1:
            for (bt, ln, m) in MEL:
                tm = tm0 + bt * BEAT
                if tm >= t1: break
                b.add("musette", I.pad([F(m)], ln * BEAT * 0.92, vel * 0.8, r, att=0.02, rel=0.12, warm=2600, detune=14, trem=trem), tm, 0.0)
            tm0 += 24 * BEAT


def build_score():
    b = Band()
    waltz(b, 0.15, fr(1325) - 0.05)
    b.add("timp", I.timpani(F(33), 0.5, rng(1), 1.6), fr(FLASH)); b.cues.append((fr(FLASH), "soft timpani under the white flash"))
    # the drop-out: "Wait, a bribe?" plays in silence, a single bass pluck lands on "bribe"
    b.add("bass", I.pluck(F(40), 0.6, rng(5), 1.2, 0.3), fr(1334)); b.cues.append((fr(1325), "music stops for 'Wait, a bribe?'"))
    waltz(b, fr(1398), fr(2097), mel=True, vel=0.5)
    b.cues.append((fr(1398), "the waltz returns on 'You see'"))
    # the ending: a cheeky final chord on "again"
    for m in [57, 60, 64, 69]: b.add("chord", I.pluck(F(m), 0.6, rng(m), 1.4, 0.6), fr(2097), 0.0)
    b.add("bass", I.pluck(F(33), 0.7, rng(9), 1.6, 0.3), fr(2097)); b.cues.append((fr(2097), "final A minor chord on 'again'"))
    BAL = {"musette": -1, "chord": -4, "bass": -3, "timp": -6}
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
        f.write("# Eiffel short: sound cues (real CC0 recordings, BigSoundBank)\n\n| t (s) | layer | what | dB vs voice |\n|---|---|---|---|\n" + "\n".join(rows) + "\n\n## Music (original, synthesized)\n\n")
        f.write("\n".join(f"- {t:.2f} s: {d}" for t, d in mcues) + "\n")
    print(f"mix {DUR:.2f} s, {integrated(mix):.1f} LUFS, TP {true_peak(mix):.1f} dBTP; voice {VREF:.1f}, music {integrated(music):.1f}, sfx {integrated(sfx):.1f} LUFS")


if __name__ == "__main__":
    main()
