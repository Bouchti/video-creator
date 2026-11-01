"""Station C, the lift station: the sewer main runs downhill under a sloping road until it is too deep, pours
into a concrete wet well (cut in half), a submersible pump pushes the sewage up a steel riser, and the riser
spills into a gravity channel near the surface."""
from mathutils import Vector

from engine import events
from engine.director import lib
from engine.flush import parts as P
from engine.flush.toilet import boolean

V = Vector
MAIN_R = 0.3
LIFT_C = (2.6, 0.0)
WELL_R_OUT, WELL_R_IN, WELL_FLOOR, WELL_TOP = 2.0, 1.72, -8.6, 0.45
LIFT_MAIN = [(-32.0, 0, -1.15), (0.7, 0, -5.5)]
RISER_R = 0.11
RISER = [(3.95, 0, -7.85), (3.95, 0, 1.15), (6.1, 0, 1.15), (6.1, 0, 0.72)]
CH = dict(x0=5.5, x1=18.0, y1=0.85, floor=-0.62, water=-0.22, top=0.22)


def ground_top(x):
    return 1.95 * (-x) / 32.0 if x < 0 else 0.0


def main_z(x):
    return -1.15 + (x + 32.0) * (-5.5 + 1.15) / 32.7


def build_lift(self):
    from engine.flush.film import carve
    R = self.root("lift")
    dirty_cut = P.water_section("water_cut_dirty", P.DIRTY[0], P.DIRTY[2])
    outline = [(-34, -400), (20, -400), (20, -0.04), (0, -0.04), (0, -0.24), (-34, ground_top(-34) - 0.24)]
    soil = P.prism("lift_soil", outline, 0.0, 9.0, P.soil(), R)
    carve(soil, LIFT_MAIN, MAIN_R, bend=0.0)
    boolean(soil, P.cylinder("well_hole", LIFT_C, WELL_R_OUT + 0.01, WELL_FLOOR - 0.3, 3, P.soil(), R))
    boolean(soil, lib.box("chan_hole", CH["x0"] - 0.2, CH["x1"] + 3, -1, CH["y1"] + 0.2, CH["floor"] - 0.16, 3,
                          P.soil(), R))
    P.prism("lift_road", [(-34, ground_top(-34) - 0.24), (0, -0.24), (0, 0.0), (-34, ground_top(-34))],
            0.0, 9.0, P.asphalt(), R)
    P.lawn("lift_lawn", WELL_R_OUT + LIFT_C[0] + 0.1, 20, CH["y1"] + 0.2, 9, parent=R, density=260, seed=31)
    P.lawn("lift_lawn_front", CH["x1"] + 0.05, 20, 0, CH["y1"] + 0.2, parent=R, density=260, seed=32)
    # the chamber: a concrete shaft cut in half, its floor and lid
    wall = P.revolve_half("well_wall", [(WELL_R_IN, WELL_FLOOR + 0.3), (WELL_R_OUT, WELL_FLOOR + 0.3),
                                        (WELL_R_OUT, WELL_TOP), (WELL_R_IN, WELL_TOP)],
                          (LIFT_C[0], LIFT_C[1], 0), P.concrete(), P.concrete_old(), R, n=64)
    carve(wall, LIFT_MAIN, MAIN_R, bend=0.0)
    P.revolve_half("well_floor", [(0.0, WELL_FLOOR), (WELL_R_OUT, WELL_FLOOR), (WELL_R_OUT, WELL_FLOOR + 0.3),
                                  (0.0, WELL_FLOOR + 0.3)], (LIFT_C[0], LIFT_C[1], 0), P.concrete(),
                   P.concrete_old(), R, n=64)
    P.revolve_half("well_lid", [(0.0, WELL_TOP), (WELL_R_OUT + 0.1, WELL_TOP),
                                (WELL_R_OUT + 0.1, WELL_TOP + 0.18), (0.0, WELL_TOP + 0.18)],
                   (LIFT_C[0], LIFT_C[1], 0), P.concrete(), P.concrete_old(), R, n=64)
    P.half_pipe("lift_main", LIFT_MAIN, MAIN_R, mat=P.pipe_concrete(), cut_mat=P.concrete(), parent=R, bend=0.0)
    P.pipe_water("lift_main_w", LIFT_MAIN, MAIN_R, level=0.05, mat=P.dirty_flow(1.4, "dirty_main_fast"),
                 parent=R, bend=0.0)
    end = V(LIFT_MAIN[-1])
    self.lift_pour, _ = P.stream("lift_pour", (end.x + 0.05, 0.14, end.z - 0.12), (0.9, 0, 0), 0.6,
                                 radius=0.09, parent=R, mat=P.fall(), flat=0.7)
    # the wet well's sewage: a half cylinder whose height (scale z) is the level
    self.well_water = P.revolve_half(
        "well_water", [(0.0, 0.0), (WELL_R_IN - 0.01, 0.0), (WELL_R_IN - 0.01, 1.0), (0.0, 1.0)], (0, 0, 0),
        P.water_glass("well_glass", P.DIRTY[0], alpha=0.5, foam=P.DIRTY[1], speed=0.1),
        P.water_glass("well_glass_cut", P.DIRTY[2], alpha=0.42), R, n=48)
    self.well_water.location = (LIFT_C[0], LIFT_C[1], WELL_FLOOR + 0.3)
    self.well_water.scale = (1, 1, 2.6)
    # the pump: blue motor, grey volute, guide rails, the discharge elbow to the riser
    blue = lib.flat("pump_blue", lib.hexrgb("#2F6FB6"), 0.35, coat=0.5)
    pump = lib.empty("pump", (3.2, 0.62, WELL_FLOOR + 0.3), R)
    lib.tube("pump_motor", [(0, 0, 0.32), (0, 0, 1.05)], 0.26, blue, pump)
    lib.tube("pump_cap", [(0, 0, 1.05), (0, 0, 1.16)], 0.2, blue, pump)
    lib.tube("pump_volute", [(0, 0, 0.0), (0, 0, 0.33)], 0.36, P.dark_steel(), pump)
    lib.tube("pump_lift_eye", [(0, 0, 1.16), (0, 0, 1.3)], 0.04, P.steel(), pump)
    lib.tube("pump_cable", [(0, -0.05, 1.2), (-0.25, 0.3, 2.2), (-0.4, 0.5, 8.6)], 0.02,
             lib.flat("cable", (0.02, 0.02, 0.02), 0.5), pump)
    lib.tube("pump_out", [(0.3, 0, 0.2), (0.6, 0, 0.2), (0.75, -0.6, 0.45)], 0.1, P.dark_steel(), pump)
    for dx in (-0.14, 0.14):
        lib.tube(f"rail{dx}", [(-0.1 + dx, 0.32, 0.0), (-0.1 + dx, 0.32, 8.7)], 0.025, P.steel(), pump)
    self.pump_ob = pump
    self.pump_home = V(pump.location)
    P.half_pipe("riser", RISER, RISER_R, mat=P.steel(), cut_mat=lib.flat("steel_cut", lib.hexrgb("#C9CED2"), 0.4),
                parent=R, bend=0.35)
    P.pipe_water("riser_w", RISER, RISER_R, level=0.9, mat=P.dirty_flow(1.6, "dirty_up"), parent=R, bend=0.35)
    self.arrows_up = [P.arrow(f"arrow_up{k}", (0, 0, 0), (0, 0, 1), size=0.13, parent=R) for k in range(3)]
    # the gravity channel the riser spills into (its front wall is cut away)
    c = CH
    lib.box("chan_floor", c["x0"], c["x1"], 0.0, c["y1"] + 0.2, c["floor"] - 0.15, c["floor"], P.concrete(), R)
    lib.box("chan_back", c["x0"], c["x1"], c["y1"], c["y1"] + 0.2, c["floor"], c["top"], P.concrete(), R)
    lib.box("chan_end", c["x0"] - 0.2, c["x0"], 0.0, c["y1"] + 0.2, c["floor"] - 0.15, c["top"], P.concrete(), R)
    P.prism("chan_water", [(c["x0"], c["floor"]), (c["x1"], c["floor"] - 0.25), (c["x1"], c["water"] - 0.25),
                           (c["x0"], c["water"])], 0.0, c["y1"],
            P.water("dirty_chan", P.DIRTY[0], P.DIRTY[1], speed=0.9, coord="Object", foam_amount=0.42), R,
            cut_mat=dirty_cut)
    P.stream("riser_pour", (6.1, 0.06, 0.62), (0.25, 0.06, -0.3), 0.3, radius=0.09, parent=R,
             mat=P.fall())
    P.foam("chan_foam", (6.3, 0.3, c["water"] + 0.02), 0.22, parent=R, seed=12)
    P.tree("lift_tree", (13.0, 6.0, 0.0), h=5.5, parent=R, seed=2)
    return R


