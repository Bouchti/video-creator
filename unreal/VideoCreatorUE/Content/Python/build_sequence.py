"""Executed inside Unreal Editor: build a level, sequence and MRQ preset from recipe.json."""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

import unreal


def require_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return Path(value).resolve()


RECIPE_PATH = require_env("VIDEO_CREATOR_RECIPE")
OUTPUT_ROOT = require_env("VIDEO_CREATOR_OUTPUT")
HANDOFF_PATH = require_env("VIDEO_CREATOR_HANDOFF")
RECIPE = json.loads(RECIPE_PATH.read_text(encoding="utf-8"))
FPS = int(RECIPE["render"]["fps"])
TOTAL = int(RECIPE["render"]["total_frames"])
SAFE_ID = re.sub(r"[^A-Za-z0-9_]", "_", OUTPUT_ROOT.name)[:48]
PACKAGE = f"/Game/Generated/{SAFE_ID}"
LEVEL = f"{PACKAGE}/VC_Level"
SEQUENCE = f"{PACKAGE}/VC_Sequence"
PRESET = f"{PACKAGE}/VC_RenderPreset"


def load(path):
    asset = unreal.EditorAssetLibrary.load_asset(path)
    if not asset:
        raise RuntimeError(f"Required Unreal asset is missing: {path}")
    return asset


CUBE = load("/Engine/BasicShapes/Cube.Cube")
SPHERE = load("/Engine/BasicShapes/Sphere.Sphere")
CYLINDER = load("/Engine/BasicShapes/Cylinder.Cylinder")
PLANE = load("/Engine/BasicShapes/Plane.Plane")


def spawn_mesh(name, mesh, location, scale, rotation=(0, 0, 0)):
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.StaticMeshActor, unreal.Vector(*location), unreal.Rotator(rotation[1], rotation[2], rotation[0]))
    actor.set_actor_label(name)
    actor.static_mesh_component.set_static_mesh(mesh)
    actor.set_actor_scale3d(unreal.Vector(*scale))
    actor.static_mesh_component.set_cast_shadow(True)
    return actor


def build_stage(archetype, index):
    x = index * 7000.0
    origin = (x, 0.0, 0.0)
    actors = [spawn_mesh(f"Stage_{index}_Ground", CUBE, (x, 0, -60), (24, 18, 0.6))]
    if archetype == "water":
        actors += [spawn_mesh(f"Stage_{index}_Water", CUBE, (x, 0, 20), (15, 10, 0.25)),
                   spawn_mesh(f"Stage_{index}_Pipe", CYLINDER, (x, 0, 180), (1.2, 1.2, 8), (0, 90, 0)),
                   spawn_mesh(f"Stage_{index}_Tank", CYLINDER, (x + 250, 0, 230), (3, 3, 4))]
    elif archetype == "bridge":
        actors += [spawn_mesh(f"Stage_{index}_Deck", CUBE, (x, 0, 280), (16, 1.4, 0.45)),
                   spawn_mesh(f"Stage_{index}_PierL", CUBE, (x - 850, 0, 110), (1.1, 2, 3.5)),
                   spawn_mesh(f"Stage_{index}_PierR", CUBE, (x + 850, 0, 110), (1.1, 2, 3.5))]
    elif archetype in ("house", "underground"):
        actors += [spawn_mesh(f"Stage_{index}_House", CUBE, (x, 0, 320), (6, 5, 4)),
                   spawn_mesh(f"Stage_{index}_Roof", CUBE, (x, 0, 770), (7, 6, 0.5), (0, 0, 18)),
                   spawn_mesh(f"Stage_{index}_Foundation", CUBE, (x, 0, -280), (7, 6, 2.5)),
                   spawn_mesh(f"Stage_{index}_Drain", CYLINDER, (x, -300, -430), (0.7, 0.7, 8), (90, 0, 0))]
    elif archetype == "tower":
        actors += [spawn_mesh(f"Stage_{index}_Tower", CYLINDER, (x, 0, 700), (3, 3, 14)),
                   spawn_mesh(f"Stage_{index}_Top", SPHERE, (x, 0, 1500), (5, 5, 3))]
    elif archetype == "transport":
        actors += [spawn_mesh(f"Stage_{index}_Body", CUBE, (x, 0, 260), (8, 3, 1.5)),
                   spawn_mesh(f"Stage_{index}_WheelL", CYLINDER, (x - 450, -300, 100), (1.5, 1.5, 0.8), (90, 0, 0)),
                   spawn_mesh(f"Stage_{index}_WheelR", CYLINDER, (x + 450, -300, 100), (1.5, 1.5, 0.8), (90, 0, 0))]
    elif archetype == "machine":
        actors += [spawn_mesh(f"Stage_{index}_Core", CYLINDER, (x, 0, 400), (4, 4, 7)),
                   spawn_mesh(f"Stage_{index}_Rotor", CYLINDER, (x, -450, 420), (3, 3, 1), (90, 0, 0)),
                   spawn_mesh(f"Stage_{index}_Housing", CUBE, (x, 0, 300), (8, 6, 4))]
    else:
        actors += [spawn_mesh(f"Stage_{index}_Bench", CUBE, (x, 0, 220), (9, 4, 0.6)),
                   spawn_mesh(f"Stage_{index}_Build", CUBE, (x, 0, 520), (4, 3, 4)),
                   spawn_mesh(f"Stage_{index}_Detail", SPHERE, (x, -250, 850), (2.5, 2.5, 2.5))]
    return origin, actors


