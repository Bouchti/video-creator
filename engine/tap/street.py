"""Station D, the street: a residential street running along x, with a stepped cutaway.

  - the section plane y = 0 cuts the street along its length: its layers (asphalt, base course, soil, the sand
    and gravel beds) and, under it, the blue water main (cut lengthwise, always FULL, under pressure) and, deeper,
    the concrete sewer (half full, gravity);
  - a second section plane x = XS cuts across the street where the house's service pipe leaves the main: an 8 m
    wide notch (x from XS - 8 to XS, y from 0 to the house) is removed down below the sewer, so on that face the
    copper service pipe shows cut lengthwise, from the corporation stop on the main's crown, under the road, the
    kerb and the verge (curb stop), the sidewalk, through the meter pit and into the house's foundation.

The service pipe's sweeps are built in the usual "front" frame (keep y >= 0) under an empty turned -90 degrees
about Z, which maps local +y to world +x: they keep x >= XS and their cut faces lie on x = XS."""
import math
import random

from mathutils import Vector

from engine import events
from engine.director import lib
from engine.flush import parts as P
from engine.flush.toilet import boolean
from engine.tap.tower import carve, ride_dir

V = Vector
X0, X1 = -70.0, 90.0                # the modelled block (the street continues beyond it without detail)
Y1 = 60.0
XS = 0.0                            # the second section plane: where the service pipe leaves the main
NOTCH_X0, NOTCH_Z = XS - 8.0, -3.3
MZ, MR, MWALL = -1.1, 0.3, 0.045    # water main: axis depth, radius, ductile-iron wall
SZ, SR = -2.45, 0.45                # sewer main
SVR = 0.07                          # service pipe radius (drawn over life size so it reads)
SV_Z = -0.62                        # service pipe axis depth
ROAD_Y1 = 6.5
KERB = (6.5, 6.7)
VERGE = (6.7, 8.0)
WALK = (8.0, 9.8)
YARD_Y0 = 9.8
HOUSE_X, HOUSE_Y = 3.6, 20.5        # house centre (front wall at y = 17.5, door at x = HOUSE_X)
FOUND_Y = (17.35, 17.7)
PIT = (XS, XS + 0.48, 10.25, 11.45)            # meter pit, inside faces (cut in half on x = XS)
PIT_FLOOR = -0.95
MY = 10.85                          # meter centre (y)
CURB_Y = 7.35
GROUND = 0.1                        # lawn level
METER_TOP = SV_Z + 0.21


def service_path():
    """World points (x = XS) of the service pipe: from the corporation stop on the main's crown to the house."""
    return [(XS, 0.12, MZ + MR + 0.1), (XS, 0.45, SV_Z), (XS, FOUND_Y[1] + 0.2, SV_Z), (XS, FOUND_Y[1] + 0.6,
                                                                                         SV_Z + 0.4)]


def _local(pts):
    """World points on the x = XS plane -> the frame empty's local section plane (x_local = -y, y_local = 0)."""
    return [(-y, 0.0, z) for _x, y, z in pts]


def _pieces(pts, gaps):
    """Split a straight-ish path (along +y) into the pieces outside the y-intervals in gaps."""
    path = P.resample(pts, 0.05)
    out, cur = [], []
    for p in path:
        inside = any(a <= p.y <= b for a, b in gaps)
        if inside:
            if len(cur) > 1:
                out.append(cur)
            cur = []
        else:
            cur.append(tuple(p))
    if len(cur) > 1:
        out.append(cur)
    return out


