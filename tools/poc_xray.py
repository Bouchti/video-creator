"""
Proof of the hybrid format: 3D story footage + AI-written 2D "x-ray" diagrams for the why-steps.

    python tools/poc_xray.py                 # -> output/poc/xray_proof.mp4

Re-uses the kept 3D bike film (output/kept/20261030_bike_v1): the film whose narration explained what its
picture could not show. The AI writes a short script for that footage (hook, two why-steps, payoff), the
diagram agent writes and reviews one diagram per why-step, then voice, captions, sound and the compositor.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

from config.paths import PROJECT_ROOT  # noqa: E402

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from agents import llm, audio_fx, diagram_writer, director  # noqa: E402

KEPT = os.path.join(PROJECT_ROOT, "output", "kept", "20261030_bike_v1", "work")
WORK = os.path.join(PROJECT_ROOT, "output", "poc", "xray")
FPS = 30
FOOTAGE = {   # the kept film's 3D footage, by what it shows (frame ranges of its beauty pass)
    "hook": (1, 109, "Max's riderless bike throws sparks, tips hard and swings back upright by itself; a kid jumps"),
    "lean": (640, 790, "the bike is pushed, tips into a lean, swings back upright by itself; Max falls over in disbelief"),
    "payoff": (1474, 1612, "confetti bursts over the bike standing upright; a kid dances, Max shakes his head"),
}

SCRIPT_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["hook_text", "beats"],
                 "properties": {"hook_text": {"type": "string"}, "beats": {"type": "array", "items": {
                     "type": "object", "additionalProperties": False,
                     "required": ["id", "text", "footage", "diagram"],
                     "properties": {"id": {"type": "string"}, "text": {"type": "string"},
                                    "footage": {"type": "string", "enum": list(FOOTAGE)},
                                    "diagram": {"type": "object", "additionalProperties": False,
                                                "required": ["use", "title", "must_see", "steps"],
                                                "properties": {"use": {"type": "boolean"}, "title": {"type": "string"},
                                                               "must_see": {"type": "string"},
                                                               "steps": {"type": "array", "items": {"type": "string"}}}}}}}}}


def write_script(facts):
    system = ("You write a 20-second proof clip of a funny science short starring MAX (an over-confident handyman) "
              "and his kids. 3D footage tells the story; at each WHY step the picture turns into an animated x-ray "
              "diagram drawn over the scene. Clear for a 12-year-old: everyday words, one idea per sentence.")
    footage = "\n".join(f"- {k}: {v[2]}" for k, v in FOOTAGE.items())
    prompt = (f"FACTS (use only these):\n{facts}\n\nFOOTAGE AVAILABLE:\n{footage}\n\nWrite exactly 4 beats, 55-65 words "
              "in total: b1 hook (footage hook, <= 10 words, a deadpan surprising line; diagram.use false), b2 and b3 "
              "the two why-steps (footage lean; diagram.use true: title <= 3 words, must_see = exactly what the "
              "animated diagram shows step by step, in concrete visual terms; steps = 2-3 phrases of <= 4 words), "
              "b4 payoff (footage payoff; the key fact in one sentence a kid could repeat, then a tiny joke; "
              "diagram.use false). hook_text: <= 4 words, shocked question for the screen. The diagrams must make "
              "the why OBVIOUS without the sound.")
    return llm.ask(system, prompt, SCRIPT_SCHEMA, effort="high")


def footage_clip(beats, timing, out):
    """The kept 3D frames for each beat, trimmed or held to the beat's length, joined into one clip."""
    src = os.path.join(KEPT, "beauty.mp4")
    parts = []
    for b, t in zip(beats, timing["beats"]):
        a, z, _ = FOOTAGE[b["footage"]]
        n = t["f1"] - t["f0"] + 1
        part = os.path.join(WORK, f"seg_{b['id']}.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf",
                        f"trim=start_frame={a - 1}:end_frame={z},setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop=-1",
                        "-frames:v", str(n), "-an", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p",
                        "-r", str(FPS), part], check=True)
        parts.append(part)
    lst = os.path.join(WORK, "parts.txt")
    with open(lst, "w") as fh:
        fh.writelines(f"file '{p}'\n" for p in parts)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out],
                   check=True)


