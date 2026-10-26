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
from datetime import datetime, timedelta
from dotenv import load_dotenv
from config.paths import get_env_path, get_output_dir, CLAUDE_MODEL

load_dotenv(get_env_path())
log = logging.getLogger("pipeline")

import anthropic
from tavily import TavilyClient

claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
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

def search_trending_subjects() -> list:
    """Search Tavily for fresh, viral-worthy subjects across multiple categories."""
    log.info("  Searching for trending subjects...")

    # Multiple search angles to find variety
    queries = [
        "fascinating untold history stories trending",
        f"surprising science discoveries {datetime.now().year}",
        "weird historical facts going viral",
        "mysterious unexplained phenomena recent",
        "incredible animal behaviors discovered",
        "lost ancient civilizations new findings",
    ]

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

You MUST submit your selection using the submit_topic_selection tool."""


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


def pick_topic(candidates: list, recently_used: list) -> dict:
    """Use Claude to select the best topic + angle from candidates."""
    log.info("  Selecting best topic with Claude...")

    used_titles = [t["topic"] for t in recently_used]

    user_prompt = f"""Pick ONE topic for today's viral short video.

CANDIDATES FROM SEARCH:
{json.dumps(candidates, indent=2)}

RECENTLY USED (avoid these or anything similar):
{json.dumps(used_titles, indent=2)}

Submit your selection using the submit_topic_selection tool. The topic should be a specific factual claim, not a generic subject. The angle should match what kind of topic it is."""

    response = claude.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1000,
        system=LEADER_SYSTEM_PROMPT,
        tools=[TOPIC_TOOL],
        tool_choice={"type": "tool", "name": "submit_topic_selection"},
        messages=[{"role": "user", "content": user_prompt}]
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_topic_selection":
            return block.input

    raise Exception("Leader Agent did not call the submit_topic_selection tool")


# ------------------- MAIN ENTRY -------------------

def find_todays_topic() -> dict:
    """Full Leader Agent flow. Returns dict with topic, angle, tone, rationale."""
    log.info("Leader Agent: finding today's topic...")

    # Get candidates
    candidates = search_trending_subjects()
    if not candidates:
        raise RuntimeError("Fresh trend research returned no candidates; refusing to use stale fallback topics")

    # Filter out recently used
    recently_used = load_used_topics()
    log.info(f"  Recently used count: {len(recently_used)}")

    # Let Claude pick
    selection = pick_topic(candidates, recently_used)
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
