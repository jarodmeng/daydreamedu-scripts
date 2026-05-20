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

  function qsFromState(state) {
    const p = new URLSearchParams();
    if (state.scope && state.scope !== "completion") p.set("scope", state.scope);
    const defaultRoot = defaultRootId();
    if (state.root_id && state.root_id !== defaultRoot) p.set("root_id", state.root_id);
    if (state.student) p.set("student", state.student);
    if (state.subject && state.subject !== "all") p.set("subject", state.subject);
    if (state.grade && state.grade !== "all") p.set("grade", state.grade);
    if (state.doc_type && state.doc_type !== "all") p.set("doc_type", state.doc_type);
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
    return p.toString();
  }

  function defaultFilterState() {
    return {
      scope: "completion",
      root_id: defaultRootId(),
      student: "",
      subject: "all",
      grade: "all",
      doc_type: "all",
      book: "",
      is_registered: "",
      has_template: "",
      has_marking: "",
      review_status: "",
    };
  }

  function stateFromUrl() {
    const p = new URLSearchParams(location.search);
    return {
      scope: p.get("scope") || "completion",
      root_id: p.get("root_id") || "",
      student: p.get("student") || localStorage.getItem(STORAGE_KEY) || "",
      subject: p.get("subject") || "all",
      grade: p.get("grade") || "all",
      doc_type: p.get("doc_type") || "all",
      book: p.get("book") || "",
      is_registered: p.get("is_registered") || "",
      has_template: p.get("has_template") || "",
      has_marking: p.get("has_marking") || "",
      review_status: p.get("review_status") || "",
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

  function buildFilters(state) {
    const el = document.getElementById("filters");
    el.innerHTML = "";
    const templateMode = state.scope === "template";

    function addSelect(id, label, options, value) {
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
      if (id === "scope" || id === "doc_type") {
        sel.addEventListener("change", onDraftLayoutChange);
      }
      lab.appendChild(title);
      lab.appendChild(sel);
      el.appendChild(lab);
    }

    const scopes = config.scopes || [];
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
    addSelect(
      "subject",
      "Subject",
      [{ value: "all", label: labelWithCount("All", "all", subjectCounts) }].concat(
        (config.subjects || []).map((s) => ({
          value: s,
          label: labelWithCount(s, s, subjectCounts),
        }))
      ),
      state.subject
    );
    addSelect(
      "grade",
      "Grade",
      [{ value: "all", label: labelWithCount("All", "all", gradeCounts) }].concat(
        (config.grades || []).map((g) => ({
          value: g,
          label: labelWithCount(g, g, gradeCounts),
        }))
      ),
      state.grade
    );
    addSelect(
      "doc_type",
      "Type",
      [{ value: "all", label: labelWithCount("All", "all", docTypeCounts) }].concat(
        (config.doc_types || []).map((t) => ({
          value: t,
          label: labelWithCount(
            t.charAt(0).toUpperCase() + t.slice(1),
            t,
            docTypeCounts
          ),
        }))
      ),
      state.doc_type
    );

    if (state.doc_type === "book") {
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
    el.appendChild(actions);
  }

  async function onDraftLayoutChange() {
    const state = readStateFromDom();
    try {
      const cfgRes = await fetch(`/api/config?${qsFromState(state)}`);
      const data = await cfgRes.json();
      applyFilterOptionsFromMeta(data);
    } catch {
      /* keep prior options */
    }
    buildFilters(state);
  }

  function readStateFromDom() {
    const scope = document.getElementById("scope")?.value || "completion";
    const root_id =
      document.getElementById("root_id")?.value || defaultRootId();
    const student = document.getElementById("student")?.value || "";
    const subject = document.getElementById("subject")?.value || "all";
    const grade = document.getElementById("grade")?.value || "all";
    const doc_type = document.getElementById("doc_type")?.value || "all";
    const book = document.getElementById("book")?.value || "";
    const is_registered = document.getElementById("is_registered")?.value || "";
    const has_template = document.getElementById("has_template")?.value || "";
    const has_marking = document.getElementById("has_marking")?.value || "";
    const review_status = document.getElementById("review_status")?.value || "";
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
      card.appendChild(chips);
      card.appendChild(statusChips);
      card.appendChild(actions);
      grid.appendChild(card);
    });
  }

  function applyFilterOptionsFromMeta(meta) {
    if (Array.isArray(meta.scopes)) config.scopes = meta.scopes;
    if (meta.scope_counts) config.scope_counts = meta.scope_counts;
    if (Array.isArray(meta.subjects)) config.subjects = meta.subjects;
    if (meta.subject_counts) config.subject_counts = meta.subject_counts;
    if (Array.isArray(meta.grades)) config.grades = meta.grades;
    if (meta.grade_counts) config.grade_counts = meta.grade_counts;
    if (Array.isArray(meta.doc_types)) config.doc_types = meta.doc_types;
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
    const scopes = config.scopes || [];
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
    if (
      next.subject !== "all" &&
      !(config.subjects || []).some((s) => s === next.subject)
    ) {
      next.subject = "all";
      changed = true;
    }
    if (next.grade !== "all" && !(config.grades || []).some((g) => g === next.grade)) {
      next.grade = "all";
      changed = true;
    }
    if (
      next.doc_type !== "all" &&
      !(config.doc_types || []).some((t) => t === next.doc_type)
    ) {
      next.doc_type = "all";
      next.book = "";
      changed = true;
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
    config.scopes = config.scopes || ["completion", "template"];
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
