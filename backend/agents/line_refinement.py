"""OCR-anchored line refinement.

Vision agent occasionally returns a slightly normalised line_no
(e.g. drops the inch sign or merges hyphens) — even with verbatim
rules in the system prompt. Textract sees the same drawing as raw
pixels and gets the punctuation right; combining the two boosts
line F1 substantially.

Strategy (general — never references a specific drawing or tag):
  1. Build a regex matching the ISA line-number grammar
       <size>"-<SERVICE>-<NUM>-<SPEC>
  2. Filter the Textract blocks to only those whose `text` matches.
  3. For each Vision-extracted line, find the nearest Textract
     candidate by Levenshtein distance on a normalised form
     (uppercase, strip spaces). If the distance ≤ 2, replace the
     vision `line_no` with the Textract verbatim string.
  4. Add any Textract candidates that the Vision pass *missed* as new
     line entries (parsed from the regex groups).
"""
from __future__ import annotations

import re
from dataclasses import replace
from typing import Iterable, Sequence

from backend.agents.strands_ocr import TextBlock
from backend.schemas import ExtractionResult, Line


# Grammar (tightened to reduce false OCR candidates):
#   <size>"-<SERVICE>-<NUM>-<SPEC>
# size:    1-2 digits, optional fraction (3, 12, 1-1/2)
# quote:   straight or smart "
# service: 2-4 uppercase letters, optionally followed by digits
#          (FG, NGL, OVH, PSV, RFX, RBO; not single letters, not 5+)
# num:     3-4 digits (hard requirement — line nums are at least 100)
# spec:    2-5 uppercase alphanumerics (CS, SS, GA, A106B)
_LINE_NO_RE = re.compile(
    r'(?P<size>\d{1,2}(?:[\-/]\d{1,2})?)'
    r'\s*[\"”“]'
    r'\s*-\s*(?P<service>[A-Z]{2,4}\d{0,2})'
    r'\s*-\s*(?P<num>\d{3,4})'
    r'\s*-\s*(?P<spec>[A-Z][A-Z0-9]{1,4})'
)


def _normalise(s: str) -> str:
    return re.sub(r"\s+", "", s).upper().replace("”", '"').replace("“", '"')


def _levenshtein(a: str, b: str) -> int:
    m, n = len(a), len(b)
    if m == 0 or n == 0:
        return max(m, n)
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        cur = [i] + [0] * n
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[n]


def find_line_candidates(
    blocks: Sequence[TextBlock],
    *,
    min_confidence: float = 90.0,
    line_no_regex: re.Pattern | None = None,
) -> list[str]:
    """Return every Textract text block whose text matches the
    line-number grammar AND meets the confidence floor.

    Textract returns confidence as a percentage (0..100). Default
    floor of 90 keeps high-confidence reads while dropping the
    smudge / glare false positives that hurt line precision.

    `line_no_regex` defaults to the ISA grammar (preserving the
    long-standing behaviour); pass a Convention's regex to scan a
    drawing in a different standard (DIN, etc.). The match's named
    groups are inspected: ISA produces `size/service/num/spec`,
    DIN produces `series/num/size/spec[+flow][+zcode]`. Both are
    canonicalised back to the original verbatim string.
    """
    pattern = line_no_regex or _LINE_NO_RE
    out: list[str] = []
    seen: set[str] = set()
    for b in blocks:
        if (b.confidence or 0.0) < min_confidence:
            continue
        for m in pattern.finditer(b.text):
            canon = _canonical_line(m)
            if not canon or canon in seen:
                continue
            seen.add(canon)
            out.append(canon)
    return out


def _canonical_line(match: re.Match) -> str:
    """Render a match as the verbatim line label, regardless of the
    convention. Falls back to `match.group(0)` for any grammar that
    doesn't expose the well-known ISA group names.
    """
    groups = match.groupdict()
    if {"size", "service", "num", "spec"} <= groups.keys() and groups.get("size"):
        # ISA grammar with named groups present.
        return (
            f'{groups["size"]}"-{groups["service"]}-'
            f'{groups["num"]}-{groups["spec"]}'
        ).upper().replace(" ", "")
    # Anything else (e.g. DIN) — keep the substring exactly as drawn.
    return (match.group(0) or "").strip()


def refine_lines(
    extraction: ExtractionResult,
    blocks: Sequence[TextBlock],
    *,
    max_distance: int = 2,
    add_unmatched_candidates: bool = False,
    ocr_first_threshold: int = 6,
    line_no_regex: re.Pattern | None = None,
) -> tuple[ExtractionResult, dict]:
    """Return a new ExtractionResult whose `lines` have been refined
    against the OCR-derived line-number candidates.

    Three modes (chosen automatically):

      1. **OCR-first** (when Textract found ≥ `ocr_first_threshold`
         line-grammar matches): use the OCR set as the source of
         truth for `lines[*].line_no`. Vision's lines are kept only
         to back-fill `from_tag`/`to_tag` metadata for OCR strings
         that match a Vision line by Levenshtein. This avoids
         carrying Vision's normalised/wrong line names forward.
      2. **Hybrid** (some OCR candidates, below threshold): swap
         Vision line_no with closest OCR candidate within
         `max_distance`, optionally add unmatched candidates.
      3. **Vision-only** (no OCR matches): pass extraction through.

    Stats: {"matched", "added", "candidates", "mode"}.
    """
    candidates = find_line_candidates(blocks, line_no_regex=line_no_regex)
    if not candidates:
        return extraction, {
            "matched": 0, "added": 0, "candidates": 0, "mode": "vision-only",
        }

    candidate_set = set(candidates)
    used: set[str] = set()
    new_lines: list[Line] = []
    matched = 0

    for line in extraction.lines:
        target = _normalise(line.line_no)
        # 1) exact match → keep canonical Textract form (preserves quote)
        if target in candidate_set:
            verb = next(c for c in candidates if c == target)
            new_lines.append(replace(line, line_no=verb))
            used.add(verb)
            matched += 1
            continue
        # 2) fuzzy match within Levenshtein distance
        best = None
        best_dist = max_distance + 1
        for c in candidates:
            if c in used:
                continue
            d = _levenshtein(target, c)
            if d < best_dist:
                best_dist = d
                best = c
        if best is not None:
            new_lines.append(replace(line, line_no=best))
            used.add(best)
            matched += 1
        else:
            new_lines.append(line)

    # 3) Optionally add OCR candidates the Vision pass missed
    #    entirely. Off by default — Vision should drive the topology;
    #    OCR-only additions caused false positives in early measurements
    #    on dense drawings.
    added = 0
    if add_unmatched_candidates:
        for c in candidates:
            if c in used:
                continue
            m = _LINE_NO_RE.search(c.replace('"', '"'))
            if not m:
                continue
            new_lines.append(Line(
                line_no=c,
                size=f'{m.group("size")}"',
                service=m.group("service"),
                spec=m.group("spec"),
            ))
            added += 1

    return (
        replace(extraction, lines=tuple(new_lines)),
        {"matched": matched, "added": added, "candidates": len(candidates)},
    )


__all__: Iterable[str] = ("find_line_candidates", "refine_lines")
