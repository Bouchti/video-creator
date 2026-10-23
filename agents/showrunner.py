"""
Showrunner: every run picks the BEST topic our 3D sets can film, researches it, writes a
creative + accurate cutaway-explainer script, has it critiqued and revised until it passes the
bar, saves a data-driven film JSON, and (optionally) renders it with engine/make_film.

    python -m agents.showrunner                  # pick topic → research → write → render
    python -m agents.showrunner --no-render      # stop after the script (review it first)
    python -m agents.showrunner --angle "why pools are never drained in spring"

Stages (all Claude Opus 5.5, adaptive thinking):
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

import anthropic
from dotenv import load_dotenv

from config.paths import get_env_path, get_output_dir
from engine import sets

load_dotenv(get_env_path())
log = logging.getLogger("pipeline")

MODEL = os.getenv("SHOWRUNNER_MODEL", "claude-opus-5-5")
WORDS_PER_SECOND = 2.4                 # measured: 206 words → 76.5 s; 198 words → 82.8 s (pauses)
TARGET_WORDS = (140, 185)              # ≈ 60–78 s with this voice
HOOK_MAX_WORDS = 13
PASS_SCORE = 8                         # every rubric score must reach this to ship
MAX_REVISIONS = 2
HISTORY = os.path.join(get_output_dir(), "explainer_history.json")
WISHLIST = os.path.join(get_output_dir(), "set_wishlist.json")
FILMS_DIR = os.path.join(get_output_dir(), "films")

_client = None


def client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


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
- Spoken English only: no emojis, no markdown, no stage directions, digits are fine."""


# ------------------- low-level call -------------------
#
# Two backends:
#   subscription (default): Claude Code's headless mode (`claude -p`) on your Claude Pro/Max
#       login — no API bill; it counts against the plan's usage limits instead.
#   api: the Anthropic API (pay per token, ~$2 per video). SHOWRUNNER_BACKEND=api to opt in.

BACKEND = os.getenv("SHOWRUNNER_BACKEND", "subscription")
CLI_MODEL = os.getenv("SHOWRUNNER_CLI_MODEL", "opus")
_API_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "CLAUDE_CODE_USE_BEDROCK",
            "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY")
_notional = [0.0]


def _call(system, prompt, schema=None, effort="high", tools=None, max_tokens=16000):
    if BACKEND == "api":
        return _call_api(system, prompt, schema, effort, tools, max_tokens)
    return _call_cli(system, prompt, schema, effort, web=bool(tools))


