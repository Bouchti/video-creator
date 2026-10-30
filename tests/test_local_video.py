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
    snap_to_script,
    speech_frames,
)
from local_video.backends import BackendAdapter, GenerationResult, _remove_generated_audio, build_backends
from local_video.config import PipelineConfig, resolve_within
from local_video.models import ProjectManifest, Shot, estimated_remaining_seconds
from local_video.planner import (
    QUALITY_BAN, allocate_frames, allocate_story_frames, continuation_source, plan_shots,
    shot_count_for_duration,
)
from local_video.project import (
    create_project, project_status, refresh_project_from_shot, replan_project, reset_shot,
)
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

    def test_each_shot_only_sees_the_look_of_its_beat(self):
        script = sample_script()
        script["characters"] = [{
            "name": "Wojtek", "look": "tiny chocolate-brown bear cub",
            "look_changes": [{"from_beat": 11, "look": "huge adult tawny bear"}],
        }]
        shots, _ = plan_shots(script, "desert city", 60, "35mm nocturne", "auto")
        self.assertIn("tiny chocolate-brown bear cub", shots[0].prompt)
        self.assertNotIn("adult", shots[0].prompt)
        self.assertIn("huge adult tawny bear", shots[-1].prompt)
        self.assertNotIn("cub", shots[-1].prompt)
        self.assertIn("cub", shots[0].continuity["characters"])

    def test_shot_only_lists_characters_its_beat_names(self):
        script = sample_script()
        script["beats"][0]["visual"]["description"] = "Piotr kneels beside Wojtek"
        script["beats"][1]["visual"]["description"] = "The Major pins a badge on Wojtek"
        script["beats"][2]["visual"]["description"] = "An empty depot at dawn"
        script["characters"] = [
            {"name": "Wojtek", "look": "adult brown bear"},
            {"name": "Piotr", "look": "lean soldier, no headgear"},
            {"name": "The Major", "look": "stocky officer, peaked cap, medals"},
        ]
        shots, _ = plan_shots(script, "desert city", 60, "35mm nocturne", "auto")
        self.assertNotIn("peaked cap", shots[0].prompt)
        self.assertIn("lean soldier", shots[0].prompt)
        self.assertIn("peaked cap", shots[1].prompt)
        self.assertNotIn("lean soldier", shots[1].prompt)
        # Nobody named: no lead is added (the whole cast once posed in a crowd shot).
        self.assertNotIn("peaked cap", shots[2].prompt)
        self.assertNotIn("lean soldier", shots[2].prompt)
        self.assertIn("None of the story's named characters", shots[2].prompt)
        self.assertIn("Exactly 2 named characters (Wojtek, Piotr), each appearing once", shots[0].prompt)
        self.assertEqual(shots[0].cast, ["Wojtek", "Piotr"])
        self.assertEqual(shots[2].cast, [])

    def test_unnamed_cast_scripts_keep_the_whole_cast(self):
        script = sample_script()
        script["characters"] = [{"name": "Mira", "look": "red raincoat"}]
        shots, _ = plan_shots(script, "desert city", 60, "35mm nocturne", "auto")
        self.assertIn("red raincoat", shots[2].prompt)
        self.assertNotIn("ON SCREEN", shots[2].prompt)

    def test_shots_open_on_the_latest_frame_of_the_same_place_and_light(self):
        script = sample_script()
        places = ["cliff", "cliff", "plain", "plain", "cliff", "cliff", "cliff"] + ["plain"] * 13
        lights = ["dawn sun"] * 4 + ["midday sun", "midday sun", "total eclipse darkness"] + ["total eclipse darkness"] * 13
        for beat, place, light in zip(script["beats"], places, lights):
            beat["visual"].update(scene=place, light=light)
        shots, _ = plan_shots(script, "desert city", 60, "35mm epic, golden light that cuts to total eclipse darkness", "auto")
        labels = [(s.scene, s.light) for s in shots]
        self.assertEqual([continuation_source(labels, i) for i in range(8)], [None, 0, None, 2, None, 4, None, None])
        # The light is the shot's own, and the style line about the later eclipse stays out of dawn.
        self.assertIn("Light: dawn sun, held steady", shots[0].prompt)
        self.assertNotIn("eclipse", shots[0].prompt.lower())
        self.assertIn("total eclipse darkness", shots[6].prompt)
        self.assertEqual(shots[0].scene, "cliff")

    def test_returning_to_a_place_reopens_on_its_last_frame(self):
        with tempfile.TemporaryDirectory() as folder:
            manifest = create_project("desert city", 60, "cinematic", "auto", script=sample_script(),
                                      config=make_test_config(folder))
            for shot, (scene, light) in zip(manifest.shots, [("cliff", "dawn"), ("plain", "dawn"), ("cliff", "dawn")]):
                shot.scene, shot.light = scene, light
            frame = Path(manifest.project_dir) / "shots" / "shot-001-last.jpg"
            frame.parent.mkdir(parents=True, exist_ok=True)
            frame.write_bytes(b"jpg")
            manifest.shots[0].last_frame = "shots/shot-001-last.jpg"
            manifest.shots[1].last_frame = "shots/shot-001-last.jpg"
            runner = QueueRunner(make_test_config(folder))
            self.assertIsNone(runner._reference_for(manifest, 1))
            self.assertEqual(runner._reference_for(manifest, 2).resolve(), frame.resolve())

    def test_a_return_needs_the_same_cast_and_keeps_screen_sides(self):
        script = sample_script()
        script["characters"] = [{"name": "Karan", "look": "crimson tunic"}, {"name": "Darios", "look": "indigo tunic"}]
        script["screen_geography"] = "Karan's army frame left facing right; Darios' army frame right facing left"
        cast = ["Karan charges", "Darios charges", "Karan and Darios's armies converge"] + ["The river"] * 17
        places = ["river", "bank", "river"] + ["valley"] * 17
        for beat, text, place in zip(script["beats"], cast, places):
            beat["visual"].update(description=text, scene=place, light="midday sun")
        shots, _ = plan_shots(script, "desert city", 60, "cinematic", "auto")
        labels, casts = [(s.scene, s.light) for s in shots], [s.cast for s in shots]
        self.assertIsNone(continuation_source(labels, 2, casts))
        self.assertEqual(continuation_source(labels, 2), 0)
        self.assertIn("Screen geography: Karan's army frame left", shots[2].prompt)

    def test_captions_spell_names_as_the_script_does(self):
        heard = [{"text": t, "start": i, "end": i + 1} for i, t in
                 enumerate(["Kharan", "wades", "uh", "forward,", "Darius", "walks."])]
        words = snap_to_script(heard, "Karan wades forward, Darios walks.")
        self.assertEqual([w["text"] for w in words], ["Karan", "wades", "uh", "forward,", "Darios", "walks."])
        self.assertEqual([w["start"] for w in words], list(range(6)))

    def test_each_shot_starts_when_its_sentence_is_spoken(self):
        beats = ["Fire spreads fast.", "Heat melts pottery to glass.", "Boudica watches."]
        heard = [{"text": t, "start": s, "end": s + 0.4} for t, s in
                 [("Fire", 0.1), ("spreads", 0.5), ("fast.", 0.9), ("Heat", 2.5), ("melts", 2.9),
                  ("pottery", 3.3), ("to", 3.7), ("glass.", 4.0), ("Boudica", 6.0), ("watches.", 6.5)]]
        frames = speech_frames(heard, beats, 9.0)
        self.assertEqual(sum(frames), 270)
        self.assertEqual(frames[0], round((2.5 - 0.12) * 30))  # cut lands on "Heat"
        self.assertEqual(sum(frames[:2]), round((6.0 - 0.12) * 30))  # and on "Boudica"
        self.assertIsNone(speech_frames([], beats, 9.0))

    def test_a_shot_is_never_timed_longer_than_its_clip_can_fill(self):
        beats = ["Fire spreads.", "Heat melts pottery to glass.", "Boudica watches."]
        heard = [{"text": t, "start": s, "end": s + 0.4} for t, s in
                 [("Fire", 0.1), ("spreads.", 0.5), ("Heat", 4.8), ("melts", 5.2), ("pottery", 5.6),
                  ("to", 6.0), ("glass.", 6.4), ("Boudica", 8.0), ("watches.", 8.5)]]
        # Voice alone gives the first shot 4.68 s; its 3.04 s clip fills only 3.33 s.
        self.assertGreater(speech_frames(heard, beats, 11.0)[0], 4.6 * 30)
        frames = speech_frames(heard, beats, 11.0, longest=[3.33, 4.1, 4.1])
        self.assertEqual(sum(frames), 330)
        self.assertLessEqual(frames[0], round(3.33 * 30))
        self.assertTrue(all(f <= round(4.1 * 30) for f in frames))
        # Clips that cannot cover the voice together: fall back to the voice, never fail.
        self.assertEqual(speech_frames(heard, beats, 11.0, longest=[3.0, 3.0, 3.0]),
                         speech_frames(heard, beats, 11.0))

    def test_a_scene_never_sees_another_scenes_world(self):
        script = sample_script()
        for i, beat in enumerate(script["beats"]):
            beat["visual"]["scene"] = "londinium settlement" if i < 10 else "excavation trench"
            beat["visual"]["light"] = "orange firelight" if i < 10 else "overcast daylight"
        script["location"] = ("In 60 AD the Roman settlement of Londinium: thatched halls by the Thames. "
                              "Two thousand years later a modern excavation trench with a vivid orange band.")
        script["color_palette"] = "amber-orange for the settlement, cool grey with an orange accent for the excavation"
        script["recurring_objects"] = ["The orange ash layer: a ten-inch band in the trench wall"]
        script["characters"] = [{"name": "Boudica", "look": "blue cloak"}, {"name": "Cara", "look": "tan vest"}]
        script["screen_geography"] = "Boudica always moves frame left to right; Cara faces the trench wall."
        script["beats"][0]["visual"]["description"] = "Orange flames climb the thatch as Boudica watches"
        script["beats"][15]["visual"]["description"] = "Cara brushes the orange layer in the trench wall"
        shots, _ = plan_shots(script, "london", 60, "cinematic", "auto")
        fire, dig = shots[0].continuity, shots[15].continuity
        self.assertNotIn("trench", fire["location"] + fire["screen_geography"] + fire["palette"])
        self.assertIn("Londinium", fire["location"])
        self.assertEqual(fire["recurring_objects"], "")  # "orange flames" is not the ash layer
        self.assertIn("trench", dig["location"])
        self.assertNotIn("thatched", dig["location"])
        self.assertIn("ash layer", dig["recurring_objects"])
        self.assertNotIn("Boudica", dig["screen_geography"])  # she is never at the dig
        self.assertIn("Boudica", fire["screen_geography"])

    def test_recurring_objects_only_reach_the_beats_that_show_them(self):
        script = sample_script()
        script["recurring_objects"] = ["Eclipse corona — silver ring in a black sky", "Thales's scroll — tan papyrus"]
        script["beats"][0]["visual"]["description"] = "Thales unrolls his scroll on the cliff"
        script["beats"][19]["visual"]["description"] = "The eclipse corona blazes above Thales"
        shots, _ = plan_shots(script, "desert city", 60, "cinematic", "auto")
        self.assertNotIn("corona", shots[0].continuity["recurring_objects"])
        self.assertIn("papyrus", shots[0].continuity["recurring_objects"])
        self.assertIn("corona", shots[-1].continuity["recurring_objects"])

    def test_first_take_prompt_states_the_end_state(self):
        script = sample_script()
        script["beats"][0]["visual"]["description"] = "The cub sniffs the crate. He lifts it onto his back."
        script["beats"][0]["visual"]["continuity_out"] = "The crate balanced on the cub's back"
        shots, _ = plan_shots(script, "desert city", 60, "35mm nocturne", "auto")
        self.assertIn("He lifts it onto his back. By the end of the clip: The crate balanced on the cub's back.",
                      shots[0].prompt)

    def test_shot_plan_is_exact_and_self_contained(self):
        shots, continuity = plan_shots(sample_script(), "desert city", 60, "35mm nocturne", "auto")
        self.assertEqual(len(shots), 20)
        self.assertEqual(sum(shot.duration_frames for shot in shots), 1800)
        self.assertTrue(all(75 <= shot.duration_frames <= 120 for shot in shots))
        # MiniMax H3's trained layout: a [Shot 1] description, then the sound and music sections.
        self.assertTrue(shots[0].prompt.startswith("integrated_multimodal_description: [Shot 1] Live-action"))
        self.assertIn("\n\noverall_soundscape: ", shots[0].prompt)
        self.assertTrue(shots[0].prompt.endswith("\n\nnon_diegetic_music: N/A"))
        self.assertIn("No subtitles, no on-screen text.", shots[0].prompt)
        self.assertIn("The camera pushes in slowly with small amplitude.", shots[0].prompt)
        # Instructions meant for a chat model are drawn by a video model, not obeyed.
        for order in ("RENDER TASK", "montage", "flashback", "PREVIOUS SHOT", "LOCK", "Dialogue: none",
                      "recurring protagonist"):
            self.assertNotIn(order, shots[0].prompt)
        self.assertLess(len(shots[0].prompt.split()), 320)
        self.assertNotIn("NEXT SHOT", shots[0].prompt)
        self.assertNotIn("WHOLE-STORY CONTRACT", shots[0].prompt)   # other beats' nouns get rendered
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
        self.assertTrue({"scene", "light"}.issubset(visual["required"]))
        self.assertEqual(schema["properties"]["characters"]["minItems"], 0)

    def test_documentary_local_ai_does_not_require_invented_characters(self):
        from agents.script import system_prompt

        documentary = system_prompt("local-ai", "documentary")
        fiction = system_prompt("local-ai", "fiction")
        self.assertIn("OBJECT-LED DOCUMENTARY", documentary)
        self.assertIn("Never invent named presenters", documentary)
        self.assertNotIn("one unmistakable physical gesture between the characters", documentary)
        self.assertIn("one unmistakable physical gesture between the characters", fiction)
        fiction_schema = build_script_tool(20, 100, 150, "local-ai", "fiction")["input_schema"]
        self.assertEqual(fiction_schema["properties"]["characters"]["minItems"], 1)

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


