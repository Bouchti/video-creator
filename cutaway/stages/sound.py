"""
Stage 9 - the sound mix (audio/mix.wav, also placed in the HyperFrames project):

  voice   the narration, full level
  music   the bed, entered on a strong bar, ducked under the voice by a sidechain envelope
  engine  a real engine recording, looped and varispeeded so its pitch follows the on-screen crank speed
  sfx     the shot list's cues plus a spark on every visible spark event; each lands its peak one frame after
          the picture (light arrives before sound), with a small seeded pitch variation per repeat

Master: two-pass loudnorm to -14 LUFS integrated, -1 dBTP; measured afterwards with ebur128.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess

import numpy as np

from config.paths import get_ffmpeg

from .. import kits
from ..config import FPS
from ..runner import StageError
from .shotlist import theta_at

log = logging.getLogger("pipeline")
SR = 48000
TARGET_I, TARGET_TP = -14.0, -1.0
SFX_GAIN_DB = {"whoosh": -13, "ignition": -9, "spark": -13, "hiss": -15, "rumble": -17, "click": -15,
               "clunk": -13, "impact": -11, "riser": -16}
MAX_LEN = {"ignition": 1.4, "clunk": 0.9, "click": 0.35, "spark": 0.8, "impact": 1.6, "whoosh": 1.2,
           "hiss": 1.6, "rumble": 2.5, "riser": 2.5}          # seconds kept per hit, with a short fade-out
MUSIC_DB, MUSIC_DUCK_DB = -27.0, -9.0      # user, 2026-11-01: "the music is too loud"
BED_DB = -25.0


def inputs(run):
    return [run.path("voice", "narration.wav"), run.path("shotlist.json"), run.path("assets.json"),
            os.path.abspath(__file__)]


def load(path: str, sr: int = SR) -> np.ndarray:
    raw = subprocess.run([get_ffmpeg(), "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def save(path: str, stereo: np.ndarray):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = np.clip(stereo, -1, 1).astype(np.float32).tobytes()
    subprocess.run([get_ffmpeg(), "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-c:a", "pcm_s24le", path], input=data, check=True)


def db(x: float) -> float:
    return 10 ** (x / 20)


def envelope(x: np.ndarray, attack: float = 0.03, release: float = 0.35) -> np.ndarray:
    """Peak-follower envelope of |x| (0..1), for sidechain ducking."""
    win = int(0.02 * SR)
    rms = np.sqrt(np.convolve(x * x, np.ones(win) / win, mode="same"))
    a, r = np.exp(-1 / (attack * SR)), np.exp(-1 / (release * SR))
    out = np.empty_like(rms)
    level = 0.0
    step = 64                                   # follow in blocks: fast enough, smooth enough
    for i in range(0, len(rms), step):
        v = rms[i:i + step].max()
        k = a if v > level else r
        level = k ** step * level + (1 - k ** step) * v
        out[i:i + step] = level
    peak = np.percentile(out, 95) or 1.0
    return np.clip(out / peak, 0, 1)


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64)))) if len(x) else 0.0


def speech_rms(voice: np.ndarray, env: np.ndarray) -> float:
    """The narration's level while it speaks (pauses left out)."""
    active = voice[env > 0.3]
    return rms(active) or rms(voice) or 0.1


def music_bed(path: str, n: int, voice_env: np.ndarray, ref: float = 0.1) -> np.ndarray:
    """The music track levelled against the narration (`ref`: its speaking RMS) before the gain and duck: a
    mastered track is ~10 dB hotter than speech, so a raw -17 dB still sat almost level with the voice."""
    m = load(path)
    m = m * (ref / max(1e-6, rms(m)))
    win = 2 * SR
    bars = [float(np.sqrt(np.mean(m[i:i + win] ** 2))) for i in range(0, min(len(m) - win, 90 * SR), SR)]
    start = next((i for i, v in enumerate(bars) if v >= 0.8 * max(bars)), 0) * SR      # enter on a strong bar
    m = m[start:]
    while len(m) < n:
        m = np.concatenate([m, m])
    m = m[:n]
    fade_in, fade_out = int(0.4 * SR), int(1.8 * SR)
    m[:fade_in] *= np.linspace(0, 1, fade_in)
    m[-fade_out:] *= np.linspace(1, 0, fade_out)
    duck = db(MUSIC_DB) * (1 - (1 - db(MUSIC_DUCK_DB)) * voice_env)
    return m * duck


def engine_bed(path: str, n: int, crank_keys, voice_env: np.ndarray, ref: float = 0.1) -> np.ndarray:
    """Loop a recorded engine and varispeed it so pitch follows the on-screen crank speed (levelled against the
    narration like the music)."""
    src = load(path)
    src = src * (ref / max(1e-6, rms(src)))
    xf = int(0.25 * SR)
    loop = src.copy()
    loop[:xf] = loop[:xf] * np.linspace(0, 1, xf) + src[-xf:] * np.linspace(1, 0, xf)
    loop = loop[:-xf]
    t = np.arange(n) / SR
    dt = 1.0 / FPS
    speeds = []
    for k in range(int(n / SR * FPS) + 2):
        a, b = theta_at(crank_keys, k * dt), theta_at(crank_keys, k * dt + dt)
        speeds.append(max(0.0, (b - a) / dt))
    spd = np.interp(t, np.arange(len(speeds)) * dt, speeds)
    rate = np.clip(0.62 + 0.36 * np.log2(1 + spd / 120.0), 0.55, 1.9)          # deg/s -> playback rate
    gain = np.clip(spd / 90.0, 0, 1)                                             # silent when the crank stops
    phase = np.cumsum(rate)
    out = np.interp(phase % len(loop), np.arange(len(loop)), loop)
    return out * gain * db(BED_DB) * (1 - 0.5 * voice_env)


