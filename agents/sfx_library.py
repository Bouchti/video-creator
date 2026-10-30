"""
Realistic sound-effect library, generated ONCE with ElevenLabs' text-to-sound-effects API and
cached in assets/sfx/ (then reused by every video, so it costs credits only the first time).

Each entry: name → (prompt, seconds or None for auto, loop?). One-shots are placed on the frame
an animation event happens; loops are tiled with crossfades to any length. sfx.render_events()
uses a library sound when one exists for an event kind and falls back to the synthesized one.

    python -m agents.sfx_library          # generate whatever is missing
"""
import logging
import math
import os
import subprocess

import numpy as np
import requests

from config.paths import PROJECT_ROOT

log = logging.getLogger("pipeline")
SR = 44100
LIB_DIR = os.path.join(PROJECT_ROOT, "assets", "sfx")

# name: (prompt, duration seconds (None = let the model decide), loop)
LIBRARY = {
    # ---- characters / comedy ----
    "step": ("a single soft footstep on grass", 0.5, False),
    "hammer": ("a hammer hitting a nail into a wooden plank, one sharp hit", 0.8, False),
    "boing": ("cartoon spring boing sound effect", 0.9, False),
    "whoosh": ("short quick cartoon swoosh of something jumping", 0.6, False),
    "kids_cheer": ("two young children cheering and laughing outdoors, yay", 3.0, False),
    "snore": ("cartoon man snoring loudly, two snores", 3.5, False),
    "scratch": ("vinyl record scratch sound effect", 1.0, False),
    "rewind": ("VHS tape rewinding fast, whirring", 3.0, True),
    "pop": ("soft bubbly UI pop", 0.4, False),
    "splash": ("person doing a cannonball jump into a swimming pool, big splash", 2.0, False),
    # ---- construction (pool) ----
    "engine": ("small excavator diesel engine running steadily, outdoors", 6.0, True),
    "engine_rev": ("small excavator diesel engine revving and tracks moving", 4.0, True),
    "scoop": ("excavator bucket digging into dirt and soil", 1.5, False),
    "dump": ("excavator dumping a bucket of dirt onto a pile", 1.5, False),
    "clink": ("steel rebar bars clanking together", 0.8, False),
    "tile": ("ceramic tile placed on a wall, light clack", 0.5, False),
    "spray": ("concrete being sprayed from a high pressure hose, hissing", 5.0, True),
    "pour": ("water pouring from a garden hose into a pool", 6.0, True),
    "pump": ("swimming pool pump motor humming", 5.0, True),
    "crack": ("concrete wall cracking loudly", 1.5, False),
    "rain": ("heavy rain falling on grass and a garden", 8.0, True),
    "thunder": ("distant thunder rumble", 3.0, False),
    # ---- plane ----
    "plane_start": ("small propeller airplane engine starting, sputtering then running", 4.0, False),
    "plane_engine": ("small propeller airplane engine running steadily, close", 6.0, True),
    "plane_flyby": ("small propeller airplane flying past close, doppler", 5.0, False),
    "crash_tree": ("small wooden airplane crashing into a big tree, branches snapping, leaves rustling", 2.5, False),
    "hay_thud": ("wooden cart rolling into hay bales, soft thud", 1.2, False),
    "flop": ("light wooden airplane flopping onto grass, clattering thud", 1.5, False),
    "roll": ("wooden wheels rolling over a grassy dirt field", 4.0, True),
    "pant": ("man panting out of breath, comedic", 2.0, False),
    # ---- nuclear station ----
    "alarm": ("industrial alarm klaxon siren blaring, two cycles, cartoonish", 3.0, False),
    "boil": ("big tank of water boiling violently, bubbling and gurgling", 6.0, True),
    "steam_hiss": ("loud steam hissing out of a pressure valve", 2.5, False),
    "turbine": ("large steam turbine spinning fast, whine and hum", 6.0, True),
    "hum": ("electric power generator humming steadily", 6.0, True),
    "geiger": ("Geiger counter, a single short burst of clicks", 0.5, False),
    "switch": ("big heavy electrical lever switch pulled down, loud clunk", 1.0, False),
    "power_up": ("electricity powering up, rising electric hum as lights switch on", 2.5, False),
    "rods_slide": ("heavy metal rods sliding down smoothly into tubes, mechanical whirr", 2.5, False),
    # ---- boat ----
    "weld": ("arc welding steel, crackling buzzing sparks", 5.0, True),
    "bubbles": ("underwater bubbles rising, gurgling", 5.0, True),
    "underwater_thud": ("heavy metal block hitting a sandy lake bottom underwater, muffled thud", 1.5, False),
    "creak": ("metal boat hull groaning and creaking as it tilts", 2.0, False),
    "rivet_pop": ("metal rivet popping out with a sharp ping", 0.8, False),
    "water_rush": ("water gushing into a boat through a hole, rushing", 5.0, True),
    "boat_motor": ("small boat outboard motor running, puttering steadily", 6.0, True),
    "paddle_splash": ("hands splashing in lake water, paddling", 0.8, False),
    "quack": ("a single duck quacking twice, comedic", 1.2, False),
    "ship_horn": ("huge container ship horn blast, deep and long, in the distance", 4.0, False),
    "lake": ("calm lake water gently lapping against a boat and a wooden dock", 10.0, True),
    # ---- bridge evolution ----
    "rumble": ("deep earth rumble, ground shifting and grinding slowly", 5.0, True),
    "stone_thud": ("heavy cut stone block dropped into place on stone, solid thud", 1.0, False),
    "steel_clank": ("steel girder bolted into place, heavy metallic clank", 0.8, False),
    "train_pass": ("old steam train crossing a steel bridge, rhythmic clatter", 6.0, True),
    "traffic": ("light car traffic driving across a bridge, steady whoosh of passing cars", 8.0, True),
    "bridge_groan": ("huge steel bridge groaning and creaking under stress, low metallic moan", 2.5, False),
    # ---- ambience ----
    "birds": ("countryside birds chirping, peaceful daytime ambience", 10.0, True),
    "wind": ("gentle wind over a grassy field", 8.0, True),
}


