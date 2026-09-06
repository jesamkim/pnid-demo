"""Cohere Embed v4 embeddings via Bedrock.

Cohere Embed v4 in Bedrock supports input_type values:
  - search_document : when embedding the corpus
  - search_query    : when embedding a user query

Uses inference profile us.cohere.embed-v4:0.
"""
from __future__ import annotations

import json

from backend.aws_clients import get_bedrock_runtime
from backend.config import get_settings


# Cohere Embed v4 (Bedrock) accepts at most 96 texts per InvokeModel call,
# and rejects empty strings with a ValidationException. Larger drawings
# easily exceed 96 docs (drawing 00 → 200+), so we chunk client-side.
_BATCH = 96


def _embed_batch(texts: list[str], input_type: str) -> list[list[float]]:
    s = get_settings()
    client = get_bedrock_runtime()
    body = {
        "texts": texts,
        "input_type": input_type,
    }
    resp = client.invoke_model(
        modelId=s.embedding_id,
        accept="application/json",
        contentType="application/json",
        body=json.dumps(body),
    )
    payload = json.loads(resp["body"].read())
    embeddings = payload["embeddings"]
    if isinstance(embeddings, dict):
        return embeddings.get("float") or embeddings.get("int8") or list(embeddings.values())[0]
    return embeddings


def _embed(texts: list[str], input_type: str) -> list[list[float]]:
    # Substitute empties with a single space so each input maps to exactly
    # one returned embedding (preserves order); Bedrock rejects "" outright.
    safe = [(t if t.strip() else " ") for t in texts]
    out: list[list[float]] = []
    for i in range(0, len(safe), _BATCH):
        out.extend(_embed_batch(safe[i : i + _BATCH], input_type))
    return out


def embed_documents(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return _embed(texts, "search_document")


def embed_query(text: str) -> list[float]:
    return _embed([text], "search_query")[0]
