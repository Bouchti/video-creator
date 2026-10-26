# Autonomous Video Creator

This project creates 9:16 social videos from research to a reviewed final MP4. With no topic argument, it searches current trends, selects a topic and angle, writes a complete screenplay, critiques and revises it, generates silent visuals, adds one ElevenLabs narration track, creates captions locally from word timings, mixes restrained ambience/music, and runs scene-level plus whole-video quality review.

The current production routes are:

- `local-ai` (default): durable, resumable MiniMax H3 generation with Wan fallback through local ComfyUI service endpoints.
- `pexels`: stock/archival footage, public-domain media, photographs, and diagrams.
- `cutaway` and `evolution`: authored Blender showrunner formats.

Hailuo and the old selectable Comfy/animated pipelines have been removed. ComfyUI remains an internal transport for the supported local MiniMax/Wan backends; it does not write narration or captions.

## Setup

```powershell
.\setup.ps1
Copy-Item .env.example .env
```

Fill in at least:

- `ANTHROPIC_API_KEY` for script and visual quality review.
- `TAVILY_API_KEY` for autonomous current-topic research.
- one of `ELEVENLABS_API_KEY` through `ELEVENLABS_API_KEY_4` for narration.
- the local MiniMax/Wan service settings installed by `setup.ps1`.

Quality review is fail-closed by default. The pipeline refuses to generate when required services, keys, credits, executables, or disk space are unavailable. It also refuses to accept clips or a final edit that cannot be reviewed. The `*_ALLOW_*` settings in `.env.example` are diagnostic overrides, not production defaults.

## Run

Activate the environment and let the AI choose a current topic:

```powershell
.\venv\Scripts\Activate.ps1
python main.py
```

Common alternatives:

```powershell
python main.py --duration 60
python main.py --source local-ai "Why deep-sea animals glow"
python main.py --source pexels "How Roman concrete heals itself"
python -m local_video.cli status output\projects\PROJECT_ID
python -m local_video.cli resume output\projects\PROJECT_ID
```

`--duration` accepts 30–90 seconds. Shot timing is allocated from the screenplay rather than fixed three-second cuts.

The output includes the video, plain post notes, and platform-specific post copy. Generated video projects remain resumable under `output/projects`.

## Publishing

Publishing is off by default. Preparing a JSON package never uploads:

```powershell
python main.py --publish youtube
```

Live publishing requires both explicit switches and credentials:

```powershell
# Set PUBLISH_ENABLED=1 and the platform token(s) in .env first.
python main.py --publish youtube --publish-live
python main.py --publish instagram --publish tiktok --publish-live
```

YouTube defaults to `private`, TikTok defaults to `SELF_ONLY`, and generated-media disclosure is included. Instagram requires a publicly reachable final-video URL in `PUBLISH_VIDEO_URL` because the Graph API fetches the media remotely.

## Audio and captions

Generated scene clips are stripped of embedded audio. The final mix contains a single software-authored narration track plus optional music/ambience. Automatic transition whooshes are disabled. Captions are generated and burned by this software; prompts explicitly prohibit generated subtitles, lettering, watermarks, and UI.

## Tests

```powershell
python -m unittest discover -s tests -v
python -m pytest -q
```

Tests use mocks and do not start video generation or publish content.
