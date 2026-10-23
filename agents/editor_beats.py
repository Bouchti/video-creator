"""
Beat editor: every visual is chosen for, and timed to, the exact words being spoken.

Flow: voiceover → Whisper word timings → align each beat to its words → build
each beat's visual for exactly its slot → concatenate → audio → subtitles.

Per beat, by visual kind (first that succeeds wins):
  scene    → local Flux image (Pixar-style 3D) animated in 2.5D (the default, free)
  diagram  → diagram engine (exact, free)
  photo    → Wikimedia/Wikipedia photo (vision-checked) → footage → text card
  footage  → footage provider (vision-checked) → photo → text card

Footage providers (the --source flag):
  pexels   free stock/archival sources (default)
  comfy    local AI video (free, slow)
  hailuo   paid cloud AI video (opt-in only)

A text card (key phrase on the brand background) is the last resort, so a beat
never falls back to an unrelated "cinematic abstract" clip.
"""
import os
import logging
import subprocess
from datetime import datetime

import requests

from config.paths import get_temp_dir
from agents.editor_pexels import _UA
from agents.beats import (
    FPS, get_beats, get_visual, align_beats, split_frames, even_split, script_word_timings,
)
from agents.editor_hailuo import (
    FFMPEG,
    _remove_files,
    get_duration,
    generate_voiceover,
    detect_crop,
    landscape_to_vertical,
    concat_clips,
    merge_audio_video,
    transcribe_with_whisper,
    burn_subtitles,
)

log = logging.getLogger("pipeline")

FOOTAGE_PROVIDERS = ("pexels", "comfy", "hailuo")
STOCK_CANDIDATES = 6     # thumbnails shown to the vision check per beat


class _Run:
    """Per-video state: temp files, used media, credits, counters."""

    def __init__(self, script: dict, footage: str):
        self.script = script
        self.footage = footage
        self.ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.temp = []
        self.used_urls = set()
        self.credits = []
        self.counter = 0
        self.ai_done = 0
        self.ai_total = 0
        self.images = {}          # id(beat) -> generated scene image
        self.scene_count = 0

    def path(self, stem: str, ext: str) -> str:
        self.counter += 1
        p = os.path.join(get_temp_dir(), f"{stem}_{self.ts}_{self.counter:03d}.{ext}")
        self.temp.append(p)
        return p


# ------------------- CANDIDATE PREVIEWS + VISION -------------------

def _fetch_preview(run: _Run, candidate: dict):
    """Local JPEG preview of a stock/photo candidate, or None."""
    out = run.path("thumb", "jpg")
    thumb = candidate.get("thumb")
    try:
        if thumb:
            r = requests.get(thumb, headers=_UA, timeout=20)
            if r.status_code == 200 and r.content:
                with open(out, "wb") as f:
                    f.write(r.content)
                return out
        if candidate.get("url", "").lower().split("?")[0].endswith((".jpg", ".jpeg", ".png", ".webp")):
            return None
        # No thumbnail: grab one frame straight from the remote video.
        r = subprocess.run([FFMPEG, "-y", "-ss", "1", "-i", candidate["url"], "-frames:v", "1",
                            "-vf", "scale=480:-2", out], capture_output=True, timeout=45)
        return out if r.returncode == 0 and os.path.exists(out) else None
    except Exception:
        return None


def _vision_filter(run: _Run, beat: dict, candidates: list) -> list:
    """Keep only candidates whose preview matches the beat, best first."""
    from agents.vision import vision_enabled, rank_images
    if not candidates or not vision_enabled():
        return candidates
    previews = [(c, _fetch_preview(run, c)) for c in candidates]
    previews = [(c, p) for c, p in previews if p]
    if not previews:
        return []
    v = get_visual(beat)
    ranked = rank_images(v.get("description", ""), beat.get("text", ""), [p for _, p in previews])
    if ranked is None:  # check unavailable → trust search order
        return [c for c, _ in previews]
    log.info(f"    Vision: {len(ranked)}/{len(previews)} candidates match")
    return [previews[i][0] for i in ranked]


# ------------------- VISUAL BUILDERS -------------------
# Each returns a list of normalized 1080x1920 clip paths whose frame counts sum
# to `frames`, or [] when it has nothing on-topic to offer.

def _build_diagram(run: _Run, beat: dict, frames: int) -> list:
    from agents.diagram import render_diagram
    v = get_visual(beat)
    log.info(f"    Diagram: {v.get('template')}")
    return [render_diagram(v, frames, run.path("diagram", "mp4"))]


