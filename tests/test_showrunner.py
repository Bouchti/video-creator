import json
import os
import tempfile
import unittest
from unittest.mock import patch

from engine.sets import spec
from agents import showrunner

# These tests exercise the classic hook + rewind rules with the pool set. Explainer sets now default
# to the build-up format (tests/test_buildup.py); EXPLAINER_FORMAT=hook keeps the classic path.

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _beats(actions, words=12):
    beats = [{"action": a, "text": " ".join(["word"] * words), "overlay": {"type": "none", "value": "", "text": ""}}
             for a in actions]
    if beats:                                          # every script ends with a question to the viewer
        beats[-1]["text"] = " ".join(["word"] * (words - 4)) + ". Would you try it?"
    return beats


GOOD = ["float_hook", "rewind", "dig", "layers", "gravel", "valve", "pipes", "rebar", "shotcrete", "cure",
        "finish", "fill", "weight", "flow", "cycle", "storm"]


@patch.dict(os.environ, {"EXPLAINER_FORMAT": "hook"})
class PoolSpecTests(unittest.TestCase):
    def test_reference_film_is_valid(self):
        film = json.load(open(os.path.join(ROOT, "engine", "films", "pool_cut.json"), encoding="utf-8"))
        self.assertEqual(spec("pool").validate(film["beats"]), [])

    def test_good_order(self):
        self.assertEqual(spec("pool").validate(_beats(GOOD)), [])

    def test_build_order_enforced(self):
        bad = GOOD.copy()
        bad[4], bad[5] = bad[5], bad[4]                  # valve before gravel
        self.assertTrue(any("build actions" in e for e in spec("pool").validate(_beats(bad))))

    def test_missing_build_step(self):
        self.assertTrue(spec("pool").validate(_beats([a for a in GOOD if a != "rebar"])))

    def test_explainer_needs_prerequisite(self):
        bad = ["float_hook", "rewind", "weight"] + [a for a in GOOD[2:] if a != "weight"]
        self.assertTrue(any("after 'fill'" in e for e in spec("pool").validate(_beats(bad))))

    def test_hook_and_rewind_first(self):
        self.assertTrue(spec("pool").validate(_beats(GOOD[1:])))
        self.assertTrue(spec("pool").validate(_beats(["float_hook"] + GOOD[2:])))

    def test_outro_must_be_last(self):
        bad = GOOD[:-2] + ["storm", "cycle"]
        self.assertTrue(any("outro" in e for e in spec("pool").validate(_beats(bad))))

    def test_unknown_action(self):
        self.assertTrue(any("unknown" in e for e in spec("pool").validate(_beats(GOOD + ["explode"]))))


@patch.dict(os.environ, {"EXPLAINER_FORMAT": "hook"})
class HardCheckTests(unittest.TestCase):
    def test_passes_in_budget(self):
        script = {"beats": _beats(GOOD, words=11)}            # 176 words
        script["beats"][0]["text"] = "An empty pool can float right out of the ground."
        self.assertEqual(showrunner.hard_checks(script, "pool"), [])

    def test_word_budget(self):
        problems = showrunner.hard_checks({"beats": _beats(GOOD, words=20)}, "pool")
        self.assertTrue(any("total narration" in p for p in problems))

    def test_hook_length(self):
        script = {"beats": _beats(GOOD, words=11)}
        script["beats"][0]["text"] = " ".join(["word"] * 20)
        self.assertTrue(any("hook is" in p for p in showrunner.hard_checks(script, "pool")))

    def test_sticker_limits(self):
        script = {"beats": _beats(GOOD, words=11)}
        for b in script["beats"][:8]:
            b["overlay"] = {"type": "stat", "value": "5 m", "text": "deep"}
        problems = showrunner.hard_checks(script, "pool")
        self.assertTrue(any("stickers" in p for p in problems))
        self.assertTrue(any("hook" in p for p in problems))

    def test_counter_gags_rejected(self):
        for gag in ("Flat boards barely deflect air. Physics 1.", "Score: 3-0 to the ground.", "Fail #2 begins."):
            script = {"beats": _beats(GOOD, words=11)}
            script["beats"][3]["text"] = gag
            self.assertTrue(any("counter gag" in p for p in showrunner.hard_checks(script, "pool")), gag)

    def test_real_numbers_allowed(self):
        for line in ("It needs 60 kilometres an hour.", "A bar every 25 centimetres.", "Double speed, four times lift."):
            self.assertIsNone(showrunner.GAG_RE.search(line), line)


