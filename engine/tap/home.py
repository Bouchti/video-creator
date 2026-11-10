"""Station A, home: a two-storey house cut through the middle (section y = 0). The supply pipe comes in under
the front yard from the street (+x), rises inside the right-hand wall, feeds the kitchen sink tap on the ground
floor and the bathroom basin tap upstairs. Pipes on the section plane are cut lengthwise and run full: tap
water is pushed, so its pipes never run half empty like a drain."""
import math

import bmesh
from mathutils import Vector

from engine import events
from engine.director import lib
from engine.flush import parts as P
from engine.flush.toilet import boolean

V = Vector
FLOOR_Z = 0.18                     # ground floor (top of the tiles)
UP_Z = 3.0                         # upstairs floor
CEIL_Z = 2.78                      # kitchen ceiling (underside of the upstairs slab)
TOP_Z = 5.6                        # top of the upstairs walls
RW0, RW1 = 1.6, 1.9                # the right-hand (street-side) exterior wall
RX = 1.75                          # the riser, inside that wall
PIPE_R = 0.035                     # supply pipe (drawn a little over life size so it reads)
COUNTER = (-1.5, RW0, 0.0, 0.62, FLOOR_Z + 0.86, FLOOR_Z + 0.9)
SX = 0.62                          # kitchen sink centre (x)
SINK_R, SINK_D = 0.22, 0.2
TAP = (SX, 0.42)                   # the kitchen tap's base (x, y), on the counter
BX = 0.95                          # bathroom basin centre (x)
BASIN_Z = UP_Z + 0.85
SUPPLY_Z = -0.85
YARD_X1 = 16.0
SUPPLY = [(YARD_X1, 0, SUPPLY_Z), (RX, 0, SUPPLY_Z), (RX, 0, BASIN_Z + 0.28), (RW0 - 0.02, 0, BASIN_Z + 0.28)]
KITCHEN_BRANCH = [(RX, 0, FLOOR_Z + 0.5), (SX + 0.42, 0, FLOOR_Z + 0.5), (SX + 0.42, 0, FLOOR_Z + 0.7)]


def chrome():
    return lib.flat("chrome", lib.hexrgb("#E8ECEF"), 0.06, metallic=1.0)


def glass_mat():
    if P.PATH_TRACED:
        # refractive glass with caustics off lets no light inside a closed glass: it rendered black in Cycles.
        # Alpha glass passes shadow rays, so the water in it stays lit; the coat keeps its highlights.
        return lib.flat("glass_clear", lib.hexrgb("#F4FBFF"), 0.02, alpha=0.16, coat=1.0)
    return lib.flat("glass_clear", lib.hexrgb("#F4FBFF"), 0.02, transmission=1.0, coat=0.3)


def tap_water():
    return P.water("tap_water", "#CDEFFC", "#FFFFFF", speed=2.0, foam_amount=0.35, scale=(6.0, 3.0, 3.0),
                   rough=0.03, glass=0.85)


