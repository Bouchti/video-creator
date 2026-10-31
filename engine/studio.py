"""
STUDIO KIT: production-quality building blocks for Max story sets (what made the boat, nuclear and
pumpkin sets look right, packaged so a new set gets it without re-learning it).

    from engine import studio as st

WORLD      st.terrain_fn(...) + st.terrain(...)    a natural mountain / valley (not a cone), rock on
                                                   steep slopes, grass on gentle ones, strata on cut faces
           st.carve(obj, cutter)                   permanent cavity (tunnel, cavern) cut into the
                                                   section face: no live boolean, no flicker
           st.tube_cutter / st.box_cutter          the cutter shapes
           st.world_floor(z)                       endless ground + deep soil: no black void anywhere
           st.scatter_on(name, ground, ...)        grass tufts that follow the terrain
WATER      st.Reservoir(...)                       volume water (no flicker) + rippling surface, keyable level
MATERIALS  st.rock_grass(), st.concrete(), st.solar_cells(), st.glass_glow() (+ engine.textures)
OBJECTS    st.dam, st.pipe (hollow, flanged, optional flowing water), st.PumpTurbine,
           st.solar_array, st.House, st.lantern
CUTAWAY    st.section_clip(obj, section) + st.Cutaway: open a hero object only while explaining its
           inside, closed whenever the camera turns
LIGHT      st.key_sky(scene, frame, elevation_deg)      dusk / night skies (key with the sun lamp)
CAMERA     st.max_height(char), st.close_on(rig, f0, f1, who)  keeps a character big (~40% of frame)
           with a slow swing; st.orbit(...), st.establish(...)  moving wide shots
LABELS     st.label / st.arrow (re-exported callouts)
INSET      st.Inset(name, center, radius)           a camera-facing magnifier circle for a small detail
LIQUID     st.Jet(name, base, direction, speed).erupt(f0, f1)   a gusher / burst pipe / fountain: core + drops

Rules the kit follows (keep them in set code too):
- Never two coplanar faces (offset touching surfaces by >= 5 mm), no bump on strongly squashed objects,
  no live booleans on anything that moves (carve once, or use section_clip).
- Large ground/background pieces do not cast shadows (visible_shadow = False): half the render time.
- The world extends far past every frame edge.
"""
import math
import random

import bmesh
import bpy
from mathutils import Vector
from mathutils import noise as mnoise

from engine import events, textures as tx, toy
from engine.cutaway import _grass_tuft, _node_curves, flow_material  # noqa: F401  (flow_material re-exported)
from engine.textures import _Tree, _cache
from engine.sets.plane_story import arrow, label  # noqa: F401  (re-exported callouts)

V = Vector
R = math.radians


# ------------------- small utilities -------------------

def _link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


