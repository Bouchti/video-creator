"""Final narration for the Gimli Glider short: ElevenLabs eleven_v4, narrator George (owner, 11 Nov: "the best
ElevenLabs voice"). One take per script line, Whisper-checked, trimmed, laid end to end with natural gaps (the picture
is timed to this voice, not the other way round). Writes voice.wav, words.json (word timings) and lines.json.
Takes are cached in takes_el/: re-running never re-buys a line that already passed (owner, 12 Nov: no ElevenLabs
credits on tests).

    python cartoon-shorts/shorts/gimli/voice/make_voice_el.py      (from Video Creator/)
"""
import json, os, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT)); os.chdir(ROOT)
from dotenv import load_dotenv  # noqa: E402
from config.paths import get_env_path, get_ffmpeg, get_ffprobe  # noqa: E402
load_dotenv(get_env_path())
from agents.voice import elevenlabs_post  # noqa: E402
from agents.transcription import transcribe_with_whisper  # noqa: E402

FF, FP = get_ffmpeg(), get_ffprobe()
MODEL, NARR = "eleven_v4", "JBFqnCBsd6RMkjVDRZzb"     # George
EL = HERE / "takes_el"; EL.mkdir(exist_ok=True)
src = (HERE.parent / "SCRIPT.md").read_text(encoding="utf-8").split("Script:\n", 1)[1]
lines = [l.strip() for l in src.splitlines() if l.strip()]
# eleven_v4 delivery tags (not spoken)
TAGS = {0: "[urgent] ", 2: "[deadpan] ", 5: "[deadpan] ", 6: "[tense] ", 7: "[deadpan] ", 8: "[amused] ",
        10: "[deadpan] ", 11: "[tense] ", 13: "[dramatic] ", 15: "[amused] "}
# pause after each line (s): short inside a beat, longer between beats; the hook runs straight on
GAPS = {0: 0.2, 5: 0.28, 7: 0.25, 9: 0.18, 11: 0.18, 13: 0.15, 14: 0.3}
GAP = 0.22
# the hook (line 0) is squeezed to 0.1 s pauses: the full claim must land by ~2.5 s
# tighten each take: pauses inside a line longer than 0.18 s are cut down to 0.18 s, then an optional pitch-neutral
# tempo (owner pace rule: 60-70 s spoken); applied to the cached takes, so no credits are spent
SQUEEZE = "silenceremove=stop_periods=-1:stop_duration=0.18:stop_threshold=-42dB:stop_silence=0.18"
TEMPO = float(os.getenv("VOICE_TEMPO", "1.09"))   # 1.09: 75.6 s -> ~69.5 s

def dur(p):
    return float(subprocess.run([FP, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout)

norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())  # noqa: E731
SKIP = {"nineteen", "eightythree", "fortyone", "thousand", "a", "the", "and", "bong", "its", "it", "extinguishers"}

def check(path, text):
    heard = " ".join(h["text"] for h in transcribe_with_whisper(str(path)))
    want = [norm(w) for w in text.split() if norm(w) and norm(w) not in SKIP]
    got = norm(heard)
    return heard, [w for w in want if w not in got]

def speak(i, text):
    out = EL / f"l{i:02d}.mp3"
    if out.exists(): return out
    payload = {"text": TAGS.get(i, "") + text, "model_id": MODEL, "voice_settings": {"stability": 0.5, "similarity_boost": 0.8, "speed": 1.2}}
    best = None
    for attempt in range(3):
        r = elevenlabs_post(f"https://api.elevenlabs.io/v1/text-to-speech/{NARR}?output_format=mp3_44100_128", payload, len(payload["text"]))
        tmp = EL / f"l{i:02d}_try{attempt}.mp3"; tmp.write_bytes(r.content)
        heard, miss = check(tmp, text)
        print(f"l{i:02d} try{attempt}: {heard}" + (f"   MISSING {miss}" if miss else ""))
        if best is None or len(miss) < best[1]: best = (tmp, len(miss))
        if not miss: break
    best[0].replace(out)
    return out

tmpd = HERE / "_el_tmp"; tmpd.mkdir(exist_ok=True)
t, words, segs, meta = 0.0, [], [], []
for i, line in enumerate(lines):
    mp3 = speak(i, line)
    trim = tmpd / f"t{i:02d}.wav"
    subprocess.run([FF, "-v", "error", "-y", "-i", str(mp3), "-af", "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse," + (SQUEEZE if i else SQUEEZE.replace("0.18", "0.1")) + f",atempo={TEMPO * (1.1 if i == 0 else 1.0):.4f}",
                    "-ar", "48000", "-ac", "1", str(trim)], check=True)
    L = dur(trim); segs.append((trim, t))
    heard = transcribe_with_whisper(str(trim))
    sw = line.split(); got, j = [None] * len(sw), 0
    for a, w in enumerate(sw):
        kk = next((kk for kk in range(j, min(j + 3, len(heard))) if norm(heard[kk]["text"]) == norm(w)), None)
        if kk is not None: got[a] = (heard[kk]["start"], heard[kk]["end"]); j = kk + 1
    for a in range(len(sw)):
        if got[a] is None:
            a_ = next((got[b][1] for b in range(a - 1, -1, -1) if got[b]), 0.0)
            nb = next(((b, got[b][0]) for b in range(a + 1, len(sw)) if got[b]), (len(sw), L))
            step = (nb[1] - a_) / max(1, nb[0] - a); got[a] = (a_, a_ + step)
    for w, (s_, e_) in zip(sw, got):
        st = t + s_
        if words and st < words[-1]["end"]: st = words[-1]["end"]
        words.append({"word": w, "start": round(st, 3), "end": round(max(t + e_, st + 0.04), 3)})
    meta.append({"i": i, "text": line, "start": round(t, 3), "end": round(t + L, 3)})
    print(f"l{i:02d} {t:6.2f}-{t + L:6.2f}  {line}")
    t += L + GAPS.get(i, GAP)
D = t + 0.6
inputs, filt = [], []
for n, (p, s) in enumerate(segs):
    inputs += ["-i", str(p)]; filt.append(f"[{n}:a]adelay={int(s * 1000)}[a{n}]")
filt.append("".join(f"[a{n}]" for n in range(len(segs))) + f"amix=inputs={len(segs)}:normalize=0,apad=whole_dur={D:.3f},atrim=0:{D:.3f},loudnorm=I=-18:TP=-2:LRA=7[o]")
subprocess.run([FF, "-v", "error", "-y", *inputs, "-filter_complex", ";".join(filt), "-map", "[o]", "-ar", "48000", "-ac", "1", str(HERE / "voice.wav")], check=True)
(HERE / "words.json").write_text(json.dumps({"duration": dur(HERE / "voice.wav"), "words": words}, indent=1), encoding="utf-8")
(HERE / "lines.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
print(f"voice.wav {dur(HERE / 'voice.wav'):.2f} s, {len(words)} words")
