"""First-take rules: the designed shot is checked before any GPU time, and a clip that goes soft is caught."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from local_video import fast
from local_video.validation import detail_kept, soft_clip_problem


class DesignLintTests(unittest.TestCase):
    def test_the_windmill_well_shot_is_flagged_before_filming(self):
        problems = fast.design_problems(
            "Medium shot on a dry plain: a cast-iron hand pump, clear afternoon sun, dust in the air.",
            "Dust blows across the empty tank, dry grass stirs, slow push in on the pump. Ends close on the spout.")
        self.assertTrue(any("'dust'" in p for p in problems))
        self.assertTrue(any("'ends close'" in p for p in problems))

    def test_camera_moves_and_changing_amounts_are_flagged(self):
        problems = fast.design_problems("Wide shot of a tank in clear light.",
                                        "The camera rises to reveal the tank as water fills it.")
        flagged = " ".join(problems)
        for word in ("'rises'", "'reveal'", "'fills'"):
            self.assertIn(word, flagged)

    def test_a_tiny_subject_or_exact_count_is_flagged(self):
        problems = fast.design_problems("Medium shot from a ship's deck: exactly one tiny orange pinpoint of fire "
                                        "on the far coast.", "The swell rolls past; the camera holds still.")
        flagged = " ".join(problems)
        for word in ("'tiny'", "'pinpoint'", "'exactly one'"):
            self.assertIn(word, flagged)

    def test_a_clean_design_passes(self):
        self.assertEqual([], fast.design_problems(
            "Wide shot: a round stone tower mill on green English farmland in clear daylight.",
            "The four lattice sails turn steadily in the wind; the camera holds still."))

    def test_flagged_shots_are_rewritten_once_and_clean_ones_untouched(self):
        shots = [type("S", (), {"id": f"shot-00{i}", "index": i - 1, "narration": "n"})() for i in (1, 2)]
        manifest = type("M", (), {"shots": shots, "concept": "windmills", "visual_style": "35mm"})()
        design = {"shot-001": {"source": "designer", "frame": "Wide shot of a mill in dust haze, sun glare.",
                               "motion": "Sails turn until the dust settles."},
                  "shot-002": {"source": "designer", "frame": "Wide shot of a mill in clear light.",
                               "motion": "Sails turn steadily; the camera holds still."}}
        fixed = {"frame": "Wide shot: a stone tower mill on green farmland in clear daylight.",
                 "motion": "The four sails turn steadily in the wind; the camera holds still."}
        with patch("agents.llm.ask", return_value=fixed) as ask:
            fast._repair_design(manifest, design)
        self.assertEqual(ask.call_count, 1)
        self.assertIn("'dust'", ask.call_args.args[1])
        self.assertEqual(design["shot-001"]["motion"], fixed["motion"])
        self.assertTrue(design["shot-001"]["repaired"])
        self.assertEqual(design["shot-002"]["motion"], "Sails turn steadily; the camera holds still.")

    def test_a_shot_that_repeats_its_neighbour_is_redesigned(self):
        """Lighthouse beats 7-8: the same brazier tower on the same shingle, twice in a row."""
        shots = [type("S", (), {"id": f"shot-00{i}", "index": i - 1, "narration": "n", "scene": "brazier tower"})()
                 for i in (1, 2)]
        manifest = type("M", (), {"shots": shots, "concept": "lighthouses", "visual_style": "35mm"})()
        clean = "Wide shot: a squat stone tower with an iron brazier on a shingle headland in clear daylight."
        design = {s.id: {"source": "designer", "frame": clean,
                         "motion": "Flames lean steadily in the sea breeze; the camera holds still."} for s in shots}
        fixed = {"frame": "Close-up: the iron brazier heaped with burning coal on the tower top in clear daylight.",
                 "motion": "Flames lean steadily in the sea breeze; the camera holds still."}
        with patch("agents.llm.ask", return_value=fixed) as ask:
            fast._repair_design(manifest, design)
        self.assertEqual(ask.call_count, 1)
        self.assertIn("looks like shot 1", ask.call_args.args[1])
        self.assertEqual(design["shot-001"]["frame"], clean)
        self.assertTrue(design["shot-002"]["frame"].startswith("Close-up"))

    def test_the_design_prompt_carries_the_motion_rules(self):
        self.assertIn("never where they end up", fast.DESIGN_SCHEMA["properties"]["shots"]["items"]
                      ["properties"]["motion"]["description"])
        self.assertNotIn("drifting smoke", fast.MOTION_RULES)


class ShotDoctorTests(unittest.TestCase):
    def test_a_doctor_plan_with_an_end_state_is_rewritten_before_the_take(self):
        """Lighthouse shot-006: the doctor wrote 'the tower drifts to frame left by the final frame'."""
        from local_video import shot_doctor
        shot = type("S", (), {"id": "shot-006", "index": 5, "duration_frames": 90, "cast": [],
                              "subject_action": "Medium shot from a ship's deck toward the Pharos.",
                              "camera_action": "slow push-in", "continuity": {}})()
        bad = {"risks": [], "camera": "push_in", "start_frame_fits": True,
               "description": "Medium shot: the deck below, the Pharos at right. The camera pushes in slowly; "
                              "the tower drifts to frame left until it ends close on the fire."}
        good = {"risks": [], "camera": "locked_off", "start_frame_fits": True,
                "description": "Medium shot: the deck fills the lower half, the Pharos stands at right in clear "
                               "light. The bow lifts and falls steadily on the swell; the camera holds still."}
        with patch.object(shot_doctor.llm, "ask", side_effect=[bad, good]) as ask:
            result = shot_doctor.examine(shot, "the tower at frame left", None)
        self.assertEqual(ask.call_count, 2)
        self.assertIn("BROKE THESE FIRST-TAKE RULES", ask.call_args.args[1])
        self.assertIn("holds still", result["description"])
        self.assertIn("never a target", ask.call_args_list[0].args[1])
        self.assertNotIn("rise", shot_doctor.SCHEMA["properties"]["camera"]["enum"])


class SoftClipTests(unittest.TestCase):
    def _clip(self, folder, soften):
        import cv2
        rng = np.random.default_rng(0)
        sharp = (rng.random((960, 544, 3)) * 255).astype("uint8")
        path = str(Path(folder) / "clip.mp4")
        writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 24, (544, 960))
        for index in range(24):
            frame = sharp if index == 0 or not soften else cv2.GaussianBlur(sharp, (0, 0), 3)
            writer.write(frame)
        writer.release()
        return path

    def test_a_clip_that_goes_soft_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            detail = detail_kept(self._clip(folder, soften=True))
        self.assertLess(detail["detail_kept"], 0.35)
        self.assertIn("goes soft", soft_clip_problem(detail))

    def test_a_clip_that_stays_sharp_passes(self):
        with tempfile.TemporaryDirectory() as folder:
            detail = detail_kept(self._clip(folder, soften=False))
        self.assertEqual("", soft_clip_problem(detail))

    def test_a_first_frame_without_detail_proves_nothing(self):
        self.assertEqual("", soft_clip_problem({"detail_first": 40.0, "detail_kept": 0.1}))


if __name__ == "__main__":
    unittest.main()