def mesh_obj(name, verts, faces, mats=(), smooth=True, mat_index=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    for m in mats:
        me.materials.append(m)
    if mat_index is not None:
        for poly, k in zip(me.polygons, mat_index):
            poly.material_index = k
    if smooth:
        me.shade_smooth()
    return _link(bpy.data.objects.new(name, me))


def no_shadow(*objs):
    for o in objs:
        for x in [o] + list(o.children_recursive):
            if hasattr(x, "visible_shadow"):
                x.visible_shadow = False


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def _mix_color(t, fac, a, b):
    nd = t.nt.nodes.new("ShaderNodeMix")
    nd.data_type = "RGBA"
    t._in(nd.inputs["Factor"], fac)
    sa = next(s for s in nd.inputs if s.name == "A" and s.type == "RGBA")
    sb = next(s for s in nd.inputs if s.name == "B" and s.type == "RGBA")
    t._in(sa, a)
    t._in(sb, b)
    return next(s for s in nd.outputs if s.type == "RGBA")


# ------------------- materials -------------------

def _kit_cached(fn):
    """Build a material once per name; the name argument may be omitted (the function's default)."""
    import inspect
    default = inspect.signature(fn).parameters["name"].default

    def wrap(name=None, *a, **kw):
        name = name or default
        if name not in _cache:
            _cache[name] = fn(name, *a, **kw)
        return _cache[name]
    wrap.__doc__ = fn.__doc__
    return wrap


@_kit_cached
def rock_grass(name="st_rock_grass", grass="#5E9A3C", grass_dark="#3E7A2A", rock="#857A6B", rock_dark="#4F473E",
               grass_above=0.72):
    """Terrain: grass where the slope is gentle (normal.z > grass_above), broken rock where it is
    steep, with a noisy boundary; rock has chunky relief, grass a soft mottling."""
    t = _Tree(name)
    geo = t.node("ShaderNodeNewGeometry")
    nz = t.node("ShaderNodeSeparateXYZ", Vector=geo.outputs["Normal"]).outputs["Z"]
    wobble = t.math("MULTIPLY", t.math("SUBTRACT", t.noise(scale=0.25, detail=4), 0.5), 0.3)
    g = t.math("DIVIDE", t.math("SUBTRACT", t.math("ADD", nz, wobble), grass_above), 0.07, clamp=True)
    rock_n = t.noise(scale=0.55, detail=6, rough=0.62)
    rock_c = t.ramp(rock_n, [(0.32, rock_dark), (0.68, rock)])
    grass_c = t.ramp(t.noise(scale=0.8, detail=5), [(0.35, grass_dark), (0.72, grass)])
    color = _mix_color(t, g, rock_c, grass_c)
    height = t.math("ADD", t.math("MULTIPLY", rock_n, t.math("SUBTRACT", 1.0, g)),
                    t.math("MULTIPLY", t.noise(scale=3.0, detail=3), t.math("MULTIPLY", g, 0.25)))
    rough = t.math("ADD", 0.78, t.math("MULTIPLY", g, 0.12))
    return t.finish(color, rough, height, strength=0.55, distance=0.12)


@_kit_cached
def section_rock(name="st_section_rock", light="#8F8475", dark="#7A7064"):
    """The cut face of a mountain: rock strata in bands with pebbles (reads as 'inside the rock')."""
    t = _Tree(name)
    warp = t.math("MULTIPLY", t.noise(scale=0.12, detail=2), 2.2)
    band = t.math("FRACT", t.math("DIVIDE", t.math("ADD", t.axis("z"), warp), 2.6))
    color = t.ramp(band, [(0.0, dark), (0.5, light), (1.0, dark)])
    color = t.shade(color, t.math("ADD", 0.85, t.math("MULTIPLY", t.noise(scale=0.6, detail=5), 0.3)))
    peb = t.node("ShaderNodeTexVoronoi", Vector=t.obj, Scale=2.2).outputs["Distance"]
    pebbles = t.math("LESS_THAN", peb, 0.12)
    color = t.shade(color, t.math("SUBTRACT", 1.0, t.math("MULTIPLY", pebbles, 0.25)))
    height = t.math("ADD", t.math("MULTIPLY", pebbles, 0.6), t.noise(scale=1.4, detail=4))
    return t.finish(color, 0.9, height, strength=0.4, distance=0.06)


@_kit_cached
def cavity_rock(name="st_cavity", hexc="#4F4943"):
    """Inside a tunnel / cavern: darker, shotcrete-like."""
    t = _Tree(name)
    n = t.noise(scale=1.1, detail=5)
    return t.finish(t.shade(toy.srgb(hexc) + (1,), t.math("ADD", 0.85, t.math("MULTIPLY", n, 0.3))), 0.85, n,
                    strength=0.35, distance=0.05)


@_kit_cached
def concrete(name="st_concrete", hexc="#B8B3A8", lift=1.2, panel=2.4):
    """Cast concrete: formwork lifts (horizontal lines every `lift` m), panel joints, rain streaks."""
    t = _Tree(name)
    value, r = tx._vary(t, 0.72, amount=0.14, scale=0.8)
    lift_l, _ = t.line(t.axis("z"), lift, width=0.03)
    panel_l, _ = t.line(t.axis("xy"), panel, width=0.02)
    streak_v = t.node("ShaderNodeMapping", Vector=t.obj, Scale=(3.0, 3.0, 0.25)).outputs["Vector"]
    streaks = t.math("MULTIPLY", t.math("GREATER_THAN", t.noise(vector=streak_v, scale=1.5, detail=3), 0.58), 0.12)
    value = t.math("SUBTRACT", value, t.math("ADD", t.math("MULTIPLY", t.math("MAXIMUM", lift_l, panel_l), 0.22),
                                              streaks))
    height = t.math("SUBTRACT", t.math("MULTIPLY", t.noise(scale=9, detail=3), 0.2), t.math("MAXIMUM", lift_l, panel_l))
    return t.finish(t.shade(toy.srgb(hexc) + (1,), value), r, height, strength=0.3, distance=0.02)


@_kit_cached
def asphalt(name="st_asphalt", hexc="#3C3D40"):
    t = _Tree(name)
    n = t.noise(scale=14, detail=4)
    return t.finish(t.shade(toy.srgb(hexc) + (1,), t.math("ADD", 0.9, t.math("MULTIPLY", n, 0.2))), 0.88, n,
                    strength=0.15)


@_kit_cached
def solar_cells(name="st_solar"):
    """Photovoltaic panel face: dark blue cells, thin silver grid, a slight sheen."""
    t = _Tree(name)
    cx, _ = t.line(t.axis("x"), 0.16, width=0.08)
    cy, _ = t.line(t.axis("y"), 0.16, width=0.08)
    grid = t.math("MAXIMUM", cx, cy)
    color = _mix_color(t, grid, toy.srgb("#1B2E5A") + (1,), toy.srgb("#C9D1DA") + (1,))
    rough = t.math("ADD", 0.18, t.math("MULTIPLY", grid, 0.3))
    return t.finish(color, rough, t.math("MULTIPLY", grid, -1.0), strength=0.2, coat=0.6)


def glass_glow(name, tint="#9FC6E0", glow="#FFC46B"):
    """Window glass whose warm interior light is keyable: st.key_glow(mat, frame, strength)."""
    mat = bpy.data.materials.new(name)
    bsdf = toy._principled(mat)
    toy._set(bsdf, "Base Color", (*toy.srgb(tint), 1))
    toy._set(bsdf, "Roughness", 0.08)
    toy._set(bsdf, "Coat Weight", 0.8)
    toy._set(bsdf, "Emission Color", (*toy.srgb(glow), 1))
    toy._set(bsdf, "Emission Strength", 0.0)
    return mat


def key_glow(mat, frame, strength, constant=False):
    """Key a material's emission strength (lights on/off, glowing screens, lanterns)."""
    sock = toy._principled(mat).inputs["Emission Strength"]
    sock.default_value = strength
    sock.keyframe_insert("default_value", frame=frame)
    if constant:
        for fc in _node_curves(mat):
            for kp in fc.keyframe_points:
                if int(round(kp.co.x)) == frame:
                    toy.set_key_interpolation(mat.node_tree, fc, kp, "CONSTANT")


def glow_mat(name, hexc, strength=3.0):
    mat = bpy.data.materials.new(name)
    bsdf = toy._principled(mat)
    toy._set(bsdf, "Base Color", (*toy.srgb(hexc), 1))
    toy._set(bsdf, "Emission Color", (*toy.srgb(hexc), 1))
    toy._set(bsdf, "Emission Strength", strength)
    return mat


def water_volume(name="st_water", color="#2B86C9", density=0.5, scatter=0.12, glow=0.0, glow_color="#1F8BFF"):
    """Water as a VOLUME: deeper reads bluer; no transparency dithering, so nothing behind it flickers.
    glow (per metre) adds a blue body light: the water reads blue without hiding what is behind it."""
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
    if glow > 0:
        emit = nt.nodes.new("ShaderNodeEmission")
        emit.inputs["Color"].default_value = (*toy.srgb(glow_color), 1)
        emit.inputs["Strength"].default_value = glow
        lit = nt.nodes.new("ShaderNodeAddShader")
        nt.links.new(add.outputs[0], lit.inputs[0])
        nt.links.new(emit.outputs[0], lit.inputs[1])
        add = lit
    nt.links.new(add.outputs[0], out.inputs["Volume"])
    return mat


def flowing_water(name="st_flowing_water", hexc="#5CC4E6", along="X", speed=2.0, foam=0.45):
    """Running water as a SHEET (a slide, a spillway, a gutter, a weir): see-through blue with white foam streaks
    stretched along the flow that race downhill (a driver on the frame: no keys to break). The water-tower slide was
    a flat blue slab with ~40 balls and two thick tubes lying on it: it read as solid. along: the object axis the
    water runs along (its positive direction downhill); speed in m/s; foam: share of the sheet in streaks."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = nodes.get("Principled BSDF")
    coord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    k = "XYZ".index(along.upper())
    stretch = [7.0, 7.0, 7.0]
    stretch[k] = 0.9                                         # long streaks along the flow
    mapping.inputs["Scale"].default_value = stretch
    links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 2.2
    noise.inputs["Detail"].default_value = 6.0
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 1.0 - foam
    ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
    ramp.color_ramp.elements[1].position = min(1.0, 1.0 - foam + 0.12)
    ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs[6].default_value = (*toy.srgb(hexc), 1)
    mix.inputs[7].default_value = (0.95, 0.98, 1.0, 1)
    links.new(ramp.outputs["Color"], mix.inputs[0])
    links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    alpha = nodes.new("ShaderNodeMapRange")
    alpha.inputs["To Min"].default_value = 0.45
    alpha.inputs["To Max"].default_value = 0.95
    links.new(ramp.outputs["Color"], alpha.inputs["Value"])
    links.new(alpha.outputs["Result"], bsdf.inputs["Alpha"])
    toy._set(bsdf, "Roughness", 0.12)
    toy._set(bsdf, "IOR", 1.33)
    # the streaks race downhill: Location along the flow = -frame * speed / fps * scale (a simple expression: it
    # runs without Python auto-exec in background renders)
    fc = mapping.inputs["Location"].driver_add("default_value", k)
    fc.driver.type = "SCRIPTED"
    fc.driver.expression = f"-frame * {speed * stretch[k] / 30.0:.5f}"
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"
    if hasattr(mat, "use_backface_culling"):
        mat.use_backface_culling = True
    return mat


def water_surface(name="st_water_surface", hexc="#5CC4E6"):
    """The rippling skin on top of a water volume (keep it the ONLY blended surface in view)."""
    mat = bpy.data.materials.new(name)
    bsdf = toy._principled(mat)
    toy._set(bsdf, "Base Color", (*toy.srgb(hexc), 1))
    toy._set(bsdf, "Roughness", 0.18)
    toy._set(bsdf, "Alpha", 0.6)
    toy._set(bsdf, "IOR", 1.33)
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"
    if hasattr(mat, "use_backface_culling"):
        mat.use_backface_culling = True
    return mat


# ------------------- terrain -------------------

def terrain_fn(peaks=(), ridges=(), flats=(), basins=(), base=0.0, detail=0.35, seed=1):
    """Height function z(x, y) for a natural landscape.
    peaks:  (x, y, height, radius)            rounded massifs with rocky detail
    ridges: (x0, y0, x1, y1, height, width)   a mountain ridge along a line
    flats:  (x0, x1, y0, y1, z, margin)       building pads / valley floors, blended in over `margin`
    basins: (cx, cy, rx, ry, bottom, margin)  dug reservoirs / lakes (z pulled down to `bottom`)
    detail: rocky noise amplitude (m) on slopes, scaled by local height."""
    off = Vector((seed * 17.3, seed * 9.1, seed * 3.7))

    def fbm(x, y, s, octaves=5):
        return mnoise.fractal(Vector((x * s, y * s, 0)) + off, 1.0, 2.0, octaves, noise_basis="PERLIN_ORIGINAL")

    def z(x, y):
        h = 0.0
        for px, py, ph, pr in peaks:
            d = math.hypot(x - px, y - py) / pr
            h = max(h, ph * math.exp(-1.6 * d * d) * (1 + 0.12 * fbm(x, y, 0.08, 3)))
        for x0, y0, x1, y1, rh, rw in ridges:
            ax, ay = x1 - x0, y1 - y0
            ll = ax * ax + ay * ay or 1.0
            u = max(0.0, min(1.0, ((x - x0) * ax + (y - y0) * ay) / ll))
            d = math.hypot(x - (x0 + u * ax), y - (y0 + u * ay)) / rw
            taper = 0.75 + 0.25 * math.sin(math.pi * u)
            h = max(h, rh * taper * math.exp(-1.6 * d * d) * (1 + 0.12 * fbm(x, y, 0.08, 3)))
        h += detail * (0.25 + min(1.0, h / 6.0)) * fbm(x, y, 0.35)
        zz = base + h
        for x0, x1, y0, y1, fz, m in flats:
            dx = max(x0 - x, 0.0, x - x1)
            dy = max(y0 - y, 0.0, y - y1)
            w = 1.0 - smooth(math.hypot(dx, dy) / max(m, 1e-3))
            zz = zz + (fz - zz) * w
        for cx, cy, rx, ry, bottom, m in basins:
            d = math.hypot((x - cx) / rx, (y - cy) / ry)
            w = 1.0 - smooth((d - 1.0) * max(rx, ry) / max(m, 1e-3)) if d > 1.0 else 1.0
            zz = zz + (min(zz, bottom) - zz) * w
        return zz
    return z


def terrain(name, x0, x1, y0, y1, height, floor=-40.0, res=0.5, top=None, side=None, edge=6.0, edge_z=0.0):
    """A CLOSED landscape block over [x0,x1] x [y0,y1]: heightfield top (rock/grass), vertical sides
    and bottom (section rock). The y0 side is the cutaway face the camera looks into. Manifold, so
    st.carve() can cut tunnels and caverns into it. Within `edge` metres of the x0/x1/y1 borders the
    surface eases down to `edge_z` (the world_floor top), so no block side ever shows; edge=0 disables."""
    if edge:
        raw = height

        def height(x, y):
            d = min(x - x0, x1 - x, y1 - y)
            w = smooth(d / edge)
            return edge_z + (raw(x, y) - edge_z) * w
    top = top or rock_grass()
    side = side or section_rock()
    nx = max(2, int(round((x1 - x0) / res)) + 1)
    ny = max(2, int(round((y1 - y0) / res)) + 1)
    xs = [x0 + (x1 - x0) * i / (nx - 1) for i in range(nx)]
    ys = [y0 + (y1 - y0) * j / (ny - 1) for j in range(ny)]
    verts = [(x, y, height(x, y)) for y in ys for x in xs]
    faces, mi = [], []
    for j in range(ny - 1):
        for i in range(nx - 1):
            a = j * nx + i
            faces.append((a, a + 1, a + nx + 1, a + nx))
            mi.append(0)
    ring = ([(i, 0) for i in range(nx)] + [(nx - 1, j) for j in range(1, ny)] +
            [(i, ny - 1) for i in range(nx - 2, -1, -1)] + [(0, j) for j in range(ny - 2, 0, -1)])
    top_idx = [j * nx + i for i, j in ring]
    base = len(verts)
    verts += [(verts[k][0], verts[k][1], floor) for k in top_idx]
    n = len(ring)
    for k in range(n):
        a, b = top_idx[k], top_idx[(k + 1) % n]
        faces.append((b, a, base + k, base + (k + 1) % n))
        mi.append(1)
    faces.append(tuple(base + k for k in range(n)))
    mi.append(1)
    ob = mesh_obj(name, verts, faces, (top, side), smooth=False, mat_index=mi)
    me = ob.data
    for poly in me.polygons:                                 # smooth landscape, crisp section edges
        poly.use_smooth = poly.material_index == 0
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    ob.visible_shadow = False
    return ob


def world_floor(z=0.0, around=None, half=450.0, depth=80.0, y0=0.06):
    """Endless grass ground BEHIND the cut plane (y >= y0) with a deep rock section face below it, so
    no frame ever shows the world's edge or a black void. y0 sits just behind the sets' own cut face
    (y = 0) so the two faces never share a plane.
    around=(x0, x1, y1): the footprint of the set's terrain block (build that block with
    floor = z - depth): the ground is laid AROUND it (left, right, behind), never through it, so it
    cannot fill the tunnels and caverns carved into the terrain."""
    flat = lambda x, y: z - 0.01                                   # noqa: E731
    if around is None:
        return [terrain("ground_far", -half, half, y0, half, flat, floor=z - depth, res=half, edge=0)]
    x0, x1, y1 = around
    o = 0.05                                                       # overlap into the terrain: no seam
    return [terrain("ground_left", -half, x0 + o, y0, half, flat, floor=z - depth, res=half, edge=0),
            terrain("ground_right", x1 - o, half, y0, half, flat, floor=z - depth, res=half, edge=0),
            terrain("ground_back", x0 + o, x1 - o, y1 - o, half, flat, floor=z - depth, res=half, edge=0)]


def carve(obj, cutter, mat=None):
    """Cut `cutter` out of `obj` ONCE (exact boolean, applied) and delete the cutter. The new cavity
    walls get `mat` (default: dark cavity rock). Static result: nothing re-meshes per frame."""
    mat = mat or cavity_rock()
    cutter.data.materials.clear()
    cutter.data.materials.append(mat)
    if mat.name not in [m.name for m in obj.data.materials if m]:
        obj.data.materials.append(mat)
    mod = obj.modifiers.new("carve", "BOOLEAN")
    mod.operation, mod.object = "DIFFERENCE", cutter
    if hasattr(mod, "solver"):
        mod.solver = "EXACT"
    if hasattr(mod, "material_mode"):
        mod.material_mode = "TRANSFER"
    with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj]):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    return obj


def _spline_pts(pts, step=0.25):
    """Catmull-Rom through `pts` sampled every ~step metres (smooth bends, exact ends)."""
    P = [V(p) for p in pts]
    if len(P) < 3:
        a, b = P[0], P[-1]
        n = max(1, int((b - a).length / step))
        return [a.lerp(b, k / n) for k in range(n + 1)]
    out = []
    ext = [P[0] + (P[0] - P[1])] + P + [P[-1] + (P[-1] - P[-2])]
    for k in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[k - 1], ext[k], ext[k + 1], ext[k + 2]
        n = max(2, int((p2 - p1).length / step))
        for s in range(n):
            t = s / n
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
                              (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-1])
    return out


def _curve_obj(name, pts, radius, caps=True, resolution=12, radii=None):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_mode = "ROUND"
    cu.bevel_depth = radius
    cu.bevel_resolution = max(2, resolution // 4)
    cu.use_fill_caps = caps
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for k, (p, q) in enumerate(zip(sp.points, pts)):
        p.co = (q.x, q.y, q.z, 1)
        if radii:
            p.radius = radii[k]
    return _link(bpy.data.objects.new(name, cu))


def _to_mesh(obj, name=None):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
    out = _link(bpy.data.objects.new(name or obj.name, me))
    out.matrix_world = obj.matrix_world.copy()
    bpy.data.objects.remove(obj, do_unlink=True)
    return out


def tube_cutter(pts, radius, extend=0.0):
    """A solid tube along a smooth path (to carve a tunnel/shaft)."""
    P = _spline_pts(pts)
    if extend:
        P = [P[0] - (P[1] - P[0]).normalized() * extend] + P + [P[-1] + (P[-1] - P[-2]).normalized() * extend]
    return _to_mesh(_curve_obj("st_tube_cutter", P, radius, caps=True))


def box_cutter(center, size):
    """A solid box (to carve a cavern / machine hall)."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    c = bpy.context.active_object
    c.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    c.name = "st_box_cutter"
    return c


