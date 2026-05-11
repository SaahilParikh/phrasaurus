"""Runtime configuration.

All tunables live in environment variables so the same code can run in dev,
staging, prod without re-deploying. Defaults target a stable, cross-region
inference profile for Claude 3.5 Haiku — cheap, fast, and strong at the
short instruction-following this app needs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Hard limit on user-supplied phrases. 280 chars is enough for any reasonable
# English phrase and short-circuits prompt-injection or DoS-via-huge-input.
# @secure_recommendation: Bounded input length mitigates resource exhaustion
# and reduces the attack surface for prompt injection payloads.
MAX_PHRASE_LENGTH: int = 280


@dataclass(frozen=True)
class Config:
    """Immutable runtime configuration resolved once per cold start."""

    # AWS region hosting the Bedrock endpoint. Must be a region where the
    # chosen model (or its cross-region inference profile) is available.
    aws_region: str

    # Bedrock model ID. Prefer cross-region inference profiles (``us.``,
    # ``eu.``, ``apac.``, ``global.`` prefix) for higher availability.
    # Alternatives worth considering:
    #   - us.amazon.nova-micro-v1:0       — cheaper, less nuanced English.
    #   - us.anthropic.claude-sonnet-4-6  — higher quality, higher cost.
    bedrock_model_id: str

    # Cap on tokens generated per call. A phrase thesaurus response is
    # short by design. MUST be set — leaving Bedrock's maxTokens unset
    # reserves the model's full max (e.g. 64K) against your quota on
    # every call and causes unexpected ThrottlingException.
    max_tokens: int

    # Optional: apply a Bedrock Guardrail to every request. Disabled when
    # either field is empty. Pin to a numbered version in production; using
    # DRAFT lets unreviewed edits take effect immediately.
    guardrail_id: str
    guardrail_version: str

    @classmethod
    def from_env(cls) -> Config:
        """Build a Config from process environment. Called once at cold start."""
        return cls(
            aws_region=os.environ.get("AWS_REGION", "us-east-1"),
            bedrock_model_id=os.environ.get(
                "BEDROCK_MODEL_ID",
                "us.anthropic.claude-haiku-4-5-20251001-v1:0",
            ),
            max_tokens=int(os.environ.get("BEDROCK_MAX_TOKENS", "60")),
            guardrail_id=os.environ.get("BEDROCK_GUARDRAIL_ID", ""),
            guardrail_version=os.environ.get("BEDROCK_GUARDRAIL_VERSION", ""),
        )
