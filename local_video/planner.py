"""Script-to-shot planning and backend-aware prompt construction."""

from __future__ import annotations

import hashlib
import math
import random
import re
from typing import Any

from .models import Shot


QUALITY_BAN = (
    "Pure cinematic imagery only. The frame contains no captions, subtitles, title cards, "
    "typography, signs, logos, watermarks, user interfaces, or graphic overlays."
)
# Camera language, not "cinematic": plain photographic wording keeps the models out of the dreamy, painterly look.
PHOTO_LOOK = (
    "real documentary footage shot on a full-frame camera, 35mm lens, natural light, true-to-life "
    "textures and colours, sharp focus, physically plausible motion"
)
MINIMAX_SUFFIX = PHOTO_LOOK + ", coherent anatomy, stable object identity"
WAN_SUFFIX = PHOTO_LOOK + ", stable motion, coherent subject"
REALISM_BAN = (
    "painting, illustration, concept art, CGI, 3D render, cartoon, anime, dreamy haze, glow, bloom, "
    "soft focus, blurry, oversaturated colours, fantasy lighting, morphing, melting shapes"
)
CAMERA_MOVES = (
    "slow push-in", "gentle tracking shot", "controlled handheld follow", "smooth orbit",
    "low-angle dolly", "overhead drift", "slow pull-back", "lateral parallax move",
)


# The writer's own `camera` choice, as a phrase the generator understands. The screenplay schema
# requires one of these per beat and the script evaluator checks it against `continuity_out`, so
# substituting a different move leaves every inherited start state describing a move that was never
# rendered. Before this, 7 of 8 shots in a run were rendered with a move the writer did not choose.
_MOVE_PHRASE = {
    "push_in": "slow push-in",
    "pull_out": "slow pull-back",
    "pan_left": "steady pan left",
    "pan_right": "steady pan right",
    "rise": "slow rising crane move",
    "orbit": "slow orbit around the subject",
    "locked_off": "locked-off static camera",
}


# Where the camera stands when the description does not say. Without it the generator picks its own
# default for a landscape, a drone view: on the 2026-10-27 volcano run 16 reviews said "high aerial,
# not the sea-level view the beat describes", in shots that never asked to leave the water.
EYE_LEVEL = "camera at eye level about two metres above the ground or water, horizon level"
_CLOSE_CUES = ("extreme close-up", "macro", "close-up", "close shot", "close on ", "close view", "close, low",
               "close and low", "close low")
# A description that places the camera itself keeps that place; the eye-level default contradicted
# "close, low view along the boardwalk" and "the camera rises", and both were rejected as "higher and
# wider than requested" and "never reaches the homes".
_HEIGHT_CUES = ("low view", "low angle", "ground level", "floor level", "shore-level", "shore level",
                "water level", "waterline view", "knee height", "camera rises", "rises from", "crane",
                "from above", "high view", "eye level", "eye-level")


def _states_height(action: str, move: str = "") -> bool:
    return any(cue in action for cue in _HEIGHT_CUES) or "rising" in move or "crane" in move
# Camera positions only: a bare "overhead" also means "gulls cross overhead", which turned an eye-level
# quay shot into a high aerial view.
_OVERHEAD_CUES = ("top-down", "overhead shot", "overhead view", "from overhead", "looking straight down",
                  "looking down", "from far above", "aerial")


def _overhead(action: str) -> bool:
    return "eye level" not in action and any(cue in action for cue in _OVERHEAD_CUES)


def framing_scale(subject: str) -> str | None:
    """"close", "wide" or None (medium or unstated), from the shot's own description."""
    action = subject.lower()
    if any(cue in action for cue in _CLOSE_CUES):
        return "close"
    if "wide" in action or _overhead(action):
        return "wide"
    return None


_TRAVEL = (r"(?:steam|sail|walk|driv|ride|rid|fly|flies|flew|run|ran|sprint|dash|bolt|gallop|bound|trot|race|chas|"
           r"charg|march|roll|drift|cross|head|mov|swim|paddl|row|continu)\w*")


def _heading(action: str) -> str:
    """'left'/'right' when the subject travels across the frame ("steaming toward frame right")."""
    # "its wake trailing behind it toward frame left": the wake points back, the ship travels right. Read
    # first, or "steaming on, its wake trailing toward frame left" would read as travelling left.
    behind = re.search(r"\b(?:wake|trail|exhaust|dust)\w*\b[^.;]{0,40}?\b(?:toward|towards|to)\s+"
                       r"(?:the\s+)?frame\s+(left|right)\b", action)
    if behind:
        return "right" if behind.group(1) == "left" else "left"
    # "sprints at full speed from frame left to frame right": the stray-dog hook came back running at the
    # camera on both keyframe takes without a side-on line.
    span = re.search(r"\bfrom\s+(?:the\s+)?frame\s+(left|right)\b[^.;]{0,40}?\b(?:to|toward|towards|into)\s+"
                     r"(?:the\s+)?frame\s+(left|right)\b", action)
    if span and span.group(1) != span.group(2):
        return span.group(2)
    found = re.search(rf"\b{_TRAVEL}\b[^.;]{{0,60}}?\b(?:toward|towards|to|into)\s+(?:the\s+)?frame\s+(left|right)\b",
                      action)
    if found:
        return found.group(1)
    found = re.search(r"\b(?:from\s+)?(left|right)[-\s]+to[-\s]+(?:the\s+)?(left|right)\b", action)
    if found and found.group(1) != found.group(2):
        return found.group(2)
    # "the Greek column ... marches right in a side-on file": the stray-dog march, with no "frame" in it
    found = re.search(rf"\b{_TRAVEL}\b\s+(?:\w+\s+)?(?:to(?:ward)?s?\s+the\s+)?(left|right)\b(?!\s+(?:hand|side|half))",
                      action)
    return found.group(1) if found else ""


