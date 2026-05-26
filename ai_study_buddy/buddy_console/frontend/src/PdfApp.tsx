import { useEffect, useMemo, useState } from "react";

type RootOption = {
  id: string;
  label: string;
  path: string;
};

type PdfBrowserConfig = {
  roots: RootOption[];
};

type PdfListResponse = {
  dirs: string[];
  pdfs: string[];
  pdfRegistration: Record<string, boolean | null>;
  registryAvailable: boolean;
  currentRel: string;
};

type ListingState = {
  status: "idle" | "loading" | "loaded" | "error";
  data: PdfListResponse | null;
  error: string | null;
};

type Bookmark = {
  id: string;
  rel: string;
};

const SHOW_RAW_KEY = "buddy_console.pdf.showRaw";
const BOOKMARKS_KEY = "buddy_console.pdf.bookmarks";
const SIDEBAR_WIDTH_KEY = "buddy_console.pdf.sidebarWidthPx";
const RAW_PREFIX = "_raw_";
const PDF_VIEWER_FRAGMENT = "#page=1&view=Fit";

function queryParam(key: string): string {
  return new URLSearchParams(window.location.search).get(key)?.trim() || "";
}

function buildPdfSrc(rootId: string, rel: string): string {
  return `/api/pdf?id=${encodeURIComponent(rootId)}&rel=${encodeURIComponent(rel)}${PDF_VIEWER_FRAGMENT}`;
}

function joinRel(parent: string, name: string): string {
  if (!parent) return name;
  return `${parent.replace(/\/+$/, "")}/${name}`;
}

function replacePdfUrl(rootId: string, rel: string): void {
  const params = new URLSearchParams();
  params.set("id", rootId);
  if (rel) params.set("rel", rel);
  window.history.replaceState(null, "", `/pdf?${params.toString()}`);
}

function keyFor(rootId: string, rel: string): string {
  return `${rootId}\n${rel}`;
}

function readShowRawPreference(): boolean {
  try {
    return window.localStorage.getItem(SHOW_RAW_KEY) === "1";
  } catch {
    return false;
  }
}