def build_street(self):
    R = self.root("street")
    rnd = random.Random(5)
    soil, conc, conc_old = P.soil(), P.concrete(), P.concrete_old()
    sand = lib.material("Ground054", scale=1.2, tint=(1.0, 0.93, 0.8), name="st_sand")
    gravel = P.gravel()
    asphalt = lib.material("Asphalt031", scale=0.45, tint=(0.42, 0.42, 0.44), name="st_asphalt_dark")
    base_mat = lib.material("Gravel023", scale=1.6, tint=(0.78, 0.78, 0.8), name="st_base")
    subbase = lib.material("Gravel023", scale=2.4, tint=(1.0, 0.86, 0.68), name="st_subbase")
    copper = lib.flat("copper", lib.hexrgb("#C9794A"), 0.25, metallic=1.0)
    copper_cut = lib.flat("copper_cut", lib.hexrgb("#E39A6B"), 0.3, metallic=1.0)
    brass = lib.flat("st_brass", lib.hexrgb("#C9A04A"), 0.28, metallic=1.0)
    # the main: dark blue-grey ductile iron, a lighter cut rim, a grey mortar lining, clear water flowing -x
    pipe = lib.flat("st_ductile", lib.hexrgb("#3F4E5E"), 0.45, metallic=0.6)
    pipe_cut = lib.flat("st_ductile_cut", lib.hexrgb("#C9D1D8"), 0.4, metallic=0.3)
    lining = lib.flat("st_lining", lib.hexrgb("#B7BBB6"), 0.8)
    flow = P.water_glass("st_main_water", "#9ED8EE", alpha=0.32, foam="#EAF8FE", speed=-0.7)
    flow_cut = P.water_glass("st_main_water_cut", "#62B4DC", alpha=0.42)
    sewer_in = lib.material("Concrete031", scale=0.6, tint=(0.62, 0.6, 0.56), name="st_sewer_in")
    svc_flow = P.water("st_service_flow", P.CLEAN[0], P.CLEAN[1], speed=0.9, foam_amount=0.25,
                       scale=(6.0, 3.0, 3.0))
    sewage = P.water("st_sewage", "#6E5634", "#A8916A", speed=-0.35, foam_amount=0.45, scale=(1.5, 4.0, 4.0))
    sewage_cut = P.water_section("st_sewage_cut", "#7A6040", "#3B2D1C")
    dark = P.dark_steel()
    frame = lib.empty("st_svc_frame", (XS, 0, 0), R)       # the x = XS section's frame (local y = world +x)
    frame.rotation_euler = (0, 0, -math.pi / 2)

    # ---- ground layers (boxes over the whole block, stacked in z), then the notch for the second section
    main_bed = (MZ - MR - 0.1, -0.55)
    sewer_bed = (SZ - SR - 0.15, SZ + SR + 0.2)
    layers = [
        lib.box("st_asphalt", X0, X1, 0, ROAD_Y1, -0.14, 0.0, asphalt, R),
        lib.box("st_base", X0, X1, 0, ROAD_Y1, -0.36, -0.14, base_mat, R),
        lib.box("st_subbase", X0, X1, 0, ROAD_Y1, -0.55, -0.36, subbase, R),
        lib.box("st_yard_soil", X0, X1, ROAD_Y1, Y1, -0.55, GROUND - 0.04, soil, R),
        lib.box("st_main_bed", X0, X1, 0, Y1, main_bed[0], main_bed[1], sand, R),
        lib.box("st_soil_mid", X0, X1, 0, Y1, sewer_bed[1], main_bed[0], soil, R),
        lib.box("st_sewer_bed", X0, X1, 0, Y1, sewer_bed[0], sewer_bed[1], gravel, R),
        P.soil_block("st_soil_deep", X0, X1, 0, Y1, -400.0, sewer_bed[0], R, deep_below=-6.0),
        lib.box("st_kerb", X0, X1, KERB[0], KERB[1], -0.35, 0.15, conc_old, R),
        lib.box("st_walk", X0, X1, WALK[0], WALK[1], -0.2, 0.13, conc, R),
    ]
    deep_lower = next(o for o in R.children if o.name == "st_soil_deep_deep")
    for solid in layers + [deep_lower]:
        boolean(solid, lib.box(f"{solid.name}_notch", NOTCH_X0, XS, -1, FOUND_Y[0], NOTCH_Z, 3.0, None, R))
    for solid in layers[3:5]:
        boolean(solid, lib.box(f"{solid.name}_pit", PIT[0] - 0.5, PIT[1] + 0.1, PIT[2] - 0.1, PIT[3] + 0.1,
                               PIT_FLOOR - 0.1, 3.0, None, R))
    main = [(X0 - 1, 0, MZ), (X1 + 1, 0, MZ)]
    sewer = [(X0 - 1, 0, SZ), (X1 + 1, 0, SZ)]
    carve(layers[4], main, MR + 0.005, step=0.5)
    carve(layers[4], [(XS - 0.05, 0, MZ), (XS + 0.43, 0, MZ)], MR + 0.056, bend=0.0, step=0.05)
    carve(layers[6], sewer, SR + 0.005, step=0.5)
    # the service pipe's groove in the x = XS face (made in the frame's local section plane)
    svc = service_path()
    for k, solid in enumerate([layers[i] for i in (2, 3, 4)]):
        groove = P.solid_tube(f"st_svc_groove{k}", _local(svc), SVR + 0.006, solid.data.materials[0], frame,
                              bend=0.25, step=0.1)
        boolean(solid, groove)
        if not solid.data.polygons:
            raise RuntimeError(f"carving {solid.name} emptied it")
    # beyond the block: plain ground on every side, so no camera ever sees the void
    lib.box("st_far_soil", -400, 400, Y1, 500, -400, GROUND - 0.04, soil, R)
    lib.box("st_far_turf", -400, 400, Y1, 500, GROUND - 0.04, GROUND, P.grass_top(), R)
    for side, (xa, xb) in (("w", (-400, X0)), ("e", (X1, 400))):
        lib.box(f"st_side_soil_{side}", xa, xb, 0, Y1, -400, -0.12, soil, R)
        lib.box(f"st_side_road_{side}", xa, xb, 0, ROAD_Y1, -0.14, 0.0, asphalt, R)
        lib.box(f"st_side_turf_{side}", xa, xb, ROAD_Y1, Y1, -0.12, GROUND, P.grass_top(), R)
    paint = lib.flat("road_paint", (0.9, 0.9, 0.86), 0.5)
    for k in range(int((X1 - X0) / 6)):
        x = X0 + 1 + k * 6
        if x + 3.0 > NOTCH_X0 and x < XS:
            continue
        lib.box(f"st_line{k}", x, x + 3.0, 3.19, 3.31, 0.0, 0.004, paint, R)
    for k, (xa, xb) in enumerate(((X0, NOTCH_X0), (XS, X1))):        # solid edge lines along both kerbs
        lib.box(f"st_edge_near{k}", xa, xb, 0.3, 0.42, 0.0, 0.004, paint, R)
        lib.box(f"st_edge_far{k}", xa, xb, ROAD_Y1 - 0.42, ROAD_Y1 - 0.3, 0.0, 0.004, paint, R)
    # lawns: turf slabs everywhere outside the notch, grass blades near the section corner
    turf = P.grass_top()
    for k, (y0, y1) in enumerate((VERGE, (YARD_Y0, FOUND_Y[0]))):
        lib.box(f"st_turf_w{k}", X0, NOTCH_X0, y0, y1, GROUND - 0.04, GROUND, turf, R)
        xa = PIT[1] + 0.1 if k == 1 else XS
        lib.box(f"st_turf_e{k}", xa, X1, y0, y1, GROUND - 0.04, GROUND, turf, R)
        if k == 1:
            for j, (ya, yb) in enumerate(((y0, PIT[2] - 0.1), (PIT[3] + 0.1, y1))):
                lib.box(f"st_turf_pit{j}", XS, xa, ya, yb, GROUND - 0.04, GROUND, turf, R)
        spans = ([(XS + 0.02, 12.0)] if k == 0 else [(XS + 0.02, HOUSE_X - 0.65), (HOUSE_X + 0.65, 12.0)])
        for j, (lo, hi) in enumerate(spans):
            for m, (ya, yb) in enumerate(((y0, y1),) if k == 0 else ((y0, PIT[2] - 0.12), (PIT[3] + 0.12, y1))):
                blades = P.lawn(f"st_lawn{k}{j}{m}", lo, hi, ya + 0.03, yb - 0.03, z=GROUND, parent=R,
                                density=320, seed=60 + k * 7 + j * 3 + m, edge_overhang=0.0)
                blades[0].hide_render = blades[0].hide_viewport = True
    lib.box("st_lawn_beyond", X0, X1, FOUND_Y[1], Y1, GROUND - 0.04, GROUND, turf, R)
    lib.box("st_path", HOUSE_X - 0.5, HOUSE_X + 0.5, WALK[1], FOUND_Y[0], GROUND - 0.02, GROUND + 0.025, conc, R)
    # the house's foundation wall, which the service pipe enters
    lib.box("st_found", HOUSE_X - 4.0, HOUSE_X + 4.0, FOUND_Y[0], FOUND_Y[1], -1.3, GROUND + 0.03, conc, R)

    # ---- houses along the street (ours first), trees
    for k, (x, wall, shut) in enumerate(((HOUSE_X, "#EDE3CF", "#4F7FB3"), (HOUSE_X - 13.5, "#E6DCCB", "#3E8E6B"),
                                         (HOUSE_X + 13.5, "#F1E9DA", "#B5523B"), (HOUSE_X - 27.0, "#E9D8C0", "#7A5C8E"),
                                         (HOUSE_X + 27.0, "#EDE3CF", "#4F7FB3"))):
        P.house(f"st_house{k}", (x, HOUSE_Y, GROUND), w=8.0, d=6.0, yaw=0, parent=R, wall_hex=wall,
                shutter_hex=shut)
    for k, (x, y) in enumerate(((9.5, 14.0), (-14.0, 14.0), (-20.0, 13.0), (22.0, 14.5), (-35, 15), (37, 13.5))):
        P.tree(f"st_tree{k}", (x, y, GROUND), h=rnd.uniform(5.0, 6.5), parent=R, seed=40 + k)
    for k in range(9):
        x = X0 + 8 + k * 18 + rnd.uniform(-3, 3)
        if abs(x - HOUSE_X) < 9:
            continue
        P.tree(f"st_far_tree{k}", (x, rnd.uniform(28, 45), GROUND), h=rnd.uniform(6, 8), parent=R, seed=60 + k)

    # ---- the mains (the notch interrupts them: each runs in two pieces)
    for k, (xa, xb) in enumerate(((X0 - 1, NOTCH_X0), (XS, X1 + 1))):
        m = [(xa, 0, MZ), (xb, 0, MZ)]
        sw = [(xa, 0, SZ), (xb, 0, SZ)]
        P.half_pipe(f"st_main{k}", m, MR, wall=MWALL, mat=pipe, cut_mat=pipe_cut, parent=R, step=0.5, n=32)
        P.half_pipe(f"st_lining{k}", m, MR - MWALL - 0.001, wall=0.014, mat=lining, cut_mat=lining, parent=R,
                    step=0.5, n=32)
        P.pipe_water(f"st_main_w{k}", m, (MR - MWALL - 0.018) / 0.985, level=0.97, mat=flow, section_mat=flow_cut,
                     parent=R, step=0.5, n=32)
        P.half_pipe(f"st_sewer{k}", sw, SR, wall=0.075, mat=sewer_in, cut_mat=conc, parent=R, step=0.5, n=32)
        P.pipe_water(f"st_sewer_w{k}", sw, SR - 0.07, level=-0.05, mat=sewage, section_mat=sewage_cut, parent=R,
                     step=0.5, n=32)
    # the tapping saddle round the main and the corporation stop on its crown (cut on x = XS too)
    P.half_pipe("st_saddle", [(XS, 0, MZ), (XS + 0.38, 0, MZ)], MR + 0.05, wall=0.045, mat=brass, cut_mat=brass,
                parent=R, bend=0.0, step=0.05, n=32)
    for k, x in enumerate((XS + 0.06, XS + 0.32)):           # the saddle's clamp lugs and bolts
        lib.box(f"st_lug{k}", x - 0.03, x + 0.03, 0.0, MR + 0.12, MZ - 0.02, MZ + 0.02, brass, R, bevel=0.008)
        lib.tube(f"st_bolt{k}", [(x, MR + 0.08, MZ - 0.07), (x, MR + 0.08, MZ + 0.07)], 0.012, dark, R, resolution=8)
    crown = MZ + MR + 0.05
    lib.box("st_corp", XS - 0.065, XS + 0.065, 0.03, 0.21, crown - 0.01, crown + 0.15, brass, R, bevel=0.015)
    lib.tube("st_corp_stem", [(XS, 0.12, crown + 0.15), (XS, 0.12, crown + 0.22)], 0.018, brass, R, resolution=8)
    lib.box("st_corp_tee", XS - 0.07, XS + 0.07, 0.105, 0.135, crown + 0.21, crown + 0.235, brass, R, bevel=0.005)

    # ---- the service pipe on the x = XS face: copper, cut lengthwise, running full; whole through the pit
    pit_gap = (PIT[2] - 0.02, PIT[3] + 0.02)
    for k, piece in enumerate(_pieces(svc, [pit_gap])):
        P.half_pipe(f"st_svc{k}", _local(piece), SVR, mat=copper, cut_mat=copper_cut, parent=frame, bend=0.25,
                    step=0.05)
        P.pipe_water(f"st_svc_w{k}", _local(piece), SVR, level=0.97, mat=svc_flow,
                     section_mat=P.water_section("st_svc_cut", P.CLEAN[0], P.CLEAN[2]), parent=frame, bend=0.25,
                     step=0.05)
    # curb stop: a brass valve on the pipe and its cast-iron valve box up to the verge
    lib.box("st_curb_valve", XS, XS + 0.09, CURB_Y - 0.1, CURB_Y + 0.1, SV_Z - 0.075, SV_Z + 0.09, brass, R,
            bevel=0.012)
    curb_at = lib.empty("st_curb_at", _local([(XS, CURB_Y, 0.0)])[0], frame)
    P.revolve_half("st_curb_box", [(0.05, SV_Z + 0.09), (0.07, SV_Z + 0.09), (0.07, GROUND + 0.03),
                                   (0.05, GROUND + 0.03)], (0, 0, 0), dark, dark, curb_at, n=24)
    lib.tube("st_curb_key", [(XS + 0.01, CURB_Y, SV_Z + 0.09), (XS + 0.01, CURB_Y, SV_Z + 0.6)], 0.012, dark, R,
             resolution=8)
    # the meter pit (cut in half), the lid lifted off onto the lawn
    x0, x1, y0, y1 = PIT
    t = 0.1
    for name, box in (("e", (x1, x1 + t, y0 - t, y1 + t)), ("s", (x0, x1, y0 - t, y0)), ("n", (x0, x1, y1, y1 + t))):
        lib.box(f"st_pit_{name}", *box, PIT_FLOOR, GROUND + 0.06, conc, R)
    lib.box("st_pit_floor", x0, x1 + t, y0 - t, y1 + t, PIT_FLOOR - 0.1, PIT_FLOOR, conc, R)
    lib.box("st_pit_gravel", x0, x1, y0, y1, PIT_FLOOR, PIT_FLOOR + 0.06, gravel, R)
    for name, box in (("e", (x1 - 0.03, x1 + 0.13, y0 - 0.13, y1 + 0.13)), ("s", (x0, x1, y0 - 0.13, y0 + 0.03)),
                      ("n", (x0, x1, y1 - 0.03, y1 + 0.13))):     # the cast-iron frame the lid sits in
        lib.box(f"st_pit_frame_{name}", *box, GROUND + 0.06, GROUND + 0.09, dark, R)
    lid = lib.box("st_pit_lid", -0.42, 0.42, -0.35, 0.35, 0.0, 0.045, dark, R, bevel=0.01)
    lid.location = (x1 + 0.75, y1 + 0.5, GROUND + 0.005)
    lid.rotation_euler = (0, 0, math.radians(16))
    for k, (ya, yb) in enumerate(((y0 - 0.12, MY - 0.17), (MY + 0.17, y1 + 0.12))):
        lib.tube(f"st_pit_pipe{k}", [(XS, ya, SV_Z), (XS, yb, SV_Z)], SVR * 0.85, copper, R, resolution=16)
    lever = lib.flat("st_valve_lever", lib.hexrgb("#2F6DB0"), 0.4)
    for k, y in enumerate((y0 + 0.13, y1 - 0.13)):
        lib.blob(f"st_ballvalve{k}", 0.075, brass, (XS, y, SV_Z), squash=1.0, parent=R, lumpy=0.0, subdiv=2)
        lib.box(f"st_lever{k}", XS - 0.014, XS + 0.014, y - 0.11, y + 0.02, SV_Z + 0.065, SV_Z + 0.093, lever, R)
    self.st_dial_root = _meter(R, brass)

    # ---- arrows: along the main and the sewer (section y = 0) and along the service pipe (section x = XS)
    self.st_main_path = [(7.0, 0, MZ - 0.04), (XS + 0.05, 0, MZ - 0.04)]          # flowing -x, toward the branch
    self.st_sewer_path = [(9.0, 0, SZ - SR * 0.5), (XS + 0.1, 0, SZ - SR * 0.5)]
    self.st_svc_path = _local(P.resample(P.rounded(svc[:3], 0.25), 0.05))
    self.st_arrows_main = [P.arrow(f"st_arrow_m{k}", (0, 0, 0), (1, 0, 0), size=0.17, parent=R) for k in range(12)]
    self.st_arrows_sewer = [P.arrow(f"st_arrow_s{k}", (0, 0, 0), (1, 0, 0), size=0.2, parent=R) for k in range(8)]
    self.st_arrows_svc = [P.arrow(f"st_arrow_v{k}", (0, 0, 0), (1, 0, 0), size=0.08, parent=frame)
                          for k in range(14)]

    # ---- anchors for the callouts
    self.anchor("street", "water_main", (XS + 2.5, -0.03, MZ + 0.08))
    self.anchor("street", "sewer_main", (XS + 3.1, -0.03, SZ - SR * 0.5))
    self.anchor("street", "service_pipe", (XS - 0.03, 0.62, SV_Z))
    self.anchor("street", "meter", (XS, MY, METER_TOP + 0.03))
    return R


