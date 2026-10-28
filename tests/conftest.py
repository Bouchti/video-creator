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