class SharedGpuTests(unittest.TestCase):
    def test_each_backend_frees_only_the_other_server(self):
        with tempfile.TemporaryDirectory() as folder:
            backends = build_backends(make_test_config(folder))
            for name, other in (("minimax", "http://wan.invalid"), ("wan", "http://minimax.invalid")):
                with patch("local_video.comfy.requests.post") as post:
                    post.return_value.ok = True
                    freed = backends[name].free_other_servers(backends[name].client.base_url)
                self.assertEqual([other], freed)
                self.assertEqual(f"{other}/free", post.call_args.args[0])
                self.assertEqual({"unload_models": True, "free_memory": True}, post.call_args.kwargs["json"])

    def test_shared_server_is_not_freed(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder, minimax_url="http://one.invalid", wan_url="http://one.invalid/")
            with patch("local_video.comfy.requests.post") as post:
                self.assertEqual([], build_backends(config)["minimax"].free_other_servers("http://one.invalid"))
            post.assert_not_called()

    def test_unreachable_server_does_not_raise(self):
        import requests

        with tempfile.TemporaryDirectory() as folder:
            backend = build_backends(make_test_config(folder))["minimax"]
            with patch("local_video.comfy.requests.post", side_effect=requests.ConnectionError):
                self.assertEqual([], backend.free_other_servers(backend.client.base_url))


class ClipLengthTests(unittest.TestCase):
    def test_generated_clips_fill_every_shot_without_a_frozen_tail(self):
        from local_video.config import MAX_CLIP_STRETCH, MAX_TRANSITION_SECONDS

        with tempfile.TemporaryDirectory() as folder:
            backends = build_backends(make_test_config(folder))
            for frames in (75, 90, 100, 108, 120):
                shot = Shot("s", 0, frames, "p", "n", 1)
                needed = shot.duration_seconds + MAX_TRANSITION_SECONDS
                for backend in backends.values():
                    self.assertGreaterEqual(backend.clip_seconds(shot) * MAX_CLIP_STRETCH, needed - 1e-6)
                self.assertEqual(1, backends["wan"].frames_for(shot) % 4)

    def test_clip_length_never_drops_below_configured_minimum(self):
        with tempfile.TemporaryDirectory() as folder:
            backends = build_backends(make_test_config(folder))
            shot = Shot("s", 0, 75, "p", "n", 1)
            self.assertGreaterEqual(backends["minimax"].clip_seconds(shot), backends["minimax"].config.minimax_seconds)
            self.assertGreaterEqual(backends["wan"].frames_for(shot), backends["wan"].config.wan_frames)


