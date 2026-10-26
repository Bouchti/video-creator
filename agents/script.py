import anthropic
import json
import os
import logging
from dotenv import load_dotenv
from config.paths import get_env_path, CLAUDE_MODEL
from agents.animate import CAMERA_MOVES
from agents.beats import DIAGRAM_TEMPLATES, OVERLAY_TYPES, narration_from_beats, repair_beats

# "animated": every beat is a generated Pixar-style 3D scene, animated in 2.5D.
# "footage": stock footage, real photos, and diagrams (the --source pexels path).
SCRIPT_MODES = ("animated", "footage", "local-ai")

load_dotenv(get_env_path())

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
log = logging.getLogger("pipeline")

# Pacing constants used to scale narration + beat count to a target duration.
WORDS_PER_SECOND = 2.1          # measured: ElevenLabs reads ~2.05 words/s (182 words -> 89s)
SECONDS_PER_BEAT = 3.0          # one visual per ~3s of narration
MIN_BEATS, MAX_BEATS = 8, 36


def plan_for_duration(target_seconds: int) -> tuple:
    """Return (num_beats, min_words, max_words) for a target video length."""
    num_beats = max(MIN_BEATS, min(MAX_BEATS, round(target_seconds / SECONDS_PER_BEAT)))
    center = int(target_seconds * WORDS_PER_SECOND)
    return num_beats, int(center * 0.85), int(center * 1.15)


def beat_word_range(num_beats: int, min_words: int, max_words: int) -> tuple:
    """Words per beat that keep the TOTAL inside min_words..max_words."""
    return max(3, min_words // num_beats), max(5, -(-max_words // num_beats))


VISUAL_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {
            "type": "string", "enum": ["footage", "photo", "diagram"],
            "description": "photo = a specific real named thing; diagram = numbers, dates, "
                           "processes, comparisons, ideas; footage = a generic filmable action/place.",
        },
        "description": {
            "type": "string",
            "description": "LITERALLY what is on screen, matching the beat's words "
                           "(e.g. 'divers lifting a corroded bronze lump from the seabed').",
        },
        "queries": {
            "type": "array", "items": {"type": "string"},
            "description": "photo/footage only: 2-3 search queries, MOST SPECIFIC first. Photo: the "
                           "exact name first ('Antikythera mechanism'), then broader. Footage: concrete "
                           "stock phrases ('scuba diver shipwreck', 'diver underwater').",
        },
        "on_screen_text": {
            "type": "string",
            "description": "Optional 1-4 word label over a photo/footage (a name, year, place) — "
                           "only a fact stated in this beat.",
        },
        "template": {"type": "string", "enum": list(DIAGRAM_TEMPLATES),
                     "description": "diagram only."},
        "text": {"type": "string", "description": "key_phrase: the phrase (max 8 words)."},
        "title": {"type": "string", "description": "Optional diagram header (max 6 words)."},
        "value": {"type": "string",
                  "description": "stat: the number as shown, e.g. '400°C', '2,000 years', '$4.2B'."},
        "label": {"type": "string", "description": "stat: what the number measures (max 8 words)."},
        "steps": {"type": "array", "items": {"type": "string"},
                  "description": "process: 2-6 step labels, max 4 words each."},
        "active_step": {"type": "integer", "description": "process: 1-based step this beat talks about."},
        "events": {
            "type": "array",
            "items": {"type": "object",
                      "properties": {"year": {"type": "string"}, "label": {"type": "string"}},
                      "required": ["year", "label"]},
            "description": "timeline: 2-6 events in order.",
        },
        "active_event": {"type": "integer", "description": "timeline: 1-based event this beat talks about."},
        "items": {
            "type": "array",
            "items": {"type": "object",
                      "properties": {"label": {"type": "string"}, "value": {"type": "number"},
                                     "display": {"type": "string"}},
                      "required": ["label", "value"]},
            "description": "comparison: 2-4 items; value is numeric, display is the shown text ('120 km/h').",
        },
    },
    "required": ["kind", "description"],
}


SCENE_VISUAL_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["scene"]},
        "description": {
            "type": "string",
            "description": "The ONE moment the picture shows, literally depicting this beat's words: "
                           "which character (by name) does what, where, with which objects, and the "
                           "framing (wide shot / close-up / top-down / low angle). Concrete and visual. "
                           "No text, signs, or numbers inside the picture.",
        },
        "camera": {"type": "string", "enum": list(CAMERA_MOVES),
                   "description": "Camera move that fits the action."},
        "overlay": {
            "type": "object",
            "description": "Optional animated sticker for a number or name SAID in this beat.",
            "properties": {
                "type": {"type": "string", "enum": list(OVERLAY_TYPES)},
                "value": {"type": "string", "description": "stat: the number as said, e.g. '2 m', '8 weeks'."},
                "text": {"type": "string",
                         "description": "label: the name/term (max 3 words); stat: what it measures."},
            },
            "required": ["type"],
        },
    },
    "required": ["kind", "description", "camera"],
}


