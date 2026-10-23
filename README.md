# Video Creator

Video Creator is a Python pipeline for producing short vertical videos for
TikTok, YouTube Shorts, and similar platforms. It discovers or accepts a topic,
writes and evaluates a script, creates a voiceover, gathers video clips, and
renders a final `1080x1920` MP4 with burned-in word-level subtitles.

### Animated mode (default): Pixar-style 3D scenes that follow the script

`python main.py "topic"` makes a fun, animated short: the script is written as
**beats** (one sentence of narration + the one scene shown while it is spoken),
starring 1-3 recurring characters.

1. **One image per beat**, generated locally on your GPU with FLUX.1-schnell
   (Apache-2.0) through ComfyUI, in a fixed Pixar-style 3D look. Image models
   follow the prompt closely, so each scene shows what its sentence says.
2. **2.5D animation**: a depth map (Depth Anything V2) gives every still a real
   camera move — push-in, pull-out, pans, rise, orbit — where near objects move
   more than the background, plus a zoom "punch" on every cut.
3. **Overlays**: numbers and names said in a beat pop in as animated stickers
   (counting-up stats, name labels) on top of the scene, never as slides.
4. **TikTok captions**: 1-3 big words at a time, the spoken word highlighted,
   each phrase popping in. Spelled from the script, timed by Whisper.
5. **Sound design**: a whoosh on every cut, a pop on every sticker, and an
   optional music bed from `assets/music/`.

Cost: $0 for visuals. Claude (script) and ElevenLabs (voice) are the only paid
calls, and all images are rendered *before* the voiceover, so a GPU problem never
wastes voice credits. See [Animated Mode Setup](#animated-mode-setup).

### Other sources

| Source | Description | Typical tradeoff |
| --- | --- | --- |
| `animated` (default) | Pixar-style 3D scenes generated locally, animated in 2.5D | Free; ~10-20 min per video on an 8 GB GPU |
| `pexels` | Stock/archival footage, real Wikimedia photos, and diagrams, each vision-checked against its sentence | Fast and free, but stock rarely has the exact shot |
| `comfy` | Footage beats as clips from a **local** video model (Wan 2.2) | Free but very slow |
| `hailuo` | Footage beats as clips from Hailuo 02 through fal.ai | Paid per clip — opt-in only |

### Free stock sources (used by `--source pexels`)

`--source pexels` queries several free sources in priority order and merges the
results, so a clip is sourced from whichever has the most on-topic match. Sources
needing a key are skipped automatically when the key is absent; the keyless ones
always run.

| Source | Key | Best for |
| --- | --- | --- |
| Pexels | `PEXELS_API_KEY` | General b-roll |
| Pixabay | `PIXABAY_API_KEY` | General b-roll |
| Coverr | `COVERR_API_KEY` | Cinematic b-roll |
| NASA | none | Space / earth / science |
| Internet Archive | none | Historical / public-domain footage |
| Wikimedia Commons | none | Historical / educational footage |

Reorder priority with the `STOCK_SOURCES` env var (comma-separated). For the
"untold historical stories" niche, putting `archive,wikimedia` first favours
on-topic period footage over generic stock, e.g.
`STOCK_SOURCES=archive,wikimedia,pexels,pixabay,nasa`.

> [!IMPORTANT]
> Publishing to social platforms is not implemented. The pipeline creates the
> final video and metadata locally.

## Pipeline

1. Select a trending topic with Tavily and Claude, or use a topic supplied on
   the command line.
2. Generate a beat-structured script with Claude (narration + one visual per beat).
3. Evaluate the script for factual accuracy, safety, length, and whether every
   visual matches its words.
4. Generate an ElevenLabs voiceover.
5. Transcribe it with Faster Whisper and time each beat to its words.
6. Build each beat's visual (diagram, vision-checked photo, or vision-checked
   footage) for exactly its time slot.
7. Concatenate, merge with the voiceover, and burn subtitles with FFmpeg.
8. Save the final MP4 and a `.txt` with title, description, hashtags, and photo
   credits in `output/`.

## Requirements

- Windows 10 or Windows 11
- Python 3.12
- FFmpeg and FFprobe available on `PATH`
- Internet access
- API accounts for the services used by your selected workflow
- Several gigabytes of free disk space for Python packages, the Whisper model,
  temporary clips, and rendered videos

