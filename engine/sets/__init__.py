"""
3D sets for data-driven cutaway films. Each set has a pure-data spec (<set>_spec.py: the
actions it can show + the facts its model depicts) and a Blender builder (<set>.py).
New topics become possible by adding a set; the script writer only ever chooses from these.
"""
import importlib

AVAILABLE = ["pool_story", "plane_story", "nuclear_story", "boat_story", "record_chasing_giant_pumpkin_story", "pumped_storage_mountain_batt_story"]          # sets the showrunner writes for (pool = explainer variant)
EVOLUTION = ["bridge_evolution"]               # problem → solution ladders (agents/evolution_writer.py)


def spec(set_id: str):
    return importlib.import_module(f"engine.sets.{set_id}_spec")