def main_flow(self, s, e):
    self.on_station("lift", s, e)
    self.shot("lift", s, e, dict(center=(-21.0, 0, main_z(-21) + 0.15), width=1.9, yaw=20, pitch=8, lens=32),
              dict(center=(-16.5, 0, main_z(-16.5) + 0.15), width=1.9, yaw=20, pitch=8, lens=32))
    events.add(s, "water_rush", duration=e - s, gain=0.9)


def downhill(self, s, e):
    self.on_station("lift", s, e)
    self.shot("lift", s, e, dict(center=(-14.0, 0, main_z(-14.0) + 0.6), width=4.6, yaw=24, pitch=12, lens=28),
              dict(center=(-6.0, 0, main_z(-6.0) + 0.6), width=4.8, yaw=22, pitch=12, lens=28))
    events.add(s, "water_rush", duration=e - s, gain=0.7)


def too_deep(self, s, e):
    self.on_station("lift", s, e)
    self.shot("lift", s, e, dict(center=(0.6, 0, -4.4), width=7.4, yaw=14, pitch=8, lens=28),
              dict(center=(1.8, 0, -5.4), width=5.0, yaw=18, pitch=8, lens=28))
    lib.tween(self.well_water, "scale", s, e, (1, 1, 2.0), (1, 1, 3.0), "smooth")
    events.add(s, "pour", duration=e - s, gain=0.8)


