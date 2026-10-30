import os
import tempfile
import unittest
from unittest.mock import patch

from agents import vision
from agents.beats import (
    FPS, align_beats, even_split, narration_from_beats, repair_beats, script_word_timings,
    split_frames, validate_beats,
)
from agents import evaluator
from agents.script import beat_word_range, plan_for_duration
from agents.diagram import TEMPLATES, render_frame, stat_text_at
from agents.photos import is_free_license, parse_imageinfo_pages


def _beat(text, kind="footage", **visual):
    v = {"kind": kind, "description": f"shot of {text}", **visual}
    if kind in ("footage", "photo"):
        v.setdefault("queries", ["query"])
    return {"text": text, "visual": v}


def _words(text, start=0.0, step=0.4):
    out = []
    for i, w in enumerate(text.split()):
        out.append({"text": w, "start": start + i * step, "end": start + i * step + 0.3})
    return out


class BeatSchemaTests(unittest.TestCase):
    def test_narration_is_beat_texts_joined(self):
        beats = [_beat(" One two. "), _beat("Three four.")]
        self.assertEqual("One two. Three four.", narration_from_beats(beats))

    def test_valid_beats_have_no_problems(self):
        beats = [
            _beat("Divers found it in 1901.", "photo", queries=["Antikythera mechanism"]),
            _beat("It has 37 gears.", "diagram", template="stat", value="37", label="gears"),
            _beat("Steps follow.", "diagram", template="process", steps=["a", "b"], active_step=1),
        ]
        self.assertEqual([], validate_beats(beats))

    def test_validation_names_the_broken_beat(self):
        beats = [_beat("Fine beat here."),
                 _beat("Broken diagram.", "diagram", template="timeline", events=[{"year": "1901"}])]
        problems = validate_beats(beats)
        self.assertEqual(1, len(problems))
        self.assertIn("beat 2", problems[0])

    def test_validation_rejects_footage_without_queries(self):
        beats = [_beat("Fine beat here."), _beat("No queries.", queries=[])]
        self.assertIn("beat 2", validate_beats(beats)[0])

    def test_repair_maps_kind_synonyms_and_infers_missing_kind(self):
        beats = [
            {"text": "a b", "visual": {"kind": "Stock", "description": "x", "queries": ["q"]}},
            {"text": "c d", "visual": {"kind": "chart", "description": "x", "template": "stat", "value": "5"}},
            {"text": "e f", "visual": {"description": "x", "queries": ["q"]}},
            {"text": "g h", "visual": {"kind": "diagram", "description": "x", "template": "map"}},
        ]
        repair_beats(beats)
        self.assertEqual(["footage", "diagram", "footage", "diagram"],
                         [b["visual"]["kind"] for b in beats])
        self.assertEqual("key_phrase", beats[3]["visual"]["template"])
        self.assertEqual([], validate_beats(beats))


class LengthTests(unittest.TestCase):
    def test_per_beat_budget_keeps_total_in_range(self):
        num, lo_total, hi_total = plan_for_duration(75)
        lo, hi = beat_word_range(num, lo_total, hi_total)
        self.assertLessEqual(num * lo, hi_total)
        self.assertGreaterEqual(num * hi, lo_total)
        self.assertLessEqual(hi, 10)  # ~3s of speech per beat, not 14 words

    def test_length_feedback_is_exact_and_graceful(self):
        msg = evaluator.length_feedback(272, 153, 206, 25)
        self.assertIn("272 words", msg)
        self.assertIn("Cut at least 66 words", msg)
        self.assertIsNone(evaluator.length_feedback(180, 153, 206, 25))
        self.assertIsNone(evaluator.length_feedback(241, 153, 206, 25, grace=0.2))
        self.assertIn("Add at least 53", evaluator.length_feedback(100, 153, 206, 25))

    def test_retry_revises_previous_draft(self):
        long_script = {k: "v" for k in evaluator.REQUIRED_KEYS}
        long_script["beats"] = [_beat("one two"), _beat("three four")]
        long_script["spoken_script"] = " ".join(["word"] * 300)
        good = dict(long_script, spoken_script=" ".join(["word"] * 180))
        with patch("agents.script.generate_script", side_effect=[long_script, good]) as gen,                 patch.object(evaluator, "evaluate_script", return_value={"verdict": "PASS"}):
            self.assertIs(good, evaluator.evaluate_with_retry("topic", max_retries=2))
        second = gen.call_args_list[1].kwargs
        self.assertIs(long_script, second["previous"])
        self.assertIn("300 words", second["feedback"])


