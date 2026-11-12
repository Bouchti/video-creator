# The Gimli Glider sets for toonrender.py (exec'd inside it: uses pbr, flat, hexc, box, plane, obj, T, mat_new, inst, hh,
# data, OUT_ROOT, KIT). Three.js coordinates in comments (x, y up, z); Blender = (x, -z, y). Mirrors src/videos/gimli/places.ts.
#   STRIP  x 0      Gimli drag strip on Family Day (golden hour): runway along z, guardrail on x = 0, pits + crowd at +z
#   RAMP   x 3000   Montreal / Ottawa apron (day): the 767 at the gate, the fuel truck, the terminal
#   COCK   x 6000   the 767 cockpit (pilots face +z: the panel is at +z)
#   SKY    x 9000   cruise above a cloud deck (dusk) + the glider cutaway at x 9600 (midday)
#   ROAD   x 12000  the country road at dusk (the mechanics' van)
# Defines VEHICLES, MOOD, SKIES and mood_of for the renderer.
import bpy, bmesh, math, os
from mathutils import Vector, Matrix, Euler

ASSETS = os.path.join(OUT_ROOT, "assets")
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.path.join(OUT_ROOT, "..", "..", "blender"), "sets_hoover.py"), encoding="utf-8").read().split("# ------------------------------------------------------------------------------------------------ materials")[0])

# ------------------------------------------------------------------------------------------------ materials
asph = pbr("asphG", "Asphalt031", scale=3.0, tint=hexc("#e2dcd8"))
asph2 = pbr("asphG2", "Asphalt031", scale=2.0, tint=hexc("#bdb6b4"))
grassm = pbr("grassG", "Grass004", scale=4.0, tint=hexc("#c8e070"), normal_strength=0.5)
grassd = pbr("grassD", "Grass001", scale=5.0, tint=hexc("#d8d070"), normal_strength=0.4)
wheat = pbr("wheat", "Ground054", scale=4.0, tint=hexc("#f0d070"), normal_strength=0.6)
apron = pbr("apron", "Concrete031", scale=4.0, tint=hexc("#e2e0da"))
conc = pbrb("concG", "Concrete034", 2.0, tint=hexc("#dcd8d0"))
metal = pbrb("metalG", "Metal032", 1.2, tint=hexc("#c8ccd4"))
gravel = pbr("gravelG", "Gravel023", scale=2.0, tint=hexc("#d8ccb8"))
white = flat("whiteG", hexc("#f4f2ec"), 0.45); black = flat("blackG", hexc("#1d1b22"), 0.55); ink = flat("inkG", hexc("#2a2a32"), 0.6)
paintW = flat("jetWhite", hexc("#f6f6f4"), 0.22, coat=0.8); paintG = flat("jetBelly", hexc("#c4c8d0"), 0.3, 0.2, coat=0.5)
paintR = flat("jetRed", hexc("#d0202c"), 0.25, coat=0.8); wingG = flat("wingGrey", hexc("#b8bcc6"), 0.35, 0.4, coat=0.3)
glassD = flat("cockGlass", hexc("#1c2838"), 0.05, coat=1.0); winD = flat("winDark", hexc("#26354a"), 0.1, coat=0.8)
chromeG = flat("chromeG", hexc("#e0e4ea"), 0.12, 1.0); fanD = flat("fanDark", hexc("#30333a"), 0.35, 0.7); rubber = flat("rubberG", hexc("#1a1a1e"), 0.7)
yel = flat("yelG", hexc("#f2c230"), 0.4); redm = flat("redG", hexc("#d8262e"), 0.4, coat=0.4); bluem = flat("blueG", hexc("#2f5fb0"), 0.4, coat=0.3)
orange = flat("orangeG", hexc("#f07a1e"), 0.45); greenm = flat("greenG", hexc("#2f8a4a"), 0.45, coat=0.3); cream = flat("creamG", hexc("#efe6d2"), 0.5)
lampm = flat("lampG", hexc("#fff6dc"), 0.3, emit=hexc("#fff2cc")); water = flat("lakeG", hexc("#3a78b8"), 0.06, coat=1.0)
cloudm = flat("cloudG", hexc("#fbf6f4"), 0.95, emit=hexc("#4a3e5e"))

def tl(x, y, z): return (x, -z, y)          # three-local -> blender-local

def coll_from(fn, name):
    before = set(bpy.data.objects); fn(); new = [o for o in bpy.data.objects if o not in before]
    return coll_of(new, name)

def mesh_obj(name, verts, faces, mat, parent=None, smooth=True, mats=None, fmat=None):
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces); me.update()
    o = obj(name, me, mat, (0, 0, 0), parent)
    if mats:
        for m in mats[1:]: o.data.materials.append(m)
        if fmat:
            for i, p in enumerate(o.data.polygons): p.material_index = fmat(i, p)
    if smooth:
        for p in o.data.polygons: p.use_smooth = True
    return o

def cyl(name, r, p0, p1, mat, parent=None, v=24, r1=None):
    """cylinder (or cone with r1) between two blender points"""
    a, b = Vector(p0), Vector(p1); d = b - a
    bpy.ops.mesh.primitive_cone_add(vertices=v, radius1=r, radius2=r if r1 is None else r1, depth=d.length, location=(a + b) / 2)
    o = bpy.context.object; o.name = name; o.rotation_mode = "QUATERNION"; o.rotation_quaternion = d.normalized().to_track_quat("Z", "Y")
    o.data.materials.append(mat); bpy.ops.object.shade_smooth()
    if parent: o.parent = parent
    return o

def ball(name, r, p, mat, parent=None, sc=(1, 1, 1), seg=24):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=seg // 2, radius=r, location=p)
    o = bpy.context.object; o.name = name; o.scale = sc; o.data.materials.append(mat); bpy.ops.object.shade_smooth()
    if parent: o.parent = parent
    return o

def loft(name, rings, mat, parent=None, n=36, mats=None, fmat=None, cap=True):
    """rings: [(z3, rx, ry, cy)] along three z -> a closed tube (three-local), optional per-face material by fmat(z3, angle)"""
    verts, faces = [], []
    for (z, rx, ry, cy) in rings:
        for k in range(n):
            a = 2 * math.pi * k / n; verts.append(tl(rx * math.sin(a), cy + ry * math.cos(a), z))
    for i in range(len(rings) - 1):
        for k in range(n):
            a0, a1 = i * n + k, i * n + (k + 1) % n
            faces.append((a0, a1, a1 + n, a0 + n))
    if cap:
        verts.append(tl(0, rings[0][3], rings[0][0])); verts.append(tl(0, rings[-1][3], rings[-1][0]))
        c0, c1 = len(verts) - 2, len(verts) - 1
        for k in range(n): faces.append((c0, (k + 1) % n, k)); faces.append((c1, (len(rings) - 1) * n + k, (len(rings) - 1) * n + (k + 1) % n))
    ff = None
    if fmat:
        def ff(i, p):
            if i >= (len(rings) - 1) * n: return 0
            ring, k = divmod(i, n); z = (rings[ring][0] + rings[ring + 1][0]) / 2; a = 2 * math.pi * (k + 0.5) / n
            return fmat(z, a)
    return mesh_obj(name, verts, faces, mat, parent, True, mats, ff)

