"""Face crops for identity review (OpenCV YuNet, Apache-2.0, ~230 KB, CPU).

A reviewer judging "is this the same person" from a whole 9:16 frame downscaled to 512 px sees a
40-pixel face in any medium or wide shot; on the 2026-10-29 Hegdahl run that passed a darker-haired
man of ~30 as the 22-year-old anchor. The crops give it the faces at a size it can compare.
The model downloads once to %LOCALAPPDATA%/VideoCreator/models; any failure returns no crops.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import requests

log = logging.getLogger("pipeline")

MODEL_URL = ("https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/"
             "face_detection_yunet_2023mar.onnx")


def _model_path() -> Path:
    base = os.getenv("LOCALAPPDATA") or os.path.expanduser("~/.cache")
    return Path(base) / "VideoCreator" / "models" / "face_detection_yunet_2023mar.onnx"


def _model() -> Path | None:
    path = _model_path()
    if path.is_file():
        return path
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(MODEL_URL, timeout=60)
        response.raise_for_status()
        path.with_suffix(".part").write_bytes(response.content)
        path.with_suffix(".part").replace(path)
        return path
    except (requests.RequestException, OSError) as exc:
        log.warning("Face detector unavailable (%s); identity review uses whole frames", exc.__class__.__name__)
        return None


def face_crops(image_path: str | Path, limit: int = 3, size: int = 320) -> list[bytes]:
    """JPEG crops of the largest faces, biggest first, each square with room for hair and jaw."""
    try:
        import cv2
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)   # "targets not supported" noise
        model = _model()
        image = cv2.imread(str(image_path))
        if model is None or image is None:
            return []
        height, width = image.shape[:2]
        detector = cv2.FaceDetectorYN.create(str(model), "", (width, height), 0.6, 0.3, 50)
        _, faces = detector.detect(image)
        crops = []
        for face in sorted(faces if faces is not None else [], key=lambda f: -f[2] * f[3])[:limit]:
            x, y, w, h = (float(v) for v in face[:4])
            side = max(w, h) * 1.8
            cx, cy = x + w / 2, y + h / 2 - h * 0.1
            left, top = max(0, int(cx - side / 2)), max(0, int(cy - side / 2))
            right, bottom = min(width, int(cx + side / 2)), min(height, int(cy + side / 2))
            if right - left < 16 or bottom - top < 16:
                continue
            crop = cv2.resize(image[top:bottom, left:right], (size, size), interpolation=cv2.INTER_CUBIC)
            ok, data = cv2.imencode(".jpg", crop, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
            if ok:
                crops.append(data.tobytes())
        return crops
    except Exception as exc:                    # identity review still runs on the whole frame
        log.warning("Face crops failed (%s)", exc.__class__.__name__)
        return []