LOCAL_AI_VISUAL_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["scene"]},
        "continuity_in": {
            "type": "string",
            "description": "Exact visible state inherited from the previous shot: character pose and position, prop positions, lighting, and environment.",
        },
        "description": {
            "type": "string",
            "description": "Production-ready description of one physical three-second shot: named character, action, connected location, recurring props, composition, lighting, and depth. No dialogue or text.",
        },
        "continuity_out": {
            "type": "string",
            "description": "Exact final pose, position, gaze, prop state, and camera direction that the next shot inherits.",
        },
        "camera": {
            "type": "string",
            "enum": list(CAMERA_MOVES),
            "description": "One motivated camera move that reveals or follows the current action.",
        },
        "transition": {
            "type": "string",
            "enum": ["cut", "match_cut", "crossfade"],
            "description": "Story-motivated edit into this shot. Use cut by default, match_cut only for matching shape/action, and crossfade only for a real passage of time.",
        },
    },
    "required": ["kind", "continuity_in", "description", "continuity_out", "camera", "transition"],
}


def build_script_tool(num_beats: int, min_words: int, max_words: int, mode: str = "footage") -> dict:
    lo, hi = beat_word_range(num_beats, min_words, max_words)
    scene_mode = mode in {"animated", "local-ai"}
    extra = {}
    if scene_mode:
        extra["characters"] = {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "description": "Recurring people or animals the viewer follows. Do not list lights, "
                           "places, or objects as characters. `look` is a fixed visual description "
                           "reused in every image (age, build, clothes + colours, hair).",
            "items": {"type": "object",
                      "properties": {"name": {"type": "string"}, "look": {"type": "string"}},
                      "required": ["name", "look"]},
        }
    if mode == "local-ai":
        extra.update({
            "story_premise": {
                "type": "string",
                "description": "Two precise sentences establishing the protagonist, inciting event, goal, and direction.",
            },
            "protagonist_goal": {
                "type": "string",
                "description": "The concrete physical goal pursued throughout the sequence.",
            },
            "stakes": {
                "type": "string",
                "description": "What visibly changes or is lost if the protagonist fails.",
            },
            "ending_payoff": {
                "type": "string",
                "description": "The final visible cause-and-effect resolution that pays off the opening without a random twist.",
            },
            "location": {
                "type": "string",
                "description": "A fixed physical world description reused across every shot: geography, architecture, scale, and recurring props.",
            },
            "time_of_day": {
                "type": "string",
                "description": "One consistent time and lighting condition for the whole sequence.",
            },
            "color_palette": {
                "type": "string",
                "description": "A restrained recurring color palette for every shot.",
            },
            "recurring_objects": {
                "type": "array",
                "minItems": 1,
                "maxItems": 6,
                "items": {"type": "string"},
                "description": "Fixed story props with immutable appearance and state rules, reused across shots.",
            },
        })
    return {
        "name": "submit_video_script",
        "description": "Submit a complete viral video script as narration beats, each with the visual shown while it is spoken.",
        "input_schema": {
            "type": "object",
            "properties": {
                "beats": {
                    "type": "array",
                    "minItems": num_beats if mode == "local-ai" else max(MIN_BEATS - 2, num_beats - 2),
                    "maxItems": num_beats if mode == "local-ai" else num_beats + 2,
                    "description": (
                        f"About {num_beats} beats IN ORDER. All beat texts joined ARE the voiceover "
                        f"({min_words}-{max_words} words total). Each beat's visual shows exactly "
                        "what its words say."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": f"The exact narration words for this beat: one short "
                                               f"sentence or clause, {lo}-{hi} words. Use single quotes "
                                               "for quoted speech.",
                            },
                            "visual": (
                                LOCAL_AI_VISUAL_SCHEMA if mode == "local-ai"
                                else SCENE_VISUAL_SCHEMA if scene_mode else VISUAL_SCHEMA
                            ),
                        },
                        "required": ["text", "visual"],
                    },
                },
                "visual_style": {
                    "type": "string",
                    "description": (
                        "One short shared look (film stock, palette, lighting), appended only to "
                        "AI-generated footage prompts so generated shots look consistent. Example: "
                        "'35mm documentary look, teal-and-amber grade, soft natural light'."
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
                **extra,
            },
            "required": [
                "beats", "video_title", "description", "hashtags", "mood", "target_duration",
            ] + (
                [
                    "characters", "visual_style", "story_premise", "protagonist_goal", "stakes",
                    "ending_payoff", "location", "time_of_day", "color_palette", "recurring_objects",
                ]
                if mode == "local-ai" else ["characters"] if mode == "animated" else ["visual_style"]
            )
        }
    }


