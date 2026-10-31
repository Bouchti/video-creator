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


def plan_schema(world: str = vocab.WORLD, hero: bool = True) -> dict:
    return {
        "type": "object", "additionalProperties": False,
        "required": ["title", "angle", "hook_line", "hook_action", "payoff", "trend_signal", "trend_source_url",
                     "fact_sheet", "storyboard"],
        "properties": {"title": S, "angle": S, "hook_line": S, "hook_action": S, "payoff": S, "trend_signal": S,
                       "trend_source_url": S, "fact_sheet": S, "storyboard": sbm.schema(world, hero=hero)},
    }


PLAN_SCHEMA = plan_schema()                 # the embankment's Max-story schema


def vocabulary(hero: bool = True, world: str = vocab.WORLD) -> str:
    """A world's vocabulary as the planner sees it (a no-hero explainer sees the same world without Max)."""
    w = vocab.for_world(world)
    changes = "\n".join(f"  - {k}: {v['does'] if hero else w.BUILT[k]}" for k, v in w.CHANGES.items())
    event_items = ((k, val) for k, val in w.EVENTS.items() if hero or val["outcome"] == "hold")
    events = "\n".join(f"  - {k} [{v['outcome']}]: {v['shows']}"
                       + (f" (needs: {', '.join(v['needs'])})" if v.get("needs") else "")
                       + (f" ({w.THING} must be: {', '.join(w.EVENT_PROFILES[k])})" if k in w.EVENT_PROFILES
                          else "")
                       for k, v in event_items)
    description = (w.DESCRIPTION + "\n\nWhat Max can BUILD in a step (change):" if hero else
                   w.DESCRIPTION_NO_HERO + "\n\nWhat can be BUILT in a step (change):")
    opening = (f'- steps: first {{"kind": "setup", "change": "none", "event": "{w.CALM}"}} (Max\'s promise on a calm '
               'day),' if hero else
               f'- steps: exactly 9-13 additive construction steps. Step 1 has kind "build" and change '
               f'"{w.FIRST_BUILD}". Every middle step has kind "build"; the last has kind "finale".\n'
               '- hooks: [] exactly. The camera begins at the empty site and never jumps to the finished system.')
    gags = f" Running gag: {', '.join(w.GAGS)}." if len(w.GAGS) > 1 else ""
    story_rules = (
        "  then at least 3 distinct fail -> fix pairs (each fix answers exactly the failure before it), then one\n"
        f'  "finale" step with a holding event ({", ".join(w.FINALE_EVENTS)}). 8-11 steps. The first build is\n'
        f'  "{w.FIRST_BUILD}" (in the first fail step).\n'
        "- a fail step has a failing event; fix and finale steps have holding events.\n"
        "- keep every mistake simple: one visible failure and one plain-language physical reason per fail step.\n"
        "- hooks: 1-2 fail steps replayed first, before the rewind. Never hook with the happy finale."
        if hero else
        "- Build in real installation order from raw site to finished system. Add one visible component or show "
        "one newly available function per step. Use ONLY the holding events listed above; never stage a "
        "deliberately wrong version, breakage, disaster, fail/fix pair, host character, hook replay or rewind.\n"
        "- A problem may be explained in narration as the reason for the next component, but the VISUAL always "
        "shows the correct component being installed and then working. The last event is one of: "
        + ", ".join(w.FINALE_EVENTS) + "."
    )
    return f"""THE 3D WORLD YOU CAN USE (world "{world}"; it is pre-built and tested):
{description}
{changes}

What can HAPPEN in a step (event):
{events}

Weather per step: {', '.join(w.WEATHER)}.{gags}

STORY RULES (a validator enforces them):
{opening}
{story_rules}
- every non-finale step has a short label naming the visible component (max {w.LABEL_MAX} characters).
- ids: snake_case, unique."""


def reference_storyboard(world: str = vocab.WORLD) -> dict:
    return sbm.LEVEE if world == vocab.WORLD else vocab.for_world(world).REFERENCE_STORYBOARD


def _example(hero: bool = True, world: str = vocab.WORLD) -> str:
    ref = reference_storyboard(world)
    if hero:
        return json.dumps(ref, indent=1)
    return json.dumps(_linear_example(world), indent=1)


