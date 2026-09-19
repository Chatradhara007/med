# CareThread — Backend Implementation & Build Status

| Milestone / Module | Component | Status | Test Coverage | Details |
| :--- | :--- | :---: | :---: | :--- |
| **Prompt 1** | Project Skeleton & Layout | **PASS** | Manual / CLI | Standardized directory tree matching build documentation. |
| **Prompt 2** | Shared Data Contracts & Provenance Layer | **PASS** | 26/26 Tests Passed | Frozen Pydantic domain models, Draft-07 JSON schemas, 0.85 confidence gate, API request/response models. |
| **Prompt 3** | DynamoDB Single-Table Repository Layer | **PASS** | 29/29 Tests Passed | Single-table CRUD, canonical `get_patient_context()`, `Decimal` serialization, provenance integrity rejection, cross-patient isolation. |
| **Prompt 4** | Document Upload Foundation (`POST /documents`) | **PASS** | 13/13 Tests Passed | Presigned S3 PUT URL (300s expiry), `raw/<patient_id>/<doc_id>.<ext>` S3 layout, Document record (`uploading`), JWT `sub` authentication, body spoofing prevention. |
| **M2** | Care Plan & Deterministic Escalations | **PASS** | 10/10 Tests Passed | 7-day multi-slot care plan (`PlanEntry`), frequency mapping, provenance inheritance, rules.yaml engine, safety dose validator, idempotency. |
| **M3** | Lab Interpreter | **PASS** | 17/17 Tests Passed | Printed report range precedence, fallback CSV repository, deterministic deviation, abnormal-first ranking, Metformin/Creatinine context cross-reading, LLM safety guardrails. |
| **M4** | Substitution Check | **PASS** | 14/14 Tests Passed | Salt-equivalent matching from `drugs.csv`, NTI hard-block (`nti.csv`), strength/form divergence flags, canonical active medication cross-check, advisory warnings. |
| **M5** | Reminders Workflow | **PASS** | 20/20 Tests Passed | EventBridge trigger, adherence suppression (`done=True`), single-table idempotency (`REMINDER#<id>`), demo mode compression (30s), safe generic SNS notifications. |
| **M1** | Ingest Pipeline & Orchestration | **NOT STARTED** | - | Awaiting Step Functions, rasterisation, Bedrock multimodal extraction, and bbox matching. |
| **M6** | Core API Handlers & End-to-End Verification | **PARTIAL** | 13/13 Tests Passed | `POST /documents`, `GET /documents/{id}` PASS. Remaining endpoints pending. |

---

### Test Execution Summary (Current)
- **Total Test Suite:** `carethread/tests/` (129 tests)
- **Results:** **129 passed, 0 failed, 0 errors**
- **Execution Time:** ~0.49 seconds
- **Dependencies (Real vs Mocked):**
  - `Curated Drug Index`: **REAL DATA** (`data/drugs.csv` with 200+ vetted bioequivalent formulations)
  - `NTI Database`: **REAL DATA** (`data/nti.csv` with 10 clinical hard-block rules)
  - `Reference Range Source`: **REAL DATA** (`data/ref_ranges.csv` with 35 biological reference intervals)
  - `Medicine OCR / Extraction`: **MOCKED** (`MockMedicineExtractionAdapter` with confidence gating)
  - `LLM Formatter`: **MOCKED** (`MockLabExplanationFormatter` and `MockLLMFormatter` with clinical safety verification)
  - `EventBridge Scheduler`: **LOCAL / MOCKED** (`MockReminderScheduler` with real adapter `EventBridgeReminderScheduler`)
  - `Amazon SNS`: **LOCAL / MOCKED** (`MockNotificationPublisher` with PHI leak detection; real adapter `SNSNotificationPublisher`)
  - `DynamoDB Table`: **LOCAL / MOCKED** (Tested with `InMemoryPatientRepository` and `MockDynamoDBTable`)
  - `S3 Storage`: **LOCAL / MOCKED** (Tested with `InMemoryStorageService` and `MockBoto3S3Client`)
  - Real AWS Infrastructure: Declared under `carethread/infra/template.yaml` (Deployable via SAM)
