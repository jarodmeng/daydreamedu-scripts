(function () {
  "use strict";

  const BOOKMARKS_KEY = "root_pdf_browser.bookmarks";
  const SHOW_RAW_KEY = "root_pdf_browser.showRaw";
  const RAW_PREFIX = "_raw_";

  /** @type {Record<string, { id: string, label: string, path: string }>} */
  let rootsById = {};
  /** @type {Array<{ id: string, label: string, path: string }>} */
  let rootsList = [];

  /** Currently opened PDF in the right pane (for left-panel highlight). */
  let currentViewRootId = null;
  let currentViewRel = null;

  function getShowRaw() {
    try {
      return localStorage.getItem(SHOW_RAW_KEY) === "1";
    } catch (e) {
      return false;
    }
  }

  function setShowRaw(on) {
    try {
      localStorage.setItem(SHOW_RAW_KEY, on ? "1" : "0");
    } catch (e) {
      /* ignore */
    }
  }

  function isRawPdfName(name) {
    return typeof name === "string" && name.startsWith(RAW_PREFIX);
  }

  function applyShowRawClass() {
    document.body.classList.toggle("hide-raw", !getShowRaw());
  }

  function joinRel(parent, name) {
    if (!parent) return name;
    return parent.replace(/\/+$/, "") + "/" + name;
  }

  function fullPathFromRootPath(rootPath, rel) {
    if (!rootPath) {
      return String(rel || "");
    }
    const sep = String(rootPath).indexOf("\\") >= 0 ? "\\" : "/";
    const base = String(rootPath).replace(/[/\\]+$/, "");
    const parts = String(rel || "")
      .split(/[/\\]+/)
      .filter(function (p) {
        return p && p !== ".";
      });
    if (!parts.length) {
      return base;
    }
    return base + sep + parts.join(sep);
  }

  function bookmarkKey(id, rel) {
    return id + "\n" + rel;
  }

  function getBookmarks() {
    try {
      const raw = localStorage.getItem(BOOKMARKS_KEY);
      if (!raw) {
        return [];
      }
      const arr = JSON.parse(raw);
      if (!Array.isArray(arr)) {
        return [];
      }
      const seen = new Set();
      const out = [];
      arr.forEach(function (item) {
        if (!item || typeof item.id !== "string" || typeof item.rel !== "string") {
          return;
        }
        const k = bookmarkKey(item.id, item.rel);
        if (seen.has(k)) {
          return;
        }
        seen.add(k);
        out.push({ id: item.id, rel: item.rel });
      });
      return out;
    } catch (e) {
      return [];
    }
  }

  function setBookmarks(items) {
    localStorage.setItem(BOOKMARKS_KEY, JSON.stringify(items));
  }

  function isBookmarked(id, rel) {
    const k = bookmarkKey(id, rel);
    return getBookmarks().some(function (b) {
      return bookmarkKey(b.id, b.rel) === k;
    });
  }

  function toggleBookmark(id, rel) {
    const list = getBookmarks();
    const k = bookmarkKey(id, rel);
    const idx = list.findIndex(function (b) {
      return bookmarkKey(b.id, b.rel) === k;
    });
    if (idx >= 0) {
      list.splice(idx, 1);
    } else {
      list.push({ id: id, rel: rel });
    }
    setBookmarks(list);
    onBookmarksChanged();
  }

  function removeBookmark(id, rel) {
    const k = bookmarkKey(id, rel);
    const list = getBookmarks().filter(function (b) {
      return bookmarkKey(b.id, b.rel) !== k;
    });
    setBookmarks(list);
    onBookmarksChanged();
  }

  function clearAllBookmarks() {
    if (!getBookmarks().length) {
      return;
    }
    if (!window.confirm("Remove all bookmarks?")) {
      return;
    }
    setBookmarks([]);
    onBookmarksChanged();
  }

  function absolutePathForBookmark(b) {
    const root = rootsById[b.id];
    if (!root) {
      return null;
    }
    return fullPathFromRootPath(root.path, b.rel);
  }

  function syncCurrentViewHighlight() {
    document.querySelectorAll(".pdf-row.is-current-view").forEach(function (el) {
      el.classList.remove("is-current-view");
    });
    document.querySelectorAll("#bookmarks-list li.is-current-view").forEach(function (el) {
      el.classList.remove("is-current-view");
    });
    document.querySelectorAll(".pdf-link[aria-current='page']").forEach(function (el) {
      el.removeAttribute("aria-current");
    });
    document.querySelectorAll(".bm-open[aria-current='page']").forEach(function (el) {
      el.removeAttribute("aria-current");
    });

    if (!currentViewRootId || currentViewRel == null) {
      return;
    }

    let scrolled = false;

    document.querySelectorAll(".pdf-row").forEach(function (row) {
      if (row.getAttribute("data-root-id") === currentViewRootId && row.getAttribute("data-rel") === currentViewRel) {
        row.classList.add("is-current-view");
        const link = row.querySelector(".pdf-link");
        if (link) {
          link.setAttribute("aria-current", "page");
        }
        if (!scrolled) {
          try {
            row.scrollIntoView({ block: "nearest", inline: "nearest" });
          } catch (e) {
            /* ignore */
          }
          scrolled = true;
        }
      }
    });

    document.querySelectorAll("#bookmarks-list li.bm-item").forEach(function (li) {
      if (li.getAttribute("data-root-id") === currentViewRootId && li.getAttribute("data-rel") === currentViewRel) {
        li.classList.add("is-current-view");
        const openBtn = li.querySelector(".bm-open");
        if (openBtn) {
          openBtn.setAttribute("aria-current", "page");
        }
        if (!scrolled) {
          try {
            li.scrollIntoView({ block: "nearest", inline: "nearest" });
          } catch (e) {
            /* ignore */
          }
          scrolled = true;
        }
      }
    });
  }

  function syncBookmarkTogglesInTree() {
    document.querySelectorAll(".bookmark-toggle").forEach(function (el) {
      const id = el.getAttribute("data-root-id");
      const rel = el.getAttribute("data-rel");
      if (!id || rel == null) {
        return;
      }
      const on = isBookmarked(id, rel);
      el.setAttribute("aria-pressed", on ? "true" : "false");
      el.textContent = on ? "\u2605" : "\u2606";
      el.setAttribute("aria-label", on ? "Remove bookmark" : "Add bookmark");
    });
  }

  function renderBookmarksPanel() {
    const listEl = document.getElementById("bookmarks-list");
    const emptyEl = document.getElementById("bookmarks-empty");
    const exportBtn = document.getElementById("bookmarks-export");
    const clearBtn = document.getElementById("bookmarks-clear");
    if (!listEl || !emptyEl || !exportBtn || !clearBtn) {
      return;
    }

    const items = getBookmarks().slice().sort(function (a, b) {
      const pa = absolutePathForBookmark(a) || a.rel;
      const pb = absolutePathForBookmark(b) || b.rel;
      return pa.localeCompare(pb, undefined, { sensitivity: "base" });
    });

    listEl.innerHTML = "";
    if (items.length === 0) {
      emptyEl.hidden = false;
      listEl.hidden = true;
      exportBtn.disabled = true;
      clearBtn.disabled = true;
      syncBookmarkTogglesInTree();
      syncCurrentViewHighlight();
      return;
    }

    emptyEl.hidden = true;
    listEl.hidden = false;
    exportBtn.disabled = false;
    clearBtn.disabled = false;

    items.forEach(function (b) {
      const root = rootsById[b.id];
      const label = root ? root.label : b.id;
      const full = absolutePathForBookmark(b);

      const li = document.createElement("li");
      li.className = "bm-item";
      li.setAttribute("data-root-id", b.id);
      li.setAttribute("data-rel", b.rel);
      const body = document.createElement("div");
      body.className = "bm-body";

      const openBtn = document.createElement("button");
      openBtn.type = "button";
      openBtn.className = "bm-open";
      openBtn.textContent = label + " — " + b.rel.split("/").pop();
      openBtn.title = full || b.rel;
      openBtn.addEventListener("click", function () {
        openPdf(b.id, b.rel);
      });

      const meta = document.createElement("span");
      meta.className = "bm-meta";
      meta.textContent = full || (root ? fullPathFromRootPath(root.path, b.rel) : b.rel);

      body.appendChild(openBtn);
      body.appendChild(meta);

      const rm = document.createElement("button");
      rm.type = "button";
      rm.className = "bm-remove";
      rm.setAttribute("aria-label", "Remove bookmark");
      rm.textContent = "\u00d7";
      rm.addEventListener("click", function () {
        removeBookmark(b.id, b.rel);
      });

      li.appendChild(body);
      li.appendChild(rm);
      listEl.appendChild(li);
    });

    syncBookmarkTogglesInTree();
    syncCurrentViewHighlight();
  }

  function onBookmarksChanged() {
    renderBookmarksPanel();
  }

  function exportBookmarkPaths() {
    const items = getBookmarks();
    if (!items.length) {
      return;
    }
    const lines = [];
    const missing = [];
    items.forEach(function (b) {
      const abs = absolutePathForBookmark(b);
      if (abs) {
        lines.push(abs);
      } else {
        missing.push(b.id + ": " + b.rel);
      }
    });
    lines.sort(function (a, b) {
      return a.localeCompare(b, undefined, { sensitivity: "base" });
    });
    let body = lines.join("\n") + (lines.length ? "\n" : "");
    if (missing.length) {
      body +=
        (body ? "\n" : "") +
        "# Unresolved (root not loaded or unknown id):\n" +
        missing.join("\n") +
        "\n";
    }
    const blob = new Blob([body], { type: "text/plain;charset=utf-8" });
    const a = document.createElement("a");
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
    a.href = URL.createObjectURL(blob);
    a.download = "bookmarked-pdf-paths-" + stamp + ".txt";
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
  }

  function wireBookmarksToolbar() {
    const exportBtn = document.getElementById("bookmarks-export");
    const clearBtn = document.getElementById("bookmarks-clear");
    if (exportBtn && !exportBtn.dataset.wired) {
      exportBtn.dataset.wired = "1";
      exportBtn.addEventListener("click", exportBookmarkPaths);
    }
    if (clearBtn && !clearBtn.dataset.wired) {
      clearBtn.dataset.wired = "1";
      clearBtn.addEventListener("click", clearAllBookmarks);
    }
  }

  async function fetchList(rootId, rel) {
    const q = new URLSearchParams({ id: rootId, rel: rel || "" });
    const res = await fetch("/api/list?" + q.toString());
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || res.statusText);
    }
    return res.json();
  }

  function appendScanRootBadge(summaryEl, isScanRoot) {
    if (!summaryEl || isScanRoot !== true) {
      return;
    }
    if (summaryEl.querySelector(".scan-root-badge")) {
      return;
    }
    const badge = document.createElement("span");
    badge.className = "scan-root-badge";
    badge.textContent = "📁";
    summaryEl.appendChild(document.createTextNode(" "));
    summaryEl.appendChild(badge);
  }

  function appendPdfRegistrationBadge(buttonEl, isRegistered) {
    if (!buttonEl || isRegistered == null) {
      return;
    }
    const badge = document.createElement("span");
    badge.className = isRegistered ? "pdf-reg-badge is-registered" : "pdf-reg-badge is-unregistered";
    badge.textContent = isRegistered ? "📄" : "⚠️";
    buttonEl.appendChild(document.createTextNode(" "));
    buttonEl.appendChild(badge);
  }

  /** Fragment hint for the browser’s built-in PDF viewer (PDFium in Chrome/Edge). */
  const PDF_VIEWER_FRAGMENT = "#page=1&view=Fit";

  let pdfOpenGeneration = 0;

  function focusPdfFrame(frame) {
    if (!frame || frame.hidden) {
      return;
    }
    try {
      frame.scrollIntoView({ block: "nearest", inline: "nearest" });
    } catch (e) {
      /* ignore */
    }
    try {
      frame.focus({ preventScroll: true });
    } catch (e) {
      frame.focus();
    }
    try {
      const w = frame.contentWindow;
      if (w) {
        w.focus();
      }
    } catch (e) {
      /* Opaque PDF inner document in some browsers */
    }
  }

  function schedulePdfViewerFocus(frame, generation) {
    function tick() {
      if (generation !== pdfOpenGeneration) {
        return;
      }
      focusPdfFrame(frame);
    }
    tick();
    window.setTimeout(tick, 80);
    window.setTimeout(tick, 250);
  }

  function syncOpenPdfUrl(rootId, rel) {
    try {
      const u = new URL(window.location.href);
      u.searchParams.set("id", rootId);
      u.searchParams.set("rel", rel);
      history.replaceState(null, "", u.pathname + "?" + u.searchParams.toString());
    } catch (e) {
      /* ignore */
    }
  }

  function parseDeepLinkFromUrl() {
    try {
      const p = new URLSearchParams(window.location.search);
      const id = p.get("id");
      const rel = p.get("rel");
      if (!id || rel == null || rel === "") {
        return null;
      }
      return { id: id, rel: rel };
    } catch (e) {
      return null;
    }
  }

  function rootBlockEl(rootId) {
    return document.querySelector(
      '.root-block[data-root-id="' + CSS.escape(rootId) + '"]'
    );
  }

  function waitUntil(deadlineMs, predicate) {
    const deadline = Date.now() + (deadlineMs || 30000);
    return new Promise(function (resolve) {
      (function tick() {
        if (predicate()) {
          resolve(true);
          return;
        }
        if (Date.now() > deadline) {
          resolve(false);
          return;
        }
        setTimeout(tick, 40);
      })();
    });
  }

  function folderDetailsEl(rootId, folderRel) {
    const block = rootBlockEl(rootId);
    if (!block) {
      return null;
    }
    if (folderRel === "") {
      return block.querySelector("[data-tree-host]");
    }
    return block.querySelector('[data-folder-rel="' + CSS.escape(folderRel) + '"]');
  }

  function startFolderLoad(details, rootId) {
    if (!details || details.dataset.treeLoaded === "1" || details.dataset.treeLoading === "1") {
      return;
    }
    const childRel = details.getAttribute("data-folder-rel") || "";
    const childHost =
      details.getAttribute("data-tree-host") === "1"
        ? details
        : details.querySelector(".tree-folder-children");
    if (!childHost) {
      return;
    }
    details.dataset.treeLoading = "1";
    renderFolder(rootId, childRel, childHost, 0);
  }

  function ensureFolderExpanded(rootId, folderRel) {
    if (folderRel === "") {
      const host = folderDetailsEl(rootId, "");
      if (!host) {
        return waitUntil(30000, function () {
          return folderDetailsEl(rootId, "") !== null;
        }).then(function () {
          const h = folderDetailsEl(rootId, "");
          return h
            ? waitUntil(30000, function () {
                return h.dataset.treeLoaded === "1";
              })
            : false;
        });
      }
      return waitUntil(30000, function () {
        return host.dataset.treeLoaded === "1";
      });
    }

    return waitUntil(30000, function () {
      return folderDetailsEl(rootId, folderRel) !== null;
    }).then(function (found) {
      if (!found) {
        return false;
      }
      const details = folderDetailsEl(rootId, folderRel);
      if (!details) {
        return false;
      }
      if (!details.open) {
        details.open = true;
      } else if (details.dataset.treeLoaded !== "1") {
        startFolderLoad(details, rootId);
      }
      return waitUntil(30000, function () {
        return details.dataset.treeLoaded === "1";
      });
    });
  }

  function scrollPdfRowIntoView(rootId, rel) {
    const row = document.querySelector(
      '.pdf-row[data-root-id="' +
        CSS.escape(rootId) +
        '"][data-rel="' +
        CSS.escape(rel) +
        '"]'
    );
    if (!row) {
      return;
    }
    row.scrollIntoView({ block: "nearest", inline: "nearest" });
    const details = row.closest("details");
    if (details && !details.open) {
      details.open = true;
    }
  }

  function applyDeepLink() {
    const link = parseDeepLinkFromUrl();
    if (!link || !rootsById[link.id]) {
      return Promise.resolve();
    }
    const parts = String(link.rel).split("/").filter(function (p) {
      return p && p !== ".";
    });
    if (!parts.length) {
      return Promise.resolve();
    }
    const dirs = parts.slice(0, -1);
    const block = rootBlockEl(link.id);
    if (block) {
      block.scrollIntoView({ block: "nearest", inline: "nearest" });
    }
    let chain = ensureFolderExpanded(link.id, "");
    let accum = "";
    dirs.forEach(function (name) {
      accum = joinRel(accum, name);
      const folderRel = accum;
      chain = chain.then(function () {
        return ensureFolderExpanded(link.id, folderRel);
      });
    });
    return chain.then(function () {
      openPdf(link.id, link.rel);
      window.setTimeout(function () {
        scrollPdfRowIntoView(link.id, link.rel);
        syncCurrentViewHighlight();
      }, 80);
    });
  }

  function openPdf(rootId, rel) {
    currentViewRootId = rootId;
    currentViewRel = rel;
    syncCurrentViewHighlight();
    syncOpenPdfUrl(rootId, rel);

    const empty = document.getElementById("empty");
    const frame = document.getElementById("pdf-frame");
    const q = new URLSearchParams({ id: rootId, rel: rel });
    const url = "/api/pdf?" + q.toString() + PDF_VIEWER_FRAGMENT;
    const generation = ++pdfOpenGeneration;

    frame.addEventListener(
      "load",
      function onPdfLoad() {
        if (generation !== pdfOpenGeneration) {
          return;
        }
        schedulePdfViewerFocus(frame, generation);
      },
      { once: true }
    );

    frame.src = url;
    frame.hidden = false;
    empty.hidden = true;
    schedulePdfViewerFocus(frame, generation);
  }

  function renderFolder(rootId, rel, container, depth) {
    container.replaceChildren();
    const ul = document.createElement("ul");
    ul.className = "tree";
    container.appendChild(ul);

    const placeholder = document.createElement("li");
    placeholder.className = "load-error";
    placeholder.textContent = "Loading…";
    ul.appendChild(placeholder);

    fetchList(rootId, rel)
      .then(function (data) {
        ul.removeChild(placeholder);
        const dirs = data.dirs || [];
        const pdfs = data.pdfs || [];
        const leafScanRoot = data.leafScanRoot === true;
        const dirScanRoots = data.dirScanRoots || {};
        const pdfRegistration = data.pdfRegistration || {};
        let rawCount = 0;
        pdfs.forEach(function (n) {
          if (isRawPdfName(n)) {
            rawCount += 1;
          }
        });
        if (dirs.length === 0 && pdfs.length === 0) {
          const li = document.createElement("li");
          li.className = "empty-folder";
          li.textContent = "(empty)";
          ul.appendChild(li);
          return;
        }
        dirs.forEach(function (name) {
          const li = document.createElement("li");
          const details = document.createElement("details");
          const childRel = joinRel(rel, name);
          details.setAttribute("data-folder-rel", childRel);
          const summary = document.createElement("summary");
          summary.textContent = name;
          appendScanRootBadge(summary, dirScanRoots[name] === true);
          details.appendChild(summary);
          const childHost = document.createElement("div");
          childHost.className = "tree-folder-children";
          details.appendChild(childHost);
          details.addEventListener("toggle", function () {
            if (!details.open) {
              return;
            }
            startFolderLoad(details, rootId);
          });
          li.appendChild(details);
          ul.appendChild(li);
        });
        pdfs.forEach(function (name) {
          const fullRel = joinRel(rel, name);
          const li = document.createElement("li");
          if (isRawPdfName(name)) {
            li.classList.add("is-raw-row");
          }
          const row = document.createElement("div");
          row.className = "pdf-row";
          row.setAttribute("data-root-id", rootId);
          row.setAttribute("data-rel", fullRel);

          const bm = document.createElement("button");
          bm.type = "button";
          bm.className = "bookmark-toggle";
          bm.setAttribute("data-root-id", rootId);
          bm.setAttribute("data-rel", fullRel);
          bm.addEventListener("click", function (e) {
            e.stopPropagation();
            e.preventDefault();
            toggleBookmark(rootId, fullRel);
          });

          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "pdf-link";
          btn.textContent = name;
          appendPdfRegistrationBadge(btn, pdfRegistration[name]);
          btn.addEventListener("click", function () {
            openPdf(rootId, fullRel);
          });

          row.appendChild(bm);
          row.appendChild(btn);
          li.appendChild(row);
          ul.appendChild(li);

          const on = isBookmarked(rootId, fullRel);
          bm.setAttribute("aria-pressed", on ? "true" : "false");
          bm.textContent = on ? "\u2605" : "\u2606";
          bm.setAttribute("aria-label", on ? "Remove bookmark" : "Add bookmark");
        });
        if (leafScanRoot) {
          const parent = container && container.parentElement;
          if (parent) {
            const summaryEl = parent.querySelector(":scope > summary");
            appendScanRootBadge(summaryEl, true);
          }
        }
        if (rawCount > 0) {
          const li = document.createElement("li");
          li.className = "raw-hidden-hint";
          li.textContent =
            rawCount + " _raw_ file" + (rawCount === 1 ? "" : "s") + " hidden";
          ul.appendChild(li);
        }
        const parentDetails = container && container.parentElement;
        if (parentDetails && parentDetails.tagName === "DETAILS") {
          parentDetails.dataset.treeLoaded = "1";
          delete parentDetails.dataset.treeLoading;
        }
        if (container && container.getAttribute("data-tree-host") === "1") {
          container.dataset.treeLoaded = "1";
          delete container.dataset.treeLoading;
        }
        syncCurrentViewHighlight();
      })
      .catch(function (err) {
        placeholder.textContent = "Failed to load: " + (err && err.message ? err.message : String(err));
        const parentDetails = container && container.parentElement;
        if (parentDetails && parentDetails.tagName === "DETAILS") {
          delete parentDetails.dataset.treeLoading;
        }
        if (container && container.getAttribute("data-tree-host") === "1") {
          delete container.dataset.treeLoading;
        }
      });
  }

  function renderRootBlock(root) {
    const block = document.createElement("div");
    block.className = "root-block";
    block.setAttribute("data-root-id", root.id);
    const h2 = document.createElement("h2");
    h2.textContent = root.label;
    block.appendChild(h2);
    const pathEl = document.createElement("div");
    pathEl.className = "root-path";
    pathEl.textContent = root.path;
    block.appendChild(pathEl);
    const treeHost = document.createElement("div");
    treeHost.className = "tree-folder-children";
    treeHost.setAttribute("data-tree-host", "1");
    block.appendChild(treeHost);
    renderFolder(root.id, "", treeHost, 0);
    return block;
  }

  function setupSidebarResize() {
    const layout = document.getElementById("layout");
    const splitter = document.getElementById("splitter");
    const sidebar = document.getElementById("sidebar");
    if (!layout || !splitter || !sidebar) {
      return;
    }

    const KEY = "root_pdf_browser.sidebarWidthPx";

    function maxSidebar() {
      return Math.min(920, Math.floor(window.innerWidth * 0.9));
    }

    function clamp(w) {
      var min = 200;
      return Math.round(Math.min(maxSidebar(), Math.max(min, w)));
    }

    var stored = localStorage.getItem(KEY);
    if (stored) {
      var n = parseInt(stored, 10);
      if (!Number.isNaN(n)) {
        layout.style.setProperty("--sidebar-width", clamp(n) + "px");
      }
    }

    var dragging = false;

    function applyWidth(px) {
      layout.style.setProperty("--sidebar-width", clamp(px) + "px");
    }

    splitter.addEventListener("mousedown", function (e) {
      if (e.button !== 0) {
        return;
      }
      e.preventDefault();
      dragging = true;
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    });

    document.addEventListener("mousemove", function (e) {
      if (!dragging) {
        return;
      }
      applyWidth(e.clientX);
    });

    document.addEventListener("mouseup", function () {
      if (!dragging) {
        return;
      }
      dragging = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      localStorage.setItem(KEY, String(Math.round(sidebar.getBoundingClientRect().width)));
    });

    splitter.addEventListener("keydown", function (e) {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") {
        return;
      }
      e.preventDefault();
      var rect = sidebar.getBoundingClientRect();
      var step = e.shiftKey ? 48 : 16;
      var delta = e.key === "ArrowRight" ? step : -step;
      applyWidth(rect.width + delta);
      localStorage.setItem(KEY, String(Math.round(sidebar.getBoundingClientRect().width)));
    });

    window.addEventListener("resize", function () {
      applyWidth(sidebar.getBoundingClientRect().width);
    });
  }

  function renderAllRoots() {
    const container = document.getElementById("roots-container");
    if (!container) {
      return;
    }
    container.innerHTML = "";
    if (rootsList.length === 0) {
      container.textContent = "No roots available.";
      renderBookmarksPanel();
      syncCurrentViewHighlight();
      return;
    }
    rootsList.forEach(function (r) {
      container.appendChild(renderRootBlock(r));
    });
    renderBookmarksPanel();
  }

  function wireShowRawToggle() {
    const cb = document.getElementById("show-raw-toggle");
    if (!cb || cb.dataset.wired) {
      return;
    }
    cb.dataset.wired = "1";
    cb.checked = getShowRaw();
    cb.addEventListener("change", function () {
      setShowRaw(cb.checked);
      applyShowRawClass();
    });
  }

  function boot() {
    applyShowRawClass();
    wireBookmarksToolbar();
    wireShowRawToggle();
    renderBookmarksPanel();
    setupSidebarResize();
    init();
  }

  function init() {
    fetch("/api/config")
      .then(function (res) {
        return res.json();
      })
      .then(function (cfg) {
        const loading = document.getElementById("roots-loading");
        const container = document.getElementById("roots-container");
        loading.hidden = true;
        container.hidden = false;
        const roots = cfg.roots || [];
        rootsById = {};
        roots.forEach(function (r) {
          rootsById[r.id] = { id: r.id, label: r.label, path: r.path };
        });
        rootsList = roots.map(function (r) {
          return { id: r.id, label: r.label, path: r.path };
        });
        renderAllRoots();
        applyDeepLink().catch(function () {
          /* tree expansion best-effort */
        });
      })
      .catch(function (err) {
        document.getElementById("roots-loading").textContent =
          "Could not load /api/config: " + (err && err.message ? err.message : String(err));
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
