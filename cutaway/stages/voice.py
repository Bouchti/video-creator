"""
Stage 4 - narration with the pipeline's own voices, one file per beat, joined into voice/narration.wav with
natural pauses: a short breath inside a chapter, a longer one where the story moves on.

CUTAWAY_VOICE_ENGINE picks the engine: "chatterbox" (default; local, expressive per sentence, chosen by the
user on 2026-11-01 when ElevenLabs ran out) or "elevenlabs" (agents.voice.generate_voiceover: ElevenLabs,
then the configured free fallback).

Each beat is cached by its text and engine, so a re-run only re-voices changed beats.
"""
from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess

from agents import voice as shared_voice
from config.paths import get_ffmpeg, get_ffprobe

from ..runner import StageError

log = logging.getLogger("pipeline")
VOICE = os.getenv("CUTAWAY_VOICE", "storyteller")
ENGINE = os.getenv("CUTAWAY_VOICE_ENGINE", "chatterbox")
LEAD_IN = 0.20          # silence before the first word (a caption at exactly 0 s looks pre-existing)
GAP = 0.28              # breath between beats of one chapter
CHAPTER_GAP = 0.55      # pause where the story moves to its next chapter
TAIL = 0.6
RATE = 48000


def inputs(run):
    return [run.path("script.json"), VOICE, ENGINE]


def speak(text: str) -> str:
    """One beat's narration file from the chosen engine (the shared voice module, by import only)."""
    if ENGINE == "elevenlabs":
        return shared_voice.generate_voiceover(text, voice=VOICE)[0]
    return shared_voice._fallback_voiceover(text, VOICE, ENGINE)


def _dur(path: str) -> float:
    out = subprocess.run([get_ffprobe(), "-v", "error", "-show_entries", "format=duration", "-of",
                          "default=nw=1:nk=1", path], capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def _to_wav(src: str, dst: str):
    subprocess.run([get_ffmpeg(), "-v", "error", "-y", "-i", src, "-ac", "1", "-ar", str(RATE),
                    "-af", "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.03,"
                           "areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.06,areverse",
                    dst], check=True)


def run(run):
    script = run.need("script.json")
    vdir = run.path("voice")
    os.makedirs(vdir, exist_ok=True)
    prev = {b["id"]: b for b in (run.load("voice/voice.json", {}) or {}).get("beats", [])}
    beats = []
    for b in script["beats"]:
        h = hashlib.sha1(f"{ENGINE}|{VOICE}|{b['narration']}".encode()).hexdigest()[:12]
        wav = os.path.join(vdir, f"{b['id']}.wav")
        old = prev.get(b["id"])
        if not (old and old.get("hash") == h and os.path.exists(wav)):
            tmp = speak(b["narration"])
            raw = os.path.join(vdir, f"{b['id']}_raw{os.path.splitext(tmp)[1] or '.mp3'}")
            shutil.copyfile(tmp, raw)
            _to_wav(raw, wav)
            log.info("[voice] %s voiced (%.2f s)", b["id"], _dur(wav))
        beats.append({"id": b["id"], "hash": h, "file": f"voice/{b['id']}.wav", "duration": round(_dur(wav), 3),
                      "mechanism": b["mechanism"]})
    gaps = [GAP if a["mechanism"] == c["mechanism"] else CHAPTER_GAP for a, c in zip(beats, beats[1:])] + [TAIL]
    # join: lead-in, beat, gap, beat, ..., tail (each beat delayed/padded so the times below are exact)
    t = LEAD_IN
    cmd = [get_ffmpeg(), "-v", "error", "-y"]
    chain = []
    for k, b in enumerate(beats):
        b["start"] = round(t, 3)
        t += b["duration"]
        b["end"] = round(t, 3)
        last = k == len(beats) - 1
        t += 0 if last else gaps[k]
        cmd += ["-i", run.path(b["file"])]
        pre = int(LEAD_IN * 1000) if k == 0 else 0
        chain.append(f"[{k}:a]adelay={pre}:all=1,apad=pad_dur={gaps[k]}[p{k}]")
    filt = ";".join(chain) + ";" + "".join(f"[p{k}]" for k in range(len(beats))) + \
        f"concat=n={len(beats)}:v=0:a=1[out]"
    out = run.path("voice", "narration.wav")
    subprocess.run(cmd + ["-filter_complex", filt, "-map", "[out]", "-ar", str(RATE), "-ac", "1", out],
                   check=True)
    total = _dur(out)
    run.save("voice/voice.json", {"voice": VOICE, "engine": ENGINE, "lead_in": LEAD_IN, "gap": GAP, "beats": beats,
                                  "duration": round(total, 3)})
    log.info("[voice] narration %.1f s for %d beats", total, len(beats))


def validate(run):
    v = run.need("voice/voice.json")
    if not os.path.exists(run.path("voice", "narration.wav")):
        raise StageError("narration.wav missing")
    script = run.need("script.json")
    if len(v["beats"]) != len(script["beats"]):
        raise StageError("voice beats do not match the script")
    target = run.need("brief.json")["target_seconds"]
    if not 0.8 * target <= v["duration"] <= 1.2 * target:
        raise StageError(f"narration runs {v['duration']:.1f} s for a {target} s target: trim or extend the script")
