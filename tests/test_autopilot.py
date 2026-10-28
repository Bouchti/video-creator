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
    def test_first_attempt_of_a_manual_resume_keeps_existing_frames(self):
        work = os.path.join(self.tmp, "f_work")
        os.makedirs(os.path.join(work, "frames"))
        open(os.path.join(work, "frames", "f_0001.png"), "wb").write(b"frame")
        open(os.path.join(work, "voice.mp3"), "wb").write(b"voice")
        produce, calls = self._produce([self.video])
        with patch.object(ap, "get_output_dir", return_value=self.tmp), patch.object(mf, "produce", produce):
            ap.stage_render(self.run, self.film)
        self.assertTrue(calls[0].resume)
        self.assertTrue(calls[0].reuse_voice)

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

    def test_persistent_rejection_fails_closed_when_explicitly_requested(self):
        rej = sv.SceneRejected([{"window": 1, "t0": 0, "t1": 3, "action": "plank", "fatal_problems": ["x"]}], "r.json")
        outcomes = [rej] * 2
        produce, calls = self._produce(outcomes)
        with patch.object(mf, "produce", produce), \
                patch.dict(os.environ, {"AUTOPILOT_MAX_ATTEMPTS": "2", "AUTOPILOT_ON_GIVE_UP": "fail"}), \
                patch.object(ap, "_restore_first_backup", lambda s, r: None):
            with self.assertRaises(ap.GiveUp):
                ap.stage_render(self.run, self.film)
        self.assertEqual(len(calls), 2)

    def test_persistent_rejection_ships_flagged_draft_by_default(self):
        rej = sv.SceneRejected([{"window": 1, "t0": 0, "t1": 3, "action": "plank",
                                 "fatal_problems": ["x"]}], "r.json")
        produce, calls = self._produce([rej, self.video])
        with patch.object(mf, "produce", produce), \
                patch.dict(os.environ, {"AUTOPILOT_MAX_ATTEMPTS": "1", "AUTOPILOT_ON_GIVE_UP": ""}), \
                patch.object(ap, "_restore_first_backup", lambda s, r: None):
            out, flagged = ap.stage_render(self.run, self.film)
            self.assertEqual(os.environ["SCENE_VALIDATE"], "0")
        self.assertEqual((out, flagged), (self.video, True))
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
    def test_unknown_ai_reset_stops_instead_of_sleeping_for_an_hour(self):
        from agents.showrunner import UsageLimit
        with self.assertRaisesRegex(ap.GiveUp, "sleeping blindly"):
            ap._wait_for_claude(UsageLimit("both subscriptions unavailable"), self.run, "script")
        self.assertIn("stopped safely", self.run["events"][-1]["what"])

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

    def test_programming_error_fails_fast_instead_of_spending_six_more_turns(self):
        calls = []

        def write(angle=None, set_id=None, render=True):
            calls.append(1)
            raise TypeError("'NoneType' object is not subscriptable")

        with patch("agents.evolution_writer.run", write):
            with self.assertRaisesRegex(ap.GiveUp, "pipeline code error"):
                ap.stage_script(self.run, "evolution", None, None)
        self.assertEqual(len(calls), 1)

    def test_bad_final_video_is_rebuilt(self):
        probes = [["no audio stream"], []]
        produce, calls = self._produce([self.video])
        with patch.object(ap, "probe", lambda p: probes.pop(0)), patch.object(mf, "produce", produce):
            ap.stage_check(self.run, self.video, self.film)
        self.assertTrue(calls[0].remix)

    def test_cutaway_forwards_set_and_does_not_retry_consumed_subject(self):
        from agents.showrunner import NoUnusedStorySets
        calls = []

        def write(angle=None, render=True, set_id=None, topic_hint=None, on_topic=None):
            calls.append((angle, set_id))
            raise NoUnusedStorySets("already consumed")

        with patch("agents.showrunner.run", write):
            with self.assertRaisesRegex(ap.GiveUp, "already consumed"):
                ap.stage_script(self.run, "cutaway", None, "nuclear_story")
        self.assertEqual(calls, [(None, "nuclear_story")])

    def test_set_repair_without_changes_stops_instead_of_retrying(self):
        from agents.set_builder import RepairNotApplied
        from agents.showrunner import NoUnusedStorySets
        plan = {"subject": "levee", "set_id": "levee_story", "build_brief": "brief"}

        def write(angle=None, render=True, set_id=None, topic_hint=None, on_topic=None):
            raise NoUnusedStorySets("all consumed")

        with patch("agents.showrunner.run", write), patch.dict(os.environ, {"SHOWRUNNER_SET_MODE": "agent"}), \
                patch("agents.showrunner.plan_new_story_set", return_value=plan), \
                patch("agents.set_builder.build_story_set",
                      side_effect=RepairNotApplied("AI repair made no source changes")) as build, \
                patch.object(ap.time, "sleep", side_effect=AssertionError("must not wait to retry")):
            with self.assertRaisesRegex(ap.GiveUp, "made no changes"):
                ap.stage_script(self.run, "cutaway", None, None)
        build.assert_called_once()

    def test_cutaway_builds_new_story_when_library_is_exhausted(self):
        from agents.showrunner import NoUnusedStorySets
        calls = []
        plan = {"subject": "Max builds a heat pump", "set_id": "heat_pump_story",
                "build_brief": "A cutaway home and ground loop."}

        def write(angle=None, render=True, set_id=None, topic_hint=None, on_topic=None):
            calls.append(set_id)
            if set_id is None:
                raise NoUnusedStorySets("all consumed")
            return self.film

        accepted = {"accepted": True, "set": "heat_pump_story", "work": self.tmp}
        with patch("agents.showrunner.run", write), \
                patch.dict(os.environ, {"SET_BUILD_ROUNDS": "4", "SHOWRUNNER_SET_MODE": "agent"}), \
                patch("agents.showrunner.plan_new_story_set", return_value=plan), \
                patch("agents.set_builder.build_story_set", return_value=accepted) as build:
            path = ap.stage_script(self.run, "cutaway", None, None)
        self.assertEqual(path, self.film)
        self.assertEqual(calls, [None, "heat_pump_story"])
        build.assert_called_once_with("A cutaway home and ground loop.", "heat_pump_story", rounds=4)
        self.assertEqual(self.run["generated_set"], "heat_pump_story")

    def test_an_exhausted_library_is_filmed_by_the_kit_without_any_agent(self):
        from agents.showrunner import NoUnusedStorySets
        from agents import storyboard as sbm
        calls = []
        plan = {"title": "Max's Backyard Levee", "set_id": "kit_demo_story", "storyboard": sbm.LEVEE,
                "subject": "levee"}

        def write(angle=None, render=True, set_id=None, topic_hint=None, on_topic=None):
            calls.append(set_id)
            if set_id is None:
                raise NoUnusedStorySets("all consumed")
            return self.film

        accepted = {"accepted": True, "set": "kit_demo_story", "work": self.tmp}
        with patch("agents.showrunner.run", write), \
                patch.dict(os.environ, {"SHOWRUNNER_SET_MODE": "kit"}), \
                patch("agents.kit_planner.plan_kit_story", return_value=plan) as planner, \
                patch("agents.set_builder.build_kit_set", return_value=accepted) as build, \
                patch("agents.set_builder.build_story_set", side_effect=AssertionError("no coding agent")):
            path = ap.stage_script(self.run, "cutaway", None, None)
        self.assertEqual(path, self.film)
        planner.assert_called_once()
        build.assert_called_once()
        self.assertEqual(calls, [None, "kit_demo_story"])
        self.assertEqual(self.run["generated_set"], "kit_demo_story")

    def test_a_kit_defect_stops_the_run_instead_of_retrying(self):
        from agents.showrunner import NoUnusedStorySets
        from agents.set_builder import KitDefect
        from agents import storyboard as sbm
        plan = {"title": "T", "set_id": "kit_demo_story", "storyboard": sbm.LEVEE, "subject": "levee"}

        def write(angle=None, render=True, set_id=None, topic_hint=None, on_topic=None):
            raise NoUnusedStorySets("all consumed")

        with patch("agents.showrunner.run", write), patch.dict(os.environ, {"SHOWRUNNER_SET_MODE": "kit"}), \
                patch("agents.kit_planner.plan_kit_story", return_value=plan), \
                patch("agents.set_builder.build_kit_set", side_effect=KitDefect("measured: Max floats")) as build, \
                patch.object(ap.time, "sleep", side_effect=AssertionError("must not retry")):
            with self.assertRaisesRegex(ap.GiveUp, "Max floats"):
                ap.stage_script(self.run, "cutaway", None, None)
        build.assert_called_once()

    def test_cutaway_retry_reuses_the_selected_topic(self):
        chosen = {"set": "record_chasing_giant_pumpkin_story", "title": "Pumpkin",
                  "angle": "split", "hook_line": "It split.", "hook_action": "split_hook",
                  "payoff": "fixed", "trend_signal": "current", "trend_source_url": "https://example.test"}
        hints = []

        def write(angle=None, render=True, set_id=None, topic_hint=None, on_topic=None):
            hints.append(topic_hint)
            if len(hints) == 1:
                on_topic(chosen)
                raise RuntimeError("editor rejected first draft")
            return self.film

        with patch("agents.showrunner.run", write):
            path = ap.stage_script(self.run, "cutaway", None, "record_chasing_giant_pumpkin_story")
        self.assertEqual(path, self.film)
        self.assertIsNone(hints[0])
        self.assertEqual(hints[1], chosen)
        self.assertEqual(self.run["script_topic"], chosen)

    def test_run_record_is_resumable(self):
        self.run.set(film=self.film, render_attempts=2)
        again = ap.Run(self.run.path)
        self.assertEqual(again["film"], self.film)
        self.assertEqual(ap.stage_script(again, "evolution", None, None), self.film)

    def test_explicit_resume_renews_attempts_and_backup_baseline(self):
        self.run.set(film=self.film, video=self.video, render_attempts=6,
                     first_backup=os.path.join(self.tmp, "old_backup.py"))
        with patch.object(ap, "stage_script", return_value=self.film), \
                patch.object(ap, "stage_render", return_value=(self.video, False)), \
                patch.object(ap, "stage_check", return_value=self.video), \
                patch.object(ap, "write_notes", return_value=self.video + ".txt"), \
                patch.object(ap, "_cleanup_successful_work"):
            ap.run(resume_path=self.run.path)
        again = ap.Run(self.run.path)
        self.assertEqual(again["render_attempts"], 0)
        self.assertIsNone(again["first_backup"])

    def test_success_cleanup_removes_only_reproducible_frame_caches(self):
        work = os.path.join(self.tmp, "f_work")
        for leaf in ("frames", "comp"):
            os.makedirs(os.path.join(work, leaf), exist_ok=True)
            open(os.path.join(work, leaf, "f_0001.png"), "wb").write(b"1234")
        open(os.path.join(work, "voice.mp3"), "wb").write(b"voice")
        with patch.object(ap, "get_output_dir", return_value=self.tmp), \
                patch.dict(os.environ, {"AUTOPILOT_KEEP_WORKFILES": "0"}):
            self.assertEqual(ap._cleanup_successful_work(self.film), 8)
        self.assertFalse(os.path.exists(os.path.join(work, "frames")))
        self.assertFalse(os.path.exists(os.path.join(work, "comp")))
        self.assertTrue(os.path.exists(os.path.join(work, "voice.mp3")))