The first transcription can take longer because Faster Whisper may download its
model files.

## Quick Start on Windows

Open PowerShell and clone the repository:

```powershell
git clone https://github.com/Bouchti/video-creator.git
cd video-creator
```

Install Python and FFmpeg if they are not already installed:

```powershell
winget install --id Python.Python.3.12 --exact
winget install --id Gyan.FFmpeg --exact
```

Close and reopen PowerShell after installation, then verify both tools:

```powershell
py -3.12 --version
ffmpeg -version
ffprobe -version
```

Create a Windows virtual environment and install the Python dependencies:

```powershell
py -3.12 -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create the local configuration file:

```powershell
Copy-Item .env.example .env
notepad .env
```

Add the API keys needed for your workflow, then generate a video:

```powershell
.\venv\Scripts\python.exe main.py --source pexels "Why Roman concrete survives underwater"
```

The completed video will be written to `output/`.

### Existing Linux Virtual Environment

Python virtual environments are not portable between operating systems. If this
folder contains a `venv` created on Linux, remove or rename it before creating a
Windows environment:

```powershell
Rename-Item venv venv-linux
py -3.12 -m venv venv
```

## API Configuration

Copy `.env.example` to `.env` and populate the required values:

```dotenv
ANTHROPIC_API_KEY=
TAVILY_API_KEY=
ELEVENLABS_API_KEY=
FAL_API_KEY=
PEXELS_API_KEY=
PIXABAY_API_KEY=
COVERR_API_KEY=
STOCK_SOURCES=pexels,pixabay,coverr,nasa,archive,wikimedia
COMFYUI_URL=http://127.0.0.1:8188
COMFY_WORKFLOW=
COMFY_TIMEOUT=3600
```

| Variable | Used for | When required |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | Topic selection, script generation, and evaluation | Always |
| `ELEVENLABS_API_KEY` | Voiceover generation | Always |
| `TAVILY_API_KEY` | Trending-topic search | Only when no topic is supplied |
| `PEXELS_API_KEY` | Pexels stock-footage search | With `--source pexels` |
| `PIXABAY_API_KEY` | Pixabay stock source | Optional; extra free source for `--source pexels` |
| `COVERR_API_KEY` | Coverr stock source | Optional; extra free source for `--source pexels` |
| `STOCK_SOURCES` | Priority order of stock sources | Optional; defaults to all six |
| `FAL_API_KEY` | Hailuo clip generation through fal.ai | With `--source hailuo` |
| `COMFYUI_URL` | Address of the local ComfyUI server | With `--source comfy` (defaults to `http://127.0.0.1:8188`) |
| `COMFY_WORKFLOW` | Path to a custom exported workflow JSON | Optional; blank uses `config/comfy_workflow_wan.json` |
| `COMFY_TIMEOUT` | Per-clip generation timeout in seconds | Optional; defaults to `3600` |
| `VISION_CHECK` | Vision check on stock clips and photos (`0` disables) | Optional; defaults to on |
| `VISION_MODEL` | Claude model for the vision check | Optional; defaults to the pipeline model |
| `HTTP_USER_AGENT` | User agent for Wikimedia / Internet Archive requests | Optional; defaults to the project URL |

No API key is required for `--source comfy` — generation runs entirely on your
own GPU.

Example minimal configuration for a manual topic with Pexels:

```dotenv
ANTHROPIC_API_KEY=your_key
ELEVENLABS_API_KEY=your_key
PEXELS_API_KEY=your_key
```

Never commit `.env`. It is already excluded by `.gitignore`.

## Usage

Show all command-line options:

```powershell
.\venv\Scripts\python.exe main.py --help
```

### Manual Topic with Pexels

```powershell
.\venv\Scripts\python.exe main.py --source pexels "How octopuses solve complex puzzles"
```

### Manual Topic with Hailuo

```powershell
.\venv\Scripts\python.exe main.py --source hailuo "Why the Sahara was once green"
```

### Manual Topic with Local ComfyUI

