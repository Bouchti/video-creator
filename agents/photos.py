"""
Photo source: real, freely-licensed images of the exact thing the narration names
(a person, artifact, building, machine), from Wikipedia lead images and Wikimedia
Commons — then animated with a smooth Ken Burns push-in over a blurred backdrop.

Only free licenses are accepted (public domain, CC0, CC BY, CC BY-SA). CC BY and
BY-SA require attribution, so every used photo returns a credit line that the
pipeline writes next to the final video.
"""
import os
import re
import logging

import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from config.paths import get_env_path, get_user_agent
from agents.render import W, H, FPS, SAFE_TOP, ease_in_out, draw_badge, encode_frames

load_dotenv(get_env_path())
log = logging.getLogger("pipeline")

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
_UA = {"User-Agent": get_user_agent()}

MIN_WIDTH = 700          # smaller originals look soft at 1080 wide
THUMB_WIDTH = 1600       # rendered/downloaded size
_FREE = re.compile(r"^(cc0|public domain|pd\b|pd-|cc[ -]by(?:-sa)?\b)", re.I)
_NON_FREE = re.compile(r"\b(nc|nd)\b|non-?commercial|no ?deriv|fair use", re.I)
_IMAGE_MIMES = ("image/jpeg", "image/png", "image/webp", "image/tiff", "image/svg+xml")


