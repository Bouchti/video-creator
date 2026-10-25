"""
PLANE STORY set — Blender builder (see plane_story_spec.py). Max builds an airplane in his field:
flat-board wings that never lift, pushing that is far too slow, a tailless plane that rears up and
stalls, a plane that can't steer into an oak tree... until it flies. Side-on diorama, with a
cutaway of the wing (airflow streamlines) and force arrows as 3D callouts.

Plane coordinates: faces +X; its root sits on the ground at the wheels. Pitch nose-UP = negative Y.
"""
import math
import random

import bmesh
import bpy
from mathutils import Euler, Vector

from engine import events, textures as tx, toy
from engine.backyard import _appear, _hide, _key
from engine.camera import CameraRig, facing_to
from engine.character import Character
from engine.cutaway import _grass_tuft, _bold_font, _pop, _hide_tree_window, flow_material, key_node_value
from engine.machines import Spray, Puffs, hammer_prop
from engine.sets.plane_story_spec import ACTIONS, beat_actions

V = Vector
R = math.radians
LANE_Y = 1.6                    # the plane's line along the field
P0 = V((-6.5, LANE_Y, 0))       # in front of the barn (the workshop spot)
WING_X = -0.9                   # wing chord centre on the body (behind the cockpit at x=0.5)
SEAT_X = 0.5
WORK = V((P0.x + 1.2, LANE_Y - 1.5, 0))     # Max's spot beside the nose: clear of wing, prop and camera
PUSH = V((-4.0, 0, 0))                      # Max's spot (relative to the plane) pushing the tail
HAY_X = 6.6
TREE = V((9.6, LANE_Y + 0.2, 0))
OAK_SCALE = 1.25
CRASH = V((5.5, LANE_Y - 0.2, 4.6))          # nose buried in the oak's leaves (edge x~7.5), cockpit still clear
CAM_Y = -10.0


# ------------------- small builders -------------------

def _mat(name, hexc, rough=0.5, **kw):
    return toy.material(name, toy.srgb(hexc), roughness=rough, **kw)


