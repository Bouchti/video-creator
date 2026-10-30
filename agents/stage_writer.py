"""
Write a STAGE plan: any topic -> a funny 60-65 s Max-and-his-kids short, as data the generic stage world films
(engine/director/stage.py). The writer only CHOOSES from vocabularies (motion-capture clips, prop moves,
spots, shot types, free-text BlenderKit searches and sound names); it never writes code or geometry.

    plan = write(topic, facts, angle)        # validated plan dict (world "stage")

A plan that breaks a rule gets one repair turn; a plan that still breaks rules is used anyway with its
problems logged as warnings and the broken parts dropped (repair()), so a run never stops here.
"""
import json
import logging
import re

from agents.plan_rules import ADVICE, _has, _words
from engine.mocap import CLIPS

log = logging.getLogger("pipeline")

# words per second of TIGHTENED narration, per voice engine (measured; updated after every recording in
# output/voice_rates.json). Chatterbox speaks ~25 % faster than ElevenLabs: a 146-word script made 46 s.
VOICE_RATES = {"elevenlabs": 2.55, "edge": 2.5, "chatterbox": 3.15}


def _rates_file():
    from config.paths import PROJECT_ROOT
    import os
    return os.path.join(PROJECT_ROOT, "output", "voice_rates.json")


def voice_rate(engine=None):
    import os
    engine = (engine or os.getenv("VOICE_ENGINE") or "elevenlabs").strip().lower()
    try:
        with open(_rates_file(), encoding="utf-8") as fh:
            measured = json.load(fh).get(engine)
        if measured and 1.5 < float(measured) < 4.5:
            return float(measured)
    except (OSError, ValueError):
        pass
    return VOICE_RATES.get(engine, 2.55)


def record_rate(words, seconds, engine=None):
    """Keep a running average of what the engine really does, so the next script is the right length."""
    import os
    engine = (engine or os.getenv("VOICE_ENGINE") or "elevenlabs").strip().lower()
    if seconds <= 5 or words <= 10:
        return
    path = _rates_file()
    try:
        with open(path, encoding="utf-8") as fh:
            rates = json.load(fh)
    except (OSError, ValueError):
        rates = {}
    rate = words / seconds
    rates[engine] = round(0.5 * rates[engine] + 0.5 * rate, 3) if engine in rates else round(rate, 3)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rates, fh, indent=1)


def words_range(engine=None):
    """Narration length that lands the film at 60-65 s with THIS voice (56.5-61.5 s of speech + the tail)."""
    r = voice_rate(engine)
    return int(round(r * 56.5)), int(round(r * 61.5))


SPOTS = ["center", "left", "right", "front_left", "front_right", "back_left", "back", "back_right", "far_left",
         "far_right"]
SPECTACLE = ["steam_burst", "smoke_burst", "launch", "confetti", "sparks", "rumble",   # see engine/director/stage
             "lean_recover"]
EVENTS = ["appear", "vanish", "grow", "shrink", "rise", "drop", "spin", "wobble", "bounce", "slide", "tip_over",
          "glow"] + SPECTACLE
REACT = {"jump", "hit", "knocked", "fall", "roll", "no", "yes", "dance", "call_out", "point"}   # a visible reaction
WHO = ["Max", "Kid1", "Kid2"]
MOVES = ["walk", "jog", "run", "sneak"]
FRAMES = ["wide", "medium", "close"]
CAMERA_MOVES = ["push_in", "pull_out", "orbit_left", "orbit_right", "static"]
SKIES = ["day", "golden", "overcast", "night"]
GROUNDS = ["grass", "sand", "dirt", "snow"]   # outdoors and COLOURFUL: grey paving made every beat washed out
DO = sorted(CLIPS)
EVENT_LOOKS = {   # what each event really looks like on screen (engine/director/stage.py event / _spectacle)
    "appear": "pops into view", "vanish": "shrinks away and disappears", "grow": "swells to 1.6 times its size",
    "shrink": "shrinks to 0.6 times its size", "rise": "floats up a little", "drop": "falls from above and lands",
    "spin": "turns once around itself", "wobble": "rocks a little and settles", "bounce": "hops three times",
    "slide": "slides along the ground to a spot", "tip_over": "falls over on its side",
    "glow": "lights up with a warm glow", "steam_burst": "puffs white cartoon steam",
    "smoke_burst": "puffs grey cartoon smoke", "launch": "shoots up spinning and lands",
    "confetti": "bursts into confetti", "sparks": "throws glowing sparks", "rumble": "shakes harder and harder",
    "lean_recover": "tips toward a fall, then swings back upright by itself"}
ARROWS = ["left", "right", "up", "down", "cw", "ccw"]   # compositor/src/Overlays.tsx ExplainArrow
ARROW_LOOKS = {"left": "pointing left", "right": "pointing right", "up": "pointing up", "down": "pointing down",
               "cw": "curling clockwise", "ccw": "curling anticlockwise"}
