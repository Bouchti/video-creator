"""Sound for "The Man Who Took a Hoover Van Hostage" (Workington, 1993): real CC0 recordings (BigSoundBank) laid per shot,
an original score (a cheeky pizzicato caper in D minor, 116 BPM, vibes tune and whistle; different from the cakewalk,
ragtime and country cues of the last shorts) ducked under the voice. Events sit on their picture frames
(src/videos/hoover/story.ts + cast.ts).

    python hoover_audio.py   (from this folder) -> mix.wav (48 kHz, exact film length), stems/, cues.md
"""
import json, os, subprocess, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "marathon", "audio"))
from dsp import SR, ns, rng, hp, lp, dbg, pan, place, read_wav, write_wav, integrated, true_peak  # noqa: E402
import instruments as I  # noqa: E402

LIB = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", "assets", "cc0", "sfx", "bigsoundbank"))
FFMPEG = "ffmpeg"
FPS, TOTAL = 30, 2040
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
    out = x.copy(); xf = SR
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
    street = lambda a, b, db=-30, off=0.0: (B("countryside-s0097", a, b, db, "suburban air", lpf=7000, off=off), B("outside-talks-2-s2969", a, b, db - 6, "distant neighbours", lpf=4000, off=off))  # noqa: E731
    crunch = lambda f, desc: (H("metal-filing-cabinet-s0773", f, -4, desc, sec=0.9), H("anvil-1-s3589@0.7", f, -10, "", sec=0.7), H("explosion-far-away-s1023@1.6", f, -12, "", sec=0.8))  # noqa: E731
    flips = lambda fs: [H("great-page-that-turns-1-s0362@1.3", f, -17, "calendar pages flipping" if i == 0 else "", sec=0.35) for i, f in enumerate(fs)]  # noqa: E731
    # 1: the hook: the lorry reversing on frame 0, CRUNCH as it boxes the van in, the horse
    B("truck-engine-2-s1443", 0, 70, -6, "frame 0: the horse truck reversing hard", lpf=5000, off=3)
    H("whoosh-6-s1799@0.8", 0, -12, "the truck swinging in", sec=0.5)
    crunch(8, "CRUNCH: the truck slams in across the drive")
    H("horse-neighing-3-s0863", 22, -10, "the horse neighs", sec=2.2)
    street(0, 185)
    # 2: thirteen days
    flips(list(range(66, 99, 3)))
    H("small-bell-s0010", 98, -16, "DAY 13 ding", sec=0.8)
    # 3: along the truck to the horse; the neighbours
    H("horse-neighing-3-s0863@1.1", 164, -6, "NEIGH! the horse pops out", sec=2.0)
    B("walla-group-averages-discussions-s0684", 120, 185, -30, "neighbours murmuring", lpf=3500)
    # 4: why? a jet overhead
    H("small-bell-s0010@0.8", 186, -18, "the question mark", sec=0.8)
    H("airplane-pass-1-s3004", 200, -9, "a jet crosses the sky", sec=3.0)
    # 5: the 1992 shop
    B("city-center-1-s2762", 255, 345, -24, "the high street", lpf=6000)
    H("small-bell-s0010", 262, -17, "BRITAIN 1992 tag", sec=0.8)
    B("supermarket-cash-registers-s0579", 345, 600, -22, "the busy electrical shop", lpf=6000)
    H("coins-1-s0193", 343, -18, "spend £100", sec=0.8)
    for k, f in enumerate((376, 382)): H("whoosh-7-s1800@1.5", f - 2, -16, "two tickets pop out" if k == 0 else "", sec=0.4); H("small-bell-s0010@1.2", f, -15, "", sec=0.6)
    H("small-bell-s0010@1.5", 428, -14, "TO AMERICA!", sec=0.8)
    H("shouts-and-applauses-of-teens-1-s0236", 405, -22, "shoppers whooping", sec=2.0)
    # 6: the scale
    H("small-ratchet-s0794", 545, -17, "the scale creaking over", sec=1.0)
    H("gavel-1-blow-s1588@0.7", 568, -4, "THUD: the tickets outweigh the vacuum", sec=0.8)
    H("explosion-far-away-s1023@1.8", 568, -14, "", sec=0.6)
    # 7: 50,000 expected; 300,000 stampede
    B("city-center-1-s2762", 596, 910, -26, "the high street", lpf=6000, off=8)
    B("walla-group-averages-discussions-s0684", 596, 676, -24, "the queue chatting", lpf=4500, off=5)
    H("small-bell-s0010", 614, -17, "EXPECTED: 50,000", sec=0.8)
    B("manifestation-s0108", 674, 716, -12, "300,000 people stampede", lpf=6000)
    B("footsteps-shoe-on-concrete-s0514@1.5", 676, 716, -14, "running feet", lpf=6000)
    H("rattle-s0923", 680, -14, "record scratch on 'three hundred thousand'", sec=0.4)
    # 8: a man and his tower of boxes
    B("footsteps-shoe-on-concrete-s0514", 716, 788, -22, "walking out with the boxes", off=4)
    H("news-paper-manipulations-s1251", 722, -20, "cardboard creak", sec=0.8)
    # 9: the small ads; boxes for sale
    H("news-paper-manipulations-s1251", 790, -16, "the newspaper opened", sec=1.0, start=1.0)
    B("typewriter-8-s2841", 796, 848, -18, "the ads filling the page")
    H("small-bell-s0010", 858, -16, "STILL IN THE BOX!", sec=0.8)
    # 10: the factory
    B("industry-workshop-s0503", 910, 968, -12, "the factory floor")
    for k, f in enumerate((918, 931, 950)): H("impact-wrench-1-s0964", f, -16, "air wrenches" if k == 0 else "", sec=0.5, p=0.3 * (1 - k))
    B("stopwatch-1-s2137@2.0", 910, 968, -20, "the clock racing")
    H("gavel-1-blow-s1588", 944, -8, "OVERTIME stamp", sec=0.6)
    # 11: the office: stamps, 14 days, the ticket
    B("slow-keyboard-s1733", 968, 1113, -30, "office typing")
    for k in range(5): H("gavel-1-blow-s1588@1.4", 990 + 14 * k, -10, "REJECTED stamps" if k == 0 else "", sec=0.4)
    H("great-page-that-turns-1-s0362", 1004, -16, "14 DAYS calendar", sec=0.6)
    H("whoosh-7-s1800@1.4", 1070, -16, "the ticket held up", sec=0.5)
    # 12-15: Dave's kitchen
    B("refrigeration-unit-s3597", 1113, 1529, -34, "kitchen fridge hum", lpf=3000)
    H("small-bell-s0010", 1116, -17, "WORKINGTON tag", sec=0.8)
    H("small-bell-s0010@1.2", 1146, -17, "DAVE DIXON tag", sec=0.8)
    H("glass-ball-bounce-1-s2240", 1185, -18, "the dream ticket", sec=0.6)
    flips(list(range(1222, 1262, 4)))
    B("stopwatch-1-s2137", 1215, 1271, -22, "the clock ticking")
    H("small-bell-s0010@0.7", 1250, -16, "NO TICKETS", sec=0.8)
    B("electric-pump-s0709@0.7", 1271, 1305, -12, "the machine shaking itself to bits", lpf=2500)
    for f in range(1278, 1302, 5): H("ax-on-wood-s0536@0.6", f, -18, "thumping" if f == 1278 else "", sec=0.3)
    H("anvil-1-s3589@0.6", 1303, -4, "KLONK: the washing machine breaks", sec=1.0)
    H("metal-bucket-s0543", 1303, -10, "", sec=0.8)
    H("splash-small-3-s1531", 1305, -12, "suds burst out", sec=0.8)
    B("water-bubbles-s0150", 1306, 1529, -30, "suds fizzing")
    H("rattle-s0923@0.7", 1512, -18, "Dave's double take", sec=0.4)
    # 16-18: the drive: the van rolls in; CRUNCH; the court order
    street(1529, 1759, -30, 9)
    B("ford-courier-engine-s0896", 1529, 1600, -9, "the Hoover van rolls up the drive", lpf=5000)
    H("click-seatbelt-s0656", 1598, -18, "handbrake", sec=0.4)
    B("truck-engine-2-s1443", 1606, 1640, -6, "the truck reversing in", lpf=5000, off=12)
    crunch(1629, "CRUNCH: boxed in")
    H("horse-neighing-3-s0863@0.95", 1650, -6, "NEIGH!", sec=2.0)
    B("footsteps-shoe-on-concrete-s0514", 1675, 1705, -20, "the bailiff walks up", off=8)
    H("news-paper-manipulations-s1251", 1709, -16, "the High Court order", sec=0.8, start=2.0)
    H("gavel-1-blow-s1588", 1722, -2, "the gavel: van released", sec=0.8)
    B("truck-engine-1-s1442", 1724, 1759, -10, "the truck pulls away", lpf=5000)
    B("ford-courier-engine-s0896", 1739, 1759, -6, "the van shoots out backwards", lpf=6000, off=6)
    H("whoosh-3-s1795", 1741, -12, "", sec=0.6)
    # 19-21: fired; 220,000 flew; sold
    B("footsteps-shoe-on-parquet-s0376", 1759, 1829, -20, "the bosses walking out")
    for k, f in enumerate((1780, 1796, 1806)): H("gavel-1-blow-s1588@1.2", f, -6, "FIRED stamps" if k == 0 else "", sec=0.5)
    H("airplane-pass-5-s3008", 1829, -4, "the jumbo roars over the rooftops", sec=3.0)
    H("shouts-and-applauses-of-teens-1-s0236", 1840, -18, "people cheering the plane", sec=1.8)
    B("industry-workshop-s0503", 1883, 1938, -24, "the factory, quieter", off=10)
    H("gavel-1-blow-s1588@0.75", 1888, -2, "BAM: SOLD", sec=0.8)
    H("explosion-far-away-s1023@1.5", 1888, -12, "", sec=0.8)
    H("small-bell-s0010", 1903, -16, "SOLD TO CANDY", sec=0.8)
    # 22: tea between the van and the truck
    street(1938, TOTAL, -30, 17)
    H("spoon-into-a-mug-of-coffee-s0410", 1946, -18, "Dave stirs his tea", sec=1.2)
    H("horse-neighing-3-s0863@1.25", 1990, -16, "the horse snickers", sec=1.4)
    # a real whoosh on every whip pan, peaking on the cut, panned with the swing
    WH = ["whoosh-3-s1795", "whoosh-4-s1796", "whoosh-7-s1800", "whoosh-8-s1801", "whoosh-5-s1797", "whoosh-6-s1799"]
    for i, at in enumerate([63, 185, 255, 345, 459, 596, 716, 788, 852, 910, 968, 1113, 1215, 1271, 1325, 1452, 1529, 1606, 1675, 1759, 1829, 1883, 1938]):
        H(WH[i % len(WH)], at - 4, -12, "whip-pan whoosh" if i == 0 else "", sec=0.9, p=0.35 if i % 2 == 0 else -0.35)
    return sfx


