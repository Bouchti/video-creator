# 3D props for the Hoover-van film (exec'd from sets_hoover.py after its materials and helpers). Every prop is a collection,
# built in THREE-local coordinates (front = +z, up = +y), instanced per frame by toonrender.py from the exported `props`.
# Origins: standing props at the bottom centre; flat cards (tickets, forms, calendars, boards) at their centre; the scale
# beam at its pivot; the scale pans at their hook; the gavel at its grip end; clock hands at the clock centre.
import bpy, math, os
from mathutils import Vector

PROPS = {}
_lib = []

def _grab():
    """collect every object created since the last call (for coll_of)"""
    got = [o for o in bpy.context.scene.objects if o.name not in _seen]
    for o in got: _seen.add(o.name)
    return got
_seen = set(o.name for o in bpy.context.scene.objects)

def lib(name, fn):
    _grab(); fn(); objs = _grab()
    PROPS[name] = coll_of(objs, "P_" + name)

def tmat(name, file, rough=0.6, emit=0.0):
    return tex_mat("pm_" + name, file, emit=emit, rough=rough, cull=False)

def card(file, w, h, d=0.004, back=None, paper="#fbf8ee", y0=None):
    """a thin printed card centred on the origin (front +z): paper box + printed face (+ printed back)"""
    yc = 0 if y0 is None else y0
    B3("cardpaper", -w / 2, w / 2, yc - h / 2, yc + h / 2, -d / 2, d / 2, flat("paper_" + paper, hexc(paper), 0.8))
    uv_plane("cardface", w, h, tmat(file, file), T(0, yc, d / 2 + 0.0008))
    o = uv_plane("cardback", w, h, tmat(back or file, back or file), T(0, yc, -d / 2 - 0.0008)); o.rotation_euler = (0, 0, math.pi)

def cyl_x(name, r, x0, x1, y, z, mat, v=20):
    bpy.ops.mesh.primitive_cylinder_add(vertices=v, radius=r, depth=x1 - x0, location=((x0 + x1) / 2, -z, y), rotation=(0, math.pi / 2, 0))
    o = bpy.context.object; o.data.materials.append(mat); bpy.ops.object.shade_smooth(); return o

def sphere(name, r, x, y, z, mat, sc=(1, 1, 1), seg=24):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=seg // 2, radius=r, location=(x, -z, y))
    o = bpy.context.object; o.scale = sc; o.data.materials.append(mat); bpy.ops.object.shade_smooth(); return o

def torus(name, R, r, x, y, z, rot, mat):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, location=(x, -z, y), rotation=rot)
    o = bpy.context.object; o.data.materials.append(mat); bpy.ops.object.shade_smooth(); return o

gold = flat("gold", hexc("#d9a640"), 0.25, 1.0); chrome = flat("chrome", hexc("#d8dce2"), 0.15, 1.0)
vgrey = flat("vgrey", hexc("#4a4e58"), 0.45, coat=0.3); vdark = flat("vdark", hexc("#26282e"), 0.5)
vred = flat("vred", hexc("#c8202a"), 0.45, coat=0.5); cardb = flat("cardboard", hexc("#c99a5e"), 0.85)
white2 = flat("white2", hexc("#f7f7f4"), 0.3, coat=0.3); leaf = flat("leaf", hexc("#5d9a3a"), 0.6); foam = flat("foam", hexc("#f6faff"), 0.35, coat=0.6)
leather2 = flat("leather2", hexc("#8a5a32"), 0.5); tea = flat("tea", hexc("#9a6a3a"), 0.2); jetW = flat("jetW", hexc("#f4f6fa"), 0.3, coat=0.5)
jetB = flat("jetB", hexc("#1f4fa0"), 0.35, coat=0.4); jetG = flat("jetG", hexc("#b9bec8"), 0.35, 0.6); jetWin = flat("jetWin", hexc("#2c3e58"), 0.1)

