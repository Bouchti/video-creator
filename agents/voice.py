"""ElevenLabs narration service with safe key rotation and quota checks."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime

import requests

from config.paths import PROJECT_ROOT, get_temp_dir
from agents.media import get_duration

log = logging.getLogger("pipeline")

VOICES = {
    "energetic": "TX3LPaxmHKxFdv7VOQHJ",
    "mysterious": "JBFqnCBsd6RMkjVDRZzb",   # George, warm captivating storyteller (was Charlie, too hyped)
    "storyteller": "JBFqnCBsd6RMkjVDRZzb",
}
_ROTATION_FILE = os.path.join(get_temp_dir(), "elevenlabs_rotation.json")
_RETRYABLE = (
    "quota_exceeded", "invalid_api_key", "detected_unusual_activity",
    "too_many_concurrent_requests", "system_busy", "payment_required",
    "unusual_activity", "max_character_limit_exceeded",
)


def elevenlabs_keys() -> list[tuple[str, str]]:
    names = ["ELEVENLABS_API_KEY"] + [f"ELEVENLABS_API_KEY_{index}" for index in range(2, 21)]
    result, seen = [], set()
    for name in names:
        key = (os.getenv(name) or "").strip()
        if key and key not in seen:
            result.append((name, key))
            seen.add(key)
    return result



def _rotation_start(size: int) -> int:
    try:
        with open(_ROTATION_FILE, encoding="utf-8") as stream:
            return int(json.load(stream).get("index", 0)) % max(size, 1)
    except (OSError, ValueError, json.JSONDecodeError):
        return 0


def _rotation_save(index: int) -> None:
    try:
        with open(_ROTATION_FILE, "w", encoding="utf-8") as stream:
            json.dump({"index": index}, stream)
    except OSError:
        pass


def credit_status(key: str) -> dict:
    """Return a non-secret readiness result for one ElevenLabs key."""
    try:
        response = requests.get(
            "https://api.elevenlabs.io/v1/user/subscription",
            headers={"xi-api-key": key}, timeout=15,
        )
        if response.status_code != 200:
            return {"valid": False, "remaining": None, "status_code": response.status_code}
        value = response.json()
        return {
            "valid": True,
            "remaining": int(value.get("character_limit", 0)) - int(value.get("character_count", 0)),
            "status_code": response.status_code,
        }
    except (requests.RequestException, ValueError) as exc:
        return {"valid": False, "remaining": None, "error": type(exc).__name__}


def _credits_left(key: str):
    status = credit_status(key)
    return status["remaining"] if status["valid"] else None


def elevenlabs_post(url: str, payload: dict, characters: int = 0, timeout: int = 60):
    """POST to ElevenLabs with the first configured key that has `characters` credits left, starting from the
    key that worked last time; a 429 is retried once and an unusable key moves on to the next one.
    ELEVENLABS_DISABLED=1 refuses every call (test runs: the voice uses VOICE_ENGINE, effects the free libraries)."""
    if os.getenv("ELEVENLABS_DISABLED") == "1":
        raise RuntimeError("ElevenLabs is disabled (ELEVENLABS_DISABLED=1)")
    keys = elevenlabs_keys()
    if not keys:
        raise RuntimeError("No ElevenLabs key configured (ELEVENLABS_API_KEY, ELEVENLABS_API_KEY_2, ...)")
    start = _rotation_start(len(keys))
    order = [(start + offset) % len(keys) for offset in range(len(keys))]
    credits = {index: _credits_left(keys[index][1]) for index in order}
    order = [i for i in order if credits[i] is None or credits[i] >= characters] + [
        i for i in order if credits[i] is not None and credits[i] < characters
    ]
    errors: list[str] = []
    for index in order:
        name, key = keys[index]
        if credits[index] is not None and credits[index] < characters:
            errors.append(f"{name}: only {credits[index]} credits left")
            continue
        headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": key}
        for attempt in range(2):
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            if response.status_code == 429 and attempt == 0:
                time.sleep(5)
                continue
            break
        if response.status_code == 200:
            _rotation_save(index)
            log.info("ElevenLabs key: %s", name)
            return response
        body = response.text[:300]
        if response.status_code in (401, 402, 403, 429) or any(value in body for value in _RETRYABLE):
            errors.append(f"{name}: {response.status_code} {body[:120]}")
            log.warning("ElevenLabs %s unusable (%s); trying the next key", name, response.status_code)
            continue
        raise RuntimeError(f"ElevenLabs failed ({name}): {response.status_code} {body}")
    raise RuntimeError("All ElevenLabs keys are out of credits or unusable: " + " | ".join(errors))


EDGE_VOICES = {                         # free Microsoft neural voices (fallback when ElevenLabs cannot speak)
    "energetic": "en-US-AndrewMultilingualNeural",
    "mysterious": "en-US-ChristopherNeural",
    "storyteller": "en-US-BrianMultilingualNeural",
}
_BREAK = re.compile(r'<break\s+time="([\d.]+)s"\s*/>')
_EDGE_RATE = 24000


def _edge_voiceover(spoken_script: str, voice: str) -> str:
    """Narration from Edge's free neural voices. Edge reads no SSML, so the ElevenLabs <break> tags between
    beats become real silences: each part is spoken separately and joined with pauses of the tagged length
    (the film's beat timing depends on them)."""
    import asyncio
    import subprocess

    import ssl

    import edge_tts
    import edge_tts.communicate
    import numpy as np

    from agents.media import FFMPEG
    # edge_tts verifies against certifi's bundle only. On this machine Norton's Web Shield re-signs HTTPS
    # with a root that only the Windows store holds, so every Edge call failed certificate verification
    # and an unattended video stopped at its narration. The OS store holds the public roots too.
    edge_tts.communicate._SSL_CTX = ssl.create_default_context()
    name = os.getenv("EDGE_TTS_VOICE") or EDGE_VOICES.get(voice, EDGE_VOICES["energetic"])
    rate = f"{round((float(os.getenv('VOICE_SPEED', '0.92')) - 1) * 100):+d}%"
    pieces = _BREAK.split(spoken_script)                 # text, pause, text, pause, ..., text
    stamp = f"{datetime.now():%Y%m%d_%H%M%S_%f}"
    pcm = []
    for k, piece in enumerate(pieces):
        if k % 2:                                        # a pause length from a <break> tag
            pcm.append(np.zeros(int(float(piece) * _EDGE_RATE), dtype=np.int16))
            continue
        text = piece.strip()
        if not text:
            continue
        part = os.path.join(get_temp_dir(), f"edge_{stamp}_{k}.mp3")
        for attempt in range(3):
            try:
                asyncio.run(edge_tts.Communicate(text, name, rate=rate).save(part))
                break
            except Exception as exc:                     # noqa: BLE001  network hiccups: retry, then report
                if attempt == 2:
                    raise RuntimeError(f"Edge TTS failed: {exc}") from exc
                time.sleep(3 * (attempt + 1))
        raw = subprocess.run([FFMPEG, "-v", "error", "-i", part, "-ac", "1", "-ar", str(_EDGE_RATE), "-f", "s16le",
                              "-"], capture_output=True, check=True).stdout
        os.remove(part)
        pcm.append(np.frombuffer(raw, dtype=np.int16))
    if not pcm:
        raise RuntimeError("Edge TTS produced no audio")
    path = os.path.join(get_temp_dir(), f"voiceover_{stamp}.mp3")
    subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "s16le", "-ar", str(_EDGE_RATE), "-ac", "1", "-i", "-",
                    "-c:a", "libmp3lame", "-b:a", "128k", path], input=np.concatenate(pcm).tobytes(), check=True)
    log.info("Narration voiced by Edge (%s)", name)
    return path


