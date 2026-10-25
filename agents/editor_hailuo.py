import os
import json
import time
import subprocess
import requests
import re
from datetime import datetime
from dotenv import load_dotenv
from config.paths import get_env_path, get_ffmpeg, get_ffprobe, get_temp_dir, CLAUDE_MODEL
import logging

load_dotenv(get_env_path())
log = logging.getLogger("pipeline")


def _tool_path(name: str) -> str:
    """Resolved ffmpeg/ffprobe path for modules that import the FFMPEG/FFPROBE constants
    (engine, beats, render); falls back to the bare name so import never fails."""
    try:
        return get_ffmpeg() if name == "ffmpeg" else get_ffprobe()
    except FileNotFoundError:
        return name


FFMPEG = _tool_path("ffmpeg")
FFPROBE = _tool_path("ffprobe")

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
FAL_API_KEY = os.getenv("FAL_API_KEY")

VOICES = {
    "energetic": "TX3LPaxmHKxFdv7VOQHJ",
    "mysterious": "IKne3meq5aSn9XLyUdCD",
    "storyteller": "JBFqnCBsd6RMkjVDRZzb",
}


# ------------------- WHISPER SINGLETON -------------------

_whisper_model = None


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    return _whisper_model


# ------------------- HELPERS -------------------

def get_scenes(script: dict) -> list:
    """Return the ordered list of scene prompts.

    Supports the beat schema (each beat's visual description), the connected
    `scenes` list, and the legacy fixed `scene_1..scene_6` schema.
    """
    beats = script.get("beats")
    if isinstance(beats, list) and beats:
        return [((b.get("visual") or {}).get("description") or b.get("text") or "").strip()
                for b in beats if isinstance(b, dict)]
    scenes = script.get("scenes")
    if isinstance(scenes, list) and scenes:
        return scenes
    legacy = [script[k] for k in sorted(script) if k.startswith("scene_") and script.get(k)]
    return legacy


def scene_prompt(script: dict, index: int) -> str:
    """Scene text with the shared visual_style appended, for cohesive output."""
    scenes = get_scenes(script)
    text = scenes[index]
    style = (script.get("visual_style") or "").strip()
    return f"{text}, {style}" if style else text


def _remove_files(paths) -> None:
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError as e:
                log.warning(f"Could not remove temporary file {path}: {e}")


def _run_process(cmd, timeout: int, cleanup_paths=()):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception:
        _remove_files(cleanup_paths)
        raise


