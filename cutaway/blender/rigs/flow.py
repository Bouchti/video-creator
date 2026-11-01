"""
Fluid flow along a path (runs inside Blender): small glowing streaks that travel along a curve, positioned by
Geometry Nodes from one keyed input, the flow phase. A streak's place is fract(index / count + phase), so
every frame is a pure function of the phase (out-of-order renders, motion blur on subframes). Colour comes
from a ramp over the position along the path (cold blue -> hot orange in a loop), read by the material from
the "flow_u" attribute.

    f = flow("primary", points, count=400, spread=0.25, size=0.06, ramp=[(0, "#4fb6ff"), (0.5, "#ff7a2a")])
    f.set_phase(obj_phase)          # then keyframe with f.key(frame)
"""
from __future__ import annotations

import bpy

from .. import materials as M


def _curve(name, points, closed):
    cu = bpy.data.curves.new(name + "_path", "CURVE")
    cu.dimensions = "3D"
    sp = cu.splines.new("POLY")
    sp.points.add(len(points) - 1)
    for i, p in enumerate(points):
        sp.points[i].co = (*p, 1.0)
    sp.use_cyclic_u = closed
    ob = bpy.data.objects.new(name + "_path", cu)
    bpy.context.scene.collection.objects.link(ob)
    ob.hide_render = True
    ob.hide_viewport = True
    return ob


def _material(name, ramp, strength, gated=False):
    """Emission coloured along the path; a gated flow fades with the object's "flow_on" property (0..1),
    so a stream can start and stop (air through a valve only while it is open)."""
    mat = bpy.data.materials.new(name + "_mat")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_type = "GEOMETRY"
    attr.attribute_name = "flow_u"
    cr = nt.nodes.new("ShaderNodeValToRGB")
    els = cr.color_ramp.elements
    els[0].position, els[0].color = ramp[0][0], M.hex_rgb(ramp[0][1])
    els[1].position, els[1].color = ramp[-1][0], M.hex_rgb(ramp[-1][1])
    for pos, col in ramp[1:-1]:
        e = els.new(pos)
        e.color = M.hex_rgb(col)
    nt.links.new(attr.outputs["Fac"], cr.inputs["Fac"])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    nt.links.new(cr.outputs["Color"], em.inputs["Color"])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    if gated:
        on = nt.nodes.new("ShaderNodeAttribute")
        on.attribute_type = "OBJECT"
        on.attribute_name = "flow_on"
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(on.outputs["Fac"], mix.inputs["Fac"])
        nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
        nt.links.new(em.outputs["Emission"], mix.inputs[2])
        nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "BLENDED"
    else:
        nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return mat


