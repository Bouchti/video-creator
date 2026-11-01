"""
"Where your toilet water goes" (runs inside Blender, started by engine/make_film.py):

  blender --background --factory-startup --python engine/films/flush_journey_film.py -- FILM.json TIMINGS.json OUT_DIR
          [--preview] [--frames=F1,F2,...] [--ranges=A:B,...] [--range=A:B]

Each beat's id names a shot method of engine/flush/film.Film; the beat's span comes from the voiceover.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

from engine import events  # noqa: E402
from engine.director import lib  # noqa: E402
from engine.flush.film import Film  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
film = json.load(open(args[0], encoding="utf-8"))
timings = json.load(open(args[1], encoding="utf-8"))
out_dir = os.path.abspath(args[2])
preview = "--preview" in args
only_frames = [int(x) for a in args if a.startswith("--frames=") for x in a.split("=", 1)[1].split(",") if x]
only_beats = {x for a in args if a.startswith("--beats=") for x in a.split("=", 1)[1].split(",") if x}
total = timings["total_frames"]
beats = film["beats"]
spans = [(t["start"] + 1, t["end"] + 1) for t in timings["beats"]]

scene = lib.reset(fps=30, preview=False, look="agx")
scene.render.resolution_percentage = int(os.getenv("CUT_PCT", "100"))
scene.eevee.taa_render_samples = int(os.getenv("CUT_SAMPLES", "48"))
scene.eevee.use_raytracing = os.getenv("CUT_RT", "1") == "1"
if os.getenv("CUT_ENGINE", "eevee").lower() == "cycles":
    # path traced (GPU, denoised): soft global light and real refractive water, like the reference
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
            if any(d.type == kind for d in prefs.devices):
                break
        except TypeError:
            continue
    for d in prefs.devices:
        d.use = d.type != "CPU"
    cy = scene.cycles
    cy.device = "GPU"
    # measured on the RTX 4070 laptop: 24 samples + a 0.05 noise threshold + the GPU denoiser gives the same
    # picture as 64 samples in well under half the time; the bounce caps only need to clear the deepest water
    cy.samples = int(os.getenv("CUT_SAMPLES", "24"))
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = float(os.getenv("CUT_THRESHOLD", "0.05"))
    cy.use_denoising = True
    cy.denoiser = os.getenv("CUT_DENOISER") or ("OPTIX" if prefs.compute_device_type == "OPTIX" else "OPENIMAGEDENOISE")
    cy.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    cy.max_bounces, cy.diffuse_bounces, cy.glossy_bounces = 12, 2, 2
    cy.transmission_bounces, cy.transparent_max_bounces, cy.volume_bounces = 12, 16, 0
    cy.caustics_reflective = cy.caustics_refractive = False
    cy.blur_glossy = 1.0
    scene.render.use_persistent_data = True
if os.getenv("CUT_RESUME") == "1":          # keep frames already on disk (a stopped render picks up where it was)
    scene.render.use_overwrite = False
scene.frame_start, scene.frame_end = 1, total
scene.view_settings.exposure = float(os.getenv("CUT_EXPOSURE", "0.1"))
lib.hdri_world(lib.hdri("kloofendal_48d"), strength=0.9, rotation_deg=140)
lib.sun(rotation=(54, 0, 28), strength=3.2, color=(1.0, 0.95, 0.86), angle_deg=3.0)
cam = lib.Camera(lens=35, fstop=4.0)

stage = Film(scene, cam, total)
needed = {b["station"] for b in beats}
for key in ("house", "clog", "trench", "street", "lift", "plant", "macro", "river"):
    if key in needed and hasattr(stage, f"build_{key}"):
        getattr(stage, f"build_{key}")()
for i, b in enumerate(beats):
    fn = getattr(stage, b["id"], None)
    if fn is None:
        print(f"WARNING: no shot for beat {b['id']}")
        continue
    fn(*spans[i])
stage.finish()
events.save(os.path.join(out_dir, "events.json"))

scene.render.image_settings.file_format = "PNG"


def _animated_visibility(ob):
    return any(fc.data_path == "hide_render" for fc in lib.fcurves(ob))


def isolate(frame):
    """Render only the station on screen at `frame` (the others leave memory and the BVH)."""
    idx = next((i for i, (s, e) in enumerate(spans) if s <= frame <= e), len(spans) - 1)
    key = beats[idx]["station"]
    for k, root in stage.roots.items():
        for ob in [root] + list(root.children_recursive):
            if not _animated_visibility(ob):
                ob.hide_render = k != key


def beat_ranges(a, b):
    """[a, b] split at beat boundaries, so each piece renders with one station isolated."""
    out = []
    for s, e in spans:
        lo, hi = max(a, s), min(b, e)
        if lo <= hi:
            out.append((lo, hi))
    return out
if os.getenv("CUT_PROBE"):
    exec(open(os.environ["CUT_PROBE"], encoding="utf-8").read())
elif only_frames:
    for f in only_frames:
        isolate(f)
        scene.frame_set(f)
        scene.render.filepath = os.path.join(out_dir, f"still_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
elif preview:
    for idx, b in enumerate(beats):
        if only_beats and b["id"] not in only_beats and str(idx + 1) not in only_beats:
            continue
        s, e = spans[idx]
        for tag, f in (("a", s + max(2, (e - s) // 8)), ("b", (s + e) // 2), ("c", e - max(2, (e - s) // 8))):
            isolate(f)
            scene.frame_set(f)
            scene.render.filepath = os.path.join(out_dir, f"preview_{idx + 1:02d}_{b['id']}_{tag}.png")
            bpy.ops.render.render(write_still=True)
else:
    frames_dir = os.path.join(out_dir, "frames")
    rng = next((a.split("=", 1)[1] for a in args if a.startswith("--range=")), None)
    many = next((a.split("=", 1)[1] for a in args if a.startswith("--ranges=")), None)
    parts = many.split(",") if many else [rng or f"1:{total}"]
    for part in parts:
        a_, b_ = (int(x) for x in part.split(":"))
        for lo, hi in beat_ranges(a_, b_):
            isolate(lo)
            scene.frame_start, scene.frame_end = lo, hi
            scene.render.filepath = os.path.join(frames_dir, "f_")
            bpy.ops.render.render(animation=True)
print("DONE")
