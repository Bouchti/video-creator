"""
The only way this project talks to Claude: Claude Code's headless mode (`claude -p`)
on the user's claude.ai subscription. There is deliberately no Anthropic API path.

API credentials are stripped from the child environment, so a stray ANTHROPIC_API_KEY
in .env or the shell can never switch billing to the API. Each call runs in an empty
temp dir with no project settings, no MCP servers, and only the tools it needs:
Read for images, WebSearch/WebFetch when asked.
"""
import json
import logging
import os
import shutil
import subprocess
import tempfile

from config.paths import CLAUDE_MODEL

log = logging.getLogger("pipeline")

# Variables that would make Claude Code bill an API account instead of the subscription.
API_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "CLAUDE_CODE_USE_BEDROCK",
           "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY")

_notional_usd = [0.0]


class ClaudeError(RuntimeError):
    pass


def executable():
    return shutil.which("claude")


def available() -> bool:
    return executable() is not None


def notional_cost() -> float:
    """What this process's calls would have cost on the API (they are billed to the subscription)."""
    return _notional_usd[0]


def subscription_env(environ=None) -> dict:
    return {k: v for k, v in (environ if environ is not None else os.environ).items() if k not in API_ENV}


def ask(system: str, prompt: str, schema: dict = None, *, model: str = None, effort: str = None,
        web: bool = False, images=(), timeout: int = 1800):
    """One Claude call on the subscription. Returns parsed JSON when `schema` is given, else text.

    `images` is a sequence of (label, path) pairs; they are copied next to the call and listed
    in the prompt for Claude to open with its Read tool.
    """
    exe = executable()
    if not exe:
        raise ClaudeError("Claude Code CLI not found: install it and run `claude` once to log in "
                          "with your claude.ai subscription")
    tools = []
    if images:
        tools.append("Read")
    if web:
        tools += ["WebSearch", "WebFetch"]
    with tempfile.TemporaryDirectory() as tmp:
        sys_file = os.path.join(tmp, "system.txt")
        with open(sys_file, "w", encoding="utf-8") as f:
            f.write(system or "")
        if images:
            listed = []
            for i, (label, path) in enumerate(images):
                name = f"image_{i:02d}{os.path.splitext(str(path))[1].lower() or '.jpg'}"
                shutil.copyfile(path, os.path.join(tmp, name))
                listed.append(f"- {name}: {label}")
            prompt = ("Open each of these image files with the Read tool before answering:\n"
                      + "\n".join(listed) + "\n\n" + prompt)
        cmd = [exe, "-p", "--output-format", "json", "--model", model or CLAUDE_MODEL,
               "--system-prompt-file", sys_file, "--no-session-persistence", "--strict-mcp-config",
               "--setting-sources", "", "--tools", *(tools or [""])]
        if tools:
            cmd += ["--allowedTools", *tools]
        if effort:
            cmd += ["--effort", effort]
        if schema is not None:
            cmd += ["--json-schema", json.dumps(schema)]
        try:
            r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                               cwd=tmp, env=subscription_env(), timeout=timeout)
        except subprocess.TimeoutExpired as e:
            raise ClaudeError(f"claude -p timed out after {timeout}s") from e
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise ClaudeError(f"claude -p failed (exit {r.returncode}): {(r.stderr or r.stdout)[-400:]}")
    if data.get("is_error") or data.get("subtype") != "success":
        raise ClaudeError(f"claude -p error ({data.get('subtype')}): {str(data.get('result'))[:300]}")
    _notional_usd[0] += float(data.get("total_cost_usd") or 0)
    if schema is not None:
        out = data.get("structured_output")
        return out if out is not None else json.loads(data["result"])
    return (data.get("result") or "").strip()