def _linear_example(world: str) -> dict:
    """Build a valid structural example from any world's vocabulary. It teaches the planner the linear
    contract without carrying the world's old fail/fix reference story into an explainer prompt."""
    w = vocab.for_world(world)
    ref = reference_storyboard(world)
    facts = list(ref.get("model_facts") or [])
    built, steps, profile = set(), [], "flat"
    holds = [(k, v) for k, v in w.EVENTS.items()
             if v["outcome"] == "hold" and k not in set(w.FINALE_EVENTS)]
    changes = [(w.FIRST_BUILD, w.CHANGES[w.FIRST_BUILD])]
    changes += [(k, change) for k, change in w.CHANGES.items() if k not in ("none", w.FIRST_BUILD)
                and any(set(change.get("adds", [])) & set(event.get("needs", [])) for _, event in holds)]

    def event_fits(event):
        allowed = w.EVENT_PROFILES.get(event)
        return set(w.EVENTS[event].get("needs", [])) <= built and (not allowed or profile in allowed)

    def usable_event(preferred=None, new_flags=()):
        if preferred and preferred in w.EVENTS and w.EVENTS[preferred]["outcome"] == "hold" \
                and event_fits(preferred):
            return preferred
        linked = [k for k, ev in holds if event_fits(k) and set(ev.get("needs", [])) & set(new_flags)]
        if linked:
            return linked[0]
        return next((k for k, _ev in holds if event_fits(k)), w.CALM)

    for n, (change, ch) in enumerate(changes, 1):
        new_flags = set(ch.get("adds", []))
        built.update(new_flags)
        profile = ch.get("profile") or profile
        event = usable_event(w.CALM if n == 1 else None, new_flags)
        label = change.replace("_", " ").upper()[:w.LABEL_MAX]
        steps.append({"id": f"build_{change}"[:31], "kind": "build", "change": change,
                      "event": event, "weather": w.WEATHER[0], "label": label})
    available = [k for k, _ev in holds if event_fits(k)]
    while len(steps) < 8:
        event = available[len(steps) % len(available)] if available else w.CALM
        steps.append({"id": f"show_function_{len(steps) + 1}", "kind": "build", "change": "none",
                      "event": event, "weather": w.WEATHER[0],
                      "label": event.replace("_", " ").upper()[:w.LABEL_MAX]})
    steps.append({"id": "finished_system", "kind": "finale", "change": "none",
                  "event": w.FINALE_EVENTS[0], "weather": w.WEATHER[0], "label": "FINISHED"})
    return {"world": world, "subject": ref.get("subject") or w.THING,
            "title": f"How an Empty Site Becomes a {str(w.THING).title()}",
            "model_facts": facts, "gag": "none" if "none" in w.GAGS else w.GAGS[0],
            "steps": steps[:13], "hooks": []}


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
        task = ("design the next no-hero linear construction explainer in the world below. Start with the raw "
                "site and visibly add the real system in installation order, one component or function per beat. "
                "Never stage the wrong version failing and never use a host character.")
        if angle:
            task += f"\nThe producer asked for: {angle}\nFollow it wherever this world can honestly film it."
        from agents import buildup
        if (os.getenv("EXPLAINER_FORMAT") or buildup.FORMAT).strip().lower() == buildup.FORMAT:
            task += ('\nIt is a LINEAR BUILD-UP explainer: title must be "How a <starting thing> Becomes a '
                     '<finished system>". hook_line is the opening sentence, starting "If you" and ending '
                     '"you have a <thing>" (at most 20 words), spoken over the first construction step.')
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
    if hero:
        style = sr.STORY_STYLE
    else:
        from agents import buildup
        style = buildup.STYLE
    plan = call(style, prompt, plan_schema(world, hero=hero), effort="medium", tools=tools)
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
        sb = call("You correct a storyboard so it follows its rules.", fix_prompt,
                  sbm.schema(world, hero=hero), effort="low")
        if not hero:
            sb["hero"] = False
        problems = sbm.validate(sb)
        if problems:
            raise RuntimeError("the planned storyboard is not filmable: " + "; ".join(problems))
        plan["storyboard"] = sb
    url = str(plan.get("trend_source_url", ""))
    if not url.startswith(("http://", "https://")):
        raise RuntimeError("the plan has no verifiable trend source")
    if hero:
        hooks = [h["id"] for h in sb["hooks"]]
        if plan.get("hook_action") not in hooks:
            plan["hook_action"] = hooks[0]
    else:
        plan["hook_action"] = sb["steps"][0]["id"]
    plan["set_id"] = sbm.set_id_for(sb)
    plan["subject"] = sb["subject"]
    log.info(f"[kit] planned: {plan['title']} | {len(sb['steps'])} steps | trend: {plan['trend_signal'][:120]}")
    return plan
