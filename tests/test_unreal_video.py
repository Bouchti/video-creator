"""Unreal route: deterministic planning and command orchestration without launching UE."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from unreal_video.config import UnrealConfig
from unreal_video.planner import build_recipe, validate_recipe
from unreal_video.project import create_project
from unreal_video.runner import UnrealPipeline, build_render_command, build_setup_command


ROOT = Path(__file__).resolve().parents[1]


def _script():
    return {
        "video_title": "How a Water Tower Works",
        "description": "A continuous engineering story.",
        "spoken_script": "Water goes up. Gravity sends it back down.",
        "visual_style": "stylized engineering diorama",
        "beats": [
            {"text": "Water goes up.", "visual": {"kind": "scene", "camera": "push_in",
                                                      "description": "A pump fills a tall water tower."}},
            {"text": "Gravity sends it back down.",
             "visual": {"kind": "scene", "camera": "orbit",
                        "description": "Cutaway pipes carry water from the tower to a house."}},
        ],
    }


class RecipeTests(unittest.TestCase):
    def test_recipe_is_exact_silent_vertical_timeline(self):
        recipe = build_recipe(_script(), 30)
        self.assertEqual(recipe["render"], {
            "width": 1080, "height": 1920, "fps": 30, "total_frames": 900,
            "audio": False, "captions": False, "transition_sounds": False,
        })
        self.assertEqual(recipe["shots"][0]["start_frame"], 0)
        self.assertEqual(recipe["shots"][-1]["end_frame"], 900)
        self.assertEqual(recipe["shots"][0]["camera"], "dolly_in")
        self.assertEqual(recipe["shots"][0]["archetype"], "water")

    def test_the_film_stays_in_one_set_and_acts_out_its_beats(self):
        texts = ["This lake is a battery.", "Cheap power pumps water uphill.",
                 "At peak demand it falls through the turbine.", "Power flows to the grid.", "Two lakes, one battery."]
        script = {"video_title": "Pumped hydro", "beats": [
            {"text": t, "visual": {"description": "a road with a truck" if k == 3 else t}} for k, t in enumerate(texts)]}
        recipe = build_recipe(script, 30)
        self.assertEqual({s["archetype"] for s in recipe["shots"]}, {"water"})   # one place, not a road cut-in
        self.assertEqual([s["action"] for s in recipe["shots"]],
                         ["finale", "pump_up", "release_down", "power_out", "finale"])   # cold open first
        recipe["shots"][1]["action"] = "traffic"                            # not something the water set can do
        with self.assertRaisesRegex(ValueError, "Unsupported Unreal action"):
            validate_recipe(recipe)

    def test_ai_plans_the_actions_and_keywords_stand_in_without_a_backend(self):
        from unreal_video.runner import plan_actions
        recipe = build_recipe(_script(), 30)
        with patch("unreal_video.runner.ai_router.ask", return_value={"actions": ["pump_up", "store"]}):
            plan_actions(recipe, _script())
        self.assertEqual([s["action"] for s in recipe["shots"]], ["pump_up", "finale"])   # the last is the payoff
        recipe = build_recipe(_script(), 30)
        with patch("unreal_video.runner.ai_router.ask", side_effect=RuntimeError("no backend")):
            plan_actions(recipe, _script())
        self.assertEqual([s["action"] for s in recipe["shots"]], ["finale", "finale"])   # cold open, payoff

    def test_every_set_offered_to_the_writer_is_built_by_unreal(self):
        import re
        from unreal_video.planner import SET_SHOWS
        engine = (ROOT / "unreal" / "VideoCreatorUE" / "Content" / "Python" / "build_sequence.py").read_text("utf-8")
        built = set(re.findall(r'"([a-z]+)": set_[a-z]+', engine))
        self.assertEqual(set(SET_SHOWS) - built, set())
        self.assertEqual(build_recipe({"video_title": "How a rocket launch works", "beats": [
            {"text": "Fuel flows in."}, {"text": "It lifts off."}]}, 30)["world"]["archetype"], "space")

    def test_recipe_rejects_embedded_audio_or_captions(self):
        recipe = build_recipe(_script(), 30)
        recipe["render"]["audio"] = True
        with self.assertRaisesRegex(ValueError, "silent visuals"):
            validate_recipe(recipe)


class ProjectAndCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.editor = self.temp / "UnrealEditor-Cmd.exe"
        self.editor.write_bytes(b"")
        self.config = UnrealConfig(
            editor=self.editor,
            project=ROOT / "unreal" / "VideoCreatorUE" / "VideoCreatorUE.uproject",
            output_root=self.temp / "projects",
            setup_script=ROOT / "unreal" / "VideoCreatorUE" / "Content" / "Python" / "build_sequence.py",
        )

    def test_project_is_resumable_and_records_audio_policy(self):
        manifest = create_project(_script(), 30, "mysterious", "none", True, True, self.config)
        self.assertTrue((Path(manifest.project_dir) / "project.json").is_file())
        self.assertTrue((Path(manifest.project_dir) / "recipe.json").is_file())
        self.assertIn("silent", manifest.settings["visual_audio_policy"])
        self.assertEqual(manifest.preferred_backend, "unreal")

    def test_commands_use_editor_python_then_mrq(self):
        setup = build_setup_command(self.config)
        self.assertTrue(any(value.startswith("-ExecutePythonScript=") for value in setup))
        self.assertIn("-NoSound", setup)
        render = build_render_command(self.config, {
            "map": "/Game/Generated/X/VC_Level",
            "sequence": "/Game/Generated/X/VC_Sequence.VC_Sequence",
            "config": "/Game/Generated/X/VC_RenderPreset.VC_RenderPreset",
        })
        self.assertIn("-game", render)
        self.assertTrue(any(value.startswith("-LevelSequence=") for value in render))
        self.assertTrue(any(value.startswith("-MoviePipelineConfig=") for value in render))
        self.assertIn("-NoSound", render)

    def test_preflight_explains_missing_unreal_install(self):
        missing = UnrealConfig(editor=None, project=self.config.project, output_root=self.temp / "missing",
                               setup_script=self.config.setup_script, minimum_free_gb=0)
        manifest = create_project(_script(), 30, "mysterious", "none", False, False, missing)
        with patch.dict(os.environ, {"LOCAL_VIDEO_ALLOW_QC_SKIP": "1"}):
            with self.assertRaisesRegex(RuntimeError, "Unreal Engine 5 was not found"):
                UnrealPipeline(missing).preflight(manifest)

    def test_project_declares_required_plugins(self):
        data = json.loads(self.config.project.read_text(encoding="utf-8"))
        enabled = {item["Name"] for item in data["Plugins"] if item.get("Enabled")}
        self.assertTrue({"PythonScriptPlugin", "EditorScriptingUtilities", "MovieRenderPipeline", "PCG"}
                        .issubset(enabled))

    def test_main_fails_before_topic_calls_when_unreal_is_missing(self):
        import main
        missing = UnrealConfig(editor=None, project=self.config.project, output_root=self.temp / "early",
                               setup_script=self.config.setup_script)
        with patch("unreal_video.config.UnrealConfig", return_value=missing), \
                patch("agents.leader.find_todays_topic", side_effect=AssertionError("must not research")):
            result = main.run_pipeline(source="unreal")
        self.assertFalse(result["success"])
        self.assertEqual(result["stage_failed"], "unreal_preflight")


if __name__ == "__main__":
    unittest.main()
