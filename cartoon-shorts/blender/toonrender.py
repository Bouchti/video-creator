"""Blender (Eevee) renderer for the cartoon story shorts (Nov 9: moved off three.js for real light, relief, haze and
fast cameras). Reads the per-frame state exported by scripts/export_blender.mjs (same story.ts / cast.ts as the old film):
cameras, cars, flat character cards and effect cards, and renders them inside a real 3D set.

    blender -b -P blender/toonrender.py -- <exportDir> <outDir> [--stills 2,40,80] [--scale 0.5] [--samples 32]

Coordinates: the export is three.js (y up, characters face +z); Blender is z up: (x, y, z)_three -> (x, -z, y).
"""
import bpy, json, math, os, sys
from mathutils import Vector, Quaternion, Matrix, Euler

argv = sys.argv[sys.argv.index("--") + 1:]
EXP, OUT = os.path.abspath(argv[0]), os.path.abspath(argv[1])
opt = {argv[i][2:]: argv[i + 1] for i in range(2, len(argv) - 1, 2) if argv[i].startswith("--")}
STILLS = [int(x) for x in opt["stills"].split(",")] if "stills" in opt else None
SCALE = float(opt.get("scale", "1"))
SAMPLES = int(opt.get("samples", "48"))
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ACG = os.path.join(ROOT, "assets", "cc0", "ambientcg")
HDRI = os.path.join(ROOT, "assets", "cc0", "polyhaven", "hdris")
QUAT = os.path.join(ROOT, "cartoon-shorts", "public", "bridge", "quat")
data = json.load(open(os.path.join(EXP, "frames.json")))
FR = {fr["f"]: fr for fr in data["frames"]}
F0, F1 = data["f0"], data["f1"]
SPR = os.path.join(EXP, "sprites")
T = lambda x, y, z: Vector((x, -z, y))  # three -> blender

# ---------------------------------------------------------------- scene
bpy.ops.wm.read_factory_settings(use_empty=True)
try: bpy.context.preferences.system.anisotropic_filter = "FILTER_16"   # v2: grazing floors (tiles, grass) shimmered
except Exception as e: print("anisotropic:", e)
sc = bpy.context.scene
bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"  # per-frame keys; booleans step anyway
sc.render.fps = data["fps"]
sc.frame_start, sc.frame_end = F0, F1 - 1
sc.render.resolution_x, sc.render.resolution_y = int(1440 * SCALE), int(2560 * SCALE)
sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
ee = sc.eevee
ee.taa_render_samples = SAMPLES
for k, v in [("use_raytracing", True), ("use_shadows", True), ("shadow_ray_count", 2), ("shadow_step_count", 8), ("use_volumetric_shadows", True),
             ("volumetric_end", 260.0), ("volumetric_tile_size", "4"), ("fast_gi_method", "GLOBAL_ILLUMINATION"), ("use_fast_gi", True)]:
    if hasattr(ee, k):
        try: setattr(ee, k, v)
        except Exception: pass
sc.render.use_motion_blur = True
if hasattr(sc.render, "motion_blur_shutter"): sc.render.motion_blur_shutter = 0.5
# GRADE (owner, 11 Nov: the Blender films looked faded and dark next to the earlier shorts: saturation 0.2 vs 0.5):
# "vivid" (default, tuned 11 Nov on Hoover stills: luma 0.35-0.60, saturation 0.36-0.74, 0 % clipped) = AgX Punchy at
# exposure 1.25, the HDRI sky saturated x1.8, haze 0.05, compositor saturation x1.25 + contrast 6; "agx" = the old look.
GRADE = opt.get("grade", "vivid")
sc.view_settings.view_transform = opt.get("view", "AgX")
sc.view_settings.exposure = float(opt.get("exposure", "1.25" if GRADE == "vivid" else "0.35"))
try: sc.view_settings.look = "AgX - Punchy" if sc.view_settings.view_transform == "AgX" else "None"
except Exception: pass
sc.render.film_transparent = False

