"""The cutaway look of --source evolution (local_video/looks.py): photoreal 3D cross-section renders like the
1hidden_by_design wastewater Shorts, carried from the script through every prompt and review. The photo look,
and every film made before looks existed, must stay exactly as it was."""

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from local_video import keyframes, looks, visual_review
from local_video.planner import REALISM_BAN, plan_shots
from local_video.project import create_project
from tests.test_local_video import make_test_config, sample_script


def cutaway_script():
    script = sample_script()
    script.update(look=looks.CUTAWAY, visual_style=looks.CUTAWAY_STYLE, characters=[])
    for beat in script["beats"]:
        beat["visual"]["description"] = ("Cutaway of the street: the road sliced open beside the kerb, a concrete "
                                         "gully chamber under the grate filling with rainwater")
    return script


class LookTests(unittest.TestCase):
    def test_anything_without_a_recorded_look_is_a_photo_film(self):
        self.assertEqual(looks.PHOTO, looks.look_of(None))
        self.assertEqual(looks.PHOTO, looks.look_of({}))
        self.assertEqual(looks.PHOTO, looks.look_of({"look": "watercolour"}))
        self.assertEqual(looks.CUTAWAY, looks.look_of({"look": "Cutaway"}))
        self.assertEqual(looks.CUTAWAY, looks.look_of(SimpleNamespace(continuity={"look": "cutaway"})))
        self.assertEqual(looks.CUTAWAY, looks.look_of(SimpleNamespace(continuity=None, script={"look": "cutaway"})))

    def test_evolution_films_in_the_cutaway_look_unless_told_photo(self):
        with patch.dict(os.environ, {"EVOLUTION_LOOK": ""}):
            self.assertEqual(looks.CUTAWAY, looks.evolution_look())
        with patch.dict(os.environ, {"EVOLUTION_LOOK": "photo"}):
            self.assertEqual(looks.PHOTO, looks.evolution_look())
        with patch.dict(os.environ, {"EVOLUTION_LOOK": "nonsense"}):
            self.assertEqual(looks.CUTAWAY, looks.evolution_look())


class PromptTests(unittest.TestCase):
    def test_cutaway_clips_lead_with_the_fixed_style_and_never_ask_for_live_action(self):
        shots, continuity = plan_shots(cutaway_script(), "street drains", 60, looks.CUTAWAY_STYLE, "minimax")
        self.assertEqual(looks.CUTAWAY, continuity["look"])
        for shot in shots:
            self.assertEqual(looks.CUTAWAY, shot.continuity["look"])
            self.assertIn(looks.CUTAWAY_STYLE, shot.prompt)
            self.assertEqual(1, shot.prompt.count(looks.CUTAWAY_STYLE[:60]))   # not repeated as the scene style
            self.assertNotIn("Live-action", shot.prompt)
            self.assertNotIn("Photorealistic:", shot.prompt)
            self.assertIn(f"Render: {looks.CUTAWAY_RENDER}", shot.prompt)
            self.assertIn("No people anywhere", shot.prompt)
            self.assertIn(looks.CUTAWAY_LIGHT, shot.prompt)
            self.assertIn(looks.CUTAWAY_WIDE, shot.prompt)            # looking down at the cut, not eye level
            self.assertNotIn("eye level", shot.prompt)
            # The photo look's ban on "CGI, 3D render" would ban this look itself.
            self.assertIn(looks.CUTAWAY_BAN, shot.negative_prompt)
            self.assertNotIn("3D render", shot.negative_prompt)

    def test_a_close_up_goes_into_the_cut(self):
        script = cutaway_script()
        script["beats"][1]["visual"]["description"] = "Close-up inside the cut: the flap valve swinging shut"
        shots, _ = plan_shots(script, "street drains", 60, looks.CUTAWAY_STYLE, "minimax")
        self.assertIn(looks.CUTAWAY_CLOSE, shots[1].prompt)
        self.assertIn(looks.CUTAWAY_CLOSE, keyframes.keyframe_prompt(shots[1]))
        self.assertIn(looks.CUTAWAY_WIDE, shots[0].prompt)

    def test_photo_films_are_unchanged(self):
        shots, continuity = plan_shots(sample_script(), "desert city", 60, "35mm nocturne", "minimax")
        self.assertEqual(looks.PHOTO, continuity["look"])
        self.assertTrue(all("Live-action, 35mm nocturne" in shot.prompt for shot in shots))
        self.assertTrue(all("Photorealistic:" in shot.prompt for shot in shots))
        self.assertTrue(all(REALISM_BAN in shot.negative_prompt for shot in shots))
        self.assertFalse(any(looks.CUTAWAY_STYLE[:40] in shot.prompt for shot in shots))

    def test_cutaway_keyframes_are_renders_drawn_from_the_same_style_text(self):
        shots, _ = plan_shots(cutaway_script(), "street drains", 60, looks.CUTAWAY_STYLE, "minimax")
        prompt = keyframes.keyframe_prompt(shots[0])
        self.assertTrue(prompt.startswith(f"Photoreal 3D cutaway cross-section render, {looks.CUTAWAY_WIDE}"))
        self.assertNotIn("eye level", prompt)
        self.assertIn(f"Style: {looks.CUTAWAY_STYLE}", prompt)
        self.assertNotIn("Photograph", prompt)
        self.assertNotIn("realistic skin", prompt)
        self.assertEqual(1, prompt.count(looks.CUTAWAY_STYLE[:60]))
        photo, _ = plan_shots(sample_script(), "desert city", 60, "35mm nocturne", "minimax")
        self.assertTrue(keyframes.keyframe_prompt(photo[0]).startswith("Photograph"))

    def test_a_render_is_no_flaw_in_a_cutaway_still_but_melting_still_is(self):
        cutaway = SimpleNamespace(continuity={"look": "cutaway"})
        photo = SimpleNamespace(continuity={})
        self.assertFalse(keyframes._weird("the render shows the chamber slightly small", cutaway))
        self.assertTrue(keyframes._weird("the render shows the chamber slightly small", photo))
        self.assertTrue(keyframes._weird("the pipe melts into the wall", cutaway))
        self.assertTrue(keyframes._weird("readable text on the grate", cutaway))


