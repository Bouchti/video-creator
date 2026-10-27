"""
Shot framing math (no Blender import, so it is unit-testable): where to put the camera so a set of
world points fills the vertical 9:16 frame with a margin. engine/studio.frame_all() samples the
scene's objects and builds the moving shot from this.
"""
import math

SENSOR = 36.0                # Blender's sensor fits the LONG side: the frame height of a 9:16 film
ASPECT = 9 / 16              # frame width / height
NEAR = 1.5                   # never put the camera closer than this to the nearest framed point (m)


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    n = math.sqrt(_dot(a, a)) or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


def basis(angle_deg, rise):
    """(toward_camera, forward, right, up) for a camera looking from `angle_deg` (-90 = from -Y, the
    front of a cutaway) and `rise` (height per metre of distance; 0.18 is a slightly high eye line)."""
    a = math.radians(angle_deg)
    back = _norm((math.cos(a), math.sin(a), rise))
    fwd = _mul(back, -1.0)
    right = _norm(_cross(fwd, (0.0, 0.0, 1.0)))
    up = _cross(right, fwd)
    return back, fwd, right, up


def tan_half(lens):
    """(horizontal, vertical) tangent of the half field of view for a 9:16 frame."""
    tv = SENSOR / (2.0 * lens)
    return tv * ASPECT, tv


def solve(points, angle=-90.0, rise=0.18, lens=28.0, margin=0.1, center=None):
    """Camera position, aim point and distance that keep every point inside the frame.

    margin: share of each half-frame kept free at the edges (0.1 = the points stay inside the middle
    90% of the width and height). center: the aim point (default: the middle of the points' box)."""
    pts = [tuple(float(x) for x in p) for p in points]
    if not pts:
        raise ValueError("frame needs at least one point")
    if center is None:
        lo = [min(p[i] for p in pts) for i in range(3)]
        hi = [max(p[i] for p in pts) for i in range(3)]
        center = tuple((lo[i] + hi[i]) / 2 for i in range(3))
    back, fwd, right, up = basis(angle, rise)
    th, tv = tan_half(lens)
    k = max(0.05, 1.0 - margin)
    dist = 0.0
    for p in pts:
        rel = _sub(p, center)
        x, y, z = _dot(rel, right), _dot(rel, up), _dot(rel, fwd)   # z > 0: farther away than the aim point
        dist = max(dist, abs(x) / (th * k) - z, abs(y) / (tv * k) - z, NEAR - z)
    return _add(center, _mul(back, dist)), tuple(center), dist


def project(point, cam, aim, lens):
    """Frame coordinates (0..1 across, 0..1 up; inside = both in [0, 1]) of `point`, or None behind."""
    fwd = _norm(_sub(aim, cam))
    right = _norm(_cross(fwd, (0.0, 0.0, 1.0)))
    up = _cross(right, fwd)
    rel = _sub(point, cam)
    depth = _dot(rel, fwd)
    if depth <= 1e-6:
        return None
    th, tv = tan_half(lens)
    return (0.5 + _dot(rel, right) / (depth * th) / 2.0, 0.5 + _dot(rel, up) / (depth * tv) / 2.0)


def height_share(height, distance, lens):
    """Share of the frame height an upright object `height` tall fills at `distance`."""
    return height * lens / (SENSOR * max(distance, 1e-6))
