"""Lambda entrypoint for the extract pipeline state."""

from carethread.pipeline.extract.handler import handler

__all__ = ["handler"]
