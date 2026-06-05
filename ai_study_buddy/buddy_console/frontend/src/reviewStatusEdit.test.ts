import { describe, expect, it } from "vitest";
import {
  canToggleReviewStatus,
  reviewStatusToggleLabel,
  reviewStatusToggleTarget,
} from "./reviewStatusEdit";

const base = {
  has_marking: true,
  registry_file_id: "attempt-1",
  review_status: "not_started",
};

describe("canToggleReviewStatus", () => {
  it("allows marked completions with registry id", () => {
    expect(canToggleReviewStatus(base)).toBe(true);
  });

  it("rejects unmarked completions", () => {
    expect(canToggleReviewStatus({ ...base, has_marking: false })).toBe(false);
  });
});

describe("reviewStatusToggleLabel", () => {
  it("offers complete when not completed", () => {
    expect(reviewStatusToggleLabel("not_started")).toBe("Mark review completed");
    expect(reviewStatusToggleLabel("in_progress")).toBe("Mark review completed");
  });

  it("offers revert when completed", () => {
    expect(reviewStatusToggleLabel("completed")).toBe("Revert review");
  });
});

describe("reviewStatusToggleTarget", () => {
  it("targets completed from open states", () => {
    expect(reviewStatusToggleTarget("not_started")).toBe("completed");
    expect(reviewStatusToggleTarget("in_progress")).toBe("completed");
  });

  it("targets not_started when reverting", () => {
    expect(reviewStatusToggleTarget("completed")).toBe("not_started");
  });
});
