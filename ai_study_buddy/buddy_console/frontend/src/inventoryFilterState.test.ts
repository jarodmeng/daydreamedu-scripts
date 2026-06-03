import { describe, expect, it } from "vitest";
import {
  filterStateForQuery,
  mergeInventoryConfig,
  normalizeFacetQuery,
  scopeOptionsFromConfig,
} from "./inventoryFilterState";

describe("normalizeFacetQuery", () => {
  it("returns empty when nothing selected", () => {
    expect(normalizeFacetQuery([], ["math", "science"])).toEqual([]);
  });

  it("treats every option selected as no restriction", () => {
    expect(normalizeFacetQuery(["math", "science"], ["math", "science"])).toEqual([]);
  });

  it("keeps partial selection", () => {
    expect(normalizeFacetQuery(["math"], ["math", "science"])).toEqual(["math"]);
  });
});

describe("scopeOptionsFromConfig", () => {
  it("falls back when API returns empty scopes", () => {
    expect(scopeOptionsFromConfig({ scopes: [] })).toEqual(["completion", "template"]);
  });
});

describe("mergeInventoryConfig", () => {
  it("preserves prior facet lists when response is empty", () => {
    const merged = mergeInventoryConfig(
      { scopes: ["completion"], subjects: ["math"] },
      { scopes: [], subjects: [] },
    );
    expect(merged.scopes).toEqual(["completion"]);
    expect(merged.subjects).toEqual(["math"]);
  });
});

describe("filterStateForQuery", () => {
  it("clears facets that include every option", () => {
    const out = filterStateForQuery(
      {
        scope: "completion",
        root_id: "all",
        student: "winston",
        subject: ["math", "science"],
        grade: [],
        doc_type: [],
        book: "",
        is_registered: "",
        has_template: "",
        has_marking: "",
        review_status: "",
        sort: "recent",
      },
      { subjects: ["math", "science"] },
    );
    expect(out.subject).toEqual([]);
  });
});
