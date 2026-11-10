# Channel plan: instructions for Claude Code

You are helping run a 30-day plan to grow and monetize a YouTube Shorts channel of animated weird true stories from history. The video pipeline in this project makes the videos. Your job each session is to follow the plan, make the day's Short with the pipeline, track the numbers, and keep the plan file up to date.

Read this whole file at the start of every session, before doing anything else.

## Files

All in the project root unless the user says otherwise:

| File | What it is | Who changes it |
|---|---|---|
| `30 day action plan.md` | The plan. Section numbers below refer to it. | You, only in the places listed under "Updating the plan" |
| `YouTube monetization plan 30 days.md` | The research and sources behind the plan | Nobody. Read-only reference |
| `kpi-log.csv` | One row per Short: what was made and how it did | You (create it on the first session if missing) |
| `variation-log.csv` | The look of each Short, so nothing repeats | You (create it on the first session if missing) |

## Start of every session

1. Read `30 day action plan.md`, `kpi-log.csv` and `variation-log.csv`.
2. Work out today's Day number. Day 1 = Sunday 8 Nov 2026, in Asia/Dubai time. Day 30 = 7 Dec. The application deadline is 15 Dec 2026 (Day 38).
3. Check the "Progress" section of the plan for open decisions. If the **channel name decision** (plan, section 4, Day 1) is not recorded yet, ask the user before making anything, because titles, the About section and the outro depend on it.
4. Check whether any Short is due for its 24 h, 48 h or 7-day numbers, and ask the user for them (see "Logging the numbers").
5. Tell the user in 3-5 lines: today's Day number, today's topic, which numbers you need from them, and any gate or trigger that applies today.

## Making the day's Short

1. **Pick the topic.** Use today's row in the topic calendar (section 5). Two exceptions:
   - A breakout trigger is active (section 3): make a follow-up of the breakout's topic type instead.
   - The Day 14 gate moved the mix to "disaster with a stupid cause" and "huge-money blunder": pick from those types.
2. **Topic check.** Search the web for existing YouTube Shorts on the topic. If it's marked "Likely crowded" or you find popular Shorts telling it the same way, propose a fresh angle (a lesser-known detail, a different person's view, a number nobody used) or a swap, and let the user choose. Record the angle in the log.
3. **Script.** 60-70 s spoken. Hook: the full claim by 2.5 s, opening mid-action. Story format with a twist ending. Fact-check every claim against at least two sources and keep the source list.
   - The "If you ..." opener rule is for the how-it-works explainer videos. Do **not** use it for these story Shorts.
   - The ending and payoff must differ from every Short in the last 14 days of `kpi-log.csv`. A recurring character's gag never ends the same way twice.
4. **Variation.** Pick a camera style, shot count, music cue, colour palette and hook type for this video, using whatever options the pipeline supports. Don't repeat the same combination used in the last 7 days of `variation-log.csv`, and don't use the same hook type two days in a row. Only the intro and outro stay the same. Write the choices to `variation-log.csv`.
5. **Render** with the pipeline. The pipeline must run on its own; if a step fails, fix it and re-run, as usual.
6. **Prepare for the human pass.** Give the user:
   - 3 title options: event name + a hard number or outcome (example: "The Town That Blew Up a Whale With 20 Cases of Dynamite").
   - A draft description with the source list, clearly marked as a draft for them to rewrite in their own words.
   - The caption question.
   - A one-line note on how today's look differs from the last few Shorts.
7. **Don't publish until the user has done the human pass** (picked and edited the title and description). After that, the same clean file goes to YouTube, TikTok, Instagram Reels and Facebook Reels. Never upload a YouTube download.
8. On the long-video days (28 Nov and 5 Dec), the long video replaces the Short. Build it from existing scenes with **new** connecting narration; leave a slot for the user's own-voice intro.

## Logging the numbers

The user reads the numbers from YouTube Studio and gives them to you. Always ask for **engaged views** (Studio > Analytics > Advanced Mode), not the public counter.

For each Short, ask at 24 h, 48 h and 7 days for:
- viewed vs swiped away %
- average view duration (seconds)
- engaged views
- new subscribers

Add them to `kpi-log.csv` with these columns:

`date, day, topic, type, angle, title, length_s, hook_type, vvsa_24h, avd_24h, engaged_24h, subs_24h, vvsa_48h, avd_48h, engaged_48h, subs_48h, engaged_7d, subs_7d, notes`

Then check the table in section 3 of the plan and tell the user straight away if any rule fires:
- **Weak hooks:** 3 of the last 7 Shorts under 60% viewed vs swiped → rebuild the hook template.
- **Mid-story drop:** average view duration under 30 s for a whole week → start the 45-55 s test cuts (YouTube only; keep 61 s+ for TikTok and Facebook).
- **Weak topic:** engaged views under 1,300 at 7 days → change the topic type, not the style.
- **Weak subs:** under 1 sub per 1,000 engaged views → stronger ending, pinned comment, trailer.
- **Breakout:** 100K engaged views within 72 h → drop the calendar, plan 3-5 follow-ups of the same type within 7 days, and propose reply-Shorts from the best comments.

Never delete or re-upload a Short, even a flop.

## Gates and reminders

| When | What to do |
|---|---|
| Every Monday | Remind the user about 5 client pitches. Offer to draft the emails (teachers' YouTube channels, museums, education apps). Don't send anything yourself. |
| Day 7 (14 Nov) | Rank the Shorts by engaged views and subs per 1,000. Report the best topic type for week 2. |
| Day 14 (21 Nov) | If total engaged views are under 50K and no Short is over 10K: switch the topic mix fully to "disaster with a stupid cause" and "huge-money blunder". |
| Day 21 (28 Nov) | **Go for 15 Dec** only if ≥500 subs, ≥3M engaged views since Day 1, and ≥450K engaged views a day and rising. Otherwise: aim for the fan-funding tier and grow long-form. |
| Days 22-28 | Run the pre-application check in section 4 and report anything that fails. |
| Days 29-38 | Report which target is reachable (1,000 subs + 10M, or 500 subs + 3M, or neither). If applying: remind the user not to change or hide any videos during review. |

Calculate every gate from `kpi-log.csv` and the totals the user gives you. Show the numbers, then the decision.

## Updating the plan

Keep `30 day action plan.md` current, but only change these parts:

1. **A "Progress" section at the very top** (add it on the first session). It holds:
   - Today's Day number and the date of the last update.
   - Totals so far: Shorts published, engaged views, subscribers.
   - Best Short so far (topic, engaged views).
   - Decisions made (channel name, gate results, topic-mix changes) with dates.
   - Open questions for the user.
2. **The topic calendar (section 5):** mark rows done, record swaps or new angles, and replace upcoming rows after a breakout or a gate decision.
3. **The "What changed" list at the end:** add one dated line for every change you make.

Don't change the targets, the rules in sections 3 and 6, or the odds without asking the user first. If the numbers suggest a rule is wrong, say so and propose the change.

## End of every session

Tell the user in a few lines:
- what was made today and where the file is
- what's waiting for them (human pass, numbers to send, pitches)
- any trigger or gate result
- what's planned for tomorrow
