"""
Beat schema helpers.

A beat is one sentence/clause of narration plus the ONE visual shown while those
words are spoken. The voiceover is the beat texts joined in order, so narration
and visuals can never drift apart. Timing comes from Whisper word timestamps:
each beat's visual starts exactly when its first word is heard.
"""
import math
import re
from difflib import SequenceMatcher

FPS = 30

VISUAL_KINDS = ("scene", "footage", "photo", "diagram")
OVERLAY_TYPES = ("stat", "label")
DIAGRAM_TEMPLATES = ("key_phrase", "stat", "process", "timeline", "comparison")

# Footage beats longer than this are cut into several shots so no single shot
# lingers long enough to bore the viewer.
MAX_SHOT_SECONDS = 3.5
MIN_BEAT_SECONDS = 0.6
# Cut to the next visual a hair before its first word — reads as "on the beat".
LEAD_SECONDS = 0.1

_WORD = re.compile(r"[a-z0-9]+")


def get_beats(script: dict) -> list:
    beats = script.get("beats") if isinstance(script, dict) else None
    return beats if isinstance(beats, list) else []


def get_visual(beat: dict) -> dict:
    visual = beat.get("visual") if isinstance(beat, dict) else None
    return visual if isinstance(visual, dict) else {}


def narration_from_beats(beats: list) -> str:
    return " ".join(b["text"].strip() for b in beats
                    if isinstance(b.get("text"), str) and b["text"].strip())


_KIND_ALIASES = {
    "stock": "footage", "video": "footage", "clip": "footage", "b-roll": "footage", "broll": "footage",
    "image": "photo", "picture": "photo", "still": "photo",
    "chart": "diagram", "graphic": "diagram", "infographic": "diagram", "text": "diagram",
}


_OVERLAY_ALIASES = {"number": "stat", "statistic": "stat", "counter": "stat",
                    "text": "label", "name": "label", "title": "label", "caption": "label"}


def repair_beats(beats: list, scene_mode: bool = False) -> list:
    """Fix the small schema slips the model sometimes makes, in place.

    A misspelled or missing visual kind is mapped to its obvious meaning (or
    inferred from the fields present) instead of failing the whole script. In
    scene mode every beat is a generated scene, whatever kind was written.
    """
    for beat in beats:
        v = get_visual(beat)
        if not v:
            continue
        overlay = v.get("overlay")
        if isinstance(overlay, dict):
            otype = str(overlay.get("type") or "").strip().lower()
            overlay["type"] = _OVERLAY_ALIASES.get(otype, otype)
            if overlay["type"] not in OVERLAY_TYPES:
                v.pop("overlay")
        elif overlay is not None:
            v.pop("overlay")
        if scene_mode:
            v["kind"] = "scene"
            continue
        kind = str(v.get("kind") or "").strip().lower()
        kind = _KIND_ALIASES.get(kind, kind)
        if kind not in VISUAL_KINDS:
            if v.get("template") in DIAGRAM_TEMPLATES:
                kind = "diagram"
            elif v.get("queries"):
                kind = "footage"
        if kind:
            v["kind"] = kind
        if kind == "diagram" and v.get("template") not in DIAGRAM_TEMPLATES and not v.get("text"):
            # Unknown template: show the beat's key words as a text card.
            v["template"], v["text"] = "key_phrase", v.get("title") or beat.get("text", "")
        elif kind == "diagram" and v.get("template") not in DIAGRAM_TEMPLATES:
            v["template"] = "key_phrase"
    return beats


def _norm_words(text: str) -> list:
    return _WORD.findall(text.lower().replace("'", "").replace("’", ""))


def _is_number(value) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def validate_beats(beats) -> list:
    """Return a list of human-readable schema problems (empty when valid)."""
    if not isinstance(beats, list) or len(beats) < 2:
        return ["beats (need a list of at least 2 beats)"]
    problems = []
    for n, beat in enumerate(beats, start=1):
        if not isinstance(beat, dict) or not _norm_words(str(beat.get("text") or "")):
            problems.append(f"beat {n}: missing narration text")
            continue
        v = get_visual(beat)
        kind = v.get("kind")
        if kind not in VISUAL_KINDS:
            problems.append(f"beat {n}: visual.kind must be one of {', '.join(VISUAL_KINDS)}")
            continue
        if not str(v.get("description") or "").strip():
            problems.append(f"beat {n}: visual.description is empty")
        if kind in ("footage", "photo"):
            queries = v.get("queries")
            if not isinstance(queries, list) or not any(str(q).strip() for q in queries):
                problems.append(f"beat {n}: {kind} needs at least one search query")
        elif kind == "diagram":
            problems.extend(f"beat {n}: {p}" for p in _diagram_problems(v))
        problems.extend(f"beat {n}: {p}" for p in _overlay_problems(v.get("overlay")))
    return problems


def _overlay_problems(overlay) -> list:
    if overlay is None:
        return []
    if not isinstance(overlay, dict) or overlay.get("type") not in OVERLAY_TYPES:
        return [f"overlay.type must be one of {', '.join(OVERLAY_TYPES)}"]
    if overlay["type"] == "stat" and not str(overlay.get("value") or "").strip():
        return ["stat overlay needs value"]
    if overlay["type"] == "label" and not str(overlay.get("text") or "").strip():
        return ["label overlay needs text"]
    return []


