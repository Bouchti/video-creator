"""
Blender-side still test of the standard water (studio.Water) against the old fixed-density Reservoir that made
the tunnel film's sea look solid. A red block sits inside a 5 m deep body, behind the cut face; the still is
rendered and measured: how much of the block's red still reaches the camera, and whether the waterline shows.

    blender --background --factory-startup --python engine/water_still.py -- OUT_DIR

Writes OUT_DIR/water_<variant>.png and OUT_DIR/water_report.json (run by tests/test_water.py).
"""
import json
import math
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import studio as st, toy  # noqa: E402

DEPTH = 5.0                               # the tunnel's sea: 5 m into the picture


def build(variant):
    from engine import textures
    toy.reset_scene()
    toy._materials.clear()                # (material caches outlive a scene reset: two variants in one process)
    textures._cache.clear()
    scene = bpy.context.scene
    scene.render.resolution_percentage = 30
    if hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = 16
    toy.setup_world()
    toy.add_sun()
    sand = bpy.data.materials.new("sand")
    toy._set(toy._principled(sand), "Base Color", (*toy.srgb("#D8C08A"), 1))
    toy.box("seabed", (14, DEPTH + 2, 0.4), (0, DEPTH / 2, -4.2), mat=sand, bevel=0)
    toy.box("backwall", (14, 0.3, 6), (0, DEPTH + 0.4, -1.5), mat=sand, bevel=0)
    red = bpy.data.materials.new("red")
    toy._set(toy._principled(red), "Base Color", (*toy.srgb("#E0262B"), 1))
    toy.box("target", (2.0, 1.0, 2.0), (0, DEPTH * 0.7, -2.6), mat=red, bevel=0)     # 3.5 m behind the cut face
    if variant == "old":
        st.Reservoir("sea", -6, 6, 0.05, DEPTH, bottom=-4.0, level=0.0, density=0.22)
    elif variant.startswith("clear"):                # experiments: clear<percent>[_glow<percent>]
        clear, _, glow = variant[5:].partition("_glow")
        st.Water("sea", -6, 6, 0.05, DEPTH, bottom=-4.0, level=0.0, clear=int(clear) / 100,
                 glow=int(glow or 25) / 100)
    else:
        st.Water("sea", -6, 6, 0.05, DEPTH, bottom=-4.0, level=0.0)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
    cam.location = (0, -9.0, -1.4)
    cam.rotation_euler = (math.radians(90), 0, 0)
    cam.data.lens = 30
    scene.camera = cam
    return scene, cam


def measure(scene, cam, png):
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector
    img = bpy.data.images.load(png)
    w, h = img.size
    px = np.array(img.pixels[:]).reshape(h, w, 4)[:, :, :3]        # rows bottom-up, linear 0..1

    def region(corners):
        pts = [world_to_camera_view(scene, cam, Vector(c)) for c in corners]
        x0, x1 = int(min(p.x for p in pts) * w), int(max(p.x for p in pts) * w)
        y0, y1 = int(min(p.y for p in pts) * h), int(max(p.y for p in pts) * h)
        return px[max(0, y0):y1, max(0, x0):x1].reshape(-1, 3)
    y = DEPTH * 0.7 - 0.5                                            # the block's front face
    block = region([(-0.6, y, -3.2), (0.6, y, -3.2), (-0.6, y, -2.0), (0.6, y, -2.0)])
    water = region([(3.5, y, -3.2), (4.7, y, -3.2), (3.5, y, -2.0), (4.7, y, -2.0)])   # same depth, no block
    line = region([(-5, 0.0, -0.04), (5, 0.0, -0.04), (-5, 0.0, 0.0), (5, 0.0, 0.0)])
    under = region([(-5, 0.0, -0.6), (5, 0.0, -0.6), (-5, 0.0, -0.4), (5, 0.0, -0.4)])
    redness = lambda a: float(np.mean(a[:, 0] - (a[:, 1] + a[:, 2]) / 2)) if len(a) else 0.0   # noqa: E731
    luma = lambda a: float(np.mean(a @ np.array([0.2126, 0.7152, 0.0722]))) if len(a) else 0.0  # noqa: E731
    return {"block_redness": redness(block), "water_redness": redness(water),
            "see_through": redness(block) - redness(water),
            "waterline_luma": luma(line), "under_luma": luma(under), "water_blue": float(np.mean(water[:, 2]))}


def main():
    out = sys.argv[sys.argv.index("--") + 1]
    os.makedirs(out, exist_ok=True)
    report = {}
    for variant in (sys.argv[sys.argv.index("--") + 2:] or ["old", "water"]):
        scene, cam = build(variant)
        png = os.path.join(out, f"water_{variant}.png")
        scene.render.filepath = png
        bpy.ops.render.render(write_still=True)
        report[variant] = measure(scene, cam, png)
    with open(os.path.join(out, "water_report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
