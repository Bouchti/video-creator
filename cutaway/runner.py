"""
Stage runner: each stage reads from and writes to runs/<slug>/, is cached by a hash of its inputs, is
validated before the next one starts, and can be resumed with --from <stage>.

A stage module exposes:
    inputs(run) -> list of file paths and plain values whose change invalidates the stage
    run(run)    -> does the work
    validate(run) -> raises StageError when the outputs are not fit for the next stage
"""
from __future__ import annotations

import hashlib
import importlib
import json
import logging
import os
import time
from datetime import datetime

from config.paths import get_log_file, slug as make_slug

from .config import RUNS, run_dir

log = logging.getLogger("pipeline")

STAGES = ["brief", "research", "script", "voice", "align", "shotlist", "assets", "render", "compose", "sound",
          "qa", "package"]
# (the HyperFrames render of the release candidate happens in qa, after the sound mix is in place)


class StageError(RuntimeError):
    """A stage's outputs failed validation: the pipeline stops here."""


class Run:
    def __init__(self, slug: str, topic: str | None = None, **opts):
        self.slug = slug
        self.dir = run_dir(slug)
        os.makedirs(self.dir, exist_ok=True)
        meta = self.load("run.json", {}) or {}
        if topic:
            meta.setdefault("topic", topic)
        meta.setdefault("created", datetime.now().isoformat(timespec="seconds"))
        for k, v in opts.items():
            if v is not None:
                meta[k] = v
        meta.setdefault("length", 70)
        meta.setdefault("quality", "draft")
        self.meta = meta
        self.save("run.json", meta)

    # ------------------------------------------------------------ files
    def path(self, *parts) -> str:
        return os.path.join(self.dir, *parts)

    def load(self, name, default=None):
        p = self.path(name)
        if not os.path.exists(p):
            return default
        with open(p, encoding="utf-8") as f:
            return json.load(f) if name.endswith(".json") else f.read()

    def save(self, name, obj):
        p = self.path(name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            if name.endswith(".json"):
                json.dump(obj, f, indent=2, ensure_ascii=False)
                f.write("\n")
            else:
                f.write(obj)
        os.replace(tmp, p)
        return p

    def need(self, name):
        obj = self.load(name)
        if obj is None:
            raise StageError(f"missing {name}: run the stage that makes it first")
        return obj

    # ------------------------------------------------------------ stage bookkeeping
    @property
    def quality(self) -> str:
        return self.meta.get("quality", "draft")


def _hash(items) -> str:
    h = hashlib.sha1()
    for it in items:
        if isinstance(it, str) and os.path.isfile(it):
            with open(it, "rb") as f:
                h.update(f.read())
        elif isinstance(it, str) and os.path.isdir(it):
            for root, _dirs, files in sorted(os.walk(it)):
                for name in sorted(files):
                    p = os.path.join(root, name)
                    h.update(name.encode())
                    h.update(str(os.path.getsize(p)).encode())
        else:
            h.update(json.dumps(it, sort_keys=True, default=str).encode())
    return h.hexdigest()[:16]


def setup_logging():
    root = logging.getLogger("pipeline")
    if root.handlers:
        return root
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    fh = logging.FileHandler(get_log_file(), encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(sh)
    root.addHandler(fh)
    return root


def run_stages(run: Run, start: str | None = None, stop: str | None = None, force: bool = False) -> dict:
    """Run every stage from `start` (default: the first stale one) to `stop`. Returns the timing table."""
    state = run.load("stages.json", {}) or {}
    begin = STAGES.index(start) if start else 0
    end = STAGES.index(stop) + 1 if stop else len(STAGES)
    timings = {}
    t_all = time.time()
    for i, name in enumerate(STAGES[:end]):
        mod = importlib.import_module(f"cutaway.stages.{name}")
        h = _hash([name, *mod.inputs(run)])
        cached = state.get(name, {}).get("hash") == h
        if i < begin or (cached and not force and not (start and i >= begin)):
            try:
                mod.validate(run)
                log.info("[cutaway] %-9s cached", name)
                continue
            except StageError:
                pass
        log.info("[cutaway] %-9s running", name)
        t = time.time()
        mod.run(run)
        mod.validate(run)
        secs = round(time.time() - t, 1)
        timings[name] = secs
        h = _hash([name, *mod.inputs(run)])           # inputs may include files this stage just wrote
        state[name] = {"hash": h, "seconds": secs, "finished": datetime.now().isoformat(timespec="seconds")}
        run.save("stages.json", state)
        log.info("[cutaway] %-9s done in %.1f s", name, secs)
    timings["total"] = round(time.time() - t_all, 1)
    return timings


def new_slug(topic: str) -> str:
    return make_slug(topic, 40, "-")


def existing(slug_or_topic: str) -> str | None:
    s = slug_or_topic if os.path.isdir(os.path.join(RUNS, slug_or_topic)) else new_slug(slug_or_topic)
    return s if os.path.isdir(os.path.join(RUNS, s)) else None
