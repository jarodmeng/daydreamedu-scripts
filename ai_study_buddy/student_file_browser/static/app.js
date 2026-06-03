(function () {
  const STORAGE_KEY = "student_file_browser.lastStudent";
  const REVIEW_WORKSPACE_PORT = 5178;
  const ROOT_BROWSER_PORT = 8770;

  /** Review Workspace / Root PDF Browser run on localhost; avoid 127.0.0.1 origin split. */
  function siblingAppHostname() {
    const h = window.location.hostname;
    if (h === "127.0.0.1" || h === "::1") return "localhost";
    return h;
  }

  function siblingAppBaseUrl(port) {
    return `http://${siblingAppHostname()}:${port}/`;
  }

  let config = null;
  let rootsById = {};
  let loadGeneration = 0;

  function defaultRootId() {
    return "all";
  }

  const DEFAULT_SCOPES = ["completion", "template"];

  function normalizeFacetQuery(selected, options) {
    if (!selected.length || !options.length) return [];
    if (selected.length < options.length) return selected;
    const allowed = new Set(options);
    if (selected.every((value) => allowed.has(value))) return [];
    return selected;
  }

  function queryFacetsFromState(state) {
    return {
      subject: normalizeFacetQuery(state.subject || [], config?.subjects || []),
      grade: normalizeFacetQuery(state.grade || [], config?.grades || []),
      doc_type: normalizeFacetQuery(state.doc_type || [], config?.doc_types || []),
    };
  }

  function scopeOptionsFromConfig() {
    const scopes = config?.scopes;
    return scopes && scopes.length ? scopes : DEFAULT_SCOPES;
  }

  function mergeFilterMeta(prev, next) {
    const merged = { ...(prev || {}), ...next };
    if (!next.scopes?.length && prev?.scopes?.length) merged.scopes = prev.scopes;
    if (!next.subjects?.length && prev?.subjects?.length) merged.subjects = prev.subjects;
    if (!next.grades?.length && prev?.grades?.length) merged.grades = prev.grades;
    if (!next.doc_types?.length && prev?.doc_types?.length) merged.doc_types = prev.doc_types;
    return merged;
  }

  function qsFromState(state) {
    const facets = queryFacetsFromState(state);
    const p = new URLSearchParams();
    if (state.scope && state.scope !== "completion") p.set("scope", state.scope);
    const defaultRoot = defaultRootId();
    if (state.root_id && state.root_id !== defaultRoot) p.set("root_id", state.root_id);
    if (state.student) p.set("student", state.student);
    facets.subject.forEach((value) => p.append("subject", value));
    facets.grade.forEach((value) => p.append("grade", value));
    facets.doc_type.forEach((value) => p.append("doc_type", value));
    if (state.book) p.set("book", state.book);
    if (state.is_registered === "true" || state.is_registered === "false") {
      p.set("is_registered", state.is_registered);
    }
    if (state.has_template === "true" || state.has_template === "false") {
      p.set("has_template", state.has_template);
    }
    if (state.has_marking === "true" || state.has_marking === "false") {
      p.set("has_marking", state.has_marking);
    }
    if (state.review_status) p.set("review_status", state.review_status);
    if (state.sort && state.sort !== "recent") p.set("sort", state.sort);
    return p.toString();
  }

  function readFacetValues(params, key) {
    return params
      .getAll(key)
      .map((value) => value.trim())
      .filter((value) => value && value !== "all");
  }

  function defaultFilterState() {
    return {
      scope: "completion",
      root_id: defaultRootId(),
      student: "",
      subject: [],
      grade: [],
      doc_type: [],
      book: "",
      is_registered: "",
      has_template: "",
      has_marking: "",
      review_status: "",
      sort: "recent",
    };
  }

  function stateFromUrl() {
    const p = new URLSearchParams(location.search);
    return {
      scope: p.get("scope") || "completion",
      root_id: p.get("root_id") || "",
      student: p.get("student") || localStorage.getItem(STORAGE_KEY) || "",
      subject: readFacetValues(p, "subject"),
      grade: readFacetValues(p, "grade"),
      doc_type: readFacetValues(p, "doc_type"),
      book: p.get("book") || "",
      is_registered: p.get("is_registered") || "",
      has_template: p.get("has_template") || "",
      has_marking: p.get("has_marking") || "",
      review_status: p.get("review_status") || "",
      sort: p.get("sort") || "recent",
    };
  }

  function reviewStatusLabel(value) {
    if (value === "not_started") return "Not started";
    if (value === "in_progress") return "In progress";
    if (value === "completed") return "Completed";
    return value;
  }

  function scopeLabel(value) {
    if (value === "completion") return "Completion";
    if (value === "template") return "Template";
    return value;
  }

  function rootLabel(value) {
    if (value === "daydreamedu") return "DaydreamEdu";
    if (value === "goodnotes") return "GoodNotes";
    if (value === "all") return "All roots";
    return value;
  }

  function labelWithCount(text, value, counts) {
    if (!counts || typeof counts !== "object") return text;
    const key = value === "all" ? "all" : value;
    const n = counts[key];
    if (n === undefined) return text;
    return `${text} (${n})`;
  }

  /** Build All + only boolean option values present in contextual meta. */
  function boolFilterOptions(optionKey, countsKey, labels) {
    const allowed = config[optionKey] || [];
    const counts = config[countsKey] || {};
    const opts = [{ value: "", label: labelWithCount("All", "", counts) }];
    if (allowed.includes("true")) {
      opts.push({
        value: "true",
        label: labelWithCount(labels.true, "true", counts),
      });
    }
    if (allowed.includes("false")) {
      opts.push({
        value: "false",
        label: labelWithCount(labels.false, "false", counts),
      });
    }
    return opts;
  }

  function syncUrl(state) {
    const q = qsFromState(state);
    const url = q ? `${location.pathname}?${q}` : location.pathname;
    history.replaceState(null, "", url);
    if (state.student) localStorage.setItem(STORAGE_KEY, state.student);
  }

  function relPathForItem(item) {
    const root = rootsById[item.root_id];
    if (!root) return null;
    const abs = String(item.absolute_path).replace(/\\/g, "/");
    const rootNorm = String(root).replace(/\\/g, "/").replace(/\/+$/, "");
    const prefix = rootNorm + "/";
    if (abs.startsWith(prefix)) return abs.slice(prefix.length);
    return null;
  }

  function closeOtherFacetMenus(active) {
    const root = document.getElementById("filters");
    if (!root) return;
    root.querySelectorAll("details.multi-select[open]").forEach((node) => {
      if (node !== active) node.removeAttribute("open");
    });
  }

  let facetClickOutsideInstalled = false;

  function installFacetClickOutside() {
    if (facetClickOutsideInstalled) return;
    facetClickOutsideInstalled = true;
    document.addEventListener("pointerdown", (event) => {
      const filters = document.getElementById("filters");
      if (!filters) return;
      const target = event.target;
      if (!(target instanceof Node)) return;
      filters.querySelectorAll("details.multi-select[open]").forEach((details) => {
        const facet = details.closest(".multi-select-filter");
        if (facet && facet.contains(target)) return;
        details.removeAttribute("open");
      });
    });
  }

  function buildFilters(state) {
    const el = document.getElementById("filters");
    el.innerHTML = "";
    const templateMode = state.scope === "template";

    function addMultiSelect(id, label, options, selected, counts, parent) {
      const host = parent || el;
      const selectedSet = new Set(selected || []);
      const lab = document.createElement("label");
      lab.className = "multi-select-filter";
      lab.htmlFor = id;
      const title = document.createElement("span");
      title.textContent = label;
      const details = document.createElement("details");
      details.className = "multi-select";
      details.id = id;
      details.addEventListener("toggle", () => {
        if (details.open) closeOtherFacetMenus(details);
      });
      const summary = document.createElement("summary");
      function refreshSummary() {
        const current = Array.from(
          details.querySelectorAll('input[type="checkbox"][data-value]:checked')
        ).map((cb) => cb.dataset.value);
        if (current.length === 0) {
          summary.textContent = labelWithCount("All", "all", counts);
        } else if (current.length === 1) {
          summary.textContent = labelWithCount(current[0], current[0], counts);
        } else {
          summary.textContent = `${current.length} selected`;
        }
      }
      const panel = document.createElement("div");
      panel.className = "multi-select-panel";
      panel.setAttribute("role", "group");
      panel.setAttribute("aria-label", label);

      const allLab = document.createElement("label");
      allLab.className = "multi-select-option";
      const allCb = document.createElement("input");
      allCb.type = "checkbox";
      allCb.checked = selectedSet.size === 0;
      allCb.addEventListener("change", () => {
        if (allCb.checked) {
          panel.querySelectorAll('input[type="checkbox"][data-value]').forEach((cb) => {
            cb.checked = false;
          });
        }
        refreshSummary();
        void onDraftLayoutChange({ rebuild: false });
      });
      const allText = document.createElement("span");
      allText.textContent = labelWithCount("All", "all", counts);
      allLab.appendChild(allCb);
      allLab.appendChild(allText);
      panel.appendChild(allLab);

      options.forEach((opt) => {
        const optLab = document.createElement("label");
        optLab.className = "multi-select-option";
        const cb = document.createElement("input");
        cb.type = "checkbox";
        cb.dataset.value = opt.value;
        cb.checked = selectedSet.has(opt.value);
        cb.addEventListener("change", () => {
          if (cb.checked) allCb.checked = false;
          let current = Array.from(
            panel.querySelectorAll('input[type="checkbox"][data-value]:checked')
          ).map((node) => node.dataset.value);
          if (options.length > 0 && current.length >= options.length) {
            const allowed = new Set(options.map((o) => o.value));
            if (current.every((value) => allowed.has(value))) {
              panel.querySelectorAll('input[type="checkbox"][data-value]').forEach((node) => {
                node.checked = false;
              });
              allCb.checked = true;
              refreshSummary();
              void onDraftLayoutChange({ rebuild: false });
              return;
            }
          }
          const anyChecked = panel.querySelector('input[type="checkbox"][data-value]:checked');
          if (!anyChecked) allCb.checked = true;
          refreshSummary();
          void onDraftLayoutChange({ rebuild: false });
        });
        const text = document.createElement("span");
        text.textContent = opt.label;
        optLab.appendChild(cb);
        optLab.appendChild(text);
        panel.appendChild(optLab);
      });

      panel.addEventListener("click", (event) => {
        event.stopPropagation();
      });

      refreshSummary();
      details.appendChild(summary);
      details.appendChild(panel);
      lab.appendChild(title);
      lab.appendChild(details);
      host.appendChild(lab);
    }

    function addSelect(id, label, options, value, parent) {
      const host = parent || el;
      const lab = document.createElement("label");
      lab.htmlFor = id;
      const title = document.createElement("span");
      title.textContent = label;
      const sel = document.createElement("select");
      sel.id = id;
      options.forEach((o) => {
        const opt = document.createElement("option");
        opt.value = o.value;
        opt.textContent = o.label;
        if (o.value === value) opt.selected = true;
        sel.appendChild(opt);
      });
      if (id === "scope") {
        sel.addEventListener("change", onDraftLayoutChange);
      }
      if (id === "sort") {
        sel.addEventListener("change", onApplyFilters);
      }
      lab.appendChild(title);
      lab.appendChild(sel);
      host.appendChild(lab);
    }

    const scopes = scopeOptionsFromConfig();
    const scopeCounts = config.scope_counts || {};
    if (scopes.length > 1) {
      addSelect(
        "scope",
        "Scope",
        scopes.map((s) => ({
          value: s,
          label: labelWithCount(scopeLabel(s), s, scopeCounts),
        })),
        state.scope
      );
    }

    const configuredRoots = config.roots || [];
    if (configuredRoots.length > 0) {
      const rootCounts = config.root_counts || {};
      const rootOptionIds =
        (config.root_ids && config.root_ids.length
          ? config.root_ids
          : configuredRoots.map((r) => r.id)) || [];
      const rootOptions = [
        { value: "all", label: labelWithCount("All roots", "all", rootCounts) },
      ];
      rootOptionIds.forEach((rid) => {
        rootOptions.push({
          value: rid,
          label: labelWithCount(rootLabel(rid), rid, rootCounts),
        });
      });
      const effectiveRoot = state.root_id || defaultRootId();
      addSelect("root_id", "Root", rootOptions, effectiveRoot);
    }

    const studentLab = document.createElement("label");
    studentLab.htmlFor = "student";
    if (templateMode) studentLab.classList.add("disabled");
    const stTitle = document.createElement("span");
    stTitle.textContent = templateMode ? "Student (n/a for templates)" : "Student";
    const stSel = document.createElement("select");
    stSel.id = "student";
    stSel.disabled = templateMode;
    const empty = document.createElement("option");
    empty.value = "";
    const studentCounts = config.student_counts || {};
    empty.textContent = labelWithCount("All students", "", studentCounts);
    stSel.appendChild(empty);
    (config.student_ids || []).forEach((sid) => {
      const opt = document.createElement("option");
      opt.value = sid;
      opt.textContent = labelWithCount(sid, sid, studentCounts);
      if (sid === state.student) opt.selected = true;
      stSel.appendChild(opt);
    });
    studentLab.appendChild(stTitle);
    studentLab.appendChild(stSel);
    el.appendChild(studentLab);

    const subjectCounts = config.subject_counts || {};
    const gradeCounts = config.grade_counts || {};
    const docTypeCounts = config.doc_type_counts || {};
    addMultiSelect(
      "subject",
      "Subject",
      (config.subjects || []).map((s) => ({
        value: s,
        label: labelWithCount(s, s, subjectCounts),
      })),
      state.subject,
      subjectCounts
    );
    addMultiSelect(
      "grade",
      "Grade",
      (config.grades || []).map((g) => ({
        value: g,
        label: labelWithCount(g, g, gradeCounts),
      })),
      state.grade,
      gradeCounts
    );
    addMultiSelect(
      "doc_type",
      "Type",
      (config.doc_types || []).map((t) => ({
        value: t,
        label: labelWithCount(
          t.charAt(0).toUpperCase() + t.slice(1),
          t,
          docTypeCounts
        ),
      })),
      state.doc_type,
      docTypeCounts
    );

    if (state.doc_type.length === 1 && state.doc_type[0] === "book") {
      const bookNames = config.book_names || [];
      const bookCounts = config.book_counts || {};
      const bookOptions = [
        { value: "", label: labelWithCount("All books", "", bookCounts) },
      ];
      const seen = new Set();
      bookNames.forEach((name) => {
        bookOptions.push({
          value: name,
          label: labelWithCount(name, name, bookCounts),
        });
        seen.add(name);
      });
      if (state.book && !seen.has(state.book)) {
        bookOptions.push({ value: state.book, label: state.book });
      }
      addSelect("book", "Book name", bookOptions, state.book);
    }

    if (config.show_is_registered_filter) {
      addSelect(
        "is_registered",
        "Registered",
        boolFilterOptions(
          "is_registered_options",
          "is_registered_counts",
          {
            true: "Registered only",
            false: "Unregistered only",
          }
        ),
        state.is_registered
      );
    }

    if (config.show_has_template_filter) {
      addSelect(
        "has_template",
        "Template",
        boolFilterOptions("has_template_options", "has_template_counts", {
          true: "Has template",
          false: "No template",
        }),
        state.has_template
      );
    }

    if (config.show_has_marking_filter) {
      addSelect(
        "has_marking",
        "Marking",
        boolFilterOptions("has_marking_options", "has_marking_counts", {
          true: "Marked",
          false: "Not marked",
        }),
        state.has_marking
      );
    }

    if (config.show_review_status_filter) {
      const reviewCounts = config.review_status_counts || {};
      const reviewOptions = [
        { value: "", label: labelWithCount("All", "", reviewCounts) },
      ].concat(
        (config.review_status_options || []).map((v) => ({
          value: v,
          label: labelWithCount(reviewStatusLabel(v), v, reviewCounts),
        }))
      );
      addSelect("review_status", "Review", reviewOptions, state.review_status);
    }

    const actions = document.createElement("div");
    actions.className = "filter-actions";
    const applyBtn = document.createElement("button");
    applyBtn.type = "button";
    applyBtn.id = "apply-filters";
    applyBtn.className = "apply-filters";
    applyBtn.textContent = "Filter";
    applyBtn.addEventListener("click", onApplyFilters);
    const resetBtn = document.createElement("button");
    resetBtn.type = "button";
    resetBtn.id = "reset-filters";
    resetBtn.className = "reset-filters";
    resetBtn.textContent = "Reset";
    resetBtn.addEventListener("click", onResetFilters);
    actions.appendChild(applyBtn);
    actions.appendChild(resetBtn);
    addSelect(
      "sort",
      "Sort",
      [
        { value: "recent", label: "Completed (recent)" },
        { value: "name", label: "Name (A–Z)" },
      ],
      state.sort || "recent",
      actions
    );
    el.appendChild(actions);
  }

  async function onDraftLayoutChange(options = {}) {
    const rebuild = options.rebuild !== false;
    const state = readStateFromDom();
    try {
      const cfgRes = await fetch(`/api/config?${qsFromState(state)}`);
      const data = await cfgRes.json();
      applyFilterOptionsFromMeta(data);
    } catch {
      /* keep prior options */
    }
    if (rebuild) buildFilters(state);
  }

  function readFacetFromDom(id) {
    const host = document.getElementById(id);
    if (!host) return [];
    return Array.from(host.querySelectorAll('input[type="checkbox"][data-value]:checked'))
      .map((cb) => cb.dataset.value)
      .filter(Boolean);
  }

  function readStateFromDom() {
    const scope = document.getElementById("scope")?.value || "completion";
    const root_id =
      document.getElementById("root_id")?.value || defaultRootId();
    const student = document.getElementById("student")?.value || "";
    const subject = readFacetFromDom("subject");
    const grade = readFacetFromDom("grade");
    const doc_type = readFacetFromDom("doc_type");
    const book = document.getElementById("book")?.value || "";
    const is_registered = document.getElementById("is_registered")?.value || "";
    const has_template = document.getElementById("has_template")?.value || "";
    const has_marking = document.getElementById("has_marking")?.value || "";
    const review_status = document.getElementById("review_status")?.value || "";
    const sort = document.getElementById("sort")?.value || "recent";
    return {
      scope,
      root_id,
      student,
      subject,
      grade,
      doc_type,
      book,
      is_registered,
      has_template,
      has_marking,
      review_status,
      sort,
    };
  }

  function setFilterButtonsDisabled(disabled) {
    const applyBtn = document.getElementById("apply-filters");
    const resetBtn = document.getElementById("reset-filters");
    if (applyBtn) applyBtn.disabled = disabled;
    if (resetBtn) resetBtn.disabled = disabled;
  }

  async function onApplyFilters() {
    const state = readStateFromDom();
    setFilterButtonsDisabled(true);
    syncUrl(state);
    try {
      await loadInventory(state);
    } finally {
      setFilterButtonsDisabled(false);
    }
  }

  async function onResetFilters() {
    localStorage.removeItem(STORAGE_KEY);
    const state = defaultFilterState();
    setFilterButtonsDisabled(true);
    syncUrl(state);
    try {
      const cfgRes = await fetch("/api/config");
      config = await cfgRes.json();
      applyFilterOptionsFromMeta(config);
      config.subjects = config.subjects || [];
      config.grades = config.grades || [];
      config.doc_types = config.doc_types || [];
      config.student_ids = config.student_ids || [];
      config.book_names = config.book_names || [];
      (config.roots || []).forEach((r) => {
        rootsById[r.id] = r.path;
      });
      buildFilters(state);
      await loadInventory(state);
    } finally {
      setFilterButtonsDisabled(false);
    }
  }

  function appendStatusChip(container, text, variant) {
    const c = document.createElement("span");
    c.className = "chip status-" + variant;
    c.textContent = text;
    container.appendChild(c);
  }

  function formatCalendarDate(isoDate) {
    if (!isoDate) return null;
    const d = new Date(`${isoDate}T12:00:00`);
    if (Number.isNaN(d.getTime())) return null;
    return d.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  }

  function formatRegistryAddedAt(iso) {
    if (!iso) return null;
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return null;
    return d.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  }

  function completionDateTooltip(item) {
    if (!item.completion_date) return "";
    const parts = [item.completion_date];
    if (item.completion_date_source) {
      parts.push(`source: ${item.completion_date_source}`);
    }
    return parts.join(" · ");
  }

  function formatMarkValue(value) {
    if (typeof value === "number" && Number.isFinite(value)) {
      return String(value);
    }
    return null;
  }

  function formatMarkingScore(item) {
    if (!item.has_marking) return null;
    const earned = formatMarkValue(item.marking_earned_marks);
    const total = formatMarkValue(item.marking_total_marks);
    if (earned === null || total === null) return null;
    let pct = item.marking_percentage;
    if (typeof pct !== "number" || Number.isNaN(pct)) {
      const e = Number(item.marking_earned_marks);
      const t = Number(item.marking_total_marks);
      pct = t > 0 ? Math.round((e / t) * 100) : 0;
    } else {
      pct = Math.round(pct);
    }
    return `${earned}/${total} (${pct}%)`;
  }

  function attemptSeriesLabel(item) {
    const attemptCount = item.attempt_count;
    const attemptSequence = item.attempt_sequence;
    if (
      typeof attemptCount === "number" &&
      attemptCount > 1 &&
      typeof attemptSequence === "number" &&
      attemptSequence >= 1
    ) {
      return `Attempt ${attemptSequence} of ${attemptCount}`;
    }
    return null;
  }

  function appendAttemptSeriesChip(container, item) {
    const label = attemptSeriesLabel(item);
    if (!label) return;
    appendStatusChip(container, label, "info");
  }

  function appendWorkflowStatusChips(container, item) {
    appendStatusChip(
      container,
      item.is_registered ? "Registered" : "Unregistered",
      item.is_registered ? "ok" : "warn"
    );
    if (!item.is_registered) return;

    if (item.scope === "template") {
      appendStatusChip(container, "Template", "neutral");
      return;
    }

    appendStatusChip(
      container,
      item.has_template ? "Has template" : "No template",
      item.has_template ? "ok" : "warn"
    );
    appendStatusChip(
      container,
      item.has_marking ? "Marked" : "Not marked",
      item.has_marking ? "ok" : "warn"
    );
    if (item.has_marking_amendment) {
      appendStatusChip(container, "Amendment", "info");
    }
    if (item.review_status) {
      const status = item.review_status;
      let variant = "warn";
      let label = "Review: not started";
      if (status === "in_progress") {
        variant = "info";
        label = "Review: in progress";
      } else if (status === "completed") {
        variant = "ok";
        label = "Review: completed";
      }
      appendStatusChip(container, label, variant);
    }
  }

  function renderCards(items) {
    const grid = document.getElementById("grid");
    grid.innerHTML = "";
    if (!items.length) {
      grid.innerHTML = '<p class="empty">No files match these filters.</p>';
      return;
    }
    items.forEach((item) => {
      const card = document.createElement("article");
      card.className = "card";
      card.setAttribute("role", "listitem");
      const icon = document.createElement("div");
      icon.className = "icon";
      icon.textContent = "PDF";
      const titleRow = document.createElement("div");
      titleRow.className = "card-title-row";
      const h3 = document.createElement("h3");
      h3.textContent = item.normal_name || item.basename;
      titleRow.appendChild(h3);
      appendAttemptSeriesChip(titleRow, item);
      let markingScoreEl = null;
      const scoreLabel = formatMarkingScore(item);
      if (scoreLabel) {
        markingScoreEl = document.createElement("p");
        markingScoreEl.className = "card-marking-score";
        markingScoreEl.textContent = scoreLabel;
      }
      let completionDateEl = null;
      const completionLabel = formatCalendarDate(item.completion_date);
      if (completionLabel) {
        completionDateEl = document.createElement("p");
        completionDateEl.className = "card-completion-date";
        completionDateEl.textContent = `Completed ${completionLabel}`;
        completionDateEl.title = completionDateTooltip(item);
      }
      let registryDateEl = null;
      const addedLabel = formatRegistryAddedAt(item.registry_added_at);
      if (addedLabel) {
        registryDateEl = document.createElement("p");
        registryDateEl.className = "card-registry-date";
        registryDateEl.textContent = `Registered ${addedLabel}`;
        registryDateEl.title = item.registry_added_at;
      }
      const chips = document.createElement("div");
      chips.className = "chips";
      ["subject", "grade_or_scope", "doc_type", "root_id"].forEach((k) => {
        const v = item[k];
        if (!v || v === "unknown") return;
        const c = document.createElement("span");
        c.className = "chip";
        c.textContent = v;
        chips.appendChild(c);
      });
      const statusChips = document.createElement("div");
      statusChips.className = "status-chips";
      appendWorkflowStatusChips(statusChips, item);
      const actions = document.createElement("div");
      actions.className = "card-actions";
      const rel = relPathForItem(item);
      if (rel) {
        const view = document.createElement("a");
        const q = new URLSearchParams({
          id: item.root_id,
          rel: rel,
        });
        view.href = `${siblingAppBaseUrl(ROOT_BROWSER_PORT)}?${q.toString()}`;
        view.target = "_blank";
        view.textContent = "View PDF";
        actions.appendChild(view);
      }
      const copyBtn = document.createElement("button");
      copyBtn.type = "button";
      copyBtn.textContent = "Copy path";
      copyBtn.addEventListener("click", () => {
        navigator.clipboard.writeText(item.absolute_path);
      });
      actions.appendChild(copyBtn);
      if (item.has_marking) {
        const rw = document.createElement("a");
        if (item.registry_file_id) {
          const q = new URLSearchParams({ attempt_id: item.registry_file_id });
          if (item.student_id) {
            q.set("student_id", item.student_id);
          }
          rw.href = `${siblingAppBaseUrl(REVIEW_WORKSPACE_PORT)}?${q.toString()}`;
        } else {
          console.warn("Review Workspace link missing registry_file_id for marked card", item);
          rw.href = siblingAppBaseUrl(REVIEW_WORKSPACE_PORT);
        }
        rw.target = "_blank";
        rw.textContent = "Review Workspace";
        actions.appendChild(rw);
      }
      card.appendChild(icon);
      card.appendChild(titleRow);
      if (markingScoreEl) card.appendChild(markingScoreEl);
      if (completionDateEl) card.appendChild(completionDateEl);
      if (registryDateEl) card.appendChild(registryDateEl);
      card.appendChild(chips);
      card.appendChild(statusChips);
      card.appendChild(actions);
      grid.appendChild(card);
    });
  }

  function applyFilterOptionsFromMeta(meta) {
    config = mergeFilterMeta(config, meta);
    if (meta.scope_counts) config.scope_counts = meta.scope_counts;
    if (meta.subject_counts) config.subject_counts = meta.subject_counts;
    if (meta.grade_counts) config.grade_counts = meta.grade_counts;
    if (meta.doc_type_counts) config.doc_type_counts = meta.doc_type_counts;
    if (Array.isArray(meta.student_ids)) config.student_ids = meta.student_ids;
    if (meta.student_counts) config.student_counts = meta.student_counts;
    if (Array.isArray(meta.book_names)) config.book_names = meta.book_names;
    if (meta.book_counts) config.book_counts = meta.book_counts;
    if (Array.isArray(meta.root_ids)) config.root_ids = meta.root_ids;
    if (meta.root_counts) config.root_counts = meta.root_counts;
    config.show_is_registered_filter = meta.show_is_registered_filter;
    config.is_registered_options = meta.is_registered_options || [];
    config.is_registered_counts = meta.is_registered_counts || {};
    config.show_has_template_filter = meta.show_has_template_filter;
    config.has_template_options = meta.has_template_options || [];
    config.has_template_counts = meta.has_template_counts || {};
    config.show_has_marking_filter = meta.show_has_marking_filter;
    config.has_marking_options = meta.has_marking_options || [];
    config.has_marking_counts = meta.has_marking_counts || {};
    config.show_review_status_filter = meta.show_review_status_filter;
    config.review_status_options = meta.review_status_options || [];
    config.review_status_counts = meta.review_status_counts || {};
  }

  function coerceStateToFilterOptions(state) {
    const next = { ...state };
    let changed = false;
    const scopes = scopeOptionsFromConfig();
    if (scopes.length === 1 && next.scope !== scopes[0]) {
      next.scope = scopes[0];
      changed = true;
    } else if (
      scopes.length > 1 &&
      next.scope &&
      !scopes.some((s) => s === next.scope)
    ) {
      next.scope = scopes[0] || "completion";
      changed = true;
    }
    if (
      next.is_registered &&
      !(config.is_registered_options || []).includes(next.is_registered)
    ) {
      next.is_registered = "";
      changed = true;
    }
    if (
      next.has_template &&
      !(config.has_template_options || []).includes(next.has_template)
    ) {
      next.has_template = "";
      changed = true;
    }
    if (
      next.has_marking &&
      !(config.has_marking_options || []).includes(next.has_marking)
    ) {
      next.has_marking = "";
      changed = true;
    }
    if (
      next.review_status &&
      !(config.review_status_options || []).includes(next.review_status)
    ) {
      next.review_status = "";
      changed = true;
    }
    if (next.subject.length && (config.subjects || []).length) {
      const filtered = next.subject.filter((value) => (config.subjects || []).includes(value));
      if (filtered.length !== next.subject.length) {
        next.subject = filtered;
        changed = true;
      }
    }
    if (next.grade.length && (config.grades || []).length) {
      const filtered = next.grade.filter((value) => (config.grades || []).includes(value));
      if (filtered.length !== next.grade.length) {
        next.grade = filtered;
        changed = true;
      }
    }
    if (next.doc_type.length && (config.doc_types || []).length) {
      const filtered = next.doc_type.filter((value) => (config.doc_types || []).includes(value));
      if (filtered.length !== next.doc_type.length) {
        next.doc_type = filtered;
        changed = true;
      }
    }
    if (next.doc_type.length !== 1 || next.doc_type[0] !== "book") {
      if (next.book) {
        next.book = "";
        changed = true;
      }
    }
    if (next.student && next.student.includes("@")) {
      const byEmail = (config.students || []).find(
        (s) => s.email && s.email.toLowerCase() === next.student.toLowerCase()
      );
      if (byEmail && byEmail.student_id) {
        next.student = byEmail.student_id;
        changed = true;
      }
    }
    if (
      next.student &&
      !(config.student_ids || []).some((id) => id === next.student)
    ) {
      next.student = "";
      changed = true;
    }
    if (next.book && !(config.book_names || []).some((b) => b === next.book)) {
      next.book = "";
      changed = true;
    }
    const allowedRoots = ["all"].concat(config.root_ids || []);
    if (!next.root_id || !allowedRoots.includes(next.root_id)) {
      next.root_id = defaultRootId();
      changed = true;
    }
    if (changed) syncUrl(next);
    return next;
  }

  function applyFilterVisibility(state, meta) {
    applyFilterOptionsFromMeta(meta);

    let changed = false;
    const next = { ...state };
    if (!meta.show_is_registered_filter && next.is_registered) {
      next.is_registered = "";
      changed = true;
    }
    if (!meta.show_has_template_filter && next.has_template) {
      next.has_template = "";
      changed = true;
    }
    if (!meta.show_has_marking_filter && next.has_marking) {
      next.has_marking = "";
      changed = true;
    }
    if (!meta.show_review_status_filter && next.review_status) {
      next.review_status = "";
      changed = true;
    }
    if (changed) {
      syncUrl(next);
      return next;
    }
    return state;
  }

  async function loadInventory(state) {
    const gen = ++loadGeneration;
    const meta = document.getElementById("meta");
    meta.textContent = "Loading…";
    const q = qsFromState(state);
    const res = await fetch(`/api/inventory?${q}`);
    if (gen !== loadGeneration) return;
    const data = await res.json();
    state = applyFilterVisibility(state, data.meta);
    state = coerceStateToFilterOptions(state);
    let msg = `${data.meta.total_after_filter} shown of ${data.meta.total_in_index} indexed`;
    if (data.meta.unregistered_in_index) {
      msg += ` (${data.meta.unregistered_in_index} unregistered in index)`;
    }
    if (data.meta.index_size_warning) {
      msg += " — large index: narrow filters";
    }
    meta.textContent = msg;
    renderCards(data.items || []);
    buildFilters(state);
  }

  async function init() {
    installFacetClickOutside();
    let state = stateFromUrl();
    document.getElementById("meta").textContent = "Loading…";
    const cfgRes = await fetch(`/api/config?${qsFromState(state)}`);
    config = await cfgRes.json();
    applyFilterOptionsFromMeta(config);
    if (!new URLSearchParams(location.search).has("root_id")) {
      state = { ...state, root_id: defaultRootId() };
    } else if (!state.root_id) {
      state = { ...state, root_id: defaultRootId() };
    }
    config.scopes = scopeOptionsFromConfig();
    config.scope_counts = config.scope_counts || {};
    config.subjects = config.subjects || [];
    config.subject_counts = config.subject_counts || {};
    config.grades = config.grades || [];
    config.grade_counts = config.grade_counts || {};
    config.doc_types = config.doc_types || [];
    config.doc_type_counts = config.doc_type_counts || {};
    config.student_ids = config.student_ids || [];
    config.student_counts = config.student_counts || {};
    config.students = config.students || [];
    config.book_names = config.book_names || [];
    config.book_counts = config.book_counts || {};
    config.is_registered_options = config.is_registered_options || [];
    config.is_registered_counts = config.is_registered_counts || {};
    config.has_template_options = config.has_template_options || [];
    config.has_template_counts = config.has_template_counts || {};
    config.has_marking_options = config.has_marking_options || [];
    config.has_marking_counts = config.has_marking_counts || {};
    config.review_status_counts = config.review_status_counts || {};
    config.root_ids = config.root_ids || [];
    config.root_counts = config.root_counts || {};
    (config.roots || []).forEach((r) => {
      rootsById[r.id] = r.path;
    });
    state = coerceStateToFilterOptions(state);
    buildFilters(state);
    await loadInventory(state);
  }

  init().catch((err) => {
    document.getElementById("meta").textContent = "Failed to load: " + err;
  });
})();
