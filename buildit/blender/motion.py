"""
Motion for Build-It shots (runs inside Blender): every animated thing is a function of time, baked to one key
per frame, so frames render in any order and a resumed render matches.

    tl = Timeline()
    tl.add(drop_in(obj, t=1.0, height=0.8))          # lands at t=1.0 with a little bounce, hidden before
    tl.add(pop_in(obj, t=2.0))                       # scales up from 0 with overshoot
    tl.add(lambda t: setattr(...))                   # any pose function
    tl.bake(f0, f1)
"""
from __future__ import annotations

import math

import bpy

FPS = 30


def clamp01(u: float) -> float:
    return 0.0 if u < 0 else 1.0 if u > 1 else u


def smooth(u: float) -> float:
    u = clamp01(u)
    return u * u * u * (u * (u * 6 - 15) + 10)


def back_out(u: float, s: float = 1.6) -> float:
    """Ease out with an overshoot past 1, settling back (the reference's "lands and settles")."""
    u = clamp01(u) - 1
    return 1 + u * u * ((s + 1) * u + s)


def settle(u: float, bounces: float = 1.6, decay: float = 5.0) -> float:
    """0 -> 1 fall with a damped bounce at the end (0 at u=0, 1 from about u=0.55, small rebounds after)."""
    u = clamp01(u)
    fall = 0.55
    if u < fall:
        x = u / fall
        return x * x
    x = (u - fall) / (1 - fall)
    return 1 - 0.06 * math.exp(-decay * x) * abs(math.sin(math.pi * bounces * x * 2))


class Timeline:
    def __init__(self):
        self.poses = []            # callables pose(t)
        self.objects = set()       # objects whose transforms / props / visibility are keyed

    def add(self, item):
        fn, objs = item if isinstance(item, tuple) else (item, ())
        self.poses.append(fn)
        self.objects.update(objs)
        return self

    def watch(self, *objs):
        self.objects.update(objs)
        return self

    def pose(self, t: float):
        for fn in self.poses:
            fn(t)

    def bake(self, f0: int, f1: int, extra=()):
        """Key every watched object (and `extra`) on every frame f0-1 .. f1+1 (motion blur needs neighbours)."""
        objs = set(self.objects) | set(extra)
        for f in range(f0 - 1, f1 + 2):
            self.pose((f - 1) / FPS)
            for o in objs:
                key(o, f)


def key(o, f: int):
    o.keyframe_insert("location", frame=f)
    o.keyframe_insert("rotation_euler", frame=f)
    o.keyframe_insert("scale", frame=f)
    o.keyframe_insert("hide_render", frame=f)
    for k in ("glow", "fill", "flow_on"):
        if k in o.keys():
            o.keyframe_insert(f'["{k}"]', frame=f)
    if "gn_inputs" in o.keys():                   # Geometry Nodes inputs driven per frame
        for ident in o["gn_inputs"].split(","):
            o.keyframe_insert(f'modifiers["{o["gn_mod"]}"].properties.inputs.{ident}.value', frame=f)
    if o.type == "LIGHT":
        o.data.keyframe_insert("energy", frame=f)


# ------------------------------------------------------------ entrances

def _hide_all(obj, hidden: bool):
    for o in (obj, *obj.children_recursive):
        o.hide_render = hidden


def drop_in(obj, t: float, height: float = 0.9, dur: float = 0.55):
    """Falls from `height` above its rest place and lands at time t with a small bounce; hidden before."""
    rest = obj.location.copy()
    objs = (obj, *obj.children_recursive)

    def f(now):
        u = (now - (t - dur * 0.55)) / dur
        _hide_all(obj, u < 0)
        obj.location = rest.copy()
        obj.location.z = rest.z + height * (1 - settle(u))
    return f, objs


def pop_in(obj, t: float, dur: float = 0.35, s: float = 1.8):
    """Scales up from nothing to full size with an overshoot, starting at t."""
    rest = obj.scale.copy()
    objs = (obj, *obj.children_recursive)

    def f(now):
        u = (now - t) / dur
        _hide_all(obj, u <= 0)
        k = max(0.0, back_out(u, s)) if u < 1 else 1.0
        obj.scale = (rest.x * k, rest.y * k, rest.z * k)
    return f, objs


def slide_in(obj, t: float, offset=(-1.2, 0, 0), dur: float = 0.6):
    """Slides in from `offset` and arrives at t with an overshoot."""
    rest = obj.location.copy()
    objs = (obj, *obj.children_recursive)

    def f(now):
        u = (now - (t - dur)) / dur
        _hide_all(obj, u < 0)
        k = 1 - back_out(u, 1.2)
        obj.location = (rest.x + offset[0] * k, rest.y + offset[1] * k, rest.z + offset[2] * k)
    return f, objs


def lerp_keys(keys: list[tuple[float, float]], t: float, ease=smooth) -> float:
    """Value at time t from [(t, v), ...], eased between keys, held outside."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * ease((t - t0) / max(1e-6, t1 - t0))
    return keys[-1][1]
