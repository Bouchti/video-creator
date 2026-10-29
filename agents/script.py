import json
import os
import logging
from dotenv import load_dotenv
from config.paths import get_env_path
from agents import ai_router
from agents.animate import CAMERA_MOVES
from agents.beats import DIAGRAM_TEMPLATES, OVERLAY_TYPES, narration_from_beats, repair_beats

# "animated": every beat is a generated Pixar-style 3D scene, animated in 2.5D.
# "footage": stock footage, real photos, and diagrams (the --source pexels path).
# "unreal": deterministic primitive-shape engineering dioramas rendered in UE5.
SCRIPT_MODES = ("animated", "footage", "local-ai", "unreal")

load_dotenv(get_env_path())

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
            "description": "Production-ready description of one physical three-second shot, starting with its "
                           "shot size ('Wide shot:', 'Medium shot:', 'Close-up:' or 'Extreme close-up:'): "
                           "named character, action, connected location, recurring props, composition, "
                           "lighting, and depth. No dialogue or text.",
        },
        "continuity_out": {
            "type": "string",
            "description": "Exact final pose, position, gaze, prop state, and camera direction that the next shot inherits.",
        },
        "camera": {
            "type": "string",
            "enum": list(CAMERA_MOVES),
            "description": "One motivated camera move that follows the current action or moves toward "
                           "or away from what is already in frame; never one that reveals something new.",
        },
        "transition": {
            "type": "string",
            "enum": ["cut", "match_cut", "crossfade"],
            "description": "Story-motivated edit into this shot. Use cut by default, match_cut only for matching shape/action, and crossfade only for a real passage of time.",
        },
        "scene": {
            "type": "string",
            "description": "Short name of the place this shot is in, e.g. 'cliff top', 'east riverbank'. Reuse "
                           "the identical words every time the story is in that place.",
        },
        "light": {
            "type": "string",
            "description": "The light and sky in this shot only, e.g. 'warm dawn sun', 'clear midday sun', "
                           "'partial eclipse dimming', 'total eclipse darkness with corona'. Reuse the identical "
                           "words while the light is unchanged; never name a later event's light early.",
        },
    },
    "required": ["kind", "continuity_in", "description", "continuity_out", "camera", "transition", "scene", "light"],
}


from unreal_video.planner import SET_SHOWS, capability_brief, set_actions  # noqa: E402

UNREAL_VISUAL_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["scene"]},
        "description": {
            "type": "string",
            "description": "One schematic engineering-diorama stage built from simple geometric machinery, structures, pipes, tanks, water, soil, roads, or vehicles. No people, text, logos, fire, smoke, or location-specific architecture.",
        },
        "camera": {
            "type": "string",
            "enum": ["orbit", "dolly_in", "dolly_out", "crane_up", "tracking", "static"],
            "description": "Supported Unreal camera move.",
        },
        "action": {
            "type": "string",
            "enum": sorted({a for name in SET_SHOWS for a in set_actions(name)}),
            "description": "What the set acts out while this beat is spoken; must be one of the chosen "
                           "set's actions. The words must describe exactly what this action shows.",
        },
    },
    "required": ["kind", "description", "camera", "action"],
}


