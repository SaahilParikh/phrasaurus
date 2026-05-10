# Contributing

Small project, short rules.

## Development workflow

```bash
make install    # install backend + frontend deps
make lint       # lint + format check
make typecheck  # mypy on the backend
make test       # pytest (backend) + vitest (frontend)
make format     # auto-fix formatting
```

All of the above run in CI on every pull request. Keep them green.

## Style

- **Python**: ruff-formatted, type-annotated, strict-mypy-clean. Prefer
  small modules with one responsibility. Keep I/O (AWS, OpenAI, Lambda
  event shape) isolated from business logic — this is what makes the code
  testable.
- **JavaScript**: prettier-formatted, ES modules, no framework, no
  bundler. Pure functions go in their own files so they can be unit-tested
  without a DOM.

## Tests

- New backend features: add a pytest test. Use `moto` for AWS stubs,
  `unittest.mock` for OpenAI. Aim to keep coverage at ≥ 90%.
- New pure JS helpers: add a vitest test.
- DOM wiring in `app.js` is deliberately not unit-tested — if a change
  warrants it, add a Playwright smoke test rather than a jsdom simulation.

## Commits

- Atomic commits. One concern per commit.
- Imperative subject line, ≤ 72 chars.
- Reference the behaviour you are changing, not the files you touched.

## Secrets

Never commit API keys. The OpenAI credentials live in AWS Secrets Manager
and are pulled at runtime; see README for the expected schema.
