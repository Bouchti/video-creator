"""
PBR materials for engineering cutaways (runs inside Blender; works in Cycles and EEVEE).

Every metal gets what makes it read as real: roughness that varies across the surface, a fine surface
(machining marks or sand-cast grain) in the bump, and grime in the crevices from an AO mask. Section-cut faces
get a matte engineering paint with a fine hatch so a cut never reads as a hollow shell.
"""
from __future__ import annotations

import bpy

_CACHE: dict = {}


def hex_rgb(h: str, a: float = 1.0):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (*lin, a)


class G:
    """Tiny node-graph builder."""

    def __init__(self, mat):
        self.nt = mat.node_tree
        self.nt.nodes.clear()
        self.x = 0

    def n(self, kind, **props):
        node = self.nt.nodes.new(kind)
        for k, v in props.items():          # plain properties first: data_type changes which sockets exist
            if not k.startswith("i_"):
                setattr(node, k, v)
        for k, v in props.items():
            if k.startswith("i_"):
                sock(node, k[2:].replace("_", " ")).default_value = v
        node.location = (self.x, 0)
        self.x += 220
        return node

    def link(self, a, b):
        self.nt.links.new(a, b)


def sock(node, name, out=False):
    """The enabled socket called `name` (Mix and Map Range nodes repeat names per data type)."""
    socks = node.outputs if out else node.inputs
    for s in socks:
        if s.name == name and getattr(s, "enabled", True):
            return s
    return socks[name]


def _new(name):
    mat = bpy.data.materials.get(name)
    if mat:
        bpy.data.materials.remove(mat)
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    return mat


def _cached(fn):
    def wrap(*args, **kw):
        key = (fn.__name__, args, tuple(sorted(kw.items())))
        mat = _CACHE.get(key)
        try:
            alive = mat is not None and mat.name in bpy.data.materials
        except ReferenceError:                  # removed by a scene reset
            alive = False
        if not alive:
            mat = fn(*args, **kw)
            _CACHE[key] = mat
        return mat
    return wrap


def _surface(g, bsdf, color, rough, rough_var, grain_scale, grain_strength, grime, coords="Object", cast=0.0,
             mottle=0.07, edge=0.25):
    """Shared wiring: roughness variation, surface grain bump and AO grime into a Principled BSDF."""
    tc = g.n("ShaderNodeTexCoord")
    out_coord = tc.outputs[coords]
    # broad roughness variation (handling, polish differences)
    big = g.n("ShaderNodeTexNoise", i_Scale=6.0, i_Detail=4.0, i_Roughness=0.55)
    g.link(out_coord, big.inputs["Vector"])
    rmap = g.n("ShaderNodeMapRange", i_To_Min=rough - rough_var, i_To_Max=rough + rough_var)
    g.link(big.outputs["Fac"], rmap.inputs["Value"])
    # fine grain: machining marks / casting sand
    fine = g.n("ShaderNodeTexNoise", i_Scale=grain_scale, i_Detail=6.0, i_Roughness=0.6)
    g.link(out_coord, fine.inputs["Vector"])
    bump = g.n("ShaderNodeBump", i_Strength=grain_strength, i_Distance=0.0004)
    g.link(fine.outputs["Fac"], bump.inputs["Height"])
    if cast:                                   # sand-cast pitting a viewer can see: millimetre-scale, deeper
        pits = g.n("ShaderNodeTexVoronoi", i_Scale=cast, i_Randomness=1.0)
        g.link(out_coord, pits.inputs["Vector"])
        bump2 = g.n("ShaderNodeBump", i_Strength=0.18, i_Distance=0.0008)
        g.link(pits.outputs["Distance"], bump2.inputs["Height"])
        g.link(bump.outputs["Normal"], bump2.inputs["Normal"])
        bump = bump2
    g.link(bump.outputs["Normal"], bsdf.inputs["Normal"])
    # grime and darker roughness in crevices
    ao = g.n("ShaderNodeAmbientOcclusion", only_local=True, samples=8, i_Distance=0.012)
    occ = g.n("ShaderNodeMapRange", i_From_Min=0.35, i_From_Max=1.0, i_To_Min=1.0 - grime, i_To_Max=1.0)
    g.link(ao.outputs["AO"], occ.inputs["Value"])
    tint = g.n("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY", i_Factor=1.0)
    sock(tint, "A").default_value = color
    g.link(sock(occ, "Result", True), sock(tint, "B"))
    # broad tonal mottling: a casting is never one flat grey
    mot = g.n("ShaderNodeTexNoise", i_Scale=4.0, i_Detail=3.0, i_Roughness=0.5)
    g.link(out_coord, mot.inputs["Vector"])
    motr = g.n("ShaderNodeMapRange", i_To_Min=1.0 - mottle, i_To_Max=1.0 + mottle)
    g.link(mot.outputs["Fac"], motr.inputs["Value"])
    mott = g.n("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY", i_Factor=1.0)
    g.link(sock(tint, "Result", True), sock(mott, "A"))
    g.link(sock(motr, "Result", True), sock(mott, "B"))
    # edge wear: convex edges catch light and polish (Cycles pointiness; flat in EEVEE drafts)
    geo_n = g.n("ShaderNodeNewGeometry")
    edge_m = g.n("ShaderNodeMapRange", i_From_Min=0.52, i_From_Max=0.6, i_To_Min=0.0, i_To_Max=edge)
    g.link(geo_n.outputs["Pointiness"], edge_m.inputs["Value"])
    lit = g.n("ShaderNodeMix", data_type="RGBA", blend_type="SCREEN")
    g.link(sock(edge_m, "Result", True), sock(lit, "Factor"))
    g.link(sock(mott, "Result", True), sock(lit, "A"))
    sock(lit, "B").default_value = (0.55, 0.56, 0.58, 1.0)
    g.link(sock(lit, "Result", True), bsdf.inputs["Base Color"])
    rough_add = g.n("ShaderNodeMath", operation="ADD")
    inv = g.n("ShaderNodeMath", operation="SUBTRACT", i_Value=1.0)
    inv.inputs[0].default_value = 1.0
    g.link(occ.outputs["Result"], inv.inputs[1])
    g.link(rmap.outputs["Result"], rough_add.inputs[0])
    g.link(inv.outputs["Value"], rough_add.inputs[1])
    polish = g.n("ShaderNodeMath", operation="SUBTRACT")
    g.link(rough_add.outputs["Value"], polish.inputs[0])
    g.link(sock(edge_m, "Result", True), polish.inputs[1])
    g.link(polish.outputs["Value"], bsdf.inputs["Roughness"])


