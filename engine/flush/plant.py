"""Station D, the treatment plant, laid out along +x on one lawn:
inlet pipe -> open channel with a bar screen -> grit section (front wall cut away) -> primary clarifier (round,
cut in half, rotating scraper bridge) -> aeration tank (cut, diffusers + bubbles) -> secondary clarifier (whole,
clear water over the weir) -> UV channel (lamp racks)."""
import math
import random

from mathutils import Vector

from engine import events
from engine.director import lib
from engine.flush import parts as P
from engine.flush.toilet import boolean

V = Vector
CH_Y0, CH_Y1, CH_FLOOR, CH_TOP, CH_WATER = 0.6, 1.8, 0.05, 1.05, 0.75
CH_YC = (CH_Y0 + CH_Y1) / 2
SCREEN_X = 6.0
GRIT = (10.0, 18.0)
CH_END = 24.0
PC = (31.0, 0.0)                         # primary clarifier centre
PC_R, PC_TOP, PC_LEVEL = 5.0, 0.8, 0.55
PIVOT_Z = 1.3
AER = (40.0, 50.0, 6.0, -4.0, 0.5)       # x0, x1, y1, floor, water
SC = (64.0, 9.0)                         # secondary clarifier centre
SC_R, WEIR_R, SC_LEVEL = 4.6, 4.28, 0.66
UV = (72.0, 82.0)


def floor_z(r):
    """Primary clarifier floor (top of the concrete): a hopper at the centre, then a cone up to the wall."""
    return -4.2 if r < 0.8 else -3.7 + (r - 0.8) * (0.7 / 4.2)


