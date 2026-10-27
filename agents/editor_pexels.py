"""
Stock-footage editor: free real video from MULTIPLE free sources instead of
AI-generated video. Reuses voice generation, subtitle burn, and stitching from
the shared media helpers. Only the clip-fetching step is stock-specific.

Sources (queried in priority order; key-gated ones auto-skip if their key is
missing, keyless ones always run):
  - pexels     (PEXELS_API_KEY)   general b-roll
  - pixabay    (PIXABAY_API_KEY)  general b-roll
  - coverr     (COVERR_API_KEY)   cinematic b-roll
  - nasa       (keyless)          space / earth / science
  - archive    (keyless)          Internet Archive — historical / public-domain
  - wikimedia  (keyless)          Wikimedia Commons — historical / educational

Order is configurable via the STOCK_SOURCES env var (comma-separated). To favour
on-topic historical footage over generic stock, put archive/wikimedia first.
"""
import os
import re
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv
from config.paths import get_env_path, get_temp_dir, get_user_agent

load_dotenv(get_env_path())

log = logging.getLogger("pipeline")

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")
COVERR_API_KEY = os.getenv("COVERR_API_KEY")

# Don't download very long files (e.g. full archival features) just to trim ~10s.
MAX_CLIP_SECONDS = 600
# Cap archival file size so we never pull a multi-GB feature film.
MAX_ARCHIVE_BYTES = 150 * 1024 * 1024

# Polite UA with a contact URL — Wikimedia and Internet Archive require one.
_UA = {"User-Agent": get_user_agent()}

# Default priority order; reorder via STOCK_SOURCES env.
DEFAULT_SOURCES = ["pexels", "pixabay", "coverr", "nasa", "archive", "wikimedia"]

# FAST = one curated HTTP call, HD, high relevance — always queried and ranked
# together so we pick the best clip ACROSS them. SLOW = nested metadata requests,
# variable quality (archival/niche) — only queried to backfill when the fast tier
# comes up short, so we don't hammer them for every clip slot.
FAST_SOURCES = {"pexels", "pixabay", "coverr"}

from agents.media import (
    _remove_files, get_duration, stitch_clips_to_duration, merge_audio_video, burn_subtitles,
)
from agents.transcription import transcribe_with_whisper, words_to_srt
from agents.voice import generate_voiceover

# Narration-aligned stock queries: one on-topic query per clip so the footage
# follows what the voiceover is actually saying (not generic mood b-roll).
from agents.comfy_prompts import narration_beats_for_clips
from agents.stock_queries import generate_stock_queries


def _duration_ok(dur, min_duration: int) -> bool:
    """Accept unknown (None) durations; otherwise enforce the min/max window."""
    if dur is None:
        return True
    return min_duration <= dur <= MAX_CLIP_SECONDS


# ------------------- PER-SOURCE SEARCHERS -------------------
# Each returns a list of {"url", "duration", "source", "thumb"} dicts in relevance
# order ("thumb" is a preview image URL, or None — used by the vision check).
# Network errors are swallowed (return []) so one flaky source never breaks a run.

def _search_pexels(query: str, min_duration: int, count: int) -> list:
    if not PEXELS_API_KEY:
        return []
    r = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": PEXELS_API_KEY},
        params={"query": query, "per_page": 15},
        timeout=15,
    )
    if r.status_code != 200:
        return []
    out = []
    for v in r.json().get("videos", []):  # KEEP relevance order
        dur = v.get("duration") or 0
        if not _duration_ok(dur, min_duration):
            continue
        # Highest-res file that doesn't exceed ~1080p width (good after crop,
        # without huge 4K downloads).
        files = sorted(v.get("video_files", []), key=lambda f: -(f.get("width") or 0))
        chosen = next((f for f in files if (f.get("width") or 0) <= 1920), None)
        if not chosen and files:
            chosen = files[-1]
        if chosen and chosen.get("link"):
            out.append({"url": chosen["link"], "duration": dur, "source": "pexels",
                        "thumb": v.get("image")})
        if len(out) >= count:
            break
    return out


