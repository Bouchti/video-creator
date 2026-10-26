"""Fail-closed story-aware review for generated clips and the final edit."""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

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
            "revision_prompt": {"type": "string"},
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
    return value not in {"0", "false", "no", "off"} and bool(os.getenv("ANTHROPIC_API_KEY"))


def _sample_frames(path: str | Path, ratios=(0.05, 0.5, 0.95)) -> list[str]:
    try:
        import cv2
    except ImportError:
        return []
    capture = cv2.VideoCapture(str(path))
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    encoded: list[str] = []
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
            encoded.append(base64.b64encode(data.tobytes()).decode("ascii"))
    capture.release()
    return encoded


def _encode_still(path: str | Path) -> str | None:
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
        return base64.b64encode(data.tobytes()).decode("ascii") if success else None
    except Exception:
        return None


def review_clip(path: str | Path, shot: Any, previous_frame: Path | None, manifest: Any) -> dict[str, Any]:
    """Return an acceptance report. Creative review is fail-closed by default."""
    if not review_enabled():
        valid = os.getenv("LOCAL_VIDEO_ALLOW_QC_SKIP", "0") == "1"
        return {"valid": valid, "skipped": True, "reason": "vision QC disabled or API key unavailable"}
    frames = _sample_frames(path)
    if not frames:
        return {"valid": False, "skipped": True, "reason": "could not sample video frames"}
    content: list[dict[str, Any]] = []
    if previous_frame and previous_frame.is_file():
        prior = _encode_still(previous_frame)
        if prior:
            content.extend([
                {"type": "text", "text": (
                    "Intended first-frame composition and identity reference:"
                    if getattr(shot, "index", 0) == 0 else
                    "Previous shot's final continuity frame:"
                )},
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": prior}},
            ])
    for index, frame in enumerate(frames, 1):
        content.extend([
            {"type": "text", "text": f"Candidate clip frame {index} of {len(frames)}:"},
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": frame}},
        ])
    content.append({"type": "text", "text": (
        "Review this candidate as a pragmatic film editor judging whether it works in the finished story. "
        "It must render only this assigned beat:\n"
        f"Visual action: {shot.subject_action}\nNarration meaning: {shot.narration}\n"
        f"World and identity lock: {shot.continuity}\n"
        "Fatal problems are limited to: a clearly unrelated scene or story reset, montage across multiple "
        "locations, duplicate protagonist, seriously broken anatomy, corrupt/smeared frames, visible text or "
        "logos, or a major identity/continuity break. Do not mark small differences in camera angle, subject "
        "scale, body drift, visibility of minor props, or ambiguous reflections as fatal when the clip is "
        "otherwise coherent and tells the correct beat. A transparent mask or visor is still present when the "
        "face is visible behind its frame; colored light reflected in eyes or glass is not broken anatomy. "
        "Camera movement and the resulting background perspective change are intentional, not a scene reset. "
        "Large opaque bubble clumps attached to a face or body, fused equipment, and implausible effect geometry "
        "must reduce image-quality and immersion scores. "
        "Reserve fatal findings for concrete, visually unambiguous failures and describe the exact visible "
        "evidence. Judge narrative function and immersion, not pixel-perfect obedience. The candidate must "
        "visibly advance beyond the supplied continuity frame instead of replaying its composition. A supplied "
        "reference is an identity and opening-state guide, not a frame that must be copied throughout. Give "
        "concise, positively worded, filmable corrections that prioritize the current beat's end-frame payoff."
    )})
    try:
        import anthropic
        response = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY")).messages.create(
            model=os.getenv("VISION_MODEL") or os.getenv("CLAUDE_MODEL") or CLAUDE_MODEL,
            max_tokens=700,
            tools=[REVIEW_TOOL],
            tool_choice={"type": "tool", "name": "submit_clip_review"},
            messages=[{"role": "user", "content": content}],
        )
        values = next(
            (block.input for block in response.content
             if getattr(block, "type", None) == "tool_use" and block.name == "submit_clip_review"),
            None,
        )
        if not isinstance(values, dict):
            raise ValueError("vision reviewer returned no structured result")
        score_names = ("visual_match", "continuity", "image_quality", "anatomy", "immersion", "story_progression")
        scores = {name: int(values.get(name, 0)) for name in score_names}
        fatal = [str(item) for item in values.get("fatal_problems", []) if item]
        threshold = int(os.getenv("LOCAL_VIDEO_VISION_MIN_SCORE", "7"))
        strict_pass = all(score >= threshold for score in scores.values())
        average = sum(scores.values()) / len(scores)
        quality_floor_pass = os.getenv("LOCAL_VIDEO_ALLOW_QUALITY_FLOOR", "0") == "1" and (
            scores["visual_match"] >= max(1, threshold - 2)
            and scores["continuity"] >= max(1, threshold - 1)
            and scores["image_quality"] >= threshold
            and scores["anatomy"] >= threshold
            and scores["immersion"] >= max(1, threshold - 1)
            and scores["story_progression"] >= threshold
            and average >= threshold - 0.6
        )
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
    content: list[dict[str, Any]] = [{"type": "text", "text": (
        "Review these chronological frames from the complete vertical social video. Judge the whole edit, "
        "not isolated beauty frames. The story must have a clear hook, causal progression and visible payoff; "
        "the same characters, wardrobe, props and geography must persist; captions must be readable and stay "
        "away from interface edges. Reject repeated shots, random objects, obvious identity changes, illegible "
        "captions, montage-like non sequiturs, or an ending that does not pay off the opening.\n\n"
        f"Title: {manifest.script.get('video_title', manifest.concept)}\n"
        f"Premise: {manifest.script.get('story_premise', manifest.concept)}\n"
        f"Goal: {manifest.script.get('protagonist_goal', '')}\n"
        f"Expected payoff: {manifest.script.get('ending_payoff', '')}"
    )}]
    for index, frame in enumerate(frames, 1):
        content.extend([
            {"type": "text", "text": f"Chronological final-video frame {index} of {len(frames)}:"},
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": frame}},
        ])
    try:
        import anthropic
        response = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY")).messages.create(
            model=os.getenv("VISION_MODEL") or os.getenv("CLAUDE_MODEL") or CLAUDE_MODEL,
            max_tokens=800,
            tools=[FINAL_REVIEW_TOOL],
            tool_choice={"type": "tool", "name": "submit_final_video_review"},
            messages=[{"role": "user", "content": content}],
        )
        values = next(
            (block.input for block in response.content
             if getattr(block, "type", None) == "tool_use" and block.name == "submit_final_video_review"),
            None,
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
