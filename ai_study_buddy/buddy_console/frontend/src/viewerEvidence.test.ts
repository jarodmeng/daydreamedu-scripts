import { describe, expect, it } from "vitest";

import {
  cachedReviewImagesForViewer,
  resolveInitialEvidenceImageUrl,
  viewerImagePool,
} from "./viewerEvidence";

const sampleViewer = {
  attempt_images: [
    { name: "page-14.png", page_num: 14, url: "/attempt/14" },
    { name: "page-15.png", page_num: 15, url: "/attempt/15" },
  ],
  answer_images: [
    { name: "page-35.png", page_num: 35, url: "/answer/35" },
    { name: "page-36.png", page_num: 36, url: "/answer/36" },
  ],
  template_images: [{ name: "page-014.png", page_num: 14, url: "/template/14" }],
};

describe("cachedReviewImagesForViewer", () => {
  it("returns a stable empty-array reference when review cache is null", () => {
    expect(cachedReviewImagesForViewer(null)).toBe(cachedReviewImagesForViewer(null));
  });

  it("returns the loaded cache array when present", () => {
    const loaded = [{ name: "page-01.png", page_num: 1, url: "/review/1" }];
    expect(cachedReviewImagesForViewer(loaded)).toBe(loaded);
  });

  it("guards against the unstable nullish fallback that broke page navigation", () => {
    // WorkspaceView had `reviewImagesCache ?? []`, which creates a new [] every render
    // and retriggered the evidence image-sync effect on every paint.
    expect(null ?? []).not.toBe(null ?? []);
    expect(cachedReviewImagesForViewer(null)).toBe(cachedReviewImagesForViewer(null));
  });
});

describe("viewerImagePool", () => {
  it("selects answer images in answer mode", () => {
    expect(viewerImagePool(sampleViewer, "answer")).toBe(sampleViewer.answer_images);
  });

  it("selects cached review images in review mode", () => {
    const reviewImages = [{ name: "page-02.png", page_num: 2, url: "/review/2" }];
    expect(viewerImagePool(sampleViewer, "review", reviewImages)).toBe(reviewImages);
  });
});

describe("resolveInitialEvidenceImageUrl", () => {
  it("jumps to the mapped page when present in the pool", () => {
    expect(resolveInitialEvidenceImageUrl(sampleViewer.answer_images, 36)).toBe("/answer/36");
  });

  it("falls back to the first page when the mapped page is missing", () => {
    expect(resolveInitialEvidenceImageUrl(sampleViewer.answer_images, 14)).toBe("/answer/35");
  });

  it("returns null for an empty pool", () => {
    expect(resolveInitialEvidenceImageUrl([], 14)).toBeNull();
  });
});
