# Sandcastle film (2026-10-30): fixes made by hand, and what the pipeline must learn from them

Film: `output/films/20261030_max_vs_the_sea_how_bacteria_turn_a_sandcastle_to.json`, set
`engine/sets/s_bacteria_cemented_backyard_story.py` (built by the set builder, 9/11 beats accepted, rendered without
the rehearsal / scene review to save time). Problems seen on the rendered frames, fixed directly in the set code,
then only the changed frames re-rendered (`make_film --redo` with time ranges).

| # | Problem on screen | Cause in the set code | Fix (set code) | Pipeline fix to make |
|---|---|---|---|---|
| 1 | Hook: the wave stands beside the castle for 5 s like a frozen blue wall, never crashes; it would not stop a scroll | `a_wave_hook` keyed the wave at x 2.55 -> 2.42 -> 2.40 -> 2.50: it barely moves | The wave rushes in from the right, hits at 0.5 s, bursts into spray over the tower, collapses and drains back | The hook must contain MOTION: QA measures the hook's main object travel / scale change in the first second; the hook rehearsal is never skipped |
| 2 | The grain inset (magnified circle) is cut by the top frame edge at the start of 6 beats | `close()` frames Max tight while the inset floats high above him | `close()` hides the inset during the opening close-up; it appears on the cut to the wide shot | QA `label_crop`-style check for any overlay prop (inset, sign) cut by the frame edge; guide rule: hide insets in close-ups |
| 3 | "No food" beat: the wave is a blue sausage (a cylinder) | `wave_run` animated a plain cylinder | The curling wave (`_surge`, the finale's) rushes in, breaks and drains back | Guide: one wave component (profile + foam lip) reused; ban primitive cylinders as water |
| 5 | A manual `--redo` started right after the run lost its kept frames | The autopilot deletes the render frames (8.2 GB) when it finishes, without checking that a redo is using them | (redo restarted: it rebuilds kept frames from video.mp4) | The cleanup skips a work dir that a running make_film holds (a lock file), and redo always rebuilds missing kept frames from video.mp4 |
| 4 | The run nearly stopped: a hook rejected by the rehearsal went to render unchecked | The time-saving restart turned off the rehearsal and scene review entirely | (process) | Fast mode keeps the hook check: rehearse and repair the hook beat even when other checks are skipped |

## Oil film (same evening, the 26 Oct pipeline in worktree `video-creator-1026`, set `backyard_oil_well_story`)

The 26 Oct set builder: 80 min, 3 rounds, stayed at 4/11 accepted (rounds 2-3 did not improve) and then stops with
no film. Fixed by hand in the set code, checked on stills, full render:

| Problem | Cause | Fix | Pipeline fix to make |
|---|---|---|---|
| Hook opens underground (gas arrows) for 1.7 s; the gusher erupts late | the hook reuses the failure beat's `_gush`, eruption at 40 % | `_gush(rise=)`: the hook erupts at 3 % | Hook staging rule: the spectacle in the first 10 frames, never a setup shot |
| Gusher reads as a stack of black balls | 18 + 16 big spheres | 40 small overlapping drops + a wide crown of small drops | A tested liquid-jet component (like studio.Water) |
| Gusher beats end on an extreme face close-up: no gusher, barbecue or cat at the end | `cu_cam` 35 mm on Max's face | a wide final shot | Measured check: the beat's must-see objects are in frame at 7/8 |
| Dry-well end: the derrick hides Max; casing: labels out of frame | cameras 2.4 m from the subject | pulled back to ~4 m | Same check (labels / must-see in frame) |

| A finished 2,286-frame render was wiped by 23 duplicate renders | make_film's sticker pass uses a process pool; on Windows each worker re-imports the calling script, and a script calling `produce()` without an `if __name__ == "__main__":` guard starts a whole render per worker, each one deleting the frames | Killed them; kept the 1,175 surviving frames (hard links in comp/) and `--redo` only the 1,111 missing ones | make_film runs the sticker pool from a module function that refuses to start when `__name__ == "__mp_main__"`, or uses threads; never `rmtree(frames)` while another make_film holds the work dir (lock file) |

Left as is (time): Max bends forward with his face hidden in the misting and packing close-ups (the `water` / `chop`
clips); a flat blue water slab in the hook's foreground; the castle turns pink when sprayed; the cement bath is an
opaque teal box (the castle soaking inside is not visible); the finale sign's pole stands in front of the castle edge. Pipeline fix: QA checks
the hero's face is visible (head facing the camera) in close-ups.

## Pipeline fixes made from these lessons (night of 30-31 Oct)

Each hand fix above is now done by the pipeline itself, so the next film needs no hand edits for it:

| Hand fix | Pipeline fix (where) |
|---|---|
| Inset / labels cut by the frame edge in close-ups | `engine/overlays.settle`: after staging, any `label_*` / `inset_*` group the camera cuts at the frame edge is hidden for those frames (no flicker: short runs merged; cut for most of its window = hidden for all of it). Runs in every render, QA and preview (21 s for 3,071 frames). New `studio.Inset` (camera-facing, parented contents) so insets get this too |
| Stickers stacked on 3D labels ("2 m" on DRY SAND, pill on 1% WATER) | `settle` also writes `text_boxes.json` (where readable labels sit, frame by frame); `make_film.drop_clashing_stickers` drops a sticker whose place a 3D label takes for > 15 % of its beat |
| Hook wave barely moved / oil eruption at 40 % | `qa.hook_motion`: measured motion of the biggest moving thing (angle seen from the camera, so camera moves don't count) in the hook's first second and first 10 frames; `hook_still` / `hook_late` reject the hook beat in the set builder |
| Oil hook's first 7 frames showed the finale close-up | `camera.HARD_CUTS`: the epilogue hook's first frame always cuts to its own shot (cutaway_film adds it) |
| Gusher = black balls | `studio.Jet`: core stream + crown of small drops (steep jets) or one arcing stream (burst pipe); guide points to it |
| Max bent over with his face hidden in close-ups | `qa.quality` `face_hidden`: in close-ups (>= 35 % of frame height) the head must face the camera for >= 60 % of the samples (flags the sandcastle mist beat, nothing else) |
| 23 duplicate renders from the sticker process pool | sticker pass uses threads |
| Cleanup deleted frames a manual redo was using | `make_film.produce` holds `work/.make_film.lock`; a second make_film refuses, autopilot cleanup skips a held work dir |
| Derrick in front of Max; sign pole in front of the castle | `qa.must_see`: a must-see thing hidden behind an opaque prop (>= 80 % of 15 rays; same-assembly parts, characters, glass/water and shader-clipped cutaways ignored) is reported |
| Nobody judged whether the WHOLE film can be followed | `agents/film_review.review` after every autopilot film: one 4-frame strip per beat, sound-off viewer test + narration; writes `<video>_viewer.json`, logs QUALITY WARNINGs (on the sandcastle film it found the frozen wave, the stacked labels, the cut inset). Plus `<video>_sheet.jpg` |
| (found tonight) Both night runs spent the whole 7M Claude budget on set repairs and STOPPED with no film | the set build may spend `SET_BUILD_BUDGET_SHARE` (0.7) of the budget; when it cannot afford another turn (or a review) it hands over its best reviewed draft instead of stopping the run |
| (found tonight) BlenderKit models rejected every beat: their toon colours read as "flat", their own booleans as "live_boolean" | QA skips objects under a `BK_*` root for the flat / construction / coplanar gates |
| (found tonight) Close shots of Max riding the rising house filmed the top of his hat | `toy.world_location_at` (parents included); `studio.close_on` follows in world space; guide rule for set-made camera helpers; `face_hidden` also flags overhead close-ups; new `camera_inside` gate |
| (found tonight) Identical spray drops parked together flagged as z-fighting | the coplanar gate treats same shape + materials + place as one surface |
| (found tonight) The floating-cabin finale rendered at 45 s/frame, GPU idle: a BlenderKit cake's subdivision + booleans evaluated at render levels on the CPU | `props.light`: imported models get subdivision capped at 1 level and fast booleans (the toon pass flattens that detail anyway) |
| (found tonight) Production repair rounds that fixed nothing (11 rejected windows before and after) each re-rendered most of the film, with up to 3 attempts x 2 rounds | patience: make_film stops repairing when a round does not reduce the rejected windows; the autopilot ships the flagged film when an attempt fixed nothing |
| Microscopic mechanism in a small inset | topic gate: `mechanism_size_cm` < 10 rejects the subject (`STORY_MIN_MECHANISM_CM`) |
| Runs stopped instead of shipping a flagged draft | `.env` `AUTOPILOT_ON_GIVE_UP=ship` (was `fail`) |

Also: `ELEVENLABS_DISABLED=1` blocks every ElevenLabs call (test runs); the mouth check no longer flags one gasp per kid in a loop over the kids; two autopilot runs at once never research the same subject (`showrunner._subjects_in_progress`).
