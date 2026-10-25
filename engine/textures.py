"""
Procedural PBR surfaces (no image files): painted metal, planks/siding, shingles, corrugated
roofing, doped wing fabric, brushed metal, rubber, straw, wood grain, cloth, tiles.

Patterns use OBJECT coordinates; toy primitives apply their scale, so these are real metres and a
plank is a plank-width wide on any part. Detail is kept above ~1 cm and bump is gentle so nothing
shimmers frame to frame (high-frequency bump = flicker under TAA).
"""
import math

import bpy

from engine import toy

_cache = {}


class _Tree:
    """Tiny node-graph builder around one Principled material."""

    def __init__(self, name):
        self.mat = bpy.data.materials.new(name)
        self.bsdf = toy._principled(self.mat)
        self.nt = self.mat.node_tree
        self.obj = self.nt.nodes.new("ShaderNodeTexCoord").outputs["Object"]
        sep = self.node("ShaderNodeSeparateXYZ", Vector=self.obj)
        self.xyz = {"x": sep.outputs["X"], "y": sep.outputs["Y"], "z": sep.outputs["Z"]}

    def _in(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v, sock)
        else:
            sock.default_value = v

    def node(self, kind, props=None, **inputs):
        nd = self.nt.nodes.new(kind)
        for k, v in (props or {}).items():
            setattr(nd, k, v)
        for k, v in inputs.items():
            self._in(nd.inputs[k.replace("_", " ")], v)
        return nd

    def math(self, op, a, b=0.0, clamp=False):
        nd = self.nt.nodes.new("ShaderNodeMath")
        nd.operation, nd.use_clamp = op, clamp
        self._in(nd.inputs[0], a)
        self._in(nd.inputs[1], b)
        return nd.outputs[0]

    def axis(self, spec):
        """'x' | 'y' | 'z' | 'xy' (x+y: runs along both wall directions of a box)."""
        out = self.xyz[spec[0]]
        for c in spec[1:]:
            out = self.math("ADD", out, self.xyz[c])
        return out

    def vec(self, x, y, z=0.0):
        return self.node("ShaderNodeCombineXYZ", X=x, Y=y, Z=z).outputs["Vector"]

    def noise(self, vector=None, scale=5.0, detail=4.0, rough=0.55):
        return self.node("ShaderNodeTexNoise", Vector=vector if vector is not None else self.obj, Scale=scale,
                         Detail=detail, Roughness=rough).outputs["Fac"]

    def ramp(self, fac, stops):
        nd = self.nt.nodes.new("ShaderNodeValToRGB")
        els = nd.color_ramp.elements
        while len(els) < len(stops):
            els.new(0.5)
        for el, (pos, hexc) in zip(els, stops):
            el.position, el.color = pos, (*toy.srgb(hexc), 1)
        self._in(nd.inputs["Fac"], fac)
        return nd.outputs["Color"]

    def shade(self, color, value):
        """color × brightness factor (value around 1)."""
        return self.node("ShaderNodeHueSaturation", Color=color, Value=value).outputs["Color"]

    def line(self, coord, period, width=0.06):
        """1 on thin seams every `period` metres along coord, 0 elsewhere (soft-edged)."""
        f = self.math("FRACT", self.math("DIVIDE", coord, period))
        d = self.math("MULTIPLY", self.math("ABSOLUTE", self.math("SUBTRACT", f, 0.5)), 2.0)
        return self.math("DIVIDE", self.math("SUBTRACT", d, 1.0 - width), width, clamp=True), f

    def finish(self, color, rough, height=None, strength=0.35, distance=0.02, metallic=0.0, coat=0.0):
        self._in(self.bsdf.inputs["Base Color"], color)
        self._in(self.bsdf.inputs["Roughness"], rough)
        toy._set(self.bsdf, "Metallic", metallic)
        toy._set(self.bsdf, "Coat Weight", coat)
        toy._set(self.bsdf, "Coat Roughness", 0.2)
        if height is not None:
            bump = self.node("ShaderNodeBump", Strength=strength, Distance=distance, Height=height)
            self.nt.links.new(bump.outputs["Normal"], self.bsdf.inputs["Normal"])
        return self.mat


