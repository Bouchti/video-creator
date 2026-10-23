"""
Cutaway (cross-section) set for 3D explainers — the "ant farm" view.

The world is sliced by a vertical SECTION PLANE at y = CUT. Everything that matters exists
only behind it (y >= CUT); the camera sits in front (y < CUT) and looks +Y, so the cut faces
show what is normally hidden: soil strata, the water table, gravel, the concrete shell, plaster,
water, and pipes. Materials that must read as continuous layers across separate objects (soil)
are driven by WORLD coordinates, so every block's cut face lines up perfectly.

Rules that keep it flicker-free (see blender-engine notes): no two visible faces share a
plane; things "drawn in the section" (pipes, valve, labels, dimension lines) sit a few cm in
FRONT of the cut face (y < CUT) instead of on it.

This module builds the reusable pieces (ground with a hole, yard dressing, pool layers, pipes
with flowing water, callouts). A film script places and times them.
"""
import math
import random

import bpy
from mathutils import Vector

from engine import events, toy
from engine.backyard import _appear, _hide, _key

R = math.radians
CUT = 0.0                     # section plane (y)
GROUND_DEPTH = 10.0           # how deep the cut face goes (deeper than any framing can see)
TURF = 0.05                   # grass layer thickness on top of the soil

# Pool (metres). Only the back half of its width exists: the cut runs down its long axis.
POOL_L = 6.0                  # length along X
POOL_HALF_W = 1.5             # half width (Y, from the cut to the back wall)
HOLE = 1.8                    # excavation depth
GRAVEL = 0.1
SHELL = 0.2
PLASTER = 0.03
FLOOR_TOP = -HOLE + GRAVEL + SHELL          # inside floor of the shell (-1.5)
WATER_TOP = -0.15
STRATA = {"topsoil": (0.0, -0.45), "clay": (-0.45, -1.9), "sand": (-1.9, -3.2), "rock": (-3.2, -GROUND_DEPTH)}
WATER_TABLE = -3.4            # resting groundwater level (animatable)


def _mat_node_value(mat, name, value):
    nt = mat.node_tree
    v = nt.nodes.new("ShaderNodeValue")
    v.name = v.label = name
    v.outputs[0].default_value = value
    return v