class NarrationFitTests(unittest.TestCase):
    def _project(self, folder, duration=75):
        config = make_test_config(folder)
        project = create_project("desert city", duration, "35mm nocturne", "auto", narration_enabled=False,
                                 config=config, script=sample_script())
        return config, project

    def test_long_narration_extends_the_timeline_instead_of_being_cut(self):
        with tempfile.TemporaryDirectory() as folder:
            config, project = self._project(folder)
            runner = QueueRunner(config, backends={})
            with patch("local_video.queue.get_duration", return_value=78.4):
                runner._fit_to_narration(project, Path(folder) / "narration.mp3")
            self.assertEqual(79, project.duration_seconds)
            self.assertEqual(79 * 30, sum(shot.duration_frames for shot in project.shots))
            self.assertTrue(any(e["event"] == "timeline_fitted_to_narration" for e in project.events))

    def test_short_narration_trims_the_silent_tail(self):
        with tempfile.TemporaryDirectory() as folder:
            config, project = self._project(folder)
            with patch("local_video.queue.get_duration", return_value=64.0):
                QueueRunner(config, backends={})._fit_to_narration(project, Path(folder) / "narration.mp3")
            self.assertEqual(65, project.duration_seconds)

    def test_a_video_asked_over_a_minute_never_ends_just_under_it(self):
        with tempfile.TemporaryDirectory() as folder:
            config, project = self._project(folder, duration=65)
            with patch("local_video.queue.get_duration", return_value=52.0):   # the voice came in short
                QueueRunner(config, backends={})._fit_to_narration(project, Path(folder) / "narration.mp3")
            self.assertEqual(61, project.duration_seconds)                     # TikTok pays over 1 minute

    def test_narration_longer_than_the_maximum_fails_before_generation(self):
        with tempfile.TemporaryDirectory() as folder:
            config, project = self._project(folder, duration=80)
            runner = QueueRunner(config, backends={})
            with patch("local_video.queue.get_duration", return_value=97.0):
                with self.assertRaises(ValueError):
                    runner._fit_to_narration(project, Path(folder) / "narration.mp3")
            self.assertEqual(80, project.duration_seconds)

    def test_failed_voiceover_stops_the_run_before_any_shot(self):
        with tempfile.TemporaryDirectory() as folder:
            config, project = self._project(folder)
            backend = FakeBackend(config, "minimax", [])
            runner = QueueRunner(config, backends={"minimax": backend, "wan": backend})
            with patch("local_video.queue.ensure_narration", side_effect=RuntimeError("ElevenLabs quota")):
                result = runner.run(project)
            self.assertEqual("failed", result.state)
            self.assertIn("ElevenLabs quota", result.error)
            self.assertTrue(all(shot.status == "pending" for shot in result.shots))
            self.assertEqual(0, backend.calls)


class MiniMaxStartupTests(unittest.TestCase):
    def _runner(self, folder, preferred):
        from local_video.backends import MiniMaxAdapter

        config = make_test_config(folder, minimax_url=None)
        project = create_project("desert city", 60, "35mm nocturne", preferred, narration_enabled=False,
                                 config=config, script=sample_script())
        wan = FakeBackend(config, "wan", [])
        return QueueRunner(config, backends={"minimax": MiniMaxAdapter(config), "wan": wan}), project, wan

    def test_auto_mode_warns_and_records_when_minimax_is_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            runner, project, _ = self._runner(folder, "auto")
            with patch("local_video.queue.ensure_minimax", return_value=(False, "FreeVideo is not set up")), \
                    self.assertLogs("pipeline", "WARNING") as logs:
                runner._prepare_minimax(project)
            self.assertTrue(any("UNAVAILABLE" in line for line in logs.output))
            self.assertTrue(any(e["event"] == "minimax_unavailable_at_start" for e in project.events))

    def test_explicit_minimax_fails_before_any_work(self):
        with tempfile.TemporaryDirectory() as folder:
            runner, project, wan = self._runner(folder, "minimax")
            with patch("local_video.queue.ensure_minimax", return_value=(False, "FreeVideo is not set up")):
                result = runner.run(project)
            self.assertEqual("failed", result.state)
            self.assertIn("MiniMax H3 was requested", result.error)
            self.assertEqual(0, wan.calls)

    def test_started_server_is_used(self):
        with tempfile.TemporaryDirectory() as folder:
            runner, project, _ = self._runner(folder, "auto")

            def started(config):
                config.minimax_url = "http://127.0.0.1:8190"
                return True, config.minimax_url

            with patch("local_video.queue.ensure_minimax", side_effect=started):
                runner._prepare_minimax(project)
            self.assertEqual("http://127.0.0.1:8190", runner.backends["minimax"].client.base_url)

    def test_ram_cap_is_saved_once_with_a_backup(self):
        from local_video import freevideo

        with tempfile.TemporaryDirectory() as folder:
            machine = Path(folder) / "machine.json"
            machine.write_text(json.dumps({"ready": True, "ram_gib": None}), encoding="utf-8")
            with patch.dict(os.environ, {"FREEVIDEO_RAM_GIB": "14"}):
                freevideo.apply_ram_cap(Path(folder))
                freevideo.apply_ram_cap(Path(folder))
            self.assertEqual(14, json.loads(machine.read_text(encoding="utf-8"))["ram_gib"])
            backup = json.loads((Path(folder) / "machine.json.before-ram-cap").read_text(encoding="utf-8"))
            self.assertIsNone(backup["ram_gib"])
            with patch.dict(os.environ, {"FREEVIDEO_RAM_GIB": "0"}):
                freevideo.apply_ram_cap(Path(folder))
            self.assertIsNone(json.loads(machine.read_text(encoding="utf-8"))["ram_gib"])

    def test_missing_installation_is_reported_without_starting_anything(self):
        from local_video import freevideo

        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder, minimax_url=None)
            with patch.dict(os.environ, {"FREEVIDEO_DIR": folder}), \
                    patch("local_video.freevideo.subprocess.Popen") as popen:
                available, reason = freevideo.ensure_minimax(config)
            self.assertFalse(available)
            self.assertIn("machine.json", reason)
            popen.assert_not_called()


