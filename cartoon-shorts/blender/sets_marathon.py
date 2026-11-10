# The 1904 marathon sets for toonrender.py (exec'd inside it: uses its helpers pbr, flat, hexc, box, plane, obj, T).
# Three.js coordinates in comments (x, y up, z); Blender = (x, -z, y). Mirrors src/videos/marathon/stlouis.ts + places.ts.
import bpy, math, os
from mathutils import Vector

WELL, MILE9, MILE19, HICKS = (-6.2, -60), (4.1, -110), (4.1, -164), (0, -220)
ORCHARD, DOGF, BOSTON, STADX = (9, -300), (-14, -350), -430, -2000
ASSETS = os.path.join(OUT_ROOT, "assets")
FIELD = 0.07

def tex_mat(name, file, emit=0.0, rough=0.7):
    m, n, l = mat_new(name); b = n["Principled BSDF"]
    m.use_backface_culling = True
    t = n.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(os.path.join(ASSETS, file), check_existing=True)
    l.new(t.outputs["Color"], b.inputs["Base Color"]); b.inputs["Roughness"].default_value = rough
    if emit:  # painted signs stay readable whatever the sun does
        l.new(t.outputs["Color"], b.inputs["Emission Color"]); b.inputs["Emission Strength"].default_value = emit
    return m

def uv_plane(name, w, h, mat, loc, rot_z=0.0, tilt=0.0):
    """vertical panel w x h facing -Y before rotation (like the cards), centre at loc (blender coords)"""
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2)], [], [(0, 1, 2, 3)])
    me.uv_layers.new(); uv = me.uv_layers[0].data
    for i, c in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]): uv[i].uv = c
    me.update(); o = obj(name, me, mat, loc); o.rotation_euler = (tilt, 0, rot_z); return o

def panel3(name, file, w, h, x3, y3, z3, yaw3, board="#9a7a54"):
    """a painted sign like stlouis.ts panel(): face toward three yaw (atan2 convention), a wooden board behind it"""
    nrm = Vector((math.sin(yaw3), -math.cos(yaw3), 0))  # the face normal (card convention: rot_z = three yaw)
    face = uv_plane(name, w, h, tex_mat("m_" + name, file, emit=0.35), T(x3, y3, z3) + nrm * 0.045)
    face.rotation_euler = (0, 0, yaw3)
    back = box(name + "_b", -w / 2 - 0.06, w / 2 + 0.06, 0.005, 0.07, -h / 2 - 0.06, h / 2 + 0.06, flat("board" + board, hexc(board), 0.8), bevel=0.01)
    back.location = T(x3, y3, z3); back.rotation_euler = (0, 0, yaw3)
    return face

def cyl(name, r, h, x3, z3, mat, y0=0.0, verts=12):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=h, location=(x3, -z3, y0 + h / 2))
    o = bpy.context.object; o.name = name; o.data.materials.append(mat); bpy.ops.object.shade_smooth(); return o

# ------------------------------------------------------------------------------------------------ the road
ZMIN, ZMAX = -480, 125
dirt = pbr("dirt", "Ground054", scale=2.2, tint=hexc("#f0d2a2"), normal_strength=1.6)
grass = pbr("grass", "Grass004", scale=2.6, tint=hexc("#c9e08c"), normal_strength=1.2)
plane("road", -700, 700, -ZMAX - 300, -ZMIN + 300, 0.0, dirt)
plane("fieldW", -700, -3.5, -ZMAX - 300, -ZMIN + 300, FIELD, grass)
plane("fieldE", 3.5, 700, -ZMAX - 300, -ZMIN + 300, FIELD, grass)
wood = flat("wood", hexc("#8a6440"), 0.75); woodD = flat("woodD", hexc("#5e4027"), 0.8)
# rail fences both sides (gaps at the well, the orchard and the dog field) as instanced bays
bay = bpy.data.collections.new("K_fencebay")
def to_bay(o):
    for c in o.users_collection: c.objects.unlink(o)
    bay.objects.link(o)
