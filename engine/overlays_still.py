"""
Blender check for engine/overlays.py + studio.Inset (tests/test_blender_stills.py, BLENDER_TESTS=1):

  blender --background --factory-startup --python engine/overlays_still.py -- OUT_DIR

A camera pans right over frames 1-60: label A (left) slides out of the left edge half-way, label B (centre)
stays in frame, an inset (right) starts cut by the right edge and comes fully in before mid-film. After settle() A must be
hidden while it is cut, B never, the inset only while cut; the text boxes must report B. Writes
OUT_DIR/overlays_report.json.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

from bpy_extras.object_utils import world_to_camera_view  # noqa: E402

from engine import overlays, studio as st, toy  # noqa: E402

out = sys.argv[sys.argv.index("--") + 1]
os.makedirs(out, exist_ok=True)
scene = toy.reset_scene()
scene.frame_start, scene.frame_end = 1, 60
scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 35
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
cam.rotation_euler = (1.5708, 0, 0)                  # looking along +y
for f, x in ((1, 0.0), (60, 1.6)):
    cam.location = (x, -8, 1.5)
    cam.keyframe_insert("location", frame=f)

a = st.label("LEFT", (-1.7, 0, 2.5), 1, 60, size=0.4)
b = st.label("MID", (0.8, 0, 1.0), 1, 60, size=0.4)
ins = st.Inset("probe", (2.4, 0, 2.4), radius=0.6)
ins.attach(toy.sphere("probe_ball", 0.15, (0, -0.05, 0)))
ins.show(1, 60, pop=2)

# a label behind an opaque wall (the water-tower film's LOAD PATH behind the tower's legs): pulled in front of it
wall = toy.box("wall", (4.0, 0.2, 1.4), (0.5, 1.0, 0.1), mat=toy.material("wall_mat", (0.6, 0.3, 0.2)))
hid = st.label("HID", (0.2, 2.0, 0.2), 1, 60, size=0.4)
scene.frame_set(30)
hid_view0 = list(world_to_camera_view(scene, cam, hid.matrix_world.to_translation()))[:2]

frames = list(range(1, 61))
hidden, boxes = overlays.settle(scene, frames, step=1)
scene.frame_set(30)
hid_view1 = list(world_to_camera_view(scene, cam, hid.matrix_world.to_translation()))[:2]


def shown(root, f):
    scene.frame_set(f)
    return overlays._shown(root)


report = {
    "hidden": hidden,
    "left_shown": [shown(a, f) for f in frames],
    "mid_shown": [shown(b, f) for f in frames],
    "inset_shown": [shown(ins.root, f) for f in frames],
    "boxes_frames": len(boxes),
    "boxes_at_30": boxes.get(30, []),
    "hid_y": hid.matrix_world.to_translation().y,
    "hid_scale": max(hid.matrix_world.to_scale()),
    "hid_view": [hid_view0, hid_view1],
    "hid_shown": [shown(hid, f) for f in frames],
}
json.dump(report, open(os.path.join(out, "overlays_report.json"), "w"), indent=1)
print("OVERLAYS", json.dumps({k: v for k, v in report.items() if k != "boxes_at_30"}))
