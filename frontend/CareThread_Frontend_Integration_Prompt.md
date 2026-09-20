# CareThread Frontend → Fixed Backend Integration Task

## READ THIS FIRST — NON-NEGOTIABLE SCOPE

You are modifying the **CareThread frontend only**.

The backend is considered **FINAL, FIXED, and IMMUTABLE**.

### Absolute rule

> **DO NOT MODIFY THE BACKEND UNDER ANY CIRCUMSTANCES.**

Do not change:

- Python files
- Lambda handlers
- Lambda services
- API routes
- API Gateway configuration
- SAM / CloudFormation
- DynamoDB schemas
- S3 configuration
- Step Functions
- Cognito configuration
- Bedrock/model code
- backend contracts
- backend data models
- backend infrastructure
- backend business logic
- backend endpoint behavior

If the frontend currently expects something that the backend does not expose, **adapt the frontend to the existing backend contract**. Do NOT add or request a backend endpoint.

The only allowed changes are inside the **frontend project**.

---

# 1. Objective

Make the existing React/Vite frontend fully compatible with the existing CareThread backend.

The frontend already has:

```text
React/Vite
    ↓
apiClient
    ├── mockApi
    └── realApi
```

Preserve this architecture.

The goal is:

```text
React UI
   ↓
frontend API layer
   ↓
Cognito JWT
   ↓
AWS API Gateway
   ↓
existing backend
```

The frontend must work against the fixed backend without changing the backend.

Do not rebuild the UI from scratch.

Do not remove the existing mock mode unless necessary.

Keep mock mode working where practical.

---

# 2. SOURCE OF TRUTH

Treat the backend's existing API implementation and canonical schemas as the source of truth.

The fixed backend exposes these routes:

```text
POST /documents
GET  /documents/{id}

GET   /record
PATCH /record
PATCH /record/field

POST /plan/generate
POST /plan/{day}/{slot}/done

POST /substitution

POST /labs/interpret
```

There is deliberately NO:

```text
GET /documents
GET /medicine/scans
```

Do not create those endpoints.

The frontend must adapt to the routes that actually exist.

---

# 3. EXISTING FRONTEND PROBLEMS TO FIX

Implement all of the following.

---

## 3.1 Fix the canonical PatientRecord model

The backend `/record` response is:

```json
{
  "patient": {},
  "documents": [],
  "diagnoses": [],
  "medications": [],
  "lab_results": [],
  "plan_entries": [],
  "alerts": [],
  "profile_complete": true
}
```

The frontend currently expects:

```text
patient
alerts
carePlan
recentDocuments
currentEpisode
activeMedications
allergies
careTeam
```

This is incompatible.

### Required frontend change

Create a clean adapter/normalization layer in the frontend API layer.

Prefer:

```text
AWS canonical response
        ↓
realApi.ts / adapter
        ↓
frontend UI model
```

Do NOT force every React component to understand backend naming.

The adapter should map:

```text
documents      → recentDocuments / document data
plan_entries   → carePlan
medications    → activeMedications
diagnoses      → diagnosis UI data
lab_results    → lab UI data
alerts         → alerts
patient        → patient
profile_complete → profile completion state
```

Do not invent backend data.

If the backend does not provide a field, do not fabricate it.

---

# 4. Fix Patient model

Backend Patient fields are:

```text
patient_id
name
age
sex
language
phone
created_at
```

The frontend currently expects:

```text
id
name
dob
```

### Required

Map:

```text
patient.patient_id → frontend patient.id
```

Remove dependence on:

```text
patient.dob
```

because the backend does not provide DOB.

Use the actual backend fields:

```text
age
sex
language
phone
```

where the UI needs them.

Do not derive DOB from age.

Do not invent missing demographics.

---

# 5. Implement profile completion

The backend exposes:

```text
profile_complete
```

and can seed a profile from Cognito claims.

A newly registered patient may have:

```json
"profile_complete": false
```

The frontend must detect this.

