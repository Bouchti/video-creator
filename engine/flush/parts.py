"""
Shared parts for the "where your toilet water goes" cutaway film (runs inside Blender).

Conventions (every station follows them):
  - Z is up, metres. The section plane is y = 0: the camera sits at y < 0 and looks +Y at the cut face,
    so everything that is cut keeps only its y >= 0 half.
  - A pipe "cut lengthwise" is a swept half-annulus (`half_pipe`) plus a swept water body (`pipe_water`)
    whose UV u runs along the pipe, so a scrolling texture shows the flow direction.
  - "front" sweeps lie in the x-z plane and are cut by y = 0; "top" sweeps lie in the x-y plane and are cut
    open from above (pipes in an open trench, seen from the air).
"""
import math
import os
import random

import bmesh
import bpy
from mathutils import Vector

from engine import toy
from engine.director import lib

V = Vector


# ------------------------------------------------------------------ materials

def _driver(socket, index, expr):
    """Drive one component of a node socket's default_value from the frame (simple expression: no
    script auto-exec needed)."""
    fc = socket.driver_add("default_value", index) if index is not None else socket.driver_add("default_value")
    fc.driver.type = "SCRIPTED"
    fc.driver.expression = expr
    return fc


def water(name, color, foam="#F2F8FF", speed=0.6, foam_amount=0.35, scale=(2.0, 6.0, 6.0), coord="UV",
          rough=0.06, emission=0.0, swirl=0.0, axis=0, density=None, glass=None):
    """Opaque, glossy water whose foam streaks scroll along +u (UV) or +x (object; `axis` picks another) at
    `speed` m/s.
    swirl > 0 rotates the pattern around the object's Z instead (the bowl of a flushing toilet)."""
    if name in lib._mats:
        return lib._mats[name]
    mat = bpy.data.materials.new(name)
    nt, bsdf = lib._bsdf(mat)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    nt.links.new(tc.outputs[coord], mp.inputs["Vector"])
    if swirl:
        _driver(mp.inputs["Rotation"], 2, f"-frame*{swirl / 30:.5f}")
    else:
        _driver(mp.inputs["Location"], axis, f"-frame*{speed / 30:.5f}")
    sc = nt.nodes.new("ShaderNodeMapping")
    sc.inputs["Scale"].default_value = scale
    nt.links.new(mp.outputs["Vector"], sc.inputs["Vector"])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.6
    noise.inputs["Detail"].default_value = 6.0
    noise.inputs["Roughness"].default_value = 0.62
    nt.links.new(sc.outputs["Vector"], noise.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 1.0 - foam_amount * 0.55
    ramp.color_ramp.elements[1].position = min(1.0, 1.0 - foam_amount * 0.55 + 0.16)
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (*lib.hexrgb(color), 1)
    mix.inputs["B"].default_value = (*lib.hexrgb(foam), 1)
    nt.links.new(ramp.outputs["Color"], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Coat Weight"].default_value = 0.6
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    bump.inputs["Distance"].default_value = 0.02
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*lib.hexrgb(color), 1)
        bsdf.inputs["Emission Strength"].default_value = emission
    if PATH_TRACED:
        # real water: clear and refractive where it is not foam (Cycles); Eevee keeps the opaque glossy look.
        # The colour is then only a light tint, and the ripples bend what is seen through it.
        bsdf.inputs["Roughness"].default_value = 0.015
        bsdf.inputs["Coat Weight"].default_value = 0.0
        bump.inputs["Strength"].default_value = 0.3
        if "fall" not in name and "swirl" not in name and density != 0:
            # depth colour: thin water stays clear, deep water turns blue (needs a closed mesh: all bodies are)
            vol = nt.nodes.new("ShaderNodeVolumeAbsorption")
            vol.inputs["Color"].default_value = (*lib.hexrgb(color), 1)
            vol.inputs["Density"].default_value = WATER_DENSITY if density is None else density
            out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
            nt.links.new(vol.outputs["Volume"], out.inputs["Volume"])
        inv = nt.nodes.new("ShaderNodeMath")
        inv.operation = "MULTIPLY_ADD"
        nt.links.new(ramp.outputs["Color"], inv.inputs[0])
        g = GLASS if glass is None else glass
        inv.inputs[1].default_value = -g
        inv.inputs[2].default_value = g
        nt.links.new(inv.outputs["Value"], bsdf.inputs["Transmission Weight"])
        bsdf.inputs["IOR"].default_value = 1.33
    lib._mats[name] = mat
    return mat


PATH_TRACED = os.getenv("CUT_ENGINE", "eevee").lower() == "cycles"
GLASS = float(os.getenv("CUT_WATER_GLASS", "0.92"))
WATER_DENSITY = float(os.getenv("CUT_WATER_DENSITY", "0.5"))


def water_section(name, color, deep):
    """The flat cut face of a water body: lighter at the top, deeper colour below (object Z)."""
    if name in lib._mats:
        return lib._mats[name]
    mat = bpy.data.materials.new(name)
    nt, bsdf = lib._bsdf(mat)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.0
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -1.0
    mr.inputs["From Max"].default_value = 0.3
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (*lib.hexrgb(deep), 1)
    mix.inputs["B"].default_value = (*lib.hexrgb(color), 1)
    nt.links.new(mr.outputs["Result"], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.12
    bsdf.inputs["Coat Weight"].default_value = 0.4
    if PATH_TRACED:
        bsdf.inputs["Transmission Weight"].default_value = GLASS * 0.6
        bsdf.inputs["IOR"].default_value = 1.33
        bsdf.inputs["Roughness"].default_value = 0.03
    lib._mats[name] = mat
    return mat


def water_glass(name, color, alpha=0.5, foam=None, speed=0.2, rough=0.04, density=0):
    """See-through water for the inside of tanks (the scraper, bubbles and lamps stay visible). Tanks are metres
    deep, so their absorption is far lighter than a pipe's, or they render black."""
    if name in lib._mats:
        return lib._mats[name]
    mat = water(name, color, foam or color, speed=speed, foam_amount=0.15 if foam else 0.0, coord="Object",
                rough=rough, density=density)
    nt, bsdf = lib._bsdf(mat)
    if PATH_TRACED:
        # see-through without refraction: refracting water blocks the sun (no caustics), and metres of it
        # leave a tank's inside black; plain transparency keeps it lit, like the reference's tanks
        for link in list(bsdf.inputs["Transmission Weight"].links):
            nt.links.remove(link)
        bsdf.inputs["Transmission Weight"].default_value = 0.0
    bsdf.inputs["Alpha"].default_value = alpha
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"
    if hasattr(mat, "use_transparency_overlap"):
        mat.use_transparency_overlap = False
    return mat


def pvc():
    return lib.flat("pvc_grey", lib.hexrgb("#C3C7CA"), rough=0.3, coat=0.3)


def pvc_cut():
    return lib.flat("pvc_cut", lib.hexrgb("#E4E6E7"), rough=0.6)


def porcelain():
    return lib.flat("porcelain", lib.hexrgb("#F4F4F1"), rough=0.12, coat=0.8)


def porcelain_cut():
    return lib.flat("porcelain_cut", lib.hexrgb("#E2DED6"), rough=0.7)


def soil():
    return lib.material("Ground106", scale=0.7, tint=(0.92, 0.84, 0.76), name="soil")


def soil_deep():
    return lib.material("Ground103", scale=0.6, tint=(0.78, 0.68, 0.6), name="soil_deep")


def tiles(name="tiles_white", hexc="#F1F0EC", grout="#B9B6AE", size=0.2):
    """Glossy square tiles with grout lines (procedural brick texture, no offset)."""
    if name in lib._mats:
        return lib._mats[name]
    mat = bpy.data.materials.new(name)
    nt, bsdf = lib._bsdf(mat)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.offset = 0.0
    br.inputs["Scale"].default_value = 1.0 / size
    br.inputs["Mortar Size"].default_value = 0.012
    br.inputs["Brick Width"].default_value = 1.0
    br.inputs["Row Height"].default_value = 1.0
    br.inputs["Color1"].default_value = (*lib.hexrgb(hexc), 1)
    br.inputs["Color2"].default_value = (*lib.hexrgb(hexc), 1)
    br.inputs["Mortar"].default_value = (*lib.hexrgb(grout), 1)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    # walls face y, floors face z: project x with (y + z) so both read as squares
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "ADD"
    nt.links.new(sep.outputs["Y"], add.inputs[0])
    nt.links.new(sep.outputs["Z"], add.inputs[1])
    nt.links.new(sep.outputs["X"], comb.inputs["X"])
    nt.links.new(add.outputs["Value"], comb.inputs["Y"])
    nt.links.new(comb.outputs["Vector"], br.inputs["Vector"])
    nt.links.new(br.outputs["Color"], bsdf.inputs["Base Color"])
    rough = nt.nodes.new("ShaderNodeMapRange")
    rough.inputs["To Min"].default_value = 0.12
    rough.inputs["To Max"].default_value = 0.7
    nt.links.new(br.outputs["Fac"], rough.inputs["Value"])
    nt.links.new(rough.outputs["Result"], bsdf.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.4
    bump.invert = True
    nt.links.new(br.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    lib._mats[name] = mat
    return mat


def grass_top():
    return lib.material("Grass004", scale=0.7, tint=(0.85, 1.0, 0.75), name="grass_top")


def concrete():
    return lib.material("Concrete034", scale=0.6, tint=(0.68, 0.67, 0.65), name="concrete")


def pipe_concrete():
    return lib.material("Concrete034", scale=0.5, tint=(0.95, 0.94, 0.92), name="pipe_concrete")


def concrete_old():
    return lib.material("Concrete031", scale=0.45, name="concrete_old")


def asphalt():
    return lib.material("Asphalt031", scale=0.45, tint=(0.8, 0.8, 0.82), name="asphalt")


def gravel():
    return lib.material("Gravel023", scale=1.2, name="gravel")


def steel():
    return lib.flat("steel", lib.hexrgb("#8A9196"), rough=0.35, metallic=0.9)


def dark_steel():
    return lib.flat("dark_steel", lib.hexrgb("#3E4448"), rough=0.4, metallic=0.85)


DIRTY = ("#B2DCEB", "#F4FAFC", "#7AB2C8")     # sewage: grey-green, pale foam, deep
CLEAN = ("#C2EBF8", "#F7FDFF", "#86C8E0")     # treated: clear blue
TOILET = ("#6CB4F5", "#E8F5FF", "#3F86D6")    # the blue toilet water


def dirty_flow(speed=0.8, name="dirty_flow"):
    return water(name, DIRTY[0], DIRTY[1], speed=speed, foam_amount=0.55)


def clean_flow(speed=0.8, name="clean_flow"):
    return water(name, CLEAN[0], CLEAN[1], speed=speed, foam_amount=0.3)


# ------------------------------------------------------------------ sweeps (pipes cut open lengthwise)

def rounded(pts, radius=0.25, steps=8):
    """Polyline with every inner corner replaced by an arc (pipe elbows)."""
    pts = [V(p) for p in pts]
    if len(pts) < 3 or radius <= 0:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        d1, d2 = (b - a), (c - b)
        r = min(radius, d1.length * 0.45, d2.length * 0.45)
        p0, p1 = b - d1.normalized() * r, b + d2.normalized() * r
        for k in range(steps + 1):
            t = k / steps
            out.append((1 - t) ** 2 * p0 + 2 * (1 - t) * t * b + t ** 2 * p1)    # quadratic Bezier
    out.append(pts[-1])
    return out


def resample(pts, step):
    pts = [V(p) for p in pts]
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.ceil((b - a).length / step)))
        for k in range(1, n + 1):
            out.append(a.lerp(b, k / n))
    return out


def _frames(pts, mode):
    """Per point: (tangent, A, B). A is the axis whose positive half is KEPT (into the scene for "front",
    down for "top"); B completes the frame (up for "front", sideways for "top")."""
    out = []
    for i, p in enumerate(pts):
        a = pts[max(0, i - 1)]
        b = pts[min(len(pts) - 1, i + 1)]
        t = (b - a).normalized()
        if mode == "front":
            A = V((0, 1, 0))
            B = t.cross(A).normalized()
        else:
            A = V((0, 0, -1))
            B = V((0, 0, 1)).cross(t).normalized()
        out.append((t, A, B))
    return out


def sweep(name, pts, profile, mode="front", mats=(), mat_of_edge=None, caps=True, parent=None, smooth=True):
    """Sweep a closed 2D profile [(a, b), ...] along pts. mat_of_edge(k) -> material index of the profile
    edge k -> k+1. UV u = arc length along the path (metres), v = profile position."""
    frames = _frames(pts, mode)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    rings = []
    for p, (_t, A, B) in zip(pts, frames):
        rings.append([bm.verts.new(p + A * a + B * b) for a, b in profile])
    s = [0.0]
    for a, b in zip(pts, pts[1:]):
        s.append(s[-1] + (b - a).length)
    n = len(profile)
    for i in range(len(rings) - 1):
        for k in range(n):
            k2 = (k + 1) % n
            f = bm.faces.new((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]))
            f.material_index = mat_of_edge(k) if mat_of_edge else 0
            f.smooth = smooth
            for loop, (u, v) in zip(f.loops, ((s[i], k / n), (s[i], k2 / n), (s[i + 1], k2 / n), (s[i + 1], k / n))):
                loop[uv].uv = (u, v)
    if caps:
        for ring, last in ((rings[0], False), (rings[-1], True)):
            try:
                f = bm.faces.new(ring if last else list(reversed(ring)))
                f.material_index = mat_of_edge(-1) if mat_of_edge else 0
            except ValueError:
                pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = lib.mesh_from_bm(name, bm, None, parent)
    for m in mats:
        ob.data.materials.append(m)
    return ob


def _arc(r, a0, a1, n):
    return [(r * math.cos(a0 + (a1 - a0) * k / n), r * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n + 1)]


def solid_tube(name, pts, radius, mat=None, parent=None, bend=None, step=0.05, n=24):
    """A closed (manifold) round tube along pts: a clean cutter for exact booleans."""
    path = resample(rounded(pts, bend if bend is not None else radius * 3), step)
    prof = _arc(radius, math.pi / n, 2 * math.pi + math.pi / n, n)[:-1]     # no vertex on the cut plane
    return sweep(name, path, prof, "front", mats=(mat,) if mat else (), parent=parent)


def half_pipe(name, pts, radius, wall=None, mode="front", mat=None, cut_mat=None, parent=None, bend=None,
              step=0.08, n=20):
    """A pipe cut open lengthwise: the half behind the cut (front) or below the axis (top)."""
    wall = wall or max(0.006, radius * 0.1)
    path = resample(rounded(pts, bend if bend is not None else radius * 3), step)
    outer = _arc(radius, -math.pi / 2, math.pi / 2, n)
    inner = list(reversed(_arc(radius - wall, -math.pi / 2, math.pi / 2, n)))
    prof = outer + inner
    # edges: outer arc 0..n-1 (shell), n (cut face top), inner arc, last (cut face bottom)
    cut_edges = {n, 2 * n + 1}

    def mat_of(k):
        return 1 if (k in cut_edges or k == -1) else 0
    return sweep(name, path, prof, mode, mats=(mat or pvc(), cut_mat or pvc_cut()), mat_of_edge=mat_of,
                 parent=parent)


def pipe_water(name, pts, radius, level=0.0, mode="front", mat=None, section_mat=None, parent=None, bend=None,
               step=0.08, n=16):
    """The water inside a half pipe. level is the water surface, as a fraction of the inner radius above
    the axis (front: -1 = empty, 0 = half full, 1 = full; top: 1 = brim of the cut, 0 = half full)."""
    r = radius * 0.985
    path = resample(rounded(pts, bend if bend is not None else radius * 3 / 0.9), step)
    if mode == "front":
        h = max(-0.95, min(0.98, level)) * r
        top = math.asin(h / r)
        prof = _arc(r, -math.pi / 2, top, n) + [(0.0, h)]
        # edges: arc (wet wall) 0..n-1, n = surface, n+1 = the cut face (section)
        surf, cut = {n}, {n + 1}
    else:
        depth = (1.0 - max(0.02, min(1.0, level))) * r      # distance of the surface below the cut (axis)
        th = math.acos(min(0.999, depth / r))
        prof = _arc(r, -th, th, n)
        surf, cut = {n}, set()

    def mat_of(k):
        return 1 if (k in cut or k == -1) else 0
    flow = mat or dirty_flow()
    sec = section_mat or water_section("water_cut_dirty", DIRTY[0], DIRTY[2])
    return sweep(name, path, prof, mode, mats=(flow, sec), mat_of_edge=mat_of, parent=parent)


def stream(name, start, velocity, length_s=0.5, radius=0.05, mat=None, parent=None, gravity=9.81, n=12, flat=1.0):
    """A falling stream (a parabola) as a tapered tube; its flow scrolls along the arc."""
    pts = []
    for k in range(n + 1):
        t = length_s * k / n
        pts.append(V(start) + V(velocity) * t + V((0, 0, -0.5 * gravity * t * t)))
    frames = []
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    rings, s = [], [0.0]
    for a, b in zip(pts, pts[1:]):
        s.append(s[-1] + (b - a).length)
    m = 12
    for i, p in enumerate(pts):
        a, b = pts[max(0, i - 1)], pts[min(n, i + 1)]
        t = (b - a).normalized()
        side = t.cross(V((0, 0, 1))) if abs(t.z) < 0.95 else V((1, 0, 0))
        side.normalize()
        up = side.cross(t).normalized()
        r = radius * (1.0 + 0.35 * i / n)
        rings.append([bm.verts.new(p + side * math.cos(2 * math.pi * k / m) * r * flat
                                   + up * math.sin(2 * math.pi * k / m) * r) for k in range(m)])
        frames.append(t)
    for i in range(n):
        for k in range(m):
            k2 = (k + 1) % m
            f = bm.faces.new((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]))
            f.smooth = True
            for loop, (u, v) in zip(f.loops, ((s[i], k / m), (s[i], k2 / m), (s[i + 1], k2 / m), (s[i + 1], k / m))):
                loop[uv].uv = (u, v)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = lib.mesh_from_bm(name, bm, mat or dirty_flow(1.6, "dirty_fall"), parent)
    return ob, pts[-1]


