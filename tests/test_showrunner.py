import json
import os
import tempfile
import unittest
from unittest.mock import patch

from engine.sets import spec
from agents import showrunner
from agents import llm

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
                patch.object(llm, "ask", side_effect=AssertionError("AI must not run")):
            with self.assertRaisesRegex(showrunner.NoUnusedStorySets, "already been used"):
                showrunner.pick_topic()

    def test_film_rendered_outside_the_log_still_consumes_its_subject(self):
        root = tempfile.mkdtemp()
        films = os.path.join(root, "films")
        os.makedirs(films)
        with open(os.path.join(films, "by_hand.json"), "w", encoding="utf-8") as f:
            json.dump({"title": "By hand", "set": "boat_story", "meta": {"angle": "a"}}, f)
        with patch.object(showrunner, "HISTORY", os.path.join(root, "missing.json")), \
                patch.object(showrunner, "FILMS_DIR", films), \
                patch.object(showrunner, "ENGINE_FILMS_DIR", os.path.join(root, "none")):
            self.assertEqual(showrunner.available_topic_sets(["nuclear_story", "boat_story"]), ["nuclear_story"])

    def test_committed_hero_films_consume_their_subject(self):
        # the published pool / boat / pumpkin films live in engine/films, outside the log
        root = tempfile.mkdtemp()
        with patch.object(showrunner, "HISTORY", os.path.join(root, "missing.json")), \
                patch.object(showrunner, "FILMS_DIR", os.path.join(root, "none")):
            available = showrunner.available_topic_sets(["boat_story", "pool_story", "record_chasing_giant_pumpkin_story"])
        self.assertEqual(available, [])

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
        with patch.object(llm, "ask", return_value=trimmed) as call:
            script, left = showrunner.repair_rules(over, "pool", problems)
        self.assertEqual(left, [])
        self.assertIs(script, trimmed)
        self.assertEqual(call.call_args.kwargs["effort"], "low")

    def test_a_repair_that_breaks_more_rules_is_not_taken(self):
        over = {"title": "t", "beats": _beats(GOOD, words=12)}
        over["beats"][3]["text"] += " extra extra extra"
        worse = {"title": "t", "beats": _beats(GOOD[:3], words=40)}
        problems = showrunner.hard_checks(over, "pool")
        with patch.object(llm, "ask", return_value=worse):
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
        target = showrunner.target_words()
        self.assertEqual(showrunner.word_budget("pool"), target)
        lo, hi = showrunner.word_budget("boat_story")
        n = len(spec("boat_story").STORY_ORDER) + 2
        cap = showrunner._words(showrunner.MAX_SECONDS)
        self.assertEqual(hi, min(cap, max(target[1], showrunner._words(showrunner.SECONDS_PER_BEAT * n))))
        self.assertGreater(hi, target[1])
        self.assertLessEqual(hi, cap)

    def test_scripts_are_sized_for_the_voice_that_really_speaks(self):
        # the tunnel script was sized for 2.4 words/s; Chatterbox spoke 3.27 and every action ran ~35 % fast
        from agents import stage_writer
        path = os.path.join(tempfile.mkdtemp(), "rates.json")
        with patch.object(stage_writer, "_rates_file", return_value=path),                 patch.dict(os.environ, {"VOICE_ENGINE": "chatterbox"}):
            stage_writer.record_rate(176, 53.8, route="cutaway")
            lo, hi = showrunner.word_budget("pool")
            self.assertEqual((lo, hi), (round(58 * 3.27), round(80 * 3.27)))
            self.assertIn("3.27 x 0.75 words", showrunner._rules("boat_story"))
            beats = _beats(["float_hook", "rewind"] + list(spec("boat_story").STORY_ORDER), words=11)
            short = [p for p in showrunner.hard_checks({"beats": beats}, "boat_story") if "it needs at least" in p]
            self.assertTrue(short)                       # 11 words cannot carry a 4 s action at this pace


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


