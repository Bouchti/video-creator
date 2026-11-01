"""
A pressurised-water reactor plant at real scale (metres), built from production-quality parts.

    plant = PwrPlant()
    plant.set_events([{"t": 12.0, "type": "rods_in", "unit": 1}, ...])
    plant.pose(phase_deg, t)            # flow phase -> coolant, steam, turbine, pumps; t -> rods, glow, plume

Layout: containment at the origin (primary loop along y = 0 so one lengthwise cut halves the vessel, hot legs
and steam generators), cold legs, pumps and pressuriser on +y (they stay whole in the cut), turbine hall to the
east (+x), cooling tower behind it (+x, +y). All cuts remove y < 0 (the quarter cut only x < 0 and y < 0).
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix

from .. import geo
from .. import materials as M
from ..rigs.flow import Flow

TAU = math.tau


def _at(obj, x=0.0, y=0.0, z=0.0):
    return geo.transform_mesh(obj, Matrix.Translation((x, y, z)))


def _x_cyl(name, r, x0, x1, segs=48, col=None, mat=None, chamfer=0.0):
    c = geo.cylinder(name, r, x0, x1, segs, col, mat, chamfer)
    return geo.transform_mesh(c, Matrix.Rotation(math.radians(90), 4, "Y"))


def _offset(profile, t):
    """Offset a (r, z) profile inward (toward the inside of the solid) by t along its normals. Ends that sit
    off the axis are open: they are pushed past the end so the hollow breaks through."""
    out = []
    n = len(profile)
    for i, (r, z) in enumerate(profile):
        a = profile[max(0, i - 1)]
        b = profile[min(n - 1, i + 1)]
        tr, tz = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(tr, tz) or 1.0
        nr, nz = -tz / ln, tr / ln                      # tangent turned +90 deg: inward for an upward profile
        out.append((max(0.0, r + nr * t), z + nz * t))
    for k, (i, sgn) in enumerate(((0, -1), (n - 1, 1))):
        if profile[i][0] > 0.05:                         # open end
            out[i] = (out[i][0], profile[i][1] + sgn * (t + 0.05))
    return out


def _shell(name, profile_out, thickness, segs=96, col=None, mat=None):
    """A hollow solid of revolution: outer profile (r, z) from bottom to top, walls `thickness` thick
    (measured along the normal, so domes keep their thickness); ends off the axis stay open."""
    prof = list(profile_out)
    if prof[0][0] > 0.05:
        closed_bottom = [(0.0, prof[0][1])]
    else:
        closed_bottom = [(0.0, prof[0][1])]
        prof = prof[1:] if prof[0][0] <= 1e-6 else prof
    outer = geo.lathe(name, closed_bottom + prof + [(0.0, prof[-1][1])], segs, col, mat)
    inner = _offset(profile_out, thickness)
    cut = geo.lathe(name + "_in", [(0.0, inner[0][1])] + inner + [(0.0, inner[-1][1])], segs)
    geo.boolean(outer, cut)
    return outer


def _dome_profile(r, z0, rise, steps=16):
    return [(r * math.cos(a), z0 + rise * math.sin(a)) for a in [math.pi / 2 * k / steps for k in range(steps + 1)]]


def _liquid(name, color, transmission=0.85, rough=0.04):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    b = mat.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = M.hex_rgb(color)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Transmission Weight"].default_value = transmission
    b.inputs["IOR"].default_value = 1.33
    return mat


def _water_volume(name, color="#3f9bff", density=0.35, glow="#2f7dff"):
    """Coolant as a volume: light blue absorption, plus blue emission scaled by the object's 'power'."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    a = nt.nodes.new("ShaderNodeAttribute")
    a.attribute_type = "OBJECT"
    a.attribute_name = "power"
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = M.hex_rgb(color)
    vol.inputs["Density"].default_value = density
    vol.inputs["Emission Color"].default_value = M.hex_rgb(glow)
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = 6.0
    nt.links.new(a.outputs["Fac"], mul.inputs[0])
    nt.links.new(mul.outputs[0], vol.inputs["Emission Strength"])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(vol.outputs["Volume"], out.inputs["Volume"])
    return mat


def _plume_material():
    mat = bpy.data.materials.new("plume")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new("ShaderNodeTexCoord")
    ph = nt.nodes.new("ShaderNodeAttribute")
    ph.attribute_type = "OBJECT"
    ph.attribute_name = "plume_phase"
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.noise_dimensions = "4D"
    noise.inputs["Scale"].default_value = 0.035
    noise.inputs["Detail"].default_value = 6.0
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    nt.links.new(ph.outputs["Fac"], noise.inputs["W"])
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.inputs["From Min"].default_value = 0.45
    ramp.inputs["From Max"].default_value = 0.75
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Value"])
    grad = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], grad.inputs["Vector"])
    fade = nt.nodes.new("ShaderNodeMath")
    fade.operation = "SUBTRACT"
    fade.inputs[0].default_value = 1.0
    nt.links.new(grad.outputs["Z"], fade.inputs[1])
    dens = nt.nodes.new("ShaderNodeMath")
    dens.operation = "MULTIPLY"
    nt.links.new(ramp.outputs["Result"], dens.inputs[0])
    nt.links.new(fade.outputs[0], dens.inputs[1])
    d2 = nt.nodes.new("ShaderNodeMath")
    d2.operation = "MULTIPLY"
    d2.inputs[1].default_value = 0.08
    nt.links.new(dens.outputs[0], d2.inputs[0])
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (0.92, 0.94, 0.97, 1)
    nt.links.new(d2.outputs[0], vol.inputs["Density"])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(vol.outputs["Volume"], out.inputs["Volume"])
    return mat


