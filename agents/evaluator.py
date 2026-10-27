import json
import os
import logging
from dotenv import load_dotenv
from config.paths import get_env_path
from agents import ai_router
from agents.beats import validate_beats

load_dotenv(get_env_path())

log = logging.getLogger("pipeline")

EVALUATOR_PROMPT = """You are a quality control agent for premium viral video scripts.

RUBRIC:
1. HOOK: beat 1 must state the most surprising fact or outcome in plain words (a cold open). An
   opener that only sets the scene or gives background ("two armies, one river...") is BLOCKING.
2. FACTUAL ACCURACY: No hallucinations or verifiably false claims. STRICTEST check.
3. LENGTH: Already verified in code before you see the script — never FAIL for length.
4. BRAND SAFETY: No political, religious, or controversial framing.
5. VISUAL MATCH (MOST IMPORTANT): every beat's visual must literally show what THAT beat's text says —
   the subject named, the number stated, the step described. A mood/atmosphere shot that doesn't
   depict the words FAILS. Numbers, dates, and names in diagrams/overlays must equal the narration.
   Name the exact beat number in feedback.
6. VISUAL KIND:
   - `scene` beats (local AI video): one clear, concrete moment that depicts the words, recurring
     characters referred to by name, no text/numbers requested inside the picture (those belong in
     the overlay). Scenes must form one chronological causal sequence, preserve character/world
     continuity, and end with a visible payoff using elements established earlier. A flashback after
     the hook, a disconnected montage, or a new unexplained person/object/twist near the ending FAILS.
     HOOK EXCEPTION: beat 1 may be a teaser that shows the story's most surprising moment (a
     flash-forward to the claim) before beat 2 starts the chronological story. That is NOT a
     flashback; only a jump backward AFTER the story has started is. Be lenient on exact framing and
     camera choice.
   - `footage`/`photo`/`diagram` beats: real named people/places/objects → photo (exact name as first
     query); numbers, dates, processes, comparisons → diagram; generic filmable actions → footage.
     Queries must be concrete, never abstract ('mystery', 'history').
7. CONTENT SAFETY: Narration and visuals MUST NOT contain ANY of these phrases or concepts:
   - "pain", "agony", "suffering", "screaming in distress", "writhing", "contorted"
   - "blood", "wound", "burned", "injured", "bleeding"
   - gratuitous or graphic use of weapons, guns, knives, or blades
   - "violent", "attack", any depiction of harm to a person's body
   - Anything showing a person suffering or being hurt
   If a beat depicts drama through suffering/pain instead of through environment/action, FAIL it.
8. FULL SCREENPLAY QUALITY for `scene` beats: premise, protagonist goal, stakes, recurring objects,
   and ending payoff must be specific and mutually consistent. Within the same `scene` and `light`,
   each shot's continuity_out must match the next shot's continuity_in. A beat whose light or
   description shows an event (eclipse, fire, storm, nightfall) before the story reaches it (except
   the beat-1 cold open, which shows the payoff moment with that moment's own scene/light labels), a
   flash-forward after beat 1, or two characters with the same dominant garment colour is blocking. So is
   a character whose look still carries an item after the beat that drops or gives it away (it needs a
   `look_changes` entry), and an ending whose agreement or resolution is not one clear physical gesture
   readable with the sound off.
   Reject vague goals, repeated filler, broken geography, unmotivated actions, contradictions, or
   endings that do not causally resolve the opening setup.

Be STRICT on facts and content safety. Be LENIENT on style details. When in doubt about facts/safety, FAIL. When in doubt about style, PASS.

List EVERY issue you find in one pass (the writer fixes them all in a single revision), each with
its beat number, a concrete fix, and a severity:
- "blocking": factual error, content/brand safety, or a story-breaking structure problem (unrelated
  scene, broken causal chain, missing or unearned payoff, flashback after the story has started).
- "minor": a visual that could depict its words more literally, a missing identifying detail,
  wording or style polish. The video still works without the fix.
Verdict is PASS when there are no issues, otherwise FAIL. Put a one-line summary in feedback."""


