"""
Shot cameras from a shot spec (runs inside Blender). Every value is a pure function of time.

    "camera": {"keys": [{"t": 5.2, "preset": "section_front"},
                        {"t": 8.9, "preset": "chamber_close", "orbit": -12, "dolly": 0.1, "rise": 0.02}],
               "focus": "piston_1", "fstop": 4.0, "handheld": 0.3}

A key names a preset (pos, target, lens) from the assembly and may orbit it (degrees about the target's
vertical), dolly it (fraction of the distance toward the target) or raise it (metres). Between keys the
camera moves around the interpolated target in spherical coordinates with an ease-in-out, so moves read as
arcs (orbits, push-ins, crane-ups), never as straight-line slides through the subject.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Vector


def smooth(u: float) -> float:
    """Ease in-out (smootherstep): zero velocity and acceleration at both ends."""
    u = max(0.0, min(1.0, u))
    return u * u * u * (u * (u * 6 - 15) + 10)


def resolve_key(key: dict, presets: dict, anchors_at) -> dict:
    p = presets[key["preset"]]
    target = anchors_at(p["target"]) if isinstance(p["target"], str) else Vector(p["target"])
    if "target" in key:
        target = anchors_at(key["target"]) if isinstance(key["target"], str) else Vector(key["target"])
    pos = Vector(p["pos"])
    off = pos - Vector(p["target"] if not isinstance(p["target"], str) else target)
    orbit = math.radians(key.get("orbit", 0.0))
    off = Vector((off.x * math.cos(orbit) - off.y * math.sin(orbit), off.x * math.sin(orbit) + off.y * math.cos(orbit),
                  off.z))
    off *= 1.0 - key.get("dolly", 0.0)
    off.z += key.get("rise", 0.0)
    return {"t": key["t"], "target": target, "off": off, "lens": key.get("lens", p["lens"]),
            "fstop": key.get("fstop", p.get("fstop", 5.6)), "shift": p.get("shift", 0.0)}


def _sph(v: Vector):
    r = v.length
    return r, math.atan2(v.y, v.x), math.asin(max(-1.0, min(1.0, v.z / r)))


def _lerp_angle(a, b, u):
    d = (b - a + math.pi) % math.tau - math.pi
    return a + d * u


def at_time(keys: list[dict], t: float) -> dict:
    """Camera state (pos, target, lens, fstop) at time t from resolved keys."""
    if t <= keys[0]["t"] or len(keys) == 1:
        k = keys[0]
        return {"pos": k["target"] + k["off"], "target": k["target"], "lens": k["lens"], "fstop": k["fstop"],
                "shift": k["shift"]}
    if t >= keys[-1]["t"]:
        k = keys[-1]
        return {"pos": k["target"] + k["off"], "target": k["target"], "lens": k["lens"], "fstop": k["fstop"],
                "shift": k["shift"]}
    for a, b in zip(keys, keys[1:]):
        if a["t"] <= t <= b["t"]:
            u = smooth((t - a["t"]) / max(1e-6, b["t"] - a["t"]))
            ra, aza, ela = _sph(a["off"])
            rb, azb, elb = _sph(b["off"])
            r = math.exp(math.log(ra) + (math.log(rb) - math.log(ra)) * u)
            az = _lerp_angle(aza, azb, u)
            el = ela + (elb - ela) * u
            off = Vector((r * math.cos(el) * math.cos(az), r * math.cos(el) * math.sin(az), r * math.sin(el)))
            target = a["target"].lerp(b["target"], u)
            return {"pos": target + off, "target": target, "lens": a["lens"] + (b["lens"] - a["lens"]) * u,
                    "fstop": a["fstop"] + (b["fstop"] - a["fstop"]) * u,
                    "shift": a["shift"] + (b["shift"] - a["shift"]) * u}
    raise ValueError("unreachable")


def handheld(t: float, amount: float, seed: int = 3) -> tuple[Vector, Vector]:
    """Small seeded drift (position metres, aim metres): sums of slow sines, a function of t only."""
    if amount <= 0:
        return Vector(), Vector()
    rnd = [((seed * 7919 + i * 104729) % 1000) / 1000.0 for i in range(12)]
    def wob(i, f):
        return math.sin(t * f * (0.7 + 0.6 * rnd[i]) + rnd[i + 1] * math.tau)
    pos = Vector((wob(0, 0.9), wob(2, 0.7), wob(4, 0.8))) * 0.0025 * amount
    aim = Vector((wob(6, 1.1), wob(8, 0.95), wob(10, 1.3))) * 0.0018 * amount
    return pos, aim


class ShotCamera:
    def __init__(self, spec: dict, presets: dict, anchors: dict):
        self.spec = spec
        self.anchors = anchors
        cam = bpy.data.cameras.new("shot_cam")
        cam.sensor_fit = "VERTICAL"
        cam.sensor_height = 36.0                   # 'lens' reads as full-frame vertical: 50 mm feels natural
        cam.clip_start = 0.01
        cam.clip_end = 50.0
        cam.dof.use_dof = True
        self.obj = bpy.data.objects.new("shot_cam", cam)
        self.obj.rotation_mode = "QUATERNION"
        self._q = None
        bpy.context.scene.collection.objects.link(self.obj)
        bpy.context.scene.camera = self.obj
        self.presets = presets
        self.keys = [resolve_key(k, presets, self._anchor_pos) for k in spec["keys"]]

    def _anchor_pos(self, name):
        bpy.context.view_layer.update()
        return self.anchors[name].matrix_world.translation.copy()

    def state(self, t: float) -> dict:
        s = at_time(self.keys, t)
        dp, da = handheld(t, self.spec.get("handheld", 0.0))
        s["pos"] = s["pos"] + dp
        s["target"] = s["target"] + da
        return s

    def place(self, t: float):
        """Set the camera for time t (call after the mechanism is posed for t: focus follows its anchor)."""
        s = self.state(t)
        o, cam = self.obj, self.obj.data
        o.location = s["pos"]
        q = (s["target"] - s["pos"]).to_track_quat("-Z", "Y")
        if self._q is not None and self._q.dot(q) < 0:      # keep the sign continuous for blur/interpolation
            q.negate()
        self._q = q
        o.rotation_quaternion = q
        cam.lens = s["lens"]
        cam.shift_y = s["shift"]
        cam.dof.aperture_fstop = self.spec.get("fstop", s["fstop"])
        focus = self.spec.get("focus")
        fp = self._anchor_pos(focus) if focus else s["target"]
        cam.dof.focus_distance = max(0.05, (fp - s["pos"]).length)
        return s

    def key(self, frame: int):
        o, cam = self.obj, self.obj.data
        o.keyframe_insert("location", frame=frame)
        o.keyframe_insert("rotation_quaternion", frame=frame)
        cam.keyframe_insert("lens", frame=frame)
        cam.keyframe_insert("shift_y", frame=frame)
        cam.dof.keyframe_insert("focus_distance", frame=frame)
        cam.dof.keyframe_insert("aperture_fstop", frame=frame)


# ------------------------------------------------------------ framing to the layout bands

def _projected_box(cam_obj, objs, stride: int = 7):
    """Screen box (px) of the evaluated geometry (cuts applied), from a stride of its vertices: corners of
    bounding boxes overstate a perspective silhouette."""
    from bpy_extras.object_utils import world_to_camera_view
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    xs, ys = [], []
    for o in objs:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        mw = o.matrix_world
        verts = me.vertices
        for i in range(0, len(verts), stride):
            p = world_to_camera_view(sc, cam_obj, mw @ verts[i].co)
            if p.z > 0:
                xs.append(p.x * 1080)
                ys.append((1 - p.y) * 1920)
        ev.to_mesh_clear()
    if not xs:
        return None
    return min(xs), max(xs), min(ys), max(ys)


def fit_presets(presets: dict, names, wide: set, objs, band=(380, 1330), max_w: float = 1250.0) -> dict:
    """Adjust presets so the subject sits in the mechanism band: wide presets dolly until the whole visible
    machine fills the band (height; its sides may crop a little past the frame, up to max_w), then shift the lens so its box centres in the band;
    close presets only shift so their target lands at the band centre. Returns new preset dicts."""
    from bpy_extras.object_utils import world_to_camera_view
    out = dict(presets)
    probe = ShotCamera({"keys": [{"t": 0, "preset": next(iter(presets))}]}, presets, {})
    cam = probe.obj
    centre = (band[0] + band[1]) / 2
    want_h = band[1] - band[0]
    for name in set(names):
        p = dict(presets[name])
        tgt = Vector(p["target"])
        off = Vector(p["pos"]) - tgt
        p["shift"] = 0.0
        for _ in range(4):
            probe.presets = {name: p}
            probe.keys = [resolve_key({"t": 0, "preset": name}, probe.presets, lambda n: None)]
            probe.place(0.0)
            bpy.context.view_layer.update()
            if name in wide:
                box = _projected_box(cam, objs)
                if box is None:
                    break
                x0, x1, y0, y1 = box
                f = max((y1 - y0) / want_h, (x1 - x0) / max_w)
                if abs(f - 1.0) > 0.02:
                    off = off * f
                    p["pos"] = tuple(tgt + off)
                    continue
                cy = (y0 + y1) / 2
            else:
                v = world_to_camera_view(bpy.context.scene, cam, tgt)
                cy = (1 - v.y) * 1920
            p["shift"] = p["shift"] - (cy - centre) / 1920.0    # +shift moves content down
            probe.presets = {name: p}
            probe.keys = [resolve_key({"t": 0, "preset": name}, probe.presets, lambda n: None)]
            probe.place(0.0)
            bpy.context.view_layer.update()
            break
        out[name] = p
    bpy.data.objects.remove(cam, do_unlink=True)
    return out
