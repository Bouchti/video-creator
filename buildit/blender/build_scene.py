"""
Compile a storyboard into an animated Blender scene and render a frame range (runs inside Blender):

    blender -b --factory-startup -P buildit/blender/build_scene.py -- job.json

job.json: {"storyboard": {...}, "words": [...], "duration": s, "quality": "draft|final|preview",
           "frames": [f0, f1] | "stills": [f, ...], "out_dir": abs path, "hdri": abs path | null}

The film is one persistent world: the host machine (a see-through fridge, washer, heater...) stands in a bright
studio and the story's parts fly in and click into its slots, pipes run along it and light up with colour-coded
moving dashes showing what flows where, and the part being talked about glows at its edges. Props (the hook and
analogy objects) stand on stage spots in front of / beside it; an analogy can fly out of its prop into the
machine. A shot is a stretch of time with its own framing, solved by projecting what it must show, so the
subject fills the picture above the captions.

Nothing is keyframed: a frame-change handler poses everything as a pure function of time (t = (frame + subframe -
1) / 30), so frames render in any order, motion-blur sub-frames are exact, and a resumed render matches. Writes
f_####.png and anchors.json (screen positions of every part.anchor and machine.anchor).
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from buildit.blender import core, effects, flowpipe, host, kit, studio  # noqa: E402
from buildit.blender import materials as M  # noqa: E402
from buildit.blender.motion import back_out, clamp01, smooth  # noqa: E402
from buildit.kit import hosts, layout  # noqa: E402
from buildit.kit.vocab import FLOW_COLORS, SPEEDS  # noqa: E402
from cutaway.blender import anchors as A  # noqa: E402

FPS = 30
TAU = math.tau
W_PX, H_PX = 1080, 1920
BAND_MACHINE = (330, 1450)         # the whole machine down to the captions (a part at its base must stay clear)
BAND = (330, 1440)                 # where the subject lives on screen (px from the top): under the loop strip,
                                   # above the captions
METALS = {"steel", "copper", "brass", "black"}
MIN_SUBJECT = 0.32                 # metres: the smallest box a close shot frames (a 10 cm knob keeps its context)
FLOW_SPEED = {"slow": 0.14, "normal": 0.3, "fast": 0.6}       # metres a second the dashes travel
AREA_REACH = 0.75                  # metres: how far a connected neighbour may be to share an area shot
MIN_PROP = 0.16                    # a prop alone on the studio floor needs no context: it fills its shot
CAPTION_ZONE = (1460, 1600)         # px from the top where the captions sit (buildit/config.CAPTION_Y)
# real gas (volumetric puffs, buildit/blender/materials.gas): look and motion of each kind
#   kind: (colour, glow colour, glow strength, density, seconds to travel the path, puffs, start / end radius)
GAS = {
    "cold": ("#f4fbff", "#d6efff", 0.6, 16.0, 1.0, 9, 0.025, 0.13),     # a spray of cold gas out of a can / nozzle
    "steam": ("#ffffff", "#ffffff", 0.3, 9.0, 1.8, 9, 0.03, 0.16),       # steam, exhaust, hot gas into the air
    "heat": ("#ffc58a", "#ff6a1a", 3.6, 8.0, 2.4, 10, 0.05, 0.18),       # heat leaving / arriving: a warm haze
    "vapour": ("#ffffff", "#e9f3fb", 0.25, 7.0, 2.2, 8, 0.02, 0.12),     # a wisp of vapour (drying, breath)
}
HEAT_HOLD = 6.0                    # seconds heat waves show when the storyboard never switches them off
JET_LOOK = {   # kind: (ramp, strength, dot size, stretch) for jets out of a port (spray, steam, exhaust)
    "air": (((0, "#ffffff"), (1, "#dcecff")), 4.5, 0.0045, 2.2),
    "cold_gas": (((0, "#f2fbff"), (1, "#9ad8ff")), 4.0, 0.004, 2.4),
    "hot_gas": (((0, "#ffd08a"), (1, "#ff5a1a")), 6.0, 0.005, 2.4),
    "steam": (((0, "#ffffff"), (1, "#eef3f7")), 2.5, 0.009, 1.2),
    "exhaust": (((0, "#a9a39b"), (1, "#5f5a55")), 1.6, 0.007, 1.3),
    "water": (((0, "#cfeeff"), (1, "#4aa3ff")), 4.0, 0.0055, 1.4),
}


def say(event, **kw):
    print("BUILDIT " + json.dumps({"event": event, **kw}), flush=True)


def _rgb(hexc):
    c = M.hex_rgb(hexc)
    return (c[0], c[1], c[2])


def ease_out(u):
    u = clamp01(u)
    return 1 - (1 - u) ** 3


class World:
    def __init__(self, job):
        self.job = job
        self.sb = job["storyboard"]
        self.words = job["words"]
        self.duration = job["duration"]
        self.place = hosts.solve(self.sb)
        self.boxes = layout.solve(self.sb)
        self.spans = layout.spans(self.sb, self.words, self.duration)
        self.parts: dict[str, kit.Part] = {}
        self.specs = {p["id"]: p for p in self.sb["parts"]}
        self.poses = []
        self.anchor_objs: dict = {}
        self.htype, self.hdims, _dr, _ab, self.accent, _sl = hosts.host(self.sb)

    def t_of(self, word: int) -> float:
        w = self.words[max(0, min(int(word), len(self.words) - 1))]
        return float(w["start"])

    def mounted(self, pid):
        return bool(self.place.get(pid, {}).get("slot"))

    # ------------------------------------------------------------ build
    def build(self):
        self.events = sorted(self.sb.get("events", []), key=lambda e: e.get("word", 0))
        self.host = host.build(self.htype)
        acc = _rgb(self.accent)
        for m in self.host.meshes:
            m["hl_col"] = acc
        for name, e in self.host.anchors.items():
            self.anchor_objs[f"machine.{name}"] = e
        self._host_motion()
        # solid pieces of the machine itself (open doors, the solid side) count as obstacles for close shots
        bpy.context.view_layer.update()
        self.occluders = {}
        for m in self.host.meshes:
            if not any(k in m.name for k in ("glass", "lamp", "produce", "bottle", "cap", "bin", "foot", "kick", "shelf_", "jar", "cake")):
                cs = [m.matrix_world @ Vector(c) for c in m.bound_box]
                lo = Vector([min(q[i] for q in cs) for i in range(3)])
                hi = Vector([max(q[i] for q in cs) for i in range(3)])
                self.occluders[m.name] = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z, hi.x - lo.x, hi.y - lo.y,
                                          hi.z - lo.z)
        for spec in self.sb["parts"]:
            pl = self.place[spec["id"]]
            spec = dict(spec)
            if pl.get("slot"):                      # machine parts keep their real finish (no candy-blue compressor)
                keep = METALS | ({"white"} if spec["type"] == "bottle" else set())
                spec["color"] = spec.get("color") if spec.get("color") in keep else None
            elif spec.get("color") == "white":      # a white prop vanishes against the bright studio
                spec["color"] = None
            p = kit.build(spec, k=pl["k"])
            p.root.location = (pl["x"], pl["y"], pl["z"])
            p.root.rotation_euler.z = math.radians(pl["rot"])
            p.base = Vector((pl["x"], pl["y"], pl["z"]))
            p.rot = math.radians(pl["rot"])
            for m in p.meshes:
                m["hl"] = 0.0
                m["hl_col"] = acc
            self.parts[spec["id"]] = p
            if str(pl.get("slot") or "").startswith("back"):   # brackets: visibly fixed to the back panel
                gap = pl["y"] - pl["d"] / 2 - self.hdims[1] / 2
                if gap > 0.004:
                    from cutaway.blender import geo as _geo
                    for sx in (-1, 1):
                        for sz in (0.3, 0.75):
                            b = _geo.box(f"{spec['id']}_bracket", (0.035, gap + 0.03, 0.03),
                                         (sx * pl["w"] * 0.32, pl["d"] / 2 + gap / 2, pl["h"] * sz),
                                         mat=M.graphite("#3a3c40", 0.4), fillet=0.006)
                            p.add(b)
                            b["hl"], b["hl_col"] = 0.0, acc
            for name, e in p.anchors.items():
                self.anchor_objs[f"{spec['id']}.{name}"] = e
        bpy.context.view_layer.update()
        for pid, p in self.parts.items():          # the real extent of each part (builders exceed DIMS a little)
            pts = [m.matrix_world @ Vector(c) for m in p.meshes for c in m.bound_box]
            if pts:
                lo = Vector([min(q[i] for q in pts) for i in range(3)])
                hi = Vector([max(q[i] for q in pts) for i in range(3)])
                self.boxes[pid] = ((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z, hi.x - lo.x, hi.y - lo.y, hi.z - lo.z)
        for pid, p in self.parts.items():
            self._part_motion(pid, p)
            self._drivers(pid, p)
            self._thermal(pid, p)
            self._highlight(pid, p.meshes)
        self._highlight("machine", self.host.meshes)
        self._status_lamps()
        self._connections()
        self._effects()
        self._finale_comet()

    def _evs(self, target, *kinds):
        return [e for e in self.events if str(e.get("target", "")).split(".")[0] == target and e["do"] in kinds]

    def _host_motion(self):
        ev = next(iter(self._evs("machine", "appear")), None)
        shakes = [self.t_of(e["word"]) for e in self._evs("machine", "shake")]
        root = self.host.root
        objs = [root, *root.children_recursive]
        t_in = self.t_of(ev["word"]) - 0.2 if ev else None

        def pose(t):
            s, hidden = 1.0, False
            if t_in is not None:
                u = (t - t_in) / 0.6
                hidden = u <= 0
                s = back_out(u, 1.3) if u < 1 else 1.0
            root.scale = (s, s, max(1e-3, s))
            root.location = (0, 0, 0)
            for ts in shakes:
                u = t - ts
                if 0 <= u < 0.5:
                    a = 0.01 * math.exp(-6 * u)
                    root.location = (a * math.sin(u * 90), 0, 0)
            for o in objs:
                o.hide_render = hidden
        self.poses.append(pose)

    # entrances (attach into a slot, fly out of a prop, drop / slide / pop), exits, shakes
    def _part_motion(self, pid, p):
        appear = next(iter(self._evs(pid, "appear")), None)
        remove = next(iter(self._evs(pid, "remove")), None)
        flies_out = next((e for e in self.events if e["do"] == "appear" and e.get("from") == pid), None)
        shakes = [self.t_of(e["word"]) for e in self._evs(pid, "shake")]
        base, rot = p.base.copy(), p.rot
        objs = [p.root, *p.root.children_recursive]
        pl = self.place[pid]
        mounted = bool(pl.get("slot"))
        t_in = self.t_of(appear["word"]) if appear else None
        how_in = (appear or {}).get("how") or ("attach" if mounted else "drop")
        if mounted and how_in not in ("pop", "grow"):
            how_in = "attach"
        src = (appear or {}).get("from")
        start, s0 = None, 1.0
        if src and src in self.place:                        # out of the prop, into the slot
            sp = self.place[src]
            start = Vector((sp["x"], sp["y"], sp["z"] + sp["h"] * 0.3))
            s0 = max(0.35, min(1.4, sp["h"] / max(0.05, pl["h"])))
        elif how_in == "attach":                             # from outside the face the slot is on
            out = Vector((math.sin(rot), -math.cos(rot), 0.0))
            start = base + out * (0.7 + 0.5 * pl["d"]) + Vector((0, 0, 0.55))
            s0 = 0.75
        t_out = self.t_of(remove["word"]) if remove else (self.t_of(flies_out["word"]) + 0.05 if flies_out else None)
        how_out = (remove or {}).get("how") or "shrink"
        if flies_out and not remove:
            how_out = "shrink"
        size = max(pl["w"], pl["d"], pl["h"])
        p.t_landed = None
        wins = [] if mounted else self._prop_windows(pid)

        def pose(t):
            loc, scale, hidden, spin = base.copy(), 1.0, False, 0.0
            sq = 1.0
            if t_in is not None:
                if how_in == "attach" or start is not None:
                    fly = 1.0 if src else 0.85             # a flight the eye can follow, with weight
                    t_land = t_in + 0.2
                    u = (t - (t_land - fly)) / fly
                    hidden = u < 0
                    if u < 1:
                        e = ease_out(u)
                        loc = start.lerp(base, e) + Vector((0, 0, (0.4 if src else 0.25) * math.sin(math.pi * e)))
                        scale = s0 + (1 - s0) * e
                        spin = (1 - e) * (0.6 if src else 0.35)
                    else:
                        v = t - t_land                       # the click: a small squash and settle
                        if v < 0.35:
                            sq = 1 - 0.07 * math.exp(-9 * v) * math.cos(v * 38)
                elif how_in == "drop":
                    u = (t - (t_in - 0.3)) / 0.55
                    hidden = u < 0
                    loc.z += (0.9 + size) * (1 - ease_out(u)) if u < 1 else 0.0
                    if 0 <= u - 1 < 0.6:
                        sq = 1 - 0.06 * math.exp(-8 * (u - 1)) * math.cos((u - 1) * 30)
                elif how_in == "slide":
                    u = (t - (t_in - 0.55)) / 0.55
                    hidden = u < 0
                    loc.x += -1.6 * (1 - back_out(u, 1.2)) * (1 if base.x <= 0 else -1)
                else:                                        # pop / grow
                    dur = 0.5 if how_in == "grow" else 0.32
                    u = (t - t_in) / dur
                    hidden = u <= 0
                    scale = max(0.0, back_out(u, 1.8)) if u < 1 else 1.0
            if t_out is not None and t >= t_out:
                u = (t - t_out) / (0.6 if how_out in ("fly_up", "fly_away") else 0.3)
                if how_out == "fly_up":
                    loc.z += 3.0 * u * u
                elif how_out == "fly_away":
                    loc.x += 4.0 * u * u * (1 if base.x >= 0 else -1)
                    loc.z += 0.6 * u
                else:
                    scale *= max(0.0, 1 - smooth(u))
                hidden = hidden or u >= 1
            for ts in shakes:
                u = t - ts
                if 0 <= u < 0.45:
                    a = 0.012 * size * math.exp(-6 * u)
                    loc.x += a * math.sin(u * 95)
                    loc.y += a * 0.5 * math.cos(u * 77)
            if wins:                                         # a prop is only there in its own shots
                g = max(clamp01((t - a + 0.3) / 0.3) * clamp01((b - t) / 0.3) for a, b in wins)
                scale *= smooth(g)
                hidden = hidden or g <= 0.001
            p.root.location = loc
            p.root.rotation_euler.z = rot + spin
            p.root.scale = (scale / math.sqrt(sq), scale / math.sqrt(sq), scale * sq)
            for o in objs:
                o.hide_render = hidden
        self.poses.append(pose)
        if t_in is not None and mounted:
            p.t_landed = t_in + 0.2

    def _stopped(self):
        """(t0, t1) windows in which the storyboard has switched the machine's motor OFF (a run stop until the next
        run): nothing circulates then, whatever the flow events say."""
        movers = [q for q, sp in self.specs.items() if sp["type"] in ("compressor", "motor", "pump", "fan")
                  and self.mounted(q)]
        segs = sorted((self.t_of(e["word"]), not (e.get("speed") == "stop" or e.get("on") is False))
                      for q in movers for e in self._evs(q, "run"))
        out, t_off = [], None
        for ts, on in segs:
            if not on and t_off is None:
                t_off = ts
            elif on and t_off is not None:
                out.append((t_off, ts))
                t_off = None
        if t_off is not None:
            out.append((t_off, self.duration + 1))
        return out

    def _temperature_bar(self, p):
        """The thermostat's thermometer: warm (full) until the machine first runs, falling while the motor runs,
        rising while it is off -- so 'cold enough: click off ... warmer: click on' is SEEN."""
        movers = [q for q, sp in self.specs.items() if sp["type"] in ("compressor", "motor", "pump", "fan")
                  and self.mounted(q)]
        runs = sorted(self.t_of(e["word"]) for q in movers for e in self._evs(q, "run")
                      if not (e.get("speed") == "stop" or e.get("on") is False))
        t_run = runs[0] if runs else None
        stopped = self._stopped()
        step, hi, lo = 1 / 30, 0.92, 0.22
        n = int(self.duration / step) + 60
        lev, table = hi, []
        for i in range(n):
            t = i * step
            off = t_run is None or t < t_run or any(a <= t < b for a, b in stopped)
            target, rate = (hi, 0.22) if off else (lo, 0.3)
            lev += (target - lev) * min(1.0, rate * step * 3)
            table.append(lev)
        fluid, cold = p.temp_fluid, p.temp_cold_col

        def pose(t):
            v = table[max(0, min(len(table) - 1, int(t / step)))]
            fluid.scale.z = max(0.02, v)
            fluid["heat"] = 0.0
            fluid["frost"] = clamp01((0.6 - v) / 0.4) * 0.6     # the fluid cools to blue as the fridge gets cold
        self.poses.append(pose)

    def _status_lamps(self):
        """A thermostat's lamp shows the machine's state: green while the compressor (or the motor) runs, dark
        while it is switched off, so 'click, off ... click, on' is seen, not just heard."""
        movers = [q for q, sp in self.specs.items() if sp["type"] in ("compressor", "motor", "pump", "fan")
                  and self.mounted(q)]
        segs = sorted((self.t_of(e["word"]), not (e.get("speed") == "stop" or e.get("on") is False))
                      for q in movers for e in self._evs(q, "run"))
        for pid, p in self.parts.items():
            if not hasattr(p, "lamp_on"):
                continue
            if hasattr(p, "temp_fluid"):
                self._temperature_bar(p)
            for a, b in self._stopped():              # the click: a spark at the dial as it switches off / on
                for tc in (a, b):
                    if tc < self.duration:
                        self._flash({"target": f"{pid}.center"}, tc, small=True)

            def pose(t, p=p):
                on = False
                for ts, v in segs:
                    if ts <= t:
                        on = v
                p.lamp_on.hide_render = not on
                p.lamp_off.hide_render = on or p.root.hide_render
                if not on:
                    return
                p.lamp_on.hide_render = p.root.hide_render
            self.poses.append(pose)

    def _shot_times(self):
        shots = self.sb["shots"]
        return [(max(0.0, self.t_of(s["start_word"]) - 0.12) if i else 0.0,
                 (self.t_of(shots[i + 1]["start_word"]) - 0.12) if i + 1 < len(shots) else self.duration, s)
                for i, s in enumerate(shots)]

    def _prop_windows(self, pid):
        """When a prop may be seen: the shots about it (and the moment a part flies out of it), merged."""
        ws = [(a, b) for a, b, s in self._shot_times() if pid in (s.get("on") or [])]
        for e in self.events:
            if e["do"] == "appear" and e.get("from") == pid:
                ws.append((self.t_of(e["word"]) - 0.9, self.t_of(e["word"]) + 0.6))
        ws.sort()
        out = []
        for a, b in ws:
            if out and a <= out[-1][1] + 0.05:
                out[-1] = (out[-1][0], max(out[-1][1], b))
            else:
                out.append((a, b))
        return out

    def _highlight(self, pid, meshes):
        """Edge glow: a pulse as a part clicks in, and on while a highlight event says so."""
        wins = []
        p = self.parts.get(pid)
        if p is not None and getattr(p, "t_landed", None) is not None:
            wins.append((p.t_landed, p.t_landed + 1.3))
        evs = self._evs(pid, "highlight")
        for i, e in enumerate(evs):
            if e.get("on") is False:
                continue
            t0 = self.t_of(e["word"])
            off = next((self.t_of(x["word"]) for x in evs[i + 1:] if x.get("on") is False), t0 + 2.6)
            wins.append((t0, max(t0 + 0.8, off)))
        if not wins:
            return

        def pose(t):
            v = 0.0
            for a, b in wins:
                if a - 0.2 <= t <= b + 0.3:
                    env = clamp01((t - a + 0.2) / 0.2) * clamp01((b + 0.3 - t) / 0.3)
                    v = max(v, env * (0.7 + 0.3 * math.sin((t - a) * 7.0)))
            for m in meshes:
                m["hl"] = v
        self.poses.append(pose)

    # drivers: run (continuous) / set (go to a value) / stop
    def _drivers(self, pid, p):
        if not p.drivers:
            return
        evs = self._evs(pid, "run", "set")
        if not evs:
            for name, fn in p.drivers.items():
                fn(0.0)
            return
        name = next((e.get("driver") for e in evs if e.get("driver") in p.drivers), None) or next(iter(p.drivers))
        angular = name in ("spin", "crank", "pump", "turn")
        segs, sets = [], []
        for e in evs:
            t = self.t_of(e["word"])
            if e["do"] == "run":
                sp = 0.0 if e.get("speed") == "stop" or e.get("on") is False else SPEEDS.get(e.get("speed") or "normal", 1.0)
                segs.append((t, sp))
            else:
                sets.append((t, float(e.get("value", 1.0) if e.get("value") is not None else 1.0)))

        def speed_at(t):
            v, prev_t, prev_v = 0.0, 0.0, 0.0
            for ts, sp in segs:
                if t < ts:
                    break
                prev_t, prev_v, v = ts, v, sp
            u = clamp01((t - prev_t) / 0.5)
            return prev_v + (v - prev_v) * smooth(u)

        step = 1 / 120
        n = int(self.duration / step) + 240
        table = [0.0] * (n + 1)
        for i in range(n):
            table[i + 1] = table[i] + speed_at(i * step) * step

        def phase(t):
            x = max(0.0, t) / step
            i = min(int(x), n - 1)
            return table[i] + (table[i + 1] - table[i]) * (x - i)

        def value_at(t):
            v = 0.0
            for i, (ts, val) in enumerate(sets):
                if t >= ts:
                    prev = sets[i - 1][1] if i else 0.0
                    v = prev + (val - prev) * smooth((t - ts) / 0.6)
            return v

        def pose(t):
            if angular:
                p.drive(name, TAU * phase(t) + (TAU * value_at(t) if sets else 0.0))
            else:
                osc = phase(t)
                v = (0.5 - 0.5 * math.cos(TAU * osc)) if segs and speed_at(t) > 0.01 else 0.0
                p.drive(name, max(v, value_at(t)) if sets else v)
        self.poses.append(pose)
        p.phase = phase

    def _thermal(self, pid, p):
        for kind in ("heat", "frost"):
            evs = [(self.t_of(e["word"]), float(e.get("value") if e.get("value") is not None else 1.0))
                   for e in self._evs(pid, kind)]
            if not evs:
                continue
            # a warm glow (a pipe coil may glow more than a solid body, which turns muddy maroon); frost is a
            # real white rime coat
            cap = (0.4 if getattr(p, "flow_path", None) else 0.1) if kind == "heat" else 0.9

            def pose(t, evs=[(ts, min(val, cap)) for ts, val in evs], kind=kind):
                v = 0.0
                for i, (ts, val) in enumerate(evs):
                    if t >= ts:
                        prev = evs[i - 1][1] if i else 0.0
                        v = prev + (val - prev) * smooth((t - ts) / 0.9)
                for m in p.meshes:
                    m[kind] = v
            self.poses.append(pose)

    # ------------------------------------------------------------ connections
    def _end(self, ref):
        pid, _, name = ref.partition(".")
        p = self.parts[pid]
        if name in p.ports:
            e, d = p.ports[name]
        else:
            free = [k for k in p.ports if k not in getattr(p, "_used_ports", set())]
            if free and not name:
                e, d = p.ports[free[0]]
                name = free[0]
            else:
                e, d = p.anchors.get(name or "center") or p.anchors["center"], Vector((0, 0, 1))
        p._used_ports = getattr(p, "_used_ports", set()) | {name}
        return e.matrix_world.translation.copy(), (p.root.matrix_world.to_3x3() @ d).normalized()

    def _connections(self):
        self.conn_objs = {}
        self.conn_pts = {}
        W, D, _H = self.hdims
        bpy.context.view_layer.update()
        for c in self.sb.get("connections", []):
            pa, pb = c["from"].split(".")[0], c["to"].split(".")[0]
            if pa not in self.parts or pb not in self.parts:
                continue
            a, da = self._end(c["from"])
            b, db = self._end(c["to"])
            slots = [str(self.place[x].get("slot") or "") for x in (pa, pb)]
            plane = D / 2 + 0.06 if any(s.startswith(("back", "inside")) for s in slots) else None
            x_run = None
            if plane is not None:                   # never straight through another part on the back
                a1 = a + Vector(da).normalized() * 0.05
                b1 = b + Vector(db).normalized() * 0.05
                z0, z1 = sorted((a1.z, b1.z))
                hits = []
                for q, box in self.boxes.items():
                    if q in (pa, pb) or not str(self.place.get(q, {}).get("slot") or "").startswith("back"):
                        continue
                    x, _y, z, w, _d, h = box
                    if x - w / 2 - 0.04 < a1.x < x + w / 2 + 0.04 and z < z1 and z + h > z0:
                        hits.append((x - w / 2 - 0.07, x + w / 2 + 0.07))
                if hits:
                    left, right = min(h_[0] for h_ in hits), max(h_[1] for h_ in hits)
                    cands = [v for v in (left, right) if abs(v) <= W / 2 - 0.03] or [W / 2 - 0.05]
                    x_run = min(cands, key=lambda v: abs(v - a1.x))
            pts = flowpipe.route(a, da, b, db, plane_y=plane, lead=0.05, radius=0.06, x_run=x_run)
            kind = c["kind"]
            if kind == "belt":
                mat, r = M.rubber("#1e1e20"), 0.012
            else:
                mat = {"pipe": M.flow_pipe("#c77a4e"), "hose": M.flow_pipe("#2c2d31", 0.0, 0.55),
                       "wire": M.flow_pipe("#b8141c", 0.0, 0.35)}[kind]
                r = {"pipe": 0.021, "hose": 0.021, "wire": 0.008}[kind]     # thick enough to read in a wide shot
            obj = flowpipe.tube(f"conn_{c['id']}", pts, r, mat)
            obj.visible_shadow = kind != "wire"
            collars = [] if kind != "pipe" else [
                flowpipe.collar(f"collar_{c['id']}_{i}", at, d, r, M.brass()) for i, (at, d) in enumerate(((a, da), (b, db)))]
            self.conn_objs[c["id"]] = obj
            self.conn_pts[c["id"]] = [Vector(q) for q in pts]
            ev = next((e for e in self.events if e.get("target") == c["id"] and e["do"] == "appear"), None)
            t_on = self.t_of(ev["word"]) if ev else max(self.spans[pa][0], self.spans[pb][0]) + 1.25
            t_off = min(self.spans[pa][1], self.spans[pb][1])
            c["_t_on"] = t_on

            def pose(t, objs=[obj, *collars], t_on=t_on, t_off=t_off):
                for o in objs:
                    o.hide_render = not (t_on <= t < t_off)
            self.poses.append(pose)

    # ------------------------------------------------------------ effects
    def _effects(self):
        st = self.studio
        streams = {}
        for e in self.events:
            if e["do"] == "flow":
                streams.setdefault(str(e["target"]), []).append(e)
        for target, evs in streams.items():
            self._flow(target, evs)
        for e in self.events:
            do = e["do"]
            t = self.t_of(e["word"])
            if do == "fill":
                self._fill(e, t)
            elif do in ("flash", "spark"):
                self._flash(e, t, small=do == "spark")
            elif do == "rings":
                self._rings(e, t)
            elif do == "smoke":
                self._smoke(e, t)
            elif do == "wash":
                self._wash(e, t, st["wash"])
        heat = {}
        for e in self.events:
            if e["do"] == "heat_flow":
                heat.setdefault((str(e["target"]), str(e.get("to") or "room")), []).append(e)
        for (src, dst), evs in heat.items():
            self._heat_flow(src, dst, evs)

    def _gas(self, name, pts, style, level, root=None, k=1.0):
        """Real gas along a path: soft volumetric puffs that leave the start, grow, drift along the path and thin
        away, churning inside (materials.gas). level(t) 0..1 turns it on and off; it hides with `root`."""
        col, glow, gs, dens, travel, n, r0, r1 = GAS[style]
        pts = [Vector(q) for q in pts]
        acc = [0.0]
        for a_, b_ in zip(pts, pts[1:]):
            acc.append(acc[-1] + (b_ - a_).length)
        total = max(acc[-1], 1e-6)

        def at(u):
            s_ = u * total
            for j in range(1, len(acc)):
                if acc[j] >= s_:
                    v = (s_ - acc[j - 1]) / max(1e-9, acc[j] - acc[j - 1])
                    return pts[j - 1].lerp(pts[j], v)
            return pts[-1]
        mat = M.gas(col, glow, gs, dens)
        puffs = []
        for i in range(n):
            bm = bmesh.new()
            bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
            me = bpy.data.meshes.new(f"{name}_{i}")
            bm.to_mesh(me)
            bm.free()
            me.materials.append(mat)
            o = bpy.data.objects.new(f"{name}_{i}", me)
            bpy.context.scene.collection.objects.link(o)
            o["gas_fade"], o["gas_t"], o["no_occlude"] = 0.0, 0.0, 1
            o.visible_shadow = False
            puffs.append(o)

        def pose(t):
            v = level(t)
            if root is not None and (root.hide_render or root.scale.z < 0.2):
                v = 0.0
            for i, o in enumerate(puffs):
                u = ((t / travel) + i / n) % 1.0
                f = v * math.sin(math.pi * u) ** 0.8
                o.hide_render = f < 0.01
                if o.hide_render:
                    continue
                r = (r0 + (r1 - r0) * u) * k
                o.location = at(u)
                o.scale = (r, r, r * 1.15)
                o["gas_fade"] = f
                o["gas_t"] = t * 0.7 + i * 1.37
        self.poses.append(pose)

    def _finale_comet(self):
        """The finale: a bright comet runs the whole loop in flow order -- through each part, along each pipe,
        back to the start -- during the last whole-machine shot, so the closed loop is SEEN working."""
        from buildit.blender.kit import _sphere
        from buildit.kit.check import loop_order
        parts = {p["id"]: p for p in self.sb["parts"]}
        order = loop_order(self.sb, parts)
        shots = [x for x in self._shot_times() if x[2].get("frame") == "machine"]
        if len(order) < 3 or not shots:
            return
        ta, tb, _s = shots[-1]
        if tb - ta < 2.5:
            return
        bpy.context.view_layer.update()
        conns = {(c["from"].split(".")[0], c["to"].split(".")[0]): c["id"] for c in self.sb.get("connections", [])}
        path = []
        for i, q in enumerate(order):
            p = self.parts.get(q)
            if p is None:
                return
            mw = p.root.matrix_world
            if getattr(p, "flow_path", None):
                path += [mw @ Vector(v) for v in p.flow_path]
            elif "in" in p.ports and "out" in p.ports:
                path += [p.ports["in"][0].matrix_world.translation.copy(), p.anchors["center"].matrix_world.translation.copy(),
                         p.ports["out"][0].matrix_world.translation.copy()]
            cid = conns.get((q, order[(i + 1) % len(order)]))
            if cid in self.conn_pts:
                path += self.conn_pts[cid]
        if len(path) < 4:
            return
        acc = [0.0]
        for a_, b_ in zip(path, path[1:]):
            acc.append(acc[-1] + (b_ - a_).length)
        total = acc[-1]

        def at(s_):
            s_ = s_ % total
            for k in range(1, len(acc)):
                if acc[k] >= s_:
                    u = (s_ - acc[k - 1]) / max(1e-9, acc[k] - acc[k - 1])
                    return path[k - 1].lerp(path[k], u)
            return path[-1]
        balls = []
        for j in range(6):                            # the head and a fading tail
            r = 0.05 * (1 - j * 0.13)
            b = _sphere(f"comet_{j}", r, M.glow("#fff2b0", 40.0 * (1 - j * 0.15)), segs=16)
            b["glow"] = 1.0
            b["no_occlude"] = 1
            b.visible_shadow = False
            balls.append(b)
        t0_, t1_ = ta + 0.5, tb - 0.3
        laps = max(1, round((t1_ - t0_) / 4.0))         # about 4 s a lap: slow enough to follow

        def pose(t):
            live = t0_ <= t <= t1_
            u = (t - t0_) / max(1e-6, t1_ - t0_)
            for j, b in enumerate(balls):
                b.hide_render = not live
                if live:
                    b.location = at(u * laps * total - j * 0.045)
        self.poses.append(pose)

    def _phase_change(self, pid, p, path, out_kind, level):
        """The state change made visible INSIDE the coil, along its outlet half: bubbles rising through a cold
        coil (the liquid boiling into gas), droplets beading along a hot one (the gas condensing into liquid)."""
        bpy.context.view_layer.update()
        mw = p.root.matrix_world
        half = path[len(path) // 2:]
        pts = [tuple(mw @ Vector(q)) for q in half[:: max(1, len(half) // 10)]]
        if len(pts) < 2:
            return
        boil = out_kind in ("cold_gas", "steam", "air")
        ramp = ((0, "#ffffff"), (1, "#cdeeff")) if boil else ((0, "#ffc27a"), (1, "#ff8a1a"))
        fl = effects.Flow(f"phase_{pid}", pts, count=180, spread=0.012 * p.k, size=0.0042 * p.k, stretch=1.0,
                          closed=False, ramp=ramp, strength=4.0 if boil else 3.0, gated=True)
        fl.obj["no_occlude"] = 1
        fl.obj.visible_shadow = False
        root = p.root

        def pose(t, fl=fl):
            v = level(t)
            for a_, b_ in self._stopped():               # nothing boils while the motor is off
                if a_ <= t <= b_:
                    v = 0.0
            if root.hide_render:
                v = 0.0
            fl.obj["flow_on"] = v
            fl.obj.hide_render = v <= 0.001
            fl.set_phase(t * (0.35 if boil else 0.18))
        self.poses.append(pose)

    def _heat_flow(self, src, dst, evs):
        """Heat MOVING: warm glowing waves drift from where the heat is (the food, a hot part) to where it goes
        (the cold coil, the room), so the viewer sees what the machine pumps where. Waves without an 'off'
        fade after HEAT_HOLD seconds, so they never clutter the shots that follow."""
        wins = []
        for i, e in enumerate(evs):
            if e.get("on") is False:
                continue
            t0 = self.t_of(e["word"])
            off = next((self.t_of(x["word"]) for x in evs[i + 1:] if x.get("on") is False), None)
            wins.append((t0, min(off if off is not None else 1e9, t0 + HEAT_HOLD)))

        def level(t):
            return max([clamp01((t - a) / 0.4) * clamp01((b - t) / 0.5) for a, b in wins] + [0.0])
        bpy.context.view_layer.update()
        a = self._anchor_point(src if "." in src or src not in self.parts else src + ".center")
        if a is None:
            return
        a = Vector(a)
        if dst == "room":
            out = Vector((a.x, a.y, 0.0))
            out = out.normalized() if out.length > 1e-6 else Vector((0, 1, 0))
            if src.split(".")[0] in self.parts and not self.mounted(src.split(".")[0]):
                b = a + out * 0.12 + Vector((0, 0, 0.6))          # off a prop the heat rises (a mug, a pump)
            else:
                b = a + out * 0.75 + Vector((0, 0, 0.55))
        else:
            b = self._anchor_point(dst if "." in dst else dst + ".center")
            if b is None:
                return
            b = Vector(b)
        mid = (a + b) / 2 + Vector((0, 0, 0.12 + 0.15 * (a - b).length))
        pts = [tuple((1 - u) ** 2 * a + 2 * (1 - u) * u * mid + u * u * b) for u in (0, 0.2, 0.4, 0.6, 0.8, 1.0)]
        small = src.split(".")[0] in self.parts and not self.mounted(src.split(".")[0])   # off a prop: filmed close
        root = self.parts[src.split(".")[0]].root if small else None
        self._gas(f"heat_{len(self.poses)}", pts, "heat", level, root=root, k=0.55 if small else 1.0)

    def _anchor_point(self, ref):
        pid, _, name = str(ref).partition(".")
        bpy.context.view_layer.update()
        if pid == "machine":
            e = self.host.anchors.get(name or "center") or self.host.anchors["center"]
            return e.matrix_world.translation.copy()
        p = self.parts.get(pid)
        if p is None:
            return Vector((0, 0, 0.5))
        e = p.anchors.get(name or "center") or p.anchors["center"]
        return e.matrix_world.translation.copy()

    def _switch(self, evs):
        switches = [(self.t_of(x["word"]), x.get("on", True) is not False) for x in evs]

        def level(t):
            past = [(ts, on) for ts, on in switches if ts <= t]
            if not past:
                return 0.0
            ts, cur = past[-1]
            was = past[-2][1] if len(past) > 1 else False
            u = clamp01((t - ts) / 0.3)
            return (1.0 if cur else 0.0) * u + (1.0 if was else 0.0) * (1 - u)
        return level

    def _flow(self, target, evs):
        """What flows where: a connection or a coil lights up with moving dashes in the flow's colour; a port
        breathes out a jet of particles."""
        e = evs[0]
        kind = e.get("kind") or "air"
        col = _rgb(FLOW_COLORS.get(kind, "#ffffff"))
        speed = FLOW_SPEED.get(e.get("speed") or "normal", 0.3)
        level = self._switch(evs)
        pid, _, port = target.partition(".")
        objs = []
        if target in self.conn_objs:
            objs = [self.conn_objs[target]]
        elif pid in self.parts and getattr(self.parts[pid], "flow_path", None) and not port:
            p = self.parts[pid]
            path = [Vector(q) for q in p.flow_path]
            r_ = getattr(p, "flow_r", 0.0175 * p.k)
            fpath = flowpipe.fillet(path, min(0.02, r_ * 0.6))
            sleeve = flowpipe.tube(f"sleeve_{pid}", fpath, r_, M.flow_pipe("#c77a4e"))
            fp_ = [Vector(q) for q in fpath]
            sleeve["flow_len"] = sum((b_ - a_).length for a_, b_ in zip(fp_, fp_[1:])) * p.k
            out_kind = next((x.get("kind_out") for x in evs if x.get("kind_out")), None)
            sleeve["flow_grad"] = 1.0 if out_kind else 0.0
            sleeve["flow_col2"] = _rgb(FLOW_COLORS.get(out_kind or kind, "#ffffff"))
            sleeve.parent = p.root
            objs = [sleeve]
            # the sleeve shows and hides with its part
            def vis(t, s=sleeve, r=p.root):
                s.hide_render = r.hide_render
            self.poses.append(vis)
            # (the state change shows as the dashes' colour shift along the coil; no dots inside the pipe)
        if objs:
            if e.get("reverse"):
                speed = -speed
            # a kind change on a later event recolours the same pipe (gas turns to liquid)
            kinds = [(self.t_of(x["word"]), _rgb(FLOW_COLORS.get(x.get("kind") or kind, "#ffffff"))) for x in evs]

            stopped = self._stopped()

            def pose(t, objs=objs):
                v = level(t)
                for a, b in stopped:                  # the motor is off: the flows fade to a halt
                    if a <= t <= b + 0.5:
                        v *= 1 - clamp01((t - a) / 0.6) * clamp01((b + 0.5 - t) / 0.5)
                c = col
                for ts, cc in kinds:
                    if ts <= t:
                        c = cc
                for o in objs:
                    o["flow_on"] = v
                    o["flow_phase"] = t * speed
                    o["flow_col"] = c
            self.poses.append(pose)
            return
        # a jet out of a port / anchor
        if pid not in self.parts:
            return
        ramp, strength, size, stretch = JET_LOOK.get(kind, JET_LOOK["air"])
        p = self.parts[pid]
        bpy.context.view_layer.update()
        if port in p.ports:
            pe, d = p.ports[port]
        else:
            pe, d = (p.anchors.get(port or "center") or p.anchors["center"]), Vector((0, -1, 0.3))
        a = pe.matrix_world.translation.copy()
        d = (p.root.matrix_world.to_3x3() @ d).normalized()
        pts = [tuple(a + d * (0.55 * u) + Vector((0, 0, 0.05 * u * u))) for u in (0, 0.2, 0.45, 0.7, 1.0)]
        style = "steam" if kind in ("steam", "hot_gas", "exhaust", "hot_liquid") else "cold"
        self._gas(f"jet_{len(self.poses)}", pts, style, level, root=p.root, k=0.8 if not self.mounted(pid) else 1.0)

    def _fill(self, e, t0):
        pid = str(e["target"]).split(".")[0]
        p = self.parts[pid]
        it = p.interior or {"kind": "cyl", "r": 0.1, "z0": 0.05, "z1": 0.3}
        kind = e.get("kind", "air")
        ramp, strength, size, _st = JET_LOOK.get(kind, JET_LOOK["air"])
        if getattr(p, "cloud", None) is None:
            z0 = 0.0 if it["z0"] == "piston" else it["z0"]
            r = it.get("r") or min(it["half"]) * 0.9
            cl = effects.Cloud(f"fill_{pid}", r * 0.95, z0 + 0.01, it["z1"], count=650,
                               size=size * 1.2, color=FLOW_COLORS.get(kind, ramp[-1][1]), strength=strength,
                               drift=0.015)
            cl.obj.parent = p.root
            if it.get("kind") == "box":
                hx, hy = it["half"]
                cl.obj.scale = (hx / r, hy / r, 1.0)
            p.cloud = cl
            p.fills = []
        p.fills.append((t0, float(e.get("value") if e.get("value") is not None else 1.0),
                        float(e.get("squeeze") or 0.0)))
        if len(p.fills) > 1:
            return
        cl = p.cloud

        def pose(t, p=p, cl=cl, it=it):
            level, sq = 0.0, 0.0
            for i, (ts, val, s) in enumerate(p.fills):
                if t >= ts:
                    prev = p.fills[i - 1][1] if i else 0.0
                    psq = p.fills[i - 1][2] if i else 0.0
                    u = smooth((t - ts) / 0.9)
                    level = prev + (val - prev) * u
                    sq = psq + (s - psq) * u
            if it["z0"] == "piston":
                bottom = p.piston_top() + 0.005
                cl.obj.location.z = bottom
                cl.set(fill=level, time=t * 0.5, top=max(0.02, it["z1"] - bottom))
            else:
                cl.set(fill=level, time=t * 0.5, top=it["z1"] - (it["z1"] - it["z0"]) * 0.75 * sq)
            cl.obj.hide_render = p.root.hide_render or level <= 0.001
        self.poses.append(pose)

    def _flash(self, e, t0, small=False):
        loc = self._anchor_point(e["target"])
        r = 0.035 if small else 0.09
        color = "#cfe6ff" if small else "#ffd9a0"
        ball, light = effects.flash(f"flash_{len(self.poses)}", loc, radius=r, color=color)
        dur = 0.18 if small else 0.55
        peak = 60.0 if small else 260.0

        def pose(t):
            u = t - t0
            g = 0.0 if u < 0 or u > dur else (min(1.0, u / 0.05) * math.exp(-5.5 * u / dur))
            ball["glow"] = g
            ball.hide_render = g <= 0.002
            ball.scale = (1 + 0.8 * clamp01(u / dur),) * 3
            light.data.energy = peak * g
        self.poses.append(pose)

    def _rings(self, e, t0):
        from cutaway.blender import geo
        loc = self._anchor_point(e["target"])
        rings = []
        for i in range(3):
            o = geo.lathe(f"ring_{len(self.poses)}_{i}",
                          [(0.1 + 0.006 * math.cos(math.radians(a)), 0.006 * math.sin(math.radians(a)))
                           for a in range(0, 361, 30)], 48, mat=M.glow(self.accent, 3.0))
            o.rotation_euler.x = math.radians(90)
            o.location = loc
            o["glow"] = 0.0
            o.visible_shadow = False
            rings.append(o)

        def pose(t):
            for i, o in enumerate(rings):
                u = (t - t0 - 0.3 * i) / 1.2
                live = 0 <= u <= 1
                o.hide_render = not live
                s = 0.3 + 2.4 * clamp01(u)
                o.scale = (s, s, s)
                o["glow"] = (1 - clamp01(u)) * 0.8 if live else 0.0
        self.poses.append(pose)

    def _smoke(self, e, t0):
        """A wisp of vapour rising off an anchor for a few seconds (water drying off, a breath, steam): fine pale
        streaks drifting up and spreading, never blocks."""
        a = Vector(self._anchor_point(e["target"]))
        pts = [tuple(a + Vector((0.03 * math.sin(u * 5), 0.02 * math.cos(u * 4), 0.55 * u))) for u in
               (0, 0.2, 0.4, 0.6, 0.8, 1.0)]
        self._gas(f"vapour_{len(self.poses)}", pts, "vapour",
                  lambda t: clamp01((t - t0) / 0.4) * clamp01((t0 + 3.0 - t) / 0.8))

    def _wash(self, e, t0, light):
        warm = (e.get("kind") or e.get("how") or "warm") != "cold"
        level = float(e.get("value") if e.get("value") is not None else 1.0)
        prev = getattr(self, "_wash_keys", [])
        prev.append((t0, level, warm))
        self._wash_keys = prev
        if len(prev) > 1:
            return

        def pose(t):
            v, w = 0.0, True
            for i, (ts, val, wm) in enumerate(self._wash_keys):
                if t >= ts:
                    pv = self._wash_keys[i - 1][1] if i else 0.0
                    v = pv + (val - pv) * smooth((t - ts) / 1.0)
                    w = wm
            light.hide_render = v < 0.01
            light.data.energy = 1800.0 * v
            light.data.temperature = 2700 if w else 12000
        self.poses.append(pose)

    # ------------------------------------------------------------ camera
    def _box_pts(self, box):
        x, y, z, w, d, h = box
        return [Vector((x + sx * w / 2, y + sy * d / 2, z + sz * h)) for sx in (-1, 1) for sy in (-1, 1)
                for sz in (0, 1)]

    def _visible(self, pid, t0, t1):
        a, b = self.spans.get(pid, (0, self.duration))
        return a < t1 and b > t0

    def _subject(self, s, t0, t1):
        """(points to frame, facing in degrees) of a shot."""
        frame = s.get("frame", "area")
        on = [pid for pid in s.get("on", []) if pid in self.place and self._visible(pid, t0, t1)]
        pts, ids = [], []
        machine_on = self.spans["machine"][0] < t1
        if frame == "machine":
            if machine_on:
                pts += self._box_pts(hosts.machine_box(self.sb))
            ids = [pid for pid in self.place if self.mounted(pid) and self._visible(pid, t0, t1)]
            ids += [pid for pid in on if not self.mounted(pid)]       # props only when the shot is about them
        elif frame == "area":
            ids = list(on)

            def near(x, y):                      # a neighbour joins only if it is close (an area, not the machine)
                bx, by = self.boxes.get(x), self.boxes.get(y)
                if not bx or not by:
                    return False
                cx = Vector((bx[0], bx[1], bx[2] + bx[5] / 2))
                cy = Vector((by[0], by[1], by[2] + by[5] / 2))
                return (cx - cy).length <= AREA_REACH
            for c in self.sb.get("connections", []):
                a, b = c["from"].split(".")[0], c["to"].split(".")[0]
                for x, y in ((a, b), (b, a)):
                    if x in on and y not in ids and y in self.place and self._visible(y, t0, t1) and near(x, y):
                        ids.append(y)
            ids = ids[:3]
        else:
            ids = on[:1]
        if not ids and not pts:
            if machine_on:
                pts = self._box_pts(hosts.machine_box(self.sb))
            else:
                ids = [pid for pid in self.place if self._visible(pid, t0, t1)][:1]
        if not ids and not pts:                        # nothing on screen yet: frame what arrives first
            first = min(self.place, key=lambda q: self.spans.get(q, (0, 0))[0], default=None)
            if first is not None and self.spans.get(first, (9e9,))[0] < self.spans["machine"][0]:
                ids = [first]
            else:
                pts = self._box_pts(hosts.machine_box(self.sb))
        self._last_ids = list(ids)                     # what this shot frames (not an intruder)
        for pid in ids:
            pts += self._box_pts(self.boxes[pid])
        if frame in ("part", "prop") and pts:          # a small part keeps some context: never a macro of a blob
            lo = Vector([min(p[i] for p in pts) for i in range(3)])
            hi = Vector([max(p[i] for p in pts) for i in range(3)])
            c, half = (lo + hi) / 2, (MIN_SUBJECT if frame == "part" else MIN_PROP) / 2
            pts = pts + [Vector((c.x + sx * half, c.y, c.z + sz * half)) for sx in (-1, 1) for sz in (-1, 1)]
        rots = [self.place[pid]["rot"] for pid in (on or ids) if self.mounted(pid)]
        if frame == "machine":
            facing = 180 if s.get("side") == "back" or (rots and all(r == 180 for r in rots)) else 0
        elif rots:
            facing = max(set(rots), key=rots.count)
        else:
            facing = 0
        return pts, facing

    @staticmethod
    def _basis(azi, elev):
        out = Vector((math.sin(azi) * math.cos(elev), -math.cos(azi) * math.cos(elev), math.sin(elev)))
        fwd = -out
        right = fwd.cross(Vector((0, 0, 1))).normalized()
        up = right.cross(fwd).normalized()
        return out, fwd, right, up

    def _fit(self, pts, azi, elev, lens, fill, wmax, band=BAND):
        """Camera (pos, target) that shows pts filling `fill` of the subject band's height (and at most wmax of
        the half-width), centred in the band. Solved by projection, so it is exact for this lens."""
        out, fwd, right, up = self._basis(azi, elev)
        ty = 18.0 / lens
        tx = ty * W_PX / H_PX
        band_c = 1 - 2 * ((band[0] + band[1]) / 2) / H_PX
        band_h = (band[1] - band[0]) / H_PX               # half-height of the band in NDC units
        want = fill * band_h
        lo_ = Vector([min(p[i] for p in pts) for i in range(3)])
        hi_ = Vector([max(p[i] for p in pts) for i in range(3)])
        target = (lo_ + hi_) / 2

        def ext(dist, tgt):
            pos = tgt + out * dist
            xs, ys = [], []
            for p in pts:
                v = p - pos
                z = max(1e-3, v.dot(fwd))
                xs.append(v.dot(right) / (z * tx))
                ys.append(v.dot(up) / (z * ty))
            return min(xs), max(xs), min(ys), max(ys)

        dist = 3.0
        for _ in range(4):
            lo, hi = 0.15, 80.0
            for _ in range(40):
                mid = (lo + hi) / 2
                x0, x1, y0, y1 = ext(mid, target)
                if (y1 - y0) / 2 <= want and max(abs(x0), abs(x1)) <= wmax and (x1 - x0) / 2 <= wmax:
                    hi = mid
                else:
                    lo = mid
            dist = hi
            x0, x1, y0, y1 = ext(dist, target)
            cy, cx = (y0 + y1) / 2, (x0 + x1) / 2
            target = target + up * ((cy - band_c) * dist * ty) + right * (cx * dist * tx)
        return target + out * dist, target, dist

    def _blocked(self, s, pts, t0, t1, azi, elev, lens, fill, wmax):
        """How much of the subject's on-screen box other parts (in front of it) cover, 0..1."""
        pos, tgt, _d = self._fit(pts, math.radians(azi), math.radians(elev), lens, fill, wmax)
        out, fwd, right, up = self._basis(math.radians(azi), math.radians(elev))

        def rect(ps):
            xs, ys, zs = [], [], []
            for p in ps:
                v = p - pos
                z = max(1e-3, v.dot(fwd))
                xs.append(v.dot(right) / z)
                ys.append(v.dot(up) / z)
                zs.append(z)
            return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)
        sx0, sx1, sy0, sy1, sz0, sz1 = rect(pts)
        area = max(1e-9, (sx1 - sx0) * (sy1 - sy0))
        ty = 18.0 / lens
        tx = ty * W_PX / H_PX
        mine = set(s.get("on", []))
        cover, clutter = 0.0, 0.0
        machine_on = self.spans["machine"][0] < t1
        others = [(pid, box) for pid, box in self.boxes.items() if pid not in mine and self._visible(pid, t0, t1)]
        others += list(self.occluders.items()) if machine_on else []
        for pid, box in others:
            ox0, ox1, oy0, oy1, oz0, oz1 = rect(self._box_pts(box))
            if oz0 >= (sz0 + sz1) / 2:                      # behind the subject: no harm
                continue
            w = max(0.0, min(sx1, ox1) - max(sx0, ox0))
            h = max(0.0, min(sy1, oy1) - max(sy0, oy0))
            cover += w * h / area
            fw = max(0.0, min(tx, ox1) - max(-tx, ox0))     # a nearer part filling the frame around it
            fh = max(0.0, min(ty, oy1) - max(-ty, oy0))
            clutter += fw * fh / (4 * tx * ty)
        return min(1.0, cover) + 0.6 * min(1.0, clutter)

    def _intrusion(self, s, pts, t0, t1, azi, elev, lens, fill, wmax, props_only=False):
        """How much other parts intrude on a framing: a part cut by the frame edge costs its in-frame area
        three times over, a whole part in the background once (fractions of the frame)."""
        pos, _tgt, _d = self._fit(pts, math.radians(azi), math.radians(elev), lens, fill, wmax)
        _out, fwd, right, up = self._basis(math.radians(azi), math.radians(elev))
        ty = 18.0 / lens
        tx = ty * W_PX / H_PX
        mine = set(s.get("on", [])) | set(getattr(self, "_last_ids", []))
        cost = 0.0
        for pid, box in self.boxes.items():
            if pid in mine or not self._visible(pid, t0, t1) or (props_only and self.mounted(pid)):
                continue
            xs, ys = [], []
            for q in self._box_pts(box):
                v = q - pos
                z = v.dot(fwd)
                if z <= 1e-3:
                    continue
                xs.append(v.dot(right) / (z * tx))
                ys.append(v.dot(up) / (z * ty))
            if not xs:
                continue
            ix = max(0.0, min(1.0, max(xs)) - max(-1.0, min(xs)))
            iy = max(0.0, min(1.0, max(ys)) - max(-1.0, min(ys)))
            inside = ix * iy / 4
            whole = (max(xs) - min(xs)) * (max(ys) - min(ys)) / 4
            cost += inside * (1.0 if inside >= 0.95 * whole else 3.0)
            # a part under the captions: they would sit on it
            cy0, cy1 = 1 - 2 * CAPTION_ZONE[1] / H_PX, 1 - 2 * CAPTION_ZONE[0] / H_PX
            cx_ = max(0.0, min(0.6, max(xs)) - max(-0.6, min(xs)))
            cy_ = max(0.0, min(cy1, max(ys)) - max(cy0, min(ys)))
            cost += 4.0 * cx_ * cy_ / 4
        return cost

    def _under_captions(self, s, pts, t0, t1, azi, elev, lens, fill, wmax):
        """Parts (other than the subject) a framing puts under the captions, a good part of the caption's width."""
        pos, _tgt, _d = self._fit(pts, math.radians(azi), math.radians(elev), lens, fill, wmax)
        _out, fwd, right, up = self._basis(math.radians(azi), math.radians(elev))
        ty = 18.0 / lens
        tx = ty * W_PX / H_PX
        cy0, cy1 = 1 - 2 * CAPTION_ZONE[1] / H_PX, 1 - 2 * CAPTION_ZONE[0] / H_PX
        mine = set(s.get("on", [])) | set(getattr(self, "_last_ids", []))
        out = []
        for pid, box in self.boxes.items():
            if pid in mine or not self._visible(pid, t0, t1) or not self.mounted(pid):
                continue
            xs, ys = [], []
            for q in self._box_pts(box):
                v = q - pos
                z = v.dot(fwd)
                if z > 1e-3:
                    xs.append(v.dot(right) / (z * tx))
                    ys.append(v.dot(up) / (z * ty))
            if xs and (max(0.0, min(0.5, max(xs)) - max(-0.5, min(xs))) > 0.3 and
                       max(0.0, min(cy1, max(ys)) - max(cy0, min(ys))) > 0.4 * (cy1 - cy0)):
                out.append(pid)
        return out

    def camera(self):
        shots = self.sb["shots"]
        self.cam_keys = []                                  # (t, state)
        # ONE home view of the machine (hosts.home_azimuth): every machine and prop shot uses it, and close shots
        # stay as near to it as a clear view allows, so the viewer never loses where things are
        home = hosts.home_azimuth(self.sb)
        prev_end, prev_azi = None, None
        for i, s in enumerate(shots):
            t0 = max(0.0, self.t_of(s["start_word"]) - 0.12) if i else 0.0
            t1 = (self.t_of(shots[i + 1]["start_word"]) - 0.12) if i + 1 < len(shots) else self.duration
            pts, facing = self._subject(s, t0, t1)
            frame = s.get("frame", "area")
            azi_d = home + (40 if frame == "prop" else 0)    # a prop: the machine slides out of the background
            elev_d = {"machine": 12, "area": 14, "part": 16, "prop": 10}.get(frame, 12)
            if frame == "prop":
                # the prop in front, the machine behind it (a little to one side): the analogy and the machine it
                # explains in one picture, never a prop alone on an empty floor
                pid0 = (s.get("on") or [None])[0]
                pl0 = self.place.get(pid0)
                if pl0 is not None and self.spans["machine"][0] < t1:
                    behind = math.degrees(math.atan2(pl0["x"], -pl0["y"]))
                    azi_d = min((behind + d for d in (18, -18, 30, -30, 8)),
                                key=lambda a: self._intrusion(s, pts, t0, t1, a, elev_d, 50.0, 0.8, 0.82, props_only=True)
                                + 0.002 * abs(a - behind - 18))
                else:
                    azi_d = min((home + d for d in (40, 70, 10, 100, -20)),
                                key=lambda a: self._intrusion(s, pts, t0, t1, a, elev_d, 50.0, 0.8, 0.82) +
                                0.0015 * abs(a - home - 40))
            if frame in ("part", "area"):                   # the illustrator's view for where the part sits
                slots = [self.place[q]["slot"] for q in s.get("on", []) if self.mounted(q)]
                if slots:
                    # the view between the parts' own views: a front part and a back part are seen from the side
                    vs = [math.radians(hosts.slot_view(self.sb, sl)) for sl in slots]
                    azi_d = math.degrees(math.atan2(sum(map(math.sin, vs)), sum(map(math.cos, vs))))
                    lens_ = {"area": 42.0, "part": 55.0}[frame]
                    # the camera height that sees the subject clearly with no other part under the captions or
                    # sliced by the frame edge (a lower camera drops what is under the subject out of the frame)
                    elev_d = min((elev_d, elev_d - 10, elev_d + 14, elev_d - 18),
                                 key=lambda e: self._blocked(s, pts, t0, t1, azi_d, e, lens_, 0.8, 0.82) +
                                 self._intrusion(s, pts, t0, t1, azi_d, e, lens_, 0.8, 0.82) +
                                 0.004 * abs(e - elev_d))
            elev = math.radians(elev_d)
            lens = {"machine": 34.0, "area": 42.0, "part": 55.0, "prop": 50.0}.get(frame, 42.0)
            fill = {"machine": 0.96, "area": 0.9, "part": 0.82, "prop": 0.8}.get(frame, 0.85)
            if frame == "part" and any(str(self.place[q].get("slot") or "").startswith("inside")
                                        for q in s.get("on", []) if q in self.place):
                fill = 0.8                                 # inside the machine: keep a little of the cabinet around it
            wmax = 0.9 if frame == "machine" else 0.82
            fstop = {"machine": 11.0, "area": 8.0, "part": 5.6, "prop": 7.0}.get(frame, 6.3)
            mv = s.get("move", "hold")

            if frame in ("part", "area"):
                # a part that would sit under the captions is framed WITH the subject (it is what is below it)
                under = self._under_captions(s, pts, t0, t1, azi_d, elev_d, lens, fill, wmax)
                h0 = max(p_.z for p_ in pts) - min(p_.z for p_ in pts)
                for q in under:
                    more = pts + self._box_pts(self.boxes[q])
                    # only a part right next to the subject joins the frame; a far one would turn a close-up into a
                    # wide shot (and still sit under the captions at its bottom)
                    if max(p_.z for p_ in more) - min(p_.z for p_ in more) <= 2.0 * max(h0, MIN_SUBJECT):
                        pts = more
            band = BAND_MACHINE if frame == "machine" else BAND

            def state(azi_deg, f):
                pos, tgt, dist = self._fit(pts, math.radians(azi_deg), elev, lens, f, wmax, band)
                return {"pos": tuple(pos), "target": tuple(tgt), "lens": lens, "fstop": fstop}
            if mv == "push_in":
                a, b = state(azi_d, fill * 0.84), state(azi_d, fill)
            elif mv == "pull_back":
                a, b = state(azi_d, fill), state(azi_d, fill * 0.84)
            elif mv == "orbit":
                a, b = state(azi_d - 8, fill * 0.95), state(azi_d + 8, fill * 0.95)
            else:
                a, b = state(azi_d - 2, fill * 0.96), state(azi_d + 2, fill)
            # a part flying out of its prop: framed with the prop until it lands, then the camera settles on the
            # part in its place (the prop is gone: holding the old framing leaves the machine jammed at the edge)
            settle = None
            for e in self.events:
                if e["do"] == "appear" and e.get("from") in (s.get("on") or []):
                    tl = self.t_of(e["word"]) + 0.2
                    if t0 < tl < t1 - 1.6:
                        s2 = dict(s, on=[q for q in s.get("on", []) if self.mounted(q)])
                        pts2, _f = self._subject(s2, tl, t1)
                        if pts2:
                            def state2(azi_deg, f, pts2=pts2):
                                pos, tgt, _d = self._fit(pts2, math.radians(azi_deg), elev, lens, f, wmax, band)
                                return {"pos": tuple(pos), "target": tuple(tgt), "lens": lens, "fstop": fstop}
                            settle = (tl, state2(azi_d, fill * 0.92), state2(azi_d, fill))
            # calm transitions: the camera GLIDES from one view to the next (the eye follows it); only a jump to the
            # other side of the machine is a cut
            turn = abs(((azi_d - prev_azi) + 180) % 360 - 180) if prev_azi is not None else 0.0
            if prev_end is not None:
                if turn > 110:
                    self.cam_keys.append((t0 - 1e-4, prev_end))
                    self.cam_keys.append((t0, a))
                else:
                    glide = min(0.45 * (t1 - t0), 0.8 + 0.5 * turn / 110)
                    self.cam_keys.append((t0, prev_end))
                    self.cam_keys.append((t0 + glide, a))
            else:
                self.cam_keys.append((t0, a))
            if settle is not None:
                tl, c1, c2 = settle
                if tl + 0.25 > self.cam_keys[-1][0]:
                    self.cam_keys.append((tl + 0.25, b))
                self.cam_keys.append((min(t1 - 0.2, tl + 1.5), c1))
                b = c2
            self.cam_keys.append((t1, b))
            prev_end, prev_azi = b, azi_d
        cd = bpy.data.cameras.new("cam")
        cd.sensor_fit, cd.sensor_height = "VERTICAL", 36.0
        cd.clip_start, cd.clip_end = 0.02, 200.0
        cd.dof.use_dof = True
        cd.shift_y = 0.0
        self.cam = bpy.data.objects.new("cam", cd)
        bpy.context.scene.collection.objects.link(self.cam)
        bpy.context.scene.camera = self.cam
        self.cam.rotation_mode = "QUATERNION"

        def pose(t):
            ks = self.cam_keys
            f = ks[-1][1]
            if t <= ks[0][0]:
                f = ks[0][1]
            else:
                for (ta, a), (tb, b) in zip(ks, ks[1:]):
                    if ta <= t <= tb:
                        u = smooth((t - ta) / max(1e-6, tb - ta))
                        f = {k: (tuple(x + (y - x) * u for x, y in zip(a[k], b[k])) if isinstance(a[k], tuple)
                                 else a[k] + (b[k] - a[k]) * u) for k in a}
                        # swing AROUND the subject: the view direction turns and the distance changes smoothly
                        # (a straight line between two views passes too close, and the subject spills out of the
                        # frame mid-glide)
                        oa = Vector(a["pos"]) - Vector(a["target"])
                        ob = Vector(b["pos"]) - Vector(b["target"])
                        la, lb = max(oa.length, 1e-4), max(ob.length, 1e-4)
                        na, nb = oa.normalized(), ob.normalized()
                        d = na.slerp(nb, u) if na.dot(nb) > -0.99 else na
                        f["pos"] = tuple(Vector(f["target"]) + d * math.exp(math.log(la) + (math.log(lb) - math.log(la)) * u))
                        break
            pos, tgt = Vector(f["pos"]), Vector(f["target"])
            self.cam.location = pos
            self.cam.rotation_quaternion = (tgt - pos).to_track_quat("-Z", "Y")
            cd.lens = f["lens"]
            cd.dof.focus_distance = (tgt - pos).length
            cd.dof.aperture_fstop = f["fstop"]
        self.poses.append(pose)

    def screen_boxes(self) -> dict:
        """{id: [x0, y0, x1, y1]} in master pixels (may reach past the frame) of every part on screen and of the
        machine body, from the real posed geometry: what the layout check and the pill placer avoid."""
        from bpy_extras.object_utils import world_to_camera_view
        sc = bpy.context.scene
        out = {}
        groups = [(pid, p.meshes) for pid, p in self.parts.items()] + [("machine", self.host.meshes)]
        for gid, meshes in groups:
            xs, ys = [], []
            for m in meshes:
                if m.hide_render or abs(m.matrix_world.determinant()) < 1e-9:
                    continue
                if gid == "machine" and any(k in m.name for k in ("glass", "lamp", "foot")):
                    continue
                for c in m.bound_box:
                    v = world_to_camera_view(sc, self.cam, m.matrix_world @ Vector(c))
                    if v.z <= 0:
                        continue
                    xs.append(v.x * W_PX)
                    ys.append((1 - v.y) * H_PX)
            if xs and max(xs) > 0 and min(xs) < W_PX and max(ys) > 0 and min(ys) < H_PX:
                out[gid] = [round(min(xs), 1), round(min(ys), 1), round(max(xs), 1), round(max(ys), 1)]
        return out

    # ------------------------------------------------------------ time
    def pose(self, t: float):
        for fn in self.poses:
            fn(t)


