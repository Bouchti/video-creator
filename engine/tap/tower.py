"""Station C, the tower: a concrete pedestal water tower on a low hill above a small town, its steel tank cut in
half (section y = 0) so the water inside shows. The riser comes up the stem from the pumps (-x); a second pipe
runs from the tank floor back down the stem and under the hill to the town's mains (+x). The tank's water level
is a shape key (it drops in the day and the pumps refill it at night)."""
import math
import random

import bmesh
import bpy
from mathutils import Vector

from engine import events
from engine.director import lib
from engine.flush import parts as P
from engine.flush.toilet import boolean

V = Vector
HILL_H = 6.0
G0 = HILL_H                        # ground at the tower's foot (the hill top, x = 0)
STEM_R0, STEM_R1 = 1.75, 2.05      # pedestal: inner, outer radius
STEM_TOP = 27.5
HOLE_R = 1.45                      # opening in the tank floor where the pipes come up
TANK_R, SHELL = 7.3, 0.3
CONE_TOP, WALL_TOP, DOME_TOP = 32.0, 38.0, 41.2
FLOOR_IN = STEM_TOP + SHELL
LEVEL_LOW, LEVEL_FULL = G0 + 28.2, G0 + 31.4
LEVEL_DAY = G0 + 30.0              # 30 m of water above the ground: 3 bar in the town's pipes
PIPE_R = 0.55                      # drawn over life size, so the flow reads in a 50 m wide frame
RISER_X, OUT_X = -0.78, 0.78
DEPTH = 1.9                        # pipes run this deep under the ground
STRIP = 1.0                        # the cut-face ground strip (y 0..STRIP) carries the pipe grooves
TOWN_X0 = 44.0


def ground_z(x, y=0.0):
    hill = HILL_H * math.exp(-(x / 20.0) ** 2 - (y / 40.0) ** 2)
    far = 14.0 / (1.0 + math.exp(-(y - 240.0) / 25.0))           # a line of low hills on the horizon
    return hill + far


def _level_value(z):
    return (z - LEVEL_LOW) / (LEVEL_FULL - LEVEL_LOW)


# ---------------------------------------------------------------- helpers shared with the street station

def ride_dir(ob, path, s, e, speed, offset=0.0, normal_offset=(0, 0, 0), plane="xz"):
    """Like parts.ride, but keyed every frame (no in-between frame when an arrow wraps to the start) and turned
    to point along the path: about Y for arrows in the section plane, about Z for arrows lying flat."""
    path = [V(p) for p in path]
    segs = [(a, b, (b - a).length) for a, b in zip(path, path[1:]) if (b - a).length > 1e-6]
    L = sum(seg for _a, _b, seg in segs)
    lib.visible(ob, 1, False)
    lib.visible(ob, s, True)
    lib.visible(ob, e + 1, False)
    no = V(normal_offset)
    for f in range(s, e + 1):
        d = ((f - s) / 30.0 * speed + offset) % L
        p, t = segs[-1][1], segs[-1][1] - segs[-1][0]
        for a, b, seg in segs:
            if d <= seg:
                p, t = a.lerp(b, d / seg), b - a
                break
            d -= seg
        ob.location = p + no
        if plane == "xz":
            ob.rotation_euler = (0.0, -math.atan2(t.z, t.x), 0.0)
        else:
            ob.rotation_euler = (0.0, 0.0, math.atan2(t.y, t.x))
        ob.keyframe_insert("location", frame=f)
        ob.keyframe_insert("rotation_euler", frame=f)
    for fc in lib.fcurves(ob):
        if fc.data_path in ("location", "rotation_euler"):
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"


def key_shape(ob, block, frame, value, interp="LINEAR"):
    kb = ob.data.shape_keys.key_blocks[block]
    kb.value = value
    kb.keyframe_insert("value", frame=frame)
    for fc in lib.fcurves(ob.data.shape_keys):
        if fc.data_path == f'key_blocks["{block}"].value':
            for kp in fc.keyframe_points:
                if abs(kp.co.x - frame) < 0.5:
                    kp.interpolation = interp


def key_socket(sock, frame, value, interp="LINEAR"):
    lib.node_key(sock, frame, value, interp)


