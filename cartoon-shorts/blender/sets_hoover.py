# The Hoover-van sets for toonrender.py (exec'd inside it: uses its helpers pbr, flat, hexc, box, plane, obj, T, mat_new, inst, hh,
# data, OUT_ROOT). Three.js coordinates in comments (x, y up, z); Blender = (x, -z, y). Mirrors src/videos/hoover/places.ts.
# Defines VEHICLES (van, truck, washer), MOOD and mood_of for the renderer.
import bpy, math, os
from mathutils import Vector, Matrix

ASSETS = os.path.join(OUT_ROOT, "assets")

def tex_mat(name, file, emit=0.0, rough=0.7, cull=True, alpha=False):
    m, n, l = mat_new(name); b = n["Principled BSDF"]
    m.use_backface_culling = cull
    t = n.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(os.path.join(ASSETS, file), check_existing=True)
    l.new(t.outputs["Color"], b.inputs["Base Color"]); b.inputs["Roughness"].default_value = rough
    if emit:
        l.new(t.outputs["Color"], b.inputs["Emission Color"]); b.inputs["Emission Strength"].default_value = emit
    return m

def decal_mat(name, file):
    """printed decal with transparent background (alpha-tested), so only the lettering and stripes show on the paint"""
    m, n, l = mat_new(name); b = n["Principled BSDF"]
    t = n.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(os.path.join(ASSETS, file), check_existing=True)
    l.new(t.outputs["Color"], b.inputs["Base Color"]); l.new(t.outputs["Alpha"], b.inputs["Alpha"]); b.inputs["Roughness"].default_value = 0.3
    if "Coat Weight" in b.inputs: b.inputs["Coat Weight"].default_value = 0.6
    if hasattr(m, "surface_render_method"): m.surface_render_method = "DITHERED"
    else: m.blend_method = "HASHED"
    return m

def pbrb(name, folder, scale=1.0, tint=None, rough_mul=1.0, normal_strength=1.0):
    """ambientCG PBR set, box-projected in WORLD space: works on scaled boxes and walls in any direction"""
    m, n, l = mat_new(name); bsdf = n["Principled BSDF"]
    geo = n.new("ShaderNodeNewGeometry"); mp = n.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1 / scale, 1 / scale, 1 / scale)
    l.new(geo.outputs["Position"], mp.inputs["Vector"])
    base = os.path.join(ACG, folder, f"{folder}_2K-JPG")
    def img(suffix, non_color=False):
        t = n.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(base + suffix, check_existing=True); t.projection = "BOX"; t.projection_blend = 0.25
        if non_color: t.image.colorspace_settings.name = "Non-Color"
        l.new(mp.outputs["Vector"], t.inputs["Vector"]); return t
    col = img("_Color.jpg")
    if tint:
        mx = n.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MULTIPLY"; mx.inputs[0].default_value = 1.0
        l.new(col.outputs["Color"], mx.inputs[6]); mx.inputs[7].default_value = (*tint, 1); l.new(mx.outputs[2], bsdf.inputs["Base Color"])
    else:
        l.new(col.outputs["Color"], bsdf.inputs["Base Color"])
    ro = img("_Roughness.jpg", True); rm = n.new("ShaderNodeMath"); rm.operation = "MULTIPLY"; rm.inputs[1].default_value = rough_mul
    l.new(ro.outputs["Color"], rm.inputs[0]); l.new(rm.outputs[0], bsdf.inputs["Roughness"])
    nm = img("_NormalGL.jpg", True); nn = n.new("ShaderNodeNormalMap"); nn.inputs["Strength"].default_value = normal_strength
    l.new(nm.outputs["Color"], nn.inputs["Color"]); l.new(nn.outputs["Normal"], bsdf.inputs["Normal"])
    return m

def glass_mat(name, col="#3a4f6a", alpha=0.35):
    m, n, l = mat_new(name); b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*hexc(col), 1); b.inputs["Roughness"].default_value = 0.05
    if "Alpha" in b.inputs: b.inputs["Alpha"].default_value = alpha
    if hasattr(m, "surface_render_method"): m.surface_render_method = "BLENDED"
    else: m.blend_method = "BLEND"
    return m

def uv_plane(name, w, h, mat, loc, rot_z=0.0, tilt=0.0, parent=None):
    """vertical panel w x h facing three +z before rotation (rot_z = three yaw), centre at loc (blender coords)"""
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2)], [], [(0, 1, 2, 3)])
    me.uv_layers.new(); uv = me.uv_layers[0].data
    for i, c in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]): uv[i].uv = c
    me.update(); o = obj(name, me, mat, loc, parent); o.rotation_euler = (tilt, 0, rot_z); return o

def P3(name, file, w, h, x, y, z, yaw=0.0, emit=0.3, off=0.02, parent=None, rough=0.7):
    """a painted sign / poster in three coords facing three yaw (0 = +z)"""
    nrm = Vector((math.sin(yaw), -math.cos(yaw), 0))
    return uv_plane(name, w, h, tex_mat("m_" + name + file, file, emit=emit, rough=rough), T(x, y, z) + nrm * off, yaw, parent=parent)

def B3(name, x0, x1, y0, y1, z0, z1, mat, bev=0.0, parent=None):
    """axis box in THREE coords"""
    return box(name, x0, x1, -z1, -z0, y0, y1, mat, parent, bev)

def CYLY(name, r, x, y0, y1, z, mat, verts=16, parent=None):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=y1 - y0, location=(x, -z, (y0 + y1) / 2))
    o = bpy.context.object; o.name = name; o.data.materials.append(mat); bpy.ops.object.shade_smooth()
    if parent: o.parent = parent
    return o

def coll_of(objs, name):
    c = bpy.data.collections.new("K_" + name)
    for o in objs:
        for u in o.users_collection: u.objects.unlink(o)
        c.objects.link(o)
    return c

def place_coll(coll, x3, y3, z3, yaw=0.0, s=1.0):
    e = bpy.data.objects.new(coll.name, None); e.instance_type = "COLLECTION"; e.instance_collection = coll
    e.location = T(x3, y3, z3); e.rotation_euler = (0, 0, yaw); e.scale = (s, s, s); bpy.context.collection.objects.link(e); return e

