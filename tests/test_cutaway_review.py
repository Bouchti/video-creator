"""Fixes from the review of the undersea-tunnel film (docs/CUTAWAY_FIX_PLAN.md): Max seemed to speak the
narration, birdsong played under the sea, and three text systems stacked on each other."""
import os
import unittest

from agents.set_builder import mouth_problems

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class NarratorOnlyTests(unittest.TestCase):
    def test_a_mouth_moving_with_the_narration_is_a_static_problem(self):
        src = '''
class S:
    def explain(self, b, e):
        for f in range(b, e, 5):
            self.max.key("mouth", f, scale=(0.9, 0.6, 2.0))
        self.kid.lipsync(b, e, self.envelope)
'''
        problems = mouth_problems(src)
        self.assertEqual(len(problems), 2)
        self.assertIn("line 5", problems[0])
        self.assertIn("lipsync", problems[1])

    def test_one_shout_or_gasp_is_fine(self):
        src = '''
def gasp(m, f0, f1):
    m.key("mouth", f0 + 4, scale=(1.3, 0.6, 3.4))
    m.key("mouth", f1, scale=(0.7, 0.6, 1.0))
'''
        self.assertEqual(mouth_problems(src), [])

    def test_one_gasp_per_kid_in_a_loop_over_the_kids_is_fine(self):
        # the sandcastle kids cheer once each: a loop over characters, not over time
        src = '''
def cheer(self, h0, h1):
    for k, kid in enumerate(self.kids):
        kid.key("mouth", h0, scale=(0.7, 0.6, 1.0))
        kid.key("mouth", h0 + 4, scale=(1.2, 0.6, 2.6))
'''
        self.assertEqual(mouth_problems(src), [])
        src_time = '''
def chatter(self, kids, b, e):
    for kid in kids:
        for f in range(b, e, 6):
            kid.key("mouth", f, scale=(1.2, 0.6, 2.6))
'''
        self.assertEqual(len(mouth_problems(src_time)), 1)

    def test_talk_keeps_the_mouth_shut(self):
        # the tunnel set called max.talk() while the narrator spoke: the flapping mouth read as Max talking
        src = open(os.path.join(ROOT, "engine", "character.py"), encoding="utf-8").read()
        body = src[src.index("    def talk("):src.index("    def look(")]
        mouth = [line for line in body.splitlines() if '"mouth"' in line]
        self.assertTrue(mouth)
        self.assertTrue(all("(0.7, 0.6, 1.0)" in line for line in mouth), mouth)

    def test_no_registered_set_moves_a_mouth_with_the_narration(self):
        import glob
        for path in glob.glob(os.path.join(ROOT, "engine", "sets", "*.py")):
            self.assertEqual(mouth_problems(open(path, encoding="utf-8").read()), [], path)


class AmbienceTests(unittest.TestCase):
    def test_each_scene_gets_the_bed_of_where_it_is(self):
        from agents.sfx import scene_ambience
        self.assertEqual(scene_ambience({"shows": "Max's shovel tunnel under the sea floods with mud"}), "underwater")
        self.assertEqual(scene_ambience({"shows": "A grab dredger scoops the soft seabed out"}), "underwater")
        self.assertEqual(scene_ambience({"shows": "Max drives his family car through the dry tunnel."}), "indoor")
        self.assertEqual(scene_ambience({"shows": "a sealed concrete tunnel block floats across the sea"}), "water")
        self.assertEqual(scene_ambience({"shows": "Max digs a hole in his backyard"}), "outdoor")
        self.assertEqual(scene_ambience({"kind": "rewind", "shows": "the story plays backwards"}), "none")
        self.assertEqual(scene_ambience({"shows": "under the sea", "ambience": "indoor"}), "indoor")   # the set says

    def test_a_sea_set_never_falls_back_to_birdsong(self):
        from agents.sfx import AMBIENCES, scene_ambience, set_ambience
        from engine.sets import spec
        sp = spec("immersed_undersea_tunnel_con_story")
        default = set_ambience(sp.SUBJECT)
        for name, action in sp.ACTIONS.items():
            where = scene_ambience(action, default)
            self.assertNotIn("birds", [layer[0] for layer in AMBIENCES[where]], name)

    def test_the_same_one_shot_in_quick_succession_plays_once(self):
        from agents.sfx import _thin
        events = [{"frame": f, "kind": "steel_clank"} for f in (10, 16, 22, 40)] + \
                 [{"frame": 12, "kind": "pour", "duration": 60}, {"frame": 14, "kind": "boing"}]
        kept = _thin(events, 30)
        self.assertEqual([e["frame"] for e in kept if e["kind"] == "steel_clank"], [10, 40])
        self.assertEqual(len(kept), 4)

    def test_beds_follow_the_scenes(self):
        import tempfile
        import numpy as np
        from agents import sfx
        from agents.media import read_pcm
        path = os.path.join(tempfile.mkdtemp(), "fx.wav")
        sfx.render_events([], 30, 6.0, path, scenes=[(0, 3, "outdoor"), (3, 6, "indoor")])
        x = read_pcm(path, 44100)
        loud = lambda a, b: float(np.sqrt(np.mean(x[int(a * 44100):int(b * 44100)] ** 2)))   # noqa: E731
        self.assertGreater(loud(0.5, 2.5), 10 * loud(3.5, 5.5))         # indoors: no bed at all