def strip_terrain(name, x0, x1, step, zfun, y0, y1, top_mat, cut_mat, parent, bottom=-400.0):
    """A ground slab between y0 and y1 whose top follows zfun(x, y): front face (y0) = the section (cut_mat),
    built from quads (a long notched n-gon triangulates badly)."""
    xs = [x0 + k * step for k in range(int(round((x1 - x0) / step)) + 1)]
    bm = bmesh.new()
    ft = [bm.verts.new((x, y0, zfun(x, y0))) for x in xs]
    bt = [bm.verts.new((x, y1, zfun(x, y1))) for x in xs]
    fb = [bm.verts.new((x, y0, bottom)) for x in xs]
    bb = [bm.verts.new((x, y1, bottom)) for x in xs]
    for i in range(len(xs) - 1):
        bm.faces.new((ft[i], ft[i + 1], bt[i + 1], bt[i])).material_index = 0
        bm.faces.new((fb[i], fb[i + 1], ft[i + 1], ft[i])).material_index = 1
        bm.faces.new((bt[i], bt[i + 1], bb[i + 1], bb[i])).material_index = 1
        bm.faces.new((bb[i], bb[i + 1], fb[i + 1], fb[i])).material_index = 1
    bm.faces.new((ft[0], bt[0], bb[0], fb[0])).material_index = 1
    bm.faces.new((fb[-1], bb[-1], bt[-1], ft[-1])).material_index = 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = lib.mesh_from_bm(name, bm, None, parent)
    ob.data.materials.append(top_mat)
    ob.data.materials.append(cut_mat)
    return ob


def carve(solid, pts, radius, bend=1.2, step=0.2):
    """A pipe groove in a solid's cut face. The exact boolean returns an EMPTY mesh when the groove's rings are
    much denser than the solid's own vertices (a 5 cm step on a 1 m ground strip did): 0.2 m rings are safe."""
    before = len(solid.data.polygons)
    boolean(solid, P.solid_tube(f"{solid.name}_groove", pts, radius, solid.data.materials[min(1, len(solid.data.materials) - 1)], solid.parent,
                                bend=bend, step=step))
    if not solid.data.polygons:
        raise RuntimeError(f"carving {solid.name} emptied it (it had {before} faces)")
    return solid


def heightfield(name, xs, ys, zfun, mat, parent):
    bm = bmesh.new()
    grid = [[bm.verts.new((x, y, zfun(x, y))) for x in xs] for y in ys]
    for j in range(len(ys) - 1):
        for i in range(len(xs) - 1):
            f = bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
            f.smooth = True
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    return lib.mesh_from_bm(name, bm, mat, parent)


def _dome(r, z0, z1, n=10, inset=0.0):
    out = []
    for k in range(1, n + 1):
        t = math.pi / 2 * k / n
        out.append(((r - inset) * math.cos(t), z0 + (z1 - z0 - inset) * math.sin(t)))
    return out


def _liner(d):
    """The tank's inner surface moved d into the tank (shell thickness included), from the dome top to the hole."""
    r_in = TANK_R - SHELL
    dr, dz = r_in - 2.3, CONE_TOP + 0.1 - FLOOR_IN
    L = math.hypot(dr, dz)
    nr, nz = -dz / L, dr / L                       # the cone's normal, into the tank
    e = d - SHELL                                   # offset beyond the shell's inner surface
    r0, z0 = 2.3 + nr * e, FLOOR_IN + nz * e        # a point on the offset cone line
    s_wall = (r_in - e - r0) / dr
    s_floor = (FLOOR_IN + e - z0) / dz
    pts = list(reversed(_dome(TANK_R, WALL_TOP, DOME_TOP, inset=d)))
    pts += [(r_in - e, WALL_TOP), (r_in - e, z0 + s_wall * dz), (r0 + s_floor * dr, FLOOR_IN + e),
            (HOLE_R + 0.03, FLOOR_IN + e)]
    return pts


# ---------------------------------------------------------------- build

