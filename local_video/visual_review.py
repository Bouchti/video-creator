"""Fail-closed story-aware review for generated clips and the final edit."""

from __future__ import annotations

import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from agents import llm
from config.paths import CLAUDE_MODEL, get_env_path
from local_video import looks

from .faces import face_crops

log = logging.getLogger("pipeline")
load_dotenv(get_env_path())

REVIEW_TOOL = {
    "name": "submit_clip_review",
    "description": "Score whether a generated video clip correctly and cleanly renders its assigned story beat.",
    "input_schema": {
        "type": "object",
        "properties": {
            "visual_match": {"type": "integer", "minimum": 1, "maximum": 10},
            "continuity": {"type": "integer", "minimum": 1, "maximum": 10},
            "image_quality": {"type": "integer", "minimum": 1, "maximum": 10},
            "anatomy": {"type": "integer", "minimum": 1, "maximum": 10},
            "immersion": {"type": "integer", "minimum": 1, "maximum": 10},
            "story_progression": {"type": "integer", "minimum": 1, "maximum": 10},
            "fatal_problems": {"type": "array", "items": {"type": "string"}},
            "problems": {"type": "array", "items": {"type": "string"}},
            "revision_prompt": {
                "type": "string",
                "description": (
                    "The prompt for the next take, fed STRAIGHT to the video generator. Write it as a "
                    "plain positive description of the shot that should exist: subject, framing, "
                    "camera move, light, and what changes from first frame to last. Never phrase a fix "
                    "as a prohibition: 'no daylight', 'not pink', 'avoid the mainland', 'do not add "
                    "trees'. The generator has no negative channel here, so a forbidden thing you name "
                    "becomes a thing you asked for, and the same defect comes back. State the "
                    "replacement instead: 'an overcast ash-grey sky', 'open sea to the horizon on both "
                    "sides', 'bare black rock to the frame edge'. If the defect was a drift away from "
                    "the intended look, describe that look as a constant held in every frame."
                ),
            },
        },
        "required": ["visual_match", "continuity", "image_quality", "anatomy", "immersion", "story_progression",
                     "fatal_problems", "problems", "revision_prompt"],
    },
}

KEYFRAME_REVIEW_TOOL = {
    "name": "submit_keyframe_review",
    "description": "Score whether a still image is a usable first frame for its assigned shot.",
    "input_schema": {
        "type": "object",
        "properties": {
            "composition_match": {"type": "integer", "minimum": 1, "maximum": 10},
            "realism": {"type": "integer", "minimum": 1, "maximum": 10},
            "anatomy": {"type": "integer", "minimum": 1, "maximum": 10},
            "identity_match": {
                "type": "integer", "minimum": 1, "maximum": 10,
                "description": "Same person as the identity reference: face, apparent age, hair, build "
                               "(10 when there is no reference; clothing does not count).",
            },
            "fatal_problems": {"type": "array", "items": {"type": "string"}},
            "problems": {"type": "array", "items": {"type": "string"}},
            "subject_heading": {
                "type": "string", "enum": ["left", "right", "toward", "away", "none"],
                "description": "Which way the main moving subject travels (or, if still, faces) in this picture: "
                               "toward the left or right edge, toward or away from the camera, or none.",
            },
            "mirror_fixes": {
                "type": "boolean",
                "description": "true only when flipping the image left-right would fix EVERY fatal problem "
                               "(the frame is right except that people face or sit on the mirrored side).",
            },
            "correction": {
                "type": "string",
                "description": (
                    "One or two sentences added to the image prompt for the next take: a plain positive "
                    "description of the composition that should exist (who stands or sits where, how many, "
                    "facing which way). Never a prohibition; name the replacement instead."
                ),
            },
        },
        "required": ["composition_match", "realism", "anatomy", "fatal_problems", "problems", "correction"],
    },
}

