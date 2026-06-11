"""
ComfyUI-based editor: generates cinematic clips with a LOCAL video model
(Wan 2.2 14B GGUF, run on the user's GPU) instead of a paid cloud API.

Reuses voice generation, stitching, audio merge, and subtitle burn from
editor_hailuo. Only the clip-generation step differs: each scene prompt is
submitted to a running ComfyUI server through its HTTP/WebSocket API, and the
rendered clip is downloaded back.

Setup (one-time) is documented in the README "Local AI video (ComfyUI)" section.
This module is model-agnostic: it templates the prompt + seed into an exported
ComfyUI "API format" workflow JSON, so swapping models only means swapping that
JSON, never this code.
"""
import os
import json
import copy
import uuid
import time
import random
import logging
from datetime import datetime

import requests
import websocket  # websocket-client
from dotenv import load_dotenv

from config.paths import get_env_path, get_temp_dir, get_comfy_workflow_path

# Reuse the shared pipeline helpers — only clip generation is ComfyUI-specific.
from agents.editor_hailuo import (
    _remove_files,
    get_duration,
    generate_voiceover,
    stitch_clips_to_duration,
    merge_audio_video,
    transcribe_with_whisper,
    words_to_srt,
    burn_subtitles,
    get_scenes,
    scene_prompt,
)

load_dotenv(get_env_path())
log = logging.getLogger("pipeline")

COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
# Per-clip timeout. Wan 2.2 14B on 8 GB VRAM is slow — default generous.
COMFY_TIMEOUT = int(os.getenv("COMFY_TIMEOUT", "3600"))

# Optional explicit node IDs (from the exported workflow). If unset, we
# auto-detect: the positive-prompt node by its _meta.title containing
# "POSITIVE_PROMPT", and the seed node as the first node exposing a seed input.
PROMPT_NODE_ID = os.getenv("COMFY_PROMPT_NODE_ID") or None
SEED_NODE_ID = os.getenv("COMFY_SEED_NODE_ID") or None

# Input keys we know how to set, in priority order.
_PROMPT_TEXT_KEYS = ("text", "positive_prompt", "prompt")
_SEED_KEYS = ("seed", "noise_seed")
_VIDEO_EXTS = (".mp4", ".webm", ".mkv", ".mov")


# ------------------- WORKFLOW TEMPLATING -------------------

def _load_workflow() -> dict:
    """Load the exported ComfyUI API-format workflow JSON."""
    path = os.getenv("COMFY_WORKFLOW") or get_comfy_workflow_path()
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"ComfyUI workflow not found at {path}. Build a text-to-video graph in "
            "ComfyUI, enable 'Save (API Format)', and export it there (see the "
            "README 'Local AI video (ComfyUI)' section)."
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _find_prompt_node(workflow: dict) -> str:
    """Return the node id whose positive prompt text we should overwrite."""
    if PROMPT_NODE_ID:
        if PROMPT_NODE_ID not in workflow:
            raise KeyError(f"COMFY_PROMPT_NODE_ID={PROMPT_NODE_ID} not in workflow")
        return PROMPT_NODE_ID

    # Prefer a node explicitly titled POSITIVE_PROMPT.
    for node_id, node in workflow.items():
        title = (node.get("_meta") or {}).get("title", "")
        if "POSITIVE_PROMPT" in title.upper():
            return node_id

    # Fallback: first node that has a settable text-like input.
    for node_id, node in workflow.items():
        inputs = node.get("inputs", {})
        if any(k in inputs and isinstance(inputs[k], str) for k in _PROMPT_TEXT_KEYS):
            return node_id

    raise RuntimeError(
        "Could not locate a positive-prompt node in the workflow. Title it "
        "'POSITIVE_PROMPT' in ComfyUI or set COMFY_PROMPT_NODE_ID."
    )


