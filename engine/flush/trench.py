"""The yard trench: the house line leaves the foundation in an open trench (cut along its top, grass on both
edges) and runs downhill across the front yard to the sidewalk, where it dives under the kerb. Seen from above
at an angle, the way the reference films its pipes."""
from engine import events
from engine.director import lib
from engine.flush import parts as P
from engine.flush.toilet import boolean

R_PIPE = 0.1
PATH = [(-1.3, 0, -0.3), (19.8, 0, -0.85), (23.5, 0, -1.0)]
HALF_W = 0.34                 # the trench is open on its near side: the block's cut face starts there
TRENCH_END = 19.8


def build_trench(self):
    R = self.root("trench")
    trench_path = [PATH[0], PATH[1]]

    def cutter():
        return P.sweep_box_cutter("yard_trench", trench_path, HALF_W + 0.25, R_PIPE + 0.12, 4.0, R)

    soil = P.soil_block("tr_soil", -14, 20.2, -HALF_W, 14, -400, -0.04, R)
    boolean(soil, cutter())
    turf = lib.box("tr_turf", -14, 20.2, -HALF_W, 14, -0.04, 0.0, P.grass_top(), R)
    boolean(turf, cutter())
    P.lawn("tr_lawn", -0.6, 20.2, HALF_W + 0.27, 14, parent=R, density=420, seed=60)[0].hide_render = True
    P.house("tr_house", (-4.6, 3.8, 0.0), w=7.0, d=6.0, yaw=0, parent=R)
    # sidewalk, kerb and road where the line dives under the street
    walk_soil = lib.box("tr_walk_soil", 20.2, 40, 0.0, 14, -400, -0.25, P.soil(), R)
    from engine.flush.film import carve
    carve(walk_soil, [(19.0, 0, PATH[1][2] + 0.04), PATH[1], PATH[2], (40, 0, -1.6)], R_PIPE, bend=0.0)
    lib.box("tr_walk", 20.2, 22.2, 0.0, 14, -0.25, 0.12, P.concrete(), R)
    lib.box("tr_kerb", 22.2, 22.4, 0.0, 14, -0.3, 0.14, P.concrete_old(), R)
    lib.box("tr_road", 22.4, 40, 0.0, 14, -0.25, 0.0, P.asphalt(), R)
    under = [PATH[1], PATH[2], (40, 0, -1.6)]
    P.half_pipe("tr_pipe_under", under, R_PIPE, parent=R, bend=0.0)
    P.pipe_water("tr_water_under", under, R_PIPE, level=-0.1, mat=P.dirty_flow(0.9), parent=R, bend=0.0)
    # the pipe and its water, in the open trench
    P.half_pipe("tr_pipe", trench_path, R_PIPE, mode="top", parent=R)
    P.pipe_water("tr_water", trench_path, R_PIPE, level=0.42, mode="top", mat=P.dirty_flow(0.9), parent=R)
    self.tr_arrows = [P.arrow(f"arrow_tr{k}", (0, 0, 0), (1, 0, 0), size=0.09, parent=R, normal=(0, 0, 1))
                      for k in range(4)]
    for k, (x, y) in enumerate(((6, 9), (13, -3.5), (-9, -3))):
        P.tree(f"tr_tree{k}", (x, y, 0), h=5.0, parent=R, seed=90 + k)
    return R


def _arrows(self, s, e, offset=0.0):
    surface = [(x, y, z - R_PIPE * (1 - 0.42) + 0.006) for x, y, z in (PATH[0], PATH[1])]
    for k, a in enumerate(self.tr_arrows):
        P.ride(a, surface, s, e, 1.0, offset=offset + k * 5.3)


def keep_going(self, s, e):
    self.on_station("trench", s, e)
    self.shot("trench", s, e, dict(center=(1.4, 0.05, -0.42), width=1.9, yaw=32, pitch=46, lens=32),
              dict(center=(6.5, 0.05, -0.55), width=2.2, yaw=26, pitch=44, lens=32))
    _arrows(self, s, e)
    events.add(s, "water_rush", duration=e - s, gain=0.6)


def street_edge(self, s, e):
    self.on_station("trench", s, e)
    self.shot("trench", s, e, dict(center=(17.6, 0.05, -0.76), width=2.2, yaw=24, pitch=40, lens=32),
              dict(center=(20.3, 0.0, -0.85), width=2.8, yaw=18, pitch=32, lens=32))
    _arrows(self, s, e, offset=12.0)
    events.add(s, "water_rush", duration=e - s, gain=0.55)
    events.add(s, "traffic", duration=e - s, gain=0.25)


SHOTS = (build_trench, keep_going, street_edge)
