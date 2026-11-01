"""
A DOHC 16-valve inline-4 (2.0 L class: 86 x 86 mm, 145 mm rods) built from production-quality parts.

    eng = Inline4Engine()             # builds every part into the "engine" collection
    eng.pose(theta_deg)               # crank angle -> pistons, rods, valves, cams, gas, spark
    eng.anchors                       # name -> empty, for callouts

Layout: crank axis along X (cylinder 1 at the front, -X), intake on -Y, exhaust on +Y, crank centre at z = 0.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Matrix, Vector  # noqa: F401

from .. import geo
from .. import materials as M
from .. import parts as P
from ..rigs import crank as K
from ..rigs.flow import Flow

TILT = math.radians(20.0)                       # valve angle from vertical (pent-roof)
AX = {"in": Vector((0.0, -math.sin(TILT), math.cos(TILT))), "ex": Vector((0.0, math.sin(TILT), math.cos(TILT)))}
VALVE_DX = {"in": 0.0175, "ex": 0.0150}         # valve offsets from the bore centre along X
VALVE_Y = {"in": -0.0150, "ex": 0.0150}
VALVE_D = {"in": 0.033, "ex": 0.028}
FACE_DZ = 0.0085                                # valve face height above the deck
S_SEAT, S_RET, S_BUCKET, S_CAM = 0.056, 0.0905, 0.085, 0.1245   # distances along a valve axis from its face
SPRING_LEN = S_RET - S_SEAT
ROOF_DZ = 0.0115


def _smooth(u: float) -> float:
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def _at(obj, x=0.0, y=0.0, z=0.0):
    return geo.transform_mesh(obj, Matrix.Translation((x, y, z)))


def _rot(obj, deg, axis):
    return geo.transform_mesh(obj, Matrix.Rotation(math.radians(deg), 4, axis))


def _yz_prism(name, outline_yz, x0, x1, col=None, mat=None):
    """Prism from an outline given in (y, z), extruded along X."""
    obj = geo.prism(name, outline_yz, x0, x1, col, mat)
    m = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    return geo.transform_mesh(obj, m)


def _x_cyl(name, r, x0, x1, segs=48, col=None, mat=None, chamfer=0.0):
    c = geo.cylinder(name, r, x0, x1, segs, col, mat, chamfer)
    return geo.transform_mesh(c, Matrix(((0, 0, 1, 0), (0, 1, 0, 0), (1, 0, 0, 0), (0, 0, 0, 1))))


def _axis_cyl(name, r, origin, axis, s0, s1, segs=40):
    c = geo.cylinder(name, r, s0, s1, segs)
    return geo.aim_z(c, axis, origin)


def _obj_attr(nt, name):
    a = nt.nodes.new("ShaderNodeAttribute")
    a.attribute_type = "OBJECT"
    a.attribute_name = name
    return a


def gas_material():
    """The charge in a cylinder or port, as a glowing translucent surface (reads in EEVEE drafts and Cycles
    alike; the first drafts' thin volume was invisible on screen). Object properties drive it per frame:
    gas_color, gas_density (opacity), gas_glow, and a flame front: a sphere of radius flame_r around
    flame_o (the spark plug tip) that burns white-yellow at the core and orange at its edge."""
    mat = bpy.data.materials.new("gas")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    col, den, glow = _obj_attr(nt, "gas_color"), _obj_attr(nt, "gas_density"), _obj_attr(nt, "gas_glow")
    fr, fo, fk = _obj_attr(nt, "flame_r"), _obj_attr(nt, "flame_o"), _obj_attr(nt, "flame_k")

    def math_(op, a, b=None, clamp=False):
        m = nt.nodes.new("ShaderNodeMath")
        m.operation = op
        m.use_clamp = clamp
        for k, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                m.inputs[k].default_value = v
            else:
                nt.links.new(v, m.inputs[k])
        return m.outputs[0]

    geo_ = nt.nodes.new("ShaderNodeNewGeometry")
    sub = nt.nodes.new("ShaderNodeVectorMath")
    sub.operation = "SUBTRACT"
    nt.links.new(geo_.outputs["Position"], sub.inputs[0])
    nt.links.new(fo.outputs["Vector"], sub.inputs[1])
    ln = nt.nodes.new("ShaderNodeVectorMath")
    ln.operation = "LENGTH"
    nt.links.new(sub.outputs[0], ln.inputs[0])
    dist = ln.outputs["Value"]
    flame = math_("MULTIPLY", math_("DIVIDE", math_("SUBTRACT", fr.outputs["Fac"], dist), 0.006, clamp=True),
                  fk.outputs["Fac"])
    core = math_("SUBTRACT", 1.0, math_("DIVIDE", dist, math_("ADD", fr.outputs["Fac"], 1e-4)), clamp=True)
    fcol = nt.nodes.new("ShaderNodeMix")
    fcol.data_type = "RGBA"
    M.sock(fcol, "A").default_value = M.hex_rgb("#ff6a12")
    M.sock(fcol, "B").default_value = M.hex_rgb("#fff3c4")
    nt.links.new(core, M.sock(fcol, "Factor"))
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(flame, M.sock(mix, "Factor"))
    nt.links.new(col.outputs["Color"], M.sock(mix, "A"))
    nt.links.new(M.sock(fcol, "Result", True), M.sock(mix, "B"))
    tc = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 45.0
    noise.inputs["Detail"].default_value = 4.0
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    swirl = nt.nodes.new("ShaderNodeMapRange")
    swirl.inputs["From Min"].default_value = 0.3
    swirl.inputs["From Max"].default_value = 0.7
    swirl.inputs["To Min"].default_value = 0.6
    nt.links.new(noise.outputs["Fac"], swirl.inputs["Value"])
    alpha = math_("ADD", math_("MULTIPLY", math_("MULTIPLY", den.outputs["Fac"], 0.17, clamp=True),
                               swirl.outputs["Result"]), math_("MULTIPLY", flame, 0.75))
    alpha = math_("MINIMUM", alpha, 0.93)
    strength = math_("ADD", math_("ADD", 1.6, math_("MULTIPLY", glow.outputs["Fac"], 0.12)),
                     math_("MULTIPLY", flame, 9.0))
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(M.sock(mix, "Result", True), em.inputs["Color"])
    nt.links.new(strength, em.inputs["Strength"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    sh = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(alpha, sh.inputs["Fac"])
    nt.links.new(tr.outputs["BSDF"], sh.inputs[1])
    nt.links.new(em.outputs["Emission"], sh.inputs[2])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(sh.outputs["Shader"], out.inputs["Surface"])
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"
    return mat


def spark_material():
    mat = bpy.data.materials.new("spark")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    s = _obj_attr(nt, "glow")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = M.hex_rgb("#bfe6ff")
    nt.links.new(s.outputs["Fac"], em.inputs["Strength"])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return mat


def _liquid(name, color, transmission, rough=0.06):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    b = mat.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = M.hex_rgb(color)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Transmission Weight"].default_value = transmission
    b.inputs["IOR"].default_value = 1.35
    b.inputs["Coat Weight"].default_value = 0.6
    return mat


def heat_tint():
    """Exhaust steel: straw and blue temper colours near the hot ports, fading to grey steel downstream."""
    mat = M._metal("heat_tint", "#9a9590", 0.34, 0.07, grain=2000.0, grain_strength=0.05, grime=0.4)
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tint_src = bsdf.inputs["Base Color"].links[0].from_socket
    geo_n = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo_n.outputs["Position"], sep.inputs["Vector"])
    rng = nt.nodes.new("ShaderNodeMapRange")
    rng.inputs["From Min"].default_value = 0.10                 # world Y: the ports sit at y = 0.10
    rng.inputs["From Max"].default_value = 0.19
    nt.links.new(sep.outputs["Y"], rng.inputs["Value"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, M.hex_rgb("#d8b06a")   # straw
    els[1].position, els[1].color = 1.0, M.hex_rgb("#b4b5b8")   # steel
    mid = els.new(0.35)
    mid.color = M.hex_rgb("#7a7fb8")                            # temper blue
    nt.links.new(rng.outputs["Result"], ramp.inputs["Fac"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MIX"
    M.sock(mix, "Factor").default_value = 0.75                  # temper colours over the grimy steel
    nt.links.new(tint_src, M.sock(mix, "A"))
    nt.links.new(ramp.outputs["Color"], M.sock(mix, "B"))
    nt.links.new(M.sock(mix, "Result", True), bsdf.inputs["Base Color"])
    return mat


def convex_hull(points):
    """2-D convex hull (monotone chain), counter-clockwise."""
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def belt_outline(pulleys, extra=0.0, steps=48):
    """Outline (y, z) of a belt wrapped round pulleys [(y, z, r)]: the hull of their rims."""
    pts = []
    for y, z, r in pulleys:
        for k in range(steps):
            a = math.tau * k / steps
            pts.append((round(y + (r + extra) * math.cos(a), 6), round(z + (r + extra) * math.sin(a), 6)))
    return convex_hull(pts)


# gas look per stroke: (colour, density, glow)
GAS = {
    "intake": (M.hex_rgb("#6fd3ff")[:3], 2.6, 0.0),
    "compression": (M.hex_rgb("#8fdcff")[:3], 4.6, 0.0),
    "power": (M.hex_rgb("#ff7a1e")[:3], 4.0, 0.0),
    "exhaust": (M.hex_rgb("#8a7c70")[:3], 3.6, 0.0),
}
BURNT = M.hex_rgb("#a0522d")[:3]           # the burnt charge cooling during the power stroke


class Inline4Engine:
    def __init__(self, coolant: bool = True, oil: bool = True):
        self.k = K.Inline4()
        self.col = geo.collection("engine")
        self.static: list = []          # castings and fixed parts (sectionable)
        self.moving: list = []          # animated parts (sectionable)
        self.fx: list = []              # gas volumes, sparks (sectionable volumes)
        self.anchors: dict = {}
        self.cyl = [dict() for _ in range(4)]
        k = self.k
        self.deck = k.deck
        self.xs = [k.x(i) for i in range(4)]
        self.mains = [self.xs[0] - k.pitch / 2] + [(self.xs[i] + self.xs[i + 1]) / 2 for i in range(3)] + \
                     [self.xs[3] + k.pitch / 2]
        self._block()
        self._head()
        self._valvetrain()
        self._bottom_end()
        self._ignition()
        self._manifolds()
        self._gas()
        if coolant:
            self._coolant()
        if oil:
            self._oil()
        self._dress()
        self._anchors()
        self.pose(0.0)

    # ------------------------------------------------------------ geometry helpers
    def face(self, i, side, s):
        """Valve face centre (s = 0) or a point s metres up the valve axis, for cylinder i, valve s=-1/+1."""
        x = self.xs[i] + side * VALVE_DX[s]
        return Vector((x, VALVE_Y[s], self.deck + FACE_DZ))

    # ------------------------------------------------------------ static castings
    def _block(self):
        k, d = self.k, self.deck
        out = [(-0.095, d), (-0.095, 0.10), (-0.112, 0.045), (-0.112, -0.072), (0.112, -0.072), (0.112, 0.045),
               (0.095, 0.10), (0.095, d)]
        block = _yz_prism("block", out, -0.215, 0.215, self.col, M.cast_aluminium())
        for xm in self.mains:                              # external ribs at each bulkhead
            for s in (-1, 1):
                geo.boolean(block, geo.box("rib", (0.010, 0.014, 0.145), (xm, s * 0.113, 0.0025)), "UNION")
        for x in self.xs:                                  # the cylinder walls show through the casting
            for s in (-1, 1):
                geo.boolean(block, _at(geo.cylinder("bulge", 0.042, 0.105, d - 0.012, 48), x, s * 0.064), "UNION")
        geo.bevel(block, 0.0035, 3, 40)
        for x in self.xs:
            geo.boolean(block, _at(geo.cylinder("bore", k.bore / 2, 0.035, d + 0.01, 96), x))
        cav = [(-0.086, -0.09)] + [(0.086 * math.cos(math.radians(a)), 0.086 * math.sin(math.radians(a)))
                                   for a in range(180, -1, -10)] + [(0.086, -0.09)]
        for i in range(4):
            geo.boolean(block, _yz_prism("cav", cav, self.mains[i] + 0.0125, self.mains[i + 1] - 0.0125))
        geo.boolean(block, _x_cyl("mainbore", 0.0275, -0.3, 0.3, 64))
        jacket = geo.prism("wj", geo.tangent_hull((self.xs[0], 0), 0.0565, (self.xs[3], 0), 0.0565, 40), 0.115,
                           d + 0.002)
        geo.boolean(jacket, geo.prism("wj_i", geo.tangent_hull((self.xs[0], 0), 0.0505, (self.xs[3], 0), 0.0505,
                                                                40), 0.10, d + 0.01))
        geo.boolean(block, jacket)
        geo.boolean(block, _at(_x_cyl("gallery", 0.005, -0.3, 0.3, 24), 0, 0.078, 0.02))
        geo.shade(block, 40)
        self.block = block
        self.static.append(block)
        for xm in self.mains:                              # main bearing cap bolts, from below
            for s in (-1, 1):
                b = geo.hex_bolt("cap_bolt", 0.010, 0.06, self.col, M.dark_steel())
                _rot(b, 180, "X")
                _at(b, xm, s * 0.048, -0.072)
                self.static.append(b)
        pan_o = [(-0.112, -0.072), (-0.112, -0.080), (-0.101, -0.082), (-0.093, -0.165), (0.093, -0.165),
                 (0.101, -0.082), (0.112, -0.080), (0.112, -0.072)]
        pan = _yz_prism("oil_pan", pan_o, -0.212, 0.212, self.col, M.cast_aluminium())
        for xf in (-0.12, -0.04, 0.04, 0.12):
            geo.boolean(pan, geo.box("fin", (0.006, 0.17, 0.010), (xf, 0, -0.168)), "UNION")
        geo.bevel(pan, 0.002, 2, 40)
        pan_i = [(-0.104, -0.068), (-0.096, -0.084), (-0.089, -0.161), (0.089, -0.161), (0.096, -0.084),
                 (0.104, -0.068)]
        geo.boolean(pan, _yz_prism("pan_in", pan_i, -0.207, 0.207))
        self.pan = pan
        self.static.append(pan)
        cover_o = [(-0.095, d + 0.185), (0.095, d + 0.185), (0.112, 0.045), (0.112, -0.10), (-0.112, -0.10),
                   (-0.112, 0.045)]
        tc = _yz_prism("timing_cover", cover_o, -0.245, -0.215, self.col, M.cast_aluminium())
        geo.bevel(tc, 0.006, 3, 40)
        self.static.append(tc)
        pul = geo.lathe("crank_pulley", [(0, 0), (0.07, 0), (0.07, 0.004), (0.064, 0.008), (0.07, 0.012),
                                         (0.064, 0.016), (0.07, 0.020), (0.07, 0.024), (0.03, 0.027), (0, 0.027)],
                        96, self.col, M.cast_iron())
        _rot(pul, -90, "Y")
        _at(pul, -0.247)
        self.pulley = pul
        self.moving.append(pul)

    def _head(self):
        k, d = self.k, self.deck
        head = geo.box("head", (0.43, 0.20, 0.13), (0, 0, d + 0.065), self.col, M.cast_aluminium())
        geo.bevel(head, 0.005, 3, 40)
        bay = geo.box("bay", (0.41, 0.17, 0.10), (0, 0, d + 0.098 + 0.05))
        geo.boolean(head, bay)
        cam_c = {s: self.face(0, 1, s) + AX[s] * S_CAM for s in ("in", "ex")}
        self.cam_yz = {s: (cam_c[s].y, cam_c[s].z) for s in cam_c}
        self.cam_journals = [self.xs[0] - 0.040] + [(self.xs[i] + self.xs[i + 1]) / 2 for i in range(3)] + \
                            [self.xs[3] + 0.040]
        for s, (cy, cz) in self.cam_yz.items():           # cam towers with their bearing bores
            for xj in self.cam_journals:
                tower = geo.box("tower", (0.016, 0.044, cz - (d + 0.098) + 0.016), (xj, cy, (cz + d + 0.098) / 2 + 0.008))
                geo.boolean(head, tower, "UNION")
        for x in self.xs:
            geo.boolean(head, _at(geo.cylinder("plug_tube", 0.0145, d + 0.05, d + 0.132, 40), x), "UNION")
        for s, (cy, cz) in self.cam_yz.items():
            geo.boolean(head, _at(_x_cyl("cam_bore", 0.0138, -0.3, 0.3, 48), 0, cy, cz))
        for i, x in enumerate(self.xs):
            dome = geo.lathe("dome", [(0, d - 0.003), (k.bore / 2 - 0.0004, d - 0.003), (k.bore / 2 - 0.0004, d + 0.001),
                                      (k.bore / 2 - 0.006, d + 0.0075), (0, d + ROOF_DZ)], 64)
            geo.boolean(head, _at(dome, x))
            for s, (mouth_y, r) in (("in", (-0.107, 0.0125)), ("ex", (0.107, 0.0115))):
                sy = 1 if s == "ex" else -1
                for side in (-1, 1):
                    f = self.face(i, side, s)
                    pts = [(x + side * 0.0105, mouth_y, d + (0.062 if s == "in" else 0.055)),
                           (x + side * 0.012, sy * 0.075, d + (0.052 if s == "in" else 0.046)),
                           (x + side * 0.016, sy * 0.045, d + (0.036 if s == "in" else 0.032)),
                           tuple(f + AX[s] * 0.011), (f.x, f.y, d + 0.004)]
                    geo.boolean(head, geo.sweep("port", pts, r, segments=20))
                    geo.boolean(head, _axis_cyl("guide", 0.0034, f, AX[s], 0.008, 0.062, 20))
                    geo.boolean(head, _axis_cyl("bucket_bore", 0.0158, f, AX[s], S_SEAT - 0.002, 0.15, 40))
            geo.boolean(head, _at(geo.cylinder("well", 0.0115, d + 0.034, d + 0.2, 40), x))
            geo.boolean(head, _at(geo.cylinder("thread", 0.0071, d - 0.01, d + 0.036, 32), x))
        geo.shade(head, 40)
        self.head = head
        self.static.append(head)
        vc = geo.box("valve_cover", (0.42, 0.18, 0.056), (0, 0, d + 0.13 + 0.028), self.col,
                     M.paint("#15181d", 0.5, True))
        geo.bevel(vc, 0.012, 4, 40)
        geo.boolean(vc, geo.box("vc_in", (0.41, 0.17, 0.056), (0, 0, d + 0.13 + 0.024)))
        for x in self.xs:
            geo.boolean(vc, _at(geo.cylinder("coil_hole", 0.0160, d + 0.1, d + 0.25, 32), x))
        self.cover = vc
        self.static.append(vc)
        for x in (self.xs[0] - 0.048, self.xs[1] + 0.048, self.xs[3] + 0.048, self.xs[2] - 0.048):
            for sy in (-1, 1):
                b = geo.hex_bolt("cover_bolt", 0.006, 0.02, self.col, M.dark_steel())
                _at(b, x, sy * 0.075, d + 0.186)
                self.static.append(b)

    # ------------------------------------------------------------ moving parts
    def _valvetrain(self):
        self.valves = []                                   # (cyl, side, s, objects...)
        for i in range(4):
            for s in ("in", "ex"):
                for side in (-1, 1):
                    f = self.face(i, side, s)
                    q = Vector((0, 0, 1)).rotation_difference(AX[s])
                    v = P.valve(f"valve_{s}_{i + 1}{'ab'[side > 0]}", VALVE_D[s], col=self.col)
                    sp = P.valve_spring(f"spring_{s}_{i + 1}{'ab'[side > 0]}", SPRING_LEN, col=self.col)
                    rt = P.retainer(f"retainer_{s}_{i + 1}{'ab'[side > 0]}", col=self.col)
                    bk = P.bucket(f"bucket_{s}_{i + 1}{'ab'[side > 0]}", col=self.col)
                    for o in (v, sp, rt, bk):
                        o.rotation_mode = "QUATERNION"
                        o.rotation_quaternion = q
                    sp.location = f + AX[s] * S_SEAT
                    self.valves.append({"cyl": i, "s": s, "side": side, "face": f, "valve": v, "spring": sp,
                                        "retainer": rt, "bucket": bk})
                    self.moving += [v, sp, rt, bk]
        self.cams = {}
        for s in ("in", "ex"):
            open_deg, close_deg = K.INTAKE if s == "in" else K.EXHAUST
            _, peak = K.cam_profile(open_deg, close_deg, 0.0175, 0.0095, steps=8)
            contact = math.degrees(math.atan2(-AX[s].z, -AX[s].y))
            lobe_xs, phases = [], []
            for i in range(4):
                for side in (-1, 1):
                    lobe_xs.append(self.xs[i] + side * VALVE_DX[s])
                    phases.append(contact + (peak + self.k.CYCLE_OFFSETS[i]) / 2)
            cam = P.camshaft(f"cam_{s}", self.k, self.xs[0] - 0.07, self.xs[3] + 0.06, lobe_xs, phases,
                             (open_deg, close_deg), self.cam_journals, col=self.col)
            cy, cz = self.cam_yz[s]
            cam.location = (0, cy, cz)
            self.cams[s] = cam
            self.moving.append(cam)
            sprocket = geo.lathe(f"cam_sprocket_{s}", [(0, 0), (0.05, 0), (0.05, 0.010), (0, 0.010)], 40, self.col,
                                 M.dark_steel())
            _rot(sprocket, -90, "Y")
            _at(sprocket, self.xs[0] - 0.072)
            sprocket.parent = cam

    def _bottom_end(self):
        k = self.k
        self.crank, _ = P.crankshaft("crankshaft", k, col=self.col)
        self.moving.append(self.crank)
        self.flywheel = P.flywheel("flywheel", self.mains[4] + 0.024, col=self.col)
        self.moving.append(self.flywheel)
        self.pistons, self.rods = [], []
        for i, x in enumerate(self.xs):
            p, rings, pin = P.piston(f"piston_{i + 1}", k.bore, k.ch, col=self.col)
            r, rparts = P.conrod(f"conrod_{i + 1}", k.rod, col=self.col)
            p.location.x = x
            r.location.x = x
            self.pistons.append(p)
            self.rods.append(r)
            self.moving += [p, *rings, pin, r, *rparts]

    def _ignition(self):
        d = self.deck
        self.plugs = []
        self.sparks = []
        smat = spark_material()
        for i, x in enumerate(self.xs):
            plug = P.spark_plug(f"spark_plug_{i + 1}", col=self.col)
            plug.location = (x, 0, d + ROOF_DZ - 0.002)
            c = P.coil(f"coil_{i + 1}", col=self.col)
            c.location = (x, 0, d + 0.091)
            self.plugs.append(plug)
            self.static += [plug, *plug.children, c, *c.children]
            dot = geo.lathe(f"spark_{i + 1}", [(0, -0.0016), (0.0016, 0), (0, 0.0016)], 12, self.col, smat)
            dot.location = (x, 0, d + ROOF_DZ - 0.0035)
            dot["glow"] = 0.0
            dot["no_occlude"] = 1
            ld = bpy.data.lights.new(f"spark_light_{i + 1}", "POINT")
            ld.color = (0.75, 0.88, 1.0)
            ld.shadow_soft_size = 0.002
            ld.energy = 0.0
            lo = bpy.data.objects.new(f"spark_light_{i + 1}", ld)
            self.col.objects.link(lo)
            lo.location = (x, 0, d + 0.002)
            self.sparks.append((dot, lo))
            fl = bpy.data.lights.new(f"flame_light_{i + 1}", "POINT")
            fl.color = (1.0, 0.55, 0.18)
            fl.shadow_soft_size = 0.02
            fl.energy = 0.0
            flo = bpy.data.objects.new(f"flame_light_{i + 1}", fl)
            self.col.objects.link(flo)
            flo.location = (x, 0, d - 0.01)
            self.cyl[i]["flame_light"] = flo

    def _manifolds(self):
        d = self.deck
        im_mat = M.plastic("#1c1f24", 0.38)
        runners = []
        for x in self.xs:
            pts = [(x, -0.1045, d + 0.060), (x, -0.150, d + 0.066), (x, -0.205, d + 0.030), (x * 0.9, -0.226, d - 0.035)]
            o = geo.sweep("runner", pts, 0.0215, self.col, im_mat, segments=24)
            geo.boolean(o, geo.sweep("runner_in", [(x, -0.098, d + 0.060)] + pts[1:-1] + [(x * 0.9, -0.24, d - 0.06)],
                                     0.0178, segments=24))
            runners.append(o)
        plenum = geo.box("plenum", (0.40, 0.075, 0.085), (0, -0.236, d - 0.060), self.col, im_mat, fillet=0.018)
        geo.boolean(plenum, geo.box("plenum_in", (0.39, 0.065, 0.075), (0, -0.236, d - 0.060)))
        tb = _x_cyl("throttle_body", 0.032, -0.25, -0.19, 48, self.col, im_mat, chamfer=0.002)
        _at(tb, 0, -0.236, d - 0.060)
        geo.boolean(tb, _at(_x_cyl("tb_in", 0.026, -0.3, -0.15, 48), 0, -0.236, d - 0.060))
        flange = geo.box("im_flange", (0.40, 0.010, 0.050), (0, -0.105, d + 0.060), self.col, im_mat, fillet=0.002)
        for x in self.xs:
            geo.boolean(flange, _at(geo.aim_z(geo.cylinder("fh", 0.0178, -0.05, 0.05, 32), (0, 1, 0)), x, -0.105,
                                    d + 0.060))
        self.static += runners + [plenum, tb, flange]
        self.intake_parts = runners + [plenum, tb, flange]
        ex_mat = heat_tint()
        ex = []
        for i, x in enumerate(self.xs):
            pts = [(x, 0.1045, d + 0.055), (x, 0.140, d + 0.050), (x * 0.55 + 0.01, 0.175, d - 0.020),
                   (0.012, 0.190, d - 0.110)]
            o = geo.sweep("ex_runner", pts, 0.0185, self.col, ex_mat, segments=24)
            geo.boolean(o, geo.sweep("ex_in", [(x, 0.098, d + 0.055)] + pts[1:-1] + [(0.012, 0.192, d - 0.13)],
                                     0.0152, segments=24))
            ex.append(o)
        coll = geo.sweep("ex_collector", [(0.012, 0.190, d - 0.095), (0.012, 0.192, d - 0.20), (0.03, 0.20, d - 0.32)],
                         0.028, self.col, ex_mat, segments=28)
        geo.boolean(coll, geo.sweep("coll_in", [(0.012, 0.190, d - 0.08), (0.012, 0.192, d - 0.20),
                                                (0.03, 0.20, d - 0.34)], 0.024, segments=28))
        exf = geo.box("ex_flange", (0.40, 0.010, 0.044), (0, 0.105, d + 0.055), self.col, ex_mat, fillet=0.002)
        for x in self.xs:
            geo.boolean(exf, _at(geo.aim_z(geo.cylinder("eh", 0.0152, -0.05, 0.05, 32), (0, 1, 0)), x, 0.105,
                                 d + 0.055))
        self.static += ex + [coll, exf]
        self.exhaust_parts = ex + [coll, exf]

    def _gas(self):
        gm = gas_material()
        k = self.k
        for i, x in enumerate(self.xs):
            g = geo.cylinder(f"gas_{i + 1}", k.bore / 2 - 0.0006, 0.0, 1.0, 48, self.col, gm)
            g.location = (x, 0, 0.0)
            g["gas_color"] = (0.5, 0.7, 1.0)
            g["gas_density"] = 0.0
            g["gas_glow"] = 0.0
            g["flame_r"] = 0.0
            g["flame_k"] = 0.0
            g["flame_o"] = (x, 0.0, self.deck + ROOF_DZ - 0.002)
            g["no_occlude"] = 1
            self.cyl[i]["gas"] = g
            self.fx.append(g)
            for s in ("in", "ex"):
                f = self.face(i, 1, s)
                fb = self.face(i, -1, s)
                sy = 1 if s == "ex" else -1
                pts = [(x, sy * 0.104, self.deck + (0.062 if s == "in" else 0.055)),
                       (x, sy * 0.075, self.deck + (0.052 if s == "in" else 0.046)),
                       (x, sy * 0.045, self.deck + (0.036 if s == "in" else 0.032)),
                       ((f.x + fb.x) / 2, f.y + AX[s].y * 0.011, f.z + AX[s].z * 0.011)]
                pg = geo.sweep(f"port_gas_{s}_{i + 1}", pts, 0.0105 if s == "in" else 0.0098, self.col, gm, segments=16)
                pg["gas_color"] = GAS["intake" if s == "in" else "exhaust"][0]
                pg["gas_density"] = 0.0
                pg["gas_glow"] = 0.0
                pg["flame_r"] = 0.0
                pg["flame_k"] = 0.0
                pg["flame_o"] = (0.0, 0.0, -1.0)
                pg["no_occlude"] = 1
                self.cyl[i][f"port_gas_{s}"] = pg
                self.fx.append(pg)
        self._flows()

    def _flows(self):
        """Streams a viewer can follow: air from the throttle through the manifold and port into each cylinder,
        fuel sprayed by the injector at the intake valves, burnt gas out through the exhaust port and manifold.
        Each runs only while its valve is open (flow_on), at a pace tied to the crank."""
        d = self.deck
        self.flows = []
        for i, x in enumerate(self.xs):
            air = [(-0.27, -0.236, d - 0.060), (min(-0.2, x * 0.9 - 0.03), -0.236, d - 0.060),
                   (x * 0.9, -0.234, d - 0.052), (x * 0.9, -0.226, d - 0.035), (x, -0.205, d + 0.030),
                   (x, -0.170, d + 0.062), (x, -0.150, d + 0.066), (x, -0.1045, d + 0.060), (x, -0.075, d + 0.052),
                   (x, -0.045, d + 0.036), (x, -0.022, d + 0.016), (x, -0.006, d - 0.012), (x, 0.004, d - 0.040)]
            ex = [(x, 0.0, d - 0.030), (x, 0.010, d + 0.004), (x, 0.026, d + 0.022), (x, 0.045, d + 0.032),
                  (x, 0.075, d + 0.046), (x, 0.1045, d + 0.055), (x, 0.140, d + 0.050),
                  (x * 0.55 + 0.01, 0.175, d - 0.020), (0.012, 0.190, d - 0.110), (0.012, 0.192, d - 0.200),
                  (0.03, 0.20, d - 0.32)]
            spray = [(x, -0.110, d + 0.063), (x, -0.090, d + 0.055), (x, -0.066, d + 0.046),
                     (x, -0.042, d + 0.033), (x, -0.024, d + 0.018)]
            fa = Flow(f"flow_air_{i + 1}", air, count=110, spread=0.0065, size=0.0021, stretch=2.6, closed=False,
                      ramp=((0.0, "#4fb6ff"), (1.0, "#a6ecff")), strength=5.0, col=self.col, seed=11 + i,
                      gated=True)
            fe = Flow(f"flow_exhaust_{i + 1}", ex, count=110, spread=0.0065, size=0.0023, stretch=2.6, closed=False,
                      ramp=((0.0, "#ff9a3c"), (0.3, "#b08a70"), (1.0, "#6e665f")), strength=3.2, col=self.col,
                      seed=31 + i, gated=True)
            ff = Flow(f"flow_fuel_{i + 1}", spray, count=60, spread=0.0042, size=0.0011, stretch=2.0, closed=False,
                      ramp=((0.0, "#fff6c8"), (1.0, "#f0d860")), strength=5.0, col=self.col, seed=51 + i,
                      gated=True)
            self.cyl[i]["flows"] = {"air": fa, "exhaust": fe, "fuel": ff}
            self.flows += [fa, fe, ff]

    def _coolant(self):
        d = self.deck
        c = geo.prism("coolant", geo.tangent_hull((self.xs[0], 0), 0.0560, (self.xs[3], 0), 0.0560, 40), 0.1155,
                      d - 0.0015, self.col, _liquid("coolant", "#29b6c8", 0.7))
        geo.boolean(c, geo.prism("cool_i", geo.tangent_hull((self.xs[0], 0), 0.0510, (self.xs[3], 0), 0.0510, 40),
                                 0.10, d + 0.01))
        self.coolant = c
        self.static.append(c)

    def _oil(self):
        o = _yz_prism("oil", [(-0.0905, -0.161), (0.0905, -0.161), (0.093, -0.148), (-0.093, -0.148)], -0.206, 0.206,
                      self.col, _liquid("oil", "#3a2608", 0.15, 0.05))
        self.oil = o
        self.static.append(o)

    def _dress(self):
        """What makes the outside read as a real engine: cover ribs and filler cap, coil harness, fuel rail
        and injectors, the front accessory drive and its belt, oil filter, mounts, freeze plugs, dipstick."""
        d, col = self.deck, self.col
        top = d + 0.186
        parts = []
        for y in (-0.075, -0.055, -0.035, 0.035, 0.055, 0.075):          # cast ribs on the valve cover
            rib = geo.box("cover_rib", (0.30, 0.006, 0.009), (0.0, y, top + 0.0035), col,
                          M.paint("#15181d", 0.5, True), fillet=0.0025)
            parts.append(rib)
        cap = geo.lathe("filler_cap", [(0, 0), (0.026, 0), (0.026, 0.004)] +
                        [p for k in range(18) for p in ((0.026, 0.004 + k * 0.0008), (0.0275, 0.0044 + k * 0.0008))] +
                        [(0.026, 0.020), (0.022, 0.022), (0, 0.022)], 72, col, M.anodized("#1f6fa8"))
        _at(cap, 0.135, -0.052, top)
        parts.append(cap)
        loom = geo.sweep("coil_loom", [(self.xs[0] - 0.05, 0.03, top + 0.03)] +
                         [(x + 0.036, 0.03, top + 0.036) for x in self.xs] + [(self.xs[3] + 0.08, 0.05, top + 0.02),
                                                                                (self.xs[3] + 0.11, 0.08, d + 0.12)],
                         0.0055, col, M.rubber("#101113"), segments=12)
        parts.append(loom)
        # fuel rail with four injectors into the runners
        rail = _x_cyl("fuel_rail", 0.0095, -0.205, 0.195, 32, col, M.brushed_steel(), chamfer=0.001)
        _at(rail, 0, -0.118, d + 0.098)
        parts.append(rail)
        for x in self.xs:
            inj = geo.lathe("injector", [(0, 0), (0.0045, 0), (0.0045, 0.006), (0.0075, 0.007), (0.0075, 0.024),
                                         (0.0085, 0.025), (0.0085, 0.029), (0, 0.029)], 32, col, M.plastic("#1d1f23"))
            ring = geo.lathe("inj_oring", [(0.0040, 0.0035), (0.0058, 0.0035), (0.0058, 0.0052), (0.0040, 0.0052),
                                           (0.0040, 0.0035)], 32, col, M.rubber("#2c5fd6"))
            for o in (inj, ring):
                geo.aim_z(o, (0, -0.25, 0.97), (x, -0.111, d + 0.066))
            parts += [inj, ring]
        parts.append(geo.sweep("fuel_line", [(-0.205, -0.118, d + 0.098), (-0.235, -0.13, d + 0.09),
                                             (-0.26, -0.16, d + 0.02), (-0.27, -0.17, d - 0.12)], 0.005, col,
                               M.rubber("#121314"), segments=10))
        # front accessory drive: crank pulley (moving), water pump and alternator pulleys, belt
        wp = (-0.062, 0.168, 0.048)
        alt = (0.168, 0.085, 0.032)
        for (py, pz, pr), name in ((wp, "water_pump_pulley"), (alt, "alternator_pulley")):
            pul = geo.lathe(name, [(0, 0), (pr, 0), (pr, 0.004), (pr - 0.004, 0.008), (pr, 0.012), (pr - 0.004, 0.016),
                                   (pr, 0.020), (pr, 0.024), (pr * 0.4, 0.026), (0, 0.026)], 64, col, M.cast_iron())
            _rot(pul, -90, "Y")
            _at(pul, -0.248, py, pz)
            parts.append(pul)
        body = _x_cyl("alternator", 0.058, -0.236, -0.152, 64, col, M.cast_aluminium(), chamfer=0.006)
        _at(body, 0, alt[0], alt[1])
        for k in range(14):                                   # cooling slots
            a = math.tau * k / 14
            slot = geo.box("alt_slot", (0.05, 0.014, 0.006), (0.0, 0.0, 0.058))
            geo.transform_mesh(slot, Matrix.Translation((-0.2, alt[0], alt[1])) @ Matrix.Rotation(a, 4, "X"))
            geo.boolean(body, slot)
        parts.append(body)
        shaft = _x_cyl("alt_shaft", 0.008, -0.25, -0.23, 24, col, M.brushed_steel())
        _at(shaft, 0, alt[0], alt[1])
        parts.append(shaft)
        parts.append(geo.box("alt_bracket", (0.05, 0.05, 0.03), (-0.19, 0.122, 0.07), col, M.cast_aluminium(),
                             fillet=0.004))
        belt_pts = belt_outline([(0.0, 0.0, 0.070), (wp[0], wp[1], wp[2]), (alt[0], alt[1], alt[2])], 0.0035)
        inner = belt_outline([(0.0, 0.0, 0.070), (wp[0], wp[1], wp[2]), (alt[0], alt[1], alt[2])], -0.0005)
        belt = _yz_prism("belt", belt_pts, -0.270, -0.250, col, M.rubber("#0f1012"))
        geo.boolean(belt, _yz_prism("belt_in", inner, -0.28, -0.24))
        parts.append(belt)
        # oil filter on the intake side, mounts, freeze plugs, dipstick
        filt = geo.lathe("oil_filter", [(0, 0), (0.030, 0), (0.036, 0.004), (0.038, 0.012)] +
                         [p for k in range(14) for p in ((0.038, 0.014 + k * 0.0018), (0.0395, 0.0149 + k * 0.0018))] +
                         [(0.038, 0.085), (0.034, 0.092), (0, 0.093)], 72, col, M.paint("#1b2a44", 0.28))
        geo.aim_z(filt, (0, -1, -0.35), (0.05, -0.112, 0.0))
        parts.append(filt)
        for x, s in ((-0.13, -1), (0.14, -1), (0.12, 1)):
            parts.append(geo.box("mount", (0.05, 0.028, 0.05), (x, s * 0.126, -0.03), col, M.cast_iron(), fillet=0.004))
            bush = _x_cyl("mount_rubber", 0.016, x - 0.03, x + 0.03, 32, col, M.rubber())
            _at(bush, 0, s * 0.148, -0.03)
            parts.append(bush)
        for x in (-0.096, 0.0, 0.096):
            for s in (-1, 1):
                plug = geo.lathe("freeze_plug", [(0, 0), (0.016, 0), (0.016, 0.003), (0.013, 0.004), (0, 0.004)], 40,
                                 col, M.brushed_steel())
                geo.aim_z(plug, (0, s, 0), (x, s * 0.0955, 0.15))
                parts.append(plug)
        parts.append(geo.sweep("dipstick", [(0.19, 0.112, 0.01), (0.195, 0.124, 0.12), (0.198, 0.124, 0.28),
                                            (0.198, 0.12, d + 0.17)], 0.0045, col, M.brushed_steel(), segments=10))
        # pan rail lip and its bolt row, head gasket line, lifting eyes
        lip = geo.box("pan_rail", (0.43, 0.236, 0.008), (0, 0, -0.0675), col, M.cast_aluminium(), fillet=0.002)
        parts.append(lip)
        for x in [-0.19 + 0.0543 * k for k in range(8)]:
            for s in (-1, 1):
                b = geo.hex_bolt("pan_bolt", 0.007, 0.012, col, M.dark_steel())
                _rot(b, 180, "X")
                _at(b, x, s * 0.106, -0.0805)
                parts.append(b)
        gasket = geo.box("head_gasket", (0.433, 0.204, 0.0028), (0, 0, d + 0.0002), col, M.gasket())
        geo.boolean(gasket, geo.box("hg_in", (0.42, 0.186, 0.01), (0, 0, d)))
        parts.append(gasket)
        for x in (-0.2, 0.2):
            eye = geo.sweep("lifting_eye", [(x + 0.022 * math.cos(a), 0.062, d + 0.150 + 0.022 * math.sin(a))
                                            for a in [math.tau * k / 20 for k in range(21)]], 0.0055, col,
                            M.paint("#2a2d31", 0.5), segments=10)
            plate = geo.box("eye_plate", (0.05, 0.012, 0.03), (x, 0.062, d + 0.122), col, M.paint("#2a2d31", 0.5),
                            fillet=0.002)
            parts += [eye, plate]
        # thermostat housing and the upper hose leaving the rear of the head
        thermo = geo.box("thermostat_housing", (0.034, 0.05, 0.046), (0.232, -0.055, d + 0.06), col,
                         M.cast_aluminium(), fillet=0.006)
        neck = _x_cyl("thermo_neck", 0.019, 0.245, 0.27, 32, col, M.cast_aluminium(), chamfer=0.002)
        _at(neck, 0, -0.055, d + 0.06)
        hose = geo.sweep("upper_hose", [(0.262, -0.055, d + 0.06), (0.30, -0.055, d + 0.055),
                                        (0.33, -0.03, d - 0.02), (0.345, 0.0, -0.06)], 0.0185, col,
                         M.rubber("#141516"), segments=20)
        clamp = _x_cyl("hose_clamp", 0.0205, 0.258, 0.266, 32, col, M.brushed_steel())
        _at(clamp, 0, -0.055, d + 0.06)
        parts += [thermo, neck, hose, clamp]
        # knock sensor with its lead
        ks = geo.lathe("knock_sensor", [(0, 0), (0.013, 0), (0.013, 0.01), (0.009, 0.014), (0.009, 0.02), (0, 0.02)],
                       6, col, M.plastic("#1b1d21"))
        geo.aim_z(ks, (0, -1, 0), (-0.005, -0.103, 0.085))
        lead = geo.sweep("ks_lead", [(-0.005, -0.12, 0.085), (0.0, -0.15, 0.1), (0.03, -0.16, 0.16)], 0.003, col,
                         M.rubber("#101113"), segments=8)
        parts += [ks, lead]
        # cast badge on the valve cover's intake side
        cu = bpy.data.curves.new("badge_txt", "FONT")
        cu.body = "DOHC 16V"
        cu.size = 0.019
        cu.extrude = 0.0012
        cu.align_x = "CENTER"
        cu.align_y = "CENTER"
        tob = bpy.data.objects.new("badge_txt", cu)
        bpy.context.scene.collection.objects.link(tob)
        dg = bpy.context.evaluated_depsgraph_get()
        tme = bpy.data.meshes.new_from_object(tob.evaluated_get(dg), depsgraph=dg)
        bpy.data.objects.remove(tob, do_unlink=True)
        txt = bpy.data.objects.new("badge_text", tme)
        col.objects.link(txt)
        tme.materials.append(M.brushed_steel())
        geo.transform_mesh(txt, Matrix.Translation((-0.03, -0.0935, d + 0.158)) @ Matrix.Rotation(math.radians(90), 4, "X"))
        plate = geo.box("badge_plate", (0.13, 0.003, 0.03), (-0.03, -0.0912, d + 0.158), col, M.paint("#141619", 0.35),
                        fillet=0.0012)
        parts += [plate, txt]
        handle = geo.sweep("dipstick_handle", [(0.198 + 0.012 * math.cos(a), 0.12, d + 0.183 + 0.012 * math.sin(a))
                                               for a in [math.tau * k / 16 for k in range(17)]], 0.0035, col,
                           M.plastic("#f2c230", 0.35), segments=10)
        parts.append(handle)
        self.static += parts

    def _anchors(self):
        k, d = self.k, self.deck

        def empty(name, loc, parent=None):
            e = bpy.data.objects.new(name, None)
            self.col.objects.link(e)
            e.empty_display_size = 0.01
            if parent is not None:
                e.parent = parent
            e.location = loc
            self.anchors[name] = e
            return e

        for i in range(4):
            empty(f"piston_{i + 1}", (0, 0, k.ch), self.pistons[i])
            empty(f"combustion_chamber_{i + 1}", (self.xs[i], 0, d + 0.004))
            empty(f"spark_plug_tip_{i + 1}", (0, 0, 0), self.plugs[i])
        empty("conrod_1", (0, 0, -k.rod * 0.45), self.rods[0])
        empty("crank_pin_1", (self.xs[0], 0, k.r), self.crank)
        empty("crankshaft", (self.mains[1], 0, 0.0))
        for v in self.valves:
            if v["cyl"] == 0 and v["side"] > 0:
                empty(f"{'intake' if v['s'] == 'in' else 'exhaust'}_valve_1", (0, 0, 0.004), v["valve"])
                empty(f"valve_spring_{v['s']}_1", (0, 0, SPRING_LEN * 0.5), v["spring"])
        empty("camshaft_intake", (self.xs[0] + VALVE_DX["in"], 0, 0), self.cams["in"])
        empty("camshaft_exhaust", (self.xs[0] + VALVE_DX["ex"], 0, 0), self.cams["ex"])
        empty("intake_port_1", (self.xs[0] + 0.012, -0.075, d + 0.052))
        empty("injector_1", (self.xs[0], -0.113, d + 0.074))
        empty("exhaust_port_1", (self.xs[0] + 0.011, 0.075, d + 0.046))
        empty("water_jacket", (self.xs[0], -0.0535, d - 0.03))
        empty("oil_pan", (0, -0.06, -0.14))
        empty("flywheel", (self.mains[4] + 0.04, 0, 0.12))
        empty("throttle_body", (-0.22, -0.236, d - 0.03))
        empty("intake_manifold", (self.xs[1], -0.205, d + 0.03))
        empty("exhaust_manifold", (self.xs[2], 0.16, d + 0.02))
        empty("cylinder_head", (self.xs[2], -0.06, d + 0.09))
        empty("engine_block", (self.xs[2], -0.1, 0.06))

    # ------------------------------------------------------------ animation
    def pose(self, theta: float):
        """Put every moving part where crank angle `theta` (degrees) puts it."""
        k, d = self.k, self.deck
        rot = -math.radians(theta)
        self.crank.rotation_euler.x = rot
        self.flywheel.rotation_euler.x = rot
        self.pulley.rotation_euler.x = rot
        for s, cam in self.cams.items():
            cam.rotation_euler.x = rot / 2
        states = [k.cylinder(i, theta) for i in range(4)]
        for i, st in enumerate(states):
            self.pistons[i].location.z = st["pin_z"]
            self.rods[i].location.z = st["pin_z"]
            self.rods[i].rotation_euler.x = st["rod_tilt"]
            crown = st["pin_z"] + k.ch
            g = self.cyl[i]["gas"]
            g.location.z = crown
            g.scale.z = max(0.001, d + ROOF_DZ * 0.7 - crown)
            stroke = st["stroke"]
            colr, dens, _ = GAS[stroke]
            c = st["cycle"]
            glow, flame_r, flame_k = 0.0, 0.0, 0.0
            if stroke == "intake":
                dens *= 0.35 + 0.65 * min(1.0, c / 90.0)
            elif stroke == "compression":
                dens = GAS["intake"][1] + (dens - GAS["intake"][1]) * (c - 180.0) / 180.0
            if K.SPARK <= c < 540.0:                        # flame front from the plug, then the burnt charge
                flame_r = 0.075 * _smooth((c - K.SPARK) / 30.0)
                flame_k = 1.0 - _smooth((c - 395.0) / 80.0)
                cool = _smooth((c - 385.0) / 150.0)
                colr = tuple(a + (b - a) * cool for a, b in zip(GAS["power"][0], BURNT))
                dens = GAS["power"][1]
                glow = 40.0 * st["combustion"]
                if c < K.SPARK + 30.0:                      # unburnt charge around the growing flame stays blue
                    colr, dens = GAS["compression"][0], GAS["compression"][1]
            g["gas_color"] = colr
            g["gas_density"] = dens
            g["gas_glow"] = glow
            g["flame_r"] = flame_r
            g["flame_k"] = flame_k
            self.cyl[i]["flame_light"].data.energy = 14.0 * st["combustion"]
            self.cyl[i]["flame_light"].location.z = (crown + d) / 2
            pin, pex = self.cyl[i]["port_gas_in"], self.cyl[i]["port_gas_ex"]
            pin["gas_density"] = 1.2 * min(1.0, st["intake_lift"] / 0.004)
            pex["gas_density"] = 1.4 * min(1.0, st["exhaust_lift"] / 0.004)
            fl = self.cyl[i]["flows"]
            fl["air"].set_phase(theta / 240.0)
            fl["air"].obj["flow_on"] = min(1.0, st["intake_lift"] / 0.0025)
            fl["fuel"].set_phase(theta / 80.0)
            fl["fuel"].obj["flow_on"] = min(1.0, st["intake_lift"] / 0.0025)
            fl["exhaust"].set_phase(theta / 220.0)
            fl["exhaust"].obj["flow_on"] = min(1.0, st["exhaust_lift"] / 0.0025)
            dot, light = self.sparks[i]
            dot["glow"] = 400.0 * st["spark"]
            light.data.energy = 6.0 * st["spark"]
        for v in self.valves:
            st = states[v["cyl"]]
            lift = st["intake_lift"] if v["s"] == "in" else st["exhaust_lift"]
            ax = AX[v["s"]]
            f = v["face"]
            v["valve"].location = f - ax * lift
            v["retainer"].location = f + ax * (S_RET - lift)
            v["bucket"].location = f + ax * (S_BUCKET - lift)
            v["spring"].scale.z = (SPRING_LEN - lift) / SPRING_LEN

    def animated(self) -> list:
        """Objects whose transform or properties change with the crank (for keyframing)."""
        objs = [self.crank, self.flywheel, self.pulley, *self.cams.values(), *self.pistons, *self.rods]
        for v in self.valves:
            objs += [v["valve"], v["retainer"], v["bucket"], v["spring"]]
        for i in range(4):
            objs += [self.cyl[i]["gas"], self.cyl[i]["port_gas_in"], self.cyl[i]["port_gas_ex"],
                     self.cyl[i]["flame_light"]]
        for dot, light in self.sparks:
            objs += [dot, light]
        objs += [f.obj for f in self.flows]
        return objs

    # ------------------------------------------------------------ vocabulary for shot planning
    STUDIO = {"floor_z": -0.175, "center": (0.0, 0.0, 0.15), "radius": 0.35}
    WIDE = {"hero_34", "hero_low", "exhaust_side", "section_front", "section_wide", "quarter_hero",
            "longitudinal_side", "intake_side"}

    def xray_solid(self) -> list:
        """Static parts that stay solid in the X-ray view: the plugs and injectors (they act on the gas)."""
        keep = [o for p in self.plugs for o in (p, *p.children_recursive)]
        keep += [o for o in self.col.all_objects if o.name.startswith(("injector", "inj_oring"))]
        return keep

    def xray_hidden(self) -> list:
        """Liquids would fog the X-ray view."""
        return [self.coolant, self.oil]

    def visible(self) -> list:
        """Rendered solid parts (for framing): everything not hidden, no gas volumes."""
        out = []
        for o in self.static + self.moving:
            for x in (o, *o.children_recursive):
                if x.type == "MESH" and not x.hide_render and x not in self.fx:
                    out.append(x)
        return out

    def cuts(self) -> dict:
        """Named section cuts: cutter bounds, the peel axis/distance, the parts cut while moving, and the
        side of the engine a camera should look from."""
        x1 = self.xs[0]
        own = self.fx + [self.coolant, self.oil]
        return {
            "transverse_1": {"bounds": ((None, x1), (None, None), (None, None)), "peel": (0, 0.5),
                             "cut_moving": [self.crank], "own_cap": own},
            "longitudinal": {"bounds": ((None, None), (None, 0.0), (None, None)), "peel": (1, 0.45),
                             "cut_moving": [self.crank], "own_cap": own},
            "quarter_1": {"bounds": ((None, x1), (None, 0.0), (None, None)), "peel": (0, 0.5),
                          "cut_moving": [self.crank], "own_cap": own},
        }

    def cameras(self) -> dict:
        """Named camera presets (positions in metres, lens in mm on a 36 mm-tall vertical sensor)."""
        x1, d = self.xs[0], self.deck
        return {
            "hero_34": {"pos": (-0.95, -1.05, 0.62), "target": (0.0, 0.0, 0.14), "lens": 40, "fstop": 8},
            "hero_low": {"pos": (-0.85, -0.80, 0.05), "target": (0.0, 0.0, 0.17), "lens": 32, "fstop": 8},
            "exhaust_side": {"pos": (-0.75, 1.05, 0.48), "target": (0.0, 0.05, 0.14), "lens": 40, "fstop": 8},
            "section_front": {"pos": (-1.25, -0.24, 0.27), "target": (x1, 0.0, 0.13), "lens": 46, "fstop": 6},
            "section_wide": {"pos": (-1.35, -0.75, 0.42), "target": (x1 + 0.05, -0.02, 0.12), "lens": 40, "fstop": 8},
            "chamber_close": {"pos": (-0.50, -0.34, 0.38), "target": (x1, 0.0, d - 0.005), "lens": 55, "fstop": 4},
            "valvetrain_close": {"pos": (-0.52, -0.30, 0.58), "target": (x1, -0.02, d + 0.115), "lens": 55, "fstop": 4},
            "crank_close": {"pos": (-0.62, -0.30, 0.02), "target": (x1, 0.0, 0.03), "lens": 52, "fstop": 4.5},
            "quarter_hero": {"pos": (-0.95, -0.95, 0.50), "target": (x1 + 0.06, -0.02, 0.15), "lens": 42, "fstop": 7},
            "longitudinal_side": {"pos": (0.0, -1.30, 0.17), "target": (0.0, 0.0, 0.14), "lens": 38, "fstop": 8},
            "longitudinal_close": {"pos": (-0.10, -0.75, 0.20), "target": (-0.05, 0.0, 0.17), "lens": 45, "fstop": 5},
            "intake_side": {"pos": (-0.62, -1.05, 0.52), "target": (0.0, -0.10, 0.17), "lens": 40, "fstop": 8},
            "stroke_close": {"pos": (-0.80, -0.05, 0.24), "target": (x1, 0.0, d - 0.045), "lens": 44, "fstop": 6},
            "injector_close": {"pos": (x1 - 0.30, -0.36, d + 0.22), "target": (x1 + 0.01, -0.075, d + 0.045),
                               "lens": 50, "fstop": 11},
            "exhaust_close": {"pos": (x1 - 0.30, 0.42, d + 0.18), "target": (x1 + 0.03, 0.09, d + 0.0), "lens": 44,
                              "fstop": 11},
            "flywheel_close": {"pos": (0.68, -0.52, 0.24), "target": (self.mains[4] + 0.03, 0.0, 0.04), "lens": 50,
                               "fstop": 5},
        }