def build_home(self):
    R = self.root("home")
    conc = P.concrete()
    plaster = lib.material("PaintedPlaster017", scale=0.8, tint=lib.hexrgb("#F1EBDF"), name="plaster_in")
    outside = lib.material("PaintedPlaster017", scale=0.8, tint=lib.hexrgb("#E9DFCB"), name="plaster_out")
    tiles = P.tiles()
    wall_tiles = P.tiles("tiles_blue", "#CFE3EE", "#A9BCC6", 0.15)
    wood = lib.flat("oak_floor", lib.hexrgb("#B88A5A"), 0.45)
    cutface = lib.flat("wall_cut", lib.hexrgb("#D9D2C4"), 0.8)
    copper = lib.flat("copper", lib.hexrgb("#C9794A"), 0.25, metallic=1.0)
    copper_cut = lib.flat("copper_cut", lib.hexrgb("#E39A6B"), 0.3, metallic=1.0)
    full = P.water("supply_flow", "#BFEAF9", "#F6FDFF", speed=0.9, foam_amount=0.25)
    full_cut = P.water_section("supply_cut", "#BFEAF9", "#5FB4DA")
    self.home_full = full

    def carve_into(solid, pts, r=PIPE_R):
        t = P.solid_tube(f"{solid.name}_groove", pts, r + 0.004, solid.data.materials[0], R, bend=0.12)
        return boolean(solid, t)

    # ---- ground: under the house, and the front yard toward the street (+x)
    under = P.soil_block("home_soil_under", -7.2, RW1 + 0.05, 0, 6, -400.0, -0.2, R, deep_below=-2.4)
    yard = P.soil_block("home_soil_yard", RW1 + 0.05, YARD_X1 + 40, 0, 6, -400.0, -0.04, R, deep_below=-2.4)
    for solid in (under, yard):
        carve_into(solid, SUPPLY[:3])
    P.lawn("home_lawn", RW1 + 0.05, YARD_X1 + 40, 0, 6, z=0.0, parent=R, density=300)
    lib.box("home_far_turf", -200, 200, 6, 300, -0.04, 0.0, P.grass_top(), R)
    lib.box("home_far_soil", -200, 200, 6, 300, -400, -0.04, P.soil(), R)
    lib.box("home_left_soil", -200, -7.2, 0, 6, -400, -0.04, P.soil(), R)
    lib.box("home_left_turf", -200, -7.2, -0.03, 6, -0.04, 0.0, P.grass_top(), R)
    slab = lib.box("home_slab", -7.2, RW1, -0.006, 6.0, -0.2, FLOOR_Z - 0.03, conc, R)
    footing = lib.box("home_footing", RW0, RW1 + 0.05, -0.006, 6.0, -1.0, -0.19, conc, R)
    carve_into(footing, SUPPLY[:3])
    lib.box("kitchen_floor", -7.2, RW0, -0.004, 5.7, FLOOR_Z - 0.03, FLOOR_Z, tiles, R)
    _ = slab

    # ---- walls, ceilings, roof (cut through the middle)
    right_low = lib.box("wall_right_low", RW0, RW1, 0, 6.0, FLOOR_Z, CEIL_Z, outside, R)
    right_up = lib.box("wall_right_up", RW0, RW1, 0, 6.0, CEIL_Z, TOP_Z, outside, R)
    for w in (right_low, right_up):
        carve_into(w, SUPPLY[1:])
    carve_into(right_low, KITCHEN_BRANCH[:2])
    lib.box("wall_left", -7.2, -6.9, 0, 6.0, FLOOR_Z, TOP_Z, outside, R)
    lib.box("wall_back", -7.2, RW1, 5.7, 6.0, FLOOR_Z, TOP_Z, outside, R)
    upslab = lib.box("up_slab", -7.2, RW0, 0, 5.7, CEIL_Z, UP_Z - 0.02, plaster, R)
    lib.box("up_floor", -7.2, RW0, -0.004, 5.7, UP_Z - 0.02, UP_Z, wood, R)
    _ = upslab
    lib.box("kitchen_back_tiles", -1.5, RW0, 0.78, 0.86, COUNTER[5], COUNTER[5] + 0.62, wall_tiles, R)
    lib.box("kitchen_back", -1.5, RW0, 0.86, 0.98, FLOOR_Z, CEIL_Z, plaster, R)
    lib.box("partition", -1.62, -1.5, 0, 5.7, FLOOR_Z, CEIL_Z, plaster, R)
    lib.box("bath_back", -0.9, RW0, 0.9, 1.02, UP_Z, TOP_Z, wall_tiles, R)
    lib.box("bath_partition", -1.02, -0.9, 0, 5.7, UP_Z, TOP_Z, plaster, R)
    lib.box("ceiling_up", -7.2, RW1, 0, 6.0, TOP_Z, TOP_Z + 0.18, plaster, R)
    roof = lib.material("RoofingTiles006", scale=0.9, tint=(1.0, 0.62, 0.48), name="roof_tiles")
    _gable_roof(R, -7.6, RW1 + 0.4, 0, 6.4, TOP_Z + 0.18, 2.1, roof, cutface)
    win = lib.flat("window_glass", lib.hexrgb("#9DB8CC"), 0.05, coat=1.0)
    trim = lib.flat("trim_white", (0.92, 0.92, 0.9), 0.4)
    for k, (x0, x1, z0, z1) in enumerate(((-5.6, -3.6, 1.0, 2.2), (-5.6, -3.6, UP_Z + 0.9, UP_Z + 2.1))):
        lib.box(f"win_back{k}", x0, x1, 5.68, 5.71, z0, z1, win, R)
        lib.box(f"win_back_frame{k}", x0 - 0.08, x1 + 0.08, 5.66, 5.69, z0 - 0.08, z1 + 0.08, trim, R)

    # ---- kitchen: counter cut open (we see the cabinet's inside), a round sink, the tap, wall cupboards
    x0, x1, y0, y1, zc0, zc1 = COUNTER
    top_mat = lib.flat("worktop", lib.hexrgb("#3A3F44"), 0.25, coat=0.4)
    worktop = lib.box("worktop", x0, x1, y0, y1 + 0.16, zc0, zc1, top_mat, R)
    boolean(worktop, P.cylinder("sink_hole", (SX, 0.0), SINK_R + 0.01, zc0 - 0.1, zc1 + 0.1, top_mat, R))
    cab = lib.flat("cabinet", lib.hexrgb("#F2EFE8"), 0.5)
    lib.box("cab_back", x0, x1, y1 + 0.1, y1 + 0.14, FLOOR_Z, zc0, cab, R)
    lib.box("cab_floor", x0, x1, 0.0, y1 + 0.14, FLOOR_Z, FLOOR_Z + 0.1, cab, R)
    for k, x in enumerate((x0, -0.3, 0.95)):
        side = lib.box(f"cab_side{k}", x, x + 0.03, 0.0, y1 + 0.14, FLOOR_Z, zc0, cab, R)
        if k == 2:
            carve_into(side, KITCHEN_BRANCH[:2])
    lib.box("cab_shelf", x0, -0.3, 0.0, y1 + 0.1, FLOOR_Z + 0.45, FLOOR_Z + 0.47, cab, R)
    steel_sink = lib.flat("sink_steel", lib.hexrgb("#C9CED2"), 0.22, metallic=1.0)
    P.revolve_half("sink_bowl", [(SINK_R, 0.0), (SINK_R + 0.02, 0.0), (SINK_R + 0.02, -SINK_D),
                                 (0.0, -SINK_D - 0.02), (0.0, -SINK_D), (SINK_R, -SINK_D + 0.02)],
                   (SX, 0.0, zc1), steel_sink, lib.flat("sink_cut", lib.hexrgb("#DADFE3"), 0.4), R, n=64)
    self.sink_floor = zc1 - SINK_D
    _kitchen_tap(self, R, copper)
    # the drain under the sink (grey, it is not part of this story but a sink without one looks wrong)
    P.half_pipe("sink_drain", [(SX, 0, zc1 - SINK_D), (SX, 0, FLOOR_Z + 0.22), (SX - 0.45, 0, FLOOR_Z + 0.22),
                               (SX - 0.45, 0, FLOOR_Z - 0.1)], 0.03, parent=R, bend=0.06)
    upper = lib.flat("cupboard", lib.hexrgb("#7FA7B8"), 0.45)
    lib.box("cupboard", -1.4, 1.5, 0.5, 0.86, 1.75, 2.45, upper, R, bevel=0.01)
    lib.box("fridge", -1.45, -0.62, 0.15, 0.86, FLOOR_Z, 2.05, lib.flat("fridge", lib.hexrgb("#E9ECEE"), 0.2, coat=0.6),
            R, bevel=0.02)
    # living room: a sofa, a rug, a lamp
    sofa = lib.flat("sofa", lib.hexrgb("#C9784B"), 0.8)
    lib.box("sofa_seat", -5.8, -3.6, 1.2, 2.2, FLOOR_Z, FLOOR_Z + 0.45, sofa, R, bevel=0.05)
    lib.box("sofa_back", -5.8, -3.6, 2.0, 2.3, FLOOR_Z, FLOOR_Z + 0.95, sofa, R, bevel=0.05)
    lib.box("rug", -6.2, -2.4, 0.3, 3.4, FLOOR_Z, FLOOR_Z + 0.012, lib.flat("rug", lib.hexrgb("#D9C9A6"), 0.95), R)
    lib.tube("lamp_pole", [(-2.3, 2.4, FLOOR_Z), (-2.3, 2.4, FLOOR_Z + 1.55)], 0.015, P.dark_steel(), R)
    lib.blob("lamp_shade", 0.2, lib.flat("lampshade", lib.hexrgb("#F6E7C8"), 0.6, emission=1.2),
             (-2.3, 2.4, FLOOR_Z + 1.6), squash=0.8, parent=R, lumpy=0.0)

    # ---- upstairs bathroom: a wall-hung basin with a wall spout, a mirror, a towel
    P.revolve_half("basin", [(0.26, 0.0), (0.28, 0.0), (0.27, -0.16), (0.0, -0.2), (0.0, -0.18), (0.25, -0.14)],
                   (BX, 0.0, BASIN_Z), P.porcelain(), P.porcelain_cut(), R, n=64)
    lib.box("basin_bracket", RW0 - 0.06, RW0, 0.0, 0.3, BASIN_Z - 0.2, BASIN_Z - 0.02, P.porcelain(), R)
    spout = [(RW0, 0.12, BASIN_Z + 0.28), (BX + 0.12, 0.12, BASIN_Z + 0.28), (BX + 0.03, 0.12, BASIN_Z + 0.22)]
    lib.tube("bath_spout", spout, 0.022, chrome(), R)
    lib.tube("bath_feed", [(RW0 - 0.02, 0.0, BASIN_Z + 0.28), (RW0 - 0.02, 0.12, BASIN_Z + 0.28)], PIPE_R, copper, R)
    lib.blob("bath_knob", 0.03, chrome(), (RW0 - 0.04, 0.3, BASIN_Z + 0.36), parent=R, lumpy=0.0)
    lib.box("bath_mirror", -0.4, 1.3, 0.88, 0.9, UP_Z + 1.3, UP_Z + 2.1,
            lib.flat("mirror", (0.8, 0.85, 0.9), 0.02, metallic=1.0), R)
    lib.box("bath_towel", -0.7, -0.2, 0.84, 0.9, UP_Z + 0.8, UP_Z + 1.4, lib.flat("towel", lib.hexrgb("#6FA8C9"), 0.9),
            R)
    lib.box("bath_mat", -0.4, 0.9, 0.2, 0.8, UP_Z, UP_Z + 0.015, lib.flat("bathmat", lib.hexrgb("#E8EEF0"), 0.95), R)
    # the bedroom next door: a bed and a window light
    bed = lib.flat("duvet", lib.hexrgb("#E7E3DA"), 0.9)
    lib.box("bed", -6.4, -3.4, 1.4, 3.6, UP_Z, UP_Z + 0.5, bed, R, bevel=0.06)
    lib.box("bed_head", -6.5, -6.35, 1.4, 3.6, UP_Z, UP_Z + 1.1, lib.flat("bed_wood", lib.hexrgb("#8C6A4B"), 0.6), R)
    lib.box("pillow", -6.3, -5.7, 1.6, 3.4, UP_Z + 0.5, UP_Z + 0.65, lib.flat("pillow", (0.95, 0.95, 0.94), 0.9), R,
            bevel=0.04)

    # ---- the supply pipe: copper, cut lengthwise, running full of clean water
    P.half_pipe("supply_pipe", SUPPLY, PIPE_R, mat=copper, cut_mat=copper_cut, parent=R, bend=0.1)
    P.pipe_water("supply_w", SUPPLY, PIPE_R, level=0.97, mat=full, section_mat=full_cut, parent=R, bend=0.1)
    P.half_pipe("kitchen_branch", KITCHEN_BRANCH, PIPE_R, mat=copper, cut_mat=copper_cut, parent=R, bend=0.08)
    P.pipe_water("kitchen_branch_w", KITCHEN_BRANCH, PIPE_R, level=0.97, mat=full, section_mat=full_cut, parent=R,
                 bend=0.08)
    self.home_supply_path = P.resample(P.rounded(SUPPLY, 0.1), 0.05)
    self.home_arrows = [P.arrow(f"home_arrow{k}", (0, 0, 0), (1, 0, 0), size=0.05, parent=R) for k in range(4)]
    # the running water: kitchen stream (falls into the sink, or into the glass) and the upstairs basin stream
    tw = tap_water()
    sx, sy, sz = self.spout_tip
    self.k_stream_root = lib.empty("k_stream_root", (sx, sy, sz), R)
    self.k_stream, _ = P.stream("k_stream", (0, 0, 0), (0, 0, -0.05), 0.3, radius=0.011, mat=tw,
                                parent=self.k_stream_root)
    self.b_stream_root = lib.empty("b_stream_root", (BX + 0.03, 0.12, BASIN_Z + 0.2), R)
    self.b_stream, _ = P.stream("b_stream", (0, 0, 0), (0, 0, -0.05), 0.27, radius=0.01, mat=tw,
                                parent=self.b_stream_root)
    for root in (self.k_stream_root, self.b_stream_root):
        root.scale = (1, 1, 0.001)
        lib.key(root, "scale", 1, (1, 1, 0.001))
    self.k_foam = P.foam("k_foam", (sx, sy, self.sink_floor + 0.012), 0.04, parent=R, seed=3)
    self.b_foam = P.foam("b_foam", (BX + 0.03, 0.12, BASIN_Z - 0.18), 0.035, parent=R, seed=4)
    for f in (self.k_foam, self.b_foam):
        lib.visible(f, 1, False)
    # the glass, standing in the sink under the spout; its water rises in the glass shot
    self.glass_root = lib.empty("glass_root", (sx, sy, self.sink_floor + 0.003), R)
    gr, gh = 0.042, 0.13
    P.revolve_half("glass", [(gr - 0.003, 0.004), (gr, 0.0), (gr + 0.006, gh), (gr + 0.003, gh), (gr - 0.002, 0.006),
                             (0.0, 0.006), (0.0, 0.0)], (0, 0, 0), glass_mat(), None, self.glass_root, n=48, full=True)
    self.glass_water = lib.empty("glass_water_root", (0, 0, 0.006), self.glass_root)
    P.revolve_half("glass_w", [(0.0, 0.0), (gr - 0.004, 0.0), (gr - 0.001, 1.0), (0.0, 1.0)], (0, 0, 0),
                   P.water("glass_water", "#CDEFFC", "#FFFFFF", speed=0.1, foam_amount=0.05, coord="Object",
                           glass=0.4, density=0),
                   None, self.glass_water, n=48, full=True)
    self.glass_water.scale = (1, 1, 0.001)
    lib.visible(self.glass_root, 1, False)

    # ---- anchors for the compositor
    self.anchor("home", "home_supply", (8.0, 0, SUPPLY_Z + PIPE_R))
    self.anchor("home", "kitchen_tap", (sx, sy, sz + 0.05))
    self.anchor("home", "bath_tap", (BX + 0.1, 0.12, BASIN_Z + 0.3))
    for k in range(3):
        P.tree(f"home_tree{k}", (6.0 + k * 7.5, 9.0 + k * 3.0, 0), h=5.5, parent=R, seed=k + 31)
    self.finishers.append(lambda: _home_finish(self))
    return R


