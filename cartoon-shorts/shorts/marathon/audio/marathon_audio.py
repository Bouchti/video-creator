"""Sound for "The Olympic Marathon Won by Car" (St. Louis, 1904): real CC0 recordings (BigSoundBank) laid per shot, an
original score (the skill's synth instruments: a 1904 World's-Fair cakewalk in F with a tuba oom-pah, different from
the molasses ragtime) ducked under the voice. Every event sits on its picture frame (src/videos/marathon/story.ts + cast.ts).

    python marathon_audio.py   (from this folder) -> mix.wav (48 kHz, exact film length), stems/, cues.md

Rules from the user's feedback: real recordings matched to what is on screen, beds crossfade across cuts, calm music
~-22 dB under the voice; the hook opens on a hit (horn + engine on frame 0).
"""
import json, os, subprocess
import numpy as np
from dsp import SR, ns, rng, hp, dbg, pan, place, read_wav, write_wav, integrated, true_peak
import instruments as I

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", "assets", "cc0", "sfx", "bigsoundbank"))
FFMPEG = "ffmpeg"
FPS, TOTAL = 30, 2130
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


def sfx_track():
    sfx = np.zeros((2, N))
    B = lambda name, a, b, db, desc="", lpf=None, off=0.0, p=0.0: lay(sfx, bed(name, ns(fr(b) - fr(a) + 0.6), lpf=lpf, offset=off), fr(a), fr(b), db, name.split("-s")[0], desc, p=p)  # noqa: E731
    H = lambda name, f, db, desc="", sec=1.5, lpf=None, start=None, p=0.0: lay(sfx, hit(name, sec, lpf=lpf, start=start), fr(f), fr(f), db, name.split("-s")[0], desc, peak=True, p=p)  # noqa: E731
    country = lambda a, b, db=-30, off=0.0: (B("countryside-s0097", a, b, db, "country air", lpf=6000, off=off), B("cicadas-s3002", a, b, db - 4, "summer heat", lpf=7000, off=off))  # noqa: E731
    steps = lambda a, b, db=-24, off=0.0, desc="runners' feet on the dirt": B("steps-on-gravels-s0510@1.25", a, b, db, desc, lpf=4000, off=off)  # noqa: E731
    # 1: the hook: the honk on frame 0, the old engine chugging, dust wind, runners coughing
    H("oogah-horn-3-s2542@1.25", 0, -6, "frame 0: the car's honk", sec=1.2)
    H("oogah-horn-3-s2542@1.3", 24, -9, "a second honk", sec=0.8)
    B("motor-car-1-s0290", 0, 96, -6, "the 1904 engine chugging", lpf=3500)
    B("strong-wind-1-s0146", 0, 96, -20, "the dust cloud", lpf=1800)
    steps(0, 96, -22)
    for f, nm in [(8, "man-cough-1-s0488"), (30, "man-cough-3-s2181"), (52, "man-cough-2-s1657")]: H(nm, f, -14, "runners coughing in the dust" if f == 8 else "", sec=1.2, p=-0.3)
    H("breathless-man-s1103", 40, -18, "a runner gasping", sec=2.0, p=-0.3)
    # 2-4: the heat; the well; the clipboard
    country(92, 390)
    steps(92, 236, -26, 4)
    H("small-bell-s0010", 100, -20, "ST. LOUIS 1904 tag", sec=0.8)
    H("small-ratchet-s0794", 140, -17, "the thermometer shooting to 90", sec=1.2)
    H("breathless-man-s1103", 180, -22, "", sec=2.5, p=0.3)
    H("metal-bucket-s0543", 262, -20, "the well's tin bucket", sec=0.6, p=-0.2)
    H("drops-of-water-2-s1385", 273, -18, "one drop of water", sec=0.6)
    H("small-bell-s0010", 300, -17, "'on purpose' ding", sec=0.8)
    H("pencil-signature-1-s3236", 345, -16, "the clipboard scribble", sec=1.4)
    # 5: the officials' car: engine, dust, coughs
    B("motor-car-1-s0290", 390, 510, -10, "the officials' car", lpf=3000, off=6)
    B("strong-wind-1-s0146", 390, 510, -16, "the dust", lpf=1600, off=4)
    steps(390, 510, -24, 9)
    for f, nm in [(455, "man-cough-2-s1657"), (466, "man-cough-1-s0488"), (480, "man-cough-3-s2181"), (494, "man-cough-1-s0488")]: H(nm, f, -13, "everyone coughing" if f == 455 else "", sec=1.2, p=0.25 if f % 2 else -0.25)
    # 6-8: the cramp; the ride; the breakdown
    country(508, 800, -32, 7)
    steps(508, 690, -25, 12)
    H("whoosh-7-s1800@1.4", 571, -18, "'OUCH!' hop", sec=0.6)
    B("motor-car-1-s0290", 594, 690, -9, "Lorz's car pulls away", lpf=3500, off=11)
    H("oogah-horn-3-s2542@1.25", 632, -9, "honk as he waves", sec=1.0)
    H("car-difficult-start-s0872", 694, -12, "the engine sputtering", sec=1.4)
    H("explosion-far-away-s1023@1.3", 730, -8, "BANG: the car breaks down", sec=1.2)
    H("hiss-of-steam-train-6-s3017", 733, -15, "steam hissing from the radiator", sec=2.5, lpf=5000)
    H("car-door-3-s1524", 765, -16, "Lorz hops out", sec=0.8)
    steps(772, 800, -22, 20)
    # 9-11: the stadium: crowd, applause, flashbulbs; the shout and the gasp
    B("crowd-of-50-60-people-1-s3515", 800, 1055, -24, "the stadium crowd", lpf=5000)
    H("whoosh-7-s1800", 824, -16, "breaking the tape", sec=0.6)
    B("applause-about-25-50-people-1-s0812", 832, 900, -14, "the crowd goes wild")
    B("shouts-and-applauses-of-teens-1-s0236", 860, 900, -18, "cheering", lpf=6000)
    for f in (866, 870, 874, 878): H("trigger-of-camera-1-s2394", f, -18, "flashbulbs" if f == 866 else "", sec=0.4, p=0.3)
    H("small-bell-s0010", 925, -18, "the wreath lands", sec=0.8)
    H("small-bell-s0010@1.5", 960, -18, "the gold medal glints", sec=0.8)
    H("rattle-s0923", 1021, -16, "record-stop on 'car!'", sec=0.4)
    B("walla-group-averages-discussions-s0684", 1024, 1055, -22, "the crowd gasps and murmurs", lpf=3500)
    H("whoosh-7-s1800@1.3", 1033, -15, "the medal snatched back", sec=0.5)
    # 12-14: Hicks: heavy breathing; the bottles; gulp; the hallucination giggles
    country(1055, 1352, -32, 15)
    H("breathless-man-s1103", 1060, -16, "Hicks wheezing", sec=3.5)
    H("breathless-man-s1103", 1110, -18, "", sec=2.5, start=3.0)
    H("glass-placed-on-table-s1204", 1189, -16, "the rat poison bottle", sec=0.6)
    H("spoon-into-a-mug-of-coffee-s0410", 1224, -18, "egg whites stirred in", sec=0.8)
    H("glass-of-water-filling-1-s1242", 1257, -18, "a shot of brandy poured", sec=1.0)
    H("gargle-1-s1652", 1270, -15, "Hicks gulps it down", sec=0.9)
    H("gargle-3-s1654", 1286, -15, "another dose", sec=0.9)
    H("whoosh-7-s1800@0.8", 1296, -14, "the shudder", sec=0.6)
    H("delirious-laughter-12-s2102", 1318, -22, "Hicks giggling at a waving egg", sec=2.2)
    # 15: carried over the line
    B("crowd-of-50-60-people-2-s3516", 1352, 1452, -22, "the crowd", lpf=5000)
    B("applause-1-s2363", 1384, 1452, -18, "applause as he is carried over")
    steps(1352, 1452, -20, 30, "the trainers' feet")
    # 16-19: Carvajal
    country(1452, 1770, -31, 22)
    H("small-bell-s0010", 1455, -19, "4TH PLACE tag", sec=0.8)
    H("great-page-that-turns-1-s0362", 1481, -18, "an envelope flap", sec=0.6)
    H("flight-bird-1-s2891@1.8", 1536, -20, "a moth flutters out of the empty pocket", sec=0.8)
    for k, f in enumerate([1592, 1600, 1608]): H("scissors-s0008", f, -13, "scissors cutting his trousers" if k == 0 else "", sec=0.4, start=0.3 + 0.35 * k)
    H("whoosh-7-s1800@1.5", 1630, -16, "two peaches snatched", sec=0.5)
    H("apple-crunched-1-s1113", 1655, -12, "crunching a rotten apple", sec=0.8)
    H("apple-crunched-1-s1113", 1668, -14, "", sec=0.6, start=1.5)
    B("man-snoring-s0170", 1704, 1770, -14, "Carvajal snoring in the orchard")
    H("small-bell-s0010@0.9", 1745, -16, "'STILL 4TH!' tag", sec=0.9)
    # 20: the dog
    B("running-in-the-tall-grass-s1843", 1770, 1848, -18, "running through the field", lpf=5000)
    for f in (1789, 1806, 1824): H("barking-dog-2-s2954", f, -10, "the dog barking at his heels" if f == 1789 else "", sec=0.9, start=None if f == 1789 else 0.6 * (f % 3), p=0.25)
    # 21: banned for life... six months
    B("walla-group-averages-discussions-s0684", 1848, 1975, -32, "an empty stadium murmur", lpf=2500, off=20)
    H("gavel-1-blow-s1588", 1886, -6, "the BANNED FOR LIFE stamp slams", sec=0.6)
    H("great-page-that-turns-1-s0362", 1945, -16, "the 6 MONTHS calendar", sec=0.8)
    H("pencil-signature-1-s3236", 1950, -16, "FOR LIFE crossed out", sec=1.0, start=0.4)
    # 22-23: Boston 1905; on foot past the car
    B("cheerful-street-s2372", 1975, 2130, -28, "a city street", lpf=5000)
    B("crowd-of-50-60-people-2-s3516", 1975, 2040, -22, "the Boston crowd", lpf=5000, off=10)
    B("applause-about-25-50-people-1-s0812", 2000, 2045, -16, "he wins: applause", off=4)
    H("whoosh-7-s1800", 2001, -16, "breaking the tape", sec=0.6)
    steps(2040, 2120, -22, 40, "jogging on foot")
    H("oogah-horn-3-s2542@1.35", 2072, -12, "the parked car honks at him", sec=0.9)
    # v2 (reference Short): a real whoosh on every whip pan, peaking on the cut (story.ts WHIPS), panned with the swing
    WH = ["whoosh-3-s1795", "whoosh-4-s1796", "whoosh-7-s1800", "whoosh-8-s1801", "whoosh-5-s1797", "whoosh-6-s1799"]
    for i, at in enumerate([236, 390, 508, 594, 690, 800, 890, 993, 1031, 1055, 1178, 1352, 1452, 1624, 1652, 1704, 1770, 1848, 1975, 2040]):
        H(WH[i % len(WH)], at - 4, -11, "whip-pan whoosh" if i == 0 else "", sec=0.9, p=0.35 if i % 2 == 0 else -0.35)
    return sfx


