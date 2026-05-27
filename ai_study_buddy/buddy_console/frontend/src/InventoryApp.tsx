import { useEffect, useMemo, useRef, useState } from "react";
import { buildPdfHref, buildReviewHref } from "./inventoryLinks";

type StudentOption = {
  student_id: string;
  display_name: string;
  email: string;
};

type RootOption = {
  id: string;
  label: string;
  path: string;
};

type InventoryConfig = {
  roots: RootOption[];
  students: StudentOption[];
  scopes?: string[];
  scope_counts?: Record<string, number>;
  root_ids?: string[];
  root_counts?: Record<string, number>;
  subjects?: string[];
  subject_counts?: Record<string, number>;
  grades?: string[];
  grade_counts?: Record<string, number>;
  doc_types?: string[];
  doc_type_counts?: Record<string, number>;
  student_ids?: string[];
  student_counts?: Record<string, number>;
  book_names?: string[];
  book_counts?: Record<string, number>;
  review_status_options?: string[];
  review_status_counts?: Record<string, number>;
  is_registered_options?: string[];
  is_registered_counts?: Record<string, number>;
  has_template_options?: string[];
  has_template_counts?: Record<string, number>;
  has_marking_options?: string[];
  has_marking_counts?: Record<string, number>;
  show_is_registered_filter?: boolean;
  show_has_template_filter?: boolean;
  show_has_marking_filter?: boolean;
  show_review_status_filter?: boolean;
};

type InventoryItem = {
  absolute_path: string;
  basename: string;
  root_id: string;
  scope: string;
  subject: string;
  grade_or_scope: string;
  doc_type: string;
  book_group_name: string | null;
  student_email: string | null;
  parse_status: string;
  is_registered: boolean;
  student_id: string | null;
  registry_file_id: string | null;
  normal_name: string | null;
  has_template: boolean | null;
  template_file_id: string | null;
  completion_series_id: string | null;
  attempt_sequence: number | null;
  attempt_count: number | null;
  has_marking: boolean | null;
  has_marking_amendment: boolean | null;
  review_status: string | null;
  marking_earned_marks: number | null;
  marking_total_marks: number | null;
  marking_percentage: number | null;
  registry_added_at: string | null;
  completion_date: string | null;
  completion_date_source: string | null;
};

type InventoryResponse = {
  items: InventoryItem[];
  meta: {
    total_in_index: number;
    total_after_filter: number;
    unregistered_in_index: number;
    index_size_warning: boolean;
  };
};

type FilterState = {
  scope: string;
  root_id: string;
  student: string;
  subject: string;
  grade: string;
  doc_type: string;
  book: string;
  is_registered: string;
  has_template: string;
  has_marking: string;
  review_status: string;
  sort: string;
};

const STORAGE_KEY = "buddy_console.inventory.lastStudent";

function defaultState(): FilterState {
  return {
    scope: "completion",
    root_id: "all",
    student: "",
    subject: "all",
    grade: "all",
    doc_type: "all",
    book: "",
    is_registered: "",
    has_template: "",
    has_marking: "",
    review_status: "",
    sort: "recent",
  };
}

function readInitialState(): FilterState {
  const params = new URLSearchParams(window.location.search);
  const state = defaultState();
  const storedStudent = window.localStorage.getItem(STORAGE_KEY) || "";
  return {
    scope: params.get("scope") || state.scope,
    root_id: params.get("root_id") || state.root_id,
    student: params.get("student") || storedStudent,
    subject: params.get("subject") || state.subject,
    grade: params.get("grade") || state.grade,
    doc_type: params.get("doc_type") || state.doc_type,
    book: params.get("book") || state.book,
    is_registered: params.get("is_registered") || state.is_registered,
    has_template: params.get("has_template") || state.has_template,
    has_marking: params.get("has_marking") || state.has_marking,
    review_status: params.get("review_status") || state.review_status,
    sort: params.get("sort") || state.sort,
  };
}

function toQueryString(state: FilterState): string {
  const params = new URLSearchParams();
  if (state.scope !== "completion") params.set("scope", state.scope);
  if (state.root_id !== "all") params.set("root_id", state.root_id);
  if (state.student) params.set("student", state.student);
  if (state.subject !== "all") params.set("subject", state.subject);
  if (state.grade !== "all") params.set("grade", state.grade);
  if (state.doc_type !== "all") params.set("doc_type", state.doc_type);
  if (state.book) params.set("book", state.book);
  if (state.is_registered) params.set("is_registered", state.is_registered);
  if (state.has_template) params.set("has_template", state.has_template);
  if (state.has_marking) params.set("has_marking", state.has_marking);
  if (state.review_status) params.set("review_status", state.review_status);
  if (state.sort !== "recent") params.set("sort", state.sort);
  return params.toString();
}

