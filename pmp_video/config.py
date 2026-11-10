"""Brand, paths and format settings for the PMP Exam Lab pipeline (env vars override the defaults)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
ASSETS = PACKAGE_DIR / "assets"

HYPERFRAMES_VERSION = os.getenv("PMP_HYPERFRAMES_VERSION", "0.9.5")
SITE = os.getenv("PMP_SITE_URL", "https://pmpexamlab.com")
SITE_LABEL = "pmpexamlab.com"
CHANNEL = "PMP Exam Lab"
TAGLINE = "Think like PMI. Pass the 2026 PMP."
TRADEMARK = ("PMP, PMBOK and PMI are registered marks of the Project Management Institute, Inc. "
             "This channel is not affiliated with or endorsed by PMI.")

# Brand tokens taken from pmpexamlab.com (apps/web) so the videos match the product.
BRAND = {
    "ground": "#0A1A2F",
    "ground_2": "#10314F",
    "panel": "#0F2740",
    "line": "#1E4A70",
    "ink": "#FFFFFF",
    "muted": "#94A3B8",
    "sky": "#38BDF8",
    "sky_soft": "#7DD3FC",
    "brand": "#0369A1",
    "good": "#22C55E",
    "bad": "#F43F5E",
    "warn": "#F59E0B",
}

DOMAIN_LABEL = {"people": "People", "process": "Process", "business": "Business Environment"}


def output_root() -> Path:
    path = Path(os.getenv("PMP_OUTPUT_DIR") or PROJECT_ROOT / "output" / "pmp")
    path.mkdir(parents=True, exist_ok=True)
    return path


def question_bank_path() -> Path:
    """The pmp-simulator question export. PMP_QUESTION_BANK overrides; the default is the sibling repo."""
    env = os.getenv("PMP_QUESTION_BANK")
    if env:
        return Path(env).expanduser()
    return PROJECT_ROOT.parent / "pmp-simulator" / "content" / "questions_export.json"


@dataclass(frozen=True)
class Shape:
    name: str
    width: int
    height: int
    caption_words: int      # words per caption group (shorts read word by word, long reads in phrases)

    @property
    def portrait(self) -> bool:
        return self.height > self.width


SHORT = Shape("short", 1080, 1920, 3)
LONG = Shape("long", 1920, 1080, 7)

# Series names match the channel plan (playlist per series) and feed the UTM campaign tag.
FORMATS = {
    "question": {"shape": SHORT, "series": "Scenario in 60", "campaign": "scenario-in-60"},
    "trap": {"shape": SHORT, "series": "Exam Traps", "campaign": "exam-traps"},
    "term": {"shape": SHORT, "series": "Term Clash", "campaign": "term-clash"},
    "mindset": {"shape": SHORT, "series": "PMI Mindset", "campaign": "pmi-mindset"},
    "walkthrough": {"shape": LONG, "series": "Exam Room", "campaign": "exam-room"},
    "course": {"shape": LONG, "series": "PMP Course", "campaign": "pmp-course"},
}

PAUSE_SECONDS = float(os.getenv("PMP_PAUSE_SECONDS", "5"))
GAP_SECONDS = 0.25          # breath between narrated beats
SCENE_TAIL = 0.45           # hold at the end of a scene before the cut


def utm(campaign: str, slug: str, medium: str = "video") -> str:
    return f"{SITE}/?utm_source=youtube&utm_medium={medium}&utm_campaign={campaign}&utm_content={slug}"