def build_tower(self):
    R = self.root("tower")
    rnd = random.Random(11)
    grass = lib.material("Grass004", scale=0.16, tint=(0.82, 0.96, 0.7), name="tw_grass")
    soil = P.soil()
    paint = lib.flat("tw_tank_paint", lib.hexrgb("#E8EDF0"), 0.5, metallic=0.1, coat=0.1)
    shell_cut = lib.flat("tw_tank_cut", lib.hexrgb("#7F8C95"), 0.5, metallic=0.4)
    stem_mat = lib.material("Concrete034", scale=0.3, tint=(1.0, 0.99, 0.96), name="tw_stem")
    stem_cut = lib.flat("tw_stem_cut", lib.hexrgb("#C9C3B8"), 0.85)
    blue = lib.flat("tw_band_blue", lib.hexrgb("#2F6DB0"), 0.4, coat=0.3)
    pipe = lib.flat("tw_pipe", lib.hexrgb("#3A6EA8"), 0.35, metallic=0.3, coat=0.3)
    pipe_cut = lib.flat("tw_pipe_cut", lib.hexrgb("#A9C1D8"), 0.45, metallic=0.3)
    flow = P.water("tw_flow", P.CLEAN[0], P.CLEAN[1], speed=2.2, foam_amount=0.32, scale=(0.6, 3.0, 3.0))
    flow_cut = P.water_section("tw_flow_cut", P.CLEAN[0], P.CLEAN[2])
    conc = P.concrete()

    # ---- pipe routes (station-local, in the section plane)
    def under(x0, x1, step=5.0):
        n = max(1, int(round(abs(x1 - x0) / step)))
        return [(x0 + (x1 - x0) * k / n, 0, ground_z(x0 + (x1 - x0) * k / n) - DEPTH) for k in range(n + 1)]
    self.tw_riser = under(-150.0, RISER_X - 3.0) + [(RISER_X, 0, G0 - DEPTH), (RISER_X, 0, FLOOR_IN + 1.3)]
    self.tw_outlet = [(OUT_X, 0, FLOOR_IN + 0.35), (OUT_X, 0, G0 - DEPTH)] + under(OUT_X + 3.0, 170.0)

    # ---- ground: the cut-face strip (with the pipe grooves) and the hill and town behind it
    strip = strip_terrain("tw_strip", -260, 340, 1.0, ground_z, 0.0, STRIP, grass, soil, R)
    pad_x = 3.4
    boolean(strip, lib.box("tw_pad_hole", -pad_x - 0.01, pad_x + 0.01, -1, 4, G0 - 1.31, G0 + 3, conc, R))
    pad = lib.box("tw_pad", -pad_x, pad_x, 0, pad_x, G0 - 1.3, G0 + 0.08, conc, R)
    for k, pts in enumerate((self.tw_riser, self.tw_outlet)):
        for solid in (strip, pad):
            carve(solid, pts, PIPE_R + 0.006)
    xs = [-260 + 2.5 * k for k in range(241)]
    ys = [STRIP + 1.5 * k for k in range(27)] + [STRIP + 39 + 6 * k for k in range(45)]
    heightfield("tw_land", xs, ys, ground_z, grass, R)
    lib.box("tw_far", -400, 500, ys[-1] - 1, 900, -1.0, ground_z(0, ys[-1]) - 0.08, grass, R)

    # ---- the pedestal (cut in half) and the tank
    P.revolve_half("tw_stem", [(STEM_R0, G0 - 1.0), (STEM_R1, G0 - 1.0), (STEM_R1, STEM_TOP), (STEM_R0, STEM_TOP)],
                   (0, 0, 0), stem_mat, stem_cut, R, n=96)
    P.revolve_half("tw_flare", [(STEM_R1, STEM_TOP - 2.2), (STEM_R1 + 0.02, STEM_TOP - 2.2), (2.6, STEM_TOP),
                                (STEM_R1, STEM_TOP)], (0, 0, 0), stem_mat, stem_cut, R, n=96)
    shell = ([(HOLE_R, STEM_TOP), (2.4, STEM_TOP), (TANK_R, CONE_TOP), (TANK_R, WALL_TOP)]
             + _dome(TANK_R, WALL_TOP, DOME_TOP))
    inner = list(reversed(_dome(TANK_R, WALL_TOP, DOME_TOP, inset=SHELL)))
    inner += [(TANK_R - SHELL, WALL_TOP), (TANK_R - SHELL, CONE_TOP + 0.1), (2.3, FLOOR_IN), (HOLE_R, FLOOR_IN)]
    P.revolve_half("tw_tank", shell + inner, (0, 0, 0), paint, shell_cut, R, n=128)
    # a matte lining inside the shell: the bare inside reflected the sky and the roof read as glass (an open cup)
    inside = lib.flat("tw_tank_inside", lib.hexrgb("#D3D8DA"), 0.85)
    P.revolve_half("tw_liner", _liner(SHELL + 0.006) + list(reversed(_liner(SHELL + 0.024))), (0, 0, 0), inside,
                   shell_cut, R, n=128)
    # a soft lamp under the roof: in the sun the dome's inside sat in deep shade and the roof did not read
    lamp_in = bpy.data.lights.new("tw_tank_lamp", "POINT")
    lamp_in.energy, lamp_in.shadow_soft_size, lamp_in.color = 2600.0, 1.5, (1.0, 0.98, 0.95)
    lob = bpy.data.objects.new("tw_tank_lamp", lamp_in)
    bpy.context.scene.collection.objects.link(lob)
    lob.parent = R
    lob.location = (0.0, 2.5, WALL_TOP + 0.6)
    P.revolve_half("tw_band", [(TANK_R + 0.006, 34.4), (TANK_R + 0.03, 34.4), (TANK_R + 0.03, 35.8),
                               (TANK_R + 0.006, 35.8)], (0, 0, 0), blue, blue, R, n=128)
    # the catwalk around the tank's waist, with a railing
    rail = lib.flat("tw_rail", lib.hexrgb("#5D6870"), 0.4, metallic=0.8)
    P.revolve_half("tw_walk", [(TANK_R, CONE_TOP - 0.12), (TANK_R + 0.9, CONE_TOP - 0.12), (TANK_R + 0.9, CONE_TOP),
                               (TANK_R, CONE_TOP)], (0, 0, 0), rail, rail, R, n=128)
    P.revolve_half("tw_toprail", [(TANK_R + 0.85, CONE_TOP + 1.05), (TANK_R + 0.9, CONE_TOP + 1.05),
                                  (TANK_R + 0.9, CONE_TOP + 1.1), (TANK_R + 0.85, CONE_TOP + 1.1)], (0, 0, 0),
                   rail, rail, R, n=128)
    for k in range(19):
        a = math.pi * (k + 0.5) / 19
        r = TANK_R + 0.87
        lib.tube(f"tw_post{k}", [(r * math.cos(a), r * math.sin(a), CONE_TOP),
                                 (r * math.cos(a), r * math.sin(a), CONE_TOP + 1.1)], 0.03, rail, R, resolution=8)
    # a ladder up the inside of the stem (behind the pipes)
    lx, ly = -1.15, 1.25
    for sx in (-0.22, 0.22):
        lib.box(f"tw_ladder_rail{sx}", lx + sx - 0.03, lx + sx + 0.03, ly, ly + 0.05, G0, STEM_TOP, rail, R)
    for k in range(int((STEM_TOP - G0) / 0.6)):
        z = G0 + 0.4 + k * 0.6
        lib.box(f"tw_rung{k}", lx - 0.22, lx + 0.22, ly + 0.01, ly + 0.04, z, z + 0.04, rail, R)
    lib.box("tw_stem_floor", -STEM_R0, STEM_R0, 0.0, STEM_R0, G0 - 0.02, G0 + 0.1, conc, R)

    # ---- the water in the tank: one closed body whose top ring rides a shape key (low .. full)
    tank_w = P.water_glass("tw_tank_water", "#9ED5EE", alpha=0.42, foam="#E2F4FD", speed=0.08)
    tank_cut = P.water_glass("tw_tank_water_cut", "#4AA3D3", alpha=0.62)
    cone_r = lambda z: 2.3 + (z - FLOOR_IN) * (TANK_R - SHELL - 2.3) / (CONE_TOP + 0.1 - FLOOR_IN)  # noqa: E731
    prof = [(0.0, FLOOR_IN + 0.04), (cone_r(FLOOR_IN + 0.04) - 0.06, FLOOR_IN + 0.04),
            (TANK_R - SHELL - 0.05, CONE_TOP + 0.1), (TANK_R - SHELL - 0.05, LEVEL_LOW), (0.0, LEVEL_LOW)]
    water = P.revolve_half("tw_water", prof, (0, 0.012, 0), tank_w, tank_cut, R, n=128)
    water.shape_key_add(name="Basis")
    full = water.shape_key_add(name="full")
    for v, kv in zip(water.data.vertices, full.data):
        if abs(v.co.z - LEVEL_LOW) < 1e-4:
            kv.co.z = LEVEL_FULL
    full.value = _level_value(LEVEL_DAY)
    self.tw_water = water

    # ---- the pipes: blue ductile iron, cut lengthwise, running full
    for name, pts in (("tw_riser", self.tw_riser), ("tw_outlet", self.tw_outlet)):
        P.half_pipe(name, pts, PIPE_R, mat=pipe, cut_mat=pipe_cut, parent=R, bend=1.2, step=0.4)
        P.pipe_water(f"{name}_w", pts, PIPE_R, level=0.97, mat=flow, section_mat=flow_cut, parent=R, bend=1.2,
                     step=0.4)
    # bell mouths where the pipes open into the tank
    for name, x, z in (("tw_riser_mouth", RISER_X, FLOOR_IN + 1.3), ("tw_outlet_mouth", OUT_X, FLOOR_IN + 0.35)):
        P.revolve_half(name, [(PIPE_R - 0.04, z - 0.25), (PIPE_R + 0.02, z - 0.25), (PIPE_R + 0.18, z),
                              (PIPE_R + 0.12, z)], (x, 0, 0), pipe, pipe_cut, R, n=48)
    self.tw_riser_path = P.resample(P.rounded(self.tw_riser, 1.2), 0.3) + [V((RISER_X, 0, FLOOR_IN + 3.4))]
    self.tw_outlet_path = P.resample(P.rounded(self.tw_outlet, 1.2), 0.3)
    self.tw_arrows_up = [P.arrow(f"tw_arrow_up{k}", (0, 0, 0), (1, 0, 0), size=0.85, parent=R) for k in range(9)]
    self.tw_arrows_down = [P.arrow(f"tw_arrow_dn{k}", (0, 0, 0), (1, 0, 0), size=0.85, parent=R) for k in range(9)]

    # ---- the town below the hill (+x), and trees
    glow = lib.flat("tw_window", lib.hexrgb("#9DB8CC"), 0.05, coat=1.0)
    nt, bsdf = lib._bsdf(glow)
    bsdf.inputs["Emission Color"].default_value = (*lib.hexrgb("#FFC978"), 1)
    bsdf.inputs["Emission Strength"].default_value = 0.0
    self.tw_glow = bsdf.inputs["Emission Strength"]
    walls = ("#EDE3CF", "#E6DCCB", "#F1E9DA", "#E9D8C0", "#F3E6D0")
    shutters = ("#4F7FB3", "#3E8E6B", "#B5523B", "#7A5C8E")
    asphalt = lib.material("Asphalt031", scale=0.2, tint=(0.8, 0.8, 0.82), name="tw_asphalt")
    for k, y in enumerate((15.5, 30.5, 45.5)):
        lib.box(f"tw_road{k}", TOWN_X0 - 2, 240, y - 2.6, y + 2.6, -0.3, ground_z(TOWN_X0, y) + 0.05, asphalt, R)
    lib.box("tw_road_x", TOWN_X0 - 2, TOWN_X0 + 3, 6.0, 70, -0.3, ground_z(TOWN_X0, 10) + 0.05, asphalt, R)
    lamp = lib.flat("tw_lamp", lib.hexrgb("#FFE2A8"), 0.4)
    _, lbsdf = lib._bsdf(lamp)
    lbsdf.inputs["Emission Color"].default_value = (*lib.hexrgb("#FFD38A"), 1)
    self.tw_lamp_glow = lbsdf.inputs["Emission Strength"]
    self.tw_lamp_glow.default_value = 0.0
    n_house = 0
    for row, y in enumerate((8.5, 23.0, 38.0, 53.0)):
        for col in range(8):
            x = TOWN_X0 + 6.0 + col * 13.5 + rnd.uniform(-1.5, 1.5)
            if rnd.random() < 0.12:
                continue
            h = P.house(f"tw_house{n_house}", (x, y + rnd.uniform(-0.6, 0.6), ground_z(x, y) - 0.02),
                        w=rnd.uniform(6.5, 8.0), d=6.0, yaw=rnd.choice((0, 0, 180)), parent=R,
                        wall_hex=walls[n_house % len(walls)], shutter_hex=shutters[n_house % len(shutters)])
            for o in h.children_recursive:
                if "_win" in o.name and o.type == "MESH":
                    o.data.materials.clear()
                    o.data.materials.append(glow)
            n_house += 1
    for k in range(10):
        x = TOWN_X0 + 4 + k * 13.0
        lib.tube(f"tw_lamp_pole{k}", [(x, 12.6, 0.0), (x, 12.6, 4.5), (x, 13.4, 4.7)], 0.07, rail, R, resolution=8)
        lib.blob(f"tw_lamp_head{k}", 0.22, lamp, (x, 13.5, 4.6), squash=0.5, parent=R, lumpy=0.0)
    for k in range(26):
        x = rnd.uniform(-120, 160)
        y = rnd.uniform(6, 90)
        if abs(x) < 12 and y < 20:
            continue
        if x > TOWN_X0 - 3 and y < 60 and rnd.random() < 0.6:
            continue
        P.tree(f"tw_tree{k}", (x, y, ground_z(x, y) - 0.1), h=rnd.uniform(5.5, 8.5), parent=R, seed=70 + k)
    for k, (x, y) in enumerate(((-14, 9), (-22, 16), (15, 11), (24, 22), (-9, 26))):
        P.tree(f"tw_hilltree{k}", (x, y, ground_z(x, y) - 0.1), h=6.5, parent=R, seed=90 + k)

    # ---- night lights (off by day): a floodlight on the tank and a cool moon fill
    flood = bpy.data.lights.new("tw_flood", "SPOT")
    flood.energy, flood.spot_size, flood.spot_blend = 0.0, math.radians(62), 0.9
    flood.color = (1.0, 0.93, 0.82)
    flood.shadow_soft_size = 0.0
    flood.use_shadow = False              # (its shadow map acned the whole dome at this distance)
    fob = bpy.data.objects.new("tw_flood", flood)
    bpy.context.scene.collection.objects.link(fob)
    fob.parent = R
    fob.location = (6.0, -26.0, G0 + 4.0)
    tgt = lib.empty("tw_flood_aim", (0, 0, 33.0), R)
    con = fob.constraints.new("TRACK_TO")
    con.target, con.track_axis, con.up_axis = tgt, "TRACK_NEGATIVE_Z", "UP_Y"
    moon = bpy.data.lights.new("tw_moon", "SUN")
    moon.energy, moon.color, moon.angle = 0.0, (0.62, 0.72, 1.0), math.radians(2)
    mob = bpy.data.objects.new("tw_moon", moon)
    bpy.context.scene.collection.objects.link(mob)
    mob.parent = R
    mob.rotation_euler = (math.radians(50), 0, math.radians(-30))
    self.tw_flood, self.tw_moon = flood, moon

    # ---- anchors for the compositor's ruler: the ground at the stem and the water surface at the tank wall
    self.anchor("tower", "tower_base", (-STEM_R1 - 0.05, -0.06, G0 + 0.08))
    self.anchor("tower", "tower_top", (-(TANK_R - SHELL) + 0.15, -0.06, LEVEL_DAY))
    return R


