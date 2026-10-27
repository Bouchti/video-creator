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
_PREFERRED_MODELS: dict[str, str] = {}


def _capacity_error(exc: object) -> bool:
    text = str(exc).lower()
    return any(phrase in text for phrase in (
        "model is at capacity", "model at capacity", "selected model is at capacity",
        "server is overloaded", "service is overloaded", "try a different model",
    ))


def _unsupported_model_error(exc: object) -> bool:
    text = str(exc).lower()
    return "model" in text and any(phrase in text for phrase in (
        "not found", "does not exist", "unsupported", "unknown model", "invalid model",
    ))


def _model_fallbacks(primary: str) -> list[str]:
    raw = os.getenv("SHOWRUNNER_CODEX_FALLBACK_MODELS", "")
    return [m for m in dict.fromkeys(x.strip() for x in raw.split(",")) if m and m != primary]


def strict_schema(value):
    """Return a Codex-compatible strict copy of a Claude-style JSON schema."""
    if isinstance(value, list):
        return [strict_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: strict_schema(item) for key, item in value.items()}
    properties = result.get("properties")
    if result.get("type") == "object" or isinstance(properties, dict):
        properties = properties or {}
        result["properties"] = properties
        result["required"] = list(properties)
        result["additionalProperties"] = False
    return result


def _effort(requested: str, cap_env: str = "SHOWRUNNER_CODEX_EFFORT_CAP") -> str:
    """Cap expensive reasoning while preserving an explicit lower setting."""
    order = ("low", "medium", "high", "xhigh", "max")
    requested = requested if requested in order else "medium"
    cap = (os.getenv(cap_env) or os.getenv("SHOWRUNNER_CODEX_EFFORT_CAP") or "medium").strip().lower()
    if cap not in order:
        cap = "medium"
    return order[min(order.index(requested), order.index(cap))]


def _failure(stdout: str, stderr: str) -> str:
    """Why a codex exec run failed, from its structured error events (never from the raw tail of
    stdout: that is usually a file the agent was reading, and its words must not be mistaken for a
    usage-limit or capacity message)."""
    reasons = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item") or {}
        if event.get("type") in ("error", "turn.failed") or item.get("type") == "error":
            err = event.get("error") or item or event
            msg = err.get("message") if isinstance(err, dict) else str(err)
            reasons.append(str(msg or json.dumps(event))[:400])
    errors = [ln for ln in (stderr or "").splitlines() if "ERROR" in ln or "error:" in ln.lower()]
    text = " | ".join(dict.fromkeys(reasons)) or " | ".join(errors[-3:]) or (stderr or "").strip()[-400:]
    return text or "no error event (see the agent's last message)"


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


def _grant_current_user(path: str) -> None:
    """The elevated Windows sandbox writes files as a separate sandbox user and rewrites the workspace
    ACL without us: grant ourselves inherited full control first, or we cannot read what it wrote."""
    user = os.getenv("USERNAME") or ""
    if os.getenv("USERDOMAIN"):
        user = f"{os.environ['USERDOMAIN']}\\{user}"
    result = subprocess.run(["icacls", path, "/grant", f"{user}:(OI)(CI)F"], capture_output=True)
    if result.returncode:
        log.warning("[codex] could not grant %s access to %s (icacls exit %s)", user, path, result.returncode)


def run(prompt: str, *, schema: dict | None = None, effort: str = "medium", web: bool = False,
        images: list[str] | None = None, cwd: str | None = None, sandbox: str = "read-only",
        model: str | None = None, timeout: int = 1800,
        effort_cap_env: str = "SHOWRUNNER_CODEX_EFFORT_CAP",
        _allow_model_fallback: bool = True) -> tuple[object, dict]:
    """Run one ephemeral Codex turn and return ``(last_message, token_usage)``."""
    exe = shutil.which("codex")
    if not exe:
        raise RuntimeError("Codex CLI not found; install it and run `codex login`")
    primary = model or os.getenv("SHOWRUNNER_CODEX_MODEL") or "gpt-5.6-sol"
    model = _PREFERRED_MODELS.get(primary, primary)
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
        if cwd:
            # On Windows, subprocess.cwd alone does not reliably establish the writable sandbox
            # root. Explicit -C keeps isolated coding-agent workspaces writable.
            cmd += ["-C", os.path.abspath(cwd)]
        if os.name == "nt" and sandbox != "read-only":
            # The default (unelevated) Windows sandbox denies every write, even inside the workspace:
            # patches are rejected and the agent ends with "the workspace is read-only".
            cmd += ["-c", f'windows.sandbox="{os.getenv("CODEX_WINDOWS_SANDBOX", "elevated")}"']
            if cwd:
                _grant_current_user(os.path.abspath(cwd))
        if schema is not None:
            schema_path = os.path.join(tmp, "schema.json")
            Path(schema_path).write_text(json.dumps(strict_schema(schema)), encoding="utf-8")
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
        if result.returncode:
            error = RuntimeError(f"codex exec failed (exit {result.returncode}): "
                                 f"{_failure(result.stdout or '', result.stderr or '')[-800:]}")
            if _allow_model_fallback and (_capacity_error(error) or _unsupported_model_error(error)):
                last_error = error
                for alternate in _model_fallbacks(primary):
                    if alternate == model:
                        continue
                    log.warning("[codex] model %s unavailable; retrying this call with %s", model, alternate)
                    try:
                        value = run(prompt, schema=schema, effort=effort, web=web, images=images,
                                    cwd=cwd, sandbox=sandbox, model=alternate, timeout=timeout,
                                    effort_cap_env=effort_cap_env, _allow_model_fallback=False)
                        _PREFERRED_MODELS[primary] = alternate
                        return value
                    except RuntimeError as alternate_error:
                        last_error = alternate_error
                        if not (_capacity_error(alternate_error) or _unsupported_model_error(alternate_error)):
                            raise
                raise last_error
            raise error
        if not os.path.exists(answer):
            raise RuntimeError(f"codex exec returned no final answer: "
                               f"{_failure(result.stdout or '', result.stderr or '')[-800:]}")
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