def _meter(R, brass):
    """An inline water meter: brass body on the pipe, a round register on top with a white dial, a red sweep hand
    (it turns while water flows), black number wheels, a glass lens."""
    lib.tube("st_meter_body", [(XS, MY - 0.17, SV_Z), (XS, MY + 0.17, SV_Z)], 0.095, brass, R, resolution=16)
    for k, y in enumerate((MY - 0.17, MY + 0.17)):
        lib.tube(f"st_meter_flange{k}", [(XS, y - 0.015, SV_Z), (XS, y + 0.015, SV_Z)], 0.108, brass, R,
                 resolution=16)
    P.cylinder("st_meter_reg", (XS, MY), 0.105, SV_Z, METER_TOP - 0.012, brass, R, n=48)
    dial = lib.flat("st_dial", lib.hexrgb("#F4F2EA"), 0.5, emission=0.15)
    P.cylinder("st_meter_dial", (XS, MY), 0.092, METER_TOP - 0.02, METER_TOP - 0.006, dial, R, n=48)
    ink = lib.flat("st_ink", lib.hexrgb("#1E2226"), 0.5)
    for k in range(12):
        a = 2 * math.pi * k / 12
        r0, r1 = (0.064, 0.084) if k % 3 == 0 else (0.073, 0.084)
        c, s = math.cos(a), math.sin(a)
        lib.tube(f"st_tick{k}", [(XS + r0 * c, MY + r0 * s, METER_TOP - 0.005),
                                 (XS + r1 * c, MY + r1 * s, METER_TOP - 0.005)], 0.0035, ink, R, resolution=4)
    # the number wheels run along y, so they read square on from the camera (which looks along +x)
    lib.box("st_wheels", XS - 0.058, XS - 0.03, MY - 0.05, MY + 0.05, METER_TOP - 0.008, METER_TOP - 0.004, ink, R)
    white = lib.flat("st_digits", lib.hexrgb("#E8E8E8"), 0.5, emission=0.3)
    for k in range(5):
        y = MY - 0.04 + k * 0.02
        lib.box(f"st_digit{k}", XS - 0.053, XS - 0.035, y - 0.0065, y + 0.0065, METER_TOP - 0.004,
                METER_TOP - 0.003, white, R)
    root = lib.empty("st_sweep", (XS + 0.015, MY, METER_TOP - 0.003), R)
    lib.box("st_sweep_hand", -0.004, 0.004, -0.01, 0.06, 0.0, 0.003, lib.flat("st_red", lib.hexrgb("#D2312B"), 0.4),
            root)
    lib.blob("st_sweep_hub", 0.009, ink, (0, 0, 0.003), squash=0.5, parent=root, lumpy=0.0, subdiv=2)
    lens = lib.flat("st_lens", lib.hexrgb("#F2F8FB"), 0.02, alpha=0.15, coat=1.0)
    lib.blob("st_meter_lens", 0.096, lens, (XS, MY, METER_TOP - 0.006), squash=0.12, parent=R, lumpy=0.0)
    return root


