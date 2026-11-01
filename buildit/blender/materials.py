"""
The Build-It material library (runs inside Blender; EEVEE and Cycles): clean, slightly stylised PBR as in
docs/style_guide.md. Every material is cached by its arguments, so a scene shares node trees.

    brushed()  brushed aluminium, strong visible brushing (linear on flats, circular on caps)
    chrome()   polished chrome          paint()   glossy candy paint (red by default)
    graphite() satin dark metal         rubber()  matte black rubber
    glass()    clear glass housing      plinth()  matte black base
    glow()     warm emitter (keyable "glow" property on the object)
    backdrop() the sand floor + warm wall gradient    haze()  one slice of the ground fog
"""
from __future__ import annotations

import bpy

from cutaway.blender.materials import G, hex_rgb, sock  # the shared node-graph helpers

_CACHE: dict = {}


def _cached(fn):
    def wrap(*args, **kw):
        key = (fn.__name__, args, tuple(sorted(kw.items())))
        mat = _CACHE.get(key)
        try:
            alive = mat is not None and mat.name in bpy.data.materials
        except ReferenceError:
            alive = False
        if not alive:
            mat = fn(*args, **kw)
            _CACHE[key] = mat
        return mat
    wrap.__name__ = fn.__name__
    return wrap


def _new(name: str):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    return mat