def build_plant(self):
    R = self.root("plant")
    rnd = random.Random(4)
    dirty = P.water("plant_dirty", P.DIRTY[0], P.DIRTY[1], speed=0.7, coord="Object", foam_amount=0.4)
    dirty_cut = P.water_section("water_cut_dirty", P.DIRTY[0], P.DIRTY[2])
    clean = P.water("plant_clean", P.CLEAN[0], P.CLEAN[1], speed=0.5, coord="Object", foam_amount=0.18)
    conc, conc_old = P.concrete(), P.concrete_old()
    # ground: soil block (section face at y = 0) with holes for the sunken tanks; turf on top
    soil = P.soil_block("plant_soil", -45, 125, 0, 60, -400.0, -0.04, R)
    boolean(soil, P.cylinder("pc_hole", PC, PC_R + 0.31, -5.0, 2, conc, R))
    boolean(soil, lib.box("aer_hole", AER[0] - 0.31, AER[1] + 0.31, -1, AER[2] + 0.31, AER[3] - 0.31, 2, conc, R))
    turf = lib.material("Grass004", scale=0.7, tint=(0.85, 1.0, 0.75), name="grass_top")
    top = lib.box("plant_turf", -45, 125, -0.03, 60, -0.04, 0.0, turf, R)
    lib.box("plant_far_turf", -250, 350, 60, 400, -0.04, 0.0, turf, R)
    for xa, xb in ((-250, -45), (125, 350)):
        lib.box(f"plant_side_turf{xa}", xa, xb, 0, 60, -0.04, 0.0, turf, R)
        lib.box(f"plant_side_soil{xa}", xa, xb, 0, 60, -400, -0.04, P.soil(), R)
    boolean(top, P.cylinder("pc_hole2", PC, PC_R + 0.31, -5.0, 2, conc, R))
    boolean(top, lib.box("aer_hole2", AER[0] - 0.31, AER[1] + 0.31, -1, AER[2] + 0.31, -5, 2, conc, R))
    for k, (xa, xb, ya, yb) in enumerate(((-12, 25, 2.2, 9), (-12, 25, 0, 0.4), (51, 90, 0, 6), (34, 39.5, 0, 6))):
        lib_blades = P.lawn(f"plant_lawn{k}", xa, xb, ya, yb, parent=R, density=170, seed=40 + k)
        lib_blades[0].hide_render = True          # the big turf slab already covers this ground
        lib_blades[0].hide_viewport = True

    # ---- the inlet: the main arrives through a concrete headwall and pours into the channel
    lib.box("headwall", -5.6, -4.8, 0.1, 2.3, -0.3, 1.9, conc_old, R)
    inlet = [(-4.8, CH_YC, 1.0), (-0.15, CH_YC, 1.0)]
    P.half_pipe("inlet_pipe", inlet, 0.32, mode="top", mat=conc_old, cut_mat=conc, parent=R)
    P.pipe_water("inlet_w", inlet, 0.32, level=0.55, mode="top", mat=P.dirty_flow(1.2, "dirty_inlet"), parent=R)
    P.stream("inlet_pour", (-0.1, CH_YC, 0.92), (0.9, 0, 0), 0.28, radius=0.12, parent=R,
             mat=P.fall(), flat=1.8)
    P.foam("inlet_foam", (0.45, CH_YC, CH_WATER), 0.32, parent=R, seed=21)
    # ---- the channel: floor, back wall, front wall (missing along the grit section), water
    lib.box("ch_floor", -0.2, CH_END, CH_Y0 - 0.2, CH_Y1 + 0.2, CH_FLOOR - 0.25, CH_FLOOR, conc, R)
    lib.box("ch_back", -0.2, CH_END, CH_Y1, CH_Y1 + 0.2, CH_FLOOR, CH_TOP, conc, R)
    lib.box("ch_start", -0.4, -0.2, CH_Y0 - 0.2, CH_Y1 + 0.2, CH_FLOOR - 0.25, CH_TOP, conc, R)
    lib.box("ch_front_a", -0.2, GRIT[0], CH_Y0 - 0.2, CH_Y0, CH_FLOOR, CH_TOP, conc, R)
    lib.box("ch_front_b", GRIT[1], CH_END, CH_Y0 - 0.2, CH_Y0, CH_FLOOR, CH_TOP, conc, R)
    lib.box("ch_end", CH_END, CH_END + 0.2, CH_Y0 - 0.2, CH_Y1 + 0.2, CH_FLOOR - 0.25, CH_TOP, conc, R)
    P.prism("ch_water", [(-0.2, CH_FLOOR), (CH_END, CH_FLOOR), (CH_END, CH_WATER), (-0.2, CH_WATER)],
            CH_Y0, CH_Y1, dirty, R, cut_mat=dirty_cut)
    self.ch_arrows = [P.arrow(f"arrow_ch{k}", (0, 0, 0), (1, 0, 0), size=0.22, parent=R, normal=(0, 0, 1))
                      for k in range(3)]
    # ---- the bar screen: inclined steel bars across the channel, rags and wipes caught on them
    bar_y = [CH_Y0 + 0.05 + k * (CH_Y1 - CH_Y0 - 0.1) / 15 for k in range(16)]
    for k, y in enumerate(bar_y):
        lib.tube(f"bar{k}", [(SCREEN_X, y, CH_FLOOR), (SCREEN_X + 0.5, y, CH_TOP + 0.45)], 0.02, P.steel(), R)
    lib.box("screen_beam", SCREEN_X + 0.47, SCREEN_X + 0.55, CH_Y0 - 0.25, CH_Y1 + 0.25, CH_TOP + 0.42, CH_TOP + 0.5,
            P.dark_steel(), R)
    rag_cols = ("#ECE9E0", "#D9D4C8", "#C9B9A8", "#E7C9CF", "#9FB6CF", "#F2F2EE")
    self.rags = []
    for k in range(9):
        y = rnd.uniform(CH_Y0 + 0.12, CH_Y1 - 0.12)
        z = rnd.uniform(CH_WATER - 0.12, CH_WATER + 0.18)
        x = SCREEN_X + (z - CH_FLOOR) * 0.5 / (CH_TOP + 0.45 - CH_FLOOR) - 0.04
        rag = lib.blob(f"rag{k}", rnd.uniform(0.07, 0.13), lib.flat(f"rag_{k % 6}", lib.hexrgb(rag_cols[k % 6]), 0.9),
                       (x, y, z), squash=0.5, seed=60 + k, parent=R, lumpy=0.45)
        rag.scale = (0.35, 1.3, 1.0)
        self.rags.append(rag)
    self.drifters = []
    for k in range(3):
        d = lib.blob(f"drift{k}", 0.08, lib.flat(f"rag_{k}", lib.hexrgb(rag_cols[k]), 0.9),
                     (2.0, CH_Y0 + 0.3 + k * 0.3, CH_WATER), squash=0.35, seed=80 + k, parent=R, lumpy=0.4)
        self.drifters.append(d)
    # ---- the grit section: sand grains sink and a sand bed builds on the floor
    sand = lib.material("Ground054", scale=1.5, tint=(1.0, 0.92, 0.78), name="sand")
    self.sand_bed = lib.box("sand_bed", GRIT[0], GRIT[1], CH_Y0, CH_Y1, 0.0, 1.0, sand, R)
    self.sand_bed.location.z = CH_FLOOR
    self.sand_bed.scale.z = 0.04
    grain = lib.flat("grain", lib.hexrgb("#C2A57A"), 0.8)
    for k in range(140):
        g = lib.blob(f"grain{k}", rnd.uniform(0.012, 0.026), grain,
                     (rnd.uniform(GRIT[0] + 0.3, GRIT[1] - 0.3), CH_Y0 - 0.012, CH_WATER), squash=0.8, seed=k,
                     parent=R, lumpy=0.2, subdiv=1)
        g.visible_shadow = False
        P.cycle_rise(g, CH_WATER - 0.05, CH_FLOOR + 0.12, rnd.randint(70, 110), -rnd.randint(0, 110))

    # ---- primary clarifier, cut in half
    P.revolve_half("pc_wall", [(PC_R, -3.3), (PC_R + 0.3, -3.3), (PC_R + 0.3, PC_TOP), (PC_R, PC_TOP)],
                   (PC[0], PC[1], 0), conc, conc_old, R, n=96)
    P.revolve_half("pc_floor", [(0.0, -4.5), (PC_R + 0.3, -3.35), (PC_R + 0.3, -3.3), (PC_R, floor_z(PC_R)),
                                (0.8, floor_z(0.81)), (0.8, -4.2), (0.0, -4.2)], (PC[0], PC[1], 0), conc, conc_old,
                   R, n=96)
    sludge = lib.material("Ground106", scale=1.0, tint=(0.3, 0.2, 0.12), rough=0.2, name="sludge")
    sludge_top = lambda r: floor_z(r) + 0.28 if r > 0.8 else -3.42    # noqa: E731
    P.revolve_half("pc_sludge", [(0.0, -4.19), (0.79, -4.19), (0.79, floor_z(0.82)), (PC_R - 0.02, floor_z(PC_R)),
                                 (PC_R - 0.02, sludge_top(PC_R)), (0.95, sludge_top(0.95)), (0.0, -3.42)],
                   (PC[0], PC[1], 0), sludge, sludge, R, n=96)
    pc_water = P.water_glass("pc_water", "#B9CDB4", alpha=0.42, foam="#DCE5D6")
    P.revolve_half("pc_water", [(0.0, -3.4), (0.95, sludge_top(0.95) + 0.02), (PC_R - 0.02, sludge_top(PC_R) + 0.02),
                                (PC_R - 0.02, PC_LEVEL), (0.0, PC_LEVEL)], (PC[0], PC[1], 0), pc_water,
                   P.water_glass("pc_water_cut", "#6E7A68", alpha=0.35), R, n=96)
    P.revolve_half("pc_well", [(0.9, -1.2), (1.0, -1.2), (1.0, 0.95), (0.9, 0.95)], (PC[0], PC[1], 0), P.steel(),
                   P.steel(), R, n=48)
    P.revolve_half("pc_column", [(0.0, -4.2), (0.3, -4.2), (0.3, PIVOT_Z), (0.0, PIVOT_Z)], (PC[0], PC[1], 0),
                   conc, conc_old, R, n=32)
    # the bridge, scraper arm and blades rotate about the centre column
    piv = lib.empty("pc_pivot", (PC[0], PC[1], PIVOT_Z), R)
    lib.box("pc_drive", -0.45, 0.45, -0.45, 0.45, 0.0, 0.4, lib.flat("drive_green", lib.hexrgb("#3F7F5F"), 0.4), piv)
    lib.box("pc_bridge", 0.0, PC_R + 0.5, -0.4, 0.4, -0.05, 0.12, P.steel(), piv, bevel=0.01)
    for sy in (-0.38, 0.38):
        lib.box(f"pc_rail{sy}", 0.2, PC_R + 0.4, sy - 0.02, sy + 0.02, 0.12, 0.95, lib.flat("rail_yellow",
                lib.hexrgb("#E2B33C"), 0.4), piv)
        lib.box(f"pc_railtop{sy}", 0.2, PC_R + 0.4, sy - 0.03, sy + 0.03, 0.92, 0.98,
                lib.flat("rail_yellow", lib.hexrgb("#E2B33C"), 0.4), piv)
    lib.box("pc_wheel", PC_R + 0.15, PC_R + 0.5, -0.3, 0.3, -0.5, -0.05, P.dark_steel(), piv)
    for r in (1.4, 2.6, 3.8):
        lib.tube(f"pc_arm{r}", [(r, 0.0, -0.05), (r, 0.0, floor_z(r) + 0.2 - PIVOT_Z)], 0.04, P.steel(), piv)
    blade_mat = lib.flat("blade", lib.hexrgb("#4A5258"), 0.45, metallic=0.6)
    for k in range(9):
        r = 1.0 + k * 0.45
        b = lib.box(f"pc_blade{k}", -0.22, 0.22, -0.02, 0.02, 0.0, 0.22, blade_mat, piv)
        b.location = (r, 0.06, floor_z(r) + 0.02 - PIVOT_Z)
        b.rotation_euler = (0, 0, math.radians(35))
        ridge = lib.blob(f"pc_ridge{k}", 0.2, sludge, (r - 0.05, 0.22, floor_z(r) + 0.3 - PIVOT_Z), squash=0.45,
                         seed=100 + k, parent=piv, lumpy=0.35)
        ridge.scale = (1.8, 0.8, 1.0)
    lib.tube("pc_truss", [(1.0, 0, floor_z(1.0) + 0.22 - PIVOT_Z), (PC_R - 0.2, 0, floor_z(PC_R - 0.2) + 0.22 - PIVOT_Z)],
             0.035, P.steel(), piv)
    self.pc_pivot = piv
    lib.key(piv, "rotation_euler", 1, (0, 0, math.radians(70)))

    # ---- aeration tank, front wall cut away
    x0, x1, y1, fl, wl = AER
    lib.box("aer_floor", x0 - 0.3, x1 + 0.3, 0, y1 + 0.3, fl - 0.3, fl, conc, R)
    lib.box("aer_back", x0 - 0.3, x1 + 0.3, y1, y1 + 0.3, fl, 0.8, conc, R)
    lib.box("aer_left", x0 - 0.3, x0, 0, y1, fl, 0.8, conc, R)
    lib.box("aer_right", x1, x1 + 0.3, 0, y1, fl, 0.8, conc, R)
    mixed = P.water_glass("aer_water", "#C9B488", alpha=0.55, foam="#EFE8D6", speed=0.05)
    P.prism("aer_body", [(x0, fl), (x1, fl), (x1, wl), (x0, wl)], 0.0, y1, mixed, R,
            cut_mat=P.water_glass("aer_cut", "#7C6E50", alpha=0.38))
    disc = lib.flat("diffuser", lib.hexrgb("#5D666C"), 0.5)
    header = lib.flat("air_header", lib.hexrgb("#7E878D"), 0.4, metallic=0.5)
    for y in (1.2, 3.0, 4.8):
        lib.tube(f"aer_header{y}", [(x0 + 0.2, y, fl + 0.12), (x1 - 0.2, y, fl + 0.12)], 0.05, header, R)
        for x in [x0 + 0.8 + k * 1.05 for k in range(9)]:
            lib.tube(f"aer_disc{x:.1f}_{y}", [(x, y, fl + 0.12), (x, y, fl + 0.2)], 0.17, disc, R)
    P.bubbles("aer_bub", x0 + 0.5, x1 - 0.5, 0.05, y1 - 0.2, fl + 0.25, wl - 0.02, 340, parent=R, seed=5,
              radius=(0.015, 0.04), period=(55, 90))
    self.aer_arrows = [P.arrow(f"arrow_air{k}", (0, 0, 0), (0, 0, 1), size=0.28, parent=R) for k in range(4)]

    # ---- secondary clarifier: whole tank, clear water spilling over a notched weir into the launder
    cx, cy = SC
    P.revolve_half("sc_wall", [(SC_R, -1.0), (SC_R + 0.3, -1.0), (SC_R + 0.3, 0.8), (SC_R, 0.8)], (cx, cy, 0),
                   conc, conc, R, n=128, full=True)
    P.revolve_half("sc_launder_floor", [(WEIR_R, 0.05), (SC_R, 0.05), (SC_R, 0.12), (WEIR_R, 0.12)], (cx, cy, 0),
                   conc_old, conc_old, R, n=128, full=True)
    P.revolve_half("sc_weir", [(WEIR_R - 0.04, -0.6), (WEIR_R, -0.6), (WEIR_R, 0.6), (WEIR_R - 0.04, 0.6)],
                   (cx, cy, 0), P.steel(), P.steel(), R, n=128, full=True)
    for k in range(220):
        a = 2 * math.pi * k / 220
        t = lib.box(f"sc_tooth{k}", -0.025, 0.025, -0.004, 0.004, 0.0, 0.06, P.steel(), R)
        t.location = (cx + (WEIR_R - 0.02) * math.cos(a), cy + (WEIR_R - 0.02) * math.sin(a), 0.6)
        t.rotation_euler = (0, 0, a + math.pi / 2)
    clear = P.water("sc_clear", "#A6DCEE", "#F0FAFD", speed=0.05, coord="Object", foam_amount=0.08)
    P.revolve_half("sc_water", [(0.0, -0.9), (WEIR_R - 0.045, -0.9), (WEIR_R - 0.045, SC_LEVEL), (0.0, SC_LEVEL)],
                   (cx, cy, 0), clear, clear, R, n=128, full=True)
    sheet = P.water("weir_sheet", "#7CC3DE", "#F2FBFF", speed=-0.8, coord="Object", foam_amount=0.4,
                    scale=(18.0, 18.0, 6.0), axis=2)
    P.revolve_half("sc_sheet", [(WEIR_R + 0.005, 0.2), (WEIR_R + 0.03, 0.2), (WEIR_R + 0.012, SC_LEVEL - 0.02),
                                (WEIR_R + 0.002, SC_LEVEL - 0.02)], (cx, cy, 0), sheet, sheet, R, n=128, full=True)
    P.revolve_half("sc_launder_w", [(WEIR_R + 0.01, 0.12), (SC_R - 0.01, 0.12), (SC_R - 0.01, 0.28),
                                    (WEIR_R + 0.01, 0.28)], (cx, cy, 0), clean, clean, R, n=128, full=True)

    # ---- UV channel: clear water, two racks of glowing lamps
    ux0, ux1 = UV
    lib.box("uv_floor", ux0, ux1, CH_Y0 - 0.2, CH_Y1 + 0.2, CH_FLOOR - 0.25, CH_FLOOR, conc, R)
    lib.box("uv_back", ux0, ux1, CH_Y1, CH_Y1 + 0.2, CH_FLOOR, CH_TOP, conc, R)
    P.prism("uv_water", [(ux0, CH_FLOOR), (ux1, CH_FLOOR), (ux1, CH_WATER), (ux0, CH_WATER)], CH_Y0, CH_Y1,
            P.water_glass("uv_clear", "#A6DCEE", alpha=0.38, foam="#E9F8FF", speed=0.5), R,
            cut_mat=P.water_glass("uv_cut", "#3E98C0", alpha=0.3))
    lamp = lib.flat("uv_lamp", lib.hexrgb("#B48CFF"), 0.1, emission=9.0)
    sleeve = lib.flat("uv_sleeve", lib.hexrgb("#DDE7F2"), 0.05, alpha=0.35)
    for rx in (74.5, 78.2):
        for fy in (CH_Y0 - 0.12, CH_Y1 + 0.04):
            lib.box(f"uv_frame{rx}_{fy:.2f}", rx - 0.05, rx + 1.95, fy, fy + 0.08, CH_TOP + 0.12, CH_TOP + 0.2,
                    P.dark_steel(), R)
        for leg in (rx, rx + 1.9):
            lib.box(f"uv_leg{leg}", leg - 0.04, leg + 0.04, CH_Y0 + 0.05, CH_Y1 - 0.05, 0.2, CH_TOP + 0.12,
                    P.steel(), R)
        for iy, y in enumerate((CH_Y0 + 0.3, CH_YC, CH_Y1 - 0.3)):
            for iz, z in enumerate((0.3, 0.52, CH_WATER - 0.04)):
                lib.tube(f"uv_tube{rx}_{iy}{iz}", [(rx + 0.05, y, z), (rx + 1.85, y, z)], 0.026, lamp, R)
                lib.tube(f"uv_sleeve{rx}_{iy}{iz}", [(rx + 0.03, y, z), (rx + 1.87, y, z)], 0.04, sleeve, R)
        light = lib.link(__import__("bpy").data.objects.new(
            f"uv_glow{rx}", __import__("bpy").data.lights.new(f"uv_glow{rx}", "POINT")), R)
        light.data.energy = 120
        light.data.color = (0.62, 0.45, 1.0)
        light.location = (rx + 0.95, CH_YC, 0.95)
    lib.box("uv_inlet_pipe", ux0 - 0.6, ux0, CH_Y0, CH_Y1, CH_FLOOR, CH_TOP, conc_old, R)
    for k, (x, y) in enumerate(((58, 22), (70, 24), (86, 18), (-8, 14), (20, 20), (44, 18))):
        P.tree(f"pl_tree{k}", (x, y, 0), h=6.0, parent=R, seed=k + 21)
    return R


