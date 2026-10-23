import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents import evaluator
from agents.editor_hailuo import (
    get_scenes,
    scene_prompt,
    stitch_clips_to_duration,
    words_to_srt,
)
from agents.publisher import publish_video


class EditorHelperTests(unittest.TestCase):
    def test_get_scenes_supports_list_and_legacy_schema(self):
        # New connected-scene schema: a scenes list.
        self.assertEqual(["a", "b", "c"], get_scenes({"scenes": ["a", "b", "c"]}))
        # Legacy fixed scene_1..N schema still works.
        self.assertEqual(["s1", "s2"], get_scenes({"scene_1": "s1", "scene_2": "s2"}))

    def test_scene_prompt_appends_shared_visual_style(self):
        script = {"scenes": ["a diver descends"], "visual_style": "35mm, teal grade"}
        self.assertEqual("a diver descends, 35mm, teal grade", scene_prompt(script, 0))

    def test_stitch_requires_at_least_one_clip(self):
        with self.assertRaisesRegex(ValueError, "At least one clip"):
            stitch_clips_to_duration([], target_duration=30)

    def test_words_to_srt_preserves_apostrophes(self):
        words = [
            {"text": "don't", "start": 0.0, "end": 0.4},
            {"text": "stop.", "start": 0.5, "end": 0.9},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "captions.srt"
            words_to_srt(words, str(output))
            content = output.read_text(encoding="utf-8")

        self.assertIn("DON'T", content)
        self.assertIn("STOP.", content)


class EvaluatorTests(unittest.TestCase):
    @staticmethod
    def _tool_response(verdict_input):
        block = type("Block", (), {"type": "tool_use", "name": "submit_verdict", "input": verdict_input})()
        return type("Response", (), {"content": [block]})()

    def test_evaluate_script_accepts_tool_verdict(self):
        response = self._tool_response({"verdict": "PASS"})
        with patch.object(evaluator.client.messages, "create", return_value=response):
            result = evaluator.evaluate_script({"spoken_script": "test"})

        self.assertEqual("PASS", result["verdict"])

    def test_evaluate_script_rejects_unknown_verdict(self):
        response = self._tool_response({"verdict": "MAYBE"})
        with patch.object(evaluator.client.messages, "create", return_value=response):
            with self.assertRaisesRegex(ValueError, "PASS or FAIL"):
                evaluator.evaluate_script({"spoken_script": "test"})

    def test_evaluator_failure_consumes_retry(self):
        script = {key: "value" for key in evaluator.REQUIRED_KEYS}
        script["spoken_script"] = " ".join(["word"] * 180)  # inside the 75s word range
        script["beats"] = [  # must be a valid beat list
            {"text": "scene one", "visual": {"kind": "footage", "description": "one", "queries": ["a"]}},
            {"text": "scene two", "visual": {"kind": "footage", "description": "two", "queries": ["b"]}},
        ]
        with (
            patch("agents.script.generate_script", return_value=script) as generate,
            patch.object(
                evaluator,
                "evaluate_script",
                side_effect=[ValueError("bad response"), {"verdict": "PASS", "feedback": None}],
            ),
        ):
            result = evaluator.evaluate_with_retry("topic", max_retries=2)

        self.assertIs(result, script)
        self.assertEqual(2, generate.call_count)


class PublisherTests(unittest.TestCase):
    def test_publisher_is_explicitly_unimplemented(self):
        with self.assertRaises(NotImplementedError):
            publish_video("video.mp4")


if __name__ == "__main__":
    unittest.main()
