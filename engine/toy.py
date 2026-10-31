"""
Toy-diorama building blocks for the Blender engine (runs inside Blender's Python).

Everything in a video is built from these: soft rounded primitives, a small set
of art-directed materials, and a render/lighting setup that gives the
"premium collectible toy in a miniature world" look (glossy plastic, soft sun,
shallow depth of field).
"""
import math

import bpy
from mathutils import Vector

# ------------------- SCENE -------------------


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 30
    scene.render.resolution_x = 1080
    scene.render.resolution_y = 1920
    scene.render.resolution_percentage = 100
    for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    ee = scene.eevee
    for attr, value in (("taa_render_samples", 48), ("use_raytracing", True),
                        ("use_shadows", True), ("shadow_ray_count", 2),
                        ("use_gtao", True), ("fast_gi_method", "GLOBAL_ILLUMINATION")):
        if hasattr(ee, attr):
            try:
                setattr(ee, attr, value)
            except (TypeError, ValueError):
                pass
    # Motion blur: the single biggest "smoothness" win at 30 fps.
    if hasattr(scene.render, "use_motion_blur"):
        scene.render.use_motion_blur = True
        scene.render.motion_blur_shutter = 0.5
        # Shutter opens ON the frame: a centred shutter samples the previous frame too, so every
        # hard cut / teleport (camera switch, character cut_place, particle respawn) smears.
        if hasattr(scene.render, "motion_blur_position"):
            scene.render.motion_blur_position = "START"
    vs = scene.view_settings
    # "Standard" keeps art-directed cartoon colours saturated (AgX desaturates them).
    vs.view_transform = "Standard"
    vs.look = "None"
    vs.exposure = -0.2
    return scene


def setup_world(sun_elevation_deg=38, sun_rotation_deg=200, strength=0.16):
    """Physically based sky (multiple scattering) — bright, saturated daylight."""
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    if hasattr(world, "use_nodes"):
        world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    sky = nt.nodes.new("ShaderNodeTexSky")
    for kind in ("MULTIPLE_SCATTERING", "NISHITA", "HOSEK_WILKIE"):
        try:
            sky.sky_type = kind
            break
        except TypeError:
            continue
    for attr, value in (("sun_elevation", math.radians(sun_elevation_deg)),
                        ("sun_rotation", math.radians(sun_rotation_deg)),
                        ("sun_disc", False), ("air_density", 1.0), ("dust_density", 0.4)):
        if hasattr(sky, attr):
            setattr(sky, attr, value)
    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    nt.links.new(bg.outputs[0], out.inputs[0])


def add_sun(rotation_deg=(50, 10, 30), strength=3.6, color=(1.0, 0.93, 0.82), angle_deg=4):
    data = bpy.data.lights.new("Sun", "SUN")
    data.energy = strength
    data.color = color
    data.angle = math.radians(angle_deg)  # soft shadows
    obj = bpy.data.objects.new("Sun", data)
    obj.rotation_euler = [math.radians(a) for a in rotation_deg]
    bpy.context.scene.collection.objects.link(obj)
    return obj


def add_area(name, location, target, energy=400, size=4.0, color=(1, 1, 1)):
    """Soft area light aimed at `target` — fill and rim lights for character appeal."""
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    obj.location = location
    direction = Vector(target) - Vector(location)
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(obj)
    return obj


# ------------------- MATERIALS -------------------

_materials = {}


def _principled(mat):
    if hasattr(mat, "use_nodes"):
        mat.use_nodes = True
    return mat.node_tree.nodes.get("Principled BSDF")


def _set(bsdf, name, value):
    if name in bsdf.inputs:
        bsdf.inputs[name].default_value = value


def material(name, color, roughness=0.45, coat=0.0, subsurface=0.0, metallic=0.0,
             transmission=0.0, ior=1.45, alpha=1.0):
    """Cached Principled material. Colors are linear RGB tuples."""
    if name in _materials:
        return _materials[name]
    mat = bpy.data.materials.new(name)
    bsdf = _principled(mat)
    _set(bsdf, "Base Color", (*color, 1))
    _set(bsdf, "Roughness", roughness)
    _set(bsdf, "Metallic", metallic)
    _set(bsdf, "Coat Weight", coat)
    _set(bsdf, "Coat Roughness", 0.15)
    _set(bsdf, "Subsurface Weight", subsurface)
    _set(bsdf, "Subsurface Radius", Vector((1.0, 0.35, 0.2)))
    _set(bsdf, "Subsurface Scale", 0.05)
    _set(bsdf, "Transmission Weight", transmission)
    _set(bsdf, "IOR", ior)
    _set(bsdf, "Alpha", alpha)
    _materials[name] = mat
    return mat


