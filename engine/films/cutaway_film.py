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
scene.render.resolution_percentage = int(os.getenv("CUT_PCT", "100"))     # QA stills render at 50
# Ray tracing costs ~12 s/frame for a near-identical image: off unless CUT_RT=1.
scene.eevee.use_raytracing = bool(os.getenv("CUT_RT"))
scene.eevee.shadow_ray_count = 1
for _attr, _val in (("volumetric_tile_size", "4"), ("volumetric_samples", 64), ("volumetric_end", 60.0),
                    ("use_volumetric_shadows", False)):
    if hasattr(scene.eevee, _attr):
        setattr(scene.eevee, _attr, _val)                # 48 TAA samples already average soft shadows: same image, 5% faster
toy.setup_world(sun_elevation_deg=42, sun_rotation_deg=190, strength=0.22)
sun = toy.add_sun(rotation_deg=(52, 0, 22), strength=4.2, angle_deg=2)
fill = toy.add_area("Fill", (0, -12, 4), (0, 0, -1.2), energy=900, size=12)
toy.add_area("Rim", (-6, 14, 7), (0, 2, 0), energy=300, size=8, color=(1.0, 0.92, 0.8))
bg = bpy.context.scene.world.node_tree.nodes["Background"].inputs["Strength"]

set_mod = importlib.import_module(f"engine.sets.{film['set']}")
set_cls = next(v for k, v in vars(set_mod).items()
               if k.endswith("Set") and isinstance(v, type) and v.__module__ == set_mod.__name__)
stage = set_cls(scene, sun, fill, bg, total)
stage.run(beats, spans, EPI)
print(f"interpolation: {toy.normalize_interpolation()} inherited keys reset to Bezier")

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
if os.getenv("CUT_PROBE"):                    # debugging: run a script against the staged scene, no render
    exec(open(os.environ["CUT_PROBE"], encoding="utf-8").read())
elif "--qa" in args:
    import time
    from engine import qa
    _t0 = time.time()
    from engine.character import Character
    chars = {}
    for v in vars(stage).values():
        for c in (v if isinstance(v, list) else [v]):
            if isinstance(c, Character):
                chars[c.name] = c.root
    mover = getattr(getattr(stage, "plane", None), "root", None)
    labelled = [(f"{idx + 1:02d}_{b['action']}", *spans[idx]) for idx, b in enumerate(beats) if b["action"] != "rewind"]
    rep = qa.run(scene, chars, mover, labelled, render_frame, step=int(os.getenv("QA_STEP", "3")),
                 out_path=os.path.join(out_dir, "qa.json"))
    for beat, items in rep["beats"].items():
        for it in items:
            print(f"QA {beat} f{it['frames'][0]}-{it['frames'][1]}: {it['issue']}")
    allow = getattr(stage, "QA_ALLOW", None)
    if allow is not None:                       # sets that declare their by-design contacts get the object check
        chars_re = "|".join(chars) or "^$"
        ends = sorted({e for _, _, e in labelled})
        objs = qa.run_objects(scene, ends, allow=allow,
                              skip=rf"^(field|g_|hill|cloud|label_|lbl|Rig|leaf|trunk|{chars_re})|_p\d+$"
                                   r"|(bubbles|steam|plume|leak\d*|dust|wash|leaves)_\d+$")
        for pair, f in sorted(objs.items(), key=lambda kv: kv[1]):
            print(f"QA object f{f}: {pair}")
        rep["count"] += len(objs)
        rep["objects"] = objs
    print(f"QA geometry checks: {time.time() - _t0:.0f} s")
    _t1 = time.time()
    if os.getenv("QA_QUALITY", "1") == "1":     # the channel's quality gates (hero size, motion, textures...)
        spec = importlib.import_module(f"engine.sets.{film['set']}_spec")
        qual = qa.quality(scene, chars, getattr(spec, "HERO", None), labelled, render_frame,
                          step=int(os.getenv("QA_QUALITY_STEP", "5")))
        # the things each action must SHOW (spec ACTIONS[a]["must_see"]), measured where the reviewer looks
        acts_of = getattr(spec, "beat_actions", lambda b: [b["action"]])
        shown = [b for b in beats if b["action"] != "rewind"]
        wanted = [(lbl, b0, b1, [n for a in acts_of(b) for n in spec.ACTIONS.get(a, {}).get("must_see", [])])
                  for (lbl, b0, b1), b in zip(labelled, shown)]
        for lbl, items in qa.must_see(scene, chars, wanted, render_frame).items():
            qual["beats"].setdefault(lbl, []).extend(items)
            qual["count"] += len(items)
        for beat, items in qual["beats"].items():
            for it in items:
                print(f"QA {beat} f{it['frames'][0]}: {it['issue']}")
        rep["quality"] = qual["beats"]
        print(f"QA quality gates: {time.time() - _t1:.0f} s")
        rep["count"] += qual["count"]
    with open(os.path.join(out_dir, "qa.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2)
    print(f"QA issues: {rep['count']}")
elif only_frames:
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
    # Parallel workers (make_film) each render a chunk: --range=A:B of the build frames and/or
    # --hook. Without these flags this process renders everything.
    # --ranges=A:B,C:D re-renders only those frames (make_film --redo); the scene is staged once.
    rng = next((a.split("=", 1)[1] for a in args if a.startswith("--range=")), None)
    many = next((a.split("=", 1)[1] for a in args if a.startswith("--ranges=")), None)
    do_hook = "--hook" in args or (rng is None and many is None)
    a_, b_ = (int(x) for x in rng.split(":")) if rng else (BUILD_START, total)
    if many is not None:
        a_, b_ = 1, 0                                    # handled below
    frames_dir = os.path.join(out_dir, "frames")
    if do_hook:
        # Hook: render the epilogue range as an animation (one still per call re-syncs the whole
        # scene, ~3x slower), then rename each frame to its place at the start of the video.
        scene.frame_start, scene.frame_end = HOOK_B + EPI, HOOK_E + EPI
        scene.render.filepath = os.path.join(frames_dir, "h_")
        bpy.ops.render.render(animation=True)
        for f in range(HOOK_B, HOOK_E + 1):
            os.replace(os.path.join(frames_dir, f"h_{f + EPI:04d}.png"), os.path.join(frames_dir, f"f_{f:04d}.png"))
    if a_ <= b_:
        scene.frame_start, scene.frame_end = a_, b_
        scene.render.filepath = os.path.join(frames_dir, "f_")
        bpy.ops.render.render(animation=True)
    for part in (many.split(",") if many else []):
        a2, b2 = (int(x) for x in part.split(":"))
        scene.frame_start, scene.frame_end = a2, b2
        scene.render.filepath = os.path.join(frames_dir, "f_")
        bpy.ops.render.render(animation=True)
print("DONE")
