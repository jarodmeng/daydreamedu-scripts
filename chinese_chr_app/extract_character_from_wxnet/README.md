# Extract Character from HWXNet

Extract Chinese character information from 汉文学网 (HWXNet) using DOM-based parsing.

## Source

Information is extracted from: `https://zd.hwxnet.com/search.do?keyword=<character>`

Where `<character>` is a single simplified Chinese character.

## Files

- **`extract_character_hwxnet.py`** - Core library for extracting information for a single character
- **`batch_extract_hwxnet.py`** - Batch extraction script with parallel processing support
- **`test_extract_character_hwxnet.py`** - Unit tests for the extraction library
- **`validate_extracted_data.py`** - Data quality validation script
- **`extracted_characters_hwxnet.json`** - Output file containing extracted data for all characters (located in `data/` folder)

## Extracted Fields

The script extracts the following information for each character:

1. **分类** (Category) - e.g., 通用字, 常用字, 次常用字
2. **拼音** (Pinyin) - All pronunciations of the character (supports breve variants: ă, ĕ, ŏ, ĭ, ŭ)
3. **部首** (Radical) - The radical component
4. **总笔画** (Total strokes) - Total number of strokes
5. **基本字义解释** (Basic meaning/explanation) - Detailed meanings with pronunciations, explanations, and example words
6. **英文翻译** (English translation) - English translation words
7. **index** - Character index from characters.json

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
# Run unit tests
python test_extract_character_hwxnet.py
```

### Validating Data

```bash
# Validate extracted data quality
python validate_extracted_data.py
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
- Example words are extracted by splitting on "。" (Chinese period)
- Parenthetical explanations in example words are automatically removed
- Chinese numbers (一, 二, 三, etc.) are automatically converted to integers for stroke counts
- The script handles both caron (ǎ, ě, ǒ, ǐ, ǔ) and breve (ă, ĕ, ŏ, ĭ, ŭ) variants for third-tone pinyin

## Known Data Quality Issues

The validation script may report some warnings for certain characters:

- **Missing 基本字义解释**: Some characters (e.g., "嗯") may have empty meanings due to special formatting in the source HTML (e.g., Zhuyin notation mixed with pinyin). This is a limitation of the current extraction logic.
- **Empty 英文翻译**: A small number of characters (e.g., "粼", "嚓", "嗒") may have empty English translations if the source page doesn't provide them.

These are minor data quality issues that don't affect the majority of extracted characters (99.9%+ have complete data).