import { describe, expect, it } from "vitest";

import {
  cachedReviewImagesForViewer,
  goodnotesShareLinkForViewerMode,
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

describe("goodnotesShareLinkForViewerMode", () => {
  const viewer = {
    goodnotes_share_link: "https://share.goodnotes.com/s/attempt-link",
    goodnotes_review_share_link: "https://share.goodnotes.com/s/review-link",
  };

  it("returns attempt link in attempt mode", () => {
    expect(goodnotesShareLinkForViewerMode(viewer, "attempt")).toBe(viewer.goodnotes_share_link);
  });

  it("returns review link in review mode", () => {
    expect(goodnotesShareLinkForViewerMode(viewer, "review")).toBe(viewer.goodnotes_review_share_link);
  });

  it("returns null for answer and template modes", () => {
    expect(goodnotesShareLinkForViewerMode(viewer, "answer")).toBeNull();
    expect(goodnotesShareLinkForViewerMode(viewer, "template")).toBeNull();
  });
});

describe("resolveInitialEvidenceImageUrl", () => {
  it("jumps to the mapped page in attempt mode when present in the pool", () => {
    expect(resolveInitialEvidenceImageUrl(sampleViewer.attempt_images, "attempt", 15)).toBe("/attempt/15");
  });

  it("always opens answer mode at the first page", () => {
    expect(resolveInitialEvidenceImageUrl(sampleViewer.answer_images, "answer", 36)).toBe("/answer/35");
  });

  it("falls back to the first page when the mapped page is missing", () => {
    expect(resolveInitialEvidenceImageUrl(sampleViewer.attempt_images, "attempt", 99)).toBe("/attempt/14");
  });

  it("returns null for an empty pool", () => {
    expect(resolveInitialEvidenceImageUrl([], "attempt", 14)).toBeNull();
  });
});
