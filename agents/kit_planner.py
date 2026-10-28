"""
Plans a new Max story as a STORYBOARD in the kit's vocabulary (engine/kit/vocab.py): one researched,
structured call (live trend search + facts + the ladder), validated by agents/storyboard.py, with at most
one cheap structured correction if it breaks a rule. No code is written; the kit films it.

    plan = plan_kit_story()          # {"storyboard": {...}, "set_id": ..., title, hook_line, ...}
    plan = plan_kit_explainer()      # the same, for a no-hero cutaway explainer ("hero": false)
"""
import datetime
import json
import logging
import os

from agents import storyboard as sbm
from engine.kit import vocab

log = logging.getLogger("pipeline")

S = {"type": "string"}


def plan_schema(world: str = vocab.WORLD) -> dict:
    return {
        "type": "object", "additionalProperties": False,
        "required": ["title", "angle", "hook_line", "hook_action", "payoff", "trend_signal", "trend_source_url",
                     "fact_sheet", "storyboard"],
        "properties": {"title": S, "angle": S, "hook_line": S, "hook_action": S, "payoff": S, "trend_signal": S,
                       "trend_source_url": S, "fact_sheet": S, "storyboard": sbm.schema(world)},
    }


PLAN_SCHEMA = plan_schema()                 # the embankment's


def vocabulary(hero: bool = True, world: str = vocab.WORLD) -> str:
    """A world's vocabulary as the planner sees it (a no-hero explainer sees the same world without Max)."""
    w = vocab.for_world(world)
    changes = "\n".join(f"  - {k}: {v['does'] if hero else w.BUILT[k]}" for k, v in w.CHANGES.items())
    events = "\n".join(f"  - {k} [{v['outcome']}]: {v['shows']}"
                       + (f" (needs: {', '.join(v['needs'])})" if v.get("needs") else "")
                       + (f" ({w.THING} must be: {', '.join(w.EVENT_PROFILES[k])})" if k in w.EVENT_PROFILES
                          else "")
                       for k, v in w.EVENTS.items())
    description = (w.DESCRIPTION + "\n\nWhat Max can BUILD in a step (change):" if hero else
                   w.DESCRIPTION_NO_HERO + "\n\nWhat can be BUILT in a step (change):")
    opening = (f'- steps: first {{"kind": "setup", "change": "none", "event": "{w.CALM}"}} (Max\'s promise on a calm '
               'day),' if hero else
               '- steps: open on the crudest version that technically works, the first fail step building\n'
               f'  "{w.FIRST_BUILD}" (the video starts "If you <do the crudest thing>, you have a <thing>"), no '
               'setup step,')
    gags = f" Running gag: {', '.join(w.GAGS)}." if len(w.GAGS) > 1 else ""
    return f"""THE 3D WORLD YOU CAN USE (world "{world}"; it is pre-built and tested):
{description}
{changes}

What can HAPPEN in a step (event):
{events}

Weather per step: {', '.join(w.WEATHER)}.{gags}

STORY RULES (a validator enforces them):
{opening} then
  fail -> fix pairs (each fix answers exactly the failure before it), then one "finale" step with a
  holding event ({', '.join(w.FINALE_EVENTS)}). 5-11 steps. The first build is "{w.FIRST_BUILD}" (in the first
  fail step).
- a fail step has a failing event; fix and finale steps have holding events.
- every fail/fix step has a short label naming its idea (max {w.LABEL_MAX} characters, e.g. CLAY CORE).
- hooks: 1-2 steps replayed first, before the rewind: a fail step (the funniest failure) and/or the finale.
- ids: snake_case, unique (e.g. fail_sand, fix_core, burrow_hook)."""


def reference_storyboard(world: str = vocab.WORLD) -> dict:
    return sbm.LEVEE if world == vocab.WORLD else vocab.for_world(world).REFERENCE_STORYBOARD


def _example(hero: bool = True, world: str = vocab.WORLD) -> str:
    ref = reference_storyboard(world)
    if hero:
        return json.dumps(ref, indent=1)
    if world != vocab.WORLD:
        return json.dumps(dict(ref, hero=False), indent=1)
    example = dict(ref, title="How a Levee Keeps a River Out", steps=ref["steps"][1:], hero=False,
                   subject="an earthen river levee between a river and a backyard, built in physical order; the "
                           "riverbank is cut open so we see inside the ground")
    return json.dumps(example, indent=1)


def plan_kit_story(published: str = "- none", call=None, world: str = vocab.WORLD) -> dict:
    """Research a timely subject this world can film and design its storyboard. Raises RuntimeError with
    the validator's problems if even the corrected storyboard is not renderable."""
    return _plan(published, call, hero=True, world=world)


def plan_kit_explainer(published: str = "- none", angle: str = None, call=None, world: str = vocab.WORLD) -> dict:
    """The same plan for a no-hero cutaway explainer: the storyboard carries "hero": false, so the kit films
    it without Max and build_kit_set registers it as an EXPLAINER set. A producer `angle` steers the subject
    when this world can film it."""
    return _plan(published, call, hero=False, angle=angle, world=world)


def _plan(published, call, hero, angle=None, world=vocab.WORLD) -> dict:
    from agents import showrunner as sr
    call = call or sr._call
    news = vocab.for_world(world).NEWS
    if hero:
        task = "design the next Max video in the world below."
    else:
        task = ("design the next no-hero cutaway explainer in the world below: the build told in physical order, "
                "each real problem shown failing and answered by the real engineering fix.")
        if angle:
            task += f"\nThe producer asked for: {angle}\nFollow it wherever this world can honestly film it."
        from agents import buildup
        if (os.getenv("EXPLAINER_FORMAT") or buildup.FORMAT).strip().lower() == buildup.FORMAT:
            task += ('\nIt is a BUILD-UP explainer: hook_line is the opening sentence, starting "If you" and ending '
                     '"you have a <thing>" (at most 20 words), spoken over the first fail step.')
    prompt = f"""Today is {datetime.date.today().isoformat()}. Search current sources from the last 14 days for a
real news hook about {news} and {task}

{vocabulary(hero, world)}

USED {'STORIES' if hero else 'VIDEOS'} (never repeat their title or angle):
{published}

A REFERENCE STORYBOARD (the format; do not copy its ladder blindly, choose what fits today's news):
{_example(hero, world)}

Return:
- title, angle, hook_line (13 words maximum; must match the hook step's visual), hook_action (the id of
  the hook you put first in storyboard.hooks), payoff
- trend_signal and the exact trend_source_url (http...) from your research
- fact_sheet: 8-12 bullets (max 250 words), each with a source domain, true to the research
- storyboard: the full storyboard in the schema; model_facts carry the facts the ladder teaches."""
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}]
    plan = call(sr.STORY_STYLE if hero else sr.STYLE, prompt, plan_schema(world), effort="medium", tools=tools)
    sb = plan["storyboard"]
    if not hero:
        sb["hero"] = False                # not in the planner's schema: the route decides it, never the model
    problems = sbm.validate(sb)
    if problems:
        log.warning(f"[kit] storyboard needs a correction: {problems}")
        fix_prompt = f"""{vocabulary(hero, world)}

This storyboard breaks these rules:
{json.dumps(problems, indent=1)}

STORYBOARD:
{json.dumps(sb, indent=1)}

Return the corrected storyboard: the smallest changes that fix every rule; keep its story and labels."""
        sb = call("You correct a storyboard so it follows its rules.", fix_prompt, sbm.schema(world), effort="low")
        if not hero:
            sb["hero"] = False
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
