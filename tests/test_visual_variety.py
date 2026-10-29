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


class SceneVarietyTest(unittest.TestCase):
    """The 2026-10-27 El Nino video: 14 of 22 shots on one shore, chained off each other's frames."""

    def _labels(self, scenes):
        return [(s, "storm") for s in scenes]

    def test_one_place_cannot_hold_most_of_the_film(self):
        texts = [f"Wide shot: grey surf {i}" if i % 2 else f"Close-up: wet planks {i}" for i in range(12)]
        script = _script(texts)
        for i, beat in enumerate(script["beats"]):
            beat["visual"]["scene"] = "shore" if i < 8 else f"place {i}"
        feedback = variety_feedback(script) or ""
        self.assertIn("'shore' is the scene of 8 of 12 shots", feedback)
        self.assertIn("in a row in 'shore'", feedback)

    def test_a_take_is_at_most_three_shots_and_a_frame_seeds_one_shot(self):
        from local_video.planner import MAX_TAKE, _take_length, continuation_source
        labels = self._labels(["shore"] * 10)
        sources = [continuation_source(labels, i) for i in range(10)]
        self.assertLessEqual(max(_take_length(labels, i) for i in range(10)), MAX_TAKE)
        used = [s for s in sources if s is not None]
        self.assertEqual(len(used), len(set(used)))          # no frame opens two shots

    def test_a_place_palette_never_reaches_another_place(self):
        from local_video.planner import _continuity
        script = {"location": "Beach shore: pale timber homes on sand. Desert city: low buildings and palms in rain.",
                  "color_palette": "slate sea, pale timber homes, wet charcoal",
                  "beats": [{"text": "a", "visual": {"scene": "Beach shore", "light": "storm"}},
                            {"text": "b", "visual": {"scene": "Desert city", "light": "storm"}}]}
        self.assertIn("timber homes", _continuity(script, "", "c", 0)["palette"])
        self.assertNotIn("timber homes", _continuity(script, "", "c", 1)["palette"])
