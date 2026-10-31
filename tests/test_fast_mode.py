"""Local-ai fast mode: the deadline plan, parallax stills and deadline-aware retakes (local_video/fast.py)."""
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from local_video import fast, keyframes, queue as queue_module
from local_video.backends import GenerationResult, MiniMaxAdapter
from local_video.project import create_project
from local_video.queue import QueueRunner
from tests.test_local_video import fake_extractor, fake_validator, make_test_config, sample_script


class FakeMiniMax(MiniMaxAdapter):
    """Passes as the real MiniMax adapter (fast mode keys on it) but renders nothing."""

    def __init__(self, config, outcomes=()):
        super().__init__(config)
        self.client = None
        self.outcomes = list(outcomes)
        self.calls = []

    def available(self):
        return True, "fake"

    def generate(self, shot, target, reference_image=None, on_submitted=None):
        self.calls.append((shot.id, reference_image))
        if on_submitted:
            on_submitted(f"p-{len(self.calls)}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"clip")
        return GenerationResult(target, "minimax", f"p-{len(self.calls)}", 200.0, "fake", {})


def draw_keyframes(manifest, config, selected=None, *, workers=1, view=None, on_ready=None, all_shots=False,
                   keep_flawed=False):
    """Every shot gets a keyframe and its full-size frame, then the follow-up step runs, as in production."""
    assert all_shots and view is not None
    made = 0
    for shot in manifest.shots:
        path = keyframes.keyframe_path(manifest, shot)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"png")
        path.with_name(f"{shot.id}.hires.png").write_bytes(b"png")
        made += 1
        if on_ready:
            on_ready(shot.index, path)
    return made


def fake_render_still(manifest, shot, config, source=None, move=None):
    target = Path(manifest.project_dir) / "shots" / f"{shot.id}-still.mp4"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"still")
    return target


