"""
Phase 0 proof of concept: "How a backyard pool is built" — ~20 s, 6 beats.

Runs inside Blender:
  blender --background --factory-startup --python engine/poc_pool.py -- TIMINGS.json OUT_DIR [--preview]

TIMINGS.json = {"fps": 30, "total_frames": N, "beats": [{"start": f0, "end": f1}, ...]} — produced
from the real voiceover, so every action lands on its words. --preview renders one still per beat.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from engine import toy  # noqa: E402
from engine.backyard import Backyard, PIT_CENTER, PIT_W, PIT_L, PIT_DEPTH  # noqa: E402
from engine.camera import shot, facing_to  # noqa: E402
from engine.character import Character  # noqa: E402
from engine.machines import Excavator, Spray, blueprint, nozzle  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
timings = json.load(open(args[0], encoding="utf-8"))
out_dir = args[1]
preview = "--preview" in args

beats = [(b["start"] + 1, b["end"] + 1) for b in timings["beats"]]   # Blender frames are 1-based
total = timings["total_frames"]

scene = toy.reset_scene()
scene.frame_start, scene.frame_end = 1, total
toy.setup_world()
toy.add_sun(strength=4.8, angle_deg=3)
toy.add_area("Fill", (-6, -8, 5), (0, 1, 0.5), energy=280, size=8)
toy.add_area("Rim", (4, 10, 6), (0, 1, 0.8), energy=350, size=6, color=(1.0, 0.9, 0.78))

yard = Backyard()
c = PIT_CENTER
hw, hl = PIT_W / 2, PIT_L / 2

# ---- cast ----
max_ = Character("Max", {"hat": "#FF7A00", "iris": "#7A4A1C"})
exc = Excavator(location=(c.x - hl - 2.3, c.y, 0), facing_deg=0)
exc_parked = Vector(exc.root.location)
exc_offstage = Vector((c.x - hl - 9.0, c.y, 0))
exc.root.location = exc_offstage
exc.root.keyframe_insert("location", frame=1)

plan = blueprint()
# Held open at chest height, tilted up toward his face (and the camera).
plan.parent = max_.j["spine"]
plan.location = (0.0, -0.36, 0.3)
plan.rotation_euler = (math.radians(-55), 0, 0)

(b1, e1), (b2, e2), (b3, e3), (b4, e4), (b5, e5), (b6, e6) = beats
corner_se = Vector((c.x + hl + 0.6, c.y - hw - 0.6, 0))


def at(p):
    return Vector(p)


# ---- Beat 1: "Every backyard pool starts with a plan." ----
spot1 = Vector((c.x + 0.4, c.y - hw - 1.0, 0))
max_.place(1, spot1, 0)
max_.pose(b1, shoulderR=(-50, 0, 22), shoulderL=(-50, 0, -22), head=(18, 0, 0))   # studying the plan
max_.pose(e1 - 14, shoulderR=(-50, 0, 22), shoulderL=(-50, 0, -22), head=(18, 0, 4))
max_.pose(e1 - 4, shoulderR=(-50, 0, 22), shoulderL=(-50, 0, -22), head=(-6, 0, 0))  # looks up, grins
max_.smile(b1)
max_.smile(e1 - 6, big=True)
shot(b1, e1, cam_from=(c.x + 2.8, c.y - 7.0, 1.6), cam_to=(c.x + 1.9, c.y - 5.4, 1.5),
     aim_from=spot1 + Vector((0, 0, 1.35)), lens=40, fstop=2.0)

# ---- Beat 2: "First, Max marks the shape with stakes and string." ----
toy.hide_tree(plan, 1, False)
toy.hide_tree(plan, b2, True)
max_.walk(b2, b2 + 26, to=corner_se, facing_deg=facing_to(spot1, corner_se))
max_.place(b2 + 30, corner_se, facing_to(corner_se, c))
max_.hammer(b2 + 30, e2 - 2)
yard.stakes(b2 + 18, frames=max(30, e2 - b2 - 22))
shot(b2, e2, cam_from=(c.x + 3.4, c.y - 6.0, 2.6), cam_to=(c.x + 3.0, c.y - 5.2, 2.1),
     aim_from=c + Vector((1.2, -0.4, 0.2)), aim_to=corner_se + Vector((0, 0, 0.6)), lens=26, fstop=4.0)

# ---- Beat 3: "Then the excavator digs a hole almost two meters deep." ----
exc.root.location = exc_offstage
exc.root.keyframe_insert("location", frame=b3 - 2)
exc.root.location = exc_parked
exc.root.keyframe_insert("location", frame=b3 + 14)       # rolls in
yard.remove_stakes(b3 + 14)
yard.dig(b3 + 16, e3, depth=PIT_DEPTH)
exc.dig_cycle(b3 + 16, e3)
spot3 = Vector((c.x + 0.6, c.y - hw - 1.3, 0))   # beside the camera axis, not in front of it
max_.place(b3, spot3, facing_to(spot3, exc_parked))
max_.point(b3 + 18, e3 - 4, hand="L", up_deg=60, side_deg=10)
max_.auto_blink(b3, e3, seed=3)
# Looking down the pit's long axis: pit in the foreground, excavator digging behind it.
shot(b3, e3, cam_from=(c.x + 5.6, c.y - 2.2, 1.6), cam_to=(c.x + 4.4, c.y - 1.6, 2.6),
     aim_from=Vector((c.x - 2.4, c.y, 0.9)), aim_to=Vector((c.x - 1.8, c.y, -0.3)), lens=24, fstop=5.0)

# ---- Beat 4: "A cage of steel rebar makes it strong." ----
exc.root.location = exc_parked
exc.root.keyframe_insert("location", frame=b4)
exc.root.location = exc_offstage
exc.root.keyframe_insert("location", frame=b4 + 30)       # drives away
exc.rest(b4)
yard.rebar(b4 + 4, e4)
rim_s = Vector((c.x - 0.6, c.y - hw - 0.45, 0))
max_.place(b4, rim_s, facing_to(rim_s, c))
max_.pose(b4 + 2, head=(30, 0, 0), spine=(10, 0, 0))     # looking down into the pit
max_.cheer(e4 - 26, e4)
shot(b4, e4, cam_from=(c.x + 0.4, c.y - 2.4, 5.8), cam_to=(c.x + 0.1, c.y - 1.9, 5.3),
     aim_from=c + Vector((0, 0, -PIT_DEPTH + 0.2)), lens=24, fstop=5.6)

# ---- Beat 5: "Sprayed concrete turns it into a solid shell." ----
gun = nozzle()
toy.hide_tree(gun, 1, True)
toy.hide_tree(gun, b5, False)
max_.hold(gun, "R")
gun.location = (0, -0.22, 0.0)
gun.rotation_euler = (math.radians(90), 0, 0)
max_.place(b5, rim_s, facing_to(rim_s, c))
max_.pose(b5 + 4, shoulderR=(-70, 0, -8), shoulderL=(-60, 0, 20), spine=(18, 0, 0))
max_.pose(e5 - 2, shoulderR=(-70, 0, 8), shoulderL=(-60, 0, 30), spine=(18, 0, 6))
concrete = Spray("concrete", toy.material("wet_concrete", toy.srgb("#5E5D59"), roughness=0.3), count=46,
                 radius=0.05)
concrete.run(b5 + 6, e5 - 2, source=rim_s + Vector((0, 0.55, 1.0)), target=c + Vector((0, 0.6, -0.9)),
             spread=0.9, arc=0.25)
yard.spray_concrete(b5 + 6, e5 - 4)
shot(b5, e5, cam_from=(c.x - 3.6, c.y - 3.4, 1.7), cam_to=(c.x - 3.0, c.y - 3.0, 2.2),
     aim_from=rim_s + Vector((0.7, 0.9, 0.2)), lens=24, fstop=3.5)

# ---- Beat 6: "Add tiles, fill it with water… and dive in!" ----
toy.hide_tree(gun, b6, True)
yard.tiles_and_coping(b6, b6 + int((e6 - b6) * 0.3))
fill_end = b6 + int((e6 - b6) * 0.62)
yard.fill_water(b6 + int((e6 - b6) * 0.25), fill_end)
hose = Spray("waterjet", yard.m["water"], count=30, radius=0.04, seed=9)
hose.run(b6 + int((e6 - b6) * 0.25), fill_end, source=Vector((c.x + hl + 0.2, c.y + hw, 0.6)),
         target=c + Vector((1.2, 0.4, -0.6)), spread=0.25, arc=0.35, period=10)
jump_at = fill_end + 4
edge = Vector((c.x + hl + 0.45, c.y - 0.2, 0))   # east end, jumping along the pool
max_.place(b6, edge, facing_to(edge, c))
max_.cheer(b6 + 6, jump_at - 2)
max_.place(jump_at, edge, facing_to(edge, c))
max_.root.location = edge + Vector((-0.8, 0, 1.1))
max_.root.keyframe_insert("location", frame=jump_at + 8)
max_.root.location = Vector((c.x + hl - 1.1, c.y - 0.2, -1.0))
max_.root.keyframe_insert("location", frame=jump_at + 16)
max_.pose(jump_at + 8, shoulderL=(0, -160, 0), shoulderR=(0, 160, 0), legL=(-30, 0, 0), legR=(-30, 0, 0))
max_.cheer(jump_at + 18, e6)
splash = Spray("splash", yard.m["water"], count=36, radius=0.06, seed=4)
splash_at = Vector((c.x + hl - 1.1, c.y - 0.2, -0.2))
splash.run(jump_at + 15, min(e6, jump_at + 30), source=splash_at, target=splash_at + Vector((0, 0, 0.1)),
           spread=1.1, arc=1.2, period=14)
shot(b6, e6, cam_from=(c.x + 1.2, c.y - 4.4, 1.6), cam_to=(c.x + 2.0, c.y - 7.6, 3.8),
     aim_from=c + Vector((1.0, 0, 0.3)), aim_to=c + Vector((0.6, 0, -0.1)), lens=28, fstop=4.0)

# Everyone keeps breathing/blinking between explicit actions.
max_.auto_blink(1, total, seed=11)

# ---- render ----
scene.render.image_settings.file_format = "PNG"
if preview:
    for i, (b, e) in enumerate(beats, start=1):
        f = (b + e) // 2
        scene.frame_set(f)
        scene.render.filepath = os.path.join(out_dir, f"preview_beat{i}.png")
        bpy.ops.render.render(write_still=True)
else:
    scene.render.filepath = os.path.join(out_dir, "frames", "f_")
    bpy.ops.render.render(animation=True)
print("DONE")
