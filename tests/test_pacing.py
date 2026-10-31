"""Pacing of the cutaway films: every action gets its minimum seconds on screen, and the Chatterbox voice keeps
the beat pauses (the tunnel film ran ~35 % faster than designed: actions in half their time, no pauses)."""
import importlib.util
import os
import unittest

from agents.beats import action_holds, align_beats, shift_words

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _spoken(lines, step=0.3, gap=0.5):
    """Beats and Whisper-style words: one word every `step` s, `gap` s of silence between beats."""
    beats, words, t = [], [], 0.0
    for action, n in lines:
        beats.append({"action": action, "text": " ".join(f"{action}{i}" for i in range(n))})
        for i in range(n):
            words.append({"text": f"{action}{i}", "start": t, "end": t + step - 0.05})
            t += step
        t += gap
    return beats, words, t - gap


MIN = {"hook": 3.0, "fix": 6.0, "fail": 5.0, "end": 4.0}


def min_seconds(beat):
    return MIN[beat["action"]]


class ActionHoldTests(unittest.TestCase):
    def test_a_short_line_gets_silence_until_its_action_has_its_minimum_time(self):
        beats, words, voice = _spoken([("hook", 12), ("fix", 12), ("fail", 20), ("end", 3)])
        holds = action_holds(beats, words, voice, 2.5, min_seconds)
        self.assertEqual([round(p, 1) for _, p in holds], [1.9, 0.5])     # fix: 4.1 s -> 6 s; end: 3.5 s -> 4 s
        at = holds[0][0]
        self.assertTrue(words[23]["end"] < at < words[24]["start"])       # inside the pause after the fix's line
        self.assertEqual(holds[1][0], round(voice, 3))                   # the last beat extends the voice's end
        shifted = shift_words(words, holds)
        slots = align_beats(beats, shifted, voice + sum(p for _, p in holds) + 2.5)
        for beat, slot in zip(beats, slots):
            self.assertGreaterEqual(slot["end"] - slot["start"] + 0.05, min_seconds(beat), beat["action"])
        self.assertEqual(shifted[23]["start"], words[23]["start"])        # words before the hold do not move
        self.assertAlmostEqual(shifted[24]["start"], words[24]["start"] + holds[0][1])

    def test_a_hold_is_capped_so_it_never_reads_as_dead_air(self):
        beats, words, voice = _spoken([("hook", 12), ("fix", 2), ("end", 15)])
        (_, pad), = action_holds(beats, words, voice, 2.5, min_seconds)
        self.assertEqual(pad, 3.0)

    def test_a_voice_that_already_holds_needs_nothing_more(self):
        beats, words, voice = _spoken([("hook", 12), ("fix", 8), ("fail", 20), ("end", 6)])
        holds = action_holds(beats, words, voice, 2.5, min_seconds)
        again = action_holds(beats, shift_words(words, holds), voice + sum(p for _, p in holds), 2.5, min_seconds)
        self.assertEqual(again, [])                       # a re-run on the held voice keeps the same timings


class SplitWordAlignmentTests(unittest.TestCase):
    def test_a_word_whisper_splits_still_starts_its_beat_on_time(self):
        # Whisper heard "Bulk heads" for "bulkheads": the beat's start was interpolated into the pause before it
        beats = [{"text": "the next anchor just bounces."}, {"text": "bulkheads out, lights on."}]
        words = [{"text": t, "start": s, "end": s + 0.25} for t, s in
                 [("the", 0.0), ("next", 0.3), ("anchor", 0.6), ("just", 0.9), ("bounces.", 1.2),
                  ("Bulk", 4.5), ("heads", 4.8), ("out,", 5.1), ("lights", 5.4), ("on.", 5.7)]]
        slots = align_beats(beats, words, 7.0)
        self.assertAlmostEqual(slots[1]["start"], 4.4, places=1)


def _speak():
    spec = importlib.util.spec_from_file_location("speak", os.path.join(ROOT, "tools", "chatterbox", "speak.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)                          # (torch and chatterbox load only in main())
    return mod


class ChatterboxPauseTests(unittest.TestCase):
    def test_beat_breaks_become_silences_instead_of_being_dropped(self):
        text = ('Max dug a tunnel. It flooded at once. <break time="0.55s" /> So he tried a trench instead, '
                'with a dredger. <break time="0.55s" /> Done.')
        plan = _speak().plan(text, 0.3)
        self.assertEqual(plan, [("Max dug a tunnel.", 0.3), ("It flooded at once.", 0.55),
                                ("So he tried a trench instead, with a dredger.", 0.55), ("Done.", 0.3)])

    def test_sentences_within_a_beat_keep_the_short_pause(self):
        plan = _speak().plan("Max called it bulletproof. Physics disagreed loudly.", 0.3)
        self.assertEqual([p for _, p in plan], [0.3, 0.3])


if __name__ == "__main__":
    unittest.main()
