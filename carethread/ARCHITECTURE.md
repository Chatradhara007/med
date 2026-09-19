# CareThread — System Architecture Specification

## 1. Overview & Core Philosophy
CareThread treats the three critical post-discharge breakdowns—incomprehensible discharge summaries, uncontextualized outpatient lab reports, and retail pharmacy counter stockouts—as **one connected episode belonging to one patient in the same week**.

Instead of five disconnected tools with separate databases, CareThread is organized around **one patient-side canonical record for one episode of care**.

---

## 2. DynamoDB Single-Table Partition Architecture

```text
                                  PATIENT#123
                                       │
            ┌──────────────────────────┼──────────────────────────┐
            ↓                          ↓                          ↓
         PROFILE                    DOC#...                    MED#...
      (Demographics)           (Document Status)          (Prescriptions)
                                                                  │
                     ┌────────────────────────────────────────────┼────────────────────────────┐
                     ↓                                            ↓                            ↓
                  LAB#...                                      DIAG#...                     PLAN#...
              (Lab Analytes)                                 (Diagnoses)                (7-Day Schedule)
                                                                                               │
                                                                                            ALERT#...
                                                                                         (Red Flag Rules)
```

### 2.1 Why the Single-Table Patient Partition is Used
In emergency post-hospitalization recovery, clinicians and patients cannot afford relational database latency, distributed joins, or eventual consistency hazards across multiple microservice databases:

1. **Zero Multi-Table Joins:** A single `Query(PK = PATIENT#<patient_id>)` loads the complete canonical patient context—patient demographics, document upload states, active medications, laboratory results, diagnostic history, 7-day care schedule slots, and fired clinical alerts—in a single sub-10ms network call.
2. **Immediate Cross-Module Context:**
   - **M2 (Care Plan):** Directly pairs `MED#` prescriptions with `DIAG#` diagnoses to construct timetable slots and evaluate static escalation triggers.
   - **M3 (Lab Interpreter):** Cross-reads newly reported `LAB#` values against active `MED#` rows (e.g. elevated Serum Creatinine in the presence of active Metformin) without separate service calls.
   - **M4 (Substitution Check):** Directly screens requested drug substitutions against the patient's active `MED#` prescription list for adverse interactions.
3. **Strict Data Isolation & Security:** Partitioning on `PATIENT#<patient_id>` ensures absolute tenant and data isolation. Queries are mechanically bounded to the authenticated patient's partition derived from the verified Cognito JWT `sub` claim. Cross-patient data leakage is physically prevented at the partition level.

### 2.2 Documented Key Patterns

| Entity | Partition Key (`PK`) | Sort Key (`SK`) | Key Content |
| :--- | :--- | :--- | :--- |
| **Patient Profile** | `PATIENT#<patient_id>` | `PROFILE` | Name, age, sex, phone, language, registration date |
| **Document Metadata** | `PATIENT#<patient_id>` | `DOC#<iso_ts>#<doc_id>` | Type, S3 key, 10-state lifecycle status, page count |
| **Medication Item** | `PATIENT#<patient_id>` | `MED#<normalised_name>` | Salt, strength, frequency, duration, verified provenance |
| **Lab Result** | `PATIENT#<patient_id>` | `LAB#<iso_ts>#<analyte>` | Value, unit, printed & fallback ref ranges, deviation score, provenance |
| **Clinical Diagnosis** | `PATIENT#<patient_id>` | `DIAG#<code_or_slug>` | Diagnostic label, ICD-10 hint, active status, provenance |
| **Care Plan Entry** | `PATIENT#<patient_id>` | `PLAN#<day_index>#<slot>` | Action, medication reference, target time, adherence done flag, provenance |
| **Fired Alert** | `PATIENT#<patient_id>` | `ALERT#<iso_ts>` | Static rule ID, severity (`info` to `critical`), action message, timestamp |

---

## 3. Data Access Layer Abstraction (`carethread/shared/repository/`)

Application code interacts with persistence through an abstract contract:

- **`PatientRepositoryInterface`:** Defines typed domain operations (`create_patient`, `get_patient`, `create_document`, `get_document`, `create_medication`, `create_lab_result`, `create_diagnosis`, `create_plan_entry`, `update_plan_entry_done`, `create_alert`, `get_patient_context`).
- **`DynamoDBPatientRepository`:** Production implementation interacting with DynamoDB via `boto3`. Handles recursive `Decimal` serialization, expression-safe queries, GSI1 projection (`status + PK`), and targeted non-destructive updates.
- **`InMemoryPatientRepository`:** High-fidelity in-memory implementation enforcing identical sort-key structures, partition isolation, and provenance invariants for credential-free local unit testing and development.
- **`MissingProvenanceError`:** Strict guardrail rejecting any attempt to persist an extracted clinical entity lacking verified provenance citations.

---

## 4. Document Upload Foundation & Storage Architecture (`POST /documents`)

```text
Client (Web / Mobile)
  │
  │ 1. POST /documents { filename, content_type } (Bearer JWT)
  ↓
API Gateway (HTTP API + JWT Authorizer)
  │
  ↓ 2. Invokes Lambda with requestContext.authorizer.jwt.claims.sub
Documents Lambda Handler
  │
  ├── a. Authenticate: extract patient_id strictly from JWT 'sub' claim
  │      (Body-supplied patient_id is explicitly ignored and rejected)
  ├── b. Generate unique doc_id: d_<random_hex>
  ├── c. Compute deterministic S3 key: raw/<patient_id>/<doc_id>.<ext>
  ├── d. Create Document record: status = "uploading"
  ├── e. Persist metadata to DynamoDB single table (PK = PATIENT#<id>, SK = DOC#<iso_ts>#<doc_id>)
  └── f. Generate S3 presigned PUT URL (valid for 300s, server-side encryption on)
  │
  ↓ 3. Return 201 Created { doc_id, upload_url }
Client
  │
  │ 4. Direct PUT binary payload to presigned upload_url
  ↓
Amazon S3 (carethread-docs)
```

### 4.1 S3 Layout & Security Standards
- **Bucket Layout:**
  - `raw/<patient_id>/<doc_id>.<ext>`: Original unprocessed uploaded PDFs or camera photos.
  - `pages/<patient_id>/<doc_id>/p<N>.png`: 150 DPI rasterised page images for UI display and bounding box overlays.
- **Access Control:** Public access is completely blocked (`BlockPublicAcls`, `BlockPublicPolicy`, `IgnorePublicAcls`, `RestrictPublicBuckets`).
- **Encryption:** Server-Side Encryption AES-256 (`SSEAlgorithm: AES256`).
- **Presigned Expiration:** 300 seconds strictly enforced.
- **Tenant Isolation:** Patients only receive presigned PUT credentials for their own `raw/<patient_id>/` path.

