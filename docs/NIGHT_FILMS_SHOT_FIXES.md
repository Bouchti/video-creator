# Night films (31 Oct 2026): shots fixed by hand, and the pipeline fixes they led to

Two films were made by the pipeline alone overnight. Both shipped flagged (`_NEEDS_REVIEW`). On 31 Oct the broken
shots were fixed in each set's code and **only those frames** were re-rendered (`make_film --redo` with time ranges,
`REDO_KEEP_STALE=1`, `SCENE_VALIDATE=0`). Every other frame, the voice and the timings were kept. The flagged
originals are untouched; the fixed films are written next to them as `<name>_FIXED.mp4`.

Backups of the set code, previews, post text and work videos from before the fixes are in
`output/kept/before_shot_fixes_20261031/`.

## Film 1: flood-proof house (`20261031_max_builds_a_flood_proof_house_it_sailed_away_fi`)

Set: `engine/sets/s_floating_riverside_cabin_a_story.py`

| Shot (frames) | What was wrong | Cause | Fix in the set |
|---|---|---|---|
| guide posts 920-993, snap 1083-1185, coils 1334-1420 | a giant orange hat fills the frame for ~1.5 s at the start of each beat | the close shot aims at standing head height while the kneeling `fix` clip bends Max toward the lens | `talk` + `point` (upright) instead of `fix`, as the set's own pontoon beat already did |
| lean 1530-1642 | Max blurred, leaning into the lens, a pipe across his head | leaning `push` clip in the same close shot | `talk` + `point` |
| drift 756-834 | "the current took the house" but the house looks parked | the camera followed the porch (lag 0.15): only the dock posts moved | wide `lag_track` of the whole house, camera follows half way (lag 0.5): the house visibly slides out of the dock |
| hook 1-105 | not spectacular: a Max close-up on the porch, the house never visibly races | same following camera | wide `lag_track` of the whole racing cabin for the first half, then the gasp close-up |

The rewind montage is rebuilt from the build frames, so its giant-hat glitch frame went away with the fix.

## Film 2: water tower (`20261031_max_builds_a_water_tower_it_crumpled_like_a_soda`)

Set: `engine/sets/s_backyard_water_tower_raise_story.py`

| Shot | What was wrong | Cause | Fix in the set |
|---|---|---|---|
| raise tank (whole beat) | a long black line across the frame for 4 s | a crane cable on the tank, with no crane in the shot | cable hidden; `talk` instead of a leaning `push` (face hidden from the high wide camera) |
| steel legs, close shot (first third) | Max lying flat over the footing, seen from above: a giant hat | the `crouch` clip in a close shot | `idle` (upright, the wrench arm still works) |
| steel legs, label | "LOAD PATH" read as "OAD PAT" | label placed between the tower legs, behind the load arrows | label moved beside the tower, on the camera side |

### Second round (user review: "the water looks solid, the pipes are not connected well and sometimes wrong")

| Shot | What was wrong | Cause | Fix in the set |
|---|---|---|---|
| hook, raise tank, finale (slide water) | the water read as solid plastic | a flat blue slab (`water_surface`) with ~40 balls (r 4.5 cm) and two 8-12 cm tubes lying on it, a 10 cm curved tube off the run-out, white foam balls (r 16-22 cm) at the end | `studio.flowing_water` on the chute (see-through, foam streaks racing down), streams 4.5-6 cm, drops 2-3 cm and few, a fan of three 3 cm jets off the run-out, foam puffs 5-7 cm |
| every shot showing the cutaway trench | the underground pipe stopped dead at the trench end | it turned back into the soil (out of the section) to reach the riser behind the slide | the run stays in the trench, rises up a carved shaft in the section, comes out through a cover plate, runs along the lawn under the slide deck, then up the riser |
| raise tank | the downpipe ran down through the soil and out of the frame | a fixed 6 m rod parented to the tank, which starts on the grass | the downpipe stands on the ground and is scaled to the tank's height at every key (`pipe_to_tank`) |
| fail ground, raise tank, poles, steel legs | an empty dark trench before any pipe is laid | the trench is carved from the start | soil fill boxes, hidden when the outlet (right) and the supply (left) are laid |

Re-rendered: beats 1, 3, 4, 5, 6, 7, 12 (the beats where the water or the pipe run is on screen, found by
comparing new test stills with the kept frames); beats 8-11 (the tank top) kept. The first `_FIXED.mp4` is kept in
`output/kept/before_water_pipe_fix_20261031/`. Result: new `_FIXED.mp4` (76.0 s, -14.5 LUFS), 1,442 frames
re-rendered, 837 kept; checked on stills of the hook, the trench, the tank raise and the finale.

## Pipeline fixes made from these lessons

| Lesson | Fix | Where | Test |
|---|---|---|---|
| kneeling / bending clip under a close camera = giant hat | before the clips play, every `fix` / `crouch` / `push` / `pick_up` / `plant`... frame where the camera is close on that character (>= 33% of the frame height) gets the upright `talk` clip | `engine/character.py` `upright_close_ups()`, called by `perform_queued()` (`CLOSE_UPRIGHT=0` turns it off) | `PostureStillTest` |
| a label hidden behind scene geometry | `overlays.unblock()`: a static label with >= 30% of its letters behind something opaque is pulled toward the camera (scaled by the same ratio: same place and size on screen); a moving one is hidden on those frames like a cut one | `engine/overlays.py` (inside `settle`) | `OverlayStillTest` (label behind a wall) |
| a cable with nothing holding it reads as a stray line | QA gate `dangling_line`: a rod / cable thinner than 5 cm and longer than 4 m that crosses >= 45% of the frame with >= 40% of its length off screen | `engine/qa.py` `_dangling()` in `quality()` | `DanglingLineStillTest` |
| water sheets read solid | `studio.flowing_water(name, color, along, speed)`: see-through water with foam streaks moving downhill (a frame driver), for slides, spillways, gutters | `engine/studio.py` | `FlowingWaterStillTest` |
| solid water, disconnected / wrong pipes, before the code is written | guide rules: LIQUIDS (sheets use flowing_water, streams <= 5 cm, drops <= 3 cm and few); PIPES CONNECT (one visible chain, stays in the section plane, comes up through the ground visibly, stretches with a moving tank, no empty trench) | `agents/set_builder.py` STORY_GUIDE | prompt size test |
| the four lessons, before the code is written | guide rules: close shots stay upright; TRAVEL MUST READ (camera follows a travelling thing at most half way); NO DANGLING LINES; LABELS IN FRONT | `agents/set_builder.py` STORY_GUIDE | prompt size test |

## Still open (not fixed in these films)

- Sound: 4 effects missing in film 1 (clunk, power down, clank, spring stretch) because ElevenLabs was disabled
  for the test; the local library had no match.
- Film 1: some 3D labels sit far from what they name ("1 m³ WATER = 1 TONNE" over the tree, "LOW BALLAST" on the
  wall); the finale's "5.5 m" sticker covers the house.
- Film 2: the poles collapse is a cluttered jumble; Max stands on a footing block in the city-tanks beat.
- The core problem is unchanged: every subject's scenes are written from scratch and about half are accepted on
  the first try. These fixes remove four defect classes; they do not make the first draft better at composition.
