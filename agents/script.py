import anthropic
import json
import os
import logging
from dotenv import load_dotenv
from config.paths import get_env_path, CLAUDE_MODEL

load_dotenv(get_env_path())

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
log = logging.getLogger("pipeline")

# Define the exact schema as a tool — Claude MUST return valid JSON matching this
SCRIPT_TOOL = {
    "name": "submit_video_script",
    "description": "Submit a complete viral video script with all required fields.",
    "input_schema": {
        "type": "object",
        "properties": {
            "spoken_script": {
                "type": "string",
                "description": "The voiceover narration. 70-90 words. High energy, hook-first, with rhythm. Use single quotes for any quoted speech inside."
            },
            "scene_1": {"type": "string", "description": "5-second hook scene prompt — most visually striking image."},
            "scene_2": {"type": "string", "description": "5-second context scene prompt — establish the world."},
            "scene_3": {"type": "string", "description": "5-second tension scene prompt — something unexpected."},
            "scene_4": {"type": "string", "description": "5-second escalation scene prompt — raise stakes visually."},
            "scene_5": {"type": "string", "description": "5-second climax scene prompt — peak emotion."},
            "scene_6": {"type": "string", "description": "5-second resolution scene prompt — satisfying close."},
            "video_title": {"type": "string", "description": "SEO title that triggers curiosity. Max 100 chars."},
            "description": {"type": "string", "description": "Platform description with hook. Max 300 chars."},
            "hashtags": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 8,
                "maxItems": 12,
                "description": "10 relevant hashtags including the niche-specific ones."
            },
            "mood": {
                "type": "string",
                "enum": ["epic", "mysterious", "shocking", "emotional", "educational"]
            },
            "target_duration": {"type": "integer", "description": "30"},
            "pexels_queries": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 6,
                "maxItems": 8,
                "description": "6-8 simple 1-3 word search queries for Pexels stock footage. Each must be a CONCRETE NOUN that exists in stock libraries. Example: for a video about ocean waves, use ['ocean waves', 'crashing wave', 'sea storm', 'underwater coral', 'beach sunset', 'whale ocean']. NEVER use abstract concepts like 'mystery' or 'science' - only physical things a camera can film."
            }
        },
        "required": [
            "spoken_script", "scene_1", "scene_2", "scene_3", "scene_4",
            "scene_5", "scene_6", "video_title", "description", "hashtags",
            "mood", "target_duration", "pexels_queries"
        ]
    }
}