@patch.dict(os.environ, {"EXPLAINER_FORMAT": "hook"})
class TopicSelectionTests(unittest.TestCase):
    def test_story_subject_is_consumed_after_first_script(self):
        history = [{"set": "nuclear_story", "title": "old", "angle": "old"}]
        available = showrunner.available_topic_sets(["nuclear_story", "boat_story"], history)
        self.assertEqual(available, ["boat_story"])

    def test_all_consumed_stops_before_any_ai_call(self):
        history = [{"set": set_id} for set_id in showrunner.sets.AVAILABLE]
        with patch.object(showrunner, "_history", return_value=history), \
                patch.object(showrunner, "_call", side_effect=AssertionError("AI must not run")):
            with self.assertRaisesRegex(showrunner.NoUnusedStorySets, "already been used"):
                showrunner.pick_topic()

    def test_film_rendered_outside_the_log_still_consumes_its_subject(self):
        root = tempfile.mkdtemp()
        films = os.path.join(root, "films")
        os.makedirs(films)
        with open(os.path.join(films, "by_hand.json"), "w", encoding="utf-8") as f:
            json.dump({"title": "By hand", "set": "boat_story", "meta": {"angle": "a"}}, f)
        with patch.object(showrunner, "HISTORY", os.path.join(root, "missing.json")), \
                patch.object(showrunner, "FILMS_DIR", films):
            self.assertEqual(showrunner.available_topic_sets(["nuclear_story", "boat_story"]), ["nuclear_story"])

    def test_explicit_repeat_override(self):
        history = [{"set": "nuclear_story"}]
        with patch.dict(os.environ, {"SHOWRUNNER_ALLOW_REPEATS": "1"}):
            self.assertEqual(showrunner.available_topic_sets(["nuclear_story"], history), ["nuclear_story"])

    def test_topic_research_fact_sheet_avoids_a_second_model_call(self):
        facts = "\n".join(f"- verified fact {n} from source.example with concrete details" for n in range(10))
        topic = {"set": "pool", "_fact_sheet": facts}
        with patch.object(showrunner, "FACTS_DIR", tempfile.mkdtemp()), \
                patch.object(showrunner, "_research", side_effect=AssertionError("must reuse combined research")):
            self.assertEqual(showrunner.research(topic), facts)


@patch.dict(os.environ, {"EXPLAINER_FORMAT": "hook"})
class RevisionTests(unittest.TestCase):
    def test_revision_is_regraded_and_can_pass_with_fresh_scores(self):
        low = {"scores": {name: 6 for name in
                           ("hook", "clarity", "story_flow", "problem_solution", "fun", "accuracy",
                            "pacing", "visual_sync", "learn")},
               "problems": ["needs work"], "line_edits": [], "verdict": "revise"}
        high = {"scores": {name: 8 for name in low["scores"]},
                "problems": [], "line_edits": [], "verdict": "ship"}
        original = {"title": "old", "beats": []}
        fixed = {"title": "new", "beats": []}
        topic = {"set": "pool", "title": "t", "angle": "a", "hook_line": "h",
                 "hook_action": "float_hook", "payoff": "p"}
        with patch.object(showrunner, "MAX_REVISIONS", 2), \
                patch.object(showrunner, "write_script", return_value=fixed), \
                patch.object(showrunner, "hard_checks", return_value=[]), \
                patch.object(showrunner, "critique_script", return_value=high) as grade:
            best, revised = showrunner._revise(topic, "facts", original, [], low,
                                                (original, [], low))
        self.assertTrue(revised)
        self.assertIs(best[0], fixed)
        self.assertIs(best[2], high)
        self.assertTrue(showrunner._ships(best[2], best[1]))
        grade.assert_called_once_with(fixed, topic, "facts", [])