def _strip_html(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()


def is_free_license(name: str) -> bool:
    name = (name or "").strip()
    return bool(_FREE.match(name)) and not _NON_FREE.search(name)


def parse_imageinfo_pages(pages: dict) -> list:
    """Commons API pages → usable candidates (free license, big enough, image)."""
    out = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        license_name = _strip_html((meta.get("LicenseShortName") or {}).get("value", ""))
        mime = info.get("mime", "")
        url = info.get("thumburl") or info.get("url")
        if not url or mime not in _IMAGE_MIMES or not is_free_license(license_name):
            continue
        if mime != "image/svg+xml" and (info.get("width") or 0) < MIN_WIDTH:
            continue
        title = page.get("title", "").removeprefix("File:")
        artist = _strip_html((meta.get("Artist") or {}).get("value", "")) or "Unknown author"
        out.append({
            "url": url,
            "thumb": url,
            "title": title,
            "credit": f"{title} — {artist}, {license_name} ({info.get('descriptionurl', '')})",
        })
    return out


def _imageinfo_params() -> dict:
    return {"prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": THUMB_WIDTH,
            "iiextmetadatafilter": "LicenseShortName|Artist"}


def _wikipedia_lead_images(query: str, limit: int = 2) -> list:
    """Free lead images of the best-matching Wikipedia articles (as File: titles)."""
    r = requests.get(WIKIPEDIA_API, headers=_UA, timeout=15, params={
        "action": "query", "format": "json", "generator": "search", "gsrsearch": query,
        "gsrlimit": limit, "prop": "pageimages", "piprop": "name", "pilicense": "free",
    })
    if r.status_code != 200:
        return []
    pages = sorted(r.json().get("query", {}).get("pages", {}).values(),
                   key=lambda p: p.get("index", 99))
    return [f"File:{p['pageimage']}" for p in pages if p.get("pageimage")]


def _commons_files(titles: list) -> list:
    if not titles:
        return []
    r = requests.get(COMMONS_API, headers=_UA, timeout=20, params={
        "action": "query", "format": "json", "titles": "|".join(titles), **_imageinfo_params()})
    if r.status_code != 200:
        return []
    pages = r.json().get("query", {}).get("pages", {})
    # Keep the order of `titles` (most relevant article first).
    order = {t.replace("_", " "): i for i, t in enumerate(titles)}
    found = parse_imageinfo_pages(pages)
    return sorted(found, key=lambda c: order.get(f"File:{c['title']}", 99))


def _commons_search(query: str, limit: int = 8) -> list:
    r = requests.get(COMMONS_API, headers=_UA, timeout=20, params={
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"filetype:bitmap|drawing {query}", "gsrnamespace": "6",
        "gsrlimit": limit, **_imageinfo_params()})
    if r.status_code != 200:
        return []
    pages = r.json().get("query", {}).get("pages", {})
    found = parse_imageinfo_pages(pages)
    index = {p.get("title", "").removeprefix("File:"): p.get("index", 99) for p in pages.values()}
    return sorted(found, key=lambda c: index.get(c["title"], 99))


def search_photos(queries: list, want: int = 6) -> list:
    """Candidates best-first: Wikipedia lead image of the named thing, then Commons."""
    out, seen = [], set()

    def add(cands):
        for c in cands:
            if c["url"] not in seen:
                seen.add(c["url"])
                out.append(c)

    queries = [str(q).strip() for q in queries if str(q).strip()]
    for i, q in enumerate(queries):
        try:
            if i == 0:  # the most specific query is usually the thing's own name
                add(_commons_files(_wikipedia_lead_images(q)))
            add(_commons_search(q))
        except Exception as e:
            log.warning(f"    Photo search failed for '{q}': {e}")
        if len(out) >= want:
            break
    return out[:want]


def download_image(url: str, path: str) -> str:
    r = requests.get(url, headers=_UA, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"Image download failed: HTTP {r.status_code}")
    with open(path, "wb") as f:
        f.write(r.content)
    return path


# ------------------- KEN BURNS RENDER -------------------

FG_MAX_W, FG_MAX_H = W - 80, 1120
FG_CENTER_Y = 770
ZOOM = 0.12


def render_photo(image_path: str, frames: int, out_path: str, caption: str = None,
                 drift: int = 1) -> str:
    """Animate a still: sharp photo slowly pushing in over a blurred, darkened copy."""
    src = ImageOps.exif_transpose(Image.open(image_path)).convert("RGB")
    sw, sh = src.size
    # With a caption, the photo moves down to leave the badge its own row above it.
    max_h, center_y = (FG_MAX_H - 130, FG_CENTER_Y + 65) if caption else (FG_MAX_H, FG_CENTER_Y)
    scale = min(FG_MAX_W / sw, max_h / sh)
    fw, fh = max(2, int(sw * scale)), max(2, int(sh * scale))
    # Downscale once so per-frame resampling stays cheap (keep 1.5x for zoom detail).
    work_w = min(sw, int(fw * 1.5))
    if work_w < sw:
        src = src.resize((work_w, int(sh * work_w / sw)), Image.LANCZOS)
        sw, sh = src.size

    bg = ImageOps.fit(src, (W, H)).filter(ImageFilter.GaussianBlur(40))
    bg = Image.blend(bg, Image.new("RGB", (W, H), (0, 0, 0)), 0.5)
    fx, fy = (W - fw) // 2, int(center_y - fh / 2)
    shadow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shadow).rectangle((fx + 10, fy + 24, fx + fw + 10, fy + fh + 24), fill=170)
    bg.paste((0, 0, 0), (0, 0, W, H), shadow.filter(ImageFilter.GaussianBlur(24)))
    if caption:
        draw_badge(ImageDraw.Draw(bg), caption, W // 2, max(SAFE_TOP - 60, fy - 125))

    duration = frames / FPS

    def frame_at(i):
        p = ease_in_out(i / max(frames - 1, 1))
        z = 1 + ZOOM * p
        cw, ch = sw / z, sh / z
        # Drift the focal point slightly sideways for a hand-held documentary feel.
        cx = sw / 2 + drift * (sw - cw) / 2 * (p - 0.5)
        cy = sh / 2
        box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
        fg = src.resize((fw, fh), Image.BILINEAR, box=box)  # float box = sub-pixel smooth
        out = bg.copy()
        out.paste(fg, (fx, fy))
        return out

    log.info(f"    Rendering photo ({duration:.1f}s)")
    return encode_frames((frame_at(i) for i in range(frames)), out_path)