def _diagram_problems(v: dict) -> list:
    template = v.get("template")
    if template not in DIAGRAM_TEMPLATES:
        return [f"diagram template must be one of {', '.join(DIAGRAM_TEMPLATES)}"]
    if template == "key_phrase" and not str(v.get("text") or "").strip():
        return ["key_phrase needs text"]
    if template == "stat" and not str(v.get("value") or "").strip():
        return ["stat needs value"]
    if template == "process":
        steps = v.get("steps")
        if not isinstance(steps, list) or len(steps) < 2:
            return ["process needs 2+ steps"]
    if template == "timeline":
        events = v.get("events")
        if (not isinstance(events, list) or len(events) < 2
                or not all(isinstance(e, dict) and e.get("year") and e.get("label") for e in events)):
            return ["timeline needs 2+ events with year and label"]
    if template == "comparison":
        items = v.get("items")
        if (not isinstance(items, list) or len(items) < 2
                or not all(isinstance(i, dict) and i.get("label") and _is_number(i.get("value"))
                           for i in items)):
            return ["comparison needs 2+ items with label and numeric value"]
    return []


def _token_times(script_tokens: list, words: list, speech_end: float) -> list:
    """Spoken start time of every script token.

    Script tokens are matched against Whisper's tokens (SequenceMatcher tolerates
    the odd mismatch such as '400' heard as 'four hundred'); unmatched tokens are
    interpolated between their nearest matched neighbours.
    """
    w_tokens, w_times = [], []
    for w in words:
        for tok in _norm_words(str(w.get("text") or "")):
            w_tokens.append(tok)
            w_times.append(float(w.get("start") or 0.0))

    times = [None] * len(script_tokens)
    sm = SequenceMatcher(None, script_tokens, w_tokens, autojunk=False)
    for a, b, size in sm.get_matching_blocks():
        for k in range(size):
            times[a + k] = w_times[b + k]

    anchors = [(-1, 0.0)] + [(i, t) for i, t in enumerate(times) if t is not None]         + [(len(script_tokens), speech_end)]
    for (i0, t0), (i1, t1) in zip(anchors, anchors[1:]):
        for i in range(i0 + 1, i1):
            times[i] = t0 + (t1 - t0) * (i - i0) / (i1 - i0)
    return times


def _speech_end(words: list, total_duration: float) -> float:
    end = float(words[-1].get("end") or total_duration) if words else total_duration
    return min(end, total_duration)


def align_beats(beats: list, words: list, total_duration: float) -> list:
    """Give each beat a frame-accurate [start, end) slot covering 0..total_duration.

    A beat starts when its first word is spoken (a hair early, so the cut lands
    on the word). Returns [{"start", "end", "frames"}] — frames sum to
    round(total * FPS).
    """
    script_tokens, beat_first = [], []
    for beat in beats:
        beat_first.append(len(script_tokens))
        script_tokens.extend(_norm_words(str(beat.get("text") or "")))
    times = _token_times(script_tokens, words, _speech_end(words, total_duration))
    starts = [times[f] if f < len(times) else total_duration for f in beat_first]

    n = len(starts)
    starts = [0.0] + [max(0.0, s - LEAD_SECONDS) for s in starts[1:]]
    for i in range(1, n):
        starts[i] = max(starts[i], starts[i - 1] + MIN_BEAT_SECONDS)
    # Keep room for every remaining beat before the end.
    for i in range(n - 1, 0, -1):
        starts[i] = min(starts[i], total_duration - MIN_BEAT_SECONDS * (n - i))
        if i + 1 < n:
            starts[i] = min(starts[i], starts[i + 1] - MIN_BEAT_SECONDS)
    starts[0] = 0.0

    total_frames = max(n, round(total_duration * FPS))
    frame_starts = [round(s * FPS) for s in starts] + [total_frames]
    for i in range(1, n):  # strictly increasing after rounding
        frame_starts[i] = max(frame_starts[i], frame_starts[i - 1] + 1)
    slots = []
    for i in range(n):
        f0, f1 = frame_starts[i], max(frame_starts[i + 1], frame_starts[i] + 1)
        slots.append({"start": f0 / FPS, "end": f1 / FPS, "frames": f1 - f0})
    return slots


def script_word_timings(beats: list, words: list, total_duration: float) -> list:
    """The SCRIPT's words (exact spelling) with Whisper's timings, for subtitles.

    Whisper can mishear names and numbers; the script can't. Returns
    [{"text", "start", "end"}] in the format words_to_srt expects.
    """
    script_words, script_tokens, first_tok = [], [], []
    for beat in beats:
        for word in str(beat.get("text") or "").split():
            toks = _norm_words(word)
            if not toks:
                continue  # dashes, lone punctuation
            script_words.append(word)
            first_tok.append(len(script_tokens))
            script_tokens.extend(toks)
    speech_end = _speech_end(words, total_duration)
    times = _token_times(script_tokens, words, speech_end)
    out = []
    for i, word in enumerate(script_words):
        start = times[first_tok[i]]
        end = times[first_tok[i + 1]] if i + 1 < len(script_words) else max(speech_end, start + 0.3)
        out.append({"text": word, "start": start, "end": max(end, start + 0.05)})
    return out


def split_frames(frames: int, max_seconds: float = MAX_SHOT_SECONDS) -> list:
    """Split a beat's frame count into near-equal shots no longer than max_seconds."""
    return even_split(frames, math.ceil(frames / (max_seconds * FPS)))


def even_split(frames: int, parts: int) -> list:
    """Split frames into `parts` near-equal integer chunks that sum to frames."""
    parts = max(1, min(parts, frames))
    base, extra = divmod(frames, parts)
    return [base + (1 if i < extra else 0) for i in range(parts)]
