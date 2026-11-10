"""Photoreal first frames from FLUX.1-schnell for shots that open fresh.

Text-only video generation drifts into a soft, dreamy look; a sharp photographic still as the first
frame anchors MiniMax to real-world texture and light. Only fresh openings get one (the first shot
and hard cuts): continuing shots open on the previous clip's last frame, as before.

FLUX runs in FreeVideo's ComfyUI with core nodes only (an all-in-one fp8 checkpoint), before any
clip is generated, and is unloaded afterwards so MiniMax gets the GPU back. Any failure skips the
keyframes and the shot falls back to text-only generation.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import requests

from . import looks
from .comfy import ComfyClient, ComfyError
from .config import PipelineConfig, env_int
from .models import MANIFEST_LOCK, ProjectManifest, Shot
from .planner import (PHOTO_LOOK, _MARKING, _heading, _name_tokens, _singular, continuation_source, framing_for,
                      framing_scale, generator_text, shot_objects)
from .validation import bar_metrics, bar_problem

log = logging.getLogger("pipeline")

PEER_DRIVES = Path(r"C:\pinokio\drive\drives\peers")
# A keyframe that keeps failing review is dropped so the last takes can generate without it.
KEYFRAME_FAILURE_LIMIT = 2


def keyframe_takes(named: bool = False) -> int:
    """FLUX takes per keyframe before the shot falls back to text (each ~30 s plus one still review).

    A named character's shot gets more: its text-only fallback draws a stranger, which breaks identity.
    """
    takes = env_int("KEYFRAME_TAKES", 3, 1, 8)
    return min(8, takes + 2) if named else takes


def keyframes_enabled() -> bool:
    return env_int("LOCAL_VIDEO_KEYFRAMES", 1, 0, 1) == 1


def checkpoint_name() -> str:
    return os.getenv("KEYFRAME_CHECKPOINT", "flux1-schnell-fp8.safetensors")


def models_dir() -> Path | None:
    """Folder whose checkpoints/ holds the FLUX checkpoint (KEYFRAME_MODELS_DIR, else a Pinokio drive)."""
    configured = os.getenv("KEYFRAME_MODELS_DIR")
    if configured:
        return Path(configured).expanduser()
    if PEER_DRIVES.is_dir():
        for found in PEER_DRIVES.glob(f"*/checkpoints/{checkpoint_name()}"):
            return found.parent.parent
    return None


def has_checkpoint(url: str) -> bool:
    try:
        spec = requests.get(f"{url}/object_info/CheckpointLoaderSimple", timeout=30).json()
        choice = spec["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"]
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return False
    # Older ComfyUI lists the names first; newer sends ["COMBO", {"options": [...]}].
    names = choice[0] if isinstance(choice[0], list) else (choice[1] or {}).get("options", [])
    return checkpoint_name() in names


def keyframe_path(manifest: ProjectManifest, shot: Shot) -> Path:
    return Path(manifest.project_dir) / "keyframes" / f"{shot.id}.png"


def fresh_openings(manifest: ProjectManifest) -> list[int]:
    """Shots that open on no earlier frame: the first (without a user reference) and hard cuts."""
    labels = [(s.scene.lower(), s.light.lower()) for s in manifest.shots]
    casts = [s.cast for s in manifest.shots]
    scales = [framing_scale(s.subject_action) for s in manifest.shots]
    objects = [shot_objects(manifest.script, s.continuity) for s in manifest.shots]
    forced = set(manifest.settings.get("open_fresh", []))    # set by the shot doctor (see queue)
    indices = []
    for index, shot in enumerate(manifest.shots):
        if index == 0:
            if not manifest.reference_image:
                indices.append(index)
        elif shot.scene and (shot.id in forced or continuation_source(labels, index, casts, scales, objects) is None):
            indices.append(index)
    return indices


def keyframe_id(path: Path) -> str:
    """Fingerprint of one keyframe file, so a regenerated keyframe does not inherit its predecessor's failures."""
    stat = path.stat()
    return f"{stat.st_size}-{stat.st_mtime_ns}"


def usable_keyframe(manifest: ProjectManifest, shot: Shot) -> Path | None:
    path = keyframe_path(manifest, shot)
    if not path.is_file():
        return None
    current, written = keyframe_id(path), path.stat().st_mtime

    def used_this_keyframe(attempt: dict) -> bool:
        if attempt.get("keyframe") is True:      # recorded before fingerprints: this file, unless it is newer
            return written <= float(attempt.get("started_at") or written)
        return attempt.get("keyframe") == current

    threshold = env_int("LOCAL_VIDEO_VISION_MIN_SCORE", 7, 1, 10)

    def judged(attempt: dict) -> bool:
        # Only a review that faults what the opening frame decides says anything about the keyframe. A crash
        # or restart ("generation process ended") and two takes rejected only for too little motion once
        # retired shot-001's keyframe (visual_match 8, continuity 8) and sent its retakes out text-only.
        if attempt.get("status") != "failed" or not used_this_keyframe(attempt):
            return False
        review = (attempt.get("validation") or {}).get("semantic_review")
        if not isinstance(review, dict):
            return False
        return bool(review.get("fatal_problems")) or any(
            int(review.get(name, threshold)) < threshold for name in ("visual_match", "continuity"))

    failed = sum(1 for attempt in shot.attempts if judged(attempt))
    return path if failed < KEYFRAME_FAILURE_LIMIT else None


def _clip_sentences(text: str, limit: int) -> str:
    """Whole sentences up to limit characters; a cut mid-word ("near the main cone, n.") reads as noise."""
    if len(text) <= limit:
        return text
    kept = ""
    for sentence in re.split(r"(?<=[.;])\s+", text):
        if len(kept) + len(sentence) + 1 > limit:
            break
        kept = f"{kept} {sentence}".strip()
    return kept or text[:limit].rsplit(" ", 1)[0]


