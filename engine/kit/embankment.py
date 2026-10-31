"""
EMBANKMENT world (the kit's first world): stages ANY valid storyboard (agents/storyboard.py) in a cutaway
riverbank: river on the left, Max's barrier in the middle, the yard on the right, a buried sand layer
under it all. Every change and event of engine/kit/vocab.py is implemented once here; positions and
framing come from engine/kit/geometry.py. A generated set is just:

    class SomeStorySet(EmbankmentSet):
        STORYBOARD = {...}

Beat template (every step): SETUP (first 40%, close on Max building or reacting) -> hard cut ->
MECHANISM (the event, framed by studio.frame_all around the event's focus, its label and Max) with the
result and Max's reaction inside the same shot. A change is still happening at the beat's middle and
finished by 7/8, where the reviewer looks.

A storyboard with "hero": false (a no-hero explainer, agents/explainer.py) films the same world and
events with no Max: the setup shot frames the part being built (geometry.build_focus) as it builds
itself, and the mechanism shots frame only what the event shows.
"""
import math
import random

import bpy
from mathutils import Vector

from engine import events, studio as st, textures as tx, toy
from engine.camera import CameraRig
from engine.character import Character
from engine.framing import solve, tan_half
from engine.kit import geometry as g
from engine.kit import vocab
from engine.sets.plane_story import label as make_label

V = Vector
SETUP = 0.40                         # share of a beat spent on the setup shot (Max big: the hero gate)
RESULT = 0.66                        # share of the mechanism after which the closer result shot starts
PUSH = 1.05                          # a shot starts this much farther than its solved framing, then pushes in
LABEL_SHARE, CAP_HEIGHT = 0.034, 0.7  # label letters: share of the frame height (QA needs >= 1.8%); cap / size
RISE, LENS, MARGIN = 0.2, 28.0, 0.1   # mechanism shots: a little from above, so the surfaces read too
Y1 = 30.0                            # depth of the world behind the cut face
MAX_LOOK = {"hat": "#FF7A00", "shirt": "#E8492F", "shoes": "#F2C230", "iris": "#7A4A1C"}
KID_LOOKS = ({"hat": None, "mustache": False, "shirt": "#FF5D8F", "overalls": "#3A7BD5", "shoes": "#F2C230",
              "hair": "#5B3A1E", "scale": 0.6, "ponytail": True},
             {"hat": None, "mustache": False, "shirt": "#3DBE6E", "overalls": "#F2A93B", "shoes": "#3A7BD5",
              "hair": "#2B1A10", "scale": 0.56})
WEATHER = {"sunny": (40, 0.22, 4.2), "rain": (16, 0.15, 2.4), "storm": (9, 0.11, 1.6)}   # sky elev, sky, sun


# ------------------- keyframe channels (instant switches at cuts, eased moves inside a shot) -------------

class Chan:
    """One animated value. set(f, v): it becomes v AT frame f (holds the old value until then). move(a, b, v):
    eases from its current value at a to v at b. Keys are written in time order per channel."""

    def __init__(self, owner, target, path, index=-1, value=0.0):
        self.owner, self.target, self.path, self.index = owner, target, path, index
        self.full = path if target is owner else target.path_from_id(path)
        self.last, self.value = None, value

    def _write(self, f, v):
        if self.index >= 0:
            getattr(self.target, self.path)[self.index] = v
            self.target.keyframe_insert(self.path, index=self.index, frame=f)
        else:
            setattr(self.target, self.path, v)
            self.target.keyframe_insert(self.path, frame=f)
        self.value = v

    def _constant(self, f):
        for fc in toy.fcurves(self.owner):
            if fc.data_path == self.full and (self.index < 0 or fc.array_index == self.index):
                for kp in fc.keyframe_points:
                    if int(round(kp.co.x)) == f:
                        toy.set_key_interpolation(self.owner, fc, kp, "CONSTANT")

    def set(self, f, v):
        if self.last is not None and f <= self.last:
            return
        if self.last is not None:
            self._constant(self.last)
            if f - 1 > self.last:
                self._write(f - 1, self.value)
                self._constant(f - 1)
        self._write(f, v)
        self._constant(f)
        self.last = f

    def move(self, a, b, v):
        if self.last is None or a > self.last:
            self.set(a, self.value)
        self._write(b, v)                 # the a..b segment stays eased (Bezier)
        self._constant(b)
        self.last = b


def _vec_chans(obj, path, value):
    return [Chan(obj, obj, path, i, value[i]) for i in range(3)]


# ------------------- materials -------------------

def _noise(name, a, b, scale=7.0, rough=0.85, bump=0.25):
    """Two-tone noise in OBJECT space (metres): the default box-normalized mapping smeared the texture into
    stripes along the 30 m-long prisms. scale is per metre here, so keep it modest."""
    mat = toy.noise_material(name, toy.srgb(a), toy.srgb(b), scale=scale, roughness=rough, bump=bump)
    nt = mat.node_tree
    tex = next(n for n in nt.nodes if n.type == "TEX_NOISE")
    if not tex.inputs["Vector"].is_linked:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        nt.links.new(tc.outputs["Object"], tex.inputs["Vector"])
        tex.inputs["Scale"].default_value = scale * 0.35
    return mat


def _glow(name, hexc, strength=2.5):
    return st.glow_mat(name, hexc, strength)


def _mixer(nt, fac, a, b):
    m = nt.nodes.new("ShaderNodeMix")
    m.data_type = "RGBA"
    if isinstance(fac, float):
        m.inputs["Factor"].default_value = fac
    else:
        nt.links.new(fac, m.inputs["Factor"])
    for sock, val in ((m.inputs[6], a), (m.inputs[7], b)):
        if isinstance(val, tuple):
            sock.default_value = (*val, 1)
        else:
            nt.links.new(val, sock)
    return m.outputs[2]


def _value(nt, name, v=0.0):
    n = nt.nodes.new("ShaderNodeValue")
    n.name = n.label = name
    n.outputs[0].default_value = v
    return n


class _Absent:
    """Max in a no-hero explainer: every gesture the staging asks of him does nothing."""

    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


