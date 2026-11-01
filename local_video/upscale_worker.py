"""Upscale accepted clips 2x with Real-ESRGAN on the GPU.

Runs under FreeVideo's engine Python (it has CUDA PyTorch), not this project's venv:
    <FreeVideo>/envs/unified/Scripts/python.exe -B local_video/upscale_worker.py --model <pth>
        --arch rrdb|compact --scale 2|4 --ffmpeg <exe> IN OUT [IN OUT ...]
local_video.upscale starts it during assembly, after FreeVideo has released the GPU.
Each clip is decoded through ffmpeg, upscaled by the model's own factor, brought to exactly 2x on
the GPU when that factor is 4, and re-encoded at its own frame rate. Prints one JSON line per
finished clip.
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


class ResidualDenseBlock(nn.Module):
    """ESRGAN's dense block (Apache-2.0, XPixelGroup/BasicSR)."""

    def __init__(self, num_feat=64, num_grow_ch=32):
        super().__init__()
        self.conv1 = nn.Conv2d(num_feat, num_grow_ch, 3, 1, 1)
        self.conv2 = nn.Conv2d(num_feat + num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv3 = nn.Conv2d(num_feat + 2 * num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv4 = nn.Conv2d(num_feat + 3 * num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv5 = nn.Conv2d(num_feat + 4 * num_grow_ch, num_feat, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

    def forward(self, x):
        x1 = self.lrelu(self.conv1(x))
        x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
        x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
        x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
        x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
        return x5 * 0.2 + x


class RRDB(nn.Module):
    def __init__(self, num_feat, num_grow_ch=32):
        super().__init__()
        self.rdb1 = ResidualDenseBlock(num_feat, num_grow_ch)
        self.rdb2 = ResidualDenseBlock(num_feat, num_grow_ch)
        self.rdb3 = ResidualDenseBlock(num_feat, num_grow_ch)

    def forward(self, x):
        return self.rdb3(self.rdb2(self.rdb1(x))) * 0.2 + x


class RRDBNet(nn.Module):
    """The full Real-ESRGAN generator (RealESRGAN_x2plus / x4plus). At 2x the input is pixel-unshuffled
    first, so the 23 blocks run at a quarter of the pixels and the network ends at exactly 2x."""

    def __init__(self, scale=4, num_feat=64, num_block=23, num_grow_ch=32):
        super().__init__()
        self.scale = scale
        self.conv_first = nn.Conv2d(3 * (4 if scale == 2 else 1), num_feat, 3, 1, 1)
        self.body = nn.Sequential(*[RRDB(num_feat, num_grow_ch) for _ in range(num_block)])
        self.conv_body = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_up1 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_up2 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_hr = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_last = nn.Conv2d(num_feat, 3, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

    def forward(self, x):
        feat = self.conv_first(F.pixel_unshuffle(x, 2) if self.scale == 2 else x)
        feat = feat + self.conv_body(self.body(feat))
        feat = self.lrelu(self.conv_up1(F.interpolate(feat, scale_factor=2, mode="nearest")))
        feat = self.lrelu(self.conv_up2(F.interpolate(feat, scale_factor=2, mode="nearest")))
        return self.conv_last(self.lrelu(self.conv_hr(feat)))


def probe(ffmpeg, path):
    ffprobe = ffmpeg[:-len("ffmpeg.exe")] + "ffprobe.exe" if ffmpeg.lower().endswith("ffmpeg.exe") else "ffprobe"
    value = json.loads(subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate",
         "-of", "json", path], capture_output=True, text=True, check=True).stdout)["streams"][0]
    return int(value["width"]), int(value["height"]), value["r_frame_rate"]


def upscale(model, ffmpeg, source, target, batch=4):
    width, height, rate = probe(ffmpeg, source)
    out_w, out_h = width * 2, height * 2
    # The 2x network unshuffles 2x2 pixel blocks: an odd side is padded by one edge pixel and cropped after.
    pad_w, pad_h = (width % 2, height % 2) if getattr(model, "scale", 4) == 2 else (0, 0)
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
            x = x.contiguous(memory_format=torch.channels_last)
            if pad_w or pad_h:
                x = F.pad(x, (0, pad_w, 0, pad_h), mode="replicate")
            y = model(x)
            if pad_w or pad_h:
                y = y[:, :, :out_h, :out_w]
            if tuple(y.shape[-2:]) != (out_h, out_w):
                y = F.interpolate(y.float(), size=(out_h, out_w), mode="bicubic", antialias=True)
            y = y.float().clamp_(0, 1).mul_(255).round_().byte().permute(0, 2, 3, 1).contiguous().cpu()
            encode.stdin.write(y.numpy().tobytes())
            frames += len(chunk)
    encode.stdin.close()
    if encode.wait() != 0 or decode.wait() != 0:
        raise RuntimeError(f"ffmpeg failed while upscaling {source}")
    return frames


def load_model(path, arch="compact", scale=4):
    state = torch.load(path, map_location="cpu", weights_only=True)
    model = RRDBNet(scale=scale) if arch == "rrdb" else SRVGGNetCompact(upscale=scale)
    model.load_state_dict(state.get("params_ema") or state.get("params") or state)
    # channels_last lets cuDNN pick its fast fp16 kernels: 0.45 -> 0.28 s per 544x960 frame for x2plus
    # on an RTX 4070.
    torch.backends.cudnn.benchmark = True
    return model.cuda().half().eval().to(memory_format=torch.channels_last)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--arch", choices=["compact", "rrdb"], default="compact")
    parser.add_argument("--scale", type=int, choices=[2, 4], default=4)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("pairs", nargs="+", help="input output [input output ...]")
    args = parser.parse_args()
    if len(args.pairs) % 2:
        parser.error("inputs and outputs must come in pairs")
    model = load_model(args.model, args.arch, args.scale)
    for source, target in zip(args.pairs[::2], args.pairs[1::2]):
        started = time.monotonic()
        frames = upscale(model, args.ffmpeg, source, target, batch=max(1, args.batch))
        print(json.dumps({"source": source, "target": target, "frames": frames,
                          "seconds": round(time.monotonic() - started, 2)}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