class FastModeTests(unittest.TestCase):
    """Planned stills (LOCAL_VIDEO_PLANNED_STILLS=1): the opt-in mode that trades quality for the deadline."""
    planned_stills = "1"

    def setUp(self):
        env = patch.dict(os.environ, {"LOCAL_VIDEO_FAST": "1", "LOCAL_VIDEO_DESIGN": "0",
                                      "LOCAL_VIDEO_PLANNED_STILLS": self.planned_stills,
                                      "PIPELINE_STARTED_AT": str(time.time()), "LOCAL_VIDEO_SHOT_DOCTOR": "0"})
        env.start()
        self.addCleanup(env.stop)

    def _run(self, folder, motion=3, reviewer=None, minutes=None):
        config = make_test_config(folder, retry_limit=2)
        project = create_project("desert city", 60, "35mm", "auto", narration_enabled=False,
                                 config=config, script=sample_script())
        project.script["beats"][0]["visual"]["description"] = "The explorer sprints down the dune"
        backend = FakeMiniMax(config)
        reviews = []

        def review(path, shot, reference, manifest):
            verdict = reviewer(shot) if reviewer else True
            reviews.append((shot.id, verdict))
            if isinstance(verdict, dict):
                return verdict
            return {"valid": verdict, "average_score": 8 if verdict else 4, "problems": [],
                    "fatal_problems": [] if verdict else ["the dune melts"], "revision_prompt": "Hold the dune."}

        def assembler(manifest, *args):
            (Path(manifest.project_dir) / "render").mkdir(exist_ok=True)
            (Path(manifest.project_dir) / "render" / "final.mp4").write_bytes(b"v")
            return {"video": "render/final.mp4"}

        runner = QueueRunner(config, {"minimax": backend}, validator=fake_validator, extractor=fake_extractor,
                             visual_reviewer=review, assembler=assembler,
                             final_reviewer=lambda *a: {"valid": True})
        budget = {"LOCAL_VIDEO_BUDGET_MINUTES": str(minutes)} if minutes else {}
        with patch.object(QueueRunner, "_prepare_minimax"), \
                patch.object(queue_module, "prepare_keyframes", side_effect=draw_keyframes), \
                patch.object(fast, "motion_budget", return_value=motion), \
                patch.object(fast, "render_still", side_effect=fake_render_still), \
                patch("local_video.validation.ffprobe", return_value={}), \
                patch("local_video.validation.media_metadata", return_value={"duration": 3.5}), \
                patch("local_video.queue.validate_final", return_value={"valid": True}), \
                patch.dict(os.environ, budget):
            result = runner.run(project)
        return result, backend, reviews

    def test_only_the_affordable_motion_shots_become_clips(self):
        with tempfile.TemporaryDirectory() as folder:
            result, backend, _ = self._run(folder, motion=3)
            self.assertEqual("completed", result.state)
            clips = [shot for shot in result.shots if shot.backend == "minimax"]
            stills = [shot for shot in result.shots if shot.backend == "still"]
            self.assertEqual(3, len(clips))
            self.assertEqual(len(result.shots) - 3, len(stills))
            self.assertIn("shot-001", [shot.id for shot in clips])          # the hook moves
            self.assertTrue(all(not shot.degraded for shot in stills))      # planned, not salvaged
            self.assertEqual(3, len(backend.calls))
            # every clip opens on its own keyframe: hard cuts, nothing waits for another shot's clip
            for shot_id, reference in backend.calls:
                self.assertEqual(f"{shot_id}.png", Path(reference).name)

    def test_a_rejected_clip_without_time_for_a_retake_plays_its_keyframe_as_a_still(self):
        with tempfile.TemporaryDirectory() as folder:
            # The clip used the time a retake needed, so the rejected take is not kept either.
            with patch.object(QueueRunner, "_can_retake", return_value=False):
                result, backend, reviews = self._run(folder, motion=1, reviewer=lambda shot: False)
            shot = result.shots[0]
            self.assertEqual(1, len(backend.calls))
            self.assertEqual("still", shot.backend)
            self.assertEqual("still", shot.degraded)
            self.assertTrue(any(e["event"] == "retake_skipped_deadline" for e in result.events))

    def test_a_rejected_clip_gets_one_retake_while_time_allows(self):
        with tempfile.TemporaryDirectory() as folder:
            verdicts = iter([False, True])
            result, backend, _ = self._run(folder, motion=1, reviewer=lambda shot: next(verdicts))
            self.assertEqual(2, len(backend.calls))
            self.assertEqual("minimax", result.shots[0].backend)
            self.assertFalse(result.shots[0].degraded)

    def test_clips_that_no_longer_fit_the_deadline_become_stills_least_needed_first(self):
        with tempfile.TemporaryDirectory() as folder:
            # 4 clips planned but the budget is nearly spent: only what fits is rendered.
            with patch.object(fast, "clip_cost", return_value=205.0), \
                    patch.object(QueueRunner, "_seconds_left", return_value=450.0):
                result, backend, _ = self._run(folder, motion=4)
            self.assertEqual(2, len(backend.calls))
            demoted = [e["shot"] for e in result.events if e["event"] == "shot_demoted_to_still"]
            self.assertEqual(2, len(demoted))
            self.assertNotIn("shot-001", demoted)                           # the hook keeps its motion


