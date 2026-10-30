import json
import os
import tempfile
import unittest
from unittest import mock

from agents import sfx_library as lib


def _catalog(rows):
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "catalog.json"), "w", encoding="utf-8") as fh:
        json.dump({"sounds": rows}, fh)
    return d


ROWS = [
    {"path": "sonniss/a/DOORWood_Door Slam Heavy 01.wav", "words": ["door", "doorwood", "heavy", "slam", "wood"],
     "folder": ["doors"], "seconds": 1.4},
    {"path": "sonniss/a/DOORWood_Door Creak Open Slow Long Squeaky Hinge.wav",
     "words": ["creak", "door", "doorwood", "hinge", "long", "open", "slow", "squeaky"], "folder": ["doors"],
     "seconds": 6.0},
    {"path": "sonniss/b/AMBRain_Rain On Roof Loop.wav", "words": ["ambrain", "loop", "rain", "roof"],
     "folder": ["weather"], "seconds": 60.0},
    {"path": "sonniss/b/CROWDKids_Children Cheering Yay.wav", "words": ["cheering", "children", "crowdkids", "yay"],
     "folder": ["crowds"], "seconds": 3.0},
]


class FindTest(unittest.TestCase):
    def setUp(self):
        lib._index = None
        self.patch = mock.patch.object(lib, "CC0_SFX", _catalog(ROWS))
        self.patch.start()
        self.env = mock.patch.dict(os.environ, {"SFX_ONLINE": "0", "SFX_GENERATE": "0"})
        self.env.start()

    def tearDown(self):
        self.patch.stop()
        self.env.stop()
        lib._index = None

    def test_every_query_word_must_match(self):
        self.assertTrue(lib.find("door_slam").endswith("Door Slam Heavy 01.wav"))
        self.assertIsNone(lib.find("glass_shatter"))

    def test_plural_and_case_insensitive(self):
        self.assertTrue(lib.find("Doors creak").endswith("Squeaky Hinge.wav"))

    def test_loops_detected_from_words(self):
        self.assertTrue(lib.find("rain").endswith("Rain On Roof Loop.wav"))
        self.assertTrue(lib.is_loop("rain on roof"))
        self.assertFalse(lib.is_loop("door slam"))

    def test_generated_sound_wins_over_library(self):
        self.assertEqual(lib._source("splash"), lib.path("splash") if os.path.exists(lib.path("splash"))
                         else lib.find("splash"))

    def test_category_prefix_is_confident(self):
        path, confident = lib._local(lib._words("door"), None)
        self.assertTrue(confident)
        _path, weak = lib._local(lib._words("roof"), None)
        self.assertFalse(weak)

    def test_missing_catalog_is_not_fatal(self):
        lib._index = None
        with mock.patch.object(lib, "CC0_SFX", tempfile.mkdtemp()):
            self.assertIsNone(lib.find("door slam"))


if __name__ == "__main__":
    unittest.main()
