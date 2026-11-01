"""
Kits: what the planner may film. A kit pairs a Blender assembly with its vocabulary (anchors, cuts, camera
presets, events, the sub-mechanisms it can explain). Pure Python: planning never needs Blender.

A topic the kits cannot film fails at the brief stage with the missing rig named, instead of shipping a weak
video. New topics need a new kit (assembly + vocabulary), not hand edits to a run.
"""
from __future__ import annotations

from . import inline4, pwr

KITS = {"inline4": inline4.KIT, "pwr": pwr.KIT}


def describe() -> str:
    """One paragraph per kit for the brief/planner prompts."""
    lines = []
    for name, kit in KITS.items():
        subs = "; ".join(f"{k}: {v['explains']}" for k, v in kit["mechanisms"].items())
        story = f" Story: {', '.join(kit['story'])}." if kit.get("story") else ""
        lines.append(f"- {name}: {kit['subject']}. Explains: {subs}.{story}")
    return "\n".join(lines)