def surface(name, sec0, sec1, mat, parent=None, mats=None):
    """a lifting surface between two airfoil sections; sec = (x, y, zLE, chord, thick, vertical) in three-local"""
    prof = [(0, 0), (0.03, 0.55), (0.12, 0.85), (0.3, 1.0), (0.55, 0.85), (0.8, 0.45), (1.0, 0.04), (0.8, -0.25), (0.55, -0.45), (0.3, -0.55), (0.12, -0.5), (0.03, -0.32)]
    def pts(sec):
        x, y, zle, c, t, vert = sec
        return [tl(x + (t * w * 0.5 if vert else 0), y + (0 if vert else t * w * 0.5), zle - u * c) for u, w in prof]
    p0, p1 = pts(sec0), pts(sec1); n = len(prof); verts = p0 + p1
    faces = [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)] + [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    return mesh_obj(name, verts, faces, mat, parent, True, mats)

# ------------------------------------------------------------------------------------------------ the Boeing 767-200
JET_CY = 4.4      # fuselage centre above the ground (gear down)
FUSE = [(24.25, 0.08, 0.08, JET_CY - 0.45), (23.85, 0.75, 0.7, JET_CY - 0.32), (23.1, 1.35, 1.3, JET_CY - 0.18), (22.0, 1.9, 1.88, JET_CY - 0.08),
        (20.6, 2.3, 2.3, JET_CY - 0.02), (18.8, 2.5, 2.5, JET_CY), (-11.5, 2.5, 2.5, JET_CY), (-14.5, 2.42, 2.36, JET_CY + 0.12), (-17.5, 2.15, 1.98, JET_CY + 0.42),
        (-20.5, 1.65, 1.4, JET_CY + 0.86), (-23.0, 0.95, 0.75, JET_CY + 1.32), (-24.5, 0.32, 0.25, JET_CY + 1.62)]

def make_jet():
    root = bpy.data.objects.new("jet", None); bpy.context.collection.objects.link(root)
    def fm(z, a):
        up = math.cos(a)                                # +1 top, -1 bottom
        side = abs(math.sin(a))
        if 21.4 < z < 23.0 and 0.3 < up < 0.82 and side > 0.35: return 3        # windshield band
        if up < -0.42: return 1                                                  # grey belly
        if -0.2 < up < -0.05 and z < 20.6: return 2                              # red cheat line under the windows
        return 0
    loft("fuselage", FUSE, paintW, root, 48, [paintW, paintG, paintR, glassD], fm)
    # cabin windows: two rows of small dark panes on the tube (one mesh), the doors as thin dark outlines
    bm = bmesh.new()
    for sx in (-1, 1):
        for k in range(58):
            z = 17.2 - k * 0.52
            if any(abs(z - dz) < 0.7 for dz in (16.0, 1.8, -11.2)): continue
            m = Matrix.Translation(Vector(tl(sx * 2.505, JET_CY + 0.42, z))) @ Matrix.Rotation(math.radians(-sx * 9), 4, "Y")
            bmesh.ops.create_cube(bm, size=1.0, matrix=m @ Matrix.Diagonal((0.05, 0.24, 0.34, 1)))
    me = bpy.data.meshes.new("cabwin"); bm.to_mesh(me); bm.free(); obj("cabwin", me, winD, (0, 0, 0), root)
    for sx in (-1, 1):
        for dz, w in ((16.0, 0.95), (1.8, 0.95), (-11.2, 0.95)):
            box("door", sx * 2.49 - 0.025, sx * 2.49 + 0.025, -dz - w / 2, -dz + w / 2, JET_CY - 0.75, JET_CY + 1.15, ink, root, 0.0)
            box("doorin", sx * 2.5 - 0.03, sx * 2.5 + 0.03, -dz - w / 2 + 0.07, -dz + w / 2 - 0.07, JET_CY - 0.68, JET_CY + 1.08, paintW, root, 0.0)
        # title above the windows (tilted to the tube), registration near the tail
        th = math.radians(28); o = uv_plane("title", 9.5, 1.19, decal_mat("titleD", "title.png"), (sx * 2.5 * math.cos(th) + sx * 0.06, -6.5, JET_CY + 2.5 * math.sin(th) + 0.02), rot_z=sx * math.pi / 2, parent=root)
        o.rotation_euler = (0, sx * -th, sx * math.pi / 2) if False else (sx * 0, 0, sx * math.pi / 2); o.rotation_euler.rotate(Euler((0, -sx * th, 0)))
        uv_plane("reg", 3.2, 0.5, decal_mat("regD", "reg.png"), (sx * 2.47, 15.5, JET_CY + 0.25), rot_z=sx * math.pi / 2, parent=root)
    # wings (dihedral 6 deg, LE sweep 31.5 deg), flap-track fairings, engines on pylons
    for sx in (-1, 1):
        surface("wing", (sx * 2.2, JET_CY - 1.55, 4.2, 8.6, 1.05, False), (sx * 23.8, JET_CY - 1.55 + 2.25, 4.2 - 21.6 * math.tan(math.radians(31.5)), 2.35, 0.3, False), wingG, root)
        surface("wingtipcap", (sx * 23.75, JET_CY + 0.7, 4.2 - 21.55 * math.tan(math.radians(31.5)), 2.36, 0.31, False), (sx * 23.9, JET_CY + 0.72, 4.2 - 21.7 * math.tan(math.radians(31.5)), 2.3, 0.28, False), paintW, root)
        for k, f in enumerate((0.3, 0.52, 0.74)):
            x = sx * (2.2 + 21.6 * f); zle = 4.2 - 21.6 * f * math.tan(math.radians(31.5)); c = 8.6 + (2.35 - 8.6) * f
            cyl("fairing", 0.22, tl(x, JET_CY - 1.6 + 2.25 * f - 0.15, zle - c * 0.55), tl(x, JET_CY - 1.6 + 2.25 * f - 0.3, zle - c * 1.18), wingG, root, 12, 0.05)
        ex = sx * 8.1; ey = JET_CY - 2.95; z0, z1 = 8.2, 2.2
        surface("pylon", (ex, ey + 0.6, z0 - 0.6, 6.5, 0.38, True), (ex, ey + 1.62, z0 - 1.6, 6.0, 0.36, True), paintW, root)
        loft("nacelle", [(z0, 1.32, 1.32, ey), (z0 - 0.4, 1.45, 1.45, ey), (z0 - 2.0, 1.45, 1.45, ey), (z1 + 0.6, 1.18, 1.18, ey), (z1, 1.0, 1.0, ey)], paintW, root, 40, cap=False)
        loft("nacellelip", [(z0 + 0.02, 1.12, 1.12, ey), (z0 + 0.06, 1.3, 1.3, ey), (z0 - 0.3, 1.34, 1.34, ey)], chromeG, root, 40, cap=False)
        loft("nacellein", [(z0 + 0.02, 1.12, 1.12, ey), (z0 - 0.9, 1.15, 1.15, ey)], fanD, root, 40, cap=False)
        loft("exhaust", [(z1 + 0.05, 0.98, 0.98, ey), (z1 - 0.9, 0.72, 0.72, ey), (z1 - 1.8, 0.2, 0.2, ey)], fanD, root, 32)
        froot = bpy.data.objects.new("fanroot%d" % sx, None); bpy.context.collection.objects.link(froot); FANROOT[sx] = froot
        base = bpy.data.objects.new("fanbase", None); bpy.context.collection.objects.link(base); base.parent = froot
        base.location = tl(ex, ey, z0 - 0.65); base.rotation_euler = (0, 0, -math.pi / 2)        # local X = three +z (the engine axis)
        spin = bpy.data.objects.new("fan", None); bpy.context.collection.objects.link(spin); spin.parent = base
        disc = cyl("fandisc", 1.1, (-0.05, 0, 0), (0.05, 0, 0), fanD, spin, 40)
        for b in range(18):
            a = 2 * math.pi * b / 18; bl = box("blade", -0.03, 0.03, -0.09, 0.09, 0.2, 1.08, chromeG, spin, 0.0)
            bl.location = (0, -0.64 * math.sin(a), 0.64 * math.cos(a)); bl.rotation_euler = (a, 0, 0)
        cone = cyl("spinner", 0.36, (0.0, 0, 0), (0.62, 0, 0), chromeG, spin, 24, 0.02)
        stripe = cyl("spinmark", 0.37, (0.12, 0, 0), (0.16, 0, 0), black, spin, 24)
        FANSPIN[sx] = spin
    # tail: fin (red, the leaf on both sides) + tailplanes
    surface("fin", (0, JET_CY + 2.0, -15.4, 8.4, 0.95, True), (0, JET_CY + 2.0 + 8.6, -15.4 - 8.6 * math.tan(math.radians(40)), 3.1, 0.32, True), paintR, root)
    for sx in (-1, 1):
        uv_plane("leaf", 4.6, 4.6, decal_mat("leafD", "tail_leaf.png"), (sx * 0.5, 23.6, JET_CY + 6.2), rot_z=sx * math.pi / 2, parent=root)
        surface("htail", (sx * 1.0, JET_CY + 0.75, -17.6, 6.0, 0.5, False), (sx * 9.4, JET_CY + 1.5, -17.6 - 8.4 * math.tan(math.radians(34)), 1.9, 0.18, False), wingG, root)
    # main gear: two 4-wheel bogies with struts (wheels spin with d)
    for sx in (-1, 1):
        cyl("mstrut", 0.18, tl(sx * 4.6, JET_CY - 1.6, -1.2), tl(sx * 4.6, 1.15, -1.2), chromeG, root, 12)
        box("bogie", sx * 4.6 - 0.15, sx * 4.6 + 0.15, -(-1.2) - 1.0, -(-1.2) + 1.0, 0.9, 1.15, ink, root, 0.03)
        for dz in (-0.75, 0.75):
            for dx in (-0.42, 0.42):
                w = bpy.data.objects.new("mwheel", None); bpy.context.collection.objects.link(w); w.parent = root; w.location = tl(sx * 4.6 + dx, 0.62, -1.2 + dz)
                cyl("tyre", 0.62, (-0.2, 0, 0), (0.2, 0, 0), rubber, w, 28); cyl("hub", 0.34, (-0.21, 0, 0), (0.21, 0, 0), chromeG, w, 16)
                FANS.append(w)
    return root

def make_nosegear():
    root = bpy.data.objects.new("ngear", None); bpy.context.collection.objects.link(root)
    cyl("nstrut", 0.14, tl(0, JET_CY - 2.0, 19.2), tl(0, 0.75, 19.4), chromeG, root, 12)
    wl = []
    for dx in (-0.3, 0.3):
        w = bpy.data.objects.new("nwheel", None); bpy.context.collection.objects.link(w); w.parent = root; w.location = tl(dx, 0.5, 19.4)
        cyl("ntyre", 0.5, (-0.14, 0, 0), (0.14, 0, 0), rubber, w, 24); cyl("nhub", 0.26, (-0.15, 0, 0), (0.15, 0, 0), chromeG, w, 14); wl.append(w)
    box("ndoor", -0.03, 0.03, -21.0, -18.6, JET_CY - 2.6, JET_CY - 1.9, paintW, root, 0.0)
    return root, wl

FANS = []; FANROOT = {}; FANSPIN = {}
JET = make_jet()
JETW = list(FANS)

# ------------------------------------------------------------------------------------------------ cars, truck, van, glider
def wheel_pair(root, x, z, r, w, rim=chromeG, lst=None):
    for sx in (-1, 1):
        e = bpy.data.objects.new("cw", None); bpy.context.collection.objects.link(e); e.parent = root; e.location = tl(sx * x, r, z)
        cyl("tyre", r, (-w / 2, 0, 0), (w / 2, 0, 0), rubber, e, 24); cyl("rim", r * 0.58, (-w / 2 - 0.01, 0, 0), (w / 2 + 0.01, 0, 0), rim, e, 16)
        if lst is not None: lst.append(e)

def make_dragster(col, name):
    root = bpy.data.objects.new(name, None); bpy.context.collection.objects.link(root); ws = []
    paint = flat(name + "P", hexc(col), 0.25, coat=0.9)
    loft(name + "body", [(3.2, 0.06, 0.06, 0.42), (2.4, 0.22, 0.16, 0.42), (0.0, 0.32, 0.24, 0.46), (-1.4, 0.42, 0.36, 0.55), (-2.2, 0.46, 0.4, 0.6)], paint, root, 20)
    box("engine", -0.36, 0.36, -(-1.6) - 0.6, -(-1.6) + 0.6, 0.6, 1.15, chromeG, root, 0.05)
    box("blower", -0.28, 0.28, -(-1.6) - 0.35, -(-1.6) + 0.35, 1.15, 1.55, chromeG, root, 0.04)
    box("scoop", -0.22, 0.22, -(-1.6) - 0.25, -(-1.6) + 0.25, 1.55, 1.75, black, root, 0.03)
    box("cage", -0.3, 0.3, -(-0.6) - 0.3, -(-0.6) + 0.3, 0.55, 1.05, black, root, 0.04)
    box("wingst", -0.05, 0.05, 2.75, 2.85, 0.5, 2.1, black, root, 0.0); box("wing", -1.0, 1.0, 2.55, 3.35, 2.05, 2.15, paint, root, 0.02)
    for sx in (-1, 1): box("wingend", sx * 1.0 - 0.02, sx * 1.0 + 0.02, 2.5, 3.4, 1.85, 2.3, black, root, 0.0)
    wheel_pair(root, 0.95, -2.4, 0.62, 0.62, chromeG, ws); wheel_pair(root, 0.55, 2.7, 0.28, 0.12, chromeG, ws)
    return root, ws

def make_muscle(col, name, stripe="#f4f4f2", y0=0.0):
    root = bpy.data.objects.new(name, None); bpy.context.collection.objects.link(root); ws = []
    paint = flat(name + "P", hexc(col), 0.22, coat=0.9); st = flat(name + "S", hexc(stripe), 0.3, coat=0.6)
    def B(n, x0, x1, y0_, y1, z0, z1, m, b=0.05): return box(n, x0, x1, -z1, -z0, y0_ + y0, y1 + y0, m, root, b)
    B("lower", -0.92, 0.92, 0.32, 0.86, -2.3, 2.3, paint, 0.12); B("hood", -0.88, 0.88, 0.8, 0.92, 0.6, 2.25, paint, 0.08)
    B("cabin", -0.78, 0.78, 0.86, 1.32, -1.2, 0.55, paint, 0.14); B("glassF", -0.72, 0.72, 0.9, 1.26, 0.5, 0.62, winD, 0.03)
    B("glassR", -0.72, 0.72, 0.9, 1.24, -1.24, -1.12, winD, 0.03)
    for sx in (-1, 1): B("glassS", sx * 0.785 - 0.02, sx * 0.785 + 0.02, 0.92, 1.24, -1.05, 0.42, winD, 0.02)
    for sx in (-0.22, 0.22): B("stripe", sx - 0.09, sx + 0.09, 0.92, 0.935, 0.6, 2.26, st, 0.0); B("stripe2", sx - 0.09, sx + 0.09, 1.32, 1.335, -1.2, 0.55, st, 0.0)
    B("bumperF", -0.94, 0.94, 0.3, 0.46, 2.25, 2.4, chromeG, 0.04); B("bumperR", -0.94, 0.94, 0.3, 0.46, -2.4, -2.25, chromeG, 0.04)
    B("grille", -0.7, 0.7, 0.5, 0.78, 2.3, 2.33, black, 0.0)
    for sx in (-1, 1): B("lamp", sx * 0.62 - 0.12, sx * 0.62 + 0.12, 0.6, 0.72, 2.31, 2.35, lampm, 0.01)
    B("spoiler", -0.85, 0.85, 0.92, 1.0, -2.3, -2.05, paint, 0.02)
    wheel_pair(root, 0.82, 1.45, 0.36, 0.3, chromeG, ws); wheel_pair(root, 0.82, -1.45, 0.38, 0.36, chromeG, ws)
    return root, ws

def make_van():
    root = bpy.data.objects.new("van", None); bpy.context.collection.objects.link(root); ws = []
    paint = flat("vanWhite", hexc("#f4f4f0"), 0.25, coat=0.7)
    def B(n, x0, x1, y0, y1, z0, z1, m, b=0.05): return box(n, x0, x1, -z1, -z0, y0, y1, m, root, b)
    B("vbody", -1.0, 1.0, 0.45, 2.45, -2.6, 1.2, paint, 0.12); B("vhood", -1.0, 1.0, 0.45, 1.3, 1.2, 2.35, paint, 0.14)
    B("wscreen", -0.92, 0.92, 1.35, 2.2, 1.17, 1.24, winD, 0.03)
    for sx in (-1, 1):
        B("vwin", sx * 1.0 - 0.02, sx * 1.0 + 0.02, 1.45, 2.15, 0.2, 1.1, winD, 0.02)
        uv_plane("vdecal", 3.8, 0.95, decal_mat("vanD", "van_side.png"), (sx * 1.006, 1.0, 1.25), rot_z=sx * math.pi / 2, parent=root)
        B("mirror", sx * 1.0, sx * 1.22, 1.55, 1.85, 1.0, 1.1, black, 0.01) if sx > 0 else B("mirror", -1.22, -1.0, 1.55, 1.85, 1.0, 1.1, black, 0.01)
    B("bumpF", -1.03, 1.03, 0.38, 0.6, 2.3, 2.48, chromeG, 0.03); B("bumpR", -1.03, 1.03, 0.38, 0.58, -2.72, -2.55, chromeG, 0.03)
    B("grille", -0.65, 0.65, 0.68, 1.12, 2.34, 2.37, black, 0.0)
    for sx in (-1, 1): B("vlamp", sx * 0.75 - 0.15, sx * 0.75 + 0.15, 0.82, 1.08, 2.34, 2.38, lampm, 0.01)
    wheel_pair(root, 0.9, 1.55, 0.38, 0.26, chromeG, ws); wheel_pair(root, 0.9, -1.75, 0.38, 0.26, chromeG, ws)
    return root, ws

def make_fueltruck():
    def build():
        root = bpy.data.objects.new("ftruck", None); bpy.context.collection.objects.link(root)
        cab = flat("ftCab", hexc("#e8e6e0"), 0.3, coat=0.6)
        def B(n, x0, x1, y0, y1, z0, z1, m, b=0.05): return box(n, x0, x1, -z1, -z0, y0, y1, m, root, b)
        B("cab", -1.2, 1.2, 0.7, 3.0, 3.2, 5.4, cab, 0.15); B("cabwin", -1.1, 1.1, 2.0, 2.85, 5.38, 5.43, winD, 0.02)
        for sx in (-1, 1): B("cabsw", sx * 1.2 - 0.02, sx * 1.2 + 0.02, 2.0, 2.8, 3.6, 4.9, winD, 0.02)
        B("chassis", -1.0, 1.0, 0.6, 0.9, -5.4, 5.4, ink, 0.03)
        loft("tank", [(3.0, 0.2, 0.2, 2.0), (2.9, 1.15, 1.0, 2.0), (-5.2, 1.15, 1.0, 2.0), (-5.3, 0.2, 0.2, 2.0)], chromeG, root, 32)
        for sx in (-1, 1): uv_plane("tdecal", 6.0, 1.5, decal_mat("truckD", "truck_side.png"), (sx * 1.17, 1.1, 2.0), rot_z=sx * math.pi / 2, parent=root)
        cyl("reel", 0.55, tl(-1.25, 1.5, -2.0), tl(1.25, 1.5, -2.0), redm, root, 24)
        wheel_pair(root, 1.05, 4.3, 0.55, 0.4); wheel_pair(root, 1.05, -2.8, 0.55, 0.45); wheel_pair(root, 1.05, -4.1, 0.55, 0.45)
    return coll_from(build, "ftruck")

def make_glider():
    root = bpy.data.objects.new("glider", None); bpy.context.collection.objects.link(root)
    gw = flat("glW", hexc("#f8f8f6"), 0.2, coat=0.9); gr = flat("glR", hexc("#d8262e"), 0.3, coat=0.7)
    loft("gfuse", [(3.6, 0.05, 0.05, 0.0), (3.2, 0.32, 0.36, 0.0), (2.0, 0.36, 0.42, 0.05), (0.0, 0.3, 0.36, 0.1), (-2.5, 0.12, 0.14, 0.18), (-4.6, 0.06, 0.08, 0.25)], gw, root, 24)
    ball("canopy", 0.36, tl(0, 0.28, 2.0), glass_mat("glCan", "#9ac8f0", 0.18), root, (0.8, 2.6, 0.75))
    for sx in (-1, 1):
        surface("gwing", (sx * 0.25, 0.3, 0.9, 1.15, 0.16, False), (sx * 8.0, 0.65, 0.6, 0.5, 0.06, False), gw, root)
        box("gtip", sx * 7.6 - 0.25 if sx > 0 else -8.0, sx * 8.0 if sx > 0 else -7.6, -0.6, -0.1, 0.64, 0.68, gr, root, 0.0)
    surface("gfin", (0, 0.2, -3.7, 1.0, 0.1, True), (0, 1.3, -4.4, 0.6, 0.05, True), gr, root)
    surface("gstab", (-1.3, 1.3, -4.2, 0.55, 0.05, False), (1.3, 1.3, -4.3, 0.4, 0.04, False), gw, root)
    return root, []

# ================================================================================================ STRIP (x 0): Gimli drag strip
SX = 0.0
plane("stripgrass", SX - 1600, SX + 1600, -1600, 1600, 0.0, grassm)
plane("runway", SX - 30, SX + 30, -700, 900, 0.03, asph)
for x in (-29, 29): plane("rwedge", SX + x - 0.25, SX + x + 0.25, -700, 900, 0.035, white)
for z in range(-680, 900, 30): plane("rwcl", SX + 14.5, SX + 15.5, -z - 12, -z, 0.035, white)          # old runway centreline (east half)
plane("strip", SX - 12, SX - 0.4, -420, 250, 0.034, asph2)                                                  # the darker rubbered drag lanes
for z in range(-250, 420, 4): plane("rubber", SX - 10.5 + (z % 8) * 0.1, SX - 7.5, -z - 3, -z, 0.0345, flat("rubberMark", hexc("#3a3a40"), 0.8)) if z > 300 else None
plane("startline", SX - 12, SX - 0.4, -330.4, -329.6, 0.036, white)
# guardrail: concrete footing + steel W-beam along x = 0 (the jet straddled it), posts by array modifier
B3("railfoot", SX - 0.25, SX + 0.25, 0.0, 0.3, -260, 420, conc)
rail = B3("rail", SX - 0.12, SX + 0.12, 0.45, 0.85, -260, 420, metal, 0.02)
post = B3("railpost", SX - 0.08, SX + 0.08, 0.0, 0.85, -260, -259.8, metal)
am = post.modifiers.new("arr", "ARRAY"); am.count = 340; am.use_relative_offset = False; am.use_constant_offset = True; am.constant_offset_displace = (0, -2.0 / post.scale[1], 0)
# the start tree (lights) and the start gantry with the banners
B3("treepole", SX - 0.6, SX - 0.45, 0.0, 3.2, 330.3, 330.45, black)
for k, c in enumerate(("#ffd84a", "#ffd84a", "#ffd84a", "#3cff6a", "#ff3a3a")):
    for sxl in (-0.9, -0.15):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.11, location=(SX + sxl, -330.2, 2.9 - k * 0.32)); o = bpy.context.object; o.data.materials.append(flat("tlamp%d" % k, hexc(c), 0.2, emit=hexc(c)))
