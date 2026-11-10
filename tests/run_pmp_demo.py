"""Build every PMP format with the fake LLM and the silent voice, compose, and optionally render (draft).

    python tests/run_pmp_demo.py [--render]
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
os.environ.setdefault("PMP_OUTPUT_DIR", str(ROOT / "output" / "pmp_demo"))

from pmp_fake_llm import ask  # noqa: E402
from pmp_video import project, writer  # noqa: E402

BANK = json.loads((ROOT / "tests" / "fixtures" / "pmp_questions.json").read_text(encoding="utf-8"))
Q = {q["id"][:8]: q for q in BANK}


def scripts():
    yield writer.short_question(Q["012dd47f"], ask=ask)
    yield writer.short_trap(Q["022e6e43"], ask=ask)
    yield writer.short_term("risk vs issue", ask=ask)
    yield writer.short_mindset(None, ask=ask)
    yield writer.long_walkthrough([Q["01000d23"], Q["012dd47f"], Q["0131b3d9"]], ask=ask, count=2)
    yield writer.long_course("Business Environment", 4, ask=ask, bank_items=BANK)


if __name__ == "__main__":
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    for script in scripts():
        if only and script["format"] not in only:
            continue
        path = project.new_project(script)
        project.compose(path, script, engine="silent")
        print(f"{script['format']:12s} {script['duration']:7.1f}s  {path}")
        if "--render" in sys.argv:
            print("   ->", project.render(path, quality="draft"))
