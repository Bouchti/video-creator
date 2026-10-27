"""Automatic topics follow the channel description, not this week's science news."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from agents import leader


class ChannelTopicTests(unittest.TestCase):
    def test_the_profile_is_the_channel_description(self):
        self.assertIn("Untold Footnotes", leader.channel_profile())

    def test_local_ai_searches_history_without_a_news_window(self):
        calls = []
        with patch.object(leader.tavily, "search", side_effect=lambda **kw: calls.append(kw) or {"results": []}):
            leader.search_trending_subjects(source="local-ai")
        self.assertEqual(len(calls), 8)                   # two per line of the description
        self.assertTrue(all("time_range" not in call for call in calls))
        joined = " ".join(call["query"] for call in calls)
        self.assertNotIn("volcano", joined)
        self.assertIn("history", joined)

    def test_every_line_of_the_description_is_searched(self):
        queries = leader._channel_queries()
        for pool in leader.CHANNEL_QUERIES.values():
            self.assertEqual(sum(query in pool for query in queries), 2)

    def test_unreal_keeps_its_mechanism_search(self):
        calls = []
        with patch.object(leader.tavily, "search", side_effect=lambda **kw: calls.append(kw) or {"results": []}):
            leader.search_trending_subjects(source="unreal")
        self.assertTrue(all(call.get("time_range") == "week" for call in calls))
        self.assertIn("engineering", " ".join(call["query"] for call in calls))

    def test_the_picker_is_given_the_channel_and_told_news_is_off_brand(self):
        seen = {}
        with patch.object(leader.ai_router, "ask", side_effect=lambda system, prompt, schema, **k:
                          seen.update(system=system, prompt=prompt) or {"topic": "Wojtek the bear"}):
            leader.pick_topic([], [], source="local-ai")
        self.assertIn("Untold Footnotes", seen["prompt"])
        self.assertIn("Current news, science explainers", seen["system"])

    def test_research_has_no_one_month_window(self):
        calls = []
        result = {"results": [{"url": f"u{i}", "content": "c"} for i in range(3)]}
        with patch.object(leader.tavily, "search", side_effect=lambda **kw: calls.append(kw) or result):
            leader.research_topic("The War of the Bucket, 1325")
        self.assertTrue(all("time_range" not in call for call in calls))

    def test_a_topic_from_last_month_is_still_remembered(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "used.json")
            old = (datetime.now() - timedelta(days=40)).isoformat()
            with open(path, "w") as f:
                json.dump([{"topic": "Wojtek the bear", "date": old}], f)
            with patch.object(leader, "USED_TOPICS_FILE", path):
                self.assertEqual([t["topic"] for t in leader.load_used_topics()], ["Wojtek the bear"])


if __name__ == "__main__":
    unittest.main()
