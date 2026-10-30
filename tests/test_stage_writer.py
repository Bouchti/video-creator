import copy
import unittest
from unittest import mock

from agents import stage_writer as sw

WORDS = ("Max swore his bike balances itself. Kid1 rolled her eyes. " * 14).split()


def _plan():
    text = " ".join(WORDS[:150])
    beats = []
    for k in range(6):
        beats.append({"id": f"b{k}", "text": "Max rides. The bike wobbles." if k == 0 else text[k * 3:][:40] + " Max rides.",
                      "shows": "Max on a bike", "hook_text": "BIKE?!" if k == 0 else "",
                      "shot": {"frame": "wide", "on": "family", "move": "push_in"},
                      "cast": [{"who": "Max", "do": "walk_proud", "at": "Max", "to": "bike", "move": "walk"}],
                      "events": [{"prop": "bike", "does": "wobble", "at": "Max"}], "sounds": [], "labels": [],
                      "callouts": []})
    return {"title": "Bike", "caption": "", "hashtags": [], "facts": [],
            "place": {"ground": "grass", "sky": "day", "backdrop": []},
            "props": [{"id": "bike", "query": "bicycle", "size_m": 1.8, "spot": "center", "facing": 0},
                      {"id": "ramp", "query": "wooden ramp", "size_m": 2.0, "spot": "left", "facing": 0},
                      {"id": "cone", "query": "traffic cone", "size_m": 0.7, "spot": "right", "facing": 0}],
            "beats": beats}


def CLEAR(s, p, sc):
    return {"learned": "bikes steer themselves", "confusing": [], "jargon": [], "fun": 5, "clear": True, "fix": ""}


def CONFUSED(s, p, sc):
    return {"learned": "", "confusing": ["what is a steering axis?"], "jargon": ["trail"], "fun": 2, "clear": False,
            "fix": "explain trail"}


class VoiceLengthTest(unittest.TestCase):
    def test_word_budget_follows_the_voice(self):
        with mock.patch.object(sw, "_rates_file", return_value="__none__.json"):
            self.assertEqual(sw.words_range("elevenlabs"), (144, 157))
            lo, hi = sw.words_range("chatterbox")
            self.assertTrue(170 <= lo < hi <= 200)

    def test_measured_rate_is_learned(self):
        import os
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "rates.json")
        with mock.patch.object(sw, "_rates_file", return_value=path):
            sw.record_rate(146, 46.3, "chatterbox")
            self.assertAlmostEqual(sw.voice_rate("chatterbox"), 3.153, places=2)

    def test_resize_keeps_cues_or_keeps_the_old_text(self):
        p = sw.repair(copy.deepcopy(_plan()))

        def longer(s, pr, sc):
            return {"beats": [{"id": b["id"], "text": b["text"] + " And then even more happens."}
                              for b in p["beats"]]}

        def lost_cue(s, pr, sc):
            return {"beats": [{"id": b["id"], "text": "Something else entirely."} for b in p["beats"]]}
        p["beats"][0]["text"] = "Max rides."          # the cold open stays <= 12 words after "longer"
        self.assertNotEqual(sw.resize(p, 200, call=longer)["beats"][1]["text"], p["beats"][1]["text"])
        self.assertIs(sw.resize(p, 200, call=lost_cue), p)


class ClarityTest(unittest.TestCase):
    def test_confusion_jargon_boredom_and_nothing_learned_are_problems(self):
        issues = sw.clarity_problems(CONFUSED(None, None, None))
        self.assertTrue(any("confused here: what is a steering axis" in i for i in issues))
        self.assertTrue(any("'trail' is jargon" in i for i in issues))
        self.assertTrue(any(i.startswith("fun: rated 2/5") for i in issues))
        self.assertTrue(any(i.startswith("teach:") for i in issues))
        self.assertEqual(sw.clarity_problems(CLEAR(None, None, None)), [])

    def test_unclear_plan_is_rewritten_once_with_the_judges_words(self):
        good = sw.repair(copy.deepcopy(_plan()))
        prompts = []

        def writer(s, p, sc):
            prompts.append(p)
            return copy.deepcopy(good)
        verdicts = iter([CONFUSED(0, 0, 0), CLEAR(0, 0, 0)])
        with mock.patch.object(sw, "validate", return_value=[]):      # the fixture is about clarity only
            plan = sw.write("bikes", "- facts", call=writer, judge=lambda s, p, sc: next(verdicts))
        self.assertTrue(any("what is a steering axis" in p for p in prompts))
        self.assertEqual(plan["clarity"]["learned"], "bikes steer themselves")

    def test_a_judge_failure_never_blocks(self):
        def broken(s, p, sc):
            raise RuntimeError("offline")
        self.assertIsNone(sw.clarity(_plan(), broken))


