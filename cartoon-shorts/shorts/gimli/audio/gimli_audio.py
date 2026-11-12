"""Sound for "The Jet That Landed on a Drag Race" (the Gimli Glider, 1983): real CC0 recordings (BigSoundBank) laid on
their picture frames (src/videos/gimli/story.ts + cast.ts), an original score ducked under the voice. The cue is new
for the channel: a jaunty B-flat adventure march (horns, pizzicato bass, snare) that stops dead on the BONG, a drone
while the engines die, a carefree vibes waltz for the glider, the march back for Family Day, a snare roll into the
landing, a brass chord on "everyone survives", and a deflating tuba after the van dies.

    python gimli_audio.py   (from this folder) -> mix.wav (48 kHz, exact film length), stems/, cues.md
"""
import json, os, subprocess, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "marathon", "audio"))
from dsp import SR, ns, rng, hp, lp, dbg, pan, place, read_wav, write_wav, integrated, true_peak  # noqa: E402
import instruments as I  # noqa: E402

LIB = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", "assets", "cc0", "sfx", "bigsoundbank"))
FFMPEG = "ffmpeg"
FPS, TOTAL = 30, 2100
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


def varispeed(x, r0, r1, seconds):
    """play x with the speed gliding from r0 to r1 (an engine spooling down)"""
    n = int(seconds * SR); rate = np.linspace(r0, r1, n); pos = np.cumsum(rate)
    pos = np.clip(pos, 0, len(x) - 2); i = pos.astype(int); fr_ = pos - i
    y = x[i] * (1 - fr_) + x[i + 1] * fr_
    k = int(0.3 * SR); y[-k:] *= np.linspace(1, 0, k); return y


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
    B = lambda name, a, b, db, desc="", lpf=None, off=0.0, p=0.0, hpf=None: lay(sfx, bed(name, ns(fr(b) - fr(a) + 0.6), lpf=lpf, hpf=hpf, offset=off), fr(a), fr(b), db, name.split("-s")[0], desc, p=p)  # noqa: E731
    H = lambda name, f, db, desc="", sec=1.5, lpf=None, start=None, p=0.0: lay(sfx, hit(name, sec, lpf=lpf, start=start), fr(f), fr(f), db, name.split("-s")[0], desc, peak=True, p=p)  # noqa: E731
    # 1 HOOK: the dragster launching past the lens (hit on f0), the kids screaming, the silent jet's rushing wind
    H("motor-car-1-s0290@1.35", 0, 4, "dragster launch past the lens (f0)", sec=2.6, p=0.35)
    B("strong-wind-1-s0146", 0, 87, -12, "the silent jet's rushing air", lpf=1800, off=12)
    H("kids-screaming-1-s1148", 22, -12, "the kids yelling", sec=2.2, start=1.0, p=-0.2)
    B("bicycle-rear-wheel-s0140", 0, 87, -18, "bike freewheel ticking", p=-0.1)
    H("whoosh-5-s1797", 84, -14, "whip to Montreal")
    # 2-8 RAMP (day): apron ambience, the fuel truck idling, a far jet; the crew's foley
    B("airplane-pass-1-s3004", 87, 716, -22, "apron: a far jet passing", lpf=2500)
    B("truck-engine-2-s1443", 87, 716, -24, "the fuel truck idling", lpf=1200, off=5)
    H("click-seatbelt-s0656", 231, -14, "finger tap on the dead gauge", sec=0.4)
    H("click-seatbelt-s0656", 238, -16, "tap again", sec=0.4)
    H("medium-chain-1-s0360", 300, -12, "the dipstick sliding out of the wing", sec=1.4)
    H("pencil-signature-1-s3236", 495, -12, "pencil on the clipboard: x 1.77", sec=2.2)
    B("electric-pump-s0709", 542, 626, -14, "the fuel pump running", lpf=3000)
    H("gavel-1-blow-s1588", 577, -6, "stamp: LESS THAN HALF", sec=0.4)
    H("medium-chain-1-s0360", 650, -14, "Ottawa: the stick again", sec=1.4)
    H("gavel-1-blow-s1588", 684, -6, "stamp: SAME MISTAKE", sec=0.4)
    for f in (264, 481, 626): H("whoosh-6-s1799", f - 3, -16, "whip", sec=0.6)
    # 9-13 CRUISE + COCKPIT: the cabin drone, the BONG, two engines spooling down, the glass panel dying
    B("airplane-pass-5-s3008", 716, 1032, -18, "cruise drone at 41,000 ft", lpf=900, off=2)
    H("whoosh-5-s1797", 713, -14, "whip up to 41,000 ft")
    B("computer-2-ventilation-s0126", 762, 1011, -24, "cockpit avionics hum", lpf=4000)
    H("small-bell-s0010@0.55", 762, 3, "BONG: the all-engines warning nobody had heard", sec=2.4)
    lay(sfx, varispeed(rec("airplane-pass-5-s3008", lpf=2200), 1.0, 0.25, 2.2), fr(878), fr(944), -8, "airplane-pass", "left engine spooling down", peak=False)
    lay(sfx, varispeed(rec("airplane-pass-5-s3008", lpf=2200), 1.0, 0.25, 2.0), fr(932), fr(992), -8, "airplane-pass", "right engine spooling down", peak=False, p=0.2)
    H("explosion-far-away-s1023", 885, -14, "a cough of smoke from the left engine", sec=1.2, lpf=900)
    H("explosion-far-away-s1023", 937, -14, "and the right", sec=1.2, lpf=900)
    H("lock-s0191", 1009, -6, "clunk: the screens go black", sec=0.6)
    B("strong-wind-1-s0146", 972, 1032, -16, "only the wind now", lpf=1400, off=30)
    # 14 GLIDER: a light breeze
    B("strong-wind-1-s0146", 1032, 1170, -22, "glider breeze", lpf=2500, off=44)
    H("whoosh-3-s1795", 1128, -12, "the barrel roll", sec=1.0)
    # 15 cockpit hush (wind)
    B("strong-wind-1-s0146", 1170, 1282, -18, "gliding: wind only", lpf=1200, off=55)
    # 16-19 FAMILY DAY: crowd, kids, BBQ sizzle, dragsters, the silent jet
    B("crowd-of-50-60-people-1-s3515", 1282, 1703, -18, "Family Day crowd", off=10)
    B("shouts-and-applauses-of-teens-1-s0236", 1282, 1414, -22, "kids having fun", off=0)
    B("log-wood-boiler-s1120", 1475, 1560, -16, "the BBQ sizzling", lpf=6000, off=8)
    H("motor-car-1-s0290@1.2", 1414, -4, "dragster burnout", sec=2.4, start=0.2)
    H("motor-car-1-s0290@1.4", 1428, -3, "launch", sec=2.0, start=0.0, p=-0.3)
    B("bicycle-rear-wheel-s0140", 1442, 1475, -14, "bikes freewheeling")
    B("strong-wind-1-s0146", 1487, 1560, -12, "the jet's silent rush overhead", lpf=1600, off=70)
    H("whoosh-5-s1797", 1279, -14, "whip to the strip")
    # 20-21 cockpit + the sideslip pass
    B("strong-wind-1-s0146", 1560, 1647, -14, "air roaring on the glass", lpf=1500, off=20)
    H("airplane-pass-1-s3004", 1650, -6, "the jet sliding past sideways", sec=2.2, start=3.0, lpf=1500)
    # 22-23 TOUCHDOWN: thump, the nose CRUNCH, scraping metal and sparks, the crowd gasping
    H("explosion-far-away-s1023", 1704, -4, "mains hit the runway", sec=1.4, lpf=700)
    H("explosion-far-away-s1023", B_COLLAPSE, -2, "the nose slams down", sec=1.6, lpf=1200)
    H("anvil-1-s3589", B_COLLAPSE + 1, -10, "metal crunch", sec=0.8)
    B("metal-filing-cabinet-s0773", B_COLLAPSE, B_STOP, -8, "nose scraping along the runway", off=3)
    B("long-welding-1-s0950", B_COLLAPSE, B_STOP, -14, "sparks hissing", off=2)
    B("truck-engine-1-s1442", 1704, B_STOP, -14, "the rumble of 100 tons sliding", lpf=300)
    H("kids-screaming-2-s1149", 1760, -12, "the crowd shrieks", sec=2.2, start=0.5)
    H("crowd-of-50-60-people-2-s3516", 1828, -14, "a stunned murmur after the stop", sec=2.0, start=8.0)
    # 24-25 the extinguishers, then cheering
    for k, f in enumerate((1858, 1863, 1868, 1876, 1884)): H("hiss-of-steam-train-6-s3017", f, -10, "extinguisher blast" if k == 0 else "", sec=1.2, p=(k % 3 - 1) * 0.3)
    H("applause-about-25-50-people-1-s0812", 1898, -10, "applause: everyone survives", sec=4.0, start=0.3)
    H("shouts-and-applauses-of-teens-1-s0236", 1900, -14, "cheers", sec=3.0)
    # 26-27 the van: engine, the cough-and-sputter, silence, crickets, a mechanic's dry cough
    H("whoosh-5-s1797", 1936, -14, "whip to the road")
    B("ford-courier-engine-s0896", 1939, 2010, -10, "the mechanics' van on the road", off=3)
    B("cicadas-s3002", 1939, TOTAL, -22, "dusk crickets")
    H("car-difficult-start-s0872", 2010, -6, "the engine coughs and dies", sec=2.4, start=1.0)
    H("man-cough-2-s1657", 2068, -14, "a dry cough", sec=1.2)
    return sfx


