"""LLM client wrapping Bedrock Converse API for Opus 4.8 / Sonnet 4.6.

Activates 1M context window via additionalModelRequestFields beta header.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

from PIL import Image

from backend.aws_clients import get_bedrock_runtime
from backend.config import ModelConfig, get_settings


@dataclass(frozen=True)
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    stop_reason: str
    model_id: str


def _image_block(img: Image.Image, fmt: str = "png") -> dict[str, Any]:
    buf = io.BytesIO()
    img.save(buf, format=fmt.upper())
    return {"image": {"format": fmt, "source": {"bytes": buf.getvalue()}}}


def _converse(
    model: ModelConfig,
    messages: list[dict[str, Any]],
    system: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> LLMResponse:
    s = get_settings()
    client = get_bedrock_runtime()

    inference_cfg: dict[str, Any] = {
        "maxTokens": max_tokens if max_tokens is not None else s.max_tokens_default,
    }
    # Opus 4.8 deprecated `temperature`; only set when caller explicitly opts in.
    if temperature is not None:
        inference_cfg["temperature"] = temperature

    kwargs: dict[str, Any] = {
        "modelId": model.id,
        "messages": messages,
        "inferenceConfig": inference_cfg,
        "additionalModelRequestFields": {"anthropic_beta": list(s.bedrock_beta_headers)},
    }
    if system:
        kwargs["system"] = [{"text": system}]

    resp = client.converse(**kwargs)
    out_msg = resp["output"]["message"]
    text = "".join(part.get("text", "") for part in out_msg["content"])
    usage = resp.get("usage", {})
    return LLMResponse(
        text=text,
        input_tokens=int(usage.get("inputTokens", 0)),
        output_tokens=int(usage.get("outputTokens", 0)),
        stop_reason=resp.get("stopReason", ""),
        model_id=model.id,
    )


def call_primary(prompt: str, system: str | None = None, **kw) -> LLMResponse:
    return _converse(
        get_settings().primary_model,
        [{"role": "user", "content": [{"text": prompt}]}],
        system=system,
        **kw,
    )


def call_secondary(prompt: str, system: str | None = None, **kw) -> LLMResponse:
    return _converse(
        get_settings().secondary_model,
        [{"role": "user", "content": [{"text": prompt}]}],
        system=system,
        **kw,
    )


def call_primary_vision(
    prompt: str, image: Image.Image, system: str | None = None, **kw
) -> LLMResponse:
    return _converse(
        get_settings().primary_model,
        [{"role": "user", "content": [_image_block(image), {"text": prompt}]}],
        system=system,
        **kw,
    )


def call_secondary_vision(
    prompt: str, image: Image.Image, system: str | None = None, **kw
) -> LLMResponse:
    return _converse(
        get_settings().secondary_model,
        [{"role": "user", "content": [_image_block(image), {"text": prompt}]}],
        system=system,
        **kw,
    )
