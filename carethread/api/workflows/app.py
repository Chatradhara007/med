"""Lambda entrypoint for Workflows API Function."""

from carethread.api.workflows.handler import handler

__all__ = ["handler"]
