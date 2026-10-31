"""Exact-duration video assembly, soundtrack mixing, captions, and outputs."""

from __future__ import annotations

import difflib
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from agents.audio_fx import build_fx_track
from agents.beats import script_word_timings
from agents.captions import words_to_ass
from agents.transcription import transcribe_with_whisper, words_to_srt
from agents.voice import generate_voiceover

from .config import MAX_CLIP_STRETCH, MAX_TRANSITION_SECONDS, PipelineConfig, resolve_within
from .models import ProjectManifest
from .upscale import upscale_clips

log = logging.getLogger("pipeline")


def ensure_narration(manifest: ProjectManifest) -> Path | None:
    """The project's narration (audio/narration.mp3), voiced once and reused on resume; None without one."""
    if not manifest.narration_enabled or not str(manifest.script.get("spoken_script") or "").strip():
        return None
    target = Path(manifest.project_dir) / "audio" / "narration.mp3"
    if target.is_file():
        return target
    source, duration = generate_voiceover(manifest.script["spoken_script"], voice=manifest.voice)
    shutil.move(source, target)
    manifest.record("narration_created", duration=duration, path=str(target.relative_to(manifest.project_dir)))
    manifest.save()
    return target


def _run(command: list[str], timeout: int, label: str) -> None:
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"{label} failed: {result.stderr[-1500:]}")


def _ffmpeg_escape(path: str | Path) -> str:
    value = str(Path(path).resolve()).replace("\\", "/")
    return value.replace(":", "\\:").replace("'", "\\'").replace("[", "\\[").replace("]", "\\]")


# Natural grade plus fine temporal grain: reads as camera footage, not a smooth AI render. "film" (opt-in via
# LOCAL_VIDEO_GRADE) also lifts the blacks, mutes colour, softens and vignettes; tried as the default on
# 2026-10-31, the final review then called the Lake Tanganyika cut "hazy, over-graded, dreamy".
GRADES = {
    "plain": "eq=contrast=1.03:saturation=0.96,noise=alls=5:allf=t+u",
    "film": ("curves=all='0/0.05 0.5/0.5 1/0.95',eq=contrast=1.02:saturation=0.88,gblur=sigma=0.5,"
             "unsharp=5:5:0.35,vignette=PI/5,noise=alls=8:allf=t+u"),
}


def grade() -> str:
    return GRADES.get(os.getenv("LOCAL_VIDEO_GRADE", "plain").strip().lower(), GRADES["plain"])


