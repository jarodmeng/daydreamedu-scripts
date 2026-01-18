# Chinese Learning App

This folder contains a web application for learning Chinese characters, along with utility scripts for extracting and processing character data from PDF card sets.

## Overview

The Chinese Learning App is a full-stack web application that helps primary school students learn simplified Chinese characters. The app displays character cards with detailed information including pinyin, radicals, stroke counts, example sentences, and word combinations.

This repository also includes utility scripts for extracting structured character data from the 冯氏早教识字卡 PDF card set.

## Project Structure

```
chinese_chr_app/
├── chinese_chr_app/              # Main web application
│   ├── backend/                   # Flask API server
│   ├── frontend/                  # React frontend
│   └── README.md                  # Detailed app documentation
│
├── extract_characters_using_ai/  # Utility: AI-based character extraction
│   └── (scripts for OpenAI Batch API extraction)
│
├── extract_using_local_ocr/      # Utility: Local OCR extraction
│   └── extract_feng_cards.py
│
└── generate_png/                 # Utility: PDF to PNG conversion
    └── generate_png_from_pdfs.py
```

## Main Application

The **Chinese Character Learning App** (`chinese_chr_app/chinese_chr_app/`) is a web application that provides an interactive interface for searching and viewing Chinese character cards.

### Features
- Search for Chinese characters by entering a single character
- Display both sides of character cards (front and back)
- Show detailed information: pinyin, radical, strokes, structure, example sentences, and word combinations

### Quick Start

See the detailed documentation in [`chinese_chr_app/README.md`](chinese_chr_app/README.md) for:
- Setup instructions (backend and frontend)
- API endpoints
- Usage guide

**Quick commands:**
```bash
# Backend (Flask API)
cd chinese_chr_app/backend
pip3 install -r requirements.txt
python3 app.py  # Runs on http://localhost:5001

# Frontend (React)
cd chinese_chr_app/frontend
npm install
npm run dev  # Runs on http://localhost:3000
```

## Utility Scripts

These utilities are used to extract and process character data from PDF card sets.

### 1. AI-Based Character Extraction (`extract_characters_using_ai/`)

**Purpose**: Extract structured character data using OpenAI's vision models via Batch API.

**Status**: ✅ **Recommended approach** - High accuracy with validation

**Key Features**:
- Uses OpenAI Batch API with GPT-5-mini vision model
- Extracts: Index, Character, Pinyin, Radical, Strokes, Structure, Sentence (例句), Words (词组)
- Includes character validation to prevent OCR errors
- Processes PDFs directly (no pre-processing needed)

**Main Scripts**:
- `make_batch_jsonl_per_character.py` - Generate batch requests from PDFs
- `upload_batch.py` - Upload and manage batch jobs
- `parse_results.py` - Parse results into CSV/JSON
- `verify_results.py` - Validate extracted characters

**Quick Start**:
```bash
cd extract_characters_using_ai

# 1. Generate requests
python3 make_batch_jsonl_per_character.py \
  --pdf_dir "/path/to/冯氏早教识字卡/" \
  --prompt_md ./chinese_character_extraction_prompt.md \
  --out_jsonl jsonl/requests.jsonl \
  --dpi 250

# 2. Upload batch (requires OPENAI_API_KEY)
python3 upload_batch.py --jsonl jsonl/requests.jsonl --output jsonl/results.jsonl

# 3. Parse results
python3 parse_results.py \
  --input jsonl/results.jsonl \
  --json ../data/characters.json \
  --validate --stats
```

**Documentation**: See `extract_characters_using_ai/` folder for detailed scripts and usage.

### 2. Local OCR Extraction (`extract_using_local_ocr/`)

**Purpose**: Extract character data using local Tesseract OCR.

**Status**: ⚠️ **Not recommended** - Lower accuracy, kept for reference

**Approach**:
- Uses Tesseract OCR with `chi_sim` language model
- Renders PDF pages with `pdftoppm`
- OCRs specific regions (center for character, top-right for index)

**Limitations**:
- OCR struggles with some fonts and low-resolution scans
- Index numbers and some characters are unreliable
- Kept for historical reference and possible hybrid use

**Script**: `extract_using_local_ocr/extract_feng_cards.py`

### 3. PNG Generation (`generate_png/`)

**Purpose**: Pre-process PDF files by extracting individual pages as PNG images.

**Use Cases**:
- Extract PNG files before running extraction pipelines
- Manual inspection of character cards
- Image-based workflows

**Features**:
- Reads PDF files (named like `0001-0010.pdf`)
- Extracts all pages as PNG files
- Creates organized folder structure: `png/<dddd>/` for each character
- Each character folder contains 2 PNG files (page 1 and page 2)

**Usage**:
```bash
cd generate_png
python3 generate_png_from_pdfs.py \
  --pdf_dir "/path/to/冯氏早教识字卡/" \
  --output_dir "/path/to/冯氏早教识字卡/png" \
  --dpi 300
```

**Note**: The AI extraction pipeline can work directly from PDFs, so this script is optional unless you specifically need standalone PNG files.

## Data Flow

1. **PDF Source**: 冯氏早教识字卡 PDF card set
2. **Extraction**: Use `extract_characters_using_ai/` to extract structured data
3. **Output**: CSV/JSON files with character data
4. **Application**: Main app (`chinese_chr_app/`) uses this data to display character cards

## Current Status

- **Main App**: ✅ Functional web application with all 3000 unique characters
- **AI Extraction**: ✅ Production-ready, successfully processed all 3000 characters with no duplicates
- **Local OCR**: ⚠️ Working but low accuracy, kept for reference
- **PNG Generation**: ✅ Functional utility script

## Getting Started

1. **For using the web app**: See [`chinese_chr_app/README.md`](chinese_chr_app/README.md)
2. **For extracting character data**: See `extract_characters_using_ai/` folder
3. **For generating PNGs**: See `generate_png/` folder
