"""Shared FFmpeg helpers used by every maintained video pipeline."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from datetime import datetime

from config.paths import get_ffmpeg, get_ffprobe, get_temp_dir

log = logging.getLogger("pipeline")


def _tool_path(name: str) -> str:
    try:
        return get_ffmpeg() if name == "ffmpeg" else get_ffprobe()
    except FileNotFoundError:
        return name


FFMPEG = _tool_path("ffmpeg")
FFPROBE = _tool_path("ffprobe")


def remove_files(paths) -> None:
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError as exc:
                log.warning("Could not remove temporary file %s: %s", path, exc)



def run_process(cmd, timeout: int, cleanup_paths=()):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception:
        remove_files(cleanup_paths)
        raise


def run(cmd, **kw):
    """Run a tool and return its CompletedProcess; raise with the tail of its output when it fails."""
    kw.setdefault("text", True)
    r = subprocess.run(cmd, capture_output=True, **kw)
    if r.returncode != 0:
        err = r.stderr or r.stdout
        err = err.decode("utf-8", "replace") if isinstance(err, bytes) else err
        raise RuntimeError(f"{os.path.basename(str(cmd[0]))} failed: {err[-1500:]}")
    return r


def probe_json(path, entries: str = "format=duration:stream=codec_type,width,height", timeout: int = 30) -> dict:
    """ffprobe's JSON for `path`, limited to `entries`."""
    return json.loads(run([FFPROBE, "-v", "error", "-show_entries", entries, "-of", "json", str(path)],
                          timeout=timeout).stdout)


def vertical_short_problems(path, min_seconds: float, max_seconds: float) -> tuple[float, list[str]]:
    """(duration, why `path` is not a deliverable short): 1080x1920 video, an audio stream and
    min_seconds < duration < max_seconds."""
    try:
        info = probe_json(path)
    except (RuntimeError, ValueError):
        return 0.0, [f"ffprobe could not read {path}"]
    streams = info.get("streams", [])
    video = [s for s in streams if s.get("codec_type") == "video"]
    duration = float(info.get("format", {}).get("duration") or 0)
    problems = []
    if not video:
        problems.append("no video stream")
    elif (video[0].get("width"), video[0].get("height")) != (1080, 1920):
        problems.append(f"video is {video[0].get('width')}x{video[0].get('height')}, not 1080x1920")
    if not any(s.get("codec_type") == "audio" for s in streams):
        problems.append("no audio stream")
    if not min_seconds < duration < max_seconds:
        problems.append(f"duration {duration:.2f}s is outside {min_seconds:g}-{max_seconds:g} s")
    return duration, problems


def read_pcm(path, sr: int, seconds: float | None = None):
    """Mono float32 samples in [-1, 1] at `sr`, decoded by FFmpeg (the first `seconds` only, if given)."""
    import numpy as np
    head = ["-t", str(seconds)] if seconds else []
    raw = run([FFMPEG, "-v", "error", "-i", str(path), *head, "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
              text=False).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768


def write_wav(path, x, sr: int) -> str:
    """Write mono float samples (clipped to [-1, 1]) as a 16-bit WAV."""
    import wave
    import numpy as np
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    return path



def get_duration(file_path: str) -> float:
    result = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", file_path],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe duration failed for {file_path}: {result.stderr[-300:]}")
    return float(result.stdout.strip()) if result.stdout.strip() else 0.0


def get_dimensions(file_path: str) -> tuple[int, int]:
    result = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", file_path],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe dimensions failed for {file_path}: {result.stderr[-300:]}")
    value = result.stdout.strip()
    return tuple(map(int, value.split("x"))) if value else (0, 0)


