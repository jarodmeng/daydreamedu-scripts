# Chinese Character App (meta)

This folder contains the **Chinese Character Learning App** (web app + backend) and **utility scripts** for extracting and processing character data from the 冯氏早教识字卡 PDF card set. The app lives in the inner `chinese_chr_app/` directory; this README describes the folder as a whole.

---

## Structure

```
chinese_chr_app/                    # You are here (meta)
├── chinese_chr_app/                # Main web application
│   ├── README.md                   # App setup, quick start, troubleshooting
│   ├── docs/                       # VISION, ARCHITECTURE, CHANGELOG, archive
│   ├── backend/                    # Flask API
│   ├── frontend/                   # React (Vite)
│   └── data/                       # JSON + optional PNGs
│
├── extract_characters_using_ai/   # AI-based extraction (OpenAI Batch API)
├── extract_using_local_ocr/       # Local OCR (Tesseract; reference only)
└── generate_png/                   # PDF → PNG conversion
```

---

## The app

The **Chinese Character Learning App** is a full-stack web app for primary school students to learn simplified Chinese: character search, pinyin search, radicals, stroke counts, stroke-order animation, and a personalized pinyin-recall learning game.

- **Setup, quick start, production URLs, troubleshooting:** [chinese_chr_app/README.md](chinese_chr_app/README.md)
- **Product strategy and vision:** [chinese_chr_app/docs/VISION.md](chinese_chr_app/docs/VISION.md)
- **Technical specs and API:** [chinese_chr_app/docs/ARCHITECTURE.md](chinese_chr_app/docs/ARCHITECTURE.md)
- **Version history:** [chinese_chr_app/docs/CHANGELOG.md](chinese_chr_app/docs/CHANGELOG.md)

**Quick start (from repo root):**

```bash
# Backend
cd chinese_chr_app/chinese_chr_app/backend && pip3 install -r requirements.txt && python3 app.py   # → http://localhost:5001

# Frontend
cd chinese_chr_app/chinese_chr_app/frontend && npm install && npm run dev   # → http://localhost:3000
```

---

## Utilities

Scripts for getting character data from PDFs and images. The **app** consumes the resulting JSON (and optional PNGs); it does not run the extraction pipelines.

| Folder | Purpose | Status |
|--------|---------|--------|
| **extract_characters_using_ai/** | Extract structured character data via OpenAI Batch API (vision). Output: JSON/CSV. | ✅ Recommended |
| **extract_using_local_ocr/** | Local Tesseract OCR extraction. | ⚠️ Reference only; lower accuracy |
| **generate_png/** | Convert PDF pages to PNGs (e.g. `png/<dddd>/page1.png`, `page2.png`). | ✅ Optional; AI pipeline can use PDFs directly |

**Data flow:** PDFs (冯氏早教识字卡) → extraction (AI or OCR) → JSON (+ optional PNGs) → app `data/` or Supabase.

For extraction workflow and commands, see the README or scripts inside each utility folder.

---

## Where to go

- **Use or develop the web app** → [chinese_chr_app/README.md](chinese_chr_app/README.md) and `chinese_chr_app/docs/`
- **Extract character data from PDFs** → `extract_characters_using_ai/` (or `generate_png/` if you need PNGs first)
- **Local OCR (reference)** → `extract_using_local_ocr/`
