"""ElevenLabs voice for the Hoover short (owner, 11 Nov: "use the best elevenlabs voice"): model eleven_v4, narrator George
(warm British storyteller), the repairman's quote by Daniel (a different British voice). Each line is generated on its
own, Whisper-checked, then time-fitted into the SAME slot the first (Chatterbox) voice had, so the rendered picture,
which is timed to that voice, stays in sync: the take is stretched to the old take's length (atempo) and placed at the
old line start. Writes voice.wav and words.json (the old ones are kept as *_chatterbox.*).

    python cartoon-shorts/shorts/hoover/voice/make_voice_el.py      (from Video Creator/)
"""
import json, os, re, shutil, subprocess, sys
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
MODEL = "eleven_v4"
NARR, REPAIR = "JBFqnCBsd6RMkjVDRZzb", "onwK4e9ZLuTAKqWW03F9"   # George, Daniel
GAP = 0.28
EL = HERE / "takes_el"; EL.mkdir(exist_ok=True)
OLD = HERE / "takes"
src = (HERE.parent / "SCRIPT.md").read_text(encoding="utf-8").split("Script:\n", 1)[1]
lines = [l.strip() for l in src.splitlines() if l.strip()]
# delivery tags (eleven_v4 audio tags, not spoken): deadpan on the dry jokes, amused on the twist
TAGS = {11: "[deadpan] ", 13: "[condescending] ", 14: "[mischievously] ", 17: "[amused] "}

def dur(p):
    return float(subprocess.run([FP, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout)

norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())  # noqa: E731
NUMW = {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifty", "hundred",
        "thousand", "twenty", "nineteen", "ninety", "ninetytwo", "sevenday", "fourteenday", "and", "a", "pounds"}

def check(path, text):
    heard = " ".join(h["text"] for h in transcribe_with_whisper(str(path)))
    want = [norm(w) for w in text.replace("machine's", "machine").split() if norm(w) and norm(w) not in NUMW]
    got = norm(heard)
    miss = [w for w in want if w not in got]
    return heard, miss

def speak(i, text):
    out = EL / f"l{i:02d}.mp3"
    if out.exists(): return out
    voice = REPAIR if text.startswith("If you think buying") else NARR
    payload = {"text": TAGS.get(i, "") + text, "model_id": MODEL, "voice_settings": {"stability": 0.5, "similarity_boost": 0.8, "speed": 1.15}}
    for attempt in range(3):
        r = elevenlabs_post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128", payload, len(payload["text"]))
        out.write_bytes(r.content)
        heard, miss = check(out, text)
        print(f"l{i:02d} try{attempt}: {heard}" + (f"   MISSING {miss}" if miss else ""))
        if not miss: return out
    raise SystemExit(f"line {i} failed the Whisper check 3 times")

# the old (picture) timing: each old take starts at the running sum of take lengths + GAP
old_len = [dur(OLD / f"l{i:02d}.wav") for i in range(len(lines))]
starts, t = [], 0.0
for L in old_len: starts.append(t); t += L + GAP
total = t - GAP

tmp = HERE / "_el_tmp"; tmp.mkdir(exist_ok=True)
fitted, words = [], []
for i, line in enumerate(lines):
    mp3 = speak(i, line)
    trim = tmp / f"t{i:02d}.wav"
    subprocess.run([FF, "-v", "error", "-y", "-i", str(mp3), "-af", "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse",
                    "-ar", "48000", "-ac", "1", str(trim)], check=True)
    L_new, L_old = dur(trim), old_len[i]
    k = L_new / L_old
    room = (starts[i + 1] - starts[i] - 0.06) if i + 1 < len(lines) else L_old + 2.0
    target = L_old if 0.8 <= k <= 1.25 else min(L_new, room) if k < 0.8 else L_old * 1.25 if L_old * 1.25 <= room else room
    tempo = L_new / target
    fit = tmp / f"f{i:02d}.wav"
    chain = []
    tt = tempo
    while tt > 2.0: chain.append("atempo=2.0"); tt /= 2.0
    while tt < 0.5: chain.append("atempo=0.5"); tt /= 0.5
    chain.append(f"atempo={tt:.5f}")
    subprocess.run([FF, "-v", "error", "-y", "-i", str(trim), "-af", ",".join(chain), "-ar", "48000", "-ac", "1", str(fit)], check=True)
    fitted.append((fit, starts[i]))
    print(f"l{i:02d}: new {L_new:.2f}s old {L_old:.2f}s -> tempo {tempo:.3f} at {starts[i]:.2f}s")
    heard = transcribe_with_whisper(str(fit))
    sw = line.split(); got, j = [None] * len(sw), 0
    for a, w in enumerate(sw):
        kk = next((kk for kk in range(j, min(j + 3, len(heard))) if norm(heard[kk]["text"]) == norm(w)), None)
        if kk is not None: got[a] = (heard[kk]["start"], heard[kk]["end"]); j = kk + 1
    Lf = dur(fit)
    for a in range(len(sw)):
        if got[a] is None:
            a_ = next((got[b][1] for b in range(a - 1, -1, -1) if got[b]), 0.0)
            nb = next(((b, got[b][0]) for b in range(a + 1, len(sw)) if got[b]), (len(sw), Lf))
            step = (nb[1] - a_) / max(1, nb[0] - a); got[a] = (a_, a_ + step)
    for w, (s_, e_) in zip(sw, got):
        st = starts[i] + s_
        if words and st < words[-1]["end"]: st = words[-1]["end"]
        words.append({"word": w, "start": round(st, 3), "end": round(max(starts[i] + e_, st + 0.04), 3)})

# lay every fitted take at its old start; loudness like the first voice
D = total + 0.5
inputs, filt = [], []
for n, (p, s) in enumerate(fitted):
    inputs += ["-i", str(p)]; filt.append(f"[{n}:a]adelay={int(s * 1000)}[a{n}]")
filt.append("".join(f"[a{n}]" for n in range(len(fitted))) + f"amix=inputs={len(fitted)}:normalize=0,apad=whole_dur={D:.3f},atrim=0:{D:.3f},loudnorm=I=-18:TP=-2:LRA=7[o]")
for name in ("voice.wav", "words.json"):
    bak = HERE / name.replace(".", "_chatterbox.")
    if not bak.exists(): shutil.copyfile(HERE / name, bak)
subprocess.run([FF, "-v", "error", "-y", *inputs, "-filter_complex", ";".join(filt), "-map", "[o]", "-ar", "48000", "-ac", "1", str(HERE / "voice.wav")], check=True)
(HERE / "words.json").write_text(json.dumps({"duration": dur(HERE / "voice.wav"), "words": words}, indent=1), encoding="utf-8")
print(f"voice.wav {dur(HERE / 'voice.wav'):.2f} s, {len(words)} words")