def mat_new(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    return m, m.node_tree.nodes, m.node_tree.links

def pbr(name, folder, scale=1.0, tint=None, rough_mul=1.0, normal_strength=1.0):
    """ambientCG PBR set, tiled in world space (no UVs needed on big planes)"""
    m, n, l = mat_new(name)
    bsdf = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord"); mp = n.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1 / scale, 1 / scale, 1 / scale)
    l.new(tc.outputs["Object"], mp.inputs["Vector"])
    base = os.path.join(ACG, folder, f"{folder}_2K-JPG")
    def img(suffix, non_color=False):
        t = n.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(base + suffix, check_existing=True)
        if non_color: t.image.colorspace_settings.name = "Non-Color"
        l.new(mp.outputs["Vector"], t.inputs["Vector"]); return t
    col = img("_Color.jpg")
    if tint:
        mx = n.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MULTIPLY"; mx.inputs[0].default_value = 1.0
        l.new(col.outputs["Color"], mx.inputs[6]); mx.inputs[7].default_value = (*tint, 1)
        l.new(mx.outputs[2], bsdf.inputs["Base Color"])
    else:
        l.new(col.outputs["Color"], bsdf.inputs["Base Color"])
    ro = img("_Roughness.jpg", True); rm = n.new("ShaderNodeMath"); rm.operation = "MULTIPLY"; rm.inputs[1].default_value = rough_mul
    l.new(ro.outputs["Color"], rm.inputs[0]); l.new(rm.outputs[0], bsdf.inputs["Roughness"])
    nm = img("_NormalGL.jpg", True); nn = n.new("ShaderNodeNormalMap"); nn.inputs["Strength"].default_value = normal_strength
    l.new(nm.outputs["Color"], nn.inputs["Color"]); l.new(nn.outputs["Normal"], bsdf.inputs["Normal"])
    return m

def flat(name, col, rough=0.6, metal=0.0, coat=0.0, emit=None):
    m, n, l = mat_new(name); b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1); b.inputs["Roughness"].default_value = rough; b.inputs["Metallic"].default_value = metal
    if coat and "Coat Weight" in b.inputs: b.inputs["Coat Weight"].default_value = coat
    if emit: b.inputs["Emission Color"].default_value = (*emit, 1); b.inputs["Emission Strength"].default_value = 1.0
    return m

def hexc(h):
    h = h.lstrip("#"); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)

def obj(name, mesh, mat=None, loc=(0, 0, 0), parent=None):
    o = bpy.data.objects.new(name, mesh); bpy.context.collection.objects.link(o); o.location = loc
    if mat: o.data.materials.append(mat)
    if parent: o.parent = parent
    return o

def box(name, x0, x1, y0, y1, z0, z1, mat, parent=None, bevel=0.0):
    """axis box in BLENDER coords"""
    import bmesh
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bm.loops.layers.uv.new("UVMap"); bmesh.ops.create_cube(bm, size=1.0, calc_uvs=True); bm.to_mesh(me); bm.free()
    o = obj(name, me, mat, ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), parent); o.scale = (x1 - x0, y1 - y0, z1 - z0)
    if bevel:
        md = o.modifiers.new("bev", "BEVEL"); md.width = bevel; md.segments = 3; md.limit_method = "NONE"
        o.modifiers.new("ws", "WEIGHTED_NORMAL") if hasattr(bpy.types, "WeightedNormalModifier") else None
    return o

def plane(name, x0, x1, y0, y1, z, mat):
    me = bpy.data.meshes.new(name); me.from_pydata([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], [], [(0, 1, 2, 3)]); me.update()
    return obj(name, me, mat)

# ---------------------------------------------------------------- world: HDRI sky + haze
world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
wn, wl = world.node_tree.nodes, world.node_tree.links
bg = wn["Background"]; env = wn.new("ShaderNodeTexEnvironment")
def hdri_path(folder):
    d = os.path.join(HDRI, folder)
    if not os.path.isdir(d): return d
    return os.path.join(d, [f for f in sorted(os.listdir(d)) if f.endswith((".hdr", ".exr"))][0])
# the default sky is pinned (Nov 12: new HDRIs sort before it and silently changed older films)
hpath = hdri_path(opt.get("hdri", "kloofendal_48d_partly_cloudy_puresky") if os.path.isdir(os.path.join(HDRI, opt.get("hdri", "kloofendal_48d_partly_cloudy_puresky"))) else sorted(os.listdir(HDRI))[0])
env.image = bpy.data.images.load(hpath); bg.inputs["Strength"].default_value = 0.85
if GRADE == "vivid":   # a cartoon-blue sky: saturate the HDRI and pull its blue deeper, clouds stay white
    hs = wn.new("ShaderNodeHueSaturation"); hs.inputs["Saturation"].default_value = float(opt.get("skysat", "1.8")); hs.inputs["Value"].default_value = 1.0
    wl.new(env.outputs["Color"], hs.inputs["Color"]); wl.new(hs.outputs["Color"], bg.inputs["Color"])
else:
    wl.new(env.outputs["Color"], bg.inputs["Color"])
