"""PMP Exam Lab pipeline: scripts, timing and composition, without LLM, TTS or a browser."""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from pmp_fake_llm import ask  # noqa: E402
from pmp_video import bank, composition, project, writer  # noqa: E402
from pmp_video.config import FORMATS  # noqa: E402

BANK = json.loads((ROOT / "tests" / "fixtures" / "pmp_questions.json").read_text(encoding="utf-8"))
Q = {q["id"][:8]: q for q in BANK}


@pytest.fixture(autouse=True)
def _out(tmp_path, monkeypatch):
    monkeypatch.setenv("PMP_OUTPUT_DIR", str(tmp_path / "pmp"))


def _fake_voice(script):
    """Beat text -> speak()-shaped result at ~2.6 words per second, no audio files."""
    out = {}
    for s in script["scenes"]:
        for b in s["beats"]:
            words = b["say"].split()
            d = max(0.8, len(words) / 2.6)
            out[b["say"]] = {"file": f"{abs(hash(b['say']))}.wav", "duration": d,
                             "words": [{"text": w, "start": i * d / len(words), "end": (i + 1) * d / len(words)}
                                       for i, w in enumerate(words)]}
    return out


def _all_scripts():
    return [writer.short_question(Q["012dd47f"], ask=ask), writer.short_trap(Q["022e6e43"], ask=ask),
            writer.short_term("risk vs issue", ask=ask), writer.short_mindset(None, ask=ask),
            writer.long_walkthrough([Q["01000d23"], Q["012dd47f"], Q["0131b3d9"]], ask=ask, count=2),
            writer.long_course("Business Environment", 4, ask=ask, bank_items=BANK)]


def test_bank_filters_and_picks_unused(tmp_path):
    path = tmp_path / "bank.json"
    path.write_text(json.dumps(BANK + [{**BANK[0], "id": "multi", "correct": [0, 1]}]), encoding="utf-8")
    items = bank.load(path)
    assert "multi" not in {q["id"] for q in items}
    first = bank.pick("question", 2, bank=items, seed=1)
    bank.mark_used("question", [first[0]["id"]])
    again = bank.pick("question", len(items) - 1, bank=items, seed=1)
    assert first[0]["id"] not in {q["id"] for q in again}
    assert bank.pick("question", 1, keywords="kanban cycle time", bank=items)[0]["id"].startswith("0131b3d9")


def test_correct_answer_comes_from_the_bank():
    script = writer.short_question(Q["012dd47f"], ask=ask)
    reveal = next(s for s in script["scenes"] if s["type"] == "reveal")
    assert reveal["correct"] == Q["012dd47f"]["correct"][0]
    assert reveal["beats"][-1]["show"] == f"good-{reveal['correct']}"
    assert reveal["beats"][-1]["say"].startswith("The answer is A.")


def test_trap_is_a_wrong_option():
    script = writer.short_trap(Q["022e6e43"], ask=ask)
    trap = next(s for s in script["scenes"] if s["type"] == "trap")
    assert trap["trap"] != trap["correct"] == 1


def test_inconsistent_question_is_skipped():
    with pytest.raises(writer.QuestionRejected):
        writer.short_question(Q["01000d23"], ask=ask)
    walk = writer.long_walkthrough([Q["01000d23"], Q["012dd47f"], Q["0131b3d9"]], ask=ask, count=2)
    assert "01000d23-1f6a-4c6a-9913-26d164193e4c" not in walk["question_ids"]


def test_house_style_removes_dashes():
    assert writer.clean("Assess first — then act – always") == "Assess first, then act, always"


def test_word_limit_check_finds_long_text():
    problems = writer._limits(writer.QUESTION_SCHEMA, {**ask("", "eight sprints", writer.QUESTION_SCHEMA),
                                                      "hook": "word " * 40})
    assert any(p.startswith(".hook") for p in problems)


@pytest.mark.parametrize("index", range(6))
def test_every_format_composes(index):
    script = _all_scripts()[index]
    shape = FORMATS[script["format"]]["shape"]
    total = composition.schedule(script, _fake_voice(script))
    starts = [s["start"] for s in script["scenes"]]
    assert starts == sorted(starts) and total == pytest.approx(sum(s["duration"] for s in script["scenes"]))
    for s in script["scenes"]:
        for b in s["beats"]:
            assert s["start"] <= b["start"] and b["start"] + b["duration"] <= s["start"] + s["duration"] + 1e-6
    page = composition.build(script, shape)
    beats = sum(len(s["beats"]) for s in script["scenes"])
    assert len(re.findall(r"<audio id='vo\d+'", page)) == beats       # every clip has an id or it renders silent
    assert "—" not in page and 'window.__timelines["main"] = tl' in page
    assert f'data-width="{shape.width}"' in page
    for sid_show in re.findall(r"tl\.to\('#(s\d+-[a-z]+-\d+)'", page):
        assert f"id='{sid_show}'" in page, sid_show                 # every reveal targets a real element


def test_long_video_post_has_chapters(tmp_path):
    script = writer.long_course("Business Environment", 4, ask=ask, bank_items=BANK)
    composition.schedule(script, _fake_voice(script))
    script["slug"] = "demo"
    post = project.write_post(tmp_path, script)
    assert "Chapters\n0:00 Intro" in post["description"]
    assert "utm_campaign=pmp-course&utm_content=demo" in post["link"]