def _call_cli(system, prompt, schema=None, effort="high", web=False):
    """One call through Claude Code headless mode, authenticated with the claude.ai login.
    API credentials are stripped from its environment (your .env holds an API key: if it leaked
    through, Claude Code would bill the API instead of the subscription). Runs in an empty temp
    dir with no project settings, no MCP servers and no tools except web search when asked."""
    import shutil
    import subprocess
    import tempfile

    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("Claude Code CLI not found (install it and run `claude` once to log in), "
                           "or set SHOWRUNNER_BACKEND=api to use the paid API")
    env = {k: v for k, v in os.environ.items() if k not in _API_ENV}
    tools = ["WebSearch", "WebFetch"] if web else [""]
    with tempfile.TemporaryDirectory() as tmp:
        sys_file = os.path.join(tmp, "system.txt")
        with open(sys_file, "w", encoding="utf-8") as f:
            f.write(system)
        cmd = [exe, "-p", "--output-format", "json", "--model", CLI_MODEL, "--effort", effort,
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
    if data.get("is_error") or data.get("subtype") != "success":
        raise RuntimeError(f"claude -p error ({data.get('subtype')}): {str(data.get('result'))[:300]}")
    _notional[0] += float(data.get("total_cost_usd") or 0)
    if schema is not None:
        out = data.get("structured_output")
        return out if out is not None else json.loads(data["result"])
    return data["result"].strip()


def _call_api(system, prompt, schema=None, effort="high", tools=None, max_tokens=16000):
    """One Opus call. With `schema`: returns parsed JSON (structured output); otherwise text.
    Server-side fallbacks keep a false-positive refusal from killing a daily run."""
    kw = dict(model=MODEL, max_tokens=max_tokens, system=system,
              messages=[{"role": "user", "content": prompt}],
              thinking={"type": "adaptive"}, output_config={"effort": effort},
              betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    if schema is not None:
        kw["output_config"]["format"] = {"type": "json_schema", "schema": schema}
    if tools:
        kw["tools"] = tools
    messages = kw["messages"]
    for _ in range(6):                                   # server tools may pause long turns
        resp = client().beta.messages.create(**kw)
        if resp.stop_reason == "refusal":
            cat = getattr(resp.stop_details, "category", None) if resp.stop_details else None
            raise RuntimeError(f"Claude declined the request (category: {cat})")
        if resp.stop_reason != "pause_turn":
            break
        messages.append({"role": "assistant", "content": resp.content})
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("response hit max_tokens")
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return json.loads(text) if schema is not None else text


def _obj(props, required=None):
    return {"type": "object", "properties": props, "required": required or list(props),
            "additionalProperties": False}


S, I = {"type": "string"}, {"type": "integer"}


# ------------------- 1. topic -------------------

def _history():
    try:
        return json.load(open(HISTORY, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def _set_brief(set_id):
    sp = sets.spec(set_id)
    actions = "\n".join(f"  - {k} [{v['kind']}]: {v['shows']}" for k, v in sp.ACTIONS.items())
    facts = "\n".join(f"  - {k}: {v}" for k, v in sp.MODEL_FACTS.items())
    return (f"SET '{set_id}': {sp.SUBJECT}\nWhat the 3D model shows (fixed facts):\n{facts}\n"
            f"Actions (visual beats this set can play):\n{actions}")


TOPIC_SCHEMA = _obj({
    "candidates": {"type": "array", "items": _obj({
        "set": S, "title": S, "angle": S, "hook_line": S, "hook_action": S, "payoff": S,
        "hook_strength": I, "curiosity": I, "visual_fit": I, "novelty": I, "shareability": I})},
    "best": I,
    "wishlist": {"type": "array", "items": _obj({"topic": S, "hook_line": S, "set_needed": S})},
})


def pick_topic(set_ids=None, forced_angle=None):
    set_ids = set_ids or sets.AVAILABLE
    used = [h.get("title", "") + " | " + h.get("angle", "") for h in _history()][-40:]
    briefs = "\n\n".join(_set_brief(s) for s in set_ids)
    prompt = f"""Pick today's video.

{briefs}

Already published (do NOT repeat these angles or hooks):
{chr(10).join('- ' + u for u in used) or '- (nothing yet)'}

{'The producer asked for this angle; develop it: ' + forced_angle if forced_angle else ''}

Brainstorm 10 distinct ANGLES that these sets can film: different hooks and questions about the
same subject (why it is built that way, what goes wrong if..., the hidden part nobody sees, the
surprising number, the thing you should never do). For each: a working title, the angle, the hook
line (the first 2 seconds, at most 13 words, a true fact), which hook action opens it, the payoff
that closes the loop, and honest 1-10 scores for hook_strength, curiosity, visual_fit (how well
this set's actions can SHOW it), novelty (vs published) and shareability. Set `best` to the index
of the strongest overall (weight hook_strength and visual_fit most). Remember the film always shows
the whole build, but build steps that are not the point can be raced through as montages, so an
angle about the water, the soil or the machinery works as well as one about construction.

Also list 5 wishlist topics that would make outstanding cutaway videos but need a NEW set (for
example a gas station's underground tanks, a septic system, a water tower): topic, hook line, and
the set to build."""
    out = _call(STYLE, prompt, TOPIC_SCHEMA, effort="high")
    _save_wishlist(out.get("wishlist", []))
    cands = out["candidates"]
    best = cands[max(0, min(out["best"], len(cands) - 1))]
    if best["set"] not in set_ids:
        best["set"] = set_ids[0]
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
    sp = sets.spec(topic["set"])
    prompt = f"""Research facts for a short video.
Title: {topic['title']}
Angle: {topic['angle']}
Hook claim to verify: {topic['hook_line']}
Subject the 3D model shows: {sp.SUBJECT}

Search the web and return a compact FACT SHEET (plain text, max ~350 words): 8-15 bullet facts
with concrete numbers, each with its source domain in brackets. Start with a verdict on the hook
claim (TRUE / NEEDS REWORDING + the accurate wording). Prefer engineering, trade and government
sources. Include 2-3 surprising details that would delight a viewer."""
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 6}]
    try:
        facts = _call("You are a meticulous fact-checker for an engineering explainer channel.", prompt,
                      tools=tools, effort="medium")
    except (anthropic.BadRequestError, RuntimeError) as e:  # web search unavailable / failed
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
    "scores": _obj({"hook": I, "clarity": I, "story_flow": I, "fun": I, "accuracy": I, "pacing": I,
                    "visual_sync": I}),
    "problems": {"type": "array", "items": S},
    "line_edits": {"type": "array", "items": S},
    "verdict": {"type": "string", "enum": ["ship", "revise"]},
})