def _cached(fn):
    def wrap(name, *a, **kw):
        if name not in _cache:
            _cache[name] = fn(name, *a, **kw)
        return _cache[name]
    wrap.__doc__ = fn.__doc__
    return wrap


def _vary(t, rough, amount=0.12, scale=2.5):
    """Low-frequency brightness + roughness variation (sun-faded, handled paint)."""
    n = t.noise(scale=scale, detail=3)
    value = t.math("ADD", 1.0 - amount / 2, t.math("MULTIPLY", n, amount))
    r = t.math("ADD", rough - 0.06, t.math("MULTIPLY", t.noise(scale=scale * 6, detail=5), 0.12))
    return value, r


@_cached
def paint(name, hexc, rough=0.35, coat=0.5, seams=None, seam_axis="x", metallic=0.0):
    """Painted panels: soft colour variation, fine orange-peel, optional panel seams every `seams` m."""
    t = _Tree(name)
    value, r = _vary(t, rough)
    height = t.math("MULTIPLY", t.noise(scale=45, detail=2), 0.15)
    if seams:
        seam, _ = t.line(t.axis(seam_axis), seams, width=0.035)
        value = t.math("SUBTRACT", value, t.math("MULTIPLY", seam, 0.35))
        height = t.math("SUBTRACT", height, seam)
    return t.finish(t.shade(toy.srgb(hexc) + (1,), value), r, height, strength=0.3, metallic=metallic, coat=coat)


@_cached
def planks(name, hex_a, hex_b, width=0.22, across="xy", along="z", lap=False, rough=0.7, seam_dark=0.45):
    """Boards side by side `width` wide across one axis, grain running along another. lap=True gives
    overlapping clapboard siding (sawtooth relief + shadow line)."""
    t = _Tree(name)
    u = t.math("DIVIDE", t.axis(across), width)
    board = t.math("FLOOR", u)
    seam, f = t.line(t.axis(across), width, width=0.07)
    pick = t.node("ShaderNodeTexWhiteNoise", props={"noise_dimensions": "1D"}, W=board).outputs["Value"]
    base = t.ramp(pick, [(0.0, hex_a), (1.0, hex_b)])
    grain = t.noise(t.vec(t.math("MULTIPLY", u, 3.0), t.math("MULTIPLY", board, 2.3),
                          t.math("MULTIPLY", t.axis(along), 0.35)), scale=7, detail=6, rough=0.6)
    value = t.math("ADD", 0.82, t.math("MULTIPLY", grain, 0.36))
    if lap:
        shadow = t.math("LESS_THAN", f, 0.07)
        value = t.math("SUBTRACT", value, t.math("MULTIPLY", shadow, seam_dark))
        height = t.math("ADD", f, t.math("MULTIPLY", grain, 0.2))
    else:
        value = t.math("SUBTRACT", value, t.math("MULTIPLY", seam, seam_dark))
        height = t.math("SUBTRACT", t.math("MULTIPLY", grain, 0.35), seam)
    r = t.math("ADD", rough - 0.08, t.math("MULTIPLY", grain, 0.16))
    return t.finish(t.shade(base, value), r, height, strength=0.4, distance=0.03)


@_cached
def wood(name, hex_a, hex_b, along="z", rough=0.55, scale=6.0):
    """Solid wood grain streaking along one local axis (props, posts, handles)."""
    t = _Tree(name)
    s = {"x": (0.25, 3, 3), "y": (3, 0.25, 3), "z": (3, 3, 0.25)}[along]
    v = t.vec(*(t.math("MULTIPLY", t.xyz[c], k) for c, k in zip("xyz", s)))
    wave = t.node("ShaderNodeTexWave", props={"wave_type": "BANDS", "bands_direction": "X" if along != "x" else "Y"},
                  Vector=v, Scale=scale, Distortion=6.0, Detail=3.0).outputs["Fac"]
    col = t.ramp(wave, [(0.2, hex_a), (0.8, hex_b)])
    return t.finish(col, rough, t.math("MULTIPLY", wave, 0.4), strength=0.25)


