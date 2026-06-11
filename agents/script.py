import anthropic
import json
import os
import logging
from dotenv import load_dotenv
from config.paths import get_env_path, CLAUDE_MODEL

load_dotenv(get_env_path())

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
log = logging.getLogger("pipeline")

# Pacing constants used to scale narration + scene count to a target duration.
WORDS_PER_SECOND = 2.4          # fast, energetic VO pace
SECONDS_PER_SCENE = 5.0         # each scene fills ~5s of the final video
MIN_SCENES, MAX_SCENES = 6, 18


def plan_for_duration(target_seconds: int, source: str = "hailuo") -> tuple:
    """Return (num_scenes, min_words, max_words) for a target video length."""
    if source == "comfy":
        # Shorter on-screen beats -> more storyboard scenes for 2s local clips.
        num_scenes = max(MIN_SCENES, min(25, round(target_seconds / 3.0)))
    else:
        num_scenes = max(MIN_SCENES, min(MAX_SCENES, round(target_seconds / SECONDS_PER_SCENE)))
    center = int(target_seconds * WORDS_PER_SECOND)
    return num_scenes, int(center * 0.85), int(center * 1.15)


# Define the exact schema as a tool — Claude MUST return valid JSON matching this
COMFY_SCENE_HINT = (
    "LOCAL AI VIDEO (ComfyUI): each scene MUST show a SPECIFIC, LITERAL, VISIBLE "
    "moment from the topic — name the real subjects (creatures, places, objects, "
    "people, era). A silent viewer must recognize the story. NO generic b-roll "
    "('cinematic landscape', 'mysterious atmosphere'). Chronological order must "
    "match the narration beat-for-beat."
)


def build_script_tool(num_scenes: int, min_words: int, max_words: int, source: str = "hailuo") -> dict:
    return {
        "name": "submit_video_script",
        "description": "Submit a complete viral video script with a CONNECTED sequence of scenes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "spoken_script": {
                    "type": "string",
                    "description": f"The voiceover narration. {min_words}-{max_words} words. One continuous, flowing story (not disconnected facts). High energy, hook-first. Use single quotes for any quoted speech inside."
                },
                "visual_style": {
                    "type": "string",
                    "description": (
                        "A SINGLE shared visual style + world anchor that ALL scenes share, so the "
                        "video looks like one cohesive film. Include: one cinematographer/film look, "
                        "ONE consistent color palette, ONE recurring main subject, ONE consistent "
                        "setting/world, and a consistent lighting mood. This string is appended to "
                        "EVERY scene prompt. Example: 'shot on 35mm, teal-and-amber grade, Denis "
                        "Villeneuve cinematography, a lone diver in a red suit as recurring subject, "
                        "deep-ocean world, soft volumetric god-rays, photoreal documentary look'."
                    )
                },
                "scenes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": num_scenes,
                    "maxItems": num_scenes,
                    "description": (
                        f"EXACTLY {num_scenes} scene prompts that form ONE CONTINUOUS, CONNECTED "
                        "journey through the SAME world with the SAME recurring subject — NOT "
                        "unrelated shots. Each scene flows from the previous one (same location/"
                        "subject, progressing in time or moving deeper). Vary only shot type and "
                        "camera angle; keep setting, subject, and palette consistent. Each scene = "
                        "[SHOT TYPE] + [subject, ONE clear action] + [environment] + [camera movement] "
                        "+ [atmosphere]. Do NOT restate the style (it is added automatically). "
                        + (COMFY_SCENE_HINT if source == "comfy" else "")
                    )
                },
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
                "target_duration": {"type": "integer", "description": "Target video length in seconds."},
                "pexels_queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": num_scenes,
                    "maxItems": num_scenes,
                    "description": (
                        f"EXACTLY {num_scenes} stock-footage search queries, ONE per scene, in the "
                        "same order. RULES, in priority order:\n"
                        "1. 1-2 words, lowercase, a CONCRETE filmable thing (object, place, action, "
                        "or creature) — never an abstract concept ('mystery', 'history', 'discovery').\n"
                        "2. Use COMMON stock-library words that thousands of clips exist for "
                        "('ancient ruins', 'bronze gears', 'ocean waves', 'city night'). NEVER proper "
                        "nouns or niche names ('Antikythera', a specific person/place) — they return "
                        "nothing; translate them to their generic visual instead.\n"
                        "3. Stay inside the SAME world/subject as the other scenes so the clips cut "
                        "together (e.g. all 'deep ocean' / 'ancient temple' shots), varying the "
                        "framing word per scene ('diver', 'coral', 'shipwreck', 'dark water')."
                    )
                }
            },
            "required": [
                "spoken_script", "visual_style", "scenes", "video_title",
                "description", "hashtags", "mood", "target_duration", "pexels_queries"
            ]
        }
    }


