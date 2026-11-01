"""
Where every part of a storyboard stands and when it is on screen (pure Python, shared by the checker and the
Blender builder). Mounted parts sit in their host-machine slots, props on their stage spots
(buildit/kit/hosts.py); each part's visible time span comes from its appear / remove events.

World: X to the right, Y away from the camera, Z up, floor at z = 0. A box is (x, y, z_base, w, d, h).
"""
from __future__ import annotations

from . import hosts
from .vocab import DIMS, SIZES


def dims(part: dict) -> tuple[float, float, float]:
    k = SIZES.get(part.get("size") or "medium", 1.0)
    w, d, h = DIMS[part["type"]]
    return w * k, d * k, h * k


def solve(sb: dict) -> dict[str, tuple]:
    """{part id: (x, y, z, w, d, h)}."""
    return {pid: (p["x"], p["y"], p["z"], p["w"], p["d"], p["h"]) for pid, p in hosts.solve(sb).items()}


def spans(storyboard: dict, words: list[dict], duration: float) -> dict[str, tuple[float, float]]:
    """{part id (and 'machine'): (t_visible_from, t_visible_until)} from appear / remove events (default: the
    whole video)."""
    t = {p["id"]: [0.0, duration] for p in storyboard["parts"]}
    t["machine"] = [0.0, duration]
    entered = set()
    for e in sorted(storyboard.get("events", []), key=lambda e: e.get("word", 0)):
        pid = str(e.get("target", "")).split(".")[0]
        if pid not in t:
            continue
        w = words[min(max(0, int(e["word"])), len(words) - 1)]["start"]
        if e["do"] == "appear":
            if pid in entered:                      # one life on screen: the first entrance counts
                continue
            entered.add(pid)
            t[pid][0] = max(0.0, w - 0.35)
            src = str(e.get("from") or "")
            if src in t:                            # the prop turns into this part: it leaves as the part flies
                t[src][1] = min(t[src][1], w + 0.3)
        elif e["do"] == "remove":
            t[pid][1] = w + 0.6
    return {k: (a, b) for k, (a, b) in t.items()}


def overlaps(a: tuple, b: tuple, slack: float = 0.01) -> bool:
    ax, ay, az, aw, ad, ah = a
    bx, by, bz, bw, bd, bh = b
    return (abs(ax - bx) * 2 < aw + bw - slack and abs(ay - by) * 2 < ad + bd - slack and
            az < bz + bh - slack and bz < az + ah - slack)
