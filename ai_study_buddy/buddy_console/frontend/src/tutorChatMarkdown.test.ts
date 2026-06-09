import { describe, expect, it } from "vitest";

import { normalizeAssistantMarkdown } from "./tutorChatMarkdown";

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
});
