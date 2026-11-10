"""
Hard checks on a storyboard before anything renders (pure Python). Every failure is a sentence the planner can
act on; the storyboard stage sends them back for a rewrite. `repair` first fixes in code what needs no judgement.
"""
from __future__ import annotations

from . import hosts, layout, vocab

MAX_HOLD = 6.2          # seconds a framing may hold
DEAD_AIR = 3.4          # seconds of a shot with nothing happening before the parts are lit up to fill it
ANALOGY_REACH = 12.0    # seconds after an analogy's last shot within which its part arrives
OFF_HOLD = 2.4          # seconds a motor switched off stays off before it restarts (so the stop is seen)
MAX_PROPS = 5           # analogy props in one film (one per analogy, the hook included)
MAX_PROP = 5.0          # seconds the same prop may hold the screen before the film moves on to the machine
MIN_HOLD = 3.0          # seconds a framing must hold: the viewer needs time to read what changed
MIN_OVERLAP = 0.4       # two parts sharing a spot for less than this (one leaving as the other lands) is fine
MACHINE_EVENTS = ("appear", "highlight", "shake", "wash", "heat_flow")
JET_PARTS = {"nozzle", "spray_can", "kettle", "cup", "fan_desk", "bottle", "balloon"}   # a port may spray
PATH_PARTS = {"coil", "radiator", "capillary"}      # parts with their own pipe path the dashes run along
COLD = {"hot_gas": "cold_gas", "hot_liquid": "cold_liquid", "steam": "cold_gas"}


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
        if e["do"] == "heat_flow":
            to = str(e.get("to") or "")
            if to.split(".")[0] not in parts and to not in vocab.HEAT_ENDS:
                errs.append(f"{what}: heat_flow 'to' must be a part id or 'room'")
        if pid == "machine":
            if e["do"] not in MACHINE_EVENTS:
                errs.append(f"{what}: the machine itself can only {', '.join(MACHINE_EVENTS)}")
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
        if t1 - t0 > MAX_HOLD + 0.6:              # repair splits from MAX_HOLD; a long pause may leave no word to cut at
            errs.append(f"shot {i + 1} holds {t1 - t0:.1f} s: change the framing at least every {MAX_HOLD:.0f} s")
        if i and t1 - t0 < MIN_HOLD - 0.01:
            errs.append(f"shot {i + 1} lasts only {t1 - t0:.1f} s: hold every shot at least {MIN_HOLD:.1f} s")
    for i in range(1, len(shots)):
        a, b = shots[i - 1], shots[i]
        same = sorted(a.get("on") or []) == sorted(b.get("on") or []) and a.get("move") == b.get("move")
        if a.get("frame") == b.get("frame") != "machine" and same:
            errs.append(f"shots {i} and {i + 1} frame {b.get('on')} the same way: give shot {i + 1} another framing "
                        "(machine, area or part) so the picture moves on with the story")
    controls = [pid for pid, p in parts.items() if p["type"] == "thermostat"]
    movers = [pid for pid, p in parts.items() if p.get("mount") and p["type"] in ("compressor", "motor", "pump", "fan")]
    if controls and movers and not any(e.get("do") == "run" and str(e.get("target", "")).split(".")[0] in movers
                                        and (e.get("speed") == "stop" or e.get("on") is False)
                                        for e in sb.get("events", [])):
        errs.append(f"the thermostat never switches {movers[0]} off: add a run event with speed stop on {movers[0]} "
                    "at the word that says it stops, and a run event (speed normal) where it starts again")
    props = [pid for pid, p in parts.items() if not p.get("mount") and not str(pid).endswith(("_2", "_3"))]
    if len(props) > MAX_PROPS:
        errs.append(f"{len(props)} props ({props}): use at most {MAX_PROPS}, one per analogy (plus the hook); "
                    "drop the extras")
    appeared = {str(e.get("target")).split(".")[0] for e in sb.get("events", []) if e.get("do") == "appear"}
    present = [pid for pid, p in parts.items() if p.get("mount") and pid not in appeared]
    if len(present) > 1:
        errs.append(f"{present} are mounted from the first frame: build the machine up, part by part "
                    "(give each an 'appear' event on the word that introduces it)")
    return errs


# ------------------------------------------------------------ deterministic repairs

_GROUP = lambda s: s.split("_")[0]          # noqa: E731  inside_top -> inside


