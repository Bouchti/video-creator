"""Station B, the street: houses on both sides, lawns, sidewalks, a road with the sewer main in an open trench
under it, and every house line joining the main (the first one along the section face y = 0)."""
from engine import events
from engine.director import lib
from engine.flush import parts as P
from engine.flush.toilet import boolean

MAIN_X, MAIN_R = 8.0, 0.3
LAT_R = 0.1
WEST_HOUSES = (4.6, 16.0, 28.0)          # house centres (y); the first one's line runs along the cut face y = 0
EAST_HOUSES = (10.0, 22.0, 34.0)
WYE_Y = 16.0


def main_z(y):
    return -1.25 - 0.01 * y


def lateral_path(y, side=-1, wye=False):
    """A house line from under the front lawn down to the side of the main (side -1 = west houses)."""
    x0 = -3.6 if side < 0 else 19.6
    xe = MAIN_X + side * (MAIN_R * 0.85)
    if wye:
        return [(x0, y, -0.4), (xe + side * 1.2, y, main_z(y) + 0.12), (xe, y + 0.9, main_z(y + 0.9) + 0.06)]
    return [(x0, y, -0.4), (xe, y, main_z(y) + 0.06)]


def build_street(self):
    from engine.flush.film import carve
    R = self.root("street")
    main = [(MAIN_X, 0.0, main_z(0)), (MAIN_X, 44.0, main_z(44))]
    laterals = [(lateral_path(0.0), "front")]
    laterals += [(lateral_path(y, -1, wye=(y == WYE_Y)), "top") for y in WEST_HOUSES[1:]]
    laterals += [(lateral_path(y, 1), "top") for y in EAST_HOUSES]

    def cutters():
        out = [P.sweep_box_cutter("trench_main", main, 1.05, MAIN_R + 0.18, 4.0, R)]
        for k, (pts, mode) in enumerate(laterals):
            if mode == "top":
                out.append(P.sweep_box_cutter(f"trench_lat{k}", pts, 0.4, LAT_R + 0.12, 4.0, R))
        return out

    blocks = [P.soil_block("st_soil_w", -16, 2.4, 0, 46, -400.0, -0.04, R),
              P.soil_block("st_soil_road", 2.4, 13.6, 0, 46, -400.0, -0.25, R),
              P.soil_block("st_soil_e", 13.6, 32, 0, 46, -400.0, -0.04, R)]
    road = lib.box("road", 4.6, 11.4, 0, 46, -0.25, 0.0, P.asphalt(), R)
    walk_w = lib.box("walk_w", 2.4, 4.4, 0, 46, -0.25, 0.12, P.concrete(), R)
    walk_e = lib.box("walk_e", 11.6, 13.6, 0, 46, -0.25, 0.12, P.concrete(), R)
    kerb_w = lib.box("kerb_w", 4.4, 4.6, 0, 46, -0.3, 0.14, P.concrete_old(), R)
    kerb_e = lib.box("kerb_e", 11.4, 11.6, 0, 46, -0.3, 0.14, P.concrete_old(), R)
    for solid in blocks + [road, walk_w, walk_e, kerb_w, kerb_e]:
        for c in cutters():
            boolean(solid, c)
    for solid in blocks + [walk_w, kerb_w, road]:
        carve(solid, laterals[0][0], LAT_R)
    # beyond the modelled block the street and lawns simply continue (no trench, no blades)
    lib.box("st_far_soil", -140, 150, 46, 220, -400, -0.04, P.soil(), R)
    lib.box("st_far_turf", -140, 150, 46, 220, -0.04, 0.0, P.grass_top(), R)
    for side, (xa, xb) in (("w", (-140, -16)), ("e", (32, 150))):
        lib.box(f"st_side_soil_{side}", xa, xb, 0, 46, -400, -0.04, P.soil(), R)
        lib.box(f"st_side_turf_{side}", xa, xb, 0, 46, -0.04, 0.0, P.grass_top(), R)
    lib.box("road_far", 4.6, 11.4, 46, 220, -0.25, 0.006, P.asphalt(), R)
    lib.box("walk_w_far", 2.4, 4.4, 46, 220, -0.25, 0.12, P.concrete(), R)
    lib.box("walk_e_far", 11.6, 13.6, 46, 220, -0.25, 0.12, P.concrete(), R)
    paint = lib.flat("road_paint", (0.9, 0.9, 0.86), 0.5)
    for k in range(9):
        lib.box(f"edge_line_w{k}", 4.85, 4.97, 1 + k * 4.8, 1 + k * 4.8 + 3.2, 0.0, 0.004, paint, R)
        lib.box(f"edge_line_e{k}", 11.03, 11.15, 1 + k * 4.8, 1 + k * 4.8 + 3.2, 0.0, 0.004, paint, R)
    # lawns in strips between the house-line trenches
    for side, (xa, xb), ys in (("w", (-16, 2.4), WEST_HOUSES[1:]), ("e", (13.6, 32), EAST_HOUSES)):
        edges = [0.0] + [v for y in ys for v in (y - 0.4, y + 0.4)] + [46.0]
        for k in range(0, len(edges), 2):
            P.lawn(f"st_lawn_{side}{k}", xa, xb, edges[k], edges[k + 1], parent=R, density=140, seed=20 + k)
    for k, y in enumerate(WEST_HOUSES):
        P.house(f"house_w{k}", (-8.5, y, 0.0), w=7.0, d=6.0, yaw=90, parent=R,
                shutter_hex=("#4F7FB3", "#3E8E6B", "#B5523B")[k])
    for k, y in enumerate(EAST_HOUSES):
        P.house(f"house_e{k}", (24.5, y, 0.0), w=7.0, d=6.0, yaw=-90, parent=R,
                wall_hex=("#E6DCCB", "#F1E9DA", "#E9D8C0")[k], shutter_hex=("#7A5C8E", "#4F7FB3", "#3E8E6B")[k])
    for k, (x, y) in enumerate(((-13, 11), (-12.5, 23), (28, 17), (29, 29), (-13.5, 36), (28.5, 5))):
        P.tree(f"st_tree{k}", (x, y, 0), h=5.0, parent=R, seed=k + 3)
    # pipes and water
    P.half_pipe("main", main, MAIN_R, mode="top", mat=P.pipe_concrete(), cut_mat=P.concrete(), parent=R)
    P.pipe_water("main_w", main, MAIN_R, level=0.55, mode="top", mat=P.dirty_flow(1.1, "dirty_main"), parent=R)
    for k, (pts, mode) in enumerate(laterals):
        P.half_pipe(f"lat{k}", pts, LAT_R, mode=mode, parent=R)
        P.pipe_water(f"lat{k}_w", pts, LAT_R, level=(-0.05 if mode == "front" else 0.45), mode=mode,
                     mat=P.dirty_flow(0.9), parent=R)
    jy = WYE_Y + 0.9
    P.foam("junction_foam", (MAIN_X - 0.12, jy, main_z(jy) - 0.06), 0.12, parent=R, seed=5)
    self.street_main, self.street_laterals = main, laterals
    # arrows: along the cut-face lateral (facing the camera) and riding the main (facing up)
    self.arrow_lat = [P.arrow(f"arrow_lat{k}", (0, 0, 0), (1, 0, 0), size=0.07, parent=R) for k in range(2)]
    self.arrow_main = [P.arrow(f"arrow_main{k}", (0, 0, 0), (0, 1, 0), size=0.32, parent=R, normal=(0, 0, 1))
                       for k in range(4)]
    return R


