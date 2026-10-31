"""
Blender check for engine/studio.flowing_water (tests/test_blender_stills.py, BLENDER_TESTS=1):

  blender --background --factory-startup --python engine/flow_still.py -- OUT_DIR

A slide's water sheet must be see-through with foam streaks that move downhill over time (the water-tower slide
was a flat blue slab: it read as solid). Renders the sheet over a red board at frames 1 and 15 (small, EEVEE) and
writes OUT_DIR/flow_report.json: how much the picture changed, how much foam, and how much the board under it
changes the picture (red board, then blue).
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from engine import studio as st, toy  # noqa: E402

out = sys.argv[sys.argv.index("--") + 1]
os.makedirs(out, exist_ok=True)
scene = toy.reset_scene()
scene.render.resolution_x, scene.render.resolution_y = 160, 160
scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in {e.identifier for e in
                                                               bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items} \
    else "BLENDER_EEVEE_NEXT"
toy.setup_world(sun_elevation_deg=50, sun_rotation_deg=190, strength=0.15)
toy.add_sun(rotation_deg=(40, 0, 20), strength=0.8)
toy.box("board", (3.0, 3.0, 0.02), (0, 0, -0.05), mat=toy.material("red_board", (0.8, 0.05, 0.05)))
sheet = toy.box("sheet", (3.0, 3.0, 0.02), (0, 0, 0.02), mat=st.flowing_water("flow_test", along="X", speed=3.0))
cam_data = bpy.data.cameras.new("Cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = 2.4
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
cam.location = (0, 0, 5)


def shot(f):
    scene.frame_set(f)
    path = os.path.join(out, f"flow_{f}.png")
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(path)
    px = np.array(img.pixels[:], dtype=np.float32).reshape(-1, 4)[:, :3]
    bpy.data.images.remove(img)
    return px


a, b = shot(1), shot(15)
lum = a.mean(axis=1)
bsdf = toy._principled(bpy.data.materials["red_board"])
bsdf.inputs["Base Color"].default_value = (0.05, 0.05, 0.8, 1)          # the same sheet over a blue board
c = shot(1)
report = {"changed": float(np.abs(a - b).mean()),                      # the streaks move
          "foam_share": float((lum > 0.75).mean()),
          "see_through": float(np.abs(a - c).mean())}                  # what is under it shows
json.dump(report, open(os.path.join(out, "flow_report.json"), "w"), indent=1)
print("DONE", report)
