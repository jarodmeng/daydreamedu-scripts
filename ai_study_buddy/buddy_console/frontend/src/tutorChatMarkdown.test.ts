import { describe, expect, it } from "vitest";

import {
  closeUnclosedInlineMathPerLine,
  convertBlockDollarToInline,
  convertParenMathDelimiters,
  escapeCurrencyDollars,
  splitCurrencyOutOfMath,
  mergeFracWithBareText,
  normalizeAssistantMarkdown,
  repairBlockMath,
  wrapBareInlineLatex,
} from "./tutorChatMarkdown";

describe("normalizeAssistantMarkdown", () => {
  it("inserts row breaks in collapsed GFM tables", () => {
    const input =
      "| Modal | What it mainly suggests | |-------|-------------------------| | could | ability |";
    const output = normalizeAssistantMarkdown(input);
    expect(output).toBe(
      "| Modal | What it mainly suggests |\n|-------|-------------------------|\n| could | ability |",
    );
  });

  it("leaves normal paragraphs unchanged", () => {
    const input = "Use **could** for ability.";
    expect(normalizeAssistantMarkdown(input)).toBe(input);
  });

  it("wraps bare fractions and escapes nearby currency", () => {
    const input = "Transport: \\frac{3}{8} of salary + $50";
    expect(normalizeAssistantMarkdown(input)).toBe("Transport: $\\frac{3}{8}$ of salary + \\$50");
  });

  it("avoids pairing currency with fraction delimiters", () => {
    const input = "+ $50 and $\\frac{1}{2}$ of salary";
    expect(normalizeAssistantMarkdown(input)).toBe("+ \\$50 and $\\frac{1}{2}$ of salary");
  });

  it("converts paren delimiters and merges frac with text", () => {
    const input = "$\\frac{1}{2}$ \\text{ (rest of salary) } = 50";
    expect(normalizeAssistantMarkdown(input)).toBe("$\\frac{1}{2} \\text{ (rest of salary) }$ = 50");
  });

  it("wraps chained fractions with times", () => {
    const input = "Treat food as (\\frac{2}{3}\\times\\frac{5}{8}) of salary";
    expect(normalizeAssistantMarkdown(input)).toBe("Treat food as $\\frac{2}{3}\\times\\frac{5}{8}$ of salary");
  });

  it("wraps parenthesized div/times arithmetic", () => {
    const input = "Check (650 \\div 5 \\times 24 = 3120) quickly.";
    expect(normalizeAssistantMarkdown(input)).toBe("Check $650 \\div 5 \\times 24 = 3120$ quickly.");
  });

  it("converts \\(...\\) without leaving visible dollar delimiters", () => {
    const input = "- whole salary \\(\\frac{3}{8}\\),";
    expect(normalizeAssistantMarkdown(input)).toBe("- whole salary $\\frac{3}{8}$,");

    const input2 = "Transport: $$\\frac{3}{8}$$ of salary + $50";
    expect(normalizeAssistantMarkdown(input2)).toBe("Transport: $\\frac{3}{8}$ of salary + \\$50");
  });

  it("splits block math before markdown and keeps currency out of KaTeX", () => {
    const input = "$$\\frac{5}{8}\\text{ of salary} + $50 = $1800\n\n**Check forward:**\n$$";
    expect(normalizeAssistantMarkdown(input)).toBe(
      "$\\frac{5}{8}\\text{ of salary} +$\\$50=\\$1800\n\n**Check forward:**\n",
    );
  });

  it("does not let a trailing $ on **Check forward:** swallow markdown", () => {
    const input = "$\\frac{5}{8}\\text{ of salary} + $50 = $1800\n\n**Check forward:**$";
    const output = normalizeAssistantMarkdown(input);
    expect(output).toContain("**Check forward:**");
    expect(output).not.toMatch(/\*\*Check forward:\*\*\$/);
    expect(output).not.toMatch(/^\$\$/);
  });

  it("wraps inner (\\frac…) in table cells without swallowing prose", () => {
    const input = "| $50 | added on transport (not part of the (\\frac{3}{8})) |";
    const output = normalizeAssistantMarkdown(input);
    expect(output).toBe("| \\$50 | added on transport (not part of the $\\frac{3}{8}$) |");
    expect(output).not.toContain("$not part");
  });

  it("preserves dollar arithmetic spans and escapes standalone currency", () => {
    expect(normalizeAssistantMarkdown("$520 + 80 + 50 = 650$")).toBe("$520 + 80 + 50 = 650$");
    expect(normalizeAssistantMarkdown("paying the extra$80.")).toBe("paying the extra\\$80.");
  });

  it("normalizes a long tutor block without swallowing markdown", () => {
    const input = `That $1800 is what's left after spending 3/8 of salary and the extra $50:
\\Rightarrow \\frac{5}{8}\\text{ of salary} + $50 = $1800
So salary = ($1800 - $50) \\div \\frac{5}{8} = $2960

**Check forward:**
- Transport: \\frac{3}{8} of salary + $50

## The big idea
| Amount | Base it belongs to |
|-------|-------|
| $50 | transport |
\\checkmark`;

    const output = normalizeAssistantMarkdown(input);
    expect(output).toContain("**Check forward:**");
    expect(output).toContain("## The big idea");
    expect(output).toContain("| Amount | Base it belongs to |");
    expect(output).not.toMatch(/\$\$[\s\S]*\*\*/);
  });
});