def area_light(name, x3, y3, z3, size, power, col="#fff4e6", size_y=None):
    L = bpy.data.lights.new(name, "AREA"); L.energy = power; L.color = hexc(col); L.shape = "RECTANGLE"; L.size = size; L.size_y = size_y or size
    o = obj(name, L, None, T(x3, y3, z3)); o.rotation_euler = (0, 0, 0); return o

def point_light(name, x3, y3, z3, power, col="#ffe6c0", r=0.3):
    L = bpy.data.lights.new(name, "POINT"); L.energy = power; L.color = hexc(col); L.shadow_soft_size = r
    return obj(name, L, None, T(x3, y3, z3))

# ------------------------------------------------------------------------------------------------ materials
asph = pbr("asph", "Asphalt031", scale=3.0, tint=hexc("#b4b4bc"))
pave = pbrb("pave", "Concrete034", 1.4, tint=hexc("#e6e2da"))
grassm = pbr("grassH", "Grass004", scale=4.0, tint=hexc("#c4e488"), normal_strength=0.5)
brick = pbrb("brick", "Bricks075A", 1.4, tint=hexc("#f4c8b0"), normal_strength=1.4)
brick2 = pbrb("brick2", "Bricks075A", 1.4, tint=hexc("#e8d0b8"), normal_strength=1.4)
plaster = pbrb("plaster", "PaintedPlaster017", 2.0, tint=hexc("#fbf3e4"))
plasterB = pbrb("plasterB", "PaintedPlaster017", 2.0, tint=hexc("#cfe2f2"))
plasterG = pbrb("plasterG", "PaintedPlaster017", 2.0, tint=hexc("#f2e2b8"))
rooft = pbrb("roof", "RoofingTiles006", 1.6, tint=hexc("#a8969a"))
woodfl = pbrb("woodfl", "WoodFloor051", 1.8)
tiles = pbrb("tiles", "Tiles074", 1.8, tint=hexc("#f4f0e8"), normal_strength=0.4)
carpet = pbrb("carpet", "Carpet016", 1.2, tint=hexc("#8a9ac8"))
woodm = pbrb("wood", "Wood049", 1.0)
metal = pbrb("metal", "Metal032", 1.2, tint=hexc("#c8ccd4"))
conc = pbrb("conc", "Concrete031", 3.0, tint=hexc("#d8d6d0"))
white = flat("white", hexc("#f4f2ec"), 0.45); upvc = flat("upvc", hexc("#fbfbf8"), 0.35)
ink = flat("inkdark", hexc("#2a2a32"), 0.6); black = flat("black", hexc("#1d1b22"), 0.55)
winglass = flat("winglass", hexc("#2c3e58"), 0.08, coat=0.6)
lampm = flat("lampm", hexc("#fff6dc"), 0.3, emit=hexc("#fff2cc"))
redm = flat("redm", hexc("#d8262e"), 0.4, coat=0.4); bluem = flat("bluem", hexc("#2f5fb0"), 0.45)
greenD = flat("greenD", hexc("#2f5a3a"), 0.35, coat=0.6); cream = flat("cream", hexc("#efe6d2"), 0.5)
grey = flat("grey", hexc("#8a8f9a"), 0.5, 0.3); steel = flat("steel", hexc("#c4c8d0"), 0.3, 0.8)

# ================================================================================================ DRIVE (x 0): Workington street
plane("road", -90, 90, -15, -8, 0.0, asph)
B3("paveN", -90, 90, 0.0, 0.12, 6.6, 8.0, pave); B3("paveS", -90, 90, 0.0, 0.12, 15.0, 16.4, pave)
B3("kerbN", -90, 90, 0.0, 0.14, 7.85, 8.0, conc); B3("kerbS", -90, 90, 0.0, 0.14, 15.0, 15.15, conc)
for x in range(-88, 90, 6): B3("roadline", x, x + 3, 0.0, 0.006, 11.42, 11.58, white)
plane("gardens", -90, 90, -6.6, 60, 0.05, grassm)                # front gardens and behind (three z -60..6.6)
plane("gardensS", -90, 90, -60, -16.4, 0.05, grassm)              # opposite side
B3("drive", 1.8, 5.4, 0.0, 0.1, -6.0, 6.6, conc)
def semi_pair(cx, zf, facing, door_cols, seed):
    """a pair of 1930s semis: front wall at zf (facing +z if facing=1 else -z), 14 m wide, brick, hipped roof, white windows"""
    s = facing; x0, x1 = cx - 14, cx + 14; zb = zf - s * 10
    zz0, zz1 = min(zf, zb), max(zf, zb)
    B3("house", x0, x1, 0, 5.6, zz0, zz1, brick if seed % 2 == 0 else brick2, bev=0.02)
    B3("eaves", x0 - 0.3, x1 + 0.3, 5.6, 5.8, zz0 - 0.3, zz1 + 0.3, white)
    me = bpy.data.meshes.new("roof"); zc = (zz0 + zz1) / 2; h = 3.4
    vs = [(x0 - 0.3, -(zz0 - 0.3), 5.8), (x1 + 0.3, -(zz0 - 0.3), 5.8), (x1 + 0.3, -(zz1 + 0.3), 5.8), (x0 - 0.3, -(zz1 + 0.3), 5.8), (x0 + 3, -zc, 5.8 + h), (x1 - 3, -zc, 5.8 + h)]
    me.from_pydata(vs, [], [(0, 1, 5, 4), (2, 3, 4, 5), (1, 2, 5), (3, 0, 4)]); me.update(); obj("roof", me, rooft)
    for k, sx in enumerate((-1, 1)):
        hx = cx + sx * 7
        # door (two semis: doors near the party wall), porch canopy, windows up and down
        dx = cx + sx * 1.6
        B3("door", dx - 0.5, dx + 0.5, 0.1, 2.15, zf + s * 0.0, zf + s * 0.06, flat("door%d" % seed, hexc(door_cols[k]), 0.4, coat=0.5))
        B3("doorframe", dx - 0.62, dx + 0.62, 0.1, 2.27, zf - s * 0.01, zf + s * 0.03, upvc)
        B3("canopy", dx - 0.9, dx + 0.9, 2.45, 2.55, zf, zf + s * 0.9, white)
        CYLY("knob", 0.04, dx + sx * 0.32, 1.0, 1.06, zf + s * 0.09, steel)
        for wx, wy, ww, wh in ((hx + sx * 2.6, 0.9, 2.4, 1.4), (hx + sx * 2.6, 3.4, 2.0, 1.2), (dx, 3.4, 1.0, 1.0), (hx - sx * 1.6, 3.4, 1.6, 1.2)):
            B3("winframe", wx - ww / 2 - 0.1, wx + ww / 2 + 0.1, wy - 0.1, wy + wh + 0.1, zf - s * 0.0, zf + s * 0.06, upvc)
            B3("winglass", wx - ww / 2, wx + ww / 2, wy, wy + wh, zf + s * 0.04, zf + s * 0.07, winglass)
            B3("winbar", wx - 0.03, wx + 0.03, wy, wy + wh, zf + s * 0.06, zf + s * 0.09, upvc)
            B3("sill", wx - ww / 2 - 0.2, wx + ww / 2 + 0.2, wy - 0.18, wy - 0.06, zf, zf + s * 0.18, flat("sill", hexc("#d9d4c8"), 0.6))
        B3("chimney", hx - 0.5, hx + 0.5, 7.0, 10.2, zc - 0.5, zc + 0.5, brick)
        for cpx in (-0.2, 0.2): CYLY("pot", 0.12, hx + cpx, 10.2, 10.7, zc, flat("pot", hexc("#b8603e"), 0.7))