class AlignmentTests(unittest.TestCase):
    def test_beats_start_when_their_first_word_is_spoken(self):
        beats = [_beat("one two three"), _beat("four five six")]
        words = _words("one two three four five six")
        slots = align_beats(beats, words, total_duration=3.0)
        self.assertEqual(0.0, slots[0]["start"])
        # "four" is spoken at 1.2s; the cut lands 0.1s early, snapped to frames.
        self.assertAlmostEqual(1.1, slots[1]["start"], delta=1 / FPS)
        self.assertEqual(round(3.0 * FPS), sum(s["frames"] for s in slots))
        self.assertEqual(3.0, slots[-1]["end"])

    def test_number_words_and_punctuation_still_align(self):
        beats = [_beat("It reached 400 degrees."), _beat("Then, it cooled down.")]
        words = _words("It reached four hundred degrees. Then it cooled down.")
        slots = align_beats(beats, words, total_duration=5.0)
        self.assertAlmostEqual(5 * 0.4 - 0.1, slots[1]["start"], delta=1 / FPS)

    def test_unmatched_beat_is_interpolated_between_neighbours(self):
        beats = [_beat("alpha beta"), _beat("zzz qqq"), _beat("gamma delta")]
        words = [{"text": "alpha", "start": 0.0, "end": 0.3}, {"text": "beta", "start": 0.4, "end": 0.7},
                 {"text": "xx", "start": 1.0, "end": 1.3}, {"text": "yy", "start": 1.4, "end": 1.7},
                 {"text": "gamma", "start": 2.0, "end": 2.3}, {"text": "delta", "start": 2.4, "end": 2.7}]
        slots = align_beats(beats, words, total_duration=3.0)
        self.assertLess(slots[0]["start"], slots[1]["start"])
        self.assertLess(slots[1]["start"], slots[2]["start"])
        self.assertAlmostEqual(1.0 - 0.1, slots[1]["start"], delta=0.15)

    def test_no_words_still_covers_whole_duration(self):
        beats = [_beat("a b"), _beat("c d"), _beat("e f")]
        slots = align_beats(beats, [], total_duration=6.0)
        self.assertEqual(180, sum(s["frames"] for s in slots))
        self.assertTrue(all(s["frames"] > 0 for s in slots))

    def test_subtitles_use_script_spelling_with_whisper_timing(self):
        beats = [_beat("The Antikythera mechanism — found 1901.")]
        words = [{"text": "The", "start": 0.0, "end": 0.2},
                 {"text": "Anti-kithera", "start": 0.3, "end": 0.8},   # misheard
                 {"text": "mechanism", "start": 0.9, "end": 1.4},
                 {"text": "found", "start": 1.5, "end": 1.8},
                 {"text": "nineteen-oh-one", "start": 1.9, "end": 2.6}]
        subs = script_word_timings(beats, words, total_duration=3.0)
        self.assertEqual(["The", "Antikythera", "mechanism", "found", "1901."], [w["text"] for w in subs])
        self.assertEqual(0.9, subs[2]["start"])
        self.assertTrue(0.0 < subs[1]["start"] < 0.9)  # interpolated between neighbours
        self.assertTrue(all(a["start"] <= b["start"] for a, b in zip(subs, subs[1:])))

    def test_frame_splits_sum_exactly(self):
        self.assertEqual([105, 105], split_frames(210))   # 7s → two 3.5s shots
        self.assertEqual([75], split_frames(75))
        self.assertEqual(101, sum(even_split(101, 3)))
        self.assertEqual([1, 1], even_split(2, 5))       # never more parts than frames