def noise_material(name, color_a, color_b, scale=6.0, roughness=0.8, bump=0.25, detail=6.0):
    """Two-tone procedural surface (grass, dirt, concrete) with bump."""
    if name in _materials:
        return _materials[name]
    mat = bpy.data.materials.new(name)
    bsdf = _principled(mat)
    nt = mat.node_tree
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = scale
    tex.inputs["Detail"].default_value = detail
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*color_a, 1)
    ramp.color_ramp.elements[1].color = (*color_b, 1)
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[1].position = 0.7
    nt.links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bmp = nt.nodes.new("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = bump
    nt.links.new(tex.outputs["Fac"], bmp.inputs["Height"])
    nt.links.new(bmp.outputs["Normal"], bsdf.inputs["Normal"])
    _set(bsdf, "Roughness", roughness)
    _materials[name] = mat
    return mat


def srgb(hex_color: str) -> tuple:
    """'#FFB000' → linear RGB (Blender colors are linear)."""
    h = hex_color.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return tuple(out)


# ------------------- GEOMETRY -------------------


def _finish(obj, mat, subdiv=2, smooth=True, parent=None, collection=None):
    if mat is not None:
        obj.data.materials.append(mat)
    if smooth and hasattr(obj.data, "shade_smooth"):
        obj.data.shade_smooth()
    if subdiv:
        m = obj.modifiers.new("Subdiv", "SUBSURF")
        m.levels = 1
        m.render_levels = subdiv
    if parent is not None:
        obj.parent = parent
    if collection is not None:
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        collection.objects.link(obj)
    return obj


def sphere(name, radius, location=(0, 0, 0), scale=(1, 1, 1), mat=None, parent=None,
           subdiv=2, segments=24, rings=12):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=location, segments=segments,
                                         ring_count=rings)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    return _finish(obj, mat, subdiv=subdiv, parent=parent)


def box(name, size, location=(0, 0, 0), mat=None, parent=None, bevel=0.02, subdiv=0,
        rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        b = obj.modifiers.new("Bevel", "BEVEL")
        b.width = bevel
        b.segments = 3
    return _finish(obj, mat, subdiv=subdiv, parent=parent)


def cylinder(name, radius, depth, location=(0, 0, 0), rotation=(0, 0, 0), mat=None, parent=None,
             vertices=24, bevel=0.0, subdiv=0):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=location,
                                        rotation=rotation, vertices=vertices)
    obj = bpy.context.active_object
    obj.name = name
    if bevel:
        b = obj.modifiers.new("Bevel", "BEVEL")
        b.width = bevel
        b.segments = 3
    return _finish(obj, mat, subdiv=subdiv, parent=parent)


def capsule(name, radius, length, location=(0, 0, 0), rotation=(0, 0, 0), mat=None, parent=None):
    """Rounded limb: a cylinder with hemispherical caps (built as one smooth mesh)."""
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=(0, 0, 0), segments=20, ring_count=12)
    obj = bpy.context.active_object
    obj.name = name
    mesh = obj.data
    half = length / 2
    for v in mesh.vertices:
        v.co.z += half if v.co.z > 1e-6 else (-half if v.co.z < -1e-6 else 0)
    obj.location = location
    obj.rotation_euler = rotation
    return _finish(obj, mat, subdiv=1, parent=parent)


def empty(name, location=(0, 0, 0), parent=None, rotation=(0, 0, 0)):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_size = 0.1
    obj.location = location
    obj.rotation_euler = rotation
    bpy.context.scene.collection.objects.link(obj)
    if parent is not None:
        obj.parent = parent
    return obj


def _socket(sockets, name, kind):
    return next(s for s in sockets if s.name == name and s.type == kind and s.enabled)


