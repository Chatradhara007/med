# CareThread

A patient-side record for one episode of care.

A discharge summary, an outpatient lab report and a pharmacy stockout are
treated as **one connected episode belonging to one person in the same week**,
not as three separate tools. The discharge summary establishes the baseline,
lab reports are read against that baseline, and substitutions are checked
against the active medication list.

**The one invariant: no value reaches the UI without a source.** Every
extracted field carries a citation to the region of the document it came from,
and nothing is inferred from medical knowledge.

CareThread does not diagnose, does not prescribe and does not give clinical
advice. It restructures, translates and cross-references what a clinician
already wrote.

## Layout

```
carethread/
├── shared/          # frozen contracts, repository, storage, auth, Bedrock, prompts
├── pipeline/        # M1 ingest: rasterise → classify → extract → validate → gate → persist
├── modules/         # M2 care plan · M3 lab interpreter · M4 substitution · M5 reminders
├── api/             # REST handlers and the unified router
├── data/            # curated drug index, NTI list, reference ranges
├── infra/           # SAM template
└── tests/           # 231 tests
```

## Local development

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest carethread/tests -q
```

The suite runs with no AWS credentials and no network access.

To exercise the API locally against in-memory adapters:

```bash
export USE_IN_MEMORY_REPO=true
export USE_IN_MEMORY_STORAGE=true
export ALLOW_MOCK_AUTH=true       # then send an X-Patient-Id header
export USE_MOCK_BEDROCK=true      # scripted model responses
export USE_MOCK_AWS=true          # in-memory scheduler and publisher
```

Every one of these is **ignored inside a deployed Lambda**. A deployed function
always uses real DynamoDB, S3, Cognito, Bedrock, EventBridge Scheduler and SNS,
so it can never silently serve fixture data.

## Deploy

```bash
cd carethread/infra
sam build && sam deploy --guided
```

Set these parameters:

- `BedrockModelId` — the newest multimodal Claude model enabled in your account.
- `WebOrigin` — the Amplify domain, so CORS is not a wildcard.
- `DemoMode` — `true` compresses a reminder "day" to 30 seconds.
- `CallbackUrl` / `LogoutUrl` — where the Cognito hosted UI returns the user.
- `HostedUiPrefix` — must be globally unique in the region.

Copy the stack outputs (`ApiUrl`, `UserPoolId`, `ClientId`, `HostedUiUrl`) into
the web app's `.env`. None of them are secrets.

### Bedrock access

Request access to the model in the Bedrock console for your region before the
first upload. The classify and extract states fail with a clear reason if the
model is not enabled.

### PDF rasterisation

The `RasteriseFn` needs a PDF renderer (PyMuPDF, or pdf2image with poppler) in
its layer. Without one, PDF uploads are marked `unsupported` with a message the
patient can act on, rather than failing silently. Camera photos need no extra
layer.

## The ingest pipeline

One Step Functions execution per uploaded document:

```
Rasterise → Classify → RouteByType ─┬→ ExtractX → ValidateSchema → GateConfidence
                                    │                                    ↓
                                    └→ MarkUnsupported          PersistEntities → MarkReady
```

- **Classify** may answer `unknown`, which is a correct outcome. The document is
  marked `unsupported` with a clear message rather than routed to the wrong
  extractor.
- **ValidateSchema** re-prompts once with the validation errors appended. This
  roughly halves extraction failures.
- **GateConfidence** splits fields at 0.85: at or above becomes `confirmed`,
  below stays `needs_review` as an amber chip the patient resolves.
- Any failure routes to `HandleFailure`, which sets the document to `failed`
  with a single-line, patient-facing reason — never a stack trace.

## Safety rails

| Rail | Where it is enforced |
| :--- | :--- |
| No new clinical advice | Extraction prompts forbid inference |
| Escalation triggers are deterministic | `rules.yaml`, never model-generated |
| NTI drugs are never substituted | Hard block from `data/nti.csv`, checked before any model call |
| Interaction checks are advisory | Copy reads "ask your pharmacist about" |
| Nothing shown without provenance | Enforced at the serialiser |
| Unknown documents are rejected | `unsupported` status with a clear message |
| Data isolation | `patient_id` from the JWT `sub` claim only |
| No PHI in notifications | `assert_no_phi()` on every delivery path, backed by the drug index |

## API

| Method | Path | Purpose |
| :--- | :--- | :--- |
| `POST` | `/documents` | Register metadata, return a presigned S3 PUT URL |
| `GET` | `/documents/{id}` | Ingestion status and rasterised pages |
| `GET` | `/record` | Full canonical record from one partition query |
| `PATCH` | `/record/{field}` | Allowlisted field edit; resolves a `needs_review` chip |
| `POST` | `/substitution` | Bioequivalent screening, NTI block, interaction cross-check |
| `POST` | `/plan/{day}/{slot}/done` | Confirm adherence, suppress that reminder |
| `POST` | `/plan/generate` | Compile the 7-day care plan |
| `POST` | `/labs/interpret` | Deterministic lab analysis against reference intervals |

All endpoints authenticate through the Cognito JWT authorizer. `patient_id`
comes from the `sub` claim and is never accepted from the request body.

### Notes for the web app

- **Sign-in** uses the Cognito hosted UI (authorization code + PKCE, no client
  secret). The sign-in page is the `HostedUiUrl` stack output. Set the
  `CallbackUrl` and `LogoutUrl` parameters to your Amplify URL at deploy time.
- **First `GET /record`** seeds a profile from the JWT claims, so `patient` is
  never null. It returns `profile_complete: false` until the patient supplies
  the age, sex and phone a token cannot carry — prompt for these and submit
  them with `PATCH /record/{field}` against `sk: "PROFILE"`.
- **`GET /documents/{id}`** returns `page_urls` alongside `pages`, index
  aligned. The bucket blocks public access, so these presigned URLs are the
  only way to render a scan or draw a bbox overlay. They expire in 15 minutes;
  re-fetch rather than caching them.
- **`POST /plan/generate`** also schedules the reminders and reports
  `reminders_scheduled`. A zero there means the plan was saved but the reminder
  channel is unconfigured.
- **`bbox` is `[ymin, xmin, ymax, xmax]` on a 0-1000 grid** — Y first, not
  pixels, not `[x, y, w, h]`. Scale to the rendered image size.
- **Document status is a ten-state machine.** Poll `GET /documents/{id}` and
  handle `unsupported`, `failed` and `review_required`, not just `ready`;
  `error` carries a message that is safe to show the patient.
- **Some fields read `"not stated"`.** A dose absent from the document is never
  inferred. Render it as an amber `needs_review` chip, not as literal text.

See `ARCHITECTURE.md` for the system design, `CONTRACTS.md` for the frozen data
contracts, and `BUILD_STATUS.md` for current status and the defect log.