def scatter_on(name, ground, density=6.0, max_slope_deg=28, size=1.6, seed=3, instance=None):
    """Grass tufts (or `instance`) scattered over the GENTLE faces of `ground` (follows the terrain),
    baked into one static, shadowless mesh."""
    from engine.toy import _socket
    inst = instance or _grass_tuft()
    em = _link(bpy.data.objects.new(name, ground.data.copy()))
    em.matrix_world = ground.matrix_world.copy()
    ng = bpy.data.node_groups.new(f"{name}_scatter", "GeometryNodeTree")
    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n, link = ng.nodes, ng.links.new
    gin, gout = n.new("NodeGroupInput"), n.new("NodeGroupOutput")
    normal = n.new("GeometryNodeInputNormal")
    sep = n.new("ShaderNodeSeparateXYZ")
    cmp = n.new("FunctionNodeCompare")
    cmp.data_type, cmp.operation = "FLOAT", "GREATER_THAN"
    _socket(cmp.inputs, "B", "VALUE").default_value = math.cos(math.radians(max_slope_deg))
    dist = n.new("GeometryNodeDistributePointsOnFaces")
    dist.distribute_method = "RANDOM"
    dist.inputs["Density"].default_value = density
    dist.inputs["Seed"].default_value = seed
    info = n.new("GeometryNodeObjectInfo")
    info.inputs["Object"].default_value = inst
    rot = n.new("FunctionNodeRandomValue")
    rot.data_type = "FLOAT_VECTOR"
    _socket(rot.inputs, "Min", "VECTOR").default_value = (-0.15, -0.15, 0)
    _socket(rot.inputs, "Max", "VECTOR").default_value = (0.15, 0.15, 2 * math.pi)
    scl = n.new("FunctionNodeRandomValue")
    scl.data_type = "FLOAT"
    _socket(scl.inputs, "Min", "VALUE").default_value = size * 0.5
    _socket(scl.inputs, "Max", "VALUE").default_value = size
    on = n.new("GeometryNodeInstanceOnPoints")
    real = n.new("GeometryNodeRealizeInstances")
    link(normal.outputs[0], sep.inputs[0])
    link(sep.outputs["Z"], _socket(cmp.inputs, "A", "VALUE"))
    link(gin.outputs[0], dist.inputs["Mesh"])
    link(cmp.outputs[0], dist.inputs["Selection"])
    link(dist.outputs["Points"], on.inputs["Points"])
    link(info.outputs["Geometry"], on.inputs["Instance"])
    link(_socket(rot.outputs, "Value", "VECTOR"), on.inputs["Rotation"])
    link(_socket(scl.outputs, "Value", "VALUE"), on.inputs["Scale"])
    link(on.outputs["Instances"], real.inputs["Geometry"])
    link(real.outputs["Geometry"], gout.inputs[0])
    mod = em.modifiers.new("scatter", "NODES")
    mod.node_group = ng
    with bpy.context.temp_override(object=em, active_object=em, selected_objects=[em]):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    em.data.materials.clear()
    for mat in inst.data.materials:
        em.data.materials.append(mat)
    em.visible_shadow = False
    inst.hide_render = True
    return em


