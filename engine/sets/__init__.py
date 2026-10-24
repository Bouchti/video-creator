"""
3D sets for data-driven cutaway films. Each set has a pure-data spec (<set>_spec.py: the
actions it can show + the facts its model depicts) and a Blender builder (<set>.py).
New topics become possible by adding a set; the script writer only ever chooses from these.
"""
import importlib

AVAILABLE = ["pool_story", "plane_story"]          # sets the showrunner writes for (pool = explainer variant)


def spec(set_id: str):
    return importlib.import_module(f"engine.sets.{set_id}_spec")
