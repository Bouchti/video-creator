"""
Monocular depth (Depth Anything V2 Small, Apache-2.0) via onnxruntime on the CPU.

The depth map drives the 2.5D camera moves in agents/animate.py: near things
move more than far things, so a still image reads as a moving camera shot.
The ~100 MB model downloads once to %LOCALAPPDATA%/VideoCreator/models.
"""
import os
import logging

import cv2
import numpy as np
import requests

log = logging.getLogger("pipeline")

MODEL_URL = ("https://huggingface.co/onnx-community/depth-anything-v2-small/"
             "resolve/main/onnx/model.onnx")
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
_INPUT_LONG_SIDE = 518  # multiple of 14, the model's patch size

_session = None


def _model_path() -> str:
    base = os.getenv("LOCALAPPDATA") or os.path.expanduser("~/.cache")
    return os.path.join(base, "VideoCreator", "models", "depth_anything_v2_small.onnx")


def _get_session():
    global _session
    if _session is None:
        import onnxruntime as ort
        path = _model_path()
        if not os.path.exists(path):
            log.info("  Downloading depth model (~100 MB, one time)...")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            r = requests.get(MODEL_URL, timeout=300, stream=True)
            r.raise_for_status()
            with open(path + ".part", "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
            os.replace(path + ".part", path)
        _session = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    return _session


def _snap14(x: float) -> int:
    return max(14, int(round(x / 14)) * 14)


def estimate_depth(rgb: np.ndarray) -> np.ndarray:
    """RGB uint8 HxWx3 → float32 HxW in [0, 1], where 1 = nearest to the camera."""
    h, w = rgb.shape[:2]
    scale = _INPUT_LONG_SIDE / max(h, w)
    ih, iw = _snap14(h * scale), _snap14(w * scale)
    x = cv2.resize(rgb, (iw, ih), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    x = ((x - _MEAN) / _STD).transpose(2, 0, 1)[None]

    session = _get_session()
    out = session.run(None, {session.get_inputs()[0].name: x.astype(np.float32)})[0][0]
    d = cv2.resize(out, (w, h), interpolation=cv2.INTER_CUBIC)
    lo, hi = np.percentile(d, 2), np.percentile(d, 98)
    d = np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)
    # Smooth so object edges stretch gently instead of tearing during moves.
    return cv2.GaussianBlur(d, (0, 0), sigmaX=max(w, h) / 250).astype(np.float32)