def _camera_plan(subject: str, index: int, chosen: str | None = None, handoff: str = "") -> tuple[str, str]:
    """Honor explicit screenplay composition instead of adding a conflicting camera preset.

    A composition cue in the description (macro, close-up, low angle, overhead) still sets both the
    framing and the move, because the cue describes where the camera is. Otherwise the writer's
    `camera` choice wins, and only a beat that supplied none falls back to the index rotation.
    The framing never comes from a rotation: that told a wide shot of an ash column it was a
    "macro detail shot" and a pan across the sea an "85mm intimate close-up", and the generator
    resolved each contradiction with a generic drone view.
    """
    action = subject.lower()
    def placed(lens: str, move: str = "") -> str:
        return lens if _states_height(action, move) else f"{lens}, {EYE_LEVEL}"

    if "extreme close-up" in action or "macro" in action:
        return "controlled macro push-in", "macro detail shot"
    if any(cue in action for cue in _CLOSE_CUES):
        return "slow intimate push-in", placed("85mm close-up")
    if "low angle" in action or "looking up" in action or "floor level" in action:
        return "slow low-angle drift", "24mm low-angle wide frame"
    if _overhead(action):
        return "slow overhead drift", "24mm high aerial wide frame looking down"
    if "side angle" in action or "side shot" in action or "from the side" in action:
        return "gentle lateral tracking shot", placed("35mm side-angle medium-wide frame")
    chosen = str(chosen or "").strip().lower()
    # A move the writer chose but this table does not know holds the camera still: the rotation once gave
    # Hegdahl's seated briefing (written "locked_off") a smooth orbit that slid the officials out of frame.
    move = (_MOVE_PHRASE.get(chosen) or ("locked-off static camera" if chosen else "")
            or CAMERA_MOVES[index % len(CAMERA_MOVES)])
    heading = _heading(action) or _heading(handoff.lower())      # "continues on course toward frame right"
    if heading and "pan" not in move and "track" not in move:
        # A subject travelling across frame leaves it in three seconds unless the camera follows: the
        # Hegdahl ship "filling the right half, steaming toward frame right" under a pull-back sailed out
        # of frame on every take.
        move = f"steady pan {heading}"
    if "wide" in action:
        return move, placed("24mm wide frame", move)
    if "medium" in action or "closer" in action:
        return move, placed("50mm medium frame", move)
    return move, placed("35mm frame", move)


def framing_for(subject: str, camera: str = "") -> str:
    """The lens and camera position a shot is rendered with; its keyframe must be shot the same way."""
    framing = _camera_plan(subject, 0)[1]
    if _states_height(subject.lower(), camera.lower()):
        framing = framing.replace(f", {EYE_LEVEL}", "")
    return framing


MIN_DURATION, MAX_DURATION = 30, 90


def validate_duration(seconds: int) -> int:
    if not MIN_DURATION <= int(seconds) <= MAX_DURATION:
        raise ValueError(f"Short-form project duration must be between {MIN_DURATION} and {MAX_DURATION} seconds")
    return int(seconds)


def shot_count_for_duration(seconds: int) -> int:
    return max(10, min(30, round(validate_duration(seconds) / 3.0)))


def allocate_frames(total_seconds: int, shot_count: int, fps: int = 30) -> list[int]:
    if shot_count < 1:
        raise ValueError("shot_count must be positive")
    total = validate_duration(total_seconds) * fps
    base, remainder = divmod(total, shot_count)
    frames = [base + (1 if i < remainder else 0) for i in range(shot_count)]
    if any(not 75 <= value <= 120 for value in frames):
        raise ValueError("Shot plan must average 2.5 to 4 seconds per shot")
    return frames


STORY_SHOT_MAX_FRAMES = 105     # 3.5 s at 30 fps


def allocate_story_frames(total_seconds: int, beat_texts: list[str], fps: int = 30) -> list[int]:
    """Allocate 2.5-3.5 second shots by narration density and story position.

    Capped at 3.5 s: MiniMax's render time grows much faster than clip length (stray-dog run: 3.0 s
    took 215 s, 3.9 s took 525 s), and assembly stretches a clip up to MAX_CLIP_STRETCH anyway.
    """
    if not beat_texts:
        return allocate_frames(total_seconds, shot_count_for_duration(total_seconds), fps)
    total = validate_duration(total_seconds) * fps
    count = len(beat_texts)
    if not count * 75 <= total <= count * STORY_SHOT_MAX_FRAMES:
        return allocate_frames(total_seconds, count, fps)
    weights: list[float] = []
    for index, text in enumerate(beat_texts):
        words = max(1, len(str(text).split()))
        position = index / max(1, count - 1)
        story_emphasis = 0.9 if index == 0 else 1.12 if position >= 0.8 else 1.0
        weights.append(max(0.75, min(1.35, words / 7.0)) * story_emphasis)
    raw = [total * weight / sum(weights) for weight in weights]
    frames = [max(75, min(STORY_SHOT_MAX_FRAMES, round(value))) for value in raw]
    delta = total - sum(frames)
    while delta:
        direction = 1 if delta > 0 else -1
        candidates = [
            index for index, value in enumerate(frames)
            if (direction > 0 and value < STORY_SHOT_MAX_FRAMES) or (direction < 0 and value > 75)
        ]
        if not candidates:
            raise ValueError("Could not allocate exact dynamic shot durations")
        candidates.sort(key=lambda index: raw[index] - frames[index], reverse=direction > 0)
        for index in candidates:
            if not delta:
                break
            frames[index] += direction
            delta -= direction
    return frames


def _split_text(text: str, count: int) -> list[str]:
    clauses = [value.strip() for value in re.split(r"(?<=[.!?;:])\s+|\n+", text) if value.strip()]
    if not clauses:
        clauses = [text.strip() or "The story develops visually."]
    if len(clauses) >= count:
        groups: list[str] = []
        for i in range(count):
            start = round(i * len(clauses) / count)
            end = round((i + 1) * len(clauses) / count)
            groups.append(" ".join(clauses[start:max(start + 1, end)]))
        return groups
    return [clauses[i % len(clauses)] for i in range(count)]


def _seed(project_key: str, index: int) -> int:
    digest = hashlib.sha256(f"{project_key}:{index}".encode()).digest()
    return int.from_bytes(digest[:8], "big") & 0x7FFFFFFF


def character_look(character: dict[str, Any], beat_index: int | None) -> str:
    """The one appearance a character has at a beat (0-based); later `look_changes` win."""
    look = str(character.get("look") or "")
    if beat_index is None:
        return look
    changes = [c for c in character.get("look_changes") or [] if isinstance(c, dict) and c.get("look")]
    for change in sorted(changes, key=lambda c: int(c.get("from_beat") or 0)):
        if int(change.get("from_beat") or 0) - 1 <= beat_index:
            look = str(change["look"])
    return look


def _beat_visual(script: dict[str, Any], beat_index: int) -> dict[str, Any]:
    beats = script.get("beats") if isinstance(script.get("beats"), list) else []
    beat = beats[beat_index] if 0 <= beat_index < len(beats) and isinstance(beats[beat_index], dict) else {}
    return beat.get("visual") if isinstance(beat.get("visual"), dict) else {}