class ComfyPollingTests(unittest.TestCase):
    def test_a_dropped_status_poll_does_not_end_the_job(self):
        import requests
        from local_video.comfy import ComfyClient

        done = unittest.mock.Mock(ok=True)
        done.json.return_value = {"p1": {"status": {"completed": True}, "outputs": {}}}
        with patch("local_video.comfy.requests.get", side_effect=[requests.ConnectionError("blip"), done]):
            history = ComfyClient("http://x.invalid", timeout=60, poll_seconds=0.01).wait("p1")
        self.assertEqual({}, history["outputs"])

    def test_a_sustained_outage_is_reported_as_infrastructure(self):
        import requests
        from local_video.comfy import ComfyClient, ComfyError
        from local_video.queue import _is_infrastructure_failure

        client = ComfyClient("http://x.invalid", timeout=60, poll_seconds=0.01)
        client.CONNECTION_GRACE_SECONDS = 0
        with patch("local_video.comfy.requests.get", side_effect=requests.ConnectionError("refused")):
            with self.assertRaises(ComfyError) as caught:
                client.wait("p1")
        self.assertTrue(_is_infrastructure_failure(caught.exception))


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

    def test_lock_with_reused_pid_is_recovered(self):
        # After a reboot the dead owner's pid can belong to a newer, unrelated process.
        with tempfile.TemporaryDirectory() as folder:
            lock = Path(folder) / ".gpu-generation.lock"
            lock.write_text(json.dumps({"pid": os.getpid(), "started": 1000.0}), encoding="utf-8")
            with FileLock(lock):
                self.assertGreater(json.loads(lock.read_text(encoding="utf-8"))["started"], 1000.0)

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
            self.assertEqual(len(result.shots[0].attempts), 3)
            # Nothing reviewable was rendered, so no repair take is spent; the shot is a last-resort
            # still and the run goes on instead of failing.
            self.assertEqual(result.shots[0].status, "accepted")
            self.assertEqual(result.shots[0].degraded, "still")

    def test_a_shot_every_take_of_which_is_rejected_gets_one_held_repair_take(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder, retry_limit=2, fallback_failures=9)
            project = self._project(folder, config)
            minimax = FakeBackend(config, "minimax", [])
            verdicts = iter([False, False, False, True])

            def reviewer(*args, **kwargs):
                return {"valid": next(verdicts), "average_score": 6, "problems": ["camera drifted"],
                        "fatal_problems": [], "revision_prompt": "Hold on the lava flow."}

            result = QueueRunner(config, {"minimax": minimax, "wan": FakeBackend(config, "wan", [])},
                                 validator=fake_validator, extractor=fake_extractor,
                                 visual_reviewer=reviewer).run(project, shots={1})
            shot = result.shots[0]
            self.assertEqual(minimax.calls, 4)
            self.assertEqual(shot.status, "accepted")
            self.assertFalse(shot.degraded)                   # the repair take passed outright
            self.assertTrue(shot.attempts[-1].get("repair"))
            self.assertIn("Static shot: the camera stays locked off on a tripod.", minimax.prompts[-1])
            self.assertTrue(minimax.prompts[-1].startswith("integrated_multimodal_description: [Shot 1]"))

    def test_the_repair_take_can_be_switched_off(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder, retry_limit=2, fallback_failures=9, repair_take=False)
            project = self._project(folder, config)
            minimax = FakeBackend(config, "minimax", [])
            reviewer = lambda *a, **k: {"valid": False, "average_score": 6, "problems": ["x"],
                                        "fatal_problems": [], "revision_prompt": "y"}
            QueueRunner(config, {"minimax": minimax, "wan": FakeBackend(config, "wan", [])},
                        validator=fake_validator, extractor=fake_extractor,
                        visual_reviewer=reviewer).run(project, shots={1})
            self.assertEqual(minimax.calls, 3)

    def _finish(self, folder, config, verdict):
        project = self._project(folder, config)
        for shot in project.shots[1:]:
            shot.status, shot.output = "accepted", "shots/x.mp4"
        (Path(project.project_dir) / "shots").mkdir(exist_ok=True)
        (Path(project.project_dir) / "shots" / "x.mp4").write_bytes(b"v")

        def assembler(manifest, *args):
            (Path(manifest.project_dir) / "render").mkdir(exist_ok=True)
            (Path(manifest.project_dir) / "render" / "final.mp4").write_bytes(b"v")
            return {"video": "render/final.mp4"}

        runner = QueueRunner(config, {"minimax": FakeBackend(config, "minimax", []),
                                      "wan": FakeBackend(config, "wan", [])},
                             validator=fake_validator, extractor=fake_extractor,
                             visual_reviewer=fake_visual_reviewer, assembler=assembler,
                             final_reviewer=lambda *a: {"valid": verdict, "problems": ["the edit loops"]})
        with patch("local_video.queue.validate_final", return_value={"valid": True}):
            return runner.run(project)

    def test_a_final_review_reject_delivers_the_video_with_a_warning_by_default(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self._finish(folder, make_test_config(folder), verdict=False)
            self.assertEqual(result.state, "completed")
            self.assertIn("the edit loops", result.settings["quality_warnings"][0])

    def test_a_final_review_reject_can_still_be_made_to_fail_the_run(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self._finish(folder, make_test_config(folder, final_review_blocks=True), verdict=False)
            self.assertEqual(result.state, "partially_completed")
            self.assertIn("the edit loops", result.error)

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
            self.assertNotEqual(minimax.prompts[0], minimax.prompts[1])
            self.assertTrue(minimax.prompts[1].startswith("integrated_multimodal_description: [Shot 1]"))
            self.assertIn("Stay underwater and show only chamber one", minimax.prompts[1])
            self.assertNotIn(minimax.prompts[0], minimax.prompts[1])   # never the old prompt plus orders

    def _rejecting_runner(self, config, reviews):
        minimax = FakeBackend(config, "minimax", [])
        wan = FakeBackend(config, "wan", [])
        reviews = iter(reviews)
        return QueueRunner(
            config, {"minimax": minimax, "wan": wan}, validator=fake_validator,
            extractor=fake_extractor, visual_reviewer=lambda *args: next(reviews),
        )

    def test_all_rejected_takes_keep_the_best_clean_one(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder, retry_limit=2, fallback_failures=9)
            project = self._project(folder, config)
            runner = self._rejecting_runner(config, [
                {"valid": False, "average_score": 5.5, "fatal_problems": [], "revision_prompt": "a"},
                {"valid": False, "average_score": 6.8, "fatal_problems": [], "revision_prompt": "b"},
                {"valid": False, "average_score": 7.5, "fatal_problems": ["duplicate protagonist"],
                 "revision_prompt": "c"},
            ])
            result = runner.run(project, shots={1})
            shot = result.shots[0]
            self.assertEqual("accepted", shot.status)
            self.assertEqual(Path("shots/shot-001-attempt-02.mp4"), Path(shot.output))
            self.assertTrue((Path(result.project_dir) / shot.output).is_file())
            self.assertTrue(any(e["event"] == "shot_accepted_best_take" for e in result.events))

    def test_only_fatal_takes_try_the_animated_still_first(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder, retry_limit=0, fallback_failures=9)
            project = self._project(folder, config)
            runner = self._rejecting_runner(config, [
                {"valid": False, "average_score": 6.0, "fatal_problems": ["visible text"], "revision_prompt": "a"},
            ])
            with patch.object(QueueRunner, "_still_replacement", return_value=False) as still, \
                    patch.object(QueueRunner, "_still_source", return_value=Path(folder) / "ref.jpg"):
                result = runner.run(project, shots={1})
            still.assert_called_once()
            self.assertEqual("accepted", result.shots[0].status)
            self.assertTrue(any(e["event"] == "shot_accepted_flawed_take" for e in result.events))

    def test_next_shot_renders_during_the_review(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder, retry_limit=1, fallback_failures=9)
            project = self._project(folder, config)
            runner = self._rejecting_runner(config, [{"valid": True}, {"valid": True}])
            result = runner.run(project, shots={1, 2})
            minimax = runner.backends["minimax"]
            self.assertEqual(2, minimax.calls)
            self.assertTrue(result.shots[1].attempts[0].get("speculative"))
            self.assertEqual("accepted", result.shots[1].status)
            events = [e["event"] for e in result.events]
            self.assertIn("speculative_shot_started", events)
            self.assertNotIn("speculative_shot_cancelled", events)

    def test_rejected_take_cancels_the_early_next_shot(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder, retry_limit=1, fallback_failures=9)
            project = self._project(folder, config)
            runner = self._rejecting_runner(config, [
                {"valid": False, "average_score": 5, "fatal_problems": [], "revision_prompt": "closer"},
                {"valid": True}, {"valid": True},
            ])
            cancelled = []
            runner.backends["minimax"].cancel = lambda prompt_id: cancelled.append(prompt_id) or True
            result = runner.run(project, shots={1, 2})
            # shot 1 take 1, its early shot 2 (thrown away), shot 1 retake, shot 2 again from the retake.
            self.assertEqual(4, runner.backends["minimax"].calls)
            self.assertTrue(any(e["event"] == "speculative_shot_cancelled" for e in result.events))
            self.assertEqual(["accepted", "accepted"], [s.status for s in result.shots[:2]])
            self.assertEqual(1, len(result.shots[1].attempts))

    def test_pause_never_leaves_an_early_render_running(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder)
            project = self._project(folder, config)
            runner = self._rejecting_runner(config, [{"valid": True}])
            states = iter(["generating", "generating", "paused", "paused", "paused", "paused"])
            with patch.object(QueueRunner, "_control_state", side_effect=lambda m: next(states, "paused")):
                result = runner.run(project)
            self.assertIsNone(runner._speculation)
            self.assertEqual(1, sum(s.status == "accepted" for s in result.shots))

    def test_upscale_reuses_cached_clips_and_never_blocks_assembly(self):
        from local_video import upscale
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder)
            project = self._project(folder, config)
            for shot in project.shots:
                clip = Path(project.project_dir) / "shots" / f"{shot.id}.mp4"
                clip.write_bytes(b"clip")
                shot.status, shot.output = "accepted", str(clip.relative_to(project.project_dir))
            cached_source = resolve_within(project.project_dir, project.shots[0].output)
            cached = Path(project.project_dir) / "render" / "upscaled" / upscale.upscaled_name(cached_source)
            cached.parent.mkdir(parents=True)
            cached.write_bytes(b"sharp")
            python = Path(folder) / "python.exe"
            python.write_bytes(b"")
            with patch.dict(os.environ, {"LOCAL_VIDEO_AI_UPSCALE": "1"}), \
                    patch.object(upscale, "engine_python", return_value=python), \
                    patch.object(upscale, "ensure_model", side_effect=OSError("offline")), \
                    patch.object(upscale.subprocess, "run") as run:
                clips = upscale.upscale_clips(project, config)
            run.assert_not_called()
            self.assertEqual({"shot-001": cached}, clips)

    def test_eta_counts_every_take_and_review(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder)
            project = self._project(folder, config)
            project.shots[0].status = "accepted"
            project.shots[0].output = "shots/x.mp4"
            project.shots[0].attempts = [
                {"status": "failed", "started_at": 0.0, "ended_at": 300.0, "generation_seconds": 250},
                {"status": "accepted", "started_at": 300.0, "ended_at": 600.0, "generation_seconds": 250},
            ]
            remaining = len(project.shots) - 1
            self.assertEqual(600.0 * remaining, estimated_remaining_seconds(project))
            self.assertEqual(600.0 * remaining, project_status(project)["estimated_remaining_seconds"])

    def test_retake_prompt_leaves_continuity_frame_and_targets_payoff(self):
        shot = Shot(
            id="shot-003", index=2, duration_frames=90, prompt="BASE PROMPT",
            negative_prompt="n", seed=1,
            subject_action="Mara reaches the archway. Close on her intact mask.",
            camera_action="smooth push-in",
        )
        # A short note amends the beat.
        prompt = _retake_prompt(shot, "Keep the regulator visible.", has_reference=True)
        self.assertIn("Mara reaches the archway. Close on her intact mask. Keep the regulator visible.", prompt)
        self.assertNotIn("BASE PROMPT", prompt)
        # A full revised description from the reviewer replaces it; the beat's end state stays the target.
        revision = "Medium shot at eye level: Mara in her diving suit walks under the stone archway toward camera."
        prompt = _retake_prompt(shot, revision, has_reference=True)
        self.assertIn(revision, prompt)
        self.assertNotIn("Mara reaches the archway", prompt)
        self.assertIn("By the end of the clip: Close on her intact mask.", prompt)
        self.assertNotIn("BASE PROMPT", prompt)

    def test_minimax_marks_a_supplied_first_frame_and_wan_gets_plain_text(self):
        from local_video.backends import MiniMaxAdapter
        from local_video.planner import FIRST_FRAME_LINE, plain_description
        shot = plan_shots(sample_script(), "desert city", 60, "35mm nocturne", "auto")[0][0]
        with tempfile.TemporaryDirectory() as folder:
            adapter = MiniMaxAdapter(make_test_config(folder))
            text = adapter.workflow(shot)["1"]["inputs"]["text"]
            self.assertNotIn(FIRST_FRAME_LINE, text)
            client = type("Client", (), {"upload_image": lambda self, path: "frame.png"})()
            adapter.client = client
            text = adapter.workflow(shot, Path(folder) / "frame.png")["1"]["inputs"]["text"]
        lead, rest = text.split(FIRST_FRAME_LINE)
        self.assertTrue(lead.endswith("9:16 vertical frame. "))      # right after the opening framing
        plain = plain_description(shot.prompt)
        self.assertNotIn("integrated_multimodal_description", plain)
        self.assertNotIn("overall_soundscape", plain)
        self.assertTrue(plain.startswith("Live-action"))

    def test_generator_text_drops_the_illustrative_label(self):
        from local_video.planner import generator_text
        self.assertEqual("Close-up: camera low on the deck.",
                         generator_text("Close-up: illustrative reconstruction, camera low on the deck."))
        self.assertEqual("35mm documentary look of a period reconstruction, muted grade",
                         generator_text("35mm documentary look of an illustrative period reconstruction, muted grade"))
        self.assertEqual("a radar dish at a ground station", generator_text("a radar dish at a ground station (illustrative)"))

    def test_a_close_up_carries_no_screen_geography(self):
        script = sample_script()
        script["screen_geography"] = "Austrian ships always frame left; the Dutch warship frame right"
        script["beats"][0]["visual"]["description"] = "Close-up: a black iron kettle on deck planks."
        script["beats"][1]["visual"]["description"] = "Wide shot: three ships sail left to right."
        shots, _ = plan_shots(script, "desert city", 60, "cinematic", "auto")
        self.assertNotIn("ships", shots[0].prompt)
        self.assertIn("Screen geography: Austrian ships always frame left", shots[1].prompt)

    def test_a_resumed_old_project_renders_pending_shots_with_the_new_prompt(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder)
            project = self._project(folder, config)
            project.shots[0].prompt = "CURRENT RENDER TASK — SHOT 01 OF 20. Render only this shot, not a montage."
            project.save()
            minimax = FakeBackend(config, "minimax", ["ok"])
            QueueRunner(config, {"minimax": minimax, "wan": FakeBackend(config, "wan", [])},
                        validator=fake_validator, extractor=fake_extractor,
                        visual_reviewer=fake_visual_reviewer).run(project, shots={1})
            self.assertTrue(minimax.prompts[0].startswith("integrated_multimodal_description: [Shot 1]"))
            self.assertIn(project.shots[0].subject_action.rstrip("."), minimax.prompts[0])
            self.assertNotIn("RENDER TASK", minimax.prompts[0])

    def test_every_unfinished_shot_is_upgraded_before_the_next_shot_renders_early(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder)
            project = self._project(folder, config)
            for shot in project.shots:
                shot.prompt = "CURRENT RENDER TASK. Render only this shot, not a montage."
            project.shots[0].status = "accepted"
            QueueRunner._upgrade_prompts(project)
            self.assertFalse(project.shots[0].prompt.startswith("integrated_multimodal_description"))
            self.assertTrue(all(s.prompt.startswith("integrated_multimodal_description: [Shot 1]")
                                for s in project.shots[1:]))

    def test_a_resumed_shot_drops_another_scenes_setting_saved_at_planning(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder)
            project = self._project(folder, config)
            for i, beat in enumerate(project.script["beats"]):
                beat["visual"]["scene"] = "peninsula shore" if i < 10 else "open pacific sea"
            project.script["location"] = ("Peninsula shore: beachfront homes facing the sea. "
                                          "Open Pacific sea: a tropical ocean seen from a palm-lined beach.")
            for shot in project.shots:  # what an older planner saved: the whole world, every scene
                shot.continuity = {**shot.continuity, "location": project.script["location"]}
                shot.prompt = shot.prompt.replace("Setting:", "Setting: palm-lined beach.")
            QueueRunner._upgrade_prompts(project)
            self.assertNotIn("palm-lined", project.shots[0].prompt)
            self.assertNotIn("palm-lined", project.shots[0].continuity["location"])
            self.assertIn("beachfront homes", project.shots[0].prompt)
            self.assertIn("palm-lined", project.shots[12].prompt)

    def test_a_shot_that_places_its_own_camera_is_not_forced_to_eye_level(self):
        from local_video.planner import framing_for
        self.assertNotIn("eye level", framing_for("Close, low view along the boardwalk: planks lifted."))
        self.assertIn("close-up", framing_for("Close, low view along the boardwalk: planks lifted."))
        self.assertNotIn("eye level", framing_for("The camera rises from the boardwalk to the walls."))
        self.assertNotIn("eye level", framing_for("Foam surges past the homes.", "slow rising crane move"))
        self.assertIn("eye level", framing_for("Foam surges past the homes.", "steady pan left"))

    def test_a_named_object_enters_the_prompt_only_when_the_shot_names_it(self):
        script = sample_script()
        script["recurring_objects"] = [
            "Austrian merchant ship: a broad-bellied sailing ship flying a yellow banner with a black eagle",
            "Bologna banners (illustrative): plain red cloth banners",
            "Modena banners (illustrative): plain white cloth banners",
        ]
        script["beats"][0]["visual"]["description"] = "Wide shot: wooden merchant sailing ships moored at a quay."
        script["beats"][1]["visual"]["description"] = "Medium shot: the Austrian merchant ship sails right."
        script["beats"][2]["visual"]["description"] = "Medium shot: a plain red cloth banner flutters on a wall."
        shots, _ = plan_shots(script, "desert city", 60, "cinematic", "auto")
        self.assertNotIn("eagle", shots[0].prompt)                    # generic ships stay generic
        self.assertIn("black eagle", shots[1].prompt)
        self.assertNotIn("white cloth", shots[2].prompt)              # never the rival city's banner
        self.assertIn("eagle", shots[0].continuity["recurring_objects"])   # the reviewer's lock is unchanged

    def test_birds_overhead_do_not_lift_the_camera(self):
        from local_video.planner import framing_for
        self.assertNotIn("aerial", framing_for("Wide shot: camera at eye level on a quay. Gulls cross overhead."))
        self.assertIn("aerial", framing_for("Wide overhead shot looking down on the harbour."))

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

    def test_a_redo_with_rendered_narration_needs_no_voice_credits(self):
        class MissingBackend:
            @staticmethod
            def available():
                return False, "offline"

        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder)
            manifest = ProjectManifest(
                id="test", concept="test", duration_seconds=60, visual_style="film",
                preferred_backend="auto", project_dir=folder, script={"spoken_script": "x" * 800},
            )
            (Path(folder) / "audio").mkdir()
            (Path(folder) / "audio" / "narration.mp3").write_bytes(b"mp3")
            with patch("local_video.preflight._tool_ok", return_value=True), \
                    patch("local_video.preflight.elevenlabs_keys", return_value=[("k", "key")]), \
                    patch("local_video.preflight.credit_status", return_value={"valid": True, "remaining": 0}):
                with self.assertRaisesRegex(RuntimeError, "No configured video backend") as raised:
                    run_preflight(manifest, config, {"minimax": MissingBackend(), "wan": MissingBackend()},
                                  require_visual_qc=False)
            self.assertNotIn("ElevenLabs", str(raised.exception))

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

    def test_manifest_save_waits_out_a_reader_holding_the_file(self):
        """Windows denies a rename over a file another process has open; save must retry."""
        with tempfile.TemporaryDirectory() as folder:
            manifest = ProjectManifest(
                id="test", concept="test", duration_seconds=60, visual_style="film",
                preferred_backend="auto", project_dir=folder,
            )
            real_replace = os.replace
            calls = []

            def flaky_replace(source, target):
                calls.append(target)
                if len(calls) < 3:
                    raise PermissionError(5, "Access is denied")
                real_replace(source, target)

            with patch("local_video.models.os.replace", flaky_replace), \
                    patch("local_video.models.time.sleep"):
                path = manifest.save()
            self.assertEqual(3, len(calls))
            self.assertEqual("test", json.loads(path.read_text(encoding="utf-8"))["id"])
            self.assertEqual([], list(Path(folder).glob("*.tmp")))

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
            self.assertNotIn("minterpolate", joined)  # blending 24->30 fps ghosts moving subjects
            sharp = Path(folder) / "render" / "upscaled" / "0-x2.mp4"
            command = build_video_command(manifest, Path(folder) / "assembled.mp4", config, {"shot-001": sharp})
            self.assertEqual(str(sharp), command[command.index("-i") + 1])
            self.assertIn(str(resolve_within(folder, "shots/1.mp4")), command)
            final = build_final_command(
                Path(folder) / "video.mp4", Path(folder) / "audio.m4a",
                Path(folder) / "final.mp4", 60, config,
            )
            self.assertIn("aac", final)
            self.assertIn("30", final)


