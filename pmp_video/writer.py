"""
Scripts for every format. A script is plain JSON (saved as script.json in the project) made of scenes;
each scene has on-screen fields and narrated beats, and a beat may name the element it reveals.

The bank question is the source of truth: its options and correct answer are copied, never written by
the model. The model writes the hook, the narration, short on-screen wording and the reasons, and its
output is checked (word limits, four options, the trap is a wrong answer, no em dashes) with one repair
turn before the run stops.
"""
from __future__ import annotations

import json
import logging
import re

from pmp_video import bank as qbank
from pmp_video.config import DOMAIN_LABEL, FORMATS, PAUSE_SECONDS, SITE_LABEL, TAGLINE

log = logging.getLogger("pipeline")
LETTERS = "ABCD"


class QuestionRejected(RuntimeError):
    """The bank question looks inconsistent (its explanation backs another option); pick another one."""


def _supported(q: dict, w: dict) -> dict:
    if w.get("explanation_supports_answer") is False:
        raise QuestionRejected(f"Question {q.get('id')}: the explanation does not support the marked answer "
                               f"{LETTERS[int(q['correct'][0])]}; fix it in the bank before filming it.")
    return w

SYSTEM = f"""You write scripts for PMP Exam Lab, a YouTube and TikTok channel that teaches the 2026 PMP exam
(Exam Content Outline from July 2026, PMBOK Guide 8th Edition) one exam-style scenario at a time.
Voice: a calm, confident PMP coach. Plain US English, short spoken sentences, second person.
Teach the PMI mindset: assess before acting, servant leadership, collaborate before escalating, follow the
plan and governance, deliver value, tailor the approach (predictive, agile, hybrid).
Hard rules:
- The question, its options and its correct answer are given. Never change which option is correct and never
  contradict the given explanation. Paraphrase only to shorten.
- Never use em dashes or en dashes. Use commas, colons or full stops.
- No made-up statistics, pass rates or quotes. No claims about what PMI "always" tests.
- Never mention PMI endorsement. Refer to options by letter (A, B, C, D) in narration.
- On-screen text is short and scannable; narration is what is said aloud and may be longer.
The call to action is always the free simulator at {SITE_LABEL}."""


def _s(max_words: int) -> dict:
    return {"type": "string", "description": f"at most {max_words} words"}


def _obj(props: dict) -> dict:
    return {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}


def _arr(item: dict, n: int | None = None, lo: int | None = None, hi: int | None = None) -> dict:
    out = {"type": "array", "items": item}
    if n is not None:
        out["minItems"] = out["maxItems"] = n
    if lo is not None:
        out["minItems"] = lo
    if hi is not None:
        out["maxItems"] = hi
    return out


QUESTION_SCHEMA = _obj({
    "explanation_supports_answer": {"type": "boolean",
                                    "description": "false if the explanation argues for a different option "
                                                   "than the marked correct answer"},
    "title": _s(12),
    "hook": _s(10),
    "scenario_screen": _s(34),
    "scenario_say": _s(55),
    "options_screen": _arr(_s(14), 4),
    "reasons": _arr(_s(22), 4),
    "rule": _s(10),
    "rule_say": _s(30),
})

TRAP_SCHEMA = _obj({
    "explanation_supports_answer": {"type": "boolean",
                                    "description": "false if the explanation argues for a different option "
                                                   "than the marked correct answer"},
    "title": _s(12),
    "hook": _s(10),
    "scenario_screen": _s(34),
    "scenario_say": _s(55),
    "options_screen": _arr(_s(14), 4),
    "trap_index": {"type": "integer", "minimum": 0, "maximum": 3},
    "tempting": _s(35),
    "wrong": _s(40),
    "right_say": _s(40),
    "rule": _s(10),
})

_SIDE = _obj({"term": _s(4), "definition": _s(14), "example": _s(14), "say": _s(45)})
TERM_SCHEMA = _obj({
    "title": _s(12), "hook": _s(10), "left": _SIDE, "right": _SIDE,
    "tip": _s(14), "tip_say": _s(35), "quiz_question": _s(20), "quiz_answer": _s(14),
})

MINDSET_SCHEMA = _obj({
    "title": _s(12), "hook": _s(10), "rule": _s(10), "explain_say": _s(50),
    "scenario": _s(30), "do": _s(14), "dont": _s(14), "do_say": _s(35), "dont_say": _s(35),
})

