"""
Main orchestrator for the autonomous video pipeline.

Three video source modes:
  hailuo  - AI-generated cinematic clips via Hailuo 02 (~$1.50/video, premium)
  pexels  - Free stock footage from Pexels (~$0/video, fast)
  comfy   - AI-generated clips from a LOCAL model via ComfyUI (~$0/video, slow, best quality)

Usage:
  python3 main.py                                          # default: hailuo
  python3 main.py --source pexels                          # use Pexels stock
  python3 main.py --source comfy "Custom topic here"       # custom topic, local AI video
  python3 main.py --source hailuo "Custom topic here"      # custom topic, cloud AI video
  python3 main.py --source pexels "Custom topic here"      # custom topic, stock
"""

import sys
import os
import shutil
import argparse
import logging
from datetime import datetime
from dotenv import load_dotenv
from config.paths import PROJECT_ROOT, get_output_dir, get_log_file

sys.path.insert(0, PROJECT_ROOT)
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

LOG_FILE = get_log_file()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
log = logging.getLogger("pipeline")

DEFAULT_TOPIC = "The hidden science behind why ocean waves never stop moving"
DEFAULT_TONE = "mysterious"
DEFAULT_VOICE = "mysterious"
DEFAULT_SOURCE = "hailuo"

OUTPUT_DIR = get_output_dir()


def run_pipeline(topic: str = None, source: str = DEFAULT_SOURCE, tone: str = None, voice: str = DEFAULT_VOICE, duration: int = 75) -> dict:
    started = datetime.now()
    log.info("=" * 70)
    log.info(f"PIPELINE START | {started.strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 70)

    # Stage 0: Find today's topic via Leader Agent (unless topic explicitly provided)
    if topic is None:
        log.info("\n[STAGE 0] Leader Agent: trending topic discovery")
        from agents.leader import find_todays_topic
        try:
            selection = find_todays_topic()
            topic = selection["topic"]
            tone = tone or selection["tone"]
            log.info(f"Selected topic: {topic}")
            log.info(f"Selected angle: {selection['angle']}")
        except Exception as e:
            log.error(f"Leader Agent failed: {e}")
            return {"success": False, "stage_failed": "leader", "error": str(e)}
    else:
        log.info(f"Topic (manual): {topic}")
        tone = tone or DEFAULT_TONE

    log.info(f"Source: {source}  |  Tone: {tone}  |  Voice: {voice}  |  Duration: {duration}s")

    log.info("\n[STAGE 1] Script generation + evaluation")
    from agents.evaluator import evaluate_with_retry
    script = evaluate_with_retry(topic, tone=tone, max_retries=3, target_seconds=duration)
    if not script:
        log.error("Script generation failed. Aborting.")
        return {"success": False, "stage_failed": "script", "topic": topic}

    log.info(f"Script approved: {script['video_title']}")
    log.info(f"Word count: {len(script['spoken_script'].split())}")

    log.info(f"\n[STAGE 2] Video generation ({source})")

    if source == "pexels":
        from agents.editor_pexels import process_video
    elif source == "hailuo":
        from agents.editor_hailuo import process_video
    elif source == "comfy":
        from agents.editor_comfy import process_video
    else:
        log.error(f"Unknown source: {source}. Use 'hailuo', 'pexels', or 'comfy'.")
        return {"success": False, "stage_failed": "source_invalid", "topic": topic}

    try:
        final_path = process_video(script, voice=voice)
    except Exception as e:
        log.error(f"Editor failed: {e}", exc_info=True)
        return {"success": False, "stage_failed": "editor", "topic": topic, "error": str(e)}

    ts = started.strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c if c.isalnum() else "_" for c in script["video_title"])[:60]
    output_path = os.path.join(OUTPUT_DIR, f"{ts}_{source}_{safe_title}.mp4")
    shutil.move(final_path, output_path)

    elapsed_min = (datetime.now() - started).total_seconds() / 60
    log.info(f"\nFINAL VIDEO: {output_path}")
    log.info(f"Elapsed: {elapsed_min:.1f} minutes")
    log.info("=" * 70)

    return {
        "success": True,
        "topic": topic,
        "source": source,
        "title": script["video_title"],
        "video_path": output_path,
        "metadata": {
            "description": script["description"],
            "hashtags": script["hashtags"],
            "mood": script.get("mood"),
            "word_count": len(script["spoken_script"].split()),
        },
        "elapsed_minutes": round(elapsed_min, 1),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the video pipeline.")
    parser.add_argument("topic", nargs="?", default=None,
                        help="Custom topic (optional). If not provided, Leader Agent picks a trending one.")
    parser.add_argument("--source", choices=["hailuo", "pexels", "comfy"], default=DEFAULT_SOURCE,
                        help="Video source: hailuo (paid cloud AI), pexels (free stock), or comfy (free local AI)")
    parser.add_argument("--tone", default=None, help="Script tone")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help="Voice style")
    parser.add_argument("--duration", type=int, default=75,
                        help="Target video length in seconds (e.g. 60-90). Scales narration + scene count.")
    args = parser.parse_args()

    # Pass tone=None if user didn't override, so Leader Agent's choice wins
    user_tone = args.tone
    result = run_pipeline(
        topic=args.topic,
        source=args.source,
        tone=user_tone,
        voice=args.voice,
        duration=args.duration
    )

    if result["success"]:
        print(f"\nSUCCESS")
        print(f"  Source: {result['source']}")
        print(f"  Video:  {result['video_path']}")
        print(f"  Title:  {result['title']}")
        print(f"  Time:   {result['elapsed_minutes']} min")
        sys.exit(0)
    else:
        print(f"\nFAILED at stage: {result.get('stage_failed', 'unknown')}")
        if "error" in result:
            print(f"  Error: {result['error']}")
        sys.exit(1)
