"""
Speak every beat of a Build-It script with Chatterbox in ONE process (the model loads once), cloning a reference
voice; English with ChatterboxTTS, other languages with ChatterboxMultilingualTTS. Runs in Chatterbox's own venv,
so it imports nothing from the project.

    python chatterbox_worker.py job.json
job: {"lang": "en", "voice_prompt": wav, "device": "auto",
      "items": [{"id": "b01", "text": "...", "exaggeration": 0.7, "cfg_weight": 0.3, "out": wav}, ...]}
prints one JSON line per item: {"id", "out", "seconds"}
"""
import json
import re
import sys
import time


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def main():
    job = json.load(open(sys.argv[1], encoding="utf-8"))
    import torch
    import torchaudio

    device = job.get("device") or "auto"
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() and torch.cuda.mem_get_info()[0] > 4 * 1024 ** 3 else "cpu"
    lang = job.get("lang", "en")
    t = time.time()
    if lang == "en":
        from chatterbox.tts import ChatterboxTTS
        model = ChatterboxTTS.from_pretrained(device=device)

        def gen(text, ex, cfg):
            return model.generate(text, audio_prompt_path=job.get("voice_prompt") or None,
                                  exaggeration=ex, cfg_weight=cfg)
    else:
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        model = ChatterboxMultilingualTTS.from_pretrained(device=device)

        def gen(text, ex, cfg):
            return model.generate(text, language_id=lang, audio_prompt_path=job.get("voice_prompt") or None,
                                  exaggeration=ex, cfg_weight=cfg)
    print(json.dumps({"event": "loaded", "seconds": round(time.time() - t, 1), "device": device}), flush=True)
    sr = model.sr
    torch.manual_seed(int(job.get("seed", 7)))
    for it in job["items"]:
        t = time.time()
        parts = []
        for k, sen in enumerate(sentences(it["text"])):
            wav = gen(sen, float(it.get("exaggeration", 0.5)), float(it.get("cfg_weight", 0.5)))
            parts.append(wav)
            if k < len(sentences(it["text"])) - 1:
                parts.append(torch.zeros(1, int(sr * float(it.get("sentence_pause", 0.12)))))
        audio = torch.cat(parts, dim=1)
        torchaudio.save(it["out"], audio, sr)
        print(json.dumps({"id": it["id"], "out": it["out"], "seconds": round(time.time() - t, 1)}), flush=True)


if __name__ == "__main__":
    main()