def place(track: np.ndarray, clip: np.ndarray, t: float, gain: float):
    """Add `clip` so its peak lands one frame after time t."""
    peak = int(np.argmax(np.abs(clip[: int(1.5 * SR)])))
    at = int((t + 1.0 / FPS) * SR) - peak
    a, b = max(0, at), min(len(track), at + len(clip))
    if b > a:
        track[a:b] += clip[a - at:b - at] * gain


def varied(clip: np.ndarray, seed: int) -> np.ndarray:
    r = 1.0 + ((seed * 7919) % 11 - 5) * 0.012                                  # +-6 % pitch
    idx = np.arange(0, len(clip) - 1, r)
    return np.interp(idx, np.arange(len(clip)), clip).astype(np.float32)


def cues(shotlist: dict, event_sfx: dict | None = None) -> list[tuple[float, str]]:
    out = []
    event_sfx = event_sfx or {}
    for s in shotlist["shots"]:
        for x in s.get("sfx_t", []):
            out.append((x["t"], x["cue"]))
        if s["cut"]["state"] != "closed":
            for e in s.get("events_t", []):
                cue = event_sfx.get(e["type"])
                if cue and not any(abs(t - e["t"]) < 0.15 for t, _c in out):
                    out.append((e["t"], cue))
        if s.get("transition") == "whip":
            out.append((s["start"] - 0.12, "whoosh"))
        if s.get("transition") == "flash":
            out.append((s["start"], "ignition"))
    return sorted(out)


def loudnorm(src: str, dst: str) -> dict:
    ff = get_ffmpeg()
    first = subprocess.run([ff, "-hide_banner", "-i", src, "-af",
                            f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA=11:print_format=json", "-f", "null", "-"],
                           capture_output=True, text=True, check=True).stderr
    m = json.loads(first[first.rindex("{"):first.rindex("}") + 1])
    af = (f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:"
          f"linear=true,alimiter=limit={db(TARGET_TP - 0.3):.4f}:attack=2:release=50:level=false")
    subprocess.run([ff, "-v", "error", "-y", "-i", src, "-af", af, "-ar", str(SR), "-c:a", "pcm_s24le", dst],
                   check=True)
    return measure(dst)


def measure(path: str) -> dict:
    out = subprocess.run([get_ffmpeg(), "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f",
                          "null", "-"], capture_output=True, text=True).stderr
    tail = out[out.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", tail)
    tp = re.search(r"Peak:\s+(-?[\d.]+) dBFS", tail)
    lra = re.search(r"LRA:\s+(-?[\d.]+) LU", tail)
    return {"I": float(i.group(1)) if i else None, "TP": float(tp.group(1)) if tp else None,
            "LRA": float(lra.group(1)) if lra else None}


def run(run):
    sl = run.need("shotlist.json")
    assets = run.need("assets.json")
    voice = load(run.path("voice", "narration.wav"))
    n = int(sl["duration"] * SR)
    voice = np.pad(voice, (0, max(0, n - len(voice))))[:n]
    env = envelope(voice)
    ref = speech_rms(voice, env)
    music = music_bed(assets["music"], n, env, ref)
    bed = engine_bed(assets["sfx"]["bed"], n, sl["crank"]["keys"], env, ref) if "bed" in assets["sfx"] else 0
    fx = np.zeros(n, dtype=np.float32)
    lib = {}
    placed = []
    event_sfx = kits.KITS[sl["kit"]].get("event_sfx", {})
    for k, (t, cue) in enumerate(cues(sl, event_sfx)):
        name = cue if cue in assets["sfx"] else ("impact" if cue == "clunk" else None)
        if name is None or name not in assets["sfx"]:
            continue
        if name not in lib:
            clip = load(assets["sfx"][name])
            keep = int(MAX_LEN.get(name, 3.0) * SR)
            if len(clip) > keep:
                clip = clip[:keep].copy()
                fade = min(int(0.15 * SR), keep // 3)
                clip[-fade:] *= np.linspace(1, 0, fade)
            lib[name] = clip
        place(fx, varied(lib[name], k), t, db(SFX_GAIN_DB.get(cue, -15)))
        placed.append({"t": round(t, 3), "cue": cue, "file": os.path.basename(assets["sfx"][name])})
    mono_fx = fx
    mix_l = voice + music + bed + mono_fx * 0.95
    mix_r = voice + music + bed + mono_fx * 0.95
    raw = run.path("audio", "mix_raw.wav")
    save(raw, np.stack([mix_l, mix_r], axis=1).reshape(-1))
    out = run.path("audio", "mix.wav")
    loud = loudnorm(raw, out)
    hf_mix = run.path("hf", "assets", "audio", "mix.wav")
    if os.path.isdir(run.path("hf")):
        os.makedirs(os.path.dirname(hf_mix), exist_ok=True)
        if os.path.exists(hf_mix):
            os.remove(hf_mix)
        shutil.copyfile(out, hf_mix)
    run.save("audio/audio.json", {"loudness": loud, "sfx": placed, "duration": sl["duration"]})
    log.info("[sound] mix %.1f LUFS, true peak %.1f dBTP, %d effects", loud["I"], loud["TP"], len(placed))


def validate(run):
    a = run.need("audio/audio.json")["loudness"]
    if a["I"] is None or abs(a["I"] - TARGET_I) > 1.0:
        raise StageError(f"mix loudness {a['I']} LUFS, want {TARGET_I} +-1")
    if a["TP"] is None or a["TP"] > TARGET_TP + 0.1:
        raise StageError(f"mix true peak {a['TP']} dBTP, want <= {TARGET_TP}")
