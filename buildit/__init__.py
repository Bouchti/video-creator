"""
Build-It Studio: fully automatic "build the machine from a simple analogy" explainers (1080x1920, 30 fps).

    python -m buildit                              # picks a trending machine topic the kit can build
    python -m buildit "How a refrigerator works"   # your topic
    python -m buildit <slug> --from compose        # resume a stage
    python -m buildit review <slug>                # contact sheet next to refs/frames + rubric

Look and storytelling: docs/style_guide.md (from refs/). Blender renders the 3D from a storyboard written in the
machine kit's vocabulary (buildit/kit/vocab.py); HyperFrames adds word-pop captions, label pills and the mix.

Settings (environment):
  BUILDIT_VOICE        chatterbox (default: local, clones voice/reference.wav) | pipeline (agents.voice)
  BUILDIT_LANG         en (default) | fr  (fr uses Chatterbox Multilingual and voice/reference_fr.wav)
  BUILDIT_WORKERS      Blender processes rendering shots in parallel (default 2)
"""
