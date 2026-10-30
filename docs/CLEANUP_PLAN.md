# Cleanup plan

Status (2026-10-30): phases 1 and 2 are done on branch `cleanup/safe-phases` (5 commits, 92 files,
-3,754 / +1,295 lines, 585 tests passing). Sources: an import graph of every module, AST duplicate
detection, and four read-only reviews (agents LLM side, agents media side, engine/, local_video + unreal +
compositor + tests), with the key claims re-checked by grep.

**Done.**
- Phase 1: every "whole files" and "symbols" item below, except the ones listed under "Left as is".
- Phase 2:
  - items 1 (agents/llm.py), 2 (media helpers), 3 (read_pcm/write_wav, in agents/media.py), 5 (ElevenLabs),
    6 (gpu_lock), 7 (tool paths + slug), 9 (post text) and 10 (shared project helpers);
  - studio-free director: not started (see section 4, last paragraph).
- Bugs from section 8:
  - fixed: #2 (bare ffprobe) and #3 (vision bypassed the budget and fallback);
  - fixed, found during the work: the closing-question check in showrunner held literal backspace
    characters instead of `\b` and never matched.

**Left as is, needs a decision:**
- **Diagram POC:** kept; the other session committed it as "x-ray diagrams".
- **Probes:** `cutaway_probe` / `cutaway_hybrid`, waiting on whether the experiment continues.
- **`septic_yard` kit world and its `kitw_*` reference sets:** a `kit_world` resume can continue them,
  so they go with the kit-route decision.
- **User-Agent strings:** some asset sites need a browser UA.

**Not done yet:**
- **Phase 2:**
  - 4: one mixer (changes the sound; needs a loudness comparison);
  - 8: download helper;
  - 11: env helpers;
  - 12: vision-review cache.
- **Phases 3-5.**
- **Bugs 1, 4, 5, 6 and 7.**

## 1. The picture in numbers

| Area | Lines | Notes |
|---|---|---|
| Whole repo (py + ts) | ~63k | 61 files modified or untracked right now |
| engine/ | ~31k | The director route needs ~4.5k of it (`director/*`, `mocap`, `character`, `toy`, `textures`, `events`) |
| engine/sets (hand-written + generated sets) | ~13.7k non-kit, ~4.4k kit | Bespoke per-topic geometry, not copy-paste: exact duplicates are only ~250 lines |
| agents/ | ~17k | Four generations of Max/explainer orchestration live side by side |

**Conclusion.** The bloat comes from **coexisting route generations** more than from copy-paste. Today
there are seven ways to make a Max/explainer film: cutaway, cutaway-bk, kit, explainer, evolution,
director, and the agent-built sets. Each has its own writer, set format, QA and camera stack. Most of the
code you can remove depends on **which routes you retire**. That decision is yours (section 5). The rest
(sections 3, 4 and 6) is safe whatever you decide.

## 2. Phase 0: preconditions (before touching anything)

1. **Commit a baseline.** Tracked files already depend on untracked ones, so committing either side
   alone breaks the build:
   - `agents/libraries.py:146,148` runs `assets/fetch_sfx.py` and `assets/fetch_music.py`.
   - `compositor/src/Short.tsx:5` imports `./diagram/Xray`.
2. **Wait for the live autopilot run.** `output/autopilot/20261030_102650_cutaway.json` is
   `status: running` and is building `immersed_undersea_tunnel_con_story`. Leave that set alone until the
   run finishes, and check the GPU lock before running anything heavy.
3. **Work on a branch in a worktree.** Another session is editing `main.py`, `autopilot.py`,
   `set_builder.py` and `showrunner.py` while this plan is being written (for example the new
   `cutaway-bk` source). Do the cleanup one phase per commit, and run `pytest` after each phase.

## 3. Phase 1: delete verified dead code (no behaviour change)

Each item below is referenced only by its own definition, or only by a test of itself.

**Whole files**
- `engine/make_poc.py`, `engine/poc_pool.py`, `engine/dev_character.py` (Phase-0 proof of concept, 339 lines).
- `engine/films/pool_film.py` and `engine/films/pool.json`. They were superseded by `sets/pool.py` and
  `cutaway_film.py`. Keep `max_*.json`, `pool_cut.json` and `pool_buildup.json`, which the set builder
  and tests load.
