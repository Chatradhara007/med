"""Unit tests for CareThread document upload foundation.

Verifies:
1. POST /documents endpoint flow
2. Authentication extraction from JWT sub claim (rejection of unauthorized calls)
3. Security rule: client-supplied patient_id in body cannot override JWT identity
4. Deterministic S3 object key convention: raw/<patient_id>/<doc_id>.<ext>
5. Presigned URL generation with 300-second expiration
6. Document entity creation with initial status 'uploading'
7. GET /documents/{id} retrieval of initial status
"""

import json
import pytest

from carethread.shared.schemas.document import DocumentStatus, DocumentType
from carethread.shared.schemas.api import DocumentCreateRequest
from carethread.shared.repository.in_memory import InMemoryPatientRepository
from carethread.shared.storage.in_memory import InMemoryStorageService
from carethread.shared.storage.s3 import S3StorageService
from carethread.shared.auth.extractor import extract_patient_id
from carethread.shared.auth.interfaces import UnauthorizedError
from carethread.api.documents.service import DocumentsService
from carethread.api.documents.handler import handler


# --- Mock S3 Client for testing S3StorageService ---
class MockBoto3S3Client:
    def __init__(self):
        self.presigned_calls = []

    def generate_presigned_url(self, ClientMethod, Params, ExpiresIn):
        self.presigned_calls.append({
            "ClientMethod": ClientMethod,
            "Params": Params,
            "ExpiresIn": ExpiresIn,
        })
        bucket = Params["Bucket"]
        key = Params["Key"]
        return f"https://{bucket}.s3.amazonaws.com/{key}?X-Amz-Expires={ExpiresIn}"


# ==================================================
# 1. STORAGE SERVICE TESTS
# ==================================================

def test_s3_key_convention():
    """Verify exact S3 key format per Section 4.2: raw/<patient_id>/<doc_id>.<ext>."""
    storage = InMemoryStorageService(bucket_name="test-bucket")
    
    key_pdf = storage.get_s3_key("pat_001", "d_123", "discharge.pdf")
    assert key_pdf == "raw/pat_001/d_123.pdf"

    key_png = storage.get_s3_key("pat_001", "d_124", "scan.png")
    assert key_png == "raw/pat_001/d_124.png"

    # Fallback to MIME if no extension in filename
    key_mime = storage.get_s3_key("pat_001", "d_125", "uploaded_file", content_type="application/pdf")
    assert key_mime == "raw/pat_001/d_125.pdf"


def test_s3_storage_service_presigned_url():
    """Verify S3StorageService invokes boto3 with put_object and 300s expiry."""
    mock_s3 = MockBoto3S3Client()
    storage = S3StorageService(bucket_name="carethread-docs-12345", s3_client=mock_s3)

    s3_key, url = storage.generate_upload_url(
        patient_id="pat_999",
        doc_id="d_001",
        filename="discharge_summary.pdf",
        content_type="application/pdf",
        expires_in=300
    )

    assert s3_key == "raw/pat_999/d_001.pdf"
    assert "carethread-docs-12345.s3.amazonaws.com/raw/pat_999/d_001.pdf" in url
    assert len(mock_s3.presigned_calls) == 1
    call = mock_s3.presigned_calls[0]
    assert call["ClientMethod"] == "put_object"
    assert call["ExpiresIn"] == 300
    assert call["Params"]["Bucket"] == "carethread-docs-12345"
    assert call["Params"]["Key"] == "raw/pat_999/d_001.pdf"
    assert call["Params"]["ContentType"] == "application/pdf"


# ==================================================
# 2. AUTHENTICATION CLAIM EXTRACTION TESTS
# ==================================================

def test_extract_patient_id_http_api_jwt():
    """Extract patient identity from HTTP API JWT Authorizer sub claim."""
    event = {
        "requestContext": {
            "authorizer": {
                "jwt": {
                    "claims": {
                        "sub": "pat_jwt_123"
                    }
                }
            }
        }
    }
    assert extract_patient_id(event) == "pat_jwt_123"


