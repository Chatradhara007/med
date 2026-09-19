"""Unified router dispatching API Gateway events to domain handlers."""

import logging
import re
from typing import Any, Dict, Optional

from carethread.shared.repository.interfaces import PatientRepositoryInterface
from carethread.shared.storage.interfaces import StorageServiceInterface
from carethread.api.common.response import make_response, error_response
from carethread.api.documents.handler import handle_post_documents, handle_get_document
from carethread.api.documents.service import DocumentsService
from carethread.api.record.handler import handle_get_record, handle_patch_field, handle_plan_done
from carethread.api.record.service import RecordService
from carethread.api.substitution.handler import handle_post_substitution
from carethread.api.substitution.service import SubstitutionApiService
from carethread.api.workflows.handler import handle_generate_plan, handle_interpret_labs

logger = logging.getLogger(__name__)


class ApiRouter:
    """Dispatches API Gateway HTTP requests to corresponding domain handlers."""

    def __init__(
        self,
        repository: Optional[PatientRepositoryInterface] = None,
        storage: Optional[StorageServiceInterface] = None,
    ) -> None:
        self.repo = repository
        self.storage = storage

    def route(self, event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
        """Inspect HTTP method and path, dispatching to matching handler."""
        http_method = (
            event.get("httpMethod")
            or event.get("requestContext", {}).get("http", {}).get("method", "GET")
        )
        http_method = http_method.upper()

        path = (
            event.get("rawPath")
            or event.get("path")
            or event.get("requestContext", {}).get("http", {}).get("path", "")
        )

        if http_method == "OPTIONS":
            return make_response(200, {"status": "ok"})

        # Initialize services if custom repo/storage injected
        doc_service = (
            DocumentsService(repository=self.repo, storage=self.storage)
            if self.repo and self.storage
            else None
        )
        record_service = RecordService(repository=self.repo) if self.repo else None
        sub_service = SubstitutionApiService(repository=self.repo) if self.repo else None

        # 1. /documents routes
        if path == "/documents" and http_method == "POST":
            if doc_service is None:
                from carethread.shared.repository import get_repository
                from carethread.shared.storage import get_storage_service
                doc_service = DocumentsService(repository=get_repository(), storage=get_storage_service())
            return handle_post_documents(event, doc_service)

        doc_match = re.match(r"^/documents/([^/]+)$", path)
        if doc_match and http_method == "GET":
            if not event.get("pathParameters"):
                event["pathParameters"] = {"id": doc_match.group(1)}
            if doc_service is None:
                from carethread.shared.repository import get_repository
                from carethread.shared.storage import get_storage_service
                doc_service = DocumentsService(repository=get_repository(), storage=get_storage_service())
            return handle_get_document(event, doc_service)

        # 2. /record routes
        if path == "/record" and http_method == "GET":
            if record_service is None:
                from carethread.shared.repository import get_repository
                record_service = RecordService(repository=get_repository())
            return handle_get_record(event, record_service)

        patch_match = re.match(r"^/record(?:/([^/]+))?$", path)
        if patch_match and http_method == "PATCH":
            field_name = patch_match.group(1)
            if field_name:
                if not event.get("pathParameters"):
                    event["pathParameters"] = {}
                event["pathParameters"]["field"] = field_name
            if record_service is None:
                from carethread.shared.repository import get_repository
                record_service = RecordService(repository=get_repository())
            return handle_patch_field(event, record_service)

        # 3. /plan/{day}/{slot}/done
        plan_done_match = re.match(r"^/plan/([^/]+)/([^/]+)/done$", path)
        if plan_done_match and http_method == "POST":
            if not event.get("pathParameters"):
                event["pathParameters"] = {}
            event["pathParameters"]["day"] = plan_done_match.group(1)
            event["pathParameters"]["slot"] = plan_done_match.group(2)
            if record_service is None:
                from carethread.shared.repository import get_repository
                record_service = RecordService(repository=get_repository())
            return handle_plan_done(event, record_service)

        # 4. /substitution route
        if path == "/substitution" and http_method == "POST":
            if sub_service is None:
                from carethread.shared.repository import get_repository
                sub_service = SubstitutionApiService(repository=get_repository())
            return handle_post_substitution(event, sub_service)

        # 5. Workflows
        if path == "/plan/generate" and http_method == "POST":
            from carethread.modules.care_plan.service import CarePlanService
            care_service = CarePlanService(repository=self.repo) if self.repo else None
            return handle_generate_plan(event, service=care_service)

        if path == "/labs/interpret" and http_method == "POST":
            from carethread.modules.lab_interpreter.service import LabInterpreterService
            lab_service = LabInterpreterService(repository=self.repo) if self.repo else None
            return handle_interpret_labs(event, service=lab_service)

        # A known path reached with the wrong verb is 405, not 404 -- the
        # resource exists, the method does not.
        allowed = self._allowed_methods(path)
        if allowed:
            return error_response(
                405,
                "METHOD_NOT_ALLOWED",
                f"Method {http_method} is not allowed on {path}",
                headers={"Allow": ",".join(sorted(allowed | {"OPTIONS"}))},
            )

        return error_response(404, "NOT_FOUND", f"Cannot {http_method} {path}")

    @staticmethod
    def _allowed_methods(path: str) -> set:
        """Methods this API exposes on the given path, if any."""
        routes = [
            (r"^/documents$", {"POST"}),
            (r"^/documents/[^/]+$", {"GET"}),
            (r"^/record$", {"GET", "PATCH"}),
            (r"^/record/[^/]+$", {"PATCH"}),
            (r"^/plan/generate$", {"POST"}),
            (r"^/plan/[^/]+/[^/]+/done$", {"POST"}),
            (r"^/substitution$", {"POST"}),
            (r"^/labs/interpret$", {"POST"}),
        ]
        for pattern, methods in routes:
            if re.match(pattern, path):
                return methods
        return set()


def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Unified entrypoint for API Gateway."""
    router = ApiRouter()
    return router.route(event, context)
