"""In-memory hybrid search index.

Stores SearchDoc objects with their embeddings, supports:
  - vector search via cosine similarity
  - keyword (substring/BM25-lite) over the .text and .tag fields
  - hybrid score = alpha * vector + (1 - alpha) * keyword

This can be swapped for OpenSearch Serverless behind the same
SearchIndex.search(...) interface; the data shape is identical.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from backend.tools.document_builder import SearchDoc
from backend.tools.embedding import embed_documents, embed_query


@dataclass(frozen=True)
class IndexedDoc:
    doc: SearchDoc
    embedding: tuple[float, ...]


@dataclass(frozen=True)
class SearchHit:
    doc: SearchDoc
    score: float
    vector_score: float
    keyword_score: float


def _tokenize(s: str) -> list[str]:
    return [t.lower() for t in re.findall(r"[A-Za-z0-9\-]+", s)]


def _cosine(a: tuple[float, ...] | list[float], b: tuple[float, ...] | list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


@dataclass
class SearchIndex:
    docs: list[IndexedDoc] = field(default_factory=list)

    def add(self, docs: list[SearchDoc], *, replace_drawing: bool = False) -> None:
        if not docs:
            return
        if replace_drawing:
            drawing_ids = {d.drawing_id for d in docs}
            self.docs = [
                ix for ix in self.docs if ix.doc.drawing_id not in drawing_ids
            ]
        texts = [d.text for d in docs]
        embs = embed_documents(texts)
        for doc, emb in zip(docs, embs):
            self.docs.append(IndexedDoc(doc=doc, embedding=tuple(emb)))

    def _keyword_score(self, query: str, doc: SearchDoc) -> float:
        q_tokens = set(_tokenize(query))
        if not q_tokens:
            return 0.0
        d_tokens = set(_tokenize(doc.text + " " + doc.tag + " " + doc.kind))
        overlap = q_tokens & d_tokens
        if not overlap:
            return 0.0
        # Exact tag match boosted heavily.
        boost = 2.0 if doc.tag.lower() in {t.lower() for t in q_tokens} else 1.0
        return boost * len(overlap) / len(q_tokens)

    def search(self, query: str, top_k: int = 5, alpha: float = 0.6,
               kind_filter: str | None = None,
               drawing_filter: str | None = None) -> list[SearchHit]:
        if not self.docs:
            return []
        q_emb = tuple(embed_query(query))

        hits: list[SearchHit] = []
        for ix in self.docs:
            if kind_filter and ix.doc.kind != kind_filter:
                continue
            if drawing_filter and ix.doc.drawing_id != drawing_filter:
                continue
            v = _cosine(q_emb, ix.embedding)
            k = self._keyword_score(query, ix.doc)
            score = alpha * v + (1 - alpha) * k
            hits.append(SearchHit(doc=ix.doc, score=score, vector_score=v, keyword_score=k))

        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]

    def __len__(self) -> int:
        return len(self.docs)
