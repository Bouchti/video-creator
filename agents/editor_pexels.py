"""
Stock-footage sources for the pexels route (agents/editor_beats.py builds the video): free real video
from MULTIPLE free sources instead of AI-generated video.

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
