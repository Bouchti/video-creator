"""
Shared Blender toolkit for director worlds (runs inside Blender's Python).

  look.setup()            Eevee 1080x1920, AgX, raytraced AO/GI, motion blur, HDRI sky
  material("Ground048")   ambientCG PBR material, box-projected in object space (no UVs needed)
  import_model(path)      .glb / .gltf / Poly Haven .blend under one parent empty
  tween(...)              keyframes with real easing (BACK overshoot, BOUNCE, ELASTIC, SINE)
  Camera                  one camera, shots solved from "what width of the world fills the frame"
  Anchors                 named points whose 2D screen positions are exported per frame
"""
import json
import math
import os
import random

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CC0 = os.path.join(ROOT, "assets", "cc0")
SENSOR = 36.0           # sensor fit VERTICAL: 36 mm spans the frame height
ASPECT = 9 / 16


# ------------------------------------------------------------------ scene + look

LOOKS = {   # name -> (view transform, look, exposure). Measured on the same frames (docs/REDESIGN.md section 9):
    # AgX desaturates and caps the brightest 2 % of a cartoon frame at 0.71 (it reads grey and faded);
    # Khronos PBR Neutral keeps material colours true: colourfulness 84 vs 50, highlights up to 0.9.
    "vivid": ("Khronos PBR Neutral", "None", 0.4),
    "standard": ("Standard", "Medium High Contrast", 0.0),
    "agx": ("AgX", "AgX - Punchy", 0.0),
}