semi_pair(0, -6.0, 1, ["#2f5fb0", "#7a2a32"], 0)
semi_pair(-30, -6.0, 1, ["#3f7a4a", "#f2c230"], 1)
semi_pair(30, -6.0, 1, ["#d8262e", "#f4f1ea"], 2)
for k in range(-2, 3): semi_pair(k * 30, 24.0, -1, [["#2f5fb0", "#f2c230", "#3f7a4a", "#7a2a32", "#d8262e"][(k + 2) % 5], "#f4f1ea"], k + 5)
# Dave's garage at the end of the drive (up-and-over door)
B3("garage", 1.6, 5.6, 0, 2.9, -10, -6.0, brick2, bev=0.02); B3("garroof", 1.4, 5.8, 2.9, 3.05, -10.2, -5.8, flat("felt", hexc("#4a4552"), 0.8))
B3("gardoor", 2.0, 5.2, 0.1, 2.4, -6.0, -5.94, flat("gardoor", hexc("#f2f0ea"), 0.35, coat=0.3))
for y in (0.6, 1.2, 1.8): B3("garrib", 2.0, 5.2, y, y + 0.03, -5.94, -5.92, flat("rib", hexc("#d9d6cf"), 0.4))
# garden walls along the pavement (gaps for the drives) and low walls between gardens
for x0, x1 in ((-44, -28.2), (-24.6, -2.3), (-0.9, 1.0), (5.4, 28.2), (31.8, 44)):
    if x1 - x0 > 0.2: B3("gwall", x0, x1, 0, 0.85, 6.3, 6.55, brick); B3("gcope", x0 - 0.04, x1 + 0.04, 0.85, 0.95, 6.26, 6.6, flat("cope", hexc("#d9d4c8"), 0.6))
for x in (-14.0, 14.0): B3("sidewall", x - 0.12, x + 0.12, 0, 0.85, -6.0, 6.3, brick)
for x0, x1 in ((-44, -1.0), (1.0, 44)): pass
# street lamps, a telegraph pole, a post box, a parked car opposite
lampc = []
lampc.append(CYLY("lpole", 0.08, 0, 0, 6.2, 0, grey)); lampc.append(B3("larm", -0.05, 0.05, 6.1, 6.2, -1.2, 0, grey)); lampc.append(B3("lhead", -0.22, 0.22, 5.95, 6.12, -1.5, -0.95, lampm))
LAMP = coll_of(lampc, "lamp")
for x in range(-72, 80, 24): place_coll(LAMP, x + 9, 0.12, 7.4, math.pi, 1.0); place_coll(LAMP, x - 3, 0.12, 15.6, 0.0, 1.0)
CYLY("pbox", 0.28, -4.5, 0.12, 1.6, 7.3, redm, 24); CYLY("pboxtop", 0.31, -4.5, 1.6, 1.75, 7.3, redm, 24)
def make_car_parked(x, z, col, yaw):
    r = bpy.data.objects.new("pcar", None); bpy.context.collection.objects.link(r); paint = flat("pc" + col, hexc(col), 0.3, coat=0.7)
    box("pcb", -0.85, 0.85, -2.1, 2.1, 0.35, 1.0, paint, r, 0.08); box("pct", -0.78, 0.78, -1.2, 0.9, 1.0, 1.45, winglass, r, 0.06)
    for wx, wy in ((-0.78, 1.35), (0.78, 1.35), (-0.78, -1.35), (0.78, -1.35)):
        bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.3, depth=0.2, location=(wx, wy, 0.3), rotation=(0, math.pi / 2, 0)); c = bpy.context.object; c.parent = r; c.data.materials.append(black)
    r.location = T(x, 0, z); r.rotation_euler = (0, 0, yaw)
make_car_parked(-34.0, 13.9, "#c8352f", math.pi / 2); make_car_parked(17.0, 14.0, "#3f6fb5", -math.pi / 2); make_car_parked(-24, 9.1, "#e8e4dc", math.pi / 2)
# gardens: hedges, trees, flowers, a washing line; distant fells
for i in range(160):
    x = -44 + 88 * hh(i, 61); z = -5.6 + 11.5 * hh(i, 62)
    if 1.0 < x < 8.5 or (abs(x) % 30 < 1.4 and z > 3): continue
    q = hh(i, 63); nm = "Bush_Common_Flowers" if q < 0.3 else "Bush_Common" if q < 0.55 else "Flower_3_Group" if q < 0.8 else "Flower_4_Group"
    inst(nm, x, z, 0.5 + 0.4 * hh(i, 64), hh(i, 65) * 6.28)
