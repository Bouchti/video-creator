"""
Production-quality engine parts (runs inside Blender). Each builder returns a finished object at the origin
in its own local frame; assemblies place and animate them. Dimensions in metres.

Frames:
  piston   origin at the wrist-pin centre, crown up (+Z)
  conrod   origin at the small end, big end at -Z (rod length below), swings about X
  crank    along X, rotates about X, origin on the axis
  valve    origin at the valve face centre, stem along +Z
  plug     origin at the electrode tip, body along +Z
  cam      along X, rotates about X
"""
from __future__ import annotations

import math

from mathutils import Matrix

from . import geo
from . import materials as M
from .rigs import crank as K


def _to_yz(obj):
    """Turn a part built in the XY plane (extruded along Z) so its outline lies in the YZ plane, thickness
    along X: X->Y, Y->Z, Z->X."""
    m = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    return geo.transform_mesh(obj, m)


def _along_x(obj):
    """Turn a lathe part (axis Z) so its axis runs along X."""
    return geo.transform_mesh(obj, Matrix.Rotation(math.radians(90), 4, "Y"))


# ---------------------------------------------------------------- piston

def piston(name: str, bore: float, ch: float, col=None):
    r = bore / 2 - 0.0002
    top = ch
    skirt = -0.028
    prof = [(0, top - 0.0025), (r * 0.55, top - 0.0008), (r - 0.0022, top), (r - 0.0005, top - 0.0004),
            (r, top - 0.0015)]
    z = top - 0.0045
    for g_top, g_h, depth in ((z, 0.0015, 0.0034), (z - 0.0045, 0.0015, 0.0034), (z - 0.009, 0.0028, 0.0030)):
        prof += [(r, g_top), (r - depth, g_top), (r - depth, g_top - g_h), (r, g_top - g_h)]
    prof += [(r, skirt + 0.0015), (r - 0.0012, skirt), (r - 0.0035, skirt), (r - 0.0035, top - 0.020),
             (r - 0.012, top - 0.0095), (0, top - 0.008)]
    body = geo.lathe(name, prof, 72, col, M.machined_aluminium(), angle=30)
    # pin bosses, and the struts that hang them from the crown
    boss = _along_x(geo.cylinder(name + "_boss", 0.0165, -r + 0.006, r - 0.006, 40, col, M.machined_aluminium()))
    geo.boolean(body, boss, "UNION")
    for s in (-1, 1):
        strut = geo.box(name + "_st", (0.010, 0.022, top - 0.004), (s * (r - 0.012), 0, (top - 0.004) / 2))
        geo.boolean(body, strut, "UNION")
    # slipper skirt: relieve the sides under the pin axis
    for s in (-1, 1):
        cut = geo.box(name + "_slip", (0.02, bore * 0.7, 0.05), (s * (r + 0.004), 0, skirt - 0.012))
        geo.boolean(body, cut)
    pin_bore = _along_x(geo.cylinder(name + "_pb", 0.0106, -r - 0.01, r + 0.01, 40))
    geo.boolean(body, pin_bore)
    geo.shade(body, 30)
    rings = []
    for k, (g_top, g_h, depth) in enumerate(((z, 0.0015, 0.0034), (z - 0.0045, 0.0015, 0.0034),
                                             (z - 0.009, 0.0028, 0.0030))):
        ring = geo.lathe(f"{name}_ring{k}", [(r - depth + 0.0003, g_top - 0.0001), (r + 0.00005, g_top - 0.0001),
                                             (r + 0.00005, g_top - g_h + 0.0001), (r - depth + 0.0003, g_top - g_h + 0.0001),
                                             (r - depth + 0.0003, g_top - 0.0001)], 72, col, M.dark_steel())
        rings.append(ring)
    pin = _along_x(geo.lathe(name + "_pin", [(0.0062, -r + 0.0015), (0.0103, -r + 0.0015), (0.0105, -r + 0.0025),
                                             (0.0105, r - 0.0025), (0.0103, r - 0.0015), (0.0062, r - 0.0015),
                                             (0.0062, -r + 0.0015)], 40, col, M.polished_steel()))
    for part in rings + [pin]:
        part.parent = body
    return body, rings, pin


# ---------------------------------------------------------------- con-rod

