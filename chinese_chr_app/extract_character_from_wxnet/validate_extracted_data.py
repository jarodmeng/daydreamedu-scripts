#!/usr/bin/env python3
"""
Validate data quality of extracted_characters_hwxnet.json

Checks:
- Required fields presence
- Data types and formats
- Index consecutiveness
- Value ranges and reasonableness
- Duplicate detection
- Cross-field consistency
"""

import json
import sys
import re
from pathlib import Path
from collections import Counter
from typing import Dict, List, Any, Tuple


# Required fields for each character entry
REQUIRED_FIELDS = [
    "character",
    "source_url",
    "分类",
    "拼音",
    "部首",
    "总笔画",
    "基本字义解释",
    "英文翻译",
    "index"
]

# Valid tone marks for pinyin
# Note: includes ă/ĕ/ŏ/ĭ/ŭ (a/e/o/i/u with breve) which some sites use instead of ǎ/ě/ǒ/ǐ/ǔ (caron)
TONE_MARKS = 'āáǎàăēéěèĕīíǐìĭōóǒòŏūúǔùŭǖǘǚǜü'


class ValidationResult:
    """Container for validation results."""
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = []
        self.stats = {}
    
    def add_error(self, message: str):
        self.errors.append(message)
    
    def add_warning(self, message: str):
        self.warnings.append(message)
    
    def add_info(self, message: str):
        self.info.append(message)
    
    def has_errors(self) -> bool:
        return len(self.errors) > 0
    
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


def validate_pinyin_format(pinyin: str) -> Tuple[bool, str]:
    """
    Validate pinyin format.
    Returns (is_valid, error_message)
    """
    if not pinyin:
        return False, "Empty pinyin"
    
    # Check for valid pinyin characters (letters and tone marks)
    # Note: includes ă/ĕ/ŏ/ĭ/ŭ (a/e/o/i/u with breve) which some sites use instead of ǎ/ě/ǒ/ǐ/ǔ (caron)
    # Also accepts numbers 1-5 at the end for tone marks (e.g., "ng4" for 嗯)
    if not (re.match(r'^[a-zāáǎàăēéěèĕīíǐìĭōóǒòŏūúǔùŭǖǘǚǜü]+$', pinyin, re.IGNORECASE) or
            re.match(r'^[a-zāáǎàăēéěèĕīíǐìĭōóǒòŏūúǔùŭǖǘǚǜü]+[1-5]$', pinyin, re.IGNORECASE)):
        return False, f"Invalid characters in pinyin: {pinyin}"
    
    # Check length (single character pinyin is typically 1-6 chars)
    if len(pinyin) > 10:
        return False, f"Pinyin too long (likely compound word): {pinyin}"
    
    return True, ""


def validate_strokes(strokes: Any, field_name: str) -> Tuple[bool, str]:
    """
    Validate stroke count.
    Returns (is_valid, error_message)
    """
    if strokes is None:
        return False, f"{field_name} is None"
    
    if not isinstance(strokes, int):
        return False, f"{field_name} is not an integer: {type(strokes)}"
    
    if strokes < 0:
        return False, f"{field_name} is negative: {strokes}"
    
    if strokes > 50:  # Reasonable upper limit
        return False, f"{field_name} is unreasonably large: {strokes}"
    
    return True, ""


def validate_meanings(meanings: Any) -> Tuple[bool, str]:
    """
    Validate 基本字义解释 structure.
    Returns (is_valid, error_message)
    """
    if not isinstance(meanings, list):
        return False, f"基本字义解释 is not a list: {type(meanings)}"
    
    if len(meanings) == 0:
        return False, "基本字义解释 is empty"
    
    for i, meaning in enumerate(meanings):
        if not isinstance(meaning, dict):
            return False, f"基本字义解释[{i}] is not a dict: {type(meaning)}"
        
        if "读音" not in meaning:
            return False, f"基本字义解释[{i}] missing '读音' field"
        
        if "释义" not in meaning:
            return False, f"基本字义解释[{i}] missing '释义' field"
        
        if not isinstance(meaning["释义"], list):
            return False, f"基本字义解释[{i}]['释义'] is not a list"
        
        if len(meaning["释义"]) == 0:
            return False, f"基本字义解释[{i}]['释义'] is empty"
        
        for j, shiyi in enumerate(meaning["释义"]):
            if not isinstance(shiyi, dict):
                return False, f"基本字义解释[{i}]['释义'][{j}] is not a dict"
            
            if "解释" not in shiyi:
                return False, f"基本字义解释[{i}]['释义'][{j}] missing '解释' field"
            
            if "例词" not in shiyi:
                return False, f"基本字义解释[{i}]['释义'][{j}] missing '例词' field"
            
            if not isinstance(shiyi["例词"], list):
                return False, f"基本字义解释[{i}]['释义'][{j}]['例词'] is not a list"
    
    return True, ""


