"""Shared FFmpeg helpers used by every maintained video pipeline."""

from __future__ import annotations

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


# Temporary compatibility alias while callers migrate.
_remove_files = remove_files


def run_process(cmd, timeout: int, cleanup_paths=()):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception:
        remove_files(cleanup_paths)
        raise


_run_process = run_process


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


def stitch_clips_to_duration(
    clip_paths: list[str], target_duration: float, loop_to_fill: bool = False,
) -> str:
    if not clip_paths:
        raise ValueError("At least one clip is required for stitching")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    per_clip = target_duration / len(clip_paths)
    normalized: list[str] = []
    total = 0.0
    try:
        for index, clip in enumerate(clip_paths):
            target = os.path.join(get_temp_dir(), f"norm_{index}_{stamp}.mp4")
            normalized.append(target)
            actual = get_duration(clip)
            seconds = per_clip if loop_to_fill else min(per_clip + 0.2, actual)
            landscape_to_vertical(clip, target, seconds, loop=loop_to_fill)
            total += get_duration(target)
        if total < target_duration - 0.5:
            gap_target = os.path.join(get_temp_dir(), f"loop_{stamp}.mp4")
            result = run_process([
                FFMPEG, "-y", "-stream_loop", "-1", "-i", normalized[-1],
                "-t", str(target_duration - total + 0.3), "-c:v", "libx264",
                "-preset", "ultrafast", "-crf", "23", "-pix_fmt", "yuv420p",
                "-an", gap_target,
            ], 60, normalized + [gap_target])
            if result.returncode != 0:
                raise RuntimeError(f"Clip loop failed: {result.stderr[-300:]}")
            normalized.append(gap_target)
        return concat_clips(normalized, target_duration)
    finally:
        remove_files(normalized)


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
