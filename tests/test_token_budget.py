"""CLAUDE_TOKEN_BUDGET: the backstop that stops a repair loop from spending a whole subscription.

The autopilot's render stage multiplies: AUTOPILOT_MAX_ATTEMPTS renders, each running up to
SCENE_FIX_ATTEMPTS agentic code-fix sessions, each of which re-renders and re-reviews the film.
The budget is checked BEFORE a Claude call so work is never abandoned half-finished, and a spent
budget must stop the run rather than trigger another retry.
"""
import os
import unittest
from unittest.mock import patch

from agents import autopilot, llm, set_builder


class TokenBudgetTests(unittest.TestCase):
    def setUp(self):
        self._saved = dict(llm.CLAUDE_USAGE)

    def tearDown(self):
        llm.CLAUDE_USAGE.clear()
        llm.CLAUDE_USAGE.update(self._saved)

    def _spend(self, tokens):
        llm.CLAUDE_USAGE.update(calls=3, input_tokens=tokens, cache_read_input_tokens=0,
                                       cache_creation_input_tokens=0, output_tokens=0)

    def test_tokens_used_sums_every_billed_category(self):
        llm.CLAUDE_USAGE.update(calls=1, input_tokens=1, cache_read_input_tokens=10,
                                       cache_creation_input_tokens=100, output_tokens=1000)
        self.assertEqual(llm.tokens_used(), 1111)

    def test_an_unset_or_zero_budget_never_blocks(self):
        self._spend(10 ** 9)
        for value in ("0", "", "not-a-number"):
            with patch.dict(os.environ, {"CLAUDE_TOKEN_BUDGET": value}):
                self.assertEqual(llm.token_budget(), 0)
                llm.check_budget("showrunner")              # must not raise

    def test_under_budget_passes(self):
        self._spend(10_000)
        with patch.dict(os.environ, {"CLAUDE_TOKEN_BUDGET": "1000000"}), \
                patch.object(llm, "_ACTIVE_BACKEND", ["subscription"]):
            llm.check_budget("scene review")                # must not raise

    def test_a_spent_budget_refuses_the_next_call(self):
        self._spend(1_500_000)
        with patch.dict(os.environ, {"CLAUDE_TOKEN_BUDGET": "1000000"}), \
                patch.object(llm, "_ACTIVE_BACKEND", ["subscription"]):
            with self.assertRaises(llm.BudgetExceeded) as caught:
                llm.check_budget("set builder")
        self.assertIn("set builder", str(caught.exception))
        self.assertIn("1,500,000", str(caught.exception))

    def test_the_codex_backend_is_not_limited_by_the_claude_budget(self):
        self._spend(10 ** 9)
        with patch.dict(os.environ, {"CLAUDE_TOKEN_BUDGET": "1000"}), \
                patch.object(llm, "_ACTIVE_BACKEND", ["codex"]):
            llm.check_budget("set builder")                 # Codex has its own quota

    def test_the_set_builder_agent_refuses_to_start_over_budget(self):
        """The costliest call in the pipeline must not even copy the repo once the budget is gone."""
        self._spend(10 ** 9)
        with patch.dict(os.environ, {"CLAUDE_TOKEN_BUDGET": "1000"}), \
                patch.object(llm, "_ACTIVE_BACKEND", ["subscription"]):
            with self.assertRaises(llm.BudgetExceeded):
                set_builder.claude_agent("fix the set", ["engine/sets/does_not_matter.py"])

    def test_autopilot_treats_a_spent_budget_as_a_stop_not_a_retry(self):
        self.assertTrue(autopilot._is_budget(llm.BudgetExceeded("spent")))
        self.assertFalse(autopilot._is_budget(RuntimeError("Blender died")))
        self.assertFalse(autopilot._is_budget(llm.UsageLimit("limit resets 3am")))

    def test_a_spent_budget_is_not_mistaken_for_a_usage_limit_reset(self):
        """is_usage_limit must not match the budget message, or the autopilot would sleep on it."""
        spent = llm.BudgetExceeded(
            "CLAUDE_TOKEN_BUDGET reached before the set builder call: 1,500,000 of 1,000,000 tokens "
            "used by 12 call(s).")
        self.assertFalse(llm.is_usage_limit(spent))


class BatchedRepairTests(unittest.TestCase):
    """A whole-film review hands fix_scenes every rejected window at once; the turn stays bounded."""

    def _rejected(self, n):
        return [{"window": i, "beat": i, "action": f"act{i}", "t0": i, "t1": i + 3,
                 "fatal_problems": ["broken"] if i % 2 else [], "problems": [], "fix": "",
                 "average_score": 10 - i, "images": [f"w{i}_a.jpg", f"w{i}_b.jpg", f"w{i}_c.jpg"]}
                for i in range(1, n + 1)]

    def _capture(self, rejected, cap):
        seen = {}

        def agent(prompt, allowed, **kw):
            seen["prompt"] = prompt
            return "fixed"

        with patch.dict(os.environ, {"SCENE_FIX_MAX_WINDOWS": cap}), \
                patch.object(set_builder, "claude_agent", agent), \
                patch.object(set_builder, "_content_hashes", lambda p: {}), \
                patch.object(set_builder, "_require_changed", lambda *a: None):
            set_builder.fix_scenes("some_set", rejected)
        return seen["prompt"]

    def test_all_rejected_windows_reach_one_turn_when_under_the_cap(self):
        prompt = self._capture(self._rejected(4), "6")
        for i in range(1, 5):
            self.assertIn(f"window {i} ", prompt)
        self.assertNotIn("ALSO rejected", prompt)

    def test_over_the_cap_the_worst_are_detailed_and_the_rest_named(self):
        prompt = self._capture(self._rejected(10), "3")
        detailed = [i for i in range(1, 11) if f"window {i} (" in prompt]
        self.assertEqual(len(detailed), 3)
        # fatal first, then lowest score: windows 9, 7, 5 are fatal with the worst scores
        self.assertEqual(detailed, [5, 7, 9])
        self.assertIn("ALSO rejected", prompt)
        self.assertIn("frames: ", prompt)

    def test_a_zero_or_negative_cap_still_sends_at_least_one_window(self):
        for cap in ("0", "-3"):
            with self.subTest(cap=cap):
                prompt = self._capture(self._rejected(5), cap)
                self.assertEqual(len([i for i in range(1, 6) if f"window {i} (" in prompt]), 1)

    def test_a_misconfigured_cap_falls_back_instead_of_breaking_the_repair(self):
        prompt = self._capture(self._rejected(10), "nonsense")
        self.assertEqual(len([i for i in range(1, 11) if f"window {i} (" in prompt]), 6)


if __name__ == "__main__":
    unittest.main()