def validate_character_entry(char: str, entry: Dict[str, Any], result: ValidationResult):
    """Validate a single character entry."""
    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in entry:
            result.add_error(f"{char}: Missing required field '{field}'")
    
    # Validate character field matches key
    if "character" in entry and entry["character"] != char:
        result.add_error(f"{char}: Character field mismatch: expected '{char}', got '{entry.get('character')}'")
    
    # Validate 分类
    if "分类" in entry:
        fenlei = entry["分类"]
        if not isinstance(fenlei, list):
            result.add_error(f"{char}: 分类 is not a list: {type(fenlei)}")
        elif len(fenlei) == 0:
            result.add_warning(f"{char}: 分类 is empty")
        else:
            valid_categories = ["通用字", "常用字", "次常用字"]
            for cat in fenlei:
                if cat not in valid_categories:
                    result.add_warning(f"{char}: Unknown category '{cat}' in 分类")
    
    # Validate 拼音
    if "拼音" in entry:
        pinyin_list = entry["拼音"]
        if not isinstance(pinyin_list, list):
            result.add_error(f"{char}: 拼音 is not a list: {type(pinyin_list)}")
        else:
            if len(pinyin_list) == 0:
                result.add_warning(f"{char}: 拼音 is empty")
            else:
                for pinyin in pinyin_list:
                    is_valid, error_msg = validate_pinyin_format(pinyin)
                    if not is_valid:
                        result.add_warning(f"{char}: Invalid pinyin format: {error_msg}")
    
    # Validate 部首
    if "部首" in entry:
        bushou = entry["部首"]
        if not isinstance(bushou, str):
            result.add_error(f"{char}: 部首 is not a string: {type(bushou)}")
        elif len(bushou) == 0:
            result.add_warning(f"{char}: 部首 is empty")
        elif len(bushou) > 1:
            result.add_warning(f"{char}: 部首 has multiple characters: '{bushou}'")
    
    # Validate 总笔画
    if "总笔画" in entry:
        is_valid, error_msg = validate_strokes(entry["总笔画"], "总笔画")
        if not is_valid:
            result.add_error(f"{char}: {error_msg}")
    
    # Validate 基本字义解释
    if "基本字义解释" in entry:
        is_valid, error_msg = validate_meanings(entry["基本字义解释"])
        if not is_valid:
            result.add_error(f"{char}: 基本字义解释 validation failed: {error_msg}")
    
    # Validate 英文翻译
    if "英文翻译" in entry:
        english = entry["英文翻译"]
        if not isinstance(english, list):
            result.add_error(f"{char}: 英文翻译 is not a list: {type(english)}")
        elif len(english) == 0:
            result.add_warning(f"{char}: 英文翻译 is empty")
        else:
            for word in english:
                if not isinstance(word, str):
                    result.add_warning(f"{char}: 英文翻译 contains non-string: {type(word)}")
                elif not re.match(r'^[a-z]+$', word, re.IGNORECASE):
                    result.add_warning(f"{char}: 英文翻译 contains invalid word: '{word}'")
    
    # Validate index
    if "index" in entry:
        index = entry["index"]
        if not isinstance(index, (str, int)):
            result.add_error(f"{char}: index is not string or int: {type(index)}")
        else:
            try:
                index_int = int(str(index))
                if index_int < 1:
                    result.add_error(f"{char}: index is less than 1: {index}")
                if index_int > 10000:  # Reasonable upper limit
                    result.add_warning(f"{char}: index is very large: {index}")
            except ValueError:
                result.add_error(f"{char}: index cannot be converted to int: {index}")


