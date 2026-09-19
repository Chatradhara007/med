# CareThread — Canonical Data Contracts & Provenance Specification

> **Contract Freeze Status:** FROZEN  
> **Primary Source of Truth:** CareThread Build Documentation (24-Hour AWS Hackathon · *Ship It* Track)  
> **Implementation State:** Shared Schemas & Provenance Invariant Implemented. Downstream modules (DynamoDB repo, S3 upload, Step Functions, OCR, extraction, care plan, lab interpreter, substitution, reminders) are **NOT IMPLEMENTED YET**.

---

## 1. Provenance Contract — The One Invariant

> [!IMPORTANT]
> **"No value reaches the UI without a source."**  
> Every extracted clinical entity must carry an unbroken, verified provenance record linking it to a physical scan coordinate. Entities missing valid provenance will fail schema validation.

### 1.1 Source Citation Structure
```json
{
  "doc_id": "d_014",
  "page": 1,
  "bbox": [120, 340, 480, 362],
  "verbatim": "Tab. Metformin 500mg BD x 30 days"
}
```

| Field | Type | Validation Rule | Status |
| :--- | :--- | :--- | :--- |
| `doc_id` | `string` | Non-empty string identifier of the originating document | **REQUIRED** |
| `page` | `integer` | 1-indexed page number (`page >= 1`) | **REQUIRED** |
| `bbox` | `array[4]` | `[ymin, xmin, ymax, xmax]` normalized to `0.0–1000.0`. Validates `ymin <= ymax` and `xmin <= xmax`. | **REQUIRED** |
| `verbatim`| `string` | Non-empty exact substring transcribed from document text layer | **REQUIRED** |

### 1.2 Confidence Gating & Extraction Lifecycle
The confidence threshold is fixed at **`0.85`**:

```
[Extraction]
      │
      ▼
confidence score
      │
  ┌───┴─────────────────────────┐
  ▼                             ▼
confidence >= 0.85        confidence < 0.85
  │                             │
  ▼                             ▼
status: "confirmed"       status: "needs_review" (Amber UI chip)
                                │
                                ▼
                    Patient taps in UI to accept or correct
                                │
                                ▼
                          status: "confirmed"
```

- **`confidence >= 0.85`** $\rightarrow$ `status: "confirmed"`
- **`confidence < 0.85`** $\rightarrow$ `status: "needs_review"`
- **Patient Correction:** When the patient resolves a `needs_review` chip via `PATCH /record/field`, status transitions to `confirmed`.

---

## 2. Canonical Shared Entities

### 2.1 Patient Profile (`shared.schemas.patient.Patient`)
- **DynamoDB Keys:** `PK = PATIENT#<patient_id>`, `SK = PROFILE`
- **Produced by:** Auth registration / M0
- **Consumed by:** M2 (Care Plan), M6 (Core APIs), Web Frontend

| Attribute | Type | Validation Rules | Classification |
| :--- | :--- | :--- | :--- |
| `patient_id` | `string` | Unique identifier (from Cognito JWT `sub` claim) | **REQUIRED** |
| `name` | `string` | Patient full legal name | **REQUIRED** |
| `age` | `integer`| Age in years (`0 <= age <= 150`) | **REQUIRED** |
| `sex` | `string` | Biological sex (`M`, `F`, `Other`, `Unknown`) | **REQUIRED** |
| `language` | `string` | Preferred language code (default: `"en"`) | **OPTIONAL** |
| `phone` | `string` | Contact phone number for SMS adherence reminders | **REQUIRED** |
| `created_at` | `string` | ISO 8601 registration timestamp | **OPTIONAL** |

---

### 2.2 Document Metadata (`shared.schemas.document.Document`)
- **DynamoDB Keys:** `PK = PATIENT#<patient_id>`, `SK = DOC#<iso_ts>#<doc_id>`
- **Produced by:** M0 (`POST /documents`), M1 (Ingest Pipeline)
- **Consumed by:** M1, M6 (`GET /documents/{id}`), Web Frontend

