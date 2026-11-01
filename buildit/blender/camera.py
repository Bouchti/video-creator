"""
The Build-It camera (runs inside Blender): calm eased moves between framings, depth of field on a target.
A framing is {"pos": (x, y, z), "target": (x, y, z), "lens": mm, "fstop": f}; keys are (t, framing).
Vertical sensor: 36 mm tall, so the lens reads like a full-frame lens on the long side.
"""
from __future__ import annotations

import bpy
from mathutils import Vector

from .motion import smooth


class Cam:
    def __init__(self, keys: list[tuple[float, dict]]):
        self.keys = sorted(keys, key=lambda k: k[0])
        cd = bpy.data.cameras.new("cam")
        cd.sensor_fit = "VERTICAL"
        cd.sensor_height = 36.0
        cd.clip_start, cd.clip_end = 0.02, 200.0
        cd.dof.use_dof = True
        self.obj = bpy.data.objects.new("cam", cd)
        bpy.context.scene.collection.objects.link(self.obj)
        bpy.context.scene.camera = self.obj
        self.obj.rotation_mode = "QUATERNION"

    def at(self, t: float) -> dict:
        ks = self.keys
        if t <= ks[0][0]:
            return dict(ks[0][1])
        for (t0, a), (t1, b) in zip(ks, ks[1:]):
            if t <= t1:
                u = smooth((t - t0) / max(1e-6, t1 - t0))
                return {k: (tuple(x + (y - x) * u for x, y in zip(a[k], b[k])) if isinstance(a[k], tuple)
                            else a[k] + (b[k] - a[k]) * u) for k in a}
        return dict(ks[-1][1])

    def place(self, t: float):
        f = self.at(t)
        pos, tgt = Vector(f["pos"]), Vector(f["target"])
        self.obj.location = pos
        self.obj.rotation_quaternion = (tgt - pos).to_track_quat("-Z", "Y")
        cd = self.obj.data
        cd.lens = f["lens"]
        cd.dof.focus_distance = (tgt - pos).length
        cd.dof.aperture_fstop = f.get("fstop", 5.6)

    def key(self, frame: int):
        self.obj.keyframe_insert("location", frame=frame)
        self.obj.keyframe_insert("rotation_quaternion", frame=frame)
        cd = self.obj.data
        cd.keyframe_insert("lens", frame=frame)
        cd.dof.keyframe_insert("focus_distance", frame=frame)
        cd.dof.keyframe_insert("aperture_fstop", frame=frame)