to_bay(box("post", -0.07, 0.07, -0.07, 0.07, 0, 1.2, woodD, bevel=0.02))
for hgt in (0.55, 1.0): to_bay(box("rail", -0.04, 0.04, -3.2, 0, hgt - 0.05, hgt + 0.05, wood, bevel=0.015))
def place_coll(coll, loc, rot=0.0, s=1.0):
    e = bpy.data.objects.new(coll.name, None); e.instance_type = "COLLECTION"; e.instance_collection = coll
    e.location = loc; e.rotation_euler = (0, 0, rot); e.scale = (s, s, s); bpy.context.collection.objects.link(e); return e
for sd in (-1, 1):
    x = sd * 4.6; z = -470.0
    while z < 120:
        skip = (sd < 0 and WELL[1] - 5 < z < WELL[1] + 5) or (sd > 0 and ORCHARD[1] - 30 < z < ORCHARD[1] + 12) or (sd < 0 and DOGF[1] - 25 < z < DOGF[1] + 25)
        if not skip: place_coll(bay, (x, -z, 0))
        z += 3.2
pole = bpy.data.collections.new("K_pole")
for o in (box("pole", -0.1, 0.1, -0.1, 0.1, 0, 7.5, woodD, bevel=0.03), box("arm", -1.0, 1.0, -0.07, 0.07, 6.8, 6.95, woodD)):
    for c in o.users_collection: c.objects.unlink(o)
    pole.objects.link(o)
z = -460.0
while z < 120: place_coll(pole, (-6.4, -z, 0)); z += 34
# the well, its WATER STOP sign, the mile posts
stone = flat("stone", hexc("#b9b2a2"), 0.9)
bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=1.0, depth=0.9, location=(WELL[0], -WELL[1], FIELD + 0.45)); w_ = bpy.context.object; w_.data.materials.append(stone)
bev = w_.modifiers.new("b", "BEVEL"); bev.width = 0.04; bev.segments = 2
bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.78, depth=0.02, location=(WELL[0], -WELL[1], FIELD + 0.62)); bpy.context.object.data.materials.append(flat("water", hexc("#2f4f6a"), 0.05))
for sd in (-1, 1): box("wpost", WELL[0] + sd * 0.95 - 0.08, WELL[0] + sd * 0.95 + 0.08, -WELL[1] - 0.08, -WELL[1] + 0.08, 0, 2.3, woodD, bevel=0.02)
roofm = flat("wellRoof", hexc("#8c3b2a"), 0.7)
for sd in (-1, 1):
    r = box("wroof", WELL[0] - 1.3, WELL[0] + 1.3, -WELL[1] - 0.05, -WELL[1] + 0.05, 2.45, 2.5, roofm); r.scale.y = 1.0
    r.dimensions = (2.6, 1.0, 0.05); r.location = (WELL[0], -WELL[1] + sd * 0.45, 2.48); r.rotation_euler = (sd * math.radians(31), 0, 0)
bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.15, depth=0.3, location=(WELL[0] + 0.6, -WELL[1] - 0.2, 1.08)); bpy.context.object.data.materials.append(flat("tin", hexc("#9aa3ab"), 0.35, 0.8))
box("signpost", WELL[0] + 2.03, WELL[0] + 2.17, -(WELL[1] + 1.8) - 0.07, -(WELL[1] + 1.8) + 0.07, 0, 1.9, woodD, bevel=0.02)
panel3("water", "water.png", 1.5, 0.98, WELL[0] + 2.1, 2.0, WELL[1] + 1.8, math.pi / 2 - 0.35)
for (mx, mz), f in ((MILE9, "mile9.png"), (MILE19, "mile19.png")):
    box("mpost", mx - 0.07, mx + 0.07, -mz - 0.07, -mz + 0.07, 0, 1.6, woodD, bevel=0.02)
    panel3("mile_" + f[:-4], f, 1.0, 0.56, mx, 1.75, mz, -math.pi / 2 + 0.5)