# ---------------------------------------------------------------- score (original): a cheeky pizzicato caper in D minor
BPM = 116
BEAT = 60 / BPM
# the tune (beats, length, midi): sneaky staccato vibes, a chromatic creep, a cheeky leap
MEL = [(0, .5, 74), (.5, .5, 77), (1, .5, 76), (1.5, .5, 74), (2, 1, 73), (3, .5, 74), (3.5, .5, 69),
       (4, .5, 70), (4.5, .5, 74), (5, .5, 72), (5.5, .5, 70), (6, 1, 69), (7, 1, 81),
       (8, .5, 74), (8.5, .5, 77), (9, .5, 76), (9.5, .5, 74), (10, .5, 73), (10.5, .5, 76), (11, 1, 79),
       (12, .5, 77), (12.5, .5, 76), (13, .5, 74), (13.5, .5, 73), (14, 2, 74)]
BASS = [38, 45, 41, 45, 34, 41, 33, 40]  # walking pizzicato roots, one per half bar (Dm, Bb, A)
MAJ = lambda m: m + (1 if m % 12 in (5, 10) else 0)  # D minor -> D major (F -> F#, Bb -> B) for the payoff  # noqa: E731


class Band:
    def __init__(self): self.tr = {}; self.cues = []
    def add(self, k, x, t, p=0.0):
        buf = self.tr.setdefault(k, np.zeros((2, N)))
        place(buf, pan(np.asarray(x, float), p) if np.ndim(x) == 1 else x, t)