def get_duration(file_path: str) -> float:
    cmd = [get_ffprobe(), "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", file_path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe duration failed for {file_path}: {r.stderr[-300:]}")
    return float(r.stdout.strip()) if r.stdout.strip() else 0.0


def get_dimensions(file_path: str) -> tuple:
    """Returns (width, height)."""
    cmd = [get_ffprobe(), "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=width,height",
           "-of", "csv=s=x:p=0", file_path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe dimensions failed for {file_path}: {r.stderr[-300:]}")
    dims = r.stdout.strip()
    if not dims:
        return (0, 0)
    w, h = map(int, dims.split("x"))
    return (w, h)


# ------------------- VOICE -------------------

# ------------------- ELEVENLABS KEY ROTATION -------------------
#
# Keys: ELEVENLABS_API_KEY, ELEVENLABS_API_KEY_2, _3, ... (any number). The current key is used
# until it runs out of credits, then the next one, wrapping around; the position persists across
# runs. Before each voiceover the key's remaining credits are checked so a script never fails
# half-way, and any quota / auth / rate-limit error falls through to the next key.
# Logs name the key slot (e.g. ELEVENLABS_API_KEY_2), never the key itself.

_ROTATION_FILE = os.path.join(get_temp_dir(), "elevenlabs_rotation.json")
_RETRYABLE = ("quota_exceeded", "invalid_api_key", "detected_unusual_activity", "too_many_concurrent_requests",
              "system_busy", "payment_required", "unusual_activity", "max_character_limit_exceeded")


def _elevenlabs_keys() -> list:
    """[(slot_name, key)] in rotation order, without blanks or duplicates."""
    names = ["ELEVENLABS_API_KEY"] + [f"ELEVENLABS_API_KEY_{i}" for i in range(2, 21)]
    out, seen = [], set()
    for n in names:
        k = (os.getenv(n) or "").strip()
        if k and k not in seen:
            out.append((n, k))
            seen.add(k)
    return out


def _rotation_start(n: int) -> int:
    try:
        with open(_ROTATION_FILE, encoding="utf-8") as f:
            return int(json.load(f).get("index", 0)) % max(n, 1)
    except (OSError, ValueError, json.JSONDecodeError):
        return 0


def _rotation_save(i: int):
    try:
        with open(_ROTATION_FILE, "w", encoding="utf-8") as f:
            json.dump({"index": i}, f)
    except OSError:
        pass


def _credits_left(key: str):
    """Remaining characters on this key's plan, or None if it can't be checked."""
    try:
        r = requests.get("https://api.elevenlabs.io/v1/user/subscription", headers={"xi-api-key": key}, timeout=15)
        if r.status_code != 200:
            return None
        d = r.json()
        return int(d.get("character_limit", 0)) - int(d.get("character_count", 0))
    except (requests.RequestException, ValueError):
        return None


def _tts_with_rotation(url: str, payload: dict, chars: int):
    keys = _elevenlabs_keys()
    if not keys:
        raise RuntimeError("No ElevenLabs key configured (ELEVENLABS_API_KEY, ELEVENLABS_API_KEY_2, ...)")
    start = _rotation_start(len(keys))
    order = [(start + k) % len(keys) for k in range(len(keys))]
    # Prefer, in rotation order, the first key that can cover the whole script.
    left = {i: _credits_left(keys[i][1]) for i in order}
    order = [i for i in order if left[i] is None or left[i] >= chars] + \
            [i for i in order if left[i] is not None and left[i] < chars]
    errors = []
    for i in order:
        name, key = keys[i]
        if left[i] is not None and left[i] < chars:
            errors.append(f"{name}: only {left[i]} credits left")
            continue
        headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": key}
        for attempt in range(2):
            r = requests.post(url, json=payload, headers=headers, timeout=60)
            if r.status_code == 429 and attempt == 0:          # busy: one short wait on the same key
                time.sleep(5)
                continue
            break
        if r.status_code == 200:
            if i != start:
                log.info(f"  ElevenLabs: switched to {name}")
            _rotation_save(i)
            remaining = f", {left[i] - chars} credits left" if left[i] is not None else ""
            log.info(f"  ElevenLabs key: {name}{remaining}")
            return r
        body = r.text[:300]
        if r.status_code in (401, 402, 403, 429) or any(s in body for s in _RETRYABLE):
            errors.append(f"{name}: {r.status_code} {body[:120]}")
            log.warning(f"  ElevenLabs {name} unusable ({r.status_code}); trying the next key")
            continue
        raise Exception(f"ElevenLabs failed ({name}): {r.status_code} {body}")
    raise Exception("All ElevenLabs keys are out of credits or unusable: " + " | ".join(errors))


def generate_voiceover(spoken_script: str, voice: str = "energetic") -> tuple:
    """ElevenLabs voiceover with expressive settings."""
    log.info(f"[1/5] Generating voiceover (ElevenLabs - {voice})...")
    if not _elevenlabs_keys():
        raise RuntimeError("ELEVENLABS_API_KEY is not configured")

    voice_id = VOICES.get(voice, VOICES["energetic"])
    payload = {
        "text": spoken_script,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.4,
            "similarity_boost": 0.75,
            "style": 0.6,
            "use_speaker_boost": True,
            "speed": float(os.getenv("VOICE_SPEED", "0.92")),   # a touch slower: easier to follow
        }
    }
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    r = _tts_with_rotation(url, payload, len(spoken_script))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(get_temp_dir(), f"voiceover_{ts}.mp3")
    with open(path, "wb") as f:
        f.write(r.content)

    duration = get_duration(path)
    log.info(f"  Voiceover: {duration:.1f}s, {len(r.content)/1024:.0f} KB")
    return path, duration


# ------------------- VIDEO GENERATION (Hailuo 02) -------------------

def generate_single_clip(prompt: str, clip_number: int, total_clips: int) -> str:
    """Generate one 6-second clip via Hailuo 02 Standard."""
    import fal_client
    if not FAL_API_KEY:
        raise RuntimeError("FAL_API_KEY is not configured")
    os.environ["FAL_KEY"] = FAL_API_KEY

    log.info(f"[{clip_number}/{total_clips}] Submitting to Hailuo 02...")

    handler = fal_client.submit(
        "fal-ai/minimax/hailuo-02/standard/text-to-video",
        arguments={
            "prompt": prompt,
            "duration": "6",
            "prompt_optimizer": True,
            "resolution": "768P",
        }
    )

    elapsed = 0
    last_status = None
    while elapsed < 360:
        time.sleep(10)
        elapsed += 10
        status = fal_client.status(
            "fal-ai/minimax/hailuo-02/standard/text-to-video",
            handler.request_id
        )
        name = type(status).__name__
        if name != last_status and elapsed % 30 == 0:
            log.info(f"  Clip {clip_number}: {name} ({elapsed}s)")
            last_status = name
        if "Completed" in name:
            break
        if "Failed" in name or "Error" in name or "Cancelled" in name:
            raise RuntimeError(f"Hailuo clip {clip_number} ended with status {name}")

    if elapsed >= 360:
        raise TimeoutError(f"Hailuo clip generation timed out after {elapsed}s (clip {clip_number})")

    result = fal_client.result(
        "fal-ai/minimax/hailuo-02/standard/text-to-video",
        handler.request_id
    )

    video_url = result.get("video", {}).get("url") if isinstance(result.get("video"), dict) else None
    if not video_url:
        raise Exception(f"No video URL: {result}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(get_temp_dir(), f"clip{clip_number}_{ts}.mp4")
    dl = requests.get(video_url, timeout=120, stream=True)
    if dl.status_code != 200:
        raise RuntimeError(
            f"Hailuo clip download failed: HTTP {dl.status_code} {dl.text[:200]}"
        )
    with open(path, "wb") as f:
        for chunk in dl.iter_content(8192):
            f.write(chunk)

    size_mb = os.path.getsize(path) / 1024 / 1024
    log.info(f"  Clip {clip_number}: OK ({size_mb:.1f} MB)")
    return path


def generate_all_clips(script: dict, num_clips: int) -> list:
    """Sequential clip generation. Hailuo costs ~$0.27/clip."""
    num_clips = min(num_clips, len(get_scenes(script)))

    log.info(f"\n[2/5] Generating {num_clips} clips via Hailuo 02 (~${0.27*num_clips:.2f} total)...\n")
    clips = []
    for i in range(num_clips):
        prompt = scene_prompt(script, i)
        path = generate_single_clip(prompt, clip_number=i + 1, total_clips=num_clips)
        clips.append(path)
    log.info(f"\nAll {num_clips} clips ready.\n")
    return clips


# ------------------- VERTICAL CONVERSION (Smart Hybrid) -------------------

def detect_crop(input_path: str):
    """FFmpeg crop filter that removes black bars baked into a clip, or None.

    Some stock/archival clips are letterboxed or pillarboxed inside their frame;
    filling 9:16 without removing the bars leaves black bands on screen.
    """
    cmd = [FFMPEG, "-ss", "1", "-i", input_path, "-t", "2",
           "-vf", "cropdetect=limit=24:round=2:reset=0", "-f", "null", "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        w0, h0 = get_dimensions(input_path)
    except Exception:
        return None
    found = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", r.stderr)
    if not found or not w0 or not h0:
        return None
    w, h, x, y = map(int, found[-1])
    # Only crop real bars (>=4% of the frame), never a near-blank/dark clip.
    if w < w0 * 0.4 or h < h0 * 0.4 or w * h > w0 * h0 * 0.96:
        return None
    return f"crop={w}:{h}:{x}:{y}"


def landscape_to_vertical(input_path: str, output_path: str, duration: float, loop: bool = False,
                          overlay_path: str = None, crop: str = None) -> str:
    """Convert landscape clip to 9:16 vertical filling the FULL frame.

    Strategy: scale source to FILL 1080x1920 with center-crop.
    This loses some side detail but produces a full-screen video like real TikTok content.
    Subjects centered in frame (which is what Hailuo defaults to) translate well.

    If loop=True, the source is looped (-stream_loop) and the OUTPUT is capped to
    exactly `duration` seconds — used for short local clips that must fill a longer
    narration slot.

    overlay_path: optional full-frame transparent PNG (e.g. an on-screen label)
    composited on top of the vertical frame. crop: optional pre-crop filter
    (from detect_crop) applied before filling the frame.
    """
    fill = (f"{crop}," if crop else "") + "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    if overlay_path:
        cmd = [FFMPEG, "-y"] + (["-stream_loop", "-1"] if loop else []) + [
            "-i", input_path, "-i", overlay_path, "-t", str(duration),
            "-filter_complex", f"[0:v]{fill}[v];[v][1:v]overlay=0:0",
            "-r", "30", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-an", output_path
        ]
    elif loop:
        cmd = [
            FFMPEG, "-y", "-stream_loop", "-1", "-i", input_path, "-t", str(duration),
            "-vf", fill,
            "-r", "30", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-an", output_path
        ]
    else:
        cmd = [
            FFMPEG, "-y", "-t", str(duration), "-i", input_path,
            "-vf", fill,
            "-r", "30", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-an", output_path
        ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise Exception(f"Vertical conversion failed: {r.stderr[-300:]}")
    return output_path



def stitch_clips_to_duration(clip_paths: list, target_duration: float, loop_to_fill: bool = False) -> str:
    """Convert each landscape clip to vertical, trim, and concatenate.
    GUARANTEES total duration covers target by looping last clip if needed.

    loop_to_fill=True makes EACH clip loop to exactly its per-clip slot. Use this
    for short local clips (e.g. ~2s Wan clips) so every narration beat is covered by
    its own footage instead of one clip being looped to fill a large tail gap.
    """
    log.info(f"\n[3/5] Converting to vertical 9:16 + stitching to {target_duration:.1f}s...")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not clip_paths:
        raise ValueError("At least one clip is required for stitching")

    per_clip = target_duration / len(clip_paths)
    log.info(f"  Each clip: {per_clip:.1f}s{' (loop-filled)' if loop_to_fill else ''}")

    # Validate each clip can supply per_clip seconds
    normalized = []
    total_supplied = 0.0

    try:
        for i, clip in enumerate(clip_paths):
            norm = os.path.join(get_temp_dir(), f"norm_{i}_{ts}.mp4")
            normalized.append(norm)
            actual_dur = get_duration(clip)

            if loop_to_fill:
                # Loop each clip to exactly fill its slot (short clips -> full coverage)
                log.info(f"  Clip {i+1}/{len(clip_paths)}: {actual_dur:.1f}s -> {per_clip:.1f}s (looped)")
                landscape_to_vertical(clip, norm, per_clip, loop=True)
            else:
                # If clip is too short, use what's there (will be padded by next step)
                trim = min(per_clip + 0.2, actual_dur)
                if trim < per_clip - 0.5:
                    log.warning(f"  WARN: Clip {i+1} only {actual_dur:.1f}s, need {per_clip:.1f}s")
                log.info(f"  Clip {i+1}/{len(clip_paths)}: {actual_dur:.1f}s -> {trim:.1f}s")
                landscape_to_vertical(clip, norm, trim)
            actual_norm = get_duration(norm)
            total_supplied += actual_norm
    except Exception:
        _remove_files(normalized)
        raise

    log.info(f"  Total supplied: {total_supplied:.1f}s (target {target_duration:.1f}s)")

    # If total is less than target, loop last clip to fill the gap
    if total_supplied < target_duration - 0.5:
        gap = target_duration - total_supplied + 0.3
        log.info(f"  Gap: {gap:.1f}s - looping last clip")
        last_loop = os.path.join(get_temp_dir(), f"loop_{ts}.mp4")
        cmd = [
            get_ffmpeg(), "-y", "-stream_loop", "-1", "-i", normalized[-1],
            "-t", str(gap),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-an", last_loop
        ]
        r = _run_process(
            cmd,
            timeout=60,
            cleanup_paths=normalized + [last_loop],
        )
        if r.returncode != 0:
            _remove_files(normalized + [last_loop])
            raise RuntimeError(f"Clip loop failed: {r.stderr[-300:]}")
        normalized.append(last_loop)

    try:
        return concat_clips(normalized, target_duration)
    finally:
        _remove_files(normalized)


def concat_clips(clip_paths: list, target_duration: float) -> str:
    """Concatenate already-vertical 1080x1920 clips and cap at target_duration."""
    if not clip_paths:
        raise ValueError("At least one clip is required for stitching")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    concat_file = os.path.join(get_temp_dir(), f"concat_{ts}.txt")
    stitched_path = os.path.join(get_temp_dir(), f"stitched_{ts}.mp4")

    try:
        with open(concat_file, "w", encoding="utf-8") as f:
            for p in clip_paths:
                escaped_path = p.replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
    except Exception:
        _remove_files([concat_file, stitched_path])
        raise

    log.info(f"  Concatenating {len(clip_paths)} clips...")
    cmd = [
        get_ffmpeg(), "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
        "-t", str(target_duration),
        "-c:v", "libx264", "-preset", "fast", "-crf", "21",
        "-r", "30", "-pix_fmt", "yuv420p", "-movflags", "+faststart", stitched_path
    ]
    r = _run_process(cmd, timeout=240, cleanup_paths=[concat_file, stitched_path])
    if r.returncode != 0:
        _remove_files([concat_file, stitched_path])
        raise RuntimeError(f"Stitch failed: {r.stderr[-300:]}")

    try:
        final_dur = get_duration(stitched_path)
    except Exception:
        _remove_files([concat_file, stitched_path])
        raise
    _remove_files([concat_file])
    log.info(f"  Stitched: {final_dur:.1f}s")
    return stitched_path



def merge_audio_video(video_path: str, audio_path: str) -> str:
    log.info("\n[4/5] Merging audio onto video...")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    merged = os.path.join(get_temp_dir(), f"merged_{ts}.mp4")

    cmd = [
        get_ffmpeg(), "-y",
        "-i", video_path, "-i", audio_path,
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-map", "0:v:0", "-map", "1:a:0",
        "-movflags", "+faststart", merged
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise Exception(f"Audio merge failed: {r.stderr[-300:]}")

    log.info(f"  Merged: {get_duration(merged):.1f}s")
    return merged


# ------------------- TRANSCRIPTION + SUBTITLES -------------------

def transcribe_with_whisper(audio_path: str) -> list:
    log.info("\n[5/5] Transcribing audio + generating word-level subtitles...")
    model = _get_whisper_model()

    segments, _ = model.transcribe(
        audio_path,
        word_timestamps=True,
        language="en",
        vad_filter=False
    )

    words = []
    for segment in segments:
        for word in segment.words:
            words.append({
                "text": word.word.strip(),
                "start": word.start,
                "end": word.end
            })

    log.info(f"  Transcribed: {len(words)} words")
    return words


def fmt_ts(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    ms = int((s % 1) * 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


def words_to_srt(words: list, srt_path: str):
    """Single-word subtitles synced exactly to voice."""
    lines = []
    idx = 1

    for i, word in enumerate(words):
        text = word["text"].strip().upper().lstrip(".,!?;:").rstrip(",;:")
        if not text:
            continue

        start = word["start"]
        if i + 1 < len(words):
            end = words[i + 1]["start"] - 0.02
        else:
            end = word["end"] + 0.1

        if end - start < 0.08:
            end = start + 0.08

        lines.append(str(idx))
        lines.append(f"{fmt_ts(start)} --> {fmt_ts(end)}")
        lines.append(text)
        lines.append("")
        idx += 1

    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def srt_time_to_seconds(t: str) -> float:
    t = t.strip().replace(",", ".")
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def burn_subtitles(video_path: str, srt_path: str) -> str:
    """Burn word-by-word yellow subtitles using the libass subtitles filter.

    Uses cwd=temp_dir and a local filename so the filter string never contains
    a Windows drive-letter colon — which breaks FFmpeg filter parsing.
    """
    log.info("  Burning subtitles...")
    import shutil

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_dir = get_temp_dir()
    final = os.path.join(temp_dir, f"final_{ts}.mp4")

    # Copy SRT next to the output so the filter can reference it by filename only.
    ext = os.path.splitext(srt_path)[1].lower() or ".srt"
    local_srt = f"subs_{ts}{ext}"
    local_srt_path = os.path.join(temp_dir, local_srt)
    shutil.copy(srt_path, local_srt_path)

    # ASS colour format: &HAABBGGRR  — yellow = R=FF, G=FF, B=00 → &H0000FFFF
    # libass scales FontSize against its 288px reference, then up to the video
    # height (~6.7x at 1920) — so FontSize=14 renders ~93px (~5% of frame),
    # large enough to read but small enough that long words never overflow.
    style = (
        "FontName=Arial Bold,"
        "FontSize=14,"
        "PrimaryColour=&H0000FFFF,"
        "OutlineColour=&H00000000,"
        "BorderStyle=1,"
        "Outline=2,"
        "Shadow=0,"
        "Alignment=2,"
        "MarginV=60"
    )
    # .ass files carry their own styling/animation (agents/captions.py).
    vf = f"subtitles={local_srt}" if ext == ".ass" else f"subtitles={local_srt}:force_style='{style}'"

    cmd = [
        get_ffmpeg(), "-y", "-i", video_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "copy", "-movflags", "+faststart", final
    ]

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                           cwd=temp_dir)
        if r.returncode != 0:
            log.error("  subtitle burn failed:")
            log.error(r.stderr[-1500:])
            raise RuntimeError("Subtitle burn failed")
    finally:
        _remove_files([local_srt_path])

    mb = os.path.getsize(final) / 1024 / 1024
    final_duration = get_duration(final)
    log.info(f"  Final: {final} ({mb:.1f} MB, {final_duration:.1f}s)")
    return final


# ------------------- MAIN PIPELINE -------------------

def process_video(script: dict, voice: str = "energetic") -> str:
    """Hailuo 02 video + ElevenLabs voice + word-by-word subtitles."""
    from agents.beats import get_beats
    if get_beats(script):  # beat scripts: visuals timed to the narration
        from agents.editor_beats import process_video as process_beats
        return process_beats(script, voice=voice, footage="hailuo")

    audio_path = None
    clips = []
    stitched = None
    merged = None
    srt = None

    try:
        audio_path, audio_duration = generate_voiceover(script["spoken_script"], voice=voice)

        num_clips = max(5, int((audio_duration + 5) // 6))  # Hailuo clips are 6s
        if num_clips > 6:
            num_clips = 6
        log.info(f"\nVoice = {audio_duration:.1f}s. Generating {num_clips} Hailuo clips.\n")

        clips = generate_all_clips(script, num_clips=num_clips)

        target_duration = audio_duration + 0.5
        stitched = stitch_clips_to_duration(clips, target_duration=target_duration)

        merged = merge_audio_video(stitched, audio_path)

        words = transcribe_with_whisper(audio_path)
        srt = merged.replace(".mp4", ".srt")
        words_to_srt(words, srt)
        final = burn_subtitles(merged, srt)

        return final
    finally:
        _remove_files(clips + [stitched, audio_path, merged, srt])


if __name__ == "__main__":
    log.info("Editor module loaded successfully (Hailuo 02 + ElevenLabs + drawtext subs).")
