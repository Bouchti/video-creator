"""
"How a backyard pool is built" — v3 film (17 beats, ~75 s), runs inside Blender:

  blender --background --factory-startup --python engine/films/pool_film.py -- FILM.json TIMINGS.json OUT_DIR
          [--preview] [--frames=F1,F2,...]

TIMINGS.json (from the real voiceover): {"total_frames", "beats": [{"start","end"}], "envelope": [0..1 per frame]}.
Writes OUT_DIR/frames/f_####.png and OUT_DIR/events.json (sound events synced to the animation).
--preview renders 3 stills per beat (start / middle / end) as preview_NN_<beat>_<a|b|c>.png;
--frames renders exactly those frames as still_####.png (for checking a specific moment).
"""
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from engine import events, toy  # noqa: E402
from engine.backyard import Backyard, PIT_CENTER, PIT_W, PIT_L, PIT_DEPTH  # noqa: E402
from engine.camera import shot, facing_to  # noqa: E402
from engine.character import Character  # noqa: E402
from engine.machines import (Excavator, Spray, blueprint, nozzle, hammer_prop, stopwatch, spray_can,  # noqa: E402
                             rake, trowel, survey_rod, test_tube, chlorinator)

args = sys.argv[sys.argv.index("--") + 1:]
film = json.load(open(args[0], encoding="utf-8"))
timings = json.load(open(args[1], encoding="utf-8"))
out_dir = args[2]
preview = "--preview" in args
only_frames = [int(x) for a in args if a.startswith("--frames=") for x in a.split("=", 1)[1].split(",") if x]
env = timings.get("envelope", [])
total = timings["total_frames"]
B = {b["id"]: (t["start"] + 1, t["end"] + 1) for b, t in zip(film["beats"], timings["beats"])}

scene = toy.reset_scene()
scene.frame_start, scene.frame_end = 1, total + 400
toy.setup_world()
sun = toy.add_sun(strength=4.8, angle_deg=3)
fill = toy.add_area("Fill", (-6, -8, 5), (0, 1, 0.5), energy=280, size=8)
toy.add_area("Rim", (4, 10, 6), (0, 1, 0.8), energy=350, size=6, color=(1.0, 0.9, 0.78))

yard = Backyard()
yard.dress()
yard.house_details()
yard.equipment_pad()
c = PIT_CENTER
hw, hl = PIT_W / 2, PIT_L / 2
V = Vector
RIM_S = V((c.x - 0.6, c.y - hw - 0.45, 0))
FLOOR = -PIT_DEPTH - 0.005
GRAVEL_TOP = -PIT_DEPTH + 0.05
WATER = -0.18
GAS_Y, POWER_Y = -3.4, 5.6           # painted utility lines (south and north lawns)

# ---------------- cast ----------------
max_ = Character("Max", {"hat": "#FF7A00", "iris": "#7A4A1C"})
lily = Character("Lily", {"hat": "#FFFFFF", "shirt": "#3DBE6E", "overalls": "#6B4FB8", "mustache": False,
                          "hair": "#2B1A10", "iris": "#2E6B3A", "skin": "#C98E6B", "ponytail": True,
                          "scale": 0.92})
toy.hide_tree(lily.root, 1, True)

EXC_Y = c.y + hw + 1.75               # excavator works from the north edge, facing south
EXC_YAW = -90
exc = Excavator(location=(6.3, EXC_Y, 0), facing_deg=EXC_YAW)
PILE = V((3.5, EXC_Y + 0.15, 0))


def prop(obj, holder=None, hand="R", rot=(0, 0, 0), loc=(0, 0, 0)):
    """Attach a prop to a hand (hidden until shown)."""
    if holder is not None:
        holder.hold(obj, hand)
    obj.location = loc
    obj.rotation_euler = [math.radians(a) for a in rot]
    toy.hide_tree(obj, 1, True)
    return obj


