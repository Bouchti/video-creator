"""
Stage 2 - research.md + facts.json.

Facts are researched on the web, then VERIFIED by code: each source page is downloaded and the fact's quote
must appear in it (whitespace, case and typographic punctuation normalised; a 90% fuzzy match is accepted for
quotes the page reflows). Wikipedia is accepted only when the fact also names the primary source behind it.
Unverified facts are listed in research.md and never reach facts.json: no source, it doesn't ship.
"""
from __future__ import annotations

import difflib
import html
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import requests

from agents import llm
from config.paths import get_user_agent

from .. import kits
from ..runner import StageError

log = logging.getLogger("pipeline")
MIN_FACTS = 6

SYSTEM = """You are a meticulous engineering researcher for a science-explainer channel. Every number must be
traceable: you give the exact sentence from the source page that states it. Prefer manufacturers, engineering
textbooks and university pages, government and energy agencies, standards bodies. Use Wikipedia only when it
cites a primary source, and then give that primary source too. Never invent a URL or a quote: open the page."""

SCHEMA = {
    "type": "object",
    "properties": {
        "notes": {"type": "string", "description": "research notes in markdown: how it works, step by step"},
        "facts": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string", "description": "short snake_case id"},
            "claim": {"type": "string", "description": "the fact in one plain sentence"},
            "value": {"type": "string", "description": "the number or term shown on screen"},
            "unit": {"type": "string"},
            "source_url": {"type": "string"},
            "quote": {"type": "string", "description": "verbatim sentence from source_url containing the fact"},
            "primary_source_url": {"type": "string", "description": "required when source_url is Wikipedia"},
        }, "required": ["id", "claim", "value", "unit", "source_url", "quote"]}},
    },
    "required": ["notes", "facts"],
}


def inputs(run):
    return [run.path("brief.json")]


def _normalise(text: str) -> str:
    text = html.unescape(text)
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-").replace(" ", " ").replace(" ", " ")
    text = re.sub(r"\[\d+\]", "", text)                      # wiki footnote markers
    return re.sub(r"\s+", " ", text).strip().lower()


def page_text(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": get_user_agent(), "Accept-Language": "en"}, timeout=30)
    r.raise_for_status()
    body = r.text
    body = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", body)
    body = re.sub(r"(?s)<[^>]+>", " ", body)
    return _normalise(body)


def quote_found(quote: str, text: str) -> float:
    """1.0 for an exact (normalised) match, else the best fuzzy ratio of the quote against the page."""
    q = _normalise(quote).strip(" .\"'")
    if not q:
        return 0.0
    if q in text:
        return 1.0
    words = q.split()
    anchor = " ".join(words[:3])
    best = 0.0
    for m in re.finditer(re.escape(anchor), text):
        window = text[m.start(): m.start() + len(q) + 40]
        best = max(best, difflib.SequenceMatcher(None, q, window[:len(q)]).ratio())
    return best


def _is_wiki(url: str) -> bool:
    return "wikipedia.org" in urlparse(url).netloc


def verify(fact: dict, cache: dict) -> dict:
    url = fact["source_url"]
    out = dict(fact)
    try:
        text = cache.get(url)
        if text is None:
            text = page_text(url)
            cache[url] = text
        score = quote_found(fact["quote"], text)
    except Exception as exc:                                   # noqa: BLE001
        out.update(verified=False, why=f"could not fetch: {type(exc).__name__}")
        return out
    value_ok = _normalise(fact["value"]).split()[0] in _normalise(fact["quote"]) if fact["value"].strip() else True
    if score < 0.9:
        out.update(verified=False, why=f"quote not on page (match {score:.2f})")
    elif not value_ok:
        out.update(verified=False, why="the value is not in the quote")
    elif _is_wiki(url) and (not fact.get("primary_source_url") or _is_wiki(fact["primary_source_url"])):
        out.update(verified=False, why="Wikipedia without a primary source")
    else:
        out.update(verified=True, match=round(score, 2))
    return out


def run(run):
    brief = run.need("brief.json")
    kit = kits.KITS[brief["kit"]]
    mech = "\n".join(f"- {m['name']}: {kit['mechanisms'][m['id']]['explains']}" for m in brief["mechanisms"])
    prompt = f"""Research for a {brief['target_seconds']}-second explainer: "{brief['topic']}".
The 3D model shown is {kit['subject']}.
Angle: {brief['angle']}
Hook idea: {brief['hook']}
The video explains, in order:
{mech}

Find 10 to 14 facts with numbers or precise terms a viewer would find surprising or clarifying (speeds,
temperatures, pressures, counts, timings, sizes, energy). Each needs the exact sentence from the page you
opened. Facts must be {kit['research_scope']}, not true only for one odd model unless the claim names it."""
    out = llm.ask(SYSTEM, prompt, SCHEMA, effort="high", web=True, label="cutaway_research")
    cache: dict = {}
    seen = set()
    facts = []
    for f in out["facts"]:
        fid = re.sub(r"[^a-z0-9_]+", "_", f["id"].lower()).strip("_") or "fact"
        while fid in seen:
            fid += "_b"
        seen.add(fid)
        f["id"] = fid
        facts.append(f)
    with ThreadPoolExecutor(6) as pool:
        checked = list(pool.map(lambda f: verify(f, cache), facts))
    good = [f for f in checked if f["verified"]]
    bad = [f for f in checked if not f["verified"]]
    for f in bad:
        log.warning("[research] dropped %s: %s", f["id"], f["why"])
    run.save("facts.json", {"facts": good})
    md = [f"# Research: {brief['topic']}", "", out["notes"], "", "## Verified facts", ""]
    md += [f"- **{f['id']}**: {f['claim']} ({f['value']} {f['unit']}) - [{urlparse(f['source_url']).netloc}]"
           f"({f['source_url']}) - \"{f['quote']}\"" for f in good]
    md += ["", "## Rejected (not shippable)", ""]
    md += [f"- {f['id']}: {f['claim']} - {f['why']} - {f['source_url']}" for f in bad]
    run.save("research.md", "\n".join(md) + "\n")
    log.info("[research] %d facts verified, %d rejected", len(good), len(bad))


def validate(run):
    facts = run.need("facts.json")["facts"]
    if len(facts) < MIN_FACTS:
        raise StageError(f"only {len(facts)} verified facts (need {MIN_FACTS}); see research.md")
    for f in facts:
        if not f.get("source_url") or not f.get("quote") or not f.get("verified"):
            raise StageError(f"fact {f.get('id')} has no verified source")