def path(name):
    return os.path.join(LIB_DIR, f"{name}.mp3")


def _keys():
    from agents.voice import _elevenlabs_keys
    return _elevenlabs_keys()


def generate(name, force=False):
    """Generate one library sound with ElevenLabs (rotating through the configured keys). A name outside
    LIBRARY is generated from its own words ('rocket_launch' -> 'rocket launch, sound effect')."""
    prompt, secs, loop = LIBRARY.get(name) or (f"{name.replace('_', ' ')}, realistic sound effect", None, False)
    out = path(name)
    if os.path.exists(out) and not force:
        return out
    os.makedirs(LIB_DIR, exist_ok=True)
    body = {"text": prompt, "prompt_influence": 0.5}
    if secs:
        body["duration_seconds"] = max(0.5, min(22.0, secs))
    errors = []
    for slot, key in _keys():
        r = requests.post("https://api.elevenlabs.io/v1/sound-generation", headers={"xi-api-key": key},
                          json=body, timeout=120)
        if r.status_code == 200 and r.content:
            with open(out, "wb") as f:
                f.write(r.content)
            log.info(f"  sfx library: generated '{name}' ({slot})")
            return out
        errors.append(f"{slot}: {r.status_code}")
    raise RuntimeError(f"could not generate sound '{name}': {errors}")


def ensure(names=None):
    """Generate every missing library sound (or just `names`). Failures fall back to synthesis."""
    for name in names or LIBRARY:
        if not os.path.exists(path(name)):
            try:
                generate(name)
            except Exception as e:                          # never block a render on a sound
                log.warning(f"  sfx library: {e}")


_cache = {}

# ---- the downloaded libraries (assets/fetch_sfx.py: Kenney CC0 + Sonniss GDC), searched by name ----
CC0_SFX = os.path.join(PROJECT_ROOT, "assets", "cc0", "sfx")
LOOP_WORDS = {"loop", "ambience", "amb", "ambient", "background", "room", "tone", "rain", "wind", "crowd", "engine",
              "idle", "drone", "hum", "traffic", "stream", "river", "waves", "forest", "birds", "machine"}
_index = None


# words a script uses -> the word sound libraries use for the same thing
SYNONYMS = {"kid": "child", "kids": "child", "children": "child", "slam": "close", "shut": "close",
            "cheer": "cheer", "yay": "cheer", "hooray": "cheer", "break": "broke", "shatter": "broke",
            "smash": "broke", "broken": "broke", "shutter": "camera", "giggle": "laugh", "chuckle": "laugh",
            "boom": "explosion", "blast": "explosion", "car": "car", "auto": "car", "automobile": "car",
            "punch": "punch", "hit": "impact", "thud": "impact", "bump": "impact", "zap": "electric",
            "spark": "electric", "beep": "beep", "bleep": "beep", "clap": "applause", "clapping": "applause",
            "footstep": "step", "footsteps": "step", "steps": "step", "walking": "step"}


