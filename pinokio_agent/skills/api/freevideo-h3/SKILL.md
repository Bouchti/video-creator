---
name: api-freevideo-h3
description: Use the FreeVideo H3 ComfyUI node API for local MiniMax H3 video generation with native audio.
---

# FreeVideo H3 API

## Operations

- Confirm the selected ComfyUI server exposes `FreeVideoGenerate` with `GET /object_info/FreeVideoGenerate`.
- Submit a standard ComfyUI API-format graph to `POST /prompt`; the graph may consist of a single `FreeVideoGenerate` output node.
- Poll `GET /history/{prompt_id}` and download the returned video through `GET /view`.
- For first-frame continuity, upload a local still through `POST /upload/image`, load it with `LoadImage`, and connect that image to the generator's `first` input.

## Runtime Inputs

`FreeVideoGenerate` requires `text`, `width`, `height`, `seconds`, and `seed`. The low-VRAM portrait profile uses two-pass generation, eight base steps, three refine steps, and automatic memory streaming managed by FreeVideo.

## Outputs

The output is a video with native audio when the model produced suitable audio. Treat audio as optional: callers should retain a valid video and replace missing or unsuitable audio during editing.

## Notes

Use the public ComfyUI HTTP surface. Do not invoke FreeVideo's bundled executable or internal CLI from clients.
