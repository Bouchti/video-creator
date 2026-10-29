"""Explainer route (--source explainer): no-hero cutaway explainers, kept apart from the Max route.
All AI, Blender and voice work is mocked."""
import copy
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from agents import autopilot as ap
from agents import storyboard as sbm
from agents import explainer
from agents import set_builder as sb
from agents import showrunner as sr
from engine import sets
import engine.make_film  # noqa: F401  (import before tests patch sys.modules)


TOPIC = {"set": "pool", "title": "Why pools float", "angle": "groundwater", "hook_line": "Empty pools can float.",
         "hook_action": "float_hook", "payoff": "the valve", "trend_signal": "storms",
         "trend_source_url": "https://example.test/storm", "_fact_sheet": "- fact [example.test]"}


class RegistryTests(unittest.TestCase):
    def test_explainer_sets_are_not_max_sets(self):
        self.assertIn("pool", sets.EXPLAINER)
        self.assertFalse(set(sets.EXPLAINER) & set(sets.AVAILABLE))
        for set_id in sets.EXPLAINER:
            self.assertIsNone(getattr(sets.spec(set_id), "HERO", None))

    def test_explainer_sets_get_the_no_hero_voice(self):
        from agents import buildup
        self.assertIs(sr._style("pool"), buildup.STYLE)          # the "If you ..." build-up format
        self.assertIs(sr._style("pool_story"), sr.STORY_STYLE)
        with patch.dict(os.environ, {"EXPLAINER_FORMAT": "hook"}):
            self.assertIs(sr._style("pool"), sr.STYLE)

    def test_max_topic_pick_never_sees_explainer_sets(self):
        self.assertEqual(sr.available_topic_sets(history=[]), list(sets.AVAILABLE))

    def test_pool_reference_film_passes_the_explainer_rules(self):
        film = json.load(open(os.path.join(os.path.dirname(__file__), "..", "engine", "films", "pool_cut.json"),
                              encoding="utf-8"))
        self.assertEqual(film["set"], "pool")
        self.assertEqual(sets.spec("pool").validate(film["beats"]), [])


class UsageTests(unittest.TestCase):
    def test_a_set_is_used_after_one_video_by_default(self):
        history = [{"set": "pool"}, {"set": "pool_story"}]
        with patch.dict(os.environ, {"EXPLAINER_MAX_USES": "", "SHOWRUNNER_ALLOW_REPEATS": "0"}):
            self.assertEqual(explainer.unused_sets(history), [])
            self.assertEqual(explainer.unused_sets([{"set": "pool_story"}]), ["pool"])

    def test_max_uses_allows_new_angles_on_the_same_set(self):
        with patch.dict(os.environ, {"EXPLAINER_MAX_USES": "2", "SHOWRUNNER_ALLOW_REPEATS": "0"}):
            self.assertEqual(explainer.unused_sets([{"set": "pool"}]), ["pool"])
            self.assertEqual(explainer.unused_sets([{"set": "pool"}] * 2), [])

    def test_new_set_ids_are_explainers(self):
        self.assertTrue(explainer.new_set_id("How a septic tank works").endswith("_explainer"))
        self.assertTrue(explainer.new_set_id("septic tank").startswith("septic_tank"))