Show a clear profile-completion UI asking the patient for the missing information instead of displaying fake values.

The backend allows controlled updates through:

```http
PATCH /record
```

or:

```http
PATCH /record/field
```

Use the existing backend mutation contract.

For profile updates the frontend must use:

```text
SK = PROFILE
```

and editable fields are:

```text
name
age
phone
language
sex
```

Do not attempt to edit:

```text
patient_id
pk
sk
created_at
```

Do not invent profile fields.

---

# 6. Fix document listing

The backend DOES NOT expose:

```http
GET /documents
```

The frontend currently calls it.

### Required change

Remove the frontend dependency on:

```text
GET /documents
```

Use:

```http
GET /record
```

and read:

```text
record.documents
```

for the patient's document list.

The frontend document list should be derived from the canonical record.

Sort using:

```text
created_at / updated_at
```

rather than the old mock-only `uploadedAt` field.

---

# 7. Fix document creation and actual S3 upload

The backend provides:

```http
POST /documents
```

Request:

```json
{
  "filename": "example.pdf",
  "content_type": "application/pdf"
}
```

Response:

```json
{
  "doc_id": "d_014",
  "upload_url": "PRESIGNED_S3_PUT_URL"
}
```

### Current frontend bug

The frontend gets the presigned URL but only logs it.

It currently does NOT upload the file.

### Required implementation

After:

```text
POST /documents
```

perform the actual:

```http
PUT <upload_url>
```

with the selected `File` as the request body.

Use the correct content type.

Do not send the file through API Gateway.

The upload flow must be:

```text
User selects file
      ↓
POST /documents
      ↓
receive doc_id + upload_url
      ↓
PUT file directly to upload_url
      ↓
poll GET /documents/{doc_id}
```

Handle upload errors cleanly.

---

# 8. Fix document status model

Backend statuses are:

```text
uploading
uploaded
rasterising
classifying
extracting
validating
review_required
ready
unsupported
failed
```

The frontend currently only understands:

```text
uploaded
processing
ready
failed
```

### Required

Update frontend types and UI so every backend status is handled.

It is acceptable to visually group statuses, for example:

```text
uploading
uploaded
rasterising
classifying
extracting
validating
    ↓
Processing

review_required
    ↓
Needs Review

ready
    ↓
Ready

unsupported
    ↓
Unsupported

failed
    ↓
Failed
```

Do not break the canonical backend status values.

---

# 9. Fix document detail response

`GET /documents/{id}` returns the document status response.

It includes:

```text
doc_id
status
type
pages
page_urls
error
```

The backend generates presigned download URLs for rasterized pages.

The frontend currently expects:

```text
id
name
type
status
uploadedAt
errorReason
extractedData
```

### Required

Adapt the backend response into the frontend UI model.

Map:

```text
doc_id → id
error → errorReason
```

and use:

```text
page_urls
```

for document rendering.

Do not expect `extractedData` directly from `GET /documents/{id}`.

---

# 10. Replace the fake document viewer

The current document viewer displays:

```text
[Simulated Document Page Content]
```

This must be removed from the real API path.

The viewer must use the actual:

```text
page_urls
```

returned by:

```http
GET /documents/{id}
```

Render the actual rasterized page image.

Support multiple pages.

Allow the user to view the relevant page when selecting:

```text
Show original
```

---

# 11. Fix provenance / bounding-box rendering

Backend provenance source is:

```json
{
  "doc_id": "d_014",
  "page": 1,
  "bbox": [120, 340, 480, 362],
  "verbatim": "Tab. Metformin 500mg BD x 30 days"
}
```

The bbox order is:

```text
[ymin, xmin, ymax, xmax]
```

and coordinates are normalized to:

```text
0–1000
```

The current frontend incorrectly treats the four numbers as:

```text
[left, top, width, height]
```

### Required conversion

For a percentage-based overlay:

```text
top    = ymin / 10
left   = xmin / 10
width  = (xmax - xmin) / 10
height = (ymax - ymin) / 10
```

