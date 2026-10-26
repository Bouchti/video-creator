"""
Autonomous vertical-video pipeline.

Every video is built from script BEATS: each sentence of narration carries the
visual shown while it is spoken.
  pexels   - Stock/archival footage, real photos, and diagrams (~$0/video, fast)
  local-ai - Durable MiniMax/Wan production with strict scene and final review (default)

Usage:
  python main.py                                           # AI chooses a current topic
  python main.py --duration 60                             # autonomous 60-second video
  python main.py --source pexels "Custom topic here"       # custom topic, stock
  python main.py --publish youtube                         # prepare a publish package
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


class _SafeStreamHandler(logging.StreamHandler):
    """Avoid Windows cp1252 crashes when log messages contain Unicode."""

    def emit(self, record):
        try:
            super().emit(record)
        except UnicodeEncodeError:
            record.msg = str(record.msg).encode("ascii", errors="replace").decode("ascii")
            record.args = None
            super().emit(record)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        _SafeStreamHandler(),
    ],
)
log = logging.getLogger("pipeline")

DEFAULT_TOPIC = "The hidden science behind why ocean waves never stop moving"
DEFAULT_TONE = "mysterious"
DEFAULT_VOICE = "mysterious"
DEFAULT_SOURCE = "local-ai"

OUTPUT_DIR = get_output_dir()


def write_post_notes(video_path: str, script: dict, credits: list) -> str:
    """Write title/description/hashtags + photo credits next to the video.

    CC BY / BY-SA photos require attribution — paste the credits into the post
    description (or pinned comment) when publishing.
    """
    notes_path = os.path.splitext(video_path)[0] + ".txt"
    lines = [script.get("video_title", ""), "", script.get("description", ""), "",
             " ".join(script.get("hashtags", []))]
    if credits:
        lines += ["", "Photo credits (Wikimedia Commons):"] + [f"- {c}" for c in credits]
    sources = script.get("research_sources") or []
    if sources:
        lines += ["", "Research sources:"] + [
            f"- {source.get('title', 'Source')}: {source.get('url')}"
            for source in sources if source.get("url")
        ]
    with open(notes_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return notes_path


def run_pipeline(
    topic: str = None,
    source: str = DEFAULT_SOURCE,
    tone: str = None,
    voice: str = DEFAULT_VOICE,
    duration: int = 75,
    backend: str = "auto",
    visual_style: str = None,
    reference_image: str = None,
    music: str = "subtle cinematic",
    ambience: str = "natural location ambience",
    captions: bool = True,
    narration: bool = True,
    publish_platforms: tuple[str, ...] = (),
    publish_live: bool = False,
) -> dict:
    started = datetime.now()
    log.info("=" * 70)
    log.info(f"PIPELINE START | {started.strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 70)

    selection = None
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

    research = selection.get("research", []) if selection else []
    if not research:
        log.info("\n[STAGE 0B] Researching factual source evidence")
        try:
            from agents.leader import research_topic
            research = research_topic(topic)
        except Exception as e:
            log.error(f"Topic research failed: {e}")
            return {"success": False, "stage_failed": "research", "topic": topic, "error": str(e)}

    log.info(f"Source: {source}  |  Tone: {tone}  |  Voice: {voice}  |  Duration: {duration}s")

    log.info("\n[STAGE 1] Script generation + evaluation")
    from agents.evaluator import evaluate_with_retry
    mode = "local-ai" if source == "local-ai" else "footage"
    angle = selection.get("angle") if selection else None
    script = evaluate_with_retry(topic, tone=tone, max_retries=3, target_seconds=duration, mode=mode,
                                 source=source, angle=angle, research=research)
    if not script:
        log.error("Script generation failed. Aborting.")
        return {"success": False, "stage_failed": "script", "topic": topic}

    log.info(f"Script approved: {script['video_title']}")
    log.info(f"Word count: {len(script['spoken_script'].split())}")

    log.info(f"\n[STAGE 2] Video generation ({source})")

    if source == "pexels":
        from agents.editor_pexels import process_video
    elif source == "local-ai":
        from agents.editor_local_ai import process_video
    else:
        log.error(f"Unknown source: {source}. Use 'pexels' or 'local-ai'.")
        return {"success": False, "stage_failed": "source_invalid", "topic": topic}

    try:
        if source == "local-ai":
            final_path = process_video(
                script,
                voice=voice,
                duration=duration,
                backend=backend,
                visual_style=visual_style,
                reference_image=reference_image,
                music=music,
                ambience=ambience,
                captions=captions,
                narration_enabled=narration,
            )
        else:
            final_path = process_video(script, voice=voice)
    except Exception as e:
        log.error(f"Editor failed: {e}", exc_info=True)
        return {"success": False, "stage_failed": "editor", "topic": topic, "error": str(e)}

    ts = started.strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c if c.isalnum() else "_" for c in script["video_title"])[:60]
    output_path = os.path.join(OUTPUT_DIR, f"{ts}_{source}_{safe_title}.mp4")
    if source == "local-ai":
        # The durable project keeps its canonical final render; preserve the
        # legacy top-level output convention with a copy.
        shutil.copy2(final_path, output_path)
    else:
        shutil.move(final_path, output_path)
    credits = script.get("credits") or []
    notes_path = write_post_notes(output_path, script, credits)
    from agents.post_text import write as write_post_text
    post_text_path = write_post_text(script, output_path)
    if selection:
        from agents.leader import save_used_topic
        save_used_topic(topic)

    publishing = []
    if publish_platforms:
        from agents.publisher import publish_video
        publish_metadata = {
            "title": script["video_title"],
            "description": script.get("description", ""),
            "hashtags": script.get("hashtags", []),
            "ai_generated": source == "local-ai",
        }
        try:
            publishing = [
                publish_video(output_path, platform, publish_metadata, live=publish_live)
                for platform in publish_platforms
            ]
        except Exception as e:
            log.error(f"Publishing failed: {e}", exc_info=True)
            return {
                "success": False, "stage_failed": "publishing", "topic": topic,
                "video_path": output_path, "notes_path": notes_path,
                "post_text_path": post_text_path, "publishing": publishing, "error": str(e),
            }

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
            "credits": credits,
        },
        "notes_path": notes_path,
        "post_text_path": post_text_path,
        "publishing": publishing,
        "elapsed_minutes": round(elapsed_min, 1),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the video pipeline.")
    parser.add_argument("topic", nargs="?", default=None,
                        help="Custom topic (optional). If not provided, Leader Agent picks a trending one.")
    parser.add_argument("--source", choices=["cutaway", "evolution", "pexels", "local-ai"],
                        default=DEFAULT_SOURCE,
                        help="local-ai (durable MiniMax/Wan production; default), cutaway (3D cross-section "
                             "explainer: the showrunner picks a filmable topic, critiques and renders), "
                             "evolution (one 3D world, escalating problem -> solution: plank -> arch -> "
                             "truss -> suspension bridge), "
                             "or pexels (free stock + photos + diagrams)")
    parser.add_argument("--set", default=None, help="Evolution set for --source evolution (default: the first in "
                                                    "engine/sets EVOLUTION; new sets: python -m agents.set_builder)")
    parser.add_argument("--tone", default=None, help="Script tone")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help="Voice style")
    parser.add_argument("--duration", type=int, default=75,
                        help="Target video length in seconds (30-90). Scales narration + scene count.")
    parser.add_argument("--backend", choices=["auto", "minimax", "wan"], default="auto",
                        help="Backend for --source local-ai (Auto prefers MiniMax H3 and records Wan fallback)")
    parser.add_argument("--visual-style", default=None, help="Shared visual style for --source local-ai")
    parser.add_argument("--reference-image", default=None, help="Optional continuity reference image")
    parser.add_argument("--music", default="subtle cinematic", help="Music preference or configured track")
    parser.add_argument("--ambience", default="natural location ambience", help="Ambience direction")
    parser.add_argument("--no-captions", action="store_true", help="Disable captions for --source local-ai")
    parser.add_argument("--no-narration", action="store_true", help="Create a music-and-ambience local AI edit")
    parser.add_argument("--publish", action="append", choices=["youtube", "instagram", "tiktok"], default=[],
                        help="Prepare a publish package (repeat for multiple platforms)")
    parser.add_argument("--publish-live", action="store_true",
                        help="Actually upload; also requires PUBLISH_ENABLED=1 and platform credentials")
    args = parser.parse_args()

    if args.publish_live and not args.publish:
        parser.error("--publish-live requires at least one --publish PLATFORM")

    if args.source in ("evolution", "cutaway"):
        # The 3D pipelines run under the autopilot: script → voice → Blender render (every ~3 s window
        # validated as it renders) → sound + captions → final check, and every failure is repaired and
        # redone automatically (agents/autopilot.py). A positional topic is the angle to develop.
        from agents.autopilot import GiveUp, run as autopilot
        try:
            film_path = autopilot(args.source, angle=args.topic, set_id=args.set)
            logging.getLogger("pipeline").info(f"Film: {film_path}")
            if args.publish:
                from agents.publisher import publish_video
                for platform in args.publish:
                    package = publish_video(film_path, platform, {"ai_generated": True}, live=args.publish_live)
                    logging.getLogger("pipeline").info(
                        f"{platform} publish status: {package.get('status')} ({package.get('package_path')})"
                    )
        except GiveUp:
            raise SystemExit(1)
        raise SystemExit(0)

    # Pass tone=None if user didn't override, so Leader Agent's choice wins
    user_tone = args.tone
    result = run_pipeline(
        topic=args.topic,
        source=args.source,
        tone=user_tone,
        voice=args.voice,
        duration=args.duration,
        backend=args.backend,
        visual_style=args.visual_style,
        reference_image=args.reference_image,
        music=args.music,
        ambience=args.ambience,
        captions=not args.no_captions,
        narration=not args.no_narration,
        publish_platforms=tuple(args.publish),
        publish_live=args.publish_live,
    )

    if result["success"]:
        print(f"\nSUCCESS")
        print(f"  Source: {result['source']}")
        print(f"  Video:  {result['video_path']}")
        print(f"  Title:  {result['title']}")
        print(f"  Notes:  {result['notes_path']}")
        print(f"  Posts:  {result['post_text_path']}")
        for package in result.get("publishing", []):
            print(f"  Publish ({package['platform']}): {package['status']}")
        print(f"  Time:   {result['elapsed_minutes']} min")
        sys.exit(0)
    else:
        print(f"\nFAILED at stage: {result.get('stage_failed', 'unknown')}")
        if "error" in result:
            print(f"  Error: {result['error']}")
        sys.exit(1)