class ChooseAndWriteTests(unittest.TestCase):
    def test_angle_is_matched_to_a_set_or_needs_a_new_one(self):
        with patch.object(explainer, "unused_sets", return_value=["pool"]), \
                patch.object(sr, "_call", return_value={"set": "pool", "reason": "same subject"}):
            self.assertEqual(explainer.choose_set("why pools have a floor valve"), "pool")
        with patch.object(explainer, "unused_sets", return_value=["pool"]), \
                patch.object(sr, "_call", return_value={"set": "none", "reason": "different subject"}):
            self.assertIsNone(explainer.choose_set("how a septic tank works"))

    def test_no_angle_lets_the_showrunner_choose_and_nothing_left_means_build(self):
        with patch.object(explainer, "unused_sets", return_value=["pool"]):
            self.assertEqual(explainer.choose_set(), "")
        with patch.object(explainer, "unused_sets", return_value=[]):
            self.assertIsNone(explainer.choose_set())

    def test_write_picks_among_explainer_sets_and_hands_the_topic_on(self):
        seen = {}

        def pick(set_ids=None, forced_angle=None):
            seen["sets"] = set_ids
            return dict(TOPIC)

        def run(angle=None, render=True, preview=False, set_id=None, topic_hint=None, on_topic=None):
            seen.update(set=set_id, hint=topic_hint, render=render)
            return "film.json"

        with patch.object(explainer, "unused_sets", return_value=["pool"]), \
                patch.object(sr, "pick_topic", pick), patch.object(sr, "run", run):
            self.assertEqual(explainer.write(), "film.json")
        self.assertEqual(seen["sets"], ["pool"])
        self.assertEqual(seen["set"], "pool")
        self.assertEqual(seen["hint"]["fact_sheet"], "- fact [example.test]")
        self.assertFalse(seen["render"])

    def test_weak_trend_becomes_a_new_set_request(self):
        with patch.object(explainer, "unused_sets", return_value=["pool"]), \
                patch.object(sr, "pick_topic", side_effect=sr.NoUnusedStorySets("weak trend")):
            with self.assertRaises(explainer.NoUnusedExplainerSets):
                explainer.write()

    def test_plan_normalises_the_hook_and_names_an_explainer_set(self):
        plan = {k: "x" for k in explainer.PLAN_SCHEMA["properties"]}
        plan.update(subject="Septic tank", hook_action="Overflow Hook", trend_source_url="https://e.test")
        with patch.object(sr, "_call", return_value=plan):
            out = explainer.plan_new_set()
        self.assertEqual(out["hook_action"], "overflow_hook")
        self.assertTrue(out["set_id"].endswith("_explainer"))

    def test_autonomous_plan_needs_a_trend_source(self):
        plan = {k: "x" for k in explainer.PLAN_SCHEMA["properties"]}
        plan.update(trend_source_url="")
        with patch.object(sr, "_call", return_value=plan):
            with self.assertRaises(explainer.NoUnusedExplainerSets):
                explainer.plan_new_set()
            self.assertTrue(explainer.plan_new_set("how a septic tank works")["set_id"])


class AutopilotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.film = os.path.join(self.tmp, "f.json")
        open(self.film, "w").write("{}")
        self.p = [patch.object(ap, "RUNS_DIR", os.path.join(self.tmp, "runs")),
                  patch.object(ap.time, "sleep", lambda s: None)]
        for x in self.p:
            x.start()
        self.run = ap.Run(source="explainer")

    def tearDown(self):
        for x in self.p:
            x.stop()

    def test_existing_set_is_used_and_max_is_never_touched(self):
        calls = []

        def run(angle=None, render=True, preview=False, set_id=None, topic_hint=None, on_topic=None):
            calls.append(set_id)
            on_topic(dict(TOPIC))
            return self.film

        with patch.object(explainer, "unused_sets", return_value=["pool"]), \
                patch.object(sr, "pick_topic", return_value=dict(TOPIC)), patch.object(sr, "run", run), \
                patch.object(sr, "plan_new_story_set", side_effect=AssertionError("Max planner")), \
                patch.object(sb, "build_story_set", side_effect=AssertionError("Max builder")):
            self.assertEqual(ap.stage_script(self.run, "explainer", None, None), self.film)
        self.assertEqual(calls, ["pool"])
        self.assertEqual(self.run["script_topic"]["set"], "pool")

    def test_no_hero_explainer_render_enables_the_exact_timing_preflight(self):
        video = os.path.join(self.tmp, "f.mp4")
        open(video, "wb").write(b"video")
        json.dump({"set": "pool", "beats": []}, open(self.film, "w"))
        seen = {}

        def produce(args):
            seen.update(validate=os.environ.get("SCENE_VALIDATE"),
                        preflight=os.environ.get("SCENE_PREFLIGHT"), args=args)
            return video

        with patch.dict(os.environ, {"SCENE_VALIDATE": "", "SCENE_PREFLIGHT": ""}), \
                patch("engine.make_film.produce", side_effect=produce), patch.object(ap, "_backup"):
            out, flagged = ap.stage_render(self.run, self.film)
        self.assertEqual((out, flagged), (video, False))
        self.assertEqual((seen["validate"], seen["preflight"]), ("1", "1"))

    def test_a_new_explainer_is_a_storyboard_the_kit_films_like_max(self):
        from agents import kit_planner, kit_world
        storyboard = dict(copy.deepcopy(sbm.LEVEE), steps=copy.deepcopy(sbm.LEVEE["steps"][1:]), hero=False)
        plan = {"title": "How a levee keeps a river out", "set_id": "kit_how_a_levee_explainer",
                "storyboard": storyboard, "hook_action": "burrow_hook"}
        written = []

        def write(angle=None, set_id=None, topic_hint=None, on_topic=None, render=False, preview=False):
            written.append(set_id)
            return self.film

        with patch.dict(os.environ, {"SHOWRUNNER_AUTO_BUILD_SETS": "1", "SHOWRUNNER_SET_MODE": ""}), \
                patch.object(explainer, "choose_set", return_value=None), \
                patch.object(explainer, "plan_new_set", side_effect=AssertionError("agent brief")), \
                patch.object(kit_world, "ensure_world", return_value="embankment") as world, \
                patch.object(kit_planner, "plan_kit_explainer", return_value=plan) as planned, \
                patch.object(sb, "build_explainer_set", side_effect=AssertionError("agent builder")), \
                patch.object(sb, "build_kit_set", return_value={"accepted": True, "set": plan["set_id"],
                                                                "work": self.tmp}) as filmed, \
                patch.object(explainer, "write", write):
            self.assertEqual(ap.stage_script(self.run, "explainer", "how levees work", None), self.film)
        self.assertEqual(world.call_args.args[0], "how levees work")       # the world exists before the plan
        self.assertEqual(planned.call_args.args[1], "how levees work")
        self.assertEqual(planned.call_args.kwargs["world"], "embankment")
        filmed.assert_called_once()
        self.assertEqual(written, ["kit_how_a_levee_explainer"])
        self.assertEqual(self.run["generated_set"], "kit_how_a_levee_explainer")

    def test_agent_mode_builds_a_new_explainer_set_when_none_fits(self):
        plan = {"subject": "Septic tank", "set_id": "septic_tank_explainer", "build_brief": "A cutaway yard.",
                "hook_action": "overflow_hook"}
        accepted = {"accepted": True, "set": "septic_tank_explainer", "work": self.tmp}
        written = []

        def write(angle=None, set_id=None, topic_hint=None, on_topic=None, render=False, preview=False):
            written.append((set_id, topic_hint))
            return self.film

        with patch.dict(os.environ, {"SET_BUILD_ROUNDS": "4", "SHOWRUNNER_AUTO_BUILD_SETS": "1",
                                     "SHOWRUNNER_SET_MODE": "agent"}), \
                patch.object(explainer, "choose_set", return_value=None), \
                patch.object(explainer, "plan_new_set", return_value=plan), \
                patch.object(explainer, "write", write), \
                patch.object(sb, "build_explainer_set", return_value=accepted) as build:
            path = ap.stage_script(self.run, "explainer", "how a septic tank works", None)
        self.assertEqual(path, self.film)
        build.assert_called_once_with("A cutaway yard.", "septic_tank_explainer", rounds=4,
                                      hook_action="overflow_hook")
        self.assertEqual(written, [("septic_tank_explainer", plan)])
        self.assertEqual(self.run["generated_set"], "septic_tank_explainer")

    def test_resume_after_build_does_not_build_again(self):
        plan = {"subject": "Septic tank", "set_id": "septic_tank_explainer", "build_brief": "b"}
        self.run.set(new_set_plan=plan, generated_set="septic_tank_explainer")
        with patch.object(explainer, "write", return_value=self.film) as write, \
                patch.object(sb, "build_explainer_set", side_effect=AssertionError("rebuilt")):
            self.assertEqual(ap.stage_script(self.run, "explainer", None, None), self.film)
        self.assertEqual(write.call_args.args[1], "septic_tank_explainer")

    def test_auto_build_off_stops_cleanly(self):
        with patch.dict(os.environ, {"SHOWRUNNER_AUTO_BUILD_SETS": "0"}), \
                patch.object(explainer, "choose_set", return_value=None):
            with self.assertRaises(ap.GiveUp):
                ap.stage_script(self.run, "explainer", "septic tanks", None)

    def test_used_named_set_stops_instead_of_building(self):
        with patch.object(explainer, "unused_sets", return_value=[]), \
                patch.object(explainer, "usage", return_value={"pool": 1}):
            with self.assertRaisesRegex(ap.GiveUp, "already carried"):
                ap.stage_script(self.run, "explainer", None, "pool")


