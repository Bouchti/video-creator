"""Route shared generation and vision calls through the configured showrunner backend."""

from __future__ import annotations

import shutil
from pathlib import Path


def available() -> bool:
    """Return whether the currently active subscription/API backend can be invoked."""
    from agents import claude_cli
    from agents.showrunner import active_backend

    backend = active_backend()
    if backend == "codex":
        return shutil.which("codex") is not None
    if backend == "subscription":
        return claude_cli.available()
    return False


def ask(system: str, prompt: str, schema: dict | None = None, *, effort: str = "medium",
        web: bool = False, images=(), timeout: int = 1800, model: str | None = None):
    """Run a structured text or image turn using the active backend.

    Text calls use the showrunner dispatcher. Image calls use the same vision dispatcher as
    Blender scene review, so Codex usage-limit fallback is consistent across every pipeline.
    """
    if images:
        from agents.scene_validator import _review_dispatch

        labelled = [(str(label), str(Path(path))) for label, path in images]
        combined = f"ROLE AND RULES:\n{system}\n\nTASK:\n{prompt}"
        return _review_dispatch(combined, labelled, schema)

    from agents import showrunner

    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 6}] if web else None
    return showrunner._call(system, prompt, schema, effort=effort, tools=tools)