for x in (-13.0, 1.2): B3("gantry", SX + x - 0.2, SX + x + 0.2, 0.0, 6.4, 332, 332.4, metal)
B3("gantrybeam", SX - 13.2, SX + 1.4, 6.0, 6.5, 332, 332.4, metal)
P3("bstart", "banner_start.png", 13.5, 2.5, SX - 5.9, 4.6, 331.9, math.pi, emit=0.25)
P3("bstartB", "banner_start.png", 13.5, 2.5, SX - 5.9, 4.6, 332.5, 0, emit=0.25)
# race control tower, sponsor boards along the strip, the FAMILY DAY banner on a scaffold, the park sign
B3("tower", SX + 18, SX + 24, 0.0, 7.5, 318, 326, flat("towerW", hexc("#f2ece0"), 0.5))
B3("towercab", SX + 17.6, SX + 24.4, 7.5, 10.0, 317.6, 326.4, winD, 0.05); B3("towerroof", SX + 17.2, SX + 24.8, 10.0, 10.4, 317.2, 326.8, redm, 0.05)
P3("towersign", "board2.png", 6.0, 1.5, SX + 21, 6.3, 317.95, math.pi, emit=0.25)
for k, z in enumerate(range(250, 330, 10)):
    for side, x in ((-1, -15.5), (1, 3.0)):
        P3("board", "board%d.png" % (k % 3), 4.0, 1.0, SX + x, 0.55, z, side * -math.pi / 2, emit=0.2)