# ------------------- water -------------------

class Reservoir:
    """A body of water over [x0,x1] x [y0,y1] from `bottom` up to a keyable `level`: a volume (deeper
    is bluer, no flicker) plus a rippling surface sheet. The y0 face is the cutaway face.

        res = st.Reservoir("upper", -8, 2, 0.05, 12, bottom=20, level=24)
        res.key_level(f0, 24); res.key_level(f1, 20.4)        # drains between f0 and f1
        res.empty(f2)                                          # DRAINED: water gone, wet floor + a puddle
        res.fill(f3)                                           # water back (then key_level as usual)

    A nearly-empty reservoir must use empty(): a thin water sheet still reads as a FULL basin on screen.
    Parent res.parts() to a moving container if the basin moves.
    """

    def __init__(self, name, x0, x1, y0, y1, bottom, level, color="#2B86C9", density=0.5, scatter=0.12, glow=0.0):
        self.name, self.bottom = name, bottom
        self.vol = toy.box(f"{name}_water", (1, 1, 1), (0, 0, 0),
                           mat=water_volume(f"{name}_vol", color, density, scatter, glow), bevel=0)
        self.vol.location = ((x0 + x1) / 2, (y0 + y1) / 2, 0)
        self.vol.scale = (x1 - x0 - 0.02, y1 - y0, 1)
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=max(8, int((x1 - x0) * 4)), y_subdivisions=max(8, int((y1 - y0) * 4)),
                                        size=1, location=((x0 + x1) / 2, (y0 + y1) / 2 + 0.003, level))
        self.surf = bpy.context.active_object
        self.surf.name = f"{name}_water_surface"
        self.surf.scale = (x1 - x0 - 0.02, y1 - y0, 1)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        self.surf.data.materials.append(water_surface(f"{name}_surface"))
        tex = bpy.data.textures.new(f"{name}_ripples", "CLOUDS")
        tex.noise_scale = 0.35
        drift = toy.empty(f"{name}_drift", (0, 0, 0))
        drift.keyframe_insert("location", frame=1)
        drift.location = (14, 6, 4)
        drift.keyframe_insert("location", frame=6000)
        toy.set_interpolation(drift, "location", (1,), "LINEAR")
        disp = self.surf.modifiers.new("ripples", "DISPLACE")
        disp.texture, disp.texture_coords, disp.texture_coords_object = tex, "OBJECT", drift
        disp.strength, disp.mid_level = 0.03, 0.5
        no_shadow(self.vol, self.surf)
        self._apply(level)
        self.level = level
        # the drained look: a darker wet floor and one irregular glossy puddle (single mesh, no bump)
        rnd = random.Random(len(name))
        cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) * 0.22, (y1 - y0) * 0.2
        ring = []
        for k in range(24):
            a = 2 * math.pi * k / 24
            r = 1 + 0.28 * math.sin(3 * a + 0.7) + 0.12 * rnd.uniform(-1, 1)
            ring.append((cx + rx * r * math.cos(a), cy + ry * r * math.sin(a), bottom + 0.012))
        pud = bpy.data.materials.new(f"{name}_puddle")
        bsdf = toy._principled(pud)
        toy._set(bsdf, "Base Color", (*toy.srgb("#2E5E7A"), 1))
        toy._set(bsdf, "Roughness", 0.05)
        toy._set(bsdf, "Coat Weight", 1.0)
        self.puddle = mesh_obj(f"{name}_puddle", ring, [tuple(range(24))], (pud,), smooth=False)
        self.wet = toy.box(f"{name}_wetfloor", (x1 - x0 - 0.04, y1 - y0 - 0.02, 0.004), (cx, cy, bottom + 0.003),
                           mat=concrete(f"{name}_wet", "#6F6B63", lift=0.5, panel=1.2), bevel=0)
        no_shadow(self.puddle, self.wet)
        for o in (self.puddle, self.wet):
            toy.hide_tree(o, 0, True)

    def parts(self):
        return [self.vol, self.surf, self.puddle, self.wet]

    def empty(self, frame):
        """Drained from `frame`: the water disappears, a wet floor and one puddle remain."""
        for o in (self.vol, self.surf):
            toy.hide_tree(o, frame, True)
        for o in (self.puddle, self.wet):
            toy.hide_tree(o, frame, False)

    def fill(self, frame):
        """Water again from `frame` (key the level as usual)."""
        for o in (self.vol, self.surf):
            toy.hide_tree(o, frame, False)
        for o in (self.puddle, self.wet):
            toy.hide_tree(o, frame, True)

    def _apply(self, level):
        top = max(self.bottom + 0.002, level - 0.06)
        self.vol.location.z = (top + self.bottom) / 2
        self.vol.scale.z = max(0.002, top - self.bottom)
        self.surf.location.z = level

    def key_level(self, frame, level, hold=True):
        """Key the water level at `frame` (hold=True also holds the previous level until frame-1 is keyed
        by the caller's previous key, so levels move only between keys)."""
        self._apply(level)
        self.vol.keyframe_insert("location", frame=frame)
        self.vol.keyframe_insert("scale", frame=frame)
        self.surf.keyframe_insert("location", frame=frame)
        self.level = level

    def hide(self, frame, hidden):
        toy.hide_tree(self.vol, frame, hidden)
        toy.hide_tree(self.surf, frame, hidden)


WATER_CLEAR = 0.5       # share of the red light that crosses the whole body to the camera: see-through
WATER_SCATTER = 0.012   # per metre: more haze turns a deep body into a milky wall
WATER_GLOW = 0.6        # blue body light over the whole depth: the blue of water, without hiding anything


class Water(Reservoir):
    """THE water for anything the viewer looks INTO (a sea, a lake, a pool, a flooded dock): a Reservoir that
    stays see-through at any size, with a visible waterline on the cut face.

        sea = st.Water("sea", -14, 9, 0.05, 5, bottom=-12, level=0)
        sea.key_level(f0, 0.0); sea.empty(f1)                    # every Reservoir method works

    Its density is computed from its own depth into the picture (y1 - y0), so WATER_CLEAR of the light always
    reaches the camera and whatever is in or behind the water (a tunnel, fish, the far bank) stays readable.
    A fixed density made the tunnel film's 5 m sea a solid blue wall (and the look repair, asked for a "bright
    blue tint", made it denser still): never raise it. The blue comes from a faint body glow (glow), which tints
    without hiding anything; measured by engine/water_still.py (tests/test_water.py).
    The waterline is a thin bright strip on the cut face at the level, keyed with it."""

    def __init__(self, name, x0, x1, y0, y1, bottom, level, color="#1E8FE6", clear=WATER_CLEAR, glow=WATER_GLOW):
        depth = max(0.2, y1 - y0)
        density = -math.log(min(0.95, max(0.2, clear))) / depth
        super().__init__(name, x0, x1, y0, y1, bottom, level, color=color, density=density,
                         scatter=min(WATER_SCATTER, density * 0.25), glow=glow / depth)
        line = bpy.data.materials.new(f"{name}_waterline")
        bsdf = toy._principled(line)
        toy._set(bsdf, "Base Color", (*toy.srgb("#E8FBFF"), 1))
        toy._set(bsdf, "Emission Color", (*toy.srgb("#CFF5FF"), 1))
        toy._set(bsdf, "Emission Strength", 1.4)
        self.line = toy.box(f"{name}_waterline", (x1 - x0 - 0.02, 0.01, 0.045), ((x0 + x1) / 2, y0 - 0.006, level),
                            mat=line, bevel=0)
        no_shadow(self.line)
        self.line.location.z = level - 0.0225

    def _apply(self, level):
        super()._apply(level)
        if hasattr(self, "line"):
            self.line.location.z = level - 0.0225

    def key_level(self, frame, level, hold=True):
        super().key_level(frame, level, hold)
        self.line.keyframe_insert("location", frame=frame)

    def parts(self):
        return super().parts() + [self.line]

    def empty(self, frame):
        super().empty(frame)
        toy.hide_tree(self.line, frame, True)

    def fill(self, frame):
        super().fill(frame)
        toy.hide_tree(self.line, frame, False)

    def hide(self, frame, hidden):
        super().hide(frame, hidden)
        toy.hide_tree(self.line, frame, hidden)


# ------------------- objects -------------------