# ---- the classic 1990s upright Hoover (1.25 m): wide head with a headlight, motor hood, a red fabric bag with the badge,
# a chrome collar, a long handle with a loop grip, the cord wound on two hooks at the back
def _vac():
    # head: wide low nozzle with bumper, headlight and red stripe; rear wheels
    B3("vhead", -0.2, 0.2, 0.02, 0.12, -0.14, 0.17, vgrey, 0.035)
    B3("vbumper", -0.21, 0.21, 0.025, 0.065, 0.15, 0.185, vdark, 0.015)
    B3("vlight", -0.09, 0.09, 0.07, 0.11, 0.165, 0.18, lampm, 0.01)
    B3("vstripe", -0.2, 0.2, 0.105, 0.12, 0.1, 0.172, vred, 0.0)
    for sx in (-1, 1): cyl_x("vwheel", 0.055, sx * 0.205 - 0.03, sx * 0.205 + 0.03, 0.055, -0.12, vdark)
    # the upright body, leaning back 12 degrees on its pivot: grey motor hood, red bag housing with the badge, chrome
    # handle tube, a small D grip; the cord wound on two hooks behind
    piv = bpy.data.objects.new("vpivot", None); bpy.context.collection.objects.link(piv); piv.location = (0, 0.06, 0.12); piv.rotation_euler = (math.radians(-12), 0, 0)
    def P_(o): o.parent = piv; o.location = o.location - Vector((0, 0.06, 0.12)); return o
    P_(B3("vhood", -0.13, 0.13, 0.12, 0.3, -0.12, 0.08, vgrey, 0.05))
    P_(B3("vbody", -0.135, 0.135, 0.3, 0.9, -0.1, 0.07, vred, 0.06))
    P_(B3("vpanel", -0.1, 0.1, 0.36, 0.84, 0.07, 0.085, flat("vpanel", hexc("#e23440"), 0.35, coat=0.6), 0.03))
    P_(uv_plane("vbadge", 0.17, 0.074, tmat("vac_badge", "vac_badge.png", rough=0.3), T(0, 0.66, 0.087)))
    P_(B3("vtop", -0.1, 0.1, 0.9, 0.95, -0.08, 0.05, vgrey, 0.02))
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.017, depth=0.3, location=(0, 0.015, 1.1)); P_(bpy.context.object).data.materials.append(chrome)
    P_(torus("vgrip", 0.045, 0.013, 0, 1.28, -0.015, (math.pi / 2, 0, 0), vdark))
    for y in (0.45, 0.85): P_(B3("vhook", -0.02, 0.02, y - 0.02, y + 0.02, -0.14, -0.1, vdark, 0.0))
    for k in range(5): P_(torus("vcord", 0.03, 0.008, 0, 0.5 + 0.08 * k, -0.14, (0, math.pi / 2, 0), flat("cord", hexc("#e2ded4"), 0.6)))
lib("vac", _vac)

def _carton():
    B3("cart", -0.25, 0.25, 0, 0.62, -0.22, 0.22, tex_mat("carton2", "carton.png", rough=0.8, cull=False))
    B3("ctape", -0.03, 0.03, 0.62, 0.625, -0.22, 0.22, flat("tape", hexc("#d9b77a"), 0.4))
lib("carton", _carton)

for nm in ("ticket_ny", "ticket_orl", "ticket_wus", "ticket_ours"): lib(nm, lambda nm=nm: card(nm + ".png", 0.42, 0.194, 0.004))
for nm in ("form", "form_rej"): lib(nm, lambda nm=nm: card(nm + ".png", 0.24, 0.32, 0.003, back="form.png"))
for n in list(range(1, 15)) + ["JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC", "JAN", "FEB", "MAR"]:
    lib(f"cal_{n}", lambda n=n: (card(f"cal_{n}.png", 0.52, 0.6, 0.05, back="cal_1.png", paper="#ffffff"),
                                [B3("calring", x - 0.025, x + 0.025, 0.28, 0.34, -0.012, 0.012, chrome, 0.01) for x in (-0.13, 0.13)]))
for k in list(range(8)) + ["7s"]:
    lib(f"week_{k}", lambda k=k: (card(f"week_{k}.png", 1.24, 0.6, 0.03, back=f"week_{k}.png", paper="#ffffff"), B3("weekframe", -0.64, 0.64, -0.32, 0.32, -0.03, -0.015, woodm)))