MAX_ACTORS = 2          # characters acting in one beat: the others stand and WATCH what the beat is about
MAX_ACTING_PROPS = 3    # the camera cuts to each acting prop; more than 3 in one beat is a strobe of cuts

RULES = """You are the head writer AND the director of a funny animated short (60-65 s, vertical, TikTok /
YouTube Shorts / Reels) starring MAX (a cheerful handyman in an orange hard hat and red shirt, over-confident)
and his two kids, KID1 (a girl, pink shirt, ponytail, sharp and sarcastic) and KID2 (a little boy, green
shirt, enthusiastic). A narrator tells the story (dry, quick, playful). The film teaches how one real thing
works, through Max trying it, getting it wrong, and the real reason being the punchline.

THE HOOK (the first beat decides everything: people scroll away in one second)
- It is the most spectacular, absurd moment of the film, SHOWN in the first second: a SPECTACLE event
  (steam_burst, smoke_burst, launch, confetti, sparks or rumble) on a prop, cued on one of the first 3 words
  (or "start"), with a big sound, a medium or close shot, and a kid reacting (jump, hit, knocked, fall, no,
  call_out...). Never a claim over a static shot, never a character just walking.
- Narration <= 12 words: a deadpan, intriguing fact about Max that makes the viewer need the explanation
  ("Max's stew exploded at 120 degrees. Water isn't supposed to do that."). hook_text: <= 5 words, a shocked
  question or exclamation.
- The surprise must come from the topic's real counter-intuitive fact: the payoff later explains it.

TEACH SOMETHING NEW: the film reveals a fact most viewers did not know (the wow in the topic), not common
knowledge. Say it plainly once, at the payoff, as the punchline.

CLEAR FOR A 12-YEAR-OLD (nobody may be confused, not for one second)
- Everyday words. No jargon: a technical word ("gyroscope", "steering axis", "atmospheric pressure") is
  either replaced by plain words or explained in the SAME sentence with an everyday comparison ("a gyroscope,
  a spinning top that refuses to tip").
- One idea per sentence; the explanation is a short chain of cause -> effect steps, each step SHOWN by a prop
  event or an action at the moment it is said, and its part named by a label.
- The key fact is said once in one simple sentence a kid could repeat to a friend.
- Never say something the picture does not show; never show something the narration contradicts.

THE FORMAT (6-9 beats)
1. The hook beat above.
2. Then the story: Max's goal -> his naive attempt -> what goes wrong on screen -> the kids react -> the real
   way it works, step by step, each step SHOWN by a prop doing something -> the payoff (the cold open makes
   sense) -> a short button joke -> one teaser line for the next episode (end_card <= 5 words).
3. Every beat shows ONE clear thing a viewer gets with the sound off: a character action (cast) and/or a prop
   move (events). Say the word the action lands on (its "at" cue must be a word of that beat's text).
4. Explain clearly: name each real part only while it is on screen (labels, 1-3 words, pinned to the prop).
   Every fact comes from the fact sheet. No advice to the viewer ("you should", tips, lessons).
5. Rhythm: sentences of 3-12 words. The total word count is given in the prompt (it depends on the voice).

THE STAGE (what exists; choose only from these)
- place (always OUTDOORS, in front of a house or in nature): ground in grass|sand|dirt|snow;
  sky in day|golden|overcast|night; backdrop = 0-3 search terms for things far behind ("oak tree", "house").
- props: 3-9 real objects the story needs, each a 1-3 word BlenderKit search for ONE concrete object
  ("wooden ladder", "garden hose", "red car" - never scenes or abstract ideas), its real largest dimension in
  metres (size_m), one spot each (no two props on the same spot) and facing in degrees (0 = faces the camera).
  Hand-size props (under 0.6 m: a pot, a gauge, a phone) are put on a worktable at the front automatically,
  with Max behind it and the kids at its ends; their spot is ignored. Spots: center, left, right, front_left, front_right (near the camera), back_left, back, back_right,
  far_left, far_right.
- cast per beat: who (Max|Kid1|Kid2), do (a motion-capture clip by meaning), at (cue word), optional to (a spot
  or a prop id to walk to first) with move (walk|jog|run|sneak), look (camera | a prop id | a character).
  Characters always stay ON THE GROUND beside things: nobody climbs, sits on, rides or holds a prop (so
  write "Max stares up at the pole", never "Max on the ladder"). Props do the moving.
- events per beat: prop (id), does (appear|vanish|grow|shrink|rise|drop|spin|wobble|bounce|slide|tip_over|glow,
  or a SPECTACLE: steam_burst|smoke_burst (cartoon puffs out of the prop), launch (the prop shoots up
  spinning and lands), confetti, sparks, rumble (a shake that grows), lean_recover (tips toward a fall, then
  swings back upright by itself)), at (cue word), to (a spot, for slide).
  Use spectacles for the hook and the payoff; elsewhere at most one per beat.
- shot per beat: frame (wide|medium|close), on (a prop id, Max, Kid1, Kid2 or family), move
  (push_in|pull_out|orbit_left|orbit_right|static). Start wide enough that the viewer knows where we are;
  go close for reactions and for the key part.
- sounds per beat: 0-3 real sound effects by name ("door slam", "kids laughing", "water splash") at a cue word.
  Footsteps and the prop moves already make their own sounds.

WHAT THE VIEWER REALLY SEES (the film is judged on this, not on "shows")
- Only events, cast actions and labels are filmed; "shows" is your note, never rendered. Each event looks
  exactly like: """ + "; ".join(f"{k} = {v}" for k, v in EVENT_LOOKS.items()) + """.
- A prop moves only as a WHOLE: its parts (handlebars, a hinge, a valve, a gear inside) cannot move or
  glow on their own. Name a part with a label pinned to the prop, and show what it does with a whole prop
  that behaves the same way (a door, a pencil and a broom, a spinning top).
- The camera cuts to each prop as its event happens: at most 3 different props act in one beat, and each
  event's cue word is the word that describes that event.
- EXPLAIN WITH ARROWS: every step of the explanation (each cause -> effect) gets an arrow drawn over the prop
  while the step is said: arrows = [{prop, dir (left|right|up|down|cw|ccw), text (1-4 words: what moves and
  how, "LEANS RIGHT", "WHEEL TURNS IN"), at (the cue word)}], at most 2 per beat, together with the event that
  moves the prop the same way. Arrows + events + labels must SHOW each step without the sound.
- CHARACTERS ACT WITH PURPOSE: in a beat only the 1-2 characters the sentence is about act (one action each,
  the one the sentence says); everyone else is left out of cast and simply watches. No random gestures: a
  clip that the sentence does not explain confuses the viewer. Big reactions only in the hook and payoff."""