def add_transform_keys(binding, sequence, start, end, loc0, loc1, rot0, rot1):
    track = binding.add_track(unreal.MovieScene3DTransformTrack)
    section = track.add_section()
    section.set_range(start, end)
    channels = section.get_all_channels()
    values0 = (*loc0, *rot0, 1.0, 1.0, 1.0)
    values1 = (*loc1, *rot1, 1.0, 1.0, 1.0)
    for channel, a, b in zip(channels, values0, values1):
        channel.add_key(unreal.FrameNumber(start), float(a))
        channel.add_key(unreal.FrameNumber(max(start + 1, end - 1)), float(b))


unreal.EditorAssetLibrary.make_directory(PACKAGE)
unreal.EditorLevelLibrary.new_level(LEVEL)
world = unreal.EditorLevelLibrary.get_editor_world()
sky = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 1800))
sky.set_actor_rotation(unreal.Rotator(-38, -35, 0), False)
sky.light_component.set_editor_property("intensity", 8.0)
unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 1200))

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
sequence = asset_tools.create_asset("VC_Sequence", PACKAGE, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
sequence.set_display_rate(unreal.FrameRate(FPS, 1))
sequence.set_tick_resolution_directly(unreal.FrameRate(FPS, 1))
sequence.set_playback_start(0)
sequence.set_playback_end(TOTAL)
cut_track = sequence.add_track(unreal.MovieSceneCameraCutTrack)

for shot in RECIPE["shots"]:
    index, start, end = int(shot["index"]), int(shot["start_frame"]), int(shot["end_frame"])
    origin, _ = build_stage(shot["archetype"], index)
    x = origin[0]
    camera = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.CineCameraActor, unreal.Vector(x - 1250, -2100, 1150))
    camera.set_actor_label(f"Camera_{index:03d}")
    target = unreal.Vector(x, 0, 350)
    start_loc = unreal.Vector(x - 1250, -2100, 1150)
    move = shot["camera"]
    if move == "dolly_in":
        end_loc = unreal.Vector(x - 900, -1650, 1000)
    elif move == "dolly_out":
        end_loc = unreal.Vector(x - 1550, -2500, 1250)
    elif move == "crane_up":
        end_loc = unreal.Vector(x - 1250, -2100, 1650)
    elif move == "tracking":
        end_loc = unreal.Vector(x + 500, -2100, 1150)
    elif move == "static":
        end_loc = start_loc
    else:
        end_loc = unreal.Vector(x + 650, -2100, 1200)
    rot0 = unreal.MathLibrary.find_look_at_rotation(start_loc, target)
    rot1 = unreal.MathLibrary.find_look_at_rotation(end_loc, target)
    binding = sequence.add_possessable(camera)
    add_transform_keys(binding, sequence, start, end,
                       (start_loc.x, start_loc.y, start_loc.z), (end_loc.x, end_loc.y, end_loc.z),
                       (rot0.roll, rot0.pitch, rot0.yaw), (rot1.roll, rot1.pitch, rot1.yaw))
    cut = cut_track.add_section()
    cut.set_range(start, end)
    cut.set_camera_binding_id(unreal.MovieSceneObjectBindingID(binding.get_id()))

unreal.EditorLevelLibrary.save_current_level()
unreal.EditorAssetLibrary.save_loaded_asset(sequence)

preset = asset_tools.create_asset("VC_RenderPreset", PACKAGE, unreal.MoviePipelinePrimaryConfig,
                                  unreal.MoviePipelinePrimaryConfigFactory())
output = preset.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
output.output_directory = unreal.DirectoryPath(str(OUTPUT_ROOT / "frames"))
output.output_resolution = unreal.IntPoint(int(RECIPE["render"]["width"]), int(RECIPE["render"]["height"]))
output.file_name_format = "frame_{frame_number_rel}"
output.zero_pad_frame_numbers = 6
output.use_custom_frame_rate = True
output.output_frame_rate = unreal.FrameRate(FPS, 1)
preset.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)
aa = preset.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
aa.spatial_sample_count = 2
aa.temporal_sample_count = 4
unreal.EditorAssetLibrary.save_loaded_asset(preset)

handoff = {
    "map": LEVEL,
    "sequence": f"{SEQUENCE}.{SEQUENCE.rsplit('/', 1)[-1]}",
    "config": f"{PRESET}.{PRESET.rsplit('/', 1)[-1]}",
    "frames": str(OUTPUT_ROOT / "frames"),
}
HANDOFF_PATH.write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")
unreal.log(f"VIDEO_CREATOR_HANDOFF={HANDOFF_PATH}")
