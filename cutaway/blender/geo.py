"""
Mesh building blocks for production-quality parts (runs inside Blender).

Every helper returns a closed, manifold mesh object so it can be booleaned (the section cut, holes, ports).
Shapes get real edges: chamfers in the profiles, bevel modifiers baked in, smooth shading split by angle.
Units are metres; Z is up.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector


def collection(name: str, parent=None):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(col)
    return col


def _object(name: str, mesh, col=None):
    obj = bpy.data.objects.new(name, mesh)
    (col or bpy.context.scene.collection).objects.link(obj)
    return obj


def from_bmesh(name: str, bm, col=None, mat=None):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    obj = _object(name, me, col)
    if mat is not None:
        me.materials.append(mat)
    return obj


def shade(obj, angle: float = 32.0):
    """Smooth shading with hard edges above `angle` degrees (machined parts read crisp, castings soft)."""
    obj.data.shade_smooth()
    obj.data.set_sharp_from_angle(angle=math.radians(angle))
    return obj


def bake(obj):
    """Apply every modifier into the mesh (so later booleans see the finished shape)."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    old = obj.data
    obj.modifiers.clear()
    obj.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    outward(obj)
    return obj


def outward(obj):
    """Point every face outward. A boolean chain can leave a closed mesh inside-out, and an inside-out operand
    makes the next EXACT boolean return its complement (a difference that fills the world)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)     # booleans leave split seams on re-triangulated ngons
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return obj


def bevel(obj, width: float, segments: int = 3, angle: float = 35.0, apply: bool = True):
    """Round every edge sharper than `angle` (fillets on castings, chamfers on machined edges)."""
    m = obj.modifiers.new("bevel", "BEVEL")
    m.width = width
    m.segments = segments
    m.limit_method = "ANGLE"
    m.angle_limit = math.radians(angle)
    m.harden_normals = True
    m.miter_outer = "MITER_ARC"
    m.profile = 0.5
    if apply:
        bake(obj)
        shade(obj, angle=angle + 5)
    return obj


def boolean(obj, cutter, op: str = "DIFFERENCE", apply: bool = True, remove_cutter: bool = True):
    m = obj.modifiers.new(f"bool_{cutter.name}", "BOOLEAN")
    m.operation = op
    m.solver = "EXACT"
    m.object = cutter
    m.material_mode = "TRANSFER"
    m.use_hole_tolerant = True
    if apply:
        bake(obj)
        if remove_cutter:
            bpy.data.objects.remove(cutter, do_unlink=True)
    return obj


def join(name: str, objs, col=None):
    """Merge objects into one mesh object (keeps each part's material)."""
    bm = bmesh.new()
    mats = []
    for o in objs:
        me = o.data
        offset = len(mats)
        for m in me.materials:
            mats.append(m)
        tmp = bmesh.new()
        tmp.from_mesh(me)
        tmp.transform(o.matrix_world)
        for f in tmp.faces:
            f.material_index += offset
        tmp_me = bpy.data.meshes.new("_tmp")
        tmp.to_mesh(tmp_me)
        tmp.free()
        bm.from_mesh(tmp_me)
        bpy.data.meshes.remove(tmp_me)
        bpy.data.objects.remove(o, do_unlink=True)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    obj = _object(name, me, col)
    obj.data.shade_smooth()
    return obj


# ---------------------------------------------------------------- primitives with real edges

def lathe(name: str, profile, segments: int = 64, col=None, mat=None, angle: float = 32.0):
    """Revolve a (radius, z) profile around Z. Start and end the profile at radius 0 for a closed solid."""
    clean = []
    for p in profile:                     # repeated points make zero-length edges -> non-manifold rings
        if not clean or abs(p[0] - clean[-1][0]) > 1e-7 or abs(p[1] - clean[-1][1]) > 1e-7:
            clean.append(p)
    profile = clean
    bm = bmesh.new()
    verts = [bm.verts.new((r, 0.0, z)) for r, z in profile]
    edges = [bm.edges.new((verts[i], verts[i + 1])) for i in range(len(verts) - 1)]
    bmesh.ops.spin(bm, geom=verts + edges, cent=(0, 0, 0), axis=(0, 0, 1),
                   angle=math.tau, steps=segments, use_merge=True, use_duplicate=False)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return shade(from_bmesh(name, bm, col, mat), angle)


def prism(name: str, outline, z0: float, z1: float, col=None, mat=None):
    """Extrude a closed (x, y) outline from z0 to z1."""
    bm = bmesh.new()
    bottom = [bm.verts.new((x, y, z0)) for x, y in outline]
    face = bm.faces.new(bottom)
    res = bmesh.ops.extrude_face_region(bm, geom=[face])
    top = [e for e in res["geom"] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=top, vec=(0, 0, z1 - z0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return shade(from_bmesh(name, bm, col, mat), 30)


def box(name: str, size, center=(0, 0, 0), col=None, mat=None, fillet: float = 0.0, segments: int = 3):
    sx, sy, sz = (s / 2 for s in size)
    cx, cy, cz = center
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx * 2, sy * 2, sz * 2), verts=bm.verts)
    bmesh.ops.translate(bm, vec=(cx, cy, cz), verts=bm.verts)
    obj = from_bmesh(name, bm, col, mat)
    if fillet:
        bevel(obj, fillet, segments)
    return obj


def cylinder(name: str, radius: float, z0: float, z1: float, segments: int = 48, col=None, mat=None,
             chamfer: float = 0.0):
    c = min(chamfer, radius * 0.4, abs(z1 - z0) * 0.4)
    prof = [(0, z0), (radius - c, z0), (radius, z0 + c), (radius, z1 - c), (radius - c, z1), (0, z1)]
    return lathe(name, prof, segments, col, mat)


def place(obj, loc=(0, 0, 0), rot=(0, 0, 0)):
    obj.location = loc
    obj.rotation_euler = rot
    return obj


def transform_mesh(obj, matrix):
    obj.data.transform(matrix)
    if matrix.to_3x3().determinant() < 0:          # a mirror turns the mesh inside-out
        obj.data.flip_normals()
    obj.data.update()
    return obj


def aim_z(obj, direction, origin=(0, 0, 0)):
    """Bake a rotation into the mesh so its local +Z points along `direction`, then move it to `origin`."""
    d = Vector(direction).normalized()
    q = Vector((0, 0, 1)).rotation_difference(d)
    transform_mesh(obj, Matrix.Translation(Vector(origin)) @ q.to_matrix().to_4x4())
    return obj


# ---------------------------------------------------------------- outlines (for prisms)

def arc(cx, cy, r, a0, a1, steps=16):
    """Points on an arc, angles in degrees, inclusive."""
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / steps)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / steps))) for i in range(steps + 1)]


