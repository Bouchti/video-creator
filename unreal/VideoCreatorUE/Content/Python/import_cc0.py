"""Executed inside Unreal Editor: import the CC0 Kenney kits (assets/cc0, see assets/fetch_cc0.py)
into /Game/CC0/Kenney/<kit>/ as static meshes with their materials. Already-imported models are
skipped, so it can be re-run after fetching more kits.

    VIDEO_CREATOR_CC0=<repo>/assets/cc0/kenney  [VIDEO_CREATOR_KITS=kit1,kit2]
"""

import os
import re
from pathlib import Path

import unreal

ROOT = Path(os.environ["VIDEO_CREATOR_CC0"])
ONLY = [k for k in (os.getenv("VIDEO_CREATOR_KITS") or "").split(",") if k]


def kit_name(folder):
    """kenney_city-kit-commercial_2.1 -> CityKitCommercial"""
    core = re.sub(r"^kenney_", "", folder)
    core = re.sub(r"_[0-9.]+$", "", core)
    return "".join(part.capitalize() for part in re.split(r"[-_]", core))


tools = unreal.AssetToolsHelpers.get_asset_tools()
done = skipped = failed = 0
for kit in sorted(p for p in ROOT.iterdir() if p.is_dir()):
    if ONLY and kit.name not in ONLY and kit_name(kit.name) not in ONLY:
        continue
    files = sorted(kit.rglob("*.glb"))
    dest = f"/Game/CC0/Kenney/{kit_name(kit.name)}"
    tasks = []
    for f in files:
        name = re.sub(r"[^A-Za-z0-9_]", "_", f.stem)
        if unreal.EditorAssetLibrary.does_directory_exist(f"{dest}/{name}"):   # <kit>/<model>/StaticMeshes
            skipped += 1
            continue
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", str(f))
        task.set_editor_property("destination_path", dest)
        task.set_editor_property("destination_name", name)
        task.set_editor_property("automated", True)
        task.set_editor_property("replace_existing", False)
        task.set_editor_property("save", True)
        tasks.append(task)
    if tasks:
        tools.import_asset_tasks(tasks)
        for task in tasks:
            if task.get_editor_property("imported_object_paths"):
                done += 1
            else:
                failed += 1
    unreal.log(f"VideoCreator CC0: {kit.name} -> {dest}: {len(tasks)} imported, {len(files) - len(tasks)} already there")
unreal.log(f"VideoCreator CC0 import finished: {done} imported, {skipped} skipped, {failed} failed")
