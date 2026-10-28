"""
Showrunner: every run picks the BEST topic our 3D sets can film, researches it, writes a
creative + accurate cutaway-explainer script, has it critiqued and revised until it passes the
bar, saves a data-driven film JSON, and (optionally) renders it with engine/make_film.

    python -m agents.showrunner                  # pick topic → research → write → render
    python -m agents.showrunner --no-render      # stop after the script (review it first)
    python -m agents.showrunner --angle "why pools are never drained in spring"

Stages (Claude subscription by default; Codex is the usage-limit fallback):
  1. pick_topic   brainstorm angles per available set, score them, avoid repeats
                  (also logs great topics that need a NEW set → output/set_wishlist.json)
  2. research     web search for verified facts + numbers (falls back to model knowledge)
  3. write        structured script: one ACTION per beat from the set's catalogue
  4. critique     a separate editor scores it on a rubric; revise until it ships (max 2 rounds)
  5. validate     hard checks: action order, word budget, hook length
"""
import argparse
import datetime
import json
import logging
import os
import re
import threading

from dotenv import load_dotenv

from config.paths import get_env_path, get_output_dir
from engine import sets

load_dotenv(get_env_path())
log = logging.getLogger("pipeline")

WORDS_PER_SECOND = 2.4                 # measured: 206 words → 76.5 s; 198 words → 82.8 s (pauses)
TARGET_WORDS = (140, 192)              # ≈ 60–80 s with this voice (incl. the closing question)
WORDS_PER_BEAT, WORDS_CAP = 18, 230    # long story ladders: ~18 words a beat, never over ~95 s
HOOK_MAX_WORDS = 13
PASS_SCORE = 8                         # what the editor and writer aim for
# What actually ships: no rule breaks and EVERY score >= SHIP_FLOOR. Calibrated on the editor's real
# scores: the old gate (all 8, or all 7 with an 8 average) was met by 0 of 77 graded scripts (median
# average 6.6), so it failed nearly every run; all-7 sits above every script the channel has posted.
SHIP_FLOOR = int(os.getenv("SHOWRUNNER_SHIP_FLOOR") or 7)
MAX_REVISIONS = max(1, int(os.getenv("SHOWRUNNER_MAX_REVISIONS", "2")))
# QUALITY=best: 3 competing drafts (~5 min). QUALITY=fast: 1 draft, 1 review, 1 fix (~2-3 min).
QUALITY = os.getenv("SHOWRUNNER_QUALITY", "efficient")
FACTS_DIR = os.path.join(get_output_dir(), "facts")
FACTS_MAX_AGE_DAYS = 30
HISTORY = os.path.join(get_output_dir(), "explainer_history.json")
WISHLIST = os.path.join(get_output_dir(), "set_wishlist.json")
FILMS_DIR = os.path.join(get_output_dir(), "films")

# ------------------- the house style (shared by writer + editor) -------------------

STYLE = """You write narration for 60-80 second vertical 3D CUTAWAY explainer videos (TikTok, Reels,
Shorts), the format of channels like @youbuiltit: the world is sliced open so viewers watch what
is normally hidden: soil layers, pipes, tanks, water and machines at work.

What makes these videos great:
- THE HOOK (beat 1, at most 13 words, about 2 seconds): one concrete, surprising, slightly
  alarming or counter-intuitive TRUE fact that the video later pays off. It must stop a thumb
  mid-scroll. Never open with "Did you know", "Have you ever wondered", "In this video", or a
  question about the viewer.
- THE BRIDGE (beat 2, the rewind): one short line that turns the hook into a promise, for example
  "So how do you build one that won't?"
- THE PATH: follow the physical order of the build or of the flow. One mechanism per beat, told
  as cause and effect or problem then fix ("But groundwater pushes up. So the floor gets...").
  Every beat should leave a small question the next beat answers.
- CONCRETE: numbers people can picture (tons, metres, litres, hours), comparisons ("heavier than
  three cars"). Use only numbers from the model facts or the research sheet.
- VOICE: a friend who builds things for a living. Conversational, confident, a little playful.
  Short sentences, contractions, fragments are fine. Plain words a 12-year-old gets; define jargon
  in the same breath ("shotcrete: concrete fired out of a hose"). Every few beats, one dry wink of
  humour (understatement, a wry aside). Never cringe, never forced, at most 2 exclamation marks.
- SYNC: each beat's words describe what is on screen in that beat (the action catalogue says what
  is visible). Never narrate something the viewer can't see then.
- PAYOFF: the last beat closes the loop: it answers the hook and ties it to everyday life (what
  the viewer will notice or should never do), so the video invites a rewatch.
- COMMENT QUESTION: the very last sentence of the last beat is a short question to the viewer
  (at most 12 words, ends with "?") that people will want to answer: a guess, an
  opinion or their own experience, tied to this story ("Which fix would you have tried first?",
  "Would you ride in Max's boat?"). Just the question: never mention comments, likes or
  subscribing, and never a yes/no that kills the thread.
- Spoken English only: no emojis, no markdown, no stage directions, digits are fine."""


STORY_STYLE = """You write narration for 60-80 second vertical 3D cutaway CARTOON videos (TikTok, Reels,
Shorts): the world is sliced open so viewers see what is hidden underground, starring a hero who
learns how things are really built by getting it hilariously wrong first.

The format is TRIAL AND ERROR:
- THE HOOK (beat 1, at most 13 words, about 2 seconds): the funniest disaster (or the happy payoff),
  shown on screen, phrased so the viewer has to know how it happened. Example of the energy, not
  the words: "This is Max. His brand new pool just floated out of the ground." Never "Did you know",
  never a question to the viewer.
- THE BRIDGE (beat 2, the rewind): one short line back to the start.
- THE LADDER: the hero tries the obvious thing, it FAILS on screen, the narration names the REAL
  physical reason in one plain sentence, the FIX is the real engineering solution and says why it
  works, and the next attempt reveals the next problem. Every failure is a true lesson and every
  fix answers exactly that failure. Make cause and effect explicit ("because", "so", "but").
- THE HERO: endearing and overconfident, never stupid: we laugh WITH him. The comedy is his
  confidence colliding with physics: deadpan understatement, famous last words ("What could go
  wrong?"), escalating disasters, a running gag (counting the fails, the kids waiting with towels),
  and a callback at the end. Short punchy sentences, contractions, fragments, timing.
- CONCRETE: real numbers people can picture (tons, metres, litres, hours), only from the model
  facts or the fact sheet.
- EVERY LINE INFORMS: each sentence either moves the story or explains something real. No score,
  counter or tally gags ("Physics 1", "Fail #2", "Round 3", scoreboards), no catchphrase that carries
  no information. The hook must make complete sense to someone who has seen nothing else.
- STORYTELLING, NOT TELEGRAMS: write like a great narrator telling a funny story out loud: full,
  natural sentences that flow into each other, with rhythm and a clear subject in each one. Fragments
  only as a deliberate punchline, never as the default ("Rewind. One field. Big idea." is wrong;
  "Let's rewind to the day Max had a big idea." is right). No repeated catchphrase in every beat.
- CLARITY: a viewer who sees the video once must always know what Max is trying, what went wrong and
  why, and what he changes. Never cryptic, never an inside joke the viewer can't follow.
- COMEDY CRAFT: every failure beat is built as SETUP then PUNCHLINE, and the punchline is the last
  words of the beat. Use the visible gags as punchlines (whatever the action shows: a deadpan salute,
  a fish on his hat, a duck overtaking him). One running gag set up early and paid off in the finale.
  Max is confident, the narrator is dry: understatement beats exclamation marks.
- THE AHA: the viewer must finish thinking "I didn't know that!". Each fix states its principle in
  ONE memorable, quotable sentence with a concrete number or comparison taken from the facts (the
  on-screen arrows, markers and numbers: name what the viewer SEES). The finale lands the most
  jaw-dropping real-world link from the facts (the giant version of the same trick) right before
  the closing question. Funny AND impressive: the laugh opens the door, the fact is the reward.
- PAYOFF: the last beat is a clear, satisfying happy ending: say plainly what finally works and show
  the family enjoying it (it must feel finished), then call back the hook.
- SYNC: each beat's words match what that beat's action shows on screen.
- COMMENT QUESTION: the very last sentence of the last beat is a short question to the viewer
  (at most 12 words, ends with "?") that people will want to answer: a guess, an
  opinion or their own experience, tied to this story ("Which fix would you have tried first?",
  "Would you ride in Max's boat?"). Just the question: never mention comments, likes or
  subscribing, and never a yes/no that kills the thread.
- Spoken English only: no emojis, no markdown, no stage directions, digits are fine."""


