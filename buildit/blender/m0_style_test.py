"""
Milestone 0 style test (runs inside Blender): a floor pump drops in beside a glass tank; each stroke pushes a
stream of glowing air through the hose and the tank fills dot by dot; a red valve pops onto the cap and closes.
Every event is keyed to a word of runs/buildit/m0/words.json.

    blender -b --factory-startup -P buildit/blender/m0_style_test.py -- <out_dir> <quality> [f0 f1]
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from buildit.blender import core, effects, parts, studio  # noqa: E402
from buildit.blender import motion as MO  # noqa: E402
from buildit.blender.camera import Cam  # noqa: E402
from cutaway.blender import anchors as A  # noqa: E402

FPS = 30


def word_t(words, text, nth=0):
    hits = [w for w in words if w["text"].strip(".,!?").lower() == text]
    return hits[min(nth, len(hits) - 1)]["start"]


def main(out_dir, quality, frames=None):
    t_start = time.time()
    words = json.load(open(os.path.join(ROOT, "runs", "buildit", "m0", "words_raw.json"), encoding="utf-8"))
    duration = 10.1
    f0, f1 = frames or (1, int(round(duration * FPS)))

    core.reset()
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
    core.setup(quality)
    hdri = os.path.join(ROOT, "cutaway", "assets", "hdri", "studio_small_09_2k.hdr")
    st = studio.build(hdri if os.path.exists(hdri) else None, size=1.0, center=(0.0, 0.0, 0.45))

    # --- parts
    tank, tk = parts.glass_tank("tank", r=0.2, h=0.62)
    tank.location = (0.22, 0.0, 0.0)
    pump, pk = parts.hand_pump("pump")
    pump.location = (-0.30, 0.02, 0.0)
    hose_pts = [(-0.238, 0.02, 0.09), (-0.19, 0.0, 0.05), (-0.10, -0.05, 0.12), (-0.07, -0.05, 0.50),
                (0.0, -0.03, 0.88), (0.16, 0.0, 0.97), (0.31, 0.0, 0.92), (0.31, 0.0, 0.835)]
    hose = parts.hose("hose", hose_pts)
    valve, vk = parts.valve("valve")
    seat = tank.location + tk["anchors"]["valve_seat"]
    valve.location = seat
    bpy.context.view_layer.update()

    # --- effects
    stream = effects.Flow("air_stream", hose_pts, count=70, spread=0.004, size=0.0045, stretch=2.2,
                          closed=False, ramp=((0.0, "#ffffff"), (1.0, "#d8ecff")), strength=5.0, gated=True)
    stream.obj["gn_mod"] = "flow"
    stream.obj["gn_inputs"] = stream.socket
    z0, z1 = tk["inner_z"]
    cloud = effects.Cloud("air_cloud", tk["inner_r"] * 0.92, z0 + 0.01, z1 - 0.01, count=700, size=0.0055,
                          color="#fff4dc", strength=9.0)
    cloud.obj.location = tank.location

    # --- story timing from the words
    t_pump = word_t(words, "pump")
    t_push = word_t(words, "push")
    t_valve = word_t(words, "valve")
    t_cant = word_t(words, "can't")
    strokes = [t_push + 0.02, t_push + 0.95, t_push + 1.85, t_push + 2.75, t_push + 3.6]
    down, up = 0.36, 0.42

    def stroke_depth(t):
        d = 0.0
        for s in strokes:
            if s <= t < s + down:
                d = MO.smooth((t - s) / down)
            elif s + down <= t < s + down + up:
                d = 1 - MO.smooth((t - s - down) / up)
        return d

    def pumped(t):           # air delivered so far (0..1 per stroke, while pushing down)
        return sum(MO.clamp01((t - s) / down) for s in strokes)

    tl = MO.Timeline()
    tl.add(MO.drop_in(pump, t_pump, height=0.9))
    hose_on = t_pump + 0.25
    tl.add((lambda t: setattr(hose, "hide_render", t < hose_on), (hose,)))
    rest_z = pk["handle"].location.z

    def pump_pose(t):
        pk["handle"].location.z = rest_z - pk["travel"] * stroke_depth(t)
    tl.add((pump_pose, (pk["handle"],)))

    def air_pose(t):
        p = pumped(t)
        on = 1.0 if any(s - 0.05 <= t < s + down + 0.25 for s in strokes) else 0.0
        stream.obj["flow_on"] = on
        stream.set_phase(p * 1.15)
        stream.obj.hide_render = t < hose_on
        cloud.set(fill=min(0.92, 0.18 * p), time=t * 0.6, top=z1 - 0.01)
    tl.add((air_pose, (stream.obj, cloud.obj)))
    tl.add(MO.pop_in(valve, t_valve - 0.05))

    def valve_pose(t):
        u = MO.smooth((t - t_cant) / 0.9)
        vk["wheel"].rotation_euler.z = -u * math.tau * 1.25
    tl.add((valve_pose, (vk["wheel"],)))

    # --- camera: wide on both, push to the tank, rise to the valve, settle close on the air
    cx = 0.0
    keys = [
        (0.0, {"pos": (cx + 0.05, -3.25, 1.05), "target": (cx, 0.0, 0.42), "lens": 52.0, "fstop": 8.0}),
        (t_push + 0.4, {"pos": (cx + 0.08, -3.0, 1.02), "target": (cx + 0.02, 0.0, 0.43), "lens": 52.0,
                        "fstop": 8.0}),
        (t_valve - 0.6, {"pos": (0.16, -2.35, 0.98), "target": (0.12, 0.0, 0.48), "lens": 55.0, "fstop": 6.0}),
        (t_valve + 0.5, {"pos": (0.22, -1.75, 1.28), "target": (0.22, 0.0, 0.74), "lens": 62.0, "fstop": 4.0}),
        (duration, {"pos": (0.24, -1.45, 0.92), "target": (0.22, 0.0, 0.52), "lens": 66.0, "fstop": 3.2}),
    ]
    cam = Cam(keys)
    cam.obj.data.shift_y = -0.11              # the subject sits above the caption band

    # anchors for labels
    an = {"tank_air": parts.empty("a_tank_air", tk["anchors"]["inside"] + Vector((0, 0, 0.05)), tank),
          "valve": parts.empty("a_valve", vk["anchors"]["wheel"], valve),
          "pump": parts.empty("a_pump", pk["anchors"]["handle"], pk["handle"])}

    tl.bake(f0, f1, extra=[st["wash"]])
    for f in range(f0 - 1, f1 + 2):
        cam.place((f - 1) / FPS)
        cam.key(f)
    print("CUTAWAY " + json.dumps({"event": "baked", "seconds": round(time.time() - t_start, 1)}), flush=True)

    track = {}
    for f in range(f0, f1 + 1):
        bpy.context.scene.frame_set(f)
        track[str(f)] = A.sample(list(an), an)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "anchors.json"), "w", encoding="utf-8") as fh:
        json.dump({"fps": FPS, "width": 1080, "height": 1920, "frames": track}, fh)
    for prefix in filter(None, os.getenv("BUILDIT_PROF_OFF", "").split(",")):     # profiling: drop elements
        for o in bpy.data.objects:
            if o.name.startswith(prefix):
                o.animation_data_clear()
                o.hide_render = True
    t_r = time.time()
    n = core.render_frames(out_dir, f0, f1)
    print("CUTAWAY " + json.dumps({"event": "done", "rendered": n, "render_s": round(time.time() - t_r, 1),
                                   "s_per_frame": round((time.time() - t_r) / max(1, n), 2),
                                   "total_s": round(time.time() - t_start, 1)}), flush=True)


if __name__ == "__main__":
    a = sys.argv[sys.argv.index("--") + 1:]
    fr = (int(a[2]), int(a[3])) if len(a) > 3 else None
    main(a[0], a[1], fr)