class Flow:
    def __init__(self, name, points, count=300, spread=0.1, size=0.03, stretch=3.0, closed=True,
                 ramp=((0.0, "#4fb6ff"), (1.0, "#4fb6ff")), strength=6.0, col=None, seed=1, gated=False):
        self.path = _curve(name, points, closed)
        mat = _material(name, ramp, strength, gated)
        ng = bpy.data.node_groups.new(name + "_gn", "GeometryNodeTree")
        it = ng.interface
        it.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        s_phase = it.new_socket("Phase", in_out="INPUT", socket_type="NodeSocketFloat")
        s_lo = it.new_socket("Clip Min", in_out="INPUT", socket_type="NodeSocketVector")
        s_hi = it.new_socket("Clip Max", in_out="INPUT", socket_type="NodeSocketVector")
        it.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
        N = ng.nodes
        L = ng.links
        gin, gout = N.new("NodeGroupInput"), N.new("NodeGroupOutput")
        pts = N.new("GeometryNodePoints")
        pts.inputs["Count"].default_value = count
        idx = N.new("GeometryNodeInputIndex")
        div = N.new("ShaderNodeMath")
        div.operation = "DIVIDE"
        div.inputs[1].default_value = float(count)
        L.new(idx.outputs[0], div.inputs[0])
        jit = N.new("FunctionNodeRandomValue")
        jit.data_type = "FLOAT"
        M.sock(jit, "Min").default_value = 0.0
        M.sock(jit, "Max").default_value = 0.6 / count
        M.sock(jit, "Seed").default_value = seed
        add = N.new("ShaderNodeMath")
        add.operation = "ADD"
        L.new(div.outputs[0], add.inputs[0])
        L.new(M.sock(jit, "Value", True), add.inputs[1])
        add2 = N.new("ShaderNodeMath")
        add2.operation = "ADD"
        L.new(add.outputs[0], add2.inputs[0])
        L.new(gin.outputs[s_phase.identifier], add2.inputs[1])
        fr = N.new("ShaderNodeMath")
        fr.operation = "FRACT"
        L.new(add2.outputs[0], fr.inputs[0])
        info = N.new("GeometryNodeObjectInfo")
        info.transform_space = "RELATIVE"
        info.inputs["Object"].default_value = self.path
        smp = N.new("GeometryNodeSampleCurve")
        smp.mode = "FACTOR"
        smp.use_all_curves = False
        L.new(info.outputs["Geometry"], smp.inputs["Curves"])
        L.new(fr.outputs[0], smp.inputs["Factor"])
        off = N.new("FunctionNodeRandomValue")
        off.data_type = "FLOAT_VECTOR"
        M.sock(off, "Min").default_value = (-spread, -spread, -spread)
        M.sock(off, "Max").default_value = (spread, spread, spread)
        M.sock(off, "Seed").default_value = seed + 7
        pos = N.new("ShaderNodeVectorMath")
        pos.operation = "ADD"
        L.new(smp.outputs["Position"], pos.inputs[0])
        L.new(M.sock(off, "Value", True), pos.inputs[1])
        setp = N.new("GeometryNodeSetPosition")
        L.new(pts.outputs["Points"], setp.inputs["Geometry"])
        L.new(pos.outputs[0], setp.inputs["Position"])
        store = N.new("GeometryNodeStoreNamedAttribute")
        store.data_type = "FLOAT"
        store.domain = "INSTANCE"
        store.inputs["Name"].default_value = "flow_u"
        align = N.new("FunctionNodeAlignRotationToVector")
        align.axis = "Z"
        L.new(smp.outputs["Tangent"], align.inputs["Vector"])
        sph = N.new("GeometryNodeMeshUVSphere")
        sph.inputs["Segments"].default_value = 8
        sph.inputs["Rings"].default_value = 5
        sph.inputs["Radius"].default_value = size
        tr = N.new("GeometryNodeTransform")
        tr.inputs["Scale"].default_value = (1.0, 1.0, stretch)
        L.new(sph.outputs["Mesh"], tr.inputs["Geometry"])
        # streak points inside the clip box (a section cutter) are removed: no air floating where metal was cut
        P_ = N.new("GeometryNodeInputPosition")
        sp, slo, shi = (N.new("ShaderNodeSeparateXYZ") for _ in range(3))
        L.new(P_.outputs[0], sp.inputs[0])
        L.new(gin.outputs[s_lo.identifier], slo.inputs[0])
        L.new(gin.outputs[s_hi.identifier], shi.inputs[0])
        inside = None
        for ax in ("X", "Y", "Z"):
            for bound, op in ((slo, "GREATER_THAN"), (shi, "LESS_THAN")):
                cmp = N.new("FunctionNodeCompare")
                cmp.data_type = "FLOAT"
                cmp.operation = op
                L.new(sp.outputs[ax], cmp.inputs[0])
                L.new(bound.outputs[ax], cmp.inputs[1])
                if inside is None:
                    inside = cmp.outputs[0]
                else:
                    a = N.new("FunctionNodeBooleanMath")
                    a.operation = "AND"
                    L.new(inside, a.inputs[0])
                    L.new(cmp.outputs[0], a.inputs[1])
                    inside = a.outputs[0]
        dele = N.new("GeometryNodeDeleteGeometry")
        dele.domain = "POINT"
        L.new(setp.outputs["Geometry"], dele.inputs["Geometry"])
        L.new(inside, dele.inputs["Selection"])
        inst = N.new("GeometryNodeInstanceOnPoints")
        L.new(dele.outputs["Geometry"], inst.inputs["Points"])
        L.new(tr.outputs["Geometry"], inst.inputs["Instance"])
        L.new(align.outputs["Rotation"], inst.inputs["Rotation"])
        L.new(inst.outputs["Instances"], store.inputs["Geometry"])
        L.new(fr.outputs[0], store.inputs["Value"])
        real = N.new("GeometryNodeRealizeInstances")
        L.new(store.outputs["Geometry"], real.inputs["Geometry"])
        setm = N.new("GeometryNodeSetMaterial")
        setm.inputs["Material"].default_value = mat
        L.new(real.outputs["Geometry"], setm.inputs["Geometry"])
        L.new(setm.outputs["Geometry"], gout.inputs[0])
        me = bpy.data.meshes.new(name)
        self.obj = bpy.data.objects.new(name, me)
        (col or bpy.context.scene.collection).objects.link(self.obj)
        m = self.obj.modifiers.new("flow", "NODES")
        m.node_group = ng
        self.socket = s_phase.identifier
        self.clip_sockets = (s_lo.identifier, s_hi.identifier)
        self.clip((1e6, 1e6, 1e6), (1e6, 1e6, 1e6))
        self.obj["no_occlude"] = 1
        self.obj["flow_socket"] = self.socket
        if gated:
            self.obj["flow_on"] = 1.0

    def set_phase(self, value: float):
        # Blender 5.x: node-modifier inputs live at modifier.properties.inputs.<identifier>.value
        getattr(self.obj.modifiers["flow"].properties.inputs, self.socket).value = value

    def clip(self, lo, hi):
        """Hide the streak points inside the box lo..hi (world space; the flow object sits at the origin)."""
        ins = self.obj.modifiers["flow"].properties.inputs
        getattr(ins, self.clip_sockets[0]).value = tuple(lo)
        getattr(ins, self.clip_sockets[1]).value = tuple(hi)

    def key(self, frame: int):
        self.obj.keyframe_insert(phase_path(self.socket), frame=frame)


def phase_path(socket: str) -> str:
    return f'modifiers["flow"].properties.inputs.{socket}.value'