for i in range(46):
    x = -44 + 88 * (i / 46) + 0.6 * hh(i, 66); inst("Bush_Common", x, 6.0, 0.9 + 0.3 * hh(i, 67), hh(i, 68) * 6.28)
for x, z in ((-9, 1.0), (10, -1.5), (-21, 2.5), (22, 0.5), (-3.5, 20.5), (12, 21), (-16, 19.5)): inst("CommonTree_%d" % (1 + int(abs(x)) % 4), x, z, 6 + 2 * hh(int(x), 3), hh(int(z), 4) * 6.28)
fell = flat("fell", hexc("#7fa060"), 0.9)
for i in range(10):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, location=(-300 + 70 * i, -260 - 40 * (i % 3), -10)); h_ = bpy.context.object
    h_.scale = (90, 60, 40 + 18 * (i % 3)); h_.data.materials.append(fell); bpy.ops.object.shade_smooth()

exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.path.join(OUT_ROOT, "..", "..", "blender"), "props_hoover.py"), encoding="utf-8").read())
# ================================================================================================ SHOP (x 2000) + its street
X = 2000
plane("s_road", X - 90, X + 90, -12, -4, 0.0, asph)
B3("s_pave", X - 90, X + 90, 0.0, 0.12, 0.0, 4.0, pave); B3("s_kerb", X - 90, X + 90, 0, 0.14, 3.85, 4.0, conc); B3("s_pave2", X - 90, X + 90, 0, 0.12, 12, 14, pave)
for x in range(-88, 90, 6): B3("s_line", X + x, X + x + 3, 0, 0.006, 7.92, 8.08, white)
B3("s_floor", X - 8, X + 8, 0.0, 0.13, -14, 0, tiles)
B3("s_wallW", X - 8.3, X - 8.0, 0, 4.4, -14, 0, plasterB); B3("s_wallE", X + 8.0, X + 8.3, 0, 4.4, -14, 0, plasterB); B3("s_wallB", X - 8.3, X + 8.3, 0, 4.4, -14.3, -14, plasterB)
B3("s_ceilband", X - 8.3, X + 8.3, 4.4, 4.6, -14.3, 0, white)
# shop front: brick piers, stall riser, glass, door gap, fascia, upper storey
for x0, x1 in ((-8.3, -7.4), (-1.1, -1.0), (1.0, 1.1), (7.4, 8.3)): B3("s_pier", X + x0, X + x1, 0, 4.4, -0.3, 0.0, brick)
for x0, x1 in ((-7.4, -1.1), (1.1, 7.4)):
    B3("s_riser", X + x0, X + x1, 0, 0.6, -0.3, 0.0, brick)
    B3("s_glass", X + x0, X + x1, 0.6, 3.5, -0.08, -0.04, glass_mat("shopglass", "#cfe4f2", 0.12))
    B3("s_frame", X + x0, X + x1, 3.5, 3.6, -0.3, 0.02, flat("sframe", hexc("#1f2a44"), 0.5))
B3("s_fasciaB", X - 8.3, X + 8.3, 3.6, 4.7, -0.3, 0.05, flat("fasciaB", hexc("#1f2a44"), 0.5))
P3("s_fascia", "fascia.png", 9.5, 1.0, X, 4.15, 0.06, 0.0, emit=0.35)
B3("s_upper", X - 8.3, X + 8.3, 4.7, 9.0, -14.3, 0.0, brick2)
for wx in (-5, 0, 5):
    B3("s_uwin", X + wx - 1.0, X + wx + 1.0, 5.6, 7.6, 0.0, 0.05, winglass); B3("s_uwf", X + wx - 1.1, X + wx + 1.1, 5.5, 5.6, 0.0, 0.12, white)
P3("s_banner", "banner.png", 6.0, 1.5, X - 4.25, 2.55, -0.2, 0.0, emit=0.45)
P3("s_poster1", "poster_usa.png", 1.3, 1.73, X + 4.0, 2.0, -0.2, 0.0, emit=0.3)
P3("s_poster2", "poster_price.png", 1.5, 1.0, X + 6.0, 1.4, -0.2, 0.0, emit=0.3)
# inside: banner over the counter, posters on the walls, the counter and till, shelves of cartons, vacuums on stands, washers
P3("s_banner2", "banner.png", 7.2, 1.8, X, 3.45, -9.6, 0.0, emit=0.5)
P3("s_sale", "sale.png", 6.0, 1.5, X, 3.3, -13.95, 0.0, emit=0.3)
for z in (-3.5, -7.0, -10.5): P3("s_pw", "poster_usa.png", 1.1, 1.47, X - 7.98, 2.6, z, math.pi / 2, emit=0.3); P3("s_pe", "poster_price.png", 1.4, 0.93, X + 7.98, 2.6, z, -math.pi / 2, emit=0.3)
B3("s_counter", X - 3.0, X + 3.0, 0, 1.0, -8.3, -7.6, woodm, bev=0.02); B3("s_ctop", X - 3.1, X + 3.1, 1.0, 1.06, -8.4, -7.5, flat("ctop", hexc("#e8e4dc"), 0.3))
B3("s_till", X - 2.2, X - 1.5, 1.06, 1.36, -8.2, -7.7, flat("till", hexc("#3a3d47"), 0.4)); B3("s_tilld", X - 2.15, X - 1.55, 1.36, 1.5, -8.1, -7.95, flat("tilld", hexc("#3a6a4a"), 0.2, emit=hexc("#6aff8a")))
carton = tex_mat("carton", "carton.png", rough=0.8, cull=False); cartonW = tex_mat("cartonW", "carton_wash.png", rough=0.6, cull=False)
CART = coll_of([B3("cart", -0.25, 0.25, 0, 0.62, -0.22, 0.22, carton)], "carton")
CARTW = coll_of([B3("cartw", -0.32, 0.32, 0, 0.9, -0.32, 0.32, cartonW)], "cartonw")
shelf = flat("shelf", hexc("#e8e4dc"), 0.5)
for sx in (-1, 1):
    xw = X + sx * 7.55
    B3("s_shelfback", xw - 0.45, xw + 0.45, 0, 3.0, -13.5, -1.0, shelf)
    for y in (0.0, 0.95, 1.9):
        B3("s_shelf", xw - 0.45, xw + 0.45, y, y + 0.05, -13.5, -1.0, shelf)
        for k in range(22): place_coll(CART, xw - sx * 0.1, y + 0.05, -13.2 + k * 0.55, 0.0 if k % 3 else 0.05)
