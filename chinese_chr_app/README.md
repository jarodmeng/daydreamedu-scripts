## Chinese Character Card Extraction Pipeline

This folder contains experiments and scripts for extracting structured data from the 冯氏早教识字卡 PDF set (index, character, pinyin, radical, strokes, structure, sentence, words).

### Overview of Approaches

- **Attempt 1 – Local OCR (not recommended now)**  
  - Location: `extract_using_local_ocr/` folder  
  - Script: `extract_using_local_ocr/extract_feng_cards.py`  
  - Approach:  
    - Render each PDF page with `pdftoppm`  
    - Use Tesseract (`chi_sim`) to OCR:
      - Page 1 center region → big character  
      - Page 2 top-right corner → index number  
  - Status: **Results not very good**  
    - OCR struggled on some fonts / low-res scans  
    - Index numbers and some characters were unreliable  
    - Kept for reference, but no longer the main path.

- **Attempt 2 – OpenAI Batch API (current recommended path)**  
  - Location: `extract_characters_using_ai/` folder  
  - Idea: Treat the back of each card (2nd page of each pair) as an image and let a vision model do structured extraction, with a carefully designed prompt and dictionary cross-check.
  - Result: **Promising** – test run on characters `0001–0100` produced clean, validated data.

### Files and Scripts

All Attempt 2 files are located in the `extract_characters_using_ai/` subfolder:

- `extract_characters_using_ai/chinese_character_extraction_prompt.md`  
  - System prompt used for the vision model.  
  - Defines:
    - Which pages to read (only page 2 of each 2-page pair: 2,4,6,8,...)  
    - Fields to extract: **Index, Character, Pinyin, Radical, Strokes, Structure, Sentence (例句), Words (词组)**  
    - Dictionary cross-check rules and how to mark corrections with `(dictionary)`  
    - Output format: **single Markdown table** with 8 columns (Words must be a JSON array).

- `extract_characters_using_ai/make_batch_jsonl_per_character.py`  
  - Generates one **OpenAI Batch JSONL request per character**.  
  - Expects PDFs in a directory, named like `dddd-dddd.pdf`, e.g. `0721-0730.pdf`.  
  - For each range file:
    - Parses the index range from the filename (e.g. `0721–0730`)  
    - Assumes 2 pages per character and extracts only the **second page** for each character (pages 2,4,6,...)  
    - Renders those pages to PNG using **PyMuPDF (fitz)**  
    - Embeds each page as a base64 `data:image/png;base64,...` URL in a JSONL line  
    - Uses `chinese_character_extraction_prompt.md` as the system message  
    - Sets `custom_id` to the 4-digit index (e.g. `0721`) so downstream parsing is simple.
  - Example command used in this project:
    ```bash
    cd extract_characters_using_ai
    python3 make_batch_jsonl_per_character.py \
      --pdf_dir "/Users/jarodm/Library/CloudStorage/GoogleDrive-winston.ry.meng@gmail.com/My Drive/冯氏早教识字卡/" \
      --prompt_md ./chinese_character_extraction_prompt.md \
      --out_jsonl jsonl/requests.jsonl \
      --dpi 250 \
      --model gpt-5-mini \
      --max_pdfs 10 \
      --save_images
    ```
  - Output: `jsonl/requests.jsonl` – ready to upload to the OpenAI Batch API.

- `extract_characters_using_ai/upload_batch.py`  
  - Master script to **upload** `requests.jsonl` and manage the Batch run.  
  - Responsibilities:
    - Uploads the JSONL as a `file` with purpose `"batch"`  
    - Creates a batch for the `/v1/responses` endpoint  
    - Polls batch status until it reaches `completed` (or fails/ends)  
    - Downloads the **output file** to a local `results.jsonl`  
  - Example usage:
    ```bash
    cd extract_characters_using_ai
    # Assumes OPENAI_API_KEY is set in your shell
    python3 upload_batch.py --jsonl jsonl/requests.jsonl --output jsonl/results.jsonl
    ```
  - The script prints the `batch_id` so you can re-check status later:
    ```bash
    python3 upload_batch.py --batch_id <batch_id> --output results.jsonl
    ```

- `extract_characters_using_ai/parse_results.py`  
  - Parses the Batch API `results.jsonl` and turns the model’s Markdown table outputs into structured data.  
  - For each line:
    - Locates the assistant message with `output_text`  
    - Extracts the Markdown table row  
    - Parses: **Index, Character, Pinyin, Radical, Strokes, Structure, Sentence, Words**  
    - Normalizes `Index` to 4-digit format (e.g. `1 → 0001`)  
    - Validates `Words` as a JSON array and parses it for JSON output  
    - Attaches `custom_id` (should match the 4-digit index).
  - Also supports:
    - **Validation** (checks required fields, numeric strokes, single-character `Character`, valid JSON array for `Words`, etc.)  
    - **Statistics** (index range, unique characters, count of `(dictionary)` corrections).
  - Example command used for the first batch (0001–0100):
    ```bash
    cd extract_characters_using_ai
    python3 parse_results.py \
      --input jsonl/results.jsonl \
      --output output/characters.csv \
      --json output/characters.json \
      --validate \
      --stats
    ```
  - Output:
    - `output/characters.csv` – 100 rows with columns: `custom_id, Index, Character, Pinyin, Radical, Strokes, Structure, Sentence, Words` (Words stored as JSON string)  
    - `output/characters.json` – same data in JSON form (Words parsed as actual JSON array).

### Current Status

- **Attempt 1 (local OCR, `extract_using_local_ocr/extract_feng_cards.py`)**:  
  - Working end‑to‑end but accuracy is not sufficient, especially for indices and some glyphs.  
  - Kept for historical reference and possible hybrid use, but not the primary pipeline.

- **Attempt 2 (OpenAI Batch + vision prompt)**:  
  - Successfully processed **0001–0100** using the `/v1/responses` Batch endpoint.  
  - All 100 requests completed with **0 failures**, and validation passed with **0 issues**.  
  - This is the **current recommended approach** for extracting data from the 冯氏早教识字卡 PDFs.

### How to Run the Full Pipeline (Summary)

All commands should be run from the `extract_characters_using_ai/` directory:

1. **Generate requests JSONL**  
   ```bash
   cd extract_characters_using_ai
   python3 make_batch_jsonl_per_character.py \
     --pdf_dir "/path/to/冯氏早教识字卡/" \
     --prompt_md ./chinese_character_extraction_prompt.md \
     --out_jsonl requests.jsonl \
     --dpi 250 \
     --model gpt-5-mini \
     --max_pdfs 10 \
     --save_images
   ```

2. **Upload and run Batch**  
   - Ensure `OPENAI_API_KEY` is set in your shell.  
   ```bash
   cd extract_characters_using_ai
   python3 upload_batch.py --jsonl requests.jsonl --output results.jsonl
   ```

3. **Parse and validate results**  
   ```bash
   cd extract_characters_using_ai
   python3 parse_results.py \
     --input results.jsonl \
     --output characters.csv \
     --json characters.json \
     --validate \
     --stats
   ```

You can repeat steps 1–3 for additional PDF ranges (e.g., 0101–0200, etc.) by adjusting `--max_pdfs` or pointing `--pdf_dir` to the appropriate subset.