def test_extract_patient_id_rest_api_cognito():
    """Extract patient identity from REST API Cognito Authorizer sub claim."""
    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "pat_cognito_456"
                }
            }
        }
    }
    assert extract_patient_id(event) == "pat_cognito_456"


def test_extract_patient_id_missing_raises_unauthorized():
    """Missing auth context must raise UnauthorizedError."""
    event = {"requestContext": {}}
    with pytest.raises(UnauthorizedError):
        extract_patient_id(event, allow_mock=False)


def test_extract_patient_id_mock_header_when_allowed():
    """Mock header allowed only when testing adapter is explicitly enabled."""
    event = {"headers": {"X-Patient-Id": "pat_mock_789"}}
    assert extract_patient_id(event, allow_mock=True) == "pat_mock_789"

    # Must fail if allow_mock=False
    with pytest.raises(UnauthorizedError):
        extract_patient_id(event, allow_mock=False)


# ==================================================
# 3. DOCUMENTS DOMAIN SERVICE TESTS
# ==================================================

def test_documents_service_create_document():
    repo = InMemoryPatientRepository()
    storage = InMemoryStorageService(bucket_name="test-docs")
    service = DocumentsService(repository=repo, storage=storage)

    req = DocumentCreateRequest(filename="hospital_discharge.pdf", content_type="application/pdf")
    res = service.create_document(patient_id="pat_001", request=req)

    assert res.doc_id.startswith("d_")
    assert "test-docs.s3.amazonaws.com" in res.upload_url
    assert f"raw/pat_001/{res.doc_id}.pdf" in res.upload_url

    # Check DynamoDB repository persistence
    saved_doc = repo.get_document("pat_001", res.doc_id)
    assert saved_doc is not None
    assert saved_doc.patient_id == "pat_001"
    assert saved_doc.doc_id == res.doc_id
    assert saved_doc.status == DocumentStatus.UPLOADING
    assert saved_doc.s3_key == f"raw/pat_001/{res.doc_id}.pdf"


# ==================================================
# 4. API HANDLER TESTS (END-TO-END UPLOAD FOUNDATION)
# ==================================================

@pytest.fixture
def test_service():
    repo = InMemoryPatientRepository()
    storage = InMemoryStorageService(bucket_name="carethread-docs-test")
    return DocumentsService(repository=repo, storage=storage)


def test_post_documents_success(test_service):
    """POST /documents returns 201 with doc_id and upload_url."""
    event = {
        "httpMethod": "POST",
        "requestContext": {
            "authorizer": {
                "jwt": {
                    "claims": {"sub": "pat_auth_001"}
                }
            }
        },
        "body": json.dumps({
            "filename": "discharge_summary.pdf",
            "content_type": "application/pdf"
        })
    }

    resp = handler(event=event, service=test_service)
    assert resp["statusCode"] == 201
    body = json.loads(resp["body"])
    assert "doc_id" in body
    assert "upload_url" in body
    assert "carethread-docs-test.s3.amazonaws.com" in body["upload_url"]

    # Verify Document persisted in repository
    doc = test_service.repo.get_document("pat_auth_001", body["doc_id"])
    assert doc is not None
    assert doc.status == DocumentStatus.UPLOADING


def test_post_documents_unauthorized(test_service):
    """POST /documents without auth returns 401."""
    event = {
        "httpMethod": "POST",
        "requestContext": {},
        "body": json.dumps({
            "filename": "discharge_summary.pdf",
            "content_type": "application/pdf"
        })
    }
    resp = handler(event=event, service=test_service)
    assert resp["statusCode"] == 401
    body = json.loads(resp["body"])
    assert "error" in body


