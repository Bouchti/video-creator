"""Dev render: one character on grass, front and 3/4 views, for look review.

blender --background --factory-startup --python engine/dev_character.py -- OUT_DIR
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bpy  # noqa: E402

from engine import toy  # noqa: E402
from engine.character import Character  # noqa: E402

out_dir = sys.argv[sys.argv.index("--") + 1]

scene = toy.reset_scene()
toy.setup_world()
toy.add_sun()
toy.add_area("Fill", (-3.5, -4.0, 2.5), (0, 0, 1.0), energy=160, size=5)
toy.add_area("Rim", (2.5, 3.5, 3.0), (0, 0, 1.2), energy=320, size=3, color=(1.0, 0.9, 0.8))
print("LOOK", scene.view_settings.look)
ground = toy.box("ground", (30, 30, 0.2), (0, 0, -0.1),
                 mat=toy.noise_material("grass", toy.srgb("#4E9A2E"), toy.srgb("#7CC242"), scale=40),
                 bevel=0)

max_ = Character("Max", {"hat": "#FF7A00"}, location=(0, 0, 0))
max_.pose(1, shoulderR=(0, 150, 0), shoulderL=(-20, 0, 10), head=(0, 0, -10))
max_.smile(1, big=True)

cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 50
cam_data.dof.use_dof = True
cam_data.dof.aperture_fstop = 2.2
cam_data.dof.focus_object = max_.j["head"]
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
scene.frame_set(1)

for label, loc, rot in (("front", (0, -4.2, 1.15), (85, 0, 0)),
                        ("threequarter", (2.6, -3.3, 1.4), (82, 0, 38))):
    cam.location = loc
    cam.rotation_euler = [math.radians(a) for a in rot]
    scene.render.filepath = os.path.join(out_dir, f"char_{label}.png")
    bpy.ops.render.render(write_still=True)
print("DONE")