def soil_material(name, surface):
    """The barrier's soil, driven by keyable values: fill (0 sand -> 1 packed earth), wet (darker), cover
    (grass; surface only). Returns (material, {value name: node})."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 11.0
    noise.inputs["Detail"].default_value = 8.0
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    fac = noise.outputs["Fac"]
    vals = {k: _value(nt, k) for k in (("fill", "wet", "cover") if surface else ("fill", "wet"))}
    sand = _mixer(nt, fac, toy.srgb("#E2C48C"), toy.srgb("#B98F55"))
    earth = _mixer(nt, fac, toy.srgb("#94704A"), toy.srgb("#5E4128"))
    col = _mixer(nt, vals["fill"].outputs[0], sand, earth)
    col = _mixer(nt, vals["wet"].outputs[0], col, toy.srgb("#4A3420"))
    if surface:
        grass = _mixer(nt, fac, toy.srgb("#6DB34A"), toy.srgb("#3F7F2C"))
        col = _mixer(nt, vals["cover"].outputs[0], col, grass)
    nt.links.new(col, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.9
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    nt.links.new(fac, bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat, vals


def ground_section_material(name="kb_section"):
    """The cut face of the ground: topsoil, the buried sand layer, bedrock (by height), textured."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 9.0
    noise.inputs["Detail"].default_value = 7.0
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    fac = noise.outputs["Fac"]

    def above(z):
        m = nt.nodes.new("ShaderNodeMath")
        m.operation = "GREATER_THAN"
        nt.links.new(sep.outputs["Z"], m.inputs[0])
        m.inputs[1].default_value = z
        return m.outputs[0]
    rock = _mixer(nt, fac, toy.srgb("#8C857C"), toy.srgb("#5F5A54"))
    sand = _mixer(nt, fac, toy.srgb("#E0C083"), toy.srgb("#C29A5E"))
    top = _mixer(nt, fac, toy.srgb("#6E4B2E"), toy.srgb("#4C321D"))
    col = _mixer(nt, above(g.SAND_BOTTOM), rock, sand)
    col = _mixer(nt, above(g.TOPSOIL), col, top)
    nt.links.new(col, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.92
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.3
    nt.links.new(fac, bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


# ------------------- geometry helpers -------------------

def cut_polygon(name, outline_xz, y, mat, origin=None):
    """A flat polygon drawn ON the cut face at depth y (a layer: wet soil, a tunnel, a patch...). With
    `origin` (x, z) the object's origin sits there, so scaling it grows the layer around that point."""
    ox, oz = origin or (0.0, 0.0)
    ob = st.mesh_obj(name, [(x - ox, y, z - oz) for x, z in outline_xz], [tuple(range(len(outline_xz)))], (mat,),
                     smooth=False)
    ob.location = (ox, 0.0, oz)
    st.no_shadow(ob)
    return ob


def band(path_xz, w0, w1):
    """A closed outline around a polyline (width w0 at its start, w1 at its end)."""
    left, right = [], []
    n = len(path_xz)
    for k, (x, z) in enumerate(path_xz):
        a = path_xz[max(0, k - 1)]
        b = path_xz[min(n - 1, k + 1)]
        dx, dz = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dz) or 1.0
        nx, nz = -dz / ln, dx / ln
        w = (w0 + (w1 - w0) * k / max(1, n - 1)) / 2
        left.append((x + nx * w, z + nz * w))
        right.append((x - nx * w, z - nz * w))
    return left + right[::-1]


def morph_prism(name, shapes, y0, y1, mats):
    """A prism whose x-z outline morphs between named shapes (same vertex count) via shape keys.
    Faces: the two ends use mats[0] (the cut section), the sides mats[1] (the outer surface)."""
    names = list(shapes)
    sink = lambda z: z if z > 1e-6 else -0.03             # noqa: E731  bottom 3 cm into the ground: no shared plane
    shapes = {k: [(x, sink(z)) for x, z in v] for k, v in shapes.items()}
    base = shapes[names[0]]
    n = len(base)
    verts = [(x, y0, z) for x, z in base] + [(x, y1, z) for x, z in base]
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    faces += [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
    mi = [0, 0] + [1] * n
    ob = st.mesh_obj(name, verts, faces, mats, smooth=False, mat_index=mi)
    ob.shape_key_add(name="basis")
    keys = {}
    for nm in names:
        kb = ob.shape_key_add(name=nm)
        for k, (x, z) in enumerate(shapes[nm]):
            kb.data[k].co = (x, y0, z)
            kb.data[n + k].co = (x, y1, z)
        kb.value = 0.0
        keys[nm] = Chan(ob.data.shape_keys, kb, "value", value=0.0)
    return ob, keys


def chevrons(name, path_xz, y, n=5, period=36, color="#3FD0FF"):
    """Flow arrows: n glowing arrowheads gliding along a path on the cut face, looping (a FOLLOW_PATH
    constraint with a cyclic offset, so it costs two keys per arrow). Returns the root empty."""
    root = toy.empty(name, (0, 0, 0))
    cu = bpy.data.curves.new(f"{name}_path", "CURVE")
    cu.dimensions = "3D"
    sp = cu.splines.new("POLY")
    sp.points.add(len(path_xz) - 1)
    for k, (x, z) in enumerate(path_xz):
        sp.points[k].co = (x, y, z, 1.0)
    cu.use_path = True
    cu.path_duration = 100
    path = bpy.data.objects.new(f"{name}_path", cu)
    bpy.context.scene.collection.objects.link(path)
    path.parent = root
    mat = _glow(f"{name}_glow", color, 3.0)
    for k in range(n):
        bpy.ops.mesh.primitive_cone_add(radius1=0.085, depth=0.24, vertices=12, location=(0, 0, 0))
        c = bpy.context.active_object
        c.name = f"{name}_{k}"
        c.data.materials.append(mat)
        c.rotation_euler = (0, math.radians(90), 0)          # the cone points along the path (+X)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        con = c.constraints.new("FOLLOW_PATH")
        con.target = path
        con.use_curve_follow = True
        con.use_fixed_location = True
        con.forward_axis = "FORWARD_X"
        path_key = f'constraints["{con.name}"].offset_factor'
        con.offset_factor = 0.0
        c.keyframe_insert(path_key, frame=1 + k * period // n)
        con.offset_factor = 1.0
        c.keyframe_insert(path_key, frame=1 + k * period // n + period)
        for fc in toy.fcurves(c):
            if fc.data_path == path_key:
                for kp in fc.keyframe_points:
                    toy.set_key_interpolation(c, fc, kp, "LINEAR")
                fc.modifiers.new("CYCLES")
        c.parent = root
        st.no_shadow(c)
    toy.hide_tree(root, 1, True)
    return root


def duck_model():
    yel = tx.paint("kb_duck_yellow", "#FFD21F")
    ora = toy.material("kb_duck_beak", toy.srgb("#FF8A1A"), roughness=0.4)
    eye = toy.material("kb_duck_eye", toy.srgb("#141414"), roughness=0.2)
    root = toy.empty("kb_duck", (0, 0, 0))
    toy.sphere("kb_duck_body", 0.2, (0, 0, 0.1), scale=(1.25, 0.95, 0.72), mat=yel, parent=root)
    toy.sphere("kb_duck_head", 0.12, (0.14, 0, 0.29), mat=yel, parent=root)
    toy.sphere("kb_duck_beak", 0.06, (0.27, 0, 0.27), scale=(1.4, 1.0, 0.45), mat=ora, parent=root)
    for s in (-1, 1):
        toy.sphere(f"kb_duck_eye{s}", 0.022, (0.21, 0.07 * s, 0.33), mat=eye, parent=root)
    toy.sphere("kb_duck_tail", 0.07, (-0.24, 0, 0.2), scale=(1, 1, 0.7), mat=yel, parent=root)
    return root


def squirrel_model():
    fur = _noise("kb_squirrel_fur", "#9A5B2C", "#6B3B19", scale=30, bump=0.15)
    belly = toy.material("kb_squirrel_belly", toy.srgb("#E8C9A0"), roughness=0.8)
    eye = toy.material("kb_squirrel_eye", toy.srgb("#141414"), roughness=0.2)
    root = toy.empty("kb_squirrel", (0, 0, 0))
    toy.sphere("kb_squirrel_body", 0.13, (0, 0, 0.16), scale=(1.1, 0.9, 1.25), mat=fur, parent=root)
    toy.sphere("kb_squirrel_belly", 0.09, (0.06, -0.06, 0.15), scale=(0.8, 0.5, 1.1), mat=belly, parent=root)
    toy.sphere("kb_squirrel_head", 0.09, (0.07, 0, 0.36), mat=fur, parent=root)
    for s in (-1, 1):
        toy.sphere(f"kb_squirrel_ear{s}", 0.035, (0.05, 0.05 * s, 0.46), scale=(0.6, 0.6, 1.3), mat=fur, parent=root)
        toy.sphere(f"kb_squirrel_eye{s}", 0.018, (0.14, 0.04 * s, 0.39), mat=eye, parent=root)
    toy.sphere("kb_squirrel_tail", 0.11, (-0.17, 0, 0.3), scale=(0.7, 0.6, 1.8), mat=fur, parent=root)
    return root


def rock_material():
    return _noise("kb_rock", "#A39E96", "#6A665F", scale=6, bump=0.6)


# ------------------- the set -------------------

class EmbankmentSet:
    STORYBOARD = None                # a validated storyboard (agents/storyboard.py)
    QA_ALLOW = None                  # kit geometry is designed to touch (props on the ground): no object check

    def __init__(self, scene, sun, fill, bg, total):
        self.scene, self.sun, self.fill, self.bg, self.total = scene, sun, fill, bg, total
        self.sb = self.STORYBOARD
        self.hero = self.sb.get("hero", True) is not False
        self.rig = CameraRig()
        self.rnd = random.Random(7)
        self._ground()
        self._river()
        self._barrier()
        self._components()
        self._effects()
        self._yard()
        self._people()
        self._weather_rig()
        self.state = self._initial()
        self._apply(self.state, 1)

    # ---- the world ----
    def _ground(self):
        def height(x, y):
            if x >= g.BANK:
                return 0.0
            if x >= g.BANK - 1.0:
                return g.BED * (g.BANK - x) / 1.0
            return g.BED
        self.ground = st.terrain("kb_ground", -24.0, 26.0, 0.0, Y1, height, floor=-80.0, res=0.25,
                                 top=_noise("kb_grass", "#6DB34A", "#3F7F2C", scale=14, bump=0.3),
                                 side=ground_section_material(), edge=0)
        st.world_floor(0.0, around=(-24.0, 26.0, Y1))

    def _river(self):
        self.river = st.Reservoir("kb_river", -24.0, -0.05, 0.02, Y1, bottom=g.BED, level=g.level("low", "flat"))
        self.level = Chan(self.river.surf, self.river.surf, "location", 2, self.river.surf.location.z)
        self.level_vz = Chan(self.river.vol, self.river.vol, "location", 2, self.river.vol.location.z)
        self.level_vs = Chan(self.river.vol, self.river.vol, "scale", 2, self.river.vol.scale.z)
        self.cur_level = g.level("low", "flat")

    def _key_level(self, f0, f1, z, instant=False):
        top = max(g.BED + 0.002, z - 0.06)
        for ch, v in ((self.level, z), (self.level_vz, (top + g.BED) / 2), (self.level_vs, max(0.002, top - g.BED))):
            (ch.set(f0, v) if instant else ch.move(f0, f1, v))
        self.cur_level = z

    def _barrier(self):
        self.sec_mat, self.sec_vals = soil_material("kb_barrier_section", surface=False)
        self.surf_mat, self.surf_vals = soil_material("kb_barrier_surface", surface=True)
        shapes = {n: g.profile(n) for n in g.PROFILES}
        self.barrier, self.shape = morph_prism("kb_barrier", shapes, 0.0, Y1, (self.sec_mat, self.surf_mat))
        self.mat_ch = {f"sec_{k}": Chan(self.sec_mat.node_tree, n.outputs[0], "default_value", value=0.0)
                       for k, n in self.sec_vals.items()}
        self.mat_ch.update({f"surf_{k}": Chan(self.surf_mat.node_tree, n.outputs[0], "default_value", value=0.0)
                            for k, n in self.surf_vals.items()})
        # the yard-side half drawn darker while it is soaked (a layer on the cut face)
        wet = _noise("kb_wet_soil", "#7A5A36", "#5A3F24", scale=12)
        self.wet_layer, self.wet_shape = morph_prism("kb_wet", {
            "steep": _yard_half(g.profile("steep")), "slumped": _yard_half(g.profile("slumped"))},
            g.DECAL_Y[1], g.DECAL_Y[1] + 0.003, (wet, wet))
        st.no_shadow(self.wet_layer)

    def _components(self):
        clay = _noise("kb_clay", "#7B5E52", "#5A4038", scale=9)
        self.core = st.prism("kb_core", g.core_outline(), g.DECAL_Y[0], Y1 - 0.5, clay)
        earth = _noise("kb_berm_soil", "#8F6B45", "#5E4128", scale=10)
        self.berm = st.prism("kb_berm", g.berm_outline(), g.DECAL_Y[0], Y1 - 0.5, earth)
        steel = tx.metal("kb_steel", "#9AA3AD")
        self.wells = toy.empty("kb_wells", (0, 0, 0))
        for k, x in enumerate(g.WELLS_X):
            toy.cylinder(f"kb_well_{k}", 0.13, 1.3, (x, 0.32, -0.25), mat=steel, parent=self.wells)
            toy.cylinder(f"kb_well_cap_{k}", 0.17, 0.08, (x, 0.32, 0.42), mat=steel, parent=self.wells)
            cut_polygon(f"kb_well_section_{k}", [(x - 0.07, g.SAND_MID), (x + 0.07, g.SAND_MID),
                                                 (x + 0.07, 0.0), (x - 0.07, 0.0)], g.DECAL_Y[2], steel).parent = self.wells
        ditch = _noise("kb_ditch_water", "#3E8FC4", "#2C6E9C", scale=10, rough=0.15, bump=0.05)
        toy.box("kb_well_ditch", (1.6, 3.0, 0.03), (g.WELLS_X[1] + 1.1, 1.6, 0.02), mat=ditch, parent=self.wells)
        rock = rock_material()
        self.riprap = toy.empty("kb_riprap", (0, 0, 0))
        prof = g.profile("raised")
        rnd = random.Random(3)
        for row in range(7):
            for k in range(6):
                t = (k + 0.5 * (row % 2) + 0.3) / 6.4
                x = prof[0][0] + (prof[5][0] - prof[0][0]) * t * 0.92
                z = prof[5][1] * t * 0.92
                y = 0.25 + row * 0.55 + rnd.uniform(-0.1, 0.1)
                r = rnd.uniform(0.13, 0.19)
                toy.sphere(f"kb_riprap_{row}_{k}", r, (x - 0.05, y, z + 0.04), scale=(1.2, 1.0, 0.7), mat=rock,
                           parent=self.riprap, subdiv=1)
        self.marker = toy.empty("kb_marker", (0, 0, 0))
        red = _glow("kb_marker_red", "#FF4B3A", 2.2)
        fl, cr = g.level("flood", "raised"), g.crest_height("raised")
        xm = g.profile("raised")[5][0] - 0.35
        toy.box("kb_marker_floodline", (2.6, 0.03, 0.035), (xm - 1.0, -0.06, fl), mat=red, parent=self.marker, bevel=0)
        yel = _glow("kb_marker_yellow", "#FFD23F", 2.2)
        toy.box("kb_marker_bar", (0.05, 0.03, cr - fl), (xm, -0.06, (cr + fl) / 2), mat=yel, parent=self.marker, bevel=0)
        for z, rot in ((cr, 0), (fl, 180)):
            bpy.ops.mesh.primitive_cone_add(radius1=0.09, depth=0.16, vertices=12, location=(xm, -0.06, z - 0.08 if
                                                                                              rot == 0 else z + 0.08))
            c = bpy.context.active_object
            c.name = f"kb_marker_tip_{rot}"
            c.rotation_euler = (math.radians(rot), 0, 0)
            c.data.materials.append(yel)
            c.parent = self.marker
        tunnel_mat = _noise("kb_tunnel_dark", "#2B1C12", "#1A110A", scale=14)
        a, b = g.tunnel_ends("raised")
        self.tunnel = cut_polygon("kb_tunnel", band([(a, g.TUNNEL_Z), (b, g.TUNNEL_Z)], 0.16, 0.24),
                                  g.DECAL_Y[2], tunnel_mat, origin=((a + b) / 2, g.TUNNEL_Z))
        self.tunnel_scale = _vec_chans(self.tunnel, "scale", (1, 1, 1))
        patch_mat = _noise("kb_patch_soil", "#C49A62", "#9C7444", scale=14)
        self.patch = cut_polygon("kb_patch", band([(b - 0.9, g.TUNNEL_Z), (b + 0.02, g.TUNNEL_Z)], 0.36, 0.42),
                                 g.DECAL_Y[3], patch_mat)
        wood = _noise("kb_nestbox_wood", "#A8743F", "#7A5028", scale=18)
        nx, ny = g.NESTBOX
        self.nestbox = toy.empty("kb_nestbox", (nx, ny, g.berm_top(nx)))
        toy.cylinder("kb_nestbox_post", 0.05, 1.2, (0, 0, 0.6), mat=wood, parent=self.nestbox)
        toy.box("kb_nestbox_box", (0.42, 0.36, 0.42), (0, 0, 1.38), mat=wood, parent=self.nestbox)
        toy.box("kb_nestbox_roof", (0.52, 0.46, 0.06), (0, 0, 1.63), mat=wood, parent=self.nestbox)
        self.gouge = cut_polygon("kb_gouge", band(_gouge_path(), 0.12, 0.12), g.DECAL_Y[1],
                                 _noise("kb_gouge_soil", "#4A2F1E", "#2F1D12", scale=16))
        for o in (self.core, self.berm, self.wells, self.riprap, self.marker, self.tunnel, self.patch, self.nestbox,
                  self.gouge):
            toy.hide_tree(o, 1, True)
        self.grow = {o.name: Chan(o, o, "scale", 2, 1.0) for o in (self.core, self.berm)}

    def _effects(self):
        y = -0.1
        self.flows = {
            "seep": [chevrons(f"kb_flow_seep{k}", p, y) for k, p in enumerate(g.seep_paths("steep"))],
            "seep_wide": [chevrons(f"kb_flow_seepw{k}", p, y) for k, p in enumerate(g.seep_paths("wide"))],
            "blocked": [chevrons(f"kb_flow_block{k}", p, y, n=3, period=30) for k, p in
                        enumerate(g.seep_paths("wide", stop_at_core=True))],
            "under": [chevrons("kb_flow_under", g.underseep_path(), y, n=7, period=60)],
            "relief": [chevrons("kb_flow_relief", [(g.BANK - 0.5, g.SAND_MID), (g.WELLS_X[0], g.SAND_MID),
                                                   (g.WELLS_X[0], 0.3)], y, n=6, period=60)],
            "tunnel": [chevrons("kb_flow_tunnel", [(g.tunnel_ends("raised")[0] - 0.3, g.TUNNEL_Z),
                                                   (g.tunnel_ends("raised")[1] + 0.2, g.TUNNEL_Z)], y, n=4, period=24)],
            "press": [chevrons(f"kb_flow_press{k}", [(g.face_x("raised", z, -1) - 1.6, z),
                                                     (g.face_x("raised", z, -1) - 0.15, z)], y, n=3, period=30)
                      for k, z in enumerate((0.35, 0.8, 1.2))],
        }
        mud = toy.material("kb_mud_water", toy.srgb("#8A6A45"), roughness=0.25, transmission=0.3)
        self.boil = toy.empty("kb_boil", (g.BOIL_X, 0.35, 0.0))
        toy.cylinder("kb_boil_ring", 0.42, 0.08, (0, 0, 0.04), mat=_noise("kb_boil_mud", "#5A3E25", "#3A2715", scale=20),
                     parent=self.boil)
        bpy.ops.mesh.primitive_cone_add(radius1=0.24, radius2=0.06, depth=0.7, vertices=20, location=(0, 0, 0.35))
        cone = bpy.context.active_object
        cone.name = "kb_boil_jet"
        cone.data.materials.append(mud)
        cone.parent = self.boil
        self.boil_jet = cone
        self.bags = toy.empty("kb_bags", (g.BOIL_X, 0.35, 0.0))
        bag = _noise("kb_bag_burlap", "#C9B07A", "#A08750", scale=40, bump=0.4)
        for k in range(8):
            a = 2 * math.pi * k / 8
            b = toy.capsule(f"kb_bag_{k}", 0.11, 0.32, (0.62 * math.cos(a), 0.62 * math.sin(a), 0.1),
                            rotation=(math.radians(90), 0, a + math.pi / 2), mat=bag, parent=self.bags)
            b.scale = (1.0, 1.0, 0.75)
        # the overtopping sheet: a thin skin of fast water over the crest and down the yard slope
        sheet_pts = g.sheet_path("wide")
        skin = band(sheet_pts, 0.1, 0.16)
        water = toy.material("kb_sheet_water", toy.srgb("#4FB2E8"), roughness=0.08, transmission=0.2)
        self.sheet = st.prism("kb_sheet", [(x, z + 0.05) for x, z in skin], -0.03, Y1 - 0.5, water)
        st.no_shadow(self.sheet)
        # the burrow's jet: a muddy tube arcing out of the yard face
        arc = g.jet_arc("raised")
        cu = bpy.data.curves.new("kb_jet_curve", "CURVE")
        cu.dimensions = "3D"
        sp = cu.splines.new("BEZIER")
        sp.bezier_points.add(len(arc) - 1)
        for k, (x, z) in enumerate(arc):
            bp = sp.bezier_points[k]
            bp.co = (x, -0.12, z)
            bp.handle_left_type = bp.handle_right_type = "AUTO"
        cu.bevel_depth = 0.11
        cu.bevel_resolution = 4
        self.jet = bpy.data.objects.new("kb_jet", cu)
        bpy.context.scene.collection.objects.link(self.jet)
        self.jet.data.materials.append(_noise("kb_jet_mud", "#A8865C", "#7A5A38", scale=12, rough=0.2, bump=0.1))
        self.splash = toy.empty("kb_splash", (arc[-1][0], -0.1, 0.05))
        foam = toy.material("kb_foam", toy.srgb("#EAF3F7"), roughness=0.3)
        for k in range(6):
            a = 2 * math.pi * k / 6
            toy.sphere(f"kb_splash_{k}", 0.09, (0.22 * math.cos(a), 0.1 * math.sin(a), 0.06 + 0.04 * (k % 2)),
                       mat=foam, parent=self.splash)
        for o in (self.boil, self.bags, self.sheet, self.jet, self.splash):
            toy.hide_tree(o, 1, True)

    def _yard(self):
        st.House("kb_house", (g.HOUSE[0], g.HOUSE[1], 0.0))
        tx_, ty, tr = g.TRAMPOLINE
        self.trampoline = toy.empty("kb_trampoline", (tx_, ty, 0))
        black = tx.rubber("kb_tramp_mat", "#1E1E22")
        blue = tx.paint("kb_tramp_pad", "#2F7FD8")
        toy.cylinder("kb_tramp_bed", tr * 0.9, 0.03, (0, 0, 0.62), mat=black, parent=self.trampoline, vertices=32)
        bpy.ops.mesh.primitive_torus_add(major_radius=tr, minor_radius=0.07, location=(tx_, ty, 0.64))
        rim = bpy.context.active_object
        rim.name = "kb_tramp_rim"
        rim.data.materials.append(blue)
        rim.parent = self.trampoline
        rim.location = (0, 0, 0.64)
        for k in range(4):
            a = 2 * math.pi * k / 4 + 0.4
            toy.cylinder(f"kb_tramp_leg_{k}", 0.03, 0.64, (tr * 0.92 * math.cos(a), tr * 0.92 * math.sin(a), 0.32),
                         mat=black, parent=self.trampoline)
        sand = _noise("kb_sandpile", "#E2C48C", "#B98F55", scale=12)
        px, py = g.SAND_PILE
        self.pile = toy.sphere("kb_sandpile", 0.55, (px, py, 0.0), scale=(1.3, 1.0, 0.75), mat=sand)
        self.pile_z = Chan(self.pile, self.pile, "location", 2, 0.0)     # used up: it sinks into the ground
        self.duck = duck_model()
        self.duck_loc = _vec_chans(self.duck, "location", (0, 0, 0))
        # Shared end-of-failure payoff: regardless of the mechanism, the lawn is visibly underwater and
        # the duck sails into it. This lives in the kit, so a planner cannot accidentally omit the disaster.
        flood = toy.material("kb_fail_flood_water", toy.srgb("#49AEE8"), roughness=0.08, transmission=0.25,
                             alpha=0.78)
        self.fail_flood = toy.box("kb_fail_flood", (7.2, 4.2, 0.055), (4.2, 2.1, 0.045), mat=flood, bevel=0.02)
        st.no_shadow(self.fail_flood)
        toy.hide_tree(self.fail_flood, 1, True)
        self.squirrel = squirrel_model()
        self.squirrel_loc = _vec_chans(self.squirrel, "location", (0, 0, 0))
        toy.hide_tree(self.squirrel, 1, True)

    def _people(self):
        if self.hero:
            wood = toy.material("kb_shovel_wood", toy.srgb("#A8743F"), roughness=0.6)
            steel = toy.material("kb_shovel_steel", toy.srgb("#8E979F"), roughness=0.3, metallic=0.8)
            self.shovel = toy.empty("kb_shovel", (0, 0, 0))
            toy.cylinder("kb_shovel_handle", 0.022, 1.0, (0, 0, 0), mat=wood, parent=self.shovel)
            toy.box("kb_shovel_blade", (0.2, 0.03, 0.26), (0, 0, -0.6), mat=steel, parent=self.shovel)
            self.max = Character("Max", MAX_LOOK)
            self.max.place(1, (0, 0, 0), 0)
            self.max.key("hips", 1, loc=(0, 0, 0.56))
            self.max.auto_blink(1, self.total + 600, seed=11)
            self.max.hold(self.shovel, "R")
            self.shovel.location = (0, -0.04, 0.28)
            # Blue drops are parented to Max, so they remain wrapped around him at every event location.
            wet = toy.material("kb_drench_water", toy.srgb("#8AD8FF"), roughness=0.05, transmission=0.3,
                               alpha=0.9)
            self.drench = toy.empty("kb_drench", (0, 0, 0), self.max.root)
            for k, (x, y, z) in enumerate(((-0.35, -0.08, 1.65), (0.34, -0.1, 1.55), (-0.28, -0.16, 1.15),
                                            (0.3, -0.17, 1.02), (-0.18, -0.2, 0.72), (0.16, -0.2, 0.62))):
                toy.sphere(f"kb_drench_drop_{k}", 0.075, (x, y, z), scale=(0.55, 0.45, 1.8), mat=wet,
                           parent=self.drench)
            toy.hide_tree(self.drench, 1, True)
        else:
            self.max = _Absent()
            self.drench = None
        self.kids = []                                # the family stays: scale and life in the yard
        for k, look in enumerate(KID_LOOKS):
            kid = Character(f"Kid{k + 1}", look)
            kid.place(1, (*g.KIDS_SETUP[k], 0.0), 0)
            kid.key("hips", 1, loc=(0, 0, 0.56))
            kid.auto_blink(1, self.total + 600, seed=k + 3)
            self.kids.append(kid)

    def _weather_rig(self):
        self.sun_e = Chan(self.sun.data, self.sun.data, "energy", value=self.sun.data.energy)
        nt = self.scene.world.node_tree
        sky = next((n for n in nt.nodes if n.type == "TEX_SKY"), None)
        self.sky_elev = Chan(nt, sky, "sun_elevation", value=sky.sun_elevation) if sky is not None else None
        self.sky_s = Chan(self.bg.id_data, self.bg, "default_value", value=self.bg.default_value)
        streak = toy.material("kb_rain_streak", toy.srgb("#D8E6F0"), roughness=0.2, alpha=0.55)
        self.rain = toy.empty("kb_rain", (0, 0, 0))
        rnd = random.Random(5)
        for k in range(160):
            x, y = rnd.uniform(-7, 8), rnd.uniform(-3.5, 4.0)
            r = toy.cylinder(f"kb_rain_{k}", 0.006, 0.42, (x, y, 7.0), mat=streak, parent=self.rain, vertices=6)
            r.rotation_euler = (0.0, math.radians(8), 0.0)
            st.no_shadow(r)
            ph = rnd.randint(1, 16)
            r.location.z = 7.0
            r.keyframe_insert("location", index=2, frame=ph)
            r.location.z = -0.5
            r.keyframe_insert("location", index=2, frame=ph + 16)
            for fc in toy.fcurves(r):
                if fc.data_path == "location" and fc.array_index == 2:
                    for kp in fc.keyframe_points:
                        toy.set_key_interpolation(r, fc, kp, "LINEAR")
                    fc.modifiers.new("CYCLES")
        toy.hide_tree(self.rain, 1, True)
        self.weather = "sunny"

    # ---- state ----
    def _initial(self):
        return {"profile": "flat", "barrier": False, "wet": False, "core": False, "berm": False, "wells": False,
                "cover": False, "riprap": False, "tunnel": False, "patch": False, "nestbox": False, "gouge": False,
                "level": "low", "weather": "sunny"}

    def _apply(self, state, f):
        """Put the whole world into `state` at frame f (a cut: nothing animates here)."""
        prof = state["profile"]
        for nm, ch in self.shape.items():
            ch.set(f, 1.0 if nm == prof else 0.0)
        toy.hide_tree(self.barrier, f, not state["barrier"])
        earth = prof in ("wide", "gouged", "raised")
        for side in ("sec", "surf"):
            self.mat_ch[f"{side}_fill"].set(f, 1.0 if earth else 0.0)
            self.mat_ch[f"{side}_wet"].set(f, 0.0)
        self.mat_ch["surf_cover"].set(f, 1.0 if state["cover"] else 0.0)
        wet_on = state["wet"] and prof in ("steep", "slumped")
        toy.hide_tree(self.wet_layer, f, not wet_on)
        for nm, ch in self.wet_shape.items():
            ch.set(f, 1.0 if nm == ("slumped" if prof == "slumped" else "steep") else 0.0)
        for key, obj in (("core", self.core), ("berm", self.berm), ("wells", self.wells), ("riprap", self.riprap),
                         ("tunnel", self.tunnel), ("patch", self.patch), ("nestbox", self.nestbox),
                         ("gouge", self.gouge)):
            toy.hide_tree(obj, f, not state[key])
        for ch in self.grow.values():
            ch.set(f, 1.0)
        for ch, v in zip(self.tunnel_scale, (1, 1, 1)):
            ch.set(f, v)
        self._key_level(f, f, g.level(state["level"], prof if state["barrier"] else "steep"), instant=True)
        self._weather(f, state["weather"])
        for o in (self.boil, self.bags, self.sheet, self.jet, self.splash, self.marker, self.fail_flood):
            toy.hide_tree(o, f, True)
        if self.drench is not None:
            toy.hide_tree(self.drench, f, True)
        for group in self.flows.values():
            for root in group:
                toy.hide_tree(root, f, True)
        self.pile_z.set(f, 0.0 if not state["barrier"] else -0.6)
        toy.hide_tree(self.pile, f, state["barrier"])
        toy.hide_tree(self.squirrel, f, not state["nestbox"])
        if state["nestbox"]:
            nx, ny = g.NESTBOX
            for ch, v in zip(self.squirrel_loc, (nx, ny - 0.22, g.berm_top(nx) + 1.17)):
                ch.set(f, v)
        self._duck_float(f, f, instant=True, state=state)

    def _weather(self, f, kind):
        elev, sky, sun = WEATHER[kind]
        if self.sky_elev is not None:
            self.sky_elev.set(f, math.radians(elev))
        self.sky_s.set(f, sky)
        self.sun_e.set(f, sun)
        toy.hide_tree(self.rain, f, kind == "sunny")
        if kind != "sunny" and self.weather == "sunny":
            events.add(f, "rain", duration=60, gain=0.5)
        if kind == "storm" and self.weather != "storm":
            events.add(f + 6, "thunder", gain=0.7)
        self.weather = kind

    def _duck_float(self, f0, f1, instant=False, state=None, x=None):
        """The duck floats on the river, just off the barrier's water face at the current level."""
        state = state or self.state
        z = self.cur_level
        prof = state["profile"] if state["barrier"] else None
        if x is None:
            if z < 0 or prof is None:
                x = g.BANK - 0.9
            else:
                x = g.face_x(prof, max(0.0, z), -1) - 0.42
        for ch, v in zip(self.duck_loc, (x, g.DUCK_Y, z - 0.06)):
            (ch.set(f0, v) if instant else ch.move(f0, f1, v))
        if instant:
            toy.hide_tree(self.duck, f0, self.sb.get("gag") != "duck")

    # ---- planning the states of every step ----
    def _plan(self):
        state = self._initial()
        plan = {}
        for s in self.sb["steps"]:
            start = dict(state)
            ch = vocab.CHANGES[s["change"]]
            after = dict(start, weather=s["weather"])
            if s["change"] != "none":
                if ch.get("profile"):
                    after["profile"] = ch["profile"]
                    after["barrier"] = True
                    after["wet"] = False
                    after["gouge"] = False
                for add in ch.get("adds", []):
                    after[add] = True
                if s["change"] == "fill_burrows":
                    after["tunnel"] = False
            ev = vocab.EVENTS[s["event"]]
            end = dict(after, level=ev["level"])
            if s["event"] == "seep_slump":
                end.update(profile="slumped", wet=True)
            elif s["event"] == "overtop_scour":
                end.update(profile="gouged", gouge=True)
            elif s["event"] == "burrow_piping":
                end.update(tunnel=True)
            plan[s["id"]] = (start, after, end)
            state = end
        return plan

    # ---- the film ----
    def run(self, beats, spans, epilogue_offset):
        self.EPI = epilogue_offset
        steps = {s["id"]: s for s in self.sb["steps"]}
        hooks = {h["id"]: h["step"] for h in self.sb["hooks"]}
        plan = self._plan()
        hook_job = None
        for i, b in enumerate(beats):
            action = (b.get("actions") or [b.get("action")])[0]
            s, e = spans[i]
            if action in steps:
                self._stage_step(steps[action], plan[action], s, e, k=i)
            elif action in hooks:
                hook_job = (steps[hooks[action]], plan[hooks[action]], s + epilogue_offset, e + epilogue_offset)
        if hook_job:
            step, (start, after, _end), s, e = hook_job
            self.state = dict(after)
            self._apply(self.state, s - 1)
            self._mechanism(step, s, e, hook=True)
        self.rig.build()

    def _stage_step(self, step, plan, s, e, k=0):
        start, after, end = plan
        self.state = dict(start, weather=step["weather"])
        self._apply(self.state, s)
        m0 = s + max(8, int((e - s) * SETUP))
        self._setup(step, start, after, s, m0, k)
        self.state = dict(after)
        self._mechanism(step, m0, e, k=k)
        self.state = dict(end)

    # ---- SETUP: Max builds the change (or reacts), close up ----
    def _setup(self, step, start, after, s, m0, k):
        ch = step["change"]
        n = m0 - s
        mx = self.max
        if ch == "none":
            prof = after["profile"] if after["barrier"] else "steep"
            mx.cut_place(s, self._on_ground(g.max_spot(step["event"], prof), prof), 0)
            _rest(mx, s)
            if step["kind"] == "setup":
                for kid, spot in zip(self.kids, g.KIDS_SETUP):
                    kid.cut_place(s, (*spot, 0.0), -15)
                    _rest(kid, s)
                    kid.hop(s + 6, m0 - 2, height=0.18, period=14)
                mx.talk(s + 2, m0 - 4)
                mx.point(s + n // 3, m0 - 2, hand="L", up_deg=60, side_deg=-30)
            else:
                mx.talk(s + 2, m0 - 2)
        else:
            spots = {"sand_wall": (1.25, g.STAND_Y, 0.0),
                     "clay_core_widen": (g.toes("wide")[1] + 0.55, g.STAND_Y, 0.0),
                     "berm_wells": (g.toes("wide")[1] + 2.15, g.STAND_Y + 0.4, 0.0),   # past the berm toe
                     "raise_armor": (g.toes("raised")[1] + 0.6, g.STAND_Y, g.berm_top(g.toes("raised")[1] + 0.6)),
                     "fill_burrows": (g.tunnel_ends("raised")[1] + 0.6, g.STAND_Y - 0.15,
                                      g.berm_top(g.tunnel_ends("raised")[1] + 0.6))}
            mx.cut_place(s, spots[ch], 90)
            _rest(mx, s)
            if self.hero:                             # his tool sounds; a build with nobody at it is silent
                if ch in ("berm_wells", "fill_burrows"):
                    mx.hammer(s + 3, m0 - 2)
                    for f in range(s + 6, m0 - 4, 10):
                        events.add(f, "hammer", gain=0.5)
                else:
                    mx.rake(s + 3, m0 - 2)
                    for f in range(s + 6, m0 - 4, 14):
                        events.add(f, "scoop", gain=0.45)
            self._build(ch, start, after, s + 2, m0 - 1)
        if step["kind"] != "setup":
            for kid, spot in zip(self.kids, g.KIDS_SPOTS):
                kid.cut_place(s, (*spot, 0.68), 0)
                _rest(kid, s)
        if self.hero:
            st.close_on(self.rig, s, m0 - 1, mx, frac=0.44, angle=-90 + (10 if k % 2 else -10), swing=12, cut=True)
        else:
            prof = after["profile"] if after["barrier"] else "steep"
            # the empty bank before anything is built, else the part being built (or the barrier as it stands)
            region = g.build_focus(ch, prof) if after["barrier"] else g.focus("calm", prof)
            self._frame(step, region, step["event"], prof, s, m0 - 1, k + 1, label=False)

    def _build(self, ch, start, after, a, b):
        """Animate what Max builds between frames a and b."""
        if after["profile"] != start["profile"]:
            src = start["profile"] if start["barrier"] else "flat"
            if not start["barrier"]:
                toy.hide_tree(self.barrier, a, False)
                self.shape["flat"].set(a, 1.0)
            self.shape[src].move(a, b, 0.0)
            self.shape[after["profile"]].move(a, b, 1.0)
        earth = after["profile"] in ("wide", "gouged", "raised")
        for side in ("sec", "surf"):
            self.mat_ch[f"{side}_fill"].move(a, b, 1.0 if earth else 0.0)
        if start["wet"]:
            toy.hide_tree(self.wet_layer, a + (b - a) // 2, True)
        if start.get("gouge"):
            toy.hide_tree(self.gouge, a + (b - a) // 3, True)
        if after["cover"] and not start["cover"]:
            self.mat_ch["surf_cover"].move(a, b, 1.0)
        for key, obj in (("core", self.core), ("berm", self.berm)):
            if after[key] and not start[key]:
                toy.hide_tree(obj, a, False)
                self.grow[obj.name].set(a, 0.02)
                self.grow[obj.name].move(a, b, 1.0)
        if after["wells"] and not start["wells"]:
            toy.hide_tree(self.wells, a + (b - a) // 2, False)
            events.add(a + (b - a) // 2, "clink", gain=0.5)
        if after["riprap"] and not start["riprap"]:
            for k, rock in enumerate(sorted(self.riprap.children, key=lambda o: o.name)):
                toy.hide_tree(rock, a + int((b - a) * k / max(1, len(self.riprap.children))), False)
            toy.hide_tree(self.riprap, a, False)
            events.add(a + 4, "stone_thud", gain=0.4)
        if after["patch"] and not start["patch"]:
            toy.hide_tree(self.patch, a + (b - a) // 3, False)
            toy.hide_tree(self.tunnel, a + (b - a) // 3, True)
        if after["nestbox"] and not start["nestbox"]:
            toy.hide_tree(self.nestbox, a + (b - a) // 2, False)
        if not start["barrier"] and after["barrier"]:
            self.pile_z.move(a, b, -0.6)

    # ---- MECHANISM: the event, its result and Max's reaction, in one framed shot ----
    def _mechanism(self, step, m0, e, hook=False, k=0):
        ev_name = step["event"]
        ev = vocab.EVENTS[ev_name]
        prof = self.state["profile"] if self.state["barrier"] else "steep"
        n = e - m0
        t = lambda frac: m0 + int(n * frac)                         # noqa: E731
        mx = self.max
        spot = self._on_ground(g.max_spot(ev_name, prof), prof)
        mx.cut_place(m0, spot, 0 if ev_name != "storm_holds" else 10)
        _rest(mx, m0)
        target = g.level(ev["level"], prof)
        if abs(target - self.cur_level) > 0.01:
            self._key_level(m0 + 1, t(0.08), target)
            events.add(m0 + 2, "water_rush", duration=max(10, t(0.08) - m0), gain=0.4)
        if self.sb.get("gag") == "duck":
            self._duck_float(m0 + 1, t(0.08))
        getattr(self, f"_ev_{ev_name}")(m0, e, t, prof)
        if ev["outcome"] == "fail" and self.hero:
            self._failure_payoff(t, e, spot, prof)
        # the result and the reaction, inside the same shot
        if ev["outcome"] == "fail":
            if ev_name in ("burrow_piping", "underseep_boil"):
                self._jaw_drop(t(0.6), e - 2)
            else:
                self._shrug(t(0.66), e - 2)
        elif self.hero:
            mx.cheer(t(0.62), e - 2)
            events.add(t(0.62), "boing", gain=0.3)
        if ev_name == "storm_holds":
            for kid in self.kids:
                kid.hop(m0 + 4, e - 2, height=0.3, period=16)
            events.add(t(0.3), "kids_cheer", gain=0.8)
        r0 = m0 + int(n * RESULT)                 # the closer result shot that ends the beat
        if hook and self.hero:                    # the hook opens close on Max as it starts to go wrong
            h = m0 + max(8, int(n * 0.36))
            mx.brows(m0 + 2, 0.8)
            st.close_on(self.rig, m0, h - 1, mx, frac=0.44, angle=-80, swing=12, cut=True)
            self._frame(step, g.focus(ev_name, prof), ev_name, prof, h, r0 - 1, k)
        else:
            self._frame(step, g.focus(ev_name, prof), ev_name, prof, m0, r0 - 1, k)
        self._frame(step, g.result_focus(ev_name, prof), ev_name, prof, r0, e, k + 1, label_from=r0 + 2)

    def _failure_payoff(self, t, e, spot, prof):
        """One shared, unmistakable ending for every mistake: flooded yard, incoming duck, drenched Max."""
        # The measured gate samples the mechanism midpoint and 7/8: the disaster is established by the
        # midpoint, then held through the final reaction instead of flashing on only at the last frame.
        flood = t(0.08)
        toy.hide_tree(self.fail_flood, flood, False)
        toy.hide_tree(self.fail_flood, e + 1, True)
        # Sail the duck beside Max after any event-specific gag has finished.
        toy.hide_tree(self.duck, flood, False)
        # Put the duck clearly inside the flooded yard, not on the toe or the foreground cut face. The
        # deeper y position keeps blue water visible around it in the final reaction shot.
        yard_toe = g.berm_outline()[1][0] if self.state["berm"] else g.toes(prof)[1] + 0.7
        duck_x = max(spot[0] - 0.2, yard_toe + 0.25)
        duck_y = max(spot[1] + 0.65, 1.35)
        for ch, value in zip(self.duck_loc, (duck_x, duck_y, 0.14)):
            ch.move(t(0.58), t(0.76), value)
        toy.hide_tree(self.drench, t(0.10), False)
        toy.hide_tree(self.drench, e + 1, True)
        events.add(t(0.58), "water_rush", duration=max(4, e - t(0.58)), gain=0.45)
        events.add(t(0.72), "splash", gain=0.7)
        events.add(t(0.76), "quack", gain=0.65)

    def _on_ground(self, spot, prof):
        """A standing spot moved onto whatever is built there now (the berm), unless it is on the crest."""
        x, y, z = spot
        if self.state["barrier"] and abs(z - g.crest_height(prof)) < 1e-6:
            return spot
        return (x, y, g.berm_top(x) if self.state["berm"] else 0.0)

    def _frame(self, step, region, ev_name, prof, m0, e, k, label_from=None, label=True):
        """One framed shot of `region` (x0, x1, z0, z1): everything in it inside the 9:16 frame, seen from a
        little above (the river and yard surfaces read; the cut face shows only the layers that matter), the
        ground line low in the frame and the step's label in the sky above the action, for this shot only (a
        label never gets cut by the next shot's framing). Max is framed too when the story has him."""
        x0, x1, z0, z1 = region
        pts = [(x, 0.0, z) for x in (x0, x1) for z in (z0, z1)]
        if self.hero:
            spot = self._on_ground(g.max_spot(ev_name, prof), prof)
            pts += [(spot[0], spot[1], spot[2] + 1.9), (spot[0], spot[1], spot[2])]
        angle = -90 + (6 if k % 2 else -6)
        cx = (x0 + x1) / 2
        bottom = (cx, 0.0, min(z0, -0.3) - 0.15)                     # just below what the event shows
        pts.append(bottom)
        label = (step.get("label") or "").upper() if label else ""
        shot, size = list(pts), 0.0
        for _ in range(4):                    # size the label from the FINAL camera distance (it widens the shot)
            center = self._aim_for(shot, bottom, angle)
            _cam, _aim, dist = solve(shot, angle, RISE, LENS, MARGIN, center=center)
            if not label:
                break
            want = LABEL_SHARE * 2 * dist * PUSH * tan_half(LENS)[1] / CAP_HEIGHT
            if abs(want - size) < 0.01:
                break
            size = want
            lz = z1 + size * 0.6
            half = 0.31 * size * len(label)
            shot = pts + [(cx - half, -0.15, lz + size * 0.6), (cx + half, -0.15, lz + size * 0.6),
                          (cx - half, -0.15, lz - size * 0.4)]
        if label:
            make_label(label, (cx, -0.15, z1 + size * 0.6), label_from or m0 + int((e - m0) * 0.12), e, size=size,
                       tilt=0)
        st.frame_all(self.rig, m0, e, shot, angle=angle, rise=RISE, lens=LENS, margin=MARGIN, push=PUSH - 1,
                     swing=5.0, cut=True, center=center)

    @staticmethod
    def _aim_for(pts, bottom, angle):
        """The aim point that puts `bottom` (the lowest thing the shot must show) just above the frame's
        lower edge, so the frame's spare height goes to the sky and the label, not to bare bedrock."""
        from engine.framing import project
        cx = sum(p[0] for p in pts) / len(pts)
        lo, hi = min(p[2] for p in pts), max(p[2] for p in pts) + 6.0
        best, best_err = None, None
        for k in range(41):
            cz = lo + (hi - lo) * k / 40
            cam, aim, _d = solve(pts, angle, RISE, LENS, MARGIN, center=(cx, 0.0, cz))
            uv = project(bottom, cam, aim, LENS)
            if uv is None:
                continue
            err = abs(uv[1] - (MARGIN / 2 + 0.03))
            if best_err is None or err < best_err:
                best, best_err = (cx, 0.0, cz), err
        return best

    # ---- reactions ----
    def _shrug(self, f0, f1):
        if not self.hero:
            return
        m = self.max
        m.pose(f0)
        m.pose(f0 + 5, shoulderL=(-32, -40, 0), shoulderR=(-32, 40, 0), head=(-4, 0, 16))
        m.pose(f1 - 4, shoulderL=(-36, -44, 0), shoulderR=(-36, 44, 0), head=(-4, 0, 18))
        m.brows(f0 + 5, 0.9)
        m.brows(f1, 0.0)
        m.pose(f1)
        events.add(f0 + 5, "boing", gain=0.3)

    def _jaw_drop(self, f0, f1):
        m = self.max
        m.pose(f0)
        m.pose(f0 + 4, shoulderL=(-35, -118, 0), shoulderR=(-35, 118, 0), head=(-16, 0, 0))
        m.pose(f1 - 2, shoulderL=(-38, -124, 0), shoulderR=(-38, 124, 0), head=(-18, 0, 0))
        m.key("mouth", f0 + 4, scale=(1.3, 0.6, 3.4))
        m.key("mouth", f1, scale=(0.7, 0.6, 1.0))
        m.brows(f0 + 4, 1.0)
        m.brows(f1, 0.0)
        m.pose(f1)

    def _flow(self, group, f0, f1):
        for root in self.flows[group]:
            toy.hide_tree(root, f0, False)
            toy.hide_tree(root, f1, True)

    # ---- the events (each one implemented once, used by every storyboard) ----
    # Timing rule (the reviewer and the must-see gate look at the beat's middle and 7/8): the mechanism
    # starts at 40% of the beat, so its key objects must be on screen by t(0.08) (the beat's middle is about
    # t(0.17)), a change keeps happening through the middle, and it is finished before the result shot.
    def _ev_calm(self, m0, e, t, prof):
        mx = self.max
        mx.point(m0 + 4, t(0.5), hand="L", up_deg=55, side_deg=-35)
        mx.talk(t(0.5), e - 4)
        for kid in self.kids:
            kid.hop(m0 + 4, e - 4, height=0.16, period=14)

    def _ev_seep_slump(self, m0, e, t, prof):
        self._flow("seep", t(0.04), e)
        toy.hide_tree(self.wet_layer, t(0.06), False)
        self.wet_shape["steep"].set(t(0.06), 1.0)
        for side in ("sec", "surf"):
            self.mat_ch[f"{side}_wet"].move(t(0.06), t(0.3), 0.6)
        self.shape["steep"].move(t(0.14), t(0.58), 0.0)
        self.shape["slumped"].move(t(0.14), t(0.58), 1.0)
        self.wet_shape["steep"].move(t(0.14), t(0.58), 0.0)
        self.wet_shape["slumped"].move(t(0.14), t(0.58), 1.0)
        events.add(t(0.16), "dump", gain=0.6)
        events.add(t(0.06), "pour", duration=t(0.5) - t(0.06), gain=0.35)

    def _ev_seep_blocked(self, m0, e, t, prof):
        self._flow("blocked", t(0.04), e)

    def _ev_underseep_boil(self, m0, e, t, prof):
        self._flow("under", t(0.03), e)
        toy.hide_tree(self.boil, t(0.07), False)
        toy.hide_tree(self.boil, e + 1, True)
        sc = _vec_chans(self.boil_jet, "scale", (1, 1, 1))
        sc[2].set(t(0.07), 0.05)
        sc[2].move(t(0.07), t(0.2), 1.0)
        for j, f in enumerate(range(t(0.2), e - 4, 8)):
            sc[2].move(f, f + 4, 0.75 if j % 2 else 1.1)
        events.add(t(0.07), "bubbles", duration=e - t(0.07), gain=0.6)
        toy.hide_tree(self.bags, t(0.45), False)
        toy.hide_tree(self.bags, e + 1, True)
        if self.sb.get("gag") == "duck":
            for ch, v in zip(self.duck_loc, (g.BOIL_X, 0.35, 0.0)):
                ch.set(t(0.1), v)
            self.duck_loc[2].move(t(0.1), t(0.24), 0.78)
            events.add(t(0.18), "quack", gain=0.6)

    def _ev_underseep_relieved(self, m0, e, t, prof):
        self._flow("relief", t(0.03), e)
        from engine.sets.plane_story import arrow
        xl = g.toes("wide")[1]
        for j, x in enumerate((xl + 0.3, xl + 1.0)):
            arrow(f"kb_weight_{j}", (x, -0.12, g.berm_top(x) + 0.9), (0, 0, -0.7), t(0.06), e, color="#FFD23F",
                  width=0.1)
        events.add(t(0.1), "pour", duration=e - t(0.1), gain=0.3)

    def _ev_overtop_scour(self, m0, e, t, prof):
        toy.hide_tree(self.sheet, t(0.06), False)
        events.add(t(0.06), "water_rush", duration=e - t(0.06), gain=0.6)
        if prof in ("wide",):
            self.shape["wide"].move(t(0.1), t(0.58), 0.0)
            self.shape["gouged"].move(t(0.1), t(0.58), 1.0)
            toy.hide_tree(self.gouge, t(0.08), False)
        if self.sb.get("gag") == "duck":
            path = g.sheet_path("wide")
            seg = [t(0.08), t(0.2), t(0.32), t(0.44), t(0.56)]
            for j, ((x, z), f) in enumerate(zip(path, seg)):
                for ch, v in zip(self.duck_loc, (x, -0.05, z + 0.12)):
                    ch.set(f, v) if j == 0 else ch.move(seg[j - 1], f, v)
            events.add(seg[1], "quack", gain=0.5)

    def _ev_freeboard_holds(self, m0, e, t, prof):
        toy.hide_tree(self.marker, t(0.05), False)
        events.add(t(0.05), "pop", gain=0.4)

    def _ev_burrow_piping(self, m0, e, t, prof):
        a, b = g.tunnel_ends(prof)
        toy.hide_tree(self.tunnel, m0 + 1, False)
        self.tunnel_scale[0].set(m0 + 1, 0.35)
        self.tunnel_scale[0].move(m0 + 1, t(0.06), 1.0)
        toy.hide_tree(self.squirrel, m0, False)
        for ch, v in zip(self.squirrel_loc, (b + 0.18, -0.08, g.TUNNEL_Z - 0.12)):
            ch.set(m0, v)
        self.squirrel_loc[0].move(m0 + 2, t(0.06), b - 0.3)
        toy.hide_tree(self.squirrel, t(0.07), True)
        self._flow("tunnel", t(0.04), e)
        toy.hide_tree(self.jet, t(0.07), False)
        toy.hide_tree(self.splash, t(0.08), False)
        self.tunnel_scale[2].move(t(0.1), t(0.58), 1.9)
        toy.hide_tree(self.jet, e + 1, True)
        toy.hide_tree(self.splash, e + 1, True)
        events.add(t(0.07), "water_rush", duration=e - t(0.07), gain=0.7)
        events.add(t(0.08), "splash", gain=0.6)
        if self.sb.get("gag") == "duck":
            arc = g.jet_arc(prof)
            fs = [t(0.1 + 0.05 * j) for j in range(len(arc))]
            for j, ((x, z), f) in enumerate(zip(arc, fs)):
                for ch, v in zip(self.duck_loc, (x, -0.2, z + 0.1)):
                    ch.set(f, v) if j == 0 else ch.move(fs[j - 1], f, v)
            events.add(fs[2], "quack", gain=0.6)

    def _ev_burrow_sealed(self, m0, e, t, prof):
        toy.hide_tree(self.squirrel, m0, False)
        nx, ny = g.NESTBOX
        for ch, v in zip(self.squirrel_loc, (nx, ny - 0.22, g.berm_top(nx) + 1.17)):
            ch.set(m0, v)
        self.squirrel_loc[2].move(t(0.2), t(0.3), g.berm_top(nx) + 1.27)
        self.squirrel_loc[2].move(t(0.3), t(0.4), g.berm_top(nx) + 1.17)

    def _ev_storm_holds(self, m0, e, t, prof):
        self._flow("press", t(0.03), e)


def _rest(char, f):
    """Back to the standing rest pose at a cut (invisible: the camera cuts on the same frame). Gestures such
    as the cheer's little jumps otherwise leave the hips keyed high, and the curve carries that into later
    beats: Max hovered ~10 cm above the ground (the measured floating gate)."""
    char.pose(f)
    char.key("hips", f, loc=(0, 0, 0.56))


def _yard_half(profile):
    """The yard-side half of a barrier outline (6 points: same count for every profile)."""
    p = profile
    cz = p[5][1] + (p[4][1] - p[5][1]) * (0.0 - p[5][0]) / max(1e-6, p[4][0] - p[5][0])
    return [(0.0, 0.0), p[1], p[2], p[3], p[4], (0.0, cz)]


def _gouge_path():
    w, gg = g.profile("wide"), g.profile("gouged")
    return [gg[4], gg[3], gg[2], gg[1]]