def build_script_tool(num_beats: int, min_words: int, max_words: int, mode: str = "footage",
                      content_mode: str = "documentary") -> dict:
    lo, hi = beat_word_range(num_beats, min_words, max_words)
    scene_mode = mode in {"animated", "local-ai"}
    extra = {}
    if scene_mode:
        extra["characters"] = {
            "type": "array",
            "minItems": 0 if mode == "local-ai" and content_mode == "documentary" else 1,
            "maxItems": 3,
            "description": (
                "For documentary local-AI videos, use [] unless the evidence names a real person whose "
                "presence is essential. Never invent a presenter, scientist, witness, or demonstrator."
                if mode == "local-ai" and content_mode == "documentary" else
                "Recurring people or animals the viewer follows. Do not list lights, places, or objects "
                "as characters. `look` is ONE fixed visual description reused in every image."
            ),
            "items": {"type": "object",
                      "properties": {
                          "name": {"type": "string"},
                          "look": {"type": "string"},
                          "look_changes": {
                              "type": "array",
                              "description": "Only if the character visibly changes during the story "
                                             "(grows up, changes outfit): the 1-based beat where each "
                                             "new complete look starts.",
                              "items": {"type": "object",
                                        "properties": {"from_beat": {"type": "integer", "minimum": 1},
                                                       "look": {"type": "string"}},
                                        "required": ["from_beat", "look"]},
                          },
                      },
                      "required": ["name", "look"]},
        }
    if mode == "unreal":
        extra["set"] = {
            "type": "string",
            "enum": list(SET_SHOWS),
            "description": "The one 3D set the whole film is shown in; every beat's action is one of its actions.",
        }
    if mode == "local-ai":
        extra.update({
            "story_premise": {
                "type": "string",
                "description": ("Two precise sentences establishing the real subject, factual question, and visual direction."
                                if content_mode == "documentary" else
                                "Two precise sentences establishing the protagonist, inciting event, goal, and direction."),
            },
            "protagonist_goal": {
                "type": "string",
                "description": ("For an object-led documentary, the concrete physical process or evidence trail the film follows; no human protagonist is required."
                                if content_mode == "documentary" else
                                "The concrete physical goal pursued throughout the sequence."),
            },
            "stakes": {
                "type": "string",
                "description": ("Why understanding this real mechanism or finding matters; do not invent danger or a personal conflict."
                                if content_mode == "documentary" else
                                "What visibly changes or is lost if the protagonist fails."),
            },
            "ending_payoff": {
                "type": "string",
                "description": "The final visible cause-and-effect resolution that pays off the opening without a random twist.",
            },
            "location": {
                "type": "string",
                "description": "A fixed physical world description reused across every shot: geography, architecture, scale, and recurring props. When the film has several places or eras, write one sentence per place that names its beat `scene` label (each shot keeps only its own place's sentence).",
            },
            "time_of_day": {
                "type": "string",
                "description": "The opening time and light; any later change of light goes in each beat's `light`.",
            },
            "color_palette": {
                "type": "string",
                "description": "A restrained recurring color palette for every shot; a clause meant for one place names that place's `scene` label.",
            },
            "screen_geography": {
                "type": "string",
                "description": "Fixed frame side and facing of each opposing side for the whole film (the "
                               "180-degree rule), e.g. 'Lydians and Karan: always frame left, facing and moving "
                               "right; Medes and Darios: always frame right, facing and moving left; the river "
                               "between them'. With no opposing sides, the protagonist's usual direction of travel.",
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
                                else UNREAL_VISUAL_SCHEMA if mode == "unreal"
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
                    "screen_geography",
                ]
                if mode == "local-ai" else ["characters"] if mode == "animated"
                else ["visual_style", "set"] if mode == "unreal" else ["visual_style"]
            )
        }
    }