def build_video_command(
    manifest: ProjectManifest, target: Path, config: PipelineConfig, clips: dict[str, Path] | None = None,
) -> list[str]:
    """`clips` maps shot ids to sharpened copies; other shots use their accepted output."""
    accepted = [shot for shot in manifest.shots if shot.status == "accepted" and shot.output]
    if len(accepted) != len(manifest.shots):
        raise ValueError("Every shot must be accepted before assembly")
    command = [config.ffmpeg, "-y"]
    for shot in accepted:
        command += ["-i", str((clips or {}).get(shot.id) or resolve_within(manifest.project_dir, shot.output))]
    filters: list[str] = []
    transition_lengths: list[float] = []
    raw_durations: list[float] = []
    for index, shot in enumerate(accepted):
        desired = shot.duration_seconds
        transition = 0.0 if index == len(accepted) - 1 else (
            MAX_TRANSITION_SECONDS if shot.transition == "crossfade" else 3 / 30 if shot.transition == "match_cut" else 2 / 30
        )
        transition_lengths.append(transition)
        raw = float((shot.validation or {}).get("duration") or desired)
        raw_durations.append(raw)
        output_duration = desired + transition
        if raw >= output_duration:
            # Mild speed-up only; past that, skip the opening and keep the ending's payoff
            # (racing a whole clip into a short shot reads as fast-forward).
            speed = min(raw / output_duration, MAX_CLIP_SPEEDUP)
            skip = max(0.0, raw - output_duration * speed)
            timing = f"trim=start={skip:.6f},setpts=PTS-STARTPTS,setpts={(1 / speed):.8f}*PTS"
            pad_seconds = 0.20
        else:
            stretch = min(output_duration / max(raw, 0.001), MAX_CLIP_STRETCH)
            stretched = raw * stretch
            timing = f"setpts={stretch:.8f}*PTS"
            pad_seconds = max(0.0, output_duration - stretched) + 0.20
        filters.append(
            f"[{index}:v]{timing},tpad=stop_mode=clone:stop_duration={pad_seconds:.6f},"
            # Repeat frames to reach 30 fps; blending neighbours leaves ghost doubles on motion.
            "fps=30,"
            f"trim=duration={output_duration:.6f},setpts=PTS-STARTPTS,"
            f"scale=1080:1920:force_original_aspect_ratio=increase:flags={config.upscale_filter},"
            "crop=1080:1920,setsar=1,"
            f"{grade()}[v{index}]"
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
    mix = ["[fx]"]
    if narration_index is not None:
        narration_filter = (
            f"[{narration_index}:a]aresample=48000,loudnorm=I=-18:TP=-1.5:LRA=9,"
            f"apad=whole_dur={manifest.duration_seconds:.6f}"
        )
        # The sound bed dips under the voice and comes back in its pauses, like the music: at a fixed
        # level the Ghost Army effects (2026-10-31) were "exaggerated" against the narration.
        if music_index is not None:
            narration_filter += ",asplit=3[narr][side][ambside]"
        else:
            narration_filter += ",asplit=2[narr][ambside]"
        filters.append(narration_filter)
        filters.append("[amb][ambside]sidechaincompress=threshold=0.03:ratio=4:attack=30:release=450[ambducked]")
        mix += ["[ambducked]", "[narr]"]
    else:
        mix.append("[amb]")
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


def snap_to_script(words: list[dict[str, Any]], script: str) -> list[dict[str, Any]]:
    """Spell heard words as the script does: Whisper hears the name 'Karan' as 'Kharan'.

    Only runs the aligner pairs one-to-one are respelled, so a word the voice skipped or
    Whisper split never shifts the timings.
    """
    tokens = script.split()

    def key(text: str) -> str:
        return re.sub(r"[^a-z0-9]", "", text.lower())

    matcher = difflib.SequenceMatcher(None, [key(w["text"]) for w in words], [key(t) for t in tokens], autojunk=False)
    for op, a0, a1, b0, b1 in matcher.get_opcodes():
        if op in ("equal", "replace") and a1 - a0 == b1 - b0:
            for i, j in zip(range(a0, a1), range(b0, b1)):
                words[i]["text"] = tokens[j]
    return words


# A cut lands just before its beat's first word; no shot is shorter than a readable glance.
SPEECH_LEAD_SECONDS = 0.12
MIN_SHOT_SECONDS = 2.2
MAX_SHOT_SECONDS = 4.8
MAX_CLIP_SPEEDUP = 1.25


def speech_frames(
    words: list[dict[str, Any]], beat_texts: list[str], total_seconds: float, fps: int = 30,
    longest: list[float] | None = None,
) -> list[int] | None:
    """Frame counts that cut to each beat's shot as its first word is spoken.

    The voice speeds up and slows down sentence by sentence, so equal-length shots drift:
    the melting pottery appeared over "Boudica watches". None when the voice cannot be aligned.
    `longest` caps each shot at what its generated clip can fill; a shot timed past that froze
    its last frame at the cut, so the cut moves off the word and a neighbour takes the time.
    """
    limits = [MAX_SHOT_SECONDS] * len(beat_texts)
    if longest and len(longest) == len(beat_texts):
        limits = [min(MAX_SHOT_SECONDS, max(MIN_SHOT_SECONDS, value)) for value in longest]
    if len(beat_texts) < 2 or not words:
        return None
    tokens: list[str] = []
    beat_starts: list[int] = []
    for text in beat_texts:
        beat_starts.append(len(tokens))
        tokens += text.split()

    def key(text: str) -> str:
        return re.sub(r"[^a-z0-9]", "", text.lower())

    heard: dict[int, int] = {}
    matcher = difflib.SequenceMatcher(None, [key(w["text"]) for w in words], [key(t) for t in tokens], autojunk=False)
    for op, a0, a1, b0, b1 in matcher.get_opcodes():
        if op in ("equal", "replace") and a1 - a0 == b1 - b0:
            heard.update(zip(range(b0, b1), range(a0, a1)))
    cuts = [0.0]
    for start in beat_starts[1:]:
        if start in heard:
            cuts.append(float(words[heard[start]]["start"]) - SPEECH_LEAD_SECONDS)
            continue
        before = [j for j in heard if j < start]
        if not before:
            return None
        cuts.append(float(words[heard[max(before)]]["end"]))
    cuts.append(float(total_seconds))
    for i in range(1, len(cuts) - 1):  # forward: keep the shot before within bounds
        cuts[i] = min(max(cuts[i], cuts[i - 1] + MIN_SHOT_SECONDS), cuts[i - 1] + limits[i - 1])
    for i in range(len(cuts) - 2, 0, -1):  # backward: keep the shot after within bounds
        cuts[i] = max(min(cuts[i], cuts[i + 1] - MIN_SHOT_SECONDS), cuts[i + 1] - limits[i])
    if any(not MIN_SHOT_SECONDS - 1e-6 <= b - a <= limit + 1e-6 for a, b, limit in zip(cuts, cuts[1:], limits)):
        # The clips cannot cover the voice together: time to speech alone (a short freeze).
        return speech_frames(words, beat_texts, total_seconds, fps) if longest else None
    marks = [round(cut * fps) for cut in cuts]
    return [b - a for a, b in zip(marks, marks[1:])]


def clip_capacities(manifest: ProjectManifest) -> list[float] | None:
    """Longest on-screen time each accepted clip fills without freezing its last frame.

    Assembly slows a clip by up to MAX_CLIP_STRETCH and borrows the next transition from it.
    None when any clip length is unknown (then timing follows the voice alone)."""
    capacities = []
    for index, shot in enumerate(manifest.shots):
        raw = (shot.validation or {}).get("duration")
        if not raw:
            return None
        transition = 0.0 if index == len(manifest.shots) - 1 else MAX_TRANSITION_SECONDS
        # Rounded down to a whole frame so the stretched clip never ends one frame short.
        capacities.append(int((float(raw) * MAX_CLIP_STRETCH - transition) * 30) / 30)
    return capacities


def fit_shots_to_speech(manifest: ProjectManifest, words: list[dict[str, Any]]) -> bool:
    """Retime one-beat-per-shot plans so each shot plays while its own sentence is spoken."""
    beats = [b for b in manifest.script.get("beats") or [] if isinstance(b, dict)]
    if len(beats) != len(manifest.shots):
        return False
    frames = speech_frames(words, [str(b.get("text") or "") for b in beats],
                           manifest.duration_seconds, manifest.fps, clip_capacities(manifest))
    if not frames:
        return False
    for shot, count in zip(manifest.shots, frames):
        shot.duration_frames = count
    return True


def spoken_words(
    heard: list[dict[str, Any]], beats: list[dict[str, Any]] | None, total_duration: float | None, script: str = "",
) -> list[dict[str, Any]]:
    """The script's own words at Whisper's timings (names spelled as written)."""
    if beats and total_duration:
        return script_word_timings(beats, heard, float(total_duration))
    return snap_to_script(heard, script) if script else heard


def opening_hook(manifest: ProjectManifest) -> str:
    """An optional headline over the first ~3 s (the script's title). Off by default: a title is not a
    hook; the hook is beat 1's own moment and line. LOCAL_VIDEO_HOOK_TITLE=1 turns it on.
    """
    if os.getenv("LOCAL_VIDEO_HOOK_TITLE", "0").strip() != "1":
        return ""
    return str(manifest.script.get("video_title") or "").strip()


def create_captions(
    narration: Path,
    output_dir: Path,
    export_srt: bool = True,
    word_highlight: bool = True,
    beats: list[dict[str, Any]] | None = None,
    total_duration: float | None = None,
    script: str = "",
    words: list[dict[str, Any]] | None = None,
    hook: str = "",
) -> tuple[Path | None, Path | None, list[dict[str, Any]]]:
    if words is None:
        words = spoken_words(transcribe_with_whisper(str(narration)), beats, total_duration, script)
    ass = Path(words_to_ass(words, str(output_dir / "captions.ass"), hook=hook)) if word_highlight else None
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

    spoken = str(manifest.script.get("spoken_script") or " ".join(
        str(beat.get("text") or "") for beat in manifest.script.get("beats") or []))
    words = None
    if narration_path:
        beats = manifest.script.get("beats") if isinstance(manifest.script.get("beats"), list) else None
        words = spoken_words(transcribe_with_whisper(str(narration_path)), beats,
                             manifest.duration_seconds, spoken)
        if fit_shots_to_speech(manifest, words):
            manifest.record("timeline_fitted_to_speech")
    _run(build_video_command(manifest, silent_video, config, upscale_clips(manifest, config)), 1800, "Video assembly")
    from . import sound
    try:
        designed = sound.render(manifest, ambience)
    except Exception as exc:                 # the video never fails on its sound bed
        log.warning("Designed sound unavailable (%s); silent ambience", exc)
        designed = False
    if not designed:
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
            words=words,
            hook=opening_hook(manifest),
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