def fall(name="water_fall", color="#CFEAF4"):
    """A pour: aerated, so mostly white foam over clear water."""
    return water(name, color, "#FFFFFF", speed=2.2, foam_amount=0.85, scale=(5.0, 3.0, 3.0), rough=0.12, glass=0.6)


def foam(name, at, radius, parent=None, seed=1, f0=1, f1=4000, pulse=0.12):
    """A churning white foam patch where a stream lands (lumpy, gently pulsing)."""
    mat = lib.flat("foam", lib.hexrgb("#F4F7F8"), rough=0.5)
    ob = lib.blob(name, radius, mat, at, squash=0.35, seed=seed, parent=parent, lumpy=0.3)
    rnd = random.Random(seed)
    f = f0
    while f < f1:
        k = 1.0 + rnd.uniform(-pulse, pulse)
        lib.key(ob, "scale", f, (k, 1.0 / k, 1.0))
        f += 6
    return ob


# ------------------------------------------------------------------ ground

def soil_block(name, x0, x1, y0, y1, z0, z1, parent=None, deep_below=None, mat=None):
    """A block of earth; with deep_below, the part under that depth uses the darker deep soil."""
    if deep_below is None or deep_below <= z0:
        return lib.box(name, x0, x1, y0, y1, z0, z1, mat or soil(), parent)
    top = lib.box(name, x0, x1, y0, y1, deep_below, z1, mat or soil(), parent)
    lib.box(f"{name}_deep", x0, x1, y0, y1, z0, deep_below + 0.002, soil_deep(), parent)
    return top


