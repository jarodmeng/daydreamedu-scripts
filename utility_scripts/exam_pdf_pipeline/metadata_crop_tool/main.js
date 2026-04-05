const MANIFEST_URL = "./assets/manifest.json";
const STORAGE_KEY = `metadata_crops_${window.location.pathname}_v1`;

const setNumberEl = document.getElementById("set-number");
const pdfPageEl = document.getElementById("pdf-page");
const savedStatusEl = document.getElementById("saved-status");
const coordsOutputEl = document.getElementById("coords-output");
const regionsListEl = document.getElementById("regions-list");
const pageImageEl = document.getElementById("page-image");
const canvasWrapEl = document.getElementById("canvas-wrap");
const selectionBoxEl = document.getElementById("selection-box");
const savedSelectionsLayerEl = document.getElementById("saved-selections-layer");
const prevBtn = document.getElementById("prev-btn");
const nextBtn = document.getElementById("next-btn");
const saveBtn = document.getElementById("save-btn");
const deleteLastBtn = document.getElementById("delete-last-btn");
const clearPendingBtn = document.getElementById("clear-pending-btn");
const clearAllBtn = document.getElementById("clear-all-btn");
const exportBtn = document.getElementById("export-btn");
const importInput = document.getElementById("import-input");

let manifest = [];
let currentIndex = 0;
let selections = loadSelections();
let dragState = null;
let pendingSelection = null;

function loadSelections() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    for (const [key, value] of Object.entries(parsed)) {
      if (!Array.isArray(value) && value && typeof value === "object" && "x" in value) {
        parsed[key] = [value];
      }
    }
    return parsed;
  } catch {
    return {};
  }
}

function persistSelections() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(selections, null, 2));
}

function selectionKey(item) {
  return String(item.set_number);
}

function getCurrentItem() {
  return manifest[currentIndex];
}

function getSavedSelections(item) {
  const saved = selections[selectionKey(item)];
  if (!saved) return [];
  return Array.isArray(saved) ? saved : [saved];
}

function selectionToDisplaySpace(selection) {
  if (
    selection &&
    typeof selection.x_norm === "number" &&
    typeof selection.y_norm === "number" &&
    typeof selection.width_norm === "number" &&
    typeof selection.height_norm === "number"
  ) {
    return {
      ...selection,
      x: selection.x_norm * pageImageEl.clientWidth,
      y: selection.y_norm * pageImageEl.clientHeight,
      width: selection.width_norm * pageImageEl.clientWidth,
      height: selection.height_norm * pageImageEl.clientHeight,
    };
  }
  return selection;
}

function withImageMetrics(selection) {
  const displayedWidth = pageImageEl.clientWidth;
  const displayedHeight = pageImageEl.clientHeight;
  const naturalWidth = pageImageEl.naturalWidth || displayedWidth;
  const naturalHeight = pageImageEl.naturalHeight || displayedHeight;
  return {
    ...selection,
    displayed_width: displayedWidth,
    displayed_height: displayedHeight,
    natural_width: naturalWidth,
    natural_height: naturalHeight,
    x_norm: displayedWidth ? selection.x / displayedWidth : 0,
    y_norm: displayedHeight ? selection.y / displayedHeight : 0,
    width_norm: displayedWidth ? selection.width / displayedWidth : 0,
    height_norm: displayedHeight ? selection.height / displayedHeight : 0,
  };
}

function normalizeSelectionForItem(selection, item) {
  if (
    selection &&
    typeof selection.x_norm === "number" &&
    typeof selection.y_norm === "number" &&
    typeof selection.width_norm === "number" &&
    typeof selection.height_norm === "number"
  ) {
    return selection;
  }
  const displayedWidth = selection.displayed_width || pageImageEl.clientWidth || item.image_width;
  const displayedHeight =
    selection.displayed_height ||
    pageImageEl.clientHeight ||
    (displayedWidth * item.image_height) / item.image_width;
  return {
    ...selection,
    displayed_width: displayedWidth,
    displayed_height: displayedHeight,
    natural_width: selection.natural_width || item.image_width,
    natural_height: selection.natural_height || item.image_height,
    x_norm: displayedWidth ? selection.x / displayedWidth : 0,
    y_norm: displayedHeight ? selection.y / displayedHeight : 0,
    width_norm: displayedWidth ? selection.width / displayedWidth : 0,
    height_norm: displayedHeight ? selection.height / displayedHeight : 0,
  };
}

function renderPendingSelection(selection) {
  if (!selection) {
    selectionBoxEl.classList.add("hidden");
    return;
  }
  selectionBoxEl.classList.remove("hidden");
  selectionBoxEl.style.left = `${selection.x}px`;
  selectionBoxEl.style.top = `${selection.y}px`;
  selectionBoxEl.style.width = `${selection.width}px`;
  selectionBoxEl.style.height = `${selection.height}px`;
}

function renderSavedSelections(savedSelections) {
  savedSelectionsLayerEl.innerHTML = "";
  for (const rawSelection of savedSelections) {
    const selection = selectionToDisplaySpace(rawSelection);
    const box = document.createElement("div");
    box.className = "selection saved";
    box.style.left = `${selection.x}px`;
    box.style.top = `${selection.y}px`;
    box.style.width = `${selection.width}px`;
    box.style.height = `${selection.height}px`;
    savedSelectionsLayerEl.appendChild(box);
  }
}

