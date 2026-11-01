"""
Stage 5 - words.json: word timestamps for every script word (Whisper on each beat, matched back to the script
words by cutaway's aligner, so captions and events use the words as written, at the times they are heard).
"""
from __future__ import annotations

import logging

from agents.transcription import transcribe_with_whisper
from cutaway.stages.align import align, norm, script_words

from ..runner import StageError

log = logging.getLogger("pipeline")


def inputs(run):
    return [run.path("voice", "voice.json"), run.path("script.json")]


def run(run):
    voice = run.need("voice/voice.json")
    script = run.need("script.json")
    words, beats, matched, total = [], [], 0, 0
    for vb, sb in zip(voice["beats"], script["beats"]):
        heard = transcribe_with_whisper(run.path(vb["file"]))
        toks = script_words(sb["narration"])
        times = align(toks, heard, vb["duration"])
        hn = {norm(h["text"]) for h in heard}
        matched += sum(1 for tk in toks if norm(tk) in hn)
        total += len(toks)
        first = len(words)
        for tok, (s, e) in zip(toks, times):
            words.append({"i": len(words), "text": tok, "start": round(vb["start"] + s, 3),
                          "end": round(vb["start"] + min(e, vb["duration"]), 3), "beat": sb["id"]})
        beats.append({"id": sb["id"], "start": vb["start"], "end": vb["end"], "first_word": first,
                      "last_word": len(words) - 1})
    run.save("words.json", {"duration": voice["duration"], "words": words, "beats": beats,
                            "match_rate": round(matched / max(1, total), 3)})
    log.info("[align] %d words, %.0f%% heard as written", len(words), 100 * matched / max(1, total))


def validate(run):
    w = run.need("words.json")
    if w["match_rate"] < 0.75:
        raise StageError(f"only {w['match_rate']:.0%} of the script was heard as written")
