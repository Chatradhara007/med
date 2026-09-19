"""Lambda entrypoint for Record API Function."""

from carethread.api.record.handler import handler

__all__ = ["handler"]
