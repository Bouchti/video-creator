"""
Leader Agent — picks today's trending topic + optimal angle.

Flow:
  1. Pulls 10-15 trending topics from Tavily search
  2. Filters out: politics, religion, unverifiable rumors, repeats from last 7 days
  3. Picks ONE topic with high view potential + good visual representation
  4. Auto-selects the best framing angle for that specific topic
  5. Returns a creative brief for the Script Agent
"""

import os
import json
import logging
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from config.paths import get_env_path, get_output_dir
from agents import ai_router

load_dotenv(get_env_path())
log = logging.getLogger("pipeline")

from tavily import TavilyClient

tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

USED_TOPICS_FILE = os.path.join(get_output_dir(), "used_topics.json")


# ------------------- TOPIC HISTORY -------------------

def load_used_topics() -> list:
    """Load topics used in the last 7 days to avoid repeats."""
    if not os.path.exists(USED_TOPICS_FILE):
        return []
    try:
        with open(USED_TOPICS_FILE) as f:
            data = json.load(f)
        cutoff = datetime.now() - timedelta(days=7)
        recent = [t for t in data if datetime.fromisoformat(t["date"]) > cutoff]
        return recent
    except Exception:
        return []


def save_used_topic(topic: str):
    """Append today's topic to the history file.
    Only recent topics (last 7 days) are kept because load_used_topics filters them.
    """
    used = load_used_topics()
    used.append({"topic": topic, "date": datetime.now().isoformat()})
    os.makedirs(os.path.dirname(USED_TOPICS_FILE), exist_ok=True)
    with open(USED_TOPICS_FILE, "w") as f:
        json.dump(used, f, indent=2)


# ------------------- TRENDING SEARCH -------------------

def search_trending_subjects(source: str | None = None) -> list:
    """Search Tavily for fresh, viral-worthy subjects across multiple categories."""
    log.info("  Searching for trending subjects...")

    # Multiple search angles to find variety
    queries = (
        [
            f"engineering infrastructure innovations discoveries {datetime.now().year}",
            "how machines work surprising engineering facts",
            "water energy transport technology engineering explainer",
            "civil engineering structures recent discovery",
            "architecture construction science innovation",
            "infrastructure mechanism surprising science",
        ]
        if source == "unreal" else
        [
            f"spectacular natural process science discovery {datetime.now().year}",
            "surprising geology weather ocean phenomenon visual explanation",
            "engineering machines materials visible science discovery",
            "plants growth movement time lapse science discovery",
            "unusual architecture infrastructure visual science",
            "spacecraft planets visible physical process discovery",
        ]
        if source == "local-ai" else
        [
            "fascinating untold history stories trending",
            f"surprising science discoveries {datetime.now().year}",
            "weird historical facts going viral",
            "mysterious unexplained phenomena recent",
            "incredible animal behaviors discovered",
            "lost ancient civilizations new findings",
        ]
    )

    all_results = []
    for q in queries:
        try:
            r = tavily.search(query=q, search_depth="advanced", max_results=5, time_range="week")
            for item in r.get("results", []):
                all_results.append({
                    "title": item.get("title", ""),
                    "snippet": item.get("content", "")[:300],
                    "url": item.get("url", "")
                })
        except Exception as e:
            log.warning(f"  Tavily query failed for '{q}': {e}")

    log.info(f"  Found {len(all_results)} candidate subjects")
    return all_results


def research_topic(topic: str) -> list[dict]:
    """Build a fresh evidence pack that the writer and critic must stay inside."""
    response = tavily.search(
        query=f'fact check authoritative sources "{topic}"',
        search_depth="advanced", max_results=6, time_range="month",
    )
    results = list(response.get("results", []))
    if len(results) < 2:
        corroboration = tavily.search(
            query=f'authoritative evidence "{topic}"', search_depth="advanced", max_results=6,
        )
        results.extend(corroboration.get("results", []))
    sources, seen = [], set()
    for item in results:
        if not item.get("url") or not item.get("content"):
            continue
        if item["url"] in seen:
            continue
        seen.add(item["url"])
        sources.append({
            "title": item.get("title", ""),
            "url": item["url"],
            "evidence": item["content"][:1200],
        })
    if len(sources) < 2:
        raise RuntimeError(f"Research returned only {len(sources)} usable source(s); need at least 2")
    return sources


