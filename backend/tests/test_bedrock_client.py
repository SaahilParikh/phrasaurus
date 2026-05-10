"""Unit tests for phrasaurus.bedrock_client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import BotoCoreError, ClientError

from phrasaurus.bedrock_client import (
    BedrockClientError,
    build_messages,
    build_system_prompts,
    get_synonym,
)

# ---------------------------------------------------------------------------
# build_messages / build_system_prompts: pure functions
# ---------------------------------------------------------------------------


def test_system_prompt_has_converse_shape() -> None:
    prompts = build_system_prompts()
    assert isinstance(prompts, list)
    assert len(prompts) == 1
    assert "phrase thesaurus" in prompts[0]["text"]


def test_build_messages_ends_with_user_phrase_in_converse_shape() -> None:
    messages = build_messages("my brilliant phrase")
    last = messages[-1]
    assert last["role"] == "user"
    assert last["content"] == [{"text": "my brilliant phrase"}]


def test_build_messages_produces_alternating_user_assistant_turns() -> None:
    messages = build_messages("x")
    # Expect N*(user, assistant) pairs + final user turn.
    roles = [m["role"] for m in messages]
    # Final role is user.
    assert roles[-1] == "user"
    # Every role is user or assistant (no system — that goes in `system`).
    assert set(roles) <= {"user", "assistant"}
    # Each message has exactly one text content block.
    for message in messages:
        assert isinstance(message["content"], list)
        assert len(message["content"]) == 1
        assert isinstance(message["content"][0]["text"], str)


def test_build_messages_is_deterministic() -> None:
    # Regression against the old module-level mutable `messages` bug.
    first = build_messages("identical input")
    second = build_messages("identical input")
    assert first == second
    assert first is not second

    first.append({"role": "user", "content": [{"text": "sneaky"}]})
    assert second[-1]["content"][0]["text"] == "identical input"


def test_build_messages_no_typo_in_examples() -> None:
    """Regression: the legacy prompt had 'acedemic' — ensure we fixed it."""
    messages = build_messages("x")
    joined = " ".join(m["content"][0]["text"] for m in messages)
    assert "acedemic" not in joined
    assert "academic" in joined


# ---------------------------------------------------------------------------
# get_synonym: mocked boto3 client
# ---------------------------------------------------------------------------


def _converse_response(text: str) -> dict[str, object]:
    """Build a Converse-shaped response body."""
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": text}],
            }
        },
        "stopReason": "end_turn",
        "usage": {"inputTokens": 100, "outputTokens": 10, "totalTokens": 110},
    }


@patch("phrasaurus.bedrock_client.boto3.client")
def test_get_synonym_returns_stripped_content(mock_boto: MagicMock) -> None:
    client = MagicMock()
    client.converse.return_value = _converse_response("  ephemeral  ")
    mock_boto.return_value = client

    result = get_synonym(
        "fleeting",
        region="us-east-1",
        model_id="us.anthropic.claude-3-5-haiku-20241022-v1:0",
        max_tokens=60,
    )

    assert result == "ephemeral"

    # Client constructed with the right service + region.
    args, kwargs = mock_boto.call_args
    assert args[0] == "bedrock-runtime"
    assert kwargs["region_name"] == "us-east-1"
    assert kwargs["config"].retries == {"max_attempts": 5, "mode": "adaptive"}

    # Converse called with the expected shape.
    converse_kwargs = client.converse.call_args.kwargs
    assert converse_kwargs["modelId"] == "us.anthropic.claude-3-5-haiku-20241022-v1:0"
    assert converse_kwargs["inferenceConfig"]["maxTokens"] == 60
    assert converse_kwargs["system"][0]["text"].startswith("You function as")
    assert converse_kwargs["messages"][-1] == {
        "role": "user",
        "content": [{"text": "fleeting"}],
    }


@patch("phrasaurus.bedrock_client.boto3.client")
def test_get_synonym_wraps_client_errors(mock_boto: MagicMock) -> None:
    client = MagicMock()
    client.converse.side_effect = ClientError(
        error_response={"Error": {"Code": "ThrottlingException", "Message": "slow down"}},
        operation_name="Converse",
    )
    mock_boto.return_value = client

    with pytest.raises(BedrockClientError, match="Bedrock Converse failed"):
        get_synonym("x", region="us-east-1", model_id="m", max_tokens=60)


@patch("phrasaurus.bedrock_client.boto3.client")
def test_get_synonym_wraps_botocore_errors(mock_boto: MagicMock) -> None:
    class _Boom(BotoCoreError):
        fmt = "endpoint unreachable"

    client = MagicMock()
    client.converse.side_effect = _Boom()
    mock_boto.return_value = client

    with pytest.raises(BedrockClientError):
        get_synonym("x", region="us-east-1", model_id="m", max_tokens=60)


@patch("phrasaurus.bedrock_client.boto3.client")
def test_get_synonym_raises_on_missing_output(mock_boto: MagicMock) -> None:
    client = MagicMock()
    client.converse.return_value = {"stopReason": "end_turn"}  # no output
    mock_boto.return_value = client

    with pytest.raises(BedrockClientError, match="missing output"):
        get_synonym("x", region="us-east-1", model_id="m", max_tokens=60)


@patch("phrasaurus.bedrock_client.boto3.client")
def test_get_synonym_raises_on_empty_content(mock_boto: MagicMock) -> None:
    client = MagicMock()
    client.converse.return_value = {"output": {"message": {"role": "assistant", "content": []}}}
    mock_boto.return_value = client

    with pytest.raises(BedrockClientError, match="empty content"):
        get_synonym("x", region="us-east-1", model_id="m", max_tokens=60)


@patch("phrasaurus.bedrock_client.boto3.client")
def test_get_synonym_raises_when_no_text_block(mock_boto: MagicMock) -> None:
    client = MagicMock()
    # Content blocks present but none contain text (e.g., only toolUse blocks).
    client.converse.return_value = {
        "output": {"message": {"role": "assistant", "content": [{"toolUse": {}}]}}
    }
    mock_boto.return_value = client

    with pytest.raises(BedrockClientError, match="no usable text"):
        get_synonym("x", region="us-east-1", model_id="m", max_tokens=60)
