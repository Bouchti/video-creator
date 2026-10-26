"""ElevenLabs narration service with safe key rotation and quota checks."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime

import requests

from config.paths import get_temp_dir
from agents.media import get_duration

log = logging.getLogger("pipeline")

VOICES = {
    "energetic": "TX3LPaxmHKxFdv7VOQHJ",
    "mysterious": "IKne3meq5aSn9XLyUdCD",
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


_elevenlabs_keys = elevenlabs_keys


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


def _tts_with_rotation(url: str, payload: dict, characters: int):
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
            response = requests.post(url, json=payload, headers=headers, timeout=60)
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


def generate_voiceover(spoken_script: str, voice: str = "energetic") -> tuple[str, float]:
    if not spoken_script.strip():
        raise ValueError("Narration is empty")
    if not elevenlabs_keys():
        raise RuntimeError("ELEVENLABS_API_KEY is not configured")
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
    response = _tts_with_rotation(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}", payload, len(spoken_script),
    )
    path = os.path.join(get_temp_dir(), f"voiceover_{datetime.now():%Y%m%d_%H%M%S_%f}.mp3")
    with open(path, "wb") as stream:
        stream.write(response.content)
    return path, get_duration(path)