class KeyframeTests(unittest.TestCase):
    def _project(self, folder):
        project = create_project("desert city", 60, "35mm nocturne", "auto", narration_enabled=False,
                                 config=make_test_config(folder), script=sample_script())
        for shot in project.shots:
            shot.scene, shot.light = "plaza", "dusk"
        project.shots[2].scene = "rooftop"            # a hard cut to a new place
        return project

    def test_only_fresh_openings_get_a_photoreal_first_frame(self):
        from local_video import keyframes
        with tempfile.TemporaryDirectory() as folder:
            project = self._project(folder)
            # the cut to the rooftop opens fresh, and so does every 4th plaza shot: a take is at most
            # MAX_TAKE shots, never 19 shots chained off one frame (the 2026-10-27 El Nino video)
            self.assertEqual([0, 2, 4, 7, 10, 13, 16, 19], keyframes.fresh_openings(project))
            prompt = keyframes.keyframe_prompt(project.shots[0])
            self.assertIn("full-frame camera", prompt)
            self.assertNotIn("cinematic", prompt.lower())

    def test_queue_opens_on_the_keyframe_until_it_keeps_failing(self):
        from local_video import keyframes
        with tempfile.TemporaryDirectory() as folder:
            project = self._project(folder)
            runner = QueueRunner(make_test_config(folder), backends={})
            first = keyframes.keyframe_path(project, project.shots[0])
            first.parent.mkdir(parents=True)
            first.write_bytes(b"png")
            self.assertEqual(first, runner._reference_for(project, 0))
            project.shots[0].attempts = [{"status": "failed", "keyframe": True}] * 2
            self.assertIsNone(runner._reference_for(project, 0))     # the last takes go text-only

    def test_missing_checkpoint_skips_keyframes_without_gpu_work(self):
        from local_video import keyframes
        with tempfile.TemporaryDirectory() as folder:
            project = self._project(folder)
            with patch.object(keyframes, "has_checkpoint", return_value=False), \
                    patch.object(keyframes.ComfyClient, "submit") as submit:
                self.assertEqual(0, keyframes.prepare_keyframes(project, make_test_config(folder)))
            submit.assert_not_called()