def loop_order(sb: dict, parts: dict) -> list[str]:
    """The machine's parts in flow order around its loop of pipes (empty if there is no loop)."""
    nxt = {}
    for c in sb.get("connections", []):
        if c.get("kind") in ("pipe", "hose"):
            a, b = (str(c.get(k, "")).split(".")[0] for k in ("from", "to"))
            if a in parts and b in parts:
                nxt.setdefault(a, b)
    if not nxt:
        return []
    start = next((q for q in nxt if str(parts[q].get("mount") or "").startswith("inside")), next(iter(nxt)))
    out, q = [], start
    while q in nxt and q not in out:
        out.append(q)
        q = nxt[q]
    return out if len(out) >= 3 else []


def refrigerant_cycle(sb: dict, parts: dict) -> dict:
    """{connection id: flow kind} of a cooling machine's loop, from what each pipe joins: into the cold coil
    cold liquid, out of it cold gas, out of the compressor hot gas, out of the hot coil warm liquid."""
    out = {}
    for c in sb.get("connections", []):
        a, b = (parts.get(str(c.get(k, "")).split(".")[0]) for k in ("from", "to"))
        if not a or not b or c.get("kind") not in ("pipe", "hose"):
            continue
        a_in = str(a.get("mount") or "").startswith("inside")
        b_in = str(b.get("mount") or "").startswith("inside")
        if b["type"] == "compressor":
            out[c["id"]] = "cold_gas"
        elif a["type"] == "compressor":
            out[c["id"]] = "hot_gas"
        elif b["type"] in ("coil", "radiator") and b_in:
            out[c["id"]] = "cold_liquid"
        elif a["type"] in ("coil", "radiator") and not a_in:
            out[c["id"]] = "hot_liquid"
    return out


# what a prop DOES when it is on screen (its analogy in action): (event, extra fields, words after its shot starts)
PROP_ACTION = {
    "spray_can": [("flow", {"target": "{p}.nozzle", "kind": "cold_gas", "on": True}, 0),
                  ("frost", {"target": "{p}", "value": 0.85}, 1)],
    "pump": [("run", {"target": "{p}", "speed": "fast", "driver": "stroke"}, 0), ("heat", {"target": "{p}", "value": 0.45}, 3)],
    "cup": [("heat_flow", {"target": "{p}", "to": "room", "on": True}, 0)],
    "kettle": [("flow", {"target": "{p}.spout", "kind": "steam", "on": True}, 0)],
    "fan_desk": [("run", {"target": "{p}", "speed": "fast", "driver": "spin"}, 0),
                 ("flow", {"target": "{p}.front", "kind": "air", "on": True}, 1)],
    "bicycle_wheel": [("run", {"target": "{p}", "speed": "normal", "driver": "spin"}, 0)],
    "balloon": [("set", {"target": "{p}", "value": 1.0, "driver": "inflate"}, 0)],
    "candle": [("heat_flow", {"target": "{p}.flame", "to": "room", "on": True}, 0)],
    "matchbox": [("heat_flow", {"target": "{p}.flame", "to": "room", "on": True}, 0)],
    "ice_cube": [("frost", {"target": "{p}", "value": 0.8}, 0)],
    "bulb": [("heat", {"target": "{p}", "value": 0.5}, 0)],
}
ACTS = {"run", "set", "flow", "frost", "heat", "heat_flow", "fill", "shake", "flash", "spark", "smoke"}


