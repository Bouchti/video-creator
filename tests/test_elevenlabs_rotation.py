import os
import tempfile
import unittest
from unittest.mock import patch

from agents import editor_hailuo as h


class _Resp:
    def __init__(self, code, text="", content=b"mp3"):
        self.status_code, self.text, self.content = code, text, content


class RotationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.env = patch.dict(os.environ, {"ELEVENLABS_API_KEY": "k1", "ELEVENLABS_API_KEY_2": "k2",
                                           "ELEVENLABS_API_KEY_3": "k3", "ELEVENLABS_API_KEY_4": ""})
        self.env.start()
        self.state = patch.object(h, "_ROTATION_FILE", os.path.join(self.tmp, "rot.json"))
        self.state.start()

    def tearDown(self):
        self.env.stop()
        self.state.stop()

    def test_keys_in_order_skip_blank(self):
        self.assertEqual([n for n, _ in h._elevenlabs_keys()],
                         ["ELEVENLABS_API_KEY", "ELEVENLABS_API_KEY_2", "ELEVENLABS_API_KEY_3"])

    def test_quota_error_falls_through_and_sticks(self):
        calls = []

        def post(url, json, headers, timeout):
            calls.append(headers["xi-api-key"])
            if headers["xi-api-key"] == "k1":
                return _Resp(401, '{"detail":{"status":"quota_exceeded"}}')
            return _Resp(200)

        with patch.object(h, "_credits_left", return_value=None), patch.object(h.requests, "post", post):
            h._tts_with_rotation("u", {}, 100)
            self.assertEqual(calls, ["k1", "k2"])
            calls.clear()
            h._tts_with_rotation("u", {}, 100)          # next run starts on the key that worked
            self.assertEqual(calls, ["k2"])

    def test_skips_key_without_enough_credits(self):
        calls = []

        def post(url, json, headers, timeout):
            calls.append(headers["xi-api-key"])
            return _Resp(200)

        left = {"k1": 50, "k2": None, "k3": 5000}
        with patch.object(h, "_credits_left", side_effect=lambda k: left[k]), patch.object(h.requests, "post", post):
            h._tts_with_rotation("u", {}, 1000)
        self.assertEqual(calls, ["k2"])

    def test_wraps_around(self):
        h._rotation_save(2)
        calls = []

        def post(url, json, headers, timeout):
            calls.append(headers["xi-api-key"])
            return _Resp(401, "quota_exceeded") if headers["xi-api-key"] == "k3" else _Resp(200)

        with patch.object(h, "_credits_left", return_value=None), patch.object(h.requests, "post", post):
            h._tts_with_rotation("u", {}, 10)
        self.assertEqual(calls, ["k3", "k1"])

    def test_all_exhausted_raises(self):
        with patch.object(h, "_credits_left", return_value=None), \
                patch.object(h.requests, "post", lambda *a, **k: _Resp(401, "quota_exceeded")):
            with self.assertRaises(Exception) as ctx:
                h._tts_with_rotation("u", {}, 10)
        self.assertIn("All ElevenLabs keys", str(ctx.exception))
        self.assertNotIn("k1", str(ctx.exception).replace("ELEVENLABS", ""))   # never leak key values


if __name__ == "__main__":
    unittest.main()
