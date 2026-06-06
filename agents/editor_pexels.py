"""
Pexels-based editor: free stock footage instead of AI-generated video.
Reuses voice generation, subtitle burn, and stitching from editor_hailuo.
Only the clip-fetching step differs.
"""
import os
import re
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv
from config.paths import get_env_path, get_temp_dir

load_dotenv(get_env_path())

log = logging.getLogger("pipeline")

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

# Reuse all the helpers from editor_hailuo
from agents.editor_hailuo import (
    _remove_files,
    get_duration,
    generate_voiceover,
    stitch_clips_to_duration,
    merge_audio_video,
    transcribe_with_whisper,
    words_to_srt,
    burn_subtitles,
)


def search_pexels_videos(query: str, min_duration: int = 6, count: int = 1) -> list:
    """Pexels portrait search; only returns clips >= min_duration seconds."""
    if not PEXELS_API_KEY:
        raise RuntimeError("PEXELS_API_KEY is not configured")
    headers = {"Authorization": PEXELS_API_KEY}
    params = {
        "query": query,
        "orientation": "portrait",
        "size": "medium",
        "per_page": 15,  # fetch more so we can filter by duration
    }
    r = requests.get("https://api.pexels.com/videos/search",
                     headers=headers, params=params, timeout=15)
    if r.status_code != 200:
        log.warning(f"Pexels search failed for '{query}': HTTP {r.status_code}")
        return []

    videos = r.json().get("videos", [])
    urls = []

    # Sort by duration desc — prefer longer clips
    videos.sort(key=lambda v: -(v.get("duration") or 0))

    for v in videos:
        clip_dur = v.get("duration", 0)
        if clip_dur < min_duration:
            continue  # skip too-short clips

        files = sorted(v.get("video_files", []), key=lambda f: -(f.get("width") or 0))
        for f in files:
            w, h = f.get("width", 0), f.get("height", 0)
            if h > w and w >= 720:
                urls.append(f["link"])
                break
        if len(urls) >= count:
            break
    return urls[:count]



def build_pexels_queries(script: dict) -> list:
    """Read queries directly from the script — Claude already wrote them properly."""
    queries = script.get("pexels_queries", [])
    if not queries:
        # Fallback if script didn't include queries
        title = script.get("video_title", "")
        title_clean = re.sub(r"[^a-zA-Z\s]", " ", title.lower())
        words = [w for w in title_clean.split() if len(w) > 3]
        queries = [" ".join(words[:2]) or "abstract cinematic"] * 8
    return queries



def download_pexels_clip(url: str, clip_num: int) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(get_temp_dir(), f"pexel_{clip_num}_{ts}.mp4")
    r = requests.get(url, timeout=60, stream=True)
    if r.status_code != 200:
        raise RuntimeError(f"Pexels download failed: HTTP {r.status_code}")
    with open(path, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
    return path


def fetch_stock_footage(script: dict, num_clips: int, per_clip_duration: float = 6.0) -> list:
    """Pull num_clips clips from Pexels, each >= per_clip_duration seconds long."""
    log.info(f"\n[2/5] Fetching {num_clips} Pexels clips (min {per_clip_duration:.0f}s each)...\n")

    queries = build_pexels_queries(script)
    fallbacks = ["cinematic abstract", "slow motion nature", "atmospheric mood", "abstract texture"]

    paths = []
    used_urls = set()  # dedupe across queries

    for i in range(num_clips):
        primary_query = queries[i] if i < len(queries) else queries[-1]
        url = None

        # Try the primary query first with strict duration
        for query in [primary_query] + fallbacks:
            log.info(f"  Clip {i+1}: trying '{query}' (need {per_clip_duration:.0f}s+)")
            urls = search_pexels_videos(query, min_duration=int(per_clip_duration), count=3)

            # Find one we haven't used
            for u in urls:
                if u not in used_urls:
                    url = u
                    used_urls.add(u)
                    break

            if url:
                break

        if not url:
            # Last resort: any portrait clip, any duration
            log.info(f"    Last resort: any portrait clip")
            urls = search_pexels_videos(fallbacks[0], min_duration=3, count=5)
            for u in urls:
                if u not in used_urls:
                    url = u
                    used_urls.add(u)
                    break

        if not url:
            raise Exception(f"No suitable footage found for clip {i+1}")

        path = download_pexels_clip(url, i+1)
        actual_dur = get_duration(path)
        size_mb = os.path.getsize(path) / 1024 / 1024
        log.info(f"    Got {actual_dur:.1f}s clip ({size_mb:.1f} MB)")
        paths.append(path)

    return paths



def process_video(script: dict, voice: str = "energetic") -> str:
    """Pexels stock + ElevenLabs voice + word-by-word subtitles. Cost: ~$0."""
    audio_path = None
    clips = []
    stitched = None
    merged = None
    srt = None

    try:
        audio_path, audio_duration = generate_voiceover(script["spoken_script"], voice=voice)

        num_clips = max(6, int((audio_duration + 4) // 5))
        if num_clips > 8:
            num_clips = 8
        log.info(f"\nVoice = {audio_duration:.1f}s. Fetching {num_clips} Pexels clips.\n")

        target_duration = audio_duration + 0.5

        clips = fetch_stock_footage(script, num_clips=num_clips, per_clip_duration=target_duration / num_clips + 1.0)
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
    log.info("Pexels editor module loaded successfully.")
