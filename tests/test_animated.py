import os
import tempfile
import unittest
import wave

import numpy as np

from agents.audio_fx import SR, build_fx_track
from agents.beats import repair_beats, validate_beats
from agents.captions import chunk_words, words_to_ass


def _scene(text, **visual):
    return {"text": text, "visual": {"kind": "scene", "description": f"Max {text}",
                                     "camera": "push_in", **visual}}


class SceneSchemaTests(unittest.TestCase):
    def test_scene_beats_validate_with_and_without_overlay(self):
        beats = [_scene("digs a hole"),
                 _scene("goes two meters down", overlay={"type": "stat", "value": "2 m", "text": "deep"})]
        self.assertEqual([], validate_beats(beats))

    def test_bad_overlay_is_reported(self):
        beats = [_scene("a b"), _scene("c d", overlay={"type": "stat"})]
        self.assertIn("beat 2", validate_beats(beats)[0])

    def test_scene_mode_repair_forces_scene_and_fixes_overlays(self):
        beats = [
            {"text": "a b", "visual": {"kind": "footage", "description": "x", "overlay": {"type": "number", "value": "5"}}},
            {"text": "c d", "visual": {"kind": "image", "description": "y", "overlay": {"type": "sparkles"}}},
        ]
        repair_beats(beats, scene_mode=True)
        self.assertEqual(["scene", "scene"], [b["visual"]["kind"] for b in beats])
        self.assertEqual("stat", beats[0]["visual"]["overlay"]["type"])
        self.assertNotIn("overlay", beats[1]["visual"])


class CaptionTests(unittest.TestCase):
    @staticmethod
    def _words(text):
        return [{"text": w, "start": i * 0.4, "end": i * 0.4 + 0.3} for i, w in enumerate(text.split())]

    def test_chunks_are_short_and_break_on_punctuation(self):
        chunks = chunk_words(self._words("Then the earth itself is torn open. Wow, really big!"))
        texts = [" ".join(w["text"] for w in c) for c in chunks]
        self.assertEqual("open.", texts[2].split()[-1])
        self.assertTrue(all(len(c) <= 3 for c in chunks))
        self.assertIn("Wow,", texts)

    def test_ass_highlights_one_word_per_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = words_to_ass(self._words("dig the {hole}"), os.path.join(tmp, "c.ass"))
            with open(path, encoding="utf-8") as f:
                content = f.read()
        events = [l for l in content.splitlines() if l.startswith("Dialogue:")]
        self.assertEqual(3, len(events))
        self.assertTrue(all(e.count("\\c&H0000E6FF") == 1 for e in events))
        self.assertIn("HOLE", events[2])          # braces stripped, uppercased
        self.assertIn("\\t(0,90", events[0])     # phrase pops in on its first word


class FxTests(unittest.TestCase):
    def test_fx_track_has_sound_at_cuts_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = build_fx_track(3.0, cut_times=[1.5], pop_times=[], path=os.path.join(tmp, "fx.wav"))
            with wave.open(path) as w:
                data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        self.assertGreater(np.abs(data[int(1.4 * SR):int(1.6 * SR)]).max(), 1000)
        self.assertEqual(0, np.abs(data[: int(1.0 * SR)]).max())


if __name__ == "__main__":
    unittest.main()
