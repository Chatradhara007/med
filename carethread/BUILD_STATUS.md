# CareThread — Backend Implementation & Build Status

## Module status

| Milestone / Module | Component | Status | Details |
| :--- | :--- | :---: | :--- |
| **Prompt 1** | Project Skeleton & Layout | **PASS** | Standardised directory tree matching the build documentation. |
| **Prompt 2** | Shared Data Contracts & Provenance Layer | **PASS** | Frozen Pydantic domain models, Draft-07 JSON schemas, 0.85 confidence gate, API request/response models. |
| **Prompt 3** | DynamoDB Single-Table Repository Layer | **PASS** | Single-table CRUD, canonical `get_patient_context()`, `Decimal` serialisation, provenance integrity rejection, cross-patient isolation, paginated reads. |
| **Prompt 4** | Document Upload Foundation (`POST /documents`) | **PASS** | Presigned S3 PUT URL (300s expiry), `raw/<patient_id>/<doc_id>.<ext>` layout, `uploading` status, JWT `sub` authentication, body spoofing prevention. |
| **M1** | Ingest Pipeline & Orchestration | **PASS** | Step Functions state machine, rasterisation, Bedrock multimodal classification and extraction, self-correcting validate loop, confidence gating, entity persistence. |
| **M2** | Care Plan & Deterministic Escalations | **PASS** | 7-day multi-slot plan, frequency mapping, provenance inheritance, `rules.yaml` engine, safety dose validator, idempotency. |
| **M3** | Lab Interpreter | **PASS** | Printed-range precedence, fallback CSV repository, deterministic deviation, abnormal-first ranking, cross-reading, LLM safety guardrails. |
| **M4** | Substitution Check | **PASS** | Salt-equivalent matching, NTI hard-block, strength/form divergence flags, active medication cross-check, advisory warnings. |
| **M5** | Reminders Workflow | **PASS** | EventBridge Scheduler, adherence suppression, single-table idempotency, demo-mode compression, PHI-free notifications. |
| **M10** | Complete REST API & Unified Router | **PASS** | All eight endpoints, strict CORS, allowlists, structured error shape, 405 handling. |

## Test suite

```
python3 -m pip install -r requirements-dev.txt
python3 -m pytest carethread/tests -q
```

**231 passed** — 155 module/API tests, 29 ingest-pipeline tests, 25 hardening
regression tests, 22 frontend-wiring tests.

## Real vs mocked dependencies

Every AWS-backed dependency is **real by default**. Mocks are opt-in through an
environment variable and are *refused outright* inside a deployed Lambda
(detected via `AWS_LAMBDA_FUNCTION_NAME`), so a deployed function can never
silently serve fixture data.

| Dependency | Deployed behaviour | Local opt-out |
| :--- | :--- | :--- |
| DynamoDB single table | `DynamoDBPatientRepository` | `USE_IN_MEMORY_REPO=true` |
| S3 documents | `S3StorageService` (presigned PUT, SSE-AES256) | `USE_IN_MEMORY_STORAGE=true` |
| Cognito JWT auth | `requestContext.authorizer.jwt.claims.sub` | `ALLOW_MOCK_AUTH=true` (ignored in Lambda) |
| Bedrock classify / extract | `BedrockClient` (multimodal, temperature 0) | `USE_MOCK_BEDROCK=true` |
| Medicine strip extraction | `BedrockMedicineExtractionAdapter` | `USE_MOCK_EXTRACTION=true` |
| Care plan / lab wording | `BedrockLLMFormatter`, `BedrockLabExplanationFormatter` | `USE_DETERMINISTIC_FORMATTER=true` |
| EventBridge Scheduler | `EventBridgeReminderScheduler` | `USE_MOCK_AWS=true` |
| Amazon SNS | `SNSNotificationPublisher` | `USE_MOCK_AWS=true` |
| Drug index / NTI / reference ranges | **Real curated CSV data** — no mock path | — |

## Defects fixed in this pass

### Deployment blockers
1. **Lambda packaging was broken for every function.** `CodeUri` pointed at a
   single handler directory while `app.py` imported `carethread.*`, so every
   function would have failed at import. All functions now package the
   repository root with fully-qualified handler paths.
2. **The template referenced files that did not exist**: `pipeline/rasterise/`,
   `pipeline/statemachine/ingest_pipeline.asl.json`, and `app.py` in each
   pipeline directory. The stack could not deploy.
3. **No dependency manifest.** Added `requirements.txt` / `requirements-dev.txt`.
4. **Missing `__init__.py`** across `pipeline/`, `modules/`, `api/*` and `tests/`.
5. **`POST /plan/generate` and `POST /labs/interpret`** were in the API contract
   but had no deployed function. Added `WorkflowsApiFn`.
6. **EventBridge Scheduler had no IAM role** to invoke the reminder function,
   and no schedule group.

