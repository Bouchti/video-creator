import unittest
from unittest.mock import patch

from agents import evaluator, leader, script


class UnrealTopicTests(unittest.TestCase):
    def test_topic_selection_receives_unreal_renderability_rules(self):
        chosen = {"topic": "How a water tower maintains pressure", "angle": "story_behind",
                  "tone": "educational", "rationale": "Visible mechanism"}
        with patch("agents.ai_router.ask", return_value=chosen) as ask:
            self.assertEqual(leader.pick_topic([{"title": "water tower"}], [], source="unreal"), chosen)
        prompt = ask.call_args.args[1]
        self.assertIn("UNREAL RENDERABILITY", prompt)
        self.assertIn("Reject wars", prompt)

    def test_local_ai_topic_rules_reject_chart_only_discoveries(self):
        chosen = {"topic": "How a geyser erupts", "angle": "story_behind",
                  "tone": "educational", "rationale": "Visible physical stages"}
        with patch("agents.ai_router.ask", return_value=chosen) as ask:
            leader.pick_topic([{"title": "geyser"}], [], source="local-ai")
        prompt = ask.call_args.args[1]
        self.assertIn("invisible data", prompt)
        self.assertIn("without invented presenters", prompt)

    def test_local_ai_reselects_safety_filtered_topic_before_scripting(self):
        unsafe = {"topic": "Meerkats teach pups to hunt scorpion prey", "angle": "story_behind",
                  "tone": "shocking", "rationale": "Visual"}
        safe = {"topic": "Sunflowers turn as they grow toward morning light", "angle": "story_behind",
                "tone": "educational", "rationale": "Visible physical process"}
        with patch("agents.ai_router.ask", side_effect=[unsafe, safe]) as ask:
            chosen = leader.pick_topic([{"title": "meerkats"}, {"title": "sunflowers"}], [],
                                       source="local-ai")
        self.assertEqual(chosen, safe)
        self.assertEqual(ask.call_count, 2)
        self.assertIn("REJECTED BY THE VIDEO RENDERER", ask.call_args.args[1])

    def test_local_ai_safety_gate_names_blocking_concept(self):
        self.assertIn("scorpion", leader.local_ai_topic_problem(
            "Wild meerkats learn with live scorpions"))
        self.assertIsNone(leader.local_ai_topic_problem(
            "How fog forms above a cold valley"))

    def test_mentioning_a_conflict_does_not_block_a_topic(self):
        """script.py's CONTENT SAFETY block already bars violent imagery from every shot, so a war
        can be the occasion for a story the shots tell through its cause, setting or aftermath.
        Blocking the words rejected two of the channel's own published videos."""
        for topic in ("They Drafted a Bear Into the Army - Then He Carried Shells Into Battle",
                      "The Eclipse That Stopped a War | 585 BC",
                      "Why this WWII tank was abandoned in a field",
                      "The weapon factory that became a concert hall",
                      "The Hidden Fire Boudica Left Under London"):
            with self.subTest(topic=topic):
                self.assertIsNone(leader.local_ai_topic_problem(topic))

    def test_subjects_with_no_safe_shot_list_are_still_refused(self):
        for topic, expected in (
            ("Inside the autopsy that solved a 200-year-old mystery", "autopsy"),
            ("The public execution that changed English law", "execution"),
            ("Footage of the massacre was hidden for 40 years", "massacre"),
            ("The mass grave found under a car park", "mass grave"),
            ("The deadliest battle of the First World War", "deadliest"),
            ("The bloodiest day in American history", "bloodiest"),
        ):
            with self.subTest(topic=topic):
                problem = leader.local_ai_topic_problem(topic)
                self.assertIsNotNone(problem)
                self.assertIn(expected, problem)

    def test_animal_harm_is_refused_but_ordinary_wildlife_is_not(self):
        for topic in ("Meerkats teach pups to hunt scorpion prey",
                      "How the box jellyfish venom kills in minutes",
                      "Why this spider devours its own cubs",
                      "Praying mantis cannibalism explained"):
            with self.subTest(blocked=topic):
                self.assertIsNotNone(leader.local_ai_topic_problem(topic))
        for topic in ("How scorpions glow under ultraviolet light",
                      "How emperor penguins survive the Antarctic winter",
                      "The bird that eats seeds from a feeder"):
            with self.subTest(allowed=topic):
                self.assertIsNone(leader.local_ai_topic_problem(topic))

    def test_every_topic_the_channel_has_published_is_still_selectable(self):
        """Regression guard: the screen must never reject work this pipeline already shipped."""
        import json
        from pathlib import Path
        record = Path("output/used_topics.json")
        if not record.is_file():
            self.skipTest("no used_topics.json in this checkout")
        data = json.loads(record.read_text(encoding="utf-8"))
        topics = data if isinstance(data, list) else data.get("topics") or list(data.values())
        for entry in topics:
            topic = entry if isinstance(entry, str) else (entry.get("topic") or entry.get("title") or "")
            with self.subTest(topic=topic[:60]):
                self.assertIsNone(leader.local_ai_topic_problem(topic))

    def test_the_topic_that_produced_the_still_slideshow_is_now_refused(self):
        """The 2026-10-27 run: every shot had to be submerged, the generator drifted to dry land
        under a bright sky, and 11 of 22 shots ended as frozen still push-ins."""
        problem = leader.local_ai_topic_problem(
            "Scientists Found Lost Rivers Hidden Under the Great Barrier Reef")
        self.assertIsNotNone(problem)
        self.assertIn("three seconds", problem)          # the reason the leader is told to route around
        self.assertIn("ordinary air and daylight", problem)

    def test_settings_a_clip_generator_cannot_hold_are_refused(self):
        for topic in ("Divers mapped a sunken city off the coast",
                      "What lives on the deep-sea floor",
                      "The microscope image that changed medicine",
                      "The wreck still resting underwater off Gibraltar"):
            with self.subTest(topic=topic):
                self.assertIsNotNone(leader.local_ai_topic_problem(topic))

    def test_filmable_topics_still_pass(self):
        for topic in ("The Hidden Fire Boudica Left Under London - Still There Today",
                      "The abandoned Soviet railway that still cuts through the tundra",
                      "How a medieval bridge survived nine centuries of floods"):
            with self.subTest(topic=topic):
                self.assertIsNone(leader.local_ai_topic_problem(topic))

    def test_an_unfilmable_topic_is_reselected_before_any_gpu_work(self):
        bad = {"topic": "The lost rivers hidden under the reef", "angle": "story_behind",
               "tone": "shocking", "rationale": "Visual"}
        good = {"topic": "The bridge that outlived nine centuries of floods", "angle": "story_behind",
                "tone": "educational", "rationale": "Visible structure"}
        with patch("agents.ai_router.ask", side_effect=[bad, good]) as ask:
            chosen = leader.pick_topic([{"title": "reef"}, {"title": "bridge"}], [], source="local-ai")
        self.assertEqual(chosen, good)
        self.assertEqual(ask.call_count, 2)
        self.assertIn("REJECTED BY THE VIDEO RENDERER", ask.call_args.args[1])

    def test_the_gate_only_applies_to_the_local_ai_renderer(self):
        reef = {"topic": "Lost rivers under the reef", "angle": "story_behind",
                "tone": "shocking", "rationale": "Visual"}
        with patch("agents.ai_router.ask", return_value=reef) as ask:
            self.assertEqual(leader.pick_topic([{"title": "reef"}], [], source="pexels"), reef)
        self.assertEqual(ask.call_count, 1)              # stock footage can show a real reef

    def test_the_leader_is_warned_about_unfilmable_settings_up_front(self):
        """Cheaper than learning it from three rejection retries."""
        chosen = {"topic": "How a medieval bridge survived nine centuries of floods",
                  "angle": "story_behind", "tone": "educational", "rationale": "Visible structure"}
        with patch("agents.ai_router.ask", return_value=chosen) as ask:
            leader.pick_topic([{"title": "bridge"}], [], source="local-ai")
        prompt = ask.call_args.args[1]
        self.assertIn("ordinary air and daylight", prompt)
        self.assertIn("underwater", prompt)
        self.assertIn("three seconds", prompt)


