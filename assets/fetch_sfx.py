"""
Download the free sound-effect libraries into assets/cc0/sfx/ and index them in assets/cc0/sfx/catalog.json.

    python assets/fetch_sfx.py              # fetch what is missing, then rebuild the catalog
    python assets/fetch_sfx.py --catalog    # only rebuild the catalog

  Kenney audio (kenney.nl)      CC0: impacts, foley, UI, RPG, sci-fi, jingles (~60 MB)
  Sonniss GDC 2026 bundle       royalty-free for media production, no attribution (gdc.sonniss.com);
                                professional field recordings and designed effects (7.5 GB zipped)

Neither may be redistributed as a sound library, so they stay out of git (assets/cc0/ is ignored) and every
machine fetches them at the start of its first run (agents/libraries.py, part "sfx").
"""
import json
import os
import re
import sys
import time
import wave
import zipfile

import requests

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cc0", "sfx")
CATALOG = os.path.join(ROOT, "catalog.json")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"}
MIN_FREE_GB = float(os.getenv("LIBRARY_MIN_FREE_GB", "15"))

KENNEY = ["impact-sounds", "interface-sounds", "rpg-audio", "sci-fi-sounds", "digital-audio", "ui-audio",
          "music-jingles", "casino-audio"]
SONNISS = [f"https://downloads.sonniss.com/Sonniss.com-GDC2026-GameAudioBundle{k}of5.zip" for k in range(1, 6)]
SOURCES = {"kenney": "CC0", "sonniss": "Sonniss GDC royalty-free (media production, no attribution)"}
EXTS = (".wav", ".ogg", ".mp3", ".flac")


def _free_gb():
    import shutil
    return shutil.disk_usage(os.path.dirname(ROOT) if os.path.isdir(os.path.dirname(ROOT)) else ".").free / 1e9


def _download(url, path):
    """Resumable streamed download (HTTP Range); returns path."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    part = path + ".part"
    have = os.path.getsize(part) if os.path.isfile(part) else 0
    headers = dict(UA, **({"Range": f"bytes={have}-"} if have else {}))
    with requests.get(url, headers=headers, stream=True, timeout=120) as r:
        if r.status_code == 416:            # already complete
            os.replace(part, path)
            return path
        r.raise_for_status()
        mode = "ab" if have and r.status_code == 206 else "wb"
        with open(part, mode) as fh:
            for chunk in r.iter_content(1 << 22):
                fh.write(chunk)
    os.replace(part, path)
    return path


def _extract(zpath, target):
    with zipfile.ZipFile(zpath) as z:
        z.extractall(target)
    os.remove(zpath)


def fetch_kenney():
    failed = []
    session = requests.Session()
    session.headers.update(UA)
    for slug in KENNEY:
        target = os.path.join(ROOT, "kenney", slug)
        if os.path.isdir(target) and os.listdir(target):
            continue
        try:
            page = f"https://kenney.nl/assets/{slug}"
            session.get(page, timeout=60)           # the signed link is only handed to a visitor of the page
            link = session.get(f"https://kenney.nl/download-link/{('assets/' + slug).encode().hex()}",
                               headers={"Referer": page}, timeout=60).json()["url"]
            _extract(_download(link, os.path.join(ROOT, "_zip", f"kenney_{slug}.zip")), target)
            print(f"get   kenney {slug}")
        except Exception as exc:  # noqa: BLE001  (never fatal; retried next run)
            print(f"FAIL  kenney {slug}: {exc}")
            failed.append(f"kenney/{slug}")
    return failed


def fetch_sonniss():
    failed = []
    for url in SONNISS:
        name = os.path.splitext(os.path.basename(url))[0]
        target = os.path.join(ROOT, "sonniss", name)
        if os.path.isdir(target) and os.listdir(target):
            continue
        if _free_gb() < MIN_FREE_GB + 3.5:
            print(f"SKIP  {name}: less than {MIN_FREE_GB + 3.5:.0f} GB free")
            failed.append(f"sonniss/{name}")
            continue
        try:
            t0 = time.time()
            _extract(_download(url, os.path.join(ROOT, "_zip", f"{name}.zip")), target)
            print(f"get   {name} ({time.time() - t0:.0f} s)")
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL  {name}: {exc}")
            failed.append(f"sonniss/{name}")
    return failed


def _seconds(path):
    if path.lower().endswith(".wav"):
        try:
            with wave.open(path) as w:
                return round(w.getnframes() / float(w.getframerate()), 2)
        except Exception:  # noqa: BLE001  (24-bit float or odd headers: fall back to the size estimate)
            pass
    return None


def tokens(text):
    """Lower-case words of a file / folder name ('DSGNImpt_Metal Hit 01' -> dsgnimpt, metal, hit)."""
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    return sorted({t for t in re.split(r"[^a-z]+", text.lower()) if len(t) > 2})


def build_catalog():
    rows = []
    for source in SOURCES:
        base = os.path.join(ROOT, source)
        for dirpath, _dirs, names in os.walk(base):
            rel_dir = os.path.relpath(dirpath, base)
            folder = tokens(" ".join(rel_dir.split(os.sep)[1:]))    # skip the pack folder name itself
            for n in names:
                if not n.lower().endswith(EXTS):
                    continue
                p = os.path.join(dirpath, n)
                rows.append({"path": os.path.relpath(p, ROOT).replace("\\", "/"), "source": source,
                             "words": tokens(os.path.splitext(n)[0]), "folder": folder, "seconds": _seconds(p)})
    os.makedirs(ROOT, exist_ok=True)
    with open(CATALOG, "w", encoding="utf-8") as fh:
        json.dump({"licenses": SOURCES, "sounds": rows}, fh)
    print(f"catalog: {len(rows)} sounds -> {CATALOG}")
    return rows


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    failed = [] if "--catalog" in argv else fetch_kenney() + fetch_sonniss()
    rows = build_catalog()
    return {"assets": len(KENNEY) + len(SONNISS), "failed": failed, "sounds": len(rows)}


if __name__ == "__main__":
    main()
