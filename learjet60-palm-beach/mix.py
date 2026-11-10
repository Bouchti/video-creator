"""Score, sound design and mix for "Four Minutes over Palm Beach" -> out/mix.wav (48 kHz stereo) + out/stems/.

Everything sits on the timeline (timeline.json) and the page's events (events.json), so every sound lands on its frame.

  palette   dry until the dive: FM pings (the lock is the film's key sound), dry ticks, a pulse bass with 2nd/3rd
            harmonics, detuned-saw pads under a low-pass, teletype clicks for the crew reports, rain and far thunder
            the turn: one wet timbre, a bowed-metal drone that rises through the dive, wind roar, a timpani roll
            weight: a single low impact (timpani, bass drum, low brass stab, punch), then silence
            after: bowed vibraphone and a low pad, a last ping, the tail
  beds      orbit hum + radio hiss; rain in the storm; low wind at the site
  voice     Kokoro (af_heart), compressed, music ducked underneath

usage: LIB=<library> $LIB/.venv/bin/python mix.py
"""
import json, os, sys
import numpy as np
import soundfile as sf
import soxr
from scipy.signal import butter, sosfilt

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.environ['LIB']
sys.path.insert(0, LIB)
from core.audio import sampler as S
from core.audio import sfx as X

SR = X.SR
TL = json.load(open(os.path.join(HERE, 'timeline.json')))
EV = json.load(open(os.path.join(HERE, 'events.json')))['ev']
T = TL['T']
DUR = T['dur']
N = int((DUR + 0.6) * SR)
BEAT = 0.75
rng = np.random.default_rng(11)
S.seed(7)

MUS = np.zeros((N, 2)); PUL = np.zeros((N, 2)); HIT = np.zeros((N, 2)); FX = np.zeros((N, 2)); BED = np.zeros((N, 2)); VOX = np.zeros((N, 2))


# ------------------------------------------------------------------ dsp helpers
def sos(kind, f, o=2): return butter(o, f, kind, fs=SR, output='sos')
def lpf(x, f, o=2): return sosfilt(sos('low', min(f, SR * .45), o), x, axis=0)
def hpf(x, f, o=2): return sosfilt(sos('high', f, o), x, axis=0)
def bpf(x, a, b, o=2): return sosfilt(sos('band', [a, min(b, SR * .45)], o), x, axis=0)
def tv(d): return np.arange(int(d * SR)) / SR
def hz(m): return 440.0 * 2 ** ((m - 69) / 12)
NOTE = {'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8, 'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11}
def mi(n): return 12 * (int(n[-1]) + 1) + NOTE[n[:-1]]
def put(buf, x, at, g=1.0, pan=0.0):
    x = np.asarray(x, np.float64)
    if x.ndim == 2:
        s = int(at * SR)
        if s >= len(buf): return
        if s < 0: x = x[-s:]; s = 0
        e = min(len(buf), s + len(x)); buf[s:e] += x[:e - s] * g
    else:
        X.add(buf, x, at, g, pan)
def adsr(d, a=.005, r=.1, curve=1.0):
    n = int(d * SR); e = np.ones(n)
    na = max(1, int(a * SR)); e[:na] = np.linspace(0, 1, na) ** curve
    nr = min(n, int(r * SR)); e[n - nr:] *= np.linspace(1, 0, nr) ** 1.5
    return e
def saw(f, d, det=0.0, nh=40):
    t = tv(d); x = np.zeros_like(t)
    for k in range(1, nh):
        if f * k > 15000: break
        x += np.sin(2 * np.pi * f * (1 + det) * k * t) / k
    return x * .55
def fm(fc, ratio, index, d, tau_i=.15):
    t = tv(d); I = index * np.exp(-t / tau_i)
    return np.sin(2 * np.pi * fc * t + I * np.sin(2 * np.pi * fc * ratio * t))
def stereo(x, w=.0006):
    d = int(w * SR); return np.stack([x, np.concatenate([np.zeros(d), x[:-d]]) if d else x], 1)
