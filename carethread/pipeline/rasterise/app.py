"""Lambda entrypoint for the rasterise pipeline state."""

from carethread.pipeline.rasterise.handler import handler

__all__ = ["handler"]
