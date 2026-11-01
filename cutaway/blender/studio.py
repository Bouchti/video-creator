"""
The product-shot studio (runs inside Blender): HDRI reflections, a dark seamless cyclorama with a soft
floor shadow, and a key / rim / kicker rig aimed at the subject.

The HDRI lights and reflects but is never seen: camera rays see the brand navy instead, so every shot sits
on the same dark background.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Vector

from . import geo
from . import materials as M


def world(hdri: str, strength: float = 0.85, diffuse: float = 0.05, rotation_deg: float = 0.0,
          bg: str = "#0a1220"):
    """HDRI at `strength` for reflections only; diffuse rays get `diffuse` of it, so the area lights shape the
    subject and the backdrop stays dark; camera rays see the flat brand navy."""
    w = bpy.data.worlds.new("studio")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(rotation_deg))
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(hdri, check_existing=True)
    hdr = nt.nodes.new("ShaderNodeBackground")
    hdr.inputs["Strength"].default_value = strength
    flat = nt.nodes.new("ShaderNodeBackground")
    flat.inputs["Color"].default_value = M.hex_rgb(bg)
    flat.inputs["Strength"].default_value = 1.0
    dim = nt.nodes.new("ShaderNodeBackground")
    dim.inputs["Strength"].default_value = diffuse
    lp = nt.nodes.new("ShaderNodeLightPath")
    gloss = nt.nodes.new("ShaderNodeMixShader")
    mix = nt.nodes.new("ShaderNodeMixShader")
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
    nt.links.new(env.outputs["Color"], hdr.inputs["Color"])
    nt.links.new(env.outputs["Color"], dim.inputs["Color"])
    nt.links.new(lp.outputs["Is Glossy Ray"], gloss.inputs["Fac"])
    nt.links.new(dim.outputs["Background"], gloss.inputs[1])
    nt.links.new(hdr.outputs["Background"], gloss.inputs[2])
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(gloss.outputs["Shader"], mix.inputs[1])
    nt.links.new(flat.outputs["Background"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return w


def cyclorama(floor_z: float, size: float = 6.0, wall: float = 4.0, radius: float = 1.2, back_y: float = 1.6,
              color: str = "#0b1426"):
    """A seamless floor that curves up into a back wall behind the subject (+Y is back)."""
    bm = bmesh.new()
    # (y, z) points: floor from the front to the start of the bend, quarter circle, then the wall
    pts = [(-size, floor_z)] + [(back_y - radius + radius * math.sin(math.radians(90 * i / 12)),
                                 floor_z + radius - radius * math.cos(math.radians(90 * i / 12)))
                                for i in range(13)] + [(back_y, floor_z + wall)]
    half = size
    left = [bm.verts.new((-half, y, z)) for y, z in pts]
    right = [bm.verts.new((half, y, z)) for y, z in pts]
    for i in range(len(pts) - 1):
        bm.faces.new((left[i], right[i], right[i + 1], left[i + 1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = geo.from_bmesh("cyclorama", bm, mat=M.backdrop(color))
    for f in obj.data.polygons:
        f.use_smooth = True
    # normals must face the subject (up on the floor, -Y on the wall)
    if obj.data.polygons[0].normal.z < 0:
        obj.data.flip_normals()
    return obj


def _area(name, kind_size, energy, kelvin, loc, target):
    ld = bpy.data.lights.new(name, "AREA")
    ld.shape = "RECTANGLE"
    ld.size, ld.size_y = kind_size
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


def face_camera(objs, center, cam_pos):
    """Turn the cyclorama and light rig about the subject so the back wall sits opposite the camera."""
    import math as _m
    d = Vector(cam_pos) - Vector(center)
    rot = _m.atan2(d.y, d.x) - _m.atan2(-1.0, 0.0)          # rig authored for a camera on -Y
    piv = Vector(center)
    for o in objs:
        local = o.location - Vector((piv.x, piv.y, 0.0))
        c, s = _m.cos(rot), _m.sin(rot)
        o.location = Vector((piv.x + local.x * c - local.y * s, piv.y + local.x * s + local.y * c, o.location.z))
        o.rotation_euler.z += rot


def lights(center, radius: float, key_side: float = -1.0, scale: float = 1.0):
    """Key (warm, big, high and to the side), rim (cool, behind), kicker (low, opposite side), top fill.
    `radius` is the subject's rough size; energies scale with distance squared so any subject reads the same."""
    tgt = bpy.data.objects.new("light_target", None)
    bpy.context.scene.collection.objects.link(tgt)
    tgt.location = center
    c = Vector(center)
    d = radius * 3.2
    e = scale * (d / 1.5) ** 2
    rig = {
        "key": _area("key", (d * 0.9, d * 0.6), 300 * e, 5200, c + Vector((key_side * d * 0.9, -d * 0.8, d * 0.75)), tgt),
        "rim": _area("rim", (d * 0.25, d * 1.1), 520 * e, 9500, c + Vector((-key_side * d * 0.7, d * 1.0, d * 0.5)), tgt),
        "kick": _area("kick", (d * 0.2, d * 0.8), 150 * e, 7800, c + Vector((-key_side * d * 1.1, -d * 0.2, -d * 0.1)), tgt),
        "top": _area("top", (d * 1.0, d * 1.0), 35 * e, 6500, c + Vector((0, 0, d * 1.3)), tgt),
    }
    return rig