def _out(g, shader_socket, volume=None, thermal: bool = False):
    """Material output; `thermal` adds the heat / frost glow every solid part can show: emission driven by
    the object's "heat" (hot orange) and "frost" (pale blue-white) properties, 0 by default."""
    out = g.n("ShaderNodeOutputMaterial")
    if thermal:
        heat = g.n("ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="heat")
        frost = g.n("ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="frost")
        # frost: a white rime coat over the surface, in patches (mixes the shader, never tints it pink)
        nz = g.n("ShaderNodeTexNoise", i_Scale=45.0, i_Detail=5.0)
        patch = g.n("ShaderNodeMapRange", i_From_Min=0.38, i_From_Max=0.62, i_To_Min=0.35, i_To_Max=1.0)
        g.link(nz.outputs["Fac"], patch.inputs["Value"])
        fv = g.n("ShaderNodeMath", operation="MULTIPLY", use_clamp=True)
        g.link(frost.outputs["Fac"], fv.inputs[0])
        g.link(sock(patch, "Result", True), fv.inputs[1])
        rime = g.n("ShaderNodeBsdfPrincipled", i_Roughness=0.85)
        rime.inputs["Base Color"].default_value = hex_rgb("#d9ecff")
        for name, v in (("Emission Color", hex_rgb("#9fd6ff")), ("Emission Strength", 0.35)):
            if name in rime.inputs:                 # a cold blue sheen: frost reads even on a white part
                rime.inputs[name].default_value = v
        coat = g.n("ShaderNodeMixShader")
        g.link(fv.outputs["Value"], coat.inputs["Fac"])
        g.link(shader_socket, coat.inputs[1])
        g.link(rime.outputs["BSDF"], coat.inputs[2])
        # heat: an orange glow strongest at the silhouette, so the part keeps its own colour in the middle
        lw = g.n("ShaderNodeLayerWeight", i_Blend=0.45)
        edge = g.n("ShaderNodeMapRange", i_To_Min=0.08, i_To_Max=1.0)
        g.link(lw.outputs["Facing"], edge.inputs["Value"])
        hv = g.n("ShaderNodeMath", operation="MULTIPLY")
        g.link(heat.outputs["Fac"], hv.inputs[0])
        g.link(sock(edge, "Result", True), hv.inputs[1])
        em = g.n("ShaderNodeEmission")
        em.inputs["Color"].default_value = hex_rgb("#ff5a12")
        hs = g.n("ShaderNodeMath", operation="MULTIPLY")
        hs.inputs[1].default_value = 1.2
        g.link(hv.outputs["Value"], hs.inputs[0])
        g.link(hs.outputs["Value"], em.inputs["Strength"])
        add = g.n("ShaderNodeAddShader")
        g.link(coat.outputs["Shader"], add.inputs[0])
        g.link(em.outputs["Emission"], add.inputs[1])
        shader_socket = add.outputs["Shader"]
        # highlight: the part the narration talks about glows at its silhouette in the film's accent colour
        # (object properties "hl" 0..1 and "hl_col" rgb)
        hl = g.n("ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="hl")
        hcol = g.n("ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="hl_col")
        lw2 = g.n("ShaderNodeLayerWeight", i_Blend=0.35)
        rim = g.n("ShaderNodeMapRange", i_From_Min=0.55, i_From_Max=0.95, i_To_Min=0.0, i_To_Max=1.0)
        g.link(lw2.outputs["Facing"], rim.inputs["Value"])
        hk = g.n("ShaderNodeMath", operation="MULTIPLY")
        g.link(hl.outputs["Fac"], hk.inputs[0])
        g.link(sock(rim, "Result", True), hk.inputs[1])
        hs2 = g.n("ShaderNodeMath", operation="MULTIPLY")
        hs2.inputs[1].default_value = 2.2
        g.link(hk.outputs["Value"], hs2.inputs[0])
        em2 = g.n("ShaderNodeEmission")
        g.link(hcol.outputs["Color"], em2.inputs["Color"])
        g.link(hs2.outputs["Value"], em2.inputs["Strength"])
        add2 = g.n("ShaderNodeAddShader")
        g.link(shader_socket, add2.inputs[0])
        g.link(em2.outputs["Emission"], add2.inputs[1])
        shader_socket = add2.outputs["Shader"]
    g.link(shader_socket, out.inputs["Surface"])
    if volume is not None:
        g.link(volume, out.inputs["Volume"])
    return out


@_cached
def brushed(color: str = "#c9ccd0", roughness: float = 0.28, scale: float = 600.0):
    """Brushed aluminium: anisotropic metal whose roughness and bump carry stretched noise streaks."""
    mat = _new(f"brushed_{color}")
    g = G(mat)
    tc = g.n("ShaderNodeTexCoord")
    mp = g.n("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0, 1.0, scale)              # streaks run around/along the part
    g.link(tc.outputs["Object"], mp.inputs["Vector"])
    nz = g.n("ShaderNodeTexNoise", i_Scale=4.0, i_Detail=8.0, i_Roughness=0.7)
    g.link(mp.outputs["Vector"], nz.inputs["Vector"])
    rr = g.n("ShaderNodeMapRange", i_To_Min=roughness * 0.55, i_To_Max=roughness * 1.35)
    g.link(nz.outputs["Fac"], rr.inputs["Value"])
    cr = g.n("ShaderNodeMapRange", i_To_Min=0.82, i_To_Max=1.0)
    g.link(nz.outputs["Fac"], cr.inputs["Value"])
    tint = g.n("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY", i_Factor=1.0)
    sock(tint, "A").default_value = hex_rgb(color)
    g.link(sock(cr, "Result", True), sock(tint, "B"))
    bump = g.n("ShaderNodeBump", i_Strength=0.06, i_Distance=0.002)
    g.link(nz.outputs["Fac"], bump.inputs["Height"])
    b = g.n("ShaderNodeBsdfPrincipled", i_Metallic=1.0)
    g.link(sock(tint, "Result", True), b.inputs["Base Color"])
    g.link(sock(rr, "Result", True), b.inputs["Roughness"])
    g.link(bump.outputs["Normal"], b.inputs["Normal"])
    if "Anisotropic" in b.inputs:
        b.inputs["Anisotropic"].default_value = 0.6
    _out(g, b.outputs["BSDF"], thermal=True)
    return mat


@_cached
def chrome(roughness: float = 0.06):
    mat = _new("chrome")
    g = G(mat)
    b = g.n("ShaderNodeBsdfPrincipled", i_Metallic=1.0, i_Roughness=roughness)
    b.inputs["Base Color"].default_value = hex_rgb("#e9ebee")
    _out(g, b.outputs["BSDF"], thermal=True)
    return mat


@_cached
def paint(color: str = "#9e0b14", roughness: float = 0.16):
    """Glossy candy paint with a clear coat."""
    mat = _new(f"paint_{color}")
    g = G(mat)
    b = g.n("ShaderNodeBsdfPrincipled", i_Roughness=roughness)
    b.inputs["Base Color"].default_value = hex_rgb(color)
    for name, v in (("Coat Weight", 0.8), ("Coat Roughness", 0.04)):
        if name in b.inputs:
            b.inputs[name].default_value = v
    _out(g, b.outputs["BSDF"], thermal=True)
    return mat


@_cached
def graphite(color: str = "#2b2c2f", roughness: float = 0.42):
    mat = _new(f"graphite_{color}")
    g = G(mat)
    b = g.n("ShaderNodeBsdfPrincipled", i_Metallic=0.7, i_Roughness=roughness)
    b.inputs["Base Color"].default_value = hex_rgb(color)
    _out(g, b.outputs["BSDF"], thermal=True)
    return mat


@_cached
def rubber(color: str = "#1c1c1e"):
    mat = _new(f"rubber_{color}")
    g = G(mat)
    b = g.n("ShaderNodeBsdfPrincipled", i_Roughness=0.75)
    b.inputs["Base Color"].default_value = hex_rgb(color)
    _out(g, b.outputs["BSDF"])
    return mat


@_cached
def copper():
    return brushed("#c77a4e", 0.24, 400.0)


@_cached
def brass():
    return brushed("#c8a457", 0.26, 400.0)


@_cached
def plastic(color: str = "#e9e6e1", roughness: float = 0.4):
    """Satin plastic (bottles, knobs, casings)."""
    mat = _new(f"plastic_{color}")
    g = G(mat)
    b = g.n("ShaderNodeBsdfPrincipled", i_Roughness=roughness)
    b.inputs["Base Color"].default_value = hex_rgb(color)
    _out(g, b.outputs["BSDF"], thermal=True)
    return mat


@_cached
def plinth(color: str = "#141416"):
    mat = _new(f"plinth_{color}")
    g = G(mat)
    b = g.n("ShaderNodeBsdfPrincipled", i_Roughness=0.62)
    b.inputs["Base Color"].default_value = hex_rgb(color)
    _out(g, b.outputs["BSDF"])
    return mat


@_cached
def glass(tint: str = "#f4f8fa", roughness: float = 0.03):
    """Clear glass for housings, as a thin shell: see-through with Fresnel reflections and bright edges, no
    refraction. The contents stay crisp (EEVEE's refraction blurred the dots inside into grey smears) and it
    renders the same, and fast, in EEVEE and Cycles."""
    mat = _new(f"glass_{tint}")
    g = G(mat)
    fr = g.n("ShaderNodeFresnel", i_IOR=1.5)
    lw = g.n("ShaderNodeLayerWeight", i_Blend=0.25)
    edge = g.n("ShaderNodeMath", operation="POWER")
    edge.inputs[1].default_value = 3.0
    g.link(lw.outputs["Facing"], edge.inputs[0])
    fac = g.n("ShaderNodeMath", operation="ADD", use_clamp=True)
    g.link(fr.outputs["Fac"], fac.inputs[0])
    sc = g.n("ShaderNodeMath", operation="MULTIPLY")
    sc.inputs[1].default_value = 0.45
    g.link(edge.outputs["Value"], sc.inputs[0])
    g.link(sc.outputs["Value"], fac.inputs[1])
    base = g.n("ShaderNodeMath", operation="ADD", use_clamp=True)
    base.inputs[1].default_value = 0.03
    g.link(fac.outputs["Value"], base.inputs[0])
    gl = g.n("ShaderNodeBsdfGlossy", i_Roughness=roughness)
    gl.inputs["Color"].default_value = hex_rgb(tint)
    tr = g.n("ShaderNodeBsdfTransparent")
    tr.inputs["Color"].default_value = hex_rgb(tint)
    mix = g.n("ShaderNodeMixShader")
    g.link(base.outputs["Value"], mix.inputs["Fac"])
    g.link(tr.outputs["BSDF"], mix.inputs[1])
    g.link(gl.outputs["BSDF"], mix.inputs[2])
    _out(g, mix.outputs["Shader"])
    mat.surface_render_method = "BLENDED"
    mat.use_transparency_overlap = True
    mat.use_backface_culling = True               # only the near wall: the far one mirrored the dots dark
    return mat


@_cached
def glow(color: str = "#ffb060", strength: float = 8.0):
    """Warm emitter; strength scaled by the object's "glow" property (0..1, keyable)."""
    mat = _new(f"glow_{color}")
    g = G(mat)
    at = g.n("ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="glow")
    mul = g.n("ShaderNodeMath", operation="MULTIPLY")
    mul.inputs[1].default_value = strength
    g.link(at.outputs["Fac"], mul.inputs[0])
    em = g.n("ShaderNodeEmission")
    em.inputs["Color"].default_value = hex_rgb(color)
    g.link(mul.outputs["Value"], em.inputs["Strength"])
    tr = g.n("ShaderNodeBsdfTransparent")
    mix = g.n("ShaderNodeMixShader")
    cl = g.n("ShaderNodeMath", operation="MINIMUM")
    cl.inputs[1].default_value = 1.0
    g.link(at.outputs["Fac"], cl.inputs[0])
    g.link(cl.outputs["Value"], mix.inputs["Fac"])
    g.link(tr.outputs["BSDF"], mix.inputs[1])
    g.link(em.outputs["Emission"], mix.inputs[2])
    _out(g, mix.outputs["Shader"])
    mat.surface_render_method = "BLENDED"
    return mat


@_cached
def particle(color: str = "#ffd36a", strength: float = 6.0):
    """Small glowing dots (fuel mist, air specks)."""
    mat = _new(f"particle_{color}")
    g = G(mat)
    em = g.n("ShaderNodeEmission", i_Strength=strength)
    em.inputs["Color"].default_value = hex_rgb(color)
    _out(g, em.outputs["Emission"])
    return mat


@_cached
def backdrop(floor: str = "#6b635b", floor_far: str = "#57514b", wall_low: str = "#86827e",
             wall_top: str = "#acaaa7", floor_z: float = 0.0, wall_h: float = 6.0):
    """The seamless studio: sandy floor with fine grain, rising into a warm grey-beige wall gradient.
    Colours are driven by world height, so the curve between floor and wall blends with no seam."""
    mat = _new("backdrop")
    g = G(mat)
    geo = g.n("ShaderNodeNewGeometry")
    sep = g.n("ShaderNodeSeparateXYZ")
    g.link(geo.outputs["Position"], sep.inputs[0])
    h = g.n("ShaderNodeMapRange", i_From_Min=floor_z + 0.05, i_From_Max=floor_z + wall_h)
    g.link(sep.outputs["Z"], h.inputs["Value"])
    ramp = g.n("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, hex_rgb(floor)
    els[1].position, els[1].color = 1.0, hex_rgb(wall_top)
    e = els.new(0.08)
    e.color = hex_rgb(wall_low)
    g.link(sock(h, "Result", True), ramp.inputs["Fac"])
    # far floor darker (depth): distance from origin on the floor
    ln = g.n("ShaderNodeVectorMath", operation="LENGTH")
    g.link(geo.outputs["Position"], ln.inputs[0])
    far = g.n("ShaderNodeMapRange", i_From_Min=2.0, i_From_Max=9.0)
    g.link(ln.outputs["Value"], far.inputs["Value"])
    mixf = g.n("ShaderNodeMix", data_type="RGBA")
    g.link(sock(far, "Result", True), sock(mixf, "Factor"))
    g.link(ramp.outputs["Color"], sock(mixf, "A"))
    sock(mixf, "B").default_value = hex_rgb(floor_far)
    # sand grain on the floor
    nz = g.n("ShaderNodeTexNoise", i_Scale=180.0, i_Detail=6.0)
    gr = g.n("ShaderNodeMapRange", i_To_Min=0.9, i_To_Max=1.06)
    g.link(nz.outputs["Fac"], gr.inputs["Value"])
    mul = g.n("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY", i_Factor=1.0)
    g.link(sock(mixf, "Result", True), sock(mul, "A"))
    g.link(sock(gr, "Result", True), sock(mul, "B"))
    bump = g.n("ShaderNodeBump", i_Strength=0.25, i_Distance=0.01)
    g.link(nz.outputs["Fac"], bump.inputs["Height"])
    b = g.n("ShaderNodeBsdfPrincipled", i_Roughness=0.92)
    g.link(sock(mul, "Result", True), b.inputs["Base Color"])
    g.link(bump.outputs["Normal"], b.inputs["Normal"])
    _out(g, b.outputs["BSDF"])
    return mat


@_cached
def haze(color: str = "#a7a39d", density: float = 0.85, scale: float = 2.2, seed: float = 0.0, lit: float = 0.86):
    """One horizontal slice of the ground fog: lumpy cloud-top alpha from 3D noise, lit softly, fading with
    distance so the floor dissolves into the wall (no horizon line). Stacked slices read as volume."""
    mat = _new(f"haze_{seed:.2f}")
    g = G(mat)
    geo = g.n("ShaderNodeNewGeometry")
    mp = g.n("ShaderNodeMapping")
    mp.inputs["Location"].default_value = (seed * 3.1, seed * 1.7, seed * 0.9)
    g.link(geo.outputs["Position"], mp.inputs["Vector"])
    nz = g.n("ShaderNodeTexNoise", i_Scale=scale, i_Detail=5.0, i_Roughness=0.62)
    g.link(mp.outputs["Vector"], nz.inputs["Vector"])
    shape = g.n("ShaderNodeMapRange", i_From_Min=0.5, i_From_Max=0.68, i_To_Min=0.0, i_To_Max=density)
    g.link(nz.outputs["Fac"], shape.inputs["Value"])
    # thicker far away (the floor melts into the wall), thinner right under the subject
    ln = g.n("ShaderNodeVectorMath", operation="LENGTH")
    g.link(geo.outputs["Position"], ln.inputs[0])
    dist = g.n("ShaderNodeMapRange", i_From_Min=0.6, i_From_Max=7.0, i_To_Min=0.35, i_To_Max=1.6)
    g.link(ln.outputs["Value"], dist.inputs["Value"])
    a0 = g.n("ShaderNodeMath", operation="MULTIPLY", use_clamp=True)
    g.link(sock(shape, "Result", True), a0.inputs[0])
    g.link(sock(dist, "Result", True), a0.inputs[1])
    # fade out before the floor bends up into the wall: slices meeting the curve drew a hard grey band
    sep = g.n("ShaderNodeSeparateXYZ")
    g.link(geo.outputs["Position"], sep.inputs[0])
    back = g.n("ShaderNodeMapRange", i_From_Min=1.2, i_From_Max=2.6, i_To_Min=1.0, i_To_Max=0.0)
    g.link(sep.outputs["Y"], back.inputs["Value"])
    a = g.n("ShaderNodeMath", operation="MULTIPLY", use_clamp=True)
    g.link(a0.outputs["Value"], a.inputs[0])
    g.link(sock(back, "Result", True), a.inputs[1])
    # unlit (no per-light shading on these big blended slices: they cost 40 % of a frame when lit); the
    # lumps get their own soft light and shadow from a second, offset noise
    nz2 = g.n("ShaderNodeTexNoise", i_Scale=scale * 0.6, i_Detail=3.0)
    g.link(mp.outputs["Vector"], nz2.inputs["Vector"])
    shade_ = g.n("ShaderNodeMapRange", i_From_Min=0.35, i_From_Max=0.65, i_To_Min=0.72, i_To_Max=1.12)
    g.link(nz2.outputs["Fac"], shade_.inputs["Value"])
    col = g.n("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY", i_Factor=1.0)
    sock(col, "A").default_value = hex_rgb(color)
    g.link(sock(shade_, "Result", True), sock(col, "B"))
    em = g.n("ShaderNodeEmission", i_Strength=lit)
    g.link(sock(col, "Result", True), em.inputs["Color"])
    tr = g.n("ShaderNodeBsdfTransparent")
    mix = g.n("ShaderNodeMixShader")
    g.link(a.outputs["Value"], mix.inputs["Fac"])
    g.link(tr.outputs["BSDF"], mix.inputs[1])
    g.link(em.outputs["Emission"], mix.inputs[2])
    _out(g, mix.outputs["Shader"])
    mat.surface_render_method = "BLENDED"
    return mat


@_cached
def flow_pipe(base: str = "#c77a4e", metal: float = 1.0, roughness: float = 0.26, period: float = 0.09,
              duty: float = 0.45):
    """A pipe that shows what flows through it: its own metal, plus bright dashes that travel along it in the
    flow's colour and a soft tint of the whole pipe (object properties "flow_on" 0..1, "flow_phase" metres
    travelled, "flow_col" rgb). Needs a UV map whose U is the arc length in metres (blender/flowpipe.py)."""
    mat = _new(f"flow_pipe_{base}")
    g = G(mat)
    b = g.n("ShaderNodeBsdfPrincipled", i_Metallic=metal, i_Roughness=roughness)
    b.inputs["Base Color"].default_value = hex_rgb(base)
    uv = g.n("ShaderNodeUVMap")
    sep = g.n("ShaderNodeSeparateXYZ")
    g.link(uv.outputs["UV"], sep.inputs[0])
    on = g.n("ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="flow_on")
    ph = g.n("ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="flow_phase")
    col = g.n("ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="flow_col")
    sub = g.n("ShaderNodeMath", operation="SUBTRACT")
    g.link(sep.outputs["X"], sub.inputs[0])
    g.link(ph.outputs["Fac"], sub.inputs[1])
    div = g.n("ShaderNodeMath", operation="DIVIDE")
    div.inputs[1].default_value = period
    g.link(sub.outputs["Value"], div.inputs[0])
    fr = g.n("ShaderNodeMath", operation="FRACT")
    g.link(div.outputs["Value"], fr.inputs[0])
    up = g.n("ShaderNodeMapRange", i_From_Min=0.0, i_From_Max=0.12, i_To_Min=0.0, i_To_Max=1.0)
    g.link(fr.outputs["Value"], up.inputs["Value"])
    dn = g.n("ShaderNodeMapRange", i_From_Min=duty, i_From_Max=duty + 0.12, i_To_Min=1.0, i_To_Max=0.0)
    g.link(fr.outputs["Value"], dn.inputs["Value"])
    st = g.n("ShaderNodeMath", operation="MINIMUM")
    g.link(sock(up, "Result", True), st.inputs[0])
    g.link(sock(dn, "Result", True), st.inputs[1])
    lift = g.n("ShaderNodeMath", operation="MULTIPLY_ADD")          # dash 1.0, gap 0.12: the pipe stays tinted
    lift.inputs[1].default_value = 0.88
    lift.inputs[2].default_value = 0.12
    g.link(st.outputs["Value"], lift.inputs[0])
    k = g.n("ShaderNodeMath", operation="MULTIPLY")
    g.link(lift.outputs["Value"], k.inputs[0])
    g.link(on.outputs["Fac"], k.inputs[1])
    s = g.n("ShaderNodeMath", operation="MULTIPLY")
    s.inputs[1].default_value = 11.0
    g.link(k.outputs["Value"], s.inputs[0])
    em = g.n("ShaderNodeEmission")
    g.link(col.outputs["Color"], em.inputs["Color"])
    g.link(s.outputs["Value"], em.inputs["Strength"])
    add = g.n("ShaderNodeAddShader")
    g.link(b.outputs["BSDF"], add.inputs[0])
    g.link(em.outputs["Emission"], add.inputs[1])
    _out(g, add.outputs["Shader"])
    return mat


@_cached
def studio_shell(floor: str = "#aab5c1", wall: str = "#c4cfda", wall_top: str = "#8396ac", roughness: float = 0.22,
                 wall_h: float = 8.0):
    """The bright seamless studio: a satin light floor (soft reflections) curving up into an almost-white wall
    that cools slightly toward the top."""
    mat = _new("studio_shell")
    g = G(mat)
    geo_ = g.n("ShaderNodeNewGeometry")
    sep = g.n("ShaderNodeSeparateXYZ")
    g.link(geo_.outputs["Position"], sep.inputs[0])
    h = g.n("ShaderNodeMapRange", i_From_Min=0.02, i_From_Max=wall_h)
    g.link(sep.outputs["Z"], h.inputs["Value"])
    ramp = g.n("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, hex_rgb(floor)
    els[1].position, els[1].color = 1.0, hex_rgb(wall_top)
    e = els.new(0.25)
    e.color = hex_rgb(wall)
    g.link(sock(h, "Result", True), ramp.inputs["Fac"])
    rr = g.n("ShaderNodeMapRange", i_To_Min=roughness, i_To_Max=0.75)
    g.link(sock(h, "Result", True), rr.inputs["Value"])
    b = g.n("ShaderNodeBsdfPrincipled")
    g.link(ramp.outputs["Color"], b.inputs["Base Color"])
    g.link(sock(rr, "Result", True), b.inputs["Roughness"])
    _out(g, b.outputs["BSDF"])
    return mat


@_cached
def frosted(tint: str = "#eef3f7", alpha: float = 0.55):
    """Frosted / satin glass (drawers, shelves): soft white, half see-through, cheap."""
    mat = _new(f"frosted_{tint}")
    g = G(mat)
    b = g.n("ShaderNodeBsdfPrincipled", i_Roughness=0.35)
    b.inputs["Base Color"].default_value = hex_rgb(tint)
    tr = g.n("ShaderNodeBsdfTransparent")
    mix = g.n("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = alpha
    g.link(tr.outputs["BSDF"], mix.inputs[1])
    g.link(b.outputs["BSDF"], mix.inputs[2])
    _out(g, mix.outputs["Shader"])
    mat.surface_render_method = "BLENDED"
    mat.use_backface_culling = True
    return mat


@_cached
def clear_pane(tint: str = "#f4f8fa"):
    """Glass for big machine walls: almost invisible, a faint Fresnel sheen only (the housing glass() mirrored the
    bright studio at grazing angles and turned whole walls milky white)."""
    mat = _new(f"clear_pane_{tint}")
    g = G(mat)
    fr = g.n("ShaderNodeFresnel", i_IOR=1.45)
    k = g.n("ShaderNodeMath", operation="MULTIPLY_ADD")
    k.inputs[1].default_value = 0.12
    k.inputs[2].default_value = 0.01
    g.link(fr.outputs["Fac"], k.inputs[0])
    gl = g.n("ShaderNodeBsdfGlossy", i_Roughness=0.05)
    gl.inputs["Color"].default_value = hex_rgb(tint)
    tr = g.n("ShaderNodeBsdfTransparent")
    mix = g.n("ShaderNodeMixShader")
    g.link(k.outputs["Value"], mix.inputs["Fac"])
    g.link(tr.outputs["BSDF"], mix.inputs[1])
    g.link(gl.outputs["BSDF"], mix.inputs[2])
    _out(g, mix.outputs["Shader"])
    mat.surface_render_method = "BLENDED"
    mat.use_backface_culling = True
    return mat
