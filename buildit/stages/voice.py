"""
Stage 4 - voice/: one file per beat (cached by text, voice and delivery), checked by Whisper (a misspoken beat
is said again once), trimmed and joined into voice/narration.wav with natural breaths: short inside a step,
longer where the story turns to its next problem.
"""
from __future__ import annotations

import hashlib
import logging
import os
import subprocess

from agents.voice import _misspoken
from config.paths import get_ffmpeg, get_ffprobe

from ..config import VOICE_REF
from ..runner import StageError
from ..voice.providers import provider, speak_beats
from .script import DELIVERY

log = logging.getLogger("pipeline")
LEAD_IN, GAP, TURN_GAP, TAIL, RATE = 0.2, 0.3, 0.55, 1.0, 48000
FIX_GAP = 0.8         # after a beat that adds a part: time to watch it click in


def inputs(run):
    lang = run.meta.get("lang", "en")
    ref = VOICE_REF.get(lang)
    return [run.path("script.json"), provider(), lang, ref if ref and os.path.exists(ref) else None]


def _dur(path):
    out = subprocess.run([get_ffprobe(), "-v", "error", "-show_entries", "format=duration", "-of",
                          "default=nw=1:nk=1", path], capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def _trim(src, dst):
    subprocess.run([get_ffmpeg(), "-v", "error", "-y", "-i", src, "-ac", "1", "-ar", str(RATE), "-af",
                    "silenceremove=start_periods=1:start_threshold=-48dB:start_silence=0.04,areverse,"
                    "silenceremove=start_periods=1:start_threshold=-48dB:start_silence=0.08,areverse,"
                    # long pauses inside a beat (between sentences) shrink to a quick breath: a snappy read
                    "silenceremove=stop_periods=-1:stop_duration=0.24:stop_threshold=-42dB:stop_silence=0.2",
                    dst], check=True)


def run(run):
    script = run.need("script.json")
    lang = run.meta.get("lang", "en")
    vdir = run.path("voice")
    os.makedirs(vdir, exist_ok=True)
    prev = {b["id"]: b for b in (run.load("voice/voice.json", {}) or {}).get("beats", [])}
    todo, keys = [], {}
    for b in script["beats"]:
        ex, cfg = DELIVERY.get(b.get("delivery", "lively"), (0.55, 0.45))
        h = hashlib.sha1(f"{provider()}|{lang}|{VOICE_REF.get(lang)}|{ex}|{cfg}|{b['narration']}".encode()
                         ).hexdigest()[:12]
        keys[b["id"]] = h
        wav = os.path.join(vdir, f"{b['id']}.wav")
        if not (prev.get(b["id"], {}).get("hash") == h and os.path.exists(wav)):
            todo.append({"id": b["id"], "text": b["narration"], "exaggeration": ex, "cfg_weight": cfg})
    if todo:
        raw = speak_beats(todo, vdir, lang)
        # Whisper hears each new beat; a misspoken one is said again once (another take, calmer delivery)
        again = [dict(it, exaggeration=max(0.4, it["exaggeration"] - 0.15), cfg_weight=0.5)
                 for it in todo if it["id"] in raw and lang == "en" and _misspoken(it["text"], raw[it["id"]])]
        if again:
            log.info("[voice] %d beat(s) misspoken, saying them again: %s", len(again), [a["id"] for a in again])
            raw.update(speak_beats(again, vdir, lang))
        for it in todo:
            if it["id"] not in raw:
                raise StageError(f"no audio for {it['id']}")
            _trim(raw[it["id"]], os.path.join(vdir, f"{it['id']}.wav"))
    beats, t = [], LEAD_IN
    roles = {b["id"]: b["role"] for b in script["beats"]}
    ids = [b["id"] for b in script["beats"]]
    cmd, chain = [get_ffmpeg(), "-v", "error", "-y"], []
    for k, bid in enumerate(ids):
        f = os.path.join(vdir, f"{bid}.wav")
        d = _dur(f)
        last = k == len(ids) - 1
        gap = TAIL if last else (FIX_GAP if roles[bid] == "fix" else
                                 TURN_GAP if roles[ids[k + 1]] in ("problem", "outro") else GAP)
        beats.append({"id": bid, "hash": keys[bid], "file": f"voice/{bid}.wav", "duration": round(d, 3),
                      "start": round(t, 3), "end": round(t + d, 3)})
        cmd += ["-i", f]
        chain.append(f"[{k}:a]adelay={int(LEAD_IN * 1000) if k == 0 else 0}:all=1,apad=pad_dur={gap}[p{k}]")
        t += d + gap
    out = run.path("voice", "narration.wav")
    filt = ";".join(chain) + ";" + "".join(f"[p{k}]" for k in range(len(ids))) + f"concat=n={len(ids)}:v=0:a=1[out]"
    subprocess.run(cmd + ["-filter_complex", filt, "-map", "[out]", "-ar", str(RATE), "-ac", "1", out], check=True)
    total = _dur(out)
    run.save("voice/voice.json", {"provider": provider(), "lang": lang, "beats": beats, "duration": round(total, 3)})
    log.info("[voice] narration %.1f s for %d beats", total, len(beats))


def validate(run):
    v = run.need("voice/voice.json")
    if not os.path.exists(run.path("voice", "narration.wav")):
        raise StageError("narration.wav missing")
    target = run.meta.get("length", 75)
    if not 0.75 * target <= v["duration"] <= 1.25 * target:
        raise StageError(f"narration runs {v['duration']:.1f} s for a {target} s target")
