"""Cutaway Studio constants: frame rate, frame size, safe zones, brand, and where things live."""
from __future__ import annotations

import os

from config.paths import PROJECT_ROOT, get_blender

FPS = 30                               # one rate end to end: Blender frame = round(t * FPS)
WIDTH, HEIGHT = 1080, 1920             # the 9:16 master

# 1080x1920 layout bands (px from the top)
SAFE_TOP = 150                         # nothing important above (status bar, search)
SAFE_BOTTOM = 1550                     # nothing important below (caption, handle)
SAFE_RIGHT = 140                       # the action rail
MECHANISM_BAND = (450, 1250)           # the 3D subject lives here; no text over it
CAPTION_BAND = (1300, 1450)            # karaoke captions, one fixed band
HEADER_BAND = (150, 430)               # step tracker + titles once they shrink

BRAND = {
    "bg": "#0a1220",                   # dark navy
    "bg2": "#111d33",
    "cold": "#6fd3ff",
    "hot": "#ffb23e",
    "ink": "#f4f6fa",
    "muted": "#8fa3bf",
    "section": "#e0552b",              # the painted section-cut faces
    "title_font": "Anton",
    "ui_font": "Inter",
}

PKG = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(PKG, "assets")
RUNS = os.path.join(PROJECT_ROOT, "runs")
BLENDER_DIR = os.path.join(PKG, "blender")


def find_blender() -> str:
    """BLENDER_EXE, else the shared default, else the newest portable C:/blender-*/blender.exe, else PATH."""
    import glob
    import shutil
    env = os.getenv("BLENDER_EXE")
    if env and os.path.exists(env):
        return env
    default = get_blender()
    if os.path.exists(default):
        return default
    portable = sorted(glob.glob(r"C:\blender-*\blender.exe"))
    if portable:
        return portable[-1]
    return shutil.which("blender") or default


BLENDER = find_blender()


def run_dir(slug: str) -> str:
    return os.path.join(RUNS, slug)


def frame_of(t: float) -> int:
    """The Blender frame shown at video time t (frame 1 is t = 0)."""
    return int(round(t * FPS)) + 1