class EveryShotMovesTests(FastModeTests):
    """The default since 2026-10-31: planned stills made videos of zooming photographs, and quality is never
    traded for time."""
    planned_stills = "0"

    def test_only_the_affordable_motion_shots_become_clips(self):
        with tempfile.TemporaryDirectory() as folder:
            result, backend, _ = self._run(folder, motion=3)    # a stills budget is ignored
            self.assertEqual("completed", result.state)
            self.assertTrue(all(shot.backend == "minimax" for shot in result.shots))
            self.assertEqual(len(result.shots), len(backend.calls))

    def test_clips_that_no_longer_fit_the_deadline_become_stills_least_needed_first(self):
        with tempfile.TemporaryDirectory() as folder:
            # Far behind schedule: every shot still gets its clip.
            with patch.object(fast, "clip_cost", return_value=205.0),                     patch.object(QueueRunner, "_seconds_left", return_value=10.0):
                result, backend, _ = self._run(folder)
            self.assertEqual(len(result.shots), len(backend.calls))
            self.assertFalse([e for e in result.events if e["event"] == "shot_demoted_to_still"])
            self.assertTrue(all(shot.backend == "minimax" for shot in result.shots))

    def test_a_rejected_clip_without_time_for_a_retake_plays_its_keyframe_as_a_still(self):
        with tempfile.TemporaryDirectory() as folder:
            # The deadline never drops a retake: the hook's first two takes fail, the third passes.
            verdicts = {"shot-001": iter([False, False, True])}
            with patch.object(QueueRunner, "_seconds_left", return_value=10.0):
                result, backend, _ = self._run(folder, reviewer=lambda shot: next(verdicts.get(shot.id, iter([True]))))
            self.assertEqual(3, sum(1 for shot_id, _ in backend.calls if shot_id == "shot-001"))
            self.assertEqual("minimax", result.shots[0].backend)
            self.assertFalse(result.shots[0].degraded)
            self.assertFalse([e for e in result.events if e["event"] == "retake_skipped_deadline"])

    def test_a_rejected_clip_gets_one_retake_while_time_allows(self):
        with tempfile.TemporaryDirectory() as folder:
            # Every normal take and the repair take are spent before any fallback.
            with patch.object(QueueRunner, "_still_replacement", return_value=False):
                result, backend, _ = self._run(folder, reviewer=lambda shot: shot.id != "shot-002")
            self.assertEqual(4, sum(1 for shot_id, _ in backend.calls if shot_id == "shot-002"))
            self.assertTrue(any(e["event"] == "shot_repair_take" for e in result.events))

    def test_a_clip_is_generated_from_and_judged_against_the_designed_staging(self):
        """Molasses hook: the plan's towering wave failed every take; the clip follows the drawable staging."""
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder)
            script = sample_script()
            script["recurring_objects"] = ["The tank: a squat riveted steel tank; intact through beat 3, torn after",
                                           "The syrup: glossy near-black liquid moving as a rolling mass"]
            project = create_project("molasses", 60, "35mm", "auto", narration_enabled=False, config=config,
                                     script=script)
            shot = project.shots[0]
            for item in project.shots:
                item.continuity = {**(item.continuity or {}), "recurring_objects": "; ".join(script["recurring_objects"])}
            project.settings["fast_design"] = {item.id: {"render": "motion", "motion_need": 5, "frame": "",
                                                          "still_move": "push_in", "source": "designer"}
                                               for item in project.shots}
            project.settings["fast_design"][shot.id].update(
                frame="Wide shot: the squat riveted steel tank stands in a cobbled yard under grey sky.",
                motion="A gull glides past and the camera pushes in slowly. The tank fills the frame at the end.",
                subjects=["The tank"])
            planned = shot.subject_action
            QueueRunner(config, {})._direct_clips(project, [shot])
            design = project.settings["fast_design"][shot.id]
            self.assertEqual(planned, design["planned_action"])
            self.assertTrue(shot.subject_action.startswith("Wide shot: the squat riveted steel tank"))
            self.assertIn("A gull glides past", shot.prompt)
            self.assertIn("The tank fills the frame at the end", shot.prompt)
            self.assertNotIn("rolling mass", shot.prompt)          # a subject this staging does not show
            self.assertNotIn("torn after", shot.prompt)            # a later state of the story
            prompt = shot.prompt
            QueueRunner(config, {})._direct_clips(project, [shot])  # once only
            self.assertEqual(prompt, shot.prompt)
            self.assertEqual("Wide shot: the squat riveted steel tank stands in a cobbled yard under grey sky.",
                             fast.frame_view(project, shot).subject_action)

    def test_a_reviewer_out_of_budget_stops_the_run_instead_of_rejecting_takes(self):
        """Ghost Army shot-010: CLAUDE_TOKEN_BUDGET ran out and every unreviewed take was rejected."""
        out = {"valid": False, "skipped": True, "reason": "vision review unavailable: BudgetExceeded"}
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(queue_module.ReviewerUnavailable):
                self._run(folder, reviewer=lambda shot: out if shot.id == "shot-003" else True)
            from local_video.project import load_project
            project = load_project(next(Path(folder).glob("**/project.json")).parent)
            shot = project.shots[2]
            self.assertEqual(1, len(shot.attempts))                  # no take was thrown away
            self.assertEqual("interrupted", shot.attempts[0]["status"])
            self.assertNotEqual("accepted", shot.status)
            self.assertEqual("accepted", project.shots[1].status)
            self.assertIn("BudgetExceeded", project.error)

    def test_a_shot_whose_every_take_fails_is_restaged_instead_of_becoming_a_still(self):
        """Ghost Army shot-018: four fatal takes of a blob-like rubber tank, then a still picture."""
        staging = {"frame": "Medium shot: Restaged soldier crouched behind a wet hedgerow in the rain.",
                   "motion": "Rain falls while he turns his head to scan the sky. At the end he looks up."}
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(fast, "restage", return_value=staging) as restage, \
                patch.object(QueueRunner, "_still_replacement", return_value=False):
            result, backend, _ = self._run(
                folder, reviewer=lambda shot: shot.id != "shot-002" or "Restaged" in shot.subject_action)
            shot = result.shots[1]
            self.assertEqual(1, restage.call_count)
            self.assertEqual("minimax", shot.backend)
            self.assertFalse(shot.degraded)
            self.assertIn("Restaged", shot.prompt)
            self.assertTrue(all(attempt.get("superseded") for attempt in shot.attempts[:-1]))
            self.assertTrue(any(e["event"] == "shot_restaged_after_failure" for e in result.events))
            self.assertEqual(5, sum(1 for shot_id, _ in backend.calls if shot_id == "shot-002"))

    def test_the_budget_allows_every_shot_a_clip(self):
        with patch.dict(os.environ, {"LOCAL_VIDEO_BUDGET_MINUTES": ""}):
            del os.environ["LOCAL_VIDEO_BUDGET_MINUTES"]
            self.assertEqual(100 * 60, fast.budget_seconds())
            with patch.dict(os.environ, {"LOCAL_VIDEO_PLANNED_STILLS": "1"}):
                self.assertEqual(55 * 60, fast.budget_seconds())


