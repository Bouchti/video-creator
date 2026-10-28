"""Serializable project and shot models for the local video pipeline."""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _replace_with_retry(source: str, target: Path, attempts: int = 20, delay: float = 0.25) -> None:
    """os.replace, retried while another process briefly holds the target open.

    On Windows a rename over a file fails with "Access is denied" while any reader (a
    `status` call, an editor, antivirus, the search indexer) has it open; that hold lasts
    milliseconds, so a manifest save must wait it out instead of crashing a long run."""
    for attempt in range(attempts):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay)


class ProjectState(str, Enum):
    DRAFT = "draft"
    PLANNING = "planning"
    QUEUED = "queued"
    GENERATING = "generating"
    VALIDATING = "validating"
    ASSEMBLING = "assembling"
    RENDERING = "rendering"
    COMPLETED = "completed"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    FAILED = "failed"
    PARTIALLY_COMPLETED = "partially_completed"


@dataclass
class Shot:
    id: str
    index: int
    duration_frames: int
    prompt: str
    negative_prompt: str
    seed: int
    narration: str = ""
    ambience: str = ""
    transition: str = "cut"
    continuity: dict[str, Any] = field(default_factory=dict)
    subject_action: str = ""
    camera_action: str = ""
    # Place and light labels from the script: a shot opens on the last frame of the latest earlier
    # shot with the same pair. Empty (older projects) means it always continues the previous shot.
    scene: str = ""
    light: str = ""
    cast: list[str] = field(default_factory=list)
    status: str = "pending"
    backend: str | None = None
    attempts: list[dict[str, Any]] = field(default_factory=list)
    output: str | None = None
    last_frame: str | None = None
    validation: dict[str, Any] | None = None
    error: str | None = None
    # How the shot was salvaged when no take passed review: "best_take", "flawed_take" or "still".
    # Empty means it genuinely passed. Salvaged shots lower the final creative review's scores, and
    # a "still" shot is never reused as a continuity source (that chains push-ins of one frame).
    degraded: str = ""

    @property
    def duration_seconds(self) -> float:
        return self.duration_frames / 30.0


@dataclass
class ProjectManifest:
    id: str
    concept: str
    duration_seconds: int
    visual_style: str
    preferred_backend: str
    project_dir: str
    state: str = ProjectState.DRAFT.value
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    schema_version: int = SCHEMA_VERSION
    fps: int = 30
    width: int = 1080
    height: int = 1920
    script: dict[str, Any] = field(default_factory=dict)
    continuity: dict[str, Any] = field(default_factory=dict)
    shots: list[Shot] = field(default_factory=list)
    reference_image: str | None = None
    narration_enabled: bool = True
    voice: str = "mysterious"
    music: str = "subtle cinematic"
    ambience: str = "generated clip ambience"
    captions: dict[str, Any] = field(default_factory=lambda: {
        "enabled": True, "burn_in": True, "export_srt": True, "word_highlight": True
    })
    settings: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    active_shot: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    elapsed_seconds: float = 0.0
    error: str | None = None

    def record(self, event: str, **details: Any) -> None:
        self.events.append({"at": utc_now(), "event": event, **details})
        self.updated_at = utc_now()

    def set_state(self, state: ProjectState | str, **details: Any) -> None:
        self.state = state.value if isinstance(state, ProjectState) else str(state)
        self.record("state_changed", state=self.state, **details)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectManifest":
        allowed = {f.name for f in fields(cls)}
        values = {k: v for k, v in data.items() if k in allowed and k != "shots"}
        values["shots"] = [Shot(**row) for row in data.get("shots", [])]
        return cls(**values)

    @classmethod
    def load(cls, path: str | Path) -> "ProjectManifest":
        with Path(path).open(encoding="utf-8") as stream:
            return cls.from_dict(json.load(stream))

    def save(self, path: str | Path | None = None) -> Path:
        target = Path(path) if path else Path(self.project_dir) / "project.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        self.updated_at = utc_now()
        fd, temporary = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(self.to_dict(), stream, indent=2, ensure_ascii=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            _replace_with_retry(temporary, target)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
        return target


def completed_shots(manifest: ProjectManifest) -> int:
    return sum(shot.status == "accepted" and bool(shot.output) for shot in manifest.shots)


def estimated_remaining_seconds(manifest: ProjectManifest, default_shot_seconds: float = 360.0) -> float:
    """Remaining wall time from finished shots: every take, its review and retakes included."""
    spent = []
    for shot in manifest.shots:
        if shot.status != "accepted" or not shot.attempts:
            continue
        total = 0.0
        for attempt in shot.attempts:
            started, ended = attempt.get("started_at"), attempt.get("ended_at")
            if started is not None and ended is not None and ended > started:
                total += float(ended) - float(started)
            else:
                total += float(attempt.get("generation_seconds") or 0)
        if total > 0:
            spent.append(total)
    per_shot = sum(spent) / len(spent) if spent else default_shot_seconds
    return per_shot * (len(manifest.shots) - completed_shots(manifest))


def total_timeline_frames(manifest: ProjectManifest) -> int:
    return sum(shot.duration_frames for shot in manifest.shots)
