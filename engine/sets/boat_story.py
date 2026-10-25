"""
BOAT STORY set — Blender builder (see boat_story_spec.py). Max builds a steel boat: a solid slab
that sinks, a hollow hull that floats (Archimedes), a top-heavy cabin that capsizes until a heavy
keel rights it, a leak that floods everything until watertight bulkheads contain it, and drifting
until a propeller and rudder drive it. Side-on cutaway: the lake is sliced at y=0 so we see above
and below the waterline, and the hull is cut along its centreline so we see inside it.

The lake water is carved by a hidden copy of the hull (boolean), so the water is visibly pushed
aside by the boat and never shows up inside a dry hull.
"""
import math
import random

import bmesh
import bpy
from mathutils import Vector

from engine import events, textures as tx, toy
from engine.backyard import _appear, _hide, _key
from engine.camera import CameraRig, facing_to
from engine.character import Character
from engine.cutaway import _grass_tuft
from engine.machines import Puffs, Spray
from engine.sets.boat_story_spec import ACTIONS, beat_actions
from engine.sets.nuclear_story import Sparks, glow_material
from engine.sets.plane_story import arrow, label

V = Vector
R = math.radians
BED = -2.6                          # lake bed (water from BED up to z = 0)
LAKE_X0, LAKE_X1, LAKE_Y1 = -9.0, 50.0, 34.0
L, W, D, HF = 4.6, 1.7, 0.75, 0.55   # hull length, width, draft below the waterline, freeboard
XB = L / 2 - 1.3                     # where the bow starts to taper
BOAT_X = -3.5                        # moored next to the dock
BOAT_Y = 0.95                        # the boat floats just BEHIND the lake's cut face: fully in the water
DOCK_TOP = 0.35
DOCK_SPOT = V((-7.0, 0.6, DOCK_TOP))
AWAY = V((0, 0, 40))                 # where the boat waits before it exists (its water-carver too)
BULK_X = (-0.75, 0.55)               # watertight bulkheads (hull-local x)


def _mat(name, hexc, rough=0.5, **kw):
    return toy.material(name, toy.srgb(hexc), roughness=rough, **kw)


def water_volume_material(name="lake_water", density=0.55, color="#2B86C9", scatter=0.12):
    """Water as a VOLUME (no surface): tints whatever is inside it, deeper = bluer, with a soft haze.
    No transparency dithering, so nothing seen through the water shimmers frame to frame."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    absorb = nt.nodes.new("ShaderNodeVolumeAbsorption")
    absorb.inputs["Color"].default_value = (*toy.srgb(color), 1)
    absorb.inputs["Density"].default_value = density
    scat = nt.nodes.new("ShaderNodeVolumeScatter")
    scat.inputs["Color"].default_value = (*toy.srgb("#BFE6F5"), 1)
    scat.inputs["Density"].default_value = scatter
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(absorb.outputs[0], add.inputs[0])
    nt.links.new(scat.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs["Volume"])
    return mat


def water_surface_material():
    """The rippling surface sheet: a glossy, softly transparent skin (the ONLY blended surface)."""
    mat = bpy.data.materials.new("lake_surface")
    bsdf = toy._principled(mat)
    toy._set(bsdf, "Base Color", (*toy.srgb("#5CC4E6"), 1))
    toy._set(bsdf, "Roughness", 0.18)                 # not mirror-sharp: no sparkling ripples
    toy._set(bsdf, "Alpha", 0.55)
    toy._set(bsdf, "IOR", 1.33)
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"         # one blended object only: nothing to re-sort
    if hasattr(mat, "use_backface_culling"):
        mat.use_backface_culling = True
    return mat


def splash_material():
    mat = bpy.data.materials.new("splash_drops")
    bsdf = toy._principled(mat)
    toy._set(bsdf, "Base Color", (*toy.srgb("#CFEFFA"), 1))
    toy._set(bsdf, "Roughness", 0.1)
    toy._set(bsdf, "Coat Weight", 0.6)
    return mat


def hull_mask(nt, ref, grow=0.03, top=0.9):
    """Shader socket: 1 inside the hull's volume (approximate plan + keel profile), 0 outside, in the
    space of `ref` (an object that moves/tilts with the boat). Replaces boolean cuts, which were
    re-meshed every frame and flickered."""
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.object = ref
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    x, y, z = sep.outputs["X"], sep.outputs["Y"], sep.outputs["Z"]

    def m(op, a, b=0.0, clamp=False):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation, n.use_clamp = op, clamp
        for sock, v in zip(n.inputs, (a, b)):
            if isinstance(v, bpy.types.NodeSocket):
                nt.links.new(v, sock)
            else:
                sock.default_value = v
        return n.outputs[0]

    t = m("DIVIDE", x, L / 2)
    tb = m("MAXIMUM", t, 0.0)                                                # 0..1 toward the bow
    w = m("ADD", m("MULTIPLY", m("SUBTRACT", 1.0, m("POWER", m("MINIMUM", tb, 1.0), 1.7)), W / 2), grow)
    d = m("ADD", m("MULTIPLY", m("SUBTRACT", 1.0, m("MULTIPLY", m("POWER", m("MINIMUM", tb, 1.0), 2.2), 0.65)), D), grow)
    inside = m("LESS_THAN", m("ABSOLUTE", x), L / 2 + grow)
    inside = m("MULTIPLY", inside, m("LESS_THAN", m("ABSOLUTE", y), w))
    inside = m("MULTIPLY", inside, m("GREATER_THAN", z, m("MULTIPLY", d, -1.0)))
    inside = m("MULTIPLY", inside, m("LESS_THAN", z, HF + top))
    return inside


def masked_water(mat, ref):
    """Cut the hull's volume out of a water volume material (density -> 0 inside the boat)."""
    nt = mat.node_tree
    absorb = next(n for n in nt.nodes if n.type == "VOLUME_ABSORPTION")
    scat = next(n for n in nt.nodes if n.type == "VOLUME_SCATTER")
    keep = nt.nodes.new("ShaderNodeMath")
    keep.operation = "SUBTRACT"
    keep.inputs[0].default_value = 1.0
    nt.links.new(hull_mask(nt, ref), keep.inputs[1])
    for node, dens in ((absorb, absorb.inputs["Density"].default_value), (scat, scat.inputs["Density"].default_value)):
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = dens
        nt.links.new(keep.outputs[0], mul.inputs[0])
        nt.links.new(mul.outputs[0], node.inputs["Density"])


def _carve(obj, cutter):
    """Subtract the hull's shape from a water mesh (live boolean, follows the boat)."""
    mod = obj.modifiers.new("hull_hole", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.object = cutter
    for solver in ("EXACT", "FLOAT", "FAST"):          # EXACT: no triangles popping frame to frame
        try:
            mod.solver = solver
            break
        except TypeError:
            continue
    return mod


def _prism(name, outline, z0, z1, mat=None, keep_back_half=False, open_top=False):
    """Extrude a plan outline [(x, y)...] from z0 to z1. keep_back_half: cut at y=0 (keep y >= 0)."""
    bm = bmesh.new()
    bot = [bm.verts.new((x, y, z0)) for x, y in outline]
    top = [bm.verts.new((x, y, z1)) for x, y in outline]
    n = len(outline)
    bm.faces.new(bot[::-1])
    if not open_top:
        bm.faces.new(top)
    for k in range(n):
        bm.faces.new((bot[k], bot[(k + 1) % n], top[(k + 1) % n], top[k]))
    if keep_back_half:
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, 0),
                               plane_no=(0, 1, 0), clear_inner=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    if mat is not None:
        obj.data.materials.append(mat)
    return obj


SECTION = [(0.0, -1.0), (0.42, -0.86), (0.72, -0.6), (0.9, -0.3), (0.98, 0.0), (1.0, 1.0)]   # (y/w, z: -d..s)
STATIONS = 26


def station(t):
    """Hull at station t in [-1 stern .. 1 bow]: half-width, keel depth below the waterline, sheer
    height above it. A pointed, rising bow, a flat transom, a little rocker."""
    if t >= 0:
        w = W / 2 * max(0.03, 1 - t ** 1.7)
        d = D * (1 - 0.65 * t ** 2.2)
        sh = HF + 0.28 * t ** 2
    else:
        a = -t
        w = W / 2 * (1 - 0.12 * a ** 3)
        d = D * (1 - 0.35 * a ** 3)
        sh = HF + 0.05 * a ** 2
    return w, d, sh


def section_pts(t, inset=0.0):
    w, d, sh = station(t)
    w = max(0.01, w - inset)
    return [(u * w, (v * (d - inset) if v < 0 else v * sh)) for u, v in SECTION]


def _mesh(name, verts, faces, mat=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    if mat is not None:
        obj.data.materials.append(mat)
    return obj


def hull_shell(name, mats):
    """The WHOLE hull (both sides, open on top): a lofted plate through the stations + a transom.
    Outer face = paint, inner face + plate edges = grey primer (seen only in cutaway)."""
    ts = [-1 + 2 * k / (STATIONS - 1) for k in range(STATIONS)]
    verts, faces = [], []
    ring_n = None
    for t in ts:
        x = t * L / 2
        right = section_pts(t)                                         # keel (y=0) → right sheer
        prof = [(-y, z) for y, z in reversed(right[1:])] + right       # left sheer → keel → right sheer
        ring_n = len(prof)
        verts += [(x, y, z) for y, z in prof]
    for i in range(STATIONS - 1):
        for j in range(ring_n - 1):
            a, b = i * ring_n + j, (i + 1) * ring_n + j
            faces.append((a, b, b + 1, a + 1))
    faces.append(tuple(range(ring_n - 1, -1, -1)))                      # transom plate
    obj = _mesh(name, verts, faces)
    for m in mats:
        obj.data.materials.append(m)
    obj.data.shade_smooth()
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(obj.data)
    bm.free()
    sol = obj.modifiers.new("plate", "SOLIDIFY")
    sol.thickness, sol.offset, sol.use_rim = 0.04, -1.0, True
    sol.material_offset, sol.material_offset_rim = 1, 1                  # inside + edges: primer
    return obj


def extrude_y(name, profile_xz, y0, y1, mat=None):
    """A closed solid from a side-view profile [(x, z)...] extruded across y0..y1."""
    bm = bmesh.new()
    a = [bm.verts.new((x, y0, z)) for x, z in profile_xz]
    b = [bm.verts.new((x, y1, z)) for x, z in profile_xz]
    n = len(profile_xz)
    bm.faces.new(a[::-1])
    bm.faces.new(b)
    for k in range(n):
        bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    if mat is not None:
        obj.data.materials.append(mat)
    return obj


def _apply_cut(obj, cutter):
    """Subtract `cutter` once, permanently (window holes, a hatch): no live boolean, no flicker."""
    mod = obj.modifiers.new("cut", "BOOLEAN")
    mod.operation, mod.object = "DIFFERENCE", cutter
    with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj]):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def section_clip(obj, section):
    """Give `obj` its own copies of its materials, cut away where the section plane passes:
    everything with local y < 0 (in `section` space) disappears. Moving `section` far forward
    shows the whole boat; at the centreline it is a cutaway. Alpha is 0 or 1: crisp, no noise."""
    for k, mat in enumerate(obj.data.materials):
        if mat is None:
            continue
        m = mat.copy()
        m.name = f"{mat.name}~clip"
        obj.data.materials[k] = m
        nt = m.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            continue
        tc = nt.nodes.new("ShaderNodeTexCoord")
        tc.object = section
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(tc.outputs["Object"], sep.inputs[0])
        keep = nt.nodes.new("ShaderNodeMath")
        keep.operation = "GREATER_THAN"
        keep.inputs[1].default_value = 0.0
        nt.links.new(sep.outputs["Y"], keep.inputs[0])
        alpha_in = bsdf.inputs["Alpha"]
        if alpha_in.is_linked:
            src = alpha_in.links[0].from_socket
            mul = nt.nodes.new("ShaderNodeMath")
            mul.operation = "MULTIPLY"
            nt.links.new(src, mul.inputs[0])
            nt.links.new(keep.outputs[0], mul.inputs[1])
            nt.links.new(mul.outputs[0], alpha_in)
        else:
            mul = nt.nodes.new("ShaderNodeMath")
            mul.operation = "MULTIPLY"
            mul.inputs[0].default_value = alpha_in.default_value
            nt.links.new(keep.outputs[0], mul.inputs[1])
            nt.links.new(mul.outputs[0], alpha_in)
        if hasattr(m, "surface_render_method") and m.surface_render_method != "BLENDED":
            m.surface_render_method = "DITHERED"
        if hasattr(m, "use_backface_culling"):
            m.use_backface_culling = False


def hull_solid(name, scale=1.0, top=0.6, inset=0.0):
    """A closed, full-width hull volume (both halves), `top` m above the sheer: the water carver."""
    ts = [-1 + 2 * k / (STATIONS - 1) for k in range(STATIONS)]
    verts, faces, rings = [], [], []
    for t in ts:
        x = t * L / 2 * scale
        right = [(y * scale, z * scale) for y, z in section_pts(t, inset)]
        sh = station(t)[2]
        ring = right + [(right[-1][0], sh + top), (-right[-1][0], sh + top)] + [(-y, z) for y, z in reversed(right[1:])]
        rings.append(len(verts))
        verts += [(x, y, z) for y, z in ring]
    m = len(verts) // STATIONS
    for i in range(STATIONS - 1):
        for j in range(m):
            a, b = rings[i] + j, rings[i + 1] + j
            faces.append((a, b, rings[i + 1] + (j + 1) % m, rings[i] + (j + 1) % m))
    faces.append(tuple(range(rings[0] + m - 1, rings[0] - 1, -1)))
    faces.append(tuple(range(rings[-1], rings[-1] + m)))
    obj = _mesh(name, verts, faces)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(obj.data)
    bm.free()
    obj.hide_render = True
    obj.display_type = "WIRE"
    return obj