_NEGATED_CLAUSE = re.compile(r"[,;]?\s*\b(?:with\s+)?(?:no|without)\s+[^,.;]+", re.I)


def _flux_text(text: str) -> str:
    """Screenplay text as FLUX should read it: no honesty labels, no negated clauses.

    FLUX runs at cfg 1 with an empty negative, and its text encoders do not read negation, so "no
    markings or writing visible" asks for markings and writing (the 2026-10-29 reviewer found hull
    text on a keyframe whose brief said exactly that).
    """
    return re.sub(r"\s{2,}", " ", _NEGATED_CLAUSE.sub("", generator_text(text))).strip(" ,;")


# FLUX renders an abstract expression as a neutral or stern face: "deliberately vacant" came back as an
# alert stare in every take of Hegdahl shot-006, and "jaw slack, eyes unfocused" or "dazed, daydreaming"
# after the subject as a wistful upward gaze. Blunt words at the very start of the prompt opened his mouth
# into a blank stare (2026-10-30 test, same seeds): the face leads the prompt.
_EXPRESSIONS = (
    (r"\b(?:vacant|blank|foolish|dim-witted|simple-minded|empty) (?:expression|look|stare|face|gaze)|\bplay(?:s|ing)? dumb",
     "a slack-jawed, dumbfounded face, mouth wide open, vacant glassy eyes staring at nothing, head tilted"),
    (r"\b(?:terrified|frightened|fearful|panicked)\b",
     "a terrified face, eyes wide open with white showing, eyebrows raised, mouth open in a gasp"),
    (r"\b(?:exhausted|weary|worn out)\b",
     "an exhausted face, heavy half-closed eyelids, dark circles under the eyes, mouth slack"),
    (r"\b(?:laughing|laughs)\b", "a laughing face, mouth wide open in laughter, eyes creased nearly shut"),
)


_GROUP = re.compile(r"\b(?:column|troops|soldiers|file of|march\w*|procession|platoon|regiment|army|convoy|caravan|"
                    r"herd|flock|crowd|parade)\b", re.I)


_TO_CAMERA = re.compile(r"\b(?:faces?|facing|looks?|looking|stares?|staring|turns?)\s+(?:straight\s+)?"
                        r"(?:at|into|toward|towards)\s+(?:the\s+)?(?:camera|lens|viewer)\b", re.I)


def _facing_lines(shot: Shot) -> str:
    """Each named character's facing from the screen-geography lock, in words FLUX draws.

    The keyframe reviewer rejects a named character facing against the lock (the clip review does too),
    yet the prompt never carried it: Hegdahl faced the camera or frame left in shots 6, 20 and 21.
    A beat that turns someone to the camera keeps its own staging.
    """
    geography = str((shot.continuity or {}).get("screen_geography") or "")
    if not geography or _TO_CAMERA.search(shot.subject_action):
        return ""
    lines = []
    for name in shot.cast or []:
        tokens = [re.escape(t) for t in _name_tokens(name, [c for c in shot.cast if c != name])] or [re.escape(name)]
        found = re.search(rf"\b(?:{'|'.join(tokens)})\b[^.;]*?\bfacing\s+(?:frame\s+)?(left|right)\b", geography)
        if found:
            lines.append(f"{name} is turned toward the {found.group(1)} edge of the picture, face in three-quarter "
                         f"view looking {found.group(1)}")
    return "; ".join(lines)


# The reviewer's mirror_fixes flag alone came back true for takes also failing on wardrobe and identity.
_MIRRORABLE = re.compile(r"\b(?:fac(?:e|es|ing)|left|right|mirror\w*|side|profile|direction|heading)\b", re.I)


# A substance has no fixed shape to lock: the molasses card ("...filling a large round riveted steel tank")
# put a giant tank into every street the molasses flooded.
_SUBSTANCE = re.compile(r"\b(?:molasses|water|flood|wave|smoke|fire|flames?|steam|mud|oil|lava|ash|dust|snow|"
                        r"rain|fog|mist|sea|river|tide|syrup|liquid|blood|clouds?)\b", re.I)


def recurring_subjects(manifest: ProjectManifest, shot: Shot) -> dict[str, str]:
    """label -> description of the script's recurring subjects this shot's own text shows.

    Matched when every word of the label is in the shot's text ("The dog" -> dog, "The border marker" ->
    border and marker), so a shot about "the tan dog" finds it. The label's last word alone anchored "the
    crumpled tank steel" (the wreckage) to a frame of the intact tank, which merely mentioned riveted steel.
    Side markings (flags) are left out: their geometry is already exact text. A designed frame (fast mode)
    names the subjects it shows itself in continuity["subjects_shown"]: word matching never found "The
    sultan's palace" (no "s" in the text) or "British warships" (the frames say "grey steel warships"), and
    the Zanzibar palace came out as a different building in every shot.
    """
    words = {_singular(word) for word in re.findall(r"[a-z]+", shot.subject_action.lower())}
    shown = (shot.continuity or {}).get("subjects_shown")
    found = {}
    for item in manifest.script.get("recurring_objects") or []:
        label, _, description = str(item).partition(":")
        label = re.sub(r"\(.*?\)", "", label).strip()
        if isinstance(shown, list):
            if (label in shown and description and not _MARKING.search(label + description[:60])
                    and not _SUBSTANCE.search(label)):
                found[label] = description.strip()
            continue
        nouns = [word for word in re.findall(r"[a-z]+", label.lower()) if word not in ("the", "a", "an", "of")]
        if not description or not nouns or _MARKING.search(label + description[:60]) or _SUBSTANCE.search(label):
            continue
        if all(_singular(noun) in words for noun in nouns) and not _changed_near(shot.subject_action, nouns[-1]):
            found[label] = description.strip()
    return found


