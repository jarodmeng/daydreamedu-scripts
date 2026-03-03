# Extract Character from HWXNet

Extract Chinese character information from 汉文学网 (HWXNet) using DOM-based parsing.

## Source

Information is extracted from: `https://zd.hwxnet.com/search.do?keyword=<character>`

Where `<character>` is a single simplified Chinese character.

## Files

- **`extract_character_hwxnet.py`** - Core library for extracting information for a single character
- **`batch_extract_hwxnet.py`** - Batch extraction script with parallel processing support
- **`test_extract_character_hwxnet.py`** - Unit tests: 例词 extraction (minimal HTML, no network) plus full extraction tests (core fields, 常用词组, 例词 segmentation checks)
- **`validate_extracted_data.py`** - Data quality validation script
- **`extract_radical_stroke_counts.py`** - Extract radical → stroke count from [按部首查字](https://zd.hwxnet.com/bushou.html); writes `data/radical_stroke_counts.json` for the app’s Radicals page sort-by-stroke feature
- **`merge_resegmented_into_main_hwxnet.py`** - Merges 基本字义解释 from a resegmented JSON (e.g. `data/extracted_characters_hwxnet.resegmented_affected.json`) into `data/extracted_characters_hwxnet.json` with timestamped backup
- **`extracted_characters_hwxnet.json`** - Main output file containing extracted data for all characters (in `data/`)
- **`extracted_characters_hwxnet.resegmented_affected.json`** - Optional resegmented subset (e.g. 417 characters) used as input to the merge script

## Extracted Fields

The script extracts the following information for each character:

1. **分类** (Category) - e.g., 通用字, 常用字, 次常用字
2. **拼音** (Pinyin) - All pronunciations of the character (supports breve variants: ă, ĕ, ŏ, ĭ, ŭ)
3. **部首** (Radical) - The radical component
4. **总笔画** (Total strokes) - Total number of strokes
5. **基本字义解释** (Basic meaning/explanation) - Detailed meanings with pronunciations, explanations, and example words
6. **常用词组** (Common phrases) - List of phrases from the 常用词组 section when present (e.g. 卢比, 卢布, 卢沟桥); empty list when the section is absent
7. **英文翻译** (English translation) - English translation words
8. **index** - Character index from characters.json

## Usage

### Single Character Extraction

```python
from extract_character_hwxnet import extract_character_info

# Extract information for a character
info = extract_character_info("和")

# Access the extracted data
print(info["拼音"])  # ['hé', 'hè', 'huó', 'huò', 'huo', 'hú']
print(info["部首"])  # "口"
print(info["总笔画"])  # 8
print(info["基本字义解释"])  # List of pronunciations with meanings
```

### Batch Extraction

```bash
# Sequential extraction (default)
python batch_extract_hwxnet.py

# Parallel extraction with 4 workers
python batch_extract_hwxnet.py --parallel --workers 4

# Reprocess existing entries
python batch_extract_hwxnet.py --overwrite

# Resume from previous progress
python batch_extract_hwxnet.py --resume

# Test mode (limit to 10 characters)
python batch_extract_hwxnet.py --test
```

### Running Tests

```bash
# Run all tests: 例词 unit tests (minimal HTML) then full extraction tests (requires network)
python test_extract_character_hwxnet.py
```

### Validating Data

```bash
# Validate extracted data quality
python validate_extracted_data.py
```

### Merging resegmented 基本字义解释

After re-running extraction for a subset of characters (e.g. to fix 例词 segmentation), merge their 基本字义解释 into the main JSON with backup:

```bash
# Backs up data/extracted_characters_hwxnet.json to data/backups/, then merges from data/extracted_characters_hwxnet.resegmented_affected.json
python merge_resegmented_into_main_hwxnet.py
```

### Radical stroke counts (部首笔画)

Build a mapping of each radical to its stroke count from [按部首查字](https://zd.hwxnet.com/bushou.html) for use by the app (e.g. sorting the Radicals page by radical stroke count):

```bash
# Write chinese_chr_app/data/radical_stroke_counts.json (default)
python extract_radical_stroke_counts.py

# Custom output path
python extract_radical_stroke_counts.py --output /path/to/radical_stroke_counts.json

# Only include radicals listed in a file (JSON array or one radical per line)
python extract_radical_stroke_counts.py --filter-radicals radicals.txt

# Dry run: print mapping to stdout, do not write file
python extract_radical_stroke_counts.py --dry-run
```

## Output Format

The function returns a dictionary with the following structure:

```json
{
  "character": "和",
  "source_url": "https://zd.hwxnet.com/search.do?keyword=和",
  "分类": ["常用字", "通用字"],
  "拼音": ["hé", "hè", "huó", "huò", "huo", "hú"],
  "部首": "口",
  "总笔画": 8,
  "基本字义解释": [
    {
      "读音": "hé",
      "释义": [
        {
          "解释": "相安，谐调",
          "例词": ["和美", "和睦", "和谐", "和声", "和合", "和衷共济"]
        },
        ...
      ]
    },
    ...
  ],
  "常用词组": ["和美", "和睦", "和谐"],
  "英文翻译": ["peaceful", "calm", "peace", "harmony"],
  "index": "0042"
}
```

## DOM Structure

The script uses DOM-based extraction for accuracy:

- **分类, 拼音, 部首, 总笔画**: Extracted from `<div class="introduce">`
- **基本字义解释**: Extracted from `<h1>基本字义解释</h1>` followed by `<div class="con_basic">`
  - Uses "● " markers for pronunciations
  - Uses "◎ " or "⊙ " markers for meanings
  - Example words separated by "。"
- **常用词组**: Extracted from the section headed 常用词组: `<h1>常用词组</h1>` is inside `<div class="sub_label">`; the content is in that div’s next sibling `<div class="view_con clearfix">`. Entries are "◎ " bullets; the leading Chinese characters on each line form the phrase list.
- **英文翻译**: Extracted from `<div class="con_english">`

## Features

### Parallel Processing

The batch extraction script supports parallel processing using `ThreadPoolExecutor`:

- **Sequential mode** (default): Processes one character at a time
- **Parallel mode**: Use `--parallel` flag with `--workers N` to process multiple characters concurrently
- **Rate limiting**: Automatic rate limiting to respect server resources
- **Progress tracking**: Thread-safe progress saving and resuming

### Error Handling

- Automatic retries with exponential backoff
- Progress saving to resume interrupted extractions
- Comprehensive error reporting

### Data Quality

- Supports Chinese number parsing (一, 二, ..., 十九, 二十, etc.) for stroke counts
- Handles pinyin variants with breve marks (ă, ĕ, ŏ, ĭ, ŭ) for third tones
- Validates data completeness and quality
- Fixes known data inconsistencies (e.g., characters that are their own radical)

## Requirements

- Python 3.x
- beautifulsoup4
- lxml

Install dependencies:
```bash
pip install beautifulsoup4 lxml
```

Or use the requirements file:
```bash
pip install -r requirements.txt
```

## Notes

- The script uses the original keyword URL (not the resolved redirect URL)
- Pinyin extraction automatically filters out "Image" tokens
- **例词 (example words)** in 基本字义解释: extracted by splitting on "。" (Chinese period); only phrases that contain the target character are stored. **All** parentheticals "（...）" and "(...)" are removed from the example-words text before splitting.
- Chinese numbers (一, 二, 三, etc.) are automatically converted to integers for stroke counts
- The script handles both caron (ǎ, ě, ǒ, ǐ, ǔ) and breve (ă, ĕ, ŏ, ĭ, ŭ) variants for third-tone pinyin

## Known Data Quality Issues

The validation script may report some warnings for certain characters:

- **Missing 基本字义解释**: Some characters (e.g., "嗯") may have empty meanings due to special formatting in the source HTML (e.g., Zhuyin notation mixed with pinyin). This is a limitation of the current extraction logic.
- **Empty 英文翻译**: A small number of characters (e.g., "粼", "嚓", "嗒") may have empty English translations if the source page doesn't provide them.

These are minor data quality issues that don't affect the majority of extracted characters (99.9%+ have complete data).