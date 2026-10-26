import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.script import build_script_tool
from local_video.assembly import (
    authored_effect_times,
    build_ambience_command,
    build_final_command,
    build_mix_command,
    build_video_command,
)
from local_video.backends import BackendAdapter, GenerationResult, _remove_generated_audio
from local_video.config import PipelineConfig, resolve_within
from local_video.models import ProjectManifest, Shot
from local_video.planner import QUALITY_BAN, allocate_frames, allocate_story_frames, plan_shots, shot_count_for_duration
from local_video.project import create_project, refresh_project_from_shot, replan_project
from local_video.preflight import run_preflight
from local_video.queue import FileLock, QueueBusyError, QueueRunner, _retake_prompt
from local_video.validation import ffprobe, media_metadata, validate_clip, validate_final
from local_video.visual_review import review_clip, review_final_video


def make_test_config(root, **values):
    defaults = dict(
        discover_services=False,
        output_root=Path(root),
        minimax_url="http://minimax.invalid",
        wan_url="http://wan.invalid",
        retry_limit=2,
        fallback_failures=1,
        generation_timeout=60,
        poll_seconds=0.01,
        ffmpeg="ffmpeg",
        ffprobe="ffprobe",
    )
    defaults.update(values)
    return PipelineConfig(**defaults)


def sample_script():
    return {
        "video_title": "A city that wakes under the desert",
        "spoken_script": " ".join(
            f"Moment {i} reveals another consequence in the same unfolding mystery."
            for i in range(1, 21)
        ),
        "beats": [
            {"text": f"Beat {i}", "visual": {"description": f"The explorer opens chamber {i}"}}
            for i in range(1, 21)
        ],
    }


class PlanningTests(unittest.TestCase):
    def test_duration_and_shot_count(self):
        self.assertEqual(shot_count_for_duration(60), 20)
        self.assertEqual(shot_count_for_duration(90), 30)
        self.assertEqual(sum(allocate_frames(60, 20)), 1800)
        self.assertEqual(sum(allocate_frames(90, 30)), 2700)
        with self.assertRaises(ValueError):
            shot_count_for_duration(29)

    def test_story_frame_allocation_is_dynamic_and_exact(self):
        frames = allocate_story_frames(30, ["tiny hook"] + ["a much longer narrated story beat here"] * 8 + ["payoff"])
        self.assertEqual(sum(frames), 900)
        self.assertTrue(all(75 <= value <= 120 for value in frames))
        self.assertGreater(len(set(frames)), 1)

    def test_shot_plan_is_exact_and_self_contained(self):
        shots, continuity = plan_shots(sample_script(), "desert city", 60, "35mm nocturne", "auto")
        self.assertEqual(len(shots), 20)
        self.assertEqual(sum(shot.duration_frames for shot in shots), 1800)
        self.assertTrue(all(75 <= shot.duration_frames <= 120 for shot in shots))
        self.assertIn(QUALITY_BAN, shots[0].prompt)
        self.assertIn("Camera:", shots[0].prompt)
        self.assertIn("Dialogue: none", shots[0].prompt)
        self.assertIn("Narration: none", shots[0].prompt)
        self.assertIn("CURRENT RENDER TASK — SHOT 01 OF 20", shots[0].prompt)
        self.assertIn("SINGLE-SHOT CONTINUITY LOCK", shots[0].prompt)
        self.assertIn("CURRENT SHOT (the only event to render)", shots[0].prompt)
        self.assertNotIn("NEXT SHOT", shots[0].prompt)
        self.assertIn("WHOLE-STORY CONTRACT", shots[0].prompt)
        self.assertNotIn("FULL VISUAL SCREENPLAY", shots[0].prompt)
        self.assertNotIn("Beat 20", shots[0].prompt)
        self.assertLess(len(shots[0].prompt), 6000)
        self.assertNotIn("Story beat:", shots[0].prompt)
        self.assertNotIn("license plate", shots[0].prompt.lower())
        self.assertEqual(shots[0].continuity, continuity)

    def test_local_ai_script_schema_requires_full_screenplay_fields(self):
        schema = build_script_tool(20, 100, 150, "local-ai")["input_schema"]
        required = set(schema["required"])
        self.assertTrue({
            "story_premise", "protagonist_goal", "stakes", "ending_payoff",
            "characters", "location", "recurring_objects",
        }.issubset(required))
        visual = schema["properties"]["beats"]["items"]["properties"]["visual"]
        self.assertEqual(schema["properties"]["beats"]["minItems"], 20)
        self.assertEqual(schema["properties"]["beats"]["maxItems"], 20)
        self.assertEqual(visual["properties"]["kind"]["enum"], ["scene"])
        self.assertIn("continuity_in", visual["required"])
        self.assertIn("continuity_out", visual["required"])

    def test_diagram_instructions_never_reach_video_prompt(self):
        script = sample_script()
        script["beats"][5]["visual"] = {
            "kind": "diagram",
            "description": "Stat card reading '3 Pulses' with large numbers",
        }
        shots, _ = plan_shots(script, "desert city", 60, "35mm nocturne", "auto")
        self.assertNotIn("card reading", shots[5].prompt.lower())
        self.assertNotIn("3 pulses", shots[5].prompt.lower())

    def test_explicit_screenplay_framing_overrides_rotating_presets(self):
        script = sample_script()
        script["beats"][3]["visual"]["description"] = "Low angle wide shot looking up at the diver."
        script["beats"][4]["visual"]["description"] = "Extreme close-up on her wrist computer."
        shots, _ = plan_shots(script, "desert city", 60, "cinematic", "auto")
        self.assertEqual(shots[3].camera_action, "slow low-angle drift")
        self.assertIn("24mm low-angle wide frame", shots[3].prompt)
        self.assertEqual(shots[4].camera_action, "controlled macro push-in")
        self.assertIn("macro detail shot", shots[4].prompt)


