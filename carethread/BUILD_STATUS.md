# CareThread — Backend Implementation & Build Status

| Milestone / Prompt | Component | Status | Test Coverage | Details |
| :--- | :--- | :---: | :---: | :--- |
| **Prompt 1** | Project Skeleton & Layout | **PASS** | Manual / CLI | Standardized directory tree matching build documentation. |
| **Prompt 2** | Shared Data Contracts & Provenance Layer | **PASS** | 26/26 Tests Passed | Frozen Pydantic domain models, Draft-07 JSON schemas, 0.85 confidence gate, API request/response models. |
| **Prompt 3** | DynamoDB Single-Table Repository Layer | **PASS** | 29/29 Tests Passed | Single-table CRUD, canonical `get_patient_context()`, `Decimal` serialization, provenance integrity rejection, cross-patient isolation. |
| **Prompt 4** | Document Upload Foundation (`POST /documents`) | **PASS** | 13/13 Tests Passed | Presigned S3 PUT URL (300s expiry), `raw/<patient_id>/<doc_id>.<ext>` S3 layout, Document record (`uploading`), JWT `sub` authentication, body spoofing prevention. |
| **Prompt 5** | Ingest Pipeline & Orchestration (M1) | **NOT IMPLEMENTED YET** | - | Awaiting approval for Step Functions, rasterisation, Bedrock multimodal extraction, and bbox matching. |
| **Prompt 6** | Care Plan & Deterministic Escalations (M2) | **NOT IMPLEMENTED YET** | - | Scheduled for M2. |
| **Prompt 7** | Lab Interpreter & Substitution Check (M3, M4) | **NOT IMPLEMENTED YET** | - | Scheduled for M3, M4. |
| **Prompt 8** | Core API Handlers & End-to-End Verification | **NOT IMPLEMENTED YET** | - | Scheduled for M6. |

---

### Test Execution Summary (Current)
- **Total Test Suite:** `carethread/tests/` (68 tests)
- **Results:** **68 passed, 0 failed, 0 errors**
- **Execution Time:** ~0.35 seconds
- **AWS Integration Status:**
  - `DynamoDB Table`: **LOCAL/MOCKED** (Tested with `InMemoryPatientRepository` and `MockDynamoDBTable`)
  - `S3 Storage`: **LOCAL/MOCKED** (Tested with `InMemoryStorageService` and `MockBoto3S3Client`)
  - Real AWS Infrastructure: Declared under `carethread/infra/template.yaml` (Deployable via SAM)