- `agents/depth.py`, plus `animate.render_scene`. First move the live parts of `animate.py`
  (`_draw_overlay`, used by `make_film.py`, and `CAMERA_MOVES`, used by `script.py`) into `render.py`,
  then delete `animate.py`. This also drops `onnxruntime` from requirements.
- `agents/comfy_prompts.py` and `agents/stock_queries.py`, plus the non-beat fallback in
  `editor_pexels.py`: `fetch_stock_footage`, `_per_clip_queries`, `build_pexels_queries`, `title_terms`,
  `search_pexels_videos`, and `media.stitch_clips_to_duration`. The evaluator requires `beats`, so the
  fallback can never run.
- `agents/scene_utils.py` (old `scenes`/`scene_N` schema; only tests use it).
- `agents/plan_writer.py`. Move `ADVICE`, `_has` and `_words` into `stage_writer.py`, which is their
  only user. `director.make` uses `stage_writer.write`.
- The unregistered kit sets and their film JSONs. History reads already tolerate missing sets.
  - `kit_max_built_a_levee_the_river_went_und_story`
  - `kitw_septic_yard_ref_story`
  - `kitw_septic_yard_ref_explainer`
  - `kit_from_sewage_pit_to_silent_treatment_explainer`

**Symbols**
- `script.SCRIPT_MODES`, `script.SYSTEM_PROMPT`, the `"animated"` script mode (script.py: 6 places),
  `set_builder._is_explainer`, `scene_validator.validate_window`, `frame_qa.flicker_map`,
  `claude_cli.notional_cost` / `_notional_usd`, `storyboard.SCHEMA`, `kit_planner.PLAN_SCHEMA`,
  `transcription.srt_time_to_seconds`, `media._run_process`, the `media._remove_files` alias,
  `main.DEFAULT_TOPIC`, `editor_beats` `ai_total` and its single-entry `FOOTAGE_PROVIDERS`.
- In local_video and unreal: `ComfyClient.health`, `config._pinokio_home`,
  `PipelineConfig.backend_available`, `models.total_timeline_frames`, `planner.is_h3`, and in
  `build_sequence.py`: `STAGE_SPACING`, `ground_cover`, `FOLIAGE`, `relative_toggle`.
- `main.SOURCE_ALIASES` / `normalize_source`. argparse never accepts `comfy`, so the alias is
  unreachable.
- Unused parameters: `ai_router.ask(timeout, model)`, `showrunner._call(max_tokens)`,
  `director.gates(plan)`.
- The web-search tool spec `[{"type": "web_search_20260209", ...}]` is built in 7 places, but only its
  truthiness is read. Replace it with `web=True`.

**Diagram POC.** `diagram_writer.py`, `compositor/src/diagram*` and `tools/poc_xray.py` are reachable
only from the POC script, and the generated `poc_b2/poc_b3` diagrams are bundled into every render.
Keep them if the X-ray diagrams are planned for the director route; otherwise delete them. Either way,
gitignore `compositor/src/diagrams/generated/`.

**Probes.** `local_video/cutaway_probe.py` and `cutaway_hybrid.py`, plus their `.bat` files (which are
gitignored while the `.py` files are not, and `run_cutaway_probe.bat` writes to a folder it never
creates). Move them to `tools/probes/` or delete them.

Estimated size: about 3,500 lines removed, with no behaviour change.

## 4. Phase 2: factorize shared infrastructure

Ordered by value. Each item gives the new single home and the copies it replaces.

1. **`agents/llm.py`: one LLM backend.** Today there are four copies of the `claude -p` call:
   - `claude_cli.ask`
   - `showrunner._call_cli`
   - `scene_validator._review_cli`
   - `set_builder.claude_agent` (the streaming variant)

   Duplicated around them:
   - `API_ENV`, effort capping, usage-limit detection (showrunner, autopilot), and Codex capacity
     detection.
   - Three wrappers that turn Codex errors into `UsageLimit`.
   - Two fallback-and-retry loops, two cost counters, and two usage-limit waits (+60 s and +90 s
     margins on the same variable).

   It also fixes a layering bug: `ai_router` imports private functions from `scene_validator` and
   `showrunner`. **Bug fixed along the way:** `claude_cli.ask`, used by `vision.py` on the director
   route, skips the token budget, usage metering and the Codex fallback, and uses a different model
   variable.
