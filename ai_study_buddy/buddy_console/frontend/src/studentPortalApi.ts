export type MarksByTypeRow = {
  question_count: number;
  earned_marks: number;
  max_marks: number;
  percentage: number | null;
};

export type MarksByQuestionTypeBlock = {
  subject_context: string;
  display_label: string;
  type_order: string[];
  marks_by_question_type: {
    question_count: number;
    earned_marks: number;
    max_marks: number;
    percentage: number | null;
    by_type: Record<string, MarksByTypeRow>;
  };
};

export type MarksByQuestionTypeResponse = {
  student_id: string;
  subject: string;
  generated_at: string;
  subjects: MarksByQuestionTypeBlock[];
  message?: string;
};

export const SUBJECT_PICKERS = [
  { value: "english", label: "English" },
  { value: "chinese", label: "Chinese" },
  { value: "math", label: "Math" },
  { value: "science", label: "Science" },
] as const;

export type SubjectPickerValue = (typeof SUBJECT_PICKERS)[number]["value"];

const VALID_SUBJECTS = new Set<string>(SUBJECT_PICKERS.map((p) => p.value));

export function parseSubjectPicker(raw: string | null): SubjectPickerValue | null {
  if (!raw) {
    return null;
  }
  const normalized = raw.trim().toLowerCase();
  return VALID_SUBJECTS.has(normalized) ? (normalized as SubjectPickerValue) : null;
}

export async function fetchMarksByQuestionType(
  studentId: string,
  subject: SubjectPickerValue,
): Promise<MarksByQuestionTypeResponse> {
  const q = new URLSearchParams({
    student_id: studentId,
    subject,
  });
  const res = await fetch(`/api/student/marks-by-question-type?${q.toString()}`);
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json() as Promise<MarksByQuestionTypeResponse>;
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  return `${value.toFixed(1)}%`;
}

export function tableRowTypes(block: MarksByQuestionTypeBlock): string[] {
  const byType = block.marks_by_question_type.by_type ?? {};
  const ordered = [...block.type_order];
  if ("UNKNOWN" in byType && !ordered.includes("UNKNOWN")) {
    ordered.push("UNKNOWN");
  }
  return ordered;
}