Do not change the backend coordinate convention.

The overlay must be positioned over the real page image.

---

# 12. Preserve the provenance invariant

The backend's core invariant is:

> No clinical value reaches the UI without a source.

Every clinical entity has provenance containing:

```text
field
value
source.doc_id
source.page
source.bbox
source.verbatim
confidence
status
```

The frontend must preserve this information.

Do not display extracted clinical values as if they were unsourced.

When rendering:

```text
medications
diagnoses
lab results
care-plan entries
```

use their provenance when available.

---

# 13. Implement confidence gating correctly

The fixed backend threshold is:

```text
confidence >= 0.85 → confirmed
confidence < 0.85  → needs_review
```

Frontend must represent:

```text
confirmed
needs_review
```

correctly.

A `needs_review` field must provide:

```text
Review & Correct
```

and allow the patient to confirm/correct it.

Do not invent another threshold.

---

# 14. Fix PATCH /record/field

The backend request is:

```json
{
  "sk": "MED#metformin",
  "field": "strength",
  "value": "500mg"
}
```

The current frontend incorrectly uses the entire category as the field name and sends the whole object as the value.

### Required

The frontend review form must identify the actual editable attribute.

Examples:

```text
strength
freq
instructions
duration_days
status
```

For diagnosis:

```text
code
status
notes
display_name
```

For plan:

```text
action
time_target
done
```

For profile:

```text
name
age
phone
language
sex
```

Send:

```text
sk = entity sort key
field = exact attribute being edited
value = corrected value for that attribute
```

Do not send the entire entity as `value` unless the exact backend contract requires it.

After success, refresh the record.

---

# 15. Fix the Care Plan model

Backend PlanEntry is:

```text
day_index
slot
action
med_ref
time_target
done
completed_at
provenance
```

Day is:

```text
0–6
```

Slot is one of:

```text
morning
afternoon
evening
night
```

The frontend currently uses:

```text
id
day: ISO date
slot
title
description
status
type
```

### Required

Adapt the backend PlanEntry into the UI model.

Do not treat `day_index` as an ISO date.

Display it as a post-discharge day:

```text
Day 0
Day 1
...
Day 6
```

Use:

```text
action → title/description as appropriate
done → completed/pending
time_target → displayed target time
med_ref → medication reference
completed_at → completion timestamp
```

Preserve provenance.

---

# 16. Fix Mark Done

The current frontend is hardcoded to:

```text
POST /plan/today/morning/done
```

This is wrong.

### Required

When a user clicks Mark Done, use the actual item's:

```text
day_index
slot
```

Call:

```http
POST /plan/{day}/{slot}/done
```

Example:

```http
POST /plan/2/evening/done
```

The backend request does NOT need a JSON body.

Do not send the old mock `id` body.

After success, refresh `/record`.

---

# 17. Add frontend support for /plan/generate

The backend exposes:

```http
POST /plan/generate
```

No request body is required.

The response contains:

```text
patient_id
days_covered
entries
alerts
reminders_scheduled
```

### Required frontend behavior

Add an API method for:

```text
generateCarePlan()
```

Use it at the appropriate point in the frontend flow.

After generation:

```text
refresh /record
```

so the newly generated plan appears in the Timeline.

Do not reimplement care-plan generation in React.

Do not create client-side medical scheduling logic.

The backend owns the care-plan rules.

---

# 18. Do not recreate backend escalation rules in the frontend

The backend owns deterministic escalation rules.

The frontend should only:

```text
display backend alerts
```

It must NOT invent its own clinical escalation rules.

Do not create frontend logic such as:

```text
if fever > X then critical
```

The backend is the source of truth for alerts.

---

# 19. Fix Alert severity mapping

Backend severity values are:

```text
info
warning
high
critical
```

The frontend currently expects:

```text
critical
high
medium
low
```

### Required

Update frontend types/components to understand the backend values.

Do not invent:

```text
medium
low
```

as backend values.

If the visual design wants different styling, map the visual style internally without changing the backend value.

