"""Voice for the Eiffel short: Chatterbox (local) reads each script line in one steady tone; the takes are joined with
short pauses and sped to the skill's ~3.7 words/s; Whisper times every word -> voice.wav, words.json."""
import json, os, re, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]  # Video Creator/
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from dotenv import load_dotenv  # noqa: E402
from config.paths import get_env_path, get_ffmpeg, get_ffprobe  # noqa: E402
load_dotenv(get_env_path())
from buildit.voice.providers import speak_beats  # noqa: E402
from agents.transcription import transcribe_with_whisper  # noqa: E402

FF = get_ffmpeg()
TEMPO = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
GAP = 0.28
src = (HERE.parent / 'SCRIPT.md').read_text(encoding='utf-8').split('Script:\n', 1)[1]
lines = [l.strip() for l in src.splitlines() if l.strip()]
tmp = Path(tempfile.mkdtemp(prefix='eiffel_voice_'))
cache = HERE / 'takes'
cache.mkdir(exist_ok=True)
SAY = {'André Poisson': 'Andray Pwasson', 'Poisson': 'Pwasson', '"': ''}
def say(t):
    for a, b in SAY.items(): t = t.replace(a, b)
    return t
items = [{'id': f'l{i:02d}', 'text': say(t), 'exaggeration': 0.5, 'cfg_weight': 0.5} for i, t in enumerate(lines)]
todo = [it for it in items if not (cache / f"{it['id']}.wav").exists()]
if todo:
    raw = speak_beats(todo, str(tmp), 'en')
    for it in todo:
        subprocess.run([FF, '-v', 'error', '-y', '-i', raw[it['id']], '-af', 'silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse',
                        '-ar', '48000', '-ac', '1', str(cache / f"{it['id']}.wav")], check=True)
gap = tmp / 'gap.wav'
subprocess.run([FF, '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono', '-t', str(GAP), str(gap)], check=True)
lst = tmp / 'list.txt'
parts = []
for it in items:
    parts += [cache / f"{it['id']}.wav", gap]
lst.write_text(''.join(f"file '{p.as_posix()}'\n" for p in parts[:-1]), encoding='utf-8')
joined = tmp / 'joined.wav'
subprocess.run([FF, '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(lst), '-c', 'copy', str(joined)], check=True)
out = HERE / 'voice.wav'
subprocess.run([FF, '-v', 'error', '-y', '-i', str(joined), '-af', f'atempo={TEMPO},loudnorm=I=-18:TP=-2:LRA=7', '-ar', '48000', '-ac', '1', str(out)], check=True)
dur = float(subprocess.run([get_ffprobe(), '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(out)],
                           capture_output=True, text=True).stdout or 0)
norm = lambda s: re.sub(r'[^a-z0-9]', '', s.lower().replace('é','e'))  # noqa: E731


def take_len(p):
    return float(subprocess.run([get_ffprobe(), '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(p)],
                                capture_output=True, text=True).stdout)


# each line is its own take, so its start in voice.wav is known exactly; Whisper only times the words inside a line
# (whole-file decoding drifts by seconds over a minute)
words, t0 = [], 0.0
for it, line in zip(items, lines):
    take = cache / f"{it['id']}.wav"
    L = take_len(take)
    heard = transcribe_with_whisper(str(take))
    print('HEARD', it['id'], ' '.join(h['text'] for h in heard))
    sw = line.split()
    got, j = [None] * len(sw), 0
    for i, w in enumerate(sw):
        k = next((k for k in range(j, min(j + 4, len(heard))) if norm(heard[k]['text']) == norm(w)), None)
        if k is not None:
            got[i] = (heard[k]['start'], heard[k]['end'])
            j = k + 1
    # words Whisper wrote differently (numbers): spread them between their timed neighbours
    for i in range(len(sw)):
        if got[i] is None:
            a_ = next((got[k][1] for k in range(i - 1, -1, -1) if got[k]), 0.0)
            nb = next(((k, got[k][0]) for k in range(i + 1, len(sw)) if got[k]), (len(sw), L))
            n = nb[0] - i
            step = (nb[1] - a_) / (n + 0)
            got[i] = (a_, a_ + step)
    for w, (s_, e_) in zip(sw, got):
        st, en = (t0 + s_) / TEMPO, (t0 + e_) / TEMPO
        if words and st < words[-1]['end']:
            st = words[-1]['end']
        words.append({'word': w, 'start': round(st, 3), 'end': round(max(en, st + 0.04), 3)})
    t0 += L + GAP
script_words = words
(HERE / 'words.json').write_text(json.dumps({'duration': dur, 'words': words}, indent=1), encoding='utf-8')
print(f'voice {dur:.2f} s, {len(script_words)} words, {len(script_words) / dur:.2f} w/s, heard {len(heard)}')