def plant_arrive(self, s, e):
    self.on_station("plant", s, e)
    self.shot("plant", s, e, dict(center=(14.0, 3.0, 0.0), width=26, yaw=22, pitch=48, lens=30),
              dict(center=(-0.6, CH_YC, 0.75), width=3.6, yaw=26, pitch=24, lens=30), ease="smooth")
    for k, a in enumerate(self.ch_arrows):
        P.ride(a, [(-0.1, CH_YC, CH_WATER + 0.01), (CH_END, CH_YC, CH_WATER + 0.01)], s, e, 0.8, offset=k * 1.6)
    events.add(s, "pour", duration=e - s, gain=0.8)
    events.add(s, "water_rush", duration=e - s, gain=0.4)


def bar_screen(self, s, e):
    self.on_station("plant", s, e)
    self.shot("plant", s, e, dict(center=(SCREEN_X - 0.3, CH_YC, CH_WATER + 0.12), width=1.9, yaw=-30, pitch=30,
                                  lens=32),
              dict(center=(SCREEN_X + 0.05, CH_YC, CH_WATER + 0.12), width=1.4, yaw=-22, pitch=28, lens=32))
    n = e - s
    for k, d in enumerate(self.drifters):
        x_stop = SCREEN_X + (CH_WATER - CH_FLOOR) * 0.5 / (CH_TOP + 0.45 - CH_FLOOR) - 0.06
        y = CH_Y0 + 0.3 + k * 0.3
        lib.key(d, "location", 1, (SCREEN_X - 3.2 - k * 0.6, y, CH_WATER))
        lib.tween(d, "location", s, s + int(n * (0.55 + 0.15 * k)), (SCREEN_X - 3.0 - k * 0.6, y, CH_WATER),
                  (x_stop, y, CH_WATER + 0.02), "out")
    events.add(s, "water_rush", duration=n, gain=0.6)


