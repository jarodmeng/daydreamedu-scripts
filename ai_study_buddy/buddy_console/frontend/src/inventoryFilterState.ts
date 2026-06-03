export type FacetFilterState = {
  scope: string;
  root_id: string;
  student: string;
  subject: string[];
  grade: string[];
  doc_type: string[];
  book: string;
  is_registered: string;
  has_template: string;
  has_marking: string;
  review_status: string;
  sort: string;
};

export const DEFAULT_INVENTORY_SCOPES = ["completion", "template"] as const;

export type InventoryFacetConfig = {
  subjects?: string[];
  grades?: string[];
  doc_types?: string[];
  scopes?: string[];
};

/** Empty array from API means "no restriction", not "match nothing". */
export function normalizeFacetQuery(selected: string[], options: string[]): string[] {
  if (!selected.length || !options.length) return [];
  if (selected.length < options.length) return selected;
  const allowed = new Set(options);
  if (selected.every((value) => allowed.has(value))) return [];
  return selected;
}

export function scopeOptionsFromConfig(config: InventoryFacetConfig | null | undefined): string[] {
  const scopes = config?.scopes;
  return scopes && scopes.length > 0 ? scopes : [...DEFAULT_INVENTORY_SCOPES];
}

export function cloneFilterState(state: FacetFilterState): FacetFilterState {
  return {
    ...state,
    subject: [...state.subject],
    grade: [...state.grade],
    doc_type: [...state.doc_type],
  };
}

export function filterStateForQuery(
  state: FacetFilterState,
  config: InventoryFacetConfig | null | undefined,
): FacetFilterState {
  if (!config) return cloneFilterState(state);
  return {
    ...state,
    subject: normalizeFacetQuery(state.subject, config.subjects || []),
    grade: normalizeFacetQuery(state.grade, config.grades || []),
    doc_type: normalizeFacetQuery(state.doc_type, config.doc_types || []),
  };
}

export function filterStateQueryKey(state: FacetFilterState): string {
  const q = filterStateForQuery(state, null);
  return [
    q.scope,
    q.root_id,
    q.student,
    q.subject.join(","),
    q.grade.join(","),
    q.doc_type.join(","),
    q.book,
    q.is_registered,
    q.has_template,
    q.has_marking,
    q.review_status,
    q.sort,
  ].join("|");
}

export function mergeInventoryConfig<T extends InventoryFacetConfig>(prev: T | null, next: T): T {
  const merged = { ...(prev || {}), ...next } as T;
  if (!next.scopes?.length && prev?.scopes?.length) {
    merged.scopes = prev.scopes;
  }
  if (!next.subjects?.length && prev?.subjects?.length) {
    merged.subjects = prev.subjects;
  }
  if (!next.grades?.length && prev?.grades?.length) {
    merged.grades = prev.grades;
  }
  if (!next.doc_types?.length && prev?.doc_types?.length) {
    merged.doc_types = prev.doc_types;
  }
  return merged;
}
