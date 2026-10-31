"""Pre-flight for every shot's first take: catch the failures a reviewer would only report afterwards.

Across 58 reviewed takes on this machine only 4 of 18 first takes passed, and most rejections were
predictable from the keyframe and the prompt alone: a push-in that crops the door the action needs
off the frame edge, a pull-back that shrinks the ship the brief says fills half the frame, a ship
steaming toward the edge it already sits on, three officials becoming five, a cap appearing on a
bare head, ripples that never spread in 3 seconds. A take costs 6-10 minutes; this check costs one
vision call, so it runs before take one and its corrected camera move and description become the
first prompt. The reviewer still judges the original beat (shot.subject_action): the doctor changes
how the shot is filmed, never what it must show.
"""
from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from agents import llm
from config.paths import CLAUDE_MODEL

log = logging.getLogger("pipeline")

CAMERAS = {
    "locked_off": "locked-off static camera",
    "push_in": "slow push-in",
    "pull_out": "slow pull-back",
    "pan_left": "steady pan left",
    "pan_right": "steady pan right",
    "track": "gentle tracking shot",
    "rise": "slow rising crane move",
    "orbit": "slow orbit around the subject",
}

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["risks", "camera", "description", "start_frame_fits"],
    "properties": {
        "risks": {"type": "array", "items": {"type": "string"}},
        "start_frame_fits": {
            "type": "boolean",
            "description": "false when the supplied first frame cannot become this shot within the clip: another "
                           "framing scale (a face close-up for a group medium shot), people or places the shot "
                           "needs that are absent, or a different setting. true when no frame is supplied.",
        },
        "camera": {"type": "string", "enum": list(CAMERAS)},
        "description": {"type": "string"},
    },
}

KNOWN_FAILURES = """Known ways a first take of this video model fails review (from real rejected takes):
1. The camera move works against the action: a push-in crops a subject that sits near a frame edge
   (the door that must swing shut left the frame), a pull-back shrinks a subject the brief says fills
   the frame, a subject travelling toward the edge it already occupies exits the frame unless the
   camera pans with it. Choose the move that keeps every element the action needs in frame from the
   first frame to the last; locked_off is right whenever the action itself is the motion.
2. The model adds or changes things mid-clip: three officials become five, a cap appears on a bare
   head, flags, markings or lettering appear on plain objects, a face drifts older, a seated man
   stands up in a quiet beat. State every count, every person's headwear and clothing, and every
   posture as constant: "the same three officials in every frame", "his head stays bare", "he stays
   seated, forearms on the table, in every frame". Say plain objects are plain ("a plain gray hull").
   A flag keeps its exact geometry from the lock (stripes, where a cross sits, the canton): "a blue flag
   with a white cross" alone came out as a Scandinavian cross.
   Count people and objects, never a person's paired parts: a stride shows both legs, and "exactly one
   boot" got a natural step rejected for its second leg.
3. Too much for the clip's length: several steps, a slow process, a reveal that needs the camera to
   travel. Keep ONE visible change that completes inside the clip, and have any process (ripples,
   smoke, a walk) already underway in the first frame and visibly continuing.
4. The end state must be reachable from the first frame within the clip with the chosen camera.
5. The model draws every noun it reads and has no negative channel: write only what should be seen,
   never "no X" or "without X" (that draws X).
6. An abstract expression ("vacant", "foolish", "terrified", "triumphant") renders as a neutral or stern
   face that reviewers reject: write the visible mechanics instead ("jaw slack, mouth slightly open,
   eyes unfocused past the lens, head tilted a little"), and say the face holds them in every frame.
7. Facing direction follows the screen geography in the lock: a character it puts facing right must
   face right; if the first frame disagrees, say so in the risks and keep the description true to it.
8. Extras turn into copies of the named character (same uniform, hair and face: "clones") unless they
   are described as clearly different people: give them other ages, hair colours and clothing colours
   ("older men with dark hair in faded brown shirts"), and keep the named character's look unique.
9. A clip cannot become a different shot than its first frame: a face close-up cannot grow a crowd
   around it, an empty room cannot fill with the people the beat needs. If the supplied frame cannot
   become this shot, set start_frame_fits false (the shot then gets its own first frame).
10. A pan, track or pull-back reveals space the first frame does not show, and the model invents it (a
   whole bank of windows appeared where the setting has one narrow high window). Say exactly what the
   revealed space holds, from the setting lock ("the same plain pale wall continues, unbroken"), or
   choose a move that reveals nothing new.
11. The frame is a tall 9:16 phone frame. Spread side by side, more than two people do not fit at the
   stated size: "Hegdahl at frame left, three officials at frame right across a table" failed fifteen
   first frames (officials cropped, tiny or missing) and the clip pushed them out of frame. Stage a
   group in depth: one person near the camera, the others behind them, over a shoulder or along the
   table's length, keeping every stated count and side. The picture fills the frame edge to edge.
   A group on the move is the exception: it marches away from the camera up its road (or toward it).
   A column asked to cross the tall frame side-on failed 13 first frames in four different wordings,
   while marching away passed first time. Its flag stays on a post: a flag "carried by the first
   soldier" was drawn on a loose pole beside the column.
12. A beat whose people only listen, sit or wait has nothing to animate: the take holds frozen, or the
   model invents a bigger change (a seated man stood up, the camera drifted back). A slight nod or
   glance does not render either. Give such a beat one clear, continuous action that fits it and
   reads at phone size: speaking with lips moving and a hand marking points on the table, writing
   fast, leaning in."""


