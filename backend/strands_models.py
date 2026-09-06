"""Strands BedrockModel adapters for our two demo models.

Centralizes model construction so every Strands Agent in the project
shares the same profile, region, and 1M-context beta header.
"""
from __future__ import annotations

from functools import lru_cache

from strands.models.bedrock import BedrockModel

from backend.aws_clients import get_session
from backend.config import get_settings


@lru_cache(maxsize=1)
def primary_model() -> BedrockModel:
    """Opus 4.8 with 1M context beta (used for Vision extraction, deep reasoning)."""
    s = get_settings()
    return BedrockModel(
        boto_session=get_session(),
        model_id=s.primary_model.id,
        max_tokens=s.max_tokens_default,
        additional_request_fields={"anthropic_beta": list(s.bedrock_beta_headers)},
    )


@lru_cache(maxsize=1)
def secondary_model() -> BedrockModel:
    """Sonnet 4.6 with 1M context beta (routing, NL query, light eval)."""
    s = get_settings()
    return BedrockModel(
        boto_session=get_session(),
        model_id=s.secondary_model.id,
        max_tokens=s.max_tokens_default,
        temperature=s.temperature_default,
        additional_request_fields={"anthropic_beta": list(s.bedrock_beta_headers)},
    )