# ------------------- TOPIC SELECTION -------------------

LEADER_SYSTEM_PROMPT = """You are an elite viral content strategist. You pick topics for a TikTok/YouTube Shorts channel that gets millions of views on history, science, and mystery content.

Given a list of candidate subjects from web search, your job is to pick ONE topic that will maximize views.

═══ TOPIC SELECTION CRITERIA ═══

REQUIRED for selection:
✓ Highly visual - a camera could film actual footage of this
✓ Surprising, counterintuitive, or mysterious
✓ Has a clear story arc with a payoff
✓ Confirmed factual (no legends, conspiracy theories, or disputed claims)
✓ NOT in the recently_used list

REJECT topics that are:
✗ Political, religious, or controversial
✗ Pure abstract concepts (theoretical physics, philosophy)
✗ Person-focused if no public-domain footage exists (avoid celebrity gossip)
✗ Already covered in recently_used list

═══ ANGLE SELECTION ═══

Once you pick the topic, choose ONE optimal framing angle:

- "story_behind" — for events, incidents, or unfolding narratives. "The Story Behind X..."
- "what_theyre_not_telling" — for myths, hidden truths, or counter-narratives. "What They're Not Telling You About X..."
- "3_things_unknown" — for objects, places, or topics with multiple surprising facts. "3 Things You Didn't Know About X..."
- "why_everyone_talking" — for trending phenomena that explode in popularity. "Why Everyone Is Talking About X..."

═══ TOPIC FORMAT ═══

The topic you output must be a SPECIFIC factual claim with intrinsic curiosity, not a generic subject.

GOOD topics:
- "The Pacific octopus that solved a Rubik's cube faster than most humans"
- "How a single Roman aqueduct in southern France still delivers water 2000 years later"
- "Why the Sahara desert was a green grassland just 6000 years ago"

BAD topics (too generic):
- "Octopus intelligence"
- "Roman engineering"
- "Ancient climate"

You MUST submit your selection as the structured output."""


TOPIC_TOOL = {
    "name": "submit_topic_selection",
    "description": "Submit your chosen topic and angle for today's video.",
    "input_schema": {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "Specific factual claim with intrinsic curiosity (1-2 sentences max)."
            },
            "angle": {
                "type": "string",
                "enum": ["story_behind", "what_theyre_not_telling", "3_things_unknown", "why_everyone_talking"],
                "description": "Optimal framing angle for this topic."
            },
            "tone": {
                "type": "string",
                "enum": ["mysterious", "epic", "shocking", "educational"],
                "description": "Emotional tone for the script."
            },
            "rationale": {
                "type": "string",
                "description": "1-2 sentences explaining why this topic will perform well."
            },
            "source_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "The url of every candidate above whose text you drew this topic from. "
                               "These become part of the evidence the script is held to, so list them "
                               "all, and do not list a candidate you did not use.",
            },
        },
        "required": ["topic", "angle", "tone", "rationale", "source_urls"]
    }
}


GROUNDED_TOPIC_TOOL = {
    "name": "submit_grounded_topic",
    "description": "Rewrite the topic so every specific in it is backed by the evidence pack.",
    "input_schema": {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "The topic rewritten to assert ONLY what the evidence supports, keeping "
                               "the most striking supported fact up front. One or two sentences.",
            },
            "kept": {
                "type": "array", "items": {"type": "string"},
                "description": "Each specific from the original topic that a source supports, followed "
                               "by the exact sentence from the evidence that states it.",
            },
            "dropped": {
                "type": "array", "items": {"type": "string"},
                "description": "Each specific removed because no source supports it, with the claim quoted.",
            },
            "usable": {
                "type": "boolean",
                "description": "True when what survives can still carry a short video on its own. False "
                               "when so much was dropped that only a thin or pointless story remains.",
            },
        },
        "required": ["topic", "kept", "dropped", "usable"],
    },
}