def _stem(w):
    for suffix in ("ing", "ed", "es", "s"):
        if len(w) > len(suffix) + 3 and w.endswith(suffix):
            return w[: -len(suffix)]
    return w


def _words(text):
    import re
    out = []
    for w in re.split(r"[^a-z]+", text.lower().replace("_", " ")):
        if len(w) > 2:
            out.append(_stem(SYNONYMS.get(w, w)))
    return out


def _catalog():
    """(rows, idf) from assets/cc0/sfx/catalog.json; empty when the library is not downloaded."""
    global _index
    if _index is None:
        import json
        import math
        try:
            with open(os.path.join(CC0_SFX, "catalog.json"), encoding="utf-8") as fh:
                rows = json.load(fh)["sounds"]
        except (OSError, ValueError, KeyError):
            rows = []
        for r in rows:
            _prep(r)
        df = {}
        for r in rows:
            for w in r["_w"] | r["_f"]:
                df[w] = df.get(w, 0) + 1
        _index = (rows, {w: math.log(1 + len(rows) / c) for w, c in df.items()})
    return _index


def _prep(r):
    r["_w"] = set(_words(" ".join(r["words"])))
    r["_f"] = set(_words(" ".join(r["folder"])))
    base = os.path.basename(r["path"])
    # Sonniss names start with a UCS category id ("WINDGust_", "DOORWood_"): the most reliable meaning
    r["_cat"] = base.split("_")[0].lower() if "_" in base and base.split("_")[0][:2].isupper() else ""
    return r


def _local(q, loop):
    """(path, confident) of the best downloaded sound for query words q, or (None, False)."""
    rows, idf = _catalog()
    best, best_score, best_conf = None, 0.0, False
    wants_loop = loop if loop is not None else bool(LOOP_WORDS & set(q))
    for r in rows:
        cat = [w for w in q if r["_cat"].startswith(w)]
        hit = [w for w in q if w in r["_w"] or w in r["_f"] or w in cat]
        if len(hit) < len(set(q)):
            continue
        score = sum(idf.get(w, 0) * (1.0 if w in r["_w"] else 0.5) for w in set(q)) + 2.0 * len(cat)
        secs = r.get("seconds") or 3.0
        score -= 0.3 * abs(math.log(max(secs, 0.2) / (12.0 if wants_loop else 1.5)))
        score -= 0.05 * len(r["_w"])                         # plain names beat long composite ones
        if score > best_score:
            # confident = the category agrees, or the query is most of what the file name says
            best, best_score = r, score
            best_conf = bool(cat) or len(set(q)) / max(1, len(r["_w"])) >= 0.5
    return (os.path.join(CC0_SFX, best["path"]) if best else None), best_conf


def _online(q):
    """BigSoundBank (CC0) search for query words q: the best-named hit is downloaded once into
    assets/cc0/sfx/bigsoundbank/ and added to the catalog. None on any failure (never fatal)."""
    if os.getenv("SFX_ONLINE", "1") == "0":
        return None
    import json
    import re
    ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"}
    try:
        best, best_score = None, 0.0
        # at least half the words, always including the LAST one: in a sound name it is the sound itself
        # ("door slam", "water splash", "kids cheer"), the earlier words only say what makes it
        need = max(1, math.ceil(len(set(q)) / 2))
        for term in (" ".join(q), q[-1]):
            html = requests.get("https://bigsoundbank.com/search", params={"q": term}, headers=ua,
                                timeout=30).text
            for slug, sid in set(re.findall(r"/([a-z0-9-]+)-s(\d{4})\.html", html)):
                words = set(_words(slug))
                common = len(set(q) & words)
                score = common - 0.1 * len(words)
                if q[-1] in words and common >= need and score > best_score:
                    best, best_score = (slug, sid), score
            if best is not None:
                break
        if best is None:
            return None
        slug, sid = best
        rel = f"bigsoundbank/{slug}-s{sid}.mp3"
        out = os.path.join(CC0_SFX, rel)
        if not os.path.isfile(out):
            r = requests.get(f"https://bigsoundbank.com/UPLOAD/mp3/{sid}.mp3", headers=ua, timeout=60)
            r.raise_for_status()
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "wb") as fh:
                fh.write(r.content)
            cat_path = os.path.join(CC0_SFX, "catalog.json")
            try:
                with open(cat_path, encoding="utf-8") as fh:
                    cat = json.load(fh)
            except (OSError, ValueError):
                cat = {"licenses": {}, "sounds": []}
            cat.setdefault("licenses", {})["bigsoundbank"] = "CC0"
            row = {"path": rel, "source": "bigsoundbank", "words": sorted(_words(slug)), "folder": [],
                   "seconds": None}
            cat["sounds"].append(row)
            with open(cat_path, "w", encoding="utf-8") as fh:
                json.dump(cat, fh)
            if _index is not None:
                _index[0].append(_prep(dict(row)))
            log.info(f"  sfx: fetched '{slug}' from BigSoundBank (CC0)")
        return out
    except Exception as e:  # noqa: BLE001  (offline or site change: the local match or synthesis is used)
        log.warning(f"  sfx: online lookup for '{' '.join(q)}' failed: {e}")
        return None