# A subject the shot shows destroyed is no longer its anchored self: "torn plates from the tank" drew the
# intact tank behind its own wreckage (molasses shot-019).
_DESTROYED = re.compile(r"\b(?:burst|torn|tore|wreck\w*|crumpl\w*|collaps\w*|broken|shatter\w*|ruin\w*|debris|"
                        r"fragments?|remains|pieces|split|ripped|smashed|crushed|destroyed|twisted)\b", re.I)


def _changed_near(text: str, noun: str) -> bool:
    for found in re.finditer(rf"\b{re.escape(noun)}\w*", text, re.I):
        if _DESTROYED.search(text[max(0, found.start() - 70): found.end() + 70]):
            return True
    return False


def _anchor_new_subjects(manifest: ProjectManifest, shot: Shot, keyframe: Path, present: dict[str, str],
                         subject_anchors: dict[str, dict[str, str]], describe) -> None:
    """Make an accepted keyframe the reference of each recurring subject it shows that has none yet."""
    for label, description in present.items():
        if label in subject_anchors:
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or "subject"
        anchor = Path(manifest.project_dir) / "keyframes" / f"subject-{slug}.png"
        anchor.write_bytes(keyframe.read_bytes())
        card = describe(anchor, label, description)
        subject_anchors[label] = {"path": str(anchor.relative_to(manifest.project_dir)), "shot": shot.id,
                                  "card": card}
        log.info("Subject anchor for %s from %s: %s", label, shot.id, card[:160])
        manifest.record("subject_anchor", label=label, shot=shot.id, card=card)


def _mirror(path: Path) -> None:
    from PIL import Image, ImageOps
    with Image.open(path) as image:
        flipped = ImageOps.mirror(image)
    flipped.save(path)


def _restaged(shot: Shot, outfits: dict[str, str], failed: str) -> str:
    """The shot doctor's staging of a shot whose first frames keep failing, for FLUX to draw instead."""
    from . import shot_doctor
    if not shot_doctor.enabled():
        return ""
    try:       # only an improvement: a broken doctor once stopped every keyframe of an unattended run
        result = shot_doctor.examine(shot, "", None, outfits,
                                     failed=f"First frames drawn for this shot were rejected for: {failed}")
    except Exception as exc:
        log.warning("Keyframe %s restaging skipped: %s", shot.id, exc)
        return ""
    if not result:
        return ""
    log.info("Keyframe %s restaged by the shot doctor: %s", shot.id, result["description"][:200])
    return _flux_text(result["description"])


def wardrobe_for(manifest: ProjectManifest, shot: Shot, describe=None) -> dict[str, str]:
    """name -> what they wear in their latest accepted earlier shot with the same planned look.

    Cached per source shot, so each accepted frame is described once. A script's planned look change
    (look_changes) starts a new wardrobe: only shots whose look text matches carry it over.
    """
    from .planner import character_look
    if describe is None:
        from .visual_review import describe_outfit as describe
    characters = {str(c.get("name") or "").strip(): c for c in manifest.script.get("characters") or []
                  if isinstance(c, dict)}
    cache: dict[str, str] = manifest.settings.setdefault("outfits", {})
    outfits = {}
    for name in shot.cast or []:
        character = characters.get(name)
        look = character_look(character, shot.index) if character else ""
        for prior in reversed(manifest.shots[:shot.index]):
            if (name not in (prior.cast or []) or prior.status != "accepted" or not prior.last_frame
                    or (character and character_look(character, prior.index) != look)):
                continue
            frame = Path(manifest.project_dir) / prior.last_frame
            if not frame.is_file():
                continue
            key = f"{prior.id}:{name}"
            if key not in cache:
                cache[key] = describe(frame, name, str((shot.continuity or {}).get("characters") or ""))
            if cache[key]:
                outfits[name] = cache[key]
            break
        anchor = (manifest.settings.get("identity_anchors") or {}).get(name) or {}
        if name in outfits or not anchor.get("path"):
            continue
        # Before any shot of theirs is accepted, the identity anchor sets the outfit: keyframes are drawn
        # in one batch at the start, and without it FLUX dressed Hegdahl gray-green in shots 1, 3 and 6
        # and navy everywhere else.
        source = next((s for s in manifest.shots if s.id == anchor.get("shot")), None)
        frame = Path(manifest.project_dir) / anchor["path"]
        if (not frame.is_file() or (character and source is not None
                                    and character_look(character, source.index) != look)):
            continue
        key = f"anchor:{name}:{anchor['path']}"
        if key not in cache:
            cache[key] = describe(frame, name, str((shot.continuity or {}).get("characters") or ""))
        if cache[key]:
            outfits[name] = cache[key]
    return outfits


def identity_anchor_path(manifest: ProjectManifest, name: str) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "character"
    return Path(manifest.project_dir) / "keyframes" / f"identity-{slug}.png"


_CHANGEABLE = {
    "hair": ("hair",),
    "beard": ("beard", "stubble", "moustache", "mustache", "facial hair", "clean-shaven", "shaven"),
    "build": ("thin", "gaunt", "weight", "build", "emaciated"),
}