def delay(x, at, fb, n, gain=1.0, pan_alt=.5):
    L = len(x) + int(at * n * SR) + 10; out = np.zeros((L, 2))
    for k in range(n + 1):
        s = int(at * k * SR); g = gain * fb ** k; p = 0 if k == 0 else (pan_alt if k % 2 else -pan_alt)
        l, r = np.cos((p + 1) * np.pi / 4) * 1.414, np.sin((p + 1) * np.pi / 4) * 1.414
        xx = lpf(x, 6000 - 900 * k) if k else x
        out[s:s + len(x), 0] += xx * g * l; out[s:s + len(x), 1] += xx * g * r
    return out
def env_curve(d, pts):
    """piecewise-linear envelope over d seconds from [(u, v), ...] with u in 0..1"""
    u = np.linspace(0, 1, int(d * SR)); return np.interp(u, [p[0] for p in pts], [p[1] for p in pts])


# ------------------------------------------------------------------ instruments (synth)
def bass(m, d, vel=.8, cut=380):
    f = hz(m); x = saw(f, d, nh=18) * .8 + np.sin(2 * np.pi * f * tv(d)) * .9 + saw(f, d, .004, nh=10) * .4
    x = lpf(x, cut, 2) + .12 * np.tanh(3 * lpf(x, 900))
    return x * adsr(d, .012, min(.25, d * .4)) * vel * .8
def ping(m, vel=.6, d=1.6):
    t = tv(d); f = hz(m)
    x = fm(f, 3.5, 3.0, d, .05) * np.exp(-t / .55) + .35 * np.sin(2 * np.pi * f * 2.01 * t) * np.exp(-t / .3)
    return x * vel
def pad(ms, d, vel=.25, cut=1400, a=.6, r=.9):
    x = np.zeros(int(d * SR))
    for m in ms:
        for det in (-.0035, .0, .0041):
            x += saw(hz(m), d, det, nh=24)
    y = lpf(x, cut) * .7 + lpf(x, cut * .5) * .3
    return y * adsr(d, a, r) * vel / max(1, len(ms))
def tick(vel=.3, f=5200):
    d = .018; return bpf(rng.standard_normal(int(d * SR)), f * .7, f * 1.3) * np.exp(-tv(d) / .003) * vel
def tock(vel=.5):
    d = .12; t = tv(d); return (np.sin(2 * np.pi * 820 * t) * np.exp(-t / .02) + .5 * np.sin(2 * np.pi * 1640 * t) * np.exp(-t / .01)) * vel
def teletype(n=4, vel=.25):
    out = np.zeros(int(.6 * SR)); t = 0.0
    for _ in range(n):
        c = bpf(rng.standard_normal(int(.012 * SR)), 1800, 6500) * np.exp(-tv(.012) / .002)
        i = int(t * SR); out[i:i + len(c)] += c * (.6 + .4 * rng.random()); t += rng.uniform(.045, .085)
    return out * vel
def servo(d=.5, f0=900, f1=1500, vel=.1):
    t = tv(d); f = f0 + (f1 - f0) * t / d
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * adsr(d, .04, .12) * vel * (1 + .2 * np.sin(2 * np.pi * 31 * t))
def sweep(d, f0, f1, q=.35, vel=.5):
    n = rng.standard_normal(int(d * SR)); out = np.zeros_like(n); blk = 256
    for i in range(0, len(n), blk):
        u = i / max(1, len(n)); f = f0 * (f1 / f0) ** u
        lo, hi = f * (1 - q), min(f * (1 + q), SR * .45)
        s = max(0, i - 3000); y = sosfilt(sos('band', [lo, hi]), n[s:i + blk]); out[i:i + blk] = y[-(min(blk, len(n) - i)):]
    return out * np.sin(np.pi * np.clip(tv(d) / d, 0, 1)) ** 1.2 * vel
def punch(vel=1.0, d=1.1):
    """an impact's body in the 60-120 Hz band; speaks on small speakers"""
    t = tv(d)
    b1 = np.sin(2 * np.pi * np.cumsum(66 * (1 + 1.2 * np.exp(-t / .025))) / SR) * np.exp(-t / .3)
    b2 = np.sin(2 * np.pi * np.cumsum(98 * (1 + .8 * np.exp(-t / .02))) / SR) * np.exp(-t / .18) * .6
    kn = bpf(rng.standard_normal(len(t)), 90, 400) * np.exp(-t / .05) * .7
    y = b1 + b2 + kn
    return (y + .25 * np.tanh(2.5 * y)) * vel