_NAME_TITLES = {"the", "of", "and", "mr", "mrs", "ms", "dr", "sir", "lady", "lord", "king", "queen", "saint",
                "st", "captain", "major", "general", "colonel", "private", "sergeant", "lieutenant", "admiral"}


def _name_tokens(name: str, others: list[str]) -> list[str]:
    """Words that alone identify a character: a surname or first name no other character shares."""
    shared = {word.lower() for other in others for word in re.findall(r"[\w'-]+", other)}
    return [word for word in re.findall(r"[\w'-]+", name)
            if len(word) >= 3 and word[0].isupper() and word.lower() not in _NAME_TITLES
            and word.lower() not in shared]


def beat_cast(script: dict[str, Any], beat_index: int) -> list[dict[str, Any]]:
    """The script characters a beat names in its visual description or continuity notes.

    A character counts when the full name appears, or a surname/first name only they carry: the
    2026-10-29 script named "Doug Hegdahl" once and "Hegdahl" in 15 more beats, and those all
    planned as "none of the story's named characters", so every shot drew a different man.
    """
    characters = [c for c in script.get("characters") or [] if isinstance(c, dict)
                  and str(c.get("name") or "").strip()]
    visual = _beat_visual(script, beat_index)
    text = " ".join(str(visual.get(key) or "") for key in ("description", "continuity_in", "continuity_out"))
    # "toward Hegdahl's off-frame position" names him without showing him: cast, he was drawn walking in.
    text = re.sub(r"\b[\w'’-]+(?:'s|’s)?\s+(?:off-?(?:frame|screen)|out[- ]of[- ](?:frame|shot|view)|unseen)\b"
                  r"|\b(?:off-?(?:frame|screen)|unseen)\s+[\w'’-]+", " ", text, flags=re.I)
    names = [str(c["name"]).strip() for c in characters]
    cast = []
    for character, name in zip(characters, names):
        tokens = _name_tokens(name, [other for other in names if other != name])
        if (re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE)
                or any(re.search(rf"\b{re.escape(token)}\b", text) for token in tokens)):
            cast.append(character)
    return cast


def _names_cast(script: dict[str, Any]) -> bool:
    """True when the beats name their characters, so a beat naming nobody really shows nobody."""
    beats = script.get("beats") if isinstance(script.get("beats"), list) else []
    return any(beat_cast(script, index) for index in range(len(beats)))


def beat_labels(script: dict[str, Any], beat_index: int) -> tuple[str, str]:
    """The beat's place and light labels, lower-cased; empty for scripts written without them."""
    visual = _beat_visual(script, beat_index)
    return (str(visual.get("scene") or "").strip().lower(), str(visual.get("light") or "").strip().lower())


def continuation_source(
    labels: list[tuple[str, str]], index: int, casts: list[list[str]] | None = None,
    scales: list[str | None] | None = None, objects: list[frozenset[str]] | None = None,
) -> int | None:
    """The earlier shot whose last frame this shot opens on, or None for a fresh opening.

    A labelled shot continues the latest earlier shot in the same place and light, so a cut
    back to a place keeps its look and a cut elsewhere never morphs out of an unrelated frame.
    A return to an earlier shot also needs the same cast: opening a two-army shot on a frame of
    one hero charging the camera makes the model add the enemy beside him.
    A close shot opens only on a close frame, and a wide one never on a close frame (`scales`, from
    framing_scale): three seconds cannot travel that far, so "close on a wave over the rock" opened
    on a wide aerial stayed a wide aerial on every take. Such a shot gets its own keyframe.
    Recurring objects (`objects`, from shot_objects) follow the same idea: a shot never opens on
    a frame of entirely different objects, and a return needs a frame already showing all of
    its own. On the 1784 Scheldt run the lone Dutch warship opened on the Austrian convoy's last
    frame, so all three ships stayed and their eagle banners turned into Dutch flags mid-clip.
    Unlabelled scripts keep the old rule: every shot continues the previous one.
    """
    if index <= 0 or index >= len(labels):
        return None
    if not labels[index][0]:
        return index - 1
    same_cast = (lambda prior: True) if casts is None else (
        lambda prior: prior == index - 1 or sorted(casts[prior]) == sorted(casts[index]))
    # A close shot opens only on a close frame: from a medium one the model "zooms" by redrawing the face,
    # and Hegdahl shot-021 came out bald and still medium on two takes from shot-020's medium frame.
    same_scale = (lambda prior: True) if scales is None else (
        lambda prior: {scales[prior], scales[index]} != {"close", "wide"}
        and (scales[index] != "close" or scales[prior] == "close"))

    def same_objects(prior: int) -> bool:
        if objects is None or not objects[index]:
            return True
        if prior == index - 1:
            return not objects[prior] or bool(objects[prior] & objects[index])
        return objects[index] <= objects[prior]

    prior = next((prior for prior in range(index - 1, -1, -1)
                  if labels[prior] == labels[index] and same_cast(prior) and same_scale(prior)
                  and same_objects(prior)), None)
    if prior is None or _take_length(labels, prior, casts, scales, objects) >= MAX_TAKE:
        return None
    # A frame seeds ONE later shot: on the El Nino run shot 1's last frame opened shots 2, 3 and 7, so
    # three shots began on the same picture. Any other shot of that place gets its own keyframe.
    if any(continuation_source(labels, later, casts, scales, objects) == prior for later in range(prior + 1, index)):
        return None
    return prior


# A continuous take (shots chained frame to frame) is at most this many shots. The 2026-10-27 El Nino
# video chained 14 shore shots off each other's last frames: one composition for ~40 s while the
# narration moved on to hurricanes, forecasters and a Kelvin wave. The next shot opens on a fresh keyframe.
MAX_TAKE = 3


def _take_length(labels, index, casts=None, scales=None, objects=None) -> int:
    """How many shots the take ending at `index` already holds (1 = it opened fresh)."""
    length = 1
    while True:
        source = continuation_source(labels, index, casts, scales, objects)
        if source is None:
            return length
        length += 1
        index = source


def _words(text: str, size: int = 5) -> set[str]:
    return set(re.findall(rf"[a-z]{{{size},}}", text.lower().replace("'s", "")))


# Words a light label shares with ordinary style text without naming a kind of light.
_GENERIC_LIGHT_WORDS = {"light", "lighting", "with", "from", "over", "under", "into"}


def _light_words(text: str) -> set[str]:
    return _words(text, 4) - _GENERIC_LIGHT_WORDS