def conrod(name: str, rod: float, crank_pin_r: float = 0.024, col=None):
    t = 0.0105                                         # half thickness along X
    big_r = crank_pin_r + 0.0115
    outline = geo.tangent_hull((0, 0), 0.0155, (0, -rod), big_r, steps=36)
    body = geo.prism(name, outline, -t, t, col, M.forged_steel())
    _to_yz(body)
    # I-beam: pockets on both faces of the shank
    pocket = geo.tangent_hull((0, -0.034), 0.0055, (0, -rod + 0.045), 0.0105, steps=24)
    for z0, z1 in ((t - 0.0035, t + 0.001), (-t - 0.001, -t + 0.0035)):
        p = geo.prism(name + "_pk", pocket, z0, z1)
        _to_yz(p)
        geo.boolean(body, p)
    # bores
    se = _along_x(geo.cylinder(name + "_se", 0.0106, -0.02, 0.02, 40))
    geo.boolean(body, se)
    be = _along_x(geo.cylinder(name + "_be", crank_pin_r + 0.0016, -0.02, 0.02, 56))
    geo.transform_mesh(be, Matrix.Translation((0, 0, -rod)))
    geo.boolean(body, be)
    # cap parting line
    split = geo.box(name + "_split", (0.03, big_r * 2.4, 0.0007), (0, 0, -rod))
    geo.boolean(body, split)
    geo.bevel(body, 0.0012, 2, 35)
    parts = []
    for s in (-1, 1):
        b = geo.hex_bolt(f"{name}_bolt", 0.0085, 0.034, col, M.dark_steel())
        geo.transform_mesh(b, Matrix.Rotation(math.pi, 4, "X"))
        geo.transform_mesh(b, Matrix.Translation((0, s * (crank_pin_r + 0.0065), -rod - 0.0125)))
        parts.append(b)
    shell = geo.lathe(name + "_shell", [(crank_pin_r + 0.0001, -0.0095), (crank_pin_r + 0.0016, -0.0095),
                                        (crank_pin_r + 0.0016, 0.0095), (crank_pin_r + 0.0001, 0.0095),
                                        (crank_pin_r + 0.0001, -0.0095)], 56, col, M.brass())
    _along_x(shell)
    geo.transform_mesh(shell, Matrix.Translation((0, 0, -rod)))
    bush = _along_x(geo.lathe(name + "_bush", [(0.0105, -0.0098), (0.0118, -0.0098), (0.0118, 0.0098),
                                               (0.0105, 0.0098), (0.0105, -0.0098)], 40, col, M.brass()))
    parts += [shell, bush]
    for p in parts:
        p.parent = body
    return body, parts


# ---------------------------------------------------------------- crankshaft

def crankshaft(name: str, eng: K.Inline4, col=None):
    """Flat-plane inline-4 crank: 5 mains, 4 pins, 8 counterweighted webs, snout and flange."""
    r = eng.r
    pin_r, main_r = 0.024, 0.026
    web_t = 0.015
    pieces = []
    xs = [eng.x(i) for i in range(4)]
    mains = [xs[0] - eng.pitch / 2] + [(xs[i] + xs[i + 1]) / 2 for i in range(3)] + [xs[3] + eng.pitch / 2]
    for i, xc in enumerate(xs):
        a = math.radians(eng.PIN_ANGLES[i])
        py, pz = r * math.sin(a), r * math.cos(a)
        pin = geo.cylinder(f"{name}_pin{i}", pin_r, -0.0125, 0.0125, 48, col, M.polished_steel(), chamfer=0.0008)
        _along_x(pin)
        geo.transform_mesh(pin, Matrix.Translation((xc, py, pz)))
        pieces.append(pin)
        for s in (-1, 1):
            # web outline in a plane across the axis: journal-to-pin hull plus a counterweight sector
            hull = geo.tangent_hull((0, 0), 0.036, (py, pz), 0.031, steps=28)
            web = geo.prism(f"{name}_web", hull, -web_t / 2, web_t / 2, col, M.forged_steel())
            back = math.degrees(math.atan2(-pz, -py))
            sector = [(0.0, 0.0)] + geo.arc(0, 0, 0.070, back - 58, back + 58, 28)
            cw = geo.prism(f"{name}_cw", sector, -web_t / 2, web_t / 2)
            geo.boolean(web, cw, "UNION")
            geo.bevel(web, 0.0025, 3, 30)
            _to_yz(web)
            geo.transform_mesh(web, Matrix.Translation((xc + s * (0.0125 + web_t / 2), 0, 0)))
            pieces.append(web)
    for i, xm in enumerate(mains):
        x0 = xm - eng.pitch / 2 + 0.0125 + web_t - 0.001 if i > 0 else xm - 0.012
        x1 = xm + eng.pitch / 2 - 0.0125 - web_t + 0.001 if i < 4 else xm + 0.012
        j = geo.cylinder(f"{name}_main{i}", main_r, x0, x1, 48, col, M.polished_steel(), chamfer=0.0008)
        _along_x(j)
        pieces.append(j)
    snout = geo.lathe(f"{name}_snout", [(0, mains[0] - 0.075), (0.016, mains[0] - 0.075), (0.017, mains[0] - 0.073),
                                        (0.017, mains[0] - 0.012), (0, mains[0] - 0.012)], 40, col, M.polished_steel())
    _along_x(snout)
    flange = geo.lathe(f"{name}_flange", [(0, mains[4] + 0.010), (0.046, mains[4] + 0.010),
                                          (0.047, mains[4] + 0.012), (0.047, mains[4] + 0.024),
                                          (0, mains[4] + 0.024)], 56, col, M.forged_steel())
    _along_x(flange)
    pieces += [snout, flange]
    body = pieces[0]
    for p in pieces[1:]:
        geo.boolean(body, p, "UNION")
    body.name = name
    geo.shade(body, 30)
    return body, mains