# ---------------------------------------------------------------- score (original): a 1904 World's-Fair cakewalk in F
BPM = 126
BEAT = 60 / BPM
BAR = 4 * BEAT
MEL = [(0, .5, 72), (.5, .25, 74), (.75, .75, 76), (1.5, .5, 77), (2, .5, 76), (2.5, .5, 72), (3, 1, 69),
       (4, .5, 70), (4.5, .25, 72), (4.75, .75, 74), (5.5, .5, 76), (6, .5, 74), (6.5, .5, 70), (7, 1, 67),
       (8, .5, 72), (8.5, .25, 74), (8.75, .75, 76), (9.5, .5, 77), (10, .5, 81), (10.5, .5, 79), (11, 1, 77),
       (12, .5, 76), (12.5, .5, 74), (13, .5, 72), (13.5, .5, 67), (14, 2, 65)]
CHORDS = [(41, [65, 69, 72]), (46, [65, 70, 74]), (36, [64, 67, 70]), (41, [65, 69, 72])]
# the woozy Hicks section: the same tune in F minor, slower, a semitone sag
MEL_M = [(b, l, m - (1 if m % 12 in (9, 2) else 0)) for b, l, m in MEL]
CHORDS_M = [(41, [65, 68, 72]), (46, [65, 70, 73]), (36, [64, 67, 70]), (41, [65, 68, 72])]