# farm house, barn, hills
box("farm", 36, 46, 42, 50, FIELD, 6, flat("farmWhite", hexc("#efe7d6"), 0.8), bevel=0.05)
bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=7.2, depth=3.2, location=(41, 46, 7.6), rotation=(0, 0, math.pi / 4)); bpy.context.object.scale = (1.0, 0.62, 1); bpy.context.object.data.materials.append(flat("farmRoof", hexc("#5a5058"), 0.7))
box("barn", -52, -40, 248, 262, FIELD, 7, flat("barnRed", hexc("#a8402e"), 0.75), bevel=0.05)
bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=9.2, depth=3.6, location=(-46, 255, 8.8), rotation=(0, 0, math.pi / 4)); bpy.context.object.scale = (0.9, 0.82, 1); bpy.context.object.data.materials.append(flat("farmRoof", hexc("#5a5058"), 0.7))
hillm = flat("hill", hexc("#93ad62"), 0.9)
for i in range(24):
    sd = 1 if i % 2 else -1; xh = sd * (170 + 90 * ((i * 37) % 7) / 7); yh = -160 + 760 * (i // 2) / 11
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, location=(xh, yh, -6))
    h = bpy.context.object; h.scale = (80 + 30 * (i % 3), 60, 24 + 12 * (i % 2)); h.data.materials.append(hillm); bpy.ops.object.shade_smooth()
# Boston 1905: banner over the road on two poles, brick blocks behind
poleB = flat("poleB", hexc("#4a4552"), 0.5, 0.3)
for sd in (-1, 1): cyl("bpole", 0.1, 4.7, sd * 2.4, BOSTON, poleB)
panel3("boston", "boston.png", 4.6, 1.23, 0, 4.0, BOSTON, 0.0, board="#f4f1ea")
for k in range(5):
    x0 = -26 + k * 10.5; hgt = 11 + (k % 2) * 3
    b = box("brick%d" % k, x0, x0 + 10, -(BOSTON - 22), -(BOSTON - 32), 0, hgt, tex_mat("brick%d" % k, "brick%d.png" % (k % 3), rough=0.85))
    # UVs on the box faces come from the cube primitive (0..1 per face): the facade texture tiles once per face
    box("cornice", x0 - 0.2, x0 + 10.2, -(BOSTON - 21.8), -(BOSTON - 32.2), hgt, hgt + 0.4, flat("cornice", hexc("#efe3c8"), 0.6), bevel=0.05)

# vegetation: Quaternius CC0 kit as linked instances along the whole road
def clear(x, z):
    return ((x < 0 and abs(z - WELL[1]) < 7 and x > -10) or (x > 0 and ORCHARD[1] - 30 < z < ORCHARD[1] + 12 and x < 16)
            or (x < 0 and abs(z - DOGF[1]) < 4 and x > -32) or (abs(z - HICKS[1]) < 1.5 and abs(x) < 4.4)
            or (3 < x < 6.2 and ((-26 < z < 2) or (12 < z < 48) or (-142 < z < -98) or (-282 < z < -266))))
for i in range(2600):
    sd = 1 if i % 2 else -1; z3 = ZMIN + (ZMAX - ZMIN) * hh(i, 11); x3 = sd * (3.75 + 10 * hh(i, 12) ** 2)
    if clear(x3, z3): continue
    q = hh(i, 13); nm = "Grass_Common_Tall" if q < .42 else "Grass_Wispy_Tall" if q < .6 else "Flower_3_Group" if q < .72 else "Flower_4_Group" if q < .82 else "Bush_Common_Flowers" if q < .88 else "Bush_Common"
    h = (0.65 + 0.5 * hh(i, 14)) if nm.startswith("Bush") else (0.4 + 0.3 * hh(i, 14)) if nm.startswith("Flower") else (0.7 + 0.6 * hh(i, 14))
    inst(nm, x3, z3, h, hh(i, 15) * 6.28)
for i in range(130):
    sd = 1 if i % 2 else -1; x3 = sd * (7.5 + 12 * hh(i, 41)); z3 = ZMIN + (ZMAX - ZMIN) * hh(i, 42)
    if clear(x3, z3): continue
    inst("CommonTree_%d" % (1 + i % 4), x3, z3, 5.5 + 4 * hh(i, 43), hh(i, 44) * 6.28)
