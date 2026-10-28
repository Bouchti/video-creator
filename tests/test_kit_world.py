"""New kit worlds and the prepare stage: a world is designed as data, its objects are built and tested one by
one, its staging is verified, and only then is it registered; every kit video is measured before it renders.
All AI and Blender work is mocked."""
import copy
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

from agents import kit_planner, kit_world, set_builder as sb, storyboard as sbm
from engine.kit import vocab, worlds

WORLD = "septic_tank_test"


def design():
    o = lambda name, x, y, z: {"name": f"{WORLD}_{name}", "what": name, "look": f"a real {name}",   # noqa: E731
                               "size_m": {"x": x, "y": y, "z": z}}
    return {
        "world": WORLD, "fits": "septic tanks, drain fields", "thing": "system", "news": "septic rules",
        "description": "A cut-open yard: house left, Max's tank middle, drain field right.",
        "description_no_hero": "A cut-open yard: house left, the tank middle, drain field right.",
        "objects": [o("ground", 14, 6, 3), o("house", 4, 4, 3), o("pipe", 3, 0.2, 0.2), o("tank", 2.5, 1.4, 1.6),
                    o("baffle", 0.1, 1.2, 1.0), o("field", 6, 3, 0.6), o("arrows", 2, 0.1, 0.5)],
        "changes": [
            {"id": "bucket_tank", "does": "Max buries a big bucket", "built": "a big bucket sinks into the ground",
             "adds": [], "first": True},
            {"id": "concrete_tank", "does": "Max sets a concrete tank", "built": "a concrete tank drops in",
             "adds": ["tank"], "first": False},
            {"id": "add_baffle", "does": "Max adds a baffle", "built": "a baffle slides in", "adds": ["baffle"],
             "first": False},
            {"id": "drain_field", "does": "Max lays a drain field", "built": "perforated pipes spread out",
             "adds": ["field"], "first": False}],
        "events": [
            {"id": "calm", "outcome": "hold", "shows": "a sunny yard", "teaches": "", "needs": [],
             "must_see": [f"{WORLD}_house"]},
            {"id": "bucket_cracks", "outcome": "fail", "shows": "the bucket cracks", "teaches": "soil pushes in",
             "needs": [], "must_see": [f"{WORLD}_tank"]},
            {"id": "tank_holds", "outcome": "hold", "shows": "the tank holds", "teaches": "concrete resists soil",
             "needs": ["tank"], "must_see": [f"{WORLD}_tank"]},
            {"id": "solids_escape", "outcome": "fail", "shows": "solids flow out", "teaches": "nothing settles",
             "needs": ["tank"], "must_see": [f"{WORLD}_pipe", f"{WORLD}_arrows"]},
            {"id": "solids_settle", "outcome": "hold", "shows": "solids settle", "teaches": "the baffle slows flow",
             "needs": ["baffle"], "must_see": [f"{WORLD}_baffle"]},
            {"id": "yard_floods", "outcome": "fail", "shows": "water pools", "teaches": "the soil cannot absorb",
             "needs": ["tank"], "must_see": [f"{WORLD}_ground"]},
            {"id": "field_drains", "outcome": "hold", "shows": "water soaks away", "teaches": "spread it out",
             "needs": ["field"], "must_see": [f"{WORLD}_field"]},
            {"id": "all_works", "outcome": "hold", "shows": "everything works", "teaches": "together",
             "needs": [], "must_see": [f"{WORLD}_house"]}],
        "calm_event": "calm", "finale_event": "all_works", "first_build": "bucket_tank",
        "reference_storyboard": {
            "title": "Max's Septic Tank", "subject": "a septic tank cut open", "model_facts": [
                {"name": "size", "fact": "a 1,000 gallon tank"}],
            "steps": [
                {"id": "promise", "kind": "setup", "change": "none", "event": "calm", "weather": "sunny", "label": ""},
                {"id": "fail_bucket", "kind": "fail", "change": "bucket_tank", "event": "bucket_cracks",
                 "weather": "sunny", "label": "BUCKET"},
                {"id": "fix_tank", "kind": "fix", "change": "concrete_tank", "event": "tank_holds", "weather": "sunny",
                 "label": "CONCRETE"},
                {"id": "fail_solids", "kind": "fail", "change": "none", "event": "solids_escape", "weather": "rain",
                 "label": "SOLIDS"},
                {"id": "fix_baffle", "kind": "fix", "change": "add_baffle", "event": "solids_settle",
                 "weather": "rain", "label": "BAFFLE"},
                {"id": "finale", "kind": "finale", "change": "none", "event": "all_works", "weather": "sunny",
                 "label": ""}],
            "hooks": [{"id": "solids_hook", "step": "fail_solids"}]},
    }


