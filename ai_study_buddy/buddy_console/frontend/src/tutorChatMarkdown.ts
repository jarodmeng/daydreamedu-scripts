/** Markdown inside a spurious `$$...$$` block (headings, bold, tables, lists). */
const MARKDOWN_INSIDE_MATH = /\n+(?:\*\*|#{1,6}\s|(?:\|[^\n]+\|)|(?:[-*+]\s)|---+)/;

/** Lines that are markdown chrome, not math — trailing `$` is almost always a model typo. */
const MARKDOWN_LINE =
  /^\s*(?:\*\*[^*]+\*\*[^$]*|\#{1,6}\s|[-*+]\s|\|.*\||---+)\s*$/;

/** `(\\frac{a}{b})` — backslash-led group only; avoids swallowing `(not part of the (\\frac…))`. */
const PAREN_INNER_LATEX = /\(\s*(\\(?:frac\{[^{}]+\}\{[^{}]+\}|text\{[^{}]*\}|times|div|cdot|Rightarrow|checkmark)[^)]*)\)/g;

/** Parenthesized arithmetic that uses LaTeX operators, e.g. `(650 \\div 5 \\times 24 = 3120)`. */
const PAREN_ARITH_LATEX = /\(\d[^)\n]*\\[a-zA-Z]+[^)\n]*\)/g;

/** Chained bare LaTeX only — do not absorb trailing arithmetic (e.g. `\frac{3}{8} \times 2960`). */
const BARE_LATEX_RUN =
  /\\(?:frac\{[^{}]+\}\{[^{}]+\}|text\{[^{}]*\}|Rightarrow|Leftarrow|rightarrow|checkmark|times|div|cdot)(?:\s*\\(?:frac\{[^{}]+\}\{[^{}]+\}|text\{[^{}]*\}|Rightarrow|Leftarrow|rightarrow|checkmark|times|div|cdot))*/g;

const CURRENCY_AMOUNT = /(?<!\\)\$(\d[\d,]*(?:\.\d{1,2})?)\b/g;

const ARITHMETIC_DOLLAR_SPAN =
  /\$(\d[\d,]*(?:\s*[+\-=×÷*/]\s*\d[\d,]*)+)\$/g;

type MathSpan = { start: number; end: number; inner: string };

function wrapInlineMath(expr: string): string {
  return `$${expr}$`;
}

function escapeCurrencyAmount(amount: string): string {
  return `\\$${amount}`;
}

function stripStrayDollarOnMarkdownLines(content: string): string {
  return content
    .split("\n")
    .map((line) => {
      if (line.endsWith("$") && MARKDOWN_LINE.test(line.slice(0, -1))) {
        return line.slice(0, -1);
      }
      return line;
    })
    .join("\n");
}

function findInlineMathClose(content: string, start: number, lineLimit: number): number {
  for (let j = start + 1; j < lineLimit; j += 1) {
    if (content[j] === "$" && content[j - 1] !== "\\") {
      const after = content[j + 1];
      if (after && /\d/.test(after)) {
        continue;
      }
      return j;
    }
  }
  return -1;
}

/** Balanced `$...$` / `$$...$$` spans (inline math must contain a LaTeX command). */
export function findMathSpans(content: string): MathSpan[] {
  const spans: MathSpan[] = [];
  let i = 0;

  while (i < content.length) {
    if (content.startsWith("$$", i)) {
      let j = i + 2;
      let closed = false;
      while (j < content.length - 1) {
        if (content.startsWith("$$", j)) {
          spans.push({ start: i, end: j + 2, inner: content.slice(i + 2, j) });
          i = j + 2;
          closed = true;
          break;
        }
        j += 1;
      }
      if (!closed) {
        i += 1;
      }
      continue;
    }

    if (content[i] === "$") {
      if (i > 0 && content[i - 1] === "\\") {
        i += 1;
        continue;
      }

      const next = content[i + 1];
      const opensMath = next === "\\" || (next !== undefined && /\d/.test(next));
      if (!opensMath) {
        i += 1;
        continue;
      }

      const lineEnd = content.indexOf("\n", i);
      const lineLimit = lineEnd === -1 ? content.length : lineEnd;
      const closeAt = findInlineMathClose(content, i, lineLimit);
      if (closeAt !== -1) {
        const inner = content.slice(i + 1, closeAt);
        if (/\\[a-zA-Z]/.test(inner)) {
          spans.push({ start: i, end: closeAt + 1, inner });
          i = closeAt + 1;
          continue;
        }
      } else if (next === "\\" && /\\[a-zA-Z]/.test(content.slice(i + 1, lineLimit))) {
        spans.push({ start: i, end: lineLimit, inner: content.slice(i + 1, lineLimit) });
        i = lineLimit;
        continue;
      }
    }

    i += 1;
  }

  return spans;
}