@patch.dict(os.environ, {"EXPLAINER_FORMAT": "hook"})
class RuleRepairTests(unittest.TestCase):
    def test_one_word_over_budget_is_trimmed_not_redrafted(self):
        over = {"title": "t", "beats": _beats(GOOD, words=12)}            # 192 words
        over["beats"][0]["text"] = "An empty pool can float right out of the ground."
        over["beats"][3]["text"] += " extra extra extra"
        trimmed = json.loads(json.dumps(over))
        trimmed["beats"][3]["text"] = " ".join(["word"] * 12)
        problems = showrunner.hard_checks(over, "pool")
        self.assertTrue(any("total narration" in p for p in problems))
        with patch.object(showrunner, "_call", return_value=trimmed) as call:
            script, left = showrunner.repair_rules(over, "pool", problems)
        self.assertEqual(left, [])
        self.assertIs(script, trimmed)
        self.assertEqual(call.call_args.kwargs["effort"], "low")

    def test_a_repair_that_breaks_more_rules_is_not_taken(self):
        over = {"title": "t", "beats": _beats(GOOD, words=12)}
        over["beats"][3]["text"] += " extra extra extra"
        worse = {"title": "t", "beats": _beats(GOOD[:3], words=40)}
        problems = showrunner.hard_checks(over, "pool")
        with patch.object(showrunner, "_call", return_value=worse):
            script, left = showrunner.repair_rules(over, "pool", problems)
        self.assertIs(script, over)
        self.assertEqual(left, problems)


@patch.dict(os.environ, {"EXPLAINER_FORMAT": "hook"})
class ToFilmTests(unittest.TestCase):
    def test_roles_and_overlays(self):
        script = {"title": "T", "caption": "c", "hashtags": ["#a"], "beats": _beats(GOOD, words=11)}
        script["beats"][2]["overlay"] = {"type": "stat", "value": "50 tons", "text": "of soil"}
        script["beats"][4]["overlay"] = {"type": "label", "value": "", "text": "Gravel"}
        film = showrunner.to_film(script, {"set": "pool", "angle": "a"}, "facts")
        self.assertEqual(film["set"], "pool")
        self.assertEqual(film["beats"][0]["video"], "epilogue")
        self.assertEqual(film["beats"][1]["video"], "rewind")
        self.assertEqual(film["beats"][2]["overlay"], {"type": "stat", "value": "50 tons", "text": "of soil"})
        self.assertEqual(film["beats"][4]["overlay"], {"type": "label", "text": "Gravel"})
        self.assertNotIn("overlay", film["beats"][3])
        self.assertEqual(film["captions"], "word")

    def test_make_film_finds_roles(self):
        from engine.make_film import _beat_ids
        beats = [{"id": "float_hook", "video": "epilogue"}, {"id": "rewind", "video": "rewind"}, {"id": "dig"}]
        self.assertEqual(_beat_ids(beats), ["hook", "rewind", "dig"])


if __name__ == "__main__":
    unittest.main()