def ground_topic(topic: str, research: list[dict]) -> dict:
    """Rewrite the topic so the writer inherits only claims the evidence pack supports.

    The topic scout writes from the trend snippets plus its own background knowledge, BEFORE the
    evidence pack is fetched, so it routinely asserts specifics no source backs. On 2026-10-27 the
    Anak Krakatau topic asserted a 300 m height and a two-thirds flank collapse in December 2018
    that none of the six retrieved sources covered. The writer built the story's spine on them, the
    evaluator blocked every beat resting on them, and five drafting rounds could not recover because
    the premise itself was unsourced. Reconciling the two costs one call and saves all of them.
    """
    evidence = json.dumps(research or [], ensure_ascii=False, indent=2)
    prompt = f"""A topic was chosen for today's video before these sources were read. Your job is to
make the topic match the evidence, so the script writer is never asked to tell an unsourced story.

PROPOSED TOPIC:
{topic}

EVIDENCE PACK (the only facts the script will be allowed to use):
{evidence}

Work through the proposed topic one specific at a time — each height, date, count, measurement,
event, collapse, record, named instrument and cause.

For each one, SEARCH THE EVIDENCE TEXT ABOVE for a sentence that states it, and decide on that basis:
- Found one? Keep the claim, and quote that sentence. Wording need not match: "emerged in 1927" in a
  source supports "first broke through the sea in 1927". A date, number or name stated anywhere in
  the evidence is supported, even in passing.
- Found none? Drop it. Your own knowledge of the subject is NOT support, however certain you are,
  and neither is plausibility.
Do not drop a claim you have not looked for. Over-dropping leaves a thin topic and wastes a good
subject; the quote is how you prove to yourself that you checked.

Then rewrite the topic using only kept specifics, with the single most striking one at the front. Add
nothing the evidence does not state, and never hedge an unsupported claim into vagueness to keep it:
drop it outright. Set usable=false only when so little survives that no short video could be built
from it — not merely because the topic came out shorter than it went in."""
    result = ai_router.ask(
        "You are a fact-checking editor. You reconcile a proposed topic with the evidence that will "
        "be used to judge the finished script, and you never let an unsourced specific survive.",
        prompt, GROUNDED_TOPIC_TOOL["input_schema"], effort="medium")
    if not isinstance(result, dict) or not str(result.get("topic") or "").strip():
        raise RuntimeError("Topic grounding returned no rewritten topic")
    return result


