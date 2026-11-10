"""Sound for "The chip in your phone": real CC0 recordings (BigSoundBank) laid per shot, an original quiet score
(the skill's synth instruments) ducked under the voice. Every event sits on its picture frame (src/videos/chip/
story.ts + cast.ts).

    python chip_audio.py        (from this folder) -> mix.wav (48 kHz, exact film length), stems/, cues.md

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
FPS, TOTAL = 30, 2240
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


# ---------------------------------------------------------------- picture timeline (src/videos/chip/story.ts)
STREET = [(0, 40), (692, 763), (2011, 2116)]
BAY = [(40, 186), (968, 1752)]                 # yellow rooms: ventilation
MACHINE = [(40, 186), (1338, 1752)]            # next to / inside the scanner
LAB = (186, 516)
KITCH = (516, 692)
CITY = [(763, 839), (2116, TOTAL)]
BEACH = (839, 968)
MIRROR = (1752, 1878)
JETS = (1878, 2011)
FLASHES = [455, 468, 482, 497, 509]


def sfx_track():
    sfx = np.zeros((2, N))
    span = lambda a, b: (fr(a), fr(b))  # noqa: E731
    for a, b in STREET:
        t0, t1 = span(a, b)
        lay(sfx, bed("cheerful-street-s2372", ns(t1 - t0 + 0.5), lpf=6000, offset=a / 7), t0, t1, -27, "street", "town street ambience (no words)")
    for a, b in BAY:
        t0, t1 = span(a, b)
        lay(sfx, bed("ventilation-5-s3598", ns(t1 - t0 + 0.5), lpf=5000, offset=a / 9), t0, t1, -25, "cleanroom air", "the fan-filter ceiling blowing clean air")
    for a, b in MACHINE:
        t0, t1 = span(a, b)
        lay(sfx, bed("refrigeration-unit-s3597", ns(t1 - t0 + 0.5), lpf=2600, offset=a / 11), t0, t1, -20, "scanner hum", "the scanner's pumps and chillers")
    # the hook: the 50,000-a-second stream as a crackle under strobe zaps
    lay(sfx, bed("long-welding-1-s0950", ns(fr(118) - fr(40) + 0.5), lpf=5000), fr(40), fr(118), -21, "plasma crackle", "the tin stream being blasted (continuous)")
    for f in range(52, 118, 18):
        lay(sfx, hit("short-welds-s0952", 0.25, lpf=7000, start=0.4 + (f % 5) * 0.7), fr(f), fr(f), -19, "zap", "a drop is blasted", peak=True, p=-0.15)
    # 1947: a quiet lab, a typewriter down the hall, the radio tubes humming
    t0, t1 = span(*LAB)
    lay(sfx, bed("computer-2-ventilation-s0126", ns(t1 - t0 + 0.5), lpf=1800), t0, t1, -31, "lab room", "a 1940s lab room tone")
    lay(sfx, bed("typewriter-8-s2841", ns(t1 - t0 + 0.5), lpf=2600), t0, t1, -33, "typewriter", "a typewriter down the hall")
    lay(sfx, bed("crackling-radio-1-s0312", ns(t1 - t0 + 0.5), lpf=3000, hpf=300), t0, t1, -36, "tubes", "warm crackle from the valve radio")
    # the press: shutters + flashes, a little applause
    for k, f in enumerate(FLASHES):
        for i in range(3):
            lay(sfx, hit("trigger-of-camera-1-s2394", 0.3), fr(f + i * 3), fr(f + i * 3), -17 - 2 * i, "shutter", "press camera shutter", peak=True, p=-0.3 + 0.3 * i)
    lay(sfx, hit("applause-1-s2363", 2.2), fr(452), fr(516), -27, "applause", "a few people clapping at the press day")
    # 1948: the page turns, breakfast, the radio
    lay(sfx, hit("news-paper-manipulations-s1251", 1.0, start=1.0), fr(512), fr(512), -15, "page", "the newspaper is opened", peak=True, p=0.1)
    lay(sfx, hit("news-paper-manipulations-s1251", 0.8, start=5.0), fr(555), fr(555), -18, "page", "a page turns", peak=True, p=-0.1)
    t0, t1 = span(558, 692)
    lay(sfx, bed("spoon-into-a-mug-of-coffee-s0410", ns(t1 - t0 + 0.5)), t0, t1, -30, "breakfast", "a spoon stirring coffee")
    lay(sfx, bed("crackling-radio-1-s0312", ns(fr(692) - fr(640) + 0.5), lpf=4500), fr(640), fr(692), -24, "radio", "the kitchen radio on the counter")
    # today: the city of switches hums
    for a, b in CITY:
        t0, t1 = span(a, b)
        lay(sfx, bed("computer-2-ventilation-s0126", ns(t1 - t0 + 0.5), lpf=4000, offset=a / 5), t0, t1, -25, "chip hum", "the electric hum of the chip")
    # the beach
    t0, t1 = span(*BEACH)
    lay(sfx, bed("sea-waves-and-seagulls-s0267", ns(t1 - t0 + 0.5), lpf=7000), t0, t1, -20, "beach", "waves and gulls")
    # the crystal furnace roar, the wafer's ting
    lay(sfx, bed("log-wood-boiler-s1120", ns(fr(1034) - fr(968) + 0.5), lpf=1600), fr(968), fr(1034), -20, "furnace", "the crystal furnace roaring")
    lay(sfx, hit("cheers-small-wineglass-1-s1325", 0.6), fr(1059), fr(1059), -20, "ting", "the shiny wafer catches the light", peak=True, p=0.2)
    lay(sfx, hit("trigger-of-camera-1-s2394", 0.3), fr(1118), fr(1118), -18, "lamp", "the exposure lamp clicks on", peak=True)
    # the blast: pre-pulse, main pulse, plasma glow
    lay(sfx, hit("short-welds-s0952", 0.18, lpf=8000, start=1.2), fr(1511), fr(1511), -18, "pre-pulse", "the first laser pulse flattens the drop", peak=True)
    lay(sfx, hit("short-welds-s0952", 0.5, start=2.4), fr(1555), fr(1555), -11, "blast", "the main laser blast", peak=True)
    lay(sfx, bed("long-welding-1-s0950", ns(fr(1643) - fr(1556) + 0.5), lpf=6000, offset=3), fr(1556), fr(1643), -18, "plasma", "the plasma crackling")
    lay(sfx, bed("long-welding-1-s0950", ns(fr(1752) - fr(1643) + 0.5), lpf=2200, offset=9), fr(1643), fr(1752), -27, "source", "the source pulsing inside the vacuum")
    # the mirror land: wind over the fields
    t0, t1 = span(*MIRROR)
    lay(sfx, bed("strong-wind-1-s0146", ns(t1 - t0 + 0.5), lpf=1400, offset=4), t0, t1, -29, "wind", "a breeze over the countryside")
    # the jets
    lay(sfx, hit("airplane-pass-1-s3004", 6.0, start=0.5), fr(1878), fr(2011), -15, "jet", "a big jet passing", p=-0.2)
    lay(sfx, hit("airplane-pass-5-s3008", 5.5, start=0.5), fr(1950), fr(2011), -17, "jet 2", "the other jets", p=0.25)
    # the queue at the one factory
    lay(sfx, bed("walla-group-averages-discussions-s0684", ns(fr(2065) - fr(2011) + 0.5), lpf=4000), fr(2011), fr(2065), -25, "queue", "a queue murmuring")
    # the tap and the flip
    lay(sfx, hit("iphone-touch-sound-2-s2038", 0.3), fr(2090), fr(2090), -14, "tap", "a tap on the screen", peak=True)
    for k in range(10):
        lay(sfx, hit("iphone-touch-sound-2-s2038", 0.3), fr(2150 + k * 2.5), fr(2150 + k * 2.5), -20 - k, "flip", "switches flipping", peak=True, p=(k % 3 - 1) * 0.4)
    return sfx


# ---------------------------------------------------------------- score (original): a curious, bright pluck theme in D
BEAT = 60 / 100
THEME = [(0, .5, 74), (.5, .5, 78), (1, .5, 81), (1.5, .5, 83), (2, 1, 81), (3, 1, 78),
         (4, .5, 76), (4.5, .5, 79), (5, .5, 83), (5.5, .5, 81), (6, 1, 79), (7, 1, 76),
         (8, .5, 74), (8.5, .5, 78), (9, .5, 81), (9.5, .5, 86), (10, 1, 83), (11, .5, 81), (11.5, .5, 79),
         (12, .5, 78), (12.5, .5, 76), (13, .5, 78), (13.5, .5, 79), (14, 2, 74)]
ROOTS = [50, 47, 43, 45]


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
    theme(b, 0.2, 4, "pluck", vel=0.55, end=fr(180)); bass(b, 0.2, fr(180))
    b.add("timp", I.timpani(F(38), 0.55, rng(1), 1.6), fr(182)); b.cues.append((fr(182), "soft timpani under the white flash"))
    # 1947-48: the theme on a music box
    theme(b, fr(190), 4, "box", vel=0.5, end=fr(556))
    for k, m in enumerate([74, 78, 81, 86]): b.add("pluck", I.pluck(F(m), 0.5, rng(10 + k), 0.5), fr(561) + 0.11 * k, 0.1)
    for k, m in enumerate([81, 78, 74, 69]): b.add("pluck", I.pluck(F(m), 0.5, rng(20 + k), 0.6), fr(622) + 0.16 * k, -0.1)
    b.cues.append((fr(561), "pluck run up on 'Luckily'")); b.cues.append((fr(622), "pluck run down on 'Unluckily'"))
    theme(b, fr(630), 2, "box", vel=0.4, end=fr(688))
    # today: vibes + pluck under the whole making-of
    theme(b, fr(694), 4, "vibes", vel=0.45, end=fr(2060)); theme(b, fr(694) + 16 * BEAT, 4, "pluck", tr=-12, vel=0.4, end=fr(2060)); bass(b, fr(694), fr(2060), 0.4)
    b.add("timp", I.timpani(F(38), 0.45, rng(2), 1.4), fr(1555)); b.cues.append((fr(1555), "timpani under the blast"))
    # ending: the theme once more, a chord after the last word
    theme(b, fr(2068), 4, "pluck", vel=0.5, end=fr(2205)); theme(b, fr(2068), 4, "vibes", vel=0.35, end=fr(2205))
    for m in [62, 66, 69, 74]: b.add("vibes", I.vibes(F(m), 0.45, rng(m), 2.4), fr(2208), 0.0)
    b.cues.append((fr(2208), "soft D chord after 'today?'"))
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
        f.write("# Chip short: sound cues (real CC0 recordings, BigSoundBank)\n\n| t (s) | layer | what | dB vs voice |\n|---|---|---|---|\n" + "\n".join(rows) + "\n\n## Music (original, synthesized)\n\n")
        f.write("\n".join(f"- {t:.2f} s: {d}" for t, d in mcues) + "\n")
    print(f"mix {DUR:.2f} s, {integrated(mix):.1f} LUFS, TP {true_peak(mix):.1f} dBTP; voice {VREF:.1f}, music {integrated(music):.1f}, sfx {integrated(sfx):.1f} LUFS")


if __name__ == "__main__":
    main()