vol = wn.new("ShaderNodeVolumePrincipled"); vol.inputs["Density"].default_value = 0.0009; vol.inputs["Color"].default_value = (*hexc("#e9dcc4"), 1)
if opt.get("haze", "0") == "1": wl.new(vol.outputs["Volume"], wn["World Output"].inputs["Volume"])  # world volume blacked out Eevee: off by default

sun_dir = T(*data["sun"]).normalized()
sun = bpy.data.lights.new("sun", "SUN"); sun.energy = 4.2; sun.color = hexc("#fff0d8"); sun.angle = math.radians(1.6)
so = obj("sun", sun); so.rotation_euler = (-sun_dir).to_track_quat("-Z", "Y").to_euler()

# ---------------------------------------------------------------- shared set helpers + the film's sets (blender/sets_<name>.py)
def load_glb(name):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(QUAT, name + ".glb"))
    new = [o for o in bpy.data.objects if o not in before]
    col = bpy.data.collections.new("K_" + name)
    for o in new:
        for c in o.users_collection: c.objects.unlink(o)
        col.objects.link(o)
    zs = [(o.matrix_world @ Vector(c)).z for o in new if o.type == "MESH" for c in o.bound_box]
    return col, (min(zs), max(zs)) if zs else (0, 1)
KIT = {n: load_glb(n) for n in ["CommonTree_1", "CommonTree_2", "CommonTree_3", "CommonTree_4", "Grass_Common_Tall", "Grass_Wispy_Tall", "Flower_3_Group", "Flower_4_Group", "Bush_Common_Flowers", "Bush_Common", "Rock_Medium_1", "Pebble_Round_1"]}
def inst(name, x3, z3, h, yaw, y3=0.07):
    col, (lo, hi) = KIT[name]; e = bpy.data.objects.new(name, None); e.instance_type = "COLLECTION"; e.instance_collection = col
    s_ = h / max(0.01, hi - lo); e.scale = (s_, s_, s_); e.location = (x3, -z3, y3 - lo * s_); e.rotation_euler = (0, 0, yaw)
    bpy.context.collection.objects.link(e)
def hh(i, s_=0):
    v = math.sin(i * 127.1 + s_ * 311.7) * 43758.5453; return v - math.floor(v)
OUT_ROOT = os.path.dirname(OUT)
SET = opt.get("set", "marathon")
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), f"sets_{SET}.py"), encoding="utf-8").read())