---

# 20. Add Lab Interpreter integration

The backend exposes:

```http
POST /labs/interpret
```

It requires only authenticated access.

It reads:

```text
lab results
diagnoses
medications
```

from the patient's canonical record.

The response is a lab interpretation report containing:

```text
patient_id
total_findings
abnormal_count
top_findings
all_findings
cross_module_alerts
generated_at
```

Each finding includes:

```text
analyte
value
unit
ref_low
ref_high
ref_source
status
deviation_score
rank
context_diagnoses
context_medications
context_notes
explanation
provenance
confidence
review_status
```

### Required frontend

Add an API function:

```text
interpretLabs()
```

and a UI path that allows the user to view the lab interpretation.

Display:

```text
Top findings
Abnormal count
Reference ranges
Status
Explanation
Relevant diagnosis/medication context
Cross-module alerts
```

Preserve provenance.

Do not generate interpretations in the browser.

Do not call an LLM directly from the frontend.

---

# 21. Fix medicine scanner architecture

The backend substitution endpoint accepts:

```json
{
  "doc_id": "d_014"
}
```

OR:

```json
{
  "brand": "Brand Name",
  "strength": "500mg"
}
```

The current frontend sends:

```text
brand = file.name
```

which is incorrect.

### Required real scan flow

When the user captures a medicine image:

```text
camera/file
    ↓
POST /documents
    ↓
receive doc_id + upload_url
    ↓
PUT image to S3 using upload_url
    ↓
poll GET /documents/{doc_id}
    ↓
once appropriate/ready
POST /substitution
{
  "doc_id": "<doc_id>"
}
```

Do not send the local filename as the medicine brand.

If the UI provides a manual fallback, it may use:

```text
brand + strength
```

but only when the actual values are entered by the user.

---

# 22. Fix substitution response model

Backend returns:

```json
{
  "blocked": false,
  "reason": null,
  "alternatives": [],
  "interactions": []
}
```

An alternative contains:

```text
brand
salt
strength_mg
form
manufacturer
price_inr
nti
common_interactions
```

Interactions are:

```text
string[]
```

The frontend currently expects:

```text
detected
generic
strength
priceEstimate
interaction objects
```

### Required

Update the frontend to use the backend response.

Do not expect:

```text
detected
generic
priceEstimate
```

from the backend unless the frontend derives those values locally from the returned data.

For example:

```text
salt → generic display
strength_mg → display strength
price_inr → INR price
```

Interactions should render as strings.

---

# 23. Preserve the NTI hard block

The backend may return:

```text
blocked = true
reason = ...
alternatives = []
```

The frontend must clearly show the refusal.

Do NOT display substitution alternatives when:

```text
blocked === true
```

Do not override the backend's block.

Do not implement a client-side NTI list.

The backend owns the NTI safety rule.

---

# 24. Remove GET /medicine/scans dependency

The backend has no:

```http
GET /medicine/scans
```

### Required

Do not call it.

For Previous Scans, derive the history from the canonical:

```text
GET /record
```

document list.

Filter documents where:

```text
type === "medicine_strip"
```

Then map:

```text
doc_id
created_at / updated_at
status
```

into the existing history UI.

If there are no medicine-strip documents, show the existing empty state.

Do not invent scan records.

---

# 25. Improve document polling

The document lifecycle is:

```text
uploading
uploaded
rasterising
classifying
extracting
validating
review_required
ready
unsupported
failed
```

The frontend should poll:

```http
GET /documents/{id}
```

after upload.

Do not poll a nonexistent:

```text
GET /documents
```

for status.

Stop polling when:

```text
ready
review_required
unsupported
failed
```

or another terminal state defined by the frontend adapter.

Do not poll forever.

---

# 26. Build extracted-field views from canonical record data

The backend `/documents/{id}` endpoint is for document status/page URLs.

Clinical entities come from:

```http
GET /record
```

with:

```text
medications
diagnoses
lab_results
plan_entries
```