def reset(fps=30, preview=False, look="vivid", motion_blur=False):
    """Render defaults chosen by measurement (docs/REDESIGN.md): Eevee's motion blur is sampled randomly per
    frame and makes fine textures sparkle, so it is OFF unless a world asks for it."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    r = scene.render
    r.fps = fps
    r.resolution_x, r.resolution_y = 1080, 1920
    r.resolution_percentage = 50 if preview else 100
    r.engine = "BLENDER_EEVEE"
    ee = scene.eevee
    for attr, value in (("taa_render_samples", 16 if preview else 64), ("use_raytracing", True),
                        ("use_shadows", True), ("shadow_ray_count", 2), ("shadow_step_count", 8),
                        ("use_gtao", True), ("gtao_distance", 0.6), ("fast_gi_method", "GLOBAL_ILLUMINATION"),
                        ("use_volumetric_shadows", True)):
        if hasattr(ee, attr):
            try:
                setattr(ee, attr, value)
            except (TypeError, ValueError):
                pass
    if hasattr(ee, "ray_tracing_options"):
        ee.ray_tracing_options.resolution_scale = "2" if preview else "1"
    r.use_motion_blur = motion_blur
    r.motion_blur_shutter = 0.45
    if hasattr(r, "motion_blur_position"):
        r.motion_blur_position = "START"     # a hard cut must not smear the previous shot
    vs = scene.view_settings
    vs.view_transform, vs.look, vs.exposure = LOOKS[look]
    r.film_transparent = False
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGB"
    r.image_settings.compression = 15
    return scene


def hdri_world(path, strength=1.0, rotation_deg=0.0, sky_tint=None):
    """Lighting + background from an HDRI. sky_tint multiplies only what the camera sees."""
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Rotation"].default_value[2] = math.radians(rotation_deg)
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(path, check_existing=True)
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(coord.outputs["Generated"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], env.inputs["Vector"])
    color = env.outputs["Color"]
    if sky_tint:
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        nt.links.new(color, mix.inputs["A"])
        mix.inputs["B"].default_value = (*sky_tint, 1.0)
        color = mix.outputs["Result"]
    nt.links.new(color, bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    return bg


def sun(rotation=(52, 0, 35), strength=3.5, color=(1.0, 0.95, 0.88), angle_deg=2.0):
    data = bpy.data.lights.new("Sun", "SUN")
    data.energy = strength
    data.color = color
    data.angle = math.radians(angle_deg)
    ob = bpy.data.objects.new("Sun", data)
    bpy.context.scene.collection.objects.link(ob)
    ob.rotation_euler = [math.radians(a) for a in rotation]
    return ob


def hdri(name_hint):
    """Path of a downloaded Poly Haven HDRI whose id contains name_hint."""
    folder = os.path.join(CC0, "polyhaven", "hdris")
    for d in sorted(os.listdir(folder)):
        if name_hint in d:
            files = [f for f in os.listdir(os.path.join(folder, d)) if f.endswith(".hdr")]
            if files:
                return os.path.join(folder, d, files[0])
    raise FileNotFoundError(name_hint)


# ------------------------------------------------------------------ materials

_mats = {}


def _img(path, non_color):
    img = bpy.data.images.load(path, check_existing=True)
    if non_color:
        img.colorspace_settings.name = "Non-Color"
    return img


def acg_maps(asset_id):
    folder = os.path.join(CC0, "ambientcg", asset_id)
    maps = {}
    for f in os.listdir(folder):
        for key in ("Color", "Roughness", "NormalGL", "AmbientOcclusion", "Displacement", "Metalness", "Opacity"):
            if f.endswith(f"_{key}.jpg") or f.endswith(f"_{key}.png"):
                maps[key] = os.path.join(folder, f)
    if "Color" not in maps:
        raise FileNotFoundError(f"ambientCG {asset_id}: no colour map")
    return maps


def tex_nodes(nt, asset_id, scale=1.0, blend=0.25, coord="Object"):
    """Box-projected ambientCG maps: returns dict of output sockets (Color, Roughness, Normal, AO, Height)."""
    maps = acg_maps(asset_id)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (scale, scale, scale)
    nt.links.new(tc.outputs[coord], mapping.inputs["Vector"])
    out = {}

    def image(key, non_color):
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = _img(maps[key], non_color)
        node.projection = "BOX"
        node.projection_blend = blend
        nt.links.new(mapping.outputs["Vector"], node.inputs["Vector"])
        return node

    out["Color"] = image("Color", False).outputs["Color"]
    if "Roughness" in maps:
        out["Roughness"] = image("Roughness", True).outputs["Color"]
    if "AmbientOcclusion" in maps:
        out["AO"] = image("AmbientOcclusion", True).outputs["Color"]
    if "Displacement" in maps:
        out["Height"] = image("Displacement", True).outputs["Color"]
    if "Metalness" in maps:
        out["Metallic"] = image("Metalness", True).outputs["Color"]
    if "NormalGL" in maps:
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = 1.0
        nt.links.new(image("NormalGL", True).outputs["Color"], nm.inputs["Color"])
        out["Normal"] = nm.outputs["Normal"]
    return out


def _bsdf(mat):
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    return nt, bsdf


def material(asset_id, scale=1.0, tint=None, rough=None, name=None, bump=None):
    """ambientCG PBR material. tint multiplies the colour (art direction without repainting)."""
    key = name or f"{asset_id}@{scale}@{tint}@{rough}"
    if key in _mats:
        return _mats[key]
    mat = bpy.data.materials.new(key)
    nt, bsdf = _bsdf(mat)
    t = tex_nodes(nt, asset_id, scale)
    color = t["Color"]
    if "AO" in t:
        ao = nt.nodes.new("ShaderNodeMix")
        ao.data_type = "RGBA"
        ao.blend_type = "MULTIPLY"
        ao.inputs["Factor"].default_value = 0.7
        nt.links.new(color, ao.inputs["A"])
        nt.links.new(t["AO"], ao.inputs["B"])
        color = ao.outputs["Result"]
    if tint:
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        nt.links.new(color, mix.inputs["A"])
        mix.inputs["B"].default_value = (*tint, 1.0)
        color = mix.outputs["Result"]
    nt.links.new(color, bsdf.inputs["Base Color"])
    if rough is not None:
        bsdf.inputs["Roughness"].default_value = rough
    elif "Roughness" in t:
        nt.links.new(t["Roughness"], bsdf.inputs["Roughness"])
    if "Metallic" in t:
        nt.links.new(t["Metallic"], bsdf.inputs["Metallic"])
    if "Normal" in t:
        nt.links.new(t["Normal"], bsdf.inputs["Normal"])
    _mats[key] = mat
    return mat


def flat(name, rgb, rough=0.45, metallic=0.0, emission=0.0, alpha=1.0, coat=0.0, transmission=0.0):
    if name in _mats:
        return _mats[name]
    mat = bpy.data.materials.new(name)
    nt, bsdf = _bsdf(mat)
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metallic
    if coat:
        bsdf.inputs["Coat Weight"].default_value = coat
    if transmission:
        bsdf.inputs["Transmission Weight"].default_value = transmission
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*rgb, 1)
        bsdf.inputs["Emission Strength"].default_value = emission
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "BLENDED"
    _mats[name] = mat
    return mat


def hexrgb(h):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb)


# ------------------------------------------------------------------ geometry

def link(ob, parent=None):
    bpy.context.scene.collection.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


def empty(name, loc=(0, 0, 0), parent=None):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_size = 0.2
    ob.location = loc
    return link(ob, parent)


def mesh_from_bm(name, bm, mat=None, parent=None, smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    if mat is not None:
        me.materials.append(mat)
    return link(ob, parent)


def box(name, x0, x1, y0, y1, z0, z1, mat=None, parent=None, bevel=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = x0 if v.co.x < 0 else x1
        v.co.y = y0 if v.co.y < 0 else y1
        v.co.z = z0 if v.co.z < 0 else z1
    ob = mesh_from_bm(name, bm, mat, parent)
    if bevel:
        mod = ob.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 3
        mod.limit_method = "ANGLE"
    return ob


def blob(name, radius, mat, loc=(0, 0, 0), squash=1.0, seed=0, parent=None, lumpy=0.12, subdiv=3):
    """Organic lump (sludge, grease, dirt chunks, the mascot body)."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=radius)
    rnd = random.Random(seed)
    phase = [rnd.uniform(0, 6.28) for _ in range(3)]
    for v in bm.verts:
        n = v.co.normalized()
        k = 1 + lumpy * (math.sin(n.x * 3 + phase[0]) * math.sin(n.y * 3 + phase[1]) * math.sin(n.z * 3 + phase[2]))
        v.co = v.co * k
        v.co.z *= squash
    ob = mesh_from_bm(name, bm, mat, parent, smooth=True)
    ob.location = loc
    return ob