# ---------------------------------------------------------------- the 1904 car (local three coords -> blender; front at three +z)
def make_car(name, body_hex):
    root = bpy.data.objects.new(name, None); bpy.context.collection.objects.link(root)
    paint = flat(name + "_paint", hexc(body_hex), 0.28, 0.0, coat=0.7)
    black = flat("carBlack", hexc("#1d1b22"), 0.55); brass = flat("brass", hexc("#d9a640"), 0.28, 1.0)
    leather = flat("leather", hexc("#5a2e1c"), 0.55); glass = flat("lampglass", hexc("#fff4cf"), 0.1, emit=hexc("#ffe7a8"))
    def B(n, x0, x1, y0, y1, z0, z1, m, bev=0.03):   # three-local box -> blender-local box
        return box(n, x0, x1, -z1, -z0, y0, y1, m, root, bev)
    B("tub", -0.72, 0.72, 0.55, 1.0, -1.45, 0.55, paint, 0.06)
    B("hood", -0.42, 0.42, 0.6, 0.98, 0.55, 1.45, paint, 0.05)
    B("radiator", -0.46, 0.46, 0.52, 1.08, 1.45, 1.56, brass, 0.03)
    B("grille", -0.36, 0.36, 0.6, 1.0, 1.56, 1.58, black, 0.0)
    B("board", -0.86, 0.86, 0.5, 0.56, -1.0, 0.9, black, 0.01)
    for z, y in ((-1.5, 1.14), (-0.14, 1.1)):
        bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.15, depth=1.32, location=(0, -z, y), rotation=(0, math.pi / 2, 0))
        c = bpy.context.object; c.parent = root; c.data.materials.append(leather); bpy.ops.object.shade_smooth()
        B("seat", -0.66, 0.66, 0.98, y, z - 0.08, z + 0.08, leather, 0.04)
    for s in (-1, 1):
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.15, depth=0.24, location=(s * 0.58, -1.52, 1.05), rotation=(math.pi / 2, 0, 0))
        c = bpy.context.object; c.parent = root; c.data.materials.append(brass); bpy.ops.object.shade_smooth()
        bpy.ops.mesh.primitive_circle_add(vertices=24, radius=0.12, fill_type="NGON", location=(s * 0.58, -1.645, 1.05), rotation=(math.pi / 2, 0, 0))
        c = bpy.context.object; c.parent = root; c.data.materials.append(glass)
        bpy.ops.mesh.primitive_cone_add(vertices=20, radius1=0.17, radius2=0.03, depth=0.62, location=(s * 0.86, 0.2, 1.18), rotation=(math.pi / 2, 0, 0))
        c = bpy.context.object; c.parent = root; c.data.materials.append(brass); bpy.ops.object.shade_smooth()
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.11, location=(s * 0.86, 0.6, 1.18)); c = bpy.context.object; c.parent = root; c.data.materials.append(black); bpy.ops.object.shade_smooth()
        B("stripe", s * 0.725 - 0.006, s * 0.725 + 0.006, 0.88, 0.92, -1.45, 0.55, brass, 0.0)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.36, minor_radius=0.08, location=(0, 2.2, 0.9), rotation=(math.pi / 2, 0, 0)); c = bpy.context.object; c.parent = root; c.data.materials.append(black)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.17, minor_radius=0.025, location=(0.35, -0.36, 1.42), rotation=(math.radians(25), 0, 0)); c = bpy.context.object; c.parent = root; c.data.materials.append(black)
    wheels = []
    for x, z in ((-0.8, 1.15), (0.8, 1.15), (-0.8, -1.15), (0.8, -1.15)):
        w = bpy.data.objects.new("wheel", None); bpy.context.collection.objects.link(w); w.parent = root; w.location = (x, -z, 0.45)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.4, minor_radius=0.065, location=(0, 0, 0), rotation=(0, math.pi / 2, 0)); c = bpy.context.object; c.parent = w; c.data.materials.append(black); bpy.ops.object.shade_smooth()
        spoke = flat("spoke", hexc("#e8d9b0"), 0.5)
        for k in range(8):
            bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.02, depth=0.76, location=(0, 0, 0), rotation=(k / 8 * math.pi, 0, 0)); c = bpy.context.object; c.parent = w; c.data.materials.append(spoke)
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.08, depth=0.14, location=(0, 0, 0), rotation=(0, math.pi / 2, 0)); c = bpy.context.object; c.parent = w; c.data.materials.append(brass)
        wheels.append(w)
    return root, wheels
# ---------------------------------------------------------------- several skies (Gimli, 12 Nov): a set file may list SKIES (HDRI folders);
# each MOOD entry then carries a 6th value, the sky index, and the world switches sky per shot (mix factors keyed per frame)
SKY_MIX = []
if "SKIES" in globals() and SKIES:
    prev = None
    def grad_sky(spec):
        """'grad:#horizon:#glow:#mid:#zenith:az=262:el=9' -> a stylised gradient sky with a warm halo round the sun"""
        parts = spec.split(":")[1:]; cols = [p for p in parts if p.startswith("#")]; kv = dict(p.split("=") for p in parts if "=" in p)
        tc = wn.new("ShaderNodeTexCoord"); sep = wn.new("ShaderNodeSeparateXYZ"); wl.new(tc.outputs["Generated"], sep.inputs[0])
        ramp = wn.new("ShaderNodeValToRGB"); cr = ramp.color_ramp
        stops = [(0.0, cols[0]), (0.07, cols[1]), (0.32, cols[2]), (1.0, cols[3])]
        cr.elements[0].position, cr.elements[0].color = stops[0][0], (*hexc(stops[0][1]), 1); cr.elements[1].position, cr.elements[1].color = stops[-1][0], (*hexc(stops[-1][1]), 1)
        for pos, c in stops[1:-1]: e_ = cr.elements.new(pos); e_.color = (*hexc(c), 1)
        mr = wn.new("ShaderNodeMapRange"); mr.inputs[1].default_value = -0.04; mr.inputs[2].default_value = 1.0; wl.new(sep.outputs["Z"], mr.inputs[0]); wl.new(mr.outputs[0], ramp.inputs[0])
        az, el = math.radians(float(kv.get("az", 0))), math.radians(float(kv.get("el", 10)))
        sd = wn.new("ShaderNodeCombineXYZ"); sd.inputs[0].default_value = math.cos(el) * math.sin(az); sd.inputs[1].default_value = math.cos(el) * math.cos(az); sd.inputs[2].default_value = math.sin(el)
        nrm = wn.new("ShaderNodeVectorMath"); nrm.operation = "NORMALIZE"; wl.new(tc.outputs["Generated"], nrm.inputs[0])
        dot = wn.new("ShaderNodeVectorMath"); dot.operation = "DOT_PRODUCT"; wl.new(nrm.outputs[0], dot.inputs[0]); wl.new(sd.outputs[0], dot.inputs[1])
        glow = wn.new("ShaderNodeMapRange"); glow.inputs[1].default_value = 0.82; glow.inputs[2].default_value = 1.0; wl.new(dot.outputs["Value"], glow.inputs[0])
        pw = wn.new("ShaderNodeMath"); pw.operation = "POWER"; pw.inputs[1].default_value = 3.0; wl.new(glow.outputs[0], pw.inputs[0])
        gm = wn.new("ShaderNodeMath"); gm.operation = "MULTIPLY"; gm.inputs[1].default_value = float(kv.get("halo", 2.5)); wl.new(pw.outputs[0], gm.inputs[0])
        add = wn.new("ShaderNodeMix"); add.data_type = "RGBA"; add.blend_type = "ADD"; wl.new(gm.outputs[0], add.inputs[0])
        wl.new(ramp.outputs["Color"], add.inputs[6]); add.inputs[7].default_value = (*hexc(kv.get("sun", "#fff0c8").replace("_", "#") if kv.get("sun") else "#fff0c8"), 1)
        return add.outputs[2]
    for i, folder in enumerate(SKIES):
        if folder.startswith("grad:"):
            out_c = grad_sky(folder)
        else:
            e = wn.new("ShaderNodeTexEnvironment"); e.image = bpy.data.images.load(hdri_path(folder), check_existing=True)
            hs_ = wn.new("ShaderNodeHueSaturation"); hs_.inputs["Saturation"].default_value = float(opt.get("skysat", "1.35")); wl.new(e.outputs["Color"], hs_.inputs["Color"]); out_c = hs_.outputs["Color"]
        if prev is None: prev = out_c; continue
        mx = wn.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.inputs[0].default_value = 0.0
        wl.new(prev, mx.inputs[6]); wl.new(out_c, mx.inputs[7]); prev = mx.outputs[2]; SKY_MIX.append(mx)
    wl.new(prev, bg.inputs["Color"])
    print("SKIES:", SKIES)
