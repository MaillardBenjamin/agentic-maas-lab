export type AgentSpan =
  | { type: "text" | "bold" | "code"; value: string }
  | { type: "link"; value: string; href: string };

export type AgentBlock =
  | { type: "gap" }
  | { type: "paragraph"; spans: AgentSpan[] }
  | { type: "heading"; level: 1 | 2 | 3; spans: AgentSpan[] };

const marker = /\*\*([^*\n]+?)\*\*|`([^`\n]+)`|\[([^\]\n]+)\]\(([^)\s\n]+)\)/g;

function safeHref(href: string): string | undefined {
  try {
    const url = new URL(href);
    if (url.protocol === "http:" || url.protocol === "https:") return url.href;
  } catch {
    return undefined;
  }
  return undefined;
}

function parseInline(line: string): AgentSpan[] {
  const spans: AgentSpan[] = [];
  let cursor = 0;
  for (const match of line.matchAll(marker)) {
    const start = match.index ?? 0;
    if (start > cursor) spans.push({ type: "text", value: line.slice(cursor, start) });
    if (match[1] !== undefined) spans.push({ type: "bold", value: match[1] });
    else if (match[2] !== undefined) spans.push({ type: "code", value: match[2] });
    else {
      const href = safeHref(match[4] ?? "");
      spans.push(href ? { type: "link", value: match[3] ?? "", href } : { type: "text", value: match[3] ?? "" });
    }
    cursor = start + match[0].length;
  }
  if (cursor < line.length) spans.push({ type: "text", value: line.slice(cursor) });
  return spans;
}

export function parseAgentMarkdown(text: string): AgentBlock[] {
  return text.split("\n").map((line) => {
    if (line.trim() === "") return { type: "gap" };
    const heading = /^(#{1,3})\s+(.+)$/.exec(line);
    if (heading) {
      const level = heading[1].length as 1 | 2 | 3;
      return { type: "heading", level, spans: parseInline(heading[2]) };
    }
    return { type: "paragraph", spans: parseInline(line) };
  });
}