def pump(self, s, e):
    self.on_station("lift", s, e)
    self.shot("lift", s, e, dict(center=(3.4, 0, WELL_FLOOR + 1.3), width=3.2, yaw=18, pitch=10, lens=30),
              dict(center=(3.9, 0, -2.6), width=3.4, yaw=18, pitch=12, lens=30))
    lib.tween(self.well_water, "scale", s, e, (1, 1, 3.0), (1, 1, 2.5), "smooth")
    for f in range(s, e + 1, 2):
        jig = V((((f * 7919) % 5 - 2) * 0.004, 0, ((f * 104729) % 5 - 2) * 0.003))
        lib.key(self.pump_ob, "location", f, tuple(self.pump_home + jig), interp="LINEAR")
    lib.key(self.pump_ob, "location", e + 2, tuple(self.pump_home))
    path = P.resample(RISER[:2], 0.2)
    for k, a in enumerate(self.arrows_up):
        P.ride(a, path, s, e, 2.2, offset=k * 3.0, normal_offset=(0, -0.006, 0))
    events.add(s, "pump", duration=e - s, gain=1.0)
    events.add(s, "water_rush", duration=e - s, gain=0.5)


def gravity_again(self, s, e):
    self.on_station("lift", s, e)
    self.shot("lift", s, e, dict(center=(6.0, 0, 0.35), width=3.6, yaw=12, pitch=18, lens=30),
              dict(center=(7.4, 0, 0.05), width=4.0, yaw=40, pitch=22, lens=30))
    events.add(s, "pour", duration=e - s, gain=0.8)
    events.add(s, "pump", duration=e - s, gain=0.4)


SHOTS = (build_lift, main_flow, downhill, too_deep, pump, gravity_again)
