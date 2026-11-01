"""
Stage 2 - research.md + facts.json: the numbers and technical claims the episode may use, each with the exact
sentence from a source page that was fetched and matched (cutaway's verifier, by import). An unverified fact never
reaches the script.
"""
from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from agents import llm
from cutaway.stages.research import SCHEMA, SYSTEM, verify

from ..runner import StageError

log = logging.getLogger("pipeline")
MIN_FACTS = 5


def inputs(run):
    return [run.path("brief.json")]


def run(run):
    b = run.need("brief.json")
    chain = "\n".join(f"{i + 1}. {s['problem']} -> {s['part_added']}" for i, s in enumerate(b["chain"]))
    prompt = f"""Research for a {b['target_seconds']}-second explainer: "{b['topic']}" (ends on: {b['machine']}).
The story, step by step:
{chain}

1. Write notes on how it really works, step by step, so the analogies stay correct.
2. Find 8 to 12 facts a viewer would find surprising or clarifying (temperatures, pressures, speeds, counts,
   sizes, energy, how often something happens) plus the key technical claims each step makes. Each needs the
   exact sentence from the page you opened. Facts must hold for typical everyday versions of the machine."""
    out = llm.ask(SYSTEM, prompt, SCHEMA, effort="high", web=True, label="buildit_research")
    seen, facts = set(), []
    for f in out["facts"]:
        fid = re.sub(r"[^a-z0-9_]+", "_", f["id"].lower()).strip("_") or "fact"
        while fid in seen:
            fid += "_b"
        seen.add(fid)
        f["id"] = fid
        facts.append(f)
    cache: dict = {}
    with ThreadPoolExecutor(6) as pool:
        checked = list(pool.map(lambda f: verify(f, cache), facts))
    good = [f for f in checked if f["verified"]]
    bad = [f for f in checked if not f["verified"]]
    for f in bad:
        log.warning("[research] dropped %s: %s", f["id"], f["why"])
    run.save("facts.json", {"facts": good})
    md = [f"# Research: {b['topic']}", "", out["notes"], "", "## Verified facts", ""]
    md += [f"- **{f['id']}**: {f['claim']} ({f['value']} {f['unit']}) - [{urlparse(f['source_url']).netloc}]"
           f"({f['source_url']}) - \"{f['quote']}\"" for f in good]
    md += ["", "## Rejected", ""] + [f"- {f['id']}: {f['claim']} - {f['why']}" for f in bad]
    run.save("research.md", "\n".join(md) + "\n")
    log.info("[research] %d facts verified, %d rejected", len(good), len(bad))


def validate(run):
    facts = run.need("facts.json")["facts"]
    if len(facts) < MIN_FACTS:
        raise StageError(f"only {len(facts)} verified facts (need {MIN_FACTS}); see research.md")
