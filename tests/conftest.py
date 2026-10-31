"""Suite-wide guard: no test may reach a real AI service (a missed mock once started a live Codex call that hung
the suite and would have spent the subscription). During tests the claude/codex executables resolve to a path
that does not exist: checks that the CLI is installed still pass, but any real run fails at once (file not
found). Tests that exercise those paths patch shutil.which themselves, which takes precedence in their block."""
import os
import shutil
import tempfile

import pytest

_real_which = shutil.which
_FAKE_DIR = os.path.join(tempfile.gettempdir(), "no_real_ai_in_tests")


@pytest.fixture(autouse=True)
def _no_real_ai(monkeypatch):
    def which(cmd, *a, **k):
        name = str(cmd).lower().replace("\\", "/").rsplit("/", 1)[-1].split(".")[0]
        if name in ("claude", "codex"):
            return os.path.join(_FAKE_DIR, f"{name}.exe")
        return _real_which(cmd, *a, **k)
    monkeypatch.setattr(shutil, "which", which)


@pytest.fixture(autouse=True)
def _no_real_video_server(monkeypatch):
    """Nor may a test start FreeVideo: a stale mock once let recover_server restart the real ComfyUI on port
    8190 while a video was rendering. Tests that exercise ensure_minimax patch it themselves."""
    import subprocess
    real_popen = subprocess.Popen

    def popen(command, *args, **kwargs):
        if "freevideo_serve" in " ".join(str(part) for part in (command if isinstance(command, list) else [command])):
            raise AssertionError("a test tried to start the real FreeVideo server")
        return real_popen(command, *args, **kwargs)
    monkeypatch.setattr(subprocess, "Popen", popen)


@pytest.fixture(autouse=True)
def _classic_local_video(monkeypatch):
    """Local-ai fast mode (deadline plan, parallax stills) is the production default; the suite's queue tests
    were written for the classic every-shot-a-clip flow, so fast mode is opted into per test."""
    monkeypatch.setenv("LOCAL_VIDEO_FAST", os.environ.get("TEST_LOCAL_VIDEO_FAST", "0"))


@pytest.fixture(autouse=True)
def _no_shared_backend_limit(monkeypatch):
    """A usage limit remembered by a real run must not switch the suite's backends, nor a test's leak out."""
    monkeypatch.setenv("SHOWRUNNER_LIMIT_MEMORY", "0")
