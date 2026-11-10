"""
Stage 12 - package/: <quality>_9x16.mp4, cover.png, captions.srt, post.txt (hook, 3-5 hashtags, sources, credits)
and credits.json; the topic goes into runs/buildit/history.json so the picker never repeats it.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont

from config.paths import get_ffmpeg
from cutaway.stages.package import _srt_time

from ..assets.fetch import CREDITS, font
from ..compose import caption_groups
from ..runner import StageError
from .qa import candidate
from .topic import remember

log = logging.getLogger("pipeline")


def inputs(run):
    return [candidate(run), run.path("script.json")]


def srt(words: list[dict]) -> str:
    out = []
    for k, g in enumerate(caption_groups(words)):
        out += [str(k + 1), f"{_srt_time(g[0]['start'])} --> {_srt_time(g[-1]['end'] + 0.1)}",
                " ".join(w["text"] for w in g), ""]
    return "\n".join(out)


def cover(run, video: str, path: str):
    """The finished machine (the last wide frame) with the title in the caption style."""
    words = run.need("words.json")
    frame = run.path("package", "_cover_frame.png")
    subprocess.run([get_ffmpeg(), "-v", "error", "-y", "-ss", f"{max(0.0, words['duration'] - 1.5):.2f}", "-i",
                    video, "-frames:v", "1", frame], check=True)
    img = Image.open(frame).convert("RGB")
    d = ImageDraw.Draw(img)
    title = run.need("brief.json")["title"]
    f = ImageFont.truetype(font("Poppins-Black.ttf"), 96)
    lines, cur = [], ""
    for w in title.split():
        if d.textlength((cur + " " + w).strip(), font=f) > 880:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    lines.append(cur)
    y = 300
    for ln in lines:
        x = (1080 - d.textlength(ln, font=f)) / 2
        d.text((x, y), ln, font=f, fill="white", stroke_width=9, stroke_fill="#1d1712")
        y += 112
    img.save(path)
    os.remove(frame)


POST_SCHEMA = {"type": "object", "properties": {
    "tiktok_caption": {"type": "string", "description": "hook line, 1-2 lines on the idea, the closing question; emojis ok"},
    "youtube_title": {"type": "string", "description": "max 90 characters, curiosity + keyword, no hashtags"},
    "youtube_intro": {"type": "string", "description": "2 short paragraphs: the hook, then how it works in plain words, "
                                                       "ending with the closing question"},
    "instagram_caption": {"type": "string", "description": "hook, 2-3 lines explaining the idea, the closing question"},
    "hashtags": {"type": "array", "items": {"type": "string"}, "description": "6-10 single words, no # and no spaces"},
    "youtube_tags": {"type": "array", "items": {"type": "string"}, "description": "12-18 search phrases"},
    "alt_text": {"type": "string", "description": "one sentence describing the video for accessibility"},
}, "required": ["tiktok_caption", "youtube_title", "youtube_intro", "instagram_caption", "hashtags", "youtube_tags",
                "alt_text"]}


def _hashtags(words: list[str], fixed=("howitworks", "science")) -> list[str]:
    """Clean single-word hashtags (letters and digits only, never a mashed-up sentence)."""
    out = []
    for w in list(fixed) + list(words):
        t = re.sub(r"[^a-z0-9]", "", str(w).lower())
        if 3 <= len(t) <= 24 and t not in out:
            out.append(t)
    return ["#" + t for t in out[:10]]


def _chapters(run) -> list[str]:
    """YouTube chapters at the real beat times: the hook, then each part as it arrives."""
    words, script = run.need("words.json"), run.need("script.json")
    out = []
    for wb, sb in zip(words["beats"], script["beats"]):
        if sb["role"] == "hook":
            name = "The hook"
        elif sb["role"] == "fix":
            lab = (sb.get("label") or {}).get("text") or str(sb.get("part_added") or "").replace("_", " ")
            name = "The " + lab.lower()
        else:
            continue
        t = 0 if sb["role"] == "hook" else int(wb["start"])
        out.append(f"{t // 60}:{t % 60:02d} {name}")
    return out


def post(run) -> str:
    """Every description field for TikTok, YouTube Shorts and Instagram Reels: the creative text written from the
    script, the chapters, sources and music credit (required by its licence on every platform) from the run."""
    from agents import llm
    b, script, facts = run.need("brief.json"), run.need("script.json"), run.need("facts.json")
    sound = run.load("audio/sound.json", {}) or {}
    used = sorted({f["source_url"] for f in facts["facts"]
                   if any(f["id"] in (x.get("fact_ids") or []) or (x.get("label") or {}).get("fact_id") == f["id"]
                          for x in script["beats"])} or {f["source_url"] for f in facts["facts"]})
    narration = "\n".join(f"{x['role']}: {x['narration']}" for x in script["beats"])
    try:
        g = llm.ask("You write social posts for a premium science-explainer channel: punchy, accurate, no clickbait lies.",
                    f"""Video: "{b['title']}" ({b['topic']}), a vertical machine explainer.