Each entity contains provenance.

### Required

When opening a document detail page:

```text
GET /documents/{id}
+
GET /record
```

Then associate clinical entities with the document by:

```text
entity.provenance.source.doc_id === document.doc_id
```

Use that to populate the document's extracted-field display.

Do not expect the backend to return the old mock:

```text
extractedData[]
```

shape.

---

# 27. Map canonical Medication correctly

Backend medication fields:

```text
name
salt
strength
form
freq
duration_days
start_date
instructions
provenance
```

Frontend currently has:

```text
name
strength
frequency
duration
```

### Required

Map:

```text
freq → frequency
duration_days → duration
```

and expose useful fields:

```text
salt
form
start_date
instructions
```

where appropriate.

Preserve provenance.

---

# 28. Map canonical Diagnosis correctly

Backend:

```text
label
code_or_slug
icd_hint
status
provenance
```

Frontend currently uses:

```text
condition
icd10
```

Map:

```text
label → condition
icd_hint → icd10
```

Do not invent an ICD code if `icd_hint` is absent.

---

# 29. Map canonical LabResult correctly

Backend:

```text
analyte
value
unit
ref_low
ref_high
ref_source
deviation_score
flag
provenance
```

Frontend currently uses:

```text
test
value
unit
```

Map:

```text
analyte → test
```

and preserve:

```text
ref_low
ref_high
ref_source
deviation_score
flag
provenance
```

for the lab UI.

---

# 30. Handle backend errors properly

The backend uses structured errors such as:

```json
{
  "error": {
    "code": "...",
    "message": "...",
    "details": []
  }
}
```

The frontend currently throws mostly:

```text
API Request failed: <statusText>
```

### Required

Update the frontend API layer to parse structured backend errors.

Create a reusable frontend error type, for example:

```text
ApiError
  status
  code
  message
  details
```

Use the backend's `message` when presenting errors to the user.

Do not expose raw stack traces.

---

# 31. Keep Cognito authentication

The current frontend already uses:

```text
aws-amplify
fetchAuthSession()
```

Keep that.

Every protected API call must send:

```http
Authorization: Bearer <Cognito JWT>
```

Do not implement a second authentication mechanism.

Do not store JWTs manually in localStorage unless the existing Amplify architecture specifically requires it.

---

# 32. Keep API configuration environment-based

The frontend must continue to use:

```text
VITE_API_GATEWAY_URL
```

for the real backend base URL.

Do not hardcode the API Gateway URL in React components.

Maintain:

```text
VITE_USE_MOCK_API
```

so mock mode can still be used for local UI development.

---

# 33. Keep all backend communication centralized

Do not put:

```text
fetch(...)
```

directly inside React pages/components.

All backend calls should go through:

```text
src/api/
```

Prefer this structure:

```text
src/api/
  client.ts
  realApi.ts
  record.ts
  documents.ts
  plan.ts
  medicine.ts
  labs.ts
  ...
```

Components should call functions such as:

```text
getRecord()
getDocument()
createDocument()
uploadDocument()
markPlanDone()
generateCarePlan()
submitSubstitution()
interpretLabs()
updateRecordField()
```

---

# 34. Remove fake behavior from the real API path

When:

```text
VITE_USE_MOCK_API=false
```

the following must NOT happen:

```text
fake delays
console.log("Mock uploading")
fake document pages
fake medicine results
fake care-plan results
hardcoded today/morning
filename treated as medicine brand
```

Mock behavior may remain under:

```text
VITE_USE_MOCK_API=true
```

but real mode must use the actual backend.

---

# 35. Do not add unsupported backend assumptions

If a value is not in the backend contract:

```text
do not invent it
```

Examples:

```text
DOB
care team
allergies
current episode
document GET list endpoint
medicine scan endpoint
detected medicine object
```

If the frontend design contains these concepts but the backend does not provide them, either:

1. remove/disable the unsupported display, or
2. derive it only from existing canonical backend data when that is legitimately possible.

