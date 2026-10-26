import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from agents import codex_cli, scene_validator as sv, set_builder, showrunner


class CodexCliTests(unittest.TestCase):
    def test_structured_turn_uses_chatgpt_login_path_and_reports_usage(self):
        seen = {}

        def fake_run(cmd, **kwargs):
            seen.update(cmd=cmd, env=kwargs["env"])
            answer = cmd[cmd.index("--output-last-message") + 1]
            with open(answer, "w", encoding="utf-8") as fh:
                json.dump({"ok": True}, fh)
            stdout = json.dumps({"type": "turn.completed", "usage": {
                "input_tokens": 100, "cached_input_tokens": 25, "output_tokens": 5,
                "reasoning_output_tokens": 2}})
            return subprocess.CompletedProcess(cmd, 0, stdout, "")

        schema = {"type": "object", "properties": {"ok": {"type": "boolean"}},
                  "required": ["ok"], "additionalProperties": False}
        with patch.object(codex_cli.shutil, "which", return_value="codex"), \
                patch.object(codex_cli.subprocess, "run", side_effect=fake_run), \
                patch.dict(os.environ, {"OPENAI_API_KEY": "must-not-leak"}):
            out, usage = codex_cli.run("test", schema=schema, effort="high")
        self.assertEqual(out, {"ok": True})
        self.assertEqual(usage["input_tokens"], 100)
        self.assertNotIn("OPENAI_API_KEY", seen["env"])
        self.assertIn("--ignore-user-config", seen["cmd"])
        self.assertIn('model_reasoning_effort="medium"', seen["cmd"])

    def test_showrunner_dispatches_to_codex(self):
        with patch.object(showrunner, "BACKEND", "codex"), patch.object(showrunner, "_ACTIVE_BACKEND", [None]), \
                patch.object(showrunner, "_call_codex", return_value={"x": 1}) as call:
            self.assertEqual(showrunner._call_once("s", "p", {"type": "object"}), {"x": 1})
        call.assert_called_once()

    def test_usage_limit_switches_remaining_calls_to_claude_subscription(self):
        with patch.object(showrunner, "BACKEND", "codex"), patch.object(showrunner, "_ACTIVE_BACKEND", [None]), \
                patch.dict(os.environ, {"SHOWRUNNER_FALLBACK_BACKEND": "subscription"}), \
                patch.object(showrunner, "_call_codex", side_effect=showrunner.UsageLimit("usage limit")) as codex, \
                patch.object(showrunner, "_call_cli", return_value={"ok": True}) as claude:
            self.assertEqual(showrunner._call("s", "p", {"type": "object"}), {"ok": True})
            self.assertEqual(showrunner.active_backend(), "subscription")
            self.assertEqual(showrunner._call_once("s2", "p2"), {"ok": True})
        self.assertEqual(codex.call_count, 1)
        self.assertEqual(claude.call_count, 2)


class CodexVisionTests(unittest.TestCase):
    def test_batch_review_returns_each_window(self):
        good = {"visual_match": 8, "readability": 8, "image_quality": 8, "continuity": 8,
                "fatal_problems": [], "problems": [], "fix": ""}
        windows = [({"window": n, "beat": n, "action": "a", "part": "whole", "t0": 0, "t1": 1,
                     "shows": "thing", "text": "words"}, [("start", f"{n}.jpg")]) for n in (1, 2)]
        with patch.object(sv, "_review_codex", return_value={"reviews": [
                {"window": 1, **good}, {"window": 2, **good}]}) as review:
            result = sv.review_batch(windows, "subject")
        self.assertEqual(set(result), {1, 2})
        self.assertTrue(result[1]["valid"])
        review.assert_called_once()

    def test_claude_subscription_uses_the_same_batch_path(self):
        good = {"visual_match": 8, "readability": 8, "image_quality": 8, "continuity": 8,
                "fatal_problems": [], "problems": [], "fix": ""}
        windows = [({"window": 1, "beat": 1, "action": "a", "part": "whole", "t0": 0, "t1": 1,
                     "shows": "thing", "text": "words"}, [("start", "1.jpg")])]
        with patch.object(sv, "_backend", return_value="subscription"), \
                patch.object(sv, "_review_cli", return_value={"reviews": [
                    {"window": 1, **good}]}) as review:
            result = sv.review_batch(windows, "subject")
        self.assertTrue(result[1]["valid"])
        self.assertIs(review.call_args.args[2], sv.BATCH_REVIEW_SCHEMA)

    def test_vision_usage_limit_falls_back_without_rejecting_the_scene(self):
        good = {"visual_match": 8, "readability": 8, "image_quality": 8, "continuity": 8,
                "fatal_problems": [], "problems": [], "fix": ""}
        windows = [({"window": 1, "beat": 1, "action": "a", "part": "whole", "t0": 0, "t1": 1,
                     "shows": "thing", "text": "words"}, [("start", "1.jpg")])]
        with patch.object(showrunner, "BACKEND", "codex"), patch.object(showrunner, "_ACTIVE_BACKEND", [None]), \
                patch.dict(os.environ, {"SHOWRUNNER_FALLBACK_BACKEND": "subscription",
                                        "SCENE_REVIEW_BACKEND": ""}), \
                patch.object(sv, "_review_codex", side_effect=showrunner.UsageLimit("usage limit")), \
                patch.object(sv, "_review_cli", return_value={"reviews": [{"window": 1, **good}]}) as claude:
            result = sv.review_batch(windows, "subject")
        self.assertTrue(result[1]["valid"])
        claude.assert_called_once()


class ClaudeParityTests(unittest.TestCase):
    def test_effort_is_capped_and_usage_is_accumulated(self):
        self.assertEqual(showrunner._capped_effort("high"), "medium")
        before = dict(showrunner.CLAUDE_USAGE)
        data = {"usage": {"input_tokens": 100, "cache_read_input_tokens": 80,
                          "cache_creation_input_tokens": 10, "output_tokens": 5}}
        showrunner._record_claude_usage(data, "test")
        self.assertEqual(showrunner.CLAUDE_USAGE["calls"], before["calls"] + 1)
        self.assertEqual(showrunner.CLAUDE_USAGE["cache_read_input_tokens"],
                         before["cache_read_input_tokens"] + 80)


class IsolatedBuilderTests(unittest.TestCase):
    def test_agent_copies_back_only_allowed_files(self):
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, "engine", "sets"))
        allowed = os.path.join(root, "engine", "sets", "new.py")
        readme = os.path.join(root, "README.md")
        with open(allowed, "w", encoding="utf-8") as fh:
            fh.write("old")
        with open(readme, "w", encoding="utf-8") as fh:
            fh.write("keep")

        def fake_agent(prompt, **kwargs):
            with open(os.path.join(kwargs["cwd"], "engine", "sets", "new.py"), "w", encoding="utf-8") as fh:
                fh.write("new")
            with open(os.path.join(kwargs["cwd"], "README.md"), "w", encoding="utf-8") as fh:
                fh.write("agent changed this")
            return "done", {}

        with patch.object(set_builder, "PROJECT_ROOT", root), patch.object(showrunner, "BACKEND", "codex"), \
                patch.object(showrunner, "_ACTIVE_BACKEND", [None]), \
                patch("agents.codex_cli.run", side_effect=fake_agent):
            set_builder.claude_agent("work", ["engine/sets/new.py"])
        self.assertEqual(open(allowed, encoding="utf-8").read(), "new")
        self.assertEqual(open(readme, encoding="utf-8").read(), "keep")


if __name__ == "__main__":
    unittest.main()