def _for_light(text: str, script: dict[str, Any], beat_index: int) -> str:
    """Drop clauses about another beat's light, so a style line about the eclipse stays out of dawn.

    Light words are matched from four letters: at five, "pale hazy sky" in the palette matched
    nothing in "hazy midday sun" and rode into every ash-darkened shot, which then came back pale.
    """
    beats = script.get("beats") if isinstance(script.get("beats"), list) else []
    light = beat_labels(script, beat_index)[1]
    if not light or not text:
        return text
    others = set().union(*(_light_words(beat_labels(script, i)[1]) for i in range(len(beats)))) - _light_words(light)
    clauses = [part for part in re.split(r"\s*[;,]\s*", text) if part and not _light_words(part) & others]
    return ", ".join(clauses)


_MARKING = re.compile(r"\b(?:flags?|banners?|ensigns?|tricolou?rs?|standards?|insignia|emblems?|markings?|"
                      r"pennants?|colours of)\b", re.I)


def colours_only(palette: str) -> str:
    """A palette without the objects it names: the generator draws every noun it reads.

    "Small accents from the Greek blue-and-white flag and the Bulgarian white-green-red flag" sat in
    every shot's palette, and a Bulgarian flag rose over the Greek camp in all three takes of the
    stray-dog shot-005. Each side's marking reaches only the shots whose description shows it.
    """
    clauses = [part for part in re.split(r"\s*[;,]\s*|\s+(?=with\b)", palette or "") if part.strip()]
    kept = [part for part in clauses if not _MARKING.search(part)]
    return ", ".join(kept).strip(" ,.")


def _palette_for_scene(palette: str, script: dict[str, Any], beat_index: int) -> str:
    """This scene's colours from a palette written per scene ("blue-gray for ship deck, sea surface, and
    open sea; dusty beige for holding room, prison yard, and cell wall").

    Splitting that on commas made "and open sea, dusty beige, faded gray, and cell wall" the open-sea
    palette (Hegdahl run): scene names read as colours, and a prison wall reached the sea.
    """
    scene = beat_labels(script, beat_index)[0]
    clauses = [part.strip() for part in re.split(r"\s*;\s*", palette or "") if part.strip()]
    owned = [re.match(r"(.+?)\s+for\s+(.+)$", part.rstrip("."), re.I) for part in clauses]
    if scene and owned and all(owned):
        for match in owned:
            labels = {label.strip().lower() for label in re.split(r",\s*(?:and\s+)?|\s+and\s+", match.group(2))}
            if scene in labels:
                return match.group(1).strip()
    return _for_scene(_for_light(palette, script, beat_index), script, beat_index)


def _for_scene(text: str, script: dict[str, Any], beat_index: int, split: str = r"\s*[;,]\s*") -> str:
    """Drop clauses that belong only to another scene, so the fire never sees the modern trench.

    A clause headed by a scene label ("Above the island: ...") belongs to that scene alone. Any
    other clause naming another scene's label words is dropped unless it also names a word only
    this beat's label has: a word every label shares proves nothing. Both "open sea off the island"
    and "above the island" contain "island", so the open-sea shots used to be handed "Above the
    island: a high vantage looking down" and rendered as drone shots.
    """
    beats = script.get("beats") if isinstance(script.get("beats"), list) else []
    scene = beat_labels(script, beat_index)[0]
    if not scene or not text:
        return text
    other_labels = {beat_labels(script, i)[0] for i in range(len(beats))} - {scene, ""}
    place = _place_vocab(script)
    own_place = place.get(scene, set())
    other_place = set().union(*(v for k, v in place.items() if k != scene)) - own_place if place else set()
    own = _words(scene)
    shared = set().union(*(_words(label) for label in other_labels)) if other_labels else set()
    others = shared - own
    distinct = own - shared

    def keep(part: str) -> bool:
        head = re.match(r"\s*([^:.;]{2,60}):", part)
        if head:
            label = head.group(1).strip().lower()
            if label == scene:
                return True
            if label in other_labels:
                return False
        words = _words(part)
        if words & other_place and not words & (own_place | own):
            return False        # "pale timber homes" describes the shore: it must not reach the desert city
        return not words & others or bool(words & distinct)

    clauses = [part for part in re.split(split, text) if part.strip() and keep(part)]
    return (" " if split == _SENTENCES else ", ").join(part.strip() for part in clauses)


def _place_vocab(script: dict[str, Any]) -> dict[str, set[str]]:
    """Scene label -> the content words of its own location sentence ("Desert city boulevard: a wide street...")."""
    beats = script.get("beats") if isinstance(script.get("beats"), list) else []
    labels = {beat_labels(script, i)[0] for i in range(len(beats))} - {""}
    vocab: dict[str, set[str]] = {}
    for sentence in re.split(_SENTENCES, str(script.get("location") or "")):
        head = re.match(r"\s*([^:.;]{2,60}):", sentence)
        if head and head.group(1).strip().lower() in labels:
            vocab.setdefault(head.group(1).strip().lower(), set()).update(_words(sentence))
    return vocab


# Whole sentences: a world description's commas belong to one place and must stay together.
# Titles are not sentence ends ("Dr. Cara").
_SENTENCES = r"(?<=[.;])(?<!\bDr\.)(?<!\bMr\.)(?<!\bMs\.)(?<!\bSt\.)(?<!\bMrs\.)\s+"


def _object_name(item: Any) -> str:
    """A recurring object's name: "Dutch warship: a dark hull..." -> "dutch warship"."""
    return re.split(r"\s+[—–-]\s+|[:;(]", str(item))[0].strip().lower()


def _singular(word: str) -> str:
    return word[:-1] if len(word) > 4 and word.endswith("s") and not word.endswith("ss") else word


