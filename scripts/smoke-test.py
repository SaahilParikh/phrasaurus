#!/usr/bin/env python3
"""End-to-end smoke test against a deployed phrasaurus Lambda.

Usage:
    python3 scripts/smoke-test.py <lambda-url> [--phrase "…"]

Exits 0 on success, 1 on any failure. Intended as a post-deploy check:

    make package
    # ...upload backend/build/phrasaurus-lambda.zip to your Lambda...
    make smoke-test URL=https://abcdef.lambda-url.us-east-1.on.aws/

Only uses the Python stdlib so no venv setup is needed. This is the
integration layer our unit tests can't cover:

    - IAM role actually has bedrock:InvokeModel on the model ARN
    - Bedrock model access is enabled in the account / region
    - CORS preflight responds from the live endpoint
    - The deployed handler returns a well-formed synonym

Costs one Bedrock Converse call per invocation (pennies with Haiku).
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any

DEFAULT_PHRASE = "a minimalistic thesaurus for phrases"
TIMEOUT_SECONDS = 15


def smoke_test(url: str, phrase: str) -> int:
    """Run one synonym request and one CORS preflight. Return 0 on success."""
    if not _check_preflight(url):
        return 1
    if not _check_synonym(url, phrase):
        return 1
    print("\n✅ Smoke test passed.")
    return 0


def _check_preflight(url: str) -> bool:
    """Assert that OPTIONS returns CORS headers. Catches misconfigured
    Function URLs / API Gateway routes."""
    print(f"→ OPTIONS {url}")
    request = urllib.request.Request(
        url,
        method="OPTIONS",
        headers={
            "Origin": "https://smoke.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            status = response.status
            allow_origin = response.headers.get("Access-Control-Allow-Origin")
    except urllib.error.HTTPError as exc:
        # API Gateway may return the CORS response as an error status in some
        # configs — still acceptable if the header is present.
        status = exc.code
        allow_origin = exc.headers.get("Access-Control-Allow-Origin") if exc.headers else None
    except urllib.error.URLError as exc:
        print(f"  ✗ Request failed: {exc}")
        return False

    if status not in (200, 204):
        print(f"  ✗ Expected 200/204, got {status}")
        return False
    if not allow_origin:
        print("  ✗ Missing Access-Control-Allow-Origin header")
        return False
    print(f"  ✓ {status}, Access-Control-Allow-Origin: {allow_origin}")
    return True


def _check_synonym(url: str, phrase: str) -> bool:
    """Assert that a real phrase request round-trips through Bedrock."""
    print(f"→ POST {url}  {{ phrase: {phrase!r} }}")
    body = json.dumps({"phrase": phrase}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            status = response.status
            payload: Any = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Read the body so the user sees what the Lambda returned.
        detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        print(f"  ✗ HTTP {exc.code}: {detail[:500]}")
        return False
    except urllib.error.URLError as exc:
        print(f"  ✗ Request failed: {exc}")
        return False
    except json.JSONDecodeError as exc:
        print(f"  ✗ Response was not JSON: {exc}")
        return False

    if status != 200:
        print(f"  ✗ Expected 200, got {status}: {payload}")
        return False
    if not isinstance(payload, dict) or not isinstance(payload.get("synonym"), str):
        print(f"  ✗ Expected {{'synonym': <string>}}, got {payload}")
        return False
    if not payload["synonym"].strip():
        print("  ✗ Empty synonym")
        return False

    print(f"  ✓ {status}  synonym: {payload['synonym']!r}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("url", help="Lambda Function URL or API Gateway endpoint")
    parser.add_argument(
        "--phrase",
        default=DEFAULT_PHRASE,
        help=f"Phrase to request a synonym for (default: {DEFAULT_PHRASE!r})",
    )
    args = parser.parse_args()
    return smoke_test(args.url, args.phrase)


if __name__ == "__main__":
    sys.exit(main())