def bowed_metal(d, m0, m1, vel=.3):
    """the one wet timbre: inharmonic partials with slow beating, gliding up from m0 to m1 over d"""
    t = tv(d); f = hz(m0) * (hz(m1) / hz(m0)) ** ((t / d) ** 1.6)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.zeros_like(t)
    for r, a in ((1.0, 1.0), (2.32, .45), (3.94, .28), (5.21, .16), (1.004, .6)):
        x += a * np.sin(ph * r + rng.random() * 6) * (.75 + .25 * np.sin(2 * np.pi * (.6 + r * .3) * t + rng.random() * 6))
    bowing = bpf(rng.standard_normal(len(t)), 1500, 5000) * .04
    return (x * .3 + bowing) * vel


# ------------------------------------------------------------------ beds
def orbit(d):
    t = tv(d)
    hum = sum(a * np.sin(2 * np.pi * f * t) for f, a in [(55, .5), (110, .35), (165, .15), (220, .08)]) * (.8 + .2 * np.sin(2 * np.pi * .3 * t))
    radio = bpf(rng.standard_normal(len(t)), 1800, 7000) * .22
    return hum * .35 + radio
def wind(d, base=380, amt=1.0):
    n = len(tv(d)); w = lpf(np.cumsum(rng.standard_normal(n)) * .02, base, 2); w = hpf(w, 40)
    w /= np.abs(w).max() + 1e-9
    mod = .55 + .45 * np.interp(tv(d), np.linspace(0, d, 12), rng.random(12))
    return w * mod * amt
def rain(d, amt=1.0):
    n = len(tv(d)); x = bpf(rng.standard_normal(n), 1200, 9000) * .5 + lpf(rng.standard_normal(n), 900) * .25
    drops = np.zeros(n)
    for _ in range(int(d * 60)):
        i = rng.integers(0, n - 400); drops[i:i + 300] += bpf(rng.standard_normal(300), 2500, 8000) * np.exp(-np.arange(300) / 40) * rng.uniform(.2, .6)
    return (x + drops) * amt
def thunder(d=3.2, vel=1.0):
    t = tv(d); x = lpf(rng.standard_normal(len(t)), 160, 4) * 6
    e = (1 - np.exp(-t / .25)) * np.exp(-t / 1.1) * (1 + .5 * np.interp(t, np.linspace(0, d, 20), rng.random(20)))
    return hpf(x * e, 35) * vel
def wind_roar(d, vel=1.0):
    """aerodynamic roar rising through the dive: noise whose level and brightness climb"""
    n = len(tv(d)); x = rng.standard_normal(n); out = np.zeros(n); blk = 2048
    for i in range(0, n, blk):
        u = i / n; f = 300 + 3200 * u ** 1.5
        s = max(0, i - 4000); y = sosfilt(sos('low', f, 2), x[s:i + blk]); out[i:i + blk] = y[-(min(blk, n - i)):]
    return hpf(out, 60) * (0.15 + 0.85 * np.linspace(0, 1, n) ** 1.8) * vel


# ------------------------------------------------------------------ the score
chords = {'Dm': ['D3', 'F3', 'A3'], 'Bb': ['Bb2', 'D3', 'F3'], 'A': ['A2', 'C#3', 'E3'], 'Gm': ['G2', 'Bb2', 'D3'], 'Dm9': ['D3', 'F3', 'A3', 'E4'], 'D5': ['D3', 'A3', 'D4']}
def cm(name, up=0): return [mi(n) + up for n in chords[name]]


