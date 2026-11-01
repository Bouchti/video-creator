"""Cutaway Studio: the pure logic (no Blender, no network, no model calls)."""
import math

import pytest

from cutaway import kits
from cutaway.blender.rigs import crank as K
from cutaway.stages import align, compose, package, research, script, shotlist
from cutaway.stages.render import frames_of

KIT = kits.KITS["inline4"]


# ------------------------------------------------------------ mechanism math

def test_piston_tdc_bdc():
    e = K.Inline4()
    assert K.piston_pin_z(0, e.r, e.rod) == pytest.approx(e.r + e.rod)
    assert K.piston_pin_z(180, e.r, e.rod) == pytest.approx(e.rod - e.r)


def test_rod_reaches_crank_pin():
    e = K.Inline4()
    for th in range(0, 360, 15):
        y, z = K.crank_pin_yz(th, e.r)
        pin = K.piston_pin_z(th, e.r, e.rod)
        tilt = K.rod_tilt(th, e.r, e.rod)
        big_end = (e.rod * math.sin(tilt), pin - e.rod * math.cos(tilt))
        assert big_end[0] == pytest.approx(y, abs=1e-9)
        assert big_end[1] == pytest.approx(z, abs=1e-9)


def test_firing_order_is_1342():
    order = K.Inline4().firing_order()
    i = order.index(1)
    assert order[i:] + order[:i] == [1, 3, 4, 2]


def test_cylinders_reach_tdc_when_their_cycle_says_so():
    e = K.Inline4()
    for i in range(4):
        theta = e.CYCLE_OFFSETS[i] + 360.0           # firing TDC of cylinder i
        st = e.cylinder(i, theta)
        assert st["cycle"] == pytest.approx(360.0)
        assert st["pin_z"] == pytest.approx(e.r + e.rod)


def test_valves_open_in_the_right_strokes():
    assert K.intake_lift(90, 0.01) > 0.009            # mid-intake: wide open
    assert K.intake_lift(450, 0.01) == 0.0            # power stroke: shut
    assert K.exhaust_lift(630, 0.01) > 0.009
    assert K.exhaust_lift(270, 0.01) == 0.0


def test_cam_lobe_matches_valve_lift():
    pts, peak = K.cam_profile(*K.INTAKE, 0.0175, 0.0095, steps=360)
    radius = dict(pts)
    for a, r in pts[::20]:
        assert r - 0.0175 == pytest.approx(K.lift(peak + 2 * a, *K.INTAKE, 0.0095), abs=1e-12)
    assert max(radius.values()) == pytest.approx(0.0175 + 0.0095, abs=1e-5)


def test_combustion_follows_spark():
    assert K.combustion(K.SPARK - 1) == 0.0
    assert K.combustion(372) == pytest.approx(1.0)
    assert 0 < K.combustion(450) < 0.5
    assert K.combustion(600) == 0.0


# ------------------------------------------------------------ crank solver / shot rules

def _shot(sid, start, end, crank="explain", events=()):
    return {"id": sid, "start": start, "end": end, "crank": crank, "events_t": list(events)}


def test_solver_lands_events_on_their_words():
    shots = [_shot("s01", 0, 3, "run", [{"type": "spark", "cylinder": 1, "t": 1.0}]),
             _shot("s02", 3, 6, "slow", [{"type": "spark", "cylinder": 3, "t": 4.2},
                                          {"type": "intake_open", "cylinder": 1, "t": 5.5}])]
    keys = shotlist.solve_crank(shots, KIT, 200.0)
    for s in shots:
        for e in s["events_t"]:
            c = (shotlist.theta_at(keys, e["t"]) - KIT["cycle_offsets"][e["cylinder"]]) % 720
            assert c == pytest.approx(KIT["event_angles"][e["type"]] % 720, abs=1e-6)
    assert all(b[1] >= a[1] for a, b in zip(keys, keys[1:]))          # the engine never runs backwards


def test_solver_closes_the_loop():
    shots = [_shot("s01", 0, 2, "run"), _shot("s02", 2, 5, "fast")]
    keys = shotlist.solve_crank(shots, KIT, 200.0, loop_to=200.0)
    assert (keys[-1][1] - 200.0) % 720 == pytest.approx(0.0)


def test_simultaneous_sparks_are_rejected():
    ev = [{"type": "spark", "cylinder": c, "t": 2.0} for c in (1, 2)]
    errs = shotlist._event_feasibility([_shot("s01", 0, 4, "run", ev)], KIT)
    assert errs and "same moment" in errs[0]