def beat_objects(script: dict[str, Any], beat_index: int) -> list[str]:
    """The recurring objects a beat's visual mentions; the rest are not in this shot.

    An object matches by its head noun ("The orange ash layer" -> "layer"): matching any word
    put the buried ash layer into every fire shot that mentions orange flames. Plurals match
    too: "three sailing ships" left the Austrian ships, and their eagle banner, out of the lock.
    Objects sharing a head noun ("Dutch warship", "Austrian warships") are told apart by the
    words only their own entry uses ("striped flag" against "eagle banner"); otherwise every
    warship shot locked both fleets' flags, and the lone Dutch ship opened on the convoy.
    """
    visual = _beat_visual(script, beat_index)
    raw = " ".join(str(visual.get(key) or "") for key in ("description", "continuity_out")).lower()
    text = {_singular(word) for word in _words(raw, 4)}
    names = {str(item): re.sub(r"^(?:the|a|an)\s+", "", _object_name(item)) for item in script.get("recurring_objects") or []}
    by_head: dict[str, list[str]] = {}
    for item in script.get("recurring_objects") or []:
        head = re.findall(r"[a-z]{4,}", _object_name(item).replace("'s", ""))
        # A name inside another object's name is that object, not this one: "the molasses tank" put
        # "The molasses ... moving as a heavy rolling mass" into a calm tank shot, and MiniMax erupted it.
        own_text = raw
        for other, name in names.items():
            if other != str(item) and head and len(name.split()) > 1 and head[-1] in name.split():
                own_text = re.sub(rf"\b{re.escape(name)}\b", " ", own_text)
        if head and _singular(head[-1]) in {_singular(word) for word in _words(own_text, 4)}:
            by_head.setdefault(_singular(head[-1]), []).append(str(item))
    present = set()
    for items in by_head.values():
        words = [{_singular(word) for word in _words(item, 4)} for item in items]
        own = [mine - set().union(*(theirs for theirs in words if theirs is not mine)) for mine in words]
        scores = [len(distinct & text) for distinct in own]
        present.update(item for item, score in zip(items, scores) if score == max(scores))
    return [str(item) for item in script.get("recurring_objects") or [] if str(item) in present]


def shot_objects(script: dict[str, Any], continuity: dict[str, Any] | None) -> frozenset[str]:
    """Names of the recurring objects a planned shot's identity lock carries."""
    locked = str((continuity or {}).get("recurring_objects") or "")
    return frozenset(_object_name(item) for item in script.get("recurring_objects") or []
                     if str(item).strip() and str(item) in locked)


def payoff_of(subject_action: str) -> str:
    """The beat's final sentence: what must be on screen when the clip ends."""
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", subject_action) if part.strip()]
    return sentences[-1] if sentences else subject_action


# The identity lock's filler when a story has no characters. The reviewer still reads it; the video
# prompt leaves it out, or a shot of a river gains "one recurring protagonist".
DEFAULT_CHARACTERS = (
    "one recurring protagonist with exactly the same face, body, clothing, equipment, "
    "and color scheme in every shot"
)
DEFAULT_LOCATION = "one continuous physical world for"
DEFAULT_PALETTE = "consistent restrained cinematic palette"


def _continuity(
    script: dict[str, Any], visual_style: str, concept: str, beat_index: int | None = None,
) -> dict[str, Any]:
    characters = [c for c in script.get("characters") or [] if isinstance(c, dict)]
    nobody = ""
    if beat_index is not None:
        # Only the characters this beat names: a listed bystander's costume (a cap, medals)
        # otherwise leaks onto whoever is on screen, and a crowd shot gains posing leads.
        named = beat_cast(script, beat_index)
        if named or not _names_cast(script):
            characters = named or characters
        else:
            characters = []
            nobody = "no named character in this shot; any people are anonymous background figures"
    cast = "; ".join(
        f"{c.get('name')}: {character_look(c, beat_index)}" for c in characters if isinstance(c, dict)
    )
    palette = script.get("color_palette") or DEFAULT_PALETTE
    time_of_day = script.get("time_of_day") or "consistent time of day unless the story explicitly advances"
    objects = script.get("recurring_objects", [])
    location = script.get("location") or (
        f"{DEFAULT_LOCATION} {concept}; preserve geography, architecture, scale, "
        "weather, and recurring props between adjacent shots"
    )
    geography = script.get("screen_geography") or ""
    if beat_index is not None:
        palette = _palette_for_scene(palette, script, beat_index)
        visual_style = _for_scene(_for_light(visual_style, script, beat_index), script, beat_index)
        location = _for_scene(location, script, beat_index, _SENTENCES)
        geography = _for_scene(geography, script, beat_index, _SENTENCES)
        scene = beat_labels(script, beat_index)[0]
        if scene and geography:
            # A character never seen in this place (Boudica at the modern dig) loses their rules here.
            beats = script.get("beats") if isinstance(script.get("beats"), list) else []
            here = {str(c.get("name")).strip() for i in range(len(beats)) if beat_labels(script, i)[0] == scene
                    for c in beat_cast(script, i)}
            names = [str(c.get("name") or "").strip() for c in script.get("characters") or []
                     if isinstance(c, dict) and str(c.get("name") or "").strip()]
            # A surname alone ("Hegdahl usually occupies frame left") names the character too.
            patterns = {name: [rf"\b{re.escape(name)}\b"] + [rf"\b{re.escape(token)}\b" for token in
                                                            _name_tokens(name, [n for n in names if n != name])]
                        for name in names}

            def mentions(part: str, name: str) -> bool:
                return any(re.search(pattern, part, re.IGNORECASE) for pattern in patterns[name])

            absent = [name for name in names if name not in here]
            parts = re.split(r"(?<=;)\s+|" + _SENTENCES, geography)
            named = [name for name in names if any(mentions(part, name) for part in parts)]
            if named and all(name in absent for name in named):
                # Every rule is about people who are not in this place ("his movement ... listeners face
                # him"): an empty open-sea shot was told to hold listeners and drew a cabin of men.
                geography = ""
            else:
                geography = " ".join(part for part in parts if not any(mentions(part, name) for name in absent))
        time_of_day = beat_labels(script, beat_index)[1] or time_of_day
        objects = beat_objects(script, beat_index)
    return {
        "characters": cast or nobody or DEFAULT_CHARACTERS,
        "wardrobe": script.get("wardrobe") or "unchanged clothing and accessories between adjacent shots",
        "vehicles": script.get("vehicles") or "identical vehicle design and markings where present",
        "location": location,
        "palette": palette,
        "screen_geography": geography,
        "time_of_day": time_of_day,
        "recurring_objects": "; ".join(str(item) for item in objects if item),
        "visual_style": visual_style,
        "period": story_period(script),
    }


def story_period(script: dict[str, Any]) -> str:
    """The year the story happens in, from the script's own words ("went overboard in 1967").

    Nothing carried the era to the generators, so the Hegdahl run's "bare, location-neutral" holding
    room came out as a clean modern hallway with a hardwood floor instead of a 1967 prison.
    """
    for key in ("description", "story_premise", "spoken_script"):
        found = re.search(r"\b(1[0-9]{3}|20[0-2][0-9])s?\b", str(script.get(key) or ""))
        if found:
            return found.group(0)
    return ""