def _style(set_id):
    """Story sets (with a hero) get the trial-and-error comedy voice; explainer sets the build-up voice
    ("If you ..., you have a ..." → "Congratulations, you've built a ...", agents/buildup.py); others STYLE."""
    from agents import buildup
    if buildup.enabled(set_id):
        return buildup.STYLE
    return STORY_STYLE if getattr(sets.spec(set_id), "HERO", None) else STYLE


# ------------------- low-level call -------------------
#
# Three backends:
#   subscription (default): Claude Code's headless mode (`claude -p`) on Claude Pro/Max.
#   codex: Codex CLI headless mode on the logged-in ChatGPT plan (the default fallback).

BACKEND = os.getenv("SHOWRUNNER_BACKEND", "subscription").strip().lower()
CLI_MODEL = os.getenv("SHOWRUNNER_CLI_MODEL", "opus")
CODEX_MODEL = os.getenv("SHOWRUNNER_CODEX_MODEL", "gpt-5.6-sol")
_API_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "CLAUDE_CODE_USE_BEDROCK",
            "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY")
_notional = [0.0]
CLAUDE_USAGE = {"calls": 0, "input_tokens": 0, "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0, "output_tokens": 0}
_ACTIVE_BACKEND = [None]
_PRIMARY_RESET = [None]                # when the primary backend's usage limit lifts (from its error text)
_BACKEND_LOCK = threading.Lock()


def active_backend():
    """Backend currently serving this process; changes once after a usage limit."""
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
        log.warning("[showrunner] %s; switching all remaining AI work to %s", str(reason)[:180], fallback)
    return True


def primary_reset():
    """When the backend this process fell back from becomes available again (None = unknown)."""
    return _PRIMARY_RESET[0]


def _capped_effort(requested, env_name="SHOWRUNNER_CLAUDE_EFFORT_CAP", default="medium"):
    """Cap subscription reasoning so a stray high-effort call cannot consume the session."""
    order = ("low", "medium", "high", "max")
    requested = requested if requested in order else default
    cap = (os.getenv(env_name) or default).strip().lower()
    if cap not in order:
        cap = default
    return order[min(order.index(requested), order.index(cap))]


def _record_claude_usage(data, label="claude"):
    """Collect Claude CLI usage across showrunner, vision and set-builder calls."""
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


def claude_usage_summary():
    u = CLAUDE_USAGE
    return (f"{u['calls']} call(s), {u['input_tokens']:,} input tokens "
            f"({u['cache_read_input_tokens']:,} cache-read, "
            f"{u['cache_creation_input_tokens']:,} cache-write), {u['output_tokens']:,} output tokens")


class BudgetExceeded(RuntimeError):
    """The CLAUDE_TOKEN_BUDGET for this process is spent; retrying cannot help."""


def token_budget() -> int:
    """Token ceiling for one process. 0 / unset = no ceiling."""
    try:
        return max(0, int(os.getenv("CLAUDE_TOKEN_BUDGET") or 0))
    except ValueError:
        return 0


_CARRIED = [0]                         # tokens an interrupted run already spent before this process resumed it


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


def _call_once(system, prompt, schema=None, effort="high", tools=None, max_tokens=16000):
    backend = active_backend()
    if backend == "codex":
        return _call_codex(system, prompt, schema, effort, web=bool(tools))
    return _call_cli(system, prompt, schema, effort, web=bool(tools))


class UsageLimit(RuntimeError):
    """A subscription backend hit its session/usage limit."""

    def __init__(self, msg):
        super().__init__(msg)
        self.reset = parse_reset(msg)


def parse_reset(msg):
    """When a usage limit lifts, from Claude ("resets 3pm") or Codex ("try again at 9:41 AM",
    "try again at Oct 29th, 2026 9:41 AM", "try again in 2 days 3 hours 5 minutes"). None if unknown."""
    import datetime as _dt
    import re as _re
    now = _dt.datetime.now()
    m = _re.search(r"try again in\s+((?:\d+\s*(?:days?|hours?|hrs?|minutes?|mins?)[\s,and]*)+)", msg, _re.I)
    if m:
        delta = _dt.timedelta()
        for n, unit in _re.findall(r"(\d+)\s*(day|hour|hr|min)", m.group(1), _re.I):
            delta += {"day": _dt.timedelta(days=int(n)), "hour": _dt.timedelta(hours=int(n)),
                      "hr": _dt.timedelta(hours=int(n)), "min": _dt.timedelta(minutes=int(n))}[unit.lower()]
        return now + delta if delta else None
    m = _re.search(r"(?:resets|try again at)\s+(?:([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4}),?\s+)?"
                   r"([0-9]{1,2})(?::([0-9]{2}))?\s*(am|pm)", msg, _re.I)
    if not m:
        return None
    h, mi = int(m.group(4)) % 12 + (12 if m.group(6).lower() == "pm" else 0), int(m.group(5) or 0)
    if m.group(1):
        try:
            day = _dt.datetime.strptime(f"{m.group(1)[:3]} {m.group(2)} {m.group(3)}", "%b %d %Y")
            return day.replace(hour=h, minute=mi)
        except ValueError:
            pass
    t = now.replace(hour=h, minute=mi, second=0, microsecond=0)
    return t if t > now else t + _dt.timedelta(days=1)


def codex_unavailable(exc):
    """True when a Codex subscription call should immediately move to the fallback.

    Codex reports both quota exhaustion and transient model saturation as ordinary CLI
    failures. Neither can be repaired by repeating the same expensive pipeline stage.
    """
    text = str(exc).lower()
    limited = "limit" in text and any(
        word in text for word in ("reset", "rate", "usage", "quota", "plan")
    )
    saturated = any(phrase in text for phrase in (
        "model is at capacity", "model at capacity", "selected model is at capacity",
        "server is overloaded", "service is overloaded", "temporarily unavailable",
        "try a different model",
    ))
    return limited or saturated


def _call(system, prompt, schema=None, effort="high", tools=None, max_tokens=16000):
    """Call the selected backend; on a usage limit, wait up to SHOWRUNNER_MAX_WAIT
    minutes) and retries once, so an unattended run finishes instead of dying."""
    import time as _t
    backend = active_backend()
    try:
        return _call_once(system, prompt, schema, effort, tools, max_tokens)
    except UsageLimit as e:
        if activate_fallback(str(e), failed_backend=backend):
            try:
                return _call_once(system, prompt, schema, effort, tools, max_tokens)
            except UsageLimit as fallback_error:
                e = fallback_error
        wait = (e.reset - __import__("datetime").datetime.now()).total_seconds() + 60 if e.reset else None
        max_wait = float(os.getenv("SHOWRUNNER_MAX_WAIT", "65")) * 60
        if wait is None or wait > max_wait:
            raise
        log.warning(f"[showrunner] subscription usage limit hit; waiting {wait / 60:.0f} min for the reset")
        _t.sleep(max(0, wait))
        return _call_once(system, prompt, schema, effort, tools, max_tokens)


def _call_cli(system, prompt, schema=None, effort="high", web=False):
    """One call through Claude Code headless mode, authenticated with the claude.ai login.
    API credentials are stripped from its environment (your .env holds an API key: if it leaked
    through, Claude Code would bill the API instead of the subscription). Runs in an empty temp
    dir with no project settings, no MCP servers and no tools except web search when asked."""
    import shutil
    import subprocess
    import tempfile

    check_budget("showrunner")
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("Claude Code CLI not found: install it and run `claude` once to log in")
    env = {k: v for k, v in os.environ.items() if k not in _API_ENV}
    tools = ["WebSearch", "WebFetch"] if web else [""]
    with tempfile.TemporaryDirectory() as tmp:
        sys_file = os.path.join(tmp, "system.txt")
        with open(sys_file, "w", encoding="utf-8") as f:
            f.write(system)
        cmd = [exe, "-p", "--output-format", "json", "--model", CLI_MODEL, "--effort",
               _capped_effort(effort),
               "--system-prompt-file", sys_file, "--no-session-persistence", "--strict-mcp-config",
               "--setting-sources", "", "--tools", *tools]
        if web:
            cmd += ["--allowedTools", "WebSearch", "WebFetch"]
        if schema is not None:
            cmd += ["--json-schema", json.dumps(schema)]
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                           cwd=tmp, env=env, timeout=1800)
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"claude -p failed (exit {r.returncode}): {(r.stderr or r.stdout)[-400:]}")
    result_text = str(data.get("result") or "")
    if data.get("is_error") and ("limit" in result_text.lower() and "reset" in result_text.lower()):
        raise UsageLimit(result_text[:200])
    if data.get("is_error") or data.get("subtype") != "success":
        raise RuntimeError(f"claude -p error ({data.get('subtype')}): {str(data.get('result'))[:300]}")
    _notional[0] += float(data.get("total_cost_usd") or 0)
    _record_claude_usage(data, "showrunner")
    if schema is not None:
        out = data.get("structured_output")
        return out if out is not None else json.loads(data["result"])
    return data["result"].strip()


