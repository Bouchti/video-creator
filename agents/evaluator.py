import anthropic
import json
import os
import logging
from dotenv import load_dotenv
from config.paths import get_env_path, CLAUDE_MODEL
from agents.beats import validate_beats

load_dotenv(get_env_path())

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
log = logging.getLogger("pipeline")

EVALUATOR_PROMPT = """You are a quality control agent for premium viral video scripts.

RUBRIC:
1. HOOK: First sentence must be surprising, bold, or mysterious. Dry openers FAIL.
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
     Be lenient on exact framing and camera choice.
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
   and ending payoff must be specific and mutually consistent. Each shot's continuity_out must match
   the next shot's continuity_in. Reject vague goals, repeated filler, broken geography, unmotivated
   actions, contradictions, or endings that do not causally resolve the opening setup.

Be STRICT on facts and content safety. Be LENIENT on style details. When in doubt about facts/safety, FAIL. When in doubt about style, PASS.

Output ONLY valid JSON:
{"verdict": "PASS", "feedback": null}
or
{"verdict": "FAIL", "feedback": "One specific thing to fix — name the exact beat number and what to fix"}"""


VERDICT_TOOL = {
    "name": "submit_verdict",
    "description": "Submit the PASS/FAIL quality verdict for the video script.",
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
            "feedback": {
                "type": "string",
                "description": "Required if FAIL: one specific thing to fix — name the exact beat number and what to fix. Empty/omit if PASS."
            },
        },
        "required": ["verdict"]
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
Be lenient on cinematic style. Submit your verdict with the submit_verdict tool."""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=400,
        system=EVALUATOR_PROMPT,
        tools=[VERDICT_TOOL],
        tool_choice={"type": "tool", "name": "submit_verdict"},
        messages=[{"role": "user", "content": prompt}]
    )

    result = None
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "submit_verdict":
            result = block.input
            break
    if not isinstance(result, dict) or result.get("verdict") not in {"PASS", "FAIL"}:
        raise ValueError("Evaluator response must contain verdict PASS or FAIL")
    if result["verdict"] == "FAIL" and not result.get("feedback"):
        raise ValueError("Evaluator FAIL response must include feedback")
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


def length_feedback(wc: int, min_words: int, max_words: int, num_beats: int, grace: float = 0.0):
    """Exact, actionable length feedback — or None when the length is acceptable."""
    target = (min_words + max_words) // 2
    per_beat = max(3, round(target / max(num_beats, 1)))
    if wc > max_words * (1 + grace):
        return (f"LENGTH: the narration is {wc} words but the maximum is {max_words}. Cut about "
                f"{wc - target} words: keep beats to ~{per_beat} words each, and merge or drop "
                "the weakest beats.")
    if wc < min_words * (1 - grace):
        return (f"LENGTH: the narration is {wc} words but the minimum is {min_words}. Add about "
                f"{target - wc} words (~{per_beat} words per beat).")
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
        problem = length_feedback(wc, min_words, max_words, num_beats,
                                  grace=LENGTH_GRACE if final else 0.0)
        if problem:
            log.warning(f"Failed. Feedback: {problem}")
            previous, last_feedback = script, problem
            if final:
                log.warning("Max retries reached. Skipping this topic.")
                return None
            continue
        if not min_words <= wc <= max_words:
            log.warning(f"Accepting {wc} words on the final attempt (within {LENGTH_GRACE:.0%} grace).")

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
