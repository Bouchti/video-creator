# Max cutaway films: review of the tunnel film and the fix plan (2026-10-30)

Goal: the pipeline makes Max films like the published pool / boat / pumpkin shorts on its own
(clear, fun, a new impressive fact, Max + kids), via `python main.py --source cutaway` (all-primitive
sets) or `--source cutaway-bk` (whole objects from BlenderKit, only the mechanism built).

Length rule: longer than 60 s, no upper limit, length is not a priority (the references run 83-90 s).

## State

- Branch `pipeline/cutaway-bk-and-gates`. Uncommitted: the human-scale fix (agents/showrunner.py,
  agents/leader.py, agents/set_builder.py, tests/test_showrunner.py) and assets/sfx/steel_clank.mp3.
- Review film: `output/immersed_undersea_tunnel_con_story.mp4` (56.3 s, -15 LUFS), made from the
  undersea-tunnel set (`engine/sets/immersed_undersea_tunnel_con_story*.py`), which the set builder never
  accepted (4/13 scenes after ~7M Claude tokens). Rendered directly with
  `SCENE_VALIDATE=0` + `engine.make_film` (run make_film as a module, never via runpy `__main__`: the
  sticker pass uses a process pool).
- Done today: novelty + impressiveness gates for new subjects; human-scale gate (largest_part_m <= 12 m,
  Max builds his OWN version; the giant real one is the closing number); set-builder look gate
  (median colourfulness >= 45), gag contacts not counted as collisions, 40 min repair turns,
  SET_FIX_MAX_WINDOWS=6; resume continues a new subject in progress; the cutaway-bk route
  (engine/props.py, agents/blenderkit.resolve_set_props).

## The user's review of the tunnel film, and the root cause of each point

| # | What the user saw | Root cause | Fix |
|---|---|---|---|
| 1 | Everything goes too fast, nobody follows | Scripts are sized for 2.4 words/s (`showrunner.WORDS_PER_SECOND`, measured on ElevenLabs); Chatterbox speaks 3.27 words/s (176 words in 53.8 s) and every action is timed to the voice, so the film runs ~35 % faster than designed | Measure the voice rate (as `stage_writer.record_rate` does) and size scripts to it; slow Chatterbox (cfg / tempo); minimum hold on each key action; length free (> 60 s) |
| 2 | Max seems to speak the narration | The set code calls `max.talk(...)` as an idle animation while a third-person narrator speaks | Rule in the set guide + a static check: no `talk`/lipsync under narration; mouth only for a shout or gasp |
| 3 | Birds even under water; noisy effects | `agents/sfx.render_events` lays ONE birdsong ambience under the whole film; effects not levelled | Ambience per scene from its setting (under water: muffled water, no birds; indoor: none); effects levelled under the voice |
| 4 | Text overlapping | Three text systems unaware of each other: 3D labels in the set (studio.label), the script's stickers (make_film `_overlay`), the captions ("RUBBER GASKET" as 3D label AND yellow pill; BUOYANCY over the caption) | One text owner per moment: drop a sticker that repeats an in-scene label, keep the caption zone clear of labels |
| 5 | Water looks solid | No standard water component; each set invents its own; the look repair pushed "bright blue" and made it opaque | A tested water block (clear body, visible waterline, see-through) that sets must use (studio.Reservoir / water_volume as the base) |
| 6 | Many animation issues | Max and the kids are animated with raw pose keys per scene | Drive the cutaway characters with the Quaternius mocap library (engine/mocap.py, used by the old director stage) |
| 7 | Objects such as the car exist online | The all-primitive route builds everything from boxes | Already built: `--source cutaway-bk`; untested on a new subject |
| 8 | The hook is weak | The cutaway route has no hook check (the director route had one: a vision check of the first second + re-stage) | Port the hook gate to the cutaway route |
| 9 | Not understandable overall | 1 + 4 + 8, plus the scale problem (a full-size sea tunnel beside a 1.8 m Max: Max at 14 % of the frame, labels at 1 %) | The fixes above + the human-scale gate (done, uncommitted) |

## Done (2026-10-30, uncommitted, all tests pass; Blender stills: `BLENDER_TESTS=1 pytest tests/test_blender_stills.py`)

1. Pacing: scripts are sized in seconds and converted with the voice's MEASURED pace (`stage_writer.voice_rate(route=
   "cutaway")`, recorded by make_film after every recording); Chatterbox keeps the beat pauses (speak.py turned the
   `<break>` tags into nothing) and plays at VOICE_SPEED 0.92: 3.27 -> 2.73 words/s; every beat is held until its
   action's minimum seconds (`beats.action_holds`: silence after the line, max 3 s). The tunnel narration: 56 s -> 75 s,
   every action at its minimum. Whisper's split words ("bulk heads") no longer move a cut into the pause.
2. Max never mouths the narration: `Character.talk` keeps the mouth shut; a static check rejects `lipsync` and mouth
   keys in loops (`set_builder.mouth_problems`).
3. Ambience per scene (`sfx.scene_ambience`: an action's "ambience", else read from "shows", else the set's subject):
   no birds at or under the sea; repeats of one effect within 0.5 s dropped; synthesized effects loudness-matched;
   effects ducked under the voice; two-pass loudnorm (-15 -> -14.5 LUFS on the tunnel mix).
4. One text per idea: a sticker repeating its beat's 3D label is dropped (`sets.repeats_label`, in to_film and at
   render); QA flags labels in the caption band (`text_caption`): BUOYANCY, RUBBER GASKET... on the tunnel set.
5. Hook gate: the film's first window is judged as the hook (scene review rubric, set previews and production).
6. Water: `studio.Water`, density from its own depth (see-through at any size), blue body glow, waterline strip;
   the guide and the look repair point to it.
7. Mocap: `Character.act(clip, f0, f1)`; idle / talk / walk are motion-captured, played after the scene is keyed
   around the hand keys (`character.perform_queued`, called by cutaway_film.py).
8. A set that is not fully accepted hands over its best reviewed draft (registered, warnings) instead of stopping.

Left: the first real `cutaway-bk` run on a new subject (step 5 below).

## Order of work

1. Pacing (1) and the length rule, since it affects every film.
2. Max not speaking (2), sound ambience (3), text ownership (4): small, deterministic, testable.
3. Hook gate (8).
4. Water component (5) and mocap for the cutaway characters (6): engine work, test on stills.
5. First real `cutaway-bk` run on a new subject, supervised to a finished film; if the set builder does
   not accept every scene, it should hand over its best draft with warnings instead of stopping.
