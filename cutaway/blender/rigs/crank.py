"""
Crank-slider, valve-lift and four-stroke timing math (pure Python: no bpy, unit-tested).

Angles: the crank angle theta (degrees) grows with time. A cylinder's own cycle angle c runs 0..720:
  0-180 intake, 180-360 compression, 360-540 power, 540-720 exhaust; c = 0 is top dead centre at the start
  of intake, c = 360 is top dead centre at firing.
"""
from __future__ import annotations

import math

STROKES = ("intake", "compression", "power", "exhaust")


def piston_pin_z(theta_deg: float, r: float, rod: float) -> float:
    """Height of the wrist pin above the crank axis (exact crank-slider)."""
    t = math.radians(theta_deg)
    return r * math.cos(t) + math.sqrt(rod * rod - (r * math.sin(t)) ** 2)


def crank_pin_yz(theta_deg: float, r: float) -> tuple[float, float]:
    """Crank-pin centre in the plane across the crank axis (y sideways, z up); theta 0 = top."""
    t = math.radians(theta_deg)
    return r * math.sin(t), r * math.cos(t)


def rod_tilt(theta_deg: float, r: float, rod: float) -> float:
    """Con-rod tilt (radians) about the crank axis, so the big end reaches the crank pin."""
    y, _ = crank_pin_yz(theta_deg, r)
    return math.asin(max(-1.0, min(1.0, y / rod)))


def cycle_angle(theta_deg: float, offset_deg: float) -> float:
    return (theta_deg - offset_deg) % 720.0


def stroke(c: float) -> str:
    return STROKES[int(c // 180) % 4]


def _bump(x: float) -> float:
    """0..1..0 over x in [0, 1], smooth at both ends (a cam's lift shape: zero velocity at the ends)."""
    if x <= 0.0 or x >= 1.0:
        return 0.0
    return math.sin(math.pi * x) ** 2


def lift(c: float, open_deg: float, close_deg: float, max_lift: float) -> float:
    """Valve lift at cycle angle c for a valve open from open_deg to close_deg (may wrap past 720)."""
    span = (close_deg - open_deg) % 720.0
    x = ((c - open_deg) % 720.0) / span
    return max_lift * _bump(x)


# Typical street-engine timing (crank degrees in the 0..720 cycle)
INTAKE = (-8.0 % 720, 228.0)        # opens 8 deg before TDC, closes 48 deg after BDC
EXHAUST = (492.0, 728.0 % 720)      # opens 48 deg before BDC, closes 8 deg after TDC
SPARK = 348.0                       # 12 deg before firing TDC


def intake_lift(c: float, max_lift: float) -> float:
    return lift(c, INTAKE[0], INTAKE[1], max_lift)


def exhaust_lift(c: float, max_lift: float) -> float:
    return lift(c, EXHAUST[0], EXHAUST[1], max_lift)


def cam_profile(open_deg: float, close_deg: float, base_r: float, max_lift: float, steps: int = 180):
    """Polar outline (angle_deg, radius) of a cam lobe whose nose (angle 0) gives max lift.
    The cam turns at half crank speed, so cam angle a corresponds to crank angle 2a."""
    peak = (open_deg + ((close_deg - open_deg) % 720.0) / 2) % 720.0
    pts = []
    for i in range(steps):
        a = -180.0 + 360.0 * i / steps
        pts.append((a, base_r + lift(peak + 2 * a, open_deg, close_deg, max_lift)))
    return pts, peak


def combustion(c: float) -> float:
    """Flame intensity 0..1: lit by the spark, peaks just after TDC, fades through the power stroke."""
    if c < SPARK or c > 540.0:
        return 0.0
    if c < 372.0:
        return (c - SPARK) / (372.0 - SPARK)
    return math.exp(-(c - 372.0) / 55.0)


def spark(c: float, width: float = 10.0) -> float:
    """Spark flash 0..1 around the ignition angle."""
    d = abs(c - SPARK)
    return max(0.0, 1.0 - d / width)


class Inline4:
    """An inline-4 with a flat-plane crank and firing order 1-3-4-2."""
    PIN_ANGLES = (0.0, 180.0, 180.0, 0.0)          # crank-pin angle of cylinders 1..4
    CYCLE_OFFSETS = (0.0, 540.0, 180.0, 360.0)     # cycle angle offset of cylinders 1..4 -> fires 1, 3, 4, 2

    def __init__(self, bore=0.086, stroke=0.086, rod=0.145, pitch=0.096, compression_height=0.031):
        self.bore = bore
        self.r = stroke / 2
        self.rod = rod
        self.pitch = pitch
        self.ch = compression_height
        self.deck = self.r + rod + compression_height + 0.0006

    def x(self, i: int) -> float:
        """Cylinder i (0-based) position along the crank axis; cylinder 1 is at the front (-X)."""
        return (i - 1.5) * self.pitch

    def cylinder(self, i: int, theta: float) -> dict:
        local = theta - self.PIN_ANGLES[i]
        c = cycle_angle(theta, self.CYCLE_OFFSETS[i])
        return {
            "pin_z": piston_pin_z(local, self.r, self.rod),
            "rod_tilt": rod_tilt(local, self.r, self.rod),
            "cycle": c,
            "stroke": stroke(c),
            "intake_lift": intake_lift(c, 0.0095),
            "exhaust_lift": exhaust_lift(c, 0.0090),
            "combustion": combustion(c),
            "spark": spark(c),
        }

    def firing_order(self) -> list[int]:
        """Cylinder numbers in the order they reach firing TDC as theta increases from 0."""
        fire_at = {i + 1: (360.0 + self.CYCLE_OFFSETS[i]) % 720.0 for i in range(4)}
        return [k for k, _ in sorted(fire_at.items(), key=lambda kv: kv[1])]