SYSTEM_PROMPT_HEAD = """You are an elite viral content director. Your videos hit 10M+ views on TikTok and YouTube. You write like MrBeast scripts a documentary — high energy, zero filler, every line earns its place.

═══ VOICEOVER NARRATION ═══
- Match the requested word count (it sets the video length).
- HOOK (first 2 seconds, ~4-6 words): The strongest visual or narrative surprise. Stop the scroll.
- ONE continuous story with a through-line — a beginning, build, and payoff. NOT a list of disconnected facts.
- Sensory language. Make people SEE it. Short punchy sentences mixed with longer builds. RHYTHM.
- Power words: insane, hidden, secret, lost, forbidden, impossible.
- Final line: cliffhanger or callback. Never generic 'follow for more'.

═══ FACTUAL ACCURACY ═══
- Only stated facts you are CERTAIN of. Skip disputed/legendary elements.
- Be conservative with names, dates, specific numbers.

"""

BEATS_FOOTAGE = """═══ BEATS — THE MOST IMPORTANT RULE ═══

The narration is written as BEATS. A beat = the exact words spoken + the ONE visual on screen while
those words are heard. All beat texts joined in order ARE the voiceover — there is no other narration.

1. A beat is ONE short sentence or clause (~3 seconds spoken). The request gives the words-per-beat
   range and the TOTAL word range. The total is a HARD limit (it sets the video length): count the
   words of every beat before submitting.
2. The visual shows EXACTLY what the beat's words say — the thing named, the number stated, the step
   described. NEVER a mood shot or a vibe. If the words say "in 1901 divers pulled a bronze lump from a
   wreck", the visual shows divers / a corroded bronze object, labelled "1901".
3. Choose the visual kind by what the words are about:
   - photo: a specific, REAL, named thing — person, place, building, artifact, machine, artwork, event.
     Real photos come from Wikipedia / Wikimedia Commons. queries[0] = its exact name
     ('Antikythera mechanism', 'Hoover Dam'), then broader fallbacks ('ancient bronze gears').
   - diagram: numbers, dates, measurements, steps of a process, comparisons, cause→effect, or a key idea
     that cannot be filmed. Rendered exactly from your parameters.
   - footage: a generic, filmable action or place ('molten steel pouring', 'waves crashing on rocks').
     queries are concrete stock-library phrases, most specific first — never abstract words
     ('mystery', 'history', 'discovery').
4. Keep it visual: at least half the beats are photo or footage; never more than 3 diagrams in a row.
5. Consecutive beats about the same process or timeline reuse the SAME diagram (identical steps/events
   list and title) and advance active_step / active_event, so the viewer watches one diagram progress.
6. Numbers, dates, and names in visuals must match the narration exactly.

DIAGRAM TEMPLATES (kind = diagram, set `template` + its fields):
- key_phrase: text — a punchy phrase (max 8 words) for an idea that can't be shown.
- stat: value ('400°C', '2,000 years', '$4.2B'), label (what it measures), optional title.
- process: title, steps (2-6 labels, max 4 words each), active_step (1-based).
- timeline: title, events (2-6 of {year, label}), active_event (1-based).
- comparison: title, items (2-4 of {label, value: number, display: '120 km/h'}).

"""