@patch.dict(os.environ, {"EXPLAINER_FORMAT": "hook"})
class MontageTests(unittest.TestCase):
    def test_grouped_build_steps_are_valid(self):
        beats = _beats(["float_hook", "rewind", "dig"]) + [
            {"actions": ["gravel", "valve", "pipes", "rebar"], "text": " ".join(["w"] * 30)},
            {"actions": ["shotcrete", "cure", "finish"], "text": " ".join(["w"] * 25)},
        ] + _beats(["fill", "flow"])
        self.assertEqual(spec("pool").validate(beats), [])

    def test_hook_cannot_be_grouped(self):
        beats = [{"actions": ["float_hook", "rewind"], "text": "x"}] + _beats(GOOD[2:])
        self.assertTrue(any("single action" in e for e in spec("pool").validate(beats)))

    def test_montage_needs_enough_words(self):
        beats = _beats(["float_hook", "rewind", "dig"], words=11) + [
            {"actions": ["gravel", "valve", "pipes", "rebar"], "text": "quick"},
        ] + _beats(["shotcrete", "cure", "finish", "fill", "flow", "cycle"], words=20)
        beats[0]["text"] = "An empty pool can float right out of the ground."
        problems = showrunner.hard_checks({"beats": beats}, "pool")
        self.assertTrue(any("needs at least" in p for p in problems))

    def test_to_film_montage(self):
        script = {"title": "T", "beats": _beats(["float_hook", "rewind"]) +
                  [{"actions": ["dig", "gravel"], "text": "a b", "overlay": {"type": "none", "value": "", "text": ""}}]}
        film = showrunner.to_film(script, {"set": "pool", "angle": "a"}, "f")
        self.assertEqual(film["beats"][2]["id"], "dig+gravel")
        self.assertEqual(film["beats"][2]["actions"], ["dig", "gravel"])


class NuclearSetTests(unittest.TestCase):
    def test_reference_film_is_valid(self):
        film = json.load(open(os.path.join(ROOT, "engine", "films", "max_nuclear.json"), encoding="utf-8"))
        self.assertEqual(spec("nuclear_story").validate(film["beats"]), [])
        self.assertEqual(showrunner.hard_checks({"beats": film["beats"]}, "nuclear_story"), [])

    def test_story_order_enforced(self):
        film = json.load(open(os.path.join(ROOT, "engine", "films", "max_nuclear.json"), encoding="utf-8"))
        beats = film["beats"]
        beats[4], beats[5] = beats[5], beats[4]            # control rods before the runaway
        self.assertTrue(any("story actions" in e for e in spec("nuclear_story").validate(beats)))


class BoatSetTests(unittest.TestCase):
    def test_reference_film_is_valid(self):
        film = json.load(open(os.path.join(ROOT, "engine", "films", "max_boat.json"), encoding="utf-8"))
        self.assertEqual(spec("boat_story").validate(film["beats"]), [])
        self.assertEqual(showrunner.hard_checks({"beats": film["beats"]}, "boat_story"), [])


@patch.dict(os.environ, {"EXPLAINER_FORMAT": "hook"})
class RetryContinuesTests(unittest.TestCase):
    def test_a_retry_revises_the_kept_best_script_instead_of_drafting_again(self):
        low = {"scores": {name: 6 for name in ("hook", "clarity", "story_flow", "problem_solution", "fun",
                                               "accuracy", "pacing", "visual_sync", "learn")},
               "problems": ["duck gag never set up"], "line_edits": [], "verdict": "revise"}
        high = {"scores": {k: 8 for k in low["scores"]}, "problems": [], "line_edits": [], "verdict": "ship"}
        topic = {"set": "pool", "title": "Same topic", "angle": "a", "hook_line": "h", "hook_action": "float_hook",
                 "payoff": "p"}
        kept = {"title": "kept", "beats": []}
        better = {"title": "better", "beats": []}
        films = tempfile.mkdtemp()
        with patch.object(showrunner, "FILMS_DIR", films), patch.object(showrunner, "hard_checks", return_value=[]):
            showrunner._keep_rejected(topic, kept, low, [])
            calls = []

            def write(t, facts, previous=None, critique=None, direction=None, effort="high"):
                calls.append(previous)
                return better

            with patch.object(showrunner, "write_script", side_effect=write), \
                    patch.object(showrunner, "critique_script", return_value=high):
                script, review = showrunner.develop(topic, "facts")
        self.assertIs(script, better)
        self.assertEqual(calls, [kept])                 # one revision of the kept script, no fresh draft


@patch.dict(os.environ, {"EXPLAINER_FORMAT": "hook"})
class WordBudgetTests(unittest.TestCase):
    def test_long_story_ladders_get_more_words_and_others_keep_the_default(self):
        self.assertEqual(showrunner.word_budget("pool"), showrunner.TARGET_WORDS)
        lo, hi = showrunner.word_budget("boat_story")
        n = len(spec("boat_story").STORY_ORDER) + 2
        self.assertEqual(hi, min(showrunner.WORDS_CAP, max(showrunner.TARGET_WORDS[1], showrunner.WORDS_PER_BEAT * n)))
        self.assertGreater(hi, showrunner.TARGET_WORDS[1])
        self.assertLessEqual(hi, showrunner.WORDS_CAP)


