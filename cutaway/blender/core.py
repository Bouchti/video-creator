"""
Scene and render setup for Cutaway Studio shots (runs inside Blender).

draft: EEVEE at half resolution, low samples, for fast review.
final: Cycles on the GPU (OptiX), OptiX denoiser, motion blur, full 1080x1920.
Both: 30 fps, AgX colour, every random seed fixed, so any frame renders identically in any order.
"""
from __future__ import annotations

import os

import bpy

FPS = 30
WIDTH, HEIGHT = 1080, 1920

QUALITY = {
    "draft": {"engine": "BLENDER_EEVEE", "pct": 50, "samples": 24, "blur": False},
    "look": {"engine": "CYCLES", "pct": 50, "samples": 48, "blur": True},
    "final": {"engine": "CYCLES", "pct": 100, "samples": 96, "blur": True},
}


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras, bpy.data.curves):
        for item in list(block):
            block.remove(item)


def _gpu():
    """Prefer OptiX, then CUDA; fall back to CPU without failing."""
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = kind
            prefs.refresh_devices()
        except TypeError:
            continue
        devs = [d for d in prefs.devices if d.type == kind]
        if devs:
            for d in prefs.devices:
                d.use = d.type == kind
            return kind
    return "CPU"


def setup(quality: str = "draft", samples: int | None = None, pct: int | None = None):
    q = QUALITY[quality]
    sc = bpy.context.scene
    r = sc.render
    r.fps = FPS
    r.fps_base = 1.0
    r.resolution_x, r.resolution_y = WIDTH, HEIGHT
    r.resolution_percentage = pct or q["pct"]
    r.engine = q["engine"]
    r.film_transparent = False
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGB"
    r.image_settings.color_depth = "8"
    r.use_motion_blur = q["blur"]
    r.motion_blur_shutter = 0.5
    r.motion_blur_position = "CENTER"
    n = samples or q["samples"]
    if q["engine"] == "CYCLES":
        cy = sc.cycles
        device = _gpu()
        cy.device = "GPU" if device != "CPU" else "CPU"
        cy.samples = n
        cy.use_adaptive_sampling = True
        cy.adaptive_threshold = 0.02
        cy.use_denoising = True
        cy.denoiser = "OPTIX" if device == "OPTIX" else "OPENIMAGEDENOISE"
        cy.denoising_use_gpu = device != "CPU"
        cy.denoising_input_passes = "RGB_ALBEDO_NORMAL"
        cy.seed = 7
        cy.use_animated_seed = True                  # noise pattern varies per frame, still a function of frame
        cy.sample_clamp_indirect = 6.0
        cy.max_bounces = 8
        cy.glossy_bounces = 4
        cy.transmission_bounces = 8
        cy.volume_bounces = 1
        cy.caustics_reflective = False
        cy.caustics_refractive = False
        cy.use_light_tree = True
    else:
        ee = sc.eevee
        ee.taa_render_samples = n
        ee.use_raytracing = True
        ee.ray_tracing_options.resolution_scale = "2"
        ee.use_shadows = True
        ee.shadow_ray_count = 1
        ee.use_fast_gi = True
        ee.volumetric_samples = 32
        ee.volumetric_tile_size = "4"
    vs = sc.view_settings
    vs.view_transform = "AgX"
    for look in ("AgX - Medium High Contrast", "AgX - Punchy", "Medium High Contrast"):
        try:
            vs.look = look
            break
        except TypeError:
            continue
    vs.exposure = -0.6
    vs.gamma = 1.0
    return sc


def output(path_prefix: str):
    """Frames go to `<prefix>####.png`; the prefix must be absolute (Blender resolves relative paths oddly)."""
    os.makedirs(os.path.dirname(path_prefix), exist_ok=True)
    bpy.context.scene.render.filepath = os.path.abspath(path_prefix)
