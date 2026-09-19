"""Lambda entrypoint for the validate pipeline state."""

from carethread.pipeline.validate.handler import handler

__all__ = ["handler"]