def grit(self, s, e):
    self.on_station("plant", s, e)
    self.shot("plant", s, e, dict(center=(GRIT[0] + 2.0, CH_Y0, 0.38), width=1.4, yaw=16, pitch=10, lens=32),
              dict(center=(GRIT[0] + 4.2, CH_Y0, 0.36), width=1.4, yaw=22, pitch=10, lens=32))
    lib.tween(self.sand_bed, "scale", s, e, (1, 1, 0.04), (1, 1, 0.28), "smooth")
    events.add(s, "water_rush", duration=e - s, gain=0.35)


def clarifier(self, s, e):
    self.on_station("plant", s, e)
    self.shot("plant", s, e, dict(center=(PC[0], 1.8, -1.2), width=13.5, yaw=14, pitch=34, lens=30),
              dict(center=(PC[0] + 0.5, 1.6, -1.5), width=12.5, yaw=40, pitch=30, lens=30))
    lib.tween(self.pc_pivot, "rotation_euler", s, e, (0, 0, math.radians(70)), (0, 0, math.radians(40)), "linear")
    events.add(s, "hum", duration=e - s, gain=0.6)


def scraper(self, s, e):
    self.on_station("plant", s, e)
    self.shot("plant", s, e, dict(center=(PC[0] + 2.6, 1.0, floor_z(2.6) + 0.3), width=3.6, yaw=10, pitch=55,
                                  lens=32),
              dict(center=(PC[0] + 1.8, 0.7, floor_z(1.8) + 0.3), width=3.0, yaw=16, pitch=52, lens=32))
    lib.tween(self.pc_pivot, "rotation_euler", s, e, (0, 0, math.radians(26)), (0, 0, math.radians(8)), "linear")
    events.add(s, "hum", duration=e - s, gain=0.7)
    events.add(s, "creak", gain=0.3)


