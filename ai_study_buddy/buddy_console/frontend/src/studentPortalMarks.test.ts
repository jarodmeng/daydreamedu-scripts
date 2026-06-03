import { describe, expect, it } from "vitest";
import { formatPercent, tableRowTypes } from "./studentPortalApi";
import type { MarksByQuestionTypeBlock } from "./studentPortalApi";

describe("studentPortalApi helpers", () => {
  it("formatPercent renders em dash for null", () => {
    expect(formatPercent(null)).toBe("—");
    expect(formatPercent(75.8)).toBe("75.8%");
  });

  it("tableRowTypes appends UNKNOWN after type_order", () => {
    const block: MarksByQuestionTypeBlock = {
      subject_context: "singapore_primary_math",
      display_label: "Math",
      type_order: ["MCQ", "SAQ"],
      marks_by_question_type: {
        question_count: 2,
        earned_marks: 1,
        max_marks: 2,
        percentage: 50,
        by_type: {
          MCQ: { question_count: 1, earned_marks: 1, max_marks: 1, percentage: 100 },
          SAQ: { question_count: 1, earned_marks: 0, max_marks: 1, percentage: 0 },
          UNKNOWN: { question_count: 0, earned_marks: 0, max_marks: 0, percentage: null },
        },
      },
    };
    expect(tableRowTypes(block)).toEqual(["MCQ", "SAQ", "UNKNOWN"]);
  });
});
