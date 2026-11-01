"""
Stage 6b - assets: the HDRI, fonts, the music bed and one sound effect per cue, every one logged with its
licence in runs/<slug>/credits.json.

Sound effects come through HyperFrames media-use (Openverse CC0 / CC BY, then its bundled library) and are
cached once in cutaway/assets/sfx/ with their provenance. Music is a Kevin MacLeod (incompetech) track,
CC BY 4.0, credited in post.txt.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import time
import urllib.parse

import requests

from .. import hf, kits
from ..assets.fetch import _download, font, load_credits, polyhaven_hdri
from ..config import ASSETS
from ..runner import StageError
from .render import HDRI

log = logging.getLogger("pipeline")
SFX_DIR = os.path.join(ASSETS, "sfx")
SFX_INDEX = os.path.join(SFX_DIR, "sfx.json")
MUSIC_DIR = os.path.join(ASSETS, "music")
INCOMPETECH = "https://incompetech.com/music/royalty-free/mp3-royaltyfree/"
MUSIC_CREDIT = ('"{title}" Kevin MacLeod (incompetech.com). Licensed under Creative Commons: By Attribution 4.0 '
                'License, http://creativecommons.org/licenses/by/4.0/')
MUSIC = ["Volatile Reaction", "Ouroboros", "Lightless Dawn"]      # driving, modern, under a voice

CUES = {                       # cue -> search intents, best first (Openverse matches short phrases best)
    "whoosh": ["whoosh", "swoosh"],
    "click": ["valve tick", "ratchet click", "mechanical click", "switch click", "click"],
    "ignition": ["fire whoosh", "gas ignition", "whoomp", "ignition", "explosion"],
    "spark": ["electric spark", "spark", "zap"],
    "hiss": ["steam hiss", "hiss"],
    "rumble": ["engine rumble", "deep rumble", "thunder rumble", "rumble"],
    "clunk": ["metal clunk", "metal clank", "heavy latch", "lever pull", "metal impact", "metal hit"],
    "riser": ["riser", "cinematic riser"],
    "impact": ["impact", "cinematic impact"],
}
# a resolved sound must say what it is: media-use does not match by meaning, we judge
KEYWORDS = {"whoosh": ["whoosh", "swoosh", "swish"], "click": ["click", "tick", "ratchet"],
            "ignition": ["ignit", "explo", "fire", "whoomp", "burst", "flame", "boom", "blast"], "spark": ["spark", "zap", "electric"], "hiss": ["hiss", "steam"],
            "rumble": ["rumbl", "thunder", "engine", "roar"],
            "clunk": ["clunk", "clank", "thud", "latch", "lever", "metal hit", "metal impact"],
            "riser": ["riser", "rise"], "impact": ["impact", "hit", "slam", "boom"],
            "bed": ["engine", "idle", "motor", "hum", "turbine", "machin"]}
NOT = {"click": ["ui", "tap", "selection", "interface", "mouse"], "clunk": ["bottle", "glass", "digital", "glitch"],
       "ignition": ["flak", "gun", "digital"], "whoosh": ["cartoon"]}


def fits(cue: str, description: str) -> bool:
    d = (description or "").lower()
    return any(k in d for k in KEYWORDS.get(cue, [cue])) and not any(k in d for k in NOT.get(cue, []))


def inputs(run):
    kit = kits.KITS[run.need("brief.json")["kit"]]
    return [sorted(CUES), kit.get("bed"), MUSIC]


def _mu_project() -> str:
    d = os.path.join(SFX_DIR, "_mu")
    if not os.path.exists(os.path.join(d, "hyperframes.json")):
        os.makedirs(SFX_DIR, exist_ok=True)
        hf.run(["init", d], cwd=SFX_DIR)
    return d


def _index() -> dict:
    if os.path.exists(SFX_INDEX):
        with open(SFX_INDEX, encoding="utf-8") as f:
            return json.load(f)
    return {}


# Cues where the pipeline's own CC0 finder (local libraries + BigSoundBank) beats a generic search
CC0_QUERIES = {"click": ["mechanical click", "relay click"], "clunk": ["car door", "lock", "metal impact"],
               "ignition": ["muffled explosion", "explosion"]}


def _cc0(cue: str) -> dict | None:
    from agents.sfx_library import find
    for q in CC0_QUERIES.get(cue, []):
        try:
            p = find(q)
        except Exception:                                  # noqa: BLE001  (offline: fall through)
            p = None
        if p and os.path.exists(p):
            name = f"{cue}{os.path.splitext(p)[1]}"
            shutil.copyfile(p, os.path.join(SFX_DIR, name))
            src = "bigsoundbank.com" if "bigsoundbank" in p else "local CC0 library"
            return {"file": name, "intent": q, "description": os.path.basename(p), "license": "cc0",
                    "credit": f"{os.path.basename(p)} ({src}, CC0)", "source_url": f"https://{src}" if
                    "bigsoundbank" in p else None, "provider": src}
    return None


def sfx(cue: str, intents: list[str]) -> dict | None:
    """One cached sound per cue: {file, credit, license, source_url, intent}."""
    idx = _index()
    if cue in CC0_QUERIES and (cue not in idx or idx[cue].get("provider") not in ("bigsoundbank.com",
                                                                                 "local CC0 library")):
        entry = _cc0(cue)
        if entry:
            idx[cue] = entry
            with open(SFX_INDEX, "w", encoding="utf-8") as f:
                json.dump(idx, f, indent=1)
            log.info("[assets] sfx %s <- %s (CC0)", cue, entry["description"])
            return entry
    if cue in idx and os.path.exists(os.path.join(SFX_DIR, idx[cue]["file"])) and             fits(cue, idx[cue].get("description")):
        return idx[cue]
    proj = _mu_project()
    for intent in intents:
        for attempt in range(3):
            r = hf.run(["media-use", "resolve", "--type", "sfx", "--intent", intent, "--project", "."], cwd=proj,
                       check=False, timeout=240)
            out = (r.stdout or "") + (r.stderr or "")
            if "resolved " in out:
                rid = out.split("resolved ", 1)[1].split()[0]
                rec = None
                with open(os.path.join(proj, ".media", "manifest.jsonl"), encoding="utf-8") as f:
                    for line in f:
                        d = json.loads(line)
                        if d["id"] == rid:
                            rec = d
                desc = ((rec or {}).get("description") or "").lower()
                if rec is None or not fits(cue, desc):
                    log.info("[assets] sfx %s: '%s' does not fit, next phrasing", cue, desc[:60])
                    break
                ext = os.path.splitext(rec["path"])[1]
                name = f"{cue}{ext}"
                shutil.copyfile(os.path.join(proj, rec["path"]), os.path.join(SFX_DIR, name))
                prov = rec.get("provenance", {})
                entry = {"file": name, "intent": intent, "description": rec.get("description"),
                         "license": prov.get("license", "bundled"), "credit": prov.get("credit"),
                         "source_url": prov.get("source_url"), "provider": prov.get("provider", "bundled")}
                idx = _index()
                idx[cue] = entry
                with open(SFX_INDEX, "w", encoding="utf-8") as f:
                    json.dump(idx, f, indent=1)
                log.info("[assets] sfx %s <- %s (%s)", cue, entry["description"], entry["license"])
                return entry
            if "no provider could resolve" in out and "unreachable" not in out:
                break                                  # nothing for this phrase: try the next intent
            time.sleep(3)                              # Openverse timeouts are common: retry
    log.warning("[assets] no sound for cue '%s'", cue)
    return None


def music() -> dict:
    os.makedirs(MUSIC_DIR, exist_ok=True)
    for title in MUSIC:
        path = os.path.join(MUSIC_DIR, f"{title}.mp3")
        try:
            if not os.path.exists(path):
                _download(INCOMPETECH + urllib.parse.quote(title) + ".mp3", path)
            return {"title": title, "file": path, "license": "CC BY 4.0", "author": "Kevin MacLeod",
                    "credit": MUSIC_CREDIT.format(title=title), "source_url": "https://incompetech.com"}
        except requests.RequestException as exc:
            log.warning("[assets] music %s unavailable: %s", title, exc)
    raise StageError("no music track could be downloaded")


def run(run):
    kit = kits.KITS[run.need("brief.json")["kit"]]
    hdri = polyhaven_hdri(HDRI)
    anton = font()
    m = music()
    cues = dict(CUES)
    if kit.get("bed"):
        cues["bed"] = kit["bed"]
    sounds = {c: sfx(c, intents) for c, intents in cues.items()}
    lib = load_credits()
    credits = {
        "hdri": lib.get(f"hdri/{HDRI}"),
        "font": lib.get("font/Anton-Regular.ttf"),
        "music": {k: m[k] for k in ("title", "license", "author", "credit", "source_url")},
        "sfx": {c: {k: v for k, v in s.items() if k != "file"} for c, s in sounds.items() if s},
        "voice": "agents.voice (ElevenLabs, or the pipeline's configured free fallback)",
        "models": "built procedurally in Blender by Cutaway Studio (cutaway/blender), no third-party meshes",
    }
    run.save("credits.json", credits)
    run.save("assets.json", {"hdri": hdri, "font": anton, "music": m["file"],
                             "sfx": {c: os.path.join(SFX_DIR, s["file"]) for c, s in sounds.items() if s}})


def validate(run):
    a = run.need("assets.json")
    for k in ("hdri", "font", "music"):
        if not os.path.exists(a[k]):
            raise StageError(f"asset {k} missing: {a[k]}")
    missing = [c for c in ("whoosh", "ignition") if c not in a["sfx"]]
    if missing:
        raise StageError(f"essential sound effects missing: {missing}")
