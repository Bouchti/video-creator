"""
"Where your tap water comes from" (runs inside Blender, started by engine/make_film.py):

  blender --background --factory-startup --python engine/films/tap_water_film.py -- FILM.json TIMINGS.json OUT_DIR
          [--preview] [--beats=id,id] [--frames=F1,F2,...] [--ranges=A:B,...] [--range=A:B]

TIMINGS.json may be the word "synthetic": spans then come from the word counts (2.9 words/s), so stills can be
previewed and judged before any voice is made. Each beat's id names a shot method of engine/tap/film.Film.
--beats builds only the stations those beats use (a station being worked on never breaks the others).

Every run also writes OUT_DIR/anchors.json: per frame, the screen position (1080x1920 px) and visibility of each
anchor a beat's callouts or ruler name, for the HyperFrames compositor's pinned labels.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

from engine import events  # noqa: E402
from engine.director import lib  # noqa: E402
from engine.tap import film as tapfilm  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
film = json.load(open(args[0], encoding="utf-8"))
out_dir = os.path.abspath(args[2])
os.makedirs(out_dir, exist_ok=True)
preview = "--preview" in args
only_frames = [int(x) for a in args if a.startswith("--frames=") for x in a.split("=", 1)[1].split(",") if x]
only_beats = {x for a in args if a.startswith("--beats=") for x in a.split("=", 1)[1].split(",") if x}
beats = film["beats"]
if args[1] == "synthetic":
    spans, f = [], 1
    for b in beats:
        n = max(45, int(round(len(b["text"].split()) / 2.9 * 30)) + 8)
        spans.append((f, f + n - 1))
        f += n
    total = f - 1 + int(film.get("tail", 1.0) * 30)
    spans[-1] = (spans[-1][0], total)
else:
    timings = json.load(open(args[1], encoding="utf-8"))
    total = timings["total_frames"]
    spans = [(t["start"] + 1, t["end"] + 1) for t in timings["beats"]]

scene = lib.reset(fps=30, preview=False, look="agx")
scene.render.resolution_percentage = int(os.getenv("CUT_PCT", "100"))
scene.eevee.taa_render_samples = int(os.getenv("CUT_SAMPLES", "48"))
scene.eevee.use_raytracing = os.getenv("CUT_RT", "1") == "1"
if os.getenv("CUT_ENGINE", "eevee").lower() == "cycles":
    # path traced (GPU, denoised): soft global light and real refractive water (settings measured on the flush film)
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
world_bg = lib.hdri_world(lib.hdri("kloofendal_48d"), strength=0.9, rotation_deg=140)
sun = lib.sun(rotation=(54, 0, 28), strength=3.2, color=(1.0, 0.95, 0.86), angle_deg=3.0)
cam = lib.Camera(lens=35, fstop=4.0)

stage = tapfilm.Film(scene, cam, total)
stage.world_bg, stage.sun = world_bg, sun
wanted = [i for i, b in enumerate(beats) if not only_beats or b["id"] in only_beats or str(i + 1) in only_beats]
if only_frames:
    wanted = sorted({i for f in only_frames for i, (s, e) in enumerate(spans) if s <= f <= e})
needed = []
for i in (wanted if (only_beats or only_frames) else range(len(beats))):
    if beats[i]["station"] not in needed:
        needed.append(beats[i]["station"])
tapfilm.load_modules(needed)
for key in needed:
    fn = getattr(stage, f"build_{key}", None)
    if fn is not None:
        fn()
for i, b in enumerate(beats):
    if b["station"] not in needed:
        continue
    fn = getattr(stage, b["id"], None)
    if fn is None:
        print(f"WARNING: no shot for beat {b['id']}")
        continue
    fn(*spans[i])
stage.finish()
events.save(os.path.join(out_dir, "events.json"))
json.dump({"total_frames": total, "spans": spans, "beats": [b["id"] for b in beats]},
          open(os.path.join(out_dir, "spans.json"), "w", encoding="utf-8"))

scene.render.image_settings.file_format = "PNG"


def _animated_visibility(ob):
    return any(fc.data_path == "hide_render" for fc in lib.fcurves(ob))


def beat_of(frame):
    return next((i for i, (s, e) in enumerate(spans) if s <= frame <= e), len(spans) - 1)


def isolate(frame):
    """Render only the station on screen at `frame` (the others leave memory and the BVH)."""
    key = beats[beat_of(frame)]["station"]
    for k, root in stage.roots.items():
        for ob in [root] + list(root.children_recursive):
            if not _animated_visibility(ob):
                ob.hide_render = k != key
                ob.hide_viewport = k != key


def beat_ranges(a, b):
    """[a, b] split at beat boundaries, so each piece renders with one station isolated."""
    out = []
    for s, e in spans:
        lo, hi = max(a, s), min(b, e)
        if lo <= hi:
            out.append((lo, hi))
    return out


# ---------------------------------------------------------------- anchors for the compositor

def anchor_names(i):
    b = beats[i]
    names = [c["anchor"] for c in b.get("callouts", [])]
    names += list((b.get("stat") or {}).get("ruler", []))
    return [n for n in names if n in stage.anchors.points]


ANCHORS = os.path.join(out_dir, "anchors.json")


def export_anchors(frames):
    from cutaway.blender.anchors import sample
    data = {"fps": 30, "width": 1080, "height": 1920, "frames": {}}
    if os.path.exists(ANCHORS):
        try:
            data = json.load(open(ANCHORS, encoding="utf-8"))
        except (OSError, ValueError):
            pass
    missing = set()
    for f in frames:
        i = beat_of(f)
        names = anchor_names(i)
        want = [c["anchor"] for c in beats[i].get("callouts", [])] + list((beats[i].get("stat") or {}).get("ruler", []))
        missing |= set(want) - set(names)
        if not names:
            continue
        isolate(f)
        scene.frame_set(f)
        data["frames"][str(f)] = sample(names, stage.anchors.points)
    for n in sorted(missing):
        print(f"WARNING: anchor '{n}' is named by a callout but no station defines it")
    json.dump(data, open(ANCHORS, "w", encoding="utf-8"))


if os.getenv("CUT_PROBE"):
    exec(open(os.environ["CUT_PROBE"], encoding="utf-8").read())
elif only_frames:
    export_anchors(only_frames)
    for f in only_frames:
        isolate(f)
        scene.frame_set(f)
        scene.render.filepath = os.path.join(out_dir, f"still_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
elif preview:
    for idx in wanted:
        b = beats[idx]
        s, e = spans[idx]
        picks = (("a", s + max(2, (e - s) // 8)), ("b", (s + e) // 2), ("c", e - max(2, (e - s) // 8)))
        export_anchors([f for _, f in picks])
        for tag, f in picks:
            isolate(f)
            scene.frame_set(f)
            scene.render.filepath = os.path.join(out_dir, f"preview_{idx + 1:02d}_{b['id']}_{tag}.png")
            bpy.ops.render.render(write_still=True)
else:
    frames_dir = os.path.join(out_dir, "frames")
    rng = next((a.split("=", 1)[1] for a in args if a.startswith("--range=")), None)
    many = next((a.split("=", 1)[1] for a in args if a.startswith("--ranges=")), None)
    parts = many.split(",") if many else [rng or f"1:{total}"]
    pieces = [p for part in parts for p in beat_ranges(*(int(x) for x in part.split(":")))]
    export_anchors([f for lo, hi in pieces for f in range(lo, hi + 1)])
    for lo, hi in pieces:
        isolate(lo)
        scene.frame_start, scene.frame_end = lo, hi
        scene.render.filepath = os.path.join(frames_dir, "f_")
        bpy.ops.render.render(animation=True)
print("DONE")
