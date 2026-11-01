"""
The Build-It studio (runs inside Blender): a warm seamless backdrop, a low lumpy ground haze, and big soft
lights, as in docs/style_guide.md. Scaled by the subject size, so a 10 cm valve and a 2 m engine sit in the same
room.

    st = build(size=1.0)          # size = the subject's rough height in metres
    st["wash"].data.energy = ...  # warm wash on the wall (heat / energy beats), keyable
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Vector

from cutaway.blender import geo

from . import materials as M

HDRI_STRENGTH = 0.55


def world(hdri: str | None, color: str = "#a09e9b"):
    """Warm ambient for diffuse; the studio HDRI only in reflections (chrome needs something to mirror)."""
    w = bpy.data.worlds.new("buildit")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    flat = nt.nodes.new("ShaderNodeBackground")
    flat.inputs["Color"].default_value = M.hex_rgb(color)
    flat.inputs["Strength"].default_value = 0.22
    out = nt.nodes.new("ShaderNodeOutputWorld")
    if not hdri:
        nt.links.new(flat.outputs["Background"], out.inputs["Surface"])
        return w
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(hdri, check_existing=True)
    hdr = nt.nodes.new("ShaderNodeBackground")
    hdr.inputs["Strength"].default_value = HDRI_STRENGTH
    nt.links.new(env.outputs["Color"], hdr.inputs["Color"])
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Glossy Ray"], mix.inputs["Fac"])
    nt.links.new(flat.outputs["Background"], mix.inputs[1])
    nt.links.new(hdr.outputs["Background"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return w


def backdrop(size: float):
    """Seamless cyclorama: floor from the front, a wide bend, the wall behind (+Y is back)."""
    depth, back, radius, wall, half = 14 * size, 6 * size, 3.0 * size, 12 * size, 16 * size
    pts = [(-depth, 0.0)] + [(back - radius + radius * math.sin(math.radians(90 * i / 16)),
                              radius - radius * math.cos(math.radians(90 * i / 16))) for i in range(17)] + \
          [(back, wall)]
    bm = bmesh.new()
    xs = [-half + 2 * half * k / 24 for k in range(25)]
    rows = [[bm.verts.new((x, y, z)) for x in xs] for y, z in pts]
    for a, b in zip(rows, rows[1:]):
        for i in range(len(xs) - 1):
            bm.faces.new((a[i], a[i + 1], b[i + 1], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = geo.from_bmesh("backdrop", bm, mat=M.backdrop(wall_h=wall * 0.75))
    for f in obj.data.polygons:
        f.use_smooth = True
    if obj.data.polygons[0].normal.z < 0:
        obj.data.flip_normals()
    return obj


def haze(size: float, layers: int = 5, height: float = 0.24, radius: float = 7.0):
    """Stacked translucent slices of lumpy fog over the floor (cheap in EEVEE and Cycles, reads as volume)."""
    out = []
    for k in range(layers):
        z = height * size * (k + 0.5) / layers
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=radius * size)
        o = geo.from_bmesh(f"haze_{k}", bm, mat=M.haze(density=1.0 - 0.08 * k, scale=2.2 / size,
                                                        seed=k * 0.37))
        o.location = (0, -1.0 * size, z)
        o.visible_shadow = False
        o["no_occlude"] = 1
        out.append(o)
    return out


def _area(name, size_xy, energy, kelvin, loc, target):
    ld = bpy.data.lights.new(name, "AREA")
    ld.shape = "RECTANGLE"
    ld.size, ld.size_y = size_xy
    ld.energy = energy
    ld.use_temperature = True
    ld.temperature = kelvin
    ob = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    c = ob.constraints.new("TRACK_TO")
    c.target = target
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"
    return ob


def lights(center, size: float):
    """Big soft key from the upper front-left, a broad fill, a warm rim, and a wall wash (off by default)."""
    tgt = bpy.data.objects.new("light_target", None)
    bpy.context.scene.collection.objects.link(tgt)
    tgt.location = center
    c = Vector(center)
    s = size
    e = s * s
    rig = {
        "key": _area("key", (3.0 * s, 2.4 * s), 900 * e, 6000, c + Vector((-2.6 * s, -3.0 * s, 3.2 * s)), tgt),
        "fill": _area("fill", (4.0 * s, 3.0 * s), 140 * e, 6400, c + Vector((3.2 * s, -3.4 * s, 1.4 * s)), tgt),
        "rim": _area("rim", (2.0 * s, 1.2 * s), 420 * e, 3800, c + Vector((1.8 * s, 2.6 * s, 2.6 * s)), tgt),
    }
    wt = bpy.data.objects.new("wash_target", None)
    bpy.context.scene.collection.objects.link(wt)
    wt.location = (c.x, 6 * s, 3.0 * s)
    rig["wash"] = _area("wash", (6.0 * s, 4.0 * s), 0.0, 3200, Vector((c.x, 2.0 * s, 1.0 * s)), wt)
    # only the key casts shadows (the soft contact shadows of the reference); fill, rim and wash light without
    # them: each shadowed light costs about a fifth of a frame in EEVEE
    for name in ("fill", "rim", "wash"):
        rig[name].data.use_shadow = False
    rig["wash"].hide_render = True                 # switched on (and keyed) only when a beat washes the wall
    return rig


def bowl(radius: float = 14.0, wall: float = 12.0, bend: float = 4.0):
    """A seamless studio all around: a round floor that curves up into a round wall, so the camera can film
    the machine from any side (the back parts too) and never sees an edge."""
    prof = [(0.0, 0.0), (radius - bend, 0.0)]
    prof += [(radius - bend + bend * math.sin(math.radians(90 * i / 12)),
              bend - bend * math.cos(math.radians(90 * i / 12))) for i in range(1, 13)]
    prof += [(radius, wall)]
    o = geo.lathe("studio_bowl", prof, 96, mat=M.studio_shell(wall_h=wall))
    o.data.flip_normals() if o.data.polygons[0].normal.z < 0 else None
    for f in o.data.polygons:
        f.use_smooth = True
    return o


def bright_lights(center, size: float, accent: str):
    """A bright product-shoot rig: a big soft key (the only shadow caster), a broad fill, two rims for clean
    edges, a soft top light, and an accent-coloured glow on the wall behind the machine."""
    tgt = bpy.data.objects.new("light_target", None)
    bpy.context.scene.collection.objects.link(tgt)
    tgt.location = center
    c, s = Vector(center), size
    e = s * s
    rig = {
        "key": _area("key", (3.2 * s, 3.2 * s), 1100 * e, 5600, c + Vector((-2.8 * s, -3.2 * s, 3.4 * s)), tgt),
        "fill": _area("fill", (5.0 * s, 4.0 * s), 300 * e, 6200, c + Vector((3.6 * s, -3.0 * s, 1.6 * s)), tgt),
        "rim_l": _area("rim_l", (1.2 * s, 3.0 * s), 520 * e, 7000, c + Vector((-2.6 * s, 2.4 * s, 1.8 * s)), tgt),
        "rim_r": _area("rim_r", (1.2 * s, 3.0 * s), 420 * e, 4800, c + Vector((2.6 * s, 2.4 * s, 1.8 * s)), tgt),
        "top": _area("top", (2.4 * s, 2.4 * s), 260 * e, 6000, c + Vector((0, 0.2 * s, 4.2 * s)), tgt),
    }
    for name in ("fill", "rim_l", "rim_r", "top"):
        rig[name].data.use_shadow = False
    wt = bpy.data.objects.new("wash_target", None)
    bpy.context.scene.collection.objects.link(wt)
    wt.location = (c.x, 9.0 * s, 2.2 * s)
    acc = _area("accent", (5.0 * s, 3.0 * s), 2600 * e, 6500, Vector((c.x, 3.2 * s, 1.0 * s)), wt)
    acc.data.use_temperature = False
    acc.data.color = M.hex_rgb(accent)[:3]
    acc.data.use_shadow = False
    rig["accent"] = acc
    rig["wash"] = _area("wash", (6.0 * s, 4.0 * s), 0.0, 3200, Vector((c.x, 3.0 * s, 1.0 * s)), wt)
    rig["wash"].data.use_shadow = False
    rig["wash"].hide_render = True
    return rig


def build_bright(hdri: str | None, accent: str = "#36b4ff", size: float = 1.0, center=(0.0, 0.0, 0.8)):
    """The bright premium studio (the default look since Nov 2026)."""
    world(hdri, color="#dfe4e9")
    bpy.context.scene.world.node_tree.nodes[0].inputs["Strength"].default_value = 0.3
    bw = bowl()
    rig = bright_lights(center, size, accent)
    return {"backdrop": bw, "haze": [], **rig}


def build(hdri: str | None, size: float = 1.0, center=(0.0, 0.0, 0.5)):
    """The whole studio; returns its pieces (lights are keyable)."""
    world(hdri)
    bd = backdrop(size)
    hz = haze(size)
    rig = lights(center, size)
    return {"backdrop": bd, "haze": hz, **rig}
