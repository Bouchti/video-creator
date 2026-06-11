import unittest

from agents.editor_comfy import (
    COMFY_CLIP_FRAMES,
    _scene_index_for_clip,
    _wan_frame_count,
    comfy_scene_prompt,
    plan_comfy_clips,
)


class ComfyHelperTests(unittest.TestCase):
    def test_wan_frame_count_is_fixed_short_clip(self):
        self.assertEqual(COMFY_CLIP_FRAMES, _wan_frame_count())
        self.assertEqual(33, _wan_frame_count(99.0))

    def test_plan_comfy_clips_scales_many_short_clips(self):
        # 78s voiceover at ~2s each -> ~39 clips, not 16.
        num_clips, gen_seconds = plan_comfy_clips(78.5, num_scenes=25)
        self.assertGreaterEqual(num_clips, 38)
        self.assertAlmostEqual(gen_seconds, 33 / 16, places=1)

    def test_scene_index_maps_clips_in_story_order(self):
        self.assertEqual(0, _scene_index_for_clip(0, 40, 25))
        self.assertEqual(0, _scene_index_for_clip(1, 40, 25))
        self.assertEqual(1, _scene_index_for_clip(2, 40, 25))

    def test_comfy_scene_prompt_includes_clip_narration_beat(self):
        script = {
            "video_title": "Last Mammoths",
            "mood": "shocking",
            "visual_style": "35mm documentary, cold blue grade",
            "spoken_script": "One. Two. Three. Four.",
            "scenes": [
                "wide shot of woolly mammoth herd on snowy Arctic island",
                "close-up of ancient Egyptian pyramid construction",
            ],
        }
        prompt = comfy_scene_prompt(
            script, 0, clip_beat="mammoths still roamed the Arctic"
        )
        self.assertIn("woolly mammoth", prompt)
        self.assertIn("Must visually depict this narration line", prompt)
        self.assertIn("mammoths still roamed", prompt)
        self.assertIn("Last Mammoths", prompt)
        self.assertIn("35mm documentary", prompt)


if __name__ == "__main__":
    unittest.main()