def score():
    # ---- opening (0 .. climb): no music; dry ticks on the beat from bar 2, very quiet
    for k in range(4, int(T['climb'] / BEAT)):
        put(PUL, tick(.18), k * BEAT, 1.0, .25 if k % 2 else -.25)
    # ---- the trip and the storm (climb .. hush): pulse bass in 8ths, chord per bar
    plan = [('Dm', 'D2'), ('Dm', 'D2'), ('Bb', 'Bb1'), ('A', 'A1'), ('Dm', 'D2'), ('Bb', 'Bb1'), ('Gm', 'G1'), ('A', 'A1')]
    t0 = T['climb']
    for k, (ch, root) in enumerate(plan):
        tb = t0 + k * 4 * BEAT; te = min(tb + 4 * BEAT, T['hush'])
        if tb >= T['hush']: break
        tp = tb
        while tp < te - .05:
            accent = abs((tp - tb) % (2 * BEAT)) < 1e-6
            put(MUS, bass(mi(root), .34, .62 if accent else .45, 360 if k < 4 else 300), tp, 1.0, 0)
            tp += BEAT / 2
        if tb >= T['climb'] + 3 * BEAT:            # the pad enters with the route; darker (lower cut) in the storm
            cut = 1800 if tb < T['storm0'] else 900
            put(MUS, pad(cm(ch, 12), te - tb + .3, .2 if tb < T['storm0'] else .26, cut, a=.4, r=.4), tb, 1.0, 0)
    # ticks: 8ths through the route, 16ths as 12:47 nears
    tp = T['route0']; k = 0
    while tp < T['hush'] - .02:
        div = .5 if tp < T['r1247'] + 2 * BEAT else .25
        put(PUL, tick(.22 if k % 2 == 0 else .14), tp, 1.0, .3 if k % 2 else -.3)
        tp += div * BEAT; k += 1
    # ---- the dive (dive0 .. impact): the one wet timbre rising, a low D pedal, a timpani roll that grows
    dd = T['impact'] - T['dive0']
    put(MUS, stereo(bowed_metal(dd + .05, mi('D4'), mi('A4'), .55) * env_curve(dd + .05, [(0, .35), (.6, .8), (1, 1)]), .0011), T['dive0'], 1.0)
    put(MUS, stereo(bowed_metal(dd + .05, mi('A3'), mi('D4'), .35) * env_curve(dd + .05, [(0, .2), (1, 1)]), .0017), T['dive0'] + .01, 1.0)
    put(MUS, stereo(S.note('tuba', 'D2', dd, vel=.55, attack=.6)), T['dive0'], .55)
    put(MUS, stereo(S.note('trombone', 'A2', dd - 2 * BEAT, vel=.45, attack=1.2)), T['dive0'] + 2 * BEAT, .4)
    tr = T['dive0'] + 8 * BEAT
    while tr < T['impact'] - .4:
        u = (tr - T['dive0'] - 8 * BEAT) / (T['impact'] - .4 - T['dive0'] - 8 * BEAT)
        put(HIT, S.note('timpani', 'D3', .5, vel=.18 + .55 * u ** 1.4), tr, .7, rng.uniform(-.2, .2))
        tr += (BEAT / 2) * (1 - .55 * u)
    # first sound after silence 1: a deep stroke as the dive begins
    put(HIT, S.note('timpani', 'D2', 2.2, vel=.75), T['dive0'], 1.0, 0)
    put(HIT, stereo(S.hit('gong', None, .45)[:int(3.0 * SR)]), T['dive0'] + .02, .35)
    # ---- the impact: a low brass stab, timpani, bass drum and the punch, then nothing
    ti = T['impact']
    put(HIT, punch(1.0), ti, 1.9, 0)
    put(HIT, S.note('timpani', 'D2', 2.6, vel=1.0), ti, 2.0, 0)
    put(HIT, stereo(S.hit('bass_drum', None, 1.0)), ti, 1.8)
    put(HIT, stereo(S.hit('gong', None, .8)[:int(3.5 * SR)]), ti + .01, .6)
    for inst, n_, v_ in (('tuba', 'D2', 1.0), ('trombone', 'D3', .95), ('trombone', 'F3', .8), ('horn_stac', 'A3', .9)):
        put(HIT, stereo(S.note(inst, n_, .7, vel=v_)), ti, 1.0)
    # ---- the site (impact .. out0): only the ground; a bowed vibraphone and a low pad return with the reading
    put(MUS, stereo(S.note('vibraphone_bowed', 'D4', 3.5, vel=.4)), T['res600'] - BEAT, .45)
    put(MUS, stereo(S.note('vibraphone_bowed', 'F4', 3.0, vel=.32)), T['res600'] + 3 * BEAT, .38)
    put(MUS, pad(cm('Dm', 0), T['out0'] - T['trail1'] + 1.0, .22, 600, a=2.0, r=1.0), T['trail1'], 1.0, 0)
    put(MUS, stereo(S.note('vibraphone_bowed', 'A4', 3.4, vel=.32)), T['breakup'], .38)
    # ---- the climb out and the end card: the pad opens, the bass once more, a low D, the tail
    put(MUS, pad(cm('Bb', 12), 3 * BEAT + .4, .2, 1200, a=1.0, r=.6), T['out0'], 1.0, 0)
    put(MUS, pad(cm('D5', 12), DUR - T['end'] + .4, .24, 1600, a=.8, r=2.0), T['end'], 1.0, 0)
    for k in range(int((T['end'] - T['out0']) / BEAT)):
        put(MUS, bass(mi('Bb1') if k < 3 else mi('A1'), .7, .4, 320), T['out0'] + k * BEAT, 1.0, 0)
    put(MUS, bass(mi('D2'), DUR - T['end'], .55, 300), T['end'], 1.0, 0)
    put(HIT, S.note('timpani', 'D3', 2.4, vel=.4), T['end'], .7, 0)
    put(MUS, stereo(S.note('vibraphone_bowed', 'D5', DUR - T['end'] - .3, vel=.35)), T['end'] + .4, .4)
    put(MUS, stereo(S.note('horn', 'D3', DUR - T['end'] - .5, vel=.35, attack=1.2)), T['end'] + .2, .4)


