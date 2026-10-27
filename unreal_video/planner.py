"""Convert an approved full script into a safe, deterministic Unreal scene recipe."""

from __future__ import annotations

import hashlib
import re
from typing import Any

# Order breaks ties: the most specific place wins (a rocket pad beats "tower", a port beats "water").
ARCHETYPES = {
    "space": ("rocket", "launch", "orbit", "space", "satellite", "astronaut", "booster", "spacecraft"),
    "port": ("port", "harbor", "harbour", "cargo", "container", "ship", "freighter", "dock", "crane"),
    "railway": ("train", "rail", "railway", "locomotive", "track", "subway", "freight train"),
    "castle": ("castle", "medieval", "moat", "drawbridge", "fortress", "fort", "rampart"),
    "factory": ("factory", "assembly line", "conveyor", "production line", "manufactur", "plant", "warehouse"),
    "city": ("city", "skyscraper", "urban", "downtown", "traffic light", "elevator", "metropolis"),
    "bridge": ("bridge", "arch", "truss", "span"),
    "water": ("water", "pool", "river", "ocean", "flood", "pipe", "dam", "septic", "well", "reservoir",
              "lake", "hydro"),
    "house": ("house", "home", "basement", "roof", "wall", "foundation", "building"),
    "tower": ("tower", "mast", "wind turbine"),
    "transport": ("car", "truck", "road", "vehicle", "highway"),
    "machine": ("engine", "reactor", "generator", "pump", "turbine", "machine", "motor"),
    "underground": ("underground", "soil", "tunnel", "mine", "buried", "groundwater"),
}

CAMERAS = {"orbit", "dolly_in", "dolly_out", "crane_up", "tracking", "static"}

# What each set can act out on screen (engine side: build_sequence.py). Every set also has the
# camera-only actions: establish (wide opener), detail (close look), finale (payoff pull-back).
COMMON_ACTIONS = ("establish", "detail", "finale")
SET_ACTIONS = {
    "water": ("pump_up", "store", "release_down", "power_out"),
    "machine": ("spin_up", "power_out"),
    "transport": ("traffic",),
    "tower": ("spin_up",),
    "bridge": ("traffic",),
    "house": ("power_out",),
    "underground": ("power_out",),
    "workshop": (),
    "space": ("fuel_up", "launch"),
    "city": ("traffic", "power_out"),
    "port": ("ship_arrive", "unload"),
    "railway": ("train_pass",),
    "castle": ("bridge_lower",),
    "factory": ("conveyor_run", "spin_up", "power_out"),
}
ACTION_HINTS = {   # keyword fallback when no AI planner is available
    "pump_up": ("pump", "uphill", "up to", "lift", "push water", "charge", "cheap", "surplus"),
    "store": ("store", "stored", "hold", "wait", "battery", "reservoir fills", "full"),
    "release_down": ("release", "fall", "falls", "rush", "down through", "drop", "turbine", "flow"),
    "power_out": ("electric", "power", "grid", "light", "megawatt", "homes", "generat", "demand"),
    "spin_up": ("spin", "turn", "rotate", "engine", "motor", "faster"),
    "traffic": ("car", "truck", "traffic", "drive", "cross", "load"),
    "fuel_up": ("fuel", "propellant", "tank", "oxygen", "load"),
    "launch": ("launch", "lift", "liftoff", "thrust", "rise", "climb", "ignit"),
    "ship_arrive": ("arrive", "sail", "dock", "berth", "ship"),
    "unload": ("unload", "lift", "crane", "container", "box"),
    "train_pass": ("train", "rail", "track", "pass", "speed"),
    "bridge_lower": ("drawbridge", "gate", "lower", "open", "enter"),
    "conveyor_run": ("conveyor", "assembly", "line", "move", "product", "box"),
}


ACTION_MEANING = {
    "establish": "wide opening view of the whole place, nothing happening yet",
    "detail": "close look at the main machine or structure",
    "finale": "payoff: everything running at once while the camera pulls back high and wide",
    "pump_up": "glowing water pulses climb the pipe from the lower lake to the upper lake; the wheel turns backwards",
    "store": "the upper lake sits full and calm, water level high, the wheel stopped",
    "release_down": "water rushes down the pipe from the upper lake and spins the turbine wheel fast",
    "power_out": "orange energy pulses run from the powerhouse along a line of pylons to the town",
    "spin_up": "the wheels and windmill sails speed up",
    "traffic": "vehicles drive across",
    "fuel_up": "glowing fuel flows through pipes from the tanks into the rocket on the pad",
    "launch": "the rocket lifts off the pad and climbs on a glowing exhaust plume",
    "ship_arrive": "a big cargo ship sails in and stops at the dock",
    "unload": "the crane lifts containers from the ship onto the dock",
    "train_pass": "a long freight train runs along the track past the station",
    "bridge_lower": "the castle's drawbridge swings down over the moat",
    "conveyor_run": "crates ride the conveyor lines between the factory buildings",
}