COURSE_SCHEMA = _obj({
    "title": _s(12),
    "subtitle": _s(14),
    "intro_say": _s(90),
    "chapters": _arr(_obj({
        "title": _s(8),
        "keywords": _s(10),
        "sections": _arr(_obj({"heading": _s(8), "bullets": _arr(_s(12), lo=2, hi=5), "say": _s(170)}),
                         lo=1, hi=4),
        "example": _obj({"heading": _s(8), "scenario": _s(40), "say": _s(120)}),
    }), lo=1, hi=12),
    "recap": _arr(_s(14), lo=3, hi=7),
    "outro_say": _s(60),
})


# ---------------------------------------------------------------- checks

_DASH = re.compile(r"\s*[—–]\s*")


def clean(text: str) -> str:
    """House style: no em or en dashes; collapse whitespace."""
    return re.sub(r"\s+", " ", _DASH.sub(", ", str(text))).strip()


def _cleaned(value):
    if isinstance(value, str):
        return clean(value)
    if isinstance(value, list):
        return [_cleaned(v) for v in value]
    if isinstance(value, dict):
        return {k: _cleaned(v) for k, v in value.items()}
    return value


def _limits(schema: dict, value, path: str = "") -> list[str]:
    """Word-limit and array-size problems in `value` against the descriptions in `schema`."""
    problems = []
    kind = schema.get("type")
    if kind == "string":
        m = re.search(r"at most (\d+) words", schema.get("description", ""))
        if m and len(str(value).split()) > int(m.group(1)) * 1.25:     # small tolerance, then repair
            problems.append(f"{path or 'text'} has {len(str(value).split())} words, limit {m.group(1)}")
        if not str(value).strip():
            problems.append(f"{path} is empty")
    elif kind == "array":
        lo, hi = schema.get("minItems"), schema.get("maxItems")
        if lo is not None and len(value) < lo or hi is not None and len(value) > hi:
            problems.append(f"{path} has {len(value)} items, expected {lo}..{hi}")
        for i, v in enumerate(value):
            problems += _limits(schema["items"], v, f"{path}[{i}]")
    elif kind == "object":
        for k, sub in schema["properties"].items():
            if k not in value:
                problems.append(f"{path}.{k} missing")
            else:
                problems += _limits(sub, value[k], f"{path}.{k}")
    return problems


def ask_checked(prompt: str, schema: dict, extra_check=None, *, ask=None) -> dict:
    """One structured LLM turn, checked, with a single repair turn. `ask` defaults to agents.llm.ask."""
    if ask is None:
        from agents import llm
        ask = llm.ask
    out = ask(SYSTEM, prompt, schema, effort="medium", label="pmp")
    out = json.loads(out) if isinstance(out, str) else out
    problems = _limits(schema, out) + (extra_check(out) if extra_check else [])
    if problems:
        log.info("[pmp] repairing script: %s", "; ".join(problems[:6]))
        repair = (prompt + "\n\nYour previous answer broke these rules, fix every one and answer again:\n- "
                  + "\n- ".join(problems) + "\n\nPrevious answer:\n" + json.dumps(out, ensure_ascii=False))
        out = ask(SYSTEM, repair, schema, effort="medium", label="pmp")
        out = json.loads(out) if isinstance(out, str) else out
        problems = _limits(schema, out) + (extra_check(out) if extra_check else [])
        if problems:
            raise RuntimeError("Script still breaks the rules after repair: " + "; ".join(problems[:6]))
    return _cleaned(out)


def _question_block(q: dict) -> str:
    c = int(q["correct"][0])
    opts = "\n".join(f"{LETTERS[i]}. {o}" for i, o in enumerate(q["options"]))
    return (f"Domain: {DOMAIN_LABEL.get(q.get('domain'), q.get('domain'))}. Approach: {q.get('approach')}.\n"
            f"Question: {q['stem']}\nOptions:\n{opts}\nCorrect answer: {LETTERS[c]}\n"
            f"Explanation (source of truth): {q['explanation']}")


# ---------------------------------------------------------------- scene helpers

def beat(say: str, show: str | None = None) -> dict:
    return {"say": clean(say), "show": show}


def _cta_scene(shape_short: bool) -> dict:
    text = "10 more like this, free" if shape_short else "Practice free with an AI coach"
    return {"type": "cta", "text": text, "url": SITE_LABEL,
            "beats": [beat(f"{text} at pmpexamlab.com." if shape_short else
                           "Keep practicing on the free simulator at pmpexamlab.com. "
                           "Subscribe for a new lesson every week.")]}


