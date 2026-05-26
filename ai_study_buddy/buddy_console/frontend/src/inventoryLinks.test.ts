import { describe, expect, it } from "vitest";

import { buildPdfHref, buildReviewHref, relPathForItem } from "./inventoryLinks";

describe("inventory link helpers", () => {
  it("builds a PDF deep link relative to the configured root", () => {
    const href = buildPdfHref(
      {
        absolute_path: "/roots/goodnotes/Math/emma/P4/worksheet.pdf",
        root_id: "goodnotes",
      },
      {
        goodnotes: "/roots/goodnotes",
      },
    );

    expect(href).toBe("/pdf?id=goodnotes&rel=Math%2Femma%2FP4%2Fworksheet.pdf");
  });

  it("returns null when a PDF path does not live under the configured root", () => {
    expect(
      relPathForItem(
        {
          absolute_path: "/other/path/file.pdf",
          root_id: "goodnotes",
        },
        { goodnotes: "/roots/goodnotes" },
      ),
    ).toBeNull();
  });

  it("builds a review deep link for marked attempts", () => {
    const href = buildReviewHref({
      registry_file_id: "attempt-123",
      has_marking: true,
      student_id: "emma",
    });

    expect(href).toBe("/review?attempt_id=attempt-123&student_id=emma");
  });

  it("does not build a review deep link for unmarked attempts", () => {
    expect(
      buildReviewHref({
        registry_file_id: "attempt-123",
        has_marking: false,
        student_id: "emma",
      }),
    ).toBeNull();
  });
});