for x in (-24, -10): B3("scaf", SX + x - 0.12, SX + x + 0.12, 0.0, 7.0, 345, 345.24, metal)
P3("bfam", "banner_family.png", 14.0, 3.5, SX - 17, 5.0, 344.8, math.pi, emit=0.3)
P3("bfamB", "banner_family.png", 14.0, 3.5, SX - 17, 5.0, 345.45, 0, emit=0.3)
P3("parksign", "sign_gimli.png", 8.0, 4.0, SX + 40, 4.0, 300, math.pi * 0.85, emit=0.25)
for x in (36.5, 43.5): B3("parkpost", SX + x - 0.15, SX + x + 0.15, 0.0, 2.2, 299.8, 300.2, white)
# pits and Family Day: campers, tents, cars, BBQs, picnic tables, coolers, flags (both sides of the strip end)
def camper(x, z, yaw, col):
    def b():
        r = bpy.data.objects.new("camper", None); bpy.context.collection.objects.link(r)
        bodym = flat("camperW%s" % col, hexc("#f4f0e6"), 0.4, coat=0.4); st = flat("camperS%s" % col, hexc(col), 0.4)
        box("cb", -1.2, 1.2, -3.5, 3.5, 0.5, 3.0, bodym, r, 0.25); box("cs", -1.21, 1.21, -3.5, 3.5, 1.3, 1.6, st, r, 0.0)
        box("cw", -1.22, 1.22, -2.6, -0.6, 1.8, 2.4, winD, r, 0.02); box("cd", 1.205, 1.225, 1.0, 1.9, 0.6, 2.6, st, r, 0.0)
        box("awning", 1.2, 3.4, -3.0, 0.5, 2.6, 2.7, flat("awn%s" % col, hexc(col), 0.5), r, 0.0)
        for zz in (-2.9, 0.4): box("awpole", 3.3, 3.38, zz, zz + 0.08, 0.0, 2.6, metal, r, 0.0)
        for zz in (-2.4, 2.4): cyl("cwh", 0.4, (-1.25, zz, 0.42), (1.25, zz, 0.42), rubber, r, 18)
    c = coll_from(b, "camper%s" % col); place_coll(c, x, 0, z, yaw)