def tube(name, pts, radius, mat=None, parent=None, resolution=16):
    """A pipe along points (bevelled curve converted to mesh)."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = max(2, resolution // 4)
    cu.use_fill_caps = True
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for p, c in zip(sp.points, pts):
        p.co = (*c, 1)
    ob = bpy.data.objects.new(name, cu)
    if mat is not None:
        cu.materials.append(mat)
    link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob)
    out = bpy.data.objects.new(name, me)
    for p in me.polygons:
        p.use_smooth = True
    return link(out, parent)


def section(ob, keep_positive_y=True, plane_y=0.0, fill=False):
    """Cut a mesh at the section plane (y = plane_y) and keep the part behind it: a cutaway."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    mw = ob.matrix_world
    inv = mw.inverted()
    co = inv @ Vector((0, plane_y, 0))
    no = (inv.to_3x3() @ Vector((0, 1, 0))).normalized()
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no, clear_inner=keep_positive_y,
                                 clear_outer=not keep_positive_y)
    if fill:
        edges = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
        if edges:
            bmesh.ops.holes_fill(bm, edges=edges)
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def boolean(target, cutter, op="DIFFERENCE"):
    mod = target.modifiers.new(f"bool_{cutter.name}", "BOOLEAN")
    mod.operation = op
    mod.object = cutter
    mod.solver = "EXACT"
    cutter.hide_render = True
    cutter.display_type = "WIRE"
    return mod


# ------------------------------------------------------------------ imported assets

def import_model(path, name, parent=None, scale=1.0):
    """Import a .glb/.gltf or a Poly Haven .blend; everything goes under one empty `name`."""
    before = set(bpy.data.objects)
    if path.lower().endswith((".glb", ".gltf")):
        bpy.ops.import_scene.gltf(filepath=path)
    elif path.lower().endswith(".blend"):
        with bpy.data.libraries.load(path, link=False) as (src, dst):
            dst.objects = list(src.objects)
        for ob in dst.objects:
            if ob is not None:
                bpy.context.scene.collection.objects.link(ob)
    else:
        raise ValueError(path)
    new = [o for o in bpy.data.objects if o not in before]
    root = empty(name, parent=parent)
    for ob in new:
        if ob.parent is None:
            ob.parent = root
    root.scale = (scale, scale, scale)
    return root