def _search_pixabay(query: str, min_duration: int, count: int) -> list:
    if not PIXABAY_API_KEY:
        return []
    r = requests.get(
        "https://pixabay.com/api/videos/",
        params={"key": PIXABAY_API_KEY, "q": query,
                "per_page": max(3, min(count * 3, 50))},
        timeout=15,
    )
    if r.status_code != 200:
        return []
    out = []
    for hit in r.json().get("hits", []):
        dur = hit.get("duration") or 0
        if not _duration_ok(dur, min_duration):
            continue
        videos = hit.get("videos", {})
        chosen = next((videos[k] for k in ("large", "medium", "small", "tiny")
                       if videos.get(k) and videos[k].get("url")), None)
        if chosen:
            out.append({"url": chosen["url"], "duration": dur, "source": "pixabay",
                        "thumb": chosen.get("thumbnail")})
        if len(out) >= count:
            break
    return out


def _search_coverr(query: str, min_duration: int, count: int) -> list:
    if not COVERR_API_KEY:
        return []
    r = requests.get(
        "https://api.coverr.co/videos",
        params={"query": query, "page_size": max(count * 2, 5), "urls": "true"},
        headers={"Authorization": f"Bearer {COVERR_API_KEY}"},
        timeout=15,
    )
    if r.status_code != 200:
        return []
    out = []
    for v in r.json().get("hits", r.json().get("videos", [])):
        dur = v.get("duration")
        if not _duration_ok(dur, min_duration):
            continue
        urls = v.get("urls") or {}
        link = urls.get("mp4_download") or urls.get("mp4")
        if link:
            out.append({"url": link, "duration": dur, "source": "coverr",
                        "thumb": v.get("thumbnail") or v.get("poster")})
        if len(out) >= count:
            break
    return out


def _search_nasa(query: str, min_duration: int, count: int) -> list:
    r = requests.get(
        "https://images-api.nasa.gov/search",
        params={"q": query, "media_type": "video"}, timeout=15,
    )
    if r.status_code != 200:
        return []
    out = []
    for item in r.json().get("collection", {}).get("items", [])[: count * 2]:
        href = item.get("href")
        if not href:
            continue
        try:
            assets = requests.get(href, timeout=15).json()
        except Exception:
            continue
        mp4s = [u for u in assets if isinstance(u, str) and u.lower().endswith(".mp4")]
        if not mp4s:
            continue
        # Prefer a smaller/mobile variant over the large original.
        mp4s.sort(key=lambda u: (0 if ("mobile" in u.lower() or "small" in u.lower()) else 1, len(u)))
        preview = next((l.get("href") for l in item.get("links") or [] if l.get("href")), None)
        out.append({"url": mp4s[0], "duration": None, "source": "nasa", "thumb": preview})
        if len(out) >= count:
            break
    return out


def _search_archive(query: str, min_duration: int, count: int) -> list:
    r = requests.get(
        "https://archive.org/advancedsearch.php",
        params={"q": f"({query}) AND mediatype:(movies)", "fl[]": "identifier",
                "rows": count * 3, "output": "json", "sort[]": "downloads desc"},
        headers=_UA, timeout=20,
    )
    if r.status_code != 200:
        return []
    out = []
    for doc in r.json().get("response", {}).get("docs", []):
        ident = doc.get("identifier")
        if not ident:
            continue
        try:
            meta = requests.get(f"https://archive.org/metadata/{ident}",
                                headers=_UA, timeout=20).json()
        except Exception:
            continue
        # Smallest reasonable .mp4 in the item (avoid full multi-GB features).
        mp4s = [(f.get("name"), int(f.get("size") or 0)) for f in meta.get("files", [])
                if f.get("name", "").lower().endswith(".mp4")]
        mp4s = [(n, s) for n, s in mp4s if n and (not s or s <= MAX_ARCHIVE_BYTES)]
        if not mp4s:
            continue
        mp4s.sort(key=lambda c: c[1] or 1e12)
        name = mp4s[0][0]
        url = f"https://archive.org/download/{ident}/{requests.utils.quote(name)}"
        out.append({"url": url, "duration": None, "source": "archive",
                    "thumb": f"https://archive.org/services/img/{ident}"})
        if len(out) >= count:
            break
    return out