def _apply_prompt_and_seed(workflow: dict, prompt: str) -> dict:
    """Return a copy of the workflow with this scene's prompt + a fresh seed.

    One fresh seed is applied to every seed-bearing node (multi-stage samplers,
    e.g. the Wan MoE high/low-noise pair, each carry their own seed input), so
    clips actually vary regardless of which sampler adds the noise.
    """
    wf = copy.deepcopy(workflow)

    prompt_node = wf[_find_prompt_node(wf)]
    for key in _PROMPT_TEXT_KEYS:
        if key in prompt_node["inputs"] and isinstance(prompt_node["inputs"][key], str):
            prompt_node["inputs"][key] = prompt
            break

    seed = random.randint(0, 2**31 - 1)
    target_ids = [SEED_NODE_ID] if SEED_NODE_ID else list(wf.keys())
    for node_id in target_ids:
        inputs = wf.get(node_id, {}).get("inputs", {})
        for key in _SEED_KEYS:
            if key in inputs:
                inputs[key] = seed
    return wf


# ------------------- COMFYUI API -------------------

def _queue_prompt(workflow: dict, client_id: str) -> str:
    """Submit the workflow; return its prompt_id."""
    r = requests.post(
        f"{COMFYUI_URL}/prompt",
        json={"prompt": workflow, "client_id": client_id},
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"ComfyUI /prompt failed: HTTP {r.status_code} {r.text[:400]}")
    prompt_id = r.json().get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI did not return a prompt_id: {r.text[:300]}")
    return prompt_id


