import copy
import json
import os
import unittest

from config.paths import PROJECT_ROOT
from agents import director
from agents.plan_writer import validate

PLAN = os.path.join(PROJECT_ROOT, "engine", "director", "plans", "septic.json")


def load_plan():
    with open(PLAN, encoding="utf-8") as f:
        return json.load(f)


class FitWindowTest(unittest.TestCase):
    def test_every_fittable_voice_lands_strictly_inside_the_window(self):
        for tenths in range(550, 670):
            d = tenths / 10
            tempo, tail = director.fit_window(d)
            if tempo is None:
                continue
            total = d / tempo + tail
            self.assertTrue(director.WINDOW[0] < total < director.WINDOW[1], (d, tempo, tail, total))
            self.assertLessEqual(abs(tempo - 1), director.MAX_TEMPO + 1e-9)

    def test_natural_lengths_keep_the_real_speech_rate(self):
        for d in (58.5, 60.0, 61.5, 63.0):
            self.assertEqual(director.fit_window(d)[0], 1.0)

    def test_hopeless_lengths_are_reported(self):
        self.assertEqual(director.fit_window(45.0), (None, None))
        self.assertEqual(director.fit_window(75.0), (None, None))


class PauseCapTest(unittest.TestCase):
    def test_cap_trims_only_what_is_needed(self):
        runs = [(i * 3.0, i * 3.0 + 1.0) for i in range(20)]       # twenty 1 s pauses
        cap = director.pause_cap(runs, 70.0, 61.0)                 # 9 s to remove
        removed = sum(max(0.0, 1.0 - cap) for _ in runs)
        self.assertAlmostEqual(70.0 - removed, 61.0, delta=0.05)

    def test_never_below_the_minimum_pause(self):
        runs = [(0.0, 0.5)] * 4
        self.assertGreaterEqual(director.pause_cap(runs, 80.0, 60.0), director.MIN_PAUSE)

    def test_short_voice_keeps_its_pauses(self):
        self.assertEqual(director.pause_cap([(1.0, 1.6)], 50.0, 61.0), director.MAX_PAUSE)


class PlanRulesTest(unittest.TestCase):
    def test_golden_plan_passes(self):
        self.assertEqual(validate(load_plan()), [])

    def test_rules_catch_bad_plans(self):
        plan = load_plan()
        bad = copy.deepcopy(plan)
        bad["beats"][0]["text"] = "This is a very long and boring opening sentence about septic tanks in general."
        bad["beats"][2]["labels"][0]["at"] = "nonexistent"
        bad["beats"].pop()
        bad["beats"][3]["text"] += " You should pump it every three years."
        problems = " | ".join(validate(bad))
        self.assertIn("cold open", problems)
        self.assertIn("is advice", problems)
        self.assertIn("nonexistent", problems)
        self.assertIn("in that order", problems)


class PropsTest(unittest.TestCase):
    def timing(self, plan):
        beats, f = [], 1
        for b in plan["beats"]:
            words = b["text"].split()
            cues = {director._key(w): f + i * 10 for i, w in enumerate(words)}
            beats.append({"id": b["id"], "f0": f, "f1": f + len(words) * 10, "cues": cues})
            f += len(words) * 10 + 1
        return {"fps": 30, "total": f - 1, "beats": beats}

    def test_overlay_timeline(self):
        plan = load_plan()
        t = self.timing(plan)
        p = director.props(plan, t, [{"text": "This", "start": 0.0, "end": 0.2}], {}, t["total"])
        self.assertEqual(p["hook"]["text"], plan["beats"][0]["hook_text"])
        self.assertTrue(2 <= len(p["chapters"]) <= 4)
        self.assertNotIn("checklist", p)                       # entertainment, not a lesson
        hook, follow = t["beats"][0], t["beats"][1]
        self.assertEqual(p["rewind"], {"from": follow["f0"], "to": follow["f0"] + 18,
                                       "sourceFrom": hook["f1"], "sourceTo": hook["f0"]})
        self.assertEqual(p["endCard"]["to"], t["total"])
        # never more than two pinned labels at once
        for f in range(1, t["total"]):
            self.assertLessEqual(sum(1 for lb in p["labels"] if lb["from"] <= f <= lb["to"]), 2, f)
        # every label lives inside its beat
        spans = {b["id"]: (b["f0"], b["f1"]) for b in t["beats"]}
        for lb in p["labels"]:
            self.assertTrue(any(a <= lb["from"] <= lb["to"] <= b for a, b in spans.values()), lb)


class FrameQATest(unittest.TestCase):
    def test_flicker_sees_strobing_but_not_steady_motion(self):
        import numpy as np
        from PIL import Image
        from agents import frame_qa
        rng = np.random.default_rng(1)
        base = rng.integers(0, 255, (480, 270), dtype=np.uint8)
        moving = [Image.fromarray(np.roll(base, k, axis=1) // 4 + 100) for k in range(3)]   # smooth, low contrast
        steady = [Image.fromarray(np.full((480, 270), 120, np.uint8)) for _ in range(3)]
        strobe = [steady[0], Image.fromarray(np.where(base > 128, 200, 120).astype(np.uint8)), steady[2]]
        self.assertLess(frame_qa.flicker(steady), 0.01)
        self.assertGreater(frame_qa.flicker(strobe), 20)
        self.assertGreaterEqual(frame_qa.flicker(moving), 0)

    def test_colorfulness_orders_grey_below_vivid(self):
        import numpy as np
        from PIL import Image
        from agents import frame_qa
        grey = Image.fromarray(np.full((480, 270, 3), 128, np.uint8))
        vivid = np.zeros((480, 270, 3), np.uint8)
        vivid[:, :135] = (255, 40, 0)
        vivid[:, 135:] = (0, 90, 255)
        self.assertLess(frame_qa.colorfulness(grey), 1)
        self.assertGreater(frame_qa.colorfulness(Image.fromarray(vivid)), frame_qa.COLORFUL_MIN)

    def test_pan_speed_catches_a_whip_pan(self):
        import numpy as np
        from PIL import Image
        from agents import frame_qa
        rng = np.random.default_rng(2)
        base = (rng.random((960, 540)) * 255).astype(np.uint8)
        slow = [Image.fromarray(np.roll(base, 2 * k, axis=1)) for k in range(3)]
        whip = [Image.fromarray(np.roll(base, 30 * k, axis=1)) for k in range(3)]
        self.assertLess(frame_qa.pan_speed(slow), frame_qa.PAN_MAX)
        self.assertGreater(frame_qa.pan_speed(whip), frame_qa.PAN_MAX)
        self.assertLess(frame_qa.flicker(whip), 0.5)        # a pan is motion, not strobing

    def test_highlights_catch_a_greyed_picture(self):
        import numpy as np
        from PIL import Image
        from agents import frame_qa
        grey = np.linspace(0, 181, 480 * 270).reshape(480, 270).astype(np.uint8)    # tops out at 0.71 (AgX)
        full = np.linspace(0, 255, 480 * 270).reshape(480, 270).astype(np.uint8)
        self.assertLess(frame_qa.highlights(Image.fromarray(grey).convert("RGB")), frame_qa.HIGHLIGHT_MIN)
        self.assertGreater(frame_qa.highlights(Image.fromarray(full).convert("RGB")), frame_qa.HIGHLIGHT_MIN)


if __name__ == "__main__":
    unittest.main()