vacp = []
vacp.append(B3("vbase", -0.22, 0.22, 0.0, 0.14, -0.2, 0.2, flat("vbase", hexc("#3a3d47"), 0.4), 0.03))
vacp.append(B3("vbody", -0.13, 0.13, 0.14, 0.82, -0.08, 0.1, redm, 0.05))
vacp.append(B3("vlabel", -0.09, 0.09, 0.4, 0.52, 0.1, 0.11, white))
vacp.append(CYLY("vhandle", 0.02, 0, 0.8, 1.15, 0.0, grey, 8)); vacp.append(B3("vgrip", -0.08, 0.08, 1.13, 1.18, -0.02, 0.02, black))
VAC = coll_of(vacp, "vac")
VAC = PROPS["vac"]   # v2: the detailed upright on the shop displays too
plinth = flat("plinth", hexc("#f2c230"), 0.5)
for r, z in enumerate((-3.0, -11.0)):
    for c, x in enumerate((-5.0, -2.0, 2.0, 5.0)):
        B3("s_plinth", X + x - 0.9, X + x + 0.9, 0.13, 0.45, z - 0.6, z + 0.6, plinth if (r + c) % 2 else flat("plinthR", hexc("#d8262e"), 0.5), 0.02)
        for k in range(3): place_coll(VAC, X + x - 0.55 + 0.55 * k, 0.45, z - 0.15 + 0.3 * (k % 2), 0.3 * (k - 1))
for k in range(9): place_coll(CARTW, X - 6.0 + k * 1.5, 0.13, -13.4, 0.0)
for x in range(-6, 7, 3): B3("s_fluor", X + x - 1.2, X + x + 1.2, 4.0, 4.08, -12, -1.5, lampm)
area_light("s_area", X, 4.3, -7, 15, 2600, "#fff6ea", 12)
# neighbouring shops and the far side of the street
for k, (x0, x1, col) in enumerate(((-38, -8.3, "#7a2a32"), (8.3, 30, "#2f5f6a"), (30, 60, "#5a6f3a"), (-60, -38, "#3a3d52"))):
    B3("s_nb", X + x0, X + x1, 0, 9.0 if k % 2 else 10.5, -14.3, -0.3, brick if k % 2 else brick2)
    B3("s_nbf", X + x0 + 0.3, X + x1 - 0.3, 3.6, 4.6, -0.32, -0.2, flat("nbf%d" % k, hexc(col), 0.5))
    for wx in range(int(x0) + 2, int(x1) - 2, 4): B3("s_nbw", X + wx, X + wx + 2.6, 0.6, 3.3, -0.33, -0.3, winglass); B3("s_nbu", X + wx + 0.3, X + wx + 2.3, 5.6, 7.6, -0.33, -0.3, winglass)
for k in range(8): B3("s_far", X - 60 + k * 15, X - 46 + k * 15, 0, 9 + 3 * (k % 3), 14, 24, brick if k % 2 else brick2)
for x in range(-50, 60, 20): place_coll(LAMP, X + x, 0.12, 3.6, math.pi, 1.0)

# ================================================================================================ FACTORY (x 4000)
X = 4000
B3("f_floor", X - 18, X + 18, -0.1, 0.0, -32, 8, conc)
B3("f_wallW", X - 18.3, X - 18, 0, 9, -32, 8, plasterG); B3("f_wallE", X + 18, X + 18.3, 0, 9, -32, 8, plasterG); B3("f_wallB", X - 18.3, X + 18.3, 0, 9, -32.3, -32, plasterG)
B3("f_wallF", X - 18.3, X + 18.3, 0, 9, 8, 8.3, plasterG)
for z in range(-28, 8, 6):
    for sx in (-1, 1): B3("f_win", X + sx * 17.98 - 0.02, X + sx * 17.98 + 0.02, 5.2, 8.2, z, z + 4, flat("fwin", hexc("#dfeeff"), 0.2, emit=hexc("#cfe6ff")))
P3("f_sign", "factory_sign.png", 6.4, 1.6, X, 5.2, -31.97, 0.0, emit=0.4)
P3("f_shift", "factory_shift.png", 3.0, 1.0, X - 6, 3.2, -31.97, 0.0, emit=0.3)
B3("f_beltframe", X - 0.6, X + 0.6, 0.72, 0.9, -30, 7, flat("fbelt", hexc("#3f6fb5"), 0.45))
B3("f_belt", X - 0.5, X + 0.5, 0.9, 0.94, -30, 7, flat("rubber", hexc("#2a2a30"), 0.8))
for z in range(-30, 8, 2):
    for sx in (-1, 1): B3("f_leg", X + sx * 0.5 - 0.05, X + sx * 0.5 + 0.05, 0, 0.72, z, z + 0.1, grey)
for z in range(-26, 6, 7):
    for sx in (-1, 1): B3("f_mach", X + sx * 3.2 - 1.0, X + sx * 3.2 + 1.0, 0, 2.4, z, z + 2.6, flat("mach", hexc("#5a7a9a"), 0.45, 0.2), 0.05); B3("f_machlight", X + sx * 3.2 - 0.3, X + sx * 3.2 + 0.3, 2.4, 2.6, z + 1.0, z + 1.4, flat("machl", hexc("#ff8a2a"), 0.3, emit=hexc("#ff7a20")))
for k in range(10):
    sx = 1 if k % 2 else -1; z = -28 + 3.4 * k
    for a in range(2):
        for b in range(3): place_coll(CART, X + sx * 13.5 + a * 0.55, 0.0 + b * 0.62, z, 0.0)
