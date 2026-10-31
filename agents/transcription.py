"""Narration transcription and SRT generation."""

from __future__ import annotations

import logging

log = logging.getLogger("pipeline")
_whisper_model = None


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    return _whisper_model


def transcribe_with_whisper(audio_path: str) -> list:
    segments, _ = _get_whisper_model().transcribe(
        audio_path, word_timestamps=True, language="en", vad_filter=False,
    )
    words = [
        {"text": word.word.strip(), "start": word.start, "end": word.end}
        for segment in segments for word in segment.words
    ]
    log.info("Transcribed %d words", len(words))
    return words


def fmt_ts(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    whole = int(seconds % 60)
    milliseconds = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{whole:02d},{milliseconds:03d}"


def words_to_srt(words: list, srt_path: str):
    lines: list[str] = []
    counter = 1
    for index, word in enumerate(words):
        text = word["text"].strip().upper().lstrip(".,!?;:").rstrip(",;:")
        if not text:
            continue
        start = word["start"]
        end = words[index + 1]["start"] - 0.02 if index + 1 < len(words) else word["end"] + 0.1
        end = max(end, start + 0.08)
        lines.extend([str(counter), f"{fmt_ts(start)} --> {fmt_ts(end)}", text, ""])
        counter += 1
    with open(srt_path, "w", encoding="utf-8") as stream:
        stream.write("\n".join(lines))

