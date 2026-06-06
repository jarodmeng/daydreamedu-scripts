import { describe, expect, it } from "vitest";

import { buildReviewWorkspaceSearch, parseDeepLinkParams } from "./deepLink";

describe("review workspace deep links", () => {
  it("parses attempt_id and student_id from search string", () => {
    expect(
      parseDeepLinkParams("?attempt_id=abc-123&student_id=winston"),
    ).toEqual({
      attemptId: "abc-123",
      studentId: "winston",
      resultId: null,
      questionIndex: null,
    });
  });

  it("returns nulls for missing params", () => {
    expect(parseDeepLinkParams("")).toEqual({
      attemptId: null,
      studentId: null,
      resultId: null,
      questionIndex: null,
    });
    expect(parseDeepLinkParams("?student_id=emma")).toEqual({
      attemptId: null,
      studentId: "emma",
      resultId: null,
      questionIndex: null,
    });
  });

  it("trims whitespace from param values", () => {
    expect(parseDeepLinkParams("?attempt_id=%20uuid%20&student_id=%20winston%20")).toEqual({
      attemptId: "uuid",
      studentId: "winston",
      resultId: null,
      questionIndex: null,
    });
  });

  it("parses result_id and question_index when provided", () => {
    expect(parseDeepLinkParams("?attempt_id=a1&result_id=Q4&question_index=3")).toEqual({
      attemptId: "a1",
      studentId: null,
      resultId: "Q4",
      questionIndex: 3,
    });
  });

  it("ignores invalid question_index values", () => {
    expect(parseDeepLinkParams("?question_index=0").questionIndex).toBeNull();
    expect(parseDeepLinkParams("?question_index=-2").questionIndex).toBeNull();
    expect(parseDeepLinkParams("?question_index=abc").questionIndex).toBeNull();
    expect(parseDeepLinkParams("?question_index=2.5").questionIndex).toBeNull();
  });

  it("builds search with result_id and question_index", () => {
    expect(
      buildReviewWorkspaceSearch({
        attemptId: "d88d78e1-0844-44c4-be4e-230651166612",
        studentId: "winston",
        resultId: "Q4",
        questionIndex: 3,
      }),
    ).toBe(
      "?attempt_id=d88d78e1-0844-44c4-be4e-230651166612&student_id=winston&result_id=Q4&question_index=3",
    );
  });

  it("skips invalid question_index when building search", () => {
    expect(
      buildReviewWorkspaceSearch({
        attemptId: "a1",
        questionIndex: 0,
      }),
    ).toBe("?attempt_id=a1");
    expect(
      buildReviewWorkspaceSearch({
        attemptId: "a1",
        questionIndex: -3,
      }),
    ).toBe("?attempt_id=a1");
    expect(
      buildReviewWorkspaceSearch({
        attemptId: "a1",
        questionIndex: 1.5,
      }),
    ).toBe("?attempt_id=a1");
  });

  it("trims whitespace from result_id", () => {
    expect(parseDeepLinkParams("?result_id=%20Q5%20")).toEqual({
      attemptId: null,
      studentId: null,
      resultId: "Q5",
      questionIndex: null,
    });
  });

  it("builds search string with attempt_id and student_id", () => {
    expect(
      buildReviewWorkspaceSearch({
        attemptId: "d88d78e1-0844-44c4-be4e-230651166612",
        studentId: "winston",
      }),
    ).toBe("?attempt_id=d88d78e1-0844-44c4-be4e-230651166612&student_id=winston");
  });

  it("parses parenthetical result_id values", () => {
    expect(parseDeepLinkParams("?result_id=Q17%28b%29&question_index=21")).toEqual({
      attemptId: null,
      studentId: null,
      resultId: "Q17(b)",
      questionIndex: 21,
    });
  });

  it("builds empty search when no params", () => {
    expect(buildReviewWorkspaceSearch({})).toBe("");
    expect(buildReviewWorkspaceSearch({ studentId: "winston" })).toBe("?student_id=winston");
  });
});
