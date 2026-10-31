"""
Explainer route (--source explainer): pure 3D cutaway explainers with NO hero, in the format of
channels like @youbuiltit. One continuous cut-open diorama, the build told in physical order as a
linear transformation from raw site to finished system, one visible component at a time.

    python main.py --source explainer                              # autopilot picks the topic
    python main.py --source explainer "Why pools have a valve in the floor"
    python main.py --source explainer --set pool
    python -m agents.explainer --no-render                          # stop after the script

This module only CHOOSES and WRITES; it reuses the showrunner's research, writing, critique and
film JSON (agents/showrunner.py picks the no-hero explainer voice, STYLE, for these sets) and the
Blender renderer (engine/films/cutaway_film.py via engine/make_film.py). The Max story route is
not touched: explainer sets live in their own registry, engine/sets EXPLAINER, and Max's
AVAILABLE list never sees them.

Topic flow:
  1. choose_set   a producer angle is matched to a registered explainer set (one cheap call); no
                  match means a new set is needed. Without an angle the showrunner scores every
                  unused explainer set against current trends.
  2. write        the showrunner researches, writes, critiques and saves the film JSON.
  3. new set      when no registered set fits (or every one is used up), a new one is made the way
                  Max stories are (SHOWRUNNER_SET_MODE=kit, the default): agents/kit_planner
                  plan_kit_explainer plans a trend-backed STORYBOARD in the tested kit's vocabulary
                  with "hero": false, and set_builder.build_kit_set compiles it, checks it with the
                  measured gates and registers it in EXPLAINER. No Blender code is written per video.
                  SHOWRUNNER_SET_MODE=agent keeps the old path: plan_new_set writes a build brief and
                  an agent codes a new set.

  EXPLAINER_MAX_USES=1   videos per explainer set before it counts as used (raise it to film new
                         angles on an existing set; SHOWRUNNER_ALLOW_REPEATS=1 ignores the limit)
"""
import argparse
import datetime
import json
import logging
import os
import re

from engine import sets

log = logging.getLogger("pipeline")


class NoUnusedExplainerSets(RuntimeError):
    """No registered explainer set can carry today's video; a new set has to be built."""


def max_uses() -> int:
    try:
        return max(1, int(os.getenv("EXPLAINER_MAX_USES") or 1))
    except ValueError:
        return 1


def registered() -> list:
    return list(getattr(sets, "EXPLAINER", []))


def usage(history=None) -> dict:
    """{set_id: number of explainer videos already written for it}."""
    from agents.showrunner import _history
    history = _history() if history is None else history
    counts = {}
    for item in history:
        set_id = item.get("set")
        if set_id in registered():
            counts[set_id] = counts.get(set_id, 0) + 1
    return counts


def unused_sets(history=None) -> list:
    """Registered explainer sets that may still carry a video."""
    if os.getenv("SHOWRUNNER_ALLOW_REPEATS", "0").lower() in ("1", "true", "yes"):
        return registered()
    used = usage(history)
    return [s for s in registered() if used.get(s, 0) < max_uses()]


# ------------------- 1. which set films this? -------------------

def _brief(set_id) -> str:
    sp = sets.spec(set_id)
    return f"- {set_id}: {sp.SUBJECT}"


MATCH_SCHEMA = {"type": "object", "properties": {"set": {"type": "string"}, "reason": {"type": "string"}},
                "required": ["set", "reason"], "additionalProperties": False}


def match_set(angle: str, candidates: list):
    """The candidate set whose 3D model can honestly film this angle, or None."""
    from agents import llm
    from agents.showrunner import STYLE
    if not candidates:
        return None
    prompt = f"""A producer wants a 3D cutaway explainer video about:
{angle}

Registered 3D sets (each can only film its own subject):
{chr(10).join(_brief(s) for s in candidates)}

Return `set` = the id of the ONE set whose subject this video is genuinely about, or "none" if the
video needs a different subject (a pool set cannot film a septic tank, a bridge or a dam). Give a
one-line reason."""
    out = llm.ask(STYLE, prompt, MATCH_SCHEMA, effort="low")
    choice = str(out.get("set", "")).strip()
    log.info(f"[explainer] angle → set: {choice or 'none'} ({out.get('reason', '')})")
    return choice if choice in candidates else None


