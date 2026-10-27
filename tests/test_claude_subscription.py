import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents import claude_cli

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ("agents", "local_video", "engine", "config")
API_PATTERNS = re.compile(r"^\s*(import anthropic|from anthropic\b)|messages\.create\(|api\.anthropic\.com", re.M)


class NoDirectApiTests(unittest.TestCase):
    def test_no_module_calls_the_anthropic_api(self):
        offenders = []
        files = [ROOT / "main.py"] + [p for d in SOURCE_DIRS for p in (ROOT / d).rglob("*.py")]
        for path in files:
            if API_PATTERNS.search(path.read_text(encoding="utf-8", errors="replace")):
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual([], offenders, "Claude must only be reached through agents/claude_cli.py (subscription)")

    def test_anthropic_sdk_is_not_a_dependency(self):
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower().split()
        self.assertNotIn("anthropic", requirements)


class _Completed:
    def __init__(self, payload):
        self.stdout = json.dumps(payload)
        self.stderr = ""
        self.returncode = 0


class ClaudeCliTests(unittest.TestCase):
    def _run(self, payload, **kwargs):
        seen = {}

        def fake_run(cmd, input, cwd, env, **_):
            seen.update(cmd=cmd, prompt=input, env=env, files=sorted(os.listdir(cwd)))
            return _Completed(payload)

        with patch.object(claude_cli, "executable", return_value="claude"), \
                patch.object(claude_cli.subprocess, "run", side_effect=fake_run), \
                patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-should-never-be-used",
                                        "ANTHROPIC_BASE_URL": "https://example.invalid"}):
            result = claude_cli.ask("system", "prompt", **kwargs)
        return result, seen

    def test_api_credentials_never_reach_claude_code(self):
        _, seen = self._run({"subtype": "success", "result": "hello"})
        for name in claude_cli.API_ENV:
            self.assertNotIn(name, seen["env"])
        self.assertIn("-p", seen["cmd"])

    def test_structured_output_is_returned_as_json(self):
        schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
        result, seen = self._run({"subtype": "success", "result": "", "structured_output": {"ok": True}},
                                 schema=schema)
        self.assertEqual({"ok": True}, result)
        self.assertEqual(json.dumps(schema), seen["cmd"][seen["cmd"].index("--json-schema") + 1])

    def test_images_are_copied_and_only_read_is_allowed(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "frame.jpg"
            image.write_bytes(b"jpeg")
            _, seen = self._run({"subtype": "success", "result": "fox"}, images=[("Frame 1", image)])
        self.assertIn("image_00.jpg", seen["files"])
        self.assertIn("image_00.jpg: Frame 1", seen["prompt"])
        tools = seen["cmd"][seen["cmd"].index("--tools") + 1]
        self.assertEqual("Read", tools)

    def test_errors_are_raised(self):
        with self.assertRaises(claude_cli.ClaudeError):
            self._run({"subtype": "error_max_turns", "is_error": True, "result": "limit"})


if __name__ == "__main__":
    unittest.main()