def _blade_ring(name, x, hub, length, n, col, chord=0.16, thick=0.035, twist=34.0):
    """One turbine stage: n twisted blades around the shaft axis (X) at z = 12, as a single mesh."""
    bm = bmesh.new()
    for q in range(n):
        a = TAU * q / n
        segs = 4
        rows = []
        for k in range(segs + 1):
            r = hub + length * k / segs
            tw = math.radians(twist * (1 - k / segs) + 10)
            c_ = chord * (1 - 0.35 * k / segs)
            ring = []
            for dx, dt in ((-c_ / 2, -thick / 2), (c_ / 2, -thick / 2), (c_ / 2, thick / 2), (-c_ / 2, thick / 2)):
                bx = dx * math.cos(tw) - dt * math.sin(tw)
                bt = dx * math.sin(tw) + dt * math.cos(tw)
                ring.append(bm.verts.new((x + bx, r * math.cos(a) - bt * math.sin(a), 12.0 + r * math.sin(a) +
                                          bt * math.cos(a))))
            rows.append(ring)
        for r0, r1 in zip(rows, rows[1:]):
            for i in range(4):
                bm.faces.new((r0[i], r0[(i + 1) % 4], r1[(i + 1) % 4], r1[i]))
        bm.faces.new(rows[0][::-1])
        bm.faces.new(rows[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = geo.from_bmesh(name, bm, col, M.polished_steel())
    geo.shade(ob, 40)
    return ob


def _points_object(name, pts, col):
    """A vertex cloud used as an instancer (instance_type VERTS): thousands of rods for the price of one."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in pts], [], [])
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    ob.instance_type = "VERTS"
    return ob


class PwrPlant:
    TIMED = True
    STUDIO = {"floor_z": -0.05, "center": (60.0, 10.0, 20.0), "radius": 70.0, "clip": (0.05, 4000.0),
              "cyc": {"size": 900, "wall": 400, "radius": 120, "back_y": 420}}
    WIDE = {"plant_wide", "plant_low", "loop_wide", "quarter_hero", "turbine_section", "sg_section",
            "vessel_section"}

    def __init__(self):
        self.col = geo.collection("plant")
        self.static, self.moving, self.fx, self.whole = [], [], [], []
        self.anchors = {}
        self.flows = {}
        self.events = []
        self.rod_insert = 0.3
        self._site()
        self._containment()
        self._vessel()
        self._loops()
        self._pressurizer()
        self._secondary()
        self._tower()
        self._flows()
        self._anchors()
        self.pose(0.0, 0.0)

    # ------------------------------------------------------------ buildings and site
    def _site(self):
        apron = geo.box("apron", (420, 220, 0.6), (75, 30, -0.3), self.col, M.concrete("#6e716f"))
        self.static.append(apron)
        for x0, x1 in ((22, 52), (140, 150)):
            self.static.append(geo.box("road", (x1 - x0, 8, 0.05), ((x0 + x1) / 2, -30, 0.02), self.col,
                                       M.concrete("#3d4043")))

    def _containment(self):
        r_out, wall, h = 21.2, 1.2, 38.0
        prof = [(r_out, 0.0), (r_out, h)] + _dome_profile(r_out, h, 18.0)[1:]
        self.containment = _shell("containment", prof, wall, 128, self.col, M.concrete("#b9bab4"))
        self.static.append(self.containment)
        self.static.append(geo.cylinder("base_slab", r_out + 1.5, -2.0, 0.0, 128, self.col, M.concrete("#8d8f8a")))
        deck = geo.cylinder("operating_deck", r_out - wall - 0.05, 14.0, 14.8, 128, self.col, M.concrete("#9c9d98"))
        geo.boolean(deck, geo.cylinder("cavity", 3.4, 10, 20, 64))
        for x in (11.0, -11.0):
            geo.boolean(deck, _at(geo.cylinder("sg_hole", 3.0, 10, 20, 48), x))
        geo.boolean(deck, _at(geo.cylinder("pz_hole", 1.8, 10, 20, 48), -6.0, 7.0))
        self.static.append(deck)
        ring = geo.lathe("crane_rail", [(r_out - wall - 0.9, 33.0), (r_out - wall - 0.05, 33.0),
                                        (r_out - wall - 0.05, 34.0), (r_out - wall - 0.9, 34.0),
                                        (r_out - wall - 0.9, 33.0)], 128, self.col, M.paint("#c99a2e", 0.5))
        self.static.append(ring)
        bridge = geo.box("polar_crane", (2 * (r_out - wall - 1.0), 3.0, 2.2), (0, 6.0, 35.0), self.col,
                         M.paint("#d9a52a", 0.45), fillet=0.15)
        self.static.append(bridge)
        hatch = _x_cyl("equipment_hatch", 4.0, -r_out - 1.5, -r_out + 1.0, 64, self.col, M.dark_steel(), 0.1)
        _at(hatch, 0, 6.0, 22.0)
        self.static.append(hatch)

    # ------------------------------------------------------------ reactor vessel and core
    def _vessel(self):
        c = self.col
        r_in, t = 2.0, 0.22
        r_o = r_in + t
        prof = list(reversed(_dome_profile(r_o, 4.0, -2.2))) + [(r_o, 14.0)]
        prof = [(r, z) for r, z in prof]
        vessel = _shell("reactor_vessel", [(0.02, 1.8)] + [(r, z) for r, z in prof[1:]], t, 96, c, M.forged_steel())
        flange = geo.lathe("vessel_flange", [(r_in, 13.6), (r_o + 0.45, 13.6), (r_o + 0.45, 14.6), (r_in, 14.6),
                                             (r_in, 13.6)], 96, c, M.forged_steel())
        head = _shell("closure_head", [(r_o, 14.6)] + _dome_profile(r_o, 14.6, 2.0)[1:], t, 96, c, M.forged_steel())
        self.static += [vessel, flange, head]
        for k in range(36):                                        # closure studs and nuts
            a = TAU * k / 36
            nut = geo.cylinder("stud_nut", 0.09, 14.6, 14.85, 6, c, M.dark_steel(), chamfer=0.01)
            _at(nut, (r_o + 0.24) * math.cos(a), (r_o + 0.24) * math.sin(a))
            self.static.append(nut)
        # control-rod drive housings on the head
        self.crdm_xy = [(i * 0.43, j * 0.43) for i in range(-3, 4) for j in range(-3, 4)
                        if (i * i + j * j) * 0.185 <= 1.62 and (i + j) % 2 == 0]
        for x, y in self.crdm_xy:
            z0 = 14.6 + math.sqrt(max(0.0, 1 - (x * x + y * y) / r_o ** 2)) * 2.0 - 0.05
            h = geo.cylinder("crdm", 0.1, z0, 21.0, 20, c, M.brushed_steel(), chamfer=0.01)
            coil = geo.cylinder("crdm_coil", 0.16, 18.4, 19.8, 20, c, M.paint("#3a4252", 0.4), chamfer=0.02)
            _at(h, x, y)
            _at(coil, x, y)
            self.static += [h, coil]
        shroud = geo.box("crdm_cable_tray", (3.6, 3.6, 0.3), (0, 0, 21.3), c, M.paint("#2a2f37", 0.5), fillet=0.05)
        self.static.append(shroud)
        # nozzles: hot legs at +-x on y = 0, cold legs toward +y
        for s in (1, -1):
            nz = _x_cyl("hot_nozzle", 0.6, 0, s * 3.0, 48, c, M.forged_steel())
            _at(nz, 0, 0, 12.0)
            self.static.append(nz)
            cn = geo.cylinder("cold_nozzle", 0.55, 0, 3.0, 48, c, M.forged_steel())
            geo.aim_z(cn, (s * 0.5, 0.866, 0), (0, 0, 12.0))
            self.static.append(cn)
        # internals: core barrel, plates, guide columns
        barrel = _shell("core_barrel", [(1.82, 3.6), (1.82, 13.4)], 0.06, 96, c, M.brushed_steel())
        lower = geo.cylinder("lower_core_plate", 1.76, 4.5, 4.75, 96, c, M.brushed_steel())
        upper = geo.cylinder("upper_core_plate", 1.76, 8.62, 8.82, 96, c, M.brushed_steel())
        support = geo.cylinder("upper_support_plate", 1.95, 12.7, 13.2, 96, c, M.brushed_steel())
        self.static += [barrel, lower, upper, support]
        for x, y in self.crdm_xy:
            g = geo.cylinder("guide_column", 0.09, 8.82, 12.7, 16, c, M.brushed_steel())
            _at(g, x, y)
            self.static.append(g)
        # fuel: assemblies on a 0.215 m pitch in the core circle; rods only where the cut can show them (y >= 0)
        pitch, rod_p = 0.215, 0.0126
        self.assemblies = [(i * pitch, j * pitch) for i in range(-8, 9) for j in range(-8, 9)
                           if math.hypot(i * pitch, j * pitch) <= 1.62]
        rods, nozzles = [], []
        for ax, ay in self.assemblies:
            nozzles.append((ax, ay, 0.0))
            for i in range(17):
                for j in range(17):
                    x, y = ax + (i - 8) * rod_p, ay + (j - 8) * rod_p
                    if y >= -0.004:
                        rods.append((x, y, 4.85))
        rod = geo.cylinder("fuel_rod", 0.0048, 0.0, 3.66, 8, c, M.zircaloy())
        fuel = _points_object("fuel_rods", rods, c)
        rod.parent = fuel
        frame = geo.box("assembly_nozzle", (0.205, 0.205, 0.14), (0, 0, 0), c, M.brushed_steel())
        geo.boolean(frame, geo.box("an_in", (0.18, 0.18, 0.3), (0, 0, 0)))
        grids = []
        for ax, ay in self.assemblies:
            if ay >= -0.1:
                grids += [(ax, ay, 4.78), (ax, ay, 8.56)] + [(ax, ay, 5.2 + 0.52 * k) for k in range(7)]
        grid_obj = _points_object("fuel_grids", grids, c)
        frame.parent = grid_obj
        self.fuel = fuel
        self.whole += [fuel, grid_obj, rod, frame]
        # control rod banks: clusters of 24 dark rods in the drive positions, hanging from a moving bank
        self.bank = bpy.data.objects.new("rod_bank", None)
        c.objects.link(self.bank)
        cl = []
        guide = [(i, j) for i in range(17) for j in range(17)
                 if (i, j) in {(2, 5), (2, 8), (2, 11), (3, 3), (3, 13), (5, 2), (5, 5), (5, 8), (5, 11), (5, 14),
                               (8, 2), (8, 5), (8, 11), (8, 14), (11, 2), (11, 5), (11, 8), (11, 11), (11, 14),
                               (13, 3), (13, 13), (14, 5), (14, 8), (14, 11)}]
        for x, y in self.crdm_xy:
            if y < -0.1:
                continue
            for i, j in guide:
                cl.append((x + (i - 8) * rod_p, y + (j - 8) * rod_p, 0.0))
        clusters = _points_object("control_rods", cl, c)
        crod = geo.cylinder("control_rod", 0.0043, 0.0, 3.8, 8, c, M.absorber())
        crod.parent = clusters
        clusters.parent = self.bank
        for x, y in self.crdm_xy:
            if y < -0.1:
                continue
            spider = geo.cylinder("rcca_spider", 0.06, 3.8, 3.9, 12, c, M.brushed_steel())
            arms = geo.box("rcca_arms", (0.17, 0.02, 0.05), (0, 0, 3.85), c, M.brushed_steel())
            arms2 = geo.box("rcca_arms2", (0.02, 0.17, 0.05), (0, 0, 3.85), c, M.brushed_steel())
            shaft = geo.cylinder("drive_shaft", 0.025, 3.9, 13.5, 12, c, M.polished_steel())
            for o in (spider, arms, arms2, shaft):
                _at(o, x, y)
                o.parent = self.bank
                self.whole.append(o)
        self.whole += [clusters, crod]
        # coolant inside the vessel and the core glow
        water = geo.lathe("vessel_water", [(0, 1.85)] + [(p[0] - 0.005, p[1]) for p in
                                                          reversed(_dome_profile(r_in, 4.0, -2.15))][1:] +
                          [(r_in - 0.005, 13.55), (0, 13.55)], 64, c, _water_volume("coolant_volume"))
        water["power"] = 1.0
        water["no_occlude"] = 1
        self.water = water
        self.fx.append(water)
        ld = bpy.data.lights.new("core_glow", "AREA")
        ld.shape = "DISK"
        ld.size = 3.0
        ld.color = (0.35, 0.6, 1.0)
        ld.energy = 0.0
        self.glow = bpy.data.objects.new("core_glow", ld)
        c.objects.link(self.glow)
        self.glow.location = (0, -0.5, 8.8)
        self.glow.rotation_euler = (math.radians(180), 0, 0)

    # ------------------------------------------------------------ primary loops
    def _loops(self):
        c = self.col
        self.sg_x = (11.0, -11.0)
        for k, s in enumerate((1, -1)):
            x = s * 11.0
            # steam generator: channel head, lower shell (tube bundle), cone, upper shell (separators)
            prof = list(reversed(_dome_profile(1.75, 8.6, -1.6)))[:-1] + [(1.75, 8.6), (1.75, 20.0), (2.3, 22.5),
                                                                         (2.3, 28.0)] + _dome_profile(2.3, 28.0, 1.6)[1:]
            sg = _shell(f"steam_generator_{k + 1}", [(0.02, prof[0][1])] + prof[1:], 0.12, 96, c, M.insulation())
            _at(sg, x)
            sheet = geo.cylinder("tube_sheet", 1.63, 8.2, 8.8, 64, c, M.forged_steel())
            _at(sheet, x)
            divider = geo.box("divider_plate", (3.2, 0.06, 1.4), (x, 0, 7.6), c, M.forged_steel())
            wrapper = _shell("tube_wrapper", [(1.5, 9.0), (1.5, 19.4)], 0.03, 64, c, M.brushed_steel())
            _at(wrapper, x)
            self.static += [sg, sheet, divider, wrapper]
            for sx, sy in [(0.0, 0.0)] + [(1.15 * math.cos(TAU * a / 6), 1.15 * math.sin(TAU * a / 6))
                                          for a in range(6)]:            # moisture separators
                sep = geo.cylinder("separator", 0.36, 22.8, 25.0, 24, c, M.brushed_steel(), chamfer=0.03)
                _at(sep, x + sx, sy)
                self.static.append(sep)
            dryer = geo.box("steam_dryer", (3.2, 3.2, 1.2), (x, 0, 26.2), c, M.brushed_steel(), fillet=0.1)
            self.static.append(dryer)
            # U-tubes (the half the cut can show): legs over the hot and cold halves of the channel head
            tubes = []
            for row in range(5):
                y = 0.08 + row * 0.24
                for n in range(9):
                    half = 0.18 + n * 0.135
                    if half + 0.05 > math.sqrt(max(0.0, 1.45 ** 2 - y * y)):
                        continue
                    top = 18.4 + half * 0.25
                    pts = [(x - half, y, 8.8), (x - half, y, top)] + \
                          [(x - half * math.cos(a), y, top + half * math.sin(a)) for a in
                           [math.pi * q / 10 for q in range(1, 10)]] + [(x + half, y, top), (x + half, y, 8.8)]
                    tubes.append(geo.sweep("u_tube", pts, 0.012, c, M.copper(), segments=8, resolution=2))
            self.static += tubes
            sg_water = geo.cylinder(f"sg_water_{k + 1}", 1.62, 8.8, 18.6, 64, c, _liquid("sg_water", "#5aa8e8"))
            _at(sg_water, x)
            sg_water["no_occlude"] = 1
            self.fx.append(sg_water)
            # hot leg: vessel nozzle -> channel head (hot half, toward the vessel)
            hot = geo.sweep(f"hot_leg_{k + 1}", [(s * 2.9, 0, 12.0), (s * 6.5, 0, 12.0), (s * 9.2, 0, 10.4),
                                                 (x - s * 0.6, 0, 7.4)], 0.42, c, M.insulation(), segments=32)
            # crossover leg (U down) to the pump on +y, then the cold leg back to the vessel
            pump = (s * 7.6, 6.2)
            cross = geo.sweep(f"crossover_leg_{k + 1}", [(x + s * 0.6, 0.6, 7.0), (x + s * 0.4, 2.6, 4.2),
                                                         (pump[0] + s * 0.4, pump[1] - 1.2, 4.0),
                                                         (pump[0], pump[1], 7.5)], 0.4, c, M.insulation(), segments=32)
            cold = geo.sweep(f"cold_leg_{k + 1}", [(pump[0] - s * 0.4, pump[1] - 0.6, 10.2),
                                                    (s * 4.5, 4.8, 12.0), (s * 1.6, 2.6, 12.0)], 0.38, c,
                             M.insulation(), segments=32)
            self.static += [hot, cross, cold]
            # reactor coolant pump: casing bowl, motor stand, motor, flywheel cover
            casing = geo.lathe(f"coolant_pump_{k + 1}", [(0, 7.2), (1.15, 7.2), (1.3, 7.8), (1.3, 9.6), (1.0, 10.4),
                                                         (0.6, 10.6), (0, 10.6)], 64, c, M.forged_steel())
            stand = geo.cylinder("pump_stand", 0.9, 10.6, 12.6, 48, c, M.paint("#3a4252", 0.4))
            motor = geo.lathe("pump_motor", [(0, 12.6), (1.25, 12.6), (1.25, 16.0), (1.05, 16.6), (0, 16.6)], 64, c,
                              M.paint("#2f5f8f", 0.38))
            for o in (casing, stand, motor):
                _at(o, *pump)
            self.static += [casing, stand, motor]
            fins = []
            for q in range(24):
                a = TAU * q / 24
                f = geo.box("motor_fin", (0.18, 0.06, 3.0), (1.3, 0.0, 14.3), c, M.paint("#2f5f8f", 0.38))
                geo.transform_mesh(f, Matrix.Translation((pump[0], pump[1], 0)) @ Matrix.Rotation(a, 4, "Z"))
                fins.append(f)
            self.static += fins
            if k == 0:
                self.pump_xy = pump

    def _pressurizer(self):
        c = self.col
        x, y = -6.0, 7.0
        prof = list(reversed(_dome_profile(1.25, 16.0, -1.2)))[:-1] + [(1.25, 16.0), (1.25, 27.0)] + \
            _dome_profile(1.25, 27.0, 1.2)[1:]
        pz = _shell("pressurizer", [(0.02, prof[0][1])] + prof[1:], 0.1, 64, c, M.insulation())
        _at(pz, x, y)
        surge = geo.sweep("surge_line", [(x, y, 14.8), (x, y, 13.0), (x + 0.5, 3.0, 12.6), (-6.2, 0.4, 12.4)], 0.17,
                          c, M.insulation(), segments=16)
        valves = []
        for q in range(3):
            v = geo.cylinder("safety_valve", 0.18, 28.0, 29.0, 16, c, M.paint("#b23a2a", 0.45), chamfer=0.03)
            _at(v, x - 0.5 + q * 0.5, y)
            valves.append(v)
        self.static += [pz, surge, *valves]
        water = geo.cylinder("pz_water", 1.13, 15.0, 22.0, 48, c, _liquid("pz_water", "#5aa8e8"))
        _at(water, x, y)
        water["no_occlude"] = 1
        self.fx.append(water)

    # ------------------------------------------------------------ steam side
    def _secondary(self):
        c = self.col
        hall = geo.box("turbine_hall", (92, 46, 34), (96, 0, 17), c, M.cladding("#8693a3"))
        geo.boolean(hall, geo.box("hall_in", (91, 45, 33.4), (96, 0, 16.6)))
        roof = geo.box("hall_roof", (94, 48, 1.2), (96, 0, 34.4), c, M.paint("#5b6470", 0.6))
        deck = geo.box("turbine_deck", (80, 14, 1.4), (94, 0, 9.3), c, M.concrete("#9c9d98"))
        self.static += [hall, roof, deck]
        self.hall = hall
        # rotors: HP and two double-flow LP turbines on one shaft at z = 12, then the generator
        shaft = _x_cyl("turbine_shaft", 0.45, 56.0, 136.0, 48, c, M.polished_steel())
        _at(shaft, 0, 0, 12.0)
        self.rotors = [shaft]
        stages = [(60.0 + 1.4 * i, 0.9 + 0.06 * i, 0.35 + 0.04 * i, 64) for i in range(8)]       # HP
        for c0 in (80.0, 102.0):                                                                # LP double flow
            for i in range(5):
                for sgn in (-1, 1):
                    stages.append((c0 + sgn * (1.6 + 1.7 * i), 1.3 + 0.12 * i, 0.5 + 0.38 * i, 72))
        for sx, hub, length, n in stages:
            disc = _x_cyl("stage_disc", hub, sx - 0.18, sx + 0.18, 64, c, M.forged_steel(), chamfer=0.02)
            _at(disc, 0, 0, 12.0)
            ring_ob = _blade_ring("turbine_blades", sx, hub, length, n, c)
            self.rotors += [disc, ring_ob]
        for x0, x1, r in ((57.5, 72.0, 2.4), (70.0, 91.0, 4.4), (92.0, 113.0, 4.4)):
            cas = _shell("turbine_casing", [(r, x0), (r, x1)], 0.25, 72, c, M.paint("#5f6b78", 0.42))
            geo.transform_mesh(cas, Matrix.Rotation(math.radians(90), 4, "Y"))
            _at(cas, 0, 0, 12.0)
            self.static.append(cas)
        gen = _x_cyl("generator", 2.5, 116.0, 132.0, 72, c, M.paint("#2f5f8f", 0.35), chamfer=0.2)
        _at(gen, 0, 0, 12.0)
        exciter = _x_cyl("exciter", 1.2, 133.0, 137.0, 48, c, M.paint("#2f5f8f", 0.35), chamfer=0.1)
        _at(exciter, 0, 0, 12.0)
        self.static += [gen, exciter]
        # condenser under the LP turbines, with its tube field and hotwell
        cond = geo.box("condenser", (40, 12, 8.0), (91, 0, 4.4), c, M.paint("#4b5560", 0.5), fillet=0.2)
        geo.boolean(cond, geo.box("cond_in", (39.4, 11.4, 7.4), (91, 0, 4.4)))
        tubes = [(x, y, z) for x in (0.0,) for y in [-4.5 + 0.3 * k for k in range(31)] if y >= -0.1
                 for z in [1.4 + 0.3 * k for k in range(12)]]
        field = _points_object("condenser_tubes", tubes, c)
        ct = _x_cyl("cond_tube", 0.06, 71.5, 110.5, 8, c, M.copper())
        ct.parent = field
        hotwell = geo.box("hotwell_water", (39.2, 11.2, 0.8), (91, 0, 1.0), c, _liquid("hotwell", "#5aa8e8"))
        hotwell["no_occlude"] = 1
        self.static.append(cond)
        self.whole += [field, ct]
        self.fx.append(hotwell)
        # main steam lines: SG domes -> through the containment wall -> HP inlet
        self.steam_pts = [(11.0, 0.0, 29.6), (11.0, 0.0, 31.5), (16.0, -2.0, 31.5), (24.0, -2.0, 30.0),
                          (44.0, -2.0, 24.0), (56.0, -2.0, 16.0), (59.5, 0.0, 14.0)]
        steam = geo.sweep("main_steam_line", self.steam_pts, 0.45, c, M.insulation(), segments=24)
        self.feed_pts = [(91.0, 0.0, 0.8), (70.0, 4.0, 1.0), (44.0, 6.0, 4.0), (24.0, 6.0, 12.0),
                         (14.0, 3.0, 18.0), (12.3, 1.0, 18.0)]
        feed = geo.sweep("feedwater_line", self.feed_pts, 0.3, c, M.paint("#3c6e5a", 0.45), segments=20)
        cross = geo.sweep("crossover_pipe", [(70.0, 0.0, 16.0), (70.0, 0.0, 19.0), (91.0, 0.0, 19.0),
                                             (102.0, 0.0, 19.0), (102.0, 0.0, 16.0)], 1.0, c, M.insulation(),
                          segments=24)
        self.static += [steam, feed, cross]
        # step-up transformer and the first pylon
        tx = geo.box("transformer", (8, 6, 7), (148, -12, 3.5), c, M.paint("#55606b", 0.45), fillet=0.2)
        self.static.append(tx)

    def _tower(self):
        c = self.col
        cx, cy = 190.0, 75.0
        prof = []
        for k in range(41):
            z = 12.0 + 118.0 * k / 40
            r = 26.0 * math.sqrt(1 + ((z - 95.0) / 58.0) ** 2)
            prof.append((r, z))
        tower = _shell("cooling_tower", prof, 0.7, 160, c, M.concrete("#c4c4bd"))
        _at(tower, cx, cy)
        self.static.append(tower)
        legs = []
        base_r = prof[0][0]
        for q in range(36):
            a = TAU * q / 36
            for sgn in (-1, 1):
                p0 = (cx + (base_r + 2) * math.cos(a), cy + (base_r + 2) * math.sin(a), 0.0)
                a1 = a + sgn * TAU / 72
                p1 = (cx + base_r * math.cos(a1), cy + base_r * math.sin(a1), 12.5)
                legs.append(geo.sweep("tower_leg", [p0, p1], 0.55, c, M.concrete("#b0b0aa"), segments=8, resolution=1))
        pond = geo.cylinder("tower_basin", base_r + 3, 0.0, 1.2, 128, c, M.concrete("#7b7d7a"))
        _at(pond, cx, cy)
        self.static += legs + [pond]
        plume = geo.lathe("vapour_plume", [(0, 128), (30, 128), (44, 150), (52, 185), (46, 225), (24, 255),
                                           (0, 262)], 48, c, _plume_material())
        _at(plume, cx + 8, cy + 6)
        plume["plume_phase"] = 0.0
        plume["no_occlude"] = 1
        self.plume = plume
        self.fx.append(plume)
        self.tower_xy = (cx, cy)

    # ------------------------------------------------------------ flows
    def _flows(self):
        c = self.col
        loop = [(0.4, 0.4, 5.0), (0.4, 0.4, 8.5), (0.6, 0.3, 11.5), (2.9, 0, 12.0), (6.5, 0, 12.0), (9.2, 0, 10.4),
                (10.4, 0.3, 8.6), (10.4, 0.4, 18.6), (11.0, 0.4, 19.0), (11.6, 0.4, 18.6), (11.6, 0.4, 8.8),
                (11.6, 0.6, 7.0), (11.4, 2.6, 4.2), (8.0, 5.0, 4.0), (7.6, 6.2, 7.5), (7.2, 5.6, 10.2),
                (4.5, 4.8, 12.0), (1.6, 2.6, 12.0), (1.9, 1.0, 12.0), (1.9, 0.4, 8.0), (1.9, 0.3, 4.2), (0.9, 0.3, 3.0)]
        self.flows["primary"] = Flow("flow_primary", loop, count=520, spread=0.22, size=0.07, stretch=3.0,
                                     ramp=((0.0, "#4fb6ff"), (0.12, "#ffb23e"), (0.42, "#ff7a2a"),
                                           (0.52, "#4fb6ff"), (1.0, "#4fb6ff")), strength=8.0, col=c, seed=3)
        mirror = [(-x, y, z) for x, y, z in loop]
        self.flows["primary_b"] = Flow("flow_primary_b", mirror, count=520, spread=0.22, size=0.07, stretch=3.0,
                                       ramp=((0.0, "#4fb6ff"), (0.12, "#ffb23e"), (0.42, "#ff7a2a"),
                                             (0.52, "#4fb6ff"), (1.0, "#4fb6ff")), strength=8.0, col=c, seed=5)
        self.flows["steam"] = Flow("flow_steam", self.steam_pts, count=260, spread=0.25, size=0.09, stretch=4.0,
                                   closed=False, ramp=((0.0, "#f4f6fa"), (1.0, "#cfe8ff")), strength=5.0, col=c, seed=7)
        self.flows["feed"] = Flow("flow_feed", self.feed_pts, count=160, spread=0.15, size=0.06, stretch=3.0,
                                  closed=False, ramp=((0.0, "#4fb6ff"), (1.0, "#4fb6ff")), strength=5.0, col=c, seed=9)
        boil = [(11.0 + 0.9 * math.cos(a), 0.7 + 0.3 * math.sin(a), 9.0 + 9.5 * k / 12) for k, a in
                enumerate([0.4 * q for q in range(13)])]
        self.flows["boil"] = Flow("flow_boil", boil, count=180, spread=0.7, size=0.05, stretch=1.2, closed=False,
                                  ramp=((0.0, "#dff1ff"), (1.0, "#ffffff")), strength=3.0, col=c, seed=11)
        for f in self.flows.values():
            self.fx.append(f.obj)

    # ------------------------------------------------------------ anchors, cuts, cameras
    def _anchors(self):
        def empty(name, loc, parent=None):
            e = bpy.data.objects.new(name, None)
            self.col.objects.link(e)
            if parent is not None:
                e.parent = parent
            e.location = loc
            self.anchors[name] = e
        empty("reactor_vessel", (0.0, 0.0, 15.5))
        empty("reactor_core", (0.0, 0.3, 6.7))
        empty("fuel_rods", (0.6, 0.3, 7.6))
        empty("control_rods", (0.0, 0.3, 3.9), self.bank)
        empty("rod_drives", (0.0, 0.0, 19.6))
        empty("hot_leg", (6.5, 0.0, 12.0))
        empty("cold_leg", (4.5, 4.8, 12.0))
        empty("coolant_pump", (self.pump_xy[0], self.pump_xy[1], 14.0))
        empty("pressurizer", (-6.0, 7.0, 22.0))
        empty("steam_generator", (11.0, 0.0, 24.0))
        empty("sg_tubes", (11.0, 0.3, 15.0))
        empty("steam_line", (40.0, -2.0, 25.0))
        empty("turbine_blades", (82.0, -2.0, 15.0))
        empty("turbine_shaft", (66.0, 0.0, 12.0))
        empty("generator", (124.0, -2.5, 13.0))
        empty("condenser", (91.0, -6.0, 5.0))
        empty("cooling_tower", (self.tower_xy[0], self.tower_xy[1] - 30.0, 80.0))
        empty("vapour_plume", (self.tower_xy[0] + 8, self.tower_xy[1], 170.0))
        empty("containment", (0.0, -21.0, 30.0))

    def cuts(self) -> dict:
        own = self.fx
        half = ((None, None), (None, 0.0), (None, None))
        return {name: {"bounds": half, "peel": (1, 260.0), "cut_moving": [], "own_cap": own}
                for name in ("containment", "vessel", "steam_generator", "turbine")} | {
            "quarter": {"bounds": ((None, 0.0), (None, 0.0), (None, None)), "peel": (1, 260.0), "cut_moving": [],
                        "own_cap": own}}

    def cameras(self) -> dict:
        tx, ty = self.tower_xy
        return {
            "plant_wide": {"pos": (-120.0, -430.0, 210.0), "target": (85.0, 20.0, 40.0), "lens": 40, "fstop": 16},
            "plant_low": {"pos": (-55.0, -95.0, 4.0), "target": (30.0, 25.0, 45.0), "lens": 24, "fstop": 16},
            "tower_close": {"pos": (tx - 90.0, ty - 190.0, 30.0), "target": (tx, ty, 95.0), "lens": 32, "fstop": 16},
            "loop_wide": {"pos": (0.0, -64.0, 24.0), "target": (0.0, 2.0, 15.0), "lens": 32, "fstop": 11},
            "quarter_hero": {"pos": (-62.0, -70.0, 52.0), "target": (0.0, 0.0, 20.0), "lens": 35, "fstop": 11},
            "vessel_section": {"pos": (1.5, -22.0, 12.5), "target": (0.0, 0.0, 11.0), "lens": 35, "fstop": 8},
            "core_close": {"pos": (-1.3, -4.6, 7.6), "target": (0.0, 0.5, 6.8), "lens": 40, "fstop": 4},
            "rods_close": {"pos": (-1.1, -5.0, 11.2), "target": (0.0, 0.5, 9.6), "lens": 40, "fstop": 4},
            "pump_close": {"pos": (2.0, -9.0, 14.0), "target": (7.6, 6.2, 11.0), "lens": 35, "fstop": 6},
            "sg_section": {"pos": (12.0, -34.0, 19.0), "target": (11.0, 0.0, 18.0), "lens": 35, "fstop": 8},
            "sg_close": {"pos": (9.6, -8.0, 13.5), "target": (11.0, 0.5, 13.0), "lens": 40, "fstop": 4},
            "turbine_section": {"pos": (58.0, -52.0, 26.0), "target": (88.0, 0.0, 12.0), "lens": 30, "fstop": 8},
            "turbine_close": {"pos": (76.0, -11.0, 15.0), "target": (82.0, 0.0, 12.0), "lens": 35, "fstop": 5},
        }

    def visible(self) -> list:
        out = []
        for o in self.static + self.moving:
            if o.type == "MESH" and not o.hide_render and o.name not in ("apron",) and not o.name.startswith("road"):
                out.append(o)
        return out

    # ------------------------------------------------------------ animation
    def set_events(self, events):
        self.events = sorted(events, key=lambda e: e["t"])

    def rods(self, t: float) -> float:
        """Rod insertion 0 (out) .. 1 (fully in) at time t: eased moves after each rods_in / rods_out event."""
        d = 0.3
        for e in self.events:
            if e["t"] > t:
                break
            target = {"rods_in": 0.92, "rods_out": 0.08}.get(e["type"])
            if target is None:
                continue
            u = min(1.0, (t - e["t"]) / 1.6)
            u = u * u * (3 - 2 * u)
            d = d + (target - d) * u
        return d

    def power(self, t: float) -> float:
        p = max(0.05, 1.0 - self.rods(t)) ** 1.4 / 0.7 ** 1.4
        for e in self.events:
            if e["type"] == "power_up" and e["t"] <= t:
                p *= 1.0 + 0.6 * math.exp(-(t - e["t"]) / 1.2)
        return p

    def pose(self, phase: float, t: float = 0.0):
        turns = phase / 360.0
        for o in self.rotors:
            o.rotation_euler.x = math.radians(phase)
        for name, f in self.flows.items():
            rate = {"primary": 1 / 6, "primary_b": 1 / 6, "steam": 1 / 3, "feed": 1 / 6, "boil": 1 / 2}[name]
            f.set_phase(turns * rate)
        d = self.rods(t)
        self.bank.location.z = 4.85 + (1.0 - d) * 3.6
        p = self.power(t)
        self.water["power"] = p
        self.glow.data.energy = 2500.0 * p
        self.plume["plume_phase"] = t * 0.15
        for e in self.events:
            if e["type"] == "steam_burst" and 0 <= t - e["t"] < 2.0:
                self.plume["plume_phase"] = t * 0.15 + 0.4 * (1 - math.exp(-(t - e["t"]) * 2))

    def animated(self) -> list:
        return [*self.rotors, self.bank, self.water, self.glow, self.plume, *[f.obj for f in self.flows.values()]]
