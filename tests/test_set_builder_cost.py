"""Set building must never silently spend the Claude subscription (one design used ~12M tokens)."""
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from agents import set_builder as sb
from agents import showrunner

FAKE_AGENT = r'''
import json, sys, time
sys.stdin.read()
for k in range(50):
    print(json.dumps({"type": "assistant", "message": {"id": f"m{k}", "content": [
        {"type": "tool_use", "name": "Read", "input": {"file_path": "engine/x.py"}}],
        "usage": {"input_tokens": 10, "cache_read_input_tokens": 100000, "cache_creation_input_tokens": 0,
                  "output_tokens": 500}}}), flush=True)
    time.sleep(0.05)
print(json.dumps({"type": "result", "result": "done", "is_error": False}), flush=True)
'''


class CostTests(unittest.TestCase):
    def _fake(self, d):
        path = os.path.join(d, "fake_agent.py")
        open(path, "w").write(FAKE_AGENT)
        return [sys.executable, path]

    def test_an_agent_is_killed_when_it_passes_its_token_cap(self):
        with tempfile.TemporaryDirectory() as d:
            result, _tail, spent, stopped = sb._run_claude_streaming(self._fake(d), "go", d, dict(os.environ), 60,
                                                                     cap_tokens=350_000)
        self.assertTrue(stopped)
        self.assertIsNone(result)
        self.assertLess(sum(spent.values()), 600_000)          # stopped after ~4 steps, not 50

    def test_without_a_cap_the_agent_finishes(self):
        with tempfile.TemporaryDirectory() as d:
            result, _tail, spent, stopped = sb._run_claude_streaming(self._fake(d), "go", d, dict(os.environ), 60)
        self.assertFalse(stopped)
        self.assertEqual(result["result"], "done")
        self.assertEqual(spent["cache_read_input_tokens"], 5_000_000)

    def test_the_call_cap_never_exceeds_what_is_left_of_the_run_budget(self):
        with patch.dict(os.environ, {"CLAUDE_TOKEN_BUDGET": "1500000", "SET_BUILDER_CALL_TOKENS": "3000000"}), \
                patch.object(showrunner, "tokens_used", return_value=1_200_000):
            self.assertEqual(sb._call_token_cap(), 300_000)

    def test_codex_out_of_quota_stops_instead_of_using_claude(self):
        files = ["engine/sets/demo_story_spec.py", "engine/sets/demo_story.py", "engine/films/demo_story.json"]
        with patch.object(showrunner, "BACKEND", "codex"), patch.object(showrunner, "_ACTIVE_BACKEND", [None]), \
                patch.dict(os.environ, {"SET_BUILDER_CLAUDE_FALLBACK": "0",
                                        "SHOWRUNNER_FALLBACK_BACKEND": "subscription"}), \
                patch("agents.codex_cli.run", side_effect=RuntimeError(
                    "codex exec failed (exit 1): You've hit your usage limit. Visit settings/usage to purchase "
                    "more credits or try again at 9:00")), \
                patch.object(sb, "_run_claude_streaming") as claude:
            with self.assertRaises(showrunner.UsageLimit) as ctx:
                sb.claude_agent("design", files)
        claude.assert_not_called()
        self.assertIn("SET_BUILDER_CLAUDE_FALLBACK", str(ctx.exception))
        self.assertEqual(showrunner.active_backend(), "codex")          # nothing else was switched either



class ResetParsingTests(unittest.TestCase):
    def test_codex_and_claude_reset_wording(self):
        import datetime as dt
        now = dt.datetime.now()
        r = showrunner.parse_reset("You've hit your usage limit. ... purchase more credits or try again in 2 hours 30 minutes.")
        self.assertAlmostEqual((r - now).total_seconds(), 9000, delta=5)
        r = showrunner.parse_reset("try again at Oct 29th, 2026 9:41 AM.")
        self.assertEqual((r.year, r.month, r.day, r.hour, r.minute), (2026, 10, 29, 9, 41))
        r = showrunner.parse_reset("usage limit reached; resets 3pm")
        self.assertEqual((r.hour, r.minute), (15, 0))
        self.assertIsNone(showrunner.parse_reset("codex exec failed (exit 1): stream disconnected"))
        self.assertIsNotNone(showrunner.UsageLimit("Codex is out of quota (... try again at 9:41 PM)").reset)

class PromptSizeTests(unittest.TestCase):
    """Every step of an agent re-sends its whole context: the prompt must carry a compact API reference,
    never send the agent off to read the engine (that made one set design cost 11M tokens)."""

    def test_the_design_prompt_is_small_and_self_contained(self):
        p = sb.story_design_prompt("a dam", "demo_story")
        self.assertLess(len(p), 45_000)                                   # ~12k tokens, all included
        for name in ("close_on(", "class Reservoir", ".empty(", "key_sky(", "class Character", ".point(",
                     "label(", "class CameraRig"):
            self.assertIn(name, p)
        self.assertNotIn("read these files first", p)

    def test_fix_prompts_point_to_line_ranges(self):
        f = sb.fix_prompt("pumped_storage_mountain_batt_story", "- beat 3: label cut", "The reviewer rejected:")
        self.assertIn("PumpedStorageMountainBattStorySet.a_tunnel: lines", f)
        self.assertLess(len(f), 45_000)


if __name__ == "__main__":
    unittest.main()