function readBookmarks(): Bookmark[] {
  try {
    const raw = window.localStorage.getItem(BOOKMARKS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    const seen = new Set<string>();
    return parsed
      .filter((item): item is Bookmark => Boolean(item?.id && typeof item.id === "string" && typeof item.rel === "string"))
      .filter((item) => {
        const key = keyFor(item.id, item.rel);
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
  } catch {
    return [];
  }
}

function readSidebarWidth(): number {
  try {
    const raw = window.localStorage.getItem(SIDEBAR_WIDTH_KEY);
    const value = raw ? parseInt(raw, 10) : NaN;
    if (Number.isFinite(value)) return value;
  } catch {
    // Ignore localStorage failures.
  }
  return 320;
}

function clampSidebarWidth(width: number): number {
  const min = 200;
  const max = Math.min(920, Math.floor(window.innerWidth * 0.9));
  return Math.round(Math.min(max, Math.max(min, width)));
}

function isRawPdfName(name: string): boolean {
  return name.startsWith(RAW_PREFIX) || name.startsWith("raw_");
}

function fullPathFromRootPath(rootPath: string, rel: string): string {
  if (!rootPath) return rel;
  const sep = rootPath.includes("\\") ? "\\" : "/";
  const base = rootPath.replace(/[/\\]+$/, "");
  const parts = rel.split("/").filter((part) => part && part !== ".");
  return parts.length ? `${base}${sep}${parts.join(sep)}` : base;
}

function exportBookmarkPaths(bookmarks: Bookmark[], rootsById: Record<string, RootOption>): void {
  if (!bookmarks.length) return;
  const lines = bookmarks
    .map((bookmark) => {
      const root = rootsById[bookmark.id];
      return root ? fullPathFromRootPath(root.path, bookmark.rel) : `${bookmark.id}: ${bookmark.rel}`;
    })
    .sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
  const blob = new Blob([`${lines.join("\n")}\n`], { type: "text/plain;charset=utf-8" });
  const href = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
  anchor.href = href;
  anchor.download = `bookmarked-pdf-paths-${stamp}.txt`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(href);
}

function PdfTree({
  root,
  rel,
  currentRootId,
  currentRel,
  listings,
  ensureListing,
  openFolders,
  setFolderOpen,
  showRaw,
  bookmarks,
  onToggleBookmark,
  onOpenPdf,
}: {
  root: RootOption;
  rel: string;
  currentRootId: string;
  currentRel: string;
  listings: Record<string, ListingState>;
  ensureListing: (rootId: string, rel: string) => void;
  openFolders: Set<string>;
  setFolderOpen: (rootId: string, rel: string, open: boolean) => void;
  showRaw: boolean;
  bookmarks: Bookmark[];
  onToggleBookmark: (rootId: string, rel: string) => void;
  onOpenPdf: (rootId: string, rel: string) => void;
}) {
  const cacheKey = keyFor(root.id, rel);
  const listing = listings[cacheKey];

  useEffect(() => {
    ensureListing(root.id, rel);
  }, [ensureListing, rel, root.id]);

  const dirs = listing?.data?.dirs || [];
  const visiblePdfs = useMemo(() => {
    const pdfs = listing?.data?.pdfs || [];
    return showRaw ? pdfs : pdfs.filter((pdf) => !isRawPdfName(pdf));
  }, [listing?.data?.pdfs, showRaw]);
  const hiddenRawCount = useMemo(() => {
    if (showRaw) return 0;
    return (listing?.data?.pdfs || []).filter((pdf) => isRawPdfName(pdf)).length;
  }, [listing?.data?.pdfs, showRaw]);
  const bookmarksSet = useMemo(
    () => new Set(bookmarks.map((bookmark) => keyFor(bookmark.id, bookmark.rel))),
    [bookmarks],
  );

  if (!listing || listing.status === "idle" || listing.status === "loading") {
    return (
      <ul className="tree">
        <li className="load-error">Loading...</li>
      </ul>
    );
  }

  if (listing.status === "error") {
    return (
      <ul className="tree">
        <li className="load-error">Failed to load: {listing.error}</li>
      </ul>
    );
  }

  return (
    <ul className="tree">
      {dirs.map((dir) => {
        const childRel = joinRel(rel, dir);
        const isOpen = openFolders.has(keyFor(root.id, childRel));
        return (
          <li key={childRel}>
            <details
              open={isOpen}
              data-folder-rel={childRel}
              onToggle={(event) => {
                const target = event.currentTarget;
                setFolderOpen(root.id, childRel, target.open);
              }}
            >
              <summary>{dir}</summary>
              {isOpen ? (
                <div className="tree-folder-children">
                  <PdfTree
                    root={root}
                    rel={childRel}
                    currentRootId={currentRootId}
                    currentRel={currentRel}
                    listings={listings}
                    ensureListing={ensureListing}
                    openFolders={openFolders}
                    setFolderOpen={setFolderOpen}
                    showRaw={showRaw}
                    bookmarks={bookmarks}
                    onToggleBookmark={onToggleBookmark}
                    onOpenPdf={onOpenPdf}
                  />
                </div>
              ) : null}
            </details>
          </li>
        );
      })}

      {visiblePdfs.map((pdf) => {
        const fullRel = joinRel(rel, pdf);
        const isCurrent = currentRootId === root.id && currentRel === fullRel;
        const isBookmarked = bookmarksSet.has(keyFor(root.id, fullRel));
        const registration = listing.data?.pdfRegistration?.[pdf];
        return (
          <li key={fullRel} className={isRawPdfName(pdf) ? "is-raw-row" : ""}>
            <div
              className={`pdf-row${isCurrent ? " is-current-view" : ""}`}
              data-root-id={root.id}
              data-rel={fullRel}
            >
              <button
                type="button"
                className="bookmark-toggle"
                aria-pressed={isBookmarked}
                aria-label={isBookmarked ? "Remove bookmark" : "Add bookmark"}
                data-root-id={root.id}
                data-rel={fullRel}
                onClick={() => onToggleBookmark(root.id, fullRel)}
              >
                {isBookmarked ? "\u2605" : "\u2606"}
              </button>
              <button
                type="button"
                className="pdf-link"
                aria-current={isCurrent ? "page" : undefined}
                onClick={() => onOpenPdf(root.id, fullRel)}
              >
                {pdf}
                {registration === false ? (
                  <span className="pdf-reg-badge is-unregistered">⚠️</span>
                ) : registration === true ? (
                  <span className="pdf-reg-badge is-registered">📄</span>
                ) : null}
              </button>
            </div>
          </li>
        );
      })}

      {!dirs.length && !visiblePdfs.length && !hiddenRawCount ? (
        <li className="empty-folder">(empty)</li>
      ) : null}
      {hiddenRawCount ? (
        <li className="raw-hidden-hint">
          {hiddenRawCount} _raw_ file{hiddenRawCount === 1 ? "" : "s"} hidden
        </li>
      ) : null}
    </ul>
  );
}

export default function PdfApp() {
  const [config, setConfig] = useState<PdfBrowserConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [currentRootId, setCurrentRootId] = useState(() => queryParam("id"));
  const [currentRel, setCurrentRel] = useState(() => queryParam("rel"));
  const [showRaw, setShowRaw] = useState(readShowRawPreference);
  const [bookmarks, setBookmarks] = useState<Bookmark[]>(readBookmarks);
  const [sidebarWidth, setSidebarWidth] = useState(() => clampSidebarWidth(readSidebarWidth()));
  const [isDraggingSidebar, setIsDraggingSidebar] = useState(false);
  const [listings, setListings] = useState<Record<string, ListingState>>({});
  const [openFolders, setOpenFolders] = useState<Set<string>>(new Set());

  const roots = config?.roots || [];
  const rootsById = useMemo(
    () => Object.fromEntries(roots.map((root) => [root.id, root])),
    [roots],
  );

  useEffect(() => {
    let cancelled = false;
    async function loadConfig(): Promise<void> {
      try {
        const response = await fetch("/api/pdf-browser/config");
        if (!response.ok) throw new Error(`Request failed: ${response.status}`);
        const nextConfig = (await response.json()) as PdfBrowserConfig;
        if (cancelled) return;
        setConfig(nextConfig);
        if (!currentRootId && nextConfig.roots[0]?.id) {
          setCurrentRootId(nextConfig.roots[0].id);
        }
      } catch (error) {
        if (!cancelled) {
          setConfigError(error instanceof Error ? error.message : "Failed to load roots");
        }
      }
    }
    void loadConfig();
    return () => {
      cancelled = true;
    };
  }, [currentRootId]);

  useEffect(() => {
    try {
      window.localStorage.setItem(SHOW_RAW_KEY, showRaw ? "1" : "0");
    } catch {
      // Ignore localStorage failures.
    }
  }, [showRaw]);

  useEffect(() => {
    try {
      window.localStorage.setItem(BOOKMARKS_KEY, JSON.stringify(bookmarks));
    } catch {
      // Ignore localStorage failures.
    }
  }, [bookmarks]);

  useEffect(() => {
    try {
      window.localStorage.setItem(SIDEBAR_WIDTH_KEY, String(sidebarWidth));
    } catch {
      // Ignore localStorage failures.
    }
  }, [sidebarWidth]);

  useEffect(() => {
    if (!isDraggingSidebar) return undefined;
    function onMove(event: MouseEvent): void {
      setSidebarWidth(clampSidebarWidth(event.clientX));
    }
    function onUp(): void {
      setIsDraggingSidebar(false);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    }
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [isDraggingSidebar]);

  useEffect(() => {
    if (!currentRootId || !currentRel) return;
    replacePdfUrl(currentRootId, currentRel);
  }, [currentRootId, currentRel]);

  useEffect(() => {
    if (!currentRootId || !currentRel.toLowerCase().endsWith(".pdf")) return;
    const parts = currentRel.split("/").filter(Boolean);
    const next = new Set<string>();
    let rel = "";
    parts.slice(0, -1).forEach((part) => {
      rel = joinRel(rel, part);
      next.add(keyFor(currentRootId, rel));
    });
    if (next.size) {
      setOpenFolders((prev) => {
        const merged = new Set(prev);
        next.forEach((item) => merged.add(item));
        return merged;
      });
    }
  }, [currentRootId, currentRel]);

  const ensureListing = (rootId: string, rel: string): void => {
    const cacheKey = keyFor(rootId, rel);
    const existing = listings[cacheKey];
    if (existing && (existing.status === "loading" || existing.status === "loaded")) {
      return;
    }
    setListings((prev) => ({
      ...prev,
      [cacheKey]: { status: "loading", data: prev[cacheKey]?.data || null, error: null },
    }));
    const params = new URLSearchParams();
    params.set("id", rootId);
    params.set("rel", rel);
    fetch(`/api/pdf-browser/list?${params.toString()}`)
      .then(async (response) => {
        if (!response.ok) throw new Error(`Request failed: ${response.status}`);
        return (await response.json()) as PdfListResponse;
      })
      .then((data) => {
        setListings((prev) => ({
          ...prev,
          [cacheKey]: { status: "loaded", data, error: null },
        }));
      })
      .catch((error) => {
        setListings((prev) => ({
          ...prev,
          [cacheKey]: {
            status: "error",
            data: null,
            error: error instanceof Error ? error.message : "Failed to load tree",
          },
        }));
      });
  };

  const toggleBookmark = (rootId: string, rel: string): void => {
    setBookmarks((prev) => {
      const key = keyFor(rootId, rel);
      const exists = prev.some((bookmark) => keyFor(bookmark.id, bookmark.rel) === key);
      if (exists) {
        return prev.filter((bookmark) => keyFor(bookmark.id, bookmark.rel) !== key);
      }
      return [...prev, { id: rootId, rel }];
    });
  };

  const setFolderOpen = (rootId: string, rel: string, open: boolean): void => {
    const folderKey = keyFor(rootId, rel);
    setOpenFolders((prev) => {
      const next = new Set(prev);
      if (open) {
        next.add(folderKey);
        ensureListing(rootId, rel);
      } else {
        next.delete(folderKey);
      }
      return next;
    });
  };

  const openPdf = (rootId: string, rel: string): void => {
    setCurrentRootId(rootId);
    setCurrentRel(rel);
  };

  const currentPdfSrc = useMemo(() => {
    if (!currentRootId || !currentRel.toLowerCase().endsWith(".pdf")) return "";
    return buildPdfSrc(currentRootId, currentRel);
  }, [currentRootId, currentRel]);

  const sortedBookmarks = useMemo(() => {
    return [...bookmarks].sort((a, b) => {
      const pathA = rootsById[a.id] ? fullPathFromRootPath(rootsById[a.id].path, a.rel) : a.rel;
      const pathB = rootsById[b.id] ? fullPathFromRootPath(rootsById[b.id].path, b.rel) : b.rel;
      return pathA.localeCompare(pathB, undefined, { sensitivity: "base" });
    });
  }, [bookmarks, rootsById]);

  return (
    <div className={`pdf-browser-legacy${showRaw ? "" : " hide-raw"}`} style={{ ["--sidebar-width" as string]: `${sidebarWidth}px` }}>
      <aside id="sidebar" className="pdf-sidebar-legacy" aria-label="Folder trees">
        <h1>Root PDF browser</h1>
        <section className="sidebar-controls" aria-label="Display options">
          <label className="toggle-row" title="When off, files whose basename starts with _raw_ are hidden from the tree.">
            <input type="checkbox" checked={showRaw} onChange={(e) => setShowRaw(e.target.checked)} />
            <span>
              Show <code>_raw_</code> files
            </span>
          </label>
        </section>

        <section className="bookmarks-section" aria-label="Bookmarked PDFs">
          <div className="bookmarks-section-head">
            <h2 className="bookmarks-heading">Bookmarks</h2>
            <div className="bookmarks-toolbar">
              <button
                type="button"
                className="btn-secondary"
                disabled={!sortedBookmarks.length}
                onClick={() => exportBookmarkPaths(sortedBookmarks, rootsById)}
              >
                Export paths...
              </button>
              <button
                type="button"
                className="btn-secondary"
                disabled={!sortedBookmarks.length}
                onClick={() => setBookmarks([])}
              >
                Clear all
              </button>
            </div>
          </div>
          {!sortedBookmarks.length ? (
            <p className="bookmarks-empty">No bookmarks yet. Use the star next to a PDF in the tree.</p>
          ) : (
            <ul className="bookmarks-list">
              {sortedBookmarks.map((bookmark) => {
                const root = rootsById[bookmark.id];
                const fullPath = root ? fullPathFromRootPath(root.path, bookmark.rel) : bookmark.rel;
                const isCurrent = bookmark.id === currentRootId && bookmark.rel === currentRel;
                return (
                  <li
                    key={keyFor(bookmark.id, bookmark.rel)}
                    className={`bm-item${isCurrent ? " is-current-view" : ""}`}
                    data-root-id={bookmark.id}
                    data-rel={bookmark.rel}
                  >
                    <div className="bm-body">
                      <button
                        type="button"
                        className="bm-open"
                        aria-current={isCurrent ? "page" : undefined}
                        title={fullPath}
                        onClick={() => openPdf(bookmark.id, bookmark.rel)}
                      >
                        {(root ? `${root.label} — ` : "") + (bookmark.rel.split("/").pop() || bookmark.rel)}
                      </button>
                      <span className="bm-meta">{fullPath}</span>
                    </div>
                    <button
                      type="button"
                      className="bm-remove"
                      aria-label="Remove bookmark"
                      onClick={() => toggleBookmark(bookmark.id, bookmark.rel)}
                    >
                      ×
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        {configError ? <p id="roots-loading">Could not load /api/pdf-browser/config: {configError}</p> : null}
        {!config && !configError ? <p id="roots-loading">Loading roots...</p> : null}

        {roots.map((root) => (
          <div key={root.id} className="root-block" data-root-id={root.id}>
            <h2>{root.label}</h2>
            <div className="root-path">{root.path}</div>
            <div className="tree-folder-children" data-tree-host="1">
              <PdfTree
                root={root}
                rel=""
                currentRootId={currentRootId}
                currentRel={currentRel}
                listings={listings}
                ensureListing={ensureListing}
                openFolders={openFolders}
                setFolderOpen={setFolderOpen}
                showRaw={showRaw}
                bookmarks={bookmarks}
                onToggleBookmark={toggleBookmark}
                onOpenPdf={openPdf}
              />
            </div>
          </div>
        ))}
      </aside>

      <div
        id="splitter"
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize sidebar"
        title="Drag to resize sidebar"
        tabIndex={0}
        onMouseDown={(event) => {
          if (event.button !== 0) return;
          event.preventDefault();
          setIsDraggingSidebar(true);
        }}
        onKeyDown={(event) => {
          if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
          event.preventDefault();
          const step = event.shiftKey ? 48 : 16;
          const delta = event.key === "ArrowRight" ? step : -step;
          setSidebarWidth((prev) => clampSidebarWidth(prev + delta));
        }}
      />

      <main id="viewer" className="pdf-viewer-legacy" aria-label="PDF viewer">
        {currentPdfSrc ? (
          <>
            <div className="pdf-viewer-toolbar">
              <span className="pdf-viewer-current">{currentRel.split("/").pop() || currentRel}</span>
              <a href={currentPdfSrc.replace(PDF_VIEWER_FRAGMENT, "")} target="_blank" rel="noreferrer">
                Open raw PDF
              </a>
            </div>
            <iframe id="pdf-frame" className="pdf-frame-legacy" title="PDF" src={currentPdfSrc} />
          </>
        ) : (
          <p id="empty" className="pdf-empty-legacy">
            Select a PDF from the left.
          </p>
        )}
      </main>
    </div>
  );
}