class _WorldFiles(unittest.TestCase):
    def tearDown(self):
        for name in (f"{WORLD}_vocab.py", f"{WORLD}_objects.py", f"{WORLD}.py"):
            path = os.path.join(kit_world.WORLDS_DIR, name)
            if os.path.exists(path):
                os.remove(path)
        sys.modules.pop(f"engine.kit.worlds.{WORLD}_vocab", None)
        while WORLD in worlds.REGISTERED:
            worlds.REGISTERED.remove(WORLD)


class DesignTests(_WorldFiles):
    def test_a_good_design_is_buildable(self):
        self.assertEqual(kit_world.validate_design(design()), [])

    def test_broken_designs_are_refused_with_every_reason(self):
        d = design()
        d["world"] = "embankment"
        d["events"][1]["must_see"] = ["a_tank_from_nowhere"]
        d["events"][2]["needs"] = ["magic"]
        d["changes"][1]["first"] = True
        problems = " | ".join(kit_world.validate_design(d))
        for needle in ("must be new", "must_see names objects", "which no change adds", "exactly one change"):
            self.assertIn(needle, problems)

    def test_the_reference_storyboard_is_checked_inside_the_design_so_a_correction_can_fix_it(self):
        d = design()                                     # what the 2026-10-28 septic run returned
        steps = d["reference_storyboard"]["steps"]
        for k, s in enumerate(steps):
            s["id"] = f"s{k + 1}"
        d["reference_storyboard"]["hooks"] = [{"id": "h1", "step": "s4"}]
        steps[1]["change"] = "none"                      # the first fail builds nothing
        d["events"][0]["needs"] = ["tank"]               # the calm opening needs a tank
        problems = " | ".join(kit_world.validate_design(d))
        self.assertIn("its needs must be []", problems)
        d["events"][0]["needs"] = []
        problems = " | ".join(kit_world.validate_design(d))
        self.assertIn("reference_storyboard: ids must be snake_case 3-31 characters", problems)
        self.assertIn("needs the system built first (bucket_tank)", problems)
        self.assertNotIn(WORLD, worlds.REGISTERED)
        self.assertNotIn(f"engine.kit.worlds.{WORLD}_vocab", sys.modules)

    def test_a_design_that_broke_the_rules_is_not_resumed(self):
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, "output", "worlds", WORLD))
        broken = dict(design(), topic="septic tanks")
        broken["reference_storyboard"]["steps"][0]["id"] = "s1"
        json.dump(broken, open(os.path.join(root, "output", "worlds", WORLD, "design.json"), "w"))
        with patch.object(kit_world, "PROJECT_ROOT", root):
            self.assertIsNone(kit_world._unfinished_design("septic tanks"))
            json.dump(dict(design(), topic="septic tanks"),
                      open(os.path.join(root, "output", "worlds", WORLD, "design.json"), "w"))
            self.assertEqual(kit_world._unfinished_design("septic tanks")["world"], WORLD)

    def test_the_vocabulary_lets_the_storyboard_pipeline_film_the_new_world(self):
        self.assertEqual(kit_world.write_vocab(design()), [])
        self.assertNotIn(WORLD, worlds.REGISTERED)               # written, but not a world yet
        worlds.REGISTERED.append(WORLD)
        v = vocab.for_world(WORLD)
        self.assertEqual(v.WORLD_CLASS, (f"engine.kit.worlds.{WORLD}", "SepticTankTestWorld"))
        ref = v.REFERENCE_STORYBOARD
        self.assertEqual(sbm.validate(ref), [])
        root = tempfile.mkdtemp()
        for folder in ("engine/sets", "engine/films"):
            os.makedirs(os.path.join(root, folder))
        set_id = sbm.compile_set(dict(ref, hero=False), "kitw_test_explainer", root=root)
        builder = open(os.path.join(root, "engine", "sets", f"{set_id}.py"), encoding="utf-8").read()
        self.assertIn(f"from engine.kit.worlds.{WORLD} import SepticTankTestWorld", builder)
        self.assertIn("a big bucket sinks into the ground", kit_planner.vocabulary(False, WORLD))
        self.assertEqual(kit_planner.plan_schema(WORLD)["properties"]["storyboard"]["properties"]["world"]["enum"],
                         [WORLD])

    def test_a_storyboard_in_an_unknown_world_is_refused(self):
        self.assertTrue(any("world must be one of" in p for p in sbm.validate(dict(sbm.LEVEE, world="moon"))))