def _cast_item():
    return {"type": "object", "additionalProperties": False, "required": ["who", "do", "at", "to", "move", "look"],
            "properties": {"who": {"type": "string", "enum": WHO}, "do": {"type": "string", "enum": DO},
                           "at": {"type": "string"}, "to": {"type": "string"},
                           "move": {"type": "string", "enum": MOVES}, "look": {"type": "string"}}}


def schema():
    s = {"type": "string"}
    beat = {
        "type": "object", "additionalProperties": False,
        "required": ["id", "text", "shows", "hook_text", "chapter", "end_card", "emphasis", "shot", "cast", "events",
                     "arrows", "sounds", "labels", "callouts"],
        "properties": {
            "id": s, "text": s, "shows": s, "hook_text": s, "chapter": s, "end_card": s,
            "emphasis": {"type": "array", "items": s},
            "shot": {"type": "object", "additionalProperties": False, "required": ["frame", "on", "move"],
                     "properties": {"frame": {"type": "string", "enum": FRAMES}, "on": s,
                                    "move": {"type": "string", "enum": CAMERA_MOVES}}},
            "cast": {"type": "array", "items": _cast_item()},
            "events": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["prop", "does", "at", "to"],
                "properties": {"prop": s, "does": {"type": "string", "enum": EVENTS}, "at": s, "to": s}}},
            "arrows": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["prop", "dir", "text", "at"],
                "properties": {"prop": s, "dir": {"type": "string", "enum": ARROWS}, "text": s, "at": s}}},
            "sounds": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["name", "at"],
                "properties": {"name": s, "at": s}}},
            "labels": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["text", "anchor", "at"],
                "properties": {"text": s, "anchor": s, "at": s}}},
            "callouts": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["kind", "text", "tone", "at"],
                "properties": {"kind": {"type": "string", "enum": ["stamp", "counter"]}, "text": s,
                               "tone": {"type": "string", "enum": ["good", "bad"]}, "at": s}}},
        }}
    prop = {"type": "object", "additionalProperties": False, "required": ["id", "query", "size_m", "spot", "facing"],
            "properties": {"id": s, "query": s, "size_m": {"type": "number"},
                           "spot": {"type": "string", "enum": SPOTS}, "facing": {"type": "number"}}}
    place = {"type": "object", "additionalProperties": False, "required": ["ground", "sky", "backdrop"],
             "properties": {"ground": {"type": "string", "enum": GROUNDS}, "sky": {"type": "string", "enum": SKIES},
                            "backdrop": {"type": "array", "items": s}}}
    return {"type": "object", "additionalProperties": False,
            "required": ["title", "caption", "hashtags", "facts", "place", "props", "beats"],
            "properties": {"title": s, "caption": s, "hashtags": {"type": "array", "items": s},
                           "facts": {"type": "array", "items": s}, "place": place,
                           "props": {"type": "array", "items": prop}, "beats": {"type": "array", "items": beat}}}


