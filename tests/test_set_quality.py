import json
import os
import tempfile
import unittest
from unittest.mock import patch

from agents import set_builder as sb


QA = {
    "fingerprint": "abc",
    "beats": {"01_hook": [{"frames": [1, 4], "issue": "collision: Kid1 x Kid2 (Kid1_skull / lantern_base)"},
                          {"frames": [5, 9], "issue": "collision: Kid1 x Kid2 (Kid1_torso / lantern_glow)"},
                          {"frames": [5, 9], "issue": "collision: Kid1 x lamp (Kid1_handmeshL / lamp_handle)"},
                          {"frames": [5, 9], "issue": "cropped: Kid2 cut by the frame edge"}]},
    "quality": {"03_fail": [{"frames": [200, 200], "issue": "hero_small: Max fills at most 12% of the frame"}],
                "all": [{"frames": [0, 0], "issue": "live_boolean: hull is cut by carver while moving"}]},
    "objects": {"pipe x post": 210},
}


class SetQualityTests(unittest.TestCase):
    def _work(self, d):
        json.dump({"fingerprint": "abc"}, open(os.path.join(d, "preview_manifest.json"), "w"))
        json.dump({"beats": [{"start": 0, "end": 99}, {"start": 100, "end": 179}, {"start": 180, "end": 299}]},
                  open(os.path.join(d, "timings.json"), "w"))
        json.dump(QA, open(os.path.join(d, "qa.json"), "w"))

    def test_measured_issues_map_to_beats(self):
        with tempfile.TemporaryDirectory() as d, \
                patch("importlib.import_module", return_value=type("S", (), {"HERO": "Max"})):
            self._work(d)
            qa = sb.qa_check("x_story", d)                       # fingerprint matches: no Blender run
        self.assertEqual(len([x for x in qa[1] if x.startswith("collision: Kid1 x Kid2")]), 1)   # one per pair
        self.assertFalse(any("handmesh" in x for x in qa[1]))                                  # holding = fine
        self.assertTrue(any(x.startswith("hero_small") for x in qa[3]))
        self.assertTrue(any("pipe x post" in x for x in qa[3]))                                # frame 210 → beat 3
        self.assertTrue(any(x.startswith("live_boolean") for x in qa[0]))

    def test_measured_problems_reject_a_beat_the_reviewer_liked(self):
        reports = [{"beat": 1, "action": "hook", "valid": True, "fatal_problems": [], "problems": []},
                   {"beat": 3, "action": "fail", "valid": True, "fatal_problems": [], "problems": []},
                   {"beat": 4, "action": "fix", "valid": True, "fatal_problems": [], "problems": []}]
        qa = {0: ["live_boolean: hull"], 1: ["cropped: Kid2 cut by the frame edge"], 3: ["hero_small: Max 12%"]}
        out = sb._merge_qa(reports, qa)
        self.assertFalse(out[0]["valid"])                       # the whole-set problem lands on the first beat
        self.assertIn("measured: cropped: Kid2 cut by the frame edge", out[0]["problems"])   # advisory only
        self.assertFalse(out[1]["valid"])
        self.assertTrue(out[2]["valid"])
        self.assertEqual(reports[1]["fatal_problems"], [])      # the review cache's lists are not mutated


class ContactTests(unittest.TestCase):
    def test_body_inside_a_prop_is_a_defect_but_limb_contact_is_not(self):
        self.assertFalse(sb._advisory("collision: Kid1 x lantern (Kid1_skull / lantern_base)"))
        self.assertFalse(sb._advisory("collision: Max x post (Max_brim / fork_post)"))
        self.assertTrue(sb._advisory("collision: Max x sand_bed (Max_shoeR / sand_bed)"))
        self.assertTrue(sb._advisory("collision: Kid1 x pk_body (Kid1_pants_top / pk_body)"))
        self.assertTrue(sb._advisory("occluded: Kid2's head hidden behind fork_post"))
        self.assertFalse(sb._advisory("hero_small: Max fills at most 12% of the frame"))

    def test_gag_creatures_landing_on_a_character_are_by_design(self):
        # "a seagull lands on his hat", "Max surfaces wearing a fish": rejecting these deleted the gags
        self.assertTrue(sb._advisory("collision: Max x gull_leg1 (Max_hat / gull_leg1)"))
        self.assertTrue(sb._advisory("collision: Max x fish_body (Max_skull / fish_body)"))
        self.assertFalse(sb._advisory("collision: Max x car_dash (Max_torso / car_dash)"))


class LookTests(unittest.TestCase):
    def test_a_washed_out_set_needs_a_set_wide_repair(self):
        import tempfile
        from unittest import mock
        work = tempfile.mkdtemp()
        for k in range(5):
            open(os.path.join(work, f"preview_{k + 1:02d}_beat_b.png"), "wb").close()
        with mock.patch("agents.frame_qa.colorfulness", return_value=38.0):
            self.assertIn("median colourfulness 38", sb.look_problem(work))
        with mock.patch("agents.frame_qa.colorfulness", return_value=52.0):
            self.assertEqual(sb.look_problem(work), "")
        self.assertEqual(sb.look_problem(tempfile.mkdtemp()), "")


if __name__ == "__main__":
    unittest.main()
