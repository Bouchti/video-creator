import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents import evaluator
from agents.transcription import words_to_srt
from agents.publisher import publish_video


class EditorHelperTests(unittest.TestCase):
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
    def test_local_ai_documentary_uses_object_led_review(self):
        with patch("agents.ai_router.ask", return_value={"verdict": "PASS", "issues": []}) as ask:
            evaluator.evaluate_script({"spoken_script": "A sample enters the chamber.",
                                       "content_mode": "documentary"}, source="local-ai")
        self.assertIs(ask.call_args.args[0], evaluator.LOCAL_AI_DOCUMENTARY_EVALUATOR_PROMPT)

    def test_evaluate_script_accepts_structured_verdict(self):
        with patch("agents.ai_router.ask", return_value={"verdict": "PASS"}) as ask:
            result = evaluator.evaluate_script({"spoken_script": "test"})

        self.assertEqual("PASS", result["verdict"])
        self.assertEqual(evaluator.VERDICT_TOOL["input_schema"], ask.call_args.args[2])

    def test_all_issues_become_one_revision_brief(self):
        issues = [{"beat": 1, "severity": "blocking", "fix": "Correct the year to 1943."},
                  {"beat": 20, "severity": "minor", "fix": "Add service medals to the veterans."}]
        with patch("agents.ai_router.ask", return_value={"verdict": "FAIL", "issues": issues}):
            result = evaluator.evaluate_script({"spoken_script": "test"})
        self.assertIn("Beat 1 [blocking]", result["feedback"])
        self.assertIn("Beat 20 [minor]", result["feedback"])
        self.assertFalse(result["minor_only"])

    def test_minor_issues_only_never_cost_a_rewrite(self):
        script = {key: "value" for key in evaluator.REQUIRED_KEYS}
        script["spoken_script"] = " ".join(["word"] * 180)
        script["beats"] = [
            {"text": "scene one", "visual": {"kind": "footage", "description": "one", "queries": ["a"]}},
            {"text": "scene two", "visual": {"kind": "footage", "description": "two", "queries": ["b"]}},
        ]
        minor = {"verdict": "FAIL", "feedback": "polish", "minor_only": True, "issues": []}
        blocking = dict(minor, minor_only=False)
        with patch("agents.script.generate_script", return_value=script), \
                patch.object(evaluator, "evaluate_script", side_effect=[blocking, minor]):
            self.assertIs(script, evaluator.evaluate_with_retry("topic", max_retries=2))
        with patch("agents.script.generate_script", return_value=script) as generate, \
                patch.object(evaluator, "evaluate_script", side_effect=[minor, blocking]):
            self.assertIs(script, evaluator.evaluate_with_retry("topic", max_retries=2))
        self.assertEqual(1, generate.call_count)
        with patch("agents.script.generate_script", return_value=script), \
                patch.object(evaluator, "evaluate_script", side_effect=[blocking, blocking]):
            self.assertIsNone(evaluator.evaluate_with_retry("topic", max_retries=2))

    def test_local_ai_tolerates_small_length_overage(self):
        self.assertIsNone(evaluator.length_feedback(151, 100, 150, 10, grace=evaluator.LOCAL_AI_LENGTH_GRACE))
        self.assertIn("Cut at least 20", evaluator.length_feedback(170, 100, 150, 10))

    def test_evaluate_script_rejects_unknown_verdict(self):
        with patch("agents.ai_router.ask", return_value={"verdict": "MAYBE"}):
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
    def test_publisher_prepares_without_external_side_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "video.mp4"
            video.write_bytes(b"video")
            result = publish_video(video, "youtube", {"title": "Test"})
            self.assertEqual(result["status"], "prepared")
            self.assertTrue(Path(result["package_path"]).is_file())
            self.assertTrue(result["metadata"]["ai_generated"])


if __name__ == "__main__":
    unittest.main()
