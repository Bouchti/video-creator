"""
Narration per beat. Each beat is voiced on its own, so every reveal lands exactly on its words and a
long course never needs one giant TTS call. Files are cached by text hash inside the project, so a
re-render or a resumed run never pays twice.

Engines: `pipeline` (default) uses agents.voice.generate_voiceover with the repo's ElevenLabs keys and
free fallbacks; `silent` writes silence of the estimated length, for layout checks without TTS.
Word timings come from faster-whisper and are mapped onto the script's own words, so captions always
show the script spelling.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger("pipeline")
WORDS_PER_SECOND = 2.6      # silent-engine estimate, close to a calm coach at ~155 wpm


def _tool(name: str) -> str:
    """The repo's own ffmpeg resolution when available (agents.media), else PATH."""
    try:
        from agents.media import _tool_path
        return _tool_path(name)
    except Exception:
        return os.getenv(name.upper()) or shutil.which(name) or name


def ffmpeg() -> str:
    return _tool("ffmpeg")


def ffprobe() -> str:
    return _tool("ffprobe")


def duration(path: Path) -> float:
    out = subprocess.run([ffprobe(), "-v", "error", "-show_entries", "format=duration", "-of",
                          "default=nw=1:nk=1", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def _to_wav(src: str, dst: Path) -> None:
    subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", src, "-ac", "1", "-ar", "48000",
                    "-af", "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                           "silenceremove=start_periods=1:start_threshold=-50dB,areverse",
                    str(dst)], check=True)


def _silence(seconds: float, dst: Path) -> None:
    subprocess.run([ffmpeg(), "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
                    "-t", f"{seconds:.3f}", str(dst)], check=True)


def tokens(text: str) -> list[str]:
    return [t for t in re.split(r"\s+", text.strip()) if t]


def _even_words(words: list[str], total: float) -> list[dict]:
    if not words:
        return []
    weights = [max(1, len(re.sub(r"\W", "", w))) + 2 for w in words]
    scale = total / sum(weights)
    out, t = [], 0.0
    for w, k in zip(words, weights):
        out.append({"text": w, "start": round(t, 3), "end": round(t + k * scale, 3)})
        t += k * scale
    return out


def _mapped_words(words: list[str], heard: list[dict], total: float) -> list[dict]:
    """Script words with timings borrowed from Whisper's words by relative position."""
    if not heard:
        return _even_words(words, total)
    out = []
    for i, w in enumerate(words):
        j = min(len(heard) - 1, int(i * len(heard) / len(words)))
        out.append({"text": w, "start": float(heard[j]["start"]), "end": float(heard[j]["end"])})
    for a, b in zip(out, out[1:]):                       # strictly increasing starts for the caption timeline
        if b["start"] <= a["start"]:
            b["start"] = round(a["start"] + 0.04, 3)
    return out


def speak(text: str, audio_dir: Path, engine: str = "pipeline", voice: str | None = None) -> dict:
    """Voice one beat. Returns {"file", "duration", "words"} with words relative to the clip start."""
    audio_dir.mkdir(parents=True, exist_ok=True)
    voice = voice or os.getenv("PMP_VOICE", "storyteller")
    key = hashlib.sha1(f"{engine}|{voice}|{text}".encode("utf-8")).hexdigest()[:16]
    wav, meta = audio_dir / f"{key}.wav", audio_dir / f"{key}.json"
    if wav.is_file() and meta.is_file():
        return json.loads(meta.read_text(encoding="utf-8"))
    words = tokens(text)
    if engine == "silent":
        secs = max(0.8, len(words) / WORDS_PER_SECOND + 0.2)
        _silence(secs, wav)
        result = {"file": wav.name, "duration": round(secs, 3), "words": _even_words(words, secs - 0.1)}
    else:
        from agents.voice import generate_voiceover
        spoken = re.sub(r"\bpmpexamlab\.com\b", "P M P Exam Lab dot com", text, flags=re.I)
        src, _ = generate_voiceover(spoken, voice)
        try:
            _to_wav(src, wav)
        finally:
            try:
                os.remove(src)
            except OSError:
                pass
        secs = duration(wav)
        heard = []
        if os.getenv("PMP_WORD_TIMINGS", "whisper") == "whisper":
            try:
                from agents.transcription import transcribe_with_whisper
                heard = transcribe_with_whisper(str(wav))
            except Exception as exc:                       # captions fall back to even spacing
                log.warning("[pmp] whisper timings unavailable (%s); spacing words evenly", exc)
        result = {"file": wav.name, "duration": round(secs, 3), "words": _mapped_words(words, heard, secs)}
    meta.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result
