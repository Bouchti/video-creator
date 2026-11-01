# Retention fixes, 2026-11-01

Why: the Untold Footnotes audit (7 Shorts, Oct 24-31, 20-490 views each) found the films lost viewers
in the first test audience. The measured causes and what changed:

| Problem (measured) | Change | Where |
|---|---|---|
| Narration ~19% silence (11-14 s of a 60 s track), read at ~2.2 words/s vs ~3.75 for the 24M-view Short on the same story | Per-sentence pauses cut to 0.10-0.35 s (were 0.30-0.60), `PAUSE_SCALE` env to tune them all; Chatterbox sentence edges trimmed to 60 ms of air; `VOICE_SPEED` default 1.0 (was 0.92) for every voice; `CHATTERBOX_SENTENCE_PAUSE` default 0.12 (was 0.4) | `agents/voice.py`, `agents/chatterbox_worker.py`, `.env.example` |
| Films ran 61-81 s with ~2.2 words/s of story | Default length 62 s (`VIDEO_DURATION` in `.env`): it must stay over one minute for TikTok Creator Rewards, so the length is kept and filled with story at ~3 words/s instead of pauses | `main.py` |
| Word budget assumed the slow read | `WORDS_PER_SECOND` 3.0 (was 2.1): 40 s = 13 beats, 102-138 words | `agents/script.py` |
| Fragment runs ("Painters. Sculptors. Designers."), dates up front ("October 18th, 1925 near Petrich."), hook debunked at 5 s ("The bucket probably didn't start the war.") | Writer rules: SPOKEN AND FAST, CONTEXT BUDGET, KEEP THE GAP OPEN; and a free code check, `pacing_feedback`, that sends such drafts back before the paid evaluation | `agents/script.py`, `agents/evaluator.py` |
| Five of seven topics were "dumbest wars" staples with existing 9K-24M view Shorts | Topic picker rejects those staples and prefers stories with no known Short | `agents/leader.py` |
| Kettle War post said the empire paid 8.5M guilders (the Dutch Republic paid); `#shorts` in titles; emoji "What you'll learn" lists; cover frames chosen for caption words | Post rules: one title pattern without hashtags, plain 2-sentence description + sources + question, cover frame that shows the subject; every number in a caption not found in the script or sources is listed under CHECK BEFORE POSTING in the `_post.txt` | `agents/post_text.py` |

Tests: `tests/test_retention_fixes.py` (new); `tests/test_beats.py` and `tests/test_pipeline_helpers.py`
updated for the new word rate. Pre-change copies of every edited file: `backup_before_retention_fix_20261101/`
(git-ignored).

Not changed yet: the visual style (generic AI stills). Next candidate: a recurring visual signature
(map opener, archival photos mixed in) so the channel is recognisable in the first frame.

How to judge it: compare YouTube Studio "Viewed vs. swiped away" and average percentage viewed for the
next 5-10 uploads against the Oct 24-31 Shorts.
