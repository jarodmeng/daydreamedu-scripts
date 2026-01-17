# AI-Based Character Extraction Pipeline

This folder contains scripts for extracting structured Chinese character data from PDF card sets using OpenAI's Batch API with vision models.

## Overview

The pipeline extracts character information (Index, Character, Pinyin, Radical, Strokes, Structure, Sentence, Words) from the 冯氏早教识字卡 PDF set using GPT-5-mini vision model via OpenAI's Batch API.

## Workflow

1. **Generate Requests** → `make_batch_jsonl_per_character.py`
2. **Upload Batch** → `upload_batch.py` or `sh/upload_day1.sh` / `sh/upload_day2.sh`
3. **Poll & Download** → `poll_and_merge_batches.py`
4. **Parse Results** → `parse_results.py`
5. **Validate** → `verify_results.py` (optional)

## Core Scripts

### 1. `make_batch_jsonl_per_character.py`

Generates OpenAI Batch JSONL request files from PDF character cards.

**Purpose**: Convert PDF files into batch request format for OpenAI API

**Key Features**:
- Reads PDFs named like `0001-0010.pdf`, `0011-0020.pdf`, etc.
- Extracts the second page of each character card (pages 2, 4, 6, ...)
- Renders pages to PNG using PyMuPDF
- Embeds images as base64-encoded data URLs
- Uses prompt from `chinese_character_extraction_prompt.md`
- Sets `custom_id` to 4-digit index (e.g., "0721")

**Usage**:
```bash
python3 make_batch_jsonl_per_character.py \
  --pdf_dir "/path/to/冯氏早教识字卡/" \
  --prompt_md ./chinese_character_extraction_prompt.md \
  --out_jsonl jsonl/requests.jsonl \
  --dpi 250 \
  --model gpt-5-mini \
  --max_pdfs 10 \
  --save_images
```

**Options**:
- `--pdf_dir`: Directory containing PDF files (required)
- `--prompt_md`: Path to prompt markdown file (required)
- `--out_jsonl`: Output JSONL file path (required)
- `--dpi`: DPI for PNG rendering (default: 250)
- `--model`: OpenAI model name (default: gpt-5-mini)
- `--max_pdfs`: Maximum number of PDFs to process (optional)
- `--max_file_size_mb`: Maximum output file size in MB (default: 50)
- `--save_images`: Save rendered PNG images to disk (optional)

**Output**: `jsonl/requests.jsonl` (or `requests_<ddd>.jsonl` if split by size)

### 2. `upload_batch.py`

Uploads JSONL files to OpenAI Batch API and manages batch processing.

**Purpose**: Upload batch requests and track batch status

**Key Features**:
- Uploads JSONL file to OpenAI
- Creates a batch job
- Tracks batch state (CREATED → COMPLETED → RESULT RETRIEVED)
- Saves batch metadata to `jsonl/batch_ids.json`
- Optionally polls for completion or uses `--no_poll` flag

**Usage**:
```bash
# Upload and poll until complete
python3 upload_batch.py \
  --jsonl jsonl/requests.jsonl \
  --output jsonl/results.jsonl

# Upload without polling (check status later)
python3 upload_batch.py \
  --jsonl jsonl/requests.jsonl \
  --output jsonl/results.jsonl \
  --no_poll

# Check status of existing batch
python3 upload_batch.py \
  --batch_id batch_xxx \
  --output jsonl/results.jsonl
```

**Options**:
- `--jsonl`: Input JSONL file path (required, unless using `--batch_id`)
- `--output`: Output results file path (required)
- `--batch_id`: Existing batch ID to check status (optional)
- `--no_poll`: Skip polling, just upload (optional)
- `--poll_interval`: Polling interval in seconds (default: 60)

**Output**: 
- `jsonl/results.jsonl` - Batch results
- `jsonl/batch_ids.json` - Updated with batch metadata

### 3. `poll_and_merge_batches.py`

Polls a single batch status and downloads results when complete.

**Purpose**: Monitor and download results from a single batch

**Usage**:
```bash
python3 poll_and_merge_batches.py \
  --batch_id batch_xxx \
  --output jsonl/results.jsonl \
  --no_poll
```

**Options**:
- `--batch_id`: Batch ID to poll (required)
- `--output`: Output file path (required)
- `--no_poll`: Skip polling, just download if complete (optional)

### 4. `parse_results.py`

Parses OpenAI Batch API results into structured CSV and JSON files.

