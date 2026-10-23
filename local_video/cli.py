"""Command-line UI for local AI video projects."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import PipelineConfig
from .models import ProjectState
from .project import create_project, load_project, project_status, replan_project, reset_shot, set_control_state
from .queue import QueueBusyError, QueueRunner


def _caption_config(value: str, word_highlight: bool = True) -> dict:
    if value == "off":
        return {"enabled": False, "burn_in": False, "export_srt": False, "word_highlight": False}
    return {
        "enabled": True,
        "burn_in": value in {"burned", "both"},
        "export_srt": value in {"srt", "both"},
        "word_highlight": word_highlight,
        "safe_position": "lower-middle",
    }


def _print_plan(manifest) -> None:
    print(f"Project: {manifest.id}")
    print(f"State: {manifest.state} | {len(manifest.shots)} shots | {manifest.duration_seconds}s | {manifest.preferred_backend}")
    print("Shot  Time       Transition  Action / Camera")
    cursor = 0.0
    for shot in manifest.shots:
        end = cursor + shot.duration_seconds
        action = shot.subject_action.replace("\n", " ")[:70]
        print(f"{shot.index + 1:>3}   {cursor:05.2f}-{end:05.2f}  {shot.transition:<10}  {action} / {shot.camera_action}")
        cursor = end


def _print_status(manifest) -> None:
    value = project_status(manifest)
    print(json.dumps(value, indent=2, ensure_ascii=False))
    if manifest.active_shot:
        shot = next((s for s in manifest.shots if s.id == manifest.active_shot), None)
        if shot:
            print(f"Active: {shot.id} | backend={shot.backend} | attempts={len(shot.attempts)} | error={shot.error or '-'}")


def _progress(value: dict) -> None:
    eta = value["estimated_remaining_seconds"]
    message = (
        f"[{value['state']}] {value['active_shot'] or '-'} | "
        f"{value['completed']}/{value['total']} | backend={value['backend'] or '-'} | "
        f"elapsed={value['elapsed_seconds']:.0f}s | ETA={eta:.0f}s"
    )
    if value.get("error"):
        message += f" | {value['error']}"
    print(message, flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create and control durable local AI-video projects.")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create", help="Generate a script and coherent shot plan")
    create.add_argument("concept")
    create.add_argument("--duration", type=int, default=60, choices=range(60, 91), metavar="60-90")
    create.add_argument("--style", default="cinematic realism, tactile detail, restrained teal and amber grade")
    create.add_argument("--backend", choices=["auto", "minimax", "wan"], default="auto")
    create.add_argument("--narration-file", type=Path)
    create.add_argument("--no-narration", action="store_true")
    create.add_argument("--reference-image", type=Path)
    create.add_argument("--music", default="subtle cinematic")
    create.add_argument("--ambience", default="natural location ambience")
    create.add_argument("--captions", choices=["burned", "srt", "both", "off"], default="both")
    create.add_argument("--no-word-highlight", action="store_true", help="Use phrase captions without per-word highlighting")
    create.add_argument("--voice", default="mysterious")
    create.add_argument("--run", action="store_true", help="Start generation immediately after planning")
    for name in ("run", "resume", "status", "pause", "cancel", "retry"):
        command = sub.add_parser(name)
        command.add_argument("project")
    regenerate = sub.add_parser("regenerate", help="Archive and regenerate one selected shot")
    regenerate.add_argument("project")
    regenerate.add_argument("shot", type=int)
    replan = sub.add_parser("replan", help="Archive old clips and rebuild local prompts from the reviewed script")
    replan.add_argument("project")
    replan.add_argument("--run", action="store_true", help="Start the clean generation immediately")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = PipelineConfig()
    try:
        if args.command == "create":
            narration = None
            enabled = not args.no_narration
            if args.narration_file:
                narration = args.narration_file.read_text(encoding="utf-8")
            manifest = create_project(
                args.concept, args.duration, args.style, args.backend, narration, enabled,
                args.reference_image, args.music, args.ambience,
                _caption_config(args.captions, not args.no_word_highlight),
                args.voice, config,
            )
            _print_plan(manifest)
            print(f"Manifest: {Path(manifest.project_dir) / 'project.json'}")
            if args.run:
                manifest = QueueRunner(config, progress=_progress).run(manifest)
                _print_status(manifest)
            return 0 if manifest.state not in {"failed", "partially_completed"} else 1
        if args.command == "status":
            _print_status(load_project(args.project, config))
            return 0
        if args.command == "pause":
            _print_status(set_control_state(args.project, ProjectState.PAUSED, config))
            return 0
        if args.command == "cancel":
            _print_status(set_control_state(args.project, ProjectState.CANCELLED, config))
            return 0
        if args.command == "regenerate":
            manifest = reset_shot(args.project, args.shot, config)
            manifest = QueueRunner(config, progress=_progress).run(manifest, shots={args.shot})
            _print_status(manifest)
            return 0 if manifest.shots[args.shot - 1].status == "accepted" else 1
        if args.command == "replan":
            manifest = replan_project(args.project, config)
            _print_plan(manifest)
            print(f"Archived prior clips and rebuilt: {Path(manifest.project_dir) / 'project.json'}")
            if args.run:
                manifest = QueueRunner(config, progress=_progress).run(manifest)
                _print_status(manifest)
            return 0 if manifest.state not in {"failed", "partially_completed"} else 1
        manifest = load_project(args.project, config)
        if args.command == "resume":
            manifest.set_state(ProjectState.QUEUED, requested_by="user")
            manifest.save()
        elif args.command == "retry":
            for shot in manifest.shots:
                if shot.status == "failed":
                    shot.status = "pending"
                    shot.error = None
            manifest.set_state(ProjectState.QUEUED, requested_by="user", reason="retry_failed_shots")
            manifest.save()
        manifest = QueueRunner(config, progress=_progress).run(manifest)
        _print_status(manifest)
        return 0 if manifest.state == ProjectState.COMPLETED.value else 1
    except (ValueError, FileNotFoundError, RuntimeError, QueueBusyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