class OneTextPerIdeaTests(unittest.TestCase):
    SET = "immersed_undersea_tunnel_con_story"

    def test_a_sticker_repeating_the_scenes_label_is_dropped(self):
        from engine.sets import repeats_label, scene_labels
        seal = scene_labels(self.SET, ["fix_seal"])
        self.assertTrue(repeats_label({"type": "label", "text": "Rubber gasket"}, seal))
        self.assertTrue(repeats_label({"type": "stat", "value": "4 atm", "text": "at 40 m deep"},
                                      scene_labels(self.SET, ["fail_dig"])))
        self.assertFalse(repeats_label({"type": "label", "text": "Rock armour"}, scene_labels(self.SET, ["fix_armor"])))
        self.assertFalse(repeats_label({"type": "none"}, seal))

    def test_only_the_beats_own_labels_count(self):
        from engine.sets import repeats_label, scene_labels
        # RUBBER GASKET is drawn in fix_seal only: a sticker in another beat is the only text there
        self.assertFalse(repeats_label({"type": "label", "text": "Rubber gasket"}, scene_labels(self.SET, ["goal"])))

    def test_the_film_json_never_carries_both(self):
        from agents import showrunner
        script = {"title": "t", "beats": [
            {"actions": ["float_hook"], "text": "x", "overlay": {"type": "none", "value": "", "text": ""}},
            {"actions": ["fix_seal"], "text": "y. Would you?", "overlay": {"type": "label", "value": "",
                                                                          "text": "Rubber gasket"}}]}
        film = showrunner.to_film(script, {"set": self.SET, "angle": "a"}, "facts")
        self.assertNotIn("overlay", film["beats"][1])


class HookGateTests(unittest.TestCase):
    def test_the_films_first_window_is_judged_as_the_hook(self):
        from agents import scene_validator as sv
        from engine.sets import spec
        sp = spec("immersed_undersea_tunnel_con_story")
        film = {"beats": [{"action": "float_hook", "text": "h"}, {"action": "rewind", "text": "r"},
                          {"action": "goal", "text": "g"}]}
        spans = [{"start": 0, "end": 179}, {"start": 180, "end": 239}, {"start": 240, "end": 419}]
        ws = sv.plan_windows(film, spans, spec=sp)
        self.assertEqual([w["hook"] for w in ws], [True] + [False] * (len(ws) - 1))
        rubric = sv._instructions(ws[0], "s", None)
        self.assertIn("FIRST SECOND, THE HOOK", rubric)
        self.assertNotIn("never fault the absence", rubric.lower())         # the start still IS the hook
        self.assertNotIn("THE HOOK", sv._instructions(ws[1], "s", None))

    def test_a_film_that_opens_on_a_build_step_has_no_hook_window(self):
        from agents import scene_validator as sv
        from engine.sets import spec
        film = {"beats": [{"action": "dig", "text": "If you dig a hole"}]}
        self.assertFalse(sv.plan_windows(film, [{"start": 0, "end": 89}], spec=spec("pool"))[0]["hook"])


class MixTests(unittest.TestCase):
    def test_the_mix_with_effects_ducked_under_the_voice_lands_on_target(self):
        import tempfile
        import numpy as np
        from agents.audio_fx import LOUDNESS_TARGET, loudness, mix_audio
        from agents.media import write_wav
        d = tempfile.mkdtemp()
        t = np.arange(44100 * 8) / 44100
        voice = np.where((t % 2) < 1.2, 0.3 * np.sin(2 * np.pi * 220 * t), 0.0)      # words, then pauses
        fx = 0.2 * np.sin(2 * np.pi * 900 * t)
        v, f = write_wav(os.path.join(d, "v.wav"), voice, 44100), write_wav(os.path.join(d, "f.wav"), fx, 44100)
        out = mix_audio(v, f, os.path.join(d, "mix.m4a"), 8.0, music=None)
        self.assertLess(abs(loudness(out) - LOUDNESS_TARGET), 1.0)


if __name__ == "__main__":
    unittest.main()


class StickerClashTests(unittest.TestCase):
    def test_a_sticker_over_a_3d_label_is_dropped(self):
        import json
        import tempfile
        from engine.make_film import drop_clashing_stickers
        beats = [{"id": "a", "overlay": {"type": "stat", "value": "2 m", "text": "castle goal"}},
                 {"id": "b", "overlay": {"type": "label", "text": "Surface tension"}},
                 {"id": "c", "overlay": {"type": "stat", "value": "70", "text": "thumps"}}]
        spans = [{"start": 0, "end": 59}, {"start": 60, "end": 119}, {"start": 120, "end": 179}]
        boxes = {str(f): [[0.4, 0.15, 0.7, 0.2]] for f in range(1, 61, 2)}           # DRY SAND under "2 m"
        boxes.update({str(f): [[0.1, 0.6, 0.3, 0.65]] for f in range(61, 121, 2)})   # a label far below the pill
        boxes.update({str(f): [[0.3, 0.12, 0.6, 0.16]] for f in range(121, 129, 2)})  # a brief pop: kept
        path = os.path.join(tempfile.mkdtemp(), "text_boxes.json")
        json.dump(boxes, open(path, "w"))
        self.assertEqual(drop_clashing_stickers(beats, spans, path), ["a"])
        self.assertNotIn("overlay", beats[0])
        self.assertIn("overlay", beats[1])
        self.assertIn("overlay", beats[2])

    def test_no_measurement_keeps_every_sticker(self):
        from engine.make_film import drop_clashing_stickers
        beats = [{"id": "a", "overlay": {"type": "stat", "value": "2 m"}}]
        self.assertEqual(drop_clashing_stickers(beats, [{"start": 0, "end": 59}], "missing.json"), [])
