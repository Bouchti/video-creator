import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import engine.make_film as mf


class _FakeProc:
    calls = []

    def __init__(self, cmd, stdout, stderr, text):
        _FakeProc.calls.append(cmd)
        stdout.write("DONE\n")

    def wait(self):
        pass


class ParallelRenderTests(unittest.TestCase):
    SPANS = [{"start": 0, "end": 88}, {"start": 89, "end": 160}, {"start": 161, "end": 2500}]

    def _run(self, n):
        _FakeProc.calls = []
        with patch.object(mf.subprocess, "Popen", _FakeProc):
            mf._render_parallel(["blender"], self.SPANS, 2500, n, tempfile.mkdtemp())
        return _FakeProc.calls

    def test_chunks_cover_every_frame_once(self):
        for n in (2, 3, 4):
            calls = self._run(n)
            ranges = [tuple(int(x) for x in c[1].split("=")[1].split(":")) for c in calls]
            self.assertEqual(ranges[0][0], 162)
            self.assertEqual(ranges[-1][1], 2500)
            for (a, b), (c, d) in zip(ranges, ranges[1:]):
                self.assertEqual(c, b + 1)

    def test_only_first_worker_renders_the_hook(self):
        calls = self._run(3)
        self.assertEqual([("--hook" in c) for c in calls], [True, False, False])

    def test_hook_worker_gets_fewer_build_frames(self):
        calls = self._run(2)
        (a0, b0), (a1, b1) = [tuple(int(x) for x in c[1].split("=")[1].split(":")) for c in calls]
        self.assertLess(b0 - a0, b1 - a1)


class ExactTimingPreflightTests(unittest.TestCase):
    def test_repairs_rehearsal_before_production_and_reuses_accepted_manifest(self):
        from agents import scene_validator as sv
        from agents import set_builder as sb

        root = tempfile.mkdtemp()
        work = os.path.join(root, "film_work")
        os.makedirs(work)
        film = {"title": "Demo", "set": "demo", "beats": [
            {"action": "one", "text": "one"}, {"action": "two", "text": "two"}]}
        spans = [{"start": 0, "end": 89}, {"start": 90, "end": 179}]
        film_json, timings = os.path.join(root, "film.json"), os.path.join(root, "timings.json")
        json.dump(film, open(film_json, "w"))
        json.dump({"beats": spans}, open(timings, "w"))
        spec = SimpleNamespace(SUBJECT="demo", ACTIONS={"one": {"kind": "story"}, "two": {"kind": "story"}})
        good = {"window": 1, "beat": 1, "action": "one", "f0": 1, "f1": 90, "valid": True}
        bad = {"window": 2, "beat": 2, "action": "two", "f0": 91, "f1": 180,
               "valid": False, "fatal_problems": ["missing"]}
        reports = [
            {"windows": [good, bad], "rejected": [bad], "accepted": 1, "planned": 2, "complete": True},
            {"windows": [good, {**bad, "valid": True}], "rejected": [], "accepted": 2, "planned": 2,
             "complete": True},
        ]
        renders = []

        def render(cmd, watcher=None, env=None):
            renders.append(cmd)
            out = cmd[-2]
            requested = [a for a in cmd if a.startswith("--frames=")][0].split("=", 1)[1]
            for value in requested.split(","):
                open(os.path.join(out, f"still_{int(value):04d}.png"), "wb").write(b"png")

        def review(_film, _spans, rehearsal_work, spec=None):
            report = reports.pop(0)
            json.dump(report, open(os.path.join(rehearsal_work, "scene_review.json"), "w"))
            return report

        with patch.object(mf, "_run_blender", side_effect=render), \
                patch.object(sv, "review_sampled_windows", side_effect=review), \
                patch.object(sb, "fix_scenes") as fix, patch.object(sb, "freeze_methods", return_value={}), \
                patch.object(sb, "restore_methods", return_value=[]), \
                patch.dict(os.environ, {"SCENE_PREFLIGHT": "1"}):
            mf._scene_preflight(film, film_json, "runner.py", timings, spans, work, spec)
            self.assertEqual(len(renders), 2)
            fix.assert_called_once()
            mf._scene_preflight(film, film_json, "runner.py", timings, spans, work, spec)
        self.assertEqual(len(renders), 2)  # accepted fingerprint skips Blender and model review


if __name__ == "__main__":
    unittest.main()