def question_scenes(q: dict, w: dict, *, pause: float = PAUSE_SECONDS, short: bool = True) -> list[dict]:
    """Scenario, options, pause, reveal and rule for one bank question with written fields `w`."""
    c = int(q["correct"][0])
    domain = DOMAIN_LABEL.get(q.get("domain"), "")
    opts = w["options_screen"]
    w["reasons"] = [r[:1].upper() + r[1:] for r in w["reasons"]]
    reveal_beats = [beat(f"{LETTERS[i]}. {w['reasons'][i]}", f"strike-{i}") for i in range(4) if i != c]
    reveal_beats.append(beat(f"The answer is {LETTERS[c]}. {w['reasons'][c]}", f"good-{c}"))
    return [
        {"type": "scenario", "domain": domain, "approach": q.get("approach", ""), "text": w["scenario_screen"],
         "beats": [beat(w["scenario_say"])]},
        {"type": "options", "options": opts, "correct": c, "reasons": w["reasons"],
         "beats": [beat(f"{LETTERS[i]}. {o}", f"opt-{i}") for i, o in enumerate(opts)]},
        {"type": "pause", "seconds": pause, "options": opts, "beats": []},
        {"type": "reveal", "options": opts, "correct": c, "reasons": w["reasons"], "beats": reveal_beats},
        {"type": "rule", "label": "PMI mindset", "text": w["rule"], "beats": [beat(w["rule_say"])]},
    ]


def _write_question(q: dict, ask=None, angle: str = "") -> dict:
    prompt = (f"{angle}\nWrite the fields for a video built on this bank question.\n{_question_block(q)}\n\n"
              "hook: the question in a sharp spoken form, for the first 3 seconds.\n"
              "scenario_screen / scenario_say: the stem, shortened for the screen / for the voice.\n"
              "options_screen: the four options in order, each shortened to its core action, meaning unchanged.\n"
              "reasons: in option order; for a wrong option, why it loses; for the correct one, why it wins.\n"
              "rule: the PMI mindset rule this question tests, as one memorable line; rule_say expands it.\n"
              "title: a YouTube title that states the dilemma, no clickbait, no hashtags.\n"
              "explanation_supports_answer: check honestly whether the explanation argues for the marked answer.")
    return _supported(q, ask_checked(prompt, QUESTION_SCHEMA, ask=ask))


# ---------------------------------------------------------------- formats

def short_question(q: dict, ask=None) -> dict:
    w = _write_question(q, ask)
    scenes = [{"type": "hook", "text": w["hook"], "badge": FORMATS["question"]["series"],
               "beats": [beat(w["hook"])]}]
    scenes += question_scenes(q, w)
    scenes.append(_cta_scene(True))
    return {"format": "question", "title": w["title"], "hook": w["hook"], "question_ids": [q["id"]],
            "scenes": scenes}


def short_trap(q: dict, ask=None) -> dict:
    c = int(q["correct"][0])

    def check(out):
        return [] if out.get("trap_index") != c else ["trap_index must be a WRONG option, not the correct one"]

    prompt = (f"Write an 'exam trap' short on this bank question: the wrong option that most candidates pick.\n"
              f"{_question_block(q)}\n\n"
              "trap_index: the most tempting WRONG option (0 to 3). tempting: why it feels right. "
              "wrong: why PMI rejects it, tied to the explanation. right_say: the correct answer and why.\n"
              "hook: name the trap, e.g. 'This answer feels right. It costs points.'\n"
              "options_screen: the four options shortened, meaning unchanged. rule: one memorable line. "
              "title: a YouTube title about the trap. explanation_supports_answer: check honestly whether the "
              "explanation argues for the marked answer.")
    w = _supported(q, ask_checked(prompt, TRAP_SCHEMA, check, ask=ask))
    t = int(w["trap_index"])
    opts = w["options_screen"]
    scenes = [
        {"type": "hook", "text": w["hook"], "badge": FORMATS["trap"]["series"], "beats": [beat(w["hook"])]},
        {"type": "scenario", "domain": DOMAIN_LABEL.get(q.get("domain"), ""), "approach": q.get("approach", ""),
         "text": w["scenario_screen"], "beats": [beat(w["scenario_say"])]},
        {"type": "options", "options": opts, "correct": c, "reasons": [""] * 4,
         "beats": [beat("Here are your options.", "opt-all"), beat(f"Most candidates pick {LETTERS[t]}.",
                                                                   f"focus-{t}")]},
        {"type": "trap", "options": opts, "correct": c, "trap": t,
         "beats": [beat(w["tempting"], f"focus-{t}"), beat(w["wrong"], f"strike-{t}"),
                   beat(w["right_say"], f"good-{c}")]},
        {"type": "rule", "label": "Avoid the trap", "text": w["rule"], "beats": [beat(w["rule"])]},
        _cta_scene(True),
    ]
    return {"format": "trap", "title": w["title"], "hook": w["hook"], "question_ids": [q["id"]], "scenes": scenes}