CHATTERBOX_STYLES = {                   # (exaggeration, cfg_weight): livelier and faster vs. calmer and slower
    "energetic": (0.6, 0.4),
    "mysterious": (0.4, 0.5),
    "storyteller": (0.5, 0.5),
    "playful": (0.75, 0.4),
    "calm": (0.4, 0.5),
    "dramatic": (0.8, 0.35),
}

_DRAMATIC = re.compile(r"\b(?:secret|danger\w*|grave|death|died|dead|kill\w*|never|nobody|suddenly|disaster|"
                       r"explo\w*|burst|collaps\w*|vanish\w*|trap\w*|fake|lie|lied|spy|spies|enemy|war)\b", re.I)


def delivery_plan(spoken_script: str, voice: str = "mysterious") -> list[tuple[str, dict]]:
    """Each sentence with the way it is said: the hook lively, a short fragment punched with a beat after it,
    a dramatic line slower and heavier, a question rising with room before it, plain narration level.

    One setting for the whole script made the Ghost Army narration sound like a robot reading a list
    (user, 2026-10-31: "it doesn't switch the tone between question, actions, something dramatic").
    """
    base_ex, base_cfg = CHATTERBOX_STYLES.get(voice, CHATTERBOX_STYLES["mysterious"])
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", spoken_script.strip()) if s.strip()]
    plan = []
    for index, sentence in enumerate(sentences):
        words = len(re.findall(r"[\w'-]+", sentence))
        if sentence.endswith("?"):
            delivery = {"exaggeration": 0.65, "cfg_weight": 0.4, "pause_after": 0.6}
            if index == len(sentences) - 1 and plan:
                plan[-1][1]["pause_after"] = max(plan[-1][1]["pause_after"], 0.55)   # a beat before the closer
        elif index == 0:
            delivery = {"exaggeration": 0.7, "cfg_weight": 0.35, "pause_after": 0.45}
        elif sentence.endswith("!"):
            delivery = {"exaggeration": 0.8, "cfg_weight": 0.3, "pause_after": 0.4}
        elif words <= 3:
            delivery = {"exaggeration": 0.75, "cfg_weight": 0.3, "pause_after": 0.45}
        elif _DRAMATIC.search(sentence):
            delivery = {"exaggeration": 0.65, "cfg_weight": 0.3, "pause_after": 0.4}
        else:
            delivery = {"exaggeration": base_ex + 0.1, "cfg_weight": base_cfg, "pause_after": 0.3}
        plan.append((sentence, delivery))
    # Chatterbox garbles a fragment spoken alone ("Painters." came back "Hainters", "Sculptors." as
    # "Helpeders"): a run of short fragments is spoken together, joined to the sentence before it.
    merged: list[tuple[str, dict]] = []
    for sentence, delivery in plan:
        short = len(re.findall(r"[\w'-]+", sentence)) <= 3 and not sentence.endswith("?")
        if short and merged:
            previous, kept = merged[-1]
            merged[-1] = (f"{previous} {sentence}", {**kept, "exaggeration": max(kept["exaggeration"],
                                                                              delivery["exaggeration"]),
                                                     "cfg_weight": min(kept["cfg_weight"], delivery["cfg_weight"]),
                                                     "pause_after": delivery["pause_after"]})
        else:
            merged.append((sentence, delivery))
    return merged