class HumanScaleTests(unittest.TestCase):
    BIG = {"subject": "Undersea tunnel", "largest_part_m": 40, "trend_source_url": "https://a.example",
           "trend_signal": "x", "hook_line": "h", "payoff": "p"}

    def _plan(self, searches, verdict):
        prompts = []

        def call(system, prompt, schema, **kw):
            prompts.append(prompt)
            return {"candidates": [dict(c) for c in searches[len(prompts) - 1]]}

        def judge(topic, need_demo=True, report=None):
            problem, known, impressive = verdict(topic)
            if report is not None:
                report["impressive"] = impressive
            return problem, known
        with patch.object(llm, "ask", side_effect=call),                 patch.object(showrunner, "_history", return_value=[]),                 patch.object(showrunner, "_wishlist", return_value=[]), patch.object(showrunner, "_subjects_in_progress", return_value=[]), patch.dict(os.environ, {"NEW_SET_SEARCHES": str(len(searches))}),                 patch("agents.leader.novelty_problem", side_effect=judge) as judged:
            return showrunner.plan_new_story_set(), prompts, judged

    def test_a_giant_subject_never_reaches_the_paid_judge(self):
        # a full-size sea tunnel left Max at 14% of the frame and 9 of 13 scenes failed
        small = dict(self.BIG, subject="Backyard floating dock", largest_part_m=6)
        plan, prompts, judged = self._plan([[self.BIG, small]], lambda t: (None, 10, 8))
        self.assertEqual(plan["subject"], "Backyard floating dock")
        self.assertEqual(judged.call_count, 1)
        self.assertEqual(len(prompts), 1)                # one search returned both candidates

    def test_three_candidates_are_judged_at_once_and_the_most_impressive_passing_one_wins(self):
        a, b, c = (dict(self.BIG, subject=n, largest_part_m=5) for n in ("Sandcastle", "Ice bridge", "Glass boat"))
        scores = {"Sandcastle": ("not impressive enough", 6), "Ice bridge": (None, 8), "Glass boat": (None, 9)}
        plan, prompts, judged = self._plan([[a, b, c]], lambda t: (scores[t.split(":")[0]][0], 10,
                                                                   scores[t.split(":")[0]][1]))
        self.assertEqual(plan["subject"], "Glass boat")
        self.assertEqual((len(prompts), judged.call_count), (1, 3))

    def test_a_second_search_is_told_what_failed_and_the_best_is_used_anyway(self):
        first = [dict(self.BIG, subject=f"Plain {k}", largest_part_m=5) for k in range(3)]
        second = [dict(self.BIG, subject=f"Odd {k}", largest_part_m=5) for k in range(3)]
        plan, prompts, _ = self._plan([first, second], lambda t: ("too common", 50, 7 if t.startswith("Odd 2") else 5))
        self.assertIn("Plain 0 (too common)", prompts[1])
        self.assertEqual(plan["subject"], "Odd 2")


