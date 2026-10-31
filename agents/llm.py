"""
The only way this project talks to an AI model: Claude Code's headless mode (`claude -p`) on the claude.ai
subscription, or `codex exec` on the ChatGPT plan (agents/codex_cli.py). There is deliberately no API path:
API credentials are stripped from every child environment, so a stray key can never switch billing.

    out = llm.ask(system, prompt, schema, effort="medium", web=False, images=())

One process-wide backend: SHOWRUNNER_BACKEND (subscription | codex) serves every call until it hits a usage
limit, then the whole process moves to SHOWRUNNER_FALLBACK_BACKEND. Claude calls are metered against
CLAUDE_TOKEN_BUDGET (checked before each call). Text turns wait for a near reset (SHOWRUNNER_MAX_WAIT
minutes); image reviews never block, their callers handle UsageLimit.
"""
import datetime
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading

from dotenv import load_dotenv

from config.paths import get_env_path

load_dotenv(get_env_path())
log = logging.getLogger("pipeline")

BACKEND = os.getenv("SHOWRUNNER_BACKEND", "subscription").strip().lower()
CLI_MODEL = os.getenv("SHOWRUNNER_CLI_MODEL", "opus")
CODEX_MODEL = os.getenv("SHOWRUNNER_CODEX_MODEL", "gpt-5.6-sol")

# Variables that would make Claude Code bill an API account instead of the subscription.
API_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "CLAUDE_CODE_USE_BEDROCK",
           "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY")