def flywheel(name: str, x: float, col=None, teeth: int = 112):
    rad = 0.142
    disc = geo.lathe(name, [(0, 0), (0.05, 0), (0.05, 0.008), (0.11, 0.008), (0.12, 0.004), (rad - 0.006, 0.004),
                            (rad - 0.006, 0.020), (0.105, 0.020), (0.09, 0.026), (0, 0.026)], 96, col,
                     M.cast_iron())
    gear = []
    for k in range(teeth):
        a0 = 360.0 * k / teeth
        da = 360.0 / teeth
        gear += [(rad * math.cos(math.radians(a0)), rad * math.sin(math.radians(a0))),
                 ((rad + 0.0045) * math.cos(math.radians(a0 + da * 0.3)), (rad + 0.0045) * math.sin(math.radians(a0 + da * 0.3))),
                 ((rad + 0.0045) * math.cos(math.radians(a0 + da * 0.55)), (rad + 0.0045) * math.sin(math.radians(a0 + da * 0.55)))]
    ring = geo.prism(name + "_ring", gear, 0.006, 0.018, col, M.forged_steel())
    hole = geo.cylinder(name + "_rh", rad - 0.008, 0.0, 0.03, 96)
    geo.boolean(ring, hole)
    for k in range(6):
        a = math.tau * k / 6
        bolt = geo.hex_bolt(f"{name}_b{k}", 0.009, 0.02, col, M.dark_steel())
        geo.transform_mesh(bolt, Matrix.Translation((0.032 * math.cos(a), 0.032 * math.sin(a), 0.026)))
        bolt.parent = disc
    ring.parent = disc
    for o in [disc] + list(disc.children):
        geo.transform_mesh(o, Matrix.Rotation(math.radians(90), 4, "Y"))
    disc.location.x = x
    return disc


# ---------------------------------------------------------------- valvetrain

def valve(name: str, head_d: float, length: float = 0.104, col=None):
    hr = head_d / 2
    sr = 0.00275
    prof = [(0, -0.0004), (hr - 0.0012, -0.0004), (hr, 0.0008), (hr, 0.0018), (hr - 0.0032, 0.0048),
            (hr * 0.55, 0.0085), (sr * 2.0, 0.0145), (sr * 1.2, 0.020), (sr, 0.026),
            (sr, length - 0.008), (sr - 0.0007, length - 0.0075), (sr - 0.0007, length - 0.0055),
            (sr, length - 0.005), (sr, length - 0.0006), (sr - 0.0005, length), (0, length)]
    return geo.lathe(name, prof, 48, col, M.polished_steel(), angle=25)


def valve_spring(name: str, length: float = 0.0345, col=None, turns: float = 6.0, wire: float = 0.0019):
    """Installed valve spring from z = 0 (seat) to z = length (retainer); ground, closed end turns."""
    pitch = (length - 2 * wire) / (turns - 1.275)
    pts = geo.helix(0.0105, pitch, turns, wire)
    return geo.sweep(name, pts, wire, col, M.dark_steel(), segments=10, resolution=2)


def retainer(name: str, col=None):
    return geo.lathe(name, [(0.0028, 0.0), (0.0075, 0.0), (0.0124, 0.0035), (0.0124, 0.0055), (0.0055, 0.0055),
                            (0.0040, 0.0010), (0.0028, 0.0010), (0.0028, 0.0)], 40, col, M.brushed_steel())


def bucket(name: str, col=None):
    return geo.lathe(name, [(0, 0.022), (0.0152, 0.022), (0.0156, 0.0215), (0.0156, 0.0005), (0.0150, 0.0),
                            (0.0135, 0.0), (0.0135, 0.019), (0, 0.019)], 48, col, M.polished_steel(), angle=40)


