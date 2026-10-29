"""Build-up explainer format ("If you ..., you have a ..." → "Congratulations, you've built a ...")."""
import json
import os
import unittest
from unittest.mock import patch

from agents import buildup
from agents import showrunner as sr
from engine import sets

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "engine", "films", "pool_buildup.json")


def _script(film):
    return {"title": film["title"], "caption": "", "hashtags": [],
            "beats": [{"actions": list(b.get("actions") or [b["action"]]), "text": b["text"],
                       "overlay": b.get("overlay") or {"type": "none", "value": "", "text": ""}}
                      for b in film["beats"]]}


def _with(script, k, text):
    out = json.loads(json.dumps(script))
    out["beats"][k]["text"] = text
    return out


class BuildupTests(unittest.TestCase):
    def setUp(self):
        self.film = json.load(open(REF, encoding="utf-8"))
        self.script = _script(self.film)

    def test_enabled_for_explainer_sets_only(self):
        self.assertTrue(buildup.enabled("pool"))
        for set_id in sets.AVAILABLE:                     # Max story sets keep their own format
            self.assertFalse(buildup.enabled(set_id))
        with patch.dict(os.environ, {"EXPLAINER_FORMAT": "hook"}):
            self.assertFalse(buildup.enabled("pool"))

    def test_reference_script_passes(self):
        self.assertEqual(self.film["format"], "buildup")
        self.assertTrue(self.film["beats"][0]["text"].startswith("If you"))
        self.assertEqual(sr.hard_checks(self.script, "pool"), [])

    def test_must_open_with_if_you(self):
        bad = _with(self.script, 0, "Every backyard pool hides a secret. Dirt drinks water, so it needs a concrete shell.")
        self.assertTrue(any("If you" in p for p in sr.hard_checks(bad, "pool")))

    def test_must_end_with_congratulations_not_a_question(self):
        q = _with(self.script, -1, "Add a ladder and some sun. Would you swim in it?")
        self.assertTrue(any("question" in p for p in sr.hard_checks(q, "pool")))
        plain = _with(self.script, -1, "Add a ladder and some sun. And that is a pool, more or less.")
        self.assertTrue(any("Congratulations" in p for p in sr.hard_checks(plain, "pool")))

    def test_no_hook_or_rewind_and_build_starts_the_film(self):
        hooked = json.loads(json.dumps(self.script))
        hooked["beats"].insert(0, {"actions": ["float_hook"], "text": "If you build a pool, you have a pool.",
                                   "overlay": {"type": "none"}})
        probs = buildup.validate(sets.spec("pool"), hooked["beats"])
        self.assertTrue(any("no hook or rewind" in p for p in probs))
        self.assertTrue(any("beat 1 must start" in p for p in probs))

    def test_no_characters(self):
        bad = _with(self.script, 2, "But Max pours concrete on wet dirt and it cracks, so the floor gets gravel.")
        self.assertTrue(any("character" in p for p in sr.hard_checks(bad, "pool")))

    def test_rules_and_prompts_speak_the_format(self):
        rules = sr._rules("pool")
        self.assertIn('"If you"', rules)
        self.assertIn("No hook and no rewind", rules)
        self.assertIn("Congratulations", rules)
        topic = {"set": "pool", "hook_line": "If you dig a hole and fill it, you have a pool.", "hook_action": "dig"}
        self.assertIn("OPENING IDEA", sr._hook_idea(topic))
        self.assertIn("[dig] If you carve", sr._tone_example("pool"))
        self.assertIs(sr._directions("pool"), buildup.DIRECTIONS)

    def test_title_promises_a_visible_transformation(self):
        bad = json.loads(json.dumps(self.script))
        bad["title"] = "The Secret Danger Under Your Pool"
        self.assertTrue(any("title must use" in p for p in sr.hard_checks(bad, "pool")))

    def test_failure_retry_language_is_rejected(self):
        bad = _with(self.script, 2, "The first attempt failed, so rewind and repair the gravel bed.")
        self.assertTrue(any("no failure" in p for p in sr.hard_checks(bad, "pool")))

    def test_hook_mode_never_takes_the_buildup_film_as_tone(self):
        with patch.dict(os.environ, {"EXPLAINER_FORMAT": "hook"}):
            self.assertNotIn("Congratulations, you've built", sr._tone_example("pool"))

    def test_film_json_is_hookless(self):
        topic = {"set": "pool", "angle": "a", "hook_line": "If you ...", "hook_action": "dig"}
        film = sr.to_film(self.script, topic, "facts")
        self.assertEqual(film["format"], "buildup")
        self.assertIsNone(film["cta"])
        self.assertFalse(any(b.get("video") for b in film["beats"]))

    def test_cutaway_runner_and_make_film_know_hookless_films(self):
        runner = open(os.path.join(ROOT, "engine", "films", "cutaway_film.py"), encoding="utf-8").read()
        self.assertIn("HOOKLESS", runner)
        mf = open(os.path.join(ROOT, "engine", "make_film.py"), encoding="utf-8").read()
        self.assertIn('hookless = evolution or film.get("format") == "buildup"', mf)


if __name__ == "__main__":
    unittest.main()
