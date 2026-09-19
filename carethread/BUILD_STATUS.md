# CareThread — Backend Implementation & Build Status

| Milestone / Prompt | Component | Status | Test Coverage | Details |
| :--- | :--- | :---: | :---: | :--- |
| **Prompt 1** | Project Skeleton & Layout | **PASS** | Manual / CLI | Standardized directory tree matching build documentation. |
| **Prompt 2** | Shared Data Contracts & Provenance Layer | **PASS** | 26/26 Tests Passed | Frozen Pydantic domain models, Draft-07 JSON schemas, 0.85 confidence gate, API request/response models. |
| **Prompt 3** | DynamoDB Single-Table Repository Layer | **PASS** | 29/29 Tests Passed | Single-table CRUD, canonical `get_patient_context()`, `Decimal` serialization, provenance integrity rejection, cross-patient isolation. |
| **Prompt 4** | Document Upload Foundation (`POST /documents`) | **PASS** | 13/13 Tests Passed | Presigned S3 PUT URL (300s expiry), `raw/<patient_id>/<doc_id>.<ext>` S3 layout, Document record (`uploading`), JWT `sub` authentication, body spoofing prevention. |
| **M2** | Care Plan & Deterministic Escalations | **PASS** | 10/10 Tests Passed | 7-day multi-slot care plan (`PlanEntry`), frequency mapping, provenance inheritance, rules.yaml engine, safety dose validator, idempotency. |
| **M1** | Ingest Pipeline & Orchestration | **NOT IMPLEMENTED YET** | - | Awaiting Step Functions, rasterisation, Bedrock multimodal extraction, and bbox matching. |
| **M3** | Lab Interpreter | **NOT IMPLEMENTED YET** | - | Scheduled for M3. |
| **M4** | Substitution Check | **NOT IMPLEMENTED YET** | - | Scheduled for M4. |
| **M5** | Reminders | **NOT IMPLEMENTED YET** | - | Scheduled for M5. |
| **M6** | Core API Handlers & End-to-End Verification | **NOT IMPLEMENTED YET** | - | Scheduled for M6. |

---

### Test Execution Summary (Current)
- **Total Test Suite:** `carethread/tests/` (78 tests)
- **Results:** **78 passed, 0 failed, 0 errors**
- **Execution Time:** ~0.37 seconds
- **AWS Integration Status:**
  - `DynamoDB Table`: **LOCAL/MOCKED** (Tested with `InMemoryPatientRepository` and `MockDynamoDBTable`)
  - `S3 Storage`: **LOCAL/MOCKED** (Tested with `InMemoryStorageService` and `MockBoto3S3Client`)
  - `LLM Formatter`: **MOCKED** (`MockLLMFormatter` with clinical safety verification)
  - Real AWS Infrastructure: Declared under `carethread/infra/template.yaml` (Deployable via SAM)
