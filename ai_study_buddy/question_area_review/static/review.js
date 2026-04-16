const state = {
  indexData: null,
  currentQuestionIndex: 0,
  currentRegionIndex: 0,
  editTarget: "question",
  draft: null,
  originalDraft: null,
  pageImageCache: new Map(),
  dragging: null,
};

const els = {
  docMeta: document.getElementById("doc-meta"),
  progressText: document.getElementById("progress-text"),
  progressFill: document.getElementById("progress-fill"),
  indexStatus: document.getElementById("index-status"),
  backBtn: document.getElementById("back-btn"),
  skipBtn: document.getElementById("skip-btn"),
  nextUnreviewedBtn: document.getElementById("next-unreviewed-btn"),
  acceptBtn: document.getElementById("accept-btn"),
  saveBtn: document.getElementById("save-btn"),
  questionLabel: document.getElementById("question-label"),
  reviewStatus: document.getElementById("review-status"),
  questionMeta: document.getElementById("question-meta"),
  questionText: document.getElementById("question-text"),
  editTargetSelect: document.getElementById("edit-target-select"),
  regionSelect: document.getElementById("region-select"),
  fieldPage: document.getElementById("field-page"),
  fieldX1: document.getElementById("field-x1"),
  fieldY1: document.getElementById("field-y1"),
  fieldX2: document.getElementById("field-x2"),
  fieldY2: document.getElementById("field-y2"),
  stimulusMeta: document.getElementById("stimulus-meta"),
  stimulusText: document.getElementById("stimulus-text"),
  saveState: document.getElementById("save-state"),
  cropMeta: document.getElementById("crop-meta"),
  cropCanvas: document.getElementById("crop-canvas"),
  pageMeta: document.getElementById("page-meta"),
  pageWrap: document.getElementById("page-wrap"),
  pageImage: document.getElementById("page-image"),
  overlay: document.getElementById("overlay"),
};

const cropCtx = els.cropCanvas.getContext("2d");
const HANDLE_POSITIONS = ["nw", "n", "ne", "e", "se", "s", "sw", "w"];
const HANDLE_GROUPS = {
  nw: ["left", "top"],
  n: ["top"],
  ne: ["right", "top"],
  e: ["right"],
  se: ["right", "bottom"],
  s: ["bottom"],
  sw: ["left", "bottom"],
  w: ["left"],
};

function currentQuestion() {
  return state.indexData.questions[state.currentQuestionIndex];
}

function currentRegion() {
  return currentQuestion().prompt_regions[state.currentRegionIndex];
}

function currentStimulus() {
  return currentQuestion().linked_stimulus;
}

function currentStimulusRegion() {
  const stimulus = currentStimulus();
  return stimulus ? stimulus.regions[state.currentRegionIndex] : null;
}

function currentEditableRegion() {
  return state.editTarget === "stimulus" ? currentStimulusRegion() : currentRegion();
}

function roundCoord(value) {
  return Math.max(0, Math.min(1, Number(value))).toFixed(3);
}

function normalizeDraft(draft) {
  const page = Math.max(1, Math.round(Number(draft.page) || 1));
  const nums = draft.bbox.map((value) => Math.max(0, Math.min(1, Number(value) || 0)));
  let [x1, y1, x2, y2] = nums;
  if (x2 <= x1) x2 = Math.min(1, x1 + 0.001);
  if (y2 <= y1) y2 = Math.min(1, y1 + 0.001);
  return { page, bbox: [x1, y1, x2, y2] };
}

function draftChanged() {
  return JSON.stringify(normalizeDraft(state.draft)) !== JSON.stringify(normalizeDraft(state.originalDraft));
}

function setSaveState(message) {
  els.saveState.textContent = message;
}

function reviewedCount() {
  return state.indexData.questions.filter((q) => ["accepted", "corrected"].includes(q.review_status)).length;
}

