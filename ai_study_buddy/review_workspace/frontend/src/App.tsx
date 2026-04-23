import { useEffect, useMemo, useState } from "react";

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
      question_page_map: Array<{
        result_id: string;
        attempt_page_start: number;
        confidence: "high" | "medium" | "low";
      }>;
    };
    question_results: QuestionRow[];
  };
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

export default function App() {
  const [detail, setDetail] = useState<AttemptDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [viewerMode, setViewerMode] = useState<ViewerMode>("attempt");
  const [viewerFitMode, setViewerFitMode] = useState<ViewerFitMode>("fit_width");
  const [viewerZoomPct, setViewerZoomPct] = useState<number>(100);
  const [activeQuestionId, setActiveQuestionId] = useState<string>("");
  const [activeImageUrl, setActiveImageUrl] = useState<string | null>(null);
  const [noteScope, setNoteScope] = useState<NoteScope>("question");
  const [noteDraft, setNoteDraft] = useState<string>("");
  const [noteSaved, setNoteSaved] = useState<boolean>(true);
  const [reviewed, setReviewed] = useState<Set<string>>(new Set());

  useEffect(() => {
    async function load() {
      try {
        const students = await fetchJson<{ students: Array<{ student_id: string }> }>("/api/students");
        const sid = students.students[0]?.student_id ?? "winston";
        const attempts = await fetchJson<{ items: Array<{ attempt_id: string }> }>(
          `/api/student/attempts?student_id=${encodeURIComponent(sid)}`,
        );
        const aid = attempts.items[0]?.attempt_id;
        if (!aid) {
          throw new Error("No attempts available in backend seed");
        }
        const payload = await fetchJson<AttemptDetail>(`/api/student/attempts/${encodeURIComponent(aid)}`);
        setDetail(payload);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unknown error");
      }
    }
    load();
  }, []);

  useEffect(() => {
    if (!detail || detail.marking_result.question_results.length === 0) {
      return;
    }
    if (!activeQuestionId) {
      setActiveQuestionId(detail.marking_result.question_results[0].result_id);
      return;
    }
    const selected = detail.marking_result.question_results.find((q) => q.result_id === activeQuestionId);
    const pageStart = selected?.attempt_page_start;
    const imagePool = viewerMode === "attempt" ? detail.viewer.attempt_images : detail.viewer.answer_images;
    if (imagePool.length === 0) {
      setActiveImageUrl(null);
      return;
    }
    const exact = pageStart != null ? imagePool.find((img) => img.page_num === pageStart) : undefined;
    setActiveImageUrl((exact ?? imagePool[0]).url);
  }, [detail, activeQuestionId, viewerMode]);

  const questions = detail?.marking_result.question_results ?? [];
  const activeQuestion = useMemo(
    () => questions.find((q) => q.result_id === activeQuestionId) ?? null,
    [questions, activeQuestionId],
  );
  const persistedReviewed = useMemo(
    () =>
      new Set(
        (detail?.review_state.question_reviews ?? [])
          .filter((q) => q.review_status === "reviewed")
          .map((q) => q.result_id),
      ),
    [detail],
  );
  const effectiveReviewed = useMemo(() => {
    const merged = new Set(persistedReviewed);
    reviewed.forEach((id) => merged.add(id));
    return merged;
  }, [persistedReviewed, reviewed]);

  useEffect(() => {
    if (!detail) {
      return;
    }
    if (noteScope === "question" && activeQuestionId) {
      const q = detail.review_state.question_reviews.find((x) => x.result_id === activeQuestionId);
      setNoteDraft(q?.note_text ?? "");
      setNoteSaved(true);
      return;
    }
    if (noteScope === "attempt") {
      setNoteDraft(detail.review_state.attempt_notes[0]?.note_text ?? "");
      setNoteSaved(true);
      return;
    }
    setNoteDraft(detail.review_state.student_subject_notes[0]?.note_text ?? "");
    setNoteSaved(true);
  }, [detail, noteScope, activeQuestionId]);

  async function persistReviewState(params: {
    questionReviews: AttemptDetail["review_state"]["question_reviews"];
    attemptNotes: AttemptDetail["review_state"]["attempt_notes"];
    studentSubjectNotes: AttemptDetail["review_state"]["student_subject_notes"];
  }) {
    if (!detail) {
      return;
    }
    const { questionReviews, attemptNotes, studentSubjectNotes } = params;
    const hasReviewed = questionReviews.some((q) => q.review_status === "reviewed");
    const hasAnyNote =
      questionReviews.some((q) => (q.note_text ?? "").trim().length > 0) ||
      attemptNotes.some((n) => (n.note_text ?? "").trim().length > 0) ||
      studentSubjectNotes.some((n) => (n.note_text ?? "").trim().length > 0);
    const reviewStatus = hasReviewed || hasAnyNote ? "in_progress" : "not_started";

    const res = await fetch(`/api/student/attempts/${encodeURIComponent(detail.attempt.attempt_id)}/review-state`, {
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
    setDetail({
      ...detail,
      review_state: payload.review_state,
    });
  }

  async function saveCurrentNote() {
    if (!detail) {
      return;
    }
    const questionReviews = [...detail.review_state.question_reviews];
    const attemptNotes = [...detail.review_state.attempt_notes];
    const studentSubjectNotes = [...detail.review_state.student_subject_notes];

    if (noteScope === "question" && activeQuestionId) {
      const idx = questionReviews.findIndex((x) => x.result_id === activeQuestionId);
      const existingStatus = idx >= 0 ? questionReviews[idx].review_status : undefined;
      const row = { result_id: activeQuestionId, note_text: noteDraft, review_status: existingStatus ?? "in_progress" };
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
    if (!detail || !activeQuestionId) {
      return;
    }
    const questionReviews = [...detail.review_state.question_reviews];
    const idx = questionReviews.findIndex((x) => x.result_id === activeQuestionId);
    if (idx >= 0) {
      questionReviews[idx] = { ...questionReviews[idx], review_status: "reviewed" };
    } else {
      questionReviews.push({ result_id: activeQuestionId, review_status: "reviewed", note_text: "" });
    }
    await persistReviewState({
      questionReviews,
      attemptNotes: [...detail.review_state.attempt_notes],
      studentSubjectNotes: [...detail.review_state.student_subject_notes],
    });
    setReviewed((prev) => {
      const next = new Set(prev);
      next.add(activeQuestionId);
      return next;
    });
  }

  if (error) {
    return <main className="shell">Error: {error}</main>;
  }
  if (!detail) {
    return <main className="shell">Loading pilot artifact...</main>;
  }

  const activeIndex = Math.max(
    0,
    questions.findIndex((q) => q.result_id === activeQuestionId),
  );
  const imagePool = viewerMode === "attempt" ? detail.viewer.attempt_images : detail.viewer.answer_images;
  const incorrectQuestionCount = questions.filter(isIncorrectQuestion).length;

  return (
    <main className="shell">
      <header className="top-panel">
        <div className="attempt-meta">
          <strong>{detail.attempt.title}</strong>
          <span>{detail.attempt.student_id}</span>
          <span>{detail.attempt.subject_context}</span>
          <span>{detail.attempt.book_label ?? "No book label"}</span>
          <span>
            {detail.marking_result.summary.earned_marks}/{detail.marking_result.summary.total_marks} (
            {formatPct(detail.marking_result.summary.percentage)})
          </span>
          {detail.marking_result.context.is_partial ? <span className="pill warning">Partial marking</span> : null}
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
          <button type="button">Attempt note</button>
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
              <p>Diagnosis type: {activeQuestion.diagnosis.mistake_type ?? "-"}</p>
              <p>Diagnosis reasoning: {activeQuestion.diagnosis.reasoning ?? "-"}</p>
              <p>Mapped page: {activeQuestion.attempt_page_start ?? "-"}</p>
              <p>Skill tags: {activeQuestion.skill_tags.join(" | ") || "-"}</p>
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
            <button onClick={() => void saveCurrentNote()}>
              Save Note
            </button>
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
        <button
          onClick={() => void markCurrentQuestionReviewed()}
        >
          Mark reviewed
        </button>
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
        <button>Student-subject note</button>
      </footer>
    </main>
  );
}