function replaceOutsideMath(content: string, transform: (text: string) => string): string {
  const spans = findMathSpans(content);
  if (spans.length === 0) {
    return transform(content);
  }

  let result = "";
  let last = 0;
  for (const span of spans) {
    result += transform(content.slice(last, span.start));
    result += content.slice(span.start, span.end);
    last = span.end;
  }
  result += transform(content.slice(last));
  return result;
}

/**
 * Split `$$...$$` before embedded markdown; optionally convert remaining same-line blocks to `$...$`.
 */
export function repairBlockMath(content: string, convertOrphans = false): string {
  if (!content.includes("$$")) {
    return content;
  }
  return content.replace(/\$\$([\s\S]*?)\$\$/g, (match, inner: string) => {
    const breakAt = inner.search(MARKDOWN_INSIDE_MATH);
    if (breakAt === -1) {
      return convertOrphans && /\\[a-zA-Z]/.test(inner) ? wrapInlineMath(inner.trim()) : match;
    }
    const mathPart = inner.slice(0, breakAt).trim();
    const rest = inner.slice(breakAt);
    if (!mathPart || !/\\[a-zA-Z]/.test(mathPart)) {
      return rest.trimStart();
    }
    return `${wrapInlineMath(mathPart)}${rest}`;
  });
}

/** `\(...\)` / `\[...\]` → `$...$` (remark-math only understands dollar delimiters). */
export function convertParenMathDelimiters(content: string): string {
  if (!content.includes("\\(") && !content.includes("\\[")) {
    return content;
  }
  return replaceOutsideMath(content, (chunk) =>
    chunk
      .replace(/\\\(([\s\S]*?)\\\)/g, (_match, inner: string) => wrapInlineMath(inner.trim()))
      .replace(/\\\[([\s\S]*?)\\\]/g, (_match, inner: string) => wrapInlineMath(inner.trim())),
  );
}

/** Same-line `$$...$$` with LaTeX → `$...$`. */
export function convertBlockDollarToInline(content: string): string {
  if (!content.includes("$$")) {
    return content;
  }
  return content.replace(/\$\$([^$\n]+)\$\$/g, (match, inner: string) => {
    if (/\\[a-zA-Z]/.test(inner)) {
      return wrapInlineMath(inner.trim());
    }
    return match;
  });
}

function wrapParenLatex(match: string): string {
  return wrapInlineMath(match.slice(1, -1).trim());
}

function wrapBareLatexInText(text: string): string {
  const withInner = text.replace(PAREN_INNER_LATEX, (_match, inner: string) => wrapInlineMath(inner.trim()));
  const withParens = withInner.replace(PAREN_ARITH_LATEX, wrapParenLatex);
  return replaceOutsideMath(withParens, (chunk) =>
    chunk.replace(BARE_LATEX_RUN, (match, offset, whole) => {
      const before = whole[offset - 1];
      const after = whole[offset + match.length];
      if (before === "$" || after === "$") {
        return match;
      }
      return wrapInlineMath(match);
    }),
  );
}

/** Join `$\frac{a}{b}$ \text{...}` into one math block so `\text` renders correctly. */
export function mergeFracWithBareText(content: string): string {
  if (!content.includes("\\text")) {
    return content;
  }
  return content.replace(
    /\$((?:\\frac\{[^{}]+\}\{[^{}]+\}))\$\s+(\\text\{[^{}]*\})/g,
    (_match, frac: string, text: string) => wrapInlineMath(`${frac} ${text}`),
  );
}