class BudgetTests(unittest.TestCase):
    def test_motion_budget_holds_one_clip_back_for_a_retake(self):
        self.assertEqual(9, fast.motion_budget(22, 2050, 205))
        self.assertEqual(0, fast.motion_budget(22, 100, 205))
        self.assertEqual(22, fast.motion_budget(22, 10 ** 6, 205))

    def test_clip_cost_learns_from_this_projects_takes(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder)
            project = create_project("desert city", 60, "35mm", "auto", narration_enabled=False,
                                     config=config, script=sample_script())
            self.assertEqual(205.0, fast.clip_cost(project))
            for shot in project.shots[:4]:
                shot.attempts = [{"backend": "minimax", "generation_seconds": 165.0}]
            self.assertLess(fast.clip_cost(project), 190.0)

    def test_the_heuristic_design_moves_the_hook_and_the_action(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder)
            script = sample_script()
            script["beats"][5]["visual"]["description"] = "A wave of sand surges and crashes over the gate"
            project = create_project("desert city", 60, "35mm", "auto", narration_enabled=False,
                                     config=config, script=script)
            design = fast.heuristic_design(project, 2)
            moving = sorted(shot_id for shot_id, d in design.items() if d["render"] == "motion")
            self.assertEqual(["shot-001", "shot-006"], moving)

    def test_the_pipeline_start_bounds_the_deadline(self):
        with patch.dict(os.environ, {"PIPELINE_STARTED_AT": str(time.time() - 600)}):
            self.assertAlmostEqual(time.time() - 600, fast.pipeline_started(), delta=2)
        with patch.dict(os.environ, {"PIPELINE_STARTED_AT": "garbage"}):
            self.assertAlmostEqual(time.time(), fast.pipeline_started(), delta=2)


