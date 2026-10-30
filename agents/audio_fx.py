"""
Sound design utilities for deliberately authored effects and an optional music
bed. Ordinary scene cuts stay silent.

Sound effects are synthesised here (no licensing questions). Music is optional:
drop royalty-free tracks into assets/music/ (or MUSIC_DIR) and one is picked at
random per video. TikTok's in-app trending sounds can also be added at posting.
"""
import os
import glob
import random
import wave
import logging
import subprocess

import numpy as np

from config.paths import PROJECT_ROOT
from agents.media import FFMPEG

log = logging.getLogger("pipeline")

SR = 44100
LOUDNESS_TARGET = float(os.getenv("LOUDNESS_TARGET", "-14"))   # integrated LUFS of every final mix
MUSIC_EXTS = (".mp3", ".wav", ".m4a", ".ogg")


def _whoosh(seconds: float = 0.45, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(SR * seconds)
    noise = rng.standard_normal(n)
    # Sweeping one-pole low-pass: the cutoff rises then falls → "whoosh".
    t = np.linspace(0, 1, n)
    cutoff = 300 + 5000 * np.sin(np.pi * t) ** 2
    alpha = 1 - np.exp(-2 * np.pi * cutoff / SR)
    out = np.empty(n)
    acc = 0.0
    for i in range(n):
        acc += alpha[i] * (noise[i] - acc)
        out[i] = acc
    env = np.sin(np.pi * t) ** 1.5
    out *= env / (np.abs(out).max() + 1e-9)
    return out * 0.35


def _pop(seconds: float = 0.09) -> np.ndarray:
    n = int(SR * seconds)
    t = np.arange(n) / SR
    freq = np.linspace(1100, 450, n)
    tone = np.sin(2 * np.pi * np.cumsum(freq) / SR)
    return tone * np.exp(-t * 38) * 0.4


def build_fx_track(total_seconds: float, cut_times: list, pop_times: list, path: str) -> str:
    """Mono WAV from explicitly authored whoosh and pop timestamps."""
    track = np.zeros(max(1, round(SR * total_seconds)))
    whoosh = _whoosh()

    def add(sound, at):
        i = max(0, int(at * SR))
        j = min(len(track), i + len(sound))
        if j > i:
            track[i:j] += sound[: j - i]

    for t in cut_times:
        add(whoosh, t - len(whoosh) / SR / 2)   # peak lands on the cut
    for t in pop_times:
        add(_pop(), t)
    track = np.clip(track, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((track * 32767).astype(np.int16).tobytes())
    return path


def pick_music():
    folder = os.getenv("MUSIC_DIR") or os.path.join(PROJECT_ROOT, "assets", "music")
    tracks = [p for p in glob.glob(os.path.join(folder, "*")) if p.lower().endswith(MUSIC_EXTS)]
    return random.choice(tracks) if tracks else None


def loudness(path: str) -> float:
    """Integrated loudness (LUFS) of a media file's audio; -70 when silent or unreadable."""
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostats", "-i", path, "-vn", "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True, timeout=300)
    lines = [ln for ln in r.stderr.splitlines() if ln.strip().startswith("I:") and "LUFS" in ln]
    try:
        return float(lines[-1].split()[1])
    except (IndexError, ValueError):
        return -70.0


def mix_audio(voice_path: str, fx_path: str, out_path: str, total_seconds: float, music: str = None) -> str:
    """Voice + effects (+ looped music bed if available) → AAC audio file.
    The music is side-chain DUCKED by the voice: it dips while words are spoken and swells
    back in the pauses, so it can sit louder without ever masking the narration."""
    music = music or pick_music()
    music_vol = float(os.getenv("MUSIC_VOLUME", "0.28"))
    cmd = [FFMPEG, "-y", "-i", voice_path, "-i", fx_path]
    filt = "[1:a]aresample=44100,volume=1.1[f];"
    if music:
        log.info(f"  Music bed: {os.path.basename(music)} (ducked under the voice)")
        cmd += ["-stream_loop", "-1", "-i", music]
        filt += ("[0:a]aresample=44100,asplit=2[v][key];"
                 f"[2:a]aresample=44100,volume={music_vol}[m0];"
                 "[m0][key]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400:makeup=1[m];"
                 "[v][f][m]amix=inputs=3:duration=longest:normalize=0[a]")
    else:
        filt += "[0:a]aresample=44100[v];[v][f]amix=inputs=2:duration=longest:normalize=0[a]"
    # Shorts platforms play at about -14 LUFS; a -22 LUFS mix sounds almost silent on a phone speaker.
    filt = filt.replace("[a]", "[raw]") + f";[raw]loudnorm=I={LOUDNESS_TARGET}:TP=-1.5:LRA=11,aresample=44100[a]"
    cmd += ["-filter_complex", filt, "-map", "[a]", "-t", f"{total_seconds:.3f}",
            "-c:a", "aac", "-b:a", "192k", out_path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"Audio mix failed: {r.stderr[-300:]}")
    return out_path
