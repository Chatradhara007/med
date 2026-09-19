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

---

## 5. M2 — Care Plan Architecture

```text
Canonical Patient Record (DynamoDB PK = PATIENT#<id>)
        ↓
Relevant Clinical Context (Active Diagnoses, Medications, Restrictions, Follow-ups)
        ↓
Deterministic Rules Engine (Static rules.yaml — fever, cardiac chest pain, vitals)
        ↓
Optional LLM Formatter (Strict plain-language translation; cannot alter dosages/rules)
        ↓
PlanEntry Objects (Day 0 to Day 6 across Morning, Afternoon, Evening, Night)
        ↓
DynamoDB Single-Table Persistence (PK = PATIENT#<id>, SK = PLAN#<day_index>#<slot>)
```

### 5.1 Deterministic Clinical Invariant
- **The rules decide. LLMs only format and translate.**
- Escalation rules are loaded strictly from `rules.yaml` (`fever_persistent`, `post_cardiac_chest_pain`, `hypoglycemia_acute`, `severe_shortness_of_breath`, `hypertensive_crisis`).
- LLMs are mechanically prevented from inventing escalation thresholds or altering drug doses.
- Every `PlanEntry` inherits and preserves the verified provenance citation from the source clinical entity.

---

## 6. M3 — Lab Interpreter Architecture

```text
Canonical Patient Record
        ↓
LabResult[]
        ↓
Reference Range Resolution
        ↓
Deterministic Deviation
        ↓
Finding Ranking
        ↓
Diagnosis/Medication Context
        ↓
Structured Interpretation
        ↓
Optional LLM Formatting
```

### 6.1 Reference-Range Precedence & Fallback Invariant
1. **Report Printed Range Takes Absolute Precedence:** If the laboratory report contains a usable printed range (`ref_low` and/or `ref_high`), it is strictly preserved as `ref_source = "REPORT"`. Generic or fallback database ranges are never substituted.
2. **Curated Fallback Dataset (`data/ref_ranges.csv`):** Queried ONLY when the uploaded laboratory report does not provide a usable reference interval. Returns `ref_source = "FALLBACK"`.
3. **Zero Range Invention:** If an analyte is not present in the report or the fallback repository, the missing reference interval is represented explicitly (`ref_source = "NONE"`, `status = "unknown"`). The system never hallucinates reference bounds.

### 6.2 Deterministic Deviation & Reproducible Ranking
- **Mathematical Formulation:**
  - Interval span: $span = ref\_high - ref\_low$
  - If $value > ref\_high$: status is `above`, deviation score $= \text{round}((value - ref\_high) / span, 2)$
  - If $value < ref\_low$: status is `below`, deviation score $= \text{round}((ref\_low - value) / span, 2)$
  - If $ref\_low \le value \le ref\_high$: status is `within`, deviation score $= 0.0$ (including exact boundaries)
- **Abnormal-First Ranking:** Abnormal findings are ordered strictly in descending order of deviation score, with deterministic alphabetical tie-breaking. Normal findings follow alphabetically. Top 3 findings are partitioned for prominent card presentation in the UI.

### 6.3 Cross-Reading Clinical Context (Diagnoses & Medications)
- **Metformin + Elevated Creatinine / BUN:** When renal parameters are elevated (`status = above`) in a patient actively prescribed Metformin, a cross-module alert is generated flagging reduced drug clearance and lactic acidosis advisory risk.
- **Potassium + RAAS Inhibitors:** Abnormal potassium levels trigger contextual electrolyte monitoring notes for patients on ACE inhibitors, ARBs, or potassium-sparing diuretics.
- **Diabetes & Cardiac History:** Glycemic and cardiac biomarkers are contextualized against documented diagnoses without creating new diagnoses.
- **Safety Boundary:** The module never creates new diagnoses, never prescribes, and never alters medications.

### 6.4 Provenance & Uncertainty Preservation
- Every interpreted finding retains the complete provenance citation (`doc_id`, `page`, `bbox`, `verbatim`, `confidence`) of the underlying `LabResult`.
- Items marked `needs_review` (or confidence $< 0.85$) preserve their uncertainty and are never promoted to `confirmed`.
- LLMs are restricted strictly to patient-friendly wording and are mechanically prevented via `verify_lab_explanation_safety` from altering values, bounds, or status directions.



