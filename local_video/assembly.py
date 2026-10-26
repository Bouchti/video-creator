"""Exact-duration video assembly, soundtrack mixing, captions, and outputs."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from agents.audio_fx import build_fx_track
from agents.beats import script_word_timings
from agents.captions import words_to_ass
from agents.transcription import transcribe_with_whisper, words_to_srt

from .config import PipelineConfig, resolve_within
from .models import ProjectManifest


def _run(command: list[str], timeout: int, label: str) -> None:
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"{label} failed: {result.stderr[-1500:]}")


def _ffmpeg_escape(path: str | Path) -> str:
    value = str(Path(path).resolve()).replace("\\", "/")
    return value.replace(":", "\\:").replace("'", "\\'").replace("[", "\\[").replace("]", "\\]")


def build_video_command(manifest: ProjectManifest, target: Path, config: PipelineConfig) -> list[str]:
    accepted = [shot for shot in manifest.shots if shot.status == "accepted" and shot.output]
    if len(accepted) != len(manifest.shots):
        raise ValueError("Every shot must be accepted before assembly")
    command = [config.ffmpeg, "-y"]
    for shot in accepted:
        command += ["-i", str(resolve_within(manifest.project_dir, shot.output))]
    filters: list[str] = []
    transition_lengths: list[float] = []
    raw_durations: list[float] = []
    for index, shot in enumerate(accepted):
        desired = shot.duration_seconds
        transition = 0.0 if index == len(accepted) - 1 else (
            4 / 30 if shot.transition == "crossfade" else 3 / 30 if shot.transition == "match_cut" else 2 / 30
        )
        transition_lengths.append(transition)
        raw = float((shot.validation or {}).get("duration") or desired)
        raw_durations.append(raw)
        output_duration = desired + transition
        if raw >= output_duration:
            timing = f"setpts={(output_duration / raw):.8f}*PTS"
            pad_seconds = 0.20
        else:
            stretch = min(output_duration / max(raw, 0.001), 1.12)
            stretched = raw * stretch
            timing = f"setpts={stretch:.8f}*PTS"
            pad_seconds = max(0.0, output_duration - stretched) + 0.20
        filters.append(
            f"[{index}:v]{timing},tpad=stop_mode=clone:stop_duration={pad_seconds:.6f},"
            "minterpolate=fps=30:mi_mode=blend,"
            f"trim=duration={output_duration:.6f},setpts=PTS-STARTPTS,"
            f"scale=1080:1920:force_original_aspect_ratio=increase:flags={config.upscale_filter},"
            "crop=1080:1920,setsar=1,eq=contrast=1.015:saturation=1.02"
            f"[v{index}]"
        )
    current = "v0"
    elapsed = accepted[0].duration_seconds
    for index in range(1, len(accepted)):
        transition = transition_lengths[index - 1]
        output = f"x{index}"
        filters.append(
            f"[{current}][v{index}]xfade=transition=fade:duration={transition:.6f}:offset={elapsed:.6f}[{output}]"
        )
        current = output
        elapsed += accepted[index].duration_seconds
    command += [
        "-filter_complex", ";".join(filters), "-map", f"[{current}]", "-an",
        "-t", f"{manifest.duration_seconds:.6f}", "-r", "30", "-c:v", "libx264",
        "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(target),
    ]
    return command


def build_ambience_command(manifest: ProjectManifest, target: Path, config: PipelineConfig) -> list[str]:
    command = [config.ffmpeg, "-y"]
    filters = []
    labels = []
    for index, shot in enumerate(manifest.shots):
        duration = shot.duration_seconds
        source_duration = duration + (0.10 if index < len(manifest.shots) - 1 else 0.0)
        # Generative video audio can contain invented speech, voices, or music.
        # Never mix it into the authored ElevenLabs/music soundtrack.
        command += ["-f", "lavfi", "-t", f"{source_duration:.6f}", "-i", "anullsrc=r=48000:cl=stereo"]
        filters.append(
            f"[{index}:a]atrim=duration={source_duration:.6f},asetpts=PTS-STARTPTS,aresample=48000,"
            f"apad=whole_dur={source_duration:.6f},volume=0.34[a{index}]"
        )
        labels.append(f"[a{index}]")
    current = "a0"
    for index in range(1, len(labels)):
        output = f"ax{index}"
        filters.append(f"[{current}][a{index}]acrossfade=d=0.10:c1=tri:c2=tri[{output}]")
        current = output
    command += [
        "-filter_complex", ";".join(filters), "-map", f"[{current}]", "-t", f"{manifest.duration_seconds:.6f}",
        "-c:a", "pcm_s16le", str(target),
    ]
    return command


def build_mix_command(
    manifest: ProjectManifest,
    ambience: Path,
    effects: Path,
    target: Path,
    config: PipelineConfig,
    narration: Path | None = None,
    music: Path | None = None,
) -> list[str]:
    command = [config.ffmpeg, "-y", "-i", str(ambience), "-i", str(effects)]
    narration_index = None
    music_index = None
    if narration:
        narration_index = 2
        command += ["-i", str(narration)]
    if music:
        music_index = 3 if narration else 2
        command += ["-stream_loop", "-1", "-i", str(music)]
    filters = ["[0:a]aresample=48000,volume=0.8[amb]", "[1:a]aresample=48000,volume=0.75[fx]"]
    mix = ["[amb]", "[fx]"]
    if narration_index is not None:
        narration_filter = (
            f"[{narration_index}:a]aresample=48000,loudnorm=I=-18:TP=-1.5:LRA=9,"
            f"apad=whole_dur={manifest.duration_seconds:.6f}"
        )
        if music_index is not None:
            narration_filter += ",asplit=2[narr][side]"
        else:
            narration_filter += "[narr]"
        filters.append(narration_filter)
        mix.append("[narr]")
    if music_index is not None:
        volume = float(os.getenv("MUSIC_VOLUME", "0.12"))
        filters.append(f"[{music_index}:a]aresample=48000,volume={volume:.4f}[music]")
        if narration_index is not None:
            filters.append("[music][side]sidechaincompress=threshold=0.035:ratio=8:attack=20:release=350[ducked]")
            mix.append("[ducked]")
        else:
            mix.append("[music]")
    filters.append(
        f"{''.join(mix)}amix=inputs={len(mix)}:duration=longest:normalize=0,"
        "loudnorm=I=-14:TP=-1.0:LRA=11,alimiter=limit=0.95[aout]"
    )
    command += [
        "-filter_complex", ";".join(filters), "-map", "[aout]", "-t", f"{manifest.duration_seconds:.6f}",
        "-c:a", "aac", "-b:a", "192k", str(target),
    ]
    return command


def build_final_command(
    video: Path,
    audio: Path,
    target: Path,
    duration: float,
    config: PipelineConfig,
    captions_ass: Path | None = None,
) -> list[str]:
    command = [config.ffmpeg, "-y", "-i", str(video), "-i", str(audio)]
    if captions_ass:
        command += ["-vf", f"subtitles='{_ffmpeg_escape(captions_ass)}'", "-c:v", "libx264", "-preset", "medium", "-crf", "18"]
    else:
        command += ["-c:v", "copy"]
    command += [
        "-map", "0:v:0", "-map", "1:a:0", "-t", f"{duration:.6f}", "-r", "30",
        "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(target),
    ]
    return command


def create_captions(
    narration: Path,
    output_dir: Path,
    export_srt: bool = True,
    word_highlight: bool = True,
    beats: list[dict[str, Any]] | None = None,
    total_duration: float | None = None,
) -> tuple[Path | None, Path | None, list[dict[str, Any]]]:
    heard_words = transcribe_with_whisper(str(narration))
    words = (
        script_word_timings(beats, heard_words, float(total_duration))
        if beats and total_duration else heard_words
    )
    ass = Path(words_to_ass(words, str(output_dir / "captions.ass"))) if word_highlight else None
    srt = None
    if export_srt or not word_highlight:
        srt = output_dir / "captions.srt"
        words_to_srt(words, str(srt))
    return ass, srt, words


def authored_effect_times(manifest: ProjectManifest) -> tuple[list[float], list[float]]:
    """Return deliberately authored effects; ordinary scene cuts stay silent."""
    whooshes: list[float] = []
    pops: list[float] = []
    events = manifest.settings.get("sound_effects", [])
    if not isinstance(events, list):
        return whooshes, pops
    for event in events:
        if not isinstance(event, dict):
            continue
        try:
            at = float(event.get("time"))
        except (TypeError, ValueError):
            continue
        if not 0.0 <= at <= manifest.duration_seconds:
            continue
        kind = str(event.get("type") or "").lower()
        if kind == "whoosh":
            whooshes.append(at)
        elif kind == "pop":
            pops.append(at)
    return whooshes, pops


def assemble_project(
    manifest: ProjectManifest,
    config: PipelineConfig,
    narration_path: Path | None = None,
    music_path: Path | None = None,
) -> dict[str, str]:
    project_dir = Path(manifest.project_dir)
    render_dir = project_dir / "render"
    render_dir.mkdir(parents=True, exist_ok=True)
    silent_video = render_dir / "assembled-video.mp4"
    ambience = render_dir / "ambience.wav"
    effects = render_dir / "effects.wav"
    soundtrack = render_dir / "soundtrack.m4a"
    final = project_dir / "final.mp4"
    thumbnail = project_dir / "thumbnail.jpg"

    _run(build_video_command(manifest, silent_video, config), 1800, "Video assembly")
    _run(build_ambience_command(manifest, ambience, config), 900, "Ambience assembly")
    whoosh_times, pop_times = authored_effect_times(manifest)
    build_fx_track(manifest.duration_seconds, whoosh_times, pop_times, str(effects))
    _run(build_mix_command(manifest, ambience, effects, soundtrack, config, narration_path, music_path), 600, "Audio mix")

    captions_ass = None
    captions_srt = None
    if narration_path and manifest.captions.get("enabled"):
        captions_ass, captions_srt, _ = create_captions(
            narration_path,
            project_dir,
            bool(manifest.captions.get("export_srt", True)),
            bool(manifest.captions.get("word_highlight", True)),
            manifest.script.get("beats") if isinstance(manifest.script.get("beats"), list) else None,
            manifest.duration_seconds,
        )
    burn = (captions_ass or captions_srt) if manifest.captions.get("burn_in", True) else None
    _run(build_final_command(silent_video, soundtrack, final, manifest.duration_seconds, config, burn), 1800, "Final render")
    thumb_command = [
        config.ffmpeg, "-y", "-ss", "1.0", "-i", str(final), "-frames:v", "1",
        "-vf", "scale=540:960:flags=lanczos", "-q:v", "2", str(thumbnail),
    ]
    _run(thumb_command, 120, "Thumbnail")
    outputs = {
        "video": str(final.relative_to(project_dir)),
        "thumbnail": str(thumbnail.relative_to(project_dir)),
        "soundtrack": str(soundtrack.relative_to(project_dir)),
        "ambience": str(ambience.relative_to(project_dir)),
    }
    if captions_srt:
        outputs["captions_srt"] = str(captions_srt.relative_to(project_dir))
    if captions_ass:
        outputs["captions_ass"] = str(captions_ass.relative_to(project_dir))
    return outputs
