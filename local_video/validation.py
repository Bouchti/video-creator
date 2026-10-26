"""FFprobe and sampled-frame validation for generated media."""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import Any

from .config import PipelineConfig, VIDEO_EXTENSIONS


def ffprobe(path: str | Path, config: PipelineConfig) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file() or source.stat().st_size == 0:
        raise ValueError(f"Generated file is missing or empty: {source}")
    if source.suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValueError(f"Generated output has unsupported extension: {source.suffix}")
    command = [
        config.ffprobe, "-v", "error", "-show_streams", "-show_format",
        "-count_frames", "-of", "json", str(source),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise ValueError(f"FFprobe rejected {source.name}: {result.stderr[-800:]}")
    try:
        return json.loads(result.stdout)
    except ValueError as exc:
        raise ValueError(f"FFprobe returned invalid JSON for {source.name}") from exc


def _ratio(value: str | None) -> float:
    if not value or value in {"0/0", "N/A"}:
        return 0.0
    try:
        numerator, denominator = value.split("/", 1)
        return float(numerator) / float(denominator)
    except (ValueError, ZeroDivisionError):
        return 0.0


def media_metadata(value: dict[str, Any]) -> dict[str, Any]:
    streams = value.get("streams") or []
    video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    video = video_streams[0] if video_streams else None
    if not video:
        raise ValueError("No video stream was found")
    audio = audio_streams[0] if audio_streams else None
    duration = float(video.get("duration") or (value.get("format") or {}).get("duration") or 0.0)
    fps = _ratio(video.get("avg_frame_rate") or video.get("r_frame_rate"))
    frames = video.get("nb_read_frames") or video.get("nb_frames")
    try:
        frame_count = int(frames)
    except (TypeError, ValueError):
        frame_count = round(duration * fps) if fps else 0
    return {
        "duration": duration,
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "fps": fps,
        "frame_count": frame_count,
        "video_codec": video.get("codec_name"),
        "video_stream_count": len(video_streams),
        "has_audio": audio is not None,
        "audio_codec": audio.get("codec_name") if audio else None,
        "audio_stream_count": len(audio_streams),
    }


def motion_metrics(path: str | Path, samples: int = 24) -> dict[str, float]:
    """Sample grayscale frames and report black/frozen/low-motion indicators."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {"black_ratio": 0.0, "frozen_ratio": 0.0, "motion_score": math.inf, "samples": 0}
    capture = cv2.VideoCapture(str(path))
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if count <= 1:
        capture.release()
        return {"black_ratio": 1.0, "frozen_ratio": 1.0, "motion_score": 0.0, "samples": 0}
    positions = np.linspace(0, count - 1, min(samples, count), dtype=int)
    frames = []
    for position in positions:
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(position))
        ok, frame = capture.read()
        if ok and frame is not None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, (160, 90), interpolation=cv2.INTER_AREA)
            frames.append(gray)
    capture.release()
    if len(frames) < 2:
        return {"black_ratio": 1.0, "frozen_ratio": 1.0, "motion_score": 0.0, "samples": len(frames)}
    means = [float(frame.mean()) for frame in frames]
    diffs = [float(cv2.absdiff(a, b).mean()) for a, b in zip(frames, frames[1:])]
    return {
        "black_ratio": sum(value < 5.0 for value in means) / len(means),
        "frozen_ratio": sum(value < 0.12 for value in diffs) / len(diffs),
        "motion_score": sum(diffs) / len(diffs),
        "samples": len(frames),
    }


def visual_quality_metrics(path: str | Path, samples: int = 12) -> dict[str, float]:
    """Detect severely blurred or oversaturated artifact frames missed by container checks."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {"focus_score": math.inf, "edge_density": math.inf, "colorfulness": 0.0,
                "artifact_score": 0.0, "quality_samples": 0}
    capture = cv2.VideoCapture(str(path))
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    values = []
    if count > 0:
        for position in np.linspace(0, count - 1, min(samples, count), dtype=int):
            capture.set(cv2.CAP_PROP_POS_FRAMES, int(position))
            ok, frame = capture.read()
            if not ok or frame is None:
                continue
            frame = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            focus = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            edges = float((cv2.Canny(gray, 80, 160) > 0).mean() * 100.0)
            b, g, r = cv2.split(frame.astype("float32"))
            rg, yb = np.abs(r - g), np.abs(0.5 * (r + g) - b)
            color = float(np.sqrt(rg.mean() ** 2 + yb.mean() ** 2) +
                          0.3 * np.sqrt(rg.std() ** 2 + yb.std() ** 2))
            values.append((focus, edges, color))
    capture.release()
    if not values:
        return {"focus_score": math.inf, "edge_density": math.inf, "colorfulness": 0.0,
                "artifact_score": 0.0, "quality_samples": 0}
    focus, edges, colors = (float(np.median([row[i] for row in values])) for i in range(3))
    return {"focus_score": focus, "edge_density": edges, "colorfulness": colors,
            "artifact_score": colors / max(edges, 1.0), "quality_samples": len(values)}


