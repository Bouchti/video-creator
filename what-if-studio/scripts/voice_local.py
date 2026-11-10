"""The What If skill's voice step with the LOCAL voice instead of ElevenLabs.

    python scripts/voice_local.py <slug>            (from what-if-studio/), then:
    python <skill>/scripts/voice.py <slug>          (tightens the pauses, writes voice.wav and words.json)

Chatterbox (the project's own energetic narrator, buildit's voice provider) reads each beat of the script; the takes
are joined with short pauses; faster-whisper times every word, which is matched to the script's words so each keeps
its punctuation (the skill sets pause lengths by it). The result is saved as the skill's voice cache
(public/<slug>/voice_raw.mp3, out/<slug>/words_raw.json, out/<slug>/voice_meta.json with the same signature voice.py
computes), so voice.py reuses it without calling ElevenLabs and does its usual tightening. No credits are spent.
"""
import hashlib, json, os, re, subprocess, sys, tempfile
from pathlib import Path

STUDIO = Path(__file__).resolve().parent.parent
ROOT = STUDIO.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from dotenv import load_dotenv  # noqa: E402
from config.paths import get_env_path, get_ffmpeg  # noqa: E402
load_dotenv(get_env_path())
from buildit.voice.providers import speak_beats  # noqa: E402
from agents.transcription import transcribe_with_whisper  # noqa: E402

slug = sys.argv[1]
ep = json.loads((STUDIO / 'src' / 'episodes' / slug / 'episode.json').read_text(encoding='utf-8'))
pub, out = STUDIO / 'public' / slug, STUDIO / 'out' / slug
pub.mkdir(parents=True, exist_ok=True)
out.mkdir(parents=True, exist_ok=True)
FF = get_ffmpeg()

# 1. Chatterbox reads each beat (energetic: the hook hotter, the rest lively)
items = [{'id': f'b{i:02d}', 'text': b['text'].strip(), 'exaggeration': 0.85 if i == 0 else 0.72,
          'cfg_weight': 0.3 if i == 0 else 0.35} for i, b in enumerate(ep['script'])]
tmp = Path(tempfile.mkdtemp(prefix='wi_voice_'))
raw = speak_beats(items, str(tmp), 'en')

# 2. join the takes (0.25 s between beats: voice.py trims each pause to the genre's pace afterwards)
lst = tmp / 'list.txt'
gap = tmp / 'gap.wav'
subprocess.run([FF, '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono', '-t', '0.25', str(gap)], check=True)
parts = []
for it in items:
    w = tmp / f"{it['id']}.wav"
    subprocess.run([FF, '-v', 'error', '-y', '-i', raw[it['id']], '-ar', '44100', '-ac', '1', str(w)], check=True)
    parts += [w, gap]
lst.write_text(''.join(f"file '{p.as_posix()}'\n" for p in parts[:-1]), encoding='utf-8')
joined = tmp / 'joined.wav'
subprocess.run([FF, '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(lst), '-c', 'copy', str(joined)], check=True)
subprocess.run([FF, '-v', 'error', '-y', '-i', str(joined), '-c:a', 'libmp3lame', '-b:a', '128k', str(pub / 'voice_raw.mp3')], check=True)

# 3. word timings from Whisper, matched to the script's own words (with their punctuation)
heard = transcribe_with_whisper(str(joined))
script_words = []
for b in ep['script']:
    for tok in b['text'].split():
        m = re.match(r"^(.*?[\w'’]+)([^\w'’]*)$", tok)
        if m:
            script_words.append((re.sub(r"^[^\w'’]+", '', m.group(1)), m.group(2)))


def norm(s):
    return re.sub(r"[^a-z0-9]", '', s.lower())


words, j = [], 0
for w, p in script_words:
    k = next((k for k in range(j, min(j + 4, len(heard))) if norm(heard[k]['text']) == norm(w)), None)
    if k is None:                                    # not heard verbatim: take the next heard word's time
        k = min(j, len(heard) - 1)
    s, e = heard[k]['start'], heard[k]['end']
    if words and s < words[-1]['e']:
        s = words[-1]['e']
    words.append({'w': w, 's': round(s, 3), 'e': round(max(e, s + 0.05), 3), 'p': p})
    j = k + 1
(out / 'words_raw.json').write_text(json.dumps(words, indent=1), encoding='utf-8')

# 4. the cache signature exactly as voice.py computes it, so it reuses this take
V = {'id': 'TX3LPaxmHKxFdv7VOQHJ', 'model': 'eleven_multilingual_v2', 'settings': {'stability': 0.4, 'similarity_boost': 0.8, 'style': 0.35, 'use_speaker_boost': True}}
V.update(ep.get('voice', {}))
text = ' '.join(b['text'].strip() for b in ep['script'])
sig = hashlib.sha1(json.dumps([text, V], sort_keys=True).encode()).hexdigest()[:12]
(out / 'voice_meta.json').write_text(json.dumps({'sig': sig, 'chars': len(text), 'voice': 'local chatterbox'}), encoding='utf-8')
print(f'local voice: {len(words)} words, {len(heard)} heard; cached for voice.py (no ElevenLabs credits)')
