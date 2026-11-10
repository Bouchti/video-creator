"""Station B, source: rain on wooded hills runs off into a reservoir held back by a concrete gravity dam.

The valley runs along x (the water's way is +x, toward the plant); the section plane y = 0 runs down the old
riverbed, so the cut shows the dam's triangular cross-section and the whole depth of the reservoir against it.
The reservoir's cut face is see-through (darker with depth), so what is under the surface stays visible: the
intake deep on the dam's upstream face behind its bar screen, fish and leaves stopped at the bars. The intake
pipe runs through the dam and on under the valley floor toward +x (the plant)."""
import math
import random

import bmesh
import bpy
from mathutils import Vector, noise

from engine import events
from engine.director import lib
from engine.flush import parts as P
from engine.flush.toilet import boolean

V = Vector
LAKE_Z = 29.0                      # reservoir surface
CREST_Z = 32.0                     # dam crest
DAM_TOE = 26.0                     # downstream toe of the dam (its upstream face is x = 0)
DAM_BASE = -5.0                    # dam foundation
X0, X1, Y1 = -480.0, 480.0, 430.0  # terrain extent (station-local)
RAW = ("#8FC7BE", "#E4F2EC", "#2B6A6E")     # raw water: surface tint, foam, deep
PIPE_R = 1.0
INTAKE_Z = 8.0
SCREEN_X = -3.75                   # the bar screen's plane (bars run along y)
INTAKE = [(-0.6, 0, INTAKE_Z), (24.0, 0, -2.4), (38.0, 0, -5.0), (X1, 0, -5.0)]


# ---------------------------------------------------------------- the land

def bed(x):
    """Height of the valley floor along the section plane (the old riverbed)."""
    if x <= 0:
        t = min(1.0, max(0.0, (-x - 12.0) / 300.0))
        z = 33.0 * (t * t * (3 - 2 * t)) ** 0.9
        if x < -312:
            z += 0.05 * (-x - 312)
        return z
    if x <= DAM_TOE:
        return 0.0
    if x <= DAM_TOE + 8:
        return -1.6 * (x - DAM_TOE) / 8
    return -1.6 - 0.008 * (x - DAM_TOE - 8)


def _n(x, y, s):
    v = V((x / s, y / s, 0.37))
    return noise.noise(v) + 0.5 * noise.noise(v * 2.13) + 0.25 * noise.noise(v * 4.41)


def h(x, y):
    """Ground height: the valley floor plus the hillside rising behind the cut (y > 0)."""
    y = max(0.0, y)
    base = 0.8 * (1 - math.exp(-y / 2.0)) + 82.0 * (1 - math.exp(-(y / 118.0) ** 2)) + 0.0003 * y * y
    ridge = 1.0 + 0.22 * math.sin(x / 70.0 + 0.6) + 0.1 * math.sin(x / 29.0 + 1.3)
    bumps = 16.0 * max(0.0, min(1.0, 0.5 + 0.5 * _n(x, y, 95.0))) * min(1.0, y / 60.0)
    return bed(x) + base * ridge + bumps


