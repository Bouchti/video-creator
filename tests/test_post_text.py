import os
import tempfile
import unittest
from unittest import mock

from agents import post_text

FILM = {"title": "Max builds a boat", "cta": "Would you ride it?",
        "beats": [{"action": "sink_hook", "text": "Max's boat sank."}, {"action": "finale", "text": "It floats. Would you ride it?"}],
        "meta": {"caption": "Steel sinks, boats float.", "hashtags": ["#physics", "boats"]}}


class PostTextTests(unittest.TestCase):
    def test_fallback_writes_a_post_next_to_the_video(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(post_text, "_ask_claude", side_effect=RuntimeError("no claude")):
            out = post_text.write(FILM, os.path.join(d, "film.mp4"))
            self.assertTrue(out.endswith("film_post.txt"))
            text = open(out, encoding="utf-8").read()
        self.assertIn("===== TIKTOK =====", text)
        self.assertIn("===== YOUTUBE SHORTS =====", text)
        self.assertIn("Would you ride it?", text)
        self.assertIn("#boats", text)
        self.assertNotRegex(text.lower(), r"\b(subscribe|like and)\b")