B_COLLAPSE, B_STOP = 1720, 1826

# ---------------------------------------------------------------- score (original): a B-flat adventure march, 128 BPM
BPM = 128
BEAT = 60 / BPM
# horn tune (beats, length, midi): bright, bouncy, a little pompous
MEL = [(0, .5, 70), (.5, .5, 74), (1, .5, 77), (1.5, .5, 74), (2, 1, 82), (3, 1, 77),
       (4, .5, 75), (4.5, .5, 77), (5, .5, 79), (5.5, .5, 75), (6, 1.5, 74), (7.5, .5, 72),
       (8, .5, 70), (8.5, .5, 74), (9, .5, 77), (9.5, .5, 82), (10, .5, 84), (10.5, .5, 82), (11, 1, 79),
       (12, .5, 77), (12.5, .5, 75), (13, .5, 74), (13.5, .5, 72), (14, 2, 70)]
BASS = [46, 53, 51, 53, 43, 50, 41, 48]   # Bb, Eb, G minor, F roots, one per half bar


class Band:
    def __init__(self): self.tr = {}; self.cues = []
    def add(self, k, x, t, p=0.0):
        buf = self.tr.setdefault(k, np.zeros((2, N)))
        place(buf, pan(np.asarray(x, float), p) if np.ndim(x) == 1 else x, t)