def _card_for(card: str, action: str) -> str:
    """The identity card minus whatever this shot's action changes ("hair already grown longer").

    Hegdahl run shot-016: the card's "short hair" fought the action's longer hair on every take.
    """
    action = action.lower()
    changed = [words for words in _CHANGEABLE.values() if any(word in action for word in words)]
    if not changed:
        return card
    kept = [part for part in re.split(r";\s*", card)
            if not any(word in part.lower() for words in changed for word in words)]
    return "; ".join(kept)


def keyframe_prompt(shot: Shot, cards: dict[str, str] | None = None, outfits: dict[str, str] | None = None,
                    subjects: dict[str, str] | None = None) -> str:
    """The still the clip opens on, described the same way the clip itself is.

    This image becomes the clip's first frame AND the continuity reference the reviewer compares
    that frame against, so anything the clip brief says about look that is missing here turns into a
    rejection. It used to omit `visual_style`, which carries the palette and grade: a brief asking
    for an ash-grey sky and a charcoal-and-steel grade produced a pale-blue cone under a clear sky,
    and the reviewer then reported "frame 1 does not match the start image".

    Where the camera stands and the light lead the prompt, ahead of the subject: FLUX weighs the
    opening words most, and with them buried after the setting every volcano keyframe came out as a
    drone view under a pale sky, even for an "ash-darkened overcast" shot. MiniMax cannot move the
    camera down to the sea or darken the sky in three seconds, so every take of those shots failed.
    """
    continuity = shot.continuity or {}
    cutaway = looks.is_cutaway(continuity)
    light = shot.light or (looks.CUTAWAY_LIGHT if cutaway else continuity.get("time_of_day"))
    face = next((mechanics for pattern, mechanics in _EXPRESSIONS if re.search(pattern, shot.subject_action, re.I)),
                "")
    framing = framing_for(shot.subject_action, shot.camera_action)
    if cutaway:
        # "Photograph" would pull FLUX toward camera footage; the render and the cut lead instead.
        parts = [f"Photoreal 3D cutaway cross-section render, {looks.cutaway_framing(framing)}, the ground and "
                 "structures sliced open to show their inside"]
    else:
        parts = [f"Photograph of {face}, {framing}" if face else f"Photograph, {framing}"]
    if light:
        parts.append(f"Light and sky in every part of the frame: {light}")
    parts.append(f"Subject: {_flux_text(shot.subject_action)}")
    for label, card in (subjects or {}).items():   # the same dog and the same stone as in earlier shots
        if card:
            parts.append(f"{label[:1].upper()}{label[1:]} looks exactly like this: {card}")
    heading = _heading(shot.subject_action)
    if heading:
        # FLUX does not read "toward frame right": three takes of a ship steaming right came back bow-on,
        # heading at the camera (Hegdahl shot-004). A side view with the front named by its edge it draws.
        other = "left" if heading == "right" else "right"
        # Not for a marching group: FLUX draws a column on a road receding from the camera whatever the words
        # say (13 side-on stray-dog frames failed in four wordings, landscape crops included); pushing it
        # sideways only fights the march-away it draws well. The script stages groups that way instead.
        if not _GROUP.search(shot.subject_action):
            parts.append(f"Seen side-on in profile, broadside to the camera: its front points to the {heading} "
                         f"edge of the picture and its back to the {other} edge")
    facing = _facing_lines(shot)
    if facing:
        parts.append(facing)
    if re.search(r"\b(?:flags?|banners?|ensigns?|tricolou?rs?)\b", shot.subject_action, re.I):
        # The stray-dog shot-004 drew the Bulgarian flag floating in front of its pole, pole through its middle.
        parts.append("Each flag is fastened along one short edge to the top of its own pole and flies out from it; "
                     "every pole is planted in the ground, fixed to a building or held in a person's hands")
    # Who it is comes right after what happens: FLUX weighs early words most, and with the look last
    # every keyframe drew a different face, age and hair for the same named person.
    cards = {name: _card_for(card, shot.subject_action) for name, card in (cards or {}).items()
             if card and name in (shot.cast or [])}
    if shot.cast and (cards or continuity.get("characters")):
        names = ", ".join(shot.cast)
        # The card fixes the body (age, face, hair); the script's lock still says what they wear now.
        look = "; ".join(f"{name}: {card}" for name, card in cards.items())
        lock = _flux_text(str(continuity.get("characters") or ""))
        look = f"{look}. {lock}"[:700] if look and lock else (look or lock[:500])
        worn = "; ".join(f"{name} wears exactly: {outfit}" for name, outfit in (outfits or {}).items() if outfit)
        parts.append(f"Exactly one of each named person ({names}), each a single unique individual; everyone "
                     f"else dressed differently. Look: {look}" + (f". {worn}" if worn else ""))
    if continuity.get("location"):
        parts.append(f"Setting: {_clip_sentences(_flux_text(str(continuity['location'])), 400)}")
    if continuity.get("period"):             # positive only: FLUX reads "never modern" as "modern"
        parts.append(f"Period: {continuity['period']}, everything in frame of that era, aged and long used")
    style = continuity.get("visual_style")
    if style and not (cutaway and looks.CUTAWAY_STYLE[:60] in str(style)):
        # the same palette and grade the clip is rendered with (a cutaway's fixed style closes the prompt)
        parts.append(f"Visual style: {_flux_text(str(style))[:400]}")
    parts.append("9:16 portrait composition, the subject filling a clear share of the frame")
    if cutaway:
        # Word for word in every still, so every shot is drawn in the same world and light.
        parts.append(f"Style: {looks.CUTAWAY_STYLE}. {looks.CUTAWAY_RENDER}, no people, plain unmarked surfaces")
    else:
        parts.append(f"{PHOTO_LOOK}, realistic skin with pores and fine wrinkles, worn real materials, "
                     "plain unmarked surfaces")
    return ". ".join(part.rstrip(". ") for part in parts) + "."


