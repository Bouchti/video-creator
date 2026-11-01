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


def post(run) -> str:
    b, script, facts = run.need("brief.json"), run.need("script.json"), run.need("facts.json")
    sound = run.load("audio/sound.json", {}) or {}
    words = re.findall(r"[A-Za-z]+", b["machine"].lower())
    tags = ["#howitworks", "#engineering", "#" + "".join(words)[:30], "#science", "#learnontiktok"][:5]
    used = sorted({f["source_url"] for f in facts["facts"]
                   if any(f["id"] in (x.get("fact_ids") or []) or (x.get("label") or {}).get("fact_id") == f["id"]
                          for x in script["beats"])} or {f["source_url"] for f in facts["facts"]})
    lines = [script["beats"][0]["narration"], "", " ".join(tags), "", "Sources:"]
    lines += [f"- {urlparse(u).netloc}: {u}" for u in used]
    if sound.get("music"):
        lines += ["", "Music: " + sound["music"]["credit"]]
    return "\n".join(lines) + "\n"


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
    credits["voice"] = {"provider": (run.load("voice/voice.json", {}) or {}).get("provider"),
                        "reference": "LibriVox 'The Time Machine' (public domain) via voice/reference.wav"}
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