function syncUrl(state: FilterState): void {
  const qs = toQueryString(state);
  const base = window.location.pathname;
  const next = qs ? `${base}?${qs}` : base;
  window.history.replaceState(null, "", next);
  if (state.student) {
    window.localStorage.setItem(STORAGE_KEY, state.student);
  } else {
    window.localStorage.removeItem(STORAGE_KEY);
  }
}

function formatScore(item: InventoryItem): string | null {
  if (!item.has_marking) return null;
  if (item.marking_earned_marks == null || item.marking_total_marks == null) return null;
  const pct =
    typeof item.marking_percentage === "number" ? Math.round(item.marking_percentage) : null;
  return pct == null
    ? `${item.marking_earned_marks}/${item.marking_total_marks}`
    : `${item.marking_earned_marks}/${item.marking_total_marks} (${pct}%)`;
}

function formatCalendarDate(isoDate: string | null): string | null {
  if (!isoDate) return null;
  const d = new Date(`${isoDate}T12:00:00`);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function formatRegistryAddedAt(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function completionDateTooltip(item: InventoryItem): string | undefined {
  if (!item.completion_date) return undefined;
  const parts = [item.completion_date];
  if (item.completion_date_source) {
    parts.push(`source: ${item.completion_date_source}`);
  }
  return parts.join(" · ");
}

function attemptSeriesLabel(item: InventoryItem): string | null {
  if (
    typeof item.attempt_count === "number" &&
    item.attempt_count > 1 &&
    typeof item.attempt_sequence === "number" &&
    item.attempt_sequence >= 1
  ) {
    return `Attempt ${item.attempt_sequence} of ${item.attempt_count}`;
  }
  return null;
}

function reviewStatusLabel(status: string): string {
  if (status === "in_progress") return "Review: in progress";
  if (status === "completed") return "Review: completed";
  return "Review: not started";
}

function labelWithCount(text: string, value: string, counts?: Record<string, number>, allKey = "all"): string {
  if (!counts) return text;
  const key = value === "" ? "" : value === "all" ? allKey : value;
  const count = counts[key];
  return typeof count === "number" ? `${text} (${count})` : text;
}

function studentLabel(studentId: string | null, studentOptions: StudentOption[]): string {
  if (!studentId) return "Unknown";
  const match = studentOptions.find((s) => s.student_id === studentId);
  return match ? `${match.student_id} (${match.display_name})` : studentId;
}

function applyFilterVisibility(state: FilterState, config: InventoryConfig): FilterState {
  const next = { ...state };
  if (!config.show_is_registered_filter) next.is_registered = "";
  if (!config.show_has_template_filter) next.has_template = "";
  if (!config.show_has_marking_filter) next.has_marking = "";
  if (!config.show_review_status_filter) next.review_status = "";
  if (next.scope === "template") next.student = "";
  if (next.doc_type !== "book") next.book = "";
  return next;
}

function coerceStateToConfig(state: FilterState, config: InventoryConfig): FilterState {
  const next = applyFilterVisibility(state, config);
  const allowedRoots = ["all", ...(config.root_ids || [])];
  if (!allowedRoots.includes(next.root_id)) next.root_id = "all";
  if (next.subject !== "all" && !(config.subjects || []).includes(next.subject)) next.subject = "all";
  if (next.grade !== "all" && !(config.grades || []).includes(next.grade)) next.grade = "all";
  if (next.doc_type !== "all" && !(config.doc_types || []).includes(next.doc_type)) next.doc_type = "all";
  if (next.student && !(config.student_ids || []).includes(next.student)) next.student = "";
  if (next.book && !(config.book_names || []).includes(next.book)) next.book = "";
  if (next.review_status && !(config.review_status_options || []).includes(next.review_status)) {
    next.review_status = "";
  }
  if (next.is_registered && !(config.is_registered_options || []).includes(next.is_registered)) {
    next.is_registered = "";
  }
  if (next.has_template && !(config.has_template_options || []).includes(next.has_template)) {
    next.has_template = "";
  }
  if (next.has_marking && !(config.has_marking_options || []).includes(next.has_marking)) {
    next.has_marking = "";
  }
  return next;
}

export default function InventoryApp() {
  const [draftState, setDraftState] = useState<FilterState>(() => readInitialState());
  const [appliedState, setAppliedState] = useState<FilterState>(() => readInitialState());
  const [config, setConfig] = useState<InventoryConfig | null>(null);
  const [inventory, setInventory] = useState<InventoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingHint, setLoadingHint] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inventoryReadyRef = useRef(false);

  useEffect(() => {
    syncUrl(appliedState);
    let cancelled = false;
    async function load(): Promise<void> {
      setLoading(true);
      setError(null);
      setLoadingHint(null);
      try {
        const healthRes = await fetch("/api/inventory/health");
        if (!cancelled && healthRes.ok) {
          const health = (await healthRes.json()) as { index_count?: number };
          const count = health.index_count;
          setLoadingHint(
            typeof count === "number"
              ? `Building inventory for ${count} indexed PDFs… first load can take 1–2 minutes.`
              : "Building inventory… first load can take 1–2 minutes.",
          );
        }

        const qs = toQueryString(appliedState);
        const suffix = qs ? `?${qs}` : "";
        const configRes = await fetch(`/api/config${suffix}`);
        if (!configRes.ok) {
          throw new Error(`Inventory request failed (config ${configRes.status})`);
        }
        const nextConfig = (await configRes.json()) as InventoryConfig;
        if (cancelled) {
          return;
        }
        setConfig(nextConfig);

        const inventoryRes = await fetch(`/api/inventory${suffix}`);
        if (!inventoryRes.ok) {
          throw new Error(`Inventory request failed (inventory ${inventoryRes.status})`);
        }
        const nextInventory = (await inventoryRes.json()) as InventoryResponse;
        if (!cancelled) {
          setInventory(nextInventory);
          inventoryReadyRef.current = true;
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load inventory");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
          setLoadingHint(null);
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [appliedState]);

  useEffect(() => {
    if (!inventoryReadyRef.current) {
      return;
    }
    let cancelled = false;
    async function loadDraftConfig(): Promise<void> {
      try {
        const qs = toQueryString(draftState);
        const suffix = qs ? `?${qs}` : "";
        const res = await fetch(`/api/config${suffix}`);
        if (!res.ok) return;
        const nextConfig = (await res.json()) as InventoryConfig;
        if (cancelled) return;
        setConfig((prev) => ({ ...(prev || {}), ...nextConfig }));
        setDraftState((prev) => coerceStateToConfig(prev, nextConfig));
      } catch {
        // Best-effort refresh only.
      }
    }
    void loadDraftConfig();
    return () => {
      cancelled = true;
    };
  }, [
    draftState.scope,
    draftState.root_id,
    draftState.student,
    draftState.subject,
    draftState.grade,
    draftState.doc_type,
    draftState.book,
    draftState.is_registered,
    draftState.has_template,
    draftState.has_marking,
    draftState.review_status,
  ]);

  const rootsById = useMemo(() => {
    const out: Record<string, string> = {};
    for (const root of config?.roots || []) {
      out[root.id] = root.path;
    }
    return out;
  }, [config]);

  const studentOptions = config?.students || [];

  function updateDraft<K extends keyof FilterState>(key: K, value: FilterState[K]): void {
    setDraftState((prev) => {
      const next = { ...prev, [key]: value };
      if (key === "scope" && value === "template") {
        next.student = "";
      }
      if (key === "doc_type" && value !== "book") {
        next.book = "";
      }
      return next;
    });
  }

  return (
    <div className="inventory-shell inventory-legacy">
      <header className="legacy-header">
        <div>
          <h1>Student File Browser</h1>
          <p className="subtitle">Buddy Console inventory</p>
        </div>
      </header>

      <section className="filters" aria-label="Filters">
        <label>
          <span>Scope</span>
          <select value={draftState.scope} onChange={(e) => updateDraft("scope", e.target.value)}>
            {(config?.scopes || ["completion", "template"]).map((scope) => (
              <option key={scope} value={scope}>
                {labelWithCount(scope === "completion" ? "Completion" : "Template", scope, config?.scope_counts)}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Root</span>
          <select value={draftState.root_id} onChange={(e) => updateDraft("root_id", e.target.value)}>
            <option value="all">{labelWithCount("All roots", "all", config?.root_counts)}</option>
            {(config?.roots || []).map((root) => (
              <option key={root.id} value={root.id}>
                {labelWithCount(root.label, root.id, config?.root_counts)}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Student</span>
          <select
            value={draftState.student}
            disabled={draftState.scope === "template"}
            onChange={(e) => updateDraft("student", e.target.value)}
          >
            <option value="">{labelWithCount("All students", "", config?.student_counts, "")}</option>
            {studentOptions.map((student) => (
              <option key={student.student_id} value={student.student_id}>
                {labelWithCount(student.student_id, student.student_id, config?.student_counts)}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Subject</span>
          <select value={draftState.subject} onChange={(e) => updateDraft("subject", e.target.value)}>
            <option value="all">{labelWithCount("All", "all", config?.subject_counts)}</option>
            {(config?.subjects || []).map((subject) => (
              <option key={subject} value={subject}>
                {labelWithCount(subject, subject, config?.subject_counts)}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Grade</span>
          <select value={draftState.grade} onChange={(e) => updateDraft("grade", e.target.value)}>
            <option value="all">{labelWithCount("All", "all", config?.grade_counts)}</option>
            {(config?.grades || []).map((grade) => (
              <option key={grade} value={grade}>
                {labelWithCount(grade, grade, config?.grade_counts)}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Type</span>
          <select value={draftState.doc_type} onChange={(e) => updateDraft("doc_type", e.target.value)}>
            <option value="all">{labelWithCount("All", "all", config?.doc_type_counts)}</option>
            {(config?.doc_types || []).map((type) => (
              <option key={type} value={type}>
                {labelWithCount(type, type, config?.doc_type_counts)}
              </option>
            ))}
          </select>
        </label>
        {draftState.doc_type === "book" ? (
          <label>
            <span>Book</span>
            <select value={draftState.book} onChange={(e) => updateDraft("book", e.target.value)}>
              <option value="">{labelWithCount("All books", "", config?.book_counts, "")}</option>
              {(config?.book_names || []).map((book) => (
                <option key={book} value={book}>
                  {labelWithCount(book, book, config?.book_counts)}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        {config?.show_is_registered_filter ? (
          <label>
            <span>Registered</span>
            <select
              value={draftState.is_registered}
              onChange={(e) => updateDraft("is_registered", e.target.value)}
            >
              <option value="">{labelWithCount("All", "", config?.is_registered_counts, "")}</option>
              {(config.is_registered_options || []).map((value) => (
                <option key={value} value={value}>
                  {labelWithCount(
                    value === "true" ? "Registered only" : "Unregistered only",
                    value,
                    config?.is_registered_counts,
                    ""
                  )}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        {config?.show_has_template_filter ? (
          <label>
            <span>Template</span>
            <select value={draftState.has_template} onChange={(e) => updateDraft("has_template", e.target.value)}>
              <option value="">{labelWithCount("All", "", config?.has_template_counts, "")}</option>
              {(config.has_template_options || []).map((value) => (
                <option key={value} value={value}>
                  {labelWithCount(
                    value === "true" ? "Has template" : "No template",
                    value,
                    config?.has_template_counts,
                    ""
                  )}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        {config?.show_has_marking_filter ? (
          <label>
            <span>Marking</span>
            <select value={draftState.has_marking} onChange={(e) => updateDraft("has_marking", e.target.value)}>
              <option value="">{labelWithCount("All", "", config?.has_marking_counts, "")}</option>
              {(config.has_marking_options || []).map((value) => (
                <option key={value} value={value}>
                  {labelWithCount(
                    value === "true" ? "Marked" : "Not marked",
                    value,
                    config?.has_marking_counts,
                    ""
                  )}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        {config?.show_review_status_filter ? (
          <label>
            <span>Review</span>
            <select
              value={draftState.review_status}
              onChange={(e) => updateDraft("review_status", e.target.value)}
            >
              <option value="">{labelWithCount("All", "", config?.review_status_counts, "")}</option>
              {(config.review_status_options || []).map((status) => (
                <option key={status} value={status}>
                  {labelWithCount(reviewStatusLabel(status).replace("Review: ", ""), status, config?.review_status_counts, "")}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <div className="filter-actions">
          <button type="button" className="apply-filters" onClick={() => setAppliedState(draftState)}>
            Apply filters
          </button>
          <button
            type="button"
            className="reset-filters"
            onClick={() => {
              const next = defaultState();
              setDraftState(next);
              setAppliedState(next);
            }}
          >
            Reset
          </button>
          <label>
            <span>Sort</span>
            <select value={draftState.sort} onChange={(e) => updateDraft("sort", e.target.value)}>
              <option value="recent">Completed (recent)</option>
              <option value="name">Name (A-Z)</option>
            </select>
          </label>
        </div>
      </section>

      <section className="meta">
        {loading ? (
          <span>{loadingHint ?? "Loading inventory…"}</span>
        ) : null}
        {error ? <span className="inventory-error">{error}</span> : null}
        {!loading && inventory ? (
          <span>
            {inventory.meta.total_after_filter} shown of {inventory.meta.total_in_index} indexed
            {inventory.meta.unregistered_in_index ? ` (${inventory.meta.unregistered_in_index} unregistered in index)` : ""}
            {inventory.meta.index_size_warning ? " - large index: narrow filters" : ""}
          </span>
        ) : null}
      </section>

      <section className="grid">
        {(inventory?.items || []).map((item) => {
          const reviewHref = buildReviewHref(item);
          const pdfHref = buildPdfHref(item, rootsById);
          const score = formatScore(item);
          const completionLabel = formatCalendarDate(item.completion_date);
          const addedLabel = formatRegistryAddedAt(item.registry_added_at);
          const attemptLabel = attemptSeriesLabel(item);
          return (
            <article key={item.absolute_path} className="card" role="listitem">
              <div className="icon">PDF</div>
              <div className="card-title-row">
                <h3>{item.normal_name || item.basename}</h3>
                {attemptLabel ? <span className="chip status-info">{attemptLabel}</span> : null}
              </div>
              {score ? <p className="card-marking-score">{score}</p> : null}
              {completionLabel ? (
                <p className="card-completion-date" title={completionDateTooltip(item)}>
                  Completed {completionLabel}
                </p>
              ) : null}
              {addedLabel ? (
                <p className="card-registry-date" title={item.registry_added_at || undefined}>
                  Registered {addedLabel}
                </p>
              ) : null}
              <div className="chips">
                {item.subject && item.subject !== "unknown" ? <span className="chip">{item.subject}</span> : null}
                {item.grade_or_scope && item.grade_or_scope !== "unknown" ? (
                  <span className="chip">{item.grade_or_scope}</span>
                ) : null}
                {item.doc_type && item.doc_type !== "unknown" ? <span className="chip">{item.doc_type}</span> : null}
                {item.root_id ? <span className="chip">{item.root_id}</span> : null}
              </div>
              <div className="status-chips">
                <span className={`chip ${item.is_registered ? "ok" : "warn"}`}>
                  {item.is_registered ? "Registered" : "Unregistered"}
                </span>
                {item.is_registered && item.scope === "template" ? (
                  <span className="chip status-neutral">Template</span>
                ) : null}
                {item.is_registered && item.scope !== "template" ? (
                  <>
                    <span className={`chip ${item.has_template ? "ok" : "warn"}`}>
                      {item.has_template ? "Has template" : "No template"}
                    </span>
                    <span className={`chip ${item.has_marking ? "ok" : "warn"}`}>
                      {item.has_marking ? "Marked" : "Not marked"}
                    </span>
                    {item.has_marking_amendment ? <span className="chip status-info">Amendment</span> : null}
                    {item.review_status ? (
                      <span
                        className={`chip ${
                          item.review_status === "completed"
                            ? "ok"
                            : item.review_status === "in_progress"
                              ? "status-info"
                              : "warn"
                        }`}
                      >
                        {reviewStatusLabel(item.review_status)}
                      </span>
                    ) : null}
                  </>
                ) : null}
              </div>
              <div className="card-actions">
                {pdfHref ? (
                  <a href={pdfHref} target="_blank" rel="noreferrer">
                    View PDF
                  </a>
                ) : (
                  <span className="disabled-link">View PDF</span>
                )}
                <button
                  type="button"
                  onClick={() => navigator.clipboard.writeText(item.absolute_path)}
                >
                  Copy path
                </button>
                {reviewHref ? (
                  <a href={reviewHref} target="_blank" rel="noreferrer">
                    Review Workspace
                  </a>
                ) : null}
              </div>
            </article>
          );
        })}
      </section>
    </div>
  );
}