class SetBuilderTests(unittest.TestCase):
    def test_design_prompt_is_hero_free_and_names_the_hook(self):
        prompt = sb.explainer_design_prompt("A septic tank in a cut-open yard", "septic_tank_explainer",
                                            "overflow_hook")
        self.assertIn('FORMAT =\n"explainer"', prompt)
        self.assertIn("`overflow_hook`", prompt)
        self.assertIn("must NOT define HERO", prompt)

    def test_explainer_identity_is_checked(self):
        errs = sb.static_checks("pool", explainer=True)        # the hand-built pool predates FORMAT
        self.assertTrue(any("FORMAT" in e for e in errs), errs)

    def test_hook_check(self):
        self.assertEqual(sb._hook_check("pool", "dig"), [])
        self.assertTrue(sb._hook_check("pool", "float_hook"))

    def test_register_adds_to_the_explainer_list_only(self):
        tmp = tempfile.mkdtemp()
        init = os.path.join(tmp, "engine", "sets", "__init__.py")
        os.makedirs(os.path.dirname(init))
        src = os.path.join(os.path.dirname(__file__), "..", "engine", "sets", "__init__.py")
        open(init, "w", encoding="utf-8").write(open(src, encoding="utf-8").read())
        with patch.object(sb, "PROJECT_ROOT", tmp):
            sb.register("septic_tank_explainer", "EXPLAINER")
        text = open(init, encoding="utf-8").read()
        self.assertIn('EXPLAINER = ["pool", "septic_tank_explainer"]', text)
        self.assertEqual(text.count("septic_tank_explainer"), 1)

    def test_explainer_preview_renders_with_the_cutaway_runner(self):
        import types
        work = tempfile.mkdtemp()
        fake = types.SimpleNamespace(FORMAT="explainer", ACTIONS={"x": {"kind": "build"}})
        calls = []
        with patch.dict(os.environ, {}, clear=True), \
                patch.dict(sys.modules, {"engine.sets.septic_tank_explainer_spec": fake}), \
                patch.object(sb, "_film_file", return_value=os.path.join(
                    os.path.dirname(__file__), "..", "engine", "films", "pool_cut.json")), \
                patch("engine.make_film._run_blender", lambda cmd, *a, **k: calls.append((cmd, k.get("env")))), \
                patch.object(sb, "_complete_preview", return_value=False):
            sb.preview_render("septic_tank_explainer", work)
            self.assertNotIn("CUT_PCT", os.environ)       # preview quality never leaks into production
        self.assertTrue(calls and calls[0][0][4].endswith("cutaway_film.py"), calls)
        self.assertEqual(calls[0][1]["CUT_PCT"], "50")

    def test_measuring_is_on_for_explainers(self):
        import types
        fake = types.SimpleNamespace(FORMAT="explainer")
        work = tempfile.mkdtemp()
        open(os.path.join(work, "timings.json"), "w").write('{"beats": []}')
        with patch.dict(sys.modules, {"engine.sets.septic_tank_explainer_spec": fake}), \
                patch.dict(os.environ, {"SET_BUILD_QA": "1"}), \
                patch("engine.make_film._run_blender", side_effect=RuntimeError("no blender")) as blender:
            self.assertEqual(sb.qa_check("septic_tank_explainer", work), {})
        blender.assert_called_once()


if __name__ == "__main__":
    unittest.main()