@patch.dict(os.environ, {"EXPLAINER_FORMAT": "hook"})
class ExtrasAndLastRevisionTests(unittest.TestCase):
    def test_the_writer_brief_tells_what_else_is_on_screen(self):
        sp = spec("boat_story")
        action = next(iter(sp.ACTIONS))
        with patch.dict(sp.ACTIONS[action], {"extras": "the rubber duck rides the wave"}):
            self.assertIn("Also on screen (use it for jokes): the rubber duck rides the wave",
                          showrunner._set_brief("boat_story"))

    def test_a_retry_continues_from_the_better_revision_and_its_notes(self):
        scores = ("hook", "clarity", "story_flow", "problem_solution", "fun", "accuracy", "pacing", "visual_sync",
                  "learn")
        old = {"scores": {k: 6 for k in scores}, "problems": ["old notes"]}
        new = {"scores": {k: 7 for k in scores}, "problems": ["new notes"]}
        topic = {"set": "pool", "title": "T"}
        with patch.object(showrunner, "FILMS_DIR", tempfile.mkdtemp()), \
                patch.object(showrunner, "hard_checks", return_value=[]):
            showrunner._keep_rejected(topic, {"title": "best"}, old, [], last=({"title": "newest"}, [], new))
            script, _problems, review = showrunner._last_rejected(topic)
        self.assertEqual(script["title"], "newest")
        self.assertEqual(review["problems"], ["new notes"])

    def test_a_retry_does_not_resume_from_a_newest_revision_that_regressed(self):
        scores = ("hook", "clarity", "story_flow", "problem_solution", "fun", "accuracy", "pacing", "visual_sync",
                  "learn")
        best = {"scores": {k: 7 for k in scores}, "problems": ["best notes"]}
        regressed = {"scores": {k: 6 for k in scores}, "problems": ["new but worse notes"]}
        topic = {"set": "pool", "title": "T"}
        with patch.object(showrunner, "FILMS_DIR", tempfile.mkdtemp()), \
                patch.object(showrunner, "hard_checks", return_value=[]):
            showrunner._keep_rejected(
                topic, {"title": "best"}, best, [], last=({"title": "newest"}, [], regressed))
            script, _problems, review = showrunner._last_rejected(topic)
        self.assertEqual(script["title"], "best")
        self.assertEqual(review["problems"], ["best notes"])


@patch.dict(os.environ, {"EXPLAINER_FORMAT": "hook"})
class ShipGateTests(unittest.TestCase):
    def _review(self, **low):
        sc = {k: 8 for k in ("hook", "clarity", "story_flow", "problem_solution", "fun", "accuracy", "pacing",
                             "visual_sync", "learn")}
        sc.update(low)
        return {"scores": sc}

    def test_every_score_at_7_ships_and_any_6_or_rule_break_does_not(self):
        self.assertTrue(showrunner._ships(self._review(fun=7, clarity=7), []))
        self.assertFalse(showrunner._ships(self._review(fun=6), []))
        self.assertFalse(showrunner._ships(self._review(accuracy=6), []))
        self.assertFalse(showrunner._ships(self._review(), ["total narration is 230 words"]))

    def test_a_kept_script_that_already_ships_is_reused_as_is(self):
        topic = {"set": "pool", "title": "T"}
        passing = self._review(fun=7)
        failing = self._review(fun=5)
        with patch.object(showrunner, "FILMS_DIR", tempfile.mkdtemp()),                 patch.object(showrunner, "hard_checks", return_value=[]):
            showrunner._keep_rejected(topic, {"title": "best"}, passing, [], last=({"title": "newest"}, [], failing))
            script, _p, review = showrunner._last_rejected(topic)
        self.assertEqual(script["title"], "best")
