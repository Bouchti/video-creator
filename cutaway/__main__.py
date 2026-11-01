"""
    python -m cutaway make "How a car engine works" --length 70 --draft
    python -m cutaway make "How a car engine works" --final
    python -m cutaway make <slug> --from compose
    python -m cutaway review <slug>
"""
from __future__ import annotations

import argparse
import logging
import sys

from dotenv import load_dotenv

from config.paths import get_env_path

load_dotenv(get_env_path())

from . import runner  # noqa: E402

log = logging.getLogger("pipeline")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="cutaway", description="Cutaway Studio: 3D cutaway explainers")
    sub = ap.add_subparsers(dest="cmd", required=True)
    mk = sub.add_parser("make", help="topic (or an existing run's slug) -> video")
    mk.add_argument("topic")
    mk.add_argument("--length", type=int, help="target seconds (60-75)")
    q = mk.add_mutually_exclusive_group()
    q.add_argument("--draft", action="store_const", const="draft", dest="quality", help="EEVEE, half res")
    q.add_argument("--final", action="store_const", const="final", dest="quality", help="Cycles OptiX, full res")
    mk.add_argument("--from", dest="start", choices=runner.STAGES, help="re-run from this stage")
    mk.add_argument("--to", dest="stop", choices=runner.STAGES, help="stop after this stage")
    mk.add_argument("--force", action="store_true", help="ignore caches")
    mk.add_argument("--workers", type=int, help="parallel Blender workers (default 2)")
    rv = sub.add_parser("review", help="contact sheet + rubric report for a run")
    rv.add_argument("slug")
    args = ap.parse_args(argv)
    runner.setup_logging()

    if args.cmd == "make":
        slug = runner.existing(args.topic)
        topic = None if slug else args.topic
        slug = slug or runner.new_slug(args.topic)
        if args.length and not 45 <= args.length <= 90:
            ap.error("--length must be between 45 and 90 seconds")
        run = runner.Run(slug, topic=topic, length=args.length, quality=args.quality, workers=args.workers)
        if args.quality and args.quality != run.meta.get("rendered_quality") and not args.start:
            start = "render" if run.load("shotlist.json") else None
        else:
            start = args.start
        timings = runner.run_stages(run, start=start, stop=args.stop, force=args.force)
        log.info("[cutaway] stage times (s): %s", ", ".join(f"{k} {v}" for k, v in timings.items()))
        print(f"\nOutput folder: {run.dir}")
        return 0
    if args.cmd == "review":
        from .stages import qa
        run = runner.Run(args.slug)
        report = qa.review(run)
        print(report["summary"])
        print(f"\nContact sheet: {report['contact_sheet']}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