| Attribute | Type | Validation Rules | Classification |
| :--- | :--- | :--- | :--- |
| `patient_id` | `string` | Owning patient ID | **REQUIRED** |
| `doc_id` | `string` | Document ID (`d_014`) | **REQUIRED** |
| `type` | `enum` | `discharge_summary`, `lab_report`, `medicine_strip`, `prescription`, `unknown` | **REQUIRED** |
| `s3_key` | `string` | Path in S3 `raw/<patient_id>/<doc_id>.<ext>` | **REQUIRED** |
| `status` | `enum` | `uploading`, `uploaded`, `rasterising`, `classifying`, `extracting`, `validating`, `review_required`, `ready`, `unsupported`, `failed` | **REQUIRED** |
| `pages` | `int \| list[str]`| Page count or list of rasterised page S3 keys | **OPTIONAL** |
| `created_at` | `string` | ISO 8601 creation timestamp | **REQUIRED** |
| `updated_at` | `string` | ISO 8601 last status transition timestamp | **REQUIRED** |
| `error_reason`| `string` | Diagnostic failure message if `status == "failed"` | **OPTIONAL** |

---

### 2.3 Medication Item (`shared.schemas.medication.Medication`)
- **DynamoDB Keys:** `PK = PATIENT#<patient_id>`, `SK = MED#<normalised_name>`
- **Produced by:** M1 (Extract discharge summary / medicine strip)
- **Consumed by:** M2 (Care Plan scheduler), M3 (Lab cross-read), M4 (Substitution cross-check), M6 (Record API)

| Attribute | Type | Validation Rules | Classification |
| :--- | :--- | :--- | :--- |
| `name` | `string` | Brand or prescribed medicine name | **REQUIRED** |
| `salt` | `string` | Active pharmaceutical salt (e.g. metformin hydrochloride) | **REQUIRED** |
| `strength` | `string` | Formulation strength (e.g., `"500mg"`) | **REQUIRED** |
| `form` | `string` | Formulation form (default: `"tablet"`) | **OPTIONAL** |
| `freq` | `string` | Dosing frequency (e.g., `"OD"`, `"BD"`, `"TDS"`, `"QID"`, `"PRN"`) | **REQUIRED** |
| `duration_days`| `integer`| Prescribed duration (`>= 0`) | **REQUIRED** |
| `start_date` | `string` | ISO date string for prescription initiation | **OPTIONAL** |
| `instructions`| `string` | Directions for use (e.g. "Take after meals") | **OPTIONAL** |
| `provenance` | `ProvenanceEnvelope` | Verified source citation pinning to physical scan coordinates | **REQUIRED** |

---

### 2.4 Lab Result (`shared.schemas.lab_result.LabResult`)
- **DynamoDB Keys:** `PK = PATIENT#<patient_id>`, `SK = LAB#<iso_ts>#<analyte>`
- **Produced by:** M1 (Extract lab report), M3 (Lab Interpreter)
- **Consumed by:** M3 (Ranking & cross-read), M7 (Cross-module reasoning), M6 (Record API)

| Attribute | Type | Validation Rules | Classification |
| :--- | :--- | :--- | :--- |
| `analyte` | `string` | Analyte name (e.g., Serum Creatinine, Fasting Blood Sugar) | **REQUIRED** |
| `value` | `float \| string` | Measured lab value | **REQUIRED** |
| `unit` | `string` | Unit of measure (e.g. `mg/dL`, `mmol/L`) | **REQUIRED** |
| `ref_low` | `float` | Lower biological reference limit | **OPTIONAL** |
| `ref_high` | `float` | Upper biological reference limit | **OPTIONAL** |
| `ref_source` | `string` | `"printed"` (from report) or `"fallback_ref_ranges"` (from data/ref_ranges.csv) | **OPTIONAL** |
| `deviation_score`| `float`| Normalised deviation score: $(value - high) / (high - low)$ | **OPTIONAL** |
| `flag` | `string` | `normal`, `high`, `low`, `critical` | **OPTIONAL** |
| `provenance` | `ProvenanceEnvelope` | Verified source citation pinning to physical scan coordinates | **REQUIRED** |

---

### 2.5 Clinical Diagnosis (`shared.schemas.diagnosis.Diagnosis`)
- **DynamoDB Keys:** `PK = PATIENT#<patient_id>`, `SK = DIAG#<code_or_slug>`
- **Produced by:** M1 (Extract discharge summary)
- **Consumed by:** M2 (Escalation rule qualification), M3 (Lab context), M6 (Record API)