def _metal(name, color, rough, rough_var=0.06, grain=900.0, grain_strength=0.08, grime=0.35,
           aniso=0.0, metallic=1.0, coat=0.0, cast=0.0, mottle=0.07, edge=0.25):
    mat = _new(name)
    g = G(mat)
    bsdf = g.n("ShaderNodeBsdfPrincipled", i_Metallic=metallic, i_Anisotropic=aniso, i_Coat_Weight=coat)
    out = g.n("ShaderNodeOutputMaterial")
    g.link(bsdf.outputs["BSDF"], out.inputs["Surface"])
    _surface(g, bsdf, hex_rgb(color) if isinstance(color, str) else color, rough, rough_var, grain,
             grain_strength, grime, cast=cast, mottle=mottle, edge=edge)
    return mat


@_cached
def cast_aluminium():
    """Sand-cast aluminium block/head: soft grey, rough, grainy."""
    return _metal("cast_aluminium", "#a3a4a0", 0.6, 0.1, grain=1400.0, grain_strength=0.22, grime=0.6,
                  cast=260.0, mottle=0.12, edge=0.35)


@_cached
def cast_iron():
    return _metal("cast_iron", "#4a4d51", 0.55, 0.08, grain=1600.0, grain_strength=0.28, grime=0.55,
                  cast=300.0, mottle=0.1, edge=0.3)


@_cached
def machined_aluminium():
    """Machined aluminium (pistons): bright, satin."""
    return _metal("machined_aluminium", "#c4c7ca", 0.28, 0.05, grain=2400.0, grain_strength=0.04, grime=0.3)


@_cached
def forged_steel():
    """Forged steel (con-rods, crank webs): darker, satin."""
    return _metal("forged_steel", "#8a8d91", 0.38, 0.07, grain=1800.0, grain_strength=0.10, grime=0.4)


@_cached
def polished_steel():
    """Ground journals, valve stems, wrist pins."""
    return _metal("polished_steel", "#c8cacd", 0.14, 0.03, grain=3000.0, grain_strength=0.02, grime=0.2,
                  aniso=0.6)


@_cached
def brushed_steel():
    return _metal("brushed_steel", "#b4b7ba", 0.26, 0.04, grain=2600.0, grain_strength=0.03, grime=0.25,
                  aniso=0.8)


@_cached
def dark_steel():
    """Black-oxide fasteners, springs, chain."""
    return _metal("dark_steel", "#3a3c40", 0.35, 0.06, grain=2200.0, grain_strength=0.05, grime=0.3)


