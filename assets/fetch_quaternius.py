"""Download the free (Standard, CC0) Quaternius packs into assets/cc0/quaternius/.

    python assets/fetch_quaternius.py                 # every pack in PACKS
    python assets/fetch_quaternius.py universal-base-characters

Quaternius (quaternius.com) publishes the free Standard tier of each pack on itch.io, CC0: free for
commercial use, no attribution. Characters share one humanoid rig with the Universal Animation
Library, so any character can play any clip. Re-running skips packs already extracted.
"""
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import http.cookiejar
import zipfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cc0", "quaternius")
PACKS = {   # itch slug -> what it gives the routes
    "universal-base-characters": "rigged humanoids (Max and extras) on the universal rig",
    "universal-animation-library": "120+ clips on the universal rig (walk, point, cheer, ...)",
    "universal-animation-library-2": "130+ more clips on the same rig",
    "modular-character-outfits-fantasy": "outfits for the universal characters",
    "stylized-nature-megakit": "stylised trees, bushes, rocks, grass",
    "150-lowpoly-nature-models": "low-poly nature set dressing",
    "textured-lowpoly-trees": "textured trees",
    "downtown-city-megakit": "city buildings and street props",
    "lowpoly-modular-street": "streets, sidewalks, lamps",
    "lowpoly-cars": "cars",
    "lowpoly-farm-buildings": "barns, silos, farm buildings",
    "medieval-village-megakit": "medieval buildings (history topics)",
    "fantasy-props-megakit": "barrels, crates, tools, props",
    "modular-sci-fi-megakit": "sci-fi corridors and machines",
    "sci-fi-essentials-kit": "sci-fi props",
    "lowpoly-spaceships": "spaceships",
    "lowpoly-robot": "animated robot",
    "lowpoly-animated-animals": "animated animals",
    "lowpoly-animated-fish": "animated fish",
    "animated-lowpoly-dinosaurs": "animated dinosaurs",
    "platformer-pack": "platformer props",
    "ultimate-platformer-pack": "platformer props and characters",
}


def _opener():
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    op.addheaders = [("User-Agent", "Mozilla/5.0 (video-creator CC0 fetch)")]
    return op


def _text(op, url, data=None):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    return op.open(url, body, timeout=120).read().decode("utf-8", "replace")


def _token(html):
    return re.search(r'csrf_token" value="([^"]+)"', html).group(1)


def fetch(slug):
    target = os.path.join(ROOT, slug)
    if os.path.isfile(os.path.join(target, ".done")):
        print(f"have  {slug}", flush=True)
        return
    op = _opener()
    base = f"https://quaternius.itch.io/{slug}"
    page = _text(op, base)
    dl_url = json.loads(_text(op, base + "/download_url", {"csrf_token": _token(page)}))["url"]
    dl_page = _text(op, dl_url)
    uploads = re.findall(r'data-upload_id="(\d+)".*?<strong title="([^"]+)"', dl_page, re.S)
    if not uploads:
        print(f"skip  {slug}: no free uploads", flush=True)
        return
    for upload_id, name in uploads:
        if not name.lower().endswith(".zip"):
            continue
        # Free packs: the file endpoint answers with a short-lived signed URL; sending the
        # download-page key is rejected ("invalid key"), so it is left out.
        info = json.loads(_text(op, f"{base}/file/{upload_id}?source=game_download",
                                {"csrf_token": _token(dl_page)}))
        print(f"get   {slug}: {name}", flush=True)
        data = op.open(info["url"], timeout=1200).read()
        zipfile.ZipFile(io.BytesIO(data)).extractall(target)
    open(os.path.join(target, ".done"), "w").close()


def main(argv):
    os.makedirs(ROOT, exist_ok=True)
    failed = []
    for slug in argv or list(PACKS):
        try:
            fetch(slug)
        except Exception as exc:  # a missing or renamed pack never stops the others
            print(f"FAILED {slug}: {str(exc)[:160]}", flush=True)
            failed.append(slug)
    return {"assets": len(argv or PACKS), "failed": failed}


if __name__ == "__main__":
    main(sys.argv[1:])