def _await_completion(prompt_id: str, client_id: str, clip_number: int) -> None:
    """Block until ComfyUI finishes this prompt, streaming progress over WebSocket."""
    ws_url = COMFYUI_URL.replace("http://", "ws://").replace("https://", "wss://")
    ws = websocket.create_connection(f"{ws_url}/ws?clientId={client_id}", timeout=60)
    deadline = time.time() + COMFY_TIMEOUT
    last_step_log = 0
    try:
        while True:
            if time.time() > deadline:
                raise TimeoutError(
                    f"ComfyUI clip {clip_number} timed out after {COMFY_TIMEOUT}s"
                )
            ws.settimeout(max(1, int(deadline - time.time())))
            try:
                raw = ws.recv()
            except websocket.WebSocketTimeoutException:
                raise TimeoutError(
                    f"ComfyUI clip {clip_number} timed out after {COMFY_TIMEOUT}s"
                )
            if not isinstance(raw, str):
                continue  # binary preview frames — ignore
            msg = json.loads(raw)
            mtype = msg.get("type")
            data = msg.get("data", {})

            if mtype == "progress":
                step, total = data.get("value", 0), data.get("max", 0)
                if total and step - last_step_log >= max(1, total // 5):
                    log.info(f"  Clip {clip_number}: sampling {step}/{total}")
                    last_step_log = step
            elif mtype == "execution_error" and data.get("prompt_id") == prompt_id:
                raise RuntimeError(
                    f"ComfyUI clip {clip_number} errored: "
                    f"{data.get('exception_message', data)}"
                )
            elif mtype == "executing" and data.get("prompt_id") == prompt_id:
                if data.get("node") is None:
                    return  # null node => this prompt is fully executed
    finally:
        ws.close()


def _download_output(prompt_id: str, clip_number: int) -> str:
    """Pull the rendered video for this prompt from ComfyUI history into temp."""
    r = requests.get(f"{COMFYUI_URL}/history/{prompt_id}", timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"ComfyUI /history failed: HTTP {r.status_code}")
    history = r.json().get(prompt_id, {})
    outputs = history.get("outputs", {})

    video = None
    for node_out in outputs.values():
        # VHS_VideoCombine reports under "gifs"; other savers under "videos"/"images".
        for key in ("gifs", "videos", "images"):
            for item in node_out.get(key, []):
                fn = item.get("filename", "")
                if fn.lower().endswith(_VIDEO_EXTS):
                    video = item
                    break
            if video:
                break
        if video:
            break

    if not video:
        raise RuntimeError(
            f"No video output found for clip {clip_number}. Ensure the workflow ends "
            "in a VHS_VideoCombine (or equivalent) node that writes an mp4."
        )

    params = {
        "filename": video["filename"],
        "subfolder": video.get("subfolder", ""),
        "type": video.get("type", "output"),
    }
    dl = requests.get(f"{COMFYUI_URL}/view", params=params, timeout=120, stream=True)
    if dl.status_code != 200:
        raise RuntimeError(f"ComfyUI /view download failed: HTTP {dl.status_code}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(get_temp_dir(), f"clip{clip_number}_{ts}.mp4")
    with open(path, "wb") as f:
        for chunk in dl.iter_content(8192):
            f.write(chunk)
    return path


# ------------------- CLIP GENERATION -------------------

def generate_single_clip(prompt: str, clip_number: int, total_clips: int) -> str:
    """Generate one clip via the local ComfyUI server."""
    log.info(f"[{clip_number}/{total_clips}] Submitting to ComfyUI (local Wan)...")
    workflow = _apply_prompt_and_seed(_load_workflow(), prompt)
    client_id = uuid.uuid4().hex

    started = time.time()
    prompt_id = _queue_prompt(workflow, client_id)
    _await_completion(prompt_id, client_id, clip_number)
    path = _download_output(prompt_id, clip_number)

    size_mb = os.path.getsize(path) / 1024 / 1024
    log.info(f"  Clip {clip_number}: OK ({size_mb:.1f} MB, {time.time()-started:.0f}s)")
    return path


def generate_all_clips(script: dict, num_clips: int) -> list:
    """Sequential clip generation, one clip per connected scene (local, no cost).

    Each prompt carries the script's shared visual_style so the clips read as one
    cohesive film rather than unrelated shots.
    """
    scenes = get_scenes(script)
    num_clips = min(num_clips, len(scenes))
    log.info(f"\n[2/5] Generating {num_clips} connected clips via local ComfyUI (Wan)...\n")
    clips = []
    for i in range(num_clips):
        clips.append(generate_single_clip(scene_prompt(script, i), clip_number=i + 1, total_clips=num_clips))
    log.info(f"\nAll {num_clips} clips ready.\n")
    return clips


# ------------------- MAIN PIPELINE -------------------

def process_video(script: dict, voice: str = "energetic") -> str:
    """Local ComfyUI video + ElevenLabs voice + word-by-word subtitles.

    Same orchestration and cleanup contract as editor_hailuo.process_video;
    only the clip source is local instead of fal.ai.
    """
    audio_path = None
    clips = []
    stitched = None
    merged = None
    srt = None

    try:
        audio_path, audio_duration = generate_voiceover(script["spoken_script"], voice=voice)

        # One clip per connected scene — maximizes unique footage so the loop-fill
        # for long (60-90s) videos repeats as little as possible.
        num_clips = len(get_scenes(script))
        log.info(f"\nVoice = {audio_duration:.1f}s. Generating {num_clips} local clips (one per scene).\n")

        clips = generate_all_clips(script, num_clips=num_clips)

        target_duration = audio_duration + 0.5
        # Local clips are short (~2s) to fit 8GB VRAM at high resolution; loop each
        # clip to fill its narration slot so every beat has its own footage.
        stitched = stitch_clips_to_duration(clips, target_duration=target_duration, loop_to_fill=True)

        merged = merge_audio_video(stitched, audio_path)

        words = transcribe_with_whisper(audio_path)
        srt = merged.replace(".mp4", ".srt")
        words_to_srt(words, srt)
        final = burn_subtitles(merged, srt)

        return final
    finally:
        _remove_files(clips + [stitched, audio_path, merged, srt])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    # Single-clip smoke test (requires a running ComfyUI + exported workflow).
    test = generate_single_clip(
        "a calm ocean wave rolling at golden-hour sunset, cinematic, slow dolly", 1, 1
    )
    log.info(f"Smoke-test clip: {test} ({get_duration(test):.1f}s)")