def workflow(prompt: str, seed: int, width: int, height: int) -> dict[str, Any]:
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint_name()}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["1", 1]}},
        "4": {"class_type": "EmptySD3LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0],
            "seed": seed, "steps": env_int("KEYFRAME_STEPS", 4, 1, 50), "cfg": 1.0,
            "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "vc_keyframe"}},
    }


def _image_item(history: dict[str, Any]) -> dict[str, Any]:
    for node in (history.get("outputs") or {}).values():
        for item in node.get("images", []) if isinstance(node, dict) else []:
            if str(item.get("filename", "")).lower().endswith(".png"):
                return item
    raise ComfyError("ComfyUI completed but returned no keyframe image")


def _fit(source: Path, target: Path, config: PipelineConfig) -> None:
    """Crop the still to MiniMax's frame so the first frame is not stretched."""
    width, height = config.minimax_width, config.minimax_height
    subprocess.run(
        [config.ffmpeg, "-y", "-loglevel", "error", "-i", str(source), "-vf",
         f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,crop={width}:{height}",
         str(target)],
        check=True, capture_output=True, timeout=120,
    )


def _anchor_new_identities(manifest: ProjectManifest, shot: Shot, keyframe: Path,
                           anchors: dict[str, dict[str, str]], describe) -> None:
    """Make a strictly passed keyframe the identity reference of its one named character, if none yet.

    Only single-character frames anchor: with two named people the describer could swap them.
    """
    cast = list(shot.cast or [])
    if len(cast) != 1 or cast[0] in anchors:
        return
    name = cast[0]
    anchor = identity_anchor_path(manifest, name)
    anchor.write_bytes(keyframe.read_bytes())
    lock = str((shot.continuity or {}).get("characters") or "")
    anchors[name] = {"path": str(anchor.relative_to(manifest.project_dir)), "shot": shot.id,
                     "appearance": describe(anchor, name, lock)}
    log.info("Identity anchor for %s from %s: %s", name, shot.id, anchors[name]["appearance"][:200])
    manifest.record("identity_anchor", name=name, shot=shot.id, appearance=anchors[name]["appearance"])


# A flawed take may be kept for a wrong hat or a loose lock detail, never for what looks wrong on screen:
# the Potsdam run kept "a red pom-pom ... reads as a surreal artifact" on the king's head (shot-018).
_WEIRD = re.compile(r"\b(?:surreal|cgi|render\w*|illustrat\w*|cartoon\w*|painterly|artifact\w*|melt\w*|"
                    r"distort\w*|warp\w*|broken|fused|extra (?:limb|arm|leg|hand|finger|head)\w*|floating|"
                    r"text|letter\w*|lettering|logo\w*|watermark\w*|blank|empty frame|"
                    r"modern|anachronis\w*|wrong era|giant)\b", re.I)
# The same for a cutaway film, which IS a render: "the render shows..." is no flaw there.
_WEIRD_CUTAWAY = re.compile(_WEIRD.pattern.replace(r"cgi|render\w*|illustrat\w*|", ""), re.I)


def _weird(problem: str, shot: Shot) -> bool:
    return bool((_WEIRD_CUTAWAY if looks.is_cutaway(shot) else _WEIRD).search(problem))


def _gpu_take(client_for, prompt: str, seed: int, width: int, height: int, raw: Path, config: PipelineConfig,
              recover, stop: threading.Event) -> None:
    """One FLUX image into `raw`; a dead or wedged ComfyUI is recovered and the take tried again."""
    for attempt in range(3):
        if stop.is_set():
            raise ComfyError("keyframes stopped: ComfyUI is not responding")
        client = client_for()
        try:
            prompt_id = client.submit(workflow(prompt, seed, width, height))
            client.download(_image_item(client.wait(prompt_id)), raw)
            return
        except (ComfyError, TimeoutError, requests.RequestException) as exc:
            failure = str(exc).lower()
            infrastructure = isinstance(exc, (TimeoutError, requests.RequestException)) or any(
                sign in failure for sign in ("timed out", "out of memory", "connection lost", "refused",
                                             "connection aborted", "reset"))
            if not infrastructure or attempt == 2 or not recover(exc):
                raise