CARS = VEHICLES if "VEHICLES" in globals() else {"lorz": make_car("carLorz", "#b3181c"), "off": make_car("carOff", "#2f6a43")}

# ---------------------------------------------------------------- cards: one object per slot, an image sequence per slot
SU = 0.00216
def card_mesh(name, w_units, h_units, sole=975):
    x = w_units / 2 * SU; z0 = -(1000 - sole) * SU; z1 = sole * SU
    me = bpy.data.meshes.new(name); me.from_pydata([(-x, 0, z0), (x, 0, z0), (x, 0, z1), (-x, 0, z1)], [], [(0, 1, 2, 3)])
    me.uv_layers.new(); uv = me.uv_layers[0].data
    for i, c in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]): uv[i].uv = c
    me.update(); return me
BODY, WIDE = card_mesh("BODY", 600, 1000), card_mesh("WIDE", 1000, 1000)
def unit_mesh():
    me = bpy.data.meshes.new("FX"); me.from_pydata([(-0.5, 0, -0.5), (0.5, 0, -0.5), (0.5, 0, 0.5), (-0.5, 0, 0.5)], [], [(0, 1, 2, 3)])
    me.uv_layers.new(); uv = me.uv_layers[0].data
    for i, c in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]): uv[i].uv = c
    me.update(); return me
FXM = unit_mesh()

SLOTDIR = os.path.join(OUT, "_slots"); os.makedirs(SLOTDIR, exist_ok=True)
BLANK = os.path.join(SLOTDIR, "blank.png")
if not os.path.exists(BLANK):
    im = bpy.data.images.new("blank", 4, 4, alpha=True); im.pixels = [0.0] * 64; im.filepath_raw = BLANK; im.file_format = "PNG"; im.save()
frames = [f for f in range(F0, F1)] if STILLS is None else STILLS
# slot assignment: per frame, the n-th card of character key o -> slot "o#n"
slots = {}
for f in range(F0, F1):
    fr = FR[f]; seen = {}
    for kind in ("places", "fx"):
        for p in fr[kind]:
            n = seen.get((kind, p["o"]), 0); seen[(kind, p["o"])] = n + 1
            slots.setdefault((kind, p["o"], n), {})[f] = p