def prism(name, outline_xz, y0, y1, mat=None):
    """Extrude a closed x-z outline (counter-clockwise) along y from y0 to y1."""
    n = len(outline_xz)
    verts = [(x, y0, z) for x, z in outline_xz] + [(x, y1, z) for x, z in outline_xz]
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    faces += [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
    ob = mesh_obj(name, verts, faces, (mat,) if mat else (), smooth=False)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def dam(name, x, y0, y1, base_z, height, crest=1.4, base=None, facing=1, mat=None):
    """A concrete gravity dam whose profile is seen in the cutaway: vertical upstream face, sloped
    downstream face (toward +x if facing=1), crest road with parapets, drain gallery line.
    Spans y0..y1 (into the picture). Returns the root empty."""
    mat = mat or concrete()
    base = base or height * 0.75
    s = facing
    up = x - s * crest / 2
    prof = [(up, base_z), (up + s * base, base_z), (up + s * crest, base_z + height), (up, base_z + height)]
    if s < 0:
        prof = prof[::-1]
    root = toy.empty(name, (0, 0, 0))
    body = prism(f"{name}_body", prof, y0, y1, mat)
    body.parent = root
    road = toy.box(f"{name}_crest_road", (crest + 0.1, y1 - y0, 0.08), (x, (y0 + y1) / 2, base_z + height + 0.04),
                   mat=asphalt(), bevel=0)
    road.parent = root
    for k, dx in enumerate((-crest / 2 + 0.06, crest / 2 - 0.06)):
        p = toy.box(f"{name}_parapet{k}", (0.12, y1 - y0 - 0.01, 0.5), (x + dx, (y0 + y1) / 2, base_z + height + 0.335),
                    mat=mat, bevel=0.01)
        p.parent = root
    for k in range(int((y1 - y0) / 2.0)):                     # lamp posts along the crest
        y = y0 + 1.0 + k * 2.0
        post = toy.cylinder(f"{name}_lamp{k}", 0.035, 1.2, (x, y, base_z + height + 0.68), mat=tx.metal(
            "st_lamp_metal", "#6B7077", 0.4), vertices=8)
        post.parent = root
    return root


def pipe(name, pts, radius, mat=None, wall=0.06, flange_every=2.5, flow=None, section=None):
    """A hollow steel pipe / penstock along a smooth path, with flanges. flow: None or a
    flow_material(...) to fill it with visibly moving water (see engine.cutaway.flow_material:
    key its 'flow_on' value). section: an empty -> the pipe is cut open on its -y side (cutaway) via
    section_clip. Returns the root empty; root['water'] is the flowing core if any."""
    mat = mat or tx.paint("st_pipe_paint", "#5E7A8C", 0.35, coat=0.4)
    P = _spline_pts(pts)
    root = toy.empty(name, (0, 0, 0))
    shell = _to_mesh(_curve_obj(f"{name}_shell", P, radius, caps=False), f"{name}_shell")
    shell.data.materials.append(mat)
    sol = shell.modifiers.new("wall", "SOLIDIFY")
    sol.thickness, sol.offset = wall, 1.0
    shell.parent = root
    core = None
    if flow is not None:
        core = _to_mesh(_curve_obj(f"{name}_water", P, radius * 0.86, caps=True), f"{name}_water")
        core.data.materials.append(flow)
        core.parent = root
    fl_mat = tx.metal("st_flange", "#4D5C66", 0.35)
    acc, nxt, k = 0.0, flange_every, 0
    for a, b in zip(P, P[1:]):
        seg = (b - a).length
        while flange_every and acc + seg >= nxt:
            t = (nxt - acc) / seg
            pos = a.lerp(b, t)
            bpy.ops.mesh.primitive_torus_add(major_radius=radius + wall * 0.6, minor_radius=wall * 0.9,
                                             major_segments=32, minor_segments=8, location=pos)
            ring = bpy.context.active_object
            ring.name = f"{name}_flange{k}"
            ring.rotation_euler = (b - a).to_track_quat("Z", "Y").to_euler()
            ring.data.materials.append(fl_mat)
            ring.parent = root
            k += 1
            nxt += flange_every
        acc += seg
    if section is not None:
        for o in [shell] + [c for c in root.children if c.name.startswith(f"{name}_flange")]:
            section_clip(o, section)
    root["water"] = core.name if core else ""
    return root


class PumpTurbine:
    """A recognizable Francis pump-turbine unit (vertical axis) as seen in a powerhouse cutaway:
    snail-shaped spiral casing fed by an inlet pipe, ring of wicket gates, a bladed runner on a shaft,
    a curved draft tube below, and a big ribbed motor-generator on top.

        u = st.PumpTurbine("unit1", (x, y, z_floor), size=1.0)
        u.spin(f0, f1, rps=1.2)            # generating (runner turns one way)
        u.spin(f2, f3, rps=-1.2)           # pumping (reversed)
        u.shudder(f4, f5)                  # rough running
        u.open_casing(section)             # cutaway: show the runner inside the casing
    size=1 -> about 3.6 m tall (scale to the set)."""

    def __init__(self, name, location, size=1.0, casing="#3D6E9E", gen="#D9A531", facing_deg=0.0):
        s = size
        self.name = name
        self.root = toy.empty(name, location)
        self.root.rotation_euler = (0, 0, R(facing_deg))
        cas = tx.paint(f"st_casing_{casing}", casing, 0.32, coat=0.55)
        steel = tx.metal("st_runner_steel", "#B8BEC4", 0.25)
        bronze = tx.metal("st_runner_bronze", "#B4874A", 0.3)
        genm = tx.paint(f"st_gen_{gen}", gen, 0.3, coat=0.6)
        dark = tx.metal("st_unit_dark", "#2E3338", 0.45)
        zc = 0.9 * s                                           # casing centre height
        # spiral casing: a curve that winds 330 deg, its tube shrinking as it feeds the runner
        pts, radii = [], []
        for k in range(34):
            a = R(-90 + k * 10)
            rr = (1.05 - 0.45 * k / 33) * s
            pts.append(V((math.cos(a) * rr, math.sin(a) * rr, zc)))
            radii.append(1.0 - 0.62 * k / 33)
        inlet = [V((-2.6 * s, -1.05 * s, zc)), V((-1.4 * s, -1.05 * s, zc))]
        cu = _curve_obj(f"{name}_spiral", inlet + pts, 0.42 * s, caps=True, radii=[1.0, 1.0] + radii)
        self.casing = _to_mesh(cu, f"{name}_spiral")
        self.casing.data.materials.append(cas)
        self.casing.parent = self.root
        ring = toy.cylinder(f"{name}_stayring", 0.62 * s, 0.5 * s, (0, 0, zc), mat=cas, vertices=40)
        ring.parent = self.root
        # wicket gates (fixed ring of guide vanes) + runner (spins)
        self.runner = toy.empty(f"{name}_runner", (0, 0, zc))
        self.runner.parent = self.root
        hub = toy.cylinder(f"{name}_hub", 0.2 * s, 0.55 * s, (0, 0, 0), mat=bronze, vertices=24)
        hub.parent = self.runner
        hub.location = (0, 0, 0)
        for k in range(9):
            a = 2 * math.pi * k / 9
            bl = toy.box(f"{name}_blade{k}", (0.36 * s, 0.05 * s, 0.42 * s), (0, 0, 0), mat=bronze, bevel=0.01)
            bl.parent = self.runner
            bl.location = (math.cos(a) * 0.36 * s, math.sin(a) * 0.36 * s, 0)
            bl.rotation_euler = (R(28), 0, a + R(25))
        for k in range(16):
            a = 2 * math.pi * k / 16
            v = toy.box(f"{name}_wicket{k}", (0.03 * s, 0.14 * s, 0.46 * s),
                        (math.cos(a) * 0.68 * s, math.sin(a) * 0.68 * s, zc), mat=dark, bevel=0.005)
            v.rotation_euler = (0, 0, a + R(35))
            v.parent = self.root
        # draft tube: down, then out to the tailrace
        dt = [V((0, 0, zc - 0.3 * s)), V((0, 0, -0.4 * s)), V((0.2 * s, 0, -0.9 * s)), V((1.6 * s, 0, -1.0 * s)),
              V((2.6 * s, 0, -1.0 * s))]
        self.draft = _to_mesh(_curve_obj(f"{name}_draft", _spline_pts(dt, 0.15), 0.42 * s, caps=True,
                                         radii=None), f"{name}_draft")
        self.draft.data.materials.append(cas)
        self.draft.parent = self.root
        # shaft + motor-generator (rotor spins with the runner; stator + ribs fixed)
        self.shaft = toy.cylinder(f"{name}_shaft", 0.09 * s, 1.5 * s, (0, 0, 0.75 * s), mat=steel, vertices=16)
        self.shaft.parent = self.runner
        self.shaft.location = (0, 0, 0.75 * s)
        stator_z = zc + 1.65 * s
        st_ = toy.cylinder(f"{name}_generator", 0.95 * s, 1.0 * s, (0, 0, stator_z), mat=genm, vertices=48)
        st_.parent = self.root
        for k in range(24):
            a = 2 * math.pi * k / 24
            rib = toy.box(f"{name}_rib{k}", (0.07 * s, 0.05 * s, 0.9 * s),
                          (math.cos(a) * 0.97 * s, math.sin(a) * 0.97 * s, stator_z), mat=dark, bevel=0.005)
            rib.rotation_euler = (0, 0, a)
            rib.parent = self.root
        cap = toy.cylinder(f"{name}_gencap", 0.75 * s, 0.16 * s, (0, 0, stator_z + 0.58 * s), mat=dark, vertices=40)
        cap.parent = self.root
        self.rotor_mark = toy.box(f"{name}_rotor_mark", (0.5 * s, 0.1 * s, 0.05 * s), (0, 0, 0), mat=glow_mat(
            f"{name}_mark", "#FFFFFF", 0.6), bevel=0.01)
        self.rotor_mark.parent = self.runner
        self.rotor_mark.location = (0.35 * s, 0, stator_z - zc + 0.69 * s)   # visible spin cue on top
        base = toy.box(f"{name}_plinth", (2.4 * s, 2.4 * s, 0.3 * s), (0, 0, 0.15 * s), mat=concrete(), bevel=0.02)
        base.parent = self.root
        self._angle = 0.0
        self._last = None
        self._keys = []

    def spin(self, f0, f1, rps=1.0):
        """Turn the runner (and rotor mark) at `rps` revolutions/second between f0 and f1 (negative =
        pumping direction). Consecutive calls continue from the reached angle."""
        if self._last is None or self._last < f0 - 1:
            self.runner.rotation_euler = (0, 0, self._angle)
            self.runner.keyframe_insert("rotation_euler", index=2, frame=f0)
            self._keys.append(f0)
        self._angle += 2 * math.pi * rps * (f1 - f0) / 30.0
        self.runner.rotation_euler = (0, 0, self._angle)
        self.runner.keyframe_insert("rotation_euler", index=2, frame=f1)
        self._keys.append(f1)
        toy.set_interpolation(self.runner, "rotation_euler", self._keys, "LINEAR")    # steady speed, no easing
        self._last = f1
        events.add(f0, "turbine", duration=f1 - f0, gain=0.35)

    def shudder(self, f0, f1, amp=0.03):
        for axis in (0, 1):
            toy.add_noise(self.root, "location", axis, strength=amp, scale=2.5, phase=axis * 5)
        mod_end = f1

        def gate(fc):
            for m in fc.modifiers:
                if m.type == "NOISE":
                    m.use_restricted_range = True
                    m.frame_start, m.frame_end = f0, mod_end
                    m.blend_in = m.blend_out = 6
        for fc in toy.fcurves(self.root):
            if fc.data_path == "location":
                gate(fc)

    def open_casing(self, section):
        """Cut the casing and generator open on the camera side (show the runner) while `section` is in."""
        for o in [self.casing] + [c for c in self.root.children if c.name.endswith(("_generator", "_stayring"))]:
            section_clip(o, section)


def solar_array(name, origin, rows=2, cols=6, panel=(1.0, 1.6), tilt=25.0, gap=0.12, facing_deg=0.0):
    """Rows of tilted photovoltaic panels on posts (cells, aluminium frames, legs)."""
    root = toy.empty(name, origin)
    root.rotation_euler = (0, 0, R(facing_deg))
    cell, frame_m = solar_cells(), tx.metal("st_alu", "#C3C8CD", 0.3)
    pw, ph = panel
    for r in range(rows):
        for c in range(cols):
            x = (c - (cols - 1) / 2) * (pw + gap)
            y = r * (ph + 1.4)
            z = 0.6 + ph / 2 * math.sin(R(tilt))
            pan = toy.box(f"{name}_panel{r}_{c}", (pw, ph, 0.04), (x, y, z), mat=cell, bevel=0.005)
            pan.rotation_euler = (R(tilt), 0, 0)
            pan.parent = root
            fr = toy.box(f"{name}_frame{r}_{c}", (pw + 0.04, ph + 0.04, 0.03), (x, y, z - 0.03), mat=frame_m,
                         bevel=0.004)
            fr.rotation_euler = (R(tilt), 0, 0)
            fr.parent = root
            for dy in (-ph * 0.35, ph * 0.35):
                h = z + dy * math.sin(R(tilt)) - 0.02
                leg = toy.cylinder(f"{name}_leg{r}_{c}_{dy:.1f}", 0.03, h, (x, y + dy * math.cos(R(tilt)), h / 2),
                                   mat=frame_m, vertices=8)
                leg.parent = root
    return root


class House:
    """A family house with lap siding, a shingled gable roof, glowing windows, a door, a porch light.
    house.lights(frame, on) switches the windows."""

    def __init__(self, name, location, w=4.2, d=3.6, h=2.6, wall="#E9DCC0", roof="#A8402F", facing_deg=0.0):
        self.root = toy.empty(name, location)
        self.root.rotation_euler = (0, 0, R(facing_deg))
        siding = tx.planks(f"st_siding_{wall}", wall, wall, width=0.2, lap=True, across="z", along="xy", rough=0.6)
        body = toy.box(f"{name}_walls", (w, d, h), (0, 0, h / 2), mat=siding, bevel=0.02)
        body.parent = self.root
        roof_m = tx.shingles(f"st_roof_{roof}", roof, "#5E2318")
        rh = d * 0.42
        gable = prism(                                     # ridge along x: profile across y, turned 90 deg
f"{name}_roof", [(-d / 2 - 0.3, 0), (d / 2 + 0.3, 0), (0, rh)], -w / 2 - 0.3, w / 2 + 0.3, roof_m)
        gable.rotation_euler = (0, 0, R(90))
        gable.location = (0, 0, h)
        gable.parent = self.root
        chim = toy.box(f"{name}_chimney", (0.4, 0.4, 1.0), (w * 0.25, d * 0.15, h + rh * 0.7), mat=tx.planks(
            "st_brick", "#9C4A36", "#8A3F2E", width=0.08, across="z", along="xy"), bevel=0.01)
        chim.parent = self.root
        self.glass = glass_glow(f"{name}_glass")
        trim = tx.paint("st_trim_white", "#F4F1EA", 0.4)
        for k, x in enumerate((-w * 0.3, w * 0.3)):
            win = toy.box(f"{name}_window{k}", (0.8, 0.04, 0.8), (x, -d / 2 - 0.006, h * 0.55), mat=self.glass, bevel=0)
            win.parent = self.root
            fr = toy.box(f"{name}_wframe{k}", (0.92, 0.03, 0.92), (x, -d / 2 + 0.004, h * 0.55), mat=trim, bevel=0.01)
            fr.parent = self.root
        door = toy.box(f"{name}_door", (0.8, 0.05, 1.7), (0, -d / 2 - 0.012, 0.85), mat=tx.wood(
            "st_door", "#6B4A2E", "#80593A"), bevel=0.01)
        door.parent = self.root
        self.porch = glow_mat(f"{name}_porch", "#FFD27A", 0.0)
        lamp = toy.sphere(f"{name}_porchlamp", 0.08, (0.6, -d / 2 - 0.1, 1.9), mat=self.porch, subdiv=1)
        lamp.parent = self.root

    def lights(self, frame, on=True, strength=6.0):
        key_glow(self.glass, frame - 1, 0.0 if on else strength, constant=True)
        key_glow(self.glass, frame, strength if on else 0.0, constant=True)
        key_glow(self.porch, frame - 1, 0.0 if on else strength, constant=True)
        key_glow(self.porch, frame, strength if on else 0.0, constant=True)


def lantern(name, color="#FFC45E"):
    """A camping lantern (base, glass globe with a keyable glow, cap, handle). Hold it with a hand
    joint; key its glow with st.key_glow(lantern['glow'], frame, strength)."""
    root = toy.empty(name, (0, 0, 0))
    dark = tx.metal("st_lantern_metal", "#2F3A33", 0.4)
    g = glow_mat(f"{name}_glow", color, 0.0)
    b = toy.cylinder(f"{name}_base", 0.07, 0.05, (0, 0, 0.025), mat=dark, vertices=16)
    glass = toy.cylinder(f"{name}_globe", 0.058, 0.13, (0, 0, 0.115), mat=g, vertices=16)
    cap = toy.cylinder(f"{name}_cap", 0.07, 0.04, (0, 0, 0.2), mat=dark, vertices=16)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.06, minor_radius=0.008, location=(0, 0, 0.25))
    handle = bpy.context.active_object
    handle.name = f"{name}_handle"
    handle.rotation_euler = (R(90), 0, 0)
    handle.data.materials.append(dark)
    for o in (b, glass, cap, handle):
        o.parent = root
    root["glow"] = g.name
    return root