def caper(b, t0, t1, mel=True, vel=0.5, major=False, whistle=False):
    r = rng(int(t0 * 100))
    k = 0
    while True:
        tb = t0 + k * 2 * BEAT
        if tb >= t1 - 0.05: break
        root = BASS[k % len(BASS)]; root = MAJ(root) if major else root
        for j in range(2):
            tj = tb + j * BEAT
            if tj >= t1: break
            b.add("bass", I.pluck(F(root + (0 if j == 0 else 7)), vel * 0.7, r, 0.3, 0.35), tj, -0.1)
            b.add("brush", I.brush(vel * (0.4 if j else 0.22), r, 0.18), tj + BEAT / 2, 0.2)
            b.add("tick", I.snare(vel * 0.12, r, 0.08, tune=1.6, snappy=0.2), tj, -0.25)
        k += 1
    if mel:
        tm0 = t0
        while tm0 < t1:
            for (bt, ln, m) in MEL:
                tm = tm0 + bt * BEAT
                if tm + ln * BEAT > t1 + 0.05: break
                mm = MAJ(m) if major else m
                b.add("mel", I.vibes(F(mm), vel * 0.5, r, dur=ln * BEAT + 0.25, trem_depth=0.1), tm, 0.1)
                b.add("pizz", I.pluck(F(mm - 12), vel * 0.35, r, 0.25, 0.8), tm, -0.15)
            tm0 += 16 * BEAT
    if whistle:
        notes, tm0 = [], t0
        while tm0 < t1:
            for (bt, ln, m) in MEL[:13]:
                tm = tm0 + bt * BEAT
                if tm + ln * BEAT > t1: break
                notes.append((tm, ln * BEAT * 0.9, (MAJ(m) if major else m) + 12, 0.6))
            tm0 += 16 * BEAT
        if notes:
            ts, y = I.whistle(notes, rng(77)); b.add("whistle", y, ts, 0.0)


