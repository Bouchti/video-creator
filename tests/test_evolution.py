"""Evolution format (bridge_evolution set): spec rules, the reference script, the writer's checks
and the parallel render split. No Blender, no paid APIs."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from engine import sets
from engine.sets import bridge_evolution_spec as spec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "engine", "films", "bridge_evolution.json")


def _script(film):
    return {"title": film["title"], "caption": "", "hashtags": [],
            "beats": [{"actions": spec.beat_actions(b), "text": b["text"],
                       "overlay": b.get("overlay") or {"type": "none", "value": "", "text": ""}}
                      for b in film["beats"]]}


class SpecTests(unittest.TestCase):
    def test_registered(self):
        self.assertIn("bridge_evolution", sets.EVOLUTION)
        self.assertNotIn("bridge_evolution", sets.AVAILABLE)      # the cutaway showrunner never picks it

    def test_every_action_is_in_the_order_and_has_a_shot(self):
        self.assertEqual(set(spec.STAGE_ORDER), set(spec.ACTIONS))
        src = open(os.path.join(ROOT, "engine", "sets", "bridge_evolution.py"), encoding="utf-8").read()
        for a in spec.ACTIONS:
            self.assertIn(f"def a_{a}(", src)

    def test_problem_is_answered_by_the_next_stage(self):
        for p, s in spec.ANSWERS.items():
            self.assertEqual(spec.STAGE_ORDER.index(s), spec.STAGE_ORDER.index(p) + 1)

    def test_validate(self):
        good = [{"action": a} for a in spec.STAGE_ORDER]
        self.assertEqual(spec.validate(good), [])
        self.assertTrue(spec.validate(good[1:]))
        self.assertTrue(spec.validate(list(reversed(good))))
        merged = good[:7] + [{"actions": ["heat", "expansion_joint"]}] + good[9:]
        self.assertEqual(spec.validate(merged), [])
        bad = good[:6] + [{"actions": ["suspension", "heat"]}] + good[8:]
        self.assertTrue(spec.validate(bad))


class ReferenceFilmTests(unittest.TestCase):
    def setUp(self):
        self.film = json.load(open(REF, encoding="utf-8"))

    def test_reference_film_is_valid(self):
        self.assertEqual(self.film["format"], "evolution")
        self.assertEqual(spec.validate(self.film["beats"]), [])

    def test_reference_passes_the_writer_checks(self):
        from agents import evolution_writer as ew
        self.assertEqual(ew.hard_checks(_script(self.film), "bridge_evolution"), [])

    def test_to_film_marks_the_format(self):
        from agents import evolution_writer as ew
        topic = {"set": "bridge_evolution", "angle": "x"}
        film = ew.to_film(_script(self.film), topic, "facts")
        self.assertEqual(film["format"], "evolution")
        self.assertEqual(film["cta"], self.film["cta"])
        self.assertEqual(spec.validate(film["beats"]), [])


class _FakeProc:
    calls = []

    def __init__(self, cmd, stdout, stderr, text):
        _FakeProc.calls.append(cmd)
        stdout.write("DONE\n")

    def wait(self):
        pass


class EvolutionParallelRenderTests(unittest.TestCase):
    def test_chunks_start_at_frame_one_without_a_hook(self):
        import engine.make_film as mf
        spans = [{"start": 0, "end": 120}, {"start": 121, "end": 300}, {"start": 301, "end": 2000}]
        for n in (2, 3):
            _FakeProc.calls = []
            with patch.object(mf.subprocess, "Popen", _FakeProc):
                mf._render_parallel(["blender"], spans, 2000, n, tempfile.mkdtemp(), start=1, hook=False)
            ranges = [tuple(int(x) for x in c[1].split("=")[1].split(":")) for c in _FakeProc.calls]
            self.assertEqual(ranges[0][0], 1)
            self.assertEqual(ranges[-1][1], 2000)
            for (a, b), (c, d) in zip(ranges, ranges[1:]):
                self.assertEqual(c, b + 1)
            self.assertFalse(any("--hook" in c for c in _FakeProc.calls))


if __name__ == "__main__":
    unittest.main()