@_cached
def anodized(color: str = "#2b5d8c"):
    return _metal(f"anodized_{color}", color, 0.32, 0.05, grain=2400.0, grain_strength=0.03, grime=0.25,
                  coat=0.2)


@_cached
def copper():
    return _metal("copper", "#c9774a", 0.3, 0.06, grain=2000.0, grain_strength=0.03, grime=0.3)


@_cached
def brass():
    return _metal("brass", "#c9a24a", 0.28, 0.05, grain=2000.0, grain_strength=0.03, grime=0.3)


def _dielectric(name, color, rough, rough_var=0.05, grain=800.0, grain_strength=0.05, grime=0.3, coat=0.0,
                sss=0.0):
    mat = _new(name)
    g = G(mat)
    bsdf = g.n("ShaderNodeBsdfPrincipled", i_Metallic=0.0, i_Coat_Weight=coat, i_Subsurface_Weight=sss)
    out = g.n("ShaderNodeOutputMaterial")
    g.link(bsdf.outputs["BSDF"], out.inputs["Surface"])
    _surface(g, bsdf, hex_rgb(color), rough, rough_var, grain, grain_strength, grime)
    return mat


@_cached
def paint(color: str = "#1d232b", rough: float = 0.45, crinkle: bool = False):
    """Painted cast parts (valve covers in wrinkle paint, brackets)."""
    return _dielectric(f"paint_{color}_{crinkle}", color, rough, 0.06,
                       grain=600.0 if crinkle else 300.0, grain_strength=0.6 if crinkle else 0.08,
                       coat=0.0 if crinkle else 0.3)


@_cached
def plastic(color: str = "#15171a", rough: float = 0.42):
    return _dielectric(f"plastic_{color}", color, rough, 0.05, grain=900.0, grain_strength=0.03, coat=0.1)


@_cached
def rubber(color: str = "#141414"):
    return _dielectric(f"rubber_{color}", color, 0.75, 0.08, grain=1200.0, grain_strength=0.06, grime=0.2)


@_cached
def ceramic():
    """Spark-plug insulator: white glazed porcelain."""
    return _dielectric("ceramic", "#ece8df", 0.18, 0.03, grain=500.0, grain_strength=0.01, grime=0.15,
                       coat=0.5, sss=0.05)


@_cached
def gasket():
    return _dielectric("gasket", "#2a2f2a", 0.6, 0.06, grain=1500.0, grain_strength=0.08)