def hook_problems(b):
    """The first second must STOP the scroll: a spectacle on a prop, cued on one of the first 3 words, a kid
    reacting, a sound, and a shot close enough to see it."""
    problems = []
    early = {w.lower() for w in _words(b.get("text", ""))[:3]} | {"start", ""}
    spect = [e for e in b.get("events", []) if e.get("does") in SPECTACLE]
    if not spect:
        problems.append(f"hook: no spectacle in the first beat; add one of {', '.join(SPECTACLE)} on a prop "
                        "(a claim over a static shot does not stop anyone scrolling)")
    elif not any(str(e.get("at", "")).lower().strip(".,!?") in early for e in spect):
        problems.append("hook: the spectacle must land in the first second: cue it on one of the first 3 words "
                        "or 'start'")
    if not any(c.get("who") in ("Kid1", "Kid2") and c.get("do") in REACT for c in b.get("cast", [])):
        problems.append(f"hook: a kid must react visibly ({', '.join(sorted(REACT))})")
    if not b.get("sounds"):
        problems.append("hook: give the surprise a big sound (sounds)")
    if (b.get("shot") or {}).get("frame") == "wide":
        problems.append("hook: a wide shot makes the surprise tiny; use medium or close")
    return problems


def validate(plan):
    problems = []
    beats = plan.get("beats", [])
    props = {p["id"] for p in plan.get("props", [])}
    if not 6 <= len(beats) <= 9:
        problems.append(f"use 6-9 beats (got {len(beats)})")
    if not 3 <= len(props) <= 9:
        problems.append(f"use 3-9 props (got {len(props)})")
    spots = [p["spot"] for p in plan.get("props", [])]
    if len(spots) != len(set(spots)):
        problems.append("two props share a spot; give each prop its own spot")
    for p in plan.get("props", []):
        if not 0.05 <= float(p.get("size_m") or 0) <= 25:
            problems.append(f"prop {p['id']}: size_m {p.get('size_m')} is not a real object size")
        if len(p.get("query", "").split()) > 3:
            problems.append(f"prop {p['id']}: search '{p['query']}' must be 1-3 words naming one object")
    n = sum(len(_words(b["text"])) for b in beats)
    lo, hi = words_range()
    if not lo <= n <= hi:
        problems.append(f"narration is {n} words; it must be {lo}-{hi} to land at 60-65 s with this voice")
    if beats:
        if len(_words(beats[0]["text"])) > 12:
            problems.append("the cold open must be <= 12 words")
        if not beats[0].get("hook_text") or len(_words(beats[0]["hook_text"])) > 5:
            problems.append("the first beat needs a hook_text of 1-5 words")
        problems += hook_problems(beats[0])
    ids = [b["id"] for b in beats]
    if len(ids) != len(set(ids)):
        problems.append("beat ids must be unique")
    names = props | set(WHO) | {"family"}
    for b in beats:
        bid = b["id"]
        if ADVICE.search(b["text"]):
            problems.append(f"{bid}: '{ADVICE.search(b['text']).group(0)}' is advice; comment on Max instead")
        if not b.get("cast") and not b.get("events"):
            problems.append(f"{bid}: nothing happens on screen; add a cast action or a prop event")
        if b.get("shot", {}).get("on") not in names:
            problems.append(f"{bid}: shot.on '{b.get('shot', {}).get('on')}' must be a prop id, Max, Kid1, Kid2 or "
                            "family")
        for c in b.get("cast", []):
            if c.get("at") and c["at"] != "start" and not _has(b["text"], c["at"]):
                problems.append(f"{bid}: cast cue '{c['at']}' is not a word of the beat's text")
            if c.get("to") and c["to"] not in props and c["to"] not in SPOTS and c["to"] not in WHO:
                problems.append(f"{bid}: '{c['to']}' is neither a spot, a prop nor a character")
        who = [c.get("who") for c in b.get("cast", [])]
        if bid != beats[0]["id"] and (len(set(who)) > MAX_ACTORS or len(who) != len(set(who))):
            problems.append(f"{bid}: only the 1-{MAX_ACTORS} characters the sentence is about act, one action each "
                            "(the others watch)")
        for a in b.get("arrows", []):
            if a.get("prop") not in props:
                problems.append(f"{bid}: arrow prop '{a.get('prop')}' is not a prop id")
            if a.get("dir") not in ARROWS:
                problems.append(f"{bid}: arrow dir '{a.get('dir')}' must be one of {', '.join(ARROWS)}")
            if a.get("at") and not _has(b["text"], a["at"]):
                problems.append(f"{bid}: arrow cue '{a['at']}' is not a word of the beat's text")
            if len(_words(a.get("text", ""))) > 4:
                problems.append(f"{bid}: arrow text '{a.get('text')}' is longer than 4 words")
        if len(b.get("arrows", [])) > 2:
            problems.append(f"{bid}: at most 2 arrows per beat")
        acting = {e.get("prop") for e in b.get("events", [])}
        if len(acting) > MAX_ACTING_PROPS:
            problems.append(f"{bid}: {len(acting)} props act in one beat; at most {MAX_ACTING_PROPS} (split the beat "
                            "or drop one)")
        for e in b.get("events", []):
            if e.get("prop") not in props:
                problems.append(f"{bid}: event prop '{e.get('prop')}' is not a prop id")
            if e.get("at") and not _has(b["text"], e["at"]):
                problems.append(f"{bid}: event cue '{e['at']}' is not a word of the beat's text")
        for lb in b.get("labels", []):
            if lb["anchor"] not in props and lb["anchor"] not in WHO:
                problems.append(f"{bid}: label anchor '{lb['anchor']}' is not a prop id or a character")
            if not _has(b["text"], lb["at"]):
                problems.append(f"{bid}: label cue '{lb['at']}' is not a word of the beat's text")
            if len(_words(lb["text"])) > 3:
                problems.append(f"{bid}: label '{lb['text']}' is longer than 3 words")
        for s in b.get("sounds", []):
            if not _has(b["text"], s["at"]):
                problems.append(f"{bid}: sound cue '{s['at']}' is not a word of the beat's text")
        if len(b.get("callouts", [])) > 1:
            problems.append(f"{bid}: more than one callout")
        long = [s for s in re.split(r"(?<=[.!?:;])\s+", b["text"]) if len(_words(s)) > 16]
        if long:
            problems.append(f"{bid}: sentence too long for short-form: '{long[0][:60]}...'")
    return problems