function setCurrentQuestion(index, regionIndex = 0) {
  state.currentQuestionIndex = Math.max(0, Math.min(state.indexData.questions.length - 1, index));
  const question = currentQuestion();
  if (state.editTarget === "stimulus" && !currentStimulus()) {
    state.editTarget = "question";
  }
  const regions = state.editTarget === "stimulus" ? (currentStimulus()?.regions || []) : (question.prompt_regions || []);
  state.currentRegionIndex = Math.max(0, Math.min(regions.length - 1, regionIndex));
  const region = currentEditableRegion();
  state.draft = { page: region.page, bbox: [...region.bbox] };
  state.originalDraft = { page: region.page, bbox: [...region.bbox] };
  render();
}

async function fetchIndex() {
  const response = await fetch("/api/index");
  if (!response.ok) throw new Error(`Failed to load index: ${response.status}`);
  state.indexData = await response.json();
  const start = Math.max(0, state.indexData.first_unreviewed_index || 0);
  setCurrentQuestion(start, 0);
}

async function loadPageImage(page) {
  if (!state.pageImageCache.has(page)) {
    const img = new Image();
    img.src = `/api/page/${page}`;
    state.pageImageCache.set(
      page,
      new Promise((resolve, reject) => {
        img.onload = () => resolve(img);
        img.onerror = reject;
      })
    );
  }
  return state.pageImageCache.get(page);
}

function updateProgress() {
  const reviewed = reviewedCount();
  const total = state.indexData.total_questions;
  els.progressText.textContent = `${reviewed} / ${total} reviewed`;
  els.progressFill.style.width = `${total ? (reviewed / total) * 100 : 0}%`;
  els.indexStatus.textContent = state.indexData.index_status;
}

function updateQuestionInfo() {
  const question = currentQuestion();
  els.docMeta.textContent = `${state.indexData.book_label} | ${state.indexData.unit_label}`;
  els.questionLabel.textContent = `${question.display_label} (${state.currentQuestionIndex + 1}/${state.indexData.questions.length})`;
  els.reviewStatus.textContent = question.review_status || "unreviewed";
  els.reviewStatus.className = `pill ${question.review_status === "accepted" ? "pill-accepted" : ""} ${question.review_status === "corrected" ? "pill-corrected" : "pill-muted"}`.trim();
  els.questionMeta.textContent = `${question.question_type} | ${question.max_marks} mark${question.max_marks === 1 ? "" : "s"} | question_id: ${question.question_id}`;
  els.questionText.textContent = question.printed_question_text || "No extracted question text.";

  const linked = question.linked_stimulus;
  if (linked) {
    els.stimulusMeta.textContent = `${linked.block_id} | ${linked.block_type}`;
    els.stimulusText.textContent = linked.summary || linked.label || "Stimulus linked.";
  } else {
    els.stimulusMeta.textContent = "None";
    els.stimulusText.textContent = "No linked stimulus block.";
  }

  els.editTargetSelect.innerHTML = "";
  const questionOption = document.createElement("option");
  questionOption.value = "question";
  questionOption.textContent = "Question region";
  els.editTargetSelect.appendChild(questionOption);
  if (linked) {
    const stimulusOption = document.createElement("option");
    stimulusOption.value = "stimulus";
    stimulusOption.textContent = `Stimulus region (${linked.block_id})`;
    els.editTargetSelect.appendChild(stimulusOption);
  }
  if (state.editTarget === "stimulus" && !linked) {
    state.editTarget = "question";
  }
  els.editTargetSelect.value = state.editTarget;

  els.regionSelect.innerHTML = "";
  const editableRegions = state.editTarget === "stimulus" ? (linked?.regions || []) : question.prompt_regions;
  editableRegions.forEach((region, idx) => {
    const option = document.createElement("option");
    option.value = String(idx);
    option.textContent = `${state.editTarget === "stimulus" ? "Stimulus" : "Region"} ${idx + 1} | page ${region.page}`;
    els.regionSelect.appendChild(option);
  });
  els.regionSelect.value = String(state.currentRegionIndex);
}

function updateFieldInputs() {
  const draft = normalizeDraft(state.draft);
  els.fieldPage.value = String(draft.page);
  els.fieldX1.value = roundCoord(draft.bbox[0]);
  els.fieldY1.value = roundCoord(draft.bbox[1]);
  els.fieldX2.value = roundCoord(draft.bbox[2]);
  els.fieldY2.value = roundCoord(draft.bbox[3]);
  els.cropMeta.textContent = `page ${draft.page} | x1 ${roundCoord(draft.bbox[0])} | y1 ${roundCoord(draft.bbox[1])} | x2 ${roundCoord(draft.bbox[2])} | y2 ${roundCoord(draft.bbox[3])}`;
  els.pageMeta.textContent = `Page ${draft.page}${draftChanged() ? " | unsaved adjustment" : ""}`;
}

