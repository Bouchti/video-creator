"""--source evolution: the problem -> solution ladder filmed by the local AI (MiniMax H3 via FreeVideo only)
and finished with a Real-ESRGAN upscale. No GPU, no paid APIs."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _beat(text, scene, kind="Wide shot"):
    return {"text": text, "visual": {"kind": "scene", "description": f"{kind}: {text}", "scene": scene}}


def _ladder(**extra):
    beats = [
        _beat("Your bridge: three planks over a stream.", "plank bridge"),
        _beat("Then a wagon of stone rolls on.", "plank bridge", "Close-up"),
        _beat("So you build a stone arch.", "stone arch bridge"),
        _beat("Then the railway comes.", "stone arch bridge", "Close-up"),
        _beat("So you brace it with steel triangles.", "steel truss bridge"),
        _beat("Then the river must stay open to ships.", "steel truss bridge"),
        _beat("So you hang the deck from cables. Which would you cross?", "suspension bridge"),
    ]
    return {"beats": beats, "characters": [], "content_mode": "evolution", **extra}


class ScriptModeTests(unittest.TestCase):
    def test_evolution_uses_the_documentary_production_bible(self):
        from agents.script import build_script_tool
        schema = build_script_tool(22, 115, 156, "local-ai", "evolution")["input_schema"]
        self.assertEqual(schema["properties"]["characters"]["minItems"], 0)
        for key in ("location", "recurring_objects", "screen_geography", "story_premise"):
            self.assertIn(key, schema["required"])
        self.assertIn("real subject", schema["properties"]["story_premise"]["description"])

    def test_the_system_prompt_keeps_every_fact_rule_and_adds_the_ladder(self):
        from agents.script import BEATS_LOCAL_AI_DOCUMENTARY, BEATS_LOCAL_AI_EVOLUTION, system_prompt
        prompt = system_prompt("local-ai", "evolution")
        self.assertIn(BEATS_LOCAL_AI_DOCUMENTARY, prompt)
        self.assertIn(BEATS_LOCAL_AI_EVOLUTION, prompt)
        self.assertNotIn(BEATS_LOCAL_AI_EVOLUTION, system_prompt("local-ai", "documentary"))

    def test_generate_script_accepts_evolution_and_keeps_its_evidence_rules(self):
        from agents import script as sc
        answer = {"beats": [{"text": "Your bridge: three planks.", "visual": {"kind": "scene"}}]}
        with patch.object(sc.llm, "ask", return_value=answer) as ask:
            out = sc.generate_script("bridges", target_seconds=65, mode="local-ai", content_mode="evolution",
                                     research=[{"url": "u"}], excluded_claims=["a made-up span"])
        system, prompt = ask.call_args.args[:2]
        self.assertIn("EVOLUTION FORMAT", system)
        self.assertIn("TREAT THE TOPIC LINE AS A LEAD", prompt)
        self.assertIn("a made-up span", prompt)
        self.assertEqual(out["content_mode"], "evolution")
        self.assertEqual(out["spoken_script"], "Your bridge: three planks.")

    def test_unknown_content_mode_is_refused(self):
        from agents import script as sc
        with self.assertRaises(ValueError):
            sc.generate_script("x", mode="local-ai", content_mode="musical")


class EvaluatorTests(unittest.TestCase):
    def test_evolution_scripts_get_the_ladder_rubric(self):
        from agents import evaluator as ev
        with patch.object(ev.llm, "ask", return_value={"verdict": "PASS", "issues": []}) as ask:
            ev.evaluate_script(_ladder(spoken_script="x"), source="evolution")
        self.assertIs(ask.call_args.args[0], ev.LOCAL_AI_EVOLUTION_EVALUATOR_PROMPT)
        self.assertTrue(ev.LOCAL_AI_EVOLUTION_EVALUATOR_PROMPT.startswith(ev.LOCAL_AI_DOCUMENTARY_EVALUATOR_PROMPT))

    def test_a_good_ladder_passes_the_free_check(self):
        from agents.evaluator import evolution_feedback
        self.assertIsNone(evolution_feedback(_ladder()))
        self.assertIsNone(evolution_feedback({"beats": [], "content_mode": "documentary"}))

    def test_the_free_check_catches_a_shown_builder_a_short_ladder_and_one_place(self):
        from agents.evaluator import evolution_feedback
        script = _ladder(characters=[{"name": "Builder", "look": "hard hat"}])
        script["beats"] = [_beat("So you build it.", "bridge"), _beat("Then rain.", "bridge")]
        problem = evolution_feedback(script)
        self.assertIn("characters", problem)
        self.assertIn("only 1 beat", problem)
        self.assertIn("only 1 scene label", problem)


class LeaderTests(unittest.TestCase):
    def test_evolution_searches_design_ladders_not_the_channel_queries(self):
        from agents import leader
        # The photo look's design histories (the cutaway look's searches: tests/test_cutaway_look.py).
        with patch.object(leader, "channel_profile", return_value="history stories"), \
                patch.object(leader, "_search", return_value=[]) as search, \
                patch.dict(os.environ, {"EVOLUTION_LOOK": "photo"}):
            leader.search_trending_subjects(source="evolution")
        queries = search.call_args.args[0]
        self.assertTrue(set(queries) <= set(leader.EVOLUTION_QUERIES))
        self.assertIsNone(search.call_args.kwargs["time_range"])

    def test_evolution_topics_follow_the_ladder_and_realism_rules(self):
        from agents import leader
        pick = {"topic": "Dams went from earth banks to arch dams.", "subject": "dam", "angle": "story_behind",
                "tone": "epic"}
        with patch.object(leader, "channel_profile", return_value="history stories"), \
                patch.object(leader.llm, "ask", return_value=pick) as ask:
            leader.pick_topic([{"title": "t"}], [], source="evolution")
        system, prompt = ask.call_args.args[:2]
        self.assertIs(system, leader.MECHANISM_LEADER_PROMPT)
        self.assertIn("EVOLUTION LADDER", prompt)
        self.assertIn("AI-VIDEO REALISM", prompt)
        self.assertNotIn("history stories", prompt)


class LadderResearchTests(unittest.TestCase):
    def test_every_rung_is_searched_and_only_search_results_become_evidence(self):
        from agents import leader
        plan = {"stages": [{"design": "plank bridge", "era": "prehistory", "search": "plank q"},
                           {"design": "stone arch", "era": "Roman", "search": "arch q"},
                           {"design": "iron girder", "era": "1840s", "search": "girder q"}]}
        results = {"plank q": [{"url": "a", "content": "planks"}],
                   "arch q": [{"url": "known", "content": "dup"}, {"url": "b", "content": "arches"}],
                   "girder q": RuntimeError("tavily down")}

        def search(query, **_):
            if isinstance(results[query], Exception):
                raise results[query]
            return {"results": results[query]}

        with patch.object(leader.llm, "ask", return_value=plan), \
                patch.object(leader.tavily, "search", side_effect=search):
            pack = leader.research_ladder("bridges", [{"url": "known", "evidence": "topic"}])
        self.assertEqual([s["url"] for s in pack], ["known", "a", "b"])
        self.assertEqual(pack[0]["evidence"], "topic")
        self.assertEqual(pack[2]["stage"], "stone arch (Roman)")


class RoutingTests(unittest.TestCase):
    def _run(self, folder, **kwargs):
        import main
        video = Path(folder) / "final.mp4"
        video.write_bytes(b"v")
        editor = MagicMock(return_value=str(video))
        evaluate = MagicMock(return_value={"video_title": "Bridges", "description": "d", "hashtags": [],
                                           "spoken_script": "one two"})
        with patch.object(main, "OUTPUT_DIR", folder), \
                patch.object(main, "minimax_preflight", return_value=None), \
                patch("agents.leader.research_topic", return_value=[{"url": "u"}]), \
                patch("agents.leader.research_ladder", return_value=[{"url": "u"}, {"url": "rung"}]) as ladder, \
                patch("agents.evaluator.evaluate_with_retry", evaluate), \
                patch("agents.editor_local_ai.process_video", editor), \
                patch("agents.post_text.write", return_value="post.txt"), \
                patch("agents.autopilot.run") as autopilot:
            result = main.run_pipeline("bridges", source="evolution", duration=65, **kwargs)
        autopilot.assert_not_called()
        ladder.assert_called_once_with("bridges", [{"url": "u"}])
        self.assertEqual(evaluate.call_args.kwargs["research"], [{"url": "u"}, {"url": "rung"}])
        return result, editor, evaluate

    def test_evolution_is_written_as_a_ladder_and_filmed_by_minimax(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"EVOLUTION_UPSCALE": ""}):
            result, editor, evaluate = self._run(folder, backend="wan")
        self.assertTrue(result["success"])
        self.assertEqual(evaluate.call_args.kwargs["content_mode"], "evolution")
        self.assertEqual(evaluate.call_args.kwargs["mode"], "local-ai")
        self.assertEqual(editor.call_args.kwargs["backend"], "minimax")
        self.assertIsNone(editor.call_args.kwargs["ai_upscale"])     # the local-ai default (x2plus) applies
        self.assertIn("_evolution_Bridges", Path(result["video_path"]).name)

    def test_the_upscale_model_can_be_changed_or_switched_off(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"EVOLUTION_UPSCALE": "off"}):
            _, editor, _ = self._run(folder)
        self.assertEqual(editor.call_args.kwargs["ai_upscale"], "off")

    def test_a_missing_freevideo_stops_the_run_before_any_paid_step(self):
        import main
        with patch.object(main, "minimax_preflight", return_value="FreeVideo missing"), \
                patch("agents.evaluator.evaluate_with_retry") as evaluate:
            result = main.run_pipeline("bridges", source="evolution", duration=65)
        self.assertEqual(result["stage_failed"], "minimax_preflight")
        evaluate.assert_not_called()

    def test_preflight_names_what_freevideo_is_missing(self):
        import main
        config = SimpleNamespace(minimax_url=None)
        with patch("local_video.config.PipelineConfig", return_value=config), \
                patch.dict(os.environ, {"FREEVIDEO_DIR": tempfile.gettempdir()}):
            problem = main.minimax_preflight()
        self.assertIn("engine Python", problem)
        with patch("local_video.config.PipelineConfig", return_value=SimpleNamespace(minimax_url="http://x")):
            self.assertIsNone(main.minimax_preflight())


class SubjectTests(unittest.TestCase):
    def test_a_subject_is_never_filmed_twice(self):
        from agents.leader import evolution_subject_problem, used_evolution_subjects
        used = used_evolution_subjects([{"topic": "t", "subject": "Lighthouses"}, {"topic": "old"}])
        self.assertEqual(used, ["bridge", "Lighthouses"])
        self.assertIn("already filmed", evolution_subject_problem("suspension bridge", used))
        self.assertIn("already filmed", evolution_subject_problem("lighthouse", used))
        self.assertIsNone(evolution_subject_problem("dam", used))
        self.assertIsNone(evolution_subject_problem("harbour wall", ["castle wall"]))
        self.assertIn("no subject", evolution_subject_problem("", used))

    def test_a_repeated_subject_is_rejected_and_the_leader_picks_again(self):
        from agents import leader
        picks = iter([{"topic": "Bridges again", "subject": "arch bridge", "angle": "a", "tone": "epic"},
                      {"topic": "Lighthouses went from fires to towers", "subject": "lighthouse",
                       "angle": "a", "tone": "epic"}])
        with patch.object(leader.llm, "ask", side_effect=lambda *a, **k: next(picks)) as ask:
            selection = leader.pick_topic([{"title": "t"}], [], source="evolution")
        self.assertEqual(selection["subject"], "lighthouse")
        schema = ask.call_args.args[2]
        self.assertIn("subject", schema["required"])
        self.assertIn("arch bridge", ask.call_args.args[1])                   # told why the first was refused
        self.assertIn("ALREADY FILMED AS EVOLUTION VIDEOS", ask.call_args.args[1])

    def test_the_finished_film_records_its_subject(self):
        import main
        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / "final.mp4"
            video.write_bytes(b"v")
            pick = {"topic": "Dams", "subject": "dam", "tone": "epic", "angle": "a", "research": [{"url": "u"}]}
            with patch.object(main, "OUTPUT_DIR", folder), \
                    patch.object(main, "minimax_preflight", return_value=None), \
                    patch("agents.leader.find_todays_topic", return_value=pick), \
                    patch("agents.leader.research_ladder", return_value=[{"url": "u"}]), \
                    patch("agents.leader.save_used_topic") as save, \
                    patch("agents.evaluator.evaluate_with_retry", return_value={
                        "video_title": "Dams", "description": "d", "hashtags": [], "spoken_script": "x"}), \
                    patch("agents.editor_local_ai.process_video", return_value=str(video)), \
                    patch("agents.post_text.write", return_value="post.txt"):
                main.run_pipeline(source="evolution", duration=65)
        save.assert_called_once_with("Dams", subject="dam")


class UpscaleTests(unittest.TestCase):
    def test_local_ai_upscales_with_x2plus_by_default(self):
        from local_video.upscale import upscale_model_name
        with patch.dict(os.environ):
            os.environ.pop("LOCAL_VIDEO_AI_UPSCALE", None)
            self.assertEqual(upscale_model_name(SimpleNamespace(settings={})), "x2plus")

    def test_model_choice(self):
        from local_video.upscale import upscale_model_name
        manifest = SimpleNamespace(settings={"ai_upscale": "x2plus"})
        with patch.dict(os.environ, {"LOCAL_VIDEO_AI_UPSCALE": "0"}):
            self.assertEqual(upscale_model_name(manifest), "x2plus")
            self.assertIsNone(upscale_model_name(SimpleNamespace(settings={})))
            self.assertIsNone(upscale_model_name(SimpleNamespace(settings={"ai_upscale": "off"})))
            self.assertIsNone(upscale_model_name(SimpleNamespace(settings={"ai_upscale": "x9"})))
        with patch.dict(os.environ, {"LOCAL_VIDEO_AI_UPSCALE": "1"}):
            self.assertEqual(upscale_model_name(SimpleNamespace(settings={})), "general-x4v3")
            self.assertIsNone(upscale_model_name(SimpleNamespace(settings={"ai_upscale": "off"})))

    def test_x2plus_runs_the_rrdb_network_at_2x_and_caches_per_model(self):
        from local_video import upscale
        with tempfile.TemporaryDirectory() as folder:
            clip = Path(folder) / "shots" / "shot-001.mp4"
            clip.parent.mkdir()
            clip.write_bytes(b"clip")
            manifest = SimpleNamespace(project_dir=folder, settings={"ai_upscale": "x2plus"},
                                       shots=[SimpleNamespace(id="shot-001", output="shots/shot-001.mp4")])
            python = Path(folder) / "python.exe"
            python.write_bytes(b"")
            target = Path(folder) / "render" / "upscaled" / upscale.upscaled_name(clip, "x2plus")
            self.assertIn("x2plus", target.name)
            self.assertNotEqual(target.name, upscale.upscaled_name(clip))

            def worker(command, **_):
                target.with_suffix(".part.mp4").write_bytes(b"sharp")
                return SimpleNamespace(returncode=0, stderr="", stdout=json.dumps({"source": str(clip)}))

            with patch.object(upscale, "engine_python", return_value=python), \
                    patch.object(upscale, "ensure_model", return_value=Path("x2.pth")) as ensure, \
                    patch.object(upscale, "stop_idle_freevideo_worker"), \
                    patch.object(upscale.subprocess, "run", side_effect=worker) as run:
                clips = upscale.upscale_clips(manifest, SimpleNamespace(ffmpeg="ffmpeg"))
            ensure.assert_called_once_with("x2plus")
            command = run.call_args.args[0]
            self.assertEqual(command[command.index("--arch") + 1], "rrdb")
            self.assertEqual(command[command.index("--scale") + 1], "2")
            self.assertEqual({"shot-001": target}, clips)
            self.assertEqual(target.read_bytes(), b"sharp")


if __name__ == "__main__":
    unittest.main()