Never fabricate clinical data.

---

# 36. Keep the existing UI where possible

Do not redesign the entire application.

Preserve:

```text
Timeline
Documents
Document Detail
Medicine Scanner
Previous Scans
Medicine Result
Profile
Authentication
Navigation
```

Modify the data wiring and components only where necessary to support the fixed backend.

The objective is:

```text
same frontend
+
correct backend integration
```

not:

```text
new frontend
```

---

# 37. Required API layer after implementation

The frontend API layer should conceptually expose at least:

```ts
getRecord()

updateRecordField()

getDocument(id)

createDocument(request)

uploadDocument(file)

markPlanDone(day, slot)

generateCarePlan()

submitSubstitution(request)

interpretLabs()
```

For document listing:

```text
DO NOT create getDocuments() that calls GET /documents.
```

Instead:

```text
getRecord().documents
```

For previous medicine scans:

```text
DO NOT create getPreviousScans() that calls /medicine/scans.
```

Instead derive them from:

```text
getRecord().documents
```

---

# 38. Required frontend data flow

## Patient record

```text
GET /record
      ↓
adapter
      ↓
PatientRecord UI model
      ↓
Timeline/Profile/Documents/Medicine
```

## Document upload

```text
POST /documents
      ↓
doc_id + upload_url
      ↓
PUT file to upload_url
      ↓
GET /documents/{doc_id}
      ↓
page_urls + status
```

## Clinical provenance

```text
GET /record
      ↓
medications / diagnoses / labs / plans
      ↓
provenance.source.doc_id
      ↓
GET /documents/{id}
      ↓
page_urls
      ↓
real page image
      ↓
bbox overlay
```

## Care plan

```text
POST /plan/generate
      ↓
backend generates plan
      ↓
GET /record
      ↓
plan_entries
      ↓
Timeline
```

## Mark done

```text
user clicks Mark Done
      ↓
POST /plan/{day}/{slot}/done
      ↓
GET /record
      ↓
updated Timeline
```

## Medicine scanner

```text
camera image
      ↓
POST /documents
      ↓
PUT image to presigned S3 URL
      ↓
GET /documents/{doc_id}
      ↓
POST /substitution { doc_id }
      ↓
substitution result
```

## Lab interpretation

```text
GET /record
      ↓
POST /labs/interpret
      ↓
LabInterpretationReport
      ↓
Lab UI
```

---

# 39. TypeScript quality requirements

Update:

```text
src/types/api.ts
```

so types represent the actual backend contract.

Do not solve type mismatches with:

```ts
any
```

unless the backend truly returns arbitrary data.

Avoid excessive:

```ts
as SomeType
```

casts.

Prefer explicit adapters and runtime checks where useful.

---

# 40. Validation requirements

After implementation:

```bash
npm run build
```

must pass.

Also run:

```bash
npm run lint
```

and fix frontend errors introduced by the changes.

Do not modify backend code to make frontend tests/builds pass.

---

# 41. Final acceptance checklist

The implementation is complete only when all of these are true:

### Authentication

- [ ] Cognito login still works.
- [ ] Real API calls include the Cognito JWT.
- [ ] API URL comes from environment configuration.

### Record

- [ ] `/record` is consumed using the canonical backend response.
- [ ] Patient ID/name/age/sex/language/phone are mapped correctly.
- [ ] `profile_complete` is handled.
- [ ] No DOB is fabricated.

### Documents

- [ ] No frontend call to `GET /documents`.
- [ ] Document list comes from `/record`.
- [ ] `POST /documents` is used to create uploads.
- [ ] Presigned S3 PUT upload actually happens.
- [ ] `GET /documents/{id}` is used for status.
- [ ] All backend document statuses are supported.
- [ ] Real `page_urls` are displayed.
- [ ] Fake document content is removed from real mode.
- [ ] Multiple pages can be displayed.
- [ ] Polling stops on terminal status.

### Provenance