if __name__ == "__main__":
    unittest.main()


class DesignedSubjectTests(unittest.TestCase):
    def test_a_designed_frame_anchors_the_recurring_subjects_it_names(self):
        """Word matching never found "The sultan's palace": Zanzibar's palace was a new building every shot."""
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder)
            script = sample_script()
            script["recurring_objects"] = [
                "The sultan's palace: a three-storey white-plastered waterfront palace with carved balconies",
                "British warships: grey steel steam warships with two buff-yellow funnels"]
            project = create_project("zanzibar", 60, "35mm", "auto", narration_enabled=False,
                                     config=config, script=script)
            shot = project.shots[1]
            shot.subject_action = "Wide shot of the white palace from the shore"
            self.assertEqual({}, keyframes.recurring_subjects(project, shot))
            project.settings["fast_design"] = {shot.id: {
                "render": "still", "motion_need": 1, "still_move": "push_in", "source": "designer",
                "frame": "Wide shot from the shore: a three-storey white-plastered palace with carved balconies.",
                "subjects": ["The sultan's palace"]}}
            view = fast.frame_view(project, shot)
            self.assertEqual(["The sultan's palace"], list(keyframes.recurring_subjects(project, view)))
            self.assertNotIn("subjects_shown", shot.continuity)       # the plan itself is untouched


class FastReviewTests(unittest.TestCase):
    def _review(self, folder, scores, fatal=()):
        import cv2
        import numpy as np
        from local_video import visual_review
        clip = Path(folder) / "c.mp4"
        writer = cv2.VideoWriter(str(clip), cv2.VideoWriter_fourcc(*"mp4v"), 30, (36, 64))
        for _ in range(10):
            writer.write(np.zeros((64, 36, 3), dtype=np.uint8))
        writer.release()
        project = create_project("zanzibar", 60, "35mm", "auto", narration_enabled=False,
                                 config=make_test_config(folder), script=sample_script())
        answer = dict(scores, fatal_problems=list(fatal), problems=[], revision_prompt="")
        seen = {}
        with patch.object(visual_review, "review_enabled", return_value=True), \
                patch.object(visual_review.llm, "ask",
                             side_effect=lambda system, prompt, schema, **k: seen.update(p=prompt) or answer):
            return visual_review.review_clip(clip, project.shots[3], None, project), seen["p"]

    def test_natural_motion_that_differs_from_the_plan_passes_in_fast_mode(self):
        """Zanzibar shot-008: a flag rippling gently instead of snapping open was rejected at 7.33."""
        scores = {"visual_match": 6, "continuity": 8, "image_quality": 8, "anatomy": 9, "immersion": 7,
                  "story_progression": 6}
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {"LOCAL_VIDEO_FAST": "1", "LOCAL_VIDEO_ALLOW_QUALITY_FLOOR": "0",
                                         "LOCAL_VIDEO_PLANNED_STILLS": "1"}):
                report, prompt = self._review(folder, scores)
            self.assertTrue(report["valid"])
            self.assertEqual("clean-motion", report["acceptance"])
            self.assertIn("THIS VIDEO CUTS BETWEEN EVERY SHOT", prompt)
            # Without planned stills the pass mark is never lowered: only the viewer-first rule applies.
            with patch.dict(os.environ, {"LOCAL_VIDEO_FAST": "1", "LOCAL_VIDEO_ALLOW_QUALITY_FLOOR": "0",
                                         "LOCAL_VIDEO_PLANNED_STILLS": "0"}):
                report, prompt = self._review(folder, scores)
            self.assertFalse(report["valid"])
            self.assertIn("THIS VIDEO CUTS BETWEEN EVERY SHOT", prompt)
            self.assertNotIn("still photograph", prompt)
            with patch.dict(os.environ, {"LOCAL_VIDEO_FAST": "0", "LOCAL_VIDEO_ALLOW_QUALITY_FLOOR": "0"}):
                report, prompt = self._review(folder, scores)
            self.assertFalse(report["valid"])                      # the classic flow stays strict
            self.assertNotIn("THIS VIDEO CUTS BETWEEN EVERY SHOT", prompt)

    def test_a_weird_clip_still_fails_in_fast_mode(self):
        scores = {name: 8 for name in ("visual_match", "continuity", "image_quality", "anatomy", "immersion",
                                       "story_progression")}
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"LOCAL_VIDEO_FAST": "1"}):
            report, _ = self._review(folder, scores, fatal=["the courtyard morphs into a waterfront"])
            self.assertFalse(report["valid"])
            report, _ = self._review(folder, dict(scores, anatomy=5))
            self.assertFalse(report["valid"])