def short_term(topic: str | None, ask=None) -> dict:
    prompt = ("Write a 'Term Clash' short: two PMP terms candidates confuse, side by side.\n"
              + (f"Terms: {topic}\n" if topic else
                 "Pick a pair that matters on the 2026 exam (e.g. risk vs issue, burnup vs burndown, MVP vs MMF, "
                 "quality assurance vs quality control, change request vs defect).\n")
              + "left / right: term, a screen definition, a concrete project example, and say (spoken explanation). "
              "tip: how to tell them apart on the exam. quiz_question: a one-line check; quiz_answer: its answer. "
              "hook: the confusion in one line. title: a YouTube title naming both terms.")
    w = ask_checked(prompt, TERM_SCHEMA, ask=ask)
    scenes = [
        {"type": "hook", "text": w["hook"], "badge": FORMATS["term"]["series"], "beats": [beat(w["hook"])]},
        {"type": "compare", "left": w["left"], "right": w["right"],
         "beats": [beat(w["left"]["say"], "left"), beat(w["right"]["say"], "right")]},
        {"type": "rule", "label": "Exam tip", "text": w["tip"], "beats": [beat(w["tip_say"])]},
        {"type": "quiz", "question": w["quiz_question"], "answer": w["quiz_answer"],
         "beats": [beat(w["quiz_question"], "question"), beat(w["quiz_answer"], "answer")]},
        _cta_scene(True),
    ]
    return {"format": "term", "title": w["title"], "hook": w["hook"], "question_ids": [], "scenes": scenes}


def short_mindset(topic: str | None, ask=None) -> dict:
    prompt = ("Write a 'PMI Mindset' short: one rule the exam rewards.\n"
              + (f"Rule or theme: {topic}\n" if topic else
                 "Pick a rule that decides many situational questions (e.g. assess before you act, talk to the "
                 "person first, update the plan then communicate, protect the team as servant leader).\n")
              + "rule: the rule as a memorable line. explain_say: why the exam rewards it. scenario: a short "
              "situation; do / dont: the right and the tempting wrong move, with do_say / dont_say spoken. "
              "hook: a sharp first line. title: a YouTube title.")
    w = ask_checked(prompt, MINDSET_SCHEMA, ask=ask)
    scenes = [
        {"type": "hook", "text": w["hook"], "badge": FORMATS["mindset"]["series"], "beats": [beat(w["hook"])]},
        {"type": "rule", "label": "The rule", "text": w["rule"], "beats": [beat(w["explain_say"])]},
        {"type": "dodont", "scenario": w["scenario"], "do": w["do"], "dont": w["dont"],
         "beats": [beat(w["scenario"], "scenario"), beat(w["dont_say"], "dont"), beat(w["do_say"], "do")]},
        _cta_scene(True),
    ]
    return {"format": "mindset", "title": w["title"], "hook": w["hook"], "question_ids": [], "scenes": scenes}


def long_walkthrough(questions: list[dict], ask=None, title: str | None = None, count: int | None = None) -> dict:
    """`questions` may hold spares: the first `count` whose explanation backs the marked answer are used."""
    count = count or len(questions)
    written = []
    for q in questions:
        if len(written) == count:
            break
        try:
            written.append((q, _write_question(q, ask)))
        except QuestionRejected as exc:
            log.warning("[pmp] skipping question: %s", exc)
    if len(written) < count:
        raise RuntimeError(f"Only {len(written)} of {count} questions passed the consistency check")
    questions = [q for q, _ in written]
    n = len(questions)
    domains = sorted({DOMAIN_LABEL.get(q.get("domain"), "") for q in questions})
    topic = domains[0] if len(domains) == 1 else "PMP"
    title = title or f"{n} {topic} Questions Walked Through (2026 PMP Exam)"
    scenes = [{"type": "title", "kicker": FORMATS["walkthrough"]["series"], "title": title, "subtitle": TAGLINE,
               "beats": [beat(f"{n} exam style questions. For each one, pause the video, pick your answer, "
                              "then watch how to eliminate the wrong options the way the exam expects.")]}]
    for i, (q, w) in enumerate(written, 1):
        scenes.append({"type": "chapter", "number": i, "title": f"Question {i}", "chapter": w["title"],
                       "beats": [beat(f"Question {i}.")]})
        scenes += question_scenes(q, w, pause=max(3.0, PAUSE_SECONDS - 1), short=False)
    scenes.append({"type": "recap", "heading": "What to remember",
                   "bullets": [s["text"] for s in scenes if s["type"] == "rule"][:7],
                   "beats": [beat("Here are the rules behind today's questions.")]})
    scenes.append(_cta_scene(False))
    return {"format": "walkthrough", "title": title, "hook": title, "question_ids": [q["id"] for q in questions],
            "scenes": scenes}


