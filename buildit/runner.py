"""
Build-It stage runner (the cutaway runner's contract: inputs / run / validate per stage, cached by a hash of the
inputs, resumable with --from), with its own stage list and run folder runs/buildit/<slug>/.
"""
from __future__ import annotations

import importlib
import logging
import os
import time
from datetime import datetime

from cutaway.runner import Run as _Run
from cutaway.runner import StageError, _hash, setup_logging  # noqa: F401  (re-exported)

from .config import RUNS

log = logging.getLogger("pipeline")

STAGES = ["topic", "research", "script", "voice", "align", "storyboard", "preview", "render", "compose", "sound",
          "qa", "package"]


class Run(_Run):
    def __init__(self, slug: str, topic: str | None = None, **opts):
        self.slug = slug
        self.dir = os.path.join(RUNS, slug)
        os.makedirs(self.dir, exist_ok=True)
        meta = self.load("run.json", {}) or {}
        if topic:
            meta.setdefault("topic", topic)
        meta.setdefault("created", datetime.now().isoformat(timespec="seconds"))
        for k, v in opts.items():
            if v is not None:
                meta[k] = v
        meta.setdefault("length", 75)
        meta.setdefault("quality", "final")
        meta.setdefault("lang", "en")
        self.meta = meta
        self.save("run.json", meta)


def run_stages(run: Run, start: str | None = None, stop: str | None = None, force: bool = False) -> dict:
    """Run every stage from `start` (default: the first stale one) to `stop`. Returns the timing table."""
    state = run.load("stages.json", {}) or {}
    begin = STAGES.index(start) if start else 0
    end = STAGES.index(stop) + 1 if stop else len(STAGES)
    timings = {}
    t_all = time.time()
    for i, name in enumerate(STAGES[:end]):
        mod = importlib.import_module(f"buildit.stages.{name}")
        h = _hash([name, *mod.inputs(run)])
        cached = state.get(name, {}).get("hash") == h
        if i < begin or (cached and not force and not (start and i >= begin)):
            try:
                mod.validate(run)
                log.info("[buildit] %-10s cached", name)
                continue
            except StageError:
                pass
        log.info("[buildit] %-10s running", name)
        t = time.time()
        mod.run(run)
        mod.validate(run)
        secs = round(time.time() - t, 1)
        timings[name] = secs
        state[name] = {"hash": _hash([name, *mod.inputs(run)]), "seconds": secs,
                       "finished": datetime.now().isoformat(timespec="seconds")}
        run.save("stages.json", state)
        log.info("[buildit] %-10s done in %.1f s", name, secs)
    timings["total"] = round(time.time() - t_all, 1)
    return timings
