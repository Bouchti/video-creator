"""Shared path configuration for the video pipeline."""

import os
import sys
import tempfile
from pathlib import Path

# Resolve project root dynamically from this file's location
# (config/ -> parent -> project root)
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)

# Ensure project root is on sys.path so `agents` is importable
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def get_env_path() -> str:
    return os.path.join(PROJECT_ROOT, ".env")


def get_output_dir() -> str:
    d = os.path.join(PROJECT_ROOT, "output")
    os.makedirs(d, exist_ok=True)
    return d


def get_log_file() -> str:
    d = os.path.join(PROJECT_ROOT, "logs")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "pipeline.log")


def get_temp_dir() -> str:
    return tempfile.gettempdir()


def get_comfy_workflow_path() -> str:
    """Default path to the exported ComfyUI API-format workflow JSON."""
    return os.path.join(PROJECT_ROOT, "config", "comfy_workflow_wan.json")


# Shared constants
CLAUDE_MODEL = "claude-sonnet-4-6"