def tent(x, z, col, s=1.0):
    def b():
        r = bpy.data.objects.new("tent", None); bpy.context.collection.objects.link(r); m = flat("tent%s" % col, hexc(col), 0.6)
        bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=2.1 * s, radius2=0.05, depth=1.1 * s, location=(0, 0, 2.6 * s), rotation=(0, 0, math.pi / 4)); o = bpy.context.object; o.data.materials.append(m); o.parent = r
        box("valance", -1.5 * s, 1.5 * s, -1.5 * s, 1.5 * s, 2.0 * s, 2.06 * s, m, r, 0.0)
        for px in (-1.45, 1.45):
            for pz in (-1.45, 1.45): box("tp", px * s - 0.04, px * s + 0.04, pz * s - 0.04, pz * s + 0.04, 0.0, 2.05 * s, metal, r, 0.0)
    c = coll_from(b, "tent%s" % col); place_coll(c, x, 0, z, 0)
def bbq(x, z):
    def b():
        r = bpy.data.objects.new("bbq", None); bpy.context.collection.objects.link(r)
        ball("kettle", 0.38, (0, 0, 0.85), black, r, (1, 1, 0.75)); box("grate", -0.36, 0.36, -0.36, 0.36, 0.86, 0.88, chromeG, r, 0.0)
        for a in range(3): cyl("leg", 0.025, (0, 0, 0.6), (0.4 * math.cos(a * 2.1), 0.4 * math.sin(a * 2.1), 0.0), chromeG, r, 8)
        for k in range(4): box("sausage", -0.25 + k * 0.15, -0.18 + k * 0.15, -0.2, 0.2, 0.88, 0.94, flat("saus", hexc("#a8502a"), 0.4), r, 0.02)
    c = coll_from(b, "bbq%d" % int(x * 10)); place_coll(c, x, 0, z, 0)
