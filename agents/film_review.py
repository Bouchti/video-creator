"""
Whole-film viewer test of a finished Max cutaway film (the scene reviews judge 3-second windows; nobody judged
whether the WHOLE film can be followed, and the sandcastle film passed its windows while "we can't even
understand what is in the video").

    from agents.film_review import review
    report = review(video, film_json)        # -> <video>_viewer.json, or None when it could not run

Each beat becomes one strip of 4 frames from the final MP4 (with its stickers and captions); a model watching
with the SOUND OFF says what it sees per beat, whether the hook stops a scroll, then (with the narration) what
it learned and what confused it. Never blocks a run: problems become quality warnings in the run log.
"""
import json
import logging
import os
import subprocess

from agents import llm
from agents.director import VIEWER_SCHEMA
from agents.media import FFMPEG
from config.paths import get_output_dir

log = logging.getLogger("pipeline")

SYSTEM = ("You are a 16-year-old scrolling TikTok with the SOUND OFF. Each image is one beat of a short animated "
          "film about Max (a cartoon builder) and his two kids: its key moments left to right. For each beat FIRST "
          "write what_happens: what you actually see, in one sentence, without guessing. THEN read the intent. "
          "clear: would you get that idea from the picture alone? funny: 1 (not at all) to 5 (I'd send it to a "
          "friend). incoherent: anything physically wrong or contradictory (objects passing through each other, "
          "water that looks solid, text over text, things cut by the frame edge, a prop in the wrong place), or ''. "
          "problem: the single change that would help most, or ''. Be blunt. hook: look ONLY at the first picture "
          "of the FIRST beat (its first second). stops_scroll: would that make you stop scrolling, because something "
          "surprising, spectacular or funny is visibly happening? A person standing next to an object is NOT "
          "enough. why: one line. LAST, with the narration as if the sound were on: learned = the new thing a "
          "12-year-old would now know, in one sentence ('' if nothing); confusing = every moment where the words "
          "and the pictures do not explain it simply, or do not match. overall: one line verdict.")


def _strip(video, t0, t1, path):
    """4 frames at 1/8, 3/8, 5/8, 7/8 of [t0, t1] side by side (310 px wide each)."""
    times = [t0 + (t1 - t0) * k / 8 for k in (1, 3, 5, 7)]
    inputs, filters = [], []
    for k, t in enumerate(times):
        inputs += ["-ss", f"{t:.2f}", "-i", video]
        filters.append(f"[{k}:v]scale=310:-2,select=eq(n\\,0)[v{k}]")
    graph = ";".join(filters) + ";" + "".join(f"[v{k}]" for k in range(4)) + "hstack=4"
    subprocess.run([FFMPEG, "-v", "error", "-y", *inputs, "-filter_complex", graph, "-frames:v", "1", path],
                   check=True, capture_output=True, timeout=300)
    return path


def review(video, film_json):
    try:
        film = json.load(open(film_json, encoding="utf-8"))
        name = os.path.splitext(os.path.basename(film_json))[0]
        timings = json.load(open(os.path.join(get_output_dir(), f"{name}_work", "timings.json"), encoding="utf-8"))
        fps = timings.get("fps", 30)
        out_dir = os.path.join(get_output_dir(), f"{name}_work", "viewer")
        os.makedirs(out_dir, exist_ok=True)
        actions = {}
        if film.get("set"):
            from engine import sets
            actions = getattr(sets.spec(film["set"]), "ACTIONS", {})
        strips, intents, said = [], [], []
        for k, (beat, span) in enumerate(zip(film["beats"], timings["beats"])):
            bid = beat.get("id") or beat.get("action") or f"beat{k + 1}"
            t0, t1 = span["start"] / fps, (span["end"] + 1) / fps
            strips.append((bid, _strip(video, t0, t1, os.path.join(out_dir, f"{k + 1:02d}_{bid}.jpg"))))
            shows = beat.get("shows") or actions.get(beat.get("action"), {}).get("shows") or beat.get("action", "")
            intents.append(f"- {bid}: {shows}")
            said.append(f"- {bid}: {beat.get('text', '')}")
        report = llm.ask(SYSTEM, "INTENT (read after describing):\n" + "\n".join(intents)
                         + "\n\nNARRATION (for learned / confusing):\n" + "\n".join(said),
                         VIEWER_SCHEMA, images=strips, effort="low", label="film-review")
    except Exception as exc:                       # noqa: BLE001  a review never fails a finished film
        log.warning(f"[film_review] the viewer test could not run: {str(exc)[:300]}")
        return None
    path = os.path.splitext(video)[0] + "_viewer.json"
    json.dump(report, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    unclear = [b["id"] for b in report.get("beats", []) if not b.get("clear")]
    if unclear or not report.get("hook", {}).get("stops_scroll") or report.get("confusing"):
        log.warning("QUALITY WARNING: [film_review] " + "; ".join(filter(None, [
            f"unclear beats (sound off): {', '.join(unclear)}" if unclear else "",
            "the hook would not stop a scroll: " + report.get("hook", {}).get("why", "")
            if not report.get("hook", {}).get("stops_scroll") else "",
            f"confusing: {' | '.join(report.get('confusing', [])[:4])}" if report.get("confusing") else ""])))
    log.info(f"[film_review] {report.get('overall', '')} (learned: {report.get('learned', '')}) -> {path}")
    return report