for r in range(4):
    for c in range(4): inst("CommonTree_%d" % (1 + (r + c) % 4), ORCHARD[0] + 2 + c * 5.5, ORCHARD[1] + 8 - r * 6 + (c % 2) * 1.5, 4.6 + 0.4 * hh(r * 4 + c, 5), hh(r, c) * 6.28)
for i in range(420): inst("Pebble_Round_1", -3.3 + 6.6 * hh(i, 21), ZMIN + (ZMAX - ZMIN) * hh(i, 22), 0.06 + 0.05 * hh(i, 23), hh(i, 24) * 6.28, -0.01)
for i in range(80):
    sd = 1 if i % 2 else -1; x3 = sd * (5.5 + 12 * hh(i, 31)); z3 = ZMIN + (ZMAX - ZMIN) * hh(i, 32)
    if clear(x3, z3): continue
    inst("Rock_Medium_1", x3, z3, 0.3 + 0.45 * hh(i, 33), hh(i, 34) * 6.28)
straw = flat("straw", hexc("#e2bd5e"), 0.85)
for i in range(50):
    sd = 1 if i % 2 else -1; x3 = sd * (9 + 26 * hh(i, 51)); z3 = ZMIN + (ZMAX - ZMIN) * hh(i, 52)
    if clear(x3, z3): continue
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.75, depth=1.3, location=(x3, -z3, 0.82), rotation=(0, math.pi / 2, hh(i, 53) * 6.28))
    bpy.context.object.data.materials.append(straw); bpy.ops.object.shade_smooth()
# the fruit stall at the peaches: a striped awning on posts with a crate of peaches
awn = tex_mat("awning", "usflag.png", rough=0.8)
sx, sz = 5.6, -275
for dx in (-0.9, 0.9):
    for dz in (-0.6, 0.6): box("stallpost", sx + dx - 0.05, sx + dx + 0.05, -(sz + dz) - 0.05, -(sz + dz) + 0.05, 0, 2.2, woodD)
