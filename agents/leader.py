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
        },
        "required": ["topic", "angle", "tone", "rationale"]
    }
}


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
- Reject predation, hunting, prey capture, venom, stings, death, injury, medical procedures, battles,
  weapons, disasters involving victims, or any subject whose essential facts require harmful imagery
  or safety-filtered words. "Wildlife" is not automatically safe: feeding, migration, nesting, play,
  cooperation, camouflage, and construction are suitable; hunting and prey training are not.
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


_LOCAL_AI_BLOCKED_TOPIC = re.compile(
    r"\b(hunt(?:s|ed|ing)?|prey|predat(?:or|ion|ory)|kill(?:s|ed|ing)?|dead|death|dying|"
    r"venom(?:ous)?|sting(?:s|ing|er)?|scorpions?|attack(?:s|ed|ing)?|injur(?:y|ed|ies)|"
    r"blood|wound(?:s|ed)?|weapon(?:s)?|battle(?:s)?|war|surgery|medical procedure)\b",
    re.IGNORECASE,
)


def local_ai_topic_problem(topic: str) -> str | None:
    """Return why an automatic local-AI topic would trip visual safety filters."""
    match = _LOCAL_AI_BLOCKED_TOPIC.search(topic)
    return f"essential subject contains safety-filtered concept '{match.group(0)}'" if match else None


# ------------------- MAIN ENTRY -------------------

def find_todays_topic(source: str | None = None) -> dict:
    """Full Leader Agent flow. Returns dict with topic, angle, tone, rationale."""
    log.info("Leader Agent: finding today's topic...")

    # Get candidates
    candidates = search_trending_subjects(source=source)
    if not candidates:
        raise RuntimeError("Fresh trend research returned no candidates; refusing to use stale fallback topics")

    # Filter out recently used
    recently_used = load_used_topics()
    log.info(f"  Recently used count: {len(recently_used)}")

    # Let Claude pick
    selection = pick_topic(candidates, recently_used, source=source)
    selection["research"] = research_topic(selection["topic"])

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