class PictureTest(unittest.TestCase):
    def test_every_event_has_a_plain_look(self):
        self.assertEqual(set(sw.EVENT_LOOKS), set(sw.EVENTS))

    def test_the_judge_sees_the_data_not_the_writers_note(self):
        p = _plan()
        b = p["beats"][1]
        b["shows"] = "the handlebars turn toward the fall"
        line = sw.screen(b, p)
        self.assertNotIn("handlebars", line)
        self.assertIn("the bicycle rocks a little and settles", line)
        self.assertIn("Max walk proud after walking to bike", line)
        self.assertIn("plain coloured shape standing in for 'bicycle'", sw.screen(b, p, missing={"bike"}))

    def test_unshown_claims_are_problems(self):
        report = dict(CLEAR(0, 0, 0), unshown=["[b5] the hinge is tilted -> only a still bike"])
        self.assertTrue(any(i.startswith("picture: said but not shown: [b5]") for i in sw.clarity_problems(report)))

    def test_arrows_are_checked_shown_and_repaired(self):
        p = _plan()
        p["beats"][2]["arrows"] = [{"prop": "bike", "dir": "right", "text": "LEANS RIGHT", "at": "Max"},
                                   {"prop": "ghost", "dir": "sideways", "text": "a b c d e f", "at": "zoom"}]
        problems = sw.validate(p)
        for bit in ("arrow prop 'ghost'", "arrow dir 'sideways'", "arrow cue 'zoom'", "longer than 4 words"):
            self.assertTrue(any(bit in x for x in problems), bit)
        self.assertIn("a big arrow pointing right drawn over the bicycle, captioned 'LEANS RIGHT'",
                      sw.screen(p["beats"][2], p))
        r = sw.repair(copy.deepcopy(p))
        self.assertEqual([a["prop"] for a in r["beats"][2]["arrows"]], ["bike"])

    def test_only_the_characters_the_sentence_is_about_act(self):
        p = _plan()
        p["beats"][2]["cast"] += [{"who": "Max", "do": "point", "at": "start"},
                                  {"who": "Kid1", "do": "jump", "at": "start"},
                                  {"who": "Kid2", "do": "dance", "at": "start"}]
        self.assertTrue(any("b2: only the 1-2 characters" in x for x in sw.validate(p)))
        r = sw.repair(copy.deepcopy(p))
        self.assertEqual([c["who"] for c in r["beats"][2]["cast"]], ["Max", "Kid1"])
        self.assertIn("Kid2 watches", sw.screen(r["beats"][2], r))

    def test_too_many_acting_props_are_reported_and_repaired(self):
        p = _plan()
        p["beats"][2]["events"] += [{"prop": "ramp", "does": "spin", "at": "Max"},
                                    {"prop": "cone", "does": "bounce", "at": "Max"},
                                    {"prop": "ramp2", "does": "spin", "at": "Max"}]
        p["props"].append({"id": "ramp2", "query": "plank", "size_m": 1.0, "spot": "back", "facing": 0})
        self.assertTrue(any("4 props act in one beat" in x for x in sw.validate(p)))
        r = sw.repair(copy.deepcopy(p))
        self.assertEqual({e["prop"] for e in r["beats"][2]["events"]}, {"bike", "ramp", "cone"})

    def test_missing_props_get_new_searches_and_failures_keep_the_plan(self):
        p = _plan()
        new = sw.replace_props(p, ["cone"], call=lambda s, pr, sc: {"props": [{"id": "cone", "query": "orange cone"},
                                                                             {"id": "bike", "query": "car"}]})
        self.assertEqual([x["query"] for x in new["props"]], ["bicycle", "wooden ramp", "orange cone"])
        self.assertEqual(p["props"][2]["query"], "traffic cone")

        def broken(s, pr, sc):
            raise RuntimeError("offline")
        self.assertIs(sw.replace_props(p, ["cone"], call=broken), p)


