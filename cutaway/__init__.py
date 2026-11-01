"""
Cutaway Studio: a topic in, a 60-75 s vertical 3D cutaway explainer out.

Blender (headless, scripted) renders the hero 3D shots; HyperFrames composites them with word-timed captions,
anchored callouts, titles, the grade and the sound mix. Every stage reads and writes runs/<slug>/.

    python -m cutaway make "How a car engine works" --length 70 --draft
    python -m cutaway make <slug> --from compose
    python -m cutaway review <slug>

This package is separate from the Max story pipeline (main.py, engine/, agents/showrunner.py): it only imports
shared helpers (config.paths, agents.voice, agents.llm) and never changes them.
"""