SYSTEM_PROMPT_HEAD = """You are an elite viral content director. Your videos hit 10M+ views on TikTok and YouTube. You write like MrBeast scripts a documentary — high energy, zero filler, every line earns its place.

═══ VOICEOVER NARRATION ═══
- Match the requested word count (it sets the video length).
- HOOK (beat 1, first 2 seconds): state the single most astonishing fact or OUTCOME of the story, in
  plain words, as a cold open ("In 585 BC, the sun vanished mid-battle and two armies stopped a war.").
  Never open with scene-setting or background ("two armies, one river..."): ~37% of viewers swipe
  away in the first seconds when the hook only sets the scene. Beat 2 then starts the story
  ("Here's how it happened.").
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
   Beat 1 is a COLD OPEN: it shows the story's most astonishing moment (the payoff image, e.g. the
   eclipse above both armies) while its words state the outcome. Give it the SAME `scene` and `light`
   labels as the later beat where that moment really happens, and do not name it a flashback. From
   beat 2 on, keep events strictly chronological: no other flash-forward, no flashbacks; beat 2 starts
   at the beginning of the story ("Here's how it happened.").
2. Every visual is kind `scene` and describes ONE filmable physical moment. It names the recurring
   character, their current action, the same location, relevant recurring props, and a clear framing.
   Give every beat a `scene` (place) and `light` label. Consecutive beats with the same scene and light
   are one continuous take: write exact `continuity_in` and `continuity_out` so they join without a
   reset. When the story cuts to another place or the light changes, change the label; that shot opens
   fresh, so its `continuity_in` describes how it opens in its own place. Mention a story event (an
   eclipse, a fire, a storm, nightfall) only in beats at or after the moment it happens.
   Choose a motivated transition into each shot: usually `cut`; `match_cut` only when motion or shape
   truly matches; `crossfade` only when the story visibly advances through time. Never use a pattern.
3. Define 1-3 recurring `characters` with exact immutable appearance. Each `look` names every garment
   with its colour and cut, the headwear (or bare head), hair, and one signature item, so the generator
   draws the same outfit every time. Characters must be told apart at a glance: no two share a dominant
   garment colour or silhouette (never two figures in white robes or white cloaks).
   Refer to them by name in every scene where they appear. Never swap or redesign a character.
   If a character visibly changes (a cub grows up, a new uniform), `look` is the first appearance only
   and each later appearance goes in `look_changes` with the beat where it starts.
   A held item is part of the look: when a character drops, plants, gives away, or picks up an item
   (a shield, a spear, a letter), add a `look_changes` entry from that beat whose look no longer (or
   now) carries it, e.g. 'bronze breastplate over crimson tunic ... empty hands, no shield'.
4. Define one `location`, `time_of_day` (the opening light), and `color_palette`. Preserve geography,
   architecture, lighting, and object positions as the camera advances through connected spaces.
   Write positions in frame terms (frame left/right, facing, toward or away from camera), never compass
   directions: the video model cannot read 'east' or 'west'. Opposing sides keep their `screen_geography`
   side and facing in every shot; when both are on screen they face each other across a visible gap,
   never walk side by side or mix into one crowd.
   `visual_style` and `color_palette` describe the film's look only, never story events or a change of
   light (no eclipse, nightfall, storm); each beat's `light` carries those.
5. No text-bearing objects or generated graphics: no title cards, signs, screens, diagrams, captions,
   subtitles, labels, logos, or written numbers. The software adds captions after rendering.
6. Narration describes the story but is never quoted inside a visual description. Characters do not
   speak. Visual descriptions contain only observable action and scene details.
7. End with a visible consequence or resolution that explains and pays off the opening hook. The
   resolution must read with the sound off: one unmistakable physical gesture between the characters
   (clasped hands or forearms, an exchanged token, weapons laid down together, a bow) in a medium or
   close framing, never two people merely standing near each other. For this
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


BEATS_LOCAL_AI_DOCUMENTARY = """═══ LOCAL AI OBJECT-LED DOCUMENTARY — THE MOST IMPORTANT RULE ═══

The video is one continuous photoreal documentary explanation generated as short physical scenes.
The narrator is separate; the video generator must never create speech, subtitles, cards, diagrams,
labels, logos, or written numbers.

1. Build an evidence-led visual journey around the REAL SUBJECT, not a fictional protagonist. The
   subject may be a spacecraft, sample, machine, structure, natural process, animal, or place. Beat 1
   is a cold-open glimpse of the strongest real outcome; beat 2 begins the explanation. After that,
   progress causally from origin/input through process/evidence to the final factual payoff.
2. `characters` should be [] unless the supplied evidence names a real person whose presence is
   essential. Never invent named presenters, scientists, archaeologists, witnesses, technicians, or
   demonstrators. Anonymous distant workers or gloved hands may appear only as neutral illustrative
   scale/context; they must not perform a claimed discovery, experiment, handoff, or historical event.
3. Every visual is kind `scene` and describes ONE filmable physical moment. Clearly call molecular
   models, reconstructions, or macro views "illustrative" when they are not sourced archival footage.
   Never claim a generated scene is archival, verified footage, or an exact photograph.
4. Visual staging details such as lens, lighting, neutral surfaces, and camera motion may be cinematic,
   but factual actions, locations, object properties, dates, quantities, and discoveries must come from
   the supplied evidence. Do not add a parachute landing, desert recovery, laboratory procedure, exact
   color, handoff, or sequence of events unless the evidence supports it.
