import { describe, expect, it } from "vitest";

import { fieldMeaningfullyChanged, pickMeaningfulDraft, questionHasMeaningfulSavedAmendment } from "./App";

describe("amendment meaningful-change detection", () => {
  it("treats equal amendment values as no-op (no meaningful amendment)", () => {
    const baseQuestion = {
      result_id: "Q9(a)",
      outcome: "partial",
      earned_marks: 1,
      max_marks: 2,
      student_answer: "Plant V: the leaves are removed",
      correct_answer: "Plant V: The plant will die.",
      skill_tags: [],
      diagnosis: { mistake_type: "incomplete_explanation", reasoning: "reasoning text" },
      attempt_page_start: 7,
    };
    const basePageMap = { confidence: "medium" as const };
    const amendmentState = {
      schema_version: "marking_amendment.v1" as const,
      summary_overrides: {},
      question_amendments: [
        {
          result_id: "Q9(a)",
          fields: {
            outcome: "partial",
            earned_marks: 1,
            max_marks: 2,
          },
        },
      ],
      question_page_map_amendments: [],
      review_meta: {},
    };

    const hasMeaningful = questionHasMeaningfulSavedAmendment(
      amendmentState,
      "Q9(a)",
      baseQuestion,
      basePageMap,
    );
    expect(hasMeaningful).toBe(false);
  });

  it("keeps only meaningfully changed fields in draft", () => {
    const meaningful = pickMeaningfulDraft(
      {
        outcome: "partial",
        earned_marks: 1,
        max_marks: 2,
        "page_map.confidence": "high",
      },
      (field) => {
        if (field === "outcome") return "partial";
        if (field === "earned_marks") return 1;
        if (field === "max_marks") return 2;
        if (field === "page_map.confidence") return "medium";
        return null;
      },
    );

    expect(meaningful).toEqual({ "page_map.confidence": "high" });
  });

  it("normalizes comparable values before comparison", () => {
    expect(fieldMeaningfullyChanged("earned_marks", "1", 1)).toBe(false);
    expect(fieldMeaningfullyChanged("student_answer", "  ", null)).toBe(false);
    expect(fieldMeaningfullyChanged("skill_tags", ["a", " b "], ["a", "b"])).toBe(false);
  });
});
