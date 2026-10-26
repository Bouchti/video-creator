"""Small, subscription-authenticated wrapper around ``codex exec``.

The Codex CLI has a substantial fixed prompt cost, so callers should batch related work instead
of using this module for tiny requests.  API credentials are removed from the child environment;
authentication comes from ``codex login`` (ChatGPT plan usage).
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


OPENAI_API_ENV = ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_ORG_ID", "OPENAI_PROJECT_ID")
TOTAL_USAGE = {"calls": 0, "input_tokens": 0, "cached_input_tokens": 0,
               "output_tokens": 0, "reasoning_output_tokens": 0}
log = logging.getLogger("pipeline")


def _effort(requested: str, cap_env: str = "SHOWRUNNER_CODEX_EFFORT_CAP") -> str:
    """Cap expensive reasoning while preserving an explicit lower setting."""
    order = ("low", "medium", "high", "xhigh", "max")
    requested = requested if requested in order else "medium"
    cap = (os.getenv(cap_env) or os.getenv("SHOWRUNNER_CODEX_EFFORT_CAP") or "medium").strip().lower()
    if cap not in order:
        cap = "medium"
    return order[min(order.index(requested), order.index(cap))]


def _usage(stdout: str) -> dict:
    usage = {}
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "turn.completed":
            usage = event.get("usage") or {}
    TOTAL_USAGE["calls"] += 1
    for key in TOTAL_USAGE:
        if key != "calls":
            TOTAL_USAGE[key] += int(usage.get(key) or 0)
    return usage


def run(prompt: str, *, schema: dict | None = None, effort: str = "medium", web: bool = False,
        images: list[str] | None = None, cwd: str | None = None, sandbox: str = "read-only",
        model: str | None = None, timeout: int = 1800,
        effort_cap_env: str = "SHOWRUNNER_CODEX_EFFORT_CAP") -> tuple[object, dict]:
    """Run one ephemeral Codex turn and return ``(last_message, token_usage)``."""
    exe = shutil.which("codex")
    if not exe:
        raise RuntimeError("Codex CLI not found; install it and run `codex login`")
    model = model or os.getenv("SHOWRUNNER_CODEX_MODEL") or "gpt-5.6-sol"
    env = {k: v for k, v in os.environ.items() if k not in OPENAI_API_ENV}
    with tempfile.TemporaryDirectory(prefix="video_creator_codex_") as tmp:
        answer = os.path.join(tmp, "answer.txt")
        cmd = [exe, "--ask-for-approval", "never"]
        if web:
            cmd.append("--search")
        cmd += ["exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
                "--skip-git-repo-check", "--sandbox", sandbox, "--model", model,
                "-c", f'model_reasoning_effort="{_effort(effort, effort_cap_env)}"', "--json",
                "--output-last-message", answer]
        if schema is not None:
            schema_path = os.path.join(tmp, "schema.json")
            Path(schema_path).write_text(json.dumps(schema), encoding="utf-8")
            cmd += ["--output-schema", schema_path]
        for path in images or []:
            cmd += ["--image", os.path.abspath(path)]
        cmd.append("-")
        result = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                                cwd=cwd or tmp, env=env, timeout=timeout)
        usage = _usage(result.stdout)
        if usage:
            log.info("[codex] usage: %s input (%s cached), %s output, %s reasoning",
                     f"{int(usage.get('input_tokens') or 0):,}",
                     f"{int(usage.get('cached_input_tokens') or 0):,}",
                     f"{int(usage.get('output_tokens') or 0):,}",
                     f"{int(usage.get('reasoning_output_tokens') or 0):,}")
        combined = (result.stderr or "") + "\n" + (result.stdout or "")
        if result.returncode:
            raise RuntimeError(f"codex exec failed (exit {result.returncode}): {combined[-800:]}")
        if not os.path.exists(answer):
            raise RuntimeError(f"codex exec returned no final answer: {combined[-800:]}")
        text = Path(answer).read_text(encoding="utf-8").strip()
    if schema is None:
        return text, usage
    try:
        return json.loads(text), usage
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Codex returned invalid structured output: {text[-500:]}") from exc


def usage_summary() -> str:
    u = TOTAL_USAGE
    return (f"{u['calls']} call(s), {u['input_tokens']:,} input tokens "
            f"({u['cached_input_tokens']:,} cached), {u['output_tokens']:,} output tokens")