def _rules(set_id):
    sp = sets.spec(set_id)
    order = " → ".join(sp.BUILD_ORDER)
    return f"""STRUCTURE RULES (the renderer enforces them):
- Beat 1 = a hook action ({', '.join(k for k, v in sp.ACTIONS.items() if v['kind'] == 'hook')}): pick the one
  whose VISUAL matches your hook line (the viewer must see what the first words say); beat 2 = rewind.
- Then EVERY build action exactly once, in this order: {order}.
- Optional explainer actions may be inserted after their prerequisite (layers after dig; weight and
  flow after fill; cycle after flow). Optional outro (storm or glamour) can only be the last beat.
- Each action at most once. A beat plays ONE action, or a quick MONTAGE of 2-4 consecutive actions
  ("actions": ["gravel", "valve", "pipes"]): use montages to race through build steps that are not
  the point of your angle, so the story stays on the angle. Hook and rewind beats are single actions.
- A beat needs enough words for what it shows: at least (sum of its actions' minimum seconds) x
  {WORDS_PER_SECOND} x 0.75 words. No beat over 32 words. 10-17 beats in total.
- Word budget: {TARGET_WORDS[0]}-{TARGET_WORDS[1]} words in total (~{WORDS_PER_SECOND} words/s); a beat runs as
  long as its words, so give each action roughly its listed seconds x {WORDS_PER_SECOND} words. Hook <= {HOOK_MAX_WORDS} words.
- overlay: optional 2D sticker for that beat. type "stat" = a number that counts up (value like
  "50 tons", text like "of soil"); "label" = a short badge (text only). Use "none" on most beats,
  at most 6 stickers in total, never on the hook.
- Numbers must match the model facts: what is ON SCREEN is the model."""


DIRECTIONS = {
    "mystery": "Play it as a slow-burn mystery: the hook is a threat, every beat tightens the screw, "
               "the payoff is the reveal. Tense, cinematic, short lines.",
    "wry": "Play it as a dry, witty insider: understatement, deadpan asides, a running joke that pays "
           "off at the end. Warm and funny, never silly.",
    "numbers": "Play it numbers-first: every beat lands one jaw-dropping, picturable number or "
               "comparison. Punchy, rhythmic, almost like a countdown.",
}


def write_script(topic, facts, previous=None, critique=None, direction=None):
    set_id = topic["set"]
    prompt = f"""{_set_brief(set_id)}

{_rules(set_id)}

TOPIC: {topic['title']}
ANGLE: {topic['angle']}
HOOK IDEA: {topic['hook_line']}  (opens with action: {topic['hook_action']})
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
            prompt += f"\nCREATIVE DIRECTION: {DIRECTIONS[direction]}\n"
        prompt += "\nWrite the script. Make the hook impossible to scroll past and every beat earn its place."
    return _call(STYLE, prompt, SCRIPT_SCHEMA, effort="high")


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
    out = _call(STYLE, prompt, SCRIPT_SCHEMA, effort="medium")
    if [b["actions"] for b in out["beats"]] != [b["actions"] for b in script["beats"]]:
        return script                                   # polish must not restructure
    return out


def critique_script(script, topic, facts, hard_problems):
    prompt = f"""You are the channel's head editor. Grade this script ruthlessly (1-10 each): hook (would
