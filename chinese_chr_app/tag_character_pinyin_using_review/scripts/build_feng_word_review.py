#!/usr/bin/env python3
"""
Build a local HTML review tool for Feng word reading decisions.

Usage:
  python3 chinese_chr_app/tag_character_pinyin_using_ai/scripts/build_feng_word_review.py
"""

from __future__ import annotations

import json
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
DATA_PATH = ROOT / "review" / "feng_word_review_data.json"
REVIEW_DIR = ROOT / "review"
OUTPUT_HTML = REVIEW_DIR / "feng_word_reading_review.html"


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Feng Word Reading Review</title>
  <style>
    :root {
      --bg: #f3efe7;
      --panel: #fffdf9;
      --ink: #1f1a14;
      --muted: #6d6154;
      --line: #d8ccbb;
      --accent: #8c3d1f;
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
    .page { max-width: 1180px; margin: 0 auto; padding: 28px 18px 56px; }
    .hero, .toolbar, .card {
      background: var(--panel);
      border: 1px solid rgba(140, 61, 31, 0.12);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }
    .hero { padding: 26px 24px 20px; margin-bottom: 18px; }
    h1 { margin: 0 0 10px; font-size: clamp(2rem, 4vw, 3.2rem); line-height: 0.95; letter-spacing: -0.03em; }
    .hero p { margin: 0; color: var(--muted); font-size: 0.98rem; line-height: 1.45; }
    .hero-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }
    .toolbar { padding: 16px; margin-bottom: 18px; }
    .toolbar-grid { display: grid; grid-template-columns: 1.1fr 0.8fr 0.8fr; gap: 12px; align-items: end; }
    .field label {
      display: block; font-size: 0.82rem; color: var(--muted); margin-bottom: 6px;
      text-transform: uppercase; letter-spacing: 0.06em;
    }
    input[type="search"], select, textarea {
      width: 100%; padding: 10px 12px; border-radius: 12px; border: 1px solid var(--line);
      background: #fff; font: inherit; color: var(--ink);
    }
    .stats { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }
    .stat { background: var(--pill); border-radius: 999px; padding: 8px 12px; font-size: 0.92rem; }
    .button {
      border: 0; border-radius: 999px; padding: 10px 14px; font: inherit; cursor: pointer;
      background: var(--ink); color: #fff;
    }
    .button.secondary { background: #eadfd1; color: var(--ink); }
    .cards { display: grid; gap: 16px; }
    .card { padding: 18px; }
    .card-head { display: flex; justify-content: space-between; align-items: start; gap: 12px; margin-bottom: 12px; }
    .title { display: flex; flex-wrap: wrap; align-items: baseline; gap: 10px; }
    .title .character { font-size: 2rem; font-weight: 700; line-height: 1; }
    .status-pill { border-radius: 999px; padding: 7px 12px; font-size: 0.84rem; background: #f1e8dc; color: var(--ink); white-space: nowrap; }
    .status-pill.complete { background: #e4f1e6; color: var(--good); }
    .status-pill.partial { background: #f7ead7; color: var(--warn); }
    .status-pill.undecided { background: #efe4d6; color: var(--ink); }
    .meta { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; color: var(--muted); font-size: 0.92rem; }
    .meta .chip { background: #f7f1e9; border-radius: 999px; padding: 6px 10px; }
    .reading-manager {
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
      background: #fff9f3;
      margin-bottom: 14px;
    }
    .reading-manager-grid {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
      align-items: end;
    }
    .reading-list {
      color: var(--muted);
      font-size: 0.92rem;
      margin-bottom: 8px;
    }
    .manual-box, .bulk-box {
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
      background: #faf5ee;
      margin-bottom: 14px;
    }
    .manual-grid {
      display: grid;
      grid-template-columns: 1.3fr 0.9fr 1fr auto;
      gap: 10px;
      align-items: end;
    }
    .manual-list {
      display: grid;
      gap: 10px;
      margin-top: 12px;
    }
    .manual-item {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
      align-items: start;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px;
      background: #fff;
    }
    .manual-item-meta {
      color: var(--muted);
      font-size: 0.9rem;
      margin-top: 4px;
    }
    .manual-item-text {
      font-size: 1.05rem;
      font-weight: 700;
    }
    .word-source {
      display: inline-block;
      margin-left: 8px;
      font-size: 0.8rem;
      color: var(--muted);
      font-weight: 400;
    }
    .bulk-grid {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr auto;
      gap: 10px;
      align-items: end;
    }
    .bulk-help {
      color: var(--muted);
      font-size: 0.9rem;
      margin-bottom: 10px;
    }
    .words { display: grid; gap: 12px; }
    .word-row { border: 1px solid var(--line); border-radius: 14px; padding: 12px; background: #fff; }
    .word-head { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 10px; margin-bottom: 8px; }
    .word-label { display: flex; gap: 10px; align-items: baseline; }
    .word-index { color: var(--muted); min-width: 2.5rem; }
    .word-text { font-size: 1.2rem; font-weight: 700; }
    .neighbor { color: var(--muted); font-size: 0.9rem; }
    .reading-options { display: flex; flex-wrap: wrap; gap: 8px; }
    .reading-options label { display: inline-flex; align-items: center; gap: 8px; padding: 8px 12px; border-radius: 999px; background: #f5eee5; cursor: pointer; }
    .word-notes { margin-top: 10px; }
    .empty {
      text-align: center; color: var(--muted); padding: 48px 20px; background: rgba(255,255,255,0.65);
      border-radius: var(--radius); border: 1px dashed rgba(140, 61, 31, 0.25);
    }
    @media (max-width: 860px) {
      .toolbar-grid { grid-template-columns: 1fr; }
      .card-head { flex-direction: column; }
      .reading-manager-grid { grid-template-columns: 1fr; }
      .bulk-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <h1>Review Feng Word Readings</h1>
      <p>Choose the reading of the target character for each Feng word. Decisions are saved in local storage and can be exported as <code>feng_word_reading_decisions.json</code>.</p>
      <div class="hero-actions">
        <button class="button" id="export-button">Export Decisions JSON</button>
        <button class="button secondary" id="clear-button">Clear Local Decisions</button>
      </div>
    </section>
    <section class="toolbar">
      <div class="toolbar-grid">
        <div class="field">
          <label for="search">Search</label>
          <input id="search" type="search" placeholder="Search by character">
        </div>
        <div class="field">
          <label for="filter">Show</label>
          <select id="filter">
            <option value="all">All characters</option>
            <option value="missing_coverage">Missing pinyin coverage</option>
            <option value="needs_review">Needs review</option>
            <option value="partial">Partially decided</option>
            <option value="complete">Fully decided</option>
          </select>
        </div>
        <div class="field">
          <label for="jump">Jump To Character</label>
          <select id="jump"></select>
        </div>
      </div>
      <div class="stats" id="stats"></div>
    </section>
    <section class="cards" id="cards"></section>
  </div>
  <script>
    const REVIEW_DATA = __REVIEW_DATA__;
    const STORAGE_KEY = "feng-word-reading-review-decisions-v1";
    const searchInput = document.getElementById("search");
    const filterSelect = document.getElementById("filter");
    const jumpSelect = document.getElementById("jump");
    const statsEl = document.getElementById("stats");
    const cardsEl = document.getElementById("cards");
    const exportButton = document.getElementById("export-button");
    const clearButton = document.getElementById("clear-button");

    function loadState() {
      try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"); }
      catch (err) { return {}; }
    }
    function saveState(state) { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }
    let state = loadState();

    function getManualWords(character) {
      const saved = state[character.character] || {};
      const words = Array.isArray(saved.__manual_words) ? saved.__manual_words : [];
      return words.filter((word) => word && typeof word.text === "string" && word.text.trim()).map((word) => ({
        text: word.text.trim(),
        reading: typeof word.reading === "string" ? word.reading.trim() : "",
        notes: typeof word.notes === "string" ? word.notes : "",
        source: "manual_word"
      }));
    }

    function getAllWords(character) {
      const baseWords = character.words.map((word) => ({ ...word, source: "feng_word", isManual: false }));
      const manualWords = getManualWords(character).map((word, index) => ({
        position: character.words.length + index + 1,
        text: word.text,
        previous_word: null,
        next_word: null,
        source: word.source,
        notes: word.notes,
        manualReading: word.reading,
        isManual: true
      }));
      return [...baseWords, ...manualWords];
    }

    function getCharacterReadings(character) {
      const saved = state[character.character] || {};
      const extras = Array.isArray(saved.__extra_readings) ? saved.__extra_readings : [];
      return [...character.allowed_readings, ...extras.filter((reading) => !character.allowed_readings.includes(reading))];
    }

    function characterStatus(character) {
      const saved = state[character.character] || {};
      const allWords = getAllWords(character);
      const total = allWords.length;
      const decided = allWords.filter((word) => {
        if (word.isManual) return word.manualReading;
        return saved[word.text] && saved[word.text].reading;
      }).length;
      if (decided === 0) return { key: "undecided", label: "Undecided", decided, total };
      if (decided === total) return { key: "complete", label: "Complete", decided, total };
      return { key: "partial", label: "Partial", decided, total };
    }

    function missingAllowedReadings(character) {
      const counts = new Map();
      getAllWords(character).forEach((word) => {
        const reading = word.isManual
          ? (word.manualReading || "")
          : ((state[character.character] || {})[word.text]?.reading || "");
        if (!reading || reading === "unknown") return;
        counts.set(reading, (counts.get(reading) || 0) + 1);
      });
      return character.allowed_readings.filter((reading) => !counts.get(reading));
    }

    function filteredCharacters() {
      const search = searchInput.value.trim();
      const filter = filterSelect.value;
      return REVIEW_DATA.filter((character) => {
        const status = characterStatus(character);
        const missingCoverage = missingAllowedReadings(character);
        if (filter === "missing_coverage" && !missingCoverage.length) return false;
        if (filter === "missing_coverage") return !search || character.character.includes(search);
        if (filter === "needs_review" && status.key === "complete") return false;
        if (filter !== "all" && filter !== "needs_review" && status.key !== filter) return false;
        if (!search) return true;
        return character.character.includes(search);
      });
    }
    function updateStats() {
      const totalCharacters = REVIEW_DATA.length;
      const totalWords = REVIEW_DATA.reduce((sum, item) => sum + getAllWords(item).length, 0);
      const decidedWords = REVIEW_DATA.reduce((sum, item) => {
        const saved = state[item.character] || {};
        return sum + getAllWords(item).filter((word) => {
          if (word.isManual) return word.manualReading;
          return saved[word.text] && saved[word.text].reading;
        }).length;
      }, 0);
      const completeCharacters = REVIEW_DATA.filter((item) => characterStatus(item).key === "complete").length;
      statsEl.innerHTML = "";
      [`Characters: ${totalCharacters}`, `Words: ${totalWords}`, `Decided Words: ${decidedWords}`, `Completed Characters: ${completeCharacters}`].forEach((text) => {
        const el = document.createElement("div");
        el.className = "stat";
        el.textContent = text;
        statsEl.appendChild(el);
      });
    }
    function exportDecisions() {
      const payload = REVIEW_DATA.map((character) => {
        const saved = state[character.character] || {};
        const manualWords = getManualWords(character);
        return {
          character: character.character,
          allowed_readings: character.allowed_readings,
          extra_readings: saved.__extra_readings || [],
          words: [
            ...character.words.map((word) => ({
              text: word.text,
              reading: saved[word.text]?.reading || "",
              notes: saved[word.text]?.notes || "",
              source: "feng_word"
            })),
            ...manualWords.map((word) => ({
              text: word.text,
              reading: word.reading || "",
              notes: word.notes || "",
              source: "manual_word"
            }))
          ]
        };
      });
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "feng_word_reading_decisions.json";
      a.click();
      URL.revokeObjectURL(url);
    }
    function renderJumpOptions() {
      jumpSelect.innerHTML = '<option value="">Select character</option>';
      REVIEW_DATA.forEach((character) => {
        const option = document.createElement("option");
        option.value = character.character;
        option.textContent = `${character.character} (${character.words.length})`;
        jumpSelect.appendChild(option);
      });
    }
    function renderCards() {
      const items = filteredCharacters();
      cardsEl.innerHTML = "";
      if (!items.length) {
        const empty = document.createElement("div");
        empty.className = "empty";
        empty.textContent = "No characters match the current search/filter.";
        cardsEl.appendChild(empty);
        return;
      }
      items.forEach((character) => {
        const saved = state[character.character] || {};
        const status = characterStatus(character);
        const card = document.createElement("article");
        card.className = "card";
        card.id = `char-${character.character}`;
        const head = document.createElement("div");
        head.className = "card-head";
        head.innerHTML = `
          <div>
            <div class="title"><span class="character">${character.character}</span></div>
            <div class="meta">
              <span class="chip">Allowed: ${character.allowed_readings.join(", ")}</span>
              <span class="chip">Words: ${getAllWords(character).length}</span>
              ${missingAllowedReadings(character).length ? `<span class="chip">Missing coverage: ${missingAllowedReadings(character).join(", ")}</span>` : ""}
            </div>
          </div>
          <span class="status-pill ${status.key}">${status.label} ${status.decided}/${status.total}</span>
        `;
        card.appendChild(head);
        const readingManager = document.createElement("div");
        readingManager.className = "reading-manager";
        const currentReadings = getCharacterReadings(character);
        readingManager.innerHTML = `
          <div class="reading-list">Current readings: ${currentReadings.join(", ")}</div>
          <div class="reading-manager-grid">
            <div class="field">
              <label>Add Missing Reading</label>
              <input class="extra-reading-input" type="text" placeholder="e.g. piǎo">
            </div>
            <button class="button extra-reading-apply" type="button">Add Reading</button>
          </div>
        `;
        const extraInput = readingManager.querySelector(".extra-reading-input");
        const extraApply = readingManager.querySelector(".extra-reading-apply");
        extraApply.addEventListener("click", () => {
          const value = extraInput.value.trim();
          if (!value) return;
          state[character.character] = state[character.character] || {};
          const extras = Array.isArray(state[character.character].__extra_readings)
            ? state[character.character].__extra_readings
            : [];
          if (!character.allowed_readings.includes(value) && !extras.includes(value)) {
            extras.push(value);
          }
          state[character.character].__extra_readings = extras;
          saveState(state);
          renderCards();
        });
        card.appendChild(readingManager);
        const manualBox = document.createElement("div");
        manualBox.className = "manual-box";
        const currentReadingsForManual = getCharacterReadings(character)
          .map((reading) => `<option value="${reading}">${reading}</option>`)
          .join("");
        const manualWords = getManualWords(character);
        manualBox.innerHTML = `
          <div class="bulk-help">Add missing words manually when a reading is real for this Feng character but the extracted word list missed the examples.</div>
          <div class="manual-grid">
            <div class="field">
              <label>Missing Word</label>
              <input class="manual-word-text" type="text" placeholder="e.g. 阿姨">
            </div>
            <div class="field">
              <label>Reading</label>
              <select class="manual-word-reading">${currentReadingsForManual}</select>
            </div>
            <div class="field">
              <label>Notes</label>
              <input class="manual-word-notes" type="text" placeholder="Optional note">
            </div>
            <button class="button manual-word-apply" type="button">Add Word</button>
          </div>
          <div class="manual-list"></div>
        `;
        const manualText = manualBox.querySelector(".manual-word-text");
        const manualReading = manualBox.querySelector(".manual-word-reading");
        const manualNotes = manualBox.querySelector(".manual-word-notes");
        const manualApply = manualBox.querySelector(".manual-word-apply");
        const manualList = manualBox.querySelector(".manual-list");
        manualApply.addEventListener("click", () => {
          const text = manualText.value.trim();
          const reading = manualReading.value.trim();
          const notes = manualNotes.value;
          if (!text || !reading) return;
          state[character.character] = state[character.character] || {};
          const existing = Array.isArray(state[character.character].__manual_words)
            ? state[character.character].__manual_words
            : [];
          const alreadyExists = character.words.some((word) => word.text === text) || existing.some((word) => (word.text || "").trim() === text);
          if (alreadyExists) return;
          existing.push({ text, reading, notes });
          state[character.character].__manual_words = existing;
          saveState(state);
          updateStats();
          renderCards();
        });
        manualWords.forEach((word, index) => {
          const item = document.createElement("div");
          item.className = "manual-item";
          item.innerHTML = `
            <div>
              <div class="manual-item-text">${word.text}</div>
              <div class="manual-item-meta">Reading: ${word.reading || "—"} | Notes: ${word.notes || "—"}</div>
            </div>
            <button class="button secondary" type="button">Remove</button>
          `;
          item.querySelector("button").addEventListener("click", () => {
            state[character.character] = state[character.character] || {};
            const existing = Array.isArray(state[character.character].__manual_words)
              ? state[character.character].__manual_words
              : [];
            existing.splice(index, 1);
            state[character.character].__manual_words = existing;
            saveState(state);
            updateStats();
            renderCards();
          });
          manualList.appendChild(item);
        });
        card.appendChild(manualBox);
        const bulkBox = document.createElement("div");
        bulkBox.className = "bulk-box";
        const readingOptions = [...getCharacterReadings(character), "unknown"]
          .map((reading) => `<option value="${reading}">${reading}</option>`)
          .join("");
        const allWords = getAllWords(character);
        const wordOptions = allWords
          .map((word) => `<option value="${word.position}">${word.position}. ${word.text}</option>`)
          .join("");
        bulkBox.innerHTML = `
          <div class="bulk-help">Bulk assign one reading to a consecutive Feng-word range. This follows the way Feng words are usually clustered by reading.</div>
          <div class="bulk-grid">
            <div class="field">
              <label>Start Word</label>
              <select class="bulk-start">${wordOptions}</select>
            </div>
            <div class="field">
              <label>End Word</label>
              <select class="bulk-end">${wordOptions}</select>
            </div>
            <div class="field">
              <label>Reading</label>
              <select class="bulk-reading">${readingOptions}</select>
            </div>
            <button class="button bulk-apply" type="button">Apply Range</button>
          </div>
        `;
        const startSelect = bulkBox.querySelector(".bulk-start");
        const endSelect = bulkBox.querySelector(".bulk-end");
        const readingSelect = bulkBox.querySelector(".bulk-reading");
        const applyButton = bulkBox.querySelector(".bulk-apply");
        applyButton.addEventListener("click", () => {
          let start = Number(startSelect.value);
          let end = Number(endSelect.value);
          if (!Number.isFinite(start) || !Number.isFinite(end)) return;
          if (start > end) {
            const temp = start;
            start = end;
            end = temp;
          }
          const reading = readingSelect.value;
          state[character.character] = state[character.character] || {};
          allWords.forEach((word) => {
            if (word.position < start || word.position > end) return;
            if (word.isManual) {
              const existing = Array.isArray(state[character.character].__manual_words)
                ? state[character.character].__manual_words
                : [];
              const match = existing.find((item) => (item.text || "").trim() === word.text);
              if (match) {
                match.reading = reading;
                match.notes = match.notes || "";
              }
              return;
            }
            state[character.character][word.text] = state[character.character][word.text] || {};
            state[character.character][word.text].reading = reading;
            state[character.character][word.text].notes = state[character.character][word.text].notes || "";
          });
          saveState(state);
          updateStats();
          renderCards();
        });
        card.appendChild(bulkBox);
        const words = document.createElement("div");
        words.className = "words";
        allWords.forEach((word) => {
          const wordSaved = saved[word.text] || {};
          const manualSaved = word.isManual
            ? getManualWords(character).find((item) => item.text === word.text) || {}
            : {};
          const row = document.createElement("div");
          row.className = "word-row";
          row.innerHTML = `
            <div class="word-head">
              <div class="word-label">
                <span class="word-index">${word.position}.</span>
                <span class="word-text">${word.text}<span class="word-source">${word.isManual ? "manual" : "feng"}</span></span>
              </div>
              <div class="neighbor">Prev: ${word.previous_word || "—"} | Next: ${word.next_word || "—"}</div>
            </div>
          `;
          const options = document.createElement("div");
          options.className = "reading-options";
          [...getCharacterReadings(character), "unknown"].forEach((reading) => {
            const label = document.createElement("label");
            const isChecked = word.isManual ? manualSaved.reading === reading : wordSaved.reading === reading;
            label.innerHTML = `<input type="radio" name="${character.character}::${word.text}" value="${reading}" ${isChecked ? "checked" : ""}><span>${reading}</span>`;
            options.appendChild(label);
          });
          row.appendChild(options);
          const notes = document.createElement("div");
          notes.className = "word-notes";
          notes.innerHTML = `<textarea placeholder="Optional notes">${word.isManual ? (manualSaved.notes || "") : (wordSaved.notes || "")}</textarea>`;
          row.appendChild(notes);
          options.querySelectorAll("input").forEach((input) => {
            input.addEventListener("change", () => {
              state[character.character] = state[character.character] || {};
              if (word.isManual) {
                const existing = Array.isArray(state[character.character].__manual_words)
                  ? state[character.character].__manual_words
                  : [];
                const match = existing.find((item) => (item.text || "").trim() === word.text);
                if (match) {
                  match.reading = input.value;
                  match.notes = row.querySelector("textarea").value;
                }
                saveState(state);
                updateStats();
                renderCards();
                return;
              }
              state[character.character][word.text] = state[character.character][word.text] || {};
              state[character.character][word.text].reading = input.value;
              state[character.character][word.text].notes = row.querySelector("textarea").value;
              saveState(state);
              updateStats();
              renderCards();
            });
          });
          row.querySelector("textarea").addEventListener("input", (event) => {
            state[character.character] = state[character.character] || {};
            if (word.isManual) {
              const existing = Array.isArray(state[character.character].__manual_words)
                ? state[character.character].__manual_words
                : [];
              const match = existing.find((item) => (item.text || "").trim() === word.text);
              if (match) {
                match.reading = match.reading || "";
                match.notes = event.target.value;
              }
              saveState(state);
              return;
            }
            state[character.character][word.text] = state[character.character][word.text] || {};
            state[character.character][word.text].reading = state[character.character][word.text].reading || "";
            state[character.character][word.text].notes = event.target.value;
            saveState(state);
          });
          words.appendChild(row);
        });
        card.appendChild(words);
        cardsEl.appendChild(card);
      });
    }
    searchInput.addEventListener("input", renderCards);
    filterSelect.addEventListener("change", renderCards);
    jumpSelect.addEventListener("change", () => {
      const value = jumpSelect.value;
      if (!value) return;
      document.getElementById(`char-${value}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    exportButton.addEventListener("click", exportDecisions);
    clearButton.addEventListener("click", () => {
      localStorage.removeItem(STORAGE_KEY);
      state = {};
      updateStats();
      renderCards();
    });
    renderJumpOptions();
    updateStats();
    renderCards();
  </script>
</body>
</html>
"""


def main() -> None:
    review_data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    html = HTML_TEMPLATE.replace("__REVIEW_DATA__", json.dumps(review_data, ensure_ascii=False))
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"Wrote review tool to {OUTPUT_HTML}")
    print(f"Characters: {len(review_data)}")


if __name__ == "__main__":
    main()