def repair(plan):
    """Drop what still breaks a rule after the repair turn (an unknown prop, a cue that is not said), so the
    film can always be made; the cue falls back to the start of the beat."""
    props = {p["id"] for p in plan.get("props", [])}
    for b in plan.get("beats", []):
        b["events"] = [e for e in b.get("events", []) if e.get("prop") in props]
        keep = list(dict.fromkeys([(b.get("shot") or {}).get("on")] + [e["prop"] for e in b["events"]]))
        keep = [p for p in keep if p in props][:MAX_ACTING_PROPS]
        b["events"] = [e for e in b["events"] if e["prop"] in keep]
        b["labels"] = [lb for lb in b.get("labels", []) if lb.get("anchor") in props | set(WHO)
                       and _has(b["text"], lb.get("at", ""))]
        for item in b.get("cast", []) + b.get("events", []) + b.get("sounds", []):
            if item.get("at") and not _has(b["text"], item["at"]):
                item["at"] = "start"
        if b.get("shot", {}).get("on") not in props | set(WHO) | {"family"}:
            b.setdefault("shot", {})["on"] = "family"
        b["callouts"] = b.get("callouts", [])[:1]
        b["arrows"] = [a for a in b.get("arrows", []) if a.get("prop") in props and a.get("dir") in ARROWS][:2]
        for a in b["arrows"]:
            a["text"] = " ".join(_words(a.get("text", ""))[:4])
            if a.get("at") and not _has(b["text"], a["at"]):
                a["at"] = "start"
        if b is not plan["beats"][0]:
            seen, cast = set(), []
            for c in b.get("cast", []):       # one action each, at most MAX_ACTORS characters: the rest watch
                if c.get("who") not in seen and len(seen) < MAX_ACTORS:
                    seen.add(c.get("who"))
                    cast.append(c)
            b["cast"] = cast
    _force_hook(plan, props)
    return plan


def restage_hook(plan, why="", call=None):
    """A new staging for the FIRST beat when the review says it would not stop a scroll. The words stay (the
    voice and timing are already recorded); only what the picture shows changes. Never fails: a bad answer
    becomes a bigger forced hook (a second spectacle and a kid knocked over)."""
    import copy
    b = copy.deepcopy(plan["beats"][0])
    props = {p["id"] for p in plan.get("props", [])}
    try:
        from agents import llm
        call = call or (lambda s, p, sc: llm.ask(s, p, sc, effort="high"))
        beat_schema = schema()["properties"]["beats"]["items"]
        prompt = (f"THE FIRST BEAT OF THIS FILM DOES NOT STOP THE SCROLL. A sound-off viewer said: {why}\n\n"
                  f"Re-stage it: keep the text EXACTLY (\"{b['text']}\") and id {b['id']}; change only shot, cast, "
                  "events, sounds and hook_text so the FIRST SECOND shows something spectacular and funny.\n\n"
                  f"PROPS: {json.dumps(plan.get('props', []))}\n\nCURRENT BEAT: {json.dumps(b)}")
        new = call(RULES, prompt, beat_schema)
        for k in ("shot", "cast", "events", "sounds", "hook_text"):
            if new.get(k):
                b[k] = new[k]
    except Exception as e:  # noqa: BLE001  (never blocks: the forced hook below)
        log.warning("hook re-staging failed (%s); forcing a bigger hook", str(e)[:120])
    b["events"] = [e for e in b.get("events", []) if e.get("prop") in props]
    for item in b.get("cast", []) + b.get("events", []) + b.get("sounds", []):
        if item.get("at") and not _has(b["text"], item["at"]):
            item["at"] = "start"
    for c in b.get("cast", []):
        for k in ("to", "look", "move"):
            if not c.get(k):
                c.pop(k, None)
    if hook_problems(b) or b == plan["beats"][0]:
        target = (b.get("shot") or {}).get("on")
        target = target if target in props else (sorted(props)[0] if props else None)
        if target:
            b.setdefault("events", []).insert(0, {"prop": target, "does": "confetti", "at": "start"})
        b.setdefault("cast", []).append({"who": "Kid1", "do": "knocked", "at": "start"})
        tmp = {"beats": [b]}
        _force_hook(tmp, props)
        b = tmp["beats"][0]
    return b


