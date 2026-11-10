"""Replace the narrator's "he came by car!" with a woman in the crowd shouting it (user, 9 Nov 2026).
Run after make_voice.py:  python cartoon-shorts/shorts/marathon/voice/post_shout.py
The narrator keeps "Then someone shouted:"; the shout (Chatterbox cloning a Kokoro af_heart reference, take t1) is
brightened, given a short stadium echo, and dropped in at the narrator's "he" (34.11 s). voice.wav stays mono; the mix
pans nothing (the shout is centred like the narration so it reads as part of the story)."""
import json, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
V = HERE / "voice.wav"
SHOUT = HERE / "shout" / "t1_trim.wav"
words = json.loads((HERE / "words.json").read_text(encoding="utf-8"))["words"]
i = next(k for k, w in enumerate(words) if w["word"] == "he" and 33 < w["start"] < 36)
t_end, t_next = words[i + 3]["end"], words[i + 4]["start"]
# v2 (user, 10 Nov: "coming late and not loud enough"): the shout starts the instant the narrator finishes "shouted:"
# (the bubble, shock face and point land on the same frame in cast.ts), and sits well above the narration
t0 = words[i - 1]["end"] + 0.02
src = HERE / "voice_narrator.wav"
if not src.exists():
    V.replace(src)                       # keep the pure narrator take once
NARR_END = 34.782   # the narrator's own "car!" ends here in voice_narrator.wav (words.json is shifted after the first run)
cut_a, cut_b = t0 - 0.01, min(NARR_END + 0.12, t_next - 0.02)
filt = (
    f"[0:a]volume=enable='between(t,{cut_a:.3f},{cut_b:.3f})':volume=0[n];"
    f"[1:a]highpass=f=160,equalizer=f=3000:t=q:w=1.2:g=5,acompressor=threshold=0.1:ratio=4:attack=5:release=80:makeup=2,volume=6.5,aecho=0.85:0.5:55|110:0.2|0.1,"
    f"adelay={int(t0 * 1000)}[s];"
    f"[n][s]amix=inputs=2:normalize=0,alimiter=limit=0.95"
)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-i", str(SHOUT), "-filter_complex", filt,
                "-ar", "48000", "-ac", "1", str(V)], check=True)
# captions follow the shout: shift its four words to the new start
d = t0 - words[i]["start"]
if abs(d) > 1e-3:
    for k in range(i, i + 4): words[k]["start"] = round(words[k]["start"] + d, 3); words[k]["end"] = round(words[k]["end"] + d, 3)
    wj = json.loads((HERE / "words.json").read_text(encoding="utf-8")); wj["words"] = words
    (HERE / "words.json").write_text(json.dumps(wj, indent=1), encoding="utf-8")
print(f"shout placed at {t0:.2f} s (narrator muted {cut_a:.2f}-{cut_b:.2f} s; next word at {t_next:.2f} s)")
