"""Inspect or resume durable Unreal projects."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import UnrealConfig
from .project import load_project
from .runner import UnrealPipeline


def status(value: str) -> dict:
    manifest = load_project(value)
    result = {
        "id": manifest.id,
        "state": manifest.state,
        "error": manifest.error,
        "project_dir": manifest.project_dir,
        "outputs": manifest.outputs,
        "last_event": manifest.events[-1] if manifest.events else None,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect and resume Unreal video projects.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "resume"):
        command = sub.add_parser(name)
        command.add_argument("project", help="project directory or project.json")
    args = parser.parse_args()
    if args.command == "status":
        status(args.project)
        return
    manifest = UnrealPipeline(UnrealConfig()).run(Path(args.project))
    print(str(Path(manifest.project_dir) / manifest.outputs["video"]))


if __name__ == "__main__":
    main()