5. Give every beat a `scene` and `light` label. Consecutive beats with the same labels form one
   continuous take: `continuity_in` must match the preceding `continuity_out`. Cuts move among the
   evidence-supported settings, close details of them, and clearly illustrative stand-ins for what
   the narration names (rule 14); every cut follows the narration, never a random montage.
6. No generated text or diagrams. Numbers and terms are spoken by narration and added later as
   software captions. Show quantities through physical groupings only when reliable generation is
   plausible; otherwise show the real object or process the number describes.
7. The ending payoff is a clear final view of the real subject, completed mechanism, or combined
   evidence—not a handshake, human gesture, invented celebration, or fictional decision.
8. The production bible is object-led: `story_premise` states the factual question and answer;
   `protagonist_goal` names the physical process/evidence trail; `stakes` explains why it matters;
   `ending_payoff` names the final factual reveal; `recurring_objects` locks the subject's appearance.
9. Do not invent a discovery, person, place, quotation, artifact, experiment, scientific mechanism,
   or historical event. When the evidence cannot support a scene, simplify to a neutral illustrative
   view of the supported object instead of filling the gap with fiction.
10. EVERY VISUAL MUST BE FILMABLE BY THIS GENERATOR. Accuracy binds the narration; the shots must
   also be renderable, or the clip is rejected and the shot becomes a frozen still. Therefore:
   - Do not name a real vehicle, vessel, craft, spacecraft or instrument in a visual. Describe it
     generically and plainly: "the deck of a research ship at sea", never "RV Investigator". The
     narration may still name it.
   - Do not stage a shot that depends on sustained underwater, submerged, aerial-only, microscopic,
     satellite or archival imagery. A generated clip drifts out of such a setting within three
     seconds, typically to dry land under a bright sky. Film the evidence where a camera can stand:
     the object on a bench, the core on a table, the coastline from the shore, the machine in a hall.
   - Do not stage instrument readouts, sonar traces, scans, screens or data displays; they come out
     as forbidden on-screen text. Show the physical thing the reading is about.
   - EVERY beat's `light` must be a DAYTIME condition. The generator cannot hold darkness: a night
     shot drifts to dawn, sunset or full daylight within three seconds, so pink sky, blue sky and
     sunlit slopes appear in the middle of what you asked to keep black. Overcast, haze, smoke, dim
     ash-darkened sky, storm light, deep shade and plain interior light are all fine; night,
     moonlight, dusk, dawn, twilight, starlight and "lit only by <glow>" are not. If the real event
     happened at night, film its daytime evidence instead — fresh black rock, steam, an ash plume,
     a scorched slope — and let the narration say it happened at night.
   - Do not stage a shot whose subject is only visible because it glows in the dark (lava rivers at
     night, embers, a furnace interior). Show the same thing by day: the dark flow it leaves, the
     steam where it meets water, the new ground it built.
   - If the evidence's real setting cannot be filmed, show a supported object from that work instead,
     and let narration carry the location.
11. KEEP EVERY ATTRIBUTION EXACTLY AS THE EVIDENCE GIVES IT. When a source credits a finding to a
   particular instrument, satellite, mission, agency or method, that credit belongs to that one and
   to no other, and the verb matters as much as the name. A source saying an instrument "tracked",
   "watched", "visualised" or "imaged" something does NOT say it measured, counted or discovered it;
   if a different source supplies the number, the number is that source's. Never merge two
   instruments into one, never move a figure from the thing that produced it to the thing that is
   more famous or more striking, and never upgrade an observation into a measurement or a discovery.
   This applies to the title, description, premise, stakes and payoff as much as to a beat: those
   lines are where a careful script usually slips.
