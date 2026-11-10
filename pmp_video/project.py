"""
A PMP video project on disk, and the steps that turn a script into an MP4:

    output/pmp/<stamp>_<format>_<slug>/
        script.json        what is said and shown (edit it and re-render with `python -m pmp_video render <dir>`)
        audio/             one wav per narrated beat (cached by text), plus the optional music bed
        assets/            vendored fonts and GSAP
        index.html         the HyperFrames composition
        <slug>.mp4         the video
        post.txt / post.json   title, description with UTM link, chapters, tags
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from pmp_video import composition, voice
from pmp_video.config import (ASSETS, CHANNEL, FORMATS, HYPERFRAMES_VERSION, TRADEMARK, output_root, utm)

log = logging.getLogger("pipeline")


def slugify(text: str, limit: int = 60) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:limit].strip("-") or "video"


def new_project(script: dict) -> Path:
    slug = slugify(script["title"])
    script["slug"] = slug
    path = output_root() / f"{datetime.now():%Y%m%d_%H%M%S}_{script['format']}_{slug}"
    path.mkdir(parents=True)
    save_script(path, script)
    return path


def save_script(path: Path, script: dict) -> None:
    (path / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_script(path: Path) -> dict:
    return json.loads((path / "script.json").read_text(encoding="utf-8"))


def _hyperframes() -> list[str]:
    """The repo's HyperFrames launcher (plugin-pinned when installed), else npx with this pipeline's pin."""
    try:
        from cutaway.hf import launcher
        cmd = launcher()
        if cmd[-1] == "hyperframes":                       # plain npx: pin the version this pipeline is tested on
            cmd[-1] = f"hyperframes@{HYPERFRAMES_VERSION}"
        return cmd
    except ImportError:
        return [shutil.which("npx") or "npx", "--yes", f"hyperframes@{HYPERFRAMES_VERSION}"]


def hf(args: list[str], cwd: Path, timeout: int = 7200, check: bool = True) -> subprocess.CompletedProcess:
    cmd = _hyperframes() + args
    log.info("[pmp] hyperframes %s", " ".join(args))
    r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout, env={**os.environ, "HYPERFRAMES_TELEMETRY": "0"})
    if check and r.returncode != 0:
        raise RuntimeError(f"hyperframes {args[0]} failed ({r.returncode}):\n{(r.stdout or '')[-2500:]}\n"
                           f"{(r.stderr or '')[-1500:]}")
    return r


def _music_bed(path: Path, total: float) -> str | None:
    """Loop PMP_MUSIC (or --music) to the film length with fades; None when no music is configured."""
    src = os.getenv("PMP_MUSIC")
    if not src:
        return None
    if not Path(src).is_file():
        log.warning("[pmp] PMP_MUSIC %s not found; rendering without music", src)
        return None
    out = path / "audio" / "music_bed.wav"
    subprocess.run([voice.ffmpeg(), "-y", "-v", "error", "-stream_loop", "-1", "-i", src, "-t", f"{total:.3f}",
                    "-af", f"afade=t=in:d=1,afade=t=out:st={max(0, total - 2):.3f}:d=2", "-ac", "2", "-ar", "48000",
                    str(out)], check=True)
    return out.name


def voice_all(path: Path, script: dict, engine: str) -> dict[str, dict]:
    voiced: dict[str, dict] = {}
    beats = [b for s in script["scenes"] for b in s["beats"]]
    for n, b in enumerate(beats, 1):
        if b["say"] not in voiced:
            voiced[b["say"]] = voice.speak(b["say"], path / "audio", engine=engine)
            log.info("[pmp] voiced beat %d/%d (%.1fs)", n, len(beats), voiced[b["say"]]["duration"])
    return voiced


def compose(path: Path, script: dict, engine: str = "pipeline", captions_on: bool = True) -> Path:
    shape = FORMATS[script["format"]]["shape"]
    voiced = voice_all(path, script, engine)
    composition.schedule(script, voiced)
    dst = path / "assets"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(ASSETS, dst)
    music = _music_bed(path, script["duration"])
    (path / "index.html").write_text(composition.build(script, shape, captions_on=captions_on, music=music),
                                     encoding="utf-8")
    (path / "hyperframes.json").write_text(json.dumps({
        "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
        "paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"},
    }, indent=2), encoding="utf-8")
    (path / "meta.json").write_text(json.dumps({"id": path.name, "name": script["title"]}, indent=2),
                                    encoding="utf-8")
    save_script(path, script)
    return path / "index.html"


def render(path: Path, quality: str = "delivery", check: bool = True) -> Path:
    script = load_script(path)
    if check:
        lint = hf(["lint"], path, timeout=600, check=False)
        if lint.returncode != 0:
            raise RuntimeError("HyperFrames lint failed:\n" + (lint.stdout or "")[-3000:])
    out = path / f"{script['slug']}.mp4"
    hf(["render", ".", "-o", str(out), "-q", quality, "--quiet"], path)
    if not out.is_file():
        raise RuntimeError(f"Render finished without {out}")
    write_post(path, script)
    return out


def chapters(script: dict) -> list[tuple[float, str]]:
    marks = [(0.0, "Intro")]
    for s in script["scenes"]:
        if s["type"] == "chapter" and s.get("title"):
            label = s["title"] if not s.get("chapter") or s["chapter"] == s["title"] else f"{s['title']}: {s['chapter']}"
            marks.append((s["start"], label))
        elif s["type"] == "recap":
            marks.append((s["start"], s.get("heading", "Recap")))
    # YouTube needs the first at 0:00, at least 3 marks, each 10 s or longer
    kept = [marks[0]]
    for m in marks[1:]:
        if m[0] - kept[-1][0] >= 10:
            kept.append(m)
    return kept if len(kept) >= 3 else []


def _ts(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


def write_post(path: Path, script: dict) -> dict:
    fmt = FORMATS[script["format"]]
    link = utm(fmt["campaign"], script["slug"])
    marks = chapters(script) if not fmt["shape"].portrait else []
    lines = [script.get("hook") or script["title"], "",
             f"Try more questions like this free: {link}", ""]
    if marks:
        lines += ["Chapters"] + [f"{_ts(t)} {label}" for t, label in marks] + [""]
    lines += ["Aligned to the 2026 PMP Exam Content Outline (PMBOK 8).", "",
              "#PMP #PMPExam #ProjectManagement", "", TRADEMARK]
    post = {
        "title": script["title"][:100],
        "description": "\n".join(lines),
        "tags": ["PMP exam", "PMP 2026", "PMP exam prep", "PMP practice questions", "PMI mindset",
                 fmt["series"], CHANNEL],
        "playlist": fmt["series"],
        "pinned_comment": f"Practice free on the PMP Exam Lab simulator: {utm(fmt['campaign'], script['slug'], 'comment')}",
        "link": link,
    }
    (path / "post.json").write_text(json.dumps(post, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (path / "post.txt").write_text(
        f"TITLE\n{post['title']}\n\nDESCRIPTION\n{post['description']}\n\nPINNED COMMENT\n{post['pinned_comment']}\n\n"
        f"PLAYLIST\n{post['playlist']}\n\nTAGS\n{', '.join(post['tags'])}\n", encoding="utf-8")
    return post
