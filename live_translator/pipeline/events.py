"""Signal/event definitions for pipeline communication."""

from __future__ import annotations

from enum import Enum, auto

__all__ = ["PipelineStatus"]


class PipelineStatus(Enum):
    """Pipeline lifecycle states."""

    IDLE = auto()
    STREAMING = auto()
    PAUSED = auto()
    ERROR = auto()
