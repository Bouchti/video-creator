"""Scene validator + auto set builder: windows, acceptance rule, pixel QC, the live watcher (with a
stub reviewer), Blender abort on rejection, and the builder's file fence. No Blender, no paid APIs."""
import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from agents import scene_validator as sv

FILM = {"title": "t", "set": "bridge_evolution", "format": "evolution",
        "beats": [{"action": "plank", "text": "a"}, {"action": "widen_arch", "text": "b"},
                  {"actions": ["heat", "expansion_joint"], "text": "c"}]}
SPANS = [{"start": 0, "end": 179}, {"start": 180, "end": 239}, {"start": 240, "end": 419}]


def _frame(path, color=(90, 140, 70), noise=True, seed=0):
    rng = np.random.default_rng(seed)
    a = np.full((96, 54, 3), color, dtype=np.uint8)
    if noise:
        a = np.clip(a + rng.integers(-60, 60, a.shape), 0, 255).astype(np.uint8)
    Image.fromarray(a).save(path)


class WindowTests(unittest.TestCase):
    def test_windows_cover_every_frame_once_and_never_straddle_beats(self):
        ws = sv.plan_windows(FILM, SPANS, seconds=3)
        frames = [f for w in ws for f in range(w["f0"], w["f1"] + 1)]
        self.assertEqual(frames, list(range(1, 421)))
        for w in ws:
            b = SPANS[w["beat"] - 1]
            self.assertTrue(b["start"] + 1 <= w["f0"] <= w["f1"] <= b["end"] + 1)
        self.assertEqual([w["beat"] for w in ws], [1, 1, 2, 3, 3])
        self.assertEqual(ws[3]["action"], "heat+expansion_joint")

    def test_shows_comes_from_the_spec(self):
        from engine.sets import bridge_evolution_spec as spec
        ws = sv.plan_windows(FILM, SPANS, seconds=3, spec=spec)
        self.assertIn("planks", ws[0]["shows"])


class JudgeTests(unittest.TestCase):
    def test_rules(self):
        good = {"visual_match": 8, "readability": 7, "image_quality": 8, "continuity": 9, "fatal_problems": [],
                "problems": [], "fix": ""}
        self.assertTrue(sv.judge(good, 6)["valid"])
        self.assertFalse(sv.judge({**good, "fatal_problems": ["subject not in frame"]}, 6)["valid"])
        self.assertFalse(sv.judge({**good, "readability": 3}, 6)["valid"])
        floor = sv.judge({**good, "readability": 5}, 6)           # minor readability dip, strong average
        self.assertTrue(floor["valid"])
        self.assertEqual(floor["acceptance"], "quality-floor")
        self.assertFalse(sv.judge({**good, "visual_match": 5}, 6)["valid"])
        floating = sv.judge({**good, "problems": ["Both children hover above the pumpkin."]}, 6)
        self.assertFalse(floating["valid"])
        self.assertTrue(floating["fatal_problems"])


class TechnicalTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def _p(self, name, **kw):
        p = os.path.join(self.d, name)
        _frame(p, **kw)
        return p

    def test_normal_frames_pass(self):
        ps = [self._p(f"{k}.png", seed=k) for k in range(3)]
        self.assertTrue(sv.technical_check(ps)["valid"])

    def test_black_magenta_flat_and_frozen(self):
        self.assertFalse(sv.technical_check([self._p("b.png", color=(2, 2, 2), noise=False)])["valid"])
        self.assertFalse(sv.technical_check([self._p("m.png", color=(255, 0, 255), noise=False)])["valid"])
        self.assertFalse(sv.technical_check([self._p("f.png", color=(120, 120, 120), noise=False)])["valid"])
        same = self._p("s.png", seed=1)
        rep = sv.technical_check([same, same, same])
        self.assertTrue(rep["valid"])
        self.assertTrue(any("frozen" in p for p in rep["problems"]))


