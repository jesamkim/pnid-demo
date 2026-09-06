"""Settings loader contract tests."""
from __future__ import annotations

from backend.config import get_settings


def test_aws_profile_is_profile2():
    s = get_settings()
    assert s.aws_profile == "profile2"


def test_aws_region_is_us_east_1():
    s = get_settings()
    assert s.aws_region == "us-east-1"


def test_primary_model_is_opus_4_8():
    s = get_settings()
    assert s.primary_model.id == "global.anthropic.claude-opus-4-8"
    assert s.primary_model.context_window == 1_000_000


def test_secondary_model_is_sonnet_4_6():
    s = get_settings()
    assert s.secondary_model.id == "global.anthropic.claude-sonnet-4-6"
    assert s.secondary_model.context_window == 1_000_000


def test_embedding_is_cohere_v4_inference_profile():
    s = get_settings()
    assert s.embedding_id == "us.cohere.embed-v4:0"


def test_bedrock_beta_headers_include_1m_context():
    s = get_settings()
    assert any("context-1m" in h for h in s.bedrock_beta_headers)


def test_settings_is_singleton():
    a = get_settings()
    b = get_settings()
    assert a is b
