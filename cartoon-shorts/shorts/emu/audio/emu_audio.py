"""Sound for "The War Australia Lost to Birds": real CC0 recordings (BigSoundBank) laid per shot, an original quiet score
(the skill's synth instruments) ducked under the voice. Every event sits on its picture frame (src/videos/emu/
story.ts + cast.ts).

    python emu_audio.py        (from this folder) -> mix.wav (48 kHz, exact film length), stems/, cues.md

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
FPS, TOTAL = 30, 2085
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
        if name.endswith("@low"):  # an octave and a half down: hens become a deep emu drumming grunt
            name = name[:-4]; af.append("asetrate=44100*0.42,aresample=48000")
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


# ---------------------------------------------------------------- picture timeline (src/videos/emu/story.ts)
FLASH = 163
OUT = [(0, 311), (410, 1058), (1058, 1366), (1417, 1590), (1663, 1897)]
GOLDEN = [(1823, TOTAL)]


def gun_burst(sfx, f0, f1, db, p=0.0, every=3, desc="the Lewis gun firing"):
    """a real rifle crack, low-passed and repeated at the Lewis gun's ~9 rounds a second (one per muzzle flash)"""
    shot = hit("rifle-shot-1-s2853", 0.45, lpf=3800)
    for k, f in enumerate(range(f0, f1, every)):
        lay(sfx, shot * (0.85 + 0.15 * ((k * 7) % 3) / 2), fr(f), fr(f), db, "gun", desc if k == 0 else "", peak=True, p=p)


