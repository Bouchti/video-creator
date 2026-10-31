"""Speak narration with Chatterbox TTS; run by Chatterbox's own Python (see agents.voice._chatterbox_voiceover).

Kept free of project imports: it runs in a separate venv whose pinned torch must not meet the pipeline's.
Input: a JSON job file {"parts": [["text", "..."] | ["pause", seconds]], "output": wav path,
"exaggeration", "cfg_weight", "voice_prompt", "device"}. Output: one 24 kHz mono WAV.
"""
import json
import re
import sys


def _sentences(text: str) -> list[str]:
    """One call per sentence: Chatterbox drifts on long inputs, and each sentence gets its own breath."""
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def main() -> int:
    job = json.load(open(sys.argv[1], encoding="utf-8"))
    import torch
    import torchaudio
    from chatterbox.tts import ChatterboxTTS

    device = job.get("device") or "auto"
    if device == "auto":
        device = "cpu"
        if torch.cuda.is_available():
            free, _ = torch.cuda.mem_get_info()
            if free > 5 * 1024 ** 3:      # the video model may still hold the card
                device = "cuda"
    model = ChatterboxTTS.from_pretrained(device=device)
    pieces, spoken = [], {}
    parts_dir = job.get("parts_dir")
    for number, part in enumerate(job["parts"]):
        kind, value = part[0], part[1]
        if kind == "pause":
            pieces.append(torch.zeros(1, int(float(value) * model.sr)))
            continue
        # A part may carry its own delivery (a question, a punchy fragment, the hook): one flat setting
        # for the whole script read every line the same way.
        delivery = part[2] if len(part) > 2 and isinstance(part[2], dict) else {}
        pause = torch.zeros(1, int(float(delivery.get("pause_after", job.get("sentence_pause", 0.4))) * model.sr))
        if kind == "wav":                 # already spoken and checked: reused as is
            wav, rate = torchaudio.load(str(value))
            pieces += [torchaudio.functional.resample(wav, rate, model.sr) if rate != model.sr else wav, pause]
            continue
        # A planned part is spoken as one chunk: it already groups short fragments with their sentence.
        for chunk in ([str(value)] if delivery else _sentences(str(value))):
            wav = model.generate(chunk, audio_prompt_path=job.get("voice_prompt") or None,
                                 exaggeration=float(delivery.get("exaggeration", job.get("exaggeration", 0.5))),
                                 cfg_weight=float(delivery.get("cfg_weight", job.get("cfg_weight", 0.5))))
            if parts_dir and delivery:    # each planned sentence on its own, for the narration check
                path = f"{parts_dir}/part-{number:03d}.wav"
                torchaudio.save(path, wav.cpu(), model.sr)
                spoken[number] = path
            # a narrator's breath between sentences; Chatterbox itself reads fast (~3 words/s at any setting)
            pieces += [wav.cpu(), pause]
    if not pieces:
        raise SystemExit("no text to speak")
    torchaudio.save(job["output"], torch.cat(pieces, dim=1), model.sr)
    print(json.dumps({"device": device, "sample_rate": model.sr, "parts": spoken}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