def _complete(sb, shots, parts, words, duration, host, fixes, hook_type=None):
    """What a planner forgets and a viewer misses, filled in by code: the hook prop opens the film doing its trick;
    every prop acts in its shot; a part's first close shot shows it working (frost on the cold coil and heat
    flowing into it, heat leaving the hot coil, the motor running); every pipe of the loop carries its flow once
    both its ends are in."""
    n = len(words)
    evs = sb["events"]

    def tw(i):
        return words[max(0, min(int(i), n - 1))]["start"]

    def ends(i):
        return shots[i + 1]["start_word"] if i + 1 < len(shots) else n

    def act(p, w0, w1):
        out = 0
        for do, kw, dw in PROP_ACTION.get(parts[p]["type"], []):
            w = min(w1 - 1, w0 + dw) if w1 > w0 else w0
            e = {"word": max(0, w), "do": do, **{k: (v.format(p=p) if isinstance(v, str) else v) for k, v in kw.items()}}
            pid, _, anc = e["target"].partition(".")
            if anc and anc not in _anchors(parts[p]["type"]):
                e["target"] = pid
            evs.append(e)
            out += 1
        return out
    # the hook: shot 1 is the script's hook object (a prop) doing its trick within the first words
    if hook_type in vocab.PARTS and shots:
        first_in = {}
        for e in sorted(evs, key=lambda e: e["word"]):
            if e.get("do") == "appear" and e.get("target") in parts:
                first_in.setdefault(e["target"], e["word"])
        hook = next((q for q, p in parts.items() if p["type"] == hook_type and not p.get("mount")
                     and first_in.get(q, 0) <= 1), None)
        if hook is None:                           # the storyboard forgot it (or brings it in later): its own copy
            hook = "hook_" + hook_type
            if hook not in parts:
                spec = {"id": hook, "type": hook_type, "size": "large", "color": None, "mount": None, "stage": "front"}
                sb["parts"].append(spec)
                parts[hook] = spec
            evs.append({"word": 0, "do": "appear", "target": hook, "how": "pop"})
            if len(shots) > 1:                     # it leaves with its shot (the story's own one may come later)
                evs.append({"word": shots[1]["start_word"], "do": "remove", "target": hook, "how": "shrink"})
            fixes.append(f"the film opens on the hook object '{hook_type}'")
        if shots[0]["frame"] != "prop" or shots[0].get("on") != [hook]:
            shots[0].update(frame="prop", on=[hook], move="push_in")
            fixes.append(f"shot 1 is the hook '{hook}'")
    # every prop acts in its shot
    for i, s in enumerate(shots):
        if s["frame"] != "prop" or not s.get("on"):
            continue
        p = s["on"][0]
        w0, w1 = s["start_word"], ends(i)
        if p in parts and not any(str(e.get("target", "")).split(".")[0] == p and e.get("do") in ACTS
                                  and w0 - 1 <= e["word"] < w1 for e in evs):
            k = act(p, w0 + (1 if i else 0), w1)
            if k:
                fixes.append(f"prop '{p}' shows its trick in its shot (word {w0})")
    # a part's first close / area shot shows it working (cooling machines: the known roles of each part)
    if host in hosts.COOLING:
        done = set()
        for i, s in enumerate(shots):
            if s["frame"] not in ("part", "area"):
                continue
            w0, w1 = s["start_word"], ends(i)
            for q in s.get("on", []):
                if q not in parts or not parts[q].get("mount") or q in done:
                    continue
                done.add(q)
                if any(str(e.get("target", "")).split(".")[0] == q and e.get("do") in ACTS for e in evs
                       if e["word"] < w1):
                    continue
                w = min(w1 - 1, w0 + 2)
                t, inside = parts[q]["type"], str(parts[q].get("mount") or "").startswith("inside")
                if t in ("coil", "radiator") and inside:
                    evs += [{"word": w, "do": "frost", "target": q, "value": 0.7},
                            {"word": w, "do": "heat_flow", "target": "machine.food", "to": q, "on": True}]
                elif t in ("coil", "radiator"):
                    evs += [{"word": w, "do": "heat", "target": q, "value": 0.4},
                            {"word": w, "do": "heat_flow", "target": q, "to": "room", "on": True}]
                elif t in ("compressor", "motor", "pump", "fan"):
                    evs.append({"word": w, "do": "run", "target": q, "speed": "normal"})
                elif t in ("capillary", "nozzle", "valve"):
                    evs.append({"word": w, "do": "frost", "target": q, "value": 0.5})    # the pressure drop chills it
                else:
                    continue
                fixes.append(f"'{q}' is shown working in its first shot (word {w})")
    # a cooling machine's coils carry their state change (liquid -> gas in the cold one, gas -> liquid in the hot
    # one) from the first time they are seen
    if host in hosts.COOLING:
        for q, p in parts.items():
            flowing = any(e.get("do") == "flow" and e.get("target") == q for e in evs)
            if p["type"] not in ("coil", "radiator") or not p.get("mount") or flowing:
                continue
            first_shot = next((s["start_word"] for s in shots if q in (s.get("on") or [])), None)
            if first_shot is None:
                continue
            inside = str(p.get("mount")).startswith("inside")
            evs.append({"word": min(n - 1, first_shot + 2), "do": "flow", "target": q, "on": True,
                        "kind": "cold_liquid" if inside else "hot_gas", "kind_out": "cold_gas" if inside else "hot_liquid"})
            fixes.append(f"coil '{q}' shows its state change")
    # the finale: the last whole-machine shot tours the loop -- each part of the cycle lights up in flow order,
    # so the closed loop is SEEN at the end (and the ending is not an idle hold)
    order = loop_order(sb, parts)
    last = next((i for i in range(len(shots) - 1, -1, -1) if shots[i]["frame"] == "machine"), None)
    if order and last is not None:
        w0, w1 = shots[last]["start_word"], ends(last)
        if not any(e.get("do") == "highlight" and e.get("tour") and w0 <= e["word"] < w1 for e in evs):
            sb["events"] = evs = [e for e in evs if not (e.get("do") == "highlight" and w0 <= e["word"] < w1)]
            t0_, t1_ = tw(w0) + 0.6, (tw(w1) if w1 < n else duration) - 0.6
            for j, q in enumerate(order):
                tj = t0_ + j * max(0.0, t1_ - t0_) / len(order)
                wj = next((k for k in range(w0, w1) if tw(k) >= tj), w0)
                evs.append({"word": wj, "do": "highlight", "target": q, "on": True, "tour": True})
            fixes.append(f"the finale tours the loop: {order}")
    # every pipe of the loop carries its flow once both its ends are in
    cycle = refrigerant_cycle(sb, parts) if host in hosts.COOLING else {}
    first = {}
    for e in sorted(evs, key=lambda e: e["word"]):
        if e.get("do") == "appear" and e.get("target") not in first:
            first[e.get("target")] = e["word"]
    for c in sb.get("connections", []):
        if c["id"] not in cycle or any(e.get("do") == "flow" and e.get("target") == c["id"] for e in evs):
            continue
        a, b_ = (str(c[k]).split(".")[0] for k in ("from", "to"))
        w = max(first.get(a, 0), first.get(b_, 0))
        w = next((k for k in range(w, n) if tw(k) >= tw(w) + 1.6), n - 1)
        evs.append({"word": w, "do": "flow", "target": c["id"], "kind": cycle[c["id"]], "on": True})
        fixes.append(f"pipe '{c['id']}' carries its {cycle[c['id']]} from word {w}")


