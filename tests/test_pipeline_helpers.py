import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents import evaluator
from agents.editor_hailuo import (
    generate_all_clips,
    stitch_clips_to_duration,
    words_to_srt,
)
from agents.publisher import publish_video


class EditorHelperTests(unittest.TestCase):
    def test_hailuo_rejects_more_scenes_than_script_defines(self):
        with self.assertRaisesRegex(ValueError, "exactly 6 scenes"):
            generate_all_clips({}, num_clips=7)

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
    def test_evaluate_script_accepts_fenced_json(self):
        response = type(
            "Response",
            (),
            {"content": [type("Block", (), {"text": '```json\n{"verdict":"PASS","feedback":null}\n```'})()]},
        )()
        with patch.object(evaluator.client.messages, "create", return_value=response):
            result = evaluator.evaluate_script({"spoken_script": "test"})

        self.assertEqual("PASS", result["verdict"])

    def test_evaluate_script_rejects_unknown_verdict(self):
        response = type(
            "Response",
            (),
            {"content": [type("Block", (), {"text": '{"verdict":"MAYBE","feedback":null}'})()]},
        )()
        with patch.object(evaluator.client.messages, "create", return_value=response):
            with self.assertRaisesRegex(ValueError, "PASS or FAIL"):
                evaluator.evaluate_script({"spoken_script": "test"})

    def test_evaluator_failure_consumes_retry(self):
        script = {key: "value" for key in evaluator.REQUIRED_KEYS}
        script["spoken_script"] = "one two three"
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