def _reparent_keep(ob, parent):
    mw = ob.matrix_world.copy()
    ob.parent = parent
    ob.matrix_world = mw


def _kitchen_tap(self, R, copper):
    """A chrome gooseneck mixer on the counter behind the sink, fed from below through the cabinet."""
    tx, ty = TAP
    zc1 = COUNTER[5]
    lib.tube("tap_base", [(tx, ty, zc1), (tx, ty, zc1 + 0.06)], 0.03, chrome(), R)
    neck = [(tx, ty, zc1 + 0.05), (tx, ty, zc1 + 0.33)]
    arc = [(tx, ty - 0.15 * (1 - math.cos(a)), zc1 + 0.33 + 0.15 * math.sin(a))
           for a in [math.pi * k / 10 for k in range(11)]]
    lib.tube("tap_neck", neck + arc[1:] + [(tx, ty - 0.30, zc1 + 0.27)], 0.016, chrome(), R)
    lib.box("tap_lever", tx - 0.008, tx + 0.008, ty - 0.01, ty + 0.11, zc1 + 0.16, zc1 + 0.18, chrome(), R, bevel=0.004)
    self.spout_tip = (tx, ty - 0.30, zc1 + 0.265)
    # the feed under the counter (whole tube, behind the section)
    bx = KITCHEN_BRANCH[-1][0]
    lib.tube("tap_feed", [(bx, 0.0, KITCHEN_BRANCH[-1][2]), (bx, ty, KITCHEN_BRANCH[-1][2]),
                          (bx, ty, zc1 - 0.06), (tx, ty, zc1 - 0.06), (tx, ty, zc1)], PIPE_R * 0.8, copper, R)


