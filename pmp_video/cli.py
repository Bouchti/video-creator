"""Command line for the PMP Exam Lab pipeline. See pmp_video/__init__.py for the formats."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

log = logging.getLogger("pipeline")


def _args(argv=None):
    p = argparse.ArgumentParser(prog="python -m pmp_video", description="PMP Exam Lab videos with HyperFrames")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--voice-engine", choices=["pipeline", "silent"], default="pipeline",
                        help="pipeline = the repo's ElevenLabs/free voices; silent = layout check without TTS")
        sp.add_argument("--quality", choices=["draft", "looks", "delivery"], default="delivery")
        sp.add_argument("--no-captions", action="store_true", help="No burned-in captions")
        sp.add_argument("--script-only", action="store_true", help="Write script.json and stop (review, then render)")
        sp.add_argument("--no-render", action="store_true", help="Voice and compose index.html, skip the MP4")
        sp.add_argument("--from-script", type=Path, help="Use a prepared script.json instead of writing one")
        sp.add_argument("--publish", choices=["youtube", "tiktok", "instagram"], action="append", default=[],
                        help="Prepare a publish package next to the video (uploads only with --publish-live)")
        sp.add_argument("--publish-live", action="store_true")

    s = sub.add_parser("short", help="9:16 short")
    s.add_argument("kind", choices=["question", "trap", "term", "mindset"])
    s.add_argument("--question-id", help="A bank question id (question/trap)")
    s.add_argument("--domain", choices=["people", "process", "business"])
    s.add_argument("--approach", choices=["predictive", "agile", "hybrid"])
    s.add_argument("--difficulty", choices=["easy", "medium", "hard"])
    s.add_argument("--topic", help="Term pair or mindset theme; for question/trap, keywords to match in the bank")
    common(s)

    lg = sub.add_parser("long", help="16:9 long video")
    lg.add_argument("kind", choices=["walkthrough", "course"])
    lg.add_argument("--count", type=int, default=10, help="Questions in a walkthrough")
    lg.add_argument("--domain", choices=["people", "process", "business"])
    lg.add_argument("--approach", choices=["predictive", "agile", "hybrid"])
    lg.add_argument("--difficulty", choices=["easy", "medium", "hard"])
    lg.add_argument("--topic", help="Course topic (required for course); keywords for a walkthrough")
    lg.add_argument("--minutes", type=int, default=12, help="Target course length")
    lg.add_argument("--notes", type=Path, help="Your own lesson notes (text/markdown) to teach from")
    lg.add_argument("--title", help="Override the video title")
    common(lg)

    r = sub.add_parser("render", help="Re-compose and render an existing project (after editing script.json)")
    r.add_argument("project", type=Path)
    r.add_argument("--voice-engine", choices=["pipeline", "silent"], default="pipeline")
    r.add_argument("--quality", choices=["draft", "looks", "delivery"], default="delivery")
    r.add_argument("--no-captions", action="store_true")
    return p.parse_args(argv)


def write_script(a) -> dict:
    from pmp_video import bank, writer
    if a.from_script:
        return json.loads(a.from_script.read_text(encoding="utf-8"))
    filters = dict(domain=a.domain, approach=a.approach, difficulty=a.difficulty)
    if a.cmd == "short":
        if a.kind in ("question", "trap"):
            candidates = [bank.by_id(a.question_id)] if a.question_id else \
                bank.pick(a.kind, 4, keywords=a.topic, **filters)
            make = writer.short_question if a.kind == "question" else writer.short_trap
            for q in candidates:
                try:
                    return make(q)
                except writer.QuestionRejected as exc:
                    log.warning("[pmp] %s", exc)
            raise SystemExit("No candidate question passed the consistency check")
        return writer.short_term(a.topic) if a.kind == "term" else writer.short_mindset(a.topic)
    if a.kind == "walkthrough":
        qs = bank.pick("walkthrough", a.count + 4, keywords=a.topic, **filters)
        return writer.long_walkthrough(qs, title=a.title, count=a.count)
    if not a.topic:
        raise SystemExit("long course needs --topic")
    notes = a.notes.read_text(encoding="utf-8") if a.notes else ""
    script = writer.long_course(a.topic, a.minutes, notes)
    if a.title:
        script["title"] = a.title
    return script


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    try:
        from dotenv import load_dotenv
        from pmp_video.config import PROJECT_ROOT
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass
    a = _args(argv)
    from pmp_video import bank, project

    if a.cmd == "render":
        script = project.load_script(a.project)
        project.compose(a.project, script, a.voice_engine, captions_on=not a.no_captions)
        out = project.render(a.project, a.quality)
        print(out)
        return 0

    script = write_script(a)
    path = project.new_project(script)
    log.info("[pmp] script: %s", path / "script.json")
    if a.script_only:
        print(path)
        return 0
    project.compose(path, script, a.voice_engine, captions_on=not a.no_captions)
    if a.no_render:
        print(path / "index.html")
        return 0
    out = project.render(path, a.quality)
    if script.get("question_ids") and a.voice_engine == "pipeline":
        bank.mark_used(script["format"], script["question_ids"])
    for platform in a.publish:
        from agents.publisher import publish_video
        post = json.loads((path / "post.json").read_text(encoding="utf-8"))
        publish_video(out, platform, {"title": post["title"], "description": post["description"],
                                      "tags": post["tags"]}, live=a.publish_live)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
