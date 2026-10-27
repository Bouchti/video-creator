"""Fail-closed story-aware review for generated clips and the final edit."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from agents import ai_router
from config.paths import CLAUDE_MODEL, get_env_path

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
    return value not in {"0", "false", "no", "off"} and ai_router.available()


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
    prompt = (
        "Review this candidate as a pragmatic film editor judging whether it works in the finished story. "
        "It must render only this assigned beat:\n"
        f"Visual action: {shot.subject_action}\nNarration meaning: {shot.narration}\n"
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
        "a named character who should not be in this shot, or a named character whose garments, headwear, "
        "or colours clearly differ from the identity lock or their identity reference still, or opposing sides "
        "(enemies, rival armies) shown side by side moving the same way, mixed into one crowd, or on the "
        "wrong side of the frame for the screen geography in the lock, or a held item (shield, weapon, "
        "prop) present or missing against the identity lock, such as a dropped shield back in a hand. "
        "Do not mark small differences in camera angle, subject "
        "scale, body drift, visibility of minor props, or ambiguous reflections as fatal when the clip is "
        "otherwise coherent and tells the correct beat. A transparent mask or visor is still present when the "
        "face is visible behind its frame; colored light reflected in eyes or glass is not broken anatomy. "
        "Camera movement and the resulting background perspective change are intentional, not a scene reset. "
        "Large opaque bubble clumps attached to a face or body, fused equipment, and implausible effect geometry "
        "must reduce image-quality and immersion scores. "
        "The film must look like real camera footage. A painterly, illustrated, CGI or video-game look, dreamy "
        "haze or glow over the whole frame, waxy plastic skin, or objects that melt or morph between frames is "
        "fatal; milder softness, oversaturation or an artificial sheen must lower the image-quality score. "
        "Reserve fatal findings for concrete, visually unambiguous failures and describe the exact visible "
        "evidence. Judge narrative function and immersion, not pixel-perfect obedience. A supplied start image "
        "is the generator's first frame, so candidate frame 1 is EXPECTED to match it closely; never "
        "penalize that. Identity reference stills show only how characters must look, not where or how lit. Judge story progression on frames 2 and 3, which must visibly advance to the new "
        "action instead of holding the opening composition. Give "
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
            values = ai_router.ask(
                "You are a film editor reviewing generated video clips.", prompt, REVIEW_TOOL["input_schema"],
                model=os.getenv("VISION_MODEL") or CLAUDE_MODEL, images=images,
            )
        if not isinstance(values, dict):
            raise ValueError("vision reviewer returned no structured result")
        score_names = ("visual_match", "continuity", "image_quality", "anatomy", "immersion", "story_progression")
        scores = {name: int(values.get(name, 0)) for name in score_names}
        fatal = [str(item) for item in values.get("fatal_problems", []) if item]
        threshold = int(os.getenv("LOCAL_VIDEO_VISION_MIN_SCORE", "7"))
        strict_pass = all(score >= threshold for score in scores.values())
        average = sum(scores.values()) / len(scores)
        quality_floor_pass = os.getenv("LOCAL_VIDEO_ALLOW_QUALITY_FLOOR", "0") == "1" and quality_floor(
            scores, threshold)
        valid = not fatal and (strict_pass or quality_floor_pass)
        return {
            "valid": valid, "skipped": False, "threshold": threshold,
            "average_score": round(average, 2),
            "acceptance": "strict" if strict_pass else "quality-floor" if valid else "rejected",
            **scores,
            "fatal_problems": fatal,
            "problems": [str(item) for item in values.get("problems", []) if item],
            "revision_prompt": str(values.get("revision_prompt") or "").strip(),
        }
    except Exception as exc:
        log.warning("Visual clip review unavailable (%s); rejecting clip", exc.__class__.__name__)
        valid = os.getenv("LOCAL_VIDEO_ALLOW_QC_SKIP", "0") == "1"
        return {"valid": valid, "skipped": True, "reason": f"vision review unavailable: {exc.__class__.__name__}"}


def review_final_video(path: str | Path, manifest: Any) -> dict[str, Any]:
    """Review the assembled narrative as a whole; unavailable review fails closed."""
    if not review_enabled():
        valid = os.getenv("LOCAL_VIDEO_ALLOW_QC_SKIP", "0") == "1"
        return {"valid": valid, "skipped": True, "reason": "final vision QC unavailable"}
    frames = _sample_frames(path, ratios=(0.02, 0.12, 0.25, 0.38, 0.5, 0.62, 0.75, 0.88, 0.98))
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
    prompt = (
        "Review these chronological frames from the complete vertical social video. Judge the whole edit, "
        f"not isolated beauty frames. {review_rules}\n\n"
        f"Title: {manifest.script.get('video_title', manifest.concept)}\n"
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
            values = ai_router.ask(
                "You are a film editor reviewing a finished short video.", prompt,
                FINAL_REVIEW_TOOL["input_schema"], model=os.getenv("VISION_MODEL") or CLAUDE_MODEL,
                images=images,
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