def prepare_keyframes(manifest: ProjectManifest, config: PipelineConfig, selected: set[int] | None = None, *,
                      workers: int = 1, view=None, on_ready=None, all_shots: bool = False,
                      keep_flawed: bool = False) -> int:
    """Generate any missing keyframes for pending fresh openings; returns how many were made.

    workers > 1 draws keyframes while earlier ones are still being reviewed: FLUX takes ~15 s and its
    review ~40 s, so one shot at a time left the GPU idle for 70% of the molasses run's 30-minute
    keyframe stage. `view(shot)` is the shot as its frame is drawn and judged (fast mode's designed
    frame); `on_ready(index, path)` runs on the worker as soon as a shot's keyframe is accepted.
    `all_shots` gives every shot its own keyframe (fast mode cuts between all shots). `keep_flawed` keeps
    the best-scored take with sound anatomy when every take had a fatal problem: in fast mode a shot with
    no keyframe at all became an unplanned text-only clip (Zanzibar shot-011, rejected for a watch's numerals).
    """
    if not keyframes_enabled() or not config.minimax_url:
        return 0
    view = view or (lambda shot: shot)
    redone: list[str] = manifest.settings.setdefault("keyframes_redone", [])
    redraws = env_int("KEYFRAME_REDRAWS", 2, 0, 5)
    openings = list(range(len(manifest.shots))) if all_shots else fresh_openings(manifest)
    for index in openings:
        shot = manifest.shots[index]
        path = keyframe_path(manifest, shot)
        # A keyframe retired by real rejections is redrawn rather than left to text-only, which for a named
        # character means a stranger's face (Hegdahl run shot-006: a stern stare for "vacant") and for any
        # shot lets MiniMax frame it itself: shot-004's text-only takes came back letterboxed and as three
        # stacked panels.
        if (shot.status != "accepted" and redone.count(shot.id) < redraws and path.is_file()
                and (selected is None or index + 1 in selected)
                and usable_keyframe(manifest, shot) is None):
            retired = Path(manifest.project_dir) / "superseded" / "keyframes-retired"
            retired.mkdir(parents=True, exist_ok=True)
            path.replace(retired / f"{shot.id}-{int(time.time())}.png")
            redone.append(shot.id)
            manifest.record("keyframe_retired_redraw", shot=shot.id)
    pending = [
        index for index in openings
        if (selected is None or index + 1 in selected)
        and manifest.shots[index].status != "accepted"
        and not keyframe_path(manifest, manifest.shots[index]).is_file()
    ]
    if on_ready is not None:      # a keyframe an earlier run accepted still needs its follow-up step
        for index in openings:
            shot = manifest.shots[index]
            path = keyframe_path(manifest, shot)
            if (index not in pending and (selected is None or index + 1 in selected)
                    and shot.status != "accepted" and path.is_file()):
                on_ready(index, path)
    if not pending:
        return 0
    if not has_checkpoint(config.minimax_url):
        log.warning("Keyframes skipped: %s is not visible to ComfyUI at %s (set KEYFRAME_MODELS_DIR "
                    "and restart FreeVideo)", checkpoint_name(), config.minimax_url)
        manifest.record("keyframes_skipped", reason="checkpoint not found")
        return 0
    from .upscale import stop_idle_freevideo_worker
    stop_idle_freevideo_worker()        # MiniMax's resident weights would leave FLUX no VRAM
    # FreeVideo also keeps MiniMax loaded inside ComfyUI itself: after an interrupted take it held 5.5 GB,
    # FLUX ran out of memory, ComfyUI wedged and the keyframe waited the full 900 s.
    timeout = env_int("KEYFRAME_TIMEOUT", 300, 60, 1800)
    ComfyClient(config.minimax_url, timeout=timeout, poll_seconds=1.0).free_memory()
    width = env_int("KEYFRAME_WIDTH", 720, 256, 2048) // 16 * 16
    height = env_int("KEYFRAME_HEIGHT", 1280, 256, 2048) // 16 * 16
    from . import visual_review
    threshold = env_int("LOCAL_VIDEO_VISION_MIN_SCORE", 7, 1, 10)
    # name -> {"path", "appearance"}: the first strictly passed keyframe of each named character, so every
    # later keyframe draws and is checked against the same person (FLUX itself takes no reference image).
    anchors: dict[str, dict[str, str]] = manifest.settings.setdefault("identity_anchors", {})
    # label -> {"path", "shot", "card"}: the same, for recurring animals and objects (the dog, the stone)
    subject_anchors: dict[str, dict[str, str]] = manifest.settings.setdefault("subject_anchors", {})
    parallel = workers > 1 and len(pending) > 1
    stop = threading.Event()
    local = threading.local()
    recover_lock = threading.Lock()

    def client_for() -> ComfyClient:
        if getattr(local, "client", None) is None or local.client.base_url != config.minimax_url:
            local.client = ComfyClient(config.minimax_url, timeout=timeout, poll_seconds=1.0)
        return local.client

    def recover(exc: Exception) -> bool:
        """Bring ComfyUI back once for everyone; False stops every keyframe."""
        with recover_lock:
            if stop.is_set():
                return False
            from .config import probe_node
            if parallel and probe_node(config.minimax_url, "CheckpointLoaderSimple"):
                # Alive: another worker already restarted it, or this job alone failed. Clearing the queue
                # here (as a lone run does) would abort the other workers' takes.
                return True
            # A CUDA out-of-memory error leaves ComfyUI "running" its job forever at 0% GPU (stray-dog
            # shot-014), and a native abort inside FLUX kills it outright (shot-021). Bring it back.
            from .freevideo import recover_server
            recovered = recover_server(config)
            if not recovered or recovered.startswith("restart failed"):
                log.warning("Keyframes stopped: ComfyUI is not responding (%s)", str(exc)[:160])
                stop.set()
                return False
            log.warning("ComfyUI recovered (%s); continuing", recovered)
            manifest.record("comfy_recovered", detail=recovered)
            ComfyClient(config.minimax_url, timeout=timeout, poll_seconds=1.0).free_memory()
            return True

    # Recurring people and subjects are drawn from the first accepted frame of each, so a shot that needs
    # an anchor still being made waits for it; a shot that owns anchors never waits (no deadlock).
    gate = threading.Lock()
    owners: dict[str, threading.Event] = {}

    def missing_anchors(shot: Shot, drawn: Shot) -> set[str]:
        names = {f"cast:{name}" for name in shot.cast or [] if name not in anchors}
        labels = {f"subject:{label}" for label in recurring_subjects(manifest, drawn) if label not in subject_anchors}
        return names | labels

    def claim(shot: Shot, drawn: Shot) -> dict[str, threading.Event]:
        if not parallel:
            return {}
        while True:
            with gate:
                missing = missing_anchors(shot, drawn)
                waits = [owners[key] for key in missing if key in owners and not owners[key].is_set()]
                if not waits:
                    mine = {key: threading.Event() for key in missing}
                    owners.update(mine)
                    return mine
            for event in waits:
                event.wait(900)

    def draw(index: int) -> str:
        """One shot's takes until a keyframe is accepted. Returns "made", "failed" or "stop"."""
        shot = manifest.shots[index]
        drawn = view(shot)
        mine = claim(shot, drawn)
        target = keyframe_path(manifest, shot)
        started = time.monotonic()
        root = Path(manifest.project_dir)
        best, best_score = target.with_suffix(".best.png"), -1.0
        # Last resort for a named character: the right face with loose blocking. Text-only draws a
        # stranger (Hegdahl run shot-016), which no clip retake can repair; blocking it can.
        likeness, likeness_score = target.with_suffix(".likeness.png"), -1.0
        flawed, flawed_score = target.with_suffix(".flawed.png"), -1.0
        hires: dict[str, Path | None] = {"take": None, "best": None, "likeness": None, "flawed": None}
        take = 0
        try:
            with MANIFEST_LOCK:
                identities = [(name, root / anchors[name]["path"]) for name in shot.cast or []
                              if name in anchors and (root / anchors[name]["path"]).is_file()]
                cards = {name: anchors[name].get("appearance", "") for name, _ in identities}
                present = recurring_subjects(manifest, drawn)
                subjects = [(label, root / subject_anchors[label]["path"]) for label in present
                            if label in subject_anchors and (root / subject_anchors[label]["path"]).is_file()]
                subject_cards = {label: subject_anchors[label].get("card", "") for label, _ in subjects}
                outfits = wardrobe_for(manifest, shot)
            prompt, problems = keyframe_prompt(drawn, cards, outfits, subject_cards), []
            facing = re.search(r"turned toward the (left|right) edge", _facing_lines(drawn))
            needed = _heading(drawn.subject_action) or (facing.group(1) if facing else "")
            staged = ""
            # Each take is reviewed against the shot's blocking before any clip is built on it; a
            # rejected still is retried with a new seed and the reviewer's positive correction.
            takes = keyframe_takes(bool(shot.cast))
            if all_shots and not keep_flawed:
                # Without a first frame the clip comes from text: the molasses hook's four text-only takes all
                # failed (~13 min of MiniMax). A few more FLUX takes (~15 s each) are far cheaper.
                takes = max(takes, env_int("KEYFRAME_RESCUE_TAKES", 6, 1, 10))
            if keep_flawed:
                # Fast mode keeps its best sound take anyway: the Potsdam run spent five takes on each of
                # four king shots (~20 FLUX runs) for frames no better than their third.
                takes = min(takes, 3)
            for take in range(takes):
                seed = shot.seed + take * 7919
                raw = target.with_name(f"{shot.id}.t{take + 1}.raw.png")
                _gpu_take(client_for, prompt, seed, width, height, raw, config, recover, stop)
                _fit(raw, target, config)
                hires["take"] = None
                if raw.is_file():          # the full FLUX frame, for a parallax still (fast mode)
                    hires["take"] = raw.with_name(f"{shot.id}.t{take + 1}.hires.png")
                    raw.replace(hires["take"])
                boxed = bar_problem(bar_metrics(target))
                review = ({"valid": False, "skipped": False, "score": 0, "fatal_problems": [boxed],
                           "problems": [], "correction": "one photograph filling the whole vertical frame "
                                                         "edge to edge"}
                          if boxed else visual_review.review_keyframe(target, drawn, identities, outfits,
                                                                      subjects=subjects))
                lateral = review.get("subject_heading") in ("left", "right") and needed in ("left", "right")
                if (lateral and review["subject_heading"] != needed and not review.get("valid")) or (
                        review.get("mirror_fixes") and all(_MIRRORABLE.search(p) for p in review["fatal_problems"])):
                    # FLUX often draws the right frame facing the wrong way: direction was 42% of the stray-dog
                    # run's keyframe rejections, Hegdahl shot-021 faced left in three takes. A photo with no
                    # lettering mirrors cleanly, and the reviewer's own heading says when to flip.
                    _mirror(target)
                    mirrored = visual_review.review_keyframe(target, drawn, identities, outfits, subjects=subjects)
                    log.info("Keyframe %s take %d mirrored: %s", shot.id, take + 1,
                             "passed" if mirrored["valid"] else "still rejected")
                    if mirrored["valid"]:
                        review = mirrored
                        if hires["take"] is not None:
                            _mirror(hires["take"])
                    else:              # a flipped face can lose likeness to the anchor: keep the original
                        _mirror(target)
                soft = (not review.get("valid") and not review.get("skipped") and not review.get("fatal_problems")
                        and int(review.get("anatomy", 0)) >= threshold
                        and int(review.get("realism", 0)) >= threshold - 1
                        and int(review.get("composition_match", 0)) >= threshold - 1)
                manifest.record("keyframe_review", shot=shot.id, take=take + 1, valid=review["valid"],
                                soft=soft, score=review.get("score"),
                                problems=(review.get("fatal_problems") or []) + (review.get("problems") or []))
                if soft:
                    # Only 7 of 120 stray-dog takes passed outright, and the shot usually kept its best soft
                    # miss anyway, after 2-4 more takes (~45 s each). The clip review is the real gate.
                    log.info("Keyframe %s take %d accepted with soft misses (%s)", shot.id, take + 1,
                             review.get("score"))
                    with MANIFEST_LOCK:
                        if parallel:     # a sound face anchors the rest instead of serializing them
                            _anchor_new_identities(manifest, shot, target, anchors, visual_review.describe_identity)
                        _anchor_new_subjects(manifest, shot, target, present, subject_anchors,
                                             visual_review.describe_subject)
                    break
                if review["valid"]:
                    if not review.get("skipped"):
                        with MANIFEST_LOCK:
                            _anchor_new_identities(manifest, shot, target, anchors, visual_review.describe_identity)
                            _anchor_new_subjects(manifest, shot, target, present, subject_anchors,
                                                 visual_review.describe_subject)
                    break
                problems = (review.get("fatal_problems") or review.get("problems") or ["rejected"])
                log.info("Keyframe %s take %d rejected (%s): %s", shot.id, take + 1, review.get("score"),
                         "; ".join(problems)[:300])
                # A fallback take may miss softly (smooth skin, loose blocking) but never on anatomy:
                # shot-022 of the Hegdahl run kept a head turned backwards on its body as "best".
                if (not review.get("fatal_problems") and int(review.get("anatomy", 0)) >= threshold
                        and float(review.get("score") or 0) > best_score):
                    best_score = float(review.get("score") or 0)
                    target.replace(best)
                    hires["best"] = hires["take"]
                elif (identities and int(review.get("identity_match", 0)) >= threshold
                      and int(review.get("anatomy", 0)) >= threshold
                      and float(review.get("score") or 0) > likeness_score):
                    likeness_score = float(review.get("score") or 0)
                    target.replace(likeness)
                    hires["likeness"] = hires["take"]
                elif (keep_flawed and int(review.get("anatomy", 0)) >= threshold
                      and int(review.get("realism", 0)) >= threshold - 1
                      and not any(_weird(p, shot) for p in review.get("fatal_problems") or [])
                      and float(review.get("score") or 0) > flawed_score):
                    flawed_score = float(review.get("score") or 0)
                    target.replace(flawed)
                    hires["flawed"] = hires["take"]
                if take == 1 and not staged or take == 3:
                    # Two misses usually mean a layout FLUX cannot draw in a tall frame (three officials
                    # across a table from Hegdahl failed fifteen times): the shot doctor restages it,
                    # in depth, keeping every count and side, and later takes draw that staging.
                    staged = _restaged(drawn, outfits, "; ".join(problems))
                if staged or review.get("correction"):
                    prompt = (f"{keyframe_prompt(drawn, cards, outfits, subject_cards)} Composition: "
                              f"{staged or review['correction']}")
            else:
                target.unlink(missing_ok=True)
                if best.is_file():
                    # Only soft misses (a slightly smooth skin, a 6 on realism): still a far better first
                    # frame than text-only generation, whose dreamy look is what keyframes exist to fix.
                    best.replace(target)
                    hires["take"] = hires["best"]
                    log.info("Keyframe %s: no take passed outright; keeping the best take without fatal "
                             "problems (%.2f)", shot.id, best_score)
                elif likeness.is_file():
                    likeness.replace(target)
                    hires["take"] = hires["likeness"]
                    log.info("Keyframe %s: keeping the best take with the right face and sound anatomy "
                             "(%.2f); the clip retakes fix its blocking", shot.id, likeness_score)
                elif flawed.is_file():
                    flawed.replace(target)
                    hires["take"] = hires["flawed"]
                    log.warning("Keyframe %s: every take had a fatal problem; keeping the best one with sound "
                                "anatomy (%.2f): %s", shot.id, flawed_score, "; ".join(problems)[:200])
                    manifest.record("keyframe_kept_flawed", shot=shot.id, score=flawed_score, problems=problems)
                else:
                    log.warning("Keyframe for %s rejected in %d takes (%s); the shot will generate from text",
                                shot.id, take + 1, "; ".join(problems)[:300])
                    manifest.record("keyframe_failed", shot=shot.id, error="rejected by review: "
                                    + "; ".join(problems)[:450])
                    return "failed"
            if hires["take"] is not None and hires["take"].is_file():
                hires["take"].replace(target.with_name(f"{shot.id}.hires.png"))
        except (ComfyError, TimeoutError, requests.RequestException, subprocess.SubprocessError, OSError) as exc:
            target.unlink(missing_ok=True)
            log.warning("Keyframe for %s failed (%s); the shot will generate from text", shot.id, exc)
            manifest.record("keyframe_failed", shot=shot.id, error=str(exc)[:500])
            return "stop" if stop.is_set() else "failed"
        except Exception:
            # Any other crash mid-take leaves an unreviewed candidate at the keyframe's path, which the next
            # run took for a finished keyframe: the stray-dog hook opened on a rejected frame of the dog
            # running at the camera.
            target.unlink(missing_ok=True)
            raise
        finally:
            for leftover in (best, likeness, flawed, *target.parent.glob(f"{shot.id}.t*.png")):
                leftover.unlink(missing_ok=True)
            for event in mine.values():
                event.set()
        log.info("Keyframe %s ready in %.0fs (take %d)", shot.id, time.monotonic() - started, take + 1)
        manifest.record("keyframe_generated", shot=shot.id, path=str(target.relative_to(manifest.project_dir)))
        # Saved per keyframe: a run killed mid-batch lost every accepted frame's record and anchor, and the
        # next run could not tell a reviewed keyframe from the unreviewed candidate the kill left behind.
        manifest.save()
        if on_ready is not None:
            try:
                on_ready(index, target)
            except Exception as exc:          # a still or plan can be made later; the keyframe stands
                log.warning("After keyframe %s: %s", shot.id, exc)
        return "made"

    made = 0
    try:
        if parallel:
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="keyframe") as pool:
                outcomes = list(pool.map(draw, pending))
            made = outcomes.count("made")
        else:
            for index in pending:
                outcome = draw(index)
                if outcome == "stop":
                    break
                made += outcome == "made"
    finally:
        ComfyClient(config.minimax_url, timeout=timeout, poll_seconds=1.0).free_memory()
        manifest.save()
    return made
