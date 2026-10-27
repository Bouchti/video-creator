"""Executed inside Unreal Editor: build a level, sequence and MRQ preset from recipe.json.

One dressed set per scene archetype (water, bridge, house, tower, transport, machine, workshop),
built from the project's Fab packs (FANTASTIC Village, Megascans, Rural Australia, European Beech,
Vehicle Variety) under a real sky: sun, atmosphere, clouds, height fog. Every shot of an archetype
films the same set from its own angle, so the film reads as one place; wheels and sails turn and
cars drive. Missing packs degrade to basic shapes instead of failing the render.
"""

from __future__ import annotations

import json
import math
import os
import random
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
STAGE_SPACING = 500000.0                      # 5 km apart: each set's 4 km ground never covers another's river

# ------------------------------------------------------------------ assets

FV = "/Game/Fantastic_Village_Pack"
ASSETS = {
    "bridge": f"{FV}/meshes/props/construction/SM_PROP_bridge_stone_01",
    "watchtower": f"{FV}/meshes/props/construction/SM_PROP_watchtower_wood_01",
    "waterwheel": f"{FV}/meshes/buildings/SM_BLD_waterwheel",
    "sail": f"{FV}/meshes/buildings/SM_BLD_windmill_sail",
    "village_tree": f"{FV}/meshes/environment/SM_ENV_TREE_village_LOD0",
    "barrel": f"{FV}/meshes/props/container/SM_PROP_barrel_01",
    "crate": f"{FV}/meshes/props/container/SM_PROP_crate_01",
    "beech": "/Game/EuropeanBeech/Geometry/PivotPainter/SM_EuropeanBeech_Field_01_PP",
    "cliff": "/Game/RuralAustralia/StaticMeshes/Rocks/Cliff_L_01/SM_Cliff_L_01_A",
    "rock": "/Game/RuralAustralia/StaticMeshes/Rocks/Rock_M_01/SM_Rock_M_01",
    "road": "/Game/RuralAustralia/StaticMeshes/Props/Road_01/SM_Road_01",
    "cars": ["/Game/VehicleVarietyPack/Meshes/SM_Hatchback", "/Game/VehicleVarietyPack/Meshes/SM_SUV",
             "/Game/VehicleVarietyPack/Meshes/SM_Pickup", "/Game/VehicleVarietyPack/Meshes/SM_Truck_Box",
             "/Game/VehicleVarietyPack/Meshes/SM_SportsCar"],
    "ground": "/Game/Megascans/Surfaces/MossyGround/MI_MossyGround",
    "water": "/Game/RuralAustralia/Water/MI_Water_01",
}
HOUSES = [f"{FV}/blueprints/buildings/BP_BLD_house_{k}" for k in (1, 3, 5, 7, 9, 11, 13)]
PROPS = {name: f"{FV}/blueprints/props/BP_PROP_{name}" for name in ("well", "cart_01", "rowboat")}
WORKSHOP = ["BlacksmithAnvilA", "OldBellows", "WoodenBarrelA", "OldWoodenTable", "WoodenWheelbarrow",
            "OldWoodenTrough", "WoodenBox"]

_cache = {}


def load(path):
    if path not in _cache:
        _cache[path] = unreal.EditorAssetLibrary.load_asset(path) if path else None
        if not _cache[path]:
            unreal.log_warning(f"VideoCreator: asset missing, using a basic shape instead: {path}")
    return _cache[path]


def bp_class(path):
    key = "bp:" + path
    if key not in _cache:
        _cache[key] = unreal.EditorAssetLibrary.load_blueprint_class(path)
        if not _cache[key]:
            unreal.log_warning(f"VideoCreator: blueprint missing: {path}")
    return _cache[key]


def megascan(name):
    """First static mesh in /Game/Megascans/3D_Assets/<name>."""
    key = "ms:" + name
    if key not in _cache:
        _cache[key] = None
        folder = f"/Game/Megascans/3D_Assets/{name}"
        if unreal.EditorAssetLibrary.does_directory_exist(folder):
            for path in unreal.EditorAssetLibrary.list_assets(folder, recursive=True):
                data = unreal.EditorAssetLibrary.find_asset_data(path)
                if str(data.asset_class_path.asset_name) == "StaticMesh":
                    _cache[key] = data.get_asset()
                    break
    return _cache[key]


CUBE = load("/Engine/BasicShapes/Cube.Cube")
CYLINDER = load("/Engine/BasicShapes/Cylinder.Cylinder")
PLANE = load("/Engine/BasicShapes/Plane.Plane")


def V(x, y, z):
    return unreal.Vector(float(x), float(y), float(z))


def spawn(name, mesh, location, scale=(1, 1, 1), rotation=(0, 0, 0), material=None):
    """rotation = (roll, pitch, yaw) in degrees."""
    mesh = mesh if isinstance(mesh, unreal.StaticMesh) else load(mesh) if isinstance(mesh, str) else mesh
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
        unreal.StaticMeshActor, V(*location), unreal.Rotator(rotation[0], rotation[1], rotation[2]))
    actor.set_actor_label(name)
    component = actor.static_mesh_component
    component.set_static_mesh(mesh or CUBE)
    component.set_mobility(unreal.ComponentMobility.MOVABLE)
    actor.set_actor_scale3d(V(*scale))
    if material:
        component.set_material(0, material)
    return actor


def spawn_sized(name, path, location, height=None, width=None, yaw=0.0, roll=0.0, pitch=0.0):
    """A mesh scaled to a target height or width (cm); falls back to a cube of that size."""
    mesh = load(path) if isinstance(path, str) else path
    if not mesh:
        h = height or width or 300
        return spawn(name, CUBE, (location[0], location[1], location[2] + h / 2), (h / 100,) * 3)
    box = mesh.get_bounding_box()
    size = box.max - box.min
    s = 1.0
    if height:
        s = height / max(size.z, 1.0)
    elif width:
        s = width / max(size.x, size.y, 1.0)
    return spawn(name, mesh, location, (s, s, s), (roll, pitch, yaw))


def spawn_bp(name, path, location, yaw=0.0, scale=1.0):
    cls = bp_class(path)
    if not cls:
        return spawn(name, CUBE, (location[0], location[1], location[2] + 300), (8, 6, 6))
    actor = unreal.EditorLevelLibrary.spawn_actor_from_class(cls, V(*location), unreal.Rotator(0, 0, yaw))
    actor.set_actor_label(name)
    actor.set_actor_scale3d(V(scale, scale, scale))
    return actor


def tiled(parent_path, name, tiles, albedo=None):
    """A material instance of `parent_path` with its texture tiled `tiles` times (big planes)."""
    parent = load(parent_path)
    if not parent:
        return None
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mic = tools.create_asset(name, PACKAGE, unreal.MaterialInstanceConstant,
                             unreal.MaterialInstanceConstantFactoryNew())
    unreal.MaterialEditingLibrary.set_material_instance_parent(mic, parent)
    names = [str(n) for n in unreal.MaterialEditingLibrary.get_scalar_parameter_names(parent)]
    for param in names:
        if param.lower() in ("tilingu", "tilingv", "tiling") or param == "Normals UV Tiling":
            unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(mic, param, float(tiles))
    if albedo is not None and "ALBEDO_Intensity" in names:
        unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(mic, "ALBEDO_Intensity", albedo)
    unreal.MaterialEditingLibrary.update_material_instance(mic)
    unreal.EditorAssetLibrary.save_loaded_asset(mic)
    return mic


# ------------------------------------------------------------------ sky, light, ground

unreal.EditorAssetLibrary.make_directory(PACKAGE)
unreal.EditorLevelLibrary.new_level(LEVEL)


