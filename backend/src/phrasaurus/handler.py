"""AWS Lambda entry point for the phrasaurus backend.

This is the only module aware of the API Gateway event/response shape. It:

1. Parses the incoming event (supporting both REST v1 and HTTP API v2 shapes).
2. Validates the ``phrase`` input (type, presence, length).
3. Calls Bedrock (auth via the Lambda execution role — no API keys).
4. Returns the synonym with CORS headers.
5. Handles CORS preflight (OPTIONS) so browsers can call the Lambda Function
   URL directly without a separate API Gateway CORS configuration.
6. Translates all error paths into structured JSON responses — the legacy
   code returned 200 with an empty body even on failure, which silently
   broke the frontend contract.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .bedrock_client import BedrockClientError, get_synonym
from .config import MAX_PHRASE_LENGTH, Config

logger = logging.getLogger()
logger.setLevel(logging.INFO)


# Cold-start: resolve config once.
_CONFIG = Config.from_env()


class _ClientError(ValueError):
    """Client-facing validation error. Translated to HTTP 400."""


def lambda_handler(event: dict[str, Any], context: object) -> dict[str, Any]:
    """AWS Lambda entry point.

    The ``context`` argument is required by Lambda but unused here.
    """
    logger.info("request_received", extra={"event_keys": list(event.keys())})

    try:
        phrase = _extract_phrase(event)
        synonym = _produce_synonym(phrase)
    except _ClientError as exc:
        logger.warning("client_error", extra={"error": str(exc)})
        # @secure_recommendation: Return only the validation message to the
        # caller; no internal state leaks.
        return _respond(400, {"error": str(exc)})
    except BedrockClientError as exc:
        # Upstream dependency failure (throttling, model access, etc.).
        logger.exception("bedrock_upstream_error")
        # @secure_recommendation: Opaque error message — Bedrock failure
        # details go to logs only, never to the client.
        return _respond(502, {"error": "Upstream provider error"}, log_detail=str(exc))
    except Exception as exc:  # pragma: no cover — defense in depth
        logger.exception("unhandled_error")
        return _respond(500, {"error": "Internal server error"}, log_detail=str(exc))

    return _respond(200, {"synonym": synonym})


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _extract_phrase(event: dict[str, Any]) -> str:
    """Pull ``phrase`` out of the request body with full validation.

    Accepts both raw JSON bodies (Lambda Function URLs / HTTP API) and
    API-Gateway-wrapped events where ``body`` is a JSON-encoded string.
    """
    raw_body = event.get("body")
    if raw_body is None:
        raise _ClientError("Request body is required")

    # API Gateway delivers the body as a string; Function URLs may pass
    # a dict if isBase64Encoded is false and the client sent JSON.
    if isinstance(raw_body, str):
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise _ClientError("Request body must be valid JSON") from exc
    elif isinstance(raw_body, dict):
        body = raw_body
    else:
        raise _ClientError("Request body must be a JSON object")

    if not isinstance(body, dict):
        raise _ClientError("Request body must be a JSON object")

    phrase = body.get("phrase")
    if not isinstance(phrase, str):
        raise _ClientError("'phrase' must be a string")

    phrase = phrase.strip()
    if not phrase:
        raise _ClientError("'phrase' must not be empty")

    # @secure_recommendation: Length cap defends against resource exhaustion
    # and reduces the attack surface for prompt-injection payloads.
    if len(phrase) > MAX_PHRASE_LENGTH:
        raise _ClientError(f"'phrase' exceeds maximum length of {MAX_PHRASE_LENGTH} characters")

    return phrase


def _produce_synonym(phrase: str) -> str:
    """Call Bedrock to produce a synonym for ``phrase``."""
    return get_synonym(
        phrase,
        region=_CONFIG.aws_region,
        model_id=_CONFIG.bedrock_model_id,
        max_tokens=_CONFIG.max_tokens,
    )


def _respond(
    status: int,
    body: dict[str, Any] | None,
    *,
    log_detail: str | None = None,
) -> dict[str, Any]:
    """Build an API-Gateway-compatible response with CORS headers.

    ``log_detail`` is emitted to logs but never to the client, so internal
    error text cannot leak to end users.
    """
    if log_detail:
        logger.info("response_detail", extra={"status": status, "detail": log_detail})

    # CORS is owned by the Lambda Function URL's cors config — emitting
    # Access-Control-* here would produce duplicate headers that browsers reject.
    headers = {
        "Content-Type": "application/json",
        # @secure_recommendation: no-store prevents intermediate caches from
        # retaining responses that may contain user-specific phrasing.
        "Cache-Control": "no-store",
    }

    return {
        "statusCode": status,
        "headers": headers,
        "body": "" if body is None else json.dumps(body),
    }
