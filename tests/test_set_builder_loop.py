"""The set build loop must make monotonic progress: accepted beats cannot be broken by a repair turn."""
import os
import tempfile
import unittest
from unittest.mock import patch

from agents import set_builder as sb

SET = '''import math


class DemoStorySet:
    def helper(self):
        return 1

    def a_one(self, i, b, e):
        return "one v1"

    def a_two(self, i, b, e):
        return "two v1"
'''


class FreezeTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "engine", "sets"))
        self.path = os.path.join(self.root, "engine", "sets", "demo_story.py")
        open(self.path, "w", encoding="utf-8").write(SET)
        self.p = patch.object(sb, "PROJECT_ROOT", self.root)
        self.p.start()

    def tearDown(self):
        self.p.stop()

    def test_an_accepted_beat_is_put_back_and_other_edits_are_kept(self):
        frozen = sb.freeze_methods("demo_story", ["one"])
        edited = SET.replace('"one v1"', '"one v2"').replace('"two v1"', '"two v2"').replace("return 1", "return 2")
        open(self.path, "w", encoding="utf-8").write(edited)
        self.assertEqual(sb.restore_methods("demo_story", frozen), ["a_one"])
        src = open(self.path, encoding="utf-8").read()
        self.assertIn('"one v1"', src)                 # accepted beat: as it was
        self.assertIn('"two v2"', src)                 # rejected beat: the repair stays
        self.assertIn("return 2", src)                 # shared code: the repair stays
        compile(src, self.path, "exec")

    def test_unchanged_methods_are_left_alone(self):
        frozen = sb.freeze_methods("demo_story", ["one", "two"])
        self.assertEqual(sb.restore_methods("demo_story", frozen), [])
        self.assertEqual(open(self.path, encoding="utf-8").read(), SET)

    def test_a_method_the_repair_deleted_is_not_resurrected(self):
        frozen = sb.freeze_methods("demo_story", ["two"])
        open(self.path, "w", encoding="utf-8").write(SET.split("    def a_two")[0])
        self.assertEqual(sb.restore_methods("demo_story", frozen), [])


def _report(beat, action, valid):
    return {"beat": beat, "window": beat, "action": action, "valid": valid,
            "fatal_problems": [] if valid else ["missing"], "average_score": 7 if valid else 4}


