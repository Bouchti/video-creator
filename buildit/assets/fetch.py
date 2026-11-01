"""Build-It assets fetched once and cached under buildit/assets/, each logged in buildit/assets/credits.json."""
from __future__ import annotations

import json
import logging
import os
import urllib.parse

import requests

from cutaway.assets.fetch import _download, polyhaven_hdri  # noqa: F401  (shared downloader, HDRIs)

ASSETS = os.path.dirname(os.path.abspath(__file__))
CREDITS = os.path.join(ASSETS, "credits.json")
log = logging.getLogger("pipeline")

FONTS = {   # captions and pills: heavy rounded geometric sans (docs/style_guide.md)
    "Poppins-Black.ttf": "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Black.ttf",
    "Poppins-ExtraBold.ttf": "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-ExtraBold.ttf",
}
INCOMPETECH = "https://incompetech.com/music/royalty-free/mp3-royaltyfree/"
MUSIC = ["Wallpaper", "Carefree", "Life of Riley", "Investigations"]       # light, upbeat, under a voice
MUSIC_CREDIT = ('"{title}" Kevin MacLeod (incompetech.com). Licensed under Creative Commons: By Attribution 4.0 '
                "License. http://creativecommons.org/licenses/by/4.0/")


def _record(key: str, entry: dict):
    data = json.load(open(CREDITS, encoding="utf-8")) if os.path.exists(CREDITS) else {}
    data[key] = entry
    with open(CREDITS, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)


def font(name: str) -> str:
    path = os.path.join(ASSETS, "fonts", name)
    if not os.path.exists(path):
        _download(FONTS[name], path)
        _record(f"font/{name}", {"kind": "font", "source": "Google Fonts", "author": "Indian Type Foundry",
                                 "license": "SIL Open Font License 1.1",
                                 "url": "https://fonts.google.com/specimen/Poppins"})
    return path


def music(prefer: str | None = None) -> dict:
    """A light upbeat CC BY track (cached); the first that downloads."""
    os.makedirs(os.path.join(ASSETS, "music"), exist_ok=True)
    for title in ([prefer] if prefer else []) + MUSIC:
        path = os.path.join(ASSETS, "music", f"{title}.mp3")
        try:
            if not os.path.exists(path):
                _download(INCOMPETECH + urllib.parse.quote(title) + ".mp3", path)
            entry = {"title": title, "file": path, "license": "CC BY 4.0", "author": "Kevin MacLeod",
                     "credit": MUSIC_CREDIT.format(title=title), "source_url": "https://incompetech.com"}
            _record(f"music/{title}", {k: v for k, v in entry.items() if k != "file"})
            return entry
        except requests.RequestException as exc:
            log.warning("[buildit] music %s unavailable: %s", title, exc)
    raise RuntimeError("no music track could be downloaded")


def hdri() -> str:
    return polyhaven_hdri("studio_small_09")