def camshaft(name: str, eng: K.Inline4, x0: float, x1: float, lobe_xs, phases_deg, timing, journals, col=None):
    """A camshaft along X with a lobe at each x; lobe k's nose points at polar angle phases_deg[k] (cam deg).
    timing = (open_deg, close_deg) in crank degrees; lobes are generated from the same lift curve as the valve."""
    shaft = geo.cylinder(name, 0.0115, x0, x1, 40, col, M.polished_steel(), chamfer=0.001)
    _along_x(shaft)
    pts, _ = K.cam_profile(timing[0], timing[1], 0.0175, 0.0095, steps=120)
    for xl, ph in zip(lobe_xs, phases_deg):
        outline = [(rad * math.cos(math.radians(a + ph)), rad * math.sin(math.radians(a + ph))) for a, rad in pts]
        lobe = geo.prism(name + "_lobe", outline, -0.0075, 0.0075, col)
        geo.bevel(lobe, 0.0008, 2, 40)
        _to_yz(lobe)
        geo.transform_mesh(lobe, Matrix.Translation((xl, 0, 0)))
        geo.boolean(shaft, lobe, "UNION")
    for xb in journals:
        j = geo.cylinder(name + "_j", 0.0135, xb - 0.008, xb + 0.008, 40, chamfer=0.0006)
        _along_x(j)
        geo.boolean(shaft, j, "UNION")
    shaft.data.materials.clear()
    shaft.data.materials.append(M.polished_steel())
    geo.shade(shaft, 30)
    return shaft


def spark_plug(name: str, col=None):
    """Electrode tip at the origin, body up +Z: threads, hex, white insulator with ribs, terminal."""
    prof = [(0, 0.0), (0.0013, 0.0), (0.0013, 0.0025), (0.0024, 0.0028), (0.0024, 0.0035)]
    z = 0.0035
    while z < 0.0215:                                   # thread ridges
        prof += [(0.0060, z + 0.0004), (0.0068, z + 0.00065), (0.0060, z + 0.0013)]
        z += 0.0013
    prof += [(0.0062, 0.0225), (0.0085, 0.0230), (0.0085, 0.0245), (0.0093, 0.0255), (0.0093, 0.0262),
             (0.0080, 0.0270), (0.0080, 0.0275), (0.0, 0.0275)]
    shell = geo.lathe(name, prof, 48, col, M.brushed_steel(), angle=25)
    hexo = geo.lathe(name + "_hex", [(0, 0.0275), (0.0092, 0.0275), (0.0092, 0.0405), (0, 0.0405)], 6, col,
                     M.brushed_steel(), angle=25)
    geo.bevel(hexo, 0.0006, 2, 25)
    ins = [(0, 0.040)]
    zi = 0.0405
    ins += [(0.0055, zi)]
    for k in range(5):                                  # insulator ribs
        ins += [(0.0055, zi + 0.0022), (0.0060, zi + 0.0030), (0.0060, zi + 0.0042), (0.0055, zi + 0.0050)]
        zi += 0.0050
    ins += [(0.0045, zi + 0.004), (0.0035, zi + 0.006), (0, zi + 0.006)]
    insul = geo.lathe(name + "_ins", ins, 48, col, M.ceramic(), angle=25)
    term = geo.lathe(name + "_term", [(0, zi + 0.0055), (0.0022, zi + 0.0055), (0.0022, zi + 0.012),
                                      (0.0032, zi + 0.0125), (0.0032, zi + 0.016), (0, zi + 0.016)], 24, col,
                     M.brushed_steel())
    ground = geo.sweep(name + "_gnd", [(0.0050, 0, 0.0035), (0.0050, 0, -0.0016), (0.0030, 0, -0.0026),
                                       (-0.0004, 0, -0.0026)], 0.0007, col, M.brushed_steel(), segments=8,
                       resolution=4)
    for p in (hexo, insul, term, ground):
        p.parent = shell
    return shell


def coil(name: str, col=None, length: float = 0.10):
    body = geo.lathe(name, [(0, 0.0), (0.0098, 0.0), (0.0106, 0.004), (0.0106, length - 0.02),
                            (0.0145, length - 0.016), (0.0145, length), (0, length)], 40, col, M.plastic("#1a1c20"))
    head = geo.box(name + "_hd", (0.05, 0.034, 0.022), (0.006, 0, length + 0.009), col, M.plastic("#1a1c20"),
                   fillet=0.004)
    plug = geo.box(name + "_cn", (0.016, 0.02, 0.014), (0.036, 0, length + 0.012), col, M.plastic("#2a2d33"),
                   fillet=0.002)
    head.parent = body
    plug.parent = body
    return body