RESIZE_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["beats"],
                 "properties": {"beats": {"type": "array", "items": {
                     "type": "object", "additionalProperties": False, "required": ["id", "text"],
                     "properties": {"id": {"type": "string"}, "text": {"type": "string"}}}}}}


def _cues(b):
    return {str(x.get("at", "")) for x in b.get("cast", []) + b.get("events", []) + b.get("sounds", []) +
            b.get("labels", []) + b.get("callouts", []) if x.get("at") and x.get("at") != "start"}


def resize(plan, target_words, call=None):
    """The narration rewritten to ~target_words (the recorded voice could not fit 60-65 s), beat by beat, same
    meaning, same jokes, and EVERY cue word the animation listens for kept. Returns the new plan, or the old one
    if the rewrite breaks a cue (never fails)."""
    import copy
    now = sum(len(_words(b["text"])) for b in plan["beats"])
    try:
        from agents import llm
        call = call or (lambda s, p, sc: llm.ask(s, p, sc, effort="medium"))
        verb = "LENGTHEN" if target_words > now else "SHORTEN"
        prompt = (f"{verb} this narration from {now} to about {target_words} words in total, beat by beat (keep "
                  "the share of each beat). Keep the meaning, the jokes, the plain words, the cold open <= 12 words, "
                  "and keep EVERY listed cue word exactly (the animation lands on them). Add clarity, not filler: "
                  "an everyday comparison, a reaction line, a beat of suspense.\n\n" +
                  "\n".join(f"[{b['id']}] cues: {sorted(_cues(b))}\n{b['text']}" for b in plan["beats"]))
        out = call(RULES, prompt, RESIZE_SCHEMA)
        texts = {b["id"]: b["text"] for b in out.get("beats", [])}
        new = copy.deepcopy(plan)
        for b in new["beats"]:
            t = texts.get(b["id"], "").strip()
            if not t or any(not _has(t, c) for c in _cues(b)):
                return plan                       # a lost cue would desync the animation: keep the old text
            b["text"] = t
        if len(_words(new["beats"][0]["text"])) > 12:
            return plan
        return new
    except Exception as e:  # noqa: BLE001
        log.warning("narration resize failed (%s)", str(e)[:120])
        return plan


PROPS_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["props"],
                "properties": {"props": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False, "required": ["id", "query"],
                    "properties": {"id": {"type": "string"}, "query": {"type": "string"}}}}}}


def replace_props(plan, missing, call=None):
    """New searches for the props no 3D model was found for (they were filmed as plain coloured shapes the
    narration still called "a spinning top"). Ids stay, so the beats are untouched. Never fails: the old plan
    comes back when the call does."""
    from agents import llm
    call = call or (lambda s, p, sc: llm.ask(s, p, sc, effort="medium"))
    story = "\n".join(f"[{b['id']}] {b['text']}" for b in plan.get("beats", []))
    lines = "\n".join(f"- {p['id']}: '{p['query']}' ({p.get('size_m')} m)" for p in plan.get("props", [])
                      if p["id"] in missing)
    try:
        out = call("You choose 3D models for an animated short from a free online library of common objects "
                   "(furniture, vehicles, tools, toys, kitchenware, sports gear, plants, animals).",
                   f"THE STORY:\n{story}\n\nNo model was found for these searches:\n{lines}\n\nFor each, give a "
                   "different 1-3 word search for a common, concrete object a viewer recognises at once and that "
                   "plays the same part in the story (simpler words, the everyday name). Keep each id.",
                   PROPS_SCHEMA)
    except Exception as e:  # noqa: BLE001
        log.warning("prop replacement unavailable (%s)", str(e)[:100])
        return plan
    new = {p["id"]: p["query"].strip() for p in out.get("props", [])
           if p.get("id") in missing and p.get("query") and len(p["query"].split()) <= 3}
    if not new:
        return plan
    plan = json.loads(json.dumps(plan))
    for p in plan.get("props", []):
        if p["id"] in new and new[p["id"]].lower() != p["query"].lower():
            log.info("stage writer: prop %s: '%s' -> '%s'", p["id"], p["query"], new[p["id"]])
            p["query"] = new[p["id"]]
    return plan