def period_line(continuity: dict[str, Any]) -> str:
    """The era in words that add no new things: H3 draws every noun, and "every room, fitting, fabric
    ... never new or modern" put a cabin interior into an open-sea shot (Hegdahl run shot-004)."""
    period = str((continuity or {}).get("period") or "")
    return f"Period: {period}, everything in frame of that era, aged and long used" if period else ""


def continuity_text(value: dict[str, Any]) -> str:
    return "; ".join(f"{key.replace('_', ' ')}: {item}" for key, item in value.items() if item)


# MiniMax H3 is trained on one prompt layout (MiniMax's h3-prompt-writing guide, which FreeVideo's own
# prompt assistant and drama agent follow): a plain description under integrated_multimodal_description
# that opens with "[Shot 1]", the style and the framing, then the sound and the music sections. Its text
# encoder reads every word as picture content, so instructions written for a chat model ("render only
# this shot, not a montage", "no flashback", "PREVIOUS SHOT: ...", "one recurring protagonist") were
# drawn instead of obeyed: across ten projects 72% of first takes were rejected and 70% of GPU time
# went to rejected takes, with prompts of 450-700 words around a 60-word beat.
H3_NO_TEXT = "No subtitles, no on-screen text."
# FreeVideo's wording for a clip whose first frame is supplied (agent/drama.py).
FIRST_FRAME_LINE = "Continuing from the opening frame, the scene keeps its exact layout, lighting and characters."
_H3_HEAD = "integrated_multimodal_description: [Shot 1] "

# H3 camera language: move type, amplitude and speed, as prose.
_CAMERA_PROSE = {
    "slow push-in": "The camera pushes in slowly with small amplitude.",
    "slow intimate push-in": "The camera pushes in slowly with small amplitude.",
    "controlled macro push-in": "The camera pushes in very slowly with small amplitude.",
    "slow pull-back": "The camera pulls out slowly with small amplitude.",
    "steady pan left": "The camera pans left at slow speed, following the motion.",
    "steady pan right": "The camera pans right at slow speed, following the motion.",
    "slow rising crane move": "The camera pedestals up at slow speed.",
    "slow orbit around the subject": "The camera arcs slowly around the subject with small amplitude.",
    "smooth orbit": "The camera arcs slowly around the subject with small amplitude.",
    "slow low-angle drift": "The camera trucks slowly with small amplitude from the low angle.",
    "slow overhead drift": "The camera trucks slowly with small amplitude, looking down from above.",
    "overhead drift": "The camera trucks slowly with small amplitude, looking down from above.",
    "gentle lateral tracking shot": "The camera trucks sideways at slow speed.",
    "lateral parallax move": "The camera trucks sideways at slow speed, with parallax.",
    "gentle tracking shot": "The camera tracks alongside the subject at slow speed.",
    "controlled handheld follow": "A handheld camera follows the subject at slow speed.",
    "low-angle dolly": "The camera dollies in slowly from a low angle.",
    "locked-off static camera": "Static shot: the camera stays locked off on a tripod.",
}

# The script marks stand-ins "illustrative" for honesty; to the generator the word asks for an
# illustration, the painterly look the reviewer rejects. The screenplay keeps it.
_ILLUSTRATIVE_LABEL = r"illustrative(?:,?\s+[\w-]+){0,2}?\s+(?:physical\s+)?(?:reconstruction|stand-in)"
# "...reconstruction of captivity beginning: a door swings shut" -- "of X:" is a title, dropped whole.
_ILLUSTRATIVE_TITLE = re.compile(rf"(^|:\s+){_ILLUSTRATIVE_LABEL}(?:\s+(?:of|for)\s+[^,.:;]+)?\s*:\s*", re.I)
_ILLUSTRATIVE_LEAD = re.compile(rf"(^|:\s+){_ILLUSTRATIVE_LABEL}\s*[,;]\s*", re.I)
# "...reconstruction of Hegdahl seated frame left, facing..." -- here X IS the shot: only the label
# goes. Dropping "of X," with it cut the subject out of 11 of 22 prompts on the 2026-10-29 Hegdahl
# run (MiniMax was never told he sat at frame left, and the first take had him walk off).
_ILLUSTRATIVE_OF = re.compile(rf"\b{_ILLUSTRATIVE_LABEL}\s+(?:of|for)\s+", re.I)


def generator_text(text: str) -> str:
    """Screenplay wording as the video model should read it."""
    value = _ILLUSTRATIVE_TITLE.sub(r"\1", str(text or ""))
    value = _ILLUSTRATIVE_LEAD.sub(r"\1", value)
    value = _ILLUSTRATIVE_OF.sub("", value)
    # "illustrative reconstruction pulls back from his face": the label was standing in for the camera
    value = re.sub(rf"\b{_ILLUSTRATIVE_LABEL}\s+(?=(?:pulls|pushes|moves|tracks|drifts|follows|holds)\b)",
                   "the camera ", value, flags=re.I)
    value = re.sub(r"\ban illustrative\s+(?=[^aeiouAEIOU\W])", "a ", value)
    value = re.sub(r"\s*\(illustrative\)|\billustrative,?\s+", "", value, flags=re.I)
    # "location-neutral" tells the writer not to claim a real place; to a generator it means generic/modern
    value = re.sub(r",?\s*\blocation-neutral\b,?", "", value, flags=re.I)
    value = re.sub(r"\s+([,.;:])", r"\1", value)
    return re.sub(r"\s{2,}", " ", value).strip()


def _sentence(text: str) -> str:
    value = str(text or "").strip().rstrip(";,")
    return value if not value or value[-1] in ".!?" else value + "."


def camera_prose(move: str) -> str:
    move = str(move or "").strip()
    return _CAMERA_PROSE.get(move.lower()) or (_sentence(f"Camera: {move}") if move else "")


def h3_prompt(description: str, sound: str) -> str:
    return (f"{_H3_HEAD}{description.strip()}\n\n"
            f"overall_soundscape: {_sentence(sound) or 'Natural ambience of the scene.'}\n\n"
            "non_diegetic_music: N/A")


def is_h3(prompt: str) -> bool:
    return prompt.startswith(_H3_HEAD)


def with_first_frame(prompt: str) -> str:
    """Tell H3 the supplied image is frame 0, right after the opening style-and-framing sentence."""
    if not prompt.startswith(_H3_HEAD) or FIRST_FRAME_LINE in prompt:
        return prompt
    lead_end = prompt.find(". ", len(_H3_HEAD))
    if lead_end < 0:
        return prompt
    return prompt[:lead_end + 2] + FIRST_FRAME_LINE + " " + prompt[lead_end + 2:]