def _build_card(run: _Run, beat: dict, frames: int) -> list:
    from agents.diagram import render_diagram
    v = get_visual(beat)
    text = v.get("on_screen_text") or beat.get("text", "")
    log.info("    Text card")
    return [render_diagram({"template": "key_phrase", "text": text}, frames, run.path("card", "mp4"))]


def _build_photo(run: _Run, beat: dict, frames: int) -> list:
    from agents.photos import search_photos, download_image, render_photo
    v = get_visual(beat)
    candidates = [c for c in search_photos(v.get("queries") or [v.get("description", "")])
                  if c["url"] not in run.used_urls]
    for c in _vision_filter(run, beat, candidates):
        try:
            img = download_image(c["url"], run.path("photo", "img"))
            out = render_photo(img, frames, run.path("photo", "mp4"),
                               caption=v.get("on_screen_text"), drift=1 if run.counter % 2 else -1)
        except Exception as e:
            log.warning(f"    Photo unusable ({e}); trying next")
            continue
        run.used_urls.add(c["url"])
        run.credits.append(c["credit"])
        log.info(f"    Photo: {c['title']}")
        return [out]
    return []


def _normalize(run: _Run, clip: str, frames: int, caption: str = None) -> str:
    overlay = None
    if caption:
        from agents.render import text_overlay_png
        overlay = text_overlay_png(caption, run.path("label", "png"))
    out = run.path("shot", "mp4")
    crop = detect_crop(clip)
    if crop:
        log.info(f"    Removing baked-in black bars ({crop})")
    landscape_to_vertical(clip, out, frames / FPS, loop=True, overlay_path=overlay, crop=crop)
    return out


def _build_stock(run: _Run, beat: dict, frames: int) -> list:
    from agents.editor_pexels import search_stock_videos, download_clip
    v = get_visual(beat)
    parts = split_frames(frames)
    candidates, seen = [], set(run.used_urls)
    for q in v.get("queries") or []:
        for c in search_stock_videos(str(q), min_duration=3, count=3):
            if c["url"] not in seen:
                seen.add(c["url"])
                candidates.append(c)
        if len(candidates) >= max(STOCK_CANDIDATES, len(parts) + 2):
            break
    matches = _vision_filter(run, beat, candidates[:STOCK_CANDIDATES])

    clips = []
    for c in matches:
        if len(clips) == len(parts):
            break
        try:
            path = download_clip(c["url"], run.counter + 1)
            run.temp.append(path)
            clips.append(path)
            run.used_urls.add(c["url"])
            log.info(f"    Footage [{c['source']}] {get_duration(path):.1f}s")
        except Exception as e:
            log.warning(f"    Clip download failed ({e}); trying next")
    if not clips:
        return []
    # Fewer matching clips than planned shots → fewer, longer shots (never filler).
    parts = even_split(frames, len(clips))
    caption = v.get("on_screen_text")
    return [_normalize(run, clip, n, caption if i == 0 else None)
            for i, (clip, n) in enumerate(zip(clips, parts))]


def _build_ai_footage(run: _Run, beat: dict, frames: int) -> list:
    """One generated clip per beat (comfy = local, hailuo = paid), looped to fit."""
    v = get_visual(beat)
    style = (run.script.get("visual_style") or "").strip()
    prompt = f"{v.get('description', '')}, {style}" if style else v.get("description", "")
    run.ai_done += 1
    if run.footage == "comfy":
        from agents.editor_comfy import generate_single_clip
    else:
        from agents.editor_hailuo import generate_single_clip
    clip = generate_single_clip(prompt, clip_number=run.ai_done, total_clips=run.ai_total)
    run.temp.append(clip)
    return [_normalize(run, clip, frames, v.get("on_screen_text"))]


def _build_footage(run: _Run, beat: dict, frames: int) -> list:
    return _build_stock(run, beat, frames) if run.footage == "pexels" else _build_ai_footage(run, beat, frames)


def _generate_scene_images(run: _Run, beats: list) -> None:
    """Render every scene still up front — before any paid step (voiceover), so a
    ComfyUI problem fails fast and costs nothing."""
    import random
    from agents.image_gen import generate_image, styled_prompt
    scenes = [b for b in beats if get_visual(b).get("kind") == "scene"]
    if not scenes:
        return
    characters = run.script.get("characters") or []
    base_seed = random.randint(0, 2**31 - 1000)
    log.info(f"\n[1/5] Generating {len(scenes)} scene images locally (Flux)...\n")
    for n, beat in enumerate(scenes, start=1):
        prompt = styled_prompt(get_visual(beat).get("description", ""), characters)
        run.images[id(beat)] = generate_image(prompt, base_seed + n, run.path("scene", "png"),
                                              label=f"{n}/{len(scenes)}")