def table(x, z, col="#b8844c"):
    def b():
        r = bpy.data.objects.new("table", None); bpy.context.collection.objects.link(r); m = flat("tbl%s" % col, hexc(col), 0.6)
        box("top", -0.9, 0.9, -0.4, 0.4, 0.72, 0.78, m, r, 0.01)
        for sz in (-0.75, 0.75): box("bench", -0.9, 0.9, sz - 0.15, sz + 0.15, 0.42, 0.47, m, r, 0.01)
        for sx in (-0.8, 0.8): box("leg", sx - 0.04, sx + 0.04, -0.85, 0.85, 0.0, 0.72, m, r, 0.0)
        box("cooler", -0.3, 0.1, -0.2, 0.15, 0.78, 1.05, flat("cool", hexc("#2f6ad8"), 0.4), r, 0.03); box("coolerlid", -0.3, 0.1, -0.2, 0.15, 1.05, 1.1, white, r, 0.02)
    c = coll_from(b, "table%s" % col); place_coll(c, x, 0, z, 0)
def flagpole(x, z, col):
    B3("fpole", x - 0.04, x + 0.04, 0.0, 6.0, z - 0.04, z + 0.04, metal)
    me = bpy.data.meshes.new("flag"); me.from_pydata([tl(x, 5.9, z), tl(x + 1.6, 5.5, z + 0.2), tl(x + 1.6, 4.7, z + 0.2), tl(x, 4.9, z)], [], [(0, 1, 2, 3)]); me.update()
    o = obj("flag", me, flat("flag%s" % col, hexc(col), 0.6)); o.data.materials[0].use_backface_culling = False
CAMPER_COLS = ["#d8262e", "#2f6ad8", "#2f9a6a", "#f07a1e", "#7a3ab8"]
for k, (x, z) in enumerate([(-34, 360), (-48, 395), (-30, 430), (24, 372), (40, 405), (28, 448), (-58, 440), (52, 365)]):
    camper(SX + x, z, math.radians(80 + 25 * hh(k, 3)), CAMPER_COLS[k % 5])
for k, (x, z) in enumerate([(-22, 352), (-40, 372), (-26, 408), (18, 356), (32, 388), (16, 425), (-46, 420), (46, 430)]):
    tent(SX + x, z, ["#ffd84a", "#ff5a5a", "#5ab0ff", "#ffffff", "#ff9a3a", "#8ae05a"][k % 6], 1.0 + 0.2 * hh(k, 5))
for k, (x, z) in enumerate([(-18.7, 359.0), (-36, 384), (20, 366), (35, 398), (-28, 420)]): bbq(SX + x, z); table(SX + x - 2.6, z - 1.6)
for k, (x, z) in enumerate([(-15, 345), (-15, 365), (3, 345), (3, 370), (-15, 390), (3, 395)]): flagpole(SX + x, z, ["#d8262e", "#ffd84a", "#2f6ad8"][k % 3])
# parked race cars in the pits (static) and the crowd's cars further out
DRAG_COLS = ["#ffd02a", "#2f6ad8", "#f4f4f2"]
for k, (x, z, yaw) in enumerate([(-18, 340, 1.4), (6, 342, -1.6), (-24, 378, 0.9)]):
    root, _ = make_dragster(DRAG_COLS[k % 3], "dragP%d" % k); root.location = T(SX + x, 0, z); root.rotation_euler = (0, 0, yaw)
MUSCLE_COLS = [("#d8262e", "#f4f4f2"), ("#2a2a32", "#f2c230"), ("#2f9a6a", "#f4f4f2"), ("#f07a1e", "#1d1b22"), ("#5ab0ff", "#f4f4f2"), ("#ffd02a", "#1d1b22")]
for k in range(14):
    x = (-70 - 6 * (k % 7)) if k < 7 else (60 + 6 * (k % 7)); z = 300 + 8 * (k % 7) + 40 * (k // 7)
    c1, c2 = MUSCLE_COLS[k % 6]; root, _ = make_muscle(c1, "mcP%d" % k, c2); root.location = T(SX + x, 0, z); root.rotation_euler = (0, 0, math.radians(90 + 8 * (hh(k, 2) - 0.5)))
# old air-base hangars (arched roofs) and the lake far to the west
for k, z in enumerate((40, 110, 180)):
    B3("hangarwall", SX + 110, SX + 150, 0.0, 9.0, z - 22, z + 22, flat("hangW%d" % k, hexc(["#d8cfc0", "#c8d0d8", "#d8c8b8"][k]), 0.6))
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=20.5, depth=44.4, location=(SX + 130, -z, 9.0), rotation=(math.pi / 2, 0, 0)); o = bpy.context.object
    o.scale = (1, 0.55, 1); o.data.materials.append(flat("hangR%d" % k, hexc(["#8a96a8", "#a89a8a", "#96a08a"][k]), 0.5, 0.3)); bpy.ops.object.shade_smooth()
    B3("hangdoor", SX + 109.8, SX + 110.0, 0.0, 8.0, z - 14, z + 14, flat("hangD", hexc("#5a6a7a"), 0.5, 0.4))
plane("lake", SX - 2400, SX - 260, -2400, 2400, -0.2, water)
for k in range(140):
    a = hh(k, 1); side = -1 if k % 2 else 1
    x = SX + side * (70 + 260 * hh(k, 4)) if k % 3 else SX + 180 + 400 * a; z = -650 + 1500 * hh(k, 7)
    if x < SX - 250: continue
    inst(["CommonTree_1", "CommonTree_2", "CommonTree_3", "CommonTree_4"][k % 4], x, z, 9 + 6 * hh(k, 9), 6.28 * hh(k, 11))
for k in range(60): inst(["Bush_Common_Flowers", "Bush_Common", "Grass_Common_Tall"][k % 3], SX + (-40 if k % 2 else 40) + 30 * (hh(k, 2) - 0.5), 200 + 300 * hh(k, 3), 1.0 + hh(k, 4), 6.28 * hh(k, 5))

# ================================================================================================ RAMP (x 3000): the gate
RX = 3000.0
plane("apron", RX - 400, RX + 400, -400, 400, 0.0, apron)
for z in range(-120, 60, 1): pass
plane("leadline", RX - 0.15, RX + 0.15, -40, 40, 0.012, yel)                     # yellow lead-in line under the nose wheel
for z in (-30, -10, 10, 30): plane("stopbar", RX - 3, RX + 3, -z - 0.15, -z + 0.15, 0.012, yel)
plane("redzone", RX - 30, RX + 30, -46.2, -45.8, 0.012, redm)
# terminal: concrete base, glass curtain wall, roof band, the city sign (two signs, one per city, toggled as vehicles)
B3("termbase", RX - 90, RX + 90, 0.0, 3.5, 46, 70, conc); B3("termglass", RX - 90, RX + 90, 3.5, 12.0, 46.2, 70, winD, 0.05)
B3("termband", RX - 90.5, RX + 90.5, 12.0, 14.0, 45.5, 70.5, flat("termBand", hexc("#e8e2d6"), 0.5))
for x in range(-88, 90, 6): B3("mullion", RX + x - 0.12, RX + x + 0.12, 3.5, 12.0, 45.9, 46.2, metal)
B3("jetbridge", RX - 1.5, RX + 1.5, 3.6, 6.4, 30, 46, flat("bridgeG", hexc("#d0d4dc"), 0.4, 0.3), 0.1)
for x in (-60, -30, 30, 60): B3("lightpole", RX + x - 0.2, RX + x + 0.2, 0.0, 22.0, 20, 20.4, metal); B3("lighthead", RX + x - 1.4, RX + x + 1.4, 21.5, 22.2, 19.6, 20.8, lampm)
def citysign(file, name):
    def b():
        r = bpy.data.objects.new(name, None); bpy.context.collection.objects.link(r)
        uv_plane(name + "p", 24.0, 6.0, tex_mat("m_" + file, file, emit=0.35, rough=0.5), (0, 0, 0), rot_z=math.pi, parent=r)
    return b