def plain_description(prompt: str) -> str:
    """The description alone, for a generator that does not know H3's sections (Wan)."""
    if not prompt.startswith(_H3_HEAD):
        return prompt
    return prompt[len(_H3_HEAD):].split("\n\noverall_soundscape:", 1)[0].strip()


def _named_here(objects: str, action: str) -> list[str]:
    """The recurring objects this shot's own text names, for the video prompt.

    The identity lock matches objects by head noun, which is right for the reviewer but too loose
    for the generator, which draws whatever it is given: "wooden merchant sailing ships" on a quay
    pulled in "Austrian merchant ship ... flying a yellow banner with a black double-headed eagle",
    and a lone red banner brought the rival city's white banners with it. An object whose name has
    a proper noun ("Austrian", "Bologna", "Dutch") goes in only when the shot says that name.
    """
    words = {_singular(word) for word in re.findall(r"[a-z]+", action.lower())}
    kept = []
    for item in (part.strip() for part in re.split(r";\s+(?=[^;:]{1,80}:)", objects) if part.strip()):
        name = re.sub(r"\(.*?\)", "", item.split(":", 1)[0]).strip()
        proper = [w for w in re.findall(r"[A-Za-z]+", name) if w[:1].isupper() and w.lower() not in _COMMON_CAPITALS]
        if not proper or any(_singular(w.lower()) in words for w in proper):
            kept.append(_without_story_states(item))
    return kept


def _without_story_states(item: str) -> str:
    """An object's look without its states at other points of the story.

    "intact through beat 12, split open from beat 13, torn and collapsed plates after" in a calm shot of
    the molasses tank made MiniMax burst it mid-clip; the shot's own action already says how it looks now.
    """
    parts = [part for part in re.split(r"\s*;\s*", item) if not re.search(r"\bbeats?\s*\d", part, re.I)]
    return re.sub(r"\s*\([^)]*\bbeats?\s*\d[^)]*\)", "", "; ".join(parts)).strip()


_COMMON_CAPITALS = {"the", "a", "an", "iron", "old", "new", "red", "white", "black"}


def construct_prompt(
    *,
    subject_action: str,
    camera_action: str,
    ambience: str,
    continuity: dict[str, Any],
    framing: str,
    backend: str,
    cast_names: list[str] | None = None,
    light: str = "",
    handoff: str = "",
) -> str:
    """One H3 prompt: what the camera sees, as plain positive description, about 150-250 words.

    Only this shot's own facts go in. Each line below exists because its absence was a recurring
    rejection: the cast count (duplicated heroes), the light held steady (night drifting to dawn),
    the screen geography (fleets swapping sides), and the recurring objects with their markings
    (the kettle and the ships changed design between shots because no prompt ever described them).
    """
    suffix = MINIMAX_SUFFIX if backend == "minimax" else WAN_SUFFIX
    style = generator_text(continuity.get("visual_style") or "photographic realism")
    parts = [f"Live-action, {style.rstrip('.')}, {framing}, 9:16 vertical frame, the picture filling it edge to edge."]
    characters = str(continuity.get("characters") or "")
    if cast_names:
        plural = len(cast_names) > 1
        parts.append(
            f"Exactly {len(cast_names)} named character{'s' if plural else ''} ({', '.join(cast_names)}), "
            f"each appearing once: {_sentence(generator_text(characters))} Every other figure is an anonymous extra in "
            "plain drab clothing, with other hair and none of their colours or signature items.")
    elif cast_names is not None:
        parts.append("None of the story's named characters; any people are anonymous background figures.")
    elif characters and characters != DEFAULT_CHARACTERS:
        parts.append(_sentence(generator_text(characters)))
    parts.append(_sentence(generator_text(subject_action)))
    end = generator_text(handoff) or generator_text(payoff_of(subject_action))
    if end and _MARKING.search(end) and not _MARKING.search(subject_action):
        # "marches right toward the Bulgarian flag" in the end state of a shot that shows no flag: MiniMax
        # drew one into the column mid-clip. The end state may not bring in a marking the shot never shows.
        end = re.sub(rf"\s+(?:toward|towards|to|under|beside|past|near|below)\s+[^,;.]*?{_MARKING.pattern}", "", end,
                     flags=re.I)
        end = re.sub(rf"[^,;]*{_MARKING.pattern}[^,;]*[,;]?", "", end, flags=re.I)
        end = re.sub(r"\s{2,}", " ", end).strip(" ,;")
    if end and end.rstrip(".") not in parts[-1]:
        parts.append(_sentence(f"By the end of the clip: {end}"))
    objects = generator_text("; ".join(_named_here(continuity.get("recurring_objects") or "", subject_action)))
    if objects:
        parts.append(_sentence(objects))
    # Which side each fleet or army holds only matters where sides are in view; in a close-up the
    # sentence's nouns ("Austrian ships always frame left") put ships into a shot of a kettle.
    if continuity.get("screen_geography") and framing_scale(subject_action) != "close":
        parts.append(_sentence(f"Screen geography: {generator_text(continuity['screen_geography'])}")
                     + " Opposing sides stay on their own side of the frame, facing each other across open space.")
    location = str(continuity.get("location") or "")
    if location and not location.startswith(DEFAULT_LOCATION):
        parts.append(_sentence(f"Setting: {generator_text(location)}"))
    if period_line(continuity):
        parts.append(_sentence(period_line(continuity)))
    palette = colours_only(str(continuity.get("palette") or ""))
    if palette and continuity["palette"] != DEFAULT_PALETTE:
        parts.append(_sentence(f"Colour palette: {generator_text(palette)}"))
    # A fixed "clear air" contradicted every hazy, smoky or ash-darkened light, and won: 28 reviews on
    # the volcano run said the sky came back pale and bright instead of ash-darkened.
    parts.append(_sentence(f"Light: {light}, held steady in every frame") if light
                 else "Natural daylight with real shadows.")
    parts.append(camera_prose(camera_action))
    parts.append(f"Photorealistic: {suffix}.")
    parts.append(H3_NO_TEXT)
    sound = f"{ambience}, environmental sound only, no voices" if ambience else ""
    return h3_prompt(" ".join(p for p in parts if p), sound)


