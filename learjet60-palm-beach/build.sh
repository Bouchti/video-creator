#!/bin/sh
# One command: "Four Minutes over Palm Beach" (Satellite Briefing)
#   sh build.sh            voice, cues, events, picture, score + mix, master, subtitles, checks, poster
#   FETCH=1 sh build.sh    first re-download imagery + radar (NASA GIBS, Planetary Computer, IEM) and fonts
#   default: vertical 1080x1920 for Shorts / Reels / TikTok;  FORMAT=landscape sh build.sh  for 1920x1080
set -e
LIB=/c/Users/tibus/lemo-opuscar
export LIB
HERE=$(cd "$(dirname "$0")" && pwd)
if [ "${FORMAT:-vertical}" = landscape ]; then SIZE=1920x1080; NAME=learjet60-palm-beach; else SIZE=1080x1920; NAME=learjet60-palm-beach-shorts; fi
PY="$LIB/.venv/bin/python"
export PYTHONUTF8=1
[ -f "$LIB/core/render/video.mjs" ] || { echo "set LIB to the library folder"; exit 1; }

if [ "${FETCH:-0}" = "1" ] || [ ! -f "$HERE/assets/plates/det.jpg" ]; then
  "$PY" -I "$HERE/tools/fetch.py" "$HERE"
  "$PY" -m pip install --quiet --target "$HERE/tools/_pkgs" contourpy
  "$PY" -I "$HERE/tools/radar.py" "$HERE"
fi
[ -f "$HERE/fonts/IBMPlexSans.ttf" ] || sh "$HERE/tools/fonts.sh"

# voice: Kokoro (af_heart); speech-to-text check with the small English model
if [ ! -f "$HERE/voice/out/dur.json" ] || [ "${VOICE:-0}" = "1" ]; then
  (cd "$LIB" && "$PY" core/tts/tts.py "$HERE/voice/lines.json" "$HERE/voice/out")
fi
(cd "$LIB" && WHISPER_MODEL=small.en "$PY" core/tts/asr_check.py "$HERE/voice/lines.json" "$HERE/voice/out" --lang en)
node "$HERE/tools/cues.mjs" "$HERE"

# picture, events, score + mix, master
cd "$LIB"
node core/render/events.mjs "$HERE"
LEMO_ANGLE=${LEMO_ANGLE:-default} node core/render/video.mjs "$HERE" --fps 24 --workers 3 --size $SIZE --out "$HERE/out/video_$SIZE.mp4"
"$PY" "$HERE/mix.py"
sh core/render/mux.sh "$HERE/out/video_$SIZE.mp4" "$HERE/out/mix.wav" "$HERE/$NAME.mp4" 24 1
"$PY" core/render/srt.py "$HERE/out/cues_srt.json" "$HERE/$NAME.srt"

# checks
LEMO_ANGLE=${LEMO_ANGLE:-default} node core/render/readcheck.mjs "$HERE" --size $SIZE > "$HERE/out/readcheck.txt" && echo "readcheck ok" || { tail -20 "$HERE/out/readcheck.txt"; echo "readcheck: see out/readcheck.txt"; }
ffmpeg -hide_banner -nostats -i "$HERE/$NAME.mp4" -vf blackdetect=d=0.1:pix_th=0.05 -af ebur128 -f null - 2>&1 | grep -E "blackdetect|I:|LRA:|Peak" | tail -6

# poster: the dive, the camera at the jet's altitude
ffmpeg -v error -y -ss 38.0 -i "$HERE/$NAME.mp4" -frames:v 1 -q:v 2 "$HERE/poster_$SIZE.jpg"
echo "done: $HERE/$NAME.mp4"
