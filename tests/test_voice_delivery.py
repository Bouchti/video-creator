"""Expressive local narration: per-sentence delivery and the misspoken-sentence check (agents/voice.py)."""
import unittest
from unittest.mock import patch

from agents import voice


class DeliveryPlanTests(unittest.TestCase):
    SCRIPT = ("Their tanks were full of air. Its recruits came from art schools. Painters. Sculptors. Designers. "
              "They hid them badly. On purpose. If discovered, they faced grave danger. "
              "Eleven hundred men, posing as whole divisions. Would you have spotted the fake tanks?")

    def test_each_kind_of_line_is_said_its_own_way(self):
        plan = dict(voice.delivery_plan(self.SCRIPT))
        hook = plan["Their tanks were full of air."]
        plain = plan["Its recruits came from art schools. Painters. Sculptors. Designers."]
        dramatic = plan["If discovered, they faced grave danger."]
        question = plan["Would you have spotted the fake tanks?"]
        self.assertGreater(hook["exaggeration"], 0.6)
        self.assertGreater(dramatic["exaggeration"], 0.6)
        self.assertLess(dramatic["cfg_weight"], 0.5)                    # slower and heavier
        self.assertGreaterEqual(question["pause_after"], 0.3)        # short on purpose (RETENTION_FIXES_2026-11-01)
        self.assertGreaterEqual(plan["Eleven hundred men, posing as whole divisions."]["pause_after"], 0.35)
        self.assertGreater(plain["exaggeration"], 0.6)                  # the fragments punch the line they join

    def test_short_fragments_are_never_spoken_alone(self):
        """Chatterbox said "Painters." as "Hainters" and "Sculptors." as "Helpeders"."""
        sentences = [sentence for sentence, _ in voice.delivery_plan(self.SCRIPT)]
        self.assertIn("They hid them badly. On purpose.", sentences)
        self.assertTrue(all(len(sentence.split()) > 3 or sentence.endswith("?") for sentence in sentences))
        self.assertEqual(self.SCRIPT, " ".join(sentences))              # nothing lost or reordered


class MisspokenTests(unittest.TestCase):
    def _heard(self, sentence, heard):
        words = [{"text": word, "start": 0, "end": 0} for word in heard.split()]
        with patch("agents.transcription.transcribe_with_whisper", return_value=words):
            return voice._misspoken(sentence, "part.wav")

    def test_an_invented_or_garbled_word_is_caught(self):
        self.assertTrue(self._heard("If discovered, they faced grave danger.",
                                    "Shell, if discovered, they faced grave danger."))
        self.assertTrue(self._heard("Others came from advertising agencies. Painters. Sculptors.",
                                    "Others came from advertising agencies. Hainters. Helpeders."))

    def test_numbers_and_split_compounds_are_not_errors(self):
        self.assertFalse(self._heard("About eleven hundred men.", "About 1 ,100 men."))
        self.assertFalse(self._heard("Fake laundry hung on camp clotheslines.",
                                     "Fake laundry hung on camp clothes lines."))
        self.assertFalse(self._heard("More than twenty deception campaigns in one year.",
                                     "More than 20 deception campaigns in one year."))

    def test_missing_words_are_caught(self):
        self.assertTrue(self._heard("Radio operators sent fake messages to the enemy.", "Radio operators."))


if __name__ == "__main__":
    unittest.main()