def _curve(name, pts, radius, mat):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions, cu.bevel_depth, cu.bevel_resolution = "3D", radius, 2
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for pt, c in zip(sp.points, pts):
        pt.co = (*c, 1)
    ob = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return ob


def _keep_back(obj, plane_y=0.001):
    """Bake an object's transform into its mesh and keep only its back half (y >= 0), capped."""
    obj.data.transform(obj.matrix_basis)
    obj.matrix_basis.identity()
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, plane_y, 0),
                           plane_no=(0, 1, 0), clear_inner=True)
    bmesh.ops.holes_fill(bm, edges=bm.edges[:], sides=0)
    bm.to_mesh(obj.data)
    bm.free()
    for mod in list(obj.modifiers):
        obj.modifiers.remove(mod)
    return obj


def hull_paint():
    """Navy topsides, a white sheer stripe, red antifouling below the waterline, plate seams."""
    from engine.textures import _Tree, _vary
    t = _Tree("bk_hull_paint")
    z = t.xyz["z"]
    f = t.math("DIVIDE", t.math("ADD", z, 1.5), 3.0)
    col = t.ramp(f, [(0.0, "#B8332B"), ((1.5 - 0.03) / 3, "#23476E"), ((1.5 + 0.33) / 3, "#F2EEE6"),
                     ((1.5 + 0.41) / 3, "#23476E")])
    col.node.color_ramp.interpolation = "CONSTANT"
    value, r = _vary(t, 0.38, amount=0.1)
    seam, _ = t.line(t.xyz["x"], 0.6, width=0.03)
    value = t.math("SUBTRACT", value, t.math("MULTIPLY", seam, 0.3))
    return t.finish(t.shade(col, value), r, t.math("MULTIPLY", seam, -1.0), strength=0.3, metallic=0.15, coat=0.4)


# ------------------- the set -------------------