_WORLD: World | None = None


def _on_frame(scene, depsgraph=None):
    if _WORLD is not None:
        _WORLD.pose((scene.frame_current + scene.frame_subframe - 1) / FPS)


def main(job_path: str):
    global _WORLD
    t0 = time.time()
    job = json.load(open(job_path, encoding="utf-8"))
    core.reset()
    q = job.get("quality", "draft")
    core.setup("draft" if q == "preview" else q, pct=job.get("pct"))
    core.set_look("AgX - Medium High Contrast", -0.6)
    core.set_bloom(6.0, 0.4)
    _t, dims, _d, _a, accent, _s = hosts.host(job["storyboard"])
    st = studio.build_bright(job.get("hdri"), accent=accent, size=max(1.0, dims[2] / 1.4),
                             center=(0.0, 0.0, dims[2] * 0.5))
    w = World(job)
    w.studio = st
    w.build()
    w.camera()
    _WORLD = w
    bpy.app.handlers.frame_change_pre.append(_on_frame)
    say("built", seconds=round(time.time() - t0, 1), parts=len(w.parts))
    out = job["out_dir"]
    os.makedirs(out, exist_ok=True)
    sc = bpy.context.scene
    frames = job.get("stills") or list(range(job["frames"][0], job["frames"][1] + 1))
    names = list(w.anchor_objs)
    track, boxes = {}, {}
    for f in frames:
        sc.frame_set(f)
        track[str(f)] = A.sample(names, w.anchor_objs)
        boxes[str(f)] = w.screen_boxes()
    with open(os.path.join(out, "anchors.json"), "w", encoding="utf-8") as fh:
        json.dump({"fps": FPS, "width": W_PX, "height": H_PX, "frames": track, "boxes": boxes}, fh)
    say("anchors", frames=len(frames))
    t_r = time.time()
    if job.get("stills"):
        n = core.render_frames(out, 0, 0, only=frames)
    else:
        n = core.render_frames(out, frames[0], frames[-1])
    say("done", rendered=n, s_per_frame=round((time.time() - t_r) / max(1, n), 2),
        total_s=round(time.time() - t0, 1))


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:]
    main(argv[0])
