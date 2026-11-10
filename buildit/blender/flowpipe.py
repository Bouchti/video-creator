"""
Pipes that show their flow (runs inside Blender): a round tube with a UV map whose U is the arc length in metres,
so materials.flow_pipe() can run dashes along it, and a router that lays a pipe between two ports along the
machine's surfaces with rounded bends (no pipes flying through the air).

    pts = route(a, da, b, db, plane_y)       # Manhattan path hugging the machine, fillets at the corners
    obj = tube("conn_x", pts, 0.014, mat)   # obj["flow_on"], obj["flow_phase"], obj["flow_col"] drive the dashes
"""
from __future__ import annotations

import math

import bmesh
from mathutils import Vector

from cutaway.blender import geo


def _dedupe(pts, eps=1e-4):
    out = []
    for p in pts:
        if not out or (p - out[-1]).length > eps:
            out.append(p)
    # drop collinear middles
    keep = [out[0]]
    for i in range(1, len(out) - 1):
        a, b, c = keep[-1], out[i], out[i + 1]
        if (b - a).length > eps and (c - b).length > eps and (b - a).normalized().dot((c - b).normalized()) > 0.9999:
            continue
        keep.append(b)
    if len(out) > 1:
        keep.append(out[-1])
    return keep


def fillet(pts, radius=0.05, steps=7):
    """Round every corner of a polyline with a quadratic arc."""
    pts = _dedupe([Vector(p) for p in pts])
    if len(pts) < 3:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        r = min(radius, (a - b).length * 0.45, (c - b).length * 0.45)
        p1 = b + (a - b).normalized() * r
        p2 = b + (c - b).normalized() * r
        for k in range(steps + 1):
            u = k / steps
            out.append((1 - u) ** 2 * p1 + 2 * (1 - u) * u * b + u * u * p2)
    out.append(pts[-1])
    return _dedupe(out, 1e-5)


def route(a, da, b, db, plane_y=None, lead=0.06, radius=0.05, x_run=None):
    """A pipe from port a (outward direction da) to port b: out of each port, then along the plane y = plane_y
    (the machine's back) when given, vertical before horizontal, with rounded bends. x_run moves the vertical run
    sideways (to go around a part mounted on the back instead of through it)."""
    a, b = Vector(a), Vector(b)
    a1, b1 = a + Vector(da).normalized() * lead, b + Vector(db).normalized() * lead
    if plane_y is None:
        mid = [Vector((a1.x, a1.y, b1.z))] if abs(a1.z - b1.z) > 1e-3 else []
        pts = [a, a1, *mid, Vector((b1.x, a1.y, b1.z)), b1, b]
    else:
        x = a1.x if x_run is None else x_run
        pts = [a, a1, Vector((a1.x, plane_y, a1.z)), Vector((x, plane_y, a1.z)), Vector((x, plane_y, b1.z)),
               Vector((b1.x, plane_y, b1.z)), b1, b]
        pts = [p for i, p in enumerate(pts) if i == 0 or (p - pts[i - 1]).length > 1e-4]
    return fillet(pts, radius)


def tube(name, pts, radius, mat, segments=14, col=None):
    """A round tube through pts with U = arc length (metres) and V around; open ends (they sit in ports)."""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    tang = []
    for i in range(n):
        t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)])
        tang.append(t.normalized() if t.length > 1e-9 else Vector((0, 0, 1)))
    ref = Vector((0, 0, 1)) if abs(tang[0].z) < 0.9 else Vector((1, 0, 0))
    nrm = (ref - tang[0] * ref.dot(tang[0])).normalized()
    frames = []
    for i in range(n):                                  # parallel transport: no twisting at bends
        if i:
            nrm = nrm - tang[i] * nrm.dot(tang[i])
            nrm = nrm.normalized() if nrm.length > 1e-9 else frames[-1][0]
        frames.append((nrm.copy(), tang[i].cross(nrm).normalized()))
    s = [0.0]
    for i in range(1, n):
        s.append(s[-1] + (pts[i] - pts[i - 1]).length)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    rings = []
    for i, p in enumerate(pts):
        nn, bb = frames[i]
        rings.append([bm.verts.new(p + radius * (math.cos(math.tau * j / segments) * nn +
                                                 math.sin(math.tau * j / segments) * bb)) for j in range(segments)])
    for i in range(n - 1):
        for j in range(segments):
            j2 = (j + 1) % segments
            f = bm.faces.new((rings[i][j], rings[i][j2], rings[i + 1][j2], rings[i + 1][j]))
            for loop, (si, vj) in zip(f.loops, ((i, j), (i, j + 1), (i + 1, j + 1), (i + 1, j))):
                loop[uvl].uv = (s[si], vj / segments)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = geo.from_bmesh(name, bm, col, mat)
    obj.data.shade_smooth()
    obj["flow_on"] = 0.0
    obj["flow_phase"] = 0.0
    obj["flow_col"] = (1.0, 1.0, 1.0)
    obj["length"] = s[-1]
    return obj


def collar(name, at, direction, radius, mat):
    """A short brass union where a pipe enters a port (the joint reads as 'connected')."""
    d = Vector(direction).normalized()
    o = geo.cylinder(name, radius * 1.55, -radius * 1.4, radius * 1.4, 20, mat=mat)
    geo.aim_z(o, d, origin=at)
    return o
