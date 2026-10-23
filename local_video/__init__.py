"""Durable local AI-video production pipeline.

The package is intentionally independent of any one ComfyUI workflow.  Backend
adapters turn a :class:`ProjectManifest` shot into a clip; the queue, validation
and assembly layers own everything around generation.
"""

from .models import ProjectManifest, ProjectState, Shot

__all__ = ["ProjectManifest", "ProjectState", "Shot"]