def scatter(name, x0, x1, y0, y1, instance, density, size=1.0, size_random=0.6, z=0.002, seed=0, tilt=0.15):
    """Scatter `instance` (e.g. a grass tuft) over a rectangle and bake it into ONE static mesh.

    Particle hair re-generates every instance on every frame (CPU-bound renders); a realized
    Geometry Nodes scatter is evaluated once and applied, so the renderer just reuses the mesh."""
    bpy.ops.mesh.primitive_plane_add(size=1, location=((x0 + x1) / 2, (y0 + y1) / 2, z))
    em = bpy.context.active_object
    em.name = name
    em.scale = (x1 - x0, y1 - y0, 1)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    ng = bpy.data.node_groups.new(f"{name}_scatter", "GeometryNodeTree")
    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n, link = ng.nodes, ng.links.new
    gin, gout = n.new("NodeGroupInput"), n.new("NodeGroupOutput")
    dist = n.new("GeometryNodeDistributePointsOnFaces")
    dist.distribute_method = "RANDOM"
    dist.inputs["Density"].default_value = density
    dist.inputs["Seed"].default_value = seed
    info = n.new("GeometryNodeObjectInfo")
    info.inputs["Object"].default_value = instance
    rot = n.new("FunctionNodeRandomValue")
    rot.data_type = "FLOAT_VECTOR"
    _socket(rot.inputs, "Min", "VECTOR").default_value = (-tilt, -tilt, 0)
    _socket(rot.inputs, "Max", "VECTOR").default_value = (tilt, tilt, 2 * math.pi)
    _socket(rot.inputs, "Seed", "INT").default_value = seed + 1
    scl = n.new("FunctionNodeRandomValue")
    scl.data_type = "FLOAT"
    _socket(scl.inputs, "Min", "VALUE").default_value = size * (1 - size_random)
    _socket(scl.inputs, "Max", "VALUE").default_value = size
    _socket(scl.inputs, "Seed", "INT").default_value = seed + 2
    inst = n.new("GeometryNodeInstanceOnPoints")
    real = n.new("GeometryNodeRealizeInstances")
    link(gin.outputs[0], dist.inputs["Mesh"])
    link(dist.outputs["Points"], inst.inputs["Points"])
    link(info.outputs["Geometry"], inst.inputs["Instance"])
    link(_socket(rot.outputs, "Value", "VECTOR"), inst.inputs["Rotation"])
    link(_socket(scl.outputs, "Value", "VALUE"), inst.inputs["Scale"])
    link(inst.outputs["Instances"], real.inputs["Geometry"])
    link(real.outputs["Geometry"], gout.inputs[0])
    mod = em.modifiers.new("scatter", "NODES")
    mod.node_group = ng
    with bpy.context.temp_override(object=em, active_object=em, selected_objects=[em]):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    for mat in instance.data.materials:
        if mat and mat.name not in em.data.materials:
            em.data.materials.append(mat)
    em.visible_shadow = False            # millions of blades in every shadow map, for shadows nobody sees
    return em


def parent_keep(child, parent):
    """Parent without moving the child in world space."""
    mw = child.matrix_world.copy()
    child.parent = parent
    child.matrix_world = mw


def _first_visibility_key(o, frame):
    """No visibility key before `frame` yet: a HIDE here means 'until now it was on stage'. Without a
    visible key before it, the hide would hold backwards to the start of the film (a turbine or the
    kids invisible for half the video)."""
    keyed = [kp.co.x for fc in fcurves(o) if fc.data_path == "hide_render" for kp in fc.keyframe_points]
    return not any(x < frame for x in keyed)


def hide_tree(obj, frame, hidden: bool):
    """Keyframe render/viewport visibility for an object and all its children."""
    stack = [obj]
    while stack:
        o = stack.pop()
        if hidden and frame > 1 and _first_visibility_key(o, frame):
            o.hide_render = o.hide_viewport = False
            o.keyframe_insert("hide_render", frame=frame - 1)
            o.keyframe_insert("hide_viewport", frame=frame - 1)
        o.hide_render = hidden
        o.hide_viewport = hidden
        o.keyframe_insert("hide_render", frame=frame)
        o.keyframe_insert("hide_viewport", frame=frame)
        stack.extend(o.children)


# ------------------- ANIMATION CURVES -------------------


def fcurves(obj):
    """All F-curves of an object's action (Blender 5 layered actions, or legacy)."""
    ad = obj.animation_data
    if not ad or not ad.action:
        return []
    action = ad.action
    legacy = getattr(action, "fcurves", None)
    if legacy is not None:
        return list(legacy)
    out = []
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                out.extend(bag.fcurves)
    return out


def add_noise(obj, data_path: str, index: int, strength: float, scale: float, phase: float = 0.0):
    """Smooth random motion on one channel via an F-curve NOISE modifier (layers under keys)."""
    obj.keyframe_insert(data_path, index=index, frame=1)
    for fc in fcurves(obj):
        if fc.data_path == data_path and fc.array_index == index:
            mod = fc.modifiers.new("NOISE")
            mod.strength = strength
            mod.scale = scale
            mod.phase = phase
            mod.blend_type = "ADD"
            return mod