def _force_hook(plan, props):
    """A plan whose hook still breaks the rules gets a minimal real one: the shot's prop (or the first prop)
    launches on the first word, Kid2 jumps, a whoosh plays, the shot is medium. Never a flat opening."""
    if not plan.get("beats"):
        return
    b = plan["beats"][0]
    problems = hook_problems(b)
    if not problems:
        return
    target = (b.get("shot") or {}).get("on")
    target = target if target in props else (sorted(props)[0] if props else None)
    if target and not any(e.get("does") in SPECTACLE for e in b.get("events", [])):
        b.setdefault("events", []).insert(0, {"prop": target, "does": "launch", "at": "start"})
    for e in b.get("events", []):
        if e.get("does") in SPECTACLE:
            e["at"] = "start"
    if not any(c.get("who") in ("Kid1", "Kid2") and c.get("do") in REACT for c in b.get("cast", [])):
        b.setdefault("cast", []).append({"who": "Kid2", "do": "jump", "at": "start"})
    if not b.get("sounds"):
        b["sounds"] = [{"name": "cartoon boing", "at": "start"}]
    if (b.get("shot") or {}).get("frame") == "wide":
        b["shot"]["frame"] = "medium"


def _clean(plan):
    for b in plan["beats"]:
        for k in ("hook_text", "chapter", "end_card", "labels", "callouts", "emphasis"):
            if not b.get(k):
                b.pop(k, None)
        for c in b.get("cast", []):
            for k in ("to", "look", "move"):
                if not c.get(k):
                    c.pop(k, None)
        for e in b.get("events", []):
            if not e.get("to"):
                e.pop("to", None)
    plan["world"] = "stage"
    plan.setdefault("voice", "energetic")
    plan.setdefault("target_seconds", 62)
    slug = re.sub(r"[^a-z0-9]+", "_", plan["title"].lower()).strip("_")[:40]
    plan["id"] = f"stage_{slug}"
    return plan


def prompt(topic, facts, angle, problems=None, previous=None):
    text = (f"TOPIC: {topic}\nANGLE: {angle or 'the funniest true story about how this works'}\n\n"
            f"FACT SHEET (use only these):\n{facts}\n\nMOTION CLIPS (cast.do): {', '.join(DO)}\n\n"
            f"TOTAL NARRATION: {words_range()[0]}-{words_range()[1]} words across all beats.")
    if problems:
        text += ("\n\nYOUR PREVIOUS PLAN BROKE THESE RULES; fix exactly these and keep the rest:\n- "
                 + "\n- ".join(problems) + "\n\nPREVIOUS PLAN:\n" + json.dumps(previous))
    return text


CLARITY_SCHEMA = {"type": "object", "additionalProperties": False,
                  "required": ["learned", "confusing", "jargon", "unshown", "fun", "clear", "fix"],
                  "properties": {"learned": {"type": "string"}, "confusing": {"type": "array", "items": {"type": "string"}},
                                 "jargon": {"type": "array", "items": {"type": "string"}},
                                 "unshown": {"type": "array", "items": {"type": "string"}},
                                 "fun": {"type": "integer"}, "clear": {"type": "boolean"}, "fix": {"type": "string"}}}
FUN_MIN = 4
CLARITY_ROUNDS = 3


def screen(b, plan, missing=()):
    """What the stage REALLY films for a beat, in plain words, built from its data (never from the writer's own
    "shows" note: the judge trusted it, passed the script, and 8 of 9 beats then said things the picture never
    showed). `missing`: prop ids with no 3D model, filmed as a plain coloured shape."""
    names = {p["id"]: p.get("query") or p["id"] for p in plan.get("props", [])}

    def what(pid):
        if pid in missing:
            return f"a plain coloured shape standing in for '{names.get(pid, pid)}' (no model)"
        return f"the {names.get(pid, pid)}"
    shot = b.get("shot") or {}
    out = [f"camera: {shot.get('frame', 'medium')} shot on {what(shot['on']) if shot.get('on') in names else shot.get('on', 'family')}"]
    out += [f"{what(e['prop'])} {EVENT_LOOKS.get(e.get('does'), e.get('does'))} (on '{e.get('at') or 'start'}')"
            for e in b.get("events", []) if e.get("prop") in names]
    out += [f"{c['who']} {c.get('do', 'idle').replace('_', ' ')}" + (f" after walking to {c['to']}" if c.get("to") else "")
            for c in b.get("cast", [])]
    out += [f"tag '{lb['text']}' pinned to {what(lb['anchor']) if lb['anchor'] in names else lb['anchor']}"
            for lb in b.get("labels", [])]
    out += [f"a big arrow {ARROW_LOOKS.get(a.get('dir'), a.get('dir'))} drawn over {what(a['prop'])}, captioned "
            f"'{a.get('text', '')}' (on '{a.get('at') or 'start'}')" for a in b.get("arrows", []) if a.get("prop") in names]
    watching = [w for w in WHO if w not in {c.get("who") for c in b.get("cast", [])}]
    if watching:
        out.append(f"{' and '.join(watching)} watch{'es' if len(watching) == 1 else ''}")
    return "; ".join(out)


