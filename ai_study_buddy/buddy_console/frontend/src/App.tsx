import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

import { parseDeepLinkParams, replaceReviewWorkspaceUrl } from "./deepLink";

type StudentRow = {
  student_id: string;
  display_name: string;
  grade_level: string;
};

type AttemptListItem = {
  attempt_id: string;
  title: string;
  student_id: string;
  subject_context: string | null;
  grade_bucket: string | null;
  collection_kind: "exam" | "book";
  book_label: string | null;
  marking_status: "marked" | "not_marked";
  review_status: "not_started" | "in_progress" | "completed";
  latest_marked_at: string | null;
  attempt_sequence: number | null;
  is_partial: boolean | null;
  score: {
    earned_marks: number | null;
    total_marks: number | null;
    percentage: number | null;
  } | null;
};

type QuestionRow = {
  result_id: string;
  outcome: string;
  earned_marks: number;
  max_marks: number;
  student_answer: string | null;
  correct_answer: string | null;
  skill_tags: string[];
  diagnosis: {
    mistake_type: string | null;
    reasoning: string | null;
  };
  attempt_page_start: number | null;
};

type MarkingResult = {
  schema_version: string;
  summary: {
    earned_marks: number;
    total_marks: number;
    percentage: number;
    overall_assessment: string;
    human_note?: string | null;
  };
  context: {
    is_partial: boolean;
    question_selection?: {
      raw_text?: string | null;
    };
    question_page_map: Array<{
      result_id: string;
      attempt_page_start: number;
      confidence: "high" | "medium" | "low";
    }>;
  };
  question_results: QuestionRow[];
};

type AmendmentState = {
  schema_version: "marking_amendment.v1";
  summary_overrides: Record<string, unknown>;
  question_amendments: Array<{
    result_id: string;
    fields: Record<string, unknown>;
    reviewer_reason?: string;
    updated_at?: string;
    updated_by?: string;
  }>;
  question_page_map_amendments: Array<{
    result_id: string;
    attempt_page_start?: number;
    confidence?: "high" | "medium" | "low";
    updated_at?: string;
    updated_by?: string;
  }>;
  review_meta: {
    updated_at?: string | null;
    updated_by?: string | null;
  };
};

type AttemptDetail = {
  attempt: {
    attempt_id: string;
    title: string;
    student_id: string;
    subject_context: string;
    book_label: string | null;
  };
  marking_status: "marked" | "not_marked";
  marking_result: MarkingResult | null;
  marking_result_base?: MarkingResult | null;
  marking_result_resolved?: MarkingResult | null;
  amendment_state?: AmendmentState;
  review_state: {
    review_status: "not_started" | "in_progress" | "completed";
    question_reviews: Array<{ result_id: string; note_text?: string; review_status?: string }>;
    attempt_notes: Array<{ note_text: string }>;
    student_subject_notes: Array<{ note_text: string }>;
  };
  viewer: {
    mode_default: "attempt" | "answer";
    attempt_images: Array<{ name: string; page_num: number; url: string }>;
    answer_images: Array<{ name: string; page_num: number; url: string }>;
    template_images: Array<{ name: string; page_num: number; url: string }>;
  };
};

type ViewerMode = "attempt" | "answer" | "template";

function viewerImagePool(
  viewer: AttemptDetail["viewer"],
  mode: ViewerMode,
): Array<{ name: string; page_num: number; url: string }> {
  if (mode === "attempt") {
    return viewer.attempt_images;
  }
  if (mode === "template") {
    return viewer.template_images ?? [];
  }
  return viewer.answer_images;
}
type NoteScope = "question" | "attempt" | "student_subject";
type SaveStatus = "idle" | "unsaved" | "saving" | "saved" | "error";
type EditableFieldKey =
  | "outcome"
  | "earned_marks"
  | "max_marks"
  | "student_answer"
  | "correct_answer"
  | "diagnosis.mistake_type"
  | "diagnosis.reasoning"
  | "skill_tags"
  | "human_note"
  | "attempt_page_start"
  | "page_map.confidence";

type Screen = "picker" | "my_work" | "workspace";
const WIDE_AMENDMENT_FIELDS = new Set<EditableFieldKey>([
  "student_answer",
  "correct_answer",
  "diagnosis.reasoning",
  "skill_tags",
  "human_note",
]);
const METRIC_AMENDMENT_FIELDS = new Set<EditableFieldKey>(["outcome", "earned_marks", "max_marks"]);
const MARKDOWN_AMENDMENT_FIELDS = new Set<EditableFieldKey>([
  "student_answer",
  "correct_answer",
  "diagnosis.reasoning",
  "human_note",
]);
const SCIENCE_SKILL_TAG_PRESET_OPTIONS: string[][] = [
  ["Cycles > Cycles in Matter and Water > Matter"],
  ["Cycles > Cycles in Matter and Water > Water"],
  ["Cycles > Cycles in Plants and Animals > Life cycles"],
  ["Cycles > Cycles in Plants and Animals > Reproduction"],
  ["Diversity > Diversity of Living and Non-Living Things > General characteristics and classification"],
  ["Diversity > Diversity of Materials"],
  ["Energy > Energy Conversion"],
  ["Energy > Energy Forms and Uses > Heat"],
  ["Energy > Energy Forms and Uses > Light"],
  ["Energy > Energy Forms and Uses > Photosynthesis"],
  ["Interactions > Interaction of Forces > Frictional force, gravitational force, elastic spring force"],
  ["Interactions > Interaction of Forces > Magnets"],
  ["Interactions > Interactions within the Environment"],
  ["Systems > Electrical System"],
  ["Systems > Human System > Digestive system"],
  ["Systems > Human System > Respiratory and circulatory systems"],
  ["Systems > Plant System > Plant parts and functions"],
  ["Systems > Plant System > Respiratory and circulatory systems"],
  ["Experiments > Fair-test"],
];

const STORAGE_KEY_STUDENT = "buddy_console.review.student_id";

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

async function fetchAttemptDetail(attemptId: string): Promise<AttemptDetail> {
  const res = await fetch(`/api/student/attempts/${encodeURIComponent(attemptId)}`);
  if (res.status === 404) {
    throw new Error("Attempt not found");
  }
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status}`);
  }
  return res.json() as Promise<AttemptDetail>;
}

function resolveDeepLinkQuestionId(
  questions: QuestionRow[],
  resultId: string | null,
  questionIndex: number | null,
): string | null {
  if (resultId) {
    const normalized = resultId.trim().toLowerCase();
    const matched = questions.find((row) => (row.result_id ?? "").trim().toLowerCase() === normalized);
    if (matched) {
      return matched.result_id;
    }
  }
  if (questionIndex && questionIndex >= 1 && questionIndex <= questions.length) {
    return questions[questionIndex - 1]?.result_id ?? null;
  }
  return null;
}

function resolveRequestedQuestionIdFromCurrentUrl(questions: QuestionRow[]): string | null {
  const deepLink = parseDeepLinkParams(window.location.search);
  return resolveDeepLinkQuestionId(questions, deepLink.resultId, deepLink.questionIndex);
}

function resolveInitialStudentId(
  students: StudentRow[],
  deepLinkStudentId: string | null,
  storedStudentId: string,
): string {
  if (deepLinkStudentId && students.some((s) => s.student_id === deepLinkStudentId)) {
    return deepLinkStudentId;
  }
  if (storedStudentId && students.some((s) => s.student_id === storedStudentId)) {
    return storedStudentId;
  }
  return students[0]?.student_id ?? "";
}

function formatPct(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }
  return `${Math.round(value)}%`;
}

function isIncorrectQuestion(q: QuestionRow): boolean {
  const outcome = (q.outcome ?? "").toLowerCase();
  if (outcome === "wrong" || outcome === "incorrect" || outcome === "partial") {
    return true;
  }
  if (typeof q.earned_marks === "number" && typeof q.max_marks === "number") {
    return q.max_marks > 0 && q.earned_marks < q.max_marks;
  }
  return false;
}

function questionStatusEmoji(q: QuestionRow): string {
  const outcome = (q.outcome ?? "").toLowerCase();
  if (outcome === "correct") {
    return "✅";
  }
  if (outcome === "partial") {
    return "⚠️";
  }
  if (outcome === "wrong" || outcome === "incorrect") {
    return "❌";
  }
  if (outcome === "excluded" || outcome === "disqualified") {
    return "🚫";
  }
  if (typeof q.earned_marks === "number" && typeof q.max_marks === "number") {
    if (q.max_marks > 0 && q.earned_marks <= 0) {
      return "❌";
    }
    if (q.earned_marks < q.max_marks) {
      return "⚠️";
    }
    if (q.earned_marks >= q.max_marks) {
      return "✅";
    }
  }
  return "•";
}

function isQuestionReviewMarkedReviewed(row: { review_status?: string; note_text?: string }): boolean {
  if (row.review_status === "reviewed") {
    return true;
  }
  return (row.note_text ?? "").trim().length > 0;
}

function getQuestionFieldValue(q: QuestionRow | null, field: EditableFieldKey): unknown {
  if (!q) {
    return null;
  }
  if (field === "diagnosis.mistake_type") {
    return q.diagnosis?.mistake_type ?? null;
  }
  if (field === "diagnosis.reasoning") {
    return q.diagnosis?.reasoning ?? null;
  }
  if (field === "attempt_page_start") {
    return q.attempt_page_start;
  }
  if (field === "page_map.confidence") {
    return null;
  }
  return q[field as keyof QuestionRow] ?? null;
}

function formatFieldValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.join(" | ") || "-";
  }
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return String(value);
}

function normalizeSkillTagsArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  const out: string[] = [];
  value.forEach((item) => {
    if (typeof item !== "string") {
      return;
    }
    const trimmed = item.trim();
    if (trimmed) {
      out.push(trimmed);
    }
  });
  return out;
}

function skillTagsLabel(tags: string[]): string {
  return tags.join(" > ");
}

function renderInlineMarkdown(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let cursor = 0;
  let key = 0;
  while (cursor < text.length) {
    const boldAt = text.indexOf("**", cursor);
    const italicAt = text.indexOf("*", cursor);
    const hasBold = boldAt !== -1;
    const hasItalic = italicAt !== -1;
    if (!hasBold && !hasItalic) {
      nodes.push(text.slice(cursor));
      break;
    }
    const nextAt = hasBold && hasItalic ? Math.min(boldAt, italicAt) : hasBold ? boldAt : italicAt;
    if (nextAt > cursor) {
      nodes.push(text.slice(cursor, nextAt));
      cursor = nextAt;
      continue;
    }
    if (text.startsWith("**", cursor)) {
      const close = text.indexOf("**", cursor + 2);
      if (close === -1) {
        nodes.push("**");
        cursor += 2;
      } else {
        nodes.push(<strong key={`md-b-${key}`}>{text.slice(cursor + 2, close)}</strong>);
        key += 1;
        cursor = close + 2;
      }
      continue;
    }
    if (text[cursor] === "*") {
      const close = text.indexOf("*", cursor + 1);
      if (close === -1) {
        nodes.push("*");
        cursor += 1;
      } else {
        nodes.push(<em key={`md-i-${key}`}>{text.slice(cursor + 1, close)}</em>);
        key += 1;
        cursor = close + 1;
      }
      continue;
    }
  }
  return nodes;
}

function renderMarkdownText(text: string): ReactNode {
  const lines = text.split("\n");
  return lines.map((line, index) => (
    <span key={`md-line-${index}`}>
      {renderInlineMarkdown(line)}
      {index < lines.length - 1 ? <br /> : null}
    </span>
  ));
}

function valuesEqual(a: unknown, b: unknown): boolean {
  return JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
}

export function normalizeComparableFieldValue(field: EditableFieldKey, value: unknown): unknown {
  if (field === "earned_marks" || field === "max_marks" || field === "attempt_page_start") {
    if (value === null || value === undefined || value === "") {
      return null;
    }
    if (typeof value === "number") {
      return Number.isFinite(value) ? value : null;
    }
    if (typeof value === "string") {
      const trimmed = value.trim();
      if (!trimmed) {
        return null;
      }
      const parsed = Number(trimmed);
      return Number.isFinite(parsed) ? parsed : null;
    }
    return value;
  }
  if (
    field === "student_answer" ||
    field === "correct_answer" ||
    field === "diagnosis.mistake_type" ||
    field === "diagnosis.reasoning" ||
    field === "human_note" ||
    field === "outcome" ||
    field === "page_map.confidence"
  ) {
    if (value === null || value === undefined) {
      return null;
    }
    if (typeof value === "string") {
      const trimmed = value.trim();
      return trimmed || null;
    }
    return value;
  }
  if (field === "skill_tags") {
    if (!Array.isArray(value)) {
      return value;
    }
    return value.map((item) => (typeof item === "string" ? item.trim() : item)).filter((item) => Boolean(item));
  }
  return value ?? null;
}

export function fieldMeaningfullyChanged(field: EditableFieldKey, value: unknown, baseValue: unknown): boolean {
  return !valuesEqual(normalizeComparableFieldValue(field, value), normalizeComparableFieldValue(field, baseValue));
}

export function pickMeaningfulDraft(
  draft: Record<string, unknown>,
  baseByField: (field: EditableFieldKey) => unknown,
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  (Object.keys(draft) as EditableFieldKey[]).forEach((field) => {
    const value = draft[field];
    if (fieldMeaningfullyChanged(field, value, baseByField(field))) {
      out[field] = normalizeComparableFieldValue(field, value);
    }
  });
  return out;
}

function savedQuestionFields(amendmentState: AmendmentState | undefined, resultId: string): Record<string, unknown> {
  const row = amendmentState?.question_amendments.find((item) => item.result_id === resultId);
  return row?.fields ?? {};
}

function savedPageMapFields(amendmentState: AmendmentState | undefined, resultId: string): Record<string, unknown> {
  const row = amendmentState?.question_page_map_amendments.find((item) => item.result_id === resultId);
  if (!row) {
    return {};
  }
  const out: Record<string, unknown> = {};
  if (row.attempt_page_start !== undefined) {
    out.attempt_page_start = row.attempt_page_start;
  }
  if (row.confidence !== undefined) {
    out["page_map.confidence"] = row.confidence;
  }
  return out;
}

function savedDraftForQuestion(amendmentState: AmendmentState | undefined, resultId: string): Record<string, unknown> {
  return {
    ...savedQuestionFields(amendmentState, resultId),
    ...savedPageMapFields(amendmentState, resultId),
  };
}

function questionHasSavedAmendment(amendmentState: AmendmentState | undefined, resultId: string): boolean {
  return (
    Object.keys(savedQuestionFields(amendmentState, resultId)).length > 0 ||
    Object.keys(savedPageMapFields(amendmentState, resultId)).length > 0
  );
}

export function questionHasMeaningfulSavedAmendment(
  amendmentState: AmendmentState | undefined,
  resultId: string,
  baseQuestion: QuestionRow | null,
  basePageMap: { confidence?: "high" | "medium" | "low" } | null,
): boolean {
  const savedDraft = savedDraftForQuestion(amendmentState, resultId);
  return (Object.keys(savedDraft) as EditableFieldKey[]).some((field) => {
    const baseValue = field === "page_map.confidence" ? basePageMap?.confidence ?? null : getQuestionFieldValue(baseQuestion, field);
    return fieldMeaningfullyChanged(field, savedDraft[field], baseValue);
  });
}

function coerceDraftValue(field: EditableFieldKey, value: string): unknown {
  if (field === "earned_marks" || field === "max_marks" || field === "attempt_page_start") {
    return value.trim() === "" ? null : Number(value);
  }
  if (field === "skill_tags") {
    return value
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean);
  }
  return value.trim() === "" ? null : value;
}

function needsReviewerReason(draft: Record<string, unknown>): boolean {
  return ["outcome", "earned_marks", "max_marks"].some((field) => Object.prototype.hasOwnProperty.call(draft, field));
}

function WorkspaceView({
  detail,
  onBack,
  initialResultId,
}: {
  detail: AttemptDetail;
  onBack: () => void;
  initialResultId?: string | null;
}) {
  const [viewerMode, setViewerMode] = useState<ViewerMode>("attempt");
  const [viewerZoomPct, setViewerZoomPct] = useState<number>(50);
  const [activeQuestionId, setActiveQuestionId] = useState<string>("");
  const [activeImageUrl, setActiveImageUrl] = useState<string | null>(null);
  const [noteScope, setNoteScope] = useState<NoteScope>("question");
  const [notesExpanded, setNotesExpanded] = useState<boolean>(false);
  const [noteDraft, setNoteDraft] = useState<string>("");
  const [noteSaved, setNoteSaved] = useState<boolean>(true);
  const [activeDetail, setActiveDetail] = useState<AttemptDetail>(detail);
  const reviewCardRef = useRef<HTMLElement | null>(null);
  const [amendmentDraft, setAmendmentDraft] = useState<Record<string, unknown>>({});
  const [editField, setEditField] = useState<EditableFieldKey | null>(null);
  const [reviewerReason, setReviewerReason] = useState<string>("");
  const [amendmentSaveStatus, setAmendmentSaveStatus] = useState<SaveStatus>("idle");
  const [amendmentError, setAmendmentError] = useState<string | null>(null);

  useEffect(() => {
    const urlInitialResultId = resolveRequestedQuestionIdFromCurrentUrl(detail.marking_result?.question_results ?? []);
    setActiveDetail(detail);
    setViewerMode("attempt");
    setViewerZoomPct(50);
    setActiveQuestionId(initialResultId ?? urlInitialResultId ?? "");
    setActiveImageUrl(null);
    setNoteScope("question");
    setNotesExpanded(false);
    setNoteDraft("");
    setNoteSaved(true);
    setAmendmentDraft({});
    setEditField(null);
    setReviewerReason("");
    setAmendmentSaveStatus("idle");
    setAmendmentError(null);
  }, [detail, initialResultId]);

  const questions = activeDetail.marking_result?.question_results ?? [];
  const baseQuestions = activeDetail.marking_result_base?.question_results ?? [];
  const isScienceSubject = (activeDetail.attempt.subject_context ?? "").toLowerCase().includes("science");
  const scienceSkillTagOptions = useMemo(() => {
    if (!isScienceSubject) {
      return [] as Array<{ value: string; label: string }>;
    }
    const seen = new Set<string>();
    const options: Array<{ value: string; label: string }> = [];
    const allQuestions = [...questions, ...baseQuestions];
    allQuestions.forEach((row) => {
      const tags = normalizeSkillTagsArray(row?.skill_tags);
      if (tags.length === 0) {
        return;
      }
      const value = JSON.stringify(tags);
      if (seen.has(value)) {
        return;
      }
      seen.add(value);
      options.push({ value, label: skillTagsLabel(tags) });
    });
    SCIENCE_SKILL_TAG_PRESET_OPTIONS.forEach((tags) => {
      const value = JSON.stringify(tags);
      if (seen.has(value)) {
        return;
      }
      seen.add(value);
      options.push({ value, label: skillTagsLabel(tags) });
    });
    return options.sort((a, b) => a.label.localeCompare(b.label));
  }, [isScienceSubject, questions, baseQuestions]);
  const questionSelectionRawText = activeDetail.marking_result?.context?.question_selection?.raw_text ?? null;

  useEffect(() => {
    if (questions.length === 0) {
      return;
    }
    const selectedQuestion = questions.find((q) => q.result_id === activeQuestionId);
    if (!activeQuestionId || !selectedQuestion) {
      const priorityQuestion = questions.find((q) => isIncorrectQuestion(q)) ?? questions[0];
      setActiveQuestionId(priorityQuestion.result_id);
      return;
    }
    const pageStart = selectedQuestion.attempt_page_start;
    const imagePool = viewerImagePool(activeDetail.viewer, viewerMode);
    if (imagePool.length === 0) {
      setActiveImageUrl(null);
      return;
    }
    const exact = pageStart != null ? imagePool.find((img) => img.page_num === pageStart) : undefined;
    setActiveImageUrl((exact ?? imagePool[0]).url);
  }, [questions, activeQuestionId, viewerMode, activeDetail.viewer]);

  useEffect(() => {
    if (!activeQuestionId) {
      return;
    }
    replaceReviewWorkspaceUrl({
      attemptId: activeDetail.attempt.attempt_id,
      studentId: activeDetail.attempt.student_id,
      resultId: activeQuestionId,
    });
  }, [activeQuestionId, activeDetail.attempt.attempt_id, activeDetail.attempt.student_id]);

  const activeQuestion = useMemo(
    () => questions.find((q) => q.result_id === activeQuestionId) ?? null,
    [questions, activeQuestionId],
  );
  const incorrectOrPartialQuestionIds = useMemo(
    () => new Set(questions.filter((q) => isIncorrectQuestion(q)).map((q) => q.result_id)),
    [questions],
  );
  const activeBaseQuestion = useMemo(
    () => baseQuestions.find((q) => q.result_id === activeQuestionId) ?? null,
    [baseQuestions, activeQuestionId],
  );
  const activePageMap = useMemo(
    () => activeDetail.marking_result?.context.question_page_map.find((entry) => entry.result_id === activeQuestionId) ?? null,
    [activeDetail.marking_result, activeQuestionId],
  );
  const activeBasePageMap = useMemo(
    () =>
      activeDetail.marking_result_base?.context.question_page_map.find((entry) => entry.result_id === activeQuestionId) ??
      null,
    [activeDetail.marking_result_base, activeQuestionId],
  );
  const persistedAmendmentDraft = useMemo(
    () => savedDraftForQuestion(activeDetail.amendment_state, activeQuestionId),
    [activeDetail.amendment_state, activeQuestionId],
  );
  const meaningfulPersistedAmendmentDraft = useMemo(
    () =>
      pickMeaningfulDraft(persistedAmendmentDraft, (field) =>
        field === "page_map.confidence" ? activeBasePageMap?.confidence ?? null : getQuestionFieldValue(activeBaseQuestion, field),
      ),
    [persistedAmendmentDraft, activeBaseQuestion, activeBasePageMap],
  );
  const meaningfulAmendmentDraft = useMemo(
    () =>
      pickMeaningfulDraft(amendmentDraft, (field) =>
        field === "page_map.confidence" ? activeBasePageMap?.confidence ?? null : getQuestionFieldValue(activeBaseQuestion, field),
      ),
    [amendmentDraft, activeBaseQuestion, activeBasePageMap],
  );
  const meaningfulAmendmentDraftForSave = useMemo(
    () =>
      pickMeaningfulDraft(amendmentDraft, (field) =>
        field === "page_map.confidence"
          ? activeBasePageMap?.confidence ?? null
          : getQuestionFieldValue(activeBaseQuestion, field),
      ),
    [amendmentDraft, activeBaseQuestion, activeBasePageMap],
  );
  const amendmentDirty = useMemo(
    () => !valuesEqual(meaningfulAmendmentDraft, meaningfulPersistedAmendmentDraft),
    [meaningfulAmendmentDraft, meaningfulPersistedAmendmentDraft],
  );

  useEffect(() => {
    setAmendmentDraft(persistedAmendmentDraft);
  }, [persistedAmendmentDraft]);

  useEffect(() => {
    setEditField(null);
    setReviewerReason("");
    setAmendmentSaveStatus("idle");
    setAmendmentError(null);
  }, [activeQuestionId]);

  useEffect(() => {
    reviewCardRef.current?.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [activeQuestionId]);

  const persistedReviewed = useMemo(
    () =>
      new Set(
        (activeDetail.review_state.question_reviews ?? [])
          .filter((q) => isQuestionReviewMarkedReviewed(q))
          .map((q) => q.result_id),
      ),
    [activeDetail],
  );
  const activeQuestionIsReviewed = activeQuestionId ? persistedReviewed.has(activeQuestionId) : false;

  useEffect(() => {
    if (noteScope === "question" && activeQuestionId) {
      const q = activeDetail.review_state.question_reviews.find((x) => x.result_id === activeQuestionId);
      setNoteDraft(q?.note_text ?? "");
      setNoteSaved(true);
      return;
    }
    if (noteScope === "attempt") {
      setNoteDraft(activeDetail.review_state.attempt_notes[0]?.note_text ?? "");
      setNoteSaved(true);
      return;
    }
    setNoteDraft(activeDetail.review_state.student_subject_notes[0]?.note_text ?? "");
    setNoteSaved(true);
  }, [activeDetail, noteScope, activeQuestionId]);

  async function persistReviewState(params: {
    questionReviews: AttemptDetail["review_state"]["question_reviews"];
    attemptNotes: AttemptDetail["review_state"]["attempt_notes"];
    studentSubjectNotes: AttemptDetail["review_state"]["student_subject_notes"];
    forceCompleted?: boolean;
  }) {
    const { questionReviews, attemptNotes, studentSubjectNotes, forceCompleted = false } = params;
    const hasReviewed = questionReviews.some((q) => isQuestionReviewMarkedReviewed(q));
    const questionIds = new Set(questions.map((q) => q.result_id));
    const reviewedQuestionCount = questionReviews.filter(
      (q) => isQuestionReviewMarkedReviewed(q) && questionIds.has(q.result_id),
    ).length;
    const allQuestionsReviewed = questionIds.size > 0 && reviewedQuestionCount === questionIds.size;
    const allIncorrectOrPartialHaveNotes =
      incorrectOrPartialQuestionIds.size === 0 ||
      [...incorrectOrPartialQuestionIds].every((resultId) =>
        questionReviews.some((q) => q.result_id === resultId && (q.note_text ?? "").trim().length > 0),
      );
    const hasAnyNote =
      questionReviews.some((q) => (q.note_text ?? "").trim().length > 0) ||
      attemptNotes.some((n) => (n.note_text ?? "").trim().length > 0) ||
      studentSubjectNotes.some((n) => (n.note_text ?? "").trim().length > 0);
    const shouldBeCompleted =
      forceCompleted ||
      allIncorrectOrPartialHaveNotes ||
      allQuestionsReviewed ||
      activeDetail.review_state.review_status === "completed";
    const reviewStatus = shouldBeCompleted ? "completed" : hasReviewed || hasAnyNote ? "in_progress" : "not_started";

    const res = await fetch(`/api/student/attempts/${encodeURIComponent(activeDetail.attempt.attempt_id)}/review-state`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        review_status: reviewStatus,
        question_reviews: questionReviews,
        attempt_notes: attemptNotes,
        student_subject_notes: studentSubjectNotes,
        updated_by: "buddy_console_ui",
      }),
    });
    if (!res.ok) {
      throw new Error(`Failed to persist review state: ${res.status}`);
    }
    const payload = (await res.json()) as { review_state: AttemptDetail["review_state"] };
    setActiveDetail((prev) => ({
      ...prev,
      review_state: payload.review_state,
    }));
  }

  async function saveCurrentNote() {
    const questionReviews = [...activeDetail.review_state.question_reviews];
    const attemptNotes = [...activeDetail.review_state.attempt_notes];
    const studentSubjectNotes = [...activeDetail.review_state.student_subject_notes];

    if (noteScope === "question" && activeQuestionId) {
      const idx = questionReviews.findIndex((x) => x.result_id === activeQuestionId);
      const hasSavedQuestionNote = noteDraft.trim().length > 0;
      const row = {
        result_id: activeQuestionId,
        note_text: noteDraft,
        review_status: hasSavedQuestionNote ? "reviewed" : "not_reviewed",
      };
      if (idx >= 0) {
        questionReviews[idx] = row;
      } else {
        questionReviews.push(row);
      }
    } else if (noteScope === "attempt") {
      attemptNotes.splice(0, attemptNotes.length, { note_text: noteDraft });
    } else {
      studentSubjectNotes.splice(0, studentSubjectNotes.length, { note_text: noteDraft });
    }

    await persistReviewState({
      questionReviews,
      attemptNotes,
      studentSubjectNotes,
    });
    setNoteSaved(true);
  }

  function updateDraftField(field: EditableFieldKey, value: unknown) {
    setAmendmentDraft((prev) => ({ ...prev, [field]: value }));
    setAmendmentSaveStatus("unsaved");
    setAmendmentError(null);
  }

  function revertAmendmentDraft() {
    setAmendmentDraft(persistedAmendmentDraft);
    setEditField(null);
    setReviewerReason("");
    setAmendmentSaveStatus("idle");
    setAmendmentError(null);
  }

  async function saveAmendmentDraft() {
    if (!activeQuestionId || !amendmentDirty) {
      return;
    }
    if (needsReviewerReason(meaningfulAmendmentDraftForSave) && reviewerReason.trim().length === 0) {
      setAmendmentSaveStatus("error");
      setAmendmentError("Reviewer reason is required for score-changing amendments.");
      return;
    }
    const questionFields: Record<string, unknown> = {};
    const pageMapAmendment: Record<string, unknown> = { result_id: activeQuestionId };
    let hasPageMapChange = false;

    Object.entries(meaningfulAmendmentDraftForSave).forEach(([field, value]) => {
      if (field === "attempt_page_start") {
        pageMapAmendment.attempt_page_start = value;
        hasPageMapChange = true;
      } else if (field === "page_map.confidence") {
        pageMapAmendment.confidence = value;
        hasPageMapChange = true;
      } else {
        questionFields[field] = value;
      }
    });

    const questionAmendments =
      Object.keys(questionFields).length > 0
        ? [
            {
              result_id: activeQuestionId,
              fields: questionFields,
              reviewer_reason: reviewerReason.trim() || undefined,
            },
          ]
        : [];
    const pageMapAmendments = hasPageMapChange ? [pageMapAmendment] : [];

    try {
      setAmendmentSaveStatus("saving");
      setAmendmentError(null);
      const res = await fetch(`/api/student/attempts/${encodeURIComponent(activeDetail.attempt.attempt_id)}/amendments`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question_amendments: questionAmendments,
          question_page_map_amendments: pageMapAmendments,
          updated_by: "buddy_console_ui",
        }),
      });
      const payload = await res.json();
      if (!res.ok) {
        const firstError = payload?.detail?.errors?.[0]?.message;
        throw new Error(firstError || `Failed to save amendment: ${res.status}`);
      }
      setActiveDetail({
        ...activeDetail,
        marking_result: payload.marking_result,
        marking_result_base: payload.marking_result_base,
        marking_result_resolved: payload.marking_result_resolved,
        amendment_state: payload.amendment_state,
      });
      setAmendmentSaveStatus("saved");
      setEditField(null);
      setReviewerReason("");
    } catch (e) {
      setAmendmentSaveStatus("error");
      setAmendmentError(e instanceof Error ? e.message : "Failed to save amendment");
    }
  }

  if (!activeDetail.marking_result) {
    return (
      <main className="shell">
        <header className="top-panel">
          <strong>{activeDetail.attempt.title}</strong>
          <button onClick={onBack}>Back to My Work</button>
        </header>
        <section className="middle-grid">
          <article className="right-panel" style={{ gridColumn: "1 / -1", padding: "12px" }}>
            This attempt has no canonical marking artifact yet.
          </article>
        </section>
      </main>
    );
  }

  const activeIndex = Math.max(
    0,
    questions.findIndex((q) => q.result_id === activeQuestionId),
  );
  const imagePool = viewerImagePool(activeDetail.viewer, viewerMode);
  const templateImagesAvailable = (activeDetail.viewer.template_images ?? []).length > 0;
  const activeImageIndex = Math.max(
    0,
    imagePool.findIndex((img) => img.url === activeImageUrl),
  );
  const incorrectQuestionCount = questions.filter(isIncorrectQuestion).length;
  const savedQuestionChanged = activeQuestionId
    ? questionHasMeaningfulSavedAmendment(activeDetail.amendment_state, activeQuestionId, activeBaseQuestion, activeBasePageMap)
    : false;

  function resolvedFieldValue(field: EditableFieldKey): unknown {
    if (Object.prototype.hasOwnProperty.call(amendmentDraft, field)) {
      return amendmentDraft[field];
    }
    if (field === "page_map.confidence") {
      return activePageMap?.confidence ?? null;
    }
    return getQuestionFieldValue(activeQuestion, field);
  }

  function baseFieldValue(field: EditableFieldKey): unknown {
    if (field === "page_map.confidence") {
      return activeBasePageMap?.confidence ?? null;
    }
    return getQuestionFieldValue(activeBaseQuestion, field);
  }

  function renderEditor(field: EditableFieldKey, value: unknown) {
    if (field === "outcome") {
      return (
        <select value={String(value ?? "")} onChange={(e) => updateDraftField(field, e.target.value)}>
          <option value="correct">correct</option>
          <option value="partial">partial</option>
          <option value="wrong">wrong</option>
          <option value="disqualified">disqualified</option>
        </select>
      );
    }
    if (field === "page_map.confidence") {
      return (
        <select value={String(value ?? "medium")} onChange={(e) => updateDraftField(field, e.target.value)}>
          <option value="high">high</option>
          <option value="medium">medium</option>
          <option value="low">low</option>
        </select>
      );
    }
    if (field === "earned_marks" || field === "max_marks" || field === "attempt_page_start") {
      return (
        <input
          type="number"
          min={0}
          step={field === "attempt_page_start" ? 1 : 0.5}
          value={value === null || value === undefined ? "" : String(value)}
          onChange={(e) => updateDraftField(field, coerceDraftValue(field, e.target.value))}
        />
      );
    }
    if (field === "skill_tags") {
      const currentTags = normalizeSkillTagsArray(value);
      const currentValue = JSON.stringify(currentTags);
      const hasOptions = scienceSkillTagOptions.length > 0;
      if (isScienceSubject && hasOptions) {
        const needsCurrentOption = currentTags.length > 0 && !scienceSkillTagOptions.some((option) => option.value === currentValue);
        return (
          <select
            value={currentValue}
            onChange={(e) => {
              const parsed = JSON.parse(e.target.value) as unknown;
              updateDraftField(field, Array.isArray(parsed) ? parsed : []);
            }}
          >
            {needsCurrentOption ? <option value={currentValue}>{skillTagsLabel(currentTags)}</option> : null}
            {scienceSkillTagOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        );
      }
      return (
        <input
          type="text"
          value={currentTags.join(", ")}
          onChange={(e) => updateDraftField(field, coerceDraftValue(field, e.target.value))}
        />
      );
    }
    return (
      <textarea
        value={value === null || value === undefined ? "" : String(value)}
        onChange={(e) => updateDraftField(field, coerceDraftValue(field, e.target.value))}
      />
    );
  }

  function renderAmendmentField(label: string, field: EditableFieldKey) {
    const resolvedValue = resolvedFieldValue(field);
    const baseValue = baseFieldValue(field);
    const isEditing = editField === field;
    const hasSavedOverride =
      Object.prototype.hasOwnProperty.call(persistedAmendmentDraft, field) &&
      fieldMeaningfullyChanged(field, persistedAmendmentDraft[field], baseValue);
    const hasDraftOverride =
      Object.prototype.hasOwnProperty.call(amendmentDraft, field) && fieldMeaningfullyChanged(field, amendmentDraft[field], baseValue);
    const isWide = WIDE_AMENDMENT_FIELDS.has(field);
    const isMetric = METRIC_AMENDMENT_FIELDS.has(field);
    const fieldClassName =
      `amend-field${isWide ? " wide" : ""}${isMetric ? " metric" : ""}${hasSavedOverride || hasDraftOverride ? " changed" : ""}`;
    const resolvedText = formatFieldValue(resolvedValue);
    const baseText = formatFieldValue(baseValue);
    const renderResolvedValue =
      MARKDOWN_AMENDMENT_FIELDS.has(field) && resolvedText !== "-" ? renderMarkdownText(resolvedText) : resolvedText;
    return (
      <div
        className={fieldClassName}
        onDoubleClick={() => setEditField(field)}
      >
        <div className="amend-label">
          <span>{label}</span>
          {hasSavedOverride || hasDraftOverride ? <span className="pill changed-pill">Changed</span> : null}
        </div>
        {isEditing ? (
          <div className="amend-editor">
            {renderEditor(field, resolvedValue)}
            <small>AI: {formatFieldValue(baseValue)}</small>
          </div>
        ) : (
          <div className="amend-read">
            <div className="amend-value">{renderResolvedValue}</div>
            {hasSavedOverride || hasDraftOverride ? <small>AI: {baseText}</small> : null}
          </div>
        )}
      </div>
    );
  }

  return (
    <main className="shell">
      <header className="top-panel">
        <div className="attempt-meta">
          <button onClick={onBack}>Back</button>
          <strong className="attempt-title">{activeDetail.attempt.title}</strong>
          <span className="attempt-inline-meta">
            {activeDetail.attempt.book_label ?? "No book label"} |{" "}
            {activeDetail.marking_result.summary.earned_marks}/{activeDetail.marking_result.summary.total_marks} (
            {formatPct(activeDetail.marking_result.summary.percentage)})
          </span>
          {activeDetail.marking_result.context.is_partial ? <span className="pill warning">Partial marking</span> : null}
        </div>
        <div className="question-nav">
          <button
            onClick={() => activeIndex > 0 && setActiveQuestionId(questions[activeIndex - 1].result_id)}
            disabled={activeIndex === 0}
          >
            Previous
          </button>
          <span>
            {activeQuestionId || "-"} ({activeIndex + 1}/{questions.length})
          </span>
          <button
            onClick={() =>
              activeIndex < questions.length - 1 && setActiveQuestionId(questions[activeIndex + 1].result_id)
            }
            disabled={activeIndex >= questions.length - 1}
          >
            Next
          </button>
          <button
            type="button"
            className="top-complete-btn"
            disabled={activeDetail.review_state.review_status === "completed"}
            onClick={() =>
              void persistReviewState({
                questionReviews: [...activeDetail.review_state.question_reviews],
                attemptNotes: [...activeDetail.review_state.attempt_notes],
                studentSubjectNotes: [...activeDetail.review_state.student_subject_notes],
                forceCompleted: true,
              })
            }
          >
            Review completed
          </button>
        </div>
      </header>

      <section className="middle-grid">
        <aside className="left-panel">
          <div className="panel-head evidence-head">
            <div className="evidence-toolbar">
              <span className="evidence-title">Evidence</span>
              <div className="toggle">
                <button className={viewerMode === "attempt" ? "active" : ""} onClick={() => setViewerMode("attempt")}>
                  Attempt
                </button>
                <button className={viewerMode === "answer" ? "active" : ""} onClick={() => setViewerMode("answer")}>
                  Answer
                </button>
                {templateImagesAvailable ? (
                  <button className={viewerMode === "template" ? "active" : ""} onClick={() => setViewerMode("template")}>
                    Template
                  </button>
                ) : null}
              </div>
              <span className="toolbar-sep" aria-hidden="true">
                |
              </span>
              <div className="zoom-widget">
                <button onClick={() => setViewerZoomPct((z) => Math.max(20, z - 10))}>-</button>
                <span>{viewerZoomPct}%</span>
                <button onClick={() => setViewerZoomPct((z) => Math.min(150, z + 10))}>+</button>
                <button onClick={() => setViewerZoomPct(50)}>Reset</button>
                <input
                  type="range"
                  min={20}
                  max={150}
                  step={10}
                  value={viewerZoomPct}
                  onChange={(e) => setViewerZoomPct(Number(e.target.value))}
                  aria-label="Evidence zoom"
                />
              </div>
            </div>
          </div>
          <div className="viewer">
            {activeImageUrl ? (
              <img
                className="fit-width"
                style={{
                  width: "100%",
                  height: "auto",
                  transform: `scale(${viewerZoomPct / 100})`,
                  transformOrigin: "top center",
                }}
                src={activeImageUrl}
                alt={`${viewerMode === "template" ? "Template" : viewerMode === "answer" ? "Answer" : "Attempt"} evidence page`}
              />
            ) : (
              <p>No image available.</p>
            )}
          </div>
          <div className="thumbs">
            <button
              type="button"
              disabled={imagePool.length === 0 || activeImageIndex <= 0}
              onClick={() => {
                if (activeImageIndex > 0) {
                  setActiveImageUrl(imagePool[activeImageIndex - 1].url);
                }
              }}
            >
              Previous
            </button>
            <select
              value={activeImageUrl ?? ""}
              onChange={(e) => setActiveImageUrl(e.target.value)}
              disabled={imagePool.length === 0}
              aria-label="Evidence page"
            >
              {imagePool.map((img) => (
                <option key={`${viewerMode}-${img.name}`} value={img.url}>
                  p{img.page_num}
                </option>
              ))}
            </select>
            <button
              type="button"
              disabled={imagePool.length === 0 || activeImageIndex >= imagePool.length - 1}
              onClick={() => {
                if (activeImageIndex < imagePool.length - 1) {
                  setActiveImageUrl(imagePool[activeImageIndex + 1].url);
                }
              }}
            >
              Next
            </button>
            <span className="thumbs-meta">
              {imagePool.length === 0 ? "No pages" : `${activeImageIndex + 1}/${imagePool.length}`}
            </span>
          </div>
        </aside>

        <section className="right-panel">
          <div className="panel-head">
            <span>Review</span>
            <select value={activeQuestionId} onChange={(e) => setActiveQuestionId(e.target.value)}>
              {questions.map((q) => (
                <option key={q.result_id} value={q.result_id}>
                  {questionStatusEmoji(q)} {q.result_id}
                  {persistedReviewed.has(q.result_id) ? " *" : ""}
                  {questionHasMeaningfulSavedAmendment(
                    activeDetail.amendment_state,
                    q.result_id,
                    baseQuestions.find((baseQ) => baseQ.result_id === q.result_id) ?? null,
                    activeDetail.marking_result_base?.context.question_page_map.find((entry) => entry.result_id === q.result_id) ?? null,
                  )
                    ? " ✎"
                    : ""}
                </option>
              ))}
            </select>
          </div>

          {activeQuestion ? (
            <article ref={reviewCardRef} className="card">
              <div className="review-card-head">
                <h2>{activeQuestion.result_id}</h2>
                <div className="review-head-pills">
                  {activeQuestionIsReviewed ? <span className="pill reviewed-pill">Reviewed</span> : null}
                  {savedQuestionChanged ? <span className="pill changed-pill">Amended</span> : null}
                </div>
              </div>
              <div className="score-strip">
                <strong>{activeQuestion.outcome}</strong>
                <span>
                  {activeQuestion.earned_marks}/{activeQuestion.max_marks}
                </span>
                <span>Page {activeQuestion.attempt_page_start ?? "-"}</span>
              </div>
              <div className="amend-grid">
                {renderAmendmentField("Outcome", "outcome")}
                {renderAmendmentField("Earned marks", "earned_marks")}
                {renderAmendmentField("Max marks", "max_marks")}
                {renderAmendmentField("Student answer", "student_answer")}
                {renderAmendmentField("Correct answer", "correct_answer")}
                {renderAmendmentField("Diagnosis type", "diagnosis.mistake_type")}
                {renderAmendmentField("Diagnosis reasoning", "diagnosis.reasoning")}
                {renderAmendmentField("Skill tags", "skill_tags")}
                {renderAmendmentField("Human note", "human_note")}
                {renderAmendmentField("Mapped page", "attempt_page_start")}
                {renderAmendmentField("Map confidence", "page_map.confidence")}
              </div>
              {amendmentDirty || amendmentSaveStatus === "saving" || amendmentSaveStatus === "saved" || amendmentError ? (
                <div className="amend-save-panel">
                  {needsReviewerReason(amendmentDraft) ? (
                    <label>
                      Reviewer reason
                      <textarea
                        value={reviewerReason}
                        onChange={(e) => setReviewerReason(e.target.value)}
                        placeholder="Why is this score or outcome changing?"
                      />
                    </label>
                  ) : null}
                  <div className="amend-actions">
                    <span className={`save-status ${amendmentSaveStatus}`}>{amendmentSaveStatus}</span>
                    <button type="button" disabled={!amendmentDirty || amendmentSaveStatus === "saving"} onClick={() => void saveAmendmentDraft()}>
                      Save amendment
                    </button>
                    <button type="button" disabled={!amendmentDirty || amendmentSaveStatus === "saving"} onClick={revertAmendmentDraft}>
                      Revert amendment
                    </button>
                  </div>
                  {amendmentError ? <p className="error-text">{amendmentError}</p> : null}
                </div>
              ) : null}
              {questionSelectionRawText ? <p>Marked scope: {questionSelectionRawText}</p> : null}
            </article>
          ) : null}

          <article className={`notes ${notesExpanded ? "expanded" : "collapsed"}`}>
            <div className="notes-head">
              <div className="notes-title-row">
                <strong>Review Notes</strong>
                {!noteSaved ? <span className="notes-unsaved-pill">Unsaved</span> : null}
              </div>
              <button
                type="button"
                className="notes-toggle"
                aria-expanded={notesExpanded}
                onClick={() => setNotesExpanded((prev) => !prev)}
              >
                {notesExpanded ? "Hide notes" : "Add notes"}
              </button>
            </div>
            {notesExpanded ? (
              <>
                <div className="scope-tabs">
                  <button className={noteScope === "question" ? "active" : ""} onClick={() => setNoteScope("question")}>
                    Question
                  </button>
                  <button className={noteScope === "attempt" ? "active" : ""} onClick={() => setNoteScope("attempt")}>
                    Attempt
                  </button>
                  <button
                    className={noteScope === "student_subject" ? "active" : ""}
                    onClick={() => setNoteScope("student_subject")}
                  >
                    Student+Subject
                  </button>
                </div>
                <textarea
                  value={noteDraft}
                  onChange={(e) => {
                    setNoteDraft(e.target.value);
                    setNoteSaved(false);
                  }}
                  placeholder={`Write ${noteScope} note...`}
                />
                <button onClick={() => void saveCurrentNote()}>Save Note</button>
              </>
            ) : null}
          </article>
        </section>
      </section>

      <footer className="bottom-panel">
        <div className="bottom-group bottom-actions">
          <button
            disabled={incorrectQuestionCount === 0}
            onClick={() => {
              if (questions.length === 0) {
                return;
              }
              for (let offset = 1; offset <= questions.length; offset += 1) {
                const idx = (activeIndex + offset) % questions.length;
                const candidate = questions[idx];
                if (isIncorrectQuestion(candidate)) {
                  setActiveQuestionId(candidate.result_id);
                  return;
                }
              }
            }}
          >
            Next incorrect
          </button>
          <button
            onClick={() => {
              setNoteScope("student_subject");
              setNotesExpanded(true);
            }}
          >
            Student-subject note
          </button>
        </div>
      </footer>
    </main>
  );
}

export default function App() {
  const [screen, setScreen] = useState<Screen>("picker");
  const [students, setStudents] = useState<StudentRow[]>([]);
  const [selectedStudentId, setSelectedStudentId] = useState<string>("");
  const [attempts, setAttempts] = useState<AttemptListItem[]>([]);
  const [detail, setDetail] = useState<AttemptDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deepLinkError, setDeepLinkError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [workspaceInitialResultId, setWorkspaceInitialResultId] = useState<string | null>(null);

  const [subjectFilter, setSubjectFilter] = useState<string>("all");
  const [collectionFilter, setCollectionFilter] = useState<"all" | "exam" | "book">("all");
  const [markingFilter, setMarkingFilter] = useState<"all" | "marked" | "not_marked">("all");
  const [reviewFilter, setReviewFilter] = useState<"all" | "not_started" | "in_progress" | "completed">("all");

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        setLoading(true);
        const deepLink = parseDeepLinkParams(window.location.search);
        const payload = await fetchJson<{ students: StudentRow[] }>("/api/students");
        if (cancelled) {
          return;
        }

        setStudents(payload.students);
        const stored = localStorage.getItem(STORAGE_KEY_STUDENT) ?? "";
        const chosen = resolveInitialStudentId(payload.students, deepLink.studentId, stored);
        if (chosen) {
          setSelectedStudentId(chosen);
          localStorage.setItem(STORAGE_KEY_STUDENT, chosen);
        }

        if (deepLink.attemptId) {
          try {
            const attemptDetail = await fetchAttemptDetail(deepLink.attemptId);
            if (cancelled) {
              return;
            }

            const attemptStudentId = attemptDetail.attempt.student_id;
            setSelectedStudentId(attemptStudentId);
            localStorage.setItem(STORAGE_KEY_STUDENT, attemptStudentId);

            if (attemptDetail.marking_status !== "marked") {
              setDeepLinkError("Attempt is not marked yet");
              setScreen("my_work");
              replaceReviewWorkspaceUrl({ studentId: attemptStudentId });
              return;
            }

            const initialResultId = resolveDeepLinkQuestionId(
              attemptDetail.marking_result?.question_results ?? [],
              deepLink.resultId,
              deepLink.questionIndex,
            );
            setWorkspaceInitialResultId(initialResultId);
            setDetail(attemptDetail);
            setScreen("workspace");
            replaceReviewWorkspaceUrl({
              attemptId: deepLink.attemptId,
              studentId: attemptStudentId,
              resultId: initialResultId,
            });
            return;
          } catch (e) {
            if (cancelled) {
              return;
            }
            setDeepLinkError(e instanceof Error ? e.message : "Attempt not found");
            replaceReviewWorkspaceUrl({ studentId: chosen || undefined });
            setScreen(chosen ? "my_work" : "picker");
            return;
          }
        }

        if (chosen) {
          setWorkspaceInitialResultId(null);
          replaceReviewWorkspaceUrl({ studentId: chosen });
          setScreen("my_work");
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Unknown error");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void bootstrap();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    async function loadAttempts() {
      if (!selectedStudentId) {
        return;
      }
      try {
        setLoading(true);
        const payload = await fetchJson<{ items: AttemptListItem[] }>(
          `/api/student/attempts?student_id=${encodeURIComponent(selectedStudentId)}`,
        );
        setAttempts(payload.items);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    }
    if (screen === "my_work") {
      void loadAttempts();
    }
  }, [selectedStudentId, screen]);

  const filteredAttempts = useMemo(() => {
    return attempts.filter((item) => {
      if (subjectFilter !== "all" && (item.subject_context ?? "unknown") !== subjectFilter) {
        return false;
      }
      if (collectionFilter !== "all" && item.collection_kind !== collectionFilter) {
        return false;
      }
      if (markingFilter !== "all" && item.marking_status !== markingFilter) {
        return false;
      }
      if (reviewFilter !== "all" && item.review_status !== reviewFilter) {
        return false;
      }
      return true;
    });
  }, [attempts, subjectFilter, collectionFilter, markingFilter, reviewFilter]);

  async function openAttempt(attemptId: string) {
    try {
      setLoading(true);
      setDeepLinkError(null);
      const payload = await fetchAttemptDetail(attemptId);
      setWorkspaceInitialResultId(null);
      setDetail(payload);
      setScreen("workspace");
      replaceReviewWorkspaceUrl({
        attemptId,
        studentId: payload.attempt.student_id,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  if (error) {
    return <main className="shell">Error: {error}</main>;
  }

  if (loading && students.length === 0) {
    return <main className="shell">Loading...</main>;
  }

  if (screen === "picker") {
    return (
      <main className="shell">
        <section className="top-panel" style={{ flexDirection: "column", alignItems: "flex-start" }}>
          <h1 style={{ margin: 0 }}>Student Picker</h1>
          <p style={{ margin: 0 }}>Select the active student for Review Workspace.</p>
          <div style={{ display: "flex", gap: "8px" }}>
            <select
              value={selectedStudentId}
              onChange={(e) => setSelectedStudentId(e.target.value)}
            >
              <option value="">Select student</option>
              {students.map((student) => (
                <option key={student.student_id} value={student.student_id}>
                  {student.display_name}
                </option>
              ))}
            </select>
            <button
              disabled={!selectedStudentId}
              onClick={() => {
                localStorage.setItem(STORAGE_KEY_STUDENT, selectedStudentId);
                replaceReviewWorkspaceUrl({ studentId: selectedStudentId });
                setScreen("my_work");
              }}
            >
              Continue
            </button>
          </div>
        </section>
      </main>
    );
  }

  if (screen === "workspace" && detail) {
    return (
      <WorkspaceView
        detail={detail}
        initialResultId={workspaceInitialResultId}
        onBack={() => {
          setDetail(null);
          setWorkspaceInitialResultId(null);
          setScreen("my_work");
          replaceReviewWorkspaceUrl({ studentId: detail.attempt.student_id });
        }}
      />
    );
  }

  const uniqueSubjects = Array.from(new Set(attempts.map((a) => a.subject_context ?? "unknown"))).sort();

  return (
    <main className="shell">
      <header className="top-panel">
        <div className="attempt-meta">
          <strong>My Work</strong>
          <span>Student: {students.find((s) => s.student_id === selectedStudentId)?.display_name ?? selectedStudentId}</span>
          <button
            onClick={() => {
              replaceReviewWorkspaceUrl({ studentId: selectedStudentId || undefined });
              setScreen("picker");
            }}
          >
            Change student
          </button>
        </div>
        <div className="question-nav">
          <select value={subjectFilter} onChange={(e) => setSubjectFilter(e.target.value)}>
            <option value="all">All subjects</option>
            {uniqueSubjects.map((subject) => (
              <option key={subject} value={subject}>
                {subject}
              </option>
            ))}
          </select>
          <select value={collectionFilter} onChange={(e) => setCollectionFilter(e.target.value as "all" | "exam" | "book")}>
            <option value="all">All kinds</option>
            <option value="exam">Exam</option>
            <option value="book">Book</option>
          </select>
          <select value={markingFilter} onChange={(e) => setMarkingFilter(e.target.value as "all" | "marked" | "not_marked")}>
            <option value="all">All marking</option>
            <option value="marked">Marked</option>
            <option value="not_marked">Not marked</option>
          </select>
          <select
            value={reviewFilter}
            onChange={(e) => setReviewFilter(e.target.value as "all" | "not_started" | "in_progress" | "completed")}
          >
            <option value="all">All review</option>
            <option value="not_started">Not started</option>
            <option value="in_progress">In progress</option>
            <option value="completed">Completed</option>
          </select>
        </div>
      </header>

      <section className="middle-grid" style={{ gridTemplateColumns: "1fr" }}>
        <section className="right-panel" style={{ display: "block", overflow: "auto", padding: "10px" }}>
          {deepLinkError ? (
            <p style={{ color: "crimson" }}>
              {deepLinkError}{" "}
              <button type="button" onClick={() => setDeepLinkError(null)}>
                Dismiss
              </button>
            </p>
          ) : null}
          {loading ? <p>Loading attempts...</p> : null}
          {!loading && filteredAttempts.length === 0 ? <p>No attempts found for current filters.</p> : null}
          {filteredAttempts.map((item) => (
            <article
              key={item.attempt_id}
              className={`card attempt-list-card${
                item.review_status === "completed"
                  ? " review-completed"
                  : item.review_status === "in_progress"
                    ? " review-in-progress"
                    : ""
              }`}
            >
              <h2 style={{ margin: "0 0 6px 0" }}>{item.title}</h2>
              <p>
                {item.subject_context ?? "unknown"} | {item.collection_kind} | {item.grade_bucket ?? "-"}
              </p>
              <p>
                Marking: <strong>{item.marking_status}</strong> | Review: <strong>{item.review_status}</strong>
              </p>
              <p>
                Score: {item.score ? `${item.score.earned_marks}/${item.score.total_marks} (${formatPct(item.score.percentage)})` : "-"}
              </p>
              <p>{item.book_label ?? "No book label"}</p>
              <button disabled={item.marking_status !== "marked"} onClick={() => void openAttempt(item.attempt_id)}>
                Open Review Workspace
              </button>
            </article>
          ))}
        </section>
      </section>
    </main>
  );
}
