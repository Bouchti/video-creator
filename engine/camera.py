"""
Shot system: one camera per shot, bound to the timeline with markers (hard cuts).

Each shot has a start/end position and an aim target (an empty that can move),
so every shot is a real camera move — dolly, crane, pan, orbit — with depth of
field focused on the subject, which gives the miniature-world look.
"""
import math

import bpy
from mathutils import Vector

from engine import toy

_count = [0]


def shot(start: int, end: int, cam_from, cam_to, aim_from, aim_to=None, lens=35.0,
         fstop=2.8, ease=True):
    """Create a camera for frames [start, end] that moves cam_from→cam_to while aiming at aim."""
    _count[0] += 1
    n = _count[0]
    scene = bpy.context.scene
    data = bpy.data.cameras.new(f"Cam{n}")
    data.lens = lens
    data.clip_start = 0.05
    data.dof.use_dof = True
    data.dof.aperture_fstop = fstop
    cam = bpy.data.objects.new(f"Cam{n}", data)
    scene.collection.objects.link(cam)

    aim = toy.empty(f"Aim{n}", aim_from)
    if aim_to is not None:
        aim.location = aim_from
        aim.keyframe_insert("location", frame=start)
        aim.location = aim_to
        aim.keyframe_insert("location", frame=end)
    data.dof.focus_object = aim

    con = cam.constraints.new("TRACK_TO")
    con.target = aim
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"

    cam.location = cam_from
    cam.keyframe_insert("location", frame=start)
    cam.location = cam_to
    cam.keyframe_insert("location", frame=end)
    if not ease:
        _linear(cam)

    marker = scene.timeline_markers.new(f"shot{n}", frame=start)
    marker.camera = cam
    if scene.camera is None:
        scene.camera = cam
    return cam


def _linear(obj):
    ad = obj.animation_data
    if not ad or not ad.action:
        return
    curves = getattr(ad.action, "fcurves", None)
    if curves is None:
        curves = [fc for layer in ad.action.layers for strip in layer.strips
                  for bag in strip.channelbags for fc in bag.fcurves]
    for fc in curves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


def facing_to(src, dst) -> float:
    """Character facing angle (deg) so a -Y-facing rig looks from src toward dst."""
    d = Vector(dst) - Vector(src)
    return math.degrees(math.atan2(d.x, -d.y))


class CameraRig:
    """ONE camera for the whole film that GLIDES between shots instead of cutting.

    Each shot holds a framing (from → to over its beat). Between consecutive shots the camera
    flies from the previous framing to the next over `blend` frames at the start of the new
    beat (eased), so the viewer follows a continuous path through one world. A shot with
    cut=True starts with a hard cut instead (e.g. hook → rewind)."""

    def __init__(self, blend: int = 16, name: str = "RigCam"):
        scene = bpy.context.scene
        self.data = bpy.data.cameras.new(name)
        self.data.clip_start = 0.05
        self.data.clip_end = 300
        self.data.dof.use_dof = True
        self.cam = bpy.data.objects.new(name, self.data)
        scene.collection.objects.link(self.cam)
        self.aim = toy.empty(f"{name}_aim")
        self.data.dof.focus_object = self.aim
        con = self.cam.constraints.new("TRACK_TO")
        con.target = self.aim
        con.track_axis = "TRACK_NEGATIVE_Z"
        con.up_axis = "UP_Y"
        scene.camera = self.cam
        self.blend = blend
        self.shots = []

    def shot(self, start, end, cam_from, cam_to=None, aim_from=None, aim_to=None, lens=35.0, fstop=4.0,
             cut=False, blend=None):
        self.shots.append(dict(start=start, end=end, cam_from=Vector(cam_from), cam_to=Vector(cam_to or cam_from),
                               aim_from=Vector(aim_from), aim_to=Vector(aim_to or aim_from), lens=lens,
                               fstop=fstop, cut=cut, blend=self.blend if blend is None else blend))

    def _key(self, frame, loc, aim, lens, fstop, constant=False):
        self.cam.location = loc
        self.cam.keyframe_insert("location", frame=frame)
        self.aim.location = aim
        self.aim.keyframe_insert("location", frame=frame)
        self.data.lens = lens
        self.data.keyframe_insert("lens", frame=frame)
        self.data.dof.aperture_fstop = fstop
        self.data.dof.keyframe_insert("aperture_fstop", frame=frame)
        if constant:
            for obj, path in ((self.cam, "location"), (self.aim, "location")):
                toy.set_interpolation(obj, path, (frame,), "CONSTANT")
            for fc in _data_curves(self.data):
                for kp in fc.keyframe_points:
                    if int(round(kp.co.x)) == frame:
                        kp.interpolation = "CONSTANT"

    def build(self, handheld: float = 0.012):
        shots = sorted(self.shots, key=lambda s: s["start"])
        for i, s in enumerate(shots):
            first = i == 0 or s["cut"]
            if first and i > 0:                       # hard cut: hold the previous framing up to here
                p = shots[i - 1]
                self._key(s["start"] - 1, p["cam_to"], p["aim_to"], p["lens"], p["fstop"], constant=True)
            settle = s["start"] if first else min(s["end"] - 1, s["start"] + s["blend"])
            self._key(settle, s["cam_from"], s["aim_from"], s["lens"], s["fstop"])
            self._key(s["end"], s["cam_to"], s["aim_to"], s["lens"], s["fstop"])
        if handheld:                                  # slow, organic drift: a person holding it
            for axis, ph in ((0, 3), (2, 7)):
                toy.add_noise(self.cam, "location", axis, strength=handheld, scale=45, phase=ph)
                toy.add_noise(self.aim, "location", axis, strength=handheld * 0.6, scale=60, phase=ph + 11)
        return self.cam


def _data_curves(idblock):
    ad = idblock.animation_data
    if not ad or not ad.action:
        return []
    legacy = getattr(ad.action, "fcurves", None)
    if legacy is not None:
        return list(legacy)
    return [fc for layer in ad.action.layers for strip in layer.strips for bag in strip.channelbags
            for fc in bag.fcurves]
