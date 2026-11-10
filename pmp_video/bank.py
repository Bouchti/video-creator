"""The PMP Exam Lab question bank: load, filter, pick unused questions, remember what was used."""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

from pmp_video.config import output_root, question_bank_path


def load(path: Path | None = None) -> list[dict]:
    path = path or question_bank_path()
    if not path.is_file():
        raise FileNotFoundError(
            f"Question bank not found at {path}. Export it from pmp-simulator "
            "(pnpm export:questions) or set PMP_QUESTION_BANK.")
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data if isinstance(data, list) else data.get("questions", [])
    return [q for q in items if usable(q)]


def usable(q: dict) -> bool:
    """Published, single answer, four options, with an explanation: the shape every video format draws."""
    opts, correct = q.get("options") or [], q.get("correct") or []
    return (q.get("is_published", True) and len(opts) == 4 and len(correct) == 1
            and 0 <= int(correct[0]) < 4 and bool((q.get("explanation") or "").strip())
            and bool((q.get("stem") or "").strip()))


def by_id(qid: str, bank: list[dict] | None = None) -> dict:
    for q in bank or load():
        if str(q.get("id")) == qid:
            return q
    raise KeyError(f"No usable question with id {qid}")


def _ledger_path() -> Path:
    return output_root() / "used_questions.json"


def used(fmt: str) -> set[str]:
    path = _ledger_path()
    if not path.is_file():
        return set()
    return set(json.loads(path.read_text(encoding="utf-8")).get(fmt, []))


def mark_used(fmt: str, ids: list[str]) -> None:
    path = _ledger_path()
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    data[fmt] = sorted(set(data.get(fmt, [])) | {str(i) for i in ids})
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{3,}", text.lower())}


def pick(fmt: str, count: int = 1, *, domain: str | None = None, approach: str | None = None,
         difficulty: str | None = None, keywords: str | None = None, exclude: set[str] | None = None,
         bank: list[dict] | None = None, seed: int | None = None) -> list[dict]:
    """Unused questions matching the filters. Keywords rank by overlap with stem, tags and explanation;
    without keywords the order is a seeded shuffle so repeated runs vary but a given seed is repeatable."""
    bank = bank if bank is not None else load()
    skip = used(fmt) | (exclude or set())
    pool = [q for q in bank if str(q.get("id")) not in skip
            and (not domain or q.get("domain") == domain)
            and (not approach or q.get("approach") == approach)
            and (not difficulty or q.get("difficulty") == difficulty)]
    if keywords:
        want = _words(keywords)
        scored = []
        for q in pool:
            text = " ".join([q["stem"], q["explanation"], " ".join(q.get("tags") or [])])
            score = len(want & _words(text))
            if score:
                scored.append((score, q))
        scored.sort(key=lambda s: -s[0])
        pool = [q for _, q in scored]
    else:
        random.Random(seed).shuffle(pool)
    if len(pool) < count:
        raise RuntimeError(f"Only {len(pool)} unused questions match; asked for {count}. "
                           "Loosen the filters or clear output/pmp/used_questions.json for this format.")
    return pool[:count]
