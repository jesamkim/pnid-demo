"""Strands Agent for natural-language P&ID queries.

Pattern:
  1) Hybrid retrieval over the SearchIndex (already in backend.tools.search_index)
  2) Strands Agent (Sonnet 4.6) drafts the answer grounded ONLY in retrieved docs.
"""
from __future__ import annotations

from dataclasses import dataclass

from strands import Agent

from backend.strands_models import secondary_model
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


@dataclass(frozen=True)
class QueryAnswer:
    text: str
    hits: tuple[SearchHit, ...]


def _format_hits(hits: list[SearchHit]) -> str:
    lines = []
    for i, h in enumerate(hits, 1):
        lines.append(
            f"[{i}] drawing={h.doc.drawing_id} kind={h.doc.kind} tag={h.doc.tag}\n"
            f"    {h.doc.text}"
        )
    return "\n".join(lines)


def _agent_text(result) -> str:
    msg = result.message
    if isinstance(msg, dict):
        for part in msg.get("content", []):
            if "text" in part:
                return part["text"]
    return str(msg)


def answer(
    query: str,
    index: SearchIndex,
    top_k: int = 6,
    *,
    drawing_filter: str | None = None,
) -> QueryAnswer:
    hits = index.search(query, top_k=top_k, drawing_filter=drawing_filter)
    if not hits:
        return QueryAnswer(text="Not found in the indexed drawings.", hits=())

    agent = Agent(model=secondary_model(), system_prompt=SYSTEM, callback_handler=None)
    user = (
        f"User query: {query}\n\n"
        f"Retrieved documents (top {len(hits)}):\n{_format_hits(hits)}\n\n"
        "Answer concisely, citing tags and drawing ids."
    )
    result = agent(user)
    text = _agent_text(result).strip()
    # When the model has actual hits but appends the zero-hits sentinel
    # as a trailing line (causing UI confusion), drop just that line.
    text = _strip_sentinel_with_hits(text)
    return QueryAnswer(text=text, hits=tuple(hits))


_SENTINEL_LINE = "Not found in the indexed drawings."


def _strip_sentinel_with_hits(text: str) -> str:
    out_lines: list[str] = []
    for line in text.splitlines():
        # Allow a leading ">" or "- " quote/bullet wrapper.
        bare = line.lstrip("> -").strip().rstrip(".") + "."
        if bare == _SENTINEL_LINE:
            continue
        out_lines.append(line)
    cleaned = "\n".join(out_lines).strip()
    return cleaned or text