class LocalAiRenderabilityPromptTests(unittest.TestCase):
    """Documentary accuracy binds the narration; the shots must still be renderable."""

    def test_documentary_shots_are_told_to_stay_filmable(self):
        prompt = script.system_prompt("local-ai", content_mode="documentary")
        self.assertIn("EVERY VISUAL MUST BE FILMABLE", prompt)
        self.assertIn("RV Investigator", prompt)         # the named-vessel example that failed
        self.assertIn("sonar", prompt)                   # instrument readouts become on-screen text
        self.assertIn("underwater", prompt)

    def test_the_narration_may_still_name_what_the_visual_may_not(self):
        prompt = script.system_prompt("local-ai", content_mode="documentary")
        self.assertIn("The\n     narration may still name it.", prompt)

    def test_the_rule_does_not_leak_into_the_stock_footage_pipeline(self):
        self.assertNotIn("EVERY VISUAL MUST BE FILMABLE", script.system_prompt("footage"))


class TopicGroundingTests(unittest.TestCase):
    """The topic is reconciled with its evidence BEFORE scripting, so STAGE 1 never has to write a
    story whose premise no source supports. On 2026-10-27 that cost 119k tokens and the whole topic."""

    CANDIDATES = [
        {"title": "NISAR sees Anak Krakatau grow", "url": "https://nasa.gov/nisar",
         "snippet": "NISAR radar shows Anak Krakatau grew after eruptions on September 4-6, 2026."},
        {"title": "Unrelated geyser story", "url": "https://example.com/geyser", "snippet": "Geysers."},
    ]
    RESEARCH = [{"title": "GVP", "url": "https://volcano.si.edu/anak",
                 "evidence": "Anak Krakatau erupted September 4-6, 2026."}]

    def test_the_candidates_the_scout_read_become_evidence(self):
        """research_topic() searches the whole topic paragraph and can return none of them back."""
        cited = leader.cited_candidates(self.CANDIDATES, ["https://nasa.gov/nisar"])
        self.assertEqual(1, len(cited))
        self.assertEqual("https://nasa.gov/nisar", cited[0]["url"])
        self.assertIn("September 4-6, 2026", cited[0]["evidence"])

    def test_an_uncited_candidate_is_not_smuggled_in_as_evidence(self):
        self.assertEqual([], leader.cited_candidates(self.CANDIDATES, ["https://nowhere.test/x"]))
        self.assertEqual([], leader.cited_candidates(self.CANDIDATES, None))

    def test_sources_are_merged_and_deduplicated_by_url(self):
        cited = leader.cited_candidates(self.CANDIDATES, ["https://nasa.gov/nisar"])
        merged = leader._merge_sources(cited, self.RESEARCH, cited)
        self.assertEqual(["https://nasa.gov/nisar", "https://volcano.si.edu/anak"],
                         [s["url"] for s in merged])

    def _flow(self, grounding, picks=None):
        picks = picks or [{"topic": "A volcano grew 300 m and collapsed in 2018", "angle": "story_behind",
                           "tone": "epic", "rationale": "Visible", "source_urls": ["https://nasa.gov/nisar"]}]
        with patch.object(leader, "search_trending_subjects", return_value=self.CANDIDATES), \
                patch.object(leader, "load_used_topics", return_value=[]), \
                patch.object(leader, "pick_topic", side_effect=picks) as pick, \
                patch.object(leader, "research_topic", return_value=self.RESEARCH), \
                patch.object(leader, "ground_topic", side_effect=grounding) as ground:
            try:
                selection = leader.find_todays_topic(source="local-ai")
            except RuntimeError as exc:
                return None, pick, ground, str(exc)
        return selection, pick, ground, None

    def test_the_writer_receives_the_grounded_topic_not_the_proposed_one(self):
        grounded = {"topic": "A volcano erupted on September 4-6, 2026 and grew",
                    "kept": ["erupted September 4-6, 2026"],
                    "dropped": ['"over 300 meters tall"', '"collapsed in December 2018"'],
                    "usable": True}
        selection, _, ground, err = self._flow([grounded])
        self.assertIsNone(err)
        self.assertEqual(grounded["topic"], selection["topic"])
        self.assertIn("300 m", selection["original_topic"])       # the proposal is kept for the record
        self.assertEqual(grounded, selection["grounding"])
        # grounding judged the topic against the merged pack, not just the fresh search
        urls = [s["url"] for s in ground.call_args.args[1]]
        self.assertIn("https://nasa.gov/nisar", urls)
        self.assertIn("https://volcano.si.edu/anak", urls)
        self.assertEqual(urls, [s["url"] for s in selection["research"]])

    def test_an_ungroundable_topic_is_replaced_rather_than_scripted(self):
        thin = {"topic": "x", "kept": [], "dropped": ["everything"], "usable": False}
        good = {"topic": "A sourced volcano story", "kept": ["a"], "dropped": [], "usable": True}
        picks = [{"topic": "unsupported one", "angle": "story_behind", "tone": "epic",
                  "rationale": "r", "source_urls": []},
                 {"topic": "second try", "angle": "story_behind", "tone": "epic",
                  "rationale": "r", "source_urls": []}]
        selection, pick, _, err = self._flow([thin, good], picks=picks)
        self.assertIsNone(err)
        self.assertEqual("A sourced volcano story", selection["topic"])
        self.assertEqual(2, pick.call_count)
        # the abandoned topic is fed back so the scout does not offer it again
        avoided = [t["topic"] for t in pick.call_args.args[1]]
        self.assertIn("unsupported one", avoided)

    def test_it_gives_up_cleanly_when_no_topic_can_be_grounded(self):
        thin = {"topic": "x", "kept": [], "dropped": ["all"], "usable": False}
        picks = [{"topic": f"bad {n}", "angle": "story_behind", "tone": "epic",
                  "rationale": "r", "source_urls": []} for n in range(3)]
        selection, pick, _, err = self._flow([thin, thin, thin], picks=picks)
        self.assertIsNone(selection)
        self.assertIn("fact-grounding", err)
        self.assertEqual(3, pick.call_count)

    def test_grounding_refuses_an_empty_rewrite(self):
        with patch.object(leader.ai_router, "ask", return_value={"topic": "  ", "usable": True}):
            with self.assertRaises(RuntimeError):
                leader.ground_topic("a topic", self.RESEARCH)

    def test_the_grounder_is_told_to_quote_its_evidence_before_dropping(self):
        seen = {}

        def capture(system, prompt, schema=None, **_):
            seen["prompt"], seen["schema"] = prompt, schema
            return {"topic": "t", "kept": [], "dropped": [], "usable": True}

        with patch.object(leader.ai_router, "ask", side_effect=capture):
            leader.ground_topic("A volcano 300 m tall", self.RESEARCH)
        self.assertIn("SEARCH THE EVIDENCE TEXT", seen["prompt"])
        self.assertIn("Do not drop a claim you have not looked for", seen["prompt"])
        self.assertIn("is NOT support", seen["prompt"])
        self.assertIn("September 4-6, 2026", seen["prompt"])        # the evidence is actually included
        self.assertEqual({"topic", "kept", "dropped", "usable"}, set(seen["schema"]["required"]))