for z in range(-28, 8, 6): B3("f_lamp", X - 1.0, X + 1.0, 6.4, 6.5, z, z + 0.4, lampm); B3("f_lampwire", X - 0.01, X + 0.01, 6.5, 9, z + 0.2, z + 0.21, black)
area_light("f_area", X, 8.8, -12, 30, 5200, "#eef4ff", 36)

# ================================================================================================ OFFICE (x 6000)
X = 6000
B3("o_floor", X - 5, X + 5, -0.1, 0.0, -6, 7, carpet)
B3("o_wallW", X - 5.3, X - 5.0, 0, 3.6, -6, 7, plasterG); B3("o_wallE", X + 5.0, X + 5.3, 0, 3.6, -6, 7, plasterG); B3("o_wallF", X - 5.3, X + 5.3, 0, 3.6, 7, 7.3, plasterG)
B3("o_wallB1", X - 5.3, X + 5.3, 0, 0.8, -6.3, -6.0, plasterG); B3("o_wallB2", X - 5.3, X + 5.3, 3.0, 3.6, -6.3, -6.0, plasterG)
for x in (-5.3, -1.6, 1.6, 4.9): B3("o_mullion", X + x, X + x + 0.4, 0.8, 3.0, -6.3, -6.0, plasterG)
uv_plane("o_view", 16, 6, tex_mat("o_view", "view_town.png", emit=1.0, rough=1.0), T(X, 1.9, -9.0))
P3("o_sign", "office_sign.png", 3.2, 0.8, X - 4.98, 2.5, -1.0, math.pi / 2, emit=0.3)
P3("o_chart", "office_chart.png", 1.6, 1.2, X + 4.98, 1.9, -2.0, -math.pi / 2, emit=0.3)
B3("o_desk", X - 1.3, X + 1.3, 0.0, 0.75, -2.45, -1.55, woodm, bev=0.02); B3("o_desktop", X - 1.4, X + 1.4, 0.75, 0.8, -2.55, -1.45, flat("leather", hexc("#3a5a3a"), 0.5))
B3("o_chair", X - 0.35, X + 0.35, 0, 1.3, -3.4, -3.0, flat("chair", hexc("#2a2a30"), 0.6), 0.05)
B3("o_phone", X + 0.7, X + 1.05, 0.8, 0.92, -2.3, -2.05, redm, 0.02); B3("o_lamp", X - 1.1, X - 1.0, 0.8, 1.25, -2.3, -2.2, steel)
for k in range(4): B3("o_cab", X + 3.6, X + 4.8, 0, 1.4, -5.6 + k * 1.3, -4.5 + k * 1.3, flat("cab", hexc("#a8acb6"), 0.4, 0.3), 0.02)
for k in range(3):
    for j in range(5): B3("o_files", X - 4.8, X - 4.4, 0.8 + 0.5 * k, 1.2 + 0.5 * k, -5.0 + j * 0.42, -4.66 + j * 0.42, flat("files%d" % ((k + j) % 3), hexc(["#d8262e", "#2f5fb0", "#f2c230"][(k + j) % 3]), 0.6))