def aeration(self, s, e):
    self.on_station("plant", s, e)
    x0, x1, y1, fl, wl = AER
    self.shot("plant", s, e, dict(center=((x0 + x1) / 2, 0, fl + 1.4), width=6.0, yaw=14, pitch=6, lens=30),
              dict(center=((x0 + x1) / 2, 0, wl - 1.0), width=6.6, yaw=16, pitch=16, lens=30))
    for k, a in enumerate(self.aer_arrows):
        x = x0 + 1.4 + k * 2.4
        P.ride(a, [(x, -0.02, fl + 0.4), (x, -0.02, wl - 0.2)], s, e, 1.2, offset=k * 1.1)
    events.add(s, "bubbles", duration=e - s, gain=0.9)


def weir(self, s, e):
    self.on_station("plant", s, e)
    cx, cy = SC
    self.shot("plant", s, e, dict(center=(cx - 1.0, cy - WEIR_R - 0.1, 0.45), width=2.6, yaw=22, pitch=26, lens=32),
              dict(center=(cx - 0.2, cy - WEIR_R - 0.1, 0.45), width=2.3, yaw=52, pitch=24, lens=32))
    events.add(s, "pour", duration=e - s, gain=0.6)


def uv(self, s, e):
    self.on_station("plant", s, e)
    self.shot("plant", s, e, dict(center=(UV[0] + 2.8, CH_Y0, 0.5), width=2.4, yaw=14, pitch=14, lens=30),
              dict(center=(UV[0] + 6.3, CH_Y0, 0.5), width=2.4, yaw=20, pitch=16, lens=30))
    events.add(s, "hum", duration=e - s, gain=0.5)
    events.add(s, "water_rush", duration=e - s, gain=0.3)


SHOTS = (build_plant, plant_arrive, bar_screen, grit, clarifier, scraper, aeration, weir, uv)
