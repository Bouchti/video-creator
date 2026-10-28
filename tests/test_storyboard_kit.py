"""The storyboard pipeline: a planned story is DATA in the kit's vocabulary, validated and compiled into a set
with no coding agent and no repair loop."""
import copy
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from agents import kit_planner, set_builder as sb, storyboard as sbm


def _steps(*specs):
    return [{"id": i, "kind": k, "change": c, "event": e, "weather": "rain", "label": lbl} for i, k, c, e, lbl in specs]


class ValidateTests(unittest.TestCase):
    def test_the_reference_storyboard_is_filmable(self):
        self.assertEqual(sbm.validate(sbm.LEVEE), [])

    def test_a_fix_must_answer_a_failure_and_needs_what_it_uses(self):
        sb_ = copy.deepcopy(sbm.LEVEE)
        sb_["steps"][2]["change"] = "none"                     # fix_core without the core it shows
        problems = sbm.validate(sb_)
        self.assertTrue(any("needs ['core']" in p for p in problems), problems)

    def test_events_are_refused_on_barrier_shapes_the_kit_was_not_built_for(self):
        sb_ = copy.deepcopy(sbm.LEVEE)
        sb_["steps"] = sb_["steps"][:3] + [sb_["steps"][7], sb_["steps"][8], sb_["steps"][9]]   # piping on a wide wall
        problems = sbm.validate(sb_)
        self.assertTrue(any("built for a raised barrier" in p for p in problems), problems)

    def test_order_hooks_labels_and_first_build(self):
        sb_ = {"world": "embankment", "gag": "duck", "title": "t", "subject": "s", "model_facts": [],
               "steps": _steps(("promise", "setup", "none", "calm", ""),
                               ("fail_x", "fail", "clay_core_widen", "seep_slump", "A VERY LONG LABEL TEXT HERE"),
                               ("finale", "finale", "none", "storm_holds", "")),
               "hooks": [{"id": "hook_a", "step": "promise"}]}
        problems = " | ".join(sbm.validate(sb_))
        for needle in ("5-11", "needs the barrier built first", "over 18 characters", "followed by the fix",
                       "must replay a fail step"):
            self.assertIn(needle, problems)


class CompileTests(unittest.TestCase):
    def test_compile_writes_a_set_the_pipeline_can_use(self):
        root = tempfile.mkdtemp()
        for d in ("engine/sets", "engine/films"):
            os.makedirs(os.path.join(root, d))
        set_id = sbm.compile_set(sbm.LEVEE, "kit_test_story", root=root)
        ns = {}
        exec(compile(open(os.path.join(root, "engine", "sets", f"{set_id}_spec.py"), encoding="utf-8").read(),
                     "spec", "exec"), ns)
        self.assertEqual(ns["KIT"], "embankment")
        self.assertEqual(ns["STORY_ORDER"], [s["id"] for s in sbm.LEVEE["steps"]])
        for a, v in ns["ACTIONS"].items():
            if v["kind"] != "rewind":
                self.assertTrue(v["must_see"] and v["shows"], a)
        film = json.load(open(os.path.join(root, "engine", "films", f"{set_id}.json"), encoding="utf-8"))
        self.assertEqual(ns["validate"](film["beats"]), [])
        builder = open(os.path.join(root, "engine", "sets", f"{set_id}.py"), encoding="utf-8").read()
        self.assertIn("class KitTestStorySet(EmbankmentSet)", builder)

    def test_an_invalid_storyboard_is_never_compiled(self):
        bad = dict(sbm.LEVEE, steps=sbm.LEVEE["steps"][:2])
        with self.assertRaises(ValueError):
            sbm.compile_set(bad, "kit_bad_story", root=tempfile.mkdtemp())


class PlannerTests(unittest.TestCase):
    def _plan(self, storyboard):
        return {"title": "T", "angle": "a", "hook_line": "h", "hook_action": "burrow_hook", "payoff": "p",
                "trend_signal": "news", "trend_source_url": "https://example.org/x", "fact_sheet": "- f",
                "storyboard": storyboard}

    def test_a_valid_plan_needs_one_call(self):
        calls = []

        def call(system, prompt, schema, effort="high", tools=None):
            calls.append(schema)
            return self._plan(copy.deepcopy(sbm.LEVEE))
        plan = kit_planner.plan_kit_story(call=call)
        self.assertEqual(len(calls), 1)
        self.assertTrue(plan["set_id"].startswith("kit_"))

    def test_one_cheap_correction_then_a_clear_refusal(self):
        broken = dict(copy.deepcopy(sbm.LEVEE), steps=sbm.LEVEE["steps"][:2])
        answers = [self._plan(broken), copy.deepcopy(sbm.LEVEE)]
        efforts = []

        def call(system, prompt, schema, effort="high", tools=None):
            efforts.append(effort)
            return answers.pop(0)
        plan = kit_planner.plan_kit_story(call=call)
        self.assertEqual(efforts, ["medium", "low"])
        self.assertEqual(plan["storyboard"], sbm.LEVEE)
        answers[:] = [self._plan(broken), broken]
        with self.assertRaises(RuntimeError):
            kit_planner.plan_kit_story(call=call)


class BuildKitSetTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        for d in ("engine/sets", "engine/films", "output/sets"):
            os.makedirs(os.path.join(self.root, d))
        open(os.path.join(self.root, "engine", "sets", "__init__.py"), "w").write('AVAILABLE = ["boat_story"]\n')
        self.p = [patch.object(sb, "PROJECT_ROOT", self.root), patch.object(sbm, "PROJECT_ROOT", self.root),
                  patch.object(sb, "contact_sheet", return_value=None)]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()

    def test_verified_without_any_agent_and_registered(self):
        with patch.object(sb, "preview_render", return_value=""), patch.object(sb, "qa_check", return_value={}), \
                patch.object(sb, "review_preview", return_value=[]), \
                patch.object(sb, "claude_agent", side_effect=AssertionError("no coding agent")):
            status = sb.build_kit_set({"storyboard": sbm.LEVEE, "set_id": "kit_x_story"})
        self.assertTrue(status["accepted"])
        self.assertIn('"kit_x_story"', open(os.path.join(self.root, "engine", "sets", "__init__.py")).read())

    def test_a_measured_defect_is_a_kit_bug_not_a_retry(self):
        with patch.object(sb, "preview_render", return_value=""), \
                patch.object(sb, "qa_check", return_value={4: ["floating: Max has no surface under the feet"]}):
            with self.assertRaisesRegex(sb.KitDefect, "floating"):
                sb.build_kit_set({"storyboard": sbm.LEVEE, "set_id": "kit_x_story"})

    def test_vision_notes_are_advisory(self):
        notes = [{"beat": 3, "action": "promise", "valid": False, "fatal_problems": ["duck small"]}]
        with patch.object(sb, "preview_render", return_value=""), patch.object(sb, "qa_check", return_value={}), \
                patch.object(sb, "review_preview", return_value=notes):
            status = sb.build_kit_set({"storyboard": sbm.LEVEE, "set_id": "kit_x_story"})
        self.assertTrue(status["accepted"])
        self.assertEqual(status["review_notes"][0]["problems"], ["duck small"])


if __name__ == "__main__":
    unittest.main()