class ReviewTests(unittest.TestCase):
    def _keyframe_prompt(self, script):
        shots, _ = plan_shots(script, "street drains", 60, script.get("visual_style") or "35mm", "minimax")
        answer = {"composition_match": 8, "realism": 8, "anatomy": 9, "fatal_problems": [], "problems": [],
                  "correction": ""}
        seen = {}
        with tempfile.TemporaryDirectory() as folder:
            still = Path(folder) / "k.png"
            from PIL import Image
            Image.new("RGB", (36, 64), "white").save(still)
            with patch.object(visual_review, "review_enabled", return_value=True), \
                    patch.object(visual_review.llm, "ask",
                                 side_effect=lambda system, prompt, schema, **k: seen.update(p=prompt) or answer):
                visual_review.review_keyframe(still, shots[0])
        return seen["p"]

    def test_the_keyframe_reviewer_is_told_the_cut_is_wanted(self):
        with patch.dict(os.environ, {"LOCAL_VIDEO_FAST": "1"}):
            prompt = self._keyframe_prompt(cutaway_script())
            self.assertTrue(prompt.startswith(looks.CUTAWAY_REVIEW_NOTE))
            self.assertIn("a crisp photoreal 3D cutaway render", prompt)
            self.assertNotIn("CGI look", prompt)
            self.assertIn("a cartoon, flat or toy-like look", prompt)
            photo = self._keyframe_prompt(sample_script())
            self.assertNotIn(looks.CUTAWAY_REVIEW_NOTE, photo)
            self.assertIn("reads as a real photograph", photo)
            self.assertIn("an illustrated, painterly or CGI look", photo)

    def test_the_clip_reviewer_judges_a_render_not_camera_footage(self):
        import cv2
        import numpy as np
        answer = {"visual_match": 8, "continuity": 8, "image_quality": 8, "anatomy": 9, "immersion": 8,
                  "story_progression": 8, "fatal_problems": [], "problems": [], "revision_prompt": ""}
        prompts = {}
        for name, script in (("cutaway", cutaway_script()), ("photo", sample_script())):
            with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"LOCAL_VIDEO_FAST": "1"}):
                clip = Path(folder) / "c.mp4"
                writer = cv2.VideoWriter(str(clip), cv2.VideoWriter_fourcc(*"mp4v"), 30, (36, 64))
                for _ in range(10):
                    writer.write(np.zeros((64, 36, 3), dtype=np.uint8))
                writer.release()
                project = create_project("drains", 60, script.get("visual_style") or "35mm", "auto",
                                         narration_enabled=False, config=make_test_config(folder), script=script)
                with patch.object(visual_review, "review_enabled", return_value=True), \
                        patch.object(visual_review.llm, "ask",
                                     side_effect=lambda system, prompt, schema, **k: prompts.update({name: prompt})
                                     or answer):
                    visual_review.review_clip(clip, project.shots[3], None, project)
        self.assertTrue(prompts["cutaway"].startswith(looks.CUTAWAY_REVIEW_NOTE))
        self.assertIn(looks.CUTAWAY_CLIP_LOOK, prompts["cutaway"])
        self.assertNotIn("must look like real camera footage", prompts["cutaway"])
        self.assertIn(visual_review.FAST_CLIP_RULE_CUTAWAY, prompts["cutaway"])
        self.assertIn("must look like real camera footage", prompts["photo"])
        self.assertIn(visual_review.FAST_CLIP_RULE, prompts["photo"])

    def test_fast_rules_for_a_cutaway_keep_everything_but_the_look(self):
        self.assertNotIn("CGI", visual_review.FAST_CLIP_RULE_CUTAWAY)
        self.assertNotIn("CGI", visual_review.FAST_KEYFRAME_RULE_CUTAWAY)
        self.assertEqual(len(visual_review.FAST_CLIP_RULE.split("fatal")),
                         len(visual_review.FAST_CLIP_RULE_CUTAWAY.split("fatal")))


