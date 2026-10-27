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
