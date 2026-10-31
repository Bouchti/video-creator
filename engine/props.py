"""
BLENDERKIT PROPS for Max story sets (the cutaway-bk route): whole, recognisable objects (a family car, a
ship, a crane barge, a forklift, a house, a tree, a picnic table) come from BlenderKit instead of being built
as grey boxes; the MECHANISM (whatever is sliced open, floods, cracks or moves piece by piece) is still built
from primitives, because a downloaded model can't be cut or taken apart.

    from engine import props as bk
    car = bk.prop("family car", 4.2, fallback=lambda: self.build_car())    # in a set's build code
    car.location = (-28, 1.4, 0.5)                                           # place / rotate / animate the root

The query and size must be LITERALS (the pipeline reads them from the code before the render and resolves
them with agents/blenderkit.py into assets/blenderkit/props_manifest.json: Blender has no network or API
key). No model found, or an import error -> the fallback builds it from primitives (at the origin, bottom on
z = 0); no fallback -> a plain rounded block. A missing model never stops a film.
"""
import json
import os

import bpy
from mathutils import Vector

from engine import toy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "assets", "blenderkit", "props_manifest.json")
SATURATE = 1.15      # imported colours, a touch livelier: the set's toy palette is saturated


def key(query):
    return " ".join(str(query).lower().split())


def _manifest():
    try:
        with open(MANIFEST, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _empty(name):
    ob = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def _to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _average(image):
    """Mean colour of an image texture (sRGB bytes -> linear), from an 8x8 copy."""
    if not image or not image.size[0]:
        return None
    small = image.copy()
    try:
        small.scale(8, 8)
        px = list(small.pixels)
    finally:
        bpy.data.images.remove(small)
    n = len(px) // 4
    if not n:
        return None
    rgb = [sum(px[i::4]) / n for i in range(3)]
    return tuple(rgb) if image.is_float else tuple(_to_linear(c) for c in rgb)


def _base_colour(mat):
    """What a material looks like at a glance: its base colour texture's mean, else its base colour."""
    if not mat or not mat.use_nodes:
        return tuple(mat.diffuse_color[:3]) if mat else (0.6, 0.6, 0.6)
    for node in mat.node_tree.nodes:
        if node.type == "BSDF_PRINCIPLED":
            sock = node.inputs.get("Base Color")
            if sock and sock.is_linked:
                src = sock.links[0].from_node
                if src.type == "TEX_IMAGE":
                    avg = _average(src.image)
                    if avg:
                        return avg
            if sock:
                return tuple(sock.default_value[:3])
    return tuple(mat.diffuse_color[:3])


def _saturate(rgb, k=SATURATE):
    m = sum(rgb) / 3
    return tuple(max(0.0, min(1.0, m + (c - m) * k)) for c in rgb)


def toon(objs):
    """The style pass: every material becomes one flat toy colour taken from its own texture, so a realistic
    model sits in the clean cartoon world instead of clashing with it (and renders faster)."""
    done = {}
    for ob in objs:
        if ob.type != "MESH":
            continue
        for slot in ob.material_slots:
            src = slot.material
            if src is None:
                continue
            if src.name not in done:
                done[src.name] = toy.material(f"bk_{src.name}"[:60], _saturate(_base_colour(src)), roughness=0.55)
            slot.material = done[src.name]


def _import(path, name, size_m, style=True):
    """Every object of a BlenderKit .blend under one empty: bottom on z = 0, footprint centred, largest
    dimension = size_m (BlenderKit models come with arbitrary origins and units)."""
    before = set(bpy.data.objects)
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = list(src.objects)
    root = _empty(f"BK_{name}")
    for ob in dst.objects:
        if ob is None or ob.type in ("CAMERA", "LIGHT", "LIGHT_PROBE", "SPEAKER"):
            continue
        bpy.context.scene.collection.objects.link(ob)
    new = [o for o in bpy.data.objects if o not in before and o is not root and o.name in bpy.context.scene.objects]
    for ob in new:
        if ob.parent is None:
            ob.parent = root
    bpy.context.view_layer.update()
    meshes = [o for o in root.children_recursive if o.type == "MESH" and not o.hide_render]
    if not meshes:
        bpy.data.objects.remove(root)
        return None
    pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    offset = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    for ob in root.children:
        ob.location -= offset
    s = float(size_m) / max(max(hi - lo), 1e-4)
    root.scale = (s, s, s)
    for o in meshes:
        o.visible_shadow = True
    light(meshes)
    if style:
        toon(meshes)
    return root


def light(objs):
    """Render-time weight of a downloaded model: subdivision capped at one level and fast booleans. A BlenderKit
    birthday cake (subdivision + displace + booleans + geometry nodes at render levels) took 45 s of CPU per
    frame with the GPU idle: the floating-cabin finale would have rendered for 4 hours. The toon pass flattens
    that detail anyway."""
    for ob in objs:
        for m in getattr(ob, "modifiers", []):
            if m.type == "SUBSURF":
                m.levels = min(m.levels, 1)
                m.render_levels = min(m.render_levels, 1)
            elif m.type == "MULTIRES":
                m.render_levels = min(m.render_levels, 1)
                m.levels = min(m.levels, 1)
            elif m.type == "BOOLEAN":
                for solver in ("FAST", "FLOAT"):          # (the fast solver's name differs between versions)
                    try:
                        m.solver = solver
                        break
                    except TypeError:
                        continue


def _placeholder(name, size_m):
    root = _empty(f"BK_{name}")
    block = toy.box(f"BK_{name}_block", (size_m * 0.8, size_m * 0.5, size_m * 0.5), (0, 0, size_m * 0.25),
                    mat=toy.material("bk_placeholder", (0.8, 0.45, 0.2), roughness=0.5), bevel=0.04)
    block.parent = root
    return root


def prop(query, size_m, fallback=None, name=None, style=True):
    """A whole recognisable object: the BlenderKit model chosen for `query` (scaled so its largest dimension
    is size_m metres, bottom on z = 0, toy-coloured), else fallback() (it must build the object at the
    origin and return its root), else a plain block. Always returns ONE root empty to place and animate."""
    name = name or key(query).replace(" ", "_")[:32]
    rec = _manifest().get(key(query))
    path = rec.get("path") if isinstance(rec, dict) else None
    if path and not os.path.isabs(path):
        path = os.path.join(ROOT, path)
    if path and os.path.isfile(path):
        try:
            root = _import(path, name, size_m, style)
            if root is not None:
                return root
        except Exception as e:  # noqa: BLE001  (a broken download must not stop the film)
            print(f"[props] '{query}': import failed ({e}); building it instead")
    if fallback is not None:
        built = fallback()
        root = _empty(f"BK_{name}")
        if built is not None:
            built.parent = root
        return root
    return _placeholder(name, size_m)