Requires the one-time setup in [Local AI Video (ComfyUI)](#local-ai-video-comfyui)
and a running ComfyUI server.

```powershell
.\venv\Scripts\python.exe main.py --source comfy "Why the Sahara was once green"
```

### Automatic Trending Topic

Omit the topic to let Tavily and Claude choose one:

```powershell
.\venv\Scripts\python.exe main.py --source pexels
```

### Tone and Voice

```powershell
.\venv\Scripts\python.exe main.py `
  --source pexels `
  --tone epic `
  --voice storyteller `
  "How ancient aqueducts carried water for miles"
```

Built-in voice names are:

- `energetic`
- `mysterious`
- `storyteller`

An unknown voice name falls back to `energetic`.

Common script tones include `mysterious`, `epic`, `shocking`, `emotional`, and
`educational`.

## Animated Mode Setup

One-time setup (~13 GB download) for the default `animated` source:

1. Download and extract ComfyUI portable for NVIDIA to `C:\ComfyUI_windows_portable`
   (or set `COMFYUI_DIR`).
2. Install the GGUF loader node:
   ```powershell
   git clone https://github.com/city96/ComfyUI-GGUF C:\ComfyUI_windows_portable\ComfyUI\custom_nodes\ComfyUI-GGUF
   C:\ComfyUI_windows_portable\python_embeded\python.exe -s -m pip install -r C:\ComfyUI_windows_portable\ComfyUI\custom_nodes\ComfyUI-GGUF\requirements.txt
   ```
3. Put the model files in `C:\ComfyUI_windows_portable\ComfyUI\models\`:

   | File | Folder | Source |
   | --- | --- | --- |
   | `flux1-schnell-Q4_K_S.gguf` | `unet/` | `city96/FLUX.1-schnell-gguf` |
   | `t5-v1_1-xxl-encoder-Q5_K_M.gguf` | `text_encoders/` | `city96/t5-v1_1-xxl-encoder-gguf` |
   | `clip_l.safetensors` | `text_encoders/` | `comfyanonymous/flux_text_encoders` |
   | `ae.safetensors` | `vae/` | `Comfy-Org/Lumina_Image_2.0_Repackaged` (`split_files/vae/`) |

The pipeline starts ComfyUI automatically in the background when it isn't
running (log: `logs/comfyui.log`). The depth model (~100 MB) downloads itself on
first use.

Optional settings:

| Variable | Purpose | Default |
| --- | --- | --- |
| `COMFYUI_DIR` | Portable ComfyUI folder | `C:\ComfyUI_windows_portable` |
| `IMAGE_STYLE` | Style text appended to every scene prompt | Pixar-style 3D |
| `FLUX_UNET`, `FLUX_T5`, `FLUX_CLIP_L`, `FLUX_VAE`, `FLUX_STEPS` | Model files / steps | Files above, 4 steps |
| `MUSIC_DIR` | Folder of royalty-free music tracks (one picked per video) | `assets/music/` |
| `MUSIC_VOLUME` | Music bed volume under the voice | `0.12` |

## Local AI Video (ComfyUI)

`--source comfy` generates clips with a video model running on your own GPU,
driven through ComfyUI's API. There is no per-clip charge, but generation is
slow and needs a one-time setup. This was built and tuned for an **8 GB VRAM**
GPU (RTX 4070 Laptop) using **Wan 2.2 14B in GGUF** with block-swap offload —
the strongest quality that fits 8 GB. Expect roughly **30–60+ minutes** for a
full six-scene video on that hardware.

The Python side is model-agnostic: it injects each scene's prompt and a fresh
seed into an exported workflow JSON, then downloads the rendered clip. Swapping
models or quality tiers only means exporting a different workflow — no code
change.

### 1. Install ComfyUI

Install [Pinokio](https://pinokio.computer/) and use its 1-click ComfyUI
installer, or install ComfyUI manually. Launch it and confirm the server is up:

```powershell
Invoke-WebRequest http://127.0.0.1:8188/system_stats | Select-Object StatusCode
```

### 2. Add custom nodes

Using ComfyUI Manager, install:

- **ComfyUI-GGUF** (city96) — loads GGUF-quantized models to save VRAM.
- **ComfyUI-WanVideoWrapper** (kijai) — Wan sampler plus a block-swap node, the
  proven low-VRAM path for the 14B model on 8 GB.
- **ComfyUI-VideoHelperSuite** — provides `VHS_VideoCombine` to write an `.mp4`.

### 3. Download model files

Into the matching ComfyUI `models/` subfolders:

- Wan 2.2 14B text-to-video UNet, **GGUF Q4_K_M or Q5** (quality/VRAM sweet spot).
- `umt5-xxl` text encoder (GGUF quant).
- Wan 2.1/2.2 VAE.

### 4. Build and export the workflow

In ComfyUI, build a text-to-video graph: GGUF UNet loader → block-swap →
positive/negative text encode → Wan sampler (target ~81 frames @ 16 fps ≈ 5 s,
resolution **720×1280 vertical**) → VAE decode → `VHS_VideoCombine` (mp4). Tune
the block-swap block count until it fits 8 GB without an out-of-memory error.

Then:

1. **Title the positive-prompt node `POSITIVE_PROMPT`** (right-click → Title) so
   the pipeline can find it. Alternatively set `COMFY_PROMPT_NODE_ID` in `.env`.
2. Enable **Settings → Enable Dev mode Options**, then use **Save (API Format)**
   to export the graph to `config/comfy_workflow_wan.json`.

The pipeline auto-detects the seed node (the sampler input named `seed` or
`noise_seed`); set `COMFY_SEED_NODE_ID` only if auto-detection picks the wrong one.

### 5. Run

With ComfyUI running:

```powershell
.\venv\Scripts\python.exe main.py --source comfy "Why the Sahara was once green"
```

If 8 GB is still too tight even at Q4, fall back (in order): raise the
block-swap count, drop to a lower GGUF quant, or switch to **Wan 2.2 TI2V-5B**.
Each is just a different exported workflow JSON.

## Durable MiniMax H3 / Wan Production

`--source local-ai` is the production workflow for 60-90 second immersive
vertical videos. It uses the existing Pinokio/ComfyUI services; it does not
install or launch a second ComfyUI copy.

The pipeline discovers compatible running services by capability. MiniMax H3
requires the `FreeVideoGenerate` node and is preferred in Auto mode. Wan uses
the exported API workflow at `config/comfy_workflow_wan.json`. Explicit
`MINIMAX_COMFYUI_URL` and `WAN_COMFYUI_URL` settings take priority when needed.

Each project has a durable `project.json` manifest and follows these states:

```text
draft -> planning -> queued -> generating -> validating -> assembling -> rendering -> completed
```

It can also be `paused`, `cancelled`, `failed`, or `partially_completed`.
Successful shots are never regenerated on resume. A global lock serializes GPU
work across projects, and ComfyUI itself remains responsible for its shared
device queue.

### Create the first 60-second TikTok

1. Start the existing FreeVideo H3 / shared ComfyUI service in Pinokio. Keep the
   Wan-capable ComfyUI service running if you want Auto fallback.
2. Confirm FFmpeg and the service:

   ```powershell
   ffmpeg -version
   Invoke-WebRequest http://127.0.0.1:8190/system_stats | Select-Object StatusCode
   ```

3. Create the script and inspect the exact 20-shot plan without using GPU time:

   ```powershell
   .\venv\Scripts\python.exe -m local_video.cli create `
     "A diver follows a light beneath an abandoned underwater city" `
     --duration 60 `
     --style "cinematic deep-sea realism, bioluminescent cyan and amber" `
     --backend auto `
     --music "slow submerged pulse" `
     --ambience "underwater pressure, bubbles, distant metal resonance" `
     --captions both
   ```

4. Copy the printed project ID, review `output/projects/<project-id>/project.json`,
   then start or resume it:

   ```powershell
   .\venv\Scripts\python.exe -m local_video.cli run <project-id>
   ```

   Add `--run` to the `create` command to combine steps 3 and 4. During the run,
   the CLI shows the active shot, completed/total shots, elapsed time, ETA,
   backend, and actionable errors.

5. Deliverables are saved under `output/projects/<project-id>/`: `final.mp4`,
   `thumbnail.jpg`, `captions.srt`, `captions.ass`, `project.json`, per-shot MP4s,
   rendered audio stems, and `logs/generation.jsonl`.

The final video is 1080x1920 at 30 FPS, H.264/AAC, loudness-normalized, captioned,
and FFprobe-validated against the exact requested duration.

### Reference image and custom narration

```powershell
.\venv\Scripts\python.exe -m local_video.cli create `
  "The last train across a frozen planet" `
  --duration 75 `
  --reference-image .\references\conductor.png `
  --narration-file .\narration.txt `
  --backend minimax `
  --run
```

The shared reference is used on the first shot. After each successful shot, the
pipeline extracts its final frame and supplies it to the next backend when that
backend supports first-frame conditioning.

Use `--no-narration` for a music-and-ambience edit. If MiniMax native audio is
missing, the visual is retained and a continuous replacement soundtrack is
built from available ambience, effects, narration, and music.

### Pause, resume, retry, cancel, and regenerate

Controls are cooperative: pause or cancel takes effect after the active GPU
generation finishes, avoiding interruption of unrelated clients on the shared
ComfyUI service.

```powershell
.\venv\Scripts\python.exe -m local_video.cli status <project-id>
.\venv\Scripts\python.exe -m local_video.cli pause <project-id>
.\venv\Scripts\python.exe -m local_video.cli resume <project-id>
.\venv\Scripts\python.exe -m local_video.cli cancel <project-id>
.\venv\Scripts\python.exe -m local_video.cli retry <project-id>
.\venv\Scripts\python.exe -m local_video.cli regenerate <project-id> 7
```

Regeneration archives the prior clip under `superseded/`; it does not delete the
previous output. Invalid clips are retained under `rejected/` with their errors
and settings in the manifest and JSONL log.

The integrated one-command entry point is:

```powershell
.\venv\Scripts\python.exe main.py --source local-ai --backend auto --duration 60 `
  --visual-style "cinematic macro nature documentary" `
  "How a seed survives a wildfire"
```

### Local AI settings

| Variable | Default | Purpose |
| --- | --- | --- |
| `MINIMAX_COMFYUI_URL` | discovered | FreeVideo H3 ComfyUI base URL |
| `WAN_COMFYUI_URL` | discovered | Wan-capable ComfyUI base URL |
| `LOCAL_VIDEO_OUTPUT_DIR` | `output/projects` | Durable project root |
| `LOCAL_VIDEO_RETRY_LIMIT` | `2` | New-seed retries after the first attempt |
| `LOCAL_VIDEO_FALLBACK_FAILURES` | `2` | MiniMax failures before recorded Auto fallback |
| `LOCAL_VIDEO_GENERATION_TIMEOUT` | `3600` | Maximum seconds for one generated shot |
| `LOCAL_VIDEO_UPSCALE_FILTER` | `lanczos` | `lanczos`, `bicubic`, or `spline` final upscale |
| `WAN_WORKFLOW` | bundled workflow | Exported Wan API workflow path |
| `WAN_MODEL` | `Wan2.2-TI2V-5B-Q5_K_M.gguf` | Wan diffusion model |
| `WAN_ENCODER` | `umt5-xxl-encoder-Q4_K_M.gguf` | Wan text encoder |

Auto fallback is always written to `project.json` and displayed; the pipeline
never silently switches models.

## Output and Logs

Final videos use this naming pattern:

```text
output/YYYYMMDD_HHMMSS_SOURCE_VIDEO_TITLE.mp4
```

Runtime logs are written to:

```text
logs/pipeline.log
```

Recent automatically selected topics are stored in:

```text
output/used_topics.json
```

Temporary media is created in the operating system's temporary directory and
removed after successful or failed runs where possible.

## Testing

Run the regression suite:

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

Compile-check all Python modules:

```powershell
.\venv\Scripts\python.exe -m compileall -q main.py agents config tests
```

The tests do not call paid APIs.

## macOS and Linux

Install Python 3.12 and FFmpeg using your package manager, then run:

```bash
python3.12 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
python main.py --source pexels "Your topic"
```

Package names and Python commands vary by distribution.

## Costs and Runtime

- Pexels does not charge for stock-footage downloads under its API terms, but
  Claude and ElevenLabs usage can still incur charges.
- Hailuo mode also incurs fal.ai video-generation charges (one clip per footage
  beat), which is why it is never the default.
- The vision check makes one small Claude request per photo/footage beat
  (a few cents per video). Set `VISION_CHECK=0` to skip it.
- ComfyUI mode has no per-clip charge (it runs locally) but is the slowest
  source and depends on your GPU; Claude and ElevenLabs usage still applies.
- Provider pricing and limits can change. Review each provider's current
  pricing before running batches.
- Hailuo generation can take several minutes per clip.
- CPU transcription and FFmpeg rendering time depend on the machine.

Diagrams and photos render locally in a few seconds each. A 75-second video has
roughly 25 beats.

## Troubleshooting

### `python`, `py`, or the virtual environment is not found

Restart PowerShell after installing Python. Verify:

```powershell
py -3.12 --version
```

If the Python launcher is unavailable, use the installed executable directly:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m venv venv
```

### `ffmpeg` or `ffprobe` is not recognized

Install FFmpeg and restart PowerShell:

```powershell
winget install --id Gyan.FFmpeg --exact
```

Then verify:

```powershell
ffmpeg -version
ffprobe -version
```

### An API key is reported as missing

Confirm `.env` exists in the repository root, the variable name matches
`.env.example`, and there are no quotes or spaces around the key unless they are
part of the key itself.

### Script generation repeatedly fails

Review `logs/pipeline.log`. The evaluator allows three generation attempts. Try
a narrower, factual topic if the script is rejected for unverifiable claims or
unsafe scene prompts.

### Pexels cannot find footage

Try a more visual topic containing concrete people, places, animals, objects, or
environments. Abstract topics are harder to match with stock footage.

### Hailuo generation times out

The project stops waiting for a clip after six minutes. Check the fal.ai
dashboard, account balance, and API status before retrying.

### Subtitle rendering fails

Confirm FFmpeg includes the `drawtext` filter:

```powershell
ffmpeg -filters | Select-String drawtext
```

On Windows the project looks for Arial Bold or Segoe UI Bold. On Linux it looks
for DejaVu Sans Bold or Liberation Sans Bold.

### The first transcription is slow

This is expected while Faster Whisper downloads and initializes the `base`
model. Later runs in the same environment should start faster.

## Project Structure

```text
.
|-- agents/
|   |-- leader.py          # Trending-topic discovery
|   |-- script.py          # Structured script generation
|   |-- evaluator.py       # Script quality control
|   |-- beats.py           # Beat schema, validation, and word-timing alignment
|   |-- image_gen.py       # Local Flux image generation through ComfyUI
|   |-- depth.py           # Depth Anything V2 (ONNX, CPU) for 2.5D motion
|   |-- animate.py         # 2.5D camera moves + animated overlays
|   |-- captions.py        # TikTok-style animated captions (ASS)
|   |-- audio_fx.py        # Whooshes, pops, optional music bed
|   |-- editor_beats.py    # Beat pipeline: picks, times, and assembles each visual
|   |-- diagram.py         # Animated diagram templates (our own renderer)
|   |-- photos.py          # Wikimedia photo search + Ken Burns render
|   |-- vision.py          # Claude vision check on candidate thumbnails
|   |-- render.py          # Shared Pillow -> FFmpeg frame encoder, fonts, layout
|   |-- editor_hailuo.py   # Voice, Hailuo, FFmpeg, and subtitles
|   |-- editor_pexels.py   # Pexels footage workflow
|   |-- editor_comfy.py    # Local ComfyUI (Wan) workflow
|   |-- editor_local_ai.py # Durable MiniMax/Wan production integration
|   `-- publisher.py       # Explicit unimplemented publishing boundary
|-- config/
|   |-- paths.py           # Portable paths and shared model configuration
|   `-- comfy_workflow_wan.json
|-- local_video/           # Manifests, planner, backends, queue, validation, render, CLI
|-- tests/
|   |-- test_pipeline_helpers.py
|   `-- test_local_video.py
|-- .env.example
|-- main.py
`-- requirements.txt
```

## Current Limitations

- Social-platform publishing is not implemented.
- The pipeline expects English transcription.
- Subtitle styling is fixed in code.
- API calls are sequential; Hailuo generation can therefore be slow.
- Factual quality depends partly on model evaluation and should be reviewed
  before public publication.
- Generated media, scripts, and provider outputs may be subject to provider
  terms and content policies.

## Security

- Keep `.env` private.
- Rotate a key immediately if it is committed or shared accidentally.
- Review generated scripts and videos before publication.
- Do not process confidential material through external providers unless their
  terms and your data-handling requirements permit it.