def _gable_roof(parent, x0, x1, y0, y1, z0, rise, roof_mat, cut_mat):
    xm = (x0 + x1) / 2
    th = 0.16
    bm = bmesh.new()
    prof = [(x0, z0), (xm, z0 + rise), (x1, z0), (x1 - th * 1.2, z0), (xm, z0 + rise - th * 1.3), (x0 + th * 1.2, z0)]
    front = [bm.verts.new((x, y0, z)) for x, z in prof]
    back = [bm.verts.new((x, y1, z)) for x, z in prof]
    n = len(prof)
    for k in range(n):
        f = bm.faces.new((front[k], front[(k + 1) % n], back[(k + 1) % n], back[k]))
        f.material_index = 0
    f = bm.faces.new(list(reversed(front)))
    f.material_index = 1
    f = bm.faces.new(back)
    f.material_index = 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = lib.mesh_from_bm("home_roof", bm, None, parent)
    ob.data.materials.append(roof_mat)
    ob.data.materials.append(cut_mat)
    bm = bmesh.new()
    vs = [bm.verts.new((x0 + 0.3, y1 - 0.4, z0)), bm.verts.new((x1 - 0.3, y1 - 0.4, z0)),
          bm.verts.new((xm, y1 - 0.4, z0 + rise - 0.25))]
    bm.faces.new(vs)
    lib.mesh_from_bm("home_attic_back", bm, lib.flat("attic", lib.hexrgb("#8C7A62"), 0.8), parent)