**Purpose**: Convert raw batch results into usable data formats

**Key Features**:
- Extracts markdown tables from AI responses
- Parses: Index, Character, Pinyin, Radical, Strokes, Structure, Sentence, Words
- Validates data structure and formats
- Normalizes Index to 4-digit format
- Parses Pinyin and Words as JSON arrays

**Usage**:
```bash
python3 parse_results.py \
  --input jsonl/results.jsonl \
  --output output/characters.csv \
  --json output/characters.json \
  --validate \
  --stats
```

**Options**:
- `--input`: Input results JSONL file (default: `jsonl/results.jsonl`)
- `--output`: Output CSV file path (optional)
- `--json`: Output JSON file path (optional)
- `--validate`: Enable validation checks (optional)
- `--stats`: Show statistics (optional)

**Output**:
- `output/characters.csv` - CSV format (Words as JSON string)
- `output/characters.json` - JSON format (Words as JSON array)

## Utility Scripts

### 5. `verify_results.py`

Validates that extracted characters appear in their sentences and words.

**Purpose**: Verify character validation is working correctly

**Usage**:
```bash
python3 verify_results.py jsonl/results_005.jsonl jsonl/results_006.jsonl
```

**Output**: Summary of validation results (character appears in sentence & words)

### 6. `merge_results.py`

Merges multiple JSONL result files into a single file.

**Purpose**: Combine results from multiple batches

**Usage**:
```bash
python3 merge_results.py \
  --inputs jsonl/results_001.jsonl jsonl/results_002.jsonl \
  --output jsonl/results.jsonl
```

### 7. `validate_requests.py`

Validates JSONL request files before uploading.

**Purpose**: Check request files for errors before uploading

**Usage**:
```bash
python3 validate_requests.py jsonl/requests.jsonl
```

### 8. `analyze_token_usage.py`

Analyzes token usage from batch results to estimate costs.

**Purpose**: Calculate token usage and cost estimates

**Usage**:
```bash
python3 analyze_token_usage.py \
  jsonl/results_005.jsonl \
  jsonl/results_006.jsonl
```

**Output**: Token counts, cost breakdown, and estimates for remaining work

### 9. `summarize_tokens.py`

Summarizes token usage across multiple result files.

**Purpose**: Aggregate token usage statistics

**Usage**:
```bash
python3 summarize_tokens.py jsonl/results_*.jsonl
```

### 10. `list_batches.py`

Lists recent batches from OpenAI API.

**Purpose**: View batch status and metadata

**Usage**:
```bash
python3 list_batches.py
```

### 11. `upload_file_simple.py`

Simple utility to upload a file to OpenAI (for testing).

**Purpose**: Test file upload functionality

### 12. `generate_single_entry.py`

Generates a single JSONL request entry for reprocessing a specific character index.

**Purpose**: Regenerate request for a single character (useful for fixing errors)

**Usage**:
```bash
python3 generate_single_entry.py \
  --index 1298 \
  --pdf_dir "/path/to/冯氏早教识字卡/" \
  --prompt_md chinese_character_extraction_prompt.md \
  --output jsonl/requests_reprocess_002.jsonl \
  --dpi 250 \
  --model gpt-5-mini
```

**Options**:
- `--index`: Character index to extract (required)
- `--pdf_dir`: Directory containing PDF files (required)
- `--prompt_md`: Path to prompt markdown file (default: `chinese_character_extraction_prompt.md`)
- `--output`: Output JSONL file path (required)
- `--dpi`: DPI for PNG rendering (default: 250)
- `--model`: OpenAI model name (default: gpt-5-mini)

**Use case**: When a character is incorrectly extracted, use this script to regenerate just that one entry with the updated prompt, then upload it separately for reprocessing.

### 13. `organize_by_radicals.py`

Organizes characters by their radicals and outputs a JSON file.

**Purpose**: Group characters by radical for analysis and organization

**Key Features**:
- Reads character data from `characters.json`
- Groups all characters by their radical
- Strips dictionary markers (e.g., " (dictionary)") from radicals
- Outputs structured JSON with radical and character arrays
- Provides statistics on radical distribution

**Usage**:
```bash
# Use default paths (output/characters.json → output/characters_by_radicals.json)
python3 organize_by_radicals.py

# Specify custom paths
python3 organize_by_radicals.py \
  --input output/characters.json \
  --output output/characters_by_radicals.json
```

**Options**:
- `--input`: Input characters.json file path (default: `output/characters.json`)
- `--output`: Output JSON file path (default: `output/characters_by_radicals.json`)

