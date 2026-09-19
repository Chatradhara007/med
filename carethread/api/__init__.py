"""CareThread API module exposing handlers, services, and unified router."""

from carethread.api.common.response import CORS_HEADERS, make_response, error_response
from carethread.api.documents.handler import handle_post_documents, handle_get_document
from carethread.api.documents.service import DocumentsService
from carethread.api.record.handler import handle_get_record, handle_patch_field, handle_plan_done
from carethread.api.record.service import RecordService
from carethread.api.substitution.handler import handle_post_substitution
from carethread.api.substitution.service import SubstitutionApiService
from carethread.api.router import ApiRouter, handler

__all__ = [
    "CORS_HEADERS",
    "make_response",
    "error_response",
    "handle_post_documents",
    "handle_get_document",
    "DocumentsService",
    "handle_get_record",
    "handle_patch_field",
    "handle_plan_done",
    "RecordService",
    "handle_post_substitution",
    "SubstitutionApiService",
    "ApiRouter",
    "handler",
]