# ---------------------------------------------------------------- running water helpers

def _run(self, root, foam, s, e, on=True):
    """Open (or keep open) a tap over [s, e]: the stream grows down from the spout in 5 frames."""
    if on:
        lib.key(root, "scale", s - 1, (1, 1, 0.001), interp="CONSTANT")
        lib.key(root, "scale", s, (1, 1, 0.001), interp="CUBIC", easing="EASE_OUT")
        lib.key(root, "scale", s + 5, (1, 1, 1), interp="CONSTANT")
        lib.key(root, "scale", e + 1, (1, 1, 0.001), interp="CONSTANT")
        if foam is not None:
            lib.visible(foam, s + 4, True)
            lib.visible(foam, e + 1, False)


def _arrows(self, s, e, speed=1.4):
    path = [V(p) for p in self.home_supply_path]
    L = sum((b - a).length for a, b in zip(path, path[1:]))
    for k, a in enumerate(self.home_arrows):
        P.ride(a, self.home_supply_path, s, e, speed, offset=k * L / len(self.home_arrows),
               normal_offset=(0, -0.006, 0))


# ---------------------------------------------------------------- shots

def tap(self, s, e):
    self.on_station("home", s, e)
    sx, sy, sz = self.spout_tip
    self.shot("home", s, e, dict(center=(sx + 0.02, 0.2, sz - 0.12), width=0.62, yaw=18, pitch=14, lens=45),
              dict(center=(sx + 0.01, 0.22, sz - 0.14), width=0.55, yaw=12, pitch=12, lens=45))
    _run(self, self.k_stream_root, self.k_foam, s + 6, e + 4)
    events.add(s + 2, "click", gain=0.5)
    events.add(s + 6, "pour", duration=e - s, gain=0.9)