SYSTEM_PROMPT = """You are an elite viral content director. Your videos hit 10M+ views on TikTok. You write like MrBeast scripts a documentary — high energy, zero filler, every line earns its place.

═══ VOICEOVER NARRATION ═══
- 70-90 words. Voiceover at fast speed = ~30 seconds.
- HOOK (first 3 seconds, ~10 words): A shocking claim or mystery. Stop the scroll.
- Sensory language. Make people SEE it.
- Short punchy sentences. Mix 3-word bursts with 8-word builds. RHYTHM IS EVERYTHING.
- Drop dramatic ONE-WORD sentences. Like this. Bam.
- Power words: insane, hidden, secret, lost, forbidden, banned, impossible, terrifying.
- Final 3 seconds: cliffhanger or callback. Never generic 'follow for more'.

═══ FACTUAL ACCURACY ═══
- Only stated facts you are CERTAIN of. Skip disputed/legendary elements.
- Famous quotes: must be EXACT or paraphrased neutrally.
- Be conservative with names, dates, specific numbers.

═══ SCENE PROMPTS — CRITICAL FOR VISUAL QUALITY ═══

Each scene = 5 seconds. Total = 30 seconds. 6 scenes.

FORMULA: [SHOT TYPE] + [SUBJECT, ONE clear action] + [ENVIRONMENT] + [CINEMATIC STYLE REFERENCE] + [LIGHTING] + [CAMERA MOVEMENT] + [ATMOSPHERE/TEXTURE]

VARIETY RULES:
- Alternate shot types: extreme close-up → wide → medium → tracking → overhead → close-up
- Each scene DIFFERENT lighting (warm/cool, hard/soft)
- Each scene DIFFERENT camera movement
- Vary COLOR PALETTE across scenes

CINEMATIC ANCHORS — vary, don't repeat:
- 'Denis Villeneuve cinematography' (epic, atmospheric)
- 'David Fincher aesthetic' (cold, precise, dark)
- 'National Geographic documentary quality'
- 'Apple commercial style' (clean, polished)
- 'A24 horror film tone' (slow, unsettling)
- 'Christopher Nolan IMAX scale'
- 'Wes Anderson symmetry'
- 'Blade Runner 2049 neon'

LIGHTING SPECIFICITY:
- 'Single hard spotlight cutting through fog'
- 'Cold blue moonlight through tall windows'
- 'Warm sodium streetlight on wet pavement'
- 'Underwater god rays piercing deep blue'
- 'Sunset rim lighting from behind'
- 'Flickering firelight casting dancing shadows'

CAMERA MOVEMENT:
- 'Slow dolly push-in on subject hands'
- 'Smooth orbit 90 degrees around object'
- 'Crane shot rising from ground level'
- 'Handheld tracking shot following from behind'
- 'Static lock-off with subject moving through frame'

ATMOSPHERE — every scene needs ONE:
- Dust particles in light beams
- Fog rolling across floor
- Steam rising from surfaces
- Rain streaking glass
- Falling embers/ash
- Floating debris underwater

═══ CONTENT SAFETY (NON-NEGOTIABLE) ═══

Video generator REJECTS prompts with these. NEVER use:
- PAIN/HARM: pain, agony, suffering, screaming, writhing, contorted, blood, wound, burned, injured, bleeding, violent, attack
- WEAPONS: gun, knife, blade, weapon
- DISTRESSING: crying child, drowning, falling from height, medical procedures on body, sexual content

INSTEAD show drama through:
- OBJECTS: spilled liquid, knocked-over bottles, swinging lanterns
- ENVIRONMENT: storm clouds, swirling dust, flickering flames
- MOTION: rushing, sweeping, gripping, reaching (NOT 'in pain')

═══ SCENE FLOW ═══

Scene 1 — HOOK: most visually shocking image.
Scene 2 — CONTEXT: establish location/world.
Scene 3 — TENSION: something unexpected. Movement.
Scene 4 — ESCALATION: tighter framing. Stakes rise.
Scene 5 — CLIMAX: peak visual moment.
Scene 6 — RESOLUTION: pull back, symbolic close.

You MUST submit the script using the submit_video_script tool. Do not write JSON yourself — call the tool with the structured arguments."""


def generate_script(topic: str, tone: str = "mysterious") -> dict:
    """Generate a video script using Claude's tool_use for guaranteed valid JSON."""

    prompt = f"""Create a viral 30-second video about:

TOPIC: {topic}
TONE: {tone}

Make it CINEMATIC, dramatic, scroll-stopping. 70-90 words for the narration.
Each scene must look DIFFERENT from the others.
Submit your complete script using the submit_video_script tool."""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        tools=[SCRIPT_TOOL],
        tool_choice={"type": "tool", "name": "submit_video_script"},
        messages=[{"role": "user", "content": prompt}]
    )

    # Extract the tool call
    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_video_script":
            return block.input

    raise Exception("Claude did not call the submit_video_script tool")


if __name__ == "__main__":
    test_topic = "The Antikythera mechanism — a 2000-year-old Greek device that predicted eclipses"
    log.info(f"Generating script for: {test_topic}")
    result = generate_script(test_topic, tone="mysterious")
    log.info(json.dumps(result, indent=2))
    log.info(f"Word count: {len(result['spoken_script'].split())}")
    log.info(f"All keys present: {list(result.keys())}")
