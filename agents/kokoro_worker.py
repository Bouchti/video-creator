"""Speak narration with Kokoro-82M; run by Kokoro's own Python (see agents.voice._kokoro_voiceover).

Kept free of project imports: it runs in a separate venv (CPU torch). Input: a JSON job file
{"parts": [["text", "..."] | ["pause", seconds]], "output": wav path, "voice", "speed"}.
Output: one 24 kHz mono WAV.
"""
import json
import sys


def main() -> int:
    job = json.load(open(sys.argv[1], encoding="utf-8"))
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline

    voice = job.get("voice") or "am_michael"
    # The voice's first letter is its accent: a = American, b = British.
    pipeline = KPipeline(lang_code=voice[0], repo_id="hexgrad/Kokoro-82M")
    pieces = []
    for kind, value in job["parts"]:
        if kind == "pause":
            pieces.append(np.zeros(int(float(value) * 24000), dtype=np.float32))
            continue
        for _, _, audio in pipeline(str(value), voice=voice, speed=float(job.get("speed", 1.0))):
            pieces.append(audio.numpy() if hasattr(audio, "numpy") else np.asarray(audio, dtype=np.float32))
    if not pieces:
        raise SystemExit("no text to speak")
    sf.write(job["output"], np.concatenate(pieces), 24000)
    print(json.dumps({"voice": voice}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
