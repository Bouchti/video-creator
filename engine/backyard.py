"""
Backyard set with construction STATES — the world evolves across a video.

The pool site is a rectangular pit whose state is animated over time:
grass → staked outline → dug pit (depth grows, dirt pile grows) → rebar cage
appears bar by bar → concrete shell sprayed (walls turn grey) → tiled rim →
water fills. The same set is used in every shot, so continuity is guaranteed.

Coordinates: pit centred at PIT_CENTER, long side along X. Z up, ground at 0.
"""
import math
import random

import bpy
from mathutils import Vector

from engine import events, toy

R = math.radians
PIT_CENTER = Vector((0.0, 1.2, 0.0))
PIT_W, PIT_L = 2.4, 4.0          # width (Y), length (X) in metres
PIT_DEPTH = 1.6
PIT_STRIPS = 3                   # soil columns the excavator removes (west → east)


def _key(obj, frame, **props):
    for name, value in props.items():
        setattr(obj, name, value)
        obj.keyframe_insert(name, frame=frame)


def _hide(obj, frame, hidden):
    """Keyframed visibility (render + viewport)."""
    obj.hide_render = hidden
    obj.hide_viewport = hidden
    obj.keyframe_insert("hide_render", frame=frame)
    obj.keyframe_insert("hide_viewport", frame=frame)


def _appear(obj, frame, frames=8, final_scale=None):
    """Pop an object into existence with a little overshoot."""
    final = Vector(final_scale or obj.scale)
    _hide(obj, 0, True)
    _hide(obj, frame, False)
    _key(obj, frame, scale=final * 0.01)
    _key(obj, frame + int(frames * 0.7), scale=final * 1.08)
    _key(obj, frame + frames, scale=final)


