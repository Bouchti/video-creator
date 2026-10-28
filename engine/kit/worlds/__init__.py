"""
Kit worlds beyond the hand-built embankment (engine/kit/embankment.py). Each world is three files, made once
by agents/kit_world.py when a topic needs a world the kit does not have, then reused by every storyboard:

    engine/kit/worlds/<world>_vocab.py     pure data: what can be built and what can happen (generated)
    engine/kit/worlds/<world>_objects.py   one tested builder function per object the world needs
    engine/kit/worlds/<world>.py           the staging class that films any valid storyboard in that world

A world is listed in REGISTERED only after its objects and its staging passed the measured gates.
"""

REGISTERED = []          # worlds built by agents/kit_world.py and verified (the embankment is always there)
