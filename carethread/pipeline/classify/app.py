"""Lambda entrypoint for the classify pipeline state."""

from carethread.pipeline.classify.handler import handler

__all__ = ["handler"]
