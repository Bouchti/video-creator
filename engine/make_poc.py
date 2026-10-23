"""
Phase 0 production driver (runs in the project venv):
voiceover → word timings → Blender render timed to the words → overlays,
sound design, captions → output/poc_pool.mp4

  python -m engine.make_poc [--voice energetic] [--reuse-voice]
"""
import argparse
import glob
import json
import logging
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402

from config.paths import PROJECT_ROOT, get_output_dir  # noqa: E402
from agents.beats import align_beats, script_word_timings, FPS  # noqa: E402
from agents.editor_hailuo import (FFMPEG, generate_voiceover, get_duration,  # noqa: E402
                                  transcribe_with_whisper, merge_audio_video, burn_subtitles)
from agents.audio_fx import build_fx_track, mix_audio  # noqa: E402
from agents.captions import words_to_ass  # noqa: E402
from agents.animate import _draw_overlay  # noqa: E402

log = logging.getLogger("pipeline")
BLENDER = os.getenv("BLENDER_EXE", r"C:\blender-5.2.3-windows-x64\blender.exe")

BEATS = [
    {"text": "Every backyard pool starts with a plan."},
    {"text": "First, Max marks the shape with stakes and string."},
    {"text": "Then an excavator digs a hole almost two meters deep.",
     "overlay": {"type": "stat", "value": "2 m", "text": "deep"}},
    {"text": "A cage of steel rebar makes it strong."},
    {"text": "Sprayed concrete turns it into a solid shell."},
    {"text": "Add tiles, fill it with water, and dive in!"},
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="energetic")
    ap.add_argument("--reuse-voice", action="store_true", help="reuse work/voice.mp3 if present")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    work = os.path.join(PROJECT_ROOT, "output", "poc_work")
    os.makedirs(work, exist_ok=True)
    voice_path = os.path.join(work, "voice.mp3")
    narration = " ".join(b["text"] for b in BEATS)

    if args.reuse_voice and os.path.exists(voice_path):
        duration = get_duration(voice_path)
    else:
        tmp, duration = generate_voiceover(narration, voice=args.voice)
        shutil.move(tmp, voice_path)
    words = transcribe_with_whisper(voice_path)
    total = duration + 0.6
    slots = align_beats(BEATS, words, total)
    total_frames = sum(s["frames"] for s in slots)
    f, beats = 0, []
    for s in slots:
        beats.append({"start": f, "end": f + s["frames"] - 1})
        f += s["frames"]
    timings_path = os.path.join(work, "timings.json")
    with open(timings_path, "w", encoding="utf-8") as fh:
        json.dump({"fps": FPS, "total_frames": total_frames, "beats": beats}, fh)
    log.info(f"Voice {duration:.1f}s → {total_frames} frames; beats: {[(b['start'], b['end']) for b in beats]}")

    # ---- render in Blender ----
    frames_dir = os.path.join(work, "frames")
    shutil.rmtree(frames_dir, ignore_errors=True)
    log.info("Rendering in Blender (this takes a while)...")
    r = subprocess.run([BLENDER, "--background", "--factory-startup", "--python",
                        os.path.join(PROJECT_ROOT, "engine", "poc_pool.py"), "--", timings_path, work],
                       capture_output=True, text=True)
    if "DONE" not in r.stdout:
        raise RuntimeError(f"Blender render failed:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    frames = sorted(glob.glob(os.path.join(frames_dir, "f_*.png")))
    log.info(f"Rendered {len(frames)} frames")

    # ---- overlays (stickers) on their beats ----
    for beat, span in zip(BEATS, beats):
        if not beat.get("overlay"):
            continue
        for i in range(span["start"], min(span["end"] + 1, len(frames))):
            img = Image.open(frames[i]).convert("RGB")
            _draw_overlay(img, beat["overlay"], (i - span["start"]) / FPS).save(frames[i])

    video = os.path.join(work, "video.mp4")
    subprocess.run([FFMPEG, "-y", "-framerate", str(FPS), "-i", os.path.join(frames_dir, "f_%04d.png"),
                    "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", video],
                   check=True, capture_output=True)

    # ---- sound + captions ----
    cuts = [b["start"] / FPS for b in beats[1:]]
    pops = [s["start"] / FPS + 0.18 for b, s in zip(BEATS, beats) if b.get("overlay")]
    fx = build_fx_track(total, cuts, pops, os.path.join(work, "fx.wav"))
    mixed = mix_audio(voice_path, fx, os.path.join(work, "mix.m4a"), total)
    merged = merge_audio_video(video, mixed)
    ass = os.path.join(work, "captions.ass")
    words_to_ass(script_word_timings(BEATS, words, total), ass)
    final = burn_subtitles(merged, ass)
    out = os.path.join(get_output_dir(), "poc_pool.mp4")
    shutil.move(final, out)
    os.remove(merged)
    log.info(f"\nPHASE 0 VIDEO: {out} ({get_duration(out):.1f}s)")


if __name__ == "__main__":
    main()
