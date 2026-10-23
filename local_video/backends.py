"""MiniMax H3/FreeVideo and Wan 2.2 ComfyUI backend adapters."""

from __future__ import annotations

import copy
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .comfy import ComfyClient
from .config import PipelineConfig, probe_model
from .models import Shot


@dataclass
class GenerationResult:
    path: Path
    backend: str
    prompt_id: str
    elapsed_seconds: float
    model: str
    settings: dict[str, Any]


class BackendAdapter:
    name = "base"

    def __init__(self, config: PipelineConfig):
        self.config = config

    def available(self) -> tuple[bool, str]:
        raise NotImplementedError

    def generate(
        self,
        shot: Shot,
        target: Path,
        reference_image: Path | None = None,
        on_submitted: Callable[[str], None] | None = None,
    ) -> GenerationResult:
        raise NotImplementedError


class MiniMaxAdapter(BackendAdapter):
    name = "minimax"
    model = "OpenVDN MiniMax H3 Edge (int8_convrot)"

    def __init__(self, config: PipelineConfig):
        super().__init__(config)
        self.client = ComfyClient(config.minimax_url, config.generation_timeout, config.poll_seconds) if config.minimax_url else None

    def available(self) -> tuple[bool, str]:
        if not self.client:
            return False, "No running ComfyUI service with FreeVideoGenerate was discovered"
        if not self.client.has_node("FreeVideoGenerate"):
            return False, f"FreeVideoGenerate is not installed at {self.client.base_url}"
        return True, self.client.base_url

    def workflow(self, shot: Shot, reference_image: Path | None = None) -> dict[str, Any]:
        inputs: dict[str, Any] = {
            "text": shot.prompt,
            "width": self.config.minimax_width,
            "height": self.config.minimax_height,
            "seconds": self.config.minimax_seconds,
            "seed": shot.seed,
            "two_pass": True,
            "base_steps": 8,
            "refine_steps": 3,
            "force_regenerate": True,
            "step_cache": "none",
            "upscale_factor": "2",
        }
        workflow: dict[str, Any] = {
            "1": {"class_type": "FreeVideoGenerate", "inputs": inputs, "_meta": {"title": shot.id}}
        }
        if reference_image:
            if not self.client:
                raise RuntimeError("MiniMax client is unavailable")
            remote_name = self.client.upload_image(reference_image)
            workflow["2"] = {"class_type": "LoadImage", "inputs": {"image": remote_name}}
            inputs["first"] = ["2", 0]
            inputs["first_frame_reference"] = True
        return workflow

    def generate(self, shot: Shot, target: Path, reference_image: Path | None = None, on_submitted=None) -> GenerationResult:
        ok, reason = self.available()
        if not ok or not self.client:
            raise RuntimeError(reason)
        settings = {
            "resolution": [self.config.minimax_width, self.config.minimax_height],
            "seconds": self.config.minimax_seconds,
            "quality": "light",
            "two_pass": True,
            "base_steps": 8,
            "refine_steps": 3,
            "gpu_streaming": "automatic",
            "native_audio": "generated but discarded during assembly",
            "encoder": "Qwen3-VL 32B NVFP4/AWQ",
        }
        started = time.monotonic()
        path, prompt_id, _ = self.client.generate(self.workflow(shot, reference_image), target, on_submitted)
        return GenerationResult(path, self.name, prompt_id, time.monotonic() - started, self.model, settings)