class DiagramTests(unittest.TestCase):
    VISUALS = {
        "key_phrase": {"text": "A computer built 2,000 years early"},
        "stat": {"value": "$4.2B", "label": "raised", "title": "Funding"},
        "process": {"steps": ["Heat", "Distil", "Cool"], "active_step": 2, "title": "Refining"},
        "timeline": {"events": [{"year": "1901", "label": "Found"}, {"year": "2005", "label": "Scanned"}]},
        "comparison": {"items": [{"label": "A", "value": 37, "display": "37"}, {"label": "B", "value": 12}]},
    }

    def test_every_template_draws_at_start_and_end(self):
        for template, params in self.VISUALS.items():
            visual = {"template": template, **params}
            for t in (0.0, 1.5, 3.0):
                frame = render_frame(visual, t, 3.0)
                self.assertEqual((1080, 1920), frame.size, template)
        self.assertEqual(set(TEMPLATES), set(self.VISUALS))

    def test_stat_counts_up_and_lands_on_exact_value(self):
        self.assertEqual("$0.0B", stat_text_at("$4.2B", 0.0))
        self.assertEqual("$4.2B", stat_text_at("$4.2B", 1.0))
        self.assertEqual("1,000", stat_text_at("1,000", 1.0))
        self.assertIn(",", stat_text_at("12,000 years", 0.5))
        self.assertEqual("1901", stat_text_at("1901", 0.2))  # years don't count up
        self.assertEqual("many", stat_text_at("many", 0.5))


class PhotoTests(unittest.TestCase):
    def test_only_free_licenses_pass(self):
        for ok in ("CC BY-SA 4.0", "CC BY 2.0", "Public domain", "CC0", "PD-old"):
            self.assertTrue(is_free_license(ok), ok)
        for bad in ("CC BY-NC 2.0", "CC BY-ND 4.0", "Fair use", "", "All rights reserved"):
            self.assertFalse(is_free_license(bad), bad)

    def test_parse_pages_builds_credit_and_filters(self):
        def page(title, license_name, width=2000, mime="image/jpeg"):
            return {"title": f"File:{title}", "imageinfo": [{
                "thumburl": f"https://x/{title}", "mime": mime, "width": width,
                "descriptionurl": f"https://commons/{title}",
                "extmetadata": {"LicenseShortName": {"value": license_name},
                                "Artist": {"value": "<a href='#'>Jane Doe</a>"}}}]}
        pages = {"1": page("good.jpg", "CC BY-SA 4.0"), "2": page("nc.jpg", "CC BY-NC 2.0"),
                 "3": page("tiny.jpg", "CC0", width=300), "4": page("doc.pdf", "CC0", mime="application/pdf")}
        found = parse_imageinfo_pages(pages)
        self.assertEqual(["good.jpg"], [c["title"] for c in found])
        self.assertIn("Jane Doe, CC BY-SA 4.0", found[0]["credit"])


class VisionTests(unittest.TestCase):
    def _images(self, tmp, n):
        from PIL import Image
        paths = []
        for i in range(n):
            p = os.path.join(tmp, f"{i}.jpg")
            Image.new("RGB", (64, 36), (i * 40, 0, 0)).save(p)
            paths.append(p)
        return paths

    def test_rank_returns_valid_unique_indices(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch("agents.llm.ask", return_value={"matches": [2, 0, 2, 9, "x"]}) as ask:
            self.assertEqual([2, 0], vision.rank_images("desc", "line", self._images(tmp, 3)))
        self.assertEqual(3, len(ask.call_args.kwargs["images"]))

    def test_vision_can_be_disabled(self):
        with patch.dict(os.environ, {"VISION_CHECK": "0"}):
            self.assertFalse(vision.vision_enabled())


if __name__ == "__main__":
    unittest.main()
