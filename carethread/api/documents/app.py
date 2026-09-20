"""Lambda entrypoint for Documents API Function."""

from carethread.api.documents.handler import handler

__all__ = ["handler"]
