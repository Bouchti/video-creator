"""Sound for "The Chicken That Lived Without a Head": real CC0 recordings (BigSoundBank) laid per shot, an original quiet score
(the skill's synth instruments) ducked under the voice. Every event sits on its picture frame (src/videos/mike/
story.ts + cast.ts).

    python mike_audio.py        (from this folder) -> mix.wav (48 kHz, exact film length), stems/, cues.md

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
FPS, TOTAL = 30, 2010
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


# ---------------------------------------------------------------- picture timeline (src/videos/mike/story.ts)
FARM = [(70, 199), (269, 907), (1051, 1248), (1481, 1620)]


def gurgle_crow(sfx, f, db=-8.0, p=0.0, desc="the gurgling crow"):
    """a real rooster crow, muffled (no head!), with a wet gargle through it"""
    lay(sfx, hit("song-of-rooster-s0283", 2.3, lpf=1500), fr(f), fr(f), db, "crow", desc + " (rooster, muffled)", peak=True, p=p)
    lay(sfx, hit("gargle-1-s1652", 2.1), fr(f + 2), fr(f + 2), db - 2, "gargle", "a wet gargle through it", peak=True, p=p)


def sfx_track():
    sfx = np.zeros((2, N))
    span = lambda a, b: (fr(a), fr(b))  # noqa: E731
    for a, b in FARM:
        t0, t1 = span(a, b)
        lay(sfx, bed("henhouse-s0282", ns(t1 - t0 + 0.5), offset=a / 5), t0, t1, -30, "hens", "hens clucking around the yard")
        lay(sfx, bed("countryside-s0097", ns(t1 - t0 + 0.5), offset=a / 7), t0, t1, -32, "country", "countryside birds and breeze")
    # 1-2: the hook: the gurgling crow on frame 0, the hens squawk, feathers
    gurgle_crow(sfx, 0, -5.0, 0.1, "frame 0: the gurgling crow")
    lay(sfx, hit("hen-scared-s1040", 1.6), fr(6), fr(6), -13, "squawk", "the hens squawk in shock", peak=True, p=-0.3)
    lay(sfx, hit("flight-bird-1-s2891", 0.8), fr(3), fr(3), -16, "flap", "a flurry of feathers", peak=True, p=0.2)
    lay(sfx, bed("henhouse-s0282", ns(2.6), offset=3), fr(0), fr(70), -30, "hens", "")
    gurgle_crow(sfx, 44, -7.0, 0.0, "the gurgle, close")
    # 4: Lloyd picks Mike: a cluck, the "!" squawk
    lay(sfx, hit("annoyed-hen-s0453", 1.2), fr(150), fr(150), -16, "cluck", "a hen clucks", peak=True, p=-0.2)
    lay(sfx, hit("hen-scared-s1040", 0.8, start=2.0), fr(165), fr(165), -12, "squawk", "Mike's alarmed squawk", peak=True)
    # 5: the kitchen
    t0, t1 = span(199, 269)
    lay(sfx, bed("refrigeration-unit-s3597", ns(t1 - t0 + 0.5), lpf=1500), t0, t1, -36, "kitchen", "kitchen hum")
    lay(sfx, hit("cutlery-manipulations-on-plate-s1193", 1.2), fr(238), fr(238), -18, "cutlery", "knife and fork clinking", peak=True)
    # 6-7: the swing and the WHACK
    lay(sfx, hit("whoosh-7-s1800", 0.8), fr(364), fr(364), -15, "swing", "the axe swings down", peak=True)
    lay(sfx, hit("ax-on-wood-s0536", 0.6), fr(372), fr(372), -5, "whack", "WHACK: axe into the stump", peak=True)
    lay(sfx, hit("gavel-1-blow-s1588", 0.3), fr(372), fr(372), -9, "whack", "", peak=True)
    lay(sfx, hit("flight-bird-3-s2893", 1.0), fr(374), fr(374), -14, "feathers", "feathers burst", peak=True, p=0.2)
    lay(sfx, hit("hen-scared-s1040", 1.0, start=3.5), fr(380), fr(380), -17, "hens", "the hens scatter", peak=True, p=-0.4)
    # 9-12: morning, the peck, the gurgle
    for k, f in enumerate([508, 516, 524]): lay(sfx, hit("gavel-1-blow-s1588", 0.2, lpf=2500), fr(f), fr(f), -22, "peck", "beak-less pecks on the ground" if k == 0 else "", peak=True, p=-0.1)
    gurgle_crow(sfx, 536, -9.0, -0.1)
    # 14-15: the diagrams pop in, the check, the clot plop, three dings for the icons
    lay(sfx, hit("door-knock-s0095", 0.2, lpf=1500), fr(664), fr(664), -20, "pop", "the diagram pops up", peak=True)
    lay(sfx, hit("small-bell-s0010", 0.8), fr(684), fr(684), -21, "ding", "the vein is spared: a ding", peak=True, p=0.2)
    lay(sfx, hit("splash-small-1-s1529@0.7", 0.6), fr(735), fr(735), -18, "plop", "the clot plugs the cut", peak=True)
    for f in (842, 867, 884): lay(sfx, hit("small-bell-s0010", 0.7), fr(f), fr(f), -21, "ding", "an icon lights up", peak=True, p=0.3)
    # 16: the computer: fan, the plug pulled, the screen dies, the fan keeps going
    t0, t1 = span(907, 1051)
    lay(sfx, bed("computer-2-ventilation-s0126", ns(t1 - t0 + 0.5)), t0, t1, -26, "fan", "the computer's fan whirring on")
    lay(sfx, hit("click-seatbelt-s0656", 0.4), fr(916), fr(916), -14, "unplug", "the plug pulled out", peak=True)
    lay(sfx, hit("whoosh-7-s1800@0.5", 0.6), fr(984), fr(984), -18, "crt", "the screen powers down", peak=True)
    # 17-18: milk drops; the scale's needle and a ding at eight
    for k in range(4): lay(sfx, hit("drops-of-water-1-s1384", 0.3, start=0.3 + k * 0.5), fr(1104 + k * 8), fr(1104 + k * 8), -18, "drops", "milk drops down the neck" if k == 0 else "", peak=True)
    lay(sfx, hit("small-ratchet-s0794", 1.3), fr(1189), fr(1189), -19, "needle", "the scale's needle swinging up", peak=True)
    lay(sfx, hit("small-bell-s0010", 1.0), fr(1228), fr(1228), -16, "ding", "ding: almost eight pounds", peak=True)
    # 19-22: the sideshow: fairground, crowd, coins, flashbulbs, cash
    t0, t1 = span(1248, 1481)
    lay(sfx, bed("pinball-and-arcade-show-ambience-1-s3599", ns(t1 - t0 + 0.5), lpf=5000, offset=12), t0, t1, -30, "fair", "sideshow ambience")
    lay(sfx, bed("crowd-of-50-60-people-2-s3516", ns(t1 - t0 + 0.5), lpf=4000, offset=40), t0, t1, -29, "crowd", "the crowd at the tent")
    lay(sfx, hit("coins-1-s0193", 0.8), fr(1293), fr(1293), -15, "coins", "a quarter for the ticket", peak=True)
    for f in (1378, 1392): lay(sfx, hit("trigger-of-camera-1-s2394", 0.5), fr(f), fr(f), -13, "flash", "the photographer's flashbulb", peak=True, p=0.3)
    lay(sfx, hit("coins-2-s0194", 1.2), fr(1421), fr(1421), -14, "cash", "money, money", peak=True)
    lay(sfx, hit("news-paper-manipulations-s1251", 1.0, start=2.0), fr(1410), fr(1410), -20, "bills", "bills fluttering", peak=True)
    # 23-24: the copycats: chickens fleeing, a deflated end
    lay(sfx, hit("hen-scared-s1040", 2.5), fr(1485), fr(1485), -13, "flee", "chickens running for their lives", peak=True)
    lay(sfx, hit("running-in-the-tall-grass-s1843", 2.2, start=4.0), fr(1484), fr(1550), -22, "run", "farmers running")
    # 25-27: the motel at night: crickets, the cough, the syringe on the dark stage, the facepalm
    t0, t1 = span(1620, 1776)
    lay(sfx, bed("campaign-at-night-1-s0110", ns(t1 - t0 + 0.5)), t0, t1, -30, "night", "night crickets")
    lay(sfx, bed("stopwatch-1-s2137", ns(fr(1691) - fr(1620) + 0.5), lpf=2500), fr(1620), fr(1691), -32, "clock", "the motel clock")
    lay(sfx, hit("gargle-3-s1654@0.8", 1.6), fr(1668), fr(1668), -14, "choke", "Mike choking (a gargle)", peak=True)
    lay(sfx, hit("door-knock-s0095", 0.15, lpf=2500), fr(1745), fr(1745), -18, "slap", "Lloyd's facepalm", peak=True)
    # 28: the festival
    t0, t1 = span(1776, 1907)
    lay(sfx, bed("cheerful-street-s2372", ns(t1 - t0 + 0.5), lpf=5000), t0, t1, -28, "street", "a busy festival street")
    lay(sfx, hit("applause-1-s2363", 2.0, lpf=5000), fr(1869), fr(1869), -18, "cheer", "the crowd cheers", peak=True)
    lay(sfx, hit("annoyed-hen-s0453", 1.0), fr(1820), fr(1820), -20, "cluck", "chickens in the crowd", peak=True, p=-0.3)
    # 29: dinner: the walk across the table
    t0, t1 = span(1907, TOTAL)
    lay(sfx, bed("refrigeration-unit-s3597", ns(t1 - t0 + 0.5), lpf=1500), t0, t1, -36, "kitchen", "kitchen hum")
    for k, f in enumerate(range(1932, 1990, 8)): lay(sfx, hit("gavel-1-blow-s1588", 0.2, lpf=1800), fr(f), fr(f), -21, "steps", "claws tapping across the table" if k == 0 else "", peak=True, p=-0.4 + k * 0.12)
    return sfx


# ---------------------------------------------------------------- score (original): a cheeky country two-step in G
BPM = 120
BEAT = 60 / BPM
BAR = 4 * BEAT
MEL = [(0, .5, 74), (.5, .5, 71), (1, .5, 74), (1.5, .5, 76), (2, 1, 79), (3, .5, 76), (3.5, .5, 74),
       (4, .5, 72), (4.5, .5, 74), (5, .5, 76), (5.5, .5, 72), (6, 1, 71), (7, 1, 67),
       (8, .5, 69), (8.5, .5, 71), (9, .5, 72), (9.5, .5, 74), (10, 1, 76), (11, .5, 74), (11.5, .5, 72),
       (12, .5, 71), (12.5, .5, 72), (13, .5, 74), (13.5, .5, 69), (14, 2, 67)]
CHORDS = [(43, [59, 62, 67]), (48, [60, 64, 67]), (50, [57, 62, 66]), (43, [59, 62, 67])]


class Band:
    def __init__(self): self.tr = {}; self.cues = []
    def add(self, k, x, t, p=0.0):
        buf = self.tr.setdefault(k, np.zeros((2, N)))
        place(buf, pan(np.asarray(x, float), p) if np.ndim(x) == 1 else x, t)


def twostep(b, t0, t1, mel=True, vel=0.5, drums=True):
    """boom-chick: plucked bass on 1 and 3 (root, fifth), banjo-ish strum on 2 and 4, brushes; a whistle-bright melody"""
    r = rng(int(t0 * 100))
    k = 0
    while True:
        tb = t0 + k * BAR
        if tb >= t1 - 0.05: break
        root, ch = CHORDS[k % 4]
        for j in range(4):
            tj = tb + j * BEAT
            if tj >= t1: break
            if j % 2 == 0: b.add("bass", I.pluck(F(root + (0 if j == 0 else 7)), vel * 0.9, r, 0.5, 0.3), tj, 0.0)
            else:
                for n, m in enumerate(ch): b.add("banjo", I.pluck(F(m + 12), vel * 0.28, r, 0.25, 0.85), tj + n * 0.01, 0.2)
            if drums: b.add("brush", I.brush(vel * (0.55 if j % 2 else 0.3), r), tj, -0.2)
        k += 1
    if mel:
        tm0 = t0
        while tm0 < t1:
            for (bt, ln, m) in MEL:
                tm = tm0 + bt * BEAT
                if tm + ln * BEAT > t1 + 0.05: break
                b.add("mel", I.glock(F(m), vel * 0.55, r, dur=ln * BEAT + 0.5), tm, 0.05)
            tm0 += 16 * BEAT


def build_score():
    b = Band()
    b.add("timp", I.timpani(F(43), 0.6, rng(1), 1.6), fr(68)); b.cues.append((fr(68), "a timpani hit on the white flash into the story"))
    twostep(b, fr(70), fr(369) - 0.05); b.cues.append((fr(70), "the country two-step starts"))
    b.cues.append((fr(370), "music cut for the WHACK"))
    twostep(b, fr(390), fr(592) - 0.05, vel=0.5)
    b.cues.append((fr(592), "silence under 'Wait. How is that even possible?'"))
    twostep(b, fr(661), fr(1620) - 0.05, vel=0.45)
    for m in [55, 59, 62]: b.add("pad", I.pad([F(m)], 3.0, 0.32, rng(m), att=0.6, rel=1.0, warm=1400), fr(1625), 0.0)
    for m in [52, 55, 59]: b.add("pad", I.pad([F(m)], 3.0, 0.32, rng(m + 1), att=0.6, rel=1.0, warm=1400), fr(1700), 0.0)
    b.cues.append((fr(1620), "soft sad chords for the motel and the syringe"))
    twostep(b, fr(1776), fr(1985), vel=0.55); b.cues.append((fr(1776), "the tune returns for the festival"))
    for m in [43, 55, 59, 62, 67]: b.add("end", I.glock(F(m + 12), 0.6, rng(m), dur=2.4), fr(1985), 0.0)
    b.add("bass", I.pluck(F(43), 0.9, rng(9), 1.6, 0.3), fr(1985))
    b.add("timp", I.cymbal(0.3, rng(3), 2.0), fr(1985)); b.cues.append((fr(1985), "final G chord after 'neck'"))
    BAL = {"mel": -2, "banjo": -5, "bass": -3, "brush": -10, "timp": -8, "end": -2, "pad": -6}
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
        f.write("# Mike short: sound cues (real CC0 recordings, BigSoundBank)\n\n| t (s) | layer | what | dB vs voice |\n|---|---|---|---|\n" + "\n".join(rows) + "\n\n## Music (original, synthesized)\n\n")
        f.write("\n".join(f"- {t:.2f} s: {d}" for t, d in mcues) + "\n")
    print(f"mix {DUR:.2f} s, {integrated(mix):.1f} LUFS, TP {true_peak(mix):.1f} dBTP; voice {VREF:.1f}, music {integrated(music):.1f}, sfx {integrated(sfx):.1f} LUFS")


if __name__ == "__main__":
    main()