def find(query, loop=None):
    """Best sound for a free-text name ('door_slam', 'kids cheering'), or None.
    Local libraries first (every query word must appear in the file name, folder or category; idf-weighted,
    duration-matched); when that match is missing or weak, BigSoundBank is searched online and the hit
    cached. A weak local match is still better than nothing."""
    q = _words(query)
    if not q:
        return None
    path_, confident = _local(q, loop)
    if confident:
        return path_
    return _online(q) or path_


def _source(name):
    """Cached generated sound first, then the downloaded libraries (+ BigSoundBank online), and last a newly
    generated sound (ElevenLabs, cached in assets/sfx/ and committed, so each name is paid for once)."""
    p = path(name)
    if os.path.exists(p):
        return p
    found = find(name)
    if found or os.getenv("SFX_GENERATE", "1") == "0":
        return found
    try:
        return generate(name)
    except Exception as e:  # noqa: BLE001  (no key / no credit: the event falls back to synthesis)
        log.warning(f"  sfx: no sound for '{name}': {e}")
        return None


def load(name):
    """Mono float32 samples at SR, loudness-normalised, or None when no sound fits the name."""
    if name in _cache:
        return _cache[name]
    p = _source(name)
    if p is None:
        _cache[name] = None
        return None
    from agents.media import FFMPEG
    raw = subprocess.run([FFMPEG, "-v", "error", "-i", p, "-t", "20", "-ac", "1", "-ar", str(SR), "-f", "s16le",
                          "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    if len(x) == 0:
        return None
    x = x / max(1e-4, float(np.sqrt(np.mean(x ** 2)))) * 0.12        # same loudness for every sample
    peak = float(np.abs(x).max())
    if peak > 0.98:
        x *= 0.98 / peak
    _cache[name] = x
    return x


def is_loop(name):
    if name in LIBRARY:
        return LIBRARY[name][2]
    return bool(LOOP_WORDS & set(_words(name)))


def tiled(name, seconds, fade=0.35):
    """A loop sound stretched to `seconds` with seamless crossfades and soft in/out fades."""
    x = load(name)
    if x is None:
        return None
    n = int(SR * seconds)
    xf = min(int(SR * 0.4), len(x) // 3)
    out = np.zeros(n + len(x))
    pos, ramp = 0, np.linspace(0, 1, xf) if xf else None
    while pos < n:
        seg = x.copy()
        if xf and pos:
            seg[:xf] *= ramp
            out[pos:pos + xf] *= ramp[::-1]
        out[pos:pos + len(seg)] += seg
        pos += len(seg) - xf
    out = out[:n]
    k = min(int(SR * fade), n // 2)
    if k:
        out[:k] *= np.linspace(0, 1, k)
        out[-k:] *= np.linspace(1, 0, k)
    return out


def varied(name, seed=0):
    """A one-shot with a slight random pitch/speed change, so repeats (steps, hammer) don't sound cloned."""
    x = load(name)
    if x is None:
        return None
    rate = 1.0 + (((seed * 2654435761) % 1000) / 1000 - 0.5) * 0.12
    idx = np.arange(0, len(x) - 1, rate)
    return np.interp(idx, np.arange(len(x)), x).astype(np.float32)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ensure()
    print(f"{sum(os.path.exists(path(n)) for n in LIBRARY)}/{len(LIBRARY)} sounds in {LIB_DIR}")
