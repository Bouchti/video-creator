import os
import tempfile
import unittest
from unittest import mock

from agents import diagram_writer as dw

GOOD = """import React from 'react';
import {Canvas, Box, DiagramProps} from '../../diagram/kit';
export default function Diagram({t, dur, w, h}: DiagramProps) {
  return <Canvas t={t} w={w} h={h}><Box x={100} y={100} w={800} h={800} /></Canvas>;
}
"""
SPEC = {"id": "Bike Lean!", "title": "WHY", "dur": 90, "must_see": "the bike leans and the wheel turns in",
        "steps": ["LEANS", "TURNS IN"]}


class StaticTest(unittest.TestCase):
    def test_only_the_kit_and_pure_code(self):
        self.assertEqual(dw.static_problems(GOOD), [])
        bad = GOOD.replace("'../../diagram/kit'", "'d3'") + "\nconst x = Math.random();"
        problems = dw.static_problems(bad)
        self.assertTrue(any("'d3' is not allowed" in p for p in problems))
        self.assertTrue(any("Math.random" in p for p in problems))

    def test_code_fences_are_removed(self):
        self.assertEqual(dw._strip_fences("```tsx\nabc\n```"), "abc\n")


class LoopTest(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp()
        self.gen = os.path.join(d, "generated")
        patches = [mock.patch.object(dw, "GENERATED", self.gen), mock.patch.object(dw, "INDEX", os.path.join(d, "index.ts")),
                   mock.patch.object(dw, "stills", return_value=["a.png", "b.png", "c.png"])]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_type_errors_go_back_to_the_writer_then_it_is_accepted(self):
        asks = []

        def writer(s, p, sc):
            asks.append(p)
            return {"code": GOOD}
        with mock.patch.object(dw, "typecheck", side_effect=["bike_lean_.tsx(3,1): error TS2304", ""]):
            out = dw.write(SPEC, call=writer, judge=lambda s, p: {"score": 5, "shows": True, "readable": True,
                                                                 "clean": True})
        self.assertEqual(out["status"], "accepted")
        self.assertEqual(out["rounds"], 2)
        self.assertIn("TS2304", asks[1])
        self.assertTrue(os.path.isfile(os.path.join(self.gen, "bike_lean_.tsx")))

    def test_a_diagram_that_never_passes_review_falls_back_and_is_removed(self):
        bad = {"shows": False, "readable": True, "clean": True, "problems": ["no wheel"], "fix": "draw the wheel"}
        seen = []

        def look(s, p, sc, images):
            seen.append(images)
            return {"code": GOOD}
        with mock.patch.object(dw, "typecheck", return_value=""):
            out = dw.write(SPEC, call=lambda s, p, sc: {"code": GOOD}, judge=lambda s, p: dict(bad, score=2), look=look)
        self.assertEqual(len(seen), 2)                      # fix rounds see their own stills
        self.assertEqual(seen[0][0], ("moment 1", "a.png"))
        self.assertEqual(out["status"], "fallback")
        self.assertIn("no wheel", out["problems"])
        self.assertFalse(os.path.exists(os.path.join(self.gen, "bike_lean_.tsx")))

    def test_the_best_version_is_kept_when_none_passes(self):
        scores = iter([3, 2, 2])
        codes = iter([GOOD, GOOD.replace("800", "700"), GOOD.replace("800", "600")])
        with mock.patch.object(dw, "typecheck", return_value=""):
            out = dw.write(SPEC, call=lambda s, p, sc: {"code": next(codes)},
                           look=lambda s, p, sc, im: {"code": next(codes)},
                           judge=lambda s, p: {"score": next(scores), "shows": True, "readable": True, "clean": False,
                                               "problems": ["x"], "fix": ""})
        self.assertEqual((out["status"], out["score"]), ("accepted", 3))
        with open(os.path.join(self.gen, "bike_lean_.tsx"), encoding="utf-8") as fh:
            self.assertIn("800", fh.read())

    def test_writer_failure_never_blocks(self):
        def broken(s, p, sc):
            raise RuntimeError("quota")
        self.assertEqual(dw.write(SPEC, call=broken)["status"], "fallback")


if __name__ == "__main__":
    unittest.main()