class TopicIsNotEvidenceTests(unittest.TestCase):
    """The topic line is written before the sources are fetched, so its specifics are unverified.

    The 2026-10-27 Anak Krakatau run: the topic asserted a 300 m height and a two-thirds collapse in
    December 2018 that no retrieved source covered. The writer built the story's spine on them and
    the evaluator blocked seven beats, then two, then one — running out of attempts one step short.
    """

    TOPIC = ("Anak Krakatau first broke through the sea in 1927. It grew over 300 meters tall, lost "
             "about two-thirds of its height when its flank collapsed in December 2018.")
    RESEARCH = [{"title": "NISAR sees it grow",
                 "text": "The island continued growing after the September 2026 eruptions."}]

    def _prompt(self, content_mode="documentary", **kwargs):
        seen = {}

        def capture(system, prompt, schema=None, **_):
            seen["prompt"] = prompt
            return {}

        with patch("agents.script.ai_router.ask", side_effect=capture):
            try:
                script.generate_script(self.TOPIC, "epic", target_seconds=65, mode="local-ai",
                                       research=self.RESEARCH, content_mode=content_mode, **kwargs)
            except Exception:                      # the fake returns no script; only the prompt matters
                pass
        return seen.get("prompt", "")

    def test_a_documentary_draft_is_told_the_topic_is_only_a_lead(self):
        prompt = self._prompt()
        self.assertIn("LEAD, NOT A SOURCE", prompt)
        self.assertIn("must be DROPPED", prompt)
        self.assertIn("height, a date, a collapse", prompt)

    def test_a_revision_is_told_the_same_thing(self):
        prompt = self._prompt(previous={"video_title": "x", "beats": [{"text": "a word"}]},
                              feedback="Beat 1 [blocking]: unsupported height")
        self.assertIn("LEAD, NOT A SOURCE", prompt)

    def test_fiction_may_use_the_topic_freely(self):
        self.assertNotIn("LEAD, NOT A SOURCE", self._prompt(content_mode="fiction"))


