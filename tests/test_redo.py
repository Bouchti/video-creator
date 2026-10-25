import unittest

from engine.make_film import _parse_redo, _ranges

BEATS = [{"id": "sink_hook", "action": "sink_hook"}, {"id": "rewind", "action": "rewind"},
         {"id": "keel", "action": "keel"}, {"id": "a+b", "action": "rebar", "actions": ["rebar", "shotcrete"]}]
SPANS = [{"start": 0, "end": 59}, {"start": 60, "end": 89}, {"start": 90, "end": 149}, {"start": 150, "end": 239}]


class RedoTests(unittest.TestCase):
    def test_by_name_number_and_montage_action(self):
        self.assertEqual(_parse_redo("keel", {}, BEATS, SPANS), list(range(91, 151)))
        self.assertEqual(_parse_redo("3", {}, BEATS, SPANS), list(range(91, 151)))
        self.assertEqual(_parse_redo("shotcrete", {}, BEATS, SPANS), list(range(151, 241)))

    def test_by_seconds(self):
        self.assertEqual(_parse_redo("2-3s", {}, BEATS, SPANS), list(range(61, 92)))

    def test_unknown_beat(self):
        with self.assertRaises(SystemExit):
            _parse_redo("nope", {}, BEATS, SPANS)

    def test_ranges(self):
        self.assertEqual(_ranges([1, 2, 3, 7, 8, 10]), [(1, 3), (7, 8), (10, 10)])
