import copy
import unittest

from agents import director


def _plan():
    beats = [{"id": f"b{k}", "text": "Max talks.", "shot": {"frame": "wide", "on": "family", "move": "static"},
              "cast": [{"who": "Max", "do": "talk", "at": "Max"}], "events": []} for k in range(4)]
    return {"world": "stage", "id": "t", "place": {"ground": "grass"}, "props": [], "assets": {}, "beats": beats}


TIMING = {"fps": 30, "total": 400, "beats": [{"id": f"b{k}", "f0": 1 + 100 * k, "f1": 100 * (k + 1), "cues": {}}
                                             for k in range(4)]}


def changed(a, b):
    ka, kb = director.beat_keys(a, TIMING, False), director.beat_keys(b, TIMING, False)
    return [bid for bid in ka if ka[bid] != kb[bid]]


class BeatKeysTest(unittest.TestCase):
    def test_a_new_shot_rerenders_only_its_beat(self):
        p = _plan()
        q = copy.deepcopy(p)
        q["beats"][2]["shot"]["frame"] = "close"
        self.assertEqual(changed(p, q), ["b2"])

    def test_an_action_rerenders_its_beat_and_where_it_still_plays(self):
        p = _plan()
        q = copy.deepcopy(p)
        q["beats"][1]["cast"][0]["do"] = "dance"      # Max dances on until his next cue, in b2
        self.assertEqual(changed(p, q), ["b1", "b2"])

    def test_a_walk_moves_the_character_for_every_later_beat(self):
        p = _plan()
        q = copy.deepcopy(p)
        q["beats"][1]["cast"][0]["to"] = "left"
        self.assertEqual(changed(p, q), ["b1", "b2", "b3"])

    def test_a_hook_burst_rerenders_only_the_hook_and_its_spill(self):
        p = _plan()
        q = copy.deepcopy(p)
        q["beats"][0]["events"] = [{"prop": "pot", "does": "steam_burst", "at": "start"}]
        self.assertEqual(changed(p, q), ["b0", "b1"])

    def test_a_prop_appearing_later_changes_every_beat(self):
        p = _plan()
        q = copy.deepcopy(p)
        q["beats"][3]["events"] = [{"prop": "pot", "does": "appear", "at": "Max"}]
        self.assertEqual(changed(p, q), ["b0", "b1", "b2", "b3"])

    def test_narration_text_alone_changes_nothing(self):
        p = _plan()
        q = copy.deepcopy(p)
        q["beats"][0]["text"] = "Max talks a lot."
        self.assertEqual(changed(p, q), [])

    def test_set_change_rerenders_everything(self):
        p = _plan()
        q = copy.deepcopy(p)
        q["place"]["ground"] = "sand"
        self.assertEqual(len(changed(p, q)), 4)


if __name__ == "__main__":
    unittest.main()