function updateSidebar() {
  const item = getCurrentItem();
  const savedSelections = getSavedSelections(item);
  const shown = pendingSelection ?? null;

  setNumberEl.textContent = item.set_number;
  pdfPageEl.textContent = item.pdf_page;
  savedStatusEl.textContent = String(savedSelections.length);
  coordsOutputEl.textContent = shown
    ? JSON.stringify(
        {
          x: shown.x,
          y: shown.y,
          width: shown.width,
          height: shown.height,
          x_norm: shown.x_norm,
          y_norm: shown.y_norm,
          width_norm: shown.width_norm,
          height_norm: shown.height_norm,
          image_width: item.image_width,
          image_height: item.image_height,
        },
        null,
        2,
      )
    : "No crop selected.";
  regionsListEl.innerHTML = "";
  if (!savedSelections.length) {
    regionsListEl.textContent = "No saved regions.";
  } else {
    savedSelections.forEach((rawSelection, index) => {
      const selection = selectionToDisplaySpace(rawSelection);
      const itemEl = document.createElement("div");
      itemEl.className = "region-item";
      itemEl.textContent =
        `Region ${index + 1}: x=${selection.x}, y=${selection.y}, ` +
        `w=${selection.width}, h=${selection.height}`;
      regionsListEl.appendChild(itemEl);
    });
  }
  renderSavedSelections(savedSelections);
  renderPendingSelection(shown);
}

function showCurrentItem() {
  const item = getCurrentItem();
  pendingSelection = null;
  pageImageEl.src = item.image_path;
  pageImageEl.onload = () => {
    updateSidebar();
  };
}

function clampRect(rect) {
  const width = Math.max(1, Math.min(pageImageEl.clientWidth - rect.x, rect.width));
  const height = Math.max(1, Math.min(pageImageEl.clientHeight - rect.y, rect.height));
  return {
    x: Math.max(0, rect.x),
    y: Math.max(0, rect.y),
    width,
    height,
  };
}

function pointerToLocal(event) {
  const bounds = pageImageEl.getBoundingClientRect();
  return {
    x: Math.max(0, Math.min(bounds.width, event.clientX - bounds.left)),
    y: Math.max(0, Math.min(bounds.height, event.clientY - bounds.top)),
  };
}

canvasWrapEl.addEventListener("pointerdown", (event) => {
  if (!pageImageEl.src) return;
  const point = pointerToLocal(event);
  dragState = { startX: point.x, startY: point.y };
  pendingSelection = { x: point.x, y: point.y, width: 1, height: 1 };
  updateSidebar();
});

window.addEventListener("pointermove", (event) => {
  if (!dragState) return;
  const point = pointerToLocal(event);
  const x = Math.min(dragState.startX, point.x);
  const y = Math.min(dragState.startY, point.y);
  const width = Math.abs(point.x - dragState.startX);
  const height = Math.abs(point.y - dragState.startY);
  pendingSelection = clampRect({ x, y, width, height });
  updateSidebar();
});

window.addEventListener("pointerup", () => {
  dragState = null;
});

saveBtn.addEventListener("click", () => {
  const item = getCurrentItem();
  if (!pendingSelection) return;
  const key = selectionKey(item);
  const savedSelections = getSavedSelections(item);
  selections[key] = [...savedSelections, withImageMetrics(pendingSelection)];
  persistSelections();
  pendingSelection = null;
  updateSidebar();
});

deleteLastBtn.addEventListener("click", () => {
  const item = getCurrentItem();
  const key = selectionKey(item);
  const savedSelections = getSavedSelections(item);
  if (!savedSelections.length) return;
  const nextSelections = savedSelections.slice(0, -1);
  if (nextSelections.length) {
    selections[key] = nextSelections;
  } else {
    delete selections[key];
  }
  persistSelections();
  updateSidebar();
});

clearPendingBtn.addEventListener("click", () => {
  pendingSelection = null;
  updateSidebar();
});

clearAllBtn.addEventListener("click", () => {
  const item = getCurrentItem();
  delete selections[selectionKey(item)];
  pendingSelection = null;
  persistSelections();
  updateSidebar();
});

prevBtn.addEventListener("click", () => {
  if (currentIndex > 0) {
    currentIndex -= 1;
    showCurrentItem();
  }
});

nextBtn.addEventListener("click", () => {
  if (currentIndex < manifest.length - 1) {
    currentIndex += 1;
    showCurrentItem();
  }
});

exportBtn.addEventListener("click", () => {
  const normalizedSelections = {};
  for (const item of manifest) {
    const key = selectionKey(item);
    const savedSelections = getSavedSelections(item);
    if (!savedSelections.length) continue;
    normalizedSelections[key] = savedSelections.map((selection) =>
      normalizeSelectionForItem(selection, item),
    );
  }
  selections = normalizedSelections;
  persistSelections();
  const payload = {
    exported_at: new Date().toISOString(),
    version: 2,
    selections: normalizedSelections,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "chinese_p2_metadata_crops.json";
  link.click();
  URL.revokeObjectURL(url);
});

importInput.addEventListener("change", async (event) => {
  const [file] = event.target.files ?? [];
  if (!file) return;
  const text = await file.text();
  const parsed = JSON.parse(text);
  selections = parsed.selections ?? {};
  persistSelections();
  pendingSelection = null;
  updateSidebar();
});

async function init() {
  const response = await fetch(MANIFEST_URL);
  const data = await response.json();
  manifest = data.items;
  showCurrentItem();
}

init().catch((error) => {
  coordsOutputEl.textContent = `Failed to load manifest: ${error}`;
});