# ---------------------------------------------------------------- shots

def _length(path):
    return sum((V(b) - V(a)).length for a, b in zip(path, path[1:]))


def _near_tower(path, reach=34.0):
    """The part of a pipe within `reach` metres (in x) of the tower: the arrows ride only where they can be seen."""
    return [p for p in path if abs(V(p).x) <= reach]


def _flow(self, s, e, up=True, down=True, speed=3.2):
    for arrows, path, on in ((self.tw_arrows_up, self.tw_riser_path, up),
                             (self.tw_arrows_down, self.tw_outlet_path, down)):
        if not on:
            continue
        sub = _near_tower(path)
        L = _length(sub)
        for k, a in enumerate(arrows):
            ride_dir(a, sub, s, e, speed, offset=k * L / len(arrows), normal_offset=(0, -0.03, 0))


def tower(self, s, e):
    self.on_station("tower", s, e)
    self.shot("tower", s, e, dict(center=(11.0, 0, 19.0), width=52.0, yaw=-27, pitch=-8, lens=24),
              dict(center=(10.0, 0, 19.5), width=48.0, yaw=-22, pitch=-7, lens=24))
    _flow(self, s, e)
    events.add(s, "water_rush", duration=e - s, gain=0.35)
    events.add(s, "wind", duration=e - s, gain=0.3)