class BoatStorySet:
    ACTIONS = ACTIONS
    QA_ALLOW = (r"lake_water|water_surface|sand|bank|ramp|dock|post|seaweed|reed|fish|hull|deck|keel|bulb|bulkhead"
                r"|flood|prop|rudder|shaft|engine|cabin|mast|nest|pump|slab|carver|_elbow|tuft|cg_|duck|ship|container"
                r"|displaced|hat_fish|helm|rib|rail|inner|bucket|weld|stanchion|porthole|boat_name|hatch|nav_|antenna"
                r"|lifering|door|console|glass")

    def __init__(self, scene, sun, fill, bg, total):
        self.scene, self.sun, self.fill, self.bg, self.total = scene, sun, fill, bg, total
        self.rig = CameraRig(blend=16)
        self.rnd = random.Random(4)
        self._world()
        self._boat()
        self._no_ground_shadows()
        self.max = Character("Max", {"hat": "#FF7A00", "iris": "#7A4A1C"})
        self.mb = Character("MaxBoat", {"hat": "#FF7A00", "iris": "#7A4A1C"})        # Max riding the boat
        self.mb.root.parent = self.body
        self.mb.place(1, V((-1.95, 0.42, HF)), 90)
        toy.hide_tree(self.mb.root, 1, True)
        self.kids = []
        for k, look in enumerate(({"hat": None, "mustache": False, "shirt": "#FF5D8F", "overalls": "#3A7BD5",
                                   "hair": "#5B3A1E", "scale": 0.6, "ponytail": True},
                                  {"hat": None, "mustache": False, "shirt": "#3DBE6E", "overalls": "#F2A93B",
                                   "hair": "#2B1A10", "scale": 0.56})):
            kid = Character(f"Kid{k + 1}", look)
            kid.root.parent = self.body
            kid.place(1, V((-0.05 + 0.72 * k, 0.32, HF)), 0)
            toy.hide_tree(kid.root, 1, True)
            self.kids.append(kid)
        self.max.place(1, DOCK_SPOT, 0)
        for c in (self.max, self.mb):
            c.auto_blink(1, total + 400, seed=len(c.name))
        events.add(1, "lake", duration=total + 400, gain=0.5)

    # ------------------- world -------------------

    def _world(self):
        soil = toy.noise_material("bk_soil", toy.srgb("#6B4A30"), toy.srgb("#86603F"), scale=8, roughness=0.9, bump=0.4)
        sand = toy.noise_material("bk_sand", toy.srgb("#C9B07A"), toy.srgb("#DCC690"), scale=18, roughness=0.9, bump=0.3)
        grass = toy.noise_material("bk_grass", toy.srgb("#4C8A33"), toy.srgb("#6AA543"), scale=30, bump=0.3)
        toy.box("bank_soil", (12, LAKE_Y1 + 6, 12.3), (-15.03, (LAKE_Y1 + 6) / 2, -6.0 + 0.15 - 0.012), mat=soil, bevel=0)      # left bank, cut open
        toy.box("bank_top", (12, LAKE_Y1 + 6, 0.1), (-15.0, (LAKE_Y1 + 6) / 2 + 0.008, 0.25 + 0.003), mat=grass, bevel=0)
        toy.box("sand_bed", (LAKE_X1 - LAKE_X0, LAKE_Y1 + 6, 0.5), ((LAKE_X0 + LAKE_X1) / 2, (LAKE_Y1 + 6) / 2,
                                                                    BED - 0.25 - 0.004),
                mat=sand, bevel=0)
        toy.box("bed_soil", (LAKE_X1 - LAKE_X0 + 30, LAKE_Y1 + 6, 9.0), ((LAKE_X0 + 0.02 + LAKE_X1 + 30) / 2,
                                                                         (LAKE_Y1 + 6) / 2 + 0.006,
                                                                         BED - 0.5 - 4.5 - 0.008),
                mat=soil, bevel=0)
        ramp = _prism("sand_ramp", [(LAKE_X0, BED), (LAKE_X0 + 2.6, BED), (LAKE_X0, 0.0)], 0.0, 30.0, mat=sand)
        ramp.rotation_euler = (R(90), 0, 0)            # the bank slopes down into the lake (prism along y)
        ramp.location = (0, 30.0, 0)
        # far shore: a sand beach rising out of the water, then the grass field set back and higher.
        # No two faces share a plane (they flickered as one horizontal line behind Max).
        toy.box("far_shore", (90, 50, 0.6), (8, LAKE_Y1 + 0.45 + 25.0, 0.0), mat=grass, bevel=0)      # top z 0.30
        toy.box("far_bank", (LAKE_X1 - LAKE_X0 + 0.4, 0.8, abs(BED) + 0.2),
                ((LAKE_X0 + LAKE_X1) / 2, LAKE_Y1 + 0.4, (BED + 0.2) / 2 - 0.01), mat=sand, bevel=0)  # top z 0.19
        # the lake itself: a section volume + a rippling surface sheet (both carved by the hull later)
        self.water_mat = water_volume_material()
        self.surface_mat = water_surface_material()
        self.drop_mat = splash_material()
        top = -0.07                                    # below the ripples: the surface sheet is the only top
        self.water = toy.box("lake_water", (LAKE_X1 - LAKE_X0 - 0.06, LAKE_Y1 + 0.15, top - BED - 0.01),
                             ((LAKE_X0 + LAKE_X1) / 2, (LAKE_Y1 + 0.15) / 2 + 0.004, (top + BED + 0.01) / 2),
                             mat=self.water_mat, bevel=0)
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=180, y_subdivisions=70, size=1,
                                        location=((LAKE_X0 + LAKE_X1) / 2, (LAKE_Y1 + 0.15) / 2 + 0.004, 0.0))
        surf = bpy.context.active_object
        surf.name = "water_surface"
        surf.scale = (LAKE_X1 - LAKE_X0 - 0.06, LAKE_Y1 + 0.15, 1)          # its far edge hides inside the bank
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        surf.data.materials.append(self.surface_mat)
        tex = bpy.data.textures.new("lake_ripples", "CLOUDS")
        tex.noise_scale = 0.35
        drift = toy.empty("lake_drift", (0, 0, 0))
        drift.keyframe_insert("location", frame=1)
        drift.location = (14, 6, 4)
        drift.keyframe_insert("location", frame=6000)
        toy.set_interpolation(drift, "location", (1,), "LINEAR")
        disp = surf.modifiers.new("ripples", "DISPLACE")
        disp.texture, disp.texture_coords, disp.texture_coords_object, disp.strength = tex, "OBJECT", drift, 0.03
        disp.mid_level = 0.5
        self.surface = surf
        # dock + posts
        wood = tx.planks("bk_dock", "#8A6440", "#9C7450", width=0.18, across="x", along="y", seam_dark=0.4)
        post = tx.wood("bk_post", "#5E4630", "#7A5A3C", along="z")
        toy.box("dock", (2.9, 1.4, 0.1), (LAKE_X0 + 1.45 - 0.2, 0.85, DOCK_TOP - 0.05), mat=wood, bevel=0.01)
        for k, x in enumerate((LAKE_X0 + 0.4, LAKE_X0 + 1.5, LAKE_X0 + 2.5)):
            for j, y in enumerate((0.3, 1.4)):
                toy.cylinder(f"dock_post{k}{j}", 0.07, 3.2, (x, y, DOCK_TOP - 1.6), mat=post, vertices=12)
        # workshop on the bank: a shed and an anvil-ish welding bench
        shed = tx.planks("bk_shed", "#5C7C99", "#527090", width=0.22)
        toy.box("shed", (3.2, 2.6, 2.6), (-14.5, 2.6, 1.6), mat=shed, bevel=0.03)
        toy.box("shed_roof", (3.6, 3.0, 0.15), (-14.5, 2.6, 3.0), mat=tx.corrugated("bk_roof", "#7C838C"), bevel=0.02)
        toy.box("bench", (1.4, 0.7, 0.8), (-10.9, 1.2, 0.7), mat=tx.metal("bk_bench", "#5F6368", 0.4), bevel=0.02)
        # grass on the bank, near and far
        tuft = _grass_tuft()
        toy.scatter("g_bank", -20, LAKE_X0 - 0.05, 0.05, 14, tuft, 160, size=1.5, z=0.302, seed=2)
        tuft.hide_render = True
        # reeds at the far end, seaweed and rocks on the bed, fish, hills, trees, clouds
        reed = _mat("bk_reed", "#5E8C38", 0.7)
        rnd = random.Random(7)
        for k in range(26):
            x, y = rnd.uniform(13.0, 17.5), rnd.uniform(0.3, 3.5)
            h = rnd.uniform(1.4, 2.4)
            rd = toy.cylinder(f"reed{k}", 0.03, h + 2.6, (x, y, BED + (h + 2.6) / 2), mat=reed, vertices=8)
            head = toy.cylinder(f"reed_head{k}", 0.06, 0.32, (0, 0, (h + 2.6) / 2 - 0.15),
                                mat=_mat("bk_cattail", "#6B4226", 0.8), vertices=10)
            head.parent = rd
            head.location = (0, 0, (h + 2.6) / 2 - 0.15)
            toy.add_noise(rd, "rotation_euler", 1, strength=0.05, scale=30, phase=k)
        weed = _mat("bk_weed", "#3E8A3A", 0.7)
        rock = toy.noise_material("bk_rock", toy.srgb("#6E6A63"), toy.srgb("#8A857C"), scale=6, bump=0.6)
        for k in range(18):
            x, y = rnd.uniform(-6, 16), rnd.uniform(0.6, 6)
            bpy.ops.mesh.primitive_cone_add(vertices=6, radius1=0.08, depth=rnd.uniform(0.6, 1.3),
                                            location=(x, y, BED + 0.4))
            wd = bpy.context.active_object
            wd.name = f"seaweed{k}"
            toy._finish(wd, weed, subdiv=0)
            toy.add_noise(wd, "rotation_euler", 1, strength=0.12, scale=25, phase=k * 3)
        for k in range(10):
            toy.sphere(f"rock{k}", rnd.uniform(0.15, 0.35), (rnd.uniform(-6, 16), rnd.uniform(0.5, 6), BED + 0.05),
                       scale=(1.4, 1.0, 0.6), mat=rock, subdiv=1)
        self.fish = []
        for k in range(5):
            f = self._fish(f"fish{k}", ("#FF8C1A", "#F2C230", "#E8572A", "#FFB347", "#F2C230")[k])
            base = V((rnd.uniform(-2, 12), rnd.uniform(1.2, 4.5), rnd.uniform(-2.0, -0.9)))
            f.location = base
            f.keyframe_insert("location", frame=1)
            f.location = base + V((rnd.choice((-1, 1)) * 6, 0, 0))
            f.keyframe_insert("location", frame=900)
            f.location = base
            f.keyframe_insert("location", frame=1800)
            f.location = base + V((rnd.choice((-1, 1)) * 6, 0, 0))
            f.keyframe_insert("location", frame=2700)
            toy.add_noise(f, "location", 2, strength=0.2, scale=40, phase=k)
            self.fish.append(f)
        hill = _mat("bk_hill", "#5F9B45", 0.9)
        for k, (x, r) in enumerate(((-25, 16), (10, 20), (42, 18))):
            toy.sphere(f"hill{k}", r, (x, 70, -r * 0.6), scale=(1.6, 1.0, 0.7), mat=hill, subdiv=1)
        bark = toy.noise_material("bk_bark", toy.srgb("#5A4632"), toy.srgb("#74604A"), scale=12, bump=0.6)
        leaf = toy.noise_material("bk_leaf", toy.srgb("#3D6B2A"), toy.srgb("#5E8C38"), scale=6, bump=0.6)
        for k, (x, y, s) in enumerate(((-17, 7, 1.1), (-12, 12, 0.9), (2, LAKE_Y1 + 4, 1.4), (14, LAKE_Y1 + 5, 1.5),
                                      (28, LAKE_Y1 + 4, 1.4))):
            h = 2.8 * s
            toy.cylinder(f"trunk{k}", 0.22 * s, h, (x, y, h / 2), mat=bark, vertices=10)
            r2 = random.Random(k)
            for j in range(6):
                toy.sphere(f"leaf{k}_{j}", r2.uniform(0.7, 1.0) * s,
                           (x + r2.uniform(-1, 1) * s, y + r2.uniform(-0.7, 0.7) * s, h + r2.uniform(0, 1.2) * s),
                           mat=leaf, subdiv=1)
        cloud = toy.material("bk_cloud", (1, 1, 1), roughness=0.95)
        r3 = random.Random(3)
        for i in range(7):
            root = toy.empty(f"cloud_{i}", (r3.uniform(-40, 50), r3.uniform(55, 80), r3.uniform(15, 26)))
            for k in range(5):
                pc = toy.sphere(f"cloud_{i}_{k}", r3.uniform(2.4, 3.6), (0, 0, 0), scale=(1.4, 1.0, 0.65), mat=cloud,
                                subdiv=1)
                pc.parent = root
                pc.location = (r3.uniform(-4, 4), r3.uniform(-1, 1), r3.uniform(-0.6, 0.8))
                pc.visible_shadow = False
            root.keyframe_insert("location", frame=1)
            root.location.x += 25
            root.keyframe_insert("location", frame=6000)
            toy.set_interpolation(root, "location", (1,), "LINEAR")

    def _no_ground_shadows(self):
        """Big flat ground/water/background pieces never need to CAST shadows (they only receive):
        drawing them into every shadow map was half the render time."""
        import re as _re
        for o in bpy.data.objects:
            if _re.match(r"^(field|bank_|sand_|bed_|far_|g_|hill|lake_water|water_surface|cloud|rock|seaweed)", o.name):
                o.visible_shadow = False

    def _fish(self, name, hexc):
        m = _mat(f"{name}_m", hexc, 0.35, coat=0.4)
        root = toy.empty(name)
        body = toy.sphere(f"{name}_body", 0.16, (0, 0, 0), scale=(1.6, 0.55, 0.9), mat=m, subdiv=1)
        body.parent = root
        bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=0.12, depth=0.18, location=(0, 0, 0))
        tail = bpy.context.active_object
        tail.name = f"{name}_tail"
        toy._finish(tail, m, subdiv=0, parent=root)
        tail.location, tail.rotation_euler = (-0.3, 0, 0), (0, R(90), 0)
        toy.add_noise(tail, "rotation_euler", 2, strength=0.4, scale=4, phase=len(name))
        eye = toy.sphere(f"{name}_eye", 0.025, (0.17, -0.06, 0.04), mat=_mat("bk_eye", "#111111", 0.2), subdiv=0)
        eye.parent = root
        return root

    # ------------------- boat -------------------

    def _boat(self):
        primer = tx.paint("bk_primer", "#8C9399", 0.6, coat=0.0)
        deck_m = tx.planks("bk_deck", "#B88A5A", "#A57A4C", width=0.12, across="y", along="x", seam_dark=0.35)
        steel = tx.metal("bk_steel", "#9AA0A6", 0.28)
        teak = tx.wood("bk_rail", "#8A5A32", "#A9733F", along="x")
        white = tx.paint("bk_cabin", "#F4F1EA", 0.45, coat=0.3)
        navy = tx.paint("bk_trim", "#23476E", 0.4, coat=0.4)
        red = tx.paint("bk_cabroof", "#B8332B", 0.45, coat=0.3)
        glass = bpy.data.materials.new("bk_glass")
        gb = toy._principled(glass)
        toy._set(gb, "Base Color", (*toy.srgb("#9FC9E0"), 1))
        toy._set(gb, "Roughness", 0.05)
        toy._set(gb, "Coat Weight", 1.0)
        toy._set(gb, "Alpha", 0.3)
        if hasattr(glass, "surface_render_method"):
            glass.surface_render_method = "BLENDED"
        self.root = toy.empty("boat_root", AWAY)
        self.body = toy.empty("boat_body", (0, 0, 0), self.root)
        self.section = toy.empty("boat_section", (0, -6.0, 0), self.body)       # closed: far in front
        ext = []                                                                 # exterior: clipped in cutaway
        hull = hull_shell("hull", [hull_paint(), primer])
        hull.parent = self.body
        ext.append(hull)
        parts = [hull]
        for k in range(1, 9):                                                    # frames inside (cutaway only)
            t = -0.86 + 1.55 * k / 9
            x = t * L / 2
            rib = _curve(f"hull_rib{k}", [(x, y, z) for y, z in section_pts(t, inset=0.045)], 0.022, steel)
            rib.parent = self.body
            parts.append(rib)
        # rub rail (a fender strip) all round the sheer, both sides
        for side in (1, -1):
            rr = _curve(f"hull_rubrail{side}", [(t * L / 2, side * (station(t)[0] + 0.012), station(t)[2] - 0.03)
                                                for t in [-1 + k / 14 for k in range(29)]], 0.035, navy)
            rr.parent = self.body
            ext.append(rr)
            parts.append(rr)
        # deck: full width, with a hatch opening (cut once) at the bailing spot
        outline = [(t * L / 2, station(t)[0] - 0.05) for t in [-0.985 + k * 1.95 / 24 for k in range(25)]]
        outline += [(x, -y) for x, y in reversed(outline)]
        deck = _prism("deck", outline, HF - 0.06, HF - 0.01, mat=deck_m)
        hx, hy, hw, hd = 0.12, 0.0, 0.56, 0.5
        _apply_cut(deck, toy.box("hatch_hole", (hw, hd, 0.3), (hx, hy, HF - 0.03), bevel=0))
        coaming = toy.box("hatch_coaming", (hw + 0.08, hd + 0.08, 0.06), (hx, hy, HF + 0.01), mat=navy, bevel=0.01)
        _apply_cut(coaming, toy.box("hatch_hole2", (hw, hd, 0.3), (hx, hy, HF), bevel=0))
        self.hatch = toy.empty("hatch_hinge", (hx, hy - hd / 2 - 0.04, HF + 0.04), self.body)   # hinged at the FRONT
        lid = toy.box("hatch_lid", (hw + 0.06, hd + 0.06, 0.04), (0, (hd + 0.06) / 2, 0), mat=deck_m, bevel=0.01)
        lid.parent = self.hatch
        for o in (deck, coaming, lid):
            if o.parent is None:
                o.parent = self.body
            ext.append(o)
            parts.append(o)
        # stanchions + a guard rail along both sides
        for side in (1, -1):
            tops = []
            for t in [-0.9 + k * 0.17 for k in range(11)]:
                y = side * (station(t)[0] - 0.08)
                z0 = station(t)[2] - 0.01
                st = toy.cylinder(f"stanchion{side}_{t:.2f}", 0.014, 0.42, (t * L / 2, y, z0 + 0.21), mat=steel, vertices=8)
                st.parent = self.body
                ext.append(st)
                parts.append(st)
                tops.append((t * L / 2, y, z0 + 0.42))
            gr = _curve(f"guardrail{side}", tops, 0.016, steel)
            gr.parent = self.body
            ext.append(gr)
            parts.append(gr)
        # name on the bow, both sides: the running gag
        from engine.cutaway import _bold_font
        for side in (-1, 1):
            t = 0.42
            w = station(t)[0]
            dw = (station(t + 0.01)[0] - station(t - 0.01)[0]) / (0.02 * L / 2)
            txt = bpy.data.curves.new(f"boat_name{side}", "FONT")
            txt.body, txt.size, txt.extrude, txt.align_x, txt.align_y = "UNSINKABLE", 0.13, 0.004, "CENTER", "CENTER"
            if _bold_font():
                txt.font = _bold_font()
            no = bpy.data.objects.new(f"boat_name{side}", txt)
            bpy.context.scene.collection.objects.link(no)
            no.data.materials.append(tx.paint("bk_name", "#F4F1EA", 0.4))
            no.parent = self.body
            no.location = (t * L / 2, side * (w + 0.012), 0.16)
            no.rotation_euler = (R(90), 0, math.atan(dw) * side + (0 if side < 0 else math.pi))
            parts.append(no)
        # portholes on the topsides
        brass = tx.metal("bk_brass", "#D4A940", 0.28)
        dark = _mat("bk_port_glass", "#1C3346", 0.08, coat=1.0)
        for side in (-1, 1):
            for x in (-1.75, -1.35, 0.15):
                t = x / (L / 2)
                w = station(t)[0]
                bpy.ops.mesh.primitive_torus_add(major_radius=0.07, minor_radius=0.014,
                                                 location=(x, side * (w + 0.006), 0.18), rotation=(R(90), 0, 0))
                ring = bpy.context.active_object
                ring.name = f"porthole{side}_{x}"
                toy._finish(ring, brass, subdiv=0, parent=self.body)
                gl = toy.cylinder(f"porthole_glass{side}_{x}", 0.062, 0.012, (x, side * (w + 0.004), 0.18),
                                  rotation=(R(90), 0, 0), mat=dark)
                gl.parent = self.body
                ext += [ring, gl]
                parts += [ring, gl]
        self.hull_parts = parts
        # the invisible carver (a coordinate frame for the water masks)
        self.carver = hull_solid("hull_carver", scale=1.02, top=0.8)
        self.carver.parent = self.body
        self.carver.hide_viewport = True
        masked_water(self.water_mat, self.carver)
        snt = self.surface_mat.node_tree
        sb = toy._principled(self.surface_mat)
        keep = snt.nodes.new("ShaderNodeMath")
        keep.operation = "SUBTRACT"
        keep.inputs[0].default_value = 0.55
        mul = snt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = 0.55
        snt.links.new(hull_mask(snt, self.carver, grow=0.05, top=3.0), mul.inputs[0])
        snt.links.new(mul.outputs[0], keep.inputs[1])
        snt.links.new(keep.outputs[0], sb.inputs["Alpha"])
        self.inner = hull_solid("hull_inner", scale=1.0, top=0.0, inset=0.05)
        self.inner.parent = self.body
        # ---- keel: a swept fin (an airfoil in section) and a torpedo lead bulb
        fin_paint = tx.paint("bk_keelpaint", "#B8332B", 0.6, coat=0.0)
        fin = extrude_y("keel_fin", [(-0.25, -D + 0.12), (0.55, -D + 0.12), (0.38, -D - 0.85), (-0.12, -D - 0.85)],
                        -0.045, 0.045, fin_paint)
        bev = fin.modifiers.new("round", "BEVEL")
        bev.width, bev.segments = 0.03, 3
        lead = tx.paint("bk_lead", "#3A3D42", 0.75, coat=0.0)
        bulb = toy.sphere("keel_bulb", 0.2, (0.12, 0.0, -D - 0.95), scale=(3.6, 1.0, 0.95), mat=lead, subdiv=2)
        self.keel = [fin, bulb]
        ext += [fin, bulb]
        # ---- wheelhouse: hollow, with window openings, a raked windscreen, roof, door, lights
        cx0, cx1 = -1.3, -0.45
        cw = 0.62
        house = extrude_y("cabin", [(cx0, HF - 0.01), (cx1, HF - 0.01), (cx1, HF + 0.55), (cx1 - 0.16, HF + 1.0),
                                    (cx0, HF + 1.0)], -cw, cw, white)
        sol = house.modifiers.new("walls", "SOLIDIFY")
        sol.thickness, sol.offset = 0.04, -1.0
        with bpy.context.temp_override(object=house, active_object=house, selected_objects=[house]):
            bpy.ops.object.modifier_apply(modifier=sol.name)
        for k, (wx0, wx1) in enumerate(((cx0 + 0.12, cx0 + 0.42), (cx0 + 0.5, cx1 - 0.08))):   # side windows
            _apply_cut(house, toy.box(f"win_cut{k}", (wx1 - wx0, 2 * cw + 0.2, 0.36), ((wx0 + wx1) / 2, 0, HF + 0.68), bevel=0))
        _apply_cut(house, toy.box("wscreen_cut", (0.3, 2 * cw - 0.2, 0.32), (cx1 - 0.06, 0, HF + 0.75),
                                  rotation=(0, R(-20), 0), bevel=0))
        _apply_cut(house, toy.box("door_cut", (0.2, 0.5, 0.78), (cx0, -0.05, HF + 0.39), bevel=0))
        house.parent = self.body
        roof = toy.box("cabin_roof", (0.98, 2 * cw + 0.16, 0.06), ((cx0 + cx1) / 2 - 0.02, 0, HF + 1.03), mat=red, bevel=0.02)
        panes = [toy.box("cabin_glass_side", (cx1 - cx0 - 0.1, 2 * cw - 0.02, 0.38), ((cx0 + cx1) / 2, 0, HF + 0.68),
                         mat=glass, bevel=0),
                 toy.box("cabin_glass_front", (0.02, 2 * cw - 0.16, 0.36), (cx1 - 0.07, 0, HF + 0.76),
                         rotation=(0, R(-20), 0), mat=glass, bevel=0)]
        for pn in panes:
            pn.visible_shadow = False
        door = toy.box("cabin_door", (0.03, 0.5, 0.78), (cx0 - 0.03, -0.05, HF + 0.39),
                       mat=tx.planks("bk_door", "#7A4E2C", "#6B4426", width=0.12, across="y", along="z"), bevel=0.01)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.15, minor_radius=0.04, location=(cx0 - 0.06, 0.35, HF + 0.55),
                                         rotation=(0, R(90), 0))
        lifering = bpy.context.active_object
        lifering.name = "cabin_lifering"
        toy._finish(lifering, tx.paint("bk_lifering", "#FF6A13", 0.4), subdiv=0)
        mast_s = toy.cylinder("cabin_antenna", 0.012, 0.5, (cx0 + 0.2, 0, HF + 1.31), mat=steel)
        port = toy.sphere("nav_red", 0.035, ((cx0 + cx1) / 2, cw + 0.05, HF + 1.0), mat=_mat("bk_navred", "#FF2A1A", 0.2))
        stbd = toy.sphere("nav_green", 0.035, ((cx0 + cx1) / 2, -cw - 0.05, HF + 1.0), mat=_mat("bk_navgreen", "#2AE05A", 0.2))
        for lt, col in ((port, "#FF2A1A"), (stbd, "#2AE05A")):
            toy._set(toy._principled(lt.data.materials[0]), "Emission Color", (*toy.srgb(col), 1))
            toy._set(toy._principled(lt.data.materials[0]), "Emission Strength", 4.0)
        # the helm: a console and a spoked wheel facing aft (seen through the windows and in cutaway)
        console = toy.box("helm_console", (0.18, 0.5, 0.55), (cx1 - 0.16, 0.1, HF + 0.27), mat=navy, bevel=0.02)
        wheel_root = toy.empty("helm", (cx1 - 0.3, 0.1, HF + 0.68))
        bpy.ops.mesh.primitive_torus_add(major_radius=0.16, minor_radius=0.02, location=(0, 0, 0), rotation=(0, R(90), 0))
        wheel = bpy.context.active_object
        wheel.name = "helm_wheel"
        toy._finish(wheel, teak, subdiv=0, parent=wheel_root)
        for k in range(6):
            sp = toy.box(f"helm_spoke{k}", (0.02, 0.02, 0.42), (0, 0, 0), mat=teak, bevel=0.004)
            sp.parent = wheel_root
            sp.rotation_euler = (R(30 * k), 0, 0)
        hub = toy.sphere("helm_hub", 0.04, (0, 0, 0), mat=brass, subdiv=1)
        hub.parent = wheel_root
        self.cabin = [house, roof, door, lifering, mast_s, port, stbd, console, wheel_root] + panes
        ext += [house, roof, door, lifering, console]
        # ---- tall mast + crow's nest (the capsize gag), on the centreline
        self.mast = [toy.cylinder("mast", 0.05, 2.6, (0.55, 0.0, HF + 1.3), mat=tx.wood("bk_mast", "#8A6440", "#A07A50")),
                     toy.box("mast_nest", (0.6, 0.6, 0.3), (0.55, 0.0, HF + 2.5),
                             mat=tx.planks("bk_nest", "#8A6440", "#9C7450", width=0.12), bevel=0.02),
                     _prism("mast_flag", [(0.0, 0.0), (0.55, 0.0), (0.0, 0.36)], 0.0, 0.02, mat=_mat("bk_flag", "#E8322A", 0.6))]
        self.mast[2].rotation_euler = (R(90), 0, 0)
        self.mast[2].location = (0.6, 0.01, HF + 2.6)
        # ---- watertight bulkheads (inside: cutaway only)
        bulk_m = tx.metal("bk_bulk", "#7A828A", 0.35)
        self.bulkheads = []
        for k, x in enumerate(BULK_X):
            t = x / (L / 2)
            pts = section_pts(t, inset=0.045) + [(0.0, station(t)[2] - 0.07)]
            wall = _prism(f"bulkhead{k}", [(y, z) for y, z in pts], -0.025, 0.025, mat=bulk_m)
            wall.rotation_euler = (R(90), 0, R(90))
            wall.location = (x, 0.0, 0.0)
            self.bulkheads.append(wall)
        # ---- flood water (inside), trimmed by the hull mask
        self.flood_mat = bpy.data.materials.new("bk_flood")
        fb = toy._principled(self.flood_mat)
        toy._set(fb, "Base Color", (*toy.srgb("#2F8FD8"), 1))
        toy._set(fb, "Emission Color", (*toy.srgb("#2F8FD8"), 1))
        toy._set(fb, "Emission Strength", 0.25)
        toy._set(fb, "Roughness", 0.15)
        toy._set(fb, "Coat Weight", 0.6)
        self.flood_mat.node_tree.links.new(hull_mask(self.flood_mat.node_tree, self.carver, grow=-0.05, top=0.0),
                                           fb.inputs["Alpha"])
        if hasattr(self.flood_mat, "surface_render_method"):
            self.flood_mat.surface_render_method = "DITHERED"
        self.flood_all = self._flood_box("flood_all", -L / 2 + 0.05, L / 2 * 0.8)
        self.flood_mid = self._flood_box("flood_mid", BULK_X[0] + 0.03, BULK_X[1] - 0.03)
        # ---- inboard engine, shaft, propeller, rudder
        red_e = tx.paint("bk_engine", "#C0392B", 0.35, coat=0.3)
        dark_m = tx.metal("bk_dark", "#2C2F33", 0.4, metallic=0.6)
        ex, ez = -1.6, -D + 0.42
        self.engine = [toy.box("engine_block", (0.62, 0.42, 0.34), (ex, 0.0, ez), mat=red_e, bevel=0.04),
                       toy.box("engine_head", (0.56, 0.32, 0.12), (ex, 0.0, ez + 0.23), mat=dark_m, bevel=0.02),
                       toy.cylinder("engine_flywheel", 0.17, 0.08, (ex - 0.36, 0.0, ez - 0.02), rotation=(0, R(90), 0),
                                    mat=dark_m)]
        for k in range(3):
            self.engine.append(toy.cylinder(f"engine_plug{k}", 0.035, 0.08, (ex - 0.18 + 0.18 * k, 0.0, ez + 0.32),
                                            mat=steel))
        sx = -L / 2
        self.engine.append(_curve("shaft", [(ex - 0.4, 0.0, ez - 0.05), (sx - 0.45, 0.0, -D + 0.18)], 0.035, steel))
        self.prop = toy.empty("prop", (sx - 0.48, 0.0, -D + 0.18), self.body)
        phub = toy.sphere("prop_hub", 0.08, (0, 0, 0), scale=(1.5, 1, 1), mat=brass, subdiv=1)
        phub.parent = self.prop
        for k in range(3):
            a = 2 * math.pi * k / 3
            bl = toy.sphere(f"prop_blade{k}", 0.16, (0, 0, 0), scale=(0.25, 0.7, 1.0), mat=brass, subdiv=1)
            bl.parent = self.prop
            bl.location = (0, math.sin(a) * 0.17, math.cos(a) * 0.17)
            bl.rotation_euler = (-a, R(30), 0)
        self.rudder = toy.empty("rudder_hinge", (sx - 0.72, 0.0, -D + 0.3), self.body)
        rd = extrude_y("rudder", [(0.0, 0.25), (0.0, -0.45), (-0.38, -0.38), (-0.42, 0.18)], -0.03, 0.03, steel)
        rbev = rd.modifiers.new("round", "BEVEL")
        rbev.width, rbev.segments = 0.015, 2
        rd.parent = self.rudder
        stock = toy.cylinder("rudder_stock", 0.03, D + HF + 0.1, (0, 0.0, (D + HF + 0.1) / 2 - 0.05), mat=steel)
        stock.parent = self.rudder
        # ---- hand bilge pump on deck, hose down into the middle compartment, spout over the side
        yel = tx.paint("bk_pump", "#F2C230", 0.4)
        px, py = 0.62, 0.25
        pump_body = toy.cylinder("pump_body", 0.07, 0.5, (px, py, HF + 0.24), mat=yel)
        self.pump_handle = toy.empty("pump_handle", (px, py, HF + 0.52), self.body)
        hrod = toy.cylinder("pump_rod", 0.02, 0.25, (0, 0, 0.1), mat=steel)
        hrod.parent = self.pump_handle
        hbar = toy.box("pump_tbar", (0.3, 0.04, 0.04), (0, 0, 0.22), mat=dark_m, bevel=0.01)
        hbar.parent = self.pump_handle
        hose = _curve("pump_hose", [(px, py, HF), (px, py - 0.05, -D + 0.25), (px - 0.1, py - 0.1, -D + 0.12)], 0.03,
                      _mat("bk_hose", "#1E1E1E", 0.7))
        spout = _curve("pump_spout", [(px, py, HF + 0.42), (px + 0.05, -0.55, HF + 0.42),
                                      (px + 0.05, -0.85, HF + 0.2)], 0.025, steel)
        self.pump = [pump_body, self.pump_handle, hose, spout]
        # ---- welding mask for Max
        self.mask = toy.box("weld_mask", (0.4, 0.07, 0.36), (0, 0, 0), mat=_mat("bk_mask", "#2B3A2E", 0.4), bevel=0.04)
        visor = toy.box("weld_visor", (0.26, 0.02, 0.1), (0, -0.04, 0.04), mat=_mat("bk_visor", "#0B1A10", 0.05, coat=1.0))
        visor.parent = self.mask
        for o in (self.keel + self.cabin + self.mast + self.bulkheads + self.engine + self.pump +
                  [self.prop, self.rudder]):
            if o.parent is None:
                o.parent = self.body
            toy.hide_tree(o, 1, True)
        for o in self.hull_parts:
            toy.hide_tree(o, 1, True)
        toy.hide_tree(self.mask, 1, True)
        for o in ext:                                                          # exterior: hidden behind the section
            if o.type in ("MESH", "CURVE", "FONT"):
                section_clip(o, self.section)
        for o in self.hull_parts + self.cabin:
            if o.type == "FONT":
                section_clip(o, self.section)
        self.cg = self._cg_marker()
        self.duck = self._duck()
        self.ship = self._giant_ship()
        # the solid slab of the first attempt (not part of the boat)
        self.slab = toy.box("slab", (3.0, 1.3, 0.4), (0, 0, 0), mat=tx.metal("bk_slab", "#7E858C", 0.35, along="x"),
                            bevel=0.03)
        self.slab.location = AWAY
        toy.add_noise(self.root, "location", 2, strength=0.03, scale=22, phase=1)       # gentle bobbing
        toy.add_noise(self.body, "rotation_euler", 0, strength=0.025, scale=30, phase=4)

    def _cg_marker(self):
        """A big glowing orange ball labelled WEIGHT: where the boat's weight is concentrated."""
        root = toy.empty("cg_marker", (0, 0, 0), self.body)
        ball_m = _mat("bk_weight_ball", "#FF7A1A", 0.35, coat=0.5)
        toy._set(toy._principled(ball_m), "Emission Color", (*toy.srgb("#FF7A1A"), 1))
        toy._set(toy._principled(ball_m), "Emission Strength", 0.6)
        ball = toy.sphere("cg_ball", 0.24, (0, 0, 0), mat=ball_m, subdiv=2)
        ball.parent = root
        ball.visible_shadow = False
        txt = bpy.data.curves.new("cg_text", "FONT")
        txt.body, txt.size, txt.extrude, txt.align_x, txt.align_y = "WEIGHT", 0.13, 0.01, "CENTER", "CENTER"
        from engine.cutaway import _bold_font
        if _bold_font():
            txt.font = _bold_font()
        to = bpy.data.objects.new("cg_text", txt)
        bpy.context.scene.collection.objects.link(to)
        to.data.materials.append(_mat("bk_weight_txt", "#FFFFFF", 0.4))
        to.parent = root
        to.location, to.rotation_euler = (0, -0.25, 0), (R(90), 0, 0)
        toy.hide_tree(root, 1, True)
        return root

    def _duck(self):
        root = toy.empty("duck", AWAY)
        body = toy.sphere("duck_body", 0.22, (0, 0, 0.12), scale=(1.3, 0.9, 0.8), mat=_mat("bk_duck", "#6B4A2E", 0.6), subdiv=1)
        head = toy.sphere("duck_head", 0.12, (0.22, 0, 0.32), mat=_mat("bk_duckhead", "#1F6B3A", 0.4, coat=0.5), subdiv=1)
        beak = toy.sphere("duck_beak", 0.06, (0.34, 0, 0.3), scale=(1.4, 0.8, 0.5), mat=_mat("bk_beak", "#F2A41F", 0.4), subdiv=0)
        eye = toy.sphere("duck_eye", 0.02, (0.3, -0.08, 0.36), mat=_mat("bk_eye", "#111111", 0.2), subdiv=0)
        for o in (body, head, beak, eye):
            o.parent = root
        toy.add_noise(root, "location", 2, strength=0.02, scale=10, phase=2)
        return root

    def _giant_ship(self):
        """A container ship: dark hull with red bottom, stacks of coloured containers, white bridge, funnel."""
        root = toy.empty("big_ship", AWAY)
        Ls, Ws = 34.0, 7.0
        hull_m = tx.paint("bk_ship_hull", "#1E2A3A", 0.45, coat=0.2, seams=1.5, seam_axis="x")
        red = tx.paint("bk_ship_bottom", "#9E2A22", 0.55)
        pts = [(-Ls / 2, -Ws / 2), (Ls / 2 - 5, -Ws / 2), (Ls / 2, 0), (Ls / 2 - 5, Ws / 2), (-Ls / 2, Ws / 2)]
        body = _prism("ship_hull", pts, -0.2, 4.2, mat=hull_m)
        bottom = _prism("ship_bottom", [(x * 1.01, y * 1.01) for x, y in pts], -3.2, -0.2, mat=red)
        stripe = toy.box("ship_stripe", (Ls - 5, Ws + 0.04, 0.25), (-2.5, 0, 4.0), mat=_mat("bk_ship_white", "#F2EEE6", 0.4))
        for o in (body, bottom, stripe):
            o.parent = root
        rnd = random.Random(11)
        cols = ["#C0392B", "#2E86C1", "#27AE60", "#F39C12", "#8E44AD", "#D35400", "#16A085", "#F1C40F"]
        for i in range(8):
            for layer in range(rnd.randint(2, 4)):
                c = tx.planks(f"bk_cont{i}_{layer}", cols[(i + layer) % 8], cols[(i + layer) % 8], width=0.18,
                              across="x", along="z", seam_dark=0.3)
                box = toy.box(f"container{i}_{layer}", (3.4, 6.2, 2.4), (-8.5 + 3.6 * i, 0, 5.4 + 2.45 * layer), mat=c,
                              bevel=0.03)
                box.parent = root
        white = tx.paint("bk_bridge", "#F2EEE6", 0.45)
        bridge = toy.box("ship_bridge", (3.8, 6.4, 6.0), (-14.0, 0, 7.2), mat=white, bevel=0.05)
        win = toy.box("ship_windows", (3.82, 6.0, 0.8), (-14.0, 0, 9.4), mat=_mat("bk_shipglass", "#1C2A3A", 0.1, coat=1.0))
        funnel = toy.cylinder("ship_funnel", 0.9, 3.0, (-15.6, 0.0, 11.0), mat=tx.paint("bk_funnel", "#C0392B", 0.4))
        for o in (bridge, win, funnel):
            o.parent = root
        return root

    def _flood_box(self, name, x0, x1):
        """Water inside the hull, trimmed to the hull's inner shape; grows up from the bottom."""
        root = toy.empty(f"{name}_root", ((x0 + x1) / 2, 0.0, -D - 0.05), self.body)
        b = toy.box(name, (x1 - x0, W / 2, 1.0), (0, W / 4 + 0.004, 0.5), mat=self.flood_mat, bevel=0)
        b.parent = root
        b.location = (0, W / 4 + 0.004, 0.5)
        root.scale = (1, 1, 0.001)
        toy.hide_tree(root, 1, True)
        return root

    def ride(self, obj, f):
        """Attach a label/arrow to the moving boat (it keeps its place relative to the boat from frame f)."""
        rl = V(toy.value_at(self.root, "location", f))
        world = V(obj.location)
        obj.parent = self.root
        obj.location = world - rl
        return obj

    def orbit(self, f0, f1, center, radius, ang0, ang1, z0, z1, lens=24, cut=True, follow_boat=False):
        """A camera that TURNS around `center` (deg: -90 = straight in front, from -Y; 0 = from +X),
        rising from z0 to z1, eased. follow_boat: the centre moves with the boat."""
        keys = []
        frames = list(range(f0, f1, 3)) + [f1]
        for f in frames:
            t = (f - f0) / max(1, f1 - f0)
            t = t * t * (3 - 2 * t)
            a = math.radians(ang0 + (ang1 - ang0) * t)
            c = V(center)
            if follow_boat:
                c = c + V(toy.value_at(self.root, "location", f)) - V(toy.value_at(self.root, "location", f0))
            cam = c + V((math.cos(a) * radius, math.sin(a) * radius, 0))
            cam.z = c.z + z0 + (z1 - z0) * t
            keys.append((f, cam, c))
        self.rig.track(f0, f1, keys, lens=lens, cut=cut)

    def mask_on(self, who, f0, f1):
        self.mask.parent = who.j["head"]
        self.mask.location = (0, -0.27, 0.22)
        toy.hide_tree(self.mask, f0, False)
        toy.hide_tree(self.mask, f1, True)

    def weld(self, f0, f1, at_fn, name, n=26):
        sparks = Sparks(name, "#FFD27A", n, 0.03, 14.0)
        rnd = random.Random(len(name))
        for f in range(f0, f1, 2):
            a = V(at_fn(f))
            sparks.fly(f, f + 5, a, a + V((rnd.uniform(-0.45, 0.45), -0.35, rnd.uniform(-0.45, 0.3))), shrink=True)
        sparks.finish()
        events.add(f0, "weld", duration=f1 - f0, gain=0.6)

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
        self.rig.build()

    # ------------------- helpers -------------------

    def place_boat(self, f, x, z=0.0, roll=0.0, pitch=0.0, cut=True):
        """Key the boat at frame f (cut=True: hold the previous pose until f-1, then snap)."""
        if cut:
            toy.key_hold(self.root, "location", f - 1, "CONSTANT")
            toy.key_hold(self.body, "rotation_euler", f - 1, "CONSTANT")
        _key(self.root, f, location=V((x, BOAT_Y, z)))
        _key(self.body, f, rotation_euler=V((R(roll), R(pitch), 0)))

    def boat_key(self, f, x=None, z=None, roll=None, pitch=None):
        if x is not None or z is not None:
            cur = V(toy.value_at(self.root, "location", f))
            _key(self.root, f, location=V((cur.x if x is None else x, BOAT_Y, cur.z if z is None else z)))
        if roll is not None or pitch is not None:
            cur = toy.value_at(self.body, "rotation_euler", f)
            _key(self.body, f, rotation_euler=V((cur[0] if roll is None else R(roll), cur[1] if pitch is None else R(pitch), 0)))

    def cutaway(self, f_open, f_close, frames=12):
        """Open the boat (front half peels away to show inside) at f_open, close it again at f_close."""
        toy.key_hold(self.section, "location", f_open - 1)
        _key(self.section, f_open + frames, location=V((0, 0.0, 0)))
        if f_close is not None:
            _key(self.section, f_close, location=V((0, 0.0, 0)))
            _key(self.section, f_close + frames, location=V((0, -6.0, 0)))
        events.add(f_open, "whoosh", gain=0.3)

    def _hide_props(self, f):
        for o in [self.mask] + getattr(self, "held_props", []):
            toy.hide_tree(o, f, True)

    def at(self, f, spot, face_to=None):
        toy.hide_tree(self.max.root, f, False)
        toy.hide_tree(self.mb.root, f, True)
        self._hide_props(f)
        self.max.cut_place(f, spot, facing_to(spot, face_to) if face_to is not None else 0)
        self.max.pose(f + 6)

    def aboard(self, f, local=(-1.85, 0.42), face_deg=0):
        toy.hide_tree(self.max.root, f, True)
        toy.hide_tree(self.mb.root, f, False)
        self._hide_props(f)
        self.mb.cut_place(f, V((local[0], local[1], HF)), face_deg)
        self.mb.pose(f + 6)

    def flood(self, root, f0, f1, level):
        """Water rising inside the hull from f0 to f1 up to `level` (m above the keel)."""
        toy.hide_tree(root, f0, False)
        _key(root, f0, scale=V((1, 1, 0.001)))
        _key(root, f1, scale=V((1, 1, level)))

    def scratch_head(self, who, f0, f1):
        who.pose(f0 + 4, shoulderR=(-25, 140, 0), head=(0, 14, 0))
        who.pose(f1 - 4, shoulderR=(-25, 150, 0), head=(0, 10, 0))
        who.brows(f0 + 4, 0.9)
        who.brows(f1, 0.0)
        who.pose(f1)

    def bubbles(self, f0, f1, name, origin_fn, rate=2, size=0.05, rise=1.4):
        Puffs(name, "#E2F6FF", count=30, size=size, seed=len(name)).emit(range(f0, f1, rate), origin_fn, rise=rise,
                                                                         life=18, drift=0.2)

    def shot(self, f0, f1, x0, x1, z=0.6, dist=6.2, aim_z=-0.2, lens=22, cut=True):
        """Side-on cutaway framing: waterline in the middle, sky above, lake bed below."""
        self.rig.shot(f0, f1, cam_from=(x0, -dist, z), cam_to=(x1, -dist + 0.4, z), aim_from=(x0, 1.0, aim_z),
                      aim_to=(x1, 1.0, aim_z), lens=lens, fstop=8.0, cut=cut)

    # ------------------- the ladder -------------------

    SLAB_HOME = V((-8.3, 1.0, DOCK_TOP + 0.18))
    STERN_LOCAL = (-2.05, 0.42)

    def a_build_slab(self, i, b, e):
        L_ = e - b
        home = self.SLAB_HOME
        self.slab.scale = (0.8, 0.85, 0.9)
        _key(self.slab, b, location=home)
        _hide(self.slab, 0, True)
        _hide(self.slab, b + 2, False)
        _key(self.slab, b + 2, scale=V((0.25, 0.85, 0.9)))
        weld_end = b + int(L_ * 0.6)
        _key(self.slab, weld_end, scale=V((0.8, 0.85, 0.9)))              # it grows plate by plate as he welds
        spot = V((-6.75, 0.55, DOCK_TOP))
        self.at(b, spot, home)
        self.mask_on(self.max, b + 2, weld_end + 4)
        self.max.crouch(b + 4, weld_end, frames=6, lean=25)
        self.weld(b + 8, weld_end, lambda f: home + V((1.2 * (f - b) / max(1, weld_end - b) - 0.1, -0.55, 0.1)),
                  "weld_slab")
        self.max.turn(weld_end + 4, 0, frames=6)                              # turns to us, thumbs up
        self.max.pose(weld_end + 10, shoulderL=(-90, 0, 20))
        self.max.smile(weld_end + 10, big=True)
        label("SOLID STEEL", home + V((0, -0.7, 0.75)), b + int(L_ * 0.45), e, size=0.26, tilt=-4)
        self.shot(b, e, -7.5, -7.3, z=1.2, dist=5.2, aim_z=0.7)

    def a_fail_sink(self, i, b, e):
        L_ = e - b
        home = self.SLAB_HOME
        tip = b + int(L_ * 0.28)
        edge = V((-5.9, home.y, home.z))
        bottom = V((-4.6, home.y, BED + 0.18))
        land = tip + int(L_ * 0.3)
        _key(self.slab, b, location=home, rotation_euler=V((0, 0, 0)))
        _key(self.slab, b + 6, location=home)
        _key(self.slab, tip, location=edge, rotation_euler=V((0, 0, 0)))          # shoved along the dock...
        _key(self.slab, tip + 6, location=edge + V((0.5, 0, -0.45)), rotation_euler=V((0, R(25), 0)))   # ...tips off
        _key(self.slab, land, location=bottom, rotation_euler=V((0, R(3), 0)))     # straight down
        toy.set_interpolation(self.slab, "location", (b + 6,), "LINEAR")
        events.add(tip + 6, "splash", gain=0.9)
        events.add(tip + 8, "bubbles", duration=int(L_ * 0.3))
        events.add(land, "underwater_thud")
        rnd = random.Random(3)
        self.bubbles(tip + 6, land + 12, "sink_bubbles",
                     lambda f: V(toy.value_at(self.slab, "location", f)) + V((rnd.uniform(-0.9, 0.9), -0.62, 0.2)), rate=1)
        Puffs("sand_puff", "#CDB585", count=10, size=0.3, seed=3).emit(
            range(land, land + 10, 1), lambda f: bottom + V((rnd.uniform(-1.2, 1.2), -0.62, -0.05)), rise=0.4, life=20,
            drift=0.4)
        Spray("sink_splash", self.drop_mat, count=24, radius=0.05, seed=4).run(
            tip + 6, tip + 18, source=V((-5.3, 0.4, 0.05)), target=V((-5.3, 0.4, 0.1)), spread=1.1, arc=1.0, period=13)
        # the physics, sized: weight beats the push-up 8 to 1
        f_on = land + 6
        arrow("slab_weight", bottom + V((-0.5, -0.7, 2.0)), (0, 0, -1.65), f_on, e, color="#FF7A1A", width=0.17)
        label("WEIGHT", bottom + V((-1.45, -0.75, 1.5)), f_on + 2, e, size=0.28, tilt=-5, color="#FF7A1A")
        arrow("slab_buoy", bottom + V((0.65, -0.7, 0.3)), (0, 0, 0.3), f_on + 8, e, color="#5EC8FF", width=0.08)
        label("BUOYANCY", bottom + V((1.2, -0.75, 0.95)), f_on + 10, e, size=0.22, tilt=5, color="#5EC8FF",
              outline="#0A2A3A")
        behind = V((-9.85, home.y - 0.25, DOCK_TOP))
        self.at(b, behind, behind + V((1, 0, 0)))
        self.max.pose(b + 4, shoulderL=(-85, 0, 0), shoulderR=(-85, 0, 0), spine=(28, 0, 0))   # hands on the slab
        self.max.walk(b + 6, tip, to=V((-7.45, behind.y, DOCK_TOP)), facing_deg=90, step_frames=7)
        self.max.pose(tip + 2)
        end_spot = V((-6.75, behind.y, DOCK_TOP))
        self.max.walk(tip + 4, tip + 16, to=end_spot, facing_deg=90, step_frames=6)
        self.max.turn(tip + 18, facing_to(end_spot, bottom + V((0, -3, 0))), frames=6)          # looks down at it
        self.max.pose(tip + 26, head=(25, 0, 0))
        self.max.brows(tip + 20, 1.0)
        self.max.pose(land + 4, shoulderR=(-150, 0, 40), head=(10, 0, 0))                      # deadpan salute
        self.max.pose(e - 4, shoulderR=(-150, 0, 40), head=(10, 0, 0))
        # camera: on the dock with Max, then FOLLOWS the slab down through the water
        self.rig.shot(b, tip + 4, cam_from=(-8.6, -4.4, 1.6), cam_to=(-7.2, -4.8, 1.2), aim_from=(-8.6, 0.8, 0.6),
                      aim_to=(-6.8, 0.8, 0.4), lens=24, fstop=8.0, cut=True)
        self.rig.shot(tip + 5, land + 4, cam_from=(-6.4, -5.2, 0.4), cam_to=(-5.0, -5.6, -1.2),
                      aim_from=(-5.6, 0.8, -0.3), aim_to=(-4.6, 0.8, -1.9), lens=24, fstop=8.0, blend=10)
        self.rig.shot(land + 5, e, cam_from=(-5.4, -5.6, -0.4), cam_to=(-5.7, -6.2, -0.1),
                      aim_from=(-5.0, 0.8, -1.3), aim_to=(-5.3, 0.8, -1.0), lens=22, fstop=8.0, blend=14)

    def a_hull(self, i, b, e):
        L_ = e - b
        toy.key_hold(self.slab, "location", b - 1)
        toy.set_interpolation(self.slab, "location", (b - 1,), "CONSTANT")   # it stays on the bed, then is gone
        _key(self.slab, b, location=AWAY)
        self.place_boat(b, BOAT_X, z=0.6)                                    # welded on the slipway, then lowered in
        build = b + int(L_ * 0.32)
        for k, o in enumerate(self.hull_parts):
            toy.hide_tree(o, b + 2 + k % 6, False)
            _key(o, b + 2 + k % 6, scale=V((0.01, 0.01, 0.01)))
            _key(o, b + 10 + k % 6, scale=V((1, 1, 1)))
        spot = V((-6.55, 0.55, DOCK_TOP))
        self.at(b, spot, (BOAT_X, 0.4, 0.4))
        self.mask_on(self.max, b + 2, build + 2)
        self.max.hammer(b + 8, build - 2, hand="R")
        self.weld(b + 10, build, lambda f: V((BOAT_X - L / 2 + 0.05 + 4.2 * ((f - b) % 24) / 24, BOAT_Y - 0.9, HF + 0.62)),
                  "weld_hull")
        settle = build + 24
        self.boat_key(build + 2, z=0.6)
        self.boat_key(settle, z=0.0)                                            # it settles to its waterline
        events.add(settle - 8, "splash", gain=0.5)
        up = settle + 4
        rise = up + int(L_ * 0.18)
        self.cutaway(settle - 2, rise - 14)                                   # frontal shot only: it's mostly air
        arrow("buoyancy", (BOAT_X + 0.3, -0.25, -D - 1.15), (0, 0, 0.95), up, e, color="#5EC8FF", width=0.12)
        label("BUOYANCY", (BOAT_X + 0.95, -0.3, -D - 1.25), up + 2, e, size=0.24, tilt=5, color="#5EC8FF", outline="#0A2A3A")
        arrow("weight", (BOAT_X - 0.2, -0.25, HF + 1.2), (0, 0, -0.95), up + 4, e, color="#FF7A1A", width=0.12)
        label("WEIGHT", (BOAT_X - 0.95, -0.3, HF + 1.3), up + 6, e, size=0.24, tilt=-5, color="#FF7A1A")
        # the aha: the water it pushed aside rises out of the lake as a block of the SAME weight
        blk_m = _mat("bk_displaced", "#46B8E8", 0.15, coat=0.6)
        toy._set(toy._principled(blk_m), "Emission Color", (*toy.srgb("#46B8E8"), 1))
        toy._set(toy._principled(blk_m), "Emission Strength", 0.35)
        rise = up + int(L_ * 0.18)
        block = toy.box("displaced_water", (1.06, 1.06, 1.06), (0, 0, 0), mat=blk_m, bevel=0.06)
        bx = BOAT_X + 3.6
        block.location = (bx, 0.6, -1.4)
        _hide(block, 0, True)
        _hide(block, rise, False)
        _key(block, rise, location=V((bx, 0.6, -1.4)))
        _key(block, rise + 24, location=V((bx, 0.6, 1.2)))                      # rises out of the lake
        _hide(block, e, True)
        events.add(rise, "bubbles", duration=24, gain=0.5)
        events.add(rise + 24, "pop", gain=0.5)
        label("1.2 T OF WATER", (bx, -0.4, 2.15), rise + 26, e, size=0.24, tilt=-4, color="#5EC8FF", outline="#0A2A3A")
        label("=", (BOAT_X + 2.3, -0.4, 1.25), rise + 32, e, size=0.5, tilt=0, color="#FFFFFF", outline="#203040")
        label("1.2 T BOAT", (BOAT_X + 0.6, -0.4, HF + 1.75), rise + 36, e, size=0.24, tilt=4)
        self.max.turn(up, facing_to(spot, (spot.x + 0.5, -6, 0)), frames=6)
        self.max.point(up + 6, e - 4, hand="R", up_deg=10, side_deg=-30)
        self.max.smile(up + 4, big=True)
        # camera: Max welding, then down UNDER the boat looking up as it settles, then back out for the block
        self.rig.shot(b, settle - 6, cam_from=(-6.0, -4.6, 1.5), cam_to=(-5.0, -5.4, 1.0), aim_from=(-5.4, 0.5, 0.8),
                      aim_to=(BOAT_X, 0.5, 0.4), lens=24, fstop=8.0, cut=True)
        self.rig.shot(settle - 5, rise, cam_from=(BOAT_X - 0.4, -5.6, -1.7), cam_to=(BOAT_X + 0.3, -5.8, -1.3),
                      aim_from=(BOAT_X, 0.5, -0.3), aim_to=(BOAT_X + 0.3, 0.5, -0.1), lens=22, fstop=8.0, blend=14)
        self.rig.shot(rise + 1, e, cam_from=(BOAT_X + 1.2, -7.4, 0.8), cam_to=(BOAT_X + 1.6, -6.9, 0.7),
                      aim_from=(BOAT_X + 1.2, 0.5, 0.4), aim_to=(BOAT_X + 1.6, 0.5, 0.4), lens=22, fstop=8.0, blend=18)

    def a_fail_capsize(self, i, b, e):
        L_ = e - b
        for k, o in enumerate(self.cabin + self.mast):
            toy.hide_tree(o, b + 3 + k % 5, False)
            _key(o, b + 3 + k % 5, scale=V((0.01, 0.01, 0.01)) if o.parent is self.body else V(o.scale))
            _key(o, b + 10 + k % 5, scale=V((1, 1, 1)))
        events.add(b + 4, "hammer", gain=0.5)
        self.aboard(b, local=self.STERN_LOCAL, face_deg=90)
        climb = b + int(L_ * 0.25)
        roof = V((-0.85, 0.36, HF + 1.07))
        self.mb.move(climb, climb + 6, V((-1.6, 0.36, HF + 1.55)))              # jumps UP first...
        self.mb.move(climb + 6, climb + 11, roof)                                # ...and lands on the roof
        self.mb.pose(climb + 4, legL=(-60, 0, 0), legR=(-20, 0, 0), shoulderL=(-120, 0, -10), shoulderR=(-120, 0, 10))
        self.mb.turn(climb + 10, 0, frames=6)
        self.mb.cheer(climb + 14, climb + 34)
        events.add(climb + 5, "boing", gain=0.3)
        toy.hide_tree(self.cg, climb - 6, False)
        _key(self.cg, climb - 6, location=V((-0.2, -0.05, 0.25)), scale=V((0.01, 0.01, 0.01)))
        _key(self.cg, climb, location=V((-0.2, -0.05, 0.25)), scale=V((1, 1, 1)))
        _key(self.cg, climb + 14, location=V((-0.5, -0.05, HF + 1.05)))          # the weight climbs with him
        tip0, tip1, flip = climb + 30, b + int(L_ * 0.66), b + int(L_ * 0.78)
        label("HEAVY UP HIGH = TIPS OVER", (BOAT_X + 0.2, -0.6, HF + 2.3), climb + 16, flip, size=0.22, tilt=-4,
              color="#FF7A1A")
        self.boat_key(climb + 26, roll=0)
        self.boat_key(tip0, roll=-10)
        self.boat_key(tip1, roll=-38)                                           # leans... more...
        self.boat_key(flip, roll=-150)                                          # ...over
        self.boat_key(flip + 10, roll=-165)
        self.boat_key(e, roll=-168)
        self.mb.brows(tip0, 1.0)
        self.mb.pose(tip0 + 4, shoulderL=(-10, -80, 0), shoulderR=(-10, 80, 0), spine=(0, 0, 12))   # arms out, wobbling
        events.add(tip0, "creak")
        events.add(tip1 - 6, "creak", gain=0.9)
        events.add(flip - 4, "splash")
        Spray("capsize_splash", self.drop_mat, count=30, radius=0.06, seed=5).run(
            flip - 4, flip + 12, source=V((BOAT_X + 0.6, -0.4, 0.05)), target=V((BOAT_X + 0.6, -0.4, 0.1)),
            spread=1.6, arc=1.2, period=15)
        toy.hide_tree(self.mb.root, flip - 8, True)                              # thrown into the lake
        toy.hide_tree(self.max.root, flip - 8, False)
        self._hide_props(flip - 8)
        in_water = V((BOAT_X + 2.85, -0.95, -1.3))
        self.max.cut_place(flip - 8, V((BOAT_X + 0.6, -0.95, 2.2)), 0)
        self.max.move(flip - 7, flip + 1, V((BOAT_X + 2.6, -0.95, -1.6)))
        self.max.move(flip + 2, flip + 12, in_water)
        self.max.wave(flip + 12, e, hand="R")
        hatfish = self._fish("hat_fish", "#FF8C1A")                                # ...with a fish on his hat
        hatfish.parent = self.max.j["head"]
        hatfish.location, hatfish.rotation_euler = (0.05, 0, 0.62), (0, 0, R(20))
        toy.hide_tree(hatfish, 1, True)
        toy.hide_tree(hatfish, flip + 10, False)
        toy.hide_tree(hatfish, e, True)
        events.add(flip + 14, "boing", gain=0.35)
        self.max.brows(flip + 12, 1.0)
        self.max.key("mouth", flip + 14, scale=(1.1, 0.6, 2.2))
        rnd = random.Random(6)
        self.bubbles(flip, flip + 20, "capsize_bubbles", lambda f: in_water + V((rnd.uniform(-0.8, 0.8), -0.1, 0.6)))
        self.rig.shot(b, flip - 6, cam_from=(BOAT_X - 1.4, -7.4, 1.6), cam_to=(BOAT_X - 0.2, -5.8, 1.5),
                      aim_from=(BOAT_X - 0.3, 0.5, 1.0), aim_to=(BOAT_X + 0.1, 0.5, 1.2), lens=22, fstop=8.0, cut=True)
        self.rig.shot(flip - 5, e, cam_from=(BOAT_X + 1.1, -6.4, 1.0), cam_to=(BOAT_X + 2.0, -5.4, 0.4),
                      aim_from=(BOAT_X + 1.2, 0.0, 0.0), aim_to=(BOAT_X + 2.4, -0.5, 0.0), lens=22, fstop=8.0, blend=10)

    def a_keel(self, i, b, e):
        L_ = e - b
        self.place_boat(b, BOAT_X, z=0.0, roll=0)
        for o in self.mast:
            toy.hide_tree(o, b, True)
        for k, o in enumerate(self.keel):
            toy.hide_tree(o, b + 6 + 4 * k, False)
            _key(o, b + 6 + 4 * k, scale=V((1, 1, 0.01)))
            _key(o, b + 18 + 4 * k, scale=V((1, 1, 1)))
        self.weld(b + 6, b + int(L_ * 0.3), lambda f: V((BOAT_X + 0.1, BOAT_Y - 0.1, -D - 0.05)), "weld_keel", n=18)
        toy.hide_tree(self.cg, b, False)
        _key(self.cg, b, location=V((-0.5, -0.05, HF + 1.05)), scale=V((1, 1, 1)))
        _key(self.cg, b + int(L_ * 0.25), location=V((-0.5, -0.05, HF + 1.05)))
        _key(self.cg, b + int(L_ * 0.38), location=V((0.1, -0.06, -D - 0.75)))     # drops right down into the keel
        events.add(b + int(L_ * 0.3), "whoosh", gain=0.4)
        label("HEAVY DOWN LOW", (BOAT_X - 1.1, -0.6, -D - 0.75), b + int(L_ * 0.38), e, size=0.26,
              tilt=4, color="#FF7A1A")
        label("= STANDS BACK UP", (BOAT_X - 1.1, -0.6, -D - 1.1), b + int(L_ * 0.38) + 6, e, size=0.22,
              tilt=4, color="#FFFFFF", outline="#203040")
        toy.hide_tree(self.cg, e, True)
        self.aboard(b, local=(0.85, 0.1), face_deg=0)
        self.mb.point(b + 8, b + int(L_ * 0.35), hand="R", up_deg=-50, side_deg=0)      # "down there"
        push = b + int(L_ * 0.42)
        for f, r in ((push, 0), (push + 8, -34), (push + 20, 15), (push + 32, -7), (push + 44, 3), (push + 56, 0)):
            self.boat_key(f, roll=r)                                            # rolled hard... and back up
        self.mb.pose(push + 4, shoulderL=(-10, -80, 0), shoulderR=(-10, 80, 0))
        self.mb.pose(push + 56)
        self.mb.smile(push + 50, big=True)
        self.mb.cheer(push + 58, e - 2)
        events.add(push, "splash", gain=0.4)
        events.add(push + 8, "creak", gain=0.6)
        arrow("keel_weight", (BOAT_X + 0.1, -0.3, -D - 0.4), (0, 0, -0.85), b + int(L_ * 0.3), e, color="#FF7A1A")
        label("KEEL", (BOAT_X + 1.2, -0.45, -D - 0.6), b + int(L_ * 0.2), e, size=0.26, tilt=-4)
        self.rig.shot(b, push - 4, cam_from=(BOAT_X + 0.9, -4.6, -1.7), cam_to=(BOAT_X + 0.3, -5.8, -0.6),
                      aim_from=(BOAT_X + 0.1, 0.4, -1.3), aim_to=(BOAT_X, 0.4, -0.6), lens=22, fstop=8.0, cut=True)
        self.orbit(push - 3, e, center=(BOAT_X + 0.1, 0.4, -0.3), radius=6.2, ang0=-110, ang1=-70, z0=0.4, z1=1.2,
                   lens=22, cut=False)

    def a_fail_leak(self, i, b, e):
        L_ = e - b
        bx = BOAT_X + 1.5
        self.place_boat(b, bx, z=0.0)
        pop = b + int(L_ * 0.16)
        hole = V((0.2, 0.2, -D + 0.08))
        jet = Spray("leak_jet", self.drop_mat, count=26, radius=0.04, seed=6)
        for pt in jet.parts:
            pt.parent = self.body
        jet.run(pop, e, source=hole, target=hole + V((0.05, -0.05, 0.75)), spread=0.12, arc=0.05, period=8)
        self.cutaway(b + 2, pop + 18)                                          # open for the frontal close-up only
        _key(self.hatch, pop + 4, rotation_euler=V((0, 0, 0)))
        _key(self.hatch, pop + 12, rotation_euler=V((R(105), 0, 0)))              # Max flips the hatch open (away from him)
        events.add(pop + 6, "clink", gain=0.5)
        self.flood(self.flood_all, pop + 4, e - 4, D + HF - 0.12)            # the hull fills up...
        self.boat_key(pop, z=0.0)
        self.boat_key(e - 4, z=-0.55)                                           # ...heavier, lower, awash
        events.add(pop, "rivet_pop")
        events.add(pop + 2, "water_rush", duration=e - pop - 2)
        label("LEAK!", (bx + 0.25, -0.5, -D - 0.45), pop + 2, pop + 40, size=0.32, tilt=6, color="#FF4A3A")
        arrow("leak_in", (bx + 0.2, -0.3, -D - 0.55), (0, 0, 0.45), pop + 2, pop + 40, color="#5EC8FF", width=0.08)
        # the bucket (with a disc of water that shows while it is full)
        bucket = toy.cylinder("bucket", 0.2, 0.3, (0, 0, 0), mat=tx.paint("bk_bucket", "#3A7BD5", 0.4))
        self.held_props = getattr(self, "held_props", []) + [bucket]
        bpy.ops.mesh.primitive_torus_add(major_radius=0.19, minor_radius=0.014, location=(0, 0, 0.16),
                                         rotation=(R(90), 0, 0))
        handle = bpy.context.active_object
        handle.name = "bucket_handle"
        toy._finish(handle, tx.metal("bk_bucket_h", "#9AA0A6"), subdiv=0, parent=bucket)
        full = toy.cylinder("bucket_water", 0.18, 0.02, (0, 0, 0.11), mat=self.drop_mat)
        full.parent = bucket
        spot = (0.12, 0.55)                                                      # on deck behind the hatch, clear of the wheelhouse
        self.aboard(b, local=spot, face_deg=0)                                  # facing us, over the open hull
        self.mb.hold(bucket, "R")
        bucket.location = (0, -0.06, -0.16)
        toy.hide_tree(bucket, 1, True)
        toy.hide_tree(bucket, pop + 8, False)
        toy.hide_tree(bucket, e, True)
        self.mb.brows(pop + 2, 1.0)
        self.mb.key("mouth", pop + 4, scale=(1.1, 0.6, 2.2))
        drops = Sparks("bail_drops", "#CFEFFA", 120, 0.085, 0.3)
        for pt in drops.parts:
            pt.data.materials[0] = self.drop_mat
        rnd = random.Random(12)
        # 1 scoop (facing us, bent into the flooded hull) -> 2 turn round -> 3 throw over the back rail
        f = pop + 12
        cycle = 40
        while f + cycle <= e - 2:
            toy.hide_tree(full, f, True)
            self.mb.turn(f, 0, frames=6)
            self.mb.pose(f + 6, shoulderR=(-15, 0, 6), spine=(70, 0, 0), head=(-25, 0, 0))   # scoop
            toy.hide_tree(full, f + 12, False)                                     # bucket comes up full
            self.mb.pose(f + 14, shoulderR=(-60, 0, 10), spine=(10, 0, 0))
            self.mb.turn(f + 16, 180, frames=8)                                    # turns round with it
            self.mb.pose(f + 26, shoulderR=(-170, 0, 20), spine=(-15, 0, 0))       # heave over the rail
            throw = f + 27
            toy.hide_tree(full, throw, True)
            zb = toy.value_at(self.root, "location", throw)[2]
            src = V((bx + spot[0] + 0.1, BOAT_Y + W / 2 + 0.1, zb + HF + 1.15))
            for j in range(20):                                                    # the water arcs into the lake
                drops.fly(throw + j % 4, throw + 16 + j % 4, src + V((rnd.uniform(-0.15, 0.15), 0, 0)),
                          V((src.x + rnd.uniform(-0.5, 0.5), BOAT_Y + rnd.uniform(1.6, 2.3), -0.05)), shrink=True)
            Puffs(f"bail_splash{f}", "#E2F6FF", count=8, size=0.22, seed=f).emit(
                range(throw + 16, throw + 20), lambda ff: V((src.x, BOAT_Y + 1.9, 0.0)), rise=0.25, life=10, drift=0.3)
            events.add(throw, "whoosh", gain=0.25)
            events.add(throw + 16, "splash", gain=0.4)
            f += cycle
        drops.finish()
        label("BAILING!", (bx + 0.6, -0.6, HF + 2.3), pop + 30, e, size=0.26, tilt=-5, color="#FFFFFF",
              outline="#203040")
        # camera: close underwater on the hole, then it TURNS around the boat to a raised 3/4 view so the
        # scoop -> turn -> throw over the back rail is plain to see
        self.rig.shot(b, pop + 30, cam_from=(bx - 0.1, -4.6, -0.2), cam_to=(bx + 0.1, -3.4, -0.55),
                      aim_from=(bx + 0.1, 0.3, -0.35), aim_to=(bx + 0.2, 0.3, -0.5), lens=24, fstop=8.0, cut=True)
        self.orbit(pop + 31, e, center=(bx + spot[0] + 0.1, BOAT_Y + 0.2, HF + 0.7), radius=5.0, ang0=-95, ang1=-35, z0=0.4,
                   z1=2.2, lens=24, cut=False, follow_boat=True)

    def a_bulkheads(self, i, b, e):
        L_ = e - b
        self.place_boat(b, BOAT_X + 1.5, z=0.0)
        toy.hide_tree(self.flood_all, b, True)
        self.cutaway(b + 2, None)
        for k, o in enumerate(self.bulkheads):
            toy.hide_tree(o, b + 4 + 6 * k, False)
            _key(o, b + 4 + 6 * k, scale=V((0.01, 0.01, 0.01)))
            _key(o, b + 12 + 6 * k, scale=V((1, 1, 1)))
        self.weld(b + 6, b + int(L_ * 0.25), lambda f: V((BOAT_X + 1.5 + BULK_X[(f // 10) % 2], BOAT_Y + 0.03, -0.2 + 0.4 * ((f % 10) / 10))),
                  "weld_bulk", n=20)
        pop = b + int(L_ * 0.28)
        hole = V((-0.1, 0.2, -D + 0.08))
        jet = Spray("leak_jet2", self.drop_mat, count=22, radius=0.04, seed=7)
        for pt in jet.parts:
            pt.parent = self.body
        jet.run(pop, b + int(L_ * 0.7), source=hole, target=hole + V((0.05, -0.05, 0.6)), spread=0.1, arc=0.05,
                period=8)
        full = pop + int(L_ * 0.25)
        self.flood(self.flood_mid, pop + 4, full, 0.8)                          # ONLY the middle compartment fills
        out = full + 6
        _key(self.flood_mid, e - 6, scale=V((1, 1, 0.12)))                      # ...and the pump empties it
        self.boat_key(pop, z=0.0)
        self.boat_key(full, z=-0.12)                                            # a touch lower: still afloat
        self.boat_key(e - 6, z=-0.02)
        for o in self.pump:
            toy.hide_tree(o, b + 2, False)
        spout = Spray("bilge_jet", self.drop_mat, count=34, radius=0.05, seed=8)
        for pt in spout.parts:
            pt.parent = self.body
        spout.run(out + 4, e, source=V((0.67, -0.85, HF + 0.2)), target=V((0.72, -1.5, -0.3)), spread=0.1, arc=0.5,
                  period=10)
        f = out
        while f < e - 4:                                                       # Max works the pump handle
            _key(self.pump_handle, f, location=V((0.62, 0.25, HF + 0.52)))
            _key(self.pump_handle, f + 5, location=V((0.62, 0.25, HF + 0.34)))
            f += 10
        events.add(pop, "rivet_pop", gain=0.7)
        events.add(out, "pump", duration=e - out)
        label("ONLY ONE ROOM FLOODS", (BOAT_X + 1.6, -0.55, -D - 0.6), full - 10, out + 24, size=0.22, tilt=-4,
              color="#5EC8FF", outline="#0A2A3A")
        label("WATERTIGHT WALLS", (BOAT_X + 1.5, -0.55, -D - 1.05), b + 10, out - 4, size=0.24, tilt=4)   # clear of the sticker
        label("PUMP", (BOAT_X + 2.55, -0.55, HF + 0.95), out, e, size=0.24, tilt=5, color="#F2C230", outline="#3A2A00")
        self.aboard(b, local=(0.6, 0.52), face_deg=0)                            # behind the pump, facing us
        f = out
        while f < e - 4:
            self.mb.pose(f, shoulderR=(-80, 0, 10), shoulderL=(-80, 0, -10), spine=(10, 0, 0))
            self.mb.pose(f + 5, shoulderR=(-50, 0, 10), shoulderL=(-50, 0, -10), spine=(22, 0, 0))
            f += 10
        self.mb.smile(e - 20, big=True)

        _key(self.hatch, e - 16, rotation_euler=V((R(105), 0, 0)))
        _key(self.hatch, e - 6, rotation_euler=V((0, 0, 0)))
        # camera: wide on the three compartments, then close on Max pumping the water out
        _key(self.section, out + 20, location=V((0, 0.0, 0)))                   # ...then it closes
        _key(self.section, out + 32, location=V((0, -6.0, 0)))
        self.rig.shot(b, out + 32, cam_from=(BOAT_X + 1.5, -5.6, 0.3), cam_to=(BOAT_X + 1.5, -5.0, 0.2),
                      aim_from=(BOAT_X + 1.5, BOAT_Y, -0.3), aim_to=(BOAT_X + 1.5, BOAT_Y, -0.3), lens=22, fstop=8.0,
                      cut=True)                                                     # head-on while open
        self.orbit(out + 33, e, center=(BOAT_X + 2.1, BOAT_Y, 0.6), radius=4.4, ang0=-88, ang1=-45, z0=0.6, z1=1.6,
                   lens=24, cut=False)                                              # turns only once closed

    def a_fail_drift(self, i, b, e):
        x0 = 7.0
        self.place_boat(b, x0, z=0.0)
        self.boat_key(e, x=x0 + 3.6)                                            # pushed by the wind... into the reeds
        toy.set_interpolation(self.root, "location", (b,), "LINEAR")
        self.aboard(b, local=(1.15, 0.3), face_deg=90)
        f, k = b + 6, 0
        while f < e - 4:                                                       # paddling with his hands
            self.mb.pose(f, shoulderL=(-60, 0, -10), shoulderR=(-60, 0, 10), spine=(28, 0, 0))
            self.mb.pose(f + 4, shoulderL=(25, 0, -10), shoulderR=(25, 0, 10), spine=(32, 0, 0))
            if k % 2:
                events.add(f + 4, "paddle_splash", gain=0.6)
            f += 8
            k += 1
        self.mb.brows(b + 10, 0.8)
        d0, d1 = b + 4, e
        _key(self.duck, d0 - 1, location=AWAY)
        _key(self.duck, d0, location=V((x0 + 3.5, -0.9, 0.0)), rotation_euler=V((0, 0, R(180))))
        _key(self.duck, d1, location=V((x0 - 1.2, -0.9, 0.0)), rotation_euler=V((0, 0, R(180))))   # against the wind
        toy.set_interpolation(self.duck, "location", (d0 - 1,), "CONSTANT")
        toy.set_interpolation(self.duck, "location", (d0,), "LINEAR")
        _key(self.duck, d1 + 1, location=AWAY)
        toy.set_interpolation(self.duck, "location", (d1,), "CONSTANT")
        events.add(b + int((e - b) * 0.5), "quack")
        self.mb.turn(b + int((e - b) * 0.55), 0, frames=6)                        # Max stares at the duck
        self.mb.brows(b + int((e - b) * 0.55), 1.0)
        events.add(b, "wind", duration=e - b, gain=0.8)
        self.ride(arrow("wind", (x0 - 0.6, -0.6, 2.4), (1.6, 0, 0), b + 6, e, color="#FFFFFF"), b)
        self.ride(label("WIND", (x0 + 0.2, -0.7, 2.85), b + 8, e, size=0.26, tilt=-4, color="#FFFFFF", outline="#203040"), b)
        self.ride(label("NO ENGINE", (x0 + 0.6, -0.6, -D - 0.6), b + 14, e, size=0.24, tilt=4), b)
        self.rig.shot(b, e, cam_from=(x0 + 0.4, -6.6, 1.2), cam_to=(x0 + 3.0, -5.6, 0.7), aim_from=(x0 + 0.7, 0.4, 0.4),
                      aim_to=(x0 + 3.3, 0.4, 0.3), lens=22, fstop=8.0, cut=True)

    def a_propeller(self, i, b, e):
        L_ = e - b
        x0 = 0.5
        self.place_boat(b, x0, z=0.0)
        for k, o in enumerate(self.engine + [self.prop, self.rudder]):
            toy.hide_tree(o, b + 4 + 2 * k, False)
        go = b + int(L_ * 0.3)
        self.cutaway(b + 2, go + 24)                                            # peek at the engine
        toy.key_hold(self.prop, "rotation_euler", go)
        self.prop.rotation_euler.x += 2 * math.pi * 0.2 * (self.total + 400 - go)
        self.prop.keyframe_insert("rotation_euler", frame=self.total + 400)
        toy.set_interpolation(self.prop, "rotation_euler", (go,), "LINEAR")
        self.boat_key(go, x=x0)
        self.boat_key(e, x=x0 + 4.5)                                            # surges forward (the bow is +X)
        for f, a in ((go + int(L_ * 0.35), 0), (go + int(L_ * 0.45), 25), (e - 6, 25)):
            _key(self.rudder, f, rotation_euler=V((0, 0, R(a))))                # the rudder swings to steer
        self.bubbles(go, e, "prop_wash", lambda f: V(toy.value_at(self.root, "location", f)) +
                     V((-L / 2 - 0.75, 0.0, -D + 0.18)), rate=1, size=0.05, rise=0.5)
        events.add(go - 10, "boat_motor", duration=e - go + 10)
        label("ENGINE", (x0 - 1.95, -0.45, -D + 0.02), b + 8, go + 20, size=0.2, tilt=-4, color="#FF7A1A")
        self.ride(label("PROPELLER", (x0 - L / 2 + 0.8, -0.45, -D - 0.6), go, e, size=0.24, tilt=5), go)
        self.ride(label("RUDDER", (x0 - L / 2 + 0.1, -0.45, -D + 1.25), go + 12, e, size=0.22, tilt=-5, color="#5EC8FF",
                        outline="#0A2A3A"), go)
        for k, dz in enumerate((-0.18, 0.0, 0.18)):                              # water thrown BACK...
            self.ride(arrow(f"water_back{k}", (x0 - L / 2 - 0.85, -0.3, -D + 0.18 + dz), (-0.8, 0, 0), go + 4 + 2 * k,
                            go + 60, color="#5EC8FF", width=0.07), go)
        self.ride(arrow("boat_fwd", (x0 + L / 2 - 0.2, -0.5, HF + 0.5), (1.1, 0, 0), go + 12, go + 60,
                        color="#FFD23F", width=0.12), go)                         # ...so the boat goes FORWARD
        self.ride(label("WATER BACK", (x0 - L / 2 - 1.25, -0.4, -D + 0.6), go + 6, go + 60, size=0.2, tilt=-4,
                        color="#5EC8FF", outline="#0A2A3A"), go)
        self.ride(label("BOAT FORWARD", (x0 + L / 2 + 0.3, -0.5, HF + 0.95), go + 14, go + 60, size=0.2, tilt=4), go)
        self.aboard(b, local=self.STERN_LOCAL, face_deg=90)
        self.mb.pose(b + 8, shoulderL=(20, 0, -15))                              # hand back on the tiller
        self.mb.cheer(go + 24, e - 2)
        self.mb.smile(go + 6, big=True)
        self.rig.shot(b, go + 30, cam_from=(x0 - L / 2 + 0.1, -3.6, -1.4), cam_to=(x0 - L / 2 + 0.4, -3.9, -1.3),
                      aim_from=(x0 - L / 2 - 0.1, 0.2, -0.75), aim_to=(x0 - L / 2 + 0.2, 0.2, -0.7), lens=26, fstop=8.0,
                      cut=True)
        self.rig.shot(go + 31, e, cam_from=(x0 - 0.6, -5.4, 0.0), cam_to=(x0 + 3.2, -7.4, 0.9),
                      aim_from=(x0 - 0.8, 0.3, -0.3), aim_to=(x0 + 3.0, 0.3, 0.2), lens=22, fstop=8.0, blend=16)

    def a_finale(self, i, b, e):
        L_ = e - b
        self.place_boat(b, BOAT_X, z=0.0)
        self.boat_key(b + 6, x=BOAT_X)
        self.boat_key(e, x=BOAT_X + 11.0)                                       # cruising across the lake
        self.aboard(b, local=self.STERN_LOCAL, face_deg=0)
        self.mb.wave(b + 10, e, hand="R")
        self.mb.smile(b + 4, big=True)
        for k, kid in enumerate(self.kids):
            toy.hide_tree(kid.root, b, False)
            kid.cut_place(b, V((0.95 + 0.62 * k, 0.12 - 0.12 * k, HF)), 0)
            kid.pose(b + 4)
            kid.cheer(b + 8 + 4 * k, e)
            kid.smile(b + 6, big=True)
            kid.auto_blink(b, e + 400, seed=k + 3)
        jump = b + int(L_ * 0.55)                                               # a fish jumps
        fj = self._fish("fish_jump", "#FF8C1A")
        fj.location = AWAY
        bx = BOAT_X + 11.0 * 0.55
        _key(fj, jump - 1, location=AWAY)
        _key(fj, jump, location=V((bx + 3.0, -0.3, -0.3)))
        _key(fj, jump + 8, location=V((bx + 3.6, -0.3, 0.9)), rotation_euler=V((0, R(-40), 0)))
        _key(fj, jump + 16, location=V((bx + 4.2, -0.3, -0.3)), rotation_euler=V((0, R(40), 0)))
        _key(fj, jump + 17, location=AWAY)
        for f in (jump - 1, jump + 16):
            toy.set_interpolation(fj, "location", (f,), "CONSTANT")
        events.add(jump, "splash", gain=0.3)
        events.add(jump + 16, "splash", gain=0.3)
        events.add(b, "boat_motor", duration=e - b, gain=0.7)
        events.add(b + 10, "kids_cheer")
        _key(self.ship, b - 1, location=AWAY)
        _key(self.ship, b, location=V((BOAT_X + 30.0, 24.0, 0.0)))
        _key(self.ship, e, location=V((BOAT_X + 13.0, 24.0, 0.0)))
        toy.set_interpolation(self.ship, "location", (b - 1,), "CONSTANT")
        toy.set_interpolation(self.ship, "location", (b,), "LINEAR")
        horn = b + int(L_ * 0.4)
        events.add(horn, "ship_horn")
        self.mb.turn(horn + 4, -15, frames=8)                                   # turns to look (stays on deck)
        self.mb.wave(horn + 12, e, hand="R")
        lbl = label("200,000 TONNES OF STEEL", (0, 0, 0), horn - 6, e, size=1.3, tilt=-3)
        lbl.parent = self.ship
        lbl.location = (2.0, -3.9, 2.2)                                           # on the hull, below the end card
        self.rig.shot(b, horn - 8, cam_from=(BOAT_X - 0.6, -5.6, 0.9), cam_to=(BOAT_X + 4.0, -6.4, 1.3),
                      aim_from=(BOAT_X - 0.4, 0.6, 0.3), aim_to=(BOAT_X + 4.6, 0.6, 0.6), lens=22, fstop=8.0, cut=True)
        self.rig.shot(horn - 7, e, cam_from=(BOAT_X + 4.6, -9.6, 1.6), cam_to=(BOAT_X + 10.0, -12.0, 2.4),
                      aim_from=(BOAT_X + 7.0, 6.0, 3.0), aim_to=(BOAT_X + 11.5, 6.0, 3.6), lens=22, fstop=11.0, blend=24)

    # ------------------- hooks (epilogue) -------------------

    def _clear_for_hook(self, h0):
        for obj in (self.ship, self.duck):
            toy.key_hold(obj, "location", h0 - 1)
            toy.set_interpolation(obj, "location", (h0 - 1,), "CONSTANT")
            _key(obj, h0, location=AWAY)

    def a_sink_hook(self, i, h0, h1):
        L_ = h1 - h0
        self._clear_for_hook(h0)
        _key(self.root, h0, location=AWAY)
        toy.set_interpolation(self.root, "location", (h0,), "CONSTANT")
        for kid in self.kids:
            toy.hide_tree(kid.root, h0, True)
        start = V((LAKE_X0 + 5.0, 0.85, -0.12))
        end = V((LAKE_X0 + 5.0, 0.85, -1.75))
        _key(self.slab, h0 - 1, location=AWAY)
        _key(self.slab, h0, location=start, rotation_euler=V((0, 0, 0)))
        _key(self.slab, h1, location=end)
        toy.set_interpolation(self.slab, "location", (h0 - 1,), "CONSTANT")
        stand = start + V((0.2, -0.25, 0.16))
        self.at(h0, stand, stand + V((0, -6, 0)))
        self.max.move(h0 + 1, h1, end + V((0.2, -0.25, 0.16)))                   # rides it down
        self.max.pose(h0 + 4, shoulderL=(-90, 0, 20))                            # proud thumbs up...
        self.max.smile(h0 + 4, big=True)
        self.max.pose(h0 + int(L_ * 0.5), shoulderL=(-90, 0, 20))
        self.max.brows(h0 + int(L_ * 0.55), 1.0)
        self.max.key("mouth", h0 + int(L_ * 0.6), scale=(0.7, 0.6, 0.5))
        self.max.blink([h0 + int(L_ * 0.7), h0 + int(L_ * 0.85)])
        rnd = random.Random(9)
        self.bubbles(h0 + 4, h1, "hook_bubbles", lambda f: V(toy.value_at(self.slab, "location", f)) +
                     V((rnd.uniform(-1.1, 1.1), -0.62, 0.25)), rate=1)
        events.add(h0, "bubbles", duration=L_)
        events.add(h0 + int(L_ * 0.4), "boing", gain=0.3)
        self.rig.shot(h0, h1, cam_from=(LAKE_X0 + 5.2, -4.8, 0.3), cam_to=(LAKE_X0 + 5.2, -4.4, -0.1),
                      aim_from=(LAKE_X0 + 5.1, 0.8, 0.2), aim_to=(LAKE_X0 + 5.1, 0.8, -0.3), lens=24, fstop=8.0, cut=True)

    def a_cruise_hook(self, i, h0, h1):
        self._clear_for_hook(h0)
        self.place_boat(h0, BOAT_X + 3, z=0.0)
        self.boat_key(h1, x=BOAT_X + 8)
        self.aboard(h0, local=self.STERN_LOCAL, face_deg=0)
        self.mb.wave(h0 + 4, h1, hand="R")
        for k, kid in enumerate(self.kids):
            toy.hide_tree(kid.root, h0, False)
            kid.cut_place(h0, V((0.95 + 0.62 * k, 0.12 - 0.12 * k, HF)), 0)
            kid.cheer(h0 + 4, h1)
        events.add(h0, "boat_motor", duration=h1 - h0, gain=0.7)
        events.add(h0 + 6, "kids_cheer")
        self.rig.shot(h0, h1, cam_from=(BOAT_X + 3.3, -6.2, 1.0), cam_to=(BOAT_X + 8.0, -5.9, 1.1),
                      aim_from=(BOAT_X + 3.2, 0.6, 0.2), aim_to=(BOAT_X + 8.0, 0.6, 0.2), lens=22, fstop=8.0, cut=True)
