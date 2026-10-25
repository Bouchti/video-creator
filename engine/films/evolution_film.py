"""
Generic EVOLUTION film: renders any script whose JSON has "format": "evolution" and names a 3D set
with one action per beat (see engine/sets/<set>_spec.py). Unlike cutaway films there is no hook
staged in an epilogue and no rewind: the film plays straight through, problem after problem.
Runs inside Blender:

  blender --background --factory-startup --python engine/films/evolution_film.py -- FILM.json TIMINGS.json OUT_DIR
          [--preview] [--frames=F1,F2,...] [--range=A:B] [--ranges=A:B,C:D]

EVO_ENGINE=CYCLES renders with Cycles (CPU, e.g. on a machine without a GPU); EVO_SAMPLES sets
the sample count; EVO_PCT the resolution percentage; EVO_RT=0 turns off screen-space reflections.
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

scene = toy.reset_scene()
scene.frame_start, scene.frame_end = 1, total
vs = scene.view_settings
try:                                          # natural daylight grade (real-world scale, not a toy)
    vs.view_transform = "AgX"
    for look in ("AgX - Punchy", "Punchy"):
        try:
            vs.look = look
            break
        except TypeError:
            continue
    vs.exposure = 0.1
except TypeError:
    pass
scene.render.resolution_percentage = int(os.getenv("EVO_PCT", "100"))
if os.getenv("EVO_ENGINE", "").upper() == "CYCLES":
    scene.render.engine = "CYCLES"
    scene.cycles.samples = int(os.getenv("EVO_SAMPLES", "24"))
    scene.cycles.use_denoising = True
    scene.render.use_motion_blur = False
else:
    ee = scene.eevee
    ee.taa_render_samples = int(os.getenv("EVO_SAMPLES", "48"))
    rt = os.getenv("EVO_RT", "1") != "0"      # screen-space reflections: the bridges mirrored in the river
    for attr, val in (("use_raytracing", rt), ("ray_tracing_method", "SCREEN"), ("shadow_ray_count", 1),
                      ("use_volumetric_shadows", False)):
        if hasattr(ee, attr):
            try:
                setattr(ee, attr, val)
            except (TypeError, ValueError):
                pass
    opts = getattr(ee, "ray_tracing_options", None)
    if opts is not None and hasattr(opts, "resolution_scale"):
        try:
            opts.resolution_scale = "2"
        except (TypeError, ValueError):
            pass
toy.setup_world(sun_elevation_deg=38, sun_rotation_deg=200, strength=0.6)
sun = toy.add_sun(rotation_deg=(48, 0, 30), strength=4.0, angle_deg=1.5)
fill = toy.add_area("Fill", (0, -400, 200), (0, 0, 0), energy=0, size=1)    # unused at this scale
bg = bpy.context.scene.world.node_tree.nodes["Background"].inputs["Strength"]

set_mod = importlib.import_module(f"engine.sets.{film['set']}")
set_cls = next(v for k, v in vars(set_mod).items()
               if k.endswith("Set") and isinstance(v, type) and v.__module__ == set_mod.__name__)
stage = set_cls(scene, sun, fill, bg, total)
stage.run(beats, spans)
print(f"interpolation: {toy.normalize_interpolation()} inherited keys reset to Bezier")
events.save(os.path.join(out_dir, "events.json"))

scene.render.image_settings.file_format = "PNG"
frames_dir = os.path.join(out_dir, "frames")
if os.getenv("CUT_PROBE"):                    # debugging: run a script against the staged scene, no render
    exec(open(os.environ["CUT_PROBE"], encoding="utf-8").read())
elif only_frames:
    for f in only_frames:
        scene.frame_set(f)
        scene.render.filepath = os.path.join(out_dir, f"still_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
elif preview:
    for idx, b in enumerate(beats):
        s, e = spans[idx]
        for tag, f in (("a", s + max(2, (e - s) // 8)), ("b", (s + e) // 2), ("c", e - max(2, (e - s) // 8))):
            scene.frame_set(f)
            scene.render.filepath = os.path.join(out_dir, f"preview_{idx + 1:02d}_{b.get('id', b['action'])}_{tag}.png")
            bpy.ops.render.render(write_still=True)
else:
    # make_film's parallel workers / --redo pass --range=A:B or --ranges=A:B,C:D; otherwise render it all.
    rng = next((a.split("=", 1)[1] for a in args if a.startswith("--range=")), None)
    many = next((a.split("=", 1)[1] for a in args if a.startswith("--ranges=")), None)
    parts = many.split(",") if many else [rng or f"1:{total}"]
    for part in parts:
        a_, b_ = (int(x) for x in part.split(":"))
        if a_ > b_:
            continue
        scene.frame_start, scene.frame_end = a_, b_
        scene.render.filepath = os.path.join(frames_dir, "f_")
        bpy.ops.render.render(animation=True)
print("DONE")