def sfx_track():
    sfx = np.zeros((2, N))
    span = lambda a, b: (fr(a), fr(b))  # noqa: E731
    # the outback: cicadas and a hot breeze under every outdoor shot
    for k, (a, b) in enumerate(OUT):
        t0, t1 = span(a, b)
        lay(sfx, bed("cicadas-s3002", ns(t1 - t0 + 0.5), lpf=7000, offset=a / 5), t0, t1, -31, "cicadas", "outback heat: cicadas")
        lay(sfx, bed("fields-of-rapeseed-s1350", ns(t1 - t0 + 0.5), lpf=3000, offset=a / 7), t0, t1, -33, "breeze", "wind over the fields")
    # 1: the hook burst, 2: the slump on "won"
    gun_burst(sfx, 99, 126, -12, p=0.15)
    lay(sfx, hit("running-in-the-tall-grass-s1843", 2.0, start=3.0), fr(20), fr(90), -27, "rustle", "emus moving in the wheat")
    lay(sfx, hit("metal-bucket-s0543", 0.6, lpf=1800), fr(134), fr(134), -16, "clank", "the gun knocked over", peak=True, p=0.2)
    # 3-4: the flock marching in, pecking
    lay(sfx, bed("running-in-the-tall-grass-s1843", ns(fr(244) - fr(167) + 0.5), lpf=2500), fr(167), fr(244), -24, "flock", "thousands of feet in the wheat")
    for k in range(5):
        lay(sfx, hit("news-paper-manipulations-s1251", 0.25, start=1.0 + k * 0.7, lpf=3500), fr(252 + k * 9), fr(252 + k * 9), -22, "peck", "beaks snapping wheat" if k == 0 else "", peak=True, p=(k % 3 - 1) * 0.3)
    # 5: the minister's office
    t0, t1 = span(311, 410)
    lay(sfx, bed("stopwatch-1-s2137", ns(t1 - t0 + 0.5), lpf=2500), t0, t1, -34, "clock", "the office clock")
    lay(sfx, bed("computer-2-ventilation-s0126", ns(t1 - t0 + 0.5), lpf=700), t0, t1, -38, "room", "room tone")
    lay(sfx, bed("steps-on-gravels-s0510", ns(0.6), lpf=3000), fr(324), fr(342), -26, "heels", "the farmers snap to attention")
    # 6: things appear with a thump; the crates drop
    for f in (416, 437, 457):
        lay(sfx, hit("door-knock-s0095", 0.25, lpf=700), fr(f), fr(f), -14, "pop", "a soft thump as each one appears", peak=True)
    for k in range(4):
        lay(sfx, hit("metal-bucket-s0543", 0.35, lpf=900), fr(492 + k * 3), fr(492 + k * 3), -17, "crates", "ammo crates landing" if k == 0 else "", peak=True, p=0.25)
    # 7: the newsreel camera whirring
    lay(sfx, hit("16mm-camera-1-s0939", 2.4, start=2.0), fr(518), fr(586), -20, "camera", "a 16 mm film camera running")
    # 8: the gunner's laugh
    lay(sfx, hit("delirious-laughter-10-s2100", 1.4, lpf=6000), fr(618), fr(618), -19, "laugh", "the gunner laughing", peak=True, p=0.1)
    # 9-10: the dam: the flock walking in, the volley, the hits, the jam
    lay(sfx, bed("pond-in-a-field-s0691", ns(fr(847) - fr(676) + 0.5), lpf=4000), fr(676), fr(847), -30, "dam", "water and frogs at the dam")
    lay(sfx, bed("running-in-the-tall-grass-s1843", ns(fr(774) - fr(676) + 0.5), lpf=2200, offset=6), fr(676), fr(774), -27, "flock", "the flock walking in")
    gun_burst(sfx, 779, 826, -11, p=0.1)
    for k in range(6):
        lay(sfx, hit("flight-bird-1-s2891", 0.5, lpf=5000), fr(799 + k * 4), fr(799 + k * 4), -21, "feathers", "flapping on each hit" if k == 0 else "", peak=True, p=(k % 3 - 1) * 0.4)
    lay(sfx, hit("gun-loading-1-s1988", 0.6), fr(827), fr(827), -10, "jam", "the gun jams: a dead metal clack", peak=True)
    lay(sfx, hit("running-in-the-tall-grass-s1843", 1.4, start=9.0), fr(830), fr(847), -21, "scatter", "the flock bolting", p=0.2)
    # 11-13: the truck starts, the chase
    lay(sfx, hit("car-difficult-start-s0872", 2.6, start=1.0), fr(852), fr(894), -20, "start", "the truck engine coughing to life")
    lay(sfx, bed("motor-car-1-s0290", ns(fr(1058) - fr(890) + 0.5), lpf=4500), fr(890), fr(1058), -20, "truck", "a vintage engine at full throttle")
    lay(sfx, hit("oogah-horn-3-s2542", 0.8), fr(900), fr(900), -18, "horn", "the truck's horn", peak=True, p=0.2)
    lay(sfx, bed("horse-gallop-tall-grass-s1850", ns(fr(1058) - fr(923) + 0.5), lpf=3000), fr(923), fr(1058), -24, "running", "emu feet pounding past")
    for k, f in enumerate(range(990, 1058, 11)):
        lay(sfx, hit("metal-bucket-s0543", 0.3, lpf=1200), fr(f), fr(f), -19, "bumps", "the tray banging over bumps" if k == 0 else "", peak=True, p=-0.1)
    gun_burst(sfx, 944, 1056, -15, p=-0.1, every=4, desc="wild bursts into the sky")
    # 14: silence but the breeze; 15-16: the flock, the burst
    lay(sfx, hit("hens-worried-s1039@low", 2.5, lpf=900, start=2.0), fr(1125), fr(1200), -28, "flock", "a low murmur of birds (pitched down)")
    gun_burst(sfx, 1269, 1293, -13)
    lay(sfx, hit("flight-bird-3-s2893", 1.2, lpf=6000), fr(1272), fr(1272), -18, "scatter", "the flock bursting apart", peak=True)
    lay(sfx, bed("horse-gallop-tall-grass-s1850", ns(fr(1366) - fr(1276) + 0.5), lpf=2500, offset=4), fr(1276), fr(1366), -23, "running", "groups running off")
    # 17: the marbles
    lay(sfx, hit("glass-ball-bounce-1-s2240", 3.0), fr(1380), fr(1380), -13, "marbles", "glass marbles bouncing and rolling", peak=True)
    lay(sfx, hit("glass-ball-bounce-2-s2241", 2.4), fr(1383), fr(1383), -16, "marbles", "more marbles", peak=True, p=0.3)
    lay(sfx, hit("door-knock-s0095", 0.25, lpf=600), fr(1380), fr(1380), -14, "bag", "the bag thuds down", peak=True)
    # 18: the lookout's alarm, the group runs
    lay(sfx, hit("hens-worried-s1039@low", 1.0, lpf=700, start=8.0), fr(1514), fr(1514), -15, "alarm", "the lookout's low alarm grunt", peak=True)
    lay(sfx, hit("running-in-the-tall-grass-s1843", 1.2, start=12.0), fr(1524), fr(1545), -21, "flee", "the group dashing off")
    # 19: the truck leaves
    lay(sfx, hit("motor-car-1-s0290", 1.6, lpf=3500), fr(1545), fr(1590), -22, "truck", "the truck driving away")
    # 20: parliament
    t0, t1 = span(1590, 1663)
    lay(sfx, bed("walla-group-averages-discussions-s0684", ns(t1 - t0 + 0.5), lpf=3000), t0, t1, -29, "house", "the chamber murmuring")
    lay(sfx, hit("atmosphere-bar-2-s0480", 1.6, start=31.0, lpf=5000), fr(1646), fr(1646), -17, "laughter", "the House laughing", peak=True)
    lay(sfx, hit("applause-about-25-50-people-1-s0812", 1.0, lpf=4000), fr(1652), fr(1652), -22, "desks", "members slapping the benches", peak=True)
    # 21-22: the brass mountain, the ten cases
    gun_burst(sfx, 1663, 1765, -18, desc="the gun still firing")
    for k, f in enumerate(range(1666, 1765, 7)):
        lay(sfx, hit("bullet-case-7-62mm-on-concrete-1-s1367" if k % 2 else "bullet-case-7-62mm-on-concrete-2-s1368", 0.5), fr(f), fr(f), -20, "cases", "spent cases tinkling" if k == 0 else "", peak=True, p=(k % 3 - 1) * 0.3)
    for k in range(10):
        lay(sfx, hit("bullet-case-7-62mm-on-concrete-1-s1367" if k % 2 else "bullet-case-7-62mm-on-concrete-2-s1368", 0.45), fr(1777 + k * 3), fr(1777 + k * 3), -15, "ten", "a case lands for each count" if k == 0 else "", peak=True, p=-0.4 + k * 0.09)
    # 23: the report: pen on paper
    lay(sfx, hit("pencil-signature-1-s3236", 1.8), fr(1826), fr(1858), -20, "pen", "the major writing")
    # 24: the parade: marching feet
    t0, t1 = span(1897, TOTAL)
    lay(sfx, bed("steps-on-gravels-s0510", ns(t1 - t0 + 0.5), lpf=3000), t0, t1, -27, "march", "the emu division marching")
    lay(sfx, bed("cicadas-s3002", ns(fr(TOTAL) - fr(1823) + 0.5), lpf=5000, offset=30), fr(1823), fr(TOTAL), -34, "evening", "evening cicadas")
    return sfx