if __name__ == "__main__":
    unittest.main()


class BudgetAcrossResumeTests(_Env):
    def test_a_resumed_run_keeps_counting_its_earlier_spend(self):
        from agents import showrunner
        with patch.dict(showrunner.CLAUDE_USAGE, {"input_tokens": 0, "cache_read_input_tokens": 2_500_000,
                                                  "cache_creation_input_tokens": 0, "output_tokens": 0}):
            self.run.event("set", "a costly turn")
            self.assertEqual(json.load(open(self.run.path, encoding="utf-8"))["claude_tokens"], 2_500_000)
        try:
            with patch.dict(showrunner.CLAUDE_USAGE, {"input_tokens": 0, "cache_read_input_tokens": 0,
                                                      "cache_creation_input_tokens": 0, "output_tokens": 0}), \
                    patch.dict(os.environ, {"CLAUDE_TOKEN_BUDGET": "2000000"}),                     patch.object(showrunner, "BACKEND", "subscription"),                     patch.object(showrunner, "_ACTIVE_BACKEND", [None]):
                ap.Run(self.run.path)                    # a new process resumes the run
                self.assertEqual(showrunner.tokens_used(), 2_500_000)
                with self.assertRaises(showrunner.BudgetExceeded):
                    showrunner.check_budget("next call")
        finally:
            showrunner.carry_tokens(0)
