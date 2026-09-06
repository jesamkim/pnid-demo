"""Natural-language query agent.

Pipeline:
  1) Receive a free-text user query.
  2) Hit the SearchIndex with hybrid retrieval.
  3) Pass top hits to Sonnet 4.6 to compose a concise grounded answer.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.llm_client import call_secondary
from backend.tools.search_index import SearchHit, SearchIndex


SYSTEM = """You are a P&ID assistant. You answer questions strictly from the
retrieved documents. Each document represents one piece of equipment, one
instrument, or one line on a P&ID drawing.

Rules:
- Only use facts that appear in the retrieved documents.
- If the documents partially support the answer, state exactly what they
  do say and which detail is missing — do NOT add the literal phrase
  "Not found in the indexed drawings"; that phrase is reserved for the
  zero-hits sentinel only.
- Never claim a tag is "missing" or "absent" globally; only state that a
  specific connection/relationship is not described in the retrieved
  documents.
- Answer in 1-3 sentences plus an optional bullet list of tags.
- Always cite the drawing id (e.g. "drawing 01") for any tag you mention.
- Korean OR English in the user query — answer in the same language."""


USER_TPL = """User query: {query}

Retrieved documents (top {k}):
{context}

Answer concisely, citing tags and drawing ids."""


@dataclass(frozen=True)
class QueryAnswer:
    text: str
    hits: tuple[SearchHit, ...]


def _format_hits(hits: list[SearchHit]) -> str:
    out = []
    for i, h in enumerate(hits, 1):
        out.append(f"[{i}] drawing={h.doc.drawing_id} kind={h.doc.kind} tag={h.doc.tag}\n    {h.doc.text}")
    return "\n".join(out)


def answer(query: str, index: SearchIndex, top_k: int = 6) -> QueryAnswer:
    hits = index.search(query, top_k=top_k)
    if not hits:
        return QueryAnswer(text="Not found in the indexed drawings.", hits=())
    prompt = USER_TPL.format(query=query, k=len(hits), context=_format_hits(hits))
    resp = call_secondary(prompt=prompt, system=SYSTEM, max_tokens=1024)
    return QueryAnswer(text=resp.text.strip(), hits=tuple(hits))
