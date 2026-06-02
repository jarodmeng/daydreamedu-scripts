export type DeepLinkParams = {
  attemptId: string | null;
  studentId: string | null;
  resultId: string | null;
  questionIndex: number | null;
};

export type ReviewWorkspaceUrlParams = {
  attemptId?: string | null;
  studentId?: string | null;
  resultId?: string | null;
  questionIndex?: number | null;
};

function parseQuestionIndex(rawValue: string | null): number | null {
  if (!rawValue) {
    return null;
  }
  const parsed = Number(rawValue.trim());
  if (!Number.isInteger(parsed) || parsed < 1) {
    return null;
  }
  return parsed;
}

export function parseDeepLinkParams(search: string): DeepLinkParams {
  const raw = search.startsWith("?") ? search.slice(1) : search;
  const q = new URLSearchParams(raw);
  return {
    attemptId: q.get("attempt_id")?.trim() || null,
    studentId: q.get("student_id")?.trim() || null,
    resultId: q.get("result_id")?.trim() || null,
    questionIndex: parseQuestionIndex(q.get("question_index")),
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
  if (params.resultId) {
    q.set("result_id", params.resultId);
  }
  if (params.questionIndex && Number.isInteger(params.questionIndex) && params.questionIndex > 0) {
    q.set("question_index", String(params.questionIndex));
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
