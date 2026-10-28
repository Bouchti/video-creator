import unittest

from engine import framing
from engine.kit import geometry as g
from engine.kit import vocab


class ProfileTests(unittest.TestCase):
    def test_every_profile_has_the_same_vertex_count_so_it_can_morph(self):
        counts = {len(g.profile(n)) for n in g.PROFILES}
        self.assertEqual(counts, {8})

    def test_outlines_are_counter_clockwise_and_sit_on_the_ground(self):
        for name in g.PROFILES:
            p = g.profile(name)
            area = sum(x0 * z1 - x1 * z0 for (x0, z0), (x1, z1) in zip(p, p[1:] + p[:1])) / 2
            self.assertGreater(area, 0, name)
            self.assertEqual(min(z for _, z in p), 0.0, name)

    def test_the_barrier_stays_on_land(self):
        for name in g.PROFILES:
            self.assertGreater(g.toes(name)[0], g.BANK, name)

    def test_levels_make_the_story_true(self):
        self.assertLess(g.level("low", "steep"), 0)                              # calm day: river in its bed
        self.assertGreater(g.level("overtop", "wide"), g.crest_height("wide"))   # overtopping goes over
        freeboard = g.crest_height("raised") - g.level("flood", "raised")
        self.assertGreater(freeboard, 0.4)                                       # visible safety margin


class FocusTests(unittest.TestCase):
    def test_every_event_has_a_compact_focus_with_max_inside(self):
        for event in vocab.EVENTS:
            shape = "steep" if event in ("seep_slump", "calm") else "raised" if "burrow" in event or \
                event in ("freeboard_holds", "storm_holds") else "wide"
            x0, x1, z0, z1 = g.focus(event, shape)
            mx = g.max_spot(event, shape)[0]
            self.assertTrue(x0 < mx < x1, event)
            self.assertLessEqual(x1 - x0, 7.2 if event == "storm_holds" else 6.0, event)

    def test_max_is_readable_in_a_mechanism_shot(self):
        # Max ~1.85 m: a frame solved for a 6 m focus still shows him at >= 15% of the frame height
        x0, x1, z0, z1 = g.focus("seep_blocked", "wide")
        pts = [(x, 0.0, z) for x in (x0, x1) for z in (z0, z1)]
        _cam, _aim, dist = framing.solve(pts, -90, 0.12, 28, margin=0.12)
        self.assertGreaterEqual(framing.height_share(1.85, dist, 28), 0.15)

    def test_characters_never_stand_inside_the_barrier(self):
        for event in vocab.EVENTS:
            for shape in ("steep", "wide", "raised"):
                x, _y, z = g.max_spot(event, shape)
                if event == "calm" or z == g.crest_height(shape):       # promise day / standing ON the crest
                    continue
                self.assertFalse(g.toes(shape)[0] - 0.2 < x < g.toes(shape)[1] + 0.2, (event, shape))


if __name__ == "__main__":
    unittest.main()