function pageToPixels(bbox, width, height) {
  const [x1, y1, x2, y2] = bbox;
  return {
    left: x1 * width,
    top: y1 * height,
    width: (x2 - x1) * width,
    height: (y2 - y1) * height,
  };
}

function buildHandle(position) {
  const handle = document.createElement("div");
  handle.className = `handle ${position}`;
  handle.dataset.handle = position;
  return handle;
}

function renderOverlay() {
  const draft = normalizeDraft(state.draft);
  const question = currentQuestion();
  els.overlay.innerHTML = "";

  const questionRegions = question.prompt_regions || [];
  questionRegions.forEach((region, idx) => {
    const active = state.editTarget === "question" && idx === state.currentRegionIndex;
    const bbox = active ? draft.bbox : region.bbox;
    const box = document.createElement("div");
    box.className = "bbox question";
    box.style.left = `${bbox[0] * 100}%`;
    box.style.top = `${bbox[1] * 100}%`;
    box.style.width = `${(bbox[2] - bbox[0]) * 100}%`;
    box.style.height = `${(bbox[3] - bbox[1]) * 100}%`;
    if (active) {
      box.dataset.dragMode = "move";
    } else {
      box.classList.add("passive");
      box.dataset.selectTarget = "question";
      box.dataset.selectIndex = String(idx);
    }

    const label = document.createElement("div");
    label.className = "bbox-label";
    label.textContent = questionRegions.length > 1 ? `${question.display_label} ${idx + 1}` : question.display_label;
    box.appendChild(label);
    if (active) {
      HANDLE_POSITIONS.forEach((position) => box.appendChild(buildHandle(position)));
    }
    els.overlay.appendChild(box);
  });

  const linked = question.linked_stimulus;
  if (linked) {
    (linked.regions || []).forEach((region, idx) => {
      const active = state.editTarget === "stimulus" && idx === state.currentRegionIndex;
      const bbox = active ? draft.bbox : region.bbox;
      const box = document.createElement("div");
      box.className = "bbox stimulus";
      box.style.left = `${bbox[0] * 100}%`;
      box.style.top = `${bbox[1] * 100}%`;
      box.style.width = `${(bbox[2] - bbox[0]) * 100}%`;
      box.style.height = `${(bbox[3] - bbox[1]) * 100}%`;
      if (active) {
        box.dataset.dragMode = "move";
      } else {
        box.classList.add("passive");
        box.dataset.selectTarget = "stimulus";
        box.dataset.selectIndex = String(idx);
      }

      const label = document.createElement("div");
      label.className = "bbox-label";
      label.textContent = idx === 0 ? linked.block_id : `${linked.block_id} ${idx + 1}`;
      box.appendChild(label);
      if (active) {
        HANDLE_POSITIONS.forEach((position) => box.appendChild(buildHandle(position)));
      }
      els.overlay.appendChild(box);
    });
  }
}

async function renderCrop() {
  const draft = normalizeDraft(state.draft);
  const image = await loadPageImage(draft.page);
  const naturalWidth = image.naturalWidth;
  const naturalHeight = image.naturalHeight;
  const px = pageToPixels(draft.bbox, naturalWidth, naturalHeight);

  const width = Math.max(1, Math.round(px.width));
  const height = Math.max(1, Math.round(px.height));
  els.cropCanvas.width = width;
  els.cropCanvas.height = height;
  cropCtx.clearRect(0, 0, width, height);
  cropCtx.drawImage(image, px.left, px.top, px.width, px.height, 0, 0, width, height);
}

async function renderPageImage() {
  const draft = normalizeDraft(state.draft);
  els.pageImage.src = `/api/page/${draft.page}`;
  els.pageImage.alt = `Page ${draft.page}`;
  await loadPageImage(draft.page);
}