LOCAL_AI_DOCUMENTARY_EVALUATOR_PROMPT = """You are the quality-control editor for a factual,
object-led documentary rendered with a local AI video generator.

Apply these rules:
1. Beat 1 states the strongest supported outcome. Beat 2 begins the explanation, which then follows
   one causal evidence trail from the real subject through its process or finding to a clear payoff.
2. Every narration claim must be supported by the supplied evidence. Reject invented people,
   discoveries, experiments, quotations, historical actions, locations, measurements, or mechanisms.
3. Do NOT require a human protagonist, recurring presenter, handshake, dramatic gesture, or personal
   stakes. For object-led science/history, `characters: []` is preferred. The subject, mechanism,
   sample, structure, place, animal, or evidence trail carries the story.
4. Anonymous distant workers or gloved hands are acceptable only as neutral illustrative context.
   Reject them when they perform a claimed discovery, experiment, transfer, recovery, or historical event
   not established by evidence. Reject any invented named demonstrator or fictional laboratory narrative.
5. Generated visuals may use ordinary cinematic staging—lens, lighting, composition, neutral tables,
   and clearly illustrative macro/model views—without separate source evidence. Those are not factual
   claims. Reject unsupported factual specifics such as an exact recovery method/location, archival claim,
   object property, human action, or event chronology.
6. Every beat remains a physical `scene`; do not demand stock footage, photos, diagrams, title cards,
   written labels, or literal on-screen numbers. Software adds captions later. A visual should depict the
   supported object/process behind the narration, but need not spell or count a number inside the image.
7. Require coherent `continuity_in`/`continuity_out` within the same scene/light and a final view that
   visibly resolves the factual question. Explanatory chronology is acceptable; it need not be a human drama.
8. Enforce content safety. Distinguish blocking factual/continuity failures from optional visual polish.

Verdict is PASS when there are no blocking issues. Return every real issue in one structured response."""


from unreal_video.planner import capability_brief  # noqa: E402

UNREAL_EVALUATOR_PROMPT = """You are the quality-control editor for a factual vertical video rendered
as a stylized Unreal Engine engineering diorama made from simple geometric components.

Judge these requirements:
1. Beat 1 is a cold open that states the most surprising fact or outcome (BLOCKING if it only sets
   the scene), and the narration forms one clear cause-and-effect explanation.
2. Every factual claim is supported by the supplied evidence. Reject invented historical events,
   people, quotations, measurements, or mechanisms.
3. The film uses ONE ready-made 3D set (`set`) and every beat's `visual.action` is one of that set's
   actions (listed below). BLOCKING: a beat whose words describe something its action does not show
   (e.g. narration about valves snapping shut over a "store" shot), a topic whose key mechanism no
   action of the set can show, or a last beat that is not "finale".
   The sets and their actions:
""" + "\n".join("   " + line for line in capability_brief().splitlines()) + """
4. Reject visuals requiring people, faces, crowds, animals, battles, weapons, fire, smoke, ruins,
   exact landmarks, archival recreations, written text, clocks, maps, logos, or UI graphics.
5. A visual description should show the physical component or process named by its beat. Numerical
   and contextual facts may be carried by narration and software captions; do not demand that the
   3D scene literally display text or a number.
6. This is an educational schematic, so do not require a human protagonist, dramatic gesture,
   exact real-world geography, photorealism, or an invented story arc. Require a visible progression
   from system input through mechanism to a complete working-system payoff.
7. Enforce the content-safety rules and identify every blocking factual or renderability issue in one pass.

Verdict is PASS when there are no blocking issues. Pure wording or camera polish is minor. Return the
requested structured verdict."""