class Backyard:
    def __init__(self, seed: int = 7):
        self.rnd = random.Random(seed)
        self.m = {
            "grass": toy.noise_material("grass", toy.srgb("#35702A"), toy.srgb("#4A8834"), scale=30, bump=0.4),
            "dirt": toy.noise_material("dirt", toy.srgb("#6B4428"), toy.srgb("#8A5A36"), scale=14, bump=0.8),
            "concrete": toy.noise_material("concrete", toy.srgb("#7E7D78"), toy.srgb("#96958F"),
                                           scale=25, roughness=0.9, bump=0.3),
            "wood": toy.noise_material("wood", toy.srgb("#B07A45"), toy.srgb("#C9905A"), scale=8, bump=0.2),
            "white": toy.material("paint_white", toy.srgb("#F4F1EA"), roughness=0.6),
            "roof": toy.material("roof", toy.srgb("#B5462E"), roughness=0.55),
            "window": toy.material("window", toy.srgb("#9FD3F2"), roughness=0.05, coat=1.0),
            "leaf": toy.material("leaf", toy.srgb("#3E9B3A"), roughness=0.7),
            "leaf2": toy.material("leaf2", toy.srgb("#56B348"), roughness=0.7),
            "trunk": toy.material("trunk", toy.srgb("#7A5230"), roughness=0.8),
            "steel": toy.material("rebar", toy.srgb("#8C4A2F"), roughness=0.5, metallic=0.6),
            "tile": toy.material("tile", toy.srgb("#2E8FD6"), roughness=0.15, coat=0.8),
            "coping": toy.material("coping", toy.srgb("#E9E2D3"), roughness=0.5),
            "string": toy.material("string", toy.srgb("#FF3B30"), roughness=0.5),
            "water": self._water_material(),
        }
        self._ground()
        self._house()
        self._fence()
        self._trees()
        self._pit()

    # ------------------- STATIC SET -------------------

    @staticmethod
    def _water_material():
        mat = toy.material("water", toy.srgb("#3FB7E8"), roughness=0.03, transmission=0.85, ior=1.33)
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "DITHERED"
        return mat

    def _ground(self):
        # Ground with a rectangular opening for the pit: four slabs around it.
        cx, cy = PIT_CENTER.x, PIT_CENTER.y
        hw, hl, big = PIT_W / 2, PIT_L / 2, 30
        g = self.m["grass"]
        toy.box("ground_n", (big * 2, big, 0.3), (cx, cy + hw + big / 2, -0.15), mat=g, bevel=0)
        toy.box("ground_s", (big * 2, big, 0.3), (cx, cy - hw - big / 2, -0.15), mat=g, bevel=0)
        toy.box("ground_e", (big, PIT_W, 0.3), (cx + hl + big / 2, cy, -0.15), mat=g, bevel=0)
        toy.box("ground_w", (big, PIT_W, 0.3), (cx - hl - big / 2, cy, -0.15), mat=g, bevel=0)
        # Real 3D grass: tufts scattered on thin emitter planes around the site.
        tuft = self._grass_tuft()
        for name, size, loc in (
            ("grass_n", (16, 7.0), (cx, cy + hw + 3.5)),
            ("grass_s", (16, 7.5), (cx, cy - hw - 3.75)),
            ("grass_e", (6.0, PIT_W), (cx + hl + 3.0, cy)),
            ("grass_w", (6.0, PIT_W), (cx - hl - 3.0, cy)),
        ):
            self._scatter(name, size, loc, tuft, density=900)

    def _grass_tuft(self):
        """One clump of 7 tapered, bent blades (instanced thousands of times)."""
        import bmesh
        mesh = bpy.data.meshes.new("tuft")
        bm = bmesh.new()
        rnd = random.Random(5)
        for b in range(7):
            ang = rnd.uniform(0, 2 * math.pi)
            lean = rnd.uniform(0.15, 0.45)
            h = rnd.uniform(0.07, 0.13)
            w = 0.008
            dx, dy = math.cos(ang), math.sin(ang)
            px, py = -dy * w, dx * w
            base = Vector((rnd.uniform(-0.02, 0.02), rnd.uniform(-0.02, 0.02), 0))
            mid = base + Vector((dx * lean * h * 0.4, dy * lean * h * 0.4, h * 0.55))
            tip = base + Vector((dx * lean * h, dy * lean * h, h))
            v = [bm.verts.new(base + Vector((px, py, 0))), bm.verts.new(base - Vector((px, py, 0))),
                 bm.verts.new(mid - Vector((px, py, 0)) * 0.7), bm.verts.new(mid + Vector((px, py, 0)) * 0.7),
                 bm.verts.new(tip)]
            bm.faces.new((v[0], v[1], v[2], v[3]))
            bm.faces.new((v[3], v[2], v[4]))
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new("tuft", mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.data.materials.append(toy.material("blade", toy.srgb("#4C8F33"), roughness=0.6))
        obj.location = (0, 0, -100)  # the template itself stays out of view
        return obj

    def _scatter(self, name, size, loc, instance, density=800, parent_obj=None):
        bpy.ops.mesh.primitive_plane_add(size=1, location=(loc[0], loc[1], 0.002))
        em = bpy.context.active_object
        em.name = name
        em.scale = (size[0], size[1], 1)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        em.data.materials.append(self.m["grass"])
        ps_mod = em.modifiers.new(f"{name}_ps", "PARTICLE_SYSTEM")
        ps = ps_mod.particle_system.settings
        ps.type = "HAIR"
        ps.count = int(size[0] * size[1] * density)
        ps.hair_length = 1.0
        ps.render_type = "OBJECT"
        ps.instance_object = instance
        ps.particle_size = 1.0
        ps.size_random = 0.6
        ps.use_rotations = True
        ps.rotation_mode = "NOR"
        ps.phase_factor_random = 2.0
        ps.use_advanced_hair = True
        # Render only the tufts. The emitter plane sits 2 mm above the ground slab with its own
        # noise pattern, so rendering it z-fights with the lawn (shimmer at a distance).
        if hasattr(em, "show_instancer_for_render"):
            em.show_instancer_for_render = False
        if hasattr(ps, "use_render_emitter"):
            ps.use_render_emitter = False
        em.particle_systems[0].seed = len(name) * 7
        if parent_obj is not None:
            em.parent = parent_obj
        return em

    def _grass_tuft_ref(self):
        return bpy.data.objects["tuft"]

    def _house(self):
        hx, hy = -1.0, 9.0
        toy.box("house", (9, 5, 4.2), (hx, hy, 2.1), mat=self.m["white"], bevel=0.05)
        roof = toy.box("roof", (9.6, 5.8, 0.25), (hx, hy, 4.9), mat=self.m["roof"], bevel=0.05)
        roof.scale = (1, 1, 1)
        for i, ry in enumerate((-1, 1)):
            toy.box(f"roof_slope{i}", (9.8, 3.4, 0.22), (hx, hy + 1.35 * ry, 5.2), mat=self.m["roof"],
                    bevel=0.04, rotation=(R(-30 * ry), 0, 0))
        for i, wx in enumerate((-3.5, -1.5, 1.5)):
            toy.box(f"win{i}", (1.1, 0.1, 1.2), (hx + wx, hy - 2.52, 2.4), mat=self.m["window"], bevel=0.02)
            toy.box(f"winframe{i}", (1.3, 0.08, 1.4), (hx + wx, hy - 2.49, 2.4), mat=self.m["wood"], bevel=0.02)
        toy.box("door", (1.1, 0.1, 2.2), (hx + 3.3, hy - 2.52, 1.1), mat=toy.material(
            "door", toy.srgb("#2E6FB0"), roughness=0.4, coat=0.5), bevel=0.03)

    def _fence(self):
        for side in (-1, 1):
            x = 7.5 * side
            for i in range(26):
                y = -5 + i * 0.5
                toy.box(f"picket_{side}_{i}", (0.08, 0.4, 1.3), (x, y, 0.65), mat=self.m["wood"], bevel=0.02)
            toy.box(f"rail_{side}", (0.06, 13, 0.1), (x - 0.06 * side, 1.25, 0.95), mat=self.m["wood"], bevel=0)

    def _trees(self):
        for i, (x, y, s) in enumerate(((-6.0, 5.5, 1.2), (5.8, 6.2, 1.0), (6.3, -3.5, 0.9), (-6.2, -2.5, 1.1))):
            toy.cylinder(f"trunk{i}", 0.18 * s, 2.0 * s, (x, y, 1.0 * s), mat=self.m["trunk"])
            for k in range(3):
                off = Vector((self.rnd.uniform(-0.5, 0.5), self.rnd.uniform(-0.4, 0.4), self.rnd.uniform(-0.2, 0.4)))
                toy.sphere(f"crown{i}_{k}", (0.9 + 0.3 * k % 2) * s, Vector((x, y, 2.6 * s)) + off * s,
                           mat=self.m["leaf"] if k % 2 else self.m["leaf2"])

    # ------------------- PIT + STATES -------------------

    def _pit(self):
        """The hole is built in final shape and FILLED with soil columns, which digging removes.

        No two visible faces may share a plane (that z-fights = flicker): the dirt walls sit 5 cm
        INSIDE the opening (their back faces hide against the ground slabs) and stop 5 mm below the
        lawn; each soil column is capped by its own grass sod and owns its slice of the pit."""
        c = PIT_CENTER
        hw, hl = PIT_W / 2, PIT_L / 2
        bottom, top = -PIT_DEPTH - 0.1, -0.005
        h, zc = top - bottom, (top + bottom) / 2
        dirt = self.m["dirt"]
        self.walls = [
            toy.box("wall_n", (PIT_L, 0.05, h), (c.x, c.y + hw - 0.025, zc), mat=dirt, bevel=0),
            toy.box("wall_s", (PIT_L, 0.05, h), (c.x, c.y - hw + 0.025, zc), mat=dirt, bevel=0),
            toy.box("wall_e", (0.05, PIT_W - 0.1, h), (c.x + hl - 0.025, c.y, zc), mat=dirt, bevel=0),
            toy.box("wall_w", (0.05, PIT_W - 0.1, h), (c.x - hl + 0.025, c.y, zc), mat=dirt, bevel=0),
        ]
        # Soil columns (west → east), each topped by a grass sod with real tufts.
        self.col_bottom = -PIT_DEPTH - 0.12
        self.columns = []
        n = PIT_STRIPS
        for i in range(n):
            x0 = c.x - hl + PIT_L * i / n
            x1 = c.x - hl + PIT_L * (i + 1) / n
            col = toy.box(f"soil_col{i}", (x1 - x0, PIT_W, -0.04 - self.col_bottom),
                          ((x0 + x1) / 2, c.y, (-0.04 + self.col_bottom) / 2), mat=dirt, bevel=0)
            sod = toy.box(f"sod{i}", (x1 - x0, PIT_W, 0.04), ((x0 + x1) / 2, c.y, -0.02), mat=self.m["grass"],
                          bevel=0)
            tufts = self._scatter(f"grass_sod{i}", (x1 - x0, PIT_W), ((x0 + x1) / 2, c.y),
                                  self._grass_tuft_ref(), density=900)
            self.columns.append({"col": col, "sod": sod, "tufts": tufts, "x": (x0 + x1) / 2,
                                 "h0": -0.04 - self.col_bottom, "top": -0.04})
        # Concrete shell: same geometry slightly inside, revealed by the "spray" step.
        self.shell = []
        for name, size, loc in (
            ("shell_n", (PIT_L - 0.1, 0.06, PIT_DEPTH), (c.x, c.y + hw - 0.03, -PIT_DEPTH / 2)),
            ("shell_s", (PIT_L - 0.1, 0.06, PIT_DEPTH), (c.x, c.y - hw + 0.03, -PIT_DEPTH / 2)),
            ("shell_e", (0.06, PIT_W - 0.1, PIT_DEPTH), (c.x + hl - 0.03, c.y, -PIT_DEPTH / 2)),
            ("shell_w", (0.06, PIT_W - 0.1, PIT_DEPTH), (c.x - hl + 0.03, c.y, -PIT_DEPTH / 2)),
            ("shell_floor", (PIT_L - 0.1, PIT_W - 0.1, 0.06), (c.x, c.y, -PIT_DEPTH + 0.03)),
        ):
            s = toy.box(name, size, loc, mat=self.m["concrete"], bevel=0)
            _hide(s, 0, True)
            self.shell.append(s)
        # Spoil pile: placed by the film where the excavator dumps (see spoil_pile).
        self.pile = None

    def stakes(self, frame: int, frames: int = 30):
        """Corner stakes pop in one by one, then the red string line draws around them."""
        c, hw, hl = PIT_CENTER, PIT_W / 2, PIT_L / 2
        corners = [(c.x - hl, c.y - hw), (c.x + hl, c.y - hw), (c.x + hl, c.y + hw), (c.x - hl, c.y + hw)]
        step = frames // 6
        for i, (x, y) in enumerate(corners):
            st = toy.box(f"stake{i}", (0.06, 0.06, 0.55), (x, y, 0.2), mat=self.m["wood"], bevel=0.01)
            _appear(st, frame + i * step, frames=6)
        for i in range(4):
            (x0, y0), (x1, y1) = corners[i], corners[(i + 1) % 4]
            length = math.hypot(x1 - x0, y1 - y0)
            line = toy.box(f"string{i}", (length, 0.015, 0.015), ((x0 + x1) / 2, (y0 + y1) / 2, 0.4),
                           mat=self.m["string"], bevel=0, rotation=(0, 0, math.atan2(y1 - y0, x1 - x0)))
            _appear(line, frame + 4 * step + i * 3, frames=6)
        self.string_objs = [o for o in bpy.data.objects if o.name.startswith(("string", "stake"))]

    def remove_stakes(self, frame: int):
        for o in getattr(self, "string_objs", []):
            _hide(o, frame, True)

    def dig_plan(self, passes: int = 2):
        """Bite order: a shallow pass over every column, then a deep pass back (snake order).
        Returns [(column index, new top z)]."""
        n = len(self.columns)
        plan = []
        for p in range(passes):
            depth = -0.04 - (PIT_DEPTH + 0.005 - 0.04) * (p + 1) / passes
            order = range(n) if p % 2 == 0 else range(n - 1, -1, -1)
            plan.extend((i, depth) for i in order)
        return plan

    def column_top(self, i: int, frame: int, top: float):
        col = self.columns[i]
        h = top - self.col_bottom
        _key(col["col"], frame, scale=Vector((1, 1, h / col["h0"])),
             location=Vector((col["x"], PIT_CENTER.y, (top + self.col_bottom) / 2)))
        col["top"] = top

    def bite(self, i: int, bite_frame: int, curl_frame: int, new_top: float):
        """The bucket bites column i: its sod vanishes as the teeth go in, then the soil drops to
        `new_top` while the bucket curls (dust puffs cover the change)."""
        col = self.columns[i]
        if col["sod"] is not None:
            for o in (col["sod"], col["tufts"]):
                _hide(o, 0, False)
                _hide(o, bite_frame + 1, True)
            col["sod"] = None
        self.column_top(i, bite_frame, col["top"])
        self.column_top(i, curl_frame + 2, new_top)

    def spoil_pile(self, location, dumps: list, final_scale=(1.3, 1.15, 0.8)):
        """Spoil heap that grows with every dump (frames), from a small mound to `final_scale`.
        Kept clear of the ground plane: it is never a flat disc lying ON the lawn (z-fight)."""
        self.pile = toy.sphere("dirt_pile", 1.0, location, scale=(0.3, 0.3, 0.18), mat=self.m["dirt"])
        _hide(self.pile, 0, True)
        _hide(self.pile, dumps[0] + 1, False)
        final = Vector(final_scale)
        _key(self.pile, dumps[0], scale=Vector((0.3, 0.3, 0.18)))
        for k, f in enumerate(dumps):
            frac = ((k + 1) / len(dumps)) ** 0.6
            _key(self.pile, f + 5, scale=Vector((max(0.3, final.x * frac), max(0.3, final.y * frac),
                                                  max(0.18, final.z * frac))))
        return self.pile

    def haul_away(self, frame: int):
        """The spoil is trucked off between beats."""
        if self.pile is not None:
            _hide(self.pile, frame, True)

    def rebar(self, start: int, end: int, spacing: float = 0.25):
        """Steel cage tied on a ~25 cm grid: floor mat, wall verticals, then horizontal wall rings."""
        c, hw, hl = PIT_CENTER, PIT_W / 2 - 0.12, PIT_L / 2 - 0.12
        z = -PIT_DEPTH + 0.12
        steel = self.m["steel"]
        nx = int(round(2 * hl / spacing)) + 1
        ny = int(round(2 * hw / spacing)) + 1
        xs = [c.x - hl + i * 2 * hl / (nx - 1) for i in range(nx)]
        ys = [c.y - hw + i * 2 * hw / (ny - 1) for i in range(ny)]
        floor, walls, rings = [], [], []
        for i, x in enumerate(xs):
            floor.append(toy.cylinder(f"rebar_x{i}", 0.016, 2 * hw, (x, c.y, z), rotation=(R(90), 0, 0),
                                      mat=steel, vertices=8))
        for i, y in enumerate(ys):
            floor.append(toy.cylinder(f"rebar_y{i}", 0.016, 2 * hl, (c.x, y, z + 0.035), rotation=(0, R(90), 0),
                                      mat=steel, vertices=8))
        vh = PIT_DEPTH - 0.15
        for i, x in enumerate(xs):
            for side, y in (("s", c.y - hw), ("n", c.y + hw)):
                walls.append(toy.cylinder(f"rebar_v{side}{i}", 0.016, vh, (x, y, -PIT_DEPTH / 2), mat=steel,
                                          vertices=8))
        for i, y in enumerate(ys[1:-1]):
            for side, x in (("w", c.x - hl), ("e", c.x + hl)):
                walls.append(toy.cylinder(f"rebar_v{side}{i}", 0.016, vh, (x, y, -PIT_DEPTH / 2), mat=steel,
                                          vertices=8))
        for k, rz in enumerate((-0.35, -0.75, -1.15)):
            for side, y in (("s", c.y - hw + 0.03), ("n", c.y + hw - 0.03)):
                rings.append(toy.cylinder(f"rebar_r{side}{k}", 0.016, 2 * hl, (c.x, y, rz), rotation=(0, R(90), 0),
                                          mat=steel, vertices=8))
            for side, x in (("w", c.x - hl + 0.03), ("e", c.x + hl - 0.03)):
                rings.append(toy.cylinder(f"rebar_r{side}{k}", 0.016, 2 * hw, (x, c.y, rz), rotation=(R(90), 0, 0),
                                          mat=steel, vertices=8))
        bars = floor + walls + rings
        span = max(1, end - start - 8)
        for k, b in enumerate(bars):
            f = start + int(span * k / len(bars))
            _appear(b, f, frames=6)
            if k % 4 == 0:
                events.add(f, "clink", gain=0.6)
        self.bars = bars

    def gravel(self, start: int, end: int):
        """Compacted gravel base spreads across the floor from the east end."""
        c = PIT_CENTER
        mat = toy.noise_material("gravel", toy.srgb("#8C857A"), toy.srgb("#B3AB9C"), scale=160, roughness=0.85,
                                 bump=1.0, detail=2.0)
        length = PIT_L - 0.1
        top, thick = -PIT_DEPTH + 0.05, 0.055
        g = toy.box("gravel_bed", (length, PIT_W - 0.1, thick), (c.x, c.y, top - thick / 2), mat=mat, bevel=0)
        east = c.x + length / 2
        _hide(g, 0, True)
        _hide(g, start, False)
        _key(g, start, scale=Vector((0.02, 1, 1)), location=Vector((east - length * 0.01, c.y, g.location.z)))
        _key(g, end, scale=Vector((1, 1, 1)), location=Vector((c.x, c.y, g.location.z)))
        for f in range(start, end, 14):
            events.add(f, "dump", gain=0.35)
        self.gravel_bed = g
        return g

    def utility_marks(self, name: str, color: str, p0, p1, start: int, end: int, flag_every: float = 1.6):
        """Spray-painted dashes + little flags along a buried line, drawn from p0 to p1 between the
        frames (synced to whoever walks it with a paint can)."""
        paint = toy.material(f"mark_{name}", toy.srgb(color), roughness=0.6)
        p0, p1 = Vector(p0), Vector(p1)
        d = p1 - p0
        length = d.length
        ang = math.atan2(d.y, d.x)
        n = int(length / 0.5)
        for k in range(n):
            t = (k + 0.5) / n
            pos = p0 + d * t
            dash = toy.box(f"{name}_dash{k}", (0.36, 0.08, 0.006), (pos.x, pos.y, 0.004), mat=paint, bevel=0,
                           rotation=(0, 0, ang))
            _appear(dash, start + int((end - start) * t), frames=3)
        pole = toy.material("flag_pole", toy.srgb("#EDEDED"), roughness=0.4)
        for k in range(int(length / flag_every) + 1):
            t = min(1.0, k * flag_every / length)
            pos = p0 + d * t + Vector((0, 0.12, 0))
            stick = toy.cylinder(f"{name}_flagpole{k}", 0.006, 0.36, (pos.x, pos.y, 0.18), mat=pole)
            toy.box(f"{name}_flag{k}", (0.11, 0.004, 0.08), (0.055, 0, 0.14), mat=paint, parent=stick, bevel=0)
            _appear(stick, start + int((end - start) * t) + 2, frames=6)
            events.add(start + int((end - start) * t) + 2, "pop", gain=0.3)

    def spray_concrete(self, start: int, end: int):
        """Concrete shell appears wall by wall over the rebar (bars then hidden)."""
        span = end - start
        for k, s in enumerate(self.shell):
            f = start + int(span * k / len(self.shell))
            _hide(s, f, False)
            _key(s, f, scale=Vector((1, 1, 0.05)) if "floor" not in s.name else Vector((0.05, 1, 1)))
            _key(s, f + span // len(self.shell), scale=Vector((1, 1, 1)))
        for b in getattr(self, "bars", []):
            _hide(b, end, True)

    def tiles_and_coping(self, start: int, end: int, plaster_start: int = None, plaster_end: int = None):
        """Blue waterline tiles + cream stone coping around the rim."""
        c, hw, hl = PIT_CENTER, PIT_W / 2, PIT_L / 2
        pieces = []
        for name, size, loc in (
            ("tile_n", (PIT_L - 0.12, 0.02, 0.25), (c.x, c.y + hw - 0.07, -0.14)),
            ("tile_s", (PIT_L - 0.12, 0.02, 0.25), (c.x, c.y - hw + 0.07, -0.14)),
            ("tile_e", (0.02, PIT_W - 0.12, 0.25), (c.x + hl - 0.07, c.y, -0.14)),
            ("tile_w", (0.02, PIT_W - 0.12, 0.25), (c.x - hl + 0.07, c.y, -0.14)),
        ):
            pieces.append(toy.box(name, size, loc, mat=self.m["tile"], bevel=0.005))
        for name, size, loc in (
            ("cope_n", (PIT_L + 0.5, 0.3, 0.08), (c.x, c.y + hw + 0.1, 0.04)),
            ("cope_s", (PIT_L + 0.5, 0.3, 0.08), (c.x, c.y - hw - 0.1, 0.04)),
            ("cope_e", (0.3, PIT_W - 0.1, 0.08), (c.x + hl + 0.1, c.y, 0.04)),   # butts the long sides:
            ("cope_w", (0.3, PIT_W - 0.1, 0.08), (c.x - hl - 0.1, c.y, 0.04)),   # no overlapping tops
        ):
            pieces.append(toy.box(name, size, loc, mat=self.m["coping"], bevel=0.02))
        # Pool-blue plaster lining just inside the concrete shell, revealed first.
        plaster = toy.material("plaster", toy.srgb("#7FD0F0"), roughness=0.35)
        lining = []
        for name, size, loc in (
            ("plaster_n", (PIT_L - 0.14, 0.01, PIT_DEPTH - 0.06), (c.x, c.y + hw - 0.065, -PIT_DEPTH / 2 - 0.03)),
            ("plaster_s", (PIT_L - 0.14, 0.01, PIT_DEPTH - 0.06), (c.x, c.y - hw + 0.065, -PIT_DEPTH / 2 - 0.03)),
            ("plaster_e", (0.01, PIT_W - 0.14, PIT_DEPTH - 0.06), (c.x + hl - 0.065, c.y, -PIT_DEPTH / 2 - 0.03)),
            ("plaster_w", (0.01, PIT_W - 0.14, PIT_DEPTH - 0.06), (c.x - hl + 0.065, c.y, -PIT_DEPTH / 2 - 0.03)),
            ("plaster_floor", (PIT_L - 0.14, PIT_W - 0.14, 0.01), (c.x, c.y, -PIT_DEPTH + 0.065)),
        ):
            lining.append(toy.box(name, size, loc, mat=plaster, bevel=0))
        # Plaster goes on AFTER tiles + coping (real build order) — its own beat when given.
        p0 = plaster_start if plaster_start is not None else start
        p1 = plaster_end if plaster_end is not None else start + 15
        step = (p1 - p0) / len(lining)
        for k, p in enumerate(lining):
            f = p0 + int(step * k)
            _hide(p, 0, True)
            _hide(p, f, False)                     # each panel is troweled on: it spreads, never pops
            grow = Vector((1, 1, 0.03)) if "floor" not in p.name else Vector((0.03, 1, 1))
            _key(p, f, scale=grow)
            _key(p, f + max(6, int(step)), scale=Vector((1, 1, 1)))
        span = max(1, end - start - 8)
        for k, p in enumerate(pieces):
            f = start + 6 + int((span - 6) * k / len(pieces))
            _appear(p, f, frames=8)
            events.add(f, "tile", gain=0.6)

    def fill_water(self, start: int, end: int, level: float = -0.18):
        """Rising water surface with gentle animated waves (subdivided grid + displacement)."""
        c = PIT_CENTER
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=80, y_subdivisions=50, size=1,
                                        location=(c.x, c.y, -PIT_DEPTH + 0.08))
        water = bpy.context.active_object
        water.name = "water"
        water.scale = (PIT_L - 0.14, PIT_W - 0.14, 1)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        water.data.materials.append(self.m["water"])
        water.data.shade_smooth()
        tex = bpy.data.textures.new("water_waves", "CLOUDS")
        tex.noise_scale = 0.35
        drift = toy.empty("water_drift", (0, 0, 0))
        drift.keyframe_insert("location", frame=1)
        drift.location = (1.5 * 6, 0.8 * 6, 0.6 * 6)     # keeps drifting past any film's end (epilogue too)
        drift.keyframe_insert("location", frame=5400)
        toy.set_interpolation(drift, "location", (1,), "LINEAR")
        disp = water.modifiers.new("waves", "DISPLACE")
        disp.texture = tex
        disp.texture_coords = "OBJECT"
        disp.texture_coords_object = drift
        disp.strength = 0.025
        disp.mid_level = 0.5
        _hide(water, 0, True)
        _hide(water, start, False)
        _key(water, start, location=Vector((c.x, c.y, -PIT_DEPTH + 0.08)))
        _key(water, end, location=Vector((c.x, c.y, level)))
        self.water = water
        return water

    def ripple(self, frame: int, at):
        """Circular splash ripple spreading from `at` (Wave modifier on the water)."""
        center = toy.empty("ripple_center", at)
        wave = self.water.modifiers.new("ripple", "WAVE")
        wave.start_position_object = center
        wave.use_normal = False
        wave.height = 0.06
        wave.width = 0.35
        wave.speed = 0.06
        wave.narrowness = 1.2
        wave.time_offset = frame
        wave.lifetime = 60
        wave.damping_time = 40
        wave.falloff_radius = 3.0

    # ------------------- SET DRESSING -------------------

    def dress(self):
        """Details that make the world feel lived-in."""
        rnd = random.Random(11)
        petal = [toy.material(f"petal{i}", toy.srgb(h), roughness=0.5)
                 for i, h in enumerate(("#FF5D8F", "#FFD23F", "#FFFFFF", "#B57BFF", "#FF7A3D"))]
        stem = toy.material("stem", toy.srgb("#3C7D2A"), roughness=0.6)
        bush = toy.material("bush", toy.srgb("#2F7A35"), roughness=0.75)
        bush2 = toy.material("bush2", toy.srgb("#3F9142"), roughness=0.75)
        rock = toy.material("rock", toy.srgb("#8F8B84"), roughness=0.9)
        # Flower bed + bushes along the house.
        for i in range(26):
            x, y = -5.0 + i * 0.36 + rnd.uniform(-0.1, 0.1), 6.15 + rnd.uniform(-0.25, 0.2)
            toy.cylinder(f"stem{i}", 0.012, 0.32, (x, y, 0.16), mat=stem, vertices=6)
            toy.sphere(f"flower{i}", 0.07, (x, y, 0.34), scale=(1, 1, 0.6), mat=petal[i % len(petal)], subdiv=1)
        for i, x in enumerate((-5.4, -3.2, 1.6, 3.6)):
            for k in range(3):
                toy.sphere(f"bush{i}_{k}", 0.42 + 0.12 * k % 2, (x + 0.35 * k - 0.35, 6.6, 0.32 + 0.06 * k),
                           mat=bush if k % 2 else bush2)
        for i in range(9):
            toy.sphere(f"rock{i}", rnd.uniform(0.08, 0.2),
                       (rnd.uniform(-6.5, 6.5), rnd.uniform(-4.5, 5.5), 0.02),
                       scale=(1.2, 1.0, 0.6), mat=rock, subdiv=1)
        # Patio table + chairs + umbrella (west side).
        white = self.m["white"]
        umbrella = toy.material("umbrella", toy.srgb("#E8453C"), roughness=0.5)
        tx, ty = -5.2, 3.6
        toy.cylinder("table_top", 0.5, 0.05, (tx, ty, 0.72), mat=white, bevel=0.01)
        toy.cylinder("table_leg", 0.04, 0.72, (tx, ty, 0.36), mat=white)
        toy.cylinder("umbrella_pole", 0.025, 2.2, (tx, ty, 1.1), mat=white)
        bpy.ops.mesh.primitive_cone_add(radius1=1.2, radius2=0.05, depth=0.45, location=(tx, ty, 2.2), vertices=16)
        u = bpy.context.active_object
        u.name = "umbrella"
        toy._finish(u, umbrella, subdiv=0)
        for k, (dx, dy) in enumerate(((0.85, 0), (-0.85, 0), (0, 0.85))):
            toy.box(f"chair_seat{k}", (0.42, 0.42, 0.05), (tx + dx, ty + dy, 0.45), mat=white, bevel=0.02)
            toy.box(f"chair_back{k}", (0.42, 0.05, 0.45), (tx + dx * 1.25, ty + dy * 1.25 + (0.2 if dy else 0), 0.7),
                    mat=white, bevel=0.02, rotation=(0, 0, math.radians(90 if dx else 0)))
            for lx in (-0.17, 0.17):
                for ly in (-0.17, 0.17):
                    toy.cylinder(f"chair_leg{k}_{lx}_{ly}", 0.018, 0.45, (tx + dx + lx, ty + dy + ly, 0.22), mat=white)
        # Construction props: cones, wheelbarrow, toolbox.
        orange = toy.material("cone_orange", toy.srgb("#FF6A13"), roughness=0.4)
        stripe = toy.material("cone_white", toy.srgb("#FFFFFF"), roughness=0.4)
        for i, (x, y) in enumerate(((3.4, -1.9), (4.7, -0.7), (-3.0, -1.9))):
            bpy.ops.mesh.primitive_cone_add(radius1=0.16, radius2=0.03, depth=0.5, location=(x, y, 0.27), vertices=16)
            cone = bpy.context.active_object
            cone.name = f"cone{i}"
            toy._finish(cone, orange, subdiv=0)
            toy.cylinder(f"cone_stripe{i}", 0.105, 0.07, (x, y, 0.3), mat=stripe)
            toy.box(f"cone_base{i}", (0.36, 0.36, 0.04), (x, y, 0.02), mat=orange, bevel=0.01)
        green = toy.material("barrow_green", toy.srgb("#2E9E5B"), roughness=0.35, coat=0.5)
        steel = toy.material("barrow_steel", toy.srgb("#3A3D42"), roughness=0.4, metallic=0.7)
        wx, wy = -4.4, -0.8   # west lawn, out of the main camera lines
        toy.box("barrow_tub", (0.9, 0.6, 0.32), (wx, wy, 0.5), mat=green, bevel=0.1)
        toy.cylinder("barrow_wheel", 0.18, 0.08, (wx + 0.55, wy, 0.18), rotation=(math.radians(90), 0, 0), mat=steel)
        for side in (-1, 1):
            toy.cylinder(f"barrow_handle{side}", 0.025, 0.9, (wx - 0.6, wy + 0.22 * side, 0.55),
                         rotation=(0, math.radians(80), 0), mat=steel)
        red = toy.material("toolbox_red", toy.srgb("#D8342C"), roughness=0.35, coat=0.6)
        toy.box("toolbox", (0.5, 0.25, 0.25), (2.9, -2.3, 0.13), mat=red, bevel=0.03)
        toy.box("toolbox_handle", (0.3, 0.04, 0.06), (2.9, -2.3, 0.3), mat=steel, bevel=0.01)
        self._clouds()

    def _clouds(self):
        cloud = toy.material("cloud", toy.srgb("#FFFFFF"), roughness=0.9)
        rnd = random.Random(21)
        for i in range(6):
            base = Vector((rnd.uniform(-25, 25), rnd.uniform(25, 45), rnd.uniform(12, 18)))
            root = toy.empty(f"cloud{i}", base)
            for k in range(4):
                toy.sphere(f"cloud{i}_{k}", rnd.uniform(1.6, 2.6),
                           (rnd.uniform(-2.5, 2.5), rnd.uniform(-0.8, 0.8), rnd.uniform(-0.4, 0.6)),
                           scale=(1.3, 1.0, 0.7), mat=cloud, parent=root, subdiv=1)
            root.keyframe_insert("location", frame=1)
            root.location = base + Vector((18, 0, 0))
            root.keyframe_insert("location", frame=5400)
            toy.set_interpolation(root, "location", (1,), "LINEAR")

    def house_details(self):
        hx, hy = -1.0, 9.0
        brick = toy.material("brick", toy.srgb("#A8553A"), roughness=0.8)
        toy.box("chimney", (0.7, 0.7, 1.6), (hx + 2.8, hy + 0.8, 5.6), mat=brick, bevel=0.03)
        gutter = toy.material("gutter", toy.srgb("#EDEDED"), roughness=0.4)
        toy.box("gutter", (9.8, 0.12, 0.1), (hx, hy - 2.95, 4.55), mat=gutter, bevel=0.02)
        for i, wx in enumerate((-3.5, -1.5, 1.5)):
            toy.box(f"flowerbox{i}", (1.2, 0.25, 0.2), (hx + wx, hy - 2.62, 1.72), mat=self.m["wood"], bevel=0.03)
            for k in range(5):
                toy.sphere(f"boxflower{i}_{k}", 0.08, (hx + wx - 0.45 + 0.22 * k, hy - 2.62, 1.9),
                           mat=bpy.data.materials.get(f"petal{k % 5}") or self.m["leaf"], subdiv=1)
        for k in range(3):
            toy.box(f"step{k}", (1.6, 0.35, 0.16), (hx + 3.3, hy - 2.7 - 0.35 * k, 0.24 - 0.08 * k),
                    mat=self.m["coping"], bevel=0.02)
        toy.cylinder("tap", 0.035, 0.18, (hx + 4.2, hy - 2.55, 0.6), rotation=(math.radians(90), 0, 0),
                     mat=toy.material("tap_brass", toy.srgb("#C9A24A"), roughness=0.25, metallic=1.0))

    # ------------------- MORE CONSTRUCTION STAGES -------------------

    def plumbing(self, start: int, end: int):
        """Main drain at the bottom + white PVC lines running to the wall and up to the rim."""
        c, hw, hl = PIT_CENTER, PIT_W / 2, PIT_L / 2
        pvc = toy.material("pvc", toy.srgb("#F2F2EE"), roughness=0.35, coat=0.4)
        grate = toy.material("grate", toy.srgb("#2D3238"), roughness=0.4, metallic=0.5)
        z = -PIT_DEPTH + 0.1
        parts = [toy.cylinder("drain", 0.16, 0.05, (c.x, c.y, -PIT_DEPTH + 0.06), mat=grate, bevel=0.01)]
        parts.append(toy.cylinder("pipe_floor", 0.05, hl - 0.15, (c.x + (hl - 0.15) / 2, c.y, z + 0.02),
                                  rotation=(0, math.radians(90), 0), mat=pvc))
        parts.append(toy.cylinder("pipe_riser", 0.05, PIT_DEPTH - 0.1, (c.x + hl - 0.12, c.y, -PIT_DEPTH / 2),
                                  mat=pvc))
        for i, y in enumerate((c.y - hw * 0.5, c.y + hw * 0.5)):
            parts.append(toy.cylinder(f"return{i}", 0.06, 0.1, (c.x - hl + 0.08, y, -0.45),
                                      rotation=(0, math.radians(90), 0), mat=pvc))
        parts.append(toy.box("skimmer", (0.3, 0.3, 0.22), (c.x + hl - 0.2, c.y - hw + 0.2, -0.12), mat=pvc, bevel=0.03))
        span = max(1, end - start - 10)
        for k, prt in enumerate(parts):
            f = start + int(span * k / len(parts))
            _appear(prt, f, frames=8)
            events.add(f, "pop", gain=0.5)
        self.pipes = parts
        return parts

    def equipment_pad(self):
        """Concrete pad by the east fence with the pump (with spinning fan) and sand filter."""
        pad_x, pad_y = 5.6, 2.6
        conc = self.m["concrete"]
        blue = toy.material("pump_blue", toy.srgb("#2B6CB0"), roughness=0.35, coat=0.6)
        grey = toy.material("filter_grey", toy.srgb("#C9CDD2"), roughness=0.35, coat=0.5)
        toy.box("equip_pad", (1.6, 1.2, 0.12), (pad_x, pad_y, 0.06), mat=conc, bevel=0.02)
        tank = toy.cylinder("filter_tank", 0.32, 0.9, (pad_x - 0.35, pad_y + 0.15, 0.57), mat=grey, bevel=0.05)
        toy.sphere("filter_dome", 0.32, (pad_x - 0.35, pad_y + 0.15, 1.02), scale=(1, 1, 0.45), mat=grey)
        pump = toy.cylinder("pump_motor", 0.17, 0.42, (pad_x + 0.4, pad_y - 0.1, 0.32),
                            rotation=(0, math.radians(90), 0), mat=blue, bevel=0.03)
        fan = toy.empty("pump_fan", (pad_x + 0.63, pad_y - 0.1, 0.32))
        for k in range(3):
            toy.box(f"fan_blade{k}", (0.02, 0.26, 0.05), (0, 0, 0), mat=grey, parent=fan, bevel=0.005,
                    rotation=(math.radians(60 * k), 0, 0))
        pvc = toy.material("pvc", toy.srgb("#F2F2EE"), roughness=0.35, coat=0.4)
        toy.cylinder("equip_pipe", 0.05, 2.4, (pad_x - 1.6, pad_y - 0.1, 0.06), rotation=(0, math.radians(90), 0),
                     mat=pvc)
        self.pump, self.fan = pump, fan
        return pump, fan

    def run_pump(self, start: int, end: int):
        self.fan.keyframe_insert("rotation_euler", frame=start)
        self.fan.rotation_euler.x += math.radians(360 * (end - start) / 6)
        self.fan.keyframe_insert("rotation_euler", frame=end)
        toy.set_interpolation(self.fan, "rotation_euler", (start,), "LINEAR")
        toy.add_noise(self.pump, "location", 2, strength=0.004, scale=1.0)
        events.add(start, "pump", duration=end - start)
