import anthropic
import json
import os
import re
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
3. LENGTH: Word count between 55 and 95.
4. BRAND SAFETY: No political, religious, or controversial framing.
5. SCENE QUALITY: All 6 scenes must include shot type, subject, lighting, and camera movement.
   Scenes should vary in shot type — not repetitive.
6. CINEMATIC QUALITY: Scenes should reference real visual styles and include atmosphere details.
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


def evaluate_script(script: dict) -> dict:
    prompt = f"""Evaluate this video script:
{json.dumps(script, indent=2)}

Check facts strictly. Check for forbidden pain/harm/weapon language in EVERY scene. 
Be lenient on cinematic style. Output only JSON."""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=300,
        system=EVALUATOR_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    raw = m.group(1).strip() if m else raw.strip()
    result = json.loads(raw)
    if not isinstance(result, dict) or result.get("verdict") not in {"PASS", "FAIL"}:
        raise ValueError("Evaluator response must contain verdict PASS or FAIL")
    if result["verdict"] == "FAIL" and not result.get("feedback"):
        raise ValueError("Evaluator FAIL response must include feedback")
    return result


REQUIRED_KEYS = [
    "spoken_script", "scene_1", "scene_2", "scene_3", "scene_4", "scene_5", "scene_6",
    "video_title", "description", "hashtags", "mood", "target_duration", "pexels_queries"
]


def has_all_keys(script: dict) -> tuple:
    """Return (ok, missing_keys_list)."""
    if not isinstance(script, dict):
        return False, ["script is not a dict"]
    missing = [k for k in REQUIRED_KEYS if k not in script]
    return (len(missing) == 0), missing


def evaluate_with_retry(topic: str, tone: str = "mysterious", max_retries: int = 3) -> dict:
    from agents.script import generate_script

    for attempt in range(1, max_retries + 1):
        log.info(f"--- Attempt {attempt} ---")
        try:
            script = generate_script(topic, tone)
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
            result = evaluate_script(script)
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
            log.warning(f"Failed. Feedback: {result['feedback']}")
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