def _build_scene(run: _Run, beat: dict, frames: int) -> list:
    from agents.animate import CAMERA_MOVES, render_scene
    v = get_visual(beat)
    image = run.images.get(id(beat))
    if not image:
        raise RuntimeError("scene image was not generated")
    run.scene_count += 1
    camera = v.get("camera")
    if camera not in CAMERA_MOVES:  # vary moves when the script didn't pick one
        camera = CAMERA_MOVES[run.scene_count % len(CAMERA_MOVES)]
    return [render_scene(image, frames, run.path("scene", "mp4"), camera=camera,
                         overlay=v.get("overlay"))]


_BUILDERS = {"diagram": _build_diagram, "photo": _build_photo,
             "footage": _build_footage, "card": _build_card, "scene": _build_scene}
_ORDER = {"scene": ["scene"],
          "diagram": ["diagram", "card"],
          "photo": ["photo", "footage", "card"],
          "footage": ["footage", "photo", "card"]}


def build_beat(run: _Run, beat: dict, frames: int) -> list:
    kind = get_visual(beat).get("kind", "footage")
    for builder in _ORDER.get(kind, _ORDER["footage"]):
        # AI-video fallbacks for photo beats would cost money/time for a weaker
        # match; only footage beats use the AI provider.
        if builder == "footage" and kind != "footage" and run.footage != "pexels":
            continue
        try:
            shots = _BUILDERS[builder](run, beat, frames)
        except Exception as e:
            if builder == "scene" or (builder == "footage" and run.footage != "pexels"):
                raise  # local/cloud generator down: fail loudly, don't fill with cards
            log.warning(f"    {builder} failed: {e}")
            shots = []
        if shots:
            return shots
    raise RuntimeError("No visual could be built for beat (text card failed)")


# ------------------- MAIN PIPELINE -------------------

def process_video(script: dict, voice: str = "energetic", footage: str = "pexels") -> str:
    """Beat-timed video: each visual appears exactly while its words are spoken."""
    if footage not in FOOTAGE_PROVIDERS:
        raise ValueError(f"Unknown footage provider: {footage}")
    beats = get_beats(script)
    if not beats:
        raise ValueError("Script has no beats")

    run = _Run(script, footage)
    run.ai_total = sum(1 for b in beats if get_visual(b).get("kind", "footage") == "footage")
    audio_path = stitched = merged = srt = None
    shots = []

    try:
        _generate_scene_images(run, beats)

        audio_path, audio_duration = generate_voiceover(script["spoken_script"], voice=voice)
        words = transcribe_with_whisper(audio_path)
        target_duration = audio_duration + 0.5
        slots = align_beats(beats, words, target_duration)

        kinds = [get_visual(b).get("kind", "footage") for b in beats]
        log.info(f"\n[2/5] Building {len(beats)} beat visuals ({kinds.count('scene')} animated scene, "
                 f"{kinds.count('footage')} footage via {footage}, {kinds.count('photo')} photo, "
                 f"{kinds.count('diagram')} diagram)\n")
        for n, (beat, slot) in enumerate(zip(beats, slots), start=1):
            log.info(f"  Beat {n}/{len(beats)} [{slot['start']:.1f}-{slot['end']:.1f}s] "
                     f"{kinds[n - 1]}: {beat.get('text', '')[:70]}")
            shots.extend(build_beat(run, beat, slot["frames"]))

        log.info(f"\n[3/5] Assembling {len(shots)} shots to {target_duration:.1f}s...")
        stitched = concat_clips(shots, target_duration)

        # Sound design: whoosh on every cut, pop when an overlay sticker appears.
        from agents.audio_fx import build_fx_track, mix_audio
        cuts = [s["start"] for s in slots[1:]]
        pops = [s["start"] + 0.18 for b, s in zip(beats, slots) if get_visual(b).get("overlay")]
        fx = build_fx_track(target_duration, cuts, pops, run.path("fx", "wav"))
        mixed = mix_audio(audio_path, fx, run.path("mix", "m4a"), target_duration)
        merged = merge_audio_video(stitched, mixed)

        # Captions spell the SCRIPT's words (Whisper only supplies the timing).
        from agents.captions import words_to_ass
        srt = merged.replace(".mp4", ".ass")
        words_to_ass(script_word_timings(beats, words, target_duration), srt)
        final = burn_subtitles(merged, srt)

        script["credits"] = run.credits
        return final
    finally:
        _remove_files(run.temp + [stitched, audio_path, merged, srt])
