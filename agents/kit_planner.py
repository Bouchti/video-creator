"""
Plans a new Max story as a STORYBOARD in the kit's vocabulary (engine/kit/vocab.py): one researched,
structured call (live trend search + facts + the ladder), validated by agents/storyboard.py, with at most
one cheap structured correction if it breaks a rule. No code is written; the kit films it.

    plan = plan_kit_story()          # {"storyboard": {...}, "set_id": ..., title, hook_line, ...}
"""
import datetime
import json
import logging

from agents import storyboard as sbm
from engine.kit import vocab

log = logging.getLogger("pipeline")

S = {"type": "string"}
PLAN_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["title", "angle", "hook_line", "hook_action", "payoff", "trend_signal", "trend_source_url",
                 "fact_sheet", "storyboard"],
    "properties": {"title": S, "angle": S, "hook_line": S, "hook_action": S, "payoff": S, "trend_signal": S,
                   "trend_source_url": S, "fact_sheet": S, "storyboard": sbm.SCHEMA},
}


def vocabulary() -> str:
    """The kit's vocabulary as the planner sees it."""
    changes = "\n".join(f"  - {k}: {v['does']}" for k, v in vocab.CHANGES.items())
    events = "\n".join(f"  - {k} [{v['outcome']}]: {v['shows']}"
                       + (f" (needs: {', '.join(v['needs'])})" if v.get("needs") else "")
                       + (f" (barrier must be: {', '.join(vocab.EVENT_PROFILES[k])})" if k in vocab.EVENT_PROFILES
                          else "")
                       for k, v in vocab.EVENTS.items())
    return f"""THE 3D WORLD YOU CAN USE (the only one; it is pre-built and tested):
A cutaway riverbank seen from the front: a river on the left, the barrier Max builds in the middle, his
yard (house, trampoline, two kids) on the right, and a buried sand layer under it all. It fits levees,
dikes, flood walls, sea walls, flood berms and embankment dams. Max is a cheerful, overconfident DIY dad.

What Max can BUILD in a step (change):
{changes}

What can HAPPEN in a step (event):
{events}

Weather per step: {', '.join(vocab.WEATHER)}. Running gag: {', '.join(vocab.GAGS)} (the rubber duck).

STORY RULES (a validator enforces them):
- steps: first {{"kind": "setup", "change": "none", "event": "calm"}} (Max's promise on a calm day), then
  fail -> fix pairs (each fix answers exactly the failure before it), then one "finale" step with a
  holding event (storm_holds). 5-11 steps. The first build is "sand_wall" (in the first fail step).
- a fail step has a failing event; fix and finale steps have holding events.
- every fail/fix step has a short label naming its idea (max {vocab.LABEL_MAX} characters, e.g. CLAY CORE).
- hooks: 1-2 steps replayed first, before the rewind: a fail step (the funniest failure) and/or the finale.
- ids: snake_case, unique (e.g. fail_sand, fix_core, burrow_hook)."""


def _example() -> str:
    return json.dumps(sbm.LEVEE, indent=1)


def plan_kit_story(published: str = "- none", call=None) -> dict:
    """Research a timely subject this world can film and design its storyboard. Raises RuntimeError with
    the validator's problems if even the corrected storyboard is not renderable."""
    from agents import showrunner as sr
    call = call or sr._call
    prompt = f"""Today is {datetime.date.today().isoformat()}. Search current sources from the last 14 days for a
real news hook about flood barriers (levees, dikes, flood walls, sea walls, embankment dams, flood
season, a failure, an audit, a record flood) and design the next Max video in the world below.

{vocabulary()}

USED STORIES (never repeat their title or angle):
{published}

A REFERENCE STORYBOARD (the format; do not copy its ladder blindly, choose what fits today's news):
{_example()}

Return:
- title, angle, hook_line (13 words maximum; must match the hook step's visual), hook_action (the id of
  the hook you put first in storyboard.hooks), payoff
- trend_signal and the exact trend_source_url (http...) from your research
- fact_sheet: 8-12 bullets (max 250 words), each with a source domain, true to the research
- storyboard: the full storyboard in the schema; model_facts carry the facts the ladder teaches."""
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}]
    plan = call(sr.STORY_STYLE, prompt, PLAN_SCHEMA, effort="medium", tools=tools)
    sb = plan["storyboard"]
    problems = sbm.validate(sb)
    if problems:
        log.warning(f"[kit] storyboard needs a correction: {problems}")
        fix_prompt = f"""{vocabulary()}

This storyboard breaks these rules:
{json.dumps(problems, indent=1)}

STORYBOARD:
{json.dumps(sb, indent=1)}

Return the corrected storyboard: the smallest changes that fix every rule; keep its story and labels."""
        sb = call("You correct a storyboard so it follows its rules.", fix_prompt, sbm.SCHEMA, effort="low")
        problems = sbm.validate(sb)
        if problems:
            raise RuntimeError("the planned storyboard is not filmable: " + "; ".join(problems))
        plan["storyboard"] = sb
    url = str(plan.get("trend_source_url", ""))
    if not url.startswith(("http://", "https://")):
        raise RuntimeError("the plan has no verifiable trend source")
    hooks = [h["id"] for h in sb["hooks"]]
    if plan.get("hook_action") not in hooks:
        plan["hook_action"] = hooks[0]
    plan["set_id"] = sbm.set_id_for(sb)
    plan["subject"] = sb["subject"]
    log.info(f"[kit] planned: {plan['title']} | {len(sb['steps'])} steps | trend: {plan['trend_signal'][:120]}")
    return plan