class ScriptAttemptBudgetTests(unittest.TestCase):
    """Three rounds stranded a converging draft one blocking issue from PASS."""

    def _rounds(self, max_retries):
        from agents import evaluator
        drafts = []

        def draft(topic, tone, **kwargs):
            drafts.append(kwargs.get("feedback"))
            return {"video_title": "t", "description": "d", "spoken_script": "w " * 130,
                    "beats": [{"text": "w " * 10} for _ in range(13)], "story_premise": "p",
                    "protagonist_goal": "g", "stakes": "s", "ending_payoff": "e"}

        with patch("agents.script.generate_script", side_effect=draft), \
                patch.object(evaluator, "has_all_keys", return_value=(True, [])), \
                patch.object(evaluator, "length_feedback", return_value=None), \
                patch.object(evaluator, "evaluate_script",
                             return_value={"verdict": "FAIL", "feedback": "Beat 1 [blocking]: unsourced",
                                           "minor_only": False}):
            result = evaluator.evaluate_with_retry("topic", max_retries=max_retries, mode="local-ai")
        return result, drafts

    def test_every_allowed_round_is_actually_used_before_the_topic_is_discarded(self):
        result, drafts = self._rounds(5)
        self.assertIsNone(result)                        # still failing, so the topic is dropped
        self.assertEqual(5, len(drafts))                 # but only after all 5 revisions
        self.assertIsNone(drafts[0])                     # first draft has no feedback
        self.assertTrue(all(drafts[1:]))                 # every later round revises with feedback

    def test_a_draft_that_converges_is_accepted_on_a_later_round(self):
        from agents import evaluator
        verdicts = iter([
            {"verdict": "FAIL", "feedback": "3 blocking", "minor_only": False},
            {"verdict": "FAIL", "feedback": "1 blocking", "minor_only": False},
            {"verdict": "PASS", "feedback": "", "minor_only": False},
        ])
        script_obj = {"video_title": "t", "description": "d", "spoken_script": "w " * 130,
                      "beats": [{"text": "w " * 10} for _ in range(13)], "story_premise": "p",
                      "protagonist_goal": "g", "stakes": "s", "ending_payoff": "e"}
        with patch("agents.script.generate_script", return_value=script_obj), \
                patch.object(evaluator, "has_all_keys", return_value=(True, [])), \
                patch.object(evaluator, "length_feedback", return_value=None), \
                patch.object(evaluator, "evaluate_script", side_effect=lambda *a, **k: next(verdicts)):
            self.assertIsNotNone(evaluator.evaluate_with_retry("topic", max_retries=5, mode="local-ai"))

    def test_three_rounds_would_have_discarded_that_same_converging_draft(self):
        """Why the default moved to 5: the third round was still blocking."""
        result, drafts = self._rounds(3)
        self.assertIsNone(result)
        self.assertEqual(3, len(drafts))


class UnrealScriptTests(unittest.TestCase):
    def test_unreal_schema_uses_only_supported_diorama_fields(self):
        schema = script.build_script_tool(10, 50, 80, "unreal")["input_schema"]
        self.assertNotIn("characters", schema["properties"])
        visual = schema["properties"]["beats"]["items"]["properties"]["visual"]
        self.assertEqual(set(visual["properties"]), {"kind", "description", "camera", "action"})
        self.assertEqual(visual["properties"]["kind"]["enum"], ["scene"])
        self.assertIn("pump_up", visual["properties"]["action"]["enum"])      # what the sets can act out
        self.assertIn("set", schema["required"])                               # one set for the whole film

    def test_unreal_evaluator_does_not_require_human_drama(self):
        result = {"verdict": "PASS", "feedback": "", "issues": []}
        with patch("agents.ai_router.ask", return_value=result) as ask:
            evaluator.evaluate_script({"spoken_script": "Water enters a pump."}, source="unreal")
        self.assertIs(ask.call_args.args[0], evaluator.UNREAL_EVALUATOR_PROMPT)


if __name__ == "__main__":
    unittest.main()
