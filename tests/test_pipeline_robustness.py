"""A full local-ai run finishes its video instead of stopping on one bad topic, shot or platform."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _script(**extra):
    return {"video_title": "Lava builds land", "description": "d", "hashtags": ["#a"],
            "spoken_script": "one two three", **extra}


class TopicRetryTests(unittest.TestCase):
    def _run(self, folder, scripts, **kwargs):
        import main
        video = Path(folder) / "final.mp4"
        video.write_bytes(b"v")
        topics = iter(["Topic A", "Topic B", "Topic C"])
        leader = MagicMock(side_effect=lambda source=None, exclude=None: {
            "topic": next(topics), "tone": "epic", "angle": "story_behind", "research": [{"url": "u"}]})
        publish = MagicMock(return_value={"success": True})
        with patch.object(main, "OUTPUT_DIR", folder), \
                patch("agents.leader.find_todays_topic", leader), \
                patch("agents.leader.save_used_topic"), \
                patch("agents.evaluator.evaluate_with_retry", side_effect=scripts), \
                patch("agents.editor_local_ai.process_video", return_value=str(video)), \
                patch("agents.post_text.write", return_value="post.txt"), \
                patch("agents.publisher.publish_video", publish):
            result = main.run_pipeline(source="local-ai", duration=65, **kwargs)
        return result, leader, publish

    def test_a_topic_whose_script_fails_is_swapped_for_a_new_one(self):
        with tempfile.TemporaryDirectory() as folder:
            result, leader, _ = self._run(folder, [None, _script()])
        self.assertTrue(result["success"])
        self.assertEqual(result["topic"], "Topic B")
        self.assertEqual(leader.call_args_list[1].kwargs["exclude"], ["Topic A"])

    def test_a_crashing_leader_is_retried(self):
        import main
        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / "final.mp4"
            video.write_bytes(b"v")
            leader = MagicMock(side_effect=[RuntimeError("search down"), {
                "topic": "Topic A", "tone": "epic", "angle": "a", "research": [{"url": "u"}]}])
            with patch.object(main, "OUTPUT_DIR", folder), \
                    patch("agents.leader.find_todays_topic", leader), \
                    patch("agents.leader.save_used_topic"), \
                    patch("agents.evaluator.evaluate_with_retry", return_value=_script()), \
                    patch("agents.editor_local_ai.process_video", return_value=str(video)), \
                    patch("agents.post_text.write", return_value="post.txt"):
                result = main.run_pipeline(source="local-ai", duration=65)
        self.assertTrue(result["success"])

    def test_the_run_only_fails_once_every_topic_attempt_is_spent(self):
        with tempfile.TemporaryDirectory() as folder:
            result, leader, _ = self._run(folder, [None, None, None])
        self.assertFalse(result["success"])
        self.assertEqual(result["stage_failed"], "script")
        self.assertEqual(leader.call_count, 3)

    def test_a_video_the_final_review_rejected_is_delivered_but_not_published(self):
        with tempfile.TemporaryDirectory() as folder:
            result, _, publish = self._run(folder, [_script(publish_hold=True, quality_warnings=["loops"])],
                                           publish_platforms=("youtube",))
        self.assertTrue(result["success"])
        self.assertTrue(result["publish_held"])
        self.assertEqual(result["quality_warnings"], ["loops"])
        publish.assert_not_called()

    def test_one_failing_platform_does_not_fail_the_run(self):
        with tempfile.TemporaryDirectory() as folder:
            import main
            video = Path(folder) / "final.mp4"
            video.write_bytes(b"v")
            publish = MagicMock(side_effect=[RuntimeError("token expired"), {"success": True}])
            with patch.object(main, "OUTPUT_DIR", folder), \
                    patch("agents.leader.save_used_topic"), \
                    patch("agents.leader.research_topic", return_value=[{"url": "u"}]), \
                    patch("agents.evaluator.evaluate_with_retry", return_value=_script()), \
                    patch("agents.editor_local_ai.process_video", return_value=str(video)), \
                    patch("agents.post_text.write", return_value="post.txt"), \
                    patch("agents.publisher.publish_video", publish):
                result = main.run_pipeline("manual topic", source="local-ai", duration=65,
                                           publish_platforms=("youtube", "instagram"))
        self.assertTrue(result["success"])
        self.assertEqual(publish.call_count, 2)
        self.assertFalse(result["publishing"][0]["success"])


class EditorResumeTests(unittest.TestCase):
    def test_a_run_that_stops_is_resumed_from_disk(self):
        from agents import editor_local_ai
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "render").mkdir()
            (Path(folder) / "render" / "final.mp4").write_bytes(b"v")
            stopped = SimpleNamespace(state="partially_completed", error="CUDA error", project_dir=folder,
                                      settings={}, outputs={})
            done = SimpleNamespace(state="completed", error=None, project_dir=folder,
                                   settings={"quality_warnings": ["2 of 22 shots were salvaged"],
                                             "final_creative_review": {"valid": True}},
                                   outputs={"video": "render/final.mp4"})
            runner = MagicMock()
            runner.return_value.run.side_effect = [stopped, done]
            script = _script()
            with patch.object(editor_local_ai, "PipelineConfig"), \
                    patch.object(editor_local_ai, "create_project", return_value=stopped), \
                    patch.object(editor_local_ai, "load_project", return_value=stopped) as load, \
                    patch.object(editor_local_ai, "QueueRunner", runner), \
                    patch.object(editor_local_ai.time, "sleep"):
                path = editor_local_ai.process_video(script)
        self.assertTrue(path.endswith("final.mp4"))
        load.assert_called_once_with(folder)
        self.assertEqual(script["quality_warnings"], ["2 of 22 shots were salvaged"])
        self.assertFalse(script["publish_hold"])

    def test_a_user_pause_is_not_resumed(self):
        from agents import editor_local_ai
        paused = SimpleNamespace(state="paused", error=None, project_dir="p", settings={}, outputs={})
        runner = MagicMock()
        runner.return_value.run.return_value = paused
        with patch.object(editor_local_ai, "PipelineConfig"), \
                patch.object(editor_local_ai, "create_project", return_value=paused), \
                patch.object(editor_local_ai, "QueueRunner", runner):
            with self.assertRaises(RuntimeError):
                editor_local_ai.process_video(_script())
        self.assertEqual(runner.return_value.run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
