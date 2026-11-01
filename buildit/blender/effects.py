"""
Effects for Build-It shots (runs inside Blender): glowing particle clouds that fill a volume, streams along a
path (cutaway's Flow rig), a warm flash. Everything is driven by keyable inputs, so frames depend on time only.

    c = Cloud("air", radius=0.18, z0=0.08, z1=0.68, count=600, color="#fff2c8")
    c.set(fill=0.4, time=t)                 # 40 % of the dots visible, drifting with time
"""
from __future__ import annotations

import math

import bpy

from cutaway.blender.materials import sock
from cutaway.blender.rigs.flow import Flow  # noqa: F401  (re-exported: streams along a path)

from . import materials as M


class Cloud:
    """Dots spread through a cylinder (radius, z0..z1), drifting with 3D noise over time; the first
    `fill` fraction of them is visible, so a container fills up dot by dot. `squeeze` compresses the cloud
    toward z0 (compression)."""

    def __init__(self, name, radius, z0, z1, count=500, size=0.006, color="#ffd36a", strength=6.0, seed=3,
                 drift=0.02):
        ng = bpy.data.node_groups.new(name + "_gn", "GeometryNodeTree")
        it = ng.interface
        it.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        s_fill = it.new_socket("Fill", in_out="INPUT", socket_type="NodeSocketFloat")
        s_time = it.new_socket("Time", in_out="INPUT", socket_type="NodeSocketFloat")
        s_top = it.new_socket("Top", in_out="INPUT", socket_type="NodeSocketFloat")
        it.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
        N, L = ng.nodes, ng.links
        gin, gout = N.new("NodeGroupInput"), N.new("NodeGroupOutput")

        def math_(op, a, b=None):
            m = N.new("ShaderNodeMath")
            m.operation = op
            for k, v in enumerate((a, b)):
                if v is None:
                    continue
                if isinstance(v, (int, float)):
                    m.inputs[k].default_value = v
                else:
                    L.new(v, m.inputs[k])
            return m.outputs[0]

        pts = N.new("GeometryNodePoints")
        pts.inputs["Count"].default_value = count
        rnd = N.new("FunctionNodeRandomValue")
        rnd.data_type = "FLOAT_VECTOR"
        sock(rnd, "Min").default_value = (0, 0, 0)
        sock(rnd, "Max").default_value = (1, 1, 1)
        sock(rnd, "Seed").default_value = seed
        sep = N.new("ShaderNodeSeparateXYZ")
        L.new(sock(rnd, "Value", True), sep.inputs[0])
        rr = math_("MULTIPLY", math_("SQRT", sep.outputs["X"]), radius)
        ang = math_("MULTIPLY", sep.outputs["Y"], math.tau)
        x = math_("MULTIPLY", rr, math_("COSINE", ang))
        y = math_("MULTIPLY", rr, math_("SINE", ang))
        # height: z0 .. Top (Top < z1 squeezes the cloud)
        span = math_("SUBTRACT", gin.outputs[s_top.identifier], z0)
        z = math_("ADD", math_("MULTIPLY", sep.outputs["Z"], span), z0)
        comb = N.new("ShaderNodeCombineXYZ")
        L.new(x, comb.inputs["X"])
        L.new(y, comb.inputs["Y"])
        L.new(z, comb.inputs["Z"])
        # drift: 4D noise of the rest position and time
        nz = N.new("ShaderNodeTexNoise")
        nz.noise_dimensions = "4D"
        nz.inputs["Scale"].default_value = 6.0
        L.new(comb.outputs[0], nz.inputs["Vector"])
        L.new(gin.outputs[s_time.identifier], nz.inputs["W"])
        cen = N.new("ShaderNodeVectorMath")
        cen.operation = "SUBTRACT"
        L.new(nz.outputs["Color"], cen.inputs[0])
        cen.inputs[1].default_value = (0.5, 0.5, 0.5)
        amp = N.new("ShaderNodeVectorMath")
        amp.operation = "SCALE"
        L.new(cen.outputs[0], amp.inputs[0])
        amp.inputs["Scale"].default_value = drift * 2
        pos = N.new("ShaderNodeVectorMath")
        pos.operation = "ADD"
        L.new(comb.outputs[0], pos.inputs[0])
        L.new(amp.outputs[0], pos.inputs[1])
        setp = N.new("GeometryNodeSetPosition")
        L.new(pts.outputs["Points"], setp.inputs["Geometry"])
        L.new(pos.outputs[0], setp.inputs["Position"])
        # keep the first Fill * count points
        idx = N.new("GeometryNodeInputIndex")
        frac = math_("DIVIDE", idx.outputs[0], float(count))
        cmp = N.new("FunctionNodeCompare")
        cmp.data_type = "FLOAT"
        cmp.operation = "GREATER_EQUAL"
        L.new(frac, cmp.inputs[0])
        L.new(gin.outputs[s_fill.identifier], cmp.inputs[1])
        dele = N.new("GeometryNodeDeleteGeometry")
        dele.domain = "POINT"
        L.new(setp.outputs["Geometry"], dele.inputs["Geometry"])
        L.new(cmp.outputs[0], dele.inputs["Selection"])
        sph = N.new("GeometryNodeMeshIcoSphere")
        sph.inputs["Radius"].default_value = size
        sph.inputs["Subdivisions"].default_value = 1
        inst = N.new("GeometryNodeInstanceOnPoints")
        L.new(dele.outputs["Geometry"], inst.inputs["Points"])
        L.new(sph.outputs["Mesh"], inst.inputs["Instance"])
        sc_r = N.new("FunctionNodeRandomValue")
        sc_r.data_type = "FLOAT"
        sock(sc_r, "Min").default_value = 0.5
        sock(sc_r, "Max").default_value = 1.3
        sock(sc_r, "Seed").default_value = seed + 5
        L.new(sock(sc_r, "Value", True), inst.inputs["Scale"])
        real = N.new("GeometryNodeRealizeInstances")
        L.new(inst.outputs["Instances"], real.inputs["Geometry"])
        setm = N.new("GeometryNodeSetMaterial")
        setm.inputs["Material"].default_value = M.particle(color, strength)
        L.new(real.outputs["Geometry"], setm.inputs["Geometry"])
        L.new(setm.outputs["Geometry"], gout.inputs[0])
        me = bpy.data.meshes.new(name)
        self.obj = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(self.obj)
        mod = self.obj.modifiers.new("cloud", "NODES")
        mod.node_group = ng
        self.ids = {"fill": s_fill.identifier, "time": s_time.identifier, "top": s_top.identifier}
        self.obj["gn_mod"] = "cloud"
        self.obj["gn_inputs"] = ",".join(self.ids.values())
        self.obj["no_occlude"] = 1
        self.obj.visible_shadow = False
        self.z1 = z1
        self.set(fill=0.0, time=0.0, top=z1)

    def set(self, fill=None, time=None, top=None):
        ins = self.obj.modifiers["cloud"].properties.inputs
        for k, v in (("fill", fill), ("time", time), ("top", top)):
            if v is not None:
                getattr(ins, self.ids[k]).value = float(v)


def flash(name, loc, radius=0.08, color="#ffd9a0"):
    """A warm explosion flash: an emissive ball plus a point light, both scaled by the "glow" property
    (set glow 0..1 per frame; the light follows it)."""
    from cutaway.blender import geo
    ball = geo.lathe(name, [(0, -radius)] + [(radius * math.sin(math.radians(a)), -radius * math.cos(math.radians(a)))
                                             for a in range(15, 180, 15)] + [(0, radius)], 32,
                     mat=M.glow(color, 30.0))
    ball.location = loc
    ball["glow"] = 0.0
    ball.visible_shadow = False
    ball["no_occlude"] = 1
    ld = bpy.data.lights.new(name + "_light", "POINT")
    ld.color = M.hex_rgb(color)[:3]
    ld.shadow_soft_size = radius
    ld.energy = 0.0
    lo = bpy.data.objects.new(name + "_light", ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.location = loc
    return ball, lo