def repair(sb: dict, words: list[dict], duration: float, facts: dict | None = None, hook: str | None = None
           ) -> list[str]:
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
    for p in sb["parts"]:
        if p["type"] == "thermostat" and m["host"] in hosts.COOLING and p.get("mount") == "front":
            p["mount"] = "inside_middle"            # inside, by the cold it senses (not on a blank closed door)
            fixes.append(f"'{p['id']}' mounts inside the {m['host']}")
        if p["type"] == "nozzle" and "capill" in p["id"].lower():
            p["type"] = "capillary"
            fixes.append(f"'{p['id']}' is a capillary tube, not a brass nozzle")
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

    cycle = refrigerant_cycle(sb, parts)
    kept = []
    for e in sb.get("events", []):
        e["word"] = clamp(e.get("word", 0))
        pid, _, anchor = str(e.get("target", "")).partition(".")
        if e.get("do") == "flow" and e.get("kind") == "heat":       # heat is not a fluid in a pipe: it MOVES
            src = parts.get(pid)
            if pid in conn_ids or src is None:
                fixes.append(f"dropped a heat 'flow' on '{pid}' (heat moves with heat_flow)")
                continue
            if src.get("mount") and str(src["mount"]).startswith("inside") and m["host"] in hosts.COOLING:
                e.update(do="heat_flow", target="machine.food", to=pid)
            else:
                e.update(do="heat_flow", target=pid, to="room")
            e.pop("kind", None)
            fixes.append(f"heat flow on '{pid}' became heat moving {e['target']} -> {e['to']}")
        if e.get("do") == "heat_flow":
            to = str(e.get("to") or "room")
            e["to"] = to if (to.split(".")[0] in parts or to in vocab.HEAT_ENDS) else "room"
        if pid == "machine":
            if e.get("do") in MACHINE_EVENTS:
                if e.get("do") == "heat_flow" and anchor not in ("food", "inside", "center"):
                    e["target"] = "machine.food"
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
        own_path = pid in parts and (not parts[pid].get("mount") or parts[pid]["type"] in JET_PARTS
                                     or (not anchor and parts[pid]["type"] in PATH_PARTS))
        if e.get("do") == "flow" and pid in parts and not own_path:
            # a machine part does not spray into the air: what leaves it goes down the pipe there
            cs = sb.get("connections", [])
            pipe = next((c["id"] for c in cs if anchor and f"{pid}.{anchor}" in (c.get("from"), c.get("to"))), None)
            pipe = pipe or next((c["id"] for c in cs if str(c.get("from", "")).split(".")[0] == pid), None)
            if pipe is None:
                fixes.append(f"dropped a jet out of '{e.get('target')}' (a machine part does not spray)")
                continue
            fixes.append(f"the jet out of '{e.get('target')}' now flows down '{pipe}'")
            e["target"] = pipe
        if e.get("do") == "flow" and pid in conn_ids and m["host"] in hosts.COOLING and cycle.get(pid):
            if e.get("kind") != cycle[pid] and e.get("on") is not False:
                e["kind"] = cycle[pid]                  # the real refrigeration cycle, whatever was written
        coil = pid in parts and parts[pid]["type"] in ("coil", "radiator")
        if e.get("do") == "flow" and coil and m["host"] in hosts.COOLING and not anchor and e.get("on") is not False:
            # the state change happens IN the coil: liquid boils to gas in the cold one, gas condenses in the hot one
            if str(parts[pid].get("mount") or "").startswith("inside"):
                e["kind"], e["kind_out"] = "cold_liquid", "cold_gas"
            else:
                e["kind"], e["kind_out"] = "hot_gas", "hot_liquid"
        inside = str(parts[pid].get("mount") or "").startswith("inside") if pid in parts else False
        if e.get("do") == "flow" and inside and m["host"] in hosts.COOLING and e.get("kind") in COLD:
            e["kind"] = COLD[e["kind"]]                 # the coil inside a fridge is the cold one
            fixes.append(f"'{pid}' inside the {m['host']} carries cold {e['kind']}")
        if e.get("do") == "appear" and e.get("from") and (e["from"] not in parts or e["from"] == pid):
            e["from"] = None
        kept.append(e)
    sb["events"] = kept
    # props leave once their moment is over (they stood around and photobombed the machine shots): a prop with
    # no exit and nothing flying out of it fades at the first shot after the last one that shows it
    shots_ = sorted(sb.get("shots", []), key=lambda s: s.get("start_word", 0))
    for p in sb["parts"]:
        if p.get("mount") or p["id"] in {e.get("from") for e in kept if e.get("do") == "appear"}:
            continue
        if any(e.get("do") == "remove" and str(e.get("target", "")).split(".")[0] == p["id"] for e in kept):
            continue
        last = max([e["word"] for e in kept if str(e.get("target", "")).split(".")[0] == p["id"]] +
                   [s["start_word"] for s in shots_ if p["id"] in (s.get("on") or [])] + [0])
        nxt = next((s["start_word"] for s in shots_ if s["start_word"] > last and p["id"] not in (s.get("on") or [])),
                   None)
        if nxt is not None:
            kept.append({"word": nxt, "do": "remove", "target": p["id"], "how": "shrink"})
            fixes.append(f"prop '{p['id']}' leaves at word {nxt}")
    # props that can move DO move while they are on screen (a pump pumps, a fan spins): the analogy acts
    for p in sb["parts"]:
        drv = vocab.PARTS[p["type"]][3]
        if p.get("mount") or not drv or any(str(e.get("target", "")).split(".")[0] == p["id"] and
                                             e.get("do") in ("run", "set") for e in kept):
            continue
        app = next((e for e in kept if e.get("do") == "appear" and e.get("target") == p["id"]), None)
        w = min(n - 1, (app["word"] if app else 0) + 2)
        kept.append({"word": w, "do": "run", "target": p["id"], "speed": "normal", "driver": drv[0]})
        fixes.append(f"prop '{p['id']}' now runs ({drv[0]}) while on screen")

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
    # a pill that names a flow state points at the pipe outlet where that state leaves (not at a part's body)
    states = [("HOT GAS", "hot_gas"), ("COLD GAS", "cold_gas"), ("WARM LIQUID", "hot_liquid"),
              ("HOT LIQUID", "hot_liquid"), ("COLD LIQUID", "cold_liquid"), ("ICY LIQUID", "cold_liquid")]
    by_kind = {}
    for c in sb.get("connections", []):
        if cycle.get(c["id"]):
            by_kind.setdefault(cycle[c["id"]], c["from"])
    flow_at = {}
    for e in sorted(sb.get("events", []), key=lambda e: e.get("word", 0)):
        if e.get("do") == "flow" and e.get("on") is not False and e.get("target") in cycle:
            flow_at.setdefault(e["target"], e["word"])
    for lb in sb.get("labels", []):
        kind = next((k for t, k in states if t in str(lb.get("text", "")).upper()), None)
        if kind in by_kind and lb.get("anchor") != by_kind[kind]:
            lb["anchor"] = by_kind[kind]
            fixes.append(f"pill '{lb['text']}' now points at the pipe that carries it")
        pipe = next((c["id"] for c in sb.get("connections", []) if cycle.get(c["id"]) == kind), None)
        if pipe in flow_at and lb.get("word", 0) < flow_at[pipe]:
            span_ = lb.get("until_word", lb["word"] + 5) - lb["word"]
            lb["word"], lb["until_word"] = flow_at[pipe], min(n - 1, flow_at[pipe] + max(4, span_))
            fixes.append(f"pill '{lb['text']}' waits for its flow (word {lb['word']})")
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
    # two shots in a row on the same subject: one shot if that is short enough; a prop that would hold the screen
    # longer than MAX_PROP hands over to the machine; else the second shot moves the camera differently
    for _ in range(2 * len(dedup)):
        ts = [words[s["start_word"]]["start"] for s in dedup] + [duration]

        def todo(i):
            a_, b_ = dedup[i - 1], dedup[i]
            if a_["frame"] == b_["frame"] == "machine":
                # the same home view twice in a row reads as one long idle hold
                return "merge" if ts[i + 1] - ts[i - 1] <= MAX_HOLD else "reframe"
            near = {"part", "area"}
            overlap = a_["frame"] in near and b_["frame"] in near and set(a_.get("on") or []) & set(b_.get("on") or [])
            if overlap and not (a_["frame"] == b_["frame"] and sorted(a_.get("on") or []) == sorted(b_.get("on") or [])):
                # a close shot then another close shot of the same part reads as one long hold
                return "merge" if ts[i + 1] - ts[i - 1] <= MAX_HOLD else "machine"
            if not (a_["frame"] == b_["frame"] != "machine" and sorted(a_.get("on") or []) == sorted(b_.get("on") or [])):
                return None
            if ts[i + 1] - ts[i - 1] <= MAX_HOLD and a_.get("move") == b_.get("move"):
                return "merge"
            if b_["frame"] == "prop" and ts[i + 1] - ts[i - 1] > MAX_PROP:
                return "machine"
            return "move" if a_.get("move") == b_.get("move") else None
        acts = [(i, todo(i)) for i in range(1, len(dedup))]
        acts = [(i, x) for i, x in acts if x]
        if not acts:
            break
        i, act = acts[0]
        if act == "merge":
            dedup.pop(i)
            fixes.append("merged two shots on the same subject")
        elif act == "reframe":                    # the second one frames the parts that act during it
            if i == len(dedup) - 1 and i > 1:     # ... unless it is the finale: then the one before it does
                i -= 1
            w0_ = dedup[i]["start_word"]
            w1_ = dedup[i + 1]["start_word"] if i + 1 < len(dedup) else n
            busy_ = [str(e.get("target", "")).split(".")[0] for e in sb.get("events", []) if w0_ <= e.get("word", 0) < w1_]
            prev_on = set(dedup[i - 1].get("on") or []) | set(dedup[i + 1].get("on") or [] if i + 1 < len(dedup) else [])
            busy_ = [q for q in dict.fromkeys(busy_) if q in parts and parts[q].get("mount") and q not in prev_on]
            if not busy_:
                busy_ = [q for q, _w in sorted(first_in.items(), key=lambda x: -x[1])
                         if q in parts and parts[q].get("mount") and _w <= w0_ and q not in prev_on][:1]
            if busy_:
                dedup[i].update(frame="area", on=busy_[:2], move="orbit")
                fixes.append(f"the second whole-machine shot in a row (word {w0_}) now frames {busy_[:2]}")
            else:
                dedup[i]["move"] = "orbit" if dedup[i - 1].get("move") != "orbit" else "pull_back"
        elif act == "machine":
            dedup[i].update(frame="machine", on=[], move="push_in")      # a prop / a part does not hold the screen
            fixes.append(f"the shot at word {dedup[i]['start_word']} moves on to the whole machine")
        else:
            dedup[i]["move"] = next(m for m in ("pull_back", "orbit", "push_in", "hold") if m != dedup[i - 1].get("move"))
            fixes.append(f"the shot at word {dedup[i]['start_word']} moves the camera differently")
    # a prop no shot ever frames is clutter: it goes, with its events
    filmed = {q for s in dedup for q in (s.get("on") or [])}
    ghosts = [p["id"] for p in sb["parts"] if not p.get("mount") and p["id"] not in filmed
              and p["id"] not in {e.get("from") for e in sb.get("events", [])}]
    if ghosts:
        sb["parts"] = [p for p in sb["parts"] if p["id"] not in ghosts]
        sb["events"] = [e for e in sb["events"] if str(e.get("target", "")).split(".")[0] not in ghosts]
        for g in ghosts:
            parts.pop(g, None)
        fixes.append(f"dropped props no shot shows: {ghosts}")
    # every analogy prop turns into the part it explains: the first mounted part to arrive after the prop's last
    # shot (within ANALOGY_REACH s) flies out of it, unless the storyboard already says where it comes from
    used = {e.get("from") for e in sb.get("events", []) if e.get("do") == "appear" and e.get("from")}
    for p in sb["parts"]:
        if p.get("mount") or p["id"] in used:
            continue
        mine = [k for k, s in enumerate(dedup) if p["id"] in (s.get("on") or [])]
        if not mine:
            continue
        w_end = dedup[mine[-1] + 1]["start_word"] if mine[-1] + 1 < len(dedup) else n - 1
        t_end = words[min(w_end, n - 1)]["start"]
        nxt = next((e for e in sorted(sb.get("events", []), key=lambda e: e["word"])
                    if e.get("do") == "appear" and not e.get("from") and e.get("target") in parts
                    and parts[e["target"]].get("mount") and words[e["word"]]["start"] >= t_end - 2.0
                    and words[e["word"]]["start"] - t_end <= ANALOGY_REACH), None)
        if nxt is not None:
            nxt["from"] = p["id"]
            used.add(p["id"])
            fixes.append(f"'{nxt['target']}' now flies out of its analogy '{p['id']}'")
    # a prop that turns into its part stays until it does: an earlier exit would leave the part flying out of
    # thin air (the flight itself makes the prop vanish)
    fly_at = {e["from"]: e["word"] for e in sb.get("events", []) if e.get("do") == "appear" and e.get("from")}
    keep = [e for e in sb.get("events", []) if not (e.get("do") == "remove" and e.get("target") in fly_at
                                                     and e["word"] <= fly_at[e["target"]] + 2)]
    if len(keep) < len(sb.get("events", [])):
        fixes.append("a prop that becomes a part no longer leaves before it does")
        sb["events"] = keep
    # an analogy turning into its part (appear from a prop) is filmed whole: the shot it happens in frames the
    # prop and the part's slot together, and starts early enough to see the prop before the part leaves it
    flies = [(e["word"], e["target"], e["from"]) for e in sb.get("events", [])
             if e.get("do") == "appear" and e.get("from") in parts and e.get("target") in parts]
    for w, part, prop in flies:
        i = max((k for k, s in enumerate(dedup) if s["start_word"] <= w), default=0)
        if i == 0:                                 # the hook shot stays on the hook prop
            continue
        s = dedup[i]
        if i and words[w]["start"] - words[s["start_word"]]["start"] < 0.9:
            k = next((k for k in range(w, -1, -1) if words[w]["start"] - words[k]["start"] >= 0.9), 0)
            if words[k]["start"] - words[dedup[i - 1]["start_word"]]["start"] >= MIN_HOLD:
                s["start_word"] = k
        s.update(frame="area", on=[part, prop], fly=True)
        fixes.append(f"the shot at word {s['start_word']} films '{part}' flying out of '{prop}'")
    out = []
    for i, s in enumerate(dedup):
        t0 = words[s["start_word"]]["start"]
        t1 = words[dedup[i + 1]["start_word"]]["start"] if i + 1 < len(dedup) else duration
        mid = (t0 + t1) / 2
        on = [pid for pid in s.get("on", []) if pid in parts and span[pid][0] <= mid <= span[pid][1]]
        if s.pop("fly", False):
            on = list(s["on"])
        elif s["frame"] == "prop":
            on = [pid for pid in on if not parts[pid].get("mount")]
        else:                                      # props are only on screen in their own shots
            on = [pid for pid in on if parts[pid].get("mount")]
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
        while t1 - t0 > MAX_HOLD:                  # split long holds (MAX_HOLD >= 2 * MIN_HOLD: always possible)
            # the cut nearest the middle that leaves both halves at least MIN_HOLD long
            ok = [k for k, x in enumerate(words) if t0 + MIN_HOLD + 0.02 <= x["start"] <= t1 - MIN_HOLD - 0.02]
            w = min(ok, key=lambda k: abs(words[k]["start"] - (t0 + t1) / 2), default=None)
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
    # the machine is there for the first shot that frames it (no empty-studio shot waiting for it)
    m_in = next((e for e in sb["events"] if e.get("do") == "appear" and e.get("target") == "machine"), None)
    first_m = next((s["start_word"] for s in out if s["frame"] in ("machine", "area", "part")), None)
    if m_in is not None and first_m is not None and m_in["word"] > first_m:
        fixes.append(f"the machine now appears at word {first_m}, with the first shot that frames it")
        m_in["word"] = first_m
    # the thermostat's click is SEEN: the motor stays off long enough to watch it stop (OFF_HOLD s), and a pill on
    # it says OFF when it stops and ON when it starts again
    movers = [q for q, p in parts.items() if p.get("mount") and p["type"] in ("compressor", "motor", "pump", "fan")]
    runs_ = sorted((e for e in sb["events"] if e.get("do") == "run" and str(e.get("target", "")).split(".")[0] in movers),
                   key=lambda e: e["word"])
    for a_, b_ in zip(runs_, runs_[1:]):
        off_ = a_.get("speed") == "stop" or a_.get("on") is False
        on_ = not (b_.get("speed") == "stop" or b_.get("on") is False)
        if off_ and on_ and words[b_["word"]]["start"] - words[a_["word"]]["start"] < OFF_HOLD:
            w = next((k for k in range(a_["word"], -1, -1)
                      if words[b_["word"]]["start"] - words[k]["start"] >= OFF_HOLD), 0)
            prev = max([e["word"] for e in runs_ if e["word"] < a_["word"]] + [0])
            if w > prev:
                fixes.append(f"the motor now stops at word {w} (was {a_['word']}): off long enough to see")
                a_["word"] = w
    if any(p["type"] == "thermostat" for p in parts.values()) and movers:
        stops = sorted((e["word"], e.get("speed") == "stop" or e.get("on") is False) for e in sb["events"]
                       if e.get("do") == "run" and str(e.get("target", "")).split(".")[0] in movers)
        seen_off = False
        mine = [lb for lb in sb.get("labels", []) if lb.get("text") in ("COMPRESSOR OFF", "COMPRESSOR ON")]
        sb["labels"] = [lb for lb in sb.get("labels", []) if lb not in mine]        # rebuilt from the events
        for k, (w, off) in enumerate(stops):
            if not off and not seen_off:
                continue                         # the first start is the machine starting, not a click
            seen_off = seen_off or off
            if any(abs(lb["word"] - w) <= 1 for lb in sb.get("labels", []) if lb.get("text") not in
                   ("COMPRESSOR OFF", "COMPRESSOR ON")):
                continue
            nxt = next((x for x, _o in stops[k + 1:] if x > w), None)
            until = min(n - 1, w + 5) if nxt is None else max(w + 1, min(nxt, w + 5))
            sb.setdefault("labels", []).append({"word": w, "until_word": until,
                                                "text": "COMPRESSOR OFF" if off else "COMPRESSOR ON",
                                                "variant": "cold" if off else "done", "anchor": f"{movers[0]}.center",
                                                "fact_id": None})
            fixes.append(f"a {'COMPRESSOR OFF' if off else 'COMPRESSOR ON'} pill at word {w}")
    _complete(sb, out, parts, words, duration, m["host"], fixes, hook)
    # dead air: a stretch of a machine / area / part shot longer than DEAD_AIR with nothing happening; the parts
    # on screen light up in turn to fill it (the shot's own parts first)
    span = layout.spans(sb, words, duration)
    for i, s in enumerate(out):
        if s["frame"] == "prop":
            continue
        w1 = out[i + 1]["start_word"] if i + 1 < len(out) else n
        t0, t1 = words[s["start_word"]]["start"], (words[w1]["start"] if w1 < n else duration)
        shown = [q for q in s.get("on", []) if q in parts and parts[q].get("mount")]
        shown += sorted((q for q, p in parts.items() if p.get("mount") and q not in shown and span[q][0] <= t0 + 0.3
                         and span[q][1] >= t1), key=lambda q: span[q][0])
        if not shown:
            continue
        ts = sorted([t0] + [words[e["word"]]["start"] for e in sb["events"] if s["start_word"] <= e["word"] < w1] + [t1])
        k = 0
        for a_, b_ in zip(ts, ts[1:]):
            tj = a_ + 1.2
            while b_ - a_ > DEAD_AIR and tj < b_ - 1.0:
                wj = next((x for x in range(s["start_word"], w1) if words[x]["start"] >= tj), None)
                if wj is None:
                    break
                sb["events"].append({"word": wj, "do": "highlight", "target": shown[k % len(shown)], "on": True})
                k += 1
                a_, tj = words[wj]["start"], words[wj]["start"] + 2.6
        if k:
            fixes.append(f"the shot at word {s['start_word']} had dead air: {k} highlight(s) fill it")
    return fixes