CLAUDE_USAGE = {"calls": 0, "input_tokens": 0, "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0, "output_tokens": 0}
_ACTIVE_BACKEND = [None]
_PRIMARY_RESET = [None]                # when the primary backend's usage limit lifts (from its error text)
_BACKEND_LOCK = threading.Lock()
_CARRIED = [0]                         # tokens an interrupted run already spent before this process resumed it
_COST = [0.0]                          # API-equivalent USD the CLI reports (informative: the subscription pays)


class UsageLimit(RuntimeError):
    """A subscription backend hit its session/usage limit."""

    def __init__(self, msg):
        super().__init__(msg)
        self.reset = parse_reset(msg)


class BudgetExceeded(RuntimeError):
    """The CLAUDE_TOKEN_BUDGET for this process is spent; retrying cannot help."""


# ------------------- backend selection -------------------

def claude_available() -> bool:
    return shutil.which("claude") is not None


def available() -> bool:
    """Whether the backend currently serving this process can be invoked."""
    return shutil.which("codex") is not None if active_backend() == "codex" else claude_available()


_LIMIT_LOADED = [False]


def _limit_file():
    """Where a usage limit is remembered between processes (SHOWRUNNER_LIMIT_MEMORY=0 turns it off)."""
    if os.getenv("SHOWRUNNER_LIMIT_MEMORY", "1").strip() == "0":
        return None
    from config.paths import get_output_dir
    return os.path.join(os.path.dirname(get_output_dir()), "logs", ".ai_backend_limit.json")


def _restore_limit():
    """Start on the fallback while the primary's last usage limit has not lifted.

    Every new process used to try the exhausted Codex first: ~40 s lost per run and per resume, and a
    local-ai run has a one-hour budget. An unknown reset time is trusted for one hour.
    """
    path = _limit_file()
    if not path or not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as stream:
            state = json.load(stream)
        written = float(state.get("written") or 0)
        until = (datetime.datetime.fromisoformat(state["until"]) if state.get("until")
                 else datetime.datetime.fromtimestamp(written + 3600))
    except (OSError, ValueError, KeyError, TypeError):
        return
    fallback = state.get("fallback")
    if (state.get("backend") == BACKEND and fallback in ("codex", "subscription") and fallback != BACKEND
            and datetime.datetime.now() < until):
        _ACTIVE_BACKEND[0] = fallback
        _PRIMARY_RESET[0] = until
        log.info("[llm] %s is still at its usage limit (until %s); using %s", BACKEND,
                 until.strftime("%Y-%m-%d %H:%M"), fallback)


def _remember_limit(failed, fallback):
    path = _limit_file()
    if not path:
        return
    reset = _PRIMARY_RESET[0]
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as stream:
            json.dump({"backend": failed, "fallback": fallback, "until": reset.isoformat() if reset else None,
                       "written": datetime.datetime.now().timestamp()}, stream)
    except OSError:
        pass


def active_backend():
    """Backend currently serving this process; changes once after a usage limit."""
    if _ACTIVE_BACKEND[0] is None and not _LIMIT_LOADED[0]:
        _LIMIT_LOADED[0] = True
        _restore_limit()
    return _ACTIVE_BACKEND[0] or BACKEND


def activate_fallback(reason="Primary backend usage limit reached", failed_backend=None):
    """Switch this process to the configured fallback. Returns True if switched."""
    fallback = (os.getenv("SHOWRUNNER_FALLBACK_BACKEND") or "").strip().lower()
    if fallback == "claude":
        fallback = "subscription"
    current = active_backend()
    # A command-line/process override can change the primary without changing `.env`. For example,
    # SHOWRUNNER_BACKEND=subscription with an `.env` written for codex -> subscription used to make
    # the fallback point straight back at the exhausted primary. An explicitly blank value still
    # disables fallback; a same-as-primary value means use the other installed subscription model.
    if fallback == current and current in ("codex", "subscription"):
        fallback = "codex" if current == "subscription" else "subscription"
    # Another worker may already have switched the process while this request was in flight.
    if failed_backend and current != failed_backend:
        return current == fallback
    if fallback not in ("codex", "subscription") or current == fallback:
        return False
    with _BACKEND_LOCK:
        if active_backend() != current:
            return True
        _ACTIVE_BACKEND[0] = fallback
        _PRIMARY_RESET[0] = parse_reset(str(reason))
        _remember_limit(current, fallback)
        log.warning("[llm] %s; switching all remaining AI work to %s", str(reason)[:180], fallback)
    return True


def primary_reset():
    """When the backend this process fell back from becomes available again (None = unknown)."""
    return _PRIMARY_RESET[0]


def capped_effort(requested, env_name="SHOWRUNNER_CLAUDE_EFFORT_CAP", default="medium"):
    """Cap subscription reasoning so a stray high-effort call cannot consume the session."""
    order = ("low", "medium", "high", "max")
    requested = requested if requested in order else default
    cap = (os.getenv(env_name) or default).strip().lower()
    if cap not in order:
        cap = default
    return order[min(order.index(requested), order.index(cap))]


# ------------------- usage limits -------------------

def parse_reset(msg):
    """When a usage limit lifts, from Claude ("resets 3pm") or Codex ("try again at 9:41 AM",
    "try again at Oct 29th, 2026 9:41 AM", "try again in 2 days 3 hours 5 minutes"). None if unknown."""
    now = datetime.datetime.now()
    m = re.search(r"try again in\s+((?:\d+\s*(?:days?|hours?|hrs?|minutes?|mins?)[\s,and]*)+)", msg, re.I)
    if m:
        delta = datetime.timedelta()
        for n, unit in re.findall(r"(\d+)\s*(day|hour|hr|min)", m.group(1), re.I):
            delta += {"day": datetime.timedelta(days=int(n)), "hour": datetime.timedelta(hours=int(n)),
                      "hr": datetime.timedelta(hours=int(n)), "min": datetime.timedelta(minutes=int(n))}[unit.lower()]
        return now + delta if delta else None
    m = re.search(r"(?:resets|try again at)\s+(?:([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4}),?\s+)?"
                  r"([0-9]{1,2})(?::([0-9]{2}))?\s*(am|pm)", msg, re.I)
    if not m:
        return None
    h, mi = int(m.group(4)) % 12 + (12 if m.group(6).lower() == "pm" else 0), int(m.group(5) or 0)
    if m.group(1):
        try:
            day = datetime.datetime.strptime(f"{m.group(1)[:3]} {m.group(2)} {m.group(3)}", "%b %d %Y")
            return day.replace(hour=h, minute=mi)
        except ValueError:
            pass
    t = now.replace(hour=h, minute=mi, second=0, microsecond=0)
    return t if t > now else t + datetime.timedelta(days=1)


def _limit_text(text) -> bool:
    """Claude's wording for a session/usage limit."""
    text = str(text).lower()
    return "limit" in text and "reset" in text


def is_usage_limit(exc) -> bool:
    return isinstance(exc, UsageLimit) or _limit_text(exc)


def codex_unavailable(exc):
    """True when a Codex subscription call should immediately move to the fallback.

    Codex reports both quota exhaustion and transient model saturation as ordinary CLI
    failures. Neither can be repaired by repeating the same expensive pipeline stage.
    """
    from agents.codex_cli import _capacity_error
    text = str(exc).lower()
    limited = "limit" in text and any(word in text for word in ("reset", "rate", "usage", "quota", "plan"))
    return limited or _capacity_error(exc) or "temporarily unavailable" in text


def reset_wait(exc, margin=90):
    """(seconds until the limit in `exc` lifts plus a margin or None if unknown, the longest automatic wait)."""
    reset = getattr(exc, "reset", None)
    wait = (reset - datetime.datetime.now()).total_seconds() + margin if reset else None
    return wait, float(os.getenv("SHOWRUNNER_MAX_WAIT", "65")) * 60


# ------------------- Claude token budget -------------------

def record_usage(data, label="claude"):
    """Collect Claude CLI usage across every call (text, vision, set builder) and log it."""
    usage = data.get("usage") or {}
    if not usage and isinstance(data.get("modelUsage"), dict):
        rows = list(data["modelUsage"].values())
        usage = {
            "input_tokens": sum(int(r.get("inputTokens") or 0) for r in rows),
            "cache_read_input_tokens": sum(int(r.get("cacheReadInputTokens") or 0) for r in rows),
            "cache_creation_input_tokens": sum(int(r.get("cacheCreationInputTokens") or 0) for r in rows),
            "output_tokens": sum(int(r.get("outputTokens") or 0) for r in rows),
        }
    CLAUDE_USAGE["calls"] += 1
    for key in CLAUDE_USAGE:
        if key != "calls":
            CLAUDE_USAGE[key] += int(usage.get(key) or 0)
    # Always log, even when the CLI reported nothing: a silent expensive call (the set-builder agent
    # turns are the costliest in the pipeline) is how a subscription gets spent unnoticed.
    log.info("[claude] %s usage: %s input (%s cache-read, %s cache-write), %s output%s", label,
             f"{int(usage.get('input_tokens') or 0):,}",
             f"{int(usage.get('cache_read_input_tokens') or 0):,}",
             f"{int(usage.get('cache_creation_input_tokens') or 0):,}",
             f"{int(usage.get('output_tokens') or 0):,}",
             "" if usage else "  (NOT REPORTED by the CLI; this call is unmetered)")
    budget = token_budget()
    if budget:
        log.info("[claude] budget: %s / %s tokens used this run (%.0f%%)",
                 f"{tokens_used():,}", f"{budget:,}", 100.0 * tokens_used() / budget)


def usage_summary():
    u = CLAUDE_USAGE
    return (f"{u['calls']} call(s), {u['input_tokens']:,} input tokens "
            f"({u['cache_read_input_tokens']:,} cache-read, "
            f"{u['cache_creation_input_tokens']:,} cache-write), {u['output_tokens']:,} output tokens "
            f"(API-equivalent reported by the CLI: ~${_COST[0]:.2f})")


def token_budget() -> int:
    """Token ceiling for one process. 0 / unset = no ceiling."""
    try:
        return max(0, int(os.getenv("CLAUDE_TOKEN_BUDGET") or 0))
    except ValueError:
        return 0


def carry_tokens(n):
    """Count tokens spent by earlier processes of the same run (autopilot --resume) against the budget,
    so stopping and resuming a run never hands it a fresh CLAUDE_TOKEN_BUDGET."""
    _CARRIED[0] = max(0, int(n or 0))


def tokens_used() -> int:
    u = CLAUDE_USAGE
    return (_CARRIED[0] + u["input_tokens"] + u["cache_read_input_tokens"]
            + u["cache_creation_input_tokens"] + u["output_tokens"])


def check_budget(label="claude"):
    """Refuse a new Claude call once the run's budget is spent. Checked before the call so work is
    never abandoned half-done, and only for the Claude subscription (Codex has its own quota)."""
    budget = token_budget()
    if budget and active_backend() != "codex" and tokens_used() >= budget:
        raise BudgetExceeded(
            f"CLAUDE_TOKEN_BUDGET reached before the {label} call: {tokens_used():,} of {budget:,} "
            f"tokens used by {CLAUDE_USAGE['calls']} call(s). Raise CLAUDE_TOKEN_BUDGET, switch "
            f"SHOWRUNNER_BACKEND to codex, or resume the run later.")


# ------------------- Claude Code -------------------

def subscription_env(environ=None) -> dict:
    return {k: v for k, v in (environ if environ is not None else os.environ).items() if k not in API_ENV}


def claude_cmd(model, effort, tools, *, allowed=None, schema=None, system_file=None, stream=False,
               effort_cap_env="SHOWRUNNER_CLAUDE_EFFORT_CAP"):
    """A headless `claude -p` command: no session, no MCP servers, no project settings, only `tools`."""
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("Claude Code CLI not found: install it and run `claude` once to log in "
                           "with your claude.ai subscription")
    cmd = [exe, "-p", "--output-format", *(["stream-json", "--verbose"] if stream else ["json"]),
           "--model", model, "--effort", capped_effort(effort, effort_cap_env)]
    if system_file:
        cmd += ["--system-prompt-file", system_file]
    cmd += ["--no-session-persistence", "--strict-mcp-config", "--setting-sources", "",
            "--tools", *(tools or [""])]
    if allowed or tools:
        cmd += ["--allowedTools", *(allowed or tools)]
    if schema is not None:
        cmd += ["--json-schema", json.dumps(schema)]
    return cmd


def claude_result(data, label="claude", structured=False):
    """The answer in a `claude -p` result event; raises UsageLimit on a session limit."""
    result_text = str(data.get("result") or "")
    if data.get("is_error") and _limit_text(result_text):
        raise UsageLimit(result_text[:500])
    if data.get("is_error") or data.get("subtype") != "success":
        raise RuntimeError(f"claude -p error ({data.get('subtype')}): {result_text[:300]}")
    _COST[0] += float(data.get("total_cost_usd") or 0)
    record_usage(data, label)
    if structured:
        out = data.get("structured_output")
        return out if out is not None else json.loads(data["result"])
    return result_text.strip()


def _call_cli(system, prompt, schema=None, *, effort="medium", web=False, images=(), model=None,
              timeout=1800, label="claude"):
    """One Claude Code turn in an empty temp dir. Images are copied next to the call and opened with the
    Read tool; web search is the only other tool ever granted."""
    check_budget(label)
    tools = (["Read"] if images else []) + (["WebSearch", "WebFetch"] if web else [])
    with tempfile.TemporaryDirectory() as tmp:
        sys_file = None
        if system:
            sys_file = os.path.join(tmp, "system.txt")
            with open(sys_file, "w", encoding="utf-8") as f:
                f.write(system)
        if images:
            listed = []
            for i, (name_, path) in enumerate(images):
                name = f"image_{i:02d}{os.path.splitext(str(path))[1].lower() or '.jpg'}"
                shutil.copyfile(path, os.path.join(tmp, name))
                listed.append(f"- {name}: {name_}")
            prompt = ("Open each of these image files with the Read tool before answering:\n"
                      + "\n".join(listed) + "\n\n" + prompt)
        cmd = claude_cmd(model or CLI_MODEL, effort, tools, schema=schema, system_file=sys_file)
        try:
            r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                               cwd=tmp, env=subscription_env(), timeout=timeout)
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"claude -p timed out after {timeout}s") from e
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"claude -p failed (exit {r.returncode}): {(r.stderr or r.stdout)[-400:]}")
    return claude_result(data, label, structured=schema is not None)


