"""Build-It Studio: the pure logic (no Blender, no network, no model calls)."""
import re

from buildit import compose
from buildit.kit import check, hosts, layout, vocab
from buildit.stages import script as script_stage
from buildit.stages import sound as sound_stage
from buildit.stages.render import shot_frames


def _words(n, step=0.4):
    return [{"text": f"w{i}", "start": round(0.2 + step * i, 3), "end": round(0.5 + step * i, 3)} for i in range(n)]


def test_every_part_has_dims_and_a_builder():
    src = open("buildit/blender/kit.py", encoding="utf-8").read()
    builders = set(re.findall(r"^def b_(\w+)\(", src, re.M))
    assert set(vocab.DIMS) == set(vocab.PARTS) and set(vocab.PARTS) <= builders


def test_every_host_has_a_dressing():
    src = open("buildit/blender/host.py", encoding="utf-8").read()
    for t, (shape, _dims, dressing, _about, _acc) in hosts.HOSTS.items():
        assert shape in hosts.SHAPE_SLOTS
        assert f'"{dressing}"' in src, dressing


SB = {
    "machine": {"host": "fridge"},
    "parts": [{"id": "can", "type": "spray_can", "stage": "front"},
              {"id": "evap", "type": "coil", "mount": "inside_top"},
              {"id": "comp", "type": "compressor", "mount": "back_bottom"}],
    "connections": [{"id": "suction", "kind": "pipe", "from": "evap.out", "to": "comp.in"}],
    "events": [{"word": 1, "do": "appear", "target": "can", "how": "drop"},
               {"word": 2, "do": "flow", "target": "can.nozzle", "kind": "cold_gas", "on": True},
               {"word": 3, "do": "flow", "target": "can.nozzle", "kind": "cold_gas", "on": False},
               {"word": 4, "do": "appear", "target": "machine"},
               {"word": 7, "do": "appear", "target": "evap", "from": "can"},
               {"word": 14, "do": "appear", "target": "comp"},
               {"word": 16, "do": "run", "target": "comp", "speed": "normal"},
               {"word": 18, "do": "flow", "target": "suction", "kind": "cold_gas", "on": True}],
    "shots": [{"start_word": 0, "frame": "prop", "on": ["can"], "move": "push_in"},
              {"start_word": 9, "frame": "part", "on": ["evap"], "move": "hold"},
              {"start_word": 18, "frame": "area", "on": ["comp"], "move": "orbit"}],
    "labels": [{"word": 14, "until_word": 20, "text": "COMPRESSOR", "variant": "neutral", "anchor": "comp.center"}],
    "sfx": [{"word": 25, "cue": "power_up"}],
}


def test_mounted_parts_fit_their_slots():
    place = hosts.solve(SB)
    W, D, H = hosts.HOSTS["fridge"][1]
    ev, comp = place["evap"], place["comp"]
    assert abs(ev["x"]) < 1e-9 and ev["z"] > H * 0.6                    # inside, up in the freezer
    assert comp["y"] > D / 2 and comp["rot"] == 180                     # behind the back wall, facing out
    (cx, cy, cz), (mw, md, mh), _ = hosts.slot_box(SB, "back_bottom")
    assert comp["w"] <= mw + 1e-9 and comp["d"] <= md + 1e-9 and comp["h"] <= mh + 1e-9
    import math
    a = math.radians(hosts.home_azimuth(SB))                            # back parts: filmed from the back-left
    assert hosts.home_azimuth(SB) == -135.0
    can = place["can"]                                                  # the prop stands toward the home camera
    assert can["x"] * math.sin(a) - can["y"] * math.cos(a) > 0.5 * math.hypot(W, D)


def test_a_good_storyboard_passes():
    assert check.check(SB, _words(30), 12.0) == []


def test_storyboard_errors_are_specific():
    bad = {**SB, "parts": SB["parts"] + [{"id": "fan", "type": "fan", "mount": "roof_garden"}],
           "events": SB["events"] + [{"word": 3, "do": "run", "target": "can", "speed": "fast"},
                                     {"word": 99, "do": "flash", "target": "evap.nowhere"}],
           "labels": [{"word": 3, "until_word": 5, "text": "-18 C", "variant": "cold", "anchor": "evap.center"}]}
    errs = check.check(bad, _words(30), 12.0, {"facts": []})
    assert any("no slot 'roof_garden'" in e for e in errs)
    assert any("nothing to run" in e for e in errs)
    assert any("outside" in e for e in errs)
    assert any("no anchor 'nowhere'" in e for e in errs)
    assert any("needs a fact_id" in e for e in errs)