def _venv_python(name: str, env: str) -> str:
    """A local voice's own interpreter: each pins its own torch in a separate venv, never the pipeline's."""
    default = os.path.join(os.getenv("LOCALAPPDATA") or os.path.expanduser("~"), "VideoCreator", name, "venv",
                           "Scripts" if os.name == "nt" else "bin", "python.exe" if os.name == "nt" else "python")
    return os.getenv(env) or default


def chatterbox_python() -> str:
    """The Chatterbox venv: CHATTERBOX_PYTHON, else the per-user one, else tools/chatterbox/.venv (agents.libraries)."""
    chosen = _venv_python("chatterbox", "CHATTERBOX_PYTHON")
    bundled = os.path.join(PROJECT_ROOT, "tools", "chatterbox", ".venv", "Scripts" if os.name == "nt" else "bin",
                           "python.exe" if os.name == "nt" else "python")
    return chosen if os.getenv("CHATTERBOX_PYTHON") or os.path.isfile(chosen) or not os.path.isfile(bundled)         else bundled


def chatterbox_available() -> bool:
    return os.path.isfile(chatterbox_python())


def kokoro_python() -> str:
    return _venv_python("kokoro", "KOKORO_PYTHON")


def kokoro_available() -> bool:
    return os.path.isfile(kokoro_python())


