"""
Vision check: before a stock clip or photo is used, Claude looks at the candidate
thumbnails and keeps only those that genuinely show what the beat describes.
One small request per beat (several thumbnails at once) — a few cents per video,
instead of paying a video model.

Disable with VISION_CHECK=0. Model defaults to the pipeline's CLAUDE_MODEL;
override with VISION_MODEL.
"""
import base64
import io
import os
import logging

import anthropic
from dotenv import load_dotenv
from PIL import Image

from config.paths import get_env_path, CLAUDE_MODEL

load_dotenv(get_env_path())
log = logging.getLogger("pipeline")

VISION_MODEL = os.getenv("VISION_MODEL") or CLAUDE_MODEL
THUMB_MAX_SIDE = 384  # plenty to judge the subject; keeps image tokens low

_client = None

RANK_TOOL = {
    "name": "submit_matches",
    "description": "Submit which candidate images genuinely show the requested shot.",
    "input_schema": {
        "type": "object",
        "properties": {
            "matches": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Indices of images that clearly show the described subject, "
                               "best match first. Empty if none fit.",
            }
        },
        "required": ["matches"],
    },
}


def vision_enabled() -> bool:
    flag = os.getenv("VISION_CHECK", "1").strip().lower()
    return flag not in ("0", "false", "no", "off") and bool(os.getenv("ANTHROPIC_API_KEY"))


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


def _jpeg_b64(path: str) -> str:
    img = Image.open(path).convert("RGB")
    img.thumbnail((THUMB_MAX_SIDE, THUMB_MAX_SIDE))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")


def rank_images(description: str, narration: str, image_paths: list):
    """Return indices of matching images (best first), or None if the check
    could not run — callers then fall back to the search order."""
    if not image_paths:
        return []
    content = []
    for i, path in enumerate(image_paths):
        try:
            data = _jpeg_b64(path)
        except Exception:
            continue  # unreadable thumbnail: simply not offered
        content.append({"type": "text", "text": f"Image {i}:"})
        content.append({"type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": data}})
    if not content:
        return []
    content.append({"type": "text", "text": (
        "A short educational video needs a shot for this narration line:\n"
        f"\"{narration}\"\n\nThe shot must show: {description}\n\n"
        "Which images genuinely show this — the right subject or action, not just a loosely "
        "related mood, place, or colour? Reject images dominated by text, logos, or watermarks. "
        "Submit their indices best first with submit_matches (empty list if none fit).")})

    try:
        response = _get_client().messages.create(
            model=VISION_MODEL,
            max_tokens=300,
            tools=[RANK_TOOL],
            tool_choice={"type": "tool", "name": "submit_matches"},
            messages=[{"role": "user", "content": content}],
        )
    except anthropic.APIError as e:
        log.warning(f"    Vision check unavailable ({e.__class__.__name__}); using search order")
        return None

    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "submit_matches":
            raw = block.input.get("matches") if isinstance(block.input, dict) else None
            if not isinstance(raw, list):
                return None
            out = []
            for i in raw:
                if isinstance(i, int) and 0 <= i < len(image_paths) and i not in out:
                    out.append(i)
            return out
    return None