| Attribute | Type | Validation Rules | Classification |
| :--- | :--- | :--- | :--- |
| `label` | `string` | Clinical diagnosis label (e.g., Type 2 Diabetes Mellitus) | **REQUIRED** |
| `code_or_slug`| `string` | URL-safe slug or internal code | **OPTIONAL** |
| `icd_hint` | `string` | ICD-10 diagnostic code hint if stated in document | **OPTIONAL** |
| `status` | `string` | Condition status (`"active"` or `"resolved"`) | **OPTIONAL** |
| `provenance` | `ProvenanceEnvelope` | Verified source citation pinning to physical scan coordinates | **REQUIRED** |

---

### 2.6 Care Plan Entry (`shared.schemas.plan_entry.PlanEntry`)
- **DynamoDB Keys:** `PK = PATIENT#<patient_id>`, `SK = PLAN#<day_index>#<slot>`
- **Produced by:** M2 (Care Plan service)
- **Consumed by:** M5 (Reminders), M6 (`POST /plan/{day}/{slot}/done`), Web Frontend

| Attribute | Type | Validation Rules | Classification |
| :--- | :--- | :--- | :--- |
| `day_index` | `integer` | Day index in post-discharge timeline (`0 <= day_index <= 6`) | **REQUIRED** |
| `slot` | `enum` | `morning`, `afternoon`, `evening`, `night` | **REQUIRED** |
| `action` | `string` | Actionable instruction (e.g. "Take Tab Metformin 500mg") | **REQUIRED** |
| `med_ref` | `string` | Sort key reference to medication (`MED#<name>`) | **REQUIRED** |
| `time_target` | `string` | Target time of day (e.g., `"08:00"`) | **OPTIONAL** |
| `done` | `boolean` | Dose adherence status (default: `false`) | **REQUIRED** |
| `completed_at`| `string` | ISO 8601 timestamp when dose was taken | **OPTIONAL** |
| `provenance` | `ProvenanceEnvelope` | Verified source citation linking to original prescription line | **REQUIRED** |

---

### 2.7 Alert Rule & Fired Alert (`shared.schemas.alert_rule.AlertRule`, `FiredAlert`)
- **DynamoDB Keys:** `PK = PATIENT#<patient_id>`, `SK = ALERT#<iso_ts>`
- **Produced by:** M2 (Deterministic rule engine), M7 (Cross-module reasoning)
- **Consumed by:** M6 (Record API), Web Frontend

> **SAFETY INVARIANT:** The rules decide. LLMs only format and translate. Escalation advice is **never** model-generated.

| Attribute | Type | Validation Rules | Classification |
| :--- | :--- | :--- | :--- |
| `alert_id` | `string` | Unique alert instance ID | **REQUIRED** |
| `rule_id` | `string` | Identifier matching static entry in `rules.yaml` | **REQUIRED** |
| `severity` | `enum` | `info`, `warning`, `high`, `critical` | **REQUIRED** |
| `message` | `string` | Deterministic escalation action (e.g., "Call emergency services now") | **REQUIRED** |
| `fired_at` | `string` | ISO 8601 trigger timestamp | **REQUIRED** |
| `acknowledged`| `boolean` | Patient acknowledgment flag | **OPTIONAL** |
| `cross_module_context` | `dict` | Evidence from multiple documents triggering the alert | **OPTIONAL** |

---

### 2.8 Extraction Result (`shared.schemas.extraction.ExtractionResult`)
- **Produced by:** M1 (Step Functions extraction and validation tasks)
- **Consumed by:** M1 (Persistence task), M2 (Initial care plan seed)

Unified envelope holding typed extraction outputs (`diagnoses`, `medications`, `lab_results`, `followups`, `restrictions`, `medicine_strip`) alongside overall document confidence, validation status (`valid`, `invalid`, `repaired`), and raw LLM JSON.

---

## 3. API Request & Response Contracts (`shared.schemas.api`)

All endpoints are authenticated via Amazon Cognito JWT Authorizer. `patient_id` is extracted exclusively from the JWT `sub` claim.

### 3.1 `POST /documents`
- **Request:** `DocumentCreateRequest`
  - `filename`: `string` (**REQUIRED**)
  - `content_type`: `string` (**REQUIRED**, e.g., `application/pdf`)
- **Response:** `DocumentCreateResponse`
  - `doc_id`: `string` (**REQUIRED**)
  - `upload_url`: `string` (**REQUIRED**, presigned S3 PUT URL)

