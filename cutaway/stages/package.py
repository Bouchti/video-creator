"""
Stage 11 - the delivery folder runs/<slug>/package/:

  final_9x16.mp4 (draft_9x16.mp4 for --draft), final_1x1.mp4 and final_16x9.mp4 reframes, cover.png (a strong
  section frame + the title), captions.srt (from the word timings), post.txt (hook caption, hashtags, sources,
  credits) and credits.json.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config.paths import get_ffmpeg

from .. import kits
from ..assets.fetch import font
from ..config import BRAND
from ..runner import StageError
from .compose import caption_groups

log = logging.getLogger("pipeline")


def inputs(run):
    return [run.path("qa", "qa.json"), run.path("credits.json"), run.quality]


def _srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def srt(words: dict) -> str:
    out = []
    for i, g in enumerate(caption_groups(words["words"]), start=1):
        out.append(f"{i}\n{_srt_time(g[0]['start'])} --> {_srt_time(g[-1]['end'] + 0.1)}\n"
                   f"{' '.join(w['text'] for w in g)}\n")
    return "\n".join(out)


def cover(run, video: str, path: str):
    """The middle of the first sectioned shot with a callout, the title set big over the header band."""
    sl = run.need("shotlist.json")
    shot = next((s for s in sl["shots"] if s["cut"]["state"] == "sectioned"), sl["shots"][0])
    t = (shot["start"] + shot["end"]) / 2
    frame = path + ".frame.png"
    subprocess.run([get_ffmpeg(), "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1", frame],
                   check=True)
    im = Image.open(frame).convert("RGB")
    os.remove(frame)
    shade = Image.new("L", im.size, 0)
    ImageDraw.Draw(shade).rectangle([0, 0, im.width, 640], fill=150)
    shade = shade.filter(ImageFilter.GaussianBlur(120))
    im = Image.composite(Image.new("RGB", im.size, (6, 10, 20)), im, shade)
    title = run.need("brief.json")["title"].upper()
    d = ImageDraw.Draw(im)
    size = 150
    f = ImageFont.truetype(font(), size)
    words, lines, cur = title.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if d.textlength(test, font=f) > im.width - 140 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = test
    lines.append(cur)
    y = 200
    for k, line in enumerate(lines[:3]):
        x = (im.width - d.textlength(line, font=f)) / 2
        d.text((x + 4, y + 6), line, font=f, fill=(0, 0, 0))
        d.text((x, y), line, font=f, fill=BRAND["hot"] if k == len(lines[:3]) - 1 else BRAND["ink"])
        y += int(size * 1.02)
    im.save(path)


def post(run) -> str:
    brief = run.need("brief.json")
    script = run.need("script.json")
    facts = run.need("facts.json")["facts"]
    credits = run.need("credits.json")
    kit = kits.KITS[brief["kit"]]
    hook = script["beats"][0]["narration"]
    question = script["beats"][-1]["narration"].split(". ")[-1]
    used = {b["stat"]["fact_id"] for b in script["beats"] if b.get("stat")}
    used |= {f for b in script["beats"] for f in b.get("fact_ids", [])}
    domains = []
    for f in facts:
        if f["id"] in used:
            dom = urlparse(f["source_url"]).netloc.replace("www.", "")
            if dom not in domains:
                domains.append(dom)
    tags = ["#engineering", "#howitworks"] + ["#" + t.replace(" ", "").replace("-", "")
                                              for t in kit["topics"][:3]]
    lines = [hook, "", question, "", " ".join(tags[:5]), "", "Sources: " + ", ".join(domains)]
    music = credits.get("music", {})
    if music.get("credit"):
        lines += ["", "Music: " + music["credit"]]
    for cue, s in (credits.get("sfx") or {}).items():
        if s.get("license") not in ("cc0", "bundled", None) and s.get("credit"):
            lines.append("Sound: " + s["credit"])
    return "\n".join(lines) + "\n"


def run(run):
    qa = run.need("qa/qa.json")
    src = qa["candidate"]
    out = run.path("package")
    os.makedirs(out, exist_ok=True)
    name = "final" if run.quality == "final" else "draft"
    main = os.path.join(out, f"{name}_9x16.mp4")
    shutil.copyfile(src, main)
    ff = get_ffmpeg()
    # 1:1 keeps the mechanism band and the caption band; 16:9 sets the vertical film on its own blurred plate
    subprocess.run([ff, "-v", "error", "-y", "-i", main, "-vf", "crop=1080:1080:0:420", "-c:v", "libx264",
                    "-crf", "16", "-preset", "medium", "-c:a", "copy", os.path.join(out, f"{name}_1x1.mp4")],
                   check=True)
    subprocess.run([ff, "-v", "error", "-y", "-i", main, "-filter_complex",
                    "[0:v]scale=1920:-2,crop=1920:1080,boxblur=40:2,eq=brightness=-0.12[bg];"
                    "[0:v]scale=-2:1080[fg];[bg][fg]overlay=(W-w)/2:0", "-c:v", "libx264", "-crf", "16",
                    "-preset", "medium", "-c:a", "copy", os.path.join(out, f"{name}_16x9.mp4")], check=True)
    cover(run, main, os.path.join(out, "cover.png"))
    with open(os.path.join(out, "captions.srt"), "w", encoding="utf-8") as f:
        f.write(srt(run.need("words.json")))
    with open(os.path.join(out, "post.txt"), "w", encoding="utf-8") as f:
        f.write(post(run))
    shutil.copyfile(run.path("credits.json"), os.path.join(out, "credits.json"))
    log.info("[package] %s", out)


def validate(run):
    out = run.path("package")
    name = "final" if run.quality == "final" else "draft"
    for f in (f"{name}_9x16.mp4", "cover.png", "captions.srt", "post.txt", "credits.json"):
        if not os.path.exists(os.path.join(out, f)):
            raise StageError(f"package is missing {f}")