def test_implausibly_fast_events_are_rejected():
    ev = [{"type": "tdc_firing", "cylinder": 1, "t": 1.0}, {"type": "spark", "cylinder": 1, "t": 1.3}]
    errs = shotlist._event_feasibility([_shot("s01", 0, 3, "slow", ev)], KIT)
    assert errs and "too fast" in errs[0]


def test_frames_tile_without_gaps():
    shots = [{"start": 0.0, "end": 2.37}, {"start": 2.37, "end": 5.0}, {"start": 5.0, "end": 7.31}]
    spans = [frames_of(s) for s in shots]
    assert spans[0][0] == 1
    for (a0, a1), (b0, b1) in zip(spans, spans[1:]):
        assert b0 == a1 + 1


# ------------------------------------------------------------ script hard checks

FACTS = {"facts": [{"id": "sparks", "claim": "fires about 3,500 times a minute", "value": "3,500",
                    "unit": "per minute", "quote": "3,500 sparks"}]}
BRIEF = {"target_seconds": 12, "mechanisms": [{"id": "ignition"}]}


def _beats(*texts, mech=("hook", "ignition", "outro")):
    return {"beats": [{"id": f"b{i + 1:02d}", "mechanism": mech[min(i, len(mech) - 1)], "narration": t,
                       "title": "", "stat": None, "fact_ids": [], "visual": "", "shot_type": "section",
                       "seconds": 3} for i, t in enumerate(texts)]}


def test_unsourced_numbers_are_rejected():
    s = _beats("Why does it not shake?", "It fires 9,000 times.", "What next?")
    errs = script.check(s, BRIEF, FACTS)
    assert any("9,000" in e for e in errs)


def test_sourced_numbers_pass():
    s = _beats("Why does it not shake?", "It fires 3,500 times a minute.", "What next?")
    s["beats"][1]["fact_ids"] = ["sparks"]
    assert not [e for e in script.check(s, BRIEF, FACTS) if "number" in e or "quantity" in e]


def test_ending_must_be_a_question_without_cta():
    s = _beats("Why?", "It turns.", "Comment below what you think.")
    errs = script.check(s, BRIEF, FACTS)
    assert any("question" in e for e in errs) and any("comments" in e for e in errs)


def test_jargon_is_flagged():
    assert script.JARGON.search("peak pressure 15 crank degrees after TDC")
    assert not script.JARGON.search("the piston starts down")


# ------------------------------------------------------------ research verification

def test_quote_matching():
    page = research._normalise("<p>The spark plug fires up to 30,000&nbsp;volts across the gap.[3]</p>")
    assert research.quote_found("fires up to 30,000 volts across the gap", page) == 1.0
    assert research.quote_found("fires up to 40,000 volts across the gap", page) < 1.0
    assert research.quote_found("completely different words here", page) < 0.9


# ------------------------------------------------------------ words, captions, srt

def test_align_keeps_script_words_and_interpolates_misses():
    toks = ["The", "coil", "sends", "30,000", "volts."]
    heard = [{"text": "The", "start": 0.0, "end": 0.1}, {"text": "coil", "start": 0.12, "end": 0.4},
             {"text": "sends", "start": 0.45, "end": 0.7}, {"text": "thirty", "start": 0.75, "end": 1.0},
             {"text": "thousand", "start": 1.0, "end": 1.3}, {"text": "volts", "start": 1.35, "end": 1.7}]
    times = align.align(toks, heard, 2.0)
    assert len(times) == len(toks)
    assert times[1] == (0.12, 0.4)
    assert times[4][0] == pytest.approx(1.35)
    assert times[2][1] <= times[3][0] + 1e-9 <= times[4][0]


def test_caption_groups_are_2_to_4_words_and_break_on_sentences():
    words = [{"text": t, "start": i * 0.3, "end": i * 0.3 + 0.25, "beat": "b01"}
             for i, t in enumerate("Each cylinder repeats four moves. Suck: the piston drops, drawing in air.".split())]
    groups = compose.caption_groups(words)
    assert all(1 <= len(g) <= 4 for g in groups)
    assert groups[0][-1]["text"] == "moves." or len(groups[0]) == 4
    assert sum(len(g) for g in groups) == len(words)


def test_srt_times():
    assert package._srt_time(3725.5) == "01:02:05,500"