def build_world():
    """Golden-hour diorama light: a low warm sun with long soft shadows, bright sky fill, warm haze,
    and a clean saturated grade (the look of a premium miniature model)."""
    sun = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.DirectionalLight, V(0, 0, 5000))
    sun.set_actor_rotation(unreal.Rotator(0, -24, -52), False)
    light = sun.light_component
    light.set_mobility(unreal.ComponentMobility.MOVABLE)
    light.set_editor_property("intensity", 8.5)
    light.set_editor_property("atmosphere_sun_light", True)
    light.set_editor_property("light_color", unreal.Color(255, 226, 190, 255))
    for prop, value in (("source_angle", 2.5), ("source_soft_angle", 2.0)):
        try:
            light.set_editor_property(prop, value)            # softer shadow edges
        except Exception:                                     # noqa: BLE001
            pass
    unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SkyAtmosphere, V(0, 0, 0))
    sky = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.SkyLight, V(0, 0, 3000))
    sky_light = sky.light_component
    sky_light.set_mobility(unreal.ComponentMobility.MOVABLE)
    sky_light.set_editor_property("real_time_capture", True)
    sky_light.set_editor_property("intensity", 1.35)
    fog = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.ExponentialHeightFog, V(0, 0, -200))
    fog.component.set_editor_property("fog_density", 0.009)            # light haze: depth, not grey
    fog.component.set_editor_property("fog_height_falloff", 0.2)
    try:
        fog.component.set_editor_property("fog_inscattering_luminance", unreal.LinearColor(0.55, 0.62, 0.78, 1))
    except Exception:                                         # noqa: BLE001
        pass
    unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.VolumetricCloud, V(0, 0, 0))
    post = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.PostProcessVolume, V(0, 0, 0))
    post.set_editor_property("unbound", True)
    settings = post.settings
    for prop, value in (("override_auto_exposure_bias", True), ("auto_exposure_bias", 0.25),
                        ("override_vignette_intensity", True), ("vignette_intensity", 0.32),
                        ("override_bloom_intensity", True), ("bloom_intensity", 0.55),
                        ("override_motion_blur_amount", True), ("motion_blur_amount", 0.0),
                        ("override_color_saturation", True), ("color_saturation", unreal.Vector4(1.06, 1.06, 1.06, 1)),
                        ("override_color_contrast", True), ("color_contrast", unreal.Vector4(1.08, 1.08, 1.08, 1)),
                        ("override_scene_color_tint", True), ("scene_color_tint", unreal.LinearColor(1.0, 0.97, 0.92, 1)),
                        ("override_ambient_occlusion_intensity", True), ("ambient_occlusion_intensity", 0.8)):
        try:
            settings.set_editor_property(prop, value)
        except Exception:                                     # noqa: BLE001 (older/newer engine field names)
            pass
    post.set_editor_property("settings", settings)


build_world()
GROUND_SIZE = 400000.0                    # 4 km: the edge is lost in the fog


def ground_material():
    """A soft stylised lawn: two greens blended by large world-space noise (no photo texture, no
    tiling). Built once into /Game/VideoCreator and reused (its shaders stay compiled)."""
    path = "/Game/VideoCreator/M_VC_Meadow"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        return load(path)
    mel = unreal.MaterialEditingLibrary
    unreal.EditorAssetLibrary.make_directory("/Game/VideoCreator")
    mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "M_VC_Meadow", "/Game/VideoCreator", unreal.Material, unreal.MaterialFactoryNew())
    a = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -700, 0)
    a.set_editor_property("constant", unreal.LinearColor(0.085, 0.20, 0.05, 1))      # deep meadow green
    b = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -700, 150)
    b.set_editor_property("constant", unreal.LinearColor(0.30, 0.36, 0.11, 1))       # dry olive patches
    noise = mel.create_material_expression(mat, unreal.MaterialExpressionNoise, -700, 300)
    for prop, value in (("scale", 0.00035), ("levels", 3), ("output_min", 0.0), ("output_max", 1.0)):
        try:
            noise.set_editor_property(prop, value)
        except Exception:                                     # noqa: BLE001
            pass
    mix = mel.create_material_expression(mat, unreal.MaterialExpressionLinearInterpolate, -350, 100)
    mel.connect_material_expressions(a, "", mix, "A")
    mel.connect_material_expressions(b, "", mix, "B")
    mel.connect_material_expressions(noise, "", mix, "Alpha")
    mel.connect_material_property(mix, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rough = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -350, 300)
    rough.set_editor_property("r", 0.85)
    mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)
    return mat


GROUND = ground_material()
BED = tiled(ASSETS["ground"], "MI_VC_Bed", 20, albedo=0.1)   # dark mud: clear water must not show grass
def clean_water():
    """Rural Australia's water without its dirty-water swirls (orange-green streaks on a clean lake)."""
    parent = load(ASSETS["water"])
    if not parent:
        return None
    mic = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "MI_VC_Water", PACKAGE, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mel = unreal.MaterialEditingLibrary
    mel.set_material_instance_parent(mic, parent)
    mel.set_material_instance_vector_parameter_value(mic, "Dirty Water Colour", unreal.LinearColor(0.02, 0.07, 0.08, 1))
    mel.update_material_instance(mic)
    unreal.EditorAssetLibrary.save_loaded_asset(mic)
    return mic


WATER = clean_water()
WATER_DEPTH = 900.0                       # translucent water needs real depth under it, or it reads as grey