async function render() {
  updateProgress();
  updateQuestionInfo();
  updateFieldInputs();
  await renderPageImage();
  renderOverlay();
  await renderCrop();
  updateButtons();
}

function updateButtons() {
  els.backBtn.disabled = state.currentQuestionIndex <= 0;
  els.skipBtn.disabled = state.currentQuestionIndex >= state.indexData.questions.length - 1;
  els.acceptBtn.textContent = draftChanged() ? "Accept Current Box" : "Accept";
  els.saveBtn.disabled = !draftChanged();
}

function goRelative(delta) {
  const next = Math.max(0, Math.min(state.indexData.questions.length - 1, state.currentQuestionIndex + delta));
  setCurrentQuestion(next, 0);
}

function findNextUnreviewedIndex(startExclusive = state.currentQuestionIndex) {
  for (let idx = startExclusive + 1; idx < state.indexData.questions.length; idx += 1) {
    if (state.indexData.questions[idx].review_status === "unreviewed") return idx;
  }
  for (let idx = 0; idx <= startExclusive; idx += 1) {
    if (state.indexData.questions[idx].review_status === "unreviewed") return idx;
  }
  return -1;
}

function goNextUnreviewed() {
  const next = findNextUnreviewedIndex();
  if (next !== -1) {
    setCurrentQuestion(next, 0);
  }
}

function applyInputFields() {
  state.draft = normalizeDraft({
    page: els.fieldPage.value,
    bbox: [els.fieldX1.value, els.fieldY1.value, els.fieldX2.value, els.fieldY2.value],
  });
  render();
}

async function saveQuestion(reviewStatus) {
  const draft = normalizeDraft(state.draft);
  const response = await fetch("/api/save-question", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question_index: state.currentQuestionIndex,
      region_index: state.currentRegionIndex,
      page: draft.page,
      bbox: draft.bbox,
      review_status: reviewStatus,
    }),
  });
  const payload = await response.json();
  if (!response.ok || payload.error) {
    throw new Error(payload.error || `Save failed (${response.status})`);
  }
  state.indexData = payload.index;
  setSaveState(
    `${currentQuestion().display_label} saved as ${reviewStatus} at ${new Date().toLocaleTimeString()}`
  );
}

async function saveStimulus() {
  const draft = normalizeDraft(state.draft);
  const stimulus = currentStimulus();
  const response = await fetch("/api/save-stimulus", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question_index: state.currentQuestionIndex,
      stimulus_block_id: stimulus.block_id,
      region_index: state.currentRegionIndex,
      page: draft.page,
      bbox: draft.bbox,
    }),
  });
  const payload = await response.json();
  if (!response.ok || payload.error) {
    throw new Error(payload.error || `Save failed (${response.status})`);
  }
  state.indexData = payload.index;
  setSaveState(
    `${stimulus.block_id} saved as corrected at ${new Date().toLocaleTimeString()}`
  );
}

async function acceptCurrent() {
  const reviewStatus = draftChanged() ? "corrected" : "accepted";
  await saveQuestion(reviewStatus);
  const nextUnreviewed = findNextUnreviewedIndex(state.currentQuestionIndex);
  if (nextUnreviewed !== -1) {
    setCurrentQuestion(nextUnreviewed, 0);
  } else if (state.currentQuestionIndex < state.indexData.questions.length - 1) {
    setCurrentQuestion(state.currentQuestionIndex + 1, 0);
  } else {
    setCurrentQuestion(state.currentQuestionIndex, 0);
  }
}

async function saveAdjustment() {
  if (state.editTarget === "stimulus") {
    await saveStimulus();
  } else {
    await saveQuestion("corrected");
  }
  const nextUnreviewed = findNextUnreviewedIndex(state.currentQuestionIndex);
  if (nextUnreviewed !== -1) {
    setCurrentQuestion(nextUnreviewed, 0);
  } else if (state.currentQuestionIndex < state.indexData.questions.length - 1) {
    setCurrentQuestion(state.currentQuestionIndex + 1, 0);
  } else {
    setCurrentQuestion(state.currentQuestionIndex, 0);
  }
}

function pointerToNormalized(event) {
  const rect = els.pageWrap.getBoundingClientRect();
  return {
    x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)),
    y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)),
  };
}