2. **`agents/media.py`: ffmpeg and ffprobe.** Add `probe_json()` and use one `run()`. This replaces:
   - `autopilot.probe`
   - `director.check`, which calls a bare `"ffprobe"` and breaks on installs where ffprobe is not on
     PATH (a latent bug)
   - `local_video/validation.py:14`
   - `upscale_worker.probe`
   - `assembly._run` and `director._run`

   Move `assembly._ffmpeg_escape` here too, with a real test.
3. **`agents/audio_io.py`: decode to PCM and write WAV** (8 copies: voice, sfx_library, director ×3,
   audio_fx, sfx, make_film).
4. **One mixer.** `audio_fx.mix_audio` (44.1 kHz, duck threshold 0.02, `TP -1.5`) and
   `local_video/assembly.build_mix_command` (48 kHz, threshold 0.035, `TP -1.0` + alimiter) both
   target -14 LUFS but differ in the details. `MUSIC_VOLUME` defaults to 0.28 in one and 0.12 in the
   other. Merging them changes the sound of one route, so do it as a separate commit and compare
   loudness before and after.
5. **One ElevenLabs client in `voice.py`.** `sfx_library.generate` has its own key loop with no 429
   retry and no rotation persistence, and reaches into `voice._elevenlabs_keys`.
6. **`gpu_lock.py`.**
   - `FileLock` lives in `local_video/queue.py`.
   - `director._gpu_lock` re-derives the lock path by copying config logic.
   - `voice.py` imports it from `agents.director` (a layering inversion).
   - The unreal runner takes no lock at all.
7. **`config/paths.py`: tool paths and one `slug()`.**
   - `BLENDER` defaults to different paths in `director.py:39` and `make_film.py:39`.
   - `NPX`/`COMPOSITOR` are defined 3×.
   - Slug code exists in 8 places, and set-id generators in 4.
   - The User-Agent string is defined 5×, sometimes imported as a private name.
8. **`assets/_download.py`.** Download with `.part` + resume + retry + free-disk guard + unzip is
   implemented 5× (fetch_library, fetch_sfx, blenderkit, depth, fetch_music). Fold
   `assets/fetch_blenderkit.py` into `agents/blenderkit.py` as its CLI, since it reimplements the same
   API with a different on-disk layout.
9. **Post text.** `main.write_post_notes` (`<video>.txt`, which carries the CC-BY credits) and
   `post_text.write` (`<video>_post.txt`) overlap. Merge credits and sources into `post_text` and drop
   the former.
10. **Shared project core for local_video and unreal_video.** The unreal side already imports
    local_video internals. Extract these:
    - `new_project_dir`, project loading and status/resume (the two CLIs)
    - `caption_settings(mode)` (built in 4 places)
    - `ensure_narration` (identical in queue.py and unreal runner)
    - the disk preflight
    - `env_int`/`env_float` (UnrealConfig parses the environment without them)
11. **Env helpers.** `autopilot._int/_enabled`, `scene_validator._env_flag`, and about 10 inline
    `try: int(os.getenv(...))` blocks in set_builder. Reuse `local_video.config.env_int/env_float`
    everywhere.
12. **Vision-review cache.** `set_builder.review_preview` and
    `scene_validator.review_sampled_windows` duplicate the cache, batching and atomic-write logic. The
    scene_validator cache key omits backend and model, so a verdict from one backend is reused for
    another.

Inside engine/, the director route uses both the old and the new helper stack: `toy.box` next to
`lib.box`, and `toy.material` next to `lib.flat`. Settle on `engine/director/lib.py` for camera,
keyframing, visibility, primitives and scene setup. Move `studio._mix_color` into `textures` first,
because the director's single lazy import of it pulls in `studio`, `cutaway`, `backyard`,
`sets.plane_story`, `machines`, `camera` and `framing`.

## 5. Phase 3: retire old routes (your decision; this is the big lever)