KOKORO_VOICES = {                       # chosen by the user from narrated samples (2026-10-30)
    "energetic": "af_bella",
    "mysterious": "am_michael",
    "storyteller": "am_michael",
}


def _run_local_tts(engine: str, python: str, settings: dict, spoken_script: str) -> str:
    """Speak the script with a local engine's worker (agents/<engine>_worker.py) in its own venv.

    The <break> tags become real silences, as for Edge; the WAV it writes becomes the narration MP3.
    """
    import subprocess

    from agents.media import FFMPEG
    pieces = _BREAK.split(spoken_script)
    parts = [["pause", float(p)] if k % 2 else ["text", p.strip()]
             for k, p in enumerate(pieces) if k % 2 or p.strip()]
    style = settings.pop("style", None)
    if style:                             # one delivery per sentence (see delivery_plan)
        planned = []
        for kind, value in parts:
            if kind == "pause":
                planned.append([kind, value])
            else:
                planned += [["text", sentence, delivery] for sentence, delivery in delivery_plan(value, style)]
        parts = planned
    stamp = f"{datetime.now():%Y%m%d_%H%M%S_%f}"
    wav = os.path.join(get_temp_dir(), f"{engine}_{stamp}.wav")
    job = os.path.join(get_temp_dir(), f"{engine}_{stamp}.json")
    parts_dir = os.path.join(get_temp_dir(), f"{engine}_{stamp}_parts") if style else ""
    worker = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{engine}_worker.py")

    def speak(job_parts: list, round_: int) -> dict:
        directory = os.path.join(parts_dir, str(round_)) if parts_dir else ""
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(job, "w", encoding="utf-8") as stream:
            json.dump({"parts": job_parts, "output": wav, "parts_dir": directory, **settings}, stream)
        done = subprocess.run([python, worker, job], capture_output=True, text=True,
                              timeout=int(os.getenv(f"{engine.upper()}_TIMEOUT") or 1800))
        if done.returncode != 0 or not os.path.isfile(wav):
            raise RuntimeError(f"{engine} failed: {(done.stderr or done.stdout)[-600:]}")
        try:
            return json.loads(done.stdout.strip().splitlines()[-1])
        except (IndexError, ValueError):
            return {}

    try:
        report = speak(parts, 0)
        if style:
            # Each planned sentence is heard back; one with an invented or garbled word is said again,
            # the rest are reused as they are (Ghost Army: "Shell, if discovered...", "Hainters").
            for round_ in (1, 2):
                spoken = {int(k): v for k, v in (report.get("parts") or {}).items()}
                wrong = {n for n, path in spoken.items() if _misspoken(parts[n][1], path)}
                if not wrong:
                    break
                log.info("Narration: %d sentence(s) misspoken, saying them again: %s", len(wrong),
                         "; ".join(parts[n][1][:50] for n in sorted(wrong)))
                kept = [["wav", spoken[n], part[2]] if n in spoken and n not in wrong else part
                        for n, part in enumerate(parts)]
                report = speak(kept, round_)
                for n, path in spoken.items():        # unchanged parts keep their checked file
                    report.setdefault("parts", {}).setdefault(str(n), path)
        path = os.path.join(get_temp_dir(), f"voiceover_{stamp}.mp3")
        subprocess.run([FFMPEG, "-v", "error", "-y", "-i", wav, "-ac", "1", "-c:a", "libmp3lame", "-b:a", "160k",
                        path], check=True)
    finally:
        for leftover in (wav, job):
            if os.path.isfile(leftover):
                os.remove(leftover)
        if parts_dir:
            import shutil
            shutil.rmtree(parts_dir, ignore_errors=True)
    log.info("Narration voiced by %s (%s)", engine, {k: v for k, v in report.items() if k != "parts"})
    return path