# ---------------------------------------------------------------- score (original): a cheeky bush-band march in G
BPM = 116
BEAT = 60 / BPM
BAR = 4 * BEAT
# melody (beat, length, midi): a bouncy fife tune over oom-pah tuba
MEL = [(0, .5, 74), (.5, .5, 71), (1, .5, 74), (1.5, .5, 79), (2, 1, 78), (3, 1, 76),
       (4, .5, 74), (4.5, .5, 72), (5, .5, 71), (5.5, .5, 72), (6, 1, 74), (7, 1, 67),
       (8, .5, 69), (8.5, .5, 71), (9, .5, 72), (9.5, .5, 74), (10, 1, 76), (11, .5, 74), (11.5, .5, 72),
       (12, .5, 71), (12.5, .5, 69), (13, .5, 67), (13.5, .5, 66), (14, 2, 67)]
CHORDS = [(43, [59, 62, 67]), (38, [57, 62, 66]), (43, [59, 62, 67]), (38, [57, 62, 66])]


class Band:
    def __init__(self): self.tr = {}; self.cues = []
    def add(self, k, x, t, p=0.0):
        buf = self.tr.setdefault(k, np.zeros((2, N)))
        place(buf, pan(np.asarray(x, float), p) if np.ndim(x) == 1 else x, t)