# What each set looks like (the topic picker and script writer choose topics a set can film).
SET_SHOWS = {
    "water": "two lakes at different heights on a hill, a big pipe down the slope to a powerhouse with a turbine "
             "wheel, pylons carrying power to a small town (pumped storage, hydro, dams, water supply, siphons)",
    "machine": "a mill on a stream with a turning waterwheel, a windmill, and a power line to houses "
               "(mills, turbines, wind and water power, rotation turned into work or electricity)",
    "bridge": "a stone arch bridge over a river with a cart crossing, houses on both banks (bridges, arches, loads)",
    "house": "a village of houses around a well with a power line coming in (homes, water wells, electricity "
             "reaching houses, village infrastructure)",
    "tower": "a wooden watchtower and a windmill with turning sails (towers, wind, height, lookouts)",
    "transport": "a two-lane road with cars and a truck driving through the countryside (roads, traffic, vehicles)",
    "workshop": "a blacksmith's yard with an anvil, bellows, barrels and tools (forging, tools, craft)",
    "space": "a rocket on a launch pad with fuel tanks, pipes, hangars and a satellite dish (rockets, launches, "
             "spaceflight, fuel, thrust, satellites)",
    "city": "a skyscraper city with streets, cars driving and power lines (cities, traffic, urban infrastructure, "
            "electricity in cities)",
    "port": "a harbour with a cargo ship, a dock crane and stacked containers (shipping, containers, ports, trade)",
    "railway": "a railway line across the countryside with a station and a long freight train (trains, rails, "
               "freight, railway engineering)",
    "castle": "a stone castle with walls, towers, a moat and a drawbridge (castles, medieval engineering, "
              "fortifications, drawbridges)",
    "factory": "an industrial site with buildings, chimneys, tanks, conveyor lines and turning cogs "
               "(factories, manufacturing, assembly lines, industry)",
}


def capability_brief() -> str:
    """The sets and what each can act out: shown to the topic picker and the script writer."""
    lines = []
    for name, shows in SET_SHOWS.items():
        actions = ", ".join(f"{a} ({ACTION_MEANING.get(a, '')})" for a in set_actions(name))
        lines.append(f"- {name}: {shows}.\n    actions: {actions}")
    return "\n".join(lines)


def set_actions(archetype: str) -> tuple[str, ...]:
    return SET_ACTIONS.get(archetype, ()) + COMMON_ACTIONS


def film_archetype(script: dict[str, Any]) -> str:
    """One set for the whole film: every shot is the same place (continuity), chosen from the title
    and all the beats together."""
    beats = script.get("beats") if isinstance(script.get("beats"), list) else []
    text = " ".join([str(script.get("video_title") or "")] * 3 + [
        str((b.get("visual") or {}).get("description") or "") + " " + str(b.get("text") or "")
        for b in beats if isinstance(b, dict)])
    return _archetype(text)


def guess_actions(recipe: dict[str, Any]) -> list[str]:
    """Keyword choice of each shot's action (the AI planner refines it in the runner)."""
    shots = recipe["shots"]
    allowed = set_actions(recipe["world"].get("archetype", "workshop"))
    actions = []
    for index, shot in enumerate(shots):
        text = (shot["narration_reference"] + " " + shot["description"]).lower()
        if index == len(shots) - 1:
            actions.append("finale")
            continue
        if index == 0:
            actions.append("finale")              # cold open: the payoff image first (beat 2 explains)
            continue
        scores = {a: sum(word in text for word in ACTION_HINTS.get(a, ())) for a in allowed}
        best = max(scores, key=lambda a: scores[a]) if scores else "detail"
        actions.append(best if scores.get(best) else ("detail" if index % 2 else "establish"))
    return actions


def _archetype(text: str) -> str:
    value = text.lower()
    scores = {name: sum(word in value for word in words) for name, words in ARCHETYPES.items()}
    name, score = max(scores.items(), key=lambda row: row[1])
    return name if score else "workshop"


def _camera(value: str, index: int) -> str:
    cleaned = re.sub(r"[^a-z_]+", "_", value.lower()).strip("_")
    aliases = {"push_in": "dolly_in", "pull_out": "dolly_out", "pan": "tracking",
               "tilt": "crane_up", "zoom_in": "dolly_in", "zoom_out": "dolly_out"}
    cleaned = aliases.get(cleaned, cleaned)
    return cleaned if cleaned in CAMERAS else ("orbit" if index % 2 else "dolly_in")