def foley():
    """Interface sounds only where a mark is made: the lock ping, stamps, readings landing, the mayday pings.
    Everything else the viewer hears is a real recording (beds())."""
    for e in EV:
        t, ty = e['t'], e['type']
        if ty == 'lock':
            put(FX, delay(ping(mi('D6'), .45, 1.6), BEAT * .5, .3, 2, 1.0), t)
        elif ty == 'lock_echo':
            put(FX, delay(ping(mi('D6'), .3, 2.0), BEAT * .5, .4, 4, 1.0), t)
        elif ty == 'stamp':
            put(FX, tock(.35), t, 1.0, .35)
        elif ty in ('mark', 'mark2'):
            put(FX, ping(mi('A5'), .2, 1.0), t, 1.0, .3 if ty == 'mark2' else -.3)
        elif ty == 'land':
            put(FX, tock(.4), t, 1.0, .35); put(FX, ping(mi('A5'), .28, 1.2), t, 1.0, .35)
        elif ty == 'alarm':           # mayday: two FM pings a minor second apart, after the spoken word
            put(FX, ping(mi('E6'), .25, .9), t, 1.0, -.2); put(FX, ping(mi('F6'), .25, .9), t + BEAT / 2, 1.0, .2)
        elif ty == 'end':
            put(FX, ping(mi('D5'), .25, 2.0), t, 1.0, 0)


# ------------------------------------------------------------------ real recordings (BigSoundBank, CC0: assets/sfx/)
SFX = os.path.join(HERE, 'assets/sfx')
def rec(name, lp=None, hp=None, rate=1.0):
    """decode a recording to 48 kHz stereo; rate < 1 plays it slower and lower (tape-style)"""
    import subprocess
    af = []
    if rate != 1.0: af += [f'asetrate={int(SR * rate)}', f'aresample={SR}']
    if hp: af += [f'highpass=f={hp}']
    if lp: af += [f'lowpass=f={lp}', f'lowpass=f={lp}']
    cmd = ['ffmpeg', '-v', 'error', '-i', os.path.join(SFX, name + '.mp3')] + (['-af', ','.join(af)] if af else []) + ['-f', 'f32le', '-ac', '2', '-ar', str(SR), '-']
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)
def act_level(x):
    """level while the recording sounds: 80th percentile of 0.25 s RMS windows"""
    m = x.mean(1); w = SR // 4
    r = [np.sqrt(np.mean(m[i:i + w] ** 2)) for i in range(0, max(1, len(m) - w), w)]
    return float(np.percentile(r, 80)) + 1e-9