B3("o_shelfw", X - 4.95, X - 4.35, 0, 2.4, -5.3, -2.8, woodm)
for k in range(6): B3("o_stack", X - 3.6 + 0.5 * (k % 3), X - 3.2 + 0.5 * (k % 3), 0, 0.4 + 0.25 * k, 4.0 + 0.7 * (k // 3), 4.5 + 0.7 * (k // 3), flat("paper", hexc("#fbf8ee"), 0.8))
inst("Bush_Common", X + 4.4, 5.5, 1.2, 0.5)
area_light("o_area", X, 3.5, 0.5, 8, 900, "#fff0dc", 10)

# ================================================================================================ KITCHEN (x 8000)
X = 8000
B3("k_floor", X - 4, X + 4, -0.1, 0.0, -4, 4, tiles)
B3("k_wallB", X - 4.3, X + 4.3, 0, 1.25, -4.3, -4.0, plasterG); B3("k_wallB2", X - 4.3, X + 4.3, 2.35, 2.8, -4.3, -4.0, plasterG)
B3("k_wallB3", X - 4.3, X - 2.6, 1.25, 2.35, -4.3, -4.0, plasterG); B3("k_wallB4", X - 0.4, X + 4.3, 1.25, 2.35, -4.3, -4.0, plasterG)
B3("k_wallW", X - 4.3, X - 4.0, 0, 2.8, -4, 4, plasterG); B3("k_wallE", X + 4.0, X + 4.3, 0, 2.8, -4, 4, plasterG); B3("k_wallF", X - 4.3, X + 4.3, 0, 2.8, 4.0, 4.3, plasterG)
uv_plane("k_view", 8, 4, tex_mat("k_view", "view_garden.png", emit=1.0, rough=1.0), T(X - 1.5, 1.6, -6.5))
B3("k_winframe", X - 2.6, X - 0.4, 1.25, 1.31, -4.1, -3.9, upvc); B3("k_winbar", X - 1.53, X - 1.47, 1.25, 2.35, -4.1, -3.95, upvc)
tilesW = pbrb("tilesW", "Tiles074", 0.9, tint=hexc("#dff2ff"), normal_strength=0.4)
B3("k_splash", X - 3.98, X + 0.9, 0.9, 1.25, -3.99, -3.96, tilesW)
units = flat("units", hexc("#7a9a6a"), 0.45, coat=0.2); work = flat("work", hexc("#e8dcc4"), 0.35)
B3("k_units", X - 3.95, X + 1.0, 0, 0.88, -3.98, -3.38, units, 0.01); B3("k_worktop", X - 4.0, X + 1.05, 0.88, 0.93, -4.0, -3.33, work)
for k in range(8): B3("k_handle", X - 3.6 + k * 0.6, X - 3.4 + k * 0.6, 0.72, 0.75, -3.37, -3.34, steel)
B3("k_upper", X - 3.95, X - 2.7, 1.5, 2.3, -3.98, -3.65, units, 0.01); B3("k_upper2", X - 0.3, X + 1.0, 1.5, 2.3, -3.98, -3.65, units, 0.01)
B3("k_sink", X - 2.0, X - 1.0, 0.88, 0.94, -3.9, -3.45, steel); CYLY("k_tap", 0.025, X - 1.5, 0.93, 1.2, -3.85, steel, 8)
CYLY("k_kettle", 0.12, X - 0.4, 0.93, 1.2, -3.65, flat("kettle", hexc("#f4f1ea"), 0.3), 16)
B3("k_fridge", X + 2.6, X + 3.6, 0, 1.75, -3.98, -3.3, flat("fridge", hexc("#f4f2ec"), 0.3, coat=0.4), 0.04)
B3("k_table", X + 1.2, X + 2.6, 0, 0.75, 0.6, 1.8, woodm, 0.02)
# the front door in the west wall: a wooden door with a brass letterbox, a doormat, coats on hooks
B3("k_door", X - 4.0, X - 3.94, 0.0, 2.05, 1.0, 2.0, flat("fdoor", hexc("#2f5fb0"), 0.4, coat=0.4))
B3("k_letter", X - 3.94, X - 3.91, 1.0, 1.08, 1.3, 1.7, flat("brass", hexc("#d9a640"), 0.3, 1.0)); B3("k_dframe", X - 3.99, X - 3.93, 2.05, 2.12, 0.9, 2.1, white)
B3("k_mat", X - 3.9, X - 3.1, 0.0, 0.02, 1.0, 2.0, flat("mat", hexc("#a8743e"), 0.9))
for k in range(3): B3("k_coat", X - 3.98, X - 3.75, 1.0, 1.7, 2.4 + 0.4 * k, 2.7 + 0.4 * k, flat("coat%d" % k, hexc(["#3f5a3a", "#d8262e", "#2f3a5a"][k]), 0.8), 0.05)
area_light("k_area", X, 2.75, -0.5, 6, 650, "#fff0dc", 7)

# ================================================================================================ vehicles (three-local, nose to +z)
def make_van():
    root = bpy.data.objects.new("van", None); bpy.context.collection.objects.link(root)
    paint = flat("vanWhite", hexc("#f4f4f0"), 0.25, coat=0.7)
    def B(n, x0, x1, y0, y1, z0, z1, m, bev=0.03): return box(n, x0, x1, -z1, -z0, y0, y1, m, root, bev)
    B("vbody", -1.0, 1.0, 0.45, 2.6, -2.5, 1.3, paint, 0.08)
    B("vhood", -1.0, 1.0, 0.45, 1.35, 1.3, 2.45, paint, 0.1)
    me = bpy.data.meshes.new("wscreen"); me.from_pydata([(-0.95, -1.3, 2.55), (0.95, -1.3, 2.55), (0.95, -1.95, 1.38), (-0.95, -1.95, 1.38)], [], [(0, 1, 2, 3)]); me.update()
    obj("wscreen", me, winglass, parent=root)
    for sx in (-1, 1):
        me = bpy.data.meshes.new("cabside"); xx = sx * 1.001
        me.from_pydata([(xx, -1.3, 2.55), (xx, -1.3, 1.35), (xx, -1.95, 1.35), (xx, -1.95, 1.38)], [], [(0, 1, 2, 3)]); me.update(); obj("cabside", me, paint, parent=root)
        uv_plane("vwin", 0.62, 0.75, winglass, (sx * 1.006, -0.95, 1.95), rot_z=sx * math.pi / 2, parent=root)
        uv_plane("vdecal", 3.6, 1.29, decal_mat("vdecal2", "van_side2.png"), (sx * 1.006, 0.6, 1.62), rot_z=sx * math.pi / 2, parent=root)
        B("vmirror", sx * 1.0, sx * 1.0 + sx * 0.18, 1.8, 2.05, 1.15, 1.25, black, 0.01) if sx > 0 else B("vmirror", -1.18, -1.0, 1.8, 2.05, 1.15, 1.25, black, 0.01)
        bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.44, depth=0.08, location=(sx * 0.99, -1.62, 0.42), rotation=(0, math.pi / 2, 0)); c = bpy.context.object; c.parent = root; c.data.materials.append(black)
        bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.44, depth=0.08, location=(sx * 0.99, 1.6, 0.42), rotation=(0, math.pi / 2, 0)); c = bpy.context.object; c.parent = root; c.data.materials.append(black)
    uv_plane("vback", 1.9, 1.75, tex_mat("vback", "van_back.png", emit=0.15, rough=0.3), (0, 2.508, 1.5), rot_z=math.pi, parent=root)
    B("vbumpF", -1.02, 1.02, 0.38, 0.62, 2.4, 2.58, black, 0.03); B("vbumpR", -1.02, 1.02, 0.38, 0.6, -2.62, -2.45, black, 0.03)
    B("vgrille", -0.6, 0.6, 0.7, 1.15, 2.44, 2.47, black, 0.0)
    for sx in (-1, 1): B("vlamp", sx * 0.62 - 0.2, sx * 0.62 + 0.2, 0.85, 1.1, 2.44, 2.48, lampm, 0.01); B("vtail", sx * 0.88 - 0.08, sx * 0.88 + 0.08, 1.0, 1.4, -2.53, -2.5, flat("tail", hexc("#c81e24"), 0.3, emit=hexc("#601014")), 0.0)
    B("vroofbar", -0.8, 0.8, 2.6, 2.66, -2.0, 0.8, grey, 0.01)
    wheels = []
    for x, z in ((-0.88, 1.6), (0.88, 1.6), (-0.88, -1.62), (0.88, -1.62)):
        w = bpy.data.objects.new("vwheel", None); bpy.context.collection.objects.link(w); w.parent = root; w.location = (x, -z, 0.36)
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.36, depth=0.24, location=(0, 0, 0), rotation=(0, math.pi / 2, 0)); c = bpy.context.object; c.parent = w; c.data.materials.append(black); bpy.ops.object.shade_smooth()
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.2, depth=0.25, location=(0, 0, 0), rotation=(0, math.pi / 2, 0)); c = bpy.context.object; c.parent = w; c.data.materials.append(steel)
        box("vnut", -0.13, 0.13, -0.03, 0.03, -0.12, 0.12, black, w, 0)
        wheels.append(w)
    return root, wheels