BEATS_SCENES = """═══ BEATS — THE MOST IMPORTANT RULE ═══

The video is a Pixar-style 3D animated short. The narration is written as BEATS: a beat = the exact
words spoken + ONE animated scene on screen while they are heard. All beat texts joined in order ARE
the voiceover. Each scene is generated from your `description`, then animated with a camera move.

1. A beat is ONE short sentence or clause (~3 seconds spoken). The request gives the words-per-beat
   range and the TOTAL word range. The total is a HARD limit (it sets the video length): count the
   words of every beat before submitting.
2. The scene shows EXACTLY what the beat's words say — the action, the object, the place, the step.
   Never a vague mood shot. "A huge excavator digs the hole" → a cartoon excavator scooping dirt out
   of a backyard pit while Max cheers from the edge.
3. Describe ONE clear moment: who (character by name), doing what, where, with which objects, plus
   the framing (wide shot / close-up / top-down / low angle). Concrete nouns only. Never ask for text,
   signs, labels, or numbers inside the picture — the image model can't spell.
4. RECURRING CHARACTERS: define 1-3 `characters` (name + fixed look: age, build, clothes and colours,
   hair) and feature them by name in most scenes, so the viewer follows someone through one world
   (same backyard, same house, same town).
5. Make it FUN and immersive: expressive faces, exaggerated action, playful details, a sense of scale.
   Vary framing — never the same framing twice in a row.
6. camera: push_in (focus, reveal a detail), pull_out (show scale, the result), pan_left/pan_right
   (follow movement, show a row of things), rise (look up, something grows/lifts), orbit (show an
   object all around). Vary the moves.
7. overlay (optional, at most 1 beat in 3): a number said in the beat (`stat`: value '2 m', text
   'deep') or a name/term (`label`: text, max 3 words). It appears as an animated sticker and must
   match the narration exactly.

"""

BEATS_LOCAL_AI = """═══ LOCAL AI CINEMATIC STORY — THE MOST IMPORTANT RULE ═══

The video is one continuous live-action cinematic sequence. The narration is written as BEATS: each
beat contains the exact words spoken by the separate ElevenLabs narrator plus ONE physical scene.
The video generator must never create narration, dialogue, subtitles, cards, diagrams, or labels.

1. Write one causal story, not a montage: each beat must happen because of the previous beat and must
   visibly move the protagonist toward the ending. Give the story a clear goal, obstacle, escalation,
   climax, and concrete payoff. Do not use disconnected mystery images or unexplained random objects.
   Keep events strictly chronological; do not jump backward after the opening or use flashbacks.
2. Every visual is kind `scene` and describes ONE filmable physical moment. It names the recurring
   character, their current action, the same location, relevant recurring props, and a clear framing.
   Write exact `continuity_in` and `continuity_out` states so adjacent shots join without a reset.
   Choose a motivated transition into each shot: usually `cut`; `match_cut` only when motion or shape
   truly matches; `crossfade` only when the story visibly advances through time. Never use a pattern.
3. Define 1-3 recurring `characters` with exact immutable appearance, clothing, colors, and equipment.
   Refer to them by name in every scene where they appear. Never swap or redesign a character.
4. Define one `location`, `time_of_day`, and `color_palette`. Preserve geography, architecture,
   lighting, and object positions as the camera advances through connected spaces.
5. No text-bearing objects or generated graphics: no title cards, signs, screens, diagrams, captions,
   subtitles, labels, logos, or written numbers. The software adds captions after rendering.
6. Narration describes the story but is never quoted inside a visual description. Characters do not
   speak. Visual descriptions contain only observable action and scene details.
7. End with a visible consequence or resolution that explains and pays off the opening hook. For this
   mode, do not end on a generic cliffhanger. Never introduce a new person, creature, object, or threat
   in the final beats merely as a twist; the payoff must come from elements established earlier.
8. This pipeline defaults to DOCUMENTARY mode. Never invent a discovery, person, place, quotation,
   artifact, scientific mechanism, or historical event. Fiction is allowed only when the request is
   explicitly marked [FICTION]; the title, narration and description must clearly label it as fiction.
   A recurring visual-only guide or demonstrator may connect the shots, but the narration must not
   present that guide as a real discoverer or witness, and the guide must never perform an invented
   historical event. Use them to observe or demonstrate only source-supported facts.
9. Write the complete production bible: `story_premise`, one concrete `protagonist_goal`, specific
   `stakes`, a causal `ending_payoff`, and immutable `recurring_objects`. These fields plus every beat
   form the full screenplay sent to the video generator for context on every shot.

"""

SYSTEM_PROMPT_TAIL = """═══ CONTENT SAFETY (NON-NEGOTIABLE) ═══

Video generators and platforms REJECT this content. Never use, in narration or visuals:
- PAIN/HARM: pain, agony, suffering, screaming, writhing, contorted, blood, wound, burned, injured, bleeding, violent, attack
- WEAPONS: gun, knife, blade, weapon
- DISTRESSING: crying child, drowning, falling from height, medical procedures, sexual content

Show drama through OBJECTS (spilled liquid, swinging lanterns), ENVIRONMENT (storm clouds, swirling dust, flickering flames), and MOTION (rushing, sweeping, reaching) — NEVER through harm to a person.

You MUST submit the script using the submit_video_script tool. Do not write JSON yourself — call the tool with the structured arguments."""