def circle(cx, cy, r, steps=48):
    return arc(cx, cy, r, 0, 360, steps)[:-1]


def tangent_hull(c0, r0, c1, r1, steps=24):
    """Outline of two circles joined by their outer tangents (a con-rod or rocker silhouette).
    c0/c1 lie on the Y axis direction; works for any two centres."""
    (x0, y0), (x1, y1) = c0, c1
    dx, dy = x1 - x0, y1 - y0
    d = math.hypot(dx, dy)
    base = math.degrees(math.atan2(dy, dx))
    phi = math.degrees(math.acos(max(-1.0, min(1.0, (r0 - r1) / d))))
    pts = arc(x0, y0, r0, base + phi, base + 360 - phi, steps)
    pts += arc(x1, y1, r1, base - phi, base + phi, max(6, steps // 2))
    return pts


# ---------------------------------------------------------------- swept tubes

def sweep(name: str, points, radius: float, col=None, mat=None, segments: int = 24, caps: bool = True,
          radii=None, resolution: int = 6):
    """A round tube through `points` (a port, a pipe, a spring), as a closed mesh."""
    cu = bpy.data.curves.new(name + "_c", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = max(2, segments // 4)
    cu.use_fill_caps = caps
    cu.resolution_u = resolution
    sp = cu.splines.new("POLY" if resolution <= 1 else "BEZIER")
    if sp.type == "BEZIER":
        sp.bezier_points.add(len(points) - 1)
        for i, p in enumerate(points):
            bp = sp.bezier_points[i]
            bp.co = p
            bp.handle_left_type = bp.handle_right_type = "AUTO"
            if radii:
                bp.radius = radii[i] / radius
    else:
        sp.points.add(len(points) - 1)
        for i, p in enumerate(points):
            sp.points[i].co = (*p, 1.0)
            if radii:
                sp.points[i].radius = radii[i] / radius
    tmp = bpy.data.objects.new(name + "_tmp", cu)
    bpy.context.scene.collection.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(tmp, do_unlink=True)
    bpy.data.curves.remove(cu)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bpy.data.meshes.remove(me)
    obj = from_bmesh(name, bm, col, mat)
    obj.data.shade_smooth()
    return obj


def helix(radius: float, pitch: float, turns: float, z0: float = 0.0, steps_per_turn: int = 24,
          closed_ends: bool = True):
    """Points of a coil spring; closed_ends squares the first and last turn like a real valve spring."""
    pts = []
    n = int(turns * steps_per_turn)
    for i in range(n + 1):
        u = i / steps_per_turn
        a = u * math.tau
        z = z0 + (_closed_pitch(u, turns, pitch) if closed_ends else u * pitch)
        pts.append((radius * math.cos(a), radius * math.sin(a), z))
    return pts


def _closed_pitch(u: float, turns: float, pitch: float) -> float:
    """Height along a spring whose first and last turns are flat (ground ends)."""
    end = 0.85
    body = max(turns - 2 * end, 0.1)
    if u < end:
        return u * pitch * 0.25
    if u > turns - end:
        return end * pitch * 0.25 + body * pitch + (u - (turns - end)) * pitch * 0.25
    return end * pitch * 0.25 + (u - end) * pitch


# ---------------------------------------------------------------- fasteners

def hex_bolt(name: str, d: float, length: float, col=None, mat=None, head: bool = True):
    """A hex-head bolt along +Z, head at z=0 sitting on the surface, shank going down to -length."""
    s = d * 1.6                       # across flats
    hh = d * 0.65
    bm = bmesh.new()
    r = s / 2 / math.cos(math.pi / 6)
    ring0 = [bm.verts.new((r * math.cos(math.pi / 6 + i * math.pi / 3), r * math.sin(math.pi / 6 + i * math.pi / 3), 0))
             for i in range(6)]
    f = bm.faces.new(ring0)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    bmesh.ops.translate(bm, verts=[e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)], vec=(0, 0, hh))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    head_obj = from_bmesh(name + "_h", bm, col, mat)
    bevel(head_obj, d * 0.08, 2, 30)
    washer = cylinder(name + "_w", s * 0.62, -0.0001, d * 0.12, 32, col, mat, chamfer=d * 0.03)
    shank = cylinder(name + "_s", d / 2, -length, 0.0, 20, col, mat, chamfer=d * 0.1)
    return join(name, [head_obj, washer, shank], col)