@_cached
def glass(color: str = "#d9ecf5", rough: float = 0.02):
    mat = _new(f"glass_{color}")
    g = G(mat)
    bsdf = g.n("ShaderNodeBsdfPrincipled", i_Roughness=rough, i_IOR=1.47, i_Transmission_Weight=1.0)
    bsdf.inputs["Base Color"].default_value = hex_rgb(color)
    out = g.n("ShaderNodeOutputMaterial")
    g.link(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


@_cached
def backdrop(color: str = "#0a1220", rough: float = 0.82):
    mat = _new("backdrop")
    g = G(mat)
    bsdf = g.n("ShaderNodeBsdfPrincipled", i_Roughness=rough, i_Specular_IOR_Level=0.25)
    bsdf.inputs["Base Color"].default_value = hex_rgb(color)
    out = g.n("ShaderNodeOutputMaterial")
    g.link(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


@_cached
def section_cap(color: str = "#4a5260", hatch_mm: float = 5.0):
    """Matte engineering paint for cut faces, with a fine 45-degree hatch in world space. Dark slate, so the
    cold-blue charge and the hot flame are the only strong colours inside a cut (the red-orange cap of the
    first drafts outshouted them)."""
    mat = _new("section_cap")
    g = G(mat)
    geo = g.n("ShaderNodeNewGeometry")
    dot = g.n("ShaderNodeVectorMath", operation="DOT_PRODUCT")
    dot.inputs[1].default_value = (0.7071, 0.7071, 0.7071)
    g.link(geo.outputs["Position"], dot.inputs[0])
    scale = g.n("ShaderNodeMath", operation="MULTIPLY", i_Value=1.0)
    scale.inputs[1].default_value = 1000.0 / hatch_mm
    g.link(dot.outputs["Value"], scale.inputs[0])
    frac = g.n("ShaderNodeMath", operation="FRACT")
    g.link(scale.outputs["Value"], frac.inputs[0])
    tri = g.n("ShaderNodeMath", operation="PINGPONG")
    tri.inputs[1].default_value = 0.5
    g.link(frac.outputs["Value"], tri.inputs[0])
    line = g.n("ShaderNodeMapRange", i_From_Min=0.03, i_From_Max=0.07, i_To_Min=0.9, i_To_Max=1.0)
    g.link(tri.outputs["Value"], line.inputs["Value"])
    col = g.n("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY", i_Factor=1.0)
    sock(col, "A").default_value = hex_rgb(color)
    g.link(sock(line, "Result", True), sock(col, "B"))
    bsdf = g.n("ShaderNodeBsdfPrincipled", i_Roughness=0.7, i_Specular_IOR_Level=0.25)
    g.link(sock(col, "Result", True), bsdf.inputs["Base Color"])
    out = g.n("ShaderNodeOutputMaterial")
    g.link(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


@_cached
def ghost(color: str = "#6fd3ff", edge: float = 0.6, body: float = 0.012, strength: float = 1.0):
    """X-ray shell: almost clear where a surface faces the camera, glowing at its silhouette, so the castings
    stay readable as outlines while the moving parts inside show through."""
    mat = _new(f"ghost_{color}")
    g = G(mat)
    lw = g.n("ShaderNodeLayerWeight", i_Blend=0.4)
    pw = g.n("ShaderNodeMath", operation="POWER")
    pw.inputs[1].default_value = 2.0
    g.link(lw.outputs["Facing"], pw.inputs[0])
    fac = g.n("ShaderNodeMapRange", i_From_Min=0.0, i_From_Max=1.0, i_To_Min=body, i_To_Max=edge)
    g.link(pw.outputs["Value"], fac.inputs["Value"])
    em = g.n("ShaderNodeEmission", i_Strength=strength)
    em.inputs["Color"].default_value = hex_rgb(color)
    tr = g.n("ShaderNodeBsdfTransparent")
    mix = g.n("ShaderNodeMixShader")
    g.link(sock(fac, "Result", True), mix.inputs["Fac"])
    g.link(tr.outputs["BSDF"], mix.inputs[1])
    g.link(em.outputs["Emission"], mix.inputs[2])
    out = g.n("ShaderNodeOutputMaterial")
    g.link(mix.outputs["Shader"], out.inputs["Surface"])
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"
    return mat


def emission(name: str, color: str, strength: float):
    """A plain emitter whose strength can be keyed (node 'emit', input 'Strength')."""
    mat = _new(name)
    g = G(mat)
    em = g.n("ShaderNodeEmission", i_Strength=strength)
    em.name = "emit"
    em.inputs["Color"].default_value = hex_rgb(color)
    out = g.n("ShaderNodeOutputMaterial")
    g.link(em.outputs["Emission"], out.inputs["Surface"])
    return mat


@_cached
def concrete(color: str = "#a9aaa5"):
    """Cast concrete: pale, rough, with form-work mottling and dirt in the crevices."""
    return _dielectric(f"concrete_{color}", color, 0.86, 0.06, grain=45.0, grain_strength=0.25, grime=0.5)


@_cached
def insulation():
    """Aluminium jacketing over pipe and vessel insulation: bright, slightly crinkled."""
    return _metal("insulation", "#c9ccd0", 0.24, 0.08, grain=60.0, grain_strength=0.12, grime=0.25)


@_cached
def zircaloy():
    """Fuel-rod cladding: pale grey, satin."""
    return _metal("zircaloy", "#b8bbbf", 0.3, 0.04, grain=3000.0, grain_strength=0.02, grime=0.2)


@_cached
def absorber():
    """Control-rod absorber: dark steel."""
    return _metal("absorber", "#2b2d31", 0.32, 0.05, grain=2500.0, grain_strength=0.03, grime=0.2)


@_cached
def cladding(color: str = "#8f9ba8"):
    """Corrugated building cladding (turbine hall)."""
    mat = _new(f"cladding_{color}")
    g = G(mat)
    bsdf = g.n("ShaderNodeBsdfPrincipled", i_Metallic=0.6, i_Roughness=0.45)
    bsdf.inputs["Base Color"].default_value = hex_rgb(color)
    tc = g.n("ShaderNodeTexCoord")
    wave = g.n("ShaderNodeTexWave", wave_type="BANDS", bands_direction="X", i_Scale=1.6, i_Distortion=0.0)
    g.link(tc.outputs["Generated"], wave.inputs["Vector"])
    bump = g.n("ShaderNodeBump", i_Strength=0.35, i_Distance=0.05)
    g.link(wave.outputs["Fac"], bump.inputs["Height"])
    g.link(bump.outputs["Normal"], bsdf.inputs["Normal"])
    out = g.n("ShaderNodeOutputMaterial")
    g.link(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat
