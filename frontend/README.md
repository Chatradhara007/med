# CareThread — web app

React + TypeScript + Vite. Talks to the deployed CareThread stack; there is no
mock layer and no offline mode.

## Run it

```bash
cd frontend
cp .env.example .env     # then fill in the stack outputs
npm install
npm run dev
```

**`.env` is gitignored, so a fresh clone has none** — that copy is step one,
and the copied file still needs its values. Without them the app cannot sign
in at all: the sign-in button throws `Auth UserPool not configured.` into the
console and nothing behind it ever loads.

If the app opens on a **"CareThread is not configured"** screen, it is telling
you which variables are missing and where each one comes from. Vite reads
`.env` once at startup, so restart the dev server after changing it.

### Where the values come from

```bash
aws cloudformation describe-stacks --stack-name carethread \
  --query "Stacks[0].Outputs" --output table
```

`.env.local` is also gitignored and takes precedence over `.env`, so use it
for per-developer overrides.

`VITE_COGNITO_DOMAIN` is the `HostedUiUrl` output **without** the `https://`
prefix. `VITE_REDIRECT_URI` is optional and defaults to the page origin plus a
trailing slash — Cognito matches callback URLs exactly, and the stack registers
them with that slash, so a bare origin is rejected as `redirect_mismatch`.

### On these values

None of them is a secret — they are public stack identifiers, and Vite inlines
them into the JavaScript bundle, so anyone who loads the app already has them.
No AWS access key belongs here: sign-in uses a Cognito token and uploads go to
presigned S3 URLs precisely so the browser never holds credentials.

## Checks

```bash
npm run lint
npx tsc --noEmit -p tsconfig.app.json
npm run build
```

## Layout

Feature-sliced. `src/features/<feature>/{pages,components}` for screens,
`src/api/` for the one network layer, `src/app/` for routing, auth and
providers.

- **`src/api/realApi.ts` is the only place `fetch` is called.** Components go
  through `apiClient`; nothing else talks to the network.
- **`src/config.ts`** reads and validates the environment once. `isConfigured`
  gates the whole app in `main.tsx`.

## Things the backend expects

- **Every patchable entity carries its own `sk`.** Read it off the entity from
  `GET /record` and send it back with `PATCH /record/field`. Never rebuild
  `MED#metformin` in the browser — the key normalisation is server-side.
- **`bbox` is `[ymin, xmin, ymax, xmax]` on a 0–1000 grid** — Y first, not
  pixels, not `[x, y, w, h]`. Scale to the rendered image size.
- **Document status is a ten-state machine.** Poll `GET /documents/{id}` and
  handle `unsupported`, `failed` and `review_required`, not just `ready`.
  `error` carries a message that is safe to show the patient.
- **`page_urls` expire in 15 minutes.** Re-fetch rather than caching them.
- **Some fields read `"not stated"`.** A value absent from the document is
  never inferred. Render it as an amber `needs_review` chip, not as text.
