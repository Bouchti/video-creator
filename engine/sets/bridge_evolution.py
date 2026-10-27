"""
BRIDGE EVOLUTION set — Blender builder (see bridge_evolution_spec.py), built on engine/evo_kit.py.

One river valley seen from drone height. The river runs along Y; every bridge spans X, centred on
the origin. Each new bridge answers the real limit of the one before:

  a wagon of stone snaps the planks → the stone arch carries it (same 6 m stream);
  the railway must cross downstream, where the river is 40 m wide and tall ships sail: a stone arch
  there would put piers in their path → the steel truss;
  the city must cross the bay at the river mouth: a truss that long would sag under its own weight
  → the suspension bridge; then summer heat and wind teach it two more fixes.

A move downstream is always a hard cut (cut_to_gap): the banks never slide apart on screen, and an
old bridge is never destroyed for no reason: it is simply left behind upstream.

  plank (beam) → stone arch → steel truss → suspension → + expansion joint → + stiffening truss

The format's signature white line-drawings (triangle vs square, the box around the expansion
joint, wind streaks, load arrows) are emissive 3D curves that draw themselves on.
"""
import math
import random

import bpy
from mathutils import Vector

from engine import events, textures as tx, toy
from engine.evo_kit import (WATER_Z, EvolutionSet, _hide, _key, base_box, beam, draw_on, ease, emissive,
                            extrude_xz, face_camera, fly_in, mat, mesh_obj, pop_in, show_between, stroke, attach)
from engine.machines import Puffs
from engine.sets.bridge_evolution_spec import ACTIONS

V = Vector
R = math.radians
GAP = {"plank": 6.0, "arch": 6.0, "truss": 40.0, "suspension": 120.0}   # the arch replaces the planks
PLANK_TOP = 0.455                    # top of the plank deck (z)
QUEUE_Z = -0.12                      # car root height on the shore road
TOWER_X, TOWER_TOP, SAG_Z = 40.0, 24.0, 2.2
CABLE_Y, DECK_HALF_W = 5.4, 5.5
SEG = 5.0                            # suspension deck segment length (m)
DECK_X0, DECK_X1 = -65.0, 65.0
JOINT_X = 20.0                       # a segment edge in the main span (clear of the towers)
BUCKLE_X = JOINT_X                   # the heat buckle peaks where the joint goes (the cables are high enough there)
SHIP_X = -9.0                        # the ship's lane at the railway crossing: straight at the left pier
SHIP_Y = 26.0                        # where the ship has come to when the arch is gone (bow ~13 m clear of the truss)
HOT_SUN = (1.0, 0.62, 0.32)          # sun colour on the hot afternoon
HOT_SKY = (1.8, 0.85, 0.36)          # the hot sky: amber at the sky's own brightness (luminance ~1)
HOT_SKY_MIX = 0.85                   # how far the sky turns to HOT_SKY at full heat
HOT_WB = 3200.0                     # white-balance shift (K) on the hot afternoon: AgX eats a subtle tint
DUST = "#C4AD86"                     # buckle dust: light tan, it must read against the dark asphalt and river
FLUTTER_MAX = 15.0                   # peak wind twist of the deck (degrees, at the quarter spans)
TWIST_PERIOD, HEAVE_PERIOD = 37, 53  # flutter periods (frames): unequal, so evenly spaced stills never repeat a pose

def cable_z(x):
    """Height of the main cable above the deck line at x (parabola between towers, sagging side spans)."""
    ax = abs(x)
    if ax <= TOWER_X:
        return SAG_Z + (TOWER_TOP - SAG_Z) * (ax / TOWER_X) ** 2
    t = (ax - TOWER_X) / (75.0 - TOWER_X)                  # tower top → anchorage (x = ±75, z = 2)
    return TOWER_TOP + (2.0 - TOWER_TOP) * t - 2.2 * math.sin(math.pi * t)



