"""
Render setup for Build-It shots (runs inside Blender).

Qualities:
  draft   EEVEE, 50 % resolution, 16 samples: fast review
  final   EEVEE, 100 %, 24 samples, motion blur. Measured on the M0 shot (RTX 4070 laptop): 64 samples 7.0 s a
          frame, 24 samples ~1.5 s with the same look; Cycles 15.6 s and worse for these stylised materials.
          The studio keeps per-sample costs low: unlit haze slices, shadows from the key light only.
  cycles  Cycles on OptiX, 100 %, adaptive 128 samples + OptiX denoise (for comparison / special shots)
All: AgX medium contrast, a soft bloom in the compositor, every frame a pure function of time.
"""
from __future__ import annotations

import os

import bpy

FPS = 30
WIDTH, HEIGHT = 1080, 1920

QUALITY = {
    "draft": {"engine": "BLENDER_EEVEE", "pct": 50, "samples": 16, "blur": False},
    "final": {"engine": "BLENDER_EEVEE", "pct": 100, "samples": 24, "blur": True},
    "cycles": {"engine": "CYCLES", "pct": 100, "samples": 128, "blur": True},
}


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _gpu() -> str:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = kind
            prefs.refresh_devices()
        except TypeError:
            continue
        if any(d.type == kind for d in prefs.devices):
            for d in prefs.devices:
                d.use = d.type == kind
            return kind
    return "CPU"


def setup(quality: str = "draft", pct: int | None = None, samples: int | None = None):
    q = QUALITY[quality]
    sc = bpy.context.scene
    r = sc.render
    r.fps, r.fps_base = FPS, 1.0
    r.resolution_x, r.resolution_y = WIDTH, HEIGHT
    r.resolution_percentage = pct or q["pct"]
    r.engine = q["engine"]
    r.film_transparent = False
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGB"
    r.image_settings.color_depth = "8"
    r.image_settings.compression = 15          # fast writes; frames are temporary
    r.use_motion_blur = q["blur"]
    r.motion_blur_shutter = 0.5
    r.use_persistent_data = True
    n = samples or q["samples"]
    if q["engine"] == "CYCLES":
        cy = sc.cycles
        dev = _gpu()
        cy.device = "GPU" if dev != "CPU" else "CPU"
        cy.samples = n
        cy.use_adaptive_sampling = True
        cy.adaptive_threshold = 0.03
        cy.use_denoising = True
        cy.denoiser = "OPTIX" if dev == "OPTIX" else "OPENIMAGEDENOISE"
        cy.seed = 7
        cy.max_bounces = 6
        cy.transmission_bounces = 6
        cy.volume_bounces = 0
        cy.caustics_reflective = cy.caustics_refractive = False
    else:
        ee = sc.eevee
        ee.taa_render_samples = n
        ee.use_raytracing = True
        ee.ray_tracing_options.resolution_scale = "2"
        ee.use_shadows = True
        ee.shadow_ray_count = 1
        ee.shadow_resolution_scale = 0.5
        ee.use_fast_gi = True
        ee.volumetric_tile_size = "8"
    vs = sc.view_settings
    vs.view_transform = "AgX"
    for look in ("AgX - Punchy", "AgX - Base Contrast", "None"):
        try:
            vs.look = look
            break
        except TypeError:
            continue
    vs.exposure = 0.0
    _bloom(sc)
    return sc


def _bloom(sc, strength: float = 0.5, threshold: float = 0.75):
    """A soft fog-glow bloom on hot spots (flashes, glows, chrome hits), as in the reference."""
    ng = bpy.data.node_groups.new("buildit_comp", "CompositorNodeTree")
    it = ng.interface
    it.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = ng.nodes.new("CompositorNodeRLayers")
    gl = ng.nodes.new("CompositorNodeGlare")
    for name, value in (("Type", "Bloom"), ("Quality", "Medium"), ("Threshold", threshold),
                        ("Strength", strength), ("Size", 0.6)):
        sock = gl.inputs.get(name)
        if sock is None:
            continue
        try:
            sock.default_value = value
        except (TypeError, ValueError):
            pass
    out = ng.nodes.new("NodeGroupOutput")
    ng.links.new(rl.outputs["Image"], gl.inputs["Image"])
    ng.links.new(gl.outputs["Image"], out.inputs[0])
    sc.compositing_node_group = ng
    sc.render.use_compositing = True


def set_bloom(threshold: float, strength: float):
    """Retune the bloom (the bright studio needs a high threshold, or every white wall glows)."""
    ng = bpy.context.scene.compositing_node_group
    for n in ng.nodes:
        if n.bl_idname == "CompositorNodeGlare":
            for name, v in (("Threshold", threshold), ("Strength", strength)):
                s = n.inputs.get(name)
                if s is not None:
                    s.default_value = v


def set_look(look: str = "AgX - Medium High Contrast", exposure: float = 0.0):
    vs = bpy.context.scene.view_settings
    try:
        vs.look = look
    except TypeError:
        pass
    vs.exposure = exposure


def render_frames(out_dir: str, f0: int, f1: int, only: list[int] | None = None) -> int:
    """Render frames f0..f1 into out_dir/f_####.png in ONE animation pass (one scene sync, persistent data),
    skipping frames already on disk. Returns how many were rendered."""
    out_dir = os.path.abspath(out_dir)          # Blender resolves relative output paths against the .blend
    os.makedirs(out_dir, exist_ok=True)
    sc = bpy.context.scene
    todo = only or [f for f in range(f0, f1 + 1)
                    if not os.path.exists(os.path.join(out_dir, f"f_{f:04d}.png"))]
    if not todo:
        return 0
    sc.render.filepath = os.path.join(out_dir, "f_####")
    sc.render.use_overwrite = False
    sc.render.use_placeholder = False
    # contiguous runs render as animations; the rest one by one
    runs, start = [], todo[0]
    for a, b in zip(todo, todo[1:] + [None]):
        if b != a + 1:
            runs.append((start, a))
            start = b
    for a, b in runs:
        sc.frame_start, sc.frame_end = a, b
        bpy.ops.render.render(animation=True)
    return len(todo)