- [ ] Provenance is preserved.
- [ ] `doc_id`, `page`, `bbox`, `verbatim`, `confidence`, and status are handled.
- [ ] Bbox conversion uses `[ymin, xmin, ymax, xmax]`.
- [ ] Real page image is used for highlighting.
- [ ] No sourced clinical value is replaced with fabricated content.

### Review

- [ ] `needs_review` is shown.
- [ ] Review uses the exact editable backend field.
- [ ] PATCH payload uses `sk`, `field`, `value`.
- [ ] Successful correction refreshes the record.
- [ ] Confidence threshold remains 0.85.

### Care plan

- [ ] `plan_entries` map correctly to the Timeline.
- [ ] Day uses backend `day_index`.
- [ ] All four slots work.
- [ ] Mark Done uses the actual day and slot.
- [ ] No hardcoded `today/morning`.
- [ ] No JSON body is sent to Mark Done unless backend requires it.
- [ ] `/plan/generate` is available from the frontend.
- [ ] Backend-generated alerts/rules are displayed rather than recreated.

### Medicine

- [ ] Camera image is actually uploaded.
- [ ] Filename is NOT treated as medicine brand.
- [ ] Substitution uses `doc_id` after scan upload, or real `brand + strength`.
- [ ] Backend substitution response is mapped correctly.
- [ ] NTI blocks are respected.
- [ ] Interaction strings render correctly.
- [ ] No `/medicine/scans` request exists.
- [ ] Previous scans are derived from `/record.documents`.

### Labs

- [ ] `/labs/interpret` is connected.
- [ ] Top findings render.
- [ ] Abnormal count renders.
- [ ] Reference ranges render.
- [ ] Explanations render.
- [ ] Diagnosis/medication context renders.
- [ ] Cross-module alerts render.
- [ ] Provenance is preserved.

### Errors

- [ ] Structured backend errors are parsed.
- [ ] User-friendly messages are displayed.
- [ ] No raw stack traces are shown.

### Architecture

- [ ] All real API calls stay inside `src/api`.
- [ ] No API URLs are hardcoded into components.
- [ ] `VITE_USE_MOCK_API=true` still supports mock mode where applicable.
- [ ] `VITE_USE_MOCK_API=false` uses only the real backend.
- [ ] No backend files were modified.
- [ ] No backend endpoints were added.
- [ ] No backend behavior was changed.

### Build

- [ ] `npm run build` passes.
- [ ] `npm run lint` passes.
- [ ] No TypeScript errors remain.

---

# 42. IMPORTANT IMPLEMENTATION PRINCIPLE

When you encounter an inconsistency:

```text
DO NOT change the backend.
DO NOT invent an endpoint.
DO NOT invent data.
DO NOT fabricate clinical information.
DO NOT silently change the backend contract.
```

Instead:

```text
READ the existing backend response
        ↓
ADAPT it in the frontend API layer
        ↓
UPDATE frontend types
        ↓
UPDATE affected UI components
        ↓
TEST against the fixed contract
```

The backend is the authority.

The frontend must conform to it.

---

# 43. Final instruction to the coding agent

Implement all frontend changes described in this document.

Before editing:

1. Inspect the entire existing frontend.
2. Inspect the backend contracts/routes only for reference.
3. Do not modify any backend file.
4. Identify the current frontend-to-backend mismatches.
5. Implement the frontend adapters and UI changes systematically.

After editing:

1. Search the frontend for obsolete endpoints:
   - `/documents` GET
   - `/medicine/scans`
2. Search for hardcoded:
   - `today/morning`
   - `file.name` being sent as a medicine brand
   - mock document content in real mode
3. Search for direct `fetch()` calls outside the API layer.
4. Run:
   ```bash
   npm run build
   npm run lint
   ```
5. Fix all frontend errors.
6. Verify that no backend file has been modified.

## Final rule

**ONLY CHANGE THE FRONTEND.**

If something appears impossible because of the backend contract, solve it on the frontend by adapting to the existing contract. Do not modify the backend to make the frontend easier.