class ValidateTest(unittest.TestCase):
    def test_unknown_prop_and_missing_cue_are_reported(self):
        p = _plan()
        p["beats"][2]["events"].append({"prop": "rocket", "does": "spin", "at": "zoom"})
        problems = sw.validate(p)
        self.assertTrue(any("'rocket' is not a prop id" in x for x in problems))
        self.assertTrue(any("'zoom' is not a word" in x for x in problems))

    def test_shared_spot_reported(self):
        p = _plan()
        p["props"][1]["spot"] = "center"
        self.assertTrue(any("share a spot" in x for x in sw.validate(p)))

    def test_repair_drops_broken_parts_and_keeps_the_film(self):
        p = _plan()
        p["beats"][2]["events"].append({"prop": "rocket", "does": "spin", "at": "zoom"})
        p["beats"][3]["cast"][0]["at"] = "nowhere"
        p["beats"][4]["shot"]["on"] = "the moon"
        r = sw.repair(copy.deepcopy(p))
        self.assertEqual([e["prop"] for e in r["beats"][2]["events"]], ["bike"])
        self.assertEqual(r["beats"][3]["cast"][0]["at"], "start")
        self.assertEqual(r["beats"][4]["shot"]["on"], "family")

    def test_clips_come_from_the_motion_library(self):
        self.assertIn("walk", sw.DO)
        self.assertIn("dance", sw.DO)
        self.assertEqual(sw.schema()["properties"]["beats"]["items"]["properties"]["cast"]["items"]
                         ["properties"]["do"]["enum"], sw.DO)

    def test_a_flat_hook_is_reported(self):
        p = _plan()
        problems = sw.validate(p)
        self.assertTrue(any(x.startswith("hook: no spectacle") for x in problems))
        self.assertTrue(any(x.startswith("hook: a kid must react") for x in problems))

    def test_a_real_hook_passes(self):
        b = _plan()["beats"][0]
        b["events"] = [{"prop": "bike", "does": "launch", "at": "Max"}]
        b["cast"].append({"who": "Kid2", "do": "jump", "at": "start"})
        b["sounds"] = [{"name": "boing", "at": "start"}]
        b["shot"]["frame"] = "medium"
        self.assertEqual(sw.hook_problems(b), [])

    def test_repair_forces_a_hook(self):
        r = sw.repair(copy.deepcopy(_plan()))
        self.assertEqual(sw.hook_problems(r["beats"][0]), [])

    def test_restage_keeps_the_words_and_never_fails(self):
        p = sw.repair(copy.deepcopy(_plan()))
        def broken(s, pr, sc):
            raise RuntimeError("no network")
        b = sw.restage_hook(p, "nothing happens", call=broken)
        self.assertEqual(b["text"], p["beats"][0]["text"])
        self.assertEqual(sw.hook_problems(b), [])
        self.assertTrue(any(e["does"] == "confetti" for e in b["events"]))

    def test_write_falls_back_to_repaired_plan(self):
        bad = _plan()
        bad["beats"][1]["events"].append({"prop": "ghost", "does": "glow", "at": "Max"})
        plan = sw.write("bikes", "- facts", call=lambda s, p, sc: copy.deepcopy(bad), judge=CLEAR)
        self.assertEqual(plan["world"], "stage")
        self.assertTrue(plan["quality_warnings"])
        self.assertFalse(any(e["prop"] == "ghost" for b in plan["beats"] for e in b.get("events", [])))


if __name__ == "__main__":
    unittest.main()
