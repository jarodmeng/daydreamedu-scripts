import { describe, expect, it } from "vitest";
import {
  buildCompletionDateOverwriteMessage,
  canEditCompletionDate,
  needsCompletionDateConfirm,
} from "./completionDateEdit";

const base = {
  is_registered: true,
  scope: "completion",
  registry_file_id: "file-1",
  completion_date: null,
  completion_date_source: null,
};

describe("canEditCompletionDate", () => {
  it("allows registered completion with registry id", () => {
    expect(canEditCompletionDate(base)).toBe(true);
  });

  it("rejects template scope", () => {
    expect(canEditCompletionDate({ ...base, scope: "template" })).toBe(false);
  });

  it("rejects unregistered", () => {
    expect(canEditCompletionDate({ ...base, is_registered: false, registry_file_id: null })).toBe(
      false,
    );
  });
});

describe("needsCompletionDateConfirm", () => {
  it("is false when no prior source", () => {
    expect(needsCompletionDateConfirm(base)).toBe(false);
  });

  it("is false for manual source", () => {
    expect(
      needsCompletionDateConfirm({
        ...base,
        completion_date: "2026-01-01",
        completion_date_source: "manual",
      }),
    ).toBe(false);
  });

  it("is true for inferred source", () => {
    expect(
      needsCompletionDateConfirm({
        ...base,
        completion_date: "2026-01-01",
        completion_date_source: "handwritten_page1",
      }),
    ).toBe(true);
  });
});

describe("buildCompletionDateOverwriteMessage", () => {
  it("includes current and new dates", () => {
    const msg = buildCompletionDateOverwriteMessage(
      {
        ...base,
        completion_date: "2026-01-01",
        completion_date_source: "filename_term",
      },
      "2026-03-15",
    );
    expect(msg).toContain("2026-01-01");
    expect(msg).toContain("filename_term");
    expect(msg).toContain("2026-03-15");
  });
});