| Retire | Frees (approx.) | Must happen first |
|---|---|---|
| **kit** (kit_world, kit_planner, storyboard, engine/kit, septic_yard world, kit sets) | ~6k lines + 3 test files | Remove `kit_max_s_backyard_levee_story` from `AVAILABLE`. Change the `.env.example` default `SHOWRUNNER_SET_MODE=kit` (your `.env` already uses `agent`). |
| **explainer** (explainer, buildup, EXPLAINER_GUIDE, `EXPLAINER_FORMAT=hook` branch) | ~1.5k | - |
| **evolution** (evolution_writer, evo_kit, bridge_evolution, evolution_film) | ~2.7k | The autopilot default source is `"evolution"`. |
| **hand-written cutaway + cutaway-bk** (showrunner writer, set_builder, scene_validator, cutaway/backyard/machines/studio/camera/framing/qa, make_film, all non-kit sets) | ~20k + ~15 test files | Keep showrunner's LLM backend section (moved to `llm.py` in Phase 2). `leader.novelty_problem` stays. |
| **All of the above → director only** | **~30k lines, about half the repo** | Director must be good enough to be the only Max/explainer route. |

Note: `set_builder` prompts point the coding agent at the hand-written sets as worked examples. While
the agent-built route exists, those reference sets are load-bearing even though nothing imports them.

## 6. Phase 4: split the survivors

- **`set_builder.py` (1.8k lines)**, only if it survives: `coding_agent.py`, `set_prompts.py`, spec
  patching, `set_qa.py`, and the build loop.
- **`showrunner.py`:** the backend moves to `llm.py`; the writer remains.
- **`editor_pexels.py`:** split into `stock_sources.py` (provider searches and download), and rename
  `editor_beats.py` to `editor_stock.py` as the route entry point.
- **`render.py`:** rename to `frames2d.py` (it is a Pillow toolkit, which is easily confused with
  Blender rendering).
- **`tests/test_local_video.py` (1.8k lines, 21 classes):** split into planning, queue, media and
  services files, with shared fixtures. Also:
  - Rename `test_unreal_ai.py` to `test_topic_selection.py`; its cwd-relative path makes it silently
    skip.
  - Rename `test_ffmpeg_path_escape.py` to `test_ffmpeg_resolution.py`.
  - Widen `test_blender_code_compiles.py` to all of `engine/**`.

## 7. Phase 5: hygiene and config

- **`setup.ps1:79`** imports `anthropic` and `websocket`, so it fails on a fresh install. Remove
  `websocket-client` from requirements too (never imported). Either add `psutil` or drop its optional
  branch.
- **`.env.example`:**
  - Remove `COMFYUI_DIR` and `COMFY_TIMEOUT` (never read).
  - Deduplicate `COMFYUI_URL` (defined twice with conflicting values), `VISION_*` and `MUSIC_VOLUME`.
  - Document the ~17 variables the code reads but the file omits (`LOUDNESS_TARGET`, `VOICE_ENGINE`,
    `FFMPEG_BIN`, `BLENDERKIT_API_KEY`, `LIBRARY_*`, ...).
- **`compositor/package.json`:** remove the unused `@remotion/media-utils` and `@remotion/transitions`.
- **`unreal_video/config.py`:** `UNREAL_WIDTH`, `UNREAL_HEIGHT` and `UNREAL_FPS` are read and then
  rejected unless they equal 1080/1920/30. Make them constants.
- **`.env.bak.2026-10-27`** holds secrets on disk. Delete it.
- **README:** drop the Hailuo and "comfy alias" history and describe the routes that remain.

## 8. Bugs found during the audit (fix regardless of cleanup)

1. **Autopilot publish bypasses the hold** (`main.py` autopilot branch). It calls `publish_video`
   without the `publish_hold` / `PUBLISH_FLAGGED_VIDEOS` gate, and with metadata `{"ai_generated": True}`
   only, so the title becomes the filename and the description is empty.
2. **`director.check` uses a bare `ffprobe`** and ignores `FFMPEG_BIN`.
3. **`claude_cli.ask` bypasses the token budget and the Codex fallback.**
4. **Scene-review cache key omits backend and model.**
5. **pexels and director ignore `--duration`, `--music`, `--no-captions` and `--no-narration`.**
6. **`setup.ps1` breaks on a fresh install.**
7. **Chatterbox strips `<break>` tags and uses a fixed pause**, while beat timing assumes exact pauses
   (Edge honours them).