class ScriptTests(unittest.TestCase):
    def test_an_evolution_script_is_written_and_recorded_in_the_cutaway_look(self):
        from agents import script as writer
        draft = {"video_title": "Drains", "beats": [{"text": "So you dig a drain.",
                                                     "visual": {"kind": "scene", "description": "Cutaway"}}]}
        with patch.dict(os.environ, {"EVOLUTION_LOOK": "cutaway"}), \
                patch.object(writer.llm, "ask", return_value=dict(draft)) as ask:
            script = writer.generate_script("drains", target_seconds=65, mode="local-ai", content_mode="evolution")
        self.assertIn(writer.BEATS_LOCAL_AI_CUTAWAY, ask.call_args.args[0])
        self.assertIn("photoreal 3D cutaway render", ask.call_args.args[1])
        self.assertEqual(looks.CUTAWAY, script["look"])
        self.assertEqual(looks.CUTAWAY_STYLE, script["visual_style"])
        with patch.dict(os.environ, {"EVOLUTION_LOOK": "photo"}), \
                patch.object(writer.llm, "ask", return_value=dict(draft)) as ask:
            script = writer.generate_script("drains", target_seconds=65, mode="local-ai", content_mode="evolution")
        self.assertNotIn("CUTAWAY LOOK", ask.call_args.args[0])
        self.assertNotIn("look", script)

    def test_a_documentary_never_gets_the_cutaway_look(self):
        from agents import script as writer
        with patch.dict(os.environ, {"EVOLUTION_LOOK": "cutaway"}):
            self.assertNotIn("CUTAWAY LOOK", writer.system_prompt("local-ai", "documentary"))
            self.assertIn("CUTAWAY LOOK", writer.system_prompt("local-ai", "evolution"))

    def test_the_evaluator_accepts_underground_views_in_a_cutaway_film(self):
        from agents import evaluator
        verdict = {"verdict": "PASS", "issues": [], "summary": "ok"}
        with patch.object(evaluator.llm, "ask", return_value=verdict) as ask:
            evaluator.evaluate_script({"content_mode": "evolution", "look": "cutaway", "spoken_script": "a b"},
                                      source="local-ai")
        self.assertIn(evaluator.CUTAWAY_EVALUATOR_NOTE, ask.call_args.args[0])
        with patch.object(evaluator.llm, "ask", return_value=verdict) as ask:
            evaluator.evaluate_script({"content_mode": "evolution", "spoken_script": "a b"}, source="local-ai")
        self.assertNotIn(evaluator.CUTAWAY_EVALUATOR_NOTE, ask.call_args.args[0])


class TopicTests(unittest.TestCase):
    def test_cutaway_topics_are_searched_among_hidden_systems(self):
        from agents import leader
        with patch.dict(os.environ, {"EVOLUTION_LOOK": "cutaway"}):
            queries = leader._evolution_queries()
        self.assertEqual(6, len(queries))
        self.assertTrue(set(queries) <= set(leader.CUTAWAY_EVOLUTION_QUERIES))
        with patch.dict(os.environ, {"EVOLUTION_LOOK": "photo"}):
            self.assertTrue(set(leader._evolution_queries()) <= set(leader.EVOLUTION_QUERIES))


if __name__ == "__main__":
    unittest.main()
