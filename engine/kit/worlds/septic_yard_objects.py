"""
KIT WORLD septic_yard: the objects. One build_<name>() per vocabulary object, each built alone at the world
origin (base centred on (0, 0, 0)) at its real size in metres; engine/kit/worlds/septic_yard.py stages them.
"""
import math
import random

import bmesh
import bpy

from engine import studio as st
from engine import textures as tx
from engine import toy


# ------------------- shared helpers -------------------

def _purge_stale():
    """Each object is built alone (fresh data between builds): drop kit-cached materials that were removed,
    so shared names (concrete, pvc, ...) are rebuilt instead of handing back a dead reference."""
    for cache in (tx._cache, st._cache):
        for key, mat in list(cache.items()):
            try:
                alive = mat is not None and mat.name in bpy.data.materials
            except ReferenceError:
                alive = False
            if not alive:
                cache.pop(key, None)


def _root(name):
    _purge_stale()
    return toy.empty(name, (0, 0, 0))


def _surf(name, hex_a, hex_b, scale=4.0, bump=0.3, rough=0.85, cells=0.0, lo=0.3, hi=0.7):
    """Two-tone surface in OBJECT space (no stretching on long blocks); cells > 0 adds voronoi stones."""
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    mat = bpy.data.materials.new(name)
    bsdf = toy._principled(mat)
    nt = mat.node_tree
    coord = nt.nodes.new("ShaderNodeTexCoord").outputs["Object"]
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = 6.0
    nt.links.new(coord, noise.inputs["Vector"])
    fac = height = noise.outputs["Fac"]
    if cells:
        vor = nt.nodes.new("ShaderNodeTexVoronoi")
        vor.inputs["Scale"].default_value = cells
        nt.links.new(coord, vor.inputs["Vector"])
        m1 = nt.nodes.new("ShaderNodeMath")
        m1.operation = "MULTIPLY"
        nt.links.new(noise.outputs["Fac"], m1.inputs[0])
        m1.inputs[1].default_value = 0.4
        m2 = nt.nodes.new("ShaderNodeMath")
        m2.operation = "MULTIPLY_ADD"
        nt.links.new(vor.outputs["Color"], m2.inputs[0])
        m2.inputs[1].default_value = 0.6
        nt.links.new(m1.outputs[0], m2.inputs[2])
        fac = m2.outputs[0]
        inv = nt.nodes.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        nt.links.new(vor.outputs["Distance"], inv.inputs[1])
        height = inv.outputs[0]
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*toy.srgb(hex_b), 1)
    ramp.color_ramp.elements[1].color = (*toy.srgb(hex_a), 1)
    ramp.color_ramp.elements[0].position = lo
    ramp.color_ramp.elements[1].position = hi
    nt.links.new(fac, ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = bump
    nt.links.new(height, bmp.inputs["Height"])
    nt.links.new(bmp.outputs["Normal"], bsdf.inputs["Normal"])
    toy._set(bsdf, "Roughness", rough)
    return mat


def _fix_normals(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def _layer(name, x0, x1, y0, y1, zbot, ztop, nx, ny, mat, parent, smooth=False):
    """A closed block over [x0,x1] x [y0,y1] between two height functions (soil strata, lumpy sludge)."""
    verts = []
    for fn in (ztop, zbot):
        for j in range(ny + 1):
            for i in range(nx + 1):
                x = x0 + (x1 - x0) * i / nx
                y = y0 + (y1 - y0) * j / ny
                verts.append((x, y, fn(x, y)))
    n = (nx + 1) * (ny + 1)

    def idx(i, j):
        return j * (nx + 1) + i

    faces = []
    for j in range(ny):
        for i in range(nx):
            a, b, c, d = idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)
            faces.append((a, b, c, d))
            faces.append((n + d, n + c, n + b, n + a))
    ring = ([idx(i, 0) for i in range(nx + 1)] + [idx(nx, j) for j in range(1, ny + 1)]
            + [idx(i, ny) for i in range(nx - 1, -1, -1)] + [idx(0, j) for j in range(ny - 1, 0, -1)])
    for k in range(len(ring)):
        a, b = ring[k], ring[(k + 1) % len(ring)]
        faces.append((a, n + a, n + b, b))
    ob = _fix_normals(st.mesh_obj(name, verts, faces, (mat,), smooth=smooth))
    ob.parent = parent
    return ob


def _wave(rng, base, amp):
    """Gently undulating boundary between soil layers."""
    p = [rng.uniform(0, 6.3) for _ in range(3)]
    return lambda x, y: base + amp * (0.6 * math.sin(0.45 * x + p[0]) + 0.3 * math.sin(1.3 * x + 0.7 * y + p[1])
                                      + 0.1 * math.sin(3.1 * x + p[2]))


def _lumps(rng, base, amp, freq=6.0):
    """Lumpy crust (sludge, scum, gravel tops)."""
    terms = [(rng.uniform(0.6, 1.4) * freq, rng.uniform(0.6, 1.4) * freq, rng.uniform(0, 6.3), rng.uniform(0, 6.3))
             for _ in range(4)]
    return lambda x, y: base + amp * sum(math.sin(fx * x + px) * math.cos(fy * y + py)
                                         for fx, fy, px, py in terms) / 4.0


def _torus(name, major, minor, loc, rot, mat, parent, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, major_segments=32,
                                     minor_segments=10, location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = scale
    ob.data.materials.append(mat)
    ob.data.shade_smooth()
    ob.parent = parent
    return ob


def _revolved(name, prof, n=32, jitter=0.0, seed=0, mats=(), smooth=False):
    """A closed solid of revolution about Z through the (radius, z) profile (bottom to top), capped."""
    rng = random.Random(seed)
    verts = []
    for k, (r, z) in enumerate(prof):
        for i in range(n):
            th = 2 * math.pi * i / n
            rr = r + (rng.uniform(-jitter, jitter) if 0 < k < len(prof) - 1 else 0.0)
            verts.append((rr * math.cos(th), rr * math.sin(th), z))
    m = len(prof)
    faces = [(k * n + i, k * n + (i + 1) % n, (k + 1) * n + (i + 1) % n, (k + 1) * n + i)
             for k in range(m - 1) for i in range(n)]
    verts.append((0, 0, prof[0][1]))
    verts.append((0, 0, prof[-1][1]))
    bot, top = len(verts) - 2, len(verts) - 1
    faces += [(bot, (i + 1) % n, i) for i in range(n)]
    faces += [(top, (m - 1) * n + i, (m - 1) * n + (i + 1) % n) for i in range(n)]
    return _fix_normals(st.mesh_obj(name, verts, faces, mats, smooth=smooth))


def _stone_mat():
    _purge_stale()
    return _surf("septic_yard_stone", "#9A9184", "#5E574D", scale=9.0, bump=0.5, rough=0.8)


def _pvc_grey():
    _purge_stale()
    return tx.paint("septic_yard_pvc_grey", "#8E9398", rough=0.4, coat=0.2)


def _pvc_white():
    _purge_stale()
    return tx.paint("septic_yard_pvc_white", "#EEEEEA", rough=0.32, coat=0.3)


def _concrete():
    _purge_stale()
    return st.concrete("septic_yard_concrete", "#A9A59C", lift=0.5, panel=1.2)


# ------------------- the objects -------------------

def build_septic_yard_ground():
    """Backyard block 20 x 6 x 4 m cut open along the front: lawn, topsoil, sandy loam, clay."""
    name = "septic_yard_ground"
    rng = random.Random(11)
    root = _root(name)
    x0, x1, y0, y1 = -10.0, 10.0, -3.0, 3.0
    clay_top = _wave(rng, 1.3, 0.12)
    loam_top = _wave(rng, 2.65, 0.12)
    soil_top = _wave(rng, 3.83, 0.03)
    lawn_top = _wave(rng, 4.0, 0.006)
    floor = lambda x, y: 0.0                                                    # noqa: E731
    strata = [
        ("clay", floor, clay_top, _surf("septic_yard_clay", "#8C7E6E", "#6A5D50", scale=2.5, bump=0.25)),
        ("loam", clay_top, loam_top, _surf("septic_yard_loam", "#C9A979", "#A88757", scale=6.0, bump=0.3)),
        ("topsoil", loam_top, soil_top, _surf("septic_yard_topsoil", "#4E3524", "#2F1F14", scale=7.0, bump=0.4)),
        ("lawn", soil_top, lawn_top, _surf("septic_yard_lawn", "#6BAA45", "#3F7A2A", scale=14.0, bump=0.3)),
    ]
    for part, bot, top, mat in strata:
        _layer(f"{name}_{part}", x0, x1, y0, y1, bot, top, 60, 6, mat, root)
    stone = _stone_mat()
    for k in range(56):                                     # pebbles poking out of the cut face
        r = rng.uniform(0.03, 0.08)
        p = toy.sphere(f"{name}_pebble{k}", r, (rng.uniform(-9.6, 9.6), y0 + r * 0.2, rng.uniform(0.12, 2.5)),
                       scale=(1.0, 0.6, rng.uniform(0.55, 0.85)), mat=stone, parent=root, subdiv=0,
                       segments=10, rings=6)
        p.rotation_euler = (0, rng.uniform(0, 3.1), 0)
    for k in range(9):                                      # thin roots under the lawn
        x = rng.uniform(-9.0, 9.0)
        toy.cylinder(f"{name}_root{k}", 0.008, rng.uniform(0.25, 0.45), (x, y0 + 0.004, 3.68),
                     rotation=(math.pi / 2 * 0 + rng.uniform(-0.4, 0.4), rng.uniform(-0.5, 0.5), 0),
                     mat=_surf("septic_yard_rootwood", "#B9A27E", "#806A4C", scale=20.0, bump=0.1),
                     parent=root, vertices=6)
    verts, faces = [], []                                   # grass blades over the whole lawn
    for k in range(3200):
        x, y = rng.uniform(x0 + 0.05, x1 - 0.05), rng.uniform(y0 + 0.02, y1 - 0.05)
        a = rng.uniform(0, math.pi)
        w, h = 0.012, rng.uniform(0.05, 0.11)
        dx, dy = w * math.cos(a), w * math.sin(a)
        z = lawn_top(x, y) - 0.005
        verts += [(x - dx, y - dy, z), (x + dx, y + dy, z),
                  (x + rng.uniform(-0.03, 0.03), y + rng.uniform(-0.03, 0.03), z + h)]
        faces.append((3 * k, 3 * k + 1, 3 * k + 2))
    grass = st.mesh_obj(f"{name}_grass", verts, faces,
                        (_surf("septic_yard_grass", "#7CC04F", "#3E7A2A", scale=30.0, bump=0.1, rough=0.7),))
    grass.parent = root
    return root


def build_septic_yard_groundwater():
    """The water table: a blue saturated band with a rippled top, its face flush with the cut face."""
    name = "septic_yard_groundwater"
    rng = random.Random(23)
    root = _root(name)
    toy.box(f"{name}_volume", (20.0, 6.0, 1.4), (0, 0, 0.7),
            mat=st.water_volume("septic_yard_groundwater_water", color="#2F7FD0", density=0.6, scatter=0.15),
            parent=root, bevel=0)
    p = [rng.uniform(0, 6.3) for _ in range(4)]

    def top(x, y):
        return (1.42 + 0.035 * math.sin(1.7 * x + p[0]) * math.cos(1.1 * y + p[1])
                + 0.015 * math.sin(4.3 * x + 2.1 * y + p[2]) + 0.01 * math.sin(7.0 * y + p[3]))

    skin = st.water_surface("septic_yard_groundwater_skin", "#5CB4E6")
    nx, ny = 100, 24
    verts = [(-10 + 20 * i / nx, -3 + 6 * j / ny, top(-10 + 20 * i / nx, -3 + 6 * j / ny))
             for j in range(ny + 1) for i in range(nx + 1)]
    faces = [(j * (nx + 1) + i, j * (nx + 1) + i + 1, (j + 1) * (nx + 1) + i + 1, (j + 1) * (nx + 1) + i)
             for j in range(ny) for i in range(nx)]
    st.mesh_obj(f"{name}_ripples", verts, faces, (skin,)).parent = root
    verts, faces = [], []                                   # the band's face on the cut plane
    for i in range(nx + 1):
        x = -10 + 20 * i / nx
        verts += [(x, -3.004, 0.0), (x, -3.004, top(x, -3.0))]
    for i in range(nx):
        faces.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
    st.mesh_obj(f"{name}_face", verts, faces, (skin,)).parent = root
    return root


def build_septic_yard_house():
    """Cut-open bathroom corner: white walls, tiled floor, toilet, sink, grey drain stack through the floor."""
    name = "septic_yard_house"
    root = _root(name)
    wall = tx.paint("septic_yard_house_wall", "#F1EFEA", rough=0.6, coat=0.1)
    ceramic = tx.paint("septic_yard_ceramic", "#F8F8F6", rough=0.12, coat=0.9)
    chrome = tx.metal("septic_yard_chrome", "#D6DADF", rough=0.15)
    pvc = _pvc_grey()
    toy.box(f"{name}_slab", (4.0, 4.0, 0.2), (0, 0, 0.1), mat=_concrete(), parent=root, bevel=0.01)
    toy.box(f"{name}_floor", (3.85, 3.85, 0.02), (0.075, -0.075, 0.21),
            mat=tx.tiles("septic_yard_floor_tiles", "#B9C0C6", grout="#E6E8EA", size=0.3, rough=0.25),
            parent=root, bevel=0)
    toy.box(f"{name}_back_wall", (4.0, 0.15, 2.8), (0, 1.925, 1.6), mat=wall, parent=root, bevel=0.005)
    toy.box(f"{name}_left_wall", (0.15, 3.85, 2.8), (-1.925, -0.075, 1.6), mat=wall, parent=root, bevel=0.005)
    toy.box(f"{name}_wall_tiles", (3.85, 0.02, 1.0), (0.075, 1.84, 0.72),
            mat=tx.tiles("septic_yard_wall_tiles", "#DCE7EC", size=0.15), parent=root, bevel=0)
    toy.box(f"{name}_side_tiles", (0.02, 3.85, 1.0), (-1.84, -0.075, 0.72),
            mat=tx.tiles("septic_yard_wall_tiles", "#DCE7EC", size=0.15), parent=root, bevel=0)
    toy.box(f"{name}_window_frame", (0.9, 0.05, 0.8), (0.8, 1.83, 2.15), mat=ceramic, parent=root, bevel=0.01)
    toy.box(f"{name}_window_glass", (0.76, 0.02, 0.66), (0.8, 1.81, 2.15),
            mat=tx.paint("septic_yard_glass", "#9FC6E0", rough=0.05, coat=1.0), parent=root, bevel=0)
    # toilet
    tx_ = -0.7
    toy.cylinder(f"{name}_toilet_foot", 0.15, 0.26, (tx_, 1.42, 0.35), mat=ceramic, parent=root, bevel=0.02)
    toy.sphere(f"{name}_toilet_bowl", 0.22, (tx_, 1.38, 0.55), scale=(1.0, 1.3, 0.5), mat=ceramic, parent=root,
               subdiv=1)
    _torus(f"{name}_toilet_seat", 0.17, 0.035, (tx_, 1.36, 0.65), (0, 0, 0), ceramic, root, scale=(1.0, 1.25, 1.0))
    toy.box(f"{name}_toilet_tank", (0.5, 0.2, 0.42), (tx_, 1.74, 0.92), mat=ceramic, parent=root, bevel=0.03)
    toy.box(f"{name}_toilet_tank_lid", (0.54, 0.23, 0.04), (tx_, 1.74, 1.15), mat=ceramic, parent=root, bevel=0.01)
    toy.box(f"{name}_toilet_lid", (0.36, 0.04, 0.42), (tx_, 1.6, 0.86), mat=ceramic, parent=root, bevel=0.02,
            rotation=(-0.15, 0, 0))
    toy.box(f"{name}_flush_handle", (0.08, 0.03, 0.02), (tx_ - 0.2, 1.63, 1.06), mat=chrome, parent=root, bevel=0)
    toy.cylinder(f"{name}_paper_roll", 0.055, 0.11, (-1.78, 1.2, 0.8), rotation=(0, math.pi / 2, 0),
                 mat=tx.cloth("septic_yard_paper", "#FAFAF7"), parent=root)
    toy.box(f"{name}_bath_mat", (0.6, 0.4, 0.012), (tx_, 0.9, 0.226),
            mat=tx.cloth("septic_yard_mat_cloth", "#5B8FB9"), parent=root, bevel=0.004)
    # sink
    toy.cylinder(f"{name}_sink_pedestal", 0.09, 0.65, (0.8, 1.66, 0.545), mat=ceramic, parent=root, bevel=0.02)
    toy.box(f"{name}_sink_basin", (0.56, 0.42, 0.16), (0.8, 1.62, 0.95), mat=ceramic, parent=root, bevel=0.05)
    toy.cylinder(f"{name}_sink_bowl", 0.17, 0.02, (0.8, 1.6, 1.025),
                 mat=tx.paint("septic_yard_basin_in", "#D9DDDF", rough=0.15, coat=0.8), parent=root)
    toy.cylinder(f"{name}_faucet", 0.018, 0.16, (0.8, 1.78, 1.1), mat=chrome, parent=root)
    toy.box(f"{name}_faucet_spout", (0.03, 0.12, 0.03), (0.8, 1.72, 1.17), mat=chrome, parent=root, bevel=0.005)
    # drain stack: vent above, down through the slab, building drain leaving right under the floor
    sx, sy = -1.55, 1.65
    toy.cylinder(f"{name}_drain_stack", 0.055, 3.45, (sx, sy, 1.275), mat=pvc, parent=root)
    toy.sphere(f"{name}_stack_elbow", 0.065, (sx, sy, -0.4), mat=pvc, parent=root, subdiv=0)
    toy.cylinder(f"{name}_building_drain", 0.055, 2.0 - sx, ((sx + 2.0) / 2, sy, -0.4),
                 rotation=(0, math.pi / 2, 0), mat=pvc, parent=root)
    toy.cylinder(f"{name}_toilet_drop", 0.045, 0.5, (tx_, 1.42, -0.03), mat=pvc, parent=root)
    toy.cylinder(f"{name}_toilet_branch", 0.045, abs(tx_ - sx), ((tx_ + sx) / 2, 1.42, -0.25),
                 rotation=(0, math.pi / 2, 0), mat=pvc, parent=root)
    toy.cylinder(f"{name}_branch_tee", 0.045, 0.25, (sx + 0.05, 1.53, -0.25), rotation=(math.pi / 2, 0, 0),
                 mat=pvc, parent=root)
    for k, z in enumerate((0.5, 1.4, 2.3)):
        toy.cylinder(f"{name}_stack_clamp{k}", 0.064, 0.04, (sx, sy, z), mat=chrome, parent=root)
    return root


def build_septic_yard_sewer_pipe():
    """4 m grey 10 cm plastic sewer pipe sloping gently down from left to right, with push-fit couplings."""
    name = "septic_yard_sewer_pipe"
    root = _root(name)
    pvc = _pvc_grey()
    z0, z1 = 0.086, 0.056
    p = st.pipe(f"{name}_run", [(-2.0, 0, z0), (0.0, 0, (z0 + z1) / 2), (2.0, 0, z1)], 0.05, mat=pvc,
                wall=0.006, flange_every=0)
    p.parent = root
    slope = math.atan2(z0 - z1, 4.0)
    for k, x in enumerate((-1.0, 0.0, 1.0)):
        z = z0 + (z1 - z0) * (x + 2.0) / 4.0
        toy.cylinder(f"{name}_coupling{k}", 0.06, 0.09, (x, 0, z), rotation=(0, math.pi / 2 + slope, 0),
                     mat=tx.paint("septic_yard_pvc_coupling", "#7D8288", rough=0.45, coat=0.2), parent=root)
    return root


def build_septic_yard_pit():
    """A crude unlined cesspit: a wide round bowl dug into a cutaway block of soil (cut through the hole's
    middle at the front), a heaped dirt rim, loose rocks set into the walls, murky sewage at the bottom."""
    name = "septic_yard_pit"
    rng = random.Random(41)
    root = _root(name)
    soil = _surf("septic_yard_pit_soil", "#7A5636", "#432D1B", scale=6.0, bump=0.6)
    wall_mat = _surf("septic_yard_pit_wall", "#6A4A2E", "#3A2716", scale=9.0, bump=0.8)
    X, Y0, Y1 = 0.95, -0.12, 1.0                            # the block (front face = the cut through the hole)
    zb, zt, rb, rt = 0.5, 1.27, 0.3, 0.72                   # bowl bottom / top, bottom / top radius

    def rad(z):
        t = max(0.0, min(1.0, (z - zb) / (zt - zb)))
        return rb + (rt - rb) * t ** 0.55

    prof = [(0.0001, zb)] + [(rad(zb + (zt - zb) * k / 8), zb + (zt - zb) * k / 8) for k in range(9)]
    prof[1] = (rb, zb)
    prof.append((rt + 0.06, 1.7))

    sub_top = _wave(rng, 0.98, 0.04)
    top_top = _wave(rng, 1.22, 0.015)
    lawn_top = _lumps(rng, 1.27, 0.008, 8.0)
    strata = [
        ("subsoil", lambda x, y: 0.0, sub_top, _surf("septic_yard_pit_subsoil", "#B48D60", "#8A6942",
                                                      scale=5.0, bump=0.35)),
        ("topsoil", sub_top, top_top, soil),
        ("lawn", top_top, lawn_top, _surf("septic_yard_lawn", "#6BAA45", "#3F7A2A", scale=14.0, bump=0.3)),
    ]
    for part, bot, top, mat in strata:
        ob = _layer(f"{name}_{part}", -X, X, Y0, Y1, bot, top, 28, 14, mat, root)
        st.carve(ob, _revolved(f"{name}_cutter", prof, n=36, jitter=0.03, seed=7), mat=wall_mat)
    rim = _torus(f"{name}_rim", rt + 0.09, 0.1, (0, 0, zt), (0, 0, 0), soil, root, scale=(1, 1, 0.5))
    st.carve(rim, st.box_cutter((0, Y0 - 1.0, 1.0), (3.0, 2.0, 3.0)), mat=soil)
    # murky sewage pooled in the bottom of the bowl, cut flush with the section
    zw = zb + 0.17
    water = _revolved(f"{name}_sewage", [(0.0001, zb + 0.005), (rb - 0.01, zb + 0.005), (rad(zw) - 0.01, zw)],
                      n=36, mats=(_surf("septic_yard_murky", "#6B5530", "#3A2C17", scale=5.0, bump=0.08,
                                        rough=0.15),))
    water.parent = root
    st.carve(water, st.box_cutter((0, Y0 - 1.0, 0.6), (3.0, 2.0, 2.0)),
             mat=_surf("septic_yard_murky", "#6B5530", "#3A2C17"))
    stone = _stone_mat()
    k = 0
    while k < 30:                                           # loose rocks set into the bowl walls
        z = rng.uniform(zb + 0.04, zt - 0.03)
        th = rng.uniform(-0.15, math.pi + 0.15)
        r = rad(z) + 0.015
        if r * math.sin(th) < Y0 + 0.08:
            continue
        s = rng.uniform(0.045, 0.09)
        rock = toy.sphere(f"{name}_rock{k}", s, (r * math.cos(th), r * math.sin(th), z),
                          scale=(1.0, rng.uniform(0.65, 0.9), rng.uniform(0.55, 0.8)), mat=stone, parent=root,
                          subdiv=0, segments=9, rings=6)
        rock.rotation_euler = (rng.uniform(0, 1), rng.uniform(0, 1), rng.uniform(0, 3))
        k += 1
    j = 0
    while j < 18:                                           # rocks in the soil of the cut face
        x, z = rng.uniform(-X + 0.08, X - 0.08), rng.uniform(0.08, 1.15)
        if z > zb - 0.08 and abs(x) < rad(z) + 0.1:
            continue
        s = rng.uniform(0.035, 0.075)
        rock = toy.sphere(f"{name}_face_rock{j}", s, (x, Y0 + s * 0.2, z), scale=(1.0, 0.6, rng.uniform(0.6, 0.85)),
                          mat=stone, parent=root, subdiv=0, segments=9, rings=6)
        rock.rotation_euler = (0, rng.uniform(0, 3.1), 0)
        j += 1
    for k in range(14):                                     # rocks dumped on the rim
        th = rng.uniform(0.0, math.pi)
        r = rt + rng.uniform(0.04, 0.18)
        s = rng.uniform(0.05, 0.09)
        rock = toy.sphere(f"{name}_rim_rock{k}", s, (r * math.cos(th), r * math.sin(th), zt + 0.04),
                          scale=(1.0, rng.uniform(0.7, 0.95), rng.uniform(0.55, 0.75)), mat=stone, parent=root,
                          subdiv=0, segments=9, rings=6)
        rock.rotation_euler = (0, 0, rng.uniform(0, 3))
    for k in range(6):                                      # floating muck
        a, d = rng.uniform(0.2, math.pi - 0.2), rng.uniform(0.05, 0.28)
        toy.sphere(f"{name}_muck{k}", rng.uniform(0.025, 0.045), (d * math.cos(a), d * math.sin(a), zw),
                   scale=(1, 1, 0.35), mat=_surf("septic_yard_muck", "#4A3A22", "#2A1F12", scale=12.0),
                   parent=root, subdiv=0, segments=8, rings=5)
    return root


def build_septic_yard_tank():
    """Watertight 1,000 gallon concrete tank, front wall cut away lengthwise, lid with an access riser."""
    name = "septic_yard_tank"
    root = _root(name)
    conc = _concrete()
    toy.box(f"{name}_floor", (2.4, 1.5, 0.12), (0, 0, 0.06), mat=conc, parent=root, bevel=0.01)
    # Keep the back face clear of the end-wall rear faces.  Their old shared
    # y=0.75 plane produced visible depth-buffer flicker at both corners.
    toy.box(f"{name}_back_wall", (2.18, 0.1, 1.2), (0, 0.72, 0.72), mat=conc, parent=root, bevel=0.01)
    for k, x in enumerate((-1.15, 1.15)):
        toy.box(f"{name}_end_wall{k}", (0.1, 1.5, 1.2), (x, 0, 0.72), mat=conc, parent=root, bevel=0.01)
    toy.box(f"{name}_lid", (2.4, 1.5, 0.12), (0, 0, 1.38), mat=conc, parent=root, bevel=0.015)
    toy.box(f"{name}_cut_edge", (2.4, 0.012, 0.04), (0, -0.745, 1.30), mat=conc, parent=root, bevel=0)
    toy.cylinder(f"{name}_riser", 0.3, 0.2, (-0.55, 0, 1.54), mat=conc, parent=root, vertices=32, bevel=0.01)
    toy.cylinder(f"{name}_riser_cap", 0.32, 0.04, (-0.55, 0, 1.66),
                 mat=tx.paint("septic_yard_riser_lid", "#3F5E3B", rough=0.6, coat=0.1), parent=root, vertices=32,
                 bevel=0.01)
    for k in range(4):                                      # ribs on the plastic lid
        a = k * math.pi / 4
        toy.box(f"{name}_cap_rib{k}", (0.5, 0.03, 0.015), (-0.55, 0, 1.686), rotation=(0, 0, a),
                mat=tx.paint("septic_yard_riser_lid", "#3F5E3B"), parent=root, bevel=0)
    toy.cylinder(f"{name}_inspection_port", 0.12, 0.08, (0.75, 0.2, 1.48),
                 mat=tx.paint("septic_yard_riser_lid", "#3F5E3B"), parent=root, vertices=24)
    pvc = _pvc_grey()
    toy.cylinder(f"{name}_inlet", 0.055, 0.3, (-1.25, 0, 1.12), rotation=(0, math.pi / 2, 0), mat=pvc, parent=root)
    toy.cylinder(f"{name}_outlet", 0.055, 0.3, (1.25, 0, 1.04), rotation=(0, math.pi / 2, 0), mat=pvc, parent=root)
    return root


def build_septic_yard_layers():
    """Thin yellow scum crust on top, pale clear effluent in the middle, thick dark sludge on the floor."""
    name = "septic_yard_layers"
    rng = random.Random(53)
    root = _root(name)
    x0, x1, y0, y1 = -1.15, 1.15, -0.7, 0.7
    sludge_top = _lumps(rng, 0.46, 0.035, 5.0)
    _layer(f"{name}_sludge", x0, x1, y0, y1, lambda x, y: 0.0, sludge_top, 24, 12,
           _surf("septic_yard_sludge_dark", "#4A3020", "#1C120A", scale=8.0, bump=0.6, rough=0.55), root,
           smooth=True)
    toy.box(f"{name}_effluent", (2.3, 1.4, 0.6), (0, 0, 0.76),
            mat=st.water_volume("septic_yard_effluent_clear", color="#B4CF98", density=0.35, scatter=0.5),
            parent=root, bevel=0)
    toy.box(f"{name}_effluent_face", (2.3, 0.004, 0.56), (0, y0 - 0.004, 0.76),
            mat=st.water_surface("septic_yard_effluent_pale", "#D3E6C0"), parent=root, bevel=0)
    _layer(f"{name}_scum", x0, x1, y0, y1, _lumps(rng, 1.06, 0.01, 4.0), _lumps(rng, 1.15, 0.02, 9.0), 24, 12,
           _surf("septic_yard_scum", "#D9C46A", "#8F7A34", scale=10.0, bump=0.9, rough=0.7, cells=14.0), root,
           smooth=True)
    specks = _surf("septic_yard_specks", "#6E5232", "#3B2A17", scale=15.0)
    for k in range(22):                                     # solids drifting down through the clear water
        toy.sphere(f"{name}_speck{k}", rng.uniform(0.012, 0.022),
                   (rng.uniform(-1.05, 1.05), rng.uniform(-0.66, 0.6), rng.uniform(0.56, 0.98)),
                   mat=specks, parent=root, subdiv=0, segments=8, rings=5)
    return root


def build_septic_yard_baffles():
    """One white sanitary tee: vertical run dipping below the scum line, side branch to the tank wall."""
    name = "septic_yard_baffles"
    root = _root(name)
    pvc = _pvc_white()
    dark = _surf("septic_yard_pipe_bore", "#2A2A2A", "#151515", scale=20.0, bump=0.05)
    toy.cylinder(f"{name}_run", 0.05, 0.6, (0, 0, 0.3), mat=pvc, parent=root)
    toy.cylinder(f"{name}_hub_top", 0.058, 0.06, (0, 0, 0.57), mat=pvc, parent=root)
    toy.cylinder(f"{name}_hub_bottom", 0.058, 0.05, (0, 0, 0.025), mat=pvc, parent=root)
    toy.cylinder(f"{name}_branch", 0.05, 0.1, (-0.06, 0, 0.45), rotation=(0, math.pi / 2, 0), mat=pvc, parent=root)
    toy.cylinder(f"{name}_hub_branch", 0.058, 0.05, (-0.1, 0, 0.45), rotation=(0, math.pi / 2, 0), mat=pvc,
                 parent=root)
    toy.cylinder(f"{name}_bore_top", 0.042, 0.004, (0, 0, 0.601), mat=dark, parent=root)
    toy.cylinder(f"{name}_bore_bottom", 0.042, 0.004, (0, 0, -0.001), mat=dark, parent=root)
    toy.cylinder(f"{name}_bore_branch", 0.042, 0.004, (-0.126, 0, 0.45), rotation=(0, math.pi / 2, 0), mat=dark,
                 parent=root)
    return root


def build_septic_yard_drainfield():
    """Three gravel trenches with white perforated pipes, a distribution box, water seeping down below."""
    name = "septic_yard_drainfield"
    rng = random.Random(67)
    root = _root(name)
    gravel = _surf("septic_yard_gravel", "#A3A39E", "#5C5D5A", scale=30.0, bump=0.8, rough=0.9, cells=28.0)
    pvc = _pvc_white()
    hole_mat = _surf("septic_yard_pipe_bore", "#2A2A2A", "#151515", scale=20.0, bump=0.05)
    drop_mat = _surf("septic_yard_seep", "#8CCBF0", "#3D8FD0", scale=25.0, bump=0.1, rough=0.08)
    stone = _stone_mat()
    pz, pr = 0.62, 0.05
    hx = -3.85
    for t, yc in enumerate((-2.4, 0.0, 2.4)):
        _layer(f"{name}_gravel{t}", -3.9, 3.9, yc - 0.3, yc + 0.3, lambda x, y: 0.2, _lumps(rng, 0.8, 0.02, 14.0),
               48, 4, gravel, root, smooth=True)
        toy.cylinder(f"{name}_pipe{t}", pr, 3.9 - hx, ((3.9 + hx) / 2, yc, pz), rotation=(0, math.pi / 2, 0),
                     mat=pvc, parent=root)
        toy.cylinder(f"{name}_cap{t}", pr + 0.006, 0.04, (3.9, yc, pz), rotation=(0, math.pi / 2, 0), mat=pvc,
                     parent=root)
        verts, faces = [], []                               # two rows of holes facing down-front / down-back
        for phi in (math.radians(40), math.radians(-40)):
            nrm = (0.0, -math.sin(phi), -math.cos(phi))
            v = (0.0, -nrm[2], nrm[1])                      # nrm x (1, 0, 0)
            x = hx + 0.15
            while x < 3.8:
                c = (x, yc + nrm[1] * (pr + 0.0015), pz + nrm[2] * (pr + 0.0015))
                base = len(verts)
                for s in range(8):
                    a = 2 * math.pi * s / 8
                    verts.append((c[0] + 0.012 * math.cos(a), c[1] + 0.012 * math.sin(a) * v[1],
                                  c[2] + 0.012 * math.sin(a) * v[2]))
                faces.append(tuple(range(base, base + 8)))
                x += 0.2
        st.mesh_obj(f"{name}_holes{t}", verts, faces, (hole_mat,), smooth=False).parent = root
        for k in range(16):                                 # effluent seeping out below the gravel
            toy.sphere(f"{name}_drop{t}_{k}", rng.uniform(0.018, 0.03),
                       (rng.uniform(-3.7, 3.7), yc - rng.uniform(0.1, 0.28), rng.uniform(0.02, 0.17)),
                       scale=(1, 1, 1.6), mat=drop_mat, parent=root, subdiv=0, segments=10, rings=6)
        for k in range(30):                                 # chunky stones on the trench faces
            s = rng.uniform(0.025, 0.045)
            toy.sphere(f"{name}_stone{t}_{k}", s, (rng.uniform(-3.8, 3.8), yc - 0.3 + s * 0.3,
                                                     rng.uniform(0.23, 0.77)),
                       scale=(1, 0.7, 0.75), mat=stone, parent=root, subdiv=0, segments=8, rings=5)
    toy.cylinder(f"{name}_header", pr, 4.8, (hx, 0, pz), rotation=(math.pi / 2, 0, 0), mat=pvc, parent=root)
    for k, yc in enumerate((-2.4, 2.4)):
        toy.sphere(f"{name}_elbow{k}", pr + 0.005, (hx, yc, pz), mat=pvc, parent=root, subdiv=0)
    toy.box(f"{name}_dbox", (0.45, 0.45, 0.45), (-4.15, 0, 0.55), mat=_concrete(), parent=root, bevel=0.015)
    toy.box(f"{name}_dbox_lid", (0.5, 0.5, 0.05), (-4.15, 0, 0.8), mat=_concrete(), parent=root, bevel=0.01)
    return root


def build_septic_yard_anchors():
    """Two separate dark concrete deadman blocks, wide dark hold-down straps arching over (the tank top)
    from one block to the other, wrapped round each block's outer end and fastened to anchor eyes."""
    name = "septic_yard_anchors"
    root = _root(name)
    conc = st.concrete("septic_yard_anchor_concrete", "#66676A", lift=0.5, panel=0.6)
    galv = tx.metal("septic_yard_galv", "#A9B0B6", rough=0.35)
    strap = tx.cloth("septic_yard_strap", "#1C1D20", rough=0.7)
    bh, bx0, bx1 = 0.22, 0.2, 1.3                           # block height, inner / outer end
    for k, sgn in enumerate((-1, 1)):
        toy.box(f"{name}_block{k}", (bx1 - bx0, 0.4, bh), (sgn * (bx0 + bx1) / 2, 0, bh / 2), mat=conc,
                parent=root, bevel=0.02)
    # strap path in x-z: up the outer end of block 0, along its top, arching over, down to block 1
    path = [(-bx1 - 0.008, 0.02), (-bx1 - 0.008, bh + 0.008)]
    for i in range(25):
        x = -0.95 + 1.9 * i / 24
        path.append((x, bh + 0.008 + 0.19 * math.cos(math.pi * x / 1.9)))
    path += [(bx1 + 0.008, bh + 0.008), (bx1 + 0.008, 0.02)]
    for s, yc in enumerate((-0.11, 0.11)):
        verts, faces = [], []
        for x, z in path:
            verts += [(x, yc - 0.065, z), (x, yc + 0.065, z)]
        for i in range(len(path) - 1):
            faces.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
        band = st.mesh_obj(f"{name}_strap{s}", verts, faces, (strap,), smooth=False)
        sol = band.modifiers.new("thick", "SOLIDIFY")
        sol.thickness, sol.offset = 0.012, 1.0
        band.parent = root
        toy.box(f"{name}_buckle{s}", (0.07, 0.15, 0.025), (0.0, yc, bh + 0.2 + 0.01), mat=galv, parent=root,
                bevel=0.004)
        for k, sgn in enumerate((-1, 1)):
            toy.box(f"{name}_wrap{s}_{k}", (bx1 - bx0 + 0.02, 0.13, 0.02), (sgn * (bx0 + bx1) / 2, yc, 0.035),
                    mat=strap, parent=root, bevel=0.003)
            toy.box(f"{name}_eye_plate{s}_{k}", (0.012, 0.12, 0.1), (sgn * (bx1 + 0.02), yc, 0.09), mat=galv,
                    parent=root, bevel=0.003)
            _torus(f"{name}_eye{s}_{k}", 0.035, 0.01, (sgn * (bx1 + 0.03), yc, 0.09), (0, math.pi / 2, 0), galv,
                   root)
    return root


def build_septic_yard_well():
    """Neighbour's drilled well: thick steel casing, a clear pump cap on top, a slotted screen standing in a
    blue column of groundwater at the bottom."""
    name = "septic_yard_well"
    root = _root(name)
    steel = tx.metal("septic_yard_casing", "#7D868F", rough=0.4)
    screen = tx.metal("septic_yard_screen", "#B8BEC4", rough=0.25)
    dark = tx.metal("septic_yard_screen_slot", "#3A3F44", rough=0.6)
    cap = tx.paint("septic_yard_well_cap_blue", "#2F5F8F", rough=0.35, coat=0.4)
    toy.cylinder(f"{name}_point", 0.07, 0.06, (0, 0, 0.03), mat=steel, parent=root)
    toy.cylinder(f"{name}_screen", 0.1, 1.2, (0, 0, 0.66), mat=screen, parent=root)
    for k in range(11):
        toy.cylinder(f"{name}_slot{k}", 0.102, 0.022, (0, 0, 0.14 + k * 0.1), mat=dark, parent=root)
    # the groundwater the screen stands in: a blue column with a rippled skin on top
    toy.cylinder(f"{name}_water", 0.148, 1.4, (0, 0, 0.7),
                 mat=st.water_volume("septic_yard_well_water", color="#1F6FD0", density=4.0, scatter=0.25),
                 parent=root, vertices=32)
    _torus(f"{name}_water_skin", 0.125, 0.024, (0, 0, 1.4), (0, 0, 0),
           st.water_surface("septic_yard_well_skin", "#5CC4E6"), root, scale=(1, 1, 0.3))
    toy.cylinder(f"{name}_coupling", 0.125, 0.1, (0, 0, 1.3), mat=steel, parent=root)
    toy.cylinder(f"{name}_casing", 0.11, 3.3, (0, 0, 2.95), mat=steel, parent=root, vertices=32)
    for k, z in enumerate((2.2, 3.3)):
        toy.cylinder(f"{name}_joint{k}", 0.122, 0.06, (0, 0, z), mat=steel, parent=root)
    toy.cylinder(f"{name}_collar", 0.15, 0.1, (0, 0, 3.98), mat=_concrete(), parent=root, bevel=0.01)
    toy.cylinder(f"{name}_cap", 0.145, 0.2, (0, 0, 4.7), mat=cap, parent=root, bevel=0.015, vertices=32)
    toy.sphere(f"{name}_cap_dome", 0.14, (0, 0, 4.8), scale=(1, 1, 0.45), mat=cap, parent=root, subdiv=1)
    for k in range(4):                                      # cap bolts
        a = k * math.pi / 2 + math.pi / 4
        toy.cylinder(f"{name}_bolt{k}", 0.014, 0.03, (0.14 * math.cos(a), 0.14 * math.sin(a), 4.62),
                     rotation=(0, math.pi / 2, a), mat=steel, parent=root)
    toy.cylinder(f"{name}_vent", 0.03, 0.08, (0, 0, 4.9), mat=steel, parent=root)
    toy.cylinder(f"{name}_conduit", 0.018, 0.5, (0.13, 0, 4.35),
                 mat=tx.paint("septic_yard_conduit", "#8A8F93", rough=0.5), parent=root)
    return root


def build_septic_yard_pump_truck():
    """Plain white vacuum truck: cab, big round steel tank, vacuum pump, black suction hose to the ground."""
    name = "septic_yard_pump_truck"
    root = _root(name)
    white = tx.paint("septic_yard_truck_white", "#F2F2EE", rough=0.3, coat=0.6, seams=0.8)
    steel = tx.metal("septic_yard_truck_tank", "#BAC0C6", rough=0.28, along="x")
    dark = tx.metal("septic_yard_truck_frame", "#2E3134", rough=0.55)
    glass = tx.paint("septic_yard_truck_glass", "#2C3A46", rough=0.06, coat=1.0)
    tyre = tx.rubber("septic_yard_tyre", "#1F1F21", tread=0.6)
    hose = tx.rubber("septic_yard_hose", "#151517", rough=0.6)
    toy.box(f"{name}_frame", (6.4, 1.0, 0.25), (0, 0, 0.78), mat=dark, parent=root, bevel=0.01)
    toy.box(f"{name}_cab", (1.6, 2.3, 2.05), (2.65, 0, 1.73), mat=white, parent=root, bevel=0.08)
    toy.box(f"{name}_windshield", (0.04, 2.0, 0.75), (3.46, 0, 2.2), mat=glass, parent=root, bevel=0.01)
    for k, y in enumerate((-1.16, 1.16)):
        toy.box(f"{name}_side_window{k}", (0.7, 0.02, 0.6), (2.85, y, 2.2), mat=glass, parent=root, bevel=0.01)
        toy.box(f"{name}_mirror{k}", (0.08, 0.06, 0.35), (3.3, y * 1.08, 2.1), mat=dark, parent=root, bevel=0.01)
        toy.box(f"{name}_step{k}", (0.45, 0.12, 0.05), (2.6, y * 0.98, 0.55), mat=dark, parent=root, bevel=0.005)
    toy.box(f"{name}_grille", (0.04, 1.4, 0.5), (3.46, 0, 1.25), mat=dark, parent=root, bevel=0.01)
    for k, y in enumerate((-0.85, 0.85)):
        toy.cylinder(f"{name}_headlight{k}", 0.1, 0.04, (3.47, y, 1.25), rotation=(0, math.pi / 2, 0),
                     mat=tx.paint("septic_yard_headlight", "#FFF3C8", rough=0.1, coat=1.0), parent=root)
    toy.box(f"{name}_bumper", (0.2, 2.4, 0.22), (3.5, 0, 0.72),
            mat=tx.metal("septic_yard_bumper", "#9AA0A6", rough=0.3), parent=root, bevel=0.02)
    # the vacuum tank
    tz = 1.95
    toy.cylinder(f"{name}_tank", 0.95, 4.6, (-1.0, 0, tz), rotation=(0, math.pi / 2, 0), mat=steel,
                 parent=root, vertices=40)
    for k, x in enumerate((-3.3, 1.3)):
        toy.sphere(f"{name}_tank_head{k}", 0.95, (x, 0, tz), scale=(0.25, 1, 1), mat=steel, parent=root,
                   subdiv=1, segments=32, rings=16)
    for k, x in enumerate((-2.7, -1.0, 0.7)):
        toy.cylinder(f"{name}_tank_band{k}", 0.97, 0.07, (x, 0, tz), rotation=(0, math.pi / 2, 0), mat=dark,
                     parent=root, vertices=40)
        toy.box(f"{name}_saddle{k}", (0.18, 1.1, 0.3), (x, 0, 1.05), mat=dark, parent=root, bevel=0.01)
    toy.cylinder(f"{name}_manway", 0.25, 0.15, (-0.5, 0, 2.94), mat=steel, parent=root, bevel=0.01)
    toy.box(f"{name}_pump", (0.5, 0.7, 0.55), (1.65, 0.1, 1.25), mat=dark, parent=root, bevel=0.03)
    toy.cylinder(f"{name}_exhaust", 0.06, 1.5, (1.85, 0.95, 2.3), mat=steel, parent=root)
    toy.cylinder(f"{name}_valve", 0.12, 0.2, (-3.5, 0.45, 1.1), rotation=(0, math.pi / 2, 0), mat=dark, parent=root)
    toy.box(f"{name}_valve_lever", (0.04, 0.04, 0.3), (-3.6, 0.45, 1.3), mat=dark, parent=root, bevel=0.005)
    for k, y in enumerate((-0.8, 0.8)):
        toy.box(f"{name}_tail_light{k}", (0.04, 0.2, 0.1), (-3.22, y, 0.82),
                mat=tx.paint("septic_yard_tail_light", "#C42A22", rough=0.2, coat=0.8), parent=root, bevel=0.01)
    st.pipe(f"{name}_hose", [(-3.62, 0.45, 1.1), (-3.75, 0.8, 0.6), (-3.55, 1.3, 0.12), (-2.8, 1.55, 0.08),
                             (-2.0, 1.42, 0.08), (-1.3, 1.55, 0.08)],
            0.07, mat=hose, wall=0.02, flange_every=0).parent = root
    toy.cylinder(f"{name}_nozzle", 0.08, 0.25, (-1.18, 1.55, 0.08), rotation=(0, math.pi / 2, 0), mat=steel,
                 parent=root)
    _torus(f"{name}_hose_coil", 0.35, 0.06, (0.2, -1.08, 1.25), (math.pi / 2, 0, 0), hose, root)
    for k, x in enumerate((2.6, -1.7, -2.75)):
        for s, y in enumerate((-1.0, 1.0)):
            toy.cylinder(f"{name}_wheel{k}_{s}", 0.5, 0.35, (x, y, 0.5), rotation=(math.pi / 2, 0, 0), mat=tyre,
                         parent=root, vertices=32, bevel=0.04)
            toy.cylinder(f"{name}_hub{k}_{s}", 0.25, 0.37, (x, y, 0.5), rotation=(math.pi / 2, 0, 0),
                         mat=tx.metal("septic_yard_hub", "#B5BAC0", rough=0.3), parent=root)
    return root


def build_septic_yard_wastewater():
    """The tank's contents in three layers: dark brown sludge on the floor, cloudy greenish clear water in
    the middle, a lumpy yellow-white scum crust floating on top."""
    name = "septic_yard_wastewater"
    rng = random.Random(71)
    root = _root(name)
    x0, x1, y0, y1 = -1.15, 1.15, -0.7, 0.7
    sludge_top = _lumps(rng, 0.42, 0.04, 5.0)
    _layer(f"{name}_sludge", x0, x1, y0, y1, lambda x, y: 0.0, sludge_top, 28, 14,
           _surf("septic_yard_ww_sludge", "#5A3A22", "#24160C", scale=8.0, bump=0.7, rough=0.5), root,
           smooth=True)
    toy.box(f"{name}_clear", (2.3, 1.4, 0.72), (0, 0, 0.75),
            mat=st.water_volume("septic_yard_ww_clear", color="#9CC48A", density=0.45, scatter=0.55),
            parent=root, bevel=0)
    toy.box(f"{name}_clear_face", (2.3, 0.004, 0.68), (0, y0 - 0.004, 0.75),
            mat=st.water_surface("septic_yard_ww_clear_face", "#B9D9A4"), parent=root, bevel=0)
    _layer(f"{name}_scum", x0, x1, y0, y1, _lumps(rng, 1.1, 0.015, 4.0), _lumps(rng, 1.24, 0.04, 9.0), 28, 14,
           _surf("septic_yard_ww_scum", "#EDE3B4", "#B8A25A", scale=11.0, bump=1.0, rough=0.75, cells=12.0), root,
           smooth=True)
    crust = _surf("septic_yard_ww_crust", "#F2EAC4", "#C2AE66", scale=14.0, bump=0.8)
    for k in range(26):                                     # lumps heaped on the crust
        x, y = rng.uniform(-1.05, 1.05), rng.uniform(-0.62, 0.62)
        toy.sphere(f"{name}_lump{k}", rng.uniform(0.04, 0.08), (x, y, 1.24), scale=(1, rng.uniform(0.7, 1.0), 0.4),
                   mat=crust, parent=root, subdiv=0, segments=10, rings=6)
    specks = _surf("septic_yard_ww_specks", "#6E5232", "#3B2A17", scale=15.0)
    for k in range(24):                                     # solids settling through the clear layer
        toy.sphere(f"{name}_speck{k}", rng.uniform(0.012, 0.024),
                   (rng.uniform(-1.05, 1.05), rng.uniform(-0.66, 0.6), rng.uniform(0.5, 1.05)),
                   mat=specks, parent=root, subdiv=0, segments=8, rings=5)
    return root


def build_septic_yard_pipes():
    """Grey 10 cm sewer pipe from the house to the tank inlet (left) and the outlet pipe on to the drain field
    (right), both sloping downhill; the outlet sits a little lower than the inlet."""
    name = "septic_yard_pipes"
    root = _root(name)
    pvc = _pvc_grey()
    hub = tx.paint("septic_yard_pipes_hub", "#7A7F85", rough=0.45, coat=0.2)
    bore = _surf("septic_yard_pipes_bore", "#2A2A2A", "#151515", scale=20.0, bump=0.05)
    hr = 0.053                                              # coupling radius: the lowest coupling sits on z = 0
    runs = (("inlet", -3.0, -0.3, 0.078, 0.066), ("outlet", 0.3, 3.0, 0.062, hr))
    for part, xa, xb, za, zb in runs:
        st.pipe(f"{name}_{part}", [(xa, 0, za), ((xa + xb) / 2, 0, (za + zb) / 2), (xb, 0, zb)], 0.05, mat=pvc,
                wall=0.006, flange_every=0).parent = root
        slope = math.atan2(za - zb, xb - xa)
        for k, f in enumerate((0.0, 0.5, 1.0)):
            x, z = xa + (xb - xa) * f, za + (zb - za) * f
            x = min(max(x, xa + 0.05), xb - 0.05)
            toy.cylinder(f"{name}_{part}_coupling{k}", hr, 0.09, (x, 0, z),
                         rotation=(0, math.pi / 2 + slope, 0), mat=hub, parent=root)
        for k, (x, z) in enumerate(((xa, za), (xb, zb))):
            toy.cylinder(f"{name}_{part}_bore{k}", 0.043, 0.004, (x, 0, z), rotation=(0, math.pi / 2 + slope, 0),
                         mat=bore, parent=root)
    return root


def build_septic_yard_drain_field():
    """Three parallel trenches of pale grey gravel under the lawn, each with a white perforated pipe on its
    gravel bed, grassy soil berms between them."""
    name = "septic_yard_drain_field"
    rng = random.Random(83)
    root = _root(name)
    gravel = _surf("septic_yard_df_gravel", "#C4C3BD", "#7C7D79", scale=30.0, bump=0.8, rough=0.9, cells=28.0)
    soil = _surf("septic_yard_df_soil", "#5A3E28", "#33231A", scale=7.0, bump=0.4)
    lawn = _surf("septic_yard_df_lawn", "#6BAA45", "#3F7A2A", scale=14.0, bump=0.3)
    pvc = _pvc_white()
    hole_mat = _surf("septic_yard_df_hole", "#2A2A2A", "#151515", scale=20.0, bump=0.05)
    stone = _surf("septic_yard_df_stone", "#B5B3AC", "#76746E", scale=9.0, bump=0.5, rough=0.85)
    x0, x1 = -2.5, 2.5
    pz, pr = 0.5, 0.05
    for t, yc in enumerate((-1.1, 0.0, 1.1)):
        _layer(f"{name}_gravel{t}", x0, x1, yc - 0.3, yc + 0.3, lambda x, y: 0.0, _lumps(rng, 0.46, 0.03, 14.0),
               50, 6, gravel, root, smooth=True)
        toy.cylinder(f"{name}_pipe{t}", pr, x1 - x0 - 0.04, (0, yc, pz), rotation=(0, math.pi / 2, 0), mat=pvc,
                     parent=root)
        toy.cylinder(f"{name}_cap{t}", pr + 0.006, 0.04, (x1 - 0.02, yc, pz), rotation=(0, math.pi / 2, 0),
                     mat=pvc, parent=root)
        toy.cylinder(f"{name}_hub{t}", pr + 0.008, 0.08, (x0 + 0.04, yc, pz), rotation=(0, math.pi / 2, 0),
                     mat=pvc, parent=root)
        verts, faces = [], []                               # rows of small holes on the visible upper half
        for ang in (math.radians(-60), math.radians(-25), math.radians(25), math.radians(60)):
            nrm = (0.0, -math.sin(ang), math.cos(ang))
            tan = (0.0, math.cos(ang), math.sin(ang))
            x = x0 + 0.2 + (0.06 if ang > 0 else 0.0)
            while x < x1 - 0.1:
                c = (x, yc + nrm[1] * (pr + 0.0015), pz + nrm[2] * (pr + 0.0015))
                base = len(verts)
                for s in range(8):
                    a = 2 * math.pi * s / 8
                    verts.append((c[0] + 0.011 * math.cos(a), c[1] + 0.011 * math.sin(a) * tan[1],
                                  c[2] + 0.011 * math.sin(a) * tan[2]))
                faces.append(tuple(range(base, base + 8)))
                x += 0.12
        st.mesh_obj(f"{name}_holes{t}", verts, faces, (hole_mat,), smooth=False).parent = root
        for k in range(40):                                 # loose stones bedding the pipe
            s = rng.uniform(0.02, 0.04)
            side = rng.choice((-1, 1))
            toy.sphere(f"{name}_stone{t}_{k}", s, (rng.uniform(x0 + 0.1, x1 - 0.1),
                                                     yc + side * rng.uniform(0.07, 0.26), 0.46 + s * 0.3),
                       scale=(1, 0.8, 0.7), mat=stone, parent=root, subdiv=0, segments=8, rings=5)
    for b, (ya, yb) in enumerate(((-0.8, -0.3), (0.3, 0.8), (1.4, 1.5))):
        soil_top = _wave(rng, 0.8, 0.01)
        lawn_top = _wave(rng, 0.9, 0.004)
        _layer(f"{name}_berm{b}", x0, x1, ya, yb, lambda x, y: 0.0, soil_top, 40, 3, soil, root)
        _layer(f"{name}_lawn{b}", x0, x1, ya, yb, soil_top, lawn_top, 40, 3, lawn, root)
    return root


def build_septic_yard_distribution_box():
    """Small grey concrete box on a gravel pad: one pipe in, three pipes out at an even, lower level."""
    name = "septic_yard_distribution_box"
    rng = random.Random(89)
    root = _root(name)
    conc = _concrete()
    pvc = _pvc_grey()
    bore = _surf("septic_yard_dbox_bore", "#2A2A2A", "#151515", scale=20.0, bump=0.05)
    gravel = _surf("septic_yard_dbox_gravel", "#C4C3BD", "#7C7D79", scale=40.0, bump=0.8, rough=0.9, cells=36.0)
    _layer(f"{name}_pad", -0.3, 0.3, -0.3, 0.3, lambda x, y: 0.0, _lumps(rng, 0.06, 0.01, 20.0), 12, 12, gravel,
           root, smooth=True)
    toy.box(f"{name}_body", (0.42, 0.42, 0.36), (0, 0, 0.24), mat=conc, parent=root, bevel=0.012)
    toy.box(f"{name}_lid", (0.46, 0.46, 0.05), (0, 0, 0.445), mat=conc, parent=root, bevel=0.008)
    galv = tx.metal("septic_yard_dbox_galv", "#A9B0B6", rough=0.35)
    for k, x in enumerate((-0.12, 0.12)):
        _torus(f"{name}_handle{k}", 0.03, 0.007, (x, 0, 0.47), (math.pi / 2, 0, 0), galv, root)
    toy.cylinder(f"{name}_inlet", 0.05, 0.12, (-0.27, 0, 0.32), rotation=(0, math.pi / 2, 0), mat=pvc,
                 parent=root)
    toy.cylinder(f"{name}_inlet_bore", 0.042, 0.004, (-0.332, 0, 0.32), rotation=(0, math.pi / 2, 0), mat=bore,
                 parent=root)
    for k, y in enumerate((-0.13, 0.0, 0.13)):
        toy.cylinder(f"{name}_outlet{k}", 0.04, 0.12, (0.27, y, 0.22), rotation=(0, math.pi / 2, 0), mat=pvc,
                     parent=root)
        toy.cylinder(f"{name}_outlet_bore{k}", 0.033, 0.004, (0.332, y, 0.22), rotation=(0, math.pi / 2, 0),
                     mat=bore, parent=root)
    return root


def build_septic_yard_anchor_straps():
    """Long concrete deadman blocks along both sides of the tank base, dark straps looping up and over the
    tank top from one block to the other, tightened with galvanised turnbuckles."""
    name = "septic_yard_anchor_straps"
    root = _root(name)
    conc = st.concrete("septic_yard_as_concrete", "#7A7B7E", lift=0.5, panel=0.8)
    galv = tx.metal("septic_yard_as_galv", "#A9B0B6", rough=0.35)
    strap = tx.cloth("septic_yard_as_strap", "#1C1D20", rough=0.7)
    bw, bh, by = 0.22, 0.25, 0.88                           # block width / height, block centre |y|
    for k, sgn in enumerate((-1, 1)):
        toy.box(f"{name}_block{k}", (2.6, bw, bh), (0, sgn * by, bh / 2), mat=conc, parent=root, bevel=0.02)
    # strap path in y-z: outer face of block 0, over its top, up the tank side, across the lid, down again
    yo, ys, zt, rc = by + bw / 2 + 0.008, 0.758, 1.455, 0.06
    half = [(-yo, 0.03), (-yo, bh + 0.008), (-ys, bh + 0.008)]
    for i in range(7):                                      # rounded tank corner
        a = math.pi - (math.pi / 2) * i / 6
        half.append((-ys + rc + rc * math.cos(a), zt - rc + rc * math.sin(a)))
    path = half + [(-y, z) for y, z in reversed(half)]
    for s, xc in enumerate((-1.05, 0.05, 1.05)):
        verts, faces = [], []
        for y, z in path:
            verts += [(xc - 0.05, y, z), (xc + 0.05, y, z)]
        for i in range(len(path) - 1):
            faces.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
        band = st.mesh_obj(f"{name}_strap{s}", verts, faces, (strap,), smooth=False)
        sol = band.modifiers.new("thick", "SOLIDIFY")
        sol.thickness, sol.offset = 0.01, 0.0
        band.parent = root
        for k, sgn in enumerate((-1, 1)):
            toy.cylinder(f"{name}_turnbuckle{s}_{k}", 0.018, 0.16, (xc, sgn * (ys + 0.02), 0.75), mat=galv,
                         parent=root)
            toy.box(f"{name}_buckle{s}_{k}", (0.12, 0.012, 0.05), (xc, sgn * (ys + 0.012), 0.86), mat=galv,
                    parent=root, bevel=0.003)
            _torus(f"{name}_eye{s}_{k}", 0.035, 0.01, (xc, sgn * (yo + 0.012), 0.12), (0, math.pi / 2, 0), galv,
                   root)
    return root


def build_septic_yard_risers():
    """Two access risers: short ribbed green plastic tubes down to the tank, round green lids flush with a
    square of lawn."""
    name = "septic_yard_risers"
    root = _root(name)
    tube = tx.paint("septic_yard_riser_tube", "#2F4F2E", rough=0.55, coat=0.1)
    lid = tx.paint("septic_yard_riser_green", "#3F7A3B", rough=0.5, coat=0.2)
    galv = tx.metal("septic_yard_riser_screw", "#A9B0B6", rough=0.35)
    lawn = _surf("septic_yard_riser_lawn", "#6BAA45", "#3F7A2A", scale=14.0, bump=0.3)
    centres = ((-0.13, -0.13), (0.13, 0.13))
    turf = toy.box(f"{name}_turf", (0.6, 0.6, 0.04), (0, 0, 0.555), mat=lawn, parent=root, bevel=0)
    for k, (cx, cy) in enumerate(centres):
        st.carve(turf, toy.cylinder(f"{name}_cut{k}", 0.15, 0.2, (cx, cy, 0.555), vertices=32), mat=lawn)
        toy.cylinder(f"{name}_tube{k}", 0.135, 0.56, (cx, cy, 0.28), mat=tube, parent=root, vertices=32)
        toy.cylinder(f"{name}_adapter{k}", 0.15, 0.05, (cx, cy, 0.025), mat=tube, parent=root, vertices=32)
        for r in range(7):                                  # corrugation ribs
            _torus(f"{name}_rib{k}_{r}", 0.135, 0.009, (cx, cy, 0.08 + r * 0.065), (0, 0, 0), tube, root)
        toy.cylinder(f"{name}_lid{k}", 0.155, 0.03, (cx, cy, 0.583), mat=lid, parent=root, vertices=32, bevel=0.006)
        for r in range(3):                                  # moulded ribs on the lid
            toy.box(f"{name}_lid_rib{k}_{r}", (0.26, 0.02, 0.01), (cx, cy, 0.601), rotation=(0, 0, r * math.pi / 3),
                    mat=lid, parent=root, bevel=0)
        for r in range(4):
            a = r * math.pi / 2 + math.pi / 4
            toy.cylinder(f"{name}_screw{k}_{r}", 0.01, 0.006, (cx + 0.125 * math.cos(a), cy + 0.125 * math.sin(a),
                                                               0.6), mat=galv, parent=root, vertices=8)
    return root