def march(b, t0, t1, mel=True, vel=0.5, soft=False):
    r = rng(int(t0 * 100)); k = 0
    while True:
        tb = t0 + k * 2 * BEAT
        if tb >= t1 - 0.05: break
        root = BASS[k % len(BASS)]
        for j in range(2):
            tj = tb + j * BEAT
            if tj >= t1: break
            b.add("bass", I.pluck(F(root - 12 + (0 if j == 0 else 7)), vel * 0.75, r, 0.3, 0.4), tj, -0.1)
            if not soft:
                b.add("snare", I.snare(vel * (0.18 if j else 0.3), r, 0.12, tune=1.2, snappy=0.6), tj + BEAT / 2, 0.15)
                b.add("tick", I.snare(vel * 0.08, r, 0.06, tune=1.8, snappy=0.2), tj + BEAT * 0.75, -0.2)
        k += 1
    if mel:
        tm0 = t0
        while tm0 < t1:
            for (bt, ln, m) in MEL:
                tm = tm0 + bt * BEAT
                if tm + ln * BEAT > t1 + 0.05: break
                b.add("horn", I.brass(F(m - 12), ln * BEAT * 0.92, vel * (0.45 if soft else 0.6), r, kind="horn"), tm, 0.12)
                b.add("glock", I.glock(F(m + 12), vel * 0.18, r, dur=0.6), tm, -0.15) if ln >= 1 else None
            tm0 += 16 * BEAT


def waltz(b, t0, t1, vel=0.5):
    """the glider: a carefree vibes waltz in F, three to a bar"""
    r = rng(7); bar = 3 * 60 / 150; tune = [77, 81, 84, 81, 79, 76, 77, 72, 74, 77, 81, 79]; k = 0
    while t0 + k * bar < t1 - 0.1:
        t = t0 + k * bar; root = [41, 46, 48, 41][k % 4]
        b.add("wbass", I.pluck(F(root), vel * 0.6, r, 0.5, 0.3), t, -0.1)
        for j in (1, 2): b.add("wchord", I.pluck(F(root + 12 + (4 if j == 1 else 7)), vel * 0.3, r, 0.3, 0.6), t + j * bar / 3, 0.2)
        b.add("vibes", I.vibes(F(tune[k % len(tune)]), vel * 0.55, r, dur=bar * 1.1), t, 0.1)
        k += 1