plan = blueprint()
plan.parent = max_.j["spine"]
plan.location = (0.0, -0.36, 0.3)
plan.rotation_euler = (math.radians(-55), 0, 0)
toy.hide_tree(plan, 1, True)
tool = prop(hammer_prop(), max_, "R", rot=(-90, 0, 0))
gun = prop(nozzle(), max_, "L", rot=(90, 0, 0), loc=(0, -0.22, 0.0))
can_y = prop(spray_can("can_yellow", "#FFD400"), max_, "R", rot=(-20, 0, 0))
can_r = prop(spray_can("can_red", "#E8322A"), lily, "R", rot=(-20, 0, 0))
lily_rake = prop(rake(), lily, "R", rot=(-35, 0, 0))
lily_trowel = prop(trowel(), lily, "R", rot=(-60, 0, 0))
tube = prop(test_tube(), max_, "R", rot=(-30, 0, 0))
rod = survey_rod("survey_rod", (c.x - 0.45, c.y + hw - 0.3, FLOOR), height=2.0)
toy.hide_tree(rod, 1, True)
watch, watch_hand = stopwatch()
watch.location = (c.x, c.y, 2.1)
toy.hide_tree(watch, 1, True)


def cam_face(pos, cam):
    return facing_to(pos, (cam[0], cam[1], 0))


def show(obj, b, e):
    toy.hide_tree(obj, b, False)
    toy.hide_tree(obj, e, True)


# Hook + rewind beats are assembled in post (make_film): the hook is rendered from the
# EPILOGUE (frames after the film's end, where the pool is finished), the rewind is a reversed
# montage of the build. The 3D timeline proper starts at the plan beat.
BUILD_START = B["plan"][0]
EPI = total                       # epilogue frame = EPI + hook frame
HOOK_B, HOOK_E = B["hook"]

# ---------------- plan (Max greets us, then unrolls the plan) ----------------
b, e = B["plan"]
spot = V((c.x + 0.8, c.y - hw - 2.4, 0))
cam = (spot.x + 1.6, spot.y - 2.6, 1.9)
max_.place(1, spot, cam_face(spot, cam))
max_.pose(b)
max_.wave(b + 2, b + 26, hand="R")
max_.smile(b + 2, big=True)
max_.brows(b + 2, 0.6)
max_.brows(b + 26, 0.0)
show(plan, b + 24, e)
max_.pose(b + 30, shoulderR=(-50, 0, 22), shoulderL=(-50, 0, -22), head=(18, 0, 0))
max_.pose(e - 16, shoulderR=(-50, 0, 22), shoulderL=(-50, 0, -22), head=(18, 0, 6))
max_.pose(e - 4, shoulderR=(-50, 0, 22), shoulderL=(-50, 0, -22), head=(-6, 0, 0))
max_.smile(e - 6, big=True)
shot(b, e, cam_from=cam, cam_to=(spot.x + 1.1, spot.y - 2.0, 1.75),
     aim_from=spot + V((0, -0.3, 1.15)), lens=36, fstop=2.0)

# ---------------- 3. utilities: Max paints the gas line, Lily the power line ----------------
b, e = B["utilities"]
gas0, gas1 = V((-2.8, GAS_Y, 0)), V((2.8, GAS_Y, 0))
pow0, pow1 = V((2.8, POWER_Y, 0)), V((-2.8, POWER_Y, 0))
max_.cut_place(b, gas0, facing_to(gas0, gas1))
max_.pose(b)
show(can_y, b, e)
w0, w1 = b + 6, e - 6
max_.walk(w0, w1, to=gas1, facing_deg=facing_to(gas0, gas1), hold_arm="R", hold_rot=(-38, 0, 8))
yard.utility_marks("gas", "#FFD400", gas0 + V((-0.35, 0, 0)), gas1 + V((-0.35, 0, 0)), w0, w1)
events.add(w0, "spray", duration=w1 - w0)
lily.cut_place(b, pow0, facing_to(pow0, pow1))
toy.hide_tree(lily.root, b, False)
show(can_r, b, e)
lily.walk(w0, w1, to=pow1, facing_deg=facing_to(pow0, pow1), hold_arm="R", hold_rot=(-38, 0, 8))
yard.utility_marks("power", "#E8322A", pow0 + V((0.3, 0, 0)), pow1 + V((0.3, 0, 0)), w0, w1)
toy.hide_tree(lily.root, e, True)
shot(b, e, cam_from=(-2.4, GAS_Y - 3.4, 2.5), cam_to=(1.2, GAS_Y - 3.2, 2.6),
     aim_from=V((-1.2, GAS_Y + 0.5, 0.35)), aim_to=V((2.0, GAS_Y + 0.5, 0.35)), lens=26, fstop=4.0)