class PathTests(unittest.TestCase):
    def test_safe_project_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertEqual(resolve_within(root, "shots/one.mp4"), root / "shots" / "one.mp4")
            with self.assertRaises(ValueError):
                resolve_within(root, "../escape.mp4")
            with self.assertRaises(ValueError):
                resolve_within(root, root / "absolute.mp4")


class FakeBackend(BackendAdapter):
    def __init__(self, config, name, outcomes):
        super().__init__(config)
        self.name = name
        self.outcomes = list(outcomes)
        self.calls = 0
        self.prompts = []

    def available(self):
        return True, "fake"

    def generate(self, shot, target, reference_image=None, on_submitted=None):
        self.calls += 1
        self.prompts.append(shot.prompt)
        if on_submitted:
            on_submitted(f"fake-{self.name}-{self.calls}")
        outcome = self.outcomes.pop(0) if self.outcomes else "ok"
        if outcome != "ok":
            raise RuntimeError(outcome)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"fake-video")
        return GenerationResult(target, self.name, f"p-{self.calls}", 1.0, self.name, {"fake": True})


def fake_validator(path, config, width, height, seconds):
    return {
        "valid": True, "duration": seconds, "width": width, "height": height,
        "fps": 24, "frame_count": max(8, round(seconds * 24)), "has_audio": False,
    }


def fake_extractor(path, target, config):
    return Path(target)


def fake_visual_reviewer(*args, **kwargs):
    return {"valid": True, "problems": [], "fatal_problems": [], "revision_prompt": ""}


