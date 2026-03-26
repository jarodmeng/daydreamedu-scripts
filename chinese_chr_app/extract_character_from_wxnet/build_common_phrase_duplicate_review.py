#!/usr/bin/env python3
"""
Build a self-contained HTML review UI for duplicated common-phrase readings.

The generated HTML embeds the current duplicated-phrase dataset so it can be
opened locally in a browser without a separate backend server.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent
DATA_PATH = BASE_DIR / "data" / "extracted_hwxnet_common_phrase_character_readings.json"
OUTPUT_HTML = SCRIPT_DIR / "review_common_phrase_duplicates.html"
DECISIONS_FILENAME = "common_phrase_duplicate_decisions.json"


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Common Phrase Duplicate Review</title>
  <style>
    :root {
      --bg: #f3efe7;
      --panel: #fffdf9;
      --ink: #1f1a14;
      --muted: #6d6154;
      --line: #d8ccbb;
      --accent: #8c3d1f;
      --accent-soft: #f6e6dc;
      --good: #2f6b3b;
      --warn: #8b5d12;
      --pill: #efe4d6;
      --shadow: 0 14px 32px rgba(75, 49, 24, 0.08);
      --radius: 18px;
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
      background:
        radial-gradient(circle at top left, #fff8ef 0%, transparent 28%),
        linear-gradient(180deg, #f5f0e8 0%, #f0e8dc 100%);
      color: var(--ink);
    }
    .page {
      max-width: 1120px;
      margin: 0 auto;
      padding: 28px 18px 56px;
    }
    .hero, .toolbar, .card {
      background: var(--panel);
      border: 1px solid rgba(140, 61, 31, 0.12);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }
    .hero {
      padding: 26px 24px 20px;
      margin-bottom: 18px;
    }
    h1 {
      margin: 0 0 10px;
      font-size: clamp(2rem, 4vw, 3.2rem);
      line-height: 0.95;
      letter-spacing: -0.03em;
    }
    .hero p, .small {
      margin: 0;
      color: var(--muted);
      font-size: 0.98rem;
      line-height: 1.45;
    }
    .hero-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }
    .toolbar {
      padding: 16px;
      margin-bottom: 18px;
    }
    .toolbar-grid {
      display: grid;
      grid-template-columns: 1.2fr 1fr 1fr;
      gap: 12px;
      align-items: end;
    }
    .field label {
      display: block;
      font-size: 0.82rem;
      color: var(--muted);
      margin-bottom: 6px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }
    input[type="search"], select, textarea {
      width: 100%;
      padding: 10px 12px;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: #fff;
      font: inherit;
      color: var(--ink);
    }
    textarea {
      min-height: 78px;
      resize: vertical;
    }
    .stats {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 14px;
    }
    .stat {
      background: var(--pill);
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 0.92rem;
    }
    .button {
      border: 0;
      border-radius: 999px;
      padding: 10px 14px;
      font: inherit;
      cursor: pointer;
      background: var(--ink);
      color: #fff;
    }
    .button.secondary {
      background: #eadfd1;
      color: var(--ink);
    }
    .button.ghost {
      background: transparent;
      color: var(--accent);
      border: 1px solid rgba(140, 61, 31, 0.22);
    }
    .button:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }
    .cards {
      display: grid;
      gap: 16px;
    }
    .card {
      padding: 18px;
    }
    .card-head {
      display: flex;
      justify-content: space-between;
      align-items: start;
      gap: 12px;
      margin-bottom: 12px;
    }
    .title {
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      gap: 10px;
    }
    .title .character {
      font-size: 2rem;
      font-weight: 700;
      line-height: 1;
    }
    .title .phrase {
      font-size: 1.45rem;
      font-weight: 700;
    }
    .status-pill {
      border-radius: 999px;
      padding: 7px 12px;
      font-size: 0.84rem;
      background: #f1e8dc;
      color: var(--ink);
      white-space: nowrap;
    }
    .status-pill.decided-keep-one { background: #e4f1e6; color: var(--good); }
    .status-pill.decided-keep-both { background: #e8eef9; color: #274f8b; }
    .status-pill.undecided { background: #f7ead7; color: var(--warn); }
    .meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 14px;
      color: var(--muted);
      font-size: 0.92rem;
    }
    .meta .chip {
      background: #f7f1e9;
      border-radius: 999px;
      padding: 6px 10px;
    }
    .options {
      display: grid;
      gap: 10px;
      margin-bottom: 14px;
    }
    .option {
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
      background: #fff;
    }
    .option label {
      display: flex;
      gap: 12px;
      align-items: start;
      cursor: pointer;
    }
    .option-main {
      flex: 1;
    }
    .option reading {
      font-weight: 700;
    }
    .option .pinyin {
      color: var(--accent);
      font-size: 1rem;
      margin-bottom: 4px;
    }
    .option .tiny {
      color: var(--muted);
      font-size: 0.88rem;
      line-height: 1.35;
    }
    .decision-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 12px;
    }
    .decision-row label {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: #f5eee5;
      cursor: pointer;
    }
    .notes {
      margin-top: 12px;
    }
    .empty {
      text-align: center;
      color: var(--muted);
      padding: 48px 20px;
      background: rgba(255,255,255,0.65);
      border-radius: var(--radius);
      border: 1px dashed rgba(140, 61, 31, 0.25);
    }
    .footer {
      margin-top: 18px;
      color: var(--muted);
      font-size: 0.92rem;
    }
    @media (max-width: 860px) {
      .toolbar-grid { grid-template-columns: 1fr; }
      .card-head { flex-direction: column; }
    }
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <h1>Review Duplicate Phrase Readings</h1>
      <p>
        Pick the reading we should keep for duplicated HWXNet common-phrase rows.
        Your choices are saved in browser storage and can be exported as
        <code>__DECISIONS_FILENAME__</code>.
      </p>
      <div class="hero-actions">
        <button class="button" id="export-decisions">Export Decisions JSON</button>
        <label class="button secondary" for="import-decisions">Import Decisions JSON</label>
        <input id="import-decisions" type="file" accept="application/json" hidden>
        <button class="button ghost" id="clear-local">Clear Local Decisions</button>
      </div>
    </section>

    <section class="toolbar">
      <div class="toolbar-grid">
        <div class="field">
          <label for="search">Search</label>
          <input id="search" type="search" placeholder="Search by character, phrase, or reading">
        </div>
        <div class="field">
          <label for="filter-status">Filter</label>
          <select id="filter-status">
            <option value="all">All</option>
            <option value="undecided">Undecided only</option>
            <option value="keep_one">Choose one only</option>
            <option value="keep_both">Keep both only</option>
          </select>
        </div>
        <div class="field">
          <label for="sort-mode">Sort</label>
          <select id="sort-mode">
            <option value="undecided_first">Undecided first</option>
            <option value="character">Character</option>
          </select>
        </div>
      </div>
      <div class="stats" id="stats"></div>
    </section>

    <main class="cards" id="cards"></main>
    <div class="footer small" id="footer"></div>
  </div>

  <script>
    const REVIEW_DATA = __REVIEW_DATA_JSON__;
    const STORAGE_KEY = "common_phrase_duplicate_review_v1";

    const state = {
      decisions: loadStoredDecisions(),
      filter: "all",
      search: "",
      sortMode: "undecided_first",
    };

    const cardsEl = document.getElementById("cards");
    const statsEl = document.getElementById("stats");
    const footerEl = document.getElementById("footer");
    const searchEl = document.getElementById("search");
    const filterEl = document.getElementById("filter-status");
    const sortEl = document.getElementById("sort-mode");

    function loadStoredDecisions() {
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        return raw ? JSON.parse(raw) : {};
      } catch (err) {
        console.warn("Failed to load decisions from localStorage", err);
        return {};
      }
    }

    function saveStoredDecisions() {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state.decisions));
    }

    function itemKey(item) {
      return item.character + "::" + item.phrase;
    }

    function decisionStatus(decision) {
      if (!decision || !decision.mode) {
        return "undecided";
      }
      if (decision.mode === "keep_one") {
        return "keep_one";
      }
      if (decision.mode === "keep_both") {
        return "keep_both";
      }
      return "undecided";
    }

    function getVisibleItems() {
      const search = state.search.trim().toLowerCase();
      let items = REVIEW_DATA.items.filter((item) => {
        const key = itemKey(item);
        const decision = state.decisions[key];
        const status = decisionStatus(decision);
        if (state.filter === "undecided" && status !== "undecided") return false;
        if (state.filter === "keep_one" && status !== "keep_one") return false;
        if (state.filter === "keep_both" && status !== "keep_both") return false;
        if (!search) return true;
        const haystack = [
          item.character,
          item.phrase,
          ...(item.readings || []),
          ...(item.rows || []).map((row) => row.displayed_phrase_pinyin || ""),
        ].join(" ").toLowerCase();
        return haystack.includes(search);
      });

      items.sort((a, b) => {
        if (state.sortMode === "undecided_first") {
          const aStatus = decisionStatus(state.decisions[itemKey(a)]);
          const bStatus = decisionStatus(state.decisions[itemKey(b)]);
          if (aStatus !== bStatus) {
            if (aStatus === "undecided") return -1;
            if (bStatus === "undecided") return 1;
          }
        }
        if (a.character !== b.character) return a.character.localeCompare(b.character, "zh-Hans-CN");
        return a.phrase.localeCompare(b.phrase, "zh-Hans-CN");
      });
      return items;
    }

    function buildStats(visibleItems) {
      const total = REVIEW_DATA.items.length;
      let undecided = 0;
      let keepOne = 0;
      let keepBoth = 0;
      for (const item of REVIEW_DATA.items) {
        const status = decisionStatus(state.decisions[itemKey(item)]);
        if (status === "keep_one") keepOne += 1;
        else if (status === "keep_both") keepBoth += 1;
        else undecided += 1;
      }

      const parts = [
        ["Total duplicate phrases", total],
        ["Visible", visibleItems.length],
        ["Undecided", undecided],
        ["Choose one", keepOne],
        ["Keep both", keepBoth],
      ];
      statsEl.innerHTML = parts
        .map(([label, value]) => `<div class="stat"><strong>${value}</strong> ${label}</div>`)
        .join("");
      footerEl.textContent = "Decisions are stored in this browser until you export them.";
    }

    function render() {
      const visibleItems = getVisibleItems();
      buildStats(visibleItems);

      if (!visibleItems.length) {
        cardsEl.innerHTML = '<div class="empty">No duplicate phrases match the current filter.</div>';
        return;
      }

      cardsEl.innerHTML = visibleItems.map(renderCard).join("");
      bindCardHandlers();
    }

    function renderCard(item) {
      const key = itemKey(item);
      const decision = state.decisions[key] || {};
      const status = decisionStatus(decision);
      const statusLabel = status === "keep_one"
        ? `Choose one: ${decision.kept_readings ? decision.kept_readings[0] : ""}`
        : status === "keep_both"
          ? "Keep both"
          : "Undecided";

      const optionsHtml = item.rows.map((row, idx) => {
        const checked = decision.mode === "keep_one" && decision.kept_readings && decision.kept_readings[0] === row.reading;
        return `
          <div class="option">
            <label>
              <input
                type="radio"
                name="reading-${escapeAttr(key)}"
                value="${escapeAttr(row.reading)}"
                data-role="reading-option"
                data-key="${escapeAttr(key)}"
                ${checked ? "checked" : ""}
              >
              <div class="option-main">
                <div class="pinyin"><strong>${escapeHtml(row.reading)}</strong> · ${escapeHtml(row.displayed_phrase_pinyin || "")}</div>
                <div class="tiny">Candidate ${idx + 1}</div>
              </div>
            </label>
          </div>
        `;
      }).join("");

      return `
        <article class="card">
          <div class="card-head">
            <div>
              <div class="title">
                <span class="character">${escapeHtml(item.character)}</span>
                <span class="phrase">${escapeHtml(item.phrase)}</span>
              </div>
              <div class="meta">
                <span class="chip">Allowed: ${escapeHtml(item.allowed_readings.join(", "))}</span>
                <span class="chip"><a href="${escapeAttr(item.source_url)}" target="_blank" rel="noreferrer">HWXNet source</a></span>
              </div>
            </div>
            <div class="status-pill ${status === "keep_one" ? "decided-keep-one" : status === "keep_both" ? "decided-keep-both" : "undecided"}">${escapeHtml(statusLabel)}</div>
          </div>

          <div class="decision-row">
            <label>
              <input
                type="radio"
                name="mode-${escapeAttr(key)}"
                value="keep_one"
                data-role="mode"
                data-key="${escapeAttr(key)}"
                ${decision.mode === "keep_one" ? "checked" : ""}
              >
              Choose one reading
            </label>
            <label>
              <input
                type="radio"
                name="mode-${escapeAttr(key)}"
                value="keep_both"
                data-role="mode"
                data-key="${escapeAttr(key)}"
                ${decision.mode === "keep_both" ? "checked" : ""}
              >
              Keep both
            </label>
            <label>
              <input
                type="radio"
                name="mode-${escapeAttr(key)}"
                value="undecided"
                data-role="mode"
                data-key="${escapeAttr(key)}"
                ${!decision.mode || decision.mode === "undecided" ? "checked" : ""}
              >
              Leave undecided
            </label>
          </div>

          <div class="options">${optionsHtml}</div>

          <div class="notes">
            <label class="small" for="note-${escapeAttr(key)}">Notes</label>
            <textarea id="note-${escapeAttr(key)}" data-role="note" data-key="${escapeAttr(key)}" placeholder="Optional review note">${escapeHtml(decision.notes || "")}</textarea>
          </div>
        </article>
      `;
    }

    function bindCardHandlers() {
      document.querySelectorAll('[data-role="mode"]').forEach((el) => {
        el.addEventListener("change", (event) => {
          const key = event.target.dataset.key;
          const mode = event.target.value;
          const existing = state.decisions[key] || {};
          if (mode === "undecided") {
            state.decisions[key] = { mode: "undecided", notes: existing.notes || "" };
          } else if (mode === "keep_both") {
            const item = REVIEW_DATA.items.find((candidate) => itemKey(candidate) === key);
            state.decisions[key] = {
              mode: "keep_both",
              kept_readings: item.readings.slice(),
              notes: existing.notes || "",
            };
          } else {
            state.decisions[key] = {
              mode: "keep_one",
              kept_readings: existing.kept_readings && existing.kept_readings.length ? existing.kept_readings.slice(0, 1) : [],
              notes: existing.notes || "",
            };
          }
          saveStoredDecisions();
          render();
        });
      });

      document.querySelectorAll('[data-role="reading-option"]').forEach((el) => {
        el.addEventListener("change", (event) => {
          const key = event.target.dataset.key;
          const reading = event.target.value;
          const existing = state.decisions[key] || {};
          state.decisions[key] = {
            mode: "keep_one",
            kept_readings: [reading],
            notes: existing.notes || "",
          };
          saveStoredDecisions();
          render();
        });
      });

      document.querySelectorAll('[data-role="note"]').forEach((el) => {
        el.addEventListener("change", (event) => {
          const key = event.target.dataset.key;
          const existing = state.decisions[key] || {};
          state.decisions[key] = {
            mode: existing.mode || "undecided",
            kept_readings: existing.kept_readings || [],
            notes: event.target.value,
          };
          saveStoredDecisions();
          render();
        });
      });
    }

    function exportDecisions() {
      const payload = {
        generated_at: new Date().toISOString(),
        source_artifact: REVIEW_DATA.source_artifact,
        item_count: REVIEW_DATA.items.length,
        decisions: Object.entries(state.decisions)
          .filter(([, value]) => value && value.mode && value.mode !== "undecided")
          .map(([key, value]) => {
            const [character, phrase] = key.split("::");
            return {
              character,
              phrase,
              mode: value.mode,
              kept_readings: value.kept_readings || [],
              notes: value.notes || "",
            };
          }),
      };
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "__DECISIONS_FILENAME__";
      a.click();
      URL.revokeObjectURL(url);
    }

    function importDecisions(file) {
      const reader = new FileReader();
      reader.onload = () => {
        const parsed = JSON.parse(reader.result);
        const next = {};
        for (const decision of parsed.decisions || []) {
          const key = decision.character + "::" + decision.phrase;
          next[key] = {
            mode: decision.mode,
            kept_readings: decision.kept_readings || [],
            notes: decision.notes || "",
          };
        }
        state.decisions = next;
        saveStoredDecisions();
        render();
      };
      reader.readAsText(file);
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }

    function escapeAttr(value) {
      return escapeHtml(value).replaceAll("'", "&#39;");
    }

    document.getElementById("export-decisions").addEventListener("click", exportDecisions);
    document.getElementById("import-decisions").addEventListener("change", (event) => {
      const file = event.target.files && event.target.files[0];
      if (file) {
        importDecisions(file);
      }
      event.target.value = "";
    });
    document.getElementById("clear-local").addEventListener("click", () => {
      if (!confirm("Clear all locally stored decisions for this review page?")) {
        return;
      }
      state.decisions = {};
      saveStoredDecisions();
      render();
    });
    searchEl.addEventListener("input", (event) => {
      state.search = event.target.value || "";
      render();
    });
    filterEl.addEventListener("change", (event) => {
      state.filter = event.target.value;
      render();
    });
    sortEl.addEventListener("change", (event) => {
      state.sortMode = event.target.value;
      render();
    });

    render();
  </script>
</body>
</html>
"""


