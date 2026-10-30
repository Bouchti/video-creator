"""
BlenderKit assets for the journey route (free assets only; royalty-free licence allows monetised video).
Needs BLENDERKIT_API_KEY in .env (Blender > Preferences > Add-ons > BlenderKit, after logging in).

    python assets/fetch_blenderkit.py search "toilet" "pvc pipe elbow" --n 12   # results + thumbnails
    python assets/fetch_blenderkit.py search-shortlist                          # every query in SHORTLIST
    python assets/fetch_blenderkit.py get ASSET_BASE_ID [ASSET_BASE_ID ...]     # download the .blend files

Search results land in assets/blenderkit/search/<query>.json with thumbnails in .../thumbs/;
downloads in assets/blenderkit/<assetBaseId>/<name>.blend plus meta.json (name, author, licence).
"""
import argparse
import json
import os
import re
import sys
import uuid

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "blenderkit")
API = "https://www.blenderkit.com/api/v1"

# What the wastewater golden film needs (search terms tried in order)
SHORTLIST = [
    "toilet", "toilet cutaway", "bathroom", "pvc pipe", "pipe elbow", "pipe fitting tee", "sewer pipe",
    "concrete pipe", "manhole", "submersible pump", "water pump", "grass", "grass clump", "soil",
    "ground cross section", "concrete wall", "house exterior", "window shutters", "sidewalk curb",
    "water treatment", "clarifier", "concrete tank", "steel railing", "river", "rocks",
]


def _key():
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(ROOT, ".env"))
    except ImportError:
        pass
    key = (os.getenv("BLENDERKIT_API_KEY") or "").strip().strip('"')
    if not key:
        sys.exit("BLENDERKIT_API_KEY is not set in .env")
    return key


def _headers():
    return {"Authorization": f"Bearer {_key()}", "User-Agent": "video-creator-journey/1.0"}


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:60]


def search(query, n=12, asset_type="model"):
    q = f"{query}+asset_type:{asset_type}+is_free:true"
    url = f"{API}/search/?query={q}&dict_parameters=1&page_size={n}&addon_version=3.12.0"
    r = requests.get(url, headers=_headers(), timeout=60)
    r.raise_for_status()
    data = r.json()
    rows = []
    thumbs = os.path.join(OUT, "search", "thumbs")
    os.makedirs(thumbs, exist_ok=True)
    for a in data.get("results", []):
        p = a.get("dictParameters") or {}
        row = {
            "query": query,
            "name": a.get("name"),
            "assetBaseId": a.get("assetBaseId"),
            "id": a.get("id"),
            "free": a.get("isFree"),
            "license": a.get("license"),
            "author": (a.get("author") or {}).get("fullName") if isinstance(a.get("author"), dict) else a.get("author"),
            "score": a.get("score"),
            "dimensions": [p.get("dimensionX"), p.get("dimensionY"), p.get("dimensionZ")],
            "faces": p.get("faceCount"),
            "pbr": p.get("pbr"),
            "condition": p.get("condition"),
            "style": p.get("modelStyle"),
            "description": (a.get("description") or "")[:200],
        }
        turl = a.get("thumbnailMiddleUrl") or a.get("thumbnailSmallUrl")
        if turl:
            path = os.path.join(thumbs, f"{asset_type}__{_slug(query)}__{row['assetBaseId']}.jpg")
            if not os.path.isfile(path):
                try:
                    t = requests.get(turl, timeout=60)
                    if t.ok:
                        open(path, "wb").write(t.content)
                except requests.RequestException:
                    pass
            row["thumb"] = os.path.relpath(path, ROOT)
        rows.append(row)
    path = os.path.join(OUT, "search", f"{asset_type}__{_slug(query)}.json")
    json.dump({"query": query, "count": data.get("count"), "results": rows}, open(path, "w", encoding="utf-8"),
              indent=1)
    print(f"{query!r}: {data.get('count')} free {asset_type}s, saved {len(rows)} -> {os.path.relpath(path, ROOT)}")
    return rows


def get(base_id):
    r = requests.get(f"{API}/search/?query=asset_base_id:{base_id}&dict_parameters=1", headers=_headers(), timeout=60)
    r.raise_for_status()
    results = r.json().get("results", [])
    if not results:
        print(f"{base_id}: not found")
        return None
    a = results[0]
    if not a.get("isFree"):
        print(f"{base_id}: not a free asset, skipped")
        return None
    blend = next((f for f in a.get("files", []) if f.get("fileType") == "blend"), None)
    if not blend:
        print(f"{base_id}: no .blend file")
        return None
    d = requests.get(blend["downloadUrl"], params={"scene_uuid": str(uuid.uuid4())}, headers=_headers(), timeout=60)
    d.raise_for_status()
    signed = d.json().get("filePath")
    folder = os.path.join(OUT, base_id)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{_slug(a.get('name') or base_id)}.blend")
    with requests.get(signed, stream=True, timeout=600) as s:
        s.raise_for_status()
        with open(path, "wb") as fh:
            for chunk in s.iter_content(1 << 20):
                fh.write(chunk)
    meta = {"name": a.get("name"), "assetBaseId": base_id, "license": a.get("license"),
            "author": (a.get("author") or {}).get("fullName") if isinstance(a.get("author"), dict) else None,
            "file": os.path.basename(path), "dimensions": [(a.get("dictParameters") or {}).get(k) for k in
                                                          ("dimensionX", "dimensionY", "dimensionZ")]}
    json.dump(meta, open(os.path.join(folder, "meta.json"), "w", encoding="utf-8"), indent=1)
    print(f"{base_id}: {meta['name']} -> {os.path.relpath(path, ROOT)} ({os.path.getsize(path) / 1e6:.1f} MB)")
    return path


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("queries", nargs="+")
    s.add_argument("--n", type=int, default=12)
    s.add_argument("--type", default="model", help="model | material | hdr")
    sh = sub.add_parser("search-shortlist")
    sh.add_argument("--n", type=int, default=12)
    g = sub.add_parser("get")
    g.add_argument("ids", nargs="+")
    a = ap.parse_args()
    if a.cmd == "search":
        for q in a.queries:
            search(q, a.n, a.type)
    elif a.cmd == "search-shortlist":
        for q in SHORTLIST:
            try:
                search(q, a.n)
            except requests.HTTPError as exc:
                print(f"{q!r}: {exc}")
        for q in ("soil", "concrete", "grass", "dirt ground", "plaster wall"):
            search(q, 8, "material")
    else:
        for i in a.ids:
            get(i)


if __name__ == "__main__":
    main()
