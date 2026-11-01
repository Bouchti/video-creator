"""
    python -m buildit                                   # pick a trending machine topic, make the whole video
    python -m buildit "How a refrigerator works"        # your topic
    python -m buildit make "How a jet engine works" --length 75 --draft
    python -m buildit make <slug> --from compose        # resume
    python -m buildit review <slug>                     # contact sheet vs refs/frames + rubric
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from config.paths import slug as make_slug

from . import runner
from .config import RUNS


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("make", "review"):
        argv = ["make"] + argv
    ap = argparse.ArgumentParser(prog="python -m buildit")
    sub = ap.add_subparsers(dest="cmd", required=True)
    mk = sub.add_parser("make")
    mk.add_argument("topic", nargs="?", help="topic or an existing run slug (omit: pick a trending topic)")
    mk.add_argument("--length", type=int, help="target seconds (60-90, default 75)")
    mk.add_argument("--lang", choices=["en", "fr"], help="narration language (default en)")
    q = mk.add_mutually_exclusive_group()
    q.add_argument("--draft", dest="quality", action="store_const", const="draft", help="fast half-res render")
    q.add_argument("--final", dest="quality", action="store_const", const="final", help="full quality (default)")
    mk.add_argument("--from", dest="start", choices=runner.STAGES)
    mk.add_argument("--to", dest="stop", choices=runner.STAGES)
    mk.add_argument("--force", action="store_true")
    rv = sub.add_parser("review")
    rv.add_argument("slug")
    args = ap.parse_args(argv)
    runner.setup_logging()
    if args.cmd == "review":
        from .stages import qa
        print(json.dumps(qa.review(runner.Run(args.slug)), indent=2))
        return
    if args.length and not 45 <= args.length <= 90:
        ap.error("--length must be between 45 and 90 seconds")
    if args.topic and os.path.isdir(os.path.join(RUNS, args.topic)):
        slug, topic = args.topic, None
    elif args.topic:
        slug, topic = make_slug(args.topic)[:60], args.topic
    else:
        from .stages.topic import pick
        topic = pick()
        slug = make_slug(topic)[:60]
    run = runner.Run(slug, topic=topic, length=args.length, quality=args.quality, lang=args.lang)
    times = runner.run_stages(run, args.start, args.stop, args.force)
    print(json.dumps({"slug": slug, "dir": run.dir, "stage_seconds": times}, indent=2))


if __name__ == "__main__":
    main()
