"""
Sound-event log: animation code records what happens on which frame
(footstep, hammer, scoop, dump, clink, spray, pour, splash, engine on/off ...),
and the audio stage synthesises matching sound effects exactly on those frames.
"""
import json

_events = []


def add(frame: int, kind: str, duration: int = 0, gain: float = 1.0):
    _events.append({"frame": int(frame), "kind": kind, "duration": int(duration), "gain": gain})


def save(path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(_events, key=lambda e: e["frame"]), f)
