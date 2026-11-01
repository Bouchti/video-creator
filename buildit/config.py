"""Constants and paths for Build-It Studio (pure Python; the Blender side has its own copies where needed)."""
from __future__ import annotations

import os

from cutaway.config import BLENDER  # noqa: F401  (the same Blender install finder)

FPS = 30
W, H = 1080, 1920
SAFE_TOP, SAFE_BOTTOM, SAFE_RIGHT = 150, 1550, 140
CAPTION_Y = (1470, 1590)            # word-pop captions band, under the subject, above the app's bottom UI
SUBJECT_BAND = (200, 1440)          # where the machine sits: big, above the captions (blender/build_scene.BAND)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.join(PKG, "blender")
ASSETS = os.path.join(PKG, "assets")
RUNS = os.path.join(ROOT, "runs", "buildit")
REFS = os.path.join(ROOT, "refs")
VOICE_REF = {"en": os.path.join(ROOT, "voice", "reference_energetic.wav"),     # upbeat narrator (Nov 1)
             "fr": os.path.join(ROOT, "voice", "reference_fr.wav")}

# the reference palette (docs/style_guide.md)
PALETTE = {
    "wall_top": "#beb4ab", "wall_low": "#938980", "floor": "#8c7b66", "floor_far": "#74614e",
    "paint": "#b8141c", "glow": "#ffb060", "ink": "#ffffff", "outline": "#1d1712",
    "pill": "#ffffff", "pill_ink": "#1d1712", "warn": "#f26b1d", "warn_bg": "#fff1e2",
    "air": "#2f7fd8", "air_bg": "#e6f2ff", "done": "#1f9d55", "done_bg": "#e7f8ee", "chip": "#1d1712",
}
