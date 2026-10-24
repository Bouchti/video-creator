import tempfile
import unittest
from unittest.mock import patch

import engine.make_film as mf


class _FakeProc:
    calls = []

    def __init__(self, cmd, stdout, stderr, text):
        _FakeProc.calls.append(cmd)
        stdout.write("DONE\n")

    def wait(self):
        pass


class ParallelRenderTests(unittest.TestCase):
    SPANS = [{"start": 0, "end": 88}, {"start": 89, "end": 160}, {"start": 161, "end": 2500}]

    def _run(self, n):
        _FakeProc.calls = []
        with patch.object(mf.subprocess, "Popen", _FakeProc):
            mf._render_parallel(["blender"], self.SPANS, 2500, n, tempfile.mkdtemp())
        return _FakeProc.calls

    def test_chunks_cover_every_frame_once(self):
        for n in (2, 3, 4):
            calls = self._run(n)
            ranges = [tuple(int(x) for x in c[1].split("=")[1].split(":")) for c in calls]
            self.assertEqual(ranges[0][0], 162)
            self.assertEqual(ranges[-1][1], 2500)
            for (a, b), (c, d) in zip(ranges, ranges[1:]):
                self.assertEqual(c, b + 1)

    def test_only_first_worker_renders_the_hook(self):
        calls = self._run(3)
        self.assertEqual([("--hook" in c) for c in calls], [True, False, False])

    def test_hook_worker_gets_fewer_build_frames(self):
        calls = self._run(2)
        (a0, b0), (a1, b1) = [tuple(int(x) for x in c[1].split("=")[1].split(":")) for c in calls]
        self.assertLess(b0 - a0, b1 - a1)


if __name__ == "__main__":
    unittest.main()