def clarity(plan, call=None, missing=()):
    """A curious 12-year-old reads the film (each beat: what is said + what is REALLY on screen) BEFORE the voice
    is recorded, while changing words is free. Returns the judge's report, or None if it could not run."""
    try:
        from agents import llm
        call = call or (lambda s, p, sc: llm.ask(s, p, sc, effort="medium"))
        film = "\n".join(f"[{b['id']}] SAID: {b['text']}\n      ON SCREEN: {screen(b, plan, missing)}"
                         for b in plan["beats"])
        system = ("You are a curious, easily bored 12-year-old watching a 60-second funny science short on your "
                  "phone. Be honest and specific. ON SCREEN is everything you see: nothing else moves, and a part "
                  "of an object cannot move by itself.")
        ask = ("THE FILM, beat by beat:\n" + film + "\n\nlearned: in one sentence, the new thing you now know (or '' if "
               "nothing). confusing: every moment you would not understand. jargon: every word a 12-year-old would "
               "not know that is not explained right where it is used. unshown: every claim of SAID that ON SCREEN "
               "does not show at that beat, as '[beat id] claim -> what you actually see' (a claim illustrated by a "
               "comparison object that is on screen counts as shown). fun: 1 (boring) to 5 (I'd send it to a "
               "friend). clear: true only if you understood every step of the explanation. fix: the single most "
               "useful change.")
        return call(system, ask, CLARITY_SCHEMA)
    except Exception as e:  # noqa: BLE001  (advice only: never blocks)
        log.warning("clarity check unavailable (%s)", str(e)[:100])
        return None


def clarity_problems(report):
    if not report:
        return []
    out = []
    if not report.get("clear") or report.get("confusing"):
        out += [f"clarity: a 12-year-old is confused here: {c}" for c in report.get("confusing") or ["(unclear)"]]
    out += [f"clarity: '{j}' is jargon; replace it with plain words or explain it in the same sentence with an "
            "everyday comparison" for j in report.get("jargon") or []]
    out += [f"picture: said but not shown: {u}; add the event or label that shows it, or say only what is shown"
            for u in report.get("unshown") or []]
    if int(report.get("fun") or 0) < FUN_MIN:
        out.append(f"fun: rated {report.get('fun')}/5; make it funnier: {report.get('fix', '')}")
    if not (report.get("learned") or "").strip():
        out.append("teach: the viewer did not learn anything new; say the key fact once in one simple sentence")
    return out


def write(topic, facts, angle=None, call=None, judge=None):
    from agents import llm
    call = call or (lambda s, p, sc: llm.ask(s, p, sc, effort="high"))
    plan, problems = None, None
    for _ in range(2):
        plan = _clean(call(RULES, prompt(topic, facts, angle, problems, plan), schema()))
        problems = validate(plan)
        if not problems:
            break
    if problems:
        for p in problems:
            log.warning("stage writer: %s (repaired)", p)
        plan = repair(plan)
        plan["quality_warnings"] = problems
    # the clarity gate: a plan that would confuse, bore or teach nothing is rewritten with the judge's words, up to
    # CLARITY_ROUNDS times; the clearest valid draft wins (one round shipped a script with 11 open confusions)
    report = clarity(plan, judge)
    issues = clarity_problems(report)
    best = (len(issues), plan, report, issues)
    for k in range(CLARITY_ROUNDS):
        if not issues:
            break
        log.warning("stage writer: clarity round %d: %s", k + 1, "; ".join(issues)[:400])
        try:
            again = _clean(call(RULES, prompt(topic, facts, angle, issues, plan), schema()))
        except Exception as e:  # noqa: BLE001
            log.warning("clarity rewrite failed (%s)", str(e)[:100])
            break
        if validate(again):
            again = repair(again)               # keep the film makeable; clarity is what this round is about
        plan, report = again, clarity(again, judge)
        issues = clarity_problems(report)
        if len(issues) < best[0]:
            best = (len(issues), plan, report, issues)
    _n, plan, report, issues = best
    if issues:
        plan["quality_warnings"] = plan.get("quality_warnings", []) + issues
    if report:
        plan["clarity"] = {k: report.get(k) for k in ("learned", "fun", "clear")}
    return plan