for n in (0, 3, 6, 9, 12, 15, 18): lib(f"ads_{n}", lambda n=n: card(f"ads_{n}.png", 0.6, 0.76, 0.006, paper="#f1ece0"))
lib("order", lambda: (card("order.png", 0.3, 0.42, 0.003), sphere("seal", 0.03, 0.08, -0.15, 0.004, vred, sc=(1, 1, 0.3))))
lib("sold", lambda: (card("sold.png", 1.04, 0.6, 0.04, paper="#d8262e"), B3("soldstake", -0.03, 0.03, -0.9, -0.3, -0.04, -0.02, woodm)))

def _clock():
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.32, depth=0.06, location=(0, 0.03, 0), rotation=(math.pi / 2, 0, 0)); o = bpy.context.object; o.data.materials.append(vdark); bpy.ops.object.shade_smooth()
    o = uv_plane("clockface", 0.6, 0.6, tmat("clock", "clock.png", rough=0.3), T(0, 0, 0.062)); o.scale = (1, 1, 1)
    torus("clockrim", 0.31, 0.02, 0, 0, 0.06, (math.pi / 2, 0, 0), chrome)
lib("clock", _clock)
lib("hand_l", lambda: (B3("hl", -0.012, 0.012, -0.03, 0.24, 0, 0.01, flat("handR", hexc("#d8262e"), 0.4)), sphere("hub", 0.025, 0, 0, 0.01, vdark)))
lib("hand_s", lambda: B3("hs", -0.02, 0.02, -0.02, 0.16, 0, 0.012, vdark))

# ---- the balance scale: brass foot and post; the beam (origin at its pivot); two pans hanging from their hooks
lib("scale_base", lambda: (CYLY("sfoot", 0.2, 0, 0.0, 0.05, 0, gold, 32), B3("spost", -0.03, 0.03, 0.05, 0.96, -0.03, 0.03, gold, 0.01), sphere("sknob", 0.05, 0, 1.0, 0, gold)))
lib("scale_beam", lambda: (B3("sbeam", -0.66, 0.66, -0.02, 0.02, -0.02, 0.02, gold, 0.008), sphere("spiv", 0.045, 0, 0, 0, gold),
                           [sphere("send", 0.03, x, 0, 0, gold) for x in (-0.64, 0.64)]))
def rod(p0, p1, r, mat):
    d = p1 - p0
    bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=r, depth=d.length, location=(p0 + p1) / 2)
    o = bpy.context.object; o.rotation_mode = "QUATERNION"; o.rotation_quaternion = d.to_track_quat("Z", "Y"); o.data.materials.append(mat); return o

def _pan(side):
    for a in (0, 2.09, 4.19):
        rod(Vector((0, 0, 0)), Vector((0.2 * math.cos(a), -0.2 * math.sin(a), -0.47)), 0.004, gold)
    bpy.ops.mesh.primitive_cylinder_add(vertices=40, radius=0.22, depth=0.03, location=(0, 0, -0.48)); o = bpy.context.object; o.data.materials.append(gold); bpy.ops.object.shade_smooth()
    if side == "L":
        # a small Hoover on the pan, its £119 tag
        for o in _vac_small(): pass
        card_tag("tag_119")
    else:
        for k in range(2):
            o2 = [];  # two tickets leaning on the pan
            B3("tk", -0.21, 0.21, -0.465, -0.461, -0.1 + 0.08 * k, 0.1 + 0.08 * k, flat("tkp", hexc("#fbf8ee"), 0.7))
            uv_plane("tkf", 0.42, 0.194, tmat("ticket_ny", "ticket_ny.png"), T(0.02 * k, -0.33 + 0.02 * k, -0.02 + 0.06 * k)).rotation_euler = (-0.35, 0, 0)
        card_tag("tag_600")
def _vac_small():
    e = bpy.data.objects.new("vacsmall", None); e.instance_type = "COLLECTION"; e.instance_collection = PROPS["vac"]
    e.location = T(0, -0.465, 0); e.scale = (0.36, 0.36, 0.36); bpy.context.collection.objects.link(e); return [e]