def street_edge(self, s, e):
    self.on_station("street", s, e)
    self.shot("street", s, e, dict(center=(2.6, 0, -0.85), width=4.0, yaw=20, pitch=10, lens=30),
              dict(center=(5.4, 0, -1.35), width=4.4, yaw=24, pitch=11, lens=30))
    pts = P.resample(self.street_laterals[0][0], 0.1)
    for k, a in enumerate(self.arrow_lat):
        P.ride(a, pts, s, e, 1.0, offset=2.5 + k * 3.0, normal_offset=(0, -0.006, 0.0))
    events.add(s, "water_rush", duration=e - s, gain=0.55)
    events.add(s, "traffic", duration=e - s, gain=0.25)


def main_join(self, s, e):
    self.on_station("street", s, e)
    self.shot("street", s, e, dict(center=(7.0, 0, -1.7), width=2.6, yaw=24, pitch=14, lens=30),
              dict(center=(3.5, 9.0, -0.5), width=19, yaw=30, pitch=52, lens=30), ease="smooth")
    for k, a in enumerate(self.arrow_main):
        P.ride(a, self.street_main, s, e, 1.6, offset=k * 9.0, normal_offset=(0, 0, MAIN_R * 0.45 + 0.02))
    events.add(s, "water_rush", duration=e - s, gain=0.6)
    events.add(s, "traffic", duration=e - s, gain=0.3)


def every_house(self, s, e):
    self.on_station("street", s, e)
    self.shot("street", s, e, dict(center=(5.0, 9.0, -0.5), width=21, yaw=30, pitch=50, lens=30),
              dict(center=(6.5, 25.0, -0.5), width=23, yaw=16, pitch=50, lens=30))
    for k, a in enumerate(self.arrow_main):
        P.ride(a, self.street_main, s, e, 1.6, offset=k * 9.0 + 4, normal_offset=(0, 0, MAIN_R * 0.45 + 0.02))
    events.add(s, "water_rush", duration=e - s, gain=0.5)
    events.add(s, "traffic", duration=e - s, gain=0.3)


def junction(self, s, e):
    self.on_station("street", s, e)
    jy = WYE_Y + 0.6
    self.shot("street", s, e, dict(center=(7.6, jy, main_z(jy) + 0.1), width=2.2, yaw=-6, pitch=58, lens=32),
              dict(center=(7.7, jy + 0.2, main_z(jy) + 0.1), width=1.9, yaw=14, pitch=56, lens=32))
    events.add(s, "water_rush", duration=e - s, gain=0.8)
    events.add(s + 6, "splash", gain=0.4)


SHOTS = (build_street, street_edge, main_join, every_house, junction)