def main():
    os.makedirs(os.path.join(WORK, "public"), exist_ok=True)
    plan_path = os.path.join(WORK, "script.json")
    if os.path.isfile(plan_path):
        script = json.load(open(plan_path, encoding="utf-8"))
    else:
        kept = json.load(open(os.path.join(KEPT, "plan.json"), encoding="utf-8"))
        script = write_script("\n".join(f"- {f}" for f in kept.get("facts", [])) or kept["title"])
        json.dump(script, open(plan_path, "w", encoding="utf-8"), indent=1)
    beats = script["beats"]
    plan = {"id": "poc_xray", "world": "poc", "beats": [{"id": b["id"], "text": b["text"]} for b in beats]}
    print("SCRIPT:", *[f"[{b['id']}] {b['text']}" for b in beats], sep="\n  ")

    # voice + word timings (no 60-65 s fitting: this is a 20 s proof)
    voice = os.path.join(WORK, "voice.wav")
    if not os.path.isfile(voice):
        from agents.voice import generate_voiceover
        raw, _d = generate_voiceover(" ".join(b["text"] for b in beats), "energetic")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-ar", "44100", voice], check=True)
    from agents.voice import get_duration
    seconds = get_duration(voice) + 1.0
    timing, words = director.stage_timing(plan, voice, seconds, WORK)
    total = timing["total"]

    # the diagrams: written, typechecked, rendered and reviewed by the agent
    cues = []
    for b, t in zip(beats, timing["beats"]):
        d = b["diagram"]
        if not d.get("use"):
            continue
        spec = {"id": f"poc_{b['id']}", "title": d["title"], "must_see": d["must_see"], "narration": b["text"],
                "steps": d["steps"], "dur": t["f1"] - t["f0"] + 1,
                "cues": sorted([[fr - t["f0"], w] for w, fr in t["cues"].items()])}
        status = diagram_writer.write(spec)
        print("DIAGRAM", status)
        cues.append({"id": status["id"], "from": t["f0"], "to": t["f1"], "mode": "xray", "title": d["title"],
                     "steps": d["steps"]})

    # picture, sound, compose
    footage_clip(beats, timing, os.path.join(WORK, "public", "beauty.mp4"))
    fx = os.path.join(WORK, "fx.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t",
                    f"{total / FPS:.2f}", fx], check=True)
    track = director.music_track(plan)
    audio_fx.mix_audio(voice, fx, os.path.join(WORK, "public", "mix.m4a"), total / FPS,
                       music=track["path"] if track else None)
    props = {"fps": FPS, "width": 1080, "height": 1920, "durationInFrames": total, "video": "beauty.mp4",
             "audio": "mix.m4a", "grain": 0.03, "grade": director.GRADE,
             "words": [{"text": w["text"], "startMs": int(w["start"] * 1000), "endMs": int(w["end"] * 1000)}
                       for w in words],
             "hook": {"text": script["hook_text"], "from": 0, "to": timing["beats"][0]["f1"]},
             "diagrams": cues, "chapters": [], "labels": [], "arrows": [], "callouts": [], "punchIns": []}
    props_path = os.path.join(WORK, "props.json")
    json.dump(props, open(props_path, "w", encoding="utf-8"), indent=1)
    final = os.path.join(PROJECT_ROOT, "output", "poc", "xray_proof.mp4")
    subprocess.run([director.NPX, "remotion", "render", "src/index.ts", "Short", final, f"--props={props_path}",
                    f"--public-dir={os.path.join(WORK, 'public')}", "--codec=h264", "--crf=20", "--audio-codec=aac",
                    "--log=error"], cwd=director.COMPOSITOR, check=True)
    print("FINAL", final, f"{total / FPS:.1f}s", f"{audio_fx.loudness(final):.1f} LUFS")


if __name__ == "__main__":
    main()
