"""
Hard checks on a storyboard before anything renders (pure Python). Every failure is a sentence the planner can
act on; the storyboard stage sends them back for a rewrite. `repair` first fixes in code what needs no judgement.
"""
from __future__ import annotations

from . import hosts, layout, vocab

MAX_HOLD = 7.0          # seconds a framing may hold
MIN_HOLD = 3.2          # seconds a framing must hold: the viewer needs time to read what changed
MIN_OVERLAP = 0.4       # two parts sharing a spot for less than this (one leaving as the other lands) is fine


def _ref(ref: str) -> tuple[str, str | None]:
    pid, _, anchor = str(ref).partition(".")
    return pid, (anchor or None)


def _anchors(ptype: str) -> list[str]:
    return vocab.PARTS[ptype][1] + vocab.PARTS[ptype][2] + ["center"]


def _clashes(sb, words, duration):
    """[(a, b)] of parts on screen together in the same slot / stage spot."""
    span = layout.spans(sb, words, duration)
    spot = {p["id"]: ("slot", p["mount"]) if p.get("mount") else ("stage", p.get("stage") or "front")
            for p in sb["parts"]}
    out = []
    ids = [p["id"] for p in sb["parts"]]
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if spot[a] == spot[b] and min(span[a][1], span[b][1]) - max(span[a][0], span[b][0]) >= MIN_OVERLAP:
                out.append((a, b))
    return out