_NUMBER_WORDS = {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
                 "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
                 "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred",
                 "thousand", "million", "billion", "and", "first", "second", "third"}


def _misspoken(sentence: str, wav_path: str) -> bool:
    """Whisper hears a word the sentence does not have, or misses words it has.

    Numbers are left out on both sides ("eleven hundred" is heard as "1100"), and words are matched inside
    the run-together letters so "clotheslines" heard as "clothes lines" still matches.
    """
    from agents.transcription import transcribe_with_whisper
    try:
        heard_words = [w["text"] for w in transcribe_with_whisper(wav_path)]
    except Exception as exc:                  # noqa: BLE001 - the check only improves the take
        log.warning("Narration check unavailable (%s)", exc.__class__.__name__)
        return False

    def tokens(text: str) -> list[str]:
        return [t for t in re.findall(r"[a-z]+", text.lower().replace("'", "")) if t not in _NUMBER_WORDS]

    expected, heard = tokens(sentence), tokens(" ".join(heard_words))
    expected_letters, heard_letters = "".join(expected), "".join(heard)
    extra = [t for t in heard if len(t) > 2 and t not in expected_letters]
    missing = [t for t in expected if len(t) > 3 and t not in heard_letters]
    return bool(extra) or len(missing) >= 2


def _kokoro_voiceover(spoken_script: str, voice: str) -> str:
    """Narration from Kokoro-82M (Apache 2.0, top of the open-weights TTS rankings): free, offline, on CPU,
    so it never competes with the video model for the GPU."""
    if not kokoro_available():
        raise RuntimeError(f"Kokoro is not installed at {kokoro_python()} (set KOKORO_PYTHON)")
    return _run_local_tts("kokoro", kokoro_python(), {
        "voice": os.getenv("KOKORO_VOICE") or KOKORO_VOICES.get(voice, KOKORO_VOICES["mysterious"]),
        "speed": float(os.getenv("KOKORO_SPEED") or 1.0)}, spoken_script)


def _chatterbox_voiceover(spoken_script: str, voice: str) -> str:
    """Narration from Chatterbox, an open-source local TTS: free, offline, no quota."""
    if not chatterbox_available():
        raise RuntimeError(f"Chatterbox is not installed at {chatterbox_python()} (set CHATTERBOX_PYTHON)")
    exaggeration, cfg_weight = CHATTERBOX_STYLES.get(voice, CHATTERBOX_STYLES["energetic"])
    path = _run_local_tts("chatterbox", chatterbox_python(), {
        "device": os.getenv("CHATTERBOX_DEVICE") or "auto",
        "exaggeration": float(os.getenv("CHATTERBOX_EXAGGERATION") or exaggeration),
        "cfg_weight": float(os.getenv("CHATTERBOX_CFG") or cfg_weight),
        "voice_prompt": os.getenv("CHATTERBOX_VOICE") or "",
        "sentence_pause": float(os.getenv("CHATTERBOX_SENTENCE_PAUSE") or 0.4),
        **({"style": voice} if os.getenv("CHATTERBOX_EXPRESSIVE", "1") != "0" else {})}, spoken_script)
    # Chatterbox speaks ~3 words/s even with the beat pauses (the published films: ~2.4); a 0.92 tempo
    # (VOICE_SPEED, as the other voices) keeps the lively read at ~2.73 words/s.
    tempo = min(1.5, max(0.7, float(os.getenv("VOICE_SPEED") or 0.92)))
    if abs(tempo - 1) > 0.005:
        import subprocess

        from agents.media import FFMPEG
        slow = path[:-4] + "_tempo.mp3"
        subprocess.run([FFMPEG, "-v", "error", "-y", "-i", path, "-filter:a", f"atempo={tempo:.3f}",
                        "-c:a", "libmp3lame", "-b:a", "160k", slow], check=True)
        os.replace(slow, path)
    return path


