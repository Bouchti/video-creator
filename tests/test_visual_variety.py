"""The shot list must keep changing: the 2026-10-27 volcano video was one cone in 21 of 22 shots."""

import unittest
from unittest.mock import patch

from agents.evaluator import evaluate_with_retry, variety_feedback


def _script(descriptions):
    return {"beats": [{"text": "w", "visual": {"description": text}} for text in descriptions]}


MONOTONE = [f"Wide shot: the cone of Anak Krakatau rises from the sea, view {i}." for i in range(12)]
VARIED = [
    "Wide shot: the cone of Anak Krakatau rises from the sea.",
    "Close-up: steam curls from a crack in black rock.",
    "Medium shot: a small boat rides the swell, anonymous crew in the distance.",
    "Extreme close-up: seawater runs off matte black stone.",
    "Wide shot: an illustrative radar dish antenna at a ground station under grey cloud.",
    "Medium shot: the lava apron of Anak Krakatau meets the surf.",
    "Close-up: grey ash settles on a wet boat deck.",
    "Wide shot: an airliner parked on an apron under a hazy sky.",
    "Close-up: rain beads on dark glass.",
    "Medium shot: surf runs up a new black beach.",
    "Wide shot: the reshaped Anak Krakatau from a boat at sea.",
    "Close-up: pumice floats on a slate-grey swell.",
]


class VarietyFeedbackTests(unittest.TestCase):
    def test_the_volcano_style_shot_list_is_sent_back(self):
        feedback = variety_feedback(_script(MONOTONE))
        self.assertIn("Krakatau is in 12 of 12 shots", feedback)
        self.assertIn("0 of 12 shots are close-ups", feedback)
        self.assertIn("12 Wide shots in a row", feedback.replace("wide", "Wide"))

    def test_a_varied_shot_list_passes(self):
        self.assertIsNone(variety_feedback(_script(VARIED)))

    def test_unsized_descriptions_are_named(self):
        feedback = variety_feedback(_script([text.split(": ", 1)[1] for text in VARIED]))
        self.assertIn("do not start with their shot size", feedback)

    def test_a_sentence_initial_capital_is_not_a_subject(self):
        script = _script([f"Close-up: The rock {i}." if i % 2 else f"Wide shot: The sea {i}." for i in range(12)])
        self.assertNotIn("The is in", variety_feedback(script) or "")

    def test_a_monotone_draft_is_revised_before_the_paid_evaluation(self):
        drafts = iter([_script(MONOTONE), _script(VARIED)])
        judged = []
        with patch("agents.script.generate_script", side_effect=lambda *a, **k: dict(
                next(drafts), video_title="t", description="d", spoken_script="w " * 130)), \
                patch("agents.evaluator.has_all_keys", return_value=(True, [])), \
                patch("agents.evaluator.length_feedback", return_value=None), \
                patch("agents.evaluator.evaluate_script",
                      side_effect=lambda script, **k: judged.append(script) or {"verdict": "PASS"}):
            result = evaluate_with_retry("topic", max_retries=5, mode="local-ai")
        self.assertEqual(len(judged), 1)                  # the monotone draft never reached it
        self.assertIn("Close-up", result["beats"][1]["visual"]["description"])

    def test_the_last_attempt_is_accepted_with_a_warning_rather_than_dropping_the_topic(self):
        with patch("agents.script.generate_script", return_value=dict(
                _script(MONOTONE), video_title="t", description="d", spoken_script="w " * 130)), \
                patch("agents.evaluator.has_all_keys", return_value=(True, [])), \
                patch("agents.evaluator.length_feedback", return_value=None), \
                patch("agents.evaluator.evaluate_script", return_value={"verdict": "PASS"}):
            self.assertIsNotNone(evaluate_with_retry("topic", max_retries=2, mode="local-ai"))


if __name__ == "__main__":
    unittest.main()
