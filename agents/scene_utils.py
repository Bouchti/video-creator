"""Small script/scene helpers shared by maintained editors."""


def get_scenes(script: dict) -> list:
    beats = script.get("beats")
    if isinstance(beats, list) and beats:
        return [
            ((beat.get("visual") or {}).get("description") or beat.get("text") or "").strip()
            for beat in beats if isinstance(beat, dict)
        ]
    scenes = script.get("scenes")
    if isinstance(scenes, list) and scenes:
        return scenes
    return [script[key] for key in sorted(script) if key.startswith("scene_") and script.get(key)]


def scene_prompt(script: dict, index: int) -> str:
    text = get_scenes(script)[index]
    style = (script.get("visual_style") or "").strip()
    return f"{text}, {style}" if style else text
