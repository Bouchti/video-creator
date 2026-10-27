"""Upscale accepted clips 2x with Real-ESRGAN general-x4v3 on the GPU.

Runs under FreeVideo's engine Python (it has CUDA PyTorch), not this project's venv:
    <FreeVideo>/envs/unified/Scripts/python.exe -B local_video/upscale_worker.py --model <pth> --ffmpeg <exe> IN OUT [IN OUT ...]
local_video.upscale starts it during assembly, after FreeVideo has released the GPU.
Each clip is decoded through ffmpeg, upscaled 4x, scaled back to 2x on the GPU, and re-encoded
at its own frame rate. Prints one JSON line per finished clip.
"""
import argparse
import json
import os
import subprocess
import sys
import time

# This folder holds queue.py, which would shadow the standard library module torch imports.
sys.path = [p for p in sys.path if os.path.abspath(p or ".") != os.path.dirname(os.path.abspath(__file__))]

import torch
import torch.nn.functional as F
from torch import nn


class SRVGGNetCompact(nn.Module):
    """Real-ESRGAN's compact network (BSD-3, xinntao/Real-ESRGAN), as used by realesr-general-x4v3."""

    def __init__(self, num_feat=64, num_conv=32, upscale=4):
        super().__init__()
        self.upscale = upscale
        self.body = nn.ModuleList([nn.Conv2d(3, num_feat, 3, 1, 1), nn.PReLU(num_parameters=num_feat)])
        for _ in range(num_conv):
            self.body.append(nn.Conv2d(num_feat, num_feat, 3, 1, 1))
            self.body.append(nn.PReLU(num_parameters=num_feat))
        self.body.append(nn.Conv2d(num_feat, 3 * upscale * upscale, 3, 1, 1))
        self.upsampler = nn.PixelShuffle(upscale)

    def forward(self, x):
        out = x
        for layer in self.body:
            out = layer(out)
        return self.upsampler(out) + F.interpolate(x, scale_factor=self.upscale, mode="nearest")


def probe(ffmpeg, path):
    ffprobe = ffmpeg[:-len("ffmpeg.exe")] + "ffprobe.exe" if ffmpeg.lower().endswith("ffmpeg.exe") else "ffprobe"
    value = json.loads(subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate",
         "-of", "json", path], capture_output=True, text=True, check=True).stdout)["streams"][0]
    return int(value["width"]), int(value["height"]), value["r_frame_rate"]


def upscale(model, ffmpeg, source, target, batch=4):
    width, height, rate = probe(ffmpeg, source)
    out_w, out_h = width * 2, height * 2
    decode = subprocess.Popen([ffmpeg, "-v", "error", "-i", source, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                              stdout=subprocess.PIPE)
    encode = subprocess.Popen(
        [ffmpeg, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{out_w}x{out_h}", "-r", rate,
         "-i", "-", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "15", "-pix_fmt", "yuv420p", target],
        stdin=subprocess.PIPE)
    size = width * height * 3
    frames = 0
    with torch.inference_mode():
        while True:
            chunk = []
            for _ in range(batch):
                raw = decode.stdout.read(size)
                if len(raw) < size:
                    break
                chunk.append(torch.frombuffer(bytearray(raw), dtype=torch.uint8).view(height, width, 3))
            if not chunk:
                break
            x = torch.stack(chunk).cuda().permute(0, 3, 1, 2).half().div_(255)
            y = model(x)
            y = F.interpolate(y.float(), size=(out_h, out_w), mode="bicubic", antialias=True)
            y = y.clamp_(0, 1).mul_(255).round_().byte().permute(0, 2, 3, 1).contiguous().cpu()
            encode.stdin.write(y.numpy().tobytes())
            frames += len(chunk)
    encode.stdin.close()
    if encode.wait() != 0 or decode.wait() != 0:
        raise RuntimeError(f"ffmpeg failed while upscaling {source}")
    return frames


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("pairs", nargs="+", help="input output [input output ...]")
    args = parser.parse_args()
    if len(args.pairs) % 2:
        parser.error("inputs and outputs must come in pairs")
    state = torch.load(args.model, map_location="cpu", weights_only=True)
    model = SRVGGNetCompact()
    model.load_state_dict(state.get("params_ema") or state.get("params") or state)
    model = model.cuda().half().eval()
    for source, target in zip(args.pairs[::2], args.pairs[1::2]):
        started = time.monotonic()
        frames = upscale(model, args.ffmpeg, source, target)
        print(json.dumps({"source": source, "target": target, "frames": frames,
                          "seconds": round(time.monotonic() - started, 2)}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