def strata_material():
    """Soil cross-section: crisp layers by WORLD height (wavy boundaries), pebbles, and a
    groundwater zone below an animatable `water_table` value (bluish, darker, glossier)."""
    mat = bpy.data.materials.new("strata")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    # Wavy layer boundaries: z + noise(x) * amplitude.
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.6
    noise.inputs["Detail"].default_value = 3
    nt.links.new(geo.outputs["Position"], noise.inputs["Vector"])
    wob = nt.nodes.new("ShaderNodeMath")
    wob.operation = "MULTIPLY_ADD"
    nt.links.new(noise.outputs["Fac"], wob.inputs[0])
    wob.inputs[1].default_value = 0.35
    wob.inputs[2].default_value = -0.175
    zw = nt.nodes.new("ShaderNodeMath")
    zw.operation = "ADD"
    nt.links.new(sep.outputs["Z"], zw.inputs[0])
    nt.links.new(wob.outputs[0], zw.inputs[1])
    # Map z ∈ [-GROUND_DEPTH, 0] → [0, 1] for the ramp.
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -GROUND_DEPTH
    mr.inputs["From Max"].default_value = 0.0
    nt.links.new(zw.outputs[0], mr.inputs["Value"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    els = ramp.color_ramp.elements
    layers = [(0.0, "#6E6A64"), (1 - 3.2 / GROUND_DEPTH, "#C9A66B"), (1 - 1.9 / GROUND_DEPTH, "#A0603A"),
              (1 - 0.45 / GROUND_DEPTH, "#4A3222")]
    els[0].position, els[0].color = layers[0][0], (*toy.srgb(layers[0][1]), 1)
    els[1].position, els[1].color = layers[1][0], (*toy.srgb(layers[1][1]), 1)
    for pos, col in layers[2:]:
        e = els.new(pos)
        e.color = (*toy.srgb(col), 1)
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    # Grain: fine noise shading + pebbles (voronoi) for texture.
    grain = nt.nodes.new("ShaderNodeTexNoise")
    grain.inputs["Scale"].default_value = 22
    grain.inputs["Detail"].default_value = 8
    nt.links.new(geo.outputs["Position"], grain.inputs["Vector"])
    shade = nt.nodes.new("ShaderNodeMix")
    shade.data_type = "RGBA"
    shade.blend_type = "MULTIPLY"
    shade.inputs["Factor"].default_value = 0.45
    nt.links.new(ramp.outputs["Color"], shade.inputs["A"])
    gr = nt.nodes.new("ShaderNodeMapRange")
    gr.inputs["To Min"].default_value = 0.7
    gr.inputs["To Max"].default_value = 1.25
    nt.links.new(grain.outputs["Fac"], gr.inputs["Value"])
    comb = nt.nodes.new("ShaderNodeCombineColor")
    for k in ("Red", "Green", "Blue"):
        nt.links.new(gr.outputs["Result"], comb.inputs[k])
    nt.links.new(comb.outputs[0], shade.inputs["B"])
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 9
    nt.links.new(geo.outputs["Position"], vor.inputs["Vector"])
    peb = nt.nodes.new("ShaderNodeMath")
    peb.operation = "LESS_THAN"
    nt.links.new(vor.outputs["Distance"], peb.inputs[0])
    peb.inputs[1].default_value = 0.12
    pebcol = nt.nodes.new("ShaderNodeMix")
    pebcol.data_type = "RGBA"
    nt.links.new(peb.outputs[0], pebcol.inputs["Factor"])
    nt.links.new(shade.outputs["Result"], pebcol.inputs["A"])
    pebcol.inputs["B"].default_value = (*toy.srgb("#8D877E"), 1)
    # Groundwater: below the (animatable) water table the soil turns wet blue.
    wt = _mat_node_value(mat, "water_table", WATER_TABLE)
    below = nt.nodes.new("ShaderNodeMath")
    below.operation = "LESS_THAN"
    nt.links.new(sep.outputs["Z"], below.inputs[0])
    nt.links.new(wt.outputs[0], below.inputs[1])
    wet = nt.nodes.new("ShaderNodeMix")
    wet.data_type = "RGBA"
    wet.blend_type = "MIX"
    nt.links.new(below.outputs[0], wet.inputs["Factor"])
    nt.links.new(pebcol.outputs["Result"], wet.inputs["A"])
    tint = nt.nodes.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    tint.blend_type = "MULTIPLY"
    tint.inputs["Factor"].default_value = 0.75
    nt.links.new(pebcol.outputs["Result"], tint.inputs["A"])
    tint.inputs["B"].default_value = (*toy.srgb("#7FB6F0"), 1)
    nt.links.new(tint.outputs["Result"], wet.inputs["B"])
    nt.links.new(wet.outputs["Result"], bsdf.inputs["Base Color"])
    rough = nt.nodes.new("ShaderNodeMapRange")
    nt.links.new(below.outputs[0], rough.inputs["Value"])
    rough.inputs["To Min"].default_value = 0.92
    rough.inputs["To Max"].default_value = 0.7          # damp, not glossy (a glossy face shows the lights)
    nt.links.new(rough.outputs["Result"], bsdf.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    nt.links.new(grain.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    mat["water_table_node"] = "water_table"
    return mat


def gravel_material():
    mat = bpy.data.materials.new("gravel_section")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 38
    nt.links.new(geo.outputs["Position"], vor.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*toy.srgb("#5D5A55"), 1)
    ramp.color_ramp.elements[1].color = (*toy.srgb("#C8C2B6"), 1)
    nt.links.new(vor.outputs["Color"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.8
    nt.links.new(vor.outputs["Distance"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.85
    return mat


def flow_material(name, direction=1.0, speed=0.9, base="#2F8FE0", stripe="#BFE9FF"):
    """Water flowing along a pipe segment's local Z: moving light stripes (texture motion, so
    nothing teleports). A `flow_on` value (0..1, keyable) fades the stripes in when pumping."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "Z"
    wave.inputs["Scale"].default_value = 1.6
    wave.inputs["Distortion"].default_value = 0.0
    nt.links.new(mp.outputs["Vector"], wave.inputs["Vector"])
    sharp = nt.nodes.new("ShaderNodeMapRange")
    sharp.inputs["From Min"].default_value = 0.55
    sharp.inputs["From Max"].default_value = 0.8
    nt.links.new(wave.outputs["Fac"], sharp.inputs["Value"])
    on = _mat_node_value(mat, "flow_on", 0.0)
    gate = nt.nodes.new("ShaderNodeMath")
    gate.operation = "MULTIPLY"
    nt.links.new(sharp.outputs["Result"], gate.inputs[0])
    nt.links.new(on.outputs[0], gate.inputs[1])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(gate.outputs[0], mix.inputs["Factor"])
    mix.inputs["A"].default_value = (*toy.srgb(base), 1)
    mix.inputs["B"].default_value = (*toy.srgb(stripe), 1)
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    toy._set(bsdf, "Emission Color", (*toy.srgb(base), 1))
    if "Emission Strength" in bsdf.inputs:
        nt.links.new(gate.outputs[0], bsdf.inputs["Emission Strength"])
    bsdf.inputs["Roughness"].default_value = 0.2
    # Stripes travel along +Z (direction=1) at `speed` m/s: animate the mapping offset linearly.
    loc = mp.inputs["Location"]
    loc.default_value = (0, 0, 0)
    loc.keyframe_insert("default_value", frame=1)
    loc.default_value = (0, 0, -direction * speed * 6000 / 30)
    loc.keyframe_insert("default_value", frame=6001)
    for fc in _node_curves(mat):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    return mat


def caustics_plaster_material(fps=30):
    """Pool plaster that shows animated CAUSTICS (rippling light lines) below the waterline.
    `water_level` (keyable) masks them, so they appear as the pool fills."""
    mat = bpy.data.materials.new("pool_plaster")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.4
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.voronoi_dimensions = "4D"
    vor.feature = "DISTANCE_TO_EDGE"
    vor.inputs["Scale"].default_value = 6.5
    nt.links.new(geo.outputs["Position"], vor.inputs["Vector"])
    w = vor.inputs["W"]
    w.default_value = 0.0
    w.keyframe_insert("default_value", frame=1)
    w.default_value = 0.022 * 6000
    w.keyframe_insert("default_value", frame=6001)
    lines = nt.nodes.new("ShaderNodeMapRange")
    lines.inputs["From Min"].default_value = 0.0
    lines.inputs["From Max"].default_value = 0.035
    lines.inputs["To Min"].default_value = 1.0
    lines.inputs["To Max"].default_value = 0.0
    nt.links.new(vor.outputs["Distance"], lines.inputs["Value"])
    level = _mat_node_value(mat, "water_level", -50.0)
    below = nt.nodes.new("ShaderNodeMath")
    below.operation = "LESS_THAN"
    nt.links.new(sep.outputs["Z"], below.inputs[0])
    nt.links.new(level.outputs[0], below.inputs[1])
    amt = nt.nodes.new("ShaderNodeMath")
    amt.operation = "MULTIPLY"
    nt.links.new(lines.outputs["Result"], amt.inputs[0])
    nt.links.new(below.outputs[0], amt.inputs[1])
    gain = nt.nodes.new("ShaderNodeMath")
    gain.operation = "MULTIPLY"
    nt.links.new(amt.outputs[0], gain.inputs[0])
    gain.inputs[1].default_value = 0.9
    toy._set(bsdf, "Emission Color", (0.72, 0.93, 1.0, 1))
    nt.links.new(gain.outputs[0], bsdf.inputs["Emission Strength"])
    # Under water the wall reads bluer.
    tint = nt.nodes.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    nt.links.new(below.outputs[0], tint.inputs["Factor"])
    tint.inputs["A"].default_value = (*toy.srgb("#E3F1F7"), 1)
    tint.inputs["B"].default_value = (*toy.srgb("#A9DDF2"), 1)
    nt.links.new(tint.outputs["Result"], bsdf.inputs["Base Color"])
    for fc in _node_curves(mat):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    return mat


def water_section_material():
    """Water seen in section: lighter turquoise near the surface, deeper blue at the bottom."""
    mat = bpy.data.materials.new("pool_water")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = FLOOR_TOP
    mr.inputs["From Max"].default_value = WATER_TOP
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*toy.srgb("#145A9E"), 1)
    ramp.color_ramp.elements[1].color = (*toy.srgb("#4CC3F2"), 1)
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.04
    toy._set(bsdf, "Alpha", 0.66)
    toy._set(bsdf, "IOR", 1.33)
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"
    return mat


def roof_tile_material():
    """Clay roof tiles: rows (saw-wave bands) with patchy colour variation."""
    mat = bpy.data.materials.new("roof_tiles")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.bands_direction = "Z"
    wave.wave_profile = "SAW"
    wave.inputs["Scale"].default_value = 0.9
    nt.links.new(geo.outputs["Position"], wave.inputs["Vector"])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3
    nt.links.new(geo.outputs["Position"], noise.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*toy.srgb("#7E3420"), 1)
    ramp.color_ramp.elements[1].color = (*toy.srgb("#C25A35"), 1)
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    shade = nt.nodes.new("ShaderNodeMix")
    shade.data_type = "RGBA"
    shade.blend_type = "MULTIPLY"
    shade.inputs["Factor"].default_value = 0.35
    nt.links.new(ramp.outputs["Color"], shade.inputs["A"])
    nt.links.new(wave.outputs["Color"], shade.inputs["B"])
    nt.links.new(shade.outputs["Result"], bsdf.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.6
    nt.links.new(wave.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.65
    return mat


def _node_curves(mat):
    ad = mat.node_tree.animation_data
    if not ad or not ad.action:
        return []
    legacy = getattr(ad.action, "fcurves", None)
    if legacy is not None:
        return list(legacy)
    return [fc for layer in ad.action.layers for strip in layer.strips for bag in strip.channelbags
            for fc in bag.fcurves]


def key_node_value(mat, node_name, frame, value, interpolation=None):
    node = mat.node_tree.nodes[node_name]
    node.outputs[0].default_value = value
    node.outputs[0].keyframe_insert("default_value", frame=frame)
    if interpolation:
        for fc in _node_curves(mat):
            for kp in fc.keyframe_points:
                if int(round(kp.co.x)) == frame:
                    kp.interpolation = interpolation


def _block(name, x0, x1, y0, y1, z0, z1, mat, bevel=0):
    return toy.box(name, (x1 - x0, y1 - y0, z1 - z0), ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2),
                   mat=mat, bevel=bevel)


class CutawayYard:
    """The pool site, cut open along its long axis. Pool centred on x = 0."""

    def __init__(self, seed: int = 7):
        self.rnd = random.Random(seed)
        self.m = {
            "strata": strata_material(),
            "grass": toy.noise_material("lawn", toy.srgb("#3F7F2E"), toy.srgb("#5A9A3A"), scale=40, bump=0.3),
            "gravel": gravel_material(),
            "concrete": toy.noise_material("shell_concrete", toy.srgb("#9A9893"), toy.srgb("#B8B6B0"),
                                           scale=60, roughness=0.9, bump=0.25),
            "plaster": caustics_plaster_material(),
            "tile": toy.material("pool_tile", toy.srgb("#1F6FB8"), roughness=0.15, coat=0.6),
            "coping": toy.noise_material("coping_stone", toy.srgb("#D9D0BE"), toy.srgb("#EDE6D6"),
                                         scale=18, roughness=0.6, bump=0.2),
            "steel": toy.material("rebar_steel", toy.srgb("#7A3B22"), roughness=0.55, metallic=0.6),
            "pipe": self._pipe_material(),
            "wood": toy.noise_material("fence_wood", toy.srgb("#8B6A4A"), toy.srgb("#A07E5C"), scale=10, bump=0.2),
            "white": toy.material("house_white", toy.srgb("#EFEDE6"), roughness=0.7),
            "roof": roof_tile_material(),
            "window": toy.material("glass_win", toy.srgb("#8FB9D4"), roughness=0.05, coat=1.0),
            "leaf": toy.noise_material("foliage", toy.srgb("#3D6B2A"), toy.srgb("#5E8C38"), scale=6, bump=0.6),
            "bark": toy.noise_material("bark", toy.srgb("#5A4632"), toy.srgb("#74604A"), scale=12, bump=0.6),
            "water": water_section_material(),
            "stone": toy.noise_material("section_stone", toy.srgb("#58534C"), toy.srgb("#7A746A"), scale=6,
                                        roughness=0.8, bump=0.8),
            "steel_bright": toy.material("stainless", toy.srgb("#D9DDE2"), roughness=0.15, metallic=1.0),
        }
        hl = POOL_L / 2
        self.hl = hl
        self.back = CUT + POOL_HALF_W
        self._ground()
        self._columns()
        self._yard()
        self._grass()
        self._stones()
        self._clouds()
        self.pool_root = toy.empty("pool_root", (0, 0, 0))   # everything that "floats" in the hook

    # ------------------- materials -------------------

    @staticmethod
    def _pipe_material():
        mat = toy.material("pipe_clear", toy.srgb("#E8EEF2"), roughness=0.08, alpha=0.28)
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "BLENDED"
        return mat

    @staticmethod
    def _water_material():
        mat = toy.material("pool_water", toy.srgb("#2E9BE0"), roughness=0.05, alpha=0.62)
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "BLENDED"
        return mat

    # ------------------- ground -------------------

    def _ground(self):
        hl, s, d = self.hl, self.m["strata"], -GROUND_DEPTH
        top = -TURF
        far = 40
        # Soil blocks around the hole (all strata, world-aligned so the cut face is continuous).
        _block("soil_back", -far, far, self.back, far, d, top, s)
        _block("soil_west", -far, -hl, CUT, self.back, d, top, s)
        _block("soil_east", hl, far, CUT, self.back, d, top, s)
        _block("soil_under", -hl, hl, CUT, self.back, d, -HOLE - 0.12, s)
        g = self.m["grass"]
        _block("turf_back", -far, far, self.back, far, top, 0, g)
        _block("turf_west", -far, -hl, CUT, self.back, top, 0, g)
        _block("turf_east", hl, far, CUT, self.back, top, 0, g)

    def _columns(self, n: int = 4):
        """Soil inside the future hole, in removable slices (west → east), each with its turf."""
        hl, s, g = self.hl, self.m["strata"], self.m["grass"]
        self.col_bottom = -HOLE - 0.12
        self.columns = []
        for i in range(n):
            x0, x1 = -hl + POOL_L * i / n, -hl + POOL_L * (i + 1) / n
            col = _block(f"soil_col{i}", x0, x1, CUT, self.back, self.col_bottom, -TURF, s)
            turf = _block(f"turf_col{i}", x0, x1, CUT, self.back, -TURF, 0, g)
            self.columns.append({"col": col, "turf": turf, "x": (x0 + x1) / 2, "h0": -TURF - self.col_bottom,
                                 "top": -TURF})

    def dig_plan(self, passes: int = 2):
        n = len(self.columns)
        plan = []
        for p in range(passes):
            depth = -TURF - (HOLE + 0.005 - TURF) * (p + 1) / passes
            order = range(n - 1, -1, -1) if p % 2 == 0 else range(n)      # east → west, then back
            plan.extend((i, depth) for i in order)
        return plan

    def column_top(self, i: int, frame: int, top: float):
        col = self.columns[i]
        _key(col["col"], frame, scale=Vector((1, 1, (top - self.col_bottom) / col["h0"])),
             location=Vector((col["x"], (CUT + self.back) / 2, (top + self.col_bottom) / 2)))
        col["top"] = top

    def bite(self, i: int, bite_frame: int, curl_frame: int, new_top: float):
        col = self.columns[i]
        if col["turf"] is not None:
            for o in (col["turf"], col.get("tufts")):
                if o is not None:
                    _hide(o, 0, False)
                    _hide(o, bite_frame + 1, True)
            col["turf"] = None
        self.column_top(i, bite_frame, col["top"])
        self.column_top(i, curl_frame + 2, new_top)

    def spoil_pile(self, location, dumps, final_scale=(1.8, 1.4, 1.0)):
        pile = toy.sphere("spoil_pile", 1.0, location, scale=(0.3, 0.3, 0.2),
                          mat=toy.noise_material("spoil", toy.srgb("#5A3D28"), toy.srgb("#7A5536"), scale=8, bump=0.9))
        _hide(pile, 0, True)
        _hide(pile, dumps[0] + 1, False)
        final = Vector(final_scale)
        _key(pile, dumps[0], scale=Vector((0.3, 0.3, 0.2)))
        for k, f in enumerate(dumps):
            frac = ((k + 1) / len(dumps)) ** 0.6
            _key(pile, f + 5, scale=Vector((max(0.3, final.x * frac), max(0.3, final.y * frac),
                                            max(0.2, final.z * frac))))
        self.pile = pile
        return pile

    # ------------------- yard dressing -------------------

    def _yard(self):
        m = self.m
        hx, hy = 0.5, 13.0
        toy.box("house", (11, 6, 4.4), (hx, hy, 2.2), mat=m["white"], bevel=0.05)
        for i, ry in enumerate((-1, 1)):
            toy.box(f"roof{i}", (11.8, 3.9, 0.25), (hx, hy + 1.5 * ry, 5.25), mat=m["roof"], bevel=0.04,
                    rotation=(R(-28 * ry), 0, 0))
        for i, wx in enumerate((-4.0, -1.6, 2.6, 4.6)):
            toy.box(f"window{i}", (1.2, 0.1, 1.3), (hx + wx, hy - 3.02, 2.5), mat=m["window"], bevel=0.02)
            toy.box(f"wframe{i}", (1.4, 0.08, 1.5), (hx + wx, hy - 2.99, 2.5), mat=m["white"], bevel=0.02)
        toy.box("door", (1.1, 0.1, 2.2), (hx + 0.5, hy - 3.02, 1.1),
                mat=toy.material("door_wood", toy.srgb("#6B4A30"), roughness=0.5), bevel=0.03)
        trim = toy.material("trim_grey", toy.srgb("#6C6F73"), roughness=0.5)
        for i, wx in enumerate((-4.0, -1.6, 2.6, 4.6)):
            toy.box(f"sill{i}", (1.55, 0.22, 0.07), (hx + wx, hy - 3.1, 1.78), mat=trim, bevel=0.01)
            toy.box(f"mullion{i}", (0.05, 0.06, 1.3), (hx + wx, hy - 3.08, 2.5), mat=m["white"], bevel=0)
        toy.box("gutter", (11.8, 0.16, 0.12), (hx, hy - 3.55, 4.32), mat=trim, bevel=0.02)
        toy.box("downpipe", (0.09, 0.09, 4.2), (hx + 5.6, hy - 3.5, 2.2), mat=trim, bevel=0.01)
        toy.box("chimney", (0.8, 0.8, 1.8), (hx + 3.2, hy + 1.0, 5.8),
                mat=toy.noise_material("brick", toy.srgb("#8E4A34"), toy.srgb("#A85C40"), scale=14, bump=0.4),
                bevel=0.02)
        toy.box("plinth", (11.1, 6.1, 0.35), (hx, hy, 0.17), mat=trim, bevel=0.01)
        # Wooden fence along the back of the yard.
        for i in range(60):
            x = -15 + i * 0.5
            toy.box(f"picket{i}", (0.42, 0.06, 1.6), (x, 9.0, 0.8), mat=m["wood"], bevel=0.01)
        for z in (0.45, 1.25):
            toy.box(f"rail{z}", (30, 0.08, 0.1), (0, 9.06, z), mat=m["wood"], bevel=0)
        self._tree((-5.2, 6.0), 1.25)
        self._tree((6.2, 7.2), 1.0)
        self._tree((-9.0, 10.5), 0.9)

    def _tree(self, xy, s):
        """Tapered trunk, forked branches, and a lumpy canopy (displaced icospheres) that sways."""
        x, y = xy
        rnd = self.rnd
        bpy.ops.mesh.primitive_cone_add(radius1=0.2 * s, radius2=0.1 * s, depth=2.8 * s, vertices=14,
                                        location=(x, y, 1.4 * s))
        trunk = bpy.context.active_object
        trunk.name = f"trunk{x}"
        toy._finish(trunk, self.m["bark"], subdiv=1)
        sway = toy.empty(f"canopy{x}", (x, y, 2.6 * s))
        toy.add_noise(sway, "rotation_euler", 0, strength=0.015, scale=70, phase=x * 3)
        toy.add_noise(sway, "rotation_euler", 1, strength=0.015, scale=90, phase=x * 5)
        for k in range(4):                                 # forked main branches
            a = R(90 * k + rnd.uniform(-20, 20))
            br = toy.cylinder(f"branch{x}_{k}", 0.06 * s, 1.3 * s, (0, 0, 0), mat=self.m["bark"], vertices=10)
            br.parent = sway
            br.location = (math.cos(a) * 0.3 * s, math.sin(a) * 0.3 * s, 0.45 * s)
            br.rotation_euler = (R(40) * -math.sin(a), R(40) * math.cos(a), 0)
        tex = bpy.data.textures.get("foliage_lumps") or bpy.data.textures.new("foliage_lumps", "CLOUDS")
        tex.noise_scale = 0.35
        leaf2 = toy.noise_material("foliage_light", toy.srgb("#4F8A33"), toy.srgb("#79AE48"), scale=5, bump=0.6)
        for k in range(11):
            off = Vector((rnd.uniform(-1.3, 1.3), rnd.uniform(-0.9, 0.9), rnd.uniform(0.2, 1.4))) * s
            r = rnd.uniform(0.55, 0.85) * s
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=r, location=(0, 0, 0))
            blob = bpy.context.active_object
            blob.name = f"leaves{x}_{k}"
            d = blob.modifiers.new("lumps", "DISPLACE")
            d.texture = tex
            d.strength = 0.35 * r
            d.texture_coords = "GLOBAL"
            toy._finish(blob, self.m["leaf"] if k % 3 else leaf2, subdiv=0)
            blob.parent = sway
            blob.location = off
            blob.scale = (1.1, 1.0, 0.85)

    def _scatter_grass(self, name, x0, x1, y0, y1, density=None, z=0.0):
        import os
        density = density or float(os.getenv("CUT_GRASS", "650"))
        if not hasattr(self, "_tuft"):
            self._tuft = _grass_tuft()
        bpy.ops.mesh.primitive_plane_add(size=1, location=((x0 + x1) / 2, (y0 + y1) / 2, z + 0.002))
        em = bpy.context.active_object
        em.name = name
        em.scale = (x1 - x0, y1 - y0, 1)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        ps = em.modifiers.new(f"{name}_ps", "PARTICLE_SYSTEM").particle_system.settings
        ps.type = "HAIR"
        ps.count = int((x1 - x0) * (y1 - y0) * density)
        ps.hair_length = 1.0
        ps.render_type = "OBJECT"
        ps.instance_object = self._tuft
        ps.particle_size = 1.0
        ps.size_random = 0.6
        ps.use_rotations = True
        ps.rotation_mode = "NOR"
        ps.phase_factor_random = 2.0
        ps.use_advanced_hair = True
        if hasattr(em, "show_instancer_for_render"):
            em.show_instancer_for_render = False
        em.particle_systems[0].seed = len(name) * 11
        return em

    def _grass(self):
        """Real 3D grass on every lawn surface, right up to the cut edge (blades overhang it)."""
        hl, b = self.hl, self.back
        self._scatter_grass("grass_back", -11, 11, b, 8.8)
        self._scatter_grass("grass_west", -11, -hl, CUT + 0.01, b)
        self._scatter_grass("grass_east", hl, 11, CUT + 0.01, b)
        n = len(self.columns)
        for i, col in enumerate(self.columns):
            x0 = col["x"] - POOL_L / n / 2
            col["tufts"] = self._scatter_grass(f"grass_col{i}", x0, x0 + POOL_L / n, CUT + 0.01, b)

    def _stones(self, n=70):
        """Stones embedded in the cut face (rock and sand layers), outside the pool's hole."""
        rnd = random.Random(31)
        placed = 0
        while placed < n:
            x = rnd.uniform(-9, 9)
            z = rnd.uniform(-7.5, -0.6)
            if abs(x) < self.hl + 0.3 and z > -HOLE - 0.3:
                continue
            r = rnd.uniform(0.04, 0.16) * (1.6 if z < -3.2 else 1.0)
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=r, location=(x, CUT + r * 0.35, z))
            st = bpy.context.active_object
            st.name = f"stone{placed}"
            st.scale = (rnd.uniform(0.8, 1.4), 1.0, rnd.uniform(0.55, 0.9))
            st.rotation_euler = (0, rnd.uniform(0, 3.1), 0)
            toy._finish(st, self.m["stone"], subdiv=1)
            placed += 1

    def _clouds(self):
        mat = toy.material("cloud_soft", (1, 1, 1), roughness=0.95)
        tex = bpy.data.textures.new("cloud_puff", "CLOUDS")
        tex.noise_scale = 0.8
        rnd = random.Random(12)
        for i in range(7):
            root = toy.empty(f"cloud{i}", (rnd.uniform(-40, 40), rnd.uniform(45, 70), rnd.uniform(14, 24)))
            for k in range(5):
                bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=rnd.uniform(2.2, 3.6), location=(0, 0, 0))
                puff = bpy.context.active_object
                puff.name = f"cloud{i}_{k}"
                d = puff.modifiers.new("puff", "DISPLACE")
                d.texture = tex
                d.strength = 0.9
                toy._finish(puff, mat, subdiv=0)
                puff.parent = root
                puff.location = (rnd.uniform(-4, 4), rnd.uniform(-1, 1), rnd.uniform(-0.6, 0.8))
                puff.scale = (1.4, 1.0, 0.65)
                puff.visible_shadow = False
            root.keyframe_insert("location", frame=1)
            root.location.x += 30
            root.keyframe_insert("location", frame=6000)
            toy.set_interpolation(root, "location", (1,), "LINEAR")
        self.cloud_mat = mat

    def ladder(self, start, x=1.9):
        """Stainless pool ladder on the back wall: two hand rails bent over the coping + treads."""
        st = self.m["steel_bright"]
        y_in = self.back - SHELL - PLASTER - 0.12
        parts = []
        for k, dx in enumerate((-0.25, 0.25)):
            parts.append(toy.cylinder(f"rail_in{k}", 0.022, 1.45, (x + dx, y_in, -0.1), mat=st))
            parts.append(toy.cylinder(f"rail_top{k}", 0.022, 0.42, (x + dx, y_in + 0.21, 0.62),
                                      rotation=(R(90), 0, 0), mat=st))
            parts.append(toy.cylinder(f"rail_out{k}", 0.022, 0.55, (x + dx, y_in + 0.42, 0.35), mat=st))
            parts.append(toy.sphere(f"rail_bend{k}", 0.022, (x + dx, y_in, 0.62), mat=st, subdiv=1))
            parts.append(toy.sphere(f"rail_bend_b{k}", 0.022, (x + dx, y_in + 0.42, 0.62), mat=st, subdiv=1))
        for j, z in enumerate((-0.35, -0.7, -1.05)):
            parts.append(toy.box(f"tread{j}", (0.5, 0.1, 0.03), (x, y_in + 0.02, z), mat=st, bevel=0.008))
        for p in parts:
            _appear(p, start, frames=8)
            toy.parent_keep(p, self.pool_root)
        return parts

    def rain(self, start, end, n=220, x=(-7, 7), y=(-2.5, 7), top=9.0, fall_frames=9, seed=5):
        """Rain streaks: each drop loops top → ground, shrinking to nothing at impact (no smear)."""
        rnd = random.Random(seed)
        mat = toy.material("rain_streak", (0.85, 0.9, 1.0), roughness=0.1, alpha=0.45)
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "BLENDED"
        tiny, full = Vector((0.01, 0.01, 0.01)), Vector((1, 1, 1))
        for i in range(n):
            dx, dy = rnd.uniform(*x), rnd.uniform(*y)
            drop = toy.cylinder(f"rain{i}", 0.006, 0.38, (0, 0, -60), mat=mat, vertices=6)
            drop.visible_shadow = False
            drop.rotation_euler = (0, R(8), 0)
            drop.location, drop.scale = (0, 0, -60), tiny
            drop.keyframe_insert("location", frame=start - 1)
            drop.keyframe_insert("scale", frame=start - 1)
            f = start + rnd.randint(0, fall_frames)
            while f < end:
                for t, z, sc in ((f, top, tiny), (f + 1, top - 0.6, full), (f + fall_frames - 1, 0.2, full),
                                 (f + fall_frames, 0.0, tiny)):
                    drop.location = (dx + (top - z) * 0.14, dy, z)
                    drop.scale = sc
                    drop.keyframe_insert("location", frame=t)
                    drop.keyframe_insert("scale", frame=t)
                f += fall_frames + 1
            drop.location, drop.scale = (0, 0, -60), tiny
            drop.keyframe_insert("location", frame=f + 1)
            drop.keyframe_insert("scale", frame=f + 1)
            for fc in toy.fcurves(drop):
                pts = fc.keyframe_points
                for k in range(len(pts) - 1):
                    pts[k].interpolation = "CONSTANT" if pts[k + 1].co.x - pts[k].co.x <= 1.01 else "LINEAR"
        events.add(start, "pour", duration=end - start, gain=0.5)

    # ------------------- pool layers (built in section) -------------------

    def caustics(self, frame, level):
        """Waterline for the plaster caustics (key alongside the water level)."""
        key_node_value(self.m["plaster"], "water_level", frame, level)

    def gravel(self, start, end):
        hl = self.hl
        g = _block("gravel_bed", -hl, hl, CUT, self.back, -HOLE, -HOLE + GRAVEL, self.m["gravel"])
        g.parent = None
        _hide(g, 0, True)
        _hide(g, start, False)
        L = POOL_L
        _key(g, start, scale=Vector((0.02, 1, 1)), location=Vector((hl - L * 0.01, g.location.y, g.location.z)))
        _key(g, end, scale=Vector((1, 1, 1)), location=Vector((0, g.location.y, g.location.z)))
        for f in range(start, end, 12):
            events.add(f, "dump", gain=0.3)
        return g

    def shell_pieces(self):
        """Concrete shell: floor + west/east/back walls, 20 cm thick, cut open at the front."""
        hl, c, b = self.hl, self.m["concrete"], self.back
        z0 = -HOLE + GRAVEL
        pieces = [
            _block("shell_floor", -hl, hl, CUT, b, z0, z0 + SHELL, c),
            _block("shell_west", -hl, -hl + SHELL, CUT, b - SHELL, z0 + SHELL, 0, c),
            _block("shell_east", hl - SHELL, hl, CUT, b - SHELL, z0 + SHELL, 0, c),
            _block("shell_back", -hl, hl, b - SHELL, b, z0 + SHELL, 0, c),
        ]
        for p in pieces:
            toy.parent_keep(p, self.pool_root)
        return pieces

    def shotcrete(self, start, end):
        pieces = self.shell_pieces()
        span = end - start
        for k, p in enumerate(pieces):
            f = start + int(span * k / len(pieces))
            _hide(p, 0, True)
            _hide(p, f, False)
            grow = Vector((1, 1, 0.05)) if p.name != "shell_floor" else Vector((0.05, 1, 1))
            _key(p, f, scale=grow)
            _key(p, f + max(8, span // len(pieces)), scale=Vector((1, 1, 1)))
        self.shell = pieces
        return pieces

    def rebar(self, start, end, spacing=0.25):
        """Steel grid in the hole. Bars along X sit ON the section plane (half of each bar shows
        in front of the cut face), so they stay visible inside the concrete afterwards."""
        hl, b = self.hl, self.back
        z_floor = -HOLE + GRAVEL + SHELL / 2
        st = self.m["steel"]
        bars = []
        nx = int((POOL_L - 0.3) / spacing) + 1
        xs = [-hl + 0.15 + i * (POOL_L - 0.3) / (nx - 1) for i in range(nx)]
        ny = int((POOL_HALF_W - 0.15) / spacing) + 1
        ys = [CUT + 0.02 + i * (POOL_HALF_W - 0.17) / max(1, ny - 1) for i in range(ny)]
        for i, y in enumerate(ys):                         # floor bars along X
            bars.append(toy.cylinder(f"rb_fx{i}", 0.016, POOL_L - 0.25, (0, y, z_floor), rotation=(0, R(90), 0),
                                     mat=st, vertices=8))
        for i, x in enumerate(xs):                         # floor bars along Y (their ends dot the cut)
            bars.append(toy.cylinder(f"rb_fy{i}", 0.016, POOL_HALF_W - 0.1, (x, CUT + (POOL_HALF_W - 0.1) / 2 - 0.01,
                                                                              z_floor + 0.035),
                                     rotation=(R(90), 0, 0), mat=st, vertices=8))
        zs = [z_floor + 0.2 + k * 0.3 for k in range(int((-z_floor - 0.3) / 0.3) + 1)]
        for k, z in enumerate(zs):                         # wall rings: back wall + side walls
            bars.append(toy.cylinder(f"rb_bk{k}", 0.016, POOL_L - 0.25, (0, b - SHELL / 2, z), rotation=(0, R(90), 0),
                                     mat=st, vertices=8))
            for side, x in (("w", -hl + SHELL / 2), ("e", hl - SHELL / 2)):
                bars.append(toy.cylinder(f"rb_{side}{k}", 0.016, POOL_HALF_W - 0.05,
                                         (x, CUT + (POOL_HALF_W - 0.05) / 2 - 0.01, z), rotation=(R(90), 0, 0),
                                         mat=st, vertices=8))
        for i, x in enumerate(xs[::2]):                    # back-wall verticals
            bars.append(toy.cylinder(f"rb_v{i}", 0.016, -z_floor - 0.1, (x, b - SHELL / 2, z_floor / 2), mat=st,
                                     vertices=8))
        for side, x in (("w", -hl + SHELL / 2), ("e", hl - SHELL / 2)):  # side-wall verticals on the cut
            bars.append(toy.cylinder(f"rb_sv{side}", 0.016, -z_floor - 0.1, (x, CUT, z_floor / 2), mat=st, vertices=8))
        span = max(1, end - start - 8)
        for k, bar in enumerate(bars):
            f = start + int(span * k / len(bars))
            _appear(bar, f, frames=6)
            toy.parent_keep(bar, self.pool_root)
            if k % 4 == 0:
                events.add(f, "clink", gain=0.5)
        self.bars = bars
        return bars

    def finish(self, start, end):
        """Plaster lining (visible thickness in section), waterline tiles, stone coping."""
        hl, b = self.hl, self.back
        p, t = self.m["plaster"], self.m["tile"]
        fl = FLOOR_TOP
        lining = [
            _block("plaster_floor", -hl + SHELL, hl - SHELL, CUT, b - SHELL, fl, fl + PLASTER, p),
            _block("plaster_west", -hl + SHELL, -hl + SHELL + PLASTER, CUT, b - SHELL, fl + PLASTER, -0.25, p),
            _block("plaster_east", hl - SHELL - PLASTER, hl - SHELL, CUT, b - SHELL, fl + PLASTER, -0.25, p),
            _block("plaster_back", -hl + SHELL + PLASTER, hl - SHELL - PLASTER, b - SHELL - PLASTER, b - SHELL,
                   fl + PLASTER, -0.25, p),
        ]
        tiles = [
            _block("tile_west", -hl + SHELL, -hl + SHELL + 0.035, CUT, b - SHELL, -0.25, -0.005, t),
            _block("tile_east", hl - SHELL - 0.035, hl - SHELL, CUT, b - SHELL, -0.25, -0.005, t),
            _block("tile_back", -hl + SHELL + 0.035, hl - SHELL - 0.035, b - SHELL - 0.035, b - SHELL, -0.25, -0.005, t),
        ]
        c = self.m["coping"]
        coping = [
            _block("coping_back", -hl - 0.15, hl + 0.15, b - SHELL - 0.05, b + 0.25, 0.0, 0.07, c, bevel=0.015),
            _block("coping_west", -hl - 0.15, -hl + SHELL + 0.05, CUT, b - SHELL - 0.05, 0.0, 0.07, c, bevel=0.015),
            _block("coping_east", hl - SHELL - 0.05, hl + 0.15, CUT, b - SHELL - 0.05, 0.0, 0.07, c, bevel=0.015),
        ]
        pieces = tiles + coping + lining
        span = max(1, end - start - 8)
        for k, piece in enumerate(pieces):
            f = start + int(span * k / len(pieces))
            _appear(piece, f, frames=8)
            toy.parent_keep(piece, self.pool_root)
            events.add(f, "tile", gain=0.5)
        return pieces

    def water(self, start, end, level=WATER_TOP):
        """Water volume inside the plaster, cut open at the front (blue section), rising."""
        hl, b = self.hl, self.back
        x0, x1 = -hl + SHELL + PLASTER, hl - SHELL - PLASTER
        y1 = b - SHELL - PLASTER
        z0 = FLOOR_TOP + PLASTER
        z0 += 0.003
        full_h = level - z0 - 0.015
        w = toy.box("water", (x1 - x0, y1 - CUT - 0.004, full_h), (0, (CUT + 0.004 + y1) / 2, z0 + full_h / 2),
                    mat=self.m["water"], bevel=0)
        toy.parent_keep(w, self.pool_root)
        _hide(w, 0, True)
        _hide(w, start, False)
        _key(w, start, scale=Vector((1, 1, 0.01)), location=Vector((0, w.location.y, z0 + 0.005)))
        _key(w, end, scale=Vector((1, 1, 1)), location=Vector((0, w.location.y, z0 + full_h / 2)))
        events.add(start, "pour", duration=end - start)
        # Wavy surface sheet riding on top of the volume (the volume stops 1.5 cm below it).
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=90, y_subdivisions=24, size=1, location=(0, 0, 0))
        surf = bpy.context.active_object
        surf.name = "water_surface"
        surf.scale = (x1 - x0, y1 - CUT - 0.004, 1)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        surf.data.materials.append(self.m["water"])
        surf.data.shade_smooth()
        tex = bpy.data.textures.new("pool_ripples", "CLOUDS")
        tex.noise_scale = 0.3
        drift = toy.empty("ripple_drift", (0, 0, 0))
        drift.keyframe_insert("location", frame=1)
        drift.location = (9, 5, 3.5)
        drift.keyframe_insert("location", frame=6000)
        toy.set_interpolation(drift, "location", (1,), "LINEAR")
        disp = surf.modifiers.new("ripples", "DISPLACE")
        disp.texture = tex
        disp.texture_coords = "OBJECT"
        disp.texture_coords_object = drift
        disp.strength = 0.03
        toy.parent_keep(surf, self.pool_root)
        _hide(surf, 0, True)
        _hide(surf, start, False)
        _key(surf, start, location=Vector((0, (CUT + 0.004 + y1) / 2, z0 + 0.02)))
        _key(surf, end, location=Vector((0, (CUT + 0.004 + y1) / 2, level)))
        self.caustics(start - 1, -50)                  # no caustics until there is water
        self.caustics(start, z0 + 0.02)
        self.caustics(end, level)
        self.water_obj, self.water_z0, self.water_full, self.water_surf = w, z0, full_h, surf
        return w

    def drain_water(self, start, end):
        w = self.water_obj
        _key(w, start, scale=Vector((1, 1, 1)), location=Vector((0, w.location.y, self.water_z0 + self.water_full / 2)))
        _key(w, end, scale=Vector((1, 1, 0.01)), location=Vector((0, w.location.y, self.water_z0 + 0.005)))
        _hide(w, end + 1, True)
        _hide(self.water_surf, end + 1, True)
        self.caustics(start, WATER_TOP)
        self.caustics(end, -50)

    def water_table(self, frame, z, interpolation=None):
        key_node_value(self.m["strata"], "water_table", frame, z, interpolation)

    # ------------------- pipes, valve, equipment (drawn in the section) -------------------

    def pipe(self, name, points, start, end, radius=0.055, flow_dir=1.0, pump_mat=None):
        """A clear pipe along an axis-aligned polyline in front of the cut face, filled with
        water whose stripes flow from points[0] → points[-1] once pumping (flow_on) starts."""
        y = CUT - radius - 0.01
        mats = getattr(self, "_flow_mats", None)
        if mats is None:
            mats = self._flow_mats = {1: flow_material("flow_pos", 1.0), -1: flow_material("flow_neg", -1.0)}
        segs = []
        pts = [Vector((p[0], y, p[1])) for p in points]
        for k in range(len(pts) - 1):
            a, b = pts[k], pts[k + 1]
            d = b - a
            length = d.length
            if length < 1e-4:
                continue
            mid = (a + b) / 2
            # Cylinder local Z → segment direction; flow stripes follow local +Z or -Z.
            if abs(d.x) > abs(d.z):
                rot, sign = (0, R(90), 0), (1 if d.x > 0 else -1)     # local Z → +X
            else:
                rot, sign = (0, 0, 0), (1 if d.z > 0 else -1)
            shell = toy.cylinder(f"{name}_pipe{k}", radius, length + radius * 2, mid, rotation=rot,
                                 mat=self.m["pipe"], vertices=20)
            fluid = toy.cylinder(f"{name}_fluid{k}", radius * 0.72, length + radius * 1.4, mid, rotation=rot,
                                 mat=mats[sign * int(flow_dir)], vertices=16)
            for o in (shell, fluid):
                _appear(o, start + int((end - start) * k / max(1, len(pts) - 1)), frames=6)
            segs += [shell, fluid]
            events.add(start + int((end - start) * k / max(1, len(pts) - 1)), "pop", gain=0.4)
        return segs

    def start_flow(self, frame, ramp=12):
        for mat in getattr(self, "_flow_mats", {}).values():
            key_node_value(mat, "flow_on", frame, 0.0)
            key_node_value(mat, "flow_on", frame + ramp, 1.0)

    def relief_valve(self, x, start):
        """Hydrostatic relief valve: a capped tube through the floor into the gravel."""
        y = CUT - 0.07
        brass = toy.material("valve_brass", toy.srgb("#C9A24A"), roughness=0.3, metallic=0.9)
        body = toy.cylinder("relief_valve", 0.06, SHELL + GRAVEL + 0.06, (x, y, -HOLE + (SHELL + GRAVEL) / 2 + 0.03),
                            mat=brass, bevel=0.01)
        toy.cylinder("relief_cap", 0.09, 0.025, (x, y, FLOOR_TOP + 0.02), mat=brass, bevel=0.008)
        cap = bpy.data.objects["relief_cap"]
        for o in (body, cap):
            _appear(o, start, frames=8)
            toy.parent_keep(o, self.pool_root)
        events.add(start, "pop", gain=0.5)
        self.valve_cap = cap
        return body, cap

    def equipment_pad(self, x=5.6):
        """Pump + sand filter on a concrete pad beside the pool (just behind the cut)."""
        conc = self.m["concrete"]
        blue = toy.material("pump_blue", toy.srgb("#2B6CB0"), roughness=0.35, coat=0.4)
        grey = toy.material("filter_grey", toy.srgb("#C9CDD2"), roughness=0.35, coat=0.3)
        pad = _block("equip_pad", x - 1.0, x + 1.0, CUT + 0.05, CUT + 1.1, 0.0, 0.12, conc, bevel=0.02)
        tank = toy.cylinder("filter_tank", 0.33, 0.95, (x + 0.45, CUT + 0.5, 0.6), mat=grey, bevel=0.05)
        toy.sphere("filter_dome", 0.33, (x + 0.45, CUT + 0.5, 1.07), scale=(1, 1, 0.45), mat=grey)
        pump = toy.cylinder("pump_motor", 0.18, 0.5, (x - 0.45, CUT + 0.45, 0.32), rotation=(0, R(90), 0), mat=blue,
                            bevel=0.03)
        self.pad_x = x
        return pad, tank, pump

    # ------------------- callouts (in the 3D scene) -------------------

    def label3d(self, text, at, start, end, size=0.22, tilt=-6, color="#FF7A1A", outline="#3A0A00"):
        """Callout label drawn in the section: bold orange text with a dark outline, slightly
        tilted, popping in at `start` and out at `end`. Emissive, so it reads in any light."""
        fill = toy.material(f"lbl_fill_{color}", toy.srgb(color), roughness=0.5)
        bsdf = fill.node_tree.nodes.get("Principled BSDF")
        toy._set(bsdf, "Emission Color", (*toy.srgb(color), 1))
        toy._set(bsdf, "Emission Strength", 1.2)
        dark = toy.material(f"lbl_line_{outline}", toy.srgb(outline), roughness=0.6)
        root = toy.empty(f"label_{text}", (at[0], CUT - 0.25, at[1]))
        root.rotation_euler = (R(90), R(tilt), 0)
        for nm, mat, off, dz in ((f"{text}_fill", fill, 0.0, 0.0), (f"{text}_line", dark, 0.018 * size / 0.22, -0.01)):
            cu = bpy.data.curves.new(nm, "FONT")
            cu.body = text
            cu.size = size
            cu.extrude = 0.004
            cu.offset = off
            cu.align_x, cu.align_y = "CENTER", "CENTER"
            bold = _bold_font()
            if bold:
                cu.font = bold
            ob = bpy.data.objects.new(nm, cu)
            bpy.context.scene.collection.objects.link(ob)
            ob.data.materials.append(mat)
            ob.parent = root
            ob.location = (0, 0, dz)                 # local Z = toward the camera after the 90° tilt
        _hide_tree_window(root, start, end)
        _pop(root, start, end)
        events.add(start, "pop", gain=0.35)
        return root

    def dimension(self, a, b, text, start, end, offset=0.0, size=0.16):
        """Measurement line between section points a=(x,z) and b=(x,z) with end ticks + label."""
        white = toy.material("dim_white", (1, 1, 1), roughness=0.5)
        bsdf = white.node_tree.nodes.get("Principled BSDF")
        toy._set(bsdf, "Emission Color", (1, 1, 1, 1))
        toy._set(bsdf, "Emission Strength", 1.0)
        a, b = Vector((a[0], CUT - 0.2, a[1])), Vector((b[0], CUT - 0.2, b[1]))
        d = b - a
        mid = (a + b) / 2
        root = toy.empty(f"dim_{text}", mid)
        horizontal = abs(d.x) > abs(d.z)
        line = toy.box(f"dim_line_{text}", (d.length, 0.012, 0.012) if horizontal else (0.012, 0.012, d.length),
                       (0, 0, 0), mat=white, bevel=0)
        line.parent = root
        for k, p in enumerate((a, b)):
            tick = toy.box(f"dim_tick_{text}{k}", (0.012, 0.012, 0.14) if horizontal else (0.14, 0.012, 0.012),
                           (0, 0, 0), mat=white, bevel=0)
            tick.parent = root
            tick.location = p - mid
        cu = bpy.data.curves.new(f"dim_txt_{text}", "FONT")
        cu.body = text
        cu.size = size
        cu.align_x, cu.align_y = "CENTER", "CENTER"
        bold = _bold_font()
        if bold:
            cu.font = bold
        txt = bpy.data.objects.new(f"dim_txt_{text}", cu)
        bpy.context.scene.collection.objects.link(txt)
        txt.data.materials.append(white)
        txt.parent = root
        txt.rotation_euler = (R(90), 0, 0)
        txt.location = (0, 0, size * 0.9) if horizontal else (size * 1.8, 0, 0)
        _hide_tree_window(root, start, end)
        _pop(root, start, end)
        return root

    def arrows(self, name, points, direction, start, end, color="#5EC8FF", size=0.18):
        """Little 3D arrows (cone + shaft) in the section, e.g. groundwater pushing up."""
        mat = toy.material(f"arrow_{color}", toy.srgb(color), roughness=0.4)
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        toy._set(bsdf, "Emission Color", (*toy.srgb(color), 1))
        toy._set(bsdf, "Emission Strength", 1.5)
        out = []
        for k, (x, z) in enumerate(points):
            root = toy.empty(f"{name}{k}", (x, CUT - 0.15, z))
            bpy.ops.mesh.primitive_cone_add(radius1=size * 0.5, depth=size * 0.7, vertices=16,
                                            location=(0, 0, size * 0.35 * direction))
            cone = bpy.context.active_object
            cone.name = f"{name}_head{k}"
            if direction < 0:
                cone.rotation_euler = (R(180), 0, 0)
            toy._finish(cone, mat, subdiv=0, parent=root)
            cone.location = (0, 0, size * 0.35 * direction)
            shaft = toy.cylinder(f"{name}_shaft{k}", size * 0.15, size * 0.8, (0, 0, -size * 0.3 * direction), mat=mat)
            shaft.parent = root
            shaft.location = (0, 0, -size * 0.3 * direction)
            # Bob along the arrow direction so it reads as a force.
            root.location.z = z - 0.06 * direction
            root.keyframe_insert("location", frame=start)
            for f in range(start, end, 16):
                root.location.z = z + (0.06 if (f - start) // 16 % 2 == 0 else -0.04) * direction
                root.keyframe_insert("location", frame=f + 8)
            _hide_tree_window(root, start + 2 * k, end)
            _pop(root, start + 2 * k, end)
            out.append(root)
        return out


def _grass_tuft():
    """One clump of 9 tapered, bent blades (instanced many thousands of times)."""
    import bmesh
    mesh = bpy.data.meshes.new("cut_tuft")
    bm = bmesh.new()
    rnd = random.Random(5)
    for _ in range(9):
        ang = rnd.uniform(0, 2 * math.pi)
        lean = rnd.uniform(0.15, 0.5)
        h = rnd.uniform(0.07, 0.15)
        w = 0.007
        dx, dy = math.cos(ang), math.sin(ang)
        px, py = -dy * w, dx * w
        base = Vector((rnd.uniform(-0.025, 0.025), rnd.uniform(-0.025, 0.025), 0))
        mid = base + Vector((dx * lean * h * 0.4, dy * lean * h * 0.4, h * 0.55))
        tip = base + Vector((dx * lean * h, dy * lean * h, h))
        v = [bm.verts.new(base + Vector((px, py, 0))), bm.verts.new(base - Vector((px, py, 0))),
             bm.verts.new(mid - Vector((px, py, 0)) * 0.7), bm.verts.new(mid + Vector((px, py, 0)) * 0.7),
             bm.verts.new(tip)]
        bm.faces.new((v[0], v[1], v[2], v[3]))
        bm.faces.new((v[3], v[2], v[4]))
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("cut_tuft", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(toy.noise_material("blades", toy.srgb("#3E7E2B"), toy.srgb("#6AA543"), scale=40,
                                                 roughness=0.55, bump=0.0))
    obj.location = (0, 0, -100)
    return obj


_font = [None, False]


def _bold_font():
    if _font[1]:
        return _font[0]
    _font[1] = True
    import os
    for path in (r"C:\Windows\Fonts\ariblk.ttf", r"C:\Windows\Fonts\arialbd.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(path):
            _font[0] = bpy.data.fonts.load(path)
            break
    return _font[0]


def _no_shadow(root):
    """Callouts float in front of the section: they must not cast ghost shadows onto it."""
    stack = [root]
    while stack:
        o = stack.pop()
        if hasattr(o, "visible_shadow"):
            o.visible_shadow = False
        stack.extend(o.children)


def _hide_tree_window(root, start, end):
    _no_shadow(root)
    toy.hide_tree(root, 0, True)
    toy.hide_tree(root, start, False)
    toy.hide_tree(root, end, True)


def _pop(obj, start, end, frames=8):
    obj.scale = (0.01, 0.01, 0.01)
    obj.keyframe_insert("scale", frame=start)
    obj.scale = (1.12, 1.12, 1.12)
    obj.keyframe_insert("scale", frame=start + int(frames * 0.7))
    obj.scale = (1, 1, 1)
    obj.keyframe_insert("scale", frame=start + frames)
    obj.keyframe_insert("scale", frame=end - 5)
    obj.scale = (0.01, 0.01, 0.01)
    obj.keyframe_insert("scale", frame=end)
