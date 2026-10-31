"""
Blender-side test of the cutaway characters' motion capture (Character.act / idle / talk / walk, played by
character.perform_queued around the hand keys). Max idles, walks, nods "yes" while a hand-keyed point holds
his right arm, then talks with his mouth shut. Measures that the clips really drove the body, that the hand
keys kept their joint, and that no joint pops between frames; renders three stills to look at.

    blender --background --factory-startup --python engine/mocap_still.py -- OUT_DIR

Writes OUT_DIR/mocap_<frame>.png and OUT_DIR/mocap_report.json (run by tests/test_water.py's sibling test).
"""
import json
import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import toy  # noqa: E402
from engine.character import Character, perform_queued  # noqa: E402
from engine.mocap import JOINTS  # noqa: E402

STILLS = (60, 125, 180)


def main():
    out = sys.argv[sys.argv.index("--") + 1]
    os.makedirs(out, exist_ok=True)
    scene = toy.reset_scene()
    scene.render.resolution_percentage = 30
    scene.eevee.taa_render_samples = 16
    scene.frame_start, scene.frame_end = 1, 210
    toy.setup_world()
    toy.add_sun()
    grass = bpy.data.materials.new("grass")
    toy._set(toy._principled(grass), "Base Color", (*toy.srgb("#5DA34A"), 1))
    toy.box("ground", (20, 20, 0.2), (0, 0, -0.1), mat=grass, bevel=0)
    mx = Character("Max", location=(-1.5, 0, 0))
    mx.idle(1, 210)
    mx.walk(30, 90, (1.0, 0, 0), 0.0)
    mx.act("yes", 100, 150)
    mx.point(110, 140, hand="R", up_deg=70)          # by hand, during the clip: the arm must stay pointing
    mx.talk(160, 205)
    kid = Character("Kid", location=(3.0, 2.0, 0))  # one clip and nothing else: it must not outlive its frames
    kid.act("talk", 20, 60)
    k2 = Character("Kid2", location=(-3.0, 2.0, 0))  # a 20-frame scoop given 100 frames: it must keep scooping
    k2.act("pick_up", 100, 200)
    perform_queued()

    def rot(j, f):
        scene.frame_set(f)
        return tuple(mx.j[j].rotation_euler)
    jumps, where = {}, {}
    for j in JOINTS:
        prev = rot(j, 1)
        worst, at = 0.0, 0
        for f in range(2, 211):
            cur = rot(j, f)
            d = max(abs(math.degrees(a - b)) for a, b in zip(cur, prev))
            if d > worst:
                worst, at = d, f
            prev = cur
        jumps[j], where[j] = round(worst, 1), at
    moving = {j: round(max(abs(math.degrees(a)) for f in range(31, 90, 5) for a in rot(j, f)), 1)
              for j in ("legL", "legR", "kneeL", "shoulderL")}
    pointing = [round(math.degrees(a), 1) for a in rot("shoulderR", 125)]
    late = {}
    for f in range(160, 200, 2):                    # the last half of the range: a frozen clip would not move
        scene.frame_set(f)
        for j in JOINTS:
            for a, v in enumerate(k2.j[j].rotation_euler):
                late.setdefault((j, a), []).append(math.degrees(v))
    scooping_late = round(max(max(v) - min(v) for v in late.values()), 1)
    scene.frame_set(120)
    leftover = round(max(abs(math.degrees(a)) for j in JOINTS for a in kid.j[j].rotation_euler), 1)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
    cam.location = (0, -6.0, 1.2)
    cam.rotation_euler = (math.radians(84), 0, 0)
    cam.data.lens = 35
    scene.camera = cam
    for f in STILLS:
        scene.frame_set(f)
        scene.render.filepath = os.path.join(out, f"mocap_{f}.png")
        bpy.ops.render.render(write_still=True)
    report = {"max_jump_deg_per_frame": jumps, "at_frame": where, "walk_motion_deg": moving, "shoulderR_at_125": pointing,
              "leftover_after_clip_deg": leftover, "scoop_motion_late_deg": scooping_late}
    with open(os.path.join(out, "mocap_report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