class WatcherTests(unittest.TestCase):
    """The watcher judges windows while frames keep arriving, and asks to stop at a rejection."""

    def setUp(self):
        self.work = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.work, "frames"))

    def _write(self, f0, f1):
        for f in range(f0, f1 + 1):
            _frame(os.path.join(self.work, "frames", f"f_{f:04d}.png"), seed=f)

    def _stub(self, reject_beat=None):
        def review(w, images, subject, previous=None):
            if w["beat"] == reject_beat:
                return {"valid": False, "fatal_problems": ["subject not in frame"], "problems": [], "fix": "move cam",
                        "skipped": False}
            return {"valid": True, "average_score": 8.0, "fatal_problems": [], "problems": [], "fix": "",
                    "skipped": False}
        return review

    def test_streams_and_accepts(self):
        with patch.dict(os.environ, {"SCENE_POLICY": "stop", "SCENE_REVIEW_BATCH_SIZE": "1"}), \
                patch.object(sv, "review_images", self._stub()), \
                patch.object(sv, "window_ready", lambda w, d, settle=2.0: _ready(w, d)):
            w = sv.SceneWatcher(FILM, SPANS, self.work, keep_previous=False)
            w.start()
            self._write(1, 90)                               # first window lands while "Blender" continues
            t0 = time.time()
            while not w.results and time.time() - t0 < 20:
                time.sleep(0.2)
            self.assertEqual(len(w.results), 1)              # judged before the rest exists
            self._write(91, 420)
            rep = w.finish()
        self.assertTrue(rep["complete"])
        self.assertEqual(rep["accepted"], 5)
        saved = json.load(open(os.path.join(self.work, "scene_review.json")))
        self.assertEqual(len(saved["windows"]), 5)
        self.assertTrue(os.path.exists(saved["windows"][0]["images"][0]))

    def test_rejection_requests_abort(self):
        with patch.dict(os.environ, {"SCENE_POLICY": "stop", "SCENE_REVIEW_BATCH_SIZE": "1"}), \
                patch.object(sv, "review_images", self._stub(reject_beat=2)), \
                patch.object(sv, "window_ready", lambda w, d, settle=2.0: _ready(w, d)):
            w = sv.SceneWatcher(FILM, SPANS, self.work, keep_previous=False)
            w.start()
            self._write(1, 240)
            t0 = time.time()
            while not w.should_abort() and time.time() - t0 < 20:
                time.sleep(0.2)
            self.assertTrue(w.should_abort())
            rep = w.finish()
        self.assertEqual([r["beat"] for r in rep["rejected"]], [2])
        with self.assertRaises(sv.SceneRejected):
            raise sv.SceneRejected(rep["rejected"], w.report_path)

    def test_ready_windows_are_batched_into_fewer_model_calls(self):
        calls = []

        def batch(items, subject):
            calls.append([w["window"] for w, _ in items])
            return {w["window"]: {"valid": True, "average_score": 8.0, "fatal_problems": [],
                                  "problems": [], "fix": "", "skipped": False}
                    for w, _ in items}

        self._write(1, 420)
        with patch.dict(os.environ, {"SCENE_POLICY": "report", "SCENE_REVIEW_BATCH_SIZE": "4"}), \
                patch.object(sv, "review_batch", side_effect=batch), \
                patch.object(sv, "window_ready", lambda w, d, settle=2.0: _ready(w, d)):
            watcher = sv.SceneWatcher(FILM, SPANS, self.work, keep_previous=False)
            watcher.start()
            report = watcher.finish()
        self.assertTrue(report["complete"])
        self.assertEqual(calls, [[1, 2, 3, 4], [5]])


def _ready(w, frames_dir):
    return all(os.path.exists(os.path.join(frames_dir, f"f_{f:04d}.png")) for f in range(w["f0"], w["f1"] + 1))


class AbortBlenderTests(unittest.TestCase):
    def test_parallel_render_is_terminated_on_rejection(self):
        import engine.make_film as mf

        class Proc:
            terminated = 0

            def __init__(self, cmd, stdout, stderr, text):
                self.alive = True

            def poll(self):
                return None if self.alive else 0

            def terminate(self):
                Proc.terminated += 1
                self.alive = False

            def wait(self):
                pass

        class Watcher:
            def should_abort(self):
                return True
        spans = [{"start": 0, "end": 99}, {"start": 100, "end": 199}, {"start": 200, "end": 999}]
        with patch.object(mf.subprocess, "Popen", Proc):
            out = mf._render_parallel(["blender"], spans, 1000, 2, tempfile.mkdtemp(), start=1, hook=False,
                                      watcher=Watcher())
        self.assertEqual(out, "aborted")
        self.assertEqual(Proc.terminated, 2)


