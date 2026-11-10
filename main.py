"""
Autonomous vertical-video pipeline.

Every video is built from script BEATS: each sentence of narration carries the
visual shown while it is spoken.
  pexels   - Stock/archival footage, real photos, and diagrams (~$0/video, fast)
  local-ai - Durable MiniMax/Wan production with strict scene and final review (default)
  evolution - Problem -> solution ladder ("you built a bridge... so you..."), filmed by the local AI:
             MiniMax H3 via FreeVideo only, then a Real-ESRGAN x2plus final upscale. Its look is a
             photoreal 3D cutaway (FLUX still -> MiniMax clip per shot; local_video/looks.py) unless
             --look photo or EVOLUTION_LOOK=photo
  unreal   - Local UE5 Sequencer/Movie Render Queue cinematics (no per-render API fee)

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

DEFAULT_TONE = "mysterious"
DEFAULT_VOICE = "mysterious"
DEFAULT_SOURCE = "local-ai"
from local_video.looks import evolution_look  # noqa: E402  (--source evolution's look: cutaway or photo)

def default_duration() -> int:
    """Target length when --duration is not given: VIDEO_DURATION from .env, else 62 s."""
    try:
        return int(os.getenv("VIDEO_DURATION") or 62)
    except ValueError:
        return 62

OUTPUT_DIR = get_output_dir()


def run_pipeline(
    topic: str = None,
    source: str = DEFAULT_SOURCE,
    tone: str = None,
    voice: str = DEFAULT_VOICE,
    duration: int = None,
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
    if duration is None:
        duration = default_duration()
    started = datetime.now()
    # Local-ai fast mode fits the whole run, topic to final video, into LOCAL_VIDEO_BUDGET_MINUTES.
    os.environ["PIPELINE_STARTED_AT"] = str(started.timestamp())
    # Evolution films are written in their own ladder format and filmed by the local-ai pipeline.
    local_ai = source in ("local-ai", "evolution")
    if source == "evolution":
        # Evolution is MiniMax H3 only: a Wan fallback would change the look mid-ladder.
        if backend not in ("auto", "minimax"):
            log.warning(f"--backend {backend} ignored: evolution films always use MiniMax H3 via FreeVideo.")
        backend = "minimax"
    if local_ai:
        # Fail before the paid script step, not after it.
        from local_video.planner import validate_duration
        try:
            validate_duration(duration)
        except ValueError as e:
            log.error(str(e))
            return {"success": False, "stage_failed": "duration", "error": str(e)}
    if source == "evolution":
        problem = minimax_preflight()
        if problem:
            log.error(problem)
            return {"success": False, "stage_failed": "minimax_preflight", "error": problem}
    log.info("=" * 70)
    log.info(f"PIPELINE START | {started.strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 70)

    # UE is a large local prerequisite. Fail before spending trend/script API calls when it is absent.
    if source == "unreal":
        from unreal_video.config import UnrealConfig
        unreal_config = UnrealConfig()
        problems = []
        if not unreal_config.editor:
            problems.append("Unreal Engine 5 was not found; install UE 5.8 or set UNREAL_EDITOR_CMD in .env")
        if not unreal_config.project.is_file():
            problems.append(f"Unreal project is missing: {unreal_config.project}")
        if problems:
            error = "; ".join(problems)
            log.error(f"Unreal preflight failed: {error}")
            return {"success": False, "stage_failed": "unreal_preflight", "error": error}

    selection = None
    manual_topic = topic is not None
    if manual_topic:
        log.info(f"Topic (manual): {topic}")
    requested_tone = tone
    from agents.evaluator import evaluate_with_retry
    mode = "unreal" if source == "unreal" else "local-ai" if local_ai else "footage"
    content_mode = "evolution" if source == "evolution" else "documentary"
    # Documentary drafts converge instead of passing outright: the evaluator finds the unsourced
    # claims a few at a time, so each revision clears some and the next one surfaces fewer. Three
    # attempts stranded a draft one blocking issue from PASS, throwing away the whole topic and its
    # research. Each attempt is ~25k tokens and CLAUDE_TOKEN_BUDGET caps the total.
    attempts = int(os.getenv("SCRIPT_MAX_ATTEMPTS") or 5)
    # A topic whose script never passes the fact check is dropped for a fresh one rather than ending
    # the run; an unsourced draft is never used. A manual topic is retried as-is, for transient errors.
    topic_attempts = max(1, int(os.getenv("PIPELINE_TOPIC_ATTEMPTS") or (2 if manual_topic else 3)))
    given_up: list[str] = []
    script, failure = None, None
    for topic_attempt in range(1, topic_attempts + 1):
        if topic_attempt > 1:
            log.warning(f"\nRetrying with {'the same' if manual_topic else 'a new'} topic "
                        f"({topic_attempt}/{topic_attempts}).")
        # Stage 0: Find today's topic via Leader Agent (unless topic explicitly provided)
        if not manual_topic:
            log.info("\n[STAGE 0] Leader Agent: trending topic discovery")
            from agents.leader import find_todays_topic
            try:
                selection = find_todays_topic(source=source, exclude=given_up)
                topic = selection["topic"]
                log.info(f"Selected topic: {topic}")
                log.info(f"Selected angle: {selection['angle']}")
            except Exception as e:
                log.error(f"Leader Agent failed: {e}")
                failure = {"success": False, "stage_failed": "leader", "error": str(e)}
                continue
        tone = requested_tone or (selection["tone"] if selection else DEFAULT_TONE)

        research = selection.get("research", []) if selection else []
        if not research:
            log.info("\n[STAGE 0B] Researching factual source evidence")
            try:
                from agents.leader import research_topic
                research = research_topic(topic)
            except Exception as e:
                log.error(f"Topic research failed: {e}")
                failure = {"success": False, "stage_failed": "research", "topic": topic, "error": str(e)}
                given_up.append(topic)
                continue
        if source == "evolution":
            # Every rung of the ladder needs its own source for WHY it replaced the last one; the topic search
            # alone left the links unsourced and the evaluator rejected every draft.
            log.info("\n[STAGE 0C] Researching every stage of the evolution ladder")
            try:
                from agents.leader import research_ladder
                research = research_ladder(topic, research)
            except Exception as e:
                log.warning(f"Ladder research failed ({e}); writing from the topic evidence only.")

        log.info(f"Source: {source}  |  Tone: {tone}  |  Voice: {voice}  |  Duration: {duration}s"
                 + (f"  |  Look: {evolution_look()}" if source == "evolution" else ""))

        if source == "director":
            # Max and his kids on the generic stage: the plan (script + staging as data) is written and
            # checked by agents/stage_writer.py, then the director films, scores, mixes and composes it.
            log.info("\n[STAGE 1-6] Director: stage plan -> BlenderKit assets -> film")
            from agents import director
            try:
                final_path, plan = director.make(topic, research, selection.get("angle") if selection else None,
                                                 (selection or {}).get("grounding"))
            except Exception as e:
                log.error(f"Director failed for this topic: {e}", exc_info=True)
                failure = {"success": False, "stage_failed": "director", "topic": topic, "error": str(e)}
                given_up.append(topic)
                continue
            script = {"video_title": plan["title"], "description": plan.get("caption", ""),
                      "hashtags": plan.get("hashtags", []), "spoken_script": director.narration(plan),
                      "quality_warnings": plan.get("quality_warnings", []), "director_final": final_path,
                      "credits": plan.get("credits", [])}
            break

        log.info("\n[STAGE 1] Script generation + evaluation")
        angle = selection.get("angle") if selection else None
        # Claims the topic grounder already struck out. The writer otherwise re-supplies them from its
        # own knowledge and the evaluator spends a revision round blocking the same claim a second time.
        excluded = ((selection.get("grounding") or {}).get("dropped") or []) if selection else []
        try:
            script = evaluate_with_retry(topic, tone=tone, max_retries=attempts, target_seconds=duration,
                                         mode=mode, source=source, angle=angle, research=research,
                                         excluded_claims=excluded, content_mode=content_mode)
        except Exception as e:
            log.error(f"Script stage crashed: {e}", exc_info=True)
            script = None
        if script:
            break
        log.error(f"Script generation failed for this topic: {topic}")
        failure = {"success": False, "stage_failed": "script", "topic": topic}
        given_up.append(topic)
    if not script:
        log.error("No topic produced a usable script. Aborting.")
        return failure or {"success": False, "stage_failed": "script", "topic": topic}

    log.info(f"Script approved: {script['video_title']}")
    log.info(f"Word count: {len(script['spoken_script'].split())}")

    log.info(f"\n[STAGE 2] Video generation ({source})")

    if source == "director":
        process_video = None
    elif source == "pexels":
        from agents.editor_beats import process_video
    elif local_ai:
        from agents.editor_local_ai import process_video
    elif source == "unreal":
        from agents.editor_unreal import process_video
    else:
        log.error(f"Unknown source: {source}. Use 'pexels', 'local-ai', 'evolution', or 'unreal'.")
        return {"success": False, "stage_failed": "source_invalid", "topic": topic}

    try:
        if source == "director":
            final_path = script["director_final"]
        elif local_ai:
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
                # Every local-ai film ends on a Real-ESRGAN pass over its accepted clips (544x960 ->
                # 1088x1920): LOCAL_VIDEO_AI_UPSCALE (default x2plus); EVOLUTION_UPSCALE overrides it there.
                ai_upscale=(os.getenv("EVOLUTION_UPSCALE") or None) if source == "evolution" else None,
            )
        elif source == "unreal":
            final_path = process_video(
                script,
                voice=voice,
                duration=duration,
                visual_style=visual_style,
                music=music,
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
    try:
        if local_ai or source in ("unreal", "director"):
            # The durable project keeps its canonical final render; preserve the
            # legacy top-level output convention with a copy.
            shutil.copy2(final_path, output_path)
        else:
            shutil.move(final_path, output_path)
    except OSError as e:
        log.error(f"Could not copy the video to {output_path} ({e}); using it where it was rendered.")
        output_path = str(final_path)
    # The video exists from here on; nothing below may turn a finished render into a failed run.
    credits = script.get("credits") or []
    post_text_path = None
    try:
        from agents.post_text import write as write_post_text
        post_text_path = write_post_text(script, output_path)
    except Exception as e:
        log.error(f"Writing post text failed: {e}", exc_info=True)
    if selection:
        try:
            from agents.leader import save_used_topic
            save_used_topic(topic, subject=selection.get("subject") if source == "evolution" else None)
        except Exception as e:
            log.error(f"Saving the used topic failed: {e}")

    quality_warnings = script.get("quality_warnings") or []
    for warning in quality_warnings:
        log.warning(f"QUALITY WARNING: {warning}")
    publishing = []
    if publish_platforms and script.get("publish_hold") and os.getenv("PUBLISH_FLAGGED_VIDEOS", "0") != "1":
        log.warning("Publishing held: the final creative review rejected this video. Watch it, then publish "
                    "it yourself, or set PUBLISH_FLAGGED_VIDEOS=1 to publish such videos automatically.")
    elif publish_platforms:
        from agents.publisher import publish_video
        publish_metadata = {
            "title": script["video_title"],
            "description": script.get("description", ""),
            "hashtags": script.get("hashtags", []),
            "ai_generated": local_ai or source == "unreal",
        }
        # One platform failing must not cost the others, or the finished video.
        for platform in publish_platforms:
            try:
                publishing.append(publish_video(output_path, platform, publish_metadata, live=publish_live))
            except Exception as e:
                log.error(f"Publishing to {platform} failed: {e}", exc_info=True)
                publishing.append({"platform": platform, "success": False, "error": str(e)})

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
        "post_text_path": post_text_path,
        "publishing": publishing,
        "quality_warnings": quality_warnings,
        "publish_held": bool(publish_platforms and script.get("publish_hold")
                             and os.getenv("PUBLISH_FLAGGED_VIDEOS", "0") != "1"),
        "elapsed_minutes": round(elapsed_min, 1),
    }


def minimax_preflight() -> str | None:
    """Why MiniMax H3 cannot run here, or None. Cheap: checks files and a running server, starts nothing."""
    from local_video.config import PipelineConfig
    from local_video.freevideo import freevideo_root, missing_parts
    if PipelineConfig().minimax_url:
        return None                         # a FreeVideo server is already up
    root = freevideo_root()
    missing = missing_parts(root)
    if missing:
        return (f"Evolution films need MiniMax H3 via FreeVideo, which cannot start from {root}: missing "
                f"{', '.join(missing)}. Set FREEVIDEO_DIR in .env to the FreeVideo engine folder.")
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the video pipeline.")
    parser.add_argument("topic", nargs="?", default=None,
                        help="Custom topic (optional). If not provided, Leader Agent picks a trending one.")
    parser.add_argument("--source", choices=["cutaway", "cutaway-bk", "explainer", "evolution", "pexels", "local-ai",
                                             "unreal", "director"],
                        default=DEFAULT_SOURCE,
                        help="local-ai (durable MiniMax/Wan production; default), cutaway (3D cross-section "
                             "story starring Max: trial and error, critiqued and rendered), cutaway-bk (the same "
                             "Max stories, with whole objects taken from BlenderKit and only the mechanism built), "
                             "explainer (no-hero 3D cutaway explainer in the @youbuiltit format: the build in "
                             "physical order, problem -> fix; builds a new set when none fits), "
                             "evolution (escalating problem -> solution ladder in one photoreal place, e.g. "
                             "plank -> arch -> truss -> suspension bridge, filmed by MiniMax H3 via FreeVideo "
                             "and upscaled with Real-ESRGAN x2plus; EVOLUTION_UPSCALE=off|x4plus|general-x4v3), "
                             "unreal (local UE5 Sequencer + Movie Render Queue), or pexels "
                             "(free stock + photos + diagrams)")
    parser.add_argument("--set", default=None, help="Specific set for cutaway; consumed Max story sets "
                                                    "are rejected unless repeats are explicitly enabled")
    parser.add_argument("--tone", default=None, help="Script tone")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help="Voice style")
    # 62 s by default (VIDEO_DURATION in .env): TikTok's Creator Rewards pays only on videos over one
    # minute, and local_video/queue.py never fits a >60 s project below TIKTOK_MIN_SECONDS (61). The
    # extra length goes into story, not pauses: the read is ~3 words/s now (was ~2.2), see
    # Docs/RETENTION_FIXES_2026-11-01.md.
    parser.add_argument("--duration", type=int, default=None,
                        help="Target video length in seconds (30-90). Scales narration + scene count.")
    parser.add_argument("--backend", choices=["auto", "minimax", "wan"], default="auto",
                        help="Backend for --source local-ai (Auto prefers MiniMax H3 and records Wan fallback); "
                             "--source evolution always uses MiniMax H3")
    parser.add_argument("--visual-style", default=None, help="Shared visual style for local-ai/unreal")
    parser.add_argument("--look", choices=["cutaway", "photo"], default=None,
                        help="Look of --source evolution: cutaway (photoreal 3D cross-section renders, the "
                             "default) or photo (real documentary footage). Overrides EVOLUTION_LOOK in .env.")
    parser.add_argument("--reference-image", default=None, help="Optional continuity reference image")
    parser.add_argument("--music", default="subtle cinematic", help="Music preference or configured track")
    parser.add_argument("--ambience", default="natural location ambience", help="Ambience direction")
    parser.add_argument("--no-captions", action="store_true", help="Disable software captions")
    parser.add_argument("--no-narration", action="store_true", help="Create a music/ambience-only edit")
    parser.add_argument("--publish", action="append", choices=["youtube", "instagram", "tiktok"], default=[],
                        help="Prepare a publish package (repeat for multiple platforms)")
    parser.add_argument("--publish-live", action="store_true",
                        help="Actually upload; also requires PUBLISH_ENABLED=1 and platform credentials")
    args = parser.parse_args()

    if args.publish_live and not args.publish:
        parser.error("--publish-live requires at least one --publish PLATFORM")

    if args.source in ("cutaway", "cutaway-bk", "explainer"):
        # Every downloadable library (CC0 assets, the compositor's npm packages) is fetched before a 3D run
        # starts, so a fresh clone is ready to produce; later runs skip this in milliseconds. The local-ai,
        # unreal and pexels routes use none of them, so they never wait on the ~45 GB first fetch.
        from agents.libraries import ensure as ensure_libraries
        ensure_libraries()

    if args.source in ("cutaway", "cutaway-bk", "explainer"):
        # The 3D pipelines run under the autopilot: script → voice → exact-timing low-res rehearsal
        # (every ~3 s window must pass) → Blender production render with free technical rechecks →
        # sound + captions → final check. This gate is shared by Max cutaways and no-hero explainers.
        # A positional topic is the angle to develop.
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

    if args.look:
        # Read by the topic scout, the script writer and the prompts (local_video/looks.evolution_look).
        os.environ["EVOLUTION_LOOK"] = args.look
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
