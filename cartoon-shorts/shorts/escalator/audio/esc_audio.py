"""Sound for "Where Do Escalator Steps Go?": real CC0 recordings (BigSoundBank) laid per shot, an original quiet score
(the skill's synth instruments) ducked under the voice. Every event sits on its picture frame (src/videos/escalator/
story.ts + cast.ts).

    python esc_audio.py        (from this folder) -> mix.wav (48 kHz, exact film length), stems/, cues.md

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
FPS, TOTAL = 30, 2080
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


# ---------------------------------------------------------------- picture timeline (story.ts)
SHOTS = {1: (0, 159), 2: (159, 318), 3: (318, 414), 4: (414, 547), 5: (547, 592), 6: (592, 652), 7: (652, 739), 8: (739, 843),
         9: (843, 957), 10: (957, 1080), 11: (1080, 1206), 12: (1206, 1366), 13: (1366, 1499), 14: (1499, 1602), 15: (1602, 1737),
         16: (1737, 1934), 17: (1934, TOTAL)}
CUT = [(85, 159), (652, 1206), (1366, 1602)]      # section views: the machine is up close
HALL = (159, 652)


def sfx_track():
    sfx = np.zeros((2, N))
    # ---- today: the escalator's steady hum + clatter, the plaza around it ----
    for a, b in [(0, 159), (652, TOTAL)]:
        t0, t1 = fr(a), fr(b)
        lay(sfx, bed("escalator-1-s3064", ns(t1 - t0 + 0.5), lpf=7000), t0, t1, -17, "escalator", "the escalator running: steps, comb, motor hum")
        lay(sfx, bed("cheerful-street-s2372", ns(t1 - t0 + 0.5), lpf=6000, offset=7), t0, t1, -27, "plaza", "town plaza ambience, far voices (no words)")
    # section views: the machine close (second escalator take, low-passed: inside the truss) on top of the hum
    for a, b in CUT:
        t0, t1 = fr(a), fr(b)
        lay(sfx, bed("escalator-3-s3066", ns(t1 - t0 + 0.5), lpf=2400, offset=3 * a / FPS), t0, t1, -16, "machine", "inside the truss: chain + rollers, low rumble")
    # ---- 1898: the hall, a murmuring crowd on parquet, the belt's soft drone ----
    t0, t1 = fr(HALL[0]), fr(HALL[1])
    lay(sfx, bed("walla-group-averages-discussions-s0684", ns(t1 - t0 + 0.5), lpf=5000), t0, t1, -24, "hall", "shoppers murmuring in the store")
    lay(sfx, bed("footsteps-shoe-on-parquet-s0376", ns(t1 - t0 + 0.5), lpf=6000), t0, t1, -30, "parquet", "footsteps on the parquet")
    lay(sfx, bed("escalator-2-s3065", ns(fr(652) - fr(318) + 0.5), lpf=700), fr(318), fr(652), -27, "belt", "the leather belt's low drone")
    # brandy: glasses on the tray, a clink; the queue's glasses
    lay(sfx, hit("3-glasses-on-table-s1205", 1.2, lpf=9000), fr(505), fr(505), -16, "glasses", "glasses on the silver tray", peak=True, p=0.2)
    lay(sfx, hit("cheers-small-wineglass-1-s1325", 0.6), fr(612), fr(612), -18, "clink", "two brandy glasses clink (the queue)", peak=True, p=-0.2)
    lay(sfx, hit("cheers-small-wineglass-1-s1325", 0.6), fr(636), fr(636), -20, "clink", "clink on 'free'", peak=True, p=0.25)
    # ---- the bicycle chain pops in: a freewheel ticking ----
    lay(sfx, bed("bicycle-rear-wheel-s0140", ns(1.3), lpf=7000), fr(703), fr(739), -20, "freewheel", "bicycle freewheel ticking with the chain drive")
    # ---- the kid steps off the comb ----
    lay(sfx, hit("footsteps-shoe-on-concrete-s0514", 0.5), fr(1322), fr(1322), -20, "step", "a shoe steps off onto the landing", peak=True)
    lay(sfx, hit("footsteps-shoe-on-concrete-s0514", 0.5, start=2.0), fr(1338), fr(1338), -22, "step", "second step", peak=True)
    # ---- the inspector's stopwatch ----
    lay(sfx, hit("stopwatch-1-s2137", 0.4), fr(1640), fr(1640), -18, "stopwatch", "stopwatch click", peak=True, p=0.2)
    lay(sfx, hit("stopwatch-1-s2137", 0.4), fr(1706), fr(1706), -18, "stopwatch", "stopwatch click (never slower)", peak=True, p=0.2)
    # ---- the certificate snatched away: a gust + paper flutter ----
    lay(sfx, bed("strong-wind-1-s0146", ns(1.8), lpf=3000, offset=10), fr(1804), fr(1858), -22, "gust", "a gust of wind")
    lay(sfx, hit("news-paper-manipulations-s1251", 1.2, start=3.0), fr(1807), fr(1807), -16, "paper", "the certificate flutters off", peak=True, p=0.3)
    return sfx


# ---------------------------------------------------------------- score (original): a light, curious pluck theme in C
BEAT = 60 / 104
THEME = [(0, .5, 72), (.5, .5, 76), (1, .5, 79), (1.5, .5, 76), (2, 1, 77), (3, 1, 74),
         (4, .5, 71), (4.5, .5, 74), (5, .5, 77), (5.5, .5, 74), (6, 1, 76), (7, 1, 72),
         (8, .5, 72), (8.5, .5, 76), (9, .5, 79), (9.5, .5, 81), (10, 1, 79), (11, .5, 77), (11.5, .5, 76),
         (12, .5, 74), (12.5, .5, 77), (13, .5, 76), (13.5, .5, 74), (14, 2, 72)]
ROOTS = [48, 43, 45, 48]


class Band:
    def __init__(self): self.tr = {}; self.cues = []
    def add(self, k, x, t, p=0.0):
        buf = self.tr.setdefault(k, np.zeros((2, N)))
        place(buf, pan(np.asarray(x, float), p) if np.ndim(x) == 1 else x, t)


def theme(b, t0, bars, inst, tr=0, vel=0.6, end=None):
    r = rng(int(t0 * 100) + tr)
    t = t0
    while True:
        for (bt, ln, m) in THEME:
            if bt >= bars * 4: break
            tm = t + bt * BEAT
            if end is not None and tm >= end: return
            f = F(m + tr)
            if inst == "pluck": b.add("pluck", I.pluck(f, vel * r.uniform(0.85, 1.0), r, 0.4 + ln * BEAT), tm, 0.15)
            elif inst == "vibes": b.add("vibes", I.vibes(f, vel, r, 1.4), tm, -0.1)
            elif inst == "box": b.add("box", I.musicbox(f, vel, r, 1.4), tm, 0.0)
        t += min(bars, 4) * 4 * BEAT
        if end is None: return


def bass(b, t0, end, vel=0.45):
    r = rng(int(t0 * 31)); k = 0
    while True:
        tm = t0 + k * 2 * BEAT
        if tm >= end: return
        b.add("bass", I.pluck(F(ROOTS[(k // 2) % 4] - 12), vel, r, 1.0, 0.2), tm, 0.0); k += 1


def build_score():
    b = Band()
    theme(b, 0.3, 4, "pluck", vel=0.55, end=fr(150)); bass(b, 0.3, fr(150))
    b.add("timp", I.timpani(F(36), 0.55, rng(1), 1.6), fr(155)); b.cues.append((fr(155), "soft timpani under the white flash"))
    # 1898: a music-box version of the theme in the hall
    theme(b, fr(163), 4, "box", vel=0.5, end=fr(545))
    # luckily / unluckily: a little pluck run up, then a falling one
    for k, m in enumerate([72, 76, 79, 84]): b.add("pluck", I.pluck(F(m), 0.5, rng(10 + k), 0.5), fr(551) + 0.11 * k, 0.1)
    for k, m in enumerate([79, 76, 72, 67]): b.add("pluck", I.pluck(F(m), 0.5, rng(20 + k), 0.6), fr(596) + 0.16 * k, -0.1)
    b.cues.append((fr(551), "pluck run up on 'Luckily'")); b.cues.append((fr(596), "pluck run down on 'Unluckily'"))
    theme(b, fr(604), 2, "box", vel=0.4, end=fr(648))
    # today: the theme on vibes + pluck under the whole machine explanation
    theme(b, fr(656), 4, "vibes", vel=0.45, end=fr(1930)); theme(b, fr(656) + 16 * BEAT, 4, "pluck", tr=-12, vel=0.4, end=fr(1930)); bass(b, fr(656), fr(1930), 0.4)
    # ending: the theme once more, a soft chord after the last word
    theme(b, fr(1938), 4, "pluck", vel=0.5, end=fr(2050)); theme(b, fr(1938), 4, "vibes", vel=0.35, end=fr(2050))
    for m in [60, 64, 67, 72]: b.add("vibes", I.vibes(F(m), 0.45, rng(m), 2.4), fr(2040), 0.0)
    b.cues.append((fr(2040), "soft C chord after 'feet?'"))
    BAL = {"pluck": 0, "vibes": -2, "box": -2, "bass": -6, "timp": -6}
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
        f.write("# Escalator short: sound cues (real CC0 recordings, BigSoundBank)\n\n| t (s) | layer | what | dB vs voice |\n|---|---|---|---|\n" + "\n".join(rows) + "\n\n## Music (original, synthesized)\n\n")
        f.write("\n".join(f"- {t:.2f} s: {d}" for t, d in mcues) + "\n")
    print(f"mix {DUR:.2f} s, {integrated(mix):.1f} LUFS, TP {true_peak(mix):.1f} dBTP; voice {VREF:.1f}, music {integrated(music):.1f}, sfx {integrated(sfx):.1f} LUFS")


if __name__ == "__main__":
    main()