def strata(name, asset, scale, tint, period=9.0):
    """Earth in the cut face with gently wavy layers (a plain texture reads as flat brown from 200 m)."""
    if name in lib._mats:
        return lib._mats[name]
    mat = lib.material(asset, scale=scale, tint=tint, name=name)
    nt, bsdf = lib._bsdf(mat)
    src = bsdf.inputs["Base Color"].links[0].from_socket
    tc = nt.nodes.new("ShaderNodeTexCoord")
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "Z"
    wave.inputs["Scale"].default_value = 0.314 / period
    wave.inputs["Phase Offset"].default_value = 1.3
    wave.inputs["Distortion"].default_value = 9.0
    wave.inputs["Detail"].default_value = 4.0
    wave.inputs["Detail Scale"].default_value = 0.35
    nt.links.new(tc.outputs["Object"], wave.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    el = ramp.color_ramp.elements
    el[0].position, el[0].color = 0.0, (1.0, 0.94, 0.86, 1)
    el[1].position, el[1].color = 1.0, (0.86, 0.78, 0.7, 1)
    e2 = el.new(0.5)
    e2.color = (1.06, 1.0, 0.9, 1)
    e3 = el.new(0.75)
    e3.color = (0.92, 0.88, 0.84, 1)
    nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 1.0
    nt.links.new(src, mix.inputs["A"])
    nt.links.new(ramp.outputs["Color"], mix.inputs["B"])
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    return mat


def _ramp(nt, value, a, b):
    """0 at value = a, 1 at value = b (clamped, either direction)."""
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.clamp = True
    mr.inputs["From Min"].default_value = a
    mr.inputs["From Max"].default_value = b
    nt.links.new(value, mr.inputs["Value"])
    return mr.outputs["Result"]


def _math(nt, op, a, b):
    m = nt.nodes.new("ShaderNodeMath")
    m.operation = op
    for i, v in enumerate((a, b)):
        if isinstance(v, (int, float)):
            m.inputs[i].default_value = v
        else:
            nt.links.new(v, m.inputs[i])
    return m.outputs["Value"]


def terrain_mat():
    """Hillside grass with large light/dark patches; the bare gravel band a reservoir leaves round its shore;
    mud under the reservoir and the river. Blended by height in one material so the lines stay smooth."""
    name = "src_ground"
    if name in lib._mats:
        return lib._mats[name]
    mat = bpy.data.materials.new(name)
    nt, bsdf = lib._bsdf(mat)
    grass = lib.tex_nodes(nt, "Grass004", 0.35)
    gravel = lib.tex_nodes(nt, "Gravel023", 0.6)
    mud = lib.tex_nodes(nt, "Ground106", 0.3)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    x, z = sep.outputs["X"], sep.outputs["Z"]
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 0.012
    nz.inputs["Detail"].default_value = 4.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    patch = nt.nodes.new("ShaderNodeValToRGB")
    patch.color_ramp.elements[0].position = 0.35
    patch.color_ramp.elements[0].color = (0.5, 0.62, 0.32, 1)
    patch.color_ramp.elements[1].position = 0.7
    patch.color_ramp.elements[1].color = (0.9, 0.92, 0.62, 1)
    nt.links.new(nz.outputs["Fac"], patch.inputs["Fac"])

    def mul(a, b_color):
        m = nt.nodes.new("ShaderNodeMix")
        m.data_type = "RGBA"
        m.blend_type = "MULTIPLY"
        m.inputs["Factor"].default_value = 1.0
        nt.links.new(a, m.inputs["A"])
        if isinstance(b_color, tuple):
            m.inputs["B"].default_value = (*b_color, 1)
        else:
            nt.links.new(b_color, m.inputs["B"])
        return m.outputs["Result"]

    def mix(fac, a, b):
        m = nt.nodes.new("ShaderNodeMix")
        m.data_type = "RGBA"
        nt.links.new(fac, m.inputs["Factor"])
        nt.links.new(a, m.inputs["A"])
        nt.links.new(b, m.inputs["B"])
        return m.outputs["Result"]

    def mixf(fac, a, b):
        m = nt.nodes.new("ShaderNodeMix")
        m.data_type = "FLOAT"
        nt.links.new(fac, m.inputs["Factor"])
        nt.links.new(a, m.inputs["A"])
        nt.links.new(b, m.inputs["B"])
        return m.outputs["Result"]

    g_col = mul(grass["Color"], patch.outputs["Color"])
    s_col = mul(gravel["Color"], (0.85, 0.8, 0.72))
    m_col = mul(mud["Color"], (0.62, 0.66, 0.52))
    lakeside = _ramp(nt, x, 3.0, 0.0)
    band = _math(nt, "MULTIPLY", _ramp(nt, z, LAKE_Z + 1.4, LAKE_Z + 0.7), lakeside)
    under = _math(nt, "MULTIPLY", _ramp(nt, z, LAKE_Z - 0.3, LAKE_Z - 1.1), lakeside)
    # the river below the dam: its water top is at bed + 1.2 = -0.128 - 0.008 x
    zr = _math(nt, "ADD", z, _math(nt, "MULTIPLY", x, 0.008))
    river = _math(nt, "MULTIPLY", _ramp(nt, zr, 0.25, -0.25), _ramp(nt, x, DAM_TOE, DAM_TOE + 3.0))
    wet = _math(nt, "MAXIMUM", under, river)
    col = mix(wet, mix(band, g_col, s_col), m_col)
    nt.links.new(col, bsdf.inputs["Base Color"])
    rough = mixf(wet, mixf(band, grass["Roughness"], gravel["Roughness"]), mud["Roughness"])
    nt.links.new(rough, bsdf.inputs["Roughness"])
    nt.links.new(grass["Normal"], bsdf.inputs["Normal"])
    lib._mats[name] = mat
    return mat


def rock():
    return lib.material("Concrete031", scale=0.25, tint=(0.72, 0.7, 0.66), name="hill_rock")


def section_mat(name, top, deep, z0, z1, alpha_top=1.0, alpha_deep=1.0, glow=0.12):
    """The flat cut face of a water body: `top` colour at z1 fading to `deep` at z0 (station-local z), with a
    faint glow so the deep part never goes black; alpha < 1 makes it a see-through window into the water."""
    if name in lib._mats:
        return lib._mats[name]
    mat = bpy.data.materials.new(name)
    nt, bsdf = lib._bsdf(mat)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = z0
    mr.inputs["From Max"].default_value = z1
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    # soft vertical light shafts near the surface
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 1.0
    sc = nt.nodes.new("ShaderNodeMapping")
    sc.inputs["Scale"].default_value = (0.25, 0.25, 0.015)
    nt.links.new(tc.outputs["Object"], sc.inputs["Vector"])
    nt.links.new(sc.outputs["Vector"], nz.inputs["Vector"])
    shaft = nt.nodes.new("ShaderNodeMath")
    shaft.operation = "MULTIPLY"
    nt.links.new(nz.outputs["Fac"], shaft.inputs[0])
    nt.links.new(mr.outputs["Result"], shaft.inputs[1])
    fac = nt.nodes.new("ShaderNodeMath")
    fac.operation = "MULTIPLY_ADD"
    fac.use_clamp = True
    nt.links.new(shaft.outputs["Value"], fac.inputs[0])
    fac.inputs[1].default_value = 0.35
    nt.links.new(mr.outputs["Result"], fac.inputs[2])
    # colours mix in linear light: without a curve the mid depths stay as bright as the surface
    curve = nt.nodes.new("ShaderNodeMath")
    curve.operation = "POWER"
    nt.links.new(fac.outputs["Value"], curve.inputs[0])
    curve.inputs[1].default_value = 2.2
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (*lib.hexrgb(deep), 1)
    mix.inputs["B"].default_value = (*lib.hexrgb(top), 1)
    nt.links.new(curve.outputs["Value"], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = glow
    bsdf.inputs["Roughness"].default_value = 0.2
    bsdf.inputs["Coat Weight"].default_value = 0.08
    if alpha_top < 1.0 or alpha_deep < 1.0:
        am = nt.nodes.new("ShaderNodeMapRange")
        am.name = "alpha_range"
        am.inputs["From Min"].default_value = z0
        am.inputs["From Max"].default_value = z1
        am.inputs["To Min"].default_value = alpha_deep
        am.inputs["To Max"].default_value = alpha_top
        nt.links.new(sep.outputs["Z"], am.inputs["Value"])
        nt.links.new(am.outputs["Result"], bsdf.inputs["Alpha"])
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "BLENDED"
        if hasattr(mat, "use_transparency_overlap"):
            mat.use_transparency_overlap = False
    lib._mats[name] = mat
    return mat


def see_through(mat, alpha):
    """Make a P.water material a blended window (no refraction: metres of refracting water render black)."""
    nt, bsdf = lib._bsdf(mat)
    for link in list(bsdf.inputs["Transmission Weight"].links):
        nt.links.remove(link)
    bsdf.inputs["Transmission Weight"].default_value = 0.0
    bsdf.inputs["Alpha"].default_value = alpha
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"
    if hasattr(mat, "use_transparency_overlap"):
        mat.use_transparency_overlap = False
    return mat


def water_volume(mat, tint, scatter, absorb=0.045, scat=0.012):
    """Murky depth inside a water body: what is just behind the cut stays clear, the far bed fades into the
    water's colour (EEVEE and Cycles both march the material's volume)."""
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    ab = nt.nodes.new("ShaderNodeVolumeAbsorption")
    ab.inputs["Color"].default_value = (*lib.hexrgb(tint), 1)
    ab.inputs["Density"].default_value = absorb
    sc = nt.nodes.new("ShaderNodeVolumeScatter")
    sc.inputs["Color"].default_value = (*lib.hexrgb(scatter), 1)
    sc.inputs["Density"].default_value = scat
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(ab.outputs["Volume"], add.inputs[0])
    nt.links.new(sc.outputs["Volume"], add.inputs[1])
    nt.links.new(add.outputs["Shader"], out.inputs["Volume"])
    return mat


def _terrain(R):
    nx, ny = 240, 120
    xs = [X0 + (X1 - X0) * i / nx for i in range(nx + 1)]
    ys = [Y1 * (j / ny) ** 1.7 for j in range(ny + 1)]
    bm = bmesh.new()
    grid = [[bm.verts.new((x, y, h(x, y))) for x in xs] for y in ys]
    for j in range(ny):
        for i in range(nx):
            f = bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
            f.smooth = True
    bm.normal_update()
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    ob = lib.mesh_from_bm("src_terrain", bm, terrain_mat(), R)
    # the cut face: earth under the valley floor, darker deep down; the intake pipe runs in a groove through it
    xs2 = [X0 + (X1 - X0) * i / 480 for i in range(481)]
    earth = strata("src_earth", "Ground106", 0.5, (0.95, 0.86, 0.76))
    deep = strata("src_earth_deep", "Ground103", 0.4, (0.8, 0.72, 0.64), period=14.0)
    soil = _slab("src_soil", [(x, bed(x)) for x in xs2], [(x, bed(x) - 14.0) for x in xs2], 0.0, 3.0, earth, R)
    boolean(soil, P.solid_tube("soil_groove", INTAKE, PIPE_R + 0.012, earth, R, bend=6.0, step=0.4))
    _slab("src_soil_deep", [(x, bed(x) - 13.99) for x in xs2], [(x, -400.0) for x in xs2], 0.0, 3.0, deep, R)
    # the dark skin under the valley floor: topsoil on land, grey silt under the reservoir and the river
    topsoil = lib.material("Ground048", scale=0.8, tint=(0.55, 0.45, 0.36), name="src_topsoil")
    silt = lib.material("Ground106", scale=0.8, tint=(0.52, 0.55, 0.5), name="src_silt")
    for name, lo, hi, mat in (("src_silt_lake", X0, -1.3, silt), ("src_topsoil_up", X0, -1.3, topsoil),
                              ("src_silt_river", DAM_TOE + 2.5, X1, silt)):
        pts = [x for x in xs2 if lo <= x <= hi]
        if name == "src_silt_lake":
            pts = [x for x in pts if bed(x) < LAKE_Z - 0.2]
        elif name == "src_topsoil_up":
            pts = [x for x in pts if bed(x) >= LAKE_Z - 0.2]
        if len(pts) < 2:
            continue
        band = _slab(name, [(x, bed(x) + 0.004) for x in pts], [(x, bed(x) - 1.6) for x in pts], -0.004, 2.0,
                     mat, R)
        if name == "src_silt_river":
            boolean(band, P.solid_tube(f"{name}_groove", INTAKE, PIPE_R + 0.012, mat, R, bend=6.0, step=0.4))
    lib.box("src_back_soil", X0, X1, 3.0, Y1, -400.0, -40.0, P.soil_deep(), R)
    return ob


def _slab(name, top, bottom, y0, y1, mat, parent, cut_mat=None):
    """A closed slab between two x-z polylines (same x samples), extruded y0..y1: a ground band of the cut face
    that follows the valley floor (built from quads: a long concave ngon front face renders torn)."""
    bm = bmesh.new()
    ft = [bm.verts.new((x, y0, z)) for x, z in top]
    fb = [bm.verts.new((x, y0, z)) for x, z in bottom]
    bt = [bm.verts.new((x, y1, z)) for x, z in top]
    bb = [bm.verts.new((x, y1, z)) for x, z in bottom]
    n = len(top)
    for i in range(n - 1):
        f = bm.faces.new((ft[i], fb[i], fb[i + 1], ft[i + 1]))   # front (the cut face)
        f.material_index = 1 if cut_mat else 0
        bm.faces.new((bt[i], bt[i + 1], bb[i + 1], bb[i]))       # back
        bm.faces.new((ft[i], ft[i + 1], bt[i + 1], bt[i]))       # top
        bm.faces.new((fb[i], bb[i], bb[i + 1], fb[i + 1]))       # bottom
    bm.faces.new((ft[0], bt[0], bb[0], fb[0]))
    bm.faces.new((ft[-1], fb[-1], bb[-1], bt[-1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    ob = lib.mesh_from_bm(name, bm, mat, parent)
    if cut_mat:
        ob.data.materials.append(cut_mat)
    return ob


def _dam(R):
    conc = lib.material("Concrete031", scale=0.3, tint=(0.86, 0.82, 0.76), name="dam_outer")
    cut = lib.material("Concrete034", scale=0.22, tint=(0.5, 0.47, 0.43), name="dam_cut")
    outline = [(-1.3, DAM_BASE), (DAM_TOE + 2.5, DAM_BASE), (DAM_TOE + 2.5, -0.2), (DAM_TOE, 0.0),
               (6.6, CREST_Z - 1.4), (6.6, CREST_Z), (0.0, CREST_Z), (0.0, 1.6), (-1.0, 0.0)]
    dam = P.prism("dam", outline, -0.012, 170.0, conc, R, cut)
    # inspection gallery running along the dam near its base
    g = lib.box("dam_gallery_cut", 9.0, 11.4, -2.0, 200.0, 0.6, 3.4, lib.flat("gallery", lib.hexrgb("#4A4C4E"), 0.8),
                R)
    boolean(dam, g)
    boolean(dam, P.solid_tube("dam_groove", INTAKE[:3], PIPE_R + 0.012, conc, R, bend=6.0, step=0.4))
    # lift joints: the dam was poured in layers; each shows as a fine dark line across the cut
    joint = lib.flat("lift_joint", lib.hexrgb("#4D4A45"), 0.8)
    for k, z in enumerate((7.0 + 6.4 * i for i in range(4))):
        if z < 10:
            continue
        xd = DAM_TOE - (DAM_TOE - 6.6) * z / (CREST_Z - 1.4)
        lib.box(f"dam_joint{k}", 0.02, xd - 0.05, -0.022, -0.017, z - 0.05, z + 0.05, joint, R)
    lib.box("dam_gallery_light", 9.8, 10.6, 0.2, 170, 3.3, 3.38, lib.flat("lamp_warm", lib.hexrgb("#FFE2B0"), 0.5,
                                                                           emission=4.0), R)
    # crest: a road, a parapet on the lake side, railing posts on the valley side
    lib.box("crest_road", 0.35, 6.3, 0.0, 170, CREST_Z, CREST_Z + 0.06, P.asphalt(), R)
    lib.box("crest_parapet", 0.0, 0.35, 0.0, 170, CREST_Z, CREST_Z + 1.1, cut, R)
    rail = lib.flat("rail_paint", lib.hexrgb("#D9DCDD"), 0.4, metallic=0.4)
    lib.box("crest_rail", 6.25, 6.32, 0.0, 170, CREST_Z + 0.95, CREST_Z + 1.02, rail, R)
    for k in range(60):
        y = 0.6 + k * 2.5
        lib.box(f"crest_post{k}", 6.24, 6.33, y, y + 0.09, CREST_Z, CREST_Z + 1.0, rail, R)
    # a small outlet at the toe keeps the river below the dam alive
    lib.tube("toe_outlet", [(21.0, 7.0, 2.2), (26.6, 7.0, 2.2)], 0.45, P.dark_steel(), R)
    pour = P.fall("toe_pour", "#CFE8E2")
    P.stream("toe_pour", (26.7, 7.0, 2.05), (3.2, 0, 0.2), 0.62, radius=0.3, mat=pour, parent=R, flat=1.3)
    P.foam("toe_foam", (28.6, 7.0, -0.38), 0.9, parent=R, seed=5)
    return dam


def _water(self, R):
    lake_top = see_through(P.water("raw_lake_top", "#4E8C88", "#DCEDE8", speed=0.12, foam_amount=0.1,
                                   scale=(0.06, 0.06, 0.06), coord="Object", density=0, rough=0.03), 0.55)
    lake_cut = section_mat("raw_lake_cut", "#8FD2C6", "#0E3A44", 0.0, LAKE_Z, alpha_top=0.3, alpha_deep=0.82,
                           glow=0.06)
    self.src_lake_alpha = lake_cut.node_tree.nodes["alpha_range"]
    for m in (lake_top, lake_cut):
        water_volume(m, "#4F9A8F", "#9CCFC2", absorb=0.035, scat=0.006)
    xs = [x for x in [-0.01 - 2.0 * k for k in range(200)] if bed(x) < LAKE_Z]
    shore_x = xs[-1] - 2.0
    cols = [shore_x] + list(reversed(xs))
    lake = _slab("reservoir", [(x, LAKE_Z) for x in cols],
                 [(shore_x, LAKE_Z - 0.02)] + [(x, bed(x) - 0.05) for x in cols[1:]], 0.0, 175.0, lake_top, R, lake_cut)
    lake.visible_shadow = False
    # the river below the dam, flowing on toward the plant (+x)
    river_top = P.water("raw_river", RAW[0], RAW[1], speed=1.4, foam_amount=0.22, scale=(0.18, 0.5, 0.5),
                        coord="Object", density=0, rough=0.05)
    river_cut = section_mat("raw_river_cut", "#86C4BC", "#3D7E7E", -3.0, 0.0, glow=0.1)
    rx = [DAM_TOE + 0.5 + 2.0 * k for k in range(int((X1 - DAM_TOE - 1) / 2.0))]
    river = _slab("river", [(x, bed(x) + 1.2) for x in rx], [(x, bed(x) - 0.05) for x in rx], 0.0, 16.0,
                  river_top, R, river_cut)
    river.visible_shadow = False
    return lake


def _ray_mat(R):
    """Sun shafts under the surface: faint, fading out with depth."""
    name = "light_ray"
    if name in lib._mats:
        return lib._mats[name]
    mat = lib.flat(name, lib.hexrgb("#DDF4EC"), 0.5, emission=1.2, alpha=0.1)
    nt, bsdf = lib._bsdf(mat)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.object = R
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    nt.links.new(_math(nt, "MULTIPLY", _ramp(nt, sep.outputs["Z"], 4.0, LAKE_Z), 0.13), bsdf.inputs["Alpha"])
    lib._mats[name] = mat
    return mat


def _intake(self, R):
    """The bar screen box on the dam's upstream face, the intake pipe (cut lengthwise, running full)."""
    conc = P.concrete()
    cut = lib.material("Concrete034", scale=0.6, tint=(0.88, 0.87, 0.85), name="screen_cut")
    z0, z1 = INTAKE_Z - 3.6, INTAKE_Z + 3.6
    lib.box("screen_floor", SCREEN_X - 0.3, -0.004, 0.012, 3.6, z0 - 0.6, z0, conc, R)
    lib.box("screen_roof", SCREEN_X - 0.3, -0.004, 0.012, 3.6, z1, z1 + 0.6, conc, R)
    lib.box("screen_side", SCREEN_X - 0.3, -0.004, 3.2, 3.6, z0, z1, conc, R)
    _ = cut
    bars = lib.flat("screen_bars", lib.hexrgb("#2F3538"), 0.3, metallic=0.85)
    y = 0.14
    while y < 3.15:
        lib.tube(f"screen_bar{int(y * 100)}", [(SCREEN_X, y, z0), (SCREEN_X, y, z1)], 0.05, bars, R, resolution=8)
        y += 0.26
    for z in (z0 + 0.08, z1 - 0.08):
        lib.box(f"screen_frame{int(z)}", SCREEN_X - 0.09, SCREEN_X + 0.09, 0.03, 3.2, z - 0.09, z + 0.09, bars, R)
    for z in (z0 + 2.4, z0 + 4.8):
        lib.box(f"screen_tie{int(z)}", SCREEN_X - 0.05, SCREEN_X + 0.05, 0.05, 3.2, z - 0.06, z + 0.06, bars, R)
    lib.box("screen_lift", SCREEN_X - 0.25, SCREEN_X + 0.25, 1.4, 1.8, z1 + 0.6, LAKE_Z + 1.2, bars, R)
    # the pipe: painted steel, cut lengthwise, full of raw water
    paint = lib.flat("penstock", lib.hexrgb("#55656E"), 0.35, metallic=0.6)
    paint_cut = lib.flat("penstock_cut", lib.hexrgb("#3C474D"), 0.3, metallic=0.8)
    flow = P.water("raw_pipe_flow", RAW[0], RAW[1], speed=2.4, foam_amount=0.32, scale=(0.5, 1.6, 1.6), density=0)
    flow_cut = P.water("raw_pipe_section", "#4F9C9C", "#D6EFEA", speed=2.4, foam_amount=0.45,
                       scale=(0.45, 2.5, 2.5), density=0, rough=0.08)
    P.half_pipe("intake_pipe", INTAKE, PIPE_R, wall=0.16, mat=paint, cut_mat=paint_cut, parent=R, bend=6.0, step=0.4)
    P.pipe_water("intake_w", INTAKE, PIPE_R - 0.16, level=0.97, mat=flow, section_mat=flow_cut, parent=R, bend=6.0,
                 step=0.4)
    self.src_path = P.resample(P.rounded([(-17.0, 0, INTAKE_Z)] + INTAKE[:3] + [(70.0, 0, -5.0)], 6.0), 0.3)
    self.src_arrows = [P.arrow(f"src_arrow{k}", (0, 0, 0), (1, 0, 0), size=0.55, parent=R) for k in range(16)]
    self.src_dam_path = P.resample(P.rounded(INTAKE[:3] + [(90.0, 0, -5.0)], 6.0), 0.5)
    self.src_dam_arrows = [P.arrow(f"src_darrow{k}", (0, 0, 0), (1, 0, 0), size=1.25, parent=R) for k in range(7)]
    # things the screen keeps out: fish and leaves
    rnd = random.Random(21)
    fish_mat = lib.flat("fish", lib.hexrgb("#B4BFA6"), 0.28, metallic=0.45)
    belly = lib.flat("fish_belly", lib.hexrgb("#D9DCCB"), 0.35, metallic=0.2)
    self.src_fish = []
    fin = lib.flat("fish_fin", lib.hexrgb("#7E8C74"), 0.4)
    for k in range(6):
        root = lib.empty(f"fish{k}", (0, 0, 0), R)
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=1.0)
        for v in bm.verts:
            x, y, z = v.co
            taper = 1.0 if x > -0.1 else max(0.18, 1.0 + 0.82 * (x + 0.1) / 0.9)
            v.co = V((x * 0.46, y * 0.075 * taper, z * 0.14 * taper + 0.02 * (1 - x * x)))
        lib.mesh_from_bm(f"fish{k}_body", bm, fish_mat, root, smooth=True)
        lib.blob(f"fish{k}_belly", 0.1, belly, (0.06, 0, -0.045), squash=0.55, seed=k + 9, parent=root, lumpy=0.02)
        bm = bmesh.new()
        vs = [bm.verts.new(p) for p in ((-0.4, 0, 0), (-0.6, 0, 0.16), (-0.53, 0, 0.0), (-0.6, 0, -0.15))]
        bm.faces.new(vs)
        vs = [bm.verts.new(p) for p in ((0.1, 0, 0.12), (-0.02, 0, 0.24), (-0.14, 0, 0.1))]
        bm.faces.new(vs)
        lib.mesh_from_bm(f"fish{k}_fins", bm, fin, root)
        eye = lib.blob(f"fish{k}_eye", 0.025, lib.flat("fish_eye", (0.02, 0.02, 0.02), 0.1), (0.36, -0.1, 0.04),
                       parent=root, lumpy=0.0, subdiv=2)
        _ = eye
        sc = rnd.uniform(1.6, 2.1)
        root.scale = (sc, sc, sc)
        self.src_fish.append(root)
    leaf_mats = [lib.flat(f"leaf_{c}", lib.hexrgb(c), 0.6) for c in ("#B5762F", "#8E5A23", "#C99A3A", "#6E7A2C")]
    self.src_leaves = []
    for k in range(16):
        lf = lib.blob(f"leaf{k}", 0.24, leaf_mats[k % 4], (0, 0, 0), squash=0.06, seed=30 + k, parent=R, lumpy=0.25)
        lf.scale = (1.6, 1.0, 1.0)
        self.src_leaves.append(lf)
    # fine silt drifting with the current into the screen box (it passes the bars: the plant takes it out)
    speck = lib.flat("silt_speck", lib.hexrgb("#C9C2A2"), 0.6, emission=0.15)
    self.src_specks = []
    for k in range(70):
        sp = lib.blob(f"silt{k}", rnd.uniform(0.025, 0.05), speck, (0, rnd.uniform(0.15, 1.6),
                      rnd.uniform(INTAKE_Z - 3.2, INTAKE_Z + 3.2)), seed=k, parent=R, lumpy=0.3, subdiv=1)
        sp.visible_shadow = False
        per = rnd.randint(150, 260)
        P.cycle_rise(sp, -16.0, -0.4, per, -rnd.randint(0, per), axis=0)
        self.src_specks.append(sp)
    self.src_rays = []
    ray_mat = _ray_mat(R)
    for k in range(7):
        x = -13.0 + k * 1.9 + rnd.uniform(-0.5, 0.5)
        y = rnd.uniform(1.0, 5.0)
        w = rnd.uniform(0.5, 1.3)
        bm = bmesh.new()
        sl = 4.0
        vs = [bm.verts.new(p) for p in ((x - w, y, LAKE_Z - 0.2), (x + w, y, LAKE_Z - 0.2), (x + w + sl, y, 2.0),
                                       (x - w + sl, y, 2.0))]
        bm.faces.new(vs)
        ray = lib.mesh_from_bm(f"light_ray{k}", bm, ray_mat, R)
        ray.visible_shadow = False
        self.src_rays.append(ray)
    for ob in self.src_fish + self.src_leaves + self.src_specks + self.src_rays:
        lib.visible(ob, 1, False)


# ---------------------------------------------------------------- trees, rocks, streams, rain

def _dam_top(x):
    if x < 6.6:
        return CREST_Z
    return max(0.0, CREST_Z - (x - 6.6) / (DAM_TOE - 6.6) * CREST_Z)


def _tree_protos(R):
    protos = []
    for k in range(3):
        protos.append(P.tree(f"src_tproto{k}", (0, 0, -1000), h=1.0, parent=None, seed=80 + k))
    needles = lib.material("Grass001", scale=2.0, tint=(0.42, 0.62, 0.45), name="conifer_needles")
    bark = lib.flat("bark", lib.hexrgb("#5A4632"), 0.8)
    for k in range(3):
        root = lib.empty(f"src_cproto{k}", (0, 0, -1000))
        lib.tube(f"src_cproto{k}_trunk", [(0, 0, 0), (0, 0, 0.35)], 0.035, bark, root)
        for t, (z, r, d) in enumerate(((0.18, 0.26 - 0.02 * k, 0.45), (0.42, 0.2, 0.38), (0.62, 0.13, 0.34))):
            bm = bmesh.new()
            bmesh.ops.create_cone(bm, cap_ends=True, segments=9, radius1=r, radius2=0.0, depth=d)
            for v in bm.verts:
                v.co.z += z + d / 2
            lib.mesh_from_bm(f"src_cproto{k}_tier{t}", bm, needles, root, smooth=True)
        protos.append(root)
    return protos


def _plant_trees(R, rnd, count):
    protos = _tree_protos(R)
    n = 0
    tries = 0
    while n < count and tries < count * 30:
        tries += 1
        x = rnd.uniform(-430, 400)
        y = 12 + (rnd.random() ** 1.3) * 330
        z = h(x, y)
        if x < 4 and z < LAKE_Z + 2.0:
            continue
        if -6 < x < DAM_TOE + 6 and z < _dam_top(x) + 2.0:
            continue
        if x > DAM_TOE and y < 18:
            continue
        if z > 150:
            continue
        g = V((h(x + 2, y) - h(x - 2, y), h(x, y + 2) - h(x, y - 2), 4.0)).normalized()
        if g.z < 0.78:
            continue
        # forests: denser where a low-frequency noise says so
        if _n(x, y, 140.0) < -0.3 and rnd.random() < 0.7:
            continue
        proto = protos[rnd.randrange(len(protos))]
        root = lib.empty(f"src_tree{n}", (x, y, z - 0.3), R)
        hgt = rnd.uniform(9.0, 17.0)
        root.scale = (hgt, hgt, hgt * rnd.uniform(0.9, 1.15))
        root.rotation_euler = (0, 0, rnd.uniform(0, 6.28))
        for c in proto.children:
            o = c.copy()
            bpy.context.scene.collection.objects.link(o)
            o.parent = root
        n += 1
    for proto in protos:
        for c in list(proto.children):
            bpy.data.objects.remove(c)
        bpy.data.objects.remove(proto)


def _rocks(R, rnd):
    m = rock()
    for k in range(60):
        x = rnd.uniform(-300, -5)
        y = rnd.uniform(4, 120)
        z = h(x, y)
        if abs(z - LAKE_Z) > 3.0 and rnd.random() < 0.7:
            continue
        lib.blob(f"src_rock{k}", rnd.uniform(0.6, 2.2), m, (x, y, z - 0.2), squash=0.55, seed=k, parent=R, lumpy=0.35)


def _streams(self, R):
    """Hillside brooks: each follows the slope down (steepest descent) until it reaches the reservoir."""
    flow = P.water("brook", "#A9D6D0", "#F2FAF8", speed=3.0, foam_amount=0.42, scale=(0.35, 1.6, 1.6),
                   density=0, rough=0.05)
    starts = [(-205, 210), (-150, 240), (-95, 190), (-48, 230), (-250, 170), (-125, 140)]
    for k, (x, y) in enumerate(starts):
        pts = []
        p = V((x, y))
        for _ in range(400):
            z = h(p.x, p.y)
            pts.append(V((p.x, p.y, z)))
            if z < LAKE_Z - 0.4 or p.y < 2:
                break
            g = V(((h(p.x + 1.5, p.y) - h(p.x - 1.5, p.y)) / 3, (h(p.x, p.y + 1.5) - h(p.x, p.y - 1.5)) / 3))
            if g.length < 1e-4:
                g = V((0, 1))
            d = -g.normalized()
            d.y = min(d.y, -0.25)      # keep heading down toward the lake
            p = p + d.normalized() * 2.5
        if len(pts) < 6:
            continue
        bm = bmesh.new()
        uv = bm.loops.layers.uv.new("UVMap")
        rows, s = [], [0.0]
        for a, b in zip(pts, pts[1:]):
            s.append(s[-1] + (b - a).length)
        for i, q in enumerate(pts):
            a, b = pts[max(0, i - 1)], pts[min(len(pts) - 1, i + 1)]
            t = V((b.x - a.x, b.y - a.y, 0)).normalized()
            side = V((-t.y, t.x, 0))
            w = 1.0 + 2.4 * i / len(pts)
            row = []
            for sgn in (-1, 1):
                c = q + side * sgn * w / 2
                row.append(bm.verts.new((c.x, c.y, h(c.x, c.y) + 0.35)))
            rows.append(row)
        for i in range(len(rows) - 1):
            f = bm.faces.new((rows[i][0], rows[i][1], rows[i + 1][1], rows[i + 1][0]))
            f.smooth = True
            for loop, (u, v) in zip(f.loops, ((s[i], 0), (s[i], 1), (s[i + 1], 1), (s[i + 1], 0))):
                loop[uv].uv = (u, v)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        for f in bm.faces:
            if f.normal.z < 0:
                f.normal_flip()
        lib.mesh_from_bm(f"brook{k}", bm, flow, R)


def _rain_sheet(R, name, x0, x1, y0, y1, count, seed, length, width, height=250.0, z0=-12.0):
    """Falling rain: thin streaks repeated twice up a column of `height`, slid down one height per cycle."""
    rnd = random.Random(seed)
    spots = [(rnd.uniform(x0, x1), rnd.uniform(y0, y1), rnd.uniform(0, height), rnd.uniform(0.7, 1.3))
             for _ in range(count)]
    bm = bmesh.new()
    for rep in (0, 1):
        for x, y, z, k in spots:
            z += z0 + rep * height
            L, w, sl = length * k, width * k, -0.08 * length * k
            vs = [bm.verts.new(p) for p in ((x - w / 2, y, z), (x + w / 2, y, z), (x + w / 2 + sl, y, z + L),
                                           (x - w / 2 + sl, y, z + L))]
            bm.faces.new(vs)
    ob = lib.mesh_from_bm(name, bm, _rain_mat(R), R)
    ob.visible_shadow = False
    return ob


def _rain_mat(R):
    """Pale streaks, faded out below the reservoir's surface (its cut face is see-through), in station space."""
    name = "rain_streak"
    if name in lib._mats:
        return lib._mats[name]
    mat = lib.flat(name, lib.hexrgb("#E4ECF2"), 0.3, emission=0.5, alpha=0.32)
    nt, bsdf = lib._bsdf(mat)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.object = R
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs["Vector"])
    above = _ramp(nt, sep.outputs["Z"], LAKE_Z, LAKE_Z + 0.6)
    downstream = _ramp(nt, sep.outputs["X"], 1.0, 3.0)
    keep = _math(nt, "MAXIMUM", above, downstream)
    nt.links.new(_math(nt, "MULTIPLY", keep, 0.32), bsdf.inputs["Alpha"])
    return mat


def _cloud(R, name, at, size, seed):
    """A rain cloud: a noisy ball of volume (soft edges, self-shadowed grey underside)."""
    mat = lib._mats.get("rain_cloud_vol")
    if mat is None:
        mat = bpy.data.materials.new("rain_cloud_vol")
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        tc = nt.nodes.new("ShaderNodeTexCoord")
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 2.2
        nz.inputs["Detail"].default_value = 6.0
        nz.inputs["Roughness"].default_value = 0.6
        nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        grad = nt.nodes.new("ShaderNodeTexGradient")
        grad.gradient_type = "SPHERICAL"
        nt.links.new(tc.outputs["Object"], grad.inputs["Vector"])
        m1 = nt.nodes.new("ShaderNodeMath")
        m1.operation = "MULTIPLY_ADD"
        nt.links.new(nz.outputs["Fac"], m1.inputs[0])
        m1.inputs[1].default_value = 1.8
        nt.links.new(grad.outputs["Fac"], m1.inputs[2])
        m2 = nt.nodes.new("ShaderNodeMapRange")
        m2.inputs["From Min"].default_value = 1.15
        m2.inputs["From Max"].default_value = 1.6
        m2.inputs["To Max"].default_value = 0.09
        nt.links.new(m1.outputs["Value"], m2.inputs["Value"])
        vol = nt.nodes.new("ShaderNodeVolumePrincipled")
        vol.inputs["Color"].default_value = (*lib.hexrgb("#D2D6DB"), 1)
        nt.links.new(m2.outputs["Result"], vol.inputs["Density"])
        nt.links.new(vol.outputs["Volume"], out.inputs["Volume"])
        lib._mats["rain_cloud_vol"] = mat
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
    ob = lib.mesh_from_bm(name, bm, mat, R)
    ob.location = at
    ob.scale = size
    ob.rotation_euler = (0, 0, seed * 0.7)
    return ob


def _weather(self, R):
    rnd = random.Random(4)
    # rain falls only behind the cut (rain in front of it would fall over the section faces)
    H = 250.0
    self.src_rain = [
        _rain_sheet(R, "rain_near", -330, 170, 1.0, 110, 3800, 1, 5.0, 0.2, H),
        _rain_sheet(R, "rain_mid", -380, 240, 110, 250, 3800, 2, 7.0, 0.3, H),
        _rain_sheet(R, "rain_far", -440, 330, 250, 420, 3200, 3, 9.0, 0.42, H),
    ]
    for k, sheet in enumerate(self.src_rain):
        P.cycle_rise(sheet, 0.0, -H, int(H / 9.0 * 30), -k * 37)
    self.src_clouds = []
    for k, (x, y, z, sx, sy, sz) in enumerate(((-260, 260, 215, 120, 80, 34), (-120, 300, 230, 150, 90, 40),
                                               (40, 250, 210, 110, 70, 32), (-200, 140, 245, 90, 60, 28),
                                               (120, 330, 240, 140, 90, 36), (-360, 360, 235, 130, 80, 34))):
        self.src_clouds.append(_cloud(R, f"rain_cloud{k}", (x + rnd.uniform(-20, 20), y, z), (sx, sy, sz), k))
    for ob in self.src_rain + self.src_clouds:
        lib.visible(ob, 1, False)


# ---------------------------------------------------------------- build

def build_source(self):
    R = self.root("source")
    rnd = random.Random(11)
    ee = self.scene.eevee
    if hasattr(ee, "use_volumetric_shadows"):
        ee.use_volumetric_shadows = True
    _terrain(R)
    _dam(R)
    _water(self, R)
    _intake(self, R)
    _streams(self, R)
    _plant_trees(R, rnd, 460)
    _rocks(R, rnd)
    _weather(self, R)
    # anchors for the compositor
    self.anchor("source", "dam", (13.0, -0.02, 13.0))
    self.anchor("source", "reservoir", (-16.0, -0.02, 20.0))
    self.anchor("source", "intake_screen", (SCREEN_X, -0.02, INTAKE_Z + 1.6))
    return R


def _far_clip(self, s, e):
    """Wide valley shots see hills farther than the default clip distance."""
    data = self.cam.data
    data.clip_end = 600.0
    data.keyframe_insert("clip_end", frame=s - 1)
    data.clip_end = 2000.0
    data.keyframe_insert("clip_end", frame=s)
    data.clip_end = 600.0
    data.keyframe_insert("clip_end", frame=e + 1)
    for fc in lib.fcurves(data):
        if fc.data_path == "clip_end":
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"


def _overcast(self, s, e):
    """A rain shower: dimmer sky and sun for the beat, the day back at the next cut (constant keys)."""
    bg = self.world_bg.inputs["Strength"]
    sun = self.sun.data
    day_bg, day_sun = bg.default_value, sun.energy
    for f, day in ((s - 1, True), (s, False), (e + 1, True)):
        lib.node_key(bg, f, day_bg if day else day_bg * 0.6, interp="CONSTANT")
        sun.energy = day_sun if day else day_sun * 0.45
        sun.keyframe_insert("energy", frame=f)
    for fc in lib.fcurves(sun):
        if fc.data_path == "energy":
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"
    bg.default_value, sun.energy = day_bg, day_sun


# ---------------------------------------------------------------- shots

def _lake_clarity(self, s, deep, top):
    am = self.src_lake_alpha
    lib.node_key(am.inputs["To Min"], s, deep, interp="CONSTANT")
    lib.node_key(am.inputs["To Max"], s, top, interp="CONSTANT")


def rain(self, s, e):
    self.on_station("source", s, e)
    _lake_clarity(self, s, 0.94, 0.5)
    self.shot("source", s, e, dict(center=(-80, 40, 62), width=215, yaw=12, pitch=21, lens=30),
              dict(center=(-70, 40, 58), width=196, yaw=8, pitch=20, lens=30))
    _far_clip(self, s, e)
    for ob in self.src_rain + self.src_clouds:
        lib.visible(ob, s, True)
        lib.visible(ob, e + 1, False)
    _overcast(self, s, e)
    events.add(s, "rain", duration=e - s + 8, gain=0.9)
    events.add(s + 10, "lake", duration=e - s, gain=0.4)


def dam(self, s, e):
    self.on_station("source", s, e)
    _lake_clarity(self, s, 0.94, 0.5)
    L = sum((b - a).length for a, b in zip(self.src_dam_path, self.src_dam_path[1:]))
    for k, a in enumerate(self.src_dam_arrows):
        P.ride(a, self.src_dam_path, s, e, 7.0, offset=k * L / len(self.src_dam_arrows), normal_offset=(0, -0.05, 0))
    self.shot("source", s, e, dict(center=(1.0, 0, 8.0), width=60, yaw=20, pitch=8, lens=32),
              dict(center=(-1.0, 0, 8.5), width=54, yaw=15, pitch=9, lens=32))
    _far_clip(self, s, e)
    events.add(s, "lake", duration=e - s, gain=0.7)
    events.add(s, "pour", duration=e - s, gain=0.25)


def intake(self, s, e):
    self.on_station("source", s, e)
    _lake_clarity(self, s, 0.34, 0.14)
    for k, ray in enumerate(self.src_rays):
        lib.visible(ray, s, True)
        lib.visible(ray, e + 1, False)
        lib.tween(ray, "location", s, e, (0, 0, 0), (0.6 + 0.1 * k, 0, 0), "linear")
    self.shot("source", s, e, dict(center=(-4.6, 0.8, INTAKE_Z - 0.6), width=10.5, yaw=-34, pitch=5, lens=35),
              dict(center=(-3.8, 0.8, INTAKE_Z - 0.7), width=10.0, yaw=-29, pitch=5, lens=35))
    _far_clip(self, s, e)
    L = sum((b - a).length for a, b in zip(self.src_path, self.src_path[1:]))
    for k, a in enumerate(self.src_arrows):
        P.ride(a, self.src_path, s, e, 2.6, offset=k * L / len(self.src_arrows), normal_offset=(0, -0.03, 0))
    for sp in self.src_specks:
        lib.visible(sp, s, True)
        lib.visible(sp, e + 1, False)
    rnd = random.Random(8)
    n = e - s
    # leaves drift in with the flow and stick to the bars
    for k, lf in enumerate(self.src_leaves):
        y = rnd.uniform(0.25, 1.8)
        z = rnd.uniform(INTAKE_Z - 3.0, INTAKE_Z + 3.0)
        start = (rnd.uniform(-15.0, -7.0), y, z + rnd.uniform(-0.8, 0.8))
        stop = (SCREEN_X - 0.06 - 0.01 * (k % 3), y, z)
        t1 = s + int(n * rnd.uniform(0.35, 0.85))
        lib.visible(lf, s, True)
        lib.visible(lf, e + 1, False)
        lf.rotation_euler = (math.radians(rnd.uniform(-40, 40)), math.radians(rnd.uniform(-30, 30)), 0)
        lib.tween(lf, "location", s, t1, start, stop, "out")
        lib.key(lf, "rotation_euler", t1, (math.radians(rnd.uniform(-10, 10)), math.radians(90), 0))
        lib.key(lf, "rotation_euler", s, (math.radians(rnd.uniform(-60, 60)), math.radians(rnd.uniform(-40, 40)),
                                          math.radians(rnd.uniform(0, 180))))
    # fish swim up to the screen, nose the bars, and turn away
    for k, fish in enumerate(self.src_fish):
        y = rnd.uniform(0.45, 1.5)
        z = rnd.uniform(INTAKE_Z - 2.5, INTAKE_Z + 2.8)
        a = (rnd.uniform(-14.0, -9.0), y, z)
        b = (SCREEN_X - 0.75, y + rnd.uniform(-0.3, 0.3), z + rnd.uniform(-0.3, 0.3))
        t1 = s + int(n * rnd.uniform(0.2, 0.55))
        t2 = min(e, t1 + int(n * 0.14))
        c = (b[0] - 3.5, b[1] + rnd.uniform(-0.6, 0.6), b[2] + rnd.uniform(-0.8, 0.8))
        lib.visible(fish, s, True)
        lib.visible(fish, e + 1, False)
        lib.tween(fish, "location", s, t1, a, b, "out")
        lib.key(fish, "location", t2, b)
        lib.tween(fish, "location", t2, t2 + 45, b, c, "in")
        # heading: +x while approaching, turns round, swims away; a steady tail beat as a body wiggle
        for f in range(s, e + 1, 3):
            turn = 0.0 if f < t2 else min(1.0, (f - t2) / 12.0) * math.pi
            wig = math.radians(9) * math.sin((f - s) * 0.9 + k)
            lib.key(fish, "rotation_euler", f, (0, 0, turn + wig), interp="LINEAR")
    events.add(s, "water_rush", duration=e - s, gain=0.6)
    events.add(s, "bubbles", duration=e - s, gain=0.4)


SHOTS = (build_source, rain, dam, intake)