def link_seq(key, per_frame):
    safe = "".join(ch if ch.isalnum() else "_" for ch in key)
    d = os.path.join(SLOTDIR, safe); os.makedirs(d, exist_ok=True)
    for f in range(F0, F1):
        dst = os.path.join(d, "%s_%05d.png" % (safe, f - F0 + 1))   # unique names: Blender caches sequence frames by file name
        p = per_frame.get(f)
        if p is None and f not in (F0,): continue                    # hidden that frame: no file needed
        if os.path.exists(dst): os.remove(dst)
        src = os.path.join(SPR, p["s"] + ".png") if p else BLANK
        try: os.link(src, dst)
        except OSError:
            import shutil; shutil.copyfile(src, dst)
    return os.path.join(d, "%s_%05d.png" % (safe, 1))

def card_material(name, first_file, soft=False, lit=True):
    m, n, l = mat_new(name)
    out = n["Material Output"]; n.remove(n["Principled BSDF"])
    tex = n.new("ShaderNodeTexImage"); img = bpy.data.images.load(first_file); img.source = "SEQUENCE"; tex.image = img
    tex.image_user.frame_duration = F1 - F0; tex.image_user.frame_start = F0; tex.image_user.use_auto_refresh = True; tex.interpolation = "Smart"
    # flat cartoon card that still sits in the light: 78 % own colour (emission) + 22 % lit diffuse (sun / shade / bounce)
    em = n.new("ShaderNodeEmission"); l.new(tex.outputs["Color"], em.inputs["Color"]); em.inputs["Strength"].default_value = 0.8 if lit else 1.0
    df = n.new("ShaderNodeBsdfDiffuse"); l.new(tex.outputs["Color"], df.inputs["Color"])
    add = n.new("ShaderNodeAddShader"); l.new(em.outputs[0], add.inputs[0]); l.new(df.outputs[0], add.inputs[1])
    tr = n.new("ShaderNodeBsdfTransparent"); mix = n.new("ShaderNodeMixShader")
    if soft:
        l.new(tex.outputs["Alpha"], mix.inputs[0])
    else:
        gt = n.new("ShaderNodeMath"); gt.operation = "GREATER_THAN"; gt.inputs[1].default_value = 0.5; l.new(tex.outputs["Alpha"], gt.inputs[0]); l.new(gt.outputs[0], mix.inputs[0])
    l.new(tr.outputs[0], mix.inputs[1]); l.new(add.outputs[0] if lit else em.outputs[0], mix.inputs[2]); l.new(mix.outputs[0], out.inputs["Surface"])
    if hasattr(m, "surface_render_method"): m.surface_render_method = "BLENDED" if soft else "DITHERED"
    else: m.blend_method = "BLEND" if soft else "HASHED"
    # characters cast their real silhouette shadow on the set (reference look), not a card-shaped one
    if hasattr(m, "use_transparent_shadow"): m.use_transparent_shadow = True
    return m

cam_d = bpy.data.cameras.new("cam"); cam_d.sensor_fit = "VERTICAL"; cam_d.sensor_height = 24.0; cam_d.sensor_width = 13.5
camo = obj("camera", cam_d); sc.camera = camo; cam_d.clip_start = 0.1; cam_d.clip_end = 3000

def cam_quat(fr):
    c = fr["cam"]; pos = T(*c["pos"]); look = T(*c["look"])
    q = (look - pos).to_track_quat("-Z", "Y")
    return pos, q @ Quaternion((0, 0, 1), c["roll"])

def key_obj(o, f, loc=None, rot=None, scl=None, hide=None):
    if loc is not None: o.location = loc; o.keyframe_insert("location", frame=f)
    if rot is not None:
        if isinstance(rot, Quaternion): o.rotation_mode = "QUATERNION"; o.rotation_quaternion = rot; o.keyframe_insert("rotation_quaternion", frame=f)
        else: o.rotation_euler = rot; o.keyframe_insert("rotation_euler", frame=f)
    if scl is not None: o.scale = scl; o.keyframe_insert("scale", frame=f)
    if hide is not None: o.hide_render = hide; o.keyframe_insert("hide_render", frame=f)

