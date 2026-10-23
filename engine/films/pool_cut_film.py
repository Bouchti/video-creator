"""
"How a swimming pool is built" — CUTAWAY edition (no characters), runs inside Blender:

  blender --background --factory-startup --python engine/films/pool_cut_film.py -- FILM.json TIMINGS.json OUT_DIR
          [--preview] [--frames=F1,F2,...]

One continuous gliding camera in front of a section cut through the pool's long axis.
The hook ("an empty pool can float out of the ground") is rendered from the EPILOGUE (after
the film's end, pool finished) and placed first by make_film; the rewind beat is a post montage.
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
from engine.backyard import _hide, _key  # noqa: E402
from engine.camera import CameraRig  # noqa: E402
from engine.cutaway import (CutawayYard, CUT, POOL_L, POOL_HALF_W, HOLE, SHELL, GRAVEL, FLOOR_TOP,  # noqa: E402
                            WATER_TABLE)
from engine.machines import Excavator, Spray  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
film = json.load(open(args[0], encoding="utf-8"))
timings = json.load(open(args[1], encoding="utf-8"))
out_dir = args[2]
preview = "--preview" in args
only_frames = [int(x) for a in args if a.startswith("--frames=") for x in a.split("=", 1)[1].split(",") if x]
total = timings["total_frames"]
B = {b["id"]: (t["start"] + 1, t["end"] + 1) for b, t in zip(film["beats"], timings["beats"])}
HOOK_B, HOOK_E = B["hook"]
EPI = total
BUILD_START = B["dig"][0]

scene = toy.reset_scene()
scene.frame_start, scene.frame_end = 1, total + 400
# Semi-realistic grade: AgX (filmic highlight roll-off) with the punchy look, more AA samples.
vs = scene.view_settings
try:
    vs.view_transform = "AgX"
    for look in ("AgX - Punchy", "Punchy"):
        try:
            vs.look = look
            break
        except TypeError:
            continue
    vs.exposure = 0.15
except TypeError:
    pass
if hasattr(scene.eevee, "taa_render_samples"):
    scene.eevee.taa_render_samples = int(os.getenv("CUT_SAMPLES", "48"))
# Ray tracing costs ~12 s/frame here (~5x) for a near-identical image: off unless CUT_RT=1.
scene.eevee.use_raytracing = bool(os.getenv("CUT_RT"))
if os.getenv("CUT_NO_MB"):
    scene.render.use_motion_blur = False
toy.setup_world(sun_elevation_deg=42, sun_rotation_deg=190, strength=0.22)
sun = toy.add_sun(rotation_deg=(52, 0, 22), strength=4.2, angle_deg=2)
fill = toy.add_area("Fill", (0, -12, 4), (0, 0, -1.2), energy=900, size=12)
toy.add_area("Rim", (-6, 14, 7), (0, 2, 0), energy=300, size=8, color=(1.0, 0.92, 0.8))

yard = CutawayYard()
hl, back = POOL_L / 2, CUT + POOL_HALF_W
rig = CameraRig(blend=18)
V = Vector

# ---------------- dig + layers: the excavator works from behind the cut ----------------
b, e = B["dig"]
lb, le = B["layers"]
EXC_Y, EXC_YAW = back + 1.9, -90
exc = Excavator(location=(10.0, EXC_Y, 0), facing_deg=EXC_YAW)
stations = [V((col["x"], EXC_Y, 0)) for col in yard.columns]
start = b + 24
span = le - 10 - start
order = yard.dig_plan(2 if span >= 8 * 30 else 1)
cycle = min(52, span // len(order))
exc.rest(b)
exc.drive(b, start - 2, stations[order[0][0]])
exc.rest(start - 2)
tops = [col["top"] for col in yard.columns]
bites = []
for i, new_top in order:
    bites.append({"root": stations[i], "target": V((yard.columns[i]["x"], CUT + 0.55, tops[i]))})
    tops[i] = new_top
PILE = V((5.6, back + 2.9, 0))
timing = exc.dig_sequence(start, bites, dump_at=PILE + V((0, 0, 0.5)), yaw_deg=EXC_YAW, cycle=cycle)
for (i, new_top), t in zip(order, timing):
    yard.bite(i, t["bite"], t["curl"], new_top)
yard.spoil_pile(PILE, [t["dump"] for t in timing])
rig.shot(b, e, cam_from=(-0.6, -7.4, 0.6), cam_to=(0.5, -7.0, 0.4), aim_from=(0.2, 1.4, -0.8),
         aim_to=(0.4, 1.2, -1.0), lens=20, fstop=8.0)

# layers: glide down the section face, labels pop on each stratum (+ the water table)
lx = -hl - 1.3
for k, (txt, z) in enumerate((("TOPSOIL", -0.22), ("CLAY", -1.15), ("SAND", -2.55), ("GROUNDWATER", -3.9))):
    yard.label3d(txt, (lx, z), lb + 6 + k * int((le - lb - 20) / 4), le, size=0.2, tilt=-5 + 4 * (k % 2))
rig.shot(lb, le, cam_from=(lx + 1.2, -4.6, 0.1), cam_to=(lx + 1.0, -4.4, -3.0), aim_from=(lx, 0, -0.5),
         aim_to=(lx, 0, -3.4), lens=30, fstop=8.0)

# ---------------- gravel ----------------
b, e = B["gravel"]
exc.drive(b + 4, b + 60, V((12.0, EXC_Y, 0)))
exc.run_engine(B["dig"][0] - 10, b + 60)
toy.hide_tree(exc.root, 1, False)
toy.hide_tree(exc.root, b + 62, True)
yard.gravel(b + 4, e - 10)
rig.shot(b, e, cam_from=(0.6, -5.2, -0.4), cam_to=(0.3, -4.5, -0.8), aim_from=(0, 0.6, -1.6),
         aim_to=(0, 0.6, -1.7), lens=28, fstop=8.0)

# ---------------- relief valve ----------------
b, e = B["valve"]
_hide(yard.pile, b, True)                         # spoil trucked away
VALVE_X = -1.5
yard.relief_valve(VALVE_X, b + 6)
yard.label3d("RELIEF VALVE", (VALVE_X + 0.15, -1.05), b + 12, e, size=0.13, tilt=-7)
yard.arrows("gw_up", [(VALVE_X, -2.7), (VALVE_X, -2.25)], 1, b + int((e - b) * 0.45), e, size=0.2)
rig.shot(b, e, cam_from=(VALVE_X + 0.4, -2.7, -1.25), cam_to=(VALVE_X + 0.2, -2.3, -1.45),
         aim_from=(VALVE_X, 0, -1.75), aim_to=(VALVE_X, 0, -1.9), lens=30, fstop=8.0)

# ---------------- pipes ----------------
b, e = B["pipes"]
PAD_X = 5.6
for o in yard.equipment_pad(PAD_X):
    toy.hide_tree(o, 1, True)
    toy.hide_tree(o, b, False)
for name in ("filter_dome",):
    toy.hide_tree(bpy.data.objects[name], 1, True)
    toy.hide_tree(bpy.data.objects[name], b, False)
PUMP = (PAD_X - 0.45, 0.32)
FILTER = (PAD_X + 0.45, 0.2)
Z_MAIN, Z_RET = -2.25, -2.6
q = (e - b - 12) // 4
yard.pipe("drain", [(0, FLOOR_TOP), (0, Z_MAIN), (PUMP[0], Z_MAIN), PUMP], b + 4, b + 4 + q)
yard.pipe("skim", [(hl - SHELL - 0.1, -0.2), (hl + 0.35, -0.2), (hl + 0.35, Z_MAIN + 0.06)], b + 4 + q, b + 4 + 2 * q)
yard.pipe("link", [(PUMP[0] + 0.2, PUMP[1]), (FILTER[0] - 0.3, PUMP[1])], b + 4 + 2 * q, b + 6 + 2 * q)
yard.pipe("ret", [(FILTER[0], 0.12), (FILTER[0], Z_RET), (-hl - 0.4, Z_RET), (-hl - 0.4, -0.6),
                  (-hl + SHELL + 0.08, -0.6)], b + 6 + 2 * q, b + 4 + 3 * q)
drain_mat = toy.material("drain_grate", toy.srgb("#2D3238"), roughness=0.4, metallic=0.5)
grate = toy.box("drain_grate", (0.32, 0.06, 0.04), (0, CUT - 0.05, FLOOR_TOP + 0.03), mat=drain_mat, bevel=0.005)
toy.parent_keep(grate, yard.pool_root)
toy.hide_tree(grate, 1, True)
toy.hide_tree(grate, b + 4, False)
yard.label3d("MAIN DRAIN", (0.0, -1.1), b + 8, b + int((e - b) * 0.55), size=0.18, tilt=-6)
yard.label3d("SKIMMER", (hl - 0.5, 0.4), b + int((e - b) * 0.4), e, size=0.2, tilt=5)
rig.shot(b, e, cam_from=(0.2, -4.0, -1.4), cam_to=(3.6, -5.2, -0.5), aim_from=(0, 0, -1.9),
         aim_to=(4.4, 0, -0.6), lens=26, fstop=8.0)

# ---------------- rebar ----------------
b, e = B["rebar"]
bars = yard.rebar(b + 2, e - 8)
xs = sorted({round(o.location.x, 3) for o in bars if o.name.startswith("rb_fy")})
mid = len(xs) // 2
zf = -HOLE + GRAVEL + SHELL / 2
yard.dimension((xs[mid], zf + 0.28), (xs[mid + 1], zf + 0.28), "25 cm", b + int((e - b) * 0.5), e, size=0.09)
rig.shot(b, e, cam_from=(2.2, -3.4, -0.6), cam_to=(xs[mid] + 0.3, -2.2, -1.1), aim_from=(1.0, 0.6, -1.4),
         aim_to=(xs[mid] + 0.1, 0.2, -1.5), lens=26, fstop=8.0)

# ---------------- shotcrete ----------------
b, e = B["shotcrete"]
yard.shotcrete(b + 4, e - 10)
gun = Spray("shotcrete", toy.material("wet_concrete", toy.srgb("#6E6D69"), roughness=0.3), count=40, radius=0.035)
gun.run(b + 4, e - 8, source=(1.9, 0.8, 0.55), target=(hl - 0.35, 0.8, -0.8), spread=0.45, arc=0.15, sound="spray")
yard.dimension((hl - SHELL, -0.75), (hl, -0.75), "20 cm", b + int((e - b) * 0.55), e, size=0.08)
rig.shot(b, e, cam_from=(3.9, -3.6, -0.2), cam_to=(3.3, -2.3, -0.55), aim_from=(2.7, 0.3, -0.8),
         aim_to=(hl - 0.1, 0.1, -0.8), lens=28, fstop=8.0)

# ---------------- cure: day/night time-lapse ----------------
b, e = B["cure"]
bg = bpy.context.scene.world.node_tree.nodes["Background"].inputs["Strength"]
days = 2
seg = (e - b) / (days * 4)
for k in range(days * 4 + 1):
    f = b + int(seg * k)
    phase = k % 4
    sun.data.energy = (4.2, 1.2, 0.0, 1.2)[phase]
    sun.data.color = ((1.0, 0.95, 0.86), (1.0, 0.55, 0.3), (0.4, 0.5, 1.0), (1.0, 0.6, 0.4))[phase]
    bg.default_value = (0.22, 0.07, 0.012, 0.07)[phase]
    fill.data.energy = (900, 350, 160, 350)[phase]
    for d, path in ((sun.data, "energy"), (sun.data, "color"), (fill.data, "energy")):
        d.keyframe_insert(path, frame=f)
    bg.keyframe_insert("default_value", frame=f)
    if phase == 0 and k < days * 4:
        mist = Spray(f"cure_mist{k}", yard.m["water"], count=18, radius=0.03, seed=20 + k)
        mist.run(f + 1, f + int(seg * 0.9), source=(-hl - 0.6, 0.7, 1.2), target=(0, 0.7, -1.2),
                 spread=1.4, arc=0.5, period=10, sound="pour")
rig.shot(b, e, cam_from=(0, -7.4, 0.4), cam_to=(0, -7.1, 0.3), aim_from=(0, 0.8, -0.9), lens=20, fstop=8.0)

# ---------------- finish: tiles, coping, plaster ----------------
b, e = B["finish"]
yard.finish(b + 2, e - 8)
yard.ladder(b + int((e - b) * 0.6))
yard.label3d("PLASTER", (-1.2, FLOOR_TOP + 0.3), b + int((e - b) * 0.6), e, size=0.17, tilt=-6)
rig.shot(b, e, cam_from=(-2.6, -2.9, 0.35), cam_to=(1.6, -2.9, 0.1), aim_from=(-2.5, 0.6, -0.4),
         aim_to=(-0.8, 0.4, -1.3), lens=26, fstop=8.0)

# ---------------- fill ----------------
b, e = B["fill"]
yard.water(b + 4, e + 10)
hose = Spray("fill_hose", yard.m["water"], count=30, radius=0.03, seed=9)
hose.run(b + 4, e, source=(hl - 0.15, back - 0.3, 0.35), target=(hl - 1.2, back - 0.6, -0.9),
         spread=0.18, arc=0.25, period=9)
rig.shot(b, e, cam_from=(0, -6.8, -0.1), cam_to=(0, -6.0, -0.3), aim_from=(0, 0.6, -0.95), lens=20, fstop=8.0)

# ---------------- weight vs groundwater ----------------
b, e = B["weight"]
yard.arrows("weight_dn", [(-1.6, -0.75), (0, -0.75), (1.6, -0.75)], -1, b + 6, e, color="#FFD23F", size=0.3)
yard.arrows("gw_push", [(-1.6, -2.7), (0, -2.7), (1.6, -2.7)], 1, b + 22, e, color="#5EC8FF", size=0.24)
rig.shot(b, e, cam_from=(0, -6.6, -1.0), cam_to=(0, -7.6, -1.2), aim_from=(0, 0, -1.6), lens=20, fstop=8.0)

# ---------------- flow: skimmer/drain → pump → filter → jets ----------------
b, e = B["flow"]
yard.start_flow(b + 4)
yard.label3d("PUMP", (PUMP[0], 1.0), b + int((e - b) * 0.45), e, size=0.24, tilt=-6)
yard.label3d("FILTER", (FILTER[0] + 0.1, 1.6), b + int((e - b) * 0.55), e, size=0.24, tilt=6)
events.add(b + 4, "pump", duration=total - b)
rig.shot(b, e, cam_from=(-0.3, -4.0, -1.5), cam_to=(4.6, -4.6, -0.2), aim_from=(0, 0, -2.0),
         aim_to=(PAD_X, 0, 0.0), lens=26, fstop=8.0)

# ---------------- cycle ----------------
b, e = B["cycle"]
rig.shot(b, e, cam_from=(1.6, -5.6, -0.3), cam_to=(0.6, -7.8, 0.0), aim_from=(1.4, 0.5, -1.0),
         aim_to=(0.8, 0.5, -1.1), lens=20, fstop=8.0)

# ---------------- outro: heavy rain → the water table climbs (loops into the hook) ----------------
b, e = B["outro"]
yard.water_table(b, WATER_TABLE)
yard.water_table(e, -2.0)
# Storm rolls in: the light drops, rain falls (and keeps falling into the hook, rendered after).
for f, sun_e, bg_v, fill_e in ((b, 4.2, 0.22, 900), (b + 30, 2.0, 0.09, 520)):
    sun.data.energy = sun_e
    bg.default_value = bg_v
    fill.data.energy = fill_e
    sun.data.keyframe_insert("energy", frame=f)
    bg.keyframe_insert("default_value", frame=f)
    fill.data.keyframe_insert("energy", frame=f)
yard.rain(b + 10, e + 2, seed=5)
HOOK_CAM = dict(cam=(0, -6.4, -0.6), aim=(0, 0, -1.05))
rig.shot(b, e, cam_from=(0, -7.6, -0.7), cam_to=HOOK_CAM["cam"], aim_from=(0, 0, -1.3), aim_to=HOOK_CAM["aim"],
         lens=20, fstop=8.0)

# ---------------- hook (epilogue): drained pool + high groundwater → it floats up ----------------
h0, h1 = EPI + HOOK_B, EPI + HOOK_E
_hide(yard.water_obj, h0, True)
_hide(yard.water_surf, h0, True)
yard.caustics(h0 - 1, -0.15)
yard.caustics(h0, -50)
yard.rain(h0, h1 + 2, seed=6)
yard.water_table(h0, -2.0)
yard.water_table(h1, -0.85)
root = yard.pool_root
root.location = (0, 0, 0)
root.rotation_euler = (0, 0, 0)
root.keyframe_insert("location", frame=h0)
root.keyframe_insert("rotation_euler", frame=h0 + 6)
root.location = (0, 0, 0.5)
root.rotation_euler = (0, math.radians(-2.0), 0)
root.keyframe_insert("location", frame=h1)
root.keyframe_insert("rotation_euler", frame=h1)
events.add(h0 + 8, "dump", gain=0.6)                     # concrete grinding loose
events.add(h0 + 30, "dump", gain=0.5)
yard.arrows("hook_up", [(-1.6, -2.5), (0, -2.5), (1.6, -2.5)], 1, h0 + 4, h1 + 2, size=0.3)
yard.label3d("GROUNDWATER", (0, -3.0), h0 + 8, h1 + 2, size=0.42, tilt=-5)
rig.shot(h0, h1, cam_from=(0, -7.2, -0.7), cam_to=HOOK_CAM["cam"], aim_from=(0, 0, -1.2), aim_to=HOOK_CAM["aim"],
         lens=20, fstop=8.0, cut=True)
rig.build()

# ---------------- render ----------------
for ev in events._events:            # epilogue sounds play under the hook (video frames 1..)
    if ev["frame"] > EPI:
        ev["frame"] -= EPI
    elif 1 < ev["frame"] < BUILD_START:
        ev["frame"] = -1
events._events[:] = [ev for ev in events._events if ev["frame"] > 0]
events.save(os.path.join(out_dir, "events.json"))


def render_frame(f):
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
    for f in range(HOOK_B, HOOK_E + 1):
        scene.frame_set(f + EPI)
        scene.render.filepath = os.path.join(frames_dir, f"f_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
    scene.frame_start, scene.frame_end = BUILD_START, total
    scene.render.filepath = os.path.join(frames_dir, "f_")
    bpy.ops.render.render(animation=True)
print("DONE")
