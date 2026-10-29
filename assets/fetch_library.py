"""Download the CC0 asset library the Blender routes build from into assets/cc0/, and index it.

    python assets/fetch_library.py                     # everything below, resumable
    python assets/fetch_library.py hdris ambientcg     # only some parts
    python assets/fetch_library.py --catalog           # rebuild assets/cc0/catalog.json from disk only

Parts (all CC0: free for commercial use, no attribution required):
  hdris      Poly Haven HDRIs, 2k .hdr                    (~6.4 GB)
  ambientcg  ambientCG PBR materials, 2K-JPG, extracted   (~6.0 GB)
  textures   Poly Haven PBR textures, 2k .blend + maps    (~18 GB)
  models     Poly Haven models, 2k .blend + maps          (~13 GB)

Re-running skips finished files (size + md5 checked for Poly Haven), so an interrupted download
resumes. It stops cleanly before free disk space drops under LIBRARY_MIN_FREE_GB (default 15).
assets/cc0/catalog.json lists every asset with its tags and categories so planners can pick by
meaning ("rusty metal", "gravel", "overcast sky") instead of by file name.
"""
import concurrent.futures as cf
import hashlib
import io
import json
import os
import shutil
import sys
import time
import urllib.request
import zipfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cc0")
CATALOG = os.path.join(ROOT, "catalog.json")
UA = {"User-Agent": "video-creator asset library fetch (CC0)"}
RES = os.getenv("LIBRARY_RES", "2k")
ACG_RES = os.getenv("LIBRARY_ACG_RES", "2K-JPG")
MIN_FREE_GB = float(os.getenv("LIBRARY_MIN_FREE_GB", "15"))
WORKERS = int(os.getenv("LIBRARY_WORKERS", "8"))
PH_KIND = {"hdris": ("hdri", "hdr"), "textures": ("blend", "blend"), "models": ("blend", "blend")}


class DiskFull(RuntimeError):
    pass


def _get(url, timeout=120):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))


def _json(url):
    return json.loads(_get(url))


def _free_gb():
    return shutil.disk_usage(ROOT).free / 1e9


def _guard(nbytes):
    if _free_gb() - nbytes / 1e9 < MIN_FREE_GB:
        raise DiskFull(f"stopping: less than {MIN_FREE_GB} GB would stay free")


def _md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _have(path, size, md5=None):
    if not os.path.isfile(path) or os.path.getsize(path) != size:
        return False
    return md5 is None or _md5(path) == md5


def _download(url, path, size, md5=None):
    if _have(path, size, md5):
        return 0
    _guard(size)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(_get(url, timeout=600))
    os.replace(tmp, path)
    return size


# ------------------------------------------------------------ Poly Haven

def _ph_files(kind, asset_id):
    fmt, key = PH_KIND[kind]
    entry = _json(f"https://api.polyhaven.com/files/{asset_id}").get(fmt, {})
    res = RES if RES in entry else (sorted(entry)[0] if entry else None)
    if res is None:
        return []
    main = entry[res][key]
    base = os.path.join(ROOT, "polyhaven", kind, asset_id)
    files = [(main["url"], os.path.join(base, os.path.basename(main["url"])), main["size"], main.get("md5"))]
    for rel, inc in (main.get("include") or {}).items():
        files.append((inc["url"], os.path.join(base, *rel.split("/")), inc["size"], inc.get("md5")))
    return files


def fetch_polyhaven(kind):
    assets = _json(f"https://api.polyhaven.com/assets?t={kind}")
    print(f"polyhaven {kind}: {len(assets)} assets", flush=True)
    meta_path = os.path.join(ROOT, "polyhaven", kind, "_assets.json")
    os.makedirs(os.path.dirname(meta_path), exist_ok=True)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(assets, f)

    def one(asset_id):
        got = 0
        for url, path, size, md5 in _ph_files(kind, asset_id):
            got += _download(url, path, size, md5)
        return got

    return _run(kind, list(assets), one)


# ------------------------------------------------------------ ambientCG

def _acg_assets():
    # paginate by offset ourselves: the API's nextPageHttp drops the include= list (no download links)
    out, offset = [], 0
    while True:
        page = _json("https://ambientcg.com/api/v2/full_json?type=Material&include=downloadData,tagData,"
                     f"displayData&limit=250&offset={offset}")
        out += page["foundAssets"]
        offset += 250
        if not page["foundAssets"] or offset >= int(page.get("numberOfResults", 0)):
            return out