Narration:
{narration}

Write the post fields. Keep every claim as the narration states it (same numbers, same conditions). End the
captions on the narration's closing question, inviting comments.""", POST_SCHEMA, effort="medium", label="buildit_post")
    except Exception as exc:                                            # noqa: BLE001
        log.warning("[package] post writer failed (%s): plain fields", str(exc)[:120])
        hook, q = script["beats"][0]["narration"], script["beats"][-1]["narration"]
        g = {"tiktok_caption": f"{hook}\n{q}", "youtube_title": b["title"][:90], "youtube_intro": f"{hook}\n\n{q}",
             "instagram_caption": f"{hook}\n\n{q}", "hashtags": ["engineering", "physics", "explained"],
             "youtube_tags": [b["topic"], "how it works", "science"], "alt_text": b["title"]}
    tags = _hashtags(g["hashtags"])
    music = ("Music: " + sound["music"]["credit"]) if sound.get("music") else ""
    music_short = re.sub(r"\s*Licensed under.*$", ", CC BY 4.0", music) if music else ""
    src = [f"- {urlparse(u).netloc}: {u}" for u in used]
    bar = lambda name: f"{'=' * 22} {name} {'=' * 22}"                  # noqa: E731
    lines = [bar("TIKTOK"), "CAPTION:", g["tiktok_caption"].strip(), "", " ".join(tags[:7]), "", music_short, "", "",
             bar("YOUTUBE SHORTS"), "TITLE (max 100 chars):", (g["youtube_title"].strip()[:90] + " #Shorts"), "",
             "DESCRIPTION:", g["youtube_intro"].strip(), "", "Chapters:", *_chapters(run), "", "Sources:", *src, "",
             music, "", "#Shorts " + " ".join(tags[:2]), "", "TAGS (comma-separated):",
             ", ".join(dict.fromkeys(t.strip() for t in g["youtube_tags"] if t.strip())), "", "",
             bar("INSTAGRAM REELS"), "CAPTION:", g["instagram_caption"].strip(), "", music_short, "",
             " ".join(tags), "", "ALT TEXT:", g["alt_text"].strip()]
    return "\n".join(lines).replace("\n\n\n\n", "\n\n\n") + "\n"


def run(run):
    q = run.quality
    d = run.path("package")
    os.makedirs(d, exist_ok=True)
    video = os.path.join(d, f"{q}_9x16.mp4")
    shutil.copyfile(candidate(run), video)
    cover(run, video, os.path.join(d, "cover.png"))
    with open(os.path.join(d, "captions.srt"), "w", encoding="utf-8") as f:
        f.write(srt(run.need("words.json")["words"]))
    with open(os.path.join(d, "post.txt"), "w", encoding="utf-8") as f:
        f.write(post(run))
    credits = json.load(open(CREDITS, encoding="utf-8")) if os.path.exists(CREDITS) else {}
    sound = run.load("audio/sound.json", {}) or {}
    from ..config import VOICE_REF
    credits["voice"] = {"provider": (run.load("voice/voice.json", {}) or {}).get("provider"),
                        "reference": VOICE_REF.get(run.meta.get("lang", "en"))}
    if sound.get("music"):
        credits["music_used"] = sound["music"]
    with open(os.path.join(d, "credits.json"), "w", encoding="utf-8") as f:
        json.dump(credits, f, indent=1)
    if q == "final":
        remember(run.meta.get("topic", run.slug), run.slug)


def validate(run):
    q = run.quality
    for n in (f"{q}_9x16.mp4", "cover.png", "captions.srt", "post.txt", "credits.json"):
        if not os.path.exists(run.path("package", n)):
            raise StageError(f"package/{n} missing")