class DegradationGuardTests(unittest.TestCase):
    """A salvaged shot is marked, never chained into another still, and ends a hopeless run.

    Accepting the least bad take keeps a run alive, but each one costs the final creative review its
    story, continuity and pacing scores. Unbounded, it renders for hours to build a video that gate
    always rejects, and chained still push-ins manufacture the very repetition it rejects.
    """

    def _runner_and_project(self, folder, **config_values):
        config = make_test_config(folder, **config_values)
        project = create_project("desert city", 60, "35mm nocturne", "auto", narration_enabled=False,
                                 config=config, script=sample_script())
        runner = QueueRunner(config, {"minimax": FakeBackend(config, "minimax", []),
                                      "wan": FakeBackend(config, "wan", [])},
                             validator=fake_validator, extractor=fake_extractor)
        return runner, project

    @staticmethod
    def _give_frames(project, count):
        for shot in project.shots[:count]:
            frame = Path(project.project_dir) / "shots" / f"{shot.id}-last.jpg"
            frame.parent.mkdir(parents=True, exist_ok=True)
            frame.write_bytes(b"frame")
            shot.last_frame = str(frame.relative_to(project.project_dir))

    _chain = staticmethod(lambda manifest, index: index - 1 if index else None)

    def test_a_still_is_built_from_the_nearest_real_frame(self):
        with tempfile.TemporaryDirectory() as folder:
            runner, project = self._runner_and_project(folder)
            self._give_frames(project, 3)
            project.shots[1].degraded = "still"               # shot 2 is itself a push-in
            with patch.object(QueueRunner, "_reference_source", staticmethod(self._chain)):
                source = runner._still_source(project, 2)
            self.assertIsNotNone(source)
            self.assertEqual(Path(project.shots[0].last_frame).name, source.name)

    def test_no_still_is_made_when_every_candidate_is_itself_a_still(self):
        with tempfile.TemporaryDirectory() as folder:
            runner, project = self._runner_and_project(folder)
            self._give_frames(project, 3)
            project.shots[0].degraded = "still"
            project.shots[1].degraded = "still"
            with patch.object(QueueRunner, "_reference_source", staticmethod(self._chain)):
                self.assertIsNone(runner._still_source(project, 2))

    def test_a_genuinely_passed_shot_is_a_valid_still_source(self):
        with tempfile.TemporaryDirectory() as folder:
            runner, project = self._runner_and_project(folder)
            self._give_frames(project, 2)
            with patch.object(QueueRunner, "_reference_source", staticmethod(self._chain)):
                source = runner._still_source(project, 1)
            self.assertEqual(Path(project.shots[0].last_frame).name, source.name)

    def test_the_run_continues_while_salvage_stays_inside_the_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            runner, project = self._runner_and_project(folder, max_degraded_percent=50)
            for shot in project.shots:
                shot.status = "accepted"
            project.shots[0].degraded = "still"
            self.assertIsNone(runner._degradation_stop(project, None))

    def test_the_run_stops_once_salvage_passes_the_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            runner, project = self._runner_and_project(folder, max_degraded_percent=25)
            for shot in project.shots:
                shot.status = "accepted"
            for shot in project.shots:                        # every shot salvaged: hopeless
                shot.degraded = "still"
            message = runner._degradation_stop(project, None)
            self.assertIsNotNone(message)
            self.assertIn("still push-in", message)
            self.assertIn("25% budget", message)
            self.assertIn(str(project.project_dir), message)
            self.assertIn("--shots", message)

    def test_a_hundred_percent_budget_restores_the_old_never_stop_behaviour(self):
        with tempfile.TemporaryDirectory() as folder:
            runner, project = self._runner_and_project(folder, max_degraded_percent=100)
            for shot in project.shots:
                shot.status, shot.degraded = "accepted", "still"
            self.assertIsNone(runner._degradation_stop(project, None))

    def test_a_partial_rerun_is_budgeted_against_the_whole_video(self):
        # The 2026-10-27 redo of 6 of 22 shots stopped at "2 salvaged, budget 1 of 6"; the final
        # review sees 22 shots, whose budget of 5 had room.
        with tempfile.TemporaryDirectory() as folder:
            runner, project = self._runner_and_project(folder, max_degraded_percent=25)
            allowed = len(project.shots) * 25 // 100
            self.assertGreaterEqual(allowed, 1)
            for shot in project.shots[:allowed]:
                shot.status, shot.degraded = "accepted", "best_take"
            self.assertIsNone(runner._degradation_stop(project, {1}))
            project.shots[allowed].status, project.shots[allowed].degraded = "accepted", "best_take"
            self.assertIsNotNone(runner._degradation_stop(project, {1}))

    def test_the_recovery_hint_names_the_project_and_the_shots_to_redo(self):
        with tempfile.TemporaryDirectory() as folder:
            runner, project = self._runner_and_project(folder)
            hint = runner._recovery_hint(project, [project.shots[0], project.shots[2]])
            self.assertIn(str(project.project_dir), hint)
            self.assertIn("--shots 1,3", hint)               # CLI shot numbers are 1-based

    def test_the_hint_omits_the_command_when_there_is_nothing_to_redo(self):
        with tempfile.TemporaryDirectory() as folder:
            runner, project = self._runner_and_project(folder)
            hint = runner._recovery_hint(project)
            self.assertIn(str(project.project_dir), hint)
            self.assertNotIn("--shots", hint)

    def test_a_salvaged_shot_records_how_it_was_salvaged(self):
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder, retry_limit=2, fallback_failures=9,
                                      max_degraded_percent=100)
            project = create_project("desert city", 60, "35mm nocturne", "auto",
                                     narration_enabled=False, config=config, script=sample_script())
            reviews = iter([
                {"valid": False, "average_score": 5.5, "fatal_problems": [], "revision_prompt": "a"},
                {"valid": False, "average_score": 6.8, "fatal_problems": [], "revision_prompt": "b"},
                {"valid": False, "average_score": 6.0, "fatal_problems": [], "revision_prompt": "c"},
            ])
            runner = QueueRunner(config, {"minimax": FakeBackend(config, "minimax", []),
                                          "wan": FakeBackend(config, "wan", [])},
                                 validator=fake_validator, extractor=fake_extractor,
                                 visual_reviewer=lambda *args: next(reviews))
            result = runner.run(project, shots={1})
            self.assertEqual("accepted", result.shots[0].status)
            self.assertEqual("best_take", result.shots[0].degraded)   # accepted != passed review

    def test_regenerating_a_shot_clears_its_salvage_mark(self):
        """Otherwise a stale mark spends the next run's budget and bars the shot as a still source."""
        with tempfile.TemporaryDirectory() as folder:
            config = make_test_config(folder)
            project = create_project("desert city", 60, "35mm nocturne", "auto",
                                     narration_enabled=False, config=config, script=sample_script())
            project.shots[0].status = "accepted"
            project.shots[0].degraded = "still"
            project.save()
            reset = reset_shot(project.project_dir, 1, config)
            self.assertEqual("pending", reset.shots[0].status)
            self.assertEqual("", reset.shots[0].degraded)

    def test_the_recovery_hint_tells_you_to_pass_redo(self):
        """Without --redo the named shots are already 'accepted', so the queue skips them and the
        command silently re-reviews the same edit."""
        with tempfile.TemporaryDirectory() as folder:
            runner, project = self._runner_and_project(folder)
            hint = runner._recovery_hint(project, [project.shots[0], project.shots[2]])
            self.assertIn("--shots 1,3", hint)
            self.assertIn("--redo", hint)