# ---------------------------------------------------------------- shots

def _ride(arrows, path, s, e, speed, normal_offset=(0, -0.025, 0)):
    L = sum((V(b) - V(a)).length for a, b in zip(path, path[1:]))
    for k, a in enumerate(arrows):
        ride_dir(a, path, s, e, speed, offset=k * L / len(arrows), normal_offset=normal_offset)


def _spin(self, s, e, turns_per_s=0.9):
    """The sweep hand turns while water flows; its angle is a function of the frame, so beats join seamlessly."""
    r = self.st_dial_root
    for f in (s, e):
        lib.key(r, "rotation_euler", f, (0, 0, -2 * math.pi * turns_per_s * f / 30.0), interp="LINEAR")


INSIDE = (0, 0.06, 0)      # main arrows ride inside the water, behind its see-through cut face


def main(self, s, e):
    self.on_station("street", s, e)
    self.shot("street", s, e, dict(center=(XS + 2.6, 0, -0.74), width=1.5, yaw=-18, pitch=25, lens=50),
              dict(center=(XS + 2.75, 0, -0.76), width=1.42, yaw=-16, pitch=25, lens=50))
    _ride(self.st_arrows_main, self.st_main_path, s, e, 1.6, INSIDE)
    events.add(s, "water_rush", duration=e - s, gain=0.5)