def card_tag(file):
    uv_plane("tag", 0.2, 0.09, tmat(file, file + ".png", rough=0.4, emit=0.2), T(0, -0.56, 0.2))
lib("scale_panL", lambda: _pan("L")); lib("scale_panR", lambda: _pan("R"))

def _obox():
    for x0, x1, z0, z1 in ((-0.22, 0.22, 0.16, 0.18), (-0.22, 0.22, -0.18, -0.16), (-0.22, -0.2, -0.18, 0.18), (0.2, 0.22, -0.18, 0.18)): B3("obw", x0, x1, 0, 0.26, z0, z1, cardb, 0.0)
    B3("obb", -0.22, 0.22, 0, 0.02, -0.18, 0.18, cardb)
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.01, depth=0.3, location=(-0.08, 0.04, 0.38)); bpy.context.object.data.materials.append(leaf)
    for k in range(5): sphere("lf", 0.06, -0.08 + 0.05 * math.cos(k * 1.3), 0.5 + 0.04 * k, 0.04 * math.sin(k * 1.3), leaf, sc=(1, 0.6, 1), seg=12)
    B3("lampstem", 0.1, 0.12, 0.2, 0.5, -0.05, -0.03, vdark); sphere("lampshade", 0.07, 0.11, 0.52, 0.02, flat("lshade", hexc("#2f5a3a"), 0.4), sc=(1, 0.7, 1))
    B3("files", -0.18, 0.0, 0.02, 0.3, -0.12, -0.08, flat("fileR", hexc("#d8262e"), 0.6)); B3("files2", -0.18, 0.0, 0.02, 0.28, -0.07, -0.03, flat("fileB", hexc("#2f5fb0"), 0.6))
lib("obox", _obox)

def _mug():
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.045, depth=0.1, location=(0, 0, 0.05)); o = bpy.context.object; o.data.materials.append(white2); bpy.ops.object.shade_smooth()
    torus("mh", 0.028, 0.008, 0.055, 0.05, 0, (math.pi / 2, 0, 0), white2)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.04, depth=0.002, location=(0, 0, 0.088)); bpy.context.object.data.materials.append(tea)
    B3("mband", -0.046, 0.046, 0.03, 0.05, -0.046, 0.046, flat("mband", hexc("#1f4fa0"), 0.4))
lib("mug", _mug)

def _chair():
    fr = flat("chairframe", hexc("#c9a46a"), 0.6); cloth = tmat("stripes", "stripes.png", rough=0.8)
    for sx in (-1, 1):
        me = bpy.data.meshes.new("rail"); x = sx * 0.3
        b = box("rail", x - 0.02, x + 0.02, -0.05, 0.05, 0.0, 1.0, fr, None, 0.0); b.rotation_euler = (math.radians(-35), 0, 0); b.location = (x, 0.25, 0.42)
        b2 = box("leg", x - 0.02, x + 0.02, -0.04, 0.04, 0.0, 0.55, fr, None, 0.0); b2.rotation_euler = (math.radians(30), 0, 0); b2.location = (x, -0.15, 0.25)
    me = bpy.data.meshes.new("sling")
    me.from_pydata([(-0.28, -0.3, 0.38), (0.28, -0.3, 0.38), (0.28, 0.05, 0.3), (-0.28, 0.05, 0.3), (0.28, 0.5, 0.95), (-0.28, 0.5, 0.95)], [], [(0, 1, 2, 3), (3, 2, 4, 5)])
    me.uv_layers.new(); uv = me.uv_layers[0].data
    for i, c in enumerate([(0, 0), (1, 0), (1, 0.4), (0, 0.4), (0, 0.4), (1, 0.4), (1, 1), (0, 1)]): uv[i].uv = c
    me.update(); obj("sling", me, cloth)
lib("chair", _chair)