class BorrowedStillTests(FastModeTests):
    def test_a_still_without_any_keyframe_borrows_its_neighbours_frame_when_no_clip_fits(self):
        """Potsdam shot-011: every keyframe take failed, so it was redrawn mid-clip-phase and made from text."""
        def draw_all_but_shot_5(manifest, config, selected=None, **options):
            on_ready = options.get("on_ready")
            for shot in manifest.shots:
                if shot.index == 4:
                    continue
                path = keyframes.keyframe_path(manifest, shot)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"png")
                path.with_name(f"{shot.id}.hires.png").write_bytes(b"png")
                if on_ready:
                    on_ready(shot.index, path)
            return len(manifest.shots) - 1

        sources = []

        def render(manifest, shot, config, source=None, move=None):
            if source is None and fast.hires_keyframe(manifest, shot) is None:
                return None                           # as the real renderer: nothing to animate
            sources.append((shot.id, Path(source).name if source else None, move))
            return fake_render_still(manifest, shot, config)

        with tempfile.TemporaryDirectory() as folder, \
                patch.object(QueueRunner, "_room_for_one_more_clip", return_value=False), \
                patch.object(queue_module, "prepare_keyframes", side_effect=draw_all_but_shot_5), \
                patch.object(fast, "render_still", side_effect=render):
            config = make_test_config(folder)
            project = create_project("desert city", 60, "35mm", "auto", narration_enabled=False,
                                     config=config, script=sample_script())
            backend = FakeMiniMax(config)
            runner = QueueRunner(config, {"minimax": backend}, validator=fake_validator,
                                 extractor=fake_extractor, visual_reviewer=lambda *a: {"valid": True},
                                 assembler=lambda m, *a: {"video": "final.mp4"},
                                 final_reviewer=lambda *a: {"valid": True})
            with patch.object(QueueRunner, "_prepare_minimax"), \
                    patch.object(fast, "motion_budget", return_value=1), \
                    patch("local_video.validation.ffprobe", return_value={}), \
                    patch("local_video.validation.media_metadata", return_value={"duration": 3.5}), \
                    patch("local_video.queue.validate_final", return_value={"valid": True}):
                result = runner.run(project)
            shot = result.shots[4]
            self.assertEqual("still", shot.backend)
            self.assertEqual("still", shot.degraded)
            borrowed = [s for s in sources if s[0] == shot.id]
            self.assertEqual("shot-004.hires.png", borrowed[0][1])          # its nearest neighbour's frame
            self.assertNotIn(shot.id, [call[0] for call in backend.calls])  # no clip from text


class RetakePolicyTests(FastModeTests):
    def test_planned_clips_go_before_any_retake(self):
        """Pig run: retakes passed no more often than first takes and pushed three planned clips into stills."""
        with tempfile.TemporaryDirectory() as folder:
            verdicts = iter([False, True, True])     # shot-001 rejected; the later clips pass first time
            result, backend, _ = self._run(folder, motion=2, reviewer=lambda shot: next(verdicts))
            rendered = [shot_id for shot_id, _ in backend.calls]
            self.assertEqual(1, rendered.count("shot-001"))            # no retake while a clip waited
            self.assertEqual("still", result.shots[0].backend)