SIGNS = {}
for nm, fl in (("mtl", "sign_mtl.png"), ("ott", "sign_ott.png")):
    before = set(bpy.data.objects); citysign(fl, nm)(); r = [o for o in bpy.data.objects if o not in before and o.parent is None][0]; SIGNS[nm] = (r, [])
# ground equipment: the fuel truck at the left wing, baggage carts, a tug, cones, chocks, a stair truck
FT = make_fueltruck(); place_coll(FT, RX - 14.5, 0, -1.5, math.pi)
def cart(x, z, k):
    def b():
        r = bpy.data.objects.new("cart", None); bpy.context.collection.objects.link(r)
        box("cbase", -0.9, 0.9, -1.4, 1.4, 0.4, 0.55, ink, r, 0.02); box("ctop", -0.9, 0.9, -1.4, 1.4, 1.9, 2.0, flat("cartTop", hexc("#2f6ad8"), 0.4), r, 0.02)
        for sx in (-0.85, 0.85):
            for sz in (-1.35, 1.35): box("cp", sx - 0.04, sx + 0.04, sz - 0.04, sz + 0.04, 0.55, 1.9, metal, r, 0.0)
        for j in range(3): box("bag", -0.7 + j * 0.5, -0.3 + j * 0.5, -1.0 + 0.3 * j, -0.2 + 0.3 * j, 0.55, 1.1 + 0.15 * j, flat("bag%d" % j, hexc(["#d8262e", "#2a2a32", "#2f9a6a"][j]), 0.5), r, 0.06)
        for sx in (-0.8, 0.8):
            for sz in (-1.1, 1.1): cyl("cwh", 0.22, (sx - 0.08, sz, 0.22), (sx + 0.08, sz, 0.22), rubber, r, 12)
    c = coll_from(b, "cart%d" % k); place_coll(c, x, 0, z, 0.1 * k)
for k in range(4): cart(RX + 14 + 3.2 * k, -8 - 1.0 * k, k)
for k, (x, z) in enumerate([(-3, 22), (3, 22), (-24, -6), (24, -6), (-6, -24), (6, -24)]):
    bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=0.22, radius2=0.03, depth=0.75, location=(RX + x, -z, 0.375)); o = bpy.context.object; o.data.materials.append(orange)
JETRAMP = {"x": RX, "z": 0.0}

# ================================================================================================ COCKPIT (x 6000): pilots face +z
CX6 = 6000.0
cockm = flat("cockGrey", hexc("#4a4e58"), 0.6); cockd = flat("cockDark", hexc("#2a2c32"), 0.5); cockl = flat("cockLight", hexc("#8a8f9a"), 0.5)
B3("cfloor", CX6 - 1.8, CX6 + 1.8, 0.0, 0.05, -2.5, 2.2, cockd)
B3("cpanel", CX6 - 1.6, CX6 + 1.6, 0.6, 1.62, 1.25, 1.55, cockm, 0.04)                 # main panel
B3("glare", CX6 - 1.65, CX6 + 1.65, 1.62, 1.74, 1.05, 1.6, cockd, 0.05)                # glareshield
P3("scroff", "screens_off.png", 2.9, 0.72, CX6, 1.25, 1.245, math.pi, emit=0.0)
B3("pedestal", CX6 - 0.28, CX6 + 0.28, 0.0, 0.6, 0.2, 1.1, cockm, 0.04)
P3("fuelgauge", "fuel_blank.png", 0.46, 0.23, CX6, 0.745, 1.245, math.pi, emit=0.5, off=0.03)
for k in range(2):
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.03, depth=0.45, location=(CX6 - 0.08 + 0.16 * k, -0.6, 0.72), rotation=(math.radians(-60), 0, 0)); o = bpy.context.object; o.data.materials.append(cockl)
    ball("knob", 0.05, (CX6 - 0.08 + 0.16 * k, -0.48, 0.92), black)
for sx in (-1, 1):   # the two yokes on their columns
    x = CX6 + sx * 0.55
    cyl("ycol", 0.05, tl(x, 0.0, 0.95), tl(x, 0.95, 0.7), cockd, None, 12)
    cyl("yhub", 0.07, tl(x, 0.98, 0.62), tl(x, 0.98, 0.72), cockl, None, 14)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.17, minor_radius=0.025, location=tl(x, 0.98, 0.62), rotation=(math.pi / 2, 0, 0)); o = bpy.context.object; o.scale = (1.3, 1, 0.75); o.data.materials.append(cockd)
    B3("seatback", x - 0.32, x + 0.32, 0.45, 1.5, -0.62, -0.42, flat("seatB", hexc("#5a4a3e"), 0.7), 0.08)
    B3("seatpan", x - 0.32, x + 0.32, 0.38, 0.5, -0.45, 0.15, flat("seatB", hexc("#5a4a3e"), 0.7), 0.06)
# window frames (the sky shows through), side walls, ceiling, overhead panel
for sx in (-1, 1):
    B3("cwall", CX6 + sx * 1.7, CX6 + sx * 1.8, 0.0, 2.2, -2.5, 1.6, cockm)
    B3("sidesill", CX6 + sx * 1.6, CX6 + sx * 1.8, 1.05, 1.15, -1.0, 1.6, cockd)
B3("cceil", CX6 - 1.8, CX6 + 1.8, 2.35, 2.45, -2.5, 1.2, cockm)
P3("overhead", "overhead.png", 1.6, 0.8, CX6, 2.3, 0.8, math.pi, emit=0.2)
for x in (-1.15, -0.35, 0.35, 1.15): B3("wpost", CX6 + x - 0.04, CX6 + x + 0.04, 1.74, 2.38, 1.45, 1.55, cockd)
B3("wtop", CX6 - 1.7, CX6 + 1.7, 2.3, 2.38, 1.3, 1.6, cockd)
# the lit screens and the warning light are vehicles (shown/hidden per frame)
def screen_on():
    r = bpy.data.objects.new("scron", None); bpy.context.collection.objects.link(r)
    uv_plane("scrp", 2.9, 0.72, tex_mat("m_scron", "screens_on.png", emit=2.2, rough=0.3), (0, 0, 0), rot_z=math.pi, parent=r)
    return r, []
def warn_light():
    r = bpy.data.objects.new("warn", None); bpy.context.collection.objects.link(r)
    uv_plane("warnp", 0.36, 0.18, tex_mat("m_warn", "warn.png", emit=6.0, rough=0.3), (0, 0, 0), rot_z=math.pi, tilt=math.radians(-35), parent=r)
    L = bpy.data.lights.new("warnL", "POINT"); L.energy = 60; L.color = hexc("#ff3020"); L.shadow_soft_size = 0.1; lo = obj("warnL", L, None, (0, -0.25, 0.1), r)
    return r, []
area_light("cockfill", CX6, 2.25, -0.4, 1.4, 60, "#ffe6c8")

# ================================================================================================ SKY (x 9000): above the clouds
KX = 9000.0
def puff_lib():
    out = []
    for k in range(4):
        def b(k=k):
            r = bpy.data.objects.new("puff", None); bpy.context.collection.objects.link(r)
            for j in range(6):
                a = 2 * math.pi * j / 6 + k; rr = 6 + 4 * hh(j, k)
                ball("pb", rr, (14 * math.cos(a) * hh(j + 3, k), 14 * math.sin(a) * hh(j + 5, k), rr * 0.35), cloudm, r, (1, 1, 0.55), 16)
            ball("pc", 13, (0, 0, 4), cloudm, r, (1.2, 1.2, 0.6), 20)
        out.append(coll_from(b, "puff%d" % k))
    return out