for (kind, o, n), per in slots.items():
    first = link_seq(f"{kind}_{o}_{n}", per)
    any_p = next(iter(per.values()))
    if kind == "places":
        ob = obj(f"card_{o}_{n}", (WIDE if any_p["wide"] else BODY).copy(), card_material(f"m_{o}_{n}", first))  # own mesh: materials live on mesh data
        ob.visible_shadow = True
    else:
        ob = obj(f"fx_{o}_{n}", FXM.copy(), card_material(f"mf_{o}_{n}", first, soft=bool(any_p["soft"]), lit=False))
        ob.visible_shadow = False
    for f in range(F0, F1):
        p = per.get(f)
        if p is None: key_obj(ob, f, hide=True); continue
        if kind == "places":
            mir = -1 if p["m"] else 1
            key_obj(ob, f, loc=T(p["x"], p["y"], p["z"]), rot=Euler((0, -p["roll"], p["yaw"]), "XYZ"), scl=(p["sc"] * mir, p["sc"], p["sc"]), hide=False)
        else:
            # the unit card's normal is -Y: Rx(-90 deg) turns it toward +Z (up for flat cards, toward the lens for facing ones)
            if p["mode"] == "flat": q = Euler((0, 0, p["rot"]), "XYZ").to_quaternion() @ Quaternion((1, 0, 0), -math.pi / 2)
            elif p["mode"] == "upright": q = Euler((0, 0, p["yaw"]), "XYZ").to_quaternion() @ Quaternion((0, 1, 0), -p["rot"])
            else: q = cam_quat(FR[f])[1] @ Quaternion((1, 0, 0), -math.pi / 2) @ Quaternion((0, 1, 0), p["rot"])
            key_obj(ob, f, loc=T(p["x"], p["y"], p["z"]), rot=q, scl=(p["w"], 1, p["h"]), hide=False)

# ---------------------------------------------------------------- camera, cars, depth of field per frame
def mood_key(f, sid):
    mv = MOOD[mood_of(sid)]; el, az, col, en, sky = mv[:5]
    if SKY_MIX and len(mv) > 5:
        for i, mx in enumerate(SKY_MIX):
            mx.inputs[0].default_value = 1.0 if i + 1 == mv[5] else 0.0; mx.inputs[0].keyframe_insert("default_value", frame=f)
    d = Vector((math.cos(math.radians(el)) * math.sin(math.radians(az)), math.cos(math.radians(el)) * math.cos(math.radians(az)), math.sin(math.radians(el))))
    so.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler(); so.keyframe_insert("rotation_euler", frame=f)
    sun.color = hexc(col); sun.keyframe_insert("color", frame=f); sun.energy = en; sun.keyframe_insert("energy", frame=f)
    bg.inputs["Strength"].default_value = sky; bg.inputs["Strength"].keyframe_insert("default_value", frame=f)
for f in range(F0, F1):
    fr = FR[f]; pos, q = cam_quat(fr)
    if f == F0 or FR[f]["id"] != FR[f - 1]["id"] or f == F1 - 1 or FR.get(f + 1, fr)["id"] != fr["id"]: mood_key(f, fr["id"])
    key_obj(camo, f, loc=pos, rot=q)
    cam_d.angle_y = math.radians(fr["cam"]["fov"]); cam_d.keyframe_insert("lens", frame=f)
    d = fr["dof"]; fc = T(*d["focus"])
    dist = max(0.3, (fc - pos).dot(q @ Vector((0, 0, -1))))
    cam_d.dof.use_dof = d["c"] > 0
    cam_d.dof.focus_distance = dist; cam_d.dof.keyframe_insert("focus_distance", frame=f)
    if d["c"] > 0:
        fmm = cam_d.lens; px_per_mm = sc.render.resolution_y / 24.0
        blur_mm = 2 * d["c"] * 0.75 * (sc.render.resolution_y / 1920) / px_per_mm
        cam_d.dof.aperture_fstop = max(0.25, fmm * fmm / (max(dist * 1000 - fmm, 1) * blur_mm))
    else:
        cam_d.dof.aperture_fstop = 64
    cam_d.dof.keyframe_insert("aperture_fstop", frame=f)
    for k, (root, wheels) in CARS.items():
        c = fr["cars"].get(k)
        if c is None: key_obj(root, f, hide=True); [key_obj(ch, f, hide=True) for ch in root.children_recursive]; continue
        key_obj(root, f, loc=T(c["x"], c.get("y", 0), c["z"]), rot=Euler((c.get("pitch", 0), c.get("roll", 0), math.pi + c["yaw"]), "XYZ"), hide=False)
        for ch in root.children_recursive: key_obj(ch, f, hide=False)
        for w in wheels: key_obj(w, f, rot=Euler((c["d"] / 0.45, 0, 0), "XYZ"))