def build_score():
    b = Band()
    # the hook is truck + CRUNCH; a timpani hit and the caper start on "For thirteen days"
    b.add("timp", I.timpani(F(38), 0.7, rng(1), 1.6), fr(63)); b.cues.append((fr(63), "timpani on 'For thirteen days'"))
    caper(b, fr(66), fr(1300) - 0.03, vel=0.5); b.cues.append((fr(66), "the D-minor caper starts"))
    caper(b, fr(255), fr(596), mel=False, vel=0.3, whistle=True); b.cues.append((fr(255), "a cheeky whistle over the shop scenes"))
    # KLONK: the band stops dead; the repairman's line in near-silence, a low tuba 'wah-wah' after "idiot"
    b.cues.append((fr(1300), "music stops dead on the washing machine's KLONK"))
    b.add("pad", I.pad([F(50), F(57), F(62)], 4.5, 0.25, rng(9), att=1.2, rel=1.5, warm=600), fr(1330)); b.cues.append((fr(1330), "a low held pad under the repairman"))
    for k, m in enumerate((38, 37, 36)): b.add("sting", I.brass(F(m), 0.32 if k < 2 else 0.7, 0.55, rng(30 + k), kind="tuba", fall=-1.5 if k == 2 else 0.0), fr(1516) + k * 0.36)
    b.cues.append((fr(1516), "tuba wah-wah-waaah after 'idiot'"))
    # revenge: the caper again, now cocky in D major, to the payoff
    caper(b, fr(1532), fr(1934) - 0.03, vel=0.55, major=True); b.cues.append((fr(1532), "the caper returns in D major for the revenge"))
    b.add("cym", I.cymbal(0.35, rng(3), 2.0), fr(1629)); b.add("cym", I.cymbal(0.3, rng(4), 1.8), fr(1888))
    # the tea: soft vibes, a final button on "idiot?"
    for k, m in enumerate((74, 78, 81, 86)): b.add("dream", I.vibes(F(m), 0.4, rng(m), dur=1.4), fr(1945) + k * 0.16, 0.2 * (k % 2 * 2 - 1))
    for m in (38, 50, 57, 62): b.add("end", I.brass(F(m), 0.5, 0.55, rng(m), kind="tuba" if m < 50 else "horn"), fr(1977))
    b.add("cym", I.cymbal(0.3, rng(5), 2.2), fr(1977)); b.add("timp", I.timpani(F(38), 0.6, rng(6), 1.8), fr(1977))
    b.cues.append((fr(1977), "a cheeky final button on 'idiot?'"))
    BAL = {"mel": -3, "pizz": -8, "bass": -4, "brush": -12, "tick": -16, "whistle": -5, "timp": -6, "cym": -10, "sting": -2, "pad": -8, "dream": -6, "end": -3}
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
        f.write("# Hoover van short: sound cues (real CC0 recordings, BigSoundBank)\n\n| t (s) | layer | what | dB vs voice |\n|---|---|---|---|\n" + "\n".join(rows) + "\n\n## Music (original, synthesized)\n\n")
        f.write("\n".join(f"- {t:.2f} s: {d}" for t, d in mcues) + "\n")
    print(f"mix {DUR:.2f} s, {integrated(mix):.1f} LUFS, TP {true_peak(mix):.1f} dBTP; voice {VREF:.1f}, music {integrated(music):.1f}, sfx {integrated(sfx):.1f} LUFS")


if __name__ == "__main__":
    main()