# ------------------- Codex -------------------

def _call_codex(system, prompt, schema=None, *, effort="medium", web=False, images=(), model=None,
                timeout=1800, effort_cap_env="SHOWRUNNER_CODEX_EFFORT_CAP"):
    """One isolated Codex CLI turn authenticated by the user's ChatGPT login."""
    from agents import codex_cli

    full = "Follow the role and constraints below. Do the task directly; do not inspect or edit local files.\n\n"
    full += f"ROLE AND RULES:\n{system}\n\nTASK:\n{prompt}" if system else prompt
    if images:
        full += "\n\nAttached images, in order:\n" + "\n".join(
            f"Image {i + 1}: {label}" for i, (label, _) in enumerate(images))
    try:
        out, _ = codex_cli.run(full, schema=schema, effort=effort, web=web, images=[str(p) for _, p in images],
                               model=model or CODEX_MODEL, timeout=timeout, effort_cap_env=effort_cap_env)
        return out
    except RuntimeError as exc:
        if codex_unavailable(exc):
            raise UsageLimit(str(exc)[:500]) from exc
        raise


# ------------------- one call -------------------

def _call_once(system, prompt, schema=None, effort="medium", web=False, images=(), model=None, label="claude"):
    if images:
        # Image reviews share one profile (SCENE_REVIEW_*): a cheap model, low effort, short timeouts.
        effort = os.getenv("SCENE_REVIEW_EFFORT") or "low"
        if active_backend() == "codex":
            return _call_codex(system, prompt, schema, effort=effort, images=images, timeout=900,
                               model=os.getenv("SCENE_REVIEW_CODEX_MODEL") or CODEX_MODEL,
                               effort_cap_env="SCENE_REVIEW_CODEX_EFFORT_CAP")
        return _call_cli(system, prompt, schema, effort=effort, images=images, timeout=600, label=label,
                         model=model or os.getenv("SCENE_REVIEW_CLI_MODEL") or CLI_MODEL)
    if active_backend() == "codex":
        return _call_codex(system, prompt, schema, effort=effort, web=web)
    return _call_cli(system, prompt, schema, effort=effort, web=web, model=model, label=label)


def ask(system, prompt, schema=None, *, effort="medium", web=False, images=(), model=None, label="claude"):
    """Run one text or image turn on the active backend; JSON for `schema`, else text.

    `images` is a sequence of (label, path). `model` overrides the Claude model only. On a usage limit the
    whole process moves to the fallback backend; a text turn then waits for a near reset rather than fail.
    """
    images = [(str(name), str(path)) for name, path in images]
    backend = active_backend()
    try:
        return _call_once(system, prompt, schema, effort, web, images, model, label)
    except UsageLimit as e:
        if activate_fallback(str(e), failed_backend=backend):
            try:
                return _call_once(system, prompt, schema, effort, web, images, model, label)
            except UsageLimit as fallback_error:
                e = fallback_error
        if images:
            raise
        wait, max_wait = reset_wait(e)
        if wait is None or wait > max_wait:
            raise
        log.warning(f"[llm] subscription usage limit hit; waiting {wait / 60:.0f} min for the reset")
        import time
        time.sleep(max(0, wait))
        return _call_once(system, prompt, schema, effort, web, images, model, label)