function beginDrag(event) {
  const handle = event.target.closest(".handle");
  const selectable = event.target.closest(".bbox.passive");
  if (selectable) {
    state.editTarget = selectable.dataset.selectTarget;
    state.currentRegionIndex = Number(selectable.dataset.selectIndex);
    const region = currentEditableRegion();
    state.draft = { page: region.page, bbox: [...region.bbox] };
    state.originalDraft = { page: region.page, bbox: [...region.bbox] };
    render();
    return;
  }

  const box = event.target.closest(".bbox.question, .bbox.stimulus");
  if (!box) return;

  const draft = normalizeDraft(state.draft);
  const point = pointerToNormalized(event);
  state.dragging = {
    mode: handle ? handle.dataset.handle : "move",
    startPoint: point,
    startDraft: JSON.parse(JSON.stringify(draft)),
  };
  window.addEventListener("pointermove", onDrag);
  window.addEventListener("pointerup", endDrag, { once: true });
}

function onDrag(event) {
  if (!state.dragging) return;
  const point = pointerToNormalized(event);
  const dx = point.x - state.dragging.startPoint.x;
  const dy = point.y - state.dragging.startPoint.y;
  const next = JSON.parse(JSON.stringify(state.dragging.startDraft));
  const bbox = [...next.bbox];

  if (state.dragging.mode === "move") {
    const width = bbox[2] - bbox[0];
    const height = bbox[3] - bbox[1];
    let x1 = bbox[0] + dx;
    let y1 = bbox[1] + dy;
    x1 = Math.max(0, Math.min(1 - width, x1));
    y1 = Math.max(0, Math.min(1 - height, y1));
    next.bbox = [x1, y1, x1 + width, y1 + height];
  } else {
    const groups = HANDLE_GROUPS[state.dragging.mode];
    if (groups.includes("left")) bbox[0] += dx;
    if (groups.includes("right")) bbox[2] += dx;
    if (groups.includes("top")) bbox[1] += dy;
    if (groups.includes("bottom")) bbox[3] += dy;
    next.bbox = bbox;
  }

  state.draft = normalizeDraft(next);
  render();
}

function endDrag() {
  state.dragging = null;
  window.removeEventListener("pointermove", onDrag);
}

function wireEvents() {
  els.backBtn.addEventListener("click", () => goRelative(-1));
  els.skipBtn.addEventListener("click", () => goRelative(1));
  els.nextUnreviewedBtn.addEventListener("click", () => goNextUnreviewed());
  els.acceptBtn.addEventListener("click", async () => {
    try {
      await acceptCurrent();
    } catch (error) {
      setSaveState(String(error));
    }
  });
  els.saveBtn.addEventListener("click", async () => {
    try {
      await saveAdjustment();
    } catch (error) {
      setSaveState(String(error));
    }
  });

  els.regionSelect.addEventListener("change", () => setCurrentQuestion(state.currentQuestionIndex, Number(els.regionSelect.value)));
  els.editTargetSelect.addEventListener("change", () => {
    state.editTarget = els.editTargetSelect.value;
    setCurrentQuestion(state.currentQuestionIndex, 0);
  });
  [els.fieldPage, els.fieldX1, els.fieldY1, els.fieldX2, els.fieldY2].forEach((input) => {
    input.addEventListener("change", applyInputFields);
  });

  els.overlay.addEventListener("pointerdown", beginDrag);

  document.addEventListener("keydown", async (event) => {
    const tag = document.activeElement && document.activeElement.tagName;
    const inField = tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA";
    if (inField && !["Enter"].includes(event.key)) return;

    try {
      if (event.key === "Enter" || event.key.toLowerCase() === "a") {
        event.preventDefault();
        await acceptCurrent();
      } else if (event.key.toLowerCase() === "s") {
        event.preventDefault();
        await saveAdjustment();
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        goRelative(1);
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        goRelative(-1);
      }
    } catch (error) {
      setSaveState(String(error));
    }
  });
}

async function init() {
  wireEvents();
  try {
    await fetchIndex();
    setSaveState("Ready. Changes save back to the JSON file immediately.");
  } catch (error) {
    setSaveState(String(error));
  }
}

init();
