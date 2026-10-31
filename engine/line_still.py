"""
Blender check for engine/qa._dangling (tests/test_blender_stills.py, BLENDER_TESTS=1):

  blender --background --factory-startup --python engine/line_still.py -- OUT_DIR

A crane cable rising 12 m out of the top of the frame (the water-tower film's stray black line) must be flagged; a
short rope fully in frame and a thick pole must not. Writes OUT_DIR/line_report.json. No frame is rendered.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

from engine import qa, toy  # noqa: E402

out = sys.argv[sys.argv.index("--") + 1]
os.makedirs(out, exist_ok=True)
scene = toy.reset_scene()
scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 28
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
cam.location = (0, -12, 3)
cam.rotation_euler = (1.5708, 0, 0)                  # looking along +y

cable = toy.cylinder("crane_cable", 0.015, 20.0, (0.4, 0, 13.0), vertices=8)      # z 3 .. 23: mostly above the frame
rope = toy.cylinder("short_rope", 0.015, 1.5, (-1.0, 0, 2.0), vertices=8)
pole = toy.cylinder("thick_pole", 0.15, 12.0, (1.5, 0, 9.0), vertices=12)
bpy.context.view_layer.update()
report = {o.name: qa._dangling(scene, cam, o) for o in (cable, rope, pole)}
json.dump(report, open(os.path.join(out, "line_report.json"), "w"), indent=1)
print("DONE", report)