PUFFS = puff_lib()
for k in range(260):
    x = KX + (hh(k, 1) - 0.5) * 2400; z = (hh(k, 2) - 0.5) * 3000; y = -95 - 25 * hh(k, 3)
    place_coll(PUFFS[k % 4], x, y, z, 6.28 * hh(k, 4), 1.4 + 1.6 * hh(k, 5))
plane("cloudfloor", KX - 1800, KX + 1800, -2000, 2000, -100, cloudm)
for k in range(40):   # a few towering cumulus near the glider (x 9600)
    place_coll(PUFFS[k % 4], KX + 600 + (hh(k, 6) - 0.5) * 500, -30 + 25 * hh(k, 7), (hh(k, 8) - 0.5) * 700, 6.28 * hh(k, 9), 0.6 + 0.8 * hh(k, 10))

# ================================================================================================ ROAD (x 12000): the van runs dry
DX = 12000.0
plane("fields", DX - 1500, DX + 1500, -1500, 1500, 0.0, wheat)
plane("verge", DX - 9, DX + 9, -1500, 1500, 0.02, grassd)
plane("road2", DX - 3.6, DX + 3.6, -1500, 1500, 0.04, asph)
for z in range(-1500, 1500, 9): plane("cl", DX - 0.08, DX + 0.08, -z - 4, -z, 0.045, yel)
for x in (-3.4, 3.4): plane("edge", DX + x - 0.07, DX + x + 0.07, -1500, 1500, 0.045, white)
for z in range(-600, 900, 45):   # telephone poles with three wires
    B3("tpole", DX + 7.5 - 0.15, DX + 7.5 + 0.15, 0.0, 9.0, z - 0.15, z + 0.15, flat("poleW", hexc("#6a4a32"), 0.8))
    B3("tarm", DX + 6.4, DX + 8.6, 8.2, 8.35, z - 0.1, z + 0.1, flat("poleW", hexc("#6a4a32"), 0.8))
for x in (6.6, 7.5, 8.4): cyl("wire", 0.015, tl(DX + x, 8.2, -600), tl(DX + x, 8.2, 900), black, None, 6)
for z in range(-600, 900, 4): B3("fence", DX - 10.2, DX - 10.05, 0.0, 1.1, z - 0.05, z + 0.05, flat("fenceW", hexc("#8a6a4a"), 0.8)) if z % 12 == 0 else None
cyl("fencewire", 0.012, tl(DX - 10.1, 0.95, -600), tl(DX - 10.1, 0.95, 900), metal, None, 6)
def farm(x, z):
    B3("barn", x - 6, x + 6, 0.0, 6.0, z - 8, z + 8, flat("barnR", hexc("#b8322a"), 0.6))
    me = bpy.data.meshes.new("barnroof"); me.from_pydata([tl(x - 6.6, 6, z - 8.4), tl(x + 6.6, 6, z - 8.4), tl(x, 10, z - 8.4), tl(x - 6.6, 6, z + 8.4), tl(x + 6.6, 6, z + 8.4), tl(x, 10, z + 8.4)], [], [(0, 2, 5, 3), (1, 4, 5, 2), (0, 1, 2), (3, 5, 4)]); me.update()
    obj("barnroof", me, flat("barnRoof", hexc("#4a4e58"), 0.5)); cyl("silo", 3.0, tl(x + 10, 0, z), tl(x + 10, 14, z), metal, None, 24); ball("silotop", 3.0, tl(x + 10, 14, z), metal, None, (1, 1, 0.6))
farm(DX - 70, 120); farm(DX + 90, -160)
for k in range(80): inst(["CommonTree_1", "CommonTree_2", "CommonTree_3"][k % 3], DX + (-1 if k % 2 else 1) * (40 + 400 * hh(k, 3)), -600 + 1500 * hh(k, 4), 8 + 5 * hh(k, 5), 6.28 * hh(k, 6))
P3("roadsign", "sign_gimli.png", 3.0, 1.5, DX + 5.2, 2.6, 260, math.pi, emit=0.2); B3("rspost", DX + 5.1, DX + 5.3, 0.0, 1.9, 259.9, 260.1, metal)

# ------------------------------------------------------------------------------------------------ vehicles
DRAG = make_dragster("#ffd02a", "dragR"); DRAG2 = make_dragster("#2f6ad8", "dragR2")
# the evacuation slide (yellow, steep: the nose was on the ground so the tail sat high), placed by the story
def make_slide():
    r = bpy.data.objects.new("slide", None); bpy.context.collection.objects.link(r); m = flat("slideY", hexc("#f2c230"), 0.35, coat=0.5)
    L = 9.5; ang = math.radians(48)
    for sx in (-0.75, 0.75): cyl("sliderail", 0.32, (sx, 0, 0), (sx, -L * math.cos(ang), -L * math.sin(ang)), m, r, 16)
    me = bpy.data.meshes.new("slidebed"); me.from_pydata([(-0.7, 0, -0.1), (0.7, 0, -0.1), (0.7, -L * math.cos(ang), -L * math.sin(ang) - 0.1), (-0.7, -L * math.cos(ang), -L * math.sin(ang) - 0.1)], [], [(0, 1, 2, 3)]); me.update()
    obj("slidebed", me, m, (0, 0, 0), r)
    return r, []
VEHICLES = {"jet": (JET, JETW), "fanL": (FANROOT[1], [FANSPIN[1]]), "fanR": (FANROOT[-1], [FANSPIN[-1]]), "slide": make_slide(), "ngear": make_nosegear(), "drag": DRAG, "drag2": DRAG2, "van": make_van(), "glider": make_glider(),
            "scron": screen_on(), "warn": warn_light(), "mtl": SIGNS["mtl"], "ott": SIGNS["ott"]}

# ------------------------------------------------------------------------------------------------ colour moods + skies
# (sun elevation, azimuth deg, sun colour, sun strength, sky strength, sky index into SKIES)
SKIES = ["grad:#ff9448:#ffc27a:#86b4ea:#3d6cc4:az=262:el=9:halo=3.0", "kloofendal_48d_partly_cloudy_puresky",
         "grad:#ff7a40:#ffb074:#9a8ac6:#2c3c84:az=248:el=7:halo=3.0", "grad:#ff6a34:#ffa060:#a888c0:#34407e:az=255:el=3:halo=3.5"]
MOOD = {"strip": (9, 262, "#ffaa66", 7.0, 1.1, 0), "ramp": (42, 145, "#fff4e2", 4.6, 1.0, 1), "cockday": (42, 145, "#fff4e2", 4.0, 1.0, 1),
        "cruise": (7, 248, "#ff9c5c", 6.5, 0.95, 2), "cockpit": (7, 248, "#ffa868", 5.5, 1.0, 2), "glider": (58, 160, "#fffaf0", 4.8, 1.0, 1),
        "road": (4, 255, "#ffb688", 4.6, 1.1, 3)}
SID_SET = {}
for fr_ in data["frames"]: SID_SET[fr_["id"]] = fr_.get("set", "strip")
def mood_of(sid):
    return SID_SET.get(sid, "strip")