12. EACH SHOT IS A MOMENT, NOT A PROCESS. A shot is about three seconds long. Whatever change you
   write into it has to be visible in three seconds of real time, or the shot is rejected for
   showing nothing happening. So:
   - The change inside a shot comes from something that genuinely moves at that speed: a wave
     breaking, surf running up rock, steam curling off a surface, ash sifting down, a bird, a
     vehicle, smoke bending in wind — or from a gentle push-in or pull-back on what is already in
     frame (a push-in that lands on the new black shoreline).
   - NEVER make a slow process the change inside one shot. A plume thickening and veiling a summit,
     a sky darkening, a shelf widening, a flow advancing into the sea, a crack spreading, a glacier
     retreating: none of these move perceptibly in three seconds, and asking for them produces a
     clip where nothing appears to happen.
   - Those slow processes are what the CUT is for. Show the stages ACROSS shots: a thin plume in one
     shot, a sky already dark in a later one, bare rock early and a wide black shelf near the end.
     The viewer reads the change from the difference between shots; each shot only has to be a
     convincing still moment of its own stage.
   - State the stage each shot is AT, not the transformation it should undergo. "A dense ash column
     already standing over the summit, its edge drifting" is filmable; "the plume grows thicker and
     spreads until it veils the summit" is not.
   - Frame the subject so it reads on a phone: it should occupy a clear share of the frame. Do not
     ask for a subject that is small, tiny or far away in frame; the generator fills the frame with
     its subject and a "small distant cone" comes back large and close, breaking the shot.
13. THE CAMERA NEVER REVEALS. A continuing shot starts on the previous shot's last frame, and the
   generator cannot invent what that frame does not already show. On a test run a pan "to another
   lava flow on the next flank" kept the first flow and drifted onto a hillside on every take, a
   rise "to reveal the lava front" pulled back until the front was a speck, and an orbit barely
   turned. So:
   - `camera` is `push_in` or `pull_out` for a still subject. Use `pan_left`/`pan_right` only to
     follow something that moves, and never use `rise` or `orbit`.
   - Whatever the shot is about must be in its first frame. To show a new subject, cut to it: give
     it its own beat whose description shows it from the start.
   - Say where the camera stands in every description: "at eye level on the shore", "from a boat
     just above the water", "high above". Without it the generator picks a drone view.
14. THE PICTURE MUST KEEP CHANGING. A test video showed the same volcano from the same distance in
   18 of 22 shots while the narration spoke of flights, a radar satellite and sailors; viewers
   called it one volcano and a camera turning. So:
   - Each beat shows what ITS line talks about. When the line names something other than the main
     subject, show a filmable stand-in for that thing, never the main subject again: a radar
     mission becomes a large radar dish antenna at a ground station (illustrative); disrupted
     flights become an airliner parked on an apron under a hazy sky; sailors become a small boat on
     the swell with anonymous crew in the distance; a cloud-covered camera becomes rain-beaded
     glass. Call a stand-in "illustrative" in the description.
   - Start every description with its shot size: "Wide shot:", "Medium shot:", "Close-up:" or
     "Extreme close-up:". At least one beat in four is a Close-up or Extreme close-up of a physical
     detail: texture, steam from a crack, water running off rock, ash on a surface, hands, a tool.
   - Never more than three beats in a row with the same shot size, and never more than three in a
     row of the same subject. The main subject appears in at most half of the beats; the rest are
     its details, its surroundings, its effects and the stand-ins above.
   - The `scene` label is the PLACE the camera is in, and it decides what the shot looks like. At
     most 40% of beats share one scene label and never more than three in a row: a line about
     forecasters, a storm far away, a satellite or a rainfall record gets its own scene.
