"""Fetch the CC0 asset kits and import them into the Unreal project.

    python -m unreal_video.assets            # download (assets/fetch_cc0.py) + import every kit
    python -m unreal_video.assets space-kit  # import only these kits (folder or Unreal names)
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from config.paths import PROJECT_ROOT

from .config import UnrealConfig


def import_kits(kits: list[str] | None = None, config: UnrealConfig | None = None) -> str:
    config = config or UnrealConfig()
    if config.editor is None:
        raise RuntimeError("Unreal Engine 5 was not found; install UE 5.8 or set UNREAL_EDITOR_CMD")
    script = Path(PROJECT_ROOT, "unreal", "VideoCreatorUE", "Content", "Python", "import_cc0.py")
    env = os.environ.copy()
    env["VIDEO_CREATOR_CC0"] = str(Path(PROJECT_ROOT, "assets", "cc0", "kenney"))
    env["VIDEO_CREATOR_KITS"] = ",".join(kits or [])
    command = [str(config.editor), str(config.project), f'-ExecutePythonScript="{script.as_posix()}"',
               "-unattended", "-nop4", "-nosplash", "-NoSound", "-nullrhi", "-stdout"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    lines = [line for line in result.stdout.splitlines() if "VideoCreator CC0" in line or "LogPython: Error" in line]
    summary = "\n".join(re.sub(r"^\[[^]]*\]\[[^]]*\]", "", line) for line in lines)
    if result.returncode != 0 and "import finished" not in summary:
        raise RuntimeError(f"Unreal import failed (exit {result.returncode}):\n{summary or result.stdout[-2000:]}")
    return summary


def main() -> None:
    kits = sys.argv[1:]
    if not kits:
        subprocess.run([sys.executable, str(Path(PROJECT_ROOT, "assets", "fetch_cc0.py"))], check=True)
    print(import_kits(kits))


if __name__ == "__main__":
    main()
