"""Strands extractor contract tests (no Bedrock calls).

Verifies prompt/system contract and JSON parsing helpers without invoking
the model — agent invocation tests live in scripts/verify_strands_pipeline.py
which exercise the full pipeline against real images.
"""
from __future__ import annotations

import json

from backend.agents.strands_extractor import (
    SYSTEM_PROMPT,
    _agent_text,
    _parse_json,
    _strip_fences,
)


def test_system_prompt_mentions_isa_5_1():
    assert "ISA-5.1" in SYSTEM_PROMPT
    assert "JSON" in SYSTEM_PROMPT


def test_system_prompt_mentions_line_label_pattern():
    assert "<size>" in SYSTEM_PROMPT or "line_no" in SYSTEM_PROMPT.lower()


def test_strip_fences_handles_plain_json():
    s = '{"a": 1}'
    assert _strip_fences(s) == s


def test_strip_fences_removes_markdown_wrapper():
    s = '```json\n{"a": 1}\n```'
    assert _strip_fences(s).strip() == '{"a": 1}'


def test_parse_json_finds_object_in_messy_text():
    raw = 'Here is the JSON:\n```json\n{"x": 2}\n```\n thanks'
    assert _parse_json(raw) == {"x": 2}


def test_agent_text_extracts_from_strands_message():
    class FakeResult:
        message = {"role": "assistant", "content": [{"text": "hello"}]}
    assert _agent_text(FakeResult()) == "hello"