SYSTEM_PROMPT = """You are an elite viral content director. Your videos hit 10M+ views on TikTok and YouTube. You write like MrBeast scripts a documentary — high energy, zero filler, every line earns its place.

═══ VOICEOVER NARRATION ═══
- Match the requested word count (it sets the video length).
- HOOK (first 3 seconds, ~10 words): A shocking claim or mystery. Stop the scroll.
- ONE continuous story with a through-line — a beginning, build, and payoff. NOT a list of disconnected facts.
- Sensory language. Make people SEE it. Short punchy sentences mixed with longer builds. RHYTHM.
- Power words: insane, hidden, secret, lost, forbidden, impossible.
- Final line: cliffhanger or callback. Never generic 'follow for more'.

═══ FACTUAL ACCURACY ═══
- Only stated facts you are CERTAIN of. Skip disputed/legendary elements.
- Be conservative with names, dates, specific numbers.

═══ CONNECTED SCENES — THE MOST IMPORTANT RULE ═══

The scenes must feel like ONE CONTINUOUS FILM, not a slideshow of unrelated clips.

1. ONE WORLD: every scene happens in the SAME setting/world established in scene 1.
2. ONE RECURRING SUBJECT: the same main subject (a person, creature, vehicle, object) appears or is implied throughout.
3. CONTINUITY: each scene flows from the previous — moving deeper, later in time, or closer in — like a camera following a single journey. No hard context switches.
4. ONE LOOK: define a single `visual_style` (cinematographer, color palette, lighting, film look) — it is automatically appended to every scene, so DON'T repeat it inside scenes.
5. VARY ONLY shot type and camera angle (wide → tracking → close-up → overhead) to keep it dynamic, while setting + subject + palette stay constant.

Think of it as storyboarding a single 60-90 second short film, scene by scene, in order.

SCENE FORMULA (per scene): [SHOT TYPE] + [recurring subject, ONE clear action] + [same environment, progressed] + [camera movement] + [atmosphere: dust/fog/particles/light].

NARRATIVE ARC across the scenes:
- Opening scenes: establish the world + hook.
- Middle scenes: journey deeper / stakes rise.
- Final scenes: climax, then a resolving pull-back in the SAME world.

═══ CONTENT SAFETY (NON-NEGOTIABLE) ═══

The video generator REJECTS prompts with these. NEVER use:
- PAIN/HARM: pain, agony, suffering, screaming, writhing, contorted, blood, wound, burned, injured, bleeding, violent, attack
- WEAPONS: gun, knife, blade, weapon
- DISTRESSING: crying child, drowning, falling from height, medical procedures, sexual content

Show drama through OBJECTS (spilled liquid, swinging lanterns), ENVIRONMENT (storm clouds, swirling dust, flickering flames), and MOTION (rushing, sweeping, reaching) — NEVER through harm to a person.

You MUST submit the script using the submit_video_script tool. Do not write JSON yourself — call the tool with the structured arguments."""


def generate_script(
    topic: str, tone: str = "mysterious", target_seconds: int = 75, source: str = "hailuo"
) -> dict:
    """Generate a CONNECTED, target-length video script via Claude tool_use."""
    num_scenes, min_words, max_words = plan_for_duration(target_seconds, source=source)
    tool = build_script_tool(num_scenes, min_words, max_words, source=source)

    comfy_extra = ""
    if source == "comfy":
        comfy_extra = f"""
LOCAL AI VIDEO MODE:
- Each scene must depict a LITERAL on-screen moment from the story (who/what/where/when).
- Name concrete visible subjects from the topic in EVERY scene (not abstract mood words).
- Scene order must follow the narration chronologically — scene 1 = opening hook, last scene = payoff.
- {COMFY_SCENE_HINT}
"""

    prompt = f"""Create a viral {target_seconds}-second video about:

TOPIC: {topic}
TONE: {tone}
VIDEO SOURCE: {source}
{comfy_extra}
Write ONE continuous story for the narration ({min_words}-{max_words} words).
Then storyboard EXACTLY {num_scenes} CONNECTED scenes that follow a single subject through ONE
consistent world — each scene flowing from the last, like one short film. Define a single
shared `visual_style` that all scenes inherit. Submit with the submit_video_script tool."""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        tools=[tool],
        tool_choice={"type": "tool", "name": "submit_video_script"},
        messages=[{"role": "user", "content": prompt}]
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_video_script":
            return block.input

    raise Exception("Claude did not call the submit_video_script tool")


if __name__ == "__main__":
    test_topic = "The Antikythera mechanism — a 2000-year-old Greek device that predicted eclipses"
    log.info(f"Generating script for: {test_topic}")
    result = generate_script(test_topic, tone="mysterious", target_seconds=75)
    log.info(json.dumps(result, indent=2))
    log.info(f"Word count: {len(result['spoken_script'].split())}")
    log.info(f"Scenes: {len(result['scenes'])}")