FREE_VOICES = {"kokoro": ("kokoro", "chatterbox", "edge"), "chatterbox": ("chatterbox", "edge"), "edge": ("edge",)}


def _fallback_voiceover(spoken_script: str, voice: str, fallback: str) -> str:
    """The free voice used when ElevenLabs cannot speak: the chosen engine, then the next one if it fails
    or is not installed, ending with Edge, so a video never stops at its narration."""
    import sys
    engines = FREE_VOICES.get(fallback, ("edge",))
    for engine in engines[:-1]:
        try:
            return getattr(sys.modules[__name__], f"_{engine}_voiceover")(spoken_script, voice)
        except Exception as exc:              # noqa: BLE001
            log.warning("%s voice unavailable (%s); trying the next free voice", engine, str(exc)[:200])
    return getattr(sys.modules[__name__], f"_{engines[-1]}_voiceover")(spoken_script, voice)


def generate_voiceover(spoken_script: str, voice: str = "energetic") -> tuple[str, float]:
    if not spoken_script.strip():
        raise ValueError("Narration is empty")
    provider = (os.getenv("VOICE_PROVIDER") or "auto").strip().lower()
    if provider not in ("auto", *FREE_VOICES, "elevenlabs"):
        raise ValueError("VOICE_PROVIDER must be auto, kokoro, chatterbox, edge or elevenlabs")
    if provider in FREE_VOICES:
        path = _fallback_voiceover(spoken_script, voice, provider)
        return path, get_duration(path)
    fallback = (os.getenv("VOICE_FALLBACK") or "edge").strip().lower()
    free = fallback in FREE_VOICES
    # VOICE_ENGINE: elevenlabs (default, premium) | chatterbox / kokoro (free, local) | edge (free, online).
    # A free engine chosen here speaks first and the next free voice covers it, so a run never loses its voice.
    engine = (os.getenv("VOICE_ENGINE") or "elevenlabs").strip().lower()
    if engine in FREE_VOICES:
        path = _fallback_voiceover(spoken_script, voice, engine)
        return path, get_duration(path)
    if not elevenlabs_keys() and provider != "elevenlabs":
        if free:
            path = _fallback_voiceover(spoken_script, voice, fallback)
            return path, get_duration(path)
        raise RuntimeError("ELEVENLABS_API_KEY is not configured")
    if not elevenlabs_keys():
        raise RuntimeError("ELEVENLABS_API_KEY is not configured")
    try:
        path = _elevenlabs_voiceover(spoken_script, voice)
    except RuntimeError as exc:
        # out of credits on every key: a video must not stop for weeks waiting for a quota reset
        if not free or "out of credits or unusable" not in str(exc):
            raise
        log.warning("ElevenLabs unavailable (%s); using the %s voice fallback", str(exc)[:160], fallback)
        path = _fallback_voiceover(spoken_script, voice, fallback)
    return path, get_duration(path)


def _elevenlabs_voiceover(spoken_script: str, voice: str) -> str:
    voice_id = VOICES.get(voice, VOICES["energetic"])
    payload = {
        "text": spoken_script,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.4,
            "similarity_boost": 0.75,
            "style": 0.6,
            "use_speaker_boost": True,
            "speed": float(os.getenv("VOICE_SPEED", "0.92")),
        },
    }
    response = elevenlabs_post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}", payload, len(spoken_script),
    )
    path = os.path.join(get_temp_dir(), f"voiceover_{datetime.now():%Y%m%d_%H%M%S_%f}.mp3")
    with open(path, "wb") as stream:
        stream.write(response.content)
    return path
