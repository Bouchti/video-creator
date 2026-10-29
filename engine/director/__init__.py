"""
Director: the redesigned Blender route (docs/REDESIGN.md).

A film is DATA (a plan: beats, shots, labels) rendered by tested code:
  lib.py      assets (ambientCG / Poly Haven / Kenney / Quaternius), the look, easing, camera, anchors
  septic.py   the golden septic-system world: its parts and the shot for every beat
  blender_job.py  runs inside Blender: build the world from a job file, export anchors, render frames
Text never lives in 3D: Blender exports the 2D screen position of named anchors per frame and the
Remotion compositor (compositor/) draws labels, captions and titles on top.
"""