def detect_crop(input_path: str):
    command = [FFMPEG, "-ss", "1", "-i", input_path, "-t", "2",
               "-vf", "cropdetect=limit=24:round=2:reset=0", "-f", "null", "-"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        source_width, source_height = get_dimensions(input_path)
    except Exception:
        return None
    found = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", result.stderr)
    if not found or not source_width or not source_height:
        return None
    width, height, x, y = map(int, found[-1])
    if (width < source_width * 0.4 or height < source_height * 0.4
            or width * height > source_width * source_height * 0.96):
        return None
    return f"crop={width}:{height}:{x}:{y}"


def landscape_to_vertical(
    input_path: str,
    output_path: str,
    duration: float,
    loop: bool = False,
    overlay_path: str | None = None,
    crop: str | None = None,
) -> str:
    fill = (f"{crop}," if crop else "") + (
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    )
    prefix = [FFMPEG, "-y"] + (["-stream_loop", "-1"] if loop else [])
    if overlay_path:
        command = prefix + [
            "-i", input_path, "-i", overlay_path, "-t", str(duration),
            "-filter_complex", f"[0:v]{fill}[v];[v][1:v]overlay=0:0",
            "-r", "30", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-an", output_path,
        ]
    else:
        command = prefix + [
            "-i", input_path, "-t", str(duration), "-vf", fill,
            "-r", "30", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-an", output_path,
        ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"Vertical conversion failed: {result.stderr[-300:]}")
    return output_path


def concat_clips(clip_paths: list[str], target_duration: float) -> str:
    if not clip_paths:
        raise ValueError("At least one clip is required for stitching")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    concat_file = os.path.join(get_temp_dir(), f"concat_{stamp}.txt")
    stitched_path = os.path.join(get_temp_dir(), f"stitched_{stamp}.mp4")
    try:
        with open(concat_file, "w", encoding="utf-8") as stream:
            for path in clip_paths:
                escaped = path.replace("'", "'\\''")
                stream.write(f"file '{escaped}'\n")
        result = run_process([
            FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
            "-t", str(target_duration), "-c:v", "libx264", "-preset", "fast", "-crf", "21",
            "-r", "30", "-pix_fmt", "yuv420p", "-movflags", "+faststart", stitched_path,
        ], 240, [concat_file, stitched_path])
        if result.returncode != 0:
            raise RuntimeError(f"Stitch failed: {result.stderr[-300:]}")
        get_duration(stitched_path)
        return stitched_path
    except Exception:
        remove_files([stitched_path])
        raise
    finally:
        remove_files([concat_file])


def merge_audio_video(video_path: str, audio_path: str) -> str:
    target = os.path.join(get_temp_dir(), f"merged_{datetime.now():%Y%m%d_%H%M%S_%f}.mp4")
    result = subprocess.run([
        FFMPEG, "-y", "-i", video_path, "-i", audio_path,
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-map", "0:v:0", "-map", "1:a:0", "-movflags", "+faststart", target,
    ], capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"Audio merge failed: {result.stderr[-300:]}")
    return target


def burn_subtitles(video_path: str, subtitle_path: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    temp_dir = get_temp_dir()
    target = os.path.join(temp_dir, f"final_{stamp}.mp4")
    extension = os.path.splitext(subtitle_path)[1].lower() or ".srt"
    local_name = f"subs_{stamp}{extension}"
    local_path = os.path.join(temp_dir, local_name)
    shutil.copy(subtitle_path, local_path)
    style = (
        "FontName=Arial Bold,FontSize=14,PrimaryColour=&H0000FFFF,"
        "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,"
        "Alignment=2,MarginV=60"
    )
    video_filter = (
        f"subtitles={local_name}" if extension == ".ass"
        else f"subtitles={local_name}:force_style='{style}'"
    )
    try:
        result = subprocess.run([
            FFMPEG, "-y", "-i", video_path, "-vf", video_filter,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "copy", "-movflags", "+faststart", target,
        ], capture_output=True, text=True, timeout=300, cwd=temp_dir)
        if result.returncode != 0:
            raise RuntimeError(f"Subtitle burn failed: {result.stderr[-600:]}")
    finally:
        remove_files([local_path])
    return target
