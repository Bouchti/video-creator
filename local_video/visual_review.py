"""Story-aware frame review for generated clips, with graceful offline fallback."""

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
            "fatal_problems": {"type": "array", "items": {"type": "string"}},
            "problems": {"type": "array", "items": {"type": "string"}},
            "revision_prompt": {"type": "string"},
        },
        "required": ["visual_match", "continuity", "image_quality", "anatomy", "immersion",
                     "fatal_problems", "problems", "revision_prompt"],
    },
}


def review_enabled() -> bool:
    value = os.getenv("LOCAL_VIDEO_VISION_QC", "1").strip().lower()
    return value not in {"0", "false", "no", "off"} and bool(os.getenv("ANTHROPIC_API_KEY"))


def _sample_frames(path: str | Path) -> list[str]:
    try:
        import cv2
    except ImportError:
        return []
    capture = cv2.VideoCapture(str(path))
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    encoded: list[str] = []
    for ratio in (0.05, 0.5, 0.95):
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
    """Return an acceptance report; service failures skip review rather than deadlocking a run."""
    if not review_enabled():
        return {"valid": True, "skipped": True, "reason": "vision QC disabled or API key unavailable"}
    frames = _sample_frames(path)
    if not frames:
        return {"valid": True, "skipped": True, "reason": "could not sample video frames"}
    content: list[dict[str, Any]] = []
    if previous_frame and previous_frame.is_file():
        prior = _encode_still(previous_frame)
        if prior:
            content.extend([
                {"type": "text", "text": "Previous shot's final continuity frame:"},
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": prior}},
            ])
    for index, frame in enumerate(frames, 1):
        content.extend([
            {"type": "text", "text": f"Candidate clip frame {index} of {len(frames)}:"},
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": frame}},
        ])
    content.append({"type": "text", "text": (
        "Review this candidate as a strict film editor. It must render only this assigned beat:\n"
        f"Visual action: {shot.subject_action}\nNarration meaning: {shot.narration}\n"
        f"World and identity lock: {shot.continuity}\n"
        "Reject story resets, wrong locations/actions, duplicated protagonists, broken anatomy, smeared or "
        "corrupt images, visible text/subtitles/logos, and clips that do not feel like one immersive continuous "
        "moment. A previous frame, if supplied, is reference only. Give concise, filmable corrections for a retry."
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
        score_names = ("visual_match", "continuity", "image_quality", "anatomy", "immersion")
        scores = {name: int(values.get(name, 0)) for name in score_names}
        fatal = [str(item) for item in values.get("fatal_problems", []) if item]
        threshold = int(os.getenv("LOCAL_VIDEO_VISION_MIN_SCORE", "7"))
        valid = not fatal and all(score >= threshold for score in scores.values())
        return {
            "valid": valid, "skipped": False, "threshold": threshold, **scores,
            "fatal_problems": fatal,
            "problems": [str(item) for item in values.get("problems", []) if item],
            "revision_prompt": str(values.get("revision_prompt") or "").strip(),
        }
    except Exception as exc:
        log.warning("Visual clip review unavailable (%s); continuing with local QC", exc.__class__.__name__)
        return {"valid": True, "skipped": True, "reason": f"vision review unavailable: {exc.__class__.__name__}"}