class WritersCameraChoiceTests(unittest.TestCase):
    """The screenplay schema requires a camera move per beat and the script evaluator checks it
    against continuity_out, but the planner used to overwrite it with CAMERA_MOVES[index % 6].
    On the 2026-10-27 volcano run 7 of 8 shots rendered a move the writer never chose, so every
    inherited start state described a move that was never filmed."""

    def test_the_writers_move_is_rendered(self):
        from local_video.planner import _camera_plan
        for chosen, expected in (("push_in", "push-in"), ("pull_out", "pull-back"),
                                 ("pan_left", "pan left"), ("pan_right", "pan right"),
                                 ("rise", "rising"), ("orbit", "orbit")):
            with self.subTest(chosen=chosen):
                move, _ = _camera_plan("a volcano across the strait", 3, chosen=chosen)
                self.assertIn(expected, move)

    def test_a_beat_with_no_choice_still_falls_back_to_the_rotation(self):
        from local_video.planner import CAMERA_MOVES, _camera_plan
        expected = CAMERA_MOVES[3 % len(CAMERA_MOVES)]
        move, _ = _camera_plan("a volcano across the strait", 3)
        self.assertEqual(expected, move)
        move, _ = _camera_plan("a volcano across the strait", 3, chosen="not_a_move")
        self.assertEqual(expected, move)

    def test_the_writers_vocabulary_is_fully_translated(self):
        """planner.CAMERA_MOVES is 8 prose phrases, the screenplay enum is 6 different values, so
        the two could never match by accident: every enum value needs an explicit phrase."""
        from agents.script import CAMERA_MOVES as SCHEMA_MOVES
        from local_video.planner import _MOVE_PHRASE
        self.assertEqual(set(SCHEMA_MOVES), set(_MOVE_PHRASE))

    def test_an_explicit_composition_cue_still_wins(self):
        """A macro or low-angle cue describes where the camera IS, so it sets the move and framing."""
        from local_video.planner import _camera_plan
        move, framing = _camera_plan("extreme close-up of the lava crust", 3, chosen="orbit")
        self.assertIn("macro", move)
        self.assertIn("macro", framing)


class KeyframeStyleTests(unittest.TestCase):
    """The keyframe is the clip's first frame AND the reference the reviewer compares it against,
    so a look the clip brief states and the keyframe omits becomes a rejection. It omitted
    visual_style, which carries the palette and grade."""

    def _shot(self, **continuity):
        return Shot(id="s", index=0, duration_frames=90, prompt="", negative_prompt="", seed=1,
                    subject_action="a dark volcanic cone across a strait",
                    light="hazy daylight under ash plume", continuity=continuity, cast=[])

    def test_the_palette_and_grade_reach_the_keyframe(self):
        from local_video.keyframes import keyframe_prompt
        prompt = keyframe_prompt(self._shot(
            visual_style="35mm documentary look, charcoal-and-steel grade with muted ember accents"))
        self.assertIn("Visual style:", prompt)
        self.assertIn("charcoal-and-steel grade", prompt)
        self.assertIn("hazy daylight under ash plume", prompt)       # and the light, as before

    def test_the_keyframe_states_the_aspect_and_framing(self):
        from local_video.keyframes import keyframe_prompt
        prompt = keyframe_prompt(self._shot(visual_style="any"))
        self.assertIn("9:16 portrait", prompt)
        self.assertIn("filling a clear share of the frame", prompt)  # not a tiny distant subject

    def test_a_shot_without_a_style_still_builds_a_prompt(self):
        from local_video.keyframes import keyframe_prompt
        prompt = keyframe_prompt(self._shot())
        self.assertNotIn("Visual style:", prompt)
        self.assertIn("a dark volcanic cone across a strait", prompt)


class VolcanoRejectionCauseTests(unittest.TestCase):
    """The prompt faults behind the 2026-10-27 volcano run's rejections, rebuilt from its own text."""

    def _script(self):
        script = sample_script()
        beats = script["beats"]
        for beat, (scene, light, description, camera) in zip(beats, [
            ("open sea off the island", "hazy midday sun",
             "From the open sea, the bare ash cone rises straight from the water.", "push_in"),
            ("open sea off the island", "ash-darkened overcast sky",
             "A wide view from the sea: a dense ash column already stands over the summit.", "push_in"),
            ("western shore", "ash-darkened overcast sky",
             "A wide view of the western shore and its dark lava apron.", "push_in"),
            ("western shore", "ash-darkened overcast sky",
             "Close on the edge of the flow: a wave rolls over hardened black rock.", "push_in"),
            ("above the island", "ash-darkened overcast sky",
             "An illustrative high, wide view looking down on the island from far above.", "push_in"),
        ]):
            beat["visual"].update(scene=scene, light=light, description=description, camera=camera)
        script["location"] = (
            "Open sea off the island: the ash cone rises from the strait, seen from the sea. "
            "Above the island: an illustrative high, wide vantage looking down on the whole cone. "
            "Western shore: dark crusted lava flows run down rough grey slopes to the waterline.")
        script["color_palette"] = "ash grey, muted sea teal, white steam, pale hazy sky"
        script["story_premise"] = "Eruptions sent lava down the flanks of the volcano."
        script["ending_payoff"] = "A clear, wide daytime view of the enlarged island."
        return script

    def _shots(self):
        shots, _ = plan_shots(self._script(), "volcano", 60, "documentary", "auto")
        return shots[:4]

    def test_another_scenes_aerial_vantage_stays_out_of_the_open_sea_shots(self):
        for shot in self._shots()[:2]:
            self.assertNotIn("looking down", shot.prompt)
            self.assertIn("Open sea off the island", shot.prompt)

    def test_a_pale_sky_stays_out_of_ash_darkened_shots(self):
        shots = self._shots()
        self.assertNotIn("pale hazy sky", shots[1].prompt)
        self.assertIn("pale hazy sky", shots[0].prompt)

    def test_clear_air_never_contradicts_the_shots_own_light(self):
        self.assertNotIn("clear air", self._shots()[1].prompt)

    def test_the_whole_story_premise_and_payoff_stay_out_of_each_shot(self):
        for shot in self._shots():
            self.assertNotIn("sent lava down", shot.prompt)
            self.assertNotIn("clear, wide daytime view", shot.prompt)

    def test_framing_follows_the_description_never_a_rotation(self):
        prompts = [shot.prompt for shot in self._shots()]
        self.assertNotIn("macro", prompts[1])                # a wide ash-column shot
        self.assertIn("24mm wide frame", prompts[1])
        self.assertIn("85mm close-up", prompts[3])
        self.assertTrue(all("eye level" in prompt for prompt in prompts))

    def test_a_close_up_after_a_wide_shot_opens_on_its_own_keyframe(self):
        from local_video.planner import framing_scale
        shots = self._shots()
        labels = [(s.scene, s.light) for s in shots]
        scales = [framing_scale(s.subject_action) for s in shots]
        self.assertEqual(scales[2:], ["wide", "close"])
        self.assertIsNone(continuation_source(labels, 3, None, scales))
        self.assertEqual(continuation_source(labels, 3), 2)     # without scales it would continue

    def test_one_side_never_opens_on_the_other_sides_frame(self):
        from local_video.planner import beat_objects, _object_name
        script = {"recurring_objects": [
            "Austrian warships: two slim two-masted ships flying a yellow eagle banner",
            "Dutch warship: a single dark-hulled ship flying a horizontal striped flag",
        ], "beats": [{"visual": {"scene": "river", "light": "overcast", "description": d}} for d in (
            "Medium shot: a single dark-hulled warship, its striped flag at the stern.",
            "Wide shot: two slim warships glide downriver, eagle banners flying.",
            "Medium shot: a single dark-hulled warship holds position, striped flag streaming.",
            "Close-up: the dark hull of the warship as one gun port puffs smoke.",
        )]}
        objects = [frozenset(_object_name(item) for item in beat_objects(script, i)) for i in range(4)]
        self.assertEqual(objects[1], {"austrian warships"})    # plural head noun, told apart by its banner
        self.assertEqual(objects[2], {"dutch warship"})
        labels = [("river", "overcast")] * 4
        self.assertEqual(continuation_source(labels, 2), 1)    # without objects: the convoy's frame
        self.assertEqual(continuation_source(labels, 2, None, None, objects), 0)  # back to its own ship
        self.assertEqual(continuation_source(labels, 3, None, None, objects), 2)
        self.assertIsNone(continuation_source(labels, 1, None, None, objects))

    def test_the_keyframe_leads_with_camera_position_and_light(self):
        from local_video.keyframes import keyframe_prompt
        prompt = keyframe_prompt(self._shots()[1])
        self.assertTrue(prompt.startswith("Photograph, 24mm wide frame, camera at eye level"))
        self.assertLess(prompt.index("ash-darkened"), prompt.index("Subject:"))
        self.assertNotIn("looking down", prompt)