class BridgeEvolutionSet(EvolutionSet):
    ACTIONS = ACTIONS
    START_GAP = GAP["plank"]

    def build(self):
        self._plank_bridge()
        self._arch_bridge()
        self._truss_bridge()
        self._suspension_bridge()
        self._ship()
        self._cars()
        self._queue_cars()
        self._heat_cars()

    # ------------------- the bridges (built hidden; the actions animate them) -------------------

    def _plank_bridge(self):
        """Two log beams and a plank deck over the 6 m stream, built as 24 thin slices across the span
        (a plank + its piece of each log and rail) so the deck can bow, snap and break up in the water.
        The slices are world-level (not on the banks): a_heavy_load moves them along the sag curve."""
        self.plank_slices = []                                   # (slice root, rest x)
        self.planks, self.plank_logs, self.plank_rails = [], [], []
        n = 12
        for side, sgn in (("L", -1), ("R", 1)):
            for k in range(n):
                u = sgn * (0.18 + k * 0.36)
                root = toy.empty(f"plank_slice_{side}{k}", (u, 0, 0))
                pl = toy.box(f"plank_{side}{k}", (0.32, 2.7, 0.07), (u, 0, 0.42), mat=self.m_plank, bevel=0.01,
                             rotation=(0, 0, R(self.rnd.uniform(-2, 2))))
                attach(pl, root)
                self.planks.append((u, pl))
                # log and rail pieces overlap their neighbours (alternating radius: no z-fighting), so the
                # beams read as continuous until the deck stretches and snaps
                alt = (k % 2) * 0.015
                for y in (-0.95, 0.95):
                    log = toy.cylinder(f"plank_log_{side}{y}_{k}", 0.2 + alt, 0.5, (u, y, 0.18),
                                       rotation=(0, R(90), 0), mat=self.m_log, vertices=12)
                    attach(log, root)
                    self.plank_logs.append((log, sgn))
                for y in (-1.3, 1.3):
                    if k in (0, 4, 8, 11):
                        post = toy.cylinder(f"plank_post_{side}{y}{k}", 0.05, 1.0, (u, y, 0.9), mat=self.m_log,
                                            vertices=8)
                        attach(post, root)
                        self.plank_rails.append(post)
                    rail = toy.cylinder(f"plank_rail_{side}{y}_{k}", 0.045 + alt * 0.6, 0.48, (u, y, 1.35),
                                        rotation=(0, R(90), 0), mat=self.m_log, vertices=8)
                    attach(rail, root)
                    self.plank_rails.append(rail)
                self.plank_slices.append((root, u))
        self.plank_slices.sort(key=lambda t: t[1])
        self.planks = [pl for _, pl in sorted(self.planks, key=lambda t: t[0])]
        # a little hand cart that crosses it
        self.cart = toy.empty("cart", (-30, 0, 0.5))
        body = toy.box("cart_body", (1.6, 1.1, 0.5), (0, 0, 0.45), mat=self.m_plank, bevel=0.03)
        body.parent = self.cart
        body.location = (0, 0, 0.45)
        for k, (x, y) in enumerate(((-0.5, -0.6), (0.5, -0.6), (-0.5, 0.6), (0.5, 0.6))):
            wh = toy.cylinder(f"cart_wheel{k}", 0.25, 0.08, (0, 0, 0), rotation=(R(90), 0, 0), mat=self.m_log, vertices=12)
            wh.parent = self.cart
            wh.location = (x, y, 0.25)
        toy.hide_tree(self.cart, 0, True)
        # two heavy wagons loaded with cut stone: one breaks the planks, one crosses the finished arch
        self.wagons = [self._wagon(f"wagon{k}") for k in range(2)]

    def _wagon(self, name):
        """A four-wheeled wagon heaped with grey stone blocks (root at wheel bottom)."""
        root = toy.empty(name, (-40, 0, 0.5))
        bed = toy.box(f"{name}_bed", (3.2, 1.7, 0.35), (0, 0, 0), mat=self.m_plank, bevel=0.03)
        bed.parent = root
        bed.location = (0, 0, 0.62)
        for k, (x, y) in enumerate(((-1.1, -0.95), (1.1, -0.95), (-1.1, 0.95), (1.1, 0.95))):
            wh = toy.cylinder(f"{name}_wheel{k}", 0.42, 0.12, (0, 0, 0), rotation=(R(90), 0, 0), mat=self.m_log,
                              vertices=14)
            wh.parent = root
            wh.location = (x, y, 0.42)
        rnd = random.Random(len(name))
        for k, (x, y, z, sz) in enumerate(((-0.8, -0.4, 1.05, 0.75), (0.1, -0.35, 1.05, 0.8), (0.95, -0.4, 1.0, 0.7),
                                           (-0.6, 0.4, 1.05, 0.75), (0.5, 0.42, 1.05, 0.8), (-0.1, 0.0, 1.6, 0.7))):
            st = toy.box(f"{name}_stone{k}", (sz * 1.15, sz, sz * 0.8), (0, 0, 0),
                         mat=self.m_stone2 if k % 2 else self.m_stone, bevel=0.06,
                         rotation=(0, 0, R(rnd.uniform(-12, 12))))
            st.parent = root
            st.location = (x, y, z)
        toy.hide_tree(root, 0, True)
        return root

    def _queue_cars(self):
        """Cars that wait at the shore of the bay (a_wide_bay): there is no bridge yet."""
        self.queue_cars = []
        for k, hexc in enumerate(("#3B6EA5", "#C33C2B", "#E8E6E0", "#D9A441", "#5C8C4A", "#2E2F33")):
            car = toy.empty(f"qcar{k}", (0, 0, -200))
            body = toy.box(f"qcar{k}_body", (4.3, 1.85, 0.75), (0, 0, 0), mat=mat(f"ev_qcar{k}", hexc, 0.3, coat=0.6),
                           bevel=0.12)
            body.parent = car
            body.location = (0, 0, 0.62)
            cab = toy.box(f"qcar{k}_cab", (2.3, 1.65, 0.62), (0, 0, 0), mat=mat("ev_glass", "#2B3440", 0.1), bevel=0.12)
            cab.parent = car
            cab.location = (-0.25, 0, 1.25)
            toy.hide_tree(car, 0, True)
            self.queue_cars.append(car)

    def _heat_cars(self):
        """Cars that brake hard short of the heat buckle (a_heat), each with brake lights that come on
        (scaled up) when it brakes. Separate from the traffic cars, whose crossing keys run on past
        their windows."""
        self.heat_cars = []
        red = emissive("ev_brake_light", "#FF2A1A", 8.0)
        for k, hexc in enumerate(("#C33C2B", "#D9A441", "#3B6EA5")):
            car = toy.empty(f"hcar{k}", (0, 0, -200))
            body = toy.box(f"hcar{k}_body", (4.3, 1.85, 0.75), (0, 0, 0), mat=mat(f"ev_hcar{k}", hexc, 0.3, coat=0.6),
                           bevel=0.12)
            body.parent = car
            body.location = (0, 0, 0.62)
            cab = toy.box(f"hcar{k}_cab", (2.3, 1.65, 0.62), (0, 0, 0), mat=mat("ev_glass", "#2B3440", 0.1), bevel=0.12)
            cab.parent = car
            cab.location = (-0.25, 0, 1.25)
            lights = []
            for y in (-0.62, 0.62):
                lt = toy.box(f"hcar{k}_brake{y}", (0.08, 0.38, 0.2), (0, 0, 0), mat=red, bevel=0)
                lt.parent = car
                lt.location = (-2.19, y, 0.78)
                lights.append(lt)
            toy.hide_tree(car, 0, True)
            self.heat_cars.append((car, lights))

    def cut_to_gap(self, f, gap):
        """A hard cut downstream to a wider crossing: the banks jump to `gap` on frame f (never on screen)."""
        for side, sgn in (("L", -1), ("R", 1)):
            root = self.banks[side]
            _key(root, f - 1, location=V(toy.value_at(root, "location", f - 1)))
            _key(root, f, location=V((sgn * gap / 2, 0, 0)))
            toy.set_interpolation(root, "location", (f - 1,), "CONSTANT")

    def _arch_bridge(self):
        """Stone arch springing from the waterline at the stream's edges, plus spandrel walls, road and parapets."""
        half = GAP["arch"] / 2
        rise_top = -1.4                                       # intrados crown
        s = rise_top - WATER_Z
        Rr = (half ** 2 + s ** 2) / (2 * s)
        cz = rise_top - Rr
        a_max = math.asin(half / Rr)
        ring = 0.85
        self.arch_root = toy.empty("arch_root", (0, 0, 0))
        n = 15
        self.voussoirs = []
        for k in range(n):
            a = -a_max + (k + 0.5) * 2 * a_max / n
            rm = Rr + ring / 2
            loc = V((rm * math.sin(a), 0, cz + rm * math.cos(a)))
            st = toy.box(f"voussoir{k}", (2 * a_max / n * rm * 0.97, 4.6, ring), loc,
                         mat=self.m_stone2 if k % 2 else self.m_stone, bevel=0.05,
                         rotation=(0, a, 0))
            st.parent = self.arch_root
            self.voussoirs.append(st)
        self.arch_geom = (Rr, cz, a_max, ring)
        toy.hide_tree(self.arch_root, 0, True)
        # spandrel walls, road and parapets, cut into 12 vertical blocks, each on its own world-level root
        # (origin at its centre)
        re = Rr + ring
        xr = re * math.sin(a_max)                             # where the extrados meets the springing
        edges = [-half - 3.5, -half - 2.0] + [-xr + k * xr / 4 for k in range(9)] + [half + 2.0, half + 3.5]
        self.arch_blocks, self.spandrel_parts, self.arch_deck = [], [], []
        for k, (x0, x1) in enumerate(zip(edges, edges[1:])):
            cx, w = (x0 + x1) / 2, x1 - x0
            if abs(cx) < xr:                                  # sits on the arch ring: curved underside
                bottom = [(x, cz + math.sqrt(re * re - x * x)) for x in (x1 + (x0 - x1) * j / 4 for j in range(5))]
            else:                                             # abutment: down into the river bed
                bottom = [(x1, WATER_Z - 0.5), (x0, WATER_Z - 0.5)]
            zc = (0.25 + min(z for _, z in bottom)) / 2
            outline = [(x0, 0.25), (x1, 0.25)] + bottom
            root = toy.empty(f"arch_block{k}", (cx, 0, zc))
            wall = extrude_xz(f"arch_spandrel{k}", [(x - cx, z - zc) for x, z in outline], -2.2, 2.2, self.m_stone)
            wall.location = (cx, 0, zc)
            attach(wall, root)
            self.spandrel_parts.append(wall)
            deck = [toy.box(f"arch_road{k}", (w, 4.0, 0.12), (cx, 0, 0.3), mat=self.m_dirt, bevel=0)]
            for y in (-2.1, 2.1):
                deck.append(toy.box(f"arch_parapet{k}_{y}", (w - 0.03, 0.45, 0.9), (cx, y, 0.7), mat=self.m_stone2,
                                    bevel=0.04))
            for o in deck:
                attach(o, root)
                self.arch_deck.append((abs(cx), o))
            self.arch_blocks.append((root, x0, x1))
            toy.hide_tree(root, 0, True)
            _hide(root, 0, False)                             # the root itself stays evaluated (it carries the fall)

    def _truss_bridge(self):
        """A Pratt-truss railway bridge over the 40 m river: two red trusses, bracing, deck and rails."""
        L, n, H, yt = 46.0, 11, 5.5, 3.6
        self.truss_len, self.rail_len = L, L + 30
        self.truss_root = toy.empty("truss_root", (0, 0, 0))
        self.truss_members = []
        xs = [-L / 2 + k * L / n for k in range(n + 1)]

        def add(o):
            o.parent = self.truss_root
            self.truss_members.append(o)
            return o

        for y in (-yt, yt):
            for k in range(n):
                add(beam(f"truss_bot{y}_{k}", (xs[k], y, 0.2), (xs[k + 1], y, 0.2), 0.45, self.m_steel))
            for k in range(1, n - 1):
                add(beam(f"truss_top{y}_{k}", (xs[k], y, H), (xs[k + 1], y, H), 0.5, self.m_steel))
            add(beam(f"truss_end{y}_0", (xs[0], y, 0.2), (xs[1], y, H), 0.5, self.m_steel))
            add(beam(f"truss_end{y}_1", (xs[n], y, 0.2), (xs[n - 1], y, H), 0.5, self.m_steel))
            for k in range(1, n):
                add(beam(f"truss_vert{y}_{k}", (xs[k], y, 0.2), (xs[k], y, H), 0.32, self.m_steel_dark))
            mid = n // 2
            for k in range(1, n - 1):
                if k < mid:
                    a, b = (xs[k], y, H), (xs[k + 1], y, 0.2)
                else:
                    a, b = (xs[k + 1], y, H), (xs[k], y, 0.2)
                add(beam(f"truss_diag{y}_{k}", a, b, 0.3, self.m_steel))
        for k in range(1, n):
            add(beam(f"truss_xtop{k}", (xs[k], -yt, H), (xs[k], yt, H), 0.3, self.m_steel_dark))
        for k in range(1, n - 1):
            add(beam(f"truss_xa{k}", (xs[k], -yt, H), (xs[k + 1], yt, H), 0.18, self.m_steel_dark))
            add(beam(f"truss_xb{k}", (xs[k], yt, H), (xs[k + 1], -yt, H), 0.18, self.m_steel_dark))
        self.truss_deck = toy.box("truss_deck", (L, 2 * yt + 0.6, 0.35), (0, 0, 0.05), mat=self.m_plank, bevel=0)
        self.truss_deck.parent = self.truss_root
        self.truss_rails = []
        for y in (-0.75, 0.75):
            r = toy.box(f"truss_rail{y}", (self.rail_len, 0.12, 0.16), (0, y, 0.3), mat=self.m_rail, bevel=0)
            r.parent = self.truss_root
            self.truss_rails.append(r)
        self.truss_members.sort(key=lambda o: (round(o.location.x / 4.0), o.location.z))
        toy.hide_tree(self.truss_root, 0, True)
        # a little train: an engine and three wagons
        self.train = toy.empty("train", (-80, 0, 0.12))
        for k in range(4):
            car = toy.box(f"train_car{k}", (5.2, 2.4, 2.3 if k == 0 else 1.9), (0, 0, 0),
                          mat=mat(f"ev_train{k}", ("#2F3B4C", "#7A3B2A", "#5B6B3A", "#7A3B2A")[k], 0.5), bevel=0.08)
            car.parent = self.train
            car.location = (-k * 5.8, 0, 1.45 if k == 0 else 1.25)
        stack = toy.cylinder("train_stack", 0.35, 1.0, (0, 0, 0), mat=mat("ev_black", "#222222", 0.4), vertices=12)
        stack.parent = self.train
        stack.location = (1.6, 0, 3.0)
        toy.hide_tree(self.train, 0, True)
        # rails on both banks at the railway crossing: outer stubs stay, inner ones give way to the truss's
        self.rail_stubs, self.rail_inner = [], []
        for sgn in (-1, 1):
            for y in (-0.75, 0.75):
                for lst, x0, x1 in ((self.rail_stubs, 38.0, 140.0), (self.rail_inner, GAP["truss"] / 2 + 0.3, 38.0)):
                    r = toy.box(f"rail_stub{sgn}{y}_{x0:.0f}", (x1 - x0, 0.12, 0.16), (sgn * (x0 + x1) / 2, y, 0.3),
                                mat=self.m_rail, bevel=0)
                    toy.hide_tree(r, 0, True)
                    lst.append(r)

    def _suspension_bridge(self):
        self.towers = []
        self.tower_parts = []
        for sgn in (-1, 1):
            x = sgn * TOWER_X
            foot = base_box(f"tower_foot{sgn}", 9, 17, 3.2, (x, 0, WATER_Z - 1.5), self.m_concrete)
            self.tower_parts.append(foot)
            legs = []
            for y in (-CABLE_Y, CABLE_Y):
                leg = base_box(f"tower_leg{sgn}{y}", 2.4, 2.4, TOWER_TOP + 1.2 - (WATER_Z + 1.7),
                               (x, y, WATER_Z + 1.7), self.m_steel)
                legs.append(leg)
            beams = [toy.box(f"tower_beam{sgn}_{z}", (2.0, 2 * CABLE_Y, 1.4), (x, 0, z), mat=self.m_steel, bevel=0.05)
                     for z in (-1.4, 12.0, TOWER_TOP + 0.4)]
            self.towers.append((x, foot, legs, beams))
        self.anchors = []
        for side, sgn in (("L", -1), ("R", 1)):
            an = base_box(f"anchor_{side}", 9, 16, 3.5, (sgn * 75.0, 0, -0.8), self.m_concrete)
            self.anchors.append(an)
        # main cables: anchorage → tower → sagging main span → tower → anchorage
        self.cables = []
        xs = [-75 + k * 1.5 for k in range(101)]
        for y in (-CABLE_Y, CABLE_Y):
            pts = [(x, y, cable_z(x) + 0.0) for x in xs]
            c = stroke(f"main_cable{y}", pts, width=0.42, material=self.m_steel)
            c.visible_shadow = True
            self.cables.append(c)
        # vertical hangers every 5 m
        self.hangers, self.hanger_info = [], []
        hm = mat("ev_hanger", "#8E3A26", 0.5)
        for k in range(-14, 15):
            x = k * 5.0 + 2.5
            if abs(abs(x) - TOWER_X) < 2.0 or abs(x) > 70:
                continue
            for y in (-CABLE_Y, CABLE_Y):
                top = cable_z(x)
                h = toy.cylinder(f"hanger{k}{y}", 0.07, top - 0.6, (x, y, (top + 0.6) / 2), mat=hm, vertices=6)
                self.hangers.append(h)
                self.hanger_info.append((h, x, y, top))              # rest pose (a_heat lifts some)
        # deck: segments that can buckle (heat) and twist (wind)
        self.segments = []
        for k in range(int((DECK_X1 - DECK_X0) / SEG)):
            xc = DECK_X0 + SEG / 2 + k * SEG
            root = toy.empty(f"seg{k}", (xc, 0, 0))
            slab = toy.box(f"seg{k}_slab", (SEG - 0.04, 2 * DECK_HALF_W - 0.6, 0.45), (xc, 0, 0.32),
                           mat=self.m_asphalt, bevel=0)
            parts = [slab]
            for y in (-DECK_HALF_W + 0.1, DECK_HALF_W - 0.1):
                parts.append(toy.box(f"seg{k}_girder{y}", (SEG - 0.02, 0.5, 1.5), (xc, y, -0.05), mat=self.m_steel,
                                     bevel=0))
                parts.append(toy.box(f"seg{k}_edge{y}", (SEG - 0.02, 0.14, 0.02), (xc, y * 0.84, 0.56),
                                     mat=self.m_line, bevel=0))
            parts.append(toy.box(f"seg{k}_dash", (2.2, 0.16, 0.02), (xc, 0, 0.56), mat=self.m_line, bevel=0))
            for p in parts:
                attach(p, root)
            self.segments.append(root)
        # expansion joint (finger plates) at x = JOINT_X, shown from that beat on
        self.joint_parts = []
        steel = tx.metal("ev_joint", "#A7AAAE", 0.35, along="x")
        for k in range(16):
            y = -DECK_HALF_W + 0.9 + k * 0.62
            off = 0.32 if k % 2 else -0.32
            tooth = toy.box(f"joint_tooth{k}", (0.9, 0.26, 0.05), (JOINT_X + off, y, 0.57), mat=steel, bevel=0)
            self.joint_parts.append((tooth, off < 0))
        for p in [self.cables[0], self.cables[1]] + self.hangers + self.segments + self.anchors + self.tower_parts:
            toy.hide_tree(p, 0, True)
        for x, foot, legs, beams in self.towers:
            for o in legs + beams:
                toy.hide_tree(o, 0, True)
        for t, _ in self.joint_parts:
            toy.hide_tree(t, 0, True)
        # stiffening truss under the deck (built in the 'stiffening' beat)
        self.stiff = []
        top_z, bot_z = -0.7, -3.4
        xs = [DECK_X0 + k * SEG for k in range(int((DECK_X1 - DECK_X0) / SEG) + 1)]
        for y in (-DECK_HALF_W - 0.1, DECK_HALF_W + 0.1):
            for k in range(len(xs) - 1):
                a, b = xs[k], xs[k + 1]
                m_ = (a + b) / 2
                self.stiff.append(beam(f"stiff_d1{y}_{k}", (a, y, top_z), (m_, y, bot_z), 0.32, self.m_white_steel))
                self.stiff.append(beam(f"stiff_d2{y}_{k}", (m_, y, bot_z), (b, y, top_z), 0.32, self.m_white_steel))
                if k:
                    self.stiff.append(beam(f"stiff_bot{y}_{k}", (xs[k - 1] + SEG / 2, y, bot_z), (m_, y, bot_z), 0.4,
                                           self.m_steel))
        for k in range(len(xs) - 1):
            m_ = (xs[k] + xs[k + 1]) / 2
            self.stiff.append(beam(f"stiff_x{k}", (m_, -DECK_HALF_W - 0.1, bot_z), (m_, DECK_HALF_W + 0.1, bot_z), 0.25,
                                   self.m_steel_dark))
        for o in self.stiff:
            toy.hide_tree(o, 0, True)


    def seg_pose(self, f, z=None, pitch=None, roll=None, dx=None, segs=None):
        for s in (segs or self.segments):
            loc = V(toy.value_at(s, "location", f))
            rot = V(toy.value_at(s, "rotation_euler", f))
            if z is not None:
                loc.z = z(s) if callable(z) else z
            if dx is not None:
                loc.x = s["x0"] + (dx(s) if callable(dx) else dx)
            if pitch is not None:
                rot.y = pitch(s) if callable(pitch) else pitch
            if roll is not None:
                rot.x = roll(s) if callable(roll) else roll
            _key(s, f, location=loc, rotation_euler=rot)

    def _tint_key(self, f, heat):
        """Key how far the sky has turned amber (0 = its own blue, 1 = hot): the sky colour is mixed
        toward HOT_SKY at the sky's own brightness (nodes inserted between the sky texture and the
        background on first use). Multiplying a blue sky by an amber tint only turns it grey. The sun
        lamp alone barely warms a frame that is a third sky and a mirroring river."""
        if getattr(self, "_sky_tint", None) is None:
            nt = self.scene.world.node_tree
            sky = next(n for n in nt.nodes if n.type == "TEX_SKY")
            bg = next(n for n in nt.nodes if n.type == "BACKGROUND")
            lum = nt.nodes.new("ShaderNodeVectorMath")                  # the sky's brightness
            lum.operation = "DOT_PRODUCT"
            lum.inputs[1].default_value = (0.2126, 0.7152, 0.0722)
            nt.links.new(sky.outputs["Color"], lum.inputs[0])
            amber = nt.nodes.new("ShaderNodeVectorMath")                # HOT_SKY * t at that brightness
            amber.operation = "SCALE"
            nt.links.new(lum.outputs["Value"], amber.inputs["Scale"])
            mix = nt.nodes.new("ShaderNodeVectorMath")                  # sky * (1 - t) + amber
            mix.operation = "MULTIPLY_ADD"
            nt.links.new(sky.outputs["Color"], mix.inputs[0])
            nt.links.new(amber.outputs["Vector"], mix.inputs[2])
            nt.links.new(mix.outputs["Vector"], bg.inputs["Color"])
            self._sky_tint = (mix.inputs[1], amber.inputs[0])
        t = heat * HOT_SKY_MIX
        keep, warm = self._sky_tint
        keep.default_value = (1.0 - t,) * 3
        warm.default_value = tuple(c * t for c in HOT_SKY)
        keep.keyframe_insert("default_value", frame=int(f))
        warm.keyframe_insert("default_value", frame=int(f))

    def _grade_key(self, f, warm):
        """Key the view's white balance (0 = neutral, 1 = hot): the whole image warms, river and shade
        included, not only the sunlit faces. A raised white point shifts the picture toward amber."""
        vs = self.scene.view_settings
        if not hasattr(vs, "white_balance_temperature"):
            return
        try:
            if getattr(self, "_wb0", None) is None:
                self._wb0 = vs.white_balance_temperature
                if hasattr(vs, "use_white_balance"):
                    vs.use_white_balance = True
            vs.white_balance_temperature = self._wb0 + HOT_WB * warm
            vs.keyframe_insert("white_balance_temperature", frame=int(f))
        except (TypeError, AttributeError, RuntimeError):
            pass

    def _dust_puffs(self, name, count, size, seed):
        """Puffs of see-through dust (no shadow): opaque puffs read as solid balls lying on the road."""
        puffs = Puffs(name, DUST, count=count, size=size, seed=seed)
        m = puffs.parts[0].active_material
        bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        toy._set(bsdf, "Alpha", 0.55)
        if hasattr(m, "surface_render_method"):
            m.surface_render_method = "DITHERED"
        for p in puffs.parts:
            p.visible_shadow = False
        return puffs

    def _sun_icon(self, f, gone, at, cam):
        """A blazing sun hung in the sky: an amber disc ringed by white pen rays that draw themselves on."""
        root = toy.empty("heat_sun", at)
        face_camera(root, cam)
        disc = toy.cylinder("heat_sun_disc", 6.0, 0.3, (0, 0, 0), mat=emissive("ev_sun", "#FFB730", 6.0), vertices=40)
        disc.parent = root
        disc.location = (0, 0, 0)
        disc.visible_shadow = False                                  # it hangs in the sky: no shadow on the river
        rays = []
        for k in range(10):
            a = 2 * math.pi * k / 10
            c, s = math.cos(a), math.sin(a)
            rays.append(stroke(f"heat_sun_ray{k}", [(8.0 * c, 8.0 * s, 0), (12.5 * c, 12.5 * s, 0)], width=0.5,
                               parent=root))
        pop_in(root, f, frames=10, gone=gone)
        for k, r in enumerate(rays):
            draw_on(r, f + 6 + k, f + 14 + k)
        events.add(f, "whoosh", gain=0.5)

    # ------------------- the actions -------------------

    def a_plank(self, i, b, e):
        L_ = e - b
        for log, sgn in self.plank_logs:
            fly_in(log, b + 2, b + int(L_ * 0.18), (sgn * 3.0, 0, 0.6))
        n = len(self.planks)
        for k, pl in enumerate(self.planks):
            f = b + int(L_ * 0.16) + int(L_ * 0.42 * k / n)
            fly_in(pl, f, f + 7, (0, 0, 2.6), spin=R(25))
            if k % 3 == 0:
                events.add(f + 7, "hammer", gain=0.5)
        for k, r in enumerate(self.plank_rails):
            pop_in(r, b + int(L_ * 0.58) + k % 6, frames=6)
        # the cart rolls over (left to right)
        c0, c1 = b + int(L_ * 0.66), e + 4
        _key(self.cart, c0, location=V((-9.0, 0, 0.45)))
        _key(self.cart, c1, location=V((9.0, 0, 0.45)))
        toy.set_interpolation(self.cart, "location", (c0,), "LINEAR")
        show_between(self.cart, c0, c1)
        self.cart_exit = (c1, 18.0 / max(1, c1 - c0))                # a_heavy_load rolls it on, off frame
        events.add(c0, "roll", duration=c1 - c0, gain=0.5)
        self.shot(b, e, cam_from=(-2.5, -25, 11), aim_from=(0, 2, -0.5), cam_to=(-1.5, -16, 7.0),
                  aim_to=(0, 1, 0.2), lens=22, cut=True)

    def _burst(self, name, f, at, radius=2.0, height=2.5, n=14, seed=1, gain=0.8, drop=1.0, ring=12):
        """A splash that erupts FROM the water at frame f: droplets thrown up and out on ballistic arcs
        that fall back in within ~half a second, and a ring of foam spreading flat on the surface.
        `drop` scales the droplets and foam dashes (bigger for far cameras), `ring` = foam dashes."""
        rnd = random.Random(seed)
        spray = mat("ev_spray", "#F4FAFB", 0.3)
        at = V((at[0], at[1], WATER_Z))
        life = 16
        for k in range(n):
            a = 2 * math.pi * (k + rnd.uniform(-0.3, 0.3)) / n
            r = radius * rnd.uniform(0.35, 1.0)
            h = height * rnd.uniform(0.5, 1.15) * (1.4 if k % 4 == 0 else 1.0)
            d = toy.sphere(f"{name}_drop{k}", rnd.uniform(0.11, 0.2) * drop, at, mat=spray, subdiv=1, segments=10,
                           rings=6)
            f0 = f + rnd.randint(0, 3)
            for j in range(0, life + 1, 2):
                t = j / life
                _key(d, f0 + j, location=at + V((r * t * math.cos(a), r * t * math.sin(a), 4 * h * t * (1 - t))),
                     scale=V((1, 1, 1.0 + 0.8 * (1 - t))) * (1.0 - 0.6 * t))
            show_between(d, f0, f0 + life)
        self._foam_ring(f"{name}_ring", f + 2, at, 0.5 * radius, 1.6 * radius, n=ring, life=22, seed=seed, size=drop)
        events.add(f, "splash", gain=gain)

    def _foam_ring(self, name, f, at, r0, r1, n=12, life=22, seed=1, size=1.0):
        """A ring of foam dashes that spreads flat on the water and fades (a ripple)."""
        rnd = random.Random(seed + 101)
        foam = mat("ev_foam", "#E6F0F2", 0.8)
        at = V((at[0], at[1], WATER_Z + 0.03))
        for k in range(n):
            a = 2 * math.pi * k / n + rnd.uniform(-0.15, 0.15)
            o = toy.sphere(f"{name}{k}", 0.3, at, mat=foam, subdiv=1, segments=10, rings=6)
            o.rotation_euler = (0, 0, a + math.pi / 2)                  # local x along the ring
            out = V((math.cos(a), math.sin(a), 0))
            _key(o, f, location=at + out * r0, scale=V((0.6, 0.5, 0.12)) * size)
            _key(o, f + life // 2, location=at + out * (r0 + (r1 - r0) * 0.7), scale=V((1.6, 0.8, 0.15)) * size)
            _key(o, f + life, location=at + out * r1, scale=V((0.05, 0.05, 0.02)) * size)
            show_between(o, f, f + life + 1)

    def a_heavy_load(self, i, b, e):
        """The planks carried people and a hand cart; now a wagon loaded with cut stone rolls on. As it
        nears mid-span the deck bows into a smile (orange arrows: the top squeezes, the bottom stretches)
        and snaps in the middle under the wagon: both halves swing down from the banks into a V, tips in
        the water (splash), and the wagon drops into the stream between them. The stream stays 6 m wide:
        the load, not the river, broke it."""
        L_ = e - b
        HALF, D_MAX = 4.4, 1.5                             # deck half-length, sag at the snap
        sag0 = b + int(L_ * 0.16)                          # the wagon's front wheels reach the deck
        crack = b + int(L_ * 0.50)                         # ...and the wagon is at mid-span
        touch = max(crack + 6, b + int(L_ * 0.64))

        def sag_d(f):
            t = max(0.0, min(1.0, (f - sag0) / max(1, crack - sag0)))
            return D_MAX * t * t

        def sag_pose(u, f):
            d = sag_d(f)
            return u, -d * (1 - (u / HALF) ** 2), -math.atan(2 * d * u / HALF ** 2)

        half_len = math.hypot(HALF, D_MAX)
        phi_c = math.atan2(D_MAX, HALF)
        phi_t = max(phi_c + R(10), math.asin(min(0.95, -(WATER_Z - 0.15) / half_len)))

        def hinge_pose(u, f):
            """Each snapped half turns rigidly about its outer end (on the bank), tip first into the water."""
            sgn = 1 if u > 0 else -1
            x0, z0, p0 = sag_pose(u, crack)
            rx, rz = x0 - sgn * HALF, z0
            t = max(0.0, min(1.0, (f - crack) / (touch - crack)))
            th = -sgn * (phi_t - phi_c) * t * t
            return (sgn * HALF + rx * math.cos(th) + rz * math.sin(th),
                    -rx * math.sin(th) + rz * math.cos(th), p0 + th)

        def pose(k, f):
            u = self.plank_slices[k][1]
            if f <= crack:
                x, z, p = sag_pose(u, f)
                return x, z, p
            if f <= touch:
                return hinge_pose(u, f)
            x, z, p = hinge_pose(u, touch)                 # hanging from the bank, rocking in the current
            sway = R(1.2) * math.sin((f - touch) * 0.25 + (1.3 if u > 0 else 0.0)) * min(1.0, (f - touch) / 10)
            return x, z, p + sway

        frames = sorted(set(range(b, e + 1, 2)) | set(range(crack, touch + 1)) | {e})
        for k, (root, _) in enumerate(self.plank_slices):
            for f in frames:
                x, z, p = pose(k, f)
                _key(root, f, location=V((x, 0, z)), rotation_euler=V((0, p, 0)))
            _hide(root, 0, False)                          # the root itself must stay evaluated until then
            toy.hide_tree(root, e + 1, True)               # cleared away before the arch is built
        # the heavy wagon: rolls in along the left bank, onto the deck, slows to a stop at mid-span as
        # the deck gives way, then drops into the stream and settles half sunk
        wagon = self.wagons[0]
        w_in = b + 2
        x_start = -15.0

        def wagon_x(f):
            if f <= sag0:
                return x_start + (-HALF - x_start) * (f - w_in) / max(1, sag0 - w_in)
            u = min(1.0, (f - sag0) / max(1, crack - sag0))
            return -HALF * (1 - u) ** 1.6

        def deck_z(x, f):
            return 0.0 if abs(x) >= HALF else -sag_d(f) * (1 - (x / HALF) ** 2)

        G = 9.81 / 30.0 ** 2
        z_crack = PLANK_TOP + deck_z(0.0, crack)
        t_hit = math.sqrt(2 * max(0.5, z_crack - (WATER_Z + 0.2)) / G)
        f_hit = crack + int(round(t_hit))
        toy.hide_tree(wagon, w_in, False)
        for f in sorted(set(range(w_in, e + 1, 2)) | {crack, f_hit, e}):
            if f <= crack:
                x = wagon_x(f)
                slope = 2 * sag_d(f) * x / HALF ** 2 if abs(x) < HALF else 0.0
                _key(wagon, f, location=V((x, 0, PLANK_TOP + deck_z(x, f))), rotation_euler=V((0, -math.atan(slope), 0)))
            elif f <= f_hit:
                t = f - crack
                _key(wagon, f, location=V((0.0, -0.3 * t / t_hit, z_crack - 0.5 * G * t * t)),
                     rotation_euler=V((R(6) * t / t_hit, R(-14) * t / t_hit, 0)))
            else:
                w = (f - f_hit) / max(1, e - f_hit)
                _key(wagon, f, location=V((0.3 * w, -0.3 - 1.0 * w, WATER_Z + 0.2 - 1.1 * ease(w))),
                     rotation_euler=V((R(6), R(-14), R(8) * w)))
        toy.hide_tree(wagon, e + 1, True)
        events.add(w_in, "roll", duration=crack - w_in, gain=0.7)
        self._burst("splash_wagon", f_hit, (0.0, -0.3), radius=2.2, height=3.4, n=16, seed=5, gain=0.9)
        # the format's drawing: on the bowed deck the top is squeezed (arrows inwards) and the bottom
        # stretched (arrows outwards), drawn while the wagon presses it down, gone just before the snap
        a0, a1 = sag0 + int((crack - sag0) * 0.3), crack - 3
        d_mid = sag_d((a0 + a1) // 2)
        z_top, z_bot = 1.35 - 0.6 * d_mid, -0.6 - 0.6 * d_mid
        y = -1.9
        for sgn in (-1, 1):
            for tag, z, inward in (("top", z_top, True), ("bot", z_bot, False)):
                x_far, x_near = sgn * 2.9, sgn * 0.8
                tail, tip = ((x_far, y, z), (x_near, y, z)) if inward else ((x_near, y, z), (x_far, y, z))
                hx = 0.45 if tip[0] > tail[0] else -0.45
                line = stroke(f"bend_{tag}{sgn}", [tail, tip], width=0.1, material=self.m_ink_orange)
                head = stroke(f"bend_{tag}{sgn}_head", [(tip[0] - hx, y, z + 0.35), tip, (tip[0] - hx, y, z - 0.35)],
                              width=0.1, material=self.m_ink_orange)
                for ob in (line, head):
                    show_between(ob, a0, a1 + 1)
                    draw_on(ob, a0, a0 + 8)
        events.add(sag0 + (crack - sag0) // 3, "creak", gain=0.7)
        events.add(crack - 8, "creak", gain=1.0)
        events.add(crack, "crack", gain=1.0)
        for sgn, tag in ((-1, "l"), (1, "r")):
            tip_x = hinge_pose(sgn * 0.18, touch)[0]
            self._burst(f"splash_tip_{tag}", touch, (tip_x, 0), radius=1.6, height=2.6, n=12,
                        seed=3 + sgn, gain=0.6)
            for j, f in enumerate(range(touch + 18, e - 10, 22)):
                self._foam_ring(f"ripple_{tag}{j}", f, (tip_x, 0.0), 0.8, 3.2, n=10, life=24, seed=20 + j + sgn)
        # the light hand cart that crossed in the plank beat rolls on along the right bank, out of frame
        c1, speed = self.cart_exit
        c2 = c1 + int(20.0 / speed)
        toy.hide_tree(self.cart, c1, False)
        _key(self.cart, c2, location=V((29.0, 0, 0.45)))
        toy.set_interpolation(self.cart, "location", (c1,), "LINEAR")
        toy.hide_tree(self.cart, c2, True)
        # close, nearly fixed drone view up the stream: the deck fills ~60% of the width and the wagon
        # rolls in from the left
        self.shot(b, e, cam_from=(-1.6, -15.5, 7.6), aim_from=(-1.0, 4.0, -1.0), cam_to=(-0.6, -14.0, 7.0),
                  aim_to=(0, 3.0, -1.8), lens=22)

    def a_arch(self, i, b, e):
        L_ = e - b
        Rr, cz, a_max, ring = self.arch_geom
        n = len(self.voussoirs)
        pairs = [(k, n - 1 - k) for k in range(n // 2)]         # from both springings inwards, keystone last
        # the first pair is already in the air, INSIDE the frame, on the beat's first frame (the plank wreck
        # is gone by then: the screen must never be an empty stream); stones drop in from just above their
        # place, slow enough (12 frames) to read without motion blur on a phone. The keystone lands at
        # ~0.33 L so the drop, the thud and the load arrows all happen in the beat's first half
        t0, t1 = b, b + int(L_ * 0.24)
        for j, pair in enumerate(pairs):
            f = t0 + int((t1 - t0) * j / max(1, len(pairs) - 1))
            for k in pair:
                st = self.voussoirs[k]
                side = -1 if st.location.x < 0 else 1
                fly_in(st, f, f + 12, (side * 0.9, -1.0, 5.0), spin=R(30))
            events.add(f + 12, "stone_thud", gain=0.4)
        key = self.voussoirs[n // 2]                            # held high over the gap, then dropped in
        key0, key_f = t1 + 4, t1 + 4 + 14
        fly_in(key, key0, key_f, (0, -0.6, 6.0), spin=R(25))       # starts inside the top of the frame
        events.add(key_f, "stone_thud", gain=1.0)
        self.dust("dust_keystone", key_f, (0, -1.0, -0.6), size=0.6)
        fill0 = key_f + 4
        for wall in self.spandrel_parts:
            wall.scale = (1, 1, 1)
            _hide(wall, 0, True)
            _hide(wall, fill0, False)
            _key(wall, fill0, scale=V((1, 0.02, 1)))
            _key(wall, fill0 + int(L_ * 0.12), scale=V((1, 1, 1)))
        for ax, o in self.arch_deck:                             # the road fills in from the crown outwards
            pop_in(o, fill0 + int(L_ * 0.12) + int(ax / 2.5), frames=8)
        # load path: weight pushes down at the crown, flows along the curve into both banks (drawn as soon
        # as the keystone locks the ring)
        f_ar = key_f + 10
        rm = Rr + ring / 2
        # the weight on the crown is a short, thick arrow with a big head (a bare vertical rod reads as a
        # road marking from the drone's angle); each load path along the ring ends in a head at the bank
        down = stroke("arch_load_down", [(0, -2.5, 4.6), (0, -2.5, 1.3)], width=0.2, material=self.m_ink_orange)
        down_head = stroke("arch_load_down_head", [(-0.9, -2.5, 2.4), (0, -2.5, 1.3), (0.9, -2.5, 2.4)], width=0.2,
                           material=self.m_ink_orange)
        for sgn in (-1, 1):
            pts = [(rm * math.sin(sgn * a_max * k / 16), -2.5, cz + rm * math.cos(sgn * a_max * k / 16) + 0.9)
                   for k in range(17)]
            end = V(pts[-1])
            tip = end + V((sgn * 3.0, 0, -1.4))
            pts.append(tuple(tip))
            arr = stroke(f"arch_load{sgn}", pts, width=0.14, material=self.m_ink_orange)
            draw_on(arr, f_ar, f_ar + 14, erase=e - 10, erase_frames=8)
            d = (tip - end).normalized()
            n_ = V((-d.z, 0, d.x))
            head = stroke(f"arch_load{sgn}_head", [tuple(tip - d * 0.8 + n_ * 0.6), tuple(tip),
                                                   tuple(tip - d * 0.8 - n_ * 0.6)], width=0.14,
                          material=self.m_ink_orange)
            draw_on(head, f_ar + 14, f_ar + 18, erase=e - 10, erase_frames=8)
        draw_on(down, f_ar - 8, f_ar, erase=e - 10, erase_frames=8)
        draw_on(down_head, f_ar - 1, f_ar + 4, erase=e - 10, erase_frames=8)
        # the proof: the same load that broke the planks now rolls straight across
        wagon = self.wagons[1]
        w0, w1 = max(fill0 + int(L_ * 0.12) + 10, b + int(L_ * 0.55)), e + 24
        show_between(wagon, w0, e + 1)
        top = 0.36                                               # arch road surface
        edge = GAP["arch"] / 2 + 3.5
        for f in range(w0, w1 + 1, 2):
            x = -14.0 + 28.0 * (f - w0) / (w1 - w0)
            z = 0.07 + (top - 0.07) * max(0.0, min(1.0, (edge + 1.0 - abs(x)) / 1.0))
            _key(wagon, f, location=V((x, 0, z)))
        events.add(w0, "roll", duration=e - w0, gain=0.6)
        # a punch-in cut on the beat's first frame (a glide from the wreck's wider framing would spend the
        # first second on an empty stream): ~25% closer than the end of a_heavy_load, still over the water
        # and looking down into the stream at ~32 degrees; the 6 m ring fills ~60% of the width and every
        # stone is in frame for its whole flight
        self.shot(b, w0 - 1, cam_from=(-0.45, -10.6, 6.0), aim_from=(0, 2.0, -1.9), cam_to=(-0.25, -9.8, 6.2),
                  aim_to=(0, 1.5, -1.6), lens=22, cut=True)
        self.shot(w0, e, cam_from=(1.2, -14.6, 7.6), aim_from=(0, 1.5, -1.0), cam_to=(0.6, -14.0, 7.3),
                  aim_to=(0, 1.2, -0.9), lens=22)                # still high: the wagon reads over the parapet

    def a_railway(self, i, b, e):
        """Hard cut downstream, to where the railway must cross: the river here is 40 m wide and tall
        ships sail up it. The stone arch stays behind at the village stream (out of frame). A train rolls
        along the left bank and stops where its rails end at the water. A white sketch draws the stone
        arches a 40 m crossing would need: piers standing in the river, crowns lower than the masts.
        The ship sails up towards them; the sketch erases. (Why a stone arch can't serve here.)"""
        L_ = e - b
        self.cut_to_gap(b, GAP["truss"])
        toy.hide_tree(self.arch_root, b, True)
        for root, _, _ in self.arch_blocks:
            toy.hide_tree(root, b, True)
        for r in self.rail_stubs + self.rail_inner:
            show_between(r, b)
        # the train is already rolling in on the first frame (engine entering at the left edge of the
        # opening shot) and brakes to a stop with its nose at the bank edge
        t0, t1 = b, b + int(L_ * 0.28)
        x_start, x_stop = -32.0, -GAP["truss"] / 2 - 2.6 - 1.2
        show_between(self.train, t0)
        for f in sorted(set(range(t0, t1 + 1, 2)) | {t1}):
            u = (f - t0) / max(1, t1 - t0)
            _key(self.train, f, location=V((x_start + (x_stop - x_start) * (1 - (1 - u) ** 2), 0, 0.12)))
        events.add(t0, "train_pass", duration=t1 - t0, gain=0.6)
        events.add(t1 - 6, "creak", gain=0.5)
        # the ship is already close on the first frame (~14% of the frame height in the opening shot) and
        # keeps sailing down its lane, straight at where the left pier would stand
        show_between(self.ship, b)
        _key(self.ship, b, location=V((SHIP_X, 48, WATER_Z)))
        _key(self.ship, e, location=V((SHIP_X, SHIP_Y, WATER_Z)))
        toy.set_interpolation(self.ship, "location", (b,), "LINEAR")
        # the sketch: three stone arches across the 40 m, piers (orange) standing in the shipping lane;
        # drawn in the beat's second half ("Arches here put piers in their path"), once the wide shot settles
        half = GAP["truss"] / 2
        span = 2 * half / 3
        y, crown, spring = -4.0, 6.5, 1.5
        d0 = b + int(L_ * 0.40)
        sketch = []
        for k in range(3):
            x0 = -half + k * span
            pts = [(x0 + span / 2 - span / 2 * math.cos(math.pi * j / 16), y,
                    spring + (crown - spring) * math.sin(math.pi * j / 16)) for j in range(17)]
            sketch.append(stroke(f"viaduct_arch{k}", pts, width=0.22))
        sketch.append(stroke("viaduct_deck", [(-half, y, crown + 0.6), (half, y, crown + 0.6)], width=0.22))
        piers = [stroke(f"viaduct_pier{k}", [(x, y, spring), (x, y, WATER_Z)], width=0.3, material=self.m_ink_orange)
                 for k, x in enumerate((-half + span, -half + 2 * span))]
        for k, ob in enumerate(sketch):
            show_between(ob, d0, e)
            draw_on(ob, d0 + 3 * k, d0 + 3 * k + 16, erase=e - 14, erase_frames=10)
        for k, ob in enumerate(piers):
            show_between(ob, d0 + 18, e)
            draw_on(ob, d0 + 18 + 4 * k, d0 + 28 + 4 * k, erase=e - 14, erase_frames=10)
            self._foam_ring(f"pier_ring{k}", d0 + 26 + 4 * k, (ob.data.splines[0].points[0].co[0], y), 0.8, 2.8,
                            n=10, life=24, seed=300 + k)
        # 1) low drone over the water near the left bank (z = 11, above the trees, which stop at y = -18),
        # looking up the river ~11 degrees left: the train (engine + first wagon, ~25 m away) fills the
        # lower left, the ship (~55-68 m away, 14-17% of the frame height) the right third
        a_end = d0 - 25
        self.shot(b, a_end, cam_from=(-17, -24, 11), aim_from=(-27.5, 30.0, -1.7), cam_to=(-16, -26, 11.5),
                  aim_to=(-26.5, 28.0, -1.2), lens=24, cut=True)
        # 2) glide back (~0.8 s, settled as the sketch starts) to a lower drone view than before (z = 20)
        # that holds the whole 40 m sketch, the stopped engine on the left and the ship behind the left
        # arch, its masts above the sketched crowns
        self.rig.shot(a_end + 1, e, cam_from=(-10.5, -57, 19), cam_to=(-10, -60, 20), aim_from=(-1, 14, 0),
                      aim_to=(-1, 14, 0), lens=22, fstop=11.0, blend=24)

    def a_truss(self, i, b, e):
        L_ = e - b
        pop_in(self.truss_deck, b + 2, frames=10)
        for r in self.truss_rails:
            pop_in(r, b + 6, frames=8)
        for r in self.rail_inner:
            toy.hide_tree(r, b + 6, True)
        n = len(self.truss_members)
        t0, t1 = b + 8, b + int(L_ * 0.48)
        for k, o in enumerate(self.truss_members):
            f = t0 + int((t1 - t0) * k / n)
            pop_in(o, f, frames=6)
            if k % 9 == 0:
                events.add(f + 4, "steel_clank", gain=0.45)
        # triangle vs square, drawn in the sky in front of the bridge
        cam = V((-3, -44, 8.5))
        d0, d1 = b + int(L_ * 0.5), e - 6
        tri_root = toy.empty("draw_triangle", (-6.5, -9, 13.5))
        sq_root = toy.empty("draw_square", (6.5, -9, 13.5))
        face_camera(tri_root, cam)
        face_camera(sq_root, cam)
        s = 3.0
        tri = stroke("triangle", [(-s, -s, 0), (s, -s, 0), (0, s, 0)], width=0.16, closed=True, parent=tri_root)
        sq = stroke("square", [(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], width=0.16, closed=True, parent=sq_root)
        for ob in (tri, sq):
            show_between(ob, d0, e)
            draw_on(ob, d0, d0 + 14)
        push0 = d0 + 22
        for root in (tri_root, sq_root):
            arrow = stroke(f"{root.name}_push", [(-s - 4.2, s, 0), (-s - 0.6, s, 0)], width=0.14,
                           material=self.m_ink_orange, parent=root)
            head = stroke(f"{root.name}_head", [(-s - 1.6, s + 0.9, 0), (-s - 0.6, s, 0), (-s - 1.6, s - 0.9, 0)],
                          width=0.14, material=self.m_ink_orange, parent=root)
            for ob in (arrow, head):
                show_between(ob, push0, e)
                draw_on(ob, push0, push0 + 8)
        bend0, bend1 = push0 + 10, push0 + 30
        pts = sq.data.splines[0].points
        for f, phi in ((bend0, 0.0), (bend1, R(32))):
            off = V((2 * s * math.sin(phi), 2 * s * math.cos(phi), 0))
            pts[2].co = (*(V((s, -s, 0)) + off), 1.0)
            pts[3].co = (*(V((-s, -s, 0)) + off), 1.0)
            for p in (pts[2], pts[3]):
                p.keyframe_insert("co", frame=int(f))
        tpts = tri.data.splines[0].points
        for f, dx in ((bend0, 0.0), (bend0 + 6, 0.12), (bend0 + 12, 0.0)):
            tpts[2].co = (dx, s, 0, 1.0)
            tpts[2].keyframe_insert("co", frame=int(f))
        events.add(bend0, "boing", gain=0.3)
        # the train crosses
        tr0, tr1 = b + int(L_ * 0.55), e + 30
        _key(self.train, tr0, location=V((-GAP["truss"] / 2 - 3.8, 0, 0.12)))   # where a_railway stopped it
        _key(self.train, tr1, location=V((70, 0, 0.12)))
        toy.set_interpolation(self.train, "location", (tr0,), "LINEAR")
        show_between(self.train, tr0, e + 1)
        events.add(tr0, "train_pass", duration=e - tr0, gain=0.7)
        _key(self.ship, b, location=V((SHIP_X, SHIP_Y, WATER_Z)))      # continues from a_railway
        _key(self.ship, e, location=V((SHIP_X, SHIP_Y - 3, WATER_Z)))
        self.shot(b, d0 - 4, cam_from=(-12, -46, 18), aim_from=(0, 0, 2.5), cam_to=(-8, -36, 12), aim_to=(0, 0, 3.0),
                  lens=22)
        self.shot(d0 - 3, e, cam_from=cam, aim_from=(0, 0, 8.5), cam_to=cam + V((1.5, 2.0, 0)), aim_to=(0, 0, 8.5),
                  lens=24)

    def _spouts(self, name, f, x0, x1, y, height, n=8, seed=1, life=26, width=1.6):
        """The body of a big splash: tall white water spouts that shoot up from the surface along a line
        and collapse back into it (_burst adds the flying droplets, _slick the foam they leave)."""
        rnd = random.Random(seed)
        spray = mat("ev_spray", "#F4FAFB", 0.3)
        seg, prof = 10, ((1.0, 0.0), (0.72, 0.35), (0.4, 0.7))           # (radius, height) up the spout
        verts = [(r * math.cos(2 * math.pi * k / seg), r * math.sin(2 * math.pi * k / seg), z)
                 for r, z in prof for k in range(seg)] + [(0.0, 0.0, 1.0)]
        faces = [(j * seg + k, j * seg + (k + 1) % seg, (j + 1) * seg + (k + 1) % seg, (j + 1) * seg + k)
                 for j in range(len(prof) - 1) for k in range(seg)]
        top, ring = len(verts) - 1, (len(prof) - 1) * seg
        faces += [(ring + k, ring + (k + 1) % seg, top) for k in range(seg)]
        rise = max(4, int(life * 0.35))
        for k in range(n):
            x = x0 + (x1 - x0) * (k + rnd.uniform(0.2, 0.8)) / n
            h = height * rnd.uniform(0.6, 1.1)
            r = width * rnd.uniform(0.75, 1.25)
            o = mesh_obj(f"{name}{k}", verts, faces, spray, smooth=True)
            o.location = (x, y + rnd.uniform(-1.0, 1.0), WATER_Z - 0.3)
            o.rotation_euler = (rnd.uniform(-0.12, 0.12), rnd.uniform(-0.12, 0.12), 0)
            f0 = f + rnd.randint(0, 3)
            _key(o, f0, scale=V((0.5 * r, 0.5 * r, 0.05 * h)))
            _key(o, f0 + rise, scale=V((r, r, h)))
            _key(o, f0 + life, scale=V((1.9 * r, 1.9 * r, 0.03 * h)))
            show_between(o, f0, f0 + life + 1)

    def _slick(self, name, f0, f1, at, rx, ry, seed=1, alpha=0.92, lift=0.04):
        """One continuous, mottled patch of foam on the water (no dashes) that spreads out and fades
        away between f0 and f1. `lift` keeps overlapping slicks from z-fighting."""
        if f1 - f0 < 12:
            return
        rnd = random.Random(seed)
        n = 32
        verts = [(0.0, 0.0, 0.0)]
        for k in range(n):
            a = 2 * math.pi * k / n
            r = 0.88 + 0.12 * math.sin(3 * a + seed) + rnd.uniform(-0.07, 0.07)
            verts.append((rx * r * math.cos(a), ry * r * math.sin(a), 0.0))
        faces = [(0, 1 + k, 1 + (k + 1) % n) for k in range(n)]
        m = bpy.data.materials.new(f"ev_slick_{name}")
        m.use_nodes = True
        nt = m.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        coord = nt.nodes.new("ShaderNodeTexCoord")
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 0.45
        noise.inputs["Detail"].default_value = 8
        nt.links.new(coord.outputs["Object"], noise.inputs["Vector"])
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (*toy.srgb("#7FA9AC"), 1)
        ramp.color_ramp.elements[1].color = (*toy.srgb("#F4F9F9"), 1)
        ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = 0.4, 0.56
        nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
        toy._set(bsdf, "Roughness", 0.75)
        if hasattr(m, "surface_render_method"):
            m.surface_render_method = "DITHERED"
        ob = mesh_obj(name, verts, faces, m)
        ob.location = (at[0], at[1], WATER_Z + lift)
        ob.rotation_euler = (0, 0, rnd.uniform(-0.08, 0.08))
        ob.visible_shadow = False
        _key(ob, f0, scale=V((0.45, 0.45, 1)))
        _key(ob, f0 + (f1 - f0) // 3, scale=V((1, 1, 1)))
        _key(ob, f1, scale=V((1.3, 1.3, 1)))
        a_in = bsdf.inputs["Alpha"]
        for f, v in ((f0, 0.0), (f0 + 4, alpha), (f0 + (f1 - f0) // 2, alpha * 0.8), (f1, 0.0)):
            a_in.default_value = v
            a_in.keyframe_insert("default_value", frame=int(f))
        show_between(ob, f0, f1 + 1)

    def a_wide_bay(self, i, b, e):
        """Hard cut further downstream, to the mouth of the river: a whole bay (shown scaled down) that a
        growing city must cross; cars queue at the shore where the road ends. A white sketch draws a truss
        long enough to span it; it bows deeper and deeper into the water under its own weight (orange)
        and erases: a truss that long is too heavy to hold itself up. The camera pulls back to show it all."""
        L_ = e - b
        self.cut_to_gap(b, GAP["suspension"])
        toy.hide_tree(self.truss_root, b, True)
        toy.hide_tree(self.train, b, True)
        for r in self.rail_stubs + self.rail_inner:
            toy.hide_tree(r, b, True)
        toy.hide_tree(self.ship, b, True)                    # back in a_suspension
        # the village is upstream, by the first crossing: not at the bay (a_suspension shows it again)
        for o in bpy.data.objects:
            if o.name.startswith(("cottage", "fence_")):
                _hide(o, 0, False)
                _hide(o, b, True)
                _hide(o, e + 1, False)
        # the queue: cars stand on the left shore road, nose to tail, up to the water
        edge = -GAP["suspension"] / 2
        for k, car in enumerate(self.queue_cars):
            show_between(car, b, e)
            _key(car, b, location=V((edge - 6.0 - k * 5.4, -1.0, QUEUE_Z)))
            _key(car, e, location=V((edge - 6.0 - k * 5.4 + (0.6 if k else 0.0), -1.0, QUEUE_Z)))
        events.add(b + 6, "traffic", duration=L_ - 12, gain=0.35)
        # the sketch: a long truss across the bay that sags under its own weight
        half = GAP["suspension"] / 2 + 2.0
        y, H, n = -3.0, 7.0, 24
        xs = [-half + 2 * half * k / n for k in range(n + 1)]
        bot = stroke("bay_truss_bot", [(x, y, 0.5) for x in xs], width=0.45)
        top = stroke("bay_truss_top", [(x, y, 0.5 + H) for x in xs], width=0.45)
        zig = stroke("bay_truss_web", [(x, y, 0.5 + (H if k % 2 else 0.0)) for k, x in enumerate(xs)], width=0.35)
        d0, d1 = b + int(L_ * 0.18), b + int(L_ * 0.42)
        s0, s1 = b + int(L_ * 0.50), b + int(L_ * 0.80)
        for k, ob in enumerate((bot, top, zig)):
            show_between(ob, d0, e)
            draw_on(ob, d0 + 4 * k, d1 + 4 * k, erase=e - 12, erase_frames=10)
            pts = ob.data.splines[0].points
            for j, p in enumerate(pts):
                x, _, z, _ = p.co
                p.keyframe_insert("co", frame=int(s0))
                droop = 9.0 * (1 - (x / half) ** 2)
                p.co = (x, y, z - droop, 1.0)
                p.keyframe_insert("co", frame=int(s1))
        events.add(s0, "bridge_groan", gain=0.8)
        events.add(s0 + (s1 - s0) // 2, "creak", gain=0.9)
        self._foam_ring("bay_sag_ring", s1 - 6, (0.0, y), 3.0, 14.0, n=16, life=30, seed=410, size=2.0)
        # from a diagonal view of the shore and the queue, a pull-back up to a high view of the whole bay
        self.shot(b, b + int(L_ * 0.45), cam_from=(-70, -78, 30), aim_from=(-48, 0, 0), cam_to=(-60, -100, 46),
                  aim_to=(-20, 6, 0), lens=22, cut=True)
        self.shot(b + int(L_ * 0.45) + 1, e, cam_from=(-60, -100, 46), aim_from=(-20, 6, 0),
                  cam_to=(-48, -160, 100), aim_to=(0, 12, -4), lens=22)

    def a_suspension(self, i, b, e):
        L_ = e - b
        for side in ("L", "R"):
            dirt, asph = self.roads[side]
            toy.hide_tree(dirt, b, True)
            show_between(asph, b)
        for an in self.anchors:
            pop_in(an, b + 4, frames=10)
        rise0, rise1 = b + 4, b + int(L_ * 0.3)
        for x, foot, legs, beams in self.towers:
            pop_in(foot, rise0, frames=8)
            for leg in legs:
                show_between(leg, rise0 + 4)
                _key(leg, rise0 + 4, scale=V((1, 1, 0.02)))
                _key(leg, rise1, scale=V((1, 1, 1)))
            for k, bm in enumerate(beams):
                pop_in(bm, rise0 + 6 + int((rise1 - rise0) * (k + 1) / 3), frames=6)
        events.add(rise0, "rumble", duration=rise1 - rise0, gain=0.5)
        c0, c1 = rise1 + 2, b + int(L_ * 0.55)
        for c in self.cables:
            show_between(c, c0)
            draw_on(c, c0, c1)
        events.add(c0, "whoosh", gain=0.6)
        h0, h1 = c1, b + int(L_ * 0.7)
        hs = sorted(self.hangers, key=lambda h: min(abs(h.location.x - TOWER_X), abs(h.location.x + TOWER_X)))
        for k, h in enumerate(hs):
            pop_in(h, h0 + int((h1 - h0) * k / len(hs)), frames=5)
        d0, d1 = h1 - 6, b + int(L_ * 0.86)
        ss = sorted(self.segments, key=lambda s: min(abs(s.location.x - TOWER_X), abs(s.location.x + TOWER_X)))
        for k, s in enumerate(ss):
            f = d0 + int((d1 - d0) * k / len(ss))
            pop_in(s, f, frames=6)
            if k % 4 == 0:
                events.add(f + 4, "steel_clank", gain=0.4)
        self.traffic_windows.append((d1 + 4, e + 1, None))
        toy.hide_tree(self.ship, b, False)                           # away during a_wide_bay; back on the cut
        _key(self.ship, b, location=V((0, 60, WATER_Z)))
        _key(self.ship, e, location=V((0, 34, WATER_Z)))
        self.shot(b, b + int(L_ * 0.5), cam_from=(-110, -150, 55), aim_from=(0, 0, 8), cam_to=(-95, -125, 42),
                  aim_to=(0, 0, 8), lens=22, cut=True)
        self.shot(b + int(L_ * 0.5) + 1, e, cam_from=(-55, -78, 26), aim_from=(0, 0, 6), cam_to=(-38, -66, 18),
                  aim_to=(10, 0, 4), lens=22)

    def a_heat(self, i, b, e):
        """The sun blazes: a drawn sun pops up in the sky and the sun, sky, light and whole picture turn
        clearly amber within the first sixth, then keep heating to full amber near the end, white
        heat-shimmer lines rising off the deck. The deck grows and, trapped between its ends, buckles up
        into a sharp tent peaking at BUCKLE_X (at mid-span the main cables hang only 2 m over the deck,
        there they are 7 m up), the hangers on it riding up too; it is already visibly bowed by the
        beat's middle. See-through dust puffs off the peak and the tent's feet until the cut, and cars
        brake hard and stop short of the tent: two in the near lane just left of it, one in the far lane
        right of it."""
        L_ = e - b
        sun0, col0, bg0 = self.sun.data.energy, tuple(self.sun.data.color), self.bg.default_value
        self._heat_base = (sun0, col0, bg0)
        self._heat_hot = (sun0 * 1.6, HOT_SUN, bg0 * 1.05)            # brighter washes out in AgX

        def mix(a, c, t):
            return tuple(x + (y - x) * t for x, y in zip(a, c))
        # two stages: clearly warm early (the first window), then still heating up through the second
        for f, t in ((b, 0.0), (b + int(L_ * 0.15), 0.55), (b + int(L_ * 0.9), 1.0)):
            self.sun_key(f, energy=sun0 + (self._heat_hot[0] - sun0) * t, color=mix(col0, HOT_SUN, t),
                         bg=bg0 + (self._heat_hot[2] - bg0) * t)
            self._tint_key(f, t)
            self._grade_key(f, t)
        # low, nearly side-on view from over the water in front of the main span, square to the deck: the
        # tent rises as a clear profile against the river and sky (a high or oblique view looks down on
        # the deck and foreshortens the rise away). Just above tree height, ~9 degrees down, so the road
        # and the cars on both lanes still show over the near rail; a slow push in keeps the whole tent
        # (feet x = 10 and 30) and the stopped cars in frame (at the end it spans about x = -5 .. 37 at the
        # deck, ~50 m away, the right tower at its right edge)
        c0, a0 = V((9.0, -62.0, 14.0)), V((15.5, 0, 3.0))
        c1, a1 = V((14.0, -50.0, 11.0)), V((16.0, 0, 2.5))
        # the blazing sun high overhead, top centre of the frame (midday, not a low sunset sun)
        self._sun_icon(b + int(L_ * 0.04), e + 1, (16, 120, 80), c0.lerp(c1, 0.5))
        # the buckle starts at once and keeps growing (40 % up by the beat's middle, full at 64 %)
        bk0, bk1 = b + int(L_ * 0.05), b + int(L_ * 0.64)
        grow = [(bk0, 0.0), (b + int(L_ * 0.25), 0.15), (b + int(L_ * 0.45), 0.4), (bk1, 1.0)]
        peak, reach = 5.0, 10.0                              # reach: whole segments (a segment edge at the peak)

        def tent(x, k):
            return k * peak * max(0.0, 1 - abs(x - BUCKLE_X) / reach)

        def k_at(f):
            if f <= grow[0][0]:
                return 0.0
            for (fa, ka), (fb, kb) in zip(grow, grow[1:]):
                if f <= fb:
                    return ka + (kb - ka) * (f - fa) / max(1, fb - fa)
            return 1.0
        for s in self.segments:
            s["x0"] = s.location.x
        self.seg_pose(bk0, z=0.0, pitch=0.0)
        self._lifted = [hi for hi in self.hanger_info if tent(hi[1], 1.0) > 0]
        for h, x, y, top in self._lifted:
            toy.key_hold(h, "location", bk0)
            toy.key_hold(h, "scale", bk0)
        for f, k in grow[1:]:
            slope = math.atan(k * peak / reach)
            self.seg_pose(f, z=lambda s, k=k: tent(s["x0"], k),
                          pitch=lambda s, sl=slope: (math.copysign(sl, s["x0"] - BUCKLE_X)
                                                     if abs(s["x0"] - BUCKLE_X) < reach else 0.0))
            for h, x, y, top in self._lifted:                  # from the lifted girder up to the cable
                lift = tent(x, k)
                _key(h, f, location=V((x, y, (top + 0.6 + lift) / 2)), scale=V((1, 1, (top - 0.6 - lift) / (top - 0.6))))
        # heat shimmer: wavy white lines rising off the road on and around the buckle, drawn and erased
        for c, x in enumerate((BUCKLE_X - 6.0, BUCKLE_X, BUCKLE_X + 6.0)):
            for n, f in enumerate(range(b + int(L_ * 0.1) + 7 * c, e - 27, 24)):   # all gone before the cut
                z0 = tent(x, k_at(f + 12)) + 1.0
                pts = [(x + 0.45 * math.sin(j * 0.9 + c), 0.0, z0 + j * 0.35) for j in range(12)]
                sh = stroke(f"heat_shimmer{c}_{n}", pts, width=0.16)
                show_between(sh, f, f + 26)
                draw_on(sh, f, f + 10, erase=f + 14, erase_frames=10)
                _key(sh, f, location=V((0, 0, 0)))
                _key(sh, f + 24, location=V((0, 0, 1.6)))
        # dust: see-through puffs where the deck kinks (the peak and the tent's two feet), spread across
        # the deck width, a first burst as the deck bows, a big one as it peaks, then a steady trickle
        # until just before the cut; ~2x the old size so they read on a phone from ~50 m away
        mid = grow[2][0]
        drnd = random.Random(1061)
        kinks = (BUCKLE_X - reach, BUCKLE_X, BUCKLE_X, BUCKLE_X + reach)  # the peak twice as often

        def ridge(f):
            x = drnd.choice(kinks) + drnd.uniform(-1.2, 1.2)
            return V((x, drnd.uniform(-DECK_HALF_W, DECK_HALF_W), tent(x, k_at(f)) + 0.7))
        self._dust_puffs("dust_buckle_early", 12, 1.9, 1062).emit(
            range(mid, mid + 24, 2), ridge, rise=3.5, life=24, drift=1.8)
        self._dust_puffs("dust_buckle", 26, 2.8, 1063).emit(
            range(bk1 - 6, bk1 + 18), ridge, rise=5.0, life=26, drift=2.6)
        self._dust_puffs("dust_buckle_trail", 12, 2.1, 1064).emit(
            range(bk1 + 18, e - 10, 3), ridge, rise=4.0, life=26, drift=2.0)
        events.add(bk0, "bridge_groan", gain=1.0)
        events.add(grow[1][0], "creak", gain=0.6)
        events.add(mid, "creak", gain=0.8)
        events.add(bk1 - 6, "crack", gain=0.9)
        # cars brake hard and stop short of the tent (feet at x = 10 and 30), all inside the frame: in the
        # near lane a red car (front 3 m short of the foot) with a yellow one close behind it, in the far
        # lane a blue one from the right; brake lights on, nose dipping while they brake
        lanes, cz = self.TRAFFIC["lanes"], self.TRAFFIC["z"]
        fb = b + int(L_ * 0.4)
        v = 0.42                                                   # m per frame (~45 km/h)
        plan = ((lanes[0], fb, 5.0, 9.0), (lanes[0], fb + 5, -2.0, 12.0), (lanes[1], fb - 8, 33.5, 10.0))
        for (car, lights), ((y, d), f_brake, x_stop, dist) in zip(self.heat_cars, plan):
            t_brake = 2 * dist / v                                 # uniform deceleration over `dist`
            f_stop = min(e - 2, f_brake + int(t_brake))

            def x_at(f, d=d, f_brake=f_brake, x_stop=x_stop, dist=dist, t_brake=t_brake):
                t = f - f_brake
                if t <= 0:
                    s = -dist + v * t
                elif t < t_brake:
                    s = -dist + v * t - v * t * t / (2 * t_brake)
                else:
                    s = 0.0
                return x_stop + d * s
            toy.hide_tree(car, b, False)
            toy.hide_tree(car, e + 1, True)
            frames = sorted(set(range(b, f_stop, 2)) | {f_stop, e})
            for f in frames:
                _key(car, f, location=V((x_at(f), y, cz)))
            toy.set_interpolation(car, "location", frames, "LINEAR")
            pitch = R(3.5)
            for f, p in ((b, 0.0), (f_brake, 0.0), (f_brake + 4, pitch), (f_stop, pitch), (f_stop + 5, -R(1.2)),
                         (f_stop + 11, 0.0)):
                if f <= e:
                    _key(car, f, rotation_euler=V((0, p, 0 if d > 0 else math.pi)))
            for lt in lights:
                _key(lt, b, scale=V((0.01, 0.01, 0.01)))
                _key(lt, f_brake - 1, scale=V((0.01, 0.01, 0.01)))
                _key(lt, f_brake, scale=V((1, 1, 1)))
        events.add(b + 2, "traffic", duration=fb - b, gain=0.4)
        keys = []
        for f in sorted(set(range(b, e, 3)) | {e}):
            g = ease((f - b) / max(1, L_))
            keys.append((f, c0.lerp(c1, g), a0.lerp(a1, g)))
        self.rig.track(b, e, keys, lens=22, fstop=11.0, cut=True)

    def a_expansion_joint(self, i, b, e):
        L_ = e - b
        sun0, col0, bg0 = self._heat_base
        hot_e, hot_col, hot_bg = self._heat_hot
        cool = b + int(L_ * 0.2)
        self.sun_key(b, energy=hot_e, color=hot_col, bg=hot_bg)        # hold the heat through a_heat
        self.sun_key(cool, energy=sun0, color=col0, bg=bg0)
        self._tint_key(b, 1.0)
        self._tint_key(cool, 0.0)
        self._grade_key(b, 1.0)
        self._grade_key(cool, 0.0)
        self.seg_pose(b, z=lambda s: toy.value_at(s, "location", b)[2], pitch=lambda s: toy.value_at(s, "rotation_euler", b)[1])
        self.seg_pose(b + int(L_ * 0.18), z=0.0, pitch=0.0)
        for h, x, y, top in self._lifted:                              # the hangers settle with the deck
            toy.key_hold(h, "location", b)
            toy.key_hold(h, "scale", b)
            _key(h, b + int(L_ * 0.18), location=V((x, y, (top + 0.6) / 2)), scale=V((1, 1, 1)))
        j0 = b + int(L_ * 0.2)
        left_teeth = []
        for t, from_left in self.joint_parts:
            pop_in(t, j0 + (2 if from_left else 4), frames=6)
            if from_left:
                left_teeth.append(t)
        box = stroke("joint_box", [(JOINT_X - 1.4, -DECK_HALF_W - 0.4, 0.75), (JOINT_X + 1.4, -DECK_HALF_W - 0.4, 0.75),
                                   (JOINT_X + 1.4, DECK_HALF_W + 0.4, 0.75), (JOINT_X - 1.4, DECK_HALF_W + 0.4, 0.75)],
                     width=0.09, closed=True)
        show_between(box, j0 + 8, e + 1)
        draw_on(box, j0 + 8, j0 + 22)
        events.add(j0 + 8, "pop", gain=0.5)
        # the deck "breathes" through the joint: everything left of it slides together
        left = [s for s in self.segments if s["x0"] < JOINT_X]
        for t in left_teeth:
            t["x0"] = t.location.x
        breath = [(j0 + 24, 0.0), (j0 + 24 + int(L_ * 0.18), 0.35), (j0 + 24 + int(L_ * 0.36), -0.25), (e, 0.0)]
        for f, dx in breath:
            if f > e:
                continue
            self.seg_pose(f, dx=dx, segs=left)
            for t in left_teeth:
                _key(t, f, location=V((t["x0"] + dx, t.location.y, t.location.z)))
        events.add(j0 + 24, "steel_clank", gain=0.3)
        self.traffic_windows.append((j0 + 20, e + 1, None))
        self.shot(b, e, cam_from=(JOINT_X + 0.5, -13.0, 8.0), aim_from=(JOINT_X, 0, 0.4),
                  cam_to=(JOINT_X - 0.5, -10.5, 6.2), aim_to=(JOINT_X, 0, 0.5), lens=26, cut=True)


    def _flutter_rest(self, f):
        """Key the hangers and main cables at rest (the deck segments are keyed by seg_pose)."""
        for h, x, y, top in self.hanger_info:
            _key(h, f, location=V((x, y, (top + 0.6) / 2)), scale=V((1, 1, 1)))
        for c in self.cables:
            _key(c, f, location=V((0, 0, 0)))

    def _flutter(self, f0, f1, amp_fn, step=2):
        """Wind flutter, Tacoma's torsional mode: the two halves of the main span twist opposite ways
        about a still line at midspan (full twist at the quarter spans, none at the towers) while the
        deck heaves; the hangers stretch to stay on the deck edges and the main cables bob with it.
        amp_fn(f) is the twist in degrees. The node at midspan keeps the deck clear of the low cable
        there. The phase is absolute, so the motion runs on unbroken from 'wind' into 'stiffening'."""
        for s in self.segments:
            if "x0" not in s:
                s["x0"] = s.location.x
        for f in sorted(set(range(f0, f1 + 1, step)) | {f1}):
            a = amp_fn(f)
            tw = math.sin(2 * math.pi * f / TWIST_PERIOD)
            hv = math.sin(2 * math.pi * f / HEAVE_PERIOD + 1.2)

            def roll(x, a=a, tw=tw):
                return R(a) * math.sin(2 * math.pi * x / 80.0) * tw

            def heave(x, a=a, hv=hv):
                return 0.05 * a * math.cos(math.pi * x / 80.0) * hv
            self.seg_pose(f, roll=lambda s: roll(s["x0"]), z=lambda s: heave(s["x0"]))
            bob = 0.02 * a * hv
            for c in self.cables:
                _key(c, f, location=V((0, 0, bob)))
            for h, x, y, top in self.hanger_info:
                r = roll(x)
                lo = heave(x) + y * math.sin(r) + 0.6 * math.cos(r)    # where the deck edge has moved to
                hi = top + bob
                _key(h, f, location=V((x, y, (hi + lo) / 2)), scale=V((1, 1, (hi - lo) / (top - 0.6))))

    def _gusts(self, name, f0, f1, n=22, seed=7, xs=(-30, 40), zs=(2.0, 15.0)):
        """Wind streaks blowing across the river (+Y) through the bridge: each white pen line draws
        itself on and wipes away again, over and over (~40 m/s), so the air is busy from the first
        frame; 8 streaks start at once, the rest join over the first third of the beat. xs keeps them
        clear of the camera (the drone camera sits at x < -40)."""
        rnd = random.Random(seed)
        L_ = f1 - f0
        for k in range(n):
            x = rnd.uniform(*xs)
            y0 = rnd.uniform(-30, -6)
            z = rnd.uniform(*zs)
            amp, ph = rnd.uniform(0.3, 0.9), rnd.uniform(0, 6.3)
            pts = [(x + 1.2 * math.sin(j * 0.5 + ph), y0 + j * 1.8, z + amp * math.sin(j * 0.7 + ph)) for j in range(20)]
            ob = stroke(f"{name}{k}", pts, width=0.2)
            show_between(ob, f0, f1 + 1)
            cu = ob.data
            per = rnd.randint(40, 52)
            s = f0 + rnd.randint(0, 4) if k < 8 else f0 + int(L_ * 0.3 * (k - 8) / max(1, n - 8)) + rnd.randint(0, 6)
            frames = []
            while s + 38 <= f1:
                for prop, val, f in (("bevel_factor_start", 0.0, s), ("bevel_factor_end", 0.0, s),
                                     ("bevel_factor_end", 1.0, s + 24), ("bevel_factor_start", 0.0, s + 14),
                                     ("bevel_factor_start", 1.0, s + 38), ("bevel_factor_end", 1.0, s + 38)):
                    setattr(cu, prop, val)
                    cu.keyframe_insert(prop, frame=f)
                frames += [s, s + 14, s + 24, s + 38]
                s += per
            # linear: the head and tail move at wind speed, and the reset (1,1) → (0,0) stays zero-length
            toy.set_interpolation(cu, "bevel_factor_start", frames, "LINEAR")
            toy.set_interpolation(cu, "bevel_factor_end", frames, "LINEAR")

    def a_wind(self, i, b, e):
        L_ = e - b
        self._gusts("wind_a", b, e)
        self._flutter_rest(b - 1)
        self._flutter(b, e, lambda f: 2.0 + (FLUTTER_MAX - 2.0) * ease((f - b) / max(1, L_ * 0.6)))
        events.add(b, "wind", duration=e - b, gain=1.2)
        events.add(b + int(L_ * 0.3), "bridge_groan", gain=0.8)
        self.shot(b, e, cam_from=(-54, -46, 19), aim_from=(2, 0, -1), cam_to=(-46, -40, 16), aim_to=(2, 0, -1), lens=22,
                  cut=True)

    def a_stiffening(self, i, b, e):
        L_ = e - b
        # the same busy gusts as in 'wind', kept clear of the camera's path (x < -18)
        self._gusts("wind_b", b, e, seed=11, xs=(-18, 45), zs=(4.0, 18.0))
        calm = b + int(L_ * 0.3)
        self._flutter(b, calm, lambda f: FLUTTER_MAX * (1 - ease((f - b) / max(1, calm - b))))
        self.seg_pose(calm + 1, roll=0.0, z=0.0)
        self._flutter_rest(calm + 1)
        # the truss grows outward from the middle of the push-in framing (x ~ 5), from the first frames
        # to three quarters of the beat, so it is visibly building the whole time the camera is close
        n = len(self.stiff)
        order = sorted(self.stiff, key=lambda o: (abs(o.location.x - 5.0), o.location.y, o.location.z))
        t0, t1 = b + 2, b + int(L_ * 0.75)
        for k, o in enumerate(order):
            f = t0 + int((t1 - t0) * k / n)
            pop_in(o, f, frames=5)
            if k % 12 == 0:
                events.add(f + 3, "steel_clank", gain=0.4)
        events.add(b, "wind", duration=e - b, gain=1.0)
        self.traffic_windows.append((b + int(L_ * 0.6), e + 1, None))
        # starts exactly where the 'wind' drone shot ended (no jump), then pushes in to 12 m above the
        # water, oblique along the span: the deck top reads in the upper half, the truss right under it
        mid = b + int(L_ * 0.6)
        self.shot(b, mid, cam_from=(-46, -40, 16), aim_from=(2, 0, -1), cam_to=(-30, -24, 8.0),
                  aim_to=(6, 0, -1.5), lens=22)
        self.shot(mid + 1, e, cam_from=(-48, -52, 12), aim_from=(0, 0, 0), cam_to=(-40, -46, 10),
                  aim_to=(0, 0, 0), lens=22)

    def a_finale(self, i, b, e):
        L_ = e - b
        self.sun_key(b, energy=self.sun.data.energy, color=tuple(self.sun.data.color))
        self.sun_key(b + int(L_ * 0.5), energy=self.sun.data.energy * 0.85, color=(1.0, 0.78, 0.55))
        toy.key_hold(self.ship, "location", b - 1, "CONSTANT")
        _key(self.ship, b, location=V((0, -40, WATER_Z)))
        _key(self.ship, e + 20, location=V((0, -120, WATER_Z)))
        toy.set_interpolation(self.ship, "location", (b,), "LINEAR")
        self.traffic_windows.append((b, e + 1, None))
        events.add(b + int(L_ * 0.35), "ship_horn", gain=0.6)
        self.shot(b, e, cam_from=(-42, -62, 14), aim_from=(0, 0, 6), cam_to=(-150, -250, 80), aim_to=(-10, 0, 0),
                  lens=22, cut=True)