class QueueTests(unittest.TestCase):
    def _project(self, folder, config):
        project = create_project(
            "desert city", 60, "35mm nocturne", "auto", narration_enabled=False,
            config=config, script=sample_script(),
        )
        screenplay = Path(project.project_dir) / project.settings["screenplay"]
        self.assertTrue(screenplay.is_file())
        self.assertIn("FULL VISUAL SCREENPLAY", screenplay.read_text(encoding="utf-8"))
        return project

    def test_global_queue_serialization(self):
        with tempfile.TemporaryDirectory() as folder:
            lock = Path(folder) / ".gpu-generation.lock"
            with FileLock(lock):
                with self.assertRaises(QueueBusyError):
                    with FileLock(lock):
                        pass

    def test_backend_fallback_is_recorded(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder, retry_limit=1, fallback_failures=1)
            project = self._project(folder, config)
            minimax = FakeBackend(config, "minimax", ["h3 failed"])
            wan = FakeBackend(config, "wan", ["ok"])
            runner = QueueRunner(config, {"minimax": minimax, "wan": wan}, validator=fake_validator,
                                 extractor=fake_extractor, visual_reviewer=fake_visual_reviewer)
            result = runner.run(project, shots={1})
            self.assertEqual(result.shots[0].status, "accepted")
            self.assertEqual(result.shots[0].backend, "wan")
            self.assertTrue(any(event["event"] == "backend_fallback" for event in result.events))
            self.assertEqual(minimax.calls, 1)
            self.assertEqual(wan.calls, 1)

    def test_retry_limit_is_finite(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder, retry_limit=2, fallback_failures=9)
            project = self._project(folder, config)
            minimax = FakeBackend(config, "minimax", ["bad", "bad", "bad", "bad"])
            wan = FakeBackend(config, "wan", [])
            result = QueueRunner(config, {"minimax": minimax, "wan": wan}, validator=fake_validator,
                                 extractor=fake_extractor).run(project, shots={1})
            self.assertEqual(minimax.calls, 3)
            self.assertEqual(result.shots[0].status, "failed")
            self.assertEqual(len(result.shots[0].attempts), 3)

    def test_cuda_failure_does_not_consume_creative_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder, retry_limit=0, fallback_failures=1)
            project = self._project(folder, config)
            minimax = FakeBackend(config, "minimax", ["CUDA error: unspecified launch failure"])
            wan = FakeBackend(config, "wan", ["ok"])
            result = QueueRunner(
                config, {"minimax": minimax, "wan": wan}, validator=fake_validator,
                extractor=fake_extractor, visual_reviewer=fake_visual_reviewer,
            ).run(project, shots={1})
            self.assertEqual(result.shots[0].status, "accepted")
            self.assertEqual(minimax.calls, 1)
            self.assertEqual(wan.calls, 1)
            self.assertTrue(any(event["event"] == "infrastructure_retry" for event in result.events))

    def test_resume_skips_successful_shots(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder, retry_limit=0)
            project = self._project(folder, config)
            first = Path(project.project_dir) / "shots" / "shot-001.mp4"
            first.write_bytes(b"already-done")
            project.shots[0].status = "accepted"
            project.shots[0].output = str(first.relative_to(project.project_dir))
            project.save()
            minimax = FakeBackend(config, "minimax", ["ok"])
            wan = FakeBackend(config, "wan", [])
            result = QueueRunner(config, {"minimax": minimax, "wan": wan}, validator=fake_validator,
                                 extractor=fake_extractor, visual_reviewer=fake_visual_reviewer).run(
                project, shots={1, 2}
            )
            self.assertEqual(minimax.calls, 1)
            self.assertEqual(Path(result.shots[0].output), Path("shots/shot-001.mp4"))
            self.assertEqual(result.shots[1].status, "accepted")

    def test_visual_rejection_revises_retry_prompt(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder, retry_limit=1, fallback_failures=9)
            project = self._project(folder, config)
            minimax = FakeBackend(config, "minimax", ["ok", "ok"])
            wan = FakeBackend(config, "wan", [])
            reviews = iter([
                {"valid": False, "problems": ["wrong opening location"], "fatal_problems": [],
                 "revision_prompt": "Stay underwater and show only chamber one."},
                {"valid": True, "problems": [], "fatal_problems": [], "revision_prompt": ""},
            ])
            runner = QueueRunner(
                config, {"minimax": minimax, "wan": wan}, validator=fake_validator,
                extractor=fake_extractor, visual_reviewer=lambda *args: next(reviews),
            )
            result = runner.run(project, shots={1})
            self.assertEqual(result.shots[0].status, "accepted")
            self.assertEqual(minimax.calls, 2)
            self.assertNotIn("DIRECTOR'S RETAKE", minimax.prompts[0])
            self.assertTrue(minimax.prompts[1].startswith("DIRECTOR'S RETAKE"))
            self.assertIn("Stay underwater and show only chamber one", minimax.prompts[1])

    def test_retake_prompt_leaves_continuity_frame_and_targets_payoff(self):
        shot = Shot(
            id="shot-003", index=2, duration_frames=90, prompt="BASE PROMPT",
            negative_prompt="n", seed=1,
            subject_action="Mara reaches the archway. Close on her intact mask.",
            camera_action="smooth push-in",
        )
        prompt = _retake_prompt(shot, "Keep the regulator visible.", has_reference=True)
        self.assertIn("leave its camera composition immediately", prompt)
        self.assertIn("REQUIRED END-FRAME PAYOFF: Close on her intact mask.", prompt)
        self.assertIn("Keep the regulator visible", prompt)
        self.assertTrue(prompt.endswith("BASE PROMPT"))

    def test_replan_archives_old_clips_and_keeps_full_screenplay(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder)
            project = self._project(folder, config)
            old_clip = Path(project.project_dir) / "shots" / "shot-001-old.mp4"
            old_clip.write_bytes(b"old")
            project.shots[0].status = "accepted"
            project.shots[0].output = str(old_clip.relative_to(project.project_dir))
            project.save()
            replanned = replan_project(project.project_dir, config)
            self.assertTrue(all(shot.status == "pending" for shot in replanned.shots))
            self.assertEqual(replanned.state, "queued")
            self.assertFalse(old_clip.exists())
            archives = list((Path(project.project_dir) / "superseded").glob(
                "replan-*/shots/shot-001-old.mp4"
            ))
            self.assertEqual(len(archives), 1)
            screenplay = (Path(project.project_dir) / "screenplay.txt").read_text(encoding="utf-8")
            self.assertIn("VOICEOVER REFERENCE (never speak or display): Beat 20", screenplay)
            self.assertNotIn("Beat 20", replanned.shots[0].prompt)

    def test_refresh_from_shot_preserves_earlier_acceptance(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder)
            project = self._project(folder, config)
            kept = Path(project.project_dir) / "shots" / "shot-001.mp4"
            replaced = Path(project.project_dir) / "shots" / "shot-004.mp4"
            kept.write_bytes(b"keep")
            replaced.write_bytes(b"replace")
            project.shots[0].status = "accepted"
            project.shots[0].output = str(kept.relative_to(project.project_dir))
            project.shots[3].status = "accepted"
            project.shots[3].output = str(replaced.relative_to(project.project_dir))
            project.save()
            refreshed = refresh_project_from_shot(project.project_dir, 4, config)
            self.assertEqual(refreshed.state, "paused")
            self.assertEqual(refreshed.shots[0].status, "accepted")
            self.assertTrue(kept.is_file())
            self.assertEqual(refreshed.shots[3].status, "pending")
            self.assertFalse(replaced.exists())
            self.assertTrue(list((Path(project.project_dir) / "superseded").glob(
                "refresh-from-004-*/shots/shot-004.mp4"
            )))