def load_duplicates() -> dict:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    items = []
    for character, payload in data.items():
        by_phrase = defaultdict(list)
        readings_by_phrase = defaultdict(set)
        for row in payload.get("common_phrase_readings", []):
            phrase = row.get("phrase")
            reading = row.get("reading")
            by_phrase[phrase].append(row)
            if reading is not None:
                readings_by_phrase[phrase].add(reading)
        for phrase, readings in readings_by_phrase.items():
            if len(readings) > 1:
                items.append(
                    {
                        "character": character,
                        "phrase": phrase,
                        "allowed_readings": payload.get("allowed_readings", []),
                        "source_url": payload.get("source_url", ""),
                        "readings": sorted(readings),
                        "rows": by_phrase[phrase],
                    }
                )
    items.sort(key=lambda item: (item["character"], item["phrase"]))
    return {
        "source_artifact": str(DATA_PATH),
        "item_count": len(items),
        "items": items,
    }


def main() -> None:
    review_data = load_duplicates()
    html = HTML_TEMPLATE.replace("__REVIEW_DATA_JSON__", json.dumps(review_data, ensure_ascii=False))
    html = html.replace("__DECISIONS_FILENAME__", DECISIONS_FILENAME)
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"Wrote {OUTPUT_HTML}")
    print(f"Embedded {review_data['item_count']} duplicate phrase cases.")


if __name__ == "__main__":
    main()