def make_truck():
    root = bpy.data.objects.new("truck", None); bpy.context.collection.objects.link(root)
    def B(n, x0, x1, y0, y1, z0, z1, m, bev=0.03): return box(n, x0, x1, -z1, -z0, y0, y1, m, root, bev)
    B("tchassis", -1.05, 1.05, 0.5, 0.95, -4.2, 4.1, black, 0.02)
    B("tcab", -1.2, 1.2, 0.95, 3.05, 2.45, 4.2, greenD, 0.12)
    B("tscreen", -1.05, 1.05, 1.95, 2.85, 4.2, 4.23, winglass, 0.0)
    for sx in (-1, 1):
        uv_plane("tcabwin", 0.9, 0.8, winglass, (sx * 1.206, -3.6, 2.4), rot_z=sx * math.pi / 2, parent=root)
        uv_plane("tside", 6.1, 2.3, tex_mat("tside", "truck_side.png", emit=0.12, rough=0.5), (sx * 1.258, 0.95, 2.3), rot_z=sx * math.pi / 2, parent=root)
    B("tbox", -1.25, 1.25, 0.95, 3.75, -4.2, 2.3, cream, 0.06)
    B("troof", -1.28, 1.28, 3.75, 3.85, -4.25, 2.35, flat("troof", hexc("#7a2a32"), 0.5), 0.03)
    # the horse window on the near (-x) side, open, dark inside, with a wooden half-door below it
    B("twin", -1.3, -1.24, 2.0, 3.05, 0.85, 2.05, flat("thole", hexc("#5a3a22"), 0.9), 0.0)
    B("twinframe", -1.33, -1.25, 1.92, 2.0, 0.78, 2.12, flat("trim", hexc("#7a2a32"), 0.5), 0.0)
    B("tramp", -1.1, 1.1, 1.0, 3.5, -4.25, -4.2, flat("ramp", hexc("#d9cdb2"), 0.6), 0.0)
    for y in (1.6, 2.3, 3.0): B("trib", -1.1, 1.1, y, y + 0.04, -4.27, -4.25, flat("rampr", hexc("#b8ab90"), 0.6), 0.0)
    B("tbump", -1.2, 1.2, 0.45, 0.8, 4.15, 4.4, black, 0.03); B("tgrille", -0.8, 0.8, 1.1, 1.8, 4.2, 4.24, black, 0.0)
    for sx in (-1, 1): B("tlamp", sx * 0.9 - 0.18, sx * 0.9 + 0.18, 1.15, 1.45, 4.2, 4.26, lampm, 0.01)
    wheels = []
    for x, z in ((-1.05, 3.35), (1.05, 3.35), (-1.05, -1.6), (1.05, -1.6), (-1.05, -2.8), (1.05, -2.8)):
        w = bpy.data.objects.new("twheel", None); bpy.context.collection.objects.link(w); w.parent = root; w.location = (x, -z, 0.5)
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.5, depth=0.32, location=(0, 0, 0), rotation=(0, math.pi / 2, 0)); c = bpy.context.object; c.parent = w; c.data.materials.append(black); bpy.ops.object.shade_smooth()
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.27, depth=0.33, location=(0, 0, 0), rotation=(0, math.pi / 2, 0)); c = bpy.context.object; c.parent = w; c.data.materials.append(redm)
        box("tnut", -0.17, 0.17, -0.04, 0.04, -0.16, 0.16, black, w, 0)
        wheels.append(w)
    return root, wheels

def make_washer():
    root = bpy.data.objects.new("washer", None); bpy.context.collection.objects.link(root)
    def B(n, x0, x1, y0, y1, z0, z1, m, bev=0.02): return box(n, x0, x1, -z1, -z0, y0, y1, m, root, bev)
    wm = flat("washWhite", hexc("#f7f7f4"), 0.25, coat=0.5)
    B("wbody", -0.3, 0.3, 0.0, 0.86, -0.3, 0.3, wm, 0.03)
    B("wpanel", -0.29, 0.29, 0.72, 0.85, 0.29, 0.31, flat("wpanel", hexc("#d9dde4"), 0.3), 0.0)
    for k in range(3): bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.03, depth=0.03, location=(-0.18 + 0.1 * k, -0.315, 0.785), rotation=(math.pi / 2, 0, 0)); c = bpy.context.object; c.parent = root; c.data.materials.append(grey)
    B("wlogo", 0.06, 0.26, 0.76, 0.81, 0.31, 0.315, redm, 0.0)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.19, minor_radius=0.035, location=(0, -0.31, 0.42), rotation=(math.pi / 2, 0, 0)); c = bpy.context.object; c.parent = root; c.data.materials.append(steel)
    bpy.ops.mesh.primitive_circle_add(vertices=32, radius=0.17, fill_type="NGON", location=(0, -0.305, 0.42), rotation=(math.pi / 2, 0, 0)); c = bpy.context.object; c.parent = root; c.data.materials.append(flat("wglass", hexc("#6a8ab0"), 0.05, coat=1.0))
    B("wfeet", -0.28, 0.28, 0.0, 0.03, -0.28, 0.28, black, 0.0)
    return root, []

VEHICLES = {"van": make_van(), "truck": make_truck(), "washer": make_washer()}

# ------------------------------------------------------------------------------------------------ colour moods per set
# (sun elevation, azimuth in degrees, sun colour, sun strength, sky strength)
MOOD = {"drive": (46, 150, "#fff1d8", 4.4, 0.95), "street": (44, 200, "#fff0d8", 4.2, 0.95), "shop": (72, 170, "#fff6e8", 3.4, 0.9),
        "factory": (66, 110, "#e8f0ff", 3.2, 0.8), "office": (38, 10, "#ffd9a8", 3.6, 0.85), "kitchen": (62, 160, "#fff0dc", 3.6, 0.9)}
SID_SET = {}
for fr_ in data["frames"]: SID_SET[fr_["id"]] = fr_.get("set", "drive")
def mood_of(sid):
    return SID_SET.get(sid, "drive")
