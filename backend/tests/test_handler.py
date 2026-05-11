"""Unit tests for phrasaurus.handler — the Lambda entry point."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from phrasaurus import handler as handler_module
from phrasaurus.bedrock_client import BedrockClientError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _event(
    body: Any = None,
    *,
    method: str = "POST",
    v2: bool = False,
) -> dict[str, Any]:
    """Build an API Gateway / Function URL event.

    ``v2=True`` produces the HTTP API v2 shape (requestContext.http.method);
    otherwise the REST v1 shape (httpMethod).
    """
    event: dict[str, Any] = {
        "body": body if isinstance(body, str) or body is None else json.dumps(body)
    }
    if v2:
        event["requestContext"] = {"http": {"method": method}}
    else:
        event["httpMethod"] = method
    return event


def _patch_synonym(return_value: str):  # type: ignore[no-untyped-def]
    return patch("phrasaurus.handler.get_synonym", return_value=return_value)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_post_returns_200_with_synonym_and_cors_headers() -> None:
    event = _event({"phrase": "green monkey"})

    with _patch_synonym("emerald primate"):
        response = handler_module.lambda_handler(event, object())

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {"synonym": "emerald primate"}

    headers = response["headers"]
    assert headers["Content-Type"] == "application/json"
    # CORS is owned by Function URL config, not by the handler.
    assert "Access-Control-Allow-Origin" not in headers
    assert headers["Cache-Control"] == "no-store"


def test_post_accepts_http_api_v2_event_shape() -> None:
    event = _event({"phrase": "hello"}, v2=True)

    with _patch_synonym("greeting"):
        response = handler_module.lambda_handler(event, object())

    assert response["statusCode"] == 200


def test_post_accepts_dict_body_from_function_url() -> None:
    event = {"httpMethod": "POST", "body": {"phrase": "foo"}}

    with _patch_synonym("bar"):
        response = handler_module.lambda_handler(event, object())

    assert response["statusCode"] == 200
    assert json.loads(response["body"])["synonym"] == "bar"


def test_handler_passes_config_values_through_to_bedrock() -> None:
    """Regression: ensure the handler actually forwards config to Bedrock."""
    event = _event({"phrase": "x"})

    with patch("phrasaurus.handler.get_synonym", return_value="y") as mock_call:
        handler_module.lambda_handler(event, object())

    _args, kwargs = mock_call.call_args
    assert "region" in kwargs
    assert "model_id" in kwargs
    assert "max_tokens" in kwargs


# ---------------------------------------------------------------------------
# Validation — 400s
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "expected_fragment"),
    [
        (None, "required"),
        ("not json at all", "valid JSON"),
        ({"phrase": ""}, "empty"),
        ({"phrase": "   "}, "empty"),
        ({"phrase": 123}, "string"),
        ({}, "string"),
        ({"phrase": "a" * 281}, "maximum length"),
    ],
)
def test_validation_errors_return_400(body: Any, expected_fragment: str) -> None:
    event = _event(body)

    response = handler_module.lambda_handler(event, object())

    assert response["statusCode"] == 400
    payload = json.loads(response["body"])
    assert expected_fragment.lower() in payload["error"].lower()


def test_body_at_length_boundary_is_accepted() -> None:
    event = _event({"phrase": "a" * 280})

    with _patch_synonym("short"):
        response = handler_module.lambda_handler(event, object())

    assert response["statusCode"] == 200


# ---------------------------------------------------------------------------
# Upstream errors
# ---------------------------------------------------------------------------


def test_bedrock_error_becomes_502() -> None:
    event = _event({"phrase": "hello"})

    with patch(
        "phrasaurus.handler.get_synonym",
        side_effect=BedrockClientError("throttled — rate limited"),
    ):
        response = handler_module.lambda_handler(event, object())

    assert response["statusCode"] == 502
    assert "upstream" in json.loads(response["body"])["error"].lower()
    # Internal detail must not leak to the client.
    assert "rate limited" not in response["body"]
    assert "throttled" not in response["body"]