def check(sb: dict, words: list[dict], duration: float, facts: dict | None = None) -> list[str]:
    errs: list[str] = []
    n_words = len(words)
    m = sb.get("machine") or {}
    if m.get("host") not in hosts.HOSTS:
        errs.append(f"machine.host must be one of {list(hosts.HOSTS)}")
    slots = hosts.slot_names(m["host"]) if m.get("host") in hosts.HOSTS else []
    parts = {}
    for p in sb.get("parts", []):
        if p.get("type") not in vocab.PARTS:
            errs.append(f"part {p.get('id')}: unknown type '{p.get('type')}' (use one of the kit's PARTS)")
            continue
        if p["id"] in parts or p["id"] == "machine":
            errs.append(f"part id '{p['id']}' is used twice (or is 'machine')")
        if p.get("mount") and p["mount"] not in slots:
            errs.append(f"part {p['id']}: the {m.get('host')} has no slot '{p['mount']}' (slots: {slots})")
        if not p.get("mount") and p.get("stage") not in vocab.STAGES:
            errs.append(f"part {p['id']}: give it a mount slot (machine part) or a stage spot {vocab.STAGES} (prop)")
        if p.get("size") and p["size"] not in vocab.SIZES:
            errs.append(f"part {p['id']}: unknown size '{p['size']}'")
        parts[p["id"]] = p
    conns = {}
    for c in sb.get("connections", []):
        if c.get("kind") not in vocab.CONNECT:
            errs.append(f"connection {c.get('id')}: unknown kind '{c.get('kind')}'")
        for end in ("from", "to"):
            pid, port = _ref(c.get(end, ""))
            if pid not in parts:
                errs.append(f"connection {c.get('id')}: '{c.get(end)}' names no part")
            elif not parts[pid].get("mount"):
                errs.append(f"connection {c.get('id')}: '{pid}' is a prop; connect mounted machine parts only")
            elif port and port not in _anchors(parts[pid]["type"]):
                errs.append(f"connection {c.get('id')}: {parts[pid]['type']} has no port '{port}'")
        conns[c.get("id")] = c

    def word_ok(i, what):
        if not isinstance(i, int) or not 0 <= i < n_words:
            errs.append(f"{what}: word index {i} is outside 0..{n_words - 1}")
            return False
        return True

    for e in sb.get("events", []):
        what = f"event {e.get('do')} on {e.get('target')}"
        if e.get("do") not in vocab.EVENTS:
            errs.append(f"{what}: unknown event")
            continue
        word_ok(e.get("word"), what)
        pid, anchor = _ref(e.get("target", ""))
        if pid == "machine":
            if e["do"] not in ("appear", "highlight", "shake", "wash"):
                errs.append(f"{what}: the machine itself can only appear, highlight or shake")
            continue
        if pid not in parts and pid not in conns:
            errs.append(f"{what}: no part or connection '{pid}'")
            continue
        if pid in parts:
            ptype = parts[pid]["type"]
            if anchor and anchor not in _anchors(ptype):
                errs.append(f"{what}: {ptype} has no anchor '{anchor}' (has {vocab.PARTS[ptype][1]})")
            if e["do"] in ("run", "set") and not vocab.PARTS[ptype][3]:
                errs.append(f"{what}: {ptype} has nothing to run (no drivers)")
            if e["do"] == "fill" and ptype not in vocab.CONTAINERS:
                errs.append(f"{what}: {ptype} is not a container")
        if e["do"] in ("flow", "fill") and e.get("kind") not in vocab.FLOWS:
            errs.append(f"{what}: flow kind '{e.get('kind')}' is not one of {list(vocab.FLOWS)}")
        if e["do"] == "appear" and e.get("from"):
            if e["from"] not in parts:
                errs.append(f"{what}: flies out of unknown prop '{e['from']}'")
            elif parts[e["from"]].get("mount"):
                errs.append(f"{what}: 'from' must be a prop (stage part), not the mounted '{e['from']}'")
    fact_ids = {f["id"] for f in (facts or {}).get("facts", [])}
    for lb in sb.get("labels", []):
        what = f"label '{lb.get('text')}'"
        word_ok(lb.get("word"), what)
        word_ok(lb.get("until_word"), what)
        if isinstance(lb.get("word"), int) and isinstance(lb.get("until_word"), int) and lb["until_word"] <= lb["word"]:
            errs.append(f"{what}: until_word must come after word")
        pid, anchor = _ref(lb.get("anchor", ""))
        if pid == "machine":
            pass
        elif pid not in parts:
            errs.append(f"{what}: anchor part '{pid}' does not exist")
        elif anchor and anchor not in _anchors(parts[pid]["type"]):
            errs.append(f"{what}: {parts[pid]['type']} has no anchor '{anchor}'")
        if len(str(lb.get("text", "")).split()) > 4:
            errs.append(f"{what}: max 4 words on a pill")
        if any(ch.isdigit() for ch in str(lb.get("text", ""))) and lb.get("fact_id") not in fact_ids:
            errs.append(f"{what}: a number on screen needs a fact_id from facts.json")
        if lb.get("variant", "neutral") not in vocab.LABEL_VARIANTS:
            errs.append(f"{what}: unknown variant '{lb.get('variant')}'")
    for x in sb.get("sfx", []):
        word_ok(x.get("word"), f"sfx {x.get('cue')}")
        if x.get("cue") not in vocab.SFX:
            errs.append(f"sfx: unknown cue '{x.get('cue')}'")
    if errs:
        return errs
    span = layout.spans(sb, words, duration)
    for a, b in _clashes(sb, words, duration):
        errs.append(f"parts '{a}' and '{b}' share the spot {parts[a].get('mount') or parts[a].get('stage')} while "
                    "both are on screen: use another slot / spot, or remove one first")
    # shots: cover the video in word order, frame parts that are on screen
    shots = sb.get("shots", [])
    if not shots:
        errs.append("no shots")
    starts = [s.get("start_word") for s in shots]
    if shots and starts[0] != 0:
        errs.append("the first shot must start at word 0")
    if any(not isinstance(a, int) or not isinstance(b, int) or b <= a for a, b in zip(starts, starts[1:])):
        errs.append("shots must start on increasing word indices")
        return errs
    for i, s in enumerate(shots):
        if s.get("frame") not in vocab.FRAMES:
            errs.append(f"shot {i + 1}: frame must be one of {vocab.FRAMES}")
        if s.get("move") not in vocab.MOVES:
            errs.append(f"shot {i + 1}: move must be one of {vocab.MOVES}")
        on = s.get("on") or []
        if s.get("frame") != "machine" and not on:
            errs.append(f"shot {i + 1}: say which part(s) it frames ('on')")
        for pid in on:
            if pid not in parts:
                errs.append(f"shot {i + 1}: frames unknown part '{pid}'")
        if s.get("frame") == "prop" and any(parts.get(pid, {}).get("mount") for pid in on):
            errs.append(f"shot {i + 1}: a prop shot frames props only")
        t0 = words[min(s["start_word"], n_words - 1)]["start"]
        nxt = shots[i + 1]["start_word"] if i + 1 < len(shots) else None
        t1 = words[min(nxt, n_words - 1)]["start"] if nxt is not None else duration
        mid = (t0 + t1) / 2
        if on and all(pid in span for pid in on) and not any(span[pid][0] <= mid <= span[pid][1] for pid in on):
            errs.append(f"shot {i + 1} frames {on}, none of which is on screen at {mid:.1f} s")
        if t1 - t0 > MAX_HOLD + 0.01:
            errs.append(f"shot {i + 1} holds {t1 - t0:.1f} s: change the framing at least every {MAX_HOLD:.0f} s")
        if i and t1 - t0 < MIN_HOLD - 0.01:
            errs.append(f"shot {i + 1} lasts only {t1 - t0:.1f} s: hold every shot at least {MIN_HOLD:.1f} s")
    appeared = {str(e.get("target")).split(".")[0] for e in sb.get("events", []) if e.get("do") == "appear"}
    present = [pid for pid, p in parts.items() if p.get("mount") and pid not in appeared]
    if len(present) > 1:
        errs.append(f"{present} are mounted from the first frame: build the machine up, part by part "
                    "(give each an 'appear' event on the word that introduces it)")
    return errs