def validate_file_structure(data: Dict[str, Any], result: ValidationResult):
    """Validate overall file structure and consistency."""
    if not isinstance(data, dict):
        result.add_error(f"Root element is not a dict: {type(data)}")
        return
    
    total_chars = len(data)
    result.stats["total_characters"] = total_chars
    
    if total_chars == 0:
        result.add_error("File is empty (no characters)")
        return
    
    # Check for duplicate characters
    chars = list(data.keys())
    if len(chars) != len(set(chars)):
        duplicates = [char for char, count in Counter(chars).items() if count > 1]
        result.add_error(f"Duplicate character keys found: {duplicates}")
    
    # Check index consecutiveness
    indices = []
    missing_indices = []
    invalid_indices = []
    
    for char, entry in data.items():
        if "index" not in entry:
            missing_indices.append(char)
        else:
            try:
                idx = int(str(entry["index"]))
                indices.append(idx)
            except (ValueError, TypeError):
                invalid_indices.append((char, entry["index"]))
    
    result.stats["characters_with_index"] = len(indices)
    result.stats["characters_missing_index"] = len(missing_indices)
    result.stats["characters_invalid_index"] = len(invalid_indices)
    
    if missing_indices:
        result.add_error(f"{len(missing_indices)} characters missing index field")
        if len(missing_indices) <= 20:
            result.add_error(f"  Missing indices: {missing_indices}")
    
    if invalid_indices:
        result.add_error(f"{len(invalid_indices)} characters have invalid index format")
        if len(invalid_indices) <= 10:
            result.add_error(f"  Invalid indices: {invalid_indices[:10]}")
    
    if indices:
        unique_indices = sorted(set(indices))
        min_idx = min(unique_indices)
        max_idx = max(unique_indices)
        
        result.stats["index_range"] = (min_idx, max_idx)
        result.stats["unique_indices"] = len(unique_indices)
        
        # Check for duplicates
        index_counts = Counter(indices)
        duplicates = [idx for idx, count in index_counts.items() if count > 1]
        if duplicates:
            result.add_error(f"Found {len(duplicates)} duplicate indices: {sorted(duplicates)[:20]}")
        
        # Check for gaps
        expected_range = set(range(min_idx, max_idx + 1))
        present_indices = set(unique_indices)
        gaps = sorted(expected_range - present_indices)
        
        if gaps:
            result.add_warning(f"Found {len(gaps)} missing indices (gaps in sequence)")
            if len(gaps) <= 20:
                result.add_warning(f"  Missing indices: {gaps[:20]}")
        else:
            result.add_info(f"All indices are consecutive from {min_idx} to {max_idx}")
        
        # Check if starting from 1
        if min_idx != 1:
            result.add_warning(f"Indices start from {min_idx}, not 1")
    
    # Field completeness statistics
    field_stats = {}
    for field in REQUIRED_FIELDS:
        present = sum(1 for entry in data.values() if field in entry and entry[field] is not None)
        field_stats[field] = {
            "present": present,
            "missing": total_chars - present,
            "percentage": (present / total_chars * 100) if total_chars > 0 else 0
        }
    
    result.stats["field_completeness"] = field_stats
    
    # Check for empty critical fields
    empty_pinyin = [char for char, entry in data.items() 
                   if entry.get("拼音") in ([], None)]
    empty_meanings = [char for char, entry in data.items() 
                     if not entry.get("基本字义解释")]
    empty_english = [char for char, entry in data.items() 
                    if entry.get("英文翻译") in ([], None)]
    
    result.stats["empty_pinyin"] = len(empty_pinyin)
    result.stats["empty_meanings"] = len(empty_meanings)
    result.stats["empty_english"] = len(empty_english)
    
    if empty_pinyin:
        result.add_warning(f"{len(empty_pinyin)} characters have empty pinyin")
        if len(empty_pinyin) <= 20:
            result.add_warning(f"  Empty pinyin: {empty_pinyin[:20]}")
    
    if empty_meanings:
        result.add_warning(f"{len(empty_meanings)} characters have empty meanings")
        if len(empty_meanings) <= 20:
            result.add_warning(f"  Empty meanings: {empty_meanings[:20]}")
    
    if empty_english:
        result.add_warning(f"{len(empty_english)} characters have empty English translation")
        if len(empty_english) <= 20:
            result.add_warning(f"  Empty English: {empty_english[:20]}")