### 3.2 `GET /documents/{id}`
- **Request:** Path parameter `doc_id`
- **Response:** `DocumentStatusResponse`
  - `doc_id`: `string` (**REQUIRED**)
  - `status`: `DocumentStatus` (**REQUIRED**)
  - `type`: `DocumentType` (**OPTIONAL**)
  - `pages`: `list[string]` (**OPTIONAL**)
  - `error`: `string` (**OPTIONAL**)

### 3.3 `GET /record`
- **Request:** Headers (`Authorization: Bearer <JWT>`)
- **Response:** `PatientRecordResponse`
  - `patient`: `Patient` (**OPTIONAL**)
  - `documents`: `list[Document]` (**REQUIRED**)
  - `diagnoses`: `list[Diagnosis]` (**REQUIRED**)
  - `medications`: `list[Medication]` (**REQUIRED**)
  - `lab_results`: `list[LabResult]` (**REQUIRED**)
  - `plan_entries`: `list[PlanEntry]` (**REQUIRED**)
  - `alerts`: `list[FiredAlert]` (**REQUIRED**)

### 3.4 `PATCH /record/field`
- **Request:** `RecordFieldPatchRequest`
  - `sk`: `string` (**REQUIRED**, e.g., `MED#metformin`)
  - `field`: `string` (**REQUIRED**)
  - `value`: `any` (**REQUIRED**)
- **Response:** `RecordFieldPatchResponse`
  - `status`: `ProvenanceStatus.CONFIRMED` (**REQUIRED**)
  - `updated_item`: `dict` (**REQUIRED**)

### 3.5 `POST /substitution`
- **Request:** `SubstitutionRequest`
  - `doc_id`: `string` (**OPTIONAL**)
  - `brand`: `string` (**OPTIONAL**)
  - `strength`: `string` (**OPTIONAL**)
  *(Validation: requires `doc_id` OR both `brand` and `strength`)*
- **Response:** `SubstitutionResponse`
  - `blocked`: `boolean` (**REQUIRED**, `true` if salt is on NTI blocklist)
  - `reason`: `string` (**OPTIONAL**, e.g. "Warfarin has a narrow therapeutic index. Do not substitute.")
  - `alternatives`: `list[DrugAlternative]` (**REQUIRED**)
  - `interactions`: `list[string]` (**REQUIRED**)

### 3.6 `POST /plan/{day}/{slot}/done`
- **Request:** Path parameters `day`: integer, `slot`: `SlotName`
- **Response:** `PlanDoneResponse`
  - `day`: `integer` (**REQUIRED**)
  - `slot`: `SlotName` (**REQUIRED**)
  - `done`: `boolean` (always `true`)
  - `completed_at`: `string` (ISO timestamp)

---

## 4. Module Contract Matrix

| Module | Consumes Schemas | Produces Schemas | Implementation Status |
| :--- | :--- | :--- | :--- |
| **M0 (Infra)** | - | `Patient`, `Document` | **NOT IMPLEMENTED YET** (Skeleton in place) |
| **M1 (Ingest Pipeline)** | S3 object, `Document` | `ExtractionResult`, `Medication`, `LabResult`, `Diagnosis`, `ProvenanceEnvelope` | **NOT IMPLEMENTED YET** |
| **M2 (Care Plan)** | `Medication`, `Diagnosis`, `rules.yaml` | `PlanEntry`, `FiredAlert` | **NOT IMPLEMENTED YET** |
| **M3 (Lab Interpreter)** | `LabResult`, `Medication`, `Diagnosis`, `ref_ranges.csv` | Ranked `LabResult`, cross-module `FiredAlert` | **NOT IMPLEMENTED YET** |
| **M4 (Substitution Check)** | `MedicineStripExtraction`, `drugs.csv`, `nti.csv`, active `Medication` | `SubstitutionResponse` (with NTI block guardrail) | **NOT IMPLEMENTED YET** |
| **M5 (Reminders)** | `PlanEntry`, `Patient` | SNS push notification payload | **NOT IMPLEMENTED YET** |
| **M6 (APIs)** | API Requests | API Responses (`PatientRecordResponse`, etc.) | **NOT IMPLEMENTED YET** |
| **M7 (Cross-Module)** | `Medication`, `LabResult`, `Diagnosis` | Cross-module `FiredAlert` (e.g. Metformin + Creatinine) | **NOT IMPLEMENTED YET** |