def pressure(self, s, e):
    self.on_station("tower", s, e)
    self.shot("tower", s, e, dict(center=(-4.6, 0, 18.4), width=48.0, yaw=2, pitch=2, lens=35),
              dict(center=(-4.4, 0, 18.6), width=46.5, yaw=4, pitch=2, lens=35))
    _flow(self, s, e, up=False, speed=4.2)
    events.add(s, "water_rush", duration=e - s, gain=0.45)


def night(self, s, e):
    self.on_station("tower", s, e)
    self.shot("tower", s, e, dict(center=(7.0, 0, 27.0), width=36.0, yaw=-22, pitch=5, lens=30),
              dict(center=(6.0, 0, 28.0), width=32.0, yaw=-18, pitch=5, lens=30))
    n = e - s
    dusk, dark = s + int(n * 0.12), s + int(n * 0.42)
    sun, bg = self.sun.data, self.world_bg.inputs["Strength"]
    day_e, day_bg, day_col = sun.energy, bg.default_value, tuple(sun.color)
    # daylight held up to the beat, dusk, night, then daylight back for whatever follows
    for f, energy, strength, col, glow, interp in (
            (s - 1, day_e, day_bg, day_col, 0.0, "CONSTANT"),
            (dusk, day_e, day_bg, day_col, 0.0, "SINE"),
            ((dusk + dark) // 2, day_e * 0.35, day_bg * 0.4, (1.0, 0.55, 0.32), 1.5, "SINE"),
            (dark, 0.0, day_bg * 0.07, (1.0, 0.55, 0.32), 9.0, "CONSTANT"),
            (e + 1, day_e, day_bg, day_col, 0.0, "CONSTANT")):
        lib.key(sun, "energy", f, energy, interp=interp, easing="EASE_IN_OUT")
        lib.key(sun, "color", f, col, interp=interp, easing="EASE_IN_OUT")
        lib.node_key(bg, f, strength, interp, "EASE_IN_OUT")
        lib.node_key(self.tw_glow, f, glow, interp, "EASE_IN_OUT")
        lib.node_key(self.tw_lamp_glow, f, glow * 1.4, interp, "EASE_IN_OUT")
    for light, on in ((self.tw_flood, 160000.0), (self.tw_moon, 0.5)):
        for f, v, interp in ((s - 1, 0.0, "CONSTANT"), ((dusk + dark) // 2, 0.0, "SINE"), (dark, on, "CONSTANT"),
                             (e + 1, 0.0, "CONSTANT")):
            lib.key(light, "energy", f, v, interp=interp, easing="EASE_IN_OUT")
    # the town sleeps (no flow out); the pumps refill the tank
    w = self.tw_water
    key_shape(w, "full", s - 1, _level_value(LEVEL_DAY), "CONSTANT")
    key_shape(w, "full", s, 0.12, "CONSTANT")
    key_shape(w, "full", dark - 6, 0.12, "SINE")
    key_shape(w, "full", e, 0.96, "CONSTANT")
    key_shape(w, "full", e + 1, _level_value(LEVEL_DAY), "CONSTANT")
    _flow(self, dark - 10, e, down=False, speed=3.6)
    events.add(dark - 10, "pump", duration=e - dark + 10, gain=0.6)
    events.add(dark - 10, "hum", duration=e - dark + 10, gain=0.4)
    events.add(dark, "bubbles", duration=e - dark, gain=0.35)


SHOTS = (build_tower, tower, pressure, night)
