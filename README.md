# Autonomous Video Creator

This project creates 9:16 social videos from research to a reviewed final MP4. With no topic argument, it searches current trends, selects a topic and angle, writes a complete screenplay, critiques and revises it, generates silent visuals, adds one ElevenLabs narration track, creates captions locally from word timings, mixes restrained ambience/music, and runs scene-level plus whole-video quality review.

The current production routes are:

- `local-ai` (default): durable, resumable MiniMax H3 generation with Wan fallback through local ComfyUI service endpoints.
- `unreal`: locally rendered UE5 Sequencer cinematics through Movie Render Queue, with no per-render API fee.
- `pexels`: stock/archival footage, public-domain media, photographs, and diagrams.
- `cutaway` and `evolution`: authored Blender showrunner formats.
- `explainer`: no-hero Blender cutaway explainers in the @youbuiltit format (see below).

Hailuo and the old selectable Comfy/animated pipelines have been removed. ComfyUI remains an internal transport for the supported local MiniMax/Wan backends; it does not write narration or captions.

## Setup

```powershell
.\setup.ps1
Copy-Item .env.example .env
```

Fill in at least:

- install Claude Code and log in once; `SHOWRUNNER_BACKEND=subscription` uses it as the primary
  script, set-builder and visual-review backend.
- install the Codex CLI and run `codex login`; `SHOWRUNNER_FALLBACK_BACKEND=codex` moves the
  remaining work to Codex if Claude reaches its session limit.
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
python main.py --source unreal "How a geothermal heat pump works"
python -m unreal_video.cli status output\unreal_projects\PROJECT_ID
python -m unreal_video.cli resume output\unreal_projects\PROJECT_ID
python main.py --source pexels "How Roman concrete heals itself"
python -m local_video.cli status output\projects\PROJECT_ID
python -m local_video.cli resume output\projects\PROJECT_ID
```

`--duration` accepts 30–90 seconds. Shot timing is allocated from the screenplay rather than fixed three-second cuts.

For `--source cutaway`, the showrunner searches current 14-day trend evidence before scoring the
unused registered 3D subjects. A Max story subject is consumed after its first generated script;
changing the title or joke does not make it new. If every registered Max set is consumed, the
autopilot researches a new trend-backed subject, creates its Blender story set, renders preview
frames, visually validates every beat, registers it only after it passes, and then writes and
renders the video. This first run for a new subject is substantially longer than reusing an existing
set. `SHOWRUNNER_AUTO_BUILD_SETS=0` disables automatic expansion; `SHOWRUNNER_ALLOW_REPEATS=1` is an
explicit rerun override, not the production default.

### Explainer route

`--source explainer` makes pure 3D cutaway explainers with no hero: one cut-open diorama, the build
told in physical order as a chain of real problems and fixes, one bold word on screen at a time.
It runs under the same autopilot, showrunner (no-hero `STYLE` voice), Blender runner and quality
review as `cutaway`, but its sets live in their own registry (`EXPLAINER` in
`engine/sets/__init__.py`), so the Max route and its consumed-subject history are unaffected.

```powershell
python main.py --source explainer                                   # trend-backed topic
python main.py --source explainer "How a septic tank works"         # producer topic
python main.py --source explainer --set pool                        # a specific explainer set
python -m agents.set_builder --explainer "BUILD BRIEF" --id septic_tank_explainer --hook overflow_hook
```

A producer topic is matched to a registered explainer set; when none fits, or every set has been
used (`EXPLAINER_MAX_USES`, default 1 video per set), the autopilot researches a new subject, has
the set builder write, preview, measure, review and register a new `*_explainer` set
(`FORMAT = "explainer"`, no `HERO`), then writes and renders the video.

The Codex and Claude subscription routes use `SHOWRUNNER_QUALITY=efficient`: one strong script, an
independent critique, and a revision only when needed. Trend selection and the winning topic's fact
sheet share one web-search turn. Preview and full-render scene checks are reviewed in batches of
four, compressed review frames and verdicts are cached, and unchanged source/settings reuse the
existing Blender preview instead of rendering it again. Reasoning effort is capped independently
for showrunning, visual review and set building; both CLIs log token/cache usage. Set building runs
in an isolated source mirror and copies back only the three allowed set files, so it cannot
overwrite changes made in the real repository during a long generation.

The default backend chain is Claude Code first, Codex second. A Claude quota/usage-limit response
switches the process once and keeps Codex active for the rest of that run, avoiding repeated Claude
failures. Set `SHOWRUNNER_FALLBACK_BACKEND=` to disable this behavior.

After an autonomous video passes final validation, raw Blender PNG frames and compositing caches
are removed to reclaim disk space; the voice, timings, review reports, encoded work video and final
MP4 remain. Set `AUTOPILOT_KEEP_WORKFILES=1` before a run if you want to retain frames for manual
`--redo` work.

### Unreal Engine route

Install Unreal Engine 5.8 through Epic Games Launcher, then enable the plugins already declared in
`unreal/VideoCreatorUE/VideoCreatorUE.uproject`: Python Editor Script, Editor Scripting Utilities,
Movie Render Queue, PCG and Geometry Scripting. If Unreal is installed outside the default Epic
Games directory, set `UNREAL_EDITOR_CMD` in `.env`.

The Unreal route is resumable under `output/unreal_projects`. Unreal renders silent 1080x1920 PNG
frames only. The application adds one narration track and local captions afterward, so scene audio,
generated speech, generated subtitles and automatic cut whooshes cannot leak into the final edit.
The first invocation creates the level, Level Sequence and Movie Render Queue preset; later stages
resume from the saved handoff and existing frames.

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