def ground_cover(origin, hole=None, clear=2600.0, reach=21000.0, step=3400.0):
    """Photoreal terrain pieces over the flat ground in a ring around the set: natural, non-repeating
    ground near the camera; the centre stays flat for buildings, lakes and rivers stay clear."""
    terrain = megascan("IcelandicTerrain")
    if not terrain:
        return
    x, y = origin[0], origin[1]
    k = 0
    n = int(reach // step)
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            jitter_x, jitter_y = ((i * 7 + j * 13) % 9 - 4) * 180, ((i * 11 + j * 5) % 9 - 4) * 180
            px, py = x + i * step + jitter_x, y + j * step + jitter_y
            r = math.hypot(px - x, py - y)
            if r < clear or r > reach:
                continue
            if hole:
                cx, cy, sx, sy = hole
                if abs(px - cx) < sx / 2 + 1400 and abs(py - cy) < sy / 2 + 1400:
                    continue
            spawn(f"Cover{k}", terrain, (px, py, -170), (2.6, 2.6, 0.9), (0, 0, (i * 97 + j * 61) % 360))
            k += 1


HOLES = {}                                 # set origin -> the lake/river cut into its ground
STF = "/Game/STF/Pack03-LandscapePro/Environment/Foliage"
FOLIAGE = [f"{STF}/GrassBush/SM_grass_bush0{k}_lod00" for k in (1, 2, 3, 4)] +           [f"{STF}/Grass/SM_GrassGroup0{k}" for k in (1, 2, 3)] +           [f"{STF}/Farn/SM_FarnGroup0{k}" for k in (1, 2)] +           [f"{STF}/Grass/SM_FlowerGroup01", f"{STF}/Bush/SM_bush01", f"{STF}/Grass/SM_PlantGroup01"]


def dress(prefix, origin, clear=900.0, reach=9500.0, count=150):
    """Bushes, grass tufts and flowers scattered round the set (never in its water)."""
    hole = HOLES.get(tuple(origin))
    placed = 0
    for k in range(count * 3):
        if placed >= count:
            break
        a = RND.uniform(0, 2 * math.pi)                       # uniform random over the ring (a spiral
        r = math.sqrt(RND.uniform(clear ** 2, reach ** 2))    # pattern drew a visible line)
        px, py = origin[0] + math.cos(a) * r, origin[1] + math.sin(a) * r
        if hole:
            cx, cy, sx, sy = hole
            if abs(px - cx) < sx / 2 + 300 and abs(py - cy) < sy / 2 + 300:
                continue
        model = PLANTS[k % len(PLANTS)]
        lo, hi = kenney_box("NatureKit", model)
        size = 160 + (k * 37) % 220
        scale = size / max(1.0, hi[0] - lo[0], hi[1] - lo[1])
        kenney(f"{prefix}_Plant{placed}", "NatureKit", model, (px, py, 0), scale, yaw=(k * 71) % 360)
        placed += 1


def ground(origin, size=GROUND_SIZE, hole=None):
    """Flat ground; `hole` = (cx, cy, sx, sy) is cut out for a lake or river with a deep bed under it."""
    x, y = origin[0], origin[1]
    HOLES[(origin[0], origin[1], origin[2]) if len(origin) == 3 else tuple(origin)] = hole
    h = size / 2
    if not hole:
        spawn("Ground", PLANE, (x, y, 0), (size / 100, size / 100, 1), material=GROUND)
        return
    cx, cy, sx, sy = hole
    x0, x1, y0, y1 = cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2
    pieces = [(x - h, x0, y - h, y + h), (x1, x + h, y - h, y + h),      # left, right of the hole
              (x0, x1, y - h, y0), (x0, x1, y1, y + h)]                  # in front of, behind it
    for k, (a, b, c, d) in enumerate(pieces):
        if b - a > 1 and d - c > 1:
            spawn(f"Ground_{k}", PLANE, ((a + b) / 2, (c + d) / 2, 0), ((b - a) / 100, (d - c) / 100, 1),
                  material=GROUND)
    spawn("Ground_Bed", PLANE, (cx, cy, -WATER_DEPTH), (sx / 100, sy / 100, 1), material=BED)
    for k, (bx, by, bsx, bsy) in enumerate(((x0, cy, 10, sy), (x1, cy, 10, sy), (cx, y0, sx, 10), (cx, y1, sx, 10))):
        spawn(f"Ground_Bank{k}", CUBE, (bx, by, -WATER_DEPTH / 2), (bsx / 100, bsy / 100, WATER_DEPTH / 100),
              material=BED)


def water(name, center, size_x, size_y, z=-40.0):
    # solid glossy stylised water: the translucent water read as dark ground in the reviews
    return spawn(name, PLANE, (center[0], center[1], z), (size_x / 100, size_y / 100, 1), material=LAKE or WATER)


def backdrop(prefix, origin):
    """Soft rolling hills (flattened domes in the lawn colour) and a ring of stylised trees."""
    for k in range(10):
        a = math.radians(k * 36 + 15)
        r = 30000 + (k * 4700) % 12000
        w = 170 + (k * 37) % 110
        spawn(f"{prefix}_FarHill{k}", SPHERE, (origin[0] + math.cos(a) * r, origin[1] + math.sin(a) * r, -1500),
              (w, w * 0.8, 55 + (k * 13) % 35), (0, 0, k * 47), material=GROUND)
    for k in range(30):
        a = math.radians(k * 12 + 6)
        r = 13000 + (k * 2900) % 6000
        tree(f"{prefix}_RingTree{k}", (origin[0] + math.cos(a) * r, origin[1] + math.sin(a) * r, 0),
             1300 + (k * 211) % 700, k)


RND = random.Random(RECIPE["title"])          # same film, same scatter
TREES = ["tree_default", "tree_oak", "tree_detailed", "tree_fat", "tree_pineRoundB", "tree_pineTallA_detailed",
         "tree_tall", "tree_simple", "tree_pineRoundD", "tree_default_dark"]
ROCKS = ["rock_largeA", "rock_largeC", "rock_largeE", "rock_tallB", "stone_largeB"]
PLANTS = ["plant_bush", "plant_bushLarge", "plant_bushDetailed", "grass_large", "grass_leafsLarge", "flower_yellowA",
          "flower_redB", "flower_purpleC", "plant_flatTall", "grass"]


def tree(name, at, height, k=0):
    """A stylised Kenney tree of the given height (cm)."""
    model = TREES[k % len(TREES)]
    raw = kenney_height("NatureKit", model, 1.0)
    return kenney(name, "NatureKit", model, at, height / max(1.0, raw), yaw=(k * 71) % 360)


def trees(prefix, origin, spots, height=1300.0):
    for k, (dx, dy) in enumerate(spots):
        tree(f"{prefix}_Tree{k}", (origin[0] + dx, origin[1] + dy, 0), height * (0.85 + 0.3 * ((k * 37) % 10) / 10), k)


def rocks(prefix, origin, spots, width=260.0):
    for k, (dx, dy) in enumerate(spots):
        model = ROCKS[k % len(ROCKS)]
        lo, hi = kenney_box("NatureKit", model)
        scale = width / max(1.0, hi[0] - lo[0], hi[1] - lo[1])
        kenney(f"{prefix}_Rock{k}", "NatureKit", model, (origin[0] + dx, origin[1] + dy, 0), scale, yaw=(k * 53) % 360)


# ------------------------------------------------------------------ animation helpers
# Every animated actor gets ONE transform track; its keys are collected shot by shot (what each shot
# acts out comes from recipe["shots"][i]["action"]) and written at the end.

asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
sequence = asset_tools.create_asset("VC_Sequence", PACKAGE, unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
sequence.set_display_rate(unreal.FrameRate(FPS, 1))
sequence.set_tick_resolution_directly(unreal.FrameRate(FPS, 1))
sequence.set_playback_start(0)
sequence.set_playback_end(TOTAL)
LINEAR = unreal.MovieSceneKeyInterpolation.LINEAR
WINDOWS = [(int(s["start_frame"]), int(s["end_frame"]), str(s.get("action") or "detail")) for s in RECIPE["shots"]]
PARK = (0.0, 0.0, -100000.0)                  # where inactive effects wait, far under the ground
TRACKS = {}


def key_transform(actor, keys, start=0, end=TOTAL, linear=False):
    """keys = [(frame, (x,y,z), (roll,pitch,yaw))]: a transform track on the actor."""
    binding = sequence.add_possessable(actor)
    track = binding.add_track(unreal.MovieScene3DTransformTrack)
    section = track.add_section()
    section.set_range(start, end)
    channels = section.get_all_channels()
    scale = actor.get_actor_scale3d().to_tuple()
    for frame, loc, rot in keys:
        values = (*loc, *rot, *scale)
        for channel, value in zip(channels, values):
            if linear:
                channel.add_key(unreal.FrameNumber(int(frame)), float(value), interpolation=LINEAR)
            else:
                channel.add_key(unreal.FrameNumber(int(frame)), float(value))
    return binding


def pose(actor):
    loc, rot = actor.get_actor_location(), actor.get_actor_rotation()
    return (loc.x, loc.y, loc.z), (rot.roll, rot.pitch, rot.yaw)


def add_keys(actor, keys):
    TRACKS.setdefault(actor.get_path_name(), [actor, []])[1].extend(keys)


def flush_tracks():
    for actor, keys in TRACKS.values():
        by_frame = {}
        for frame, loc, rot in keys:
            by_frame[int(frame)] = (loc, rot)
        key_transform(actor, [(f, *by_frame[f]) for f in sorted(by_frame)], linear=True)


def spinner(actor, axis=1, speeds=None, default=20.0):
    """Turn about one local axis (0 roll, 1 pitch, 2 yaw); degrees per second per shot action."""
    speeds = speeds or {}
    loc, rot = pose(actor)
    angle = rot[axis]
    keys = [(0, loc, rot)]
    for start, end, action in WINDOWS:
        angle += speeds.get(action, default) * (end - start) / FPS
        r = list(rot)
        r[axis] = angle
        keys.append((end, loc, tuple(r)))
    add_keys(actor, keys)


def spin(actor, axis, degrees_per_second):
    spinner(actor, axis, default=degrees_per_second)


def level(actor, deltas, low, high):
    """A water surface that rises or falls during the shots whose action moves it."""
    loc, rot = pose(actor)
    z = loc[2]
    keys = [(0, loc, rot)]
    for start, end, action in WINDOWS:
        keys.append((start, (loc[0], loc[1], z), rot))
        z = max(low, min(high, z + deltas.get(action, 0.0)))
        keys.append((end, (loc[0], loc[1], z), rot))
    add_keys(actor, keys)


def drive(actor, x0, x1):
    loc, rot = pose(actor)
    add_keys(actor, [(0, (x0, loc[1], loc[2]), rot), (TOTAL, (x1, loc[1], loc[2]), rot)])


def glow_material(name, rgb, strength):
    """An unlit glowing material (cached in /Game/VideoCreator) for flow and energy pulses."""
    path = f"/Game/VideoCreator/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        return load(path)
    mel = unreal.MaterialEditingLibrary
    unreal.EditorAssetLibrary.make_directory("/Game/VideoCreator")
    mat = asset_tools.create_asset(name, "/Game/VideoCreator", unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    color = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -500, 0)
    color.set_editor_property("constant", unreal.LinearColor(rgb[0] * strength, rgb[1] * strength, rgb[2] * strength, 1))
    mel.connect_material_property(color, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)
    return mat


def flat_material(name, rgb, roughness=0.7):
    """A plain lit colour (concrete, painted steel), cached in /Game/VideoCreator."""
    path = f"/Game/VideoCreator/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        return load(path)
    mel = unreal.MaterialEditingLibrary
    unreal.EditorAssetLibrary.make_directory("/Game/VideoCreator")
    mat = asset_tools.create_asset(name, "/Game/VideoCreator", unreal.Material, unreal.MaterialFactoryNew())
    color = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -500, 0)
    color.set_editor_property("constant", unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1))
    mel.connect_material_property(color, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rough = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -500, 200)
    rough.set_editor_property("r", roughness)
    mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)
    return mat


CONCRETE = flat_material("M_VC_Concrete", (0.42, 0.42, 0.40), 0.85)
STEEL = flat_material("M_VC_Steel", (0.30, 0.33, 0.36), 0.45)
LAKE = flat_material("M_VC_LakeBlue", (0.02, 0.16, 0.26), 0.06)   # solid, glossy: shallow translucent water showed the hill
FLOW_GLOW = glow_material("M_VC_GlowWater2", (0.1, 0.45, 1.0), 3.0)     # bright enough to read, not white
POWER_GLOW = glow_material("M_VC_GlowPower2", (1.0, 0.45, 0.05), 4.0)
SPHERE = load("/Engine/BasicShapes/Sphere.Sphere")
DARK = tiled(ASSETS["ground"], "MI_VC_Dark", 4, albedo=0.05)


def beam(name, a, b, radius, material=None):
    """A cylinder from point a to point b (pipes, poles, wires)."""
    a, b = V(*a), V(*b)
    d = b - a
    length = d.length()
    rot = unreal.MathLibrary.make_rot_from_z(d)
    mid = (a + b) * 0.5
    actor = spawn(name, CYLINDER, (mid.x, mid.y, mid.z), (radius / 50, radius / 50, length / 100), material=material)
    actor.set_actor_rotation(rot, False)
    return actor


