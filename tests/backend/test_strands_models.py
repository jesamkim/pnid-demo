"""Strands BedrockModel adapter contract tests."""
from __future__ import annotations

from strands.models.bedrock import BedrockModel

from backend.strands_models import primary_model, secondary_model


def test_primary_uses_opus_4_8():
    m = primary_model()
    assert isinstance(m, BedrockModel)
    cfg = m.get_config()
    assert cfg["model_id"] == "global.anthropic.claude-opus-4-8"


def test_secondary_uses_sonnet_4_6():
    m = secondary_model()
    cfg = m.get_config()
    assert cfg["model_id"] == "global.anthropic.claude-sonnet-4-6"


def test_primary_includes_1m_beta_header():
    m = primary_model()
    cfg = m.get_config()
    add = cfg.get("additional_request_fields") or {}
    beta = add.get("anthropic_beta", [])
    assert any("context-1m" in b for b in beta)


def test_secondary_includes_1m_beta_header():
    m = secondary_model()
    cfg = m.get_config()
    add = cfg.get("additional_request_fields") or {}
    beta = add.get("anthropic_beta", [])
    assert any("context-1m" in b for b in beta)


def test_models_are_singletons():
    assert primary_model() is primary_model()
    assert secondary_model() is secondary_model()
