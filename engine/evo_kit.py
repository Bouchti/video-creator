"""
EVOLUTION KIT — the reusable toolkit every "evolution" set is built from (runs inside Blender).

An evolution set is one continuous world seen from drone height where something gets smarter
beat after beat (see engine/sets/bridge_evolution.py for the reference set). This kit gives:

  helpers      pop_in / fly_in / fall / show_between, attach, beam, base_box, extrude_xz, mesh_obj
  pen strokes  stroke() + draw_on(): the white line-drawings (arrows, outlines, wind streaks)
  EvolutionSet base class: shared materials palette, the river valley (two banks that can slide
               apart with widen(), forest, roads, a village, clouds), a sailing ship, cars and
               traffic windows, camera shots, sun/sky keys, splash and dust puffs, wind streaks,
               and the action driver (one a_<action>(i, b, e) method per action in the spec).

A new set subclasses EvolutionSet, sets ACTIONS / START_GAP, builds its models (hidden) in
build(), and animates them in its a_<action> methods.
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from engine import events, textures as tx, toy
from engine.camera import CameraRig
from engine.machines import Puffs

V = Vector
R = math.radians
WATER_Z = -4.0                       # river surface; the bank tops are at z = 0
BANK_DEPTH = 9.0
ORANGE = "#C4452C"                   # "international orange" steel

# ------------------- small helpers -------------------

def _key(obj, frame, **props):
    for name, value in props.items():
        setattr(obj, name, value)
        obj.keyframe_insert(name, frame=int(frame))


def _hide(obj, frame, hidden):
    obj.hide_render = hidden
    obj.hide_viewport = hidden
    obj.keyframe_insert("hide_render", frame=int(frame))
    obj.keyframe_insert("hide_viewport", frame=int(frame))


def show_between(obj, f0, f1=None):
    """Visible only in [f0, f1) (whole hierarchy)."""
    toy.hide_tree(obj, 0, True)
    toy.hide_tree(obj, int(f0), False)
    if f1 is not None:
        toy.hide_tree(obj, int(f1), True)


def pop_in(obj, f, frames=7, final=None, gone=None):
    """Pop an object into existence with a small overshoot (hidden before f, after `gone`)."""
    final = V(final or obj.scale)
    toy.hide_tree(obj, 0, True)
    toy.hide_tree(obj, int(f), False)
    _key(obj, f, scale=final * 0.01)
    _key(obj, f + int(frames * 0.7), scale=final * 1.06)
    _key(obj, f + frames, scale=final)
    if gone is not None:
        toy.hide_tree(obj, int(gone), True)


def fly_in(obj, f0, f1, offset, spin=0.0, gone=None):
    """Object arrives at its current location from location+offset between f0 and f1."""
    home = V(obj.location)
    rot = V(obj.rotation_euler)
    toy.hide_tree(obj, 0, True)
    toy.hide_tree(obj, int(f0), False)
    _key(obj, f0, location=home + V(offset), rotation_euler=rot + V((0, spin, 0)))
    _key(obj, f1, location=home, rotation_euler=rot)
    if gone is not None:
        toy.hide_tree(obj, int(gone), True)


def fall(obj, f0, f1, drop, rnd, spin=60.0, drift=2.0):
    """Hold, then tumble into the river and vanish under the surface."""
    toy.key_hold(obj, "location", f0)
    toy.key_hold(obj, "rotation_euler", f0)
    loc = V(toy.value_at(obj, "location", f0))
    rot = V(toy.value_at(obj, "rotation_euler", f0))
    _key(obj, f1, location=loc + V((rnd.uniform(-drift, drift), rnd.uniform(-drift, drift), -drop)),
         rotation_euler=rot + V([R(rnd.uniform(-spin, spin)) for _ in range(3)]))
    toy.hide_tree(obj, int(f1) + 1, True)


def attach(child, parent):
    """Parent without moving the child, computed from the (top-level) parent's own transform, so it
    does not depend on Blender having updated matrix_world yet."""
    pm = Matrix.LocRotScale(V(parent.location), parent.rotation_euler, V(parent.scale))
    cw = Matrix.LocRotScale(V(child.location), child.rotation_euler, V(child.scale))
    child.parent = parent
    child.matrix_parent_inverse = Matrix.Identity(4)
    child.matrix_basis = pm.inverted() @ cw


def mat(name, hexc, rough=0.5, **kw):
    return toy.material(name, toy.srgb(hexc), roughness=rough, **kw)


def emissive(name, hexc="#FFFFFF", strength=4.0):
    if name in toy._materials:
        return toy._materials[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*toy.srgb(hexc), 1)
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    toy._materials[name] = m
    return m


def mesh_obj(name, verts, faces, material=None, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.update()
    if smooth:
        me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if material is not None:
        me.materials.append(material)
    return ob


def extrude_xz(name, outline, y0, y1, material=None):
    """A polygon drawn in the XZ plane, extruded along Y from y0 to y1."""
    n = len(outline)
    verts = [(x, y0, z) for x, z in outline] + [(x, y1, z) for x, z in outline]
    faces = [list(range(n)), list(range(n, 2 * n))]
    faces += [[k, (k + 1) % n, n + (k + 1) % n, n + k] for k in range(n)]
    return mesh_obj(name, verts, faces, material)


def base_box(name, sx, sy, h, base, material=None):
    """Box whose origin is at the centre of its BASE (so scaling z grows it upwards)."""
    x, y = sx / 2, sy / 2
    verts = [(-x, -y, 0), (x, -y, 0), (x, y, 0), (-x, y, 0), (-x, -y, h), (x, -y, h), (x, y, h), (-x, y, h)]
    faces = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    ob = mesh_obj(name, verts, faces, material)
    ob.location = base
    return ob


def beam(name, a, b, t, material, tw=None):
    """A square bar from point a to point b (origin in the middle)."""
    a, b = V(a), V(b)
    d = b - a
    ob = toy.box(name, (tw or t, t, d.length), (a + b) / 2, mat=material, bevel=0)
    ob.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    return ob


def stroke(name, pts, width=0.12, closed=False, material=None, parent=None):
    """An emissive white line (a 'pen stroke') through pts; draw it on with draw_on()."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = width
    cu.bevel_resolution = 2
    cu.use_fill_caps = True
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for p, c in zip(sp.points, pts):
        p.co = (*c, 1.0)
    sp.use_cyclic_u = closed
    cu.bevel_factor_mapping_start = "SPLINE"
    cu.bevel_factor_mapping_end = "SPLINE"
    ob = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(ob)
    cu.materials.append(material or emissive("ev_ink"))
    ob.visible_shadow = False
    if parent is not None:
        ob.parent = parent
    return ob


