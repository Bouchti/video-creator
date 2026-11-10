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
    assert hosts.home_azimuth(SB) == -120.0
    can = place["can"]                                                  # the prop stands toward the home camera
    assert math.hypot(can["x"], can["y"]) > 0.5 * math.hypot(W, D) + 0.3     # clear of the machine
    assert can["x"] * math.sin(a) - can["y"] * math.cos(a) > 0                # on the camera's side


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


def test_caption_groups_are_short_phrases_never_ending_on_a_small_word():
    words = [{"text": t, "start": i * 0.3, "end": i * 0.3 + 0.25}
             for i, t in enumerate("You grab a bike pump and push, every stroke shoves more air".split())]
    groups = [" ".join(w["text"] for w in g) for g in compose.caption_groups(words)]
    assert all(len(g.split()) <= 4 and len(g) <= compose.CAPTION_CHARS for g in groups)
    assert not any(g.split()[-1].lower() in compose.SMALL for g in groups[:-1] if not g.endswith(","))
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
    sb["shots"].append({"start_word": 22, "frame": "prop", "on": ["can"], "move": "push_in"})
    fixes = check.repair(sb, _words(40), 16.2)
    assert any("comes back" in f for f in fixes)
    sp = layout.spans(sb, _words(40), 16.2)
    assert sp["can"][0] < 1.0 and sp["can"][1] < sp["can_2"][0]      # first life at the start, then the copy
    assert any(e["target"] == "can_2.nozzle" for e in sb["events"])


def test_audio_is_measured_not_guessed():
    from buildit import review
    calm = [(0.2, "spray", 2.0), (3.0, "clank"), (8.0, "click"), (10.0, "hum", 30.0), (20.0, "clank")]
    assert review.audio_score(calm, 40.0, {"I": -14.1, "TP": -1.2})["score"] >= review.PASS
    busy = [(i * 0.5, "pop") for i in range(60)] + [(1.0, "spray", 30.0)]
    bad = review.audio_score(busy, 40.0, {"I": -9.0, "TP": 0.0})
    assert bad["score"] < review.PASS and "spray" in bad["why"] and "loudness" in bad["why"]


def test_repair_shows_heat_moving_and_keeps_machine_parts_from_spraying():
    import copy
    sb = copy.deepcopy(SB)
    sb["parts"].append({"id": "cond", "type": "coil", "mount": "back_middle"})
    sb["connections"].append({"id": "hot", "kind": "pipe", "from": "comp.out", "to": "cond.in"})
    sb["events"] += [{"word": 20, "do": "flow", "target": "evap", "kind": "heat", "on": True},
                     {"word": 21, "do": "flow", "target": "cond", "kind": "heat", "on": True},
                     {"word": 22, "do": "flow", "target": "comp", "kind": "hot_gas", "on": True},
                     {"word": 23, "do": "flow", "target": "evap", "kind": "hot_gas", "on": True}]
    check.repair(sb, _words(30), 12.0)
    ev = sb["events"]
    assert {"word": 20, "do": "heat_flow", "target": "machine.food", "to": "evap", "on": True} in ev
    assert any(e["do"] == "heat_flow" and e["target"] == "cond" and e["to"] == "room" for e in ev)
    assert any(e["word"] == 22 and e["target"] == "hot" for e in ev)              # down the pipe, not a jet
    assert any(e["word"] == 23 and e["kind"] == "cold_liquid" and e.get("kind_out") == "cold_gas"
               for e in ev)                                                         # the inside coil: liquid boils to gas
    assert check.check(sb, _words(30), 12.0) == []


def test_props_only_in_their_own_shots():
    import copy
    sb = copy.deepcopy(SB)
    sb["shots"][2]["on"] = ["comp", "can"]
    check.repair(sb, _words(30), 12.0)
    assert all("can" not in s["on"] for s in sb["shots"] if s["frame"] != "prop")
    sb = copy.deepcopy(SB)                                # ... and the shot a part flies out of one in
    sb["events"][4]["word"] = 12
    sb["shots"][1]["start_word"] = 9
    fixes = check.repair(sb, _words(30), 12.0)
    fly = next(s for s in sb["shots"] if "can" in s["on"] and s["frame"] != "prop")
    assert fly["frame"] == "area" and set(fly["on"]) == {"evap", "can"} and any("flying out" in f for f in fixes)


def test_pills_avoid_parts_and_layout_is_measured():
    boxes = {"machine": (200, 400, 880, 1400), "evap": (300, 500, 800, 980)}
    lb = {"text": "EVAPORATOR", "variant": "neutral"}
    pw = compose.pill_width(lb)
    x, y = compose.place_pill(550, 650, pw, boxes)
    assert compose._overlap((x, y, x + pw, y + compose.PILL_H), boxes["evap"]) == 0
    assert 40 <= x and x + pw <= compose.W - 140
    from buildit import review
    shot = {"frame": "part", "on": ["evap"]}
    assert review.layout_faults(1.0, shot, boxes, [], None) == []
    cut = review.layout_faults(1.0, shot, {"evap": (-200, 500, 600, 800)}, [], None)
    assert any("left edge" in f for f in cut)
    small = review.layout_faults(1.0, shot, {"evap": (500, 600, 560, 640)}, [], None)
    assert any("small" in f for f in small)