@_cached
def shingles(name, hexc, hex_dark, row=0.22, rough=0.75):
    """Overlapping roof shingles on the part's local XY plane (rows across local Y)."""
    t = _Tree(name)
    br = t.node("ShaderNodeTexBrick", Vector=t.vec(t.xyz["x"], t.xyz["y"]), Color1=(*toy.srgb(hexc), 1),
                Color2=(*toy.srgb(hex_dark), 1), Mortar=(*toy.srgb(hex_dark), 1), Scale=1.0, Mortar_Size=0.012,
                Bias=0.0, Brick_Width=row * 1.6, Row_Height=row)
    value, r = _vary(t, rough, amount=0.18, scale=4)
    _, f = t.line(t.xyz["y"], row)
    height = t.math("SUBTRACT", f, t.math("MULTIPLY", br.outputs["Fac"], 0.8))
    return t.finish(t.shade(br.outputs["Color"], value), r, height, strength=0.45, distance=0.03)


@_cached
def corrugated(name, hexc, pitch=0.12, axis="x", rust="#8A4B2A", rough=0.42):
    """Corrugated metal roofing: sine ridges every `pitch` m across `axis`, with rust patches."""
    t = _Tree(name)
    ridge = t.math("SINE", t.math("MULTIPLY", t.axis(axis), 2 * math.pi / pitch))
    patches = t.noise(scale=1.4, detail=6, rough=0.65)
    col = t.ramp(patches, [(0.58, hexc), (0.74, rust)])
    value, r = _vary(t, rough, amount=0.14, scale=3)
    r = t.math("ADD", r, t.math("MULTIPLY", patches, 0.25))
    return t.finish(t.shade(col, value), r, ridge, strength=0.5, distance=0.025, metallic=0.55)


@_cached
def fabric(name, hexc, rib=0.38, axis="y", rough=0.55, coat=0.25):
    """Doped aircraft fabric stretched over ribs: taut tape lines every `rib` m with a slight sag
    between them, and a faint weave."""
    t = _Tree(name)
    tape, f = t.line(t.axis(axis), rib, width=0.08)
    sag = t.math("SINE", t.math("MULTIPLY", f, math.pi))
    value, r = _vary(t, rough, amount=0.1, scale=3)
    value = t.math("ADD", value, t.math("MULTIPLY", tape, 0.06))
    height = t.math("ADD", t.math("MULTIPLY", sag, -0.5), t.math("MULTIPLY", t.noise(scale=60, detail=1), 0.08))
    return t.finish(t.shade(toy.srgb(hexc) + (1,), value), r, height, strength=0.35, distance=0.02, coat=coat)


@_cached
def metal(name, hexc, rough=0.3, along="z", metallic=0.9):
    """Brushed metal: roughness streaks along one axis, faint smudges."""
    t = _Tree(name)
    s = {"x": (1, 30, 30), "y": (30, 1, 30), "z": (30, 30, 1)}[along]
    streak = t.noise(t.vec(*(t.math("MULTIPLY", t.xyz[c], k) for c, k in zip("xyz", s))), scale=4, detail=6)
    smudge = t.noise(scale=3, detail=4)
    r = t.math("ADD", rough - 0.1, t.math("ADD", t.math("MULTIPLY", streak, 0.12), t.math("MULTIPLY", smudge, 0.12)))
    value = t.math("ADD", 0.92, t.math("MULTIPLY", smudge, 0.16))
    return t.finish(t.shade(toy.srgb(hexc) + (1,), value), r, t.math("MULTIPLY", streak, 0.1), strength=0.15,
                    metallic=metallic)


