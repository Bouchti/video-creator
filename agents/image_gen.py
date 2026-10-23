"""
Local image generation: FLUX.1-schnell (Apache-2.0) through ComfyUI on your GPU.

Each beat's scene description becomes one Pixar-style 3D still. Image models
follow prompts far more faithfully than video models, so the picture shows what
the narration says; agents/animate.py then brings it to life. $0 per image.

ComfyUI is started automatically from COMFYUI_DIR when it isn't already running.
The graph is built in code (no exported workflow needed); model file names can
be overridden with FLUX_UNET / FLUX_T5 / FLUX_CLIP_L / FLUX_VAE.
"""
import os
import time
import uuid
import logging
import subprocess

import requests
from dotenv import load_dotenv

from config.paths import get_env_path, get_log_file

load_dotenv(get_env_path())
log = logging.getLogger("pipeline")

COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
COMFYUI_DIR = os.getenv("COMFYUI_DIR", r"C:\ComfyUI_windows_portable")
STARTUP_TIMEOUT = 300

FLUX_UNET = os.getenv("FLUX_UNET", "flux1-schnell-Q4_K_S.gguf")
FLUX_T5 = os.getenv("FLUX_T5", "t5-v1_1-xxl-encoder-Q5_K_M.gguf")
FLUX_CLIP_L = os.getenv("FLUX_CLIP_L", "clip_l.safetensors")
FLUX_VAE = os.getenv("FLUX_VAE", "ae.safetensors")
IMAGE_W, IMAGE_H = 768, 1344      # ~1 MP, 9:16-ish; animate.py upscales to 1080x1920
STEPS = int(os.getenv("FLUX_STEPS", "4"))

# One fixed look for every video, so the channel has a recognisable style.
STYLE = os.getenv("IMAGE_STYLE", (
    "Pixar-style 3D animated movie still, stylized cute characters with expressive faces, "
    "vibrant saturated colors, soft global illumination, warm cinematic lighting, "
    "shallow depth of field, highly detailed 3D render, no text, no letters, no watermark"
))


def build_workflow(prompt: str, seed: int) -> dict:
    """ComfyUI API-format graph: GGUF Flux schnell → 4-step sampling → PNG."""
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": FLUX_UNET}},
        "2": {"class_type": "DualCLIPLoaderGGUF",
              "inputs": {"clip_name1": FLUX_CLIP_L, "clip_name2": FLUX_T5, "type": "flux"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": FLUX_VAE}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]},
              "_meta": {"title": "POSITIVE_PROMPT"}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["2", 0]}},
        "6": {"class_type": "EmptySD3LatentImage",
              "inputs": {"width": IMAGE_W, "height": IMAGE_H, "batch_size": 1}},
        "7": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "seed": seed, "steps": STEPS, "cfg": 1.0,
            "sampler_name": "euler", "scheduler": "simple",
            "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["6", 0], "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "videocreator"}},
    }


def styled_prompt(description: str, characters: list = None) -> str:
    """Scene description + the look of any recurring character it names + the house style."""
    parts = [description.strip().rstrip(".")]
    for c in characters or []:
        name, look = str(c.get("name") or "").strip(), str(c.get("look") or "").strip()
        if name and look and name.lower() in description.lower():
            parts.append(f"{name} is {look}")
    return ". ".join(parts) + ". " + STYLE


# ------------------- SERVER -------------------

def comfy_running() -> bool:
    try:
        return requests.get(f"{COMFYUI_URL}/system_stats", timeout=3).status_code == 200
    except requests.RequestException:
        return False


def ensure_comfy() -> None:
    """Start the portable ComfyUI in the background if it isn't up yet."""
    if comfy_running():
        return
    python = os.path.join(COMFYUI_DIR, "python_embeded", "python.exe")
    main = os.path.join(COMFYUI_DIR, "ComfyUI", "main.py")
    if not (os.path.exists(python) and os.path.exists(main)):
        raise RuntimeError(
            f"ComfyUI is not running at {COMFYUI_URL} and no portable install was found at "
            f"{COMFYUI_DIR}. Start ComfyUI or set COMFYUI_DIR in .env (see README).")
    log.info(f"  Starting ComfyUI from {COMFYUI_DIR} ...")
    log_path = os.path.join(os.path.dirname(get_log_file()), "comfyui.log")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with open(log_path, "ab") as out:
        subprocess.Popen([python, "-s", main, "--windows-standalone-build", "--disable-auto-launch"],
                         cwd=COMFYUI_DIR, stdout=out, stderr=subprocess.STDOUT, creationflags=flags)
    deadline = time.time() + STARTUP_TIMEOUT
    while time.time() < deadline:
        if comfy_running():
            log.info("  ComfyUI is up.")
            return
        time.sleep(3)
    raise RuntimeError(f"ComfyUI did not start within {STARTUP_TIMEOUT}s — see {log_path}")


# ------------------- GENERATION -------------------

def generate_image(prompt: str, seed: int, out_path: str, label: str = "") -> str:
    """Render one image with the local Flux model; returns out_path (PNG)."""
    from agents.editor_comfy import _queue_prompt, _await_completion
    ensure_comfy()
    client_id = uuid.uuid4().hex
    started = time.time()
    prompt_id = _queue_prompt(build_workflow(prompt, seed), client_id)
    _await_completion(prompt_id, client_id, label or "image")

    r = requests.get(f"{COMFYUI_URL}/history/{prompt_id}", timeout=30)
    r.raise_for_status()
    outputs = r.json().get(prompt_id, {}).get("outputs", {})
    image = next((img for node in outputs.values() for img in node.get("images", [])), None)
    if not image:
        raise RuntimeError("ComfyUI returned no image (check logs/comfyui.log)")
    dl = requests.get(f"{COMFYUI_URL}/view", timeout=60, params={
        "filename": image["filename"], "subfolder": image.get("subfolder", ""),
        "type": image.get("type", "output")})
    dl.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(dl.content)
    log.info(f"    Image {label} generated in {time.time() - started:.0f}s")
    return out_path