def kenney(kit, model):
    folder = os.path.join(CC0, "kenney")
    for d in os.listdir(folder):
        if kit in d:
            for dirpath, _dirs, names in os.walk(os.path.join(folder, d)):
                if f"{model}.glb" in names:
                    return os.path.join(dirpath, f"{model}.glb")
    raise FileNotFoundError(f"kenney {kit}/{model}")


def find_asset(sub, pattern):
    """First file under assets/cc0/<sub> whose name contains pattern (case-insensitive)."""
    for dirpath, _dirs, names in os.walk(os.path.join(CC0, sub)):
        for n in sorted(names):
            if pattern.lower() in n.lower() and n.lower().endswith((".glb", ".gltf", ".blend")):
                return os.path.join(dirpath, n)
    raise FileNotFoundError(f"{sub}/{pattern}")


# ------------------------------------------------------------------ animation

def fcurves(idblock):
    ad = idblock.animation_data
    if not ad or not ad.action:
        return []
    legacy = getattr(ad.action, "fcurves", None)
    if legacy is not None:
        return list(legacy)
    return [fc for layer in ad.action.layers for strip in layer.strips for bag in strip.channelbags
            for fc in bag.fcurves]


def _set_interp(idblock, path, frame, interp, easing="AUTO", back=1.70158):
    for fc in fcurves(idblock):
        if fc.data_path != path:
            continue
        for kp in fc.keyframe_points:
            if abs(kp.co.x - frame) < 0.5:
                kp.interpolation = interp
                kp.easing = easing
                if interp == "BACK":
                    kp.back = back


def key(ob, path, frame, value=None, interp="BEZIER", easing="AUTO", back=1.70158):
    if value is not None:
        _assign(ob, path, value)
    ob.keyframe_insert(path, frame=frame)
    _set_interp(ob, path, frame, interp, easing, back)


def _assign(ob, path, value):
    if "." in path or "[" in path:
        ob.path_resolve(path)  # validates
        exec(f"ob.{path} = value", {"ob": ob, "value": value})
    else:
        setattr(ob, path, value)


EASES = {   # name -> (interpolation, easing) applied to the FIRST key of a segment
    "smooth": ("SINE", "EASE_IN_OUT"),
    "out": ("CUBIC", "EASE_OUT"),
    "in": ("CUBIC", "EASE_IN"),
    "pop": ("BACK", "EASE_OUT"),        # overshoot then settle
    "bounce": ("BOUNCE", "EASE_OUT"),
    "elastic": ("ELASTIC", "EASE_OUT"),
    "linear": ("LINEAR", "AUTO"),
    "hold": ("CONSTANT", "AUTO"),
}


MIN_BOUNCY = 20   # frames: BOUNCE / ELASTIC pack several bounces into any span; shorter they jitter frame to frame


def tween(ob, path, f0, f1, a, b, ease="smooth", back=1.7):
    """Animate ob.path from a (at f0) to b (at f1) with a named ease. A bounce or elastic ease shorter than
    MIN_BOUNCY frames becomes one overshoot ("pop"): the ta-da hop flickered up-down-up on 3 frames."""
    if ease in ("bounce", "elastic") and f1 - f0 < MIN_BOUNCY:
        ease = "pop"
    interp, easing = EASES[ease]
    key(ob, path, f0, a, interp, easing, back)
    key(ob, path, f1, b, "BEZIER")


def visible(ob, frame, on, children=True):
    """Hard show/hide at a frame (render + viewport)."""
    for o in [ob] + (list(ob.children_recursive) if children else []):
        o.hide_render = not on
        o.hide_viewport = not on
        o.keyframe_insert("hide_render", frame=frame)
        o.keyframe_insert("hide_viewport", frame=frame)
        for fc in fcurves(o):
            if fc.data_path in ("hide_render", "hide_viewport"):
                for kp in fc.keyframe_points:
                    kp.interpolation = "CONSTANT"


