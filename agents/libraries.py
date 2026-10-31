"""
Make sure every downloadable library the pipeline builds from is on this machine, BEFORE a run starts.

    python -m agents.libraries            # fetch whatever is missing (first time ~45 GB, ~30 min)
    python -m agents.libraries --status   # what is installed

The libraries are not in git (they are large and re-downloadable); this module is what makes a fresh clone
transportable: clone, then the first `python main.py` (or `python -m agents.director ...`) downloads them.
Each part leaves a stamp in assets/cc0/.stamps/ when it finished without failures, so later runs check in
milliseconds and never touch the network. Never fatal: a failed download is a warning, the run goes on with
what is there, and the next run retries the part (house rule: the pipeline never fails).

  LIBRARIES_AUTO=0     skip the check entirely (offline machines)
  LIBRARIES_PARTS=...  comma list to limit the parts (e.g. "kenney,quaternius,compositor")
"""
import importlib.util
import json
import logging
import os
import shutil
import subprocess
import sys
import time

from config.paths import COMPOSITOR, PROJECT_ROOT

log = logging.getLogger("pipeline")
ASSETS = os.path.join(PROJECT_ROOT, "assets")
STAMPS = os.path.join(ASSETS, "cc0", ".stamps")
VERSION = 1            # bump to make every machine re-check its libraries
TOLERANCE = 0.005      # a part with <= 0.5 % broken upstream records (2 of 2,037 ambientCG) still counts as done

# part -> (what it is, rough size) ; the order is the download order (small and essential first)
PARTS = {
    "python": ("Python packages in requirements.txt (a missing edge-tts left a run with no voice)", "0.1 GB"),
    "kenney": ("Kenney CC0 kits + sky HDRI (assets/fetch_cc0.py)", "0.2 GB"),
    "quaternius": ("Quaternius CC0 characters, animations, props (assets/fetch_quaternius.py)", "1.8 GB"),
    "compositor": ("Remotion compositor npm packages (compositor/)", "0.3 GB"),
    "sfx": ("Kenney CC0 audio + Sonniss GDC sound effects (assets/fetch_sfx.py)", "7.5 GB"),
    "music": ("Kevin MacLeod comedy music beds, CC BY 4.0 (assets/fetch_music.py)", "0.07 GB"),
    "chatterbox": ("Chatterbox TTS in its own env, tools/chatterbox (only when VOICE_ENGINE=chatterbox)", "3 GB"),
    "hdris": ("Poly Haven HDRIs, 2k", "6.4 GB"),
    "ambientcg": ("ambientCG PBR materials, 2K", "6 GB"),
    "textures": ("Poly Haven PBR textures, 2k", "18 GB"),
    "models": ("Poly Haven models, 2k", "13 GB"),
}


def _stamp(part):
    return os.path.join(STAMPS, f"{part}.json")


def installed(part):
    try:
        with open(_stamp(part), encoding="utf-8") as f:
            return json.load(f).get("version") == VERSION
    except (OSError, ValueError):
        return False


def _mark(part, info):
    os.makedirs(STAMPS, exist_ok=True)
    with open(_stamp(part), "w", encoding="utf-8") as f:
        json.dump(dict(info, version=VERSION, at=time.strftime("%Y-%m-%dT%H:%M:%S")), f)


