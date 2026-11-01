"""
Fetch Cutaway Studio's licensed assets and log each one in cutaway/assets/credits.json.

    python -m cutaway.assets.fetch                 # the default HDRIs
    python -m cutaway.assets.fetch hdri studio_small_09
    python -m cutaway.assets.fetch texture metal_plate

Poly Haven (polyhaven.com) assets are CC0: no attribution needed, logged anyway so every file has a record.
Downloads are git-ignored; credits.json is committed and is the source of the credits line in post.txt.
"""
from __future__ import annotations

import json
import logging
import os
import sys

import requests

from config.paths import get_user_agent

from ..config import ASSETS

log = logging.getLogger("pipeline")
CREDITS = os.path.join(ASSETS, "credits.json")
API = "https://api.polyhaven.com"
DEFAULT_HDRIS = ("studio_small_09", "photo_studio_loft_hall", "studio_small_03")


def _get(url, stream=False):
    r = requests.get(url, headers={"User-Agent": get_user_agent()}, timeout=60, stream=stream)
    r.raise_for_status()
    return r


def load_credits() -> dict:
    if os.path.exists(CREDITS):
        with open(CREDITS, encoding="utf-8") as f:
            return json.load(f)
    return {}


def record(key: str, entry: dict) -> None:
    """Log one asset: {kind, name, source, url, license, author, files}."""
    credits = load_credits()
    credits[key] = entry
    with open(CREDITS, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(credits.items())), f, indent=2)
        f.write("\n")


def _download(url: str, path: str) -> str:
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    with _get(url, stream=True) as r, open(tmp, "wb") as f:
        for chunk in r.iter_content(1 << 20):
            f.write(chunk)
    os.replace(tmp, path)
    return path


def _authors(asset_id: str) -> str:
    info = _get(f"{API}/info/{asset_id}").json()
    return ", ".join(info.get("authors", {})) or "Poly Haven"


def polyhaven_hdri(asset_id: str, res: str = "2k") -> str:
    path = os.path.join(ASSETS, "hdri", f"{asset_id}_{res}.hdr")
    if not os.path.exists(path):
        files = _get(f"{API}/files/{asset_id}").json()
        _download(files["hdri"][res]["hdr"]["url"], path)
        record(f"hdri/{asset_id}", {
            "kind": "hdri", "name": asset_id, "source": "Poly Haven",
            "url": f"https://polyhaven.com/a/{asset_id}", "license": "CC0", "author": _authors(asset_id),
            "files": [os.path.relpath(path, ASSETS).replace("\\", "/")],
        })
        log.info("HDRI %s -> %s", asset_id, path)
    return path


TEXTURE_MAPS = {"Diffuse": "diff", "Rough": "rough", "nor_gl": "nor_gl", "AO": "ao", "Displacement": "disp"}


def polyhaven_texture(asset_id: str, res: str = "2k") -> dict:
    """Download a PBR texture set; returns {map: path} for the maps it has."""
    folder = os.path.join(ASSETS, "textures", asset_id)
    files = _get(f"{API}/files/{asset_id}").json()
    out = {}
    for key, short in TEXTURE_MAPS.items():
        entry = files.get(key, {}).get(res, {})
        fmt = entry.get("jpg") or entry.get("png")
        if fmt:
            ext = "jpg" if "jpg" in entry else "png"
            out[short] = _download(fmt["url"], os.path.join(folder, f"{asset_id}_{short}_{res}.{ext}"))
    record(f"texture/{asset_id}", {
        "kind": "texture", "name": asset_id, "source": "Poly Haven",
        "url": f"https://polyhaven.com/a/{asset_id}", "license": "CC0", "author": _authors(asset_id),
        "files": [os.path.relpath(p, ASSETS).replace("\\", "/") for p in out.values()],
    })
    return out


FONTS = {
    "Anton-Regular.ttf": ("https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf",
                          "Anton by Vernon Adams", "SIL Open Font License 1.1",
                          "https://fonts.google.com/specimen/Anton"),
}


def font(name: str = "Anton-Regular.ttf") -> str:
    url, author, lic, page = FONTS[name]
    path = os.path.join(ASSETS, "fonts", name)
    if not os.path.exists(path):
        _download(url, path)
        record(f"font/{name}", {"kind": "font", "name": name, "source": "Google Fonts", "url": page,
                                "license": lic, "author": author, "files": [f"fonts/{name}"]})
    return path


def ensure_defaults() -> list[str]:
    return [polyhaven_hdri(h) for h in DEFAULT_HDRIS]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    args = sys.argv[1:]
    if not args:
        print("\n".join(ensure_defaults()))
    elif args[0] == "hdri":
        print("\n".join(polyhaven_hdri(a) for a in args[1:]))
    elif args[0] == "texture":
        for a in args[1:]:
            print(json.dumps(polyhaven_texture(a), indent=1))
    else:
        sys.exit("usage: python -m cutaway.assets.fetch [hdri ID...|texture ID...]")
