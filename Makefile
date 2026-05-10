# phrasaurus — top-level developer commands.
#
# Usage:
#   make install      # install backend dev deps + frontend node modules
#   make lint         # lint backend + frontend
#   make format       # auto-format backend + frontend
#   make test         # run all tests
#   make typecheck    # mypy on backend
#   make package      # build the Lambda deployment zip under backend/build/
#   make serve        # serve the frontend locally on :8000
#   make clean        # remove build artefacts

.PHONY: install lint format test typecheck package serve smoke-test clean \
        backend-install backend-lint backend-format backend-test backend-typecheck backend-package \
        frontend-install frontend-lint frontend-format frontend-test

PYTHON ?= python3

# ------------------------------------------------------------------ install

install: backend-install frontend-install

backend-install:
	cd backend && $(PYTHON) -m pip install -r requirements.txt -r requirements-dev.txt

frontend-install:
	cd frontend && npm install

# ------------------------------------------------------------------ lint / format

lint: backend-lint frontend-lint

format: backend-format frontend-format

backend-lint:
	cd backend && $(PYTHON) -m ruff check src tests
	cd backend && $(PYTHON) -m ruff format --check src tests

backend-format:
	cd backend && $(PYTHON) -m ruff format src tests
	cd backend && $(PYTHON) -m ruff check --fix src tests

frontend-lint:
	cd frontend && npm run lint

frontend-format:
	cd frontend && npm run format

# ------------------------------------------------------------------ test

test: backend-test frontend-test

backend-test:
	cd backend && $(PYTHON) -m pytest

frontend-test:
	cd frontend && npm test

# ------------------------------------------------------------------ typecheck

typecheck: backend-typecheck

backend-typecheck:
	cd backend && $(PYTHON) -m mypy src

# ------------------------------------------------------------------ package

package: backend-package

# Builds a Lambda deployment zip at backend/build/phrasaurus-lambda.zip.
#
# With Bedrock as the only upstream, we have NO runtime dependencies that
# aren't already in the Lambda Python runtime — boto3 is provided by AWS.
# So the zip is just our ~15 KB of source code. Nothing to vendor.
backend-package:
	rm -rf backend/build
	mkdir -p backend/build/pkg
	cp -R backend/src/phrasaurus backend/build/pkg/phrasaurus
	cd backend/build/pkg && zip -rq ../phrasaurus-lambda.zip . -x "*.pyc" "__pycache__/*"
	@echo "Built backend/build/phrasaurus-lambda.zip"
	@ls -lh backend/build/phrasaurus-lambda.zip

# ------------------------------------------------------------------ serve

# Serves the frontend on :8000 so you can click around without deploying.
serve:
	cd frontend/src && $(PYTHON) -m http.server 8000

# ------------------------------------------------------------------ smoke-test

# Runs a post-deploy smoke test against a live Lambda endpoint.
# Usage:
#   make smoke-test URL=https://abcdef.lambda-url.us-east-1.on.aws/
#   make smoke-test URL=https://… PHRASE="my test phrase"
#
# Costs one Bedrock call. Not part of `make test` because it requires a
# deployed endpoint and real AWS billing.
PHRASE ?= a minimalistic thesaurus for phrases
smoke-test:
	@if [ -z "$(URL)" ]; then \
	    echo "Usage: make smoke-test URL=<lambda-url> [PHRASE='…']"; \
	    exit 1; \
	fi
	$(PYTHON) scripts/smoke-test.py "$(URL)" --phrase "$(PHRASE)"

# ------------------------------------------------------------------ clean

clean:
	rm -rf backend/build backend/.pytest_cache backend/.mypy_cache backend/.ruff_cache
	rm -rf frontend/node_modules frontend/coverage
	find . -name '__pycache__' -type d -exec rm -rf {} +