def polyline_at(points, lengths, total, u):
    target = u * total
    for k in range(len(points) - 1):
        if target <= lengths[k + 1] or k == len(points) - 2:
            seg = max(1e-3, lengths[k + 1] - lengths[k])
            t = max(0.0, min(1.0, (target - lengths[k]) / seg))
            a, b = points[k], points[k + 1]
            return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))
    return points[-1]


def pulses(name, points, material, active, count=10, size=90.0, mesh=None, scale=None):
    """Glowing pulses that travel along a path while a shot's action is in `active`
    ({action: (direction +1/-1, speed cm/s)}); parked out of sight otherwise."""
    lengths = [0.0]
    for a, b in zip(points, points[1:]):
        lengths.append(lengths[-1] + math.dist(a, b))
    total = lengths[-1]
    rot = (0.0, 0.0, 0.0)
    for k in range(count):
        actor = spawn(f"{name}{k}", mesh or SPHERE, PARK, (scale or size / 100,) * 3, material=material)
        keys = [(0, PARK, rot)]
        for start, end, action in WINDOWS:
            if action not in active:
                keys += [(start, PARK, rot), (end, PARK, rot)]
                continue
            direction, speed = active[action]
            for f in range(start, end + 1, 2):
                u = (k / count + (f - start) * speed / FPS / total) % 1.0
                keys.append((f, polyline_at(points, lengths, total, u if direction > 0 else 1.0 - u), rot))
            keys.append((end + 1, PARK, rot))
        add_keys(actor, keys)


def power_line(prefix, start, end, poles=5, height=1100.0):
    """Pylons with a wire between them; returns the wire's points (for the energy pulses)."""
    tops = []
    for i in range(poles):
        t = i / (poles - 1)
        x, y = start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t
        beam(f"{prefix}_Pole{i}", (x, y, 0), (x, y, height), 22, DARK)
        spawn(f"{prefix}_Arm{i}", CUBE, (x, y, height - 60), (0.25, 2.2, 0.2), material=DARK)
        tops.append((x, y, height - 20))
    for i, (a, b) in enumerate(zip(tops, tops[1:])):
        beam(f"{prefix}_Wire{i}", a, b, 5, DARK)
    return tops


# ------------------------------------------------------------------ the sets
# Each returns a brief: where the camera looks (focus, radius), from which side (facing ± spread,
# height as a fraction of the radius), and named targets for the actions ({name: (point, radius)}).
# Origins are 5 km apart.

def brief(focus, radius, facing, spread, height, **targets):
    return {"focus": focus, "radius": radius, "facing": facing, "spread": spread, "height": height,
            "targets": targets}