def node_key(socket, frame, value, interp="BEZIER", easing="AUTO"):
    """Keyframe a shader node input (e.g. a water level) and set its interpolation."""
    socket.default_value = value
    socket.keyframe_insert("default_value", frame=frame)
    tree = socket.id_data
    path = socket.path_from_id("default_value")
    for fc in fcurves(tree):
        if fc.data_path == path:
            for kp in fc.keyframe_points:
                if abs(kp.co.x - frame) < 0.5:
                    kp.interpolation = interp
                    kp.easing = easing


# ------------------------------------------------------------------ camera

def tan_half():
    tv = SENSOR / 2.0
    return tv * ASPECT, tv   # multiplied by 1/lens


class Camera:
    """One camera. A shot is: look at `center`, with `width` metres of the world filling the frame
    width, from a yaw (0 = from the front, looking +Y) and a pitch (degrees above the horizon).
    Shots blend (glide) or cut; shake() adds impact."""

    def __init__(self, lens=35.0, fstop=5.6):
        data = bpy.data.cameras.new("Cam")
        data.lens = lens
        data.sensor_fit = "VERTICAL"
        data.sensor_height = SENSOR
        data.clip_start = 0.05
        data.clip_end = 600
        data.dof.use_dof = True
        data.dof.aperture_fstop = fstop
        self.data = data
        self.rig = empty("CamShake")
        self.cam = link(bpy.data.objects.new("Cam", data), self.rig)
        self.aim = empty("CamAim")
        con = self.cam.constraints.new("TRACK_TO")
        con.target = self.aim
        con.track_axis = "TRACK_NEGATIVE_Z"
        con.up_axis = "UP_Y"
        data.dof.focus_object = self.aim
        bpy.context.scene.camera = self.cam
        self.lens = lens
        self.shots, self.notes, self.last_f0 = [], [], 1

    def pose(self, center, width, yaw=0.0, pitch=12.0, lens=None):
        """(camera position, aim) so `width` metres around `center` span the frame width."""
        lens = lens or self.lens
        th = (SENSOR / 2.0) * ASPECT / lens
        dist = (width / 2.0) / th
        y, p = math.radians(yaw), math.radians(pitch)
        back = Vector((math.sin(y) * math.cos(p), -math.cos(y) * math.cos(p), math.sin(p)))
        return Vector(center) + back * dist, Vector(center)

    def _key(self, f, cam, aim, lens, interp, easing):
        self.cam.location = cam
        self.aim.location = aim
        self.data.lens = lens
        self.cam.keyframe_insert("location", frame=f)
        self.aim.keyframe_insert("location", frame=f)
        self.data.keyframe_insert("lens", frame=f)
        for idb, path in ((self.cam, "location"), (self.aim, "location"), (self.data, "lens")):
            _set_interp(idb, path, f, interp, easing)

    # Gentle camera, enforced here for every world (docs/REDESIGN.md section 8): without motion blur a fast
    # move strobes, and cuts between near-identical framings read as the picture "zooming" by itself.
    MAX_TRAVEL = 0.008     # aim travel per frame, as a share of the frame width
    MAX_ZOOM = 0.004       # |ln(width change)| per frame (~12 %/s)
    MAX_TURN = 0.35        # degrees of yaw / pitch per frame

    def _limit(self, a, b, frames):
        """Shorten the move a -> b until it respects the speed limits; returns the (possibly) new b."""
        ca, cb = Vector(a["center"]), Vector(b["center"])
        w = (a["width"] + b["width"]) / 2
        need = max((cb - ca).length / w / self.MAX_TRAVEL,
                   abs(math.log(b["width"] / a["width"])) / self.MAX_ZOOM,
                   abs(b.get("yaw", 0) - a.get("yaw", 0)) / self.MAX_TURN,
                   abs(b.get("pitch", 12) - a.get("pitch", 12)) / self.MAX_TURN) / max(1, frames)
        if need <= 1.0:
            return b
        k = 1.0 / need
        self.notes.append(f"move at frames {self.last_f0}+ shortened to {k:.0%}: too fast for a clean picture")
        out = dict(b)
        out["center"] = tuple(ca.lerp(cb, k))
        out["width"] = a["width"] * (b["width"] / a["width"]) ** k
        for key, default in (("yaw", 0.0), ("pitch", 12.0)):
            out[key] = a.get(key, default) + (b.get(key, default) - a.get(key, default)) * k
        return out

    @staticmethod
    def _similar(p, q):
        """Two framings a viewer would see as the same shot (a cut between them is a jump cut)."""
        w = max(p["width"], q["width"])
        return (max(p["width"], q["width"]) / min(p["width"], q["width"]) < 1.35
                and (Vector(p["center"]) - Vector(q["center"])).length < 0.3 * w
                and abs(p.get("yaw", 0) - q.get("yaw", 0)) < 12 and abs(p.get("pitch", 12) - q.get("pitch", 12)) < 8)

    def shot(self, f0, f1, a, b=None, cut=True, ease="smooth"):
        """a / b: dicts of pose() arguments for the start and end of the move.
        A cut to a framing similar to the previous one becomes a continuation (no jump cut); every move is
        speed-limited (shortened when needed)."""
        if not hasattr(self, "shots"):
            self.shots, self.notes = [], []
        self.last_f0 = f0
        b = dict(b or a)
        a = dict(a)
        prev = self.shots[-1] if self.shots and self.shots[-1][1] == f0 - 1 else None
        if prev is not None and self._similar(prev[3], a):
            a, cut = dict(prev[3]), False          # glide on from where we are instead of jump-cutting
        elif prev is not None and not cut:
            cut = True                              # a 1-frame "glide" to a different framing IS a cut
        b = self._limit(a, b, f1 - f0)
        la, lb = a.get("lens", self.lens), b.get("lens", self.lens)
        ca, aa = self.pose(**a)
        cb, ab = self.pose(**b)
        interp, easing = EASES[ease]
        if cut and f0 > 1:
            prev_keys = [kp for fc in fcurves(self.cam) if fc.data_path == "location" for kp in fc.keyframe_points
                         if kp.co.x < f0]
            if prev_keys:
                last = max(kp.co.x for kp in prev_keys)
                for idb, path in ((self.cam, "location"), (self.aim, "location"), (self.data, "lens")):
                    _set_interp(idb, path, last, "CONSTANT")
        self._key(f0, ca, aa, la, interp, easing)
        self._key(f1, cb, ab, lb, "BEZIER", "AUTO")
        self.shots.append((f0, f1, a, b))

    def shake(self, f0, f1, amp=0.06, seed=1, hz=4.0):
        """A smooth, decaying rumble (keyed every frame on a sine): random jumps every 2 frames strobed."""
        rnd = random.Random(seed)
        phase = [rnd.uniform(0, 6.28) for _ in range(3)]
        self.rig.location = (0, 0, 0)
        self.rig.keyframe_insert("location", frame=f0 - 1)
        for f in range(f0, f1 + 1):
            t = (f - f0) / 30.0
            k = amp * math.exp(-4.0 * t)
            self.rig.location = tuple(k * math.sin(2 * math.pi * hz * t + ph) * s
                                      for ph, s in zip(phase, (1.0, 0.3, 0.8)))
            self.rig.keyframe_insert("location", frame=f)
        self.rig.location = (0, 0, 0)
        self.rig.keyframe_insert("location", frame=f1 + 1)


# ------------------------------------------------------------------ anchors

class Anchors:
    """Named points (empties, possibly parented to moving parts). export() writes, per frame, each
    anchor's position on screen (x across, y DOWN, 0..1) for the compositor's pinned labels."""

    def __init__(self):
        self.points = {}

    def add(self, name, loc, parent=None):
        ob = empty(f"A_{name}", loc, parent)
        if parent is not None:
            ob.location = parent.matrix_world.inverted() @ Vector(loc)
        self.points[name] = ob
        return ob

    def export(self, path, f0, f1):
        scene = bpy.context.scene
        cam = scene.camera
        out = {n: {"start": f0, "xy": []} for n in self.points}
        for f in range(f0, f1 + 1):
            scene.frame_set(f)
            for n, ob in self.points.items():
                v = world_to_camera_view(scene, cam, ob.matrix_world.translation)
                xy = [round(v.x, 4), round(1 - v.y, 4)] if v.z > 0 else [-1, -1]
                out[n]["xy"].append(xy)
        with open(path, "w") as fh:
            json.dump(out, fh)
        return out