def test_two_parts_in_one_slot_are_moved_by_repair():
    sb = {**SB, "parts": SB["parts"] + [{"id": "comp2", "type": "pump", "mount": "back_bottom"}],
          "events": SB["events"] + [{"word": 16, "do": "appear", "target": "comp2"}]}
    assert any("share the spot" in e for e in check.check(sb, _words(30), 12.0))
    import copy
    sb2 = copy.deepcopy(sb)
    check.repair(sb2, _words(30), 12.0)
    assert check.check(sb2, _words(30), 12.0) == []
    assert {p["mount"] for p in sb2["parts"] if p["id"] in ("comp", "comp2")} != {"back_bottom"}


def test_repair_mounts_connected_parts_and_splits_long_holds():
    import copy
    sb = copy.deepcopy(SB)
    sb["parts"][2]["mount"] = None                       # connected but given no slot
    sb["shots"] = [{"start_word": 0, "frame": "wide", "on": ["can"], "move": "pan"}]
    check.repair(sb, _words(30), 12.0)
    assert sb["parts"][2]["mount"]
    assert all(s["frame"] in vocab.FRAMES and s["move"] in vocab.MOVES for s in sb["shots"])
    assert check.check(sb, _words(30), 12.0) == []


def test_spans_follow_appear_and_fly_out():
    sp = layout.spans(SB, _words(30), 12.0)
    assert sp["evap"][0] > 2.0 and sp["can"][1] < sp["evap"][0] + 1.0   # the can leaves as the coil flies out


def test_sound_cues_follow_the_picture():
    class R:
        def need(self, name):
            return {"storyboard.json": SB, "words.json": {"words": _words(30), "duration": 12.0}}[name]
    cs = sound_stage.cues(R())
    kinds = [c[1] for c in cs]
    assert "clank" in kinds and "whoosh" in kinds and "hiss" in kinds
    spray = [c for c in cs if c[1] == "spray"]
    assert len(spray) == 1 and spray[0][2] <= 0.6                     # only while the can sprays
    assert sum(1 for c in cs if c[1] == "hum") == 1
    hum = next(c for c in cs if c[1] == "hum")
    assert len(hum) == 3 and hum[2] > 3.0                                # the compressor hums while it runs
    land = _words(30)[7]["start"] + sound_stage.LAND                   # the coil clicks into its slot
    assert any(c[1] in ("clank", "clank_small") and abs(c[0] - land) < 1e-6 for c in cs)


def test_caption_groups_keep_small_words_with_the_next():
    words = [{"text": t, "start": i * 0.3, "end": i * 0.3 + 0.25}
             for i, t in enumerate("You grab a bike pump and push, every stroke shoves more air".split())]
    groups = [" ".join(w["text"] for w in g) for g in compose.caption_groups(words)]
    assert "a bike" in groups and all(len(g.split()) <= 3 for g in groups)
    assert sum(len(g.split()) for g in groups) == len(words)


def test_script_check_wants_you_short_sentences_and_a_question():
    beats = [{"id": f"b{i}", "role": r, "narration": n, "fact_ids": [], "label": None}
             for i, (r, n) in enumerate([("hook", "A spray can turns ice cold in seconds.")] +
                                        [("fix", "The machine keeps going and going.")] * 5 +
                                        [("outro", "That is a fridge, and it never stops working all day long.")])]
    errs = script_stage.check({"beats": beats}, {"target_seconds": 12}, {"facts": []})
    assert any("'you'" in e for e in errs)
    assert any("question" in e for e in errs)


def test_shot_frames_tile():
    class R:
        def need(self, name):
            return {"storyboard.json": SB, "words.json": {"words": _words(30), "duration": 12.0}}[name]
    spans = shot_frames(R())
    assert spans[0][1] == 1
    assert all(b[1] == a[2] + 1 for a, b in zip(spans, spans[1:]))
    assert spans[-1][2] == 360


def test_a_part_that_comes_back_gets_its_own_copy():
    import copy
    sb = copy.deepcopy(SB)
    sb["events"] += [{"word": 22, "do": "appear", "target": "can", "how": "pop"},
                     {"word": 24, "do": "flow", "target": "can.nozzle", "kind": "cold_gas", "on": True}]
    fixes = check.repair(sb, _words(30), 12.0)
    assert any("comes back" in f for f in fixes)
    sp = layout.spans(sb, _words(30), 12.0)
    assert sp["can"][0] < 1.0 and sp["can"][1] < sp["can_2"][0]      # first life at the start, then the copy
    assert any(e["target"] == "can_2.nozzle" for e in sb["events"])
