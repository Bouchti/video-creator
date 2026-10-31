import json
import os
import tempfile
import unittest
from unittest import mock

from agents import autopilot, blenderkit, set_builder

BK_SET = '''from engine import studio as st, props as bk
class World:
    def build(self):
        self.car = bk.prop("family car", 4.2, fallback=lambda: self.build_car())
        self.ship = bk.prop( "Cargo  Ship" , 60)
        self.again = bk.prop("family car", 4.2)
        self.other = self._prop(pid, want)
'''
OLD_SET = 'from engine import studio as st\ncar = prop("family car", 4.2)\n'


class CodePropsTest(unittest.TestCase):
    def test_literal_calls_of_a_blenderkit_set_are_read_once(self):
        self.assertEqual(blenderkit.code_props(BK_SET), [("family car", 4.2), ("Cargo  Ship", 60.0)])

    def test_sets_that_build_everything_are_left_alone(self):
        self.assertEqual(blenderkit.code_props(OLD_SET), [])


class ResolveSetPropsTest(unittest.TestCase):
    def test_found_and_missing_props_are_recorded_and_never_fatal(self):
        root = tempfile.mkdtemp()
        set_path = os.path.join(root, "x_story.py")
        with open(set_path, "w", encoding="utf-8") as fh:
            fh.write(BK_SET)
        model = os.path.join(root, "assets", "car.blend")
        os.makedirs(os.path.dirname(model))
        open(model, "w").close()

        def fake_resolve(query, kind, size, story):
            return {"path": model, "name": "Family Car"} if "car" in query else None
        manifest = os.path.join(root, "props_manifest.json")
        with mock.patch.object(blenderkit, "PROPS_MANIFEST", manifest), \
                mock.patch.object(blenderkit, "OUT", root), \
                mock.patch.object(blenderkit, "PROJECT_ROOT", root), \
                mock.patch.object(blenderkit, "resolve", side_effect=fake_resolve) as res:
            self.assertEqual(blenderkit.resolve_set_props(set_path), 1)
            data = json.load(open(manifest, encoding="utf-8"))
            self.assertEqual(data["family car"]["path"], os.path.join("assets", "car.blend"))
            self.assertIsNone(data["cargo ship"])
            blenderkit.resolve_set_props(set_path)          # a found prop is not resolved twice
            self.assertEqual([c.args[0] for c in res.call_args_list].count("family car"), 1)

    def test_an_old_set_triggers_nothing(self):
        root = tempfile.mkdtemp()
        set_path = os.path.join(root, "old_story.py")
        with open(set_path, "w", encoding="utf-8") as fh:
            fh.write(OLD_SET)
        with mock.patch.object(blenderkit, "resolve") as res:
            self.assertEqual(blenderkit.resolve_set_props(set_path), 0)
        res.assert_not_called()


class OptInTest(unittest.TestCase):
    def test_only_the_bk_route_asks_for_blenderkit_props(self):
        with mock.patch.object(set_builder, "build_set", return_value={}) as b:
            set_builder.build_story_set("a tunnel", "t_story")
            set_builder.build_story_set("a tunnel", "t_story", assets=True)
        self.assertEqual([c.kwargs["assets"] for c in b.call_args_list], [False, True])

    def test_repairs_of_a_blenderkit_set_keep_its_rules(self):
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, "engine", "sets"))
        for name, code in (("bk_story", BK_SET), ("old_story", OLD_SET)):
            with open(os.path.join(root, "engine", "sets", f"{name}.py"), "w", encoding="utf-8") as fh:
                fh.write(code)
        with mock.patch.object(set_builder, "PROJECT_ROOT", root):
            self.assertIn("BLENDERKIT PROPS", set_builder._bk_rules("bk_story"))
            self.assertEqual(set_builder._bk_rules("old_story"), "")

    def test_the_bk_route_films_only_blenderkit_sets(self):
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, "engine", "sets"))
        for name, code in (("plane_story", OLD_SET), ("ship_story", BK_SET)):
            with open(os.path.join(root, "engine", "sets", f"{name}.py"), "w", encoding="utf-8") as fh:
                fh.write(code)
        with mock.patch.object(autopilot, "PROJECT_ROOT", root), \
                mock.patch("agents.showrunner.available_topic_sets", return_value=["plane_story", "ship_story"]):
            self.assertEqual(autopilot._unused_bk_set(), "ship_story")
        with mock.patch.object(autopilot, "PROJECT_ROOT", root), \
                mock.patch("agents.showrunner.available_topic_sets", return_value=["plane_story"]):
            self.assertIsNone(autopilot._unused_bk_set())


if __name__ == "__main__":
    unittest.main()