def enabled() -> bool:
    return os.getenv("LOCAL_VIDEO_SHOT_DOCTOR", "1").strip() != "0"


def fingerprint(shot: Any, end_state: str, keyframe: Path | None, outfits: dict[str, str] | None = None) -> str:
    stamp = ""
    if keyframe and keyframe.is_file():
        stat = keyframe.stat()
        stamp = f"{stat.st_size}-{stat.st_mtime_ns}"
    # Not the camera move: the doctor sets it, and the next run must still recognise the shot. The rules
    # are in it, so a lesson added to KNOWN_FAILURES re-checks every shot not yet reviewed.
    text = "\n".join([shot.subject_action, end_state, str(shot.duration_frames), stamp, KNOWN_FAILURES,
                      repr(sorted((outfits or {}).items()))])
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def examine(shot: Any, end_state: str, keyframe: Path | None,
            outfits: dict[str, str] | None = None, failed: str = "") -> dict[str, Any] | None:
    """One shot's pre-flight: the risks seen, and the camera move and description that avoid them."""
    seconds = shot.duration_frames / 30.0
    hook = shot.index == 0
    prompt = (
        f"You plan a {seconds:.1f}-second shot for an image-to-video model before it is generated.\n"
        f"The beat it must show (keep its meaning, facts and named characters): {shot.subject_action}\n"
        f"Its end state: {end_state or 'as the beat describes'}\n"
        f"Planned camera move: {shot.camera_action}\n"
        f"Named characters on screen: {', '.join(shot.cast) if shot.cast else 'none'}\n"
        f"Identity and world lock: {str(shot.continuity.get('characters') or '')[:400]}\n"
        + (f"Screen geography lock (sides and facing; the reviewer rejects a named character facing against it, "
           f"so never write 'facing the lens' for them): {shot.continuity['screen_geography']}\n"
           if (shot.continuity or {}).get("screen_geography") else "")
        + "".join(f"WARDROBE LOCK for {name}, exactly as in their previous shot (write it into the description "
                  f"word for word, unchanged in every frame): {outfit}\n"
                  for name, outfit in (outfits or {}).items() if outfit)
        + ("This is the HOOK, the first shot of the video: strong visible action from the first frame.\n"
           if hook else "")
        + ("The attached image IS the first frame: read where everything sits in it and plan the move "
           "from there.\n" if keyframe else "No first frame is supplied; the description sets the layout.\n")
        + KNOWN_FAILURES
        + (f"\nA PREVIOUS TAKE OF THIS SHOT WAS REJECTED FOR:\n{failed}\nPlan this retake so it cannot fail "
           "the same way: fix the cause (camera move, layout, counts, wardrobe, expression), not only the "
           "symptom.\n" if failed else "")
        + "\nThe planned move is a suggestion, not a constraint: when a risk you list comes from it (an orbit "
          "sliding a seated group out of frame), choose another move.\n"
        + "\nReturn the risks you see for THIS shot, the camera move that avoids them, and a corrected "
          "description for the video model: start with the shot size (\"Medium shot:\", \"Wide shot:\", "
          "\"Close-up:\"), one continuous moment, where each element sits in frame, the one visible change, "
          "the constants (counts, headwear, plain surfaces), at most 90 words, positive wording only. "
          "Submit the structured output."
    )
    try:
        with tempfile.TemporaryDirectory() as tmp:
            images = []
            if keyframe and keyframe.is_file():
                from .visual_review import _encode_still
                data = _encode_still(keyframe)
                if data:
                    still = Path(tmp) / "first-frame.jpg"
                    still.write_bytes(data)
                    images.append(("First frame of the shot", still))
            for attempt in range(2):
                try:
                    values = llm.ask("You are a cinematographer planning shots for a video generator.",
                                           prompt, SCHEMA, model=os.getenv("VISION_MODEL") or CLAUDE_MODEL,
                                           images=images)
                    break
                except Exception:
                    # Parallel calls race the backend switch: one call's usage-limit error flips every
                    # later call to the fallback, but the call already in flight still raises. Once more.
                    if attempt:
                        raise
        if not isinstance(values, dict) or values.get("camera") not in CAMERAS:
            return None
        description = str(values.get("description") or "").strip()
        if len(description) < 40:
            return None
        return {"camera": CAMERAS[values["camera"]], "description": description,
                "risks": [str(r) for r in values.get("risks") or []][:8],
                "start_frame_fits": values.get("start_frame_fits") is not False}
    except Exception as exc:                  # the shot simply keeps its planned prompt
        log.warning("Shot doctor unavailable for %s (%s)", shot.id, exc.__class__.__name__)
        return None


def examine_all(jobs: list[tuple], workers: int = 4) -> list[dict[str, Any] | None]:
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        return list(pool.map(lambda job: examine(*job), jobs))
