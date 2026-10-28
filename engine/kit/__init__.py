"""
The story kit: pre-built, tested 3D building blocks that a STORYBOARD (pure data, written by the
planner) drives. A video never needs new Blender code: the planner describes what happens in each
beat with the kit's vocabulary (engine/kit/vocab.py), agents/storyboard.py validates it and generates
a normal set (spec + a three-line builder), and the kit stages, animates and frames every beat.

A subject the kit cannot show is not filmed: it goes to the wishlist as a kit extension (developer
work with tests), never improvised during a run.
"""