class NewSetPlanScriptTests(unittest.TestCase):
    """The script of a NEW set comes from its plan: the plan's prose hook is mapped to the set's hook action.
    A fresh topic search found the new set 'consumed' (its own reference film) and, with
    SHOWRUNNER_FORCE_NEW_SET=1, filtered it out entirely: the run would have stopped after building the set."""
    SET = "immersed_undersea_tunnel_con_story"

    def test_a_prose_hook_maps_to_the_hook_action_that_shows_it(self):
        self.assertEqual(showrunner._hook_for(self.SET, "Max drives his family car through the lit dry tunnel"),
                         "happy_hook")
        self.assertEqual(showrunner._hook_for(self.SET, "a sealed concrete block floats out of the dock"),
                         "float_hook")

    def test_the_plan_is_scripted_without_a_new_topic_search(self):
        plan = {"title": "t", "angle": "a", "hook_line": "h", "payoff": "p", "trend_signal": "s",
                "trend_source_url": "https://x.example", "hook_action": "the block floats out to sea",
                "fact_sheet": "facts"}
        seen = {}

        def develop(topic, facts):
            seen.update(topic)
            return {"title": "T", "beats": []}, {}
        d = tempfile.mkdtemp()
        with patch.dict(os.environ, {"SHOWRUNNER_FORCE_NEW_SET": "1"}), \
                patch.object(showrunner, "pick_topic", side_effect=AssertionError("no new topic search")), \
                patch.object(showrunner, "research", return_value="facts"), \
                patch.object(showrunner, "_ensure_extras"), \
                patch.object(showrunner, "develop", side_effect=develop), \
                patch.object(showrunner, "to_film", return_value={"beats": [{"id": "h", "text": "x"}]}), \
                patch.object(showrunner, "FILMS_DIR", d), patch.object(showrunner, "HISTORY", os.path.join(d, "h.json")), \
                patch.object(showrunner, "_history", return_value=[]):
            path = showrunner.run(render=False, set_id=self.SET, topic_hint=plan)
        self.assertTrue(os.path.isfile(path))
        self.assertEqual((seen["hook_action"], seen["set"], seen["angle"]), ("float_hook", self.SET, "a"))

    def test_force_new_set_never_filters_a_set_named_explicitly(self):
        with patch.dict(os.environ, {"SHOWRUNNER_FORCE_NEW_SET": "1"}):
            self.assertEqual(showrunner.available_topic_sets([self.SET], history=[]), [self.SET])
            self.assertNotIn("boat_story", showrunner.available_topic_sets(history=[]))


class OneWordOverTests(unittest.TestCase):
    """A revision that met the bar was beaten by an older fun-6 draft because one beat had 33 words (max 32)."""
    GOOD = {k: 8 for k in ("hook", "clarity", "story_flow", "problem_solution", "fun", "accuracy", "pacing",
                           "visual_sync", "learn")}

    def test_a_revision_is_trimmed_before_it_is_graded(self):
        draft = ({"title": "old"}, [], dict(scores=dict(self.GOOD, fun=6)))
        revision = {"title": "new"}
        trimmed = {"title": "new, trimmed"}
        graded = []

        def critique(script, topic, facts, problems):
            graded.append((script["title"], problems))
            return {"scores": dict(self.GOOD)}
        with patch.object(showrunner, "write_script", return_value=revision), \
                patch.object(showrunner, "hard_checks", return_value=["beat 12 has 33 words; max 32"]), \
                patch.object(showrunner, "repair_rules", return_value=(trimmed, [])), \
                patch.object(showrunner, "critique_script", side_effect=critique):
            best, revised = showrunner._revise({"set": "pool"}, "f", *draft, best=draft)
        self.assertEqual(graded[0], ("new, trimmed", []))
        self.assertTrue(revised)
        self.assertEqual(best[0]["title"], "new, trimmed")

    def test_a_retry_ships_the_saved_revision_once_it_is_trimmed(self):
        d = tempfile.mkdtemp()
        topic = {"set": "pool", "title": "T"}
        with patch.object(showrunner, "FILMS_DIR", d):
            showrunner._keep_rejected(topic, {"title": "old"}, {"scores": dict(self.GOOD, fun=6)}, [],
                                      last=({"title": "new"}, ["beat 12 has 33 words; max 32"],
                                            {"scores": dict(self.GOOD)}))
            with patch.object(showrunner, "hard_checks",
                              side_effect=lambda s, set_id: ["beat 12 has 33 words; max 32"] if s["title"] == "new" else []), \
                    patch.object(showrunner, "repair_rules", return_value=({"title": "new, trimmed"}, [])):
                script, problems, review = showrunner._last_rejected(topic)
        self.assertEqual((script["title"], problems), ("new, trimmed", []))
        self.assertTrue(showrunner._ships(review, problems))