# ------------------------------------------------------------ deterministic repairs

_GROUP = lambda s: s.split("_")[0]          # noqa: E731  inside_top -> inside


def repair(sb: dict, words: list[dict], duration: float, facts: dict | None = None) -> list[str]:
    """Fix in place what code can fix without judgement, so the planner only rewrites what needs it.
    Returns what was changed."""
    fixes: list[str] = []
    n = len(words)
    m = sb.setdefault("machine", {})
    if m.get("host") not in hosts.HOSTS:
        fixes.append(f"unknown host '{m.get('host')}' became 'machine'")
        m["host"] = "machine"
    slots = hosts.slot_names(m["host"])
    sb["parts"] = [p for p in sb.get("parts", []) if p.get("type") in vocab.PARTS and p.get("id") != "machine"]
    parts = {p["id"]: p for p in sb["parts"]}
    # a part that appears AGAIN later (the hook object coming back) becomes a copy with its own entrance:
    # a part has one life on screen, so its second appear used to hide it from the start
    entered: set = set()
    for e in sorted(sb.get("events", []), key=lambda e: e.get("word", 0)):
        pid = str(e.get("target", "")).split(".")[0]
        if e.get("do") != "appear" or pid not in parts:
            continue
        if pid not in entered:
            entered.add(pid)
            continue
        k = 2
        while f"{pid}_{k}" in parts:
            k += 1
        new, w0 = f"{pid}_{k}", e.get("word", 0)
        clone = dict(parts[pid], id=new)
        sb["parts"].append(clone)
        parts[new] = clone
        entered.add(new)

        def swap(ref, pid=pid, new=new):
            head, dot, tail = str(ref).partition(".")
            return new + dot + tail if head == pid else ref
        for x in sb.get("events", []):
            if x.get("word", 0) >= w0:
                x["target"] = swap(x.get("target", ""))
                if x.get("from") == pid:
                    x["from"] = new
        for lb in sb.get("labels", []):
            if lb.get("word", 0) >= w0:
                lb["anchor"] = swap(lb.get("anchor", ""))
        for s in sb.get("shots", []):
            if s.get("start_word", 0) >= w0:
                s["on"] = [swap(q) for q in s.get("on", [])]
        fixes.append(f"'{pid}' comes back at word {w0}: a copy '{new}' makes that entrance")
    conn_ids = {c.get("id") for c in sb.get("connections", [])}
    connected = {str(c.get(e, "")).split(".")[0] for c in sb.get("connections", []) for e in ("from", "to")}
    sources = {e.get("from") for e in sb.get("events", []) if e.get("do") == "appear" and e.get("from")}
    for p in sb["parts"]:
        if p.get("mount") and p["mount"] not in slots:
            fixes.append(f"'{p['id']}' had no slot '{p['mount']}'")
            p["mount"] = None
            p["_needs_slot"] = True
        if p.get("mount"):
            p["stage"] = None
        elif p["id"] in connected or p.get("_needs_slot"):
            p["_needs_slot"] = True
        elif p.get("stage") not in vocab.STAGES:
            p["stage"] = "front"
    for p in sb["parts"]:                      # a prop something flies out of stays a prop
        if p["id"] in sources and p.get("mount"):
            p["stage"], p["mount"] = "front", None
            fixes.append(f"'{p['id']}' is a prop (a part flies out of it)")

    def clamp(i):
        return max(0, min(int(i) if isinstance(i, (int, float)) else 0, n - 1))

    kept = []
    for e in sb.get("events", []):
        e["word"] = clamp(e.get("word", 0))
        pid, _, anchor = str(e.get("target", "")).partition(".")
        if pid == "machine":
            if e.get("do") in ("appear", "highlight", "shake", "wash"):
                kept.append(e)
            continue
        if pid not in parts and pid not in conn_ids:
            fixes.append(f"dropped {e.get('do')} on unknown '{pid}'")
            continue
        if pid in parts:
            ptype = parts[pid]["type"]
            if anchor and anchor not in _anchors(ptype):
                e["target"] = pid
            if e.get("do") == "fill" and ptype not in vocab.CONTAINERS:
                if ptype in ("coil", "radiator"):
                    e.update(do="flow", on=True, target=pid)
                    fixes.append(f"fill on {ptype} '{pid}' became a flow through it")
                else:
                    fixes.append(f"dropped fill on {ptype} '{pid}' (not a container)")
                    continue
            if e.get("do") in ("run", "set") and not vocab.PARTS[ptype][3]:
                fixes.append(f"dropped {e['do']} on {ptype} '{pid}' (nothing to run)")
                continue
        if e.get("do") in ("flow", "fill") and e.get("kind") not in vocab.FLOWS:
            e["kind"] = "air"
        if e.get("do") == "appear" and e.get("from") and (e["from"] not in parts or e["from"] == pid):
            e["from"] = None
        kept.append(e)
    sb["events"] = kept

    # parts that must be mounted get a free slot; clashing parts move to a free slot / spot of the same kind
    span = layout.spans(sb, words, duration)

    def busy(pid, spot):
        a0, a1 = span.get(pid, (0, duration))
        for q in sb["parts"]:
            if q["id"] == pid:
                continue
            qs = q.get("mount") or ("stage:" + (q.get("stage") or "front"))
            b0, b1 = span.get(q["id"], (0, duration))
            if qs == spot and min(a1, b1) - max(a0, b0) >= MIN_OVERLAP:
                return True
        return False

    order = sorted(sb["parts"], key=lambda p: span.get(p["id"], (0, 0))[0])
    for p in order:
        if p.pop("_needs_slot", False) and not p.get("mount"):
            free = [s for s in slots if not busy(p["id"], s)]
            p["mount"], p["stage"] = (free or slots)[0], None
            fixes.append(f"'{p['id']}' mounted in {p['mount']}")
    for _ in range(12):
        clash = _clashes(sb, words, duration)
        if not clash:
            break
        a, b = clash[0]
        mover = parts[b] if span[b][0] >= span[a][0] else parts[a]      # the later arrival moves
        if mover.get("mount"):
            same = [s for s in slots if _GROUP(s) == _GROUP(mover["mount"]) and not busy(mover["id"], s)]
            other = [s for s in slots if not busy(mover["id"], s)]
            to = (same or other or [None])[0]
            if to is None:
                break
            fixes.append(f"'{mover['id']}' moved from {mover['mount']} to {to}")
            mover["mount"] = to
        else:
            free = [s for s in vocab.STAGES if not busy(mover["id"], "stage:" + s)]
            if not free:
                break
            fixes.append(f"prop '{mover['id']}' moved to stage {free[0]}")
            mover["stage"] = free[0]

    labels = []
    fact_ids = {f["id"] for f in (facts or {}).get("facts", [])}
    for lb in sb.get("labels", []):
        lb["word"] = clamp(lb.get("word", 0))
        lb["until_word"] = clamp(lb.get("until_word", lb["word"] + 6))
        if lb["until_word"] <= lb["word"]:
            lb["until_word"] = min(n - 1, lb["word"] + 6)
        pid, _, anchor = str(lb.get("anchor", "")).partition(".")
        if pid == "machine":
            lb["anchor"] = "machine." + (anchor if anchor in ("top", "center", "back", "door") else "top")
        elif pid not in parts:
            fixes.append(f"dropped label '{lb.get('text')}' (no part '{pid}')")
            continue
        elif not anchor or anchor not in _anchors(parts[pid]["type"]):
            lb["anchor"] = f"{pid}.center"
        if any(ch.isdigit() for ch in str(lb.get("text", ""))) and lb.get("fact_id") not in fact_ids:
            fixes.append(f"dropped label '{lb.get('text')}' (a number without a fact)")
            continue
        labels.append(lb)
    sb["labels"] = labels
    sb["sfx"] = [dict(x, word=clamp(x.get("word", 0))) for x in sb.get("sfx", []) if x.get("cue") in vocab.SFX]

    # shots: in order from word 0, framing what is on screen, never holding over MAX_HOLD
    span = layout.spans(sb, words, duration)
    shots = sorted([s for s in sb.get("shots", []) if isinstance(s.get("start_word"), (int, float))],
                   key=lambda s: s["start_word"])
    dedup = []
    for s in shots:
        s["start_word"] = clamp(s["start_word"])
        if s.get("frame") not in vocab.FRAMES:
            s["frame"] = {"wide": "machine", "medium": "area", "close": "part"}.get(s.get("frame"), "area")
        if s.get("move") not in vocab.MOVES:
            s["move"] = "hold"
        if dedup and s["start_word"] <= dedup[-1]["start_word"]:
            continue
        dedup.append(s)
    if not dedup:
        dedup = [{"start_word": 0, "frame": "machine", "on": [], "move": "hold"}]
    dedup[0]["start_word"] = 0
    # a close shot of a part starts just before that part arrives (not seconds early on an empty slot)
    first_in = {}
    for e in sorted(sb.get("events", []), key=lambda e: e.get("word", 0)):
        q = str(e.get("target", "")).split(".")[0]
        if e.get("do") == "appear" and q not in first_in:
            first_in[q] = e["word"]
    for i, s in enumerate(dedup[1:], 1):
        if s["frame"] in ("part", "area") and s.get("on") and all(q in first_in for q in s["on"]):
            w_in = min(first_in[q] for q in s["on"])
            late = words[w_in]["start"] - words[s["start_word"]]["start"]
            nxt = dedup[i + 1]["start_word"] if i + 1 < len(dedup) else n
            if late > 1.0:
                w = max(s["start_word"], next((k for k in range(w_in, -1, -1)
                                                if words[w_in]["start"] - words[k]["start"] >= 0.6), w_in))
                if dedup[i - 1]["start_word"] < w < nxt:
                    s["start_word"] = w
                    fixes.append(f"shot on {s['on']} now starts as it arrives (word {w})")
    # calm pacing: a shot shorter than MIN_HOLD goes (the one before simply holds on); a close shot of a part
    # that is arriving wins over the wider shot before it
    for _ in range(len(dedup)):
        ts = [words[s["start_word"]]["start"] for s in dedup] + [duration]
        short = [i for i in range(1, len(dedup)) if ts[i + 1] - ts[i] < MIN_HOLD]
        if not short:
            break
        i = short[0]
        if dedup[i]["frame"] == "part" and dedup[i - 1]["frame"] != "part" and i - 1 > 0:
            dedup[i]["start_word"] = dedup[i - 1]["start_word"]
            dedup.pop(i - 1)
        else:
            dedup.pop(i)
        fixes.append("merged a shot shorter than %.1f s" % MIN_HOLD)
    out = []
    for i, s in enumerate(dedup):
        t0 = words[s["start_word"]]["start"]
        t1 = words[dedup[i + 1]["start_word"]]["start"] if i + 1 < len(dedup) else duration
        mid = (t0 + t1) / 2
        on = [pid for pid in s.get("on", []) if pid in parts and span[pid][0] <= mid <= span[pid][1]]
        if s["frame"] == "prop":
            on = [pid for pid in on if not parts[pid].get("mount")]
        if not on and s["frame"] != "machine":
            visible = sorted((pid for pid in parts if span[pid][0] <= mid <= span[pid][1]),
                             key=lambda pid: -span[pid][0])
            on = visible[:1]
            if on:
                s["frame"] = "prop" if not parts[on[0]].get("mount") else ("part" if s["frame"] == "part" else "area")
                fixes.append(f"shot at word {s['start_word']} now frames {on} (on screen then)")
            else:
                s["frame"] = "machine"
        if s["frame"] in ("part", "prop"):
            on = on[:1]
        s["on"] = on
        out.append(s)
        while t1 - t0 > MAX_HOLD:                  # split long holds: alternate the framing
            w = next((k for k, x in enumerate(words) if x["start"] >= t0 + (t1 - t0) / 2), None)
            if w is None or w <= s["start_word"]:
                break
            nxt = {"machine": "area", "area": "machine", "part": "area", "prop": "machine"}[s["frame"]]
            t_end = t1
            mid2 = (words[w]["start"] + t_end) / 2
            on2 = [q for q in s["on"] if span[q][0] <= mid2 <= span[q][1]]
            if nxt == "area" and not on2:
                nxt = "machine"
            s2 = dict(s, start_word=w, frame=nxt, on=on2 if nxt != "machine" else [],
                      move="orbit" if s["move"] != "orbit" else "push_in")
            out.append(s2)
            fixes.append(f"split a {t1 - t0:.1f} s shot at word {w}")
            t0 = words[w]["start"]
            s = s2
    sb["shots"] = out
    return fixes
