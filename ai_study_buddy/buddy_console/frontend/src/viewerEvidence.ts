export type ViewerImage = { name: string; page_num: number; url: string };

export type ViewerMode = "attempt" | "answer" | "template" | "review";

export type ViewerImageSources = {
  attempt_images: ViewerImage[];
  answer_images: ViewerImage[];
  template_images?: ViewerImage[];
};

const EMPTY_VIEWER_IMAGES: ViewerImage[] = [];

/** Stable fallback while review evidence has not loaded (null cache). */
export function cachedReviewImagesForViewer(reviewImagesCache: ViewerImage[] | null): ViewerImage[] {
  return reviewImagesCache ?? EMPTY_VIEWER_IMAGES;
}

export function viewerImagePool(
  viewer: ViewerImageSources,
  mode: ViewerMode,
  cachedReviewImages: ViewerImage[] = EMPTY_VIEWER_IMAGES,
): ViewerImage[] {
  if (mode === "attempt") {
    return viewer.attempt_images;
  }
  if (mode === "template") {
    return viewer.template_images ?? [];
  }
  if (mode === "review") {
    return cachedReviewImages;
  }
  return viewer.answer_images;
}

export function goodnotesShareLinkForViewerMode(
  viewer: {
    goodnotes_share_link?: string | null;
    goodnotes_review_share_link?: string | null;
  },
  mode: ViewerMode,
): string | null {
  if (mode === "attempt") {
    return viewer.goodnotes_share_link ?? null;
  }
  if (mode === "review") {
    return viewer.goodnotes_review_share_link ?? null;
  }
  return null;
}

export function resolveInitialEvidenceImageUrl(
  imagePool: ViewerImage[],
  mode: ViewerMode,
  attemptPageStart: number | null | undefined,
): string | null {
  if (imagePool.length === 0) {
    return null;
  }
  // L4: page jump applies to Attempt/Template/Review only — Answer always opens at p1.
  const pageStart = mode === "answer" ? null : attemptPageStart;
  const exact = pageStart != null ? imagePool.find((img) => img.page_num === pageStart) : undefined;
  return (exact ?? imagePool[0]).url;
}
