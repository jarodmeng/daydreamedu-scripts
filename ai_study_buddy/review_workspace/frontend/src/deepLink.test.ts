import { describe, expect, it } from "vitest";

import { buildReviewWorkspaceSearch, parseDeepLinkParams } from "./deepLink";

describe("review workspace deep links", () => {
  it("parses attempt_id and student_id from search string", () => {
    expect(
      parseDeepLinkParams("?attempt_id=abc-123&student_id=winston"),
    ).toEqual({
      attemptId: "abc-123",
      studentId: "winston",
    });
  });

  it("returns nulls for missing params", () => {
    expect(parseDeepLinkParams("")).toEqual({
      attemptId: null,
      studentId: null,
    });
    expect(parseDeepLinkParams("?student_id=emma")).toEqual({
      attemptId: null,
      studentId: "emma",
    });
  });

  it("trims whitespace from param values", () => {
    expect(parseDeepLinkParams("?attempt_id=%20uuid%20&student_id=%20winston%20")).toEqual({
      attemptId: "uuid",
      studentId: "winston",
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

  it("builds empty search when no params", () => {
    expect(buildReviewWorkspaceSearch({})).toBe("");
    expect(buildReviewWorkspaceSearch({ studentId: "winston" })).toBe("?student_id=winston");
  });
});