def test_repair_fills_dead_air_and_never_splits_below_the_minimum_hold():
    import copy
    sb = copy.deepcopy(SB)
    sb["shots"] = [{"start_word": 0, "frame": "prop", "on": ["can"], "move": "push_in"},
                   {"start_word": 10, "frame": "area", "on": ["evap"], "move": "hold"},
                   {"start_word": 19, "frame": "machine", "on": [], "move": "orbit"}]
    sb["events"] = [e for e in sb["events"] if e["word"] < 19]
    fixes = check.repair(sb, _words(40, step=0.45), 18.2)
    assert any("dead air" in f for f in fixes)
    assert any(e["do"] == "highlight" and e["word"] >= 19 for e in sb["events"])
    assert check.check(sb, _words(40, step=0.45), 18.2) == []


def test_preview_keeps_the_best_version():
    from buildit.stages import preview
    def v(*s):
        return {"scores": {f"k{i}": {"score": x} for i, x in enumerate(s)}}
    assert preview._rank(v(4, 4, 4)) > preview._rank(v(3, 5, 5)) and preview._rank(v(4, 3, 4)) > preview._rank(v(3, 3, 4))
    assert preview._rank(v(4, 4, 3)) == preview._rank(v(3, 4, 4))


def test_labels_wait_for_the_camera_to_settle():
    sb = {"shots": [{"start_word": 0}, {"start_word": 10}], "labels": [
        {"word": 11, "until_word": 20, "text": "A"}, {"word": 9, "until_word": 20, "text": "B"},
        {"word": 20, "until_word": 25, "text": "C"}]}
    W = _words(30)
    cut = W[10]["start"] - 0.12
    (a, ta, _), (b, tb, _), (c, tc, _) = compose.label_times(sb, W)
    assert abs(ta - (cut + compose.SETTLE)) < 1e-9 and abs(tb - (cut + compose.SETTLE)) < 1e-9
    assert tc == W[20]["start"]


def test_an_analogy_prop_turns_into_the_next_part():
    import copy
    sb = copy.deepcopy(SB)
    sb["events"][4].pop("from")                                     # the coil no longer comes out of the can
    fixes = check.repair(sb, _words(30), 12.0)
    assert any("flies out of its analogy 'can'" in f for f in fixes)
    assert next(e for e in sb["events"] if e["do"] == "appear" and e["target"] == "evap")["from"] == "can"


def test_the_review_panel_takes_the_median_of_independent_reviews(monkeypatch):
    from buildit import review
    draws = iter([3, 4, 4])

    def fake(run, sheet, caps, extra=""):
        x = next(draws)
        return {"scores": {k: {"score": x, "why": f"{k} {x}"} for k in review.RUBRIC},
                "fixes": [f"fix {x}"], "stills": [{"n": 1, "ok": x > 3, "problem": "p"}],
                "engine_gaps": [], "fix_stage": "storyboard"}
    monkeypatch.setattr(review, "judge", fake)
    v = review.panel(None, "sheet", [], n=3)
    assert all(s["score"] == 4 for s in v["scores"].values())
    assert set(v["fixes"]) == {"fix 3", "fix 4"} and len(v["stills"]) == 1 and v["fix_stage"] == "storyboard"


def test_the_panel_survives_an_empty_review(monkeypatch):
    from buildit import review
    draws = iter([None, 4, 4, 4])

    def fake(run, sheet, caps, extra=""):
        x = next(draws)
        if x is None:
            return None
        return {"scores": {k: {"score": x, "why": ""} for k in review.RUBRIC}, "fixes": [], "stills": [],
                "engine_gaps": [], "fix_stage": "storyboard"}
    monkeypatch.setattr(review, "judge", fake)
    v = review.panel(None, "sheet", [], n=3)
    assert all(s["score"] == 4 for s in v["scores"].values()) and len(v["panel"]) == 3


def test_repair_opens_on_the_hook_and_makes_every_prop_act():
    import copy
    sb = copy.deepcopy(SB)
    sb["shots"][0] = {"start_word": 0, "frame": "machine", "on": [], "move": "hold"}
    fixes = check.repair(sb, _words(30), 12.0, hook="cup")
    assert sb["shots"][0]["frame"] == "prop" and sb["shots"][0]["on"] == ["hook_cup"]
    assert any(e["do"] == "heat_flow" and e["target"] == "hook_cup" for e in sb["events"])     # the cup shows its trick
    assert any("hook object" in f for f in fixes)


def test_the_panel_survives_a_reviewer_that_fails(monkeypatch):
    from buildit import review
    draws = iter(["boom", 4, 4, 4])

    def fake(run, sheet, caps, extra=""):
        x = next(draws)
        if x == "boom":
            raise RuntimeError("claude -p error (error_max_structured_output_retries)")
        return {"scores": {k: {"score": x, "why": ""} for k in review.RUBRIC}, "fixes": [], "stills": [],
                "engine_gaps": [], "fix_stage": "storyboard"}
    monkeypatch.setattr(review, "judge", fake)
    v = review.panel(None, "sheet", [], n=3)
    assert all(s["score"] == 4 for s in v["scores"].values())
