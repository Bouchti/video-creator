import json
import os
import unittest

from engine.sets import spec
from agents import showrunner

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _beats(actions, words=12):
    return [{"action": a, "text": " ".join(["word"] * words), "overlay": {"type": "none", "value": "", "text": ""}}
            for a in actions]


GOOD = ["float_hook", "rewind", "dig", "layers", "gravel", "valve", "pipes", "rebar", "shotcrete", "cure",
        "finish", "fill", "weight", "flow", "cycle", "storm"]


class PoolSpecTests(unittest.TestCase):
    def test_reference_film_is_valid(self):
        film = json.load(open(os.path.join(ROOT, "engine", "films", "pool_cut.json"), encoding="utf-8"))
        self.assertEqual(spec("pool").validate(film["beats"]), [])

    def test_good_order(self):
        self.assertEqual(spec("pool").validate(_beats(GOOD)), [])

    def test_build_order_enforced(self):
        bad = GOOD.copy()
        bad[4], bad[5] = bad[5], bad[4]                  # valve before gravel
        self.assertTrue(any("build actions" in e for e in spec("pool").validate(_beats(bad))))

    def test_missing_build_step(self):
        self.assertTrue(spec("pool").validate(_beats([a for a in GOOD if a != "rebar"])))

    def test_explainer_needs_prerequisite(self):
        bad = ["float_hook", "rewind", "weight"] + [a for a in GOOD[2:] if a != "weight"]
        self.assertTrue(any("after 'fill'" in e for e in spec("pool").validate(_beats(bad))))

    def test_hook_and_rewind_first(self):
        self.assertTrue(spec("pool").validate(_beats(GOOD[1:])))
        self.assertTrue(spec("pool").validate(_beats(["float_hook"] + GOOD[2:])))

    def test_outro_must_be_last(self):
        bad = GOOD[:-2] + ["storm", "cycle"]
        self.assertTrue(any("outro" in e for e in spec("pool").validate(_beats(bad))))

    def test_unknown_action(self):
        self.assertTrue(any("unknown" in e for e in spec("pool").validate(_beats(GOOD + ["explode"]))))


class HardCheckTests(unittest.TestCase):
    def test_passes_in_budget(self):
        script = {"beats": _beats(GOOD, words=11)}            # 176 words
        script["beats"][0]["text"] = "An empty pool can float right out of the ground."
        self.assertEqual(showrunner.hard_checks(script, "pool"), [])

    def test_word_budget(self):
        problems = showrunner.hard_checks({"beats": _beats(GOOD, words=20)}, "pool")
        self.assertTrue(any("total narration" in p for p in problems))

    def test_hook_length(self):
        script = {"beats": _beats(GOOD, words=11)}
        script["beats"][0]["text"] = " ".join(["word"] * 20)
        self.assertTrue(any("hook is" in p for p in showrunner.hard_checks(script, "pool")))

    def test_sticker_limits(self):
        script = {"beats": _beats(GOOD, words=11)}
        for b in script["beats"][:8]:
            b["overlay"] = {"type": "stat", "value": "5 m", "text": "deep"}
        problems = showrunner.hard_checks(script, "pool")
        self.assertTrue(any("stickers" in p for p in problems))
        self.assertTrue(any("hook" in p for p in problems))


class ToFilmTests(unittest.TestCase):
    def test_roles_and_overlays(self):
        script = {"title": "T", "caption": "c", "hashtags": ["#a"], "beats": _beats(GOOD, words=11)}
        script["beats"][2]["overlay"] = {"type": "stat", "value": "50 tons", "text": "of soil"}
        script["beats"][4]["overlay"] = {"type": "label", "value": "", "text": "Gravel"}
        film = showrunner.to_film(script, {"set": "pool", "angle": "a"}, "facts")
        self.assertEqual(film["set"], "pool")
        self.assertEqual(film["beats"][0]["video"], "epilogue")
        self.assertEqual(film["beats"][1]["video"], "rewind")
        self.assertEqual(film["beats"][2]["overlay"], {"type": "stat", "value": "50 tons", "text": "of soil"})
        self.assertEqual(film["beats"][4]["overlay"], {"type": "label", "text": "Gravel"})
        self.assertNotIn("overlay", film["beats"][3])
        self.assertEqual(film["captions"], "word")

    def test_make_film_finds_roles(self):
        from engine.make_film import _beat_ids
        beats = [{"id": "float_hook", "video": "epilogue"}, {"id": "rewind", "video": "rewind"}, {"id": "dig"}]
        self.assertEqual(_beat_ids(beats), ["hook", "rewind", "dig"])


if __name__ == "__main__":
    unittest.main()


class MontageTests(unittest.TestCase):
    def test_grouped_build_steps_are_valid(self):
        beats = _beats(["float_hook", "rewind", "dig"]) + [
            {"actions": ["gravel", "valve", "pipes", "rebar"], "text": " ".join(["w"] * 30)},
            {"actions": ["shotcrete", "cure", "finish"], "text": " ".join(["w"] * 25)},
        ] + _beats(["fill", "flow"])
        self.assertEqual(spec("pool").validate(beats), [])

    def test_hook_cannot_be_grouped(self):
        beats = [{"actions": ["float_hook", "rewind"], "text": "x"}] + _beats(GOOD[2:])
        self.assertTrue(any("single action" in e for e in spec("pool").validate(beats)))

    def test_montage_needs_enough_words(self):
        beats = _beats(["float_hook", "rewind", "dig"], words=11) + [
            {"actions": ["gravel", "valve", "pipes", "rebar"], "text": "quick"},
        ] + _beats(["shotcrete", "cure", "finish", "fill", "flow", "cycle"], words=20)
        beats[0]["text"] = "An empty pool can float right out of the ground."
        problems = showrunner.hard_checks({"beats": beats}, "pool")
        self.assertTrue(any("needs at least" in p for p in problems))

    def test_to_film_montage(self):
        script = {"title": "T", "beats": _beats(["float_hook", "rewind"]) +
                  [{"actions": ["dig", "gravel"], "text": "a b", "overlay": {"type": "none", "value": "", "text": ""}}]}
        film = showrunner.to_film(script, {"set": "pool", "angle": "a"}, "f")
        self.assertEqual(film["beats"][2]["id"], "dig+gravel")
        self.assertEqual(film["beats"][2]["actions"], ["dig", "gravel"])
