"""Retention fixes from the Nov 2026 Untold Footnotes audit: faster read, shorter films, no fragment runs,
no early dates, no self-debunked hook, grounded post text."""
import os
import unittest
from unittest.mock import patch

from agents.evaluator import pacing_feedback
from agents.post_text import _normalise, _template, unsupported_numbers
from agents.script import WORDS_PER_SECOND, plan_for_duration
from agents.voice import delivery_plan


class PacingFeedbackTests(unittest.TestCase):
    def test_fragment_runs_and_early_date_are_sent_back(self):
        script = {"spoken_script": "Their tanks were full of air. In January 1944, a secret unit formed. "
                                   "Painters. Sculptors. Designers. About eleven hundred men.",
                  "beats": [{"text": "Their tanks were full of air."},
                            {"text": "In January 1944, a secret unit formed."}, {"text": "a"}, {"text": "b"}]}
        problem = pacing_feedback(script)
        self.assertIn("fragment runs", problem)
        self.assertIn("date or era", problem)

    def test_hook_debunked_before_the_payoff_is_sent_back(self):
        script = {"beats": [{"text": "7,000 soldiers beat 32,000 and took home a bucket."},
                            {"text": "The bucket probably didn't start the war."},
                            {"text": "Modena captured a castle."}, {"text": "x"}, {"text": "y"}]}
        self.assertIn("hook is weakened", pacing_feedback(script))

    def test_connected_story_passes(self):
        script = {"beats": [{"text": "Greece invaded Bulgaria, and it started with a dog."},
                            {"text": "A soldier chased his dog across the border and Bulgarian guards shot him."},
                            {"text": "So Greece sent an army after him."},
                            {"text": "Would you have gone after the dog?"}]}
        self.assertIsNone(pacing_feedback(script))


class PaceAndLengthTests(unittest.TestCase):
    def test_word_budget_matches_the_faster_read(self):
        self.assertGreaterEqual(WORDS_PER_SECOND, 2.8)
        beats, low, high = plan_for_duration(40)
        self.assertLessEqual(high, 150)
        self.assertGreaterEqual(low, 95)

    def test_pauses_are_short(self):
        plan = delivery_plan("The emperor sent three ships down the river. A Dutch warship fired once. "
                             "The ball hit a soup kettle! Would you have surrendered?")
        self.assertTrue(all(d["pause_after"] <= 0.35 for _, d in plan))

    def test_pause_scale(self):
        with patch.dict(os.environ, {"PAUSE_SCALE": "0"}):
            plan = delivery_plan("The emperor sent three ships down the river. A Dutch warship fired once.")
        self.assertTrue(all(d["pause_after"] == 0 for _, d in plan))

    def test_default_duration_clears_tiktoks_minute_and_is_configurable(self):
        import main
        with patch.dict(os.environ, {"VIDEO_DURATION": ""}):
            self.assertGreater(main.default_duration(), 60)
        with patch.dict(os.environ, {"VIDEO_DURATION": "45"}):
            self.assertEqual(main.default_duration(), 45)


class PostTextTests(unittest.TestCase):
    def test_invented_number_is_flagged(self):
        film = _normalise({"video_title": "One cannon shot hit soup",
                           "beats": [{"text": "In 1784 a cannonball hit a soup kettle."}],
                           "research_sources": [{"title": "Kettle War",
                                                 "evidence": "The Republic paid 2 million guilder."}]})
        post = {"youtube_description": "The empire paid 8.5 million guilders in 1784."}
        self.assertEqual(unsupported_numbers(post, film), ["8.5"])

    def test_template_title_has_no_shorts_tag(self):
        film = _normalise({"video_title": "A bear joined the army", "beats": [{"text": "A bear joined."}]})
        self.assertNotIn("#shorts", _template(film)["youtube_title"])
        self.assertNotIn("#shorts", _template(film)["youtube_description"])


if __name__ == "__main__":
    unittest.main()