FINAL_REVIEW_TOOL = {
    "name": "submit_final_video_review",
    "description": "Approve or reject the complete assembled social video.",
    "input_schema": {
        "type": "object",
        "properties": {
            "story_coherence": {"type": "integer", "minimum": 1, "maximum": 10},
            "continuity": {"type": "integer", "minimum": 1, "maximum": 10},
            "visual_quality": {"type": "integer", "minimum": 1, "maximum": 10},
            "pacing": {"type": "integer", "minimum": 1, "maximum": 10},
            "caption_readability": {"type": "integer", "minimum": 1, "maximum": 10},
            "fatal_problems": {"type": "array", "items": {"type": "string"}},
            "problems": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["story_coherence", "continuity", "visual_quality", "pacing",
                     "caption_readability", "fatal_problems", "problems"],
    },
}


def review_enabled() -> bool:
    value = os.getenv("LOCAL_VIDEO_VISION_QC", "1").strip().lower()
    return value not in {"0", "false", "no", "off"} and llm.available()


def _sample_frames(path: str | Path, ratios=(0.05, 0.5, 0.95)) -> list[bytes]:
    try:
        import cv2
    except ImportError:
        return []
    capture = cv2.VideoCapture(str(path))
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    encoded: list[bytes] = []
    for ratio in ratios:
        capture.set(cv2.CAP_PROP_POS_FRAMES, max(0, round((count - 1) * ratio)))
        ok, frame = capture.read()
        if not ok or frame is None:
            continue
        height, width = frame.shape[:2]
        scale = min(1.0, 512 / max(height, width))
        if scale < 1:
            frame = cv2.resize(frame, (round(width * scale), round(height * scale)))
        success, data = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        if success:
            encoded.append(data.tobytes())
    capture.release()
    return encoded


def _encode_still(path: str | Path) -> bytes | None:
    try:
        import cv2
        frame = cv2.imread(str(path))
        if frame is None:
            return None
        height, width = frame.shape[:2]
        scale = min(1.0, 512 / max(height, width))
        if scale < 1:
            frame = cv2.resize(frame, (round(width * scale), round(height * scale)))
        success, data = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        return data.tobytes() if success else None
    except Exception:
        return None


def _identity_stills(shot: Any, manifest: Any, start_frame: Path | None) -> list[tuple[str, bytes]]:
    """Each on-screen character's latest accepted look, so a changed outfit is caught after a cut."""
    stills: list[tuple[str, bytes]] = []
    used = {start_frame.resolve()} if start_frame else set()
    for name in getattr(shot, "cast", None) or []:
        for prior in reversed(getattr(manifest, "shots", [])[:getattr(shot, "index", 0)]):
            if name not in (getattr(prior, "cast", None) or []) or prior.status != "accepted" or not prior.last_frame:
                continue
            frame = (Path(manifest.project_dir) / prior.last_frame).resolve()
            if frame in used or not frame.is_file():
                break
            data = _encode_still(frame)
            if data:
                used.add(frame)
                stills.append((f"Identity reference still for {name} (an earlier accepted shot)", data))
            break
    return stills


def quality_floor(scores: dict[str, int], threshold: int) -> bool:
    """Keep a take that misses on the soft dimensions while the hard ones are clean.

    story_progression gets the same one-point relief as visual_match and immersion: a three
    second clip of a slow subject can only ever show a moment of it, so a 6 there is routine even
    for a good take (17 of 20 takes on the 2026-10-27 volcano run, several otherwise scoring 8s).
    image_quality may also sit one point low, but only on an otherwise strong take: MiniMax renders
    ash plumes and smoke "slightly CGI-like" on every seed, so on that run five takes averaging up
    to 7.17 died on image_quality 6 alone and the retakes could never fix it. anatomy still needs
    the full threshold, a fatal problem still rejects outright, and LOCAL_VIDEO_MAX_DEGRADED_PERCENT
    still stops a run whose shots are mostly salvaged, so this cannot quietly become a slideshow.
    """
    average = sum(scores.values()) / len(scores)
    image_ok = scores["image_quality"] >= threshold or (
        scores["image_quality"] >= threshold - 1 and average >= threshold - 0.3)
    return (
        scores["visual_match"] >= max(1, threshold - 2)
        and scores["continuity"] >= max(1, threshold - 1)
        and image_ok
        and scores["anatomy"] >= threshold
        and scores["immersion"] >= max(1, threshold - 1)
        and scores["story_progression"] >= max(1, threshold - 1)
        and average >= threshold - 0.6
    )


def review_clip(path: str | Path, shot: Any, previous_frame: Path | None, manifest: Any) -> dict[str, Any]:
    """Return an acceptance report. Creative review is fail-closed by default."""
    if not review_enabled():
        valid = os.getenv("LOCAL_VIDEO_ALLOW_QC_SKIP", "0") == "1"
        return {"valid": valid, "skipped": True, "reason": "vision QC disabled or Claude Code unavailable"}
    frames = _sample_frames(path)
    if not frames:
        return {"valid": False, "skipped": True, "reason": "could not sample video frames"}
    stills: list[tuple[str, bytes]] = []
    if previous_frame and previous_frame.is_file():
        prior = _encode_still(previous_frame)
        if prior:
            stills.append((
                "Intended first-frame composition and identity reference"
                if getattr(shot, "index", 0) == 0 else
                "Start image: the final frame of an earlier shot in this place and light",
                prior,
            ))
    stills.extend(_identity_stills(shot, manifest, previous_frame))
    for index, frame in enumerate(frames, 1):
        stills.append((f"Candidate clip frame {index} of {len(frames)}", frame))
    light = getattr(shot, "light", "")
    cast = getattr(shot, "cast", None)
    end = re.search(r"By the end of the clip: (.+?)(?:\.\s|\.$|\n)", str(getattr(shot, "prompt", "") or ""))
    # The take was rendered from the shot doctor's plan, which keeps the beat's meaning but stages it the way
    # this first frame and model can (a row of listeners where the beat said a semicircle). Judging staging
    # against the script's words rejected every take that followed the plan (Hegdahl shot-010).
    planned = ((getattr(manifest, "settings", None) or {}).get("shot_doctor_take") or {}).get(getattr(shot, "id", ""))
    action = (f"Visual action as planned for this take (judge staging, layout and camera against this): {planned}\n"
              f"Beat as written in the script (judge story meaning, people and facts against this; its staging "
              f"details may differ from the plan): {shot.subject_action}\n") if planned else \
        f"Visual action: {shot.subject_action}\n"
    cutaway = looks.is_cutaway(shot)
    prompt = (
        (looks.CUTAWAY_REVIEW_NOTE if cutaway else "")
        + "Review this candidate as a pragmatic film editor judging whether it works in the finished story. "
        "It must render only this assigned beat:\n"
        f"{action}Narration meaning: {shot.narration}\n"
        + (f"Intended end state: {end.group(1)}\n" if end else "")
        + (f"Light and sky in this shot: {light}\n" if light else "")
        + (f"Named characters on screen: {', '.join(cast) if cast else 'none (anonymous figures only)'}\n"
           if cast is not None and getattr(shot, "scene", "") else "")
        + f"World and identity lock: {shot.continuity}\n"
        "Fatal problems are limited to: a clearly unrelated scene or story reset, montage across multiple "
        "locations, duplicate protagonist (including background extras dressed as a named character: same "
        "hair, cloak, colours or signature item), seriously broken anatomy, corrupt/smeared frames, visible text or "
        "logos, a major identity/continuity break, a dream-like morph or dissolve from one place or time into "
        "another inside the clip, light or sky that contradicts this shot's stated light (an eclipse, night, "
        "storm, or fire that belongs to another moment of the story, or its absence when this shot needs it), "
        "a named character who should not be in this shot, a garment, hat, cap or held object that appears, "
        "vanishes or changes on anyone between frame 1 and frame 3 (a cap materializing on a bare head "
        "mid-clip), or a named character whose garments, headwear, "
        "or colours clearly differ from the identity lock or their identity reference still, or opposing sides "
        "(enemies, rival armies) shown side by side moving the same way, mixed into one crowd, or on the "
        "wrong side of the frame for the screen geography in the lock, or a held item (shield, weapon, "
        "prop) present or missing against the identity lock, such as a dropped shield back in a hand, "
        "or a flag, banner, insignia or uniform colour that differs from the one the identity lock gives "
        "that side or vehicle, or that changes into another side's during the clip (one fleet flying the "
        "enemy's flag reads as the wrong side), or a number the visual action states (exactly one, a "
        "single, two, three) visibly contradicted: two ships where it says one, a second muzzle flash or "
        "smoke burst where it says a single shot, or an event the action shows only as aftermath "
        "(drifting smoke, a spilled pot) happening again in frame, or an impact the action or narration "
        "calls a crash, strike or hit that never visibly lands because the clip opens after it. "
        "Do not mark small differences in camera angle, subject "
        "scale, body drift, visibility of minor props, or ambiguous reflections as fatal when the clip is "
        "otherwise coherent and tells the correct beat. A transparent mask or visor is still present when the "
        "face is visible behind its frame; colored light reflected in eyes or glass is not broken anatomy. "
        "Camera movement and the resulting background perspective change are intentional, not a scene reset. "
        "Large opaque bubble clumps attached to a face or body, fused equipment, and implausible effect geometry "
        "must reduce image-quality and immersion scores. "
        + (looks.CUTAWAY_CLIP_LOOK if cutaway else
           "The film must look like real camera footage. A painterly, illustrated, CGI or video-game look, dreamy "
           "haze or glow over the whole frame, waxy plastic skin, or objects that melt or morph between frames is "
           "fatal; milder softness, oversaturation or an artificial sheen must lower the image-quality score. ")
        + "The picture must fill the whole vertical frame edge to edge: black letterbox or pillarbox bars, a "
        "wide picture boxed inside the frame, a split screen, stacked panels or an inset picture is fatal "
        "(a letterboxed ship plays as a small strip on a phone). A flag not fastened along one short edge to "
        "its own pole (floating in front of it, the pole through the cloth's middle) is fatal, and so is a flag "
        "or pole floating in the air instead of planted in the ground, on a building or held by a person. "
        "Judge a flag by "
        "the pattern a viewer recognizes (colours, stripe order, where a cross or canton sits), never by "
        "counting the stripes of a waving or distant flag. "
        "Reserve fatal findings for concrete, visually unambiguous failures and describe the exact visible "
        "evidence. Judge narrative function and immersion, not pixel-perfect obedience. A supplied start image "
        "IS frame 0 of this clip: any garment, hat, cap or held object on a person in the candidate frames "
        "that the start image does not show appeared during the clip, which is fatal, even when it then "
        "stays on (candidate frame 1 is sampled a few frames in, after such a change). Candidate frame 1 is "
        "otherwise EXPECTED to match it closely; never "
        "penalize that. Identity reference stills show only how characters must look, not where or how lit. Judge story progression on frames 2 and 3, which must visibly advance to the new "
        "action instead of holding the opening composition. "
        + ((FAST_CLIP_RULE_CUTAWAY if cutaway else FAST_CLIP_RULE) if _fast_mode() else "")
        + ("THIS IS THE HOOK, the first shot a scrolling viewer sees: it must grab within two seconds, with "
           "strong visible action from frame 1. A calm or near-static frame fails story_progression and "
           "immersion however clean it is. "
           if getattr(shot, "index", 1) == 0 else
           "When the intended end state keeps the opening arrangement (someone remains seated, a door stays "
           "shut, a held moment), the beat IS that moment: score story_progression on whether it plays as a "
           "living moment (glances, breathing, small gestures, the camera move), not on a new action it never "
           "asked for. ")
        + "Give "
        "concise, positively worded, filmable corrections that prioritize the current beat's end-frame payoff. "
        "Submit the review as the structured output."
    )
    try:
        with tempfile.TemporaryDirectory() as tmp:
            images = []
            for index, (label, data) in enumerate(stills):
                still = Path(tmp) / f"{index}.jpg"
                still.write_bytes(data)
                images.append((label, still))
            values = llm.ask(
                "You are a film editor reviewing generated video clips.", prompt, REVIEW_TOOL["input_schema"],
                images=images,
            )
        if not isinstance(values, dict):
            raise ValueError("vision reviewer returned no structured result")
        score_names = ("visual_match", "continuity", "image_quality", "anatomy", "immersion", "story_progression")
        scores = {name: int(values.get(name, 0)) for name in score_names}
        fatal = [str(item) for item in values.get("fatal_problems", []) if item]
        threshold = int(os.getenv("LOCAL_VIDEO_VISION_MIN_SCORE", "7"))
        strict_pass = all(score >= threshold for score in scores.values())
        average = sum(scores.values()) / len(scores)
        # The hook gets no soft-score relief: it is the shot that decides whether anyone keeps watching.
        quality_floor_pass = (os.getenv("LOCAL_VIDEO_ALLOW_QUALITY_FLOOR", "0") == "1"
                              and getattr(shot, "index", 1) != 0 and quality_floor(scores, threshold))
        valid = not fatal and (strict_pass or quality_floor_pass)
        clean_pass = False
        if not valid and not fatal and _fast_mode() and os.getenv("LOCAL_VIDEO_PLANNED_STILLS", "0") == "1":
            # Better than the still it would be replaced with: natural, clean motion that tells the beat.
            clean_pass = (average >= threshold - 1 and scores["anatomy"] >= threshold
                          and scores["image_quality"] >= threshold - 1 and scores["continuity"] >= threshold - 1)
            valid = clean_pass
        return {
            "valid": valid, "skipped": False, "threshold": threshold,
            "average_score": round(average, 2),
            "acceptance": ("strict" if strict_pass else "clean-motion" if clean_pass
                           else "quality-floor" if valid else "rejected"),
            **scores,
            "fatal_problems": fatal,
            "problems": [str(item) for item in values.get("problems", []) if item],
            "revision_prompt": str(values.get("revision_prompt") or "").strip(),
        }
    except Exception as exc:
        log.warning("Visual clip review unavailable (%s); rejecting clip", exc.__class__.__name__)
        valid = os.getenv("LOCAL_VIDEO_ALLOW_QC_SKIP", "0") == "1"
        return {"valid": valid, "skipped": True, "reason": f"vision review unavailable: {exc.__class__.__name__}"}


IDENTITY_CARD_TOOL = {
    "name": "submit_identity_card",
    "input_schema": {
        "type": "object",
        "properties": {"appearance": {"type": "string"}},
        "required": ["appearance"],
    },
}


def describe_identity(path: str | Path, name: str, lock: str) -> str:
    """One concrete sentence of how this person looks, so later FLUX frames draw the same person.

    FLUX takes no reference image, and the script's look ("young adult U.S. Navy sailor") let it draw a
    different face, age and hair in every keyframe of the 2026-10-29 Hegdahl run.
    """
    still = _encode_still(path)
    if not still or not review_enabled():
        return ""
    prompt = (
        f"This image is the identity reference for {name}. Their story lock says: {lock[:500]}\n"
        "Describe the fixed physical appearance of this one person so an image generator can draw the "
        "same person again, starting with the apparent age in years: then hair colour, length and cut, "
        "facial hair, face shape and notable features, build, skin tone. Leave clothing out (it changes "
        "with the story). One sentence of concrete nouns and adjectives, no pose, camera, lighting or "
        "setting words. Submit the structured output."
    )
    try:
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "identity.jpg"
            image.write_bytes(still)
            values = llm.ask("You write character identity cards for a film.", prompt,
                                   IDENTITY_CARD_TOOL["input_schema"],
                                   model=os.getenv("VISION_MODEL") or CLAUDE_MODEL, images=[(name, image)])
        return str((values or {}).get("appearance") or "").strip() if isinstance(values, dict) else ""
    except Exception as exc:
        log.warning("Identity card for %s unavailable (%s)", name, exc.__class__.__name__)
        return ""


def describe_subject(path: str | Path, label: str, lock: str) -> str:
    """One concrete sentence of how a recurring non-human subject looks, so later frames draw the same one.

    The stray-dog video's dog was golden in one shot, fox-like in the next and a shepherd at the end, and
    its border stone changed shape: the script's description left FLUX too much to choose.
    """
    still = _encode_still(path)
    if not still or not review_enabled():
        return ""
    prompt = (
        f"This image is the reference for the recurring subject '{label}'. The story describes it as: "
        f"{lock[:400]}\nDescribe the fixed look of this one subject as it appears here, so an image generator "
        "draws the same one again: for an animal its breed type, size, coat length and texture, exact colours "
        "and markings, ears, tail; for an object its shape, proportions, height, material, colour, wear and "
        "any marks. Describe ONLY the subject itself: never its container, surroundings or any other object "
        "(the card goes into every later image prompt, and a molasses card that named its tank put a giant "
        "tank into every street). One sentence of concrete nouns and adjectives, no pose, camera, lighting "
        "or setting words. Submit the structured output."
    )
    try:
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "subject.jpg"
            image.write_bytes(still)
            values = llm.ask("You write continuity cards for a film's recurring subjects.", prompt,
                                   IDENTITY_CARD_TOOL["input_schema"],
                                   model=os.getenv("VISION_MODEL") or CLAUDE_MODEL, images=[(label, image)])
        return str((values or {}).get("appearance") or "").strip() if isinstance(values, dict) else ""
    except Exception as exc:
        log.warning("Subject card for %s unavailable (%s)", label, exc.__class__.__name__)
        return ""


def describe_outfit(path: str | Path, name: str, lock: str) -> str:
    """Exactly what this character wears in an accepted frame, so the next shots dress them the same.

    The clip reviewer compares each shot with the character's latest accepted one, but nothing fixed the
    clothes: the Hegdahl run drew a sage sailor uniform, a gray top and a green jumpsuit with an orange
    patch for the same captivity, and rejected the take that changed it.
    """
    still = _encode_still(path)
    if not still or not review_enabled():
        return ""
    prompt = (
        f"This frame shows {name}. Their story lock says: {lock[:400]}\n"
        "Describe ONLY what this one person wears, so an image and video generator can dress them exactly "
        "the same in the next shot: each garment, its colour, collar, sleeves, buttons, trim, and any "
        "headwear or its absence (\"bare head\"). One sentence, concrete, no body, pose or setting words. "
        "Submit the structured output."
    )
    try:
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "outfit.jpg"
            image.write_bytes(still)
            values = llm.ask("You keep wardrobe continuity for a film.", prompt,
                                   {"type": "object", "properties": {"outfit": {"type": "string"}},
                                    "required": ["outfit"]},
                                   model=os.getenv("VISION_MODEL") or CLAUDE_MODEL, images=[(name, image)])
        return str((values or {}).get("outfit") or "").strip() if isinstance(values, dict) else ""
    except Exception as exc:
        log.warning("Outfit card for %s unavailable (%s)", name, exc.__class__.__name__)
        return ""


# Fast mode cuts between every shot and often plays the keyframe itself as the shot. Of the Zanzibar run's
# keyframe rejections (2026-10-31) most were details nobody sees in three seconds on a phone (Roman numerals
# on a watch dial, one funnel instead of two, a warship's bow pointing left), each costing a 15 s take.
FAST_KEYFRAME_RULE = (
    "THIS VIDEO CUTS BETWEEN EVERY SHOT. Judge the frame as a viewer sees it on a phone for three seconds. "
    "Screen direction (which side of the frame something is on, which way it faces or heads) is never fatal "
    "here, whatever the lock says. Fine details of the lock or action that a viewer would not notice at that "
    "size and speed (the exact number of funnels, masts or small props, markings on a dial, a small emblem on "
    "a flag's cloth, a seal count, the exact pose of a hand) are problems, not fatal. Fatal stays reserved for "
    "what a viewer WOULD notice: readable letters or numbers, objects from the wrong era or place (cars, "
    "modern clothes, plastic, painted road lane markings, asphalt highways, power lines; mountains where the "
    "story is on a plain), a surreal set (walls of draped cloth, an impossible corridor) or a hybrid object (a "
    "truck with aircraft wings), broken anatomy (a hand or glove with no arm and person attached to it, "
    "floating or lying on an object), a surreal, illustrated or CGI look, a frame that does not show the "
    "subject or place the narration is about, an empty or blank frame, a named character who is the wrong "
    "person. "
)


# Fast mode's alternative to a rejected clip is its approved keyframe as a parallax still, so a clip only has to
# beat that, cleanly. The Zanzibar run (2026-10-31) rejected all 9 first takes, half of them for motion that
# merely differed from the plan: a flag rippling gently instead of snapping open (scored 7.33), a muzzle flash
# a little low, a ship drifting closer, a blast already underway in frame 1.
FAST_CLIP_RULE = (
    "THIS VIDEO CUTS BETWEEN EVERY SHOT. Judge it as a viewer sees it on a phone for three seconds. Fatal is only "
    "what that viewer would notice as wrong or weird: things melting or morphing, the place turning into "
    "another place, a person or a sizeable object appearing from nowhere or vanishing, broken anatomy (a "
    "hand or glove with no arm and person attached), "
    "readable letters or numbers, a CGI or illustrated look, a soft, blurry or veiled picture where frame 1 is "
    "sharp (the windmill run passed a well shot gone soft behind dust), black bars, a frozen or corrupt picture, objects "
    "from the wrong era or place (painted road lane markings, asphalt highways, power lines, plastic, modern "
    "vehicles; mountains or a fjord where the story is on a plain or a river). Motion that breaks physics is "
    "fatal: a vehicle, animal or person moving backwards against the way it faces (a truck rolling rear-first, "
    "someone walking backwards), vehicles in one lane driving both ways, wheels or legs that slide without "
    "turning or stepping, an object moving with nothing driving it (Ghost Army convoy: trucks drove backwards "
    "between trucks driving forwards, and the clip passed). Surreal sets are fatal too: walls of cloth, "
    "impossible corridors, a vehicle fused with another (a truck with aircraft wings). Motion that differs from the planned action but looks natural (a flag rippling "
    "gently instead of snapping open, a flash or splash in a slightly different place, a ship drifting closer, "
    "the action already underway in frame 1, a different camera move) is NOT fatal: lower visual_match or "
    "story_progression instead. Screen direction (which side, which way something faces) is never fatal here. "
)


def _for_cutaway(rule: str, photo_look: str) -> str:
    """A fast-mode rule for a cutaway film: a render is its look, so a cartoon look is the one to reject."""
    if photo_look not in rule:
        raise ValueError(f"fast-mode rule no longer names {photo_look!r}; update its cutaway version")
    return rule.replace(photo_look, "a cartoon, flat or toy-like look")


FAST_CLIP_RULE_CUTAWAY = _for_cutaway(FAST_CLIP_RULE, "a CGI or illustrated look")
FAST_KEYFRAME_RULE_CUTAWAY = _for_cutaway(FAST_KEYFRAME_RULE, "a surreal, illustrated or CGI look")


def _fast_mode() -> bool:
    return os.getenv("LOCAL_VIDEO_FAST", "1").strip() != "0"


def review_keyframe(path: str | Path, shot: Any, identities: list[tuple[str, Path]] | None = None,
                    outfits: dict[str, str] | None = None,
                    subjects: list[tuple[str, Path]] | None = None) -> dict[str, Any]:
    """Check a FLUX first frame against its shot before an expensive clip is built on it.

    A keyframe is the clip's first frame and the reference its review compares against, so a still
    that breaks the stated blocking dooms every take: shot-001 of the 2026-10-29 Hegdahl run asked for
    Hegdahl at frame left facing three officials at frame right, FLUX centred him between two, and the
    11-minute MiniMax take failed review on exactly that. A still costs ~30 s to redo.

    Fails open (valid, skipped): keyframes only improve the look, and the clip review stays fail-closed.
    """
    if not review_enabled():
        return {"valid": True, "skipped": True, "reason": "vision QC disabled or unavailable"}
    still = _encode_still(path)
    if not still:
        return {"valid": False, "skipped": False, "score": 0, "fatal_problems": ["unreadable image"],
                "problems": [], "correction": ""}
    light = getattr(shot, "light", "")
    cast = getattr(shot, "cast", None)
    period = str((getattr(shot, "continuity", None) or {}).get("period") or "")
    cutaway = looks.is_cutaway(shot)
    prompt = (
        (looks.CUTAWAY_REVIEW_NOTE if cutaway else "")
        + "This still will be the FIRST FRAME of a short video shot; the video model animates from it and "
        "cannot rearrange the people in it. Judge whether it sets up this shot:\n"
        f"Visual action: {shot.subject_action}\n"
        + (f"Narration at this moment: {shot.narration}\n" if getattr(shot, "narration", "") else "")
        + (f"Story period: {period}\n" if period else "")
        + "".join(f"Wardrobe lock for {name} (as in their latest accepted shot; a different outfit is fatal): "
                  f"{outfit}\n" for name, outfit in (outfits or {}).items() if outfit)
        + (f"Light and sky: {light}\n" if light else "")
        + (f"Named characters on screen: {', '.join(cast) if cast else 'none (anonymous figures only)'}\n"
           if cast is not None else "")
        + f"World and identity lock: {shot.continuity}\n"
        "The setting must read, to a viewer hearing the narration, as that place and era: a clean, new or "
        "modern-looking room (fresh paint, polished floor, domestic fittings) standing in for a prison, ship "
        "or other period place is the wrong setting, even when the action calls it bare or plain. "
        "Fatal problems are limited to: a number of people or objects the action states (one, two, three) "
        "visibly contradicted; a person or group on the wrong side of the frame when the action places them "
        "(frame left, frame right, foreground, background); a named character facing the opposite way from "
        "the screen geography in the lock (looking left where the lock has him facing right), which the clip "
        "review rejects; a subject facing or heading the wrong way when "
        "the action states a direction (a ship steaming right shown bow-on or heading left, someone walking "
        "left-to-right shown walking at the camera): the clip cannot turn it around, and its review rejects "
        "exactly that; a facial expression or manner the action states (vacant, foolish, terrified, "
        "laughing, exhausted) contradicted by the face (a stern alert stare for 'deliberately vacant'): the "
        "video keeps the first frame's expression; a stated posture contradicted (standing where it "
        "says seated); the wrong setting or light; anonymous extras who look or dress like the named "
        "character (the same uniform, hair and youth: the clip reads them as clones); a named character "
        "missing, duplicated, or dressed against "
        "the identity lock; visible text, logos or watermarks; "
        + ("a cartoon, flat, sketched or toy-like look; " if cutaway else "an illustrated, painterly or CGI look; ")
        + "black letterbox or pillarbox bars, a split screen, stacked panels or an inset picture instead of "
        "one image filling the vertical frame; a flag not fastened along one short edge to its own pole "
        "(floating in front of or beside the pole, the pole running through the cloth's middle), or a flag or "
        "pole floating in the air instead of planted in the ground, on a building or held by a person; a flag "
        "standing alone in empty land with nothing of its side near it; a flag whose "
        "colours, stripe order or layout differ from the lock (white-red-green where it says white, green, "
        "red is another country's flag), judged by the pattern a viewer recognizes, never by counting the "
        "stripes of a waving or distant flag; "
        "broken anatomy of ANY person, background figures included: a head turned further than a neck "
        "allows or facing the opposite way from its body, a detached, floating or wrongly sized head, fused "
        "people, extra or missing limbs or fingers on a visible hand, a melted face. "
        + ("Judge identity on the face crops, which show the faces at full size: find the named character "
           "among the candidate's crops and compare that face with the reference face. "
           "Score identity_match strictly against the identity reference image: the same face, the same "
           "apparent age (more than about five years older or younger scores 4 or less), the same hair "
           "colour and cut, the same build. Clothing may change with the story; judge it against the "
           "identity lock, not the reference. A change the visual action states (longer hair, a beard, "
           "weight loss) is required, not a mismatch. A clearly different person is fatal. "
           if identities else "Score identity_match 10: there is no identity reference. ")
        + ("Recurring subject references are attached: the same subject in this frame must match its reference "
           "(an animal's breed type, coat and colours; an object's shape and proportions). A clearly different "
           "one (another breed or coat, a stone of another shape) is fatal; pose, angle and light may differ. "
           if subjects else "")
        + ((FAST_KEYFRAME_RULE_CUTAWAY if cutaway else FAST_KEYFRAME_RULE) if _fast_mode() else "")
        + "The action's ending state is NOT required: this is the opening frame, so "
        "judge only what must already be true when the shot starts. Small differences in camera height, "
        "prop detail or background are not fatal. Score composition_match on how faithfully the opening "
        "blocking matches, realism on whether it reads as "
        + ("a crisp photoreal 3D cutaway render with believable materials" if cutaway else "a real photograph")
        + ". Submit the structured output."
    )
    try:
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "keyframe.jpg"
            image.write_bytes(still)
            images = [("Candidate first frame", image)]
            for number, (label, reference) in enumerate(subjects or []):
                data = _encode_still(reference)
                if data:
                    ref = Path(tmp) / f"subject-{number}.jpg"
                    ref.write_bytes(data)
                    images.append((f"Reference for the recurring subject '{label}' (how it must look, not where)",
                                   ref))
            for number, (name, reference) in enumerate(identities or []):
                data = _encode_still(reference)
                if data:
                    ref = Path(tmp) / f"identity-{number}.jpg"
                    ref.write_bytes(data)
                    images.append((f"Identity reference for {name} (how they must look, not where)", ref))
                # Faces at a size the reviewer can compare: downscaled to 512 px, a medium shot's face
                # is ~40 px, and a different, older man passed as the anchor on the Hegdahl run.
                for crop_number, crop in enumerate(face_crops(reference, limit=1)):
                    face = Path(tmp) / f"identity-{number}-face-{crop_number}.jpg"
                    face.write_bytes(crop)
                    images.append((f"Face of {name} in the identity reference", face))
            if identities:
                for crop_number, crop in enumerate(face_crops(path)):
                    face = Path(tmp) / f"candidate-face-{crop_number}.jpg"
                    face.write_bytes(crop)
                    images.append((f"Face crop {crop_number + 1} from the candidate frame (largest first)", face))
            values = llm.ask(
                "You are a film editor checking first frames before shots are generated.", prompt,
                KEYFRAME_REVIEW_TOOL["input_schema"], model=os.getenv("VISION_MODEL") or CLAUDE_MODEL,
                images=images,
            )
        if not isinstance(values, dict):
            raise ValueError("vision reviewer returned no structured result")
        scores = {name: int(values.get(name, 0)) for name in ("composition_match", "realism", "anatomy")}
        identity = int(values.get("identity_match", 10)) if identities else 10
        fatal = [str(item) for item in values.get("fatal_problems", []) if item]
        threshold = int(os.getenv("LOCAL_VIDEO_VISION_MIN_SCORE", "7"))
        # The 2026-10-29 run passed a man of ~40 against a 21-year-old anchor while identity was only one
        # clause in the fatal list; a scored dimension with its own floor is what the reviewer honours.
        if identities and identity < threshold:
            fatal.append(f"not the same person as the identity reference (identity_match {identity})")
        return {
            "identity_match": identity,
            "valid": not fatal and all(score >= threshold for score in scores.values()),
            "skipped": False, "score": round(sum(scores.values()) / len(scores), 2), **scores,
            "fatal_problems": fatal,
            "problems": [str(item) for item in values.get("problems", []) if item],
            "correction": str(values.get("correction") or "").strip(),
            "mirror_fixes": bool(values.get("mirror_fixes")) and bool(fatal),
            "subject_heading": str(values.get("subject_heading") or "none"),
        }
    except Exception as exc:
        log.warning("Keyframe review unavailable (%s); keeping the keyframe", exc.__class__.__name__)
        return {"valid": True, "skipped": True, "reason": f"vision review unavailable: {exc.__class__.__name__}"}


def _shot_middles(manifest: Any, count: int = 9) -> tuple[float, ...]:
    """Where to sample the finished video: the middles of evenly spread shots, never a cut.

    Fixed percentages landed mid-crossfade, and the reviewer rejected the stray-dog video for a "ghosted
    double exposure" that was the dissolve from the two-flags shot into the guardhouse shot.
    """
    lengths = [max(1, int(getattr(shot, "duration_frames", 0) or 0)) for shot in getattr(manifest, "shots", [])]
    total = sum(lengths)
    if len(lengths) < count or not total:
        return ()
    picks = sorted({round(k * (len(lengths) - 1) / (count - 1)) for k in range(count)})
    starts = [sum(lengths[:index]) for index in range(len(lengths))]
    return tuple((starts[index] + lengths[index] / 2) / total for index in picks)


def review_final_video(path: str | Path, manifest: Any) -> dict[str, Any]:
    """Review the assembled narrative as a whole; unavailable review fails closed."""
    if not review_enabled():
        valid = os.getenv("LOCAL_VIDEO_ALLOW_QC_SKIP", "0") == "1"
        return {"valid": valid, "skipped": True, "reason": "final vision QC unavailable"}
    frames = _sample_frames(path, ratios=_shot_middles(manifest) or (0.02, 0.12, 0.25, 0.38, 0.5, 0.62, 0.75,
                                                                        0.88, 0.98))
    if len(frames) < 6:
        return {"valid": False, "skipped": True, "reason": "could not sample enough final-video frames"}
    unreal = getattr(manifest, "preferred_backend", "") == "unreal"
    review_rules = (
        "This is a schematic Unreal Engine engineering diorama built from simple geometric components. "
        "Do not expect people, photorealism, exact landmarks, or literal on-screen numbers. Judge whether the "
        "stages consistently depict one mechanism, progress from input through process to output, remain clean "
        "and readable, and end on the complete working system. Captions must be readable. Reject corrupt frames, "
        "unrelated stage families, broken continuity, or an ending with no mechanical payoff."
        if unreal else
        "The story must have a clear hook, causal progression and visible payoff; the same characters, wardrobe, "
        "props and geography must persist; captions must be readable and stay away from interface edges. Reject "
        "repeated shots, random objects, obvious identity changes, illegible captions, montage-like non sequiturs, "
        "or an ending that does not pay off the opening. It must read as real camera footage: reject a "
        "painterly, dreamy, glowing or CGI look and shapes that melt or morph."
    )
    if looks.is_cutaway(manifest):
        review_rules = looks.CUTAWAY_FINAL_RULES
    narration = str(manifest.script.get("spoken_script") or "").strip()
    prompt = (
        "Review these chronological frames from the complete vertical social video. Judge the whole edit, "
        f"not isolated beauty frames. {review_rules}\n"
        f"The frames are {len(frames)} evenly spaced samples of a video of about {len(manifest.shots)} shots: "
        "neighbouring frames are usually several shots apart, so judge continuity between shots that "
        "show the same people or place, not the jumps between samples. The narration below is spoken over "
        "the frames and the captions show it a few words at a time: judge the story with it.\n\n"
        + (f"Narration: {narration[:1600]}\n" if narration else "")
        + f"Title: {manifest.script.get('video_title', manifest.concept)}\n"
        f"Premise: {manifest.script.get('story_premise', manifest.concept)}\n"
        f"Goal: {manifest.script.get('protagonist_goal', '')}\n"
        f"Expected payoff: {manifest.script.get('ending_payoff', '')}\n"
        "Submit the review as the structured output."
    )
    try:
        with tempfile.TemporaryDirectory() as tmp:
            images = []
            for index, frame in enumerate(frames, 1):
                still = Path(tmp) / f"final_{index:02d}.jpg"
                still.write_bytes(frame)
                images.append((f"Chronological final-video frame {index} of {len(frames)}", still))
            values = llm.ask(
                "You are a film editor reviewing a finished short video.", prompt,
                FINAL_REVIEW_TOOL["input_schema"], images=images,
            )
        if not isinstance(values, dict):
            raise ValueError("final reviewer returned no structured result")
        names = ("story_coherence", "continuity", "visual_quality", "pacing", "caption_readability")
        scores = {name: int(values.get(name, 0)) for name in names}
        threshold = int(os.getenv("LOCAL_VIDEO_FINAL_MIN_SCORE", "7"))
        fatal = [str(item) for item in values.get("fatal_problems", []) if item]
        valid = not fatal and all(score >= threshold for score in scores.values())
        return {
            "valid": valid, "skipped": False, "threshold": threshold, **scores,
            "average_score": round(sum(scores.values()) / len(scores), 2),
            "fatal_problems": fatal,
            "problems": [str(item) for item in values.get("problems", []) if item],
        }
    except Exception as exc:
        valid = os.getenv("LOCAL_VIDEO_ALLOW_QC_SKIP", "0") == "1"
        return {"valid": valid, "skipped": True, "reason": f"final vision review unavailable: {exc.__class__.__name__}"}
