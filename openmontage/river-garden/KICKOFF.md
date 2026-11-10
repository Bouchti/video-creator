# River Garden: OpenMontage kickoff

**Concept:** "What if you ran a river through your garden?" Same structure as the reference short (a sensible plan, an idyllic payoff, slow failure, then a flood), told by a second-person narrator, about 68 seconds, vertical 9:16.

## Locked decisions
- **Pipeline:** `cinematic` (reference analysis already done; see "Reference brief" below)
- **Everything runs locally through ComfyUI. No API keys, no paid calls.**
- **Keyframes:** FLUX 3 on local ComfyUI (`comfyui_image` with a custom workflow). Text-to-image for K0; the FLUX 3 edit workflow for every later keyframe, using the previous keyframe as its input image (chained for continuity).
- **Motion:** MiniMax H3 on local ComfyUI (`comfyui_video`, `model_family: minimax_h3_local`, custom workflow). Use the start and end image wherever the shot sheet gives a last frame.
- **Audio:** single narrator, no dialogue. Calm, curious, slightly deadpan; speeds up from the spring flood. Low ambient bed plus the water and machine sounds MiniMax produces.
- **Captions:** one word at a time, bold white sans with a thin black outline, centred at about 62% of frame height, no animation beyond a quick pop-in. Small "AI-generated" label bottom-left (keep this for platform disclosure).
- **Length:** 9 clips, 68 s total (see `scene_plan.json`)

## Files in this pack
- `script.json`: narration, schema-valid for OpenMontage
- `scene_plan.json`: 9 scenes with keyframe and motion prompts in `required_assets`, schema-valid
- `shot_sheet.md`: the same plan in readable form (keyframe chain, clip table, prompts)

## Local setup (one-time)
OpenMontage's ComfyUI tools send a custom workflow **as-is**: they do not find your prompt or image nodes for you. So it needs your three workflows exported in **API format** (ComfyUI: Workflow > Export (API)) and told which node IDs to fill in for each shot.

1. Start ComfyUI and set `COMFYUI_SERVER_URL=http://127.0.0.1:8188` in OpenMontage's `.env`. Use the URL your ComfyUI actually runs on; for a Pinokio install, check the port Pinokio shows. `COMFYUI_VIDEO_SERVER_URL` can point to the same server.
2. Export these three workflows into `projects/river-garden/workflows/`:
   - `flux3_t2i.json`: FLUX 3 text-to-image, set to 1080x1920
   - `flux3_edit.json`: FLUX 3 image edit (one input image + prompt)
   - `minimax_h3_i2v.json`: MiniMax H3 image-to-video with a start-image and an end-image input, 9:16
3. Fill in `workflows/node_map.json` (template below) with the node IDs from each exported file.
4. Narration: Piper works offline; or reuse the voice from your video-creator pipeline.

`workflows/node_map.json` template:
```json
{
  "flux3_t2i":      {"prompt": "<node id>", "seed": "<node id>", "output": "<node id>"},
  "flux3_edit":     {"prompt": "<node id>", "input_image": "<LoadImage node id>", "seed": "<node id>", "output": "<node id>"},
  "minimax_h3_i2v": {"prompt": "<node id>", "start_image": "<LoadImage node id>", "end_image": "<LoadImage node id or empty>",
                     "length_seconds_or_frames": "<node id>", "seed": "<node id>", "output": "<node id>"}
}
```

## How to run
1. Copy this folder to `OpenMontage/projects/river-garden/` and add the `workflows/` files above.
2. Open the OpenMontage root in Claude Code (or Cursor) and paste the prompt below.

## Prompt to paste

```
Reference-driven production. Project: projects/river-garden/.
The reference analysis, concept choice and provider choice are already done:
read projects/river-garden/KICKOFF.md, script.json, scene_plan.json and shot_sheet.md.

Run the cinematic pipeline from the sample sub-stage onward, following AGENT_GUIDE.md.
Everything is local, no paid providers: FLUX 3 via comfyui_image and MiniMax H3 via
comfyui_video (model_family minimax_h3_local), both with the custom API-format workflows in
projects/river-garden/workflows/. For every call, load the workflow, upload the input
image(s) to ComfyUI, patch the nodes listed in workflows/node_map.json (prompt, images,
seed, length), and pass the result as workflow_json with output_node. 9:16 throughout.
Read the flux-best-practices and minimax-h3 Layer 3 skills before writing prompts.
First run preflight and confirm ComfyUI is reachable and both models are loaded.

Sample first: K0, K1, K2 and clips c1 + c2 with narration s1-s4 and the caption style,
as projects/river-garden/assets/sample/sample_v1.mp4. Stop for my approval after the sample.

Continuity matters most: every keyframe after K0 must be an edit of its listed input
image, not a fresh generation. If an edit drifts (house, fence or camera angle change),
regenerate it with a new seed before animating.
```

## Reference brief (from the analysis)
- **Content:** "What if you did this to your house" story: a beach-to-pool channel works, erodes, gets armoured, then a storm floods the house and street.
- **Style:** Realistic AI-generated 3D, 9:16, word-by-word white captions, fast second-person narration.
- **Structure:** About 76 s. The first 17 s is one continuous evolving aerial of the same garden, then about 12 motion clips of 3 to 6 s, cutting faster during the disaster.
- **Motion:** All generated video clips; continuity carried by reusing the last frame / the same locked aerial angle.
- **What makes it work:** The payoff is shown in the first second; each step seems reasonable; the same place keeps getting worse; arrows and water movement make cause and effect easy to see.