def test_post_documents_security_body_patient_id_ignored(test_service):
    """CRITICAL SECURITY TEST: Client-supplied patient_id in body is completely ignored.
    The document MUST be registered under the authenticated JWT sub identity."""
    attacker_payload = {
        "filename": "discharge.pdf",
        "content_type": "application/pdf",
        "patient_id": "VICTIM_PATIENT_ID"  # Spoofed!
    }
    event = {
        "httpMethod": "POST",
        "requestContext": {
            "authorizer": {
                "jwt": {
                    "claims": {"sub": "LEGITIMATE_AUTHENTICATED_PATIENT"}
                }
            }
        },
        "body": json.dumps(attacker_payload)
    }

    resp = handler(event=event, service=test_service)
    assert resp["statusCode"] == 201
    body = json.loads(resp["body"])
    doc_id = body["doc_id"]

    # Document must exist under the authenticated user
    doc = test_service.repo.get_document("LEGITIMATE_AUTHENTICATED_PATIENT", doc_id)
    assert doc is not None
    assert doc.patient_id == "LEGITIMATE_AUTHENTICATED_PATIENT"

    # Victim's partition must NOT have this document
    victim_doc = test_service.repo.get_document("VICTIM_PATIENT_ID", doc_id)
    assert victim_doc is None


def test_post_documents_malformed_body(test_service):
    """POST /documents with missing filename returns 400."""
    event = {
        "httpMethod": "POST",
        "requestContext": {
            "authorizer": {
                "jwt": {
                    "claims": {"sub": "pat_001"}
                }
            }
        },
        "body": json.dumps({"content_type": "application/pdf"})  # Missing filename
    }
    resp = handler(event=event, service=test_service)
    assert resp["statusCode"] == 400


def test_get_document_status_flow(test_service):
    """POST /documents creates document in uploading status; GET /documents/{id} retrieves it."""
    post_event = {
        "httpMethod": "POST",
        "requestContext": {
            "authorizer": {
                "jwt": {
                    "claims": {"sub": "pat_flow_001"}
                }
            }
        },
        "body": json.dumps({
            "filename": "lab_report.pdf",
            "content_type": "application/pdf"
        })
    }
    post_resp = handler(event=post_event, service=test_service)
    doc_id = json.loads(post_resp["body"])["doc_id"]

    # Now query status via GET /documents/{id}
    get_event = {
        "httpMethod": "GET",
        "requestContext": {
            "authorizer": {
                "jwt": {
                    "claims": {"sub": "pat_flow_001"}
                }
            }
        },
        "pathParameters": {"id": doc_id}
    }
    get_resp = handler(event=get_event, service=test_service)
    assert get_resp["statusCode"] == 200
    status_body = json.loads(get_resp["body"])
    assert status_body["doc_id"] == doc_id
    assert status_body["status"] == DocumentStatus.UPLOADING
    assert status_body["pages"] == []


def test_get_document_status_not_found(test_service):
    """GET /documents/{id} for non-existent document returns 404."""
    get_event = {
        "httpMethod": "GET",
        "requestContext": {
            "authorizer": {
                "jwt": {
                    "claims": {"sub": "pat_001"}
                }
            }
        },
        "pathParameters": {"id": "non_existent_doc"}
    }
    get_resp = handler(event=get_event, service=test_service)
    assert get_resp["statusCode"] == 404


def test_delete_document_success(test_service):
    """DELETE /documents/{id} successfully deletes document."""
    # 1. Register a document
    create_req = DocumentCreateRequest(filename="doc_to_delete.pdf", content_type="application/pdf")
    created = test_service.create_document("pat_del_01", create_req)
    doc_id = created.doc_id

    # 2. DELETE /documents/{id}
    del_event = {
        "httpMethod": "DELETE",
        "requestContext": {
            "authorizer": {
                "jwt": {
                    "claims": {"sub": "pat_del_01"}
                }
            }
        },
        "pathParameters": {"id": doc_id}
    }
    del_resp = handler(event=del_event, service=test_service)
    assert del_resp["statusCode"] == 200
    assert json.loads(del_resp["body"])["status"] == "deleted"

    # 3. Verify it is now 404
    get_event = {
        "httpMethod": "GET",
        "requestContext": {
            "authorizer": {
                "jwt": {
                    "claims": {"sub": "pat_del_01"}
                }
            }
        },
        "pathParameters": {"id": doc_id}
    }
    get_resp = handler(event=get_event, service=test_service)
    assert get_resp["statusCode"] == 404