# ------------------- liquid jet -------------------

class Jet:
    """A liquid jet (an oil gusher, a burst pipe, a fountain, a hose): one CONTINUOUS core stream that arcs under
    gravity plus many SMALL drops flying off it, so it reads as liquid, never as a stack of balls (the oil film's
    first gusher was 34 big black spheres).

        gush = st.Jet("gush", base=(0, 0, 0.4), direction=(0.1, 0, 1), speed=9, color="#121212")
        gush.erupt(f0, f1, rise=3)           # shoots out within `rise` frames (a hook: rise=2-3), stops at f1

    speed (m/s) sets the height (~speed^2 / 19.6 m straight up). color: oil #121212, water #8FD3FF, mud #6B4A2E."""

    def __init__(self, name, base, direction=(0, 0, 1), speed=8.0, color="#8FD3FF", radius=0.09, drops=90,
                 drop_size=0.065, spread=0.3, seed=1, fps=30):
        self.name, self.base, self.fps = name, V(base), fps
        d = V(direction).normalized()
        self.v = d * speed
        self.gravity = V((0, 0, -9.81))
        water = color.upper() in ("#8FD3FF", "#5CC4E6") or color.upper().startswith("#8")
        self.mat = toy.material(f"st_jet_{color}", toy.srgb(color), roughness=0.06 if water else 0.12, coat=0.6)
        self.root = toy.empty(f"{name}_jet", base)
        # a steep jet's stream rises to its peak and breaks into a crown of falling drops (a column that bends back
        # to the ground reads as a hose arch); a sideways one (a burst pipe) arcs all the way down as one stream
        steep = d.z > 0.7
        t_end = self.v.z / 9.81 if steep else self._flight(self.v)
        pts = [self._at(self.v, t_end * k / 24) - self.base for k in range(25)]
        cu = bpy.data.curves.new(f"{name}_core", "CURVE")
        cu.dimensions = "3D"
        cu.bevel_mode = "ROUND"
        cu.bevel_depth = radius
        cu.bevel_resolution = 3
        cu.use_fill_caps = True
        if hasattr(cu, "bevel_factor_mapping_end"):
            cu.bevel_factor_mapping_start = cu.bevel_factor_mapping_end = "SPLINE"
        sp = cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        for k, (pt, q) in enumerate(zip(sp.points, pts)):
            pt.co = (q.x, q.y, q.z, 1)
            pt.radius = 1.0 + (2.2 if steep else 0.6) * (k / 24) ** 1.5      # it widens as it slows and breaks up
        self.core = _link(bpy.data.objects.new(f"{name}_core", cu))
        self.core.data.materials.append(self.mat)
        self.core.parent = self.root
        rnd = random.Random(seed)
        top = self._at(self.v, t_end)
        self.drops = []
        for i in range(drops):
            if steep:                         # the crown: drops burst out of the column's top and rain around it
                start = top + V((rnd.gauss(0, radius * 2), rnd.gauss(0, radius * 2), rnd.uniform(-0.3, 0.1)))
                a = rnd.uniform(0, 2 * math.pi)
                out = speed * spread * rnd.uniform(0.45, 1.2)
                v = V((math.cos(a) * out, math.sin(a) * out, speed * rnd.uniform(0.0, 0.3))) + 0.3 * V((self.v.x, self.v.y, 0))
            else:
                start = self.base
                jitter = V((rnd.gauss(0, spread), rnd.gauss(0, spread), rnd.gauss(0, spread * 0.5)))
                v = (d + jitter).normalized() * speed * rnd.uniform(0.75, 1.08)
            r = drop_size * rnd.uniform(0.55, 1.25)
            drop = toy.sphere(f"{name}_drop_{i}", r, (0, 0, 0), mat=self.mat, subdiv=1, parent=self.root)
            self.drops.append((drop, start, v, rnd.random()))
        no_shadow(self.core, *[dr for dr, *_rest in self.drops])
        toy.hide_tree(self.root, 1, True)

    def _at(self, v, t, start=None):
        return (self.base if start is None else start) + v * t + 0.5 * self.gravity * t * t

    def _flight(self, v, start=None):
        """Seconds until a drop launched at `start` (default: the nozzle) falls back to the nozzle's height."""
        drop = 0.0 if start is None else max(0.0, start.z - self.base.z)
        return max(0.4, (v.z + math.sqrt(v.z * v.z + 2 * 9.81 * drop)) / 9.81)

    def erupt(self, f0, f1, rise=4):
        """Shoots out from f0 (full length after `rise` frames), runs to f1, then the stream drains away."""
        cu = self.core.data
        toy.hide_tree(self.root, f0, False)
        for f, end, start in ((f0, 0.0, 0.0), (f0 + rise, 1.0, 0.0), (f1, 1.0, 0.0), (f1 + 10, 1.0, 1.0)):
            cu.bevel_factor_end, cu.bevel_factor_start = end, start
            cu.keyframe_insert("bevel_factor_end", frame=f)
            cu.keyframe_insert("bevel_factor_start", frame=f)
        toy.hide_tree(self.core, f1 + 11, True)
        last = f1 + 11
        for drop, start, v, phase in self.drops:
            flight = self._flight(v, start)
            period = max(8, int(round(flight * self.fps)))
            launch = f0 + int(phase * period * 0.9) + rise // 2
            for k in range(9):                                 # one flight, repeated by a CYCLES modifier
                drop.location = self._at(v, flight * k / 8, start) - self.base
                drop.keyframe_insert("location", frame=launch + period * k / 8)
            for fc in toy.fcurves(drop):
                if fc.data_path == "location":
                    for kp in fc.keyframe_points:
                        kp.interpolation = "LINEAR"
                    fc.modifiers.new("CYCLES")
            toy.hide_tree(drop, 1, True)
            toy.hide_tree(drop, launch, False)
            n = max(0, (f1 - launch) // period + 1)            # it lands after the stream has stopped
            toy.hide_tree(drop, launch + n * period, True)
            last = max(last, launch + n * period)
        events.add(f0, "splash", gain=0.6)
        return last


# ------------------- magnifier inset -------------------

class Inset:
    """A magnifier circle (brass ring, dark backdrop) that ALWAYS faces the camera, for a detail too small to read
    in the shot (the layers of a gasket, a valve's seat). Build its contents at the origin of the inset's local
    space and attach them: x right, z up, y < 0 in front of the backdrop (toward the camera).

        ins = st.Inset("seal", (2.6, 1.0, 2.8), radius=0.7)
        ins.attach(toy.sphere("seal_ball", 0.12, (0, -0.05, 0)))
        ins.show(f0, f1)                     # pops in at f0, out at f1; hidden otherwise

    It is a SUPPLEMENT, never the explanation: the story is told by the big mechanism itself. The render step
    hides it on any frame where the camera cuts it at the frame edge (engine/overlays.py), so show it in
    medium / wide shots and keep it beside, not above, the subject (in a close-up on Max it would be cut)."""

    def __init__(self, name, center, radius=0.7, rim="#C9A227", backdrop="#173E7A"):
        self.root = toy.empty(f"inset_{name}", center)
        self.radius = radius
        cam = bpy.context.scene.camera
        if cam is not None:
            con = self.root.constraints.new("DAMPED_TRACK")
            con.target = cam
            con.track_axis = "TRACK_NEGATIVE_Y"
        brass = tx.metal(f"st_inset_rim_{rim}", rim, 0.3)
        bpy.ops.mesh.primitive_torus_add(major_radius=radius, minor_radius=radius * 0.07, major_segments=64,
                                         minor_segments=12, location=(0, 0, 0))
        ring = bpy.context.active_object
        ring.name = f"inset_{name}_ring"
        ring.rotation_euler = (R(90), 0, 0)
        ring.data.materials.append(brass)
        back = toy.cylinder(f"inset_{name}_back", radius * 0.97, 0.02, (0, 0.03, 0), rotation=(R(90), 0, 0),
                            mat=toy.material(f"st_inset_back_{backdrop}", toy.srgb(backdrop), roughness=0.8),
                            vertices=64)
        for o in (ring, back):
            o.parent = self.root
        no_shadow(ring, back)
        self.parts = [ring, back]
        toy.hide_tree(self.root, 1, True)

    def attach(self, obj, location=None):
        """Parent obj to the inset (location: its place in the inset's local space)."""
        obj.parent = self.root
        if location is not None:
            obj.location = location
        no_shadow(obj)
        self.parts.append(obj)
        if self.root.hide_render:
            toy.hide_tree(obj, 1, True)
        return obj

    def show(self, f0, f1, pop=8):
        """Visible (popping in and out) from f0 to f1."""
        toy.hide_tree(self.root, f0, False)
        toy.hide_tree(self.root, f1 + 1, True)
        for f, s in ((f0, 0.05), (f0 + pop, 1.0), (max(f0 + pop, f1 - pop), 1.0), (f1, 0.05)):
            self.root.scale = (s, s, s)
            self.root.keyframe_insert("scale", frame=f)


# ------------------- cutaway -------------------

def section_clip(obj, section):
    """Give `obj` its own copies of its materials, cut away where y < 0 in `section` space. Move the
    section empty far toward -y to close the object (whole), to y=0 to open it (crisp 0/1 alpha)."""
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
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        if alpha_in.is_linked:
            nt.links.new(alpha_in.links[0].from_socket, mul.inputs[0])
        else:
            mul.inputs[0].default_value = alpha_in.default_value
        nt.links.new(keep.outputs[0], mul.inputs[1])
        nt.links.new(mul.outputs[0], alpha_in)
        if hasattr(m, "surface_render_method") and m.surface_render_method != "BLENDED":
            m.surface_render_method = "DITHERED"
        if hasattr(m, "use_backface_culling"):
            m.use_backface_culling = False


class Cutaway:
    """One section plane for a hero object: closed (whole object) by default.

        cut = st.Cutaway("unit_cut", y_open=0.0)
        st.section_clip(part, cut.section) for each part
        cut.open(f0); cut.close(f1)        # open ONLY in head-on shots, closed before the camera turns
    """

    def __init__(self, name, origin=(0, 0, 0), y_open=0.0, y_closed=-30.0):
        self.section = toy.empty(name, (origin[0], origin[1] + y_closed, origin[2]))
        self.origin, self.y_open, self.y_closed = V(origin), y_open, y_closed
        self.section.keyframe_insert("location", frame=0)

    def _at(self, f, y):
        self.section.location = (self.origin.x, self.origin.y + y, self.origin.z)
        self.section.keyframe_insert("location", frame=f)

    def open(self, f, frames=12):
        toy.key_hold(self.section, "location", f - 1)
        self._at(f + frames, self.y_open)
        events.add(f, "whoosh", gain=0.25)

    def close(self, f, frames=12):
        toy.key_hold(self.section, "location", f - 1)
        self._at(f + frames, self.y_closed)


# ------------------- light -------------------

def key_sky(scene, frame, elevation_deg, strength=None):
    """Set the SKY's own sun (the physical sky model) at `frame`: ~40 deg day, ~20 afternoon, ~1 dusk (orange
    horizon), ~-5 night (deep blue). Without it dusk and night keep a bright blue daytime sky. Key it with
    the same frames as the sun lamp's energy/colour; strength optionally keys the sky brightness too."""
    nodes = scene.world.node_tree.nodes
    sky = next((n for n in nodes if n.type == "TEX_SKY"), None)
    if sky is not None:
        sky.sun_elevation = math.radians(elevation_deg)
        sky.keyframe_insert("sun_elevation", frame=frame)
    if strength is not None:
        bg = next((n for n in nodes if n.type == "BACKGROUND"), None)
        if bg is not None:
            bg.inputs["Strength"].default_value = strength
            bg.inputs["Strength"].keyframe_insert("default_value", frame=frame)


# ------------------- camera -------------------

SENSOR = 36.0          # Blender's sensor fits the LONG side: the frame height of a 9:16 film


def max_height(char):
    """World height of a character (lowest to highest visible mesh point) at the current frame."""
    pts = [o.matrix_world @ V(c) for o in [char.root] + list(char.root.children_recursive)
           if o.type == "MESH" for c in o.bound_box]
    return max(p.z for p in pts) - min(p.z for p in pts) if pts else 1.5


def frame_distance(height, frac, lens):
    """Camera distance at which an object `height` tall fills `frac` of the frame height."""
    return height * lens / (SENSOR * frac)


def _root_at(char, f):
    return V(toy.world_location_at(char.root, f))          # (world: Max may ride a boat or a rising house)


def close_on(rig, f0, f1, who, frac=0.42, angle=-90.0, swing=16.0, rise=0.25, lens=32.0, look=0.62,
             offset=(0, 0, 0), cut=False, fstop=4.0, height=None):
    """A MOVING close shot that keeps `who` at ~frac of the frame height (default 42%), swinging
    `swing` degrees around him (angle: -90 = from -Y, the front) and following him if he walks.
    offset shifts the framed point (e.g. toward the prop he works on)."""
    H = height or max_height(who)
    dist = frame_distance(H, frac, lens)
    keys = []
    for f in list(range(f0, f1, 3)) + [f1]:
        t = smooth((f - f0) / max(1, f1 - f0))
        a = R(angle - swing / 2 + swing * t)
        c = _root_at(who, f) + V((0, 0, H * look)) + V(offset)
        cam = c + V((math.cos(a) * dist, math.sin(a) * dist, H * rise))
        keys.append((f, cam, c))
    rig.track(f0, f1, keys, lens=lens, fstop=fstop, cut=cut)


def orbit(rig, f0, f1, center, radius, ang0, ang1, z0, z1, lens=24.0, cut=False, fstop=8.0):
    """The camera TURNS around `center` from ang0 to ang1 (deg, -90 = front), rising z0 -> z1, eased."""
    keys = []
    for f in list(range(f0, f1, 3)) + [f1]:
        t = smooth((f - f0) / max(1, f1 - f0))
        a = R(ang0 + (ang1 - ang0) * t)
        c = V(center)
        cam = c + V((math.cos(a) * radius, math.sin(a) * radius, z0 + (z1 - z0) * t))
        keys.append((f, cam, c))
    rig.track(f0, f1, keys, lens=lens, cut=cut, fstop=fstop)


def _frame_points(things, frames):
    """World bounding-box corners of `things` (objects, Characters, or (x, y, z) points) as they RENDER at
    each of `frames`; hidden objects are skipped (a parked, hidden prop must not widen the shot)."""
    scene = bpy.context.scene
    keep = scene.frame_current
    pts = []
    try:
        for f in frames:
            scene.frame_set(f)
            dg = bpy.context.evaluated_depsgraph_get()
            for t in things:
                if isinstance(t, (tuple, list, Vector)) and len(t) == 3 and all(
                        isinstance(x, (int, float)) for x in t):
                    pts.append(tuple(t))
                    continue
                root = getattr(t, "root", t)
                for o in [root] + list(root.children_recursive):
                    if o.type not in ("MESH", "FONT", "CURVE"):
                        continue
                    p, hidden = o, False
                    while p is not None and not hidden:
                        hidden, p = p.hide_render, p.parent
                    if hidden:
                        continue
                    mw = o.evaluated_get(dg).matrix_world
                    pts += [tuple(mw @ V(c)) for c in o.bound_box]
    finally:
        scene.frame_set(keep)
    return pts


def frame_all(rig, f0, f1, things, angle=-90.0, rise=0.18, lens=28.0, margin=0.12, push=0.06, swing=6.0,
              cut=False, fstop=8.0, sample=None, center=None):
    """A MOVING shot that keeps EVERY one of `things` (objects, Characters, (x, y, z) points: the mechanism,
    its label, the result meter, Max) fully inside the 9:16 frame from f0 to f1: the camera distance is
    solved from their real bounds (engine/framing.py), then it pushes in by `push` and swings `swing`
    degrees so the shot never holds still. Use it for every shot that must SHOW something named in the
    narration; list only what must be seen (each extra far-away thing makes the shot wider). center: a fixed
    aim point (default: the middle of the things), e.g. to set where the ground line sits in the frame."""
    from engine import framing
    mid = (f0 + f1) // 2
    pts = _frame_points(things, sample or (f0, mid, f1))
    if not pts:
        raise ValueError(f"frame_all({f0}-{f1}): none of the things is visible")
    keys, dist = [], 0.0
    for f in list(range(f0, f1, 3)) + [f1]:
        t = smooth((f - f0) / max(1, f1 - f0))
        cam, aim, dist = framing.solve(pts, angle - swing / 2 + swing * t, rise, lens, margin, center=center)
        cam = V(aim) + (V(cam) - V(aim)) * (1.0 + push * (1.0 - t))      # push in to the solved framing
        keys.append((f, cam, V(aim)))
    rig.track(f0, f1, keys, lens=lens, fstop=fstop, cut=cut)
    return dist


def establish(rig, f0, f1, center, dist0, dist1, angle=-90.0, height=0.25, lens=24.0, cut=False):
    """A wide shot that slowly pushes in from dist0 to dist1 (use it briefly, then go close)."""
    a = R(angle)
    d = V((math.cos(a), math.sin(a), height)).normalized()
    rig.shot(f0, f1, cam_from=V(center) + d * dist0, cam_to=V(center) + d * dist1, aim_from=center, lens=lens,
             fstop=8.0, cut=cut)