def build_score():
    b = Band()
    b.add("timp", I.timpani(F(46), 0.8, rng(1), 1.6), fr(69)); b.add("cym", I.cymbal(0.35, rng(2), 1.8), fr(69)); b.cues.append((fr(69), "timpani + cymbal on 'drag race'"))
    march(b, fr(87), fr(762) - 0.02, vel=0.5); b.cues.append((fr(87), "the B-flat adventure march starts (Montreal)"))
    for k, m in enumerate((46, 45)): b.add("sting", I.brass(F(m - 12), 0.35, 0.6, rng(20 + k), kind="tuba"), fr(514) + k * 0.3)
    b.cues.append((fr(514), "tuba 'bwomp' on 'pounds'"))
    for k, m in enumerate((46, 44, 43)): b.add("sting", I.brass(F(m - 12), 0.32, 0.55, rng(25 + k), kind="tuba", fall=-1.2 if k == 2 else 0.0), fr(688) + k * 0.28)
    b.cues.append((fr(688), "tuba 'wah-wah-waah' on 'same mistake'"))
    b.cues.append((fr(762), "music stops dead on the BONG"))
    b.add("pad", I.pad([F(38), F(45), F(50)], 9.0, 0.3, rng(9), att=1.5, rel=2.0, warm=500), fr(871)); b.cues.append((fr(871), "a low, uneasy drone while the engines die"))
    b.cues.append((fr(1011), "everything cuts with the screens"))
    waltz(b, fr(1036), fr(1168), vel=0.5); b.cues.append((fr(1036), "carefree vibes waltz for Bob's glider"))
    notes = [(fr(1145) + k * 0.09, 0.1, 84 + 2 * k, 0.5) for k in range(6)]; ts, y = I.whistle(notes, rng(11)); b.add("whistle", y, ts, 0.0)
    b.cues.append((fr(1145), "a rising whistle on 'for fun'"))
    b.add("pad2", I.pad([F(41), F(48), F(53)], 3.8, 0.3, rng(12), att=0.8, rel=1.2, warm=700), fr(1170))
    march(b, fr(1286), fr(1414) - 0.02, vel=0.55); b.cues.append((fr(1286), "the march back, festive, for Family Day"))
    rr = rng(13)
    for (t, v) in I.snare_roll(fr(1490), fr(1703), 0.05, 0.6, rr): b.add("roll", I.snare(v, rr, 0.1, tune=1.1, snappy=0.8, buzz=True), t, 0.1)
    b.cues.append((fr(1490), "a snare roll building into the landing"))
    for t in (1560, 1600, 1640, 1672): b.add("timp", I.timpani(F(41), 0.4 + 0.1 * (t > 1620), rng(t), 1.2), fr(t))
    b.cues.append((fr(1703), "silence for the touchdown and the scrape (only real sound)"))
    for m in (46, 53, 58, 62, 65): b.add("chord", I.brass(F(m - 12), 1.8, 0.6, rng(m), kind="horn" if m > 50 else "tuba"), fr(1898))
    b.add("cym", I.cymbal(0.45, rng(5), 2.6), fr(1898)); b.add("timp", I.timpani(F(46), 0.8, rng(6), 2.0), fr(1898)); b.cues.append((fr(1898), "a brass chord on 'everyone survives'"))
    march(b, fr(1942), fr(2010) - 0.02, vel=0.42, soft=True); b.cues.append((fr(1942), "the march, soft, for the mechanics' van"))
    for k, m in enumerate((46, 45, 44, 43)): b.add("sting", I.brass(F(m - 12), 0.34 if k < 3 else 1.4, 0.6, rng(40 + k), kind="tuba", fall=-2.0 if k == 3 else 0.0), fr(2050) + k * 0.36)
    b.cues.append((fr(2050), "the deflating tuba after the van dies"))
    BAL = {"horn": -3, "glock": -12, "bass": -5, "snare": -12, "tick": -18, "timp": -6, "cym": -10, "sting": -2, "pad": -10, "pad2": -12, "vibes": -4, "wbass": -8,
           "wchord": -12, "whistle": -6, "roll": -10, "chord": -2}
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
    music = music * dbg(VREF - 21.0 - integrated(music))
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
        f.write("# Gimli Glider short: sound cues (real CC0 recordings, BigSoundBank)\n\n| t (s) | layer | what | dB vs voice |\n|---|---|---|---|\n" + "\n".join(rows) + "\n\n## Music (original, synthesized)\n\n")
        f.write("\n".join(f"- {t:.2f} s: {d}" for t, d in mcues) + "\n")
    print(f"mix {DUR:.2f} s, {integrated(mix):.1f} LUFS, TP {true_peak(mix):.1f} dBTP; voice {VREF:.1f}, music {integrated(music):.1f}, sfx {integrated(sfx):.1f} LUFS")


if __name__ == "__main__":
    main()