def fetch_ambientcg():
    assets = _acg_assets()
    print(f"ambientcg: {len(assets)} materials", flush=True)
    base = os.path.join(ROOT, "ambientcg")
    os.makedirs(base, exist_ok=True)
    with open(os.path.join(base, "_assets.json"), "w", encoding="utf-8") as f:
        json.dump([{k: a.get(k) for k in ("assetId", "tags", "category", "displayName", "displayCategory")}
                   for a in assets], f)
    by_id = {a["assetId"]: a for a in assets}

    def one(asset_id):
        folders = (by_id[asset_id].get("downloadFolders") or {}).get("default") or {}
        downloads = folders.get("downloadFiletypeCategories", {}).get("zip", {}).get("downloads", [])
        dl = next((d for d in downloads if d["attribute"] == ACG_RES), None)
        if dl is None:
            return 0
        target = os.path.join(base, asset_id)
        done = os.path.join(target, ".done")
        if os.path.isfile(done):
            return 0
        _guard(dl["size"] * 1.1)
        zipfile.ZipFile(io.BytesIO(_get(dl["downloadLink"], timeout=600))).extractall(target)
        open(done, "w").close()
        return dl["size"]

    return _run("ambientcg", list(by_id), one)


# ------------------------------------------------------------ shared

def _run(label, ids, one):
    got, failed, t0 = 0, [], time.time()
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        futures = {ex.submit(one, i): i for i in ids}
        for n, fut in enumerate(cf.as_completed(futures), 1):
            try:
                got += fut.result()
            except DiskFull as exc:
                for f in futures:
                    f.cancel()
                print(f"{label}: {exc}", flush=True)
                raise
            except Exception as exc:  # one bad asset never stops the library
                failed.append((futures[fut], str(exc)[:120]))
            if n % 50 == 0 or n == len(ids):
                print(f"{label}: {n}/{len(ids)}  +{got / 1e9:.2f} GB  {time.time() - t0:.0f}s  "
                      f"free {_free_gb():.1f} GB", flush=True)
    for asset_id, err in failed:
        print(f"{label}: FAILED {asset_id}: {err}", flush=True)
    return {"assets": len(ids), "failed": [a for a, _ in failed]}


def build_catalog():
    """Index everything on disk (Poly Haven, ambientCG, Kenney) into catalog.json."""
    items = []
    for kind in PH_KIND:
        meta = os.path.join(ROOT, "polyhaven", kind, "_assets.json")
        if not os.path.isfile(meta):
            continue
        with open(meta, encoding="utf-8") as f:
            assets = json.load(f)
        for asset_id, a in assets.items():
            folder = os.path.join(ROOT, "polyhaven", kind, asset_id)
            if not os.path.isdir(folder):
                continue
            main = [n for n in os.listdir(folder) if n.endswith((".blend", ".hdr"))]
            if not main:
                continue
            items.append({"source": "polyhaven", "kind": kind[:-1] if kind != "hdris" else "hdri",
                          "id": asset_id, "name": a.get("name"), "tags": a.get("tags", []),
                          "categories": a.get("categories", []), "dimensions_mm": a.get("dimensions"),
                          "path": os.path.relpath(os.path.join(folder, main[0]), ROOT).replace("\\", "/")})
    meta = os.path.join(ROOT, "ambientcg", "_assets.json")
    if os.path.isfile(meta):
        with open(meta, encoding="utf-8") as f:
            for a in json.load(f):
                folder = os.path.join(ROOT, "ambientcg", a["assetId"])
                if os.path.isfile(os.path.join(folder, ".done")):
                    items.append({"source": "ambientcg", "kind": "material", "id": a["assetId"],
                                  "name": a.get("displayName"), "tags": a.get("tags") or [],
                                  "categories": [c for c in (a.get("category"), a.get("displayCategory")) if c],
                                  "path": os.path.relpath(folder, ROOT).replace("\\", "/")})
    kenney = os.path.join(ROOT, "kenney")
    if os.path.isdir(kenney):
        for kit in sorted(os.listdir(kenney)):
            for dirpath, _dirs, names in os.walk(os.path.join(kenney, kit)):
                for name in names:
                    if name.endswith(".glb"):
                        stem = os.path.splitext(name)[0]
                        items.append({"source": "kenney", "kind": "model", "id": f"{kit}/{stem}",
                                      "name": stem.replace("-", " ").replace("_", " "),
                                      "tags": [kit.replace("kenney_", "")], "categories": ["low-poly"],
                                      "path": os.path.relpath(os.path.join(dirpath, name), ROOT).replace("\\", "/")})
    with open(CATALOG, "w", encoding="utf-8") as f:
        json.dump({"license": "CC0-1.0", "items": items}, f, indent=0)
    counts = {}
    for it in items:
        counts[(it["source"], it["kind"])] = counts.get((it["source"], it["kind"]), 0) + 1
    print("catalog:", ", ".join(f"{s} {k}: {n}" for (s, k), n in sorted(counts.items())), flush=True)


def main(argv):
    os.makedirs(ROOT, exist_ok=True)
    if "--catalog" in argv:
        build_catalog()
        return
    parts = [a for a in argv if not a.startswith("-")] or ["hdris", "ambientcg", "textures", "models"]
    try:
        for part in parts:
            fetch_ambientcg() if part == "ambientcg" else fetch_polyhaven(part)
    except DiskFull:
        print("stopped early for disk space; free some space and run again to resume", flush=True)
    finally:
        build_catalog()


if __name__ == "__main__":
    main(sys.argv[1:])
