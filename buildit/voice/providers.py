"""
Voice providers for Build-It (BUILDIT_VOICE):

  chatterbox (default)  local Chatterbox (Resemble AI) on the GPU, cloning voice/reference.wav (reference_fr.wav
                        for French), every beat in one model load, per-beat exaggeration / cfg_weight
  pipeline              the project's own voice (agents.voice.generate_voiceover: ElevenLabs, then its fallback)

    speak_beats([{"id", "text", "exaggeration", "cfg_weight"}], out_dir, lang) -> {id: wav path}
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import time

from ..config import VOICE_REF

log = logging.getLogger("pipeline")
WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chatterbox_worker.py")


def provider() -> str:
    return os.getenv("BUILDIT_VOICE", "chatterbox")


def _chatterbox(items, out_dir, lang) -> dict:
    from agents.voice import chatterbox_python
    ref = VOICE_REF.get(lang)
    if not ref or not os.path.exists(ref):
        if lang != "en":
            raise RuntimeError(f"no {lang} reference voice at {ref}: add a 10-15 s clean clip in that language")
        ref = None
        log.warning("[voice] no voice/reference.wav: Chatterbox's default voice")
    job = {"lang": lang, "voice_prompt": ref, "device": os.getenv("CHATTERBOX_DEVICE") or "auto",
           "items": [{**it, "out": os.path.join(out_dir, f"{it['id']}_raw.wav")} for it in items]}
    path = os.path.join(out_dir, "chatterbox_job.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(job, f, indent=1)
    t = time.time()
    p = subprocess.run([chatterbox_python(), WORKER, path], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=3600)
    if p.returncode != 0:
        raise RuntimeError(f"chatterbox failed: {(p.stderr or p.stdout)[-1500:]}")
    done = {}
    for line in p.stdout.splitlines():
        if line.startswith("{"):
            ev = json.loads(line)
            if "id" in ev:
                done[ev["id"]] = ev["out"]
            elif ev.get("event") == "loaded":
                log.info("[voice] chatterbox loaded in %.1f s on %s", ev["seconds"], ev["device"])
    log.info("[voice] chatterbox spoke %d beats in %.1f s", len(done), time.time() - t)
    return done


def _pipeline(items, out_dir, lang) -> dict:
    import shutil

    from agents.voice import generate_voiceover
    out = {}
    for it in items:
        tmp, _ = generate_voiceover(it["text"], voice=os.getenv("BUILDIT_PIPELINE_VOICE", "storyteller"))
        dst = os.path.join(out_dir, f"{it['id']}_raw{os.path.splitext(tmp)[1] or '.mp3'}")
        shutil.copyfile(tmp, dst)
        out[it["id"]] = dst
    return out


def speak_beats(items: list[dict], out_dir: str, lang: str = "en") -> dict:
    os.makedirs(out_dir, exist_ok=True)
    if not items:
        return {}
    return _pipeline(items, out_dir, lang) if provider() == "pipeline" else _chatterbox(items, out_dir, lang)