def lake_shore(prefix, hole, step=1100.0):
    """Stylised stones along the edges of a lake cut into the ground."""
    cx, cy, sx, sy = hole
    k = 0
    for x0, y0, dx, dy in ((cx - sx / 2, cy - sy / 2, 1, 0), (cx - sx / 2, cy + sy / 2, 1, 0),
                           (cx - sx / 2, cy - sy / 2, 0, 1), (cx + sx / 2, cy - sy / 2, 0, 1)):
        length = sx if dx else sy
        for t in range(int(length // step) + 1):
            rocks(f"{prefix}_Shore{k}", (x0 + dx * t * step, y0 + dy * t * step, 0), [(0, 0)], width=step * 1.1)
            k += 1


def town(prefix, at, count=3):
    for k in range(count):
        spawn_bp(f"{prefix}_TownHouse{k}", HOUSES[(k * 3 + 2) % len(HOUSES)],
                 (at[0] + (k % 2) * 1500 - 700, at[1] + k * 1400 - 1400, 0), yaw=200 + k * 25)


def set_water(o):
    """A lake high on a hill and a lake below, joined by a pipe down the slope to a powerhouse with a
    turbine wheel; a pylon line carries the power to a small town (water storage, hydro, pumping)."""
    x, y = o[0], o[1]
    lake = (x + 5600, y + 500, 7600, 6800)
    ground(o, hole=lake)
    lower = water("Water_Lower", lake[:2], lake[2], lake[3])
    lake_shore("Water", lake)
    # the hill: a smooth grassy dome with rocks round its foot, a round lake set into its top
    hx, hy = x - 6600, y
    dome_r, dome_h = 3400.0, 1500.0
    spawn("Water_Hill", SPHERE, (hx, hy, 0), (dome_r / 50, dome_r / 50, dome_h / 50), material=GROUND)
    spawn("Water_HillB", SPHERE, (hx - 5600, hy + 4200, -300), (130, 110, 40), material=GROUND)
    spawn("Water_HillC", SPHERE, (hx - 4200, hy - 5600, -300), (110, 120, 34), material=GROUND)
    # the lake rests on the dome's top (a disc below the top was covered by the hill: "an empty ring")
    top = dome_h + 12.0
    lake_r = dome_r * 0.32                                 # the dome falls < 1 m inside this: rim rocks hide it
    upper = spawn("Water_Upper", CYLINDER, (hx, hy, top), (lake_r / 50, lake_r / 50, 0.06), material=LAKE)
    for k in range(12):                                   # a rocky rim round the upper lake
        a = math.radians(k * 30)
        rocks(f"Water_Rim{k}", (hx + math.cos(a) * lake_r, hy + math.sin(a) * lake_r, 0), [(0, 0)], width=520)
    for k in range(14):                                   # boulders at the hill's foot
        a = math.radians(k * 26 + 10)
        rocks(f"Water_Foot{k}", (hx + math.cos(a) * dome_r * 0.95, hy + math.sin(a) * dome_r * 0.95, 0), [(0, 0)],
              width=700)
    house_x, house_y = x + 1000, y - 1900
    spawn_bp("Water_Powerhouse", HOUSES[1], (house_x, house_y, 0), yaw=90)
    wheel_at = (house_x + 150, house_y + 950, 450)
    wheel = spawn_sized("Water_Wheel", ASSETS["waterwheel"], wheel_at, height=900, yaw=0)
    p_top, p_bot = (hx + lake_r * 0.9, wheel_at[1], top - 60), (wheel_at[0] - 350, wheel_at[1], 700)
    beam("Water_Pipe", p_top, p_bot, 170, STEEL)
    ride = 230                                                   # the flow beads ride along the pipe's top
    line = power_line("Water_Line", (house_x + 900, house_y - 800), (x + 12500, y - 5200))
    town("Water", (x + 13800, y - 5600))
    trees("Water", o, [(-1500, -4400), (-1200, 4300), (3200, -7600), (10600, -1800), (10800, 5200),
                       (2400, 5400), (6200, 5600), (-9800, -800)], height=1500)
    rocks("Water", o, [(900, 2600), (2600, -900), (-300, -3200)])
    # what each action looks like
    spinner(wheel, 1, {"pump_up": -70, "store": 0, "release_down": 170, "power_out": 120, "finale": 130,
                       "establish": 20, "detail": 35})
    level(upper, {"pump_up": 45, "release_down": -45}, top, top + 90)         # never sinks into the hill
    level(lower, {"pump_up": -35, "release_down": 35}, -110, 30)
    pulses("Water_Flow", [(p_bot[0], p_bot[1], p_bot[2] + ride), (p_top[0], p_top[1], p_top[2] + ride)], FLOW_GLOW,
           {"pump_up": (+1, 900.0), "release_down": (-1, 1700.0), "finale": (-1, 1700.0)}, count=14, size=150)
    pulses("Water_Power", line, POWER_GLOW, {"power_out": (+1, 2600.0), "finale": (+1, 2600.0)}, count=12, size=80)
    mid_pipe = V((p_top[0] + p_bot[0]) / 2, p_top[1], (p_top[2] + p_bot[2]) / 2)
    mid_line = V((line[0][0] + line[-1][0]) / 2, (line[0][1] + line[-1][1]) / 2, 500)
    return brief(V(x - 1200, y - 700, 500), 6200.0, 25.0, 35.0, 0.42,
                 pipe=(mid_pipe, 3300.0), upper=(V(hx, hy, top), 3000.0), line=(mid_line, 4800.0),
                 detail=(V(*wheel_at), 1500.0))


def set_bridge(o):
    x, y = o[0], o[1]
    river = (x, y, 1300, 30000)
    ground(o, hole=river)
    water("Bridge_River", river[:2], river[2], river[3])
    spawn_sized("Bridge_Stone", ASSETS["bridge"], (x, y, -40), width=1700, yaw=90)
    spawn_bp("Bridge_HouseL", HOUSES[0], (x - 2600, y - 1400, 0), yaw=90)
    spawn_bp("Bridge_HouseR", HOUSES[2], (x + 2600, y + 1500, 0), yaw=-90)
    spawn_bp("Bridge_Boat", PROPS["rowboat"], (x, y - 1800, 10), yaw=90)
    cart = spawn_bp("Bridge_Cart", PROPS["cart_01"], (x - 2600, y + 150, 0), yaw=0)
    drive(cart, x - 2600, x + 2600)
    trees("Bridge", o, [(-3200, 2000), (3400, -1800), (-4200, -3600), (4400, 3600), (-2000, 4800)])
    rocks("Bridge", o, [(-800, 900), (800, -1200), (-700, -2600)])
    return brief(V(x, y, 250), 3200.0, -90.0, 45.0, 0.35, detail=(V(x, y, 200), 1600.0))


def set_house(o):
    x, y = o[0], o[1]
    ground(o)
    spots = ((-1500, -700, 30), (1400, -900, -20), (0, 1500, 180), (-2300, 1700, 120), (2500, 1300, 210),
             (-3200, -2200, 60), (3300, -2400, -40))
    for k, (dx, dy, yaw) in enumerate(spots):
        spawn_bp(f"House_{k}", HOUSES[k % len(HOUSES)], (x + dx, y + dy, 0), yaw=yaw)
    spawn_bp("House_Well", PROPS["well"], (x + 100, y - 100, 0))
    spawn_bp("House_Cart", PROPS["cart_01"], (x + 700, y + 500, 0), yaw=40)
    line = power_line("House_Line", (x + 9000, y - 3200), (x + 1400, y - 1600), poles=4)
    pulses("House_Power", line, POWER_GLOW, {"power_out": (+1, 2200.0), "finale": (+1, 2200.0)}, count=9, size=70)
    trees("House", o, [(-4200, -400), (3900, 2900), (4600, -600), (-3900, 3600), (500, -3600), (-600, 3400)])
    mid_line = V((line[0][0] + line[-1][0]) / 2, (line[0][1] + line[-1][1]) / 2, 450)
    return brief(V(x, y, 300), 4200.0, -90.0, 55.0, 0.5, line=(mid_line, 5200.0), detail=(V(x + 100, y - 100, 250), 1900.0))


def set_tower(o):
    x, y = o[0], o[1]
    ground(o)
    spawn_sized("Tower_Watch", ASSETS["watchtower"], (x, y, 0), height=1300)
    spawn_bp("Tower_Mill", HOUSES[3], (x + 2300, y + 600, 0), yaw=-30)
    sail = spawn_sized("Tower_Sail", ASSETS["sail"], (x + 2300, y - 300, 1150), height=1500, yaw=-30)
    spinner(sail, 1, {"spin_up": 90, "finale": 70}, default=25)
    trees("Tower", o, [(-2600, 1800), (2900, -2700), (-3600, -2400), (600, 3800)])
    return brief(V(x + 900, y, 550), 2700.0, -90.0, 45.0, 0.36, detail=(V(x, y, 900), 1700.0))


def set_transport(o):
    x, y = o[0], o[1]
    ground(o)
    for k in range(-3, 3):
        spawn("Road_%d" % k, load(ASSETS["road"]) or CUBE, (x + k * 3500, y, 2))
    for k, path in enumerate(ASSETS["cars"]):
        lane = -220 if k % 2 else 220
        car = spawn_sized(f"Car_{k}", path, (x - 9000 + k * 3600, y + lane, 0), width=430 if k != 3 else 730,
                          yaw=0 if lane < 0 else 180)
        start = x - 9000 + k * 3600 if lane < 0 else x + 9000 - k * 3600
        drive(car, start, start + (11000 if lane < 0 else -11000))
    spawn_bp("Road_House", HOUSES[4], (x - 1200, y + 2600, 0), yaw=180)
    trees("Road", o, [(-3800, -1800), (-1200, -2300), (1800, -2000), (4200, -1700), (2600, 2400), (5200, 2900)])
    return brief(V(x, y, 150), 2600.0, -90.0, 40.0, 0.3, detail=(V(x, y, 120), 1300.0))


def set_machine(o):
    x, y = o[0], o[1]
    stream = (x, y + 600, 30000, 900)
    ground(o, hole=stream)
    water("Machine_Stream", stream[:2], stream[2], stream[3])
    spawn_bp("Machine_Mill", HOUSES[5], (x, y - 900, 0), yaw=0)
    wheel = spawn_sized("Machine_Wheel", ASSETS["waterwheel"], (x + 200, y + 450, 380), height=850, yaw=0)
    sail = spawn_sized("Machine_Sail", ASSETS["sail"], (x - 2400, y - 600, 1250), height=1400, yaw=10)
    spawn_bp("Machine_Tower", HOUSES[6], (x - 2400, y - 1600, 0), yaw=10)
    spinner(wheel, 1, {"spin_up": 160, "power_out": 110, "finale": 140}, default=45)
    spinner(sail, 1, {"spin_up": 110, "power_out": 70, "finale": 90}, default=30)
    for k, (dx, dy) in enumerate(((900, -200), (1150, -350), (1000, 150))):
        spawn_sized(f"Machine_Barrel{k}", ASSETS["barrel"], (x + dx, y + dy, 0), height=110)
    line = power_line("Machine_Line", (x + 1300, y - 1500), (x + 9500, y - 4800), poles=4)
    town("Machine", (x + 10800, y - 5200), count=2)
    pulses("Machine_Power", line, POWER_GLOW, {"power_out": (+1, 2400.0), "finale": (+1, 2400.0)}, count=9, size=70)
    trees("Machine", o, [(-4200, 2600), (3600, -2800), (4200, 2900), (-3500, -3600)])
    mid_line = V((line[0][0] + line[-1][0]) / 2, (line[0][1] + line[-1][1]) / 2, 450)
    return brief(V(x - 600, y, 450), 3000.0, 90.0, 45.0, 0.32, line=(mid_line, 4200.0),
                 detail=(V(x + 200, y + 450, 380), 1400.0))


def set_workshop(o):
    x, y = o[0], o[1]
    ground(o)
    spawn_bp("Workshop_House", HOUSES[2], (x, y + 900, 0), yaw=180)
    for k, (name, dx, dy) in enumerate(zip(WORKSHOP, (-150, 120, 380, -420, 600, -650, 260),
                                           (-120, 60, -260, 180, 120, -300, 320))):
        mesh = megascan(name)
        if mesh:
            spawn_sized(f"Workshop_{name}", mesh, (x + dx, y + dy, 0), width=110 if k else 90, yaw=k * 40)
    trees("Workshop", o, [(-2600, 1500), (2400, 1900), (-1900, -2400)])
    return brief(V(x, y, 110), 900.0, -90.0, 50.0, 0.45, detail=(V(x - 150, y - 120, 80), 450.0))


# ------------------------------------------------------------------ Kenney CC0 kits (python -m unreal_video.assets)

KENNEY = "/Game/CC0/Kenney"
ANCHORS = {}                                   # actor path -> the point it was placed at (footprint centre)
KEEP = unreal.AttachmentRule.KEEP_WORLD


def kenney_meshes(kit, model):
    key = f"kenney:{kit}/{model}"
    if key not in _cache:
        folder = f"{KENNEY}/{kit}/{model}/StaticMeshes"
        meshes = []
        if unreal.EditorAssetLibrary.does_directory_exist(folder):
            for path in sorted(unreal.EditorAssetLibrary.list_assets(folder, recursive=False)):
                asset = unreal.EditorAssetLibrary.load_asset(path)
                if isinstance(asset, unreal.StaticMesh):
                    meshes.append(asset)
        if not meshes:
            unreal.log_warning(f"VideoCreator: Kenney model missing: {kit}/{model}")
        _cache[key] = meshes
    return _cache[key]


def kenney_box(kit, model):
    lo, hi = [1e9] * 3, [-1e9] * 3
    for mesh in kenney_meshes(kit, model):
        b = mesh.get_bounding_box()
        lo = [min(lo[0], b.min.x), min(lo[1], b.min.y), min(lo[2], b.min.z)]
        hi = [max(hi[0], b.max.x), max(hi[1], b.max.y), max(hi[2], b.max.z)]
    return lo, hi


def kenney_height(kit, model, scale):
    lo, hi = kenney_box(kit, model)
    return (hi[2] - lo[2]) * scale


def kenney(name, kit, model, at, scale, yaw=0.0):
    """Place a Kenney model with its footprint centred on `at` and its base on at.z (the kits are
    authored off-centre); multi-part models are attached to their first part, which is returned."""
    meshes = kenney_meshes(kit, model)
    if not meshes:
        return spawn(name, CUBE, (at[0], at[1], at[2] + 100 * scale), (scale * 2,) * 3)
    lo, hi = kenney_box(kit, model)
    cx, cy = (lo[0] + hi[0]) / 2 * scale, (lo[1] + hi[1]) / 2 * scale
    a = math.radians(yaw)
    loc = (at[0] - (cx * math.cos(a) - cy * math.sin(a)), at[1] - (cx * math.sin(a) + cy * math.cos(a)),
           at[2] - lo[2] * scale)
    root = None
    for k, mesh in enumerate(meshes):
        part = spawn(name if k == 0 else f"{name}_part{k}", mesh, loc, (scale,) * 3, (0, 0, yaw))
        if root is None:
            root = part
        else:
            part.attach_to_actor(root, "", KEEP, KEEP, KEEP, False)
    ANCHORS[root.get_path_name()] = tuple(at)
    return root


def attach(child, parent):
    child.attach_to_actor(parent, "", KEEP, KEEP, KEEP, False)


def path_at(points, u):
    lengths = [0.0]
    for a, b in zip(points, points[1:]):
        lengths.append(lengths[-1] + math.dist(a, b))
    return polyline_at(points, lengths, lengths[-1], max(0.0, min(1.0, u)))


def travel(actor, points, acts, rest=0.0):
    """Move an actor along `points` during the shots whose action is in acts ({action: (u0, u1)},
    0..1 along the path); it holds where it ended between them (at `rest` before the first)."""
    loc, rot = pose(actor)
    # the path is where the model's footprint centre goes; its actor origin sits off-centre by this much
    anchor = ANCHORS.get(actor.get_path_name(), loc)
    off = (loc[0] - anchor[0], loc[1] - anchor[1], loc[2] - anchor[2])

    def at(u):
        p = path_at(points, u)
        return (p[0] + off[0], p[1] + off[1], p[2] + off[2])
    u = rest
    keys = [(0, at(u), rot)]
    for start, end, action in WINDOWS:
        if action in acts:
            u0, u1 = acts[action]
            keys += [(start, at(u0), rot), (end, at(u1), rot)]
            u = u1
        else:
            keys += [(start, at(u), rot), (end, at(u), rot)]
    add_keys(actor, keys)


def relative_toggle(actor, offset, active):
    """An attached effect (e.g. exhaust) that sits at `offset` from its parent during `active`
    actions and far below it otherwise (sequencer keys of attached actors are relative)."""
    rot = (0.0, 0.0, 0.0)
    hidden = (offset[0], offset[1], -100000.0)
    keys = []
    for start, end, action in WINDOWS:
        place = offset if action in active else hidden
        keys += [(start, place, rot), (end - 1 if end - 1 > start else end, place, rot)]
    add_keys(actor, keys)


def follow(actor, points, acts, dz):
    """Ride `dz` below a travelling actor during its moving shots (exhaust); parked otherwise."""
    rot = (0.0, 0.0, 0.0)
    keys = [(0, PARK, rot)]
    for start, end, action in WINDOWS:
        if action in acts:
            u0, u1 = acts[action]
            a, b = path_at(points, u0), path_at(points, u1)
            keys += [(start, (a[0], a[1], a[2] + dz), rot), (end - 1, (b[0], b[1], b[2] + dz), rot), (end, PARK, rot)]
        else:
            keys += [(start, PARK, rot), (end, PARK, rot)]
    add_keys(actor, keys)


def pulses_mesh(name, points, mesh, active, count=10, scale=1.0):
    """pulses() with a real mesh (crates on a conveyor) instead of glowing spheres."""
    pulses(name, points, None, active, count=count, mesh=mesh, scale=scale)


# ------------------------------------------------------------------ the sets built from the CC0 kits

def set_space(o):
    """A rocket on its pad: fuel tanks feeding it through pipes, hangars, a dish; it lifts off on a
    glowing plume (rockets, launches, fuel, thrust, satellites)."""
    x, y = o[0], o[1]
    ground(o)
    spawn("Space_Slab", CUBE, (x, y, 45), (58, 58, 0.85), material=CONCRETE)   # just under the pad tiles' tops
    pad_scale = 9.0
    for i in range(-1, 2):
        for j in range(-1, 2):
            kenney(f"Space_Pad{i}{j}", "SpaceKit", "platform_large", (x + i * 1800, y + j * 1800, 0), pad_scale)
    stack_scale = 19.0
    rocket = None
    z = 140.0
    for part in ("rocket_baseA", "rocket_fuelB", "rocket_sidesA", "rocket_topA"):
        piece = kenney(f"Space_Rocket_{part}", "SpaceKit", part, (x, y, z), stack_scale)
        if rocket is None:
            rocket = piece
        else:
            attach(piece, rocket)
        z += kenney_height("SpaceKit", part, stack_scale)
    fins = kenney("Space_Rocket_fins", "SpaceKit", "rocket_finsA", (x, y, 140.0), stack_scale)
    attach(fins, rocket)
    rocket_height = z - 140.0
    flight = [(x, y, 140.0), (x, y, 140.0 + 9000.0), (x + 2500, y, 140.0 + 30000.0)]
    lift = {"launch": (0.0, 0.22), "finale": (0.0, 0.18)}     # climbs ~80 m in a shot: stays in frame
    travel(rocket, flight, lift, rest=0.0)
    for k, (dz, size) in enumerate(((-300, 380), (-900, 460), (-1700, 540))):
        flame = spawn(f"Space_Plume{k}", SPHERE, PARK, (size / 100, size / 100, size / 40), material=POWER_GLOW)
        follow(flame, flight, lift, dz)
    tanks = []
    for k, (dx, dy) in enumerate(((-5200, -2600), (-5200, 0), (-5200, 2600))):
        tanks.append(kenney(f"Space_Tank{k}", "SpaceKit", "machine_barrelLarge", (x + dx * 0.7, y + dy * 0.8, 140), 22.0))
    pipe_path = [(x - 3000, y, 700), (x - 1600, y, 700), (x - 700, y, 1000)]
    beam("Space_Pipe", pipe_path[0], pipe_path[1], 110, STEEL)
    beam("Space_PipeUp", pipe_path[1], pipe_path[2], 110, STEEL)
    pulses("Space_Fuel", [(p[0], p[1], p[2] + 150) for p in pipe_path], FLOW_GLOW,
           {"fuel_up": (+1, 1100.0)}, count=10, size=120)
    kenney("Space_HangarA", "SpaceKit", "hangar_roundA", (x + 6500, y - 4200, 0), 20.0, yaw=-30)
    kenney("Space_HangarB", "SpaceKit", "hangar_largeA", (x + 6800, y + 3800, 0), 20.0, yaw=20)
    kenney("Space_Dish", "SpaceKit", "satelliteDish_large", (x - 3200, y - 6200, 0), 30.0, yaw=40)
    kenney("Space_Gen", "SpaceKit", "machine_generatorLarge", (x - 3400, y + 4800, 0), 26.0)
    trees("Space", o, [(-12000, -8000), (11000, -9000), (-13000, 9000), (12500, 9500)], height=1500)
    return brief(V(x, y, rocket_height * 0.5), 9000.0, -90.0, 40.0, 0.2,
                 pipe=(V(x - 1700, y, 900), 6800.0), launch=(V(x, y, rocket_height * 1.1), 11500.0),
                 detail=(V(x, y, rocket_height * 0.45), 7000.0))


def set_city(o):
    """Skyscrapers along a street grid, cars driving, power lines into the blocks (cities, traffic)."""
    x, y = o[0], o[1]
    ground(o)
    road_scale = 26.0
    tile = 100 * road_scale
    for i in range(-6, 7):
        kenney(f"City_RoadX{i}", "CityKitRoads", "road-straight", (x + i * tile, y, 5), road_scale, yaw=90)
        if i:
            kenney(f"City_RoadY{i}", "CityKitRoads", "road-straight", (x, y + i * tile, 5), road_scale)
    kenney("City_Cross", "CityKitRoads", "road-crossroad", (x, y, 6), road_scale)
    towers = ["building-skyscraper-a", "building-skyscraper-b", "building-skyscraper-c", "building-skyscraper-d",
              "building-skyscraper-e", "building-m", "building-n", "building-l", "building-j", "building-f"]
    k = 0
    for qx in (-1, 1):
        for qy in (-1, 1):
            for i in range(2):
                for j in range(2):
                    bx = x + qx * (tile * 0.95 + i * tile * 0.95)
                    by = y + qy * (tile * 0.95 + j * tile * 0.95)
                    model = towers[(k * 7 + i + j) % len(towers)]
                    kenney(f"City_Tower{k}", "CityKitCommercial", model, (bx, by, 0), 22.0,
                           yaw=0 if qy < 0 else 180)
                    k += 1
    cars = ["sedan", "taxi", "suv", "van", "police", "truck", "delivery", "hatchback-sports"]
    for n, model in enumerate(cars):
        along_x = n % 2 == 0
        lane = 330 if (n // 2) % 2 else -330
        car = kenney(f"City_Car{n}", "CarKit", model, (x, y, 30), 1.9, yaw=90 if along_x else 0)
        if along_x:
            pts = [(x - 15000 + n * 1700, y + lane, 30), (x + 15000 + n * 1700, y + lane, 30)]
        else:
            pts = [(x + lane, y - 15000 + n * 1700, 30), (x + lane, y + 15000 + n * 1700, 30)]
        if lane > 0:
            pts.reverse()
        travel(car, pts, {"traffic": (0.0, 0.5), "finale": (0.45, 0.95), "establish": (0.1, 0.2),
                          "detail": (0.2, 0.3), "power_out": (0.3, 0.4)}, rest=0.0)
    line = power_line("City_Line", (x + 12000, y - 9000), (x + 3600, y - 3000), poles=5, height=1500)
    pulses("City_Power", line, POWER_GLOW, {"power_out": (+1, 2800.0), "finale": (+1, 2800.0)}, count=10, size=90)
    mid_line = V((line[0][0] + line[-1][0]) / 2, (line[0][1] + line[-1][1]) / 2, 700)
    return brief(V(x, y, 2500), 15000.0, -120.0, 40.0, 0.9, line=(V(x + 5200, y - 4200, 900), 12500.0),
                 traffic=(V(x, y, 300), 11500.0), detail=(V(x, y, 1500), 10500.0))


def set_port(o):
    """A harbour: a cargo ship sails in to the dock, a crane lifts containers ashore (shipping, trade)."""
    x, y = o[0], o[1]
    sea = (x, y + 16000, 60000, 28000)
    ground(o, hole=sea)
    water("Port_Sea", sea[:2], sea[2], sea[3])
    spawn("Port_Quay", CUBE, (x, y + 1000, -200), (240, 20, 4.6), material=CONCRETE)    # the quay edge
    cargo = ["cargo-container-a", "cargo-container-b", "cargo-container-c", "cargo-pile-a", "cargo-pile-b"]
    for k in range(14):
        kenney(f"Port_Cargo{k}", "WatercraftPack", cargo[k % len(cargo)],
               (x - 9000 + (k % 7) * 2600, y - 2600 - (k // 7) * 3000, 0), 7.0, yaw=90)
    crane = kenney("Port_Crane", "FactoryKit", "crane", (x - 600, y - 300, 0), 9.0, yaw=0)
    ship = kenney("Port_Ship", "WatercraftPack", "ship-cargo-a", (x, y + 3300, -60), 9.0, yaw=90)
    travel(ship, [(x + 30000, y + 3300, -60), (x, y + 3300, -60)],
           {"ship_arrive": (0.0, 1.0)}, rest=0.0)
    box = kenney("Port_Box", "WatercraftPack", "cargo-container-a", (x, y + 3300, 2600), 7.0, yaw=90)
    travel(box, [(x, y + 3300, 2600), (x, y + 1500, 4600), (x - 400, y - 600, 4600), (x - 400, y - 600, 0)],
           {"unload": (0.0, 1.0), "finale": (0.0, 1.0)}, rest=0.0)
    for k, (dx, dy) in enumerate(((9000, 9000), (-12000, 12000))):
        kenney(f"Port_Tug{k}", "WatercraftPack", "boat-tug-a", (x + dx, y + dy, -60), 9.0, yaw=60 + 50 * k)
    kenney("Port_Buoy", "WatercraftPack", "buoy-flag", (x + 6000, y + 8000, -60), 9.0)
    trees("Port", o, [(-14000, -9000), (12000, -9000), (-6000, -12000)], height=1500)
    return brief(V(x, y + 1200, 900), 9000.0, -70.0, 35.0, 0.35,
                 ship=(V(x + 4000, y + 3300, 700), 10000.0), crane=(V(x - 300, y + 1200, 1800), 5200.0),
                 detail=(V(x - 600, y - 300, 1500), 3800.0))


def set_railway(o):
    """A railway line through the countryside past a station; a long freight train runs along it."""
    x, y = o[0], o[1]
    ground(o)
    scale = 6.0
    tile = 400 * scale
    for i in range(-14, 15):
        kenney(f"Rail_Track{i}", "TrainKit", "railroad-straight", (x + i * tile, y, 5), scale, yaw=90)
    spawn_bp("Rail_Station", HOUSES[4], (x - 800, y - 2300, 0), yaw=0)
    spawn("Rail_Platform", CUBE, (x - 800, y - 1050, 40), (32, 7, 0.8), material=DARK)
    cars = ["train-locomotive-a", "train-carriage-container-red", "train-carriage-tank", "train-carriage-container-blue",
            "train-carriage-lumber", "train-carriage-coal", "train-carriage-container-green"]
    length = 270 * scale + 60
    train = None
    for k, model in enumerate(cars):
        car = kenney(f"Rail_Car{k}", "TrainKit", model, (x - k * length, y, 70), scale, yaw=-90)
        if train is None:
            train = car
        else:
            attach(car, train)
    travel(train, [(x - 30000, y, 70), (x + 34000, y, 70)],
           {"train_pass": (0.25, 0.75), "finale": (0.35, 0.8), "establish": (0.05, 0.12)}, rest=0.05)
    line = power_line("Rail_Line", (x - 18000, y - 1200), (x + 18000, y - 1200), poles=7, height=900)
    trees("Rail", o, [(-6000, 4200), (3000, 5200), (9000, 3600), (-11000, -5200), (12000, -6000), (-2000, -7800)],
          height=1500)
    return brief(V(x, y, 300), 7000.0, -80.0, 45.0, 0.3, train=(V(x, y, 300), 5200.0),
                 detail=(V(x - 800, y - 1500, 300), 3200.0))


def set_castle(o):
    """A stone castle on an island in its moat; the drawbridge swings down over the water."""
    x, y = o[0], o[1]
    moat = (x, y, 9000, 9000)
    ground(o, hole=moat)
    water("Castle_Moat", moat[:2], moat[2], moat[3])
    spawn("Castle_Island", CUBE, (x, y, -WATER_DEPTH / 2), (70, 70, WATER_DEPTH / 100), material=GROUND)
    scale = 9.0
    step = 100 * scale
    half = 3 * step
    for k in range(-3, 4):                       # four walls
        for side, (wx, wy, yaw) in enumerate(((x + k * step, y - half, 0), (x + k * step, y + half, 0),
                                              (x - half, y + k * step, 90), (x + half, y + k * step, 90))):
            if side == 0 and k == 0:
                continue                         # the gate goes here
            kenney(f"Castle_Wall{side}_{k}", "CastleKit", "wall", (wx, wy, 0), scale, yaw=yaw)
    for cx, cy in ((x - half, y - half), (x + half, y - half), (x - half, y + half), (x + half, y + half)):
        z = 0.0
        for part in ("tower-square-base", "tower-square-mid-windows", "tower-square-top-roof-high"):
            kenney(f"Castle_Tower{cx:.0f}_{cy:.0f}_{part}", "CastleKit", part, (cx, cy, z), scale * 1.25)
            z += kenney_height("CastleKit", part, scale * 1.25)
    kenney("Castle_Gate", "CastleKit", "wall-narrow-gate", (x, y - half, 0), scale)
    keep_z = 0.0
    for part in ("tower-square-base", "tower-square-mid-door", "tower-square-mid-windows", "tower-square-roof"):
        kenney(f"Castle_Keep_{part}", "CastleKit", part, (x, y + 600, keep_z), scale * 1.8)
        keep_z += kenney_height("CastleKit", part, scale * 1.8)
    bridge = kenney("Castle_Drawbridge", "CastleKit", "bridge-draw", (x, y - half - 500, 20), scale * 1.1)
    loc, rot = pose(bridge)
    raised = (rot[0], rot[1], rot[2])
    keys = [(0, loc, (raised[0] + 80, raised[1], raised[2]))]
    state = 80.0
    for start, end, action in WINDOWS:
        target = 0.0 if action in ("bridge_lower", "finale") else state
        keys += [(start, loc, (raised[0] + state, raised[1], raised[2])), (end, loc, (raised[0] + target, raised[1], raised[2]))]
        state = target
    add_keys(bridge, keys)
    for k, (dx, dy) in enumerate(((-7000, -6500), (7200, -6000), (-7600, 6200), (7400, 7000))):
        kenney(f"Castle_Tree{k}", "CastleKit", "tree-large", (x + dx, y + dy, 0), 9.0)
    trees("Castle", o, [(-11000, -3000), (11500, 2500), (-3000, -12000), (4000, 12000)], height=1500)
    return brief(V(x, y, 1000), 7600.0, -90.0, 40.0, 0.4, gate=(V(x, y - half, 500), 3400.0),
                 detail=(V(x, y - 600, 1400), 6200.0))


def set_factory(o):
    """An industrial site: buildings, chimneys, tanks, conveyor lines carrying crates, turning cogs."""
    x, y = o[0], o[1]
    ground(o)
    scale = 16.0
    blocks = [("building-a", -4200, 2400, 0), ("building-l", 2600, 2600, 180), ("building-r", -3800, -3600, 0),
              ("building-m", 3600, -3800, 0), ("building-f", 9000, 600, 90)]
    for k, (model, dx, dy, yaw) in enumerate(blocks):
        kenney(f"Factory_Building{k}", "CityKitIndustrial", model, (x + dx, y + dy, 0), scale, yaw=yaw)
    for k, (model, dx, dy) in enumerate((("chimney-large", -6800, 4200), ("chimney-medium", 5600, 4700),
                                         ("detail-tank-large", -800, 5200), ("water-tower", 7600, -6200))):
        kenney(f"Factory_Stack{k}", "CityKitIndustrial", model, (x + dx, y + dy, 0), scale)
    conveyor_scale = 9.0
    for i in range(-5, 6):
        kenney(f"Factory_Conveyor{i}", "FactoryKit", "conveyor-long", (x + i * 200 * conveyor_scale, y - 300, 0),
               conveyor_scale, yaw=90)
    crate = kenney_meshes("FactoryKit", "box-small")
    belt = [(x - 5.5 * 200 * conveyor_scale, y - 300, 420), (x + 5.5 * 200 * conveyor_scale, y - 300, 420)]
    if crate:
        pulses_mesh("Factory_Crate", belt, crate[0], {"conveyor_run": (+1, 600.0), "finale": (+1, 600.0),
                                                       "establish": (+1, 300.0), "detail": (+1, 400.0)},
                    count=12, scale=conveyor_scale)
    cogs = []
    for k, (dx, dy) in enumerate(((-1200, 900), (-150, 900), (850, 900))):
        cog = kenney(f"Factory_Cog{k}", "FactoryKit", "cog-a", (x + dx, y + dy, 30), 10.0)
        spinner(cog, 2, {"spin_up": 160 * (1 if k % 2 else -1), "finale": 140 * (1 if k % 2 else -1),
                         "conveyor_run": 60 * (1 if k % 2 else -1)}, default=20 * (1 if k % 2 else -1))
    line = power_line("Factory_Line", (x + 16000, y - 9000), (x + 4400, y - 2600), poles=5, height=1300)
    pulses("Factory_Power", line, POWER_GLOW, {"power_out": (+1, 2600.0), "finale": (+1, 2600.0)}, count=10, size=85)
    trees("Factory", o, [(-12000, -6000), (11500, 6500), (-9000, 9500), (2000, -11000)], height=1500)
    mid_line = V((line[0][0] + line[-1][0]) / 2, (line[0][1] + line[-1][1]) / 2, 650)
    return brief(V(x, y, 900), 8200.0, -90.0, 40.0, 0.42, conveyor=(V(x, y - 300, 400), 4200.0),
                 cogs=(V(x - 150, y + 900, 200), 2600.0), line=(mid_line, 5500.0),
                 detail=(V(x, y - 300, 400), 3000.0))


SETS = {"space": set_space, "city": set_city, "port": set_port, "railway": set_railway, "castle": set_castle,
        "factory": set_factory, "water": set_water, "bridge": set_bridge, "house": set_house, "underground": set_house,
        "tower": set_tower, "transport": set_transport, "machine": set_machine, "workshop": set_workshop}

# ------------------------------------------------------------------ one set for the film, one camera per shot

kind = RECIPE["world"].get("archetype") or RECIPE["shots"][0]["archetype"]
kind = kind if kind in SETS else "workshop"
ORIGIN = (0.0, 0.0, 0.0)
STAGE = SETS[kind](ORIGIN)
backdrop(kind.capitalize(), ORIGIN)
dress(kind.capitalize(), ORIGIN)
unreal.log(f"VideoCreator: built the {kind} set; actions: {[w[2] for w in WINDOWS]}")
flush_tracks()

cut_track = sequence.add_track(unreal.MovieSceneCameraCutTrack)
PORTRAIT = unreal.CameraFilmbackSettings(sensor_width=18.0, sensor_height=32.0)   # 9:16, no letterbox
ACTION_TARGET = {"pump_up": ("pipe",), "release_down": ("pipe",), "store": ("upper",), "power_out": ("line",),
                 "spin_up": ("cogs", "detail"), "detail": ("detail",), "fuel_up": ("pipe",), "launch": ("launch",),
                 "ship_arrive": ("ship",), "unload": ("crane",), "train_pass": ("train",),
                 "bridge_lower": ("gate",), "conveyor_run": ("conveyor",), "traffic": ("traffic",)}


def camera_pose(focus, radius, angle_deg, dist, height):
    a = math.radians(angle_deg)
    return V(focus.x + math.cos(a) * radius * dist, focus.y + math.sin(a) * radius * dist,
             max(250.0, focus.z + radius * height))


for shot in RECIPE["shots"]:
    index, start, end = int(shot["index"]), int(shot["start_frame"]), int(shot["end_frame"])
    action = str(shot.get("action") or "detail")
    focus, radius = STAGE["focus"], STAGE["radius"]
    target = next((STAGE["targets"][t] for t in ACTION_TARGET.get(action, ()) if t in STAGE["targets"]), None)
    if target:                                            # frame the part this shot is about
        focus, radius = target
    facing, spread, height = STAGE["facing"], STAGE["spread"], STAGE["height"]
    angle = facing - spread + (index * 67) % (2 * spread)  # the camera stays on the set's open side
    dist0, dist1, h0, h1, a1 = 0.95, 0.95, height, height, angle
    move = shot["camera"]
    if move == "dolly_in":
        dist1 = 0.72
    elif move == "dolly_out":
        dist0, dist1 = 0.72, 0.95
    elif move == "crane_up":
        h0, h1 = height * 0.6, height * 1.4
    elif move == "tracking":
        a1 = angle + 14
    elif move == "orbit":
        a1 = angle + 22
    if action == "establish":                             # the opener shows the whole place from high up
        angle, a1 = facing - 8, facing + 6
        dist0, dist1, h0, h1 = 1.45, 1.3, height * 1.9, height * 1.7
    elif action == "finale":                              # the payoff: everything running, pull back high
        angle, a1 = facing - 10, facing + 12
        dist0, dist1, h0, h1 = 0.75, 1.55, height * 0.9, height * 1.6
    loc0 = camera_pose(focus, radius, angle, dist0, h0)
    loc1 = camera_pose(focus, radius, a1, dist1, h1)
    camera = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.CineCameraActor, loc0)
    camera.set_actor_label(f"Camera_{index:03d}")
    component = camera.get_cine_camera_component()
    component.set_editor_property("filmback", PORTRAIT)
    component.set_editor_property("current_focal_length", 22.0)
    # tilt-shift: sharp on the subject, the foreground and background soften (the miniature look)
    focus_settings = component.get_editor_property("focus_settings")
    focus_settings.set_editor_property("focus_method", unreal.CameraFocusMethod.MANUAL)
    focus_settings.set_editor_property("manual_focus_distance", float((loc0 - focus).length() + (loc1 - focus).length()) / 2)
    component.set_editor_property("focus_settings", focus_settings)
    lens = component.get_editor_property("lens_settings")
    lens.set_editor_property("min_f_stop", 0.1)
    component.set_editor_property("lens_settings", lens)
    component.set_editor_property("current_aperture", 0.7 if action in ("detail", "establish", "finale") else 1.0)
    rot0 = unreal.MathLibrary.find_look_at_rotation(loc0, focus)
    rot1 = unreal.MathLibrary.find_look_at_rotation(loc1, focus)
    binding = key_transform(camera, [(start, (loc0.x, loc0.y, loc0.z), (rot0.roll, rot0.pitch, rot0.yaw)),
                                     (max(start + 1, end - 1), (loc1.x, loc1.y, loc1.z),
                                      (rot1.roll, rot1.pitch, rot1.yaw))], start=start, end=end)
    cut = cut_track.add_section()
    cut.set_range(start, end)
    cut.set_camera_binding_id(sequence.get_binding_id(binding))

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
preset.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)   # the lit image ("0 Passes" without it)
preset.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)
aa = preset.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
# The sequence ticks at FPS (keys are whole frames), so a frame can't be split into temporal
# samples ("Too many temporal samples"): all the anti-aliasing comes from spatial samples.
aa.spatial_sample_count = 8
aa.temporal_sample_count = 1
# Warm-up frames so Lumen, clouds and auto exposure settle before the first saved frame.
aa.engine_warm_up_count = 32
aa.render_warm_up_count = 32
unreal.EditorAssetLibrary.save_loaded_asset(preset)

handoff = {
    "map": LEVEL,
    "sequence": f"{SEQUENCE}.{SEQUENCE.rsplit('/', 1)[-1]}",
    "config": f"{PRESET}.{PRESET.rsplit('/', 1)[-1]}",
    "frames": str(OUTPUT_ROOT / "frames"),
}
HANDOFF_PATH.write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")
unreal.log(f"VIDEO_CREATOR_HANDOFF={HANDOFF_PATH}")