def lay(buf, name, at, dur=None, db=-30.0, skip=0.0, fin=.6, fout=.8, env=None, **kw):
    """place a recording at `at` for `dur` s (looped with a crossfade if short), at `db` dBFS active RMS,
    with fades in/out and an optional gain envelope [(u, gain), ...] over its length"""
    x = rec(name, **kw)[int(skip * SR):]
    x = x * (10 ** (db / 20) / act_level(x))
    n = int((dur if dur else len(x) / SR) * SR)
    if len(x) < n:
        xf = min(SR, len(x) // 4); out = x.copy()
        while len(out) < n:
            r = np.linspace(0, 1, xf)[:, None]; out[-xf:] = out[-xf:] * (1 - r) + x[:xf] * r; out = np.concatenate([out, x[xf:]])
        x = out
    x = x[:n].copy()
    a, b_ = int(fin * SR), int(fout * SR)
    if a: x[:a] *= np.linspace(0, 1, a)[:, None] ** 1.5
    if b_: x[-b_:] *= np.linspace(1, 0, b_)[:, None] ** 1.5
    if env: x *= env_curve(n / SR, env)[:len(x), None]
    put(buf, x, at)


def beds():
    E = {e['type'] + str(i): e for i, e in enumerate(EV)}
    logs = [e['t'] for e in EV if e['type'] == 'log']
    # opening: the neighbourhood afterwards, a helicopter somewhere overhead, far away
    lay(BED, 'two-helicopters-flying-s0861', 0.0, T['climb'] + 1.0, db=-27, skip=4, fin=.4, fout=1.2, lp=2500)
    lay(BED, 'countryside-s0097', 0.0, T['climb'] + 1.0, db=-38, skip=10, fin=.4, fout=1.2, lp=6000)
    # the climb and the orbit: thin high-altitude air
    lay(BED, 'whistling-of-the-wind-1-s0147', T['climb'] - .3, T['storm0'] - T['climb'] + 1.5, db=-44, skip=20, fin=1.0, fout=1.2, lp=2200)
    # cruising at 35,000 ft: an airliner passing high overhead, under "cruising at thirty-five thousand feet"
    lay(BED, 'airplane-pass-4-s3007', T['cruise'] - 4.2, 9.5, db=-33, fin=.8, fout=1.5, lp=5000)
    # the storm: rain, and thunder heard before the storm is seen (J-cut); the rain thins in the silence
    st, en = T['storm0'] - 0.8, T['dive0'] + 1.2
    lay(BED, 'storm-and-rain-3-s2717', st, en - st, db=-37, skip=1.5, fin=1.2, fout=1.0, lp=7000,
        env=[(0, 1), ((T['hush'] - st) / (en - st), 1), ((T['hush'] + .4 - st) / (en - st), .55), (1, .55)])
    lay(BED, 'thunder-8-s3181', T['storm0'] - 1.0, 9.0, db=-30, fin=.05, fout=2.5, lp=4000)
    lay(BED, 'thunder-3-s3114', T['radar'][2] + .1, 8.0, db=-32, fin=.05, fout=2.0, lp=5000)
    lay(BED, 'thunder-s2718', T['req370'] - 1.6, 7.0, db=-34, fin=.05, fout=2.0, lp=5000)
    # the crew reports: a burst of radio for each line of the log
    for i, t in enumerate(logs):
        lay(FX, ['crackling-radio-1-s0312', 'crackling-radio-2-s0313'][i % 2], t - .05, 1.3, db=-34, skip=.3 * i, fin=.03, fout=.4, hp=300, lp=4500)
    # the dive: wind howling louder and higher, and a jet's roar slowed down, rising to the impact
    d0, d1 = T['dive0'], T['impact']
    lay(BED, 'wind-from-inside-1-s1714', d0, d1 - d0, db=-27, skip=8, fin=.8, fout=.02, lp=6000,
        env=[(0, .12), (.5, .4), (.85, .85), (1, 1)])
    lay(BED, 'airplane-pass-4-s3007', d0 + 1.0, d1 - d0 - 1.0, db=-27, fin=1.5, fout=.02, rate=.8, lp=5000,
        env=[(0, .3), (.6, .7), (1, 1)])
    lay(BED, 'airplane-pass-5-s3008', d1 - 6.2, 6.2, db=-25, skip=0.0, fin=2.0, fout=.02, rate=.85, lp=6000)
    # the impact: a distant, muffled explosion under the musical hit (kept far away)
    lay(HIT, 'explosion-far-away-s1023', T['impact'] - .02, 4.4, db=-16, fin=.0, fout=1.5, lp=1800)
    lay(HIT, 'explosion-far-away-2-s1806', T['impact'], .69, db=-18, fin=.0, fout=.3, lp=2500)
    # the site: helicopters over the scene, a low wind; they fade with the climb back out
    lay(BED, 'two-helicopters-flying-s0861', T['impact'] + 1.3, T['end'] - T['impact'] + .5, db=-34, skip=24, fin=1.6, fout=2.0, lp=3500)
    lay(BED, 'strong-wind-1-s0146', T['impact'] + .6, T['end'] - T['impact'], db=-44, skip=10, fin=1.5, fout=1.5, lp=1200)
    # the end card: high air again, very low
    lay(BED, 'whistling-of-the-wind-1-s0147', T['out0'], DUR - T['out0'] + .3, db=-46, skip=50, fin=1.5, fout=2.0, lp=2000)


def voice():
    for e in EV:
        if e['type'] != 'vo': continue
        x, sr = sf.read(os.path.join(HERE, 'voice/out', e['id'] + '.wav'))
        if x.ndim > 1: x = x.mean(1)
        x = soxr.resample(x, sr, SR)
        x = hpf(x, 90)
        x = X.compress(x / (np.abs(x).max() + 1e-9) * .9, thr=.22, ratio=3.2, att=.003, rel=.09)
        x = x + .04 * lpf(x, 3000)
        put(VOX, stereo(x, .0002), e['t'])


def rms(x): return float(np.sqrt(np.mean(x ** 2) + 1e-12))
def lufs(x):
    import subprocess, tempfile, re
    f = os.path.join(tempfile.mkdtemp(), 'm.wav'); sf.write(f, x.astype(np.float32), SR)
    out = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', f, '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True).stderr
    return float(re.findall(r'I:\s+(-?[\d.]+) LUFS', out)[-1])
