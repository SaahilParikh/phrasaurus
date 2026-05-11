"""Unit tests for phrasaurus.config."""

from __future__ import annotations

import pytest

from phrasaurus.config import MAX_PHRASE_LENGTH, Config


def test_from_env_uses_defaults_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "AWS_REGION",
        "BEDROCK_MODEL_ID",
        "BEDROCK_MAX_TOKENS",
    ):
        monkeypatch.delenv(var, raising=False)

    cfg = Config.from_env()

    assert cfg.aws_region == "us-east-1"
    # Default points at a cross-region inference profile so it works
    # out of the box in the common case.
    assert cfg.bedrock_model_id.startswith("us.")
    assert cfg.max_tokens == 60


def test_from_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "us.amazon.nova-micro-v1:0")
    monkeypatch.setenv("BEDROCK_MAX_TOKENS", "120")

    cfg = Config.from_env()

    assert cfg.aws_region == "eu-west-1"
    assert cfg.bedrock_model_id == "us.amazon.nova-micro-v1:0"
    assert cfg.max_tokens == 120


def test_config_is_immutable() -> None:
    cfg = Config.from_env()
    with pytest.raises(AttributeError):
        cfg.aws_region = "eu-west-1"  # type: ignore[misc]


def test_max_phrase_length_is_reasonable() -> None:
    # Guardrail so we don't accidentally widen the limit to something absurd.
    assert 50 <= MAX_PHRASE_LENGTH <= 1000
