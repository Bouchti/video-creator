"""
Blender check for engine/character.upright_close_ups (tests/test_blender_stills.py, BLENDER_TESTS=1):

  blender --background --factory-startup --python engine/posture_still.py -- OUT_DIR

Max kneels to fix something over frames 1-80 ('fix' clip). The camera is close on him over frames 1-40 (he fills
~half the frame: the flood-house film's giant-hat shots), then wide over 41-80. The guard must give him the upright
talk clip over the close frames only; a kid kneeling in the wide frames keeps his clip. Writes
OUT_DIR/posture_report.json. No frame is rendered.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

from engine import toy  # noqa: E402
from engine.character import Character, screen_share, upright_close_ups  # noqa: E402

out = sys.argv[sys.argv.index("--") + 1]
os.makedirs(out, exist_ok=True)
scene = toy.reset_scene()
scene.frame_start, scene.frame_end = 1, 80
scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
Character.cast.clear()
mx = Character("Max", location=(0, 0, 0))
kid = Character("Kid", look={"scale": 0.6, "hat": None, "mustache": False}, location=(2.5, 3.0, 0))
mx.act("fix", 1, 80)
kid.act("crouch", 41, 80)

cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 32
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
aim = toy.empty("Aim", (0, 0, 1.0))
con = cam.constraints.new("TRACK_TO")
con.target = aim
con.track_axis = "TRACK_NEGATIVE_Z"
for f, loc in ((1, (0, -3.2, 1.4)), (40, (0, -3.2, 1.4)), (41, (1, -22, 4)), (80, (1, -22, 4))):
    cam.location = loc
    cam.keyframe_insert("location", frame=f)
for fc in toy.fcurves(cam):
    for kp in fc.keyframe_points:
        kp.interpolation = "CONSTANT"

shares = {f: round(screen_share(scene, mx, f), 3) for f in (10, 60)}
before = {c.name: len(c._queue) for c in (mx, kid)}
done = upright_close_ups(scene)
talk = [(a, b) for clip, a, b, *_ in mx._queue if clip == "talk"]
kid_talk = [(a, b) for clip, a, b, *_ in kid._queue if clip == "talk"]
json.dump({"shares": shares, "max_talk": talk, "kid_talk": kid_talk, "done": done, "before": before},
          open(os.path.join(out, "posture_report.json"), "w"), indent=1)
print("DONE")
