"""
The HyperFrames CLI, run the way the installed plugin requires (its launcher pins the CLI version):

    node <plugin>/skills/hyperframes/scripts/plugin-cli.mjs <command> <args...>

HYPERFRAMES_LAUNCHER overrides the launcher path; without the plugin, `npx hyperframes` is used.
"""
from __future__ import annotations

import glob
import json
import logging
import os
import shutil
import subprocess

log = logging.getLogger("pipeline")


def launcher() -> list[str]:
    env = os.getenv("HYPERFRAMES_LAUNCHER")
    if env:
        return ["node", env]
    pattern = os.path.join(os.path.expanduser("~"), ".claude", "plugins", "cache", "hyperframes", "hyperframes", "*",
                           "skills", "hyperframes", "scripts", "plugin-cli.mjs")
    found = sorted(glob.glob(pattern), key=lambda p: [int(x) if x.isdigit() else x
                                                      for x in p.split(os.sep)[-5].split(".")])
    if found:
        return ["node", found[-1]]
    return [shutil.which("npx") or "npx", "--yes", "hyperframes"]


def run(args: list[str], cwd: str, timeout: int = 3600, check: bool = True) -> subprocess.CompletedProcess:
    cmd = launcher() + args
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(f"hyperframes {' '.join(args[:2])} failed ({r.returncode}):\n"
                           f"{(r.stdout or '')[-2500:]}\n{(r.stderr or '')[-1500:]}")
    return r


def run_json(args: list[str], cwd: str, timeout: int = 3600) -> dict:
    r = run(args + ["--json"], cwd, timeout, check=False)
    text = r.stdout.strip()
    start = text.find("{")
    if start < 0:
        raise RuntimeError(f"hyperframes {args[0]} gave no JSON:\n{text[-1500:]}\n{r.stderr[-800:]}")
    return json.loads(text[start:])