def sewer(self, s, e):
    self.on_station("street", s, e)
    self.shot("street", s, e, dict(center=(XS + 2.9, 0, -1.8), width=3.0, yaw=-22, pitch=16, lens=40),
              dict(center=(XS + 3.0, 0, -1.8), width=2.85, yaw=-20, pitch=16, lens=40))
    _ride(self.st_arrows_main, self.st_main_path, s, e, 1.6, INSIDE)
    _ride(self.st_arrows_sewer, self.st_sewer_path, s, e, 0.45)
    events.add(s, "water_rush", duration=e - s, gain=0.45)


def service(self, s, e):
    """Close on the branch: the main (cut open) at the bottom, the brass saddle and stop valve, the copper pipe
    leaving for the house; the camera glides along it toward the curb stop."""
    self.on_station("street", s, e)
    self.shot("street", s, e, dict(center=(XS + 0.12, 0.28, -0.8), width=1.35, yaw=-42, pitch=24, lens=35),
              dict(center=(XS + 0.04, 0.85, -0.72), width=1.3, yaw=-50, pitch=24, lens=35))
    _ride(self.st_arrows_main, self.st_main_path, s, e, 1.6, INSIDE)
    _ride(self.st_arrows_svc, self.st_svc_path, s, e, 1.1)
    _spin(self, s, e)
    events.add(s, "pour", duration=e - s, gain=0.35)


def meter(self, s, e):
    self.on_station("street", s, e)
    self.shot("street", s, e, dict(center=(XS + 0.12, MY + 0.1, -0.5), width=1.3, yaw=-46, pitch=30, lens=35),
              dict(center=(XS + 0.1, MY + 0.06, -0.5), width=1.22, yaw=-50, pitch=31, lens=35))
    _ride(self.st_arrows_svc, self.st_svc_path, s, e, 1.1)
    _spin(self, s, e)
    events.add(s, "pour", duration=e - s, gain=0.3)
    events.add(s + 4, "click", gain=0.25)


SHOTS = (build_street, main, sewer, service, meter)