class QualityFloorTests(unittest.TestCase):
    """A 3s clip of a slow subject scores low on story_progression even when it is a good shot:
    17 of 20 takes on the volcano run, several otherwise scoring 8s. The floor now gives that
    dimension the same one-point relief as visual_match and immersion."""

    GOOD = {"visual_match": 8, "continuity": 8, "image_quality": 8, "anatomy": 10,
            "immersion": 8, "story_progression": 6}

    def _accepts(self, scores):
        from local_video.visual_review import quality_floor
        return all(v >= 7 for v in scores.values()) or quality_floor(scores, 7)

    def test_a_take_missing_only_on_progression_is_kept(self):
        self.assertTrue(self._accepts(self.GOOD))           # avg 8.0, rejected before this change

    def test_anatomy_still_rejects(self):
        self.assertFalse(self._accepts(dict(self.GOOD, anatomy=6)))

    def test_progression_two_below_still_rejects(self):
        self.assertFalse(self._accepts(dict(self.GOOD, story_progression=5)))

    def test_strong_take_with_cgi_looking_smoke_is_kept(self):
        # shot-007 take 1 of the 2026-10-27 run: avg 7.17, rejected on image_quality 6 alone.
        scores = {"visual_match": 7, "continuity": 8, "image_quality": 6, "anatomy": 9,
                  "immersion": 6, "story_progression": 7}
        self.assertTrue(self._accepts(scores))

    def test_image_quality_one_low_on_a_middling_take_still_rejects(self):
        scores = {"visual_match": 6, "continuity": 7, "image_quality": 6, "anatomy": 9,
                  "immersion": 6, "story_progression": 6}   # avg 6.67, under 6.7
        self.assertFalse(self._accepts(scores))

    def test_image_quality_two_low_still_rejects(self):
        self.assertFalse(self._accepts(dict(self.GOOD, image_quality=5)))

    def test_the_floor_stays_off_unless_enabled(self):
        import inspect
        from local_video import visual_review
        source = inspect.getsource(visual_review.review_clip)
        self.assertIn('os.getenv("LOCAL_VIDEO_ALLOW_QUALITY_FLOOR", "0") == "1" and quality_floor(', source)


class RetakeCorrectionTests(unittest.TestCase):
    """A rejected take's correction is fed straight to the generator as the next prompt.

    MiniMax has no negative channel (only WanAdapter reads Shot.negative_prompt), so a forbidden
    thing named in the correction becomes a thing that was asked for. The 2026-10-27 run's
    corrections read "no daylight", "no pink", "avoid the mainland" and the same defects returned.
    """

    def test_the_reviewer_is_told_to_write_corrections_positively(self):
        spec = review_clip.__globals__["REVIEW_TOOL"]["input_schema"]["properties"]["revision_prompt"]
        self.assertIn("description", spec)               # it had none, so the format was invented
        description = spec["description"]
        self.assertIn("Never phrase a fix as a prohibition", description)
        self.assertIn("no negative channel", description)
        self.assertIn("becomes a thing you asked for", description)
        self.assertIn("State the replacement instead", description)

    def test_only_the_wan_backend_consumes_a_negative_prompt(self):
        """Why corrections must be positive: the primary backend ignores negative_prompt."""
        import inspect
        from local_video.backends import MiniMaxAdapter, WanAdapter
        self.assertIn("negative_prompt", inspect.getsource(WanAdapter))
        self.assertNotIn("negative_prompt", inspect.getsource(MiniMaxAdapter))


class RedoFlagTests(unittest.TestCase):
    """`run --shots` reuses accepted shots; only --redo re-renders them."""

    def _project(self, folder):
        config = make_test_config(folder)
        project = create_project("desert city", 60, "35mm nocturne", "auto", narration_enabled=False,
                                 config=config, script=sample_script())
        clip = Path(project.project_dir) / "shots" / "shot-001.mp4"
        clip.parent.mkdir(parents=True, exist_ok=True)
        clip.write_bytes(b"clip")
        project.shots[0].status = "accepted"
        project.shots[0].degraded = "still"
        project.shots[0].output = str(clip.relative_to(project.project_dir))
        project.save()
        return config, project

    def test_redo_resets_the_named_shots_before_running(self):
        from local_video import cli
        with tempfile.TemporaryDirectory() as folder:
            config, project = self._project(folder)
            with patch.object(cli.QueueRunner, "run", side_effect=lambda m, shots=None: m) as run, \
                    patch.object(cli, "PipelineConfig", return_value=config):
                cli.main(["run", str(project.project_dir), "--shots", "1", "--redo"])
            passed = run.call_args.kwargs.get("shots") or run.call_args.args[1]
            self.assertEqual({1}, passed)
            reloaded = json.loads((Path(project.project_dir) / "project.json").read_text(encoding="utf-8"))
            self.assertEqual("pending", reloaded["shots"][0]["status"])   # archived, will re-render
            self.assertEqual("", reloaded["shots"][0]["degraded"])

    def test_without_redo_an_accepted_shot_is_left_alone(self):
        from local_video import cli
        with tempfile.TemporaryDirectory() as folder:
            config, project = self._project(folder)
            with patch.object(cli.QueueRunner, "run", side_effect=lambda m, shots=None: m), \
                    patch.object(cli, "PipelineConfig", return_value=config):
                cli.main(["run", str(project.project_dir), "--shots", "1"])
            reloaded = json.loads((Path(project.project_dir) / "project.json").read_text(encoding="utf-8"))
            self.assertEqual("accepted", reloaded["shots"][0]["status"])  # reused, as before

    def test_a_run_finished_from_the_cli_writes_post_text_next_to_the_video(self):
        """A resume after a crash finishes the render here, not in main.py, so it must write the post text."""
        from local_video import cli
        with tempfile.TemporaryDirectory() as folder:
            config, project = self._project(folder)
            final = Path(project.project_dir) / "final.mp4"

            def finish(manifest, shots=None):
                final.write_bytes(b"video")
                manifest.state = "completed"
                return manifest

            with patch.object(cli.QueueRunner, "run", side_effect=finish), \
                    patch.object(cli, "PipelineConfig", return_value=config), \
                    patch("agents.post_text.write", return_value="final_post.txt") as write:
                cli.main(["resume", str(project.project_dir)])
            write.assert_called_once()
            self.assertEqual(str(final), write.call_args.args[1])
            self.assertEqual(project.script["video_title"], write.call_args.args[0]["video_title"])

    def test_an_unfinished_run_writes_no_post_text(self):
        from local_video import cli
        with tempfile.TemporaryDirectory() as folder:
            config, project = self._project(folder)
            with patch.object(cli.QueueRunner, "run", side_effect=lambda m, shots=None: m), \
                    patch.object(cli, "PipelineConfig", return_value=config), \
                    patch("agents.post_text.write") as write:
                cli.main(["resume", str(project.project_dir)])
            write.assert_not_called()

    def test_redo_without_shots_is_refused_rather_than_wiping_the_project(self):
        import contextlib
        import io as _io
        from local_video import cli
        with tempfile.TemporaryDirectory() as folder:
            config, project = self._project(folder)
            stderr = _io.StringIO()
            with patch.object(cli.QueueRunner, "run") as run, \
                    patch.object(cli, "PipelineConfig", return_value=config), \
                    contextlib.redirect_stderr(stderr):
                self.assertEqual(2, cli.main(["run", str(project.project_dir), "--redo"]))
            run.assert_not_called()
            self.assertIn("--redo needs --shots", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