def choose_set(angle=None, set_id=None):
    """Return a set id, "" (let the showrunner choose among the unused sets) or None (build a new one)."""
    if set_id:
        if set_id not in registered():
            raise NoUnusedExplainerSets(f"'{set_id}' is not a registered explainer set: {registered()}")
        return set_id
    candidates = unused_sets()
    if not candidates:
        return None
    if angle:
        return match_set(angle, candidates)
    return ""


# ------------------- 2. write -------------------

def write(angle=None, set_id=None, topic_hint=None, on_topic=None, render=False, preview=False):
    """Pick (or reuse) the topic, then let the showrunner research, write, critique and save the film."""
    from agents import showrunner as sr
    if set_id and set_id not in unused_sets() and not topic_hint:
        raise NoUnusedExplainerSets(
            f"explainer set '{set_id}' already carried {usage().get(set_id, 0)} video(s) "
            f"(EXPLAINER_MAX_USES={max_uses()})")
    hint = topic_hint
    if not hint:
        candidates = [set_id] if set_id else unused_sets()
        if not candidates:
            raise NoUnusedExplainerSets("every registered explainer set is used")
        try:
            topic = sr.pick_topic(set_ids=candidates, forced_angle=angle)
        except sr.NoUnusedStorySets as exc:         # no candidate has a strong, sourced trend today
            raise NoUnusedExplainerSets(str(exc)) from exc
        if topic["set"] not in candidates:
            topic["set"] = candidates[0]
        hint = dict(topic)
        if topic.get("_fact_sheet"):
            hint["fact_sheet"] = topic["_fact_sheet"]
        set_id = topic["set"]
    if hint.get("_fact_sheet") and not hint.get("fact_sheet"):
        hint = {**hint, "fact_sheet": hint["_fact_sheet"]}
    set_id = set_id or hint.get("set")
    return sr.run(angle=angle, render=render, preview=preview, set_id=set_id, topic_hint=hint,
                  on_topic=on_topic)


# ------------------- 3. a new subject that needs a new set -------------------

PLAN_SCHEMA = {
    "type": "object",
    "properties": {k: {"type": "string"} for k in (
        "subject", "title", "angle", "hook_line", "hook_action", "payoff", "trend_signal",
        "trend_source_url", "why_people_care_now", "build_brief", "fact_sheet")},
    "required": ["subject", "title", "angle", "hook_line", "hook_action", "payoff", "trend_signal",
                 "trend_source_url", "why_people_care_now", "build_brief", "fact_sheet"],
    "additionalProperties": False,
}


def new_set_id(subject: str) -> str:
    words = re.sub(r"\b(how|why|a|an|the|is|are|built|works?|inside|of)\b", " ", subject.lower())
    from config.paths import slug
    stem = slug(words, 26) or "new_cutaway"
    candidate, n = stem + "_explainer", 2
    here = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine", "sets")
    while os.path.exists(os.path.join(here, candidate + ".py")):
        candidate, n = f"{stem[:22]}_{n}_explainer", n + 1
    return candidate