VERDICT_TOOL = {
    "name": "submit_verdict",
    "description": "Submit the PASS/FAIL quality verdict for the video script.",
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
            "feedback": {
                "type": "string",
                "description": "Required if FAIL: one-line summary of what to fix. Empty/omit if PASS."
            },
            "issues": {
                "type": "array",
                "description": "Every issue found, all at once. Empty if PASS.",
                "items": {
                    "type": "object",
                    "properties": {
                        "beat": {"type": "integer", "description": "1-based beat number; 0 for the whole script."},
                        "severity": {"type": "string", "enum": ["blocking", "minor"]},
                        "fix": {"type": "string", "description": "The concrete change to make."},
                    },
                    "required": ["beat", "severity", "fix"],
                },
            },
        },
        "required": ["verdict", "issues"]
    }
}


def evaluate_script(
    script: dict, min_words: int = 55, max_words: int = 220, source: str = "pexels",
    research: list[dict] | None = None,
) -> dict:
    wc = len(script.get("spoken_script", "").split())
    content_mode = script.get("content_mode", "documentary")
    prompt = f"""Evaluate this video script:
{json.dumps(script, indent=2)}

(Length already verified: {wc} words, target {min_words}–{max_words}. Do not judge length.)
Check facts strictly. Check for forbidden pain/harm/weapon language in EVERY beat.
CONTENT MODE: {content_mode}. If documentary, FAIL any invented event, discovery, person, quotation,
place, artifact, or scientific claim. If fiction, require the title, narration and description to label it.
SOURCE EVIDENCE: {json.dumps(research or script.get('research_sources', []), indent=2)}
For documentary content, every specific claim must be supported by this evidence. Unsupported claims FAIL.
Confirm each beat's visual shows exactly what that beat's words say.
Be lenient on cinematic style. Submit your verdict as the structured output."""

    system = (UNREAL_EVALUATOR_PROMPT if source == "unreal" else
              LOCAL_AI_DOCUMENTARY_EVALUATOR_PROMPT if source == "local-ai" and content_mode == "documentary"
              else EVALUATOR_PROMPT)
    result = ai_router.ask(system, prompt, VERDICT_TOOL["input_schema"], effort="medium")
    if not isinstance(result, dict) or result.get("verdict") not in {"PASS", "FAIL"}:
        raise ValueError("Evaluator response must contain verdict PASS or FAIL")
    issues = [i for i in (result.get("issues") or []) if isinstance(i, dict) and i.get("fix")]
    for issue in issues:
        if issue.get("severity") not in {"blocking", "minor"}:
            issue["severity"] = "blocking"  # unknown severity: never wave it through
    result["issues"] = issues
    if result["verdict"] == "FAIL":
        if not issues and not result.get("feedback"):
            raise ValueError("Evaluator FAIL response must include feedback")
        if issues:
            # One revision brief with every issue, so the rewrite fixes them all at once.
            result["feedback"] = "Fix ALL of these issues in one revision:\n" + "\n".join(
                f"- Beat {i.get('beat') or 'all'} [{i['severity']}]: {i['fix']}" for i in issues)
    result["minor_only"] = bool(issues) and all(i["severity"] == "minor" for i in issues)
    return result


REQUIRED_KEYS = [
    "spoken_script", "beats",
    "video_title", "description", "hashtags", "mood", "target_duration",
]


def has_all_keys(script: dict) -> tuple:
    """Return (ok, missing_keys_list)."""
    if not isinstance(script, dict):
        return False, ["script is not a dict"]
    missing = [k for k in REQUIRED_KEYS if k not in script]
    if "beats" not in missing:
        missing.extend(validate_beats(script.get("beats")))
    return (len(missing) == 0), missing


# On the final attempt, a script up to this fraction outside the word range is
# accepted (the video just runs a little longer/shorter) rather than discarded.
LENGTH_GRACE = 0.2
# Local AI retimes its shots to the recorded voiceover, so a few words over or under
# the range never justify a full rewrite there.
LOCAL_AI_LENGTH_GRACE = 0.1


