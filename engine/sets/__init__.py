"""
3D sets for data-driven cutaway films. Each set has a pure-data spec (<set>_spec.py: the
actions it can show + the facts its model depicts) and a Blender builder (<set>.py).
New topics become possible by adding a set; the script writer only ever chooses from these.
"""
import importlib
import re

AVAILABLE = ["pool_story", "plane_story", "nuclear_story", "boat_story", "record_chasing_giant_pumpkin_story", "pumped_storage_mountain_batt_story", "levee_story_earthen_river_le_story", "kit_max_s_backyard_levee_story"]          # sets the showrunner writes for (pool = explainer variant)
EVOLUTION = ["bridge_evolution"]               # problem → solution ladders (agents/evolution_writer.py)
EXPLAINER = ["pool"]               # pure cutaway explainers, no hero (agents/explainer.py, --source explainer)


def spec(set_id: str):
    return importlib.import_module(f"engine.sets.{set_id}_spec")


_TOKEN = re.compile(r"[a-z0-9]+")
_FILLER = {"a", "an", "the", "of", "at", "in", "on", "to", "and", "is", "it"}


def _tokens(text) -> set:
    return set(_TOKEN.findall(str(text or "").lower())) - _FILLER


def scene_labels(set_id: str, actions=None) -> list:
    """Token sets of the 3D labels a set's Blender code writes (the text literal of every *label*(...) call):
    the scene already says these words, so a 2D sticker repeating one stacks two texts on the same idea.
    actions: only the labels of those actions' methods (a_<action>) plus those outside any action method."""
    import ast
    import os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{set_id}.py")
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except (OSError, SyntaxError, ValueError):
        return []
    wanted = None if actions is None else {f"a_{a}" for a in actions}
    out = []

    def visit(node, method):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef):
                visit(child, child.name if child.name.startswith("a_") else method)
                continue
            if isinstance(child, ast.Call) and child.args and (wanted is None or method is None or method in wanted):
                fn = child.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                arg = child.args[0]
                if "label" in name.lower() and isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    words = _tokens(arg.value)
                    if words:
                        out.append(words)
            visit(child, method)
    visit(tree, None)
    return out


def repeats_label(overlay: dict, labels: list) -> bool:
    """Does a sticker ({type: stat|label, value, text}) say what an in-scene label already says? ("Rubber gasket"
    over a RUBBER GASKET label, "4 atm" over SEA PRESSURE 4 ATM: the tunnel film showed both, overlapping)."""
    said = _tokens(overlay.get("value") if overlay.get("type") == "stat" else overlay.get("text"))
    return bool(said) and any(said <= lab or lab <= said for lab in labels)
