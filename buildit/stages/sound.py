"""
Stage 10 - audio/mix.wav: narration on top, light upbeat music levelled and ducked under it, and sound effects
derived from what the picture does, timed to the frame it happens on (the same timings the Blender builder
uses): a clank as a part clicks into its slot, a whoosh as it flies out of a prop, a click as a pipe appears, a
hum / whirr for as long as a motor runs, a hiss as gas starts to flow, a spray while a jet sprays; plus the
storyboard's own accents. -14 LUFS, -1 dBTP.
"""
from __future__ import annotations

import logging
import os
import shutil

from .. import sound
from ..assets.fetch import music
from ..kit import hosts, layout
from ..runner import StageError

log = logging.getLogger("pipeline")
LOOP_OF = {"pump": "hum", "spin": "whirr", "crank": "hum"}     # a hand pump's strokes make no hum
LAND = 0.2            # a mounted part lands this long after its word (blender/build_scene.py _part_motion)
ACCENTS = {"power_up", "bang", "boil", "bubbles"}      # storyboard sfx code cannot infer from the events
SPRAYERS = {"spray_can", "nozzle"}                     # only these make a spray / hiss jet sound
MIN_GAP = 0.6                                          # seconds between one-shot sounds
PIPE_AFTER = 1.25     # a pipe shows up this long after its later part starts arriving (build_scene._connections)


def inputs(run):
    return [run.path("voice", "narration.wav"), run.path("storyboard.json"), os.path.abspath(sound.__file__),
            os.path.abspath(__file__)]


def cues(run) -> list[tuple]:
    sb, wj = run.need("storyboard.json"), run.need("words.json")
    W, duration = wj["words"], wj["duration"]
    place = hosts.solve(sb)
    span = layout.spans(sb, W, duration)
    parts = {p["id"]: p for p in sb["parts"]}

    def t(i):
        return W[max(0, min(int(i), len(W) - 1))]["start"]
    # the storyboard may add a few accents code cannot infer; everything tied to an event comes from the events
    out: list[tuple] = [(t(x["word"]), x["cue"]) for x in sb.get("sfx", []) if x["cue"] in ACCENTS][:3]
    evs = sorted(sb.get("events", []), key=lambda e: e.get("word", 0))
    runs: dict = {}                                    # part -> [start, end] of its single running loop
    hisses, rattles = 0, []
    for e in evs:
        pid = str(e.get("target", "")).split(".")[0]
        do, tw = e["do"], t(e["word"])
        if do == "appear":
            if pid == "machine":
                out += [(tw - 0.15, "whoosh"), (tw + 0.35, "clank")]
            elif pid in place and place[pid].get("slot"):
                if e.get("from"):
                    out.append((tw - 0.4, "whoosh"))
                small = max(place[pid]["w"], place[pid]["h"]) < 0.25
                out.append((tw + LAND, "clank_small" if small else "clank"))
            else:
                how = e.get("how") or "drop"
                out.append((tw + 0.2, "thud") if how == "drop" else (tw, "pop") if how in ("pop", "grow")
                           else (tw - 0.3, "whoosh"))
        elif do == "remove":
            if (e.get("how") or "") in ("fly_up", "fly_away"):
                out.append((tw, "whoosh"))
        elif do == "run" and pid in parts:
            on = e.get("speed") not in ("stop", None) and e.get("on") is not False
            if on and pid not in runs:
                runs[pid] = [tw, min(span.get(pid, (0, duration))[1], duration)]
            elif not on and pid in runs and runs[pid][1] > tw:
                runs[pid][1] = tw
        elif do == "flow" and e.get("on", True) is not False:
            ptype = parts.get(pid, {}).get("type")
            if "." in str(e.get("target")) and ptype in SPRAYERS and e.get("kind") in ("cold_gas", "air", "steam",
                                                                                      "cold_liquid", "water"):
                off = next((t(x["word"]) for x in evs if x["do"] == "flow" and x.get("target") == e.get("target")
                            and x["word"] > e["word"] and x.get("on") is False), tw + 1.8)
                out.append((tw, "spray" if ptype == "spray_can" else "hiss", min(2.2, max(0.6, off - tw))))
            elif "." not in str(e.get("target")) and e.get("kind") in ("hot_gas", "cold_gas") and hisses < 2:
                hisses += 1                                  # the first gas flows get a soft hiss, not every one
                out.append((tw, "hiss"))
        elif do in ("flash",):
            out.append((tw, "bang"))
        elif do == "spark":
            out.append((tw, "spark"))
        elif do == "shake" and not rattles:                      # one rattle per film is plenty
            rattles.append(tw)
            out.append((tw, "rattle"))
    for pid, (a, b) in runs.items():                    # one loop per running part, as long as it runs
        driver = {"compressor": "pump", "pump": "stroke"}.get(parts[pid]["type"], "spin")
        loop = "turbine" if parts[pid]["type"] == "turbine" else LOOP_OF.get(driver)
        if loop and b - a > 0.4:
            out.append((a, loop, b - a))
    for c in sb.get("connections", []):                 # a pipe connecting: a click when it shows up
        a, b = c["from"].split(".")[0], c["to"].split(".")[0]
        if a in span and b in span:
            ev = next((x for x in evs if x.get("target") == c["id"] and x["do"] == "appear"), None)
            out.append((t(ev["word"]) if ev else max(span[a][0], span[b][0]) + PIPE_AFTER, "click"))
    # sparse: one-shots at least MIN_GAP apart (a part landing always keeps its clank); loops of the same sound
    # never overlap (two hums at once were just noise)
    keep, last, loops = [], -9.0, {}
    for c in sorted(out, key=lambda c: (c[0], c[1] not in ("clank", "clank_small"))):
        if len(c) > 2 and sound.CUES.get(c[1], (0, 0, 0, False))[3]:
            end = loops.get(c[1], -1.0)
            if c[0] < end:
                continue
            loops[c[1]] = c[0] + c[2]
            keep.append(c)
            continue
        if c[0] - last < MIN_GAP and c[1] not in ("clank", "clank_small", "power_up"):
            continue
        last = c[0]
        keep.append(c)
    return keep


def run(run):
    words = run.need("words.json")
    track = music()
    out = run.path("audio", "mix.wav")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cs = cues(run)
    report = sound.mix(run.path("voice", "narration.wav"), words["duration"], track["file"], cs, out)
    run.save("audio/sound.json", {"loudness": report, "music": {k: v for k, v in track.items() if k != "file"},
                                  "cues": [list(c) for c in cs]})
    hf_mix = run.path("hf", "assets", "audio", "mix.wav")
    if os.path.isdir(os.path.dirname(hf_mix)):
        if os.path.exists(hf_mix):
            os.remove(hf_mix)
        shutil.copyfile(out, hf_mix)
    log.info("[sound] %d cues, %s", len(cs), report)


def validate(run):
    s = run.need("audio/sound.json")
    if abs(s["loudness"]["I"] + 14) > 1.0 or s["loudness"]["TP"] > -0.5:
        raise StageError(f"loudness off target: {s['loudness']}")
