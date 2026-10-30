"""
Inside Blender:  blender -b --factory-startup --python engine/director/blender_job.py -- JOB.json

JOB: {"world": "septic", "timing": {...}, "out": dir, "preview": bool, "stills": [frames] | null}
Writes <out>/anchors.json, then either <out>/still_<frame>.png for each still, or <out>/frames/#####.png.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import bpy  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Vector  # noqa: E402

WORLDS = {"septic": "engine.director.septic:SepticWorld", "stage": "engine.director.stage:StageWorld"}


def measure_actions(world, path):
    """Visibility gate data: for every registered action, the actor's on-screen height (share of the frame)
    and whether its centre is in frame, sampled every 2 frames of the action."""
    scene = bpy.context.scene
    out = []
    for a in getattr(world, "actions", []):
        ob = bpy.data.objects[a["obj"]]
        meshes = [o for o in [ob] + list(ob.children_recursive) if o.type == "MESH"]
        shares, inside = [], []
        for f in range(a["f0"], a["f1"] + 1, 2):
            scene.frame_set(f)
            pts = [world_to_camera_view(scene, scene.camera, o.matrix_world @ Vector(c))
                   for o in meshes for c in o.bound_box]
            pts = [p for p in pts if p.z > 0]
            if not pts:
                shares.append(0.0)
                inside.append(False)
                continue
            ys = [min(1.0, max(0.0, p.y)) for p in pts]
            xs = [p.x for p in pts]
            cx, cy = sum(xs) / len(xs), sum(p.y for p in pts) / len(pts)
            shares.append(max(ys) - min(ys))
            inside.append(0.02 < cx < 0.98 and 0.02 < cy < 0.98)
        shares.sort()
        out.append(dict(a, share=round(shares[len(shares) // 2], 4) if shares else 0.0,
                        visible=round(sum(inside) / max(1, len(inside)), 3)))
    with open(path, "w") as fh:
        json.dump(out, fh, indent=1)


def main():
    job = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
    mod, cls = WORLDS[job["world"]].split(":")
    kw = {"plan": job["plan"]} if job.get("plan") else {}       # data-driven worlds film the plan itself
    world = getattr(__import__(mod, fromlist=[cls]), cls)(job["timing"], preview=job.get("preview", False), **kw)
    world.film()
    for path, value in (job.get("overrides") or {}).items():   # e.g. {"eevee.use_raytracing": false}
        owner, attr = path.rsplit(".", 1)
        setattr(bpy.context.scene.path_resolve(owner), attr, value)
    for ob in bpy.context.scene.objects:          # diagnostics: hide objects by name prefix
        if any(ob.name.startswith(p) for p in job.get("hide", [])):
            ob.hide_render = True
    out = job["out"]
    os.makedirs(out, exist_ok=True)
    scene = bpy.context.scene
    world.anchors.export(os.path.join(out, "anchors.json"), 1, scene.frame_end)
    measure_actions(world, os.path.join(out, "actions.json"))
    with open(os.path.join(out, "camera_notes.json"), "w") as fh:     # moves the camera had to shorten
        json.dump(getattr(world.cam, "notes", []), fh)
    with open(os.path.join(out, "sound_events.json"), "w") as fh:     # footsteps, pops ... where they happen
        json.dump(getattr(world, "sounds", []), fh)
    if job.get("save_blend"):
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "scene.blend"))
    if job.get("stills"):
        for f in job["stills"]:
            scene.frame_set(f)
            scene.render.filepath = os.path.join(out, f"still_{f:05d}.png")
            bpy.ops.render.render(write_still=True)
        return
    if job.get("segments"):            # only the beats that changed, each into its own folder
        scene.render.use_overwrite = False
        scene.render.use_placeholder = True
        for seg in job["segments"]:
            os.makedirs(seg["dir"], exist_ok=True)
            scene.frame_start, scene.frame_end = seg["f0"], seg["f1"]
            scene.render.filepath = os.path.join(seg["dir"], "")
            bpy.ops.render.render(animation=True)
        return
    scene.frame_start = job.get("frame_start", 1)
    scene.frame_end = job.get("frame_end", scene.frame_end)
    scene.render.filepath = os.path.join(out, "frames", "")
    scene.render.use_overwrite = False       # resume: frames already on disk are skipped
    scene.render.use_placeholder = True
    bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()