class WanAdapter(BackendAdapter):
    name = "wan"
    model = "Wan 2.2 TI2V 5B GGUF"

    def __init__(self, config: PipelineConfig):
        super().__init__(config)
        self.client = ComfyClient(config.wan_url, config.generation_timeout, config.poll_seconds) if config.wan_url else None

    def available(self) -> tuple[bool, str]:
        if not self.client:
            return False, "No compatible Wan/ComfyUI service was discovered"
        if not self.config.wan_workflow.is_file():
            return False, f"Wan workflow is missing: {self.config.wan_workflow}"
        try:
            workflow = json.loads(self.config.wan_workflow.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return False, f"Wan workflow is invalid: {exc}"
        missing = sorted({node.get("class_type") for node in workflow.values()} - {
            key for key in (node.get("class_type") for node in workflow.values()) if self.client.has_node(key)
        } - {"VHS_VideoCombine"})
        if missing:
            return False, f"ComfyUI is missing workflow nodes: {', '.join(missing)}"
        required_models = [
            ("UnetLoaderGGUF", "unet_name", self.config.wan_model),
            ("CLIPLoaderGGUF", "clip_name", self.config.wan_encoder),
            ("VAELoader", "vae_name", self.config.wan_vae),
        ]
        absent = [model for node, field, model in required_models
                  if not probe_model(self.client.base_url, node, field, model)]
        if absent:
            return False, f"ComfyUI is missing configured Wan model files: {', '.join(absent)}"
        return True, self.client.base_url

    def _load_workflow(self) -> dict[str, Any]:
        return json.loads(self.config.wan_workflow.read_text(encoding="utf-8"))

    @staticmethod
    def _first_id(workflow: dict[str, Any], class_type: str) -> str | None:
        return next((node_id for node_id, node in workflow.items() if node.get("class_type") == class_type), None)

    def workflow(self, shot: Shot, reference_image: Path | None = None) -> dict[str, Any]:
        workflow = copy.deepcopy(self._load_workflow())
        negative_set = False
        sampler_id: str | None = None
        latent_id: str | None = None
        decoded: list[Any] | None = None
        for node_id, node in workflow.items():
            inputs = node.setdefault("inputs", {})
            class_type = node.get("class_type")
            title = str((node.get("_meta") or {}).get("title", "")).lower()
            if class_type == "UnetLoaderGGUF":
                inputs["unet_name"] = self.config.wan_model
            elif class_type == "CLIPLoaderGGUF":
                inputs["clip_name"] = self.config.wan_encoder
            elif class_type == "VAELoader":
                inputs["vae_name"] = self.config.wan_vae
            elif class_type == "CLIPTextEncode":
                if "negative" in title:
                    inputs["text"] = shot.negative_prompt
                    negative_set = True
                elif "positive" in title or not negative_set:
                    inputs["text"] = shot.prompt
            elif class_type == "Wan22ImageToVideoLatent":
                latent_id = node_id
                inputs.update(width=self.config.wan_width, height=self.config.wan_height,
                              length=self.config.wan_frames, batch_size=1)
            elif class_type == "KSampler":
                sampler_id = node_id
                inputs.update(seed=shot.seed, steps=self.config.wan_steps, cfg=self.config.wan_cfg,
                              sampler_name="uni_pc", scheduler="simple", denoise=1.0)
            elif class_type == "VAEDecode":
                decoded = [node_id, 0]
            elif class_type == "CreateVideo":
                inputs["fps"] = self.config.wan_fps
            elif class_type == "VHS_VideoCombine":
                decoded = inputs.get("images") or decoded
                node["class_type"] = "CreateVideo"
                node["inputs"] = {"images": decoded, "fps": self.config.wan_fps, "codec": "h264"}

        if not decoded:
            raise ValueError("Wan workflow has no decoded image output")
        create_id = self._first_id(workflow, "CreateVideo")
        if not create_id:
            create_id = str(max((int(k) for k in workflow if str(k).isdigit()), default=100) + 1)
            workflow[create_id] = {"class_type": "CreateVideo", "inputs": {
                "images": decoded, "fps": self.config.wan_fps, "codec": "h264"
            }}
        save_id = self._first_id(workflow, "SaveVideo")
        if not save_id:
            save_id = str(max((int(k) for k in workflow if str(k).isdigit()), default=100) + 1)
            workflow[save_id] = {"class_type": "SaveVideo", "inputs": {
                "video": [create_id, 0], "filename_prefix": f"video_creator/{shot.id}",
                "format": "mp4", "codec": "h264"
            }}
        else:
            workflow[save_id]["inputs"].update(video=[create_id, 0], filename_prefix=f"video_creator/{shot.id}")

        if reference_image and latent_id:
            if not self.client:
                raise RuntimeError("Wan client is unavailable")
            image_id = str(max((int(k) for k in workflow if str(k).isdigit()), default=100) + 1)
            remote_name = self.client.upload_image(reference_image)
            workflow[image_id] = {"class_type": "LoadImage", "inputs": {"image": remote_name}}
            workflow[latent_id]["inputs"]["start_image"] = [image_id, 0]
        if not sampler_id:
            raise ValueError("Wan workflow has no KSampler")
        return workflow

    def generate(self, shot: Shot, target: Path, reference_image: Path | None = None, on_submitted=None) -> GenerationResult:
        ok, reason = self.available()
        if not ok or not self.client:
            raise RuntimeError(reason)
        settings = {
            "resolution": [self.config.wan_width, self.config.wan_height],
            "frames": self.config.wan_frames,
            "fps": self.config.wan_fps,
            "steps": self.config.wan_steps,
            "cfg": self.config.wan_cfg,
            "sampler": "uni_pc",
            "scheduler": "simple",
            "denoise": 1.0,
            "model": self.config.wan_model,
            "encoder": self.config.wan_encoder,
            "vae": self.config.wan_vae,
        }
        started = time.monotonic()
        path, prompt_id, _ = self.client.generate(self.workflow(shot, reference_image), target, on_submitted)
        return GenerationResult(path, self.name, prompt_id, time.monotonic() - started, self.model, settings)


def build_backends(config: PipelineConfig) -> dict[str, BackendAdapter]:
    return {"minimax": MiniMaxAdapter(config), "wan": WanAdapter(config)}