def pick_topic(candidates: list, recently_used: list, source: str | None = None) -> dict:
    """Use the configured AI backend to select the best topic and angle."""
    log.info("  Selecting best topic with the configured AI backend...")

    used_titles = [t["topic"] for t in recently_used]

    from unreal_video.planner import capability_brief
    unreal_rules = """
UNREAL RENDERABILITY (mandatory):
- The video is filmed in ONE of these ready-made 3D sets, using only the actions listed. Pick a topic
  one set can show END TO END (its key mechanism is one of the set's actions); reject a topic whose
  key part the sets cannot show (e.g. a ram pump's valves, gears inside an engine, circuits):
""" + capability_brief() + """
- Pick a physical engineering mechanism or infrastructure process those actions can explain.
- Reject wars, politics, biographies, animals, archaeology narratives, breaking-news incidents,
  and any topic whose story depends on named people, faces, crowds, weapons, fire, or exact places.
- Prefer timeless cause-and-effect subjects such as how a pump, dam, bridge, foundation, turbine,
  water system, tunnel, or vehicle mechanism works. Fresh reporting may motivate the choice, but
  the selected topic itself must be a durable mechanism the renderer can show.
""" if source == "unreal" else """
AI-VIDEO REALISM (mandatory for the local-ai generator):
- The video generator looks real on physical, real-world subjects: nature, weather, space seen from
  Earth, machines, engineering, places, materials, animals in the wild, everyday objects.
- It looks fake on crowds, battles, armies, period costumes, close-up faces, hands doing fine work,
  and on-screen text. Prefer a candidate whose story can be told with few or no people; when people
  are essential, one or two figures seen at a distance beat crowds and close-ups.
- Reject topics whose payoff is invisible data, molecular bookkeeping, a list of numbered findings,
  or a comparison that only a chart can explain. The generator cannot make reliable diagrams or
  exact counts. Prefer a subject with observable physical stages and a payoff visible without text.
- The story must work without invented presenters, scientists, witnesses, or staged discoveries.
  Choose an object-led or process-led topic that neutral documentary scenes can show end to end.
- The camera must be able to STAND where the story happens, in ordinary air and daylight. The
  generator cannot hold a shot that is underwater, submerged, on the seafloor, on a reef, microscopic,
  inside a body, or visible only from orbit: within three seconds it drifts out, usually to dry land
  under a bright sky, and every shot of the video is rejected. Reject a topic whose essential setting
  is one of those, even when it is safe and interesting; narration alone cannot rescue it.
- Platform safety is about what the VIDEO SHOWS, not what the topic mentions. A war, a battle, a
  shipwreck or a death may be the occasion for the story, because the shots can show its cause,
  setting, machinery or aftermath: armies lowering their spears, a sky going dark, a burnt layer in
  the soil, an empty ruin, a tank rusting in a field. Choose such a framing and say so in the angle.
- Reject only subjects with no safe shot list at all: the casualties or the body count themselves
  (the deadliest/bloodiest X, a massacre, a mass grave), executions, torture, corpses, autopsies,
  amputation, suicide or self-harm, and sexual content. "Wildlife" is not automatically safe either:
  feeding, migration, nesting, play, cooperation, camouflage and construction are all suitable, but
  predation, prey capture, venom and animals eating their young are removed as animal cruelty.
""" if source == "local-ai" else ""

    base_prompt = f"""Pick ONE topic for today's viral short video.

CANDIDATES FROM SEARCH:
{json.dumps(candidates, indent=2)}

RECENTLY USED (avoid these or anything similar):
{json.dumps(used_titles, indent=2)}
{unreal_rules}

Submit your selection as the structured output. The topic should be a specific factual claim, not a generic subject. The angle should match what kind of topic it is."""

    rejected = []
    for _ in range(3):
        retry = ("\n\nREJECTED BY THE VIDEO RENDERER (do not choose these or close variants):\n- "
                 + "\n- ".join(rejected)) if rejected else ""
        selection = ai_router.ask(LEADER_SYSTEM_PROMPT, base_prompt + retry, TOPIC_TOOL["input_schema"])
        if not isinstance(selection, dict):
            raise ValueError("Leader Agent returned no topic selection")
        problem = local_ai_topic_problem(str(selection.get("topic") or "")) if source == "local-ai" else None
        if not problem:
            return selection
        rejected.append(f"{selection.get('topic', '')} — {problem}")
        log.warning("  Topic rejected before scripting: %s", problem)
    raise RuntimeError("Leader Agent could not select a local-AI-safe, visibly filmable topic")


# A platform ban is about what the VIDEO SHOWS, not what the topic mentions. script.py's CONTENT
# SAFETY block already forbids depicting pain, wounds, weapons or medical procedures in ANY shot and
# requires drama to be carried by objects, weather and motion. So a topic may mention a war, a battle
# or a death and still be filmed safely: armies lowering their spears, a sky going dark, an empty
# ruin, a bear mascot carrying crates. Blocking the mere words rejected two of the channel's own
# published videos ("Carried Shells Into Battle", "The Eclipse That Stopped a War") and, because
# pick_topic gives up after three rejections, made ordinary history unselectable.
#
# These two patterns therefore match only subjects that CANNOT be told without imagery the platforms
# remove. Keep them narrow: the visual layer is the real guard, this is the last resort.

