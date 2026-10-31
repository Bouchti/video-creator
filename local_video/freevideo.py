"""Start the local FreeVideo (MiniMax H3) ComfyUI on demand, like animated mode starts its ComfyUI."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from pathlib import Path

import requests

from config.paths import get_log_file

from .config import PipelineConfig, env_int, probe_node

log = logging.getLogger("pipeline")

SERVE_SCRIPT = Path(__file__).with_name("freevideo_serve.py")


def freevideo_root() -> Path:
    return Path(os.getenv("FREEVIDEO_DIR") or r"C:\FreeVideo").expanduser()


def engine_python(root: Path) -> Path:
    return root / "envs" / "unified" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def missing_parts(root: Path) -> list[str]:
    """What a headless FreeVideo server still needs (empty when it can be started)."""
    required = {
        "engine setup (machine.json)": root / "machine.json",
        "engine Python": engine_python(root),
        "FreeVideo ComfyUI": root / "ComfyUI" / "main.py",
        "ComfyUI environment (launcher/comfy-host.json)": root / "launcher" / "comfy-host.json",
        "FreeVideo node": root / "ComfyUI" / "custom_nodes" / "FreeVideo" / "__init__.py",
    }
    return [name for name, path in required.items() if not path.exists()]


def ram_cap_gib() -> float | None:
    """FREEVIDEO_RAM_GIB: system RAM FreeVideo may hold (default 14). 0 lets it use all free RAM."""
    value = os.getenv("FREEVIDEO_RAM_GIB", "14").strip()
    try:
        gib = float(value)
    except ValueError:
        log.warning("Ignoring FREEVIDEO_RAM_GIB=%r (not a number)", value)
        return None
    return gib if gib > 0 else None


def apply_ram_cap(root: Path) -> None:
    """Save the RAM cap in FreeVideo's machine.json, which its engine reads before each generation.

    Uncapped, the resident worker pins nearly all free RAM (19 GB of 32 GB measured) and starves
    everything else on the PC. The original file is kept once as machine.json.before-ram-cap.
    """
    path = root / "machine.json"
    try:
        machine = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    cap = ram_cap_gib()
    if machine.get("ram_gib") == cap:
        return
    backup = path.with_name("machine.json.before-ram-cap")
    if not backup.exists():
        backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    machine["ram_gib"] = cap
    staged = path.with_suffix(".json.tmp")
    staged.write_text(json.dumps(machine, indent=2), encoding="utf-8")
    os.replace(staged, path)
    log.info("FreeVideo RAM cap set to %s", f"{cap:g} GiB" if cap else "all free RAM")


def ensure_minimax(config: PipelineConfig) -> tuple[bool, str]:
    """Make sure a FreeVideoGenerate server is reachable, starting FreeVideo if needed.

    Returns (available, url-or-reason) and updates config.minimax_url on success.
    """
    root = freevideo_root()
    if (root / "machine.json").is_file():
        apply_ram_cap(root)
    if config.minimax_url and probe_node(config.minimax_url, "FreeVideoGenerate"):
        return True, config.minimax_url
    missing = missing_parts(root)
    if missing:
        return False, f"FreeVideo is not set up at {root} (missing: {', '.join(missing)}); set FREEVIDEO_DIR"
    port = env_int("FREEVIDEO_PORT", 8190, 1024, 65535)
    url = f"http://127.0.0.1:{port}"
    if not probe_node(url, "FreeVideoGenerate"):
        log_path = Path(get_log_file()).with_name("freevideo.log")
        log.info("Starting FreeVideo (MiniMax H3) from %s on port %s ... (log: %s)", root, port, log_path)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        from .keyframes import models_dir
        command = [str(engine_python(root)), "-B", str(SERVE_SCRIPT), "--root", str(root), "--port", str(port)]
        models = models_dir()
        if models:
            command += ["--models", str(models)]
        with open(log_path, "ab") as out:
            subprocess.Popen(
                command,
                cwd=str(root), stdout=out, stderr=subprocess.STDOUT, creationflags=flags,
            )
        deadline = time.monotonic() + env_int("FREEVIDEO_STARTUP_TIMEOUT", 180, 10, 3600)
        while not probe_node(url, "FreeVideoGenerate"):
            if time.monotonic() > deadline:
                return False, f"FreeVideo did not start on {url} in time (see {log_path})"
            time.sleep(3)
        log.info("FreeVideo is up on %s", url)
    config.minimax_url = url
    return True, url


def recover_server(config: PipelineConfig) -> str:
    """Bring a dead or stuck FreeVideo back. Returns what was done, "" if nothing was needed, or
    "restart failed: ..." when it stays down."""
    if not (config.minimax_url and probe_node(config.minimax_url, "FreeVideoGenerate")):
        # ComfyUI aborted inside FLUX ("Fatal Python error: Aborted") and the process was gone.
        available, detail = ensure_minimax(config)
        return "restarted a dead server" if available else f"restart failed: {detail}"
    return clear_orphaned_jobs(config)


def stop_freevideo_server(port: int) -> None:
    """Kill the ComfyUI server FreeVideo runs on this port (both its launcher and its engine process)."""
    if os.name == "nt":
        command = ["powershell", "-NoProfile", "-Command",
                   "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*ComfyUI*main.py*' "
                   f"-and $_.CommandLine -like '*--port {port}*' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId "
                   "-Force }"]
    else:
        command = ["pkill", "-f", f"ComfyUI/main.py.*--port {port}"]
    subprocess.run(command, capture_output=True, timeout=60)


def clear_orphaned_jobs(config: PipelineConfig, wait_seconds: float = 30.0) -> str:
    """Clear ComfyUI work no run owns; restart a server that cannot be interrupted. Returns what was done.

    Called while this run holds the GPU lock, so any job already queued or running belongs to a run
    that died. A run killed in the middle of a FLUX keyframe left one "running" at 0% GPU, and the next
    run's first keyframe waited out the full 300 s timeout behind it.
    """
    url = config.minimax_url
    try:
        queue = requests.get(f"{url}/queue", timeout=10).json()
        if not (queue.get("queue_running") or queue.get("queue_pending")):
            return ""
        requests.post(f"{url}/queue", json={"clear": True}, timeout=10)
        requests.post(f"{url}/interrupt", json={}, timeout=10)
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            if not requests.get(f"{url}/queue", timeout=10).json().get("queue_running"):
                return "interrupted a job left by an earlier run"
            time.sleep(1)
    except (requests.RequestException, ValueError):
        return ""
    log.warning("ComfyUI is stuck on a job left by an earlier run; restarting FreeVideo")
    stop_freevideo_server(int(url.rsplit(":", 1)[-1]))
    time.sleep(3)
    config.minimax_url = ""
    available, detail = ensure_minimax(config)
    return "restarted a stuck server" if available else f"restart failed: {detail}"
