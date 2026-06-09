/** Repair common one-line GFM tables from streamed assistant output. */
export function normalizeAssistantMarkdown(content: string): string {
  if (!content.includes("|")) {
    return content;
  }

  // Repair rows collapsed onto one line, e.g. "| A | B | |---|" or "|---| | could |".
  return content.replace(/ \| \|/g, " |\n|").replace(/\| \| /g, "|\n| ");
}