def system_prompt(mode: str = "footage") -> str:
    beats = BEATS_SCENES if mode == "animated" else BEATS_LOCAL_AI if mode == "local-ai" else BEATS_FOOTAGE
    return SYSTEM_PROMPT_HEAD + beats + SYSTEM_PROMPT_TAIL


# Backward-compatible default prompt.
SYSTEM_PROMPT = system_prompt("footage")


def generate_script(topic: str, tone: str = "mysterious", target_seconds: int = 75,
                    previous: dict = None, feedback: str = None, mode: str = "footage",
                    angle: str | None = None, content_mode: str = "documentary",
                    research: list[dict] | None = None) -> dict:
    """Generate a beat-structured, target-length video script via Claude tool_use.

    With `previous` + `feedback`, the model REVISES its earlier draft to fix the
    reported problems instead of starting over (a rewrite tends to repeat or
    trade one problem for another).
    """
    if topic.lstrip().upper().startswith("[FICTION]"):
        content_mode = "fiction"
    if content_mode not in {"documentary", "fiction"}:
        raise ValueError("content_mode must be 'documentary' or 'fiction'")
    num_beats, min_words, max_words = plan_for_duration(target_seconds)
    lo, hi = beat_word_range(num_beats, min_words, max_words)
    tool = build_script_tool(num_beats, min_words, max_words, mode)
    limits = (f"LIMITS: {min_words}-{max_words} words TOTAL across all beat texts, "
              f"about {num_beats} beats of {lo}-{hi} words each.")
    evidence = json.dumps(research or [], ensure_ascii=False, indent=2)

    if previous and feedback:
        draft = {k: v for k, v in previous.items() if k not in ("spoken_script", "credits")}
        wc = len(narration_from_beats(get_beat_list(previous)).split())
        prompt = f"""Your previous draft of this {target_seconds}-second video ({wc} words) FAILED review:

{feedback}

Fix exactly those problems. Keep the story, facts, and visuals otherwise as close as possible —
shorten or merge beats if the narration is too long.
TOPIC: {topic}
FRAMING ANGLE: {angle or 'choose the strongest truthful framing'}
CONTENT MODE: {content_mode}
TONE: {tone}
{limits}
SOURCE EVIDENCE (use only supported claims; never invent missing details):
{evidence}

PREVIOUS DRAFT:
{json.dumps(draft, ensure_ascii=False)}

Submit the corrected FULL script with the submit_video_script tool."""
    else:
        visual_hint = (
            "Every beat is a fun Pixar-style 3D scene that shows exactly what its words say, "
            "starring your recurring characters." if mode == "animated" else
            "Make every beat one connected, photoreal live-action scene with the same recurring "
            "characters and physical world. Use no diagrams, cards, labels, or generated text." if mode == "local-ai" else
            "Give every beat the visual that shows exactly what its words say — photo for real named "
            "things,\ndiagram for numbers/dates/processes/comparisons, footage for generic filmable actions.")
        prompt = f"""Create a viral {target_seconds}-second video about:

TOPIC: {topic}
FRAMING ANGLE: {angle or 'choose the strongest truthful framing'}
CONTENT MODE: {content_mode}. In documentary mode, do not invent events or discoveries.
TONE: {tone}
SOURCE EVIDENCE (use only supported claims; never invent missing details):
{evidence}

Write ONE continuous story as beats. {limits}
{visual_hint}
Submit with the submit_video_script tool."""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=16000,
        system=system_prompt(mode),
        tools=[tool],
        tool_choice={"type": "tool", "name": "submit_video_script"},
        messages=[{"role": "user", "content": prompt}]
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_video_script":
            script = block.input
            beats = get_beat_list(script)
            if beats:
                repair_beats(beats, scene_mode=mode in {"animated", "local-ai"})
                # The voiceover IS the beats — derived, so words and visuals can't drift.
                script["spoken_script"] = narration_from_beats(beats)
            script["content_mode"] = content_mode
            script["research_sources"] = research or []
            if angle:
                script["framing_angle"] = angle
            return script

    raise Exception("Claude did not call the submit_video_script tool")


def get_beat_list(script: dict) -> list:
    beats = script.get("beats") if isinstance(script, dict) else None
    return [b for b in beats if isinstance(b, dict)] if isinstance(beats, list) else []


if __name__ == "__main__":
    test_topic = "The Antikythera mechanism — a 2000-year-old Greek device that predicted eclipses"
    log.info(f"Generating script for: {test_topic}")
    result = generate_script(test_topic, tone="mysterious", target_seconds=75)
    log.info(json.dumps(result, indent=2))
    log.info(f"Word count: {len(result['spoken_script'].split())}")
    log.info(f"Beats: {len(result['beats'])}")