# ---------------- 4. layout: walk to the corner, hammer stakes ----------------
b, e = B["layout"]
corner = V((c.x + hl + 0.6, c.y - hw - 0.6, 0))
max_.pose(b)
walk_end = min(b + max(24, int((corner - gas1).length / 1.5 * 30)), e - 30)
max_.walk(b + 2, walk_end, to=corner, facing_deg=facing_to(gas1, corner))
show(tool, walk_end, e)
max_.turn(walk_end + 1, facing_to(corner, c), frames=6)
max_.hammer(walk_end + 8, e - 2)
yard.stakes(b + 10, frames=max(30, e - b - 14))
shot(b, e, cam_from=(c.x + 4.4, c.y - 6.0, 2.6), cam_to=(c.x + 3.8, c.y - 5.2, 2.1),
     aim_from=c + V((1.0, -0.6, 0.2)), aim_to=corner + V((0, 0, 0.6)), lens=26, fstop=4.0)

# ---------------- 5. dig: the excavator really bites the lawn, column by column ----------------
b, e = B["dig"]
yard.remove_stakes(b)
stations = [V((col["x"], EXC_Y, 0)) for col in yard.columns]
n_cols = len(yard.columns)
start = b + 26
span = e - 6 - start
passes = 2 if span >= 6 * 30 else 1
order = [(n_cols - 1 - i, top) for i, top in yard.dig_plan(passes)]        # east → west first
cycle = min(56, span // len(order))
exc.rest(b)
exc.drive(b, start - 2, stations[order[0][0]])
exc.rest(start - 2)
tops = [col["top"] for col in yard.columns]
bites = []
for k, (i, new_top) in enumerate(order):
    y = c.y + (0.2 if new_top > -1.0 else -0.15)
    bites.append({"root": stations[i], "target": V((yard.columns[i]["x"], y, tops[i]))})
    tops[i] = new_top
timing = exc.dig_sequence(start, bites, dump_at=PILE + V((0, 0, 0.4)), yaw_deg=EXC_YAW, cycle=cycle)
for (i, new_top), t in zip(order, timing):
    yard.bite(i, t["bite"], t["curl"], new_top)
yard.spoil_pile(PILE, [t["dump"] for t in timing])
spot3 = V((c.x + 0.6, c.y - hw - 1.0, 0))
max_.cut_place(b, spot3, facing_to(spot3, c + V((0, 1.5, 0))))
max_.pose(b)
max_.point(b + 30, b + 70, hand="L", up_deg=50, side_deg=10)
for t in timing[::2]:
    max_.look_at(t["bite"], V((c.x, c.y + 0.8, 0.3)), hold=10)
max_.cheer(e - 30, e - 2)
shot(b, e, cam_from=(c.x - 3.8, c.y - 5.4, 3.8), cam_to=(c.x - 3.2, c.y - 4.7, 3.3),
     aim_from=V((c.x + 0.9, c.y + 1.6, 0.3)), aim_to=V((c.x + 0.6, c.y + 1.3, 0.0)), lens=24, fstop=5.0)

# ---------------- 6. depth: Max hops inside the finished hole, only his head pops out ----------------
b, e = B["depth"]
show(rod, b, B["gravel"][0])
inside = V((c.x + 0.45, c.y + hw - 0.45, FLOOR))       # against the far wall, the rod beside him
cam6 = (c.x + 0.3, c.y - hw - 0.9, 1.05)
max_.cut_place(b, inside, cam_face(inside, cam6))
max_.pose(b)
max_.hop(b + 10, e - 4, height=0.3, period=18)
max_.brows(b + 8, 0.8)
max_.smile(b + 12, big=True)
max_.brows(e - 2, 0.0)
exc.drive(b + 6, b + 70, V((9.0, EXC_Y, 0)))
toy.hide_tree(exc.root, 1, False)
toy.hide_tree(exc.root, b + 72, True)
exc.run_engine(B["dig"][0] - 10, b + 70)
shot(b, e, cam_from=cam6, cam_to=(c.x + 0.2, c.y - hw - 0.6, 0.95),
     aim_from=V((c.x + 0.1, c.y + hw - 0.3, -0.75)), lens=24, fstop=5.0)

# ---------------- 7. gravel: Lily rakes the base flat ----------------
b, e = B["gravel"]
yard.haul_away(b)
yard.gravel(b + 2, e - 10)
lily_spot = V((c.x - 0.9, c.y + 0.2, GRAVEL_TOP))
lily.cut_place(b, lily_spot, facing_to(lily_spot, (c.x + 2, c.y - 0.5, 0)))
toy.hide_tree(lily.root, b, False)
show(lily_rake, b, e)
lily.rake(b + 4, e - 2)
lily.auto_blink(b, e, seed=3)
north = V((c.x + 1.0, c.y + hw + 0.5, 0))
max_.cut_place(b, north, facing_to(north, c))
max_.pose(b)
max_.look_at(b + 4, V((c.x - 0.6, c.y + 0.2, -1.4)), hold=e - b - 8)
shot(b, e, cam_from=(c.x + 1.2, c.y - 2.6, 4.2), cam_to=(c.x + 0.8, c.y - 2.0, 3.8),
     aim_from=c + V((-0.2, 0.2, -1.4)), lens=26, fstop=5.0)

# ---------------- 8. pipes ----------------
b, e = B["pipes"]
toy.hide_tree(lily.root, b, True)
max_.brows(b, 0.0)
east_rim = V((c.x + hl + 0.45, c.y + 0.4, 0))
max_.cut_place(b, east_rim, facing_to(east_rim, c))
max_.pose(b)
max_.point(b + 6, e - 4, hand="R", up_deg=35, side_deg=-10)
yard.plumbing(b + 4, e - 6)
shot(b, e, cam_from=(c.x + 0.6, c.y - 2.6, 5.8), cam_to=(c.x + 0.3, c.y - 2.0, 5.3),
     aim_from=c + V((0.3, 0, -PIT_DEPTH + 0.2)), lens=24, fstop=5.6)

# ---------------- 9. rebar (Lily ties bars inside the pit) ----------------
b, e = B["rebar"]
yard.rebar(b + 2, e - 4)
lily_spot = V((c.x - 1.0, c.y + 0.3, GRAVEL_TOP))
lily.cut_place(b, lily_spot, facing_to(lily_spot, (c.x + 2, c.y - 3, 0)))
toy.hide_tree(lily.root, b, False)
lily.hammer(b + 4, e - 4, hand="R")
lily.auto_blink(b, e, seed=5)
max_.cut_place(b, V((c.x + 1.4, c.y - hw - 0.5, 0)), facing_to((c.x + 1.4, c.y - hw - 0.5, 0), c))
max_.pose(b)
max_.cheer(e - 24, e)
shot(b, e, cam_from=(c.x - 3.8, c.y - 2.4, 3.6), cam_to=(c.x - 3.1, c.y - 1.9, 3.1),
     aim_from=c + V((0.3, 0, -1.1)), lens=24, fstop=5.0)

# ---------------- 10. shotcrete ----------------
b, e = B["shotcrete"]
toy.hide_tree(lily.root, b, True)
toy.hide_tree(gun, b, False)
max_.cut_place(b, RIM_S, facing_to(RIM_S, c))
max_.pose(b + 4, shoulderL=(-70, 0, 8), shoulderR=(-60, 0, -20), spine=(18, 0, 0))
max_.pose(e - 2, shoulderL=(-70, 0, -8), shoulderR=(-60, 0, -30), spine=(18, 0, -6))
concrete = Spray("concrete", toy.material("wet_concrete", toy.srgb("#5E5D59"), roughness=0.3), count=46, radius=0.05)
concrete.run(b + 6, e - 2, source=RIM_S + V((0.15, 0.55, 1.0)), target=c + V((0, 0.6, -0.9)),
             spread=0.9, arc=0.25, sound="spray")
yard.spray_concrete(b + 6, e - 4)
shot(b, e, cam_from=(c.x - 3.6, c.y - 3.4, 1.7), cam_to=(c.x - 3.0, c.y - 3.0, 2.2),
     aim_from=RIM_S + V((0.7, 0.9, 0.2)), lens=24, fstop=3.5)

# ---------------- 11. cure: day/night time-lapse; every morning Max wets the shell ----------------
b, e = B["cure"]
max_.cut_place(b, RIM_S, facing_to(RIM_S, c))
toy.hide_tree(gun, e, True)
AWAKE = dict(shoulderL=(-60, 0, 0), spine=(10, 0, 0))
ASLEEP = dict(shoulderL=(-15, 0, 0), spine=(22, 0, 8), head=(38, 0, 12), shoulderR=(-5, 0, 0))
cure_seg = (e - b) / 8
max_.pose(b + 2, **AWAKE)
z_mat = toy.material("snore_z", (1, 1, 1), roughness=0.5)
cam_cure = V((c.x + 4.8, c.y - 6.6, 3.0))
for night, nk in enumerate((2, 6)):
    n0, n1 = b + int(cure_seg * (nk - 0.6)), b + int(cure_seg * (nk + 1.2))
    max_.pose(n0, **AWAKE)
    max_.pose(n0 + 8, **ASLEEP)
    max_.pose(n1 - 6, **ASLEEP)
    max_.pose(n1, **AWAKE)                     # snaps awake
    max_.brows(n1 - 2, 0.0)
    max_.brows(n1, 1.0)
    max_.brows(n1 + 12, 0.0)
    events.add(n0 + 8, "snore", duration=n1 - n0 - 14, gain=0.8)
    events.add(n1, "boing", gain=0.6)
    for k in range(3):                         # three Zs drift up from his head
        zc = bpy.data.curves.new(f"z{night}{k}", "FONT")
        zc.body = "Z"
        zc.size = 0.22 + 0.06 * k
        zc.extrude = 0.015
        zc.align_x, zc.align_y = "CENTER", "CENTER"
        z = bpy.data.objects.new(f"z{night}{k}", zc)
        bpy.context.scene.collection.objects.link(z)
        z.data.materials.append(z_mat)
        z.rotation_euler = (math.radians(90), 0, math.radians(facing_to(RIM_S, cam_cure)))
        f0 = n0 + 12 + k * 7
        base = RIM_S + V((0.15, 0.0, 1.9))
        for f, off, sc in ((f0, V((0, 0, 0)), 0.2), (f0 + 10, V((0.15, 0, 0.3 + 0.2 * k)), 1.0),
                           (n1 - 4, V((0.35, 0, 0.6 + 0.25 * k)), 1.0),
                           (n1 - 1, V((0.4, 0, 0.7 + 0.25 * k)), 0.01)):
            z.location, z.scale = base + off, (sc, sc, sc)
            z.keyframe_insert("location", frame=f)
            z.keyframe_insert("scale", frame=f)
        toy.hide_tree(z, 1, True)
        show(z, f0, n1)
max_.pose(e - 4, **AWAKE)
show(watch, b, e)
watch_hand.keyframe_insert("rotation_euler", frame=b)
watch_hand.rotation_euler.z -= math.radians(360 * 4)
watch_hand.keyframe_insert("rotation_euler", frame=e)
toy.set_interpolation(watch_hand, "rotation_euler", (b,), "LINEAR")
events.add(b, "tick", duration=e - b)
bg = bpy.context.scene.world.node_tree.nodes["Background"].inputs["Strength"]
days = 2
seg = (e - b) / (days * 4)
for k in range(days * 4 + 1):
    f = b + int(seg * k)
    phase = k % 4                  # day, dusk, night, dawn
    sun.data.energy = (4.8, 1.2, 0.0, 1.2)[phase]
    sun.data.color = ((1.0, 0.93, 0.82), (1.0, 0.55, 0.3), (0.4, 0.5, 1.0), (1.0, 0.6, 0.4))[phase]
    bg.default_value = (0.16, 0.06, 0.012, 0.06)[phase]
    fill.data.energy = (280, 120, 60, 120)[phase]
    sun.data.keyframe_insert("energy", frame=f)
    sun.data.keyframe_insert("color", frame=f)
    bg.keyframe_insert("default_value", frame=f)
    fill.data.keyframe_insert("energy", frame=f)
    if phase == 0 and k < days * 4:     # morning watering
        mist = Spray(f"cure_water{k}", yard.m["water"], count=16, radius=0.035, seed=20 + k)
        mist.run(f + 1, f + int(seg * 0.9), source=RIM_S + V((0.1, 0.45, 0.95)), target=c + V((0.2, 0.2, -1.0)),
                 spread=0.7, arc=0.3, period=8, sound="pour")
sun.rotation_euler.z = math.radians(30)
sun.keyframe_insert("rotation_euler", frame=b)
sun.rotation_euler.z = math.radians(30 + 360 * days)
sun.keyframe_insert("rotation_euler", frame=e)
sun.rotation_euler.z = math.radians(30)
sun.keyframe_insert("rotation_euler", frame=e + 1)
shot(b, e, cam_from=(c.x + 4.8, c.y - 6.6, 3.0), cam_to=(c.x + 4.2, c.y - 6.0, 2.8),
     aim_from=c + V((0.0, -0.6, 0.4)), lens=26, fstop=4.0)

# ---------------- 12. tiles + coping ----------------
b, e = B["tiles"]
b13, e13 = B["plaster"]
yard.tiles_and_coping(b, e - 4, plaster_start=b13 + 4, plaster_end=e13 - 10)
kneel = V((c.x - 1.4, c.y - hw - 0.4, 0))
max_.cut_place(b, kneel, facing_to(kneel, c))
show(tool, b, e)
max_.crouch(b + 1, e - 2, frames=6, lean=12)
max_.hammer(b + 8, e - 6, hand="R")
shot(b, e, cam_from=(c.x + 3.6, c.y - 2.4, 1.2), cam_to=(c.x + 2.8, c.y - 1.8, 1.0),
     aim_from=c + V((-0.4, -hw, -0.1)), lens=26, fstop=3.2)

# ---------------- 13. plaster (Lily trowels) ----------------
lily_spot = V((c.x + 0.6, c.y + 0.4, -PIT_DEPTH + 0.065))
lily.cut_place(b13, lily_spot, facing_to(lily_spot, (c.x, c.y + 3, 0)))
toy.hide_tree(lily.root, b13, False)
show(lily_trowel, b13, e13)
lily.pose(b13)
lily.sweep(b13 + 2, e13 - 2, hand="R", stroke=10)
max_.cut_place(b13, V((c.x + 1.6, c.y + hw + 0.5, 0)), facing_to((c.x + 1.6, c.y + hw + 0.5, 0), c))
max_.pose(b13 + 2, spine=(15, 0, 0), head=(20, 0, 0))
shot(b13, e13, cam_from=(c.x + 0.4, c.y - 2.0, 4.8), cam_to=(c.x + 0.2, c.y - 1.6, 4.4),
     aim_from=c + V((0, 0, -1.0)), lens=24, fstop=5.0)

# ---------------- 14. fill ----------------
b, e = B["fill"]
toy.hide_tree(lily.root, b, True)
show(gun, b, e)
hose_spot = V((c.x + 1.8, c.y + hw + 0.55, 0))
max_.cut_place(b, hose_spot, facing_to(hose_spot, c))
max_.pose(b + 2, shoulderL=(-60, 0, 0), spine=(10, 0, 0))
max_.pose(e - 2, shoulderL=(-60, 0, 0), spine=(10, 0, 0))
yard.fill_water(b + 6, e + 10, level=WATER)
hose = Spray("waterjet", yard.m["water"], count=34, radius=0.045, seed=9)
hose.run(b + 6, e, source=hose_spot + V((-0.1, -0.45, 0.95)), target=c + V((0.8, 0.3, -0.7)),
         spread=0.25, arc=0.35, period=10, sound="pour")
max_.smile(b + 10, big=True)
shot(b, e, cam_from=(c.x + 3.4, c.y - 3.4, 1.8), cam_to=(c.x + 2.6, c.y - 4.0, 2.5),
     aim_from=c + V((0.6, 0.4, -0.6)), lens=26, fstop=4.0)

# ---------------- 15. pump ----------------
b, e = B["pump"]
yard.run_pump(b, total)
pump_spot = V((4.4, 3.7, 0))          # beside the pad, not between it and the camera
max_.cut_place(b, pump_spot, facing_to(pump_spot, (5.6, 2.6, 0)))
max_.pose(b)
max_.point(b + 4, e - 4, hand="L", up_deg=40, side_deg=0)
shot(b, e, cam_from=(3.5, 0.3, 1.3), cam_to=(3.8, 0.7, 1.4), aim_from=(5.2, 2.8, 0.6), lens=30, fstop=2.8)

# ---------------- 16. chemistry: Max tests the water, a chlorine float bobs by ----------------
b, e = B["chemistry"]
floater = chlorinator()
floater.location = (c.x - 1.0, c.y + 0.5, WATER + 0.01)
floater.keyframe_insert("location", frame=1)
floater.location = (c.x - 0.2, c.y + 0.2, WATER + 0.01)
floater.keyframe_insert("location", frame=e)
toy.add_noise(floater, "location", 2, strength=0.012, scale=12, phase=4)
toy.add_noise(floater, "rotation_euler", 0, strength=0.06, scale=15, phase=8)
toy.hide_tree(floater, 1, True)
toy.hide_tree(floater, b, False)
toy.hide_tree(floater, total + 1, False)
test_spot = V((c.x + 0.7, c.y - hw - 0.4, 0))
max_.cut_place(b, test_spot, facing_to(test_spot, c))
show(tube, b, e)
max_.pose(b + 1)
max_.pose(b + 10, spine=(28, 0, 0), head=(20, 0, 0), shoulderR=(-70, 0, 0))   # lean over the edge
max_.pose(b + 30, spine=(28, 0, 0), head=(20, 0, 0), shoulderR=(-70, 0, 0))
max_.pose(b + 42, spine=(4, 0, 0), shoulderR=(-115, 0, -10))
max_.key("shoulderR", b + 1, rot_deg=(0, 0, 0))
max_.key("shoulderR", b + 12, rot_deg=(-70, 0, 0))     # dip the tube...
max_.key("shoulderR", b + 30, rot_deg=(-70, 0, 0))
max_.key("shoulderR", b + 42, rot_deg=(-115, 0, -10))  # ...and hold it up to read the colour
max_.key("shoulderR", e - 4, rot_deg=(-115, 0, -10))
max_.look_at(b + 42, V((test_spot.x - 0.1, test_spot.y - 0.3, 1.0)), hold=e - b - 48)
max_.smile(b + 46, big=True)
shot(b, e, cam_from=(c.x + 1.8, c.y + 1.0, 1.15), cam_to=(c.x + 1.55, c.y + 0.75, 1.05),
     aim_from=test_spot + V((0, 0.25, 0.3)), lens=30, fstop=3.2)

# ---------------- the cannonball (shared by the hook and the finale) ----------------
RUN_FROM = V((c.x + hl + 2.6, c.y, 0))
EDGE = V((c.x + hl + 0.15, c.y, 0))
APEX = V((c.x + hl - 0.7, c.y, 1.25))
SPLASH_AT = V((c.x + hl - 1.05, c.y, WATER))
HOOK_CAM_FROM = (c.x - 0.75, c.y - 0.3, 0.6)      # low over the water: Max flies straight at the lens
TUCK = dict(shoulderL=(-70, 0, -35), shoulderR=(-70, 0, 35), legL=(-85, 0, 0), legR=(-85, 0, 0),
            spine=(15, 0, 0), head=(10, 0, 0))


def cannonball(t0, t_jump, t_apex, t_land=None, run_from=RUN_FROM):
    """Sprint from run_from to the edge, leap into a tuck. With t_land: drop in and splash."""
    face = facing_to(run_from, EDGE)
    max_.cut_place(t0, run_from, face)
    max_.pose(t0)
    max_.walk(t0 + 1, t_jump, to=EDGE, facing_deg=face, step_frames=6)
    max_.brows(t0, 0.9)
    max_.smile(t0, big=True)
    max_.pose(t_jump, spine=(25, 0, 0), legL=(-30, 0, 0), legR=(-30, 0, 0),
              shoulderL=(40, 0, 0), shoulderR=(40, 0, 0))
    max_.move(t_jump, t_apex, APEX)
    max_.pose(t_jump + 5, **TUCK)
    max_.pose(t_apex, **TUCK)
    events.add(t_jump, "whoosh")
    if t_land:
        max_.move(t_apex, t_land, SPLASH_AT + V((0, 0, -0.85)))
        max_.pose(t_land, **TUCK)
        max_.pose(t_land + 10)
        splash = Spray(f"splash{t_land}", yard.m["water"], count=44, radius=0.065, seed=4)
        splash.run(t_land, t_land + 18, source=SPLASH_AT + V((0, 0, 0.05)), target=SPLASH_AT + V((0, 0, 0.1)),
                   spread=1.3, arc=1.5, period=16)
        events.add(t_land, "splash")
        yard.ripple(t_land, SPLASH_AT)


# ---------------- dive: "Now, where were we? Oh yeah..." (Max to camera) ----------------
b, e = B["dive"]
talk_spot = RUN_FROM
cam_d = (talk_spot.x - 1.3, talk_spot.y - 2.0, 1.45)
max_.cut_place(b, talk_spot, cam_face(talk_spot, cam_d))
max_.pose(b)
max_.lipsync(b, e, env)
SHRUG = dict(shoulderL=(-10, -50, 0), shoulderR=(-10, 50, 0), head=(-4, 14, 0), spine=(0, -4, 0))
max_.pose(b + 6, **SHRUG)                                            # "where were we?"
max_.pose(e - 14, **SHRUG)
max_.pose(e - 4, head=(0, 0, 0))
max_.brows(e - 10, 1.0)
max_.smile(e - 8, big=True)
shot(b, e, cam_from=cam_d, cam_to=(talk_spot.x - 1.1, talk_spot.y - 1.7, 1.4),
     aim_from=talk_spot + V((0, 0, 1.25)), lens=40, fstop=2.2)

# ---------------- cannonball: the payoff, from the hook's angle ----------------
b, e = B["cannonball"]
lily_rim = V((c.x - 0.6, c.y + hw + 0.6, 0))
lily.cut_place(b, lily_rim, facing_to(lily_rim, c))
toy.hide_tree(lily.root, b, False)
lily.pose(b)
lily.cheer(b + 2, e)
t_jump = b + min(26, (e - b) // 3)
cannonball(b, t_jump, t_jump + 9, t_jump + 18)
max_.lipsync(b, t_jump + 6, env)
max_.cheer(t_jump + 30, e)
max_.smile(t_jump + 26, big=True)
shot(b, e, cam_from=HOOK_CAM_FROM, cam_to=(c.x - 1.3, c.y - 0.6, 1.0),
     aim_from=EDGE + V((0, 0, 0.9)), aim_to=SPLASH_AT + V((0, 0, 0.4)), lens=20, fstop=4.0)

# ---------------- hook (epilogue): the finished pool, Max leaps... (freeze + rewind in post) ----------------
h0, h1 = EPI + HOOK_B, EPI + HOOK_E
lily.cut_place(h0, lily_rim, facing_to(lily_rim, c))
toy.hide_tree(lily.root, h0, False)
lily.pose(h0)
lily.cheer(h0 + 2, h1)
apex = h1 - 1
cannonball(h0, apex - 11, apex, run_from=V((c.x + hl + 3.6, c.y, 0)))
shot(h0, h1, cam_from=HOOK_CAM_FROM, cam_to=(c.x - 0.6, c.y - 0.25, 0.65),
     aim_from=EDGE + V((1.6, 0, 0.9)), aim_to=APEX + V((0, 0, 0.05)), lens=20, fstop=4.0)

max_.auto_blink(1, total, seed=11)

# ---------------- render ----------------
for ev in events._events:            # epilogue sounds play under the hook (video frames 1..)
    if ev["frame"] > EPI:
        ev["frame"] -= EPI
    elif 1 < ev["frame"] < BUILD_START:
        ev["frame"] = -1                     # nothing from the build timeline plays under hook/rewind
events._events[:] = [ev for ev in events._events if ev["frame"] > 0]
events.save(os.path.join(out_dir, "events.json"))


def render_frame(f):
    """Video frame → 3D frame: the hook beat is rendered from the epilogue."""
    return f + EPI if HOOK_B <= f <= HOOK_E else f

scene.render.image_settings.file_format = "PNG"
if only_frames:
    for f in only_frames:
        scene.frame_set(render_frame(f))
        scene.render.filepath = os.path.join(out_dir, f"still_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
elif preview:
    for idx, (name, (b, e)) in enumerate(B.items()):
        if name == "rewind":
            continue
        for tag, f in (("a", b + max(2, (e - b) // 8)), ("b", (b + e) // 2), ("c", e - max(2, (e - b) // 8))):
            scene.frame_set(render_frame(f))
            scene.render.filepath = os.path.join(out_dir, f"preview_{idx + 1:02d}_{name}_{tag}.png")
            bpy.ops.render.render(write_still=True)
else:
    frames_dir = os.path.join(out_dir, "frames")
    for f in range(HOOK_B, HOOK_E + 1):        # hook from the epilogue, saved under its video frame
        scene.frame_set(f + EPI)
        scene.render.filepath = os.path.join(frames_dir, f"f_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
    scene.frame_start, scene.frame_end = BUILD_START, total
    scene.render.filepath = os.path.join(frames_dir, "f_")
    bpy.ops.render.render(animation=True)
print("DONE")