15. SAY IT ONCE, SHOW IT ONCE, MAKE IT LAND. A test video about one cannon shot showed the enemy
   fleet flying the other side's flag, two smoke bursts under "exactly one shot", and a cannonball
   already resting beside a tipped kettle under "the ball crashed into a soup kettle". So:
   - When two sides appear (nations, fleets, armies, teams), give each its own `recurring_objects`
     entry with its marking described concretely ("a red, white and blue horizontal tricolour" /
     "a yellow banner with a black double-headed eagle"), and repeat that marking in every
     description that shows that side. Show both sides in one shot only when the beat is about
     them meeting.
   - Keep movable things out of `location`. "A broad river with sailing ships on the water" puts
     extra ships, flying whatever flag the generator likes, into every shot of that river, including
     the one about a single ship. The location is the place only; each beat names what is in it.
   - Numbers in the narration are literal on screen. The beat that shows "one shot" or "three ships"
     says "exactly one" / "exactly three" and frames tightly enough that nothing else of that kind
     is in view (one gun port, not a whole broadside). A once-only event is shown once; later beats
     show only its aftermath, stated as such ("the smoke of that one shot, already drifting, no new
     firing").
   - An impact (hit, struck, crashed into, smashed, exploded) is shown AS it lands, never after: the
     first frame has the target intact, the object arrives fast, and the last sentence of the
     description is the violent reaction ("the cannonball slams into the iron kettle, which bursts
     sideways in a spray of broth and dented iron"), not the calm aftermath. Objects only, never
     a person hit.

"""

SYSTEM_PROMPT_TAIL = """═══ CONTENT SAFETY (NON-NEGOTIABLE) ═══

Video generators and platforms REJECT this content. Never use, in narration or visuals:
- PAIN/HARM: pain, agony, suffering, screaming, writhing, contorted, blood, wound, burned, injured, bleeding, violent, attack
- WEAPONS: gun, knife, blade, weapon
- DISTRESSING: crying child, drowning, falling from height, medical procedures, sexual content

Show drama through OBJECTS (spilled liquid, swinging lanterns), ENVIRONMENT (storm clouds, swirling dust, flickering flames), and MOTION (rushing, sweeping, reaching) — NEVER through harm to a person.

You MUST submit the script as the structured output, matching its schema exactly."""


BEATS_UNREAL = """═══ UNREAL 3D SET FILM ═══
This video is rendered from ready-made 3D sets, not a general image generator. Each set can show only
the things and actions listed below, so the narration must be a story those actions can show.

THE SETS (choose ONE for the whole film in `set`):
""" + capability_brief() + """

Hard rules:
- Choose the topic's framing so the chosen set shows it end to end. If a fact needs something the set
  cannot show (valves, gears inside a machine, people, numbers on screen), say it in words over an
  action that shows its effect; never promise a picture the set doesn't have.
- Every beat sets `visual.action` to one of the chosen set's actions. Its words describe exactly what
  that action shows (e.g. "pump_up" while the narration says water is pushed uphill). Follow the real
  process in order: input, process, output. Beat 1 is a COLD OPEN: its words state the most
  astonishing fact or outcome and its action is the most striking one ("finale", "launch",
  "release_down"...); beat 2 is usually "establish" and starts the explanation; the last beat is
  "finale", the payoff with everything running.
- `visual.description` says what the viewer sees in that beat, in the set's own terms.
- No people, faces, crowds, animals, battles, weapons, flames, written labels or on-screen numbers.
  Narration carries the facts; it must stay factual and supported by the supplied evidence.

"""


def system_prompt(mode: str = "footage", content_mode: str = "documentary") -> str:
    beats = (BEATS_SCENES if mode == "animated" else
             BEATS_LOCAL_AI_DOCUMENTARY if mode == "local-ai" and content_mode == "documentary" else
             BEATS_LOCAL_AI if mode == "local-ai"
             else BEATS_UNREAL if mode == "unreal" else BEATS_FOOTAGE)
    return SYSTEM_PROMPT_HEAD + beats + SYSTEM_PROMPT_TAIL


# Backward-compatible default prompt.
SYSTEM_PROMPT = system_prompt("footage")


def generate_script(topic: str, tone: str = "mysterious", target_seconds: int = 75,
                    previous: dict = None, feedback: str = None, mode: str = "footage",
                    angle: str | None = None, content_mode: str = "documentary",
                    research: list[dict] | None = None,
                    excluded_claims: list[str] | None = None) -> dict:
    """Generate a beat-structured, target-length video script with the configured AI backend.

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
    tool = build_script_tool(num_beats, min_words, max_words, mode, content_mode)
    limits = (f"LIMITS: {min_words}-{max_words} words TOTAL across all beat texts, "
              f"about {num_beats} beats of {lo}-{hi} words each.")
    evidence = json.dumps(research or [], ensure_ascii=False, indent=2)
    # The topic line is written by the topic scout BEFORE the sources are fetched, so it routinely
    # asserts specifics the evidence never backs (a height, a date, a collapse). Handed over as plain
    # fact it becomes the story's spine, and the evaluator then blocks every beat that rests on it.
    topic_caveat = ("\nTREAT THE TOPIC LINE AS A LEAD, NOT A SOURCE. It was written before these sources were "
                    "read. Any specific in it that SOURCE EVIDENCE does not support — a height, a date, a "
                    "collapse, a record, a measurement — must be DROPPED, not retold or softened, and must "
                    "not carry a beat, the title, the premise or the ending. A shorter arc that is fully "
                    "sourced beats a richer one built on an unsupported claim."
                    if content_mode == "documentary" else "")
    # Claims a fact-checker already removed from this topic for want of a source. Without this list
    # the writer supplies them again from its own knowledge of the subject (an Anak Krakatau draft
    # re-asserted that the name means "child of Krakatau" one minute after it was struck out), and
    # the evaluator spends a whole revision round blocking the same claim again.
    excluded = ""
    if content_mode == "documentary" and excluded_claims:
        excluded = ("\n\nALREADY REJECTED FOR THIS TOPIC — a fact-checker removed each of these because no "
                    "source supports it. They are not open questions and your own knowledge does not "
                    "settle them. Do not state, imply, hint at or build a beat, title, premise or ending "
                    "on any of them:\n"
                    + "\n".join(f"- {str(claim)[:300]}" for claim in excluded_claims[:12]))

    if previous and feedback:
        draft = {k: v for k, v in previous.items() if k not in ("spoken_script", "credits")}
        wc = len(narration_from_beats(get_beat_list(previous)).split())
        prompt = f"""Your previous draft of this {target_seconds}-second video ({wc} words) FAILED review:

{feedback}

Fix exactly those problems. Keep the story, facts, and visuals otherwise as close as possible —
shorten or merge beats if the narration is too long.
TOPIC: {topic}{topic_caveat}
FRAMING ANGLE: {angle or 'choose the strongest truthful framing'}
CONTENT MODE: {content_mode}
TONE: {tone}
{limits}
SOURCE EVIDENCE (use only supported claims; never invent missing details):
{evidence}{excluded}

PREVIOUS DRAFT:
{json.dumps(draft, ensure_ascii=False)}

Submit the corrected FULL script as the structured output."""
    else:
        visual_hint = (
            "Every beat is a fun Pixar-style 3D scene that shows exactly what its words say, "
            "starring your recurring characters." if mode == "animated" else
            "Make every beat one connected, photoreal object-led documentary scene. Use no invented "
            "people, staged discoveries, diagrams, cards, labels, or generated text." if mode == "local-ai" and content_mode == "documentary" else
            "Make every beat one connected, photoreal live-action scene with the same recurring "
            "characters and physical world. Use no diagrams, cards, labels, or generated text." if mode == "local-ai" else
            "Make every beat one stage of the same schematic Unreal engineering diorama. Use only "
            "the supported primitive structures and machinery; never introduce people or historical reenactments." if mode == "unreal" else
            "Give every beat the visual that shows exactly what its words say — photo for real named "
            "things,\ndiagram for numbers/dates/processes/comparisons, footage for generic filmable actions.")
        prompt = f"""Create a viral {target_seconds}-second video about:

TOPIC: {topic}{topic_caveat}
FRAMING ANGLE: {angle or 'choose the strongest truthful framing'}
CONTENT MODE: {content_mode}. In documentary mode, do not invent events or discoveries.
TONE: {tone}
SOURCE EVIDENCE (use only supported claims; never invent missing details):
{evidence}{excluded}

Write ONE continuous story as beats. {limits}
{visual_hint}
Submit it as the structured output."""

    script = ai_router.ask(system_prompt(mode, content_mode), prompt, tool["input_schema"], effort="high")
    if not isinstance(script, dict):
        raise ValueError("Claude did not return a video script")
    beats = get_beat_list(script)
    if beats:
        repair_beats(beats, scene_mode=mode in {"animated", "local-ai", "unreal"})
        # The voiceover IS the beats — derived, so words and visuals can't drift.
        script["spoken_script"] = narration_from_beats(beats)
    script["content_mode"] = content_mode
    script["research_sources"] = research or []
    if angle:
        script["framing_angle"] = angle
    return script


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