# ---------------------------------------------------------------- 3D props (set files that define PROPS): one collection
# instance per (kind, n-th of that kind in the frame), keyed per frame (Hoover film v2, 11 Nov)
PR = globals().get("PROPS")
if PR:
    pslots = {}
    for f in range(F0, F1):
        seen = {}
        for p in FR[f].get("props", []):
            n = seen.get(p["k"], 0); seen[p["k"]] = n + 1
            pslots.setdefault((p["k"], n), {})[f] = p
    for (k, n), per in pslots.items():
        if k not in PR: print("MISSING PROP", k); continue
        e = bpy.data.objects.new(f"prop_{k}_{n}", None); e.instance_type = "COLLECTION"; e.instance_collection = PR[k]; bpy.context.collection.objects.link(e)
        for f in range(F0, F1):
            p = per.get(f)
            if p is None: key_obj(e, f, hide=True); continue
            key_obj(e, f, loc=T(p["x"], p["y"], p["z"]), rot=Euler((p["pitch"], p["roll"], p["yaw"]), "XYZ"), scl=(p["s"], p["s"], p["s"]), hide=False)
    print("PROP SLOTS", len(pslots))

# ---------------------------------------------------------------- compositor: a little glare for the lamps and highlights
bpy.context.view_layer.use_pass_mist = True
world.mist_settings.start = 40; world.mist_settings.depth = 450; world.mist_settings.falloff = "QUADRATIC"
def build_comp():
    if hasattr(sc, "compositing_node_group"):
        ng = bpy.data.node_groups.new("Comp", "CompositorNodeTree")
        ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        sc.compositing_node_group = ng
        out = ng.nodes.new("NodeGroupOutput"); out_in = out.inputs[0]
    else:
        sc.use_nodes = True; ng = sc.node_tree; out_in = ng.nodes["Composite"].inputs["Image"]
    nodes, links = ng.nodes, ng.links
    rl = nodes.get("Render Layers") or nodes.new("CompositorNodeRLayers")
    # depth haze: mix toward a pale warm haze colour by the mist pass
    try:
        mix = nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; fac, a, b, res = mix.inputs[0], mix.inputs[6], mix.inputs[7], mix.outputs[2]
    except Exception:
        mix = nodes.new("CompositorNodeMixRGB"); fac, a, b, res = mix.inputs[0], mix.inputs[1], mix.inputs[2], mix.outputs[0]
    b.default_value = (*hexc("#e4e2dc"), 1)
    try:
        mul = nodes.new("ShaderNodeMath")
    except Exception:
        mul = nodes.new("CompositorNodeMath")
    mul.operation = "MULTIPLY"; mul.inputs[1].default_value = 0.18 if GRADE != "vivid" else 0.05
    links.new(rl.outputs["Mist"], mul.inputs[0]); links.new(mul.outputs[0], fac); links.new(rl.outputs["Image"], a)
    if GRADE == "vivid":
        hs = None
        for kind in ("CompositorNodeHueSat", "ShaderNodeHueSaturation"):
            try: hs = nodes.new(kind); break
            except Exception: pass
        cs = None
        for kind in ("CompositorNodeBrightContrast",):
            try: cs = nodes.new(kind); break
            except Exception: pass
        cur = res
        if hs is not None:
            sat_in = hs.inputs.get("Saturation"); img_in = hs.inputs.get("Image") or hs.inputs.get("Color")
            sat_in.default_value = float(opt.get("sat", "1.25")); links.new(cur, img_in); cur = hs.outputs[0]; print("GRADE: saturation", sat_in.default_value)
        if cs is not None:
            cs.inputs["Contrast"].default_value = float(opt.get("contrast", "6")); cs.inputs["Bright"].default_value = float(opt.get("bright", "0"))
            links.new(cur, cs.inputs["Image"]); cur = cs.outputs[0]; print("GRADE: contrast")
        links.new(cur, out_in)
    else:
        links.new(res, out_in)  # (glare dropped: the Blender 5 glare node API changed and an unlinked output renders black)
try:
    build_comp(); print("COMPOSITOR OK")
except Exception as e:
    import traceback; traceback.print_exc(); print("compositor skipped:", e)

# ---------------------------------------------------------------- render
os.makedirs(OUT, exist_ok=True)
sc.render.image_settings.file_format = "PNG"
sc.render.filepath = os.path.join(OUT, "f_")
sc.render.use_overwrite = False; sc.render.use_placeholder = True   # a killed render resumes where it stopped
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "scene.blend"))
if opt.get("build") == "1":
    print("BUILT", os.path.join(OUT, "scene.blend"))
elif STILLS is not None:
    for f in STILLS:
        sc.frame_set(f); sc.render.filepath = os.path.join(OUT, "s_%04d.png" % f); bpy.ops.render.render(write_still=True)
        print("STILL", f)
else:
    sc.render.filepath = os.path.join(OUT, "f_"); bpy.ops.render.render(animation=True)
