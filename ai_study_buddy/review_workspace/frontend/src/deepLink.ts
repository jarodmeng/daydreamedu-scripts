export type DeepLinkParams = {
  attemptId: string | null;
  studentId: string | null;
};

export type ReviewWorkspaceUrlParams = {
  attemptId?: string | null;
  studentId?: string | null;
};

export function parseDeepLinkParams(search: string): DeepLinkParams {
  const raw = search.startsWith("?") ? search.slice(1) : search;
  const q = new URLSearchParams(raw);
  return {
    attemptId: q.get("attempt_id")?.trim() || null,
    studentId: q.get("student_id")?.trim() || null,
  };
}

export function buildReviewWorkspaceSearch(params: ReviewWorkspaceUrlParams): string {
  const q = new URLSearchParams();
  if (params.attemptId) {
    q.set("attempt_id", params.attemptId);
  }
  if (params.studentId) {
    q.set("student_id", params.studentId);
  }
  const serialized = q.toString();
  return serialized ? `?${serialized}` : "";
}

export function replaceReviewWorkspaceUrl(params: ReviewWorkspaceUrlParams): void {
  if (typeof window === "undefined") {
    return;
  }
  const search = buildReviewWorkspaceSearch(params);
  const url = `${window.location.pathname}${search}${window.location.hash}`;
  window.history.replaceState(null, "", url);
}
