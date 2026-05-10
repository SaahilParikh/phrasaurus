# phrasaurus

A minimalistic thesaurus for phrases. Type a word or phrase, get back a
synonymous phrase.

Two-tier app:

- **Frontend** — a static HTML/CSS/JS single page, served from any web host
  (S3, CloudFront, GitHub Pages, or `make serve` for local dev).
- **Backend** — an AWS Lambda function (Python 3.11+) that invokes Amazon
  Bedrock via the Converse API. Auth uses the Lambda execution role — there
  are no API keys or secrets to rotate.

```
┌───────────────┐        POST /api/v1        ┌───────────────────────┐
│  Browser      │ ─────────────────────────▶ │ Lambda Function URL   │
│  (static SPA) │     { "phrase": "…" }      │ (or API Gateway)      │
└───────────────┘                            └──────────┬────────────┘
        ▲                                               │
        │     { "synonym": "…" }                        ▼
        │                                   ┌───────────────────────┐
        │                                   │ Lambda (Python)       │
        │                                   │  phrasaurus.handler   │
        │                                   └──────────┬────────────┘
        │                                              │ IAM-signed
        │                                              ▼
        │                               ┌───────────────────────────┐
        │                               │ Amazon Bedrock            │
        │                               │  Converse API             │
        │                               │  (Claude 3.5 Haiku        │
        │                               │   cross-region profile)   │
        │                               └──────────┬────────────────┘
        │                                          │
        └────────────  rendered  ◀─────────────────┘
```

## Project layout

```
.
├── backend/                  AWS Lambda — Python
│   ├── src/phrasaurus/       package: config, bedrock_client, handler
│   ├── tests/                pytest unit tests (mocked boto3; no AWS required)
│   ├── pyproject.toml        ruff + mypy + pytest config
│   ├── requirements.txt      runtime deps (boto3 — provided by Lambda runtime)
│   └── requirements-dev.txt  dev/test tools
├── frontend/                 Static SPA — plain HTML/CSS/JS (no bundler)
│   ├── src/                  index.html, styles.css, config.js, api.js,
│   │                         placeholders.js, app.js
│   ├── tests/                vitest unit tests
│   ├── package.json          eslint + prettier + vitest
│   └── eslint.config.js
├── .github/workflows/ci.yml  GitHub Actions — lint + typecheck + test
└── Makefile                  top-level dev commands
```

## Local development

Prerequisites: Python 3.11+, Node 20+, GNU Make.

```bash
make install      # install backend + frontend deps
make lint         # lint + format check
make typecheck    # mypy on the backend
make test         # pytest (backend) + vitest (frontend)
make format       # auto-fix formatting
make serve        # serve the frontend on http://localhost:8000
```

For local development against a live backend, point the frontend at it by
injecting a config override into `frontend/src/index.html` before the app
script:

```html
<script>
  window.PHRASAURUS_CONFIG = { apiUrl: 'https://your-lambda-url.lambda-url…/' };
</script>
<script type="module" src="./app.js"></script>
```

## Backend configuration

All tunables are environment variables.

| Variable               | Default                                              | Meaning                                       |
| ---------------------- | ---------------------------------------------------- | --------------------------------------------- |
| `AWS_REGION`           | `us-east-1`                                          | Region hosting the Bedrock endpoint           |
| `BEDROCK_MODEL_ID`     | `us.anthropic.claude-3-5-haiku-20241022-v1:0`        | Bedrock model ID or cross-region profile      |
| `BEDROCK_MAX_TOKENS`   | `60`                                                 | Cap on tokens generated per call              |
| `CORS_ALLOWED_ORIGIN`  | `*`                                                  | `Access-Control-Allow-Origin` header value    |

### Choosing a model

The default is Claude 3.5 Haiku on a cross-region inference profile — fast,
cheap, and strong at short-form instruction following. Sensible alternatives:

- `us.amazon.nova-micro-v1:0` — lower cost, acceptable for short synonyms.
- `us.anthropic.claude-sonnet-4-6` — higher quality for nuanced phrases, higher cost.

List what's available in your region:

```bash
aws bedrock list-foundation-models --region us-east-1
aws bedrock list-inference-profiles --region us-east-1
```

You must also **enable model access** for the chosen model in the Bedrock
console (one-time, per-account, per-region) before the first invocation
will succeed.

### Always set `BEDROCK_MAX_TOKENS`

Leaving Bedrock's `maxTokens` unset reserves the model's full maximum
(e.g. 64 K for Claude) against your quota on every call — a common cause
of unexpected `ThrottlingException`. The handler passes a deliberate low
cap by default.