describe("repairBlockMath", () => {
  it("ends block math before markdown headings", () => {
    const input = "$$\\frac{5}{8}\\text{ of salary}\n\n## The big idea$$";
    expect(repairBlockMath(input)).toBe("$\\frac{5}{8}\\text{ of salary}$\n\n## The big idea");
  });

  it("converts orphan same-line block math to inline", () => {
    expect(repairBlockMath("$$\\frac{3}{8}$$", true)).toBe("$\\frac{3}{8}$");
  });
});

describe("convertBlockDollarToInline", () => {
  it("maps same-line double-dollar latex to single-dollar math", () => {
    expect(convertBlockDollarToInline("$$\\frac{3}{8}$$")).toBe("$\\frac{3}{8}$");
  });
});

describe("splitCurrencyOutOfMath", () => {
  it("moves currency out of inline math delimiters", () => {
    expect(splitCurrencyOutOfMath("$\\frac{5}{8} + $50$")).toBe("$\\frac{5}{8} +$\\$50");
  });
});

describe("convertParenMathDelimiters", () => {
  it("maps inline paren delimiters to dollar math", () => {
    expect(convertParenMathDelimiters("\\(\\frac{1}{2}\\)")).toBe("$\\frac{1}{2}$");
  });
});

describe("wrapBareInlineLatex", () => {
  it("does not double-wrap fractions already in math delimiters", () => {
    const input = "Already $\\frac{3}{8}$ here.";
    expect(wrapBareInlineLatex(input)).toBe(input);
  });

  it("wraps multiple bare fractions in one line", () => {
    const input = "\\frac{3}{8} and \\frac{2}{3}";
    expect(wrapBareInlineLatex(input)).toBe("$\\frac{3}{8}$ and $\\frac{2}{3}$");
  });

  it("wraps frac and text together", () => {
    const input = "\\frac{1}{2} \\text{ (rest of salary) } = 50";
    expect(wrapBareInlineLatex(input)).toBe("$\\frac{1}{2} \\text{ (rest of salary) }$ = 50");
  });

  it("wraps frac-times-frac as one run", () => {
    const input = "\\frac{2}{3}\\times\\frac{5}{8}";
    expect(wrapBareInlineLatex(input)).toBe("$\\frac{2}{3}\\times\\frac{5}{8}$");
  });

  it("wraps Rightarrow with following frac", () => {
    const input = "\\Rightarrow \\frac{5}{8}\\text{ of salary}";
    expect(wrapBareInlineLatex(input)).toBe("$\\Rightarrow \\frac{5}{8}\\text{ of salary}$");
  });
});

describe("mergeFracWithBareText", () => {
  it("joins split frac/text math blocks", () => {
    const input = "$\\frac{1}{2}$ \\text{ (rest of salary) }";
    expect(mergeFracWithBareText(input)).toBe("$\\frac{1}{2} \\text{ (rest of salary) }$");
  });
});

describe("escapeCurrencyDollars", () => {
  it("escapes currency outside math blocks", () => {
    const input = "costs $50. Next $\\frac{1}{2}$";
    expect(escapeCurrencyDollars(input)).toBe("costs \\$50. Next $\\frac{1}{2}$");
  });
});

describe("closeUnclosedInlineMathPerLine", () => {
  it("closes an odd inline math delimiter at end of line", () => {
    const input = "$\\frac{5}{8}\\text{ of salary} + \\$50 = \\$1800";
    expect(closeUnclosedInlineMathPerLine(input)).toBe(
      "$\\frac{5}{8}\\text{ of salary} + \\$50 = \\$1800$",
    );
  });
});
