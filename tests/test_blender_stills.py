"""Engine fixes from the tunnel film review, tested on rendered stills in Blender (GPU, ~1 min): BLENDER_TESTS=1.
- the standard water (engine/studio.Water) stays see-through and blue at the tunnel sea's depth, where the old
  fixed-density Reservoir read as a solid wall;
- the cutaway characters move with motion capture (Character.act / idle / talk / walk) and hand keys keep
  their joints, with no pops."""
import json
import os
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@unittest.skipUnless(os.getenv("BLENDER_TESTS") == "1", "renders in Blender: set BLENDER_TESTS=1")
class WaterStillTest(unittest.TestCase):
    def test_water_is_see_through_blue_with_a_waterline(self):
        from config.paths import get_blender
        out = tempfile.mkdtemp()
        subprocess.run([get_blender(), "--background", "--factory-startup", "--python",
                        os.path.join(ROOT, "engine", "water_still.py"), "--", out], check=True, capture_output=True)
        rep = json.load(open(os.path.join(out, "water_report.json"), encoding="utf-8"))
        old, new = rep["old"], rep["water"]
        self.assertGreater(new["see_through"], old["see_through"] + 0.08)       # the red block reads through 3.5 m
        self.assertGreater(new["block_redness"], 0.12)
        self.assertGreater(new["water_blue"], 0.75)                             # ...and the water is still blue
        self.assertLess(new["water_redness"], -0.1)
        self.assertGreater(new["waterline_luma"], new["under_luma"] + 0.15)     # a visible waterline


@unittest.skipUnless(os.getenv("BLENDER_TESTS") == "1", "renders in Blender: set BLENDER_TESTS=1")
class MocapStillTest(unittest.TestCase):
    def test_clips_drive_the_body_and_hand_keys_keep_their_joint(self):
        from config.paths import get_blender
        out = tempfile.mkdtemp()
        subprocess.run([get_blender(), "--background", "--factory-startup", "--python",
                        os.path.join(ROOT, "engine", "mocap_still.py"), "--", out], check=True, capture_output=True)
        rep = json.load(open(os.path.join(out, "mocap_report.json"), encoding="utf-8"))
        self.assertGreater(rep["walk_motion_deg"]["kneeL"], 30)                # the knees bend: a real walk
        self.assertAlmostEqual(rep["shoulderR_at_125"][0], -70, delta=5)        # the point keeps its arm
        self.assertLess(rep["leftover_after_clip_deg"], 1.0)                 # back to its own pose after a clip
        self.assertGreater(rep["scoop_motion_late_deg"], 10)                 # a work clip repeats, never freezes
        for joint, deg in rep["max_jump_deg_per_frame"].items():
            self.assertLess(deg, 40, joint)                                     # no pop between frames


@unittest.skipUnless(os.getenv("BLENDER_TESTS") == "1", "renders in Blender: set BLENDER_TESTS=1")
class OverlayStillTest(unittest.TestCase):
    def test_labels_and_insets_are_hidden_only_while_the_frame_cuts_them(self):
        from config.paths import get_blender
        out = tempfile.mkdtemp()
        subprocess.run([get_blender(), "--background", "--factory-startup", "--python",
                        os.path.join(ROOT, "engine", "overlays_still.py"), "--", out], check=True, capture_output=True)
        rep = json.load(open(os.path.join(out, "overlays_report.json"), encoding="utf-8"))
        left, mid, inset = rep["left_shown"], rep["mid_shown"], rep["inset_shown"]
        self.assertTrue(all(left[2:12]))                     # in frame at the start
        self.assertFalse(any(left[20:30]))                   # hidden while the left edge slices it
        self.assertTrue(all(mid[2:58]))                      # a label inside the frame is never touched
        self.assertFalse(any(inset[3:15]))                   # cut by the right edge early on: hidden
        self.assertTrue(all(inset[40:58]))                   # fully in frame later: shown
        self.assertTrue(rep["boxes_at_30"])                  # make_film learns where the readable text sits
        # a label behind a wall (the water-tower film's LOAD PATH behind the legs): pulled in front, same place on
        # screen, and still shown
        self.assertLess(rep["hid_y"], 0.9)
        (x0, y0), (x1, y1) = rep["hid_view"]
        self.assertLess(abs(x1 - x0) + abs(y1 - y0), 0.05)
        self.assertTrue(all(rep["hid_shown"][2:58]))


@unittest.skipUnless(os.getenv("BLENDER_TESTS") == "1", "renders in Blender: set BLENDER_TESTS=1")
class PostureStillTest(unittest.TestCase):
    def test_a_kneeling_clip_in_a_close_shot_turns_upright(self):
        # the flood-house film: four beats opened on a giant orange hat (kneeling 'fix' under a close camera)
        from config.paths import get_blender
        out = tempfile.mkdtemp()
        subprocess.run([get_blender(), "--background", "--factory-startup", "--python",
                        os.path.join(ROOT, "engine", "posture_still.py"), "--", out], check=True, capture_output=True)
        rep = json.load(open(os.path.join(out, "posture_report.json"), encoding="utf-8"))
        self.assertGreater(rep["shares"]["10"], 0.33)                         # close: he fills half the frame
        self.assertLess(rep["shares"]["60"], 0.2)                             # wide
        self.assertEqual(len(rep["max_talk"]), 1)
        a, b = rep["max_talk"][0]
        self.assertLessEqual(a, 2)
        self.assertTrue(40 <= b <= 46)                                        # upright over the close frames only
        self.assertEqual(rep["kid_talk"], [])                                 # kneeling in a wide shot: kept


@unittest.skipUnless(os.getenv("BLENDER_TESTS") == "1", "renders in Blender: set BLENDER_TESTS=1")
class DanglingLineStillTest(unittest.TestCase):
    def test_a_cable_running_off_the_frame_is_flagged(self):
        # the water-tower film: the crane cable (no crane in the shot) read as a stray black line
        from config.paths import get_blender
        out = tempfile.mkdtemp()
        subprocess.run([get_blender(), "--background", "--factory-startup", "--python",
                        os.path.join(ROOT, "engine", "line_still.py"), "--", out], check=True, capture_output=True)
        rep = json.load(open(os.path.join(out, "line_report.json"), encoding="utf-8"))
        self.assertEqual(rep, {"crane_cable": True, "short_rope": False, "thick_pole": False})


@unittest.skipUnless(os.getenv("BLENDER_TESTS") == "1", "renders in Blender: set BLENDER_TESTS=1")
class FlowingWaterStillTest(unittest.TestCase):
    def test_a_water_sheet_is_see_through_with_moving_foam(self):
        # the water-tower slide: a flat blue slab with balls on it read as solid plastic
        from config.paths import get_blender
        out = tempfile.mkdtemp()
        subprocess.run([get_blender(), "--background", "--factory-startup", "--python",
                        os.path.join(ROOT, "engine", "flow_still.py"), "--", out], check=True, capture_output=True)
        rep = json.load(open(os.path.join(out, "flow_report.json"), encoding="utf-8"))
        self.assertGreater(rep["changed"], 0.02)                             # the streaks race along
        self.assertTrue(0.02 < rep["foam_share"] < 0.5)                      # streaks, not a white sheet
        self.assertGreater(rep["see_through"], 0.08)                         # the board under it shows


if __name__ == "__main__":
    unittest.main()
