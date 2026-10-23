"""
Generic DATA-DRIVEN cutaway film: renders any script whose JSON names a 3D set and one action
per beat (see engine/sets/<set>_spec.py). Runs inside Blender:

  blender --background --factory-startup --python engine/films/cutaway_film.py -- FILM.json TIMINGS.json OUT_DIR
          [--preview] [--frames=F1,F2,...]

Beat 1 (hook) is staged in the EPILOGUE (after the film's end, with the build finished) and
saved as the first video frames; beat 2 (rewind) is a post montage built by make_film.
"""
import importlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

from engine import events, toy  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
film = json.load(open(args[0], encoding="utf-8"))
timings = json.load(open(args[1], encoding="utf-8"))
out_dir = os.path.abspath(args[2])
preview = "--preview" in args
only_frames = [int(x) for a in args if a.startswith("--frames=") for x in a.split("=", 1)[1].split(",") if x]
total = timings["total_frames"]
beats = film["beats"]
spans = {i: (t["start"] + 1, t["end"] + 1) for i, t in enumerate(timings["beats"])}
HOOK_B, HOOK_E = spans[0]
BUILD_START = spans[2][0]
EPI = total                                   # epilogue frame = EPI + hook frame

scene = toy.reset_scene()
scene.frame_start, scene.frame_end = 1, total + 400
vs = scene.view_settings
try:                                          # semi-realistic grade: AgX + punchy look
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
scene.eevee.taa_render_samples = int(os.getenv("CUT_SAMPLES", "48"))
# Ray tracing costs ~12 s/frame for a near-identical image: off unless CUT_RT=1.
scene.eevee.use_raytracing = bool(os.getenv("CUT_RT"))
toy.setup_world(sun_elevation_deg=42, sun_rotation_deg=190, strength=0.22)
sun = toy.add_sun(rotation_deg=(52, 0, 22), strength=4.2, angle_deg=2)
fill = toy.add_area("Fill", (0, -12, 4), (0, 0, -1.2), energy=900, size=12)
toy.add_area("Rim", (-6, 14, 7), (0, 2, 0), energy=300, size=8, color=(1.0, 0.92, 0.8))
bg = bpy.context.scene.world.node_tree.nodes["Background"].inputs["Strength"]

set_mod = importlib.import_module(f"engine.sets.{film['set']}")
set_cls = next(v for k, v in vars(set_mod).items() if k.endswith("Set") and isinstance(v, type))
stage = set_cls(scene, sun, fill, bg, total)
stage.run(beats, spans, EPI)

# ---------------- sound events: epilogue → hook; nothing from the build under hook/rewind ----------------
for ev in events._events:
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
    for idx, b in enumerate(beats):
        if b["action"] == "rewind":
            continue
        s, e = spans[idx]
        for tag, f in (("a", s + max(2, (e - s) // 8)), ("b", (s + e) // 2), ("c", e - max(2, (e - s) // 8))):
            scene.frame_set(render_frame(f))
            scene.render.filepath = os.path.join(out_dir, f"preview_{idx + 1:02d}_{b['action']}_{tag}.png")
            bpy.ops.render.render(write_still=True)
else:
    frames_dir = os.path.join(out_dir, "frames")
    # Hook: render the epilogue range as an animation (one still per call re-syncs the whole
    # scene, ~3x slower), then rename each frame to its place at the start of the video.
    scene.frame_start, scene.frame_end = HOOK_B + EPI, HOOK_E + EPI
    scene.render.filepath = os.path.join(frames_dir, "h_")
    bpy.ops.render.render(animation=True)
    for f in range(HOOK_B, HOOK_E + 1):
        os.replace(os.path.join(frames_dir, f"h_{f + EPI:04d}.png"), os.path.join(frames_dir, f"f_{f:04d}.png"))
    scene.frame_start, scene.frame_end = BUILD_START, total
    scene.render.filepath = os.path.join(frames_dir, "f_")
    bpy.ops.render.render(animation=True)
print("DONE")