_TUFT = []


def tuft():
    if not _TUFT:
        from engine.cutaway import _grass_tuft
        t = _grass_tuft()
        t.scale = (1.6, 1.6, 1.9)
        _TUFT.append(t)
    return _TUFT[0]


def lawn(name, x0, x1, y0, y1, z=0.0, parent=None, density=420, edge_overhang=0.03, slab=0.04, seed=3):
    """Grass: a textured turf slab (its front edge overhangs the cut by a few cm) plus 3D blades."""
    slab_ob = lib.box(f"{name}_turf", x0, x1, y0 - edge_overhang, y1, z - slab, z + 0.005, grass_top(), parent)
    blades = toy.scatter(f"{name}_blades", x0, x1, y0 - edge_overhang * 0.5, y1, tuft(), density, size=1.0,
                         size_random=0.5, z=z, seed=seed)
    if parent is not None:
        blades.parent = parent
    return slab_ob, blades


# ------------------------------------------------------------------ buildings

def house(name, origin, w=7.0, d=6.0, h=2.8, yaw=0.0, parent=None, wall_hex="#EDE3CF", shutter_hex="#4F7FB3"):
    """A small suburban house: plaster walls, red tiled gable roof, windows with blue shutters, a door.
    origin = centre of the footprint at ground level; the ridge runs along the local x axis."""
    root = lib.empty(name, origin, parent)
    root.rotation_euler = (0, 0, math.radians(yaw))
    wall = lib.material("PaintedPlaster017", scale=0.8, tint=lib.hexrgb(wall_hex), name=f"plaster_{wall_hex}")
    roof = lib.material("RoofingTiles006", scale=0.9, tint=(1.0, 0.62, 0.48), name="roof_tiles")
    trim = lib.flat("trim_white", lib.hexrgb("#F6F4EE"), 0.4)
    glass = lib.flat("window_glass", lib.hexrgb("#9DB8CC"), 0.05, coat=1.0)
    shutter = lib.flat(f"shutter_{shutter_hex}", lib.hexrgb(shutter_hex), 0.5)
    door = lib.flat("door_wood", lib.hexrgb("#6B4A33"), 0.55)
    lib.box(f"{name}_base", -w / 2 - 0.05, w / 2 + 0.05, -d / 2 - 0.05, d / 2 + 0.05, -0.05, 0.35, concrete(), root)
    lib.box(f"{name}_walls", -w / 2, w / 2, -d / 2, d / 2, 0.3, h, wall, root)
    # gable roof as a prism with eaves
    ov, rise = 0.45, d * 0.38
    bm = bmesh.new()
    xs = (-w / 2 - ov, w / 2 + ov)
    ring = []
    for x in xs:
        ring.append([bm.verts.new((x, -d / 2 - ov, h - 0.12)), bm.verts.new((x, 0, h + rise)),
                     bm.verts.new((x, d / 2 + ov, h - 0.12))])
    a, b = ring
    bm.faces.new((a[0], b[0], b[1], a[1]))
    bm.faces.new((a[1], b[1], b[2], a[2]))
    # thickness: an under-side
    th = 0.12
    under = [[bm.verts.new(v.co + V((0, 0, -th))) for v in r] for r in ring]
    c, e = under
    bm.faces.new((c[1], e[1], e[0], c[0]))
    bm.faces.new((c[2], e[2], e[1], c[1]))
    for r, u in ((a, c), (b, e)):
        bm.faces.new((r[0], r[1], r[2], u[2], u[1], u[0]))
    bm.faces.new((a[0], c[0], e[0], b[0]))
    bm.faces.new((b[2], e[2], c[2], a[2]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    lib.mesh_from_bm(f"{name}_roof", bm, roof, root)
    # gable wall triangles
    for sx in (-1, 1):
        bm = bmesh.new()
        x = sx * w / 2
        vs = [bm.verts.new((x, -d / 2, h)), bm.verts.new((x, d / 2, h)), bm.verts.new((x, 0, h + rise - 0.1))]
        bm.faces.new(vs)
        lib.mesh_from_bm(f"{name}_gable{sx}", bm, wall, root)
    # windows + shutters on the front (-y) and back walls, a door on the front
    for side in (-1, 1):
        y = side * (d / 2 + 0.01)
        for k, x in enumerate((-w * 0.3, 0.0, w * 0.3)):
            if side == -1 and k == 1:
                lib.box(f"{name}_door", x - 0.45, x + 0.45, y - 0.04 * side, y + 0.02 * side, 0.35, 2.3, door, root)
                lib.box(f"{name}_doorframe", x - 0.55, x + 0.55, y - 0.02 * side, y, 0.33, 2.4, trim, root)
                continue
            z0, z1 = 1.0, 2.15
            lib.box(f"{name}_win{side}{k}", x - 0.5, x + 0.5, y - 0.03 * side, y, z0, z1, glass, root)
            lib.box(f"{name}_sill{side}{k}", x - 0.6, x + 0.6, y - 0.08 * side, y, z0 - 0.08, z0, trim, root)
            for sx in (-1, 1):
                lib.box(f"{name}_sh{side}{k}{sx}", x + sx * 0.55, x + sx * 0.95, y - 0.05 * side, y - 0.01 * side,
                        z0 - 0.02, z1 + 0.02, shutter, root)
    for o in root.children_recursive:
        o.location = o.location        # (keep local transforms under the rotated root)
    return root


# ------------------------------------------------------------------ flow arrows

def arrow(name, at, direction=(1, 0, 0), size=0.12, parent=None, normal=(0, -1, 0)):
    """A flat white chevron arrow facing the camera (normal), pointing along `direction`."""
    mat = lib.flat("arrow_white", (0.95, 0.95, 0.95), 0.4, emission=0.6)
    d = V(direction).normalized()
    nrm = V(normal).normalized()
    s = d.cross(nrm).normalized()
    pts2 = [(-0.5, 0.18), (0.1, 0.18), (0.1, 0.42), (0.6, 0.0), (0.1, -0.42), (0.1, -0.18), (-0.5, -0.18)]
    bm = bmesh.new()
    vs = [bm.verts.new(V(at) + (d * x + s * y) * size) for x, y in pts2]
    bm.faces.new(vs)
    ob = lib.mesh_from_bm(name, bm, mat, parent)
    ob.visible_shadow = False
    return ob


# ------------------------------------------------------------------ solids for tanks, channels, ground

def prism(name, outline_xz, y0, y1, mat=None, parent=None, cut_mat=None):
    """Extrude a closed x-z outline from y0 to y1 (sloped ground, channel sections). The y0 face takes
    cut_mat (it is usually the section face)."""
    bm = bmesh.new()
    f0 = [bm.verts.new((x, y0, z)) for x, z in outline_xz]
    f1 = [bm.verts.new((x, y1, z)) for x, z in outline_xz]
    n = len(outline_xz)
    for k in range(n):
        bm.faces.new((f0[k], f0[(k + 1) % n], f1[(k + 1) % n], f1[k]))
    front = bm.faces.new(list(reversed(f0)))
    front.material_index = 1 if cut_mat else 0
    bm.faces.new(f1)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = lib.mesh_from_bm(name, bm, None, parent)
    ob.data.materials.append(mat)
    if cut_mat:
        ob.data.materials.append(cut_mat)
    return ob


def revolve_half(name, profile_rz, center=(0, 0, 0), mat=None, cut_mat=None, parent=None, n=48, full=False,
                 a0=0.0):
    """Revolve a closed r-z outline about the vertical axis through center. Half: angles 0..pi, i.e. the
    y >= 0 half, with flat cut faces on y = 0 (cut_mat). full=True makes a whole ring (no cut faces)."""
    bm = bmesh.new()
    span = 2 * math.pi if full else math.pi
    steps = n if full else n // 2
    cx, cy, cz = center
    rings = []
    for k in range(steps + (0 if full else 1)):
        th = a0 + span * k / steps
        c, s = math.cos(th), math.sin(th)
        # a radius of exactly 0 stacks every ring's vertex on the axis: the cut faces then fail to build and
        # the mesh is left open (a refractive volume that never ends renders black)
        rings.append([bm.verts.new((cx + max(r, 0.003) * c, cy + max(r, 0.003) * s, cz + z))
                      for r, z in profile_rz])
    m = len(profile_rz)
    count = len(rings) if full else len(rings) - 1
    for i in range(count):
        a, b = rings[i], rings[(i + 1) % len(rings)]
        for k in range(m):
            f = bm.faces.new((a[k], a[(k + 1) % m], b[(k + 1) % m], b[k]))
            f.smooth = True
    if not full:
        for ring in (rings[0], rings[-1]):
            try:
                f = bm.faces.new(ring)
                f.material_index = 1 if cut_mat else 0
            except ValueError:
                pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = lib.mesh_from_bm(name, bm, None, parent)
    ob.data.materials.append(mat)
    if cut_mat:
        ob.data.materials.append(cut_mat)
    return ob


def cycle_rise(ob, z0, z1, period, phase, axis=2):
    """Move ob linearly from z0 to z1 every `period` frames, forever (an F-curve with a Cycles modifier)."""
    loc = list(ob.location)
    loc[axis] = z0
    ob.location = loc
    ob.keyframe_insert("location", index=axis, frame=phase)
    loc[axis] = z1
    ob.location = loc
    ob.keyframe_insert("location", index=axis, frame=phase + period)
    for fc in lib.fcurves(ob):
        if fc.data_path == "location" and fc.array_index == axis:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
            if not fc.modifiers:
                fc.modifiers.new("CYCLES")


def bubbles(name, x0, x1, y0, y1, z0, z1, count, parent=None, seed=3, radius=(0.012, 0.03), period=(45, 80)):
    mat = lib.flat("bubble", lib.hexrgb("#F4FAFF"), 0.2, emission=0.35)
    rnd = random.Random(seed)
    out = []
    for k in range(count):
        r = rnd.uniform(*radius)
        b = lib.blob(f"{name}{k}", r, mat, (rnd.uniform(x0, x1), rnd.uniform(y0, y1), z0), squash=0.85,
                     seed=k, parent=parent, lumpy=0.05, subdiv=2)
        b.visible_shadow = False
        per = rnd.randint(*period)
        cycle_rise(b, z0, z1, per, -rnd.randint(0, per))
        out.append(b)
    return out


def tree(name, at, h=4.0, parent=None, seed=1):
    """A soft broadleaf tree: a tapered trunk and lumpy canopy blobs."""
    rnd = random.Random(seed)
    root = lib.empty(name, at, parent)
    bark = lib.flat("bark", lib.hexrgb("#5A4632"), 0.8)
    leaves = lib.material("Grass001", scale=2.5, tint=(0.75, 0.95, 0.7), name="leaves")
    lib.tube(f"{name}_trunk", [(0, 0, 0), (0.05, 0, h * 0.55)], 0.12 * h / 4, bark, root)
    for k in range(5):
        lib.blob(f"{name}_leaf{k}", h * rnd.uniform(0.2, 0.3), leaves,
                 (rnd.uniform(-0.5, 0.5) * h * 0.25, rnd.uniform(-0.5, 0.5) * h * 0.25,
                  h * rnd.uniform(0.6, 0.85)), squash=0.85, seed=seed * 10 + k, parent=root, lumpy=0.25)
    return root


def sweep_box_cutter(name, pts, half_w, below, above, parent=None, mode="top"):
    """A closed box-section cutter swept along pts (an open trench that follows a sloped pipe)."""
    prof = [(-above, -half_w), (below, -half_w), (below, half_w), (-above, half_w)]
    return sweep(name, resample(pts, 0.25), prof, mode, parent=parent, smooth=False)


def cylinder(name, center_xy, r, z0, z1, mat=None, parent=None, n=48):
    """A closed cylinder rotated half a segment, so no vertex lies on the section plane (clean booleans)."""
    bpy.ops.mesh.primitive_cylinder_add(vertices=n, radius=r, depth=z1 - z0,
                                        location=(center_xy[0], center_xy[1], (z0 + z1) / 2),
                                        rotation=(0, 0, math.pi / n))
    ob = bpy.context.active_object
    ob.name = name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if mat is not None:
        ob.data.materials.append(mat)
    if parent is not None:
        ob.parent = parent
    return ob


def ride(ob, path, s, e, speed, offset=0.0, normal_offset=(0, 0, 0), step=2):
    """Key ob along a polyline at `speed` m/s from frame s to e (wrapping), hidden outside [s, e]."""
    path = [V(p) for p in path]
    L = sum((b - a).length for a, b in zip(path, path[1:]))
    lib.visible(ob, 1, False)
    lib.visible(ob, s, True)
    lib.visible(ob, e + 1, False)
    for f in range(s, e + 1, step):
        d = ((f - s) / 30.0 * speed + offset) % L
        p = path[-1]
        for a, b in zip(path, path[1:]):
            seg = (b - a).length
            if d <= seg:
                p = a.lerp(b, d / seg)
                break
            d -= seg
        lib.key(ob, "location", f, tuple(p + V(normal_offset)), interp="LINEAR")
