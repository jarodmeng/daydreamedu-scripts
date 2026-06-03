import { useCallback, useEffect, useMemo, useState } from "react";
import {
  SUBJECT_PICKERS,
  fetchMarksByQuestionType,
  formatPercent,
  parseSubjectPicker,
  tableRowTypes,
  type MarksByQuestionTypeResponse,
  type SubjectPickerValue,
} from "./studentPortalApi";

function readUrlState(): { studentId: string | null; subject: SubjectPickerValue | null } {
  const q = new URLSearchParams(window.location.search);
  return {
    studentId: q.get("student_id")?.trim() || null,
    subject: parseSubjectPicker(q.get("subject")),
  };
}

function replaceStudentPortalUrl(studentId: string, subject: SubjectPickerValue | null): void {
  const q = new URLSearchParams();
  q.set("student_id", studentId);
  if (subject) {
    q.set("subject", subject);
  }
  const search = q.toString();
  const url = `${window.location.pathname}?${search}`;
  window.history.replaceState(null, "", url);
}

export default function StudentPortalApp() {
  const initial = useMemo(() => readUrlState(), []);
  const [studentId] = useState(initial.studentId);
  const [selectedSubject, setSelectedSubject] = useState<SubjectPickerValue | null>(initial.subject);
  const [payload, setPayload] = useState<MarksByQuestionTypeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadMarks = useCallback(async (sid: string, subject: SubjectPickerValue) => {
    setLoading(true);
    setError(null);
    setPayload(null);
    try {
      const data = await fetchMarksByQuestionType(sid, subject);
      setPayload(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load marks");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!studentId || !selectedSubject) {
      setPayload(null);
      setError(null);
      setLoading(false);
      return;
    }
    void loadMarks(studentId, selectedSubject);
  }, [studentId, selectedSubject, loadMarks]);

  const onSelectSubject = (subject: SubjectPickerValue) => {
    if (!studentId) {
      return;
    }
    setSelectedSubject(subject);
    replaceStudentPortalUrl(studentId, subject);
  };

  if (!studentId) {
    return (
      <div className="student-portal-shell">
        <header className="student-portal-header">
          <h1>Student marks</h1>
          <p className="student-portal-subtitle">Marks by question type</p>
        </header>
        <p className="student-portal-warn">
          Missing <code>student_id</code> in the URL. Example:{" "}
          <code>/student?student_id=winston&amp;subject=math</code>
        </p>
      </div>
    );
  }

  return (
    <div className="student-portal-shell">
      <header className="student-portal-header">
        <h1>Student marks</h1>
        <p className="student-portal-subtitle">
          Marks by question type for <strong>{studentId}</strong>
        </p>
      </header>

      <div className="student-portal-picker" role="group" aria-label="Subject">
        {SUBJECT_PICKERS.map((option) => (
          <button
            key={option.value}
            type="button"
            className={
              selectedSubject === option.value
                ? "student-portal-picker-btn is-active"
                : "student-portal-picker-btn"
            }
            onClick={() => onSelectSubject(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>

      {!selectedSubject && (
        <p className="student-portal-hint">Select a subject to load marks.</p>
      )}

      {selectedSubject && loading && <p className="student-portal-hint">Loading marks…</p>}

      {selectedSubject && error && (
        <p className="student-portal-warn" role="alert">
          {error}
        </p>
      )}

      {selectedSubject && !loading && !error && payload && payload.subjects.length === 0 && (
        <p className="student-portal-hint">{payload.message ?? "No marks in scope for this subject."}</p>
      )}

      {selectedSubject &&
        !loading &&
        !error &&
        payload?.subjects.map((block) => (
          <section key={block.subject_context} className="student-portal-block">
            <h2>{block.display_label}</h2>
            <table className="student-portal-table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Questions</th>
                  <th>Earned</th>
                  <th>Max</th>
                  <th>%</th>
                </tr>
              </thead>
              <tbody>
                {tableRowTypes(block).map((qtype) => {
                  const row = block.marks_by_question_type.by_type[qtype];
                  if (!row) {
                    return null;
                  }
                  return (
                    <tr key={qtype}>
                      <td>{qtype}</td>
                      <td>{row.question_count}</td>
                      <td>{row.earned_marks}</td>
                      <td>{row.max_marks}</td>
                      <td>{formatPercent(row.percentage)}</td>
                    </tr>
                  );
                })}
                <tr className="student-portal-total-row">
                  <td>
                    <strong>Total</strong>
                  </td>
                  <td>
                    <strong>{block.marks_by_question_type.question_count}</strong>
                  </td>
                  <td>
                    <strong>{block.marks_by_question_type.earned_marks}</strong>
                  </td>
                  <td>
                    <strong>{block.marks_by_question_type.max_marks}</strong>
                  </td>
                  <td>
                    <strong>{formatPercent(block.marks_by_question_type.percentage)}</strong>
                  </td>
                </tr>
              </tbody>
            </table>
          </section>
        ))}

      {selectedSubject && !loading && !error && payload && (
        <footer className="student-portal-footnote">
          <p>
            Computed: {payload.generated_at}. Totals use counted rows with amendments applied (same as
            operator report).
          </p>
        </footer>
      )}
    </div>
  );
}
