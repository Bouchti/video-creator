"""
Stage 5 - words.json: every script word with its start and end in the narration.

Whisper word timestamps (agents.transcription, faster-whisper) are taken per beat file, then aligned to the
script's own words with a sequence match: the script's spelling and numbers are what is shown; Whisper only
supplies the clock. Words Whisper missed or misheard are interpolated between their matched neighbours.
Every later timing keys off these words (the spark fires on the word "fires").
"""
from __future__ import annotations

import difflib
import logging
import re

from agents.transcription import transcribe_with_whisper

from ..runner import StageError

log = logging.getLogger("pipeline")


def inputs(run):
    return [run.path("voice", "voice.json"), run.path("script.json")]


def norm(w: str) -> str:
    return re.sub(r"[^a-z0-9]", "", w.lower())


def script_words(text: str) -> list[str]:
    return [w for w in re.split(r"\s+", text.strip()) if w]


def align(script_tokens: list[str], heard: list[dict], duration: float) -> list[tuple[float, float]]:
    """Times (start, end) for each script token, relative to the beat file."""
    a = [norm(w) for w in script_tokens]
    b = [norm(h["text"]) for h in heard]
    times: list = [None] * len(a)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            h = heard[blk.b + k]
            times[blk.a + k] = (h["start"], h["end"])
    # replaced spans of equal length: take Whisper's times one to one (e.g. "2,500" heard as "2500")
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "replace" and (i2 - i1) == (j2 - j1):
            for k in range(i2 - i1):
                times[i1 + k] = (heard[j1 + k]["start"], heard[j1 + k]["end"])
    # interpolate the rest between neighbours, weighting by word length
    i = 0
    n = len(a)
    while i < n:
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < n and times[j] is None:
            j += 1
        t0 = times[i - 1][1] if i > 0 else 0.0
        t1 = times[j][0] if j < n else duration
        weights = [max(1, len(a[k])) for k in range(i, j)]
        total = sum(weights)
        t = t0
        for k, wgt in zip(range(i, j), weights):
            d = (t1 - t0) * wgt / total
            times[k] = (t, t + d)
            t += d
        i = j
    # monotonic, non-overlapping, minimum 50 ms
    out = []
    last = 0.0
    for s, e in times:
        s = max(s, last)
        e = max(e, s + 0.05)
        out.append((s, e))
        last = s
    return out


def run(run):
    voice = run.need("voice/voice.json")
    script = run.need("script.json")
    words, beats = [], []
    matched = total = 0
    for vb, sb in zip(voice["beats"], script["beats"]):
        heard = transcribe_with_whisper(run.path(vb["file"]))
        toks = script_words(sb["narration"])
        times = align(toks, heard, vb["duration"])
        hn = {norm(h["text"]) for h in heard}
        matched += sum(1 for t in toks if norm(t) in hn)
        total += len(toks)
        first = len(words)
        for tok, (s, e) in zip(toks, times):
            words.append({"id": f"w{len(words)}", "text": tok, "start": round(vb["start"] + s, 3),
                          "end": round(vb["start"] + min(e, vb["duration"]), 3), "beat": sb["id"]})
        beats.append({"id": sb["id"], "start": vb["start"], "end": vb["end"], "first_word": first,
                      "last_word": len(words) - 1})
    run.save("words.json", {"duration": voice["duration"], "words": words, "beats": beats,
                            "match_rate": round(matched / max(1, total), 3)})
    log.info("[align] %d words, %.0f%% heard as written", len(words), 100 * matched / max(1, total))


def validate(run):
    w = run.need("words.json")
    if w["match_rate"] < 0.75:
        raise StageError(f"only {w['match_rate']:.0%} of the script was heard: the voice misread it")
    prev = -1.0
    for x in w["words"]:
        if x["start"] < prev - 1e-6 or x["end"] < x["start"]:
            raise StageError(f"word times not monotonic at {x['id']}")
        prev = x["start"]