class BuildWorldTests(_WorldFiles):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.p = [patch.object(kit_world, "PROJECT_ROOT", self.tmp), patch.object(kit_world, "register_world")]
        for x in self.p:
            x.start()

    def tearDown(self):
        for x in self.p:
            x.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def _agent(self, written):
        def agent(prompt, allowed, **kwargs):
            written.append((allowed[0], prompt))
            for rel in allowed:
                path = os.path.join(self.tmp, rel)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                open(path, "a").close()
            return "done"
        return agent

    def test_objects_are_tested_one_by_one_before_any_staging_is_written(self):
        written, order = [], []
        results = [{f"{WORLD}_tank": ["size: z is 4.00 m, the design says 1.60 m"]}, {}]

        def objects(d, work):
            order.append("objects")
            return results.pop(0)

        def staging(world):
            order.append("staging")
            return ""

        with patch.object(sb, "claude_agent", self._agent(written)), \
                patch.object(kit_world, "check_objects", objects), patch.object(kit_world, "check_staging", staging):
            status = kit_world.build_world("how a septic tank works", design=design())
        self.assertTrue(status["accepted"])
        self.assertEqual(order, ["objects", "objects", "staging"])
        files = [f for f, _ in written]
        self.assertEqual(files, [f"engine/kit/worlds/{WORLD}_objects.py", f"engine/kit/worlds/{WORLD}_objects.py",
                                 f"engine/kit/worlds/{WORLD}.py"])
        repair = written[1][1]
        self.assertIn("Fix ONLY these objects", repair)
        self.assertIn(f"{WORLD}_tank", repair)
        self.assertNotIn(f"- {WORLD}_house:", repair)            # a passing object is not sent back
        kit_world.register_world.assert_called_once_with(WORLD)

    def test_a_world_whose_objects_never_pass_is_not_staged_or_registered(self):
        with patch.dict(os.environ, {"KIT_WORLD_ROUNDS": "2"}), \
                patch.object(sb, "claude_agent", self._agent([])), \
                patch.object(kit_world, "check_objects", return_value={f"{WORLD}_tank": ["flat"]}), \
                patch.object(kit_world, "check_staging", side_effect=AssertionError("staged")):
            status = kit_world.build_world("septic tanks", design=design())
        self.assertEqual((status["accepted"], status["stage"]), (False, "objects"))
        kit_world.register_world.assert_not_called()
        self.assertNotIn(WORLD, worlds.REGISTERED)

    def test_ensure_world_reuses_a_world_that_fits(self):
        with patch.object(kit_world, "world_for", return_value="embankment"), \
                patch.object(kit_world, "build_world", side_effect=AssertionError("rebuilt")):
            self.assertEqual(kit_world.ensure_world("how levees fail"), "embankment")

    def test_ensure_world_builds_one_when_none_fits_and_can_be_switched_off(self):
        with patch.object(kit_world, "world_for", return_value=None), \
                patch.object(kit_world, "build_world", return_value={"accepted": True, "world": WORLD}):
            self.assertEqual(kit_world.ensure_world("septic tanks"), WORLD)
        with patch.dict(os.environ, {"SHOWRUNNER_AUTO_BUILD_WORLDS": "0"}), \
                patch.object(kit_world, "world_for", return_value=None):
            with self.assertRaises(kit_world.WorldNotBuilt):
                kit_world.ensure_world("septic tanks")


class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.mkdtemp()
        self.film = os.path.join(self.work, "film.json")
        json.dump({"set": "kit_max_s_backyard_levee_story", "beats": []}, open(self.film, "w"))
        self.timings = os.path.join(self.work, "timings.json")
        json.dump({"beats": [{"start": 0, "end": 89}, {"start": 90, "end": 179}]}, open(self.timings, "w"))

    def _blender(self, rep):
        calls = []

        def run(cmd, watcher=None, env=None):
            calls.append(cmd)
            json.dump(rep, open(os.path.join(cmd[-2], "qa.json"), "w"))
        return run, calls

    def test_every_object_is_measured_with_this_films_timings_before_rendering(self):
        run, calls = self._blender({"beats": {}, "quality": {}})
        with patch("engine.make_film._run_blender", run):
            sb.prepare_kit_film(self.film, self.timings, self.work)
            sb.prepare_kit_film(self.film, self.timings, self.work)      # unchanged: reused, not rebuilt
        self.assertEqual(len(calls), 1)
        self.assertIn("--qa", calls[0])
        self.assertIn(self.timings, calls[0])

    def test_a_missing_object_stops_the_video_before_any_frame(self):
        run, _ = self._blender({"beats": {}, "quality": {"02_fail_sand": [
            {"issue": "must_see: kb_flow is not on screen at the beat's middle", "frames": [120, 120]}]}})
        with patch("engine.make_film._run_blender", run):
            with self.assertRaisesRegex(sb.KitDefect, "kb_flow"):
                sb.prepare_kit_film(self.film, self.timings, self.work)


if __name__ == "__main__":
    unittest.main()