def _suitcase():
    B3("sc", -0.32, 0.32, 0, 0.44, -0.11, 0.11, leather2, 0.03)
    for x in (-0.2, 0.2): B3("strap", x - 0.025, x + 0.025, 0.0, 0.445, -0.115, 0.115, flat("strap", hexc("#5a3418"), 0.6), 0.0)
    torus("shandle", 0.07, 0.015, 0, 0.47, 0, (0, 0, 0), flat("strap", hexc("#5a3418"), 0.6)).scale = (1, 0.4, 1)
    for x in (-0.25, 0.25): B3("clasp", x - 0.03, x + 0.03, 0.36, 0.4, 0.11, 0.12, gold, 0.0)
lib("suitcase", _suitcase)

def _gavel():
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.015, depth=0.3, location=(0.15, 0, 0), rotation=(0, math.pi / 2, 0)); o = bpy.context.object; o.data.materials.append(flat("gwood", hexc("#7a4a22"), 0.4)); bpy.ops.object.shade_smooth()
    bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.04, depth=0.16, location=(0.3, 0, 0)); o = bpy.context.object; o.data.materials.append(flat("gwood2", hexc("#5a3418"), 0.35)); bpy.ops.object.shade_smooth()
lib("gavel", _gavel)

def _suds():
    import random
    r = random.Random(5)
    for k in range(16):
        a = r.random() * 6.28; d = 0.25 * r.random() ** 0.5; rr = 0.07 + 0.1 * r.random()
        sphere("bub", rr, d * math.cos(a), rr * 0.8 + 0.12 * r.random(), d * math.sin(a), foam, seg=16)
lib("suds", _suds)

# ---- the jumbo jet (about 40 m at s = 1): nose to +z
def _plane():
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=2.0, depth=30, location=(0, 0, 0), rotation=(math.pi / 2, 0, 0)); o = bpy.context.object; o.data.materials.append(jetW); bpy.ops.object.shade_smooth()
    sphere("nose", 1.0, 0, 0, 15, jetW, sc=(2.0, 3.4, 2.0), seg=32)
    bpy.ops.mesh.primitive_cone_add(vertices=32, radius1=2.0, radius2=0.4, depth=8, location=(0, 19, 0.6), rotation=(-math.pi / 2, 0, 0)); o = bpy.context.object; o.data.materials.append(jetW); bpy.ops.object.shade_smooth()
    B3("belly", -2.02, 2.02, -0.9, -0.55, -15, 15, jetB, 0.0)
    for sx in (-1, 1):
        B3("winstrip", sx * 2.0 - 0.02, sx * 2.0 + 0.02, 0.45, 0.85, -13, 13, jetWin, 0.0)
        me = bpy.data.meshes.new("wing")
        vs = [(sx * 1.6, -2, -0.6), (sx * 1.6, 6, -0.6), (sx * 20, 10, -0.2), (sx * 20, 6.5, -0.2)]
        me.from_pydata([(x, y, z) for x, y, z in vs] + [(x, y, z + 0.35) for x, y, z in vs], [], [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])
        me.update(); obj("wing", me, jetG)
        for ex in (6.5, 12.5):
            bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.9, depth=3.6, location=(sx * ex, -(-0.5 - ex * 0.2), -1.4), rotation=(math.pi / 2, 0, 0)); o = bpy.context.object; o.data.materials.append(jetG); bpy.ops.object.shade_smooth()
        me = bpy.data.meshes.new("tailplane"); vs = [(sx * 0.4, 18, 1.0), (sx * 0.4, 21.5, 1.0), (sx * 7, 22.5, 1.2), (sx * 7, 20.5, 1.2)]
        me.from_pydata(vs + [(x, y, z + 0.2) for x, y, z in vs], [], [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]); me.update(); obj("tailplane", me, jetG)
    me = bpy.data.meshes.new("fin"); vs = [(0, 16, 1.6), (0, 22.5, 1.6), (0, 23.5, 9.5), (0, 20.5, 9.5)]
    me.from_pydata([(x - 0.15, y, z) for x, y, z in vs] + [(x + 0.15, y, z) for x, y, z in vs], [], [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]); me.update(); obj("fin", me, jetB)
    B3("cockpit", -1.1, 1.1, 0.7, 1.2, 15.2, 16.4, jetWin, 0.1)
lib("plane", _plane)

