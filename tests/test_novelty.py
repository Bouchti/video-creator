import unittest
from unittest import mock

from agents import leader


def _judge(known, impressive=8, wow="Ice is slippery because of a liquid-like surface layer.", first="a sled flies off",
           why="The ice top is wet like a puddle. A wet floor makes you slide.",
           demo="a skate slides on an ice block, then sticks on a dry one; an arrow shows the slide"):
    return mock.patch("agents.ai_router.ask", return_value={"known_percent": known, "impressive": impressive, "impressive_why": "x", "wow": wow, "first_second": first,
                                                           "simple_why": why, "demo": demo, "verdict": "x"})


class NoveltyTest(unittest.TestCase):
    def test_common_knowledge_is_rejected(self):
        with _judge(85):
            problem, known = leader.novelty_problem("a pressure cooker cooks food faster")
        self.assertIn("common knowledge", problem)
        self.assertEqual(known, 85)

    def test_a_surprising_fact_passes(self):
        with _judge(12):
            self.assertEqual(leader.novelty_problem("ice is slippery because of a surface layer"), (None, 12))

    def test_no_visible_surprise_is_rejected(self):
        with _judge(10, first=""):
            problem, _ = leader.novelty_problem("a fact with nothing to show")
        self.assertIn("no wow fact or no visible", problem)

    def test_too_hard_to_explain_is_rejected(self):
        with _judge(8, why=""):
            problem, _ = leader.novelty_problem("hinge geometry of bicycle steering")
        self.assertIn("too hard to explain", problem)

    def test_a_why_that_cannot_be_shown_is_rejected(self):
        with _judge(8, demo=""):
            problem, _ = leader.novelty_problem("why a bike steers itself")
        self.assertIn("cannot be SHOWN", problem)

    def test_the_writer_is_briefed_with_how_to_show_it(self):
        brief = leader.director_brief("Max tries it", {"wow": "W", "demo": "a skate slides", "simple_why": ""})
        self.assertEqual(brief, "Max tries it\nTHE WOW: W\nHOW TO SHOW IT: a skate slides")

    def test_an_ordinary_subject_is_rejected(self):
        with _judge(10, impressive=5):
            problem, _ = leader.novelty_problem("why garden retaining walls tip over", need_demo=False)
        self.assertIn("not impressive enough (5/10", problem)

    def test_judge_failure_never_blocks(self):
        with mock.patch("agents.ai_router.ask", side_effect=RuntimeError("offline")):
            self.assertEqual(leader.novelty_problem("anything"), (None, 0))


if __name__ == "__main__":
    unittest.main()