it stop the scroll in 2 s?), clarity (a 12-year-old follows every beat), story_flow (each beat
answers the last and raises the next), fun (personality, wit, surprise, no filler), accuracy (every
claim matches the fact sheet or the model facts), pacing (no beat too long or rushed, total
length right), visual_sync (each beat's words match what that action shows).

{_set_brief(topic['set'])}

FACT SHEET:
{facts}

SCRIPT:
{json.dumps(script, ensure_ascii=False, indent=1)}

Automatic checks found: {hard_problems or 'nothing'}

List concrete problems and line edits (quote the line, give the better line). verdict = "ship"
only if every score is {PASS_SCORE}+ and there are no factual errors or rule breaks."""
    return _call(STYLE, prompt, CRITIQUE_SCHEMA, effort="high")


def hard_checks(script, set_id):
    sp = sets.spec(set_id)
    beats = script["beats"]
    problems = list(sp.validate(beats))
    for k, b in enumerate(beats):
        n = len(b["text"].split())
        need = int(sp.min_seconds(b) * WORDS_PER_SECOND * 0.75)
        if k > 1 and n < need:
            problems.append(f"beat {k + 1} {sp.beat_actions(b)} has {n} words; it needs at least {need} to show its actions")
        if n > 32:
            problems.append(f"beat {k + 1} has {n} words; max 32")
    words = sum(len(b["text"].split()) for b in beats)
    if not TARGET_WORDS[0] <= words <= TARGET_WORDS[1]:
        problems.append(f"total narration is {words} words; it must be {TARGET_WORDS[0]}-{TARGET_WORDS[1]}")
    if beats and len(beats[0]["text"].split()) > HOOK_MAX_WORDS:
        problems.append(f"hook is {len(beats[0]['text'].split())} words; max {HOOK_MAX_WORDS}")
    stickers = sum(1 for b in beats if b.get("overlay", {}).get("type", "none") != "none")
    if stickers > 6:
        problems.append(f"{stickers} stickers; max 6")
    if beats and beats[0].get("overlay", {}).get("type", "none") != "none":
        problems.append("no sticker on the hook beat")
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
    return not problems and (min(sc) >= PASS_SCORE or (min(sc) >= PASS_SCORE - 1 and sum(sc) / len(sc) >= PASS_SCORE))


def develop(topic, facts):
    """Three competing drafts (different creative directions) → the editor picks the best →
    revise until it ships (max MAX_REVISIONS) → read-aloud polish. Returns (script, review)."""
    from concurrent.futures import ThreadPoolExecutor

    def draft_and_review(direction):
        script = write_script(topic, facts, direction=direction)
        problems = hard_checks(script, topic["set"])
        return script, problems, critique_script(script, topic, facts, problems), direction

    with ThreadPoolExecutor(max_workers=len(DIRECTIONS)) as pool:
        drafts = list(pool.map(draft_and_review, DIRECTIONS))
    for script, problems, review, direction in drafts:
        log.info(f"[showrunner] draft '{direction}': {json.dumps(review['scores'])} | hard problems: {len(problems)}")
    script, problems, review, direction = max(drafts, key=lambda d: _rank(d[2], d[1]))
    log.info(f"[showrunner] best draft: '{direction}'")
    best = (script, problems, review)
    for round_ in range(MAX_REVISIONS):
        if _ships(review, problems):
            break
        script = write_script(topic, facts, previous=script, critique={"automatic_checks": problems, **review})
        problems = hard_checks(script, topic["set"])
        review = critique_script(script, topic, facts, problems)
        log.info(f"[showrunner] revision {round_ + 1}: {json.dumps(review['scores'])} | hard problems: {len(problems)}")
        if _rank(review, problems) > _rank(best[2], best[1]):
            best = (script, problems, review)
    script, problems, review = best
    if problems:
        raise RuntimeError(f"no renderable script: {problems}")
    polished = polish(script, topic, facts)
    if not hard_checks(polished, topic["set"]):
        script = polished
    if not _ships(review, problems):
        log.warning(f"[showrunner] best script scores {json.dumps(review['scores'])}: below the bar, shipping anyway")
    return script, review


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
        if ov.get("type") == "stat" and ov.get("value"):
            beat["overlay"] = {"type": "stat", "value": ov["value"], "text": ov.get("text", "")}
        elif ov.get("type") == "label" and ov.get("text"):
            beat["overlay"] = {"type": "label", "text": ov["text"]}
        beats.append(beat)
    return {"title": script["title"], "set": topic["set"], "voice": "energetic", "captions": "word",
            "music": "synth", "tail": 1.2, "beats": beats,
            "meta": {"angle": topic["angle"], "caption": script.get("caption", ""),
                     "hashtags": script.get("hashtags", []), "facts": facts, "review": review,
                     "created": datetime.datetime.now().isoformat(timespec="seconds"), "model": MODEL}}


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:48]


def run(angle=None, render=True, preview=False):
    log.info(f"[showrunner] backend: {BACKEND}" + (f" (claude -p, model {CLI_MODEL})" if BACKEND != "api" else ""))
    topic = pick_topic(forced_angle=angle)
    facts = research(topic)
    script, review = develop(topic, facts)
    film = to_film(script, topic, facts, review)
    os.makedirs(FILMS_DIR, exist_ok=True)
    name = f"{datetime.date.today():%Y%m%d}_{slug(script['title'])}"
    path = os.path.join(FILMS_DIR, f"{name}.json")
    json.dump(film, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    log.info(f"[showrunner] script saved: {path}")
    if BACKEND != "api":
        log.info(f"[showrunner] Claude usage: on your subscription (the same calls on the API would "
                 f"have cost ~${_notional[0]:.2f})")
    for b in film["beats"]:
        log.info(f"   [{b['id']:>24}] {b['text']}")
    hist = _history()
    hist.append({"title": script["title"], "angle": topic["angle"], "hook": film["beats"][0]["text"],
                 "set": topic["set"], "film": path, "date": datetime.date.today().isoformat()})
    json.dump(hist, open(HISTORY, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    if not render:
        return path
    from engine.make_film import produce
    return produce(argparse.Namespace(film=path, reuse_voice=False, preview=preview, frames="", remix=False))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Pick the best topic, write a great script, render the film.")
    ap.add_argument("--angle", default=None, help="develop this angle instead of choosing one")
    ap.add_argument("--no-render", action="store_true", help="stop after writing the script")
    ap.add_argument("--preview", action="store_true", help="render preview stills instead of the full film")
    a = ap.parse_args()
    print(run(angle=a.angle, render=not a.no_render, preview=a.preview))