def _physical_descriptions(beats: list[dict[str, Any]], concept: str) -> list[str]:
    """Return only filmable scene descriptions, replacing diagram/title-card instructions."""
    values: list[str | None] = []
    for beat in beats:
        visual = beat.get("visual") if isinstance(beat, dict) else None
        visual = visual if isinstance(visual, dict) else {}
        description = str(visual.get("description") or "").strip()
        kind = str(visual.get("kind") or "").lower()
        looks_graphic = any(token in description.lower() for token in (
            "card reading", "text reading", "title card", "stat card", "key phrase card",
            "timeline graphic", "diagram showing",
        ))
        values.append(None if kind == "diagram" or looks_graphic else description or None)
    if not values:
        return [f"A concrete physical action that advances the story of {concept}"]
    physical = [value for value in values if value]
    fallback = physical[0] if physical else f"A concrete physical action that advances the story of {concept}"
    result: list[str] = []
    for index, value in enumerate(values):
        if value:
            result.append(value)
            continue
        previous = next((values[i] for i in range(index - 1, -1, -1) if values[i]), None)
        following = next((values[i] for i in range(index + 1, len(values)) if values[i]), None)
        result.append(f"A direct visual continuation of {previous or following or fallback}")
    return result


def build_visual_screenplay(
    script: dict[str, Any],
    concept: str,
    continuity: dict[str, Any],
    descriptions: list[str],
) -> str:
    """Create the complete silent screenplay used as the project's source of truth."""
    beats = script.get("beats") if isinstance(script.get("beats"), list) else []
    premise = script.get("story_premise") or script.get("description") or concept
    goal = script.get("protagonist_goal") or "The protagonist pursues the goal established by the premise."
    stakes = script.get("stakes") or "Failure prevents the protagonist from resolving the central problem."
    payoff = script.get("ending_payoff") or "The final physical action resolves the opening setup."
    lines = [
        "FULL VISUAL SCREENPLAY — SILENT CONTEXT ONLY",
        f"Title: {script.get('video_title') or concept}",
        f"Premise: {premise}",
        f"Protagonist goal: {goal}",
        f"Stakes: {stakes}",
        f"Ending payoff: {payoff}",
        f"Cast and world bible: {continuity_text(continuity)}",
        "Sequence outline:",
    ]
    count = max(len(descriptions), len(beats))
    for index in range(count):
        beat = beats[index] if index < len(beats) and isinstance(beats[index], dict) else {}
        narration = str(beat.get("text") or "").strip()
        visual = descriptions[min(index, len(descriptions) - 1)]
        visual_data = beat.get("visual") if isinstance(beat.get("visual"), dict) else {}
        continuity_in = str(visual_data.get("continuity_in") or "").strip()
        continuity_out = str(visual_data.get("continuity_out") or "").strip()
        line = f"{index + 1:02d}. VISUAL: {visual}"
        if continuity_in:
            line += f" | INHERIT: {continuity_in}"
        if continuity_out:
            line += f" | HANDOFF: {continuity_out}"
        if narration:
            line += f" | VOICEOVER REFERENCE (never speak or display): {narration}"
        lines.append(line)
    return "\n".join(lines)


def beat_handoff(script: dict[str, Any], beat_index: int) -> str:
    """The state the shot ends on (`continuity_out`), which the next shot inherits."""
    return str(_beat_visual(script, beat_index).get("continuity_out") or "").strip()


def plan_shots(
    script: dict[str, Any],
    concept: str,
    duration_seconds: int,
    visual_style: str,
    preferred_backend: str = "auto",
    ambience: str = "natural scene ambience",
    fps: int = 30,
    shot_count: int | None = None,
) -> tuple[list[Shot], dict[str, Any]]:
    beats = script.get("beats") if isinstance(script.get("beats"), list) else []
    count = shot_count or len(beats) or shot_count_for_duration(duration_seconds)
    beat_texts = [str(beat.get("text") or "") for beat in beats] if beats else [""] * count
    frames = (allocate_story_frames(duration_seconds, beat_texts, fps) if len(beat_texts) == count
              else allocate_frames(duration_seconds, count, fps))
    narration = script.get("spoken_script") or " ".join(str(b.get("text") or "") for b in beats)
    # One beat per shot: its own sentence ("Dr. Cara" must not split at the abbreviation).
    texts = [str(b.get("text") or "").strip() for b in beats if isinstance(b, dict)]
    segments = texts if len(texts) == count and all(texts) else _split_text(narration, count)
    descriptions = _physical_descriptions(beats, concept)
    continuity = _continuity(script, visual_style, concept)
    prompt_backend = "minimax" if preferred_backend in ("auto", "minimax") else "wan"
    beat_of = [min(len(descriptions) - 1, math.floor(index * len(descriptions) / count)) for index in range(count)]
    labels = [beat_labels(script, beat) for beat in beat_of]
    names_cast = _names_cast(script)
    shots: list[Shot] = []
    for index in range(count):
        beat_index = beat_of[index]
        subject = descriptions[beat_index]
        cast_names = [str(c["name"]).strip() for c in beat_cast(script, beat_index)]
        # Each shot carries only the looks its beat needs (a cub scene never sees the adult).
        shot_continuity = _continuity(script, visual_style, concept, beat_index)
        camera, framing = _camera_plan(subject, index,
                                       chosen=_beat_visual(script, beat_index).get("camera"),
                                       handoff=beat_handoff(script, beat_index))
        scene_ambience = ambience or "natural location tone and specific diegetic details"
        transition = str(_beat_visual(script, beat_index).get("transition") or "cut")
        if index == 0 or transition not in {"cut", "match_cut", "crossfade"}:
            transition = "cut"
        shots.append(Shot(
            id=f"shot-{index + 1:03d}",
            index=index,
            duration_frames=frames[index],
            prompt=construct_prompt(
                subject_action=subject,
                camera_action=camera,
                ambience=scene_ambience,
                continuity=shot_continuity,
                framing=framing,
                backend=prompt_backend,
                cast_names=cast_names if names_cast else None,
                light=labels[index][1],
                handoff=beat_handoff(script, beat_index),
            ),
            negative_prompt=(
                "static image, frozen motion, black frame, low detail, flicker, duplicate subject, "
                "warped anatomy, broken geometry, abrupt lighting change, " + REALISM_BAN + ". " + QUALITY_BAN
            ),
            seed=_seed(script.get("video_title") or concept, index),
            narration=segments[index],
            ambience=scene_ambience,
            transition=transition,
            continuity=shot_continuity,
            subject_action=subject,
            camera_action=camera,
            scene=labels[index][0],
            light=labels[index][1],
            cast=cast_names,
        ))
    return shots, continuity


def reseed(shot: Shot, attempt: int) -> int:
    rng = random.Random(shot.seed + attempt * 104729)
    return rng.randint(0, 2**31 - 1)