class ValidationTests(unittest.TestCase):
    def test_visual_review_is_fail_closed_unless_explicitly_overridden(self):
        manifest = ProjectManifest(
            id="test", concept="test", duration_seconds=60, visual_style="film",
            preferred_backend="auto", project_dir=".", script={},
        )
        shot = Shot(id="shot-001", index=0, duration_frames=90, prompt="p",
                    negative_prompt="n", seed=1)
        with patch.dict(os.environ, {"LOCAL_VIDEO_VISION_QC": "0", "LOCAL_VIDEO_ALLOW_QC_SKIP": "0"}):
            self.assertFalse(review_clip("missing.mp4", shot, None, manifest)["valid"])
            self.assertFalse(review_final_video("missing.mp4", manifest)["valid"])
        with patch.dict(os.environ, {"LOCAL_VIDEO_VISION_QC": "0", "LOCAL_VIDEO_ALLOW_QC_SKIP": "1"}):
            self.assertTrue(review_clip("missing.mp4", shot, None, manifest)["valid"])

    def test_preflight_rejects_when_no_video_backend_is_available(self):
        class MissingBackend:
            @staticmethod
            def available():
                return False, "offline"

        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder)
            manifest = ProjectManifest(
                id="test", concept="test", duration_seconds=60, visual_style="film",
                preferred_backend="auto", project_dir=folder, narration_enabled=False,
            )
            with patch("local_video.preflight._tool_ok", return_value=True):
                with self.assertRaisesRegex(RuntimeError, "No configured video backend"):
                    run_preflight(
                        manifest, config, {"minimax": MissingBackend(), "wan": MissingBackend()},
                        require_visual_qc=False,
                    )

    def test_minimax_output_audio_is_physically_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder)
            source = Path(folder) / "generated-with-audio.mp4"
            subprocess.run([
                config.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=blue:s=544x960:r=24:d=0.5",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=0.5",
                "-c:v", "libx264", "-c:a", "aac", "-shortest", str(source),
            ], check=True)
            self.assertTrue(media_metadata(ffprobe(source, config))["has_audio"])
            _remove_generated_audio(source, config.ffmpeg)
            self.assertFalse(media_metadata(ffprobe(source, config))["has_audio"])

    def test_ffprobe_rejects_corrupt_media(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder)
            source = Path(folder) / "bad.mp4"
            source.write_bytes(b"not-a-video")
            completed = subprocess.CompletedProcess([], 1, "", "invalid data")
            with patch("local_video.validation.subprocess.run", return_value=completed):
                with self.assertRaisesRegex(ValueError, "FFprobe rejected"):
                    ffprobe(source, config)

    def test_validation_checks_dimensions_and_motion(self):
        probe = {
            "streams": [{
                "codec_type": "video", "width": 544, "height": 960, "avg_frame_rate": "24/1",
                "nb_read_frames": "72", "codec_name": "h264", "duration": "3.0",
            }],
            "format": {"duration": "3.0"},
        }
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder)
            source = Path(folder) / "clip.mp4"
            source.write_bytes(b"video")
            with patch("local_video.validation.ffprobe", return_value=probe), patch(
                "local_video.validation.motion_metrics",
                return_value={"black_ratio": 0.0, "frozen_ratio": 0.0, "motion_score": 2.0, "samples": 12},
            ):
                report = validate_clip(source, config, 544, 960, 3.0)
                self.assertTrue(report["valid"])
                with self.assertRaisesRegex(ValueError, "wrong size"):
                    validate_clip(source, config, 320, 576, 3.0)

    def test_final_rejects_multiple_audio_streams(self):
        probe = {
            "streams": [
                {"codec_type": "video", "width": 1080, "height": 1920, "avg_frame_rate": "30/1",
                 "nb_read_frames": "1800", "codec_name": "h264", "duration": "60"},
                {"codec_type": "audio", "codec_name": "aac"},
                {"codec_type": "audio", "codec_name": "aac"},
            ],
            "format": {"duration": "60"},
        }
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder)
            video = Path(folder) / "final.mp4"
            video.write_bytes(b"video")
            with patch("local_video.validation.ffprobe", return_value=probe):
                with self.assertRaisesRegex(ValueError, "exactly 1 / 1"):
                    validate_final(video, config, 60)