_BANNABLE_SUBJECT = re.compile(
    r"\b(gore|gory|mutilat\w*|dismember\w*|behead\w*|decapitat\w*|disembowel\w*|"
    r"corpses?|cadavers?|autops(?:y|ies)|amputat\w*|"
    r"execution(?:s|ed)?|torture\w*|lynch\w*|massacres?|genocid\w*|atrocit(?:y|ies)|"
    r"suicid\w*|self[-\s]?harm|overdos\w*|"
    r"rape|sexual\w*|nudity|naked|porn\w*|"
    r"child\s+(?:abuse|soldiers?)|"
    r"graphic\s+(?:violence|injury|injuries|footage))\b",
    re.IGNORECASE,
)

# A conflict is filmable; its body count is not. "A battle happened" is fine, "the deadliest battle"
# makes the carnage itself the subject, and every shot would have to show it.
_CARNAGE_SUBJECT = re.compile(
    r"\b(bloodiest|deadliest|most\s+brutal|slaughter\w*|carnage|body\s+count|"
    r"death\s+toll|casualt(?:y|ies)|mass\s+grave(?:s)?)\b",
    re.IGNORECASE,
)

# Predation filmed close up is removed as animal cruelty even as natural history, so reject it when
# the harm is the subject rather than an incidental word ("how scorpions glow" stays selectable).
_PREDATION_SUBJECT = re.compile(
    r"\bprey\b|\bpredat(?:ion|or|ors|ory)\b|\bvenom(?:ous)?\b|\benvenomat\w*\b"
    r"|\bcannibal\w*\b"
    r"|\blive\s+(?:prey|insects?|scorpions?|snakes?|rodents?|mice|crickets?)\b"
    r"|\b(?:hunt|kill|stalk|ambush|devour|eats?|eating)\w*"
    r"(?:\s+(?:its|their|the|his|her))?(?:\s+own)?\s+"
    r"(?:prey|pups?|cubs?|chicks?|calves|calf|fawns?|hatchlings?|young|offspring|mates?)\b",
    re.IGNORECASE,
)


# Settings the short-clip generator cannot hold for three seconds, so EVERY shot of such a topic
# fails review. Measured on the 2026-10-27 "lost rivers under the Great Barrier Reef" run: asked to
# stay fully submerged, the model drifted to sunlit dry land with a blue sky, giving 143 fatal
# problems across 65 takes (54 "sky", 36 "land", 35 "morph"). Only 2 of 22 shots passed, 11 fell back
# to still push-ins, and the assembled video was rejected after 3h24m. Narration can describe such a
# place; a generated clip cannot be filmed there.
_LOCAL_AI_UNFILMABLE_SETTING = re.compile(
    r"\b(underwater|undersea|sub\s?sea|submerged|submarine|sunken|seafloor|sea\s?bed|"
    r"deep[-\s]?sea|abyssal|reefs?|shipwrecks?|"
    r"microscopic|microscope|subatomic|bloodstream|"
    r"under\s+(?:the\s+)?(?:sea|ocean|water|waves|ice|ice\s?sheet))\b",
    re.IGNORECASE,
)


