"""Autopilot: every failure type is repaired and the stage redone (all external work mocked)."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from agents import autopilot as ap
from agents import scene_validator as sv
import engine.make_film as mf


class _Env(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.film = os.path.join(self.tmp, "f.json")
        json.dump({"title": "T", "set": "bridge_evolution", "format": "evolution", "beats": [],
                   "meta": {"caption": "c", "hashtags": ["#a"]}}, open(self.film, "w"))
        self.video = os.path.join(self.tmp, "f.mp4")
        open(self.video, "w").write("x")
        self.p = [patch.object(ap, "RUNS_DIR", os.path.join(self.tmp, "runs")),
                  patch.object(ap, "BACKUPS", os.path.join(self.tmp, "runs", "backups")),
                  patch.object(ap.time, "sleep", lambda s: None),
                  patch.object(ap, "_backup", lambda set_id, run: None)]
        for x in self.p:
            x.start()
        self.run = ap.Run(source="evolution")

    def tearDown(self):
        for x in self.p:
            x.stop()

    def _produce(self, outcomes):
        calls = []

        def produce(args):
            calls.append(args)
            o = outcomes.pop(0)
            if isinstance(o, Exception):
                raise o
            return o
        return produce, calls


class RenderRepairTests(_Env):
    def test_code_crash_is_fixed_by_claude_then_resumed(self):
        produce, calls = self._produce([mf.BlenderFailed("Traceback (most recent call last):\n  boom"), self.video])
        fixed = []
        with patch.object(mf, "produce", produce), \
                patch("agents.set_builder.fix_code", lambda set_id, log_, allowed=None: fixed.append(set_id)):
            out, flagged = ap.stage_render(self.run, self.film)
        self.assertEqual((out, flagged), (self.video, False))
        self.assertEqual(fixed, ["bridge_evolution"])
        self.assertEqual(len(calls), 2)

    def test_gpu_crash_is_retried_without_code_changes(self):
        produce, calls = self._produce([mf.BlenderFailed("EXCEPTION_ACCESS_VIOLATION"), self.video])
        with patch.object(mf, "produce", produce), \
                patch("agents.set_builder.fix_code", side_effect=AssertionError("must not edit code")):
            out, _ = ap.stage_render(self.run, self.film)
        self.assertEqual(out, self.video)

    def test_persistent_rejection_fails_closed(self):
        rej = sv.SceneRejected([{"window": 1, "t0": 0, "t1": 3, "action": "plank", "fatal_problems": ["x"]}], "r.json")
        outcomes = [rej] * 2
        produce, calls = self._produce(outcomes)
        with patch.object(mf, "produce", produce), \
                patch.dict(os.environ, {"AUTOPILOT_MAX_ATTEMPTS": "2"}), \
                patch.object(ap, "_restore_first_backup", lambda s, r: None):
            with self.assertRaises(ap.GiveUp):
                ap.stage_render(self.run, self.film)
        self.assertEqual(len(calls), 2)

    def test_give_up_fail_mode_raises(self):
        rej = sv.SceneRejected([], "r.json")
        produce, _ = self._produce([rej, rej])
        with patch.object(mf, "produce", produce), \
                patch.dict(os.environ, {"AUTOPILOT_MAX_ATTEMPTS": "2", "AUTOPILOT_ON_GIVE_UP": "fail"}), \
                patch.object(ap, "_restore_first_backup", lambda s, r: None):
            with self.assertRaises(ap.GiveUp):
                ap.stage_render(self.run, self.film)

    def test_voice_out_of_credits_stops_clearly(self):
        produce, _ = self._produce([Exception("All ElevenLabs keys are out of credits or unusable: ...")])
        with patch.object(mf, "produce", produce):
            with self.assertRaises(ap.GiveUp):
                ap.stage_render(self.run, self.film)

    def test_network_error_is_retried(self):
        produce, calls = self._produce([Exception("ElevenLabs failed (key1): 503 busy"), self.video])
        with patch.object(mf, "produce", produce):
            out, _ = ap.stage_render(self.run, self.film)
        self.assertEqual(len(calls), 2)


class ScriptAndCheckTests(_Env):
    def test_script_retries_then_succeeds(self):
        tries = []

        def write(angle=None, set_id=None, render=True):
            tries.append(angle)
            if len(tries) < 3:
                raise RuntimeError("no renderable script")
            return self.film
        with patch("agents.evolution_writer.run", write):
            path = ap.stage_script(self.run, "evolution", "my angle", None)
        self.assertEqual(path, self.film)
        self.assertEqual(tries, ["my angle", "my angle", None])     # 3rd try: fresh angle

    def test_bad_final_video_is_rebuilt(self):
        probes = [["no audio stream"], []]
        produce, calls = self._produce([self.video])
        with patch.object(ap, "probe", lambda p: probes.pop(0)), patch.object(mf, "produce", produce):
            ap.stage_check(self.run, self.video, self.film)
        self.assertTrue(calls[0].remix)

    def test_cutaway_forwards_set_and_does_not_retry_consumed_subject(self):
        from agents.showrunner import NoUnusedStorySets
        calls = []

        def write(angle=None, render=True, set_id=None):
            calls.append((angle, set_id))
            raise NoUnusedStorySets("already consumed")

        with patch("agents.showrunner.run", write):
            with self.assertRaisesRegex(ap.GiveUp, "already consumed"):
                ap.stage_script(self.run, "cutaway", None, "nuclear_story")
        self.assertEqual(calls, [(None, "nuclear_story")])

    def test_cutaway_builds_new_story_when_library_is_exhausted(self):
        from agents.showrunner import NoUnusedStorySets
        calls = []
        plan = {"subject": "Max builds a heat pump", "set_id": "heat_pump_story",
                "build_brief": "A cutaway home and ground loop."}

        def write(angle=None, render=True, set_id=None):
            calls.append(set_id)
            if set_id is None:
                raise NoUnusedStorySets("all consumed")
            return self.film

        accepted = {"accepted": True, "set": "heat_pump_story", "work": self.tmp}
        with patch("agents.showrunner.run", write), \
                patch("agents.showrunner.plan_new_story_set", return_value=plan), \
                patch("agents.set_builder.build_story_set", return_value=accepted) as build:
            path = ap.stage_script(self.run, "cutaway", None, None)
        self.assertEqual(path, self.film)
        self.assertEqual(calls, [None, "heat_pump_story"])
        build.assert_called_once_with("A cutaway home and ground loop.", "heat_pump_story", rounds=4)
        self.assertEqual(self.run["generated_set"], "heat_pump_story")

    def test_run_record_is_resumable(self):
        self.run.set(film=self.film, render_attempts=2)
        again = ap.Run(self.run.path)
        self.assertEqual(again["film"], self.film)
        self.assertEqual(ap.stage_script(again, "evolution", None, None), self.film)


if __name__ == "__main__":
    unittest.main()
