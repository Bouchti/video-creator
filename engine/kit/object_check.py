"""
Builds every object of a kit world ON ITS OWN and measures it before any staging code uses it (Blender):

    blender --background --factory-startup --python engine/kit/object_check.py -- <world> <out_dir> [--no-render]

For each object in the world's vocabulary OBJECTS (name, size_m), engine/kit/worlds/<world>_objects.py must
define build_<name>() returning the object's root. Checked: it builds without an error, has real geometry,
its size matches the design (every axis within 0.6x-1.6x), every visible mesh has a material and the big
surfaces are not one flat colour. One still per object goes to <out_dir>/<name>.png for the look check.
Writes <out_dir>/objects.json: {"objects": {name: [issue, ...]}, "sizes": {name: [x, y, z]}}.
"""
import importlib
import json
import math
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from engine import qa, toy  # noqa: E402

TOLERANCE = (0.6, 1.6)


def _meshes(root):
    out = [root] if root.type == "MESH" else []
    for child in root.children_recursive:
        if child.type == "MESH" and qa._visible(child):
            out.append(child)
    return out


def _bounds(meshes):
    dg = bpy.context.evaluated_depsgraph_get()
    lo, hi = None, None
    for o in meshes:
        _tree, box = qa._mesh_tree(o, dg)
        if box is None:
            continue
        lo = box[0] if lo is None else Vector(map(min, lo, box[0]))
        hi = box[1] if hi is None else Vector(map(max, hi, box[1]))
    return lo, hi


def check(world, out_dir, render=True):
    vocab = importlib.import_module(f"engine.kit.worlds.{world}_vocab")
    objects = importlib.import_module(f"engine.kit.worlds.{world}_objects")
    report = {"objects": {}, "sizes": {}}
    for item in vocab.OBJECTS:
        name, want = item["name"], item["size_m"]
        issues = report["objects"].setdefault(name, [])
        scene = toy.reset_scene()
        toy.setup_world(sun_elevation_deg=42, sun_rotation_deg=190, strength=0.22)
        toy.add_sun(rotation_deg=(52, 0, 22), strength=4.2, angle_deg=2)
        build = getattr(objects, f"build_{name}", None)
        if build is None:
            issues.append(f"missing: {world}_objects.py defines no build_{name}()")
            continue
        try:
            root = build()
        except Exception:                                   # noqa: BLE001  reported to the builder agent
            issues.append("crashed: " + traceback.format_exc()[-900:])
            continue
        if root is None:
            issues.append(f"build_{name}() returned None; it must return the object's root")
            continue
        meshes = _meshes(root)
        lo, hi = _bounds(meshes)
        if lo is None:
            issues.append("empty: no visible geometry")
            continue
        size = [round(hi[k] - lo[k], 3) for k in range(3)]
        report["sizes"][name] = size
        for axis, got, target in zip("xyz", size, (want["x"], want["y"], want["z"])):
            if target > 0 and not TOLERANCE[0] <= got / target <= TOLERANCE[1]:
                issues.append(f"size: {axis} is {got:.2f} m, the design says {target:.2f} m (real proportions)")
        bare = [o.name for o in meshes if not any(s.material for s in o.material_slots)]
        if bare:
            issues.append(f"no material on: {', '.join(bare[:6])}")
        volume = lambda o: math.prod(max(d, 0.01) for d in o.dimensions)        # noqa: E731
        flat = [o.name for o in sorted(meshes, key=volume, reverse=True)[:5]
                if o.material_slots and all(qa._is_flat(s.material) for s in o.material_slots if s.material)]
        if flat:
            issues.append(f"flat: {', '.join(flat)} use one flat colour; use engine.studio / engine.textures "
                          "materials (a real surface)")
        if render:
            centre = (lo + hi) / 2
            span = max(size) or 1.0
            cam_data = bpy.data.cameras.new("objcam")
            cam_data.lens = 40
            cam = bpy.data.objects.new("objcam", cam_data)
            scene.collection.objects.link(cam)
            cam.location = centre + Vector((span * 1.1, -span * 2.2, span * 0.9))
            cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
            scene.camera = cam
            scene.render.resolution_x, scene.render.resolution_y = 640, 640
            scene.render.resolution_percentage = 100
            scene.eevee.taa_render_samples = 8
            scene.render.image_settings.file_format = "PNG"
            scene.render.filepath = os.path.join(out_dir, f"{name}.png")
            bpy.ops.render.render(write_still=True)
    with open(os.path.join(out_dir, "objects.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    return report


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:]
    os.makedirs(args[1], exist_ok=True)
    rep = check(args[0], os.path.abspath(args[1]), render="--no-render" not in args)
    print(f"OBJECT CHECK: {sum(len(v) for v in rep['objects'].values())} issues")