@pytest.mark.parametrize("kit_name", sorted(kits.KITS))
def test_kit_vocab_is_consistent(kit_name):
    kit = kits.KITS[kit_name]
    for name, (need, _d) in kit["cameras"].items():
        assert "closed" in need or "xray" in need or any(c in need for c in kit["cuts"]), name
    for m in kit["mechanisms"].values():
        assert m["cut"] in kit["cuts"] or m["cut"] in ("closed", "xray")
        assert all(c in kit["cameras"] for c in m["cameras"])
        assert all(a in kit["anchors"] for a in m["anchors"])
    assert kit["drive"] in ("crank", "flow")
    if kit["drive"] == "crank":
        assert set(kit["event_angles"]) == set(kit["events"])
    assert all(m in kit["mechanisms"] for m in kit.get("story", []))
    tr = kit.get("tracker")
    if tr:
        assert all(m in kit.get("story", kit["mechanisms"]) for m in tr["mechanisms"])
        assert len(tr["labels"]) * tr["span"] == 720.0


def test_telegraphic_lines_are_rejected():
    s = _beats("Why does it not shake?", "Suck: the piston drops, drawing in air.", "What next?")
    assert any("reads like a label" in e for e in script.check(s, BRIEF, FACTS))
    s = _beats("Why does it not shake?", "The piston drops and pulls air in behind it.", "What next?")
    assert not any("reads like a label" in e for e in script.check(s, BRIEF, FACTS))


def _look_shot(sid, preset, state="sectioned", cut="transverse_1"):
    return {"id": sid, "camera": {"from": {"preset": preset}, "to": {"preset": preset}},
            "cut": {"state": state, "preset": cut}}


def test_repeated_views_are_rejected():
    same = [_look_shot("s01", "section_front"), _look_shot("s02", "section_front")]
    assert any("repeats" in e for e in shotlist._variety(same))
    many = [_look_shot(f"s{i:02d}", p) for i, p in enumerate(["section_front", "chamber_close"] * 4)]
    assert any("at most 3 times" in e for e in shotlist._variety(many))
    mixed = [_look_shot(f"s{i:02d}", p, st) for i, (p, st) in enumerate(
        [("hero_34", "closed"), ("intake_side", "xray"), ("injector_close", "xray"), ("stroke_close", "sectioned"),
         ("chamber_close", "sectioned"), ("stroke_close", "sectioned"), ("exhaust_close", "xray"),
         ("crank_close", "sectioned"), ("valvetrain_close", "sectioned"), ("longitudinal_side", "xray"),
         ("flywheel_close", "xray"), ("hero_34", "closed")])]
    assert shotlist._variety(mixed) == []


def test_stroke_tracker_follows_the_crank():
    beats = [{"id": "b01", "start": 0.0, "end": 2.0}, {"id": "b02", "start": 2.0, "end": 10.0},
             {"id": "b03", "start": 10.0, "end": 12.0}]
    sc = {"beats": [{"id": "b01", "mechanism": "hook"}, {"id": "b02", "mechanism": "intake_stroke"},
                    {"id": "b03", "mechanism": "outro"}]}
    sl = {"crank": {"keys": [(0.0, 0.0), (12.0, 720.0 * 12 / 8.0)]}, "duration": 12.0}   # 90 deg/s
    labels, lit, t0, t1 = compose._chips_timeline(sc, {"beats": beats}, {"kit": "inline4"}, sl)
    assert labels == ["INTAKE", "COMPRESSION", "POWER", "EXHAUST"]
    assert t0 == pytest.approx(1.7) and t1 == pytest.approx(10.4)
    first = {k: on for k, on, _ in reversed(lit)}
    assert first[1] == pytest.approx(2.0, abs=1 / 30)          # 180 deg at 90 deg/s
    assert first[2] == pytest.approx(4.0, abs=1 / 30)
    assert all(b - a > 0 for _, a, b in lit)


def test_story_kit_brief_covers_every_chapter():
    kit = kits.KITS["inline4"]
    assert kit["story"][0] == "air_fuel" and kit["story"][-1] == "output"
    assert "Story:" in kits.describe()


def test_flow_kits_take_events_without_pinning():
    pwr = kits.KITS["pwr"]
    shots = [_shot("s01", 0, 3, "run", [{"type": "rods_in", "cylinder": 1, "t": 1.0},
                                        {"type": "rods_out", "cylinder": 1, "t": 1.05}])]
    assert shotlist._event_feasibility(shots, pwr) == []
    keys = shotlist.solve_crank(shots, pwr, 0.0)
    assert keys[-1][1] == pytest.approx(540.0 * 3)
