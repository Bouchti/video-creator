import itertools
import random
import unittest

from engine import framing


def _box(lo, hi):
    return list(itertools.product(*zip(lo, hi)))


class SolveTests(unittest.TestCase):
    def assertInside(self, pts, cam, aim, lens, margin=0.0):
        for p in pts:
            u = framing.project(p, cam, aim, lens)
            self.assertIsNotNone(u, p)
            for c in u:
                self.assertGreaterEqual(c, margin / 2 - 1e-6, (p, u))
                self.assertLessEqual(c, 1 - margin / 2 + 1e-6, (p, u))

    def test_every_point_lands_inside_the_frame_from_any_angle(self):
        rng = random.Random(4)
        for _ in range(60):
            pts = [(rng.uniform(-20, 20), rng.uniform(-5, 8), rng.uniform(-3, 9)) for _ in range(6)]
            angle, rise, lens = rng.uniform(-150, -30), rng.uniform(0.0, 0.5), rng.uniform(18, 50)
            cam, aim, _ = framing.solve(pts, angle, rise, lens, margin=0.1)
            self.assertInside(pts, cam, aim, lens, margin=0.1)

    def test_tight_on_the_limiting_side(self):
        # a wide, flat levee from the front: the width decides the distance, and it fills the margin
        pts = _box((-12, -1, 0), (12, 1, 3))
        cam, aim, dist = framing.solve(pts, -90, 0.0, 28, margin=0.1)
        xs = [framing.project(p, cam, aim, 28)[0] for p in pts]
        self.assertAlmostEqual(min(xs), 0.05, delta=0.01)
        self.assertAlmostEqual(max(xs), 0.95, delta=0.01)

    def test_a_tall_subject_is_limited_by_the_height(self):
        pts = _box((-0.4, -0.4, 0), (0.4, 0.4, 1.8))           # Max alone, 1.8 m
        cam, aim, dist = framing.solve(pts, -90, 0.0, 32, margin=0.1)
        self.assertGreater(framing.height_share(1.8, dist, 32), 0.7)          # perspective: the near face limits it

    def test_camera_never_sits_inside_the_subject(self):
        cam, aim, dist = framing.solve([(0, 0, 0)], -90, 0.2, 28)
        self.assertGreaterEqual(dist, framing.NEAR)


if __name__ == "__main__":
    unittest.main()
