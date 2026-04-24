import { useEffect, useMemo, useState } from "react";

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
  feedback: string | null;
  skill_tags: string[];
  diagnosis: {
    mistake_type: string | null;
    reasoning: string | null;
  };
  attempt_page_start: number | null;
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
  marking_result: {
    schema_version: string;
    summary: {
      earned_marks: number;
      total_marks: number;
      percentage: number;
      overall_assessment: string;
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
  } | null;
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
  };
};

type ViewerMode = "attempt" | "answer";
type ViewerFitMode = "fit_height" | "fit_width";
type NoteScope = "question" | "attempt" | "student_subject";

type Screen = "picker" | "my_work" | "workspace";

const STORAGE_KEY_STUDENT = "review_workspace.student_id";

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
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

function WorkspaceView({ detail, onBack }: { detail: AttemptDetail; onBack: () => void }) {
  const [viewerMode, setViewerMode] = useState<ViewerMode>("attempt");
  const [viewerFitMode, setViewerFitMode] = useState<ViewerFitMode>("fit_width");
  const [viewerZoomPct, setViewerZoomPct] = useState<number>(100);
  const [activeQuestionId, setActiveQuestionId] = useState<string>("");
  const [activeImageUrl, setActiveImageUrl] = useState<string | null>(null);
  const [noteScope, setNoteScope] = useState<NoteScope>("question");
  const [noteDraft, setNoteDraft] = useState<string>("");
  const [noteSaved, setNoteSaved] = useState<boolean>(true);
  const [reviewed, setReviewed] = useState<Set<string>>(new Set());
  const [activeDetail, setActiveDetail] = useState<AttemptDetail>(detail);

  useEffect(() => {
    setActiveDetail(detail);
    setViewerMode("attempt");
    setViewerFitMode("fit_width");
    setViewerZoomPct(100);
    setActiveQuestionId("");
    setActiveImageUrl(null);
    setNoteScope("question");
    setNoteDraft("");
    setNoteSaved(true);
    setReviewed(new Set());
  }, [detail]);

  const questions = activeDetail.marking_result?.question_results ?? [];
  const questionSelectionRawText = activeDetail.marking_result?.context?.question_selection?.raw_text ?? null;

  useEffect(() => {
    if (questions.length === 0) {
      return;
    }
    if (!activeQuestionId) {
      setActiveQuestionId(questions[0].result_id);
      return;
    }
    const selected = questions.find((q) => q.result_id === activeQuestionId);
    const pageStart = selected?.attempt_page_start;
    const imagePool = viewerMode === "attempt" ? activeDetail.viewer.attempt_images : activeDetail.viewer.answer_images;
    if (imagePool.length === 0) {
      setActiveImageUrl(null);
      return;
    }
    const exact = pageStart != null ? imagePool.find((img) => img.page_num === pageStart) : undefined;
    setActiveImageUrl((exact ?? imagePool[0]).url);
  }, [questions, activeQuestionId, viewerMode, activeDetail.viewer.attempt_images, activeDetail.viewer.answer_images]);

  const activeQuestion = useMemo(
    () => questions.find((q) => q.result_id === activeQuestionId) ?? null,
    [questions, activeQuestionId],
  );

  const persistedReviewed = useMemo(
    () =>
      new Set(
        (activeDetail.review_state.question_reviews ?? [])
          .filter((q) => q.review_status === "reviewed")
          .map((q) => q.result_id),
      ),
    [activeDetail],
  );

  const effectiveReviewed = useMemo(() => {
    const merged = new Set(persistedReviewed);
    reviewed.forEach((id) => merged.add(id));
    return merged;
  }, [persistedReviewed, reviewed]);

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
  }) {
    const { questionReviews, attemptNotes, studentSubjectNotes } = params;
    const hasReviewed = questionReviews.some((q) => q.review_status === "reviewed");
    const hasAnyNote =
      questionReviews.some((q) => (q.note_text ?? "").trim().length > 0) ||
      attemptNotes.some((n) => (n.note_text ?? "").trim().length > 0) ||
      studentSubjectNotes.some((n) => (n.note_text ?? "").trim().length > 0);
    const reviewStatus = hasReviewed || hasAnyNote ? "in_progress" : "not_started";

    const res = await fetch(`/api/student/attempts/${encodeURIComponent(activeDetail.attempt.attempt_id)}/review-state`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        review_status: reviewStatus,
        question_reviews: questionReviews,
        attempt_notes: attemptNotes,
        student_subject_notes: studentSubjectNotes,
        updated_by: "review_workspace_ui",
      }),
    });
    if (!res.ok) {
      throw new Error(`Failed to persist review state: ${res.status}`);
    }
    const payload = (await res.json()) as { review_state: AttemptDetail["review_state"] };
    setActiveDetail({
      ...activeDetail,
      review_state: payload.review_state,
    });
  }

  async function saveCurrentNote() {
    const questionReviews = [...activeDetail.review_state.question_reviews];
    const attemptNotes = [...activeDetail.review_state.attempt_notes];
    const studentSubjectNotes = [...activeDetail.review_state.student_subject_notes];

    if (noteScope === "question" && activeQuestionId) {
      const idx = questionReviews.findIndex((x) => x.result_id === activeQuestionId);
      const existingStatus = idx >= 0 ? questionReviews[idx].review_status : undefined;
      const row = {
        result_id: activeQuestionId,
        note_text: noteDraft,
        review_status: existingStatus ?? "in_progress",
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

  async function markCurrentQuestionReviewed() {
    if (!activeQuestionId) {
      return;
    }
    const questionReviews = [...activeDetail.review_state.question_reviews];
    const idx = questionReviews.findIndex((x) => x.result_id === activeQuestionId);
    if (idx >= 0) {
      questionReviews[idx] = { ...questionReviews[idx], review_status: "reviewed" };
    } else {
      questionReviews.push({ result_id: activeQuestionId, review_status: "reviewed", note_text: "" });
    }
    await persistReviewState({
      questionReviews,
      attemptNotes: [...activeDetail.review_state.attempt_notes],
      studentSubjectNotes: [...activeDetail.review_state.student_subject_notes],
    });
    setReviewed((prev) => {
      const next = new Set(prev);
      next.add(activeQuestionId);
      return next;
    });
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
  const imagePool = viewerMode === "attempt" ? activeDetail.viewer.attempt_images : activeDetail.viewer.answer_images;
  const incorrectQuestionCount = questions.filter(isIncorrectQuestion).length;

  return (
    <main className="shell">
      <header className="top-panel">
        <div className="attempt-meta">
          <button onClick={onBack}>Back</button>
          <strong>{activeDetail.attempt.title}</strong>
          <span>{activeDetail.attempt.student_id}</span>
          <span>{activeDetail.attempt.subject_context}</span>
          <span>{activeDetail.attempt.book_label ?? "No book label"}</span>
          <span>
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
          <button type="button" onClick={() => setNoteScope("attempt")}>Attempt note</button>
        </div>
      </header>

      <section className="middle-grid">
        <aside className="left-panel">
          <div className="panel-head">
            <span>Evidence</span>
            <div className="toggle">
              <button className={viewerMode === "attempt" ? "active" : ""} onClick={() => setViewerMode("attempt")}>
                Attempt
              </button>
              <button className={viewerMode === "answer" ? "active" : ""} onClick={() => setViewerMode("answer")}>
                Answer
              </button>
            </div>
            <div className="toggle">
              <button
                className={viewerFitMode === "fit_height" ? "active" : ""}
                onClick={() => setViewerFitMode("fit_height")}
              >
                Fit height
              </button>
              <button
                className={viewerFitMode === "fit_width" ? "active" : ""}
                onClick={() => setViewerFitMode("fit_width")}
              >
                Fit width
              </button>
            </div>
            <div className="zoom-widget">
              <button onClick={() => setViewerZoomPct((z) => Math.max(50, z - 10))}>-</button>
              <span>{viewerZoomPct}%</span>
              <button onClick={() => setViewerZoomPct((z) => Math.min(300, z + 10))}>+</button>
              <button onClick={() => setViewerZoomPct(100)}>Reset</button>
              <input
                type="range"
                min={50}
                max={300}
                step={10}
                value={viewerZoomPct}
                onChange={(e) => setViewerZoomPct(Number(e.target.value))}
                aria-label="Evidence zoom"
              />
            </div>
          </div>
          <div className="viewer">
            {activeImageUrl ? (
              <img
                className={viewerFitMode === "fit_height" ? "fit-height" : "fit-width"}
                style={
                  viewerFitMode === "fit_height"
                    ? { height: `${viewerZoomPct}%` }
                    : { width: `${viewerZoomPct}%` }
                }
                src={activeImageUrl}
                alt="Attempt evidence page"
              />
            ) : (
              <p>No image available.</p>
            )}
          </div>
          <div className="thumbs">
            {imagePool.map((img) => (
              <button
                key={`${viewerMode}-${img.name}`}
                className={img.url === activeImageUrl ? "thumb active" : "thumb"}
                onClick={() => setActiveImageUrl(img.url)}
              >
                p{img.page_num}
              </button>
            ))}
          </div>
        </aside>

        <section className="right-panel">
          <div className="panel-head">
            <span>Review</span>
            <select value={activeQuestionId} onChange={(e) => setActiveQuestionId(e.target.value)}>
              {questions.map((q) => (
                <option key={q.result_id} value={q.result_id}>
                  {questionStatusEmoji(q)} {q.result_id}
                </option>
              ))}
            </select>
          </div>

          {activeQuestion ? (
            <article className="card">
              <h2>{activeQuestion.result_id}</h2>
              <p>
                Outcome: <strong>{activeQuestion.outcome}</strong> ({activeQuestion.earned_marks}/
                {activeQuestion.max_marks})
              </p>
              <p>Student answer: {activeQuestion.student_answer ?? "-"}</p>
              <p>Correct answer: {activeQuestion.correct_answer ?? "-"}</p>
              <p>Feedback: {activeQuestion.feedback ?? "-"}</p>
              <p>Diagnosis type: {activeQuestion.diagnosis.mistake_type ?? "-"}</p>
              <p>Diagnosis reasoning: {activeQuestion.diagnosis.reasoning ?? "-"}</p>
              <p>Mapped page: {activeQuestion.attempt_page_start ?? "-"}</p>
              <p>Skill tags: {activeQuestion.skill_tags.join(" | ") || "-"}</p>
              {questionSelectionRawText ? <p>Marked scope: {questionSelectionRawText}</p> : null}
            </article>
          ) : null}

          <article className="notes">
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
          </article>
        </section>
      </section>

      <footer className="bottom-panel">
        <span>Viewing: {viewerMode}</span>
        <span>Fit: {viewerFitMode === "fit_height" ? "Height" : "Width"}</span>
        <span>Zoom: {viewerZoomPct}%</span>
        <span>Active: {activeQuestionId || "-"}</span>
        <span>Note: {noteSaved ? "Saved" : "Unsaved"}</span>
        <span>Question: {effectiveReviewed.has(activeQuestionId) ? "Reviewed" : "Not reviewed"}</span>
        <button onClick={() => void markCurrentQuestionReviewed()}>Mark reviewed</button>
        <button
          onClick={() => {
            if (questions.length === 0) {
              return;
            }
            for (let offset = 1; offset <= questions.length; offset += 1) {
              const idx = (activeIndex + offset) % questions.length;
              const candidate = questions[idx];
              if (!effectiveReviewed.has(candidate.result_id)) {
                setActiveQuestionId(candidate.result_id);
                return;
              }
            }
          }}
        >
          Next unreviewed
        </button>
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
        <button onClick={() => setNoteScope("student_subject")}>Student-subject note</button>
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
  const [loading, setLoading] = useState<boolean>(false);

  const [subjectFilter, setSubjectFilter] = useState<string>("all");
  const [collectionFilter, setCollectionFilter] = useState<"all" | "exam" | "book">("all");
  const [markingFilter, setMarkingFilter] = useState<"all" | "marked" | "not_marked">("all");
  const [reviewFilter, setReviewFilter] = useState<"all" | "not_started" | "in_progress" | "completed">("all");

  useEffect(() => {
    async function loadStudents() {
      try {
        setLoading(true);
        const payload = await fetchJson<{ students: StudentRow[] }>("/api/students");
        setStudents(payload.students);

        const stored = localStorage.getItem(STORAGE_KEY_STUDENT) ?? "";
        const chosen = payload.students.find((s) => s.student_id === stored)
          ? stored
          : (payload.students[0]?.student_id ?? "");
        setSelectedStudentId(chosen);
        if (chosen) {
          setScreen("my_work");
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    }
    loadStudents();
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
      const payload = await fetchJson<AttemptDetail>(`/api/student/attempts/${encodeURIComponent(attemptId)}`);
      setDetail(payload);
      setScreen("workspace");
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
        onBack={() => {
          setScreen("my_work");
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
          {loading ? <p>Loading attempts...</p> : null}
          {!loading && filteredAttempts.length === 0 ? <p>No attempts found for current filters.</p> : null}
          {filteredAttempts.map((item) => (
            <article key={item.attempt_id} className="card" style={{ border: "1px solid var(--line)", borderRadius: "10px", marginBottom: "10px" }}>
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