def _call_codex(system, prompt, schema=None, effort="high", web=False):
    """One isolated Codex CLI turn authenticated by the user's ChatGPT login."""
    from agents import codex_cli

    full = ("Follow the role and constraints below. Do the task directly; do not inspect or edit local files.\n\n"
            f"ROLE AND RULES:\n{system}\n\nTASK:\n{prompt}")
    try:
        out, _ = codex_cli.run(full, schema=schema, effort=effort, web=web, model=CODEX_MODEL)
        return out
    except RuntimeError as exc:
        if codex_unavailable(exc):
            raise UsageLimit(str(exc)[:500]) from exc
        raise


def _obj(props, required=None):
    return {"type": "object", "properties": props, "required": required or list(props),
            "additionalProperties": False}


S, I = {"type": "string"}, {"type": "integer"}


# ------------------- 1. topic -------------------

class NoUnusedStorySets(RuntimeError):
    """Every requested hero/story set has already been used for a published script."""


def _history():
    """Logged scripts plus any film JSON in FILMS_DIR the log missed (e.g. a film written or
    rendered by hand), so a subject already filmed is never offered again as unused."""
    try:
        hist = json.load(open(HISTORY, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        hist = []
    known = {os.path.normcase(os.path.abspath(h["film"])) for h in hist if h.get("film")}
    try:
        names = sorted(n for n in os.listdir(FILMS_DIR) if n.endswith(".json"))
    except OSError:
        names = []
    for name in names:
        path = os.path.join(FILMS_DIR, name)
        if os.path.normcase(os.path.abspath(path)) in known:
            continue
        try:
            film = json.load(open(path, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(film, dict) and film.get("set"):
            meta = film.get("meta") or {}
            hist.append({"title": film.get("title", ""), "angle": meta.get("angle", ""),
                         "set": film["set"], "film": path, "date": str(meta.get("created", ""))[:10]})
    return hist


def available_topic_sets(set_ids=None, history=None):
    """Return selectable sets, treating a hero set as one consumable story subject.

    A different title, hook, or running gag does not make Max rebuilding the same thing a new
    subject. Non-story explainer sets may still support genuinely different mechanisms/angles.
    SHOWRUNNER_ALLOW_REPEATS=1 is an explicit producer override for reruns and tests.
    """
    requested = list(set_ids or sets.AVAILABLE)
    if os.getenv("SHOWRUNNER_ALLOW_REPEATS", "0").lower() in ("1", "true", "yes"):
        return requested
    history = _history() if history is None else history
    consumed = {item.get("set") for item in history if item.get("set")}
    return [set_id for set_id in requested
            if not (getattr(sets.spec(set_id), "HERO", None) and set_id in consumed)]


NEW_STORY_SCHEMA = _obj({
    "subject": S,
    "title": S,
    "angle": S,
    "hook_line": S,
    "hook_action": S,
    "payoff": S,
    "trend_signal": S,
    "trend_source_url": S,
    "why_people_care_now": S,
    "build_brief": S,
    "fact_sheet": S,
})


def _wishlist():
    try:
        return json.load(open(WISHLIST, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def _new_story_set_id(subject):
    words = re.sub(r"\b(max|builds?|makes?|creates?|a|an|the|his|her)\b", " ", subject.lower())
    stem = re.sub(r"[^a-z0-9]+", "_", words).strip("_")[:28] or "new_max_project"
    base = stem + "_story"
    candidate, n = base, 2
    while os.path.exists(os.path.join(os.path.dirname(__file__), "..", "engine", "sets", candidate + ".py")):
        candidate, n = f"{stem[:24]}_{n}_story", n + 1
    return candidate


def plan_new_story_set():
    """Research and choose a genuinely new, timely Max subject that can become a 3D set."""
    published = "\n".join(f"- {h.get('set')}: {h.get('title')}" for h in _history()) or "- none"
    ideas = _wishlist()[-30:]
    wishlist = "\n".join(f"- {i.get('topic')}: {i.get('set_needed')}" for i in ideas) or "- none"
    prompt = f"""Today is {datetime.date.today().isoformat()}. Search current sources from the last
14 days and choose one genuinely new Max trial-and-error engineering story to build next. Search
across home projects, infrastructure, transport, energy, water, machines and practical science.
The subject must work as one coherent 3D cutaway with at least three true failure -> fix steps.

OLDER SET WISHLIST (inspiration only; live research wins):
{wishlist}

USED SUBJECTS (never repeat or rename these):
{published}

Return:
- subject: a short concrete name for the thing Max builds
- title, angle, hook_line (13 words maximum), hook_action, and payoff for the eventual video
- trend_signal and the exact direct trend_source_url from the live research
- why_people_care_now
- fact_sheet: a compact 8-12 bullet fact sheet (maximum 250 words), verified during this same
  search, with a source domain or direct URL on every bullet and a TRUE / NEEDS REWORDING verdict
  for hook_line
- build_brief: a self-contained production brief describing the single coherent cutaway world,
  Max's goal, two children in the payoff, 3-5 escalating visible failures, the real engineering fix
  immediately after each failure, the final working result, and the physical principles viewers
  learn. It must be feasible using Blender primitives and must not need logos or downloaded assets.

Do not choose a subject merely because it appears in the old wishlist. It needs a credible current
signal and must be different from every used subject."""
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 6}]
    plan = _call(STORY_STYLE, prompt, NEW_STORY_SCHEMA, effort="medium", tools=tools)
    url = str(plan.get("trend_source_url", ""))
    if not url.startswith(("http://", "https://")):
        raise NoUnusedStorySets("Fresh topic research returned no verifiable trend source; no set was built.")
    plan["set_id"] = _new_story_set_id(plan["subject"])
    log.info(f"[showrunner] new subject: {plan['subject']} | trend: {plan['trend_signal']}")
    return plan


def _ensure_extras(set_id):
    """A Max story set whose spec says nothing about its gags gets "extras" described once from its own
    code, so the writer can joke about what is really on screen (see set_builder.backfill_extras)."""
    import importlib
    sp = sets.spec(set_id)
    if not getattr(sp, "HERO", None) or getattr(sp, "KIT", None) or any(v.get("extras") for v in sp.ACTIONS.values()):
        return                          # (a kit set's extras come from the kit itself, never from a model)
    from agents.set_builder import backfill_extras
    if backfill_extras(set_id):
        importlib.reload(sp)


def _set_brief(set_id):
    sp = sets.spec(set_id)
    actions = "\n".join(f"  - {k} [{v['kind']}]: {v['shows']}"
                        + (f" Also on screen (use it for jokes): {v['extras']}" if v.get("extras") else "")
                        for k, v in sp.ACTIONS.items())
    facts = "\n".join(f"  - {k}: {v}" for k, v in sp.MODEL_FACTS.items())
    return (f"SET '{set_id}': {sp.SUBJECT}\nWhat the 3D model shows (fixed facts):\n{facts}\n"
            f"Actions (visual beats this set can play):\n{actions}")


TOPIC_SCHEMA = _obj({
    "candidates": {"type": "array", "items": _obj({
        "set": S, "title": S, "angle": S, "hook_line": S, "hook_action": S, "payoff": S,
        "trend_signal": S, "trend_source_url": S, "trend_relevance": I,
        "hook_strength": I, "curiosity": I, "visual_fit": I, "novelty": I, "shareability": I})},
    "best": I,
    "fact_sheet": S,
    "wishlist": {"type": "array", "items": _obj({"topic": S, "hook_line": S, "set_needed": S})},
})


def pick_topic(set_ids=None, forced_angle=None):
    requested = list(set_ids or sets.AVAILABLE)
    history = _history()
    set_ids = available_topic_sets(requested, history)
    if not set_ids:
        consumed = sorted({h.get("set") for h in history if h.get("set") in requested})
        raise NoUnusedStorySets(
            "All registered Max story subjects have already been used"
            + (f": {', '.join(consumed)}" if consumed else "")
            + ". Add a new story set before generating another Max video, or set "
              "SHOWRUNNER_ALLOW_REPEATS=1 only when you intentionally want a rerun."
        )
    skipped = [set_id for set_id in requested if set_id not in set_ids]
    if skipped:
        log.info(f"[showrunner] consumed subjects excluded: {', '.join(skipped)}")
    used = [h.get("title", "") + " | " + h.get("angle", "") for h in history][-40:]
    briefs = "\n\n".join(_set_brief(s) for s in set_ids)
    prompt = f"""Today is {datetime.date.today().isoformat()}. Search current sources from the last
14 days, then pick today's video.

{briefs}

Already published (do NOT repeat these angles or hooks):
{chr(10).join('- ' + u for u in used) or '- (nothing yet)'}

{'The producer asked for this angle; develop it, using the set whose SUBJECT matches it: ' + forced_angle if forced_angle else ''}

Return 3 distinct ANGLES that these sets can film: different hooks and questions about the
same subject (why it is built that way, what goes wrong if..., the hidden part nobody sees, the
surprising number, the thing you should never do). For each: a working title, the angle, the hook
line (the first 2 seconds, at most 13 words, a true fact), which hook action opens it, the payoff
that closes the loop, the exact current trend signal, its direct source URL, and honest 1-10 scores
for trend_relevance, hook_strength, curiosity, visual_fit (how well this set's actions can SHOW it),
novelty (vs published) and shareability. A weak or forced trend connection must score below 6.
Set `best` to the index of the strongest overall (weight trend relevance, hook strength and visual
fit most). Remember the film always shows
the whole build, but build steps that are not the point can be raced through as montages, so an
angle about the water, the soil or the machinery works as well as one about construction.

After choosing `best`, use the same search turn to return `fact_sheet`: a compact 8-12 bullet fact
sheet (maximum 250 words) for that winning subject. Put a source domain or direct URL on every
bullet, verify the winning hook with a TRUE / NEEDS REWORDING verdict, and include only facts the
script can safely repeat.

Also list 2 wishlist topics that would make outstanding cutaway videos but need a NEW set (for
example a gas station's underground tanks, a septic system, a water tower): topic, hook line, and
the set to build."""
    if any(getattr(sets.spec(s_), "HERO", None) for s_ in set_ids):
        prompt += """

For hero (story) sets, an ANGLE is a fresh telling of the hero's trial-and-error story: what he is
building it for, the running gag, which disaster becomes the hook, the comic voice, the payoff.
Never frame it as a score or contest ("Physics 1, Max 0", "rounds", "fail #2"): a counter tells the
viewer nothing. The hook line must make sense on its own to someone who has seen nothing else."""
    from agents import buildup
    if any(buildup.enabled(s_) for s_ in set_ids):
        prompt += buildup.TOPIC_NOTE
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 6}]
    out = _call(_style(set_ids[0]), prompt, TOPIC_SCHEMA, effort="medium", tools=tools)
    _save_wishlist(out.get("wishlist", []))
    cands = out["candidates"]
    best = cands[max(0, min(out["best"], len(cands) - 1))]
    if GAG_RE.search(best["hook_line"] + " " + best["title"]):            # no "Physics won round 3" hooks
        clean = [c for c in cands if not GAG_RE.search(c["hook_line"] + " " + c["title"])]
        if clean:
            best = max(clean, key=lambda c: 2 * c["hook_strength"] + 2 * c["visual_fit"] + c["curiosity"]
                       + c["novelty"] + c["shareability"])
    if best["set"] not in set_ids:
        best["set"] = set_ids[0]
    if str(out.get("fact_sheet", "")).strip():
        best["_fact_sheet"] = out["fact_sheet"].strip()
    minimum_trend = int(os.getenv("SHOWRUNNER_MIN_TREND_SCORE", "6"))
    if not forced_angle and (best.get("trend_relevance", 0) < minimum_trend
                             or not str(best.get("trend_source_url", "")).startswith(("http://", "https://"))):
        raise NoUnusedStorySets(
            "No unused story subject has a strong, sourced trend signal today. "
            "No video was started; add a new set from output/set_wishlist.json or try again later."
        )
    log.info(f"[showrunner] topic: {best['title']} | hook: {best['hook_line']}")
    return best


def _save_wishlist(items):
    try:
        cur = json.load(open(WISHLIST, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cur = []
    seen = {c["topic"].lower() for c in cur}
    cur += [dict(i, date=datetime.date.today().isoformat()) for i in items if i["topic"].lower() not in seen]
    os.makedirs(os.path.dirname(WISHLIST), exist_ok=True)
    json.dump(cur, open(WISHLIST, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


# ------------------- 2. research -------------------

def research(topic):
    """Fact sheet for the set's subject, web-researched once and reused for FACTS_MAX_AGE_DAYS."""
    import time
    cache = os.path.join(FACTS_DIR, f"{topic['set']}.txt")
    try:
        if time.time() - os.path.getmtime(cache) < FACTS_MAX_AGE_DAYS * 86400:
            facts = open(cache, encoding="utf-8").read()
            log.info(f"[showrunner] fact sheet: cached ({len(facts.split())} words)")
            return facts
    except OSError:
        pass
    combined = str(topic.get("_fact_sheet") or "").strip()
    if len(combined.split()) >= 50:
        facts = combined
        log.info(f"[showrunner] fact sheet: reused from topic research ({len(facts.split())} words)")
    else:
        facts = _research(topic)
    os.makedirs(FACTS_DIR, exist_ok=True)
    with open(cache, "w", encoding="utf-8") as f:
        f.write(facts)
    return facts


def _research(topic):
    sp = sets.spec(topic["set"])
    prompt = f"""Research facts for a short video.
Subject: {sp.SUBJECT}
Facts the 3D model already shows: {json.dumps(sp.MODEL_FACTS, ensure_ascii=False)}
Example hook to verify: {topic['hook_line']}

Search the web and return a compact FACT SHEET (plain text, max ~250 words): 8-12 bullet facts
with concrete numbers about this subject, each with its source domain in brackets; correct any of
the model facts that are wrong. Start with a verdict on the example hook (TRUE / NEEDS REWORDING). Prefer engineering, trade and government
sources. Include 2-3 surprising details that would delight a viewer."""
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 6}]
    try:
        facts = _call("You are a meticulous fact-checker for an engineering explainer channel.", prompt,
                      tools=tools, effort="medium")
    except UsageLimit:
        raise
    except RuntimeError as e:  # web search unavailable / failed
        log.warning(f"[showrunner] web search failed ({str(e)[:100]}); using model knowledge")
        facts = _call("You are a meticulous fact-checker for an engineering explainer channel.",
                      prompt.replace("Search the web and return", "From reliable knowledge, return"), effort="medium")
    log.info(f"[showrunner] fact sheet: {len(facts.split())} words")
    return facts


# ------------------- 3. write, 4. critique + revise -------------------

SCRIPT_SCHEMA = _obj({
    "title": S,
    "beats": {"type": "array", "items": _obj({
        "actions": {"type": "array", "items": S}, "text": S,
        "overlay": _obj({"type": {"type": "string", "enum": ["none", "stat", "label"]}, "value": S, "text": S}),
    })},
    "caption": S,
    "hashtags": {"type": "array", "items": S},
})

CRITIQUE_SCHEMA = _obj({
    "scores": _obj({"hook": I, "clarity": I, "story_flow": I, "problem_solution": I, "fun": I, "accuracy": I,
                    "pacing": I, "visual_sync": I, "learn": I}),
    "problems": {"type": "array", "items": S},
    "line_edits": {"type": "array", "items": S},
    "verdict": {"type": "string", "enum": ["ship", "revise"]},
})


def _rules(set_id):
    from agents import buildup
    if buildup.enabled(set_id):
        return buildup.rules(set_id, WORDS_PER_SECOND, word_budget(set_id))
    sp = sets.spec(set_id)
    order = getattr(sp, "STORY_ORDER", None) or sp.BUILD_ORDER
    hooks = ", ".join(k for k, v in sp.ACTIONS.items() if v["kind"] == "hook")
    explain = "; ".join(f"{k} after {v['after']}" for k, v in sp.ACTIONS.items() if v["kind"] == "explain")
    outros = ", ".join(k for k, v in sp.ACTIONS.items() if v["kind"] == "outro")
    fails = [k for k, v in sp.ACTIONS.items() if v["kind"] == "fail"]
    max_group = 3 if fails else 4
    ladder = (f"\n- The fail_* actions are the hero's failures ({', '.join(fails)}): give each its own beat, name the"
              f"\n  real cause, and make the NEXT beat the fix that answers it. Never use stickers for fail counts,"
              f"\n  scores or attempts (no 'Fail #', no scoreboards).") if fails else ""
    lo, hi = word_budget(set_id)
    return f"""STRUCTURE RULES (the renderer enforces them):
- Beat 1 = a hook action ({hooks}): pick the one whose VISUAL matches your hook line (the viewer must
  see what the first words say); beat 2 = rewind.
- Then these actions exactly once each, in this order: {' → '.join(order)}.{ladder}
- Optional explainer actions after their prerequisite: {explain or 'none'}.{(' Optional outro (last beat only): ' + outros + '.') if outros else ''}
- A beat plays ONE action, or a quick MONTAGE of 2-{max_group} consecutive actions ("actions": ["rebar",
  "shotcrete"]) to race through steps that are not the point. Hooks, the rewind{' and failures' if fails else ''} are single.
- A beat needs enough words for what it shows: at least (sum of its actions' minimum seconds) x
  {WORDS_PER_SECOND} x 0.75 words. No beat over 32 words. 10-17 beats in total.
- Word budget: aim for {hi - 37}-{hi - 12} words and count before returning. The hard allowed range is
  {lo}-{hi} words in total (~{WORDS_PER_SECOND} words/s); do not draft at
  the upper boundary. Hook <= {HOOK_MAX_WORDS} words.
- overlay: optional 2D sticker for that beat. type "stat" = a number that counts up (value like
  "50 tons", text like "of dirt": a REAL measurement only); "label" = a short badge naming a real
  part or idea, no numbers (e.g. "Planes turn by banking"). Use "none" on most beats,
  at most 6 stickers in total, never on the hook. Never repeat a label the action already shows in
  the scene (its "shows" text names labels like 7 m TUNNEL or 285-315 rpm): the two overlap on screen.
- Numbers must match the model facts: what is ON SCREEN is the model."""


STORY_DIRECTIONS = {
    "slapstick": "Escalating physical comedy: every disaster bigger than the last, big reactions, the "
                 "narrator landing each visible mishap as a punchline. Use one physical running gag "
                 "that pays off at the end; never count, score or number the failures. Fast, punchy.",
    "deadpan": "A dry, deadpan narrator who describes each catastrophe with total calm and perfect "
               "understatement. The calmer the voice, the bigger the disaster.",
    "sitcom": "A family sitcom: the kids waiting with towels and floaties as a running gag, Max's famous "
              "last words before each fail, a warm callback at the end.",
}

DIRECTIONS = {
    "mystery": "Play it as a slow-burn mystery: the hook is a threat, every beat tightens the screw, "
               "the payoff is the reveal. Tense, cinematic, short lines.",
    "wry": "Play it as a dry, witty insider: understatement, deadpan asides, a running joke that pays "
           "off at the end. Warm and funny, never silly.",
    "numbers": "Play it numbers-first: every beat lands one jaw-dropping, picturable number or "
               "comparison. Punchy, rhythmic, almost like a countdown.",
}


def write_script(topic, facts, previous=None, critique=None, direction=None, effort="high"):
    set_id = topic["set"]
    prompt = f"""{_set_brief(set_id)}

{_rules(set_id)}

TOPIC: {topic['title']}
ANGLE: {topic['angle']}
{_hook_idea(topic)}
PAYOFF IDEA: {topic['payoff']}

FACT SHEET (verified research):
{facts}
"""
    if previous:
        prompt += f"""
YOUR PREVIOUS DRAFT:
{json.dumps(previous, ensure_ascii=False, indent=1)}

THE EDITOR'S NOTES (fix every one; keep what works):
{json.dumps(critique, ensure_ascii=False, indent=1)}

Write the improved script."""
    else:
        if direction:
            prompt += f"\nCREATIVE DIRECTION: {_directions(set_id)[direction]}\n"
        example = _tone_example(set_id)
        if example:
            prompt += ("\nTONE EXAMPLE: another writer's script for this same set. Do NOT reuse its jokes, lines "
                       f"or hook; beat it.\n{example}\n")
        prompt += "\nWrite the script. Make the hook impossible to scroll past and every beat earn its place."
    return _call(_style(set_id), prompt, SCRIPT_SCHEMA, effort=effort)


def _hook_idea(topic):
    from agents import buildup
    if buildup.enabled(topic["set"]):
        return (f"OPENING IDEA: {topic['hook_line']}  (the first sentence must start with \"If you\" and say "
                "\"you have a <thing>\"; the film opens on the first build step)")
    return f"HOOK IDEA: {topic['hook_line']}  (opens with action: {topic['hook_action']})"


def _directions(set_id):
    from agents import buildup
    if buildup.enabled(set_id):
        return buildup.DIRECTIONS
    return STORY_DIRECTIONS if getattr(sets.spec(set_id), "HERO", None) else DIRECTIONS


def _tone_example(set_id):
    """Narration of a hand-written reference film for this set (engine/films/*.json), if any."""
    import glob
    from agents import buildup
    if buildup.enabled(set_id):
        return buildup.tone_example(set_id)
    for path in glob.glob(os.path.join(os.path.dirname(os.path.dirname(__file__)), "engine", "films", "*.json")):
        try:
            film = json.load(open(path, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if film.get("set") == set_id and film.get("format") != "buildup":
            return "\n".join(f"[{b.get('id')}] {b['text']}" for b in film["beats"])
    return ""


def polish(script, topic, facts):
    """Read-aloud pass: fix wording only (rhythm, awkward phrases, tongue-twisters, repetition).
    The beat list, actions, overlays and facts stay exactly as they are."""
    prompt = f"""Read this script ALOUD in your head as a voice actor would, then polish the wording.
Fix: awkward or unclear phrases, clunky rhythm, repeated words, tongue-twisters, sentences that
are hard to say in one breath, anything a listener could mishear. Sharpen jokes, never add new
facts, never change numbers, keep every beat, its action and its overlay exactly, keep each beat's
length within +/-15%. Return the full script.

FACT SHEET (for reference only):
{facts}

SCRIPT:
{json.dumps(script, ensure_ascii=False, indent=1)}"""
    out = _call(_style(topic["set"]), prompt, SCRIPT_SCHEMA, effort="low")
    if [b["actions"] for b in out["beats"]] != [b["actions"] for b in script["beats"]]:
        return script                                   # polish must not restructure
    return out


def critique_script(script, topic, facts, hard_problems):
    lo, hi = word_budget(topic["set"])
    prompt = f"""You are the channel's head editor. Grade this script ruthlessly (1-10 each): hook (would
it stop the scroll in 2 s?), clarity (a 12-year-old follows every beat), story_flow (each beat
answers the last and raises the next; a clear, satisfying ending; natural spoken sentences, not
telegraphic fragments), problem_solution (every problem/failure has its REAL cause
named, and the next beat's fix clearly answers it and says why it works), fun (genuinely funny:
character, comic timing, escalation, callbacks; no filler, nothing cringe), accuracy (every claim
matches the fact sheet or the model facts), pacing (no beat too long or rushed, total length
right), visual_sync (each beat's words match what that action shows), learn (would a curious adult
say "I didn't know that!": surprising, concrete, memorable facts, a jaw-dropping finale link).

{_set_brief(topic['set'])}

FACT SHEET:
{facts}

SCRIPT:
{json.dumps(script, ensure_ascii=False, indent=1)}

Automatic checks found: {hard_problems or 'nothing'}

WORD BUDGET (a hard rule, not a preference): the whole narration must stay within {lo}-{hi}
words, about {hi // max(1, len(script.get('beats', [])))} words per beat for this script ({len(script.get('beats', []))} beats).
Grade clarity, problem_solution and learn against what fits: each beat needs ONE cause or ONE principle,
said plainly, not every fact on the sheet. A better line is never more than a few words longer than the
line it replaces; when a beat cannot hold both its lesson and its gag, keep the lesson and cut the gag.
Edits that would push the total over budget are wrong edits (a revision that followed such notes grew to
294 words and failed).

List concrete problems and line edits (quote the line, give the better line). verdict = "ship"
only if every score is {PASS_SCORE}+ and there are no factual errors or rule breaks."""
    from agents import buildup
    if buildup.enabled(topic["set"]):
        prompt += buildup.CRITIQUE_NOTE
    return _call(_style(topic["set"]), prompt, CRITIQUE_SCHEMA, effort="medium")


def closing_question(text):
    """The final sentence of `text` if it is a question to the viewer, else None."""
    t = text.strip()
    if not t.endswith("?"):
        return None
    parts = re.split(r"(?<=[.!?])\s+", t)
    return parts[-1].strip() if parts else None


GAG_RE = re.compile(r"\b(physics|fail(ure)?|round|attempt|score|plane|max|take)\s*#?\s*(\d+|zero|one|two|"
                    r"three|four|five)\b|\bscoreboard\b|\b\d+\s*-\s*\d+\b|\brounds\b|"
                    r"\b(physics|gravity)\s+(wins|won|leads|led|scores?|scored)\b", re.I)


def word_budget(set_id):
    """(min, max) narration words for a set. A Max story ladder gets ~WORDS_PER_BEAT words per beat (its
    actions + hook + rewind), at least TARGET_WORDS' maximum and at most WORDS_CAP: a 12-beat ladder with
    four failure mechanisms could not be both clear and funny in 192 words (16 a beat) - every revision
    traded one for the other. Other formats keep TARGET_WORDS."""
    try:
        sp = sets.spec(set_id)
    except Exception:                                    # noqa: BLE001  unknown set: the default budget
        return TARGET_WORDS
    order = getattr(sp, "STORY_ORDER", None)
    if not (getattr(sp, "HERO", None) and order):
        return TARGET_WORDS
    return TARGET_WORDS[0], min(WORDS_CAP, max(TARGET_WORDS[1], WORDS_PER_BEAT * (len(order) + 2)))


def hard_checks(script, set_id):
    from agents import buildup
    if buildup.enabled(set_id):
        return buildup.checks(script, set_id, WORDS_PER_SECOND, word_budget(set_id))
    sp = sets.spec(set_id)
    beats = script["beats"]
    problems = list(sp.validate(beats))
    for k, b in enumerate(beats):
        if GAG_RE.search(b["text"]):
            problems.append(f"beat {k + 1}: score/counter gag ('{GAG_RE.search(b['text']).group(0)}') carries no "
                            "information; replace it with story or explanation")
        n = len(b["text"].split())
        need = int(sp.min_seconds(b) * WORDS_PER_SECOND * 0.75)
        if k > 1 and n < need:
            problems.append(f"beat {k + 1} {sp.beat_actions(b)} has {n} words; it needs at least {need} to show its actions")
        if n > 32:
            problems.append(f"beat {k + 1} has {n} words; max 32")
    words = sum(len(b["text"].split()) for b in beats)
    lo, hi = word_budget(set_id)
    if not lo <= words <= hi:
        problems.append(f"total narration is {words} words; it must be {lo}-{hi}")
    if beats and len(beats[0]["text"].split()) > HOOK_MAX_WORDS:
        problems.append(f"hook is {len(beats[0]['text'].split())} words; max {HOOK_MAX_WORDS}")
    stickers = sum(1 for b in beats if b.get("overlay", {}).get("type", "none") != "none")
    if stickers > 6:
        problems.append(f"{stickers} stickers; max 6")
    if beats and beats[0].get("overlay", {}).get("type", "none") != "none":
        problems.append("no sticker on the hook beat")
    if beats:
        q = closing_question(beats[-1]["text"])
        if not q:
            problems.append("the last beat must END with a short question to the viewer that invites comments")
        elif re.search(r"(comment|comments|like|subscribe|follow)", q, re.I):
            problems.append("the closing question must not mention comments, likes, subscribing or following")
        elif len(q.split()) > 14:
            problems.append(f"the closing question has {len(q.split())} words; keep it under 13")
    for b in beats:
        if not b["text"].strip():
            problems.append(f"beat {sp.beat_actions(b)} has no narration")
    return problems


def _rank(review, problems):
    """Sort key: renderable first, then the weakest score, then the average."""
    sc = review["scores"].values()
    return (not problems, min(sc), sum(sc) / len(sc))


def _ships(review, problems):
    sc = list(review["scores"].values())
    return not problems and bool(sc) and min(sc) >= SHIP_FLOOR


def develop(topic, facts):
    """Three competing drafts (different creative directions) → the editor picks the best →
    revise until it ships (max MAX_REVISIONS) → read-aloud polish. Returns (script, review)."""
    from concurrent.futures import ThreadPoolExecutor

    def draft_and_review(direction):
        script = write_script(topic, facts, direction=direction, effort="high")
        problems = hard_checks(script, topic["set"])
        return script, problems, critique_script(script, topic, facts, problems), direction

    directions = _directions(topic["set"])
    keep = 2 if QUALITY == "best" else 1
    directions = dict(list(directions.items())[:keep])
    earlier = _last_rejected(topic)
    if earlier:
        # a retry continues from the best script so far and its editor notes instead of drafting from
        # scratch: fresh drafts kept landing at the same scores and discarded the progress made
        log.info(f"[showrunner] continuing from the earlier best script: {json.dumps(earlier[2]['scores'])}")
        drafts = [(*earlier, "earlier best")]
    else:
        with ThreadPoolExecutor(max_workers=len(directions)) as pool:
            drafts = list(pool.map(draft_and_review, directions))
    for script, problems, review, direction in drafts:
        log.info(f"[showrunner] draft '{direction}': {json.dumps(review['scores'])} | hard problems: {len(problems)}")
    script, problems, review, direction = max(drafts, key=lambda d: _rank(d[2], d[1]))
    log.info(f"[showrunner] best draft: '{direction}'")
    best = (script, problems, review)
    revised = False
    trace = {}
    try:
        best, revised = _revise(topic, facts, script, problems, review, best, trace=trace)
    except UsageLimit as e:
        if not _ships(best[2], best[1]):
            raise
        log.warning(f"[showrunner] {e}; the best draft already passes, so revision is skipped")
    script, problems, review = best
    if problems:
        script, problems = repair_rules(script, topic["set"], problems)
    if problems:
        raise RuntimeError(f"no renderable script: {problems}")
    if not revised and QUALITY == "best":              # efficient mode avoids a redundant third call
        try:
            polished = polish(script, topic, facts)
            if not hard_checks(polished, topic["set"]):
                script = polished
        except UsageLimit as e:
            log.warning(f"[showrunner] {e}; skipping the polish pass")
    if not _ships(review, problems):
        _keep_rejected(topic, script, review, problems, last=trace.get("last"))
        raise RuntimeError(
            f"best script remained below the publication bar after revision: {json.dumps(review['scores'])}"
        )
    return script, review


def _keep_rejected(topic, script, review, problems, last=None):
    """Save a script that missed the bar WITH the editor's notes (output/films/_rejected/): the notes
    lived only in memory, so a failed script stage could not be diagnosed without paying to redo it."""
    try:
        folder = os.path.join(FILMS_DIR, "_rejected")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{datetime.datetime.now():%Y%m%d_%H%M%S}_{slug(script.get('title', 'script'))}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"set": topic.get("set"), "title": topic.get("title"), "script": script, "review": review,
                       "hard_problems": problems,
                       # the newest revision and ITS notes: a retry continues from here (continuing from the
                       # best-ranked script reused stale notes and repeated the same revision)
                       "last": {"script": last[0], "review": last[2]} if last else None},
                      fh, indent=1, ensure_ascii=False)
        log.info(f"[showrunner] rejected script and editor notes kept: {path}")
    except (OSError, TypeError, ValueError) as exc:
        log.warning(f"[showrunner] could not keep the rejected script: {exc}")


def _last_rejected(topic):
    """(script, hard problems, review) of the newest kept script for this same set and title, if any."""
    folder = os.path.join(FILMS_DIR, "_rejected")
    try:
        names = sorted((n for n in os.listdir(folder) if n.endswith(".json")), reverse=True)
    except OSError:
        return None
    for name in names:
        try:
            d = json.load(open(os.path.join(folder, name), encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if d.get("set") == topic.get("set") and d.get("title") == topic.get("title") and d.get("review"):
            best = (d["script"], hard_checks(d["script"], topic["set"]), d["review"])
            if _ships(best[2], best[1]):                 # already good enough: ship it, no more revising
                return best
            last = d.get("last") or {}
            if last.get("review"):
                return last["script"], hard_checks(last["script"], topic["set"]), last["review"]
            return best
    return None


def repair_rules(script, set_id, problems, attempts=2):
    """Minimal edits for mechanical rule breaks (word budget, hook length, a missing closing question...)
    of an otherwise finished script. A script one word over the budget used to fail the whole stage and
    restart drafting from scratch; this is one small call instead. Returns (script, remaining problems)."""
    for attempt in range(attempts):
        prompt = f"""{_rules(set_id)}

This finished script breaks these automatic rules:
{json.dumps(problems, ensure_ascii=False, indent=1)}

SCRIPT:
{json.dumps(script, ensure_ascii=False, indent=1)}

Return the same script with the SMALLEST edits that fix every rule above: keep every beat, its actions,
its overlay and every line that is not involved exactly as it is. When a word budget is exceeded, cut
a few filler words so the total lands well inside the limit (not on the boundary)."""
        try:
            fixed = _call(_style(set_id), prompt, SCRIPT_SCHEMA, effort="low")
        except (UsageLimit, BudgetExceeded):
            raise
        except Exception as exc:                         # noqa: BLE001  the unrepaired script still fails loudly
            log.warning(f"[showrunner] rule repair failed: {exc}")
            break
        fixed_problems = hard_checks(fixed, set_id)
        log.info(f"[showrunner] rule repair {attempt + 1}: {fixed_problems or 'all rules pass'}")
        if len(fixed_problems) < len(problems) or not fixed_problems:
            script, problems = fixed, fixed_problems
        if not problems:
            break
    return script, problems


def _revise(topic, facts, script, problems, review, best, trace=None):
    """Apply fresh editor notes and independently grade every revision.

    Re-grading costs one small call, but prevents a repaired script from being rejected with its
    predecessor's stale scores and gives the next revision precise, current feedback.
    """
    revised = False
    for round_ in range(MAX_REVISIONS):
        if _ships(review, problems):
            break
        fixed = write_script(topic, facts, previous=script, critique={
            "automatic_checks": problems, **review,
            "also": ("Fix every score below 8, not only the automatic checks. Read it aloud as a "
                     "voice actor: full, flowing, funny sentences with punchlines; polish rhythm. "
                     f"If narration is over budget, cut it decisively to {word_budget(topic['set'])[1] - 12} "
                     "words or fewer instead "
                     "of shaving only enough words to sit on the hard boundary. Stay inside the word "
                     "budget while fixing: take each editor line's IDEA in your own shorter words, and "
                     "when a beat cannot hold both its lesson and a gag, keep the lesson.")},
            effort="high")
        fixed_problems = hard_checks(fixed, topic["set"])
        new_review = critique_script(fixed, topic, facts, fixed_problems)
        log.info(f"[showrunner] revision {round_ + 1}: {json.dumps(new_review['scores'])} | "
                 f"hard problems: {fixed_problems or 0}")
        if _rank(new_review, fixed_problems) > _rank(best[2], best[1]):
            best, revised = (fixed, fixed_problems, new_review), True
        script, problems, review = fixed, fixed_problems, new_review
        if trace is not None:
            trace["last"] = (fixed, fixed_problems, new_review)
    return best, revised


# ------------------- 5. film JSON + run -------------------

def to_film(script, topic, facts, review=None):
    beats = []
    sp = sets.spec(topic["set"])
    for b in script["beats"]:
        acts = sp.beat_actions(b)
        beat = {"id": "+".join(acts), "action": acts[0], "text": b["text"].strip()}
        if len(acts) > 1:
            beat["actions"] = acts
        if acts[0] == "rewind":
            beat["video"] = "rewind"
        elif sp.ACTIONS[acts[0]]["kind"] == "hook":
            beat["video"] = "epilogue"
        ov = b.get("overlay") or {}
        if ov.get("type") == "label" and re.search(r"\d", str(ov.get("text", ""))):
            ov = {}                     # no counters/scores/"Fail #N" labels; numbers belong in real stats
        if sp.ACTIONS[acts[0]].get("label"):
            ov = {}                     # the scene already shows this beat's label: a sticker would stack on it
        if ov.get("type") == "stat" and ov.get("value"):
            beat["overlay"] = {"type": "stat", "value": ov["value"], "text": ov.get("text", "")}
        elif ov.get("type") == "label" and ov.get("text"):
            beat["overlay"] = {"type": "label", "text": ov["text"]}
        beats.append(beat)
    backend = active_backend()
    film = {"title": script["title"], "set": topic["set"], "voice": "energetic", "captions": "word",
            "music": "synth", "beats": beats, "cta": closing_question(beats[-1]["text"]) if beats else None,
            # story sets end on a reunion: hold the payoff after the last word so it can land
            "tail": 2.5 if getattr(sets.spec(topic["set"]), "HERO", None) else 1.2,
            "meta": {"angle": topic["angle"], "caption": script.get("caption", ""),
                     "hashtags": script.get("hashtags", []), "facts": facts, "review": review,
                     "created": datetime.datetime.now().isoformat(timespec="seconds"),
                     "model": CODEX_MODEL if backend == "codex" else CLI_MODEL}}
    from agents import buildup
    if buildup.enabled(topic["set"]):                  # starts on the first build step: no hook, no question
        film.update(buildup.film_extras())
    return film


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:48]


def run(angle=None, render=True, preview=False, set_id=None, topic_hint=None, on_topic=None):
    import time
    t0 = time.time()
    backend = active_backend()
    detail = f"codex exec, model {CODEX_MODEL}" if backend == "codex" else f"claude -p, model {CLI_MODEL}"
    fallback = (os.getenv("SHOWRUNNER_FALLBACK_BACKEND") or "").strip().lower()
    log.info(f"[showrunner] backend: {backend} ({detail}), quality: {QUALITY}"
             + (f", fallback: {fallback}" if fallback else ""))
    needed = ("title", "angle", "hook_line", "hook_action", "payoff", "trend_signal", "trend_source_url")
    hint_is_filmable = (topic_hint and set_id and all(topic_hint.get(k) for k in needed)
                        and topic_hint.get("hook_action") in sets.spec(set_id).ACTIONS)
    if hint_is_filmable:
        topic = {k: topic_hint[k] for k in needed}
        topic["set"] = set_id
        if topic_hint.get("fact_sheet"):
            topic["_fact_sheet"] = topic_hint["fact_sheet"]
        log.info(f"[showrunner] reusing the new-set trend brief: {topic['title']} | hook: {topic['hook_line']}")
    else:
        topic = pick_topic(set_ids=[set_id] if set_id else None, forced_angle=angle)
    if on_topic:
        on_topic(dict(topic))
    facts = research(topic)
    _ensure_extras(topic["set"])
    script, review = develop(topic, facts)
    log.info(f"[showrunner] script written in {(time.time() - t0) / 60:.1f} min")
    film = to_film(script, topic, facts, review)
    os.makedirs(FILMS_DIR, exist_ok=True)
    name = f"{datetime.date.today():%Y%m%d}_{slug(script['title'])}"
    path = os.path.join(FILMS_DIR, f"{name}.json")
    json.dump(film, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    log.info(f"[showrunner] script saved: {path}")
    from agents.codex_cli import TOTAL_USAGE, usage_summary
    if TOTAL_USAGE["calls"]:
        log.info(f"[showrunner] Codex subscription usage this process: {usage_summary()}")
    if CLAUDE_USAGE["calls"]:
        log.info(f"[showrunner] Claude subscription usage this process: {claude_usage_summary()} "
                 f"(API-equivalent reported by CLI: ~${_notional[0]:.2f})")
    for b in film["beats"]:
        log.info(f"   [{b['id']:>24}] {b['text']}")
    hist = _history()
    hist.append({"title": script["title"], "angle": topic["angle"], "hook": film["beats"][0]["text"],
                 "set": topic["set"], "film": path, "date": datetime.date.today().isoformat(),
                 "trend_signal": topic.get("trend_signal", ""),
                 "trend_source_url": topic.get("trend_source_url", "")})
    json.dump(hist, open(HISTORY, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    if not render:
        return path
    from engine.make_film import produce
    return produce(argparse.Namespace(film=path, reuse_voice=False, preview=preview, frames="", remix=False))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Pick the best topic, write a great script, render the film.")
    ap.add_argument("--angle", default=None, help="develop this angle instead of choosing one")
    ap.add_argument("--set", choices=sets.AVAILABLE, default=None, help="use one specific unused set")
    ap.add_argument("--no-render", action="store_true", help="stop after writing the script")
    ap.add_argument("--preview", action="store_true", help="render preview stills instead of the full film")
    a = ap.parse_args()
    print(run(angle=a.angle, render=not a.no_render, preview=a.preview, set_id=a.set))
