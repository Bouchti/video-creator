"""A toilet cut in half down its middle (y = 0): porcelain bowl, S-trap, cistern, seat; blue water."""
import bpy
from mathutils import Vector

from engine.director import lib
from engine.flush import parts as P

V = Vector


def _apply(ob):
    """Bake every modifier into the mesh (exact booleans are slow to re-evaluate on every frame)."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(old)
    return ob


def boolean(target, cutter, op="DIFFERENCE"):
    mod = target.modifiers.new(f"b_{cutter.name}", "BOOLEAN")
    mod.operation = op
    mod.object = cutter
    mod.solver = "EXACT"
    if hasattr(mod, "material_mode"):
        mod.material_mode = "TRANSFER"
    _apply(target)
    bpy.data.objects.remove(cutter)
    # A cut face with a notch is one big concave n-gon, and the renderer's own triangulation of it can leave
    # a triangle out (the background showed through the plant's soil face). Triangulate it here, properly.
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(target.data)
    big = [f for f in bm.faces if len(f.verts) > 4]
    if big:
        bmesh.ops.triangulate(bm, faces=big, quad_method="BEAUTY", ngon_method="EAR_CLIP")
        bm.to_mesh(target.data)
    bm.free()
    return target


def cut_front(ob, cut_mat, keep_y0=0.0007):
    """Remove everything in front of the section plane; the new faces get cut_mat."""
    c = lib.box(f"{ob.name}_cutter", -60, 60, -60, keep_y0, -60, 60, cut_mat, ob.parent)
    return boolean(ob, c)


def ellipsoid(name, center, radii, mat, parent=None, seg=48):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=seg // 2, radius=1.0, location=(0, 0, 0))
    ob = bpy.context.active_object
    ob.name = name
    for v in ob.data.vertices:
        v.co = V((v.co.x * radii[0] + center[0], v.co.y * radii[1] + center[1], v.co.z * radii[2] + center[2]))
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.use_smooth = True
    if parent is not None:
        ob.parent = parent
    return ob


def frustum(name, z0, z1, r0, r1, mat, parent=None, seg=48, x=0.0):
    bpy.ops.mesh.primitive_cone_add(vertices=seg, radius1=1.0, radius2=1.0, depth=1.0, location=(0, 0, 0))
    ob = bpy.context.active_object
    ob.name = name
    for v in ob.data.vertices:
        top = v.co.z > 0
        rx, ry = (r1 if top else r0)
        v.co = V((v.co.x * rx + x, v.co.y * ry, z1 if top else z0))
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.use_smooth = True
    if parent is not None:
        ob.parent = parent
    return ob


TRAP = [(-0.03, 0.0, 0.25), (0.04, 0.0, 0.17), (0.12, 0.0, 0.24), (0.17, 0.0, 0.34), (0.24, 0.0, 0.3),
        (0.25, 0.0, 0.12), (0.25, 0.0, -0.12)]
WATER_Z = 0.335


def build(parent, flush_f0=1, flush_f1=60):
    """The toilet at the parent's origin, floor at z = 0, bowl opening toward -x, cistern at +x.
    Returns handles for the animation."""
    por, cutm = P.porcelain(), P.porcelain_cut()
    body = frustum("wc_pedestal", 0.0, 0.27, (0.15, 0.12), (0.17, 0.14), por, parent, x=0.06)
    bowl = ellipsoid("wc_bowl", (-0.05, 0, 0.33), (0.29, 0.21, 0.16), por, parent)
    boolean(body, bowl, "UNION")
    tank = lib.box("wc_tank", 0.23, 0.45, -0.24, 0.24, 0.43, 0.8, por, parent, bevel=0.03)
    tank.modifiers[0].segments = 3
    _apply(tank)
    boolean(body, tank, "UNION")
    neck = lib.box("wc_neck", 0.12, 0.3, -0.14, 0.14, 0.2, 0.47, por, parent)
    boolean(body, neck, "UNION")
    inner = ellipsoid("wc_inner", (-0.06, 0, 0.42), (0.24, 0.165, 0.165), cutm, parent)
    boolean(body, inner)
    top = lib.box("wc_top", -1, 0.2, -1, 1, 0.405, 1.5, cutm, parent)
    boolean(body, top)
    cav = lib.box("wc_tankcav", 0.255, 0.425, -0.215, 0.215, 0.46, 0.85, cutm, parent)
    boolean(body, cav)
    cut_front(body, cutm, keep_y0=0.003)     # 3 mm behind the trap water's flat face, which lies on y = 0
    body.name = "toilet"
    # lid of the cistern + seat + raised cover
    lid = lib.box("wc_lid", 0.215, 0.465, 0.0, 0.26, 0.8, 0.84, por, parent, bevel=0.012)
    seat_mat = lib.flat("seat", lib.hexrgb("#F7F7F5"), 0.25, coat=0.6)
    seat = lib.box("wc_seat", -0.34, 0.17, 0.0, 0.2, 0.405, 0.43, seat_mat, parent, bevel=0.01)
    hole = ellipsoid("wc_seathole", (-0.07, 0, 0.42), (0.2, 0.135, 0.2), cutm, parent, seg=32)
    boolean(seat, hole)
    cover = lib.box("wc_cover", 0.17, 0.2, 0.0, 0.2, 0.43, 0.9, seat_mat, parent, bevel=0.01)
    cover.rotation_euler = (0, -0.22, 0)
    # blue water: bowl pool (swirling), trap stream, cistern
    blue = P.water("toilet_swirl", P.TOILET[0], P.TOILET[1], foam_amount=0.45, coord="Object",
                   scale=(3.0, 3.0, 3.0), swirl=4.0)
    pool = ellipsoid("wc_pool", (-0.06, 0, 0.42), (0.237, 0.162, 0.162), blue, parent)
    cap = lib.box("wc_poolcap", -1, 1, -1, 1, WATER_Z, 2, blue, parent)
    boolean(pool, cap)
    cut_front(pool, P.water_section("toilet_cut", P.TOILET[0], P.TOILET[2]))
    trap_w = P.pipe_water("wc_trapwater", TRAP, 0.034, level=0.98, mode="front",
                          mat=P.water("toilet_flow", P.TOILET[0], P.TOILET[1], speed=0.9, foam_amount=0.5),
                          section_mat=P.water_section("toilet_cut", P.TOILET[0], P.TOILET[2]), parent=parent,
                          bend=0.05, step=0.015)
    cistern = lib.box("wc_cistern", 0.258, 0.422, 0.0, 0.212, 0.47, 0.72,
                      P.water_section("toilet_cut", P.TOILET[0], P.TOILET[2]), parent)
    return {"body": body, "pool": pool, "trap_water": trap_w, "cistern": cistern, "lid": lid}