class SetBuilderTests(unittest.TestCase):
    def test_static_checks_pass_on_the_bridge_set(self):
        from agents import set_builder as sb
        self.assertEqual(sb.static_checks("bridge_evolution"), [])

    def test_static_checks_pass_on_a_max_story_set(self):
        from agents import set_builder as sb
        self.assertEqual(sb.static_checks("boat_story", story=True), [])

    def test_register_adds_once(self):
        from agents import set_builder as sb
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, "engine", "sets"))
        p = os.path.join(root, "engine", "sets", "__init__.py")
        open(p, "w").write('AVAILABLE = ["a"]\nEVOLUTION = ["bridge_evolution"]   # comment\n')
        with patch.object(sb, "PROJECT_ROOT", root):
            sb.register("ship_evolution")
            sb.register("ship_evolution")
        self.assertIn('EVOLUTION = ["bridge_evolution", "ship_evolution"]', open(p).read())

    def test_registers_story_in_available_once(self):
        from agents import set_builder as sb
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, "engine", "sets"))
        p = os.path.join(root, "engine", "sets", "__init__.py")
        open(p, "w").write('AVAILABLE = ["pool_story"]\nEVOLUTION = ["bridge_evolution"]\n')
        with patch.object(sb, "PROJECT_ROOT", root):
            sb.register("heat_pump_story", "AVAILABLE")
            sb.register("heat_pump_story", "AVAILABLE")
        self.assertIn('AVAILABLE = ["pool_story", "heat_pump_story"]', open(p).read())

    def test_preview_fingerprint_changes_only_when_render_inputs_change(self):
        from agents import set_builder as sb
        root = tempfile.mkdtemp()
        for directory in ("engine", os.path.join("engine", "films"), os.path.join("engine", "sets")):
            os.makedirs(os.path.join(root, directory), exist_ok=True)
        files = {
            "engine/shared.py": "SHARED = 1\n",
            "engine/films/cutaway_film.py": "# runner\n",
            "engine/films/demo_story.json": "{}\n",
            "engine/sets/demo_story.py": "# set\n",
            "engine/sets/demo_story_spec.py": "# spec\n",
        }
        for relative, content in files.items():
            with open(os.path.join(root, relative), "w", encoding="utf-8") as fh:
                fh.write(content)
        runner = os.path.join(root, "engine", "films", "cutaway_film.py")
        with patch.object(sb, "PROJECT_ROOT", root):
            first = sb._preview_fingerprint("demo_story", runner, True)
            self.assertEqual(first, sb._preview_fingerprint("demo_story", runner, True))
            with open(os.path.join(root, "engine", "sets", "demo_story.py"), "a", encoding="utf-8") as fh:
                fh.write("CHANGED = 1\n")
            self.assertNotEqual(first, sb._preview_fingerprint("demo_story", runner, True))

    def test_complete_preview_does_not_require_synthesized_rewind_stills(self):
        from agents import set_builder as sb
        work = tempfile.mkdtemp()
        film = {"beats": [{"action": "hook"}, {"action": "rewind"}, {"action": "build"}]}

        class Spec:
            ACTIONS = {"hook": {"kind": "hook"}, "rewind": {"kind": "rewind"},
                       "build": {"kind": "build"}}

        for beat in (1, 3):
            for tag in "abc":
                open(os.path.join(work, f"preview_{beat:02d}_scene_{tag}.png"), "wb").write(b"image")
        self.assertTrue(sb._complete_preview(work, film, Spec))

    def test_fake_timings(self):
        from agents import set_builder as sb
        p = os.path.join(tempfile.mkdtemp(), "t.json")
        spans = sb.fake_timings({"beats": [{"text": "one two"}, {"text": " ".join(["w"] * 48)}]}, p)
        self.assertEqual(spans[0], {"start": 0, "end": 74})
        self.assertEqual(json.load(open(p))["total_frames"], spans[-1]["end"] + 1)


if __name__ == "__main__":
    unittest.main()


class VoidTests(unittest.TestCase):
    def test_black_band_below_the_world_is_fatal(self):
        rng = np.random.default_rng(0)
        scene = (rng.random((480, 270, 3)) * 200 + 30).astype(np.uint8)
        void = scene.copy()
        void[-120:] = 0                                   # the ground ends a quarter above the bottom
        with tempfile.TemporaryDirectory() as d:
            ok, bad = os.path.join(d, "ok.png"), os.path.join(d, "bad.png")
            Image.fromarray(scene).save(ok)
            Image.fromarray(void).save(bad)
            self.assertTrue(sv.technical_check([ok])["valid"])
            report = sv.technical_check([bad])
        self.assertFalse(report["valid"])
        self.assertIn("void", report["fatal_problems"][0])
