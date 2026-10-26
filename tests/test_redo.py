import os
import tempfile
import unittest
from unittest import mock

from engine.make_film import _parse_redo, _ranges, _restore_redo_frames

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

    def test_cleaned_cache_is_restored_from_video_without_overwriting_targets(self):
        with tempfile.TemporaryDirectory() as folder:
            frames = os.path.join(folder, "frames")
            os.makedirs(frames)
            video = os.path.join(folder, "video.mp4")
            open(video, "wb").close()
            target = os.path.join(frames, "f_0002.png")
            with open(target, "wb") as fh:
                fh.write(b"new target")

            def fake_extract(command, check):
                pattern = command[-1]
                for f in range(1, 5):
                    with open(pattern.replace("%04d", f"{f:04d}"), "wb") as fh:
                        fh.write(f"old {f}".encode())

            with mock.patch("engine.make_film.subprocess.run", side_effect=fake_extract) as run:
                restored = _restore_redo_frames(video, frames, 4, targets=[2])

            self.assertEqual(restored, 3)
            with open(target, "rb") as fh:
                self.assertEqual(fh.read(), b"new target")
            with open(os.path.join(frames, "f_0004.png"), "rb") as fh:
                self.assertEqual(fh.read(), b"old 4")
            self.assertIn("-fps_mode", run.call_args.args[0])

    def test_restore_is_skipped_when_cache_is_complete(self):
        with tempfile.TemporaryDirectory() as folder:
            frames = os.path.join(folder, "frames")
            os.makedirs(frames)
            for f in (1, 3):
                open(os.path.join(frames, f"f_{f:04d}.png"), "wb").close()
            with mock.patch("engine.make_film.subprocess.run") as run:
                restored = _restore_redo_frames(os.path.join(folder, "video.mp4"), frames, 3, targets=[2])
            self.assertEqual(restored, 0)
            run.assert_not_called()