class Band:
    def __init__(self): self.tr = {}; self.cues = []
    def add(self, k, x, t, p=0.0):
        buf = self.tr.setdefault(k, np.zeros((2, N)))
        place(buf, pan(np.asarray(x, float), p) if np.ndim(x) == 1 else x, t)


def cakewalk(b, t0, t1, mel=True, vel=0.5, minor=False, beat=BEAT, sag=0.0):
    """tuba oom-pah (root on 1, fifth on 3), plucked banjo-piano chords on 2 and 4, snare brushes, a glock-and-pluck tune"""
    r = rng(int(t0 * 100))
    chords, melody = (CHORDS_M, MEL_M) if minor else (CHORDS, MEL)
    bar = 4 * beat
    k = 0
    while True:
        tb = t0 + k * bar
        if tb >= t1 - 0.05: break
        root, ch = chords[k % 4]
        for j in range(4):
            tj = tb + j * beat
            if tj >= t1: break
            if j % 2 == 0: b.add("tuba", I.brass(F(root - 12 + (0 if j == 0 else 7)) * (1 + sag * np.sin(tj)), 0.32, vel * 0.8, r, kind="tuba"), tj, 0.0)
            else:
                for n, m in enumerate(ch): b.add("chord", I.pluck(F(m - 12), vel * 0.3, r, 0.22, 0.75), tj + n * 0.01, 0.2)
            b.add("brush", I.snare(vel * (0.35 if j % 2 else 0.18), r, 0.18), tj, -0.2)
        k += 1
    if mel:
        tm0 = t0
        while tm0 < t1:
            for (bt, ln, m) in melody:
                tm = tm0 + bt * beat
                if tm + ln * beat > t1 + 0.05: break
                b.add("mel", I.pluck(F(m), vel * 0.55, r, ln * beat + 0.3, 0.85), tm, 0.05)
                if not minor and bt % 4 == 0: b.add("glock", I.glock(F(m + 12), vel * 0.25, r, dur=0.8), tm, -0.1)
            tm0 += 16 * beat