def validate_clip(
    path: str | Path,
    config: PipelineConfig,
    expected_width: int,
    expected_height: int,
    expected_seconds: float,
) -> dict[str, Any]:
    metadata = media_metadata(ffprobe(path, config))
    problems: list[str] = []
    if metadata["width"] != expected_width or metadata["height"] != expected_height:
        problems.append(
            f"wrong size {metadata['width']}x{metadata['height']} (expected {expected_width}x{expected_height})"
        )
    if metadata["duration"] < max(1.0, expected_seconds * 0.65):
        problems.append(f"abnormally short ({metadata['duration']:.3f}s; expected about {expected_seconds:.3f}s)")
    if metadata["frame_count"] < 8:
        problems.append(f"too few frames ({metadata['frame_count']})")
    metrics = motion_metrics(path)
    if metrics["black_ratio"] >= 0.80:
        problems.append(f"mostly black frames ({metrics['black_ratio']:.0%})")
    if metrics["frozen_ratio"] >= 0.92:
        problems.append(f"mostly frozen frames ({metrics['frozen_ratio']:.0%})")
    if metrics["samples"] and metrics["motion_score"] < 0.18:
        problems.append(f"extremely low motion ({metrics['motion_score']:.3f})")
    quality = visual_quality_metrics(path)
    if quality["quality_samples"] and quality["focus_score"] < 12.0:
        problems.append(f"severely blurred frames (focus {quality['focus_score']:.1f})")
    if (quality["quality_samples"] and (
            (quality["artifact_score"] > 22.0 and quality["colorfulness"] > 85.0)
            or (quality["artifact_score"] > 14.0 and quality["colorfulness"] > 140.0))):
        problems.append("probable smeared/oversaturated generation artifacts")
    report = {**metadata, **metrics, **quality, "valid": not problems, "problems": problems}
    if problems:
        raise ValueError("; ".join(problems))
    return report


def validate_final(path: str | Path, config: PipelineConfig, duration: float) -> dict[str, Any]:
    metadata = media_metadata(ffprobe(path, config))
    problems = []
    if (metadata["width"], metadata["height"]) != (1080, 1920):
        problems.append(f"final size is {metadata['width']}x{metadata['height']}, expected 1080x1920")
    if abs(metadata["duration"] - duration) > 0.08:
        problems.append(f"final duration is {metadata['duration']:.3f}s, expected {duration:.3f}s")
    if abs(metadata["fps"] - 30.0) > 0.05:
        problems.append(f"final frame rate is {metadata['fps']:.3f}, expected 30")
    expected_frames = round(duration * 30)
    if abs(metadata["frame_count"] - expected_frames) > 2:
        problems.append(
            f"final video has {metadata['frame_count']} frames, expected about {expected_frames}"
        )
    if metadata["video_codec"] != "h264":
        problems.append(f"final video codec is {metadata['video_codec']}, expected h264")
    if not metadata["has_audio"] or metadata["audio_codec"] != "aac":
        problems.append(f"final audio codec is {metadata['audio_codec']}, expected aac")
    if metadata["video_stream_count"] != 1 or metadata["audio_stream_count"] != 1:
        problems.append(
            f"final stream layout is {metadata['video_stream_count']} video / "
            f"{metadata['audio_stream_count']} audio; expected exactly 1 / 1"
        )
    metadata.update(valid=not problems, problems=problems)
    if problems:
        raise ValueError("; ".join(problems))
    return metadata


def extract_last_frame(path: str | Path, target: str | Path, config: PipelineConfig) -> Path:
    output = Path(target)
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [config.ffmpeg, "-y", "-sseof", "-0.08", "-i", str(path), "-frames:v", "1", str(output)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if result.returncode != 0 or not output.is_file():
        raise RuntimeError(f"Could not extract continuity frame: {result.stderr[-500:]}")
    return output
