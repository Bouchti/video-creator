"""
Probe 2: picture first, then animation (the local-ai mechanism) in the 3D-cutaway look.

For each shot it makes first-frame stills with local FLUX (FreeVideo's ComfyUI), then animates each
still with local MiniMax H3:
  (a) "text"   FLUX from the cutaway prompt alone
  (b) "layout" FLUX repainting a layout image (a Blender render with the correct plumbing) at a few
               denoise strengths, so the geometry stays right while the look becomes photoreal

    python -m local_video.cutaway_hybrid                      # all variants
    python -m local_video.cutaway_hybrid --only text          # skip the layout variants
    python -m local_video.cutaway_hybrid --stills-only        # FLUX stills only (fast check)

Inputs:  output/_review/cutaway_hybrid/layout_<shot>.png (optional)
Outputs: output/_review/cutaway_hybrid/<shot>_<variant>.png and .mp4, run log in hybrid_log.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from config.paths import PROJECT_ROOT

from .backends import MiniMaxAdapter
from .comfy import ComfyClient
from .config import PipelineConfig
from .freevideo import ensure_minimax
from .keyframes import _image_item, checkpoint_name, has_checkpoint
from .models import Shot
from .planner import h3_prompt
from .upscale import stop_idle_freevideo_worker

LOOK = ("photoreal 3D cutaway cross-section render, premium engineering explainer, objects sliced exactly "
        "in half to show their inside, glossy white ceramic and white PVC, bright clear blue water, clean "
        "brown soil cross-section, warm golden afternoon sunlight with soft shadows, gentle depth of field, "
        "crisp detail, 9:16 vertical")

SHOTS = {
    "toilet": {
        "still": (
            "Side view of a white ceramic toilet with a cistern in a bright bathroom with pale blue walls and "
            "white floor tiles. The toilet is sliced in half from front to back: inside the white ceramic, a "
            "smooth S-shaped trap channel filled with bright blue water leads from the bottom of the bowl, up "
            "over a bend and down to the floor. Under the tiled floor, a thin concrete slab and a brown soil "
            "cross-section. A round white PVC drain pipe, cut open lengthwise so the blue water inside is "
            "visible, goes straight down from the toilet into the soil and turns with a white elbow into a "
            "horizontal pipe."),
        "motion": (
            "The toilet flushes: blue water swirls down out of the bowl, flows through the S-shaped trap inside "
            "the ceramic and rushes down inside the open round pipe into the ground, then along the horizontal "
            "pipe. The toilet, floor, slab and pipes stay exactly in place. Camera: very slow gentle push-in, "
            "steady."),
        "sound": "Toilet flush, water rushing down a pipe.",
    },
}


def _fit(src: Path, dst: Path, w: int, h: int, ffmpeg: str) -> None:
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(src), "-vf",
                    f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h}", str(dst)],
                   check=True, capture_output=True, timeout=120)


def flux_text(prompt, seed, w, h, steps):
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint_name()}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["1", 1]}},
        "4": {"class_type": "EmptySD3LatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0],
            "seed": seed, "steps": steps, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple",
            "denoise": 1.0}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "vc_cutaway"}},
    }


def flux_layout(prompt, image_name, seed, w, h, steps, denoise):
    wf = flux_text(prompt, seed, w, h, steps)
    wf["8"] = {"class_type": "LoadImage", "inputs": {"image": image_name}}
    wf["9"] = {"class_type": "ImageScale", "inputs": {"image": ["8", 0], "upscale_method": "lanczos",
                                                       "width": w, "height": h, "crop": "center"}}
    wf["4"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["9", 0], "vae": ["1", 2]}}
    wf["5"]["inputs"]["denoise"] = denoise
    return wf


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default=",".join(SHOTS))
    ap.add_argument("--only", choices=["text", "layout"], default=None)
    ap.add_argument("--stills-only", action="store_true")
    ap.add_argument("--denoise", default="0.5,0.65")
    ap.add_argument("--seconds", type=float, default=5.0)
    ap.add_argument("--steps", type=int, default=6)
    a = ap.parse_args()
    out = Path(PROJECT_ROOT) / "output" / "_review" / "cutaway_hybrid"
    out.mkdir(parents=True, exist_ok=True)
    config = PipelineConfig()
    config.minimax_seconds = a.seconds
    ok, where = ensure_minimax(config)
    if not ok:
        print(f"FreeVideo/MiniMax is not available: {where}")
        return 1
    if not has_checkpoint(config.minimax_url):
        print(f"{checkpoint_name()} is not visible to ComfyUI at {config.minimax_url}")
        return 1
    log_path = out / "hybrid_log.json"
    log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else []
    W, H = 720, 1280
    stills = []
    # ---- 1. FLUX stills (MiniMax's resident worker is stopped first so FLUX gets the VRAM)
    stop_idle_freevideo_worker()
    client = ComfyClient(config.minimax_url, timeout=900, poll_seconds=1.0)
    try:
        for name in [s.strip() for s in a.shots.split(",") if s.strip()]:
            spec = SHOTS[name]
            prompt = f"{LOOK}. {spec['still']} No text, no watermark."
            variants = []
            if a.only in (None, "text"):
                variants += [("text_a", flux_text(prompt, 11, W, H, a.steps)),
                             ("text_b", flux_text(prompt, 23, W, H, a.steps))]
            layout = out / f"layout_{name}.png"
            if a.only in (None, "layout") and layout.exists():
                remote = client.upload_image(layout)
                for d in [float(x) for x in a.denoise.split(",")]:
                    variants.append((f"layout_d{int(d * 100)}", flux_layout(prompt, remote, 11, W, H, a.steps, d)))
            for variant, wf in variants:
                target = out / f"{name}_{variant}.png"
                if not target.exists():
                    t0 = time.monotonic()
                    raw = client.download(_image_item(client.wait(client.submit(wf))), target.with_suffix(".raw.png"))
                    _fit(raw, target, config.minimax_width, config.minimax_height, config.ffmpeg)
                    raw.unlink(missing_ok=True)
                    print(f"still {target.name} in {time.monotonic() - t0:.0f}s", flush=True)
                stills.append((name, variant, target))
    finally:
        client.free_memory()
    if a.stills_only:
        print(f"stills in {out}")
        return 0
    # ---- 2. MiniMax animates each still (the still is frame 0)
    backend = MiniMaxAdapter(config)
    for name, variant, still in stills:
        target = out / f"{name}_{variant}.mp4"
        if target.exists():
            continue
        spec = SHOTS[name]
        prompt = h3_prompt(f"{LOOK}. {spec['still']} {spec['motion']} No subtitles, no on-screen text.",
                           spec["sound"])
        shot = Shot(id=f"{name}-{variant}", index=0, duration_frames=int(a.seconds * 30), prompt=prompt,
                    negative_prompt="", seed=1000)
        t0 = time.monotonic()
        print(f"animating {target.name} ...", flush=True)
        try:
            backend.generate(shot, target, reference_image=still)
        except Exception as exc:              # keep going: one failed take must not cost the others
            print(f"  FAILED {target.name}: {str(exc)[:400]}", flush=True)
            continue
        dt = time.monotonic() - t0
        print(f"  done in {dt / 60:.1f} min", flush=True)
        log.append({"shot": name, "variant": variant, "minutes": round(dt / 60, 2)})
        log_path.write_text(json.dumps(log, indent=1), encoding="utf-8")
    print(f"clips in {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