class AssemblyTests(unittest.TestCase):
    def test_scene_cuts_do_not_create_automatic_whooshes(self):
        manifest = ProjectManifest(
            id="test", concept="test", duration_seconds=60, visual_style="film",
            preferred_backend="auto", project_dir=".",
        )
        self.assertEqual(authored_effect_times(manifest), ([], []))
        manifest.settings["sound_effects"] = [
            {"type": "whoosh", "time": 12.5},
            {"type": "pop", "time": 30},
            {"type": "whoosh", "time": 99},
        ]
        self.assertEqual(authored_effect_times(manifest), ([12.5], [30.0]))

    def test_generated_clip_audio_is_never_used_as_ambience(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder)
            shot = Shot(
                id="shot-001", index=0, duration_frames=1800, prompt="p",
                negative_prompt="n", seed=1, status="accepted",
                output="shots/with-native-voice.mp4",
                validation={"duration": 60.0, "has_audio": True},
            )
            manifest = ProjectManifest(
                id="test", concept="test", duration_seconds=60, visual_style="film",
                preferred_backend="auto", project_dir=folder, shots=[shot],
            )
            command = build_ambience_command(manifest, Path(folder) / "ambience.wav", config)
            self.assertIn("anullsrc=r=48000:cl=stereo", command)
            self.assertNotIn(str(Path(folder) / shot.output), command)

    def test_mix_does_not_create_unconnected_sidechain_without_music(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder)
            manifest = ProjectManifest(
                id="test", concept="test", duration_seconds=60, visual_style="film",
                preferred_backend="auto", project_dir=folder,
            )
            command = build_mix_command(
                manifest,
                Path(folder) / "ambience.wav",
                Path(folder) / "effects.wav",
                Path(folder) / "mix.m4a",
                config,
                narration=Path(folder) / "narration.wav",
            )
            graph = command[command.index("-filter_complex") + 1]
            self.assertIn("apad=whole_dur=60.000000[narr]", graph)
            self.assertNotIn("asplit", graph)
            self.assertNotIn("[side]", graph)

    def test_mix_creates_sidechain_when_music_is_present(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder)
            manifest = ProjectManifest(
                id="test", concept="test", duration_seconds=60, visual_style="film",
                preferred_backend="auto", project_dir=folder,
            )
            command = build_mix_command(
                manifest,
                Path(folder) / "ambience.wav",
                Path(folder) / "effects.wav",
                Path(folder) / "mix.m4a",
                config,
                narration=Path(folder) / "narration.wav",
                music=Path(folder) / "music.wav",
            )
            graph = command[command.index("-filter_complex") + 1]
            self.assertIn("asplit=2[narr][side]", graph)
            self.assertIn("[music][side]sidechaincompress", graph)

    def test_ffmpeg_command_has_exact_timeline_and_delivery_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder)
            frames = allocate_frames(60, 20)
            shots = []
            for index, duration_frames in enumerate(frames):
                shots.append(Shot(
                    id=f"shot-{index + 1:03d}", index=index, duration_frames=duration_frames,
                    prompt="p", negative_prompt="n", seed=index, status="accepted",
                    output=f"shots/{index}.mp4", validation={"duration": 3.0},
                    transition="crossfade" if index == 4 else "cut",
                ))
            manifest = ProjectManifest(
                id="test", concept="test", duration_seconds=60, visual_style="film",
                preferred_backend="auto", project_dir=folder, shots=shots,
            )
            command = build_video_command(manifest, Path(folder) / "assembled.mp4", config)
            joined = " ".join(command)
            self.assertIn("xfade=transition=fade", joined)
            self.assertIn("scale=1080:1920", joined)
            self.assertIn("60.000000", joined)
            self.assertIn("libx264", command)
            final = build_final_command(
                Path(folder) / "video.mp4", Path(folder) / "audio.m4a",
                Path(folder) / "final.mp4", 60, config,
            )
            self.assertIn("aac", final)
            self.assertIn("30", final)


if __name__ == "__main__":
    unittest.main()