box("stalltop", sx - 1.1, sx + 1.1, -sz - 0.8, -sz + 0.8, 2.2, 2.3, flat("awnRed", hexc("#c8352f"), 0.7))
box("crate", sx - 0.8, sx + 0.8, -sz - 0.5, -sz + 0.5, 0.0, 0.9, wood, bevel=0.02)
peach = flat("peach", hexc("#f2a050"), 0.6)
for i in range(14):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.08, location=(sx - 0.6 + 0.18 * (i % 7), -sz - 0.2 + 0.2 * (i // 7), 0.98)); bpy.context.object.data.materials.append(peach)

# ------------------------------------------------------------------------------------------------ the stadium (x = -2000)
X = STADX
cinder = pbr("cinder", "Ground054", scale=1.6, tint=hexc("#ff9a70"), normal_strength=1.4)
plane("cinder", X - 300, X + 300, -300, 300, 0.0, cinder)
plane("infield", X + 4.6, X + 300, -300, 300, FIELD, grass)
box("chalk", X - 4.4, X + 4.4, -0.15, 0.15, 0.0, 0.03, flat("chalk", hexc("#f4f1ea"), 0.6))
standL = flat("standL", hexc("#c9a878"), 0.8); standD = flat("standD", hexc("#8a6a4a"), 0.8)
box("standwall", X - 7.2, X - 6.9, -70, 70, 0, 1.2, standL, bevel=0.02)
crowdm = tex_mat("crowd", "crowd.png", emit=0.15, rough=0.9)
me = bpy.data.meshes.new("bank")
me.from_pydata([(X - 7.6, 70, 1.2), (X - 7.6, -70, 1.2), (X - 19, -70, 8.6), (X - 19, 70, 8.6)], [], [(0, 1, 2, 3)])
me.uv_layers.new(); uv = me.uv_layers[0].data
for i, c in enumerate([(0, 0), (7, 0), (7, 1), (0, 1)]): uv[i].uv = c
me.update(); obj("bank", me, crowdm)
box("standback", X - 19.6, X - 19, -70, 70, 0, 11.5, standD)
for zz in range(-68, 69, 8): box("standpost", X - 7.8, X - 7.55, -zz - 0.12, -zz + 0.12, 1.2, 11, standD)
roof = box("standroof", X - 20, X - 7.0, -70, 70, 11.0, 11.25, flat("standRoof", hexc("#5a5058"), 0.7)); roof.rotation_euler = (0, math.radians(-3.5), 0)
for sd in (-1, 1): cyl("fpost", 0.12, 4.8, X + sd * 4.6, 0, flat("white", hexc("#f4f1ea"), 0.5))
panel3("finishA", "finish.png", 8.8, 1.3, X, 4.2, 0.15, 0.0, board="#f4f1ea")
panel3("finishB", "finish.png", 8.8, 1.3, X, 4.2, -0.15, math.pi, board="#f4f1ea")
panel3("games", "games.png", 22, 1.6, X - 6.95, 2.2, -12, math.pi / 2, board="#1f2a44")
palace = flat("palace", hexc("#f2efe6"), 0.6)
box("palace", X + 50, X + 110, 120, 160, FIELD, 14, palace, bevel=0.2)
bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=14, location=(X + 80, 140, 14)); bpy.context.object.data.materials.append(palace); bpy.ops.object.shade_smooth()
cyl("lantern", 2, 6, X + 80, -140, palace, y0=28)
pen = [flat("penR", hexc("#d23a32"), 0.6), flat("penW", hexc("#f4f1ea"), 0.6), flat("penB", hexc("#2f5aa8"), 0.6)]
def bunting(x0, y0, z0, x1, y1, z1, n, sag, sz=0.32):
    for i in range(n):
        u = (i + 0.5) / n; x = x0 + (x1 - x0) * u; z = z0 + (z1 - z0) * u; y = y0 + (y1 - y0) * u - sag * 4 * u * (1 - u)
        dx = (x1 - x0) / n * 0.42; dz = (z1 - z0) / n * 0.42
        me = bpy.data.meshes.new("pen"); me.from_pydata([(x - dx, -(z - dz), y), (x + dx, -(z + dz), y), (x, -z, y - sz)], [], [(0, 1, 2)]); me.update()
        obj("pen", me, pen[i % 3])
for zz in range(-70, 70, 10): bunting(X - 7.6, 10.6, zz, X - 7.6, 10.6, zz + 10, 16, 0.9)
bunting(X - 4.6, 5.15, 0.3, X + 4.6, 5.15, 0.3, 22, 0.08, 0.24)  # above the FINISH board (it crossed the letters)
flagm = tex_mat("usflag", "usflag.png", rough=0.8)
for zz in range(-64, 65, 16):
    cyl("flagpole", 0.05, 3.4, X - 13, zz, flat("white", hexc("#f4f1ea"), 0.5), y0=11.6)
    uv_plane("flag", 1.6, 1.0, flagm, (X - 13 + 0.8, -zz, 14.4), rot_z=0.4)
for i in range(18): inst("CommonTree_%d" % (1 + i % 4), X + 24 + 40 * hh(i, 1), -100 + 200 * hh(i, 2), 7 + 4 * hh(i, 3), hh(i, 4) * 6.28)

# ------------------------------------------------------------------------------------------------ colour moods per shot
# (sun elevation/azimuth in degrees, sun colour, sun strength, sky strength): road = hot hazy noon, Hicks = harsh glare,
# stadium = golden late afternoon, Boston 1905 = cool spring morning
MOOD = {"road": (52, 130, "#fff0d8", 4.2, 0.85), "hot": (64, 120, "#fff2c8", 4.8, 0.95), "stadium": (24, 200, "#ffc88a", 4.0, 0.7), "boston": (34, 60, "#eaf2ff", 3.6, 0.9)}
def mood_of(sid):
    if sid in (9, 10, 11, 15, 21): return "stadium"
    if sid in (12, 13, 14): return "hot"
    if sid in (22, 23): return "boston"
    return "road"
