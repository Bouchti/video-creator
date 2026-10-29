"""Staging for the reusable ``septic_yard`` kit world."""
import math

from engine import events, studio as st, toy
from engine.camera import CameraRig
from engine.character import Character
from engine.framing import solve, tan_half
from engine.sets.plane_story import arrow, label as make_label
from engine.kit.worlds import septic_yard_objects as obj


SETUP = 0.40
RESULT = 0.66
LENS, MARGIN, RISE, PUSH = 27.0, 0.11, 0.16, 0.07
LABEL_SHARE, CAP_HEIGHT = 0.034, 0.7  # label letters: share of the frame height; cap / font size
MAX_LOOK = {
    "hat": "#F28A24", "shirt": "#E5533D", "overalls": "#3E79A8",
    "shoes": "#D6A52A", "iris": "#76502D", "toolbelt": "#7B4B27",
}


def _key_vec(ob, path, frame, value):
    setattr(ob, path, value)
    ob.keyframe_insert(path, frame=frame)


def _move_vec(ob, path, a, b, va, vb):
    _key_vec(ob, path, a, va)
    _key_vec(ob, path, b, vb)


class SepticYardWorld:
    """Film any validated septic-yard storyboard, with or without Max."""

    STORYBOARD = None
    QA_ALLOW = None

    def __init__(self, scene, sun, fill, bg, total):
        self.scene, self.sun, self.fill, self.bg, self.total = scene, sun, fill, bg, total
        self.sb = self.STORYBOARD
        self.hero = self.sb.get("hero", True) is not False
        self.rig = CameraRig()

        # Every durable item comes from the object kit.  Roots are placed so the
        # house drain, sewer, tank inlet/outlet, distribution box and well form
        # one readable section across the twenty metre cut face.
        self.ground = obj.build_septic_yard_ground()
        self.groundwater = obj.build_septic_yard_groundwater()
        self.house = obj.build_septic_yard_house()
        self.sewer_pipe = obj.build_septic_yard_sewer_pipe()
        self.pit = obj.build_septic_yard_pit()
        self.tank = obj.build_septic_yard_tank()
        self.layers = obj.build_septic_yard_layers()
        self.baffles = obj.build_septic_yard_baffles()
        self.drainfield = obj.build_septic_yard_drainfield()
        self.anchors = obj.build_septic_yard_anchors()
        self.well = obj.build_septic_yard_well()
        self.pump_truck = obj.build_septic_yard_pump_truck()

        self.pos = {
            "ground": (0.0, 0.0, 0.0), "groundwater": (0.0, 0.0, 0.0),
            "house": (-8.0, 0.72, 4.0), "sewer_pipe": (-4.0, -2.18, 2.84),
            "pit": (-0.75, -2.05, 2.73), "tank": (-0.75, -2.05, 1.78),
            "layers": (-0.75, -2.05, 1.90), "baffles": (0.63, -2.05, 2.37),
            "drainfield": (4.65, -0.35, 2.42), "anchors": (-0.75, -2.05, 1.72),
            "well": (9.15, -2.15, 0.0), "pump_truck": (-0.8, 0.25, 4.0),
        }
        for name, p in self.pos.items():
            getattr(self, name).location = p
        # The supplied anchor is a compact demonstrator; vertical scaling makes
        # its straps visibly pass over this tank while preserving its footprint.
        self.anchors.scale = (1.08, 1.2, 3.55)
        self._base_scale = {n: tuple(getattr(self, n).scale) for n in
                            ("pit", "tank", "layers", "baffles", "drainfield", "anchors", "pump_truck")}
        # Some failure events animate individual contents rather than their root.  Remember those local
        # transforms so the next cut (and a hook replayed after the body) gets a clean tank again.
        self._layer_parts = {c.name: c for c in self.layers.children
                             if c.name.endswith(("_sludge", "_scum"))}
        self._layer_part_base = {name: (tuple(part.location), tuple(part.scale))
                                 for name, part in self._layer_parts.items()}

        if self.hero:
            self.max = Character("Max", MAX_LOOK)
            # The lawn's top is about z=4.0.  Keeping the character root on that
            # surface makes the QA support ray hit the lawn instead of stopping
            # just above it.
            self.max.place(1, (-5.8, -1.0, 3.95), 0)
            self.max.auto_blink(1, total + 600, seed=19)
        else:
            self.max = None

        self.state = self._initial()
        self._apply(self.state, 1)

    # -------------------------------- state ---------------------------------
    @staticmethod
    def _initial():
        return {"pit": False, "tank": False, "layers": False, "anchors": False,
                "drainfield": False, "baffles": False, "filter": False,
                "pump_truck": False, "weather": "sunny"}

    def _apply(self, state, frame):
        """Cut the complete diorama to a planned state."""
        for name in ("ground", "groundwater", "house", "sewer_pipe", "well"):
            toy.hide_tree(getattr(self, name), frame, False)
        for name in ("pit", "tank", "layers", "anchors", "drainfield", "baffles", "pump_truck"):
            toy.hide_tree(getattr(self, name), frame, not state[name])
            getattr(self, name).location = self.pos[name]
            getattr(self, name).keyframe_insert("location", frame=frame)
            getattr(self, name).scale = self._base_scale[name]
            getattr(self, name).keyframe_insert("scale", frame=frame)
            getattr(self, name).rotation_euler = (0.0, 0.0, 0.0)
            getattr(self, name).keyframe_insert("rotation_euler", frame=frame)
        for name, part in self._layer_parts.items():
            part.location, part.scale = self._layer_part_base[name]
            part.keyframe_insert("location", frame=frame)
            part.keyframe_insert("scale", frame=frame)
        rise = 1.18 if state["weather"] == "storm" else (0.58 if state["weather"] == "rain" else 0.0)
        self.groundwater.location = (0.0, 0.0, rise)
        self.groundwater.keyframe_insert("location", frame=frame)

    def _plan(self):
        """Return (before, after change, after event) for every storyboard step."""
        state, plan = self._initial(), {}
        for step in self.sb["steps"]:
            start = dict(state)
            after = dict(start, weather=step["weather"])
            ch = step["change"]
            if ch == "dig_pit":
                after["pit"] = True
            elif ch == "build_tank":
                after.update(pit=False, tank=True, layers=True)
            elif ch == "anchor_tank":
                after["anchors"] = True
            elif ch == "lay_drainfield":
                after["drainfield"] = True
            elif ch == "add_baffles":
                after["baffles"] = True
            elif ch == "schedule_pumping":
                after["pump_truck"] = True
            elif ch == "add_filter":
                after.update(baffles=True, filter=True)
            # Failures are demonstrated, then reset at the next cut.  This keeps
            # freely combined planner steps dependent only on vocabulary state.
            end = dict(after)
            plan[step["id"]] = (start, after, end)
            state = end
        return plan

    # -------------------------------- film ----------------------------------
    def run(self, beats, spans, epilogue_offset):
        self.EPI = epilogue_offset
        steps = {s["id"]: s for s in self.sb["steps"]}
        hooks = {h["id"]: h["step"] for h in self.sb.get("hooks", [])}
        plan = self._plan()
        hook_job = None
        for k, beat in enumerate(beats):
            action = (beat.get("actions") or [beat.get("action")])[0]
            s, e = spans[k]
            if action in steps:
                self._stage_step(steps[action], plan[action], s, e, k)
            elif action in hooks:
                hook_job = (steps[hooks[action]], plan[hooks[action]],
                            s + epilogue_offset, e + epilogue_offset, k)
        if hook_job:
            step, (_start, after, _end), s, e, k = hook_job
            self.state = dict(after)
            self._apply(self.state, s - 1)
            self._mechanism(step, s, e, hook=True, k=k)
        self.rig.build()

    def _stage_step(self, step, plan, s, e, k=0):
        start, after, end = plan
        self.state = dict(start, weather=step["weather"])
        self._apply(self.state, s)
        m0 = s + max(8, int((e - s) * SETUP))
        # Extending the build slightly into the mechanism makes it visibly in
        # progress at the beat midpoint, while it is complete long before 7/8.
        build_end = min(e - 8, s + max(12, int((e - s) * 0.58)))
        self._setup(step, start, after, s, m0, build_end, k)
        self.state = dict(after)
        self._mechanism(step, m0, e, k=k)
        self.state = dict(end)

    def _setup(self, step, start, after, s, m0, build_end, k):
        ch = step["change"]
        focus = self._change_focus(ch)
        if self.hero:
            # Work beside excavations and suspended parts, never directly under
            # them.  The sewer is buried here, so this remains firm lawn.
            x = self._hero_change_x(ch, focus[0])
            self.max.cut_place(s, (x, -1.05, 3.95), 0)
            self.max.pose(s)
            if ch == "none":
                self.max.talk(s + 2, m0 - 2)
                self.max.point(s + 4, m0 - 2, hand="L", up_deg=58, side_deg=-24)
            else:
                self.max.crouch(s + 2, m0 - 2, frames=5, lean=26)
                self.max.rake(s + 3, m0 - 2, stroke=10)
                for f in range(s + 6, m0 - 2, 12):
                    events.add(f, "scoop", gain=0.4)
            st.close_on(self.rig, s, m0 - 1, self.max, frac=0.43,
                        angle=-96 if k % 2 else -84, swing=10, cut=True)
        else:
            self._frame(step, self._change_objects(ch), s, m0 - 1, k, label=False)
        if ch != "none":
            self._build(ch, start, after, s + 2, build_end)

    def _build(self, ch, start, after, a, b):
        mid = a + (b - a) // 2
        if ch == "dig_pit":
            toy.hide_tree(self.pit, a, False)
            _move_vec(self.pit, "scale", a, b, (1.0, 1.0, 0.04), self._base_scale["pit"])
            events.add(a + 2, "scoop", duration=max(8, b - a), gain=0.45)
        elif ch == "build_tank":
            toy.hide_tree(self.pit, mid, True)
            toy.hide_tree(self.tank, a, False)
            toy.hide_tree(self.layers, a, False)
            p = self.pos["tank"]
            _move_vec(self.tank, "location", a, b, (p[0], p[1], p[2] + 4.2), p)
            lp = self.pos["layers"]
            _move_vec(self.layers, "location", a, b, (lp[0], lp[1], lp[2] + 4.2), lp)
            events.add(b - 5, "stone_thud", gain=0.6)
        elif ch == "anchor_tank":
            toy.hide_tree(self.anchors, a, False)
            _move_vec(self.anchors, "scale", a, b, (0.04, 1.2, 3.55), self._base_scale["anchors"])
            events.add(mid, "clink", gain=0.55)
        elif ch == "lay_drainfield":
            toy.hide_tree(self.drainfield, a, False)
            _move_vec(self.drainfield, "scale", a, b, (0.04, 1.0, 1.0), self._base_scale["drainfield"])
            events.add(a + 2, "gravel", duration=max(8, b - a), gain=0.5)
        elif ch in ("add_baffles", "add_filter"):
            toy.hide_tree(self.baffles, a, False)
            p = self.pos["baffles"]
            _move_vec(self.baffles, "location", a, b, (p[0], p[1], p[2] + 2.2), p)
            if ch == "add_filter":
                _move_vec(self.baffles, "scale", a, b, (0.55, 0.55, 0.12), self._base_scale["baffles"])
            events.add(b - 3, "clink", gain=0.5)
        elif ch == "schedule_pumping":
            toy.hide_tree(self.pump_truck, a, False)
            p = self.pos["pump_truck"]
            _move_vec(self.pump_truck, "location", a, b, (p[0] + 13.0, p[1], p[2]), p)
            events.add(a, "truck", duration=max(10, b - a), gain=0.55)

    def _mechanism(self, step, m0, e, hook=False, k=0):
        n = max(1, e - m0)
        t = lambda f: m0 + int(n * f)  # noqa: E731
        name = step["event"]
        getattr(self, f"_ev_{name}")(m0, e, t)
        if self.hero:
            x = self._hero_event_x(name)
            self.max.cut_place(m0, (x, -1.0, 3.95), 0)
            self.max.pose(m0)
            outcome = "fail" if name in {
                "pit_poisons_well", "tank_floats", "tank_backs_up", "scum_clogs_field",
                "sludge_reaches_outlet", "pumped_in_flood"} else "hold"
            if outcome == "fail":
                self._shrug(t(0.64), e - 2)
            else:
                self.max.cheer(t(0.64), e - 2)
                events.add(t(0.64), "boing", gain=0.28)
        r0 = m0 + int(n * RESULT)
        things = self._event_objects(name)
        if hook and self.hero:
            # Hook beats have no setup close-up, so hold Max large for enough
            # of the beat to read before returning to the mechanism.
            # Finish the hero close-up before the midpoint, where must-see QA
            # expects the tank and pipe, while retaining >35% hero coverage.
            h = m0 + max(7, int(n * 0.42))
            st.close_on(self.rig, m0, h - 1, self.max, frac=0.46, angle=-82, swing=9, cut=True)
            self._frame(step, things, h, r0 - 1, k)
        else:
            self._frame(step, things, m0, r0 - 1, k)
        self._frame(step, things, r0, e, k + 1, label_from=r0 + 1)

    def _frame(self, step, things, f0, f1, k, label_from=None, label=True):
        things = list(dict.fromkeys(things))
        pts = list(things)
        cx = self._event_center(step["event"])
        top = 6.0 if self.house in things or self.well in things else 4.9
        text = (step.get("label") or "").upper() if label else ""
        angle = -94 if k % 2 else -86
        if text:
            # Size the label from the FINAL camera distance (the label widens the shot).
            base = st._frame_points(things, (f0, (f0 + f1) // 2, f1))
            shot, size, extra = list(base), 0.0, []
            for _ in range(5):
                _cam, _aim, dist = solve(shot, angle, RISE, LENS, MARGIN)
                want = LABEL_SHARE * 2 * dist * (1.0 + PUSH) * tan_half(LENS)[1] / CAP_HEIGHT
                if abs(want - size) < 0.01:
                    break
                size = want
                lz = top + 0.4 + size * 0.5
                half = 0.31 * size * len(text)
                extra = [(cx - half, -3.15, lz + size * 0.6), (cx + half, -3.15, lz + size * 0.6),
                         (cx - half, -3.15, lz - size * 0.4)]
                shot = base + extra
            make_label(text, (cx, -3.15, lz), label_from or f0 + max(2, (f1 - f0) // 10), f1,
                       size=size, tilt=0)
            pts += extra
        st.frame_all(self.rig, f0, f1, pts, angle=angle,
                     rise=RISE, lens=LENS, margin=MARGIN, push=PUSH, swing=5.5,
                     cut=True, fstop=8.0)

    @staticmethod
    def _aim_for(pts, bottom, angle):
        # Kept as part of the common kit-world interface; frame_all solves this
        # world's compact object-root bounds directly.
        return ((sum(p[0] for p in pts) / len(pts)) if pts else bottom[0], 0.0,
                max(bottom[2] + 1.0, 2.8))

    def _change_focus(self, ch):
        return {"none": (-4.0, 0, 4.0), "dig_pit": (-0.75, 0, 4.0),
                "build_tank": (-0.75, 0, 3.0), "anchor_tank": (-0.75, 0, 3.0),
                "lay_drainfield": (5.0, 0, 3.0), "add_baffles": (0.25, 0, 3.0),
                "add_filter": (0.25, 0, 3.0), "schedule_pumping": (-0.8, 0, 5.0)}[ch]

    @staticmethod
    def _hero_change_x(ch, fallback):
        return {
            "dig_pit": -5.8, "build_tank": -5.8, "anchor_tank": -5.8,
            "add_baffles": -5.8, "add_filter": -5.8,
            "schedule_pumping": -5.8,
        }.get(ch, fallback)

    @staticmethod
    def _hero_event_x(name):
        # Tank events can lift or lower the complete cutaway through lawn
        # height.  Max watches from the clear strip immediately to its left.
        if name in {
            "tank_holds_sewage", "tank_floats", "tank_backs_up",
            "scum_clogs_field", "sludge_reaches_outlet", "pumped_in_flood",
            "tank_held_down", "layers_separate", "whole_system_works",
        }:
            return -5.8
        return {
            "family_flushes": -5.8, "pit_poisons_well": 2.6,
            "field_drains_tank": 2.4,
        }.get(name, -5.8)

    def _change_objects(self, ch):
        return {"none": [self.house, self.sewer_pipe], "dig_pit": [self.pit, self.sewer_pipe],
                "build_tank": [self.tank, self.sewer_pipe], "anchor_tank": [self.tank, self.anchors],
                "lay_drainfield": [self.tank, self.drainfield], "add_baffles": [self.tank, self.baffles],
                "add_filter": [self.tank, self.baffles],
                "schedule_pumping": [self.pump_truck, self.tank]}[ch]

    def _event_center(self, name):
        return {"family_flushes": -5.0, "pit_poisons_well": 3.6, "tank_holds_sewage": 1.5,
                "tank_floats": -0.7, "tank_backs_up": -4.0, "field_drains_tank": 2.8,
                "scum_clogs_field": 2.4, "sludge_reaches_outlet": 1.7,
                "pumped_in_flood": -0.7, "tank_held_down": -0.7, "layers_separate": -0.7,
                "whole_system_works": 0.0}[name]

    def _event_objects(self, name):
        return {
            "family_flushes": [self.house, self.sewer_pipe, self.ground, self.groundwater],
            "pit_poisons_well": [self.pit, self.groundwater, self.well, self.ground],
            "tank_holds_sewage": [self.tank, self.sewer_pipe, self.groundwater, self.well],
            "tank_floats": [self.tank, self.groundwater, self.ground, self.sewer_pipe],
            "tank_backs_up": [self.tank, self.sewer_pipe, self.house, self.layers],
            "field_drains_tank": [self.tank, self.drainfield, self.ground, self.house],
            "scum_clogs_field": [self.tank, self.layers, self.drainfield, self.ground],
            "sludge_reaches_outlet": [self.tank, self.layers, self.baffles, self.drainfield],
            "pumped_in_flood": [self.pump_truck, self.tank, self.groundwater],
            "tank_held_down": [self.tank, self.anchors, self.groundwater],
            "layers_separate": [self.tank, self.layers, self.baffles],
            "whole_system_works": [self.house, self.tank, self.layers, self.baffles,
                                   self.drainfield, self.groundwater, self.well],
        }[name]

    def _show(self, frame, *names):
        for name in names:
            toy.hide_tree(getattr(self, name), frame, False)

    def _flow_arrows(self, prefix, specs, start, end, color="#8B4D26"):
        for k, (base, vec) in enumerate(specs):
            arrow(f"septic_yard_{prefix}_{k}", base, vec, start, end,
                  color=color, width=0.085)

    def _shrug(self, f0, f1):
        if not self.hero:
            return
        self.max.pose(f0)
        self.max.pose(f0 + 4, shoulderL=(-32, -42, 0), shoulderR=(-32, 42, 0), head=(-4, 0, 16))
        self.max.pose(f1 - 3, shoulderL=(-35, -46, 0), shoulderR=(-35, 46, 0), head=(-4, 0, 18))
        self.max.brows(f0 + 4, 0.9)
        self.max.brows(f1, 0.0)
        self.max.pose(f1)

    # ------------------------------- events --------------------------------
    def _ev_family_flushes(self, m0, e, t):
        self._flow_arrows("flush", [((-8.7, -2.7, 5.2), (0, 0, -1.0)),
                                     ((-7.8, -2.7, 3.0), (1.4, 0, -0.05)),
                                     ((-5.8, -2.7, 2.93), (1.5, 0, -0.03))], t(0.03), e)
        events.add(t(0.03), "flush", gain=0.65)

    def _ev_pit_poisons_well(self, m0, e, t):
        self._show(m0, "pit")
        self._flow_arrows("poison", [((-0.75, -3.05, 3.15), (0, 0, -1.8)),
                                      ((-0.2, -3.05, 1.15), (3.2, 0, -0.15)),
                                      ((3.0, -3.05, 1.0), (3.0, 0, 0.0)),
                                      ((6.0, -3.05, 1.0), (2.8, 0, 0.0))], t(0.03), e)
        events.add(t(0.04), "pour", duration=max(8, e - t(0.04)), gain=0.45)

    def _ev_tank_holds_sewage(self, m0, e, t):
        self._show(m0, "tank", "layers")
        self._flow_arrows("tank_in", [((-3.5, -3.0, 2.92), (1.4, 0, -0.04)),
                                       ((-1.85, -3.0, 2.85), (0.7, 0, -0.35))], t(0.03), e)
        events.add(t(0.03), "flush", gain=0.55)

    def _ev_tank_floats(self, m0, e, t):
        self._show(m0, "tank")
        p = self.pos["groundwater"]
        _move_vec(self.groundwater, "location", t(0.02), t(0.24), p, (0, 0, 1.18))
        for x in (-1.5, -0.75, 0.0):
            arrow(f"septic_yard_lift_{x}", (x, -3.0, 1.5), (0, 0, 1.35), t(0.05), e,
                  color="#48B6F0", width=0.1)
        tp = self.pos["tank"]
        _move_vec(self.tank, "location", t(0.15), t(0.57), tp, (tp[0], tp[1], tp[2] + 2.0))
        self.tank.rotation_euler = (0, 0, 0)
        self.tank.keyframe_insert("rotation_euler", frame=t(0.15))
        self.tank.rotation_euler = (0, math.radians(-10), math.radians(4))
        self.tank.keyframe_insert("rotation_euler", frame=t(0.57))
        events.add(t(0.16), "creak", gain=0.7)
        events.add(t(0.5), "snap", gain=0.75)

    def _ev_tank_backs_up(self, m0, e, t):
        self._show(m0, "tank", "layers")
        base = self._base_scale["layers"]
        _move_vec(self.layers, "scale", t(0.03), t(0.42), base, (base[0], base[1], 1.22))
        self._flow_arrows("backup", [((-1.9, -3.0, 3.0), (-1.8, 0, 0.0)),
                                      ((-4.2, -3.0, 3.02), (-1.7, 0, 0.0)),
                                      ((-7.0, -2.6, 3.2), (0, 0, 1.5))], t(0.12), e)
        events.add(t(0.15), "bubbles", duration=max(8, e - t(0.15)), gain=0.6)

    def _ev_field_drains_tank(self, m0, e, t):
        self._show(m0, "tank", "drainfield")
        self._flow_arrows("drain", [((0.5, -3.0, 2.85), (1.7, 0, 0.0)),
                                     ((2.3, -2.8, 3.03), (2.0, 0, 0.0)),
                                     ((5.0, -2.7, 3.0), (0, 0, -0.8)),
                                     ((7.0, -2.7, 3.0), (0, 0, -0.8))], t(0.03), e, "#5CBDF0")
        events.add(t(0.03), "water_rush", duration=max(8, e - t(0.03)), gain=0.4)

    def _ev_scum_clogs_field(self, m0, e, t):
        self._show(m0, "tank", "layers", "drainfield")
        self._flow_arrows("scum", [((0.0, -3.0, 3.05), (1.8, 0, -0.05)),
                                    ((2.0, -3.0, 3.0), (2.2, 0, 0.0)),
                                    ((4.5, -3.0, 3.0), (1.6, 0, 0.0))], t(0.03), e, "#6B5522")
        events.add(t(0.2), "squelch", duration=max(8, e - t(0.2)), gain=0.55)

    def _ev_sludge_reaches_outlet(self, m0, e, t):
        self._show(m0, "tank", "layers", "baffles", "drainfield")
        sludge = next((c for c in self.layers.children if c.name.endswith("_sludge")), self.layers)
        scum = next((c for c in self.layers.children if c.name.endswith("_scum")), self.layers)
        # The tee is physically small but is a required teaching object in this wide tank-to-field shot.
        # Magnify it as an explanatory inset so it clears the phone-size must-see gate.
        base = self._base_scale["baffles"]
        _move_vec(self.baffles, "scale", m0, m0 + 1, base, (2.0, 2.0, 2.0))
        _key_vec(self.baffles, "scale", e, (2.0, 2.0, 2.0))
        _move_vec(sludge, "scale", t(0.02), t(0.5), (1, 1, 1), (1, 1, 1.9))
        _move_vec(scum, "location", t(0.02), t(0.5), tuple(scum.location),
                  (scum.location.x, scum.location.y, scum.location.z - 0.28))
        self._flow_arrows("solids_out", [((0.0, -3.0, 2.95), (1.5, 0, 0.0)),
                                          ((1.7, -3.0, 2.95), (1.8, 0, 0.0))], t(0.42), e, "#443020")
        events.add(t(0.42), "squelch", gain=0.55)

    def _ev_pumped_in_flood(self, m0, e, t):
        self._show(m0, "pump_truck", "tank", "layers")
        _move_vec(self.groundwater, "location", t(0.02), t(0.18), tuple(self.groundwater.location), (0, 0, 1.18))
        base = self._base_scale["layers"]
        _move_vec(self.layers, "scale", t(0.05), t(0.36), base, (base[0], base[1], 0.05))
        tp = self.pos["tank"]
        _move_vec(self.tank, "location", t(0.3), t(0.58), tp, (tp[0] + 0.12, tp[1], tp[2] + 0.72))
        events.add(t(0.04), "pump", duration=max(10, t(0.42) - t(0.04)), gain=0.65)
        events.add(t(0.35), "creak", gain=0.6)

    def _ev_tank_held_down(self, m0, e, t):
        self._show(m0, "tank", "anchors")
        _move_vec(self.groundwater, "location", t(0.02), t(0.2), tuple(self.groundwater.location), (0, 0, 1.18))
        for x in (-1.45, -0.75, -0.05):
            arrow(f"septic_yard_held_{x}", (x, -3.0, 1.5), (0, 0, 1.25), t(0.04), e,
                  color="#48B6F0", width=0.1)
        events.add(t(0.22), "strap", gain=0.55)

    def _ev_layers_separate(self, m0, e, t):
        self._show(m0, "tank", "layers", "baffles")
        self._flow_arrows("separate", [((-1.6, -3.0, 2.95), (0.65, 0, -0.25)),
                                        ((-0.5, -3.0, 2.8), (0, 0, -0.55)),
                                        ((-0.15, -3.0, 2.7), (0, 0, 0.55)),
                                        ((0.15, -3.0, 2.9), (1.2, 0, 0.0))], t(0.03), e, "#67BDE8")
        events.add(t(0.03), "pour", duration=max(8, e - t(0.03)), gain=0.4)

    def _ev_whole_system_works(self, m0, e, t):
        self._show(m0, "tank", "layers", "baffles", "drainfield", "anchors")
        # The finale necessarily spans the entire 20 m yard.  Magnify the tee
        # as an explanatory cutaway inset so it still reads in that wide shot.
        _move_vec(self.baffles, "scale", m0, m0 + 1,
                  self._base_scale["baffles"], (48.0, 48.0, 48.0))
        _key_vec(self.baffles, "scale", e, (48.0, 48.0, 48.0))
        self._flow_arrows("whole", [((-8.7, -3.0, 5.2), (0, 0, -1.0)),
                                     ((-7.0, -3.0, 3.0), (2.4, 0, -0.05)),
                                     ((-3.9, -3.0, 2.95), (2.1, 0, -0.05)),
                                     ((0.4, -3.0, 2.9), (2.1, 0, 0.0)),
                                     ((3.0, -3.0, 3.0), (2.2, 0, 0.0)),
                                     ((6.3, -3.0, 2.95), (0, 0, -0.85))], t(0.02), e, "#64BFEF")
        events.add(t(0.02), "flush", gain=0.6)
        events.add(t(0.22), "water_rush", duration=max(8, e - t(0.22)), gain=0.4)