### Correctness
7. **`test_api.py` did not import `Any`** — the whole suite failed to collect,
   so the previously reported "155 passed" could not have been produced.
8. **DynamoDB reads never paginated.** Every `query()` ignored
   `LastEvaluatedKey`, so a patient whose partition exceeds one 1 MB page would
   silently receive a truncated canonical record.
9. **`RecordService` reached into `repo._table`**, bypassing the repository
   contract and rewriting whole items. Replaced with
   `update_entity_field()`, a targeted `UpdateExpression` write.
10. **A known path with the wrong verb returned 404** instead of 405.
11. **Reminder slots in the past were only corrected for day 0**, so a plan
    generated late scheduled reminders into the past.

### Security and safety
12. **The reminder Lambda defaulted to mocks in production.** `USE_REAL_AWS`
    defaulted to `false` and the template never set it, so the deployed
    function read an empty in-memory table and published nothing — while
    looking healthy in CloudWatch. Real AWS is now the default.
13. **Fabricated AWS identifiers** (`123456789012`) were hardcoded as defaults
    for the SNS topic, the scheduler target and the scheduler role, and the
    notification destination was built from one. Schedules created against them
    would be accepted and then never fire. All removed; missing configuration
    now fails loudly.
14. **Environment variable mismatch**: the template set `SNS_TOPIC_ARN` while
    the publisher read `REMINDER_SNS_TOPIC_ARN`; the reminder handler defaulted
    `TABLE_NAME` to `carethread-records` while the table is `carethread`.
15. **The PHI rail was enforced only in the mock publisher.** Real SNS
    deliveries were unchecked. `assert_no_phi()` now guards both, covers the
    subject line, and screens drug names against the curated drug and NTI
    indexes rather than a hand-written keyword list.
16. **`ALLOW_MOCK_AUTH` was honoured inside a deployed Lambda**, making the
    `X-Patient-Id` header a full authentication bypass. It is now ignored there,
    and `x-patient-id` was removed from the API Gateway allowed headers.
17. **A nested map on `authorizer.sub`** was stringified and accepted as an identity.
18. **Workflow handlers returned raw exception text** to the client, against the
    Section 9.3 "no internal detail leaks" rule.
19. **CORS was a hardcoded wildcard.** Now `CORS_ALLOW_ORIGIN`, defaulting to
    `*` only for local development.
20. **`verify_medication_action_safety` had an operator-precedence bug** that
    would skip the drug-name check for a medication carrying no salt.

## Frontend wiring pass

Four gaps stood between a working backend and a web app that could consume it.
All four are closed and covered by `tests/test_frontend_wiring.py`.

1. **No patient profile was ever created.** `create_patient` had no caller
   outside tests, so a patient who had just signed up through Cognito got
   `patient: null` from `GET /record` and every screen showing a name broke.
   The first read now seeds a profile from the verified JWT claims and returns
   `profile_complete: false` until the patient supplies the age, sex and phone
   a token cannot carry. Those three are placeholders, never guesses.
2. **No way to display a document.** `pages` returned raw S3 keys against a
   bucket that correctly blocks all public access, so the document detail
   screen and the bbox overlay — the "show original" safety rail — could not be
   built at all. `GET /documents/{id}` now also returns index-aligned,
   15-minute presigned `page_urls`, minted only after the document has been
   fetched patient-scoped.
3. **Reminders were never scheduled.** M5 was complete and tested as a unit
   with nothing calling it. `POST /plan/generate` now schedules them and
   reports `reminders_scheduled`. Deliberately best-effort: an unconfigured
   reminder channel must not lose a care plan that was already persisted.
4. **No Cognito hosted UI.** The pool and client existed but there was no
   domain, no OAuth flows and no callback URLs, so there was no sign-in page.
   Added, using authorization code with PKCE and no client secret.

## What is still mocked, deliberately

The deterministic formatters (`MockLLMFormatter`,
`MockLabExplanationFormatter`) remain as the **fallback** inside the Bedrock
formatters. When model wording fails `verify_medication_action_safety` or
`verify_lab_explanation_safety`, the deterministic phrasing is served instead.
This is the safety net that keeps a drifting model away from the patient, not
an unfinished path.

## Configuration required before deploy

| Parameter | Purpose |
| :--- | :--- |
| `BedrockModelId` | Point at the newest multimodal Claude model enabled in your account. The default is a known-valid ID, not necessarily the best one available to you. |
| `WebOrigin` | The Amplify domain. Tighten from `*` before submission. |
| `DemoMode` | `true` compresses a reminder "day" to 30 seconds for judging. |

Rasterisation needs a PDF renderer in the Lambda layer (PyMuPDF or
pdf2image/poppler). Without one, PDF uploads are marked `unsupported` with a
clear patient-facing message rather than failing silently.
