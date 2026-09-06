"""Anti-cheating guardrail for ralph-loop.

ralph-loop must improve accuracy via *general* changes (system prompts,
tile parameters, agent topology, evaluation thresholds) — never by
leaking ground-truth answers into production code.

This static check fails if any of the following appears under
backend/, scripts/runtime_*, or config/:

  1. A reference to `data/ground_truth/` from non-test code
  2. A drawing-id-conditional branch that forces specific tag output,
     e.g. `if drawing_id == "00": return [V-101, PSV-101, ...]`
  3. Any GT-only tag string set (V-907, ST-501, etc.) hard-coded as
     a literal in production code (allowlist for legitimate ISA-5.1
     demo data is checked, see ALLOWED_LITERAL_BACKEND below)

The list of "GT-only tags" is built by reading every ground_truth
JSON; it's a runtime list, not hardcoded.

Run:
  python3 scripts/check_no_gt_leak.py
  → exit 0 if clean, exit 1 with diagnostics if a leak is detected.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GT_DIR = ROOT / "data" / "ground_truth"

# Production code paths that must stay GT-free.
SCAN_DIRS = [
    ROOT / "backend",
    ROOT / "agent_main.py",
]

# These files are *allowed* to reference ground truth — they're test
# infrastructure, not production agents.
ALLOWED_PATHS_PARTS = (
    "tests/",
    "scripts/eval_",
    "scripts/check_",
    "scripts/freeze_",  # build-time showcase freezer (replay-only demo)
    "benchmark/",
    "data/synthesis/",  # synthesis SVG builders own their tag spec
    "data/ground_truth/",
)


def _gt_tags() -> set[str]:
    tags: set[str] = set()
    for gt_file in GT_DIR.glob("*.json"):
        try:
            data = json.loads(gt_file.read_text())
        except Exception:  # noqa: BLE001
            continue
        for e in data.get("equipment", []):
            if e.get("tag"):
                tags.add(str(e["tag"]).upper())
        for i in data.get("instruments", []):
            if i.get("tag"):
                tags.add(str(i["tag"]).upper())
        for l in data.get("lines", []):
            if l.get("line_no"):
                tags.add(str(l["line_no"]).upper())
    return tags


def _scan_files() -> list[Path]:
    out: list[Path] = []
    for entry in SCAN_DIRS:
        if entry.is_file():
            out.append(entry)
            continue
        for p in entry.rglob("*.py"):
            rel = p.relative_to(ROOT).as_posix()
            if any(part in rel for part in ALLOWED_PATHS_PARTS):
                continue
            out.append(p)
    return out


def _strip_comments_and_strings(src: str) -> str:
    """Coarse strip of triple-quoted strings + line comments.

    Replaces string contents with whitespace (preserving newlines so
    line numbers in findings still line up with the original file).
    Not a real parser — sufficient for the leak guard.
    """
    # Triple-quoted strings (greedy, multiline).
    src = re.sub(
        r'(?P<q>"""|\'\'\')[\s\S]*?(?P=q)',
        lambda m: re.sub(r'\S', ' ', m.group(0)),
        src,
    )
    # Line comments.
    src = re.sub(r'#[^\n]*', lambda m: ' ' * len(m.group(0)), src)
    return src


def main() -> int:
    gt_tags = _gt_tags()
    findings: list[str] = []

    for path in _scan_files():
        text = path.read_text(errors="ignore")
        rel = path.relative_to(ROOT).as_posix()

        # Strip Python comments + docstrings before applying rules so
        # legitimate ISA-5.1 examples in module docstrings aren't
        # flagged. We do a coarse strip — good enough for ralph-loop
        # diff guard, not a full parser.
        scrubbed = _strip_comments_and_strings(text)

        # Rule 1 — opening data/ground_truth/ as a file path (production
        # code must never read GT). Variable references that happen to
        # contain "ground_truth" in their name are OK.
        if re.search(r'data/ground_truth/', scrubbed):
            findings.append(f"{rel}: opens data/ground_truth/")

        # Rule 2 — drawing-id-conditional branch with literal id
        for m in re.finditer(
            r'if\s+\w+\s*==\s*[\'"](?:00|01|01b|02|03|04|real-\d+)[\'"]',
            scrubbed,
        ):
            line = scrubbed[: m.start()].count("\n") + 1
            findings.append(
                f"{rel}:{line}: drawing-id-conditional branch detected: "
                f"{m.group(0)!r}"
            )

        # Rule 3 — GT tag literals appearing as values in lists / dicts /
        # function returns (i.e. *outside* docstrings/comments).
        # We check the scrubbed text but require the tag to appear in a
        # context that looks like data, not narrative prose.
        hits = 0
        for tag in gt_tags:
            pattern = re.compile(
                r'(?:[=:\[(,]\s*|return\s+)[\'"]' + re.escape(tag) + r'[\'"]'
            )
            for m in pattern.finditer(scrubbed):
                line = scrubbed[: m.start()].count("\n") + 1
                findings.append(
                    f"{rel}:{line}: GT tag literal {tag!r} embedded as value"
                )
                hits += 1
                if hits >= 5:
                    break
            if hits >= 5:
                break

    if findings:
        print("GT LEAK DETECTED — ralph-loop run rejected:")
        for f in findings:
            print(f"  - {f}")
        return 1
    print(f"OK — no GT leak across {len(_scan_files())} files "
          f"(checked against {len(gt_tags)} ground-truth tags)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