def _seed(title: str, index: int) -> int:
    digest = hashlib.sha256(f"{title}:{index}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def _allocate_frames(duration: int, texts: list[str], fps: int) -> list[int]:
    total = int(duration * fps)
    weights = [max(1, len(re.findall(r"\b\w+\b", text))) for text in texts]
    raw = [total * weight / sum(weights) for weight in weights]
    frames = [max(1, int(value)) for value in raw]
    difference = total - sum(frames)
    order = sorted(range(len(frames)), key=lambda index: raw[index] - int(raw[index]), reverse=True)
    step = 1 if difference > 0 else -1
    for offset in range(abs(difference)):
        index = order[offset % len(order)]
        if step > 0 or frames[index] > 1:
            frames[index] += step
    if sum(frames) != total:
        frames[-1] += total - sum(frames)
    return frames


def build_recipe(script: dict[str, Any], duration: int, width: int = 1080,
                 height: int = 1920, fps: int = 30) -> dict[str, Any]:
    beats = script.get("beats") if isinstance(script.get("beats"), list) else []
    if len(beats) < 2:
        raise ValueError("Unreal rendering requires at least two script beats")
    texts = [str(beat.get("text") or "").strip() for beat in beats]
    if any(not text for text in texts):
        raise ValueError("Every Unreal beat needs narration text")
    frames = _allocate_frames(duration, texts, fps)
    title = str(script.get("video_title") or "Untitled Unreal video")
    archetype = script.get("set") if script.get("set") in SET_SHOWS else film_archetype(script)
    shots, cursor = [], 0
    for index, (beat, count) in enumerate(zip(beats, frames)):
        visual = beat.get("visual") if isinstance(beat.get("visual"), dict) else {}
        description = str(visual.get("description") or beat["text"]).strip()
        end = cursor + count
        shots.append({
            "id": f"shot_{index + 1:03d}",
            "index": index,
            "start_frame": cursor,
            "end_frame": end,
            "description": description,
            "narration_reference": str(beat["text"]).strip(),
            "archetype": archetype,
            "camera": _camera(str(visual.get("camera") or ""), index),
            "seed": _seed(title, index),
            "overlay": visual.get("overlay") if isinstance(visual.get("overlay"), dict) else None,
        })
        cursor = end
    recipe = {
        "schema_version": 1,
        "title": title,
        "world": {
            "style": str(script.get("visual_style") or "stylized cinematic engineering diorama"),
            "continuity": "one coherent physical world; recurring materials, scale and lighting",
            "archetype": archetype,
            "palette": ["#18324A", "#E17B3F", "#E8D8B0", "#4D8B67", "#65B8D0"],
        },
        "render": {"width": width, "height": height, "fps": fps, "total_frames": cursor,
                   "audio": False, "captions": False, "transition_sounds": False},
        "shots": shots,
    }
    allowed = set_actions(archetype)
    written = [str((b.get("visual") or {}).get("action") or "") for b in beats]
    if all(a in allowed for a in written):                # the script chose them for its set
        actions = written
        actions[-1] = "finale"
        recipe["world"]["actions_planned_by"] = "script"
    else:
        actions = guess_actions(recipe)
    for shot, action in zip(shots, actions):
        shot["action"] = action
    validate_recipe(recipe)
    return recipe


def retime_recipe(recipe: dict[str, Any], starts_seconds: list[float], lead: float = 0.15) -> dict[str, Any]:
    """Start each shot just before its narration is spoken (starts_seconds: one per shot)."""
    shots, fps = recipe["shots"], int(recipe["render"]["fps"])
    total = int(recipe["render"]["total_frames"])
    if len(starts_seconds) != len(shots):
        return recipe
    cuts = [0] + [max(0, round((t - lead) * fps)) for t in starts_seconds[1:]] + [total]
    for k in range(1, len(cuts) - 1):                  # strictly increasing, at least half a second each
        cuts[k] = max(cuts[k], cuts[k - 1] + fps // 2)
    for k in range(len(cuts) - 2, 0, -1):
        cuts[k] = min(cuts[k], cuts[k + 1] - fps // 2)
    if any(b <= a for a, b in zip(cuts, cuts[1:])):
        return recipe
    for shot, a, b in zip(shots, cuts, cuts[1:]):
        shot["start_frame"], shot["end_frame"] = a, b
    validate_recipe(recipe)
    return recipe


def validate_recipe(recipe: dict[str, Any]) -> None:
    render = recipe.get("render") or {}
    if (render.get("width"), render.get("height"), render.get("fps")) != (1080, 1920, 30):
        raise ValueError("Unreal recipe must be 1080x1920 at 30 fps")
    if any(render.get(name) is not False for name in ("audio", "captions", "transition_sounds")):
        raise ValueError("Unreal must render silent visuals without captions or transition sounds")
    shots = recipe.get("shots")
    if not isinstance(shots, list) or len(shots) < 2:
        raise ValueError("Unreal recipe needs at least two shots")
    cursor = 0
    for shot in shots:
        if shot.get("start_frame") != cursor or int(shot.get("end_frame", 0)) <= cursor:
            raise ValueError("Unreal shot frame ranges must be contiguous and non-empty")
        if shot.get("camera") not in CAMERAS:
            raise ValueError(f"Unsupported Unreal camera move: {shot.get('camera')}")
        if not str(shot.get("description") or "").strip():
            raise ValueError("Every Unreal shot requires a concrete visual description")
        if shot.get("action") is not None and shot["action"] not in set_actions(shot.get("archetype", "")):
            raise ValueError(f"Unsupported Unreal action for the {shot.get('archetype')} set: {shot['action']}")
        cursor = int(shot["end_frame"])
    if cursor != int(render.get("total_frames", -1)):
        raise ValueError("Unreal recipe total_frames does not match its shots")