@_cached
def rubber(name, hexc="#1F1F21", rough=0.82, tread=0.0):
    """Tyre rubber: matte with scuffs; `tread` > 0 adds grooves around a local-Z axle."""
    t = _Tree(name)
    scuff = t.noise(scale=12, detail=5)
    value = t.math("ADD", 0.85, t.math("MULTIPLY", scuff, 0.35))
    height = t.math("MULTIPLY", scuff, 0.2)
    if tread:
        ang = t.math("ARCTAN2", t.xyz["y"], t.xyz["x"])
        groove = t.math("GREATER_THAN", t.math("SINE", t.math("MULTIPLY", ang, tread)), 0.3)
        height = t.math("SUBTRACT", height, groove)
    return t.finish(t.shade(toy.srgb(hexc) + (1,), value), t.math("ADD", rough - 0.05, t.math("MULTIPLY", scuff, 0.1)),
                    height, strength=0.35)


@_cached
def straw(name, light="#F2DC8A", mid="#E2C25A", dark="#A9822F"):
    """Round hay bale (axis = local Z): swirled rings on the ends, wrapped fibres round the side."""
    t = _Tree(name)
    rings = t.node("ShaderNodeTexWave", props={"wave_type": "RINGS", "rings_direction": "Z"},
                   Vector=t.vec(t.xyz["x"], t.xyz["y"]), Scale=5.0, Distortion=9.0, Detail=4.0,
                   Detail_Scale=2.0).outputs["Fac"]
    fibres = t.noise(t.vec(t.math("MULTIPLY", t.xyz["x"], 2), t.math("MULTIPLY", t.xyz["y"], 2),
                           t.math("MULTIPLY", t.xyz["z"], 22)), scale=3, detail=8, rough=0.7)
    mix = t.math("ADD", t.math("MULTIPLY", rings, 0.5), t.math("MULTIPLY", fibres, 0.5))
    col = t.ramp(mix, [(0.25, dark), (0.5, mid), (0.78, light)])
    return t.finish(col, 0.92, mix, strength=0.6, distance=0.04)


@_cached
def cloth(name, hexc, rough=0.78):
    """Woven clothing: soft colour mottling and a faint twill, no shine."""
    t = _Tree(name)
    value, r = _vary(t, rough, amount=0.14, scale=6)
    twill = t.math("SINE", t.math("MULTIPLY", t.math("ADD", t.xyz["x"], t.xyz["z"]), 2 * math.pi / 0.012))
    return t.finish(t.shade(toy.srgb(hexc) + (1,), value), r, t.math("MULTIPLY", twill, 0.15), strength=0.12,
                    distance=0.005)


@_cached
def tiles(name, hexc, grout="#E8ECEF", size=0.15, rough=0.15, coat=0.6):
    """Square glazed tiles with grout lines on every face: each face gets the grid of the two axes
    it spans (picked by its object-space normal), so walls and floors both tile correctly."""
    t = _Tree(name)
    nrm = t.node("ShaderNodeSeparateXYZ", Vector=t.obj.node.outputs["Normal"]).outputs
    g, cell = 0.0, []
    for c, n in zip("xyz", nrm):
        lc, _ = t.line(t.xyz[c], size, width=0.1)
        spans = t.math("LESS_THAN", t.math("ABSOLUTE", n), 0.5)           # 0 on faces facing this axis
        g = t.math("MAXIMUM", g, t.math("MULTIPLY", lc, spans))
        cell.append(t.math("MULTIPLY", t.math("FLOOR", t.math("DIVIDE", t.xyz[c], size)), spans))
    pick = t.node("ShaderNodeTexWhiteNoise", props={"noise_dimensions": "3D"},
                  Vector=t.vec(*cell)).outputs["Value"]
    value = t.math("ADD", 0.93, t.math("MULTIPLY", pick, 0.14))
    tile_col = t.shade(toy.srgb(hexc) + (1,), value)
    mix = t.node("ShaderNodeMix", props={"data_type": "RGBA"})
    t._in(mix.inputs[0], g)
    t._in(mix.inputs[6], tile_col)
    t._in(mix.inputs[7], (*toy.srgb(grout), 1))
    r = t.math("ADD", rough, t.math("MULTIPLY", g, 0.6))
    return t.finish(mix.outputs[2], r, t.math("MULTIPLY", g, -1.0), strength=0.4, distance=0.01, coat=coat)
