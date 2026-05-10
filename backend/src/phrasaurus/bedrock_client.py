"""Amazon Bedrock chat-completion client.

Uses the ``bedrock-runtime`` Converse API because it exposes a uniform
request/response shape across model providers (Anthropic, Nova, Llama,
Titan) and is the current AWS-recommended invocation path.

The public surface is two functions:

- ``build_messages(phrase)`` — deterministic few-shot prompt construction.
- ``get_synonym(phrase, *, region, model_id, max_tokens)`` — single
  Bedrock call returning the synonym string.

Isolating the boto3 dependency behind this module keeps the handler
free of AWS plumbing and lets tests stub one import site.
"""

from __future__ import annotations

import logging
from typing import Any, Final

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
# The Converse API separates the system prompt from the conversation
# messages. ``_FEW_SHOT_EXAMPLES`` become alternating user/assistant turns,
# and the user's actual phrase is the final user turn.
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT: Final[str] = (
    "You function as a phrase thesaurus. Upon receiving a word, words, or a "
    "phrase, your response will exclusively consist of a single synonymous "
    "word or phrase. No additional text, context, or explanations should be "
    "provided. Your output will strictly adhere to the principle of phrase "
    "synonymy."
)

_FEW_SHOT_EXAMPLES: Final[tuple[tuple[str, str], ...]] = (
    (
        "Give me a word or phrase that reflects the inner struggle of "
        "mankind but on a more academic level",
        "existential crisis",
    ),
    ("a lot of pain due to heat", "Intense discomfort caused by high temperature"),
    ("I helped a patient in need of surgery", "Assisted in a critical surgical intervention"),
    (
        "Assistant, what's the tallest mountain in the world",
        "Which peak is the highest?",
    ),
)


# Errors worth retrying per the Bedrock skill's error classification.
# Adaptive retry mode handles the backoff; we just need to declare the
# max attempts. See: Bedrock Converse API docs, "Error retry classification".
# @secure_recommendation: Adaptive retry with bounded attempts prevents
# runaway traffic against a throttled dependency.
_RETRY_CONFIG: Final[Config] = Config(retries={"max_attempts": 5, "mode": "adaptive"})


class BedrockClientError(RuntimeError):
    """Raised when the upstream Bedrock call fails or returns an unusable response.

    Wrapping botocore's ``ClientError``/``BotoCoreError`` lets the handler
    translate any upstream failure into a single 502 response without
    leaking provider details to callers.
    """


def build_messages(phrase: str) -> list[dict[str, Any]]:
    """Construct the Converse-shaped messages array for a single request.

    Pure function — no network, no mutation of module state. The system
    prompt is returned separately by :func:`build_system_prompts` because
    Converse takes it as a top-level parameter, not a message role.
    """
    messages: list[dict[str, Any]] = []
    for user_turn, assistant_turn in _FEW_SHOT_EXAMPLES:
        messages.append({"role": "user", "content": [{"text": user_turn}]})
        messages.append({"role": "assistant", "content": [{"text": assistant_turn}]})
    messages.append({"role": "user", "content": [{"text": phrase}]})
    return messages


def build_system_prompts() -> list[dict[str, str]]:
    """System prompt in the Converse API's list-of-{'text': ...} shape."""
    return [{"text": _SYSTEM_PROMPT}]


def get_synonym(
    phrase: str,
    *,
    region: str,
    model_id: str,
    max_tokens: int,
) -> str:
    """Call Bedrock Converse and return the synonym string.

    Args:
        phrase: The user-supplied phrase. The caller is responsible for
            validating length / emptiness before we get here.
        region: AWS region hosting the Bedrock endpoint.
        model_id: Bedrock model ID (typically a cross-region inference
            profile such as ``us.anthropic.claude-3-5-haiku-20241022-v1:0``).
        max_tokens: Hard cap on generated tokens. MUST be set explicitly —
            leaving it unset reserves the model's full maximum (e.g. 64K)
            against your quota on every call and causes unexpected
            ThrottlingException.

    Raises:
        BedrockClientError: on any upstream failure or malformed response.
    """
    # @secure_recommendation: Use bedrock-runtime (data plane) — NOT bedrock
    # (control plane). Wrong client is the #1 cause of UnknownOperationException.
    client = boto3.client("bedrock-runtime", region_name=region, config=_RETRY_CONFIG)

    try:
        response = client.converse(
            modelId=model_id,
            system=build_system_prompts(),
            messages=build_messages(phrase),
            # @secure_recommendation: Always set maxTokens explicitly. Leaving
            # unset reserves the model's full max against quota on every call.
            inferenceConfig={"maxTokens": max_tokens, "temperature": 0.7},
        )
    except (ClientError, BotoCoreError) as exc:
        raise BedrockClientError(f"Bedrock Converse failed: {exc}") from exc

    return _extract_text(response)


def _extract_text(response: dict[str, Any]) -> str:
    """Pull the first text block out of a Converse response.

    Defensive: Converse's shape is well-defined but we guard against an
    empty ``content`` array or a missing ``text`` block so a malformed
    response becomes a typed error rather than an obscure ``KeyError``.
    """
    try:
        blocks = response["output"]["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise BedrockClientError("Bedrock response is missing output.message.content") from exc

    if not blocks:
        raise BedrockClientError("Bedrock returned an empty content array")

    for block in blocks:
        text = block.get("text") if isinstance(block, dict) else None
        if isinstance(text, str) and text.strip():
            return text.strip()

    raise BedrockClientError("Bedrock response contained no usable text block")