## Deploying the Lambda

```bash
make package
# -> backend/build/phrasaurus-lambda.zip  (~8 KB)
```

The zip contains only the `phrasaurus/` package — boto3 is provided by the
Lambda Python runtime, and there are no other runtime dependencies. Upload
to your Lambda function via the console, CLI, or your deploy tool of choice.

Set the handler to `phrasaurus.handler.lambda_handler`.

### IAM policy for the Lambda role

The function needs exactly one permission: invoke the chosen Bedrock model.
Scope the resource ARN to the specific model ID to follow least privilege:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel"],
      "Resource": [
        "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-haiku-20241022-v1:0",
        "arn:aws:bedrock:*::inference-profile/us.anthropic.claude-3-5-haiku-20241022-v1:0"
      ]
    }
  ]
}
```

When using a cross-region inference profile (the default), **both** the
inference-profile ARN and the underlying foundation-model ARN are required
— Bedrock validates access against both.

### Recommended follow-ups (not in this repo)

- **[Bedrock Guardrails](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html)**
  — a managed filter for prompt-injection, off-topic, and harmful content.
  Creating one requires AWS console work and a guardrail ID, so it's
  deliberately not checked in. If you create one, pass its ID via a new
  `BEDROCK_GUARDRAIL_ID` env var and thread it into the `converse()` call
  in `bedrock_client.py`.
- **CloudWatch log retention** — configure the Lambda's log group with a
  bounded retention (e.g. 30 days) to avoid indefinite log storage.

## Testing

Three layers, each catching different classes of bugs:

1. **Unit tests** — `make test`.
   - Backend: `pytest` with ~97% line coverage. No network, no AWS creds;
     boto3 is stubbed via `unittest.mock`.
   - Frontend: `vitest` against the pure modules (`config.js`,
     `placeholders.js`, `api.js`). The DOM wiring in `app.js` is not
     unit-tested; integration-testing a 200-line SPA isn't worth the
     dependency weight.
2. **Handler integration tests** — part of `make test`. Drive
   `lambda_handler` with realistic API-Gateway-v1 and HTTP-API-v2 event
   shapes, mocking only the Bedrock call. Catches event-parsing bugs and
   frontend/backend contract mismatches without leaving the process.
3. **Deployed smoke test** — `make smoke-test URL=<lambda-url>`.
   Runs one real POST (and one CORS preflight) against your deployed
   endpoint. Catches IAM misconfiguration, missing Bedrock model access,
   and regional-availability problems that mocks can't. Costs one Bedrock
   call (fractions of a cent with Haiku). Not part of CI — CI has no AWS
   credentials and no Bedrock entitlement.

```bash
# After a deploy:
make smoke-test URL=https://abcdef.lambda-url.us-east-1.on.aws/
# Optionally override the phrase:
make smoke-test URL=https://… PHRASE="my test phrase"
```

True browser-in-the-loop E2E (Playwright against a deployed stack) is
possible but not included — for a page this small the smoke test plus
the handler integration tests cover the bugs that matter.

## What changed from the original

This repo was revived in 2026. The previous version had several bugs that
prevented the frontend from getting a real response, plus ~10 MB of
vendored pip packages checked into git. The fixes:

- Migrated from the OpenAI API to **Amazon Bedrock** (Claude 3.5 Haiku via
  the Converse API). Eliminates the OpenAI API key, Secrets Manager
  dependency, and all OpenAI-related vendored packages. Auth now uses the
  Lambda execution role.
- Removed `lambda_package/` vendored dependency tree. With Bedrock there
  are no runtime dependencies that aren't already in the Lambda Python
  runtime — the deployment zip shrank from ~10 MB to ~8 KB.
- Fixed the module-level `messages` list that grew unbounded across warm
  Lambda invocations and leaked context between unrelated requests.
- Fixed `lambda_handler` to actually parse the incoming event and return
  the synonym in the response body (previously hardcoded input, empty
  body out).
- Added CORS headers so the browser fetch works.
- Replaced deprecated `document.execCommand('copy')` with
  `navigator.clipboard.writeText`.
- Removed unused jQuery, Popper, and Bootstrap JS (only a couple of CSS
  utility classes were in use; they were replaced with plain CSS).
- Introduced input validation (type, presence, length) and structured
  error responses.
- Added ruff / mypy / pytest for the backend and eslint / prettier /
  vitest for the frontend, plus GitHub Actions CI.

## License

MIT. See `LICENSE`.
