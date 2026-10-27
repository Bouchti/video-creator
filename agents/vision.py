"""
Vision check: before a stock clip or photo is used, Claude looks at the candidate
thumbnails and keeps only those that genuinely show what the beat describes.
One small request per beat (several thumbnails at once), on the Claude subscription.

Disable with VISION_CHECK=0. Model defaults to the pipeline's CLAUDE_MODEL;
override with VISION_MODEL.
"""
import os
import logging
import tempfile

from dotenv import load_dotenv
from PIL import Image

from config.paths import get_env_path, CLAUDE_MODEL
from agents import claude_cli

load_dotenv(get_env_path())
log = logging.getLogger("pipeline")

VISION_MODEL = os.getenv("VISION_MODEL") or CLAUDE_MODEL
THUMB_MAX_SIDE = 384  # plenty to judge the subject; keeps image tokens low

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
    return flag not in ("0", "false", "no", "off") and claude_cli.available()


def _thumbnail(path: str, target: str) -> None:
    img = Image.open(path).convert("RGB")
    img.thumbnail((THUMB_MAX_SIDE, THUMB_MAX_SIDE))
    img.save(target, format="JPEG", quality=80)


def rank_images(description: str, narration: str, image_paths: list):
    """Return indices of matching images (best first), or None if the check
    could not run — callers then fall back to the search order."""
    if not image_paths:
        return []
    with tempfile.TemporaryDirectory() as tmp:
        images = []
        for i, path in enumerate(image_paths):
            thumb = os.path.join(tmp, f"{i}.jpg")
            try:
                _thumbnail(path, thumb)
            except Exception:
                continue  # unreadable thumbnail: simply not offered
            images.append((f"Image {i}", thumb))
        if not images:
            return []
        prompt = (
            "A short educational video needs a shot for this narration line:\n"
            f"\"{narration}\"\n\nThe shot must show: {description}\n\n"
            "Which images genuinely show this — the right subject or action, not just a loosely "
            "related mood, place, or colour? Reject images dominated by text, logos, or watermarks. "
            "Submit their numbers (the N in 'Image N') best first as the structured output "
            "(empty list if none fit).")
        try:
            result = claude_cli.ask("You check stock images for a video editor.", prompt,
                                    RANK_TOOL["input_schema"], model=VISION_MODEL, images=images)
        except claude_cli.ClaudeError as e:
            log.warning(f"    Vision check unavailable ({str(e)[:80]}); using search order")
            return None

    raw = result.get("matches") if isinstance(result, dict) else None
    if not isinstance(raw, list):
        return None
    out = []
    for i in raw:
        if isinstance(i, int) and 0 <= i < len(image_paths) and i not in out:
            out.append(i)
    return out
