# Video Creator

Video Creator is a Python pipeline for producing short vertical videos for
TikTok, YouTube Shorts, and similar platforms. It discovers or accepts a topic,
writes and evaluates a script, creates a voiceover, gathers video clips, and
renders a final `1080x1920` MP4 with burned-in word-level subtitles.

The project supports three video sources:

| Source | Description | Typical tradeoff |
| --- | --- | --- |
| `pexels` | Downloads real footage from multiple free stock + archival sources | Faster and no footage-generation charge |
| `hailuo` | Generates cinematic clips with Hailuo 02 through fal.ai | Slower and paid, but tailored to the script |
| `comfy` | Generates clips with a **local** model (Wan 2.2) through ComfyUI | No per-clip charge and highest control, but slow and requires a one-time GPU setup |

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
2. Generate a structured 30-second script with Claude.
3. Evaluate the script for factual accuracy, safety, length, and scene quality.
4. Generate an ElevenLabs voiceover.
5. Download Pexels footage, generate Hailuo clips, or generate local ComfyUI clips.
6. Convert footage to vertical video and merge it with the voiceover.
7. Transcribe the voiceover with Faster Whisper and burn subtitles with FFmpeg.
8. Save the final MP4 in `output/`.

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
- Hailuo mode also incurs fal.ai video-generation charges.
- ComfyUI mode has no per-clip charge (it runs locally) but is the slowest
  source and depends on your GPU; Claude and ElevenLabs usage still applies.
- Provider pricing and limits can change. Review each provider's current
  pricing before running batches.
- Hailuo generation can take several minutes per clip.
- CPU transcription and FFmpeg rendering time depend on the machine.

The pipeline creates up to six Hailuo clips and up to eight Pexels clips per
video.

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
|   |-- editor_hailuo.py   # Voice, Hailuo, FFmpeg, and subtitles
|   |-- editor_pexels.py   # Pexels footage workflow
|   |-- editor_comfy.py    # Local ComfyUI (Wan) workflow
|   `-- publisher.py       # Explicit unimplemented publishing boundary
|-- config/
|   `-- paths.py           # Portable paths and shared model configuration
|-- tests/
|   `-- test_pipeline_helpers.py
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
