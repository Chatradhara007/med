"""Lambda entrypoint for the confidence pipeline state."""

from carethread.pipeline.confidence.handler import handler

__all__ = ["handler"]