def draw_on(ob, f0, f1, erase=None, erase_frames=10):
    """Animate a stroke drawing itself (f0→f1), optionally erasing from its tail at `erase`."""
    cu = ob.data
    cu.bevel_factor_start, cu.bevel_factor_end = 0.0, 0.0
    cu.keyframe_insert("bevel_factor_end", frame=int(f0))
    cu.keyframe_insert("bevel_factor_start", frame=int(f0))
    cu.bevel_factor_end = 1.0
    cu.keyframe_insert("bevel_factor_end", frame=int(f1))
    if erase is not None:
        cu.keyframe_insert("bevel_factor_start", frame=int(erase))
        cu.bevel_factor_start = 1.0
        cu.keyframe_insert("bevel_factor_start", frame=int(erase + erase_frames))


def face_camera(obj, cam_pos):
    """Orient obj so its local XY plane faces cam_pos (local +Z toward the camera, +Y up)."""
    d = V(cam_pos) - V(obj.location)
    obj.rotation_euler = d.to_track_quat("Z", "Y").to_euler()


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def beat_actions(beat: dict) -> list:
    return list(beat.get("actions") or [beat.get("action")])


# ------------------- the base set -------------------

class EvolutionSet:
    ACTIONS = {}
    START_GAP = 6.0                   # river width at frame 1 (m); RIVER = False for dry land only
    RIVER = True
    VILLAGE = True
    TRAFFIC = {"x_from": 95.0, "z": 0.55, "lanes": ((-2.2, 1), (2.2, -1)), "speed": 0.55}

    def __init__(self, scene, sun, fill, bg, total):
        self.scene, self.sun, self.fill, self.bg, self.total = scene, sun, fill, bg, total
        self.rig = CameraRig(blend=18)
        self.rig.data.clip_end = 6000
        self.rig.data.clip_start = 0.3
        self.rnd = random.Random(11)
        self.cars = []
        self.traffic_windows = []
        self._materials()
        self._world()
        self.build()
        for o in bpy.data.objects:                                   # big ground pieces only receive shadows
            if o.type == "MESH" and o.name.startswith(("bank_ground", "river", "cloud")):
                o.visible_shadow = False

    def build(self):
        """Subclasses build their models here (hidden; the actions reveal and animate them)."""

    # ------------------- materials -------------------

    def _materials(self):
        self.m_grass = self._grass_material()
        self.m_dirt = toy.noise_material("ev_dirt", toy.srgb("#8A6D4B"), toy.srgb("#A3855E"), scale=40, bump=0.3)
        self.m_asphalt = toy.noise_material("ev_asphalt", toy.srgb("#3A3C40"), toy.srgb("#4A4C51"), scale=60,
                                            roughness=0.85, bump=0.1)
        self.m_stone = toy.noise_material("ev_stone", toy.srgb("#B9AE9A"), toy.srgb("#D3C9B4"), scale=14, bump=0.5)
        self.m_stone2 = toy.noise_material("ev_stone2", toy.srgb("#A89C86"), toy.srgb("#C4B8A0"), scale=9, bump=0.6)
        self.m_concrete = toy.noise_material("ev_concrete", toy.srgb("#9C9A94"), toy.srgb("#B5B2AA"), scale=20,
                                             bump=0.25)
        self.m_plank = tx.planks("ev_planks", "#7A5634", "#93693F", width=0.3, across="x", along="y")
        self.m_log = tx.wood("ev_log", "#5B4128", "#7A5A38", along="x")
        self.m_steel = tx.paint("ev_steel", ORANGE, rough=0.45, coat=0.2)
        self.m_steel_dark = tx.paint("ev_steel_dark", "#9E3622", rough=0.5, coat=0.1)
        self.m_white_steel = tx.paint("ev_white_steel", "#E9E6DF", rough=0.45, coat=0.2)
        self.m_rail = tx.metal("ev_rail", "#8E9196", 0.3, along="x")
        self.m_line = mat("ev_roadline", "#F2F2EC", 0.6)
        self.m_wall = tx.planks("ev_cottage", "#E6DCC5", "#D9CDB2", width=0.4, rough=0.85)
        self.m_thatch = toy.noise_material("ev_thatch", toy.srgb("#B8955C"), toy.srgb("#CFAE70"), scale=25, bump=0.8)
        self.m_ink = emissive("ev_ink")
        self.m_ink_orange = emissive("ev_ink_orange", "#FFB23A", 3.0)
        self.m_water = self._water_material()

    def _grass_material(self):
        """Meadow seen from the air: big soft patches + fine mottling, in OBJECT space (generated
        coordinates stretch over the 4 km bank boxes and the bevel)."""
        m = bpy.data.materials.new("ev_grass")
        m.use_nodes = True
        nt = m.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        coord = nt.nodes.new("ShaderNodeTexCoord")
        big = nt.nodes.new("ShaderNodeTexNoise")
        big.inputs["Scale"].default_value = 0.035
        big.inputs["Detail"].default_value = 4
        fine = nt.nodes.new("ShaderNodeTexNoise")
        fine.inputs["Scale"].default_value = 0.9
        fine.inputs["Detail"].default_value = 6
        for n in (big, fine):
            nt.links.new(coord.outputs["Object"], n.inputs["Vector"])
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (*toy.srgb("#4C7A2B"), 1)
        ramp.color_ramp.elements[1].color = (*toy.srgb("#8DAE4C"), 1)
        ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = 0.3, 0.72
        mix = nt.nodes.new("ShaderNodeMath")
        mix.operation = "MULTIPLY_ADD"
        nt.links.new(fine.outputs["Fac"], mix.inputs[0])
        mix.inputs[1].default_value = 0.35
        nt.links.new(big.outputs["Fac"], mix.inputs[2])
        add = nt.nodes.new("ShaderNodeMath")
        add.operation = "SUBTRACT"
        nt.links.new(mix.outputs[0], add.inputs[0])
        add.inputs[1].default_value = 0.17
        nt.links.new(add.outputs[0], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.2
        nt.links.new(fine.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        toy._set(bsdf, "Roughness", 0.92)
        return m

    def _water_material(self):
        m = bpy.data.materials.new("ev_river")
        m.use_nodes = True
        nt = m.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        toy._set(bsdf, "Base Color", (*toy.srgb("#163B40"), 1))
        toy._set(bsdf, "Roughness", 0.06)
        toy._set(bsdf, "Specular IOR Level", 0.6)
        coord = nt.nodes.new("ShaderNodeTexCoord")
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 0.35
        noise.inputs["Detail"].default_value = 6
        nt.links.new(coord.outputs["Object"], noise.inputs["Vector"])
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.08
        nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        return m

    # ------------------- world -------------------

    def _world(self):
        """Two banks (rigs that widen() can slide apart) with a river between them. RIVER = False:
        the banks meet (flat land, START_GAP ignored) and there is no water."""
        g0 = self.START_GAP / 2 if self.RIVER else 0.0
        if self.RIVER:
            bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, WATER_Z))
            river = bpy.context.active_object
            river.name = "river"
            river.scale = (5000, 5000, 1)
            river.data.materials.append(self.m_water)
        self.banks = {}
        for side, sgn in (("L", -1), ("R", 1)):
            root = toy.empty(f"bank_{side}", (sgn * g0, 0, 0))
            ground = toy.box(f"bank_ground_{side}", (4000, 5000, BANK_DEPTH),
                             (sgn * 2000, 0, -BANK_DEPTH / 2), mat=self.m_grass, bevel=0)
            if self.RIVER:                                              # rounded, grassy river edge
                bev = ground.modifiers.new("Bank", "BEVEL")
                bev.width, bev.segments, bev.limit_method = 2.6, 6, "ANGLE"
            attach(ground, root)
            ground.location = (sgn * 2000, 0, -BANK_DEPTH / 2)
            self.banks[side] = root
        # roads: a dirt track first, an asphalt road from the suspension bridge on
        self.roads = {}
        for side, sgn in (("L", -1), ("R", 1)):
            root = self.banks[side]
            dirt = toy.box(f"road_dirt_{side}", (600, 3.4, 0.08), (0, 0, 0), mat=self.m_dirt, bevel=0)
            dirt.parent = root
            dirt.location = (sgn * 302.5, 0, 0.03)
            asph = toy.box(f"road_asphalt_{side}", (600, 11.0, 0.1), (0, 0, 0), mat=self.m_asphalt, bevel=0)
            asph.parent = root
            asph.location = (sgn * 302.5, 0, 0.04)
            self.roads[side] = (dirt, asph)
        self._forest()
        if self.VILLAGE:
            self._village()
        self._clouds()

    def _tree_meshes(self):
        """Low-poly conifer (two stacked cones) and broadleaf (lumpy ball on a stub), base at z=0."""
        def cone(cx, r, z0, h, n=8):
            vs = [(cx[0] + r * math.cos(2 * math.pi * k / n), cx[1] + r * math.sin(2 * math.pi * k / n), z0)
                  for k in range(n)]
            return vs + [(cx[0], cx[1], z0 + h)]
        verts, faces = [], []
        for r, z0, h in ((2.4, 0.3, 5.4), (1.7, 3.4, 4.6), (1.0, 6.2, 3.4)):
            base = len(verts)
            verts += cone((0, 0), r, z0, h)
            faces += [(base + k, base + (k + 1) % 8, base + 8) for k in range(8)]
            faces.append(tuple(base + k for k in range(8)))
        conifers = []
        for k, hexc in enumerate(("#2E5B2C", "#3B6B30", "#284F2A")):
            conifers.append(mesh_obj(f"tree_conifer{k}", verts, faces,
                                     toy.noise_material(f"ev_pine{k}", toy.srgb(hexc),
                                                        toy.srgb("#4F7F3A" if k != 2 else "#365E30"),
                                                        scale=3, bump=0.6)))
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=3.0, location=(0, 0, 0))
        ball = bpy.context.active_object
        ball.name = "tree_broadleaf"
        rnd = random.Random(5)
        for v in ball.data.vertices:
            v.co *= 1 + rnd.uniform(-0.12, 0.12)
            v.co.z = v.co.z * 0.85 + 4.4
        ball.data.materials.append(toy.noise_material("ev_leaf", toy.srgb("#557F2E"), toy.srgb("#7FA347"), scale=2,
                                                      bump=0.8))
        return conifers + [ball]

    def _forest(self):
        kinds = self._tree_meshes()
        g0 = self.START_GAP / 2
        seed = 1
        for side, sgn in (("L", -1), ("R", 1)):
            root = self.banks[side]
            # zones in bank-local x (distance from the river edge) and world y
            zones = [(8, 700, 18, 800), (8, 700, -800, -18)] if side == "R" else \
                    [(8, 700, 70, 800), (48, 700, 16, 70), (8, 700, -800, -18)]
            for (d0, d1, y0, y1) in zones:
                x0, x1 = sorted((sgn * (g0 + d0), sgn * (g0 + d1)))
                for k, (inst, dens) in enumerate(zip(kinds, (0.0035, 0.0025, 0.002, 0.0016))):
                    seed += 3
                    sc = toy.scatter(f"forest_{side}_{seed}", x0, x1, y0, y1, inst, dens, size=1.0,
                                     size_random=0.45, z=0.0, seed=seed, tilt=0.06)
                    attach(sc, root)
                # a denser belt of trees along the water's edge: the river reads as a river
            belt = (sgn * (g0 + 3), sgn * (g0 + 14))
            for k, inst in enumerate(kinds[:2]):
                for (y0, y1) in ((24, 800), (-800, -22)):
                    seed += 3
                    sc = toy.scatter(f"belt_{side}_{seed}", min(belt), max(belt), y0, y1, inst, 0.012,
                                     size=0.9, size_random=0.4, z=0.0, seed=seed, tilt=0.05)
                    attach(sc, root)
        for o in kinds:
            o.hide_render = True
            o.hide_viewport = True

    def _village(self):
        """A few thatched cottages and a fence on the left bank, near the first crossing."""
        root = self.banks["L"]
        g0 = self.START_GAP / 2
        rnd = random.Random(3)
        spots = [(-12, 24, 8), (-22, 34, -10), (-14, 46, 4), (-30, 22, 15), (-34, 48, -6), (-24, 58, 12)]
        for k, (dx, y, rot) in enumerate(spots):
            w, d, h = rnd.uniform(7, 9.5), rnd.uniform(5, 6.2), rnd.uniform(2.6, 3.2)
            house = toy.empty(f"cottage{k}", (-g0 + dx, y, 0))
            house.rotation_euler = (0, 0, R(rot))
            walls = base_box(f"cottage{k}_walls", w, d, h, (0, 0, 0), self.m_wall)
            walls.parent = house
            roof_h = d * 0.62
            roof = extrude_xz(f"cottage{k}_roof", [(-d / 2 - 0.5, h - 0.2), (d / 2 + 0.5, h - 0.2), (0, h + roof_h)],
                              -w / 2 - 0.45, w / 2 + 0.45, self.m_thatch)
            roof.parent = house
            roof.rotation_euler = (0, 0, R(90))
            ch = base_box(f"cottage{k}_chimney", 0.8, 0.8, 1.6, (w * 0.28, 0, h + roof_h * 0.45), self.m_stone2)
            ch.parent = house
            attach(house, root)
        fence = tx.wood("ev_fence", "#6A5038", "#7E6244", along="x")
        for k in range(14):
            post = base_box(f"fence_post{k}", 0.18, 0.18, 1.1, (-g0 - 6 - k * 2.2, 14, 0), fence)
            attach(post, root)
        rail = toy.box("fence_rail", (29, 0.1, 0.12), (-g0 - 6 - 14.3, 14, 0.8), mat=fence, bevel=0)
        attach(rail, root)

    def _clouds(self):
        cloud = toy.material("ev_cloud", (1, 1, 1), roughness=1.0)
        r3 = random.Random(9)
        for i in range(16):
            root = toy.empty(f"cloudset_{i}", (r3.uniform(-900, 900), r3.uniform(500, 1400), r3.uniform(140, 260)))
            for k in range(6):
                pc = toy.sphere(f"cloud_{i}_{k}", r3.uniform(28, 48), (0, 0, 0), scale=(1.5, 1.0, 0.62), mat=cloud,
                                subdiv=1, segments=16, rings=8)
                pc.parent = root
                pc.location = (r3.uniform(-60, 60), r3.uniform(-20, 20), r3.uniform(-8, 14))
            root.keyframe_insert("location", frame=1)
            root.location.x += 120
            root.keyframe_insert("location", frame=6000)
            toy.set_interpolation(root, "location", (1,), "LINEAR")


    def _ship(self):
        """A small three-masted sailing ship that works its way down the river through the film."""
        self.ship = toy.empty("ship", (0, 420, WATER_Z))
        hull_c = tx.planks("ev_hull", "#5A3B22", "#6B4628", width=0.3, across="z", along="x")
        L, Wd, Hh = 16.0, 4.2, 2.6
        outline = [(-L / 2, 0.4), (L / 2 - 2.5, 0.4), (L / 2 + 1.2, Hh), (-L / 2 - 0.4, Hh + 0.3)]
        hull = extrude_xz("ship_hull", [(x, z - 1.0) for x, z in outline], -Wd / 2, Wd / 2, hull_c)
        hull.parent = self.ship
        sail = mat("ev_sail", "#F1E9D6", 0.8)
        mast_m = tx.wood("ev_mast", "#4E3A26", "#62492F", along="z")
        for k, (x, h) in enumerate(((-4.5, 10), (0.5, 13), (5.2, 10))):
            m_ = toy.cylinder(f"ship_mast{k}", 0.16, h, (x, 0, Hh + h / 2 - 1.0), mat=mast_m, vertices=8)
            m_.parent = self.ship
            for j, (zz, w) in enumerate(((0.38, 3.6), (0.7, 2.9))):
                sl = toy.box(f"ship_sail{k}{j}", (0.12, w, h * 0.27), (x + 0.2, 0, Hh - 1.0 + h * zz), mat=sail,
                             bevel=0.05)
                sl.parent = self.ship
        self.ship.rotation_euler = (0, 0, R(-90))                   # bow points down the river (-y)
        toy.add_noise(self.ship, "rotation_euler", 0, strength=0.025, scale=35)
        toy.hide_tree(self.ship, 0, True)

    def _cars(self):
        self.cars = []
        for k, hexc in enumerate(("#D9A441", "#C33C2B", "#E8E6E0", "#3B6EA5", "#2E2F33", "#D9A441", "#5C8C4A")):
            car = toy.empty(f"car{k}", (0, 0, -200))
            body = toy.box(f"car{k}_body", (4.3, 1.85, 0.75), (0, 0, 0), mat=mat(f"ev_car{k}", hexc, 0.3, coat=0.6),
                           bevel=0.12)
            body.parent = car
            body.location = (0, 0, 0.62)
            cab = toy.box(f"car{k}_cab", (2.3, 1.65, 0.62), (0, 0, 0), mat=mat("ev_glass", "#2B3440", 0.1), bevel=0.12)
            cab.parent = car
            cab.location = (-0.25, 0, 1.25)
            self.cars.append(car)


    # ------------------- driver -------------------

    def run(self, beats, spans):
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
        self.span_of = dict(zip(self.acts, self.spans))
        self.traffic_windows = []
        for i, a in enumerate(self.acts):
            getattr(self, f"a_{a}")(i, *self.spans[i])
        if self.cars:
            self._traffic()
        self.rig.build(handheld=0)
        # handheld drift, keyed from the camera's REAL frame-1 pose (toy.add_noise keys frame 1 with the
        # current value, which after build() is the last shot's position)
        for obj, strength, ph in ((self.rig.cam, 0.12, 3), (self.rig.aim, 0.07, 14)):
            obj.location = toy.value_at(obj, "location", 1)
            for axis in (0, 2):
                toy.add_noise(obj, "location", axis, strength=strength, scale=45, phase=ph + axis)

    # ------------------- helpers used by the actions -------------------

    def widen(self, f0, f1, g_from, g_to):
        for side, sgn in (("L", -1), ("R", 1)):
            root = self.banks[side]
            _key(root, f0, location=V((sgn * g_from / 2, 0, 0)))
            _key(root, f1, location=V((sgn * g_to / 2, 0, 0)))
        events.add(f0, "rumble", duration=f1 - f0, gain=0.8)

    def splash(self, name, f, at, size=1.2, n=10, rise=4.0):
        Puffs(name, "#EEF6F7", count=n, size=size, seed=len(name)).emit(
            range(f, f + 2 * n, 2), lambda _f: V(at) + V((self.rnd.uniform(-1.5, 1.5), self.rnd.uniform(-1.5, 1.5), 0)),
            rise=rise, life=20, drift=1.2)
        events.add(f, "splash", gain=0.9)

    def dust(self, name, f, at, size=0.6, n=8):
        Puffs(name, "#D8CDB8", count=n, size=size, seed=len(name)).emit(range(f, f + n * 2, 2), lambda _f: V(at),
                                                                         rise=1.4, life=18, drift=0.8)

    def shot(self, f0, f1, cam_from, aim_from, cam_to=None, aim_to=None, lens=24, cut=False):
        self.rig.shot(f0, f1, cam_from=cam_from, cam_to=cam_to or cam_from, aim_from=aim_from,
                      aim_to=aim_to or aim_from, lens=lens, fstop=11.0, cut=cut)

    def sun_key(self, f, energy=None, color=None, bg=None):
        if energy is not None:
            self.sun.data.energy = energy
            self.sun.data.keyframe_insert("energy", frame=int(f))
        if color is not None:
            self.sun.data.color = color
            self.sun.data.keyframe_insert("color", frame=int(f))
        if bg is not None:
            self.bg.default_value = bg
            self.bg.keyframe_insert("default_value", frame=int(f))


    def _wind_streaks(self, name, f0, f1, n=12, cycles=2):
        rnd = random.Random(len(name))
        per = max(16, (f1 - f0) // cycles)
        for k in range(n):
            x = rnd.uniform(-55, 55)
            z = rnd.uniform(2.0, 16.0)
            amp = rnd.uniform(0.4, 1.2)
            pts = [(x + 3.0 * math.sin(j * 0.6 + k), -70 + j * 7, z + amp * math.sin(j * 0.9 + k)) for j in range(21)]
            ob = stroke(f"{name}{k}", pts, width=0.13)
            show_between(ob, f0, f1 + 1)
            cu = ob.data
            for c in range(cycles):
                s = f0 + c * per + rnd.randint(0, per // 2)
                if s + 18 > f1:
                    break
                cu.bevel_factor_start, cu.bevel_factor_end = 0.0, 0.0
                cu.keyframe_insert("bevel_factor_start", frame=s)
                cu.keyframe_insert("bevel_factor_end", frame=s)
                cu.bevel_factor_end = 1.0
                cu.keyframe_insert("bevel_factor_end", frame=s + 12)
                cu.bevel_factor_start = 1.0
                cu.keyframe_insert("bevel_factor_start", frame=s + 18)
                cu.bevel_factor_end = 1.0
                cu.keyframe_insert("bevel_factor_end", frame=s + 18)


    # ------------------- traffic -------------------

    def _traffic(self):
        """Cars cross the suspension bridge in both lanes during each traffic window. A window with a
        stop position makes the cars brake there (the heat buckle) instead of crossing."""
        T = self.TRAFFIC
        speed, lanes, z, reach = T["speed"], T["lanes"], T["z"], T["x_from"]   # speed: m per frame
        rnd = random.Random(31)
        for car in self.cars:
            toy.hide_tree(car, 0, True)
        for (w0, w1, stop) in self.traffic_windows:
            for k, car in enumerate(self.cars):
                y, d = lanes[k % 2]
                start = w0 + rnd.randint(0, 25) + (k // 2) * 22
                if start >= w1 - 4:
                    continue
                x0 = -d * reach
                if stop is not None:
                    if k > 1:
                        continue
                    x_stop = d * stop
                    t_stop = start + int(abs(x_stop - x0) / speed)
                    toy.hide_tree(car, start, False)
                    _key(car, start, location=V((x0, y, z)), rotation_euler=V((0, 0, 0 if d > 0 else math.pi)))
                    _key(car, min(w1 - 1, t_stop), location=V((x_stop, y, z)))
                    toy.hide_tree(car, w1, True)
                    continue
                t_end = start + int(2 * reach / speed)
                toy.hide_tree(car, start, False)
                _key(car, start, location=V((x0, y, z)), rotation_euler=V((0, 0, 0 if d > 0 else math.pi)))
                _key(car, t_end, location=V((-x0, y, z)))
                toy.set_interpolation(car, "location", (start,), "LINEAR")
                toy.hide_tree(car, min(t_end, w1), True)
            events.add(w0, "traffic", duration=w1 - w0, gain=0.5)