def main():
    """Main validation function."""
    script_dir = Path(__file__).resolve().parent
    data_dir = script_dir.parent / "data"
    json_file = data_dir / "extracted_characters_hwxnet.json"
    
    print("="*70)
    print("VALIDATING extracted_characters_hwxnet.json")
    print("="*70)
    
    if not json_file.exists():
        print(f"\n✗ ERROR: File not found: {json_file}")
        return 1
    
    # Load JSON file
    print(f"\nLoading {json_file.name}...")
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"\n✗ ERROR: Invalid JSON format: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ ERROR: Failed to load file: {e}")
        return 1
    
    print(f"Loaded {len(data)} character entries")
    
    # Validate
    result = ValidationResult()
    
    print("\nValidating file structure...")
    validate_file_structure(data, result)
    
    print(f"\nValidating individual character entries...")
    for i, (char, entry) in enumerate(data.items(), 1):
        if i % 500 == 0:
            print(f"  Progress: {i}/{len(data)} characters validated...")
        validate_character_entry(char, entry, result)
    
    # Print results
    print(f"\n{'='*70}")
    print("VALIDATION RESULTS")
    print(f"{'='*70}")
    
    # Statistics
    if result.stats:
        print("\nSTATISTICS:")
        print(f"  Total characters: {result.stats.get('total_characters', 'N/A')}")
        print(f"  Characters with index: {result.stats.get('characters_with_index', 'N/A')}")
        print(f"  Characters missing index: {result.stats.get('characters_missing_index', 'N/A')}")
        
        if "index_range" in result.stats:
            min_idx, max_idx = result.stats["index_range"]
            print(f"  Index range: {min_idx} to {max_idx}")
            print(f"  Unique indices: {result.stats.get('unique_indices', 'N/A')}")
        
        if "field_completeness" in result.stats:
            print(f"\n  FIELD COMPLETENESS:")
            for field, stats in result.stats["field_completeness"].items():
                pct = stats["percentage"]
                status = "✓" if pct == 100 else "⚠" if pct >= 95 else "✗"
                print(f"    {status} {field}: {stats['present']}/{result.stats['total_characters']} ({pct:.1f}%)")
        
        if "empty_pinyin" in result.stats:
            print(f"\n  DATA QUALITY:")
            print(f"    Empty pinyin: {result.stats.get('empty_pinyin', 0)}")
            print(f"    Empty meanings: {result.stats.get('empty_meanings', 0)}")
            print(f"    Empty English: {result.stats.get('empty_english', 0)}")
    
    # Errors
    if result.errors:
        print(f"\n✗ ERRORS ({len(result.errors)}):")
        for error in result.errors[:50]:  # Show first 50 errors
            print(f"  {error}")
        if len(result.errors) > 50:
            print(f"  ... and {len(result.errors) - 50} more errors")
    else:
        print(f"\n✓ NO ERRORS FOUND")
    
    # Warnings
    if result.warnings:
        print(f"\n⚠ WARNINGS ({len(result.warnings)}):")
        for warning in result.warnings[:50]:  # Show first 50 warnings
            print(f"  {warning}")
        if len(result.warnings) > 50:
            print(f"  ... and {len(result.warnings) - 50} more warnings")
    else:
        print(f"\n✓ NO WARNINGS")
    
    # Info
    if result.info:
        print(f"\nℹ INFO ({len(result.info)}):")
        for info in result.info[:20]:  # Show first 20 info messages
            print(f"  {info}")
        if len(result.info) > 20:
            print(f"  ... and {len(result.info) - 20} more info messages")
    
    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    
    if result.has_errors():
        print(f"✗ VALIDATION FAILED: {len(result.errors)} error(s) found")
        return 1
    elif result.has_warnings():
        print(f"⚠ VALIDATION PASSED WITH WARNINGS: {len(result.warnings)} warning(s)")
        return 0
    else:
        print(f"✓ VALIDATION PASSED: No errors or warnings")
        return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