def plan_new_set(angle=None) -> dict:
    """Research a subject no registered set covers and write the brief the set builder works from."""
    from agents import llm
    from agents.showrunner import _history, _wishlist
    from agents.buildup import STYLE
    published = "\n".join(f"- {h.get('set')}: {h.get('title')}" for h in _history()) or "- none"
    wishlist = "\n".join(f"- {i.get('topic')}: {i.get('set_needed')}" for i in _wishlist()[-30:]) or "- none"
    have = "\n".join(_brief(s) for s in registered()) or "- none"
    if angle:
        task = (f"The producer asked for this video: {angle}\nDevelop exactly that subject. A current trend "
                "signal is welcome but not required; leave trend_source_url empty if you find none.")
    else:
        task = ("Search current sources from the last 14 days and choose one genuinely new subject. Search "
                "home projects, infrastructure, construction, transport, energy, water and machines.")
    prompt = f"""Today is {datetime.date.today().isoformat()}. {task}

The video is a pure cutaway explainer with NO characters as heroes: the world is sliced open and
the camera starts at the raw site and follows how the thing is built in real installation order.
Each beat adds one visible component or shows the function that component unlocks. There is no
finished-state hook, rewind, wrong attempt, failure scene, repair, host or character story.

SETS WE ALREADY HAVE (never pick their subjects):
{have}

ALREADY PUBLISHED:
{published}

OLDER WISHLIST (inspiration only):
{wishlist}

Return:
- subject: a short concrete name for the thing being built or shown
- title: exactly the shape "How a <starting thing> Becomes a <finished system>"
- angle, opening hook_line (20 words maximum, starts "If you" and describes the first visible build
  step) and payoff
- hook_action: the snake_case id of the FIRST BUILD action (for example "excavate_site"); this is not
  a hook replay—the film starts on this action
- trend_signal and the direct trend_source_url from the research (empty only for a producer topic)
- why_people_care_now
- fact_sheet: 8-12 bullets (maximum 250 words), verified in this same search, a source domain or URL
  on every bullet, and a TRUE / NEEDS REWORDING verdict for hook_line
- build_brief: a self-contained production brief for ONE coherent cut-open diorama (ground in
  section, the structure, surroundings) that a Blender coder can build from primitives: 9-13 additive
  steps from empty site through excavation, base/foundation, main structure, connections, hidden
  internals, working flow and surface finish. Every step installs one visible part or demonstrates its
  newly available function. Explain constraints while the correct part goes in; never show a failure
  or redo. End on the finished working result with a little life (people for scale, water, lights), plus
  real dimensions, model numbers and short 3D component labels. No logos, brands or downloaded assets."""
    plan = llm.ask(STYLE, prompt, PLAN_SCHEMA, effort="medium", web=True)
    if not angle and not str(plan.get("trend_source_url", "")).startswith(("http://", "https://")):
        raise NoUnusedExplainerSets("fresh topic research returned no verifiable trend source; no set was built")
    plan["hook_action"] = re.sub(r"[^a-z0-9_]+", "_", str(plan.get("hook_action") or "prepare_site").lower()).strip("_")
    plan["set_id"] = new_set_id(plan["subject"])
    log.info(f"[explainer] new subject: {plan['subject']} ({plan['set_id']}) | trend: {plan.get('trend_signal')}")
    return plan


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description="Write (and optionally render) a no-hero cutaway explainer.")
    ap.add_argument("--angle", default=None)
    ap.add_argument("--set", default=None, help=f"one of {registered()}")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args()
    chosen = choose_set(a.angle, a.set)
    if chosen is None:
        if (os.getenv("SHOWRUNNER_SET_MODE") or "kit").strip().lower() == "kit":
            from agents.kit_planner import plan_kit_explainer
            print(json.dumps(plan_kit_explainer(angle=a.angle), indent=1, ensure_ascii=False))
            print("No registered explainer set fits: run `python main.py --source explainer` to film this "
                  "storyboard with the kit automatically.")
            return
        print(json.dumps(plan_new_set(a.angle), indent=1, ensure_ascii=False))
        print("No registered explainer set fits: build it with "
              "`python -m agents.set_builder --explainer \"<build_brief>\" --id <set_id>` "
              "or run `python main.py --source explainer` to do it automatically.")
        return
    print(write(a.angle, chosen or None, render=not a.no_render, preview=a.preview))


if __name__ == "__main__":
    main()
