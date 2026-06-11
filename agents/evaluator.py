import anthropic
import json
import os
import logging
from dotenv import load_dotenv
from config.paths import get_env_path, CLAUDE_MODEL

load_dotenv(get_env_path())

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
log = logging.getLogger("pipeline")

EVALUATOR_PROMPT = """You are a quality control agent for premium viral video scripts.

RUBRIC:
1. HOOK: First sentence must be surprising, bold, or mysterious. Dry openers FAIL.
2. FACTUAL ACCURACY: No hallucinations or verifiably false claims. STRICTEST check.
3. LENGTH: Word count must be within the expected range given in the user message.
4. BRAND SAFETY: No political, religious, or controversial framing.
5. SCENE QUALITY: Every scene must include shot type, subject, and camera movement.
   Scenes should vary in shot type — not repetitive.
6. CONNECTEDNESS: The scenes must form ONE continuous world with a recurring subject — a single
   short film, not unrelated clips. There must be a shared `visual_style`. If scenes jump between
   unrelated contexts/subjects, FAIL with feedback naming the disconnected scene.
7. CONTENT SAFETY: Scene prompts MUST NOT contain ANY of these phrases or concepts:
   - "pain", "agony", "suffering", "screaming in distress", "writhing", "contorted"
   - "blood", "wound", "burned", "injured", "bleeding"
   - "weapon", "gun", "knife", "blade"
   - "violent", "attack", any depiction of harm to a person's body
   - Anything showing a person suffering or being hurt
   If a scene depicts drama through suffering/pain instead of through environment/action, FAIL it.

Be STRICT on facts and content safety. Be LENIENT on style details. When in doubt about facts/safety, FAIL. When in doubt about style, PASS.

Output ONLY valid JSON:
{"verdict": "PASS", "feedback": null}
or
{"verdict": "FAIL", "feedback": "One specific thing to fix — name the exact scene and the exact phrase to remove"}"""


VERDICT_TOOL = {
    "name": "submit_verdict",
    "description": "Submit the PASS/FAIL quality verdict for the video script.",
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
            "feedback": {
                "type": "string",
                "description": "Required if FAIL: one specific thing to fix — name the exact scene and the exact phrase to remove. Empty/omit if PASS."
            },
        },
        "required": ["verdict"]
    }
}


def evaluate_script(
    script: dict, min_words: int = 55, max_words: int = 220, source: str = "hailuo"
) -> dict:
    wc = len(script.get("spoken_script", "").split())
    comfy_check = ""
    if source == "comfy":
        comfy_check = """
8. LOCAL AI LITERALNESS: Every scene must show a specific visible subject/action from the
   topic — not generic stock-style b-roll. A silent viewer should follow the story. If scenes
   are vague, abstract, or could fit any topic, FAIL with feedback naming which scene lacks
   concrete story visuals.
"""
    prompt = f"""Evaluate this video script:
{json.dumps(script, indent=2)}

Expected spoken_script word count for this video: {min_words}–{max_words} words (actual: {wc} words).
Video source: {source}
Check facts strictly. Check for forbidden pain/harm/weapon language in EVERY scene.
Confirm the scenes form ONE connected world (recurring subject), not unrelated clips.
{comfy_check}
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
    "spoken_script", "scenes", "visual_style",
    "video_title", "description", "hashtags", "mood", "target_duration", "pexels_queries"
]


def has_all_keys(script: dict) -> tuple:
    """Return (ok, missing_keys_list)."""
    if not isinstance(script, dict):
        return False, ["script is not a dict"]
    missing = [k for k in REQUIRED_KEYS if k not in script]
    if "scenes" not in missing and (not isinstance(script.get("scenes"), list) or len(script["scenes"]) < 2):
        missing.append("scenes (need a non-trivial list)")
    return (len(missing) == 0), missing


def evaluate_with_retry(
    topic: str,
    tone: str = "mysterious",
    max_retries: int = 3,
    target_seconds: int = 75,
    source: str = "hailuo",
) -> dict:
    from agents.script import generate_script, plan_for_duration

    _, min_words, max_words = plan_for_duration(target_seconds, source=source)

    last_feedback = None
    for attempt in range(1, max_retries + 1):
        log.info(f"--- Attempt {attempt} ---")
        # Append previous failure feedback so the generator can fix the exact issue.
        augmented_topic = topic if not last_feedback else f"{topic}\n\nPREVIOUS ATTEMPT FAILED — fix this before regenerating: {last_feedback}"
        try:
            script = generate_script(
                augmented_topic, tone, target_seconds=target_seconds, source=source
            )
        except Exception as e:
            log.error(f"Script generation crashed: {e}")
            if attempt == max_retries:
                return None
            continue

        # Check required keys first
        ok, missing = has_all_keys(script)
        if not ok:
            log.warning(f"Script missing keys: {missing}. Retrying...")
            if attempt == max_retries:
                log.warning("Max retries reached. Skipping this topic.")
                return None
            continue

        wc = len(script["spoken_script"].split())
        log.info(f"Script generated. Word count: {wc}")

        try:
            result = evaluate_script(
                script, min_words=min_words, max_words=max_words, source=source
            )
        except Exception as e:
            log.error(f"Script evaluation crashed: {e}")
            if attempt == max_retries:
                return None
            continue
        log.info(f"Verdict: {result['verdict']}")

        if result["verdict"] == "PASS":
            log.info("Script approved.")
            return script
        else:
            last_feedback = result["feedback"]
            log.warning(f"Failed. Feedback: {last_feedback}")
            if attempt == max_retries:
                log.warning("Max retries reached. Skipping this topic.")
                return None
    return None



if __name__ == "__main__":
    test_topic = "The Antikythera mechanism — a 2000-year-old Greek device that predicted eclipses"
    log.info(f"Testing: {test_topic}")
    approved = evaluate_with_retry(test_topic, tone="epic")
    if approved:
        log.info(f"APPROVED: {approved['video_title']}")