def long_course(topic: str, minutes: int = 12, notes: str = "", ask=None, bank_items=None) -> dict:
    chapters = max(2, min(10, round(minutes / 3)))
    words = minutes * 140
    prompt = (f"Write a full video lesson for the course '{topic}'. Length about {minutes} minutes spoken, "
              f"so about {words} narrated words across intro_say, every section say, every example say and "
              f"outro_say. Use {chapters} chapters; 2 or 3 sections each.\n"
              "Each section: a heading, 2 to 5 short bullets shown on screen, and say, the spoken teaching of "
              "those bullets with a concrete project example. Each chapter ends with an example: a short exam "
              "style situation and its say (how a PMP thinks it through). keywords: 3 to 6 words used to find a "
              "matching practice question in the bank (e.g. 'stakeholder engagement conflict').\n"
              "recap: one line per key takeaway. title and subtitle: the lesson title for YouTube.\n"
              + (f"\nTeach from these notes first; they are the instructor's own material:\n{notes}\n" if notes else ""))
    w = ask_checked(prompt, COURSE_SCHEMA, ask=ask)
    scenes = [{"type": "title", "kicker": FORMATS["course"]["series"], "title": w["title"],
               "subtitle": w["subtitle"], "beats": [beat(w["intro_say"])]}]
    taken: set[str] = set()
    ids = []
    for ci, ch in enumerate(w["chapters"], 1):
        scenes.append({"type": "chapter", "number": ci, "title": ch["title"], "chapter": ch["title"],
                       "beats": [beat(f"Chapter {ci}. {ch['title']}.")]})
        for sec in ch["sections"]:
            scenes.append({"type": "bullets", "heading": sec["heading"], "bullets": sec["bullets"],
                           "beats": _spread_bullets(sec["say"], len(sec["bullets"]))})
        ex = ch["example"]
        scenes.append({"type": "example", "heading": ex["heading"], "text": ex["scenario"],
                       "beats": [beat(ex["say"])]})
        q = qw = None
        try:
            candidates = qbank.pick("course", 3, keywords=ch["keywords"] + " " + ch["title"], exclude=taken,
                                    bank=bank_items)
        except RuntimeError:
            candidates = []
        for cand in candidates:
            taken.add(str(cand["id"]))
            try:
                qw = _write_question(cand, ask, angle=f"This question checks chapter '{ch['title']}' of a lesson.")
                q = cand
                break
            except QuestionRejected as exc:
                log.warning("[pmp] skipping question: %s", exc)
        if q:
            ids.append(q["id"])
            scenes.append({"type": "chapter", "number": ci, "title": "Check yourself", "chapter": None,
                           "beats": [beat("Check yourself with an exam style question.")]})
            scenes += question_scenes(q, qw, pause=4.0, short=False)
    scenes.append({"type": "recap", "heading": "Recap", "bullets": w["recap"],
                   "beats": _spread_bullets(" ".join(w["recap"]), len(w["recap"]), prefix="Let's recap. ")})
    scenes.append({"type": "cta", "text": "Practice free with an AI coach", "url": SITE_LABEL,
                   "beats": [beat(w["outro_say"] + " Practice free at pmpexamlab.com.")]})
    return {"format": "course", "title": w["title"], "hook": w["subtitle"], "question_ids": ids, "scenes": scenes}


def _spread_bullets(say: str, n: int, prefix: str = "") -> list[dict]:
    """Split a section's narration into n beats at sentence boundaries so each bullet lands with its words."""
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", clean(prefix + say)) if s]
    if not sentences:
        return [beat(say, "b-0")]
    groups: list[list[str]] = [[] for _ in range(max(1, min(n, len(sentences))))]
    per = len(sentences) / len(groups)
    for i, s in enumerate(sentences):
        groups[min(len(groups) - 1, int(i / per))].append(s)
    beats = [beat(" ".join(g), f"b-{i}") for i, g in enumerate(groups)]
    for extra in range(len(groups), n):          # more bullets than sentences: reveal the rest with the last beat
        beats[-1].setdefault("also", []).append(f"b-{extra}")
    return beats