def _script(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ASSETS, f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ok(result):
    if not isinstance(result, dict):
        return True
    return len(result.get("failed", [])) <= TOLERANCE * max(1, result.get("assets", 1))


def missing_packages():
    """requirements.txt entries not installed in this Python (name only; version pins are not enforced)."""
    from importlib import metadata
    import re as _re
    path = os.path.join(PROJECT_ROOT, "requirements.txt")
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return []
    missing = []
    for line in lines:
        name = _re.split(r"[<>=!~;\[ ]", line.split("#")[0].strip())[0]
        if not name:
            continue
        try:
            metadata.distribution(name)
        except metadata.PackageNotFoundError:
            missing.append(line.split("#")[0].strip())
    return missing


CHATTERBOX = os.path.join(PROJECT_ROOT, "tools", "chatterbox")


def _chatterbox_env():
    """tools/chatterbox/.venv: Python 3.10 + CUDA torch 2.6 + chatterbox-tts, isolated from the pipeline's env."""
    py = os.path.join(CHATTERBOX, ".venv", "Scripts" if os.name == "nt" else "bin",
                      "python.exe" if os.name == "nt" else "python")
    steps = []
    if not os.path.isfile(py):
        launcher = ["py", "-3.10"] if os.name == "nt" and shutil.which("py") else [sys.executable]
        steps.append(launcher + ["-m", "venv", os.path.join(CHATTERBOX, ".venv")])
    # a fresh venv's old pip trusts only its own certificate bundle and fails behind TLS inspection
    # (antivirus / proxy): bring truststore in through THIS env's pip, then upgrade pip with the system store
    wheels = os.path.join(CHATTERBOX, ".wheels")
    steps += [[sys.executable, "-m", "pip", "download", "truststore", "-d", wheels, "--only-binary=:all:"],
              [py, "-m", "pip", "install", "--no-index", "--find-links", wheels, "truststore"],
              [py, "-m", "pip", "install", "--use-feature=truststore", "--upgrade", "pip"]]
    steps += [[py, "-m", "pip", "install", "torch==2.6.0", "torchaudio==2.6.0", "--index-url",
               "https://download.pytorch.org/whl/cu124"],
              [py, "-m", "pip", "install", "chatterbox-tts"],
              [py, "-c", "import chatterbox, torch; assert torch.cuda.is_available()"]]
    for cmd in steps:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"{' '.join(cmd[:4])}: {(r.stderr or r.stdout)[-400:]}")
    return {"assets": 1, "failed": []}


def _fetch(part):
    if part == "python":
        missing = missing_packages()
        if missing:
            r = subprocess.run([sys.executable, "-m", "pip", "install", *missing], capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(r.stderr[-600:])
        return {"assets": 1, "failed": missing_packages()}
    if part == "chatterbox":
        return _chatterbox_env()
    if part == "kenney":
        _script("fetch_cc0").main()
        return {"assets": 1, "failed": []}
    if part == "quaternius":
        return _script("fetch_quaternius").main([])
    if part == "sfx":
        return _script("fetch_sfx").main([])
    if part == "music":
        return _script("fetch_music").main([])
    if part == "compositor":
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm") or shutil.which("npm")
        if not npm:
            raise RuntimeError("Node.js/npm is not installed (https://nodejs.org); the 2D layer needs it")
        # `ci` installs exactly the versions pinned in package-lock.json
        r = subprocess.run([npm, "ci", "--no-fund", "--no-audit"], cwd=COMPOSITOR, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(r.stderr[-600:])
        return {"assets": 1, "failed": []}
    lib = _script("fetch_library")
    try:
        return lib.fetch_ambientcg() if part == "ambientcg" else lib.fetch_polyhaven(part)
    finally:
        lib.build_catalog()


def ensure(parts=None):
    """Fetch every missing part; returns warnings (empty when all libraries are in place)."""
    if os.getenv("LIBRARIES_AUTO", "1") == "0":
        return []
    wanted = parts or [p.strip() for p in os.getenv("LIBRARIES_PARTS", ",".join(PARTS)).split(",") if p.strip()]
    # Python packages are checked on EVERY run (cheap, and a stamp cannot see a package removed later); the
    # 3 GB Chatterbox env only when it is the chosen voice
    if (os.getenv("VOICE_ENGINE") or "").strip().lower() != "chatterbox":
        wanted = [p for p in wanted if p != "chatterbox"]
    missing = [p for p in wanted if p in PARTS and (not installed(p) or (p == "python" and missing_packages()))]
    if not missing:
        return []
    log.info("libraries: fetching %s before the run (one-time; later runs skip this)",
             ", ".join(f"{p} (~{PARTS[p][1]})" for p in missing))
    warnings = []
    for part in missing:
        t0 = time.time()
        try:
            result = _fetch(part)
        except Exception as exc:
            warnings.append(f"library '{part}' could not be fetched: {str(exc)[:300]}")
            continue
        if _ok(result):
            _mark(part, {"seconds": round(time.time() - t0), "failed": (result or {}).get("failed", [])})
            log.info("libraries: %s ready (%.0f s)", part, time.time() - t0)
        else:
            warnings.append(f"library '{part}': {len(result['failed'])} of {result['assets']} items failed; "
                            "the next run retries them")
    for w in warnings:
        log.warning("QUALITY WARNING: %s", w)
    return warnings


def status():
    for part, (what, size) in PARTS.items():
        print(f"{'ok     ' if installed(part) else 'MISSING'} {part:<11} {size:>7}  {what}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    sys.path.insert(0, PROJECT_ROOT)
    if "--status" in sys.argv:
        status()
    else:
        ensure()
        status()