def march(b, t0, t1, mel=True, vel=0.5, drums=True):
    r = rng(int(t0 * 100))
    k = 0
    while True:
        tb = t0 + k * BAR
        if tb >= t1 - 0.05: break
        root, ch = CHORDS[k % 4]
        for j in range(4):
            tj = tb + j * BEAT
            if tj >= t1: break
            if j % 2 == 0: b.add("tuba", I.brass(F(root + (0 if j == 0 else 7)), BEAT * 0.55, vel * 0.8, r, "tuba"), tj, 0.0)
            else:
                for m in ch: b.add("chord", I.pluck(F(m), vel * 0.3, r, 0.25, 0.6), tj, 0.15)
            if drums: b.add("snare", I.snare(vel * (0.42 if j % 2 else 0.25), r, buzz=False), tj, -0.2)
        k += 1
    if mel:
        tm0 = t0
        while tm0 < t1:
            for (bt, ln, m) in MEL:
                tm = tm0 + bt * BEAT
                if tm + ln * BEAT > t1 + 0.05: break
                b.add("fife", I.fife(F(m), ln * BEAT * 0.85, vel * 0.7, r), tm, 0.05)
            tm0 += 16 * BEAT


def build_score():
    b = Band()
    march(b, 0.15, fr(1058) - 0.1)
    b.add("timp", I.timpani(F(31), 0.5, rng(1), 1.6), fr(FLASH)); b.cues.append((fr(FLASH), "soft timpani under the white flash"))
    # the drop-out: "Wait, how do birds beat a machine gun?" plays over the breeze alone; one low tuba note on "gun"
    b.add("tuba", I.brass(F(31), 0.9, 0.5, rng(5), "soft"), fr(1100)); b.cues.append((fr(1058), "music stops for 'Wait, how do birds beat a machine gun?'"))
    march(b, fr(1117), fr(1823), mel=True, vel=0.5)
    b.cues.append((fr(1117), "the march returns on 'You see'"))
    # the report: soft and dreamy, then the division: the march again, grander, ending on 'world'
    for m in [67, 71, 74]: b.add("chord", I.pad([F(m)], 2.2, 0.35, rng(m), att=0.3, rel=0.8, warm=1800), fr(1830), 0.0)
    for m in [69, 72, 76]: b.add("chord", I.pad([F(m)], 1.6, 0.35, rng(m + 1), att=0.3, rel=0.8, warm=1800), fr(1866), 0.0)
    b.cues.append((fr(1823), "dreamy chords under the report"))
    march(b, fr(1897), fr(2018), mel=True, vel=0.6)
    for m in [55, 59, 62, 67, 74]: b.add("brassEnd", I.brass(F(m), 1.6, 0.6, rng(m), "horn"), fr(2018), 0.0)
    b.add("tuba", I.brass(F(31), 1.8, 0.7, rng(9), "tuba"), fr(2018))
    b.add("timp", I.cymbal(0.4, rng(3), 2.4), fr(2018)); b.cues.append((fr(2018), "final G major chord + cymbal on 'world'"))
    BAL = {"fife": -2, "chord": -5, "tuba": -3, "snare": -9, "timp": -8, "brassEnd": -2}
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
        f.write("# Emu short: sound cues (real CC0 recordings, BigSoundBank)\n\n| t (s) | layer | what | dB vs voice |\n|---|---|---|---|\n" + "\n".join(rows) + "\n\n## Music (original, synthesized)\n\n")
        f.write("\n".join(f"- {t:.2f} s: {d}" for t, d in mcues) + "\n")
    print(f"mix {DUR:.2f} s, {integrated(mix):.1f} LUFS, TP {true_peak(mix):.1f} dBTP; voice {VREF:.1f}, music {integrated(music):.1f}, sfx {integrated(sfx):.1f} LUFS")


if __name__ == "__main__":
    main()