def build_score():
    b = Band()
    # the hook is engine + horn; a timpani and cymbal on the flash into the story, then the cakewalk
    b.add("timp", I.timpani(F(41), 0.7, rng(1), 2.0), fr(92)); b.add("cym", I.cymbal(0.35, rng(2), 2.2), fr(92)); b.cues.append((fr(92), "timpani + cymbal on the flash"))
    cakewalk(b, fr(94), fr(1021) - 0.03, vel=0.5); b.cues.append((fr(94), "the cakewalk starts"))
    # 'he came by car!': the band stops dead; a single low tuba 'uh-oh'
    b.cues.append((fr(1021), "music stops dead on 'car!'"))
    b.add("sting", I.brass(F(36), 0.5, 0.6, rng(11), kind="tuba", fall=-2.0), fr(1028))
    # Hicks: the tune slows and sags into a woozy minor
    cakewalk(b, fr(1060), fr(1352) - 0.05, vel=0.42, minor=True, beat=60 / 104, sag=0.006); b.cues.append((fr(1060), "woozy minor cakewalk for Hicks"))
    for k, m in enumerate((84, 88, 91, 96, 91, 88)): b.add("dream", I.vibes(F(m), 0.45, rng(m), dur=1.2), fr(1318) + k * 0.12, 0.2 * (k % 2 * 2 - 1))
    b.cues.append((fr(1318), "dreamy vibes for the hallucination"))
    # carried over the line: back to major, then Carvajal
    b.add("cym", I.cymbal(0.25, rng(3), 1.6), fr(1384))
    cakewalk(b, fr(1352), fr(1884) - 0.03, vel=0.48); b.cues.append((fr(1352), "the cakewalk returns"))
    # banned for life: dead stop, a fife slide down; six months: the band kicks back in to the end, a final button
    b.cues.append((fr(1884), "music stops on 'banned'"))
    for k, m in enumerate((79, 76, 72, 67)): b.add("fife", I.fife(F(m), 0.16, 0.5, rng(20 + k)), fr(1892) + k * 0.13)
    cakewalk(b, fr(1956), fr(2068) - 0.03, vel=0.52); b.cues.append((fr(1956), "the band kicks back in on 'six months'"))
    for m in (41, 53, 60, 65): b.add("end", I.brass(F(m), 0.6, 0.6, rng(m), kind="tuba" if m < 50 else "horn"), fr(2068))
    b.add("cym", I.cymbal(0.4, rng(4), 2.4), fr(2068)); b.add("timp", I.timpani(F(41), 0.8, rng(5), 2.2), fr(2068))
    b.cues.append((fr(2068), "a big final button on 'time'"))
    BAL = {"mel": -2, "glock": -9, "chord": -6, "tuba": -3, "brush": -12, "timp": -6, "cym": -10, "sting": -2, "dream": -6, "fife": -4, "end": -2}
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
        f.write("# Marathon short: sound cues (real CC0 recordings, BigSoundBank)\n\n| t (s) | layer | what | dB vs voice |\n|---|---|---|---|\n" + "\n".join(rows) + "\n\n## Music (original, synthesized)\n\n")
        f.write("\n".join(f"- {t:.2f} s: {d}" for t, d in mcues) + "\n")
    print(f"mix {DUR:.2f} s, {integrated(mix):.1f} LUFS, TP {true_peak(mix):.1f} dBTP; voice {VREF:.1f}, music {integrated(music):.1f}, sfx {integrated(sfx):.1f} LUFS")


if __name__ == "__main__":
    main()
