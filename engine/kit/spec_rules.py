"""Generic story-spec rules for kit sets (pure python): every generated spec gets the same functions."""


def make_rules(actions: dict, story_order: list):
    """(beat_actions, min_seconds, validate) for a spec with these ACTIONS and STORY_ORDER."""

    def beat_actions(beat: dict) -> list:
        return list(beat.get("actions") or [beat.get("action")])

    def min_seconds(beat: dict) -> float:
        return sum(actions.get(a, {}).get("seconds", (0, 0))[0] for a in beat_actions(beat))

    def validate(beats: list) -> list:
        errs = []
        for k, b in enumerate(beats):
            acts_k = beat_actions(b)
            if len(acts_k) != 1:
                errs.append(f"beat {k + 1} has {len(acts_k)} actions; every kit beat plays exactly one")
        acts = [a for b in beats for a in beat_actions(b)]
        unknown = [a for a in acts if a not in actions]
        if unknown:
            errs.append(f"unknown actions: {unknown}")
        hooks = [a for a in acts if actions.get(a, {}).get("kind") == "hook"]
        if not acts or actions.get(acts[0], {}).get("kind") != "hook":
            errs.append(f"beat 1 must be a hook action ({', '.join(k for k, v in actions.items() if v['kind'] == 'hook')})")
        if len(hooks) != 1:
            errs.append(f"exactly one hook action is allowed (got {hooks})")
        if len(acts) < 2 or acts[1] != "rewind":
            errs.append("beat 2 must be 'rewind'")
        story = [a for a in acts if actions.get(a, {}).get("kind") in ("story", "fail", "fix")]
        if story != list(story_order):
            errs.append(f"story actions must appear exactly once each, in order: {list(story_order)} (got {story})")
        if len(set(acts)) != len(acts):
            errs.append("each action may be used once")
        return errs

    return beat_actions, min_seconds, validate
