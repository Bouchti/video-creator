"""
BRIDGE EVOLUTION set — Blender builder (see bridge_evolution_spec.py), built on engine/evo_kit.py.

One river valley seen from drone height. The river runs along Y; every bridge spans X, centred on
the origin. The two banks slide apart to widen the river (6 → 15 → 40 → 120 m), carrying their
forest, roads and the village with them. Each bridge is built on screen, then destroyed by the
next problem:

  plank (beam) → stone arch → steel truss → suspension → + expansion joint → + stiffening truss

The format's signature white line-drawings (triangle vs square, the box around the expansion
joint, wind streaks, load arrows) are emissive 3D curves that draw themselves on.
"""
import math
import random

from mathutils import Vector

from engine import events, textures as tx, toy
from engine.evo_kit import (WATER_Z, EvolutionSet, _hide, _key, base_box, beam, draw_on, ease, extrude_xz,
                            face_camera, fall, fly_in, mat, pop_in, show_between, stroke, attach)
from engine.sets.bridge_evolution_spec import ACTIONS

V = Vector
R = math.radians
GAP = {"plank": 6.0, "arch": 15.0, "truss": 40.0, "suspension": 120.0}
TOWER_X, TOWER_TOP, SAG_Z = 40.0, 24.0, 2.2
CABLE_Y, DECK_HALF_W = 5.4, 5.5
SEG = 5.0                            # suspension deck segment length (m)
DECK_X0, DECK_X1 = -65.0, 65.0
JOINT_X = 20.0                       # a segment edge in the main span (clear of the towers)

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

    # ------------------- the bridges (built hidden; the actions animate them) -------------------

    def _plank_bridge(self):
        """Two log beams and a plank deck over the 6 m stream, as two halves that can sag apart."""
        g0 = GAP["plank"] / 2
        self.plank_halves = []
        self.planks = []
        self.plank_rails = []
        for side, sgn in (("L", -1), ("R", 1)):
            bank = self.banks[side]
            pivot = toy.empty(f"plank_pivot_{side}", (sgn * 4.4, 0, 0.18))
            for y in (-0.95, 0.95):
                log = toy.cylinder(f"plank_log_{side}{y}", 0.2, 4.6, (sgn * 2.2, y, 0.18), rotation=(0, R(90), 0),
                                   mat=self.m_log, vertices=12)
                attach(log, pivot)
            n = 12
            for k in range(n):
                x = sgn * (0.18 + k * 0.36)
                pl = toy.box(f"plank_{side}{k}", (0.32, 2.7, 0.07), (x, 0, 0.42), mat=self.m_plank, bevel=0.01,
                             rotation=(0, 0, R(self.rnd.uniform(-2, 2))))
                attach(pl, pivot)
                self.planks.append((x, pl))
            for y in (-1.3, 1.3):
                for k in range(4):
                    post = toy.cylinder(f"plank_post_{side}{y}{k}", 0.05, 1.0, (sgn * (0.3 + k * 1.3), y, 0.9),
                                        mat=self.m_log, vertices=8)
                    attach(post, pivot)
                    self.plank_rails.append(post)
                rail = toy.cylinder(f"plank_rail_{side}{y}", 0.045, 4.2, (sgn * 2.2, y, 1.35),
                                    rotation=(0, R(90), 0), mat=self.m_log, vertices=8)
                attach(rail, pivot)
                self.plank_rails.append(rail)
            attach(pivot, bank)
            self.plank_halves.append((pivot, sgn))
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

    def _arch_bridge(self):
        """Segmental stone arch springing from the waterline at x = ±7.5, plus spandrel walls, road and parapets."""
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
        ext = [(math.sin(a) * (Rr + ring), cz + math.cos(a) * (Rr + ring))
               for a in [a_max - k * 2 * a_max / 24 for k in range(25)]]
        outline = [(-half - 3.5, 0.25), (half + 3.5, 0.25), (half + 3.5, WATER_Z - 0.5)] + ext + \
                  [(-half - 3.5, WATER_Z - 0.5)]
        self.spandrel = extrude_xz("arch_spandrel", outline, -2.2, 2.2, self.m_stone)
        self.spandrel.parent = self.arch_root
        self.arch_deck = []
        road = toy.box("arch_road", (2 * half + 7, 4.0, 0.12), (0, 0, 0.3), mat=self.m_dirt, bevel=0)
        road.parent = self.arch_root
        self.arch_deck.append(road)
        for y in (-2.1, 2.1):
            par = toy.box(f"arch_parapet{y}", (2 * half + 7, 0.45, 0.9), (0, y, 0.7), mat=self.m_stone2, bevel=0.04)
            par.parent = self.arch_root
            self.arch_deck.append(par)
        self.arch_geom = (Rr, cz, a_max, ring)
        toy.hide_tree(self.arch_root, 0, True)

    def _truss_bridge(self):
        """A Pratt-truss railway bridge over the 40 m river: two red trusses, bracing, deck and rails."""
        L, n, H, yt = 46.0, 11, 5.5, 3.6
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
            r = toy.box(f"truss_rail{y}", (L + 30, 0.12, 0.16), (0, y, 0.3), mat=self.m_rail, bevel=0)
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
        self.hangers = []
        hm = mat("ev_hanger", "#8E3A26", 0.5)
        for k in range(-14, 15):
            x = k * 5.0 + 2.5
            if abs(abs(x) - TOWER_X) < 2.0 or abs(x) > 70:
                continue
            for y in (-CABLE_Y, CABLE_Y):
                top = cable_z(x)
                h = toy.cylinder(f"hanger{k}{y}", 0.07, top - 0.6, (x, y, (top + 0.6) / 2), mat=hm, vertices=6)
                self.hangers.append(h)
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

    # ------------------- the actions -------------------

    def a_plank(self, i, b, e):
        L_ = e - b
        for pivot, sgn in self.plank_halves:
            for ch in pivot.children:
                if ch.name.startswith("plank_log"):
                    fly_in(ch, b + 2, b + int(L_ * 0.18), (sgn * 3.0, 0, 0.6))
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
        events.add(c0, "roll", duration=c1 - c0, gain=0.5)
        self.shot(b, e, cam_from=(-2.5, -25, 11), aim_from=(0, 2, -0.5), cam_to=(-1.5, -16, 7.0),
                  aim_to=(0, 1, 0.2), lens=22, cut=True)

    def a_widen_arch(self, i, b, e):
        L_ = e - b
        g0, g1 = GAP["plank"], GAP["arch"]
        slide_end = b + int(L_ * 0.62)
        self.widen(b, slide_end, g0, g1)
        crack = b + int(L_ * 0.48)
        for pivot, sgn in self.plank_halves:
            _key(pivot, b, rotation_euler=V((0, 0, 0)))
            _key(pivot, crack, rotation_euler=V((0, sgn * -R(9), 0)))     # sags as its support slides away
            _key(pivot, crack + 10, rotation_euler=V((0, sgn * -R(78), 0)))
            loc = V(pivot.location)
            _key(pivot, crack + 10, location=loc)
            _key(pivot, crack + 24, location=loc + V((0, 0, -8)))
            toy.hide_tree(pivot, crack + 25, True)
        events.add(crack - 6, "creak", gain=0.9)
        events.add(crack, "crack", gain=0.8)
        self.splash("splash_planks", crack + 12, (0, 0, WATER_Z), size=0.8)
        self.shot(b, e, cam_from=(-2, -22, 11), aim_from=(0, 2, -1.5), cam_to=(-3, -36, 19), aim_to=(0, 3, -2.0),
                  lens=22)

    def a_arch(self, i, b, e):
        L_ = e - b
        Rr, cz, a_max, ring = self.arch_geom
        n = len(self.voussoirs)
        order = []
        lo, hi = 0, n - 1
        while lo < hi:                                          # from both springings inwards, keystone last
            order += [lo, hi]
            lo, hi = lo + 1, hi - 1
        order.append(n // 2)
        t0, t1 = b + 2, b + int(L_ * 0.5)
        for j, k in enumerate(order):
            st = self.voussoirs[k]
            f = t0 + int((t1 - t0) * j / len(order))
            side = -1 if st.location.x < 0 else 1
            last = j == len(order) - 1
            fly_in(st, f, f + (12 if last else 9), (side * 6.0 if not last else 0, -2.0, 9.0 if last else 6.0),
                   spin=R(40))
            events.add(f + 9, "stone_thud", gain=1.0 if last else 0.35)
        key_f = t1 + 12
        self.dust("dust_keystone", key_f, (0, 0, -0.5), size=0.5)
        fill0 = key_f + 2
        self.spandrel.scale = (1, 1, 1)
        _hide(self.spandrel, 0, True)
        _hide(self.spandrel, fill0, False)
        _key(self.spandrel, fill0, scale=V((1, 0.02, 1)))
        _key(self.spandrel, fill0 + int(L_ * 0.12), scale=V((1, 1, 1)))
        for k, o in enumerate(self.arch_deck):
            pop_in(o, fill0 + int(L_ * 0.12) + 2 * k, frames=8)
        # load path: weight pushes down at the crown, flows along the curve into both banks
        f_ar = b + int(L_ * 0.72)
        rm = Rr + ring / 2
        down = stroke("arch_load_down", [(0, -2.5, 6.0), (0, -2.5, 1.2)], width=0.14, material=self.m_ink_orange)
        for sgn in (-1, 1):
            pts = [(rm * math.sin(sgn * a_max * k / 16), -2.5, cz + rm * math.cos(sgn * a_max * k / 16) + 0.9)
                   for k in range(17)]
            end = V(pts[-1])
            pts.append(tuple(end + V((sgn * 3.0, 0, -1.4))))
            arr = stroke(f"arch_load{sgn}", pts, width=0.14, material=self.m_ink_orange)
            draw_on(arr, f_ar, f_ar + 14, erase=e - 10, erase_frames=8)
        draw_on(down, f_ar - 8, f_ar, erase=e - 10, erase_frames=8)
        self.shot(b, b + int(L_ * 0.6), cam_from=(-5, -23, 4.5), aim_from=(0, 0, -1.6), cam_to=(-3, -19, 2.5),
                  aim_to=(0, 0, -1.4), lens=22)
        self.shot(b + int(L_ * 0.6) + 1, e, cam_from=(4, -26, 1.5), aim_from=(0, 0, -1.2), cam_to=(1, -24, 1.0),
                  aim_to=(0, 0, -1.2), lens=24)

    def a_widen_truss(self, i, b, e):
        L_ = e - b
        self.widen(b + 4, b + int(L_ * 0.7), GAP["arch"], GAP["truss"])
        rnd = random.Random(21)
        c0 = b + int(L_ * 0.18)
        parts = self.voussoirs + [self.spandrel] + self.arch_deck
        for k, st in enumerate(sorted(self.voussoirs, key=lambda o: abs(o.location.x))):
            f = c0 + int(L_ * 0.35 * k / len(self.voussoirs))
            fall(st, f, f + 16, 7.0, rnd, spin=90, drift=1.5)
        for o in [self.spandrel] + self.arch_deck:
            fall(o, c0 + 6, c0 + 30, 9.0, rnd, spin=12, drift=0.5)
        del parts
        events.add(c0, "crack", gain=0.9)
        events.add(c0 + 4, "stone_thud", gain=0.8)
        self.splash("splash_arch", c0 + 14, (0, 0, WATER_Z), size=1.4, n=12)
        # the ship comes into view upstream
        _key(self.ship, b, location=V((0, 260, WATER_Z)))
        show_between(self.ship, b)
        self.shot(b, e, cam_from=(-3, -32, 13), aim_from=(0, 6, -2), cam_to=(-6, -68, 30), aim_to=(0, 14, -2),
                  lens=22)

    def a_truss(self, i, b, e):
        L_ = e - b
        pop_in(self.truss_deck, b + 2, frames=10)
        for r in self.truss_rails:
            pop_in(r, b + 6, frames=8)
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
        _key(self.train, tr0, location=V((-70, 0, 0.12)))
        _key(self.train, tr1, location=V((70, 0, 0.12)))
        toy.set_interpolation(self.train, "location", (tr0,), "LINEAR")
        show_between(self.train, tr0, e + 1)
        events.add(tr0, "train_pass", duration=e - tr0, gain=0.7)
        _key(self.ship, b, location=V((0, 260, WATER_Z)))
        _key(self.ship, e, location=V((0, 70, WATER_Z)))
        self.shot(b, d0 - 4, cam_from=(-12, -46, 18), aim_from=(0, 0, 2.5), cam_to=(-8, -36, 12), aim_to=(0, 0, 3.0),
                  lens=22)
        self.shot(d0 - 3, e, cam_from=cam, aim_from=(0, 0, 8.5), cam_to=cam + V((1.5, 2.0, 0)), aim_to=(0, 0, 8.5),
                  lens=24)

    def a_widen_suspension(self, i, b, e):
        L_ = e - b
        self.widen(b + 2, b + int(L_ * 0.7), GAP["truss"], GAP["suspension"])
        f0, f1 = b + int(L_ * 0.25), b + int(L_ * 0.5)
        toy.key_hold(self.truss_root, "location", f0)
        toy.key_hold(self.truss_root, "rotation_euler", f0)
        _key(self.truss_root, f1, location=V((0, 3, WATER_Z - 6)), rotation_euler=V((R(70), R(4), 0)))
        toy.hide_tree(self.truss_root, f1 + 2, True)
        events.add(f0, "bridge_groan", gain=0.9)
        self.splash("splash_truss", f1 - 6, (0, 2, WATER_Z), size=2.6, n=14, rise=8)
        _key(self.ship, e, location=V((0, 60, WATER_Z)))
        self.shot(b, e, cam_from=(-10, -46, 18), aim_from=(0, 0, -1), cam_to=(-120, -175, 70), aim_to=(0, 10, -4),
                  lens=22)

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
        _key(self.ship, b, location=V((0, 60, WATER_Z)))
        _key(self.ship, e, location=V((0, 34, WATER_Z)))
        self.shot(b, b + int(L_ * 0.5), cam_from=(-110, -150, 55), aim_from=(0, 0, 8), cam_to=(-95, -125, 42),
                  aim_to=(0, 0, 8), lens=22)
        self.shot(b + int(L_ * 0.5) + 1, e, cam_from=(-55, -78, 26), aim_from=(0, 0, 6), cam_to=(-38, -66, 18),
                  aim_to=(10, 0, 4), lens=22)

    def a_heat(self, i, b, e):
        L_ = e - b
        sun0 = self.sun.data.energy
        self.sun_key(b, energy=sun0, color=tuple(self.sun.data.color), bg=self.bg.default_value)
        self.sun_key(b + int(L_ * 0.3), energy=sun0 * 1.7, color=(1.0, 0.72, 0.45), bg=self.bg.default_value * 1.35)
        self._heat_base = (sun0, (1.0, 0.93, 0.82))
        bk0, bk1 = b + int(L_ * 0.35), b + int(L_ * 0.62)
        peak, reach = 2.4, 20.0
        for s in self.segments:
            s["x0"] = s.location.x
        self.seg_pose(bk0, z=0.0, pitch=0.0)

        def z(s):
            return peak * max(0.0, 1 - abs(s["x0"]) / reach)

        def pitch(s):
            return math.copysign(math.atan(peak / reach), s["x0"]) if abs(s["x0"]) < reach else 0.0
        self.seg_pose(bk1, z=z, pitch=pitch)
        self.dust("dust_buckle", bk1 - 6, (0, 0, peak), size=0.9, n=10)
        events.add(bk0, "bridge_groan", gain=1.0)
        events.add(bk1 - 6, "crack", gain=0.9)
        self.traffic_windows.append((b, e + 1, -26.0))                # cars stop short of the buckle
        self.shot(b, e, cam_from=(-9, -52, 14.0), aim_from=(0, 0, 1.6), cam_to=(-6, -42, 10.5), aim_to=(0, 0, 1.8),
                  lens=24, cut=True)

    def a_expansion_joint(self, i, b, e):
        L_ = e - b
        sun0, col0 = self._heat_base
        self.sun_key(b, energy=self.sun.data.energy)
        self.sun_key(b + int(L_ * 0.2), energy=sun0, color=col0, bg=self.bg.default_value / 1.35)
        self.seg_pose(b, z=lambda s: toy.value_at(s, "location", b)[2], pitch=lambda s: toy.value_at(s, "rotation_euler", b)[1])
        self.seg_pose(b + int(L_ * 0.18), z=0.0, pitch=0.0)
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


    def _twist(self, f0, f1, amp_fn, step=2):
        for s in self.segments:
            if "x0" not in s:
                s["x0"] = s.location.x
        for f in range(f0, f1 + 1, step):
            a = amp_fn(f)

            def roll(s, f=f, a=a):
                return R(a) * math.sin(2 * math.pi * s["x0"] / 80.0 - 2 * math.pi * (f - f0) / 44.0)

            def zz(s, f=f, a=a):
                return 0.09 * a * math.sin(2 * math.pi * s["x0"] / 80.0 - 2 * math.pi * (f - f0) / 44.0 + 1.2)
            self.seg_pose(f, roll=roll, z=zz)

    def a_wind(self, i, b, e):
        L_ = e - b
        self._wind_streaks("wind_a", b, e, n=14, cycles=3)
        self._twist(b, e, lambda f: 10.0 * ease((f - b) / max(1, L_ * 0.8)))
        events.add(b, "wind", duration=e - b, gain=1.2)
        events.add(b + int(L_ * 0.4), "bridge_groan", gain=0.8)
        self.shot(b, e, cam_from=(-62, -58, 20), aim_from=(0, 0, 1), cam_to=(-50, -50, 16), aim_to=(0, 0, 1), lens=22,
                  cut=True)

    def a_stiffening(self, i, b, e):
        L_ = e - b
        self._wind_streaks("wind_b", b, e, n=12, cycles=2)
        calm = b + int(L_ * 0.3)
        self._twist(b, calm, lambda f: 10.0 * (1 - ease((f - b) / max(1, calm - b))))
        self.seg_pose(calm + 1, roll=0.0, z=0.0)
        n = len(self.stiff)
        order = sorted(self.stiff, key=lambda o: min(abs(o.location.x - TOWER_X), abs(o.location.x + TOWER_X)))
        t0, t1 = b + 4, b + int(L_ * 0.55)
        for k, o in enumerate(order):
            f = t0 + int((t1 - t0) * k / n)
            pop_in(o, f, frames=5)
            if k % 12 == 0:
                events.add(f + 3, "steel_clank", gain=0.4)
        events.add(b, "wind", duration=e - b, gain=1.0)
        self.traffic_windows.append((b + int(L_ * 0.6), e + 1, None))
        self.shot(b, b + int(L_ * 0.55), cam_from=(-26, -24, -1.2), aim_from=(-5, 0, -1.6), cam_to=(-16, -21, -1.6),
                  aim_to=(2, 0, -1.4), lens=22, cut=True)
        self.shot(b + int(L_ * 0.55) + 1, e, cam_from=(-48, -52, 12), aim_from=(0, 0, 0), cam_to=(-40, -46, 10),
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

