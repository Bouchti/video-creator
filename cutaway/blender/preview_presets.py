"""
Stills of every camera preset of an assembly, each with the cut it is made for (runs inside Blender):

    blender -b --factory-startup -P cutaway/blender/preview_presets.py -- <assembly> <out_dir> [theta] [pct]

One build per cut state; writes <out_dir>/<preset>.png. Used to tune framing and as a kit QA sheet.
"""
from __future__ import annotations

import importlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bpy  # noqa: E402

from cutaway import kits  # noqa: E402
from cutaway.blender import core, section, studio  # noqa: E402
from cutaway.blender.assemblies import ASSEMBLIES  # noqa: E402
from cutaway.blender.camera import ShotCamera, fit_presets  # noqa: E402


def main(assembly, out_dir, theta=370.0, pct=40):
    kit = next(k for k in kits.KITS.values() if k["assembly"] == assembly)
    groups = {}
    for name, (need, _desc) in kit["cameras"].items():
        cut = None if need.startswith("closed") else next((c for c in kit["cuts"] if c in need), None)
        groups.setdefault(cut, []).append(name)
    os.makedirs(out_dir, exist_ok=True)
    hdri = os.path.join(ROOT, "cutaway", "assets", "hdri", "studio_small_09_2k.hdr")
    for cut, cams in groups.items():
        core.reset()
        core.setup("look", samples=32, pct=pct)
        mod, cls = ASSEMBLIES[assembly]
        asm = getattr(importlib.import_module(mod), cls)()
        st = asm.STUDIO
        studio.world(hdri)
        cyc = studio.cyclorama(st["floor_z"], **st.get("cyc", {"size": 4, "wall": 4, "radius": 0.8, "back_y": 1.0}))
        rig = studio.lights(st["center"], st["radius"])
        asm.pose(theta, 1.0) if getattr(asm, "TIMED", False) else asm.pose(theta)
        if cut:
            p = asm.cuts()[cut]
            section.apply(asm.static + asm.fx, asm.moving, section.cutter(p["bounds"]), travel=0.012,
                          cut_moving=p["cut_moving"], own_cap=p["own_cap"])
        presets = fit_presets(asm.cameras(), cams, asm.WIDE, asm.visible())
        turned = 0.0
        for name in cams:
            for o in [o for o in bpy.data.objects if o.name.startswith("shot_cam")]:
                bpy.data.objects.remove(o, do_unlink=True)
            for o in [cyc, *rig.values()]:                  # undo the previous turn, then face this camera
                o.rotation_euler.z -= turned
            import math as _m
            from mathutils import Vector as _V
            for o in [cyc, *rig.values()]:
                rel = o.location - _V((st["center"][0], st["center"][1], 0))
                c, s_ = _m.cos(-turned), _m.sin(-turned)
                o.location = _V((st["center"][0] + rel.x * c - rel.y * s_, st["center"][1] + rel.x * s_ + rel.y * c,
                                 o.location.z))
            d = _V(presets[name]["pos"]) - _V(st["center"])
            turned = _m.atan2(d.y, d.x) - _m.atan2(-1.0, 0.0)
            studio.face_camera([cyc, *rig.values()], st["center"], presets[name]["pos"])
            cam = ShotCamera({"keys": [{"t": 0, "preset": name}]}, presets, asm.anchors)
            cam.obj.data.clip_start, cam.obj.data.clip_end = st.get("clip", (0.01, 50.0))
            cam.place(0.0)
            bpy.context.scene.render.filepath = os.path.join(out_dir, f"{name}.png")
            bpy.ops.render.render(write_still=True)
            print("CUTAWAY " + json.dumps({"event": "still", "preset": name, "cut": cut}), flush=True)


if __name__ == "__main__":
    a = sys.argv[sys.argv.index("--") + 1:]
    main(a[0], a[1], float(a[2]) if len(a) > 2 else 370.0, int(a[3]) if len(a) > 3 else 40)
