"""Lambda entrypoint for Substitution API Function."""

from carethread.api.substitution.handler import handler

__all__ = ["handler"]
