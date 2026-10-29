# Max + Explainer redesign

Status: director route built 2026-10-29 (golden septic film); automation of new worlds next. Covers `--source explainer` and the Max story route (`cutaway` / kit).
`local-ai`, `pexels`, `unreal` are out of scope.

## 1. What is actually wrong (evidence)

Checked on the latest outputs: `output/20261028_from_sewage_pit_to_silent_treatment_plant.mp4`
(explainer) and `output/sets/kitw_septic_yard_ref_story/preview_*.png` (Max).

| Symptom the viewer sees | Root cause in the code |
|---|---|
| Subject is a thin strip in the middle of the frame; 60-70% is empty sky and black void; Max is a few pixels tall | `engine/framing.solve` fits *every* object of a 20 m-wide horizontal cutaway into the narrow width of a 9:16 frame. Kit worlds have no environment past their edges (the evolution route's `world_floor` is not used). |
| Static camera | `frame_all` re-solves the same "fit everything, side-on" shot for every beat; motion is a 5° swing and a 6% push. No close-ups, no shot grammar. |
| Objects are very basic | Each new topic makes a coding agent write a world from scratch (`septic_yard_objects.py`: 886 lines of boxes, cylinders and noise shaders). 2,100 CC0 Kenney models in `assets/cc0` are used only by Unreal. |
| Few textures | Materials are two-tone noise ramps. No PBR texture library, one HDRI. |
| Bad animation | Builds are linear tweens: scale 0.04→1, or slide down 4.2 m. No anticipation, overshoot, stagger, secondary motion. |
| Giant cropped letters filling the screen | Labels are 3D text in world space, sized from one solved camera distance; the gliding camera flies through them. |
| Captions unreadable / unhelpful | `captions: "word"` shows one word at a time; frames rendered at 50% (540x960) and upscaled at the end. |
| "We don't understand what is happening" | 11 fail/fix beats in 80 s of one diorama from the same angle; consecutive states differ by a 20-pixel part. Named concepts ("deadman blocks", "baffles") are never isolated on screen. Script is good; the picture does not carry it. |
| QA passed it anyway | Gates check "object is somewhere in frame", collisions, floating. Final check = resolution, audio, duration. Nothing measures size on screen, legibility, or whether a muted viewer can follow. Vision review is opt-in (`KIT_VISION_CHECK`). |

The older evolution route (bridge video) already looks far better: full-frame world, terrain past the
edges, 2D overlays. The regression is the **kit** path, which both Max and explainer now go through.

## 2. Principles

1. **Phone first.** Every shot is composed for a 9:16 screen held at arm's length: one subject, filling
   40-70% of the frame height, inside the platform safe zones.
2. **The picture tells the story; the voice confirms it.** A muted viewer must follow every beat.
3. **LLMs choose and parametrise; they never write geometry or rendering code.** Assets, animations,
   camera moves and layouts are authored once, by a developer, with tests. Per-video output is data.
4. **Text is a 2D layer**, composited after rendering, pinned to tracked 3D anchors. Never 3D text.
5. **Prove one golden video by hand before automating.** The current pipeline automated planning
   before the renderer could make a single good video.
6. **Measure what the viewer experiences** (coverage, legibility, visible change, mute-test),
   and keep the house rule: gates warn and fall back; only the final review can hold publishing.

## 3. Target pipeline

```
topic + facts (existing research)
  -> 1. Story plan        LLM -> beat sheet: hook, orientation, 3-4 chapters, payoff  (JSON)
  -> 2. Scene + shot plan LLM -> scene graph from the component kit + shot list       (JSON)
  -> 3. Animatic          Eevee low-res keyframes + overlays -> measured gates + mute test
                          -> cheap JSON repairs (never code), max N rounds, then fall back
  -> 4. Voice             narration written TO the locked shot list -> TTS -> word timings
  -> 5. Final render      Eevee 1080x1920 30 fps: beauty pass + per-frame 2D anchor positions
  -> 6. Compositor        labels, arrows, callouts, counters, captions, punch-ins, transitions,
                          music/SFX ducking
  -> 7. Final QA          technical + phone test + mute test -> publish or hold
```

### 3.1 Story plan (replaces 11-beat fail/fix storyboards)

- Length: **strictly more than 60 s and less than 65 s** (target 62 s). Hard requirement, see 3.7.
- Hook + orientation + **4-5 chapters** + payoff, one idea each, 8-11 s per chapter.
- `0-2 s` hook: the most dramatic visual of the video (tank pops out of the lawn) + a 3-6 word
  question on screen.
- Orientation beat: what are we looking at, 2-3 parts labelled.
- Chapters: problem visual -> mechanism close-up -> fix with a satisfying animation -> one-line takeaway.
- Payoff: full system working; last frame rhymes with the first for loops.
- Every beat declares its `visual_change` (what differs on screen) and a `mute_caption` (what a silent
  viewer should understand). Narration <= 2.6 words/s and only names things that are on screen.

### 3.2 Component kit (replaces LLM-written kit worlds)

Engineering explainers are built from a small set of recurring things. Author each once, high quality,
parametric, tested:

- **Ground & section**: layered soil/rock/water-table slab with a clean cut face, grass/gravel top,
  continues past every frame edge; section-cut shader for any object.
- **Containers & structures**: tank, chamber, wall, dam, foundation, pit — bevelled, PBR, cutaway-able.
- **Pipes & flow**: spline pipes with fittings; animated flow (particles / scrolling shader) with colour
  = fluid type (clean / grey / sewage / gas).
- **Fluids & layers**: fill level, stratified layers (sludge/scum), plumes that spread, rising water.
- **Forces & signals**: arrows (push/pull/flow), pressure glow, crack/fail FX, shake.
- **Set dressing**: Kenney houses, trees, vehicles, fences, tools (already on disk, 2,100 models).
- **Characters**: Max as a rigged CC0 character with a clip library (idle, walk, point, cheer, shrug,
  facepalm, dig, carry) instead of the procedural figure.
- **Materials**: ~40 CC0 PBR sets (ambientCG / Poly Haven: soil, gravel, clay, concrete, rusted and
  painted metal, PVC, brick, wood, asphalt, grass, water) + 3-4 HDRIs.

A topic the kit cannot show is not filmed in this route: topic selection is constrained by kit coverage
(fallback: next topic, or another route). New components are developer work with tests.

### 3.3 Shot grammar (replaces `frame_all` for everything)

A fixed library of camera templates, each solved against **the subject's** bounds only, and
vertical-first (fit height, allow the world to bleed past the sides):

| Template | Use |
|---|---|
| `establish_push` | orientation: wide-to-medium push with labels popping in |
| `hero_close` | one part fills 50-70% of the frame height |
| `reveal_cut` | camera holds while the section cut sweeps open |
| `follow_flow` | camera rides along a pipe with the flow |
| `split_compare` | before/after stacked top/bottom (natural for 9:16) |
| `orbit_detail` | 3/4 orbit around a mechanism |
| `reaction` (Max) | medium shot of Max, 35-55% of frame height, intercut with mechanism shots |
| `impact` | short punch-in + shake on a failure moment |

Rules: no shot longer than 3.5 s without a cut or a clear move; consecutive shots differ in template
or scale; subject coverage >= 25% of frame area.

### 3.4 Animation library

Easing presets (back-out overshoot, anticipation, spring settle), staggered part-by-part builds,
drop-and-bounce, dig/fill, flow start/stop, fill-level rise, plume spread, crack and shake, glow pulse
for "look here". Timed to narration words (existing `align_beats`).

### 3.5 Look

Eevee at full 1080x1920 (no 50% render + upscale), AgX, HDRI + sun, ambient occlusion, bloom,
shallow depth of field for the miniature look, motion blur, subtle film grain in the compositor.
A per-route style sheet (palette, fonts, label style) so every video is on-brand.

### 3.6 Compositor and text

Blender writes the beauty pass plus a JSON of every anchor's 2D screen position per frame.
The compositor draws on top:

- **Labels** with leader lines pinned to anchors, max 2 at once, top half of the frame.
- **Captions** in 2-4 word phrases, keyword highlight, cap height ~5% of the frame, placed at
  ~60-68% of frame height (clear of the TikTok/Shorts bottom bar and right rail).
- **Chapter titles**, counters ("3-5 years"), arrows and circles, punch-in zooms, whip transitions.

Recommended tool: **Remotion** (React video, JSON-driven, spring animations, proper typography,
caption tooling). Alternative if adding Node is unwanted: a Python compositor on `skia-python`
(same design, more work for animation and text layout).

### 3.7 Duration: 60 s < final < 65 s

- The planner budgets words from the target (62 s at the measured voice rate, ~150-160 words).
- After TTS, the measured voice length decides: too long -> tighten the script (cut/merge a sentence)
  and re-voice; too short -> add a sentence to the payoff or lengthen holds (hook freeze, chapter
  title holds, end tail) within limits.
- Last resort, so the run never fails: adjust the tail/holds, then a speech-rate change of at most
  +/-5% (pitch preserved), to land the final inside the window.
- Shots are retimed to the voice, so picture length always follows.
- Final check: `60.0 < duration < 65.0` on the encoded MP4 (container and streams).

### 3.8 QA that measures the viewer's experience

Measured on the animatic (cheap, before voice and final render) and again on the final:

- **Coverage**: subject share of the frame per shot (from an object-index pass) >= 25%.
- **Legibility**: text cap height >= 3.5% of frame height at 1080p; contrast; inside safe zones;
  no overlap between labels, captions and the subject's key part.
- **Visible change**: per beat, image difference in the subject region between start and end
  above a threshold (the state change must be visible at thumbnail size).
- **Motion**: no static span > 3.5 s.
- **Mute test**: a vision model sees each beat's keyframes without narration and describes what
  happens; compared with the beat's `mute_caption`.
- **Phone test**: same review on a 360x640 downscale.
- **Duration**: final strictly between 60 and 65 s (3.7).

Failures repair the JSON (re-pick template, move a label, enlarge a part). After the repair budget
the run continues with a warning; the final mute test is the only thing that can hold publishing.

## 4. Toolchain and asset library (chosen 2026-10-28)

All free; assets are CC0 (commercial use, no attribution). Downloaded by scripts, git-ignored.

| Need | Tool / source | Where | Status |
|---|---|---|---|
| 3D render | Blender 5.2, Eevee, AgX | `BLENDER_EXE` | installed |
| PBR materials | ambientCG, 2,037 materials, 2K JPG | `assets/cc0/ambientcg` | downloaded |
| PBR textures | Poly Haven, 869 textures, 2k `.blend` + maps | `assets/cc0/polyhaven/textures` | `assets/fetch_library.py` |
| Realistic models | Poly Haven, 521 models, 2k `.blend` | `assets/cc0/polyhaven/models` | `assets/fetch_library.py` |
| Lighting / skies | Poly Haven, 997 HDRIs, 2k | `assets/cc0/polyhaven/hdris` | downloaded |
| Stylised props | Kenney, 19 kits (2,100 models) | `assets/cc0/kenney` | `assets/fetch_cc0.py` |
| Characters + motion | Quaternius Universal Base Characters + Universal Animation Library 1 & 2 (86 clips, one 65-bone rig) + 19 prop/nature/city/vehicle/animal packs | `assets/cc0/quaternius` | `assets/fetch_quaternius.py` |
| Asset index | `assets/cc0/catalog.json` (tags, categories, real size) | | built by `fetch_library.py --catalog` |
| 2D layer + final edit | Remotion 4.0.535 (React; `@remotion/captions`, google-fonts, transitions) | `compositor/` | working: captions, hook/chapter cards, pinned labels, stamps/counters, punch-ins, grain |

Remotion licence: free for individuals and companies of up to 3 people; larger companies need a
company licence.

## 5. Plan

| Phase | Deliverable | Done when |
|---|---|---|
| 0. Stop the bleeding (1-2 days) | Full-res render, 2D labels instead of 3D text, phrase captions in safe zone, vertical-first framing with a coverage floor, environment past the edges | Re-rendered septic explainer: subject fills the frame, no cropped text |
| 1. Look & text | PBR/HDRI library, render preset, compositor (captions, pinned labels, arrows), anchor export | One hand-built shot looks "YouTube-ready" |
| 2. Kit & camera | Component kit (ground/section, tanks, pipes+flow, fluids/layers, forces), shot templates, animation library | **Golden video**: septic explainer from a hand-written JSON, judged against the bar |
| 3. Automate | Story planner, scene/shot planner, animatic loop, new QA gates | Three new topics produced unattended at golden quality |
| 4. Max | Rigged character + clip library, reaction-shot grammar, Max story planner | One Max story at golden quality |
| 5. Cleanup | Retire `kit_world` world-coding, per-topic `engine/sets` code, `frame_all` on new routes | Tests green; old routes behind a flag or deleted |

## 6. Open decisions

1. Keep Phase 0 (quick fixes on the old path) or go straight to Phase 1.

## 7. What is built (2026-10-29)

```powershell
python -m agents.director engine/director/plans/septic.json --stills   # voice + timing + 2 stills per beat
python -m agents.director engine/director/plans/septic.json            # the full film
python -m agents.director engine/director/plans/septic.json --compose-only   # redo sound + text only
```

| Piece | File | What it does |
|---|---|---|
| Plan (the scenario, data) | `engine/director/plans/septic.json` | beats: narration, hook text, chapters, labels -> anchors, callouts, checklist, end card |
| World spec (data) | `engine/director/worlds.py` | what each beat shows, cue words, anchors, beat order |
| Plan writer | `agents/plan_writer.py` | retention rules as the prompt + a validator (word budget, hook <= 12 words, cue words present, labels <= 3 words, 3-4 chapters, 3 rules); one repair turn, then the reference plan |
| Blender toolkit | `engine/director/lib.py` | ambientCG PBR (box-projected), HDRI, easing (BACK/BOUNCE/ELASTIC), camera shots by "metres of world across the frame", shake, anchors export |
| Golden world | `engine/director/septic.py` | strata soil with a keyed water table, half-cut tank with sludge/water/scum, PVC tees and pipes, gravel drainfield, mascot, truck, burst FX |
| Driver | `agents/director.py` | voice fit (pause tightening -> <=5 % tempo -> tail), Whisper cues, Blender under the shared GPU lock, synced SFX + music bed, Remotion compose, duration check, mute test |
| Text layer | `compositor/` | Remotion: captions, hook/chapter cards, pinned labels, stamps/counters, checklist, end card, punch-ins, grain |
| Tests | `tests/test_director.py` | window fitting, pause capping, plan rules, overlay timeline (<= 2 labels at once) |

Measured on the golden film: narration 156 words -> 60.7 s after tightening 26 pauses to <= 0.5 s, no tempo
change, 1.8 s tail -> 62.5 s total. Full-resolution Eevee frame ~4 s on the RTX 3080 (about 2 h per film).

Next: a second world built on the same toolkit (proves the toolkit generalises), plan writer wired to the
autopilot's topic research, then Max on the Quaternius rig (Phase 4).

## 8. Review of golden v1 -> pipeline fixes (2026-10-29)

The first golden film was rejected by the producer: flicker, unclear, faded, incoherent (the tank rose and
the hole vanished), nothing visible inside the tank, not funny, and a checklist that felt like a lesson.
Each was a pipeline gap, so each became a pipeline rule or gate, not a one-off fix:

| Rejection | Measured cause | Pipeline fix |
|---|---|---|
| Flicker | 965 of 1,873 frames had > 0.2 % single-frame pixel spikes. Eevee motion blur (random per-frame sampling) made fine textures sparkle; thin foliage aliased; overlapping blended water strobed | `lib.reset` defaults: motion blur OFF, shallow focus (f/2.2) on the actor; chunky set dressing only; opaque liquids, no coplanar faces. **Flicker gate** (`agents/frame_qa.flicker`) on consecutive animatic frames |
| Faded colours | Subject palette (beige soil, grey concrete, pale water) | `AgX - Punchy` look, art-directed `PALETTE` (actors are the most saturated things in frame), +15 % saturation grade in the compositor. **Colourfulness gate** (Hasler-Suesstrunk >= 40) |
| Can't see / not clear | Actions tiny and brief; nothing measured them | Worlds register every action (`world.act(name, obj, f0, f1, min_share)`); Blender measures each actor's on-screen size and time in frame (`actions.json`). **Visibility gate**: size >= min_share, in frame >= 80 %, held >= 0.6 s |
| Incoherent | The cavity moved with the tank; nothing checked physics | World state persists (static cavity, keyed breach cutter, lid and dirt stay where they land, the tank breaches instead of flying). **Viewer review** flags physical contradictions |
| Not funny / lecture | The format was "explain + 3 tips" | Format = hero + one gag per beat + payoff + button + teaser. Every world declares a `hero` and a `gag` per shot; the plan writer bans advice ("you should", "make sure", checklists) and the validator rejects it |
| Found too late | Stills -> 2 h final | **Animatic stage**: every frame at half resolution (~20 min) -> gates + a sound-off, text-off viewer review (what happens / clear / funny 1-5 / incoherent / biggest fix) -> `qa_report.json`, before the final render |

These apply to every future world and to the Max route (Max is the hero; same gates, same format).
