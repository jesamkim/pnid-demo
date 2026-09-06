/**
 * Tiny, dependency-free Markdown renderer for the scripted chatbot
 * answers. Supports just what the frozen Sonnet answers use: headings
 * (##), bold (**), bullet lists (-), and GitHub-style tables (| a | b |).
 * Anything else falls through as plain text. No HTML injection: we only
 * ever emit React elements from parsed tokens.
 */
import { Fragment, type ReactNode } from "react";

function renderInline(text: string): ReactNode[] {
  // Split on **bold** spans.
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) => {
    if (p.startsWith("**") && p.endsWith("**")) {
      return (
        <strong key={i} className="font-semibold text-fg-primary">
          {p.slice(2, -2)}
        </strong>
      );
    }
    return <Fragment key={i}>{p}</Fragment>;
  });
}

function isTableRow(line: string): boolean {
  return /^\s*\|.*\|\s*$/.test(line);
}

function isDivider(line: string): boolean {
  return /^\s*\|?[\s:|-]+\|?\s*$/.test(line) && line.includes("-");
}

function cells(line: string): string[] {
  return line
    .trim()
    .replace(/^\||\|$/g, "")
    .split("|")
    .map((c) => c.trim());
}

export function Markdown({ text }: { text: string }) {
  const lines = text.split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Table: a row, then a divider, then more rows.
    if (isTableRow(line) && i + 1 < lines.length && isDivider(lines[i + 1])) {
      const header = cells(line);
      const rows: string[][] = [];
      i += 2;
      while (i < lines.length && isTableRow(lines[i])) {
        rows.push(cells(lines[i]));
        i++;
      }
      blocks.push(
        <div key={key++} className="my-2 overflow-hidden rounded-lg border border-border-default">
          <table className="w-full text-sm">
            <thead className="bg-raised">
              <tr>
                {header.map((h, hi) => (
                  <th key={hi} className="px-3 py-2 text-left font-semibold text-fg-secondary">
                    {renderInline(h)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, ri) => (
                <tr key={ri} className="border-t border-border-default">
                  {r.map((c, ci) => (
                    <td key={ci} className="px-3 py-1.5 font-mono text-fg-primary">
                      {renderInline(c)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }

    // Heading.
    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) {
      blocks.push(
        <div key={key++} className="mt-3 mb-1 text-base font-bold text-accent">
          {renderInline(h[2])}
        </div>,
      );
      i++;
      continue;
    }

    // Bullet list — collect consecutive items.
    if (/^\s*[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*]\s+/, ""));
        i++;
      }
      blocks.push(
        <ul key={key++} className="my-1 list-disc space-y-1 pl-5 text-fg-primary">
          {items.map((it, ii) => (
            <li key={ii}>{renderInline(it)}</li>
          ))}
        </ul>,
      );
      continue;
    }

    // Blank line.
    if (line.trim() === "") {
      i++;
      continue;
    }

    // Paragraph.
    blocks.push(
      <p key={key++} className="my-1 leading-relaxed text-fg-primary">
        {renderInline(line)}
      </p>,
    );
    i++;
  }

  return <div className="space-y-0.5">{blocks}</div>;
}