def true_peak(x): return float(np.abs(soxr.resample(x, SR, 4 * SR)).max())
def tp_limit(x, ceil):
    from scipy.ndimage import maximum_filter1d, uniform_filter1d
    up = np.abs(soxr.resample(x, SR, 4 * SR)).max(1)
    n = len(x); pk = up[:n * 4].reshape(-1, 4).max(1) if len(up) >= n * 4 else np.pad(up, (0, n * 4 - len(up))).reshape(-1, 4).max(1)
    g = np.minimum(1.0, ceil / np.maximum(pk, 1e-9))
    look = int(.004 * SR)
    g = -maximum_filter1d(-g, 2 * look + 1)
    g = uniform_filter1d(g, look)
    g = np.minimum(g, -maximum_filter1d(-np.minimum(1.0, ceil / np.maximum(pk, 1e-9)), 3))
    return x * g[:, None]


def main():
    score(); foley(); beds(); voice()
    from scipy.ndimage import uniform_filter1d, maximum_filter1d
    mus = S.room(MUS, .6, .24); pul = S.room(PUL, .35, .14); hit = S.room(HIT, .75, .28)
    fx = FX.copy(); bed = BED.copy()
    v = np.abs(VOX).mean(1)
    env = uniform_filter1d(maximum_filter1d(v, int(.12 * SR)), int(.15 * SR)); env = np.clip(env / (env.max() + 1e-9) * 3, 0, 1)
    # silences: music, pulse and foley stop; hits ring on and decay; beds stay (thinner)
    for e in EV:
        if e['type'] == 'silence':
            a0, b = int(e['t'] * SR), int(e['to'] * SR)
            for buf, st, fd in ((mus, .02, .1), (pul, .02, .06), (fx, .3, .35), (hit, .6, 1.2)):
                a = int((e['t'] + st) * SR); fade = int(fd * SR)
                buf[a:a + fade] *= (np.linspace(1, 0, fade) ** 2)[:, None]; buf[a + fade:b] *= 0
    # suck-out before the impact: everything drops away for 0.35 s, then the hit lands
    i0, i1 = int((T['impact'] - .35) * SR), int((T['impact'] - .005) * SR); f = int(.05 * SR)
    g = np.ones(N); g[i0:i0 + f] = np.linspace(1, .05, f); g[i0 + f:i1] = .05
    for buf in (mus, pul, fx, bed): buf *= g[:, None]
    h = np.ones(N); h[i0:i0 + f] = np.linspace(1, .2, f); h[i0 + f:i1] = .2; hit *= h[:, None]
    speaking = env > .5
    g_mus, g_pul, g_hit, g_fx, g_bed = 0.22, 0.4, 0.75, 0.5, 1.0
    duck_m = (1 - .45 * env)[:, None]; duck_p = (1 - .3 * env)[:, None]; duck_h = (1 - .2 * env)[:, None]; duck_b = (1 - .35 * env)[:, None]
    stems = {'music': mus * g_mus * duck_m, 'pulse': pul * g_pul * duck_p, 'hits': hit * g_hit * duck_h,
             'fx': fx * g_fx * (1 - .4 * env)[:, None], 'beds': bed * g_bed * duck_b, 'voice': VOX}
    shelf = 10 ** (-5 / 20)
    for k in ('music', 'pulse', 'hits', 'beds', 'fx'):
        x = hpf(stems[k], 46 if k == 'hits' else 38, 4 if k == 'hits' else 2)
        stems[k] = x - (1 - shelf) * lpf(x, 62, 2)
    from scipy.ndimage import maximum_filter1d as mxf
    bus = stems['music'] + stems['pulse'] + stems['fx'] + stems['beds']
    lvl = np.sqrt(uniform_filter1d((bus ** 2).max(1), int(.012 * SR)))
    thr = 10 ** (-12 / 20) * np.percentile(lvl, 99.9)
    gg = np.where(lvl > thr, (thr + (lvl - thr) / 2.5) / np.maximum(lvl, 1e-9), 1.0)
    gg = uniform_filter1d(-mxf(-gg, int(.008 * SR)), int(.03 * SR))
    mix = bus * gg[:, None] + stems['hits'] + stems['voice']
    mix = mix[:int(DUR * SR)]
    fade = int(.6 * SR); mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
    for _ in range(3):
        I = lufs(mix); mix = mix * 10 ** ((-14.4 - I) / 20); mix = tp_limit(mix, 10 ** (-4.6 / 20))
    print(f'master: {lufs(mix):.2f} LUFS, true peak {20 * np.log10(true_peak(mix)):.2f} dBTP')
    vr = rms(stems['voice'][:int(DUR * SR)][speaking[:int(DUR * SR)]]); mr = rms((stems['music'] + stems['pulse'])[:int(DUR * SR)][speaking[:int(DUR * SR)]])
    print(f'voice over music while speaking: {20 * np.log10(vr / max(mr, 1e-9)):.1f} dB')
    os.makedirs(os.path.join(HERE, 'out/stems'), exist_ok=True)
    sf.write(os.path.join(HERE, 'out/mix.wav'), mix.astype(np.float32), SR)
    for name, b in stems.items():
        sf.write(os.path.join(HERE, 'out/stems', name + '.wav'), b[:int(DUR * SR)].astype(np.float32), SR)
    from numpy.fft import rfft, rfftfreq
    m = mix.mean(1); Fq = rfftfreq(len(m), 1 / SR); P = np.abs(rfft(m)) ** 2
    lo = P[(Fq > 20) & (Fq < 60)].sum(); rest = P[(Fq >= 20) & (Fq < 16000)].sum()
    print(f'20-60 Hz vs full band: {10 * np.log10(lo / rest):.1f} dB')


if __name__ == '__main__':
    main()
