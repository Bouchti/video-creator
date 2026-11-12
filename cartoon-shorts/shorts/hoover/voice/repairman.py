"""The Hoover repairman's line in his own voice (rule: quoted lines are voiced by the character). A British male Kokoro
voice (bm_george) speaks a reference clip; Chatterbox clones it for several takes of the line; pick by Whisper + ear."""
import json, os, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent / "repair"; HERE.mkdir(exist_ok=True)
ROOT = Path(__file__).resolve().parents[4]; sys.path.insert(0, str(ROOT)); os.chdir(ROOT)
from agents.voice import kokoro_python, chatterbox_python  # noqa: E402
ref = HERE / "male_ref.wav"
if not ref.exists():
    kj = HERE / "kjob.json"
    kj.write_text(json.dumps({"parts": [["text", "Right then, let's have a look at this machine. Oh dear. No, no, no. That's not going to work, is it? "
        "I've been fixing these things for twenty years, mate, and I'll tell you what I tell everybody. You get what you pay for."]],
        "output": str(ref), "voice": "bm_george", "speed": 1.0}), encoding="utf-8")
    subprocess.run([kokoro_python(), str(ROOT / "agents" / "kokoro_worker.py"), str(kj)], check=True)
LINE = "If you think buying a washing machine's going to get you two tickets to America... you must be an idiot."
takes = [(0.6, 0.5), (0.75, 0.45), (0.85, 0.4), (0.7, 0.5), (0.9, 0.45), (0.65, 0.45)]
job = {"lang": "en", "voice_prompt": str(ref), "device": "auto",
       "items": [{"id": f"t{i}", "text": LINE, "exaggeration": e, "cfg_weight": c, "out": str(HERE / f"t{i}.wav")} for i, (e, c) in enumerate(takes)]}
cj = HERE / "cjob.json"; cj.write_text(json.dumps(job, indent=1), encoding="utf-8")
p = subprocess.run([chatterbox_python(), str(ROOT / "buildit" / "voice" / "chatterbox_worker.py"), str(cj)], capture_output=True, text=True, encoding="utf-8", errors="replace")
print(p.stdout[-1500:], p.stderr[-800:] if p.returncode else "")
