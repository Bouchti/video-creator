"""Designed sound for local-ai videos: beds and spot effects on the shots' times (local_video/sound.py)."""
import tempfile
import unittest
from pathlib import Path

from local_video import sound
from local_video.project import create_project
from tests.test_local_video import make_test_config, sample_script


class SoundEventTests(unittest.TestCase):
    def _project(self, folder, plans):
        project = create_project("ghost army", 60, "35mm", "auto", narration_enabled=False,
                                 config=make_test_config(folder), script=sample_script())
        project.settings["fast_design"] = {shot.id: plan for shot, plan in zip(project.shots, plans)}
        return project

    def test_a_place_keeps_one_bed_across_its_cuts_and_spots_land_on_their_shot(self):
        with tempfile.TemporaryDirectory() as folder:
            project = self._project(folder, [
                {"sound_bed": "wind", "sound_spot": ""},
                {"sound_bed": "wind", "sound_spot": "plane_flyby"},
                {"sound_bed": "engine", "sound_spot": ""},
                {"sound_bed": "", "sound_spot": "boing"},             # not a documentary sound: ignored
            ])
            events = sound.events(project)
            beds = [event for event in events if event.get("bed")]
            self.assertEqual(["wind", "engine"], [event["kind"] for event in beds])
            first_two = project.shots[0].duration_seconds + project.shots[1].duration_seconds
            self.assertAlmostEqual(first_two * sound.FPS, beds[0]["duration"], places=3)
            self.assertAlmostEqual(first_two * sound.FPS + 1, beds[1]["frame"], places=3)
            spots = [event for event in events if not event.get("bed")]
            self.assertEqual(["plane_flyby"], [event["kind"] for event in spots])
            start = project.shots[0].duration_seconds
            self.assertGreater(spots[0]["frame"], start * sound.FPS)
            self.assertLess(spots[0]["frame"], first_two * sound.FPS)

    def test_a_video_without_designed_sound_keeps_the_silent_bed(self):
        with tempfile.TemporaryDirectory() as folder:
            project = self._project(folder, [{} for _ in range(30)])
            self.assertEqual([], sound.events(project))
            self.assertFalse(sound.render(project, Path(project.project_dir) / "x.wav"))


if __name__ == "__main__":
    unittest.main()
