import os
import subprocess
import tempfile
import unittest

from config.paths import get_ffmpeg, get_ffprobe


class FfmpegResolutionTests(unittest.TestCase):
    def test_ffmpeg_tools_resolve_to_existing_binaries(self):
        ffmpeg = get_ffmpeg()
        ffprobe = get_ffprobe()
        self.assertTrue(os.path.isfile(ffmpeg), ffmpeg)
        self.assertTrue(os.path.isfile(ffprobe), ffprobe)

    def test_ffprobe_reads_duration_from_generated_clip(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = os.path.join(tmp, "out.mp4")
            cmd = [
                get_ffmpeg(),
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=1080x1920:d=1",
                "-t",
                "1",
                output,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            self.assertEqual(0, result.returncode, result.stderr[-500:])

            probe = subprocess.run(
                [
                    get_ffprobe(),
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    output,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(0, probe.returncode, probe.stderr[-500:])
            self.assertGreater(float(probe.stdout.strip()), 0.0)


if __name__ == "__main__":
    unittest.main()
