"""
Chatterbox TTS (Resemble AI, MIT licence), run in its OWN environment (tools/chatterbox/.venv, made by
agents/libraries.py part "chatterbox"), so its torch / CUDA stack never touches the pipeline's.

    .venv/Scripts/python speak.py JOB.json

JOB: {"text": "...", "out": "voice.wav", "exaggeration": 0.6, "cfg_weight": 0.45, "temperature": 0.8,
      "voice": "optional reference .wav to clone", "seed": 7, "pause": 0.18}

Long narration is spoken sentence by sentence (the model is best on short inputs) and joined with a short
pause, at the model's own sample rate.
"""
import json
import re
import sys

try:                      # verify HTTPS (the model download) against the system store: works behind TLS inspection
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

import torch
import torchaudio as ta
from chatterbox.tts import ChatterboxTTS


def sentences(text):
    text = re.sub(r"<[^>]+>", " ", text)                       # SSML tags (ElevenLabs breaks) are not spoken
    parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    out, buf = [], ""
    for s in parts:                                           # very short sentences ride with the next one
        buf = f"{buf} {s}".strip()
        if len(buf.split()) >= 4:
            out.append(buf)
            buf = ""
    if buf:
        out.append(buf)
    return out


def main():
    job = json.load(open(sys.argv[1], encoding="utf-8"))
    device = job.get("device") or ("cuda" if torch.cuda.is_available() else "cpu")
    model = ChatterboxTTS.from_pretrained(device=device)
    torch.manual_seed(int(job.get("seed", 7)))
    pause = torch.zeros(1, int(model.sr * float(job.get("pause", 0.18))))
    pieces = []
    for s in sentences(job["text"]):
        kw = dict(exaggeration=float(job.get("exaggeration", 0.6)), cfg_weight=float(job.get("cfg_weight", 0.45)),
                  temperature=float(job.get("temperature", 0.8)))
        if job.get("voice"):
            kw["audio_prompt_path"] = job["voice"]
        wav = model.generate(s, **kw).cpu()
        pieces += [wav, pause]
    ta.save(job["out"], torch.cat(pieces, dim=1), model.sr)
    print(json.dumps({"ok": True, "device": device, "sentences": len(pieces) // 2}))


if __name__ == "__main__":
    main()