def length_feedback(wc: int, min_words: int, max_words: int, num_beats: int, grace: float = 0.0):
    """Exact, actionable length feedback — or None when the length is acceptable."""
    target = (min_words + max_words) // 2
    per_beat = max(3, round(target / max(num_beats, 1)))
    if wc > max_words * (1 + grace):
        return (f"LENGTH: the narration is {wc} words but the maximum is {max_words}. Cut at least "
                f"{wc - max_words} words (aim for about {target}): keep beats to ~{per_beat} words "
                "each, and tighten the wordiest beats.")
    if wc < min_words * (1 - grace):
        return (f"LENGTH: the narration is {wc} words but the minimum is {min_words}. Add at least "
                f"{min_words - wc} words (aim for about {target}, ~{per_beat} words per beat).")
    return None


def evaluate_with_retry(topic: str, tone: str = "mysterious", max_retries: int = 3, target_seconds: int = 75,
                        mode: str = "footage", source: str = "pexels", angle: str | None = None,
                        content_mode: str = "documentary", research: list[dict] | None = None) -> dict:
    from agents.script import generate_script, plan_for_duration

    num_beats, min_words, max_words = plan_for_duration(target_seconds)

    previous, last_feedback = None, None
    for attempt in range(1, max_retries + 1):
        final = attempt == max_retries
        log.info(f"--- Attempt {attempt}{' (revising previous draft)' if previous else ''} ---")
        try:
            # After a failure, the model revises its own draft to fix the exact issue.
            script = generate_script(topic, tone, target_seconds=target_seconds,
                                     previous=previous, feedback=last_feedback, mode=mode,
                                     angle=angle, content_mode=content_mode, research=research)
        except Exception as e:
            log.error(f"Script generation crashed: {e}")
            if final:
                return None
            continue

        # Check required keys first
        ok, missing = has_all_keys(script)
        if not ok:
            log.warning(f"Script missing keys: {missing}. Retrying...")
            previous = script if isinstance(script, dict) else None
            last_feedback = "Fix these schema problems: " + "; ".join(missing[:8])
            if final:
                log.warning("Max retries reached. Skipping this topic.")
                return None
            continue

        wc = len(script["spoken_script"].split())
        log.info(f"Script generated. Word count: {wc} (target {min_words}-{max_words})")

        # Length is checked in code (free, exact) — the model judge can't count reliably.
        grace = LENGTH_GRACE if final else LOCAL_AI_LENGTH_GRACE if mode in {"local-ai", "unreal"} else 0.0
        problem = length_feedback(wc, min_words, max_words, num_beats, grace=grace)
        if problem:
            log.warning(f"Failed. Feedback: {problem}")
            previous, last_feedback = script, problem
            if final:
                log.warning("Max retries reached. Skipping this topic.")
                return None
            continue
        if not min_words <= wc <= max_words:
            log.warning(f"Accepting {wc} words (within the {grace:.0%} length grace).")

        try:
            result = evaluate_script(
                script, min_words=min_words, max_words=max_words, source=source, research=research
            )
        except Exception as e:
            log.error(f"Script evaluation crashed: {e}")
            if final:
                return None
            continue
        log.info(f"Verdict: {result['verdict']}")

        if result["verdict"] == "PASS":
            log.info("Script approved.")
            return script
        else:
            previous, last_feedback = script, result["feedback"]
            log.warning(f"Failed. Feedback: {last_feedback}")
            if result.get("minor_only"):
                # Polish notes alone never cost a full rewrite: facts, safety and structure passed.
                log.warning("Accepting the draft: only minor issues remain (facts, safety and structure passed).")
                return script
            if final:
                log.warning("Max retries reached. Skipping this topic.")
                return None
    return None



if __name__ == "__main__":
    test_topic = "The Antikythera mechanism — a 2000-year-old Greek device that predicted eclipses"
    log.info(f"Testing: {test_topic}")
    approved = evaluate_with_retry(test_topic, tone="epic")
    if approved:
        log.info(f"APPROVED: {approved['video_title']}")