def world_matrix_at(obj, frame: int):
    """obj's WORLD matrix at `frame` from its animation curves and its parents' (no frame_set; constraints are
    ignored). value_at(root, "location") is relative to the parent: a close shot of Max riding a floating house
    aimed at his local coordinates and filmed the top of his hat from metres away."""
    from mathutils import Euler, Matrix
    loc = Vector(value_at(obj, "location", frame))
    rot = Euler(value_at(obj, "rotation_euler", frame), obj.rotation_mode if obj.rotation_mode in
                ("XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX") else "XYZ")
    local = Matrix.LocRotScale(loc, rot, Vector(value_at(obj, "scale", frame)))
    if obj.parent is None:
        return local
    return world_matrix_at(obj.parent, frame) @ obj.matrix_parent_inverse @ local


def world_location_at(obj, frame: int):
    """obj's world position at `frame` (world_matrix_at): where a camera must look to find it."""
    return world_matrix_at(obj, frame).to_translation()


def value_at(obj, data_path: str, frame: int):
    """The ANIMATED value of a vector property at `frame` (falls back to the current value).

    Never trust obj.<prop> while building animation: any scene.frame_set() (look-at aiming,
    particle origins...) makes Blender overwrite animated properties with their values at
    THAT frame, so "the current value" is silently some other moment of the film."""
    current = list(getattr(obj, data_path))
    for fc in fcurves(obj):
        if fc.data_path == data_path and fc.array_index < len(current):
            _normalize_curve(obj, fc)        # read the curve as it will RENDER (see normalize_interpolation)
            current[fc.array_index] = fc.evaluate(frame)
    return current


def key_hold(obj, data_path: str, frame: int, interpolation: str = None):
    """Key the property at `frame` with its animated value there (a hold / start-of-move key)."""
    setattr(obj, data_path, value_at(obj, data_path, frame))
    obj.keyframe_insert(data_path, frame=frame)
    if interpolation:
        set_interpolation(obj, data_path, (frame,), interpolation)


# Blender gives a newly inserted key the interpolation of the key before it, so ONE constant
# hold (a cut) silently turns every later key on that curve into a jump. Every deliberate
# interpolation is recorded here; normalize_interpolation() resets all other keys to Bezier.
_explicit = {}


def set_interpolation(obj, data_path: str, frames, interpolation: str):
    """Set the interpolation of the segment starting at each given keyframe."""
    targets = set(int(f) for f in frames)
    for f in targets:
        _explicit[(obj.as_pointer(), data_path, f)] = interpolation
    for fc in fcurves(obj):
        if fc.data_path != data_path:
            continue
        for kp in fc.keyframe_points:
            if int(round(kp.co.x)) in targets:
                kp.interpolation = interpolation


def set_key_interpolation(owner, fc, kp, interpolation: str):
    """Deliberately set one keyframe's interpolation (recorded, survives normalize_interpolation)."""
    _explicit[(owner.as_pointer(), fc.data_path, int(round(kp.co.x)))] = interpolation
    kp.interpolation = interpolation


def _normalize_curve(owner, fc):
    """normalize_interpolation() for one curve (so values sampled mid-build match the render)."""
    if "hide" in fc.data_path:
        return
    for kp in fc.keyframe_points:
        want = _explicit.get((owner.as_pointer(), fc.data_path, int(round(kp.co.x))), "BEZIER")
        if kp.interpolation != want:
            kp.interpolation = want


def normalize_interpolation():
    """Undo inherited interpolation: every key not set on purpose becomes Bezier (call once after
    the whole film is staged). Discrete channels (visibility) are left alone."""
    owners = list(bpy.data.objects) + list(bpy.data.cameras) + list(bpy.data.lights) + \
        [m.node_tree for m in bpy.data.materials if m.node_tree] + \
        [w.node_tree for w in bpy.data.worlds if w.node_tree]
    fixed = 0
    for owner in owners:
        for fc in fcurves(owner):
            if "hide" in fc.data_path:
                continue
            for kp in fc.keyframe_points:
                want = _explicit.get((owner.as_pointer(), fc.data_path, int(round(kp.co.x))), "BEZIER")
                if kp.interpolation != want:
                    kp.interpolation = want
                    fixed += 1
    return fixed