class LoopTests(FreezeTests):
    def _files(self):
        for rel in sb._files("demo_story")[::2]:          # spec + film json (the builder already exists)
            path = os.path.join(self.root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w").write("{}")

    def test_repair_cannot_break_an_accepted_beat_and_the_set_is_accepted(self):
        self._files()
        rounds = [[_report(1, "one", True), _report(2, "two", False)],
                  [_report(1, "one", True), _report(2, "two", True)]]
        seen = []

        def repair(set_id, rejected, allowed=None, keep=None, max_windows=None, allow_edit=True, measure=True):
            seen.append((keep, max_windows, allow_edit, measure))
            src = open(self.path, encoding="utf-8").read()
            open(self.path, "w", encoding="utf-8").write(src.replace('"one v1"', '"one broken"')
                                                          .replace('"two v1"', '"two fixed"'))

        with patch.object(sb, "static_checks", return_value=[]), \
                patch.object(sb, "preview_render", return_value=""), \
                patch.object(sb, "review_preview", side_effect=lambda *a: rounds.pop(0)), \
                patch.object(sb, "contact_sheet", return_value=None), \
                patch.object(sb, "register") as register, \
                patch.object(sb, "fix_scenes", side_effect=repair), \
                patch.dict(os.environ, {"SET_FIX_MAX_WINDOWS": ""}):
            status = sb.build_set("demo", "demo_story", rounds=3, story=True)
        self.assertTrue(status["accepted"])
        register.assert_called_once()
        self.assertEqual(seen, [(["one"], 3, False, False)])      # small turn, one full rewrite (no Edit tool)
        src = open(self.path, encoding="utf-8").read()
        self.assertIn('"one v1"', src)
        self.assertIn('"two fixed"', src)

    def test_a_restore_that_breaks_the_build_is_undone_without_a_paid_turn(self):
        self._files()
        renders = ["", "Traceback (most recent call last): NameError", ""]
        rounds = [[_report(1, "one", True), _report(2, "two", False)],
                  [_report(1, "one", True), _report(2, "two", True)]]

        def repair(set_id, rejected, allowed=None, keep=None, max_windows=None, allow_edit=True, measure=True):
            src = open(self.path, encoding="utf-8").read()
            open(self.path, "w", encoding="utf-8").write(src.replace('"one v1"', '"one v2"'))

        with patch.object(sb, "static_checks", return_value=[]), \
                patch.object(sb, "preview_render", side_effect=lambda *a: renders.pop(0)), \
                patch.object(sb, "review_preview", side_effect=lambda *a: rounds.pop(0)), \
                patch.object(sb, "contact_sheet", return_value=None), \
                patch.object(sb, "register"), \
                patch.object(sb, "fix_scenes", side_effect=repair), \
                patch.object(sb, "claude_agent", side_effect=AssertionError("no paid turn for this")):
            status = sb.build_set("demo", "demo_story", rounds=3, story=True)
        self.assertTrue(status["accepted"])
        self.assertIn('"one v2"', open(self.path, encoding="utf-8").read())

    def test_two_repairs_in_a_row_that_change_nothing_stop_the_build(self):
        self._files()
        with patch.object(sb, "static_checks", return_value=[]), \
                patch.object(sb, "preview_render", return_value=""), \
                patch.object(sb, "review_preview",
                             return_value=[_report(1, "one", True), _report(2, "two", False)]), \
                patch.object(sb, "contact_sheet", return_value=None), \
                patch.object(sb, "fix_scenes", side_effect=sb.RepairNotApplied("no changes")) as fix:
            with self.assertRaises(sb.RepairNotApplied):
                sb.build_set("demo", "demo_story", rounds=4, story=True)
        self.assertEqual(fix.call_count, 2)


if __name__ == "__main__":
    unittest.main()


class FilmRenderRepairTests(FreezeTests):
    def test_film_repair_keeps_fully_accepted_scenes_and_sends_a_few_windows(self):
        from types import SimpleNamespace
        from engine import make_film as mf
        windows = [dict(_report(1, "one", True), f0=1, f1=90), dict(_report(2, "two", True), f0=91, f1=180),
                   dict(_report(2, "two", False), f0=181, f1=270)]
        watcher = SimpleNamespace(policy="fix", report_path="r.json",
                                  finish=lambda: {"windows": windows, "rejected": windows[2:], "accepted": 2,
                                                  "planned": 3})
        seen = {}

        def repair(set_id, rejected, allowed=None, keep=None, max_windows=None, allow_edit=True, measure=True):
            seen.update(keep=keep, max_windows=max_windows)
            src = open(self.path, encoding="utf-8").read()
            open(self.path, "w", encoding="utf-8").write(src.replace('"one v1"', '"one v2"').replace('"two v1"', '"two v2"'))

        args = SimpleNamespace(film="demo", resume=False, reuse_voice=False, redo="")
        with patch.object(sb, "fix_scenes", side_effect=repair), \
                patch.object(mf, "produce", return_value="film.mp4"), \
                patch.dict(os.environ, {"SCENE_FIX_ATTEMPTS": "2", "SCENE_FIX_MAX_WINDOWS": "",
                                        "SET_FIX_MAX_WINDOWS": ""}):
            out = mf._scene_verdict(args, {"set": "demo_story"}, watcher, [{"start": 0}, {"start": 90}],
                                    tempfile.mkdtemp())
        self.assertEqual(out, "film.mp4")
        self.assertEqual(seen, {"keep": ["one"], "max_windows": 3})       # beat 2 has a rejected window
        self.assertEqual(args.redo, "2")
        src = open(self.path, encoding="utf-8").read()
        self.assertIn('"one v1"', src)
        self.assertIn('"two v2"', src)

    def test_film_repair_uses_scene_specific_window_cap(self):
        from types import SimpleNamespace
        from engine import make_film as mf
        rejected = [dict(_report(2, "two", False), f0=181, f1=270)]
        watcher = SimpleNamespace(policy="fix", report_path="r.json",
                                  finish=lambda: {"windows": rejected, "rejected": rejected,
                                                  "accepted": 0, "planned": 1})
        seen = {}

        def repair(set_id, windows, allowed=None, keep=None, max_windows=None,
                   allow_edit=True, measure=True):
            seen["max_windows"] = max_windows

        args = SimpleNamespace(film="demo", resume=False, reuse_voice=False, redo="")
        with patch.object(sb, "fix_scenes", side_effect=repair), \
                patch.object(mf, "produce", return_value="film.mp4"), \
                patch.dict(os.environ, {"SCENE_FIX_ATTEMPTS": "2", "SCENE_FIX_MAX_WINDOWS": "6",
                                        "SET_FIX_MAX_WINDOWS": "3"}):
            mf._scene_verdict(args, {"set": "demo_story"}, watcher, [{"start": 0}, {"start": 90}],
                              tempfile.mkdtemp())
        self.assertEqual(seen["max_windows"], 6)


SPEC = '''SET_ID = "demo_story"
ACTIONS = {
    # hooks
    "hook": {"kind": "hook", "shows": "the jet", "seconds": (3, 5)},
    "rewind": {"kind": "rewind", "shows": "rewind"},
    "one": {"kind": "story",
            "shows": "the levee leaks"},
    "two": {"must_see": ["kept"], "kind": "story", "shows": "x"},
}
'''


class MustSeeBackfillTests(FreezeTests):
    def test_insert_keeps_layout_and_existing_values(self):
        out = sb.insert_must_see(SPEC, {"hook": ["jet", "Max"], "one": ["levee"], "two": ["replaced"]})
        ns = {}
        exec(compile(out, "spec", "exec"), ns)
        self.assertEqual(ns["ACTIONS"]["hook"]["must_see"], ["jet", "Max"])
        self.assertEqual(ns["ACTIONS"]["one"]["must_see"], ["levee"])
        self.assertEqual(ns["ACTIONS"]["two"]["must_see"], ["kept"])        # an existing list is left alone
        self.assertNotIn("must_see", ns["ACTIONS"]["rewind"])
        self.assertIn("# hooks", out)

    def test_a_non_literal_actions_table_is_refused(self):
        with self.assertRaises(ValueError):
            sb.insert_must_see("ACTIONS = dict(a={})\n", {"a": ["x"]})

    def test_backfill_is_one_structured_call_not_an_agent_turn(self):
        spec_path = os.path.join(self.root, "engine", "sets", "demo_story_spec.py")
        open(spec_path, "w", encoding="utf-8").write(SPEC)
        answer = {"actions": [{"action": "hook", "must_see": ["jet"]}, {"action": "one", "must_see": ["levee"]}]}
        with patch("agents.showrunner._call", return_value=answer) as call, \
                patch.object(sb, "claude_agent", side_effect=AssertionError("no agent turn")):
            self.assertTrue(sb.backfill_must_see("demo_story"))
        self.assertEqual(call.call_args.kwargs["effort"], "low")
        self.assertIn('"must_see": ["levee"]', open(spec_path, encoding="utf-8").read())


class ExtrasBackfillTests(FreezeTests):
    def test_extras_come_from_one_structured_call(self):
        spec_path = os.path.join(self.root, "engine", "sets", "demo_story_spec.py")
        open(spec_path, "w", encoding="utf-8").write(SPEC)
        answer = {"actions": [{"action": "one", "extras": "the duck surfs the leak"}, {"action": "hook", "extras": ""}]}
        with patch("agents.showrunner._call", return_value=answer), \
                patch.object(sb, "claude_agent", side_effect=AssertionError("no agent turn")):
            self.assertTrue(sb.backfill_extras("demo_story"))
        ns = {}
        exec(compile(open(spec_path, encoding="utf-8").read(), "spec", "exec"), ns)
        self.assertEqual(ns["ACTIONS"]["one"]["extras"], "the duck surfs the leak")
        self.assertNotIn("extras", ns["ACTIONS"]["hook"])