def why(self, s, e):
    self.on_station("home", s, e)
    sx, sy, sz = self.spout_tip
    self.shot("home", s, e, dict(center=(3.6, 0, 1.2), width=9.5, yaw=14, pitch=8, lens=32),
              dict(center=(4.6, 0, 0.7), width=11.0, yaw=18, pitch=9, lens=32), ease="smooth")
    _run(self, self.k_stream_root, self.k_foam, s - 4, e)
    _arrows(self, s + int((e - s) * 0.3), e)
    events.add(s, "pour", duration=e - s, gain=0.5)


def upstairs(self, s, e):
    self.on_station("home", s, e)
    self.shot("home", s, e, dict(center=(RX - 0.2, 0, FLOOR_Z + 0.9), width=2.6, yaw=16, pitch=6, lens=35),
              dict(center=(BX + 0.25, 0.1, BASIN_Z + 0.05), width=1.6, yaw=20, pitch=10, lens=35), ease="smooth")
    _arrows(self, s, e, speed=1.2)
    _run(self, self.b_stream_root, self.b_foam, s + int((e - s) * 0.55), e + 2)
    events.add(s + int((e - s) * 0.55), "pour", duration=int((e - s) * 0.45), gain=0.6)


def glass(self, s, e):
    self.on_station("home", s, e)
    sx, sy, sz = self.spout_tip
    lib.visible(self.glass_root, s, True)
    lib.visible(self.glass_root, e + 1, False)
    self.shot("home", s, e, dict(center=(sx, sy, self.sink_floor + 0.1), width=0.5, yaw=10, pitch=26, lens=50),
              dict(center=(sx, sy, self.sink_floor + 0.11), width=0.44, yaw=16, pitch=24, lens=50))
    _run(self, self.k_stream_root, None, s, e - 8)
    lib.key(self.glass_water, "scale", s, (1, 1, 0.01))
    lib.tween(self.glass_water, "scale", s + 2, e - 8, (1, 1, 0.01), (1, 1, 0.11), "linear")
    events.add(s, "pour", duration=e - s - 8, gain=0.7)


def question(self, s, e):
    self.on_station("home", s, e)
    self.shot("home", s, e, dict(center=(1.6, 0, 1.6), width=9.0, yaw=16, pitch=8, lens=32),
              dict(center=(1.0, 0, 2.2), width=11.5, yaw=22, pitch=10, lens=32))
    _arrows(self, s, e, speed=1.0)


def _home_finish(self):
    pass


SHOTS = (build_home, tap, why, upstairs, glass, question)