**Output Format**:
```json
[
  {
    "radical": "口",
    "characters": [
      {
        "Character": "叫",
        "custom_id": "0123",
        "Index": "0123",
        "Pinyin": ["jiào"],
        "Strokes": "5",
        "Structure": "左右结构"
      },
      ...
    ]
  },
  ...
]
```

**Output**: `output/characters_by_radicals.json` - JSON array organized by radicals

**Statistics**: The script prints:
- Total number of unique radicals
- Top 10 radicals by character count
- Total characters processed

**Example Output**:
```
Loaded 3000 characters
Organized into 246 unique radicals
Top 10 radicals by character count:
  1. 口: 161 characters
  2. 扌: 160 characters
  3. 氵: 157 characters
  ...
```

## Shell Scripts

Located in `sh/` folder:

### `sh/upload_day1.sh`

Automated script to upload Day 1 batch files (007-010, 027).

**Usage**:
```bash
bash sh/upload_day1.sh
```

### `sh/upload_day2.sh`

Automated script to upload Day 2 batch files (011-026).

**Usage**:
```bash
bash sh/upload_day2.sh
```

## Configuration Files

### `chinese_character_extraction_prompt.md`

System prompt used for character extraction. Defines:
- Which pages to read (page 2 of each character pair)
- Fields to extract (8 columns)
- Dictionary cross-check rules
- Character validation requirements
- Output format (Markdown table)

## Directory Structure

```
extract_characters_using_ai/
├── jsonl/                    # Request and result files
│   ├── requests_*.jsonl      # Batch request files
│   ├── results_*.jsonl       # Batch result files
│   ├── results.jsonl         # Merged results
│   └── batch_ids.json        # Batch metadata
├── output/                   # Parsed output files
│   ├── characters.csv        # CSV format
│   └── characters.json             # JSON format
├── sh/                       # Shell scripts
│   ├── upload_day1.sh
│   └── upload_day2.sh
└── (Python scripts)
```

## Complete Workflow Example

### Step 1: Generate Requests
```bash
python3 make_batch_jsonl_per_character.py \
  --pdf_dir "/path/to/冯氏早教识字卡/" \
  --prompt_md ./chinese_character_extraction_prompt.md \
  --out_jsonl jsonl/requests.jsonl \
  --dpi 250 \
  --model gpt-5-mini
```

### Step 2: Upload Batch
```bash
python3 upload_batch.py \
  --jsonl jsonl/requests.jsonl \
  --output jsonl/results.jsonl \
  --no_poll
```

### Step 3: Check Status (later)
```bash
python3 list_batches.py
# Or check specific batch:
python3 poll_and_merge_batches.py \
  --batch_id batch_xxx \
  --output jsonl/results.jsonl \
  --no_poll
```

### Step 4: Parse Results
```bash
python3 parse_results.py \
  --input jsonl/results.jsonl \
  --output output/characters.csv \
  --json output/characters.json \
  --validate \
  --stats
```

### Step 5: Verify (optional)
```bash
python3 verify_results.py jsonl/results.jsonl
```

## Requirements

- Python 3.8+
- `openai` package: `pip install openai`
- `pymupdf` (fitz): `pip install pymupdf`
- OpenAI API key set as `OPENAI_API_KEY` environment variable

## Current Status

- ✅ Successfully processed 1,335 characters (0001-3000, with gaps)
- ✅ Character validation working correctly with strengthened prompt
- ✅ All entries pass validation checks
- ✅ Prompt updated with stronger validation (STOP IMMEDIATELY, 从/丛 example)
- ⏳ Remaining: 1,665 characters (1311-2975) - Day 2 files ready for upload

## Cost Optimization

- Average tokens per character: ~3,794 (based on recent processing)
- Average cost per character: ~$0.000595
- Free tier: 2,500,000 tokens/day
- Estimated cost for remaining 1,665 characters: ~$0.60 (if processed tomorrow with fresh free tier)

See `analyze_token_usage.py` for detailed cost analysis.

## Notes

- Batch API provides 50% discount on input/output tokens
- Cached tokens are free (prompt caching)
- Character validation in prompt prevents OCR errors (e.g., 要/耍, 晴/睛, 从/丛)
- Prompt includes strong validation with "STOP IMMEDIATELY" instruction
- Results are sorted by Index number in output files
- Use `generate_single_entry.py` to reprocess individual characters when errors are found
