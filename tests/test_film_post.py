import os
import unittest

from engine import hf_compose
from engine.make_film import _voice_engine, _voice_text

BEATS = [{"text": "One.", "chapter": None}, {"text": "Two.", "chapter": "a"}, {"text": "Three.", "chapter": "a"},
         {"text": "Four.", "chapter": "b"}]


class VoiceTextTests(unittest.TestCase):
    def test_chapter_pause_only_where_a_new_chapter_starts(self):
        text = _voice_text(BEATS, 0, 0.45)
        self.assertEqual(text, 'One. <break time="0.45s" /> Two. Three. <break time="0.45s" /> Four.')

    def test_beat_pause_without_chapters(self):
        self.assertEqual(_voice_text(BEATS[:2], 0.3), 'One. <break time="0.30s" /> Two.')

    def test_voice_engine_is_restored(self):
        old = os.environ.get("VOICE_ENGINE")
        with _voice_engine("chatterbox"):
            self.assertEqual(os.environ["VOICE_ENGINE"], "chatterbox")
        self.assertEqual(os.environ.get("VOICE_ENGINE"), old)


class ComposeTests(unittest.TestCase):
    def test_label_dropped_when_anchor_is_hidden(self):
        film = {"beats": [{"id": "dam", "callouts": [{"anchor": "dam", "text": "Dam", "at": 0.1}]}]}
        anchors = {str(f): {"dam": [500, 800, 0]} for f in range(1, 200)}
        _page, warnings = hf_compose.labels_scene(film, [(0.0, 5.0)], anchors, 5.0)
        self.assertTrue(any("hidden or off screen" in w for w in warnings))

    def test_label_follows_its_anchor(self):
        film = {"beats": [{"id": "dam", "callouts": [{"anchor": "dam", "text": "Dam", "at": 0.1}]}]}
        anchors = {str(f): {"dam": [400 + f, 800, 1]} for f in range(1, 200)}
        page, warnings = hf_compose.labels_scene(film, [(0.0, 5.0)], anchors, 5.0)
        self.assertEqual(warnings, [])
        self.assertIn("DAM", page)
        self.assertIn("Math.max(0,", page)

    def test_route_leaves_for_the_question(self):
        film = {"chapters": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
                "beats": [{"id": "x", "chapter": "a"}, {"id": "y", "chapter": "b"}, {"id": "q", "chapter": "b",
                                                                                     "question": "WHY?"}]}
        page = hf_compose.route_scene(film, [(0, 2), (2, 4), (4, 6)], 6.0)
        self.assertIn('tl.to("#route .rt-in", { opacity: 0', page)


if __name__ == "__main__":
    unittest.main()
