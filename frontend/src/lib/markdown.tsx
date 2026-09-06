/**
 * Tiny markdown renderer for NL Query answers.
 *
 * Sonnet emits a small markdown subset for the demo (## headings,
 * **bold**, list bullets, blank-line paragraphs). Pulling in a full
 * markdown library would inflate the bundle for a handful of tags, so
 * we render that subset inline. Anything outside the subset falls
 * through as plain text — safe by construction.
 */
import { Fragment, type ReactNode } from "react";

export function MarkdownLite({ text }: { text: string }) {
  if (!text) return null;
  const blocks = text.replace(/\r\n/g, "\n").split(/\n{2,}/);
  return (
    <div className="flex flex-col gap-3 text-sm leading-relaxed text-fg-primary">
      {blocks.map((block, i) => (
        <Block key={i} block={block} />
      ))}
    </div>
  );
}

function Block({ block }: { block: string }) {
  const trimmed = block.trim();
  if (!trimmed) return null;

  // ## Heading 2  (treat anything starting with ## or ### as a heading)
  const h2 = trimmed.match(/^#{2,3}\s+(.*)$/m);
  if (h2 && trimmed.startsWith("#")) {
    return (
      <h3 className="text-base font-semibold text-fg-primary">
        <Inline text={h2[1] ?? ""} />
      </h3>
    );
  }

  // Bullet list (lines starting with "-" or "*")
  const lines = trimmed.split("\n");
  if (lines.every((l) => /^\s*[-*]\s+/.test(l))) {
    return (
      <ul className="ml-5 list-disc space-y-1 text-fg-primary">
        {lines.map((l, i) => (
          <li key={i}>
            <Inline text={l.replace(/^\s*[-*]\s+/, "")} />
          </li>
        ))}
      </ul>
    );
  }

  // Default paragraph (preserve single-line breaks via <br/>)
  return (
    <p className="whitespace-pre-line text-fg-primary">
      <Inline text={trimmed} />
    </p>
  );
}

function Inline({ text }: { text: string }) {
  // Split on **bold** segments while keeping the text intact.
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((part, i) => {
        if (/^\*\*[^*]+\*\*$/.test(part)) {
          return (
            <strong key={i} className="font-semibold text-fg-primary">
              {part.slice(2, -2)}
            </strong>
          );
        }
        return <Fragment key={i}>{part}</Fragment>;
      })}
    </>
  );
}

export function _splitForTesting(text: string): ReactNode {
  return <MarkdownLite text={text} />;
}
