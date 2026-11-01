"""
Render one shot (runs inside Blender):

    blender -b --factory-startup -P cutaway/blender/render_shot.py -- job.json

job.json:
  {"assembly": "inline4", "quality": "draft|look|final", "out_dir": "<abs>", "frames": [f0, f1],
   "only": [f, ...] (optional: render just these), "crank": {"keys": [[t, deg], ...]},
   "shot": {"id", "cut": {"state": "closed|sectioned|peeling", "preset", "peel": [t0, t1]},
            "camera": {...}, "anchors": [names]},
   "hdri": "<abs>", "samples": n (optional), "pct": n (optional)}

Frame f shows video time t = (f - 1) / 30. Every frame is a function of t alone (mechanism, camera, cut), so
frames render in any order and a resumed render skips the PNGs already on disk.
Writes <out_dir>/f_####.png and <out_dir>/anchors.json; prints one 'CUTAWAY {json}' line per milestone.
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import bpy  # noqa: E402

from cutaway.blender import anchors as A  # noqa: E402
from cutaway.blender import core, section, studio  # noqa: E402
from cutaway.blender.assemblies import ASSEMBLIES  # noqa: E402
from cutaway.blender.camera import ShotCamera, fit_presets  # noqa: E402

FPS = 30


def say(event, **kw):
    print("CUTAWAY " + json.dumps({"event": event, **kw}), flush=True)


def theta_fn(keys):
    """Crank angle (deg) at time t: piecewise linear through keys, extrapolated at the end speeds."""
    keys = sorted(keys)

    def f(t):
        if len(keys) == 1:
            return keys[0][1]
        if t <= keys[0][0]:
            (t0, a0), (t1, a1) = keys[0], keys[1]
        elif t >= keys[-1][0]:
            (t0, a0), (t1, a1) = keys[-2], keys[-1]
        else:
            for (t0, a0), (t1, a1) in zip(keys, keys[1:]):
                if t0 <= t <= t1:
                    break
        return a0 + (a1 - a0) * (t - t0) / max(1e-9, t1 - t0)
    return f


def pose(asm, theta, t: float):
    """Pose an assembly for time t: crank kits read only the drive angle, flow kits read the time too."""
    if getattr(asm, "TIMED", False):
        asm.pose(theta(t), t)
    else:
        asm.pose(theta(t))


def t_of(frame: int) -> float:
    return (frame - 1) / FPS


def _key_props(o, frame):
    o.keyframe_insert("location", frame=frame)
    if o.rotation_mode == "QUATERNION":
        o.keyframe_insert("rotation_quaternion", frame=frame)
    else:
        o.keyframe_insert("rotation_euler", frame=frame)
    o.keyframe_insert("scale", frame=frame)
    for k in ("gas_color", "gas_density", "gas_glow", "glow", "flame_r", "flame_k", "flow_on"):
        if k in o.keys():
            o.keyframe_insert(f'["{k}"]', frame=frame)
    if o.type == "LIGHT":
        o.data.keyframe_insert("energy", frame=frame)
    if "flow_socket" in o.keys():                         # Geometry Nodes flow phase (rigs/flow.py)
        o.keyframe_insert(f'modifiers["flow"].properties.inputs.{o["flow_socket"]}.value', frame=frame)
    for k in ("plume_phase", "power", "glow_level"):
        if k in o.keys():
            o.keyframe_insert(f'["{k}"]', frame=frame)


def xray(asm) -> dict:
    """See-through castings: every static part but the ones the assembly keeps solid becomes a glowing-edged
    ghost (no shadow, transparent to anchor rays), so the moving parts and the gas read in context."""
    from cutaway.blender import materials as M
    keep = set(asm.xray_solid()) if hasattr(asm, "xray_solid") else set()
    hidden = list(asm.xray_hidden()) if hasattr(asm, "xray_hidden") else []
    ghost = M.ghost()
    done = 0
    for o in hidden:
        o.hide_render = True
    for root in asm.static:
        for o in (root, *root.children_recursive):
            if o in keep or o in hidden or o.type != "MESH":
                continue
            for slot in o.material_slots:
                slot.link = "OBJECT"
                slot.material = ghost
            if not o.material_slots:
                o.data.materials.append(ghost)
            o.visible_shadow = False
            o["no_occlude"] = 1
            done += 1
    return {"ghosted": done}


def main(job_path: str):
    t_start = time.time()
    with open(job_path, encoding="utf-8") as f:
        job = json.load(f)
    shot = job["shot"]
    f0, f1 = job["frames"]
    out_dir = job["out_dir"]
    os.makedirs(out_dir, exist_ok=True)

    core.reset()
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
    sc = core.setup(job.get("quality", "draft"), samples=job.get("samples"), pct=job.get("pct"))
    sc.render.use_persistent_data = True
    sc.frame_start, sc.frame_end = f0, f1

    mod, cls = ASSEMBLIES[job["assembly"]]
    asm = getattr(importlib.import_module(mod), cls)()
    st = asm.STUDIO
    studio.world(job["hdri"], rotation_deg=job.get("hdri_rotation", 0.0))
    cyc = studio.cyclorama(st["floor_z"], **st.get("cyc", {"size": 4, "wall": 4, "radius": 0.8, "back_y": 1.0}))
    rig = studio.lights(st["center"], st["radius"])
    theta = theta_fn(job["crank"]["keys"])
    if hasattr(asm, "set_events"):
        asm.set_events(job.get("events", []))                 # state events (rods, valves, bursts) by time
    say("built", seconds=round(time.time() - t_start, 1))

    # cut state (pose at mid-shot first so moving parts are tested where they are)
    pose(asm, theta, t_of((f0 + f1) // 2))
    cut = shot.get("cut", {"state": "closed"})
    report = {}
    if cut.get("state") == "xray":
        report = xray(asm)
    elif cut.get("state", "closed") != "closed":
        preset = asm.cuts()[cut["preset"]]
        box = section.cutter(preset["bounds"])
        if cut["state"] == "peeling":
            p0, p1 = cut.get("peel", [t_of(f0), t_of(f0) + 1.2])
            axis, dist = preset["peel"]
            report = section.peel(asm.static + asm.fx, asm.moving, box, axis, dist,
                                  (round(p0 * FPS) + 1, round(p1 * FPS) + 1),
                                  cut_moving=preset["cut_moving"], own_cap=preset["own_cap"])
        else:
            report = section.apply(asm.static + asm.fx, asm.moving, box, travel=0.012,
                                   cut_moving=preset["cut_moving"], own_cap=preset["own_cap"])
        lo = [b[0] if b[0] is not None else -section.BIG for b in preset["bounds"]]
        hi = [b[1] if b[1] is not None else section.BIG for b in preset["bounds"]]
        for fl in getattr(asm, "flows", []):
            fl.clip(lo, hi)
    say("cut", state=cut.get("state", "closed"), cut=len(report.get("cut", [])),
        removed=len(report.get("removed", [])))

    # frame the subject in the mechanism band, turn the studio to face the camera
    names = [k["preset"] for k in shot["camera"]["keys"]]
    presets = fit_presets(asm.cameras(), names, asm.WIDE, asm.visible())
    studio.face_camera([cyc, *rig.values()], st["center"], presets[names[0]]["pos"])
    say("framed", presets={n: [round(v, 3) for v in presets[n]["pos"]] + [round(presets[n]["shift"], 3)]
                           for n in set(names)})

    # bake mechanism + camera keys for every frame (one extra on each side for motion blur)
    cam = ShotCamera(shot["camera"], presets, asm.anchors)
    cam.obj.data.clip_start, cam.obj.data.clip_end = st.get("clip", (0.01, 50.0))
    moving = asm.animated()
    for f in range(f0 - 1, f1 + 2):
        t = t_of(f)
        pose(asm, theta, t)
        for o in moving:
            _key_props(o, f)
        bpy.context.view_layer.update()
        cam.place(t)
        cam.key(f)
    say("baked", frames=f1 - f0 + 1, seconds=round(time.time() - t_start, 1))

    # anchors (cheap: no render)
    names = shot.get("anchors") or list(asm.anchors)
    track = {}
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        track[str(f)] = A.sample(names, asm.anchors)
    with open(os.path.join(out_dir, "anchors.json"), "w", encoding="utf-8") as fh:
        json.dump({"fps": FPS, "width": 1080, "height": 1920, "shot": shot.get("id"), "frames": track}, fh)
    say("anchors", count=len(names))

    todo = job.get("only") or list(range(f0, f1 + 1))
    done = 0
    for f in todo:
        path = os.path.join(out_dir, f"f_{f:04d}.png")
        if os.path.exists(path) and os.path.getsize(path) > 0:
            continue
        t = time.time()
        sc.frame_set(f)
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        done += 1
        say("frame", frame=f, seconds=round(time.time() - t, 2))
    say("done", rendered=done, seconds=round(time.time() - t_start, 1))


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    main(argv[0])