def _search_wikimedia(query: str, min_duration: int, count: int) -> list:
    # filetype:video is a relevance boost, not a hard filter — over-fetch and
    # filter client-side so video hits aren't crowded out by image results.
    r = requests.get(
        "https://commons.wikimedia.org/w/api.php",
        params={"action": "query", "format": "json", "generator": "search",
                "gsrsearch": f"filetype:video {query}", "gsrnamespace": "6",
                "gsrlimit": max(count * 5, 20), "prop": "imageinfo", "iiprop": "url|size",
                "iiurlwidth": 480},
        headers=_UA, timeout=20,
    )
    if r.status_code != 200:
        return []
    out = []
    for page in r.json().get("query", {}).get("pages", {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        url = info.get("url")
        if url and url.lower().endswith((".webm", ".ogv", ".mp4", ".mov")):
            out.append({"url": url, "duration": None, "source": "wikimedia",
                        "thumb": info.get("thumburl")})
        if len(out) >= count:
            break
    return out


_SOURCE_FUNCS = {
    "pexels": _search_pexels,
    "pixabay": _search_pixabay,
    "coverr": _search_coverr,
    "nasa": _search_nasa,
    "archive": _search_archive,
    "wikimedia": _search_wikimedia,
}
_KEY_GATED = {"pexels": PEXELS_API_KEY, "pixabay": PIXABAY_API_KEY, "coverr": COVERR_API_KEY}


def _enabled_sources() -> list:
    """Resolve the active source list from STOCK_SOURCES (or the default order),
    dropping unknown names and key-gated sources whose key is missing."""
    requested = os.getenv("STOCK_SOURCES")
    names = [s.strip() for s in requested.split(",") if s.strip()] if requested else DEFAULT_SOURCES
    active = []
    for n in names:
        if n not in _SOURCE_FUNCS:
            continue
        if n in _KEY_GATED and not _KEY_GATED[n]:
            continue
        active.append(n)
    return active


def _query_tier(names: list, query: str, min_duration: int, count: int, seen: set) -> list:
    """Query every source in `names`, scoring each candidate so the BEST across
    sources sorts first. Lower score = better. A clip's score is its relevance
    rank within its own source plus a small penalty for the source's position in
    the priority list — so the top hits from each source compete, with ties
    broken by STOCK_SOURCES order. Skips URLs already in `seen`."""
    scored = []
    for src_pos, name in enumerate(names):
        try:
            results = _SOURCE_FUNCS[name](query, min_duration, count)
        except Exception as e:
            log.warning(f"  [{name}] search failed for '{query}': {e}")
            results = []
        for in_rank, item in enumerate(results):
            if item["url"] in seen:
                continue
            seen.add(item["url"])
            item["_score"] = in_rank + src_pos * 0.5
            scored.append(item)
    scored.sort(key=lambda it: it["_score"])
    return scored


def search_stock_videos(query: str, min_duration: int = 5, count: int = 3) -> list:
    """Gather candidates across sources and return them BEST-FIRST.

    The fast curated stock sources (Pexels/Pixabay/Coverr) are all queried and
    ranked together, so for each query we pick the strongest clip across them
    rather than whatever the first source happens to return. The slow archival
    sources (NASA/Archive/Wikimedia) are only queried to backfill when the fast
    tier comes up short — keeping niche topics covered without hitting their
    nested endpoints for every clip slot. Returns {"url","duration","source"} dicts.
    """
    enabled = _enabled_sources()
    seen = set()

    fast = [n for n in enabled if n in FAST_SOURCES]
    merged = _query_tier(fast, query, min_duration, count, seen)

    if len(merged) < count:
        slow = [n for n in enabled if n not in FAST_SOURCES]
        merged += _query_tier(slow, query, min_duration, count, seen)

    return merged


# Backward-compatible thin wrapper (returns plain URLs).
def search_pexels_videos(query: str, min_duration: int = 6, count: int = 1) -> list:
    return [it["url"] for it in search_stock_videos(query, min_duration, count)]


def build_pexels_queries(script: dict) -> list:
    """Read queries directly from the script — Claude already wrote them properly."""
    queries = script.get("pexels_queries", [])
    if not queries:
        # Fallback if script didn't include queries
        queries = title_terms(script) or ["abstract cinematic"] * 8
    return queries


def title_terms(script: dict) -> list:
    """Concrete 1-2 word phrases derived from the video title, used as on-topic
    fallbacks before resorting to generic stock queries."""
    title = script.get("video_title", "")
    words = [w for w in re.sub(r"[^a-zA-Z\s]", " ", title.lower()).split() if len(w) > 3]
    terms = []
    for i in range(len(words) - 1):
        terms.append(f"{words[i]} {words[i+1]}")  # bigrams
    terms.extend(words)  # then single words
    # de-dupe preserving order
    seen, out = set(), []
    for t in terms:
        if t not in seen:
            seen.add(t); out.append(t)
    return out



def download_clip(url: str, clip_num: int) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(get_temp_dir(), f"clip_{clip_num}_{ts}.mp4")
    # 120s timeout: archival files can be larger/slower than Pexels b-roll.
    r = requests.get(url, timeout=120, stream=True, headers=_UA)
    if r.status_code != 200:
        raise RuntimeError(f"Clip download failed: HTTP {r.status_code}")
    with open(path, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
    return path


def _per_clip_queries(script: dict, num_clips: int) -> tuple:
    """Return (clip_queries, clip_beats): one narration-aligned stock query per clip.

    Falls back to (None, beats) so the caller can use the proportional scene-query
    mapping when Claude is unavailable.
    """
    clip_beats = narration_beats_for_clips(script, num_clips)
    log.info("[2a/5] Writing narration-aligned stock queries (Claude)...")
    try:
        clip_queries = generate_stock_queries(script, num_clips, clip_beats)
        log.info(f"  Got {len(clip_queries)} story-aligned stock queries")
        return clip_queries, clip_beats
    except Exception as e:
        log.warning(f"  Stock query generation failed ({e}) — using scene-query mapping")
        return None, clip_beats


def fetch_stock_footage(script: dict, num_clips: int, per_clip_duration: float = 6.0) -> list:
    """Pull num_clips clips across all enabled stock sources, each >= per_clip_duration."""
    log.info(f"\n[2/5] Fetching {num_clips} stock clips (min {per_clip_duration:.0f}s each) "
             f"from: {', '.join(_enabled_sources())}\n")

    queries = build_pexels_queries(script)
    title_fallbacks = title_terms(script)
    generic = ["cinematic abstract", "slow motion nature", "atmospheric mood", "abstract texture"]

    # Per-clip queries tied to the narration beat that plays over each clip, so the
    # footage follows the STORY in order rather than generic mood b-roll.
    clip_queries, clip_beats = _per_clip_queries(script, num_clips)

    paths = []
    used_urls = set()  # dedupe across queries

    for i in range(num_clips):
        beat = clip_beats[i] if i < len(clip_beats) else ""
        if clip_queries:
            # On-topic query for THIS clip's narration, then its neighbours (same
            # world), then the rest, the script's scene queries, title terms, generic.
            primary_query = clip_queries[i]
            neighbours = [clip_queries[j] for j in (i - 1, i + 1)
                          if 0 <= j < len(clip_queries) and clip_queries[j] != primary_query]
            others = [q for q in clip_queries if q != primary_query and q not in neighbours]
            candidate_queries = ([primary_query] + neighbours + others
                                 + queries + title_fallbacks + generic)
        else:
            # Fallback: map each clip slot back to a scene query proportionally so the
            # cuts still follow the story IN ORDER even without per-clip queries.
            scene_idx = (i * len(queries)) // max(num_clips, 1)
            primary_query = queries[min(scene_idx, len(queries) - 1)]
            neighbours = [queries[j] for j in (scene_idx - 1, scene_idx + 1)
                          if 0 <= j < len(queries) and queries[j] != primary_query]
            others = [q for q in queries if q != primary_query and q not in neighbours]
            candidate_queries = [primary_query] + neighbours + others + title_fallbacks + generic

        # De-dupe while preserving order so we don't search the same term twice.
        _seen_q = set()
        candidate_queries = [
            q for q in candidate_queries if q and not (q in _seen_q or _seen_q.add(q))
        ]

        chosen = None
        if beat:
            log.info(f"  Clip {i+1}/{num_clips} | VO: {beat[:55]}{'...' if len(beat) > 55 else ''}")

        for query in candidate_queries:
            log.info(f"  Clip {i+1}: trying '{query}' (need {per_clip_duration:.0f}s+)")
            for item in search_stock_videos(query, min_duration=int(per_clip_duration), count=3):
                if item["url"] not in used_urls:
                    chosen = item
                    used_urls.add(item["url"])
                    break
            if chosen:
                break

        if not chosen:
            # Last resort: any clip, any duration, any source.
            log.info(f"    Last resort: any clip")
            for item in search_stock_videos(generic[0], min_duration=3, count=5):
                if item["url"] not in used_urls:
                    chosen = item
                    used_urls.add(item["url"])
                    break

        if not chosen:
            raise Exception(f"No suitable footage found for clip {i+1}")

        path = download_clip(chosen["url"], i + 1)
        actual_dur = get_duration(path)
        size_mb = os.path.getsize(path) / 1024 / 1024
        log.info(f"    Got {actual_dur:.1f}s clip ({size_mb:.1f} MB) [{chosen['source']}]")
        paths.append(path)

    return paths



def process_video(script: dict, voice: str = "energetic") -> str:
    """Pexels stock + ElevenLabs voice + word-by-word subtitles. Cost: ~$0."""
    from agents.beats import get_beats
    if get_beats(script):  # beat scripts: visuals timed to the narration
        from agents.editor_beats import process_video as process_beats
        return process_beats(script, voice=voice, footage="pexels")

    audio_path = None
    clips = []
    stitched = None
    merged = None
    srt = None

    try:
        audio_path, audio_duration = generate_voiceover(script["spoken_script"], voice=voice)

        target_duration = audio_duration + 0.5

        # Cut roughly every MAX_CLIP_SCREEN_SECONDS so no single shot lingers long
        # enough to bore the viewer. num_clips scales with length (e.g. ~25 clips
        # for a 75s video) instead of the old hard cap of 8 (which left each clip
        # on screen ~9s). fetch_stock_footage maps these slots back onto the scene
        # queries in order, so more cuts == tighter pacing, NOT lost story order.
        MAX_CLIP_SCREEN_SECONDS = 3.0
        num_clips = max(6, round(target_duration / MAX_CLIP_SCREEN_SECONDS))
        log.info(f"\nVoice = {audio_duration:.1f}s. Fetching {num_clips} stock clips "
                 f"(~{target_duration / num_clips:.1f}s each).\n")

        # Accept clips as short as 3s so on-topic footage isn't rejected for being
        # short (loop_to_fill trims long clips AND loops short ones to fill their
        # ~3s slot, so every cut is covered by its own scene-matched footage).
        clips = fetch_stock_footage(script, num_clips=num_clips, per_clip_duration=3.0)
        stitched = stitch_clips_to_duration(clips, target_duration=target_duration, loop_to_fill=True)

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