def airfoil_mesh(name, chord, span, thickness=0.12, camber=0.04, mat=None, n=24):
    """A NACA-4-style wing (chord along X, span along Y, centred), so the wing tip SHOWS the
    airfoil when seen side-on."""
    pts_top, pts_bot = [], []
    p = 0.4
    for k in range(n + 1):
        b_ = 0.5 * (1 - math.cos(math.pi * k / n))          # cosine spacing: round nose
        yt = 5 * thickness * (0.2969 * math.sqrt(b_) - 0.126 * b_ - 0.3516 * b_ ** 2 + 0.2843 * b_ ** 3
                              - 0.1015 * b_ ** 4)
        yc = camber / p ** 2 * (2 * p * b_ - b_ ** 2) if b_ < p else camber / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * b_ - b_ ** 2)
        pts_top.append((b_, yc + yt))
        pts_bot.append((b_, yc - yt))
    profile = pts_top[::-1] + pts_bot[1:-1]                  # trailing edge → nose → trailing edge
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    rings = []
    for y in (-span / 2, span / 2):
        rings.append([bm.verts.new(((0.5 - u) * chord, y, v * chord)) for u, v in profile])
    m = len(profile)
    for k in range(m):
        bm.faces.new((rings[0][k], rings[0][(k + 1) % m], rings[1][(k + 1) % m], rings[1][k]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    if mat:
        obj.data.materials.append(mat)
    return obj, profile


def label(text, loc, start, end, size=0.35, tilt=-5, color="#FF7A1A", outline="#3A0A00"):
    """Tilted orange callout facing the camera (emissive, no shadows), popping in and out."""
    fill = _mat(f"lbl_fill_{color}", color)
    bsdf = fill.node_tree.nodes.get("Principled BSDF")
    toy._set(bsdf, "Emission Color", (*toy.srgb(color), 1))
    toy._set(bsdf, "Emission Strength", 1.2)
    dark = _mat(f"lbl_line_{outline}", outline, 0.6)
    root = toy.empty(f"label_{text}_{start}", loc)
    root.rotation_euler = (R(90), R(tilt), 0)
    for nm, mat, off, dz in ((f"{text}_fill", fill, 0.0, 0.0), (f"{text}_line", dark, 0.02 * size / 0.22, -0.01)):
        cu = bpy.data.curves.new(f"{nm}_{start}", "FONT")
        cu.body, cu.size, cu.extrude, cu.offset = text, size, 0.004, off
        cu.align_x, cu.align_y = "CENTER", "CENTER"
        if _bold_font():
            cu.font = _bold_font()
        ob = bpy.data.objects.new(f"{nm}_{start}", cu)
        bpy.context.scene.collection.objects.link(ob)
        ob.data.materials.append(mat)
        ob.parent = root
        ob.location = (0, 0, dz)
    _hide_tree_window(root, start, end)
    _pop(root, start, end)
    events.add(start, "pop", gain=0.35)
    return root


def arrow(name, base, vec, start, end, color="#FFD23F", width=0.09, parent=None):
    """A 3D force arrow from `base` along `vec` (its length = |vec|), bobbing gently."""
    mat = _mat(f"arrow_{color}", color, 0.4)
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    toy._set(bsdf, "Emission Color", (*toy.srgb(color), 1))
    toy._set(bsdf, "Emission Strength", 1.4)
    d = V(vec)
    L = d.length
    root = toy.empty(name, base)
    root.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    shaft = toy.cylinder(f"{name}_shaft", width * 0.45, L * 0.72, (0, 0, L * 0.36), mat=mat, vertices=12)
    shaft.parent = root
    shaft.location = (0, 0, L * 0.36)
    bpy.ops.mesh.primitive_cone_add(radius1=width, depth=L * 0.3, vertices=16, location=(0, 0, 0))
    cone = bpy.context.active_object
    cone.name = f"{name}_head"
    toy._finish(cone, mat, subdiv=0, parent=root)
    cone.location = (0, 0, L * 0.85)
    if parent is not None:
        root.parent = parent
    toy.add_noise(root, "scale", 2, strength=0.04, scale=10, phase=len(name))
    _hide_tree_window(root, start, end)
    _pop(root, start, end)
    return root


class Plane:
    """Procedural ultralight assembled in stages (each part group appears/disappears on cue)."""

    def __init__(self):
        red = tx.paint("plane_red", "#D8342C", 0.32, coat=0.6, seams=0.55, seam_axis="x")
        cream = tx.paint("plane_cream", "#F1E6CF", 0.45, coat=0.4)
        skin = tx.fabric("wing_fabric", "#F1E6CF", rib=0.4, axis="y")             # doped fabric over ribs
        fin_skin = tx.fabric("fin_fabric", "#D8342C", rib=0.28, axis="x", coat=0.4)
        metal = tx.metal("plane_metal", "#9AA0A6", 0.3)
        cowl_metal = tx.metal("cowl_metal", "#B9BEC4", 0.25, along="x")
        dark = tx.rubber("plane_tyre", tread=36)
        seat_mat = tx.cloth("seat_leather", "#5A3A26", rough=0.6)
        wood = tx.planks("plank_wood", "#B07A45", "#C9905A", width=0.26, across="x", along="y", seam_dark=0.35)
        prop_wood = tx.wood("prop_wood", "#8A5A32", "#B98250", along="z")
        self.root = toy.empty("plane_root", P0)
        self.body = toy.empty("plane_body", (0, 0, 0), self.root)          # banks/pitches around here
        g = {}
        fus = toy.box("fuselage", (4.4, 0.8, 0.9), (-0.25, 0, 1.02), mat=red, parent=self.body, bevel=0.24)
        glass = _mat("windshield", "#BFE3F5", 0.05, coat=1.0)
        shield = toy.box("windshield", (0.12, 0.7, 0.45), (1.05, 0, 1.55), mat=glass, parent=self.body, bevel=0.04,
                         rotation=(0, R(-28), 0))
        stripe = toy.box("fus_stripe", (4.42, 0.735, 0.12), (-0.25, 0, 1.0), mat=cream, parent=self.body, bevel=0.03)
        tailcone = toy.box("tailcone", (1.0, 0.4, 0.4), (-2.6, 0, 1.08), mat=red, parent=self.body, bevel=0.12)
        seat = toy.box("seat", (0.5, 0.45, 0.12), (SEAT_X, 0, 1.18), mat=seat_mat, parent=self.body, bevel=0.03)
        wheels = []
        for side in (-1, 1):
            wheels.append(toy.cylinder(f"wheel{side}", 0.26, 0.14, (0.6, 0.55 * side, 0.26), rotation=(R(90), 0, 0),
                                       mat=dark, parent=self.body, bevel=0.03))
            toy.cylinder(f"gear{side}", 0.03, 0.72, (0.6, 0.38 * side, 0.55), rotation=(R(-28 * side), 0, 0),
                         mat=metal, parent=self.body)
        tailwheel = toy.cylinder("tailwheel", 0.1, 0.06, (-2.95, 0, 0.62), rotation=(R(90), 0, 0), mat=dark,
                                 parent=self.body)
        g["base"] = [fus, stripe, tailcone, seat, tailwheel, shield] + wheels + \
            [o for o in self.body.children if o.name.startswith("gear")]
        self.wheels = wheels + [tailwheel]
        # flat plank wings (attempt 1)
        flat = toy.box("flat_wing", (1.3, 8.0, 0.06), (WING_X, 0, 1.62), mat=wood, parent=self.body, bevel=0.01)
        g["flat"] = [flat]
        # airfoil wings + struts
        wing, self.profile = airfoil_mesh("wing", 1.45, 8.0, mat=skin)
        wing.parent = self.body
        wing.location = (WING_X, 0, 1.62)
        wing.rotation_euler = (0, R(-3), 0)                                 # a little angle of attack
        struts = [toy.cylinder(f"strut{side}", 0.025, 1.9, (WING_X, 1.5 * side, 1.35), rotation=(R(-60 * side), 0, 0),
                               mat=metal, parent=self.body) for side in (-1, 1)]
        g["wing"] = [wing] + struts
        g["struts_flat"] = [toy.cylinder(f"fstrut{side}", 0.025, 1.9, (WING_X, 1.5 * side, 1.35),
                                         rotation=(R(-60 * side), 0, 0), mat=metal, parent=self.body)
                            for side in (-1, 1)]
        g["flat"] += g["struts_flat"]
        # engine + propeller
        cowl = toy.sphere("cowl", 0.42, (2.05, 0, 1.0), scale=(1.1, 0.85, 0.9), mat=cowl_metal, parent=self.body)
        self.prop = toy.empty("prop", (2.55, 0, 1.0), self.body)
        hub = toy.sphere("prop_hub", 0.1, (0, 0, 0), scale=(1.6, 1, 1), mat=red, parent=self.prop)
        blades = [toy.box(f"blade{k}", (0.05, 0.13, 0.85), (0, 0, 0.42 * (1 if k else -1)), mat=prop_wood,
                          parent=self.prop, bevel=0.02) for k in range(2)]
        g["engine"] = [cowl, hub] + blades
        # tail
        stab, _ = airfoil_mesh("stabilizer", 0.75, 2.8, thickness=0.09, camber=0.0, mat=skin)
        stab.parent = self.body
        stab.location = (-2.75, 0, 1.12)
        fin = toy.box("fin", (0.85, 0.06, 0.85), (-2.85, 0, 1.6), mat=fin_skin, parent=self.body, bevel=0.06)
        g["tail"] = [stab, fin]
        # control surfaces (hinged so they can deflect): ailerons, elevator, rudder
        self.hinges = {}
        ail_x = WING_X - 0.72                                               # the wing's trailing edge
        for nm, pos, size, axis_rot in (("aileron_L", (ail_x, 2.9, 1.6), (0.35, 1.8, 0.04), (0, 0, 0)),
                                        ("aileron_R", (ail_x, -2.9, 1.6), (0.35, 1.8, 0.04), (0, 0, 0)),
                                        ("elevator", (-3.18, 0, 1.12), (0.3, 2.7, 0.04), (0, 0, 0)),
                                        ("rudder", (-3.35, 0, 1.6), (0.3, 0.05, 0.8), (0, 0, 0))):
            hinge = toy.empty(f"hinge_{nm}", pos, self.body)
            toy.box(nm, size, (-size[0] / 2, 0, 0), mat=tx.fabric("ctrl_yellow", "#F2C230", rib=0.3, axis="y"), parent=hinge,
                    bevel=0.01)
            self.hinges[nm] = hinge
        g["controls"] = [h.children[0] for h in self.hinges.values()]
        self.groups = g
        for parts in g.values():
            for o in parts:
                toy.hide_tree(o, 1, True)

    def show(self, group, frame, visible=True, pop=False):
        for k, o in enumerate(self.groups[group]):
            if pop and visible:
                _appear(o, frame + 3 * k, frames=6)
            else:
                toy.hide_tree(o, frame, not visible)

    # ---- motion ----
    def key(self, f, loc=None, pitch=None, roll=None, yaw=None):
        if loc is not None:
            self.root.location = V(loc)
            self.root.keyframe_insert("location", frame=f)
        if yaw is not None:
            self.root.rotation_euler = (0, 0, R(yaw))
            self.root.keyframe_insert("rotation_euler", frame=f)
        if pitch is not None or roll is not None:
            self.body.rotation_euler = (R(roll or 0), R(pitch or 0), 0)
            self.body.keyframe_insert("rotation_euler", frame=f)

    def teleport(self, f, loc, pitch=0, roll=0, yaw=0):
        """Snap to a new pose at a cut (hold the old pose until f-1)."""
        for obj, path in ((self.root, "location"), (self.root, "rotation_euler"), (self.body, "rotation_euler")):
            toy.key_hold(obj, path, f - 1, "CONSTANT")
        self.key(f, loc, pitch, roll, yaw)

    def roll_wheels(self, f0, f1, dist):
        for w in self.wheels:
            toy.key_hold(w, "rotation_euler", f0)
            w.rotation_euler.y += dist / 0.26
            w.keyframe_insert("rotation_euler", frame=f1)

    def spin(self, f0, f1, revs_per_frame=0.37):
        toy.key_hold(self.prop, "rotation_euler", f0)
        self.prop.rotation_euler.x += 2 * math.pi * revs_per_frame * (f1 - f0)
        self.prop.keyframe_insert("rotation_euler", frame=f1)
        toy.set_interpolation(self.prop, "rotation_euler", (f0,), "LINEAR")

    def wiggle(self, f0, f1, period=14):
        """Control surfaces flap through their range (for the explainer)."""
        for nm, hinge in self.hinges.items():
            axis = 2 if nm == "rudder" else 1
            f, k = f0, 0
            while f < f1:
                rot = [0, 0, 0]
                rot[axis] = R(25 if k % 2 else -25) * (-1 if nm == "aileron_R" else 1)
                hinge.rotation_euler = rot
                hinge.keyframe_insert("rotation_euler", frame=f)
                f += period // 2
                k += 1
            hinge.rotation_euler = (0, 0, 0)
            hinge.keyframe_insert("rotation_euler", frame=f1)


# ------------------- the set -------------------

class PlaneStorySet:
    ACTIONS = ACTIONS

    def __init__(self, scene, sun, fill, bg, total):
        self.scene, self.sun, self.fill, self.bg, self.total = scene, sun, fill, bg, total
        self.rig = CameraRig(blend=16)
        self._world()
        self.plane = Plane()
        self.max = Character("Max", {"hat": "#FF7A00", "iris": "#7A4A1C"})
        self.pilot = Character("MaxPilot", {"hat": "#FF7A00", "iris": "#7A4A1C", "scale": 0.9})
        self.pilot.root.parent = self.plane.body
        self.pilot.place(1, V((SEAT_X + 0.05, 0, 0.55)), 90)                  # facing +X (flight direction)
        self.pilot.sit(1, total + 400, frames=1)
        toy.hide_tree(self.pilot.root, 1, True)
        self.kids = [Character("Kid1", {"hat": None, "mustache": False, "shirt": "#FF5D8F", "overalls": "#3A7BD5",
                                        "hair": "#5B3A1E", "scale": 0.6, "ponytail": True}),
                     Character("Kid2", {"hat": None, "mustache": False, "shirt": "#3DBE6E", "overalls": "#F2A93B",
                                        "hair": "#2B1A10", "scale": 0.56})]
        for kid in self.kids:
            toy.hide_tree(kid.root, 1, True)
        self.hammer = hammer_prop("plane_hammer")
        self.max.hold(self.hammer, "R")
        self.hammer.rotation_euler = (R(-90), 0, 0)
        toy.hide_tree(self.hammer, 1, True)
        self.max.place(1, WORK, 0)
        for c in (self.max, self.pilot):
            c.auto_blink(1, total + 400, seed=len(c.name))
        self.flying = False
        self._tracks = []

    # ------------------- world -------------------

    def _world(self):
        grass = toy.noise_material("field_grass", toy.srgb("#4C8A33"), toy.srgb("#6AA543"), scale=30, bump=0.3)
        toy.box("field", (120, 80, 0.4), (0, 20, -0.2), mat=grass, bevel=0)
        dirt = toy.noise_material("strip_dirt", toy.srgb("#9C7A52"), toy.srgb("#B8946A"), scale=12, bump=0.5)
        toy.box("airstrip", (40, 2.2, 0.03), (0, LANE_Y, -0.005), mat=dirt, bevel=0)
        tuft = _grass_tuft()
        for k, (nm, (x0, x1, y0, y1), dens, size) in enumerate((
                ("g_front", (-16, 16, -3, LANE_Y - 1.15), 260, 1.4),
                ("g_near", (-18, 18, -12, -3), 150, 2.0),                      # sparser, bigger
                ("g_back", (-16, 16, LANE_Y + 1.15, 9), 260, 1.4))):
            toy.scatter(nm, x0, x1, y0, y1, tuft, dens, size=size, seed=k)     # one static mesh, no particles
        tuft.hide_render = True
        # Max's red barn (the workshop)
        red = tx.planks("barn_red", "#A8322B", "#922A24", width=0.28)                 # vertical barn boards
        white = tx.planks("barn_white", "#F2EEE6", "#E4DED2", width=0.2, seam_dark=0.25)
        trim = tx.paint("barn_trim", "#F2EEE6", 0.55, coat=0.0)
        roof = tx.corrugated("barn_roof", "#6E757E", pitch=0.12, axis="x")
        toy.box("barn", (6, 5, 4), (-11.5, 5.5, 2.0), mat=red, bevel=0.05)
        for k, s_ in enumerate((-1, 1)):
            toy.box(f"barn_roof{k}", (6.6, 3.2, 0.2), (-11.5, 5.5 + 1.25 * s_, 4.75), mat=roof, bevel=0.04,
                    rotation=(R(-38 * s_), 0, 0))
        toy.box("barn_door", (2.4, 0.1, 2.8), (-11.5, 2.97, 1.4), mat=white, bevel=0.03)
        brace = tx.paint("barn_brace", "#A8322B", 0.6, coat=0.0)
        toy.box("barn_x1", (0.12, 0.12, 3.4), (-11.5, 2.9, 1.4), mat=brace, rotation=(0, R(40), 0), bevel=0.01)
        toy.box("barn_x2", (0.12, 0.12, 3.4), (-11.5, 2.9, 1.4), mat=brace, rotation=(0, R(-40), 0), bevel=0.01)
        for k, (x, w, h, z) in enumerate(((-11.5, 2.7, 0.16, 2.88), (-12.75, 0.16, 2.9, 1.45),
                                          (-10.25, 0.16, 2.9, 1.45))):
            toy.box(f"barn_trim{k}", (w, 0.08, h), (x, 2.95, z), mat=trim, bevel=0.01)          # door frame
        toy.box("barn_loft", (1.4, 0.1, 1.0), (-11.5, 2.97, 3.35), mat=white, bevel=0.03)     # hay-loft door
        toy.box("barn_loft_trim", (1.6, 0.06, 1.2), (-11.5, 2.99, 3.35), mat=trim, bevel=0.01)
        # house, fence, hills, trees, haystack, windsock
        siding = tx.planks("fh_siding", "#F2EEE6", "#E8E2D6", width=0.22, across="z", along="xy", lap=True,
                           seam_dark=0.22)
        toy.box("farmhouse", (8, 5, 4.2), (4.0, 16.0, 2.1), mat=siding, bevel=0.05)
        shingle = tx.shingles("fh_roof", "#B8532F", "#7E3520")
        for k, s_ in enumerate((-1, 1)):
            toy.box(f"farmhouse_roof{k}", (8.8, 3.3, 0.18), (4.0, 16.0 + 1.35 * s_, 5.05), mat=shingle, bevel=0.03,
                    rotation=(R(-32 * s_), 0, 0))
        bpy.ops.mesh.primitive_cylinder_add(vertices=3, radius=1.0, depth=7.9, location=(4.0, 16.0, 4.71),
                                            rotation=(0, R(-90), 0))         # triangular prism, apex up
        gable = bpy.context.active_object                                     # the gable wall under the roof
        gable.name = "fh_gable"
        gable.scale = (1.02, 2.83, 1.0)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)   # siding runs level
        toy._finish(gable, siding, subdiv=0, smooth=False)
        glass = _mat("fh_glass", "#7FA9C4", 0.08, coat=1.0)
        for k, x in enumerate((1.2, 3.0, 6.8)):
            toy.box(f"fh_win{k}", (1.1, 0.08, 1.2), (x, 13.47, 2.4), mat=glass, bevel=0.01)
            toy.box(f"fh_wframe{k}", (1.3, 0.06, 1.4), (x, 13.5, 2.4), mat=trim, bevel=0.01)
        toy.box("fh_door", (1.0, 0.08, 2.1), (4.9, 13.47, 1.05),
                mat=tx.planks("fh_door", "#4E6E8E", "#466482", width=0.14), bevel=0.02)
        post_wood = tx.wood("fence_post", "#7E5E40", "#9C7B58", along="z")
        rail_wood = tx.wood("fence_rail", "#7E5E40", "#9C7B58", along="x")
        for i in range(40):
            toy.box(f"fpost{i}", (0.12, 0.12, 1.2), (-20 + i, 11.0, 0.6), mat=post_wood, bevel=0.01)
        toy.box("frail", (40, 0.08, 0.1), (0, 11.0, 0.9), mat=rail_wood, bevel=0)
        toy.box("frail2", (40, 0.08, 0.1), (0, 11.0, 0.45), mat=rail_wood, bevel=0)
        hill = _mat("hill_green", "#5F9B45", 0.9)
        for k, (x, r) in enumerate(((-25, 14), (8, 18), (40, 16))):
            toy.sphere(f"hill{k}", r, (x, 60, -r * 0.6), scale=(1.6, 1.0, 0.7), mat=hill, subdiv=1)
        self._tree(TREE, OAK_SCALE, oak=True)
        for x, y, s in ((-16, 8, 1.1), (14, 9, 1.0), (-2, 12.5, 0.9), (20, 4, 1.2)):
            self._tree(V((x, y, 0)), s)
        hay = tx.straw("hay")
        for k, (dx, dz) in enumerate(((0, 0.45), (0.0, 1.35), (-0.4, 0.45))):
            toy.cylinder(f"hay{k}", 0.55, 1.4, (HAY_X + 0.9 + dx, LANE_Y + (0.6 if k == 2 else 0), dz),
                         rotation=(R(90), 0, 0), mat=hay, bevel=0.08)
        toy.cylinder("sock_pole", 0.04, 4.0, (15.0, 7.0, 2.0), mat=tx.metal("pole", "#DDDDDD", 0.35))  # out of camera paths
        sock = toy.cylinder("windsock", 0.2, 1.0, (14.5, 7.0, 3.8), rotation=(0, R(80), 0),
                            mat=tx.cloth("sock", "#FF6A13"))
        toy.add_noise(sock, "rotation_euler", 2, strength=0.15, scale=20)
        self._clouds()

    def _tree(self, at, s, oak=False):
        bark = toy.noise_material("bark2", toy.srgb("#5A4632"), toy.srgb("#74604A"), scale=12, bump=0.6)
        leaf = toy.noise_material("foliage2", toy.srgb("#3D6B2A"), toy.srgb("#5E8C38"), scale=6, bump=0.6)
        h = 4.2 * s if oak else 2.8 * s
        bpy.ops.mesh.primitive_cone_add(radius1=0.32 * s, radius2=0.18 * s, depth=h, vertices=14,
                                        location=(at.x, at.y, h / 2))
        trunk = bpy.context.active_object
        trunk.name = f"trunk_{at.x}"
        toy._finish(trunk, bark, subdiv=0)
        tex = bpy.data.textures.get("foliage_lumps2") or bpy.data.textures.new("foliage_lumps2", "CLOUDS")
        tex.noise_scale = 0.4
        rnd = random.Random(int(at.x * 10))
        canopy = toy.empty(f"canopy_{at.x}", (at.x, at.y, h))
        toy.add_noise(canopy, "rotation_euler", 0, strength=0.012, scale=80, phase=at.x)
        for k in range(14 if oak else 9):
            off = V((rnd.uniform(-1.6, 1.6), rnd.uniform(-1.2, 1.2), rnd.uniform(-0.3, 1.5))) * s
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=rnd.uniform(0.8, 1.2) * s, location=(0, 0, 0))
            blob = bpy.context.active_object
            blob.name = f"leaf_{at.x}_{k}"
            d = blob.modifiers.new("lumps", "DISPLACE")
            d.texture, d.strength = tex, 0.3 * s
            toy._finish(blob, leaf, subdiv=0)
            blob.parent = canopy
            blob.location = off
        if oak:
            self.oak_canopy = canopy

    def _clouds(self):
        mat = toy.material("cloud_soft2", (1, 1, 1), roughness=0.95)
        tex = bpy.data.textures.new("cloud_puff2", "CLOUDS")
        tex.noise_scale = 0.8
        rnd = random.Random(3)
        for i in range(8):
            root = toy.empty(f"cloud_{i}", (rnd.uniform(-50, 50), rnd.uniform(50, 80), rnd.uniform(14, 26)))
            for k in range(5):
                bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=rnd.uniform(2.4, 3.8), location=(0, 0, 0))
                puff = bpy.context.active_object
                puff.name = f"cloud_{i}_{k}"
                d = puff.modifiers.new("puff", "DISPLACE")
                d.texture, d.strength = tex, 0.9
                toy._finish(puff, mat, subdiv=0)
                puff.parent = root
                puff.location = (rnd.uniform(-4, 4), rnd.uniform(-1, 1), rnd.uniform(-0.6, 0.8))
                puff.scale = (1.4, 1.0, 0.65)
                puff.visible_shadow = False
            root.keyframe_insert("location", frame=1)
            root.location.x += 30
            root.keyframe_insert("location", frame=6000)
            toy.set_interpolation(root, "location", (1,), "LINEAR")

    # ------------------- driver -------------------

    def run(self, beats, spans, epilogue_offset):
        self.EPI = epilogue_offset
        self.acts, self.spans = [], []
        for i, b in enumerate(beats):
            acts = beat_actions(b)
            s, e = spans[i]
            weights = [sum(self.ACTIONS[a].get("seconds", (1, 1))) for a in acts]
            t = s
            for k, (a, w) in enumerate(zip(acts, weights)):
                end = e if k == len(acts) - 1 else t + int((e - s + 1) * w / sum(weights)) - 1
                self.acts.append(a)
                self.spans.append((t, end))
                t = end + 1
        for i, a in enumerate(self.acts):
            if self.ACTIONS[a]["kind"] in ("hook", "rewind"):
                continue
            getattr(self, f"a_{a}")(i, *self.spans[i])
        hb, he = self.spans[0]
        getattr(self, f"a_{self.acts[0]}")(0, hb + epilogue_offset, he + epilogue_offset)
        # Tracking shots follow the plane's FINAL motion: normalize interpolation first (it changes
        # how the plane moves between keys), then sample the path.
        toy.normalize_interpolation()
        for t in self._tracks:
            self._track(**t)
        self.rig.build()

    # ------------------- helpers -------------------

    def ground_max(self, f, spot, face_to=None):
        toy.hide_tree(self.pilot.root, f, True)
        toy.hide_tree(self.max.root, f, False)
        toy.hide_tree(self.hammer, f, True)            # un-hiding Max un-hides his hammer too; beats that use it re-show it
        self.max.cut_place(f, spot, facing_to(spot, face_to) if face_to is not None else 0)
        self.max.pose(f + 6)

    def pilot_on(self, f):
        toy.hide_tree(self.max.root, f, True)
        toy.hide_tree(self.pilot.root, f, False)

    def light(self, f, sun_e=4.2, bg_v=0.22, fill_e=900):
        for d, path, v in ((self.sun.data, "energy", sun_e), (self.fill.data, "energy", fill_e)):
            setattr(d, path, v)
            d.keyframe_insert(path, frame=f)
        self.bg.default_value = bg_v
        self.bg.keyframe_insert("default_value", frame=f)

    def engine_noise(self, f0, f1):
        events.add(f0, "plane_engine", duration=max(1, f1 - f0))

    def plane_center(self, f):
        """World position of the plane's visual centre at frame f (follows pitch/roll/yaw, so a
        plane rearing nose-up stays centred, unlike its root at the wheels)."""
        pl = self.plane
        loc = V(toy.value_at(pl.root, "location", f))
        yaw = toy.value_at(pl.root, "rotation_euler", f)[2]
        body = Euler(toy.value_at(pl.body, "rotation_euler", f))
        lift = toy.value_at(pl.body, "location", f)
        return loc + V(lift) + Euler((0, 0, yaw)).to_matrix() @ body.to_matrix() @ V((-0.3, 0, 1.0))

    def track_plane(self, f0, f1, cam_off=(-3.2, -7.5, 1.3), aim_off=(0, 0, 0), lens=26, cut=False, dist=None,
                    hold=None, cam_z=None, smooth=10):
        """Camera that follows the plane. Recorded now, built in run() once the motion is final.
        cam_off: direction from the plane to the camera (length = distance unless `dist`).
        hold: (frame, cam, aim) to stop tracking and settle on a fixed framing from that frame.
        cam_z: keep the camera at this height (looks UP at a climbing plane: sky behind it)."""
        self._tracks.append(dict(f0=f0, f1=f1, cam_off=cam_off, aim_off=aim_off, lens=lens, cut=cut, dist=dist,
                                 hold=hold, cam_z=cam_z, smooth=smooth))

    def _track(self, f0, f1, cam_off, aim_off, lens, cut, dist, hold, cam_z, smooth):
        last = hold[0] if hold else f1
        frames = list(range(f0, last + 1))
        centers = [self.plane_center(f) for f in frames]

        def blur(pts, sigma):                       # gaussian smoothing, edges clamped
            r = int(sigma * 2.5)
            w = [math.exp(-0.5 * (k / sigma) ** 2) for k in range(-r, r + 1)]
            out = []
            for i in range(len(pts)):
                acc, tot = V((0, 0, 0)), 0.0
                for k, wk in zip(range(-r, r + 1), w):
                    acc += pts[min(len(pts) - 1, max(0, i + k))] * wk
                    tot += wk
                out.append(acc / tot)
            return out

        base = blur(centers, smooth)                # the camera body moves calmly...
        aims = blur(centers, 2.5)                   # ...while the aim keeps the plane centred
        off = V(cam_off)
        if dist:
            off = off.normalized() * dist
        keys = []
        for k in list(range(0, len(frames) - 1, 3)) + [len(frames) - 1]:
            cam = base[k] + off
            cam.z = cam_z if cam_z is not None else max(0.6, cam.z)
            keys.append((frames[k], cam, aims[k] + V(aim_off)))
        if hold:
            keys.append((max(hold[0] + 1, min(f1, hold[0] + 36)), V(hold[1]), V(hold[2])))   # unhurried reframe
            keys.append((f1, V(hold[1]) + V((0.15, 0.25, 0)), V(hold[2])))
        self.rig.track(f0, f1, keys, lens=lens, cut=cut)

    def follow(self, f0, f1, x0, x1, z=1.6, dist=10.0, lens=26, cut=False, z_aim=None):
        """Side-on tracking shot from x0 to x1."""
        za = z if z_aim is None else z_aim
        self.rig.shot(f0, f1, cam_from=(x0 - 3.6, LANE_Y - dist, z + 2.2), cam_to=(x1 - 3.6, LANE_Y - dist, z + 2.2),
                      aim_from=(x0, LANE_Y, za), aim_to=(x1, LANE_Y, za), lens=lens, fstop=8.0, cut=cut)

    def scratch_head(self, f0, f1):
        m = self.max
        m.pose(f0 + 4, shoulderR=(-25, 140, 0), head=(0, 14, 0))
        m.pose(f1 - 4, shoulderR=(-25, 150, 0), head=(0, 10, 0))
        m.brows(f0 + 4, 0.9)
        m.brows(f1, 0.0)

    # ------------------- the ladder -------------------

    def a_build_flat(self, i, b, e):
        pl = self.plane
        pl.key(b, P0, 0, 0, 0)
        pl.show("base", b + 2, pop=True)
        pl.show("flat", b + int((e - b) * 0.45), pop=True)
        self.ground_max(b, WORK, WORK + V((0, 1, 0)))                     # faces the fuselage side
        toy.hide_tree(self.hammer, b, False)
        toy.hide_tree(self.hammer, e - 10, True)
        self.max.hammer(b + 6, e - 14, hand="R")
        self.max.turn(e - 14, facing_to(WORK, (-1.0, -2.6, 0)), frames=8)  # turns to camera...
        self.max.pose(e - 10, shoulderL=(-90, 0, 20))                     # ...thumbs up
        self.max.smile(e - 10, big=True)
        self.rig.shot(b, e, cam_from=(-0.6, -3.0, 2.0), cam_to=(-1.0, -2.6, 1.9), aim_from=(-6.4, LANE_Y - 0.3, 1.0),
                      aim_to=(-6.2, LANE_Y - 0.3, 1.0), lens=24, fstop=8.0)

    def a_fail_flat(self, i, b, e):
        pl = self.plane
        L = e - b
        rel, stop_f = b + int(L * 0.5), b + int(L * 0.8)
        release = V((P0.x + 6.0, LANE_Y, 0))
        stop = V((HAY_X - 2.2, LANE_Y, 0))
        pl.key(b + 4, P0, 0, 0, 0)
        pl.key(rel, release)
        pl.key(stop_f, stop)                                                # eases into the haystack
        toy.set_interpolation(pl.root, "location", (b + 4,), "LINEAR")     # same speed as Max while pushed
        pl.roll_wheels(b + 4, stop_f, (stop - P0).length)
        pl.key(stop_f + 4, pitch=-4)                                       # bumps the hay
        pl.key(stop_f + 10, pitch=0)
        events.add(b + 4, "roll", duration=stop_f - b - 4)
        events.add(stop_f, "hay_thud")
        behind = PUSH
        self.ground_max(b, P0 + behind, P0 + behind + V((1, 0, 0)))
        self.max.walk(b + 4, rel, to=release + behind, facing_deg=facing_to(P0 + behind, release + behind),
                      step_frames=6)
        self.max.pose(b + 6, shoulderL=(-80, 0, 0), shoulderR=(-80, 0, 0), spine=(25, 0, 0))
        self.max.pose(rel + 2)
        self.max.point(rel + 4, stop_f, hand="R", up_deg=40, side_deg=0)   # "go on!"
        self.scratch_head(stop_f + 6, e - 2)
        self.track_plane(b, e, cam_off=(-6.2, -5.4, 1.8), aim_off=(-1.6, 0, -0.1), lens=22, dist=9.0, cut=True,
                         hold=(rel, (-7.8, -0.4, 2.0), (0.0, LANE_Y, 0.9)))

    def a_airfoil(self, i, b, e):
        pl = self.plane
        L = e - b
        pl.teleport(b, P0)
        pl.show("flat", b + 4, False)
        Puffs("swap_dust", "#C9B79A", count=8, size=0.35, seed=4).emit(range(b + 3, b + 9),
                                                                       lambda f: (P0.x, LANE_Y - 1.5, 1.6), rise=0.6)
        pl.show("wing", b + 6, pop=True)
        self.ground_max(b, WORK, (P0.x + 0.6, LANE_Y - 7.0, 0))           # faces the viewer
        # the cutaway insert: a big wing section with the air streaming over and under it
        d0 = b + int(L * 0.3)
        cx, cy, cz, chord = P0.x + 0.2, LANE_Y - 2.6, 3.4, 2.6
        cream = _mat("plane_cream", "#F1E6CF", 0.6)
        insert, prof = airfoil_mesh("wing_section", chord, 0.12, mat=cream)
        insert.location = (cx, cy, cz)
        insert.rotation_euler = (0, R(-4), 0)
        _appear(insert, d0, frames=8)
        _hide(insert, e, True)
        card_mat = _mat("cutaway_card", "#14324A", 0.6)
        toy._set(card_mat.node_tree.nodes.get("Principled BSDF"), "Emission Color", (*toy.srgb("#14324A"), 1))
        toy._set(card_mat.node_tree.nodes.get("Principled BSDF"), "Emission Strength", 0.6)
        card = toy.box("cutaway_card", (chord * 2.1, 0.04, 3.1), (cx, cy + 0.35, cz + 0.35), mat=card_mat, bevel=0.12)
        card.visible_shadow = False
        _appear(card, d0 - 4, frames=8)                                     # the diagram sits on its own card
        _hide(card, e, True)
        self._temp = []
        top = flow_material("air_fast", 1.0, speed=2.2, base="#9FD8FF", stripe="#FFFFFF")
        bot = flow_material("air_slow", 1.0, speed=0.9, base="#9FD8FF", stripe="#FFFFFF")
        for mat in (top, bot):
            key_node_value(mat, "flow_on", d0 + 6, 0.0)
            key_node_value(mat, "flow_on", d0 + 14, 1.0)
        for k, off in enumerate((0.16, 0.34, 0.55)):                       # streamlines: arcs over, flatter under
            for side, mat in ((1, top), (-1, bot)):
                pts = [(cx - chord * 0.9, cz + side * off * 0.6)]
                for t in range(9):
                    xx = cx - chord * 0.7 + chord * 1.4 * t / 8
                    bump = math.sin(math.pi * t / 8) * (0.22 if side > 0 else 0.05) * (1.4 - off)
                    pts.append((xx, cz + side * (off + 0.05) + bump * side))
                pts.append((cx + chord * 0.9, cz + side * off * 0.6))
                for s_ in range(len(pts) - 1):
                    (xa, za), (xb, zb) = pts[s_], pts[s_ + 1]
                    seg_len = math.hypot(xb - xa, zb - za)
                    cyl = toy.cylinder(f"air_{k}_{side}_{s_}", 0.022, seg_len, ((xa + xb) / 2, cy - 0.02, (za + zb) / 2),
                                       rotation=(0, math.atan2(xb - xa, zb - za), 0), mat=mat, vertices=8)
                    cyl.visible_shadow = False
                    _appear(cyl, d0 + 4 + s_, frames=4)
                    _hide(cyl, e, True)
        label("LOW PRESSURE", (cx - 0.75, cy - 0.1, cz + 1.2), d0 + 10, e, size=0.22, tilt=-4)
        label("HIGH PRESSURE", (cx - 0.2, cy - 0.1, cz - 0.95), d0 + 16, e, size=0.22, tilt=4, color="#5EC8FF",
              outline="#0A2A3A")
        arrow("lift_arrow", (cx + 0.35, cy - 0.05, cz + 0.3), (0, 0, 1.2), d0 + 22, e)
        label("LIFT", (cx + 0.95, cy - 0.1, cz + 1.4), d0 + 24, e, size=0.3, tilt=6, color="#FFD23F")
        self.max.point(d0, e - 4, hand="L", up_deg=70, side_deg=10)
        self.rig.shot(b, e, cam_from=(cx + 1.2, cy - 6.2, cz - 0.6), cam_to=(cx + 0.6, cy - 5.2, cz - 0.4),
                      aim_from=(cx, cy, cz - 0.9), aim_to=(cx, cy, cz - 0.6), lens=24, fstop=8.0, cut=True)

    def a_fail_thrust(self, i, b, e):
        pl = self.plane
        L = e - b
        run_end = b + int(L * 0.6)
        stop = V((P0.x + 4.5, LANE_Y, 0))
        coast = stop + V((1.3, 0, 0))
        pl.key(b + 4, P0)
        pl.key(run_end, stop)
        toy.set_interpolation(pl.root, "location", (b + 4,), "LINEAR")     # matches Max's running speed
        pl.key(run_end + 14, coast)                                         # rolls on as he lets go
        hop = b + int(L * 0.45)
        for f, z in ((hop - 6, 0.0), (hop, 0.18), (hop + 6, 0.0)):          # a pathetic little hop
            pl.body.location = (0, 0, z)
            pl.body.keyframe_insert("location", frame=f)
        pl.roll_wheels(b + 4, run_end + 14, (coast - P0).length)
        self.ground_max(b, P0 + PUSH, P0 + PUSH + V((1, 0, 0)))
        self.max.walk(b + 4, run_end, to=stop + PUSH, facing_deg=90, step_frames=5)
        self.max.pose(b + 6, shoulderL=(-80, 0, 0), shoulderR=(-80, 0, 0), spine=(30, 0, 0))
        self.max.crouch(run_end + 10, e - 2, frames=6, lean=28)           # out of breath (the plane has rolled on)
        events.add(b + 4, "roll", duration=run_end - b - 4, gain=0.8)
        events.add(hop, "boing", gain=0.4)
        events.add(run_end + 4, "pant")
        self.max.key("mouth", run_end + 6, scale=(1.2, 0.6, 2.2))
        self.track_plane(b, e, cam_off=(-6.2, -5.4, 1.8), aim_off=(-1.6, 0, -0.1), lens=22, dist=9.0, cut=True,
                         hold=(run_end, (stop.x - 7.5, -6.0, 2.2), (stop.x - 1.8, LANE_Y, 0.9)))

    def a_engine(self, i, b, e):
        pl = self.plane
        pl.teleport(b, P0)
        pl.show("engine", b + 4, pop=True)
        spin0 = b + int((e - b) * 0.45)
        pl.spin(spin0, e - 2)
        events.add(spin0, "plane_start")
        self.engine_noise(spin0 + 60, e)
        Puffs("prop_wash", "#C9B79A", count=14, size=0.3, seed=7).emit(range(spin0 + 2, e - 4, 3),
                                                                        lambda f: (P0.x - 2.6, LANE_Y, 0.4), rise=0.3,
                                                                        drift=0.8)
        arrow("thrust_arrow", (P0.x + 2.9, LANE_Y - 0.6, 1.0), (1.6, 0, 0), spin0 + 8, e)
        label("THRUST", (P0.x + 3.7, LANE_Y - 0.7, 1.6), spin0 + 10, e, size=0.3, tilt=-5, color="#FFD23F")
        self.ground_max(b, V((P0.x + 1.9, LANE_Y - 1.9, 0)), (-1.0, -5.8, 0))   # beside the nose, clear of the prop
        self.max.cheer(spin0 + 6, e - 2)
        self.rig.shot(b, e, cam_from=(-1.0, -5.8, 2.8), cam_to=(-1.8, -5.0, 2.5), aim_from=(-5.0, LANE_Y, 1.1),
                      aim_to=(-4.6, LANE_Y, 1.1), lens=26, fstop=8.0, cut=True)

    def a_forces(self, i, b, e):
        c = P0 + V((0, 0, 1.2))
        for k, (nm, vec, col, txt, off) in enumerate((("f_lift", (0, 0, 1.5), "#FFD23F", "LIFT", (0.4, 0, 2.0)),
                                                      ("f_weight", (0, 0, -1.2), "#FF7A1A", "WEIGHT", (0.5, 0, -1.4)),
                                                      ("f_thrust", (1.6, 0, 0), "#5EC8FF", "THRUST", (2.4, 0, 0.4)),
                                                      ("f_drag", (-1.4, 0, 0), "#B78CFF", "DRAG", (-2.2, 0, 0.4)))):
            arrow(nm, c + V((0, -1.3, 0)), vec, b + 4 + 6 * k, e, color=col)
            label(txt, c + V((off[0], -1.4, off[2])), b + 6 + 6 * k, e, size=0.28, tilt=(-1) ** k * 5, color=col)
        spot = V((P0.x + 2.6, LANE_Y - 2.2, 0))                            # clear of every arrow, camera side
        self.ground_max(b, spot, (P0.x - 1.0, -7.5, 0))
        self.max.point(b + 6, e - 4, hand="R", up_deg=45, side_deg=40)
        self.rig.shot(b, e, cam_from=(P0.x - 1.0, -7.5, 3.0), cam_to=(P0.x - 0.6, -6.9, 2.8),
                      aim_from=(P0.x + 0.4, LANE_Y - 0.6, 1.3), lens=22, fstop=8.0)

    def a_fail_flip(self, i, b, e):
        pl = self.plane
        L = e - b
        pl.teleport(b, P0)
        self.pilot_on(b)
        t_roll, t_lift, t_top, t_fall = b + 4, b + int(L * 0.35), b + int(L * 0.6), b + int(L * 0.8)
        lift_x = P0.x + 6
        pl.key(t_roll, P0, 0)
        pl.key(t_lift, V((lift_x, LANE_Y, 0.1)), -12)
        pl.roll_wheels(t_roll, t_lift, lift_x - P0.x)
        t_tail = e - 12
        pl.key(t_top, V((lift_x + 3.0, LANE_Y, 4.4)), -70)                 # rears up...
        pl.key(t_fall, V((lift_x + 2.6, LANE_Y, 4.3)), -100)               # ...stalls...
        pl.key((t_fall + t_tail) // 2, V((lift_x + 2.2, LANE_Y, 3.4)), -75)
        pl.key(t_tail, V((lift_x + 1.9, LANE_Y, 1.7)), -42)                # ...tail hits the grass...
        pl.key(e - 6, V((lift_x + 1.5, LANE_Y, 0.0)), -2)                  # ...and it slams onto its wheels
        pl.key(e - 3, V((lift_x + 1.45, LANE_Y, 0.12)), 2)
        pl.key(e - 1, V((lift_x + 1.4, LANE_Y, 0.0)), 0)
        events.add(t_tail, "flop")
        events.add(e - 6, "hay_thud")
        events.add(e - 5, "boing", gain=0.4)
        pl.spin(b, t_fall)
        self.engine_noise(b, t_fall)
        self.pilot.brows(t_top - 4, 1.0)
        self.pilot.key("mouth", t_top, scale=(1.2, 0.6, 2.4))
        self.track_plane(b, e, cam_off=(4.0, -9.0, 0.4), lens=24, dist=11.0, cut=True)

    def a_tail(self, i, b, e):
        pl = self.plane
        pl.teleport(b, P0)
        pl.show("tail", b + 4, pop=True)
        mid = b + int((e - b) * 0.5)
        arrow("cg_weight", (P0.x - 0.4, LANE_Y - 1.3, 1.0), (0, 0, -0.9), mid, e, color="#FF7A1A")
        label("WEIGHT", (P0.x - 0.6, LANE_Y - 1.4, 0.3), mid + 2, e, size=0.24, tilt=5, color="#FF7A1A")
        arrow("cg_lift", (P0.x + WING_X, LANE_Y - 1.3, 1.9), (0, 0, 1.0), mid + 6, e)
        label("LIFT", (P0.x + WING_X - 0.6, LANE_Y - 1.4, 3.0), mid + 8, e, size=0.24, tilt=-5, color="#FFD23F")
        tail_spot = V((P0.x - 4.6, LANE_Y - 0.9, 0))                       # just behind the elevator tip
        self.ground_max(b, tail_spot, (P0.x - 3.0, LANE_Y - 0.4, 0))
        toy.hide_tree(self.hammer, b, False)
        toy.hide_tree(self.hammer, e - 4, True)
        self.max.hammer(b + 6, e - 6, hand="R")
        self.rig.shot(b, e, cam_from=(-12.2, -5.0, 2.6), cam_to=(-11.6, -4.6, 2.5), aim_from=(-9.4, LANE_Y - 0.6, 1.1),
                      aim_to=(-9.0, LANE_Y - 0.6, 1.1), lens=22, fstop=8.0, cut=True)

    def a_fail_turn(self, i, b, e):
        pl = self.plane
        L = e - b
        pl.teleport(b, P0)
        self.pilot_on(b)
        t_lift, t_level, t_hit = b + int(L * 0.25), b + int(L * 0.45), b + int(L * 0.78)
        pl.key(b + 4, P0, 0)
        pl.key(t_lift, V((P0.x + 6, LANE_Y, 0.2)), -10)
        pl.roll_wheels(b + 4, t_lift, 6)
        pl.key(t_level, V((P0.x + 9.5, LANE_Y, 4.2)), -6)
        crash = CRASH
        pl.key(t_hit - 4, crash + V((-1.0, 0, 0)), 0)
        pl.key(t_hit, crash, 14, roll=6)
        pl.key(e - 2, crash + V((0.05, 0, -0.08)), 18, roll=8)
        pl.spin(b, t_hit)
        self.engine_noise(b, t_hit)
        events.add(t_hit - 2, "crash_tree")
        leaves = Spray("leaf_burst", toy.noise_material("foliage2", toy.srgb("#3D6B2A"), toy.srgb("#5E8C38"), scale=6),
                       count=36, radius=0.07, seed=5)
        leaves.run(t_hit, e, source=crash + V((2.4, 0, 0.6)), target=crash + V((2.0, 0, -3.0)), spread=1.4, arc=0.8,
                   period=26)
        self.pilot.brows(t_hit, 1.0)
        self.pilot.key("mouth", t_hit + 2, scale=(1.1, 0.6, 2.4))
        self.track_plane(b, e, cam_off=(3.5, -8.5, 0.3), lens=24, dist=10.0, cut=True,
                         hold=(t_hit - 14, (crash.x - 2.2, LANE_Y - 11.0, crash.z - 1.6),
                               (crash.x + 1.6, LANE_Y, crash.z - 0.4)))

    def a_controls(self, i, b, e):
        pl = self.plane
        pl.teleport(b, P0)
        pl.show("controls", b + 4, pop=True)
        w0 = b + int((e - b) * 0.3)
        pl.wiggle(w0, e - 4)
        label("AILERONS", (P0.x + WING_X - 0.9, LANE_Y - 3.2, 2.35), w0 + 2, e, size=0.36, tilt=-5)
        label("ELEVATOR", (P0.x - 3.4, LANE_Y - 1.9, 0.75), w0 + 8, e, size=0.32, tilt=5)
        label("RUDDER", (P0.x - 3.5, LANE_Y - 0.6, 2.75), w0 + 14, e, size=0.32, tilt=-5)
        self.ground_max(b, WORK, (-3.0, -7.5, 0))
        self.max.point(w0, e - 4, hand="R", up_deg=55, side_deg=30)
        self.rig.shot(b, e, cam_from=(-3.4, -6.4, 3.8), cam_to=(-3.8, -5.9, 3.5), aim_from=(-7.6, LANE_Y - 0.6, 1.2),
                      aim_to=(-7.6, LANE_Y - 0.6, 1.2), lens=22, fstop=8.0, cut=True)

    def _kids_cheer(self, f0, f1):
        for k, kid in enumerate(self.kids):
            spot = V((-0.6 + 0.9 * k, -0.6 - 0.3 * k, 0))
            toy.hide_tree(kid.root, f0, False)
            kid.cut_place(f0, spot, 0)
            kid.pose(f0 + 4)
            kid.cheer(f0 + 6, f1)
            kid.smile(f0 + 6, big=True)
            kid.auto_blink(f0, f1 + 400, seed=k + 3)

    def _flyover(self, f0, f1, takeoff=True):
        """Take off, climb, bank into a wide turn and come back low over the kids."""
        pl = self.plane
        L = f1 - f0
        if takeoff:
            pl.teleport(f0, P0)
            pl.key(f0 + 4, P0, 0, 0, 0)
            t_lift = f0 + int(L * 0.2)
            pl.key(t_lift, V((P0.x + 6, LANE_Y, 0.25)), -10)
            pl.roll_wheels(f0 + 4, t_lift, 6)
            pl.key(f0 + int(L * 0.38), V((4.0, LANE_Y + 1.0, 3.6)), -6, 0, 0)
            pl.key(f0 + int(L * 0.55), V((10.0, LANE_Y + 7.0, 4.6)), 0, -35, 70)     # banks into a left turn
            pl.key(f0 + int(L * 0.72), V((6.0, LANE_Y + 10.0, 4.4)), 0, -30, 160)
            pl.key(f0 + int(L * 0.88), V((-0.5, LANE_Y - 0.6, 2.6)), 2, 0, 180)       # low pass over the kids
            pl.key(f1, V((-6.0, LANE_Y - 1.0, 3.2)), -4, 0, 180)
        else:
            pl.teleport(f0, V((4.5, LANE_Y - 0.6, 3.0)), 2, 8, 180)
            pl.key(f1, V((-6.0, LANE_Y - 1.0, 2.6)), 0, -6, 180)
        self.pilot_on(f0)
        self.pilot.wave(f1 - int(L * 0.25), f1, hand="R")
        self.pilot.smile(f0 + 4, big=True)
        pl.spin(f0, f1)
        self.engine_noise(f0, f1)
        events.add(f0 + int(L * 0.35), "plane_flyby")
        events.add(f0 + 6, "kids_cheer", gain=0.8)

    def a_finale(self, i, b, e):
        pl = self.plane
        L = e - b
        self.light(b)
        t_lift, t_land, t_stop = b + int(L * 0.14), b + int(L * 0.58), b + int(L * 0.66)   # a third left for the reunion
        pl.teleport(b, P0)
        pl.key(b + 4, P0, 0, 0, 0)
        pl.key(t_lift, V((P0.x + 5.5, LANE_Y, 0.25)), -10, 0, 0)
        pl.roll_wheels(b + 4, t_lift, 5.5)
        pl.key(b + int(L * 0.24), V((2.5, LANE_Y + 0.8, 3.2)), -6, -20, 20)        # climbs, banks left
        pl.key(b + int(L * 0.33), V((7.5, LANE_Y + 6.0, 4.0)), 0, -35, 95)
        pl.key(b + int(L * 0.42), V((3.0, LANE_Y + 9.0, 3.8)), 0, -30, 170)
        pl.key(b + int(L * 0.50), V((5.0, LANE_Y, 1.8)), 3, -10, 180)              # lines up with the strip
        pl.key(t_land, V((1.5, LANE_Y, 0.02)), -4, 0, 180)                        # touchdown
        pl.key(t_stop, V((-1.2, LANE_Y, 0)), 0, 0, 180)                           # rolls to a stop
        pl.roll_wheels(t_land, t_stop, 2.7)
        pl.spin(b, t_stop + 20)
        self.pilot_on(b)
        self.pilot.smile(b + 4, big=True)
        self.pilot.pose(t_stop + 6, shoulderL=(-150, 0, 0))                      # thumbs up / wave
        self.pilot.wave(t_stop + 8, e, hand="L")
        self.engine_noise(b, t_stop + 20)
        events.add(b + int(L * 0.42), "plane_flyby")
        # the kids watch, then run to the plane
        for k, kid in enumerate(self.kids):
            spot = V((-3.0 + 0.8 * k, -2.9 - 0.2 * k, 0))
            toy.hide_tree(kid.root, b, False)
            kid.cut_place(b, spot, 0)
            kid.pose(b + 4)
            kid.cheer(b + 6, t_land)
            kid.auto_blink(b, e + 400, seed=k + 3)
            dest = V((-1.9 - 0.7 * k, 0.5 - 0.3 * k, 0))                       # by the cockpit, ahead of the wing
            arrive = t_stop + 20 + 3 * k
            kid.walk(t_stop + 2 + 3 * k, arrive, to=dest, facing_deg=facing_to(spot, dest), step_frames=4)  # they RUN
            kid.turn(arrive + 1, facing_to(dest, (0.6, LANE_Y - 6.6, 0)), frames=6)   # turn to the viewer
            kid.cheer(arrive + 6, e)
            kid.smile(arrive + 2, big=True)
        events.add(t_land, "kids_cheer")
        events.add(t_stop + 24, "kids_cheer", gain=0.8)
        self.track_plane(b, e, cam_off=(-3.0, -9.5, 0.0), lens=24, dist=12.0, cut=True, cam_z=1.4, smooth=14,
                         hold=(t_land - 6, (0.6, LANE_Y - 6.6, 1.3), (-2.0, LANE_Y - 0.8, 1.15)))

    # ------------------- hooks (epilogue) -------------------

    def a_tree_hook(self, i, h0, h1):
        pl = self.plane
        crash = CRASH
        pl.teleport(h0, crash, 16, roll=7)
        pl.key(h1, crash + V((0.03, 0, -0.06)), 19, roll=8)
        self.pilot_on(h0)
        for kid in self.kids:
            toy.hide_tree(kid.root, h0, True)
        leaves = Spray("hook_leaves", toy.noise_material("foliage2", toy.srgb("#3D6B2A"), toy.srgb("#5E8C38"), scale=6),
                       count=24, radius=0.07, seed=9)
        leaves.run(h0, h1, source=crash + V((2.4, 0, 0.8)), target=crash + V((2.0, 0, -3.4)), spread=1.6, arc=0.2,
                   period=40)
        self.pilot.blink([h0 + 12, h0 + 30, h0 + 44])
        self.pilot.brows(h0 + 4, 1.0)
        events.add(h0, "crash_tree", gain=0.6)
        events.add(h0 + 14, "boing", gain=0.4)
        self.rig.shot(h0, h1, cam_from=(crash.x - 1.6, LANE_Y - 7.8, crash.z - 0.7),
                      cam_to=(crash.x - 0.8, LANE_Y - 6.2, crash.z - 0.5), aim_from=(crash.x + 1.4, LANE_Y, crash.z + 0.1),
                      aim_to=(crash.x + 1.2, LANE_Y, crash.z + 0.2), lens=26, fstop=8.0, cut=True)

    def a_fly_hook(self, i, h0, h1):
        self.light(h0)
        self._flyover(h0, h1, takeoff=False)
        self._kids_cheer(h0, h1)
        self.rig.shot(h0, h1, cam_from=(-0.4, -4.6, 0.7), cam_to=(-0.9, -4.4, 0.8), aim_from=(1.2, LANE_Y - 0.6, 2.0),
                      aim_to=(-0.8, LANE_Y - 0.8, 1.8), lens=20, fstop=8.0, cut=True)