def local_ai_topic_problem(topic: str) -> str | None:
    """Return why an automatic local-AI topic cannot be filmed, or None when it is safe to script."""
    match = _BANNABLE_SUBJECT.search(topic)
    if match:
        return (f"the subject '{match.group(0)}' cannot be shown without imagery the platforms remove; "
                f"no safe shot list exists for it")
    match = _CARNAGE_SUBJECT.search(topic)
    if match:
        return (f"'{match.group(0)}' makes the casualties themselves the subject, so every shot would "
                f"have to depict them. A conflict is fine when the video can show its cause, setting "
                f"or aftermath instead")
    match = _PREDATION_SUBJECT.search(topic)
    if match:
        return (f"'{match.group(0)}' makes an animal being harmed the subject, which is removed as "
                f"animal cruelty even as natural history. Feeding, migration, nesting, building, "
                f"play and camouflage are all fine")
    match = _LOCAL_AI_UNFILMABLE_SETTING.search(topic)
    if match:
        return (f"every shot would have to be set '{match.group(0)}', which the clip generator cannot "
                f"hold: it drifts to dry land under a bright sky within three seconds. Pick a subject "
                f"that can be filmed in ordinary air and daylight")
    return None


# ------------------- MAIN ENTRY -------------------

def cited_candidates(candidates: list, urls) -> list[dict]:
    """The trend items the scout drew the topic from, as evidence entries.

    These are what it actually read, so dropping them loses real support: research_topic() runs a
    fresh search on the whole topic paragraph and may return none of them back.
    """
    wanted = {str(u).strip() for u in (urls or []) if str(u).strip()}
    found = []
    for item in candidates:
        url = str(item.get("url") or "").strip()
        if url and url in wanted:
            found.append({"title": item.get("title", ""), "url": url,
                          "evidence": str(item.get("snippet") or "")[:1200]})
    return found


def _merge_sources(*groups) -> list[dict]:
    merged, seen = [], set()
    for group in groups:
        for item in group or []:
            url = str(item.get("url") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            merged.append(item)
    return merged


def find_todays_topic(source: str | None = None) -> dict:
    """Full Leader Agent flow. Returns dict with topic, angle, tone, rationale and research.

    The topic is reconciled with its evidence before it leaves this function, so STAGE 1 never has
    to write a story whose premise no source supports.
    """
    log.info("Leader Agent: finding today's topic...")

    candidates = search_trending_subjects(source=source)
    if not candidates:
        raise RuntimeError("Fresh trend research returned no candidates; refusing to use stale fallback topics")

    recently_used = load_used_topics()
    log.info(f"  Recently used count: {len(recently_used)}")

    rejected, attempts = [], max(1, int(os.getenv("LEADER_TOPIC_ATTEMPTS") or 3))
    for attempt in range(1, attempts + 1):
        selection = pick_topic(candidates, recently_used + rejected, source=source)
        # The candidates the scout read are evidence too; research_topic() searches the whole topic
        # paragraph and often returns none of them.
        research = _merge_sources(cited_candidates(candidates, selection.get("source_urls")),
                                  research_topic(selection["topic"]))
        log.info(f"  Evidence pack: {len(research)} source(s)")

        grounded = ground_topic(selection["topic"], research)
        for claim in grounded.get("dropped") or []:
            log.warning("  Unsourced claim dropped from the topic: %s", str(claim)[:160])
        if not grounded.get("usable"):
            reason = (f"too little of it is supported by the evidence "
                      f"({len(grounded.get('kept') or [])} claim(s) survived)")
            log.warning("  Topic abandoned after grounding: %s", reason)
            rejected.append({"topic": selection["topic"]})
            if attempt == attempts:
                raise RuntimeError(
                    f"No topic survived fact-grounding in {attempts} attempt(s). The trend search is "
                    f"returning subjects whose details the sources do not confirm.")
            continue
        if grounded["topic"].strip() != selection["topic"].strip():
            log.info("  Topic grounded to its sources (was: %s)", selection["topic"][:110])
        selection["original_topic"] = selection["topic"]
        selection["topic"] = grounded["topic"].strip()
        selection["grounding"] = grounded
        selection["research"] = research
        break

    log.info(f"  Topic: {selection['topic']}")
    log.info(f"  Angle: {selection['angle']}")
    log.info(f"  Tone:  {selection['tone']}")
    log.info(f"  Why:   {selection['rationale']}")

    return selection


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    result = find_todays_topic()
    log.info("\n" + "="*60)
    log.info(json.dumps(result, indent=2))
