import os
import tempfile
import unittest
from unittest.mock import patch

from agents import voice as h


class _Resp:
    def __init__(self, code, text="", content=b"mp3"):
        self.status_code, self.text, self.content = code, text, content


class RotationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        keys = {f"ELEVENLABS_API_KEY_{k}": "" for k in range(4, 21)}       # the real .env may define more keys
        keys.update({"ELEVENLABS_API_KEY": "k1", "ELEVENLABS_API_KEY_2": "k2", "ELEVENLABS_API_KEY_3": "k3"})
        self.env = patch.dict(os.environ, keys)
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


class EdgeFallbackTests(unittest.TestCase):
    def test_edge_provider_never_touches_elevenlabs_even_when_keys_exist(self):
        from agents import voice
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "real-key", "VOICE_PROVIDER": "edge"}), \
                patch.object(voice, "_elevenlabs_voiceover",
                             side_effect=AssertionError("ElevenLabs must not be called")), \
                patch.object(voice, "_edge_voiceover", return_value="edge.mp3") as edge, \
                patch.object(voice, "get_duration", return_value=8.0):
            self.assertEqual(voice.generate_voiceover("Hello there."), ("edge.mp3", 8.0))
        edge.assert_called_once_with("Hello there.", "energetic")

    def test_out_of_credits_everywhere_falls_back_to_edge(self):
        from agents import voice
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "k", "VOICE_FALLBACK": "edge"}), \
                patch.object(voice, "_elevenlabs_voiceover",
                             side_effect=RuntimeError("All ElevenLabs keys are out of credits or unusable: x")), \
                patch.object(voice, "_edge_voiceover", return_value="edge.mp3") as edge, \
                patch.object(voice, "get_duration", return_value=8.0):
            self.assertEqual(voice.generate_voiceover("Hello there.", "energetic"), ("edge.mp3", 8.0))
        edge.assert_called_once_with("Hello there.", "energetic")

    def test_other_elevenlabs_errors_and_a_disabled_fallback_still_fail_loudly(self):
        from agents import voice
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "k", "VOICE_FALLBACK": "edge"}), \
                patch.object(voice, "_elevenlabs_voiceover", side_effect=RuntimeError("ElevenLabs failed (x): 500")), \
                patch.object(voice, "_edge_voiceover") as edge:
            with self.assertRaises(RuntimeError):
                voice.generate_voiceover("Hello.")
        edge.assert_not_called()
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "k", "VOICE_FALLBACK": "none"}), \
                patch.object(voice, "_elevenlabs_voiceover",
                             side_effect=RuntimeError("All ElevenLabs keys are out of credits or unusable: x")), \
                patch.object(voice, "_edge_voiceover") as edge:
            with self.assertRaises(RuntimeError):
                voice.generate_voiceover("Hello.")
        edge.assert_not_called()

    def test_out_of_credits_falls_back_to_chatterbox_and_edge_only_if_chatterbox_fails(self):
        from agents import voice
        out = RuntimeError("All ElevenLabs keys are out of credits or unusable: x")
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "k", "VOICE_FALLBACK": "chatterbox", "VOICE_PROVIDER": ""}), \
                patch.object(voice, "_elevenlabs_voiceover", side_effect=out), \
                patch.object(voice, "_chatterbox_voiceover", return_value="cb.mp3") as chatterbox, \
                patch.object(voice, "_edge_voiceover") as edge, \
                patch.object(voice, "get_duration", return_value=8.0):
            self.assertEqual(voice.generate_voiceover("Hello there.", "energetic"), ("cb.mp3", 8.0))
        chatterbox.assert_called_once_with("Hello there.", "energetic")
        edge.assert_not_called()
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "k", "VOICE_FALLBACK": "chatterbox", "VOICE_PROVIDER": ""}), \
                patch.object(voice, "_elevenlabs_voiceover", side_effect=out), \
                patch.object(voice, "_chatterbox_voiceover", side_effect=RuntimeError("CUDA out of memory")), \
                patch.object(voice, "_edge_voiceover", return_value="edge.mp3"), \
                patch.object(voice, "get_duration", return_value=8.0):
            self.assertEqual(voice.generate_voiceover("Hello there."), ("edge.mp3", 8.0))

    def test_kokoro_comes_first_with_the_style_voice_and_the_next_free_voice_covers_it(self):
        from agents import voice
        out = RuntimeError("All ElevenLabs keys are out of credits or unusable: x")
        settings = {}

        def run(engine, python, chosen, script):
            settings.update(chosen)
            return "kokoro.mp3"

        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "k", "VOICE_FALLBACK": "kokoro", "VOICE_PROVIDER": "",
                                     "KOKORO_VOICE": ""}), \
                patch.object(voice, "_elevenlabs_voiceover", side_effect=out), \
                patch.object(voice, "kokoro_available", return_value=True), \
                patch.object(voice, "_run_local_tts", side_effect=run), \
                patch.object(voice, "get_duration", return_value=8.0):
            self.assertEqual(("kokoro.mp3", 8.0), voice.generate_voiceover("Hello there.", "mysterious"))
            self.assertEqual("am_michael", settings["voice"])
            voice.generate_voiceover("Hello there.", "energetic")
            self.assertEqual("af_bella", settings["voice"])
        with patch.dict(os.environ, {"VOICE_PROVIDER": "kokoro"}), \
                patch.object(voice, "_kokoro_voiceover", side_effect=RuntimeError("not installed")), \
                patch.object(voice, "_chatterbox_voiceover", return_value="cb.mp3"), \
                patch.object(voice, "get_duration", return_value=8.0):
            self.assertEqual(("cb.mp3", 8.0), voice.generate_voiceover("Hello there."))

    def test_chatterbox_job_keeps_the_beat_pauses(self):
        import json as json_module
        from agents import voice
        jobs = []

        def run(command, **kwargs):
            if command[0].endswith("python.exe") or command[1].endswith("chatterbox_worker.py"):
                job = json_module.load(open(command[2], encoding="utf-8"))
                jobs.append(job)
                open(job["output"], "wb").write(b"wav")
                return type("Done", (), {"returncode": 0, "stdout": '{"device": "cpu"}', "stderr": ""})()
            open(command[-1], "wb").write(b"mp3")
            return type("Done", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        with patch.object(voice, "chatterbox_available", return_value=True), \
                patch("subprocess.run", side_effect=run), patch.dict(os.environ, {"CHATTERBOX_EXPRESSIVE": "0"}):
            path = voice._chatterbox_voiceover('One runaway dog. <break time="0.4s" /> Two countries.', "energetic")
        self.assertEqual([["text", "One runaway dog."], ["pause", 0.4], ["text", "Two countries."]], jobs[0]["parts"])
        os.remove(path)
        # Expressive (the default): each sentence carries its own delivery, and the pause stays where it was.
        jobs.clear()
        with patch.object(voice, "chatterbox_available", return_value=True), \
                patch("subprocess.run", side_effect=run), patch.object(voice, "_misspoken", return_value=False):
            path = voice._chatterbox_voiceover('One runaway dog. <break time="0.4s" /> Two countries.', "energetic")
        parts = jobs[0]["parts"]
        self.assertEqual(["text", "pause", "text"], [part[0] for part in parts])
        self.assertEqual("One runaway dog.", parts[0][1])
        self.assertIn("exaggeration", parts[0][2])
        os.remove(path)

    def test_break_tags_become_pauses_between_spoken_parts(self):
        from agents import voice
        self.assertEqual(voice._BREAK.split('One. <break time="0.35s" /> Two.'), ["One. ", "0.35", " Two."])