/** Wrap bare LaTeX (fractions, `\times`, `\div`, `\text`, etc.) in `$...$` outside existing math. */
export function wrapBareInlineLatex(content: string): string {
  if (!content.includes("\\")) {
    return content;
  }
  return replaceOutsideMath(content, wrapBareLatexInText);
}

function escapeCurrencyInText(text: string): string {
  const preserved: string[] = [];
  let escaped = text.replace(ARITHMETIC_DOLLAR_SPAN, (match) => {
    preserved.push(match);
    return `\x00ARITH${preserved.length - 1}\x00`;
  });
  escaped = escaped.replace(CURRENCY_AMOUNT, (_match, amount: string) => escapeCurrencyAmount(amount));
  return escaped.replace(/\x00ARITH(\d+)\x00/g, (_, index: string) => preserved[Number(index)] ?? "");
}

/** Keep currency amounts like `$50` out of the math parser (outside math segments only). */
export function escapeCurrencyDollars(content: string): string {
  if (!content.includes("$")) {
    return content;
  }
  return replaceOutsideMath(content, escapeCurrencyInText);
}

function explodeMathAroundCurrency(inner: string): string {
  let result = "";
  let pending = inner;

  while (pending.length > 0) {
    const match = pending.match(/\$(\d[\d,]*(?:\.\d{1,2})?)\b/);
    if (!match || match.index === undefined) {
      const chunk = pending.trim();
      if (chunk && /\\[a-zA-Z]/.test(chunk)) {
        result += wrapInlineMath(chunk);
      } else {
        result += pending;
      }
      break;
    }

    const before = pending.slice(0, match.index).trim();
    if (before && /\\[a-zA-Z]/.test(before)) {
      result += wrapInlineMath(before);
    } else if (before) {
      result += before;
    }

    result += escapeCurrencyAmount(match[1]);
    pending = pending.slice(match.index + match[0].length);
  }

  return result;
}

/** `$50` cannot stay inside `$...$` — remark-math treats it as a closing delimiter. */
export function splitCurrencyOutOfMath(content: string): string {
  const spans = findMathSpans(content);
  if (spans.length === 0) {
    return content;
  }

  let result = "";
  let last = 0;
  for (const span of spans) {
    result += content.slice(last, span.start);
    if (/\$(\d[\d,]*(?:\.\d{1,2})?)\b/.test(span.inner)) {
      result += explodeMathAroundCurrency(span.inner);
    } else {
      result += content.slice(span.start, span.end);
    }
    last = span.end;
  }
  result += content.slice(last);
  return result;
}

/** Close an odd `$` on a LaTeX line only — never on prose/markdown lines. */
export function closeUnclosedInlineMathPerLine(content: string): string {
  if (!content.includes("$") || !content.includes("\\")) {
    return content;
  }
  return content
    .split("\n")
    .map((line) => {
      if (!/\\[a-zA-Z]/.test(line)) {
        return line;
      }
      let singles = 0;
      for (let i = 0; i < line.length; i += 1) {
        if (line[i] === "$" && line[i - 1] !== "\\" && line[i - 1] !== "$" && line[i + 1] !== "$") {
          singles += 1;
        }
      }
      return singles % 2 === 1 ? `${line}$` : line;
    })
    .join("\n");
}

/** Repair common one-line GFM tables and tutor LaTeX/markdown from streamed assistant output. */
export function normalizeAssistantMarkdown(content: string): string {
  let normalized = stripStrayDollarOnMarkdownLines(content);
  normalized = repairBlockMath(normalized);
  normalized = convertParenMathDelimiters(normalized);
  normalized = convertBlockDollarToInline(normalized);
  normalized = splitCurrencyOutOfMath(normalized);
  normalized = escapeCurrencyDollars(normalized);
  normalized = mergeFracWithBareText(normalized);
  normalized = wrapBareInlineLatex(normalized);
  normalized = closeUnclosedInlineMathPerLine(normalized);
  normalized = stripStrayDollarOnMarkdownLines(normalized);
  normalized = repairBlockMath(normalized, true);

  if (!normalized.includes("|")) {
    return normalized;
  }

  return normalized.replace(/ \| \|/g, " |\n|").replace(/\| \| /g, "|\n| ");
}
